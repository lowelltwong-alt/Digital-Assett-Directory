# AGENTS.md

Follow the Rust AI Engineering Preflight rules.

- Public API is re-exported from `src/lib.rs`.
- Keep helpers private by default.
- Use `pub(crate)` only when crate-internal cross-module access is needed.
- Run `cargo fmt --check`, `cargo clippy --all-targets --all-features -- -D warnings`, and `cargo test --all` before reporting completion.
