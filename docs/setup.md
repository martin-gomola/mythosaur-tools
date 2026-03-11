# Setup

Use this guide when you want to bring up `mythosaur-tools`, connect a local client, and verify the forge is alive.

## Local Bring-Up

```bash
cp .env.example .env
```

Set at least:

- `MYTHOSAUR_TOOLS_API_KEY` to a strong local token
- `MYTHOSAUR_TOOLS_WORKSPACE_HOST` to the repo or workspace you want the tools to see

Then start the stack:

```bash
docker compose up -d --build
curl -s http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8064}/healthz | jq
```

Default host ports:

- `8063` for `searxng-cache`
- `8064` for the MCP server

## Connect to Cursor

1. Start the MCP server.

```bash
docker compose up -d --build
```

2. Copy the local MCP config template.

```bash
cp .cursor/mcp.json.example .cursor/mcp.json
```

3. Edit `.cursor/mcp.json` and replace `replace-with-strong-token` in the `Authorization` header with the same value as `MYTHOSAUR_TOOLS_API_KEY` in `.env`.

4. Restart Cursor and open `Settings -> Tools & MCP`.

You should see `mythosaur-tools`. Enable it if needed.

If you run the MCP server on a different port, update the `url` in `.cursor/mcp.json`.

For standalone Cursor use, set `MYTHOSAUR_TOOLS_WORKSPACE_HOST` to `.` for this repo or to the path of the project you actually have open in Cursor. Restart the stack after changing it.

## Export Skills for Codex

Export the shared skills plus the Codex adapter bundle:

```bash
./scripts/export-skills.sh --consumer codex
make codex-install
```

That bundle installs:

- the portable workflows from `skills/shared/`
- the Codex adapter from `skills/consumers/codex/`

The Codex adapter is expected to prefer native Codex tools for local filesystem, shell,
git, and code editing work, while using `mythosaur-tools` MCP for remote execution such as
search, fetch, browser, transcript, PII, and Google-family tools:

- Calendar and Gmail
- Drive, Sheets, and Docs
- Photos and Maps
- NotebookLM

If the client cannot send a consumer hint during `tools/list`, run a dedicated IDE-facing
instance with:

```bash
MYTHOSAUR_TOOLS_DEFAULT_CONSUMER=codex docker compose up -d --build
```

Verify the filtered catalog with:

```bash
./scripts/smoke_consumer_catalog.sh codex query
./scripts/smoke_consumer_catalog.sh codex header
make codex-smoke
```

The export writes a manifest to `~/.codex/skills/mythosaur/.export-manifest.json` so you can verify:

- which skills were copied into the Mythosaur bundle
- which sibling top-level Codex skills were overwritten with newer Mythosaur versions

## Smoke Test

```bash
API_KEY="$(awk -F= '/^MYTHOSAUR_TOOLS_API_KEY=/{print substr($0,index($0,"=")+1)}' .env | tail -n1)"
MCP_URL="http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8064}/mcp"

curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual","version":"1.0.0"}}}'

curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"current_time","arguments":{"timezone":"Europe/Bratislava"}}}' | jq
```

If you also want to verify bundled search:

```bash
curl -s "http://127.0.0.1:${MYTHOSAUR_TOOLS_SEARXNG_PORT:-8063}/search?q=healthcheck&format=json" | jq '.results | length'
```
