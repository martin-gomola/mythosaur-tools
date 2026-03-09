# Skills (Central Source)

`mythosaur-tools` is the source of truth for shared skills used across agent runtimes and consumers.

- Shared source path: `skills/shared/`
- Optional local export helper: `scripts/export-skills.sh`

Current shared skills:
- `context7`
- `agent-browser`
- `architect`
- `code-quality`
- `python-patterns`
- `refactor-cleaner`
- `tool-intent-router`
- `pii-precommit-check`
- `google-workspace-router`

Update shared skills in this directory. Consumers should sync or reload them using their own runtime-specific workflow.
