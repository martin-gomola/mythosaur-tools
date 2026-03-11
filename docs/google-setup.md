# Google Setup

`mythosaur-tools` owns the canonical Google auth bootstrap because it owns the MCP runtime contract and the `secrets/` mount.

`mythosaur-ai` can still call the same flow through its wrapper targets, but the source of truth lives here.

## Files

Store auth material in the local `secrets/` directory:

- `secrets/google-credentials.json`
- `secrets/google-token.json`

NotebookLM host auth also lives under `secrets/notebooklm/`.

## Minimal Google Workspace Bootstrap

1. Open Google Cloud Console at `https://console.cloud.google.com/`.
2. Create or select a project.
3. Enable the APIs you actually plan to use:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Sheets API
   - Google Docs API
   - Google Photos Library API
   - Places API
   - Routes API
4. Configure the OAuth consent screen.
5. Create an OAuth client ID with application type `Desktop app`.
6. Save the downloaded credentials file as `secrets/google-credentials.json`.
7. Run the login flow:

```bash
make google-login
```

## Important Rules

- Use a Desktop-app OAuth client JSON
- Do not use a service account key for these user-scoped tools
- `make google-login` also handles NotebookLM host login when NotebookLM is enabled in `.env`
- the container mounts `./secrets` to `/secrets`
- for standalone IDE use, set `MYTHOSAUR_TOOLS_WORKSPACE_HOST` directly in `.env`
- from `mythosaur-ai`, `make google-login` delegates back to this repo

## Runtime Gates

OAuth scopes and runtime policy are separate on purpose.

The token may hold broad scopes while the runtime stays restricted through flags such as:

- `MYTHOSAUR_TOOLS_GOOGLE_*_ENABLED`
- `MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_WRITE_ENABLED`
- `MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED`

Google Photos remains limited to app-created albums and media items, plus duplicate-candidate heuristics over that app-created set.

## Maps Configuration

For API-backed Maps tools:

- set `GOOGLE_MAPS_API_KEY` in `.env`
- optionally set `GOOGLE_MAPS_PLATFORM`
- enable only the Maps Platform services you plan to use

Without a Maps API key, the link-builder tools still work, but API-backed Maps calls return a structured configuration error.

## Environment Variables

- `MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE=/secrets/google-credentials.json`
- `MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE=/secrets/google-token.json`
- `MYTHOSAUR_TOOLS_GOOGLE_*_ENABLED=true|false`
- `GOOGLE_MAPS_API_KEY=<your-maps-api-key>`
- `GOOGLE_MAPS_PLATFORM=<your-project-or-platform-id>`
- `NOTEBOOKLM_MCP_CLI_PATH=/secrets/notebooklm`
- `MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=mythosaur`

## Related Guides

- [google-operations.md](google-operations.md)
- [notebooklm.md](notebooklm.md)
