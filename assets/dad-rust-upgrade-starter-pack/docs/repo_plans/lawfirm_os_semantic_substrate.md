# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `LawFirm-os-semantic-substrate`

| Field | Value |
|---|---|
| Rust status | `low_control_plane_not_now` |
| Priority | `13` |
| Plane | LawFirm OS canonical control plane |
| Confidence | high |
| Risk | medium-high if Rust is allowed to encode policy authority prematurely. |

## Why

Governance, schema authority, registries, and meaning boundaries are human-readable control-plane surfaces; Python validators are sufficient unless slow.

## First Rust slice

Optional lawfirm_contract_lint later: duplicate IDs, changed-path coverage, JSON registry coverage, link checks.

## Keep in Python / non-Rust

All semantic authority, governance maps, schemas, SHACL, review processes.

## CI posture

Keep existing Python validation.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
