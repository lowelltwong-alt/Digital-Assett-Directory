# Workflow Part Usage Guidance Evidence

Evidence date: 2026-06-29

## Decision

Add a manual generated guidance surface for reviewed workflow-part labels:

```powershell
python -m digital_asset_directory.cli recommend workflow-part-guidance --limit 50
```

Generated outputs:

- `processed/reports/workflow_part_usage_guidance.md`
- `processed/workflow_parts/workflow_part_usage_guidance.json`

Tracked source evidence:

- `roadmap/evidence/workflow-part-calibration.md`
- `roadmap/evidence/workflow-part-calibration-review-path.md`
- `docs/BACKGROUND_CONNECTION_RADAR.md`

## Risk Tier

`risk_tier=medium`

Why not high:

- The command is manual and opt-in.
- It does not change preflight output, scoring, roadmap status, graph truth, or source-repo files.
- It writes only ignored generated outputs under `processed/`.
- Automatic preflight surfacing, workflow assembly packs, score influence, and cross-repo installation remain deferred behind a separate high-risk human gate.

Known downstream consumers:

- AI agents building context packs or reviewing workflow reuse.
- Future background-radar or workflow-assembly planning.
- Human reviewers deciding whether a candidate is review-use, human-gated, rejected, or deferred.

## Methodology

Methodology version: `workflow-part-usage-guidance-v0.1`

Inputs:

- `processed/workflow_parts/workflow_part_review_template.jsonl`
- `WorkflowPartReviewRecord.decision`
- `WorkflowPartReviewRecord.usefulness`
- `WorkflowPartReviewRecord.safety`
- `WorkflowPartReviewRecord.specificity`
- `WorkflowPartReviewRecord.dataflow_completeness`
- structured review notes

Gate:

- Reuses `summarize_workflow_part_reviews`.
- Fails closed unless `calibration_gate_complete=true`.

Deterministic routing:

- `accept_for_review_use` becomes manual review-use context only.
- `needs_human_gate` requires explicit human approval before reuse across repos or authority boundaries.
- `reject_candidate` becomes false-positive, noise, temp-fixture, marker-file, or lineage evidence only.
- `defer` requires manual review before use.
- Accepted candidates with missing inputs, outputs, side effects, or unsure dataflow require declared dataflow before assembly.

No calculated score is introduced. Counts are direct deterministic aggregates from reviewed labels.

## Applies When

- An agent is planning workflow reuse, workflow-part review, or a context pack.
- A task needs examples of validators, gates, contracts, runners, prompts, learning signals, boundary maps, or calibration gates from the current catalog.
- A future agent needs false-positive patterns before trusting generated workflow-part candidates.

## Does Not Apply When

- The task would execute or copy code from a scanned source repo without source authority review.
- The task would use workflow parts to change current value score, roadmap phase status, or source truth.
- The candidate has missing dataflow and the agent wants to assemble or install it without declaring inputs, outputs, side effects, and human gates.

## Danger If Misapplied

A generated workflow-part candidate can look like reusable architecture while actually being a marker file, temp fixture, private authority surface, or context-specific gate. Treating it as automatic source truth can create noisy preflights, unsafe composition, and false confidence.

## Red Team

- False positive risk: marker files, package `__init__` files, temp fixtures, and generated packets can look like reusable workflow parts. Mitigation: rejected labels route these to noise or lineage evidence only.
- Authority risk: useful governance or boundary documents may belong to a source repo or private domain. Mitigation: `needs_human_gate` blocks reuse until a human approves the exact use context.
- Dataflow risk: validators, gates, and runners can be useful but still unsafe to assemble because inputs, outputs, side effects, or fixture contracts are undeclared. Mitigation: missing-dataflow labels force `declare_dataflow_before_assembly`.
- Ceremony risk: surfacing every possible workflow part in preflight would bury agents in noise. Mitigation: v1 is manual only.
- Overtrust risk: reviewed examples could be mistaken for score authority. Mitigation: guidance states that score influence and automatic promotion are not authorized.

## Premortem

Assume this failed six months from now. Likely causes:

- A future agent treated the generated guidance as permission to copy or execute source-repo assets.
- Missing-dataflow examples were assembled without declaring inputs, outputs, and side effects.
- Human-gated private or authority-sensitive candidates were reused as generic templates.
- Automatic preflight surfacing was added without a separate high-risk review and flooded routine tasks with low-signal suggestions.

Kill criteria for any later automatic surfacing:

- Guidance appears for tasks that are not workflow reuse, workflow review, or assembly.
- Rejected marker/temp patterns appear as recommended reusable parts.
- Any workflow-part output changes current score, roadmap status, or source truth.
- Any cross-repo installation happens without an explicit human gate.

## Result

The manual guidance command generated:

- 50 reviewed labels consumed.
- 28 accepted for review use.
- 7 human-gated.
- 14 rejected as noise or false-positive patterns.
- 1 deferred.
- 13 accepted candidates still requiring declared dataflow before assembly.

This completes the manual operational bridge from workflow-part calibration to future-agent review use. It does not complete automatic preflight surfacing or workflow assembly.

