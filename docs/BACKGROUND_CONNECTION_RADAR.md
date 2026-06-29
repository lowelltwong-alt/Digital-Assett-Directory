# Background Connection Radar

## Purpose

The Background Connection Radar is a two-speed discovery workflow for DAD:

```text
low-compute background scout -> candidate connection -> high-intensity verifier -> expansion map -> human review
```

It copies a useful human pattern: quiet associative search runs in the
background around current attention, then a promising connection pulls older
memory out of cold storage and receives concentrated reasoning.

V1 is implemented as a manual local-only CLI command, not an enabled daemon. It
remains candidate-only, bounded, and review-gated.

## Mental Model

The system has two modes.

### 1. Background Scout

The scout is cheap and patient. It does not need a powerful model. It slowly
searches the knowledge base for weak signals that connect:

- what is currently active or recently interesting;
- old assets that have not been touched in a long time;
- weak or orphaned graph nodes;
- duplicate variants and deltas;
- learning-loop events;
- workflows that share a shape but live in different domains.

The scout should prefer recall, but only emit small candidate packets. It does
not make truth claims, edit sources, run expensive enrichment, or escalate every
similarity hit.

### 2. High-Intensity Verifier

The verifier wakes only when a candidate connection crosses a threshold. It can
use a stronger model, deeper context, fresh-eyes review, and multi-hop graph
expansion.

The verifier asks:

- Is this connection real, or just lexical coincidence?
- Does it connect to multiple useful nodes?
- Does it activate a cold asset, orphan asset, or forgotten workflow?
- Does the connection create a new composite workflow?
- Does it need human review before any score, edge, or roadmap consequence?
- What would make this connection more valuable?

The verifier still writes candidate evidence, not source truth.

## Core Objects

| Object | Meaning |
|---|---|
| `attention_seed` | A current interest, active task, recent asset, roadmap phase, or repeated user theme. |
| `cold_memory_asset` | An older or low-recent-use asset that may become useful again. |
| `background_probe` | A cheap scan pass around one or more attention seeds. |
| `connection_candidate` | A proposed edge or composite relation with evidence and uncertainty. |
| `escalation_packet` | The bounded context sent to a stronger verifier. |
| `expansion_map` | The verifier's candidate graph of direct and multi-hop follow-on nodes. |
| `human_review_packet` | A compact packet for deciding whether the connection is useful, safe, novel, and actionable. |

## Inputs

### Attention Sources

Use current attention as the hot side of the search:

- assets changed in recent local git history;
- recently edited files;
- active roadmap phase and unresolved gates;
- recently reviewed assets, proposals, or calibration labels;
- recently created lessons or postflights, reduced to tags and asset IDs;
- redacted preflight task text reduced to controlled tags and capabilities;
- active repo names or source scopes approved by the user.

Attention seeds must be privacy-first. Do not persist raw user messages, raw
chat excerpts, or unredacted task text as attention. Store only deterministic
artifact IDs, controlled tags, capabilities, source scope IDs, and redacted task
signals. Attention seeds should decay over time so yesterday's obsession does
not dominate forever; start with a seven-day half-life for git-recency seeds and
calibrate later.

### Cold Storage Sources

Use cold storage as the deep-memory side:

- older assets with low recency but high potential value;
- orphaned or weakly connected graph nodes;
- old workflow docs, handoffs, lessons, temp attempts, and archaeology records;
- duplicate or near-duplicate clusters with meaningful deltas;
- archived repos and old project families, subject to source-scope approval;
- low-score but high-upside assets flagged during calibration.

Cold assets are not low value by default. They are low-attention until a new
context activates them.

## Low-Compute Background Scout

The scout should run bounded, incremental passes. In v1, it should be a CLI
command or scheduled job only after explicit approval, not an always-on hidden
process.

Cheap signals:

- shared controlled tags and context tags;
- asset pattern overlap;
- need-to-capability matches;
- graph two-hop paths;
- orphan-to-active-topic bridges;
- duplicate cluster deltas;
- semantic-evolution grades;
- lesson applicability tags;
- title/path/token overlap using deterministic indexes;
- age gap plus current-topic match, to find cold-storage resurfacing.

The scout emits only candidate packets with:

- source asset IDs;
- target asset IDs;
- attention seed IDs;
- cold-memory cue;
- evidence snippets or metadata;
- cheap score components;
- why this may matter now;
- why it may be false;
- escalation reason;
- generated timestamp and scan ID.

## Escalation Trigger

Escalate when a cheap candidate looks unusually connective, not merely similar.

Use gate-before-score escalation. A high score can never override a failed
safety, evidence, or authority gate.

Methodology version: `background-connection-connectivity-v1`.

### Hard Gates

All gates must pass before scoring can rank a candidate:

| Gate | Required condition |
|---|---|
| `safety_gate` | Redaction is clean; no secrets, raw credentials, excluded paths, sensitive lanes, source-mutation implication, or unapproved scope. |
| `evidence_gate` | At least two independent cheap signals; both endpoints have real content identity or declared metadata; graph evidence is from the current scan watermark. |
| `authority_gate` | Authority boundaries are compatible, or the packet is explicitly marked `requires_human_gate` for cross-boundary review. |

If any gate fails, do not escalate. Store a rejected or blocked candidate only if
that record is useful for calibration.

### Connectivity Score

Score only candidates that pass all hard gates:

```text
connectivity_score =
  0.30 * attention_relevance
+ 0.20 * cold_lift
+ 0.25 * complementarity
+ 0.15 * multi_hop_potential
+ 0.10 * novelty
```

Inputs are normalized to `0.0..1.0`.

| Component | Deterministic meaning |
|---|---|
| `attention_relevance` | Match between candidate endpoints and current artifact-derived attention tags. |
| `cold_lift` | Old or low-attention asset resurfacing in a current context; zero when both endpoints are already hot. |
| `complementarity` | Capability/need or workflow-part fit minus duplicate or MinHash similarity. |
| `multi_hop_potential` | Capped, log-scaled count of distinct useful two-hop neighbors gained. |
| `novelty` | Zero when the edge already exists, is reviewed, or is obvious duplicate/lineage evidence. |

Default escalation threshold: `connectivity_score >= 0.70`.

Default budget: `5` packets per run, with `1` to `2` slots reserved for
cold-only candidates so hot topics cannot consume the entire budget.

Before spending the budget, cluster candidates by connection type and endpoint
families. Escalate only the highest-scoring representative; attach other members
as supporting evidence inside the same packet.

### Escalation Packet

The packet is bounded, safety-cleared, and untrusted-data aware:

```text
packet_id
scan_id_watermark
generated_at
methodology_version
attention_seed_ids[]
cold_memory_cue
source_asset_ids[]
target_asset_ids[]
deduped_member_candidate_ids[]
minimal_context: title, asset_type, role_in_workflow, authority_boundary
redacted_evidence_snippets[]
cheap_signal_evidence{}
component_scores{}
connectivity_score
proposed_connection_type
reuse_first_edge_mapping
why_might_matter_now
why_might_be_false
stop_conditions
safety_cleared=true
requested_verifier_tasks[]
budget_priority
review_status="generated_candidate"
```

Do not include raw knowledge-base dumps. Any scanned content in the packet is
evidence, not instructions.

## High-Intensity Verification

The verifier receives an escalation packet, not the entire knowledge base. It
can request more context only through approved retrieval.

Verifier tasks:

1. Confirm or reject the proposed connection.
2. Classify the connection type.
3. Identify direct follow-on nodes.
4. Search for multi-hop expansion candidates.
5. Separate duplicate similarity from complementarity.
6. Estimate current usefulness, future upside, and lift conditions.
7. Red-team false positives and unsafe compositions.
8. Produce a human review packet.

Output remains candidate-only:

```text
verified_candidate | rejected_candidate | needs_human_review | needs_more_evidence
```

## Candidate Connection Types

Useful packet labels include:

- `activates_cold_asset`
- `bridges_orphan_to_attention_seed`
- `composes_with`
- `duplicate_variant_delta`
- `same_workflow_different_domain`
- `lesson_applies_when`
- `lesson_does_not_apply_when`
- `workflow_part_of`
- `missing_capability_for`
- `dangerous_composition_with`
- `requires_human_gate`
- `supports_but_cannot_override`

These labels are review-packet types, not automatically new edge IDs. Claude's
workflow-composition red-team found that DAD already has a rich edge vocabulary,
so the radar should reuse existing edge types before proposing new ones.

Reuse-first mapping:

| Packet meaning | Prefer existing vocabulary |
|---|---|
| Assets combine usefully | `composes_with`, `complements`, `has_workflow_step`, `has_member_asset` |
| One asset activates another | `activates`, `satisfies_need`, `blocked_by` |
| Human review is required | `requires_human_gate`, `governed_by` |
| Lesson is context-bound | `applies_when`, `does_not_apply_when`, `dangerous_out_of_context` |
| Order matters | `depends_on`, `should_precede`, `stabilized_by` |
| Unsafe or boundary-risky connection | `unsafe_composition_with`, `contaminates_if_default`, `supports_but_cannot_override` |
| Duplicate, variant, or lineage evidence | `variant_of`, `near_duplicate_of`, `lineage_evidence_for`, `has_delta_candidate` |

WorkflowPartRecord Phase A added the narrow edge additions after
implementation-time registry review:

- `produces_input_for`
- `substitutes_for`
- `specializes`
- `generalizes`
- `quarantines`

`incompatible_with` remains deferred unless structural incompatibility proves
distinct from `unsafe_composition_with`.

Do not add near-synonym edges when an existing edge plus context tag is enough.

## Workflow Parts And Recomposition

Claude's red-team adds an important layer: the radar should discover not only
whole workflow assets, but recombinable workflow parts beneath those assets.

Current distinction:

| Layer | Meaning |
|---|---|
| Asset pattern | A whole-workflow shape such as evaluation harness, learning loop, or security scanner. |
| Workflow part | A reusable sub-unit such as validator, gate, review packet, runner, boundary map, or learning signal. |
| Connection candidate | A proposed relation between assets or parts. |
| Assembly packet | A candidate plan for combining parts in a new context. |

Candidate contract: `WorkflowPartRecord`.

Phase A implements this contract and the manual command:

```text
asset-dir recommend workflow-parts --source-id all --review-sample 50
```

Deterministically knowable fields include:

- `part_id`
- `part_type`
- `source_asset_ids`
- `asset_pattern_id`
- `role_in_workflow`
- `authority_boundary`
- `human_gates`
- `validation_commands`, when declared
- `context_tags`
- `maturity`
- `confidence`
- `risk`
- `methodology_version`
- `review_status="generated_candidate"`

Fields that must remain empty unless declared, structured, or human-reviewed:

- `inputs`
- `outputs`
- `preconditions`
- `postconditions`
- `side_effects`
- `failure_modes`
- `composition_affordances`
- `incompatible_parts`

This prevents the radar from hallucinating dataflow from filenames or weak
semantic similarity.

Workflow-part assembly packs and preflight surfacing remain deferred until
reviewed part examples exist and the ceremony threshold is calibrated.

## Multi-Hop Expansion

The most valuable moments are not single edges. They are connection cascades.

When one edge is verified, ask:

- What other assets become newly relevant because of this edge?
- Does this reveal a workflow family?
- Does this turn an orphan into a hub?
- Does this suggest a new abstraction layer?
- Does it expose a missing capability, evaluator, dataset, schema, or gate?
- Does it connect current interest to an old lesson?

The expansion map should show:

- direct nodes;
- second-hop nodes;
- confidence per hop;
- why each hop might be useful;
- why each hop might be wrong;
- stop conditions.

V1 expansion caps:

- maximum `2` hops;
- maximum `25` nodes per expansion map;
- confidence decays per hop;
- stop when a path crosses unapproved authority boundaries, loses evidence, or
  repeats an already known edge.

## Safety Boundaries

The radar must not:

- mutate scanned source repositories;
- promote candidate edges to truth;
- treat similarity, graph centrality, or model judgment as proof of value;
- read excluded sensitive locations;
- send secrets or raw credentials to a verifier;
- run broad scans without source-scope approval;
- wake expensive models without a bounded escalation packet and budget.

Generated connection records should be stored under `processed/` until curated
evidence is reviewed and intentionally tracked.

## Compute Policy

Use a tiered budget:

| Tier | Compute | Role |
|---|---|---|
| Tier 0 | Deterministic indexes only | Maintain attention seeds, cold queues, cheap graph features. |
| Tier 1 | Small/local model or heuristics | Generate connection candidates and reason strings. |
| Tier 2 | Strong model | Verify high-potential candidates and map expansion. |
| Tier 3 | Human review | Promote, reject, defer, or request more evidence. |

V1 can start with Tier 0 and Tier 1 only. Tier 2 should be a manual command or
review queue until provider/privacy gates are approved.

Hard compute bounds for v1:

- index-driven probes only, not all-pairs scans;
- hot set cap: `200` attention seeds;
- per-seed neighbor cap: `50`;
- complexity target: `O(hot_set * per_seed_cap)`, not `O(N^2)`;
- incremental watermark: probe assets changed since last pass plus their indexed
  neighbors;
- escalation budget: `5` packets per run;
- cold-only reserve: `1` to `2` packets per run;
- multi-hop expansion cap: `2` hops and `25` nodes;
- Tier 2 verification is manual until Phase 4 provider/privacy gates are
  approved.

Family dedup happens before budget allocation. A duplicate family, pytest copy
flood, or repeated stale proposal can contribute supporting members to one
packet, but cannot consume many escalation slots.

## Claude Fresh-Eyes Design Prompt

Use this prompt to ask Claude for an independent design. Claude should not edit
files unless explicitly authorized.

```text
You are giving an independent fresh-eyes design for the Digital Asset Directory
Background Connection Radar.

Repo:
C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory

Read first:
1. AGENTS.md
2. AI_FRONT_DOOR.md
3. AI_TABLE_OF_CONTENTS.md
4. docs/BACKGROUND_CONNECTION_RADAR.md
5. docs/KNOWLEDGE_GRAPH_MODEL.md
6. docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md
7. docs/CONTEXTUAL_LEARNING_AND_WORKTREE_ARCHAEOLOGY.md
8. docs/ASSET_USE_PAY_FORWARD_LOOP.md
9. docs/LOAD_BEARING_DECISION_REVIEW.md

Task:
Design your own version of a low-compute background scout that slowly scans the
knowledge base for new connections around current attention, then escalates only
high-potential candidates to a stronger verifier for multi-hop expansion.

Constraints:
- Local-only and candidate-only.
- Do not mutate scanned/source repos.
- Do not enable GitHub scanning.
- Do not implement a daemon yet.
- Keep generated graph edges and model judgments as candidate evidence.
- Protect secrets and sensitive source data.

Deliver:
1. Your independent architecture.
2. What cheap signals should run in the background.
3. What threshold should wake a stronger model.
4. What the escalation packet should contain.
5. How to prevent false positives and compute blowups.
6. What contracts/schemas are needed later.
7. Premortem: how this could fail.
8. Red-team: unsafe or misleading behaviors.
9. Your recommendation: Codex design, your design, or hybrid.

Write your report to:
roadmap/evidence/claude-background-connection-radar-review.md
```

## Synthesis Workflow

After Claude produces its independent design:

1. Compare architectures side by side.
2. Keep shared conclusions as likely stable.
3. Preserve disagreements as design choices, not errors.
4. Red-team the hybrid.
5. Choose a v1 bounded experiment:
   - no daemon;
   - one CLI command;
   - fixed source scope;
   - fixed attention seed set;
   - fixed escalation budget;
   - generated output only.
6. Add schemas only after the review says the fields are right.
7. Add roadmap evidence without marking phases complete automatically.

Applied synthesis from Claude's workflow-composition red-team:

- reuse existing edge, context-tag, and asset-pattern registries first;
- add only genuinely missing edge types after registry review;
- treat `WorkflowPartRecord` as a candidate contract beneath existing asset
  patterns;
- recognize one part per asset family, not one per temp or pytest copy;
- keep private/public-safe boundaries from `docs/PUBLIC_SAFE_SOURCE_SWEEPS.md`;
- use same-repo or same-family evidence before cross-repo recomposition unless a
  human gate approves the wider jump;
- leave unknown inputs, outputs, side effects, and failure modes empty rather
  than inferring them from weak evidence.

Applied hardenings from Claude's background-radar fresh-eyes review:

- use gate-before-score escalation with `safety_gate`, `evidence_gate`, and
  `authority_gate` as binary blockers;
- use `background-connection-connectivity-v1` with explicit formula, threshold
  `0.70`, and budget `5`;
- derive attention from redacted repo artifacts, not raw user messages;
- apply hard compute caps and incremental watermarks;
- dedupe by endpoint family before spending the escalation budget;
- reserve `1` to `2` slots for cold-only candidates;
- feed verified connections into ceiling or edge-candidacy review, never current
  score, until calibrated.

## Suggested V1 Experiment

Run a one-shot "attention to cold storage" report:

```text
asset-dir recommend background-connections --attention recent --cold older --limit 50 --escalation-budget 5 --tau 0.70 --max-hops 2 --reserve-cold 2
```

V1 should produce:

- `processed/learning/background_attention_seeds.jsonl`
- `processed/reports/background_connection_candidates.md`
- `processed/learning/background_connection_candidates.jsonl`
- `processed/learning/background_escalation_packets.jsonl`
- `processed/reports/background_connection_escalation_packets.md`
- `processed/learning/background_expansion_maps.jsonl`

No autonomous model calls are needed in the first pass. The report can instead
select the top escalation packets for human or Claude/Codex review.

## Current Defaults And Remaining Questions

Defaults adopted for v1:

- current attention comes from redacted repo artifacts, not raw messages;
- attention decay starts with a seven-day half-life for git-recency seeds;
- cold and stale are separate axes: cold means low recent attention; stale means
  past a freshness threshold;
- background passes are manual one-shot commands;
- escalation budget is `5` packets per run;
- Tier 2 strong-model verification is manual until Phase 4 provider/privacy
  gates;
- review-packet labels stay generated-only before any edge-registry promotion;
- workflow-part records stay generated-only and are not shown in preflight by
  default;
- verified connections can affect ceiling or edge-candidacy review, not current
  score, until calibrated.

Remaining decisions:

- threshold calibration for when real catalog candidates should become
  escalation packets;
- which workflow-part families are useful enough for human review and later
  preflight surfacing;
- whether scheduled or postflight-triggered runs are worth the governance cost
  after the manual one-shot experiment.

## Recommendation

Use a hybrid design:

- deterministic scout first;
- privacy-first attention from redacted artifacts;
- graph and lesson signals as cheap background association;
- gate-before-score escalation;
- family dedup before escalation budget;
- hard compute caps;
- strong-model verifier only through bounded escalation packets;
- human review before promotion;
- one-shot CLI experiment before any daemon or scheduled process.

This keeps the "background thought" feeling while respecting DAD's authority,
privacy, compute, and candidate-only boundaries.
