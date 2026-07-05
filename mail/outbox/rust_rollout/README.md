# DAD Rust Rollout Mail

Deterministic local instruction packets only. These files do not send external
email, mutate target repos, open GitHub PRs, authorize source changes, or clear
public/private release gates.

Every packet in this folder is staged candidate evidence with
`delivery_status=staged_not_deliverable`,
`requires_target_policy_review=true`, and
`public_release_status=pending_human` until the target repo visibility and local
policy are reviewed.

Logos repos are instruction-mail-only.

During concurrent Rust rollout work, run DAD's dirty-spool diagnostic before
collecting, routing, or delivering mail:

```powershell
python -m digital_asset_directory.cli mail storm-gate
python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap
python -m digital_asset_directory.cli rust mail-spool-check
```

`mail storm-gate` is the first compact go/no-go answer for concurrent repo
mail. `mail doctor` separates mailbox/staged-packet dirt from ordinary DAD git
worktree dirt. If it reports `dirty=false` and `worktree_dirty=true`, mail
collection/routing is not blocked by that fact alone; review the worktree with
`git status` and use `--fail-on-worktree-dirty` only for scripts that require a
clean DAD tree.

Use `safe_for_mail_storm_operations`, `safe_to_collect`, `safe_to_route`, and
`safe_to_deliver` for mail operations during a real multi-repo storm. A clean
Rust structural probe is evidence only; it does not replace the all-repo
`mail storm-gate` gate.

Repo agents should write Rust lessons or rollout feedback to their own
`.digital-asset/mail/outbox.jsonl`. Do not write directly to DAD's
`processed/mail/inbox/*.jsonl` or a target repo's `.digital-asset/mail/inbox.jsonl`;
DAD collection and delivery create those rows and the matching audit logs.

Routine `asset-dir rust-rollout build-mail` output goes to ignored staging under
`processed/mail/staged/rust_rollout/` by default. The tracked
`mail/outbox/rust_rollout/` folder is a reference snapshot for review, not the
write target every branch should churn.
