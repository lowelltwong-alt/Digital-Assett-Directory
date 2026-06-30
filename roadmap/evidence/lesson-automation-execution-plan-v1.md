# Lesson Automation Execution Plan V1

Status: implemented as generated execution-plan bridge. No approved action was
executed.

## Purpose

The lesson-automation decision template records human approvals, deferrals, and
rejections. This execution plan is the next bridge: it turns reviewed approved
rows into exact command text or manual next steps while keeping execution
separate.

This prevents a future agent from treating the next-action queue or a pending
decision row as permission to read source contents, mutate source repos, call
GitHub, call models, or mark roadmap phases complete.

## Implemented Surfaces

- Command:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-execution-plan`
- Generated outputs:
  `processed/reports/lesson_automation_execution_plan.md`
  `processed/reports/lesson_automation_execution_plan.json`
- Navigation:
  `AI_FRONT_DOOR.md`
  `AI_TABLE_OF_CONTENTS.md`
  `MACHINE_NAVIGATION_MANIFEST.json`
  `docs/LESSON_AUTOMATION_COVERAGE.md`
  `docs/OPERATIONS.md`
- Code:
  `src/digital_asset_directory/lesson_action_queue.py`
  `src/digital_asset_directory/cli.py`
  `src/digital_asset_directory/lesson_automation_coverage.py`
- Tests:
  `tests/test_lesson_action_queue.py`

## Live Result

The live generated plan was run against
`processed/learning/lesson_automation_action_decisions.jsonl`.

- Decision rows: 7
- Approved rows: 0
- Pending rows: 7
- Deferred or rejected rows: 0
- Execution entries: 0
- Ready-for-manual-run entries: 0
- Commands executed: 0
- Source repos mutated: 0
- Content files read: 0
- GitHub calls: 0
- Model calls: 0

This is the correct fail-closed result while all decision rows remain pending.

## Methodology

Methodology version:
`lesson-automation-execution-plan-v0.1`

The command reads only the generated decision ledger. A row is eligible only
when `decision="approve"` and `review_status="reviewed"`. Each approved row is
validated with the same fail-closed checks used by the decision-label command.

For bounded priority content extraction, the plan can produce a
`priority-content-extract` command using only the approved approval id, repo
keys, categories, scope file, byte cap, and file cap from the decision record.
For source-repo files-only installs, it emits install commands only when exact
repo paths are already approved. Governance-map adoption, external APIs, and
missing extractors remain manual or blocked steps.

No new priority score is introduced. When priority context is needed, use the
existing lesson-automation next-action formula as review-routing evidence only:

```text
priority_score = 100 * (0.30*scope_readiness + 0.25*lesson_yield + 0.20*safety_margin + 0.15*approval_specificity + 0.10*cycle_urgency)
```

## Scan-Cycle Link

Future agents should read `processed/reports/scan_coverage_cycle.md` and
`processed/learning/scan_cycle_events.jsonl` before using this plan. Those
generated surfaces record what was checked, what was intentionally skipped, and
which signal families are next in the cycle.

The execution-plan output is now included in lesson-automation coverage output
presence checks so future coverage runs can report that the bridge already
exists instead of repeating setup work.

## Risk Review

Risk tier: medium.

Why not high: this bridge writes generated command text only. It does not run
commands, read source files, mutate source repos, call APIs, call models, change
scores, alter registries, or complete roadmap gates.

Self red-team:

- A future agent could confuse a generated command with a completed action.
- A future agent could copy a command and broaden repo keys or byte caps.
- Source-repo install commands would mutate downstream repos if run without
  verifying the exact approval row.
- Manual governance adoption could imply upstream authority if the human gate
  is skipped.
- The generated `processed/` plan is ignored by Git, so this evidence file must
  summarize the implemented behavior.

Premortem:

The most likely failure is an agent running a generated command from an outdated
approval row after the source scope or privacy boundary changed. The guard is to
read the scan-cycle log first, re-run the execution-plan command, and verify the
approval id, repo keys, categories, byte cap, file cap, and stop conditions
before executing anything manually.

Rollback:

Remove the CLI command and helper functions, then delete ignored generated files
under `processed/reports/lesson_automation_execution_plan.*`. No source repos
need rollback because this implementation does not touch them.

## Validation

- `$env:PYTHONPATH='src'; python -m pytest tests/test_lesson_action_queue.py tests/test_lesson_automation_coverage.py`:
  10 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- Live generation:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-execution-plan`
  returned 7 decisions, 0 approved, 0 execution entries, and 0 commands
  executed.

- `python -m pytest`: 239 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate`:
  valid, 85 checked, 0 errors.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; phases 4 and 5 remain `boundary_deferred`.
