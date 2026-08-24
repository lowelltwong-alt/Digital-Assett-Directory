# Phase 06 — Scale, Narrow, Retire, or Re-audit

## Outcome

Convert the pilot evidence into one explicit lifecycle decision. Architecture,
effort already spent, asset count, activity volume, or stakeholder optimism
cannot substitute for the decision criteria.

## Prerequisites

- Phase 05 has accepted evidence or an accepted early-stop failure receipt.
- Every pilot case and exclusion reconciles.
- Independent checker findings and sampled human calibration are available.
- Costs, operator attention, harms, false positives, missingness, and uncertainty
  are included.

## Job

`jobs/J-600_ISSUE_SCALE_NARROW_RETIRE_DECISION.md`

## Allowed decisions

### `scale`

Use only when the P5C value gate passes. Retain the safety kernel, outcome
contract, and only successful workflow slices. Create a bounded follow-on plan
for those slices; do not reactivate all frozen features.

Required memo content:

- exact passing thresholds and cohorts;
- slice-level effects and counterevidence;
- cost and attention budget;
- owner and review/expiry date for each retained surface;
- rollback, monitoring, and revalidation triggers;
- explicit dormant/retired list.

### `narrow`

Use when one slice shows credible benefit but the whole pilot does not justify
scale. Retain the safety/provenance kernel and one proven slice. Mark the rest
dormant with pointers and review dates.

### `retire`

Use when no slice produces sufficient value, operator burden is excessive, or
guardrails fail. Preserve raw evidence, provenance, validated fixes, and
tombstones. Retirement execution is a separate human-approved campaign; this
decision does not delete anything.

### `re-audit`

Use only when evidence is invalid or materially incomplete—such as corrupted
joins, changed cohorts, evaluator compromise, or unavailable outcome sources.
Disappointing valid results do not justify re-audit. The memo must identify the
minimum evidence repair and why it could change the decision.

## Decision method

1. Verify case reconciliation and methodology revision.
2. Compare frozen baseline and candidate metrics overall and per slice.
3. Present positive evidence, counterevidence, harms, missingness, bias, cost,
   and operator burden side by side.
4. Apply P5 thresholds without post-hoc changes.
5. Run an independent premortem for each plausible decision.
6. Select one allowed decision and state why the others were rejected.
7. Define retained, dormant, superseded, and proposed-retired components.
8. Give each retained component an owner, evidence revision, review date,
   revalidation triggers, and rollback.
9. Give every superseded component a lifecycle-registry pointer/tombstone plan.
10. Obtain Lowell's signed decision receipt.

## Required decision packet

- machine-readable decision JSON;
- human-readable decision memo;
- baseline/candidate metric table and distributions;
- slice-level and repository-level results;
- safety/privacy/defect/attention guardrails;
- cost and elapsed-time accounting;
- excluded/unknown data and sensitivity analysis;
- independent checker report and disagreements;
- component disposition map;
- follow-on boundary and explicit non-authority statement;
- signed human decision receipt.

## Acceptance

- One and only one allowed decision is selected.
- The decision follows the frozen thresholds or clearly states a human exception;
  an exception cannot be represented as measured success.
- Every retained component has owner, current evidence, expiry/review date,
  rollback, and revalidation triggers.
- Every non-retained component has `dormant`, `superseded`, or
  `proposed_retirement` treatment with a pointer.
- Raw evidence is preserved.
- No deletion, cleanup, publish, merge, deployment, downstream mutation, or
  recurring activation occurs as part of the decision job.
- DAD postflight and exact workspace disposition are recorded.

## Campaign completion

The campaign completes on the signed decision, even when the decision is
`narrow` or `retire`. Any implementation of scale, consolidation, or retirement
starts with a new exact scope and human-approved manifest revision.

