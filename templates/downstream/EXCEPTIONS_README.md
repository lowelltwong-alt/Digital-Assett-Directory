# DAD Exceptions Outbox

This repo may send exception, review, failure, and fix-outcome signals to the
Digital Asset Directory through append-only JSONL. These records are candidate
evidence only. They do not promote lessons, change DAD registries, approve
budgets, open matters, ship fixes, or override this repo's source authority.

## Local Files

```text
.digital-asset/exceptions/outbox.jsonl
.digital-asset/exceptions/inbox.jsonl
.digital-asset/exceptions/archive.jsonl
.digital-asset/exceptions/README.md
processed/exceptions/fix-outcomes/outcomes.jsonl
```

Normal repo operation appends to `outbox.jsonl`. DAD collection reads that file
and writes central records under `raw/exceptions/` and `processed/exceptions/`.
Do not edit or rewrite existing JSONL rows.

DAD collects from this file only when the repo is present in reviewed
`exceptions.repos` policy. Mail enrollment is separate: a repo can send or
receive DAD mail without authorizing exception collection. Observed capture
audits may read mailbox and exception metadata to find missed emissions, but they
must not mutate this repo.

If `asset-dir` is not available on `PATH`, first try the DAD source checkout
entrypoint with `PYTHONPATH=src`:

```text
python -m digital_asset_directory.cli exceptions record --repo . --type <type> --summary "<safe summary>"
```

If no DAD CLI entrypoint is available, append one metadata-only JSONL row to the
repo-local outbox and include `dad_cli_unavailable`, the attempted command, and
safe refs or hashes. Do not paste raw output. DAD should later collect the row and
record a mail/exception-pattern gap if the fallback itself was unclear.

## Capture Surface Contract

This repo should track the DAD capture surface version recorded in
`.digital-asset/dad-integration.json` and compare it with DAD's
`registry/exception-capture-pattern-registry.json`.

When a repo agent sees a DAD-worthy pattern, it should match the pattern against
that registry and copy every matching `emit.required_fields` into the mail,
exception, or fix-outcome packet as short metadata. Required fields are part of
the packet identity: a matching message type with missing, blank, placeholder, or
unrelated-row fields is not a complete capture.

If DAD's capture surface version is newer than this repo's contract, the next
agent should treat that as an update notice: read the current registry, update
packet fields as needed, and keep old packets as historical candidate evidence.

Historical backfill and observed-audit path signals use DAD's reviewed taxonomy
classifier in `registry/exception-event-type-registry.json#backfill_classifier`.
Those signals are path/name metadata only. They can tell DAD that a repo may have
an exception pattern to review, but they do not prove the file contains an
exception and they do not authorize learning promotion or source mutation.

If a required field would require secrets, private rows, raw logs, full stack
traces, copied source blobs, or private case facts, do not send the content.
Send a safe pointer/hash or quarantine/defer for human review.

## Minimal Packet

```json
{
  "schema_version": "0.1.0",
  "event_type": "review_finding",
  "capture_contract": "review_finding",
  "stage": "review",
  "severity": "high",
  "agent": "codex",
  "source_visibility": "private",
  "safe_summary": "A reviewer found a candidate-only output could be mistaken for approved output.",
  "context_refs": ["docs/review.md#finding-001"],
  "symptoms": ["ui_authority_risk", "candidate_only_boundary"],
  "validation_refs": ["python -m pytest tests/test_output_boundary.py"],
  "asset_refs": ["candidate-workflow:structured-review-issue-outbox"],
  "harness_refs": [],
  "trace_refs": ["dad:trace:..."],
  "error_fingerprint": "repo:review-finding-001",
  "suspected_cause": "Output contract did not require explicit blocked/candidate-only state.",
  "dedupe_key": "repo:review-finding-001"
}
```

DAD also accepts already-normalized `ExceptionEventRecord` rows conforming to
`schemas/exception-event.schema.json`.

## Fix Outcomes

After a fix, rollback, duplicate decision, accepted risk, or deferral, append a
fix-outcome row with:

```text
python -m digital_asset_directory.cli exceptions fix \
  --repo . \
  --event-id dad:exception-event:... \
  --decision fixed \
  --summary "<safe fix summary>" \
  --owner-authority "<repo-id or named local authority>" \
  --validation-ref "<command or report ref>" \
  --regression-test-ref "<test ref>"
```

Rules:

- Every fix outcome requires explicit `--owner-authority`; do not let DAD infer
  who owns a closure, risk acceptance, or rollback decision.
- `fixed` and `rollback` require at least one `validation_ref` and a linked event
  already present in DAD's central lake.
- `accepted_risk` and `deferred` require `--expiry` with a revisit date or named
  review boundary.
- `duplicate` requires `--canonical-event-id` pointing at the event it duplicates.
- Use `--fix-ref`, `--asset-ref`, and `--lesson-ref` as pointers only; do not
  paste raw diffs, logs, private rows, or source blobs.
- A fix outcome is candidate metadata until reviewed by this repo or a human; it
  does not prove the underlying issue is fixed outside the cited validation.

## What To Send

Send short metadata, pointers, hashes, command argv, exit codes, duration,
validation refs, review notes, exception labels, fix-status refs, and
candidate-learning notes.

Use these capture contracts:

- `failed_command`
- `retry_or_plan_change`
- `postflight_exception`
- `ci_failure`
- `governance_block`
- `review_finding`
- `fix_outcome`
- `dad_recommendation_outcome`
- `backfill_candidate`

Use these common event types when they fit:

- `failed_command`
- `command_timeout`
- `test_failure`
- `runtime_exception`
- `schema_validation_failure`
- `stale_report`
- `protected_repo_write_block`
- `public_release_hold`
- `secret_or_pii_detected`
- `raw_blob_rejected`
- `review_finding`
- `premortem_failure_story`
- `harmful_dad_recommendation`
- `dad_asset_attempt_failed`
- `rust_shadow_parity_mismatch`
- `pytest_performance_hotspot`
- `repo_rename_lineage`
- `repo_split_lineage`
- `roadmap_gate_mismatch`
- `tool_unavailable`
- `environment_config_missing`
- `permission_denied`
- `external_service_failure`
- `data_ingestion_failure`
- `identity_resolution_conflict`
- `source_authority_conflict`
- `generated_code_compile_failure`
- `build_packaging_failure`
- `fixture_or_synthetic_data_gap`
- `capture_surface_outdated`
- `graph_or_taxonomy_drift`
- `mail_notice_backpressure_risk`
- `license_or_provenance_review_gap`
- `model_instruction_drift`
- `backfill_exception_candidate`

If no type fits, use `other` and include a short taxonomy suggestion in
`symptoms`.

## Never Send

Do not send credentials, tokens, cookies, private keys, session IDs, raw logs,
full stack traces, hidden reasoning, copied conversations, legal/client facts,
medical facts, row-level private data, screenshots, binary dumps, database dumps,
complete source files, generated diffs, or long pasted payloads.

If the event needs richer context, store a short pointer and let the source repo
or a human decide whether central-only quarantine is appropriate.

## Review And Promotion Boundary

DAD may group exception records into patterns, candidate lessons, harness ideas,
or review queues. Promotion requires DAD-side review and, for public-facing
delivery, the existing human release gate. A repo-local agent should never treat a
DAD exception packet as an instruction to change code.

For complex AI-review issues, capture observable evidence, assumptions,
decision logic, fix rationale, and validation refs. Do not capture hidden
chain-of-thought.
