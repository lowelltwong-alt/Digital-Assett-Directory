# DAD First Rust Upgrade Plan

## Goal

Introduce Rust as a deterministic scan core while preserving DAD's Python orchestration and governance.

## Target architecture

```text
asset-dir scan
  -> Python loads config and chooses source scope
  -> dad_scan_core scans local source safely
  -> dad_scan_core emits raw/local/<scan_id>.jsonl
  -> Python ingests observations into DAD's existing CatalogDB
  -> Python builds identity layers, graph, synergies, context packs, lessons
```

## Crate boundary

```text
tools/dad_scan_core/
```

### Rust owns

- local directory walk;
- symlink refusal;
- ignore/exclude/quarantine matching;
- metadata fingerprints;
- optional content SHA-256;
- file type hints;
- bounded content profile metadata only;
- raw observation JSONL;
- quarantine summary JSON;
- scan summary JSON.

### Python owns

- Typer CLI;
- DAD config model;
- SQLite catalog;
- scoring;
- graph/radar/recommendations;
- context packs;
- lessons;
- mail center;
- agent preflight/postflight;
- cross-repo governance;
- reviewed promotion decisions.

## Initial command contract

```bash
cargo run --manifest-path tools/dad_scan_core/Cargo.toml -- scan-local   --source ./examples/demo_assets   --source-id demo_assets   --path-alias demo   --out raw/local/demo-scan.jsonl   --summary-out processed/scans/demo-summary.json   --quarantine-out processed/quarantine/demo-quarantine.json   --max-files 100
```

## Observation schema draft

```json
{
  "schema_version": "dad_scan_observation.v0_1",
  "observation_type": "local_file_candidate",
  "source_id": "demo_assets",
  "path_alias": "demo",
  "logical_path": "demo/README.md",
  "size_bytes": 100,
  "modified_unix_seconds": 1234567890,
  "metadata_sha256": "...",
  "content_sha256": "... or null",
  "content_hash_mode": "content_sha256|metadata_only|oversize_metadata_only|read_error",
  "asset_type_hint": "markdown",
  "extract_method": "extension_hint_only",
  "no_mutation_performed": true
}
```

## Phase plan

### Phase 0 — scaffold

- Copy `overlay/tools/dad_scan_core/` into DAD.
- Run `cargo check`.
- Fix compile errors.
- Run smoke test.

### Phase 1 — parity observation

- Run Rust scanner on a tiny local fixture.
- Verify JSONL is parseable by Python.
- Add a Python adapter that converts Rust observations to current `AssetRecord` candidates.
- Do not remove the Python scanner yet.

### Phase 2 — dual-run comparison

Run both scanners on the same small fixture:

```text
Python scan -> normalized asset candidates
Rust scan -> raw observation candidates -> Python adapter -> normalized candidates
```

Compare:

- file count;
- skipped/quarantined count;
- path aliases;
- content/metadata hash availability;
- asset type hints;
- no mutation proof.

### Phase 3 — Rust as default local scanner for small scope

Only after parity fixtures pass.

### Phase 4 — long CI

Add large synthetic fixture scans, nextest, coverage, dependency audit, property tests, and optional mutation tests.

## Fail-closed rules

The Rust scanner must fail closed when:

- source path is missing;
- output parent cannot be created;
- source path is a symlink and symlink following is not explicitly enabled;
- output path is inside source path without explicit safe-output override;
- observation JSON serialization fails;
- source file changes during scan if change detection is enabled.

## Do not optimize early

Initial Rust success is correctness and no-mutation proof, not speed. Speed becomes a measured target after parity.
