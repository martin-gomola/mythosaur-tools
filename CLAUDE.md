# CLAUDE.md

Handoff document for AI coding assistants working in or consuming `mythosaur-tools`.
Read this first. For protocol details, see `docs/integration.md`.

## What This Repo Is

`mythosaur-tools` is a shared MCP (Model Context Protocol) server that provides tool backends
consumed by multiple clients. It is **not** a chat runtime or agent framework.
It runs as a Docker stack and exposes tools over HTTP POST at `/mcp`.

### Consumers

| Consumer | How it connects | Workspace override |
|----------|----------------|-------------------|
| **mythosaur-ai** | `MT_MCP_URL` + `MT_API_KEY` in its `.env`. `make up` can auto-start this stack and inject `WORKSPACE_DIR` so both stacks share the same workspace. | `MT_WORKSPACE_HOST` overridden by mythosaur-ai's Makefile |
| **Codex / Claude Code** | Configure this repo as an MCP HTTP server and point the client at `http://127.0.0.1:8064/mcp` with Bearer auth. | Set `MT_WORKSPACE_HOST` in `.env` to the target project |
| **Cursor IDE** | `.cursor/mcp.json` with `url` + `Authorization` header pointing at `http://127.0.0.1:8064/mcp` | Set `MT_WORKSPACE_HOST` in `.env` to the project open in Cursor |
| **Any MCP client** | HTTP POST to `/mcp` with Bearer auth. See `docs/integration.md` for the JSON-RPC protocol. | Same env var |

### Boundary Rules

- **Execution logic** (tool handlers, API wrappers, CLI subprocess calls) belongs here.
- **Orchestration logic** (message loops, skills routing, chat context) belongs in the consuming repo.
- **Shared skills** (routing policies that decide *when* to call a tool) live in `skills/shared/` and are exported to consumers.
- **Consumer-specific adapter skills** live in `skills/consumers/` when a runtime needs local routing preferences that are not portable enough for `skills/shared/`.
- If a capability should work across `mythosaur-ai`, Codex, Cursor, Claude Code, and other MCP consumers, the handler belongs here.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Consumer (mythosaur-ai / Cursor / any MCP client)           │
│  ─ sends JSON-RPC to /mcp with Bearer token                  │
└──────────────┬───────────────────────────────────────────────┘
               │ HTTP POST
┌──────────────▼───────────────────────────────────────────────┐
│  mythosaur-tools container                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  FastAPI app (services/mcp_server/app.py)               │ │
│  │  ├─ /healthz     — health + plugin diagnostics          │ │
│  │  ├─ /schema      — export all tool schemas              │ │
│  │  └─ /mcp         — JSON-RPC 2.0 endpoint                │ │
│  │       ├─ initialize  → session + Mcp-Session-Id header  │ │
│  │       ├─ tools/list  → registered tools (filterable)    │ │
│  │       └─ tools/call  → invoke a tool by name            │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Plugin auto-discovery (plugins/*_tools.py)             │ │
│  │  Each module: get_tools() -> list[ToolDef]              │ │
│  │                                                         │ │
│  │  mythosaur.time        — current_time, format_date      │ │
│  │  mythosaur.git         — git_status/log/diff/branch     │ │
│  │  mythosaur.filesystem  — read/write/list/search files   │ │
│  │  mythosaur.search      — search/news/images (SearXNG)   │ │
│  │  mythosaur.fetch       — fetch/json/html/download       │ │
│  │  mythosaur.browser     — headless browser automation    │ │
│  │  mythosaur.google_workspace — Calendar, Gmail, Drive,   │ │
│  │      Sheets, Docs, Photos, Maps, NotebookLM             │ │
│  │  mythosaur.pii         — PII scanning + pre-commit hook │ │
│  └─────────────────────────────────────────────────────────┘ │
│  Mounts:                                                     │
│    WORKSPACE_HOST → /workspace  (tools operate here)         │
│    ./secrets      → /secrets    (Google OAuth, NotebookLM)   │
└──────────────────────────────────────────────────────────────┘
               │ internal DNS
┌──────────────▼────────────┐
│  searxng + searxng-cache  │
│  (bundled search backend) │
└───────────────────────────┘
```

## How mythosaur-ai Consumes This Repo

1. **Auto-start**: `make up` in mythosaur-ai checks for `../mythosaur-tools/docker-compose.yml`.
   If found and `MT_AUTOSTART=true` (default), it starts this stack with
   `MT_WORKSPACE_HOST` set to mythosaur-ai's `WORKSPACE_DIR`.

2. **Tool calls**: mythosaur-ai sends JSON-RPC `tools/call` requests to
   `MT_MCP_URL` (default: `http://mythosaur-tools:8080/mcp` or `http://127.0.0.1:8064/mcp`).

3. **Catalog refresh**: `make tools-refresh` in mythosaur-ai rebuilds this stack and
   reloads the `tools/list` catalog in the consuming runtime.

4. **Auth delegation**: `make google-login` in mythosaur-ai delegates to this repo's
   `make google-login` since this repo owns `secrets/`.

5. **Shared skills**: Skills in `skills/shared/` (e.g. `tool-intent-router`,
   `google-workspace-router`) are exported to consumer repos and decide when/how
   to invoke tools. The skills call tools; the tools live here.

## How Codex / Claude Code Consume This Repo

1. Configure `mythosaur-tools` as an MCP server using the local HTTP endpoint.
2. Point the client to `http://127.0.0.1:8064/mcp` with `Authorization: Bearer <MT_API_KEY>`.
3. Set `MT_WORKSPACE_HOST` in this repo's `.env` to the project the tools should operate on.
4. Export the shared skills plus the Codex adapter bundle with `./scripts/export-skills.sh --consumer codex`.
5. If the client cannot send a consumer hint during `tools/list`, set `MT_DEFAULT_CONSUMER=codex` for that instance.
6. Restart the stack after tool or config changes so the client sees the updated catalog.

## How Cursor Consumes This Repo

1. `.cursor/mcp.json` points at `http://127.0.0.1:8064/mcp` with a Bearer token.
2. Cursor's Agent discovers tools via the MCP protocol and uses them in chat.
3. `MT_WORKSPACE_HOST` in `.env` determines what the tools can access.
   Set it to `.` for this repo or to the project you have open in Cursor.

## How Any Other Client Can Consume This Repo

1. Start the stack: `docker compose up -d --build`
2. HTTP POST to `http://127.0.0.1:8064/mcp` with `Authorization: Bearer <token>`
3. Follow the JSON-RPC 2.0 protocol: `initialize` → `tools/list` → `tools/call`
4. Parse the tool result envelope: `{ status, tool, data, error, meta }`
5. See `docs/integration.md` for the full contract.

## Tool Result Envelope

Every tool returns this shape. Consumers should always check `status` first.

```json
{
  "status": "ok",
  "tool": "tool_name",
  "data": { ... },
  "error": null,
  "meta": { "duration_ms": 5, "source": "plugin_id" }
}
```

On error: `status: "error"`, `data: {}`, `error: { "code": "...", "message": "..." }`.

## Key Files

| Path | Purpose |
|------|---------|
| `services/mcp_server/app.py` | FastAPI app, auth, rate limiting, MCP protocol |
| `services/mcp_server/plugins/*_tools.py` | Tool implementations (auto-discovered) |
| `services/mcp_server/plugins/common.py` | Shared helpers: ToolDef, ok/err, path guards |
| `skills/shared/` | Shared skill sources exported to consumers |
| `skills/consumers/` | Consumer-specific adapter skills such as the Codex orchestrator |
| `scripts/google_oauth_bootstrap.py` | Google OAuth flow for `make google-login` |
| `docs/integration.md` | Full protocol, auth, env var reference |
| `docs/notebooklm.md` | NotebookLM setup and tool reference |
| `.env` / `.env.example` | Runtime config (gitignored / committed) |
| `.cursor/mcp.json` / `.cursor/mcp.json.example` | Cursor MCP config (gitignored / committed) |
| `docker-compose.yml` | Stack definition |

## Hard Rules

- **Current date:** For "today", "this week", or any date range, use the `current_time` MCP tool (mythosaur-tools) with the user's timezone (e.g. `Europe/Bratislava`) rather than trusting the session context "Today's date"—the latter can be wrong (e.g. off by a year).
- Do not duplicate tool execution logic in consumer repos. If the tool exists here, call it over MCP.
- Do not embed consumer-specific routing in tool handlers. Tools are consumer-agnostic.
- All file operations must go through `resolve_under_workspace` or `resolve_under_base` path guards.
- Never hardcode secrets, tokens, or credentials in source code.
- Prefer adding a new `*_tools.py` plugin over growing an existing one beyond its domain.
- Keep tool handlers synchronous where possible; use `is_async=True` only when needed.
- Every tool must return the `ok()`/`err()` envelope from `common.py`.

## Adding a New Tool

1. Create `services/mcp_server/plugins/my_tools.py`
2. Implement handlers and `get_tools() -> list[ToolDef]`
3. Server auto-discovers on startup — no registration code needed
4. Add tests in `tests/test_my_tools.py`
5. Update `README.md` tool catalog and `docs/integration.md` if needed
6. Rebuild: `docker compose up -d --build`

## Tooling

```bash
make up              # start the stack
make down            # stop the stack
make restart         # restart
make logs            # tail logs
make test            # run tests
make google-login    # Google OAuth + NotebookLM auth
```
