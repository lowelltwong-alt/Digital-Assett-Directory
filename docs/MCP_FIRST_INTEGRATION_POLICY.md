# DAD MCP-First Integration Policy

DAD internal integrations default to MCP-style adapters over direct vendor APIs.
The durable authority remains `AGENTS.md`, the DAD CLI lifecycle, schemas,
audit records, Git/CI checks, and human gates. MCP is the preferred neutral
runtime boundary; it is not a new governance authority.

## Default

- Prefer MCP servers/resources/tools/prompts for internal agent access.
- Treat direct APIs and vendor SDKs as external adapter fallback only.
- Keep agent IDs arbitrary non-empty strings; MCP clients, servers, and hosts do
  not get special authority because of their vendor or runtime.
- Use DAD CLI commands as the implementation behind MCP tools whenever possible.
- Record side effects through DAD preflight, midflight when required, postflight,
  audit JSONL, and human approval IDs.

## MCP Surface Shape

- Resources expose read-only context: `AGENTS.md`, front-door docs, schemas,
  governance maps, data maps, transport status, journal status, scheduled-task
  status, audit summaries, and enrollment status.
- Tools wrap bounded actions: `agent preflight`, `agent midflight`,
  `agent postflight`, `data status`, `transport readiness`, `journal status`,
  reviewed plan generation, and approved apply commands.
- Prompts provide reusable workflows only: preflight briefing, review-lane
  checklist, postflight drafting, transport rollout review, and MCP adapter
  design review.

The local scheduled-task surface is `dad://report/scheduled-tasks`, backed by
`asset-dir daemon scheduled-tasks` and the active-data-root report
`processed/reports/scheduled_tasks.json`. It is read-only status evidence for
UI/adapters, not scheduler mutation authority.

## Runtime-Neutral Host Adapters

The reviewed local graph server has one logical identity,
`dad-local-graph-surfaces`, and one direct stdio invocation through
`asset-dir mcp graph-stdio`. Host-specific configuration is a thin adapter only;
it does not fork the server contract or grant a vendor extra authority.

`assets/mcp/dad-local-readonly/` contains validated templates for Codex, Claude
Code, Claude Desktop, Cursor, VS Code/GitHub Copilot, and Copilot CLI. Every
template resolves to the same Python module, argument vector, read-only tool
allowlist, local-only transport, and deny-all execution boundary. Machine paths
are rendered at installation time and are not stored in the reusable templates.

Installation, host trust, and restart remain explicit human gates. An adapter
validation pass proves configuration parity, not that a particular host loaded
the server; each installed host still needs an initialize handshake and local
status check.

## Dependency Freshness And Blast Radius

`registry/mcp-dependency-map.json` is the reviewed machine contract for DAD's
single local stdio server. It covers identity, protocol, CLI and packaging
entrypoints, implementation and backends, runtime data, schemas, registries,
governance, adapters, navigation, validation, and security authority. Typed
edges point from a changed dependency to its downstream consumer, while named
flows preserve source-to-transform-to-sink direction.

Dedicated MCP files use exact hashes. Shared registries, CLI/packaging files,
and navigation surfaces use semantic selectors so unrelated changes do not
create false staleness. Repository validation fails closed when selected
semantics, local imports, runtime tools/resources, adapter allowlists, first-
party host-source freshness, authority direction, or data-flow direction drift.

The server exposes categorical dependency status, stale-refusing impact, and a
review-only candidate fingerprint report. Candidate refresh never writes the
map, authorizes itself, edits host configuration, or grants Git/DAD execution
authority. Installed-host evidence is metadata-only and distinguishes reusable
template parity from configuration, availability, and confirmed activation.

## Safety Rules

- Resource URIs must be validated and scoped to approved DAD surfaces.
- Tools with side effects must require explicit inputs for repo, session,
  summary, tests, approval ID when needed, and target path.
- Tool calls that mutate source repos, enroll repos, publish data, or touch
  protected repos must fail closed without reviewed DAD policy and human gate
  evidence.
- MCP server descriptions are advisory. DAD policy, schema validation, and audit
  records decide what is allowed.
- Cloud, hosted, or vendor-specific MCP servers are optional adapters. Local DAD
  MCP is the internal default.

## API Fallback

Use a direct API only when MCP cannot express the integration, when a reviewed
human gate approves that adapter, and when the adapter still writes DAD evidence
through the same lifecycle. API credentials must never become DAD authority, and
API availability must not bypass local source authority, transport quarantine,
or postflight.

References: Model Context Protocol specification, version 2025-06-18
(`modelcontextprotocol.io/specification/2025-06-18`), especially the
host/client/server model, resources, tools, prompts, capability negotiation, and
security guidance.
