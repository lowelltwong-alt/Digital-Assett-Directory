# Algorithm Calibration and Fixes — Handoff for Codex

Status date: 2026-06-24. Author: Claude Code (review + first fixes). Audience: Codex (next implementer).

This is a self-contained handoff. Read `AGENTS.md`, `AI_FRONT_DOOR.md`, and `registry/design-authority.json`
first, then run the preflight before material work. All scores/edges remain candidate-only; do not
promote any heuristic output to source-of-truth.

## 1. What was already fixed (committed-ready, tests added)

Three contained algorithmic defects were fixed and verified (`pytest` 77 passed, `ruff` clean,
`validate` valid):

1. **Word-boundary keyword extraction.** `extractors._matches` used substring `phrase in text`,
   so `agent` matched `management`, `graph` matched `paragraph`, `rag` matched `storage`. Now uses
   `_phrase_pattern` with `(?<!\w)…(?!\w)` boundaries applied only at alphanumeric ends (so `recall@`,
   `tf-idf` still match). This is the substrate for tags/capabilities/needs → it feeds edges, synergy,
   scoring, and recommendations. File: `src/digital_asset_directory/extractors.py`.
2. **Deterministic token selection.** `graph_engine.build_edges` did `list(toks)[:500]` over a `set`;
   CPython randomizes str hashing, so the chosen 500 tokens (and therefore the edges) varied per run
   for token-rich assets. Now `sorted(toks)[:500]`. File: `src/digital_asset_directory/graph_engine.py`.
3. **Dead scoring components made real.** `provenance` was always `0.95` (every asset has
   `content_hash`) and `uniqueness` was a literal `0.55` — ~21% of the weight carried zero information.
   Now `provenance` keys off `content_sha256` (0.95 read / 0.55 metadata-only / 0.2 none) and
   `uniqueness` is `1 - min(0.6, 0.15*(cluster_size-1))` from duplicate-cluster membership. `catalog.run_scan`
   re-scores assets with `duplicate_counts` after `build_identity_layers`. The `no_provenance` penalty
   now keys off `content_sha256`+`source_provenance`. Files: `scoring.py`, `catalog.py`.
   Demonstrated effect: a 5-asset mix that previously shared identical 55.0/95.0 now spreads ~29 points.

## 2. Remaining algorithm fixes (do these next)

### 2.1 IDF-weighted similarity (replaces unweighted Jaccard) — highest precision lever
- Where: `utils.jaccard` usage in `graph_engine.build_edges` (`related_to` edges) and
  `context_pack.rank_assets`.
- Problem: Jaccard weights every token equally; shared domain-boilerplate scores like shared rare terms.
- How: the postings loop already yields document frequency `df[token] = len(postings[token])`.
  Compute `idf = log(N / df)` and score a pair by IDF-weighted cosine over shared tokens, not
  `|A∩B|/|A∪B|`. Apply the same to `rank_assets` (query-term match should weight rare terms).
- Also: when truncating to 500 tokens, prefer the **lowest-df (rarest)** tokens, not the first sorted —
  they carry the signal. (Determinism is already fixed; this is a quality upgrade.)
- Recalibrate `related_similarity_threshold` (currently 0.34) on the labeled set (see §3).

### 2.2 Near-duplicate algorithm: shingling/MinHash + containment
- Where: `identity_layers.build_asset_chunks` (fixed 1200-char windows from offset 0) and
  `_near_duplicate_records` (`overlap = |shared| / max(len_left, len_right)`).
- Two math problems:
  - Position-aligned windows miss shifted/reordered content (one inserted char → zero shared chunks).
  - `max` in the denominator misses **containment** (a small file fully inside a large one scores low).
- How: replace fixed windows with **overlapping k-token shingles + a small MinHash signature**
  (e.g., 64 permutations) per asset; estimate Jaccard from signature agreement. Deterministic and
  shift-invariant. Separately compute `containment = |shared| / min(...)` and emit a distinct
  `contained_in`/`subset_of` candidate when containment is high but symmetric overlap is low
  (register the new edge type if added). Chunk full extracted text, not only the 5 KB excerpt.
- Until replaced: lower near-dup confidence (cap ≤0.8) and state in the delta/cluster summary that
  evidence is excerpt-prefix, position-aligned only (see open red-team item §4).

### 2.3 Synergy: separate sameness from complementarity; exclude duplicates
- Where: `radars.detect_synergies` (`score = 0.35*outcome + 0.35*need + 0.20*diversity + 0.10*tag_overlap`).
- Problems: rewards shared outcomes/tags (the signature of *duplicates*, not synergies); the `OUTCOMES`
  vocabulary has only 6 values so `min(1, shared/2)` saturates; nothing excludes near-duplicate pairs.
- How: model synergy as complementarity given proximity — high need↔capability coverage with *moderate*
  (not total, not zero) domain overlap. Drop or down-weight `tag_overlap`. Gate out any pair already in
  an `exact_duplicate_of`/`near_duplicate_of` cluster (you now have them). Re-fit the `/2`, `/5`
  normalizers against the real outcome/capability distribution.

### 2.4 Lower-severity
- Dead config key `risk_penalties.unknown_license` (`config/scoring.yaml`) is never read by `score_asset`;
  either wire it (GitHub `license` metadata is available) or remove it.
- Risk penalties are absolute subtractions from a [0,1] weighted average (`scoring.py`); prefer a
  multiplicative risk factor `raw *= (1 - risk)` for interpretability.
- `freshness` is double-counted (a weighted component and a `stale` penalty); pick one lever.
- After §2.1, consider percentile/z-score normalizing components across the corpus before weighting so
  `value_score` reflects relative standing rather than absolute heuristic sums.

## 3. What to calibrate and how

Calibration data already exists in the repo's workflows:
- Proposal review labels: `processed/proposals/proposal_review_template.jsonl` (`useful`/`not_useful`,
  `safe`/`unsafe`, `decision`) via `recommend proposal-review-*` commands.
- Asset score labels: `processed/calibration/asset_rating_template.jsonl`
  (`too_high`/`about_right`/`too_low`) via `recommend calibration-*` commands.
- Both are produced from a real scan and reviewed under the phase-2 gate (≥50 asset ratings, ≥25 per
  proposal engine, plus false-positive/false-negative notes).

Calibrate in this order:
1. **Thresholds → ROC/PR on labels.** For `related_similarity_threshold` (0.34), near-duplicate overlap
   (0.5), and `synergy_alert_threshold` (0.64): treat the human `useful`/`true-positive` labels as ground
   truth, sweep the threshold, and pick the operating point by target precision (this is a review queue —
   favor precision to avoid alert fatigue). Record the chosen point and the precision/recall in
   `roadmap/evidence/`.
2. **`confidence` → probability calibration.** The `confidence` fields (bands at 0.78/0.55/0.45) are
   monotone transforms of heuristic scores, not probabilities. Fit a logistic/Platt mapping from raw
   score → P(useful) on the labels, or rename the field to `heuristic_strength`. Do not present
   uncalibrated values as probabilities.
3. **Scoring weights → against `too_high`/`too_low` ratings.** Use the asset-rating labels to adjust
   `config/scoring.yaml` weights (e.g., fit a simple ordinal/logistic model of rating vs components,
   or do guided manual adjustment). Document every weight change with before/after rating distributions
   per the existing `proposal-calibration-evidence` / asset calibration evidence flow. Keep the
   deterministic baseline; do not introduce embeddings until the phase-4 privacy/provider/eval gates pass.

Acceptance: a calibration is "done" only with (a) the labeled sample meeting the phase-2 gate counts,
(b) the chosen thresholds/weights and their precision/recall recorded as roadmap evidence, and
(c) `pytest`/`validate`/`roadmap check` green. Calibration must not auto-promote candidates.

## 4. Open red-team items (from the distribution review; still relevant)
- **Near-dup over-promises** (subsumed by §2.2): excerpt-prefix, position-aligned overlap labeled up to
  0.95. Constrain confidence/labeling.
- **Scan summary honesty:** `catalog.run_scan` hardcodes `source_files_mutated: False` while
  `local_scan` now only soft-flags changed-during-scan files; add `changed_during_scan_count` to the
  summary and `scan_summary.md`.
- **Schema conformance not exercised:** add fixtures/tests validating a `model_dump()` of asset/chunk/
  delta/duplicate records against the registered JSON Schemas (`jsonschema` is a dep). Registration ≠
  conformance.
- **Cloud-placeholder guard is Windows-only** (`local_scan._is_cloud_placeholder` reads
  `st_file_attributes`); document it and add a conservative non-Windows fallback before scanning on
  other platforms.
- **Before any public exposure:** add `CODEOWNERS`, branch protection, and a CI path-guard so external
  feedback PRs cannot run workflows; or keep the public-feedback docs clearly marked "not yet live."
  (Repo is private for now; non-blocking until it goes public.)

## 5. Operating notes
- Run the CLI with `PYTHONPATH=src` (package not installed in dev shell).
- Tests use markers: `pytest -m unit | integration | proposals | calibration`; `nox -s tests|fast|changed`.
- Validation baseline: `pytest`, `cli validate`, `cli roadmap check --no-update`.
- Keep changes narrow and reversible; capture a postflight; preserve append-only raw observations.
