# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `fmg-fractal-capability-ontology`

| Field | Value |
|---|---|
| Rust status | `low_control_plane_not_now` |
| Priority | `17` |
| Plane | FMG semantic control plane / contract repo |
| Confidence | medium-high |
| Risk | medium. |

## Why

Similar to LawFirm Semantic Substrate; Python/rdflib/pyshacl contract validation is appropriate now.

## First Rust slice

Optional shared contract linter if validation becomes slow.

## Keep in Python / non-Rust

Ontology, governance, schemas, SHACL, audit wrappers.

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
