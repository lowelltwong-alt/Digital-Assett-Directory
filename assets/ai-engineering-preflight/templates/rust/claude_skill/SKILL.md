---
name: ai-engineering-preflight-rust
description: Use before modifying Rust crates, public APIs, module boundaries, pub/pub(crate) visibility, or large modules.
---

# Rust AI Engineering Preflight Skill

## Procedure

1. Read `AGENTS.md` and `docs/ai-preflight/RUST_PREFLIGHT.md`.
2. Map public `pub` items, private helpers, `pub(crate)` items, re-exports, side effects, errors, traits, and tests.
3. Preserve the public API unless asked to break it.
4. Keep items private by default.
5. Expose a clean façade through `lib.rs` where useful.
6. Prefer newtypes, enums, builders, meaningful errors, and traits for boundaries.
7. Run cargo checks and report exact results.

## Output

Report:

- public API touched;
- visibility changes;
- files changed;
- tests/checks run;
- checks not run and why;
- risks.
