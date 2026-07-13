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

## Declared role directory

Reusable skills may expose role contracts before the roles have any execution
history. Those declarations live in explicitly allowlisted, schema-validated
`subagent_pack` files and project into
`processed/agents/subagent-role-directory.json`. They do not enter the
attempt-first capability graph as role revisions and do not receive synthetic
attempts, prompt hashes, capability edges, ratings, or zero scores.

The directory and evaluation graph remain separate evidence classes:

```text
registered skill -> declared role catalog (candidate / possibly untried)
immutable attempt packet -> evaluated role revision graph
exact declared evaluated_role_revision_ids -> identity-checked directory summary
```

The join never uses role names, token similarity, declared capabilities, model
family, or graph proximity. Directory search is read-only relevance retrieval:
exact identity, exact declared capability/search phrase, all query tokens, then
stable lexical order. It is not a quality ranking or dispatch authority.

## Red-team boundary

The graph cannot emit `better_than`, `recommended`, `approved_by`, `trusted`, inferred
`supersedes`, or any automatic keep/combine/promote action. Similarity and agreement are
discovery signals only. Failed, cancelled, interrupted, mixed, and corrected attempts are
retained so survivorship bias remains visible.


## Integrity and Cross-Domain Improvement Layer

The post-hoc attempt score remains bounded observational evidence. It is not
self-improvement authority. The integrity layer adds three separate contracts:

- registry/subagent-evaluation-profile-registry.json defines the universal
  learning loop, explicit context-bounded domain overlays, intervention layers,
  preserve-simple policy, and the ban on cross-domain score comparison;
- schemas/subagent-self-assessment.schema.json stores a criterion-level
  prediction whose runtime receipt can prove it arrived before the outcome; and
- schemas/subagent-evaluation-integrity-report.schema.json validates the
  categorical read-only meta-review.

Commands:

    asset-dir subagents profiles
    asset-dir subagents self-assess --packet <prediction.json>
    asset-dir subagents integrity-review
    asset-dir subagents integrity-review --profile dad:evaluation-profile:simple-deterministic

The integrity command does not write a report cursor, copy source scores, or
rank agents. It checks self-assessment timing, independent identity, model and
parent-session lineage, reciprocal review cycles, missing blindness, missing
prompt lineage, the difference between hash integrity and evidence truth,
profile fit, domain-expert requirements, routing proportionality, and candidate
fault layers.

Identity-verified independent review is still integrity-incomplete when
blindness, environment replay, domain qualification, prompt lineage, or held-out
meta-evaluation is absent. Missing evidence blocks clearance; it does not become
a zero or a reassuring average.

A simple deterministic role may be nominated as no_change_freeze_candidate only
from a comparable cohort under the explicit simple profile. The nomination
remains human-gated and requires held-out shadow and non-regression evidence.
Extra intelligence should be placed in a workflow wrapper or downstream
specialist when changing the simple role would add cost, latency, or instability.
