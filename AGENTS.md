# Repository Instructions

## Purpose

The repository is the source repository for `coding-agents`: a
source-grounded, vendor-agnostic pack of reusable coding-agent workflows.
Codex and Claude Code use native plugin surfaces. ChatGPT Work Mode, claude.ai,
portable Agent Skills, Gemini CLI, and Kimi Code use generated packages. Cursor
and GitHub Copilot have documented direct Agent Plugins compatibility routes;
other Agent Skills consumers use their documented discovery/import paths. These
are repository-level structural contracts, not proof of live host installation
or runtime behavior; see [docs/host-support.md](./docs/host-support.md). The repo
also contains two project agents, maintenance scripts, CI, and operational docs.

## Sources of Truth

- Author plugin changes under `plugins/coding-workflows/`.
- Treat `.agents/plugins/marketplace.json` as the repo marketplace definition for Codex.
- Treat `.claude-plugin/marketplace.json` and
  `plugins/coding-workflows/.claude-plugin/plugin.json` as the same plugin's Claude Code
  marketplace and manifest. They point at the identical `skills/` directory Codex uses;
  keep their `version` fields equal to `.codex-plugin/plugin.json`'s.
- Treat each skill's `SKILL.md` as its routing and workflow contract.
- Treat `plugins/coding-workflows/skills/` as the canonical workflow source.
  Do not hand-edit generated `work-mode/dist/`, `claude-app/dist/`,
  `agent-skills/dist/`, `gemini/dist/`, or `kimi/dist/` package outputs.
- Treat `.codex/agents/*.toml` as the project-agent definitions, and
  `.claude/agents/*.md` as their Claude Code subagent equivalents. Keep both surfaces'
  agent names, role purpose, and authority boundary identical in meaning; the Claude
  allowlist is exactly `Read`, `Grep`, and `Glob`.
- Treat `docs/inventory.md` as generated output. Change sources, then regenerate it.
- Keep external connectors and credentials outside this repository.

## Required Change Loop

1. Inspect `git status --short --branch` and the relevant source files.
2. Preserve unrelated user work and keep the change limited to the requested scope.
3. Update source files before generated inventory.
4. Run the relevant validation commands.
5. Inspect the complete diff and check for stale paths, secrets, generated debris, and accidental churn.
6. Commit, push, publish, deploy, or install into a user profile only after explicit authorization.

## Validation

Run from the repository root:

```powershell
python scripts\validate-repository.py
python scripts\generate-inventory.py --check
python scripts\package-work-mode.py --check
python scripts\package-claude-app.py --check
python scripts\package-agent-skills.py --check
python -m unittest discover -s tests -v
git diff --check HEAD
```

When a skill changes, run an available official skill validator, such as
`skills-ref`, against that changed skill. If no official skill validator is
installed, record that check as not checked. This checkout's Codex CLI does not
provide a plugin validator. Plugin metadata changes require the repository-owned
`python scripts\validate-repository.py` check. If the Claude Code CLI is
installed, also run `claude plugin validate plugins/coding-workflows --strict`
and `claude plugin validate . --strict`; otherwise record those host checks as
not checked rather than treating them as passed.

## Capability Rules

- Keep skills focused and non-overlapping. Prefer one clear trigger contract over generic expertise claims.
- Do not recreate Codex's built-in file, shell, Git, planning, explorer, or worker capabilities.
- Add a project agent only when its tool or permission profile materially differs from a built-in agent.
- Add a connector or MCP server only when a live external capability is required and cannot be supplied by the host.
- Do not add placeholder values, empty tracked files, empty component folders, copied dependency trees, or generated caches.
- Keep large research corpora, prompt archives, and historical source outside the active repository. Bounded, source-linked research ledgers may live under `docs/research/` when they support a current decision; they must not become runtime dependencies.

## Portability and Safety

- Keep shared scripts compatible with Windows PowerShell and Linux cloud runtimes.
- Use Python 3.11 or newer and the standard library unless a dependency clearly earns its maintenance cost.
- Never print or commit secrets, tokens, cookies, private keys, or credential-bearing configuration.
- Do not infer that an external plugin is installed, authenticated, or callable from repository configuration alone.
- Do not claim a check passed unless it was run or directly inspected.

## Local Paths

Keep changes inside the current repository unless the user explicitly includes
another checkout. Do not move, clean, or modify other projects or local profiles.
