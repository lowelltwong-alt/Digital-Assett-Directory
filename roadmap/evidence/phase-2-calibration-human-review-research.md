# Phase 2 Calibration Human Review Research

Status: human-authorized calibration research and review rationale. This file
explains the labels imported into
`processed/calibration/asset_rating_template.jsonl` and the tracked evidence in
`roadmap/evidence/phase-2-asset-calibration.md`.

Date: 2026-06-25

Reviewer context: Lowell asked Codex to perform the Phase 2 human review. Codex
applied the reviewed rules surfaced by preflight:

- `learning-rule:calculated-score-requires-methodology`
- `learning-rule:current-score-before-upside`
- `learning-rule:temp-fixture-copy-is-lineage-evidence`

Methodology references:

- current score methodology: `asset-value-v0.2-red-team-discipline`
- clean sample methodology: `asset-calibration-sampling-v0.2-clean-deduped`
- governing document: `docs/ASSET_VALUE_MODEL.md`

## Scope

The review labeled all 100 records in the clean calibration sample:

- reviewed records: `100`
- `about_right`: `54`
- `too_high`: `18`
- `too_low`: `28`
- false-positive notes: `18`
- false-negative notes: `28`
- weight-change notes: `100`

The compact full label table is tracked at
`roadmap/evidence/phase-2-calibration-label-table.csv`.

The review did not mutate scanned source repositories and did not treat
generated scores as truth. Labels calibrate this hub's scoring behavior only.

## Review Method

Review order was current-score first:

1. Read the generated score, band, asset type, instance class, and information
   content class.
2. Inspect source path, local file existence, line count, and byte count for all
   100 records.
3. Read representative files from both bands:
   - validation workflow examples;
   - governance workflow examples;
   - intake budget code;
   - exception-lake event ingestion code.
4. Assign `score_rating`.
5. Add false-positive, false-negative, and weight-change notes.

The decisive evidence was not future upside. It was whether the current score
was supported by direct current evidence.

## Main Finding

Phase 1.5 fixed the old temp-fixture flood, but this clean sample exposed a new
calibration problem: the sample is still too content-blind.

Every reviewed record was `metadata_only`. Many rows also had
`score_methodology_version=null` in the generated evidence, even though the
sample methodology was current. That means the sample is clean enough to label,
but it is not yet rich enough for a reliable score formula.

The label pattern was clear:

- some real workflows deserve `medium`;
- short archive/template/pinned workflow wrappers should not reach `medium`;
- substantial source code modules should not remain `low` merely because the
  catalog did not extract or use code content.

## Label Policy

### Too High

Medium workflow scores were marked `too_high` when the asset was an archive,
template, pinned CI copy, duplicated workflow wrapper, or low-information
metadata-only item without enough direct content or usage evidence.

Examples:

- `asset-review-003` `bug_report`
- `asset-review-005` `documentation_request`
- `asset-review-012` `CODEOWNERS`
- `asset-review-016` `workflow_escalation_example`
- `asset-review-018` `main-canonical-ruleset`
- `asset-review-023` `repo-drift-check`
- `asset-review-028` `validate-external-alignment`
- `asset-review-030` `pull_request_template`
- `asset-review-031` `validate-talent-intelligence-extension`
- `asset-review-032` `phase5-validate-object-sets`
- `asset-review-035` `pull_request_template`
- `asset-review-037` `concept_proposal`
- `asset-review-038` `validate-spine`
- `asset-review-040` `documentation_request`
- `asset-review-043` `check-ids`
- `asset-review-044` `workflow_atlas`
- `asset-review-045` `WORKFLOW_ATLAS_BOUNDARY`
- `asset-review-048` `validate-address`

Calibration lesson: freshness, provenance, and workflow/type labels should not
carry an archive/template/pinned or metadata-only wrapper into `medium` without
content, execution, usage, or canonical-source evidence.

### Too Low

Low code scores were marked `too_low` when local inspection showed substantial
readable implementation code rather than a marker or thin helper. These are
false negatives caused by content-blind scoring.

Examples:

- `asset-review-051` `cli`
- `asset-review-052` `grounding`
- `asset-review-054` `contract_loader`
- `asset-review-057` `evidence_packet_admission`
- `asset-review-060` `admission_validator`
- `asset-review-061` `validation_gateway`
- `asset-review-062` `defect_generator`
- `asset-review-074` `evidence`
- `asset-review-079` `update_contract_lock`
- `asset-review-081` `api`
- `asset-review-082` `budget_draft_generator`
- `asset-review-090` `budget_template_rows`
- `asset-review-091` `budget`
- `asset-review-093` `workers`
- `asset-review-096` `insurance_budget_poc`
- `asset-review-097` `substrate_mutation_guard`
- `asset-review-100` `event_ingestion`

Calibration lesson: readable source code needs direct content features, module
role features, and test/runtime-position evidence. A substantial source module
should not score like a tiny marker because the scan stored only metadata.

### About Right

Records were marked `about_right` when:

- a source workflow or governance artifact had enough direct path/file evidence
  to justify `medium`, but not enough for a higher band; or
- a low-scored code file was a marker, thin helper, tiny wrapper, simple store,
  or small support module.

Calibration lesson: the current bands are not useless. The problem is that
metadata-only scoring compresses too many different assets into the same band.

## Score Changes Recommended

The next scoring iteration should:

1. Reject or warn on calibration samples where most records are
   `metadata_only`.
2. Record content extraction coverage in the calibration summary.
3. Use readable code content, line count, module role, imports, public API
   surface, tests, and package position as scoring features.
4. Split workflow scoring into:
   - executable validation workflow;
   - governance workflow document;
   - issue or pull-request template;
   - archive or pinned copy;
   - registry/config wrapper.
5. Reduce the ability of freshness and provenance alone to create a medium
   score.
6. Keep archive and pinned-copy assets as lineage evidence unless direct current
   value is reviewed.
7. Preserve current-score-before-upside review order in future calibration
   queues.

## Gate Result

Phase 2 calibration gates are now satisfied:

- `phase-2-asset-ratings-reviewed`
- `phase-2-false-positive-negative-notes-captured`
- `phase-2-weight-changes-documented`

The roadmap checker should compute Phase 2 as `complete` once the tracked
evidence and local generated outputs are present.

## Remaining Risks

- Labels are based on the current clean sample, not a broad unbounded scan.
- Generated outputs under `processed/` remain local and regenerable.
- A full local scan previously timed out and still needs performance work.
- The next score implementation should be evaluated against these labels before
  using scores for proposal generation, downstream governance, or scheduled
  alerts.

## Reusable Lesson

Clean sampling removes noise, but it does not guarantee useful calibration.
Calibration also needs enough direct content evidence inside the sample. A clean
metadata-only sample can still reveal scorer defects, but the fix is to improve
content-aware scoring before broad downstream use.
