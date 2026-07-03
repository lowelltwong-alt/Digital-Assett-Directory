# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `Bi-Test`

| Field | Value |
|---|---|
| Rust status | `none_now` |
| Priority | `22` |
| Plane | Power BI candidate test package |
| Confidence | high |
| Risk | low. |

## Why

Small Python tooling and packaging workflow; candidate task is Power BI, not Rust.

## First Rust slice

None.

## Keep in Python / non-Rust

Dataset generation, package validation, candidate zip build.

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
