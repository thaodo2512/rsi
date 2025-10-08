#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/download.sh [TIMEFRAME] ["PAIR1 PAIR2 ..."] [DAYS]
#   scripts/download.sh 5m "BTC/USDT ETH/USDT" 420

TIMEFRAME=${1:-5m}
PAIRS=${2:-"BTC/USDT ETH/USDT"}
DAYS=${3:-400}

echo "Downloading data: timeframe=${TIMEFRAME} days=${DAYS} pairs=${PAIRS}" >&2
docker compose run --rm freqtrade download-data \
  -c /freqtrade/user_data/config.json \
  -t "${TIMEFRAME}" \
  --days "${DAYS}" \
  --pairs ${PAIRS}
