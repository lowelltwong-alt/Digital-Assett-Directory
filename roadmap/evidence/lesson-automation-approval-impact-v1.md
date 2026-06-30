# Lesson Automation Approval Impact V1

## Summary

Implemented a generated approval-impact brief for pending lesson-automation
decisions. The first use case is `lesson-automation-decision-001`, the bounded
priority-content extraction gate currently blocking repo-completion wave 1.

The brief exists to help Lowell decide whether to approve, narrow, defer, or
reject a generated approval command before any content is read.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend lesson-automation-approval-impact --sample-id lesson-automation-decision-001
```

Generated outputs:

```text
processed/reports/lesson_automation_approval_impact.md
processed/reports/lesson_automation_approval_impact.json
```

## Methodology

Methodology version: `lesson-automation-approval-impact-v0.4`

The command reads only generated DAD surfaces:

- `processed/learning/lesson_automation_action_decisions.jsonl`;
- generated approval packet data;
- `processed/reports/priority_content_extract_scope.json`.

It does not:

- apply labels;
- approve actions;
- execute commands;
- read source contents;
- mutate source repos;
- call GitHub or models;
- mark roadmap phases complete.

## Live Result

The live brief for `lesson-automation-decision-001` reported:

- recommended decision: `approve`;
- proposed repo count: 5;
- proposed category count: 6;
- matched candidate paths: 40;
- candidate paths shown: 40;
- truncated candidate paths: 0;
- max bytes per file: 20,000;
- max files: 50;
- max possible bytes if later executed: 800,000;
- labels applied: 0;
- commands executed: 0;
- content files read: 0;
- source repos mutated: 0;
- GitHub/model calls: 0 / 0.

The brief intentionally exposes the candidate path list in generated outputs so
Lowell can decide whether the proposed scope is too broad, includes noisy
inspection/extract paths, or should be narrowed before approval.

After scope-hygiene hardening, the live brief reports:

- hygiene-flagged candidate paths: 6;
- unflagged candidate paths: 34;
- hygiene rules observed:
  - `backup_or_snapshot_variant`: 3;
  - `fixture_or_seed_pack_path`: 1;
  - `inspection_or_extract_path`: 2;
  - `private_or_sensitive_name`: 1;
- suggested human decision: `narrow_before_approval`.

The generated approval command remains visible for review, but the generated
recommendation is no longer "approve as-is" when flagged path classes are
present. The safe next human action is to narrow the repo/category/path scope or
explicitly approve those flagged classes for this exact action.

V0.3 adds executable path constraints:

- decision labels can record `approved_include_paths` and
  `approved_exclude_paths`;
- `priority-content-extract` accepts `--include-path` and `--exclude-path`;
- the execution plan carries those constraints into the generated extractor
  command;
- the live impact brief now emits a clean-subset approval command with 34
  explicit include paths, 6 flagged paths excluded, `max_files=34`, and max
  possible bytes reduced from 800,000 to 680,000.

The clean-subset command is still only generated guidance. It does not approve a
decision, update the ledger, read source content, or mutate any source repo.

V0.4 makes the clean-subset approval reviewable without a very long command:

- `lesson-automation-decision-label` accepts `--include-path-file` and
  `--exclude-path-file`;
- `priority-content-extract` accepts the same file options for direct bounded
  runs;
- the generated clean-subset command points at
  `processed/reports/lesson_automation_approval_impact.json`;
- the CLI expands that file and stores the exact include/exclude paths in the
  reviewed decision record before any execution plan can run.

## Red Team

- Risk: a generated impact brief could be mistaken for approval.
  Guard: the brief states that it does not apply labels or execute commands.
- Risk: the proposed content-read scope may include stale, nested, inspection,
  or private working paths.
  Guard: deterministic scope-hygiene flags identify inspection/extract paths,
  backup or snapshot variants, fixture or seed-pack paths, and private-looking
  names. Any flagged path changes the generated suggested human decision to
  `narrow_before_approval`.
- Risk: a narrowed command could be shown but not enforced later.
  Guard: the decision contract, execution-plan command, and extractor now carry
  exact include/exclude path filters.
- Risk: an exact clean-subset command can become too long for reliable human
  review.
  Guard: path-filter files keep the human-facing command compact while still
  expanding into exact stored paths before execution.
- Risk: byte caps can create false comfort.
  Guard: the report gives the maximum possible bytes if later executed, but
  still treats source content as human-gated.
- Risk: deterministic path/category matching can overstate usefulness.
  Guard: category matching is framed as routing metadata, not evidence that the
  content is useful or safe.

## Current Boundary

This feature does not unblock wave 1 by itself. It provides the review packet
needed before Lowell decides whether to approve, narrow, defer, or reject
`lesson-automation-decision-001`.

After any human decision:

1. Run only the exact human-approved `lesson-automation-decision-label` command.
2. Regenerate `lesson-automation-execution-plan`.
3. Inspect the generated extraction command.
4. Run extraction only if it exactly matches the approved repo keys,
   categories, caps, and approval id.
5. Regenerate `repo-completion-proof-check`.

## Validation

Focused validation:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests\test_lesson_action_queue.py
python -m ruff check src\digital_asset_directory\lesson_action_queue.py src\digital_asset_directory\cli.py tests\test_lesson_action_queue.py src\digital_asset_directory\lesson_automation_coverage.py
```

Results:

- focused pytest: 11 passed;
- focused ruff: all checks passed.

Full validation was run after implementation and recorded in the agent
postflight for this session.
