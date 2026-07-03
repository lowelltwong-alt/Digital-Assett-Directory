# Exception Learning Readiness Runbook

Run the synthetic readiness check:

```text
python -m digital_asset_directory.cli exceptions learning-check --scenarios assets/coding-harnesses/exception-learning-readiness/examples/synthetic-learning-readiness-scenarios.json
```

Use this runbook when changing:

- `write_exception_learning_queue`;
- fix-outcome validation or quarantine behavior;
- public/private release blockers;
- backfill promotion boundaries;
- event-type clustering or sample-size gates.

The runbook is an execution pointer, not promotion authority. A passing result
keeps known false-green cases covered; real lesson promotion still needs reviewed
source evidence and human approval.
