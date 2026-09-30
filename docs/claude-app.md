# Coding Workflows for the Claude App (claude.ai)

## Repository-proven behavior

`plugins/coding-workflows/skills/` remains the only authored workflow source. Run:

```powershell
python scripts\package-claude-app.py
python scripts\package-claude-app.py --check
```

The generator creates one deterministic ZIP file per active canonical skill in
`plugins/coding-workflows/claude-app/dist/`. Each ZIP
contains the skill's own directory as its root (for example `repo-xray.zip` contains
`repo-xray/SKILL.md`), matching the upload format documented for claude.ai Custom Skills.
A package carries only its `SKILL.md`, its helper scripts, and the supporting references and
shared modules it actually needs; it
does not depend on sibling repository paths or Codex-only `agents/openai.yaml` metadata.

`plugins/coding-workflows/claude-app/manifest.json` records the canonical source, the
generated package root, and the package file suffix. It deliberately does not enumerate
skills one by one: the generator discovers every directory under the canonical source that
has a `SKILL.md` and packages it, so a new canonical skill participates in this
distribution automatically the next time the packages are regenerated, without a manifest
edit. An `excluded_skills` list (empty today) is the one place to opt a future skill out if
it is ever inappropriate for this surface.

The packaging logic reuses the shared-reference copying, `SKILL.md` rewriting, and
secret/path scanning already proven by the ChatGPT Work Mode packager
(`scripts/work_mode_packages.py`) — see [`docs/work-mode.md`](./work-mode.md). Only the
container differs: a single deterministic ZIP file per skill instead of a plain directory.

## Product-documented behavior

Before implementing this distribution, the current first-party Anthropic documentation was
checked directly (not assumed):

- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) —
  the general Agent Skills contract: `SKILL.md` YAML frontmatter requires `name` (max 64
  characters; lowercase letters, numbers, and hyphens only; no XML tags; cannot contain the
  reserved words "anthropic" or "claude") and `description` (non-empty, max 1024 characters,
  no XML tags). It also describes custom Skills as user-specific rather than synchronized
  across Claude surfaces (the API, Claude Code, and claude.ai).
- [How to create custom Skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
  (Claude Help Center) — for individual Free/Pro/Max users, enable **Settings > Capabilities >
  Code execution and file creation**, then use **Customize > Skills > + > Create skill > Upload
  a skill**. It also documents the ZIP requirement: *"The ZIP should contain the skill folder as
  its root (not a subfolder)"* with the folder name matching the skill name.
- [Using Skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)
  (Claude Help Center) — confirms upload-time validation rejects a ZIP that exceeds size
  limits, a folder name that doesn't match the skill name, a missing `SKILL.md`, or invalid
  characters in the name or description, without disclosing an exact byte limit.

The platform Agent Skills documentation states that uploads must be under **30 MB uncompressed**.
The claude.ai Help Center pages above refer only to the app's generic size limits and do not give
that numeric limit for claude.ai specifically. These generated packages are small, text-based skill
bundles (tens of kilobytes each), so validation does not enforce a numeric app-specific size gate.
Use the product's current instructions for the exact upload flow, then upload the matching file
from `plugins/coding-workflows/claude-app/dist/` individually for each skill you want.

## Validate the Claude app distribution

Run from the repository root:

```powershell
python scripts\validate-repository.py
python scripts\package-claude-app.py --check
python -m unittest discover -s tests -v
```

`validate-repository.py` proves, for every generated ZIP: it contains exactly one
top-level directory matching the skill name, that directory contains `SKILL.md`, the
frontmatter `name` matches the folder and satisfies the official name contract (including
the reserved-word and XML-tag rules), the `description` satisfies the official contract, no
Codex-only `agents/` metadata or cache/debris files (`__pycache__`, `.pyc`, `.DS_Store`,
`Thumbs.db`) are present, every internal relative reference resolves to another file inside
the same ZIP without escaping the package root, and no local machine path or secret-shaped
string appears in any bundled Markdown file. It also cross-checks that the set of generated
packages exactly matches the active canonical skill set.

`package-claude-app.py --check` additionally proves the packages are byte-for-byte
deterministic: rebuilding from the canonical source in a temporary directory must produce
ZIP files identical to the checked-in ones, so stale output is detected rather than
silently drifting.

## Helper-backed skills

Helper scripts run only where the account's code-execution capability is enabled, inside
the product sandbox, and only on uploaded material; they cannot reach a user's local
repository. Each helper-backed skill degrades explicitly when execution, a repository, or
network reads are unavailable, and never claims a helper ran. Execution-bound skills such
as `patch-proof` and `session-checkpoint` are packaged on purpose; `excluded_skills`
remains empty.

## Account-side behavior not verified

This repository cannot inspect or prove a claude.ai account's Custom Skills upload,
enablement, per-user synchronization, or code-execution availability. Those remain
account/host state, exactly as Codex plugin installation, ChatGPT Work Mode account state,
and Claude Code plugin installation are host-side for the other three surfaces. Repository
validation proves the ZIP packages are structurally correct, self-contained, and traceable
to the canonical skill source; it does not prove any of them has been uploaded to a
specific claude.ai account.

## What is deliberately not used

- **No hand-authored Claude-app skill copy.** The packages are generated from the same
  canonical `skills/` tree the Codex plugin, Claude Code plugin, and Work Mode packages use;
  `dist/` is regenerated output, never a second source.
- **No per-skill manifest entries.** Unlike the Work Mode manifest, the Claude app manifest
  does not list skills individually — see "Repository-proven behavior" above for why.
- **No claude.ai-specific numeric ZIP size gate**, since the current Help Center does not disclose
  one; the platform's separate 30 MB uncompressed limit is documented above.
