# Lesson Automation Approval Packet V1

Status: implemented as a generated human-approval packet. No approval labels
were applied.

## Purpose

The lesson-automation queue had reached a human gate: pending decision rows
existed, but future agents still had to reconstruct exact approval commands from
chat or generated JSON. The approval packet makes that gate deterministic and
discoverable.

The packet prepares exact `lesson-automation-decision-label` commands for
pending rows. It does not run those commands, approve rows, execute downstream
actions, read source contents, mutate source repos, call GitHub, call models, or
mark roadmap phases complete.

## Implemented Surfaces

- Command:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-approval-packet`
- Generated outputs:
  `processed/reports/lesson_automation_approval_packet.md`
  `processed/reports/lesson_automation_approval_packet.json`
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

The live packet was generated from the current decision ledger.

- Decision rows: 7
- Pending rows: 7
- Recommended approvals: 1
- Recommended deferrals: 6
- Label commands generated: 7
- Labels applied: 0
- Commands executed: 0
- Source repos mutated: 0
- Content files read: 0
- GitHub calls: 0
- Model calls: 0

The single recommended approval is for `lesson-automation-decision-001`, a
bounded read-only priority content extract. The other pending rows are suggested
for deferral because they involve source-repo mutation, external API gates,
missing extractors, or no deterministic executor.

## Methodology

Methodology version:
`lesson-automation-approval-packet-v0.1`

Inputs:

- `processed/learning/lesson_automation_action_decisions.jsonl`
- referenced generated scope JSON files under `processed/reports/`

Rules:

- Only pending rows are included.
- `bounded_content_extract` may receive a suggested approve command when a
  generated scope exists.
- Source-repo writes, governance adoption, external APIs, missing extractors,
  and rows without deterministic executors receive suggested defer commands.
- Suggested approval uses generated scope repo keys, generated scope categories,
  byte/file caps, and redaction.
- The packet never writes reviewed labels; Lowell must approve or run a
  suggested command separately.

## Context Boundaries

Applies when:

- a future agent needs to present exact lesson-automation approve/defer commands;
- a pending decision ledger exists and no row should be silently approved;
- the work is still inside DAD's generated planning surfaces.

Does not apply when:

- a decision row has already been reviewed;
- the user is asking to execute a previously approved action;
- the source scope or privacy boundary has changed and scopes need regeneration.

Danger if misapplied:

- a generated command can be mistaken for human approval;
- stale scope rows can approve the wrong repo family or category;
- running all suggested commands would defer or approve more than Lowell chose.

## Risk Review

Risk tier: low.

Why not high: this command writes generated reports only. It changes no schema,
registry, scoring formula, roadmap gate, source repo, hook, external API path,
or model path.

Self red-team:

- Future agents may treat suggested commands as already approved.
- The recommended approval can become stale after a new scan.
- Approval packets can create a false sense that all pending rows should be
  labeled at once.

Premortem:

The most likely failure is copying a stale approve command after source scope
changes. The guard is to regenerate the packet, inspect repo keys, categories,
byte caps, file caps, and rationale, and apply only the specific row Lowell
approves.

Rollback:

Remove the command/helper functions and delete ignored generated
`processed/reports/lesson_automation_approval_packet.*` files. No source repos
need rollback.

## Validation

- `$env:PYTHONPATH='src'; python -m pytest tests/test_lesson_action_queue.py`:
  9 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- Live generation:
  `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-approval-packet`
  returned 7 pending rows, 1 recommended approval, 6 recommended deferrals, and
  0 labels applied.

- `python -m pytest`: 241 passed.
- `python -m ruff check src tests scripts noxfile.py`: passed.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate`:
  valid, 85 checked, 0 errors.
- `$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update`:
  passed; phases 4 and 5 remain `boundary_deferred`.
