# Contextual Learning And Worktree Archaeology Evidence

Status: generated candidate evidence only; no roadmap phase is complete because of this file.

Generated on: 2026-06-25

Source scope:
- Current local Digital Asset Directory catalog only.
- GitHub scanning remained deferred.
- Source repositories were not mutated.
- Repo learning-loop installation was implemented as an opt-in files-only command and was not applied to any external repo.

Generated outputs:
- `processed/reports/worktree_archaeology.md`
- `processed/reports/root_cause_lesson_candidates.md`
- `processed/reports/context_tag_coverage.md`
- `processed/learning/worktree_attempts.jsonl`
- `processed/learning/repo_timeline_events.jsonl`
- `processed/learning/change_patterns.jsonl`
- `processed/learning/failure_signals.jsonl`
- `processed/learning/root_cause_hypotheses.jsonl`
- `processed/learning/counterfactual_lessons.jsonl`
- `processed/learning/repo_learning_events.jsonl`

Observed counts:
- Worktree/archive/temp/repository attempts: 377
- Bounded local timeline events: 1701
- Change patterns: 300
- Failure-like signals: 12257
- Repo learning events found in scanned repos: 0
- Root-cause hypotheses: 1
- Counterfactual lesson candidates: 1

Candidate lesson surfaced:

In similar contexts, establish the smallest validation/review route before promoting outputs or expanding implementation.

Context bounds:
- Applies when a task has route, schema, evaluation, promotion, or source-authority risk.
- Applies when failure-like signals appear before validation, review, or gold artifacts are stable.
- Does not apply when the source sequence is unknown or the stabilizer was present before the failure.
- Does not apply when work is exploratory and intentionally pre-contract.
- Danger if misapplied: it can turn every exploratory task into a heavy governance exercise and hide genuine requirement changes.

False-positive risks:
- Temp folders, archives, fixtures, copied repos, and generated files dominate the signal field.
- Failure words such as `fail`, `error`, `todo`, and `regression` are weak evidence without local context.
- Co-occurrence does not prove causation; every root-cause hypothesis remains candidate-only.
- Context tags route attention but do not prove value, truth, or applicability.

Human review still needed:
- Review the top archaeology samples for active-source versus temp/archive noise.
- Confirm or reject the single counterfactual lesson candidate.
- Decide whether repo-local learning-loop files should be installed in any selected downstream pilot repo.
