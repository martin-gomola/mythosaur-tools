# Integration

## Quick Start

```bash
cp .env.example .env
# set MYTHOSAUR_TOOLS_API_KEY
# Default internal search endpoint is bundled in this stack: http://searxng-cache:8080

docker compose up -d --build
curl -s http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8064}/healthz | jq
curl -s "http://127.0.0.1:${MYTHOSAUR_TOOLS_SEARXNG_PORT:-8063}/search?q=healthcheck&format=json" | jq '.results | length'
```

## MCP Test

```bash
API_KEY="${MYTHOSAUR_TOOLS_API_KEY}"
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

---

## Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | No | Health check with plugin diagnostics |
| `/schema` | GET | No | Export all tool schemas for client generation |
| `/mcp` | POST | Bearer | JSON-RPC 2.0 MCP endpoint |

---

## Authentication

All `/mcp` requests require a `Bearer` token in the `Authorization` header.

```
Authorization: Bearer <MYTHOSAUR_TOOLS_API_KEY>
```

---

## Rate Limiting

The server enforces a per-key sliding-window rate limit (default: 120 calls / 60s).
Configure via `MYTHOSAUR_TOOLS_RATE_LIMIT` env var. Set to `0` to disable.

When exceeded, the server returns HTTP 429.

---

## MCP Protocol

### `initialize`

Creates a session. Returns `Mcp-Session-Id` header for subsequent requests.

### `tools/list`

Returns all registered tools. Supports optional plugin filtering:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "plugins": "mythosaur.time,mythosaur.search"
  }
}
```

### `tools/call`

Invoke a tool by name with arguments.

---

## Tool Result Contract

Every tool handler returns a consistent JSON envelope. Consumers should rely on this shape.

### Success

```json
{
  "status": "ok",
  "tool": "current_time",
  "data": {
    "timezone": "UTC",
    "iso": "2026-03-05T12:00:00+00:00",
    "human": "2026-03-05 12:00:00 UTC"
  },
  "error": null,
  "meta": {
    "duration_ms": 2,
    "source": "time"
  }
}
```

### Error (handled)

```json
{
  "status": "error",
  "tool": "search",
  "data": {},
  "error": {
    "code": "search_failed",
    "message": "MYTHOSAUR_TOOLS_SEARXNG_URL is not configured"
  },
  "meta": {
    "duration_ms": 1,
    "source": "search"
  }
}
```

### Error (unhandled exception)

```json
{
  "status": "error",
  "tool": "fetch",
  "data": {},
  "error": {
    "code": "internal_error",
    "message": "Connection refused"
  },
  "meta": {
    "duration_ms": 150,
    "source": "mythosaur.fetch"
  }
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"ok" \| "error"` | Whether the tool call succeeded |
| `tool` | `string` | Canonical tool name (not alias) |
| `data` | `object` | Tool-specific output payload (empty `{}` on error) |
| `error` | `object \| null` | `null` on success; `{code, message}` on failure |
| `error.code` | `string` | Machine-readable error category |
| `error.message` | `string` | Human-readable error detail |
| `meta.duration_ms` | `integer` | Handler execution time in milliseconds |
| `meta.source` | `string` | Plugin source identifier |

---

## MCP Response Wrapper

Tool results are wrapped in MCP content format for the JSON-RPC response:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"status\":\"ok\", ...}"
      }
    ],
    "structuredContent": {
      "status": "ok",
      "tool": "current_time",
      "data": { "..." : "..." },
      "error": null,
      "meta": { "duration_ms": 2, "source": "time" }
    }
  }
}
```

Use `structuredContent` for typed access; `content[0].text` for pass-through.

---

## Schema Export

`GET /schema` returns all tool definitions for client-side code generation and validation:

```json
{
  "version": "0.2.0",
  "protocol_version": "2024-11-05",
  "tools": [
    {
      "name": "current_time",
      "plugin_id": "mythosaur.time",
      "description": "Return current date/time in a timezone.",
      "input_schema": { "..." : "..." },
      "aliases": ["osaurus.current_time"]
    }
  ]
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MYTHOSAUR_TOOLS_API_KEY` | Yes | — | Bearer token for MCP auth |
| `MYTHOSAUR_TOOLS_MCP_PORT` | No | `8064` | HTTP listen port |
| `MYTHOSAUR_TOOLS_PROFILE` | No | `readonly` | `readonly` or `power` (controls mutating FS tools) |
| `MYTHOSAUR_TOOLS_WORKSPACE_ROOT` | No | `/workspace` | Root for filesystem/git tools |
| `MYTHOSAUR_TOOLS_PII_ROOT` | No | `MYTHOSAUR_TOOLS_WORKSPACE_ROOT` | Base dir for PII repo scans and hook installs |
| `MYTHOSAUR_TOOLS_PII_SCRIPT_PATH` | No | `scripts/pii_scan.py` in repo root | Local CLI script used by installed pre-commit hooks |
| `MYTHOSAUR_TOOLS_SEARXNG_PORT` | No | `8063` | Host port for bundled `searxng-cache` |
| `MYTHOSAUR_TOOLS_SEARXNG_URL` | No | `http://searxng-cache:8080` | SearXNG endpoint for search tools |
| `MYTHOSAUR_TOOLS_SEARXNG_TOKEN` | No | — | Optional SearXNG auth token |
| `MYTHOSAUR_TOOLS_BROWSER_ENABLED` | No | `false` | Enable browser tools |
| `MYTHOSAUR_TOOLS_BROWSER_HEADLESS` | No | `true` | Run browser headless |
| `MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE` | No | `/secrets/google-credentials.json` | Google OAuth client credentials file |
| `MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE` | No | `/secrets/google-token.json` | Google OAuth authorized user token file |
| `MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_READ_ENABLED` | No | `true` | Allow calendar read tools |
| `MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_WRITE_ENABLED` | No | `false` | Allow calendar event creation |
| `MYTHOSAUR_TOOLS_GOOGLE_GMAIL_READ_ENABLED` | No | `true` | Allow Gmail read tools |
| `MYTHOSAUR_TOOLS_GOOGLE_GMAIL_SEND_ENABLED` | No | `false` | Allow Gmail send tool |
| `MYTHOSAUR_TOOLS_GOOGLE_DRIVE_READ_ENABLED` | No | `true` | Allow Drive read tools |
| `MYTHOSAUR_TOOLS_GOOGLE_DRIVE_WRITE_ENABLED` | No | `false` | Allow Drive write tools |
| `MYTHOSAUR_TOOLS_GOOGLE_SHEETS_READ_ENABLED` | No | `true` | Allow Sheets read tools |
| `MYTHOSAUR_TOOLS_GOOGLE_SHEETS_WRITE_ENABLED` | No | `false` | Allow Sheets write tools |
| `MYTHOSAUR_TOOLS_GOOGLE_DOCS_READ_ENABLED` | No | `true` | Allow Google Docs read tools |
| `MYTHOSAUR_TOOLS_GOOGLE_DOCS_WRITE_ENABLED` | No | `false` | Allow Google Docs create/write tools |
| `MYTHOSAUR_TOOLS_GOOGLE_PHOTOS_READ_ENABLED` | No | `false` | Allow Google Photos app-created read tools |
| `MYTHOSAUR_TOOLS_GOOGLE_PHOTOS_WRITE_ENABLED` | No | `false` | Allow Google Photos app-created write tools |
| `MYTHOSAUR_TOOLS_GOOGLE_MAPS_ENABLED` | No | `true` | Allow Google Maps tools |
| `MYTHOSAUR_TOOLS_GOOGLE_MAPS_NAVIGATE_DEFAULT` | No | `false` | Add `dir_action=navigate` by default to route links |
| `GOOGLE_MAPS_API_KEY` | No | — | Google Maps API key used by Places and Routes API tools |
| `GOOGLE_MAPS_PLATFORM` | No | — | Optional Google Maps Platform project identifier for future metadata or routing policy use |
| `MYTHOSAUR_TOOLS_NOTEBOOKLM_BIN` | No | `nlm` | NotebookLM CLI binary used by the wrapper tools |
| `MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED` | No | `true` | Allow NotebookLM tools at runtime |
| `MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE` | No | `mythosaur` | NotebookLM auth profile to use inside the container |
| `MYTHOSAUR_TOOLS_NOTEBOOKLM_TIMEOUT` | No | `120` | Default NotebookLM query timeout in seconds |
| `NOTEBOOKLM_MCP_CLI_PATH` | No | `/secrets/notebooklm` | Shared NotebookLM CLI state directory mounted into the container |
| `MYTHOSAUR_TOOLS_RATE_LIMIT` | No | `120` | Max tool calls per 60s window (0 = disabled) |
| `LOG_LEVEL` | No | `INFO` | Python log level |

---

## Google Workspace Tools

Canonical auth bootstrap lives in `mythosaur-tools` because this repo owns the MCP runtime contract and `secrets/`.
`mythosaur-ai` can call the same flow through a wrapper target.

Available tools:

- `google_calendar_events`
- `google_calendar_create_event`
- `gmail_unread`
- `gmail_send`
- `google_drive_recent_files`
- `google_drive_create_folder`
- `google_drive_create_text_file`
- `google_drive_upload_file`
- `google_sheets_read_range`
- `google_sheets_write_range`
- `google_sheets_append_rows`
- `google_sheets_create_sheet`
- `google_docs_get`
- `google_docs_create`
- `google_photos_list_albums`
- `google_photos_create_album`
- `google_photos_list_media_items`
- `google_photos_upload_file`
- `google_photos_add_to_album`
- `google_photos_find_duplicate_candidates`
- `google_photos_create_curated_album`
- `google_maps_build_route_link`
- `google_maps_build_place_link`
- `google_maps_search_places`
- `google_maps_compute_route`
- `notebooklm_auth_status`
- `notebooklm_list_notebooks`
- `notebooklm_query_notebook`
- `notebooklm_create_notebook`
- `notebooklm_list_sources`
- `notebooklm_add_source`
- `notebooklm_create_studio_content`
- `notebooklm_download_artifact`
- `notebooklm_share`

NotebookLM operator guide:

- `docs/notebooklm.md`

Expected local files for Docker compose:

- `./secrets/google-credentials.json`
- `./secrets/google-token.json`

Minimal operator flow:

1. Open Google Cloud Console: `https://console.cloud.google.com/`
2. Create or select a project.
3. Enable these APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Sheets API
   - Google Docs API
   - Google Photos Library API
   - Places API
   - Routes API
4. Configure the OAuth consent screen.
5. Create OAuth client credentials:
   - `APIs & Services` -> `Credentials` -> `Create Credentials` -> `OAuth client ID`
   - In `Application type`, select `Desktop app`
   - Enter a name such as `mythosaur-google`
   - Click `Create`
6. Download the JSON credentials file and save it as `./secrets/google-credentials.json`.
7. From this repo, run:

```bash
make google-login
```

Important:

- Use a Desktop app OAuth client JSON.
- Do not use a service account key for these Google Workspace user tools.
- `make google-login` also handles NotebookLM host login when it is enabled in `.env`.

The MCP container mounts `./secrets` to `/secrets`, and the Google tools read credentials from:

- `/secrets/google-credentials.json`
- `/secrets/google-token.json`

If the token is missing, expired, or not authorized for the requested scopes, the tool returns a structured MCP error.

For standalone use with Cursor or another MCP client, set `MYTHOSAUR_TOOLS_WORKSPACE_HOST` directly in `.env`. When launched by `mythosaur-ai`, that repo overrides the value with its `WORKSPACE_DIR`.
From `mythosaur-ai`, `make google-login` just delegates to this repo.

Write-capable tools such as `google_calendar_create_event`, `gmail_send`, `google_drive_upload_file`, and the Sheets write helpers need broader Google scopes than the read-only tools. If those calls fail after deployment, refresh `./secrets/google-token.json` with the required scopes.

Runtime capability flags are a second control layer above OAuth. Use them to disable actions even when the bot account has the underlying scope. This is the intended backend contract for a future Mythosaur settings UI.

Current Google Photos limitation:

- the MCP tools only operate on app-created Google Photos albums and media items
- duplicate detection is heuristic over those app-created items
- broad read access to a user’s entire personal Google Photos library is not implemented here

Optional future Maps Platform setup for API-backed itinerary work:

- set `GOOGLE_MAPS_API_KEY` in `.env` for Places and Routes API-backed tools
- set `GOOGLE_MAPS_PLATFORM` in `.env`
- enable only the Maps Platform services you actually plan to call
- link-builder tools work without the key
- `google_maps_search_places` and `google_maps_compute_route` require the key

---

## PII Tools

Available tools:

- `scan_pii_staged`
- `scan_pii_repo`
- `install_pii_precommit_hook`

Recommended usage pattern:

1. call `scan_pii_staged` before commit
2. block commit progress if findings exist
3. call `scan_pii_repo` for wider audits
4. call `install_pii_precommit_hook` when the user wants local automation

Design note:

- the shared MCP tools own scanning and hook installation
- a thin client skill should only decide when to trigger, which tool to call, and how to react to findings

---

## Plugin System

Tools are auto-discovered from `plugins/*_tools.py` modules. Each module must expose:

```python
def get_tools() -> list[ToolDef]:
    ...
```

Adding a new plugin requires only creating a new `*_tools.py` file — no registration code changes needed.

Path safety helpers in `plugins/common.py` support both workspace-root and arbitrary base-dir constrained resolution. Use those helpers instead of building file paths manually.

### Async Support

Plugins can provide async handlers by setting `is_async=True` on the `ToolDef`. Sync handlers
are automatically offloaded to a thread pool via `asyncio.to_thread`.

---

## Consumer Integration Patterns

### mythosaur-ai

mythosaur-ai is the primary consumer. Its Makefile auto-starts this stack on `make up`:

1. Checks for `../mythosaur-tools/docker-compose.yml`
2. If `MYTHOSAUR_TOOLS_AUTOSTART=true` (default), starts this stack
3. Injects its own `WORKSPACE_DIR` as `MYTHOSAUR_TOOLS_WORKSPACE_HOST` so tools operate on the same workspace
4. Nanobot sends `tools/call` requests to `MYTHOSAUR_TOOLS_MCP_URL`

After changing tools, run `make tools-refresh` from mythosaur-ai to rebuild this stack and restart Nanobot.

Auth flows (Google OAuth, NotebookLM login) run from this repo because it owns `secrets/`.
mythosaur-ai's `make google-login` delegates here.

### Cursor IDE

Cursor connects via `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mythosaur-tools": {
      "url": "http://127.0.0.1:8064/mcp",
      "headers": {
        "Authorization": "Bearer <MYTHOSAUR_TOOLS_API_KEY>"
      }
    }
  }
}
```

Set `MYTHOSAUR_TOOLS_WORKSPACE_HOST` in `.env` to the project Cursor should operate on.
Restart the stack and Cursor after changes.

### Any MCP Client

Any tool that speaks MCP over HTTP can connect:

1. Start the stack: `docker compose up -d --build`
2. `POST /mcp` with `Authorization: Bearer <token>` and `Content-Type: application/json`
3. Send `initialize`, then `tools/list` to discover tools, then `tools/call` to invoke
4. Parse the tool result envelope (`status`, `data`, `error`, `meta`)

The `/schema` endpoint exports all tool definitions without auth for client code generation.

### Shared Skills

Skills in `skills/shared/` are the routing layer that consumers embed. They decide *when* to call
a tool and *how* to interpret the result. The tool handlers here are the execution layer.

Export skills to a consumer:

```bash
./scripts/export-skills.sh /path/to/consumer/skills
```

---

## Session Notes

Sessions are stored in-memory. They do not survive server restarts and are not shared
across horizontal instances. This is acceptable for current single-instance deployments.
For multi-instance scaling, consider an external session store (Redis).

---

## Adding a New Tool Plugin

1. Create `services/mcp_server/plugins/my_tools.py`
2. Define handlers and `get_tools() -> list[ToolDef]`
3. The server auto-discovers it on next startup
4. Add tests in `tests/test_my_tools.py`

```python
from .common import ToolDef, err, now_ms, ok

def _my_handler(args: dict) -> dict:
    started = now_ms()
    # ... tool logic ...
    return ok("my_tool", {"result": "value"}, "my_plugin", started)

def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="my_tool",
            plugin_id="mythosaur.my_plugin",
            description="Does something useful.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
            },
            handler=_my_handler,
            aliases=["osaurus.my_tool"],
        ),
    ]
```
