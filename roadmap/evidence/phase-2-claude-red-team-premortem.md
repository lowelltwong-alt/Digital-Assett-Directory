# Claude Red Team Premortem

Date: 2026-06-25. Reviewer: Claude Code (independent, read-only). Status: candidate
evidence only. No labels applied, no calibration JSONL edited, no roadmap phase marked
complete, no source repos mutated, GitHub scanning not enabled.

## Executive Verdict

**Conditional.** The architecture *can* become a useful Digital Asset Directory, and the
identity/similarity layer is now genuinely good (deterministic shingle MinHash, containment,
exact SHA, append-only raw, candidate-only edges). But the project is **expanding breadth
(identity ladder, semantic-evolution grading, deterministic learning rules, contextual
archaeology, ~25 schemas, ~7 registries) faster than it is fixing the core defect that makes
any of it trustworthy: the value scorer still cannot tell a canonical asset from a throwaway
pytest copy.**

Concrete proof: `validate` now checks 61 contract files (up from 26 at seed), yet the Phase 2
calibration sample of 50 assets collapses into **three** distinct scores (71.4 ×1, 66.75 ×24,
35.25 ×25), **21 of 50 are `.pytest-tmp-root` temp copies + 1 worktree copy**, and the sample
still shows the pre-fix constant `uniqueness=55.0`. Calibrating this sample now would mostly
**confirm known scanner bugs**, not calibrate value.

The single highest-leverage decision: **pause net-new subsystems, fix scoring discipline +
sampling, then calibrate.** Otherwise the project accretes machinery on top of an
uncalibrated core and the learning loop becomes paperwork.

## Critical Findings

Top 10, ordered by severity.

1. **Scoring has no path/instance-class discipline (CRITICAL).** `score_asset`
   (`src/digital_asset_directory/scoring.py`) has no awareness of canonical vs temp/worktree/
   generated. A pytest temp copy with zero capabilities scores 66.75 (medium) on type +
   freshness + provenance alone. This was the #1 recommendation in the prior handoff and the
   second-opinion; it did **not** land. Everything downstream (calibration, ranking, graph
   centrality) inherits this.

2. **The scanner ingests ephemeral sandboxes and OS junk (CRITICAL).**
   `config/sources.example.yaml` excludes `.git`, `.venv`, `.env`, secrets — but **not**
   `**/.pytest-tmp-root/**`, `**/pytest-of-*/**`, or `.DS_Store`. Result: 50–108 copies of
   each schema basename flood the catalog (e.g., ~99 `claim_v3.schema.json` temp copies), and
   `.DS_Store` is scored a 35-point asset. This is the upstream cause of finding #1's blast
   radius.

3. **The calibration sample is stale and biased (CRITICAL for Phase 2).**
   `recommend calibration-review-summary`: template 50, **reviewed 3**, gate incomplete. The
   sample shows `uniqueness=55.0` (the pre-fix constant), so it predates the scoring fixes in
   commit `b5c64d5`, and it is dominated by temp-fixture copies (top/bottom-by-score sampling
   pulls the copy flood). Labeling it produces evidence about scanner bugs, not value.

4. **Value scorer has near-zero resolution on real corpora (HIGH).** 50 assets → 3 scores.
   Content-derived signals (`capabilities`/`needs`/`outcomes`) are empty for almost all scanned
   files, so `type + freshness + provenance` dominate. A scorer that emits 3 buckets cannot
   rank a portfolio.

5. **Media/binary scoring is content-blind (HIGH).** A `.DS_Store`, a screenshot, and a
   300-page dissertation PDF all score an identical 35.25 because nothing is extracted from
   binaries. The catalog cannot distinguish junk from a valuable research corpus.

6. **`freshness` rewards write/copy recency (HIGH).** Temp copies get `freshness=100` because
   pytest wrote them seconds ago. The "freshest" assets in the catalog are throwaway artifacts.
   Freshness should track canonical source revision, not file mtime of a generated copy.

7. **Duplicate-awareness is too weak to discipline copy floods (HIGH).** The uniqueness fix is
   correct in direction but weak: weight 0.08 × floor 0.4 ⇒ a 99-copy cluster drops the score
   only ~1–5 points (66.75 → ~65). Copy floods remain "medium."

8. **Roadmap evidence is computed from git-ignored local outputs (MEDIUM-HIGH).** `roadmap
   check` reports **phase-1 complete**, derived from `processed/catalog/assets.jsonl` etc.,
   which are git-ignored. A fresh clone cannot reproduce "phase-1 complete," and the human
   gates (source scope reviewed, mutation check) are self-asserted. Generated outputs are
   quietly becoming roadmap truth.

9. **Schema/registry sprawl is outrunning validated value (MEDIUM).** 61 contract files, ~7
   registries, and multiple learning subsystems exist before a single trustworthy value score
   has been produced end-to-end. Complexity itself is now a top failure mode (see Premortem).

10. **Exact-duplicate pairing is unbounded in group size (MEDIUM).**
    `identity_layers._bounded_pairs` iterates `combinations(group, 2)` over a content-identical
    group with no group-size cap (the near-dup side caps postings at 100). A large identical
    group (boilerplate across hundreds of repos) is an O(N²) cliff for ≤8 edges each.

## Math And Scoring Review

Formula (`scoring.py`): 8 weighted components summing to 1.0, then a multiplicative risk
discount `raw *= max(0, 1 - min(0.85, risk))`. Improvements since last review (credit Codex):
provenance now discriminates (`0.95` read / `0.55` metadata-only / `0.2` none via
`content_sha256`); uniqueness is cluster-aware; risk is multiplicative and interpretable;
`unknown_license` is wired for GitHub repos; freshness is single-counted.

Remaining math problems that create misleading certainty:

- **Type bonuses fire on the label, not the instance.** `verification += 0.55` for
  `asset_type ∈ {test, evaluation, schema}`; `reuse += 0.25` for reusable types; `learning +=
  0.45` for learning types. A zero-evidence schema copy inherits all three. Fix: gate type
  bonuses on canonical/source class AND/OR corroborating evidence (declared capabilities, a
  test that references it, a usage record). Expected effect: temp/empty typed files fall to
  low band; real canonical schemas keep their bonus.
- **Low-information assets score too high; high-potential unextracted assets score too low —
  simultaneously.** A `.DS_Store` (no info) gets 35.25; a dissertation PDF (high latent value,
  unextracted) also gets 35.25. Fix: (a) extract text from PDFs/docs so they earn
  content-derived signal; (b) add an `information_content` gate (size/þ tokens/extractable
  text) so empty/marker files floor out. Expected effect: media spreads from one bucket into a
  real distribution; junk floors; research corpus rises with extraction.
- **Uniqueness weight too small for floods.** Either raise the weight, remove the 0.6 floor so
  large clusters approach 0, or — better — make "redundant copy of a canonical cluster member"
  a multiplicative discount (like risk), not a small additive nudge. Expected effect: the Nth
  copy of a schema approaches ~0 independent value while the representative keeps full value.
- **Confidence is not a probability.** `confidence` bands and `semantic_change_score`/
  `noise_score` are monotone transforms presented as graded certainty. Per the project's own
  Calculated-Score-Methodology rule, either calibrate to P(useful) on review labels or keep
  calling them heuristics. Today they read as more certain than they are.

## Algorithm Review

**Good enough for v1 (keep):**
- Exact SHA-256 identity and metadata fingerprints; the metadata-only path correctly sets
  `content_sha256=None` so placeholders/oversize files are excluded from exact-dup.
- Near-duplicate via overlapping token shingles (`SHINGLE_SIZE=4`) + 64-perm MinHash +
  containment (`shared/min`, threshold 0.82) + overlap threshold 0.5, confidence capped 0.8.
  This addresses the prior "position-aligned windows + max-denominator" defect: it now catches
  shifted text and subset/containment duplication. Solid v1.
- IDF-weighted similarity now present in `graph_engine`/`context_pack` (prior recommendation
  landed). Candidate edges default `generated_candidate`. Append-only raw observations.

**Dangerous / brittle (fix):**
- **Path overfitting in classification.** `asset-review-001`: an `__init__.py` is typed
  `evaluation` and scored 71.4 (the top score in the set) — almost certainly a path-segment
  match (`eval`/`evaluation` in path). Classifier needs word-boundary + role evidence, not
  path substrings deciding `asset_type`.
- **Near-dup may still be excerpt-bounded.** `_content_text` reads
  `metadata["chunk_text"] or metadata["excerpt"]`. If only the 5000-char excerpt is populated,
  near-dup/semantic comparison sees only the first 5 KB. Confirm full extracted text feeds
  chunking; otherwise large files are compared on their prefix only.
- **Copy-flood candidate generation** (finding #10): exact-dup group pairing has no size cap.
- **Stale generated outputs as evidence** (finding #8): regenerable surfaces drive roadmap
  status.

## Data Flow Review

scanner → catalog (sqlite + JSONL) → chunks → duplicate clusters → graph edges → re-score with
duplicate_counts → calibration template → roadmap evidence.

- **Source protection: good.** Read-only scan; symlinks skipped; before/after revision-identity
  check; mutation now soft-flags `changed_during_scan` per asset (reasonable). Source repos are
  not mutated.
- **Provenance: good and improved.** `source_provenance` is populated and explicitly
  non-authority-transferring; identity ladder is documented and consistent across
  docs/ontology/registries.
- **Where candidates leak into "truth":** (1) roadmap phase-1 "complete" computed from
  git-ignored generated outputs (#8); (2) the calibration template is generated from the
  scorer, so labeling it risks ratifying scorer output rather than independently judging value;
  (3) `confidence`/grade values that read as probabilities. None are catastrophic, but each is
  a quiet candidate→truth path.
- **Append-only raw:** holds (raw observations + audit are append-only; lesson routing appends).
  Note the one tension flagged earlier: secrets in append-only raw would be permanent — the
  redact-at-boundary fix mitigates, but raw remains the unforgiving sink.

## Learning Loop Review

The loop is well-designed *on paper*: candidate lesson → reviewed learning rule →
preflight/midflight acknowledgement, with `applies_when` / `does_not_apply_when` /
`danger_if_misapplied` required on context-bound lessons, and observable-decision-trace-only
(no hidden reasoning). The deterministic learning rules are genuinely good guardrails (the
temp-fixture and current-score-before-upside rules are exactly right).

Risks:
- **Paperwork risk is real.** Six subsystems (preflight, midflight, postflight, learning rules,
  repo events, asset-use feedback, archaeology) exist before there is evidence any lesson has
  changed a future outcome. Capture is rich; *demonstrated reuse* is unproven. The loop will
  only earn its overhead if rules measurably prevent rework — add a "rule fired → outcome
  improved" trace.
- **Noise capture.** Contextual archaeology over worktrees/temp/CI artifacts will generate
  large candidate volumes; without precision gating it floods the same way temp fixtures
  flooded the catalog. Same disease, new surface.
- **Misuse outside context.** The `applies_when`/`danger_if_misapplied` discipline is the right
  defense; enforce it (midflight already exits non-zero on unacknowledged `require_ack` rules —
  good). Keep rules few; every promoted rule constrains all future agents.

## Calibration Review

State: 50 template / 3 reviewed / gate incomplete (FP notes 1, FN 0, weight-change 3). The
sample is **both stale (pre-fix `uniqueness=55`) and biased (21 temp + 1 worktree of 50; 3
score buckets)**. The prior second opinion and all-50 triage already concluded the temp-copy
records are `too_high` — those labels are *correct about the bug* but would calibrate the
scanner's defect, not the value model.

**Recommendation: (d) pause and fix scoring first, then (b) regenerate a deduped sample, then
(a) label — in that order.** Do not finish labeling the current 50 as Phase 2 evidence.
Rationale: labeling now spends the scarce human-label budget rating ~33 ephemeral copies and
encodes scanner artifacts into calibration evidence. The only records worth keeping from this
batch are the 3 genuine source records (`001` misclassification, `004` canonical schema, `006`
source test) and the FP/weight-change *notes*, which are valuable bug evidence.

## Roadmap Review

Phases 0–5 are reasonably scoped, but the **ordering has a gap**: Phase 2 ("calibrate value/
staleness/orphan/synergy") assumes the scorer is worth calibrating. It is not yet, because the
scoring-discipline + sampling fixes are not in. Recommended edits:

- **Insert Phase 1.5 "Scoring discipline + clean sampling"** before Phase 2 labeling: path/
  instance-class gating, scan-exclude of pytest/worktree/junk, type-bonus gating, freshness
  source-recency, media extraction, dedup-before-sample. Phase 2 should consume a regenerated
  sample.
- **Sequence scoring fixes before proposal-engine calibration.** Proposals rank on the same
  scores/edges; calibrating proposals on an uncalibrated value model compounds error.
- **Phase 1 "complete" should require tracked acceptance evidence**, not git-ignored local
  outputs. Either commit a sanitized evidence digest or change the gate to a reviewed summary.
- **Phase 3 (downstream pilot) placement is correct** — after the hub's own scoring is trusted.
  Do not pilot governance into other repos while the value signal is 3 buckets.
- **Highest-risk dependencies:** (a) trustworthy value score gates everything; (b) clean
  sampling gates calibration; (c) text extraction gates media/PDF value and near-dup quality.

## Premortem

If this fails in 6 months, the most likely causes:

- **Technical:** scorer never gains resolution; everything ranks the same; users stop trusting
  the score and ignore it.
- **Data quality:** copy floods + unexcluded sandboxes/junk dominate the catalog; signal is
  buried; the graph fills with copy-of-copy edges.
- **Calibration:** the human-label budget is spent ratifying scanner bugs; weights are tuned to
  a biased sample; "calibrated" scores are worse than uncalibrated.
- **Human-review bottleneck:** every score/edge/lesson is candidate-only and needs review;
  nobody has time; the review queue becomes a graveyard (alert fatigue).
- **Agent misuse:** lessons applied outside `applies_when`; a reviewed rule overfit to LawFirm
  schemas misfires elsewhere.
- **Graph/ontology overcomplexity:** ~25 schemas + ~7 registries + multiple learning
  subsystems exceed what a single maintainer can keep coherent; drift between code and
  contracts.
- **Security/injection:** public-feedback path (when public) executes PR code in CI; or
  archaeology ingests untrusted repo text as "lessons."
- **False confidence:** `confidence`/grade numbers read as probabilities; a 0.9 is trusted as
  90%.
- **Roadmap/order:** calibrating and piloting governance before the core score is trustworthy.

The dominant theme: **breadth outrunning a uncalibrated core.**

## Recommended Fix Order

1. **Stop adding new schemas/registries/learning subsystems** until one trustworthy value
   score exists end-to-end.
2. **Scan exclusion:** add `**/.pytest-tmp-root/**`, `**/pytest-of-*/**`, `.DS_Store` to default
   excludes. (Biggest single cleanup.)
3. **Scoring discipline:** path/instance-class as a multiplicative discount; gate type bonuses
   on canonical class + evidence; freshness from source recency; strengthen duplicate discount.
4. **Media/text extraction:** extract PDF/doc text so media earns real signal and near-dup sees
   full content; floor empty/marker files.
5. **Regenerate a deduped, class-stratified calibration sample** (canonical representatives,
   not copies; include media, code, docs, schemas in proportion).
6. **Then** label Phase 2 and document weight changes.
7. Fix roadmap phase-1 evidence to be reproducible; only then proposal-engine calibration;
   then Phase 3 pilot.

## Tests To Add

- Scoring: a temp/worktree/generated-class asset scores in the low band; a canonical schema
  with evidence scores higher than an identical-typed temp copy.
- Scoring: an empty/marker file (`__init__.py`, `.DS_Store`) floors out and is not typed as
  evaluation/schema from path alone.
- Scoring: media value varies with extracted-text presence (content-blind regression guard).
- Scan: `.pytest-tmp-root` / `pytest-of-*` / `.DS_Store` are excluded by default config.
- Identity: near-dup uses full extracted text, not just the 5 KB excerpt (shifted-content +
  containment cases); exact-dup group pairing is bounded for large identical groups.
- Calibration: sampler returns class-stratified, deduped records (no >1 copy of a cluster).
- Schema conformance: emitted asset/chunk/delta/duplicate records validate against registered
  JSON Schemas.
- Roadmap: phase status does not flip to complete on git-ignored-only evidence.

## Open Questions For Lowell

1. Is the catalog's job to inventory **everything observed** (including temp/worktree copies as
   lineage) or only **portfolio assets**? This decides exclude-vs-quarantine for sandboxes.
2. Should PDFs/docs get text extraction in v1 (unlocks media value + near-dup) or stay deferred?
3. What's the intended human-label budget per quarter? It bounds how much candidate volume the
   loop can ever clear.
4. Is phase-1 "complete" acceptable on local-only evidence, or must roadmap status be
   reproducible from a clean clone?
5. Should `confidence`/grades be calibrated to probabilities, or renamed to heuristic strength
   until labels exist?

## Evidence Reviewed

- Authority/docs: AGENTS.md, AI_FRONT_DOOR.md, MACHINE_NAVIGATION_MANIFEST.json,
  registry/source-of-truth.json, registry/design-authority.json, AI_TABLE_OF_CONTENTS.md,
  docs/ASSET_VALUE_MODEL.md, docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md,
  docs/KNOWLEDGE_GRAPH_MODEL.md, docs/DETERMINISTIC_LEARNING_RULES.md,
  docs/SEMANTIC_EVOLUTION_GRADING.md, docs/CONTEXTUAL_LEARNING_AND_WORKTREE_ARCHAEOLOGY.md.
- Roadmap: roadmap/roadmap.yaml, roadmap/evidence/phase-2-temp-fixture-calibration-research.md,
  roadmap/evidence/phase-2-claude-second-opinion.md.
- Code: src/digital_asset_directory/scoring.py, identity_layers.py (params + near-dup),
  graph_engine.py, extractors.py, catalog.py, config/sources.example.yaml.
- Data: processed/calibration/asset_rating_template.jsonl (50 records, field-level),
  processed/learning/semantic_evolution_candidates.jsonl, processed/catalog/assets.jsonl
  (streamed, basename counts).
- Checks: `git status --short` (clean except this evidence area); `validate` (valid, 61
  checked); `roadmap check --no-update` (phase-0/1 complete computed, phase-2
  awaiting_human_gate); `recommend calibration-review-summary` (50 template / 3 reviewed / gate
  incomplete).
</content>
