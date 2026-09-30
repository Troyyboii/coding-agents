# Instruction Surfaces

Agent instruction files look alike but are loaded differently. Before writing or
changing a host-specific file, confirm that host's current documentation with
`live-research`; this table is orientation, not proof of current host behavior.
Review date: 2026-09-26, structural only.

| File | Typical consumer | Scope and loading to confirm | Notes |
| --- | --- | --- | --- |
| `AGENTS.md` | Hosts that follow the AGENTS.md convention | Whether nested files apply to their directory subtree, and how nearest-file precedence works | Preferred host-neutral source when the repository serves several agents. |
| `CLAUDE.md` | Claude Code | Which levels load automatically (user, project, subdirectory) and whether it can import another file | Keep it a thin pointer to `AGENTS.md` plus Claude-only facts. |
| `GEMINI.md` | Gemini CLI | Hierarchical loading and whether another context file name is configured | Same pointer pattern. |
| `.github/copilot-instructions.md` | GitHub Copilot | Repository-wide application and which Copilot surfaces read it | Path-scoped files under `.github/instructions/` use their own frontmatter. |
| `.cursor/rules/` files | Cursor | Rule types (always applied, glob-scoped, requested) and frontmatter fields | Legacy `.cursorrules` may still exist; do not keep both in conflict. |
| `.clinerules`, `.windsurfrules`, `.windsurf/rules/` | Cline, Windsurf | File versus directory form and load order | Create only when the user uses that host. |

## Authoring model

- One canonical source. Put shared rules in `AGENTS.md`; nested `AGENTS.md`
  files hold only rules that differ for that subtree.
- Host-specific files hold only the host delta: a pointer to the canonical file
  and facts true only for that host. Never copy the canonical content into them.
- Write only what an agent cannot cheaply discover and would get wrong: build,
  test, and validation commands; generated files not to edit; protected paths;
  authorization rules; non-obvious conventions. Link to existing documentation
  instead of restating it.
- Every command and path must come from an inspected file: a manifest, CI step,
  script, or existing documentation.

## Audit checks

- Referenced paths and commands resolve (the helper checks this without running
  anything).
- Two files do not give different commands for the same job.
- The package manager named matches the lockfile present.
- Instructions do not tell agents to edit generated files.
- Nested scopes do not silently override a root rule without saying so.
- Host-specific files are thin and agree with the canonical source.
