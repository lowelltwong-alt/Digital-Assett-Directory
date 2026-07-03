# Exception Learning Readiness Scripts

This harness currently uses the DAD CLI as its executable script surface.

Primary command:

```text
asset-dir exceptions learning-check --scenarios assets/coding-harnesses/exception-learning-readiness/examples/synthetic-learning-readiness-scenarios.json
```

See `runbook.md` for the manual run sequence, expected outputs, and review
checks. Keep script additions deterministic and local-only; this harness must
not mutate downstream repos or send cross-repo mail while evaluating readiness.
