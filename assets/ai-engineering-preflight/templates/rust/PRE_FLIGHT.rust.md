# Rust Preflight Checklist

## Before editing

- [ ] Read `Cargo.toml`, `src/lib.rs` or `src/main.rs`, and relevant modules.
- [ ] Identify public `pub` items and re-exports.
- [ ] Identify private helpers and internal modules.
- [ ] Identify `pub(crate)` boundaries.
- [ ] Identify structs with public fields.
- [ ] Identify error types and `Result` flow.
- [ ] Identify side effects: filesystem, network, database, env, subprocesses, randomness, time.
- [ ] Identify tests and doc tests.

## While coding

- [ ] Keep items private by default.
- [ ] Use `pub` only for intended external API.
- [ ] Use `pub(crate)` only when internal cross-module access is needed.
- [ ] Avoid leaking internal module paths.
- [ ] Use `pub use` to expose a clean façade.
- [ ] Use newtypes for IDs and units.
- [ ] Use enums for states and modes.
- [ ] Use builders/constructors for complex values.
- [ ] Validate inputs at boundaries.
- [ ] Return `Result<T, E>` for recoverable failures.

## Before final answer

- [ ] Run `cargo fmt --check`.
- [ ] Run `cargo clippy --all-targets --all-features -- -D warnings`.
- [ ] Run `cargo test --all`.
- [ ] Run `cargo test --doc` for library crates with docs.
- [ ] Inspect diff.
- [ ] Report changed files, commands run, commands not run, assumptions, and risks.
