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
