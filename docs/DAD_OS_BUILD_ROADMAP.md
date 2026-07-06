# DAD OS Build Roadmap (living checklist)

Purpose: turn DAD into the operating system the user runs all work through — a
self-improving library + exceptions-lake + graph that finds novel high-leverage
asset combinations for workflows nobody has named yet, and deploys learning back
into itself and every repo it makes.

This file is the **handoff checklist**. Fable/Opus builds the hardest, most
algorithm-heavy pieces (marked `[HARD]`) and checks them off. Codex 5.5 finishes
the rest using the kernel detail in each section. A coding agent can take over at
any unchecked box.

Convention: `[x]` done + validated (tests green), `[~]` in progress / partial,
`[ ]` not started. Every `[x]` names the files and the test that proves it.

---

## Track A — Graph inference & combination discovery `[HARD]`

The crown jewel. The user: "how do we not only store digital assets but often
look for novel and important combinations for workflows we don't know about... a
lot of that is how good the edges are." This is deterministic graph algorithm
work (stage adjacency, produces/consumes chaining), not ML.

- [x] **A1. Asset facets on offerings** — `workflow_stages`, `produces`, `consumes`
      added to `schemas/dad-offering-registry.schema.json` (optional, closed enums)
      and backfilled onto all offerings in `registry/dad-offerings-registry.json`.
      Proof: `tests/test_graph_inference.py::test_offering_facets_are_valid_vocab`.
- [x] **A2. Inference methodology** — `registry/graph-inference-methodology.json`
      (+ `schemas/graph-inference-methodology.schema.json`): closed
      `workflow_stages` and `artifact_kinds` vocabularies, the discovery rules with
      versions/thresholds, output labels, and the anti-false-confidence gate
      (counts not percentages below N reviewed). Satisfies the
      calculated-score-requires-methodology learning rule.
      Proof: `tests/test_graph_inference.py::test_methodology_validates`.
- [x] **A3. Combination discovery engine** — `src/digital_asset_directory/graph_inference.py`.
      Deterministic. Produces `complements` (stage-adjacency + need-coverage),
      `co_used_with` (usage co-occurrence), and `combination_candidate` hypernodes
      with `member_of` edges from produces/consumes chains (length >= 3). Every
      inference edge carries `method_version`. Writes a review queue.
      Proof: `tests/test_graph_inference.py` (golden mini-hub, precision-exact).
- [x] **A4. Wire into graph build + CLI** — `build_lesson_graph(..., infer=False)`
      gains an inference pass; `asset-dir lesson graph --infer` and
      `asset-dir graph combinations` surface candidates + review queue.
      Proof: `tests/test_graph_inference.py::test_cli_infer_flag_adds_edges`.
- [ ] **A5. Combination review + labeling loop** — `asset-dir graph combo-review-queue`
      and `graph combo-label` (accept/reject/trial), writing
      `processed/learning/combination-reviews.jsonl`. Rejected combos preserved as
      negative evidence. Labels feed threshold calibration (reuse the
      `dad calibration` idiom). CODEX: mirror `recommend workflow-part-review-*`.
- [ ] **A6. Adopted combination -> workflow node** — an accepted combination
      graduates into a `workflow` node with ordered `fills_stage` edges; a
      `workflow` offering_type row can be generated for the catalog. CODEX.
- [ ] **A7. Exception-aware inference edges** — `same_failure_pattern_as`,
      `likely_prevented_by`, `gap_evidence_for` over the exceptions lake, gated on
      the exception learning methodology. CODEX, after Track C lands facets on
      exception clusters.

## Track B — Card projections & cross-type chunking `[HARD]`

So edges can cross prose / code / JSON / lessons. Edges are computed on card
projections, never raw bodies (see `docs/GRAPH_BUILDOUT_HANDOFF.md` §3).

- [ ] **B1. Projection builder** — `src/digital_asset_directory/card_projection.py`:
      one `AssetCard` per source type (registry row, lesson record, markdown
      heading-section, python `ast` item). Shared facets: id, category,
      capabilities, task_types, workflow_stages, produces, consumes, key_terms,
      version, provenance_ref. CODEX. Kernel + per-type table in the handoff doc.
- [ ] **B2. Term registry** — `registry/graph-term-registry.json`: canonical terms,
      synonym lists, facet ownership, gap-list loop. Consolidate the 3 tokenizer
      copies into one normalizer module. CODEX.
- [ ] **B3. Cross-format identity rule** — one node when the same asset exists as
      md + json (shared dir or declared `asset_id`). CODEX; decision needed first
      (see handoff §10 open problems).

## Track C — Exceptions lake -> real learning propagation `[HARD math]`

Codex has built capture/collection/taxonomy/backfill. The unbuilt hard part is the
**root-cause & propagation reasoner**: cluster exceptions, find an upstream root
cause, identify downstream dependents, and pre-emptively fix them. This is the
user's "really and actually learns and deploys that learning."

- [ ] **C1. Deterministic cluster -> root-cause candidate** — group screened events
      by error_fingerprint + normalized command + affected surface; emit a
      `root_cause_hypothesis` with the dependency-ordering math (topological rank
      of affected assets via `graphlib`). CODEX gets the kernel below.
- [ ] **C2. Downstream dependent finder** — from a root-cause asset, walk
      `depends_on` / `uses_asset` edges to list repos/assets that will hit the same
      failure; emit pre-emptive context-pack warnings. CODEX.
- [ ] **C3. Fix-propagation ledger** — when a fix validates for one event, stage
      candidate pre-emptive notices for dependents (pointer mail only, never source
      writes). CODEX.

## Track D — Library-first preflight escalation ladder

The user: repos check DAD first at preflight/midflight for harnesses; stubborn
issues dig deeper or ask DAD to research and remember.

- [~] **D1. Context-pack already returns assets/patterns/deferred-mail** (built).
- [ ] **D2. Escalation ladder** — `easy_local_fix -> known_template -> hard_issue_lookup
      -> new_exception -> solution_lineage_review` wired into midflight so a repeated
      failure auto-triggers `exceptions hard-issue-lookup`. CODEX; ladder is
      specified in `docs/DAD_EXCEPTIONS_LAKE_BUILDOUT.md`.
- [ ] **D3. "Ask DAD to research" bridge** — a hard-issue with no library answer
      opens a bounded research-intake request (Track already exists in
      `research_intake.py`); wire the trigger + the remember-the-answer loop. CODEX.

## Track E — Mail actually acted on, not just collected

The user's worry: repos collect mail but never act on high-value lessons.

- [x] **E0. Deferred-mail resurfacing** (built earlier): task-match OR watched-asset
      brings saved mail back at preflight.
- [ ] **E1. Adoption-follow-through audit** — `asset-dir mail follow-through` flags
      inbox lessons with no triage/adoption/usage record after N days, per repo,
      as a coverage gap (not spam). CODEX.
- [ ] **E2. Value-weighted nudge** — high-leverage patterns (pattern registry
      `leverage: very_high`) that a repo received but never adopted get one bounded
      digest nudge; DAD notes when the repo later evolves to that lesson. CODEX.

## Track F — Public asset scanning (ingest high-signal external assets)

- [x] **F0. Trusted-source registry + research intake pipeline + language frontier
      radar** (built by Fable + Codex): quarantine -> screen -> human-approved
      pointer promotion.
- [ ] **F1. GitHub high-signal scanner** — bounded, pointer-only discovery over
      trusted orgs into intake quarantine (never auto-promote). CODEX; must reuse
      the screening + human-approval gates.

## Track G — Repo templates / OS shell

- [~] **G1. `asset-dir agent new` scaffolds a governed repo** (built).
- [ ] **G2. OS-grade template** bundling context-map, mailbox, exceptions outbox,
      events outbox, and the core AGENTS contract in one reviewed wave. CODEX.

---

## Definition of done for the hard tracks (A, B, C)

1. Deterministic: same inputs -> byte-identical output (sorted, no inline
   timestamps except top-level `generated_at`).
2. Every inference edge / score cites `method_version` from a named methodology.
3. Candidate-only: nothing promotes itself; a human/queue promotes.
4. Precision provable on a synthetic golden mini-hub with planted structures AND
   noise; the test asserts exactly the planted structures are found.
5. Rebuildable: graph/queue are compiled artifacts; raw records stay source truth.

## Where the kernels live

- Track A kernel: this repo now — `graph_inference.py` (built, read it as the
  worked example for Tracks B/C).
- Track B/C kernels: `docs/GRAPH_BUILDOUT_HANDOFF.md` and the "CODEX KERNEL"
  sections appended to this file as each hard track is scoped.
