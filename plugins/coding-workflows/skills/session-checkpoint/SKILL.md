---
name: session-checkpoint
description: Save or resume an explicit coding-session checkpoint that records repository identity, branch, HEAD, changed files with content hashes, decisions, evidence, unrun checks, pending authorization, blockers, and next actions, and check on resume whether the repository has moved on. Use only when the user explicitly asks to save a checkpoint, save progress to resume later, or resume from a checkpoint. Use context-first to continue work when no checkpoint is identified.
---

# Objective

Give the user a save point they can trust on resume: a compact record of where
the work stands, checked against the real repository before anyone acts on it.

Read `references/checkpoint-schema.md` for fields and freshness states, and
`../../references/evidence-contract.md` for evidence kinds.

## When to run

Only on an explicit request to save, checkpoint, or resume. Never suggest or
create checkpoints during ordinary work, and never capture in the background.

## Authority

- `inspect`: run `scripts/checkpoint.py` (shared module
  `../../references/cw_scan.py`), which runs read-only Git commands only.
- `local-write`: write the checkpoint file only when the user wants it persisted
  and the host permits writing. Printing it is the default.
- `prohibited`: hooks, automatic capture, editing ignore files, committing the
  checkpoint, and storing command output, logs, or secrets.

## Save

1. Write the narrative as JSON: goal and success condition, completed steps,
   decisions with reasons, evidence with its kind and a short result, unrun
   checks, pending authorization, blockers, and next actions. Summarize; never
   paste command output.
2. Run `python scripts/checkpoint.py capture --narrative <file>`. It prints the
   checkpoint. It refuses (exit `3`) if the narrative contains secret-shaped
   text; remove it and capture again.
3. To persist, suggest `.agent-checkpoints/<name>.json` and write it only with
   the user's approval via `--output`. The helper warns when the path is tracked
   or not ignored; tell the user, and leave ignore rules to them.

## Resume

1. Run `python scripts/checkpoint.py compare <checkpoint>` before acting.
2. `current`: continue from `next_actions`.
3. Any other state: report what moved (new commits, changed files, branch, or
   upstream), treat evidence in the checkpoint as `not checked` until rerun, and
   re-inspect the drifted paths. When the drift or the narrative conflicts with
   the repository in ways that change the plan, hand the comparison to
   `context-first` to reconcile; do not loop back here.
4. `different-repository`: stop and say so.
5. `pending_authorization` records what was waiting for a decision. It is never
   authorization now; ask again.

## Execution branches

- **No Git repository:** save a narrative-only checkpoint marked unverifiable;
  on resume, say freshness cannot be checked.
- **Helper unavailable:** record branch, HEAD, and changed paths from Git output
  in the same fields, and compare them by hand on resume; content hashes are
  `not checked`.
- **Writing not permitted:** print the checkpoint for the user to keep.

## Output

- **Save:** the checkpoint JSON or the path it was written to, and any tracked
  or not-ignored warning.
- **Resume:** the freshness states, what changed, which evidence needs rerunning,
  and the next action.

## Final check

Nothing was captured without a request, nothing secret was stored, and resumed
work started from the comparison, not from the checkpoint alone.
