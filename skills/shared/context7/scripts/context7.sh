#!/bin/bash
set -euo pipefail

TOOL_NAME="${1:?Usage: context7.sh <tool-name> '<json-args>'}"
ARGS="${2:-}"
if [[ -z "$ARGS" ]]; then
  ARGS='{}'
fi
MCP_URL="${CONTEXT7_MCP_URL:-https://mcp.context7.com/mcp}"

if ! echo "$ARGS" | jq -e . >/dev/null 2>&1; then
  echo '{"error":"invalid json args"}'
  exit 1
fi

AUTH_HEADER=()
if [[ -n "${CONTEXT7_API_KEY:-}" ]]; then
  if [[ "$CONTEXT7_API_KEY" == ctx7sk* ]]; then
    AUTH_HEADER=(-H "Authorization: Bearer ${CONTEXT7_API_KEY}")
  else
    echo "context7: ignoring CONTEXT7_API_KEY (expected prefix ctx7sk...)." >&2
  fi
fi

INIT_PAYLOAD='{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"mythosaur-context7","version":"1.0.0"}}}'
TMP_HEADERS="$(mktemp)"
curl -sS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${AUTH_HEADER[@]}" \
  -D "$TMP_HEADERS" \
  -d "$INIT_PAYLOAD" >/dev/null

SESSION_ID="$(grep -i "^mcp-session-id:" "$TMP_HEADERS" | awk '{print $2}' | tr -d '\r' || true)"
rm -f "$TMP_HEADERS"

CALL_PAYLOAD="$(jq -cn --arg name "$TOOL_NAME" --argjson args "$ARGS" '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":$name,"arguments":$args}}')"

if [[ -n "$SESSION_ID" ]]; then
  RESPONSE="$(curl -sS -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $SESSION_ID" \
    "${AUTH_HEADER[@]}" \
    -d "$CALL_PAYLOAD")"
else
  RESPONSE="$(curl -sS -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    "${AUTH_HEADER[@]}" \
    -d "$CALL_PAYLOAD")"
fi

if echo "$RESPONSE" | grep -q '^data: '; then
  echo "$RESPONSE" | grep '^data: ' | tail -1 | sed 's/^data: //'
else
  echo "$RESPONSE"
fi
