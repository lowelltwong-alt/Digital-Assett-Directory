# Background Connection Radar Synthesis

## Inputs

- Codex design: `docs/BACKGROUND_CONNECTION_RADAR.md`
- Claude red-team: `roadmap/evidence/claude-workflow-composition-red-team.md`
- Claude background-radar fresh-eyes review:
  `roadmap/evidence/claude-background-connection-radar-review.md`
- Edge vocabulary checked at synthesis time: `registry/edge-type-registry.json`

## Synthesis Decision

The Background Connection Radar should use a reuse-first graph design.

The core loop remains:

```text
low-compute scout -> candidate connection -> bounded escalation packet -> high-intensity verifier -> human review
```

Claude's main correction is that DAD does not need many new edge types to make
this work. The existing edge registry already covers most composition,
authority, gating, ordering, duplicate, learning, and safety relationships.

## Adopted From Claude

From workflow-composition red-team:

- Reuse existing edge, context-tag, and asset-pattern registries first.
- Treat packet labels such as `activates_cold_asset` as review labels, not new
  edge IDs.
- Add new edge types only after implementation-time registry review.
- Keep `WorkflowPartRecord` as a future candidate contract beneath existing
  asset patterns.
- Recognize one workflow part per asset family, not one per temp, worktree, or
  pytest copy.
- Leave inputs, outputs, preconditions, side effects, failure modes, and
  composition affordances empty unless declared, structured, or human-reviewed.
- Prefer same-repo or same-family recomposition before cross-repo jumps unless a
  human gate approves wider composition.
- Keep public-safe boundaries: role and metadata only, no private rows or raw
  source payloads in tracked evidence.

From background-radar fresh-eyes review:

- Use gate-before-score escalation. Safety, evidence, and authority are binary
  gates; a high score cannot override a failed gate.
- Define methodology version `background-connection-connectivity-v1`.
- Use the deterministic formula:

  ```text
  connectivity_score =
    0.30 * attention_relevance
  + 0.20 * cold_lift
  + 0.25 * complementarity
  + 0.15 * multi_hop_potential
  + 0.10 * novelty
  ```

- Start with threshold `0.70`, escalation budget `5` per run, and `1` to `2`
  reserved cold-only slots.
- Derive attention from redacted repo artifacts, never persisted raw user
  messages.
- Use index-driven probes with caps: hot set `200`, per-seed neighbors `50`,
  max hops `2`, max expansion nodes `25`.
- Dedupe by connection type and endpoint family before spending escalation
  budget.
- Let verified connections affect ceiling or edge-candidacy review, never
  current score, until calibrated.

## Rejected Or Deferred

Rejected for now:

- adding a large batch of near-synonym edge types;
- implementing a daemon;
- autonomous strong-model escalation;
- promoting generated candidate connections into graph truth.
- persisting raw user messages as attention seeds;
- running all-pairs background scans;
- allowing connectivity scores to bypass safety, evidence, or authority gates.

Deferred:

- `WorkflowPartRecord` schema;
- `workflow-part` recognizer;
- workflow assembly context pack;
- any new edge types such as `produces_input_for`, `substitutes_for`,
  `specializes`, `generalizes`, or `quarantines`;
- optional `incompatible_with`, only if later review proves it is distinct from
  `unsafe_composition_with`.

## Design Rule For Implementation

Before implementing background connections or workflow parts:

1. Re-confirm the edge registry at implementation time.
2. Map each proposed relation to an existing edge first.
3. Add a new edge only when an existing edge plus context tag cannot express the
   distinction.
4. Keep all generated connections candidate-only.
5. Keep source/private data out of tracked public-ready evidence.
6. Require human/provider gates before scheduled background scans or model
   escalation.
7. Define every score and threshold with methodology version, inputs,
   normalization, caps, and uncertainty handling before use.
8. Dedupe families before budget allocation so repeated copies cannot consume
   the review queue.

## Remaining Human Decisions

- Should workflow parts be public-safe tracked records, private generated
  records, or both?
- Should the first implementation be same-repo/same-family only?
- What is the ceremony threshold for showing assembly suggestions in preflight?
- Which asset patterns are mature enough to become first workflow-part
  families?
- Should strong-model verification wait for Phase 4 provider/privacy gates?
- What precision target should trigger changing the default threshold from
  `0.70`?
