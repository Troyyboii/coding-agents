# Contributing

Changes should make an existing coding-agent workflow more reliable or add a
clearly distinct capability. File count is not a goal.

## Before Editing

1. Read [AGENTS.md](./AGENTS.md) and [WORKFLOWS.md](./WORKFLOWS.md).
2. Run `git status --short --branch` and preserve unrelated work.
3. Identify the source file. Do not edit generated `docs/inventory.md`,
   `plugins/coding-workflows/work-mode/dist/`,
   `plugins/coding-workflows/agent-skills/dist/`,
   `plugins/coding-workflows/gemini/dist/`,
   `plugins/coding-workflows/kimi/dist/`, or
   `plugins/coding-workflows/claude-app/dist/` by hand.
4. Check that the proposed capability does not duplicate Codex built-ins or a
   host-provided plugin.

## Skill Changes

- Keep routing language concrete and non-overlapping.
- Update `agents/openai.yaml` when user-facing metadata changes.
- Update the labelled routing cases when activation or boundary behavior changes.
- Regenerate Work Mode and claude.ai packages when skill instructions or
  references change; never hand-edit `work-mode/dist/` or `claude-app/dist/`.
- Regenerate the portable Agent Skills, Gemini, and Kimi packages when skills
  or references change; never hand-edit those `dist/` trees.
- Add a new skill only after repeated real requests demonstrate one coherent
  unsupported workflow, or through explicit owner-directed capability expansion
  backed by research, routing and authority boundaries, and validation (see
  the capability lifecycle in `docs/coding-agents-program.md`).

## Required Checks

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
`skills-ref`, against that changed skill. If none is installed, record that check
as not checked. This checkout's Codex CLI does not provide a plugin validator, so
plugin metadata and packaging rely on the
repository-owned `python scripts\validate-repository.py` check. If the Claude
Code CLI is installed, also run:

```text
claude plugin validate plugins/coding-workflows --strict
claude plugin validate . --strict
```

Otherwise record those host checks as not checked.

Use `python scripts\routing_evals.py` for the free routing dry run. Live
model-backed evaluations are optional, require explicit cost acknowledgement,
and remain human-reviewed evidence.

## Pull Requests

Keep pull requests focused. Use
[the pull-request template](./.github/pull_request_template.md).

Describe the user-visible behavior, the source of truth, generated files that
were regenerated rather than hand-edited (`docs/inventory.md`, Work Mode,
claude.ai, and Agent Skills packages), the checks actually run with their exact
results, and anything deliberately not verified. Review the full diff, including
deletions and generated files.

Do not include credentials, generated caches, model-evaluation reports, or
unrelated formatting churn. Keep `plugins/coding-workflows/skills/` canonical;
derive host outputs from it and document their contract and checks. Do not add a
live MCP server or hand-maintained host-specific skill copies.
