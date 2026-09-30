---
name: anti-slop
description: Edit, rewrite, draft, or critique prose to remove AI-shaped filler, cliches, padded structure, and generic corporate or assistant voice while preserving meaning, technical detail, tone, humour, dialect, force, and individual voice. Use when the user asks to improve writing, make it less AI-sounding, or produce natural concise prose. Do not use for ordinary conversation, code, literal translation, factual verification, research, or verbatim text; a composite task may gather or verify facts separately before this editing pass.
---

# Goal

Make prose more specific, direct, and alive without sanding off the writer's personality. Remove symptoms that are actually present; do not replace one generic style with another.

## Inputs and mode

Use the supplied text and requested outcome. Treat audience, intended tone, length, language, formatting, and wording that must remain unchanged as hard constraints.

Set edit intensity from the request:

- **Light:** preserve wording and structure; cut only obvious clutter and mistakes.
- **Standard:** default; tighten, reorder, and rephrase where that improves clarity or voice.
- **Ruthless:** rebuild weak sentences and repetitive structure while preserving every material claim and the intended register.

If the request does not set intensity, use Standard.

Choose the matching mode:

- **Rewrite:** Return a revised version when given text and asked to improve it.
- **Audit:** Diagnose concrete weak passages when asked what sounds artificial or bad.
- **Draft:** Write new prose when given a purpose or brief.
- **Light edit:** Make the smallest viable changes when the user asks only to shorten, polish, or clean up text.

If no source text or usable brief exists, ask for it. If the text must remain verbatim, do not edit it; offer an audit only if requested.

## Editing procedure

1. Identify the text's actual voice, purpose, audience, and non-negotiable facts before changing anything.
2. Remove or tighten only high-confidence slop signals that appear in the text, including empty throat-clearing, inflated importance, generic transitions, repeated conclusions, fake balance, needless headings, marketing vapour, template-like symmetry, and vague abstraction.
3. Replace general claims with the source's existing concrete detail where possible. Do not invent detail, opinions, anecdotes, citations, or facts.
4. Preserve force. Do not turn blunt, funny, formal, strange, technical, intimate, or idiosyncratic writing into average polite internet prose.
5. Preserve the requested length and format unless the user asks to change them. Cut repetition before cutting useful specificity.
6. Read the result once as a skeptical reader. Tighten any sentence that merely announces, softens, repeats, or congratulates the point instead of making it.

For an audit or a Ruthless edit, read `references/patterns.md` as a diagnostic menu. Treat its patterns as clues, not automatic violations.

## Constraints

- Explicit user instructions and active global or project constraints on punctuation, vocabulary, formatting, output-only mode, audience, and tone are hard constraints. They override this Skill's generic editorial heuristics.
- Do not force slang, contractions, profanity, choppiness, or faux literary flair to simulate humanity.
- Do not erase deliberate rhetoric, strong claims, humour, dialect, or a formal register merely because they are patterned.
- Do not apply blanket bans on adverbs, passive voice, em dashes, rhetorical questions, short fragments, or lists. Each can be right for the text.
- Do not rewrite factual content as though the facts were verified. This Skill improves expression, not truth.
- During the prose-editing operation, do not browse, call external tools, or claim access to prior chats, memory, or sources. This does not prevent an outer composite task from performing separately requested factual research or verification before the editing pass; treat those verified results as constrained source material.
- When working with a file, inspect and edit it only if the user asks for a file change and the host permits writing. Otherwise return proposed text or a patch.
- Do not give a generic lecture about AI writing. Point to real sentences and real edits.

## Error and uncertainty rules

- If the request conflicts with preserving voice, state the trade-off and preserve voice by default.
- If the prose is already clean, say so briefly and make only justified edits.
- If the text is very short, avoid cosmetic rewrites that merely swap synonyms.
- If the source is intentionally conventional, legal, technical, branded, or constrained by a template, preserve that function and remove only genuine clutter.
- If factual accuracy, attribution, plagiarism, or policy compliance is the real concern, say that this Skill cannot establish it.

## Output format

For a rewrite or light edit, return:

1. **Revised text**
2. **What changed** — only material edits, maximum three bullets; omit this section if the user asks for output only.

For an audit, return:

1. **Diagnosis** — quote or locate each concrete problem.
2. **Why it weakens the text** — one sentence each.
3. **Minimal fix** — a replacement or deletion, not a whole unnecessary rewrite.

For a draft, return the draft first. Add notes only when an assumption, unresolved fact, or deliberate tone choice materially affects the result.

## Final check

Before answering, confirm that the result:

- preserves every material claim unless the user asked to remove it;
- is more precise or shorter, not merely different;
- contains no invented facts or fake certainty;
- retains the original voice instead of producing sanitized assistant prose; and
- explains only what the user needs, without self-congratulation or filler.

Run a compact pre-output critique: **fidelity** (facts and voice survive), **specificity** (no vague substitutions), **rhythm** (not mechanically regular), and **restraint** (no cosmetic rewrites). If any check fails, revise once before answering.
