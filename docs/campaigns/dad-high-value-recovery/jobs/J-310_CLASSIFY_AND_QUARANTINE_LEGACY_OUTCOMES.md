# J-310 — Classify and Quarantine Legacy Outcomes

## Contract

- Phase: P3
- Depends on: accepted J-300 receipt
- Owner: `bounded-writer`
- Checker: `independent-checker`
- Lease: 120 minutes; heartbeat every 15 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-310:r1`
- Auto-advance: yes after reconciliation

## Goal

Create a deterministic, reversible classification overlay for every historical
outcome without changing raw rows.

## Inputs

- immutable historical outcome sources and digests;
- J-300 canonical contract/classifier revision;
- H-008 treatment and privacy limits.

## Outputs

- classification projection/report with `joinable`, `invalid`, and `unknown`;
- reason-code counts and reconciliation by source/time/event family;
- aggregate filter that admits only eligible `joinable` rows;
- tests for repeatability, corrections, and raw-source zero-write.

## Procedure

1. Fingerprint each source before processing.
2. Classify deterministically; never infer missing recommendation membership.
3. Emit safe IDs/hashes and reason codes, not raw private payloads.
4. Reconcile every source total exactly.
5. Compare source fingerprints after processing to prove zero writes.
6. Update aggregate readers to filter by exact classification/methodology
   revision and expose excluded counts.
7. Regenerate unchanged inputs and compare semantic output.
8. Independently sample all reason-code families, not only joinable rows.

## Acceptance checks

- `source_total = joinable + invalid + unknown` for every source and globally.
- Raw source hashes are unchanged.
- Repeated unchanged-input classification is stable.
- Aggregates exclude invalid and unknown rows and show their counts.
- Corrections append/supersede; they do not rewrite prior evidence.
- Samples confirm prose sentinels and absent-membership rows are invalid.

## Failure and repair

One repair may fix deterministic classifier/report logic. Ambiguous identity is
`unknown`, not a repair target. Any raw mutation is a gold-standard failure and
stops the campaign.

## Handoff

Index source/classifier/report digests, reconciliation, zero-write proof,
sampled checker findings, and limitations for J-320.

