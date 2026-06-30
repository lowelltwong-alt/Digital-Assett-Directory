# DAD Mail Center

Status: governed candidate-message channel for sharing lessons, assets,
workflows, taxonomy ideas, capability updates, and governance notices across
repos.

DAD is the central mail hub. Persistent repos may keep a lightweight local
mirror under `.digital-asset/mail/`. The mirror is intentionally small: JSONL
files plus a README. A repo does not need to vendor DAD's Python test suite just
to receive or send suggestions.

## Authority Boundary

Mail packets are append-only candidate evidence. They are not source truth,
instructions, or approval to mutate a target repo.

Mail must not overwrite:

- `AGENTS.md`, `CLAUDE.md`, Cursor rules, AI front doors, or local governance;
- registries, schemas, source code, hooks, CI, migrations, or roadmap gates;
- secrets, credentials, private rows, or large raw file contents.

Cross-repo delivery writes only to `.digital-asset/mail/` in repos explicitly
allowed by the command or DAD config. If a target is missing, read-only, not in
the allowlist, or marked `central_only`, DAD keeps the packet centrally.

## Packet Types

The mail message schema supports:

- `lesson_suggestion`
- `asset_suggestion`
- `workflow_suggestion`
- `taxonomy_suggestion`
- `capability_suggestion`
- `governance_notice`
- `inbox_ack`
- `review_decision`

Core fields are `mail_id`, `thread_id`, `message_type`, `source_repo`,
`target_repo`, `created_at`, `dedupe_key`, `sensitivity`, `review_status`,
`payload`, `evidence`, and `suggested_actions`.

Schemas:

```text
schemas/mail-message.schema.json
schemas/mail-decision.schema.json
```

## Storage

Central DAD storage:

```text
processed/mail/inbox/*.jsonl
processed/mail/outbox/*.jsonl
processed/mail/archive/*.jsonl
processed/reports/mail_center.md
processed/reports/mail_center.json
```

Repo-local mirror:

```text
.digital-asset/mail/inbox.jsonl
.digital-asset/mail/outbox.jsonl
.digital-asset/mail/archive.jsonl
.digital-asset/mail/README.md
.digital-asset/mail/last_checked.json
```

## Commands

Compose a repo-local outbox packet:

```powershell
python -m digital_asset_directory.cli mail compose `
  --repo C:\path\to\repo `
  --type lesson_suggestion `
  --target-repo central_only `
  --summary "Use daily mail digest before adopting cross-repo suggestions."
```

Collect repo outboxes into DAD:

```powershell
python -m digital_asset_directory.cli mail collect --repo C:\path\to\repo
python -m digital_asset_directory.cli mail collect --repo all
```

Route and deliver:

```powershell
python -m digital_asset_directory.cli mail route
python -m digital_asset_directory.cli mail deliver --repo C:\path\to\target
python -m digital_asset_directory.cli mail deliver --repo all
```

Review locally:

```powershell
python -m digital_asset_directory.cli mail digest --repo C:\path\to\target
python -m digital_asset_directory.cli mail review `
  --repo C:\path\to\target `
  --mail-id dad:mail:... `
  --decision accept `
  --decided-by human
```

Review decisions are append-only. Accepted mail still requires a normal local
change, local tests, preflight/postflight, and any repo-specific human gates.

## Daily Check Model

DAD runs the central daily collection, routing, and delivery job. Repos do not
collect mail on every preflight.

Preflight only reads `.digital-asset/mail/last_checked.json`. If the digest is
missing, invalid, in the future, or older than 24 hours, preflight surfaces a
stale mail-digest warning. The fix is to run:

```powershell
python -m digital_asset_directory.cli mail digest --repo C:\path\to\repo
```

## Deduplication

DAD deduplicates by canonical `mail_id` plus `dedupe_key`. On collection, DAD
does not trust hand-written packet IDs. It revalidates the packet, rewrites the
source repo to the actual outbox owner, redacts secret-like text, rejects
disallowed sensitivity, and recomputes canonical identity. Duplicate delivery
creates an `inbox_ack` archive record instead of a second inbox suggestion.

## Sensitivity

Mail may carry metadata, paths, summaries, hashes, and review notes. It must not
carry secrets, credentials, raw private rows, or large raw file contents.

Transport rejects `confidential`, `restricted`, and `unknown` sensitivity. Use
public-safe summaries and point to local evidence that the target repo can review
under its own authority.

## Taxonomy Inbox

Existing taxonomy recommendation inbox notes are candidate inputs for
`taxonomy_suggestion` mail. Fold them into mail packets or mail-center docs after
review; do not stage standalone recommendation inbox files as authority unless a
separate governance change approves them.
