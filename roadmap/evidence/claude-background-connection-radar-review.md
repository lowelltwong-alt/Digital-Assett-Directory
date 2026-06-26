# Claude Background Connection Radar — Independent Fresh-Eyes Design

Date: 2026-06-26. Reviewer: Claude Code (independent design). Status: candidate design evidence
only. Read-only except this file. No source/scanned repos mutated, no GitHub scanning, no daemon,
no autonomous model calls proposed for v1. Repo is under active parallel edits — registry/doc
contents cited are a point-in-time read.

## How this differs from Codex's design

Codex's `docs/BACKGROUND_CONNECTION_RADAR.md` is already strong and already absorbed my prior
workflow-composition red-team (reuse-first edges, deterministic-only `WorkflowPartRecord` fields,
public-safe boundary, one-part-per-family). I will not re-derive what it gets right. This design
**keeps Codex's two-speed architecture and object model** and supplies the three things it leaves
under-specified, plus one lesson it doesn't carry:

1. **Escalation as gates-before-score, with concrete math** (Codex lists 7 components but no
   formula or threshold).
2. **Attention defined privacy-first from repo artifacts, not raw user messages** (Codex's
   attention sources include "recent user messages," a new sensitive sink).
3. **Hard compute bounds** (Codex says "bounded/rate-limited" but gives no numbers; multi-hop is
   left open-ended).
4. **Family-dedup before the escalation budget** — carrying the Phase 2B finding (one idea
   counted 23 times ate the review budget) directly into the radar.

These are additive hardenings, not disagreements, except #2 (a real disagreement worth keeping).

## 1. Independent Architecture — "watermarked, index-driven, gate-before-budget"

```text
attention vector (decayed, redacted, artifact-derived)
  + scan watermark (only assets changed since last pass + their index neighbors)
        |
Tier 0  deterministic index probe  ->  raw connection candidates
        |   (reuse existing IDF postings, shingle/MinHash postings, tag/capability indexes,
        |    graph 2-hop, duplicate clusters, lesson context tags)
        v
Tier 1  cheap scoring + HARD GATES  ->  passing candidates only
        |   gates(safety, evidence, authority) are binary; score(connectivity) ranks survivors
        v
        family-dedup  ->  representative candidates  ->  hard per-run budget (priority queue)
        v
        escalation packets (bounded, safety-cleared, generated-only)
        |
Tier 2  strong verifier  =  MANUAL queue in v1 (human or Claude/Codex reads the packet)
        |   confirm/reject, classify, bounded 2-hop expansion, dup-vs-complement, red-team
        v
Tier 3  human review  ->  promote to ceiling/edge-candidacy only (never current score) after calibration
```

The defining property: **a high connectivity score can never override a failed safety, evidence,
or authority gate.** Gates are multiplicative 0/1; score only ranks survivors. This is the
structural defense against "misleading certainty," which is the recurring failure mode in this
project.

## 2. Cheap Background Signals (Tier 0/1, no model)

All reuse existing deterministic indexes — the scout adds no new heavy computation:

- shared controlled tags / context tags (existing `context-tag-registry.json`);
- asset-pattern overlap (existing `asset-pattern-registry.json`);
- need→capability matches (existing `satisfies_need` logic);
- graph 2-hop paths over existing candidate edges;
- IDF-weighted token overlap (existing postings) — **rare shared terms only**, not raw overlap;
- shingle/MinHash near-duplicate + containment (existing identity layer);
- duplicate-cluster deltas + semantic-evolution grades (existing);
- lesson `applies_when` context-tag match (existing);
- **cold-lift signal**: `age_gap_normalized × current_topic_match` — an old asset that matches a
  hot topic. Zero if both endpoints are already hot (no resurfacing value).

Attention vector (my privacy-first definition): a small, decaying, **deterministic** set derived
from repo artifacts only —
- assets changed in recent local git history (no message content);
- active roadmap phase + unresolved gates;
- recently generated postflights/lessons/calibration labels (their tags, not raw text);
- preflight task text **after redaction**, reduced to controlled tags/capabilities, never stored raw;
- user-approved source scopes.

Attention seeds are themselves candidate, carry a decay half-life, and store only tags/ids — never
raw user messages or excerpts. This avoids creating a new sensitive sink.

## 3. Escalation Threshold (concrete, calibratable)

**Step 1 — hard gates (all must pass, else never escalate):**
- `safety_gate`: redaction pass clean (no secrets/PII), no excluded/sensitive paths, source scope
  approved, no source-mutation implication.
- `evidence_gate`: ≥2 independent cheap signals AND both endpoints have real content identity
  (`content_sha256` or declared metadata — not metadata-only ghosts) AND graph evidence is from the
  **current scan watermark** (reject stale-edge candidates).
- `authority_gate`: endpoint authority boundaries compatible, OR a `requires_human_gate` is attached
  for cross-source-owned links (cross-authority never auto-escalates).

**Step 2 — connectivity score (0–1, deterministic, cited), only if gates pass:**
```
score = 0.30*attention_relevance
      + 0.20*cold_lift
      + 0.25*complementarity      # = capability/need coverage MINUS duplicate similarity
      + 0.15*multi_hop_potential  # capped, log-scaled count of distinct 2-hop neighbors gained
      + 0.10*novelty              # 0 if the edge already exists or is reviewed/obvious
```
`complementarity` subtracts MinHash/near-dup similarity, so duplicate floods score low (they are
not connective, just same). `novelty` zeroes known edges.

**Step 3 — family-dedup, then budget:** cluster passing candidates by `(connection_type, sorted
endpoint families/clusters)`; keep the highest-score representative; others ride along as packet
members, not separate escalations. Then escalate the top-K where `score ≥ τ` within a hard per-run
budget `B`.

Start conservative: `τ = 0.70`, `B = 5` per run, and **reserve ~1–2 budget slots for cold-only
candidates** so the scout doesn't fixate on hot topics. Calibrate `τ`/weights later on a deduped,
class-stratified sample (do not calibrate on a repetition-biased sample — the Phase 2B lesson).

## 4. Escalation Packet Contents (bounded, safety-cleared)

```text
packet_id, scan_id_watermark, generated_at, methodology_version
attention_seed_ids[], cold_memory_cue
source_asset_ids[], target_asset_ids[]   # representative + deduped members
minimal_context: title, asset_type, role_in_workflow, authority_boundary  # NO raw content
redacted_evidence_snippets[]             # bounded token budget, redaction-proven
cheap_signal_evidence{}, component_scores{}, connectivity_score
proposed_connection_type                 # review-packet label, reuse-first edge mapping
why_might_matter_now, why_might_be_false, stop_conditions
safety_cleared = true                    # redaction clean, no secrets, scope approved
requested_verifier_tasks[]               # confirm/reject; classify; bounded 2-hop expand;
                                         # dup-vs-complement; ceiling (not current-score) estimate; red-team-false
budget_priority, review_status = "generated_candidate"
```
The packet is a **self-contained, untrusted-data artifact**: scanned content is framed as evidence,
never instructions (prompt-injection defense), and is token-bounded so it cannot smuggle the KB.

## 5. Preventing False Positives And Compute Blowups

False positives:
- gates-before-score (unsafe/under-evidenced/cross-authority can't escalate);
- `complementarity` penalizes duplicates; `novelty` zeroes known edges;
- min ≥2 independent signals; IDF down-weights common tokens (kills generic-overlap FPs — the
  Phase 2B cross-repo lexical failure);
- family-dedup so one idea can't win N budget slots;
- attention decay so stale obsessions stop generating candidates.

Compute blowups:
- index-driven, not all-pairs: probe `hot_set (≤~200) × per-seed neighbors (≤~50)` via existing
  postings → roughly `O(|hot|·cap)`, not `O(N²)`;
- watermark/incremental: only assets changed since last pass + their neighbors are re-probed;
- multi-hop capped at **2 hops, ≤25 nodes per expansion**, confidence-decayed per hop, with stop
  conditions;
- hard per-run escalation budget + priority queue (no unlimited wakeups);
- Tier 2 is manual in v1 — zero autonomous model spend.

## 6. Contracts/Schemas Needed Later (after v1 proves field shape)

- `AttentionSeedRecord` (seed_id, source_kind, tags/capabilities, decay/half-life, created_at,
  review_status).
- `ConnectionCandidateRecord` (candidate_id, source/target ids, connection_type, component_scores,
  connectivity_score, gates_passed, evidence, scan_watermark, review_status).
- `EscalationPacketRecord` (fields in §4).
- `ExpansionMapRecord` (direct nodes, 2nd-hop nodes, per-hop confidence, why-useful/why-wrong, stop
  conditions).
- Reserve `WorkflowPartRecord` (per Codex/my prior design) but do not invent it yet.
- **Reuse** `edge-type-registry.json`, `context-tag-registry.json`, `asset-pattern-registry.json`;
  add only the previously-identified missing edges after registry review. Every record:
  `review_status="generated_candidate"` default, `methodology_version` required (the
  score-methodology learning rule).

This is a **high-risk, load-bearing** layer (it touches scoring inputs, automation, and a future
model-call path) — route the schema/threshold decisions through `docs/LOAD_BEARING_DECISION_REVIEW.md`.

## 7. Premortem (how this fails in 6 months)

- **Attention becomes a privacy leak**: raw user messages/excerpts persisted as seeds. → derive
  from artifacts + tags only, redact, store no raw text.
- **Budget eaten by repeated families**: same orphan→topic bridge escalated 23×. → family-dedup
  before budget (if skipped, this is the most likely failure, by direct analogy to Phase 2B).
- **Multi-hop blowup / runtime death** on the real corpus. → hop/fan-out/budget caps + incremental
  watermark; if uncapped, the first whole-drive run is the last.
- **Hot-topic fixation**: cold storage never resurfaces (the whole point lost). → `cold_lift`
  component + reserved cold-only budget slots.
- **Stale-evidence escalation**: candidates built on an old scan's edges. → watermark guard.
- **Verifier over-trust**: a strong model "confirms" a lexical coincidence and it leaks into
  scores. → candidate-only, human gate, mandatory red-team-false in packet, feed ceilings not
  current score.
- **Noise fatigue**: too many candidates, humans stop reading. → precision-first `τ`, small `B`,
  review queue not firehose.
- **Premature daemon**: an always-on background process scanning sensitive trees. → v1 one-shot CLI
  only; daemon is a separate, later, gated decision.

## 8. Red-Team (unsafe or misleading behaviors)

- **Secret/PII exfiltration to the verifier.** → `safety_gate` + redaction proof + bounded packet;
  `safety_cleared` must be true or the packet is not emitted.
- **Candidate edges treated as truth.** → candidate-only everywhere; promotion only to
  ceiling/edge-candidacy after human calibration, never current value score.
- **Cross-authority recomposition suggested as safe** (e.g., combine LawFirm + Logos parts). →
  `authority_gate` forces `requires_human_gate`; never auto-escalate cross-source-owned links.
- **Domain lessons over-generalized** (legal/scripture rules applied broadly). → carry
  `applies_when`/`does_not_apply_when`/`dangerous_out_of_context` into the packet; domain-scope tag.
- **Prompt injection from scanned content** into the verifier. → packet frames all scanned text as
  untrusted evidence/data, strips imperative instructions, token-bounded.
- **Attention manipulation**: a doc stuffed with hot tokens forces escalation. → IDF down-weights
  common tokens, per-seed fan-out cap, gates; a single noisy doc can't buy a budget slot.
- **Novelty rewarding spurious cross-domain links.** → complementarity penalty + min-evidence +
  cross-authority human gate (the exact Phase 2B cross-repo-lexical failure, pre-empted).

## 9. Recommendation: Hybrid (Codex architecture + these hardenings)

**Hybrid.** Codex's two-speed architecture, object model, tiered compute policy, and reuse-first
edge mapping are sound and already incorporate prior review — adopt them. Add the four fresh-eyes
hardenings: (a) gate-before-score escalation with the concrete formula/threshold in §3; (b)
privacy-first artifact-derived attention in §2 (the one genuine disagreement — do **not** persist
raw user messages); (c) hard compute bounds in §5; (d) family-dedup before budget.

**V1 bounded experiment** (matches Codex's suggested experiment, with my gates/bounds):
```text
asset-dir recommend background-connections \
  --attention recent --cold older --limit 50 \
  --escalation-budget 5 --tau 0.70 --max-hops 2 --reserve-cold 2
```
- Tier 0/1 only; Tier 2 = manual packet review (no autonomous calls).
- Generated-only outputs: `processed/learning/background_connection_candidates.jsonl`,
  `processed/reports/background_connection_candidates.md`,
  `processed/reports/background_connection_escalation_packets.md`.
- No daemon. Add schemas only after this report proves the field shape. Record evidence in
  `roadmap/evidence/` without marking any roadmap phase complete.

## Open Questions For Lowell (answering Codex's, with my position)

- **"Current attention" definition** → artifact-derived + redacted tags only; not raw messages.
- **Attention decay** → start with a ~7-day half-life on git-recency seeds; calibrate.
- **Cold vs stale** → cold = low recent attention but real content identity + nonzero potential;
  stale = past freshness threshold. Different axes; don't conflate.
- **Scheduled/manual/postflight-triggered** → manual one-shot for v1; postflight-triggered later;
  daemon only after a separate gated decision.
- **Escalation budget** → 5/run with 1–2 reserved cold slots; raise only after precision is measured.
- **Strong-model verification** → manual until Phase 4 provider/privacy gates; the model call is
  itself a high-risk load-bearing decision.
- **Edge registry vs generated-only labels** → generated-only review-packet labels first; promote to
  registry edges only after review (reuse existing edges; ≤5 new).
- **Feedback into score** → ceilings/edge-candidacy only, never current score, until calibrated.

## Files Inspected

- `docs/BACKGROUND_CONNECTION_RADAR.md` (Codex design), `docs/ASSET_USE_PAY_FORWARD_LOOP.md`,
  `docs/LOAD_BEARING_DECISION_REVIEW.md` (this pass).
- `AGENTS.md`, `AI_FRONT_DOOR.md`, `AI_TABLE_OF_CONTENTS.md`, `docs/KNOWLEDGE_GRAPH_MODEL.md`,
  `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`, `docs/CONTEXTUAL_LEARNING_AND_WORKTREE_ARCHAEOLOGY.md`
  (this pass + earlier this session).
- Prior-session context: edge/context-tag/asset-pattern registries, scoring instance-class +
  duplicate discounts, identity layers (IDF/shingle/MinHash), Phase 2/2B calibration findings.

## Assumptions

- Existing inverted indexes (IDF postings, shingle/MinHash postings, tag/capability maps) are
  reusable by the scout; if not, Tier 0 must build lightweight ones before the scout is bounded.
- "Hot set" can be derived deterministically from local git recency + roadmap state without reading
  raw user messages.
- Registry/doc contents are a point-in-time read under active parallel edits; re-confirm at
  implementation time.
</content>
