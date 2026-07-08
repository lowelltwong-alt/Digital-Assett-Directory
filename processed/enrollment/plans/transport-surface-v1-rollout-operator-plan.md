# Transport Surface v1 Rollout Operator Plan

Generated for DAD transport surface `1.0.0` and implementation bundle `1.0.0-m0m1m2`.

This is an operator handoff for notifying enrolled repos about the new local-pull transport architecture. It is candidate control-plane metadata only: it does not approve downstream writes, protected repo fixes, public release, data-root migration, daemon installation, or journal pushes.

## Scope

- Upgrade plan: `processed/enrollment/plans/update-transport-surface-v1.json`
- Human-readable queue: `processed/enrollment/plans/update-transport-surface-v1.md`
- Live version report: `processed/reports/transport_version_status.json`
- Live transport audit: `processed/reports/transport_audit.json`
- Upgrade queue: `processed/mail/staged/transport-upgrade-queue.jsonl`

Current rollout target count: 9 repos.

Current live status:

- 8 repos are `upgrade_recommended`.
- 1 repo is `upgrade_required`.
- 1 protected repo, `logos-scripture-graph`, has tracked mailbox JSONL and must stay central-only until explicit local-write approval exists.
- `logos-governance-architecture` has no DAD surface and is not part of this update wave.

## Required Downstream Contract Block

Each upgraded repo must carry:

```json
"transport": {
  "surface_version": "1.0.0",
  "implementation_version": "1.0.0-m0m1m2",
  "mode": "local_pull",
  "journal_fallback": true
}
```

`surface_version` tracks the repo-facing contract shape. `implementation_version` tracks the DAD implementation bundle so future repos can be upgraded by exact version, not vibes.

## Notification And Adoption Flow

1. Land the DAD transport implementation cleanly first.
2. Refresh central evidence with `asset-dir transport audit`, `asset-dir transport version-status`, and `asset-dir transport upgrade-plan --wave transport-surface-v1`.
3. Review holds before any downstream write.
4. Notify repos through reviewed enrollment update waves.
5. Verify adoption by rerunning `asset-dir transport version-status`.
6. Capture repo-specific failures as candidate lessons through local outboxes or DAD postflight.

## Stop Conditions

- Stop before any protected repo local write without explicit local-write approval.
- Stop if a target repo has unreviewed dirty worktree changes.
- Stop if schema compatibility would break existing contracts.
- Stop if public-facing repos would receive private, internal, restricted, or unknown-origin payloads without release evidence.
- Stop if Cloudflare relay work becomes necessary; M3 remains design-only until the Cloudflare human gate is satisfied.

