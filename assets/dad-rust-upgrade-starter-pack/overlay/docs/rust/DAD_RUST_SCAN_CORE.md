# DAD Rust Scan Core

## Status

Candidate implementation scaffold. Not canonical until reviewed and adopted.

## Purpose

`tools/dad_scan_core` is the first Rust leaf tool for Digital Asset Directory.

It scans local source trees and emits raw, non-authorizing observations for Python to validate and ingest.

## Boundary

Rust may:

- walk local directories;
- skip excluded paths;
- refuse symlinks by default;
- hash metadata/content;
- emit JSONL observations;
- emit quarantine and summary JSON.

Rust may not:

- score asset value;
- decide lifecycle status;
- infer final duplicate identity;
- create graph truth;
- create AI context packs;
- mutate source files;
- become the source of governance authority.

## Verification

```bash
cargo check --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings
```

## First fixture scan

```bash
python scripts/run_dad_scan_core.py   --source examples/demo_assets   --source-id demo_assets   --path-alias demo   --out raw/local/demo.jsonl   --summary-out processed/scans/demo-summary.json   --quarantine-out processed/quarantine/demo-quarantine.json   --max-files 100
```
