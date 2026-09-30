---
name: verification-gate
description: Synthesize final evidence for whether completed coding, repository, configuration, document, or product work meets its acceptance claims. Use after implementation when the user asks to verify, prove, confirm, validate, or audit completion before handoff, commit, deploy, or submission. When the request is solely a diff review, browser flow, repository orientation, paired before-and-after fix proof, or publication readiness, use diff-judge, browser-proof, repo-xray, patch-proof, or public-release-audit respectively; compose their evidence when useful, but do not replace their focused procedures or implement the work.
---

# Objective

Make completion claims earned. Match the proof to the claim, distinguish what was checked from what was merely inferred, and expose the smallest remaining gap.

Read `../../references/workflow-coordination.md` when composing evidence from other
skills or delegated work.

## Method

1. Restate the requested outcome as observable acceptance checks.
2. Reuse focused evidence already produced by `diff-judge`, `browser-proof`, or `repo-xray` when it is current and directly supports an acceptance check.
3. Classify each claim before choosing proof: scope/artifact, behavior, runtime/UI,
   configuration, publication, or security boundary. Inspect the remaining relevant
   artifact, repository state, output, logs, configuration, or live surface before
   declaring anything. Evidence must be fresh enough to describe the current artifact;
   rerun the proving command after material changes.
4. Select proportionate evidence: tests for behaviour, diff inspection for scope, build or lint for integrity, browser evidence for UI, and remote checks for published state. Do not repeat a focused skill's complete procedure merely to synthesize its result.
5. Run only safe, relevant checks within the user's authorization. Do not deploy, publish, mutate data, or broaden scope merely to obtain proof.
6. For each material check, record the evidence kind (`observed`, `executed`,
   `inferred`, or `unverified`), command or artifact identity, result, relevant
   environment, and limitation. Then classify the acceptance check as **verified**,
   **failed**, **not checked**, or **blocked**. Never collapse those into a vague green tick.

## Output

Return:

1. **Verdict** — complete, incomplete, blocked, or partially verified.
2. **Evidence table** — acceptance check, evidence, result, and limitation.
3. **Scope state** — changed paths or artifacts, unrelated changes, and secret/generated-debris check where applicable.
4. **Remaining gap** — only concrete unverified or failed items.

When verifying an authorized fix, include both proof that the original failure no
longer reproduces and, where relevant, proof that the nearest legitimate behavior
still works. A changed error message or a single green command does not establish
either claim by itself. Use `patch-proof` evidence when the pre-fix state must be
reproduced from a pinned revision.

## Boundaries

- Do not say a test, build, deployment, clean tree, remote state, or browser flow passed without running or inspecting it.
- Do not manufacture a test plan after the fact as proof that testing happened.
- Do not treat agent reports, old command output, test counts from another tree, or a
  reviewer verdict as direct proof without inspecting the referenced artifact.
- If access, credentials, environment, or a live dependency is unavailable, say exactly that and mark the claim unverified.
- Do not modify files unless the user separately asks for a fix.
- Do not turn a request solely for diff review, browser verification, or repository orientation into a broad completion audit.

## Final check

Ensure the conclusion is no stronger than the strongest evidence and that a reader can tell verified facts from assumptions in seconds.
