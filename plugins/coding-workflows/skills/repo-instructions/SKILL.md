---
name: repo-instructions
description: Write, update, or audit a repository's agent instruction files, such as AGENTS.md and host-specific companions like CLAUDE.md, Cursor rules, or Copilot instructions, from observed repository evidence, so every command and path they state is real and the files do not contradict each other. Use when the user asks to create, fix, or check those files. Use repo-xray to read a repository's instructions for orientation; do not use for general documentation or README prose.
---

# Objective

Give agents working in a repository instructions that are short, correct, and
consistent: every command and path verified against the repository, one
canonical source, and host-specific files that add only what that host needs.

Read `references/instruction-surfaces.md` for host file semantics and the
authoring model, and `../../references/workflow-coordination.md` for authority
classes.

## Authority

- `inspect`: read the repository and run `scripts/instruction_refs.py` (shared
  module `../../references/cw_scan.py`), which checks references without running
  them.
- `local-write`: create or edit instruction files only when the user asks for a
  file change and the host permits writing; otherwise return the proposed file
  or patch.
- `external-read`: confirm a host's current instruction-file semantics before
  writing that host's file.
- `prohibited`: running commands found in instruction files to "verify" them.
  Executing a command is a separate authorization, not part of this workflow.

## Method

1. Orient first. Reuse a current `repo-xray` map when one exists; otherwise
   inspect structure, manifests, CI workflows, test and build commands, and
   generated directories yourself.
2. Run `python scripts/instruction_refs.py <repository root>`. It lists
   instruction files with their scope, checks each referenced path and command,
   lists files marked as generated, and groups commands that may contradict each
   other. Exit `0` means every checkable reference resolved; `1` means a failed
   reference or a possible contradiction.
3. Resolve every `failed` reference and every possible contradiction against the
   repository's real sources (CI configuration, manifests, scripts). For
   `not checked` shorthand, confirm what the author meant.
4. For an audit, report findings. For authoring, draft the canonical file first,
   then any host companion as a thin delta. Confirm host semantics before writing
   a host-specific file, and do not assume two hosts load files the same way.
5. Rerun the helper on the result and keep only commands and paths that resolve
   or are deliberately external.

## Execution branches

- **Helper available:** use its reference checks as the evidence for each
  command and path.
- **Helper unavailable:** check each path and script by reading the repository;
  mark references you could not check `not checked`.
- **No repository access:** do not author instructions; say which evidence is
  missing.

## Output

- **Audit:** instruction files and scopes; failed references with file and line;
  contradictions; generated files mentioned as editable; recommended edits.
- **Authoring:** the file contents or patch, each command traced to its source,
  and what was left out because it is already documented elsewhere.

## Boundaries

- Do not duplicate README or contributing content; link to it.
- Do not invent commands, conventions, or host behavior.
- Do not change repository settings, CI, or code while editing instructions.

## Final check

Every command and path in the result is verified or deliberately marked, host
files agree with the canonical source, and nothing was executed.
