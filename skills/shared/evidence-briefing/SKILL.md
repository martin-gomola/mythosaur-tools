---
name: evidence-briefing
description: >
  Turn evidence into a concise brief, update, plan, or decision note. Use when
  the task is to summarize findings, prepare a status update, draft a weekly
  plan, or produce a compact written artifact from local files, search/fetch
  results, Google Docs/Sheets data, or calendar context.
---

# Evidence Briefing

Use this skill when the user wants a brief, update, plan, or compact report grounded in evidence rather than freeform opinion.

## Goal

- Gather the minimum evidence needed.
- Turn that evidence into a concise, decision-useful artifact.
- Keep publishing separate from drafting.

## Workflow

1. Clarify the target if needed:
   - topic or project
   - audience
   - reporting or planning window
   - desired output destination such as chat, Doc, or Sheet
2. Gather the minimum evidence first:
   - prefer native local file/search tools for workspace evidence when the consumer has them
   - use `tool-intent-router` to choose remote evidence tools like search/fetch
   - use `google-workspace-router` when the source of truth is Calendar, Docs, Sheets, Gmail, Drive, or NotebookLM
3. Build a compact structure:
   - summary or focus
   - key evidence or recent deltas
   - risks, blockers, or uncertainty
   - next step, ask, or decision
4. If the result should become a durable artifact, draft it fully first and only then publish it to a Doc, Sheet, email, or another destination.

## Judgment Rules

- Prefer explicit evidence over narrative filler.
- Prefer a few strong inputs over broad shallow collection.
- Separate facts, interpretation, and missing data.
- If evidence is thin or stale, say so directly.
- Keep the result short enough to scan in one pass unless the user asks for depth.

## Tooling Split

This skill owns:

- deciding what evidence matters
- deciding when there is enough evidence
- structuring the final brief or plan
- making uncertainty and next steps explicit

Tools and other shared skills own:

- local/native workspace reads and search
- remote search/fetch execution
- Google and NotebookLM execution
- final publish/write actions

## Standalone Mode

If live execution is unavailable:

- still produce the brief, update, or plan in chat-ready form
- state what could not be verified or published live
- leave the missing execution step as an explicit follow-up
