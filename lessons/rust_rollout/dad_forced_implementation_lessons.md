# DAD Rust Implementation Lessons

Source ledger: `lessons/rust_rollout/lesson_ledger.jsonl`

Early lessons:

- Generated Rust overlays should be formatted immediately, then checked with
  `cargo fmt --check`.
- Python needs a structured bridge around Rust subprocess execution before any
  DAD orchestration depends on a Rust tool.
- File scanners should reject self-observing output layouts by default.

These lessons are candidates for downstream Rust rollout packets and target repo
templates.
