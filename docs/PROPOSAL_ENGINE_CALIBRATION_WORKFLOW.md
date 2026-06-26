# Proposal Engine Calibration Workflow

Status: operational workflow for generated candidate proposals

This workflow supports the dual proposal engines:

- bottom-up self-proposal;
- top-down orchestration.

It does not authorize source-repository mutation, automatic promotion, roadmap completion, or external code reuse.

## Authority Boundary

Proposal outputs are generated candidates. Human labels are calibration evidence. Neither one is source-repository truth.

Keep these boundaries:

- Generated proposal JSONL and reports stay under ignored `processed/` paths.
- Review labels may be entered into a generated review JSONL file or a copied curated review file.
- Tracked roadmap evidence may be written only after at least 25 reviewed records from each engine exist.
- Roadmap phase status must not change unless the relevant acceptance evidence exists.
- GitHub scanning remains deferred unless a fine-grained read-only token scope is separately approved.

## Generate A Gate-Ready Review Set

Run both engines against the current catalog and create a 25-per-engine review template:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend proposals --engine both --per-asset-limit 3 --portfolio-limit 25 --review-sample 25
```

Expected generated outputs:

```text
processed/proposals/bottom_up_proposals.jsonl
processed/proposals/top_down_proposals.jsonl
processed/proposals/proposal_review_template.jsonl
processed/reports/proposal_engine_comparison.md
processed/reports/proposal_review_sample.md
processed/reports/proposal_calibration_summary.md
```

The review template should contain 50 records: 25 bottom-up and 25 top-down. If `calibration_gate_ready` is false, raise `--portfolio-limit` or inspect why one engine produced too few proposals.

## Review Queue

List the next pending proposals with their context:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend proposal-review-queue --status pending --engine all --limit 5
```

Useful filters:

```powershell
python -m digital_asset_directory.cli recommend proposal-review-queue --status pending --engine bottom-up --limit 5
python -m digital_asset_directory.cli recommend proposal-review-queue --status pending --engine top-down --limit 5
python -m digital_asset_directory.cli recommend proposal-review-queue --status reviewed --engine all --limit 10
```

Use queue output to inspect:

- `sample_id`;
- `proposal_id`;
- `proposal_engine`;
- `proposal_type`;
- source and target asset IDs;
- source and target asset context, including title, path, asset type, lifecycle, freshness, and confidence;
- needs;
- rationale;
- smallest bounded experiment;
- confidence and risk.

## Batch Review CSV

For spreadsheet-style review, export the review set and proposal context to CSV:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend proposal-review-export-csv
```

Expected generated output:

```text
processed/proposals/proposal_review_batch.csv
processed/proposals/proposal_review_unblind_map.csv
```

The batch CSV hides `proposal_engine` by default to reduce bottom-up/top-down review bias.
Use the unblind map only after first-pass scoring, or pass `--include-engine` when an
unblinded operational export is more useful than blinded calibration.

The CSV includes compact source and target asset context so reviewers can inspect titles,
paths, types, lifecycle state, freshness, and confidence without unblinding the engine label.

Editable label columns:

```text
reviewer
usefulness
safety
novelty
actionability
decision
notes
false_positive_reason
false_negative_note
useful_example_note
```

Do not edit proposal context columns to change proposal meaning. The importer uses the IDs and validated label columns; generated proposal evidence remains candidate-only.

After editing the CSV, import labels back into the review JSONL:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend proposal-review-import-csv --reviewer "Human Reviewer"
```

The import fails closed on invalid labels or unmatched review records. It does not write roadmap evidence.

## Label A Review Record

Update one record at a time:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend proposal-review-label --sample-id review-001 --reviewer "Human Reviewer" --usefulness useful --safety safe --novelty novel --actionability actionable --decision accept_candidate --notes "Useful and safe bounded candidate." --useful-example-note "Clear bounded reuse example."
```

Allowed values:

```text
usefulness: unreviewed, useful, not_useful, unsure
safety: unreviewed, safe, unsafe, needs_more_review
novelty: unreviewed, novel, already_known, unsure
actionability: unreviewed, actionable, not_actionable, unsure
decision: pending, accept_candidate, reject_candidate, defer
```

Label semantics:

- `accept_candidate` means the proposal is worth a bounded experiment or review action. It does not authorize source mutation, graph promotion, external code import, or roadmap completion.
- `actionable` means the next review step can be taken now without an unresolved boundary dependency. Use `not_actionable` when the proposal is useful but blocked by active-repo, source-authority, license, privacy, or owner-review gates.
- `safety=needs_more_review` should be used when the proposal touches an active or explicitly excluded repo, suggests external code/research, implies source changes, or crosses an authority boundary that has not been reviewed.
- Generated `deterministic_review_guards` in proposal evidence are suggestions for the human reviewer, not labels. They must not count as human review until a reviewer records labels.

Use the structured calibration note fields to capture:

- `false_positive_reason`: why a generated proposal looked wrong, unsafe, duplicate, or not useful.
- `false_negative_note`: what better proposal, missing connection, or missed need the engine failed to surface.
- `useful_example_note`: why a proposal is worth keeping as a representative positive example.

A label command rewrites only the selected review JSONL file. It does not change proposal records, graph edges, source files, roadmap state, or source repositories.

## Summarize Review Progress

After labeling records, summarize current progress:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend proposal-review-summary
```

Expected generated output:

```text
processed/reports/proposal_review_results_summary.md
```

This summary reports reviewed counts, label counts, structured calibration note counts, and whether the calibration gate is complete. It is generated output and should not be treated as tracked roadmap evidence by itself.

## Distinct-Idea Sampling And Bundles

Proposal comparison reports count both raw records and distinct proposal ideas. Distinct idea keys are deterministic candidate metadata derived from proposal type, relationship, collection, need/capability context, and source/target assets. Use distinct idea counts when comparing engines; raw proposal counts can be inflated by repeated item-level records.

Top-down stale/risk review should prefer collection-level bundles over repeated item-level stale proposals. A stale bundle is grouped by collection and asset type and carries member asset IDs plus alert IDs. Accepting a bundle means "review this collection-level decision path," not "act on every member without review."

Bottom-up proposals are same-repo or same-family by default. Cross-repo bottom-up proposals require stronger evidence than lexical overlap, such as a shared need/capability, existing graph evidence, same content identity, or shared outcome plus calibrated similarity. Cross-repo lexical-only matches should be treated as false-positive-prone review noise.

## Export Tracked Evidence

After at least 25 bottom-up and 25 top-down records have human labels, and after structured
false-positive, false-negative, and useful-example notes are captured, export tracked-ready
roadmap evidence with an explicit human default-path decision:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend proposal-calibration-evidence --default-path hybrid --default-rationale "Human review found complementary strengths; use hybrid as the default until a later calibration cycle changes it."
```

Expected tracked-ready output:

```text
roadmap/evidence/proposal-engine-calibration.md
```

This command fails closed if the review gate is incomplete, if structured calibration notes are missing, or if `--default-path` / `--default-rationale` are omitted. It should not create roadmap evidence from unreviewed generated templates. The evidence includes false positive notes, false negative notes, useful examples, the candidate default from accepted counts, and the explicit human-selected default path.

When distinct proposal idea keys are available, use the distinct accepted idea counts as the candidate default signal. Raw accepted counts are still reported for traceability, but they should not be used alone to conclude that one engine outperformed another.

After evidence export, review the evidence file before committing it. Do not mark any roadmap phase complete unless its acceptance criteria are otherwise satisfied.

## Validation

Run the baseline after any implementation or evidence work:

```powershell
python -m pytest
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
```

## Stop Conditions

Stop and report if:

- review records cannot be traced to proposal IDs;
- a generated proposal implies authority over a source repository;
- a label file contains invented or unclear human labels;
- evidence export succeeds before 25 reviewed records from each engine exist;
- a roadmap phase would be marked complete without acceptance evidence;
- any command would mutate scanned source files;
- validation fails.
