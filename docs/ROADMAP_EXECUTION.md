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
