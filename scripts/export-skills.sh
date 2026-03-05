#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${MYTHOSAUR_SHARED_SKILLS_DIR:-$ROOT_DIR/skills/shared}"
DEST_DIR="${1:-${MYTHOSAUR_SKILLS_EXPORT_DIR:-$HOME/.codex/skills/mythosaur}}"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "ERROR: shared skills source not found: $SRC_DIR" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
find "$DEST_DIR" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
cp -R "$SRC_DIR"/. "$DEST_DIR"/
find "$DEST_DIR" -type f -name '*.sh' -exec chmod +x {} +

count="$(find "$DEST_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
echo "Exported $count skill(s) from $SRC_DIR to $DEST_DIR"
