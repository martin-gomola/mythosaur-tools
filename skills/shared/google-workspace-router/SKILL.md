---
name: google-workspace-router
description: >
  Route requests about Google Calendar, Gmail, Google Drive, Google Sheets,
  and NotebookLM to the current mythosaur-tools MCP tools. Use when the user
  asks about meetings, unread mail, Drive files, spreadsheet ranges, notes,
  research notebooks, or document-grounded answers. Do not invent write or
  send actions that are not yet exposed as tools.
metadata: {"openclaw":{"always":false}}
---

# Google Workspace Router

Use this skill for requests backed by the Google and NotebookLM tools in `mythosaur-tools`.

## Current Tool Map

- Calendar -> `google_calendar_events`
- Calendar create -> `google_calendar_create_event`
- Gmail inbox status -> `gmail_unread`
- Gmail send -> `gmail_send`
- Drive recent files -> `google_drive_recent_files`
- Drive folder creation -> `google_drive_create_folder`
- Drive text file creation -> `google_drive_create_text_file`
- Drive file upload -> `google_drive_upload_file`
- Sheets read-only cell ranges -> `google_sheets_read_range`
- Sheets range writes -> `google_sheets_write_range`
- Sheets row appends -> `google_sheets_append_rows`
- Sheets tab creation -> `google_sheets_create_sheet`
- Maps route links -> `google_maps_build_route_link`
- Maps place links -> `google_maps_build_place_link`
- Maps place search -> `google_maps_search_places`
- Maps route compute -> `google_maps_compute_route`
- NotebookLM auth check -> `notebooklm_auth_status`
- NotebookLM notebook discovery -> `notebooklm_list_notebooks`
- NotebookLM grounded Q&A -> `notebooklm_query_notebook`

## Routing Rules

1. Use a Google or NotebookLM tool when the user asks about:
   - upcoming meetings, schedule, or calendar windows
   - creating a calendar event
   - unread email or inbox state
   - sending an email
   - recent Drive files
   - creating a Drive folder
   - creating a text or markdown file in Drive
   - uploading a workspace file to Drive
   - reading a specific sheet range
   - writing or appending sheet data
   - creating a sheet tab
   - generating a Google Maps route or place link
   - searching for places on a route
   - computing route distance and duration
   - their notes, research, notebooks, or NotebookLM content
2. For NotebookLM:
   - use `notebooklm_list_notebooks` first if the notebook is not clearly identified
   - use `notebooklm_query_notebook` only after you know the target notebook
3. Do not guess. If the tool does not return the answer, say the data is missing or unavailable.
4. If the user asks for a write action that is not yet implemented, say so clearly instead of improvising.

## Not Yet Available

These actions are planned but not currently exposed through `mythosaur-tools`:

- creating or updating NotebookLM notebooks and sources
- moving or deleting Drive files
- Gmail draft creation

## Role Split

- Grogu: use these tools for quick retrieval and short answers.
- Mythosaur: use these tools to gather inputs for planning, then write durable project state back into workspace files.

For assistant workflows such as daily briefing slots, prefer creating a calendar event explicitly instead of implying that a briefing job already exists.
