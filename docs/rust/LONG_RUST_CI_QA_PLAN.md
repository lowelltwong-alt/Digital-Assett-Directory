# Long Rust CI QA Plan

PR Rust CI should stay tolerable:

- `cargo fmt --check`
- `cargo check`
- `cargo test`
- `cargo clippy --all-targets --all-features -- -D warnings`
- Python wrapper smoke tests

Long Rust CI may add:

- `cargo nextest`
- `cargo deny`
- `cargo audit`
- coverage
- mutation testing
- cross-platform matrix

Long CI should be manual, scheduled, or path-filtered until the Rust surface is
stable. Passing Rust CI proves only the deterministic tool contract; it does not
prove DAD governance truth, asset value, legal judgment, or theological meaning.
