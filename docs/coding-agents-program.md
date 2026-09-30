# coding-agents: Product and Implementation Program

Status: `CURRENT` as the canonical program document. Version `1.5.0` is prepared
as the first public release candidate, but the repository is not yet public and
the release has not been tagged or published; publication remains a target
milestone, not the current state.

This document is the long-lived product and implementation map for
`Troyyboii/coding-agents`. It describes the machine the repository is building,
the boundaries that keep it coherent, the evidence for what exists now, and the
work required before a public V1 claim is honest.

## 1. Authority, use, and maintenance

This document is the canonical product and implementation program. It owns the
project's identity, product promise, doctrine, scope, capability lifecycle,
public-release definition, roadmap, and architectural invariants. It is written
for maintainers, contributors, Codex sessions, and users deciding whether a
capability belongs in this repository.

It does not override live implementation, repository policy, or verified
external state. When prose and evidence disagree, use this order:

| Authority | Owns | Not owned here |
| --- | --- | --- |
| Live repository implementation and verified host or remote state | What actually exists and works in the inspected environment | Product intent that has not been implemented or verified |
| `AGENTS.md` and `WORKFLOWS.md` | Operational repository policy, authority limits, and change loop | The full product strategy |
| Plugin, skill, agent, manifest, script, test, and workflow sources | Their own runtime or structural contracts | The product roadmap |
| `docs/inventory.md` | Volatile current inventory generated from source | Hand-authored product interpretation |
| `README.md` | Public orientation and shortest adoption path | The complete internal program |
| Specialized documents such as `docs/releasing.md`, `docs/work-mode.md`, and `docs/integrations/` | Narrow procedures and boundary details | General product identity |
| This document | Product doctrine, implementation direction, public V1 boundary, and roadmap intent | Proof that planned work is implemented |

Roadmap language never proves implementation. A configuration entry never proves
that a host integration is callable. A passing structural check never proves
that a workflow is behaviorally useful in every task.

Update this program when the product identity, public promise, major architecture,
public V1 boundary, capability lifecycle, distribution model, or major roadmap
state materially changes. Do not update it for volatile counts, commit IDs,
current branches, CI run numbers, or host snapshots; link to the authoritative
source or record the observation in a task-specific report instead.

## 2. Identity

### What coding-agents is

`coding-agents` is a source-grounded, vendor-agnostic pack of reusable
coding-agent workflows — skills, and where the capability lifecycle (Section
10) justifies it, plugins and generated MCP-facing packages — meant for
multiple coding-agent hosts to consume without competing hand-authored copies
per host. It supports dedicated read-only project agents and maintains the
repository contracts needed to validate, evaluate, and distribute those
workflows.

Today the canonical plugin is structurally compatible with Codex and Claude
Code, its Agent Plugins 1.0 manifest is documented by Cursor and GitHub Copilot,
and generated Agent Skills packages cover Gemini CLI, Kimi Code, and hosts that
consume the shared skills format. The versioned [host support matrix](./host-support.md)
records repository evidence separately from untested host behavior. Public
V1 publication and live installation proof remain outstanding.

Its primary job is to make coding-agent work more reliable at the points where
agents commonly overreach or make unsupported claims:

- orienting in an unfamiliar repository;
- resolving scattered context before a consequential decision;
- researching current technical facts;
- diagnosing before repairing;
- reviewing a real change rather than its description;
- proving completion with fresh, proportionate evidence;
- keeping browser checks, tests, design critique, and writing within their
  respective boundaries.

The smallest accurate public description is:

> A source-grounded, vendor-agnostic pack of bounded coding workflows, with
> deterministic repository validation, currently distributed through Codex and
> Claude Code plugins, generated Work Mode and claude.ai packages, Agent Plugins
> compatibility, and generated portable Agent Skills, Gemini CLI, and Kimi Code
> packages. See the versioned support matrix for host-level evidence and limits.

### Why it is a repository

This needs to be more than a folder of prompts because a usable workflow
capability has a lifecycle and a contract. The repository owns plugin metadata,
skill source, routing cases, shared references, read-only project-agent
definitions, validation tooling, generated inventory, generated Work Mode
packages, CI, and release procedure. Those surfaces make a capability reviewable
and reproducible across repositories and host surfaces.

Ordinary agent prompting can describe a desired answer. This project adds a
reusable operating contract: when a workflow applies, what it may claim, what it
must inspect, which authority boundary it respects, which evidence is enough,
and when it must stop. The repository does not replace the model, the host, or
the user's authorization; it gives those runtime pieces a coherent workflow
layer.

### Who it is for

The primary users are developers and maintainers who use a supported
coding-agent host for repository work and want repeatable inspection, bounded
execution, review, debugging, testing, design, research, or completion proof.

The secondary users are contributors who add or maintain workflow capabilities.
They need to understand not only how to edit a `SKILL.md`, but also how routing,
generated packages, validation, host boundaries, and release compatibility fit
together.

## 3. Public product promise

The eventual public repository should promise a small, honest product:

1. **Reusable workflow contracts.** Users can adopt focused workflows for
   repository orientation, context gathering, research, debugging, diff review,
   verification, browser proof, design critique, testing, writing, and immediate
   action shaping.
2. **Source-grounded operation.** The workflows tell an agent to inspect the
   relevant source, configuration, history, or runtime state before making a
   claim or taking a consequential step.
3. **Bounded authority.** The workflows distinguish read-only inspection,
   implementation, review, host capability, and external publication. They do
   not grant authority merely because an agent can describe an action.
4. **Repository-level integrity.** The repository provides deterministic checks
   for plugin, skill, agent, routing, inventory, path, generated-package, and
   documentation contracts.
5. **Portable distribution artifacts.** The canonical skills are directly reusable on the
   supported Codex and Claude Code plugin surfaces, and packaged for the supported
   ChatGPT Work Mode and claude.ai Custom Skills surfaces, without maintaining competing
   hand-authored copies. Section 20's Phase 1 extends this same one-source, generated-package
   pattern to additional coding-agent hosts as they earn a compatibility contract.

A new user should be able to clone the repository, understand the supported
prerequisites and surfaces, install or select the plugin using the documented
path, invoke a relevant workflow, and run the repository checks. They should not
be promised automatic host installation, authenticated external tools, account
synchronization, model quality, or publication authority unless a separate
current proof exists.

## 4. Product doctrine

These are the durable rules extracted from the repository's operating policy,
skill contracts, validation code, and distribution documentation.

- **Inspect before action.** Read governing instructions, current state, and the
  smallest relevant source path before changing or recommending a change.
- **Evidence before claims.** State what was observed, executed, inferred, or
  left unverified. A plausible summary is not proof.
- **Authority is bounded by the task.** Tool access, a plugin manifest, a host
  integration, or a worker profile does not authorize commit, push, publication,
  deployment, credential access, or destructive cleanup.
- **Preserve unrelated work.** Dirty worktrees, user-authored changes, and
  unrelated generated material are protected inputs, not cleanup opportunities.
- **The artifact outranks the summary.** Inspect the actual diff, generated
  tree, source file, test output, or live state instead of accepting an agent's
  account of it.
- **Host capability must be proved at the right level.** Registration,
  configuration, reported authentication, and a successful callable operation
  are different claims.
- **One source per capability.** Canonical skill source generates the Work Mode
  packages; generated inventory is regenerated; parallel copies are not a
  compatibility strategy.
- **Focused capabilities compose.** A new skill needs a distinct job. Cross-skill
  precedence belongs in the coordination contract, not in a giant universal
  agent.
- **Validation belongs beside architecture.** New structural contracts need a
  deterministic validator or test at the same time as the source change.
- **Portability is part of correctness.** Shared tooling is dependency-light and
  validated on the repository's supported Windows and Ubuntu CI surfaces.
- **External services remain host-owned.** GitHub, Context7, OpenAI documentation
  access, and worker runtimes are documented boundaries, not vendored services.
- **Boring verification comes before shiny automation.** Automation is justified
  when it prevents drift or makes a meaningful claim testable, not when it merely
  produces activity.

## 5. Capability vocabulary

The program uses these labels consistently. They describe maturity of a specific
claim, not the importance of the idea.

| Label | Meaning |
| --- | --- |
| `CURRENT` | Supported by inspected repository evidence for the claimed repository-owned behavior. For host or remote behavior, the label applies only to the repository's implemented boundary unless direct external proof is also named. |
| `PARTIAL` | A meaningful foundation exists, but an important contract, distribution path, host path, validation layer, user experience, or proof boundary is incomplete. |
| `PLANNED` | Deliberately intended work in the active release program that is not implemented yet. |
| `FUTURE` | Longer-term direction outside the active public-release program. |
| `BLOCKED` | Work or a claim cannot proceed because an explicit boundary, missing owner decision, unavailable prerequisite, or unresolved external dependency stops it. This is not permission to guess. |
| `UNVERIFIED` | Configuration, documentation, or an implementation lead exists, but sufficient direct evidence of the claimed behavior is absent. |
| `HISTORICAL` | Retained provenance or context that no longer defines the active system. |

`BLOCKED` and `UNVERIFIED` are not interchangeable. A host connector may be
configured but `UNVERIFIED`; a repository-owned MCP server is `BLOCKED` because
the project deliberately does not own one.

## 6. Current source-grounded snapshot

The generated [active inventory](./inventory.md) owns volatile lists and counts.
The table below records the architecture and maturity that matter to the
program without becoming a second inventory generator.

| Capability | Current implementation | Validation or distribution evidence | Remaining gap |
| --- | --- | --- | --- |
| Repository operating policy | `AGENTS.md`, `WORKFLOWS.md`, `CONTRIBUTING.md`, `SECURITY.md`, and the pull-request template define inspection, authority, validation, review, and release boundaries. | Required files and stale markers are checked by `scripts/validate-repository.py`; policy is read by contributors and agents. | Policy is strong for the current maintainer workflow; public newcomer comprehension still needs a stranger-path audit. `PARTIAL` |
| First-party plugin | `.agents/plugins/marketplace.json` points to `plugins/coding-workflows/`; the plugin manifest declares the package, metadata, assets, license, and skill source. | Repository validation checks marketplace/plugin identity and metadata; Codex installation is a separate host action. `CURRENT` | Public marketplace or registry submission and a public installation proof are not current repository behavior. `PARTIAL` |
| Claude Code plugin | `.claude-plugin/marketplace.json` points to `plugins/coding-workflows/`; `plugins/coding-workflows/.claude-plugin/plugin.json` declares the same package and resolves skills from the identical `skills/` directory the Codex plugin uses, so there is no second skill source. | Repository validation checks the closed marketplace and manifest metadata, rejects executable Claude component paths, checks version parity with the Codex manifest, and enforces the exact `Read`/`Grep`/`Glob` subagent allowlist plus semantic role and authority parity; Claude Code installation is a separate host action. `CURRENT` at repository level | Public marketplace submission and a public installation proof are not current repository behavior, the same gap as the Codex plugin. `PARTIAL` |
| Workflow skills | `plugins/coding-workflows/skills/` is the authored source for focused workflow contracts covering action, writing, browser proof, context, system design, product critique, research, orientation, debugging, testing, diff review, and verification, plus the owner-directed 2026-09 trust and assurance workflows: extension supply audit, specification tracing, instruction files, CI trust, dependency risk, session checkpoints, paired fix proof, and publication readiness. Seven of those ship offline Python helpers under a validated helper policy. | Each skill has frontmatter and restricted Codex metadata; routing cases cover direct, indirect, negative, and edge behavior. `CURRENT` structurally | Behavioral usefulness and cross-host quality are not proved by Markdown or metadata validation alone. `PARTIAL` |
| Shared workflow contracts | `references/workflow-coordination.md` defines phase ownership, precedence, authority, handoffs, and completion conditions; `references/evidence-contract.md` defines durable evidence fields. | Skills and repository tests refer to those contracts; Work Mode copies only needed references. `CURRENT` | New cross-skill behavior must keep the coordination contract and routing corpus aligned. |
| Project agents | `.codex/agents/reviewer.toml` and `verifier.toml` are read-only, review- and evidence-focused agents. Built-in default, explorer, and worker roles are not duplicated. | Validator requires project agents to be read-only and structurally complete. `CURRENT` | Additional agents need a materially different permission or tool profile; none is currently justified by repository evidence. |
| Repository validation | `scripts/validate-repository.py` checks source paths, symlink containment, JSON/TOML, plugin and skill contracts, closed Claude boundaries, agent role/tool parity, Cursor's environment boundary, audit-ledger schema, semantic CI workflow shape, routing data, package mappings, required files, links, bounded stale/secret text, file limits, and the skill-helper boundary (helper location, standard-library and offline imports, per-helper subprocess allowances, and referenced support files). | Required local check and cross-platform CI job. `CURRENT` | It proves repository contracts, not model behavior, host authentication, or every public-history secret. |
| Deterministic inventory | `scripts/repository_inventory.py` derives `docs/inventory.md` from the marketplace, plugin, skills, agents, scripts, workflows, Work Mode manifest, and documented integration boundaries. | `scripts/generate-inventory.py --check` detects drift; the generated file is checked in. `CURRENT` | Do not hand-edit the generated file; maintainers must remember to regenerate after source changes. |
| Work Mode distribution | `plugins/coding-workflows/work-mode/manifest.json` maps canonical skills to generated, self-contained packages under `work-mode/dist/`; current entries use the shared-core form. | `python scripts/package-work-mode.py --check` validates package structure, references, portability, determinism, and source equality. `CURRENT` at repository level | ChatGPT account installation, enablement, synchronization, and availability remain separate and `UNVERIFIED`. |
| claude.ai Custom Skills distribution | `plugins/coding-workflows/claude-app/manifest.json` maps every active canonical skill to a generated, self-contained ZIP package under `claude-app/dist/`, one skill per ZIP, built with the same shared packaging logic as Work Mode. | `python scripts/package-claude-app.py --check` validates package structure, the official Agent Skills name/description contract, reference containment, and determinism relative to canonical skill source. `CURRENT` at repository level | claude.ai account upload, enablement, per-user synchronization, and code-execution availability remain separate and `UNVERIFIED`. |
| Portable Agent Skills, Gemini CLI, and Kimi Code distribution | `scripts/agent_skill_packages.py` generates a generic self-contained skills tree under `agent-skills/dist/` plus thin Gemini and Kimi wrappers under `gemini/dist/` and `kimi/dist/` from canonical skills and required shared references. | `python scripts/package-agent-skills.py --check` validates manifests, package-local references, names/descriptions, path confinement, symlink absence, version parity, deterministic output, and stale output. `CURRENT` at repository level | Host installations and invocation remain unverified. Gemini and Kimi packages include skills only; no agents or runtime services ship. |
| Additional Agent Skills consumers | OpenCode, Hermes Agent, Kilo Code, and Kiro document Agent Skills or discover `.agents/skills/`; Cline documents Agent Skills in its own project and user skill directories. | Generic generated distribution and import paths are recorded in `docs/host-support.md`. `CURRENT` as repository structure | No live host behavior has been tested. |
| Host readiness | `scripts/host_toolbox.py` safely inspects Codex plugin/MCP listings and expected host-level worker contracts, then evaluates `config/host-readiness.json`. | The doctor distinguishes configuration, reported auth, worker contract verification, and readiness; it never claims external callability. `CURRENT` as a tool | A particular host snapshot must be rerun in its own environment. The audit execution could verify the configured worker contracts but could not parse live Codex plugin/MCP listings. `UNVERIFIED` |
| Routing evaluation | `plugins/coding-workflows/evals/trigger-routing.json` is a stable labeled corpus; `scripts/routing_evals.py` supports a free dry run and optional model-backed runs. | The dry run executes without model calls or report files; model-backed results require human review. `CURRENT` as evaluation machinery | No automated result can substitute for human review of usefulness, safety, or boundary behavior. `PARTIAL` |
| CI and documentation hygiene | GitHub Actions run the repository-owned semantic workflow check, offline link and Markdown checks, repository validation, inventory, all generated-package `--check` commands, unit tests, Python compilation, and a full event-base whitespace comparison on Ubuntu and Windows. | `.github/workflows/knowledge-hygiene.yml` and `.github/workflows/validate-repository.yml`. `CURRENT` as a repository contract | Hosted CI health for a future public release must be checked on the exact release candidate. |
| Research and integration notes | `docs/research/`, `docs/integrations/`, and `docs/tools/` record bounded mechanisms, provenance, optional tools, and host ownership; they are not runtime dependencies. | Inventory marks optional review candidates and external integrations separately. `CURRENT` as documentation | Refresh research only when a fact could change a product, security, or compatibility decision; use the host support matrix for volatile status. |
| Release/versioning | The plugin manifests, host matrix, and generated packages carry version `1.5.0`; `CHANGELOG.md` has a `1.5.0` first-release section (undated, pending publication) above an empty Unreleased section; `docs/releasing.md` defines verification and separately authorized publication steps. | Release checklist and repository validation, which checks version parity. `CURRENT` for the prepared candidate | No tag, GitHub release, or dated release record exists. `PUBLIC-BLOCKER` for a V1 release claim |
| Public-facing adoption | `README.md` gives the skill overview, Codex and Claude Code quick starts, delivery routes, contribution and validation commands, and links the versioned support matrix. | Internal links and Markdown are checked. `CURRENT` as orientation | Clean-environment stranger testing and a final owner release review remain; the repository stays private until the owner changes its visibility. `PUBLIC-READINESS` |
| Archive/vendor boundary | The active tree excludes validator-rejected legacy roots and does not own an MCP server or dependency tree; the research ledger records source provenance without becoming a prompt corpus. | Validator stale/legacy markers, path rules, inventory boundaries, and `.gitignore` support this. `CURRENT` in inspected scope | A history privacy scrub was completed (owner-reported); bundled assets, third-party attribution, and supply-chain assumptions still require an explicit owner review, and the publication audit should be repeated on the exact release candidate. `UNVERIFIED` |

## 7. System architecture

The repository is a source-and-contract system. The runtime host supplies the
model, built-in tools, external integrations, and optional workers. The
repository supplies workflow instructions, package metadata, local validation,
and distribution artifacts.

```text
repository policy and contracts
        |
        v
canonical plugin metadata + skill source + shared references
        |
        +--> Codex plugin marketplace/package surface
        |          |
        |          v
        |     host routing and workflow execution
        |
        +--> Claude Code plugin marketplace surface (same skill source, no copy)
        |          |
        |          v
        |     host routing and workflow execution
        |
        +--> routing evaluation corpus and structural validators
        |
        +--> deterministic inventory generation
        |
        +--> generated Work Mode packages
        |
        +--> generated claude.ai Custom Skill ZIP packages
        |
        +--> project-scoped read-only reviewer/verifier agents
        |
        v
fresh evidence, diff review, tests, and release checks

host-provided: model runtime, Codex built-ins, GitHub, Context7, OpenAI docs,
               and Luna worker definitions
```

### Source and generated boundaries

- The marketplace file identifies the repository's first-party plugin; the
  plugin manifest identifies its name, version, public metadata, and skill root.
- Each `skills/<name>/SKILL.md` is the workflow contract. Its
  `agents/openai.yaml` carries the restricted user-facing Codex metadata and
  default prompt for that skill.
- The Claude Code marketplace and plugin manifest are a second pointer to the same plugin,
  not a second skill source: they resolve skills from the identical `skills/` directory and
  ignore each skill's Codex-only `agents/openai.yaml`.
- Shared references are reusable contracts, not a second copy of a skill's
  entire body.
- The Work Mode manifest is a mapping record. `work-mode/dist/` is generated
  output and must not become a hand-edited source tree.
- `docs/inventory.md` is generated output. Counts, lists, and package state in
  it are authoritative only after regeneration or a passing check.
- Routing cases are a test/evaluation source, not an alternative skill
  description. They should express boundaries and expected behavior.

### Runtime and host boundaries

The repository does not provide a model runtime, a local MCP server, connector
credentials, a GitHub service, or a worker daemon. Codex built-ins cover files,
shell, Git, and subagent operations. External services and account-side
installation stay outside the repository unless a future product decision
explicitly creates a new owned boundary with a security and maintenance case.

### Validation and release boundaries

Local scripts validate the repository's own structure and generated state. CI
repeats those checks on the declared operating systems. The release checklist
adds plugin validation, fresh-surface installation checks, representative
routing exercises, and human review. None of these local boundaries proves a
host connector is authenticated or callable; that requires a separate live
verification record.

## 8. Scope and non-goals

### In scope

The project owns reusable coding-agent workflow contracts, their plugin and
portable package metadata, small shared references, routing/evaluation data,
repository contract tooling, generated inventory, generated Work Mode packages,
and the documentation needed to use and maintain those surfaces.

### Deliberate non-goals

- **A random prompt dump.** A prompt belongs only when it has a distinct job,
  ownership, trigger boundary, and maintenance path. Convenience templates may
  remain documentation, but they are not runtime capabilities by default.
- **An MCP server zoo.** The repository does not operate or host a live MCP
  server. Host-provided connectors are documented and verified at the host
  boundary rather than copied into the marketplace. This does not by itself
  exclude *generating* a portable MCP-facing package as a future distribution
  surface — the same way Work Mode and claude-app packages are generated
  artifacts rather than live services — but such a package is a capability
  candidate like any other: it goes through the lifecycle (Section 10) and
  taxonomy (Section 9) before it is added, not assumed from this direction
  alone.
- **An unlimited autonomous agent.** Skills and project agents do not grant
  unrestricted authority, silent publication, credential access, or destructive
  cleanup.
- **A repository-specific hack collection.** Application business logic,
  customer data, migrations, and one-project assumptions belong with the
  application that owns them.
- **An application-hosting or deployment platform.** The repository provides
  workflow contracts and checks, not servers, deployment credentials, or live
  environments.
- **A replacement for Codex, ChatGPT, GitHub, Context7, or host tools.** Those
  systems remain runtime or integration boundaries.
- **A vendor-content mirror.** Research may record source-level mechanisms,
  provenance, licenses, and rejected ideas; it must not turn the active tree
  into copied third-party prompt or dependency content.
- **A dumping ground for experiments and archives.** Experiments need a clear
  active contract or remain outside the active tree. Historical material keeps
  provenance but does not silently become active capability.
- **A collection of near-duplicate skills.** Overlap is a merge, split, or
  retirement signal, not a reason to add another trigger phrase.
- **A giant universal agent or framework.** Composition and explicit phase
  ownership are preferred while the repository remains small and inspectable.
- **Generated-package sprawl.** Generated distributions exist to serve a
  supported surface and must remain traceable to one canonical source.

## 9. Capability taxonomy

Use the following decision rules before adding anything. Every new capability
must have one owner, one reason to exist, a boundary against nearby components,
and proportionate evidence.

### Skill

Create a skill only for a repeated, coherent workflow with a distinct trigger
and a distinct failure boundary. The skill owns its objective, method, output,
and stop conditions. It does not own general file/shell/Git behavior, a project
agent's permission profile, or another skill's phase.

Do not create one for a single prompt, a domain label with no workflow contract,
or behavior already supplied by Codex or a host plugin. Validate frontmatter,
restricted metadata, name/description alignment, routing cases, source links,
and generated Work Mode mapping. Document the user task, positive triggers,
negative triggers, handoffs, and unsupported states in the skill and evaluation
corpus.

### Project agent

Create a project agent only when its tool, permission, or review profile differs
materially from a built-in role. The current reviewer and verifier are justified
by read-only review and evidence-verification profiles. A project agent is not a
renamed default worker and must not become a place to hide broad instructions.

Validate TOML shape, required fields, read-only mode where the role is review or
verification, and the absence of credentials or private environment assumptions.
Document why the profile cannot be expressed as a skill or built-in role.

### Reusable workflow or shared reference

Create a shared workflow/reference when multiple skills need the same phase
ownership, evidence fields, authority rule, or coordination behavior. It should
state the shared contract and handoff, not duplicate all callers. Do not use it
to smuggle an all-purpose agent policy into every skill.

Validate reference paths in generated packages and inspect all affected skills.
Document the consumers and the compatibility impact of changing the contract.

### Prompt or task template

Keep a prompt/template as documentation when it helps a human start a bounded
task but has no independent runtime trigger or validation contract. It may live
under `docs/workflows/` when reused. Do not treat it as an active capability,
duplicate a skill's full body, or add a template merely to increase file count.

Validate links, examples, private-path hygiene, and secret absence. Mark its
status as documentation, not `CURRENT` runtime behavior.

### Script or tooling

Create a script when repository maintenance, packaging, inspection, or evidence
collection is deterministic and repeatedly useful. Keep it dependency-light,
bounded, cross-platform where shared, and non-secret-bearing. Do not create a
script to replace a host service, conceal an external side effect, or automate
activity without a meaningful contract.

Validate normal, malformed, limit, and failure paths as appropriate; include
tests for parsers and generators. Document inputs, output, exit codes, mutation
behavior, and whether it is observational or write-producing.

### Validation rule

Add a validator rule when a structural or source-of-truth contract can be stated
deterministically and a violation would cause incorrect packaging, unsafe path
handling, misleading metadata, broken links, or release drift. Do not encode
subjective workflow quality as a parser rule.

Validate both the passing repository and focused adversarial fixtures. Document
the contract, error boundary, and what the rule cannot prove.

### Test or evaluation case

Add a unit/contract test for stable executable behavior or malformed/boundary
handling. Add a routing case for trigger selection, precedence, negative
activation, authority, or stop behavior. Add a model-backed evaluation only when
the cost is acknowledged and a human will review the result.

Do not add tests that merely assert prose exists, recreate stale historical
results, or claim broad quality from a narrow fixture. Document the scenario,
expected observable outcome, boundary, and owning source.

### Configuration

Add configuration only when a host or repository contract needs a declarative
profile that the repository can safely validate without executable content. The
host-readiness profile is an example: it names required, recommended, and
optional capabilities, but does not contain credentials or prove callability.

Validate schema, allowed fields, path scope, duplicate requirements, and safe
failure behavior. Document ownership, severity, freshness, and the difference
between configuration evidence and live proof.

### Generated distribution content

Generate distribution content when a supported host surface needs a different
package layout or reference resolution from the canonical source. Keep the
manifest explicit and the generator deterministic. Do not hand-edit generated
files to fix a source problem or add a host surface without an owner decision.

Validate source-to-output equality, package-local references, portability,
symlink/path safety, secret absence, and stale-output detection. Document the
source path, target surface, generator command, and account-side limits.

### Research documentation

Use research documentation to record source-backed mechanisms, decisions,
provenance, licenses, rejected alternatives, and stop rules. It is not a
runtime dependency and does not become a feature merely because a candidate was
interesting.

Validate source links and attribution where relevant. Document the date or
version boundary and the decision the research supports. Refresh it when stale
facts could change an active decision.

### Integration documentation

Use integration documentation to describe host-provided services, ownership,
transport/auth boundaries, write risk, and verification procedures. It must not
turn a host integration into a repository-owned dependency.

Validate that examples contain no credentials, that claims name their evidence
level, and that the document distinguishes configuration from a harmless live
call. Record unresolved setup or authentication as `UNVERIFIED`.

### Host-provided capability

Treat a capability as host-provided when Codex, the account, a worker runtime,
or an external service owns its installation, authentication, availability, or
side effects. The repository may declare a requirement or explain how to verify
it. It must not copy the host definition, claim ownership, or store credentials
without a separate product decision.

Validation is a live, environment-specific proof pack: registration,
authentication category, harmless callable operation, and relevant write
controls. Repository configuration alone is never enough.

### Outside the repository

Keep material outside the active tree when it is application-specific, private,
credential-bearing, a large research corpus, a disposable experiment, a vendor
dependency without a clear redistribution/maintenance case, or a host feature
the repository does not own. “Outside” is a product boundary, not a failure to
organize a file.

## 10. Capability lifecycle

The lifecycle is:

```text
need identified
  -> inspect existing capabilities and built-ins
  -> classify ownership and capability type
  -> research current facts when needed
  -> design the smallest distinct contract
  -> implement canonical source
  -> validate structure and boundaries
  -> evaluate behavior and routing
  -> document use, limits, and provenance
  -> package or distribute supported surfaces
  -> release with compatibility evidence
  -> maintain and refresh evidence
  -> deprecate with migration guidance
  -> remove or archive with provenance
```

### Entry rules

- Search existing skills, shared references, built-ins, and host plugins before
  adding a new capability.
- A new skill requires repeated real requests for one coherent unsupported
  workflow, not an attractive topic or a single edge case.
- Alternatively, a new skill may enter through explicit owner-directed
  capability expansion when deliberate research demonstrates a coherent
  unsupported workflow, a distinct deliverable, clear routing and authority
  boundaries, an implementation plan, and validation proportionate to the
  capability. Record such additions as owner-directed in
  [`audit-findings.md`](./audit-findings.md) and
  [`research/capability-expansion-ledger.md`](./research/capability-expansion-ledger.md);
  never describe them as satisfying the repeated-demand path.
- A project agent requires a materially different tool or permission profile.
- A host feature should replace local functionality when the host already owns
  the same capability safely and the repository gains no durable contract by
  wrapping it.
- A cross-skill concern belongs in shared coordination only after the repeated
  boundary is demonstrated; do not create architecture before the need exists.

### Evolution rules

- Merge overlapping skills when their trigger, phase, and authority boundaries
  are substantially the same.
- Split a skill when it has multiple independent jobs, conflicting permissions,
  or an output contract that cannot remain clear.
- Keep generated artifacts synchronized from canonical source; a generated diff
  is a symptom to investigate, not a new source of truth.
- For a breaking workflow or package change, document the migration, affected
  surfaces, compatibility decision, and deprecation window before release.

### Exit rules

Deprecate a capability when a host now supplies it, the use case is no longer
distinct, maintenance cost exceeds value, or it cannot meet the project's
authority/safety boundary. Mark it `HISTORICAL` only when provenance is useful;
otherwise remove it with links or migration notes where users could reasonably
depend on it. Never leave an unowned parallel copy “for convenience.”

## 11. Distribution model

### Current surfaces

| Surface | What the repository provides | What it does not prove |
| --- | --- | --- |
| Repository-native checkout | Source, docs, scripts, tests, marketplace definition, and generated artifacts. | That any host has loaded the repository or that a user has the prerequisites. |
| Codex plugin | `coding-workflows` through the repository marketplace, with canonical skills under `plugins/coding-workflows/skills/`. | Installation, enablement, session refresh, or model behavior in a user's profile. |
| Claude Code plugin | `coding-workflows` through the repository's Claude Code marketplace (`.claude-plugin/marketplace.json`), resolving the identical `plugins/coding-workflows/skills/` tree the Codex plugin uses. | Installation, enablement, session refresh, or model behavior in a user's profile. |
| ChatGPT Work Mode | Generated portable skill directories under `plugins/coding-workflows/work-mode/dist/`, mapped by the Work Mode manifest. | Account-side installation, availability, synchronization, role, region, workspace policy, or cross-device state. |
| claude.ai Custom Skills | Generated per-skill ZIP packages under `plugins/coding-workflows/claude-app/dist/`, mapped by `plugins/coding-workflows/claude-app/manifest.json`. | Account-side upload, enablement, per-user synchronization, or code-execution availability. |
| Host readiness | A redacted inspection and configuration-readiness report from `scripts/host_toolbox.py`. | External MCP callability, successful login, or permission to perform a consequential action. |

### Distribution strategy

The near-term strategy is one canonical source with generated target packages:

1. author and review the skill under `plugins/coding-workflows/skills/`;
2. update the plugin metadata, routing cases, and manifest only when the source
   contract changes;
3. run the repository and package checks;
4. use direct Agent Plugins or Agent Skills routes where documented, generated
   Gemini and Kimi wrappers where their host contracts require them, and select
   the Work Mode or claude.ai package for the target account surface;
5. state the account-side and host-side limits explicitly.

Public plugin-directory or registry submission and signed release artifacts
remain `PLANNED`. The project does not promise automatic installation or
synchronization; host-side installation must be verified separately.

## 12. Host capability model

Use four levels for every external capability:

1. **Repository-owned capability:** source, contract, and maintenance live here.
2. **Configured host capability:** a repository profile or host listing names a
   plugin, worker, or MCP server.
3. **Detected host capability:** the host command returned a parseable or
   contract-valid status in one environment.
4. **Verified callable capability:** a harmless authorized operation succeeded in
   the relevant host/session and the proof records its limits.

Only the first level is repository implementation. The latter three are
environmental evidence with limited freshness.

The Host Capability Doctor fits between configured and detected state. It:

- reads redacted Codex plugin/MCP listings and expected host-level worker files;
- validates `config/host-readiness.json` without accepting executable content;
- distinguishes missing, invalid, unknown, and satisfied requirements;
- returns readiness states such as `ready`, `degraded`, and `not_ready`;
- never installs, logs in, changes configuration, reads credential values, or
  calls an external MCP tool.

The default profile currently expresses a required repository plugin, required
host-level Luna worker contracts, a recommended GitHub capability, and optional
Context7 capability. The `authenticated` fields in that JSON are requirements
for a report, not credentials or proof. Public documentation must present these
as host prerequisites or optional integrations, never as bundled product
features.

## 13. Validation and evaluation model

### Automated repository proof

The normal local and CI checks prove different layers:

- `scripts/validate-repository.py` proves structure, metadata, path containment,
  symlink safety, closed Claude and Cursor boundaries, semantic agent parity, the
  audit ledger, semantic CI workflow shape, required files, link integrity, routing
  data, generated package contracts, and bounded text hygiene.
- `scripts/generate-inventory.py --check` proves the checked-in inventory is
  the output of current source.
- `python scripts/package-work-mode.py --check`, `python scripts/package-claude-app.py --check`,
  and `python scripts/package-agent-skills.py --check` prove their respective portable
  packages are valid and byte-for-byte deterministic relative to canonical skill
  source. `validate-repository.py` imports the same modules' structural validators
  (package existence, manifest shape, `SKILL.md` metadata, and reference
  containment), but not their rebuild-and-compare determinism check, so CI invokes
  all three `--check` commands directly.
- `python -m unittest discover -s tests -v` exercises parser, generator,
  adversarial boundary, host-report, and repository-contract behavior.
- `scripts/routing_evals.py` validates and previews the labeled routing corpus
  without model calls. Its current corpus size belongs to the script output and
  is intentionally not repeated here.
- GitHub Actions (`.github/workflows/validate-repository.yml`) run the repository-
  owned semantic workflow check, `scripts/validate-repository.py`,
  `scripts/generate-inventory.py --check`, all three generated-package checks,
  `python -m unittest discover -s tests -v`,
  `python -m compileall -q scripts tests`, and a
  full event-base `git diff --check` on Ubuntu and Windows. The exact release
  candidate must be checked again.

These checks are necessary but not sufficient. Markdown validity does not prove
that a skill gives useful advice, and a green inventory check does not prove
that a host can call GitHub, Context7, or a Work Mode package.

### Behavioral maturity evidence

A workflow or capability is mature enough for a public promise only when the
evidence appropriate to it covers:

- trigger accuracy and negative-trigger resistance;
- phase, scope, and authority correctness;
- usefulness of the output for the intended user task;
- failure behavior and honest handling of missing access;
- deterministic behavior where the contract requires it;
- Windows/Ubuntu or other declared portability boundaries;
- generated-package correctness and source traceability;
- regression coverage for known contract failures;
- documentation accuracy against live implementation.

Model-backed routing runs are supporting evidence only after human review. Live
browser, connector, account, or publication claims need their own direct proof
and must not be inferred from local files.

## 14. Public-release program

Public release is a product milestone with a gate, not a repository visibility
toggle. The aim is that a stranger can understand, install, use, validate, and
contribute without knowing the maintainer's private environment.

### Public-readiness findings from the inspected repository

These findings are evidence-bounded. They identify work for the roadmap; they do
not claim a secret, external state, or historical fact that was not observed.

| Label | Finding | Evidence path | Program consequence |
| --- | --- | --- | --- |
| `PUBLIC-BLOCKER` | The repository is private (owner-stated); the local tree cannot establish GitHub visibility or settings. A stranger-path installation test from a clean environment has not been run. | `README.md`, `CLOUD_CODING_SETUP.md` | Confirm repository identity and visibility through an authorized owner view before a public V1 claim; run the clean-environment stranger-path test named in this section's readiness workstreams. |
| `PUBLIC-BLOCKER` | Version `1.5.0` and its changelog section are prepared, but the section is undated and the inspected tree establishes no tag or GitHub release. | `CHANGELOG.md`, `docs/releasing.md`, `plugins/coding-workflows/.codex-plugin/plugin.json` | Owner must execute a separately authorized tag/release, date the changelog section, and verify the exact candidate before calling the project a released V1. |
| `PUBLIC-READINESS` | A versioned public host support matrix and troubleshooting guide now record host routes, repository checks, review date, and runtime limits. Clean-environment installation and workflow evidence remain open. | `README.md`, `docs/host-support.md`, `docs/host-troubleshooting.md` | Keep claims aligned with the matrix and complete the stranger-path installation test before a public V1 claim. |
| `DISTRIBUTION` | Work Mode generation and package validation are repository-owned and current, while account installation, enablement, synchronization, and availability are explicitly unverified. | `docs/work-mode.md`, `plugins/coding-workflows/work-mode/manifest.json`, `scripts/work_mode_packages.py` | Public V1 may promise generated artifacts and documented selection, not automatic account delivery. |
| `METADATA` | Plugin metadata contains repository-owned homepage, repository, license, keyword, and display fields; GitHub repository description, topics, and visibility settings are not established by the local tree and may lag the repository (for example, a description that still states an older skill count). | `plugins/coding-workflows/.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` | Owner must review public repository metadata separately; do not infer it from local manifests. |
| `SECURITY` | The repository has a security policy, secret ignore patterns, path/symlink defenses, bounded validation, and checkout credential hardening. A history privacy scrub was completed (owner-reported), but the required local checks do not by themselves prove absence of secrets in all history, ignored artifacts, or external settings. | `SECURITY.md`, `.gitignore`, `scripts/validate-repository.py`, `.github/workflows/*.yml` | Repeat the public-history, workflow-permission, asset, and supply-chain review on the release candidate before any visibility change. Do not weaken fail-closed checks to make the gate pass. |
| `LICENSING` | MIT licensing is present. The research ledger records third-party sources and licenses and says mechanisms were adapted rather than copied, but public release still requires an owner review of bundled assets, attribution, and repository history. | `LICENSE`, `docs/research/agent-skill-ecosystem-raid.md`, `plugins/coding-workflows/assets/` | Resolve attribution and redistribution questions before publishing bundled material; this document makes no legal conclusion. |
| `QUALITY` | Structural and routing evaluation machinery is current, but model-backed behavior remains opt-in and human-reviewed; local checks do not establish universal workflow quality. | `docs/evaluations.md`, `plugins/coding-workflows/evals/trigger-routing.json`, `tests/test_repository_tools.py` | Scope V1 quality guarantees to tested contracts and publish the limits plainly. |
| `OPTIONAL` | A small number of operational notes are identified by the generated inventory as possible removal candidates if they stop being reused; see `CHANGELOG.md` for a record of past removals made on this basis and `docs/inventory.md` for the current candidates. | `docs/inventory.md`, `scripts/repository_inventory.py` | Do not remove the remaining ones as part of release hygiene without evidence of disuse and a separately bounded cleanup decision. |

### Readiness workstreams

Before visibility changes, the owner should complete these in order:

1. **Identity and metadata:** settle the public description, homepage, topics,
   examples, supported surfaces, and whether the public name remains the right
   name. Keep the public README short and accurate.
2. **Stranger installation:** test clone, prerequisites, Codex plugin setup, a
   representative workflow, validation, and Work Mode package selection from a
   clean supported environment. Record account-side limits separately.
3. **Hygiene and legal review:** inspect tracked history, ignored outputs, local
   paths, private URLs, credentials, environment files, personal assumptions,
   generated debris, vendor material, asset provenance, and attribution.
4. **Release and security review:** confirm CI permissions, pinned actions,
   unsafe scripts/hooks, symlink/path behavior, package boundaries, security
   reporting, changelog/version choice, rollback/deprecation expectations, and
   exact release verification.
5. **Public support model:** define what issues are supported, how contributors
   propose capabilities, what host integrations are optional, and what the
   project deliberately will not troubleshoot.

## 15. Public V1

### V1 boundary

Public V1 is the neutral, multi-agent pack described in Section 2 — not a
narrower Codex-and-Claude-only release. It has two tiers.

**Already built (`CURRENT`), the foundation V1 ships on:**

- the first-party `coding-workflows` plugin and repository marketplace for
  Codex, and the equivalent Claude Code plugin marketplace;
- the canonical focused skills in `plugins/coding-workflows/skills/`;
- the current read-only project-agent model, including reviewer and verifier;
- source-backed repository validation, deterministic inventory generation, and
  contract tests;
- labeled routing evaluation data and a free dry-run evaluator;
- generated, validated Work Mode, claude.ai Custom Skills, portable Agent
  Skills, Gemini CLI, and Kimi Code package artifacts from one canonical source;
- a versioned host support matrix, source review, and host troubleshooting path;
- the host capability model and configuration-only doctor as inspection tools;
- documentation for installation, workflow selection, validation, Work Mode,
  claude.ai Custom Skills, contribution, security, and release preparation.

**Remaining release work (`PARTIAL`):**

- complete the stranger-path and owner review for the documented compatibility
  matrix;
- run live install and invocation checks for hosts selected for stronger-than-
  structural claims;
- evaluate whether a generated MCP-facing package belongs in that set, subject
  to the Section 8 boundary between packaging and operating a server;
- separately authorize any public repository or marketplace publication.

This is the intended product boundary, not a release claim. The implemented
tier is repository evidence; remaining live tests and external publication are
separate gates. The public-release program (Section 20) must
still close stranger-path, metadata, and legal/security review gaps.

### Supported V1 path

The supported repository/tooling baseline should be:

- Git and Python 3.11 or newer for repository tooling;
- each supported host's own documented installation or import path in
  [`docs/host-support.md`](./host-support.md), with repository compatibility
  kept separate from live installation proof;
- Windows and Ubuntu for the shared repository checks, because those are the CI
  surfaces currently declared;
- ChatGPT Work Mode and claude.ai Custom Skills package artifacts as
  separately documented distribution paths, with account-side installation
  treated as host-dependent;
- no local service, package-install bootstrap, MCP server, or connector
  credential required to run repository validation.

### V1 quality promise

Public V1 may guarantee that the repository checks its declared structural
contracts, keeps generated inventory and all declared distribution packages
tied to canonical source, provides focused workflow boundaries, and
documents what local checks cannot prove. It may not guarantee that an agent
always chooses the right skill, that a host connector is authenticated, that a
model's answer is correct, or that a user's account can install a package.

### Not V1

The following stay experimental, host-dependent, unsupported, or deferred:

- automatic account installation or synchronization;
- public plugin-directory submission until separately decided and verified;
- claiming a specific coding-agent host as supported before it has its own
  documented compatibility contract (Section 9, Section 10) — growth itself is
  not excluded from V1, an unverified claim of support is;
- repository-owned, live MCP servers or connector credentials (a generated
  MCP-facing package is a different question — see Section 8);
- application-specific code, deployment workflows, and customer data;
- unlimited autonomous write or publication authority;
- a promise that optional model-backed evaluations are exhaustive;
- extra project agents without a distinct permission or tool rationale.

### Current versus release work

| Classification | V1 interpretation |
| --- | --- |
| Already complete locally | Canonical plugin/skill layout, read-only project agents, repository checks, inventory generator, Work Mode, claude-app and Agent Skills generators, host support matrix, routing corpus/runner, security/contribution/release docs, and cross-platform CI contracts. |
| Needs cleanup | Any remaining stranger-facing assumptions found during fresh clean-environment use and review. |
| Needs verification | Clean-environment installation, public metadata, exact CI health for the release candidate, public-history secret review, asset/vendor attribution, host/account behavior, and representative user flows. |
| Needs documentation | Owner-approved final V1 promises, compatibility/deprecation policy, and the limits already recorded in the host matrix and troubleshooting guide. |
| Needs implementation | Any actionable findings from the clean-environment and release-candidate reviews. Phase 1 research and repository packaging are implemented and remain `PARTIAL` only for want of live host evidence. |
| Deliberately deferred | Automatic synchronization, repository-owned live external services, claiming host support without a compatibility contract, giant agents, and speculative ecosystem machinery. |

## 16. Public V1 definition of done

The repository is ready for a public V1 only when every required gate below is
verified or an owner explicitly accepts a documented exception. “The repository
is public” is not itself evidence that these gates passed.

### Identity and user experience

- A stranger can explain the project from the README in one sitting.
- The public description, repository metadata, plugin metadata, examples, and
  links agree on the product and its supported surfaces.
- The clean-environment path works without knowledge of a private Forge,
  maintainer checkout, or personal account state.
- Unsupported host, account, browser, connector, and publication paths are
  labeled instead of implied.

### Documentation and contribution

- Installation, prerequisites, workflow selection, agents, Work Mode, validation,
  troubleshooting, architecture, security reporting, contribution, and release
  preparation are linked and internally consistent.
- `CONTRIBUTING.md` and the pull-request template describe source-of-truth,
  generated-file, test, review, and no-secret expectations.
- The README remains public orientation; this program remains the full product
  and implementation map.

### Hygiene, security, and legal review

- No secrets, private configuration, environment material, credentials, cookies,
  private URLs, personal machine paths, or private payloads are exposed in the
  release tree or public-facing examples.
- Public history, ignored artifacts, hooks, CI permissions, action pins,
  path/symlink handling, generated packages, and supply-chain assumptions have
  been reviewed.
- MIT licensing, third-party attribution, bundled assets, adapted research
  mechanisms, and redistribution constraints have an owner-approved record.
- Archive and vendor boundaries are intentional and no retired material is
  accidentally packaged.

### Structural and quality proof

- Repository validation, generated inventory check, Work Mode package check,
  contract tests, routing dry run, Markdown/link hygiene, and diff whitespace
  checks pass on the supported release candidate.
- CI is healthy on each declared operating system for that exact candidate.
- The canonical skill source and generated distributions are deterministic and
  free of stale or hand-patched output.
- Representative direct, indirect, negative, and edge workflow cases have been
  reviewed for routing, authority, failure behavior, and useful output.
- No public text claims host installation, authentication, callable tools,
  account synchronization, or model quality without direct evidence.

### Release and compatibility

- The owner has chosen the plugin/project version from actual user-visible
  compatibility impact and moved the relevant changelog entries into a dated
  release section.
- The exact tag/release artifact, generated packages, and plugin metadata agree.
- The release procedure, rollback/deprecation path, and security-reporting path
  are usable by someone other than the maintainer.
- All launch blockers from the readiness findings are resolved or explicitly
  accepted with a reason, scope, owner, and follow-up.

The current repository does not meet this gate solely from the inspected local
state: the repository is private, the `1.5.0` changelog section is undated and
unpublished, and public metadata, clean-environment proof, and release proof
remain separate work or owner decisions. Host and account proof is required
only for claims that V1 chooses to make about those external surfaces; otherwise
it must be explicitly scoped out.

## 17. Contributor model

Contributors start with `AGENTS.md`, `WORKFLOWS.md`, this program, and the narrow
document closest to the proposed change. They should then:

1. identify the user problem and inspect existing capabilities, Codex built-ins,
   and host boundaries;
2. classify the proposal using the taxonomy and record why the existing
   capability cannot own it;
3. choose the smallest source change and name generated or test surfaces;
4. validate the source, routing, generated outputs, and relevant contracts;
5. review the complete diff, documentation accuracy, security boundary, and
   deliberate exclusions.

A new skill proposal should include its distinct job, positive and negative
   triggers, authority boundary, output contract, handoffs, and validation plan.
An agent proposal should include its permission/tool difference. A generated
file change should identify its canonical source and generator. A public-facing
change should identify claims that remain unverified.

Reviews should judge the actual diff first, use risk-sensitive lenses, and keep
findings tied to the changed surface. Breaking changes require a compatibility
decision; cosmetic churn and file count are not reasons to expand scope.

## 18. Maintainer model

Recurring maintenance should protect the contracts that prevent drift:

- regenerate or check `docs/inventory.md` after capability/source changes;
- regenerate or check Work Mode packages after skill/reference changes;
- keep plugin metadata, skill metadata, routing cases, and changelog aligned;
- run repository tests and cross-platform CI for structural changes;
- review host-readiness assumptions and integration notes without exposing
  credentials;
- refresh routing/evaluation cases when triggers or boundaries change;
- audit public documentation for private assumptions and claim inflation;
- perform security, asset, attribution, and supply-chain review before releases;
- prepare version/changelog changes only for an actual user-visible release;
- maintain deprecation, migration, and removal notes when a capability leaves.

Automation is worthwhile when it detects drift, unsafe paths, broken links,
invalid metadata, or stale generated output. The current inventory, package,
validation, and CI tools are justified by those failure modes. New automation
should earn the same proof and maintenance cost.

## 19. Versioning and compatibility

The plugin manifest is the current version identity for the installable
`coding-workflows` package. Its exact version is authoritative in
`plugins/coding-workflows/.codex-plugin/plugin.json` and the generated inventory;
this program must not duplicate it as a permanent fact. The changelog currently
uses an Unreleased section and the release document says to choose a semantic
version from user-visible compatibility impact.

Until the owner decides otherwise, use these compatibility questions for every
release:

- Does the change alter a skill's trigger, authority, output, failure behavior,
  or required host capability?
- Does it alter plugin metadata, package layout, generated references, manifest
  schema, routing case meaning, or required Python version?
- Does a contributor or user need to migrate a prompt, installation step,
  generated package, or project-agent expectation?

If yes, treat the change as potentially breaking, document the impact, decide
the version and deprecation path, and update the changelog. Do not invent a
project-wide semantic-versioning promise for unversioned documentation or
host-account behavior. The exact public compatibility matrix and deprecation
window are `PLANNED` owner decisions.

## 20. Roadmap

The roadmap is capability-based rather than date-based. A phase is complete only
when its acceptance criteria are evidenced and its deliberate exclusions remain
true.

### Phase 0 — Canonical program and truth cleanup

**Status:** `CURRENT` for the program document; ongoing truth maintenance.

**Objective:** Establish one durable product brain and keep architectural truth
separate from volatile inventory and host snapshots.

**Required work:** maintain this program, link it from the documentation index,
reconcile contradictions as they are found, and keep current/partial/planned
labels honest.

**Complete when:** the program exists at `docs/coding-agents-program.md`, its
  authority hierarchy is clear, its current snapshot points to live sources, and
  no roadmap sentence is used as implementation proof.

**Dependencies:** live repository inspection and owner decisions recorded in
Section 24.

**Excludes:** implementation changes, repository visibility changes, release
publication, and cleanup unrelated to the document.

### Phase 1 — Multi-agent research and packaging

**Status:** `PARTIAL`. Primary-source research and repository-owned generated
packages now cover the routes in
[`docs/host-support.md`](./host-support.md); no host installation has been
live-verified.

**Objective:** Extend the existing host surfaces into the vendor-agnostic pack
described in Section 2, retaining direct standard-compatible routes where a
generated duplicate is unnecessary and generating packages where hosts require
their own wrapper.

**Required work:** keep primary-source host research current; maintain the
compatibility contract and status for each selected host; validate generated
packages from canonical skills and references; add package drift checks to
cross-platform CI; and keep the inventory and Section 6/11 snapshots aligned.

**Complete when:** every matrix route has a documented install/import path and
repository validation story; generated outputs are deterministic and checked
in CI; direct standards are validated without duplicate trees; and claims
distinguish structural compatibility from harmless live installation and
invocation evidence.

**Dependencies:** none; this can start independently of Phase 0's cleanup.

**Excludes:** unsupported live-runtime claims; repository-identity claims beyond
what Section 2 states; operating a live MCP server (Section 8).

### Phase 2 — Public-readiness audit

**Status:** `PARTIAL`. The repository has strong policy, security, contribution,
validation, packaging, and release foundations; the complete public audit is not
complete.

**Objective:** Make the public boundary credible to a stranger.

**Required work:** complete owner identity/metadata review, run a clean-environment
installation and use path, repeat the public-history and ignored-material audit
on the release candidate (a history privacy scrub is already complete,
owner-reported), review assets/vendor/legal provenance, inspect workflows and
actions, and record any accepted exceptions to the support matrix or V1 gates.

**Complete when:** every Public V1 definition-of-done gate has a fresh result or
an explicit owner-accepted exception, with no unresolved `PUBLIC-BLOCKER`.

**Dependencies:** owner decisions on public identity, metadata, compatibility,
and release scope.

**Excludes:** automatic host synchronization, new integrations, and speculative
features discovered during the audit.

### Phase 3 — Public V1

**Status:** `PARTIAL`. Version `1.5.0`, its changelog section, the manifests, the
host matrix, and the generated packages are prepared as the release candidate.
Phase 2 gates, the dated release record, and every external publication step
remain open.

**Objective:** Publish the bounded product promised in Section 15 with a real
version and a reproducible release record.

**Required work:** complete Phase 2, finalize the public README and support
matrix, confirm the version, date the changelog section, validate the exact
candidate, and perform separately authorized tag/release/publication actions.

**Complete when:** the exact public V1 artifact, plugin metadata, generated
packages, documentation, and release record agree and the V1 gate is signed off.

**Dependencies:** Phase 2, owner authorization for external publication, and
healthy supported CI.

**Excludes:** promises about account-side installation or unverified host tools.

### Phase 4 — Distribution and installation maturity

**Status:** `PARTIAL`. Codex and Claude Code marketplaces, Work Mode and claude.ai
packages, a versioned host matrix, portable Agent Skills, and Gemini/Kimi packages
exist. Fresh host installation and invocation evidence remains incomplete.

**Objective:** Make supported installation surfaces predictable without creating
parallel sources.

**Required work:** keep the support matrix current; test fresh installation and
refresh behavior where authorized; refine package selection and troubleshooting;
and decide whether a public plugin directory or registry submission is worth its
maintenance cost.

**Complete when:** every supported surface has a documented install/use path,
version compatibility rule, generated artifact proof, and explicit unsupported
boundary.

**Dependencies:** Public V1 identity and owner decision on distribution targets.

**Excludes:** automatic synchronization without a reliable host-owned mechanism.

### Phase 5 — Evaluation and quality maturity

**Status:** `PARTIAL`. The deterministic corpus and evaluator exist; behavioral
quality evidence remains deliberately human-reviewed and selective.

**Objective:** Measure workflow quality without pretending that routing or
Markdown checks are universal model evaluation.

**Required work:** maintain representative direct/indirect/negative/edge cases,
define review criteria and a small reproducible behavioral sample, track failure
classes, and add regression cases only for observed contract failures.

**Complete when:** each public workflow has a maintained trigger/boundary suite,
documented quality limits, reviewed representative evidence, and a clear response
to regressions.

**Dependencies:** stable V1 contracts and human review capacity.

**Excludes:** expensive exhaustive model benchmarking and quality claims for
unsupported hosts.

### Phase 6 — Contributor and ecosystem maturity

**Status:** `PLANNED`.

**Objective:** Let outside contributors extend the system without eroding
  coherence.

**Required work:** refine proposal/review examples, document compatibility and
  deprecation, publish a small extension contract, and identify which external
  integrations are documentation-only versus worth a separate ownership case.

**Complete when:** a contributor unfamiliar with the private origin can add or
  change a bounded capability, run checks, understand generated output, and
  receive a reviewable answer about scope and compatibility.

**Dependencies:** public V1 feedback and evidence of repeated extension needs.

**Excludes:** heavyweight governance, broad plugin sprawl, and a marketplace of
  unreviewed third-party prompts.

### Phase 7 — Bounded capability expansion

**Status:** `CURRENT` for the owner-directed 2026-09 tranche; `FUTURE` for
demand-gated expansion beyond it.

**Owner-directed expansion (2026-09):** the owner directed eight researched
capabilities (`CAP-04` through `CAP-11` in the audit ledger) through the
owner-directed entry path in Section 10 ahead of the demand gate. All eight are
implemented and `verified_repository` in the ledger; live host smoke evidence
remains separate. That exception does not relax the demand gate for other
candidates, which stays the rule for everything after this tranche.

**Objective:** Add genuinely repeated workflow capabilities or supported surfaces
  only when the evidence justifies ownership and maintenance cost.

**Required work:** evaluate each candidate through the lifecycle, prefer merge or
  host delegation when appropriate, add new source/validation/distribution
  contracts only when necessary, and preserve the invariants below.

**Complete when:** each expansion has a distinct user problem, owner boundary,
  compatibility story, quality evidence, and a removal path.

**Dependencies:** mature public V1 maintenance and demonstrated demand.

**Excludes:** an autonomous framework, local service platform, MCP zoo, and
  abstractions whose cost exceeds the repeated problem they solve.

## 21. Long-term target state

A mature `coding-agents` installation should feel small and dependable: a user
can identify the right workflow, the agent inspects the relevant source and
authority boundary, the work produces a useful artifact or review, and the final
claim points to fresh evidence. Installation surfaces are explicit, generated
packages are reproducible, compatibility is visible, and failures explain what
was unavailable rather than filling the gap with confidence.

The project should own workflow contracts, composability rules, package
generation, deterministic repository checks, routing/evaluation structure, and
documentation of its trust boundaries. It should leave models, host tools,
external service auth, account policy, customer data, and live deployments to the
systems that own them.

The ecosystem that can reasonably grow around it is a small set of focused,
reviewable skills and perhaps declared distribution adapters. Third-party
contributions should fit the same trigger, authority, validation, provenance,
and compatibility model. Growth must be controlled by distinct jobs, generated
source traceability, removal paths, and a bias toward merging or delegating
before adding.

What should remain simple:

- no local service is required to validate the repository;
- shared maintenance tooling remains dependency-light;
- a skill remains readable at its entry point;
- host integrations remain named boundaries rather than copied infrastructure;
- release proof remains more important than automation volume.

## 22. Architectural invariants

Future work must preserve these rules unless an owner explicitly changes the
program and the affected compatibility contract.

1. There is one canonical authored source for each workflow capability.
2. Generated inventory and distribution artifacts are derived, checked, and
   never casually hand-edited.
3. Live implementation and verified external state outrank stale documentation
   snapshots.
4. A capability is not current merely because it is named in configuration or a
   roadmap.
5. External capability claims require evidence at the level claimed.
6. Skills remain bounded, composable, non-duplicative, and explicit about
   handoffs and negative triggers.
7. A new project agent must earn its distinct permission or tool profile.
8. Repository-specific application logic and private data stay outside reusable
   workflows.
9. Secrets never enter source, generated distributions, examples, tests, or
   public evidence.
10. Validation accompanies new structural, packaging, path, or source-of-truth
    contracts.
11. Public documentation never assumes the maintainer's private environment.
12. Host-provided tools, credentials, authentication, and account state remain
    host-owned unless a separately approved product boundary says otherwise.
13. No commit, push, publication, deployment, release, or destructive action is
    implied by a workflow description or a passing local check.

## 23. Failure modes

| Failure mode | What it looks like here | Prevention |
| --- | --- | --- |
| Agent theatre | A large refactor, ceremony, or automation layer produces activity without a clearer contract or proof. | Smallest bounded change, explicit authority, and evidence-based completion. |
| Giant universal agent | One skill or agent claims orientation, implementation, review, research, and publication. | Phase ownership, composable skills, and distinct project-agent profiles. |
| Skill proliferation | New skills repeat an existing job with different wording. | Search first, use routing negatives, merge overlap, and require repeated need. |
| Prompt graveyard | Templates, experiments, and copied prompts look like supported capabilities. | Classify documentation, research, historical, or outside material explicitly. |
| Unverified integration claim | A manifest or readiness profile is described as a callable authenticated tool. | Four-level host model and direct harmless-call evidence. |
| Stale generated package | `work-mode/dist/` or inventory differs from canonical source. | Deterministic generators, check mode, CI, and no hand edits. |
| Hidden host assumption | Normal use requires a private path, account, connector, or worker without saying so. | Clean-environment test, support matrix, and public-path review. |
| Maintainer-specific documentation | A stranger must know a personal checkout or private Forge flow. | Relative repository paths, public installation instructions, and examples without private state. |
| Attribution drift | Adapted third-party mechanisms or assets lose provenance during editing. | Research ledger, MIT/asset review, attribution record, and no copied distinctive prose. |
| Formatting-only CI confidence | Markdown or inventory passes and is treated as proof of workflow quality. | Separate structural checks, behavioral evaluation, runtime proof, and publication proof. |
| Premature architecture | A new framework, server, or abstraction is added before repeated demand. | Lifecycle entry rules, host delegation, and Phase 7 gate. |
| Private release process | Publishing depends on undocumented personal steps, credentials, or account state. | Public release checklist, exact candidate verification, and separately authorized external actions. |

## 24. Owner decisions

The repository does not contain enough evidence to silently settle the durable
product choices that remain open. They belong to the owner and should be
recorded when decided.

### Settled by the 1.5.0 implementation

These were open earlier and are now answered by what the repository ships.
Revisit them only through the lifecycle and Section 25.

- Generated Work Mode output is a supported artifact with host and account
  limitations (`docs/work-mode.md`, `docs/host-support.md`), not an
  account-delivery promise.
- The agent model is `reviewer` and `verifier` plus host-provided workers; no
  further project agent is justified.
- No generated MCP-facing package ships. Every generated package is skills-only,
  and the repository owns no MCP server. A future MCP-facing package would
  reopen the packaging-versus-operating boundary in Sections 8 to 10 and 15.
- The first public version is `1.5.0`, carried by all plugin manifests and
  checked for parity; the tag and release remain a separately authorized action.
- Rollback and deprecation guidance is in `docs/releasing.md`, and disclosure
  guidance is in `SECURITY.md`.

### Still open

- Which structurally compatible hosts merit live installation and invocation
  testing before any stronger runtime claim is made?
- What release/tag/version policy should govern future breaking skill or
  package changes?
- Should the project pursue a public plugin directory/registry submission after
  V1, and what maintenance cost justifies it?
- What compatibility and deprecation window is acceptable for skill triggers,
  outputs, project agents, and generated package schemas?
- Which contribution expectations are necessary at the project's scale, and
  which community files would be ceremony rather than useful support?
- Which future host integrations, if any, should remain documentation-only and
  which would justify repository ownership?

Until these are decided, the program uses the narrowest plausible V1 promise and
labels the broader direction `PLANNED` or `FUTURE`.

## 25. Maintenance rule for this program

When a future session proposes a material change, it should answer five
questions before editing source:

1. What user problem and product promise does this change serve?
2. Which existing capability, host boundary, or built-in was inspected first?
3. What is the canonical source, and what is generated or downstream?
4. Which authority, validation, evaluation, distribution, and compatibility
   contracts change?
5. What evidence will justify calling the result `CURRENT`, and what remains
   `UNVERIFIED`, `BLOCKED`, `PLANNED`, or `FUTURE`?

If the answer requires changing product identity, public V1 scope, lifecycle,
distribution ownership, major architecture, or an invariant, update this
program in the same bounded change. If it only changes a local procedure, keep
the procedure in its specialized document. If it is only a volatile inventory
fact, regenerate or inspect the authoritative source instead of copying it here.

This is the project's product brain, not a substitute for live inspection. Keep
it opinionated where repository evidence is strong, explicit where the owner
must decide, and replace stale prose with current evidence when the machine
changes.
