# J-510 — Run the 10-Task Shadow Calibration

## Contract

- Phase: P5A
- Depends on: accepted J-500 receipt
- Owner: `pilot-producer`
- Checker: `independent-checker`
- Lease: one case at a time; 90 minutes maximum per case
- Attempts: one governed task attempt plus its normal approved repair policy;
  campaign-envelope repair limit one
- Idempotency key: `dad-high-value-recovery-v1:J-510:<case-id>:r1`
- Auto-advance: no; P5A human review

## Goal

Complete 10 real cases to prove envelope closure and metric reliability, without
claiming workflow value.

## Inputs

- frozen protocol/case bank and exact repo-local approvals;
- current source/runtime/model/adapter revisions per case;
- accepted value-spine schemas and operational readiness.

## Outputs

- append-only privacy-safe case envelopes;
- `processed/reports/dad-high-value-recovery/pilot-shadow-10.json`
- `processed/reports/dad-high-value-recovery/pilot-shadow-10.md`
- independent case/gate receipts under `checks/evidence/pilot/`.

## Procedure

J-510 is a cohort reconciliation gate. The controller materializes and leases
the ten `J-510-Cxx` child records already bound by J-500; it never leases J-510
as one 10-case work unit.

For each case:

1. Verify source revision, eligibility, assignment, authority, and lease.
2. Record task start and frozen metric inputs before outcome visibility.
3. Run only the approved baseline/candidate behavior; no automatic external or
   destructive action.
4. Record recommendation, adoption/non-adoption, outcome, validation, cost/time,
   retries/reviews, and missingness through the Phase 03 contract.
5. Have the distinct checker verify actual final state, not the agent's claim.
6. Close within seven days or record an unresolved reason.
7. Append the receipt; never rewrite an earlier case.

After 10 cases, reconcile eligible/completed/closed/excluded/unknown counts,
compute metric reproducibility, and sample human disagreement.

## Acceptance checks

- Exactly 10 eligible real cases are accounted for.
- Ten unique child receipts match the frozen slot/case digests; no duplicate,
  rebound, skipped, or whole-cohort execution is accepted.
- 100% have structurally valid joinable envelopes or the gate fails.
- Metric recomputation matches stored results.
- Producer/checker independence holds.
- Negative cases do not trigger inappropriate recommendations/actions.
- No privacy/source-authority/harmful-action breach occurred.
- The report explicitly says this stage does not prove value.

## Failure and repair

One envelope repair may append a correction for structural mistakes. A privacy,
source-authority, or checker-integrity breach stops the pilot slice. Valid but
disappointing results are preserved.

## Handoff

Index every case receipt, reconciliation, disagreements, limitations, and the
P5A go/no-go decision. J-520 needs exact accepted protocol and P5A receipt.
