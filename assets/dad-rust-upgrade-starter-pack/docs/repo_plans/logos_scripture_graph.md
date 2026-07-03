# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `logos-scripture-graph`

| Field | Value |
|---|---|
| Rust status | `immediate_already_started` |
| Priority | `2` |
| Plane | Logos deterministic Scripture data plane |
| Confidence | high |
| Risk | medium: must preserve no-text/non-authorizing boundaries. |

## Why

Existing Rust USFM observation scanner, large word-token artifacts, raw-source scan/ingest/chunk/index pipeline.

## First Rust slice

Split usfm_observation_scanner into modules; add cargo test/fmt/clippy; add manual/nightly full-scan workflow.

## Keep in Python / non-Rust

Governance validation, theological decision registers, route/evaluator authority, reviewed-gold promotion.

## CI posture

PR contract-only + cargo tests; full scan only path-triggered/manual/nightly.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
