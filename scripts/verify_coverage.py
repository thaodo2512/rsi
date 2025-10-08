#!/usr/bin/env python3
import argparse
import datetime as dt
import gzip
import json
import os
from pathlib import Path
from typing import Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "user_data" / "config.json"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def infer_data_path(exchange: str, timeframe: str, pair: str) -> Optional[Path]:
    """Return path to OHLCV file for a pair/timeframe.
    Supports both legacy flat layout and nested spot/timeframe layout.
    """
    exch = exchange.lower()
    pair_key = pair.replace("/", "_")

    # New-style nested path
    nested = ROOT / "user_data" / "data" / exch / "spot" / timeframe
    # Legacy flat path
    flat = ROOT / "user_data" / "data" / exch

    candidates = [
        nested / f"{pair_key}-{timeframe}.json",
        nested / f"{pair_key}-{timeframe}.json.gz",
        flat / f"{pair_key}-{timeframe}.json",
        flat / f"{pair_key}-{timeframe}.json.gz",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def read_ts_range(path: Path) -> Optional[Tuple[dt.datetime, dt.datetime]]:
    def _parse_rows(rows) -> Optional[Tuple[dt.datetime, dt.datetime]]:
        if not rows:
            return None
        # Common freqtrade json format: list of lists [ts_ms, o, h, l, c, v]
        if isinstance(rows[0], (list, tuple)) and len(rows[0]) >= 6:
            # compute min/max of timestamp (ms)
            tmin = min(int(r[0]) for r in rows)
            tmax = max(int(r[0]) for r in rows)
            return (dt.datetime.utcfromtimestamp(tmin / 1000), dt.datetime.utcfromtimestamp(tmax / 1000))
        # Fallback: list of dicts with possible keys
        if isinstance(rows[0], dict):
            # Try ms fields
            keys = ["time", "timestamp", "date", "t", "open_time"]
            ts = None
            te = None
            for r in rows:
                val = None
                for k in keys:
                    if k in r:
                        val = r[k]
                        break
                if val is None:
                    continue
                if isinstance(val, (int, float)):
                    epoch = float(val)
                    if epoch > 10_000_000_000:  # ns
                        epoch = epoch / 1e9
                    elif epoch > 10_000_000:  # ms
                        epoch = epoch / 1e3
                    tcur = dt.datetime.utcfromtimestamp(epoch)
                else:
                    # assume ISO string
                    try:
                        tcur = dt.datetime.fromisoformat(str(val).replace("Z", "+00:00")).astimezone(dt.timezone.utc).replace(tzinfo=None)
                    except Exception:
                        continue
                ts = tcur if ts is None or tcur < ts else ts
                te = tcur if te is None or tcur > te else te
            if ts and te:
                return (ts, te)
        return None

    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                rows = json.load(f)
        else:
            with path.open("r", encoding="utf-8") as f:
                rows = json.load(f)
        return _parse_rows(rows)
    except Exception:
        return None


def parse_date(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify OHLCV coverage vs FreqAI warmup and backtest window.")
    ap.add_argument("--start", required=True, help="Backtest start date YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="Backtest end date YYYY-MM-DD")
    ap.add_argument("--timeframe", default=None, help="Timeframe (default: read from config.json)")
    ap.add_argument("--pairs", default=None, help="Space-separated pairs (default: config whitelist)")
    args = ap.parse_args()

    cfg = load_config(CONFIG)
    timeframe = args.timeframe or cfg.get("timeframe") or "5m"
    exch = (cfg.get("exchange", {}).get("name") or "binance").lower()
    train_days = int(cfg.get("freqai", {}).get("train_period_days", 365))
    pairs = args.pairs.split() if args.pairs else cfg.get("exchange", {}).get("pair_whitelist", [])

    start = parse_date(args.start)
    end = parse_date(args.end)
    earliest_needed = start - dt.timedelta(days=train_days)

    print(f"Config: timeframe={timeframe}, exchange={exch}, train_period_days={train_days}")
    print(f"Backtest: start={start.date()} end={end.date()} (need data from <= {earliest_needed.date()})")
    print("")

    ok = True
    for pair in pairs:
        path = infer_data_path(exch, timeframe, pair)
        if not path:
            print(f"[MISSING] {pair}: no file found under user_data/data/{exch}/(spot/{timeframe}|.)")
            ok = False
            continue
        rng = read_ts_range(path)
        if not rng:
            print(f"[UNREADABLE] {pair}: could not parse timestamps from {path}")
            ok = False
            continue
        first, last = rng
        need_earliest = earliest_needed
        need_latest = end + dt.timedelta(days=1)
        status = "OK"
        if first > need_earliest:
            status = "INSUFFICIENT_EARLY_DATA"
            ok = False
        if last < end:
            status = "INSUFFICIENT_LATE_DATA"
            ok = False
        print(f"[{status}] {pair}: file={path.name} first={first} last={last} needed_first<={need_earliest}")

    if not ok:
        print("\nOne or more pairs lack sufficient coverage.")
        print("Suggestions:")
        print("- Use timerange download (recommended):")
        tr = f"{earliest_needed.strftime('%Y%m%d')}-{(end).strftime('%Y%m%d')}"
        pairs_arg = " ".join(f"-p {p}" for p in pairs)
        print(f"  docker compose run --rm freqtrade download-data -c /freqtrade/user_data/config.json -t {timeframe} --timerange {tr} {pairs_arg}")
        print("- Or increase days to cover earliest_need from today (may be large).")
        return 2

    print("\nAll pairs have sufficient coverage for the requested backtest window and FreqAI warmup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
