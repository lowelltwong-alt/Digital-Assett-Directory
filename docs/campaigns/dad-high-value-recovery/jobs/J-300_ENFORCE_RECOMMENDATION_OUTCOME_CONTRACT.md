# J-300 — Enforce the Recommendation/Outcome Contract

## Contract

- Phase: P3
- Depends on: accepted J-210 receipt
- Owner: `bounded-writer`
- Checker: `independent-checker`
- Lease: 180 minutes; heartbeat every 20 minutes
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-300:r1`
- Auto-advance: yes after all gates

## Goal

Make invalid recommendation outcomes impossible to count and difficult to write,
while remaining backward-readable for existing data.

## Inputs

- Phase 03 contract and reverse-consumer map;
- current usage, recommendation, workflow-run, pipeline schemas;
- `dad_library.py`, `event_pipeline.py`, relevant fixtures/tests;
- H-008 retention decision.

## Outputs

- backward-compatible schema revisions/fields on existing surfaces;
- producer-boundary membership, enum, revision, adoption, idempotency, and
  checker-integrity validation;
- positive/negative/end-to-end tests;
- schema registry/key-value updates required by existing governance.

## Procedure

1. Enumerate every producer and consumer of the affected records with direction,
   authority, compatibility, and test coverage.
2. Define canonical envelope fields and constrained reason codes.
3. Add optional backward-readable fields to existing schemas; enforce the full
   counted-envelope contract at new-write/aggregation boundaries.
4. In `record_trace_outcomes`, resolve the exact recommended asset set and reject
   non-members, prose, sentinels, empty IDs, and unsupported enums.
5. Separate identity, outcome, reason, and evidence fields.
6. Add stable idempotency: identical retry dedupes; conflicting retry fails.
7. Prevent producer/checker equality from creating independently validated state.
8. Ensure synthetic rows cannot satisfy real-task gates.
9. Run reverse-consumer and backward-fixture tests.

## Acceptance checks

- All Phase 03 negative fixtures fail at the correct boundary.
- Positive fixtures traverse recommendation, adoption, outcome, validation, and
  lifecycle references.
- Old schema revisions remain readable and are not silently promoted.
- No unknown/recommended-nonmember asset can enter a counted outcome.
- Identical retries are idempotent; conflicts are visible failures.
- Full validation remains green.

## Failure and repair

A repair may fix code/schema/test inconsistency. A compatibility break, unknown
consumer, or need for in-place history rewrite is terminal for this revision and
requires a versioned migration decision.

## Handoff

Index schema/methodology revisions, reverse-consumer evidence, fixture results,
compatibility limits, and checker receipt. Give J-310 the exact classifier rules.

