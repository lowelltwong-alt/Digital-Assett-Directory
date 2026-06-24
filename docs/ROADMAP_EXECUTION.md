# Roadmap Execution

Run:

```text
asset-dir roadmap check
```

The checker computes file-based gates and records evidence in `roadmap/state.json`. Human gates remain explicit and cannot be auto-satisfied.

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

For batch review, export and import a CSV:

```powershell
python -m digital_asset_directory.cli recommend calibration-review-export-csv
python -m digital_asset_directory.cli recommend calibration-review-import-csv --reviewer "Human Reviewer"
```

The phase-2 gate still requires at least 50 reviewed asset ratings plus false-positive,
false-negative, and weight-change notes.

A phase may be marked complete only when:

- required files or outputs exist;
- required validation commands have been run and reported;
- human gates are recorded where required;
- remaining risks are stated;
- the completion does not imply unperformed user-machine scans or production readiness.
