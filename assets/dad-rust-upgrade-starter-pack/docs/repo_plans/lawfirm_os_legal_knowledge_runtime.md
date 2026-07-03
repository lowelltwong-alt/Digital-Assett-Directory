# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-os-legal-knowledge-runtime`

| Field | Value |
|---|---|
| Rust status | `medium_later` |
| Priority | `8` |
| Plane | legal document ingestion/retrieval context runtime |
| Confidence | medium |
| Risk | medium-high: retrieval/model output must not become legal truth. |

## Why

Document preflight, hashes, offsets, chunk candidates, and Legal Context Bundle source refs are Rust-suitable after corpus volume grows.

## First Rust slice

tools/legal_doc_preflight: source inventory, hash manifest, offset map, bounded text profile, chunk-boundary candidates.

## Keep in Python / non-Rust

Legal Context Bundle assembly, legal workflow semantics, human-review/finality boundaries.

## CI posture

Synthetic fixture only at first.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
