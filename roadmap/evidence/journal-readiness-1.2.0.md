# Journal Readiness 1.2.0 Evidence

Status: reviewed implementation evidence; synthetic/mock development scope only.

## Profile

Baseline command:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli transport readiness --hub . --journal-repo "$HOME/.dad/dad-journal"
```

Observed full-output baseline: 300.1 seconds over approximately 14,700 indexed
files. A warm-cache cProfile run took 118.4 seconds: full index integrity used
58.2 seconds, `sha256_file` used 47.4 seconds, duplicate JSONL status counting
used 19.3 seconds, and rich JSON rendering used 32.6 seconds. Within hashing,
Windows file opens used 31.4 seconds, so storage latency dominated CPU hashing.

## Reproducible Benchmark

```powershell
$env:PYTHONPATH='src'
python scripts/benchmark_journal_integrity.py `
  --journal-repo "$HOME/.dad/dad-journal" `
  --workers 1,2,4 `
  --repeats 3
```

The initial same-corpus experiment produced identical normalized result digests
and zero errors for all worker counts. One-worker, two-worker, and four-worker
runs took 17.1, 10.7, and 9.2 seconds respectively. Three end-to-end
`--summary-only` readiness runs took 26.4, 26.2, and 26.6 seconds, all reporting
full integrity valid through `python_thread_pool` and the same pending human gate.

## Decision

Four bounded Python workers improved the integrity hot loop by 46 percent and
the compact end-to-end readiness path by about 91 percent versus the original
full-output baseline. This clears the Python-first optimization gate. A Rust
batch verifier is therefore deferred: it must show at least 20 percent
incremental improvement over this optimized path, with exact parity, before
promotion. Python remains the executable serial oracle and fallback.

Independent failure-path review found and closed three readiness gaps before
promotion: executor worker-start/submission failures now use the serial oracle,
an existing unreadable or malformed checkpoint manifest forces immediate
recovery even below normal thresholds, and compact readiness output preserves
the journal status plus expected/seen engine versions. Focused reproductions
and the complete transport module pass with these cases enabled.

No file contents or private paths are emitted by the benchmark. It records only
counts, durations, clean/head checks, and a digest of the normalized result.
