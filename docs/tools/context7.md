# Context7

Context7 is a host-provided documentation integration, not repository-owned
code. Use it when implementation depends on current library or framework APIs
and the primary documentation is available through the active Codex session.

## Boundary

- Do not vendor a Context7 wrapper, API key, or generated runtime configuration.
- Verify that the integration is callable in the current session before relying
  on it.
- Treat returned documentation as external evidence and prefer the library's
  official material when the answer is consequential or ambiguous.
- Fall back to official web documentation when Context7 is unavailable.

This note does not prove installation, authentication, or live availability.
