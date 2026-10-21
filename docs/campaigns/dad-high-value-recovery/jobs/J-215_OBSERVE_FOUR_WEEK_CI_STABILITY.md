# J-215 — Observe Four-Week CI Stability

## Contract

- Phase: P2 external-state observation
- Depends on: accepted J-210 immediate enforcement receipt
- Owner: `ci-stability-observer`
- Checker: `independent-checker`
- Lease: one observation lease per scheduled run; no busy polling
- Attempts: observe each naturally scheduled run once; one evidence-repair pass
- Idempotency key: `dad-high-value-recovery-v1:J-215:<scheduled-run-id>:r1`
- Auto-advance: no; Phase 05 waits for the final checker receipt

## Goal

Prove the repaired workflow stays green for four consecutive naturally scheduled
weekly runs on accepted revisions while other local recovery work proceeds.

## Inputs

- accepted J-210 workflow, protection, required-context, and head digests;
- scheduled workflow run IDs/URLs and authoritative GitHub conclusions;
- current workflow/protection state at each observation.

## Outputs

- `processed/reports/dad-high-value-recovery/ci-stability-4-week.json`
- `processed/reports/dad-high-value-recovery/ci-stability-4-week.md`
- one append-only observation receipt per run and a final independent receipt
  under `checks/evidence/phase-2/`.

## Procedure

1. Register a bounded weekly monitor or resume at the next expected run; do not
   repeatedly poll unchanged state.
2. For each natural scheduled run, record run ID/URL, event time, workflow SHA,
   tested head, required job conclusions, duration, and current protection state.
3. Reject a run if the workflow/protection contract changed without a revised
   J-210 gate, or if required evidence is missing/skipped/stale.
4. Preserve failed runs. Do not manually rerun them and relabel the sequence as
   four scheduled passes.
5. After four consecutive eligible scheduled passes, reconcile the observation
   window and obtain the independent checker receipt.
6. If a run fails, return to J-200/J-210 under a revised dependency graph; the
   four-pass sequence restarts only after the new repair is accepted.

## Acceptance checks

- Four consecutive eligible naturally scheduled weekly runs pass.
- Every run used the accepted or explicitly revised workflow/protection contract.
- No required child is failed, cancelled, unexpectedly skipped, missing, or stale.
- Run URLs and GitHub conclusions are authoritative external evidence.
- No unfavorable run was deleted, hidden, or replaced by a manual rerun.

## Failure and repair

Evidence formatting may use one repair. A workflow change, failed run, or stale
protection state is not an evidence repair; it reopens the underlying CI job.
Permission/access absence is `blocked_human` or `coverage_unavailable`.

## Handoff

Update the evidence index after each run without waking the user for unchanged
state. On the fourth pass, hand the final stability receipt to the Phase 05 gate.

