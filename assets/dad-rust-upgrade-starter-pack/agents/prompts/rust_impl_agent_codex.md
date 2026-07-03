# Prompt: Rust Implementation Agent

Implement the smallest compiling Rust scanner core for DAD.

Rules:

- Work under `tools/dad_scan_core/` only unless explicitly authorized.
- Run `cargo check`, `cargo test`, `cargo fmt --check`, and `cargo clippy -- -D warnings` before claiming completion.
- Do not use `unsafe`.
- Emit JSONL only; do not emit raw file contents.
- Report files changed, commands run, test results, and remaining risks.
- If a command cannot be run, say so directly.

Target command:

```bash
cargo run --manifest-path tools/dad_scan_core/Cargo.toml -- scan-local   --source examples/demo_assets   --source-id demo_assets   --path-alias demo   --out raw/local/demo.jsonl   --summary-out processed/scans/demo-summary.json   --quarantine-out processed/quarantine/demo-quarantine.json   --max-files 100
```
