# Host Support Matrix

**Matrix version:** 1.0
**Compatibility review:** 2026-09-23
**Canonical source:** `plugins/coding-workflows/skills/`
**Package version:** `1.5.0` (must match the canonical plugin manifest; checked by `validate-repository.py`).

This matrix distinguishes repository package evidence from host runtime behavior.
`Structurally compatible` means this repository validates the declared files,
manifest, generated output, and references. It does not mean an account has
installed a package or that a particular host loaded, selected, or invoked it.
See [host troubleshooting](./host-troubleshooting.md) for common discovery and
import checks.

## Supported repository surfaces

| Host / surface | State | Consumption and install route | Canonical / generated source | Minimum documented format | Repository validation | Live verification and limits |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI Codex plugin | CURRENT / VERIFIED REPOSITORY COMPATIBILITY | Add this repository as a marketplace, then install `coding-workflows@coding-agents` with the Codex plugin CLI. | Canonical skills and `plugins/coding-workflows/` | Codex plugin manifest and Agent Skills `SKILL.md`; version shown above | `validate-repository.py` and Agent Plugins 1.0 contract checks | No account installation or invocation tested in this review. Project agents are separate from the plugin. |
| Claude Code plugin | CURRENT / VERIFIED REPOSITORY COMPATIBILITY | Add this repository marketplace with `claude plugin marketplace add <repo>` and install `coding-workflows@coding-agents`. | Canonical skills and `plugins/coding-workflows/` | Claude Code plugin/marketplace manifest; version shown above | Repository validator checks closed manifests, versions, skills path, exact read-only tools, and project-agent role parity. | Claude Code CLI validation and live session install or invocation were not run in this review. |
| ChatGPT Skills upload package (repository's Work Mode package surface) | GENERATED PACKAGE AVAILABLE | In an eligible workspace, use Skills → Create → Upload from your computer; upload individual generated packages as allowed by that product surface. | Canonical skills; `plugins/coding-workflows/work-mode/dist/` | Agent Skills name/description and package-local supporting files | `package-work-mode.py --check` | No account upload, availability, enablement, or invocation tested. Workspace policy and product availability vary. |
| Claude.ai Custom Skills | GENERATED PACKAGE AVAILABLE | Upload an individual generated ZIP through Claude's Skills interface. | Canonical skills; `plugins/coding-workflows/claude-app/dist/` | Agent Skills skill directory in one ZIP root | `package-claude-app.py --check` | No account upload, enablement, or invocation tested. |
| Cursor Agent Plugins | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Install through Cursor Customize from a marketplace. For local inspection, copy `plugins/coding-workflows/` to `~/.cursor/plugins/local/coding-workflows`, reload Cursor, and confirm skills in Customize. Local imports can be disabled by organization policy. | Existing Agent Plugins 1.0 `plugin.json` and canonical `skills/`; no Cursor skill copy | Agent Plugins 1.0.0 | Repository checks enforce the portable manifest, fixed `skills/` discovery, and matching versions | No Cursor installation or skill invocation tested. Cursor-specific marketplace publication is not done. |
| GitHub Copilot CLI | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Install the plugin from the repository subdirectory with `copilot plugin install Troyyboii/coding-agents:plugins/coding-workflows`; this route requires public repository access, and the repo's Claude marketplace is not a Copilot marketplace. | Existing Agent Plugins 1.0 manifest and canonical `skills/`; no Copilot skill copy | Agent Plugins 1.0.0 | Repository checks enforce the portable manifest and fixed `skills/` discovery | No Copilot CLI/account install or invocation tested. Copilot cloud agent/app surfaces may have distinct policy and installation behavior. |
| Gemini CLI | GENERATED PACKAGE AVAILABLE | Install `plugins/coding-workflows/gemini/dist/` from a local path with `gemini extensions install <path>`, or use the skills installer on an individual skill directory. | Canonical skills; generated extension at `plugins/coding-workflows/gemini/dist/` | `gemini-extension.json` plus extension `skills/` containing Agent Skills | `package-agent-skills.py --check` | Skills-only package; no `GEMINI.md`, MCP server, hooks, or subagents. No live install or invocation tested. |
| Kimi Code CLI | GENERATED PACKAGE AVAILABLE | Install the generated plugin from `/plugins` → Custom or with `/plugins install <path-or-url>`; use `/reload` or a new session after changes. | Canonical skills; generated plugin at `plugins/coding-workflows/kimi/dist/` | `kimi.plugin.json` plus plugin `skills/` using Agent Skills | `package-agent-skills.py --check` | Skills-only package; reviewer/verifier agents omitted because parity with the repository's restrictive agent authority is not established. No live install or invocation tested. |
| OpenCode | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Copy the generated `agent-skills/dist/skills/<skill>/` directories to project `.agents/skills/`, or configure a skills root. | Canonical skills; `plugins/coding-workflows/agent-skills/dist/skills/` | Agent Skills `SKILL.md`; OpenCode supports `.agents/skills` and configured roots | `package-agent-skills.py --check` | Supporting references are included under each skill. No OpenCode install or invocation tested. |
| Hermes Agent | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Copy skill directories to `~/.hermes/skills/` or a documented external skill directory. | Canonical skills; `plugins/coding-workflows/agent-skills/dist/skills/` | Agent Skills-compatible skill directory | `package-agent-skills.py --check` | No Hermes install or invocation tested; external skill path configuration may be needed to avoid copying. |
| Kilo Code | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Copy to project `.agents/skills/` or a supported Kilo skills directory. | Canonical skills; `plugins/coding-workflows/agent-skills/dist/skills/` | Agent Skills `SKILL.md`; `.agents/skills` is discovered by default | `package-agent-skills.py --check` | No Kilo install or invocation tested. |
| Kiro | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Import a generated skill folder from the Kiro Agent Steering & Skills panel, or place it in `.kiro/skills/`. | Canonical skills; `plugins/coding-workflows/agent-skills/dist/skills/` | Agent Skills `SKILL.md` with supporting files inside the skill | `package-agent-skills.py --check` | No Kiro import or invocation tested. |
| Cline | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Copy skill directories to `.cline/skills/`, `.clinerules/skills/`, or `.claude/skills/` for project scope; use `~/.cline/skills/` for global scope. | Canonical skills; `plugins/coding-workflows/agent-skills/dist/skills/` | Agent Skills `SKILL.md` with supporting files inside the skill | `package-agent-skills.py --check` | Cline's documented discovery paths do not include `.agents/skills/`. No Cline install or invocation tested. |
| Muse Code | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Install a generated skill folder with `muse skills install <skill-dir> --scope user`, or place it under `.agents/skills/` / `~/.agents/skills/`. | Canonical skills; `plugins/coding-workflows/agent-skills/dist/skills/` | Agent Skills `SKILL.md` | `package-agent-skills.py --check`; Meta documents `muse skills validate <skill-dir>`, but the CLI was not run | Current Meta developer documentation establishes Agent Skills discovery and validation. No Muse Code install or invocation tested. |
| Grok Build | STRUCTURALLY COMPATIBLE, LIVE HOST TEST NOT YET PERFORMED | Use the Claude Code marketplace/plugin route in Grok Build. | Existing Claude Code marketplace/plugin and canonical skills | Claude Code plugin and marketplace format | Existing repository and Claude package validation | Grok documents automatic Claude Code plugin/marketplace compatibility. No Grok session loaded or invoked this plugin. |

## Researched, deferred, or discontinued

| Host | State | Reason |
| --- | --- | --- |
| Roo Code | DISCONTINUED | The owner-archived repository states the extension was shut down on 2026-05-15. No active support target is created. |

## Shared package layout

`plugins/coding-workflows/agent-skills/dist/skills/` is the host-neutral
generated skills tree. The same generator builds the thin Gemini and Kimi
wrappers from that tree. For any canonical skill that refers to shared files in
`plugins/coding-workflows/references/`, generation copies the required reference
and its nested dependencies into that skill's own `references/` folder and
rewrites the link. This keeps each portable skill self-contained without
editing canonical source or maintaining per-vendor skill trees.

Shared Python modules named by a skill (`../../references/<module>.py`) are
copied the same way but byte-for-byte, without link rewriting, so a skill's
`scripts/` helpers run from both the whole-plugin layout and every generated
per-skill package. claude.ai ZIPs store every text file, these modules included,
with LF line endings, so a ZIP is identical whether it is built from an LF or a
CRLF checkout. Whether a host actually executes a helper is host behavior:
each helper-backed skill states how it degrades when execution, a repository, or
external reads are unavailable.

Generate or check all three outputs with:

```powershell
python scripts/package-agent-skills.py
python scripts/package-agent-skills.py --check
```

The generated wrappers include skills only. MCP, hooks, commands, context files,
system prompts, and subagents are excluded. Repository validation checks output
shape, known manifest fields, names/descriptions, references, symlinks, secrets
and machine paths, version parity, determinism, and stale output. Runtime skill
selection and host permission behavior require a separate harmless live test.

## Host contract notes

These notes distinguish each host's bundle format from capabilities this
repository actually ships. Agent Skills describes reusable skill folders; it
does not by itself define plugins, agents, MCP servers, hooks, or account-side
updates.

| Host | Discovery and bundled resources | Agents and MCP | Version, updates, and validation |
| --- | --- | --- | --- |
| OpenAI Codex | Native repository plugin marketplace; canonical plugin metadata resolves the `skills/` tree. | Project agents are separate; this plugin declares no MCP server. | Plugin version is shown above; installed Codex CLI exposes no plugin validator. Repository contracts are the validation evidence. |
| Claude Code | Native repository plugin marketplace; plugin root has `.claude-plugin/plugin.json` and `skills/`. | Claude subagents exist separately under `.claude/agents/`; this plugin does not bundle them or MCP. | Plugin version is shown above. Claude Code CLI strict validation, host install, and update behavior were not run in this review. |
| ChatGPT Skills / Work Mode | Upload individual generated packages containing `SKILL.md` and needed references. | The uploaded package is a skill; no subagent or MCP bundle is claimed. | Upload a regenerated package to update it. Account behavior was not tested. |
| claude.ai Custom Skills | Upload one generated ZIP per skill; referenced files remain inside that skill package. | These are skills, not Claude Code plugins, subagents, or MCP servers. | Regenerate ZIPs from canonical sources and re-upload for updates. Account behavior was not tested. |
| Cursor | Agent Plugins 1.0 `plugin.json` and canonical `skills/`; local plugin development requires reload. | The host format supports additional components, but this repository route ships no MCP or host-specific agent adapter. | Manifest version matches the canonical version shown above; marketplace updates and local reload were not tested. No repository-provided Cursor CLI validator. |
| GitHub Copilot CLI | Agent Plugins 1.0; direct repository subdirectory install is documented by Copilot. | The plugin format can carry more than skills, but this package adds no MCP server or Copilot-specific agents. | Manifest version matches the canonical version shown above; source and marketplace updates are host-managed. The installed CLI help has no plugin validation command. |
| Gemini CLI | Extension root has `gemini-extension.json` and `skills/`; each skill is self-contained with its references. | Gemini extensions can declare MCP capabilities. This generated extension intentionally contains no MCP or subagents because permission parity is unproved. | `gemini extensions validate <path>` is documented; extension update commands exist. Neither validator nor install/update ran because Gemini CLI is not installed. |
| Kimi Code CLI | Plugin root has `kimi.plugin.json` and `skills/`; installs may be directory, ZIP, or repository URL. | Kimi plugins can bundle skills, agents, MCP, commands, hooks, and prompt additions. This package contains skills only; no read-only agent mapping was established. | Manifest follows the canonical version shown above; refresh with `/reload` or a new session after update. No separate static validator was identified in reviewed docs; CLI is not installed. |
| OpenCode | Discovers Agent Skills from project `.agents/skills/` and other documented roots; skill references load relative to the skill directory. | Agents and MCP are configured separately; the generated skills tree adds neither. | Copy/update the skill directory or configure a source; no host package validator is required by its documented format. No live test. |
| Hermes Agent | Current docs accept Agent Skills-compatible folders and document a personal skill directory and external skill sources. | Hermes has its own agent and tool model; this package does not map project agents or MCP configuration. | Updates follow copied/external source behavior; no repository install or validation command was run. |
| Kilo Code | Discovers Agent Skills at documented project and user roots, including `.agents/skills/`. | Host-specific agents and MCP remain separate from portable skill metadata; not bundled here. | Copy generated folders and refresh the host as documented; no separate package validator run. |
| Kiro | Imports Agent Skills folders through its skills interface or project directory; supporting files travel with each skill. | Kiro steering/agent features are distinct; the generic package does not translate project-agent permissions. | Import/update behavior is controlled by the Kiro UI; no local static validator or live import was used. |
| Cline | Discovers project skills from `.cline/skills/`, `.clinerules/skills/`, or `.claude/skills/`; global skills from `~/.cline/skills/`. Bundled supporting files are supported. | Cline's MCP and agent configuration is separate; generated output is skills-only. | Copy/update files and refresh the host; no live test or separate package validator. [Official Cline Skills documentation](https://docs.cline.bot/customization/skills). |
| Muse Code | Meta's current documentation establishes user and project Agent Skills discovery and `muse skills install` / `muse skills validate`. | Muse documents agents, hooks, and MCP independently; this package claims only Agent Skills and adds no such configuration. | Use the documented skill validator when Muse is installed; it was not run here. No live import/invocation. |
| Grok Build | Current xAI documentation states that Grok Build reads Claude Code marketplaces, plugins, skills, agents, MCP, hooks, and instructions. This repository reuses its Claude plugin route. | The compatible format can represent those features; this repository's plugin does not include MCP and its project agents remain separate. | Claude plugin version and marketplace update behavior apply; no Grok validator or runtime session was used. |
| Roo Code | No current support route. The owner-archived repository says the extension was shut down. | Discontinued. | No package, updates, or validation. |

For generic Agent Skills hosts, the shared generated distribution preserves
package-local supporting files and the standard `name` and `description`
frontmatter. Host discovery and skill invocation remain unverified individually.

### Evidence required to promote a host claim

Repository structure and current vendor documentation support a structural claim.
Promote a host to live-verified compatibility only after recording the host and
version, installing/importing the exact version from a clean or documented
profile, confirming skill discovery and a harmless invocation, checking referenced
resources load, and exercising the documented update/reload path. Record failures
and host-specific policy limits in this matrix; do not infer account availability
or authentication from repository validation.

## Primary sources reviewed on 2026-09-23

- [Agent Plugins 1.0 specification](https://agent-plugins.org/specification) and [schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)
- [Cursor plugins](https://cursor.com/docs/plugins) and [Cursor Agent Skills](https://cursor.com/docs/skills)
- [GitHub Copilot plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins) and [Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)
- [Gemini CLI Agent Skills](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/using-agent-skills.md) and [extension reference](https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/reference.md)
- [Kimi Code plugins](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/customization/plugins.md)
- [OpenCode Agent Skills](https://opencode.ai/docs/skills)
- [Hermes Agent Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)
- [Kilo Code Skills](https://kilo.ai/docs/customize/skills)
- [Kiro Agent Skills](https://kiro.dev/docs/skills/)
- [Cline Skills](https://docs.cline.bot/customization/skills)
- [Muse Code extension and Skills documentation](https://dev.meta.ai/docs/muse-code/extending)
- [Grok Skills, Plugins & Marketplaces](https://docs.x.ai/build/features/skills-plugins-marketplaces)
- [Roo Code archived repository](https://github.com/RooCodeInc/Roo-Code)
- [ChatGPT Skills](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)
- [Claude Code plugins](https://code.claude.com/docs/en/plugins) and [Claude Code skills](https://code.claude.com/docs/en/skills)
