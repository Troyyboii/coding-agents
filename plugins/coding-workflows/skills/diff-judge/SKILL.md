---
name: diff-judge
description: Review an actual proposed or completed code or configuration diff, or technically evaluate review feedback against that diff, for correctness, scope, regressions, security, and verification gaps. Use when the user identifies a patch, commit, pull request, staged change, working-tree diff, or concrete review comments. Use repo-xray for repository orientation; do not use to make the change, accept feedback performatively, or review a whole repository when no diff exists. Use spec-trace for per-requirement conformance to a specification.
---

# Objective

Judge the actual change rather than its intentions. Find defects that matter, distinguish blockers from nits, and keep the review tied to the requested scope.

Read `../../references/workflow-coordination.md` for builder, reviewer, and verifier
authority boundaries.

## Method

1. Require an actual diff. Use a supplied patch or inspect the identified commit, pull request, staged change, or working-tree diff when access is available. If no diff can be obtained, report the missing review artifact instead of reviewing the repository in the abstract.
2. Inspect repository instructions, current status when available, and the complete relevant diff before reaching a verdict.
3. Reconstruct the intended behaviour from the task, changed code, adjacent callers, schemas, configuration, and tests.
4. Select review lenses from the changed surface rather than reciting a universal
   checklist: public/API contracts, data and migrations, authorization/privacy,
   concurrency/state, configuration/deployment, compatibility, generated or secret
   debris, and test adequacy. State the lenses used when they materially affect the
   verdict.
5. Map the change's direct surface—changed contract or symbol, callers/consumers,
   data or configuration boundary, and tests—before claiming an impact is isolated.
   Use targeted history only when it changes the risk judgment.
6. Inspect related code only where the diff requires it. Do not perform a ceremonial whole-repo safari.
7. Rank findings by severity and confidence. Do not manufacture comments to look diligent.

When receiving review feedback, read all items, restate only unclear technical
requirements, verify each claim against the current diff and repository constraints,
then accept or reject it with evidence. Conflicting or ambiguous feedback is a stop
condition, not permission to implement a guessed compromise. Fixes require a separate
write-authorized pass and fresh review of the resulting diff.

## Output

Return findings first, ordered by severity:

- **Blocker** — likely incorrect, unsafe, data-damaging, or release-stopping.
- **Important** — material regression or missing behaviour with credible evidence.
- **Minor** — legitimate but non-blocking improvement.

For every finding include: file/path and location, the concrete failure mode, why it happens, and the smallest credible fix. Then add:

1. **Scope verdict** — requested scope met, expanded, or unclear.
2. **Evidence checked** — diff, adjacent files, tests, commands, or runtime proof.
3. **Residual risk** — only unverified areas that could change the shipping decision.

Use `independently corroborated` only when separate evidence paths support the same
finding; a second agent repeating the same diff reading is not independent proof.

If no blocker, important, or minor finding exists, say `No material findings` and still state what you inspected and what remains unverified.

## Boundaries

- Do not modify, stage, commit, reset, or publish anything unless separately asked.
- Keep review independent from building where practical. A builder's summary is not a
  review artifact, and agreement is not evidence that a finding is correct.
- Do not call code correct because it looks plausible; name the evidence.
- Do not treat style preferences as defects unless they create a real maintenance, correctness, or consistency cost.
- Do not expose secrets contained in a diff. Flag their presence without reproducing values.
- Do not expand a focused diff review into a general repository audit merely to produce more findings.

## Final check

Ensure each finding is actionable, grounded in the diff and surrounding code, and proportionate to actual risk.
