---
name: patch-proof
description: Produce paired before-and-after execution evidence that a fix works by running the same approved commands against a pinned base revision and the pinned patched revision in isolated temporary clones, covering the original reproduction, a root-cause variant, and nearby legitimate behavior. Use when the user asks to prove a bug or vulnerability is fixed against the base revision. Use verification-gate for the overall completion verdict and test-writer to author the tests.
---

# Objective

Replace "the fix looks right" with executed evidence: the failure reproduces on
the base revision, does not reproduce on the patched revision, a variant of the
same root cause is also fixed, and legitimate behavior still works.

Read `references/proof-plan.md` for the plan and evidence formats, and
`references/workflow-coordination.md` for authority classes and the
temporary-clone rule.

## Authority

- `inspect`: read the repository, the fix, and the commands a plan would run;
  validate a plan with `scripts/proof_run.py` (shared module
  `references/cw_scan.py`), which by default prints the plan and runs
  nothing.
- `exec-test`: run the plan with `--execute` only after the user approves the
  exact printed commands. Setup commands that install or download are a separate
  approval because they reach the network. Running code from an untrusted fork
  needs explicit authorization naming that revision.
- `prohibited`: changing the user's working tree, index, branches, or stash;
  running commands the user has not seen; discovering scripts in the repository
  (for example `package.json` scripts) and running them on your own.

## Method

1. Pin the revisions: the base commit that shows the failure and the patched
   commit, or base plus a diff file with its SHA-256.
2. Build the cases:
   - original reproduction: the failing test or command from the report,
     `root-cause-debugging`, or `test-writer`. Reuse a revision-pinned
     fail-then-pass observation from `test-writer` when it already covers this;
   - root-cause variant: a different input that reaches the same cause;
   - legitimate behavior: the nearest valid path that must keep working.
3. Read what each command actually runs (the test file, script, or target)
   before proposing it. Keep argv lists; no shell strings.
4. Run `python scripts/proof_run.py <plan> --repo <repository>` and show the user
   the printed commands, including any setup. Ask for approval.
5. With approval, rerun with `--execute`. Report the result exactly as the
   evidence states it.
6. A `not-reproduced-on-base` case invalidates the proof; fix the reproduction,
   do not reinterpret the result.

## Execution branches

- **Execution approved and available:** run the plan; evidence kind `executed`.
- **Execution not approved:** deliver the validated plan; the claim stays
  `not checked`.
- **No local repository or Git (for example an upload-only host):** write the
  plan from the material available; the claim is `blocked`, and no source
  reading is presented as proof.
- **Browser-visible defect:** use `browser-proof`, against both builds when
  authorized.
- **Single revision only (for example an outsider reproduction handed over by
  `public-release-audit`):** use `single_revision` mode; the result is not a patch
  proof.

## Output

1. **Result** — `verified`, `failed`, `blocked`, or `not checked`, with the
   claim it covers.
2. **Cases** — role, command, base and patched exit codes, markers, status, and
   reason.
3. **Isolation** — pinned commits, source worktree unchanged, cleanup result.
4. **Limits** — network not controlled, submodules and LFS not fetched, and any
   waiver.

## Boundaries

- Do not call source inspection a proof.
- Do not weaken an expectation to make a case pass.
- Hand the evidence to `verification-gate` for the overall completion verdict.

## Final check

Every executed command was approved, both revisions are pinned, and the result
wording matches the evidence exactly.
