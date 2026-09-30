---
name: browser-proof
description: Verify a live web interface or browser-based user flow with direct browser evidence after a change or before a completion claim. Use when the user asks to check a live page, exercise a UI flow, confirm a form, reproduce a visual bug, or prove an interface path works. Use verification-gate for broader completion synthesis; do not use for source-only review, cross-browser claims from one run, or unapproved production changes.
---

# Objective

Replace "it should work" with observable browser evidence while keeping the test tied to the user's actual claim.

## Method

1. Convert the claimed behaviour into a short path: starting URL or state, user
   action, expected visible result, and any relevant viewport, test-data, or account
   state. Do not use or expose real customer data when a safe test state is available.
2. Confirm browser access and the target environment. Treat production, authenticated, paid, destructive, or irreversible actions as a stop point until explicitly authorized.
3. Execute the narrowest representative path. Observe rendered UI, navigation, errors, loading, data persistence, and responsive state as relevant.
4. Capture a proof pack proportionate to the claim: URL, viewport, rendered visual
   state, semantic or accessibility snapshot/assertion when available, console or
   network error when relevant, and a screenshot only when it adds proof. After a
   meaningful action or state transition, take a fresh snapshot or observation; do
   not treat an earlier page state as proof of the result.
5. Retry once only when a transient loading or interaction failure is plausible. Do not disguise a flaky result as a pass.

## Capability branches

- **Browser available:** Execute the narrow path and report direct observations.
- **Target server unavailable:** Record the target and observed connection or server failure, return `blocked`, and do not substitute source inspection for browser proof.
- **Authentication unavailable:** Exercise only relevant public states. Mark protected steps blocked without requesting, exposing, or inventing credentials.
- **Production or destructive action:** Stop before the consequential action until the user explicitly authorizes it. If authorization is absent, report the path as blocked rather than performing a safer-looking substitute.
- **Browser capability unavailable:** Return `blocked` and state which browser capability is missing. Code, screenshots, or descriptions may inform a separate review but cannot prove a live flow.

## Output

Return:

1. **Verdict** — pass, fail, blocked, or partially verified.
2. **Path tested** — start state, actions, expected result, observed result.
3. **Evidence** — URLs, visible states, relevant error text, and screenshots where useful.
4. **Limits** — viewport, account role, environment, untested branches, or access constraints.

When the request claims responsive behavior, test the named viewports or state that
responsive coverage was not exercised. When the request is exploratory QA rather
than proof of one named flow, agree the exploration scope separately; do not report
an informal browse as deterministic verification.

## Boundaries

- Do not claim cross-browser, mobile-device, accessibility, performance, security, or backend coverage from one browser pass.
- Do not submit forms, alter data, purchase, publish, delete, or send anything without explicit authorization.
- Do not invent browser evidence from source code or a screenshot.
- Keep one tested path distinct from broader device, accessibility, security, backend, or performance claims.

## Final check

Ensure the verdict follows directly from the recorded path and that the report makes clear exactly what was and was not exercised.
