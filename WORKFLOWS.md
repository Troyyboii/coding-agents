# Workflows

## Start a Task

```powershell
# Run from the checked-out repository root.
git status --short --branch
```

Read `AGENTS.md` and the files closest to the requested change. Inspect before
editing, distinguish generated files from source files, and preserve unrelated
work.

## Change a Skill

1. Edit the skill under `plugins/coding-workflows/skills/<skill-name>/`.
2. Keep frontmatter limited to `name` and `description`.
3. Keep `agents/openai.yaml` aligned with the trigger contract and ensure its default prompt invokes `$<skill-name>`.
4. Update `plugins/coding-workflows/evals/trigger-routing.json` when routing behavior changes.
5. Regenerate the Work Mode, claude.ai, portable Agent Skills, Gemini, and Kimi packages whenever the skill's
   instructions or references change (`python scripts\package-work-mode.py`,
   `python scripts\package-claude-app.py`, and `python scripts\package-agent-skills.py`).
   Never hand-edit `work-mode/dist/`, `claude-app/dist/`, `agent-skills/dist/`,
   `gemini/dist/`, or `kimi/dist/`.
6. Run an available official skill validator, when installed, and the repository checks; otherwise record the unavailable validator as not checked.
7. Regenerate `docs/inventory.md` only if the capability set or descriptions changed.

### Skill helpers

A skill may ship Python helpers only at `skills/<name>/scripts/<file>.py`, and shared
helper code only at `plugins/coding-workflows/references/<module>.py`. The
repository validator enforces the policy recorded in `SECURITY.md`: Python 3.11
standard library plus named shared modules, offline, no shell, subprocess denied
unless the helper is listed in `HELPER_SUBPROCESS_POLICY`, a module docstring, a
`__main__` guard, and every helper, support file, and shared module referenced
from its `SKILL.md`. Name a shared module in the consuming `SKILL.md` as
`../../references/<module>.py` so generated packages copy it byte-for-byte.
Generated-package scanners also apply to helper source, so:

- never write two consecutive backslashes (use `os.sep` or `pathlib`);
- locate shared modules with `Path` parts, not path-shaped string literals;
- write repository paths in skill prose without a `./` prefix;
- assemble secret-shaped test canaries at runtime; never commit them;
- build hostile or malformed fixtures in temporary directories during tests.

For cross-skill changes, update
`plugins/coding-workflows/references/workflow-coordination.md` and add deterministic
routing cases for precedence, negative triggers, authority, handoffs, and skip
conditions. Do not create a new skill when an existing phase owner or Codex built-in
already covers the behavior.

Preview affected labelled cases without model calls:

```powershell
python scripts\routing_evals.py --skill <skill-name>
```

Live routing evaluations are optional. They require the installed plugin,
`--run --acknowledge-cost`, and human review of the resulting report.

## Change Plugin Metadata

1. Edit `plugins/coding-workflows/.codex-plugin/plugin.json`.
2. Keep the plugin name equal to its folder and marketplace entry.
3. Use strict semantic versioning and real publisher metadata.
4. Do not declare apps, MCP servers, hooks, or assets unless those components exist.
5. When the version, name, or description changes, update
   `plugins/coding-workflows/.claude-plugin/plugin.json` to match. Do not add a `skills`
   field there; it must keep resolving the same `skills/` directory Codex uses.
6. Keep `plugins/coding-workflows/plugin.json` (Agent Plugins 1.0 portable floor) on the
   same version. Do not add `skills`, MCP, or other closed-schema fields there; skills
   stay at the fixed `skills/` location. See `docs/host-contracts/agent-plugins.md`.
7. Validate the plugin and check marketplace consistency on both surfaces.

## Change Project Agents

Project agents live under `.codex/agents/`. Each file must define `name`,
`description`, and `developer_instructions`. Keep review-oriented agents
read-only. Omit model pins unless a task establishes a durable reason for one.

When a project agent changes, update its Claude Code subagent equivalent under
`.claude/agents/<name>.md` with the same name, purpose, and authority meaning.
Claude Code has no `sandbox_mode = "read-only"` field; its `tools` allowlist must be
exactly `Read`, `Grep`, and `Glob`, with no delegation, MCP, or write tools. The
repository validator checks the semantic role and authority profile rather than
requiring identical prose.

Do not add custom versions of Codex's built-in default, explorer, or worker
agents, or of Claude Code's built-in general-purpose or explore subagents.

## Repository Checks

```powershell
python scripts\validate-repository.py
python scripts\generate-inventory.py --check
python scripts\package-work-mode.py --check
python scripts\package-claude-app.py --check
python scripts\package-agent-skills.py --check
python -m unittest discover -s tests -v
git diff --check HEAD
```

The validator checks active component contracts, the audit ledger, Cursor's
repository-owned environment boundary, and the validation workflow's semantic
shape. The inventory check proves the generated capability list matches source.
Unit tests cover deterministic tooling behavior. If the Codex CLI has no plugin
validator, record that check as unavailable; run the Claude CLI strict checks
only when that CLI is installed. None of these checks proves that a host-provided
connector is currently authenticated or callable. The validation workflow uses
the pull-request base, the parent of a push's previous commit, or an explicit
manual/root fallback, then checks the complete base-to-HEAD range. Text
hygiene scans bounded UTF-8 artifacts across the repository for stale markers and
high-confidence secret signatures, and reports paths without matched values. The
Cursor contract retains only the exact bounded compile command
`python -m compileall -q scripts tests`; it does not authorize package, system,
service, or test setup mutations.

## Review and Handoff

- Use `.github/pull_request_template.md` for pull-request descriptions.
- Review the full diff, including deletions and generated files.
- Report checks that actually ran and their exact result.
- Classify unavailable checks as not checked or blocked.
- Keep commits focused and use exact-path staging.
- Commit and push only after explicit authorization.

Keep builders, reviewers, and verifiers distinct when the change is large enough to
benefit from independent judgment. Parallel agents require independent scopes and
disjoint write ownership. Worktrees require a concrete isolation risk or explicit
user request; they do not grant commit, push, merge, or cleanup authority.

## Workflow Influence

The coordination rules and root-cause discipline were informed by
[Superpowers](https://github.com/obra/superpowers) by Jesse Vincent
(MIT License, copyright 2025). This repository uses original local guidance and does
not vendor Superpowers skills, prompts, templates, scripts, or documentation.

## Plugin Development Loop

Add the repository marketplace once:

```powershell
codex plugin marketplace add .
```

Install or refresh the plugin through the configured marketplace, then use a new
Codex session for testing. Repository validation does not mutate the normal user
plugin installation.

## Release Preparation

Follow [docs/releasing.md](./docs/releasing.md). Version changes, tags, pushes,
GitHub releases, and public plugin submissions remain separately authorized
external actions.
