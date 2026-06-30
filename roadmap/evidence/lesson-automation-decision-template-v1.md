# Lesson Automation Decision Template V1

Status: implemented as generated human-decision template. No action is approved
by default.

## Purpose

The next-action queue ranks gated lesson-automation work, but ranking is not
approval. This decision template records the exact human decision for each queued
action: approve, defer, or reject. Approved rows must include precise repo,
category, path, cap, and permission fields before any content read, source-repo
write, external API call, or model call can proceed.

## Implemented Surfaces

- Schema:
  `schemas/lesson-automation-decision.schema.json`
- Model:
  `LessonAutomationDecisionRecord`
- Commands:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-decision-template --limit 25`
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-decision-queue --status pending --limit 10`
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-decision-label ...`
- Generated outputs:
  `processed/learning/lesson_automation_action_decisions.jsonl`
  `processed/reports/lesson_automation_decision_template.md`
  `processed/reports/lesson_automation_decision_template.json`

## Live Result

The live template was generated from the current next-action queue.

- Template rows: 7
- Pending rows: 7
- Reviewed rows: 0
- Approved rows: 0
- Deferred rows: 0
- Rejected rows: 0
- Content-read approvals: 0
- Source-mutation approvals: 0
- External-API approvals: 0

The first pending row is `lesson-automation-decision-001` for
`priority_content_extracts`. It points at
`processed/reports/priority_content_extract_scope.json` and remains pending
until Lowell supplies exact repo/category/path selectors and caps.

## Fail-Closed Rules

- Content-read approvals require `approval_id`, reviewer, target selector,
  `allow_content_read=true`, positive `max_bytes_per_file`, positive
  `max_files`, and `redaction_required=true`.
- Source-repo write approvals require `allow_source_mutation=true` and a target
  repo selector.
- External API approvals require `allow_external_api=true`,
  `token_scope_note`, and `privacy_boundary_note`.
- Model-call approvals require `allow_model_call=true` and a
  `privacy_boundary_note`.
- Defer and reject decisions require rationale or notes.

Pending rows are generated candidates. They do not authorize any action.

## Risk Review

Risk tier: medium.

Why not high: this adds a fail-closed approval ledger and does not itself read
content, call APIs, mutate source repos, run models, change scoring, or alter
roadmap gates.

Self red-team:

- A future agent could treat a pending row as approval if it ignores
  `decision`.
- A human could approve too broad a repo family without specifying target
  selectors.
- A source-repo mutation approval could be confused with content-read approval
  unless the booleans stay separate.
- Generated decision files under `processed/` are not curated long-term
  roadmap evidence unless copied into tracked evidence later.

Premortem:

The likely failure mode is an agent running `priority-content-extract` with a
vague approval id but no exact repo/category/cap boundary. The label command
blocks that path by requiring target selectors and byte/file caps for approved
content reads.

Rollback:

Delete generated
`processed/learning/lesson_automation_action_decisions.jsonl` and
`processed/reports/lesson_automation_decision_template.*`; no source repos are
touched.

## Validation To Date

- `PYTHONPATH=src python -m pytest tests/test_lesson_action_queue.py tests/test_schema_conformance.py`:
  21 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- Live fail-closed check:
  `lesson-automation-decision-label` rejected an incomplete content-read approval
  with `Content-read approvals require positive byte and file caps.`
- `python -m pytest`: 236 passed.
- `PYTHONPATH=src python -m digital_asset_directory.cli validate`: valid,
  85 checked, 0 errors.
- `PYTHONPATH=src python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; phases 4 and 5 remain `boundary_deferred`.
