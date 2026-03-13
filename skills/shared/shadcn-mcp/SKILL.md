---
name: shadcn-mcp
description: >
  Use the official shadcn MCP workflow for project-scoped component registry
  browsing and component execution. Start from
  https://ui.shadcn.com/docs/mcp and prefer direct shadcn MCP execution over
  prompt-only component guessing when the consumer can connect a project-local
  MCP server.
---

# shadcn MCP

## Primary Reference

- Official MCP guide: `https://ui.shadcn.com/docs/mcp`

## When To Use

- The request needs real shadcn component execution, not only design guidance.
- The consumer can run a project-local MCP server from the frontend root.
- The project already has `components.json`, or the runtime can bootstrap it first.

## Workflow

1. Confirm the frontend root and that `components.json` exists.
2. Start or connect the official shadcn MCP server from that frontend root.
3. Use shadcn MCP for registry browsing, add/install flows, and component-aware project work.
4. Use `shadcn-ui` for official docs/pattern guidance when implementation decisions still need narrative context.

## Rules

- Prefer direct shadcn MCP execution over hand-written component scaffolding when the runtime supports it.
- Do not proxy shadcn MCP through unrelated tool servers unless the consumer explicitly requires that architecture.
- Treat the frontend root as project-scoped; one project's registry context should not bleed into another.
- If `components.json` is missing, bootstrap or report the missing setup before pretending MCP execution is available.

## Standalone Mode

If shadcn MCP cannot be connected:

- state that live shadcn MCP execution is unavailable
- keep the task moving with `shadcn-ui` docs guidance and verified local project state
- record the missing prerequisite clearly
