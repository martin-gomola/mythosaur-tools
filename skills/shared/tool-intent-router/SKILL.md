---
name: tool-intent-router
description: >
  Decide the minimal MCP tool call for a user request and call only what is
  needed through mythosaur_tool_call. Use for requests that may need time/date,
  search, fetch, git, browser, or filesystem data. Skip tool calls for normal
  conversational replies.
allowed-tools: Bash(curl:*)
metadata: {"openclaw":{"always":true}}
---

# Tool Intent Router

## Goal

- Minimize tool overhead per turn.
- Select the smallest valid tool set for the request.
- Prefer one deterministic tool call before any multi-step chain.

## Routing Rules

1. Classify request:
   - `chat_only`: no external data/tool needed.
   - `time`: current time/date formatting.
   - `search`: discover public web/news/image results.
   - `fetch`: retrieve specific URL content.
   - `git`: repository state/history/diff/branch.
   - `filesystem`: workspace file/directory read operations.
   - `browser`: interactive page actions/snapshots/screenshots.
2. If `chat_only`, answer directly without tool calls.
3. If tool is needed, call exactly one MCP tool first via `mythosaur_tool_call`.
4. Call additional tools only when prior output proves it is required.
5. If request is ambiguous, ask one short clarification instead of broad tool fan-out.

## Canonical MCP Map

- `time` -> `current_time`, `format_date`
- `search` -> `search`, `search_news`, `search_images`
- `fetch` -> `fetch`, `fetch_json`, `fetch_html`, `download`
- `git` -> `git_status`, `git_log`, `git_diff`, `git_branch`
- `filesystem` -> `read_file`, `list_directory`, `search_files`, `get_file_info`
- `browser` -> `browser_navigate`, `browser_snapshot`, `browser_click`,
  `browser_type`, `browser_select`, `browser_hover`, `browser_scroll`,
  `browser_press_key`, `browser_wait_for`, `browser_screenshot`,
  `browser_execute_script`
- `google` -> see `google-workspace-router` skill for the full Google/NotebookLM tool map
- `pii` -> `scan_pii_staged`, `scan_pii_repo`, `install_pii_precommit_hook`

## Call Format

Use the generic wrapper:

```json
{"name":"mythosaur_tool_call","args":{"name":"<mcp_tool_name>","args":{...}}}
```

Examples:

```json
{"name":"mythosaur_tool_call","args":{"name":"current_time","args":{"timezone":"Europe/Bratislava"}}}
```

```json
{"name":"mythosaur_tool_call","args":{"name":"search","args":{"query":"qwen3.5 9b latency","max_results":5}}}
```

## Safety

- Respect active tool profile (`readonly` vs `power`).
- Keep filesystem/download paths under workspace root only.
- Never attempt blocked mutating filesystem tools in `readonly`.
