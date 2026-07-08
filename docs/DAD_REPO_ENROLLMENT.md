# DAD Repo Enrollment

DAD enrollment is a reviewed, versioned way to connect persistent repos to the
Digital Asset Directory hub. It is not filesystem discovery and it is not
automatic source mutation.

## Contract

Every enrolled repo gets:

```text
.digital-asset/dad-integration.json
```

The contract records the stable repo ID, visibility, public-facing status, DAD
hub reference, enrollment version, approved wave, cadence, enabled control
planes, local validation commands, return address, and the exact DAD-managed
paths approved for enrollment.

Current contracts also carry surface-version blocks for the repo-facing DAD
control planes. Absence means `legacy`, never `current`; a missing block marks
the repo update-needed until a reviewed enrollment wave refreshes the contract.

```json
"transport": {
  "surface_version": "1.0.0",
  "implementation_version": "1.0.0-m0m1m2",
  "mode": "local_pull",
  "journal_fallback": true
},
"graph": {
  "surface_version": "0.1.0",
  "mode": "generated_candidate_surfaces"
},
"mcp": {
  "surface_version": "0.1.0",
  "mode": "local_stdio_read_only",
  "remote_enabled": false,
  "vendor_sdk_required": false
},
"journal": {
  "surface_version": "0.1.0",
  "mode": "plan_only_until_human_gate",
  "checkpoint_scope": "DATA_PLANE_PATHS"
},
"events": {
  "surface_version": "0.1.0",
  "mode": "repo_outbox_to_central_log",
  "append_only": true
}
```

`surface_version` pins the downstream contract shape. `implementation_version`
pins the DAD transport implementation bundle so future upgrade waves can target
exact versions. Repos missing these blocks, repos with stale versions, or repos
with mailboxes but no contract are transport-upgrade candidates. `asset-dir
transport audit` writes the central audit report and deduped upgrade queue;
reviewed enrollment update waves apply the contract and README refresh.
Protected repos remain central-only until a repo-specific local-write approval
exists.

`asset-dir enroll surface-status` writes a central read-only compatibility
report and deduped queue rows keyed by `repo + surface + expected_version`.
Those rows are candidate planning evidence only. They do not apply updates,
mutate protected repos, or authorize generated graph, MCP, journal, or event
data as source truth.

The optional `agent_runtime_policy` block makes no-lock-in explicit. New
contracts default internal integrations to MCP over direct APIs:

```json
"internal_integration_default": "mcp_over_direct_api",
"direct_api_policy": "external_adapter_fallback_only"
```

MCP resources, tools, and prompts are adapters over DAD governance, not a new
authority layer.

Current DAD control planes include the library/card catalog, mail center,
reusable assets, coding harnesses, agent skills, templates, architecture
references, repo enrollment, coding/test parity guidance, governance maps, data
maps, and learning/postflight loops.

Repo renames and copies keep the same stable repo ID only when the repo-local
contract still represents the same repo. Repo splits require new enrollment
records so DAD does not confuse return addresses, data boundaries, or authority.

## Modes

Enrollment has two modes:

- Full governance install: one-time or update-time writes to the reviewed
  allowlist after `asset-dir enroll apply` or `asset-dir enroll update-apply`
  receives a reviewed human approval ID.
- Normal recurring operation: DAD writes only to `.digital-asset/mail/**`.

DAD never enrolls arbitrary discovered folders. `asset-dir enroll discover` is
read-only, and `asset-dir enroll plan --repo all` uses only reviewed
`enrollment.repos` policy entries in a specified rollout wave.

## Approved Surfaces

Full governance enrollment may install or update only:

```text
.digital-asset/mail/**
.digital-asset/assets/README.md
.digital-asset/assets/index.jsonl
.digital-asset/assets/adoption.jsonl
.digital-asset/learning/events.jsonl
.digital-asset/skills/checkout.json
.digital-asset/context-map.json
.digital-asset/governance-map.yaml
.digital-asset/data-map.yaml
.ai-assets.json
AGENTS.md managed block
CLAUDE.md import/block
AI_FRONT_DOOR.md managed block
AI_TABLE_OF_CONTENTS.md managed rows
.githooks/pre-push
.githooks/pre-push.ps1
```

Managed Markdown changes must preserve repo-authored content outside DAD
markers. Hook installation must be disclosed in the plan and audit output. Hook
activation remains a local repo decision.

## Cadence

- Mail digest: daily.
- Asset, skill, template, architecture, governance-map, data-map, and enrollment
  freshness checks: weekly.
- Preflight behavior: warn only when a digest or weekly check is stale.

Weekly checks generate candidate mail such as asset updates, skill update or
retirement notices, template updates, governance-map drift, data-map drift, and
new best-practice recommendations. They do not mutate target repos.

Repos that use or watch DAD assets should keep `.digital-asset/dad-usage.jsonl`
and source-owned asset cards in `.digital-asset/assets/index.jsonl`, then send
usage feedback to DAD. DAD uses those ledgers to target future upgrade notices
rather than spamming every repo.

Repo-local asset memory is not a second DAD database. It is a small,
metadata-only, source-repo owned surface for paths, summaries, tags, hashes,
validation commands, adoption notes, and upgrade pointers. DAD can collect it
with `asset-dir dad repo-assets --repo <repo>` without mutating the source repo.
Asset cards should use DAD's compact 9-layer address model. Layer 9 is
`learning_adaptation`; workflow/orchestration depth belongs in workflow-card
refs or source docs, not pasted into the asset card.

## Public Safety

Public-facing repos receive public-safe pointers by default. Local absolute
paths are omitted unless `local_paths_allowed` is explicitly true in reviewed
policy. Private, internal, restricted, or unknown-origin mail cannot reach a
public-facing repo without the mail center's human release gate.

Logos Scripture Graph and Logos Governance require explicit local-write approval
even for enrollment repair. Mock Trial/Albert follows normal reviewed-policy
rules rather than a special protected-repo class.

## Commands

```text
asset-dir enroll discover
asset-dir enroll plan --repo all --wave <id>
asset-dir enroll apply --repo <path-or-id> --approval-id <id>
asset-dir enroll update-plan --repo all --wave <id>
asset-dir enroll update-apply --repo <path-or-id> --approval-id <id>
asset-dir enroll status --repo all
```

Plan commands write central candidate reports under `processed/enrollment/`.
Apply commands append central audit records and fail closed when policy or
approval is missing.
