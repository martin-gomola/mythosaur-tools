# Catalog

This page keeps the long-form reference out of the front door.

## Tool Catalog

| Plugin ID | Tools |
|---|---|
| `mythosaur.time` | `current_time`, `format_date` |
| `mythosaur.git` | `git_status`, `git_log`, `git_diff`, `git_branch` |
| `mythosaur.browser` | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_select`, `browser_hover`, `browser_scroll`, `browser_press_key`, `browser_wait_for`, `browser_screenshot`, `browser_execute_script` |
| `mythosaur.fetch` | `fetch`, `fetch_json`, `fetch_html`, `download` |
| `mythosaur.search` | `search`, `search_news`, `search_images` |
| `mythosaur.filesystem` | `read_file`, `write_file`, `list_directory`, `create_directory`, `delete_file`, `move_file`, `search_files`, `get_file_info` |
| `mythosaur.google_workspace` | `google_calendar_events`, `google_calendar_create_event`, `gmail_unread`, `gmail_send`, `google_drive_recent_files`, `google_drive_create_folder`, `google_drive_create_text_file`, `google_drive_upload_file`, `google_sheets_read_range`, `google_sheets_write_range`, `google_sheets_append_rows`, `google_sheets_create_sheet`, `google_docs_get`, `google_docs_create`, `google_photos_list_albums`, `google_photos_create_album`, `google_photos_list_media_items`, `google_photos_upload_file`, `google_photos_add_to_album`, `google_photos_find_duplicate_candidates`, `google_photos_create_curated_album`, `google_maps_build_route_link`, `google_maps_build_place_link`, `google_maps_search_places`, `google_maps_compute_route`, `notebooklm_auth_status`, `notebooklm_list_notebooks`, `notebooklm_query_notebook`, `notebooklm_create_notebook`, `notebooklm_list_sources`, `notebooklm_add_source`, `notebooklm_create_studio_content`, `notebooklm_download_artifact`, `notebooklm_share` |
| `mythosaur.pii` | `scan_pii_staged`, `scan_pii_repo`, `install_pii_precommit_hook` |

## Shared Skills

Bot-agnostic skill sources live here:

- `skills/shared/context7`
- `skills/shared/agent-browser`
- `skills/shared/tool-intent-router`
- `skills/shared/pii-precommit-check`
- `skills/shared/google-workspace-router`

Skill export path used by local agent environments:

```bash
${MYTHOSAUR_TOOLS_SKILLS_DIR:-../mythosaur-tools/skills/shared}
```

Export the shared skills for Codex, Cursor, or another local agent runtime:

```bash
./scripts/export-skills.sh
./scripts/export-skills.sh /path/to/your/agent/skills
```

## Security Defaults

- Workspace paths must resolve under `MYTHOSAUR_TOOLS_WORKSPACE_ROOT`
- PII scan paths must resolve under `MYTHOSAUR_TOOLS_PII_ROOT`
- Base-dir helpers reject NUL bytes and directory escape attempts
- `MYTHOSAUR_TOOLS_WORKSPACE_HOST` controls the host path mounted into the container
- `mythosaur-ai` overrides that host path with its own `WORKSPACE_DIR` when it launches this stack
- `readonly` blocks mutating filesystem tools
- `power` enables mutating filesystem tools
- Browser tools are disabled by default with `MYTHOSAUR_TOOLS_BROWSER_ENABLED=false`
- Google Workspace tools require OAuth credentials and tokens mounted from `./secrets`
