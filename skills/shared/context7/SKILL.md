---
name: context7
description: >
  Retrieve current library/framework documentation and API examples via
  Context7 MCP when accuracy depends on latest docs.
allowed-tools: Bash(curl:*)
metadata: {"openclaw":{"requires":{"bins":[]}}}
---

# Context7

## Configuration

- Default endpoint: `https://mcp.context7.com/mcp`
- Override: set `CONTEXT7_MCP_URL`
- Optional auth: set `CONTEXT7_API_KEY` (must start with `ctx7sk`)

## Workflow

Wrapper: `$HOME/.openclaw/skills/context7/scripts/context7.sh`
Alias below as `c7` for brevity.

### 1. Resolve the library ID

```bash
c7 resolve-library-id '{"libraryName":"react"}'
```

- If multiple candidates are returned, pick the best match by name and description.
- If no results, try alternate names (e.g., "expressjs" instead of "express").

### 2. Query documentation

```bash
c7 query-docs '{"libraryId":"/facebook/react","query":"useEffect cleanup examples"}'
```

Optional: add `"tokens": 5000` to control response size (default varies by library).

## Output

Response is JSON with a `result.content` array. Each entry has `type: "text"` and a `text` field containing the relevant documentation excerpt. Present the most relevant excerpts to the user; omit boilerplate.

## Troubleshooting

- **No results from resolve**: try broader or alternate library names.
- **Empty docs response**: rephrase the query to be more specific.
- **Auth errors**: verify `CONTEXT7_API_KEY` starts with `ctx7sk` and is valid.
