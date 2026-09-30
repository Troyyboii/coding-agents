---
name: live-research
description: >-
  Research current technical, library, framework, OpenAI, Codex, or repository facts
  using authoritative live documentation and source-backed tools. Use when freshness,
  version-specific API details, external repository state, or direct citations matter.
  Prefer Context7 for library documentation, official OpenAI documentation for OpenAI
  products, and GitHub sources for repository facts. Do not use for ordinary coding
  from known local context, stale memory, or unsupported third-party claims. Use
  dependency-risk to decide whether depending on a package is acceptable.
---

# Technical Reconnaissance

Answer the decision, not the first search result. Use the narrowest authoritative
source that can establish each material claim. Read
`../../references/evidence-contract.md` when the result will guide a design,
dependency, migration, ecosystem comparison, or implementation choice.

## Research loop

1. State the decision or factual question, the required freshness, and the claim
   types that matter: behaviour, compatibility, security, cost, maintenance,
   license, or operational availability.
2. Ground local claims locally first. Identify the pinned dependency/version, actual
   call site, configuration, test, or observed failure before researching a general
   answer to a repository-specific question.
3. Choose source lanes deliberately:
   - **Framework/library behaviour:** Context7 or versioned official documentation.
   - **OpenAI/Codex behaviour:** current official OpenAI documentation.
   - **Repository, release, issue, or implementation fact:** the project's primary
     repository, selected ref, release notes, and the actual relevant source file.
   - **Ecosystem comparison:** independent primary repositories or official docs;
     use articles and search summaries only to discover candidates.
4. For a promising repository, inspect the precise files that implement the claimed
   mechanism—such as a `SKILL.md`, evaluator, test, config, workflow, or source
   module—not just its README. Check the applicable license before substantial reuse.
5. Extract claim-to-source evidence. Separate source statement, direct observation,
   inference, and unresolved conflict. Seek a second independent source only when it
   could change a consequential decision; do not create fake triangulation from
   mirrors or copied marketing.
6. Stop when the answer is decision-complete or new credible sources are materially
   repetitive. Say what was not inspected rather than continuing a link harvest.

## Ecosystem-recon output

When comparing methods, provide a compact candidate ledger: project and direct
source URL, specific files inspected, mechanism, fit to the current system,
implementation and maintenance cost, overlap, license/reuse note, and one verdict:
`ADAPT NOW`, `MERGE INTO EXISTING SKILL`, `DOCUMENT FOR LATER`, or `SKIP`.
Explain the mechanism in original local language. Do not vendor prompts, scripts, or
distinctive prose merely because a license permits it.

## Capability branches

- Prefer Context7 when it is available for framework documentation, but use official
  versioned docs or primary repository files when it is not.
- If search, GitHub, browser, or a connector is unavailable or unauthenticated,
  use the remaining authoritative source if possible and mark the gap. Registration
  or configuration never proves a tool is callable.
- When sources disagree on a consequential point, report the disagreement, source
  dates or versions, and the decision that remains blocked. Do not average them.

## Boundaries

- Do not expose API keys, authorization headers, cookies, or credential-bearing config.
- Do not install, authenticate, publish, deploy, or change external state without
  explicit authorization.
- Do not present generated documentation, search snippets, or model memory as
  authoritative when a current primary source is available.
- Do not turn ordinary local implementation into research theatre when the needed
  convention is already observed in the repository.
