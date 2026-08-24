# J-530 — Run the 40-Task Value Gate

## Contract

- Phase: P5C
- Depends on: accepted passing J-520 receipt
- Owner: `pilot-producer`
- Checker: `independent-checker` plus sampled human calibration
- Lease: one case at a time; 90 minutes maximum per case
- Attempts: frozen task policy; one envelope correction
- Idempotency key: `dad-high-value-recovery-v1:J-530:<case-id>:r1`
- Auto-advance: no; Phase 06 decision required

## Goal

Decide whether any approved workflow slice produces enough verified real-task
value to justify continued investment.

## Inputs

- unchanged frozen protocol and accepted P5B evidence;
- at least three approved repos and current per-case source/runtime revisions;
- two-week voluntary-use observation design.

## Outputs

- append-only case and voluntary-use evidence;
- `processed/reports/dad-high-value-recovery/pilot-value-gate-40.json`
- `processed/reports/dad-high-value-recovery/pilot-value-gate-40.md`
- independent/human calibration receipts under `checks/evidence/pilot/`.

## Procedure

J-530 is a cohort reconciliation gate. The controller leases the forty frozen
`J-530-Cxx` child records one at a time and accepts no whole-cohort lease.

1. Continue only the frozen eligible case design; no post-hoc success metric.
2. Complete at least 40 comparable real cases across at least three repos.
3. Observe two weeks in which approved participants can voluntarily use or
   decline the workflow; invocation alone is not voluntary-value proof.
4. Reconcile and independently verify every case.
5. Compute overall and per-slice primary outcome, guardrails, cost, operator
   attention, voluntary use, missingness, and uncertainty.
6. Run blind/sample human calibration and document disagreement.
7. Apply early-stop rules immediately and preserve negative evidence.
8. Issue a pass/fail/inconclusive receipt without selecting the lifecycle
   decision; J-600 owns that decision.

## Acceptance checks

- At least 40 real comparable tasks and three repos are reconciled.
- Allocation meets at least 10 cases per repo, 8 per selected slice, and 16 per
  arm or matched-pair equivalent; every child slot and eligible case reconciles.
- Two weeks of voluntary-use evidence exists.
- The H-005 primary metric meets its frozen P5C threshold; no secondary metric
  or post-result estimator substitutes.
- Zero independently confirmed harmful cases (the below-2% rule at this sample);
  false-positive attention below 10%; median queue age below seven days; closure
  at least 80% within seven days.
- No material defect/privacy/source-authority/safety regression.
- Synthetic/fixture rows contribute zero success cases.
- At least two assets retain independently evidenced cross-repo reuse.

## Failure and repair

Evidence computation may be corrected with an append-only receipt. A valid
failure is terminal for `scale` and proceeds to J-600. Evidence invalidity is
`inconclusive` and supports only `re-audit`.

## Handoff

Index all cohort/result/guardrail/cost/attention/voluntary-use evidence,
counterevidence, checker disagreement, and P5C receipt for J-600.
