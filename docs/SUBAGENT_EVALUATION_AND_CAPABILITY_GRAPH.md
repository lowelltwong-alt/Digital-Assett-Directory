# Subagent Evaluation And Capability Graph

## Purpose

DAD records how bounded subagent attempts performed, what evidence supported the review,
and what should improve next time. It keeps execution attempts, reusable role profiles,
model claims, and nicknames separate. This prevents a useful run from becoming an
unsupported model leaderboard.

## Identity layers

1. A **role profile** describes a reusable mission and operating contract.
2. A **role profile revision** pins one exact prompt/tool-policy revision.
3. An **execution attempt** is one invocation. A retry is a new attempt.
4. A **runtime/model claim** is attributed metadata unless independently verified.
5. A nickname is display text only and is never an identity key.

Archaeological `worktree_attempt` rows are not execution attempts. They may enter an
unrated inventory, but they cannot receive performance scores without invocation and
review evidence.

## Rating contract

Attempt ratings use `registry/subagent-evaluation-methodology.json`. Every score exposes
its five dimensions, weights, evidence, limitations, evaluator relationship, and
confidence. Missing evidence is `insufficient_evidence`, not zero. A score applies only
to the attempt and cohort described by its record.

Parent-reconstructed summaries may carry an `parent_observational_rating` so useful
feedback remains visible, but those scores never count toward profile eligibility.
Only direct hashed evidence or verified independent hashed review can produce a
`rated_attempt` used by profile comparison.

Role-profile summaries require at least three comparable attempts. Default comparisons
require at least five attempts across two repositories or task families. Even then,
recommendations are candidate review rows. DAD never automatically changes agent routing.

## Consolidation decisions

The review queue may suggest `keep_both`, `consolidate_patterns`,
`promote_one_as_default`, `retain_as_specialist`, `supersede_after_review`, or
`insufficient_evidence`. Decisions consider capability overlap, complementary strengths,
correlated failures, context diversity, independent review counts, and counterevidence.
An aggregate score alone is insufficient.

Combining two role profiles creates a new composite candidate. It does not rewrite or
delete source profiles, attempts, evaluations, or failures. Promotion and supersession
require a separate verified human decision.

## Data flow

```text
repo review packet
  -> immutable role/attempt/evaluation intake
  -> schema and rubric replay validation
  -> processed attempt summaries
  -> candidate capability graph
  -> candidate consolidation review queue
  -> human decision overlay
```

Raw records use the active DAD data root. Processed graphs are rebuildable and carry
input, methodology, registry, builder, and graph hashes. Absolute private paths, prompts,
hidden reasoning, secrets, and source blobs do not belong in evaluation records.

## Red-team boundary

The graph cannot emit `better_than`, `recommended`, `approved_by`, `trusted`, inferred
`supersedes`, or any automatic keep/combine/promote action. Similarity and agreement are
discovery signals only. Failed, cancelled, interrupted, mixed, and corrected attempts are
retained so survivorship bias remains visible.
