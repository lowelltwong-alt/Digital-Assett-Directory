# Rust Rollout Lesson Capture Protocol

Rust rollout lessons are append-only records in:

```text
lessons/rust_rollout/lesson_ledger.jsonl
```

Each lesson records:

- source repo;
- phase;
- problem;
- observed failure or friction;
- fix or workaround;
- reusable pattern;
- repo types it applies to;
- whether future prompts or templates should change;
- confidence;
- evidence references.

Summaries are regenerated from the ledger:

```bash
asset-dir rust-rollout lessons-summarize
```

The default summary destination is:

```text
processed/reports/rust_rollout/
```

Do not silently rewrite prior lesson records. Add superseding records when a
lesson changes.
