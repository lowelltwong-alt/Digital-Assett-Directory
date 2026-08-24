# J-600 — Issue the Scale/Narrow/Retire/Re-audit Decision

## Contract

- Phase: P6
- Depends on: accepted J-530 receipt or accepted early-stop/failure receipt
- Owner: `campaign-owner`
- Checker: `independent-checker`
- Lease: 120 minutes; heartbeat every 15 minutes
- Attempts: one draft plus one bounded response to checker findings
- Idempotency key: `dad-high-value-recovery-v1:J-600:r1`
- Auto-advance: no; Lowell signs the final decision

## Goal

Select one allowed lifecycle decision from the frozen evidence and define a
bounded follow-on boundary without performing it.

## Inputs

- all accepted campaign evidence and corrections;
- frozen thresholds/methodology;
- cost, attention, harm, missingness, counterevidence, and checker reports;
- component inventory and lifecycle registry.

## Outputs

- `processed/reports/dad-high-value-recovery/scale-or-shrink-decision.json`
- `processed/reports/dad-high-value-recovery/scale-or-shrink-decision.md`
- component disposition map and proposed lifecycle pointers;
- signed human decision and independent receipt under
  `checks/evidence/decision/`.

## Procedure

1. Reconcile every required evidence receipt and correction.
2. Apply the frozen thresholds mechanically and show the preliminary result.
3. Present overall and slice-level benefit, counterevidence, cost, operator
   burden, harm, missingness, bias, and uncertainty.
4. Run independent premortems for `scale`, `narrow`, `retire`, and `re-audit`.
5. Select one decision and state why every alternative was rejected.
6. Map each component to retained, dormant, superseded, or proposed retirement.
7. For each retained component name owner, evidence revision, review/expiry,
   rollback, and revalidation triggers.
8. Define the smallest follow-on campaign scope. Do not execute it.
9. Obtain checker disposition, resolve findings, then obtain Lowell's signed
   exact decision.
10. Record DAD postflight and workspace lifecycle disposition.

## Acceptance checks

- One allowed decision, no ambiguous hybrid.
- Decision matches thresholds or explicitly labels a human exception that is not
  represented as measured success.
- Counterevidence, costs, attention, harms, unknowns, and disagreements are not
  omitted.
- Every component has a disposition and pointer plan.
- Raw evidence remains immutable.
- No scale, retirement, cleanup, publication, merge, deployment, or downstream
  action occurs in this job.
- Signed decision, DAD postflight, and worktree disposition exist.

## Failure and repair

One revision may answer checker findings. Missing/invalid evidence allows only
`re-audit`; valid disappointing evidence allows `narrow`/`retire`. A request to
perform the follow-on action is new scope and must stop this job.

## Handoff

Update `07_EVIDENCE_INDEX.md`, `08_SUPERSESSION_AND_ARCHIVE_MAP.md`, and
`handoff.md` with the signed decision, exact follow-on boundary, retained risks,
and final worktree disposition. Then close the campaign postflight.

