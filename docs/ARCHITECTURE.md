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
        +----> extracted text, when safe and supported
        +----> embeddings only after privacy/license/provider/eval gates
        +----> duplicate / near-duplicate cluster candidates
        +----> delta records between similar assets
        +----> knowledge-graph role and relationship signals
        +----> append-only audit events
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

The deterministic v1 follows the Asset Identity And Similarity Ladder in
`docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`:

- metadata fingerprint: fast change detection and metadata-only broad scans;
- exact SHA-256: exact content sameness when available;
- chunk records: overlapping token shingles or metadata chunks tied to a specific asset revision;
- extracted text: generated evidence for comparison, tagging, and indexing when safe and supported;
- exact duplicate clusters: assets with the same non-empty `content_sha256`;
- near-duplicate clusters: generated candidates from deterministic token-shingle MinHash similarity;
- containment candidates: generated `contained_in` edges when most source shingles appear inside a larger target;
- delta records: bounded pairwise evidence showing exact match or shared/one-sided chunk hashes;
- graph edges: `exact_duplicate_of`, `near_duplicate_of`, `has_delta_candidate`, and role/similarity
  edges for retrieval and review;
- audit logs: append-only scan, lesson, handoff, and governance evidence.

`related_to` graph edges use IDF-weighted cosine over bounded rare-token candidate sets. This keeps common boilerplate from dominating relation evidence while staying deterministic.

Embeddings and external semantic enrichment remain deferred until the relevant privacy, provider, and evaluation gates are approved.

## Authority model

- Source repositories govern their own internal meaning.
- Raw observations record what was seen.
- Processed records are candidate interpretations.
- A score or generated edge is never an authority transfer.

## Scale posture

The graph builder avoids full all-pairs comparison. Candidate pairs are generated through shared tags, capabilities, needs, and outcomes, then capped per asset. This is adequate for thousands of assets; larger corpora should add a dedicated inverted index or vector retrieval layer after evaluation.

## Retention and garbage collection

Assets are keyed by stable `asset_id` and upserted, so they do not multiply
across scans. The per-scan *generated* records — `edges`, `asset_chunks`,
`asset_deltas`, `duplicate_clusters`, and open `alerts` — are only valid for the
scan that produced them. Without retention they accumulated every scan (a
pre-migration catalog reached 1.6 GB with ~178k perpetually-open alerts before
this was fixed).

`run_scan` therefore prunes non-latest generated rows, but **only after a
full-scope scan**: a bounded or partial run (`--local-only`, `--github-only`,
`--max-files`, or any run where a source errored) updates what it saw without
pruning the rest of the graph, because it did not regenerate the sources it
skipped. The scan summary reports the outcome under `retention_pruned`
(`scope: full|partial`). `asset-dir catalog-vacuum` performs one-time pruning
plus `VACUUM`; it keys on the latest **complete** scan, never a crashed or
failed one, so a failed newest scan cannot delete the last good graph.

Human-acknowledged or resolved alerts (`status != open`) are preserved by
pruning as a safety net.

**Deferred (known limitation):** an alert's identity embeds its `scan_id`, so an
acknowledgment on one scan's alert does not suppress the identical condition
re-firing as a new open alert on the next scan. Retention bounds the resulting
volume (open alerts are pruned to the latest scan), so this is no longer a
bloat risk, only a UX gap. A future change should drop `scan_id` from alert
identity (keeping it as a field) so recurrence deduplicates, while still letting
human status win over regeneration.
