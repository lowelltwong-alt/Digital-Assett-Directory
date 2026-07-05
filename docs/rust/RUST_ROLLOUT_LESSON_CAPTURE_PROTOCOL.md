# Rust Rollout Lesson Capture Protocol

Rust rollout lessons are append-only records in:

```text
lessons/rust_rollout/lesson_ledger.jsonl
```

The row shape is registered at:

```text
schemas/rust-rollout-lesson.schema.json
```

`python -m digital_asset_directory.cli validate` checks existing ledger rows
against that schema.

Source repos do not write directly to this ledger or to DAD's central inbox.
They send Rust rollout feedback through their own repo-local outbox:

```text
.digital-asset/mail/outbox.jsonl
```

If `asset-dir` is unavailable, the fallback is still the same source-repo
outbox. Do not write to `processed/mail/inbox/**`, any repo inbox, or
`lessons/rust_rollout/lesson_ledger.jsonl` directly.

DAD collects, screens, routes, and reviews the candidate mail before appending
any DAD-owned lesson record. During a multi-repo Rust rollout storm, use:

```bash
python -m digital_asset_directory.cli mail storm-gate
python -m digital_asset_directory.cli mail repair-plan
```

The storm gate separates ordinary git worktree dirt, source-outbox retries,
tracked Rust reference-snapshot churn, and true mailbox authority blockers.
If a reviewed repair regenerates staged Rust rollout packets while packet dirt
is still present, pass both a human reason and the current
`dirty_state_fingerprint` shown by `mail storm-gate` or `mail doctor`:

```bash
python -m digital_asset_directory.cli rust-rollout build-mail \
  --dirty-state-ack "reviewed Rust rollout packet resync" \
  --dirty-state-fingerprint "<fingerprint-from-storm-gate-or-doctor>"
```

DAD need route: `dad:need:rust-rollout-feedback`.

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

When known, include `applies_when`, `does_not_apply_when`, and
`danger_if_misapplied` so future agents do not turn a local Rust fix into a
false universal rule.

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
