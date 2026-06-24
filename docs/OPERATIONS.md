# Operations

## Generated outputs

```text
raw/<source>/<scan-id>.jsonl
processed/catalog/assets.jsonl
processed/graph/edges.jsonl
processed/graph/graph.json
processed/graph/graph.graphml
processed/alerts/alerts.jsonl
processed/alerts/alert_inbox.md
processed/reports/scan_summary.md
processed/context_packs/<timestamp>-<slug>.md
state/catalog.sqlite3
audit/events/audit.jsonl
```

## Recommended cadence

- scan active repos after material updates;
- run a broader portfolio scan daily or weekly, depending on corpus size;
- review high-value orphan and stale alerts weekly;
- review synergy and external research candidates before new builds;
- calibrate scores from accepted/rejected recommendations;
- archive generated snapshots according to storage policy.

## Failure behavior

- local source mutation: fail scan;
- invalid schema: fail validation;
- GitHub rate limit: preserve partial raw snapshot and report incomplete status;
- missing token: scan public repos only or skip GitHub, depending on config;
- unreadable/binary file: metadata-only record;
- secret-like file: exclude or metadata-only record with sensitivity flag.


## Scheduled change detection on Windows

After a successful reviewed first scan, register a daily read-only refresh:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_scheduled_scan.ps1 -DailyAt '02:30'
```

The task polls configured local and GitHub sources. It does not use webhooks, write into source repositories, or automatically promote generated findings. Remove it with `scripts\unregister_scheduled_scan.ps1`.

The optional whole-`C:\\` source in `config/sources.example.yaml` is disabled. Enable it only after reviewing exclusions; broad drive scans can encounter sensitive material and should start metadata-only or with narrower roots.
