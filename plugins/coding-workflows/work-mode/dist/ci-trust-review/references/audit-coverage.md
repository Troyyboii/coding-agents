# Audit Coverage Contract

Use this contract in audit workflows that search for risk: extension supply
audits, dependency risk, CI trust review, and publication readiness. It extends
the shared evidence vocabulary in [evidence-contract.md](./evidence-contract.md);
it does not replace it.

## Coverage per check

Every check an audit claims to cover ends in exactly one state:

| State | Meaning |
| --- | --- |
| `flagged` | The check ran and found at least one finding. |
| `clear` | The check ran over its whole stated scope and found nothing. |
| `not checked (reason)` | The check did not run over its whole scope: outside scope, unsupported format, limit reached, or helper not run. |
| `blocked (reason)` | A named prerequisite prevented the check: no access, no network, no repository, or execution not authorized. |

`clear` means "nothing found in the inspected scope", never "safe". A report
whose checks are all `not checked` or `blocked` has measured nothing and must say
so; it is never a pass.

## Findings

Record each finding with: rule or check, severity, location (file and line, or
the equivalent), evidence kind from the evidence contract, a short redacted
excerpt, and the concrete consequence.

| Severity | Meaning |
| --- | --- |
| `Blocker` | Likely unsafe, credential-exposing, or release-stopping; do not proceed until resolved. |
| `Important` | A material risk with credible evidence that needs a decision or mitigation. |
| `Minor` | A legitimate but non-blocking risk or hygiene issue. |

A finding that depends on an `inferred` step names that step and is at most
`Important`. Contextual matches, such as a dangerous command quoted in
documentation, stay visible but are ranked by the context they appear in.

## Adoption decision

When the audit answers whether to install or depend on something, end with one
decision:

- `reject` — at least one Blocker, or Important findings the user cannot accept;
- `accept with conditions` — named, checkable conditions that address each
  remaining finding;
- `no blocking findings in the inspected scope` — plus the coverage table and
  what was not inspected.

## Secret handling

Report the rule, file, and line of a secret match. Never print the matched value,
a partial value, or a hash or fingerprint that could help confirm it.
