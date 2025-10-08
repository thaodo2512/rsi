#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/clean.sh [options]

Cleans generated artifacts (logs, DBs, results, caches).
By default, preserves downloaded market data under user_data/data/.

Options:
  --all        Also remove downloaded data (keeps *.example.csv)
  --docker     Stop containers and remove anonymous volumes (docker compose down -v)
  --yes        Do not prompt for confirmation
  --dry-run    Show actions without executing

Examples:
  scripts/clean.sh --docker
  scripts/clean.sh --all --yes
  scripts/clean.sh --dry-run
USAGE
}

ALL=false
DOCKER=false
YES=false
DRYRUN=false

for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0 ;;
    --all) ALL=true ;;
    --docker) DOCKER=true ;;
    --yes) YES=true ;;
    --dry-run) DRYRUN=true ;;
    *) echo "Unknown option: $arg" >&2; usage; exit 1 ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

[[ -f docker-compose.yml && -d user_data ]] || {
  echo "Error: Run from repository with docker-compose.yml and user_data/ present: $repo_root" >&2
  exit 1
}

echo "Repo root: $repo_root"
echo "Options: ALL=$ALL DOCKER=$DOCKER YES=$YES DRYRUN=$DRYRUN"

confirm() {
  $YES && return 0
  read -r -p "Proceed with cleanup? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

run() {
  if $DRYRUN; then
    echo "+ $*"
  else
    eval "$@"
  fi
}

confirm || { echo "Aborted."; exit 1; }

if $DOCKER; then
  run docker compose down -v --remove-orphans || true
fi

# Core cleanup
run rm -rf user_data/logs user_data/backtest_results user_data/hyperopt_results
run rm -f user_data/trades*.sqlite user_data/*.log
run rm -rf user_data/freqaimodels user_data/freqai* user_data/models user_data/.cache || true

# Python caches
run find . -type d -name __pycache__ -prune -exec rm -rf {} +
run rm -rf .pytest_cache .mypy_cache || true
run find . -type f -name '*.pyc' -delete

# Optional: remove downloaded data but keep example CSVs
if $ALL; then
  if [[ -d user_data/data ]]; then
    shopt -s nullglob
    shopt -s extglob
    run bash -lc "rm -rf user_data/data/!(*.example.csv)"
  fi
fi

echo "Cleanup complete."

