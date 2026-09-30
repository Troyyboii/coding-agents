# Documentation

This directory holds the product, compatibility, and operational documentation for
the coding-agents workflow pack. Start with the [repository README](../README.md) for
the skill list and quick start; the sections below say who each document is for.

## Using the skills

- [inventory.md](./inventory.md): generated list of the shipped skills, agents,
  helpers, and package surfaces.
- [claude-code.md](./claude-code.md): Claude Code plugin, marketplace, and subagent
  boundary.
- [work-mode.md](./work-mode.md): ChatGPT Work Mode packages.
- [claude-app.md](./claude-app.md): claude.ai Custom Skill ZIP packages.

## Hosts, installation, and support

- [host-support.md](./host-support.md): versioned host compatibility matrix,
  repository checks, install routes, and live-verification limits.
- [host-troubleshooting.md](./host-troubleshooting.md): skill discovery,
  generated-package, and host-side troubleshooting.
- [host-contracts/agent-plugins.md](./host-contracts/agent-plugins.md): Agent Plugins
  1.0.0 portable floor for `plugins/coding-workflows` (manifest, discovery, and
  explicit non-claims).
- [integrations/README.md](./integrations/README.md): curated host plugins, MCPs,
  live documentation routes, and Luna worker boundaries.
- [tools/context7.md](./tools/context7.md): Context7 usage boundary.

## Contributing, release, and maintenance

- [coding-agents-program.md](./coding-agents-program.md): canonical product and
  implementation program: identity, doctrine, capability lifecycle, Public V1
  boundary, and roadmap.
- [monorepo-operating-doctrine.md](./monorepo-operating-doctrine.md): source-of-truth
  and maintenance rules.
- [releasing.md](./releasing.md): validation and publication checklist.
- [evaluations.md](./evaluations.md): labelled routing cases and optional local replay.
- [workflows/codex-task-templates.md](./workflows/codex-task-templates.md): reusable
  task prompts for repository work.

## Audit and research history

These are maintainer evidence records, not user guides. Read them for provenance and
open backlog, not for current product claims.

- [audit-findings.md](./audit-findings.md): finding ledger with stable IDs, statuses,
  and evidence; a historical record that is also the active audit backlog.
- [research/agent-skill-ecosystem-raid.md](./research/agent-skill-ecosystem-raid.md):
  bounded source and mechanism ledger used for research decisions.
- [research/capability-expansion-ledger.md](./research/capability-expansion-ledger.md):
  bounded provenance ledger for the owner-directed 2026-09 capability expansion.

The research ledgers are bounded decision records, not prompt corpora or runtime
dependencies. Their source, privacy, refresh, and replacement rules are maintained in
[the research ledger policy](./research/agent-skill-ecosystem-raid.md#bounded-ledger-policy).
