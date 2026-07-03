# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-os-orchestrator`

| Field | Value |
|---|---|
| Rust status | `low_optional_verifier` |
| Priority | `12` |
| Plane | LawFirm OS execution plane |
| Confidence | medium |
| Risk | medium: Rust must not create route/event authority. |

## Why

Mostly orchestration, autonomy gates, harness selection, owner packets. Rust only for packet/ledger/hash verification later.

## First Rust slice

tools/orchestrator_packet_verify: packet hash verification, contract pin drift check, JSONL evidence packet integrity.

## Keep in Python / non-Rust

Autonomy classification, harness selection, human pauses, owner packet assembly.

## CI posture

Only after packet volumes grow.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
