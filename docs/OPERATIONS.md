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

## Operational readiness

Use `doctor` when you need one local check that DAD is wired up and has the
generated surfaces needed by future agents:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli doctor
```

The command writes:

```text
processed/reports/operational_readiness.md
processed/reports/operational_readiness.json
```

It checks the front door, machine manifest, catalog database, generated graph,
scan summary, alert inbox, workflow-part usage guidance, roadmap gates, and
schema validation state. It does not scan, call GitHub, mutate source repos,
mark roadmap gates complete, or promote generated outputs to truth.

If it exits non-zero, read the warnings and run only the specific recommended
commands needed to restore the missing surface. A clean clone may be code-valid
while not locally operational because generated `processed/` and `state/`
outputs are intentionally ignored.

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

Scheduled scans are not approved by the current Phase 5 boundary. Treat this as a
future operations template only. After a separate human gate approves scheduled
scans, register a daily read-only refresh:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_scheduled_scan.ps1 -DailyAt '02:30'
```

The task polls configured local and GitHub sources. It does not use webhooks, write into source repositories, or automatically promote generated findings. Remove it with `scripts\unregister_scheduled_scan.ps1`.

The optional whole-`C:\\` source in `config/sources.example.yaml` is disabled. Enable it only after reviewing exclusions; broad drive scans can encounter sensitive material and should start metadata-only or with narrower roots.
