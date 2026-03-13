#!/usr/bin/env bash
set -euo pipefail

consumer="${1:-codex}"
mode="${2:-query}"

api_key="${MT_API_KEY:-${MYTHOSAUR_TOOLS_API_KEY:-}}"
if [[ -z "$api_key" && -f .env ]]; then
  api_key="$(
    awk -F= '
      /^MT_API_KEY=/{value=substr($0,index($0,"=")+1)}
      /^MYTHOSAUR_TOOLS_API_KEY=/{legacy=substr($0,index($0,"=")+1)}
      END { print value ? value : legacy }
    ' .env | tail -n1
  )"
fi
if [[ -z "$api_key" ]]; then
  echo "ERROR: MT_API_KEY is not set and could not be read from .env" >&2
  exit 1
fi

base_url="http://127.0.0.1:${MT_MCP_PORT:-${MYTHOSAUR_TOOLS_MCP_PORT:-8064}}"
schema_url="$base_url/schema"
mcp_url="$base_url/mcp"

schema_headers=()
mcp_headers=(
  -H "Authorization: Bearer $api_key"
  -H "Content-Type: application/json"
)

if [[ "$mode" == "query" ]]; then
  schema_url="$schema_url?consumer=$consumer"
  tools_list_payload="{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{\"consumer\":\"$consumer\"}}"
elif [[ "$mode" == "header" ]]; then
  schema_headers+=(-H "X-Mythosaur-Consumer: $consumer")
  mcp_headers+=(-H "X-Mythosaur-Consumer: $consumer")
  tools_list_payload='{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
else
  echo "ERROR: mode must be 'query' or 'header'" >&2
  exit 1
fi

schema_args=(-fsS "$schema_url")
if [[ "${#schema_headers[@]}" -gt 0 ]]; then
  schema_args=("${schema_headers[@]}" "${schema_args[@]}")
fi

mcp_args=(-fsS "${mcp_headers[@]}" -d "$tools_list_payload" "$mcp_url")

schema_json="$(curl "${schema_args[@]}")"
mcp_json="$(curl "${mcp_args[@]}")"

SCHEMA_JSON="$schema_json" MCP_JSON="$mcp_json" python3 - "$consumer" <<'PY'
import json
import os
import sys

consumer = sys.argv[1]
schema = json.loads(os.environ["SCHEMA_JSON"])
mcp = json.loads(os.environ["MCP_JSON"])

schema_plugins = {tool["plugin_id"] for tool in schema["tools"]}
mcp_plugins = {tool["annotations"]["pluginId"] for tool in mcp["result"]["tools"]}
blocked = {"mythosaur.filesystem", "mythosaur.git"}
required = {"mythosaur.search", "mythosaur.fetch", "mythosaur.google_workspace"}

print(f"consumer={consumer}")
print(f"schema_plugins={sorted(schema_plugins)}")
print(f"mcp_plugins={sorted(mcp_plugins)}")

missing = sorted(required - schema_plugins)
if missing:
    raise SystemExit(f"missing required schema plugins: {missing}")

unexpected = sorted(blocked & mcp_plugins)
if unexpected:
    raise SystemExit(f"unexpected IDE-blocked plugins present: {unexpected}")

print("consumer catalog smoke test passed")
PY
