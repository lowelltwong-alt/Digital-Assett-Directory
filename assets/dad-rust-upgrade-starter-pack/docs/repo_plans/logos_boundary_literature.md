# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `logos-boundary-literature`

| Field | Value |
|---|---|
| Rust status | `low_wait_for_corpus` |
| Priority | `15` |
| Plane | Logos boundary/noncanonical literature scaffold |
| Confidence | high |
| Risk | medium: boundary material must not contaminate canonical Scripture. |

## Why

Currently scaffold/no source text imported. Rust is premature until actual corpus/metadata ingest exists.

## First Rust slice

Future boundary_source_audit after corpus import: source metadata, trust profile, contamination checks.

## Keep in Python / non-Rust

Trust hierarchy, routing guardrails, review status, governance constraints.

## CI posture

No Rust until data/ corpus exists.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
