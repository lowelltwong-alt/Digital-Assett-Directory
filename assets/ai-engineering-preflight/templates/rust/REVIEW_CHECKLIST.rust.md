# Rust AI Code Review Checklist

## Boundary review

- [ ] Is `pub` used only for intended external API?
- [ ] Is `pub(crate)` justified?
- [ ] Are struct fields private unless intentionally exposed?
- [ ] Is `lib.rs` a clean façade with `pub use` where useful?
- [ ] Are internal modules kept internal?

## API design review

- [ ] Newtypes used for IDs/units/domain values where useful.
- [ ] Enums used for states/modes instead of bools or strings.
- [ ] Builders/constructors used for complex values.
- [ ] Recoverable errors use `Result<T, E>`.
- [ ] Error types are meaningful.
- [ ] Important errors/panics/safety constraints are documented.
- [ ] Public types implement or derive `Debug` where appropriate.

## Verification review

- [ ] `cargo fmt --check` run or not-run reason stated.
- [ ] `cargo clippy --all-targets --all-features -- -D warnings` run or not-run reason stated.
- [ ] `cargo test --all` run or not-run reason stated.
- [ ] `cargo test --doc` run or not-run reason stated.
