# Workflow Sweeps

Status: deterministic generated-candidate workflow discovery.

Workflow sweeps are ordered passes over the current catalog. They do not rescan, mutate source
repositories, install hooks, or promote candidates. They help future agents look for important
workflow assets in a deliberate order instead of searching one giant mixed report.

## Sweep Order

Run governance first:

1. Governance workflows
2. Learning and feedback workflows
3. Evaluation and calibration workflows
4. Agent and skill orchestration workflows
5. Retrieval and context workflows
6. Security and privacy workflows
7. Research and external-intake workflows
8. Duplicate and variant workflows
9. Scoring and ranking workflows
10. CI and validation workflows

Governance comes first because authority boundaries, source mutation policy, human gates,
review paths, and promotion rules determine how every later workflow should be interpreted.

## Command

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend workflow-sweeps --source-id all --review-sample 50
```

Generated reports are written under:

```text
processed/reports/workflow_sweeps/
```

The command also writes:

```text
processed/reports/workflow_sweeps/workflow_usefulness_review.md
processed/reports/workflow_sweeps/workflow_usefulness_candidates.jsonl
```

## Interpretation

Each sweep is candidate evidence. A match means "review this as a possible workflow asset,"
not "this asset is correct, complete, safe, or source-authoritative."

Obvious temp, worktree, dependency, and cache noise paths, such as pytest temp roots,
`_codex_worktrees`, virtual environments, `node_modules`, and cache folders, are excluded by
default. Use `--include-noise` only for archaeology-style review where fixture lineage is the
subject.

Use the sweep reports to:

- find high-leverage workflows across repos;
- identify which workflow families are missing tests, gates, labels, or feedback;
- choose the next human review batch;
- route follow-up asset-use feedback through the pay-forward loop.

## Usefulness Review

The usefulness review is a generated triage layer over the sweep samples. It separates:

- `review_first_for_reuse`
- `review_after_first_batch`
- `variant_or_delta_review`
- `keep_for_contextual_review`
- `low_signal_keep_as_evidence`
- `exclude_from_default_review`

The utility score is deterministic, candidate-only, and method-versioned as
`workflow-sweep-usefulness-v1`.

```text
utility_score = current_value_score
  + asset_type_bonus
  + min(evidence_count * 3, 18)
  + declared_pattern_bonus
  + path_class_adjustment
  + sweep_priority_bonus
```

Archive and copied repo variants can still be useful, but they route to delta review before
reuse. Current score remains separate from usefulness triage.
