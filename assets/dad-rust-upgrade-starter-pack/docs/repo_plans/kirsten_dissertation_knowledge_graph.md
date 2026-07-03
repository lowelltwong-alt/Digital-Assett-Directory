# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `kirsten-dissertation-knowledge-graph`

| Field | Value |
|---|---|
| Rust status | `low_later_if_citation_audit_slow` |
| Priority | `16` |
| Plane | dissertation citation/source KG |
| Confidence | medium |
| Risk | medium: citation correctness cannot be inferred from structural checks alone. |

## Why

Citation/source hash ledger validation could benefit later, but corpus is manageable and correctness/review matters more than speed.

## First Rust slice

tools/citation_ledger_check: source-file hashes, citation registry integrity, PDF/source inventory.

## Keep in Python / non-Rust

Citation judgment, APA/final-review logic, manual DOCX fixes, source verification decisions.

## CI posture

Only when citation validators slow down.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
