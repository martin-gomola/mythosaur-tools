---
name: action-triage
description: >
  Triage incoming items such as emails, tickets, alerts, or queue entries,
  prioritize what needs action, and draft a response or next step before any
  send/write action. Use when the user asks what needs attention, what needs a
  reply, or how to sort urgent items from monitor-only items.
---

# Action Triage

Use this skill when the user wants to triage a queue of incoming items rather than summarize them all equally.

## Goal

- Separate urgent action from routine awareness.
- Produce a short, decision-useful triage view.
- Draft responses before taking any send or write action.

## Workflow

1. Clarify the triage target if needed:
   - which queue or source
   - how many recent items to consider
   - whether the goal is prioritization, drafting, or both
2. Gather the minimum item set first:
   - use native local tools for local queues when available
   - use `google-workspace-router` for Gmail-backed inbox work
   - use `tool-intent-router` for other remote sources
   - pull local workspace context only if it is needed to produce a grounded response
3. Build a compact triage structure:
   - urgent / time-sensitive
   - action needed
   - monitor / no action
   - drafted reply or recommended next step
4. If a send or write action is requested, draft first and execute only after the content is coherent.

## Judgment Rules

- Prefer a short priority list over equal treatment of every item.
- Distinguish action-required items from awareness-only items.
- Do not draft a confident response when critical context is missing.
- Surface uncertainty instead of guessing intent from partial evidence.
- Keep the output easy to scan.

## Tooling Split

This skill owns:

- deciding which items matter
- prioritizing what needs action
- deciding whether there is enough context to draft a response
- producing the triage view and draft text

Tools and other shared skills own:

- queue retrieval
- workspace lookup
- remote Gmail or other execution actions
- final send/write actions

## Standalone Mode

If live execution is unavailable:

- still provide the triage structure for pasted items
- note that queue freshness could not be verified live
- leave any send/write action as an explicit follow-up
