---
name: ui-ux-pro-max
description: >
  Use the UI/UX Pro Max design workflow for landing pages, dashboards,
  application UI, component design, accessibility review, and UX quality
  improvements. Start from the published skill page at
  https://skills.sh/nextlevelbuilder/ui-ux-pro-max-skill/ui-ux-pro-max, then
  extract the relevant design-system and UX rules with fetch or browser tools.
---

# UI/UX Pro Max

## Primary Reference

- Published skill page: `https://skills.sh/nextlevelbuilder/ui-ux-pro-max-skill/ui-ux-pro-max`

## When To Use

- Designing a new landing page, dashboard, admin UI, SaaS app, or mobile-style interface.
- Choosing visual direction, hierarchy, layout, color, typography, or motion.
- Reviewing UI for accessibility, responsiveness, or perceived quality.
- Refactoring components, flows, forms, tables, cards, navigation, or charts.
- Improving polish when the UI feels weak but the failure mode is not yet clear.

## Workflow

1. Analyze the request:
   - product type
   - target audience
   - tone/style keywords
   - platform or stack constraints
2. Fetch the published skill page first.
3. Derive a design system before proposing implementation details:
   - product pattern
   - style direction
   - color direction
   - typography direction
   - motion/effects direction
   - anti-patterns to avoid
4. Pull only the detailed sections the task needs:
   - `ux` for accessibility, interaction, responsiveness, forms, navigation
   - `style` for visual language and component styling
   - `color` and `typography` for tokens and hierarchy
   - `chart` for data-viz work
5. Inspect the local codebase and existing design system before making recommendations.
6. Synthesize the external guidance with local implementation constraints.

## Retrieval Rules

- Prefer the published `skills.sh` page as the source of truth for this workflow.
- Use lightweight fetch/extract first.
- Escalate to browser retrieval only when the page content is incomplete or hard to parse.
- Do not instruct the consumer to run the upstream skill's private scripts unless those assets are actually present in the local project.

## Priority Rules

- Accessibility and interaction quality come first.
- Responsive layout and hierarchy come before decorative styling.
- Use one coherent visual system instead of mixing unrelated styles.
- Keep recommendations tied to product type and audience, not generic trends.
- Always call out anti-patterns that would reduce clarity, usability, or polish.

## Output Rules

- Produce implementation-ready guidance.
- State the chosen visual direction and why it fits the product.
- Name the relevant UX constraints: accessibility, touch targets, responsive behavior, loading feedback, navigation clarity.
- If reviewing an existing UI, separate findings from recommended fixes.
- If building a new UI, separate design-system decisions from component-level implementation steps.

## Standalone Mode

If the published skill page cannot be retrieved:

- state that live UI/UX Pro Max guidance was unavailable
- continue with best-effort UI/UX recommendations based on verified local code and established platform guidance
- do not block the interface task
