# Long Rust CI and QA Plan

## Principle

Use two CI tiers:

```text
PR CI = fast, deterministic, blocks bad Rust quickly.
Long CI = manual/nightly/path-triggered, expensive assurance.
```

Do not put every expensive Rust test into every PR until the repo has stable performance data.

## PR Rust CI

Target runtime: under 5 minutes.

```bash
cargo fmt --check --manifest-path tools/dad_scan_core/Cargo.toml
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
python scripts/run_dad_scan_core.py --help
```

## Long Rust CI

Target runtime: allowed to be long.

Use for:

- nightly scheduled runs;
- manual `workflow_dispatch`;
- changes under `tools/**`, scanner config, source adapters, schema contracts;
- pre-release verification.

Suggested long gates:

```bash
cargo nextest run --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml --doc
cargo deny check
cargo audit
cargo llvm-cov --manifest-path tools/dad_scan_core/Cargo.toml --lcov --output-path coverage/lcov.info
cargo mutants --manifest-path tools/dad_scan_core/Cargo.toml --timeout 60 --jobs 2
cargo run --manifest-path tools/dad_scan_core/Cargo.toml -- scan-local ...large synthetic fixture...
python scripts/validate_rust_observation_jsonl.py ...
```

## Cross-platform matrix

Run at least:

```text
ubuntu-latest
windows-latest
macos-latest
```

For DAD, Windows is important because the source paths and OneDrive/cloud-placeholder behavior matter.

## What long CI should prove

- scanner works cross-platform;
- scanner can process a large synthetic source tree;
- source files are not mutated;
- quarantine rules are stable;
- output schema stays stable;
- no unexpected raw content is emitted;
- dependency/advisory/license posture is acceptable;
- tests remain meaningful under mutation or property testing.

## Tools to consider

| Tool | Use |
|---|---|
| `cargo-nextest` | faster, more reliable Rust test runner with CI support |
| `cargo-deny` | dependency graph, licenses, bans, sources, advisories |
| `cargo-audit` | RustSec vulnerability advisory check |
| `cargo-llvm-cov` | coverage |
| `cargo-mutants` | mutation testing |
| `proptest` | property tests |
| `insta` | snapshot tests |
| `assert_cmd` + `predicates` | CLI integration tests |
| `criterion` | benchmarks; long/manual first |
| `hyperfine` | command-level performance checks |

## Long CI warning

Long CI is useful only when it is structured. A 60-minute workflow that fails ambiguously will train agents to ignore it. Every long step should write a small report artifact and have a clear owner.
