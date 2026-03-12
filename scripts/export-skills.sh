#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${MYTHOSAUR_SHARED_SKILLS_DIR:-$ROOT_DIR/skills/shared}"
CONSUMERS_DIR="${MYTHOSAUR_CONSUMER_SKILLS_DIR:-$ROOT_DIR/skills/consumers}"
DEST_DIR=""
CONSUMER=""
DEST_SET=0
OVERWRITTEN_SKILLS=()
COPIED_SKILLS=()
MANIFEST_PATH=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/export-skills.sh [DEST_DIR]
  ./scripts/export-skills.sh --consumer codex [DEST_DIR]
  ./scripts/export-skills.sh --consumer cursor [DEST_DIR]

Exports shared skills by default. When --consumer is set, exports shared skills
plus the matching consumer-specific bundle into the same destination.

Default destination by consumer:
  codex   → ~/.codex/skills/mythosaur
  cursor  → ~/.cursor/skills/mythosaur

Override with MYTHOSAUR_SKILLS_EXPORT_DIR or a positional DEST_DIR.

If the destination is nested under a skills registry root (e.g. ~/.codex/skills
or ~/.cursor/skills), any skill that already exists as a sibling in the
registry is replaced there and not duplicated under the bundle directory.
EOF
}

duplicate_registry_target() {
  local skill_name="$1"
  local parent_dir
  parent_dir="$(dirname "$DEST_DIR")"

  if [[ "$(basename "$parent_dir")" != "skills" ]]; then
    return 1
  fi

  if [[ -d "$parent_dir/$skill_name" && "$parent_dir/$skill_name" != "$DEST_DIR/$skill_name" ]]; then
    printf '%s\n' "$parent_dir/$skill_name"
    return 0
  fi

  return 1
}

copy_skill_dirs() {
  local source_dir="$1"
  local skill_dir
  for skill_dir in "$source_dir"/*; do
    [[ -d "$skill_dir" ]] || continue
    local skill_name
    local target_path
    skill_name="$(basename "$skill_dir")"
    if target_path="$(duplicate_registry_target "$skill_name")"; then
      rm -rf "$target_path"
      cp -R "$skill_dir" "$target_path"
      OVERWRITTEN_SKILLS+=("$skill_name")
    else
      target_path="$DEST_DIR/$skill_name"
      cp -R "$skill_dir" "$DEST_DIR"/
    fi
    find "$target_path" -type f -name '*.sh' -exec chmod +x {} +
    COPIED_SKILLS+=("$skill_name")
  done
}

write_manifest() {
  MANIFEST_PATH="$DEST_DIR/.export-manifest.json"

  COPIED_JOINED="$(printf '%s\n' "${COPIED_SKILLS[@]-}" | sed '/^$/d')"
  OVERWRITTEN_JOINED="$(printf '%s\n' "${OVERWRITTEN_SKILLS[@]-}" | sed '/^$/d')"
  export MANIFEST_PATH DEST_DIR SRC_DIR CONSUMERS_DIR CONSUMER COPIED_JOINED OVERWRITTEN_JOINED

  python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

def lines(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [line for line in raw.splitlines() if line]

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "destination": os.environ["DEST_DIR"],
    "shared_source": os.environ["SRC_DIR"],
    "consumer": os.environ.get("CONSUMER") or None,
    "consumer_source": (
        os.path.join(os.environ["CONSUMERS_DIR"], os.environ["CONSUMER"])
        if os.environ.get("CONSUMER")
        else None
    ),
    "copied_skills": sorted(lines("COPIED_JOINED")),
    "overwritten_sibling_skills": sorted(lines("OVERWRITTEN_JOINED")),
}

with open(os.environ["MANIFEST_PATH"], "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --consumer)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --consumer requires a value" >&2
        exit 1
      fi
      CONSUMER="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ "$DEST_SET" -eq 1 ]]; then
        echo "ERROR: destination provided more than once: $1" >&2
        exit 1
      fi
      DEST_DIR="$1"
      DEST_SET=1
      ;;
  esac
  shift
done

# Default destination by consumer when not set explicitly
if [[ "$DEST_SET" -eq 0 ]]; then
  if [[ -n "${MYTHOSAUR_SKILLS_EXPORT_DIR:-}" ]]; then
    DEST_DIR="$MYTHOSAUR_SKILLS_EXPORT_DIR"
  elif [[ "$CONSUMER" == "cursor" ]]; then
    DEST_DIR="$HOME/.cursor/skills/mythosaur"
  else
    DEST_DIR="$HOME/.codex/skills/mythosaur"
  fi
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "ERROR: shared skills source not found: $SRC_DIR" >&2
  exit 1
fi

if [[ -n "$CONSUMER" && ! -d "$CONSUMERS_DIR/$CONSUMER" ]]; then
  echo "ERROR: consumer skills source not found: $CONSUMERS_DIR/$CONSUMER" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
find "$DEST_DIR" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
copy_skill_dirs "$SRC_DIR"

if [[ -n "$CONSUMER" ]]; then
  copy_skill_dirs "$CONSUMERS_DIR/$CONSUMER"
fi

write_manifest

count="$(find "$DEST_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
if [[ -n "$CONSUMER" ]]; then
  echo "Exported $count skill(s) from $SRC_DIR and $CONSUMERS_DIR/$CONSUMER to $DEST_DIR"
else
  echo "Exported $count skill(s) from $SRC_DIR to $DEST_DIR"
fi

if [[ "${#OVERWRITTEN_SKILLS[@]}" -gt 0 ]]; then
  printf 'Overwrote sibling skill(s) in parent registry: %s\n' "$(printf '%s ' "${OVERWRITTEN_SKILLS[@]}" | sed 's/ $//')"
fi

echo "Wrote export manifest to $MANIFEST_PATH"
