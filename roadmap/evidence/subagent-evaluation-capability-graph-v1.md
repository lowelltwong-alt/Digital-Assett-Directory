# Subagent Evaluation Capability Graph V1 Decision

Risk tier: **high**. Agent routing and comparative scores can create false authority.

## Options

- **Attempt-first evidence graph (selected):** immutable attempts, pinned rubric,
  explicit counterevidence, candidate recommendations, and a human decision overlay.
- **Model-name leaderboard (rejected):** conflates model, prompt, tools, task, and runtime;
  hides failures and encourages unsupported routing.
- **Automatic duplicate merging (rejected):** destroys lineage and can combine agents with
  complementary strengths or correlated blind spots.

## Premortem

- Nicknames accidentally become identities.
- Reconstructed records look complete.
- Rubric edits silently change historical scores.
- Parent/self reviews count as independent votes.
- High averages conceal a failed safety gate.
- Similar roles are merged before enough cross-context evidence exists.
- Only successful attempts reach DAD.

## Controls

- Separate role revision, attempt, evaluation, model claim, and display label.
- Pin rubric hashes and replay the score formula at ingest and graph build.
- Preserve terminal failures, missing fields, limitations, and counterevidence.
- Require minimum sample/diversity thresholds and human review.
- Make graph and review-queue outputs candidate-only and rebuildable.
- Treat unknown or archaeological attempts as unrated inventory.

## Rollback and kill criteria

Disable graph/recommendation generation while preserving raw records if duplicate IDs
accept different bytes, historical score replay changes, missing evidence becomes zero,
an unknown edge is emitted, a graph output makes an authority claim, or routing changes
without a verified human decision.

## Review history

- Claude Opus produced no verdict before a 15-minute ceiling; the attempt is retained as
  failed and unscored. Claude Sonnet could not start because the provider session limit
  was reached; it is also retained as failed and unscored.
- Sol post-implementation reviewer Lorentz rejected V1 with seven P1 findings: duplicate
  review inflation, non-replayable seed evidence, non-atomic intake, mutable-rubric replay,
  scored missing-evidence states, unvalidated unrated payloads, and an unresolved graph
  logical prefix. It also found model-claim collapse and missing navigation routes.
- The remediation adds distinct-attempt/reviewer thresholds, packet-local hashed evidence,
  a global intake lock plus immutable packet receipt, versioned rubric snapshots,
  conditional score/evidence schemas, unrated privacy validation, graph-prefix/freshness
  support, full model-claim identity, and front-door/TOC/manifest routing.
- A second Sol review found that independence was still self-attested, privacy scanning
  missed secrets and generic absolute paths, the local development ledger still pinned the
  prior rubric hash, reconstructed ratings were self-referential, and navigation timestamps
  disagreed. The final remediation requires a completed evaluator attempt plus verified
  actor/evidence linkage, applies DAD secret patterns and absolute-path rejection, rebuilds
  the ignored development ledger from its corrected immutable packet, labels reconstructed
  scores `parent_observational_rating`, and aligns navigation freshness metadata.
- Final Sol closure review returned `APPROVE` after the generic absolute-path detector
  rejected Windows, UNC, and POSIX paths while preserving `source://`, `https://`, and
  ordinary relative references.

The seed scores remain parent-reviewed observations with reduced confidence and explicit
limitations. They are not `rated_attempt` evidence and do not satisfy independent-evidence
thresholds, so every role profile
remains `attempt_evidence_only` and every consolidation row remains
`insufficient_evidence`.
