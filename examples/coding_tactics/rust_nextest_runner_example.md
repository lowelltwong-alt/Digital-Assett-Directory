# Rust Test Runner Evidence Example

Use an isolated runner only when the repo needs per-test duration, retries,
partitioning, or machine-readable reports.

```text
cargo nextest run --workspace --profile ci
cargo test --workspace
```

Record both commands during evaluation before changing the repo default. A speed
claim needs the same workload, same test scope, exit codes, durations, and report
paths.
