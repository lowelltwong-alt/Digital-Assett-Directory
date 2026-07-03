# Drop-in Map

## Safe default

Place this whole folder in:

```text
assets/dad-rust-upgrade-starter-pack/
```

Nothing is active until you copy the overlay files.

## Overlay files

| Pack path | Suggested DAD repo path | Purpose |
|---|---|---|
| `overlay/tools/dad_scan_core/` | `tools/dad_scan_core/` | First Rust scanner crate |
| `overlay/scripts/run_dad_scan_core.py` | `scripts/run_dad_scan_core.py` | Python wrapper to invoke Rust scanner |
| `overlay/docs/rust/DAD_RUST_SCAN_CORE.md` | `docs/rust/DAD_RUST_SCAN_CORE.md` | DAD scanner design note |
| `templates/github/workflows/rust-ci-pr.yml` | `.github/workflows/rust-ci-pr.yml` | PR Rust smoke CI |
| `templates/github/workflows/rust-ci-long.yml` | `.github/workflows/rust-ci-long.yml` | Manual/nightly long Rust CI |
| `templates/nextest.toml` | `.config/nextest.toml` | nextest profile template |
| `templates/deny.toml` | `deny.toml` | cargo-deny starter config |

## Non-overlay planning files

Keep these under `assets/dad-rust-upgrade-starter-pack/` or promote selectively into DAD docs after review.
