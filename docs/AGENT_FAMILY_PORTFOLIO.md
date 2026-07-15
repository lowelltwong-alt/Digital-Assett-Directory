# DAD Agent-Family Portfolio

## Purpose

DAD governs a small portfolio of reusable capability families instead of creating a new agent for every task. The stable unit is a capability contract, not a vendor model. `Luna`, `Terra`, and `Sol` are runtime capability aliases resolved from availability, tools, context, privacy, cost, and consequence; provider and model identifiers exist only on expiring execution attempts.

The authority record is `registry/agent-family-portfolio-registry.json`. It defines nine governed candidates: machine learning, full-stack engineering, quality/verification/release, security/privacy/supply chain, knowledge/research/provenance, data/schema/knowledge graph, integration/MCP/automation, product/UX/accessibility, and the legal evidence/governance overlay.

## Shared contract

Every family uses the same seven roles:

1. `router` selects the smallest applicable family combination.
2. `boss` protects mission, authority, and escalation boundaries.
3. `architect` defines interfaces, dependencies, proof obligations, and rollback.
4. `foreman` decomposes bounded non-overlapping work.
5. `worker` is the single writer or evidence producer.
6. `independent_checker` re-derives acceptance and cannot be the producer.
7. `sentinel` observes deltas and emits one deduplicated candidate issue without rewriting guidance.

The interfaces are `family_manifest`, `capability_contract`, `assignment`, `evidence`, `challenge`, `health_snapshot`, `candidate_change`, and `human_decision`. Lifecycle is candidate, piloted, reviewed, active, watch, stale, superseded, and retired.

## Typed dependency graph

The portfolio projects families, skills, packs, roles, capabilities, projects, validation evidence, governance gates, and runtime claims. Its allowed relationship vocabulary is `depends_on`, `implements`, `validated_by`, `governed_by`, `applies_to`, `observed_by`, `stale_due_to`, `conflicts_with`, and `supersedes`. New edge types are also registered in `registry/graph-edge-registry.json`.

Generated links, scores, health states, and supersession candidates are evidence for review. They do not become source truth or authorize mutation. The graph closes unknown relations at the projection boundary and preserves evidence references for every emitted edge.

## One-human cockpit

The family cockpit is a side-by-side `dad.portfolio_cockpit.v2` projection; it does not change the existing v1 contract. It combines existing portfolio attention with family integrity and freshness issues, deduplicates by semantic fingerprint, and exposes at most three items in `Now`. Remaining evidence stays in the full digest. It has no action controls and cannot dispatch work.

```powershell
$env:PYTHONPATH = 'src'
python -m digital_asset_directory.cli agent-families catalog --hub .
python -m digital_asset_directory.cli agent-families route "build a secure full-stack case dashboard" --risk-tag privacy --hub .
python -m digital_asset_directory.cli agent-families graph --hub .
python -m digital_asset_directory.cli agent-families health --hub .
python -m digital_asset_directory.cli agent-families cockpit --publish --hub .
```

`--publish` writes only governed DAD generated reports. It does not mutate source repositories, code, policy, releases, agent instructions, schedules, or external systems.

## Pilots

The DAD and Mock Trial pilots use tracked-path metadata and Git status fingerprints only. The pilot command records stack indicators and checks the source fingerprint before and after inspection. It never reads raw file bodies or writes to the pilot repository.

```powershell
python -m digital_asset_directory.cli agent-families pilot pilot:dad-family-control-plane <dad-repo> --hub .
python -m digital_asset_directory.cli agent-families pilot pilot:mock-trial-family-routing <mock-trial-repo> --hub .
```

LawFirm OS security and legal-governance work remains incubating until its repository scope and human legal/privacy gates are explicitly approved.

## Freshness and research

Sentinels compare declared skill revisions, dependency graphs, validation evidence, attempts, governance changes, and runtime capability changes. A changed dependency produces one semantic issue; timestamps do not create duplicate notifications. Sentinels may propose adapt, rewrite, supersede, retire, or leave-alone decisions but cannot apply them.

The research cadence is a dormant `P14D` contract. Activation requires human approval. No-change cycles are deterministic and use no model tokens; changed cycles default to Luna and may use Terra for bounded synthesis. Recurring Sol use is forbidden. Research remains pointer-only and human-gated for adoption.

## Promotion rule

A new top-level family needs evidence of recurrence across at least three repositories, or one high-consequence authority domain, plus its own authority boundary, validation harness, freshness sources, and failure modes. Otherwise the capability remains a specialist pack. Platform/SRE, documentation/DevEx, migration, performance, and cost optimization start inside full-stack engineering.

Only one family build and one bounded pilot may be active at once. Extra work remains incubating. A family never approves its own material output, and no scan or cockpit issue authorizes a change.

## On-demand specialist routing

Generic family roles protect the shared hierarchy; specialist packs make deep
methods discoverable without creating more top-level families. The Integration
family owns `pack:mcp-integration-specialist-pack`, and Product/UX owns
`pack:ui-ux-specialist-pack`. A project-position diagnosis identifies the
demonstrated gap first, then routes at most three primary specialists. The
entire pack is never activated by default.

Negative intent, a sufficient deterministic tool, an exact bounded change, or
missing target/user evidence suppresses specialist activation. Passing one
completion depth does not activate the next. Pack membership and graph edges
express discovery and governance only; they cannot grant execution authority.
