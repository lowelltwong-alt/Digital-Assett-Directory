# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `Albert-Trial-Simulation-System`

| Field | Value |
|---|---|
| Rust status | `high_next_case_scaling` |
| Priority | `4` |
| Plane | mock-trial KG / evidence / simulation system |
| Confidence | medium-high |
| Risk | medium-high: do not encode legal strategy or witness knowledge rules in early Rust. |

## Why

Evidence source inventory, OCR artifact checks, path isolation, chunk manifests, multi-case outputs, and simulation snapshots are repeatable data paths.

## First Rust slice

tools/albert_evidence_indexer: raw/processed evidence hash inventory, OCR completeness, path-isolation and chunk-manifest outputs.

## Keep in Python / non-Rust

Trial strategy, witness prep, case interpretation, Monte Carlo governance, human decision sessions.

## CI posture

PR path/hash smoke; full multi-case artifact audit as long CI/manual.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
