# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `obsidian-foundry-vault`

| Field | Value |
|---|---|
| Rust status | `low_optional_vault_scan` |
| Priority | `19` |
| Plane | Obsidian/vault content surface |
| Confidence | low-medium |
| Risk | low. |

## Why

If it is a large markdown vault, a Rust note scanner could be useful, but Orphan Radar/DAD should own that first.

## First Rust slice

Reuse orphan_scan_core or DAD scanner; no custom crate first.

## Keep in Python / non-Rust

Vault-specific curation and human review.

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
