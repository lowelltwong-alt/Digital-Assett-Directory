# Lesson Automation Next-Action Queue V1

Status: implemented as generated candidate queue. No human-gated action has
been approved or performed by this evidence.

## Purpose

The scan-cycle log says what has been checked and what should happen next. The
next-action queue makes that executable by consolidating prepared scope reports
into one review list. It tells Lowell or a future agent which human decision is
most ready next, what exact command or manual next step would follow approval,
and why approval is still required.

## Implemented Surfaces

- Command:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-next-actions --limit 25`
- Module:
  `src/digital_asset_directory/lesson_action_queue.py`
- Tests:
  `tests/test_lesson_action_queue.py`
- Generated outputs:
  `processed/reports/lesson_automation_next_actions.md`
  `processed/reports/lesson_automation_next_actions.json`
  `processed/reports/lesson_automation_next_actions_approval_prompt.md`

## Inputs

The command reads only generated DAD outputs:

- `processed/reports/scan_coverage_cycle.json`
- `processed/reports/priority_content_extract_scope.json`
- `processed/reports/repo_learning_loop_install_scope.json`
- `processed/reports/governance_map_adoption_scope.json`
- `processed/reports/ci_release_artifact_scope.json`

It does not read source file contents, recurse through source filesystems, call
GitHub, call models, mutate source repos, install hooks, or mark roadmap phases
complete.

## Methodology

Methodology version: `lesson-automation-next-action-queue-v0.1`

```text
priority_score = 100 * (0.30*scope_readiness + 0.25*lesson_yield + 0.20*safety_margin + 0.15*approval_specificity + 0.10*cycle_urgency)
```

Inputs:

- `scope_readiness`: whether a generated scope exists and the cycle status is
  ready for approval.
- `lesson_yield`: bounded estimate from candidate file/repo counts in generated
  scopes.
- `safety_margin`: deterministic caution factor by action family. Content
  extraction is safer than source-repo mutation; external API work is lowest.
- `approval_specificity`: whether the action has a concrete generated scope
  file or only an abstract gate.
- `cycle_urgency`: earlier cycle positions rank slightly higher when otherwise
  similar.

Scores are review routing only. They do not authorize content reads, source
repo writes, API calls, model calls, or promotion.

## Medium-Risk Review

Risk tier: medium.

Why not high: this queue influences future-agent routing, but it is generated
only, reversible, and does not change schemas, scoring defaults, source repos,
hooks, or roadmap gates.

Self red-team:

- A future agent might over-trust the highest score as approval.
- Existing scope reports can become stale after a new catalog scan.
- Source-repo mutation actions can appear as simple as generated-output actions
  unless human gates are explicit.
- CI/release artifacts may contain secrets and need a stricter extractor than
  ordinary docs.

Premortem:

The likely failure mode is a future agent running a recommended command without
a concrete human approval id, repo key, category, source boundary, byte cap, and
redaction plan.

Rollback:

Delete generated `processed/reports/lesson_automation_next_actions.*` outputs.
No source repos are touched.

## Context Boundaries

Applies when:

- a future agent or Lowell is choosing the next lesson-automation action from
  existing generated scopes;
- the goal is to avoid repeating broad scans while moving gated work toward
  explicit approval.

Does not apply when:

- the user already approved a specific repo, category, source mutation, or
  content read;
- the task is to inspect one named repo directly rather than choose among cycle
  gates.

Danger if misapplied:

A high queue priority can be mistaken for permission to read content, call APIs,
or mutate source repos. It is only a review-routing score.

## Validation To Date

- `PYTHONPATH=src python -m pytest tests/test_lesson_action_queue.py`:
  2 passed.
- Live run:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-next-actions --limit 25`
  wrote 7 generated candidate actions and performed 0 source repo mutations, 0
  content reads, 0 filesystem recursions, 0 GitHub calls, and 0 model calls.
- Live top action order:
  1. `priority_content_extracts` at 94.35
  2. `repo_learning_events` at 88.50
  3. `governance_map_adoption` at 86.65
  4. `ci_and_release_artifacts` at 83.35
- `PYTHONPATH=src python -m pytest tests/test_lesson_action_queue.py tests/test_lesson_automation_coverage.py`:
  5 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- `python -m pytest`: 233 passed.
- `PYTHONPATH=src python -m digital_asset_directory.cli validate`: valid,
  84 checked, 0 errors.
- `PYTHONPATH=src python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; phases 4 and 5 remain `boundary_deferred`.
