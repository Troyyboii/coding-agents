---
name: test-writer
description: >-
  Add or repair focused automated tests for an identified behavior, bug, interface, or
  change using the repository's existing test conventions. Use when the user explicitly
  asks for tests, an authorized plan requires test-first regression evidence, or a
  confirmed bug must be reproduced executably before repair. Do not use for
  documentation-only work, implementation that explicitly excludes tests, broad quality audits, or
  claims that existing tests passed.
---
# Test Writer

Read `../../references/workflow-coordination.md` when tests feed a debugging,
implementation, review, or verification phase.

## Method

- Inspect the behavior under test, its callers, existing tests, fixtures, and test commands.
- Before generating a non-trivial test, state a concise scenario ledger: setup or
  fixture, action or input, observable expected outcome, material boundary or
  negative condition, and the owning test surface. This is a decision aid, not a
  second requirements document.
- Choose the lowest-cost test level that can prove the behavior. Add broader integration or end-to-end coverage only when unit boundaries cannot establish the claim.
- Reproduce confirmed bugs with a failing test when practical, then keep the test focused on observable behavior.
- For test-first work, run the narrow test before implementation and confirm it fails
  for the intended missing behavior rather than setup, syntax, or environment errors.
  Hand that evidence to the authorized builder; this skill does not own production
  changes.
- Cover the main success path, material errors, boundaries, and regression cases without duplicating implementation details.
- Keep tests deterministic, isolated, fast enough for their intended suite, and consistent with local naming and fixture patterns.
- Run the narrow test first, then the relevant containing suite. Report exact commands and results.
- After implementation, rerun the same narrow test and containing suite. Preserve both
  the failing and passing observations when claiming a regression test was proven.

If a generated test fails because its expectation, selector, fixture, or the product
contract is unclear, reconcile the scenario against observed behavior and the
authoritative requirement. Do not silently "heal" a test merely to regain green.

## Contract Tests

- For configuration, plugins, skills, schemas, or generated files, validate the public contract and source-of-truth relationship rather than testing prose mechanically.
- For generators, test normal generation, check mode, malformed input, and drift detection.
- For command wrappers, assert exit status, bounded output, and failure behavior without depending on machine-specific state.

## Boundaries

- Do not add speculative tests for behavior the product does not promise.
- Do not rewrite production code merely to satisfy a brittle test unless the user authorized the implementation change.
- Do not force test-first work onto prose, generated output, exploratory prototypes,
  or configuration changes where no stable executable behavior can be asserted.
- Do not claim coverage improvement without measuring it.
- Preserve unrelated tests and fixtures, including failures that predate the requested change.
