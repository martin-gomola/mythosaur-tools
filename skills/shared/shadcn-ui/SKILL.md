---
name: shadcn-ui
description: >
  Use the official shadcn/ui skills guidance for requests that mention shadcn,
  shadcn/ui, or the shadcn skills docs. Fetch
  https://ui.shadcn.com/docs/skills first, then use the relevant official
  shadcn docs pages for the components or patterns the task needs.
---

# shadcn/ui

## Primary Reference

- Official skills doc: `https://ui.shadcn.com/docs/skills`

## When To Use

- The request explicitly mentions `shadcn` or `shadcn/ui`.
- The task is to build or redesign a UI using shadcn/ui components or patterns.
- The user links to `https://ui.shadcn.com/docs/skills` or another `ui.shadcn.com` docs page.

## Workflow

1. Fetch the official skills doc first.
2. Pull only the component or pattern docs that the task actually needs.
3. Inspect the local project before suggesting changes:
   - `components.json`
   - `package.json`
   - existing `components/ui/*`
   - current Tailwind or design-token setup
4. Reuse existing project conventions instead of inventing a fresh component system.
5. If the page is hard to extract with plain fetch, use browser-based retrieval.

## Retrieval Rules

- Prefer official shadcn docs over third-party summaries.
- Use lightweight fetch/extract first for `ui.shadcn.com`.
- Escalate to browser retrieval only when the fetched page is incomplete or heavily client-rendered.
- If the task depends on a specific component, fetch that component's official docs page after the skills page.

## Output Rules

- Keep recommendations implementation-ready.
- Name the specific shadcn/ui primitives, blocks, or patterns you are using.
- Call out any local setup gaps such as missing shadcn init, missing Tailwind config, or absent component files.
- Do not claim a component exists locally unless you verified it in the project.

## Standalone Mode

If live shadcn docs cannot be retrieved:

- say that the official shadcn docs were unavailable
- continue with best-effort guidance based on verified local project state
- avoid blocking the rest of the UI task
