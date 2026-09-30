# Coding-agents integration catalog

**Catalog review date:** 2026-08-21

This catalog describes the approved toolbox plan without changing Codex
configuration or installing anything. The labels are deliberate:

- **Repository-owned:** source and behavior belong in this repository.
- **Host-provided:** supplied by Codex or the host account/session; this
  repository does not vendor, configure, authenticate, or verify it.
- **Optional candidate:** a discovery or research route, not an approved live
  dependency. It requires a separate scope, security review, and explicit setup
  decision.

## Host Capability Doctor

`python scripts\host_toolbox.py` remains an observational, exit-zero report.
Use `python scripts\host_toolbox.py --check` to evaluate the configured host
against the repository default profile at `config/host-readiness.json`; pass
`--profile PATH` to evaluate another valid profile, and add `--json` for the
machine-readable schema.

The doctor checks configuration only. It does not install a plugin, start a
login flow, mutate Codex configuration, inspect credential values, or make an
external MCP call. `0` means required checks are satisfied; `1` means a
required check is missing, invalid, or unknown; `2` means invalid profile or
command-line usage. The aggregate state is `ready`, `degraded`, or `not_ready`;
a recommended warning can be degraded while the command still exits zero. A
configured server or reported authentication state is evidence of
configuration, not proof that an MCP tool is callable.

## Catalog entries

| Entry | Ownership and status | Role | Transport | Auth | Write risk | Verification date |
| --- | --- | --- | --- | --- | --- | --- |
| `coding-workflows` plugin and repository marketplace | **Repository-owned; first-party and approved.** The plugin source is under `plugins/coding-workflows/`; the repository marketplace remains the source of truth for this first-party package. | Focused workflow skills for repository orientation, debugging, review, testing, design, browser proof, writing, and verification. | Codex plugin/package loading; no external MCP transport. | No connector credential. Any external service used by a workflow is separately host-provided. | Low at package level; a skill can describe or request consequential actions, so the active task still controls authorization. | 2026-08-08: repository instructions and current docs inspected; runtime installation not tested. |
| GitHub MCP | **Host-provided; recommended.** GitHub's remote MCP service is the preferred route for GitHub repository, issue, pull-request, and Actions context. | Read GitHub state and, only when explicitly authorized, perform narrowly scoped GitHub actions through exposed tools. | Remote HTTPS MCP. GitHub documents the hosted endpoint and host-specific HTTP/SSE configuration; the active host's transport details remain session-specific. | OAuth or a host-supported PAT flow, depending on the MCP host. Never place a token in this repository. | **Medium to high** because available tools may create or modify issues, pull requests, branches, releases, or workflow state. Prefer read-only mode, least privilege, and explicit confirmation for writes. | 2026-08-08: official GitHub setup and server docs reviewed; this catalog does not verify live registration, authentication, or tool calls. |
| Context7 MCP | **Host-provided; recommended when current library or framework documentation matters, but optional.** | Retrieve version-aware library and framework documentation and examples before implementation decisions. | Remote HTTP MCP or local stdio, depending on the host and chosen Context7 route. | Follow the current Context7/client setup; API keys and generated configuration remain outside this repository. | **Low write risk:** documentation retrieval is read-oriented. Treat returned text as external input and cross-check consequential or ambiguous claims against primary project docs. | 2026-08-08: official Context7 docs reviewed; the repository's existing Context7 note remains the boundary; live availability is not verified. |
| OpenAI documentation route | **Host-provided research route; authoritative for OpenAI and Codex product behavior.** | Resolve current OpenAI product, MCP-app, Apps SDK, and Codex documentation questions. Use the relevant library's own primary docs for non-OpenAI APIs. | HTTPS web documentation or the active host's documentation access; no repository transport. | Whatever access the host provides; no repository credential. | **None directly:** research does not write to an external service, but retrieved instructions must not be treated as authorization to act. | 2026-08-08: official OpenAI MCP/app documentation reviewed; no claim is made about current account access or connector availability. |
| Luna worker definitions | **Host-level; not repository-owned.** The worker definitions are global host configuration outside this repository; their filesystem location is environment-specific. | Host-level delegated execution for bounded independent work when the parent task explicitly routes it. | Internal Codex worker dispatch; not an MCP server or repository plugin transport. | Host/runtime identity and permissions; no repository credential. | Depends on the delegated packet and worker permissions. Every packet must state allowed writes, forbidden changes, acceptance checks, and evidence requirements. | 2026-08-08: ownership boundary documented; global files were not changed or live-tested in this documentation-only task. |
| Official MCP server references and registry discovery | **Optional candidate route; not installed or approved as a repository dependency.** Use the official reference-server repository for protocol examples and the official registry for metadata discovery. | Find or study a server only after defining the required capability, data boundary, auth model, and write policy. | Varies by candidate: local stdio or remote HTTP/SSE/Streamable HTTP. Inspect the candidate's current primary documentation. | Varies by candidate: may be none, OAuth, a scoped token, or another mechanism. Do not copy credentials into this repository. | **Unknown until audited.** Treat every tool as untrusted until its data access, side effects, scopes, package provenance, and write controls are reviewed. | 2026-08-08: official MCP server and registry material reviewed; no candidate was installed, configured, authenticated, or verified live. |

## Why the boundaries stay separate

### The first-party marketplace remains first-party

The repository marketplace packages the repository's own `coding-workflows`
plugin. That is a distribution boundary for source-controlled workflow skills,
not a general catalog of every service the host can reach. GitHub MCP, Context7,
OpenAI documentation access, and any future external connector remain
host-level integrations because their servers, authentication, availability,
and permissions are controlled outside this repository. Copying them into the
marketplace would falsely turn host capability into repository-owned source and
would blur the difference between a package that can be reviewed here and a
service that must be verified in the active host.

### Luna remains host-level

Luna is a worker/runtime choice, not a plugin or MCP server. Its global agent
definitions are outside the repository and can apply across workspaces. The
repository may document the boundary and packet contract, but it must not copy,
modify, or pretend to own those global definitions.

## Recommended use order

1. Use the repository-owned `coding-workflows` plugin for the workflow contract
   and repository-specific operating rules.
2. Use GitHub MCP for GitHub context and actions when the active host exposes it;
   start with read-only inspection and keep write authorization explicit.
3. Use Context7 when current library or framework API material is needed, then
   prefer the library's primary documentation when the result is consequential
   or ambiguous.
4. Use official OpenAI documentation as the authoritative route for OpenAI and
   Codex behavior.
5. Treat the official MCP registry and reference-server repository as discovery
   and research sources only. A candidate becomes an approved integration only
   after a separate decision and live verification.
6. Keep Luna dispatch at the host level and use a bounded packet whenever
   delegated work is appropriate.

## Verification contract

The dates above are documentation/source-review dates, not operational health
checks. A later live verification should record, separately and without exposing
secrets:

- the host/session in which the integration was observed;
- registration or availability status;
- a harmless read-only call that proves the tool is callable;
- authentication result using names or redacted identity only; and
- the observed tool set and whether write actions are disabled, gated, or
  explicitly authorized.

Configuration listings alone do not prove that an external MCP is running or
authenticated. No live verification, installation, authentication, MCP
configuration change, or external write was performed for this catalog.

## Primary sources

- [Context7 MCP overview](https://context7.com/docs/overview)
- [Context7 MCP clients and transport/auth options](https://context7.com/docs/resources/all-clients)
- [OpenAI developer mode and full MCP connectors](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt)
- [OpenAI Apps in ChatGPT](https://help.openai.com/en/articles/11487775-connectors-in-chatgpt)
- [GitHub's official MCP server](https://github.com/github/github-mcp-server)
- [GitHub MCP setup documentation](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/set-up-the-github-mcp-server)
- [Official MCP reference servers](https://github.com/modelcontextprotocol/servers)
- [Official MCP Registry overview](https://modelcontextprotocol.io/registry/about)
- [Official MCP Registry](https://registry.modelcontextprotocol.io/)
