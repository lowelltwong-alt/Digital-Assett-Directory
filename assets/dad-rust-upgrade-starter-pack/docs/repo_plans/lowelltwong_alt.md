# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `lowelltwong-alt`

| Field | Value |
|---|---|
| Rust status | `none_now` |
| Priority | `24` |
| Plane | GitHub profile/routing repo |
| Confidence | high |
| Risk | low. |

## Why

Profile routing and public repo map; no Rust runtime surface.

## First Rust slice

None.

## Keep in Python / non-Rust

Markdown/registry routing.

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
