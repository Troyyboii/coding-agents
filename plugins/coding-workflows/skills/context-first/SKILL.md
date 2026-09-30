---
name: context-first
description: Assemble missing decision-relevant context internally before acting on an underspecified, scattered, or consequential request. Use when files, prior material, constraints, unresolved requirements, or conflicting evidence must be reconciled for research, planning, a handoff, or a complex build. Do not use for ordinary self-contained requests or to reopen a complete specification; use repo-xray instead for solely repository orientation, and show a briefing only when needed to expose a consequential conflict, unblock one missing input, or support a handoff. Use session-checkpoint to save or resume from an explicit repository checkpoint.
---

# Objective

Create a usable briefing from the material actually available, then proceed on evidence rather than silently filling gaps with generic nonsense.

Read `../../references/workflow-coordination.md` when the task also needs design,
implementation, review, or verification.

## Method

1. Define the decision, deliverable, or action that context must support.
2. Identify the smallest set of relevant sources: user instructions, current files, repository rules, supplied documents, live data, or prior messages the host genuinely provides.
3. Extract only facts that change the answer: goals, constraints, audience, existing decisions, dependencies, evidence, and unresolved choices.
4. Detect contradictions, stale material, and hidden assumptions. Prefer the most authoritative current source and label uncertainty.
5. Assemble a compact internal context packet, then proceed with the requested work unless one missing input materially blocks it.

When requirements are genuinely unresolved, ask only questions whose answers
change scope or design. Compare viable approaches only when a real choice remains,
recommend one, and hand the resolved constraints to `system-designer` or built-in
planning. Do not impose a brainstorming gate after the user has supplied a complete
and internally consistent specification.

## Visibility

Keep the packet internal by default. Show a working brief or evidence map only when:

- the briefing itself is the requested deliverable;
- the user asks to inspect the gathered context;
- a consequential conflict or assumption must be exposed;
- one missing input materially blocks progress; or
- a handoff requires the packet.

Otherwise answer or act directly. Surface only assumptions, conflicts, or uncertainty that affect the result.

When a visible packet is needed, include the goal and success condition, source-backed facts, material assumptions or conflicts, and the decision-ready next action.

## Boundaries

- Do not claim access to memory, chats, files, connectors, or browsing that the host did not provide.
- Do not summarize everything merely because it exists; exclude material that does not affect the current decision.
- Do not turn context gathering into an endless preliminary ceremony. Stop when additional material has diminishing value.
- Do not make the user consume a process briefing before a clear task can begin.
- Do not make external changes while assembling context.

## Final check

Confirm that the brief is shorter than the source pile, preserves the decisions that matter, and makes all consequential uncertainty visible.
