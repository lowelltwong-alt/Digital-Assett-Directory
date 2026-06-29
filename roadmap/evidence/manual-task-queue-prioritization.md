# Manual Task Queue Prioritization Evidence

Evidence date: 2026-06-29

## Decision

Add a generated manual task queue command:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend manual-tasks --limit 25 --family-limit 12
```

Generated outputs:

- `processed/reports/manual_task_queue.md`
- `processed/reports/manual_task_queue.json`

## Purpose

The alert inbox is useful but not sufficient as a human work queue because it is
sorted by severity and title. In the current catalog, the top literal rows are
mostly same-shaped medium orphan alerts. Manual review needs a second layer that
keeps traceability but ranks by:

- alert severity;
- current value score;
- alert type;
- asset type;
- high-leverage family context;
- source-boundary posture;
- temp, marker, and fixture noise.

## Methodology

Methodology version: `manual-task-priority-v0.1`

```text
priority_score =
  0.40 * severity_weight
+ 0.30 * value_score
+ alert_type_bonus
+ asset_type_bonus
+ family_bonus
- noise_penalty
```

The score is clamped to `0..100`. It is a review-order heuristic, not a value
score and not truth. Family grouping happens after scoring so repeated validators
or repeated orphan alerts do not consume the whole human review budget.

## Local Research Support

- `docs/ORPHAN_ACTIVATION_AND_SYNERGY_RADAR.md`: orphan alerts are review
  signals for hidden, under-described, or intentionally isolated assets.
- `docs/KNOWLEDGE_GRAPH_MODEL.md`: graph edges and generated relationships are
  candidate evidence, not source-authority transfer.
- `docs/LOGOS_REUSABLE_ASSET_FINDINGS.md`: Logos route isolation, chunking,
  validation, and gold/review packet patterns are reusable beyond Bible work
  when generalized carefully.
- `roadmap/evidence/workflow-part-usage-guidance.md`: accepted workflow parts
  may be cited as manual review context, but assembly requires declared inputs,
  outputs, side effects, authority boundaries, validation, and gates.
- `roadmap/evidence/claude-workflow-composition-red-team.md`: reuse existing
  vocabulary and avoid ontology sprawl.
- `roadmap/evidence/claude-background-connection-radar-review.md`: gate-before-
  score, family deduplication, and privacy-first evidence reduce false positives
  and budget capture.

## Manual Task Outcomes

The command turns the current manual tasks into explicit sections:

- top alert families;
- top alert items;
- workflow-part review-use examples;
- workflow parts blocked by missing dataflow;
- workflow parts requiring human gates;
- workflow-part false-positive patterns.

It keeps Mock Trial and other active/source-owned repositories read-only. It
does not mutate Logos, Mock Trial, LawFirm OS, or any scanned source repository.

## Red Team

- False positive risk: a repeated family of validators can look like many
  independent tasks. Mitigation: family grouping and representative review.
- Authority risk: a source-owned alert can be mistaken for permission to edit.
  Mitigation: each ranked item carries source-boundary posture and blockers.
- Workflow assembly risk: useful workflow parts may still be missing inputs,
  outputs, or side effects. Mitigation: missing-dataflow items are separated and
  blocked from assembly.
- Privacy/public risk: private legal or source-specific content can leak into a
  future public DAD repo. Mitigation: the report uses metadata paths and review
  notes, not raw source rows or private data.
- Score overtrust risk: a priority score could be confused with value or truth.
  Mitigation: the methodology labels it as a review-order heuristic only.
- Stale snapshot risk: files may change during a long local scan. Mitigation:
  changed-during-scan count is surfaced as a caveat.

## Boundary

This evidence completes the manual triage bridge from generated alert and
workflow-part outputs to a bounded human work queue. It does not complete source
repo fixes, workflow assembly, automatic preflight surfacing, source mutation,
current-score changes, or roadmap phase completion.
