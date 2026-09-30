# Checkpoint Schema

`scripts/checkpoint.py capture` produces this document; `compare` reads it.
Schema `coding-workflows/session-checkpoint`, version 1.

## Captured by the helper

| Field | Content |
| --- | --- |
| `repository.root_commits` | Root commit IDs; the identity check. |
| `repository.remotes` | Remote URLs with any user information stripped. |
| `repository.toplevel_name` | Directory name, for display only. |
| `git.branch`, `git.head` | Current branch (null when detached) and HEAD commit. |
| `git.upstream`, `git.upstream_head` | Upstream branch and the local remote-tracking commit. The helper never fetches. |
| `worktree.changed`, `worktree.untracked` | Paths with Git status and a SHA-256 of current content (null for deleted or very large files); at most 500 paths, with `truncated` set when more exist. |
| `created_at` | UTC time of capture, for display only. Never used to judge freshness. |

When no Git repository exists, `repository`, `git`, and `worktree` are null and
`freshness` says the checkpoint is unverifiable.

## Written by the agent (`--narrative` JSON)

| Field | Content |
| --- | --- |
| `goal`, `success_condition` | What the session is for and how completion is judged. |
| `completed` | Finished steps, one line each. |
| `decisions` | Objects with `decision`, `reason`, and `evidence`. |
| `evidence` | Objects with `claim`, `kind` (`observed`, `executed`, `inferred`, `unverified`), `source`, and `result` (at most 300 characters). |
| `unrun_checks` | Checks that were planned but not run. |
| `pending_authorization` | Actions awaiting the user's decision. |
| `blockers` | What stops progress, and who can unblock it. |
| `next_actions` | The next concrete steps. |

Never include command output, logs, credentials, tokens, private URLs, or
customer data. The helper refuses to write a narrative that matches a secret
signature and names only the field.

## Freshness from `compare`

| State | Meaning |
| --- | --- |
| `current` | Same repository, branch, HEAD, upstream commit, and changed-file contents. |
| `advanced` | HEAD descends from the checkpoint commit; the new commits are listed. |
| `diverged` | HEAD does not descend from the checkpoint commit, or that commit no longer exists. |
| `branch-changed` | A different branch is checked out. |
| `upstream-moved` | The local remote-tracking commit changed. |
| `worktree-drift` | Changed files were modified again, became clean, or new files changed. |
| `different-repository` | No shared root commit. Stop. |
| `unverifiable` | The checkpoint has no repository state to compare. |

Any state other than `current` means evidence recorded in the checkpoint is not
checked for the current state until rerun.
