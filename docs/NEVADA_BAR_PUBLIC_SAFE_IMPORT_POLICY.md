# Nevada Bar Public-Safe Import Policy

Status: reviewed local-source boundary for the Nevada Bar Results asset family.

This policy exists because the Nevada Bar Results folder contains two different things:

- reusable workflow architecture that DAD should learn from;
- scraped or derived public-person/professional data that should not be imported into a DAD repository that may later become public.

## Decision

DAD may capture the Nevada Bar Results workflow shape, source-ordering lessons, schema ideas, scraper-variant patterns, review-gate patterns, and public-safe metadata-only inventory.

DAD must not import row-level scraped data, raw source snapshots, SQLite rows, CSV rows, attorney/profile facts, recruiting leads, candidate opportunity records, or generated stakeholder exports into tracked files.

## Approved Public-Safe Scope

- Workflow and architecture docs.
- Identity-model and data-dictionary concepts.
- Opportunity-signal taxonomy concepts, without person-level examples.
- Roadmap/check-gate design.
- Test and validation gate patterns.
- Script names and roles as metadata-only candidates.
- Scraper variant clusters as candidates for delta review, not as independently high-value assets.

## Excluded From Public DAD

- `data/`, `raw/`, source snapshots, manual rosters, page captures, and local scrape caches.
- `output/`, SQLite databases, CSV/XLSX exports, stakeholder packages, dashboards, and generated deliverables.
- HTML/TXT/PDF/DOCX/ZIP content.
- LinkedIn-like profile data, search-result rows, exception rows, and profile URLs.
- Person-specific recruiting, acquisition, liftout, rising-star, or opportunity claims.

## Safe Command

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend public-safe-source-sweep `
  --source-path "<local Nevada Bar Results folder>" `
  --source-id nevada-bar-results `
  --review-sample 80
```

This command writes generated outputs under `processed/reports/external_sweeps/` and does not read file contents or open SQLite. Those generated files are ignored by Git.

## Review Order

1. Curate the authority-first enrichment workflow.
2. Curate the person-vs-credential identity architecture.
3. Curate roadmap/check-gate lessons.
4. Cluster scraper variants before copying or reusing code.
5. Keep source-snapshot and SQLite architecture as private-source evidence only unless a separate private catalog is approved.

## Stop Conditions

Stop and ask before:

- running a normal DAD scan against the Nevada folder;
- adding the Nevada folder to `config/sources.local.yaml`;
- opening or summarizing the SQLite database for tracked evidence;
- reading CSV, HTML, TXT, PDF, DOCX, ZIP, or generated export content;
- creating person-specific examples in docs;
- copying scraper code into DAD or another repo without license, terms, privacy, and compatibility review.
