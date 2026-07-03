# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-Talent-Intel-ATS`

| Field | Value |
|---|---|
| Rust status | `medium_later_shared_utility` |
| Priority | `7` |
| Plane | ATS/recruiting archive + shared UI workspaces |
| Confidence | medium-low |
| Risk | medium: source truth separation must not collapse LinkedIn and Nevada workspaces. |

## Why

SQLite, LinkedIn archive, Nevada workspace, UI app-state and exports may need a shared ingestion/fingerprint core later.

## First Rust slice

Reuse talent_ingest_core if workspace volume grows; no separate Rust crate first.

## Keep in Python / non-Rust

UI state, outreach packet shaping, scoring policy, reviewed cross-workspace links.

## CI posture

No Rust until shared ingest contract exists.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
