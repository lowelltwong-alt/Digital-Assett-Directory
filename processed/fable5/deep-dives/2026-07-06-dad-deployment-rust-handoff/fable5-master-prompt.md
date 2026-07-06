# Fable 5 Prompt: DAD Deployment And Rust Event Pipeline Handoff

You are Fable 5 reviewing DAD, the Digital Asset Directory. DAD is a
local-first library/control plane for many repos. Repos retain local source
authority. DAD recommendations, mail, generated reports, exception events,
scores, and Rust observations are candidate evidence until reviewed.

## Mission

Spend scarce Fable effort on the highest-leverage current question:

Is DAD in a good, non-brittle place for Codex to continue the deployment roadmap
in order after the Rust event-log checker landed?

## Read First

- `processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/README.md`
- `processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/whats-changed-since-last-review.md`
- `processed/fable5/deep-dives/2026-07-06-dad-deployment-rust-handoff/evidence-index.json`
- `roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md`
- `roadmap/evidence/phase-8-dad-local-deployment.md`
- `roadmap/evidence/phase-10a-mailbox-event-pipeline.md`
- `docs/DAD_EVENT_PIPELINE.md`
- `docs/rust/DAD_RUST_SCAN_CORE.md`
- `tools/dad_scan_core/src/event_log.rs`
- `src/digital_asset_directory/rust_bridge/dad_scan_core.py`
- `AI_FRONT_DOOR.md`
- `AI_TABLE_OF_CONTENTS.md`

## Highest Priority Questions

1. Phase 8 false confidence:
   - Does the evidence prove local DAD deployment enough for human review?
   - Could the user shim, hub locator, or doctor output still pass falsely?
   - Are real non-DAD repos protected from target writes during deployment
     smoke tests?

2. Roadmap ordering:
   - Is the current order still right: Phase 8, then Phase 9, Phase 10, Phase
     10A, Phase 11, Phase 12?
   - Did the Rust event-log work accidentally skip ahead in a way that creates
     false confidence?

3. Rust boundary:
   - Is `asset-dir rust event-log-check` correctly limited to deterministic
     structural evidence?
   - Could it miss dangerous rows, leak local paths, count the wrong things, or
     be over-used as policy authority?
   - What is the next best Rust-fit leaf after this, if any?

4. Registration and discoverability:
   - Can an agent reliably find the deployment roadmap, Phase 8 evidence,
     Phase 10A evidence, Rust scanner docs, and this Fable packet from the
     front door and TOC?
   - Is any newly important artifact missing from navigation, validation, or
     roadmap evidence?

5. Hard issue lookup and learning loop:
   - Would future agents know to look in DAD for prior deployment/Rust/event
     pipeline failures before improvising?
   - What should become a harness versus a deterministic gate?

## Constraints

- Do not copy secrets, private rows, raw stack traces, large source blobs,
  proprietary content, leaked content, or long third-party documentation.
- Do not mutate protected repos.
- Do not approve human gates.
- Do not promote Rust beyond leaf deterministic scanning/checking without
  parity and correctness evidence.
- Do not treat match scores, green tests, graph edges, or Fable output as proof
  of truth.

## Output

Return findings that satisfy `expected-output.schema.json`.

Use this severity order:

- Critical: likely leak, data corruption, protected-repo write, false human-gate
  approval, or a feature that appears working but fails its central purpose.
- High: brittle deployment proof, weak fail-closed behavior, stale generated
  evidence, Rust/Python authority confusion, or missing gate tests.
- Medium: missing navigation, unclear docs, incomplete audit trail, or weak
  ergonomics that could cause future agent mistakes.
- Low: cleanup and clarity.

For each lower-level issue, include a Codex delegation item with exact files,
patch hint, and validation command.

If you make one direct fix, keep it small, reversible, and local to DAD.
