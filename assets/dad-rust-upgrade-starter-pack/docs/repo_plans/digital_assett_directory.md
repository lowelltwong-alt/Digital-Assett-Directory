# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `Digital-Assett-Directory`

| Field | Value |
|---|---|
| Rust status | `immediate` |
| Priority | `1` |
| Plane | portfolio intelligence / asset graph runtime |
| Confidence | high |
| Risk | medium: avoid replacing DAD orchestration before Rust observation contract is stable. |

## Why

Local/GitHub scanning, hashing, duplicate detection, quarantine, bounded extraction, JSONL/SQLite/graph output are deterministic hot paths.

## First Rust slice

tools/dad_scan_core: local source scanner emitting raw asset observation JSONL and quarantine report.

## Keep in Python / non-Rust

Typer CLI, SQLite orchestration, graph/radar scoring, recommendations, context packs, lessons, mail/usage workflows.

## CI posture

PR smoke + long nightly/manual scanner regression.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
