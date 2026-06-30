# Repo Completion Dashboard V1

Status: implemented as a generated repo-by-repo blocker dashboard. No source
repos were mutated.

## Purpose

The long-running objective is to cover all repos and automate lessons learned,
but the current blocker is distributed across multiple generated scopes and
human gates. This dashboard gives future agents one generated view of each
cataloged repo's lesson-automation blockers before they rescan, read content, or
write files.

## Implemented Surfaces

- Command:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-completion-dashboard --limit 100`
- Generated outputs:
  `processed/reports/repo_completion_dashboard.md`
  `processed/reports/repo_completion_dashboard.json`
- Navigation:
  `AI_FRONT_DOOR.md`
  `AI_TABLE_OF_CONTENTS.md`
  `MACHINE_NAVIGATION_MANIFEST.json`
  `docs/LESSON_AUTOMATION_COVERAGE.md`
  `docs/OPERATIONS.md`
- Code:
  `src/digital_asset_directory/repo_completion.py`
  `src/digital_asset_directory/cli.py`
  `src/digital_asset_directory/lesson_automation_coverage.py`
- Tests:
  `tests/test_repo_completion.py`

## Live Result

The live dashboard was generated from the current catalog and generated scope
files.

- Repo records: 35
- Noise/temp repo groups skipped: 108
- Groups without repo assets skipped: 38
- `blocked_by_content_read_gate`: 15 repos
- `blocked_by_source_repo_governance_gate`: 20 repos
- Pending lesson-automation decisions: 7
- Approved lesson-automation decisions: 0
- Content-read approvals: 0
- Source-mutation approvals: 0
- Source repos mutated: 0
- Content files read: 0
- GitHub calls: 0
- Model calls: 0

## Methodology

Methodology version:
`repo-completion-dashboard-v0.1`

The dashboard uses deterministic status labels, not calculated scores.

Inputs:

- catalog repository assets and logical paths;
- `processed/reports/priority_content_extract_scope.json`;
- `processed/reports/repo_learning_loop_install_scope.json`;
- `processed/reports/governance_map_adoption_scope.json`;
- `processed/reports/ci_release_artifact_scope.json`;
- `processed/learning/lesson_automation_action_decisions.jsonl`;
- `processed/reports/lesson_automation_approval_packet.json`;
- `processed/reports/lesson_automation_execution_plan.json`.

Output labels:

- `metadata_completion_ready_for_human_review`;
- `blocked_by_content_read_gate`;
- `blocked_by_source_repo_governance_gate`;
- `metadata_incomplete`.

Noise/temp/worktree repo groups are skipped using deterministic path and
instance-class markers. Priority-content scope categories can show that an AI
navigation or validation surface is queued but unread; the dashboard then uses
the content-read gate rather than falsely claiming the surface is absent.

## Context Boundaries

Applies when:

- a future agent needs a repo-by-repo blocker map before scanning or installing
  anything;
- the user asks what remains to complete repo coverage and lesson automation;
- DAD should start from generated status surfaces instead of chat memory.

Does not apply when:

- the user has approved a direct source-repo mutation or content read for one
  named repo;
- the catalog is stale and a new approved scan is required;
- source truth must be established from actual repo contents.

Danger if misapplied:

- generated completion states can be mistaken for proof a repo is complete;
- a queued content surface can be mistaken for reviewed content;
- source-repo learning-loop or governance blockers can be mistaken for
  permission to write files.

## Risk Review

Risk tier: low.

Why not high: this dashboard writes generated reports only. It changes no
schemas, scoring defaults, source repos, hooks, roadmap gates, approvals,
external access, or model calls.

Self red-team:

- Per-repo blockers depend on the last catalog and generated scope files.
- Metadata can miss repo-local files excluded by scan configuration.
- A repo can be valuable even if it lacks DAD learning-loop or governance
  surfaces.
- The dashboard can encourage broad source-repo installs unless the human gate
  is respected.

Premortem:

The likely failure is a future agent treating `blocked_by_source_repo_governance_gate`
as permission to install files across many repos. The guard is to route through
the approval packet and decision ledger first, and to install files only after
Lowell selects exact repo paths and write permission.

Rollback:

Remove the command/helper module and delete ignored generated
`processed/reports/repo_completion_dashboard.*` files. No source repos need
rollback.

## Validation

- `$env:PYTHONPATH='src'; python -m pytest tests/test_repo_completion.py`:
  2 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- Live generation:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-completion-dashboard --limit 100`
  returned 35 repo records, 108 skipped noise/temp groups, 15 content-read
  gate blockers, and 20 source-repo governance gate blockers.

- `python -m pytest`: 243 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate`:
  valid, 85 checked, 0 errors.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; phases 4 and 5 remain `boundary_deferred`.
