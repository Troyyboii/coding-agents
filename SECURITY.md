# Security Policy

## Supported Version

Security fixes apply to the current `main` branch. No historical release line
is maintained yet.

## Reporting a Vulnerability

Use GitHub's private vulnerability reporting for this repository. If that
surface is unavailable, contact the repository owner through GitHub before
sharing sensitive details. Do not place secrets, exploit code, credentials, or
private logs in a public issue.

Include the affected path, impact, minimal reproduction, and any safe mitigation
already tested. Reports are evidence, not authorization to access accounts,
systems, or data outside the reporter's control.

## Repository Security Boundary

This repository contains workflow skills and dependency-free validation scripts.
Most skills are instructions only. Some ship a small Python helper at
`skills/<name>/scripts/<file>.py`, and shared helper code lives in
`plugins/coding-workflows/references/*.py`. The repository validator enforces
the helper boundary:

- Python 3.11 standard library only, plus named shared modules;
- no network, dynamic-import, or native-code modules, no shell execution, no
  `os` process functions, and no `eval` or `exec`;
- subprocess use denied by default; the only exceptions are named per helper and
  listed in [the generated inventory](./docs/inventory.md);
- helpers run only when an agent invokes them, never on install, and never as
  hooks, commands, or background services.

Hooks, commands, MCP servers, nested script directories, shell scripts, and
binaries remain forbidden in the plugin. The repository does not own connector
credentials or an MCP server. A valid plugin package does not prove that a host
connector is installed, authenticated, or safe for a particular external action.
