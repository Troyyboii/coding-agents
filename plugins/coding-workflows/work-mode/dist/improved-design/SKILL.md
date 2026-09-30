---
name: improved-design
description: Critique a product interface, screen, flow, landing page, or visual direction and prioritize concrete design recommendations. Use when the user asks what looks wrong, why a design underperforms, what to preserve, or which UI/UX changes matter most. Do not use for generic code review, and do not edit code, create mockups, or silently turn critique into implementation without a separate request and host write authorization.
---

# Objective

Turn available interface evidence into a prioritized critique that improves comprehension, hierarchy, trust, and use without inventing a fashionable redesign for its own sake.

## Method

1. Inspect the supplied screen, prototype, code, or description. State the evidence available and do not pretend to see an unprovided interface.
2. Infer the primary user task and identify the screen's visual and interaction hierarchy: what is noticed first, what is actionable, and what competes.
3. Check hierarchy, spacing, typography, contrast, grouping, controls, states, copy, responsiveness, and consistency against that task.
4. Separate real friction from personal taste. Preserve deliberate character when it does not obstruct use.
5. Recommend the smallest high-leverage changes first. Explain the mechanism, expected effect, and priority rather than merely naming an aesthetic.

## Output

Return, in order:

1. **Verdict** — one plain-language statement of what works and what most limits the result.
2. **Priority fixes** — up to five items, each with evidence, expected effect, and concrete change.
3. **Keep** — elements that should not be "improved" away.
4. **Optional direction** — only when useful: a compact visual direction or implementation note for a separately authorized implementation pass.

## Boundaries

- Do not invent accessibility compliance, screenshots, user research, conversion data, or live behaviour.
- Do not confuse more decoration, motion, gradients, cards, or rounded corners with improvement.
- If a brand, platform guideline, or target device is absent and would change the recommendation, label the assumption.
- Treat critique and implementation as separate scopes. If the user also requests implementation and the host authorizes writing, finish or hand off the prioritized recommendations before making changes under that separate scope.

## Final check

Ensure every recommendation is tied to an observed issue or explicit assumption, has an expected user-facing effect, and is ranked by impact rather than novelty.
