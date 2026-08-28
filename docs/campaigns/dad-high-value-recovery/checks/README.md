# Campaign Checks

This directory defines evidence shape and acceptance semantics. During an
authorized run, only the controller or independent checker may write under
`checks/evidence/`; implementation workers must not edit their own gate results.

## Evidence layout

```text
checks/
  ACCEPTANCE_MATRIX.md
  evidence-receipt.template.json
  human-decision-receipt.template.json
  evidence/
    launch/
    phase-1/
    phase-2/
    phase-3/
    phase-4/
    pilot/
    navigation/
    decision/
```

The directories under `evidence/` are controller-owned runtime paths. They do
not need placeholder files before launch.

## Result semantics

- `pass`: required evidence exists, inputs are current, and the named checker
  confirms the acceptance condition.
- `fail_repairable`: the job may use its one bounded repair attempt.
- `fail_terminal`: a protected invariant or success criterion cannot be met in
  the current campaign revision.
- `blocked_human`: an exact decision or permission is required.
- `inconclusive`: evidence is missing, stale, unjoinable, or cannot distinguish
  pass from fail. The campaign does not advance.

Every producer attempt must include the campaign/job/gate/attempt and binding
revisions, idempotency, source/input/dependency digests, adapter/capability
evidence, outputs/evidence, outcome/state/coverage, measured budgets, lease and
effects, case/closure/route bindings, limitations, affected paths, privacy class,
and revalidation triggers. Canonicalize that immutable material before any
checker field and record its `producer_attempt_digest`.

A distinct checker writes a separate record binding the exact producer digest,
checker identity and independence basis, disposition `pass` or `challenge`,
timestamp, limitations, and the checker record's canonical digest. The final
receipt binds the checker-record path and digest. Producer and checker identities
must differ, and the producer cannot write the checker record. Missing, stale,
malformed, challenged, self-checked, mismatched, or circular bindings fail
closed. A dependency is accepted only when its job result satisfies the declared
outcome contract and its checker disposition is `pass`. Checker `pass` means
faithful evidence, not a favorable job outcome.

Terminal-route evidence lives under `checks/evidence/navigation/`. The campaign
controller and shell adapter can produce only an inert projection. An existing
Portfolio OS lease must separately authorize a task-local
`campaign-navigation-writer`, and a distinct `independent-checker` owns the
immutable `checks/evidence/navigation/{route_id}.json` receipt. Ordinary job
writers may never write the navigation root, `07_EVIDENCE_INDEX.md`,
`handoff.md`, or `08_SUPERSESSION_AND_ARCHIVE_MAP.md`.

`verify_receipt_durability.py` loads `campaign.json` and fails closed on missing
fields, placeholder identities, stale pass inputs, unresolved dependency
digests, producer/checker identity reuse, missing checker-record bindings,
incomplete pass coverage, incomplete cohort closure, undeclared paths, weak
digests, or a receipt that omits the gate evidence/revalidation contract. It
proves shape and linkage only; the independent checker still owns truth
evaluation.

Run the checker contract tests before launch:

```powershell
python -m pytest docs/campaigns/dad-high-value-recovery/checks/test_verify_receipt_durability.py -q
```
