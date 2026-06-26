# Public-Safe Source Sweeps

Status: reusable workflow asset for private or sensitive local sources whose architecture is useful but whose rows must not be imported into a public DAD repository.

Use this when a folder contains valuable workflows, schemas, tests, scripts, prompts, or governance patterns mixed with scraped rows, public-person data, raw snapshots, exports, or other material that should stay out of tracked evidence.

## Core Rule

```text
private working corpus -> metadata-only architecture sweep -> generated candidate report -> curated public-safe evidence
```

The sweep is intentionally not a normal DAD source import. It does not read file contents, open SQLite databases, parse CSVs, extract profile facts, or catalog row-level records. It classifies paths by metadata only, quarantines data/output lanes, and writes generated reports under `processed/`.

## Command

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend public-safe-source-sweep `
  --source-path "<local private source>" `
  --source-id "<source-id>" `
  --review-sample 50
```

Generated outputs:

```text
processed/reports/external_sweeps/<source-id>_public_safe_sweep.md
processed/reports/external_sweeps/<source-id>_public_safe_sweep.json
```

These files are ignored by Git. Track only curated policy, methodology, and reusable workflow findings.

## Allowed Tracked Evidence

- Methodology and source-scope decision.
- Aggregate category counts.
- Reusable workflow, identity, schema, test, governance, and architecture patterns.
- Candidate-only graph or asset-family conclusions that do not include private rows.
- Stop conditions and human gates for any future private scan.

## Forbidden Tracked Evidence

- Scraped person rows or profile facts.
- Raw HTML/TXT snapshots, PDFs, DOCX files, spreadsheets, CSVs, SQLite rows, ZIP contents, or screenshots.
- Candidate recruiting, acquisition, liftout, or opportunity leads about specific people.
- Source URLs or local absolute paths when they would reveal private working structure.
- Secrets, tokens, credentials, or terms-restricted data.

## Default Quarantine Lanes

- `data/`, `raw/`, source snapshots, manual rosters, and page captures.
- `output/`, exports, dashboards, stakeholder packages, and generated deliverables.
- `.sqlite`, `.csv`, `.xlsx`, `.pdf`, `.docx`, `.zip`, `.html`, `.txt`, `.jsonl`, and similar row/bulk-data formats.
- Runtime caches and dependencies such as `__pycache__`, `.pytest_cache`, `.venv`, and `node_modules`.
- Ambiguous structured data unless it is clearly a schema, manifest, taxonomy, registry, roadmap, or config file.

## Reuse Conditions

Reuse this asset when:

- a private source has reusable workflow architecture;
- the eventual DAD repo may be public;
- row-level data is unnecessary for recognizing the asset family;
- a generated report can answer what to review next without exposing private records.

Do not reuse this as-is when:

- the user explicitly needs row-level private cataloging in a private/encrypted store;
- source terms prohibit even metadata inventory;
- filenames themselves contain sensitive facts;
- the workflow requires content-level extraction before it can be understood.

## Future Private Mode

If row-level evidence becomes necessary, use a separate private catalog mode or private repository with explicit approval, source-terms review, retention rules, and access controls. Do not mix that store with a public DAD branch.
