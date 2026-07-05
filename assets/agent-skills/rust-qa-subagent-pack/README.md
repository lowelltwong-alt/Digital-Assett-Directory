# Rust QA Subagent Pack

Status: candidate AI-agnostic DAD skill pack.

This pack defines reusable Rust review roles for Codex, Claude Code, Cursor,
Fable, or future agents. It is a pointer/wrapper asset: downstream repos should
check out a pointer to this pack, not copy the full role body, unless a local
human review approves vendoring.

## Use When

- A task adds or changes Rust code.
- A Python workflow calls a Rust CLI, crate, or extension.
- A repo claims Rust speed, parity, safety, or deterministic scanner behavior.
- A Rust starter-pack overlay, rollout packet, or downstream template changes.

## Do Not Use When

- The task is a trivial non-Rust edit.
- Rust is being proposed without a stable leaf boundary or profiling evidence.
- A repo has stricter local Rust guidance that supersedes this candidate pack.

## Roles

- `rust-architecture-boundary-reviewer`: keeps Rust in deterministic leaf
  tooling unless profiling, parity, and governance evidence justify more.
- `rust-leaf-test-hardener`: designs anti-brittleness tests for path handling,
  no-write failures, deterministic ordering, JSONL shape, symlinks, hashing,
  and quarantine behavior.
- `rust-qa-gauntlet-runner`: runs and reports the Rust validation ladder.
- `python-rust-boundary-and-parity-reviewer`: checks Python orchestration,
  Rust subprocess/CLI boundaries, redacted output, and same-scope parity.
- `rust-boundary-frontier-scout`: watches high-signal Rust and Python-to-Rust
  practices and converts them into pointer-only DAD candidates.
- `dad-learning-and-asset-scout`: captures lessons, harness ideas, and asset
  updates back into DAD with applicability limits.
- `red-team-premortem-reviewer`: looks for false confidence, privacy leaks,
  brittle tests, over-Rusting, and stale rollout artifacts.

## Validation Baseline

```text
cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check
cargo check --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings
PYTHONPATH=src python -m pytest tests/test_rust_bridge_dad_scan_core.py tests/test_rust_rollout.py -q
```
