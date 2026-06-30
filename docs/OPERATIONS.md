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

## Manual task queue

Use `recommend manual-tasks` after a scan, doctor run, and workflow-part guidance
refresh when you need the safest next human-review tasks:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend manual-tasks --limit 25 --family-limit 12
```

The command writes:

```text
processed/reports/manual_task_queue.md
processed/reports/manual_task_queue.json
```

It re-ranks the current open alerts for manual review using a cited deterministic
formula and joins them with reviewed workflow-part guidance. It does not rescan,
mutate source repositories, promote graph edges to truth, change current value
scores, or mark roadmap phases complete.

## Repo buildout advisor

Use `recommend repo-buildout` when you want generated, repo-specific advice for
one cataloged repository:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-buildout --repo "git-projects/04_Digital_Assett_Directory" --limit 10
```

The command writes:

```text
processed/reports/repo_buildout/<repo_slug>.md
processed/reports/repo_buildout/<repo_slug>.json
processed/reports/repo_buildout/<repo_slug>_fresh_eyes_prompt.md
processed/reports/repo_buildout/index.md
```

It reads the existing catalog database and optional generated reports when
present. It does not rescan, mutate the target repo, call GitHub, call models,
install hooks, promote candidates to truth, change scores, or mark roadmap
phases complete.

## Lesson automation coverage

Use `recommend lesson-automation-coverage` when you need to know what has not
been scanned or instrumented yet, and you do not want to repeat prior broad
passes:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-coverage --limit 50
```

The command writes:

```text
processed/reports/lesson_automation_coverage.md
processed/reports/lesson_automation_coverage.json
processed/reports/scan_coverage_cycle.md
processed/reports/scan_coverage_cycle.json
```

It reads current catalog records, scan metadata, config metadata, and generated
report presence. It does not rescan, read source contents, call GitHub, inspect
CI logs, call models, mutate source repos, install hooks, or promote generated
gaps to truth.

## Template library

Use `templates check` when you need to validate DAD's reusable template library,
review stale templates, or inspect direct and reverse dependencies:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli templates check
```

The command writes:

```text
processed/reports/template_library.md
processed/reports/template_library.json
```

Use no-write validation when you only need the registry check:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli templates validate
```

Template improvement is recommend-only in v1. The checker may flag due templates
and dependency impacts, but it does not rewrite templates, install hooks, mutate
downstream repositories, or propagate updates without a separate human-approved
patch workflow.

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
