# Semantic Evolution Grading Evidence

## Status

Generated candidate evidence only. This does not mark a roadmap phase complete and does
not promote any generated graph edge, score, or lineage claim to source truth.

## Why This Exists

Phase 2 calibration exposed a repeated ambiguity: temp/test fixture copies can inflate
current asset scores, but copied variants may also preserve real schema evolution over
time. Future agents need a deterministic way to separate those signals before labeling
scores, creating graph edges, or deciding whether a copied asset is useful.

## Implemented Asset

- Asset pattern: `semantic_evolution_grading_system`
- Implementation: `src/digital_asset_directory/semantic_evolution.py`
- Contract: `schemas/semantic-evolution.schema.json`
- Grade registry: `registry/semantic-evolution-grade-registry.json`
- Learning rules:
  - `learning-rule:semantic-evolution-check-required`
  - `learning-rule:calculated-score-requires-methodology`
  - `learning-rule:observable-decision-trace-to-candidate-lesson`

## Methodology

Methodology version: `semantic-evolution-grading-v1`

The grader groups structured assets by family key, classifies path authority, computes
raw hashes, normalized JSON hashes, and cosmetic-key-stripped semantic signatures, then
compares required fields, properties, types, enum values, patterns, and formats.

It emits two separate signals:

- `semantic_change_score`: behavior-relevant structured evolution.
- `noise_score`: copy, fixture, formatting, path, or metadata noise.

The formula and thresholds are documented in `docs/SEMANTIC_EVOLUTION_GRADING.md`.

## Generated Evidence

Command:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend semantic-evolution --source-id all --asset-type schema --max-families 20 --review-sample 20 --max-read-bytes 500000
```

Result:

- Candidate families: 20
- `breaking_semantic`: 8
- `none`: 12
- `mixed_signal`: 8
- `fixture_lineage_noise`: 4
- `exact_copy`: 8
- Scan id: `dad:scan:5282a773-44d9-4826-973c-677d29cbe726`
- Generated report: `processed/reports/semantic_evolution_candidates.md`
- Generated records: `processed/learning/semantic_evolution_candidates.jsonl`

Top mixed-signal families included `artifact.schema.json`, `attorney.schema.json`,
`chunk.schema.json`, `employment_episode.schema.json`, `external_identifier.schema.json`,
`law_firm.schema.json`, `source_profile.schema.json`, and
`talent_signal_claim.schema.json`.

## Captured Lesson

An initial broader run timed out when asked to inspect many cataloged JSON families.
The bounded command now exposes `--max-read-bytes`; the default is documented as part
of the methodology. Future agents should treat resource bounds as part of deterministic
scoring behavior whenever a calculated report can influence review.

Observable decision trace captured here:

- Trigger: user asked whether temp copies changed over time and whether evolution was valuable.
- Correction: implementation test showed structural delta direction needed explicit lineage ordering.
- Result: lineage ordering is now candidate-inferred from timestamps, path class, and version cues.
- Guardrail: hidden/private reasoning is not stored; observable commands, failures, edits, and rules are.

## Caveats

- Lineage direction is candidate-inferred unless source authority or human review proves it.
- High `semantic_change_score` means review priority, not automatic correctness.
- High `noise_score` means copied-instance scores should be conservative, not that the family is worthless.
- Generated records remain under `processed/` and are not tracked truth.
- Human review is still required before using these candidates to change calibration labels.
