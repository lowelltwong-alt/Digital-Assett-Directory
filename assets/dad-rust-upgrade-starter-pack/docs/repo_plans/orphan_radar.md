# Repo Rust Plan

Status categories are candidate planning labels, not canonical repo authority.


## `orphan-radar`

| Field | Value |
|---|---|
| Rust status | `medium_low_optional` |
| Priority | `9` |
| Plane | local note graph maintenance engine |
| Confidence | medium |
| Risk | low-medium. |

## Why

Fast markdown link extraction and note hash manifests may help large vaults; TF-IDF and graph logic can stay Python.

## First Rust slice

tools/orphan_scan_core: markdown link extraction, note inventory, source hash manifest, edge list.

## Keep in Python / non-Rust

NetworkX/scikit-learn scoring, report generation, calibration.

## CI posture

Only when vault size makes scan slow.

## Preparation checklist

- Confirm stable input and output artifacts.
- Define JSON/JSONL schema before implementation.
- Add tiny fixture before large fixture.
- Add no-mutation test if source files are scanned.
- Add Python validator/adapter before changing production workflow.
- Add PR CI before long CI.
- Add long CI only after smoke is stable.
- Record what Rust is not authorized to decide.
