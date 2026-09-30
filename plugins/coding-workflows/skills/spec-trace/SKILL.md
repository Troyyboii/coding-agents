---
name: spec-trace
description: Trace an authoritative specification to an implementation, or to a specific patch, requirement by requirement and in reverse, returning a cited verdict per requirement and the undocumented behavior found. Use when the user asks whether code or a patch conforms to a named spec, RFC, PRD, API contract, or standard. Use diff-judge to find defects in a diff when a spec is only context; do not use to write the spec or reconcile conflicting sources.
---

# Objective

Show, requirement by requirement, whether an implementation does what its
authoritative specification says, and what it does that the specification does
not say, with every verdict tied to a citation or a recorded search.

Read `references/trace-matrix.md` for row fields, verdicts, and the JSON shape,
and `../../references/evidence-contract.md` for evidence kinds.

## Authority

- `inspect`: read the specification, code, tests, and configuration in scope.
- `external-read`: read a remote specification; record its version or date.
- `prohibited`: editing code, tests, or the specification. Fixes are a separate,
  authorized pass, reviewed afterwards with `diff-judge`.

## Method

1. Identify the authoritative specification: exact source, version or date, and
   precedence when several documents apply. If sources conflict in a way that
   changes verdicts, stop and hand the conflict to `context-first`.
2. Fix the scope: whole implementation, named components, or a specific patch.
   For a patch, judge only requirements the patch touches or should touch, and
   say so.
3. Extract individually testable requirements. Reuse the specification's IDs;
   otherwise assign stable `R-<section>-<n>`. Quote the text and record normative
   strength.
4. For each requirement, write the absence criterion before searching: what
   would exist if it were implemented, and where.
5. Search, record what was searched, and map implementation evidence and
   enforcement evidence (tests, runtime checks, schemas) separately.
6. Assign a verdict: `satisfied`, `partial`, `contradicted`, `not found in the
   inspected scope`, `blocked`, or `not checked`.
7. Reverse pass: list material implemented behavior in scope and classify each
   as `documented`, `extension`, `divergent`, or `internal`.
8. Review material divergence: contradicted or partial `must` requirements,
   missing enforcement for `must` requirements, and `divergent` behaviors, ranked
   by consequence.

Large specifications may be traced in batches or limited to sections the user
names; count every requirement not reached as `not checked`.

## Output

1. **Specification** — source, version, precedence, scope.
2. **Matrix** — one row per requirement with citation, verdict, and evidence.
3. **Reverse pass** — implemented behavior not traced to a requirement.
4. **Material divergences** — ranked, each with the requirement ID and location.
5. **Coverage** — requirements total, assessed, and why any were not.

## Boundaries

- Do not report defects unrelated to a requirement; that is `diff-judge` for a
  diff.
- Do not turn a missing search into `not found in the inspected scope`.
- Do not claim runtime conformance from source reading alone; mark such
  verdicts `inferred` unless executed evidence exists.

## Final check

Every row has a citation or a recorded search, every `must` requirement has a
verdict, and the divergence list follows from the matrix.
