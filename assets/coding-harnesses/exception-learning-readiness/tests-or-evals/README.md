# Exception Learning Readiness Evals

The minimum eval records the false-green cases that the learning queue must keep
blocked, including one-off validated fixes that are still below the comparable
sample threshold. The runnable command is:

```text
python -m digital_asset_directory.cli exceptions learning-check --scenarios assets/coding-harnesses/exception-learning-readiness/examples/synthetic-learning-readiness-scenarios.json
```
