# Prompt: DAD Rust Upgrade First Task

Goal: Add DAD's first Rust scanner core as a non-authorizing deterministic leaf tool.

Scope:

- Add `tools/dad_scan_core/` from this pack.
- Add `scripts/run_dad_scan_core.py` wrapper.
- Add `docs/rust/DAD_RUST_SCAN_CORE.md`.
- Add PR Rust CI template only if the crate compiles.

Do not:

- replace the Python scanner;
- alter graph/radar scoring;
- change DAD source-of-truth registries;
- add PyO3;
- use `unsafe`;
- scan the whole local drive in CI.

Verification:

```bash
cargo check --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
cargo fmt --check --manifest-path tools/dad_scan_core/Cargo.toml
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings
python scripts/run_dad_scan_core.py --help
```

Final report must include files changed, commands run, tests run, tests not run, and risks.
