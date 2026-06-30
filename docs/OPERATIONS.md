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
processed/learning/scan_cycle_events.jsonl
processed/learning/learning_rule_promotion_candidates.jsonl
processed/reports/repo_learning_loop_install_scope.md
processed/reports/ci_release_artifact_scope.md
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
processed/learning/scan_cycle_events.jsonl
```

It reads current catalog records, scan metadata, config metadata, and generated
report presence. It does not rescan, read source contents, call GitHub, inspect
CI logs, call models, mutate source repos, install hooks, or promote generated
gaps to truth.

`processed/reports/scan_coverage_cycle.md` is the latest handoff. The append-only
`processed/learning/scan_cycle_events.jsonl` file is the generated event trail
that lets later agents see what prior passes checked, skipped, and recommended
next.

Use `recommend lesson-automation-next-actions` after scope reports exist to
choose the next human-gated action without rereading every scope:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-next-actions --limit 25
```

The command writes:

```text
processed/reports/lesson_automation_next_actions.md
processed/reports/lesson_automation_next_actions.json
processed/reports/lesson_automation_next_actions_approval_prompt.md
```

It reads only generated scope reports and the scan-cycle log. It does not
rescan, read source contents, call GitHub, call models, mutate source repos,
install hooks, or mark roadmap phases complete. Its priority score is review
routing only.

Use `recommend repo-learning-loop-scope` before installing repo-local learning
files into any source repo:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-learning-loop-scope --limit 50
```

The command writes:

```text
processed/reports/repo_learning_loop_install_scope.md
processed/reports/repo_learning_loop_install_scope.json
processed/reports/repo_learning_loop_install_approval_prompt.md
```

It recommends candidate repos for files-only learning-loop installation but
does not write to those repos. After Lowell explicitly selects a repo, install
with:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli agent install-learning-loop --repo "<repo-path>" --mode files-only
```

Use `recommend governance-map-scope` before installing cross-repo governance
dependency maps, child mirrors, validators, tests, or PR disclosure sections:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend governance-map-scope --limit 50
```

The command writes:

```text
processed/reports/governance_map_adoption_scope.md
processed/reports/governance_map_adoption_scope.json
processed/reports/governance_map_adoption_approval_prompt.md
```

It is metadata-only. It does not read source file contents, recurse through
source filesystems, call GitHub, call models, mutate source repos, install
hooks, or mark roadmap phases complete. It routes a later human choice of which
repo family should receive the `templates/cross-repo-governance-dependency-map/`
pattern first.

Use `recommend priority-content-scope` before any bounded content pass:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-scope --limit 200 --per-repo-limit 12
```

The command writes:

```text
processed/reports/priority_content_extract_scope.md
processed/reports/priority_content_extract_scope.json
processed/reports/priority_content_extract_approval_prompt.md
```

It lists candidate file paths already present in the catalog and creates a
fresh-eyes approval prompt. It still reads no source file contents.

Use `recommend ci-release-scope` before reading CI logs, release notes,
changelogs, QA reports, dependency locks, or build artifacts:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend ci-release-scope --limit 200 --per-repo-limit 12
```

The command writes:

```text
processed/reports/ci_release_artifact_scope.md
processed/reports/ci_release_artifact_scope.json
processed/reports/ci_release_artifact_approval_prompt.md
```

It is metadata-only. It does not read artifact contents, recurse through source
filesystems, call GitHub, call CI services, call models, mutate source repos, or
promote candidate findings to truth.

After human approval, use `recommend priority-content-extract` to read only
approved paths from the scope file:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-extract `
  --approval-id "<human-approval-id>" `
  --repo-key "<catalog-repo-key>" `
  --category ai_navigation `
  --max-bytes-per-file 20000 `
  --limit 50
```

It fails closed without an approval id, repo key, and category. It writes
generated observations under `processed/learning/` and a generated report under
`processed/reports/`; it does not mutate source repos.

After generated observations exist, use `recommend priority-content-lessons` to
create context-bound lesson candidates:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lessons --min-observations 1 --limit 100
```

The command writes generated `CounterfactualLessonRecord` candidates under
`processed/learning/` and a generated review report under `processed/reports/`.
It does not read source repos or promote lesson candidates into reviewed
learning rules.

Create the human review queue:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-template --sample-size 100
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-review-queue --status pending --limit 10
```

Apply labels only after human approval with
`recommend priority-content-lesson-review-label`, then inspect
`recommend priority-content-lesson-review-summary`. Accepted review-use examples
remain candidates; promotion to deterministic learning rules is a separate
future gate.

After review, package generated promotion candidates without editing the rule
registry:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lesson-promotion-candidates --limit 100
```

This writes `processed/learning/learning_rule_promotion_candidates.jsonl` plus
markdown/JSON reports. It does not mutate `registry/learning-rule-registry.json`.

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
