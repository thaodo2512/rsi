#!/usr/bin/env bash
set -euo pipefail

TIMEFRAME=${1:-5m}
shift || true

PAIRS=${*:-"BTC/USDT ETH/USDT"}

echo "Downloading data: timeframe=${TIMEFRAME} pairs=${PAIRS}" >&2
docker compose run --rm freqtrade download-data \
  -c /freqtrade/user_data/config.json \
  -t "${TIMEFRAME}" -p ${PAIRS}

