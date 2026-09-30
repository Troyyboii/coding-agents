# coding-agents

`coding-agents` is a vendor-neutral pack of practical workflows for coding agents. It gives you a shared set of ways to research, plan, implement, review, and verify software changes.

There is one canonical workflow source in `plugins/coding-workflows/skills/`. Codex and Claude Code use native plugin surfaces; other hosts use generated packages or documented standards-based routes. Repository checks prove files and package structure, not installation or runtime behavior in a host account.

## What you get

Twenty focused workflow skills, plus the scripts and documentation needed to build and validate their distributions:

| Skill | Use it for |
| --- | --- |
| `action-mode` | Action-first work with concrete next steps |
| `anti-slop` | Clear, natural writing that preserves the intended voice |
| `browser-proof` | Evidence from an authorized browser workflow |
| `context-first` | Reconciling scattered, decision-relevant information |
| `diff-judge` | Reviewing a specific change or pull request |
| `improved-design` | Prioritized product-interface critique |
| `live-research` | Current research grounded in authoritative sources |
| `repo-xray` | Read-only orientation to a repository or worktree |
| `root-cause-debugging` | Diagnosing a failure before repairing it |
| `system-designer` | Settling software boundaries and interfaces |
| `test-writer` | Focused tests for a defined behavior |
| `verification-gate` | Checking completion claims against evidence |
| `skill-supply-audit` | Auditing a third-party skill, plugin, MCP definition, or hook bundle before installing it |
| `spec-trace` | Checking code or a patch against a specification, requirement by requirement |
| `repo-instructions` | Writing or auditing agent instruction files such as `AGENTS.md` |
| `ci-trust-review` | Tracing outsider paths to code execution or secrets through GitHub Actions |
| `dependency-risk` | Deciding whether depending on a package is acceptable, with measured coverage |
| `session-checkpoint` | Saving and resuming an explicit, freshness-checked session checkpoint |
| `patch-proof` | Proving a fix by running the same approved commands before and after it |
| `public-release-audit` | Checking whether a repository is ready to be made public |

Some skills ship a small offline Python helper under `scripts/`; the helpers run only
when an agent invokes them and follow the boundary described in [SECURITY.md](./SECURITY.md).

## Quick start

### Codex

From the repository root, add the local marketplace and install the plugin:

```powershell
codex plugin marketplace add .
codex plugin add coding-workflows@coding-agents
```

### Claude Code

From the repository root, add this checkout as a marketplace, then install the plugin in a Claude Code session:

```powershell
claude plugin marketplace add .
```

```text
/plugin install coding-workflows@coding-agents
```

Both native plugins use the canonical skills directly. Start a new host session after installing or updating so it loads the current skills.

## Hosts and delivery routes

| Route | Hosts and package surfaces |
| --- | --- |
| Native plugins | Codex and Claude Code |
| Generated packages | ChatGPT Work Mode, claude.ai Custom Skills, portable Agent Skills, Gemini CLI, and Kimi Code |
| Structural compatibility | Cursor and GitHub Copilot Agent Plugins; OpenCode, Hermes Agent, Kilo Code, Kiro, Cline, Muse Code, and other documented Agent Skills consumers |
| Claude-compatible route | Grok Build uses the repository's Claude Code plugin format |

Native and generated routes are repository-owned and validated here. Structural compatibility means the repository follows a documented format or discovery route; host installation, skill discovery, invocation, and updates have not necessarily been live-tested. Roo Code is discontinued and is not an active target.

Generate the portable Agent Skills, Gemini, and Kimi packages from canonical skills with:

```powershell
python scripts\package-agent-skills.py
python scripts\package-agent-skills.py --check
```

See the [host support matrix](./docs/host-support.md) for installation routes and evidence, and [host troubleshooting](./docs/host-troubleshooting.md) for discovery and import help. Separate guides cover [ChatGPT Work Mode](./docs/work-mode.md), [Claude Code](./docs/claude-code.md), and [claude.ai Custom Skills](./docs/claude-app.md).

## Contributing and development

Start with [AGENTS.md](./AGENTS.md), [WORKFLOWS.md](./WORKFLOWS.md), and [CONTRIBUTING.md](./CONTRIBUTING.md). Edit canonical sources, then regenerate repository-owned packages with their scripts; do not hand-edit generated output.

Run the main local checks from the repository root:

```powershell
python scripts\validate-repository.py
python scripts\generate-inventory.py --check
python scripts\package-work-mode.py --check
python scripts\package-claude-app.py --check
python scripts\package-agent-skills.py --check
python -m unittest discover -s tests -v
python scripts\routing_evals.py
git diff --check HEAD
```

The routing evaluation is a no-model dry run. Repository validation and documentation hygiene also run in GitHub Actions on Windows and Ubuntu. See [SECURITY.md](./SECURITY.md) for vulnerability reporting and [LICENSE](./LICENSE) for the project license.
