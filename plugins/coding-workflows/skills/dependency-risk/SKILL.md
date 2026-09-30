---
name: dependency-risk
description: Decide whether depending on a package is acceptable, or audit a project's existing dependencies, from measured evidence such as install scripts, resolution sources, integrity, lockfile drift, and known advisories, with explicit coverage for what was not checked. Use when the user asks whether to add, keep, or trust a package or wants their lockfile's supply-chain risk. Use live-research for a package's API or current behavior; do not use for GitHub Actions or agent extensions.
---

# Objective

Turn "is this dependency OK?" into a decision backed by measured checks, with
every unmeasured check stated rather than assumed clear.

Read `references/coverage-and-sources.md` for what is measured and how, and
`../../references/audit-coverage.md` for coverage states, severities, and the
adoption decision.

## Authority

- `inspect`: read manifests and lockfiles and run `scripts/dep_inventory.py`
  (shared module `../../references/cw_scan.py`). The helper makes no network
  requests and never prints credential values.
- `external-read`: look up public facts about a package the user named. Sending
  the repository's own package list to an external service, such as an advisory
  batch query, needs the user's authorization first.
- `prohibited`: installing, upgrading, or removing packages, and rewriting
  lockfiles.

## Method

1. Decide the mode: an existing project's dependencies, or a candidate package
   the user is considering.
2. **Project mode:** run `python scripts/dep_inventory.py <project directory>`.
   It reports declared versus resolved, direct versus transitive, install
   scripts, resolution sources, integrity, drift, unsupported ecosystems, and
   coverage. Exit `2` means nothing was measured; never report that as low risk.
3. For advisories, write the query payload with `--emit-osv-query <file>`, ask
   before sending it, then ingest the saved response with `--osv-results <file>`.
   Without authorization or network, advisories stay `not checked`.
4. **Candidate mode:** gather facts from primary sources through the host's
   research tools, following `live-research` source discipline: the package's
   manifest at that version, install scripts, maintainers and release history,
   advisories, license, and source repository. Record each fact's source.
5. Judge each finding in context: an install script in a well-known native
   package differs from one in an unfamiliar package with a new maintainer.
6. Decide: `reject`, `accept with conditions`, or `no blocking findings in the
   inspected scope`.

## Execution branches

- **Helper and lockfile available:** measured local checks, plus advisories when
  authorized.
- **No lockfile:** resolved versions and transitive packages are `blocked`; say
  so and recommend generating one before judging.
- **Unsupported ecosystem:** list it as `not checked`; do not extrapolate from npm.
- **No network or no authorization:** local signals only; advisories and
  registry metadata `not checked`.
- **Helper unavailable:** read the lockfile directly for the same facts and mark
  completeness `not checked (helper not run)`.

## Output

1. **Decision** or **risk summary** — per the adoption decision vocabulary.
2. **Findings** — package, version, check, severity, evidence, why it matters.
3. **Coverage** — each check's state with reasons, plus unsupported ecosystems.
4. **Facts used** — sources and dates for anything external.

## Boundaries

- Do not use this for GitHub Actions `uses:` references (`ci-trust-review`) or
  agent extensions (`skill-supply-audit`).
- Do not install anything to "see what happens".
- Do not print tokens found in `.npmrc` or elsewhere; report the location only.

## Final check

Every check is `flagged`, `clear`, `not checked`, or `blocked` with a reason, and
the decision is no stronger than the checks that actually ran.
