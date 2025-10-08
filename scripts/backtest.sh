#!/usr/bin/env bash
set -euo pipefail

START=${1:-2023-01-01}
END=${2:-2023-12-31}

echo "Backtesting MyFreqAIStrategy from ${START} to ${END}" >&2
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/config.json \
  --strategy MyFreqAIStrategy \
  -s "${START}" -e "${END}"

