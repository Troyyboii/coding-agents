# Cloud Coding Setup

The repository needs Python 3.11 or newer and Git. It has no package-install
bootstrap and no local service dependency.

## GitHub Codespaces

The checked-in devcontainer installs Python 3.11. It does not automatically run
checkout-controlled scripts or tests during creation.

Create the Codespace from the `main` branch, review the checkout, and then run
the validation commands documented in [AGENTS.md](./AGENTS.md). No repository
secrets are required for validation.

## Cursor Cloud Agents

Cursor's current Cloud Agents documentation says that `.cursor/environment.json`
can select a Dockerfile or snapshot and that its `install` command runs from the
project root while a Build is created. The command must be idempotent because a
Build can reuse prepared disk state. See the official [Cloud Environment Setup]
documentation (https://cursor.com/docs/cloud-agent/setup).

This repository declares only the environment `name` and the exact install
command `python3 -c 'import sys; assert sys.version_info >= (3, 11)' && python3 -m compileall -q scripts tests`.
Cursor runs that command from the project root while creating a Build. It first
requires Python 3.11 or newer, then performs bounded, repeatable byte-compilation;
it does not install packages, mutate system paths, start services, or execute
repository modules. Python and Git must already be available in the selected
Cursor environment; the repository does not provision them there. A
future setup command requires a separate authority decision, an idempotence
review, documentation, and a validator rule. No Cursor Cloud installation or
invocation was run for this repository.

## Codex Cloud

Use this repository and branch, then begin with a read-only orientation:

```text
Read AGENTS.md and WORKFLOWS.md. Inspect Git status and the active inventory.
Report the relevant files and validation commands before editing.
```

Keep agent internet disabled unless the specific task needs current external
documentation or repository data. Add secrets only for a task that explicitly
requires them, and never store their values in the repository.

## Verification Boundary

Successful setup proves only that the selected environment has the prerequisites
needed for the checks that were actually run. Passing the manually invoked
repository checks is separate evidence; neither proves that personal Codex or
Claude plugins, GitHub credentials, Cursor Cloud state, or other host integrations
are installed, authenticated, or callable there.
