# Graph Buildout Handoff (for Codex / next agent)

Written 2026-07-02 by Fable 5 after building the first lesson graph
(`asset-dir lesson graph` → `processed/learning/lesson-graph.json`). This file is the
design contract and work order for growing that seed into DAD's connective tissue:
the thing that finds novel, important combinations of assets across categories for
workflows and contexts we cannot predict yet.

Read first: `AGENTS.md`, `src/digital_asset_directory/learning.py` (build_lesson_graph),
`schemas/lesson-graph.schema.json`, `registry/asset-pattern-registry.json`,
`tests/test_lesson_graph.py`. Run `asset-dir agent preflight` before starting; the
load-bearing-decision rule WILL fire — graph edge semantics affect scoring, labels, and
every future agent, so classify this work as HIGH risk tier and follow the fresh-eyes /
premortem path in `docs/LOAD_BEARING_DECISION_REVIEW.md`.

## 0. Current state (do not rediscover)

- Nodes: lesson, repo, pattern, offering. Edges: learned_in, matches_pattern,
  about_asset, uses_asset — all deterministic joins with `edge_basis` strings,
  `review_status: candidate`, rebuilt from scratch each run (no incremental state).
- Known result: 200+ lessons produce almost no `matches_pattern` edges because lessons
  use free-text `reusable_patterns`; `pattern_gap_candidates` in the graph output is the
  curation queue. Structured intakes (`lesson review-feedback`, marker codes) fix this
  going forward — the marker + exact-id pattern is the proven recipe.
- The graph is a compiled artifact: raw lessons + registries are source of truth; the
  graph is always safe to delete and rebuild. Keep this property forever — it is what
  makes every schema change survivable (migration = rebuild).

## 1. Edge vocabulary — the load-bearing decision

The user's directive: edge types and the words that form connections must be robust and
intentionally selected. Treat the edge vocabulary as a REVIEWED, CLOSED, VERSIONED
registry, not an emergent convention.

**Build `registry/graph-edge-registry.json` + schema.** Each edge type declares:

```json
{
  "edge_type": "complements",
  "edge_class": "inference",            // join | inference — NEVER blur these
  "direction": "asset -> asset (symmetric pair stored once, lower id first)",
  "cardinality": "many-to-many",
  "semantics": "Covers an adjacent, non-overlapping workflow stage for a shared task context.",
  "allowed_bases": ["workflow-stage-adjacency-v1", "need-coverage-v1"],
  "evidence_required": ["shared task_type token set", "disjoint workflow_stages"],
  "version": "0.1.0",
  "examples": ["dad:offering:python-underused-idioms -> dad:harness:mutation-testing"],
  "danger_if_wrong": "False complements pollute combination discovery and waste review time."
}
```

**Two edge classes, hard rule:**
- `join` edges are facts derived from records (a lesson names a repo; a usage row
  exists). They can be trusted for counting and provenance.
- `inference` edges are generated hypotheses (similarity, complementarity, co-use).
  They carry a method id + version + threshold per the calculated-score learning rule,
  and they NEVER promote themselves. Validation must reject any graph where an
  inference edge lacks a method version.

**Proposed v0.2 vocabulary** (start here; every addition needs a registry row + example
+ test + human review):

Join: `learned_in`, `about_asset`, `matches_pattern`, `uses_asset`, `watches_asset`
(split from uses — watching is a weaker signal), `supersedes` (mail→mail and
offering-version lineage), `promoted_from` (offering/skill → intake record → research
report entry: the full provenance chain of the research-intake pipeline),
`sighting_of` (mail/lesson → pattern), `validated_by` (offering/harness → eval case or
test artifact), `depends_on` (asset → asset, from declared dependencies only).

Inference: `similar_to` (same-category near-duplicate/variant; MUST route through
semantic-evolution grading, do not invent a second similarity scale),
`complements` (cross-category adjacency, below), `co_used_with` (usage ledger
co-occurrence), `gap_evidence_for` (failure/lesson → need), `member_of`
(asset → combination hypernode, below).

## 2. Combination discovery — 2, 3, 4 assets, whole workflows

Pairwise edges cannot represent "these four things form a workflow." Add two node types:

- **`combination_candidate` hypernode**: members via `member_of` edges; fields:
  hypothesis (one sentence), discovery_basis (which rule fired), status
  (`hypothesized -> trialed -> adopted | rejected`), outcome_refs. Rejected combinations
  are kept as negative evidence so they never resurface silently.
- **`workflow` node**: ordered stage slots; assets attach via `fills_stage` edges.
  An adopted combination graduates into a workflow node.

**Deterministic discovery rules (no ML needed, run in this order):**

1. **Stage adjacency**: give every offering/harness/skill a `workflow_stages` facet from
   a closed vocabulary — propose: `orient, gather_context, plan, generate, validate,
   review, ship, learn`. Assets sharing task-context tokens whose stages are adjacent
   and disjoint → `complements`. Three or more assets covering a contiguous stage run →
   `combination_candidate`. (Example that should fall out: idiom card [generate] +
   mutation harness [validate] + review-feedback intake [learn].)
2. **Produces/consumes chaining**: add `produces` and `consumes` facets over a closed
   artifact-kind vocabulary (`report, registry_row, eval_case, lesson, mail_packet,
   pointer, score`). A produces what B consumes → pipeline edge; chains of length ≥3 →
   combination candidate. This is the strongest whole-workflow signal.
3. **Co-usage**: usage rows or one decision trace showing assets used together in the
   same repo/session; repeated across ≥2 distinct repos → `co_used_with`, and with
   stage-disjointness → combination candidate.
4. **Need coverage**: two assets linked to the same `dad:need:*` through different
   capabilities → complement candidates.
5. **Failure complement**: a review-feedback lesson names a miss (finding=...) whose
   terms match another asset's capabilities → `gap_evidence_for` + complement.

All five write to a **review queue** (`processed/learning/combination-candidates.jsonl`),
human-labeled with the existing review-queue idiom (see
`recommend workflow-part-review-*` commands for the established pattern). Labels feed
threshold calibration; below N=10, report counts, never percentages.

## 3. Chunking across asset types — how edges cross prose/code/JSON

Do NOT chunk everything into one comparable soup. The rule: **edges are computed on
card projections, never on raw bodies.** Raw bodies only feed per-type term extraction.

**Card projection** = one small schema'd record per asset regardless of type, holding
the shared facets: `id, category, capabilities[], task_types[], workflow_stages[],
produces[], consumes[], key_terms[], version, review_status, provenance_ref`.
Registries already ARE card projections (offerings, patterns, harness rows, skills).
What lacks projections: lessons (free prose), docs, code, prompts. Add a projection
builder per type:

| Source type | Chunk unit (never split) | key_terms extraction |
|---|---|---|
| JSON registry rows | the row | declared fields (capabilities, tags, task_types) — already curated |
| Lesson records | the record + its `key=value` lines | marker-code lines first (`DAD_*_V1` format is the chunking strategy — extend it, don't parse prose) |
| Markdown docs/prose | heading section, heading-path kept as breadcrumb | headings + emphasized terms + code-fence identifiers |
| Python code | top-level function/class via `ast` | identifiers, docstring nouns, raised exceptions |
| Rust code (later) | item level via syn/tree-sitter | pub identifiers, doc comments |
| Prompts | whole file | front-matter fields only |

**The connective words need governance.** Build `registry/graph-term-registry.json`:
canonical terms, synonym lists (`test/tests/testing/pytest → test`), which facet each
term belongs to, examples, review_status. One shared normalizer (grow the existing
`_tokenize`/`_pattern_key` lineage into a single module — there are already three
near-copies; consolidate before adding a fourth). Extraction may PROPOSE new terms into
a gap list (same mechanism as `pattern_gap_candidates`); humans promote them. Edge
quality is capped by this registry's quality — this is where "amazingly robust,
intentionally selected" lives concretely.

## 4. The accompanying description file — solve drift by generating it

A hand-written companion doc will miss things; the user is right. Split it:

- **`docs/LESSON_GRAPH.md`** (hand-written, small, stable): concepts, edge-class rule,
  how to query, pointers. Changes rarely.
- **`processed/learning/lesson-graph-manifest.json`** (GENERATED every build): counts by
  node/edge type; every edge type present with its registry definition inlined; method
  versions used; term-registry version; input hashes (lessons dir digest, each registry
  hash); and a computed **coverage report** — how many assets lack `workflow_stages`,
  how many lessons have no projection, which edge types produced zero edges. "What the
  graph is missing" becomes computed output, not remembered knowledge.
- **Drift = validation error**: `cli validate` checks (a) every edge type in the graph
  exists in the edge registry, (b) every edge's basis is in its type's allowed_bases,
  (c) manifest input hashes match current files (stale manifest → warning, same pattern
  as mail-digest staleness), (d) schema enums match the edge registry (single source:
  generate the schema enum from the registry or test they're equal).

## 5. Metadata rules

- Node metadata = facets only, each facet either (a) used by at least one edge rule or
  (b) provenance. No ornamental metadata — every field must earn its place or be cut.
- Edge metadata (required): `edge_id, source, target, edge_type, edge_class,
  edge_basis, method_version (inference only), created_at (build time), evidence_refs[],
  review_status`. Inference edges add score fields ONLY with a named methodology
  (calculated-score rule); prefer `matched_terms`-style raw observations over scores.
- Graph metadata: `generated_at`, input hashes, registry versions. The graph never
  stores anything unrecoverable from sources — repeat: rebuild is the only migration.

## 6. Freshness — when to rebuild, upgrade, extend

- **Rebuild triggers**: (a) postflight (cheap at current scale — full rebuild is fine
  well past 10k lessons; do NOT build incremental updating until a rebuild measurably
  exceeds ~30s), (b) weekly cadence job, (c) preflight warning when input hashes differ
  from manifest (nudges, never blocks).
- **Upgrading the vocabulary**: adding an edge type or facet = medium/high-risk change:
  registry row + example + synthetic-fixture test + schema/enum sync + human review.
  Renaming/removing = high-risk: requires a deprecation note in the edge registry and a
  rebuild; never leave two names for one meaning.
- **Changing thresholds** on inference rules: only against the labeled combination
  queue (counts, not vibes), recorded via the calibration idiom already in
  `dad calibration`.

## 7. Testing with synthetic data — the golden mini-hub

Build `tests/fixtures/golden_mini_hub/` (or a builder function) — a synthetic hub with
PLANTED structures and NOISE, so discovery precision is assertable:

- Plant: one 3-asset produces/consumes chain (must be found as a combination
  candidate); two co-usage pairs across 2 repos (must edge); one near-duplicate offering
  pair (must route to similar_to/semantic-evolution, NOT complements); one cold orphan
  asset (zero edges — must appear in coverage report); one lesson with a marker code
  matching a pattern (must edge) and one free-text lesson (must land in gap list).
- Noise: ~20 unrelated lessons/assets with overlapping common words — asserts the term
  registry + stopwords prevent false edges (precision test: exactly the planted
  structures are found, count-exact).
- Properties: build twice → byte-identical graph (sort everything, no timestamps inside
  nodes/edges except graph-level generated_at); adding an unrelated lesson never removes
  an edge; every edge endpoint exists; every edge type is in the registry.
- Keep the golden hub tiny (<40 records) and human-readable — it doubles as the worked
  example for every future agent reading this file.

## 8. Prioritized work order

1. `registry/graph-edge-registry.json` + schema + validate wiring + `docs/LESSON_GRAPH.md`
   skeleton. (Vocabulary first — everything else hangs on it.)
2. Facets on existing registries: `workflow_stages`, `produces`, `consumes` for
   offerings/harnesses/skills (schema-additive; backfill the ~10 current rows by hand —
   they are few and you understand them).
3. Extend `build_lesson_graph`: new join edges (watches_asset, supersedes,
   promoted_from via intake records, validated_by, sighting_of), manifest generation,
   coverage report.
4. Term registry + consolidate the three tokenizer copies into one module.
5. Golden mini-hub + tests (do this BEFORE the inference pass so precision is
   measurable from day one).
6. Inference pass behind a flag (`lesson graph --infer`): stage adjacency,
   produces/consumes chains, co-usage; combination review queue + labeling.
7. Later: markdown/code chunk projections; Rust items; incremental build only if slow.

## 9. Constraints (non-negotiable, inherited)

- Generated edges/combinations are candidates; human review promotes; rejected
  hypotheses are preserved as negative evidence.
- No score without a named methodology version; prefer raw matched-term observations.
- Never copy asset bodies into the graph — ids, labels ≤120 chars, and refs only.
- The graph must stay deletable: raw records + registries remain the only truth.
- Closed vocabularies (edge types, facets, terms) — additions through review, never
  through drive-by string invention. The moment an agent can invent an edge type
  inline, the vocabulary is dead.

## 10. Open problems I did not solve (be honest with the human)

- Cross-language identity: when the same conceptual asset exists as md doc + json card
  (e.g., rust-buildout README vs rust-buildout.json), they should be ONE node with two
  body refs, not two nodes. Needs an identity rule (shared dir? declared `asset_id`
  field in both?) — decide before projections multiply.
- Term-registry cold start: seeding synonyms by hand is tedious; the gap-list loop
  helps but the first 50 terms are manual. Budget an hour with the human.
- Combination *usefulness* vs combination *validity*: stage-adjacency finds valid
  pipelines; whether a combo is worth a workflow node is a human call — the queue
  ordering (co-use count, distinct-repo count) is only a triage aid.
- Prose lessons predating marker codes (200 of them) will never edge well; a one-time
  curation pass mapping the top-20 `pattern_gap_candidates` to pattern ids is cheap and
  fixes most of the mass; do not attempt automated backfill.
