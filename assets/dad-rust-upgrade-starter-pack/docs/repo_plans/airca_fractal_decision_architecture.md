# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `airca-fractal-decision-architecture`

| Field | Value |
|---|---|
| Rust status | `none_now` |
| Priority | `20` |
| Plane | conceptual decision architecture |
| Confidence | high |
| Risk | low. |

## Why

Content/architecture repo, not a deterministic data runtime.

## First Rust slice

None; maybe future artifact validator if machine-readable artifacts grow.

## Keep in Python / non-Rust

Docs, JSON artifacts, conceptual examples.

## CI posture

No Rust now.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
