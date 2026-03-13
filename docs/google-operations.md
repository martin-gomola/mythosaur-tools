# Google Operations Design

This document defines how Google services should fit into the Mythosaur stack without turning into a pile of one-off workflows.

## Goal

Keep each system responsible for one thing:

- Google Drive stores files.
- Google Docs stores collaborative narrative documents.
- Google Sheets stores indexes, registries, and lightweight structured rows.
- Google Photos stores app-created media collections and curated albums.
- Google Maps stores route links and optional API-backed route or place lookups.
- NotebookLM stores research and document-grounded knowledge.
- Workspace files store active project state, tasks, and decisions.

## Current Capabilities

Available today in `mythosaur-tools`:

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

These now cover the first clean write layer for Gmail, Drive, Sheets, Docs, and app-created Google Photos albums/media, plus direct text-file creation in Drive, both Google Maps link builders and API-backed itinerary primitives, and the current NotebookLM notebook/source/studio flows exposed by the CLI wrapper.

## Runtime Capability Flags

OAuth scopes and runtime permission flags are separate on purpose.

- OAuth scopes define what the Google token can do.
- runtime capability flags define what Mythosaur is allowed to do right now.

Current env-backed capability flags:

- `MT_GOOGLE_CALENDAR_READ_ENABLED`
- `MT_GOOGLE_CALENDAR_WRITE_ENABLED`
- `MT_GOOGLE_GMAIL_READ_ENABLED`
- `MT_GOOGLE_GMAIL_SEND_ENABLED`
- `MT_GOOGLE_DRIVE_READ_ENABLED`
- `MT_GOOGLE_DRIVE_WRITE_ENABLED`
- `MT_GOOGLE_SHEETS_READ_ENABLED`
- `MT_GOOGLE_SHEETS_WRITE_ENABLED`
- `MT_GOOGLE_DOCS_READ_ENABLED`
- `MT_GOOGLE_DOCS_WRITE_ENABLED`
- `MT_GOOGLE_PHOTOS_READ_ENABLED`
- `MT_GOOGLE_PHOTOS_WRITE_ENABLED`
- `MT_GOOGLE_MAPS_ENABLED`
- `MT_NOTEBOOKLM_ENABLED`

This lets you keep one separate bot Google account with broad scopes, while still disabling actions in the runtime until you explicitly want them.

## Future UI Contract

These capability flags should become toggles in a Mythosaur settings UI later.

Recommended UI sections:

- Calendar
- Gmail
- Drive
- Sheets
- Docs
- Photos
- Maps
- NotebookLM

Each section should expose:

- enabled or disabled
- read actions
- write actions
- account identity in use
- token health or scope health

The UI should manage runtime policy, not store business logic. The MCP tools remain the execution layer.

For Calendar specifically, separate:

- read events
- create events

This lets the assistant manage briefing or check-in events without forcing full calendar write behavior to always stay on.

## Planned Atomic Tools

Add small MCP tools, not one large "Google workflow" tool.

### Gmail

- `gmail_draft_create`
- `gmail_search`

### Google Drive

- `google_drive_get_file`
- `google_drive_search_files`

### Google Sheets

- keep the current write tools narrow and stable
- add higher-level conventions in Mythosaur, not in the tool layer

### Google Docs

- keep Docs tools focused on document creation and straightforward reads
- add richer document workflows in Mythosaur, not in the tool layer

### Google Maps

- `google_maps_build_route_link`
- `google_maps_build_place_link`
- `google_maps_search_places`
- `google_maps_compute_route`

These should keep generating stable links first. When a Maps API key is configured, Places and Routes can also be queried directly for itinerary building. Route persistence still belongs in Sheets, not in the Maps layer.

Maps config:

- `MT_GOOGLE_MAPS_API_KEY`
- `MT_GOOGLE_MAPS_PLATFORM`

`MT_GOOGLE_MAPS_API_KEY` enables the live Places and Routes tools. `MT_GOOGLE_MAPS_PLATFORM` can still be reserved for project/platform metadata or future policy.

### Google Photos

- `google_photos_list_albums`
- `google_photos_create_album`
- `google_photos_list_media_items`
- `google_photos_upload_file`
- `google_photos_add_to_album`
- `google_photos_find_duplicate_candidates`
- `google_photos_create_curated_album`

These operate on app-created Google Photos albums and media items. Duplicate detection is heuristic and limited to the media items that the current Google Photos API still allows the app to list.

### NotebookLM

- `notebooklm_create_notebook`
- `notebooklm_get_notebook`
- `notebooklm_add_source_url`
- `notebooklm_add_source_text`
- `notebooklm_add_source_drive_file`
- `notebooklm_describe_notebook`
- `notebooklm_get_or_create_notebook`

## Ownership Model

To avoid spaghetti, each data type has one canonical home.

### Files

Canonical home: Google Drive

Use Drive for:

- PDFs
- generated reports
- exported artifacts
- screenshots
- route plans
- supporting documents

Do not use NotebookLM as a general file store.

### Structured Registry Data

Canonical home: Google Sheets

Use Sheets for:

- lists of routes
- location registries
- delivery or travel tables
- notebook indexes
- Drive file URLs
- status rows

Do not use Sheets as a document store.

### Research Memory

Canonical home: NotebookLM

Use NotebookLM for:

- research notebooks
- source collections
- grounded question answering
- summaries over curated document sets

Do not use NotebookLM as the source of truth for active tasks or operations.

### Active Project Memory

Canonical home: workspace epic files

Use workspace files for:

- `tasks.md`
- `memory.md`
- `docs/plan.md`
- `docs/decision-YYYY-MM-DD.md`

This remains the operational source of truth for Grogu and Mythosaur.

## Canonical Linking Pattern

Each workflow should produce explicit links between systems.

Example route workflow:

1. Generate Google Maps route link.
2. Store the route link and metadata in Google Sheets.
3. Store any supporting files in Drive.
4. Store route research or context in NotebookLM if there is document-backed reasoning.
5. Write the current status and next action into workspace files.

This means:

- Drive holds the file URL
- Sheets holds the row that references the Drive file and Maps link
- NotebookLM holds the research context
- workspace files hold the live task/decision state

## Naming Conventions

Use stable, human-readable names.

### Drive

Folder pattern:

- `Mythosaur/<domain>/<project-or-epic>/`

Examples:

- `Mythosaur/routes/client-a/`
- `Mythosaur/research/epic-demo-landing/`

### Sheets

Workbook pattern:

- one workbook per domain or workflow

Tab pattern:

- `routes`
- `locations`
- `deliveries`
- `notebooks`
- `artifacts`

### NotebookLM

Notebook pattern:

- one notebook per project, client, or stable research area

Examples:

- `Client A Routes`
- `Demo Landing Research`
- `Mythosaur Travel Ops`

Do not create a new notebook for every small question.

## Bot Responsibilities

### Grogu

Use for:

- quick retrieval
- "what do I have"
- "what is on my calendar"
- "what are the takeaways from notebook X"
- "show the latest Drive files"

Grogu should not run long multi-system workflows unless the path is trivial and deterministic.

### Mythosaur

Use for:

- multi-step workflows
- choosing the right notebook, sheet, and Drive folder
- connecting retrieved facts to active work
- writing decisions and task updates into workspace memory

Mythosaur is the orchestrator. The tools stay atomic.

## Anti-Spaghetti Rules

1. Never hide multiple side effects behind one generic tool.
2. Keep each MCP tool narrow and explicit.
3. Keep write operations separate from read operations.
4. Keep Drive, Sheets, Maps, NotebookLM, and workspace memory as separate layers.
5. Prefer IDs and URLs in Sheets over copying large blobs of content between systems.
6. Write the workflow state back into workspace files, not only into Google services.
7. Use shared skills only for routing and policy, not for embedding large operational logic.

## Recommended Rollout

Phase 1:

- ship the routing skill for current read tools

Phase 2:

- add write tools for Gmail, Drive, and Sheets

Status:

- complete for the first atomic set

Phase 3:

- add Google Maps link builders

Status:

- complete

Phase 4:

- add NotebookLM notebook/source creation tools

Phase 5:

- add one Mythosaur workflow that ties them together for a concrete use case

Example:

- route planning
- client outreach
- research archive

Build one clean workflow at a time.
