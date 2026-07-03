# Skill: Rust Python Bridge

## Purpose

Connect Rust leaf tools to Python orchestration safely.

## Default bridge

Use CLI + JSON/JSONL first.

## Promote to PyO3 only when

- CLI boundary is stable;
- JSONL overhead is proven to be the bottleneck;
- packaging needs justify Python extension complexity;
- CI can build wheels on target platforms.

## Required safeguards

- Python validates Rust output before ingestion.
- Rust errors fail closed.
- Fallbacks are explicit.
- No raw payload leaks.
- No authority bypass.
