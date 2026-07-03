# Rust Buildout Guide

Offering: `dad:offering:rust-buildout-guide` — machine-readable guide in
[rust-buildout.json](rust-buildout.json).

## What this asset decides

Whether, when, and how Rust enters a Python repo in this family:

- **When Rust pays off** (profiled CPU-bound text processing, parallel batch work,
  correctness-critical parsers, distributable CLIs) and when it does not (I/O-bound glue,
  prototypes, unprofiled guesses).
- **The staged migration path**: profile → Python-first fixes → Rust shadow →
  parity gate → PyO3/maturin extension → (rarely, human-gated) full port. Stages are
  ordered; the parity gate uses the existing
  [rust-shadow-parity harness](../coding-harnesses/rust-shadow-parity-harness/) and
  timing claims stay gated behind verified same-scope parity.
- **Rust idioms for AI legibility** (`rs-idiom:*` ids): typed errors, newtypes,
  exhaustive match, let-else, doc-tests, clippy pedantic — the conventions that keep
  Rust code readable and safely editable by future agents.

## How agents should use it

Consult during preflight for any task mentioning performance, Rust, ports, parsing
speed, or "make it faster". Stage 1 (profile) is mandatory before proposing Rust.
Cite `rs-idiom:*` ids in reviews and lessons so adoption is traceable.

## Frontier refresh

Refresh candidates come from `registry/trusted-source-registry.json` entries for
`rust-lang`, `rust-community-frontier`, `rust-ecosystem-curation`,
`rust-security`, `rust-fuzz`, `rust-test-frontier`, `pyo3`, and `google`.
Treat them as research pointers only. New Rust guidance needs screening, license
and maintenance checks for crates, profile evidence where performance is
claimed, and parity evidence before it changes downstream advice.

Rust starter packs, overlays, and rollout plans are candidates until reviewed.
Do not apply a full Rust overlay merely because a zip or source pack exists.
Prefer one DAD-owned read-only Rust leaf tool first, then record lessons before
downstream rollout.

The stronger language control plane lives in
`registry/language-coding-advantage-registry.json`. Its Rust row lists internal
guidelines, high-signal codebase watch targets, and promotion/rejection evidence
for Rust frontier ideas.

## Boundary

Installed candidate guidance for local reuse. The enforceable part is the stage gates
(profile evidence, parity reports, human review for full ports), not language preference.
