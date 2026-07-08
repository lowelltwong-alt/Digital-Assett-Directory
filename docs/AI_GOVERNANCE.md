# AI Governance

## Front-door strategy

- `AGENTS.md` is the durable AI-agent contract for DAD-governed repos.
- DAD CLI lifecycle commands, schemas, audit records, deterministic hooks, and human gates are the enforcement backbone.
- Runtime-specific files such as `CLAUDE.md`, Codex config, Cursor rules, or Copilot instructions are optional adapters over the same contract.
- Runtime hook bridges should call the neutral DAD agent lifecycle adapter instead of owning governance semantics themselves.
- Git pre-push enforcement is runtime-neutral and can require a current handoff for changed work.
- Internal integration adapters should default to MCP tools/resources/prompts over direct vendor APIs.

No AI runtime is required for DAD governance. Agent identifiers are arbitrary
non-empty strings such as `codex`, `claude-code`, `cursor`, `copilot`, `human`,
`ci`, or `other`.

## MCP-first integration default

MCP is DAD's preferred internal agent boundary because it gives one neutral
surface for capability discovery, read-only resources, bounded tools, reusable
prompts, and auditable tool calls across runtimes. MCP servers do not become
governance authorities; they expose DAD-controlled resources and wrap DAD CLI
commands.

Use MCP resources for context, MCP tools for bounded commands, and MCP prompts
for reusable workflows. Direct APIs, vendor SDKs, and hosted connectors are
external adapter fallbacks only when MCP cannot cover the use case and the
adapter still records DAD lifecycle/audit evidence. See
`docs/MCP_FIRST_INTEGRATION_POLICY.md`.

## Behavioral guidance versus enforcement

Instruction files guide model behavior. Enforcement belongs in deterministic hooks, validators, Git hooks, CI, and review policy.

## Environment-specific capabilities

Use `docs/AI_ENVIRONMENT_CAPABILITY_MATRIX.md` when deciding whether Codex,
Cursor, Claude Code, or another AI environment should use skills, subagents,
MCP servers, hooks, plugins, connectors, cloud/background agents, or plain local
work. The matrix is advisory and date-bound; reverify vendor docs when stale.

## Handoff quality

Automatic hook capture is a fallback, not the preferred record. An explicit postflight should replace the draft with task context, tests, uncertainty, and reusable lessons.

## Agent swarm recommendations

The catalog may recommend specialized roles based on task and assets:

- source/provenance steward;
- schema and ontology reviewer;
- code implementation agent;
- test/evaluation agent;
- security/license reviewer;
- orphan-link analyst;
- research scout;
- handoff and lesson curator.

No swarm role receives authority beyond the source repository's governance.
