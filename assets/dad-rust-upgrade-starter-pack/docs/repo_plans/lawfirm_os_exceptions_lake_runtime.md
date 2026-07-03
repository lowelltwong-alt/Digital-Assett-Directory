# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-os-exceptions-lake-runtime`

| Field | Value |
|---|---|
| Rust status | `low_medium_later` |
| Priority | `10` |
| Plane | LawFirm OS evidence plane / append-only runtime evidence |
| Confidence | medium |
| Risk | medium: runtime evidence must not become canon. |

## Why

Append-only JSONL event logs and hash-chain/idempotency verification become Rust candidates when event volume grows.

## First Rust slice

tools/exceptions_ledger_verify: JSONL validation, hash-chain verify, idempotency-key scan, no raw-payload enforcement.

## Keep in Python / non-Rust

Runtime facade, policy gates, synthetic/non-synthetic readiness, contract consumption.

## CI posture

PR fixture ledger; long ledger stress test manual/nightly.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
