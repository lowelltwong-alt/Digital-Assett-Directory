# Tests Or Evals

Evals should include write-protected Logos repos, dirty worktrees, non-main
branches, ambiguous repo names, public/private mail gates, and mail-spool
integrity during concurrent Rust rollout work.

Mail-spool integrity means:

- wrong-box central inbox or repo inbox writes block collect/route/deliver;
- malformed JSONL, oversized rows, active locks, stale locks, temp fragments,
  missing fresh collection audit, and same-stage duplicates are diagnosed;
- valid Rust rollout packets remain staged candidate evidence, not delivered
  inbox mail;
- ordinary DAD git worktree dirt is reported as `worktree_dirty`, not as
  mailbox corruption;
- multi-repo storm checks use `mail storm-gate` first and the
  `safe_for_ingest_operations`, `safe_for_delivery_operations`,
  `safe_for_mail_storm_operations`, `safe_to_collect`, `safe_to_route`, and
  `safe_to_deliver` fields;
- blocked storm gates use
  `mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap`
  for full diagnostics;
- same-source outbox retries are observations, but same packet identities from
  different reviewed repo IDs block as provenance conflicts.
