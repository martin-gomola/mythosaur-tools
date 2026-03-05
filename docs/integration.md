# Integration

## Run

```bash
cp .env.example .env
# set MYTHOSAUR_TOOLS_API_KEY
# For search/news/images set MYTHOSAUR_TOOLS_SEARXNG_URL to reachable SearXNG endpoint

docker compose up -d --build
curl -s http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8080}/healthz | jq
```

## MCP Test

```bash
API_KEY="${MYTHOSAUR_TOOLS_API_KEY}"
MCP_URL="http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8080}/mcp"

curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual","version":"1.0.0"}}}'

curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"current_time","arguments":{"timezone":"Europe/Bratislava"}}}' | jq
```
