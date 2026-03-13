# Skills (Central Source)

`mythosaur-tools` is the source of truth for shared skills used across agent runtimes and consumers.

- Shared source path: `skills/shared/`
- Consumer-specific adapters: `skills/consumers/`
- Optional local export helper: `scripts/export-skills.sh`

Current shared skills:
- `action-triage`
- `context7`
- `evidence-briefing`
- `agent-browser`
- `architect`
- `code-quality`
- `shadcn-ui`
- `shadcn-mcp`
- `ui-ux-pro-max`
- `python-patterns`
- `refactor-cleaner`
- `tool-intent-router`
- `pii-precommit-check`
- `google-workspace-router`

Update shared skills in this directory. Consumers should sync or reload them using their own runtime-specific workflow.

Use consumer-specific skills only for runtime adapters such as Codex-specific routing preferences.
Do not move product-specific `mythosaur-ai` orchestration into this repo's consumer skill layer.
