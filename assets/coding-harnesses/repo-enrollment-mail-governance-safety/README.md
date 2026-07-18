# Repo Enrollment Mail Governance Safety

Candidate harness for checking DAD enrollment waves, mailbox-only recurring
operation, protected repo gates, public-release holds, and approval IDs.

Before apply, compare the implementation's actual write set with the plan's
approved DAD-managed paths. Repo-local exception and fix-outcome paths may be
reported for orientation but must not be created or normalized by enrollment.

Use the mail-spool integrity cases when multiple repos or branches may be
writing Rust rollout lessons, DAD mail, or learning-loop packets at the same
time. The harness separates true mailbox hazards from ordinary dirty git
worktrees:

- true mailbox hazards: malformed JSONL, active/stale locks, wrong-box central
  inbox rows, repo inbox rows without delivery logs, missing fresh collection
  audit, oversized rows, same-stage duplicate identities, or invalid Rust
  rollout packets;
- worktree telemetry: ordinary source/docs/registry changes and tracked
  `mail/outbox/rust_rollout/` reference-snapshot churn.

During a mail storm, duplicate rows in a source repo's own outbox are
backpressure observations. They should not block collection by themselves; DAD
canonicalizes one central row and records `duplicate_seen` audit evidence.
If reviewed `mail.repos` policy says the same source-outbox packet identity
came from different repo IDs, treat it as a provenance conflict instead of a
retry. Duplicates in central, routed, delivered, or tracked Rust snapshot stages
still block.

Rust rollout feedback follows the same rule: source repos append lessons or
feedback to their own `.digital-asset/mail/outbox.jsonl`. DAD central inbox rows
are collection-owned, and DAD central routed outbox rows are route-owned. Direct
writes to `processed/mail/inbox/*.jsonl` or `processed/mail/outbox/routed.jsonl`
are wrong-box writes unless matching collection or route audit evidence exists.

The `mail_storm_dirty_state_classifier` sub-harness separates:

- mailbox corruption: malformed rows, locks, oversized rows, wrong-box writes,
  missing collection/route/delivery audit, or provenance conflicts;
- tracked Rust reference snapshot churn: reviewed `mail/outbox/rust_rollout/`
  evidence, never live delivery;
- ignored staging churn: generated `processed/mail/staged/rust_rollout/`
  packets;
- ordinary DAD worktree dirt: source, docs, registry, roadmap, asset, or
  generated-evidence changes that need normal code review.

Backdated central inbox rows are not trusted from packet contents alone. They
must either have a collection audit row or a separate reviewed legacy allowlist
entry keyed by `mail_id`, `dedupe_key`, and record hash.

Valid JSON source-outbox rows that fail the DAD mail schema stay untrusted. A
storm repair may quarantine the current row by mailbox path and hash with
`mail doctor --quarantine-invalid-packets --invalid-quarantine-ack "<reason>"`.
That creates DAD-local metadata-only quarantine evidence, does not copy raw
payloads, does not delete or edit the source outbox, and does not authorize
delivery. If the source row changes, the gate blocks again.

Run `mail storm-gate` before collect, route, deliver, or Rust rollout packet
regeneration during a real multi-repo storm. It defaults to reviewed
`mail.repos` coverage and returns one compact `gate_status`. Use
`safe_for_ingest_operations`, `safe_for_delivery_operations`,
`safe_for_mail_storm_operations`, `safe_to_collect`, `safe_to_route`, and
`safe_to_deliver` as the first go/no-go answer. Run
`mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap`
when the gate blocks or you need full diagnostics. Use
`--fail-on-worktree-dirty` only when a specific script requires a clean DAD git
tree.

For collect/route automation that should continue during a protected-repo
delivery hold, run `mail storm-gate --operation ingest`. Use
`mail storm-gate --operation delivery` or the default all-operations gate
before writing target repo inboxes.

When a reviewed Rust packet repair intentionally bypasses allowed packet dirt,
the bypass must include both `--dirty-state-ack` and the current
`--dirty-state-fingerprint` from `mail storm-gate` or `mail doctor`. If the
fingerprint changes, the reviewed dirty state changed; rerun the gate before
regenerating packets.
