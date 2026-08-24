# Phase 02 — CI and Enforcement Recovery

## Outcome

Make local validation, GitHub Actions, and protected-branch enforcement tell the
same truth. A deliberately failing required contract must fail the required
status and block the protected path.

## Prerequisites

- Phase 01 baseline and freeze are accepted.
- H-004 selects either administrator enforcement or an exact, time-limited,
  signed bypass receipt design.
- A separate approval exists before any GitHub setting mutation.
- Current workflow heads, protection state, and scheduled-failure artifacts are
  captured by immutable URL/digest.

## Jobs in order

1. `jobs/J-200_REPAIR_LOCAL_AND_SCHEDULED_REGRESSION.md`
2. `jobs/J-210_BIND_REQUIRED_CHECKS_AND_PROTECTION.md`
3. Start `jobs/J-215_OBSERVE_FOUR_WEEK_CI_STABILITY.md` as a bounded external-state monitor.

J-210 has an immediate enforcement-ready gate: local checks pass, two manual
full regressions pass, and a deliberate failure is remotely blocked. After that
gate, Phase 03 may proceed while J-215 observes four scheduled weekly runs.
Phase 05 cannot start until J-215 passes. This overlaps calendar waiting without
weakening the final stability requirement.

## Existing surfaces to repair

- `.github/workflows/scheduled-full-regression.yml`
- `.github/workflows/dad-contract-check.yml`
- `.github/workflows/validate.yml`
- `.github/workflows/rust-ci-pr.yml`
- `.github/workflows/rust-ci-long.yml`
- `.ci/module-boundaries.yaml`
- `scripts/validate_ci_module_boundaries.py`
- `tests/test_ci_module_boundaries.py`
- `docs/TESTING_AND_ORCHESTRATION.md`
- the exact source/test files implicated by the refreshed failures

Use `assets/agent-skills/dad-ci-module-boundary-governance/` and its harness.
Do not broaden path filters or required-check ownership without observed-edge
evidence and a reviewed manifest change.

## Implementation order

### A. Reproduce and classify

1. Re-run each failing test locally against the exact accepted head.
2. Classify each as product defect, stale fixture, environment dependency,
   nondeterminism, workflow defect, or coverage unavailable.
3. Preserve failure output before editing.
4. Create one regression test per repaired root cause; do not simply loosen an
   assertion or remove a test.

### B. Repair the product/test causes

1. Fix the smallest source boundary that explains each failure.
2. Keep Python/Rust authority unchanged; Rust leaf checks cannot satisfy Python
   governance gates.
3. Run focused tests after each repair, then the full local baseline once.
4. If the exact unchanged full-suite command already ran for at least five
   seconds, reuse immutable evidence until inputs change.

### C. Remove false green

1. Remove or isolate `continue-on-error` behavior from required conclusions.
2. Ensure aggregation jobs fail when a required child job fails, is cancelled,
   is skipped unexpectedly, or emits stale evidence.
3. Preserve truly advisory checks under a clearly non-required name and display
   their advisory status.
4. Make validation and roadmap checks run in a way that reports all required
   failures without converting a prior failure into a skipped green aggregate.
5. Add deliberate-failure fixtures for contract failure, stale evidence,
   cancelled child, skipped child, and missing dependency coverage.

### D. Bind branch protection

1. Produce the exact proposed protection diff from current settings.
2. H-004 option A: require the accepted aggregate and enforce it for
   administrators.
3. H-004 option B: keep a bypass only if it is actor-specific, reasoned,
   expiring, reviewable, and represented by a signed receipt checked against the
   exact head and required statuses.
4. Apply settings only with separate human authorization.
5. Capture the post-change settings from GitHub, not from a local assertion.
6. Deliberately fail the contract on a test branch/PR and prove the protected
   path blocks it. Do not merge the test failure.

## Validation ladder

```powershell
$env:PYTHONPATH = 'src'
python -m pytest <focused tests>
python scripts/validate_ci_module_boundaries.py
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check --no-update
```

J-210 obtains external evidence for:

- two consecutive manually triggered full-regression passes on accepted heads;
- one deliberate required-check failure that blocks the protected path;
- protection state matching H-004;
- no bypass outside its exact signed scope.

J-215 then observes four consecutive scheduled weekly full-regression passes.
It never reruns the workflow just to replace an unfavorable scheduled result.

## Acceptance

- All local baseline commands exit zero.
- Every refreshed scheduled-regression failure has a root cause, regression
  test, and repair evidence.
- Required workflow aggregation fails closed on failed, cancelled, unexpected
  skipped, missing, and stale child evidence.
- A deliberate contract failure produces a failing required status.
- Protected-branch settings have authoritative external evidence.
- Administrators are enforced or the approved signed bypass is exact and
  expiring.
- Two immediate full regressions pass on accepted revisions (J-210).
- Four weekly scheduled full regressions pass on accepted revisions (J-215).
- No assertion was weakened solely to make a run green.

## Stop conditions

Stop on secrets in logs, unexplained nondeterminism, a changed workflow head,
an unapproved GitHub mutation, protection ambiguity, dependency coverage
unavailable for a required check, or any proposal to bypass a failing gate.

## Rollback

Workflow/code rollback is the bounded inverse patch on the exact accepted head.
GitHub settings rollback requires a separate approved settings receipt. Never
restore a false-green configuration as an emergency shortcut.
