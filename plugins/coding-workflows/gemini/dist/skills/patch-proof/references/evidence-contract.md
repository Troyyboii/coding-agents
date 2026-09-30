# Evidence Contract

Use this compact record when a task needs durable proof rather than a short
answer. It is a reporting pattern, not a database, hook, or requirement to create
files.

| Field | Record |
| --- | --- |
| Claim | The precise behaviour, fact, or boundary being established. |
| Evidence kind | `observed`, `executed`, `inferred`, or `unverified`. |
| Source or artifact | URL, file and line, command, test name, screenshot, log, or browser state. |
| Result | What the evidence actually showed, including relevant exit status. |
| Freshness and environment | Version, commit, URL, viewport, account role, date, or other state that limits reuse. |
| Limitation | What this evidence cannot establish. |
| Acceptance status | `verified`, `failed`, `not checked`, or `blocked` when the task has acceptance criteria. |

## Rules

- A search-result snippet, agent summary, configuration entry, or passing command
  alone is a lead, not automatic proof of a broader claim.
- Reuse evidence only when the artifact and relevant environment have not changed.
  Rerun or reinspect after a material edit, deployment, or state transition.
- Keep source facts, local observations, and deductions separate. Cite sources next
  to the claims they support.
- Record a meaningful absence as `not found in the inspected scope`; do not turn it
  into proof that it does not exist elsewhere.
- Do not capture credentials, private payloads, cookies, or sensitive test data in
  an evidence record.

## Smallest useful forms

For an ordinary answer, a sentence can be enough: “`npm test` exited 0 on commit
`abc123`; it did not exercise the browser flow.” For a multi-source investigation,
use one row per claim. Do not produce a ceremonial ledger when the task has no
decision that depends on it.
