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
| `MYTHOSAUR_TOOLS_SEARXNG_PORT` | No | `8063` | Host port for bundled `searxng-cache` |
| `MYTHOSAUR_TOOLS_SEARXNG_URL` | No | `http://searxng-cache:8080` | SearXNG endpoint for search tools |
| `MYTHOSAUR_TOOLS_SEARXNG_TOKEN` | No | — | Optional SearXNG auth token |
| `MYTHOSAUR_TOOLS_BROWSER_ENABLED` | No | `false` | Enable browser tools |
| `MYTHOSAUR_TOOLS_BROWSER_HEADLESS` | No | `true` | Run browser headless |
| `MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE` | No | `/data/google-credentials.json` | Google OAuth client credentials file |
| `MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE` | No | `/data/google-token.json` | Google OAuth authorized user token file |
| `MYTHOSAUR_TOOLS_RATE_LIMIT` | No | `120` | Max tool calls per 60s window (0 = disabled) |
| `LOG_LEVEL` | No | `INFO` | Python log level |

---

## Google Workspace Tools

Available tools:

- `google_calendar_events`
- `gmail_unread`
- `google_drive_recent_files`
- `google_sheets_read_range`

Expected local files for Docker compose:

- `./data/google-credentials.json`
- `./data/google-token.json`

The MCP container mounts `./data` to `/data`, and the Google tools read credentials from:

- `/data/google-credentials.json`
- `/data/google-token.json`

If the token is missing, expired, or not authorized for the requested scopes, the tool returns a structured MCP error.

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
