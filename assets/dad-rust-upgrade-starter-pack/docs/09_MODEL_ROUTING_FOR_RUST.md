# Model Routing for Rust Work

## Working principle

Do not pick one model for all Rust work. Route by task type.

## Cheap coding model / Cursor Composer-style use

Use a cheaper coding model for:

- module scaffolding;
- serde structs;
- simple CLI flags;
- converting small Python functions to Rust;
- obvious compiler-error loops;
- test fixture boilerplate;
- documentation drafts.

Do not let a cheap model be the final reviewer for:

- security-sensitive scanner logic;
- dependency trust decisions;
- unsafe code;
- cross-repo architecture;
- CI policy;
- source-of-truth/authority boundaries.

## Strong implementation agent

Use a stronger repo-editing agent for:

- making the crate compile;
- running `cargo check/test/fmt/clippy`;
- wiring Python wrapper/adapters;
- fixing CI failures;
- preserving current DAD behavior while adding Rust.

## Architecture/review model

Use a stronger reasoning model for:

- crate boundary design;
- Rust-vs-Python boundary decisions;
- no-mutation and path-safety review;
- governance/authority boundary review;
- long CI strategy;
- multi-repo reusable patterns.

## Prompt rule

Every Rust implementation prompt should include:

```text
Do not claim completion unless you ran the commands.
Report files changed.
Report commands run.
Report tests run.
Report tests not run.
Do not use unsafe.
Keep Rust output non-authorizing JSON/JSONL evidence.
Keep Python as orchestrator unless explicitly told otherwise.
```

## Composer/Cursor note

Cursor Composer-style models are attractive for cost-sensitive Rust scaffolding, especially if the work is in Cursor and the agent can use the repo context. Treat generated Rust as draft until compiled and tested. Rust's compiler is a useful reviewer, but passing `cargo check` does not prove architecture, security, or domain correctness.
