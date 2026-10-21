# J-320 — Correct Learning-Yield Semantics

## Contract

- Phase: P3
- Depends on: accepted J-310 receipt
- Owner: `bounded-writer`
- Checker: `independent-checker`
- Lease: 120 minutes; heartbeat every 15 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-320:r1`
- Auto-advance: yes after report parity

## Goal

Make the yield report count actual written, reused, promoted, failed, and harmful
events according to the canonical value spine.

## Inputs

- accepted classification projection and J-300 semantics;
- `learning_yield_report.py`, event enums, usage/adoption sources, and tests;
- current report outputs if present.

## Outputs

- corrected yield aggregation and methodology version;
- golden positive/negative fixtures;
- report with numerators, denominators, exclusions, missingness, self-use, and
  cross-repo reuse separated;
- focused/full validation receipts.

## Procedure

1. Map every source event enum to one and only one yield category or exclusion.
2. Stop counting acknowledgements and saved-for-future as reuse.
3. Require a joinable used outcome, adoption link, independent validation, and
   distinct eligible task/repo for counted reuse.
4. Count promotion only from a named human lifecycle decision for the exact
   revision.
5. Report attempted failure and harm separately.
6. Report self-use and downstream/cross-repo reuse separately.
7. Add fixtures that would reproduce the old overcount and prove it now fails.
8. Compare report totals directly to the classified source rows.

## Acceptance checks

- Category mapping is exhaustive and mutually exclusive.
- Golden fixtures match expected counts.
- Acknowledgement/saved events produce zero reuse.
- Invalid/unknown/unverified rows produce zero beneficial reuse.
- Report totals reconcile to eligible/excluded rows.
- No generated report is labeled high-value without a pilot cohort.
- Full validation remains green.

## Failure and repair

One repair may correct mapping/report logic. Conflicting event semantics require
a schema/authority decision and block the job; do not choose a favorable mapping.

## Handoff

Index methodology revision, old/new count comparison, fixtures, excluded rows,
checker receipt, and Phase 03 completion decision.

