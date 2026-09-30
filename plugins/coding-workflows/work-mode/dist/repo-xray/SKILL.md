---
name: repo-xray
description: Orient a code repository read-only by mapping its available contents, governing instructions, and repository state. Use for repository tours, current-state maps, change-location questions, audit-scale orientation, or handoff briefings from a live worktree, remote GitHub repository, or supplied snapshot. Use diff-judge for an actual diff, repo-instructions to write or audit instruction files, and session-checkpoint for a resumable save point; do not use to edit, verify completed work, judge security or publication risk, or infer local Git state from remote or uploaded contents.
---

# Objective

Build a compact factual map of the available repository source so subsequent work starts from observed state instead of memory, pasted snippets, or wishful cartography.

## Method

1. Identify the available source and follow its branch below.
2. Read governing instructions first, including `AGENTS.md`, contribution rules, and relevant local guidance.
3. Identify runtime, package manager, entry points, tests, deployment or configuration surfaces, and the files closest to the requested area.
4. Start with a compact orientation map, then trace only the requested path: entry
   point or public contract → target surface → direct callers or consumers →
   configuration/data boundary → relevant tests. Follow one hop at a time and stop
   once the next change or investigation step is clear.
5. For unfamiliar, legacy, audit-scale, or change-impact requests, add a small
   dossier for the critical path: component or symbol, what it demonstrably does,
   dependencies, evidence location, and open question. Record an absence as “not
   found in the inspected scope,” never as a universal negative.
6. Use history only when it changes the answer: recent targeted commits, blame, or
   a known regression range. Do not perform `git bisect`, switch branches, alter a
   worktree, or contact remotes under this read-only workflow.
7. Use targeted searches rather than dumping the whole tree. Treat generated folders, dependencies, secrets, and unrelated user changes as protected.
8. Separate observed facts from reasonable inferences. Name unavailable or uninspected state.

## Source branches

### Local live worktree

Inspect the repository root, branch, status, remotes, current commit, recent relevant history, tracked shape, and local modifications. Report only values actually observed.

### Remote GitHub repository only

Inspect the repository, selected branch or ref, remote commit, governing files, and relevant contents available through the remote. Mark local working-tree state as unavailable. Do not claim the user's clone is clean, current, or synchronized.

### Uploaded archive or repository snapshot

Map the supplied contents and any included instructions. Mark branch, remotes, Git history, current commit, and uncommitted-change state as unavailable unless the snapshot itself contains reliable evidence for a narrower claim. Never invent them from folder names or file timestamps.

## Output

Return:

1. **Repository snapshot** — source type and the repository, ref, status, remotes, and commit fields that are actually available.
2. **Working map** — relevant directories, entry points, commands, and governing rules.
3. **Path trace** — direct callers, boundaries, tests, and likely change impact only
   when the request needs them.
4. **Change path** — likely files and dependencies for the named task, without editing them.
5. **Risks or blockers** — only material ones, including dirty worktree or missing tool access.

## Boundaries

- Remain read-only. Do not install, build, run unfamiliar scripts, modify configuration, or contact remotes unless separately authorized.
- Do not expose secret values. Report only the presence and role of a secret-bearing file when necessary.
- Do not claim the repository is clean, current, or deployable unless the corresponding live evidence was checked.

## Final check

Make the report useful for the next agent: concrete paths and commands over generic technology labels, and no invented project history.
