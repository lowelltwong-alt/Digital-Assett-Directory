# Testing and Orchestration

## Why markers

The suite is fast today but grows by area. Markers let you and agents run
only the tests relevant to a change, satisfying the `AGENTS.md` *task-relevant validation*
rule without running everything every time.

## Marker taxonomy

| Marker | Meaning |
|---|---|
| `unit` | Fast, pure-logic; no filesystem, sqlite, or network |
| `integration` | Touches the filesystem, sqlite, or the full pipeline |
| `network` | Reaches external services (GitHub); **deselected by default** |
| `slow` | Long-running; deselect with `-m "not slow"` |
| `proposals` | Proposal-engine tests |
| `calibration` | Calibration-workflow tests |

Markers are enforced (`--strict-markers`): an unregistered marker fails the run.

## Selecting tests

```bash
pytest                              # full suite (skips network via default addopts)
pytest -m unit                      # only fast logic tests
pytest -m proposals                 # only proposal-engine tests
pytest -m "integration and not slow"
pytest tests/test_extractors.py -k redact   # one file / name filter
pytest --lf                         # rerun last failures
pytest --testmon                    # only tests affected by your changes (needs pytest-testmon)
pytest --picked                     # tests for files changed per git (needs pytest-picked)
```

> Note: a command-line `-m` overrides the default `-m "not network"`. To keep both,
> write `-m "unit and not network"`.

## Orchestration with nox

`noxfile.py` standardizes dev/CI tasks so there is one entrypoint:

```bash
nox -l                 # list sessions
nox -s tests           # full suite
nox -s fast            # unit only
nox -s changed         # testmon: only affected tests
nox -s lint types validate
```

Recommended wiring:

- **Local pre-push hook** -> `nox -s changed` (fast, relevant to the change).
- **CI** -> `nox -s tests lint types validate` (full coverage).

This keeps the heavy gate in CI while local loops stay fast. Do not reach for a workflow
engine (Airflow/Prefect/Dagster): this is a single-machine CLI pipeline, and the Typer CLI
plus nox is the right altitude.
