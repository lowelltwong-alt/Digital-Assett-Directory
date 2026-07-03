# Target Repo Rust Ownership Model

DAD owns rollout policy, templates, lessons, reports, local instruction packets,
and planning commands.

Each target repo owns:

- its own `Cargo.toml`;
- its own lockfile when appropriate;
- its own Rust source under `tools/<repo_specific_tool>/`;
- its own Rust tests and fixtures;
- its own Rust CI workflows;
- its own Rust adoption docs, reports, and lessons;
- its own validation commands.

DAD must not create a target repo Rust slice that depends on a local relative
path back into DAD. Separation readiness is part of the rollout contract.
