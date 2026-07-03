# dad_scan_core

Deterministic local source scanner for Digital Asset Directory.

## Boundary

This crate emits **non-authorizing raw observations**. Python remains responsible for DAD orchestration, scoring, graph/radar logic, and review workflows.

## Commands

```bash
cargo run --manifest-path tools/dad_scan_core/Cargo.toml -- scan-local   --source examples/demo_assets   --source-id demo_assets   --path-alias demo   --out raw/local/demo.jsonl   --summary-out processed/scans/demo-summary.json   --quarantine-out processed/quarantine/demo-quarantine.json   --max-files 100
```

## Required verification

```bash
cargo check --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings
```

Generated scaffold note: this crate was generated without a Rust compiler in the current environment. Run `cargo check` first and treat compile fixes as expected.
