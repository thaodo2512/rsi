#!/usr/bin/env bash
set -euo pipefail

SPACES=${*:-"buy sell"}

echo "Hyperopting MyFreqAIStrategy with spaces: ${SPACES}" >&2
docker compose run --rm freqtrade hyperopt \
  -c /freqtrade/user_data/config.json \
  --strategy MyFreqAIStrategy \
  --spaces ${SPACES}

