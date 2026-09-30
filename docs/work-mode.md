# Coding Workflows for ChatGPT Work Mode

## Repository-proven behavior

`plugins/coding-workflows/skills/` is the only authored workflow source. Run:

```powershell
python scripts\package-work-mode.py
python scripts\package-work-mode.py --check
```

The generator creates one self-contained portable Agent Skill directory per canonical skill in
`plugins/coding-workflows/work-mode/dist/`. Each package contains its `SKILL.md`
and only the supporting references, helper scripts, and shared modules it needs. It does not depend on sibling
repository paths or Codex-only `agents/openai.yaml` metadata.

The manifest records each canonical source, generated package path, and one of:

- `shared-core`: package instructions are the canonical contract with package-local
  reference rewrites only.
- `surface-adapted`: a future package may preserve the same objective and boundaries
  while carrying declared host-specific instructions from
  `work-mode/adaptations/<skill-name>/`. The manifest must declare that overlay;
  generation applies it to the portable package.

Both package forms are generated; `dist/` is never a hand-authored source. Current
packages are all `shared-core`.

## Product-documented behavior

[OpenAI's Skills documentation](https://help.openai.com/en/articles/20001066-skills-in-chatgpt/)
describes Skills creation and upload. Use the product's current instructions for the
target ChatGPT Work Mode surface, then select the appropriate generated package
directory from `work-mode/dist/`. The portable artifact is the package directory,
not the canonical source folder.

## Helper-backed skills

Some packages include `scripts/*.py` helpers and a copied `references/cw_scan.py`.
Whether a ChatGPT workspace executes uploaded skill scripts, and with what files or
network, is account-side behavior this repository has not verified. Each helper-backed
skill states its degradation: without execution it plans or reviews manually, and
without a Git repository it marks repository evidence `blocked` or `not checked`;
it never claims a helper ran. `patch-proof` and `session-checkpoint` are included
deliberately and behave this way.

## Account-side behavior not verified

This repository cannot inspect or prove a ChatGPT account's installation, enablement,
availability, synchronization, role, region, workspace policy, or cross-device state.
Codex plugin installation is a separate action. Personal-only host skills such as
`playwright`, `hatch-pet`, and Azure/Foundry skills remain outside this distribution.
