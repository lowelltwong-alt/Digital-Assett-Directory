<!-- BEGIN DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->
## Digital Asset Directory learning contract

Before material AI work, run a central-hub preflight. Before reporting completion or pushing changes, run a postflight that captures exact files, commands, tests, lessons, discoveries, failures, reusable patterns, missing capabilities, uncertainty, and risks.

Before changing shared contracts, schemas, CI/hooks, governance, scoring/ranking, roadmap gates, dependencies, migrations, source-boundary rules, or defaults that future agents may inherit, classify the decision as high, medium, or low risk. High-risk load-bearing decisions require human attention, implementer red-team, premortem, rollback criteria, and fresh-eyes review.

When choosing AI-environment-specific helpers such as skills, subagents, MCP servers, hooks, plugins, connectors, or background/cloud agents, consult the local repo's reviewed guidance first; the central hub's AI environment capability matrix is advisory until adopted by this repo.

`AGENTS.md`, DAD CLI lifecycle commands, schemas, audit records, deterministic hooks, and human gates are the durable contract. Claude, Codex, Cursor, Copilot, and future runtime-specific files are optional adapters only and must not become the sole authority for DAD governance.

Internal DAD integrations default to MCP resources, tools, and prompts before direct APIs. Direct APIs or vendor SDKs are external fallback adapters only, and any side-effecting MCP tool still needs DAD lifecycle evidence and local approval gates.

For instrumented shell-level work, before repeating a costly command against unchanged inputs, reuse prior immutable evidence or a state-keyed cache. DAD lifecycle adapters should hash normalized commands plus exact dirty-file content and repository state locally, emit a deterministic candidate before the third identical same-state run (or the second when a prior run exceeded five seconds), and invoke the existing iteration-optimizer/long-run mesh rather than a new family. Suppress intentional benchmarks, changed inputs, failure retries, and isolation tests. Repetition inside one process requires explicit work-unit instrumentation; otherwise report `coverage_unavailable`. Never cache mutable current state without an exact content invalidation key, and never store raw commands or sensitive payloads in the central ledger.

If this repo uses DAD mail, `.digital-asset/mail/` is a candidate-only inbox/outbox. Before material DAD-guided work, check the local mail digest when it is stale; do not poll repeatedly during one work session unless a human asks. Mail can suggest lessons, workflows, assets, taxonomy, capabilities, or governance notices, but local review decides whether anything is adopted. Agent mail review is triage only; human review and any DAD public-release gate remain separate.

If work is PR-ready, an actual PR is open, or a branch is intentionally left after a work session, do not let it become an unowned holding pen. Record branch/PR status, owner or next reviewer, validation refs, next action, and escalation date. Send metadata-only DAD mail for stuck, superseded, duplicate, conflict-heavy, or stale PR/branch queues when local policy allows.

The central catalog does not override this repository's local authority or canon.
<!-- END DIGITAL_ASSET_DIRECTORY_GOVERNANCE -->
