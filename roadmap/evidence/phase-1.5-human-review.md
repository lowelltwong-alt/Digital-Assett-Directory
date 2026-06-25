# Phase 1.5 Human Review And Research

Status: human-authorized roadmap gate review. Generated catalog outputs remain
candidate evidence. This file does not apply Phase 2 labels and does not claim
asset-value probability calibration is complete.

Date: 2026-06-25

Reviewer context: Lowell asked Codex to perform the Phase 1.5 human review and
to add the supporting research. Codex prepared this evidence from local files,
generated reports, tests, and the prior Claude/Codex red-team research.

## Scope

This review covers Phase 1.5:

- scanner noise excludes and quarantine reporting;
- score methodology and discount metadata;
- regenerated clean calibration sample methodology.

It does not cover Phase 2 asset rating labels. The current calibration template
has zero reviewed labels and still needs separate human scoring work.

## Evidence Reviewed

- `config/sources.example.yaml`
- `config/sources.local.yaml`
- `src/digital_asset_directory/local_scan.py`
- `src/digital_asset_directory/instance_class.py`
- `src/digital_asset_directory/scoring.py`
- `src/digital_asset_directory/calibration.py`
- `src/digital_asset_directory/catalog.py`
- `tests/test_local_scan.py`
- `tests/test_scoring.py`
- `tests/test_phase2_calibration.py`
- `tests/test_validation_roadmap.py`
- `docs/ASSET_VALUE_MODEL.md`
- `docs/DATA_DICTIONARY.md`
- `docs/ROADMAP_EXECUTION.md`
- `roadmap/evidence/phase-1.5-scoring-discipline.md`
- `roadmap/evidence/phase-2-temp-fixture-calibration-research.md`
- `roadmap/evidence/phase-2-claude-second-opinion.md`
- `roadmap/evidence/phase-2-claude-red-team-premortem.md`
- `processed/reports/quarantine_summary.md`
- `processed/reports/scan_summary.md`
- `processed/reports/asset_rating_calibration_summary.md`

## Research Findings

### Scanner Noise And Quarantine

The scanner now suppresses the red-team noise classes from scoring by default:

- `.pytest-tmp-root`;
- `pytest-of-*`;
- `_codex_worktrees`;
- `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.nox`, and `.tox`;
- `.DS_Store`, `Thumbs.db`, and `desktop.ini`;
- this hub's generated `raw`, `processed`, `state`, and `audit` folders.

The quarantine output is generated evidence only. Quarantined paths do not create
`AssetRecord`s and do not become roadmap truth by themselves.

The latest generated quarantine report came from a bounded validation scan:

- scan id: `dad:scan:f9dec3c0-3fdf-4657-9c1a-cba16fb70207`;
- status: `complete`;
- assets: `505`;
- changed during scan: `0`;
- source files mutated: `False`;
- quarantine count: `1`;
- bounded scan: `True`;
- inspected paths: `500`;
- reason observed: `pytest cache`.

Review conclusion: the scanner-noise and quarantine behavior is accepted for the
Phase 1.5 gate. The caveat is that this is a behavior and methodology approval,
not proof that a full unbounded portfolio scan is fast enough. The full local
scan over the whole Git Projects tree timed out during implementation and needs
a later performance slice.

### Score Methodology

The scorer now uses methodology
`asset-value-v0.2-red-team-discipline`.

The accepted design changes are:

- deterministic instance classes for source, archive, generated output, temp
  fixture, worktree copy, OS junk, and unknown observations;
- deterministic information-content classification for empty markers,
  metadata-only observations, extracted content, binary metadata, and
  content-bearing files;
- explicit `information_content` score component;
- score metadata including methodology version, eligibility, heuristic strength,
  and discount reasons;
- evidence-gated type bonuses so schema, test, and evaluation labels alone do
  not grant high scores;
- multiplicative discounts before banding for temp/worktree/generated instances,
  OS/cache junk, empty markers, metadata-only observations, and duplicate
  non-representatives;
- continued candidate-only status for all generated scores.

Review conclusion: the score methodology is accepted for Phase 1.5. The score is
still a heuristic routing signal, not a calibrated probability.

### Clean Sampling

The regenerated asset calibration sample reports methodology
`asset-calibration-sampling-v0.2-clean-deduped`.

Current summary:

- template records: `100`;
- reviewed records: `0`;
- stale sample warning: `False`;
- instance classes: `source=91`, `archive=9`;
- score ratings: `unreviewed=100`;
- value bands: `medium=50`, `low=50`.

The sample is clean enough to start Phase 2 labeling because it is no longer the
old temp-fixture dominated 50-record sample. It is not Phase 2 evidence yet
because no labels have been applied.

Review conclusion: the clean-sampling gate is accepted. Phase 2 can now proceed
to human asset rating labels and structured false-positive, false-negative, and
weight-change notes.

## Gate Decisions

| gate | decision | caveat |
| --- | --- | --- |
| `phase-1.5-noise-quarantine-reviewed` | verified | Full unbounded scan performance remains a follow-up. |
| `phase-1.5-score-methodology-reviewed` | verified | Scores remain heuristic strength, not probabilities. |
| `phase-1.5-clean-calibration-sample-reviewed` | verified | The sample has zero reviewed labels; Phase 2 is still separate. |

## What This Unlocks

Phase 1.5 can be treated as complete by the roadmap checker once gate evidence
is recorded. That should unblock Phase 2 from dependency-blocked to
awaiting-human-gate.

The next work should be Phase 2 labeling:

- review at least 50 asset rating records;
- capture false-positive and false-negative notes;
- document any weight-change notes;
- keep temp-fixture findings as bug evidence, not as labels on the old stale
  sample.

## Risks And Follow-Ups

- Full local scan performance is still not solved.
- The quarantine report from the validation run is bounded and should not be
  described as a complete portfolio quarantine census.
- Media extraction is intentionally minimal and bounded.
- Path-based instance classification may need more patterns after more repos are
  scanned.
- The database may still contain older records until a full refreshed scan is
  completed.

## Reusable Lesson

A human review gate should separate three things that are easy to blur:

1. implementation behavior is accepted;
2. generated evidence is present and reviewable;
3. downstream calibration labels are complete.

Phase 1.5 satisfies the first two. Phase 2 is where the third begins.
