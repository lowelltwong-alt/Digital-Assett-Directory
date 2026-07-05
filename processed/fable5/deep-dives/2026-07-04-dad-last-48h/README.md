# Fable 5 Deep Dive: DAD Last 48 Hours

Status: candidate internal audit packet.

Use this packet after the DAD Rust scan core is green. It gives Fable 5 a
ranked evidence map for the major DAD changes from July 3-4, 2026, with Rust
validation evidence included. Fable should focus on hard architecture,
algorithm, false-confidence, and root-cause problems, then delegate mechanical
implementation back to Codex with exact hints.

## Start Here

1. Read `fable5-master-prompt.md`.
2. Use `ranked-audit-map.md` to choose the highest-risk surfaces first.
3. Use `evidence-index.json` for commits, exception IDs, Rust validation, and
   path references.
4. Return findings in the shape described by `expected-output.schema.json`.
5. Use `codex-delegation-template.md` for lower-level fixes.

## Current Rust Evidence

The Rust scanner was hardened before this packet was created:

- `cargo test --manifest-path tools/dad_scan_core/Cargo.toml`: 18 Rust
  integration tests passed.
- `cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check`: passed.
- `cargo check --manifest-path tools/dad_scan_core/Cargo.toml`: passed.
- `cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings`: passed.
- `PYTHONPATH=src python -m pytest tests/test_rust_bridge_dad_scan_core.py tests/test_rust_rollout.py -q`: 13 passed.
- Real scan evidence:
  `raw/local/rust/dad_scan_core_20260704_142903.jsonl`,
  `processed/reports/rust/dad_scan_core_20260704_142903_summary.json`,
  `processed/quarantine/rust/dad_scan_core_20260704_142903_quarantine.json`.

## Boundaries

Do not copy private raw logs, credentials, large source blobs, or third-party
documentation into findings. Treat all findings as candidate evidence until DAD
validation and postflight confirm them.
