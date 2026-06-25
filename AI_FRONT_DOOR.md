# AI Front Door - Digital Asset Directory

## Repository identity

- **Repository:** `Digital-Assett-Directory`
- **Role:** private portfolio intelligence, metadata, graph, discovery, and governed-learning hub
- **Authority level:** authority for this repository's catalog contracts and workflows only
- **Non-authority:** this repository does not redefine the internal canon of any source repository it scans

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
- candidate value, staleness, orphan, missing-part, and synergy scoring;
- lessons and AI handoff capture;
- AI entrypoints and downstream integration templates;
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
| Search external GitHub | `research_missing_part` | query, candidates, license/freshness metadata, human review note |
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
