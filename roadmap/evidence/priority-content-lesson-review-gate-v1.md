# Priority Content Lesson Review Gate V1

## Summary

Implemented a structured human-review gate for generated priority-content lesson
candidates. The gate creates review templates, queue views, label updates, and
summaries without promoting any lesson candidate into a deterministic learning
rule.

## Commands

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-template --sample-size 100
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-queue --status pending --limit 10
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-label --sample-id <id> --reviewer Lowell ...
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-summary
```

## Contract

Added `PriorityContentLessonReviewRecord` and
`schemas/priority-content-lesson-review.schema.json`.

Review labels cover:

- applicability;
- usefulness;
- safety;
- actionability;
- decision;
- false-positive notes;
- missing-context notes;
- useful-example notes;
- promotion-blocker notes.

## Authority Boundary

Review records are labels for generated candidates only. They do not promote
lessons to deterministic learning rules, preflight defaults, source truth, or
roadmap completion.

## Risk Tier

Medium.

Reason: this creates the gate future agents will use before lesson promotion.
The implementation is generated-output and review-label only; it does not read
source repos, mutate downstream repos, or promote rules.

## Applies When

- Generated priority-content lesson candidates exist.
- Lowell or another human reviewer is deciding whether a candidate is useful,
  safe, actionable, and context-valid.
- A future agent needs evidence before proposing lesson promotion.

## Does Not Apply When

- No generated lesson candidates exist.
- The task is raw observation, content extraction, or direct repo inspection.
- A lesson should be promoted automatically. That remains forbidden.

## Danger If Misapplied

- Accepted review-use examples can be mistaken for deterministic learning rules.
- Labels without notes can hide false positives or missing context.
- One reviewer's acceptance can be overgeneralized outside the candidate's
  `applies_when` and `does_not_apply_when`.

## Red-Team

- Promotion risk: summary always reports `promotion_gate_complete=false`.
- Context loss: review evidence carries candidate applicability,
  non-applicability, danger, source events, and context tags.
- Bad labels: Pydantic/schema validation rejects unsupported label values.
- Silent mutation: commands only rewrite generated review JSONL under
  `processed/`.

## Premortem

Failure mode: a future agent sees `accept_for_review_use` and treats it as
approval to add a learning rule.

Guard: docs, evidence, and summary state that promotion is a separate future
human gate.

Failure mode: review labels are applied to the wrong candidate.

Guard: commands support `sample_id` or `lesson_candidate_id`, reject missing
matches, and prefer sample IDs for ambiguity.

Failure mode: review queue becomes stale after new lesson candidates are
generated.

Guard: review templates are generated outputs and can be regenerated from the
current candidate file.

## Validation

Focused tests cover:

- schema conformance;
- review template creation;
- pending/reviewed queue behavior;
- label updates;
- summary counts;
- no promotion gate completion from review labels.

## Acceptance Status

Implemented as a generated review gate. Lesson promotion remains unimplemented
and intentionally blocked pending a separate human-approved design.
