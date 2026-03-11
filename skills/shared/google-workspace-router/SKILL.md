---
name: google-workspace-router
description: >
  Route requests about Google Calendar, Gmail, Google Drive, Google Sheets,
  Google Docs, Google Photos, Google Maps, and NotebookLM to the current
  mythosaur-tools MCP tools. Use when the user asks about meetings, schedule,
  unread mail, sending email, Drive files, spreadsheet ranges, documents,
  photo albums, map routes, places, notes, research notebooks, generating
  podcasts, or document-grounded answers. Do not invent write or send actions
  that are not yet exposed as tools.
---

# Google Workspace Router

Route requests to the Google and NotebookLM tools in `mythosaur-tools`.

## Current Tool Map

**Calendar**
- `google_calendar_events` — list events
- `google_calendar_create_event` — create an event

**Gmail**
- `gmail_unread` — inbox status and recent messages
- `gmail_send` — send a message

**Drive**
- `google_drive_recent_files` — recent files
- `google_drive_create_folder` — create a folder
- `google_drive_create_text_file` — create a text/markdown file
- `google_drive_upload_file` — upload a workspace file

**Sheets**
- `google_sheets_read_range` — read cell ranges
- `google_sheets_write_range` — write cell ranges
- `google_sheets_append_rows` — append rows
- `google_sheets_create_sheet` — create a tab

**Docs**
- `google_docs_get` — read a document
- `google_docs_create` — create a document

**Photos** (app-created items only)
- `google_photos_list_albums` — list albums
- `google_photos_create_album` — create an album
- `google_photos_list_media_items` — list media
- `google_photos_upload_file` — upload a file
- `google_photos_add_to_album` — add media to album
- `google_photos_find_duplicate_candidates` — find duplicates
- `google_photos_create_curated_album` — create curated album

**Maps**
- `google_maps_build_route_link` — build a route link
- `google_maps_build_place_link` — build a place link
- `google_maps_search_places` — search places (requires API key)
- `google_maps_compute_route` — compute route (requires API key)

**NotebookLM**
- `notebooklm_auth_status` — check auth
- `notebooklm_list_notebooks` — list notebooks
- `notebooklm_query_notebook` — grounded Q&A
- `notebooklm_create_notebook` — create a notebook
- `notebooklm_list_sources` — list sources in a notebook
- `notebooklm_add_source` — add URL, text, Drive, or file source
- `notebooklm_create_studio_content` — generate podcast, video, mind map, slides, etc.
- `notebooklm_download_artifact` — download generated content
- `notebooklm_share` — share notebook publicly or via invite

## Routing Rules

1. Match the request to the narrowest tool above. Prefer read tools before write tools.
2. For NotebookLM:
   - `notebooklm_list_notebooks` first if the notebook is not clearly identified.
   - `notebooklm_query_notebook` only after you know the target notebook.
   - `notebooklm_create_notebook` + `notebooklm_add_source` to build a knowledge base.
   - `notebooklm_create_studio_content` to generate podcasts, mind maps, slides, etc.
   - `notebooklm_download_artifact` to retrieve generated content.
   - `notebooklm_share` to make notebooks accessible via public or invite link.
3. Do not guess. If the tool does not return the answer, say the data is missing or unavailable.
4. If the user asks for a write action that is not yet implemented, say so clearly instead of improvising.

## Not Yet Available

- Moving or deleting Drive files
- Gmail draft creation
- Full-library duplicate scanning across the user's entire personal Google Photos library

## Standalone Mode

If Google Workspace or NotebookLM execution is unavailable:

- draft the email, calendar entry, note, or response
- state what required API action could not be executed
- gather the fields needed for a later retry or copy-paste completion

Keep the workflow useful even when the execution layer is temporarily unavailable.
