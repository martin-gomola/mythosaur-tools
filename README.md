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
| `mythosaur.google_workspace` | `google_calendar_events`, `google_calendar_create_event`, `gmail_unread`, `gmail_send`, `google_drive_recent_files`, `google_drive_create_folder`, `google_drive_create_text_file`, `google_drive_upload_file`, `google_sheets_read_range`, `google_sheets_write_range`, `google_sheets_append_rows`, `google_sheets_create_sheet`, `google_docs_get`, `google_docs_create`, `google_maps_build_route_link`, `google_maps_build_place_link`, `notebooklm_auth_status`, `notebooklm_list_notebooks`, `notebooklm_query_notebook` |
| `mythosaur.pii` | `scan_pii_staged`, `scan_pii_repo`, `install_pii_precommit_hook` |

## Security Defaults

- Workspace guard: file paths must resolve under `MYTHOSAUR_TOOLS_WORKSPACE_ROOT`
- PII guard: repo scan paths must resolve under `MYTHOSAUR_TOOLS_PII_ROOT` (defaults to the workspace root)
- Base-dir helpers reject NUL bytes and directory escape attempts
- Host mount path is configured separately via `MYTHOSAUR_TOOLS_WORKSPACE_HOST`
- When launched from `mythosaur-ai`, that repo overrides `MYTHOSAUR_TOOLS_WORKSPACE_HOST` with its `WORKSPACE_DIR`
- Profile guard:
  - `readonly` blocks mutating filesystem tools
  - `power` enables mutating filesystem tools
- Browser tools are disabled by default (`MYTHOSAUR_TOOLS_BROWSER_ENABLED=false`)
- Google Workspace tools require OAuth token and credentials files mounted from `./secrets`

## Quick Start

```bash
cp .env.example .env
# set a strong token in MYTHOSAUR_TOOLS_API_KEY
# point host workspace mount to the repo you want tools to access
# MYTHOSAUR_TOOLS_WORKSPACE_HOST=/path/to/workspace
# mount Google OAuth files into ./secrets if you want Google Workspace tools
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

This repo owns the canonical auth bootstrap because it owns the MCP runtime contract and `secrets/`.
`mythosaur-ai` can still call the same flow through a wrapper target.

Store auth material in the local `secrets/` directory:

- `secrets/google-credentials.json`
- `secrets/google-token.json`

Minimal setup:

1. Open Google Cloud Console: `https://console.cloud.google.com/`
2. Create or select a project.
3. Enable these APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Sheets API
   - Google Docs API
4. Configure the OAuth consent screen.
5. Create OAuth client credentials:
   - `APIs & Services` -> `Credentials` -> `Create Credentials` -> `OAuth client ID`
   - In `Application type`, select `Desktop app`
   - Enter a name such as `mythosaur-google`
   - Click `Create`
6. Download the JSON credentials file and save it as `secrets/google-credentials.json`.
7. From this repo, run:

```bash
make google-login
```

Important:

- Use an OAuth client JSON for a Desktop app.
- Do not use a service account key for these user-scoped Google Workspace tools.
- `make google-login` also handles NotebookLM host login when it is enabled in `.env`.
- The container mounts `./secrets` to `/secrets`.
- For standalone use with Cursor or another MCP client, set `MYTHOSAUR_TOOLS_WORKSPACE_HOST` directly in `.env`.
- From `mythosaur-ai`, `make google-login` just delegates to this repo.

Optional future Maps Platform setup for API-backed itinerary work:

- set `GOOGLE_MAPS_PLATFORM` in `.env`
- enable only the Maps Platform services you actually plan to call
- current Maps tools still only build links and do not call Maps Platform APIs yet

Env vars:

- `MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE=/secrets/google-credentials.json`
- `MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE=/secrets/google-token.json`
- `MYTHOSAUR_TOOLS_GOOGLE_*_ENABLED=true|false`
- `GOOGLE_MAPS_PLATFORM=<your-project-or-platform-id>`
- `NOTEBOOKLM_MCP_CLI_PATH=/secrets/notebooklm`
- `MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=mythosaur`

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
- `google_docs_get`
- `google_docs_create`
- `google_maps_build_route_link`
- `google_maps_build_place_link`
- `notebooklm_auth_status`
- `notebooklm_list_notebooks`
- `notebooklm_query_notebook`

## NotebookLM Setup

Default path:

```bash
cd /path/to/mythosaur-tools
make google-login
```

That is the intended operator flow. Use the dedicated guide only for troubleshooting or manual re-login:

- [docs/notebooklm.md](docs/notebooklm.md)

Runtime policy is separate from OAuth scopes. The bot account can hold broad scopes, while `MYTHOSAUR_TOOLS_GOOGLE_*_ENABLED` and `MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED` decide what the runtime is actually allowed to do.

Calendar creation uses its own runtime gate: `MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_WRITE_ENABLED`.
