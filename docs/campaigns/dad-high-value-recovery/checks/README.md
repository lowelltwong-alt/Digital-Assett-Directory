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

Every receipt must include the campaign/job/gate/attempt revisions, input and
dependency digests, source revision, producer/checker identities, adapter and
capability evidence, released lease, command or external query, timestamps,
exit/result, evidence/output digests, affected paths, measured budgets, privacy
class, state, next action, and revalidation triggers.

`verify_receipt_durability.py` loads `campaign.json` and fails closed on missing
fields, placeholder identities, stale pass inputs, unresolved dependency
digests, producer/checker identity reuse, incomplete pass coverage, undeclared
paths, weak digests, or a receipt that omits the gate evidence/revalidation
contract. It proves shape and linkage only; the independent checker still owns
truth evaluation.

Run the checker contract tests before launch:

```powershell
python -m pytest docs/campaigns/dad-high-value-recovery/checks/test_verify_receipt_durability.py -q
```
