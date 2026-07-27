# LawFirm OS — Master Architecture Packet

Author: Fable (boss/architect), effort MAX. Date: 2026-07-09. Version: 1.0.
Inputs: Opus 4.8 architecture intake brief (authoritative on current state); LawFirm OS repo
family source docs; DAD structural pattern (pattern only).
Status: **complete as architecture; execution gated on D17; D18/D19/D20 open (fail-closed
placeholders in force).** No code was written. All cross-repo work exists as specs.

---

## 1. Master architecture

### 1.1 Repo & authority map

| Unit | Plane | Owns | Must not own | Consumed how |
|---|---|---|---|---|
| `LawFirm-os-semantic-substrate` | Control | Canonical schemas, registries, route/event IDs, lifecycle + promotion policy, AI front door | Runtime execution, raw legal payloads, real facts | Read-only; pinned by SHA |
| `LawFirm-os-orchestrator` | Execution | Policy-gated orchestration, evidence-packet prep, gates, pause/resume | Canon, route/event minting, promotion | Pins substrate |
| `LawFirm-os-exceptions-lake-runtime` | Evidence | Append-only runtime records, deny-by-default admission | Canon mutation, raw payloads, promotion | Pins substrate |
| `LawFirm-os-legal-knowledge-runtime` | Legal knowledge | Ingestion preflight, SourceRef/PassageRef/ClaimRef, context bundles | Workflow authority, legal conclusions | Pins substrate |
| `LawFirm-os-skills-registry` | Skill supply chain | Draft/candidate skills, scans, evals, trust records | Promotion authority, runtime evidence | Pins substrate |
| `LawFirm-os-intake` **(B only)** | Vertical (`authority_plane: none`) | Intake→budget vertical, fixtures, evals, candidate schemas, learning loop | Canon of any kind | Pins all five |
| **DAD** (this repo) | **Orchestration home (operational, non-authority)** | Build coordination: portfolio, board, leases, specs, decisions | Any LawFirm OS canon; any target repo's boundary | Drives via specs; writes cross-repo only per D17 |
| ALS (`Albert-Trial-Simulation-System`, now local under `00_LawFirm_OS/`) | External simulator | Its own product | Any LawFirm OS role | Adapter-only behind `LITIGATION_SIMULATION_ADAPTER_BOUNDARY.md`; private catalog excluded |
| `billing-guideline-simulator` | Candidate app | Portfolio-level stochastic what-if | Canon; billing system of record | Candidate input/output only |
| `orphan_radar` | External library | KG hygiene engine | Any LawFirm OS role | Reusable skill candidate (Inform) |
| AIRCA | Doctrine | Decision-governance framing | — | North star; substrate is declared AIRCA-aligned |

Conflict resolution order is unchanged: substrate `source-of-truth.json` → `design-authority.json`
→ `CROSS_REPO_MAP.md` → boundary docs → child `AGENTS.md` → vendor adapters (consumers, never
authorities — **including this orchestration home**).

### 1.2 AIRCA legibility map

| AIRCA layer | LawFirm OS realization |
|---|---|
| **Architect** | Substrate (schemas, registries, authority contexts, validation doctrine) |
| **Inform** | Legal Knowledge Runtime (source/passage/claim refs, context bundles); orphan_radar-class retrieval/graph capabilities; DAD asset cards (discoverability) |
| **Rank** | Candidate scorecards, eval reports, learning-promotion-readiness checks, billing-sim sensitivity outputs — all `model_proposal`/`deterministic_inference` class, never authority |
| **Commit** | Human gates only: intake confirmation, reviewed-learning-gate, budget review, D-series decisions, promotion decisions |
| **Act** | Orchestrator execution under authority passports; build agents under the same passports |

Design rule: every new artifact must be placeable in exactly one AIRCA layer; an artifact that
claims Rank output as Commit authority is the laundering pattern Kernel K2 blocks.

### 1.3 Workflow map (what runs)

1. **Intake→budget vertical** (exists, in B): source bundle → custody gate → segmentation →
   candidates → human confirmation → conflict seed (no conclusion) → deterministic budget
   proposal → carrier-compliant projection (two numbers, `rewrites_budget=False`) →
   `blocked_pending_conflicts_and_engagement`.
2. **Carrier learning loop** (exists, in B): rejection/appeal/actual variance → learning
   proposal/report → proposed-change-set (+ red-team notes) → shadow evals → reviewed gate →
   owner handoff → (dry-run Lake candidates; promotion package).
3. **Asset-use loop** (new, P1): every stage above emits an asset-use record against the asset
   registry; pay-forward improvements become candidate learning, never silent mutation.
4. **Build-agent workflow** (new, P2): spec → claim → branch/PR in target repo → independent
   checker executes → verdict → merge-train → provenance appended (this is the same
   evidence/authority machinery applied to the builders themselves).
5. **Engine consolidation** (new, P3): characterize → extract harness → extract MC kernel →
   equivalence-gated deletion of the copy.

### 1.4 Data-flow map

```text
synthetic source bundle
  -> intake custody gate -> segments+hashes -> candidates (evidence_class: model_proposal)
  -> human confirmation (class: human_confirmation)
  -> conflict seed candidate | budget proposal (deterministic_inference; proposal-only)
  -> carrier projection (two numbers) -> rejection/appeal/variance capture (source_fact via RejectionSourceRef)
  -> learning packets (candidate_learning) -> reviewed gate (human) -> owner handoff
  -> Exception Lake DRY-RUN candidates (not_authorized_for_lake_write=true)
  -> promotion package -> owning repo PR -> human promotion (promoted_canon, substrate only)
Build plane (parallel): spec -> worker PR -> checker execution -> verdict -> merge train
  -> provenance/lineage appended -> agent-action records (Lake dry-run candidates)
```

No arrow authorizes real data, external writes, conflict clearance, matter opening, budget or
appeal submission, profile mutation, or canon change.

### 1.5 Learning-flow map

The existing B loop is the spine; P1 adds only what is missing:

```text
observed evidence (source_fact)
  -> proposal (model_proposal) -> deterministic checks (deterministic_inference)
  -> human confirmation -> candidate learning packet
       + NEW: isolation declaration {matter_isolation, aggregation_level,
              small_cell_status(k), dominance_status, reuse_scope}   [K1]
  -> shadow eval -> reviewed-learning-gate (human; named approver/version/effective date) [K5]
  -> promotion-readiness check (FAILS CLOSED if isolation undeclared)
  -> owner handoff -> owning repo promotion
```

Learning never mutates profiles, rates, guidelines, templates, gates, or canon in place —
already type-locked in B (`mutates_profile_or_template: false`); K1/K2 add the cross-matter and
class-escalation guards that are genuinely missing.

### 1.6 Promotion-flow map

```text
candidate (any repo) -> reviewed gate (human) -> owner handoff package
  -> PR in OWNING repo (substrate for schemas/policy; orchestrator for runtime;
     lake for record formats; skills-registry for skills; LKR for source adapters)
  -> owning repo validators + human approval -> promoted
  -> consumers adopt by explicit pin refresh (never floating)
```

Single-writer rule: at most one program holds the substrate canon lease at a time (P6);
the integrator (Fable) holds it, no one else.

---

## 2. Engine consolidation plan (M4)

### 2.1 Share matrix

| Concern | ALS | billing-sim | intake budget | orphan_radar |
|---|---|---|---|---|
| Core method | Monte Carlo | Monte Carlo (copied from ALS) | deterministic driver math | graph + TF-IDF |
| HARNESS (seeds, run manifest, run record, label-free eval/calibration, red-team fixtures, score-language guard, human-adoption gate, no-write, provenance) | ✓ | ✓ | ✓ | ✓ |
| MONTE CARLO kernel | ✓ (origin) | ✓ (copy — the real duplication) | ✗ | ✗ |
| Graph kernel | ✗ | ✗ | ✗ | ✓ |

Only two shared units exist. Anything more is over-DRY and forbidden (E4).

### 2.2 Target shape

- **Contracts → Substrate** (canonical after promotion): `simulation-run-manifest`,
  `simulation-run-record`, `simulation-eval-report`, `score-language-policy`. Named
  `simulation-*` deliberately — "evidence packet" is already an orchestrator/lake term and must
  not be overloaded.
- **Executable library → `lawfirm-os-sim-harness`** (home = D18; recommendation: new repo,
  `authority_plane: none`, registered in the substrate repo registry): packages `harness/`
  (all four engines depend) and `montecarlo/` (ALS + billing-sim only). Consumed by pinned SHA.
- **Each engine = thin domain adapter.** Intake keeps its deterministic kernel; orphan_radar
  keeps its graph kernel; ALS keeps its trial domain; billing-sim keeps its finance domain and
  **deletes its MC copy** once equivalence is proven.

### 2.3 intake-budget vs billing-sim — resolved

- **Intake owns the governed, matter-scoped budget PROPOSAL**: deterministic, source-bound,
  human-gated, `rewrites_budget=False`, proposal-only. This is the Commit-adjacent path.
- **billing-sim owns portfolio-level stochastic WHAT-IF** (guideline changes → cash flow,
  realization, write-offs): Rank/Inform-layer decision support only.
- Data flows one way: intake proposals may be billing-sim INPUT fixtures (synthetic only);
  billing-sim outputs never write back into intake artifacts; they may spawn
  `candidate_learning` packets routed through the reviewed gate like any other lesson.
- Shared surface = schemas only (budget line, UTBMS/scenario contracts) promoted through
  Substrate. Neither imports the other's engine code. Both adopt `harness/`.

### 2.4 Migration order (safe) and equivalence gates

1. **Characterization tests first** (T-0009..T-0012): capture each engine's CURRENT outputs.
   Deterministic engines: byte-identical goldens. MC engines: pinned seed + pinned RNG →
   byte-identical output streams (fall back to distributional tests ONLY if an RNG
   implementation change is separately approved; none is planned).
2. Contracts drafted as candidates (harness home), submitted to Substrate via promotion package.
3. Extract `harness/`; refactor all four behind interfaces; characterization stays green.
4. Extract `montecarlo/`; point ALS at it; point billing-sim at it; **delete billing-sim's copy
   only after its equivalence test passes against the shared kernel.**
5. Intake and orphan_radar math untouched (harness adoption only).
6. Pins + promotion through normal gates.

### 2.5 Guard rails

- Nothing duplicated is deleted before an equivalence test proves the shared version matches.
- ALS's private catalog (`AI_DIGITAL_ASSET_CATALOG.md`, `.digital-asset/`) never crosses into
  any LawFirm OS repo — the outbound denylist (O4) covers ALS-private tokens as well as
  DAD-private ones. Only the kernel pattern is extracted.
- P3 is a HARD-CODER program (GPT-5.5) with mandatory characterization coverage before any
  extraction PR is specced.

---

## 3. Minimum DAD-style digital asset layer (M1)

### 3.1 Candidate asset-card schema (`lawfirm-digital-asset-card.schema.json`, in B)

`additionalProperties: false`. Fields:

| Field | Type/lock | Note |
|---|---|---|
| `asset_id` | string, `^asset\.[a-z0-9-]+\.[a-z0-9-]+$` | e.g. `asset.intake.conflict-seed-boundary-check` |
| `schema_version` | const "0.1" | |
| `purpose` | string ≤ 300 chars | public-safe wording only |
| `workflow_surface` | string | which workflow stage it serves |
| `capability_refs` | array of repo-relative paths | must resolve inside `owner_repo`; validator checks existence |
| `data_class` | enum {`synthetic_fixture`,`metadata_only`} | nothing else admissible |
| `authority_level` | enum {`candidate`,`fixture`,`reference`} | `promoted_canon` is UNREPRESENTABLE here by design |
| `evidence_class` | enum per K2 lattice, ≤ `candidate_learning` | type-locked ceiling |
| `owner_repo` | enum of registered repo names | |
| `promotion_target` | enum of the five platform repos | |
| `blocked_uses` | array, minItems 1 | e.g. "conflict clearance", "budget submission" |
| `synthetic_fixture_refs` / `validation_refs` | arrays of paths | validator checks existence |
| `candidate_only` | const true | |
| `provenance` | object (per §5.3) | required |

### 3.2 Registry shape (`registry/lawfirm-os-digital-assets.candidate.json`, in B)

`{ registry_id: "lawfirm-os-digital-assets.candidate.v0_1", canonical: false,
status: "candidate", assets: [cards...] }` — mirrors the fail-closed style of the substrate
repo registry: the validator rejects unknown fields, unregistered owner repos, and any card
failing §3.4.

### 3.3 Initial seven assets — facades over capabilities that ALREADY exist in B

1. `asset.intake.source-custody-segmentation-gate` → `provenance.py`, `segmenter.py`
2. `asset.intake.conflict-seed-boundary-check` → `conflict-seed-packet.schema.json` + `workflow/prohibited-transitions.yaml`
3. `asset.intake.budget-driver-preflight-matrix` → `budget_driver_qa.py`, `budget-driver-*` schemas
4. `asset.intake.carrier-rejection-learning-loop` → `carrier_rejection_learning.py` + proposal/report schemas
5. `asset.intake.human-review-packet-template` → `review.py`, `human-review-packet.schema.json`
6. `asset.intake.reviewed-learning-gate` → `reviewed_learning_gate.py`, `learning-promotion-readiness-*`
7. `asset.intake.dad-mailbox-safety-audit` → `dad_mailbox_safety.py` (offline; no hub contact)

No card creates new capability; cards make existing capability discoverable and governable.

### 3.4 Forbidden fields & disclosure rules (validator denylist — fail closed)

Forbidden anywhere in a card or registry: `private_path`, `dad_hub_id`, `asset_score`,
`asset_rank`, `value_score`, `dependency_graph`, `owner_notes`, `strategy`, any lineage
outside registered public repos; any string matching DAD/ALS-private patterns
(`04_Digital_Assett_Directory`, `AI_DIGITAL_ASSET_CATALOG`, `dad://hub`, ALS `.digital-asset/`
paths). Disclosure rule: cards are **derivative capability cards** — describe what LawFirm OS
can do, never what the private catalogs contain. Absence is not enough; the denylist is
checked affirmatively on every validation run.

---

## 4. Hard kernels (only the genuinely hard)

**K1 — Cross-matter learning non-interference.** *Hard because* the leak is statistical, not
textual, and passes ordinary synthetic tests. *Solution:* every learning packet carries a
mandatory `isolation declaration` (`matter_isolation`, `aggregation_level`,
`small_cell_status{declared_k|null,status}`, `dominance_status{rule_ref|null,status}`,
`reuse_scope`, `blocked_reason`); the promotion-readiness check **fails closed when any field is
undeclared** — the system never invents K or a dominance rule (D16 discipline). *Owner:* intake
(candidate, T-0005) → substrate (promoted rule) → orchestrator (runtime enforcement) → lake
(evidence). *Acceptance:* a fixture packet with `declared_k: null` must be `blocked_undeclared`
and fail promotion readiness; a declared packet passes. *Not yet:* real-data aggregation,
automatic thresholds, production learning memory.

**K2 — Evidence-class lattice (authority-laundering prevention).** *Hard because* defenses today
are ~dozens of ad-hoc booleans across 420 schemas; unifying without breaking them is the trick.
*Solution:* one enum `{source_fact < model_proposal ≈ deterministic_inference <
human_confirmation < candidate_learning-with-review < promoted_canon}` + **envelope adoption**:
new artifacts carry `evidence_class` mandatorily; existing artifacts map via a shipped
compat table (`config/evidence-class-compat-map.json`: e.g. `candidate_only:true` ⇒ ceiling
`candidate_learning`); the validator enforces at **packet boundaries** (the assembly points that
already exist), rule: `class(output) ≤ min(class(inputs))` unless the step is a registered human
gate. Only substrate promotion mints `promoted_canon`. *Owner:* intake candidate (T-0004) →
substrate canonical definitions → orchestrator runtime transitions → skills-registry output
labels. *Acceptance:* validator rejects a fixture where a `model_proposal` is consumed as
`promoted_canon`; compat map covers every existing packet schema in B (coverage test).
*Not yet:* rewriting existing schemas; automatic class promotion of any kind.

**K3 — Authority passport (tool chains AND build agents — one mechanism).** *Hard because*
authority is transitive: two individually-safe hops compose into an unsafe action several hops
after the decision. *Solution:* one schema `authority-passport.schema.json` with
`subject_type ∈ {run, tool_chain, build_agent}`, fields: `permitted_data_classes`,
`permitted_write_targets` (repo + path globs), `permitted_external_actions` (const `[]` in this
phase), `authority_ceiling` (an evidence class), `human_gates[]`,
`no_transitive_authority: const true`, `chain[]` where every hop appends
`{holder, consumed, returned}` and returned ⊆ consumed (monotone non-increasing). The build
team's provenance block embeds the same passport — the checker verifies the diff touched only
`permitted_write_targets`. This single mechanism serves P1 (workflow) and P2 (builders).
*Owner:* substrate schema; orchestrator enforcement; intake dry-run fields (T-0006);
skills-registry capability declarations. *Acceptance:* fixture chain where a child returns MORE
authority than consumed must fail; test proving `permitted_external_actions == []` end-to-end.
*Not yet:* live connector chains; automatic grant escalation.

**K4 — Append-only evidence with retroactive screens.** *Hard because* deletion breaks audit,
visibility breaks privilege, and screens arrive after the fact. *Solution:* immutable identity +
append-only overlays (`quarantine`, `redaction`, `access-policy`, `supersession`, reviewer
rationale); projections are views, never mutations. B already has append-only + supersession
primitives; only the overlay layer is new. *Owner:* lake (overlays/projection), substrate
(overlay semantics), orchestrator (access checks), intake (dry-run modeling only,
`not_authorized_for_lake_write=true`). *Acceptance:* dry-run package showing an overlay applied
over an existing candidate without altering its hash/identity. *Not yet:* deletion; any intake
Lake write.

**K5 — Carrier learning promotion gate.** *Hard because* rejection feedback is operationally
valuable and tempting to auto-apply, and may be wrong/strategic/carrier-specific. *Solution:*
extend B's existing reviewed-learning-gate: any profile/rate/guideline/template implication
requires `{named_approver, version, effective_date, supersession_ref}` before promotion;
candidates stay type-locked `mutates_profile_or_template: Literal[False]`. *Owner:* intake gate
extension; substrate promoted rule; orchestrator approval workflow. *Acceptance:* gate fixture
missing an approver fails closed. *Not yet:* real carrier profiles, negotiated rates, appeal
submission.

**K6 — Replay across model/provider deprecation.** *Hard because* exact replay is impossible and
re-running a changed model creates false confidence. *Solution:* replay = **equivalence testing
against declared criteria** (never hidden-state reproduction); persist prompt hashes, adapter
version, model class, deterministic post-processing, human decisions, output evidence class. B's
`benchmark-replay-*` is the base; add an equivalence-criteria declaration. No chain-of-thought
storage, ever. *Owner:* intake fixtures; orchestrator run ledger; skills-registry prompt/model
metadata; substrate policy. *Acceptance:* a candidate reviewed WITHOUT the original model call,
using only the persisted packet. *Not yet:* production model dependency.

**K7 — Public-structure→synthetic without reconstruction.** *Hard because* structure leaks
origin when too many fields survive; synthetic fixtures decay into lightly-redacted real
records. *Solution:* conversion manifests (never payloads) + non-reconstruction checks: no real
party names, no unique date/location/case tuples, no copied source text, mandatory synthetic
origin declaration. B's `public-data-cache-audit-*` is the base. *Owner:* intake specs; LKR
source handling; substrate policy if promoted. *Acceptance:* conversion-spec fixture passes;
a fixture violating the tuple rule fails. *Not yet:* committed public payload corpus.

Excluded from kernels: asset-card CRUD, docs, TOC edits, fixture plumbing — routine, cheap-tier.

---

## 5. Multi-agent build & verification architecture (M2)

### 5.1 Org chart & routing (efforts assigned)

| Role | Model | Effort | Gets | Never |
|---|---|---|---|---|
| Boss / architect / integrator | Claude Fable | HIGH; MAX for packet/kernels/disputes | Specs, partition, rulings, merge train, canon lease | Production code; self-approval |
| Hard coder | GPT-5.5 | high | K1–K7 artifacts, refactors, MC characterization, escalations | Canon writes without integrator lease |
| Cheap coder | Composer 2.5 | low | File-scoped PRs from specs (docs ports, schemas, fixtures, tests) | Inferring authority; editing outside `paths` |
| Cheap coder (foreign) | GLM 5.2 | low | Same as Composer | Merging without backdoor scan; checking own family's work |
| Checker | any model ≠ worker | medium | Executes the work; verdicts | Trusting self-reports; "recalling" canonical values |

Pairing matrix: see `decisions/D20`. Auditions (T7): Composer and GLM each pass a tryout
(T-0008) with an auto-scored acceptance check before their first real task.

### 5.2 Checker protocol (T1–T4, operational)

Checker MUST: run the task's validation commands itself; re-derive every canonical value from
substrate registries (`source-of-truth.json` etc.), never memory; diff-audit that only spec
`paths` changed; verify the DoD constitution clause by clause; emit the verdict format (§8).
Checker MUST NOT: read the worker's report as evidence; approve on "looks right". Disputes go to
the boss and may be ruled FOR the worker; rulings are recorded on the board (`ruling` event).

### 5.3 Provenance + lineage schema (append-only)

Canonical block (embedded in PR descriptions and artifact headers; JSON in
`DEFINITION_OF_DONE.md` §7): `authoring_agent`, `model`, `task_id`, `spec_ref`, `prompt_hash`,
`checker`, `checker_verdict`, `source_of_truth_refs[]`, `evidence_class`,
`originated_from: "DAD-orchestration"`, `ts`, `lineage[]` (every subsequent touch appends
`{agent, model, ts, task_id, what}`). Erasing or rewriting lineage is a red-flag escalation.
This block IS an authority passport binding (`subject_type: build_agent`, K3).

### 5.4 Backdoor gate (T6)

Applies to all foreign/opaque-model output before merge: scan for hidden network/exfil calls,
obfuscated payloads (hex/base64 blobs, homoglyphs), unpinned or typosquatted dependencies,
eval/exec of remote or constructed content, silent permission/scope expansion, and writes
outside `permitted_write_targets`. Owner: Skills Registry (the scan is itself a candidate
skill, T-0007); enforcement point: the merge train (integrator refuses un-scanned GLM PRs).

### 5.5 Placement (who owns what)

Provenance schema + checker protocol + model-trust tiers + DoD = **Substrate** (candidate
policy, promoted later). Runner + checker execution + escalation + merge gate = **Orchestrator**.
Supply-chain scan + auditions + capability declarations = **Skills Registry**. Append-only
agent-action/verdict/lineage records = **Exception Lake** (dry-run candidates from intake).
Candidate fixtures/tests = **Intake (B)**. Until those PRs land, the operational copies live in
this home (`COORDINATION_PROTOCOL.md`, `DEFINITION_OF_DONE.md`) — explicitly marked candidate.

---

## 6. Parallel / multi-program coordination (M3)

Operational detail in `COORDINATION_PROTOCOL.md`, `HOT_FILES.json`, `PORTFOLIO.md`. Design:

- **P1–P6 rules** as specified: program layer; file-set parallelism / repo hot-file
  serialization; leases; generated-over-hand-maintained; one merge train per repo with the
  integrator (Fable) owning it; canon single-writer.
- **Known collision surface:** P1 and P2 both touch intake B hot files
  (`scripts/validate_repo.py`, `AI_TABLE_OF_CONTENTS.md`). Resolved by dependency-ordering the
  early tasks (T-0001→T-0002→T-0004) rather than concurrent leases — cheaper than lease churn
  at this scale.
- **OneDrive hazard (accepted risk, mitigated):** this workspace syncs via OneDrive; concurrent
  writes can fork conflicted copies. Mitigations: day-one `dispatch_mode=human_manual`
  serializes; board appends use read-tail-then-append with temp+rename; leases carry
  `lease_until` so stale locks expire; once D17 records `agent_auto`, move board/mail updates to
  commit-per-append on a git branch.

---

## 7. PR roadmap (summary — detail in `programs/*/ROADMAP.md`, specs in `specs/`)

| # | Task | Program | Target repo | Tier | Depends |
|---|---|---|---|---|---|
| PR#0 | T-0001 port DAD-layer docs A→B **with correction headers** | P1 | intake B | cheap | — |
| PR#1 | T-0002 asset-card schema + registry + 7 cards + denylist validator + golden fixture | P1 | intake B | cheap | T-0001 |
| PR#2 | T-0003 asset-use/pay-forward record + additive emitter | P1 | intake B | cheap | T-0002 |
| PR#3 | T-0004 evidence-class lattice + compat map + boundary validator | P1 | intake B | **hard** | T-0002 |
| PR#4 | T-0005 isolation declaration + fail-closed readiness gate (K1) | P1 | intake B | **hard** | T-0004 |
| PR#5 | T-0006 authority passport schema + dry-run binding (K3) | P1 | intake B | **hard** | T-0004 |
| — | T-0007 backdoor-scan candidate skill card | P2 | skills-registry | cheap | — |
| — | T-0008 model auditions (Composer, GLM) | P2 | DAD home | boss-authored | — |
| — | T-0009..T-0012 characterization tests (billing-sim, intake, orphan_radar, ALS) | P3 | each engine repo | mixed | — |
| — | T-0013 create `lawfirm-os-sim-harness` | P3 | new repo | hard | **D18** |

Every PR: one repo, no mixed concerns, cheap-authored unless flagged hard, independent checker +
DoD gate, provenance block mandatory. All cross-repo execution is `human_manual` dispatch until
D17 records otherwise.

---

## 8. Coder build packet (exact formats)

Spec template, worker report format, and checker verdict format are canonical in
`COORDINATION_PROTOCOL.md` §5–§7; every spec in `specs/` references them. Invariant style:
prefer type-locks (`Literal[False]`, `const` enums, `additionalProperties:false`) over runtime
asserts. Stop conditions (verbatim in every spec): real/privileged data appears; a canonical
value can't be confirmed against substrate registries; the spec requires touching a path outside
`paths`; a validator must be weakened to pass; any external write would occur; prompt/manifest
authority expands. On stop: append `blocked` to the board, mail the program thread, halt.

---

## 9. Open decisions

| ID | Question | Owner | Blocking | Placeholder (in force) | Risk if guessed |
|---|---|---|---|---|---|
| **D17** | DAD cross-repo write scope | Lowell | all cross-repo task execution | `human_manual` dispatch; DAD writes home+mail only | authority inversion; contract breach |
| **D18** | Harness home (new repo vs skills-registry) | Lowell | P3 extraction PRs | characterization proceeds; no shared code | role-mixing or registry validation failure |
| **D19** | Stale copy A archival (rename blocked by file lock) | Lowell | none (marker in place) | all specs name B only | agents edit the dead tree |
| **D20** | Checker fleet + pairing matrix | Lowell | checker assignments | GPT-5.5 default checker; Claude checks GPT-5.5 | rubber-stamp pairings |
| carried | D8/D16 reviewer role + thresholds; K1 parameters (K, adversary, dominance); substrate event-label promotion; MCP-first canon location | Lowell + counsel | K1 promotion; event registration | fail-closed (`blocked_undeclared`) | AI-invented thresholds become de-facto policy |

---

## 10. Validation strategy

- **Intake B locals** (every intake PR): `python scripts/validate_repo.py` ·
  `python scripts/export_schemas.py` · `python -m pytest` · `ruff check` + `ruff format --check`
  · `bash scripts/smoke_demo.sh` (must end `blocked_pending_conflicts_and_engagement`).
- **Cross-repo front door** (workspace root): substrate `validate_ai_front_door.py` and
  `validate_skill_agent_control_plane.py --workspace .`
- **New candidate-layer gates** (added by P1): digital-asset denylist validator;
  evidence-class boundary validator + compat-map coverage test; isolation-declaration
  fail-closed test; passport monotonicity test; `permitted_external_actions == []` test.
- **No-real-data / no-external-write:** existing intake gates + spec stop conditions + checker
  diff audit.
- **Build-plane gates:** provenance-present check; backdoor scan on foreign output; checker
  verdict recorded before merge; merge-train ordering.
- **P3 gates:** characterization goldens green before extraction; equivalence test green before
  any duplicate deletion.

---

## 11. Red-team findings → fixes applied

1. *Ported plan docs carry a stale diagnosis (authored against copy A).* → T-0001 requires a
   CORRECTION header on every ported doc stating G1/G2 facts.
2. *This home is itself ungoverned mutable state.* → board is append-only with schema;
   protocol/policy files are integrator-edit-only; decisions are files, not chat.
3. *Checker collusion (same family).* → D20 pairing matrix; GLM never checks GLM; model ids
   recorded in provenance.
4. *OneDrive concurrent-write forks.* → §6 mitigations; human_manual day one.
5. *Board could be edited to erase history.* → append-only rule + genesis event + (post-D17)
   commit-per-append; lineage erasure = red-flag escalation.
6. *Specs drift if B's active branch moves under Codex.* → every spec pins `base_branch` and
   records base SHA at claim time; checker validates against the pinned base.
7. *"Evidence packet" name collision with orchestrator term.* → engine contracts renamed
   `simulation-*`.
8. *Two early tasks contend for the same B hot files.* → serialized via `depends_on` instead of
   parallel leases.
9. *ALS private catalog newly inside the workspace tree.* → O4 denylist extended to ALS tokens;
   ALS remains adapter-only behind the litigation-sim boundary.
10. *A future Fable session could re-trust copy A.* → D19 record + START_HERE step-4 prohibition
    + memory note.

## 12. Premortem (standing answers)

Governance weakens **if** DAD starts owning canon → O1/O3 + single-writer canon lease prevent.
Child repos drift **if** pins float → O7 + pin-refresh-only-by-review. Client-data boundaries
blur **if** real data enters fixtures → data-class gates + stop conditions + checker audit.
AI rules become authority **if** class escalation goes unchecked → K2 validator. Local
convenience overrides governance **if** the home's copies of policy diverge from substrate →
placement plan (§5.5) promotes them; home copies marked candidate. CI passes with incomplete
discovery **if** governance-facing files skip the map → DoD §10. A cheating/hostile agent
survives **if** checkers rubber-stamp → T1/T2 + D20 matrix + backdoor gate. Provenance forged
**if** blocks are hand-written → checker recomputes prompt_hash and diff-audits; forgery =
red-flag. Parallel programs corrupt a repo **if** leases are skipped → board refuses
overlapping claims; merge train serializes. Engine extraction changes behavior **if** deletion
precedes proof → equivalence gate is a hard precondition.

## 13. Completion status

Maps (§1), engine plan (§2), asset layer (§3), kernels (§4), build architecture (§5),
coordination (§6), roadmap (§7), build packet (§8), decisions (§9), validation (§10) are
mutually consistent — verified against red-team items 1–10 above. **Architecture: COMPLETE.**
Execution: blocked on D17 (by design); D18 blocks only P3 extraction; D19/D20 have safe
placeholders. First human actions: resolve D17; answer D18; dispatch T-0001.
