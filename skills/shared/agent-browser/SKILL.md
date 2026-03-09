---
name: agent-browser
description: >
  Browser automation via the agent-browser CLI for web interaction tasks
  including navigation, forms, clicks, screenshots, scraping, and UI testing.
  This skill uses the standalone agent-browser binary, not the MCP browser_*
  tools. Use when the user needs interactive browser sessions with snapshot-based
  element references, or when the MCP browser tools are insufficient for the task.
---

# Agent Browser

## Rules

- Start every session by opening a URL and taking a fresh interactive snapshot.
- Interact only via snapshot references (`@e1`, `@e2`, ...), never guessed selectors.
- Re-snapshot after any navigation or DOM-changing action.
- Isolate parallel work with `--session-name <task-id>`.
- Default to headless mode unless visual debugging is requested.

## Commands

The wrapper script is bundled at `scripts/agent-browser.sh` (relative to this skill directory).
The consumer runtime determines the absolute path. Alias as `ab` for brevity.

```bash
ab open <url>
ab snapshot -i
ab click @e1
ab fill @e2 "value"
ab wait --load networkidle
ab screenshot output/page.png
```

## Workflow

1. Determine the task type:
   - **Selector discovery** -> open, snapshot, return element refs + CSS/XPath candidates.
   - **Form filling / interaction** -> open, snapshot, fill/click, re-snapshot, verify.
   - **Screenshot capture** -> open, wait for networkidle, screenshot.

2. Core loop:

```bash
ab open <url>
ab snapshot -i
# interact with refs
ab snapshot -i        # always re-snapshot after mutations
```

## Troubleshooting

- **Empty snapshot**: page may still be loading. Run `ab wait --load networkidle` then re-snapshot.
- **Stale ref after click**: DOM changed. Re-snapshot to get fresh refs.
- **Timeout on open**: verify URL is reachable; retry once before reporting failure.

## Deliverables

- Selector tasks: element refs and matching CSS/XPath candidates.
- Testing tasks: steps executed, assertions, and screenshots.
- Save artifacts under the workspace output directory.
