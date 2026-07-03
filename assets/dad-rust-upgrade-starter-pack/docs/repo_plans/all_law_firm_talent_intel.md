# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `All-Law-Firm-Talent-Intel`

| Field | Value |
|---|---|
| Rust status | `unknown_low` |
| Priority | `18` |
| Plane | unknown / possibly empty or legacy talent-intel surface |
| Confidence | low |
| Risk | unknown. |

## Why

README was not found in accessible path during inspection; treat as unknown until repo content is audited.

## First Rust slice

None until DAD scans it and identifies active data paths.

## Keep in Python / non-Rust

Unknown.

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
