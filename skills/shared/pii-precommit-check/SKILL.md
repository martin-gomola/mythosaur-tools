---
name: pii-precommit-check
description: >
  Run shared PII scan tools before commits, interpret findings, and block
  commit progress until sensitive values are redacted or parameterized. Use
  before creating a commit, when reviewing staged changes for secrets, emails,
  local home paths, tokens, or auth files, or when installing local pre-commit
  protection for a repo.
---

# pii-precommit-check

## Workflow

1. Call `scan_pii_staged` first.
2. If findings exist:
   - stop the commit
   - redact or parameterize the sensitive values
   - rerun the scan
3. If the user wants repo-wide validation, call `scan_pii_repo`.
4. If the user wants automatic local protection, call `install_pii_precommit_hook`.

## Design

This skill stays intentionally small.

The shared MCP tools own:

- scanning
- matching and severity rules
- structured findings
- hook installation

The skill owns:

- when to trigger
- which tool to call
- how to react to findings

## Standalone Mode

If the shared PII MCP tools are unavailable:

- stop the commit anyway
- run an equivalent local scan if one is available
- manually inspect staged diffs for emails, home paths, tokens, and auth material
- do not proceed until the findings are either redacted or intentionally suppressed
