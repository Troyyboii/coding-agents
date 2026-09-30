# Agent Skill Ecosystem Raid

> Source ledger for the coding-workflows 1.3.0 upgrade. This repository adapts
> mechanisms in original language; it does not vendor external prompt corpora,
> scripts, or services. The anti-copy check rejects a small set of known distinctive
> phrases; it is not automated proof of universal originality or copyright provenance.
>
> Historical research snapshot: host compatibility state was refreshed on
> 2026-09-23 in [docs/host-support.md](../host-support.md). Use that matrix for
> current supported/deferred/discontinued states.

## Method and stop rule

The sweep covered 30 primary source files or official documents across coding-agent
projects and vendor ecosystems. Search results were leads only: promising candidates
were followed to the specific skill, evaluator, test, implementation, or official
documentation file. The sweep stopped once new candidates mostly repeated the same
high-value mechanisms: narrow trigger contracts, staged context, evidence records,
report-only investigation, and explicit tool fallbacks.

## Bounded ledger policy

This file is a bounded source-and-decision ledger, not an active prompt corpus,
runtime dependency, or historical archive. Keep at most 30 primary-source rows
and 10 provenance rows; when a row is superseded, replace it or record the
rejection reason instead of appending unbounded research. Each row names the
specific source, inspected version or date where relevant, mechanism, local fit,
license or provenance status, and one verdict. Do not store credentials, private
paths, raw model output, transcripts, or copied source material. Refresh only
when a fact could change an active product, security, or compatibility decision.
Otherwise the current host support matrix remains the place for volatile status.
Research never grants implementation or host-runtime authority by itself.

## Candidate ledger

| Project | Specific source inspected | Useful mechanism | Local fit | Reuse note | Verdict |
| --- | --- | --- | --- | --- | --- |
| OpenAI Codex | [skill creator sample](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md) | Concrete triggers, lean entrypoints, and on-demand references. | All skills. | Apache-2.0; original wording. | ADAPT NOW |
| OpenAI plugins | [fix finding](https://github.com/openai/plugins/blob/main/plugins/codex-security/skills/fix-finding/SKILL.md) | Prove a defect is gone and the nearest valid path still works. | Debugging and completion. | Mechanism only. | ADAPT NOW |
| OpenAI docs | [latest model guide](https://developers.openai.com/api/docs/guides/latest-model) | Bounded tool stages and final validation. | Research and verification. | Official-doc guidance, not copied. | MERGE INTO EXISTING SKILL |
| Agent Skills | [official specification](https://agentskills.io/specification) | Discover metadata, load instructions on match, then resources on demand. | Adopted as the portable skill baseline and generated for compatible hosts. | Specification constraints adapted; no prose copied. | ADOPTED; see `docs/host-support.md` |
| Claude Code | [skill development](https://github.com/anthropics/claude-code/blob/main/plugins/plugin-dev/skills/skill-development/SKILL.md) | Progressive disclosure and concrete trigger tests. | Existing skill contracts. | Vendor guidance; mechanisms only. | ADAPT NOW |
| Claude Code | [subagents](https://code.claude.com/docs/en/sub-agents) | Bounded delegated investigation with constrained authority. | Large recon and review. | Host already supplies workers. | MERGE INTO EXISTING SKILL |
| GitHub Copilot | [agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) | Separate project and personal skill surfaces. | Dual-surface documentation. | Vendor guidance; mechanisms only. | ADAPT NOW |
| GitHub Copilot | [adding skills](https://docs.github.com/en/enterprise-cloud%40latest/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) | Skills differ from broad instructions and preserve provenance. | Work Mode distribution. | Vendor guidance; mechanisms only. | DOCUMENT FOR LATER |
| Cursor | [rules](https://docs.cursor.com/context/rules-for-ai) | Always-on, path, and manual activation differ. | Better descriptions only. | Do not add unsupported routing metadata. | DOCUMENT FOR LATER |
| Continue | [rules deep dive](https://docs.continue.dev/customize/deep-dives/rules) | Selective context and explicit read/write policy. | Workflow boundaries. | Apache-2.0; original wording. | MERGE INTO EXISTING SKILL |
| Cline | [Plan and Act](https://docs.cline.bot/core-workflows/plan-and-act) | Stay read-only while uncertainty is unresolved; skip ritual for small work. | Context and design. | Vendor guidance; no planner skill. | MERGE INTO EXISTING SKILL |
| Aider | [repomap.py](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py) | Compact relevance-ranked map before source drill-down. | `repo-xray` path trace. | Apache-2.0; no indexer copied. | ADAPT NOW |
| Trail of Bits | [audit context building](https://github.com/trailofbits/skills/blob/main/plugins/audit-context-building/skills/audit-context-building/SKILL.md) | Record guarantees, dependencies, open questions, and meaningful absence. | `repo-xray` deep mode. | CC-BY-SA-4.0; mechanism rewritten. | ADAPT NOW |
| SourceAtlas | [impact skill](https://github.com/lis186/SourceAtlas/blob/main/plugin/commands/impact/SKILL.md) | Dependents, test impact, and risk in bounded tracing. | `repo-xray`, not a new skill. | Mechanism only. | MERGE INTO EXISTING SKILL |
| Superpowers | [systematic debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md) | One hypothesis, one variable, three-strike design reassessment. | Root-cause debugging. | MIT; no distinctive prose. | ADAPT NOW |
| Superpowers | [testing skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/testing-skills-with-subagents.md) | Pressure scenarios expose workflow loopholes. | Routing evolution. | MIT; deterministic corpus stays primary. | DOCUMENT FOR LATER |
| Vercel | [agent-browser core](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/core/SKILL.md) | Observe, act, then take a fresh snapshot; visual and semantic proof differ. | Browser proof. | Apache-2.0; mechanism rewritten. | ADAPT NOW |
| Microsoft Playwright | [CLI skill](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/skills/playwright-cli/SKILL.md) | Accessibility snapshots and scenario-led tests. | Browser proof and tests. | Mechanism only; no runtime added. | ADAPT NOW |
| Every | [code review](https://github.com/EveryInc/compound-engineering-plugin/blob/main/skills/ce-code-review/SKILL.md) | Risk-sensitive review lenses and report-only default. | Diff judge. | MIT; trim and rewrite. | ADAPT NOW |
| OpenHands | [AGENTS.md](https://github.com/OpenHands/OpenHands/blob/main/AGENTS.md) | Trigger-scoped instruction layers. | Personal/plugin separation. | No local runtime added. | DOCUMENT FOR LATER |
| LangChain DeepAgents | [skills middleware](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/skills.py) | Layer precedence and robust metadata failure handling. | Distribution doctrine. | No middleware copied. | DOCUMENT FOR LATER |
| IronLaw | [repository](https://github.com/Porphyrioon/ironlaw) | Evidence grades and external completion state. | Vocabulary only. | Adds a daemon/governance layer. | SKIP |
| Consensys | [repo security review](https://github.com/Consensys/repo-security-review) | Reachability before severity. | Diff-review concept only. | Duplicates installed security skill family. | SKIP |
| Researcher Agent | [research skill](https://github.com/drader/researcher_agent/blob/main/skills/research/SKILL.md) | Rich claim/provenance matrix. | Future Work Mode research. | CC-BY-NC-4.0; no plugin reuse. | PERSONAL SKILL CANDIDATE |
| Indubitably | [skill index](https://github.com/indubitably-ai/indubitably-skills/blob/master/README.md) | Session archaeology and self-tests. | Personal surface only. | No locally exposed Work Mode corpus. | PERSONAL SKILL CANDIDATE |

## Adopted weapons

- Technical reconnaissance now requires direct source-file inspection, license-aware
  candidate ledgers, source conflicts, and a saturation stop.
- Repository orientation traces a bounded path and records meaningful unknowns.
- Debugging compares a known-good reference, records falsifiable probes, and avoids
  worktree-changing regression hunts without authorization.
- Browser proof gathers a proportional proof pack and refreshes evidence after a
  state transition.
- Tests begin with a concise scenario ledger; reviews select lenses by change risk;
  completion claims record evidence kind, identity, freshness, and limits.

## Adopted-source provenance

This table records the stronger sources actually used for local changes. GitHub
links below were inspected at the named branch or document version on 2026-09-01;
they are readable source references, not a claim that every URL is immutable.

| Project | Authority | Inspected file / ref | License source or status | Mechanism adapted |
| --- | --- | --- | --- | --- |
| Agent Skills | Official specification | [specification](https://agentskills.io/specification), current site version | Specification terms not reused as prose | Portable `name`/`description` limits and package-local references. |
| OpenAI Codex | Vendor implementation | [skill creator sample](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md), `main` | [Apache-2.0](https://github.com/openai/codex/blob/main/LICENSE) | Lean entrypoints and on-demand resources. |
| OpenAI plugins | Vendor implementation | [fix-finding SKILL.md](https://github.com/openai/plugins/blob/main/plugins/codex-security/skills/fix-finding/SKILL.md), `main` | Repository license inspected; no text copied | Prove the original failure is gone plus nearest valid behavior. |
| Trail of Bits | Third-party implementation | [audit-context-building SKILL.md](https://github.com/trailofbits/skills/blob/main/plugins/audit-context-building/skills/audit-context-building/SKILL.md), `main` | [CC-BY-SA-4.0](https://github.com/trailofbits/skills/blob/main/LICENSE) | Guarantees, dependencies, open questions, and bounded absence. |
| Superpowers | Community repository | [systematic-debugging SKILL.md](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md), `main` | [MIT](https://github.com/obra/superpowers/blob/main/LICENSE) | Falsifiable hypothesis discipline; original local wording. |
| Vercel Agent Browser | Vendor implementation | [core SKILL.md](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/core/SKILL.md), `main` | [Apache-2.0](https://github.com/vercel-labs/agent-browser/blob/main/LICENSE) | Fresh observation after browser state change. |
| Playwright | Vendor implementation | [playwright-cli SKILL.md](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/skills/playwright-cli/SKILL.md), `main` | [Apache-2.0](https://github.com/microsoft/playwright/blob/main/LICENSE) | Semantic evidence and scenario-led UI verification. |
| Every Compound Engineering | Community repository | [code-review SKILL.md](https://github.com/EveryInc/compound-engineering-plugin/blob/main/skills/ce-code-review/SKILL.md), `main` | [MIT](https://github.com/EveryInc/compound-engineering-plugin/blob/main/LICENSE) | Risk lenses and report-only review. |

## Rejected on purpose

No generic planner, security-reviewer, subagent manager, visual-regression suite,
research daemon, repository indexer, memory database, hook system, MCP server, or
third-party prompt dump was added. Each either overlaps a host capability or existing
phase owner, needs infrastructure this repository deliberately does not own, or fails
the maintenance-to-repeated-value test.
