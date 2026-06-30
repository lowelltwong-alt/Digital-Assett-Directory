# AI Front Door - Digital Asset Directory

## Repository identity

- **Repository:** `Digital-Assett-Directory`
- **Role:** private portfolio intelligence, metadata, graph, discovery, and governed-learning hub
- **Authority level:** authority for this repository's catalog contracts and workflows only
- **Non-authority:** this repository does not redefine the internal canon of any source repository it scans

## Single AI entrypoint

All AI agents start here. Do not begin from a random doc, generated report, or
remembered path. This file is the deterministic front door; it routes agents to
authority, the AI table of contents, knowledge-graph entrypoints, task-specific
contracts, and validation.

```text
AI_FRONT_DOOR.md
-> authority stack
-> AI_TABLE_OF_CONTENTS.md branch
-> knowledge graph entrypoints
-> task-relevant schemas, registries, docs, and roadmap gates
-> generated reports only as candidate evidence
```

AI navigation files follow `docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md`.
Every AI table-of-contents row must give the path, what it is, routing tags,
and when to look further.

## Required read order

1. `AGENTS.md`
2. `MACHINE_NAVIGATION_MANIFEST.json`
3. `registry/source-of-truth.json`
4. `registry/design-authority.json`
5. `registry/identity-layer-registry.json`
6. `AI_TABLE_OF_CONTENTS.md`
7. `docs/ARCHITECTURE.md`
8. `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`
9. task-relevant schemas, registries, and roadmap gates

## AI TOC branches

Use `AI_TABLE_OF_CONTENTS.md` as the branching map after the required read
order. Choose the branch by task, then read only the matching docs, schemas,
registries, evidence, and generated reports needed for the work.

Core branches:

- front doors and authority;
- architecture and knowledge graph;
- contracts and controlled vocabularies;
- operations and validation;
- roadmap evidence;
- reference and generated-candidate surfaces.

## Knowledge graph entrypoints

Knowledge-graph surfaces are navigation and candidate-evidence aids. They do
not prove source truth, value, authority, or promotion.

| Entrypoint | What it is | Use when |
|---|---|---|
| `docs/KNOWLEDGE_GRAPH_MODEL.md` | Conceptual model for asset nodes, edges, authority posture, and graph use. | You need to understand what graph facts can and cannot mean. |
| `registry/edge-type-registry.json` | Controlled edge vocabulary. | You create, interpret, or validate graph relationships. |
| `registry/asset-pattern-registry.json` | Controlled high-leverage pattern vocabulary. | You classify workflows, composite assets, or reusable systems. |
| `registry/template-registry.json` | Controlled template library with forward and reverse dependencies. | You create, update, validate, or reuse templates. |
| `docs/CROSS_REPO_GOVERNANCE_DEPENDENCY_MAP_PATTERN.md` | Reusable cross-repo governance map and child-mirror template pattern. | You design a repo family where upstream governance and child repo mirrors must stay aligned. |
| `ontology/digital-asset-ontology.ttl` | Ontology layer for graph concepts. | You need semantic graph structure or external graph alignment. |
| `ontology/taxonomy.skos.ttl` | Taxonomy layer for broader/narrower concept navigation. | You need controlled concept hierarchy. |
| `processed/graph/graph.json` | Generated graph output. | You need candidate edges from the latest processed catalog; treat as generated evidence. |
| `processed/reports/asset_family_recognition.md` | Generated report of asset-family candidates. | You need composite workflow or family candidates from scans. |
| `processed/reports/workflow_sweeps/workflow_sweeps_index.md` | Generated workflow-sweep index. | You need cross-repo workflow pattern candidates. |
| `processed/reports/workflow_part_recognition.md` | Generated workflow-part report. | You need recombinable workflow sub-unit candidates beneath existing asset patterns. |
| `processed/reports/workflow_part_calibration_review_sample.md` | Stratified workflow-part calibration sample. | You need human labels before workflow parts affect radar, preflight guidance, scoring, or assembly. |
| `processed/reports/workflow_part_usage_guidance.md` | Generated manual guidance from reviewed workflow-part labels. | You need to know which workflow-part candidates are review-use examples, human-gated, rejected noise, or blocked by missing dataflow. |
| `processed/reports/manual_task_queue.md` | Generated manual task queue that re-ranks alerts and workflow-part guidance. | You need the safest next manual review tasks, with source-boundary and red-team posture. |
| `processed/reports/repo_buildout/index.md` | Generated repo-specific buildout advisor index. | You need candidate recommendations for improving one cataloged repo from its own assets and safe cross-repo inspiration. |
| `processed/reports/template_library.md` | Generated template dependency and review-cadence report. | You need to know what templates depend on and what depends on them. |
| `processed/reports/scan_coverage_cycle.md` | Generated no-rescan coverage-cycle log. | You need to know what was checked, intentionally skipped, and should be scanned next without repeating broad passes. |
| `processed/learning/scan_cycle_events.jsonl` | Generated append-only scan-cycle event trail. | You need the sequence of prior coverage passes, skipped signal families, gated next work, and cycle handoff context. |
| `processed/reports/repo_learning_loop_install_scope.md` | Generated repo-learning-loop installation approval scope. | You need candidate repos and proposed files-only install commands before mutating any source repo. |
| `processed/reports/ci_release_artifact_scope.md` | Generated metadata-only CI/release artifact scope. | You need candidate CI workflows, changelogs, QA reports, logs, and lockfiles before authorizing any content reads. |
| `processed/reports/priority_content_extract_scope.md` | Generated metadata-only approval scope for a future bounded content pass. | You need candidate priority paths before any source content is read. |
| `processed/learning/priority_content_observations.jsonl` | Generated bounded observations from approved content reads. | You need candidate content signals after a human-approved scoped extract; do not treat as source truth. |
| `processed/learning/priority_content_lesson_candidates.jsonl` | Generated context-bound lesson candidates from approved content observations. | You need reviewable lesson candidates before any learning rule or preflight default is changed. |
| `processed/learning/learning_rule_promotion_candidates.jsonl` | Generated learning-rule promotion candidate packages. | You need reviewed lesson candidates packaged for later human-approved registry promotion without mutating learning rules. |

## Core boundary

```text
source artifact
-> immutable observation
-> normalized asset candidate
-> candidate graph relations
-> human-reviewable alert or context pack
-> explicit promotion decision, when needed
```

Discovery output is evidence and recommendation, not source-repository authority.

## What this repository owns

- source adapters and scan policy;
- asset identity and revision identity;
- the Asset Identity And Similarity Ladder for exact identity, similarity, graph discovery, and audit provenance;
- catalog metadata and local graph vocabulary;
- generated workflow-part candidates beneath existing asset-family patterns;
- candidate value, staleness, orphan, missing-part, and synergy scoring;
- lessons and AI handoff capture;
- lesson-automation coverage routing and scan-cycle logs;
- AI entrypoints and downstream integration templates;
- cross-repo governance dependency-map template seeds;
- local audit, validation, and roadmap state.

## What this repository must not own

- the meaning or authority rules of a scanned repository;
- silent changes to source repositories;
- automatic promotion of inferred tags, links, or research findings into source canon;
- credentials, API tokens, private keys, or raw secrets;
- a claim that a heuristic score proves truth or importance.

## Work routes

| Intent | Route | Required outputs |
|---|---|---|
| Scan new sources | `source_scan` | raw snapshot, processed assets, audit event, source-mutation check |
| Change metadata contracts | `schema_change` | schema, example, registry update, validation |
| Change graph vocabulary | `ontology_change` | edge registry, ontology/taxonomy update, migration note |
| Change identity or similarity rules | `identity_change` | ladder doc, identity-layer registry, schema/edge updates, validation |
| Add a learning record | `lesson_capture` | lesson JSONL, provenance, confidence, reuse candidates |
| Build a feature | `implementation` | preflight, changed files, tests, postflight, lessons |
| Check operational readiness | `doctor` | readiness JSON, `processed/reports/operational_readiness.md`, missing-surface warnings |
| Search external GitHub | `research_missing_part` | explicit `--enable-external`, query, candidates, license/freshness metadata, human review note |
| Change roadmap | `roadmap_change` | gate evidence, status transition, remaining risks |

## Mandatory AI preflight

Before material changes, report:

```text
Route:
Goal:
Authority files read:
Allowed paths:
Forbidden paths:
Validation plan:
Stop conditions:
Context pack used:
```

Run:

```text
asset-dir agent preflight --repo <repo> --agent <agent> --task "<task>"
```

If the preflight includes `required_learning_rule_acknowledgements`, run a midflight
acknowledgement before proceeding through the matching work:

```powershell
asset-dir agent midflight --session <id> --context "<task context>" --ack-rule "<rule id>"
```

## Mandatory AI postflight

Before reporting completion, record:

```text
Files changed:
Commands run:
Tests run:
Tests not run:
Discoveries:
Failures or uncertainty:
Reusable lessons:
New assets created:
Missing capabilities:
Risks:
Next recommended action:
```

Run:

```text
asset-dir agent postflight --session <id> --repo <repo> --summary "..." --tests "..."
```

## Stop-and-report triggers

Stop rather than guess when:

- the correct source repository or authority file is unclear;
- a scan would traverse a sensitive or excluded location;
- a requested action would modify source artifacts;
- a token or secret appears in content or configuration;
- the same logical asset appears under conflicting identities;
- a proposed workflow treats SHA-256, embeddings, graph similarity, or fuzzy hashing as enough by itself to prove authority, reuse value, or canonical status;
- a proposed relationship would imply authority transfer;
- a schema, lifecycle, or edge definition conflicts with an existing registry;
- validation fails;
- an external repository lacks a reviewable license or provenance path;
- a roadmap phase is being marked complete without its acceptance evidence.

## Validation

```text
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check
```
