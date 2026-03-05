# Skills (Central Source)

`mythosaur-tools` is the source-of-truth for shared skills used across bots and local agent runtimes.

- Shared source path: `skills/shared/`
- OpenClaw consumer mount path (in `mythosaur-ai`): `/opt/openclaw-templates/skills`
- Optional local export helper: `scripts/export-skills.sh`

Do not edit local placeholders under `mythosaur-ai/openclaw/templates/skills`.
Update files here, then restart OpenClaw (`make openclaw-agents`).
