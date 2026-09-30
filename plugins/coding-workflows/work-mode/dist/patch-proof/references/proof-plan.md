# Proof Plan and Evidence

`scripts/proof_run.py` reads a plan, prints the exact commands without running
them, and runs them only with `--execute` after the user approves.

## Plan (`coding-workflows/proof-plan`, version 1)

| Field | Rule |
| --- | --- |
| `mode` | `differential` (base versus patched) or `single_revision` (one revision; never called a patch proof). |
| `base.rev` | Any revision name; resolved to a full commit SHA before anything runs. |
| `patched` | `differential` only: `{"rev": ...}`, or `{"diff": <file>, "diff_sha256": <hex>}` applied to base; the hash must match. |
| `setup` | Optional list of `{argv, timeout_s}` run in each workspace before the cases, such as installing dependencies. Show these separately: they often reach the network. |
| `cases` | List of `{id, role, argv, timeout_s, expect}`. `argv` is a list of strings; shell command strings and `sh -c`-style wrappers are rejected. |
| `role` | `differential`: `original_reproduction`, `root_cause_variant`, `legitimate_behavior`. `single_revision`: `reproduction`. |
| `expect` | Per side (`base` and `patched`, or `revision`): `exit` as a number, `zero`, or `nonzero`; `stdout_contains` and `stdout_excludes` markers (stdout and stderr combined). |
| `waiver.root_cause_variant` | Reason when no independent variant exists; required if there is no variant case. |
| `env` | `pass`: extra variable names to pass through; `set`: fixed values. Everything else is withheld from commands. |
| `limits` | `output_bytes` kept per command (head and tail, redacted), `total_timeout_s` for the run. |
| `network` | Must be `not-controlled`: the runner cannot stop commands from using the network. |

A differential plan needs at least one `original_reproduction`, one
`legitimate_behavior`, and one `root_cause_variant` or a waiver.

## Isolation

- Each side is a fresh `git clone --no-checkout --no-hardlinks` into a temporary
  directory outside the repository, checked out detached at the pinned commit,
  with user and system Git configuration ignored so hooks, filters, and
  credential helpers do not run. Submodules and Git LFS objects are not fetched.
- The source repository is only read. The evidence records whether its
  `git status` was identical before and after.
- Each command runs without a shell, in its own process group, under its timeout;
  a timed-out group is terminated. Workspaces are removed afterwards unless
  `--keep-workspaces` is given.

## Evidence (`coding-workflows/proof-evidence`)

Per case and side: exit code, timeout flag, duration, output size and SHA-256,
redacted head and tail, marker results, and whether the expectation was met.

| Case status | Meaning |
| --- | --- |
| `verified` | Expectations met on every side. |
| `failed` | Reason `not-reproduced-on-base` (the proof is invalid), `still-fails`, `regressed`, `baseline-broken`, or `expectation-not-met`. |
| `blocked` | Reason `timeout` or `start-failed`; setup failures block the run. |

The overall result is `verified` only when every original reproduction and
legitimate-behavior case is verified and a root-cause variant is verified or
waived; otherwise `failed`, `blocked`, or `not checked` (no variant and no
waiver). A `single_revision` result is labelled as not a patch proof.
