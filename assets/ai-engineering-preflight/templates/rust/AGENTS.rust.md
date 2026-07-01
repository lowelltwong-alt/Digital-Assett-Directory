# Rust AI Engineering Preflight

## Rust modularity rule

Rust is private by default. Use that property deliberately.

- Use `pub` only for the intended external API.
- Use `pub(crate)` only for crate-internal APIs that must cross module boundaries.
- Keep struct fields private unless direct field access is intentionally part of the API.
- Use `pub use` from `lib.rs` to create a clean public façade.
- Keep helper modules private when they are implementation details.

## API design tactics

- Use newtypes for domain IDs, units, and values that should not be confused.
- Use enums for states instead of booleans or stringly typed state.
- Use builders or constructors for complex values.
- Return `Result<T, E>` for recoverable errors.
- Use meaningful error types and document important error behavior.
- Validate arguments at boundaries.
- Implement or derive `Debug` for public types where appropriate.
- Prefer traits for dependency boundaries when production code and tests need different implementations.
- Avoid exposing internals only to make tests easier.

## Module layout tactics

Prefer this shape for library crates:

```text
src/
  lib.rs              # public façade, pub use intended API
  domain/             # value types and domain rules
  services/           # public use-case orchestration
  adapters/           # database, HTTP, filesystem, external systems
  errors.rs           # public or crate error types
```

Example façade:

```rust
mod billing;
mod errors;

pub use billing::{BillingResult, SubscriptionBilling};
pub use errors::BillingError;
```

## Long-module refactor tactics

For oversized Rust modules:

1. Map public items, private functions, structs/enums, side effects, trait boundaries, and tests.
2. Preserve public API unless asked.
3. Extract value types and errors first.
4. Extract pure domain logic next.
5. Extract adapters and side effects last.
6. Re-export only the intended public API from `lib.rs`.

## Default checks

Run available checks. Prefer workspace-specific commands if documented.

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all
cargo test --doc
```

If a command is unavailable or too broad for the repo, report that and run the nearest relevant check.
