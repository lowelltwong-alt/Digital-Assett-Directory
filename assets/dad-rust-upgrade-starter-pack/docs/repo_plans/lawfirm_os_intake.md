# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-os-intake`

| Field | Value |
|---|---|
| Rust status | `immediate_narrow` |
| Priority | `3` |
| Plane | LawFirm OS vertical workflow composition/evaluation |
| Confidence | high |
| Risk | medium-high: legal workflow logic must not move into Rust evidence scanner. |

## Why

Long artifact chain with source inventory, provenance-preserving segmentation, ledgers, hashes, smoke demo, and long pytest/smoke gates.

## First Rust slice

tools/intake_ingest_probe: source inventory, byte/line offsets, hashes, duplicate source candidates, JSONL ledger integrity.

## Keep in Python / non-Rust

Legal/domain candidate generation, budget workflows, human gates, Excel/openpyxl, review packets.

## CI posture

PR smoke on synthetic fixture; full ingest probe on nightly/manual or input-path changes.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
