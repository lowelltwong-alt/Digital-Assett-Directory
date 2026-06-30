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

## Rust shadow parity pilot

Native pytest is the authority for this repository. Rust tests or Rust-backed
test runners may be added as a shadow path, but they are candidate evidence until
their parity is reviewed over time.

Use the parity checker to run both paths and append an audit event. Exit-code-only
runs are telemetry, not verified parity:

```bash
python -m digital_asset_directory.cli test parity \
  --native-command "python -m pytest -q -m unit" \
  --shadow-command "cargo test --manifest-path rust-tests/Cargo.toml" \
  --session "<agent-session-id>"
```

The checker compares command exit codes, but it only reports `matched_pass` when
both sides produce fresh, non-empty structured JSON or JSONL reports with matching
test IDs and outcomes. If those records also include `duration_seconds`,
`duration`, `elapsed_seconds`, or `time`, the checker estimates per-test
replacement savings:

```bash
python -m digital_asset_directory.cli test parity \
  --native-command "python -m pytest -q --json-report --json-report-file processed/test_parity/native.json" \
  --shadow-command "cargo run --manifest-path rust-tests/Cargo.toml -- --report processed/test_parity/rust.jsonl" \
  --native-report processed/test_parity/native.json \
  --shadow-report processed/test_parity/rust.jsonl
```

Interpretation:

- `matched_pass`: both paths passed and any structured reports agree.
- `exit_code_match_only`: both commands passed, but coverage was not verified.
- `shadow_failed_native_passed`: Rust produced a false red.
- `shadow_passed_native_failed`: Rust produced a false green; treat as high concern.
- `structured_mismatch`: command exit codes may match, but reports are missing,
  empty, stale, same-path, or have per-test outcome differences.
- `both_failed`: not a green result; native pytest still failed.

Timing interpretation:

- **Shadow burn-in** runs both native pytest and Rust. It improves confidence but
  costs extra time. If run sequentially, wall-clock is roughly Python plus Rust.
  If run in parallel, wall-clock is roughly the slower side and may be distorted
  by CPU, disk, import, and antivirus contention.
- **Replacement estimate** is the cleaner speed signal: compare native duration
  with Rust duration when each runs without fighting the other and structured
  parity is verified. This estimates how much time could be saved after a
  specific Rust path is promoted.
- **Promotion** should be narrow. Replace only the slice with reviewed parity and
  measured savings; keep periodic native pytest runs to catch semantic drift.

Audit records are written under ignored `audit/events/` paths. Command output
tails are omitted from audit records by default because test logs can contain
private paths, environment details, or secrets. Audit events are useful burn-in
evidence, not promotion evidence by themselves. Promote any Rust path to a real
gate only after reviewed parity history, clear coverage mapping, and a rollback
plan.
