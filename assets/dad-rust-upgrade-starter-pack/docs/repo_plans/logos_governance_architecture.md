# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `logos-governance-architecture`

| Field | Value |
|---|---|
| Rust status | `low_control_plane_not_now` |
| Priority | `14` |
| Plane | Logos theological/governance source architecture |
| Confidence | high |
| Risk | medium-high: do not make tool output certify governance truth. |

## Why

Defines source-trust, derivation, authority, and review obligations; not the deterministic data plane.

## First Rust slice

Optional logos_gov_lint much later for link/frontmatter/dependency-map coverage.

## Keep in Python / non-Rust

Governance semantics, theological derivation, authority boundaries, dependency map policy.

## CI posture

Keep Python validators.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
