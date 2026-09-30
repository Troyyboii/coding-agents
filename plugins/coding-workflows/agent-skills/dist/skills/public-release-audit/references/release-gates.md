# Release Gates

Each gate ends as `verified`, `failed`, `not checked`, `blocked`, or
`not applicable`, with the evidence that decided it. `scripts/release_scan.py`
settles the file-level gates; the rest need another workflow, an owner decision,
or platform access.

| Gate | Settled by | `failed` when |
| --- | --- | --- |
| Secrets in tracked files | helper | A format-specific secret signature matches. Generic pattern matches stay `not checked` until a person reviews the listed locations. |
| Secrets in history | helper with `--history` | Same, across added lines in all history. A secret once committed is exposed even if deleted; rotate it. |
| Sensitive files | helper | Private keys, environment files, credential JSON, keystores, or state files are tracked, or were ever added (with `--history`). |
| Files tracked despite ignore rules | helper | Tracked paths match current ignore rules, often committed before the rule existed. |
| Licence | helper | No root licence file, or package metadata declares a different licence. |
| Third-party and vendored material | reviewer | Bundled code, assets, or text lack attribution or redistribution rights. |
| Dependency provenance | `dependency-risk` | Its findings or coverage show unacceptable risk; otherwise cite its result. |
| Generated, large, and debris artifacts | helper | Caches, build debris, or files above the size limit are tracked. |
| Personal data in history | helper with `--history`, then owner | The owner does not accept the author identities, private paths, or internal hosts that would become public. |
| README | helper | No root README. |
| Outsider reproduction | `patch-proof` in `single_revision` mode | Following the documented setup from a clean clone fails. |
| CI exposure when public | `ci-trust-review` | Outsider-reachable paths to code execution or secrets exist. |
| Security policy | helper | No `SECURITY.md` with a reporting route. |
| Contribution and support surfaces | helper, then owner | The owner decides they are needed and they are absent. |
| Release and versioning procedure | helper | Only when the owner requires one for this publication. |
| Platform settings | host tools | Visibility, secret scanning, branch protection, or private vulnerability reporting are not as intended; `blocked` unless inspected. |

A gate that depends on another workflow stays `not checked` until that
workflow's evidence is cited. Never mark a gate `verified` from the absence of a
check.
