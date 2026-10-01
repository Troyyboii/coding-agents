# Release Checklist

Releases are deliberate external actions. Preparing a release does not authorize
a commit, tag, push, GitHub release, or plugin-directory submission.

## Prepare

1. Confirm the intended changes are listed under `CHANGELOG.md` → `Unreleased`.
2. Choose the semantic version from user-visible compatibility impact.
3. Update `plugins/coding-workflows/.codex-plugin/plugin.json`,
   `plugins/coding-workflows/.claude-plugin/plugin.json`, and
   `plugins/coding-workflows/plugin.json` to the same version; do not use a
   release version bump merely as a local cachebuster.
4. Regenerate the portable Agent Skills, Gemini, and Kimi packages after the
   version change:

   ```powershell
   python scripts\package-agent-skills.py
   ```

5. Update the displayed package version in `docs/host-support.md` to match the
   canonical plugin manifests. `validate-repository.py` checks this value.
6. Regenerate `docs/inventory.md`.
7. Move the changelog entries into a dated version section without inventing
   prior release history. Date the release section on the release commit used for
   the tag.

## Verify

Run the repository checks on Windows or Linux:

```powershell
python scripts\validate-repository.py
python scripts\generate-inventory.py --check
python scripts\package-work-mode.py --check
python scripts\package-claude-app.py --check
python scripts\package-agent-skills.py --check
python -m unittest discover -s tests -v
git diff --check HEAD
```

`python scripts\validate-repository.py` is the required repository-owned plugin
manifest and contract check; the installed Codex CLI does not provide a plugin
validation subcommand. If the Claude Code CLI is installed, run its official
validator against both plugin and marketplace metadata:

```powershell
claude plugin validate plugins/coding-workflows --strict
claude plugin validate . --strict
```

If `skills-ref` or another official Agent Skills validator is installed, run it
against every changed skill. After explicit authorization to change local host
state, install the package from the repository marketplace in a fresh Codex
session and exercise representative direct, indirect, negative, and edge
requests.

After separate explicit authorization, install the marketplace and plugin in a
fresh Claude Code session and exercise the same representative requests.

Model-backed routing reports are supporting evidence only after human review.
Do not commit reports under `.artifacts/`.

## Publish

After explicit authorization, stage exact release paths, review the complete
diff, commit, push, tag the verified commit, and create release notes from the
dated changelog section. Verify the remote tag and release point at that exact
commit. Public plugin submission remains a separate authorized workflow.

## Rollback and deprecation

Do not silently replace an already published version or rewrite its tag. If a
release has a material defect, document the affected version and impact, stop
promoting that artifact where the distribution channel permits, and prepare a
corrective version with a clear changelog entry. For a deprecated host route,
record the last supported package/version, the reason, and a migration path in
the support matrix before removing its generator or artifacts. These steps are
release guidance; local validation cannot revoke a package from user accounts.
