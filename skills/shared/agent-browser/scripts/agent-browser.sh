#!/usr/bin/env bash
set -euo pipefail

if ! command -v agent-browser >/dev/null 2>&1; then
  echo "agent-browser binary not found in PATH." >&2
  echo "Rebuild/restart OpenClaw image to install it." >&2
  exit 127
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: agent-browser.sh <agent-browser args...>" >&2
  exit 2
fi

exec agent-browser "$@"
