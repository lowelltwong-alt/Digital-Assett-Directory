# Logos Asset Family Recognition Evidence

Evidence date: 2026-06-25

## Scope

This evidence records generated candidate reports from the current local catalog. No
new scan was run for this evidence, no GitHub scan was run, and no source repository
was modified.

Commands used:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend asset-families --source-id all --review-sample 50
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend learning-loops --source-id all --review-sample 25
```

Generated outputs:

- `processed/reports/asset_family_recognition.md`
- `processed/reports/logos_asset_family_candidates.md`
- `processed/reports/learning_loop_candidates.md`
- `processed/learning/learning_loop_candidates.jsonl`
- `processed/learning/asset_family_candidate_edges.jsonl`

Generated outputs are ignored by Git and remain candidate evidence.

## Results

- Assets considered in the current catalog: 94,399
- Candidate asset-family patterns detected: 8
- Candidate asset-family matches sampled for review: 400
- Logos-like assets in the current catalog: 7,998
- Candidate learning-loop records: 33
- Candidate learning-loop edges: 82

The Logos-like candidates show reusable versions of the intended patterns:

- governed learning loops;
- boundary and contamination firewalls;
- gold set and review packet systems;
- route-isolated evaluation harnesses;
- duplicate and variant preservation systems;
- frontier signal intake loops.

The first learning-loop samples include Logos chunking/evaluation assets where tests,
lesson indexes, candidate promotion decisions, review gates, and workflow-rule
registries appear together as a reviewable loop.

## Authority Boundary

All records and edges are generated candidates. They do not:

- promote candidate findings to source truth;
- authorize source repository mutation;
- choose a canonical Logos repo or worktree;
- complete any roadmap phase;
- prove current or future asset value.

## Risks And Review Needs

- The current catalog includes many Logos worktrees and some temp/test-fixture-like
  paths, so duplicate volume and false positives are expected.
- Human review should calibrate which Logos variants are active, archived, duplicated,
  or intentionally preserved.
- The asset-family recognizer uses deterministic text/path/type evidence only; it is
  not a semantic embedding layer.
- Current value scores are shown before candidate upside ranges, but the upside ranges
  need human calibration before they affect prioritization.

## Next Review Actions

- Review the Logos candidate report for the active Logos repos versus worktree/archive
  variants.
- Tighten `config/sources.local.yaml` exclusions before any future scan if temp or
  copied worktree volume is not desired.
- Use the learning-loop JSONL as a review queue, not as accepted truth.
- Preserve close variants until a human-reviewed delta explains shared core,
  strengths, neutral differences, weaker parts, and any merge-or-keep decision.
