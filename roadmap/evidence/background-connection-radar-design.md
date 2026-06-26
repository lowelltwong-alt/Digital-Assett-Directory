# Background Connection Radar Design Evidence

## Decision

DAD now has a design for a "background thought" workflow:

```text
low-compute scout -> connection candidate -> bounded escalation packet -> high-intensity verifier -> human review
```

The design is documented in `docs/BACKGROUND_CONNECTION_RADAR.md`.

## Why It Exists

The goal is to find useful new connections between:

- current attention and recent interests;
- older cold-storage assets;
- orphan or weakly connected graph nodes;
- duplicate variants and semantic deltas;
- old lessons, workflows, and worktree archaeology signals.

When a candidate looks unusually connective, the system should escalate a small
bounded packet to a stronger verifier rather than spending heavy compute on
everything.

## Current Status

This is a design artifact only.

Not yet enabled:

- no daemon;
- no scheduler;
- no autonomous model calls;
- no source repo mutation;
- no promotion of generated graph edges;
- no GitHub scanning.

## Reusable Asset Pattern

Registered pattern:

- `background_connection_radar_system`

The pattern describes a two-speed connection discovery workflow with:

- attention seeds;
- cold-storage queues;
- cheap deterministic scout signals;
- escalation packets;
- high-intensity verification;
- multi-hop expansion maps;
- candidate-only human review.

## Fresh-Eyes Review

The design doc includes a Claude prompt. Claude should write independent review
to:

```text
roadmap/evidence/claude-background-connection-radar-review.md
```

After that, Codex and Claude designs can be synthesized into a bounded v1
experiment.

## Remaining Risks

- Weak associations can create noisy or misleading edges.
- Current attention can overweight recency and miss deeper older patterns.
- Cold-storage scans can become expensive without strict budgets.
- Strong-model escalation can leak sensitive context if packets are not bounded
  and redacted.
- Multi-hop expansion can feel insightful while amplifying a false first edge.

## Next Gate

Before implementation, choose:

- manual one-shot CLI only, or scheduled background job;
- deterministic-only scout, or small local model scout;
- whether strong-model verification waits for Phase 4 provider/privacy gates;
- escalation budget per run;
- schema fields for connection candidates and escalation packets.
