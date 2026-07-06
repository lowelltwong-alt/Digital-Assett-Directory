# Phase 10A: Mailbox-Backed Event Pipeline Evidence

Generated: 2026-07-06
Status: initial machine evidence captured; upstream human gates still pending

## Scope

This packet covers the first Goal 3A slice from
`roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md`.

It establishes a local-first event/data pipeline beneath DAD mail:

- repo-owned event outbox: `.digital-asset/events/outbox.jsonl`;
- central append-only event log: `processed/events/event_log.jsonl`;
- central response-state log: `processed/events/response_state.jsonl`;
- central quarantine: `processed/events/quarantine/`;
- central report: `processed/events/reports/event_pipeline.json` and `.md`.

This slice does not deliver mail, enroll repos, approve public release, mirror to
Cloudflare, or write target repo source/governance files.

## Implemented

- Added `schemas/dad-pipeline-event.schema.json`.
- Added `src/digital_asset_directory/event_pipeline.py`.
- Added CLI commands:
  - `asset-dir events record`;
  - `asset-dir events collect`;
  - `asset-dir events report`.
- Registered central event-log validation in `asset-dir validate`.
- Added `docs/DAD_EVENT_PIPELINE.md` and downstream mailbox guidance.
- Added AI front-door, TOC, manifest, and navigation-registry routes.

## Machine Evidence

Focused tests:

```text
PYTHONPATH=src python -m pytest tests/test_event_pipeline.py -q
```

Result: passed, 6 tests.

Covered behavior:

- repo agents can append candidate events to their own
  `.digital-asset/events/outbox.jsonl`;
- DAD collection reads repo event outboxes and writes only central DAD event
  files;
- duplicate collection is idempotent by `event_id` and `dedupe_key`;
- malformed JSONL, invalid UTF-8, invalid records, and unsafe payloads are
  quarantined by metadata/hash while good rows continue;
- `dad_notice_*` response events write explicit response-state rows;
- response transitions such as `acknowledged` then `implemented` are append-only
  instead of silently suppressed;
- private, internal, restricted, or unknown source-origin to public/unknown
  target events carry `public_release_required` and `pending_human` metadata;
- source-authored visibility is advisory only; DAD collection canonicalizes
  source/target visibility from reviewed policy or conservative `unknown`;
- `dad_notice_*` response events are accepted only when the notice already
  exists in the central event log and the responding repo matches the notice
  target;
- reports flag actionable notices that lack response-state rows.

Static check:

```text
PYTHONPATH=src python -m ruff check src/digital_asset_directory/event_pipeline.py src/digital_asset_directory/cli.py tests/test_event_pipeline.py
```

Result: passed.

## Rust Boundary

Rust was evaluated for this slice and intentionally kept out of the policy path.
The correct next Rust use is a deterministic leaf checker that shadows the
Python event validator for:

- JSONL shape and malformed/oversized row scans;
- event/dedupe identity conflicts;
- alias/path hygiene and no-local-path output;
- provenance hashes and dependency-freshness inputs.

Rust must not decide response states, public release, source visibility, human
gates, repo adoption, mail delivery, or learning promotion.

## Human Gates Still Pending

This evidence supports later review of:

- `phase-10a-event-contract-reviewed`;
- `phase-10a-mailbox-edge-boundary-reviewed`;
- `phase-10a-response-loop-reviewed`;
- `phase-10a-rust-leaf-checker-reviewed`;
- `phase-10a-cloud-boundary-reviewed`.

Phase 10A still depends on Phase 8, Phase 9, and Phase 10 human gates. This
packet is review input only and does not make those dependencies complete.
