#!/usr/bin/env bash
set -euo pipefail

# Ensure bind-mounted user_data is writable by the container user (ftuser:ftuser -> 1000:1000).
# Usage: scripts/fix_perms.sh [path]

TARGET=${1:-user_data}

if [[ ! -d "$TARGET" ]]; then
  echo "Error: Directory '$TARGET' not found" >&2
  exit 1
fi

echo "Fixing ownership to 1000:1000 for '$TARGET' ..."
sudo chown -R 1000:1000 "$TARGET"
echo "Applying u+rwX,g+rwX permissions ..."
chmod -R u+rwX,g+rwX "$TARGET"
echo "Done."

