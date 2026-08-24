# J-520 — Run the 20-Task Comparative Pilot

## Contract

- Phase: P5B
- Depends on: accepted J-510 receipt
- Owner: `pilot-producer`
- Checker: `independent-checker`
- Lease: one case at a time; 90 minutes maximum per case
- Attempts: frozen case/task policy; one envelope correction
- Idempotency key: `dad-high-value-recovery-v1:J-520:<case-id>:r1`
- Auto-advance: no; threshold decision required

## Goal

Measure a large practical effect on at least 20 comparable real tasks across at
least two approved repositories.

## Inputs

- unchanged frozen protocol, primary metric, and assignment method;
- P5A accepted measurement/envelope evidence;
- current per-case source/runtime revisions and approvals.

## Outputs

- append-only case envelopes;
- `processed/reports/dad-high-value-recovery/pilot-comparison-20.json`
- `processed/reports/dad-high-value-recovery/pilot-comparison-20.md`
- independent threshold receipt under `checks/evidence/pilot/`.

## Procedure

J-520 is a cohort reconciliation gate. The controller leases the twenty frozen
`J-520-Cxx` child records one at a time and accepts no whole-cohort lease.

1. Execute cases without changing inclusion, metric, or thresholds.
2. Balance/match baseline and candidate per the frozen method.
3. Keep runtime/model/tool changes visible and exclude only by predeclared rule.
4. Verify outcomes with deterministic final-state checks where possible and an
   independent reviewer otherwise.
5. Reconcile all eligible cases and exclusions.
6. Compute the frozen primary estimator, rework, defects/safety, closure, harm, false
   positives, reuse, sessions, follow-through, and queue guardrails.
7. Present slice-level and overall results, uncertainty, counterevidence, and
   cost/attention.

## Acceptance checks

- At least 20 comparable real tasks and two repos are accounted for.
- Allocation meets at least 8 cases per repo, 6 per selected slice, and 8 per
  arm or matched-pair equivalent; every child slot and eligible case reconciles.
- At least 80% close validly within seven days.
- The H-005 primary metric meets its frozen P5B threshold; secondary metrics do
  not substitute.
- No verified defect/safety/privacy regression.
- Zero independently confirmed harmful cases (the below-2% rule at this sample);
  false-positive attention below 10% with its denominator reported.
- Two assets have independently evidenced reuse across two repos.
- Phase 04 operational ceilings remain met.

If benefit does not pass with valid evidence, the result is `fail_terminal` for
scale and routes to Phase 06; do not add cases to find significance.

## Failure and repair

Only evidence-envelope/method computation defects may be corrected. Changed
protocol, compromised evaluator, or invalid cohort routes to `re-audit`. Valid
negative evidence routes to `narrow`/`retire`.

## Handoff

Index case reconciliation, baseline/candidate tables, thresholds, guardrails,
counterevidence, cost, checker receipt, and the P5B decision.
