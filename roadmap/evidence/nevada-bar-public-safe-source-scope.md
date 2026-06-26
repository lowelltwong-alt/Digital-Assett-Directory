# Nevada Bar Public-Safe Source Scope Evidence

Status: curated evidence for a privacy-preserving local sweep boundary.

## Decision

The Nevada Bar Results source is useful to DAD as a workflow and asset-family seed, but its scraped and derived row-level data is not imported into tracked DAD evidence because this repository may become public.

The approved path is:

```text
metadata-only public-safe sweep
-> generated local report under processed/
-> curated workflow and policy evidence
-> no scraped rows in Git
```

## Evidence Recorded

- Reusable workflow evidence: `roadmap/evidence/nevada-bar-professional-intelligence-workflow.md`
- Public-safe policy: `docs/NEVADA_BAR_PUBLIC_SAFE_IMPORT_POLICY.md`
- Reusable sweep method: `docs/PUBLIC_SAFE_SOURCE_SWEEPS.md`
- CLI command: `recommend public-safe-source-sweep`

## Metadata-Only Sweep Result

Command:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend public-safe-source-sweep --source-path "<local Nevada Bar Results folder>" --source-id nevada-bar-results --review-sample 80
```

Generated local outputs:

- `processed/reports/external_sweeps/nevada-bar-results_public_safe_sweep.md`
- `processed/reports/external_sweeps/nevada-bar-results_public_safe_sweep.json`

Aggregate result:

- Files seen: 30,040
- Metadata-only candidate files: 221
- Quarantined files: 29,819
- File contents read: false
- SQLite opened: false
- Row-level data imported: false

Candidate role counts:

- workflow or governance docs: 11
- identity or schema design: 2
- opportunity signal design: 4
- test or validation gates: 12
- source intake or extraction code: 132
- implementation code: 53
- architecture docs: 7

Quarantine counts:

- row data or source snapshot lane: 29,180
- generated output or export lane: 537
- runtime cache or dependency noise: 100
- row data, bulk export, or scraped content by extension: 2

## Boundary Confirmed

- File contents are not read by the public-safe sweep.
- SQLite databases are not opened.
- CSV/XLSX/PDF/DOCX/ZIP/HTML/TXT contents are quarantined.
- Data and output lanes are quarantined.
- Generated sweep reports remain under `processed/` and are ignored by Git.
- Tracked evidence may describe methodology, aggregate categories, and workflow patterns only.

## Remaining Risks

- Existing local generated reports may contain aggregate SQLite table counts; those are ignored and should not be committed.
- Filenames can still reveal source structure, so tracked docs should use category descriptions rather than full private path listings.
- A future private row-level catalog would need separate approval, access control, retention policy, and source-terms review.

## Human Gate

No normal DAD scan or row-level import of the Nevada Bar Results folder is approved. Any future broadened scan needs explicit human approval and a private-store plan.
