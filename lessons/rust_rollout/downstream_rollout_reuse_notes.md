# Downstream Rust Rollout Reuse Notes

Reusable defaults for future target repos:

- Install a repo-local Rust leaf tool; do not depend on a local DAD path.
- Add a Python bridge that can be mocked before orchestration depends on Rust.
- Run fmt, check, test, and clippy before claiming Rust readiness.
- Keep Rust output candidate-only until Python/DAD review ingests it.
- Preserve local source authority and do not move governance meaning into Rust.

Logos repos receive instruction packets only. Any Logos Rust implementation must
be initiated and governed inside the Logos repo.
