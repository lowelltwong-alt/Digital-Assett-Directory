# Contextual Learning And Worktree Archaeology

## Purpose

Worktrees, temp repos, changelogs, local git history, repeated file variants, CI
artifacts, handoffs, and review packets can reveal how work actually unfolded. This
layer turns those traces into generated candidate evidence so future agents can ask:

- What failed repeatedly?
- What stabilizer appeared late?
- Which files or concepts tended to change together?
- What order probably would have reduced rework?
- When is the lesson useful, and when would it be dangerous?

## Safety Rule

A lesson without context is unsafe. Every counterfactual lesson candidate must include:

- `applies_when`
- `does_not_apply_when`
- `danger_if_misapplied`
- `counterfactual_better_order`
- `context_tags`
- source events and evidence assets

These fields constrain future use. They do not prove the lesson is true.

## Archaeology Signals

The deterministic v1 looks for:

- worktree, archive, and temp-fixture path patterns;
- repeated failure words such as error, regression, revert, drift, false positive, and false negative;
- late stabilizers such as tests, schemas, validators, review gates, and gold packets;
- co-changing files in bounded local git history;
- changelog and review-packet themes;
- same file names appearing across multiple attempts.

Generated records are written under `processed/learning/` and generated reports under
`processed/reports/`. They are review queues, not source-truth.

## Repo-Local Learning Loop

Downstream repositories may opt in to a files-only learning loop:

```text
.digital-asset-directory/learning/README.md
.digital-asset-directory/learning/context-tags.yaml
.digital-asset-directory/learning/events.jsonl
```

Agents can append `before_work`, `during_failure`, `after_work`, and `review` events
using `asset-dir lesson repo-event`. Those events are untrusted candidate evidence
until reviewed by the hub.

Hooks are intentionally out of scope for the default installation mode.
