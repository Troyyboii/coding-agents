# Pull Request

## Outcome

<!-- What user-visible workflow or repository contract changes? -->

## Scope

- Source files changed:
- Generated files changed (`docs/inventory.md`, `work-mode/dist/`, `claude-app/dist/`, `agent-skills/dist/`, `gemini/dist/`, `kimi/dist/`):
- Deliberately out of scope:

## Evidence

Report checks that actually ran and their exact result. Classify unavailable
checks as not checked or blocked.

- [ ] `python scripts/validate-repository.py`
- [ ] `python scripts/generate-inventory.py --check`
- [ ] `python scripts/package-work-mode.py --check`
- [ ] `python scripts/package-claude-app.py --check`
- [ ] `python scripts/package-agent-skills.py --check`
- [ ] `python -m unittest discover -s tests -v`
- [ ] `git diff --check HEAD`
- [ ] Available official skill validator, when applicable
- [ ] Claude CLI strict validation, when the CLI is installed

## Review

<!-- Confirm source vs generated files, deletions, and that all generated packages were regenerated rather than hand-edited. -->

## Risk and Boundaries

<!-- Note unverified behavior, external dependencies, migrations, secrets, or live-state assumptions. Do not include credentials. -->
