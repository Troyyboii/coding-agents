# Repository Operating Doctrine

## Keep the Active Tree Operational

Every tracked component must support a real Codex coding workflow. Research,
historical material, speculative integrations, empty scaffolds, dependency
installs, and caches belong outside the active tree.

## One Source for Each Capability

- One repo marketplace defines installable first-party plugins.
- One plugin owns the workflow skills.
- One `SKILL.md` owns each workflow contract.
- One TOML file owns each custom project agent.
- Generated inventory is rebuilt from those sources and checked in CI.

Do not preserve parallel copies for convenience. If a host already supplies a
capability, document the boundary instead of vendoring a wrapper that pretends
to provide it.

## Evidence Before Claims

Repository validation proves local structure, parsing, naming, and generated
state. Tests prove only the behavior they exercise. Connector configuration does
not prove installation, authentication, or live calls. State those boundaries
in reviews and handoffs.

## Dependencies Must Earn Their Cost

Prefer standard-library tooling for repository maintenance. Add a dependency
only when it removes meaningful risk or complexity, lock it reproducibly, and
give it an explicit validation path.

## Safe Change Discipline

- Inspect status and relevant instructions before editing.
- Preserve unrelated work.
- Make the smallest coherent change that satisfies the request.
- Review deletions and generated files as carefully as additions.
- Never commit, push, publish, deploy, or alter credentials without explicit authorization.
