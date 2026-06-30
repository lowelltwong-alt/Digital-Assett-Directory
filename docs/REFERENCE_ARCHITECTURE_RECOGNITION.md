# Reference Architecture Recognition

Reference architecture recognition finds reusable system shapes in the current
catalog without reading source file contents or mutating source repositories.
It is a metadata-only pass over already-cataloged assets and candidate edges.

## What Counts

A reference architecture is not one impressive file. It is a repeatable pattern
made from cooperating pieces:

- AI/navigation entrypoints;
- architecture and design docs;
- schemas, contracts, registries, ontologies, or taxonomies;
- governance rules, authority boundaries, and human gates;
- validators, tests, CI, QA, or calibration checks;
- workflows, runbooks, and dataflow/normalization maps;
- learning loops, preflight/postflight, handoffs, and pay-forward records;
- templates or scaffolds that make the pattern reusable;
- public-safe/private-source boundaries.

The first version recognizes repo-level architecture candidates from catalog
metadata. It should be treated as a review queue, not as proof that a source
repo's architecture is canonical or complete.

## Good Reference Criteria

A good reference architecture usually has:

- multiple architecture roles working together;
- explicit authority boundaries and gates;
- contracts plus validators, not only prose;
- a clear workflow order;
- a learning/pay-forward loop;
- reusable template or scaffold surfaces;
- privacy/public-safe boundaries where sensitive source repos are involved;
- a small bounded experiment for trying the pattern safely elsewhere.

## Score Formula

```text
reference_score = 100 * (
  0.22 * completeness
+ 0.20 * usefulness
+ 0.18 * reusability
+ 0.15 * composition
+ 0.15 * validation_readiness
+ 0.10 * novelty
) * (1 - 0.35 * risk)
```

Failed gates cap the score at `25`.

The score is a routing signal only. Current component evidence must be reviewed
before future upside or reuse potential.

## Recognition Command

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend reference-architectures --limit 50 --component-limit 12
```

The command writes:

```text
processed/reports/reference_architectures.md
processed/reports/reference_architectures.json
processed/learning/reference_architecture_candidates.jsonl
processed/learning/scan_cycle_events.jsonl
```

## Boundaries

The command checks:

- catalog assets table;
- asset paths, titles, types, tags, capabilities, needs, outcomes, sensitivity,
  and value scores.

The command intentionally does not check:

- the full candidate edge table by default, to keep the first pass bounded on
  large catalogs;
- source file contents;
- fresh filesystem recursion;
- GitHub, CI, or external APIs;
- model calls, embeddings, or semantic enrichment;
- source repository writes.

Use `--include-edges` only when a later pass needs full edge-aware composition
scoring and the catalog size makes that safe.

## Next Scan Cycle

After this metadata pass, future agents should avoid repeating broad scans and
instead choose one of these narrower follow-ups:

- human review of high-score candidates;
- compare candidates to template dependencies;
- compare candidates to workflow-part records;
- request a bounded content-read scope for one repo or path family if metadata
  cannot prove the architecture roles;
- only after review, package a candidate architecture as a template or roadmap
  proposal.
