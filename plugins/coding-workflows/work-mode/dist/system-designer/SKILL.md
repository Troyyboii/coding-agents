---
name: system-designer
description: >-
  Design or review a software system by clarifying requirements, defining boundaries and
  interfaces, comparing viable options, and producing an implementation-ready decision.
  Use when the user asks for system design, component boundaries, technology choices,
  integration design, or a substantial structural refactor. Do not use for ordinary
  implementation, settled small changes, repository orientation, or a review limited
  to an existing diff.
---
# System Designer

Read `references/workflow-coordination.md` when design is one phase of a
larger implementation workflow.

## Method

- Inspect existing constraints, code, data contracts, and deployment surfaces before proposing a design.
- Define the goal, users, success criteria, non-goals, and material quality requirements.
- Compare only viable options. Explain costs, failure modes, operational burden, and migration impact.
- Select one approach and make component ownership, interfaces, data flow, and trust boundaries explicit.
- Prefer the smallest design that satisfies the stated requirements. Reuse existing conventions where they remain sound.
- Resolve decisions needed for implementation instead of leaving a menu of undefined choices.
- If one unresolved product or trust decision materially changes the design, hand
  back that exact decision through `context-first`; do not guess or restart broad
  discovery.

## Output

- State the recommended design and why it wins.
- Specify components, public interfaces, data flow, persistence, security boundaries, and failure handling when relevant.
- Include a compact diagram only when relationships are materially clearer visually.
- Give an ordered implementation and migration path with exact scope, protected
  areas, checkpoints, evidence, and stop conditions. Use built-in planning for task
  tracking rather than creating a second planning workflow.

## Boundaries

- Do not invent requirements that can materially change the design.
- Do not disguise a product decision as a technical necessity.
- Do not implement, deploy, or publish unless the user separately authorizes that work.
- Mark facts observed in the repository separately from assumptions and recommendations.
