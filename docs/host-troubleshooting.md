# Host Troubleshooting

Start with the [host support matrix](./host-support.md). It lists each
consumption route, repository check, and the point where host-side proof is
still needed.

## Skills are not available

1. Confirm the host surface and scope. Workspace skills, user skills, imported
   skills, and plugin skills have different discovery roots.
2. Confirm the skill directory directly contains `SKILL.md`, then start a new
   session or use the host's documented reload command.
3. Check that the host supports the Agent Skills frontmatter and automatic skill
   discovery; accepting Markdown alone does not establish compatibility.
4. For a generated package, run `python scripts/package-agent-skills.py --check`
   from the repository root. Do not edit generated `dist/` files by hand.
5. Confirm that referenced files are inside the installed skill folder. The
   generated portable distribution relocates the shared references used by the
   canonical skills into each skill's `references/` folder.

## A skill helper does not run

Some skills ship an optional Python helper in `scripts/`. Helpers need Python
3.11 or later and a way to execute code; a host session without code execution
(for example a claude.ai account with code execution turned off) cannot run
them. The skill still works by hand in that case and reports the mechanical
check as `not checked (helper not run)` rather than passing it. If the helper reports a
missing `cw_scan` module, the installed skill folder is incomplete: reinstall
from a generated package, which copies the shared module into the skill.

## Gemini CLI extension

Install the generated directory from a local checkout with the host's documented
extension command:

```sh
gemini extensions install plugins/coding-workflows/gemini/dist
```

Restart Gemini CLI after installation. List the extension and its skills using
the current CLI's extension and skill commands. The package contains skills only;
it does not configure MCP, hooks, or session-wide context.

## Kimi Code plugin

The generated Kimi plugin lives at `plugins/coding-workflows/kimi/dist/`. Install
it through `/plugins` → **Custom**, then reload or start a new session. Check the
plugin's `skills/` directory and invoke a skill by its documented name. The
package does not include reviewer/verifier agents.

## Direct Agent Plugins consumers

Cursor and GitHub Copilot consume the canonical plugin format directly. Confirm
that the root `plugin.json` and `skills/` directory are present. Cursor local
development uses `~/.cursor/plugins/local/` and requires a reload; enterprise
policy may disable local imports. Copilot's installation commands depend on the
client and its registered marketplaces. The repository's Codex and Claude Code
marketplace manifests do not by themselves register a Copilot marketplace.

## What a repository check cannot tell you

Repository checks establish local manifest and package contracts. They cannot
show whether a host account permits installation, the host loaded the expected
version, an agent selected a skill, or a workflow behaved correctly. Verify
those in the host itself with a harmless prompt and report the host/version and
observed result separately. Do not include credentials or private prompt data
in issue reports.
