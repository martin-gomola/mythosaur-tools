---
name: codex-mythosaur-orchestrator
description: >
  Adapter skill for using mythosaur shared workflows from Codex. Prefer native
  Codex tools for local code, shell, filesystem, and git work. Use
  mythosaur-tools MCP for remote execution such as search, fetch, browser,
  Google Workspace, NotebookLM, transcript extraction, and PII workflows.
---

# Codex Mythosaur Orchestrator

## Purpose

Use this skill when Codex is connected to `mythosaur-tools` and should follow Mythosaur
workflows without pretending to be the `mythosaur-ai` runtime.

This skill is an adapter:

- shared workflow knowledge still lives in `skills/shared/`
- product-specific orchestration still belongs in `mythosaur-ai`
- `mythosaur-tools` remains the shared execution backend

## Load With

Use the smallest additional shared skill set needed for the task:

- `tool-intent-router` for broad routing
- `google-workspace-router` for Google Workspace or NotebookLM tasks
- `pii-precommit-check` for staged-file or repo scanning
- `agent-browser` when browser automation is required
- `shadcn-ui` when frontend work explicitly targets shadcn/ui
- `shadcn-mcp` when frontend work needs real shadcn component execution
- `ui-ux-pro-max` when frontend work needs broader UI/UX direction or review

## Routing Contract

Prefer native Codex capabilities for:

- local filesystem reads and writes
- shell commands and test execution
- local git inspection and local git operations
- code edits and patch generation
- repository-local analysis

Prefer `mythosaur-tools` MCP for:

- public web search or news/image discovery
- remote page fetch or HTML extraction
- browser automation and screenshots
- transcript extraction
- Google Calendar, Gmail, Drive, Sheets, Docs, Photos, Maps, and NotebookLM access
- shared PII scanning workflows exposed by the MCP server

## Google Tool Map

Use `google-workspace-router` for the detailed routing rules. The main MCP families available here are:

- Calendar: `google_calendar_events`, `google_calendar_create_event`
- Gmail: `gmail_unread`, `gmail_send`
- Drive: `google_drive_recent_files`, `google_drive_create_folder`, `google_drive_create_text_file`, `google_drive_upload_file`
- Sheets: `google_sheets_read_range`, `google_sheets_write_range`, `google_sheets_append_rows`, `google_sheets_create_sheet`
- Docs: `google_docs_get`, `google_docs_create`
- Photos: `google_photos_list_albums`, `google_photos_create_album`, `google_photos_list_media_items`, `google_photos_upload_file`, `google_photos_add_to_album`, `google_photos_find_duplicate_candidates`, `google_photos_create_curated_album`
- Maps: `google_maps_build_route_link`, `google_maps_build_place_link`, `google_maps_search_places`, `google_maps_compute_route`
- NotebookLM: `notebooklm_auth_status`, `notebooklm_list_notebooks`, `notebooklm_query_notebook`, `notebooklm_create_notebook`, `notebooklm_list_sources`, `notebooklm_add_source`, `notebooklm_create_studio_content`, `notebooklm_download_artifact`, `notebooklm_share`

## Standalone Rule

If `mythosaur-tools` is unavailable, still produce useful output:

- draft the message, report, or response
- provide a copy-paste-ready command or plan
- explain what remote step could not be executed

Do not fail a workflow just because the execution layer is unavailable.

## Guardrails

- Do not emulate `mythosaur-ai` private state or runtime internals.
- Do not move product-specific orchestration into this skill.
- Do not route local filesystem or git work through MCP unless there is a specific reason.
- Prefer one direct tool call over broad MCP fan-out.
- Keep the shared skill boundary clean: adapt, do not duplicate.
