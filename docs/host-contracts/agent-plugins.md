# Agent Plugins 1.0 portable floor

This is the repository-owned compatibility contract for the Agent Plugins
Specification 1.0.0 portable plugin floor. Cursor and GitHub Copilot document
support for this format. Repository conformance checks establish structural
compatibility only; no live client has loaded, installed, or invoked this
package in the current review.

Inspected specification and schema (2026-09-21):

- [Agent Plugins Specification 1.0.0](https://agent-plugins.org/specification)
- Canonical `$schema` identifier:
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`
- Machine-readable schema:
  [schemas/1.0.0/plugin.schema.json](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)

The specification text is authoritative if it conflicts with the schema.

## Compatibility contract

| Field | Contract |
| --- | --- |
| Host / format | Agent Plugins 1.0.0 portable plugin |
| Canonical source | `plugins/coding-workflows/skills/<name>/SKILL.md` |
| Package form | The existing `plugins/coding-workflows/` directory, with a root `plugin.json` |
| Skills copy | None. Clients discover the same `skills/` tree Codex and Claude Code already use. |
| Generated `dist/` | Not used for this floor. Work Mode remains `plugins/coding-workflows/work-mode/dist/`. |
| MCP | Not included. No `mcp.json`. MCP is a separate optional Agent Plugins component. |
| Project agents | `reviewer` and `verifier` stay project-scoped under `.codex/agents/` and `.claude/agents/`. They are not plugin components. |
| Marketplace | Deferred. This file does not define a public registry or marketplace submission. |

## Manifest

Agent Plugins requires a manifest at `plugin.json` in the plugin root. The closed
portable field set is `$schema`, `name`, `version`, `description`, `author`,
`homepage`, `repository`, `license`, `keywords`, and `extensions`. Required
fields are `$schema` and `name`. Unknown top-level fields are schema violations.

This repository's `plugins/coding-workflows/plugin.json`:

- sets `$schema` to `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`;
- uses `name` `coding-workflows`, matching the plugin folder;
- keeps `version` aligned with `.codex-plugin/plugin.json` and
  `.claude-plugin/plugin.json`; the canonical manifest is the version source,
  and the validator checks parity rather than repeating a version here. The
  schema types `version` as a string and recommends Semantic Versioning;
- does not declare `extensions`, `skills`, or any other non-portable field;
- does not add `mcp.json`.

The Codex and Claude manifests remain host-specific nested files. They are not
the Agent Plugins portable manifest and must not replace `plugin.json`.

## Discovery model

Per specification §6.1 and §7.1:

- Skills are discovered only from the fixed location `skills/`.
- `plugin.json` cannot override that location or inline skill configuration.
- Each **immediate** child directory of `skills/` that contains a regular file
  named exactly `SKILL.md` is one skill.
- Clients must not recursively search deeper descendants for additional skills.
- A missing `skills/` directory is not a client error in the specification; this
  plugin is skills-based, so repository validation requires `skills/` to exist
  as a directory and to expose the canonical skill set.
- A missing `mcp.json` is not an error. This repository treats a present
  `mcp.json` as a contract violation because MCP packaging is out of scope.

Shared references under `plugins/coding-workflows/references/` remain inside the
plugin root. Relative links of the form `../../references/...` from a skill body
resolve inside that root for a whole-plugin install. Isolated per-skill copies
are a different consumption model and are not this floor.

Some skills also ship reviewed Python helpers at `skills/<name>/scripts/<file>.py`
and import shared modules from `plugins/coding-workflows/references/*.py`. In a
whole-plugin install the helper finds the shared module at the plugin root; the
generated per-skill packages carry their own copy. Helpers are files the agent
may run; they are not Agent Plugins components, hooks, or commands.

Codex-only `agents/openai.yaml` files inside skill directories are not Agent
Plugins components. They stay in the canonical tree for Codex and are ignored
by this portable contract.

## Validation

Run from the repository root:

```powershell
python scripts\validate-repository.py
```

The validator's Agent Plugins checks confirm:

- `plugins/coding-workflows/plugin.json` exists, is JSON, uses the canonical
  `$schema`, and stays within the closed 1.0.0 field set.
- `name` satisfies the specification's 1–64 character, lowercase alphanumeric /
  hyphen / period rules and matches the plugin folder.
- `version` matches `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`.
- `skills/` is a directory whose immediate `*/SKILL.md` children are the
  canonical workflow skills.
- `mcp.json` is absent, and no executable Claude component path is present.

These checks prove repository structure. They do not prove that an Agent
Plugins client has loaded the plugin.

## Explicit non-claims

- Cursor and GitHub Copilot are documented consumers of Agent Plugins 1.0 and
  are listed in [`docs/host-support.md`](../host-support.md) as structurally
  compatible, not live-verified.
- No live client installation, enablement, routing, or invocation is verified.
- MCP packaging is skipped; do not add `mcp.json` or treat MCP as part of this
  floor.
- `reviewer` and `verifier` are not packaged here.
- Marketplace, registry, and public plugin-directory submission are deferred.
- Work Mode package layout is unchanged.

## Deliberate exclusions

- No generated or hand-authored skill copy for Agent Plugins.
- No client extension namespace (`extensions` or `com.example.client/`-style
  directories).
- No hooks, commands, rules, or project-agent files in the portable plugin.
- No change to `work-mode/dist/` generation or path.
