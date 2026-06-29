# AI Entrypoint And TOC Routing Standard Evidence

## Decision

The repository now treats AI navigation as a reusable workflow asset:

```text
AI_FRONT_DOOR.md -> AI_TABLE_OF_CONTENTS.md branches -> knowledge graph entrypoints -> task-specific evidence
```

The standard exists because future agents need more than file names. They need a
single start point, authority boundaries, branch descriptions, routing tags, and
use-when triggers so they can decide when to look deeper.

## Implemented Surfaces

- `AI_FRONT_DOOR.md`: declares the single AI entrypoint and lists graph entrypoints.
- `AI_TABLE_OF_CONTENTS.md`: uses deterministic rows with path, what it is, tags,
  and use-when triggers.
- `docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md`: reusable standard for this
  repo and future repos.
- `templates/ai-table-of-contents.template.md`: copyable TOC template.
- `MACHINE_NAVIGATION_MANIFEST.json`: machine-readable navigation standard and
  knowledge-graph entrypoints.
- `registry/learning-rule-registry.json`: reviewed rule
  `learning-rule:ai-entrypoint-toc-routing-required`.
- `registry/asset-pattern-registry.json`: reusable pattern
  `ai_entrypoint_toc_routing_system`.

## Candidate-Only Boundary

Knowledge-graph reports and generated outputs remain candidate evidence. The
navigation standard helps agents find them, but does not promote generated graph
edges, centrality, similarity, tags, or reports into source truth.

## Applies When

- A repo is being prepared for future AI builders.
- AI front doors, TOCs, manifests, or knowledge-graph entrypoints are created or
  changed.
- Agents are likely to miss authority or graph context from filenames alone.

## Does Not Apply When

- A task is a trivial typo or one-off scratch edit.
- The repo has no persistent AI navigation need.
- An existing reviewed navigation standard already covers the exact context.

## Remaining Risks

- The TOC row shape is documented and unit-tested for core files, but a full
  markdown linter for every row is future work.
- Downstream repos still need adoption examples before the pattern can be
  calibrated for ceremony versus usefulness.
- Generated reports must continue to be tagged as candidate evidence so graph
  entrypoints do not become accidental authority.
