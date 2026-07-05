# Manual Runbook

1. Confirm the target repo is in reviewed DAD policy.
2. Confirm broad writes have an approval ID and path allowlist.
3. Confirm recurring operation writes only `.digital-asset/mail/**`.
4. Confirm protected repos are central-only unless explicit local-write approval exists.
5. Confirm generated reports are candidate evidence, not enrollment permission.
6. During a multi-repo mail or Rust rollout storm, run
   `python -m digital_asset_directory.cli mail storm-gate`.
7. Confirm `safe_for_ingest_operations`, `safe_for_delivery_operations`,
   `safe_for_mail_storm_operations`, `safe_to_collect`, `safe_to_route`, and
   `safe_to_deliver` before moving mail. If ingest or delivery blocks, run
   `python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap`.
   Collector/router automation may use `mail storm-gate --operation ingest`;
   delivery automation must use `--operation delivery` or the default all gate.
8. Confirm `worktree_dirty` is treated separately from `spool_dirty`.
9. Confirm same-source outbox retries are observations, while cross-source
   packet identity conflicts block until provenance review.

This runbook is a safety check for rollout, not an enrollment approval.
