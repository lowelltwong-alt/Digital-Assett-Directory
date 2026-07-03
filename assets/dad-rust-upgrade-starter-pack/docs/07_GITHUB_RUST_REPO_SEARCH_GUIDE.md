# GitHub Rust Repo Search Guide

## When to search GitHub for Rust examples

Search before choosing a Rust architecture when:

- building a scanner, parser, indexer, or CLI you have not built before;
- picking crates for walking, globbing, hashing, JSONL, SQLite, or Python bindings;
- adding security/dependency tooling;
- adding long CI patterns;
- considering async/Tokio;
- considering PyO3/maturin;
- seeing borrow-checker complexity that suggests the design is wrong.

Do not search GitHub to copy unknown code blindly. Search to learn crate patterns, testing style, CI layout, error handling, and repo organization.

## Search query templates

```text
language:Rust walkdir globset sha2 jsonl cli
language:Rust clap serde_json walkdir sha256
language:Rust path traversal symlink scanner tests
language:Rust cargo nextest github actions cargo-deny cargo-audit
language:Rust pyo3 maturin cli python bindings
language:Rust jsonl streaming parser serde tests
language:Rust no_std not needed scanner CLI
```

## Quality filters

Prefer repos with:

- active recent commits;
- clear license;
- tests and CI;
- low/no `unsafe` for scanner-style code;
- explicit error handling;
- stable public API or CLI docs;
- responsible dependency posture;
- examples and benchmarks;
- maintainers who respond to issues.

Do not overfit to stars alone.

## High-signal Rust repos to study

| Repo | Why it matters for you |
|---|---|
| `BurntSushi/ripgrep` | file walking, ignore rules, regex/search performance, CLI rigor |
| `sharkdp/fd` | friendly filesystem scanner CLI |
| `serde-rs/serde` | serialization/deserialization patterns |
| `clap-rs/clap` | robust CLI interfaces |
| `tokio-rs/tokio` | async runtime patterns, only when async is justified |
| `astral-sh/ruff` | Python tooling implemented in Rust; relevant to Rust-for-Python acceleration |
| `pydantic/pydantic-core` | Rust core under Python API pattern |
| `pola-rs/polars` | Rust engine with Python integration and data workloads |
| `nextest-rs/nextest` | Rust test runner and CI patterns |
| `EmbarkStudios/cargo-deny` | dependency/license/advisory policy enforcement |
| `rustsec/rustsec` | cargo-audit and RustSec ecosystem |
| `taiki-e/cargo-llvm-cov` | coverage workflow patterns |

## What to extract from examples

Extract:

- module layout;
- error handling shape;
- CLI flag design;
- test fixture organization;
- snapshot testing style;
- GitHub Actions structure;
- dependency choices.

Do not extract:

- license-incompatible code;
- large copied algorithms without understanding;
- unsafe blocks;
- hidden policy assumptions;
- domain semantics from unrelated projects.
