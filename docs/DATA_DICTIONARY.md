# Data Dictionary

## Core identity

| Field | Meaning | Authority |
|---|---|---|
| `asset_id` | Stable identifier for a logical asset at a source identity and logical path. | Directory contract |
| `revision_id` | Identifier for one content revision of an asset. | Derived from asset identity + content hash |
| `source_id` | Registered local or GitHub source adapter identity. | Source configuration |
| `parent_asset_id` | Container/repository relationship. | Observed source hierarchy |
| `logical_path` | Path using a source alias rather than exposing an absolute local path. | Normalized observation |
| `content_hash` | SHA-256 locally or Git blob identity remotely. | Observed evidence |

## Discovery and use

| Field | Meaning |
|---|---|
| `asset_type` | Form: code, schema, ontology, lesson, evaluation, workflow, and so on. |
| `tags` | Broad topics and facets used for routing. |
| `capabilities` | What the asset can provide. IDs come from `registry/capability-registry.json`. |
| `needs` | Missing dependency or condition that may activate the asset. IDs come from `registry/need-registry.json`. |
| `outcomes` | Future results the asset may support. |
| `entrypoints` | Files a new human or AI should read first. |
| `value_score` | 0–100 review-priority heuristic; not proof of truth or business value. |
| `value_components` | Exposed score dimensions used to produce `value_score`. |
| `metadata.asset_patterns` | File-level generated candidate pattern IDs, such as evaluation harness or model/algorithm hints. |
| `metadata.pattern_evidence` | Evidence terms that caused an asset pattern hint. |
| `metadata.composite_patterns` | Repository or bundle-level generated candidate patterns inferred from connected child assets. |
| `metadata.composite_asset_hint` | Candidate member IDs, child count, and authority note for a possible composite asset. |
| `metadata.instance_of_asset_ids` | For use/run/deployment assets, the assets instantiated together. |
| `metadata.workflow_steps` | For workflow assets, ordered or named steps when known. |

## Governance and time

| Field | Meaning |
|---|---|
| `lifecycle_state` | Discovered, candidate, reviewed, active, dormant, stale, deprecated, archived, missing, quarantined, or tombstoned. |
| `freshness_status` | Current, watch, stale, or unknown relative to the type-specific threshold. |
| `sensitivity` | Public, internal, confidential, restricted, or unknown. |
| `trust_zone` | Source-owned, generated candidate, reviewed candidate, verified, or other registered trust posture. |
| `confidence` | Confidence in the normalized metadata, not confidence that the source claim is true. |
| `first_seen_at` / `last_seen_at` | Catalog observation times. |
| `modified_at` | Source-reported modification time when available. |

## Relationship evidence

Every edge records `edge_type`, source and target IDs, method, confidence, evidence, scan identity, creation time, and review status. A generated edge is a retrieval and review candidate; it does not transfer authority.
