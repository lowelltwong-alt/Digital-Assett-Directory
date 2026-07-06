# What Changed (for Fable to read later)

Status: candidate delta note. Review input only - same authority boundary as this
packet's `README.md` and `evidence-index.json`. Nothing here approves a human gate,
enrollment, cross-repo write, public release, or Rust governance authority.

Delta compiled: 2026-07-06 at baseline `main` tip `865ef79`.
Prior Fable baseline: the `2026-07-04-dad-last-48h` deep dive (roughly commit
`94639a5` and earlier).

## TL;DR

DAD grew its first real Rust core (a deterministic leaf checker) and wired a
local-first event pipeline underneath the mailbox. Rust is a leaf worker only;
Python/DAD keeps all policy authority. Deployment sits at Phase 8 with machine
evidence awaiting human gate - not approved. Read `fable5-master-prompt.md`
next; this file is just the "what moved" summary.

## New since the last Fable review

1. Rust event-log structural checker (commit `865ef79`, the baseline tip).
   - Rust: `tools/dad_scan_core/src/event_log.rs` reads event-log JSONL under
     declared roots, checks structure, counts, and samples issues.
   - Python bridge: `src/digital_asset_directory/rust_bridge/dad_scan_core.py`
     shells out to cargo and returns a frozen `DadScanCoreResult` dataclass.
     The Rust core now backs three deterministic leaf checks by schema:
     `dad_event_log_check.v0_1`, `dad_mail_spool_check.v0_1`, and
     `dad_repo_inventory_probe.v0_2`.
   - CLI: `asset-dir rust event-log-check`. A no-root run returns exit 0 with
     `summary_valid true`, `default roots missing`,
     `event_log_structural_clean false`, and
     `event_pipeline_gate_satisfied false`, so it fails closed and does not fake
     a clean gate when roots are absent.
   - Tests: `tests/test_rust_bridge_dad_scan_core.py`.
   - Docs: `docs/rust/DAD_RUST_SCAN_CORE.md`,
     `docs/DAD_EVENT_PIPELINE.md`, and roadmap evidence.
   - Boundary: Rust does deterministic scanning, hashing, dedupe, freshness, and
     structure checks only. Python/DAD owns policy, public/private release, and
     human gates.

2. Phase 10A local-first event pipeline (commit `94639a5`).
   Repo-owned event records under `.digital-asset/events/outbox.jsonl` for short
   metadata signals such as `asset_used`, `harness_needed`, `exception_seen`,
   `fix_outcome`, and `dad_notice_*`. DAD collection reads them and writes only
   central DAD event files. These remain candidate metadata; mailboxes remain
   the safe repo-local edge adapter.

3. This Fable packet is now registered into navigation.
   `AI_FRONT_DOOR.md`, `AI_TABLE_OF_CONTENTS.md`,
   `MACHINE_NAVIGATION_MANIFEST.json`, `registry/ai-navigation-registry.json`,
   and a new "Fable Review Checkpoint" section in
   `roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md` point
   agents at `2026-07-06-dad-deployment-rust-handoff/`.
   `tests/test_ai_navigation.py` was updated to match. Verify this handoff
   commit is present before relying on the navigation routes.

## Validation snapshot

Current checks run for this packet before handoff:

- `PYTHONPATH=src python -m pytest tests/test_ai_navigation.py -q`: 12 passed.
- `PYTHONPATH=src python -m ruff check tests/test_ai_navigation.py`: passed.
- `PYTHONPATH=src python -m digital_asset_directory.cli validate`: valid, 623 checks.
- `PYTHONPATH=src python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; Phase 8 awaiting human gate; Phase 10A still blocked by upstream gates.

Last known from the Rust event-log checker commit:

- `cargo fmt --check`, `cargo check`, and `cargo clippy -- -D warnings`: passed.
- `cargo test` for `dad_scan_core`: 37 passed.
- `PYTHONPATH=src python -m pytest`: 927 passed.

Re-run broad checks before treating them as current.

## Roadmap position

Phase 8 local deployment has machine evidence and is awaiting human gate.
Phases 9, 10, 10A, 11, and 12 remain blocked or planned because upstream human
gates are not approved. Broad enrollment is intentionally last.

## Not on main - do not miss this

The graph combination-discovery kernel from the prior Fable/Opus session is
committed on branch `dad-graph-inference-kernel` (commits `ba2eb9d` and
`ded68f0`), not merged to main. It adds
`src/digital_asset_directory/graph_inference.py`,
`registry/graph-inference-methodology.json`, offering-schema facets, and a
golden test. A future Fable should decide whether to rebase or merge it forward.

## Environment caveat from prior working sessions

Prior sessions reported background main-branch churn while other agents were
working. Commit early on a branch when doing larger edits. This is why the graph
kernel lives on its own branch until a reviewer decides whether to rebase or
merge it.

## Suggested first moves for the next Fable

Defer to `evidence-index.json` `suggested_fable_focus`, but in short: hunt
false-green paths in the Phase 8 proof; audit the Rust checker and bridge for
local-path leakage, stale-schema drift, and missing-root false confidence;
confirm roadmap gate ordering blocks enrollment before earlier phases are
proven; and decide the graph-inference branch's fate.
