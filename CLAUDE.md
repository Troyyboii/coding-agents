# Claude Code Instructions

This repository's operating rules are [AGENTS.md](./AGENTS.md) and
[WORKFLOWS.md](./WORKFLOWS.md). Read both before making a change. They govern Claude
sessions the same way they govern Codex sessions: inspect before acting, preserve
unrelated work, validate before claiming completion, and never commit, push, publish, or
install into a user profile without explicit authorization.

## Claude-specific surfaces

- The `coding-workflows` skills are available as a local Claude Code plugin, not a
  generated copy. `.claude-plugin/marketplace.json` at the repository root declares the
  repository as a marketplace; `plugins/coding-workflows/.claude-plugin/plugin.json` is the
  plugin manifest. Both point at the same `plugins/coding-workflows/skills/` tree the Codex
  plugin uses — there is no separate Claude skill source to keep in sync.
- Installing the `coding-workflows` plugin distributes only the canonical skills (with their
  bundled helper scripts and the shared references they name).
  `.claude/agents/reviewer.md` and `.claude/agents/verifier.md` are project-scoped
  subagents that belong to this checkout, not to the plugin; they are not installed into
  another repository by installing the plugin there, matching the equally project-scoped
  `.codex/agents/*.toml` agents. They mirror those Codex agents' purpose and read-only
  boundary: their `tools:` list omits `Edit`, `Write`, `NotebookEdit`, and `Bash`, since
  Claude Code has no `sandbox_mode = "read-only"` equivalent; that omission is the
  enforced boundary.
- See [docs/claude-code.md](./docs/claude-code.md) for the full adapter contract,
  validation commands, and what is deliberately not used.
- claude.ai Custom Skills distribution is a separate, fourth surface:
  `scripts/package-claude-app.py` generates one deterministic ZIP per active canonical
  skill under `plugins/coding-workflows/claude-app/dist/`, from the same `skills/` tree
  the Claude Code plugin and Codex plugin use. See [docs/claude-app.md](./docs/claude-app.md)
  for the package contract, validation commands, and the account-side upload state this
  repository cannot verify.

## Working directory

Resolve the live repository root (for example with `git rev-parse --show-toplevel`) before
acting, and operate inside that repository. Do not move, clean, or modify files outside the
resolved repository root unless the task explicitly authorizes it.
