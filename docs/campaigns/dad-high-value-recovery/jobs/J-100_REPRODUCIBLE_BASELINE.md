# J-100 — Produce the Reproducible Recovery Baseline

## Contract

- Phase: P1
- Depends on: signed launch receipt
- Owner: `bounded-writer`
- Checker: `independent-checker`
- Lease: 90 minutes; heartbeat every 15 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-100:r1`
- Auto-advance: no; owner accepts the baseline

## Goal

Create a deterministic, privacy-safe baseline report that refreshes every audit
dimension in Phase 01 and reconciles its own totals.

## Inputs

- `campaign.md`, `01_BASELINE_AND_FREEZE.md`, and this packet;
- current Git and global worktree registry observations;
- current local validation, GitHub run/protection, DAD outcome/usage/yield,
  session/mail/coverage, daemon/journal/transport, and portfolio reports;
- accepted source revision and launch manifest digest.

## Outputs

- `processed/reports/dad-high-value-recovery/baseline.json`
- `processed/reports/dad-high-value-recovery/baseline.md`
- `processed/reports/dad-high-value-recovery/operational-eligibility-baseline.json`
- focused fixtures/tests only if an existing surface cannot provide a required
  observation and the manifest is re-approved with exact paths
- checker receipts under `checks/evidence/phase-1/`

## Procedure

1. Record source revision, branch, worktree registration, observation time, and
   every command/query revision before collecting counts.
2. Reuse existing read-only DAD reports and commands. Do not trigger mutation,
   collection delivery, janitor apply, or cleanup.
3. Capture local checks even when they fail; preserve stdout/stderr/exit code.
4. Inspect GitHub state read-only and store run URLs/IDs, workflow SHA, required
   context, protection state, and query time.
5. Recompute outcome-join and sentinel counts from immutable sources. Publish
   the eligibility rule and all excluded/unknown counts.
6. Freeze the operational denominator artifact: cutoff, exact source IDs and
   revisions, privacy-safe stable item IDs or hashes, population by source
   category, inclusion/exclusion rules, reason-code map, and the equation
   `expected_open = baseline_eligible + eligible_arrivals - verified_closures -
   approved_superseding_corrections`.
7. Reconcile each family and every operational equation term to item-level
   evidence so source total equals classified totals.
8. Capture command duration and coverage. Do not estimate unknown token/cost
   values without labeling methodology.
9. Regenerate against unchanged inputs and compare semantic output after
   excluding only generated timestamps.
10. Give raw evidence and report to the checker without a producer-authored pass
   label.

## Acceptance checks

- JSON parses and all required dimensions exist.
- Every numeric claim has source refs and observation time.
- Reconciliation equations hold.
- The operational eligibility artifact's digest is recorded in the acceptance
  receipt, and its cutoff, sources, stable population, rules, reason codes, and
  reconciliation equation are complete and independently reproducible.
- Missing sources render `coverage_unavailable` or `unknown`.
- Repeated unchanged-input generation is semantically identical.
- No source, global registry, GitHub setting, mailbox, or worktree was mutated.
- The report makes no high-value claim.

## Failure and repair

One repair may correct the report/composition logic. A changed source, missing
authority, or irreproducible observation is `inconclusive`, not a repairable
formatting error. Stop before J-110 until the owner accepts the baseline.

## Handoff

Record the report digests, operational-eligibility-baseline digest, checker
receipt, changed-vs-prior-audit table, unknowns, and exact next job in
`07_EVIDENCE_INDEX.md` and `handoff.md`. J-400 must consume the exact accepted
operational-baseline path and digest; a symbolic manifest digest must be rebound
to that accepted digest before J-400 can be dispatched.
