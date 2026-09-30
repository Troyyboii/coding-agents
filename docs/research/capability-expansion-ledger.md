# Capability Expansion Ledger

> Bounded provenance and decision ledger for the owner-directed 2026-09
> capability expansion (`CAP-04` through `CAP-11` in
> [`../audit-findings.md`](../audit-findings.md)). It records why each
> capability exists, its boundary, and where its design ideas came from. It is
> not a prompt corpus, a runtime dependency, or a copy of any third-party source.

## Ledger policy

- This expansion entered through the owner-directed path in the capability
  lifecycle of [`../coding-agents-program.md`](../coding-agents-program.md), not
  through the repeated-demand path. Do not describe it as demand-proven.
- Keep one row per capability (eight) and at most twelve source rows. Replace a
  source row when it is superseded; do not append history.
- Record only public sources. Do not store credentials, private paths, raw model
  output, transcripts, or copied third-party text.
- Every implementation in this expansion is original. No third-party prompt
  text, rule list, or script was transplanted. Material under share-alike
  licences (for example CC-BY-SA-4.0) is used for mechanism ideas only, because
  copying its text would impose terms incompatible with this MIT package.
- The owner's excavation brief named additional inspiration projects. They were
  not re-inspected during implementation and nothing from them was reused, so
  they are not listed as sources here.

## Capabilities

| ID | Skill | Why it is additive | Routing boundary | Authority | Implementation form | Status |
| --- | --- | --- | --- | --- | --- | --- |
| CAP-04 | `skill-supply-audit` | No skill judged third-party agent extensions before installation. | Third-party skills, plugins, MCP definitions, hooks; own diffs stay with `diff-judge`, library packages with `dependency-risk`. | inspect; external-read through host tools; local copies of remote material only with authorization; never installs or runs audited content. | Skill, threat-lens reference, offline scanner, shared `cw_scan`. | Implemented locally; live host smoke not run |
| CAP-05 | `spec-trace` | No skill produced per-requirement conformance with a reverse pass. | Requirement-level verdicts; hunk-level defects stay with `diff-judge`. | inspect; external-read for remote specifications. | Skill and matrix reference; no helper. | Implemented locally; live host smoke not run |
| CAP-06 | `repo-instructions` | No skill authored or audited agent instruction files from evidence. | Writing or auditing instruction files; reading them for orientation stays with `repo-xray`. | inspect; local-write when a file change is requested and permitted. | Skill, instruction-surface reference, offline reference checker. | Implemented locally; live host smoke not run |
| CAP-07 | `ci-trust-review` | No skill traced attacker input through CI to execution and privilege. | Attacker paths through GitHub Actions; ordinary workflow diff review stays with `diff-judge`. | inspect; external-read for pinned remote actions. | Skill, trust-model reference, fail-closed workflow locator. | Implemented locally; live host smoke not run |
| CAP-08 | `dependency-risk` | No skill owned measured dependency adoption decisions (mechanism named in `CAP-03`). | Whether depending on a package is acceptable; current facts stay with `live-research`. | inspect; external-read; sending repository-derived package lists outside requires authorization. | Skill, coverage reference, offline npm lockfile inventory. | Implemented locally; live host smoke not run |
| CAP-09 | `session-checkpoint` | No skill saved an explicit, freshness-checkable save point. | Explicit save/resume only; ordinary handoff packets stay with `context-first`. | inspect; local-write of one approved checkpoint file. | Skill, schema reference, Git-only capture/compare helper; explicit invocation only. | Implemented locally; live host smoke not run |
| CAP-10 | `patch-proof` | No skill produced paired baseline-versus-patch execution evidence. | Producing differential evidence; completion verdicts stay with `verification-gate`. | inspect; exec-test in temporary clones after the plan is authorized. | Skill, plan reference, plan-first isolated runner. | Implemented locally; live host smoke not run |
| CAP-11 | `public-release-audit` | No skill audited publication fitness (publication part of `CAP-02`). | Repository fitness for publication; completion of specific fixes stays with `verification-gate`. | inspect; external-read for platform settings; isolated execution only through `patch-proof`. | Skill, gate reference, Git-only tree/history scanner. | Implemented locally; live host smoke not run |

## Design decisions

- Isolated execution for `patch-proof` and `public-release-audit` uses two plan
  modes in one runner, `differential` and `single_revision`, rather than a shared
  execution primitive. A shared module that starts processes would extend the
  subprocess allowance to every skill that imports it; keeping execution in
  `patch-proof/scripts/proof_run.py` confines it to one reviewed helper.
  `public-release-audit` hands outsider reproduction to that runner in
  `single_revision` mode, whose result is never called a patch proof.

## Sources

| Source | Used for | Capabilities | Reuse note |
| --- | --- | --- | --- |
| [Agent Skills specification](https://agentskills.io/specification) | Skill folder layout, optional `scripts/` and `references/` directories. | all | Specification constraints; no prose copied. |
| [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions) | Script injection, untrusted input, token and third-party action guidance. | CAP-07, CAP-11 | Vendor documentation; mechanisms described in original wording. |
| [npm `package-lock.json` documentation](https://docs.npmjs.com/cli/v10/configuring-npm/package-lock-json) | Lockfile v2/v3 `packages` fields. | CAP-08 | Format specification; no text copied. Checked against the npm 10.9.7 copy bundled with the local Node installation; the public page was not reachable from the implementation environment. |
| [OSV schema](https://ossf.github.io/osv-schema/) and [OSV API](https://google.github.io/osv.dev/api/) | Shape of agent-mediated advisory queries. | CAP-08 | Public schema; the helper only emits a request payload and ingests results. The request and result shapes were not re-verified during implementation because the pages were not reachable; treat them as unverified until checked. |
| [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) | Normative keyword strength for requirements. | CAP-05 | Public standard. |
| [Git documentation](https://git-scm.com/docs) | `status --porcelain=v2`, `clone`, `ls-files`, environment variables for isolated configuration. | CAP-09, CAP-10, CAP-11 | Public documentation. |
| [OpenAI plugins `fix-finding` skill](https://github.com/openai/plugins/blob/main/plugins/codex-security/skills/fix-finding/SKILL.md) | "Original failure gone and nearest valid behaviour still works", already recorded in the existing research ledger. | CAP-10 | Mechanism only; no text copied. |
| [Trail of Bits skills](https://github.com/trailofbits/skills) (CC-BY-SA-4.0, per the existing research ledger) | Idea of requirement-level traceability; its per-requirement agent machinery was deliberately not adopted. | CAP-05 | Mechanism only; share-alike text not reused. |
