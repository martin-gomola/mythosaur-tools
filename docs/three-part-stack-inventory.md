# Three-Part Stack Inventory

This inventory classifies the current `mythosaur-tools` surface using the 3-part stack:

- `mythosaur-ai` for richest product-specific orchestration
- `skills/shared/` for portable workflow knowledge
- consumer-specific adapter skills for runtime-local routing preferences
- `mythosaur-tools` for shared execution capabilities

## Plugin Inventory

| Component | Classification | Keep In | Notes |
|---|---|---|---|
| `services/mcp_server/plugins/browser_tools.py` | execution | `mythosaur-tools` | Remote browser execution with runtime sessions and configuration. |
| `services/mcp_server/plugins/fetch_tools.py` | execution | `mythosaur-tools` | Shared HTTP retrieval and extraction capability. |
| `services/mcp_server/plugins/filesystem_tools.py` | execution with consumer caveat | `mythosaur-tools` | Useful for generic MCP clients, but Codex and similar IDE agents should prefer native local filesystem tools. |
| `services/mcp_server/plugins/git_tools.py` | execution with consumer caveat | `mythosaur-tools` | Useful for generic MCP clients, but Codex and similar IDE agents should prefer native local git access. |
| `services/mcp_server/plugins/google_tools/` | execution | `mythosaur-tools` | Authenticated Google Workspace, Maps, and Photos access. |
| `services/mcp_server/plugins/notebooklm_tools.py` | execution | `mythosaur-tools` | Authenticated NotebookLM capability execution. |
| `services/mcp_server/plugins/pii_tools.py` | hybrid leaning execution | `mythosaur-tools` | Shared scanning capability plus shared policy patterns. Keep execution here; routing and commit workflow stay in skills. |
| `services/mcp_server/plugins/search_tools.py` | execution | `mythosaur-tools` | Shared SearXNG-backed discovery capability. |
| `services/mcp_server/plugins/time_tools.py` | execution utility | `mythosaur-tools` | Stable utility tool used by multiple consumers. |
| `services/mcp_server/plugins/transcript_tools.py` | execution | `mythosaur-tools` | Remote transcript retrieval is a shared capability. |

## Shared Skill Inventory

| Skill | Classification | Keep In | Notes |
|---|---|---|---|
| `skills/shared/action-triage` | portable workflow knowledge | `skills/shared/` | Shared queue/inbox triage pattern extracted from product-owned inbox workflows without carrying over product-specific routing. |
| `skills/shared/agent-browser` | portable workflow knowledge | `skills/shared/` | Runtime-agnostic browser workflow using the bundled CLI wrapper, not the MCP browser tools. |
| `skills/shared/architect` | portable knowledge | `skills/shared/` | Architecture guidance, not runtime-specific orchestration. |
| `skills/shared/code-quality` | portable knowledge | `skills/shared/` | Shared review and coding standards. |
| `skills/shared/context7` | portable workflow knowledge | `skills/shared/` | Teaches when and how to use Context7; execution remains external. |
| `skills/shared/evidence-briefing` | portable workflow knowledge | `skills/shared/` | Shared evidence-to-brief workflow extracted from Mythosaur-owned research, status, and planning skills. |
| `skills/shared/google-workspace-router` | portable workflow knowledge | `skills/shared/` | Shared routing and guardrails for Google and NotebookLM tool usage. |
| `skills/shared/pii-precommit-check` | portable workflow knowledge | `skills/shared/` | Shared commit workflow and blocking behavior built on top of PII execution tools. |
| `skills/shared/python-patterns` | portable knowledge | `skills/shared/` | Language guidance. |
| `skills/shared/refactor-cleaner` | portable knowledge | `skills/shared/` | Cleanup/refactor guidance. |
| `skills/shared/tool-intent-router` | portable workflow knowledge | `skills/shared/` | Shared routing heuristics for when to call tools. |

## Consumer Adapter Inventory

| Skill | Classification | Keep In | Notes |
|---|---|---|---|
| `skills/consumers/codex/codex-mythosaur-orchestrator` | consumer-specific adapter | `skills/consumers/codex/` | Uses shared Mythosaur workflows while preferring native Codex local tools and MCP for remote execution. |

## Contribution Rule

Use these placement rules for new work:

- Add to `mythosaur-ai` if the logic is product-specific, stateful, or tightly coupled to the primary runtime.
- Add to `skills/shared/` if the logic is stable workflow knowledge that should transfer across consumers.
- Add to `skills/consumers/<runtime>/` if the logic is only an adapter for one runtime's local capabilities.
- Add to `mythosaur-tools` if the logic performs shared execution against remote systems, authenticated APIs, browser sessions, or shared scanning utilities.

## Current Follow-Up Decisions

- Cursor currently shares the lighter IDE MCP catalog, but it does not reuse the Codex adapter by default.
- Add a dedicated Cursor adapter only if Cursor-specific routing behavior proves meaningfully different from the current shared-plus-IDE-profile model.
- `filesystem` and `git` remain exposed by MCP for generic consumers even though Codex should prefer native access.
