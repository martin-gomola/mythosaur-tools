# mythosaur-tools

A shared MCP tool forge for the Mythosaur stack.

This repository keeps network-facing tools, external integrations, and shared skill sources separate from `mythosaur-ai` so the runtime can stay local-first while the tool backend evolves on its own cadence.

## The Forge

`mythosaur-tools` is the companion arsenal:

- search, fetch, browser, Google Workspace, NotebookLM, and PII tooling
- transcript extraction for supported video URLs
- browser-backed rendered-page extraction for difficult sites
- a single MCP HTTP surface for local runtimes and IDE clients
- the shared source-of-truth for reusable Mythosaur skills

The local runtime still keeps its hands on the workbench:

- workspace filesystem mutation
- local git operations
- message delivery, cron, sessions, memory, and routing

That boundary is deliberate. Network and API integrations benefit from one shared MCP implementation. Direct workspace mutation is safer and more reliable when it stays local.

## What It Provides

- MCP endpoint at `/mcp`
- health endpoint at `/healthz`
- bundled SearXNG plus `searxng-cache` for search
- bearer auth with `Authorization: Bearer <MYTHOSAUR_TOOLS_API_KEY>`
- canonical plugin namespace `mythosaur.*` with `osaurus.*` aliases

## Quick Start

```bash
cp .env.example .env
# set MYTHOSAUR_TOOLS_API_KEY
# set MYTHOSAUR_TOOLS_WORKSPACE_HOST to the repo or workspace you want exposed

docker compose up -d --build
curl -s http://127.0.0.1:${MYTHOSAUR_TOOLS_MCP_PORT:-8064}/healthz | jq
```

Default host ports:

- `8063` for `searxng-cache`
- `8064` for the MCP server

## The Arsenal

Tool families currently forged here:

- time and date helpers
- web search and fetch
- transcript extraction for supported video URLs
- browser automation and rendered-page extraction fallback
- guarded filesystem and git access for the mounted workspace
- Google Workspace, Google Maps, Google Photos, and NotebookLM tools
- PII scanning and pre-commit hook install helpers

The full catalog lives in [docs/catalog.md](docs/catalog.md).

## Skills

Shared skill source-of-truth lives under `skills/shared/*`.

Consumer-specific adapter skills live under `skills/consumers/*`.
These adapt shared workflows to a specific runtime without moving product-specific
orchestration into the MCP server.

Export those skills into a local agent environment with:

```bash
./scripts/export-skills.sh
```

Or choose a custom target:

```bash
./scripts/export-skills.sh /path/to/your/agent/skills
```

Export shared skills plus the Codex adapter bundle with:

```bash
./scripts/export-skills.sh --consumer codex
```

The default export target is `~/.codex/skills/mythosaur`.
Each export also writes `~/.codex/skills/mythosaur/.export-manifest.json` so you can inspect which
skills were copied into the bundle and which sibling skills were overwritten in the parent registry.

For IDE-focused deployments, you can also run the server with
`MYTHOSAUR_TOOLS_DEFAULT_CONSUMER=codex` to default discovery to the lighter remote-execution catalog.

Useful shortcuts:

```bash
make codex-install
make codex-smoke
make codex-up
```

## Structured Delivery Bundle

For nontrivial plugin, shared-skill, infra, or docs work, initialize a local execution bundle:

```bash
make init-execution-bundle TITLE="Add fetch retry guard" SUMMARY="Keep retry behavior explicit and tested"
```

This writes:

- `artifacts/execution/request-packet.json`
- `artifacts/execution/implementation-contract.md`
- `artifacts/execution/verification-plan.md`
- `artifacts/execution/evidence-bundle.md`
- `artifacts/execution/completion-summary.md`
- `docs/architecture-decisions.md`

The goal is simple: keep tool/plugin work packetized, evidence-backed, and easy to resume without recreating the full lane system from `mythosaur-ai`.

As work progresses, update the bundle status and write back evidence:

```bash
make update-execution-bundle STATUS=in_progress
python scripts/update_execution_bundle.py --status completed \
  --evidence "uv run pytest tests/test_execution_bundle.py -q" \
  --summary "Verification passed"
```

## The Waypoints

Start here, then go deeper only if you need the details:

- [docs/setup.md](docs/setup.md): local bring-up, Cursor wiring, smoke tests
- [docs/catalog.md](docs/catalog.md): tool families, shared skills, security defaults
- [docs/integration.md](docs/integration.md): MCP endpoints, auth, protocol, response contract, env vars
- [docs/google-setup.md](docs/google-setup.md): Google Workspace, Maps, and NotebookLM bootstrap
- [docs/google-operations.md](docs/google-operations.md): design rules for Google services in the stack
- [docs/notebooklm.md](docs/notebooklm.md): NotebookLM verification and troubleshooting

## The Pact with mythosaur-ai

`mythosaur-ai` consumes this MCP backend via `MYTHOSAUR_TOOLS_MCP_URL` and `MYTHOSAUR_TOOLS_API_KEY`.
The same backend can serve Grogu, Mythosaur, Nanoclaw, and local IDE clients without duplicating tool logic or auth bootstrap.
