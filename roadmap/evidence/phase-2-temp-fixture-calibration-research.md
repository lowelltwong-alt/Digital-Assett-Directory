# Phase 2 Temp Fixture Calibration Research

Status: candidate calibration research and reviewer aid only. This file does not
complete Phase 2, apply labels, change scores, or promote generated evidence to truth.

Recorded on: 2026-06-25

## Purpose

Phase 2 asset calibration exposed a repeated pattern: pytest-created contract
repository copies were scored like independent reusable schema assets. The
specific copied files often have high path/type signals, but the copied instance
usually has weak current value when a canonical/source schema exists elsewhere.

This note preserves the research behind the current recommendation so future
agents and Claude Code can review the same evidence instead of rediscovering it.

## Context Boundaries

Applies when:

- an asset review sample points into `.pytest-tmp-root`, `test_*`, copied
  `contract-repo`, temp worktree, archive, or generated fixture paths;
- same-basename, same-hash, chunk, normalized JSON, or source-path evidence
  points to canonical/source variants nearby;
- the review question is the current score of the copied instance.

Does not apply when:

- the fixture copy is the only available source of truth;
- the review is explicitly measuring fixture coverage rather than independent
  asset value;
- a reviewed delta proves the copied fixture has meaningful unique content or a
  deliberate test-only role that should be scored as its own asset.

Danger if misapplied:

- treating every fixture copy as high-value floods the graph with false
  high-value assets;
- discarding fixture copies erases lineage, coverage, version-drift, and
  semantic-evolution evidence that may be valuable at the family level.

## Research Method

The review used the existing DAD scoring lens:

1. Judge current score first, before upside or ceiling.
2. Classify path authority: canonical/source, temp fixture, worktree, archive,
   generated, or unknown.
3. Check duplicate and same-basename families.
4. Compare fixture copy to canonical/source candidates by bytes and, where
   needed, normalized JSON structure.
5. Preserve semantic-evolution and lineage evidence at family level even when
   the individual copied instance is over-scored.

Relevant learning rules:

- `learning-rule:current-score-before-upside`
- `learning-rule:temp-fixture-copy-is-lineage-evidence`
- `learning-rule:context-bound-lessons-need-non-applicability`

## Runtime Fixture Pattern

The inspected pytest fixture `contract_repo_copy` copies `registry`, `schemas`,
`governance`, and `docs` from a canonical/source contract repository into a temp
`contract-repo`, then initializes git for runtime safety tests.

Observed fixture definitions:

- `C:\Users\lowel\OneDrive\Desktop\Git Projects\lawfirm-skills-merge-workspace\repos\LawFirm-os-exceptions-lake-runtime\tests\conftest.py`
- `C:\Users\lowel\OneDrive\Desktop\Git Projects\00_LawFirm_OS\LawFirm-os-exceptions-lake-runtime-main\tests\conftest.py`

Representative tests using the copied contract repo:

- `test_runtime_data_path_nested_inside_contract_repo_is_rejected`
- `test_rejects_direct_mutation_attempts`
- `test_cli_rejects_production_or_live_connector_flags`
- `test_rejects_unknown_event_class`
- `test_falls_back_when_export_manifest_absent`
- `test_fails_closed_when_export_manifest_*`
- `test_fails_closed_when_lock_missing_required_field`
- `test_cli_list_events_returns_stored_events`

Interpretation: the copied schemas are useful lineage and safety-harness
evidence. The independent value usually belongs to the canonical schema, the
schema family, or the runtime harness, not to each temp copy.

## Current Review State

At the time this note was recorded:

- 3 of 50 asset reviews were reviewed.
- `asset-review-001` was labeled `too_high` by human-approved application.
- First-batch pending examples below remain recommendations only until the human
  approves labels.

## Remaining First-Batch Recommendations

| sample_id | asset | reviewed target path cue | current-score recommendation | research basis | family-level value to preserve |
| --- | --- | --- | --- | --- | --- |
| `asset-review-002` | `external_identifier.schema` | `.pytest-tmp-root/.../contract-repo/schemas/extensions/talent_intelligence/external_identifier.schema.json` | `too_high` for copied instance | 108 same-basename files; about 99 temp copies and 9 canonical/source-like paths; target matches chosen canonical byte-for-byte. | Semantic-evolution report showed `breaking_semantic` with `mixed_signal`; preserve as family review priority, not temp-copy score proof. |
| `asset-review-003` | `frontier-review-record.schema` | `.pytest-tmp-root/.../test_rejects_direct_mutation_a0/contract-repo/schemas/harness/frontier-review-record.schema.json` | `too_high` for copied instance | 103 same-basename files; about 99 temp copies and 4 canonical/source-like paths; target matches canonical byte-for-byte. | Evidence of harness contract reuse and mutation-boundary tests. |
| `asset-review-005` | `frontier-review-record.schema` | `.pytest-tmp-root/.../test_cli_list_events_returns_s0/contract-repo/schemas/harness/frontier-review-record.schema.json` | `too_high` for copied instance | Same canonical family as `asset-review-003`; target matches canonical byte-for-byte. | Evidence that event-listing tests reuse the same harness contract. |
| `asset-review-007` | `span-selector.schema` | `.pytest-tmp-root/.../test_cli_rejects_production_or0/contract-repo/schemas/span-selector.schema.json` | `too_high` for copied instance | 105 same-basename files; about 99 temp copies and 6 canonical/source-like paths; target matches chosen canonical byte-for-byte. | Evidence of span-selector contract availability inside safety tests. |
| `asset-review-008` | `evaluation-run.schema` | `.pytest-tmp-root/.../test_rejects_unknown_event_cla0/contract-repo/schemas/evaluation-run.schema.json` | `too_high` for copied instance | 105 same-basename files; about 99 temp copies and 6 canonical/source-like paths; target matches chosen canonical byte-for-byte. | Evidence of evaluation-run contract propagation into runtime tests. |
| `asset-review-009` | `embedding-set.schema` | `.pytest-tmp-root/.../test_fails_closed_when_export_0/contract-repo/schemas/embedding-set.schema.json` | `too_high` for copied instance | 105 same-basename files; about 99 temp copies and 6 canonical/source-like paths; target matches chosen canonical byte-for-byte. | Evidence of export-manifest fail-closed coverage. |
| `asset-review-010` | `skill-gap-detection.schema` | `main-clean-20260616/.../.pytest-tmp-root/.../contract-repo/schemas/skill-gap-detection.schema.json` | `too_high` for copied instance | 54 same-basename files; about 50 temp copies, 3 canonical/source-like paths, and 1 archive path. Target differs by bytes, but required fields/properties match canonical; observed diff looked like formatting/line-ending or metadata churn, not structural semantic change. | Preserve as possible weak variant/delta evidence; do not inflate copied-instance current score without reviewed unique behavior. |
| `asset-review-011` | `claim_v3.schema` | `.pytest-tmp-root/.../test_fails_closed_when_export_1/contract-repo/schemas/claim_v3.schema.json` | `too_high` for copied instance | 105 same-basename files; about 99 temp copies and 6 canonical/source-like paths; target matches chosen canonical byte-for-byte. | Evidence that claim schema participates in export-manifest fail-closed tests. |
| `asset-review-012` | `legal-document-span-ref.schema` | `.pytest-tmp-root/.../test_fails_closed_when_lock_mi0/contract-repo/schemas/legal-document-span-ref.schema.json` | `too_high` for copied instance | 53 same-basename files; about 50 temp copies and 3 canonical/source-like paths; target matches chosen canonical byte-for-byte. | Evidence of lock-file validation coverage and legal span reference schema propagation. |

## Scoring Implication

Recommended scoring correction for future calibration:

- discount empty structural marker files and temp fixture copies when evidence is
  path-only, type-only, or copied-instance-only;
- route schema family value to the canonical/source schema or composite workflow
  asset when that family has reviewed semantic evolution, tests, or downstream
  usage;
- keep fixture copy counts, hashes, normalized diffs, and test-path lineage as
  graph evidence;
- require reviewed unique behavior before a copied fixture receives a high
  current score as an independent asset.

## Claude Second Opinion Location

Claude Code should put independent findings in:

`roadmap/evidence/phase-2-claude-second-opinion.md`

Claude should add findings as dated sections and should not edit
`processed/calibration/asset_rating_template.jsonl` or apply labels unless the
human explicitly asks it to do so.

## Open Review Questions

- Should all pending first-batch copied schema fixture instances be labeled
  `too_high`, or should any be `unsure` because their fixture role is itself the
  asset under review?
- Should scoring add a direct temp-fixture discount factor, or should it route
  copied instances into a separate lineage/coverage review queue?
- Should family-level semantic evolution increase the canonical family score,
  the composite workflow score, or only review priority until more labels exist?
