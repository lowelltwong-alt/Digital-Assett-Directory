# Scan-Cycle Events And Learning-Rule Promotion Candidates V1

## Summary

This change adds two generated-only safety surfaces for future agents:

- append-only scan-cycle events at `processed/learning/scan_cycle_events.jsonl`;
- learning-rule promotion candidate packages at `processed/learning/learning_rule_promotion_candidates.jsonl`.

Both are routing and review evidence only. They do not authorize new scans, mutate
source repositories, call external services, or edit `registry/learning-rule-registry.json`.

## Why

Future agents need to know what prior passes checked, what was intentionally
skipped, and which signal family should be considered next. A single overwritten
coverage report is useful as a dashboard, but not enough as history.

Reviewed lesson candidates also need a safe intermediate package before any
learning rule can affect preflight or midflight behavior. Accepted review-use
labels are not promotion.

## Boundaries

- `ScanCycleEventRecord` is generated candidate history, not proof of source
  value or permission to broaden source scope.
- `LearningRulePromotionCandidateRecord` contains a proposed `LearningRuleRecord`
  and human gates, but always records `registry_mutated=false`.
- Actual learning-rule promotion remains a later human-approved registry edit.
- Generated outputs stay under ignored `processed/`.

## Red-Team And Premortem

- Risk: future agents could treat a scan-cycle gap as permission to scan. Guard:
  each event carries authority boundaries, applies/does-not-apply, and danger
  notes.
- Risk: a reviewed lesson could become an over-broad deterministic rule. Guard:
  promotion candidates preserve `applies_when`, `does_not_apply_when`, and
  danger language, and require a separate human registry gate.
- Risk: repeated coverage runs could create noisy history. Guard: the latest
  dashboard remains separate from append-only history; agents should read the
  most recent entries and current `scan_coverage_cycle.md` together.

## Validation

Required validation:

```powershell
python -m pytest
python -m ruff check src tests scripts noxfile.py
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
```

## Acceptance Status

Implemented as generated candidate infrastructure. No roadmap phase is marked
complete by this evidence.
