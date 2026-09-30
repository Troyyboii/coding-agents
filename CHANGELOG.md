# Changelog

All notable changes are recorded here. This file follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## Unreleased

No unreleased changes yet.

## 1.5.0 - first public release (pending publication)

This is the first public release of `coding-agents`; there are no earlier releases.
The package manifests already carry version `1.5.0`, but the release has not been
tagged or published, so no release date is recorded yet. Set the date when the tag is
created (see [docs/releasing.md](./docs/releasing.md)). Every host route below is a
repository-level structural contract, not proof of live installation or runtime behavior
in a host account; see [docs/host-support.md](./docs/host-support.md).

### Added

#### Workflow skills

- Twenty canonical workflow skills under `plugins/coding-workflows/skills/`: `action-mode`,
  `anti-slop`, `browser-proof`, `ci-trust-review`, `context-first`, `dependency-risk`,
  `diff-judge`, `improved-design`, `live-research`, `patch-proof`, `public-release-audit`,
  `repo-instructions`, `repo-xray`, `root-cause-debugging`, `session-checkpoint`
  (explicit invocation only), `skill-supply-audit`, `spec-trace`, `system-designer`,
  `test-writer`, and `verification-gate`. The eight most recent were owner-directed
  additions (`skill-supply-audit`, `spec-trace`, `repo-instructions`, `ci-trust-review`,
  `dependency-risk`, `session-checkpoint`, `patch-proof`, `public-release-audit`),
  each researched and bounded against the existing twelve.
- A validated skill-helper boundary: skills may ship Python helpers at
  `skills/<name>/scripts/<file>.py`, checked for Python 3.11 standard-library imports,
  no network, dynamic-execution, or shell use, per-helper subprocess allowances (Git only,
  plus the approved-plan runner in `patch-proof`), and referenced support files. Generated
  packages copy shared Python modules from `references/` byte-for-byte.
- Shared contracts: an evidence contract, `references/audit-coverage.md` (coverage states,
  severities, adoption decision, secret handling), and `references/workflow-coordination.md`
  (phase ownership, precedence, authority classes, handoffs, untrusted-content,
  repository-data, and temporary-clone rules).
- A labelled routing golden set covering every skill, with an opt-in local evaluation
  runner that makes no model calls unless explicitly requested.

#### Distribution

- Native Codex plugin (`.agents/plugins/marketplace.json`) and native Claude Code plugin
  (`.claude-plugin/marketplace.json`) that resolve the same `plugins/coding-workflows/skills/`
  tree, plus read-only `reviewer` and `verifier` project agents for both hosts (Claude
  allowlist: `Read`, `Grep`, `Glob`).
- An Agent Plugins 1.0.0 portable floor: a root `plugin.json` for `plugins/coding-workflows`
  and a host contract at `docs/host-contracts/agent-plugins.md`. This is a packaging check,
  not a claim that any client has loaded the plugin.
- Deterministic generated packages from the canonical skills: ChatGPT Work Mode, claude.ai
  Custom Skills (one ZIP per skill), portable Agent Skills, a Gemini CLI extension, and a
  Kimi Code plugin. Shared references are copied into each package-local skill folder.
  Account-side upload, installation, and enablement are host-side and unverified.
- A versioned host support matrix and source-reviewed install and troubleshooting routes
  for Agent Plugins and Agent Skills consumers, including Cursor, GitHub Copilot CLI,
  OpenCode, Hermes Agent, Kilo Code, Kiro, Cline, Muse Code, and Grok Build. Roo Code is
  recorded as discontinued.

#### Validation and governance

- Repository validation of plugin, skill, agent, routing, marketplace, package, and
  documentation contracts, a deterministic generated inventory, and adversarial tests for
  package determinism, malformed manifests, unsupported metadata, broken references,
  source symlinks, and canonical-source immutability.
- Windows and Ubuntu validation in GitHub Actions, including generated-package drift
  checks and a full event-base whitespace check.
- A configuration-only Host Capability Doctor and redacted host-toolbox inspection, and a
  curated host integration catalog.
- `docs/coding-agents-program.md` as the canonical product and implementation program
  (identity, doctrine, capability lifecycle, distribution model, Public V1 boundary,
  roadmap), an audit finding ledger (`docs/audit-findings.md`), and a bounded research
  ledger under `docs/research/`.
- MIT license, contribution guidance, security policy, pull-request template, and release
  checklist.

### Changed

- The project identity is a vendor-neutral, multi-agent-host pack (owner-stated
  2026-09-18): `docs/coding-agents-program.md`, `README.md`, `AGENTS.md`, and
  `CONTRIBUTING.md` no longer frame it as Codex-only.
- Skill descriptions for `repo-xray`, `diff-judge`, `live-research`, `context-first`, and
  `verification-gate` gained boundary clauses so the newer skills do not compete with them
  by keyword.
- Research, repository-orientation, debugging, testing, review, browser, and completion
  workflows gained staged context, targeted path tracing, risk-sensitive lenses, fresh
  evidence, and explicit stop conditions.
- Host compatibility language describes repository-owned outputs and structural-only
  evidence; maintainer checkout paths were replaced in newcomer-facing examples.
- Plugin listing metadata follows the documented skills-only submission length and asset
  requirements.

### Removed

- `docs/tools/repomix.md` and `.repomixignore`, which the generated inventory flagged as
  removal candidates because no repository packet was ever produced with them.

### Fixed

- Malformed JSON object shapes and invalid structured routing responses are rejected
  without crashing or recording false completions.
- Marketplace, plugin, skill, and generated-inventory paths are confined to the
  repository, and symlink-based read or write escapes are refused.
- Repository validation is bounded by file count, individual size, aggregate bytes,
  streaming traversal, and a CI timeout.
- Validation workflows no longer persist checkout credentials, and devcontainer setup no
  longer executes checkout-controlled Python automatically.
- The Markdownlint action pin was refreshed and a stale external version reference was
  removed from workflow documentation.
