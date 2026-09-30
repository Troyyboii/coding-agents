# Extension Threat Lenses

Use these lenses to decide what an agent extension can actually do once it is
installed. The helper's rule families map to them; the helper finds candidate
lines, and these questions decide whether a candidate is a real risk.

## Where extensions execute or instruct

Extension formats differ by host. Check which of these surfaces the target
actually uses before judging it; the repository's host support matrix records
what each host format can carry.

| Surface | Examples | Why it matters |
| --- | --- | --- |
| Skill instructions | `SKILL.md`, files it loads from `references/` | Text the agent reads as guidance. Instructions to run commands, fetch remote text, hide actions, or claim authority act like code. |
| Bundled scripts | `scripts/`, any file with a shebang or executable bit | Runs when the agent or user invokes it, with the user's filesystem, environment, and network. |
| Hooks | `hooks/hooks.json`, lifecycle event names such as `PreToolUse` or `SessionStart`, Git hooks | Run automatically, without a per-use decision. |
| MCP server definitions | `mcpServers` in `.mcp.json`, plugin or extension manifests, `[mcp_servers.*]` in TOML | Start a local process or connect to a remote service; may request environment variables. |
| Agents and commands | `agents/*.md` with `tools:`, `commands/*.md` | Change tool access or add user-invoked flows. |
| Package lifecycle | `package.json` `preinstall`/`install`/`postinstall`/`prepare`, `setup.py` | Run at install time, before any review of behavior. |
| Permission settings | `allowed-tools`, `settings.json` `permissions`, `bypassPermissions`, `danger-full-access`, `approval_policy = "never"` | Remove the host's approval step for everything else. |
| Opaque content | native executables, archives, encrypted members | Cannot be reviewed statically at all. |

## Lens questions

1. **Execution:** What runs, when, and who triggers it? Automatic (hooks,
   install scripts, MCP launch) outranks invoked-on-request.
2. **Reach:** What can it read? Credentials, SSH or cloud configuration,
   browser data, environment variables, files outside the project.
3. **Egress:** Where can data go? Every non-documentation endpoint, especially
   paste sites, webhooks, tunnels, shorteners, and raw IP addresses.
4. **Persistence:** Does it change anything that outlives the session? Shell
   profiles, scheduled tasks, services, Git hooks, agent configuration, `PATH`.
5. **Authority:** Does it widen permissions or tell the agent to act without the
   user, conceal actions, obey fetched text, or treat itself as a system message?
6. **Routing:** Does its description try to capture unrelated requests, or does
   its name shadow an installed skill?
7. **Provenance:** Is anything downloaded at run time instead of shipped? Unpinned
   `npx -y`, `pip install` from URLs, and fetch-and-execute patterns move the
   real code outside what was reviewed.
8. **Proportion:** Does each capability match the extension's stated purpose? A
   formatting skill that reads `~/.aws` is suspicious in a way a cloud skill that
   documents the same path is not.

## Context rules

- The same text means different things in different places. A command inside a
  skill's instructions is an instruction to the agent; the same command inside a
  README's fenced example is documentation. Keep both visible, rank by context.
- Hidden text is never documentation. Instructions inside HTML comments, or lines
  containing bidirectional or zero-width characters, are treated as deliberate.
- A clean scan of an extension that downloads its real payload later proves
  nothing about that payload; say so.
