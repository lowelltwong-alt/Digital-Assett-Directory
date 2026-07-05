# Rust QA Subagents

Status: candidate DAD routing guide.

DAD uses AI-agnostic Rust subagent roles when Rust work is material enough that
one agent should not both implement and bless the design. The canonical pack is
`assets/agent-skills/rust-qa-subagent-pack/`.

## Default Lanes

- Architecture boundary: decide whether Rust belongs in the slice at all.
- Leaf test hardening: convert scanner/parser/hash/CLI behavior into Rust tests.
- QA gauntlet: run fmt, check, tests, clippy, and bridge tests.
- Python/Rust boundary: verify Python owns orchestration and default outputs are
  public-safe/repo-relative.
- Frontier scout: research high-signal Rust/Python-to-Rust practices and route
  them as DAD candidates.
- Learning scout: capture lessons, asset updates, and harness ideas.
- Red-team reviewer: find false confidence, stale overlays, and privacy leaks.

## Use With DAD Rust Work

Use the pack before promoting any Rust code beyond candidate leaf tooling. For
DAD's current Rust scanner, the important tests are no-write failures, path
alias safety, deterministic file limits, directory-level quarantine, symlink
refusal, exact JSONL shape, and overlay synchronization.

## Boundary

Subagents advise and test. They do not approve downstream repo writes, public
release, or Python-to-Rust replacement. Local repo authority, profiling, parity,
and validation still decide.
