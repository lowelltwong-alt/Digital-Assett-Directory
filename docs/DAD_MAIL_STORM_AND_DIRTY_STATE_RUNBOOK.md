# DAD Mail Storm And Dirty State Runbook

Status: operator runbook for concurrent repo mail, Rust rollout packet churn,
and "very dirty" DAD states.

Use this when multiple repos or branches are sending Rust lessons, learning-loop
packets, exception candidates, or rollout feedback to DAD at the same time.

## First Command

From the DAD repo:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli mail storm-gate
```

`storm-gate` defaults to `--repo all`, checks reviewed `mail.repos`, checks
mailbox coverage, and returns one compact go/no-go verdict. It is read-only and
does not collect, route, deliver, repair, or promote Rust rollout snapshots.
When a reviewed repair needs to regenerate staged Rust packet evidence while
allowed Rust packet dirt is still present, copy the reported
`dirty_state_fingerprint`. The later bypass must match that exact fingerprint,
so new mail appended by other repos cannot ride on an old review.

For automation that only collects and routes mail into the central queue, use:

```powershell
python -m digital_asset_directory.cli mail storm-gate --operation ingest
python -m digital_asset_directory.cli mail ingest
```

For automation that writes repo inboxes, use the default all-operations gate or
an explicit delivery gate:

```powershell
python -m digital_asset_directory.cli mail storm-gate --operation delivery
```

This distinction matters when protected repos block delivery while the source
outbox and central routing path remain clean.

`mail ingest` is the preferred receive path during a Rust rollout or learning
storm. It defaults to reviewed `mail.repos`, collects source repo
`.digital-asset/mail/outbox.jsonl` rows into DAD, routes central candidates, and
does not write any target repo inbox. Delivery remains a separate
policy-gated command.

If the storm gate blocks, or if you need full issue/observation detail, run:

```powershell
python -m digital_asset_directory.cli mail repair-plan
```

`repair-plan` is the read-only bridge between "blocked" and "what next." It
groups the current dirty state into ordered repair lanes, repeats whether
collect/route/deliver are safe, and labels which steps require operator review.
It does not repair stale locks, quarantine rows, allowlist legacy evidence,
promote Rust snapshots, or write to repo inboxes.

The `review_queue` inside the repair plan is sanitized operator evidence. It
includes row identities and hashes for review, but it does not copy raw payloads
and does not approve direct inbox edits.

When multiple repos are reporting Rust or learning-loop mail and you need a
durable handoff packet for another agent or human reviewer, add:

```powershell
python -m digital_asset_directory.cli mail repair-plan --write-report
```

This writes JSON and Markdown under:

```text
processed/reports/mail_storm_repair/
```

Each write keeps the timestamped packet and also refreshes:

```text
processed/reports/mail_storm_repair/latest.json
processed/reports/mail_storm_repair/latest.md
```

Use the timestamped file for audit history and `latest.*` as the stable operator
handoff pointer during an active storm. The stable pointer is still DAD-local
evidence only; it does not approve any repair or repo write.

The report write is DAD-local operator evidence only. It does not make the dirty
state safe, does not approve repair, and does not authorize collect, route,
deliver, public release, tracked Rust snapshot promotion, or target-repo writes.

For full doctor detail, run:

```powershell
python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap
```

If you only need the hub-local mailbox and staged Rust packets, omit
`--repo all`. During a real multi-repo mail storm, prefer `--repo all` so DAD
checks reviewed repo outboxes and inboxes from `mail.repos`.

For a fast Rust leaf probe of the hub-local mail roots, run:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli rust mail-spool-check
```

This probe is read-only and alias-only. It can help spot lock/temp debris,
malformed JSONL, oversized rows, and Rust rollout packet churn quickly, but
`mail doctor` remains the authoritative collect/route/deliver gate.

## Read The Result

`dirty` and `spool_dirty` answer whether the mailbox/staged-packet system has a
blocking problem.

`worktree_dirty` answers whether the DAD git tree has uncommitted files. That is
important for pushing or merging, but it is not proof that mail is corrupt.

Use `action_summary.safe_to_collect`, `safe_to_route`, and `safe_to_deliver` for
mail operations. Use `--fail-on-worktree-dirty` only for scripts that truly
require a clean git tree.

For `mail storm-gate`, read the operation-specific gates first:

- `safe_for_ingest_operations` controls collection and routing.
- `safe_for_delivery_operations` controls writes to repo inboxes.
- `safe_for_mail_storm_operations` is the all-operations gate and is false when
  either ingest or delivery is blocked.

A `gate_status` of `mail_safe_worktree_dirty` means mail can move under policy,
but push/merge still needs ordinary git review. A `gate_status` starting with
`blocked_` means do not collect, route, or deliver until the issue is classified
or repaired.

`mail_safe_delivery_policy_hold` means the mailbox/storm scope is structurally
clean, but at least one selected repo is write-protected or delivery-disallowed
by reviewed `mail.repos` policy. Collection/routing can still be safe for the
selected scope, but delivery is not approved. Narrow the repo scope or change
policy only after repo-specific human review. `mail deliver --repo all` fails
closed on this hold instead of silently delivering to only the writable subset;
use explicit repo targets for narrowed delivery.

When `--repo all` is used, also read `mailbox_coverage`. It is read-only
coverage evidence from bounded mailbox discovery. If it reports unreviewed
mailbox candidates, DAD has found repo-local mailboxes outside reviewed
`mail.repos` policy. That does not make the spool dirty and it does not
authorize collection, but it means "all reviewed repos" is not the same as "all
mailboxes that currently exist." `mail collect --repo all` and
`mail deliver --repo all` fail closed on that condition unless an operator gives
a named `--allow-coverage-gap-ack`.

## Write Targets

Repo agents write only to their own:

```text
.digital-asset/mail/outbox.jsonl
```

DAD collection writes:

```text
processed/mail/inbox/*.jsonl
processed/mail/archive/collection_log.jsonl
```

DAD routing writes:

```text
processed/mail/outbox/routed.jsonl
```

DAD delivery writes target repo inboxes:

```text
.digital-asset/mail/inbox.jsonl
```

If a repo agent writes directly to DAD central inbox or any repo inbox, treat it
as a wrong-box write until DAD collection or delivery creates matching audit
evidence.

## DAD Inbound Address Rule

Messages "to DAD" still start in the source repo's own outbox:

```text
<source repo>/.digital-asset/mail/outbox.jsonl
```

Use `target_repo: "central_only"` when the message should be held by DAD for
review instead of delivered to another repo. Do not write directly to:

```text
Digital-Assett-Directory/.digital-asset/mail/inbox.jsonl
Digital-Assett-Directory/processed/mail/inbox/*.jsonl
<target repo>/.digital-asset/mail/inbox.jsonl
```

If `asset-dir` or the DAD Python module is not available in the source repo,
the fallback is a metadata-only source-outbox row with a `dad_cli_unavailable`
note and the attempted command. That row is still candidate mail. It should not
contain raw logs, secrets, private rows, copied source blobs, or hidden
reasoning. DAD collection later adds collection audit, dedupes retries, and
routes the candidate through the normal central flow.

`central_only` means central DAD queue/hold, not DAD repo-local inbox delivery.
DAD's own `.digital-asset/mail/inbox.jsonl` requires delivery evidence targeted
to `dad` or `repo:dad`, not a generic central-only log row.

Old pre-enforcement repo inbox rows may have only legacy delivery-log evidence
without a row hash. Do not edit the inbox to make those rows look clean. After
reviewing the current row, use:

```powershell
python -m digital_asset_directory.cli mail doctor --repo <repo> `
  --allowlist-legacy-repo-inbox `
  --legacy-allowlist-ack "reviewed pre-enforcement repo inbox row"
```

That writes DAD-local audit rows to:

```text
processed/mail/archive/legacy_delivery_allowlist.jsonl
```

The allowlist is keyed by `mail_id`, `dedupe_key`, the current inbox row hash,
and the target repo. If the row changes later, the doctor blocks again. This is
a migration record only; it does not approve adoption, public release, future
direct inbox writes, or target-repo source changes.

Valid JSON rows in a source repo outbox can still fail the DAD mail schema. Do
not delete, rewrite, or manually promote those rows during a storm. After
reviewing the metadata-only issue record from `mail doctor`, quarantine the
current path/hash:

```powershell
python -m digital_asset_directory.cli mail doctor --repo <repo> `
  --quarantine-invalid-packets `
  --invalid-quarantine-ack "reviewed invalid source-outbox row"
```

That writes DAD-local audit rows to:

```text
processed/mail/quarantine/invalid_mail_packet.jsonl
```

The quarantine is keyed by mailbox path and row hash and never copies raw
payload content. If the source row changes later, the doctor blocks again. This
quarantine only lets DAD continue processing other well-formed mail; the source
repo should still fix or replay the bad candidate through its own outbox.

## What Blocks

Pause collect, route, and deliver when doctor reports:

- malformed JSONL or oversized rows;
- active locks or stale locks that have not been repaired;
- atomic temp fragments from interrupted writes;
- central inbox rows without collection provenance or collection audit;
- repo inbox rows without delivery-log evidence;
- valid JSON rows that fail the DAD mail schema and have not been quarantined
  by current source-outbox path/hash;
- duplicate packet identities in the same central/routed/delivered lifecycle
  stage;
- matching packet identities from different reviewed source repo IDs;
- duplicate source-outbox rows from unknown source identities until the source
  worktree is classified as reviewed, duplicate, archive, temp, or protected;
- invalid Rust rollout packets, delivery-status drift, write claims, or
  duplicate Rust rollout packet identities.

Repair only stale/dead locks or stale temp fragments with explicit repair flags.
Quarantine malformed or oversized rows by hash and metadata only; do not copy
private payloads into a fix note.

## What Does Not Block By Itself

These are observations or normal worktree chores, not mail corruption:

- duplicate rows in a source repo's own outbox from agent retries;
- source-outbox rows already quarantined by current path/hash, as long as the
  quarantine is metadata-only and the row is not in a central inbox, central
  outbox, or repo inbox;
- backup or repair files inside `.digital-asset/mail/` whose names are not
  `inbox.jsonl`, `outbox.jsonl`, `archive.jsonl`, or `adoption.jsonl`; move
  them outside the live mailbox or rename them without a `.jsonl` suffix;
- duplicate source-outbox rows from the same reviewed source identity
  worktrees, when they do not claim different reviewed repo IDs;
- the same packet identity appearing across lifecycle stages;
- ordinary source, docs, registry, or test changes in the DAD git worktree;
- tracked `mail/outbox/rust_rollout/` reference-snapshot churn when the mail
  spool itself is clean.

Source-outbox duplicate storms should be collected once. DAD records
`duplicate_seen` audit evidence so retries do not spam central inboxes.
If reviewed policy says two different source repo IDs emitted the same packet
identity, treat it as a provenance conflict rather than a retry.

## Rust Rollout Packets

Routine Rust rollout packet generation belongs under ignored staging:

```text
processed/mail/staged/rust_rollout/
```

The tracked snapshot is:

```text
mail/outbox/rust_rollout/
```

`asset-dir rust-rollout build-mail --out-dir` is path-gated. In-repo output is
limited to ignored staging or the tracked reference snapshot with the explicit
promotion acknowledgement. Off-repo output is allowed only under the system temp
directory for ad hoc review; arbitrary absolute paths are blocked because they
may be another repo's mailbox or source tree.

Treat the tracked snapshot as review evidence, not live delivery. Writing there
requires:

```powershell
python -m digital_asset_directory.cli rust-rollout build-mail `
  --out-dir mail/outbox/rust_rollout `
  --promote-reference-snapshot-ack "<reviewed reason>"
```

Regenerating staged Rust packets during a dirty-spool repair requires
`--dirty-state-ack` plus the current `--dirty-state-fingerprint` from
`mail storm-gate` or `mail doctor`, and that bypass is logged. It does not
permit normal mail collect, route, or deliver to ignore dirty-spool blockers.

```powershell
python -m digital_asset_directory.cli rust-rollout build-mail `
  --out-dir processed/mail/staged/rust_rollout `
  --dirty-state-ack "reviewed Rust rollout packet resync" `
  --dirty-state-fingerprint "<fingerprint-from-storm-gate-or-doctor>"
```

If the fingerprint changed, rerun the storm gate and review the new issue set
before regenerating packets.

Intentional promotion of the tracked reference snapshot writes a metadata-only
audit row to:

```text
processed/mail/archive/rust_rollout_snapshot_promotion.jsonl
```

That audit row records the acknowledgement, packet count, and per-packet hashes.
It is promotion evidence only; it is not inbox delivery, public release approval,
target repo adoption, or permission for other branches to write live traffic
under `mail/outbox/rust_rollout/`.

A matching pair of one ignored staging packet and one tracked reference snapshot
for the same Rust rollout semantic identity is comparison evidence, not a dirty
mail blocker, only when there is no revision disagreement and no stable-content
hash disagreement. Multiple active packets in the same class, differing revision
IDs or stable content hashes for the same semantic identity, invalid packet JSON,
delivery-status claims other than `staged_not_deliverable`, or any write claim
remain blockers.

## Escalation

If doctor reports `blocked` or `dirty_needs_review`, do not push mail forward.
Create an exception candidate with safe metadata:

- issue type and doctor status;
- affected path class, not raw private contents;
- hashes for malformed rows or blocked payloads;
- repo alias or `repo-path-sha256`, not public local paths;
- command attempted and exit code;
- whether the fix was stale-lock repair, re-collect, quarantine, dedupe, or
  tracked snapshot regeneration.

If doctor reports `dirty=false` and `worktree_dirty=true`, handle the dirty git
tree with normal code review, tests, and commit discipline. Mail can continue
when policy allows.

## Coverage Gap Repair

`--repo all` means all reviewed `mail.repos`, not every mailbox folder on disk.
During Rust rollout or cross-repo learning storms, run strict coverage before
pickup or delivery:

```powershell
python -m digital_asset_directory.cli mail collect --repo all
python -m digital_asset_directory.cli mail deliver --repo all
```

If either command reports `dad_mailbox_coverage_gate.v1`, do not loosen
discovery. Classify each unreviewed mailbox as one of:

- persistent repo to add to reviewed `mail.repos`;
- protected repo that should stay central-only or write-protected;
- archive/temp/duplicate clone to ignore;
- unknown repo needing human classification.

After adding a reviewed policy row, rerun doctor with
`--repo all --summary-only --fail-on-coverage-gap`. Only then collect. When a
human intentionally wants to collect only already reviewed repos while leaving a
known unreviewed mailbox untouched, use:

```powershell
python -m digital_asset_directory.cli mail collect --repo all --allow-coverage-gap-ack "<reviewed reason>"
```

The acknowledgement is logged and does not enroll, collect from, or deliver to
the unreviewed mailbox. This keeps newly created repo outboxes from being
silently skipped while preserving the rule that DAD does not collect from
arbitrary discovered folders.

Coverage samples use safe path hashes by default. Add `--include-local-paths`
only for local debugging output that will not be pasted into public-facing mail
or review packets.
