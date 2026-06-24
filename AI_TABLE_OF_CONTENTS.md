# AI Table of Contents

## Front doors and authority

- `AI_FRONT_DOOR.md` — mission, ownership, routing, stop conditions
- `AGENTS.md` — standing agent contract
- `MACHINE_NAVIGATION_MANIFEST.json` — machine-readable entrypoint map
- `registry/source-of-truth.json` — repository precedence and layer definitions
- `registry/design-authority.json` — non-negotiable design rules

## Architecture

- `docs/ARCHITECTURE.md`
- `docs/DATA_FLOW.md`
- `docs/KNOWLEDGE_GRAPH_MODEL.md`
- `docs/ASSET_VALUE_MODEL.md`
- `docs/ORPHAN_ACTIVATION_AND_SYNERGY_RADAR.md`
- `docs/LESSONS_AND_HANDOFF_LOOP.md`
- `docs/AI_GOVERNANCE.md`
- `docs/SECURITY_AND_PRIVACY.md`
- `docs/ORPHAN_RADAR_INTEGRATION.md`
- `docs/RESEARCH_BASIS.md`
- `docs/DUAL_PROPOSAL_ENGINE_RESEARCH_AND_BUILD_PLAN.md` — research-backed plan for bottom-up and top-down proposal engines

## Contracts

- `schemas/asset.schema.json`
- `schemas/edge.schema.json`
- `schemas/lesson.schema.json`
- `schemas/handoff.schema.json`
- `schemas/alert.schema.json`
- `schemas/source.schema.json`
- `schemas/synergy.schema.json`
- `schemas/activation-trigger.schema.json`
- `schemas/capability-recommendation.schema.json`
- `schemas/proposal.schema.json`
- `schemas/proposal-review.schema.json`
- `schemas/asset-calibration-review.schema.json`
- `examples/proposals/bottom-up-proposal.example.json`
- `examples/proposals/top-down-proposal.example.json`

## Controlled vocabularies

- `registry/asset-type-registry.json`
- `registry/edge-type-registry.json`
- `registry/lifecycle-registry.json`
- `config/taxonomy.yaml`
- `ontology/digital-asset-ontology.ttl`
- `ontology/taxonomy.skos.ttl`

## Operations

- `config/sources.example.yaml`
- `docs/OPERATIONS.md`
- `docs/PROPOSAL_ENGINE_CALIBRATION_WORKFLOW.md` — operational workflow for reviewing bottom-up and top-down proposal engines
- `docs/DOWNSTREAM_REPO_GOVERNANCE.md`
- `docs/TESTING_AND_ORCHESTRATION.md` — marker taxonomy, change-driven test selection, and nox tasks
- `scripts/bootstrap.ps1`
- `scripts/install_to_target.ps1`
- `scripts/new_repo.ps1` — scaffold a new repository pre-wired to this hub
- `scripts/claude_hook.py`
- `scripts/register_scheduled_scan.ps1`
- `scripts/unregister_scheduled_scan.ps1`

## Roadmap

- `roadmap/roadmap.yaml`
- `roadmap/state.json`
- `docs/ROADMAP_EXECUTION.md`

- `docs/DATA_DICTIONARY.md` — field meanings and authority posture.
- `registry/capability-registry.json` — controlled capability IDs.
- `registry/need-registry.json` — controlled missing-part IDs.

- `VERIFICATION_REPORT.md` — verified checks, scope, and environment-dependent gaps
