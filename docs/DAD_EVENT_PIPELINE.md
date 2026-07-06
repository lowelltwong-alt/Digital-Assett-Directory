# DAD Event Pipeline

Status: initial local-first event/data pipeline contract.

The event pipeline is the candidate state layer beneath DAD mail. Repos still
use mailboxes for human-readable suggestions, but durable response tracking and
learning-loop signals should move through short metadata events.

## Paths

Repo-local event outbox:

```text
.digital-asset/events/outbox.jsonl
```

DAD central storage:

```text
processed/events/event_log.jsonl
processed/events/response_state.jsonl
processed/events/quarantine/
processed/events/reports/event_pipeline.json
processed/events/reports/event_pipeline.md
```

## Event Types

The current event contract supports:

- `lesson_found`
- `exception_seen`
- `fix_outcome`
- `asset_used`
- `asset_rejected`
- `harness_needed`
- `dad_notice_ack`
- `dad_notice_saved_for_future`
- `dad_notice_implemented`
- `dad_notice_rejected`
- `governance_drift`
- `pipeline_health`

Notice response events require `notice_id` and write central response-state
rows. Absence of mail or absence of a response row is never treated as adoption.
Response events are accepted only when DAD has already recorded the actionable
notice and the responding source matches the notice target.

## Commands

Record a repo-owned event:

```text
asset-dir events record --repo . --type asset_used --summary "Used DAD Rust scan guidance" --dedupe-key "<stable-key>"
```

Collect one or more repo event outboxes into DAD:

```text
asset-dir events collect --repo <repo-path-or-reviewed-alias>
asset-dir events collect --repo all
```

`--repo all` uses reviewed `mail.repos` policy only. Explicit temp repo paths
are allowed for synthetic proofs, but collection is read-only against the source
repo and writes only central DAD event files.

Refresh the central report:

```text
asset-dir events report
```

Run the Rust structural leaf checker for event JSONL roots:

```text
asset-dir rust event-log-check
```

By default this checks DAD's repo-local event mirror and central event storage
using public-safe aliases. It reports JSONL shape, UTF-8, oversized rows,
duplicate `event_id` / `dedupe_key`, and obvious unsafe strings. It does not
collect events or update response state.

## Safety

Events are append-only candidate metadata. They do not override source repo
authority, satisfy human gates, approve public release, deliver mail, or
authorize enrollment.

Event payloads must be short metadata: summaries, IDs, paths expressed as
repo-relative or `dad://` references, hashes, and review notes. Do not include
secrets, private rows, hidden reasoning, long logs, copied source blobs, table
rows, or local absolute paths.

Source-authored visibility and release claims are advisory only. DAD collection
canonicalizes source and target visibility from reviewed policy; unreviewed
sources become `unknown`. Private/internal/restricted/unknown source visibility
aimed at public or unknown targets is held as `public_release_required` with
`public_release_status: pending_human` until a future reviewed release flow
approves movement. The initial event pipeline does not deliver to public repos
and does not mirror private/internal data to cloud storage.

## Rust Boundary

Rust is now used as a deterministic leaf checker for event JSONL shape,
oversized-row scans, invalid field values, duplicate-key scans, alias/path
hygiene, and obvious unsafe string screening:

```text
asset-dir rust event-log-check
```

The Rust report is structural evidence only. Python/DAD remains the policy
authority for collection, public release, source visibility, human gates,
response-state acceptance, repo adoption, and event report validation.
Inspect root statuses as well as `issue_count`: missing roots are not a green
event-pipeline signal even when there are no malformed rows.
