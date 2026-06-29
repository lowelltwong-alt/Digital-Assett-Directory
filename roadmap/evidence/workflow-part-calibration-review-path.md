# Workflow Part Calibration Review Path

Date: 2026-06-29

Status: review path implemented; calibration labels pending.

## Scope

This evidence records the narrow completion of the next step after
`WorkflowPartRecord` Phase A: a deterministic, stratified review path for
workflow-part candidates.

The review path is local-only and candidate-only. It reads generated
workflow-part candidates from `processed/learning/workflow_parts.jsonl` and
writes generated review artifacts under `processed/`. It does not rescan, call
GitHub, call models, mutate scanned source repositories, alter current value
scores, mark roadmap phases complete, or surface workflow parts as mandatory
preflight guidance.

## Added Review Contract

- Added `WorkflowPartReviewRecord`.
- Added `schemas/workflow-part-review.schema.json`.
- Registered `workflow_part_review` in `registry/schema-registry.json`.

Review labels:

- `usefulness`: `useful`, `not_useful`, `unsure`.
- `safety`: `safe`, `unsafe`, `needs_more_review`.
- `specificity`: `right_level`, `too_broad`, `too_narrow`, `unsure`.
- `dataflow_completeness`: `adequate_for_now`, `missing_inputs`,
  `missing_outputs`, `missing_side_effects`, `not_applicable`, `unsure`.
- `decision`: `accept_for_review_use`, `reject_candidate`, `defer`,
  `needs_human_gate`.

All labels default to unreviewed or pending. Human labels are required before
the review records become calibration evidence.

## Added Commands

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-part-review-template --sample-size 50
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-part-review-queue --status pending --limit 10
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-part-review-label --sample-id <id> --reviewer Lowell ...
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-part-review-summary
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-part-calibration-evidence
```

`workflow-part-calibration-evidence` fails closed until:

- the review template has enough reviewed records;
- at least one false-positive note exists;
- at least one false-negative note exists;
- at least one useful-example note exists;
- at least one missing-dataflow note exists;
- at least one candidate is accepted for review use.

## Generated Outputs

The review-template command writes:

- `processed/workflow_parts/workflow_part_review_template.jsonl`
- `processed/reports/workflow_part_calibration_review_sample.md`
- `processed/reports/workflow_part_review_results_summary.md`

These are generated outputs and should not be tracked as truth.

## Real-Catalog Smoke Result

Input candidate count: 8177 workflow parts.

Generated review template: 50 records.

The sample is stratified across all 15 workflow-part types:

- `boundary_map`: 4
- `calibration_gate`: 4
- `capability_provider`: 4
- `contract`: 4
- `decision_record`: 4
- `eval_gold`: 3
- `gate`: 3
- `human_gate`: 3
- `learning_signal`: 3
- `lesson_part`: 3
- `orchestrator`: 3
- `prompt_part`: 3
- `quarantine_gate`: 3
- `runner`: 3
- `validator`: 3

The first pending queue batch returns 10 records, each with candidate context,
representative paths, path-class counts, applicability, non-applicability,
danger-if-misapplied, context tags, and dataflow-inference status.

The evidence export was intentionally tested before labels and failed closed
with:

```text
Workflow part calibration evidence requires reviewed records, structured notes,
and at least one accepted review-use candidate.
```

## Red-Team And Premortem

Risk: first labels overfit one sorted part type.
Mitigation: use stratified sampling across part types and pattern diversity.

Risk: temp fixtures or copied variants inflate usefulness.
Mitigation: preflight/midflight acknowledged temp-copy and semantic-evolution
rules; candidate context carries path-class and family-key evidence.

Risk: reviewers treat generated parts as permission to compose workflows.
Mitigation: decisions are `accept_for_review_use`, not "promote" or "install";
evidence export explicitly excludes preflight, scoring, and assembly effects.

Risk: empty dataflow fields hide an important missing dependency.
Mitigation: review labels include `dataflow_completeness` and a required
missing-dataflow note for calibration evidence.

Risk: future agents bypass the generated review template and label old
first-50 samples.
Mitigation: AI front door, TOC, manifest, data dictionary, and radar docs now
point to the stratified calibration sample.

## Validation Evidence

Focused validation:

```powershell
python -m pytest tests\test_workflow_parts.py tests\test_schema_conformance.py -q
# passed

python -m ruff check src\digital_asset_directory\workflow_parts.py src\digital_asset_directory\models.py src\digital_asset_directory\cli.py tests\test_workflow_parts.py tests\test_schema_conformance.py
# All checks passed
```

Full validation after this evidence file was added:

```powershell
python -m pytest
# 180 passed

python -m ruff check src tests scripts noxfile.py
# All checks passed

$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
# valid=true, checked_count=68, errors=[]

$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
# exited 0
```

## Reusable Lesson

When a generated recognizer creates many candidates, the first review sample
must be stratified by the decision-relevant candidate class before human labels
are collected. Otherwise calibration labels can validate sorting artifacts
instead of recognizer quality.

## Acceptance

Accepted:

- Review-record contract.
- Stratified generated review template.
- Queue, label, summary, and fail-closed evidence commands.
- Navigation and documentation rows that route agents to the stratified sample.

Not accepted yet:

- Workflow parts influencing current scores.
- Workflow parts surfacing as mandatory preflight guidance.
- Workflow assembly packs.
- Any roadmap completion claim based on workflow-part calibration.

Next action: review the 50 workflow-part records in batches and apply only
human-approved labels.
