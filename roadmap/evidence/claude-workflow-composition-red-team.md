# Claude Workflow Composition Red Team

Date: 2026-06-26. Reviewer: Claude Code (independent, read-only design + red-team). Status:
candidate design evidence only. No source repos mutated, no GitHub scanning, no private rows
imported, no roadmap phase marked complete. This file is the only file written.

## Scope And Headline

Goal: design a "workflow part and recomposition recognition" layer so DAD recognizes not just
whole workflows but **recombinable parts** that future agents can reassemble in other repos.

**Headline red-team finding: the biggest risk here is not missing machinery — it is over-building
it.** DAD already has a ~50-entry edge registry, a 19-entry context-tag registry, a 27-pattern
asset-pattern registry, and instance-class/duplicate discounts in scoring. Most of the proposed
edge types and context fields **already exist or have near-synonyms**. Adding the full proposed
set verbatim would create semantic-conflict debt and ontology overcomplexity (a named failure
mode). The design below therefore prioritizes **reuse + a small new record + ~4 genuinely new
edges**, deterministic v1, candidate-only.

A second framing point: **asset patterns (existing) are whole-workflow shapes; workflow parts
(new) are the recombinable sub-units beneath them.** A `WorkflowPartRecord` should reference the
asset-pattern it belongs to, not duplicate it.

## 1. Repo Surfaces To Scan For Reusable Parts

DAD already scans these files; "recognition" means deriving a part from existing catalog
signals, not new scanning. Map each surface to a candidate `part_type` and the deterministic
signal already available (asset_type, capabilities, path role, pattern match):

| Surface | part_type (candidate) | Deterministic signal already in catalog |
|---|---|---|
| Validators, schema-conformance tests | `validator` | asset_type test/schema + `validate_contracts` |
| JSON Schema / OpenAPI / type contracts | `contract` | asset_type schema + `schema_contract` tag |
| CI workflows, pre-push hooks, nox/make/just | `gate` / `runner` | `.github/workflows`, hook paths, `human_gate` |
| Runbooks, operating manuals, AI work-cycle docs | `orchestrator` | workflow asset_type + preflight/postflight language |
| Prompts, prompt headers | `prompt_part` | path `prompts/`, prompt language |
| Agents, skills, capability registries | `capability_provider` | asset_type agent/skill + capability registry |
| Review packets, gold sets, scorecards | `human_gate` / `eval_gold` | `gold_promotion` tag, `has_gold_set`/`has_review_packet` |
| Exception logs, pressure vectors | `learning_signal` | exception-lake pattern, `produces_learning_signal` |
| Data-flow / authority maps | `boundary_map` | cross-repo authority pattern |
| Changelogs, ADRs/decision records | `decision_record` | asset_type decision |
| Postflights, handoffs, lessons | `lesson_part` | learning-loop pattern, `learned_from` |
| Calibration evidence, A/B reports | `calibration_gate` | `calibration` tag, A/B pattern |
| Security/intent scanners, quarantine policy | `quarantine_gate` | security_scanner pattern |
| Temp worktrees / pytest copies | **NOT independent parts** | `temp_fixture_noise` tag → lineage only |

Guardrails on surfaces (carry forward existing discipline):
- **Public-safe boundary applies (`docs/PUBLIC_SAFE_SOURCE_SWEEPS.md`):** recognize parts from
  canonical workflow/code/schema paths only; never from `data/`, `output/`, raw snapshots,
  CSV/SQLite/PDF/HTML/ZIP lanes. A part record stores role/metadata, never row content or private
  examples.
- **Temp/worktree exclusion:** parts are recognized once per asset family; pytest/worktree copies
  are `lineage_evidence_for`, never independent parts (reuse the existing instance-class +
  duplicate-representative discount).

## 2. WorkflowPartRecord (proposed new contract)

New first-class record, sibling to `AssetChunkRecord`/`DuplicateClusterRecord`. The proposed
fields are good; below is a refined set marking what v1 can populate **deterministically** vs what
needs **human review** (honesty matters — v1 cannot infer dataflow it cannot see).

| Field | v1 source | Notes |
|---|---|---|
| `part_id` | deterministic (stable id from family + role) | one per family, not per copy |
| `part_type` | deterministic | from table above |
| `source_asset_ids` | deterministic | canonical members; copies excluded |
| `asset_pattern_id` | deterministic | link to existing pattern; **do not duplicate the pattern** |
| `role_in_workflow` | deterministic (cue-based) | validator/gate/orchestrator/etc. |
| `inputs` / `outputs` | **human or structured front-matter only** | v1 leaves empty unless the asset declares them; do not hallucinate dataflow |
| `preconditions` / `postconditions` | **human / declared only** | same caution |
| `side_effects` | **human review** | esp. writes, network, source mutation risk |
| `authority_boundary` | deterministic (from source_provenance/trust_zone) | the cross-boundary guard |
| `human_gates` | deterministic (cue) + human confirm | from `human_gate`/review-packet links |
| `validation_commands` | deterministic if declared | else empty → lowers maturity |
| `failure_modes` | **human / exception-lake derived** | candidate from `produces_learning_signal` |
| `applies_when` / `does_not_apply_when` / `danger_if_misapplied` | reuse context-tag taxonomy + human | **required** before any preflight use |
| `composition_affordances` | derived from edges | what it can connect to |
| `incompatible_parts` | derived from edges | authority/format conflicts |
| `example_workflows` | deterministic **references only** | sanitized asset-id references, never embedded private content |
| `context_tags` | deterministic | reuse `registry/context-tag-registry.json` |
| `maturity` | deterministic | new: `recognized` < `validated` < `reused` < `reviewed` |
| `confidence` / `risk` | deterministic (methodology-cited) | per `score_methodology` rule |
| `provenance` (method, scan_id, evidence) | deterministic | required by edge/record rules |
| `review_status` | deterministic | always `generated_candidate` |
| `methodology_version` | deterministic | e.g. `workflow-part-recognition-v1` |

Add `maturity` and `methodology_version` (not in the original list); they are what let the
assembly pack rank and what the `score_methodology` deterministic-learning-rule requires.

## 3. Edge Types For Recomposition — reuse first

**Already in `registry/edge-type-registry.json` (REUSE, do not re-add):**
- `composes_with`, `unsafe_composition_with`, `should_precede`, `depends_on`, `satisfies_need`,
  `requires_human_gate`, `governed_by`, `supports_but_cannot_override`, `routes_to`,
  `has_workflow_step`, `has_member_asset`, `stabilized_by`, `tests`, `has_gold_set`,
  `has_review_packet`, `produces_learning_signal`, `failed_before`, `fixed_by`,
  `learned_from_attempt`, `contaminates_if_default`, `blocked_by`.

**Proposed-vs-existing mapping (avoid near-synonym proliferation):**

| Proposed | Verdict | Reason |
|---|---|---|
| `requires_before` | **reuse** `should_precede` / `depends_on` | hard order = depends_on; recommended order = should_precede |
| `validates` | **reuse** `tests` + `stabilized_by` | already covered |
| `gates_promotion_of` | **reuse** `requires_human_gate` + `governed_by` | already covered |
| `composes_with` | **exists** | |
| `incompatible_with` | **add (narrow)** | distinct from `unsafe_composition_with`: structural/format incompatibility vs risky-without-review |
| `learned_from_failure` | **reuse** `learned_from_attempt` / `failed_before` / `fixed_by` | already covered |
| `should_precede` | **exists** | |
| `unsafe_without` | **reuse** `blocked_by` + `unsafe_composition_with` | "B unsafe without gate A" = blocked_by(A) |
| `reusable_in_context` | **reuse** `applies_when` + context tags | already a first-class mechanism |
| `quarantines` | **add** | security scanner → input; no current edge |
| `produces_input_for` | **add** | dataflow: output of A is input to B; genuinely missing |
| `substitutes_for` | **add** | interchangeable parts; missing (≠ variant_of, which is lineage) |
| `specializes` / `generalizes` | **add (pair)** | part hierarchy; missing |

**Net new edges to add (5):** `produces_input_for`, `substitutes_for`, `specializes`,
`generalizes`, `quarantines` — plus optionally `incompatible_with` if structural incompatibility
is truly distinct from `unsafe_composition_with`. Everything else reuses existing vocabulary.
Adding the full 14 would duplicate ~9 existing edges and is **not recommended**.

## 4. Workflow Assembly Context Pack

Extend the existing `context_pack` machinery rather than build a new retriever.

Input: `task_type` (e.g., "build a source-faithful retrieval pipeline") + `repo_context`
(target repo's authority plane, existing assets, allowed directions).

Pipeline (deterministic v1):
1. **Retrieve** candidate parts whose `applies_when`/context_tags match task_type and whose
   `authority_boundary` is compatible with the target repo plane.
2. **Rank** by a cited formula over: fit (tag/role match), maturity (`recognized<validated<reused
   <reviewed`), validation strength (has passing `validation_commands`), risk (lower = better for
   default), and prior-use feedback (reuse `asset_use_pay_forward` records — actual use > projected).
3. **Assembly order** via topological sort over `depends_on`/`should_precede`/`produces_input_for`;
   surface cycles and ambiguous order as review items, not silent guesses.
4. **Missing gates and dangers**: list parts that are `blocked_by`/`unsafe_composition_with`/
   `requires_human_gate` an absent part, plus each part's `danger_if_misapplied` and
   `does_not_apply_when`.
5. **Candidate-only** output: every suggestion carries confidence, methodology version, and
   "this is a planning candidate, not authority" — same posture as proposals.

Output is a "suggested assembly" with explicit holes (missing validator, missing gate,
cross-boundary edge requiring human approval), not a ready-to-run recipe.

## 5. Red-Team Risks And Guards

| Risk | Guard |
|---|---|
| Over-recommending process | Maturity + risk-tier gating; only surface parts above an evidence threshold; an explicit ceremony budget per task tier (reuse `load_bearing_decision`/`fresh_eyes_review` tags). Default to *fewer, validated* parts. |
| Private/source data into public DAD | Public-safe boundary: parts carry role/metadata only; `example_workflows` are sanitized asset-id references, never embedded content; no recognition from data/output/row lanes; part records git-ignored until curated. |
| Generated candidates as truth | `review_status=generated_candidate`, mandatory `methodology_version`, confidence; assembly pack labeled candidate; no auto-promotion. |
| Recombining across incompatible authority | `authority_boundary` field + `unsafe_composition_with`/`incompatible_with` + cross-repo authority map; assembly **refuses** to compose source-owned parts across planes without `requires_human_gate`. |
| Legal/Bible-specific rules applied too broadly | Mandatory `applies_when`/`does_not_apply_when`/`context_tags` with domain scope; domain-specific parts (Logos scripture, legal chunking) tagged non-universal; never surfaced outside matching domain without a human gate. |
| Temp worktree noise | `temp_fixture_noise` tag + instance-class discount; copies → `lineage_evidence_for`, never independent parts. |
| Score inflation from repeated copies | Recognize one part per asset family (duplicate-representative discount already exists); part maturity counts distinct reuse, not copy count. |
| Stale docs | Freshness on source members; parts whose `validation_commands` have not passed recently are marked `unverified` and cannot be auto-suggested for high-risk assembly. |
| Missing validation | No `validation_commands` ⇒ low maturity ⇒ excluded from high-risk assembly; surfaced as "needs validation" in the pack. |

## 6. Implementation Phases (checklist)

**Phase A — schema + registry design (deterministic, no behavior change):**
- [ ] `schemas/workflow-part.schema.json` (fields in §2), `additionalProperties:false`, `review_status` required.
- [ ] Register in `registry/schema-registry.json`; add `WorkflowPartRecord` Pydantic model + schema-conformance test.
- [ ] Add only the ~5 new edges to `registry/edge-type-registry.json` with method/evidence rule; document in KG model + ontology.
- [ ] Add a `part_type` controlled vocabulary registry; reuse existing context tags.
- [ ] Human decision recorded on public-vs-private part catalog (see §Open decisions).

**Phase B — deterministic recognizer over current catalog:**
- [ ] Recognize parts from existing assets (asset_type + capabilities + path role + asset_pattern match), one per family.
- [ ] Populate only deterministically-knowable fields; leave inputs/outputs/preconditions empty unless declared.
- [ ] Emit `generated_candidate` part records + edges to `processed/learning/` (git-ignored); never to source.
- [ ] Exclude temp/worktree/data/output lanes; apply instance-class + duplicate discounts.

**Phase C — workflow assembly report:**
- [ ] `recommend workflow-assembly --task-type ... --repo-context ...` → candidate pack (markdown + JSONL).
- [ ] Cited ranking formula; topological assembly order; missing-gates/dangers section; candidate-only banner.

**Phase D — human review queue:**
- [ ] Calibration template for parts (usefulness/safety/novelty/actionability with the dead-axis fixes from the proposal red-team: make safety carry cross-boundary flags, define actionability as "usable now").
- [ ] Reviewer labels + structured notes; dedupe/representative sampling so one family ≠ N copies.

**Phase E — preflight integration (only after review):**
- [ ] Promote only reviewed, high-maturity parts into preflight/midflight suggestions, behind risk-tier gating.
- [ ] Require `applies_when`/`danger_if_misapplied` on any promoted part; midflight ack for high-risk composition.

**Phase F — repo-local learning-loop feedback:**
- [ ] Capture `asset_use`-style feedback on part reuse in other repos (files-only, candidate-only) to feed maturity/ranking.
- [ ] Never auto-update scores; feedback is candidate calibration evidence.

## Open Human Decisions

1. **Public vs private part catalog.** Are workflow parts public-safe (architecture only) or do
   some carry domain-specific examples that must live in a private store? Decides where part
   records and example references may be tracked.
2. **First-class contract vs doc.** Which of the existing 27 patterns become first-class
   `WorkflowPartRecord` families now, vs stay as docs? (Recommend starting with the 3–4 highest-
   leverage, well-validated ones: AI work-cycle governance, evaluation/contract, source-faithful
   chunking gate, security scanner/quarantine.)
3. **Cross-repo by default?** Should part recognition and assembly run same-repo/same-family first
   (per the Phase 2B finding that cross-repo lexical evidence is weak), and only cross-repo with
   stronger evidence + human gate?
4. **Ceremony threshold.** At what risk tier does the assembly pack appear in preflight vs stay an
   on-demand report? (Avoid process-everywhere.)
5. **Domain-scoping policy.** Confirm that legal/scripture/recruiting parts are tagged
   non-universal and gated out of unrelated domains.

## Files Inspected

- `AGENTS.md`, `AI_FRONT_DOOR.md`, `AI_TABLE_OF_CONTENTS.md` (current).
- `docs/CROSS_REPO_WORKFLOW_ASSET_PATTERNS.md`, `docs/PUBLIC_SAFE_SOURCE_SWEEPS.md`.
- `registry/asset-pattern-registry.json` (27 patterns), `registry/edge-type-registry.json` (~50
  edges), `registry/context-tag-registry.json` (19 tags).
- Prior context from this session's earlier reads: scoring instance-class/duplicate discounts
  (`tests/test_scoring.py`), identity layers, Phase 2/2B calibration evidence.

## Assumptions

- `docs/WORKFLOW_SWEEPS.md` and `docs/PROFESSIONAL_RECRUITING_INTELLIGENCE_WORKFLOW.md` were not
  re-read in full this pass; their content is summarized inside
  `docs/CROSS_REPO_WORKFLOW_ASSET_PATTERNS.md`, which I relied on. Verify before implementing the
  recruiting-domain parts (they carry the strongest privacy constraints).
- The repo is under active parallel local edits; registry contents above are a point-in-time read
  and should be re-confirmed at implementation time.
- No `WorkflowPartRecord` / workflow-part schema exists yet (parts are a new layer beneath the
  existing repository-composite asset patterns).
</content>
