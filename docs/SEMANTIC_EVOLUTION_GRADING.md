# Semantic Evolution Grading

## Purpose

When an agent inspects temp copies, near-duplicates, changelogs, schema variants, or
deltas over time, it must separate two signals:

- **semantic evolution**: the asset family changed in a way that can affect behavior,
  compatibility, authority, scoring, or graph edges;
- **noise / lineage**: copies, formatting, path movement, generated fixture churn, or
  cosmetic metadata changed without behavior changing.

Both can be useful. They must not be collapsed into one score.

## Required Command

For current-catalog schema families:

```powershell
python -m digital_asset_directory.cli recommend semantic-evolution --basename "<file-name>.json"
```

For broader review:

```powershell
python -m digital_asset_directory.cli recommend semantic-evolution --asset-type schema --max-families 100 --max-read-bytes 1000000
```

Generated outputs:

- `processed/learning/semantic_evolution_candidates.jsonl`
- `processed/reports/semantic_evolution_candidates.md`

These are generated candidates, not source truth.

## Asset Classification

This grader is a reusable digital asset, not just a command:

- asset family: semantic evolution grading system;
- asset pattern: `semantic_evolution_grading_system`;
- implementation asset: `src/digital_asset_directory/semantic_evolution.py`;
- schema contract: `schemas/semantic-evolution.schema.json`;
- grade authority: `registry/semantic-evolution-grade-registry.json`;
- workflow role: detect whether near-duplicate/temp/changelog deltas are real behavior
  changes or lineage noise before changing scores or graph edges.

## Methodology

Methodology version: `semantic-evolution-grading-v1`

For JSON-like structured assets, the deterministic analyzer:

1. Groups candidate assets by family key, currently the lowercased basename.
2. Classifies path authority as canonical/source, temp fixture, worktree, archive, or generated/processed.
3. Reads bounded local files already present in the current catalog.
4. Computes raw content hashes.
5. Computes normalized JSON hashes with sorted keys.
6. Computes semantic signatures after removing cosmetic JSON keys:
   `$id`, `$schema`, `$comment`, `title`, `description`, and `examples`.
7. Compares required fields, properties, types, enum values, patterns, and formats.
8. Emits separate `semantic_change_score` and `noise_score`.

The default read bound is `--max-read-bytes 1000000`. Set it lower for fast triage or
raise it only when a specific family needs larger structured files inspected.

The analyzer uses candidate lineage ordering. It prefers timestamps when available, then
path-class and version cues such as `v2`, `version`, `revision`, `attempt`, `copy`, and
`pytest` numbers. This ordering is evidence for review, not source authority.

## Evolution Grades

Use `registry/semantic-evolution-grade-registry.json` as authority.

Short form:

- `insufficient_evidence`: not enough readable comparable evidence.
- `none`: no semantic change after normalization.
- `cosmetic_metadata`: only identity/explanatory metadata changed.
- `minor_semantic`: small compatible semantic change.
- `moderate_semantic`: multiple compatible additions or bounded constraint changes.
- `major_semantic`: broad semantic change likely to affect downstream behavior.
- `breaking_semantic`: required-field changes, property removals, type changes, enum removals or renames, or pattern tightening.

## Noise Classes

- `exact_copy`: exact after selected identity layer.
- `format_or_order_noise`: raw hashes differ but normalized structured content matches.
- `path_or_metadata_noise`: only path or non-behavioral metadata changed.
- `fixture_lineage_noise`: many temp/test fixture copies mirror canonical variants.
- `mixed_signal`: real semantic evolution and copy/noise propagation both exist.
- `insufficient_evidence`: cannot separate signal from noise.

## Scoring Rules

Output range:

- `semantic_change_score`: `0.0` to `1.0`, where higher means more behavior-relevant
  structured change.
- `noise_score`: `0.0` to `1.0`, where higher means more copy, fixture, formatting,
  path, or metadata noise.

Formula summary for `semantic-evolution-grading-v1`:

- fewer than two readable comparable JSON objects: grade `insufficient_evidence`,
  both scores `0.0`;
- one semantic version and one raw version: grade `none`, noise `exact_copy`,
  semantic score `0.0`, noise score `0.1`;
- one semantic version, multiple raw versions, one normalized version: grade `none`,
  noise `format_or_order_noise` or `fixture_lineage_noise`, semantic score `0.0`,
  noise score `0.55` or `0.8`;
- one semantic version, multiple normalized versions: grade `cosmetic_metadata`,
  noise `path_or_metadata_noise` or `fixture_lineage_noise`, semantic score `0.0`,
  noise score `0.6` or `0.75`;
- multiple semantic versions with required-field additions/removals, property removals,
  type additions/removals/changes, enum removals, enum value removals, pattern additions,
  or pattern changes: grade `breaking_semantic`, semantic score `0.9`;
- multiple semantic versions without breaking signals and at least eight total structural
  changes: grade `major_semantic`, semantic score `0.72`;
- multiple semantic versions without breaking signals and at least three additive changes
  or four total changes: grade `moderate_semantic`, semantic score `0.48`;
- remaining semantic changes: grade `minor_semantic`, semantic score `0.25`.

Tie-breakers and uncertainty:

- if temp fixtures and canonical/source paths both appear, prefer `fixture_lineage_noise`
  or `mixed_signal` over generic path noise;
- if raw version count is higher than semantic version count, mark noise as `mixed_signal`
  when semantic evolution also exists;
- structural direction is candidate-inferred unless source authority or reviewed evidence
  states the lineage order;
- human review can override grades, but should preserve the raw formula evidence.

- Score copied fixture instances conservatively as current assets.
- Preserve copy counts, hashes, normalized diffs, and path lineage as family-level evidence.
- Route real semantic evolution to family/variant graph edges, not to every copied instance.
- Do not delete or ignore divergent copies.
- Do not call cosmetic metadata drift real semantic evolution.
- Do not call enum removals, required-field changes, type changes, or pattern tightening noise.

## Graph Routing

Candidate edge suggestions may include:

- `semantic_variant_of`
- `evolved_from`
- `noise_variant_of`
- `lineage_evidence_for`
- `has_delta_candidate`

These edges remain candidate-only until reviewed.

## Calibration Use

During Phase 2 calibration:

- Use semantic evolution records before labeling temp copies or near-duplicate variants.
- If `noise_score` is high and semantic score is low, current copied-instance score is likely too high.
- If `semantic_change_score` is high, evaluate the canonical family or variant cluster, not every copy.
- If both are high, preserve both: copy flood is noise, semantic change is signal.
