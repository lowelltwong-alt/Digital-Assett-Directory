# Phase 4 Semantic Enrichment Evidence

Status: boundary deferred under a conservative local-only
semantic-enrichment boundary.

Date: 2026-06-26

## Boundary Decision

Phase 4 does not approve external embeddings, external model enrichment, raw
source-content export, raw chat persistence, or provider-side retention.

The approved Phase 4 surface is:

- deterministic local content profiles;
- deterministic identity, chunk, MinHash, graph, and score evidence;
- generated candidate reports and metadata;
- human-reviewed calibration evidence.

Any later embedding provider, model enrichment provider, retention policy, or
raw-content transfer remains a new human gate. This evidence records the safe
boundary and the deterministic evaluation result, but it does not claim that
external embeddings or AI-assisted enrichment have been delivered.

## Gate Coverage

| Gate | Status | Evidence |
|---|---|---|
| `phase-4-provider-privacy-boundary-approved` | Verified for local-only/no-external-provider boundary | `docs/SECURITY_AND_PRIVACY.md`, `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`, `registry/identity-layer-registry.json` |
| `phase-4-deterministic-baseline-retained` | Verified | `docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md`, `roadmap/evidence/phase-2.5-content-aware-scoring.md` |
| `phase-4-evaluation-harness-benefit-shown` | Verified | `roadmap/evidence/phase-2.5-content-aware-scoring.md`, `processed/reports/phase_2_5_score_delta_validation.md`, `processed/reports/phase_2_5_score_delta_validation.json` |
| `phase-4-generated-metadata-candidate-status` | Verified | `AI_FRONT_DOOR.md`, `AGENTS.md`, `docs/ROADMAP_EXECUTION.md`, `roadmap/evidence/background-connection-radar-v1-implementation.md` |

## Measurable Benefit

The Phase 2.5 score-delta validation is the Phase 4 evaluation harness for this
conservative slice. It compares the old content-blind score with the
content-aware deterministic profile score against the same 100 human-reviewed
Phase 2 records.

Final recorded result:

- reviewed rows matched: `100 / 100`;
- reviewed `too_high` examples: `18 / 18` moved from medium to low;
- reviewed `too_low` examples: `28 / 28` moved from low to medium;
- reviewed `about_right` examples: `54 / 54` stayed in the same band;
- about-right churn: `0`;
- validation status: `passed`.

This proves benefit for deterministic content-aware score routing. It does not
prove that external embeddings or model-enriched summaries are safe or better.

## Candidate-Only Controls

- Generated profiles, scores, edges, proposals, background candidates, and
  reports remain candidate evidence.
- Source repositories remain authoritative for their own files and meaning.
- Embeddings remain deferred in the identity ladder until privacy, license,
  provider, retention, and evaluation gates are separately approved.
- Verified connections may inform ceiling/upside review or future candidate
  edges; they do not directly update current value scores.

## Red-Team And Premortem

Failure mode: a future agent treats this phase as blanket permission to turn on
embeddings or LLM enrichment.

Mitigation: this evidence explicitly approves only the local deterministic
enrichment boundary and says external providers remain gated.

Failure mode: the Phase 2.5 harness is over-generalized to documents, media, or
private row-level corpora.

Mitigation: the recorded benefit is for the reviewed code/workflow/schema/test
and configuration target surface. Document/media enrichment still needs a
separate calibration set.

Failure mode: generated candidate metadata is mistaken for source truth.

Mitigation: front-door, roadmap, identity-ladder, and background-radar evidence
all preserve candidate-only semantics.

## Remaining Risks

- The measured benefit is strong for the Phase 2.5 target surface, not for all
  possible asset families.
- External embedding/provider selection is still unresolved and must not be
  inferred from this phase.
- If the repository later becomes public, provider/privacy review must be
  repeated with the public/private split in mind.

## Result

Phase 4 is `boundary_deferred`: the deterministic enrichment boundary is
documented, while external embeddings, external model calls, scheduled
enrichment, and promotion of generated metadata to truth remain undelivered and
separately gated.
