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

- [~] **A1. Asset facets on offerings** — `workflow_stages`, `produces`, `consumes`
      added to `schemas/dad-offering-registry.schema.json` (optional, closed enums, COMMITTED). Live-offering backfill is PENDING
      (Codex) — see CODEX KERNEL A1.
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
- [ ] **A4. Wire into graph build + CLI** — `build_lesson_graph(..., infer=False)`
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

---

# CODEX KERNELS (buildable detail for the unchecked boxes)

Read `src/digital_asset_directory/graph_inference.py` first — it is the worked
example for all of this: deterministic, methodology-versioned, candidate-only,
golden-tested. Match its style. Definition-of-done for hard tracks is above.

## CODEX KERNEL A1 — backfill offering facets

For each live offering in `registry/dad-offerings-registry.json`, add the three
optional arrays. Use ONLY the closed vocab (stages: orient, gather_context, plan,
generate, validate, review, ship, learn; artifact_kinds: report, registry_row,
eval_case, lesson, mail_packet, pointer, score, test, profile_evidence,
fix_outcome, context_pack, code_change, review_finding). Suggested map (adjust to
each offering's real role, keep it honest — a wrong facet makes a false edge):

- python-underused-idioms: stages [generate], produces [code_change], consumes [context_pack]
- rust-buildout-guide: stages [plan, generate], produces [code_change, profile_evidence], consumes [profile_evidence]
- python-test-performance-harness: stages [validate], produces [test, report], consumes [code_change]
- rust-shadow-parity-harness: stages [validate], produces [test, report], consumes [code_change]
- ai-engineering-preflight: stages [orient, plan], produces [context_pack], consumes [registry_row]
- agent-skill-library: stages [gather_context], produces [pointer], consumes [registry_row]
- repo-enrollment-mail-governance-safety-harness: stages [ship, review], produces [mail_packet], consumes [review_finding]

The point is to make at least one real produces->consumes chain exist (e.g.
idioms[code_change] -> test-performance[consumes code_change, produces test] ->
a learn-stage asset that consumes test). After backfill run
`write_inference_outputs(hub)` and confirm a real combination appears.

## CODEX KERNEL A4 — CLI + graph-build wiring

1. In `learning.py::build_lesson_graph`, add param `infer: bool = False`. When
   true, call `graph_inference.infer_graph(repo_root)` and merge its
   `inference_nodes` into `nodes` and `inference_edges` into `edges` BEFORE the
   counts/manifest are computed (so coverage_report and edges_by_type include
   inference edges). Inference edges already carry `edge_class="inference"` and
   `method_version`; the manifest's `method_versions_used` will pick them up.
   Keep join-only default (infer=False) so the existing test stays green.
2. New typer sub-app in `cli.py` (mirror how `dad_app`/`mail_app` are added):
   `graph_app = typer.Typer(...)`, `app.add_typer(graph_app, name="graph")`.
   - `graph combinations [--hub]`: calls `write_inference_outputs(cfg.repo_root)`,
     prints the report summary (combination_count, edges_by_type, queue path).
   - `lesson graph` gains `--infer/--no-infer` (default no-infer) that forwards to
     `build_lesson_graph(..., infer=infer)`.
3. Test `test_cli_infer_flag_adds_edges`: build a temp hub with a planted chain,
   call `build_lesson_graph(hub, infer=True)`, assert `member_of` in edges_by_type;
   call with infer=False, assert it is absent.

## CODEX KERNEL A5 — combination review + labeling

Mirror `workflow_parts.py` + `recommend workflow-part-review-*` exactly (it is the
established review-queue idiom in this repo). Queue rows already written by
`write_inference_outputs` to `processed/learning/combination-candidates.jsonl`.
Add `processed/learning/combination-reviews.jsonl` (append-only) with rows:
`{combination_id, decision: accepted|rejected|trial, reviewed_by (named human),
reviewed_at, rationale, review_status: human_reviewed}`. A rejected combination
stays in the reviews ledger as NEGATIVE EVIDENCE: `write_inference_outputs` must
read it and skip re-proposing a rejected combination_id (add a `rejected_ids`
filter before the queue append). Only human `accepted` promotes to A6.

## CODEX KERNEL C1 — exception cluster -> root-cause -> downstream (HARD math)

This is the "really learns and pre-emptively fixes downstream" piece. Design it
deterministic and candidate-only. New module `exception_root_cause.py`.

Inputs: screened events `processed/exceptions/lake/events.jsonl`, fix outcomes,
the offering `depends_on` edges (Track A edge type, declared), and the usage
ledger. Methodology: extend `registry/exception-learning-methodology.json` with a
`root_cause_v1` section (versioned) before emitting anything.

Algorithm (all deterministic, counts not scores):
1. CLUSTER: group events by `(error_fingerprint, normalized_command, affected
   surface class)`. A cluster with events from >= 2 INDEPENDENT repos (apply the
   independence rules already in the buildout doc: same-repo repeats = 1 context;
   same DAD bug/harness/outage != independent) is a `root_cause_candidate`.
2. RANK by dependency order: build the affected-asset subgraph from declared
   `depends_on` edges. Use `graphlib.TopologicalSorter` (py-idiom:graphlib-toposort)
   to get topo order; the UPSTREAM-most affected asset (lowest topo rank that
   appears in the cluster) is the root-cause hypothesis. Emit a
   `root_cause_hypothesis` record (schema exists) naming: cluster id, upstream
   asset, the ordered downstream dependents (everything reachable FROM the root in
   the depends_on DAG), method_version, and independence evidence. CycleError ->
   mark `dependency_cycle_suspected`, do not guess a root.
3. DOWNSTREAM PRE-EMPTION: for each downstream dependent asset, find repos that
   `uses_asset`/`depends_on` it (graph join) but have NOT yet reported the failure.
   Emit a candidate pre-emptive context-pack warning + pointer mail (NEVER a source
   write) for those repos: "asset X you depend on has an upstream root cause in Y;
   here is the validated fix ref once it exists."
4. GATES (reuse buildout doc's Self-Learning Rules): no global rule from one event;
   no pre-emptive notice to public-facing repo from private-origin evidence without
   human release; counts only below N=10 reviewed; every hypothesis candidate-only.

Golden test: synthetic hub with a 3-asset depends_on chain A->B->C, exceptions
reported on B and C from 2 repos, and a third repo using A but silent. Assert the
root-cause hypothesis names A (upstream-most), lists B and C as downstream, and
stages exactly one pre-emptive notice for the silent repo. Assert determinism.

## CODEX KERNEL B1 — card projections (cross-type chunking)

New `card_projection.py`. One `AssetCard` dataclass (frozen, slots) with the
shared facets from `graph_inference._AssetCard` PLUS `key_terms` and
`provenance_ref`. Build projections per source type (table in
`docs/GRAPH_BUILDOUT_HANDOFF.md` §3): registry rows (already cards), lesson records
(marker-code `key=value` lines first), markdown (heading sections), python (`ast`
top-level items). The inference engine then runs on projections instead of only
offerings, so lessons/docs/code can join. Determinism + term registry (B2) gate
edge quality. Do B2 (term registry + one shared tokenizer — there are 3 copies:
`dad_library._tokenize`, `learning._pattern_key`, and the mail tokenizer) before
widening projections, or edges will be noisy.

## Environment note for the takeover agent

A background `git pull --rebase origin main` + hard-reset loop runs on this repo
and reverts uncommitted edits to shared registries/schemas on `main`. Work on a
branch and commit early. The Track A kernel is committed on branch
`dad-graph-inference-kernel` (commit "Add graph inference & combination discovery
kernel"). Rebase/cherry-pick it forward rather than rebuilding.

## Track H — Transport & communications (three-plane) `[HARD kernel done]`

Design: `docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md` (+ Implementation Manifest).
Roadmap gate: `roadmap/roadmap.yaml` phase-13-transport-data-plane.

- [x] **H1. Transport kernel** — `src/digital_asset_directory/transport.py`:
      fail-safe DAD_DATA_ROOT resolver, copy-verify-activate migration (never
      deletes/never runs git), OneDrive guard, read-only legacy-transport
      auditor + deduped upgrade queue. Proof: `tests/test_transport.py` (5
      golden tests, green). Branch fable/transport-kernel.
- [x] **H2. First live audit** — hub upgrade_required (161 tracked data files);
      8/10 enrolled repos queued; logos-scripture-graph has tracked spool JSONL
      (protected, central-only). Output: processed/reports/transport_audit.json.
- [ ] **H3. M0a reroute writers through data_path** — CODEX (manifest list).
- [ ] **H4. M0b CLI (data init/migrate/status, transport audit) + detector
      v1.1 contract_missing signal** — CODEX.
- [ ] **H5. M1 daemon run-cycle + Task Scheduler + heartbeat** — CODEX.
- [ ] **H6. M2 dad-journal checkpoint + remote-outbox ingest** — CODEX.
- [ ] **H7. Doc/template wave (9-item list in manifest) + enrollment upgrade
      wave from the queue** — CODEX + human wave approval.
- [ ] **H8. M3 Cloudflare relay** — DEFERRED (phase-10a cloud gate).
