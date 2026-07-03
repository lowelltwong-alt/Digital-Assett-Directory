# Skill: Rust Scan Core

## Purpose

Build and maintain Rust scanner cores that emit non-authorizing JSON/JSONL observations for Python orchestration.

## Use when

- scanning many files;
- hashing files;
- building source inventories;
- producing stable JSONL observation streams;
- enforcing no-mutation source safety.

## Do not use when

- the task requires legal/theological/domain judgment;
- the output would become canonical authority;
- the workflow is still changing daily;
- a Python wrapper/validator does not exist.

## Required checks

```bash
cargo check
cargo test
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
```

## Required report

- files changed;
- commands run;
- tests run;
- tests not run;
- source-mutation proof;
- unsafe/dependency risks.
