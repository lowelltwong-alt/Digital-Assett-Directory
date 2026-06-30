# Repo Completion Wave Plan V1

Status: implemented as a generated ordered wave plan. No wave was executed.

## Purpose

The repo completion dashboard shows blockers per repo. The wave plan turns those
blockers into an ordered path for completing repo coverage and automating
lessons learned without relying on chat memory.

It makes the current work sequence explicit:

1. approve bounded priority content extraction;
2. synthesize context-bound lesson candidates from generated observations;
3. select repos for files-only learning-loop installation;
4. select repo families for governance maps or child mirrors;
5. review AI navigation and validation gaps;
6. human-review any metadata-ready repos.

## Implemented Surfaces

- Command:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-completion-waves --dashboard-limit 500 --per-wave-repo-limit 25`
- Generated outputs:
  `processed/reports/repo_completion_wave_plan.md`
  `processed/reports/repo_completion_wave_plan.json`
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

The live wave plan was generated from the current repo completion dashboard.

- Repo count: 35
- Wave count: 6
- Content-read approval wave repos: 15
- Lesson-candidate synthesis wave repos: 15
- Learning-loop selection wave repos: 35
- Governance-map selection wave repos: 35
- AI navigation or validation review wave repos: 33
- Metadata-ready repos: 0
- Source repos mutated: 0
- Content files read: 0
- GitHub calls: 0
- Model calls: 0
- Roadmap phases marked complete: 0

## Methodology

Methodology version:
`repo-completion-wave-plan-v0.1`

The plan uses deterministic wave order, not calculated scores.

Inputs:

- repo completion dashboard blocker labels;
- lesson automation decision summary;
- presence of priority content observations.

Wave order:

- `content_read_approval_wave`;
- `lesson_candidate_synthesis_wave`;
- `repo_learning_loop_selection_wave`;
- `governance_map_selection_wave`;
- `ai_navigation_and_validation_review_wave`;
- `metadata_ready_review_wave`.

Each wave carries a human gate, generated next step, proof-to-advance list, and
danger-if-misapplied note.

## Context Boundaries

Applies when:

- a future agent needs an ordered path for completing repo lesson automation;
- the dashboard has generated blocker labels;
- source reads and writes still require human gates.

Does not apply when:

- Lowell has selected a specific repo and asked for direct work there;
- the catalog or scope reports are stale and need an approved refresh;
- the task is to verify source truth from actual repository contents.

Danger if misapplied:

- a generated wave can be mistaken for permission to execute that wave;
- broad learning-loop installs can create noisy source churn;
- content-read approval without caps and redaction can pull sensitive source
  material into generated outputs.

## Risk Review

Risk tier: low.

Why not high: the wave plan writes generated reports only. It changes no
schemas, scoring defaults, source repos, hooks, roadmap gates, approvals,
external access, or model paths.

Self red-team:

- The plan can look like an execution order rather than a human-gated order.
- Wave counts depend on the current generated dashboard and scope reports.
- A later scan could move repos between waves.
- Metadata-ready repos still require human review and are not complete by
  default.

Premortem:

The likely failure is a future agent running the next command in each wave
without checking proof-to-advance. The guard is to treat every wave as generated
candidate guidance and require the listed proof before moving to the next wave.

Rollback:

Remove the wave command/helper functions and delete ignored generated
`processed/reports/repo_completion_wave_plan.*` files. No source repos need
rollback.

## Validation

- `$env:PYTHONPATH='src'; python -m pytest tests/test_repo_completion.py`:
  4 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- Live generation:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend repo-completion-waves --dashboard-limit 500 --per-wave-repo-limit 25`
  returned 35 repos, 6 waves, 15 content-read wave repos, and 0 source
  mutations/content reads/API/model calls.

- `python -m pytest`: 245 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate`:
  valid, 85 checked, 0 errors.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; phases 4 and 5 remain `boundary_deferred`.
