# Rust Minimal Preflight Template

This minimal crate demonstrates the preflight asset's Rust style:

- private-by-default internals;
- narrow public façade from `lib.rs`;
- newtypes for domain values;
- explicit error type;
- tests against public behavior.

Run:

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all
```
