# Phase 13 Transport Upgrade Wave Evidence

Reviewed: 2026-07-11

Reviewer: Lowell

Approvals:

- Read-only LLOS rollout: `USER-2026-07-11-LOGOS-LLOS-READONLY-ROLLOUT`
- One-time Scripture transport rollout: `USER-2026-07-11-LOGOS-SCRIPTURE-TRANSPORT`

## Decision

The Phase 13 repository transport upgrade wave is approved and verified. Lowell
approved gates 1, 2, 3, and 5, then explicitly approved the one-time Logos
rollout. The continuing authority boundary is asymmetric: Logos repositories
may write candidate communication to DAD and read candidate communication from
DAD, while recurring DAD operation may only read reviewed Logos metadata and
outboxes and write central DAD data-root state. DAD has no standing authority to
write any Logos file. A future Logos write requires new explicit approval.

## Acceptance Evidence

- DAD PR #40 merged the read-only Logos LLOS bridge.
- DAD PR #41 merged central control mirrors and fail-closed LLOS path checks.
- logos-scripture-graph PR #176 moved the tracked mail spool byte-for-byte to a
  hashed test fixture, installed transport contract `1.0.0` with implementation
  `1.0.0-m0m1m2`, and left the runtime spool untracked.
- DAD PR #42 separated transport audit roots from live repository roots and
  added linked-worktree-aware, content-sensitive audit fingerprints.
- `processed/reports/transport_audit.json`, generated at
  `2026-07-11T22:41:42.436901+00:00`, reports 12 reviewed repositories: 9
  `current`, 3 protected Logos repositories intentionally classified
  `no_dad_surface`, and no repository requiring a transport upgrade.
- `processed/reports/logos_llos_audit.json`, generated at
  `2026-07-11T22:41:37.500682+00:00`, reports all 4 Logos LLOS surfaces
  `current`, `upgrade_required_count: 0`, and `source_write_count: 0`.
- A production-shaped daemon cycle completed with daemon status `complete`,
  journal status `ok`, and no pending journal checkpoint. The persisted cycle
  evidence is
  `C:/Users/lowel/.dad/data/processed/reports/daemon-heartbeat.json`; its cycle
  completed at `2026-07-11T22:45:50.176055+00:00` with
  `logos_llos_current_count: 4`, `journal_checkpoint_applied: true`, and
  `journal_checkpoint_due: false`. The separately persisted Logos audit proves
  the read-only auditor's `source_write_count: 0`; no broader source-mutation
  claim is inferred from the heartbeat.
- `asset-dir transport upgrade-status --hub .` returned
  `no_current_upgrade_rows` at `2026-07-11T22:52:34.260395+00:00`, with 26
  historical rows, 9 effective rows, `selected_count: 0`, and all 9 effective
  rows skipped as `superseded_by_current_audit`. Its inputs are the persisted
  transport audit and
  `C:/Users/lowel/.dad/data/processed/mail/staged/transport-upgrade-queue.jsonl`.
- Windows Task Scheduler task `DAD Daemon Run Cycle` is installed and `Ready`.
- The private data-only journal is clean and synchronized at commit
  `1cc50b663697450f3847a62c145d4f4ca942c867` (`Checkpoint DAD data root`).
- Full DAD validation passed after the final transport-audit patch, including
  the Python suite, CLI validation, roadmap check, and GitHub CI. The Scripture
  rollout passed `972` tests with `25` skips plus its repository validators and
  GitHub CI. DAD PR #42 checks are GitHub Actions runs `29170823507` and
  `29170824984`; Scripture PR #176 is run `29169942547`. The exact local test
  counts are recorded in the corresponding DAD postflights
  `dad:handoff:a5fa7db2-e4aa-54af-b2ae-e13796506a3b` and
  `dad:handoff:c6f5b5b1-eb45-5109-b9fb-1e715b2a8b65`.

## Authority And Scope

The three protected Logos repositories without DAD transport surfaces use the
central read-only LLOS mirror path by design. `logos-scripture-graph` has the
versioned local transport contract needed for candidate communication. No
protected repository receives silent enrollment, delivery, untracking, or
source mutation. Candidate mail remains candidate evidence and local source
authority is unchanged.

Cloudflare Worker+D1 relay work remains design-only and is not part of this
completion. It remains deferred until `phase-10a-cloud-boundary-reviewed`.

## Risk Review

Risk tier: medium. Most of this change records already-approved deployment
evidence, but it also corrects roadmap acceptance so `required_outputs` resolve
through the fail-safe data plane while `required_files` remain Git-relative.
It does not change transport writes, source authority, schema meaning, or gate
meaning. A configured but uninitialized or wrong-hub data root still falls back
to the legacy checkout. Rollback is a normal revert of this commit. The
principal failure modes are weakening the fail-safe resolver or overstating
deployment completeness; initialized-root, uninitialized-root, and
wrong-hub-root tests plus deterministic audit counts, source-write counters,
merged PRs, scheduler state, journal state, and independent fresh-eyes review
guard those claims.
