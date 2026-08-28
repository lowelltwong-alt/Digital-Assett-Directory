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
- `processed/reports/dad-high-value-recovery/pilot-comparison-20-closure.json`
- independent threshold receipt under `checks/evidence/pilot/`.

## Procedure

J-520 is a cohort reconciliation gate. The controller leases the twenty frozen
`J-520-Cxx` child records one at a time and accepts no whole-cohort lease. It
materializes `{case_digest}` in memory and requires the accepted v2 binding-table
digest in the packet, lease, dispatch projection, checkpoint, and receipt. Each
child writes only its unique
`processed/reports/dad-high-value-recovery/pilot-case-envelopes/{job_id}.json`;
it cannot request parent aggregate, closure, navigation, or checker paths.

1. Execute cases without changing inclusion, metric, or thresholds.
2. Balance/match baseline and candidate per the frozen method.
3. Keep runtime/model/tool changes visible and exclude only by predeclared rule.
4. Verify outcomes with deterministic final-state checks where possible and an
   independent reviewer otherwise.
5. Freeze each producer-attempt digest, obtain a separate digest-bound checker
   record, and reconcile all eligible cases and exclusions.
6. Compute the frozen primary estimator, rework, defects/safety, closure, harm, false
   positives, reuse, sessions, follow-through, and queue guardrails.
7. Present slice-level and overall results, uncertainty, counterevidence, and
   cost/attention.
8. With parent action `validate` only, create the aggregate reports after the
   closure artifact exactly partitions all twenty slots, independently verifies
   every started child, enumerates immutable unstarted/withdrawn reasons,
   releases leases, reconciles effects, and proves no post-stop receipt or lease.

## Acceptance checks

- At least 20 comparable real tasks and two repos are accounted for.
- Allocation meets at least 8 cases per repo, 6 per selected slice, and 8 per
  arm or matched-pair equivalent; every child slot and eligible case reconciles.
- All twenty v2 slots have unique matching envelopes and binding-table digests,
  and closure is complete. Partial closure never passes.
- At least 80% close validly within seven days.
- The H-005 primary metric meets its frozen P5B threshold; secondary metrics do
  not substitute.
- No verified defect/safety/privacy regression.
- Zero independently confirmed harmful cases (the below-2% rule at this sample);
  false-positive attention below 10% with its denominator reported.
- Two assets have independently evidenced reuse across two repos.
- Phase 04 operational ceilings remain met.

If benefit does not pass with valid complete evidence, the result is
`fail_terminal` for scale. After closure, `p5b-valid-terminal` permits only
`narrow` or `retire`; do not add cases to find significance.

## Failure and repair

Only evidence-envelope/method computation defects may be corrected. Changed
protocol, compromised evaluator, invalid cohort, missing/stale/unjoinable data,
metric corruption, or checker-integrity failure is `inconclusive`; after
complete control-plane closure, only `p5b-inconclusive` to `re-audit` is valid.

## Handoff

The controller projects but does not perform navigation. A separately leased
`campaign-navigation-writer` and distinct `independent-checker` must accept the
exact P5C or J-600 route.
The successor binds the P5B receipt, closure, checker record, navigation receipt,
and no other predecessor.
