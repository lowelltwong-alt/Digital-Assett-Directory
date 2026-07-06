# DAD Rust Scan Core

## Status

Candidate implementation scaffold. Not canonical until reviewed and adopted.

## Purpose

`tools/dad_scan_core` is the first Rust leaf-tool crate for Digital Asset Directory.

It currently provides these read-only probes:

- `scan-local`: scans local source trees and emits raw, non-authorizing observations for Python to validate and ingest.
- `mail-spool-check`: checks DAD mail spool roots for JSONL, lock/temp, malformed-row, oversized-row, and Rust rollout packet signals using public-safe aliases.
- `event-log-check`: checks DAD event JSONL roots for malformed/invalid UTF-8/oversized rows, invalid field values, duplicate event ids and dedupe keys, obvious unsafe strings, and alias-only output.
- `phase8-evidence-check`: checks Phase 8 local-deployment command-evidence JSON for required proof rows, pending human-review status, unsafe strings, and false authority claims.
- `repo-inventory-probe`: discovers local Git repository roots under configured roots using public-safe aliases and emits `dad_repo_inventory_probe.v0_2` contract-surface facts for Phase 9 inventory/deployment-doctor evidence.

## Boundary

Rust may:

- walk local directories;
- skip excluded paths;
- refuse symlinks by default;
- hash metadata/content;
- emit JSONL observations;
- emit quarantine and summary JSON.
- count mail-spool lock/temp fragments and malformed/oversized JSONL rows.
- count event-log malformed, invalid UTF-8, oversized, invalid field value,
  duplicate identity, and obvious unsafe-string structural issues.
- discover Git repository root markers under configured local roots.
- report whether `.digital-asset/dad-integration.json` has the required
  capture fields, stable user shim pointers, raw-checkout fallback, and
  issue-code-only structural failures.
- check that Phase 8 command-evidence JSON is structurally clean while reporting
  `phase8_human_gate_satisfied=false`.

Rust may not:

- score asset value;
- decide lifecycle status;
- infer final duplicate identity;
- create graph truth;
- create AI context packs;
- collect, route, deliver, release, or adopt mail;
- classify repos for enrollment, infer GitHub lineage, decide protected status,
  inspect branch/dirty policy, or satisfy human gates;
- decide that an enrollment contract is valid, deployed, public-safe, current,
  or ready for rollout;
- mutate source files;
- become the source of governance authority.

## Verification

```bash
cargo check --manifest-path tools/dad_scan_core/Cargo.toml
cargo test --manifest-path tools/dad_scan_core/Cargo.toml
cargo fmt --manifest-path tools/dad_scan_core/Cargo.toml --check
cargo clippy --manifest-path tools/dad_scan_core/Cargo.toml --all-targets -- -D warnings
```

## First fixture scan

```bash
python scripts/run_dad_scan_core.py   --source examples/demo_assets   --source-id demo_assets   --path-alias demo   --out raw/local/demo.jsonl   --summary-out processed/scans/demo-summary.json   --quarantine-out processed/quarantine/demo-quarantine.json   --max-files 100
```

## Mail Spool Probe

During concurrent repo mail storms or Rust rollout packet churn, use the Python
mail storm gate for the first go/no-go decision:

```bash
python -m digital_asset_directory.cli mail storm-gate
python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap
```

Use the Rust probe when you want a fast, deterministic, read-only leaf check of
mail roots:

```bash
python -m digital_asset_directory.cli rust mail-spool-check
```

The Rust summary is evidence only. `mail storm-gate` gives the first
collect/route/deliver answer, and `mail doctor` provides detailed issue
diagnostics.

Rust rollout packet generation is write-gated even though the Rust probe is
read-only. `asset-dir rust-rollout build-mail` may write to DAD's ignored
`processed/mail/staged/rust_rollout/`, to the tracked
`mail/outbox/rust_rollout/` reference snapshot with explicit promotion
acknowledgement, or to a system temp directory for ad hoc review. It must not
write generated packets into another repo's `.digital-asset/mail/` or source
tree.

## Event Log Probe

For Phase 10A event-pipeline evidence, use:

```bash
python -m digital_asset_directory.cli rust event-log-check
```

The command defaults to DAD's repo-local event mirror and central
`processed/events/` storage. It emits alias-only structural evidence for JSONL
shape, invalid UTF-8, oversized rows, invalid field values, duplicate `event_id`
/ `dedupe_key`, and obvious unsafe strings. Python `events collect`, `events report`, and
`validate` remain authoritative for collection, policy canonicalization, public
release, response-state acceptance, stale report detection, and Phase 10A gate
review.

Do not treat `issue_count: 0` alone as green. The Python wrapper also reports
whether every requested root was actually checked; missing roots are not event
pipeline readiness evidence.

## Phase 8 Evidence Probe

For Phase 8 local-deployment evidence, use:

```bash
python -m digital_asset_directory.cli rust phase8-evidence-check
```

The command checks the Phase 8 command-evidence JSON for the original five
deployment proof rows, `status: passed`, `human_review_status: pending`,
alias-only issue samples, and obvious local path or credential markers.

This is intentionally not a deployment doctor. It does not invoke `asset-dir`
from non-DAD repos, prove module attestation, inspect live PATH state, authorize
repo enrollment, or satisfy human gates. Python `roadmap check --no-update`,
`validate`, and recorded human gate review remain authoritative.

## Repo Inventory Probe

For Phase 9 read-only inventory evidence, use:

```bash
python -m digital_asset_directory.cli rust repo-inventory-probe --max-depth 6
```

The command defaults to DAD's configured local sources and emits alias-only Git
root evidence plus contract-surface facts. Python `dad inventory` and the DAD
deployment doctor remain the authority for classification, public-safe
redaction, GitHub reconciliation, policy holds, enrollment readiness, and
deployment decisions.

The `contract_structural_pass` field only means the required structural facts
were observed in the contract file. It is not schema validity, enrollment
readiness, a public/private release decision, or permission to write to a repo.
