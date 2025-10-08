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


def infer_data_path(exchange: str, timeframe: str, pair: str, mode: str) -> Optional[Path]:
    """Return path to OHLCV file for a pair/timeframe.
    Supports both legacy flat layout and nested spot/futures layout.
    """
    exch = exchange.lower()
    settle = "USDT"  # Assume USDT for Binance futures; adjust if using USDC or others
    full_pair = f"{pair}:{settle}" if mode == "futures" and ':' not in pair else pair
    pair_key = full_pair.replace("/", "_").replace(":", "_")
    suffix = "-futures" if mode == "futures" else ""
    subdir = "futures" if mode == "futures" else ""

    file_base = f"{pair_key}-{timeframe}{suffix}"
    data_dir = ROOT / "user_data" / "data" / exch
    nested_dir = data_dir / subdir if subdir else data_dir
    flat_dir = data_dir  # Legacy flat is directly in data/{exch}

    candidates = [
        nested_dir / f"{file_base}.json",
        nested_dir / f"{file_base}.json.gz",
        flat_dir / f"{file_base}.json",
        flat_dir / f"{file_base}.json.gz",
        # Add .feather or .parquet if your config uses them (check "dataformat_ohlcv" in config.json)
        # nested_dir / f"{file_base}.feather",
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
            return (
                dt.datetime.fromtimestamp(tmin / 1000, dt.timezone.utc),
                dt.datetime.fromtimestamp(tmax / 1000, dt.timezone.utc),
            )
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
                    tcur = dt.datetime.fromtimestamp(epoch, dt.timezone.utc)
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


def parse_date_utc(s: str) -> dt.datetime:
    # Interpret input date as UTC midnight
    return dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)


def timeframe_to_timedelta(tf: str) -> dt.timedelta:
    tf = tf.strip().lower()
    unit = tf[-1]
    try:
        val = int(tf[:-1])
    except Exception:
        raise ValueError(f"Invalid timeframe: {tf}")
    if unit == 'm':
        return dt.timedelta(minutes=val)
    if unit == 'h':
        return dt.timedelta(hours=val)
    if unit == 'd':
        return dt.timedelta(days=val)
    raise ValueError(f"Unsupported timeframe unit in: {tf}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify OHLCV coverage vs FreqAI warmup and backtest window.")
    ap.add_argument("--start", required=True, help="Backtest start date YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="Backtest end date YYYY-MM-DD")
    ap.add_argument("--timeframe", default=None, help="Timeframe (default: read from config.json)")
    ap.add_argument("--pairs", default=None, help="Space-separated pairs (default: config whitelist)")
    ap.add_argument(
        "--late-policy",
        choices=["day", "frame", "end"],
        default="frame",
        help="Late coverage policy: 'day' requires >= end+1day, 'frame' requires >= end+timeframe (default), 'end' requires >= end",
    )
    args = ap.parse_args()

    cfg = load_config(CONFIG)
    timeframe = args.timeframe or cfg.get("timeframe") or "5m"
    exch = (cfg.get("exchange", {}).get("name") or "binance").lower()
    mode = (cfg.get("trading_mode") or "spot").lower()
    train_days = int(cfg.get("freqai", {}).get("train_period_days", 365))
    pairs = args.pairs.split() if args.pairs else cfg.get("exchange", {}).get("pair_whitelist", [])

    start = parse_date_utc(args.start)
    end = parse_date_utc(args.end)
    earliest_needed = start - dt.timedelta(days=train_days)
    tf_delta = timeframe_to_timedelta(timeframe)
    if args.late_policy == "day":
        need_latest = end + dt.timedelta(days=1)
    elif args.late_policy == "frame":
        need_latest = end + tf_delta
    else:  # 'end'
        need_latest = end
    # Don't require future data
    now_utc = dt.datetime.now(dt.timezone.utc)
    if need_latest > now_utc:
        need_latest = now_utc

    print(f"Config: timeframe={timeframe}, exchange={exch}, train_period_days={train_days}")
    print(f"Backtest: start={start.date()} end={end.date()} (need data from <= {earliest_needed.date()} to >= {need_latest.date()})")
    print("")

    ok = True
    for pair in pairs:
        path = infer_data_path(exch, timeframe, pair, mode)
        if not path:
            print(f"[MISSING] {pair}: no file found under user_data/data/{exch}/({mode if mode != 'spot' else ''})")
            ok = False
            continue
        rng = read_ts_range(path)
        if not rng:
            print(f"[UNREADABLE] {pair}: could not parse timestamps from {path}")
            ok = False
            continue
        first, last = rng
        status = "OK"
        if first > earliest_needed:
            status = "INSUFFICIENT_EARLY_DATA"
            ok = False
        if last < need_latest:
            status = "INSUFFICIENT_LATE_DATA"
            ok = False
        print(f"[{status}] {pair}: file={path.name} first={first} last={last} (needed <= {earliest_needed} to >= {need_latest})")

    if not ok:
        print("\nOne or more pairs lack sufficient coverage.")
        print("Suggestions:")
        print("- Use timerange download (recommended):")
        tr = f"{earliest_needed.strftime('%Y%m%d')}-{(need_latest).strftime('%Y%m%d')}"
        adjusted_pairs = [f"{p}:USDT" if mode == "futures" and ':' not in p else p for p in pairs]
        pairs_arg = f"--pairs {' '.join(adjusted_pairs)}"
        trading_mode_arg = "--trading-mode futures" if mode == "futures" else ""
        print(f"  docker compose run --rm freqtrade download-data -c /freqtrade/user_data/config.json -t {timeframe} --timerange {tr} {pairs_arg} {trading_mode_arg}")
        print("- Or increase days to cover earliest_need from today (may be large).")
        return 2

    print("\nAll pairs have sufficient coverage for the requested backtest window and FreqAI warmup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
