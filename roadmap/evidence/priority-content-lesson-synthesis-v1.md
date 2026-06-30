# Priority Content Lesson Synthesis V1

## Summary

Implemented generated lesson-candidate synthesis from bounded priority-content
observations. The command consumes existing generated observations under
`processed/` and emits context-bound `CounterfactualLessonRecord` candidates.

No live source repos are read by this synthesis step. In the current repo state,
live priority-content observations have not been generated yet; tests use
synthetic observations only.

## Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend priority-content-lessons --min-observations 1 --limit 100
```

Generated outputs:

- `processed/learning/priority_content_lesson_candidates.jsonl`
- `processed/reports/priority_content_lesson_candidates.md`
- `processed/reports/priority_content_lesson_candidates.json`

## Contract

Every generated lesson candidate uses `CounterfactualLessonRecord` and includes:

- `applies_when`
- `does_not_apply_when`
- `danger_if_misapplied`
- `counterfactual_better_order`
- `source_events`
- `context_tags`
- `review_status="generated_candidate"`

## Authority Boundary

Generated lesson candidates only. The command consumes bounded priority-content
observations already written under `processed/`; it does not read source repos,
call GitHub, call models, mutate downstream repos, install hooks, or promote
lessons to truth.

## Risk Tier

Medium.

Reason: lesson candidates can shape future agent behavior if over-trusted, but
the command does not read live sources and keeps all output candidate-only.

## Applies When

- Generated priority-content observations exist.
- A future agent needs reviewable candidate lessons from observed AI navigation,
  schema/contract, governance, learning-loop, or workflow/dataflow signals.
- The goal is to prepare human review, not to promote a deterministic rule.

## Does Not Apply When

- No priority-content observations exist.
- The task needs raw content extraction or direct repo inspection.
- The candidate would be promoted to preflight behavior without human review.

## Danger If Misapplied

- A generated lesson can become harmful if stripped from its source repo,
  signal family, or non-applicability context.
- Bounded observations may be incomplete excerpts, so candidates can miss
  exceptions or contradictory repo guidance.
- Multiple weak observations can create false confidence if treated as reviewed
  learning rules.

## Red-Team

- False positives: generic words such as schema, gate, or workflow can produce
  plausible but too-broad lessons.
- False negatives: useful lessons may hide in content without the current signal
  terms.
- Promotion risk: candidates must not become deterministic learning rules until
  reviewed and accepted.
- Context risk: each candidate carries applies/does-not-apply/danger fields to
  constrain reuse.

## Premortem

Failure mode: a future agent treats generated lesson candidates as reviewed
rules and changes preflight defaults.

Guard: outputs remain `generated_candidate`; evidence and docs require human
review before promotion.

Failure mode: no observations exist, but the command invents lessons anyway.

Guard: the command fails closed when the observations file is missing, empty, or
does not produce candidates.

Failure mode: one repo's AI navigation pattern becomes a universal rule.

Guard: lesson text is repo-scoped and every candidate includes
`does_not_apply_when` and `danger_if_misapplied`.

## Validation

Focused tests cover:

- missing/empty observation files fail closed;
- generated lesson candidates validate against `CounterfactualLessonRecord`;
- candidates include applicability, non-applicability, danger, better order, and
  source events;
- coverage-cycle status advances to `lesson_candidates_synthesized` only when
  generated lesson outputs exist.

## Acceptance Status

Implemented and tested with synthetic observations. Live synthesis waits for a
human-approved priority-content extraction pass.
