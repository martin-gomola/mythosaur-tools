---
name: code-quality
description: Code quality specialist combining review workflow with coding standards for correctness, security, maintainability, and consistency.
origin: mythosaur-tools
---

# Code Reviewer

Combined code review and coding standards guidance for maintaining correctness, security, maintainability, and consistency.

## When to Activate

- Reviewing pending code changes or PRs
- Auditing modified files for regressions
- Reviewing AI-generated code before acceptance
- Refactoring code to align with project conventions
- Enforcing naming, structure, and error-handling standards

## Primary Goal

Use this skill as the single source of truth for both:
- How code should be written
- How code changes should be reviewed

## Review Process

1. Gather context from the diff or recent commits.
2. Understand the scope and reason for the change.
3. Read surrounding code, not just changed lines.
4. Check the change against the severity checklist.
5. Check the implementation against the coding standards below.
6. Report only issues that are real, actionable, and high confidence.

## Confidence Filter

- Report findings only when confidence is high.
- Skip stylistic opinions unless they violate project conventions.
- Skip unchanged-code issues unless they are critical.
- Consolidate repeated patterns into a smaller number of findings.
- Prioritize bugs, security risks, regressions, data loss, and missing tests.

## Review Checklist

### Security
- Hardcoded credentials or secrets
- SQL injection or unsafe query composition
- XSS from unsanitized user content
- Path traversal through user-controlled paths
- Missing CSRF protection on state-changing routes
- Authentication or authorization gaps
- Sensitive data exposed in logs
- Vulnerable or unsafe dependency usage

### Correctness and Reliability
- Missing error handling
- Unvalidated inputs
- External calls without timeouts
- Internal errors leaked to clients
- Missing loading or error states
- Stale closures or missing hook dependencies
- State updates during render
- Unbounded queries or N+1 patterns

### Maintainability
- Large functions or files that need extraction
- Deep nesting that should be flattened
- Dead code or unreachable branches
- Duplicate logic that should be consolidated
- Weak naming in non-trivial logic
- Magic numbers without explanation
- TODO or FIXME without tracking reference

### Performance
- Inefficient algorithms
- Repeated expensive work without caching or memoization
- Broad imports that increase bundle size
- Blocking synchronous I/O in request paths
- Re-render hotspots in UI code

## Coding Standards

### Core Principles
- Prefer readability over cleverness.
- Keep solutions simple and avoid premature optimization.
- Remove duplication when it improves clarity.
- Avoid speculative abstractions until they are needed.

### Naming and Structure
- Use descriptive variable and function names.
- Prefer verb-noun names for functions.
- Keep modules and components focused on one responsibility.
- Prefer self-documenting code over explanatory comments.

### State and Data Handling
- Prefer immutable updates over direct mutation.
- Use functional state updates when based on prior state.
- Keep data flow explicit and easy to trace.
- Validate request inputs and boundary data.

### Types and APIs
- Prefer explicit types over `any`.
- Keep API response shapes consistent.
- Use clear resource naming and conventional HTTP semantics.
- Make failure cases explicit in interfaces and behavior.

### React and Frontend
- Use typed props and clear component contracts.
- Avoid ternary-heavy render logic when clarity suffers.
- Use stable keys for lists.
- Keep hooks dependency arrays correct.
- Extract reusable logic into hooks when it reduces duplication.

### Error Handling
- Fail clearly and predictably.
- Handle unhappy paths, not just success paths.
- Avoid swallowing exceptions.
- Do not leave debug logging in production changes.

## Approval Criteria

- Approve when there are no critical or high-severity findings.
- Warn when high-severity issues exist without critical problems.
- Block when critical issues are found.

## Working Style

When using this skill:
- Review against the project’s actual conventions, not generic preferences.
- Apply the standards while writing code and while reviewing it.
- Focus first on correctness, security, regressions, and missing coverage.
- Keep findings concise, specific, and tied to concrete files or lines.
- Prefer a short list of strong findings over a long list of weak ones.

Source consolidated from `coding-standards` and adapted from `affaan-m/everything-claude-code` `agents/code-reviewer.md`.
