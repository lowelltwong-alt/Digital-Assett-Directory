# Data Dictionary

## Core identity

| Field | Meaning | Authority |
|---|---|---|
| `asset_id` | Stable identifier for a logical asset at a source identity and logical path. | Directory contract |
| `revision_id` | Identifier for one content revision of an asset. | Derived from asset identity + content hash |
| `source_id` | Registered local or GitHub source adapter identity. | Source configuration |
| `parent_asset_id` | Container/repository relationship. | Observed source hierarchy |
| `logical_path` | Path using a source alias rather than exposing an absolute local path. | Normalized observation |
| `content_hash` | Scanner revision identity hash. It may be exact content identity or metadata-derived when content was intentionally not read. | Observed evidence |
| `metadata_fingerprint` | Fast fingerprint of observable metadata such as size, timestamps, and platform attributes. | Derived observation |
| `content_sha256` | Exact SHA-256 of file bytes when bytes were safely read; otherwise `null`. | Exact observed evidence when present |
| `source_provenance` | Source adapter, path/repo context, scanner, and authority boundary. | Normalized observation |

## Identity layers

| Record | Meaning | Authority |
|---|---|---|
| `AssetChunkRecord` | Deterministic token-shingle or metadata chunk tied to one asset revision. | Generated candidate evidence |
| `DuplicateClusterRecord` | Exact-content or near-duplicate candidate group of assets. | Generated candidate evidence |
| `AssetDeltaRecord` | Pairwise exact/near duplicate delta summary and shared/one-sided chunk hashes. | Generated candidate evidence |
| `exact_duplicate_of` edge | Assets share the same non-empty exact `content_sha256`. | Generated candidate relationship |
| `near_duplicate_of` edge | Assets share enough deterministic token-shingle MinHash similarity to warrant review. | Generated candidate relationship |
| `contained_in` edge | Most source shingles appear inside the target asset even when symmetric overlap is lower. | Generated candidate relationship |
| `has_delta_candidate` edge | A generated delta record exists for the asset pair. | Generated candidate relationship |

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
| `metadata.chunk_text` | Redacted extracted text used for deterministic token-shingle chunking. Generated output only. |

## Governance and time

| Field | Meaning |
|---|---|
| `lifecycle_state` | Discovered, candidate, reviewed, active, dormant, stale, deprecated, archived, missing, quarantined, or tombstoned. |
| `freshness_status` | Current, watch, stale, or unknown relative to the type-specific threshold. |
| `sensitivity` | Public, internal, confidential, restricted, or unknown. |
| `trust_zone` | Source-owned, generated candidate, reviewed candidate, verified, or other registered trust posture. |
| `confidence` | Heuristic strength/confidence in normalized metadata, not calibrated P(useful) and not confidence that the source claim is true. |
| `first_seen_at` / `last_seen_at` | Catalog observation times. |
| `modified_at` | Source-reported modification time when available. |

## Relationship evidence

Every edge records `edge_type`, source and target IDs, method, confidence, evidence, scan identity, creation time, and review status. A generated edge is a retrieval and review candidate; it does not transfer authority.
