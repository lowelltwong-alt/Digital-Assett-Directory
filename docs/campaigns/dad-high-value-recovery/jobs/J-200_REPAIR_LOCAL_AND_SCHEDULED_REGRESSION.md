# J-200 — Repair Local and Scheduled Regression Failures

## Contract

- Phase: P2
- Depends on: accepted J-110 receipt
- Owner: `bounded-writer`
- Checker: `independent-checker`
- Lease: 180 minutes; heartbeat every 20 minutes
- Attempts: one original plus one bounded repair per accepted root-cause batch
- Idempotency key: `dad-high-value-recovery-v1:J-200:r1`
- Auto-advance: yes after deterministic and independent gates

## Goal

Repair the refreshed local/scheduled failures by root cause without weakening
assertions, hiding failures, or changing unrelated behavior.

## Inputs

- accepted baseline failure inventory and immutable run artifacts;
- `.github/workflows/scheduled-full-regression.yml`;
- exact failing tests and implicated source files;
- `.ci/module-boundaries.yaml` and CI governance harness.

## Outputs

- smallest source/test/fixture changes for each accepted root cause;
- regression tests that fail on the pre-fix behavior and pass after repair;
- focused/full validation evidence under `checks/evidence/phase-2/`.

## Procedure

1. Create a table of every refreshed failure, reproduction command, root-cause
   class, implicated file, proposed fix, and regression test.
2. Narrow the manifest write set to exact files before editing. If the failure
   list differs from J-100, stop for a digest revision.
3. Reproduce focused failures without repeating unchanged expensive commands.
4. Fix product defects in the smallest authority-owning module. Repair stale
   fixtures only when the expected contract is independently confirmed.
5. Add negative tests for the root cause; do not delete or relax a test solely
   to pass.
6. Run focused checks, then one full baseline after inputs materially change.
7. Have the checker compare pre-fix failure evidence, patch, test sensitivity,
   unrelated diff, and full result.

## Acceptance checks

- Every baseline failure is fixed, intentionally deferred with owner/evidence,
  or still explicitly failing; none disappear through skipping.
- New tests fail against the old behavior or an equivalent fault injection.
- No required assertion, privacy boundary, source-authority rule, or module edge
  is weakened.
- Focused and full local validation pass.
- Diff is limited to the accepted root-cause table.

## Failure and repair

One bounded repair may address checker findings. A new unrelated failure,
nondeterministic result, changed dependency, or assertion-weakening proposal
stops the job as inconclusive/terminal for owner review.

## Handoff

Index each failure-to-fix mapping, tests, full-suite receipt, remaining risks,
and exact accepted head. Pass J-210 only the verified revision.

