# mythosaur-tools

Shared MCP tool services and shared skill sources for Mythosaur bots and UIs.

This repository keeps tool backends and managed skill sources separate from `mythosaur-ai`, so orchestration/chat runtime and shared capabilities can evolve independently.

## What This Provides

- MCP HTTP endpoint: `/mcp`
- Health endpoint: `/healthz`
- Bundled SearXNG + micro-cache (`searxng`, `searxng-cache`) for search tools
- Static bearer auth via `Authorization: Bearer <MYTHOSAUR_TOOLS_API_KEY>`
- Plugin catalog (canonical namespace: `mythosaur.*`, with `osaurus.*` aliases)
- Central source for shared agent skills (`skills/shared/*`)

## Skills (Bot-Agnostic Source)

Shared skill source-of-truth lives here:

- `skills/shared/context7`
- `skills/shared/agent-browser`
- `skills/shared/tool-intent-router`
- `skills/shared/pii-precommit-check`
- `skills/shared/google-workspace-router`

Skill export path used by local agent environments:

```bash
${MYTHOSAUR_TOOLS_SKILLS_DIR:-../mythosaur-tools/skills/shared}
```

Export same shared skills for local IDE/dev agent stacks (Codex, Cursor, other runtimes):

```bash
# default export target: ~/.codex/skills/mythosaur
./scripts/export-skills.sh

# or export to a custom location
./scripts/export-skills.sh /path/to/your/agent/skills
```

## Tool Catalog

| Plugin ID | Tools |
|---|---|
| `mythosaur.time` | `current_time`, `format_date` |
| `mythosaur.git` | `git_status`, `git_log`, `git_diff`, `git_branch` |
| `mythosaur.browser` | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_select`, `browser_hover`, `browser_scroll`, `browser_press_key`, `browser_wait_for`, `browser_screenshot`, `browser_execute_script` |
| `mythosaur.fetch` | `fetch`, `fetch_json`, `fetch_html`, `download` |
| `mythosaur.search` | `search`, `search_news`, `search_images` |
| `mythosaur.filesystem` | `read_file`, `write_file`, `list_directory`, `create_directory`, `delete_file`, `move_file`, `search_files`, `get_file_info` |
| `mythosaur.google_workspace` | `google_calendar_events`, `google_calendar_create_event`, `gmail_unread`, `gmail_send`, `google_drive_recent_files`, `google_drive_create_folder`, `google_drive_create_text_file`, `google_drive_upload_file`, `google_sheets_read_range`, `google_sheets_write_range`, `google_sheets_append_rows`, `google_sheets_create_sheet`, `google_maps_build_route_link`, `google_maps_build_place_link`, `notebooklm_auth_status`, `notebooklm_list_notebooks`, `notebooklm_query_notebook` |
| `mythosaur.pii` | `scan_pii_staged`, `scan_pii_repo`, `install_pii_precommit_hook` |

## Security Defaults

- Workspace guard: file paths must resolve under `MYTHOSAUR_TOOLS_WORKSPACE_ROOT`
- PII guard: repo scan paths must resolve under `MYTHOSAUR_TOOLS_PII_ROOT` (defaults to the workspace root)
- Base-dir helpers reject NUL bytes and directory escape attempts
- Host mount path is configured separately via `MYTHOSAUR_TOOLS_WORKSPACE_HOST`
- Profile guard:
  - `readonly` blocks mutating filesystem tools
  - `power` enables mutating filesystem tools
- Browser tools are disabled by default (`MYTHOSAUR_TOOLS_BROWSER_ENABLED=false`)
- Google Workspace tools require OAuth token and credentials files mounted into `./data`

## Quick Start

```bash
cp .env.example .env
# set a strong token in MYTHOSAUR_TOOLS_API_KEY
# point host workspace mount to the repo you want tools to access
# MYTHOSAUR_TOOLS_WORKSPACE_HOST=../mythosaur-ai
# mount Google OAuth files into ./data if you want Google Workspace tools
# Default port sequence:
# 8063 = mythosaur-tools searxng-cache
# 8064 = mythosaur-tools MCP
# 8065 = Mattermost

docker compose up -d --build
curl -s http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8064}/healthz | jq
```

## MCP Smoke Test

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

## Integration Contract with mythosaur-ai

- `mythosaur-ai` consumes these tools via `MYTHOSAUR_TOOLS_MCP_URL` and `MYTHOSAUR_TOOLS_API_KEY`
- Grogu uses explicit command-driven tool calls (non-agentic)
- Nanoclaw can call the same MCP backend for Grogu and Mythosaur roles
- Shared clients can export `pii-precommit-check` from `skills/shared/` and reuse the same PII MCP tools instead of duplicating scan logic in prompts

## Google Workspace Setup

Provide OAuth files in the local `data/` directory used by Docker compose:

- `data/google-credentials.json`
- `data/google-token.json`

Env vars:

- `MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE=/data/google-credentials.json`
- `MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE=/data/google-token.json`
- `MYTHOSAUR_TOOLS_GOOGLE_*_ENABLED=true|false`
- `NOTEBOOKLM_MCP_CLI_PATH=/data/notebooklm`
- `MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=default`

Current Google MCP tools:

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
- `google_maps_build_route_link`
- `google_maps_build_place_link`
- `notebooklm_auth_status`
- `notebooklm_list_notebooks`
- `notebooklm_query_notebook`

## NotebookLM Setup

Use the dedicated guide: [docs/notebooklm.md](docs/notebooklm.md)

Short version:

```bash
cd /path/to/mythosaur-tools
NOTEBOOKLM_MCP_CLI_PATH="$PWD/data/notebooklm" uv tool run --from notebooklm-mcp-cli nlm login --profile mythosaur
docker compose up -d --build
```

For the broader Google write scopes used by Gmail send, Drive upload, and Sheets writes, you may need to refresh the mounted Google token if the existing token was authorized as read-only.

Runtime policy is separate from OAuth scopes. The bot account can hold broad scopes, while `MYTHOSAUR_TOOLS_GOOGLE_*_ENABLED` and `MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED` decide what the runtime is actually allowed to do.

Calendar creation uses its own runtime gate: `MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_WRITE_ENABLED`.
