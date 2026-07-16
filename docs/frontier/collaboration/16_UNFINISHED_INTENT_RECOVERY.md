# Durable Plan Memory and Unfinished-Build Recovery

Status: implemented candidate; automatic schedule and notification inactive.

DAD now has a non-authorizing recovery plane for explicit material families,
libraries, products, architectures, and multi-session builds. It stores a small
intent seed and immutable sanitized plan revisions under initialized private
`DAD_DATA_ROOT`, maintains stable semantic entities above names, searches
related work before creation, and reconstructs partial-build evidence without
changing Git.

The implementation consists of:

- `portfolio_intents.py`: append-only intent events, private immutable plan
  artifacts, idempotent capture, revisions, and deterministic plan index;
- `entity_identity.py`, `entity_matching.py`, and `entity_graph.py`: semantic
  cards, durable IDs, candidate relations, deterministic matching, cycle
  validation, lineage, neighbors, and blast radius;
- `portfolio_related_work.py`: top-five search across plans, entities, families,
  skills, capabilities, and workflows with no embeddings or identity winner;
- `portfolio_build_recovery.py`: conservative source-snapshot bundles and
  proposal-only dispositions;
- `portfolio_weekly_digest.py`: an at-most-three, zero-model projection over
  the existing Today decision queue;
- `runtime_resolver.py`, `harness_engineering.py`, and `autonomy_control.py`:
  provider-neutral routes, immutable harnesses, typed safe commands, A0-A4
  policy, exact leases, selective quarantine, and deterministic kill evidence.

## Authority and privacy

Plan capture never calls `os capture` and therefore creates no idea or proposed
workstream. All artifacts assert `execution_authorized=false`. Similarity never
merges identities. Recovery never checks out, commits, merges, stashes, resets,
cleans, deletes, rebases, pushes, binds, closes, or dispatches work.

Private plan persistence fails closed when `DAD_DATA_ROOT` is not initialized.
Capture minimizes structured fields, redacts credentials and local absolute
paths, and does not store raw conversations, prompts, prompt hashes, hidden
reasoning, client rows, or source blobs. MCP exposes sanitized read-only plan,
lineage, identity, neighbor, blast-radius, and recovery projections; it cannot
capture plans or make identity decisions.

## Runtime and harness rules

Roles name durable capabilities, tools, context, privacy, effort, cost, and
consequence requirements—not vendor model IDs. Runtime snapshots come from
explicit local registrations or host receipts. The resolver deterministically
filters and ranks current runtimes and preselects at most one fallback before a
side effect. Route decisions and leases remain candidates.

Harness commands use explicit `argv[]`, `shell=false`, allowed working
directories, environment allowlists, effect classes, tool capabilities, and
timeouts. Harness activation, supersession, and retirement require human
approval and independent evidence.

The autonomy registry is deny-execute. A0 observes, A1 recommends, A2 is a
future exact allowlisted reversible delivery, A3 requires exact human
confirmation, and A4 is prohibited. Kill and quarantine may only restrict;
recovery always requires a new human decision.

## Rollout gate

The weekly Monday 07:00 America/New_York schedule and Windows toast are only
candidate configuration. Activation requires five supervised read-only reviews
over at least seven days, acceptable false-positive/noise and privacy results,
zero accidental mutations, and Lowell's explicit activation. Unknown delivery
outcomes are reconciled and never blindly retried.
