# J-500 — Freeze the Pilot Protocol and Case Set

## Contract

- Phase: P5
- Depends on: accepted J-410 and J-215 receipts
- Owner: `pilot-designer`
- Checker: `independent-checker`
- Lease: 120 minutes; heartbeat every 15 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-500:r1`
- Auto-advance: no; H-005, H-006, H-007 and repo-local gates

## Goal

Freeze the primary metric, cohorts, assignments, case eligibility, evidence
boundary, and stopping rules before pilot outcomes are visible.

## Inputs

- accepted Phases 01–04 evidence;
- H-005 metric, H-006 slices, H-007 exact repos;
- repo-local authority/privacy/participation decisions;
- Phase 05 record and threshold definitions.

## Outputs

- `processed/reports/dad-high-value-recovery/pilot-protocol.json`
- `processed/reports/dad-high-value-recovery/pilot-protocol.md`
- immutable case-bank manifest with 10 shadow, 20 comparative, and 40 value-gate
  case bindings;
- exact child-slot binding table for `J-510-C01..C10`, `J-520-C01..C20`, and
  `J-530-C01..C40`, including case digests, dependency order, idempotency,
  checkpoint, receipt, lease, and reissue rules;
- checker and human approval receipts under `checks/evidence/pilot/`.

## Procedure

1. Select one primary metric and freeze its direction, estimator, denominator,
   analysis population, missing-data rule, and charter P5B/P5C thresholds;
   preserve all guardrails and predeclare secondary metrics.
2. Define task start/end, human-wait exclusion, repair/review counting, defect
   verification, operator-attention collection, and missing-data behavior.
3. Define inclusion/exclusion before results, with a case reconciliation rule.
4. Choose baseline/candidate assignment and matching/randomization method.
5. Stratify by workflow, repo, task difficulty, and arm/matched pair without
   post-result relabeling. Freeze at least 8 cases per repo, 6 per selected
   slice, and 8 per arm/pairs for P5B; at least 10 per repo, 8 per selected
   slice, and 16 per arm/pairs for P5C.
6. Include positive and should-not-trigger/negative cases.
7. Name producer, checker, sampled human calibrator, and independence basis.
8. Define privacy-safe metadata fields and forbid raw content/transcripts.
9. Define early stops and the rule against enlarging a valid disappointing pilot.
10. Bind each enumerated manifest child slot to one case digest. Child IDs,
    idempotency keys, checkpoints, and receipt paths are immutable after binding;
    only one child may hold a lease at a time.
11. Hash/freeze the protocol, case bank, and binding table; obtain local repo
    approvals and an independent manifest-consistency receipt.

## Acceptance checks

- Protocol fully computes the primary metric from permitted evidence.
- Cohorts, assignment, inclusion, exclusions, thresholds, and stops are frozen.
- The selected primary metric alone determines benefit-gate success; no
  post-outcome metric, estimator, denominator, or eligibility substitution is
  possible.
- All 70 child slots have unique immutable IDs, case digests, idempotency keys,
  checkpoints, receipts, and serial dependency order before J-510 dispatch.
- Every case has an independent evaluation path.
- Maximum three exact repos and only approved workflow slices are included.
- No downstream write or real task starts from this planning job alone.
- Checker and Lowell approve exact protocol/case digests.

## Failure and repair

One repair may resolve measurement ambiguity. Missing repo authority, privacy
boundary, or evaluator independence is `blocked_human`. Do not replace a hard-to-
measure primary metric after seeing outcomes.

## Handoff

Index protocol/case digests, approvals, primary metric, assignments, exclusions,
privacy boundary, and exact start conditions for J-510.
