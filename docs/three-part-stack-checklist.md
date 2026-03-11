# Three-Part Stack Checklist

## Current Decision

- [x] Keep `mythosaur-ai` as the richest orchestration runtime.
- [x] Keep `skills/shared/` as the portable workflow knowledge layer.
- [x] Add consumer-specific adapter skills instead of making every consumer emulate `mythosaur-ai`.
- [x] Keep `mythosaur-tools` focused on shared execution capabilities.

## Phase 1: Foundation

- [x] Write the 3-part stack decision document.
- [x] Audit every current skill and plugin as `product-specific`, `portable knowledge`, or `execution`.
- [x] Create a Codex-specific adapter skill scaffold.
- [x] Add export support for `shared + consumer-specific` skill bundles.
- [x] Document how Codex should install the bundle and what it should prefer natively.

## Phase 2: Codex Integration

- [x] Add a Codex-oriented tool discovery profile that prefers remote execution plugins only.
- [x] Document the Codex routing contract in `docs/integration.md`.
- [ ] Validate that Codex local tasks do not require MCP for filesystem or git work.
- [ ] Validate that Codex still routes search, browser, Google, NotebookLM, and PII through MCP.

## Phase 3: Shared Knowledge Cleanup

- [x] Review shared skills for consumer-agnostic wording.
- [x] Split any Codex-specific guidance out of `skills/shared/`.
- [ ] Move product-specific orchestration details back to `mythosaur-ai` where needed.
- [x] Add a "standalone mode" rule to each shared workflow that should still produce useful output without MCP.

## Phase 4: Rollout

- [ ] Export the new Codex bundle into a local Codex skills directory and smoke test it.
- [ ] Verify `mythosaur-ai` still consumes shared skills without regression.
- [x] Decide whether Cursor should reuse the Codex adapter or get its own consumer-specific skill.
- [x] Publish a contribution rule for where new orchestration logic belongs.

## Started In This Change

- [x] Added the 3-part stack decision doc.
- [x] Added this checklist.
- [x] Added the Codex consumer skill scaffold.
- [x] Started exporter changes for consumer-specific bundles.
- [x] Started lighter MCP catalog support for Codex.
