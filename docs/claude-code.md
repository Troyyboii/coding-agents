# Coding Workflows for Claude Code

## Repository-proven behavior

`plugins/coding-workflows/skills/` remains the only authored workflow source — the same
skills that back the Codex plugin. Claude Code discovers them as a local plugin, not a
generated or hand-copied package:

- `.claude-plugin/marketplace.json` at the repository root declares this repository as a
  local Claude Code plugin marketplace, analogous to `.agents/plugins/marketplace.json`
  for Codex.
- `plugins/coding-workflows/.claude-plugin/plugin.json` is the Claude plugin manifest, a
  sibling of `.codex-plugin/plugin.json`. It does not declare a `skills` path; Claude Code
  resolves a plugin's skills from its default `skills/` subdirectory, which is the identical
  `plugins/coding-workflows/skills/` tree Codex uses. No skill content is duplicated,
  generated, or rewritten for Claude, so there is nothing that can drift out of sync.
- Each skill's `agents/openai.yaml` remains Codex-only metadata. Claude Code does not read
  it and no `SKILL.md` instructs reading it; it is inert for a Claude session.
- `.claude/agents/reviewer.md` and `.claude/agents/verifier.md` are project-scoped Claude
  subagents that translate `.codex/agents/reviewer.toml` and `verifier.toml`. They keep the
  same name, purpose, trigger, and read-only boundary. Claude Code has no OS-level
  `sandbox_mode = "read-only"` equivalent, so the boundary is enforced by the
  exact `Read`, `Grep`, and `Glob` `tools` allowlist. Practically,
  this means these subagents review a supplied diff or evidence rather than independently
  running `git`, a test suite, or any other command themselves; the invoking session
  gathers that evidence and hands it in.

### Distribution boundary: plugin-distributed skills versus project-scoped agents

Installing the `coding-workflows` plugin in another repository distributes only the
canonical skills under `plugins/coding-workflows/skills/`. It does **not** install
`reviewer` or `verifier` there. Those two subagents live under this checkout's
`.claude/agents/` directory, are scoped to this repository the way any project-level
Claude Code agent is, and are discovered only when Claude Code is run inside this
checkout (or a checkout that copies them in on purpose). This mirrors the Codex side of
the same repository exactly: `.codex/agents/reviewer.toml` and `verifier.toml` are also
project agents, not plugin content, and installing the Codex `coding-workflows` plugin
elsewhere does not bring them along either. The distinction is intentional, not an
oversight: the reviewer and verifier are meant to review *this* repository's own changes,
not to travel with the skill set to unrelated codebases.
- `CLAUDE.md` at the repository root is a short, always-loaded pointer to `AGENTS.md` and
  `WORKFLOWS.md`. It does not duplicate their content or any skill body, matching Anthropic's
  own size guidance for `CLAUDE.md` files.

## Validate the Claude distribution

Run from the repository root:

```powershell
python scripts\validate-repository.py
```

The validator's Claude-specific checks confirm:

- `.claude-plugin/marketplace.json` and `plugins/coding-workflows/.claude-plugin/plugin.json`
  are well-formed closed metadata objects for the one local `coding-workflows` entry,
  and the plugin version matches `plugins/coding-workflows/.codex-plugin/plugin.json`.
- `.claude/agents/reviewer.md` and `verifier.md` have valid frontmatter (`name`,
  `description`, `tools`), their `name` matches the file, and their `tools` list is
  exactly `Read`, `Grep`, and `Glob`.
- The Claude and Codex project-agent sets have identical names and reviewed role,
  purpose, trigger, and read-only authority contracts, so a renamed or contradictory
  project agent cannot exist on only one surface.

If the current environment has a first-party `claude plugin validate <path> [--strict]`
command available, run it against the repository root (validates the marketplace) and
against `plugins/coding-workflows` (validates the plugin) as an additional check. This
repository's own validator does not replace it, and this document does not claim that
command has been run for a specific release — that is a live, environment-specific check.

## Product-documented behavior

Use Claude Code's current plugin documentation for the authoritative command syntax, since
CLI surface can change independently of this repository. As documented at the time this
adapter was written, run from the repository root:

```bash
claude plugin marketplace add .
```

which adds the current checkout as a marketplace regardless of where it happens to be
cloned or what operating system it is on. (A Windows checkout not opened from its own root
can instead pass the absolute path as a quoted example, e.g.
`claude plugin marketplace add "C:/path/to/coding-agents"` — that path is illustrative,
not repository truth; resolve the actual checkout location instead of assuming it.) Then,
inside a Claude Code session:

```text
/plugin install coding-workflows@coding-agents
```

installs the plugin in a session (plugin installation is a slash command, not a separate
`claude plugin install` CLI verb). From a pushed GitHub checkout, the marketplace can also
be added with `claude plugin marketplace add Troyyboii/coding-agents`. Start a new Claude
Code session after installing or updating the plugin so the current skill version loads.

## Account-side behavior not verified

This repository cannot inspect or prove a Claude Code account's or session's plugin
installation, enablement, marketplace registration, synchronization, or automatic-versus-
manual skill invocation. Those remain host/account state, exactly as Codex plugin
installation and ChatGPT Work Mode account state are host-side for the other two surfaces.
Repository validation proves the marketplace and plugin files are structurally correct and
traceable to the canonical skill source; it does not prove a Claude Code session has loaded
or can invoke them.

## What is deliberately not used

- **No generated Claude-specific skill copy.** The plugin points at the same canonical
  `skills/` tree Codex uses, so there is no `dist/`-style package to generate, validate for
  determinism, or keep from drifting.
- **No Claude Code hooks, MCP server bundling, or LSP server declarations** in the plugin
  manifest. This repository owns no MCP server and does not vendor host-level automation,
  matching the same boundary documented for Codex in
  [`docs/integrations/catalog.md`](./integrations/catalog.md).
- **No `permissionMode` override on the reviewer/verifier subagents.** Documented behavior
  for permission-mode overrides (such as a plan-only mode) in a non-interactive delegated
  subagent context could not be confirmed, so the read-only boundary uses the unambiguous
  tool-allowlist omission instead.
- **No slash-command files for helper-backed skills.** Skills that ship a helper under
  `scripts/` (for example `session-checkpoint`) run it through the session's normal
  shell tool with the user's permission settings. Claude Code has no repository-supported
  way here to mark a skill explicit-only, because canonical frontmatter is limited to
  `name` and `description`; `session-checkpoint` states in its description that it runs
  only on an explicit request.
- **No `.claude/skills/` project-level skill copies.** They would be a second source for
  content the plugin already supplies from the canonical directory, and would risk the two
  copies drifting apart.

## Adding a future skill without drift

Add or change the skill under `plugins/coding-workflows/skills/<name>/` exactly as
documented in [`WORKFLOWS.md`](../WORKFLOWS.md). No Claude-specific step is required: the
plugin manifest already resolves the whole `skills/` directory, so a new skill folder with a
valid `SKILL.md` becomes available to Claude Code the next time the plugin loads. Only
`plugins/coding-workflows/.claude-plugin/plugin.json`'s `version` needs a matching bump
alongside `.codex-plugin/plugin.json`'s, per [`docs/releasing.md`](./releasing.md).
