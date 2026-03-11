# Three-Part Stack

## Context

`mythosaur-tools` serves multiple consumers, but the primary runtime is `mythosaur-ai`.
That creates a layering problem:

- `mythosaur-ai` needs richer orchestration than generic IDE clients.
- Codex and Cursor should reuse portable workflow knowledge without inheriting product-specific runtime behavior.
- MCP should stay focused on execution, not become a second agent runtime.

The goal is to keep the richest behavior in the primary runtime while still exposing portable skills and execution tools to other consumers.

## Decision

Use a 3-part stack:

1. `mythosaur-ai` keeps the richest product-specific orchestration.
2. `skills/shared/` keeps portable workflow knowledge that can be exported to multiple consumers.
3. Consumer-specific adapter skills translate shared workflows into the local runtime's preferred execution model.

For Codex, that means:

- prefer native Codex tools for local filesystem, shell, git, and code editing work
- use `mythosaur-tools` MCP only for remote or authenticated execution work
- preserve standalone behavior where a skill can still produce useful output without MCP

## Consequences

Positive:

- `mythosaur-ai` can keep product-specific orchestration without constraining other clients
- shared workflow knowledge stays versioned in Markdown and exported across consumers
- Codex gets lower MCP tool overhead and more natural routing
- `mythosaur-tools` stays a capability backend instead of growing a second orchestration layer

Tradeoffs:

- workflow logic now exists at two levels: shared and consumer-specific
- portability requires active boundary discipline
- exporter and documentation need to understand both shared and consumer-specific skills

## Placement Rules

Put logic in `mythosaur-ai` when it is:

- product-specific
- tied to durable project state or memory
- dependent on local runtime affordances or internal orchestration

Put logic in `skills/shared/` when it is:

- stable workflow knowledge
- useful across `mythosaur-ai`, Codex, Cursor, and similar consumers
- understandable without direct access to a specific runtime implementation

Put logic in consumer-specific skills when it is:

- an adapter for local tool preference
- necessary to map shared workflows into a specific consumer's runtime
- not portable enough for `skills/shared/`

Put logic in `mythosaur-tools` when it is:

- authenticated remote execution
- browser automation
- search/fetch/transcript retrieval
- Google Workspace or NotebookLM integration
- PII scanning or other shared capability execution
