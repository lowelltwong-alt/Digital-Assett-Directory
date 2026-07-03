# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `exceptions-lake-runtime`

| Field | Value |
|---|---|
| Rust status | `low_medium_later_shared` |
| Priority | `11` |
| Plane | older/general Exceptions Lake runtime |
| Confidence | medium-low |
| Risk | low-medium. |

## Why

Could reuse the LawFirm OS ledger verifier if both runtimes remain active.

## First Rust slice

Shared exceptions_ledger_verify only if older FMG runtime remains maintained.

## Keep in Python / non-Rust

Contract consumption and MVP runtime behavior.

## CI posture

Only after shared verifier exists.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
