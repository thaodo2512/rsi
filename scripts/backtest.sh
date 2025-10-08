#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/backtest.sh [START_DATE] [END_DATE]
#   scripts/backtest.sh 2023-01-01 2023-12-31
# If omitted, defaults to the last full year.

START=${1:-2023-01-01}
END=${2:-2023-12-31}

# Freqtrade expects timerange in compact form YYYYMMDD-YYYYMMDD
START_COMPACT=${START//-/}
END_COMPACT=${END//-/}

echo "Backtesting MyFreqAIStrategy --timerange ${START_COMPACT}-${END_COMPACT}" >&2
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  --strategy MyFreqAIStrategy \
  --timerange "${START_COMPACT}-${END_COMPACT}"
