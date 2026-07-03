# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-os-talent-intelligence`

| Field | Value |
|---|---|
| Rust status | `medium_later_scaling` |
| Priority | `6` |
| Plane | talent intelligence runtime/state-by-state data system |
| Confidence | medium |
| Risk | medium: identity resolution must remain review-gated. |

## Why

Bulk CSV/import normalization, SQLite loading, identity fingerprints, public-source snapshots become Rust candidates when scaling beyond Nevada.

## First Rust slice

tools/talent_ingest_core: CSV normalization, snapshot hashes, identity-fingerprint candidate features, bulk SQLite import.

## Keep in Python / non-Rust

Review queues, exports, CRM/ATS boundaries, attorney/firms interpretation, workbook/dashboard generation.

## CI posture

PR tiny fixture; long state import on manual/nightly.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
