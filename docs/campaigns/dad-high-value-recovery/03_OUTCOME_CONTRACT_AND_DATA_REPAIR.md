# Phase 03 — Outcome Contract and Data Repair

## Outcome

Repair the recommendation-to-value chain so new outcomes are valid by
construction, historical outcomes are honestly classified, and yield reporting
counts actual reuse rather than lifecycle acknowledgements.

## Prerequisites

- Phase 02 local CI is green and the accepted workflow revision is pinned.
- H-008 approves immutable legacy-row treatment.
- The source schemas, producers, consumers, reports, fixtures, and migration
  surface have a reverse-consumer map.
- Schema evolution follows compatibility and key-value governance.

## Jobs in order

1. `jobs/J-300_ENFORCE_RECOMMENDATION_OUTCOME_CONTRACT.md`
2. `jobs/J-310_CLASSIFY_AND_QUARANTINE_LEGACY_OUTCOMES.md`
3. `jobs/J-320_CORRECT_LEARNING_YIELD_SEMANTICS.md`

## Extend, do not replace

Primary implementation surfaces:

- `schemas/repo-asset-usage.schema.json`
- `schemas/capability-recommendation.schema.json`
- `schemas/workflow-run-event.schema.json`
- `schemas/dad-pipeline-event.schema.json`
- `src/digital_asset_directory/dad_library.py`
- `src/digital_asset_directory/event_pipeline.py`
- `src/digital_asset_directory/learning_yield_report.py`
- `tests/test_dad_library_control_plane.py`
- `tests/test_event_pipeline.py`
- `tests/test_learning_yield_report.py`
- `registry/schema-registry.json` if existing registry rules require a revision
- `.digital-asset/key-values/change-log.jsonl` for load-bearing field semantics

Do not create a fourth ledger. Prefer backward-compatible optional fields first,
then make them required for newly counted outcome envelopes at the application
validation boundary. Historical rows remain readable under their original
schema revision.

## Contract design

### Recommendation

Add or expose stable recommendation identity, recommendation revision, task/run
scope, recommended asset IDs, immutable asset revisions, producer identity,
methodology revision, and evidence refs.

### Adoption/non-adoption

Use the existing repo asset-usage/adoption plane. Require `adoption_id` for use
and a constrained reason for non-adoption. Mail acknowledgement, save-for-future,
or preflight appearance does not equal adoption.

### Outcome

At `record_trace_outcomes` and every other producer boundary:

1. accept only the constrained enum `used`, `ignored`, `attempted_failed`, or
   `harmful`;
2. require asset IDs to be members of the trace's recommended asset set;
3. reject empty strings, `none`, prose explanations, and unknown asset IDs;
4. require one outcome per recommended asset or an explicit trace-level closure
   rule;
5. make duplicate retries idempotent by stable envelope key;
6. keep reason/details in separate bounded fields, never in identity fields;
7. record verification status and independent checker refs;
8. distinguish real, synthetic, and fixture evidence.

### Independent validation

The outcome producer cannot be the sole checker. A self-report may remain
`unverified`; it cannot satisfy promoted reuse, beneficial/harmful aggregation,
or a pilot value gate until an eligible checker verifies it.

## Required negative fixtures

- arbitrary unknown asset ID;
- valid-looking asset ID absent from the trace recommendation set;
- `none`, empty string, and prose in an asset identity field;
- unsupported outcome enum;
- missing adoption/non-adoption closure;
- duplicate retry with the same idempotency key;
- retry with conflicting payload;
- missing asset revision;
- missing validation reference;
- producer and checker are the same identity;
- acknowledgement incorrectly counted as reuse;
- synthetic row attempting to satisfy a real pilot gate.

## Legacy classification

J-310 scans immutable historical outcome rows and emits a separate classification
projection:

- `joinable`: schema-valid and deterministically linked to its recommendation;
- `invalid`: violates identity/enum/membership/structural rules;
- `unknown`: required source evidence is unavailable or ambiguous.

For every source ledger:

```text
source_total = joinable + invalid + unknown
```

The report records source path/digest, classifier revision, reason codes, counts,
sample-safe IDs, privacy class, and limitations. It does not edit or delete the
source rows. Aggregates use `joinable` only and publish excluded counts.

## Yield semantics

J-320 defines and tests:

- `written`: a new eligible recommendation/asset/lesson was recorded;
- `reused`: a distinct task/repo has a joinable `used` outcome linked through
  adoption and independent validation;
- `promoted`: a named human lifecycle decision promotes the exact revision;
- `acknowledged`: receipt only, reported separately;
- `saved_for_future`: intent only, reported separately;
- `attempted_failed` and `harmful`: outcomes, never reuse;
- self-use and cross-repo reuse: separate series.

Every yield aggregate publishes numerator, denominator, eligible/excluded rows,
missingness, time window, and methodology revision.

## Validation

```powershell
$env:PYTHONPATH = 'src'
python -m pytest tests/test_dad_library_control_plane.py
python -m pytest tests/test_event_pipeline.py
python -m pytest tests/test_learning_yield_report.py
python -m pytest
python -m digital_asset_directory.cli validate
python -m digital_asset_directory.cli roadmap check --no-update
```

Also run a small synthetic end-to-end case and negative cases through the real
producer, collector, classifier, aggregate, and report paths. Synthetic success
proves plumbing only.

## Acceptance

- 100% of new outcome writes validate membership against the exact trace.
- Zero new identity fields accept sentinels or prose.
- Conflicting duplicate retries fail closed; identical retries dedupe.
- Producer/checker collision cannot yield independently validated status.
- Every historical row is joinable, invalid, or unknown with reconciliation.
- Raw historical records are unchanged.
- Value/yield aggregates include joinable eligible rows only and show exclusions.
- Written, acknowledged, saved, reused, promoted, failed, and harmful semantics
  match actual event enums.
- The full local validation baseline remains green.

## Rollback

Rollback restores the prior producer/consumer code while retaining new raw rows
and classification evidence. If compatibility cannot be preserved, stop and
design an explicit versioned migration; never coerce history in place.

