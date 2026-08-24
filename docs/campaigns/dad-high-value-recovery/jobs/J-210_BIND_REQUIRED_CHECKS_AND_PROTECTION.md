# J-210 — Bind Required Checks and Branch Protection

## Contract

- Phase: P2
- Depends on: accepted J-200 receipt
- Owner: `bounded-writer` for repository changes; named human for GitHub settings
- Checker: `independent-checker`
- Lease: 120 minutes for repo work and immediate external tests
- Attempts: one original plus one bounded repair
- Idempotency key: `dad-high-value-recovery-v1:J-210:r1`
- Auto-advance: no; human/external-state gates

## Goal

Make a required failure fail the aggregate and the protected path, with current
GitHub evidence and no silent administrator bypass.

## Inputs

- accepted J-200 head and all five workflow files;
- current required contexts and branch-protection snapshot;
- H-004 decision and separate setting-change authorization;
- CI module-boundary manifest/harness.

## Outputs

- fail-closed workflow aggregation and tests;
- privacy-safe proposed/current/post-change protection snapshots;
- deliberate-failure and six-pass run evidence;
- checker receipts under `checks/evidence/phase-2/`.

## Procedure

1. Trace each required conclusion to its producer jobs and path filters.
2. Make failed, cancelled, unexpectedly skipped, missing, and stale required
   evidence produce a failing aggregate.
3. Keep optional checks visibly advisory and outside the required aggregate.
4. Add deterministic workflow-contract fixtures for every conclusion state.
5. Produce an exact protection-settings diff. Stop before mutation unless the
   separate human authorization matches repo, branch, settings, and head.
6. Apply H-004 through the authorized GitHub path; never use a local claim as
   proof of remote state.
7. On a non-merge test branch/PR, inject a known contract failure and prove the
   required status fails and blocks the protected path.
8. Restore the test branch state without merging it.
9. Trigger/observe two immediate accepted-head full regressions.
10. Start J-215 to observe four scheduled weekly regressions.
11. Revalidate on any workflow, head, protection, or required-context change.

## Acceptance checks

- CI governance harness passes.
- Required aggregate fails for every negative fixture.
- Deliberate failure is blocked remotely.
- Protection snapshot matches H-004, including administrator behavior.
- Any bypass is exact, actor-bound, reasoned, expiring, and independently visible.
- Two immediate accepted-head regressions pass.
- J-215 is registered to observe four scheduled weekly runs before Phase 05.

## Failure and repair

Repository logic may use one repair. Remote permission absence is
`blocked_human`; flaky or stale remote evidence is `inconclusive`. Never disable
or bypass protection to make the gate pass.

## Handoff

Index workflow SHA, required contexts, remote settings evidence, deliberate
failure URL, two immediate pass URLs, bypass expiry, and checker receipt. Hand
the exact workflow/protection/head digests to J-215. Phase 03 may begin while the
scheduled stability gate remains open.
