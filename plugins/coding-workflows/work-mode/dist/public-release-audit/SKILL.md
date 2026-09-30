---
name: public-release-audit
description: Audit whether a repository is ready to be made public or open-sourced, read-only, across secrets in files and history, sensitive files, licence, vendored material, dependency and CI exposure, artifacts, personal data, documentation, security policy, and release procedure, reporting each gate as verified, failed, not checked, blocked, or not applicable. Use when the user asks if a repository is ready to publish. Never publish or change visibility; use verification-gate to confirm fixes are done.
---

# Objective

Tell the owner what would go wrong if this repository became public today, gate
by gate, with the evidence behind each answer and nothing changed.

Read `references/release-gates.md` for the gates, `references/audit-coverage.md`
for severities and secret handling, and `references/workflow-coordination.md`
for authority classes.

## Authority

- `inspect`: read the repository and run `scripts/release_scan.py` (shared module
  `references/cw_scan.py`), which runs read-only Git commands only.
- `external-read`: inspect platform settings with host tools when the user
  permits.
- `exec-test`: only through `patch-proof` in `single_revision` mode, for the
  outsider-reproduction gate, after the user approves its plan.
- `prohibited`: changing visibility, publishing, tagging, releasing, rewriting
  history, rotating or revoking secrets, filing issues, and editing files.

## Method

1. Run `python scripts/release_scan.py <repository>`; add `--history` when the
   user agrees to a full-history scan. It reports gate statuses and secret
   locations (rule, file, line, or commit), never values.
2. Review every secret location in place without copying its value. Format
   signature matches fail the gate; generic pattern matches need your judgment
   (a documentation placeholder is not a secret).
3. Settle the gates the helper cannot: vendored material and attribution, and
   the owner decisions (personal data, contribution surfaces, release procedure).
4. Hand dependency provenance to `dependency-risk` and CI exposure to
   `ci-trust-review`, and cite their results; if not run, those gates stay
   `not checked`.
5. For outsider reproduction, write a `single_revision` plan that follows the
   README from a clean clone and hand it to `patch-proof`; otherwise leave the
   gate `not checked`.
6. Inspect platform settings through host tools if permitted; otherwise `blocked`.

## Execution branches

- **Helper and repository available:** file-level gates settled by evidence.
- **No history scan permitted:** history gates `not checked`.
- **Uploaded archive without Git data:** file gates only from what was uploaded;
  history gates `blocked`.
- **Helper unavailable:** check each file-level gate by hand and mark mechanical
  completeness `not checked (helper not run)`.

## Output

1. **Verdict** — ready, not ready (list the `failed` gates), or undetermined
   (list the consequential `not checked` and `blocked` gates).
2. **Gate table** — gate, status, evidence, owner action.
3. **Secret locations** — rule and location only, with the instruction to rotate
   anything real.
4. **Hand-offs** — which workflow or person settles each open gate.

## Boundaries

- Never print or paraphrase a secret value, part of one, or a fingerprint.
- Never treat a clean current tree as clean history.
- Confirming that later fixes are complete is `verification-gate` work.

## Final check

Every gate has a status and evidence, no secret value appears anywhere, and
nothing in the repository or on the platform was changed.
