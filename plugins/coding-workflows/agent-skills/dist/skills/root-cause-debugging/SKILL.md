---
name: root-cause-debugging
description: Diagnose a reproducible bug, failing test, build error, performance regression, or unexpected technical behavior before repair. Use when the cause is unknown and the task requires evidence, reproduction, data-flow tracing, or hypothesis testing. Do not use when the cause is already demonstrated, for broad repository audits, or to make an unauthorized fix.
---

# Objective

Establish why the failure occurs and identify the smallest credible repair target
before changing behavior.

Read `references/workflow-coordination.md` when another workflow also
applies.

## Method

1. Capture the exact symptom, error output, environment, and expected behavior.
2. Reproduce with the narrowest stable command or sequence. If reproduction is
   intermittent, gather timing and state evidence instead of guessing.
3. Inspect recent relevant changes, working examples, callers, configuration, and
   component boundaries. Trace the bad value or state backward to its source.
4. Compare a known-good path, earlier revision, working caller, or controlled
   environment when one exists. Treat timing with a change as a lead, not proof of
   causation.
5. State one falsifiable cause hypothesis, its supporting observations, and the
   smallest observation that would reject it.
6. Test one variable at a time with the smallest safe probe. Keep a compact
   symptom → hypothesis → probe → result record when multiple probes are needed.
   Do not mix repair,
   refactoring, dependency upgrades, and diagnostics.
7. When evidence confirms the cause, hand off the reproduction, causal chain,
   affected scope, and smallest repair target. Implement only when the user also
   authorized a fix.

Use `test-writer` for an executable regression reproduction when stable observable
behavior exists. After an authorized repair, use `diff-judge` for the actual patch
and `verification-gate` for the final acceptance verdict.

## Evidence

Record the reproduction command or path, observed output, relevant changed state,
hypothesis, probe result, and remaining uncertainty. Distinguish a confirmed cause
from a correlation or plausible explanation.

## Boundaries

- Do not expose secret values while inspecting environment or configuration.
- Do not propose a repair before reproducing or otherwise localizing the failure.
- Do not broaden a diagnostic probe into cleanup, upgrades, or unrelated fixes.
- Do not treat a changed error message as proof that the underlying failure is fixed.
- Inspect targeted history read-only only when it can discriminate a regression
  hypothesis. Do not run `git bisect`, switch branches, or change a worktree unless
  separately authorized and an isolated clean target is available.
- After three materially different failed repair attempts, stop and re-evaluate the
  underlying design or missing evidence before attempting another change.

## Output

Return the observed failure, reproduction, evidence chain, cause verdict
(`confirmed`, `probable`, `unresolved`, or `blocked`), smallest repair target, and
the next proof required.
