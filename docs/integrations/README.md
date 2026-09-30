# Integration catalog

This directory records the approved integration boundaries for the coding-agents
toolbox. It is documentation, not a setup file. Nothing here proves that a
host-provided integration is installed, authenticated, enabled, or callable in
the current Codex session.

- [Integration catalog](./catalog.md): ownership, recommended routes, risk fields,
  and source links.

The Host Capability Doctor (`python scripts\host_toolbox.py --check`) evaluates
the configured host against the repository readiness profile. It is
configuration-only: it does not install or log in to anything, change Codex
configuration, inspect credentials, or call an external MCP tool. A configured
or authenticated entry is not proof that its tools are callable.
