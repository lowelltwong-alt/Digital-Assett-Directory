# Rust Long-Module Refactor Protocol

Use this when a Rust file is oversized, exposes too much with `pub`, mixes domain logic with I/O, or is hard for an AI agent to reason about.

## Phase 1 — Map first

Do not edit immediately. Return:

```text
- public items and re-exports
- private helpers
- pub(crate) items
- structs/enums/traits
- error types
- side effects
- dependencies
- tests/doc tests
- recommended extraction plan
```

## Phase 2 — Preserve API

Keep the crate's public API stable unless the task asks for a breaking change.

Check:

```bash
cargo test --all
cargo test --doc
```

## Phase 3 — Extract in safe order

1. value types and newtypes;
2. error types;
3. pure domain functions;
4. traits for dependency boundaries;
5. adapters for external systems;
6. service/orchestration module;
7. public façade in `lib.rs`.

## Phase 4 — Re-export intentionally

Public consumers should import from the façade where possible:

```rust
use my_crate::{SubscriptionBilling, BillingError};
```

not from deep internal paths:

```rust
use my_crate::billing::internal::retry::RetryCalculator;
```

## Phase 5 — Verify

Run formatting, Clippy, tests, and doc tests where applicable.
