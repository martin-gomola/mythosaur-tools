---
name: agent-browser
description: >
  Browser automation CLI for AI agents. Use when the user needs to interact
  with websites: navigate pages, fill forms, click buttons, take screenshots,
  extract data, discover selectors, test web apps, or automate any browser
  task. Triggers include "open a URL", "fill out a form", "click a button",
  "take a screenshot", "scrape data from a page", "test this web app",
  "log in to a site", or any task requiring programmatic web interaction.
allowed-tools: Bash(agent-browser:*), Bash($HOME/.openclaw/skills/agent-browser/scripts/agent-browser.sh:*)
metadata: {"openclaw":{"requires":{"bins":["agent-browser"]},"always":true}}
---

# Agent Browser

## Rules

- Start every session by opening a URL and taking a fresh interactive snapshot.
- Interact only via snapshot references (`@e1`, `@e2`, ...), never guessed selectors.
- Re-snapshot after any navigation or DOM-changing action.
- Isolate parallel work with `--session-name <task-id>`.
- Default to headless mode unless visual debugging is requested.

## Commands

Wrapper: `$HOME/.openclaw/skills/agent-browser/scripts/agent-browser.sh`
Alias below as `ab` for brevity.

```bash
ab open <url>
ab snapshot -i
ab click @e1
ab fill @e2 "value"
ab wait --load networkidle
ab screenshot /workspace/public/page.png
```

## Workflow

1. Determine the task type:
   - **Selector discovery** → open, snapshot, return element refs + CSS/XPath candidates.
   - **Form filling / interaction** → open, snapshot, fill/click, re-snapshot, verify.
   - **Screenshot capture** → open, wait for networkidle, screenshot.

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
- Save all artifacts under `/workspace/public/`.
