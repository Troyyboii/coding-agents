# GitHub Actions Trust Model

A CI finding needs a complete path: an attacker-controlled **source**, reachable
through a **trigger** the attacker can cause, flowing into an execution **sink**,
in a job that holds a **privilege** worth taking. A dangerous-looking keyword
without that path is a hardening note, not a finding.

Primary reference: GitHub's security hardening guide for Actions (linked from
the capability-expansion ledger). Re-check current platform defaults there when a
conclusion depends on them.

## Sources

| Source | Who controls it |
| --- | --- |
| Issue, pull request, comment, review, and discussion titles and bodies | Anyone who can open or comment, including on public repositories, strangers |
| Pull request head ref, label text, head repository contents, commit messages, author names | The pull request author, including forks |
| Code checked out from a pull request head | The pull request author |
| Artifacts and caches written by runs triggered from forks | The fork author |
| `workflow_dispatch` and `workflow_call` inputs | Whoever can dispatch or call; usually write access, lower risk |
| Outputs of earlier steps or jobs | Whatever fed those steps; trace them back |

## Triggers and reachability

| Trigger | Context it runs in |
| --- | --- |
| `pull_request` from a fork | Fork context: read-only token and no repository secrets by default |
| `pull_request_target` | Base repository context with its token and secrets, even for fork pull requests |
| `issue_comment`, `issues`, `discussion`, `pull_request_review*` | Base repository context; any commenter may trigger |
| `workflow_run` | Base repository context, triggered after another workflow, including one started by a fork |
| `push`, `schedule`, `workflow_dispatch` | Require write access or repository control |

Guards such as `if:` checks on author association, labels, or actor narrow
reachability; read them exactly, since a guard on one job does not protect
another.

## Sinks

- `${{ }}` expressions interpolated into `run:` scripts or `actions/github-script`
  `script:` bodies; the expression text becomes code before the shell runs.
- Composite action `run:` steps that interpolate `inputs.*`.
- Untrusted text written to `GITHUB_ENV`, `GITHUB_OUTPUT`, or `GITHUB_PATH`.
- Building, testing, or installing checked-out pull request code in a privileged
  job (install scripts and test code run too).
- Extracting or executing artifacts produced by an untrusted run.
- AI agent steps that receive untrusted text and hold tools, tokens, or write
  access; the text can instruct the agent.

Passing the same value through an `env:` variable and reading it as `"$VAR"` in
the script is not an interpolation sink; the shell treats it as data.

## Privilege

- Explicit `permissions:` at workflow or job level. When absent, the token's
  default is a repository or organization setting; record it as `blocked` unless
  the setting was inspected.
- Secrets referenced by the job, `secrets: inherit` into reusable workflows, and
  environment secrets (protection rules are settings; mark them `blocked` unless
  inspected).
- `actions/checkout` leaves credentials in the workspace unless
  `persist-credentials: false` is set.
- Self-hosted runners persist between jobs and may reach internal networks.

## Cross-file chains

Follow local composite actions (`uses: ./path`) and local reusable workflows
(`uses: ./.github/workflows/file.yml`). A remote action or reusable workflow is
unresolved until its source at the pinned ref is read; say which hop is
unresolved rather than assuming it is safe or unsafe.

## Finding rules

- A finding names the source, the trigger that makes it reachable, every hop to
  the sink with file and line, and the privilege available there.
- Each hop has an evidence kind. Any `inferred` hop caps the finding at
  `Important`; a path with no outsider-reachable source is a hardening note.
- Unpinned third-party actions and missing `persist-credentials: false` are
  hardening notes unless they complete a path.
