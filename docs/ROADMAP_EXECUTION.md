# Roadmap Execution

Run:

```text
asset-dir roadmap check
```

The checker computes file-based gates and records evidence in `roadmap/state.json`. Human gates remain explicit and cannot be auto-satisfied.
Verified human gates are recorded in `roadmap/gate-evidence.json`; generated reports under
`processed/` do not satisfy gates by themselves.

Phase 1 is a reviewed bounded local inventory. GitHub scanning remains deferred until a
fine-grained read-only token scope is separately approved.

Before more Phase 2 labels are applied, complete the Phase 1.5 scoring-discipline
checkpoint. This checkpoint exists because noisy temp fixtures, duplicated source
copies, zero-byte markers, and metadata-only observations can otherwise consume human
calibration time and make the value scorer look better than it is.

Phase 1.5 requires:

- scanner noise and quarantine behavior reviewed;
- score methodology reviewed, including instance/content classes and multiplicative
  discounts;
- a fresh clean, deduped calibration sample regenerated after those changes.

Generated samples with a missing or legacy `sample_methodology_version` are stale.
They may be kept as bug evidence, but `calibration-evidence` fails closed until the
sample uses `asset-calibration-sampling-v0.2-clean-deduped`.

Generate phase-2 calibration review reports from the current catalog without rescanning:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend calibration-reports --sample-size 25
```

This writes generated outputs only:

```text
processed/reports/scoring_calibration.md
processed/reports/orphan_review_sample.md
processed/reports/synergy_review_sample.md
processed/calibration/asset_rating_template.jsonl
processed/reports/asset_rating_calibration_summary.md
```

These reports prepare human calibration; they do not satisfy human gates or change roadmap status by themselves.

Record one structured asset score review:

```powershell
python -m digital_asset_directory.cli recommend calibration-review-label --sample-id asset-review-001 --reviewer "Human Reviewer" --score-rating about_right --notes "Looks reasonable."
```

Summarize structured asset score reviews:

```powershell
python -m digital_asset_directory.cli recommend calibration-review-summary
```

List pending or reviewed asset score reviews with generated score context:

```powershell
python -m digital_asset_directory.cli recommend calibration-review-queue --status pending --band all --limit 10
python -m digital_asset_directory.cli recommend calibration-review-queue --status reviewed --limit 10
```

Each queue item includes a deterministic `review_lens` with:

- a visible pattern key for repeated review patterns;
- current graph role and future-agent usefulness;
- up to three layers: grounded current role, latent role, and bridge role;
- high-signal candidate edges with `direct`, `derived`, or `projected` evidence levels;
- missing or combine-with suggestions;
- projected value lift, recorded as review context rather than proof of current score;
- generated current floor, conditional potential ceiling, upside gap, ceiling confidence,
  development posture, and justifications for both current score and upside;
- deterministic `current_score_range` with midpoint equal to the generated score until human
  labels support a measured error model;
- current-score-first review order plus interpretable `potential_ceiling_range` and
  `upside_delta_range` fields in score bands;
- a duplicate/variant prompt for assets that may be reinvented across repos.
- a cluster-delta prompt for close assets where one part may be better, another merely
  different, and another weaker.

For repeated patterns, apply prior label logic only after the reviewer explicitly confirms it.
Always label the current generated score before considering potential ceiling. Use upside only
for development notes, activation conditions, and future reevaluation.
For high-ceiling assets with weak current proof, prefer `validate_first` and record the
activation conditions instead of raising the current score.
For near-duplicates, variants, superseded copies, or merge candidates, preserve source
provenance and record the relationship instead of silently deleting or double-counting value.
For very close clusters, produce a candidate delta review before selecting a canonical asset.

For batch review, export and import a CSV:

```powershell
python -m digital_asset_directory.cli recommend calibration-review-export-csv
python -m digital_asset_directory.cli recommend calibration-review-import-csv --reviewer "Human Reviewer"
```

The phase-2 gate still requires at least 50 reviewed asset ratings plus false-positive,
false-negative, and weight-change notes.

After the 50 asset ratings and structured notes exist, export tracked evidence:

```powershell
python -m digital_asset_directory.cli recommend calibration-evidence
```

This writes `roadmap/evidence/phase-2-asset-calibration.md` and updates
`roadmap/gate-evidence.json`. It fails closed if review counts, structured notes, reviewers,
or the source review file are missing.

After Phase 2 labels are exported, apply the Phase 2.5 content-aware scoring
recommendation before using scores for downstream pilot selection. The governing
note is `roadmap/evidence/phase-2.5-content-aware-scoring.md`.

Run a fresh scan and score-delta validation:

```powershell
python -m digital_asset_directory.cli scan --local-only
python -m digital_asset_directory.cli recommend phase25-score-delta
```

The generated report is written to:

```text
processed/reports/phase_2_5_score_delta_validation.md
processed/reports/phase_2_5_score_delta_validation.json
```

The comparison should show that reviewed too-high workflow/template/archive
examples move down, reviewed too-low substantive code examples move up, and
about-right examples do not churn bands. Treat this as a score-methodology
evaluation, not a source-truth promotion.

Generate a downstream governance pilot selection pack without installing hooks:

```powershell
python -m digital_asset_directory.cli recommend downstream-pilots --limit 10
```

This writes `processed/reports/downstream_pilot_candidates.md`. Mock Trial repositories are
excluded from pilot recommendations while active work is in progress.

Generate planning-only readiness templates for later roadmap phases:

```powershell
python -m digital_asset_directory.cli recommend roadmap-readiness
```

This writes Phase 4 and Phase 5 readiness reports under `processed/reports/`. It does not
enable embeddings, scheduled scans, external research automation, or alert delivery.

A phase may be marked complete only when:

- required files or outputs exist;
- tracked gate evidence verifies every human gate;
- required validation commands have been run and reported;
- human gates are recorded where required;
- remaining risks are stated;
- the completion does not imply unperformed user-machine scans or production readiness.
