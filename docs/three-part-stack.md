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

Extraction gate for moving logic from `mythosaur-ai` into `skills/shared/`:

- keep new workflow logic product-local first
- extract only after the pattern repeats across at least two product workflows or clearly transfers across consumers
- extract the reusable workflow skeleton and guardrails, not product-specific triggers, role ownership, or workspace artifact names
- do not let new prompt workflows shadow deterministic direct intents that already have a narrower runtime path

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

## Implementation Progress

The first article-aligned product workflows now live in `mythosaur-ai`, not in this repo's MCP server:

- `research-brief` keeps research synthesis and judgment in Markdown while using `mythosaur-tools` for search, fetch, and NotebookLM execution
- `status-brief` keeps weekly/project update structure and reporting judgment in Markdown while using local workspace reads plus Docs/Sheets execution tools when needed
- `weekly-planning` keeps planning judgment in Markdown while using local workspace reads plus live calendar/Docs reads when capacity or publication matters
- `release-prep` keeps release-readiness judgment in Markdown while using workspace delivery artifacts plus optional Docs publication
- `inbox-triage` keeps message prioritization and reply judgment in Markdown while using Gmail execution tools only for inbox reads and explicit send actions
- `evidence-briefing` now captures the reusable cross-consumer pattern in `skills/shared/`: clarify target, gather minimal evidence, draft first, then publish
- `action-triage` now captures the reusable cross-consumer triage pattern in `skills/shared/`: sort urgent/action-needed/monitor items, draft first, then send

That is the intended model:

- product-specific workflow knowledge in `mythosaur-ai`
- portable shared routing in `skills/shared/`
- execution-only capabilities in `mythosaur-tools`
