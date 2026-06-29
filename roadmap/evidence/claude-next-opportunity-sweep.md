# Claude Next Opportunity Sweep

Reviewer: Claude Code (claude-opus-4-8), fresh-eyes opportunity sweep
Date: 2026-06-29
Repo state: branch `codex/algorithm-calibration-fixes`, working tree clean.
Latest commit at sweep time: `64663c9 Harden roadmap gates and external research`
(landed after my post-merge red-team; PR #1 merged at `cdb7dd2`).
Scope: read-only except this report. No scans, no GitHub, no embeddings/alerts/
scheduled jobs, no source mutation. All scores/edges/proposals/radar outputs treated
as generated candidate evidence.

---

## Executive verdict

**The premise "Phase 0–5 is complete" is no longer true, and that is good news.**
The hardening commit added a human-reviewer check to the roadmap gate logic
(`roadmap.py:_has_human_reviewer`) and an `--enable-external` gate to missing-part
research — both directly addressing my prior red-team. As an honest side effect, the
checker now **re-opens the phases that had leaned on agent-attested gates**:

| Phase | Declared | Computed (now) | Why |
|---|---|---|---|
| phase-0-seed | complete | **complete** | file-based |
| phase-1-first-inventory | planned | **awaiting_human_gate** | `phase-1-source-mutation-check-passed` reviewer=codex |
| phase-1.5-scoring-discipline | planned | **complete** | gates reviewer=Lowell |
| phase-2-calibration | planned | **complete** | gates reviewer=Lowell |
| phase-2.5-content-aware | complete | **complete** | file/output-based |
| phase-3-downstream-governance | planned | **awaiting_human_gate** | 3 gates reviewer=codex |
| phase-4-semantic-enrichment | boundary_deferred | **awaiting_human_gate** | gates status=`boundary_deferred`≠`verified` |
| phase-5-alerting-and-research | boundary_deferred | **awaiting_human_gate** | gates status=`boundary_deferred`≠`verified` |

So the real baseline is: **phases 0, 1.5, 2, 2.5 are genuinely complete; phases 1, 3,
4, 5 are open.** The single most valuable next move is *not* to build a new system —
it is to honestly reconcile the roadmap so it stops claiming, and stops being able to
re-claim, work that no human verified. Only after that should new asset-building start.

The strongest *new* build candidate is `WorkflowPartRecord` (fully designed, reserved,
deterministic, candidate-only). The most urgent *calibration* gap is that the
background radar currently surfaces **nothing** on the real catalog (0 escalation
packets out of 10,000 candidates) and the value-score calibration sample never touched
a high-value or document/media asset.

---

## Top 10 next opportunities, ranked

### 1. Reconcile the re-opened roadmap (phases 1 & 3) honestly
The hardened checker correctly fails `phase-1-source-mutation-check-passed`,
`phase-3-pre-push-enforcement-reviewed`, `phase-3-lessons-arrive-central-hub`, and
`phase-3-bypass-failure-tested` because all four carry `reviewer: "codex"`. Either a
human actually reviews each and re-records the gate (reviewer=Lowell or
`human_verified: true`), **or** these phases are re-stated as not-complete and the
roadmap stops implying otherwise.

### 2. Make `boundary_deferred` a truthful resting state (it is currently half-wired)
`roadmap.yaml` declares phases 4/5 as `boundary_deferred` and the checker has a
`boundary_deferred` computed branch — but that branch (`roadmap.py:174`) sits *after*
the `unverified_gates → awaiting_human_gate` branch (`roadmap.py:170`). Because the
phase-4/5 gates are themselves marked `status: "boundary_deferred"` (not `"verified"`),
they count as unverified, so the phases compute `awaiting_human_gate` and the
`boundary_deferred` resting state is **unreachable**. Decide and implement how a phase
with intentionally-deferred gates should rest.

### 3. Reconcile `roadmap.yaml` declared statuses with computed reality
Phases 1.5 and 2 are declared `planned` but compute `complete`; the new
`status_warnings` field now surfaces this on every run. Flip the declared statuses (or
adopt the warnings as the contract). Cheap, removes standing drift.

### 4. `WorkflowPartRecord` — Phase A (schema + ~5 edges + `part_type` registry)
The single biggest genuinely-new asset layer. Fully designed in
`claude-workflow-composition-red-team.md` and reserved in
`docs/BACKGROUND_CONNECTION_RADAR.md`. Confirmed: the 5 proposed edges
(`produces_input_for`, `substitutes_for`, `specializes`, `generalizes`, `quarantines`)
are genuinely **absent** from `registry/edge-type-registry.json` (53 existing types,
no near-duplicates of these). Build only after the 5 open human decisions (§Open
decisions in that file) are answered.

### 5. Background-radar calibration harness (the radar fires nothing today)
Per `background-connection-radar-v1-implementation.md`: 10,000 candidates → evidence
gate failed **9,979**, safety failed 1,785, **0 escalation packets** at `tau=0.70`.
The radar surfaces no connections on the real catalog. Build a labeled
recall/precision harness (use DAD's own known asset families as positives) to learn
where the evidence gate and `tau` should sit — **without lowering gates to force
output**, which the v1 evidence explicitly warns against.

### 6. Calibration breadth batch (document / dataset / media / model / high-value)
`calibration-review-summary`: 100/100 reviewed, but instance classes are only
`source: 91` / `archive: 9`, value bands only `medium: 50` / `low: 50` — **zero
high-value-band assets were ever reviewed**, and content profiling barely covers
document/dataset/media (Phase 2.5 JSON: `document` 1/38,314 profiled). Score trust
outside the code/schema/test surface is unproven. A second labeled batch is the
prerequisite for any scoring-dependent feature.

### 7. Validate the 27 asset-patterns (recognized ≠ validated)
`registry/asset-pattern-registry.json` lists 27 very-high-leverage patterns, but nearly
every one's `missing_evidence` is "human labels / reviewed examples / precision-recall."
They are recognized, never validated. Pick the 3–4 highest-leverage (AI work-cycle
governance, evaluation/contract, source-faithful chunking gate, security
scanner/quarantine — same shortlist the WorkflowPart red-team recommends) and produce
reviewed positive/negative examples.

### 8. AI-TOC row-shape validator + wire in new evidence files
The `ai_entrypoint_toc_routing_system` pattern itself names "validator that checks AI
TOC row shape" as missing evidence. A cheap deterministic linter (path | what-it-is |
tags | use-when present; tags in the tag index; referenced path exists) is a
high-leverage governance asset and dogfoods DAD's own standard. Also: the new
`claude-post-merge-roadmap-red-team.md` and this sweep are not yet in
`AI_TABLE_OF_CONTENTS.md`, and `boundary_deferred` is undocumented in
`docs/ROADMAP_EXECUTION.md`.

### 9. Public-release scrub epic + public/private split decision
`config/sources.example.yaml` carries a real owner handle (`lowelltwong-alt`) and a
personal absolute path; `roadmap/gate-evidence.json` and several evidence files embed
`C:\Users\lowel\...` paths, a temp sandbox path, real session/handoff/lesson IDs, and
names private repo families (Mock Trial, LawFirm OS, Logos). None are secrets, but all
are public-release blockers. Needs a human decision on the public/private split before
any publish, and a scrub checklist.

### 10. Deferred-systems decision doc (plan, not implementation)
Embeddings / `semantically_similar_to` edge (reserved-deferred in the edge registry),
the Tier-2 strong-model radar verifier, scheduled scans, and alert channels each need a
single provider/privacy/retention decision document so the next agent has named gates
instead of re-deriving them. This is a *planning* artifact; it enables nothing.

---

## Why each matters (one line each)

1. The roadmap currently can be read as "done" when 4 of 6 working phases aren't human-verified — the core trust contract.
2. Without a real resting state, deferred phases nag as `awaiting_human_gate` forever and invite a dishonest "fix."
3. Standing declared/computed drift erodes confidence in every status read.
4. Recombinable workflow parts are the next abstraction layer above the existing 27 whole-workflow patterns; nothing else unlocks assembly.
5. A discovery system that surfaces nothing is either mis-tuned or proving the graph is too sparse — either way you can't tell without a harness.
6. Scores are only validated on code/schema/test; trusting them on documents/media is unproven and the calibration set has no high-value examples.
7. 27 patterns guide scoring and proposals but none are precision/recall-validated.
8. DAD preaches a navigation standard it does not yet enforce on itself.
9. A single publish would leak local paths, an owner handle, and private repo names.
10. The deferred systems will be revisited; a named-gate plan prevents ad-hoc enabling.

---

## Evidence / repo surfaces supporting each

- **1, 2, 3:** `roadmap.py:75-110,166-196`; `roadmap/roadmap.yaml:3-10`;
  `roadmap/gate-evidence.json` (phase-1/3/4/5 reviewer fields); live `roadmap check`
  output (table above).
- **4:** `roadmap/evidence/claude-workflow-composition-red-team.md`;
  `docs/BACKGROUND_CONNECTION_RADAR.md:289-335`; `registry/edge-type-registry.json`
  (53 types, 5 proposed absent); `registry/asset-pattern-registry.json`.
- **5:** `roadmap/evidence/background-connection-radar-v1-implementation.md:177-202`;
  `docs/BACKGROUND_CONNECTION_RADAR.md:143-187,529-553`.
- **6:** `calibration-review-summary` output; `processed/reports/phase_2_5_score_delta_validation.json`
  (content-profile coverage); `docs/ASSET_VALUE_MODEL.md`.
- **7:** `registry/asset-pattern-registry.json` (`missing_evidence` on all 27).
- **8:** `registry/asset-pattern-registry.json` (`ai_entrypoint_toc_routing_system`);
  `AI_TABLE_OF_CONTENTS.md`; `docs/ROADMAP_EXECUTION.md`.
- **9:** `config/sources.example.yaml:10,98`; `roadmap/gate-evidence.json`;
  `roadmap/evidence/phase-3-sandbox-pilot.md:11-13`; `docs/SECURITY_AND_PRIVACY.md`.
- **10:** `roadmap/evidence/phase-4-semantic-enrichment.md`,
  `roadmap/evidence/phase-5-alerting-and-research-radar.md`;
  `registry/edge-type-registry.json` (`semantically_similar_to`).

## Risk / human-review / ownership per opportunity

| # | Opportunity | Risk | Human review? | Data class |
|---|---|---|---|---|
| 1 | Reconcile phases 1 & 3 | Medium (governance) | **Yes — required** | source-owned (gate evidence) |
| 2 | Fix `boundary_deferred` logic | Low | Yes (design call) | source-owned (code+yaml) |
| 3 | Reconcile declared statuses | Low | Yes (sign-off) | source-owned (yaml) |
| 4 | WorkflowPartRecord Phase A | Medium | **Yes — 5 open decisions first** | candidate-only outputs |
| 5 | Radar calibration harness | Medium | Yes (label set) | generated/candidate |
| 6 | Calibration breadth batch | Medium | **Yes — human labels** | candidate-only labels |
| 7 | Validate 27 patterns | Medium | **Yes — labels** | candidate-only |
| 8 | AI-TOC validator + TOC fixes | Low | Light | source-owned (docs/tooling) |
| 9 | Public-release scrub | Medium-High (if published) | **Yes — public/private split** | source-owned + generated |
| 10 | Deferred-systems plan doc | Low (planning only) | Yes (sets gates) | source-owned (doc) |

---

## What should NOT be done yet

- Do **not** flip the codex-attested phase-1/3 gates to `human_verified: true` or
  `reviewer: Lowell` without an actual human review — that re-introduces exactly the
  dishonesty the hardening removed.
- Do **not** enable embeddings, the `semantically_similar_to` edge, scheduled scans,
  alert delivery, GitHub scanning, external research automation, or the Tier-2
  strong-model radar verifier. All remain behind named, unmet gates.
- Do **not** lower the radar's `tau` or evidence gate to "get results." Calibrate with a
  labeled harness first.
- Do **not** promote any generated edge, score, proposal, radar candidate, or pattern
  match to truth, or install governance hooks into an active repo (phase-3 gate is not
  human-verified).
- Do **not** build `WorkflowPartRecord` before the 5 open decisions in the
  workflow-composition red-team are answered.

---

## Suggested next roadmap phases / epics

- **Phase 1/3 human re-verification** (close the honest gaps; smallest critical path).
- **Roadmap-integrity hardening v2**: finish `boundary_deferred` semantics + reconcile YAML.
- **Phase 2.6 — calibration breadth**: document/dataset/media/model + high-value-band labels.
- **Radar v1.1 — calibration harness** (recall/precision over labeled known-good links).
- **Workflow-part recognition epic** (red-team Phases A–F), candidate-only.
- **Public-release readiness phase** (scrub + public/private split).

---

## Premortem — next 90 days

1. **Most likely failure:** someone closes the re-opened phases by editing
   `gate-evidence.json` (reviewer→Lowell or `human_verified: true`) without a real
   review, silently undoing the hardening. Mitigation: require a linked human review
   artifact per gate, and treat unexplained reviewer flips as a red flag.
2. `boundary_deferred` stays half-wired; phases 4/5 show `awaiting_human_gate`
   indefinitely, and a future agent "helpfully" marks the deferred gates verified.
3. `WorkflowPartRecord` is built before the open decisions → ontology sprawl and a
   public/private part-catalog leak (the exact risks the red-team named).
4. The radar is "made useful" by lowering `tau`/gates → false-positive flood that
   poisons reviewer trust.
5. Phase 2.5's clean 100/100 code-surface result is over-generalized to documents/
   media, and scores are trusted where they were never calibrated.
6. The repo is published with local paths, owner handle, and private repo names intact.
7. Calibration and proposal engines stagnate: proposal review already shows novelty
   `already_known: 25` vs `novel: 6` — the engine mostly restates known patterns.

---

## Recommended fix / build order

1. **Reconcile the roadmap** (#1, #2, #3): human-verify or honestly re-state phases 1
   and 3; finish `boundary_deferred`; flip declared statuses. Nothing else should be
   called "next" until the baseline tells the truth.
2. **Public/private split + scrub decision** (#9): cheap, unblocks publishing and
   prevents leaks; needed before any external sharing of evidence.
3. **Calibration breadth batch** (#6): prerequisite for trusting scores in any
   downstream build.
4. **Radar calibration harness** (#5): turn a silent system into a measured one.
5. **WorkflowPartRecord Phase A** (#4): after the 5 open decisions.
6. **AI-TOC validator + TOC/doc updates** (#8): cheap governance, dogfoods the standard.
7. **Deferred-systems plan doc** (#10): name the gates for the next agent.
8. **Validate the top 3–4 asset patterns** (#7): feeds both scoring and WorkflowParts.

---

## Commands run and results

All with `$env:PYTHONPATH='src'` from repo root (Windows / Python 3.12).

| Command | Result |
|---|---|
| `cli validate` | `{"valid": true, "checked_count": 65, "errors": []}` |
| `cli roadmap check --no-update` | exit 0; statuses per table above; new `status_warnings` and `human_gate_unverified_details` present |
| `cli recommend calibration-review-summary` | 100/100 reviewed, gate complete; instance `source:91/archive:9`; bands `medium:50/low:50`; ratings `about_right:54/too_high:18/too_low:28`; methodology `asset-calibration-sampling-v0.2-clean-deduped`, no stale warning |
| `cli recommend proposal-review-summary` | 50/50 reviewed; `useful:30`; novelty `already_known:25/novel:6/unsure:19`; decisions `accept:28/reject:18/defer:4` |
| `cli recommend roadmap-readiness` | wrote `processed/reports/phase4_semantic_enrichment_readiness.md` and `phase5_alerting_research_readiness.md` (planning templates only; enabled nothing) |

Also verified by reading: `roadmap.py` (hardened gate logic), `cli.py:466-483` +
`research.py:14-33` (`--enable-external` gate now present — my prior red-team finding is
**fixed**), `registry/edge-type-registry.json`, `registry/asset-pattern-registry.json`,
`docs/SECURITY_AND_PRIVACY.md`, `docs/BACKGROUND_CONNECTION_RADAR.md`,
`config/sources.example.yaml`, and git log (commit `64663c9`).

---

## Things not verified

- The operative `config/sources.local.yaml` (gitignored) was not read; the
  GitHub-deferred / source-scope posture depends on it.
- Radar smoke-run numbers (10k candidates / 0 packets / ~95k assets) were read from
  evidence, not re-executed (no scan run per constraints).
- The generated catalog, calibration JSONL, and graph are local-only (gitignored); I
  inspected the Phase 2.5 validation JSON on disk but did not regenerate it.
- Independence of the Phase 2 desired-band labels from the content-aware scorer (a
  possible-circularity flag from my red-team) is still unconfirmed.
- I did not run scans, GitHub calls, embeddings, the radar, or `research missing`; this
  sweep is read-only except for this report.
- Whether any human review actually occurred behind the codex-recorded gates is
  unknown from the repo alone — the reviewer field is the only signal.
