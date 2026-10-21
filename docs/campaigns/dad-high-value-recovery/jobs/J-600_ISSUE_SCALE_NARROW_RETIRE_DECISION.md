# J-600 — Issue the Scale/Narrow/Retire/Re-audit Decision

## Contract

- Phase: P6
- Depends on: exactly one selected predecessor from the accepted revision-7
  terminal route; never all possible predecessors
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
- selected route ID, predecessor receipt/result/state/coverage, trigger class,
  closure digest, passing checker-record digest, accepted navigation-receipt
  digest, and permitted-decision set;
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

1. Verify the route receipt and materialize a J-600 packet whose `depends_on`
   and dependency digest name only the selected predecessor.
2. Reconcile every required evidence receipt and correction, including the
   exact closure and producer/checker digest chain.
3. Apply the frozen thresholds mechanically and show the preliminary result.
4. Present overall and slice-level benefit, counterevidence, cost, operator
   burden, harm, missingness, bias, and uncertainty.
5. Run independent premortems for only the route's permitted decisions.
6. Select one permitted decision and state why every permitted alternative was
   rejected; never select a decision outside the route.
7. Map each component to retained, dormant, superseded, or proposed retirement.
8. For each retained component name owner, evidence revision, review/expiry,
   rollback, and revalidation triggers.
9. Define the smallest follow-on campaign scope. Do not execute it.
10. Freeze the producer-attempt digest, obtain a separate digest-bound checker
    record, resolve findings, then obtain Lowell's signed
   exact decision.
11. Request separately leased final navigation and record DAD postflight and
    workspace lifecycle disposition. The J-600 writer performs no navigation.

## Acceptance checks

- One allowed decision, no ambiguous hybrid.
- The decision is in the selected route's permitted set, and the packet,
  Portfolio event, checkpoint, and receipt bind the same route ID, predecessor,
  result/state/coverage, trigger class, closure digest, navigation-receipt
  digest, and permitted decisions.
- Decision matches thresholds or explicitly labels a human exception that is not
  represented as measured success.
- Counterevidence, costs, attention, harms, unknowns, and disagreements are not
  omitted.
- Every component has a disposition and pointer plan.
- Raw evidence remains immutable.
- No scale, retirement, cleanup, publication, merge, deployment, or downstream
  action occurs in this job.
- The J-600 writer cannot request `07_EVIDENCE_INDEX.md`, `handoff.md`,
  `08_SUPERSESSION_AND_ARCHIVE_MAP.md`, or `checks/evidence/navigation/`.
- Signed decision, DAD postflight, and worktree disposition exist.

## Failure and repair

One revision may answer checker findings. Missing, stale, malformed, unjoinable,
metric-corrupt, or checker-integrity evidence allows only `re-audit`; valid
disappointing evidence allows `narrow`/`retire`. A request to perform the
follow-on action is new scope and must stop this job.

## Handoff

After the signed decision, the inert controller may project a final-navigation
packet. Only a separately leased `campaign-navigation-writer` may update
`07_EVIDENCE_INDEX.md` and `handoff.md`; it may update
`08_SUPERSESSION_AND_ARCHIVE_MAP.md` only because J-600 is signed. A distinct
`independent-checker` must accept a second immutable
`{route_id}-post-j600.json` receipt that
binds the final projection digest, `post-j600-signed-decision` stage, exact
07/handoff/08 paths, and signed J-600 receipt digest. It cannot reuse or
overwrite the pre-J-600 `{route_id}.json` receipt. Then close campaign
postflight without performing the follow-on action.
