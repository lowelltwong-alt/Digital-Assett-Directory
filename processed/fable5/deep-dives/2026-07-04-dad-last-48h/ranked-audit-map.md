# Ranked Audit Map

## 1. Exception Capture And Exceptions Lake

Risk: DAD may look like it learned from repos, while real repo agents still fail
to emit the right mail or exception packet without Lowell rescuing the pattern
from chat.

Evidence:
- `docs/DAD_EXCEPTIONS_LAKE_BUILDOUT.md`
- `src/digital_asset_directory/exception_capture.py`
- `src/digital_asset_directory/exceptions_lake.py`
- `assets/coding-harnesses/exception-capture-completeness/`
- `processed/exceptions/lake/events.jsonl`

Fable task: find false positives, false negatives, missing synthetic pattern
updates, weak backfill gates, and places where fix outcomes do not become useful
future lookup evidence.

## 2. Mail, Locks, And Daily Repo Learning

Risk: daily mail, triage, and learning can fail on Windows/OneDrive locks,
`asset-dir` PATH gaps, duplicate delivery, or stale state while appearing
processed.

Evidence:
- `src/digital_asset_directory/mail_center.py`
- `src/digital_asset_directory/utils.py`
- exception IDs `dad:exception-event:bff4a3cb-6950-5f22-9583-0f185bad6d3e`
- exception IDs `dad:exception-event:02bd7f7f-b0b0-5d1a-b532-ac5b9a1e8412`
- exception IDs `dad:exception-event:713ae8d1-ee57-543e-b2c9-b06f76c4dd1c`

Fable task: design a durable mailbox protocol and decide which failures need
hard deterministic checks versus harness coverage.

## 3. Rust Scan Core And Rust Rollout

Risk: Rust appears installed but does not yet create enough proof, lessons, and
safe downstream templates. Fixed bugs could re-enter downstream repos if overlay
files drift.

Evidence:
- `tools/dad_scan_core/`
- `src/digital_asset_directory/rust_bridge/`
- `assets/dad-rust-upgrade-starter-pack/`
- `lessons/rust_rollout/lesson_ledger.jsonl`
- `processed/reports/rust/dad_scan_core_20260704_142903_summary.json`

Fable task: red-team Rust/Python boundaries, no-write guards, path privacy,
directory quarantine, overlay synchronization, and the criteria for future Rust
promotion.

## 4. AI Front Door, TOC, And Registration Drift

Risk: important new assets exist but are missing from front doors, TOCs,
manifests, registries, validators, generated snapshots, or roadmaps.

Evidence:
- `AI_FRONT_DOOR.md`
- `AI_TABLE_OF_CONTENTS.md`
- `MACHINE_NAVIGATION_MANIFEST.json`
- `registry/ai-navigation-registry.json`
- exception ID `dad:exception-event:8a45eee1-3d92-537b-bbc3-0e5838585c05`

Fable task: propose an artifact registration invariant and a harness that finds
orphaned assets, prompts, reports, and implementation files.

## 5. Language Frontier And Professional Research Layer

Risk: the research layer becomes noisy, stale, hype-driven, or too weak to catch
the next high-leverage coding harness discovery.

Evidence:
- `docs/DAD_PROFESSIONAL_RESEARCH_LAYER.md`
- `docs/RESEARCH_INTAKE_PIPELINE.md`
- `docs/FABLE_PROFESSIONAL_RESEARCH_LAYER_PROMPT.md`
- `registry/trusted-source-registry.json`
- `assets/coding-harnesses/language-frontier-research/`

Fable task: improve source filters, novelty scoring, high-signal escalation,
and DAD-first then research-second routing.

## 6. Lesson Lifecycle, Address Model, And Graph Governance

Risk: lessons accumulate without review clocks, downgrade/archive paths, variant
links, or compact addresses, making DAD noisy instead of smarter.

Evidence:
- `docs/LESSON_LIFECYCLE_GOVERNANCE.md`
- `docs/DAD_ADDRESS_MODEL.md`
- `registry/dad-address-model-registry.json`
- `docs/FABLE_HARD_ISSUE_LOOKUP_AND_SOLUTION_LINEAGE_PROMPT.md`

Fable task: design lightweight lifecycle metadata and solution-family graph
links that prevent sprawl.
