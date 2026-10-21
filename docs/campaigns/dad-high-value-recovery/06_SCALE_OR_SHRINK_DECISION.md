# Phase 06 — Scale, Narrow, Retire, or Re-audit

## Outcome

Convert the pilot evidence into one explicit lifecycle decision. Architecture,
effort already spent, asset count, activity volume, or stakeholder optimism
cannot substitute for the decision criteria.

## Prerequisites

- Exactly one revision-7 terminal route is accepted and binds J-600 to its
  selected predecessor only.
- The selected predecessor receipt binds its result, state, coverage, trigger
  class, producer-attempt digest, passing checker-record digest, and complete
  cohort-closure digest.
- An independently accepted navigation receipt binds the route ID, predecessor,
  closure, permitted decisions, pre-J-600 projection digest/stage/exact paths,
  and projected J-600 packet.
- Every started, unstarted, withdrawn, and excluded pilot slot reconciles.
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

## Route-to-decision matrix

| Route | Exact predecessor condition | Permitted decisions |
|---|---|---|
| `p5c-pass` | J-530 `pass/complete/complete` with accepted closure | `scale`, `narrow`, `retire`, `re-audit` |
| `p5a-valid-terminal` | J-510 `fail_terminal/failed/complete` from confirmed privacy, source-authority, harmful, or material-safety evidence | `narrow`, `retire` |
| `p5a-inconclusive` | J-510 `inconclusive` or `blocked_human`, `partial` or `coverage_unavailable`, accepted closure | `re-audit` |
| `p5b-valid-terminal` | J-520 `fail_terminal/failed/complete` from frozen benefit failure or safety/authority evidence | `narrow`, `retire` |
| `p5b-inconclusive` | J-520 inconclusive or blocked, `partial` or `coverage_unavailable`, accepted closure | `re-audit` |
| `p5c-valid-terminal` | J-530 `fail_terminal/failed/complete` | `narrow`, `retire` |
| `p5c-inconclusive` | J-530 inconclusive or blocked, `partial` or `coverage_unavailable`, accepted closure | `re-audit` |

Missing, stale, malformed, unjoinable, metric-corrupt, or checker-integrity
evidence is never a valid terminal failure and permits only `re-audit`. No route
exists without complete control-plane closure.

## Decision method

1. Verify the selected route, single predecessor dependency, closure,
   navigation receipt, case reconciliation, and methodology revision.
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
11. Request a separate final-navigation packet; do not perform navigation in
    the J-600 producer lease.

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
- selected route ID, predecessor receipt digest, result/state/coverage, trigger
  class, closure digest, navigation receipt digest, and permitted-decision set.

## Acceptance

- One and only one allowed decision is selected.
- The decision belongs to the selected route's permitted-decision set, and the
  J-600 packet/checkpoint/receipt depend on only that predecessor.
- The decision follows the frozen thresholds or clearly states a human exception;
  an exception cannot be represented as measured success.
- Every retained component has owner, current evidence, expiry/review date,
  rollback, and revalidation triggers.
- Every non-retained component has `dormant`, `superseded`, or
  `proposed_retirement` treatment with a pointer.
- Raw evidence is preserved.
- No deletion, cleanup, publish, merge, deployment, downstream mutation, or
  recurring activation occurs as part of the decision job.
- J-600 does not edit `07_EVIDENCE_INDEX.md`, `handoff.md`,
  `08_SUPERSESSION_AND_ARCHIVE_MAP.md`, or navigation evidence. A separately
  leased `campaign-navigation-writer` and distinct `independent-checker` own
  that metadata transition. Final navigation produces a separate immutable
  `{route_id}-post-j600.json` receipt bound to the signed J-600 receipt,
  post-J-600 projection digest, stage, and exact 07/handoff/08 paths; it cannot
  reuse or overwrite the pre-J-600 `{route_id}.json` receipt;
  `08` remains unavailable until the decision is signed.
- DAD postflight and exact workspace disposition are recorded.

## Campaign completion

The campaign completes on the signed decision and accepted final-navigation
receipt, even when the decision is `narrow` or `retire`. Any implementation of
scale, consolidation, or retirement starts with a new exact scope and
human-approved manifest revision.
