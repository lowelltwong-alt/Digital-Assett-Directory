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

Cross-repo delivery writes only to `.digital-asset/mail/` in repos covered by
reviewed DAD `mail.repos` policy. If a target is missing, read-only, lacks
reviewed target policy, ambiguous, or marked `central_only`, DAD keeps the
packet centrally.

Private, internal, restricted, and unknown source origins are not presumed safe
for public-facing repositories. If a target repo is marked `public_facing: true`
in reviewed mail policy, mail from those origins is held in central quarantine
until `asset-dir mail release` records explicit human approval. Agent-authored
mail review decisions are triage only and never satisfy public release.

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
`payload`, `evidence`, `suggested_actions`, `source_provenance`, and
`public_release`.

`source_provenance` records the canonical source repo, reviewed visibility,
original source chain, return address, and compose/collect timestamps.
`public_release` records the target visibility, whether a public release gate is
required, release status, human release ID, and release reason.

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
processed/mail/quarantine/*.jsonl
processed/mail/releases/*.jsonl
processed/reports/mail_center.md
processed/reports/mail_center.json
```

Repo-local mirror:

```text
.digital-asset/mail/inbox.jsonl
.digital-asset/mail/outbox.jsonl
.digital-asset/mail/archive.jsonl
.digital-asset/mail/README.md
.digital-asset/mail/.gitignore
.digital-asset/mail/last_checked.json
```

Mailbox JSONL and `last_checked.json` are local operational state by default.
The mailbox `.gitignore` keeps them out of normal commits. Do not commit them to
a public-facing repo unless a human has reviewed packet provenance and public
release status.

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
python -m digital_asset_directory.cli mail discover-repos
```

`--repo all` uses only reviewed `mail.repos` config entries. `discover-repos`
is read-only and reports mailbox candidates; it does not authorize delivery.

Route and deliver:

```powershell
python -m digital_asset_directory.cli mail route
python -m digital_asset_directory.cli mail deliver --repo C:\path\to\target
python -m digital_asset_directory.cli mail deliver --repo all
```

`mail deliver` requires reviewed target policy even for explicit `--repo` paths.
Add the repo to `mail.repos` before delivery so DAD knows the target visibility
and whether it is public-facing.

Release a held private/internal/restricted/unknown-origin packet to a
public-facing target only after human review:

```powershell
python -m digital_asset_directory.cli mail release `
  --mail-id dad:mail:... `
  --decision approve `
  --human-reviewed-by Lowell `
  --notes "Checked provenance, payload, license, and public-safe summary."
```

Review locally:

```powershell
python -m digital_asset_directory.cli mail digest --repo C:\path\to\target
python -m digital_asset_directory.cli mail review `
  --repo C:\path\to\target `
  --mail-id dad:mail:... `
  --decision accept `
  --decided-by human `
  --human-reviewed
```

Review decisions are append-only. Without `--human-reviewed`, a review is agent
triage and does not mark the message handled for local digest purposes. Accepted
mail still requires a normal local change, local tests, preflight/postflight,
and any repo-specific human gates.

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
source repo to the actual outbox owner, applies best-effort credential/PII
screening, rejects disallowed sensitivity, downgrades unreviewed source
visibility claims to `unknown`, and recomputes canonical identity. Duplicate
delivery creates an `inbox_ack` archive record instead of a second inbox
suggestion.

## Sensitivity

Mail may carry metadata, paths, summaries, hashes, and review notes. It must not
carry secrets, credentials, raw private rows, copied prompt/code blobs, or large
raw file contents.

Transport rejects `confidential`, `restricted`, and `unknown` sensitivity. DAD
performs best-effort credential/PII screening for common tokens, keys, emails,
phones, SSN-like values, database URLs, and private-key blocks. A screening
count is not proof of safety. Public-facing delivery also rejects unknown payload
keys, long free-form values, table-like rows, and packets that needed screening.
Use public-safe summaries and point to local evidence that the target repo can
review under its own authority.

## Taxonomy Inbox

Existing taxonomy recommendation inbox notes are candidate inputs for
`taxonomy_suggestion` mail. Fold them into mail packets or mail-center docs after
review; do not stage standalone recommendation inbox files as authority unless a
separate governance change approves them.
