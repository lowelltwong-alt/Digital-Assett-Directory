# Architecture

## Architectural position

The directory is a **portfolio intelligence hub**, not a replacement monorepo and not a source-of-truth override for scanned repositories.

```text
Local drive + GitHub
        |
        v
Read-only source adapters
        |
        v
Raw immutable observations -----> append-only audit
        |
        v
Normalization + stable identity + revision identity
        |
        v
Layered identity records
        |
        +----> metadata fingerprints
        +----> optional exact content SHA-256
        +----> deterministic chunk records
        +----> duplicate / near-duplicate cluster candidates
        +----> delta records between similar assets
        |
        v
SQLite catalog + JSONL export
        |
        v
Knowledge graph + value/freshness scoring
        |
        +----> Orphan / missing-part radar
        +----> Dormant activation radar
        +----> Synergy and bundle candidates
        +----> Context packs for AI and humans
        +----> External GitHub research candidates
        |
        v
Human review / governed promotion / downstream reuse
```

## Why SQLite plus graph exports

The seed uses SQLite as the durable local catalog and NetworkX/JSON/GraphML as regenerable graph surfaces. This keeps the first build portable, inspectable, and local-first while leaving room for later graph databases or vector stores.

## Identity model

- `asset_id` is stable for a logical asset location and source identity.
- `revision_id` changes with content hash.
- A file edit therefore creates a new revision without pretending the logical asset is a different thing.
- Moves and renames are initially new logical assets unless a reviewed migration or high-confidence lineage rule connects them.
- `metadata_fingerprint` is a fast observable-state fingerprint for broad scans and change detection.
- `content_sha256` is present only when file bytes were read safely and can support exact duplicate evidence.
- `content_hash` remains the scanner's revision identity hash and may be metadata-derived for oversized, offline, or intentionally metadata-only files.
- `chunks.jsonl`, `duplicate_clusters.jsonl`, and `deltas.jsonl` are generated evidence surfaces, not source-of-truth promotion.

## Similarity and delta layers

The deterministic v1 uses multiple bounded layers:

- metadata fingerprint: fast change detection and metadata-only broad scans;
- exact SHA-256: exact content sameness when available;
- chunk records: overlapping token shingles or metadata chunks tied to a specific asset revision;
- exact duplicate clusters: assets with the same non-empty `content_sha256`;
- near-duplicate clusters: generated candidates from deterministic token-shingle MinHash similarity;
- containment candidates: generated `contained_in` edges when most source shingles appear inside a larger target;
- delta records: bounded pairwise evidence showing exact match or shared/one-sided chunk hashes;
- graph edges: `exact_duplicate_of`, `near_duplicate_of`, and `has_delta_candidate` edges for retrieval and review.

`related_to` graph edges use IDF-weighted cosine over bounded rare-token candidate sets. This keeps common boilerplate from dominating relation evidence while staying deterministic.

Embeddings and external semantic enrichment remain deferred until the relevant privacy, provider, and evaluation gates are approved.

## Authority model

- Source repositories govern their own internal meaning.
- Raw observations record what was seen.
- Processed records are candidate interpretations.
- A score or generated edge is never an authority transfer.

## Scale posture

The graph builder avoids full all-pairs comparison. Candidate pairs are generated through shared tags, capabilities, needs, and outcomes, then capped per asset. This is adequate for thousands of assets; larger corpora should add a dedicated inverted index or vector retrieval layer after evaluation.
