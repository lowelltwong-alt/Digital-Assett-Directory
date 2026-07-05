# Knowledge Graph Model

## Node families

- digital assets: repositories, files, schemas, workflows, tests, datasets, prompts, skills, agents, decisions, lessons, research, algorithms, models, forecasters, adapters, and composite bundles;
- composite assets: repositories, workflows, bundles, clusters, and systems made from multiple connected assets;
- asset instances: observed uses, runs, deployments, or task-specific combinations of assets;
- revisions: content-specific observations;
- activities: scans, builds, validations, research runs;
- agents: human or software actors when known;
- alerts, activation triggers, and synergy candidates.

## Edge discipline

Every generated edge carries:

- edge type;
- method;
- confidence;
- evidence;
- scan ID;
- review status.

DAD's 9-layer address model is complementary to this edge model. The address
model is a compact coordinate system for where an object belongs, what layer of
meaning it occupies, and which authority boundary governs it. Graph edges model
relationships between addressed objects. Do not use an address as proof of a
relationship, and do not use an edge as a replacement for provenance, layer
placement, or source authority.

A `related_to` edge means bounded IDF-weighted token similarity, not sameness. A
`semantically_similar_to` edge is reserved for a later approved semantic layer. A
`plays_same_architecture_role_as` edge means candidate role similarity, not content
equivalence. A `complements` edge means a plausible combination, not an implemented
integration. A `satisfies_need` edge means lexical/metadata evidence that one capability
may address another asset's need. An `exact_duplicate_of` edge means exact content
identity only, not canonical preference. A `near_duplicate_of` edge means deterministic
token-shingle MinHash similarity sufficient for review, not proof that one asset should
replace another. A `contained_in` edge means the source asset's shingles are mostly
present inside the target asset.

Asset-family recognition may also emit candidate edges such as `routes_to`,
`handles_form`, `has_gold_set`, `has_review_packet`, `produces_learning_signal`,
`requires_human_gate`, `composes_with`, `unsafe_composition_with`,
`contaminates_if_default`, and `supports_but_cannot_override`. These edges help
future agents inspect workflows, learning loops, and composition risks. They do not
authorize implementation, source mutation, or source-authority override.

Workflow-part recognition sits beneath asset-family recognition. A
`WorkflowPartRecord` is a generated candidate for a recombinable sub-unit such
as a validator, contract, gate, runner, prompt part, human gate, learning
signal, boundary map, calibration gate, or quarantine gate. It references an
existing asset pattern instead of replacing the pattern registry. V1 records
only deterministic metadata and sanitized asset-id references; inputs, outputs,
preconditions, side effects, failure modes, and composition affordances remain
empty unless declared, structured, or human-reviewed.

Workflow-part recomposition reuses existing graph vocabulary first. The narrow
new edge types are `produces_input_for`, `substitutes_for`, `specializes`,
`generalizes`, and `quarantines`. These are candidate planning signals only.
They do not prove that two parts are safe to compose, do not select a canonical
variant, and do not cross source-authority boundaries without human review.

## Composite Asset Recognition

A digital asset may be a single file, but high-leverage assets are often composites:

- a whole repository with workflows, tests, schemas, and governance;
- an AI workflow made from agents, skills, prompts, tools, memory, and handoff rules;
- an evaluation system made from tests, golden cases, schemas, and labels;
- a model or algorithm system made from code, data, assumptions, backtests, and reports;
- a knowledge-graph system made from ontology, taxonomy, extraction, retrieval, and review loops;
- a cluster of near-duplicate or variant assets that needs a delta review;
- an instance where several assets were used together for a task.

Scanners should recognize these as generated candidates by combining weak signals instead of
using one brittle filename rule. Useful signals include asset types, path terms, tags,
capabilities, needs, outcomes, entrypoints, co-occurrence inside a repo, and explicit
feedback markers such as `DAD_ASSET_USE_FEEDBACK_V1`.

The pattern registry is `registry/asset-pattern-registry.json`. Pattern matches stay in
metadata as candidate evidence until human review promotes a bundle, cluster, workflow, or
instance.

## Duplicate and variant handling

When two assets are nearly the same because similar work was recreated in different repos,
preserve both source records until a human review decides the relationship. Do not delete one
asset or double-count both as independent value by default.

Use generated candidate edges where they fit:

- `related_to` with evidence subtype `near_duplicate` when assets appear substantially similar;
- `exact_duplicate_of` when non-empty exact `content_sha256` matches;
- `near_duplicate_of` when deterministic token-shingle MinHash similarity exceeds the configured threshold;
- `contained_in` when deterministic shingle containment is high but symmetric similarity is lower;
- `has_delta_candidate` when a pairwise delta record exists;
- `supersedes` when a reviewed newer asset replaces an older one;
- `derived_from` when provenance shows one asset was copied or adapted from another;
- `complements` when overlap exists but each asset contributes a different useful piece.

These edges implement part of the Asset Identity And Similarity Ladder. Hashes identify
exact versions; chunk hashes and deltas locate overlap and change; graph edges make role,
workflow, dependency, and reuse relationships discoverable. No one layer proves asset
value, authority, or canonical status by itself.

If the relationship is not yet reviewed, record it as candidate evidence or calibration notes
and propose a bounded consolidation experiment. Future registry changes may add explicit
`merge_candidate` edge types, but those should be reviewed before they become source-of-truth
graph semantics.

For clusters of very close assets, prefer generated `duplicate_clusters.jsonl` and
`deltas.jsonl` records over a winner-take-all decision. The delta should preserve:

- the shared core across the cluster;
- per-asset strengths;
- neutral differences for different roles or contexts;
- weaker or obsolete parts;
- missing evidence needed for fair comparison;
- the proposed merge, variant, or supersession experiment.

## Provenance mapping

The ontology aligns conceptually with W3C PROV-O:

- assets and revisions are `prov:Entity`-like objects;
- scans and transformations are `prov:Activity`-like objects;
- people and software tools are `prov:Agent`-like objects;
- derivation, generation, use, and attribution should remain traceable.

## Version and staleness

Staleness is type-specific and reviewable. A ten-year-old decision may remain valid; a six-month-old provider integration may be stale. The catalog records both age and the reason for the freshness classification.
