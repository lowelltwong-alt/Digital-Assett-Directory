# J-410 — Reconcile Daemon, Journal, and Scheduled-Task Health

## Contract

- Phase: P4
- Depends on: accepted J-400 receipt
- Owner: `bounded-writer`
- Checker: `independent-checker`
- Lease: 120 minutes; heartbeat every 15 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-410:r1`
- Auto-advance: yes after truth-consistency gate

## Goal

Ensure DAD health reporting cannot show green when the scheduled task, daemon
heartbeat, journal checkpoint, data root, or source reports disagree or are stale.

## Inputs

- accepted baseline and current operator-backlog observation time;
- `daemon.py`, `journal.py`, `transport.py`, `transport_readiness.py`, scheduled
  task registry, heartbeat/report schemas, and relevant tests;
- current Windows scheduled-task state read-only.

## Outputs

- consistent health fold using existing status/report surfaces;
- deterministic contradiction and stale/missing fixtures;
- tests and privacy-safe reconciliation report;
- checker receipt under `checks/evidence/phase-4/`.

## Procedure

1. Define source precedence and freshness for task state, heartbeat, last cycle,
   journal checkpoint, data root, transport audit, and generated reports.
2. Enumerate contradiction cases: task disabled but fresh heartbeat, running task
   with stale heartbeat, heartbeat success with failed journal, configured but
   uninitialized data root, missing report counted as zero, and clock skew.
3. Fold to explicit states such as `healthy`, `degraded`, `stale`, `missing`, or
   `coverage_unavailable`; do not invent success.
4. Preserve privacy minimization and path redaction required by current policy.
5. Add fault-injection fixtures for every contradiction.
6. Compare report against current scheduled-task/daemon/journal observations.
7. Do not change the task schedule or activate a daemon in this job.

## Acceptance checks

- Every source has precedence, freshness, and missing behavior.
- Contradictions and staleness cannot render healthy.
- Configured-but-uninitialized data root follows existing fallback policy.
- Fault-injection fixtures pass.
- Current live evidence reconciles or is explicitly degraded/unavailable.
- Full validation remains green.

## Failure and repair

One repair may fix fold/test logic. Access denied or external-state ambiguity is
`coverage_unavailable`; do not modify scheduled tasks to obtain a clean result.

## Handoff

Index source revisions, precedence table, fault fixtures, current reconciliation,
unknowns, and the Phase 04 readiness receipt.

