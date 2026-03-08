# NotebookLM Setup

This guide connects NotebookLM to `mythosaur-tools` using the dedicated Mythosaur Google account.

## What This Uses

- Host login flow: `nlm`
- Shared auth storage: `./secrets/notebooklm`
- Container path: `/secrets/notebooklm`
- MCP tools:
  - `notebooklm_auth_status`
  - `notebooklm_list_notebooks`
  - `notebooklm_query_notebook`

## One-Time Setup

Default path:

```bash
cd /path/to/mythosaur-tools
make google-login
```

That is the intended operator flow. It handles the Google OAuth bootstrap first and then runs the NotebookLM host login when NotebookLM is enabled in `.env`.

Manual NotebookLM-only path, only if you need to re-login or debug:

1. Log in on the Mac host with the Mythosaur Google account:

```bash
cd /path/to/mythosaur-tools
NOTEBOOKLM_MCP_CLI_PATH="$PWD/secrets/notebooklm" uv tool run --from notebooklm-mcp-cli nlm login --profile mythosaur
```

2. Confirm the login still works:

```bash
NOTEBOOKLM_MCP_CLI_PATH="$PWD/secrets/notebooklm" uv tool run --from notebooklm-mcp-cli nlm login --check --profile mythosaur
```

3. Make sure `.env` contains these values:

```bash
MYTHOSAUR_TOOLS_NOTEBOOKLM_BIN=nlm
MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=mythosaur
MYTHOSAUR_TOOLS_NOTEBOOKLM_TIMEOUT=120
NOTEBOOKLM_MCP_CLI_PATH=/secrets/notebooklm
```

4. Rebuild the service:

```bash
docker compose up -d --build
```

## Verify The MCP Tools

List the NotebookLM tools exposed by the MCP server:

```bash
curl -s http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8064}/schema | jq '.tools[] | select(.name | startswith("notebooklm_"))'
```

Check auth from the MCP side:

```bash
API_KEY="$(awk -F= '/^MYTHOSAUR_TOOLS_API_KEY=/{print substr($0,index($0,"=")+1)}' .env | tail -n1)"
MCP_URL="http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8064}/mcp"

curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"notebooklm_auth_status","arguments":{"profile":"mythosaur"}}}' | jq
```

List available notebooks:

```bash
curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"notebooklm_list_notebooks","arguments":{"profile":"mythosaur","max_results":10}}}' | jq
```

Query a notebook:

Replace `NOTEBOOK_ID` with a real notebook ID from the previous command.

```bash
curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"notebooklm_query_notebook","arguments":{"profile":"mythosaur","notebook_id":"NOTEBOOK_ID","question":"What are the three key takeaways?"}}}' | jq
```

## Files Used

- Host auth state: `secrets/notebooklm/`
- Container auth state: `/secrets/notebooklm`
- Plugin code: `services/mcp_server/plugins/notebooklm_tools.py`

## Troubleshooting

If auth fails:

```bash
NOTEBOOKLM_MCP_CLI_PATH="$PWD/secrets/notebooklm" uv tool run --from notebooklm-mcp-cli nlm login --profile mythosaur --force
```

If the MCP server does not show the NotebookLM tools:

```bash
docker compose up -d --build
docker compose logs mythosaur-tools
```

If the login works on the host but not in Docker, verify:

- `NOTEBOOKLM_MCP_CLI_PATH=/secrets/notebooklm` is set in `.env`
- `MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=mythosaur` is set in `.env`
- `./secrets` is mounted into the container
