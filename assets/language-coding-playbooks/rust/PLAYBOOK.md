# Rust Coding Playbook

Status: candidate DAD operational guidance.

## Role

Rust is DAD's deterministic leaf-tool language first. Use it for profiled hot
paths, scanners, chunkers, parsers, hashers, source-offset mappers, validators,
and single-binary tools when the compiler, Clippy, tests, and parity reports
make the boundary easier to trust.

Python keeps orchestration and review authority unless a human-reviewed design
decision says otherwise.

## Before Coding

- Require profile evidence before suggesting Rust for speed.
- Try Python-first fixes when the bottleneck may be algorithmic, fixture-bound,
  I/O-bound, subprocess-bound, or import-bound.
- Define a narrow boundary: same input, same output, deterministic order,
  schema-versioned JSON/JSONL where possible, and typed error cases.
- Run `cargo fmt`, `cargo check`, `cargo clippy`, tests, and doctests for Rust
  changes. Treat these as proof surfaces, not polish.
- For replacement claims, require same-scope parity and native validation before
  any timing or savings claim.

## AI-Overlooked Operations

- Use `cargo metadata` and `cargo tree` before adding or promoting Rust
  dependencies.
- Use newtypes, enums, exhaustive matches, `#[must_use]`, typed errors, and
  doc tests where they make future-agent mistakes fail deterministically.
- Use fuzz, property, mutation, or Miri-style scouts around pure parser,
  scanner, serializer, unsafe-sensitive, and offset-mapping boundaries.
- Use API compatibility checks before a shared crate or CLI becomes a DAD-owned
  dependency.
- Use benchmark/profiler evidence before adding parallelism, async, unsafe
  optimization, or a broader port.

## Harness Routes

- Python-to-Rust replacement candidate: `dad:harness:rust-shadow-parity`.
- Slow Python tests before Rust discussion:
  `dad:harness:python-test-performance-orchestration`.
- New Rust crate, tool, pattern, fuzz strategy, or compiler feature:
  `dad:harness:language-frontier-research`.
- Public/private or cross-repo Rust tool delivery:
  `dad:harness:public-private-source-provenance`.

## Frontier Watch

Use `asset-dir research frontier-watch --language rust` for the current source
list. Watch Rust project goals, Rust blog and RFCs, Cargo, Clippy, rust-analyzer,
Miri, RustSec, rust-fuzz, nextest, API compatibility tools, mutation testing,
PyO3/maturin, parser/search/indexing codebases, and performance measurement
tools.

Frontier findings are candidate-only. A crate, benchmark, blog post, or nightly
feature is not a DAD rule. Record pointer, safe summary, applicability limits,
proof surface, local validation idea, and rejection signals.

## Send Back To DAD

Send candidate mail when a Rust change reveals:

- a leaf tool that makes a repeated DAD task easier to run or audit;
- a parity mismatch that Python caught or Rust caught;
- a fuzz/property/mutation case that exposes an agent-written bug;
- a packaging, ABI, API compatibility, or dependency lesson;
- a frontier source pointer that could update the Rust buildout guide, tactics,
  or a harness eval.

