# dad_scan_core

Deterministic Rust leaf probes for Digital Asset Directory.

## Boundary

This crate emits **non-authorizing raw observations**. Python remains responsible for DAD orchestration, scoring, graph/radar logic, mail policy, release gates, and review workflows.

## Commands

```bash
cargo run --manifest-path tools/dad_scan_core/Cargo.toml -- scan-local   --source examples/demo_assets   --source-id demo_assets   --path-alias demo   --out raw/local/demo.jsonl   --summary-out processed/scans/demo-summary.json   --quarantine-out processed/quarantine/demo-quarantine.json   --max-files 100

cargo run --manifest-path tools/dad_scan_core/Cargo.toml -- mail-spool-check   --root processed/mail   --root-alias dad/central-mail   --root mail/outbox/rust_rollout   --root-alias dad/rust-rollout-reference
```

`mail-spool-check` is read-only. It counts JSONL files, lock files, atomic temp
fragments, Rust rollout packet JSON files, malformed JSONL rows, and oversized
JSONL rows using public-safe root aliases. It does not collect, route, deliver,
release, adopt, or mutate mail.

## Required verification

```bash
cargo check --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings
```

Verification note: this crate has been compiled and tested locally in DAD. Treat broad scans, downstream adoption, and any Python behavior replacement as candidate-only until their own local validation and parity evidence pass.
