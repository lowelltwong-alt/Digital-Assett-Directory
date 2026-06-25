# Phase 1.5 Scoring Discipline Evidence

Status: generated implementation evidence. Human gate decisions are recorded in
`roadmap/evidence/phase-1.5-human-review.md` and
`roadmap/gate-evidence.json`.

Date: 2026-06-25

## Scope

This checkpoint implements the scoring and sampling discipline needed before more
Phase 2 calibration labels are applied.

It remains local-only and candidate-only:

- no GitHub scanning was enabled;
- no scanned source repository was mutated;
- no human labels were invented or applied;
- no roadmap phase was marked complete by this evidence file.

## Implemented Evidence

- Added deterministic instance classification for source, archive, generated,
  temp fixture, worktree, and OS junk observations.
- Added deterministic information-content classification for OS junk, empty
  markers, empty files, metadata-only observations, extracted content, binary
  metadata, and content-bearing files.
- Updated value scoring to methodology
  `asset-value-v0.2-red-team-discipline`.
- Added `information_content` as an explicit score component.
- Gated schema, test, and evaluation type bonuses on direct value evidence.
- Applied multiplicative discounts for temp fixtures, worktrees, generated
  outputs, OS junk, empty/marker files, metadata-only observations, and
  non-representative duplicates.
- Preserved temp/worktree/generated observations as lineage or quarantine
  evidence rather than treating them as independent current value by default.
- Added clean calibration sampling methodology
  `asset-calibration-sampling-v0.2-clean-deduped`.
- Made Phase 2 calibration evidence fail closed when the asset sample uses a
  missing or legacy sample methodology.

## Review Consequence

The current pre-fix Phase 2 sample can still be useful as bug evidence. It should
not be used to satisfy the Phase 2 human calibration gate. A fresh clean,
deduped sample should be regenerated before additional labels are applied.

Review order for each asset remains:

1. Current score only.
2. Duplicate, temp, generated, or noise status.
3. Real semantic evolution.
4. Upside and ceiling after the current-score label.

## Human Review Update

The Phase 1.5 review now verifies:

- `phase-1.5-noise-quarantine-reviewed`
- `phase-1.5-score-methodology-reviewed`
- `phase-1.5-clean-calibration-sample-reviewed`

The review accepts the behavior and methodology gates. It does not apply Phase 2
asset rating labels and does not claim a full unbounded portfolio scan is fast
enough.

## Risks

- Clean sampling depends on a refreshed catalog and regenerated calibration
  reports; existing generated reports may still reflect old score metadata.
- Path-based instance classification can still misclassify unusual repos until
  human review expands the pattern list.
- Discounts are heuristic routing controls, not calibrated probabilities.
- Content extraction remains bounded and may miss value in files that require
  richer parsers.

## Reusable Lesson

When a score drives human calibration, its formula, eligibility gates, noise
classes, duplicate handling, and sample methodology must be explicit before the
labels are collected. Otherwise human review can accidentally validate scanner
noise instead of asset value.
