#!/usr/bin/env python3
import pathlib
import sys
import time
import json
from typing import List

import requests


def fetch(limit: int = 2000) -> List[dict]:
    url = f"https://api.alternative.me/fng/?limit={limit}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()["data"]
    return data


def write_csv(rows: List[dict], outpath: pathlib.Path) -> None:
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open("w", encoding="utf-8") as f:
        f.write("date,value\n")
        # API returns newest-first; write oldest-first
        for row in reversed(rows):
            # row: { value: "68", timestamp: "1735516800", time_until_update: "...", value_classification: "Greed" }
            ts = int(row.get("timestamp", 0))
            if ts <= 0:
                continue
            d = time.strftime("%Y-%m-%d", time.gmtime(ts))
            val = row.get("value", "50")
            f.write(f"{d},{val}\n")


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    out = pathlib.Path("user_data/data/fear_greed.csv")
    rows = fetch(limit)
    write_csv(rows, out)
    print(f"Saved {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

