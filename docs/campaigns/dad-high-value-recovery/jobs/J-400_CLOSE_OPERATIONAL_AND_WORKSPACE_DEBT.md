# J-400 — Close Operational and Workspace Debt

## Contract

- Phase: P4
- Depends on: accepted J-320 receipt and accepted J-100 operational baseline
- Owner: `bounded-writer` for reports/code; named humans for lifecycle decisions
- Checker: `independent-checker`
- Lease: 180 minutes; heartbeat every 20 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-400:r1`
- Auto-advance: no; lifecycle human gates may remain

## Goal

Produce and act on a bounded review queue until Phase 04 readiness thresholds are
met, without inferring closure or performing unapproved cleanup.

## Inputs

- accepted Phase 03 value spine;
- exact
  `processed/reports/dad-high-value-recovery/operational-eligibility-baseline.json`
  path and digest from the accepted J-100 receipt;
- session reaper, janitor dry-run, cockpit/recovery, mail doctor/follow-through,
  coverage, Git/PR, and global worktree registry evidence;
- H-009 exact action boundary.

## Outputs

- `processed/reports/dad-high-value-recovery/operator-backlog.json`
- `processed/reports/dad-high-value-recovery/operator-backlog.md`
- narrow fixes to existing projection/classifier code only if current coverage is
  unavailable and a revised manifest pins the files;
- human decision packets, not inferred actions;
- checker evidence under `checks/evidence/phase-4/`.

## Procedure

1. Collect read-only observations and prove source-zero-write.
2. Resolve the manifest's symbolic J-100 output digest to the exact accepted
   operational-eligibility-baseline digest before dispatch. Load its population,
   source IDs/revisions, cutoff, inclusion/exclusion rules, and reason-code map;
   append eligible arrivals and reconcile every removal as a correction rather
   than redefining the denominator.
3. Normalize to a rebuildable projection with source type, stable ID, severity,
   owner, age, expiry/review, evidence, and suggested decision.
4. Dedupe display only; retain source records and show all contributing IDs.
5. Classify sessions honestly: active, completed-awaiting-postflight, abandoned
   candidate, parked/leased/held, or unknown.
6. Classify mail/follow-through without treating absence as a response.
7. Classify branches/worktrees with dirty/untracked counts, unique commits,
   upstream/PR/containment, registry state, and hold.
8. Present at most three immediate human asks; keep the full queue filterable.
9. Apply only actions exactly allowed by H-009 and each governing subsystem.
10. After every action, reobserve and record success, partial failure, residuals,
    and concurrent changes.
11. Repeat only when inputs changed; do not rescan unchanged costly sources.

## Acceptance checks

- 100% of observed worktrees have owner/disposition/review or recovery hold.
- Open sessions, follow-through, and high-signal queue meet Phase 04 ceilings.
- No invalid mail packets remain; unavailable scope is explicit.
- Every stale sensitive branch has a human disposition record.
- Immediate human asks are at most three.
- No present worktree/branch/source repo changed during read-only classification.
- Every mutation has an exact prior approval and residual check.
- Threshold reconciliation proves that no item became ineligible through a
  post-baseline reason-code or denominator change.
- The backlog report cites the exact accepted operational-baseline path and
  digest, and every equation term resolves to its stable source item or receipt.

## Failure and repair

Projection/dedupe logic may use one repair. Missing ownership/authority is
`blocked_human`. Ambiguous containment or dirty state requires `recovery_hold`;
it is never permission to clean.

## Handoff

Index before/after counts, source-zero-write fingerprints, decision/action
receipts, residuals, holds, unknowns, and checker findings. Pass J-410 only the
accepted observation time and sources.
