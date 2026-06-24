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

## Authority model

- Source repositories govern their own internal meaning.
- Raw observations record what was seen.
- Processed records are candidate interpretations.
- A score or generated edge is never an authority transfer.

## Scale posture

The graph builder avoids full all-pairs comparison. Candidate pairs are generated through shared tags, capabilities, needs, and outcomes, then capped per asset. This is adequate for thousands of assets; larger corpora should add a dedicated inverted index or vector retrieval layer after evaluation.
