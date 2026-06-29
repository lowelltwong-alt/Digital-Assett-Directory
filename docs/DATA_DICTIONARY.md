# Data Dictionary

## Core identity

| Field | Meaning | Authority |
|---|---|---|
| `asset_id` | Stable identifier for a logical asset at a source identity and logical path. | Directory contract |
| `revision_id` | Identifier for one content revision of an asset. | Derived from asset identity + content hash |
| `source_id` | Registered local or GitHub source adapter identity. | Source configuration |
| `parent_asset_id` | Container/repository relationship. | Observed source hierarchy |
| `logical_path` | Path using a source alias rather than exposing an absolute local path. | Normalized observation |
| `content_hash` | Scanner revision identity hash. It may be exact content identity or metadata-derived when content was intentionally not read. | Observed evidence |
| `metadata_fingerprint` | Fast fingerprint of observable metadata such as size, timestamps, and platform attributes. | Derived observation |
| `content_sha256` | Exact SHA-256 of file bytes when bytes were safely read; otherwise `null`. | Exact observed evidence when present |
| `source_provenance` | Source adapter, path/repo context, scanner, and authority boundary. | Normalized observation |

## Identity layers

| Record | Meaning | Authority |
|---|---|---|
| `AssetChunkRecord` | Deterministic token-shingle or metadata chunk tied to one asset revision. | Generated candidate evidence |
| `DuplicateClusterRecord` | Exact-content or near-duplicate candidate group of assets. | Generated candidate evidence |
| `AssetDeltaRecord` | Pairwise exact/near duplicate delta summary and shared/one-sided chunk hashes. | Generated candidate evidence |
| `SemanticEvolutionRecord` | Family-level candidate that separates behavior-relevant version change from formatting, path, metadata, or fixture-copy noise. | Generated candidate evidence |
| `identity_layer` | One step in the Asset Identity And Similarity Ladder. Controlled by `registry/identity-layer-registry.json`. | Directory contract |
| `exact_duplicate_of` edge | Assets share the same non-empty exact `content_sha256`. | Generated candidate relationship |
| `near_duplicate_of` edge | Assets share enough deterministic token-shingle MinHash similarity to warrant review. | Generated candidate relationship |
| `contained_in` edge | Most source shingles appear inside the target asset even when symmetric overlap is lower. | Generated candidate relationship |
| `has_delta_candidate` edge | A generated delta record exists for the asset pair. | Generated candidate relationship |
| `semantic_change_score` | Deterministic 0-1 strength of behavior-relevant evolution under the current methodology. | Candidate routing signal |
| `noise_score` | Deterministic 0-1 strength of copy, path, formatting, metadata, or fixture-lineage noise. | Candidate routing signal |
| `evolution_grade` | Insufficient, none, cosmetic, minor, moderate, major, or breaking semantic evolution. | Candidate routing signal |
| `noise_class` | Exact copy, format/order noise, path/metadata noise, fixture-lineage noise, mixed signal, or insufficient evidence. | Candidate routing signal |

## Discovery and use

| Field | Meaning |
|---|---|
| `asset_type` | Form: code, schema, ontology, lesson, evaluation, workflow, and so on. |
| `tags` | Broad topics and facets used for routing. |
| `capabilities` | What the asset can provide. IDs come from `registry/capability-registry.json`. |
| `needs` | Missing dependency or condition that may activate the asset. IDs come from `registry/need-registry.json`. |
| `outcomes` | Future results the asset may support. |
| `entrypoints` | Files a new human or AI should read first. |
| `value_score` | 0–100 review-priority heuristic; not proof of truth or business value. |
| `value_components` | Exposed score dimensions used to produce `value_score`. |
| `value_components.content_role` | Generated deterministic code-role or workflow-subtype score component under the current methodology. |
| `metadata.asset_patterns` | File-level generated candidate pattern IDs, such as evaluation harness or model/algorithm hints. |
| `metadata.pattern_evidence` | Evidence terms that caused an asset pattern hint. |
| `metadata.composite_patterns` | Repository or bundle-level generated candidate patterns inferred from connected child assets. |
| `metadata.composite_asset_hint` | Candidate member IDs, child count, and authority note for a possible composite asset. |
| `metadata.instance_of_asset_ids` | For use/run/deployment assets, the assets instantiated together. |
| `metadata.workflow_steps` | For workflow assets, ordered or named steps when known. |
| `metadata.chunk_text` | Redacted extracted text used for deterministic token-shingle chunking. Generated output only. |

## Workflow-part candidates

| Record / field | Meaning | Authority |
|---|---|---|
| `WorkflowPartRecord` | Generated candidate for a recombinable sub-unit beneath an asset pattern, such as a validator, contract, gate, runner, prompt part, human gate, learning signal, boundary map, calibration gate, or quarantine gate. | Generated candidate evidence |
| `part_type` | Controlled part role from `registry/workflow-part-type-registry.json`. | Directory contract |
| `asset_pattern_id` | Existing high-level asset pattern this part supports; the part does not replace the pattern registry. | Generated candidate relationship |
| `inputs` / `outputs` / `preconditions` / `side_effects` | Empty in deterministic v1 unless declared in structured metadata or reviewed by a human. | Candidate constraint |
| `maturity` | Recognized, validated, reused, or reviewed; v1 defaults to recognized and does not claim validation merely because a test-like file exists. | Candidate routing signal |
| `methodology_version` | The recognition method and formulas used to produce the candidate. Current value: `workflow-part-recognition-v1`. | Directory contract |
| `WorkflowPartReviewRecord` | Human-label wrapper around generated workflow-part candidates. | Human calibration evidence after label entry |
| `usefulness` | Whether the detected part is useful as a reusable review/planning surface: `useful`, `not_useful`, or `unsure`; default `unreviewed`. | Human calibration label |
| `safety` | Whether the candidate can be safely considered for review use: `safe`, `unsafe`, or `needs_more_review`; default `unreviewed`. | Human calibration label |
| `specificity` | Whether the part is at the right abstraction level, too broad, too narrow, or unsure. | Human calibration label |
| `dataflow_completeness` | Whether v1's empty or declared inputs/outputs/side effects are adequate for now or missing something important. | Human calibration label |
| `decision` | Review-use decision: accept for review use, reject, defer, or require human gate. This does not authorize source mutation, score influence, or preflight surfacing. | Human calibration label |

## Learning-loop candidates

| Record / field | Meaning | Authority |
|---|---|---|
| `LearningLoopRecord` | Generated candidate linking expectation/evaluation evidence, exception signals, adaptation proposals, human gates, and promotion targets. | Generated candidate evidence |
| `learning_loop_type` | Candidate loop shape: governed learning, asset-use feedback, evaluation-promotion, or exception-to-adaptation. | Directory contract |
| `source_asset_ids` | Assets that provided evidence for the loop. | Generated relationship evidence |
| `expectation_source` | Asset or text evidence that defines expected behavior or evaluation criteria. | Generated candidate summary |
| `exception_signal` | Asset or text evidence that something failed, drifted, or needs learning. | Generated candidate summary |
| `adaptation_proposal` | Candidate improvement, rule, patch, or workflow update. | Generated candidate summary |
| `review_gate` | Human or governance gate required before promotion. | Directory contract |
| `promotion_target` | Rule, validator, workflow, schema, or registry that could change after review. | Generated candidate summary |

## Contextual archaeology

| Record / field | Meaning | Authority |
|---|---|---|
| `ContextTagRecord` | Controlled context label with applicability and misapplication risk. | Directory contract |
| `WorktreeAttemptRecord` | Candidate grouping for a repository, worktree, temp repo, or archive attempt. | Generated candidate evidence |
| `RepoTimelineEventRecord` | Bounded local history, changelog, CI, or repo-learning event. | Generated candidate evidence |
| `ChangePatternRecord` | Co-change, repeated edit, variant, late stabilizer, or changelog theme candidate. | Generated candidate evidence |
| `FailureSignalRecord` | Failure-like evidence such as tests, error terms, TODO/FIXME, reverts, drift, or missing gates. | Generated candidate evidence |
| `RootCauseHypothesisRecord` | Reviewable hypothesis explaining why repeated failure or rework may have happened. | Generated candidate evidence |
| `CounterfactualLessonRecord` | Context-bound lesson candidate with applicability limits and a better-order hypothesis. | Generated candidate evidence |
| `RepoLearningEventRecord` | Opt-in downstream repo event captured before, during, after, or during review of work. | Source repo opt-in candidate evidence |
| `LearningRuleRecord` | Reviewed deterministic rule surfaced by preflight and acknowledged by midflight. | Reviewed operating constraint |
| `applies_when` | Conditions under which a lesson may be useful. | Candidate constraint |
| `does_not_apply_when` | Conditions under which a lesson should not be applied. | Candidate constraint |
| `danger_if_misapplied` | Explicit warning for stripping a lesson from context. | Candidate safety constraint |
| `danger_if_ignored` | Explicit warning for ignoring a reviewed learning rule during matching work. | Reviewed operating constraint |

## Governance and time

| Field | Meaning |
|---|---|
| `lifecycle_state` | Discovered, candidate, reviewed, active, dormant, stale, deprecated, archived, missing, quarantined, or tombstoned. |
| `freshness_status` | Current, watch, stale, or unknown relative to the type-specific threshold. |
| `sensitivity` | Public, internal, confidential, restricted, or unknown. |
| `trust_zone` | Source-owned, generated candidate, reviewed candidate, verified, or other registered trust posture. |
| `confidence` | Backward-compatible label for heuristic strength in normalized metadata; not calibrated P(useful) and not confidence that the source claim is true. |
| `metadata.instance_class` | Generated scoring class such as source, archive, generated output, temp fixture, worktree copy, or cache/OS junk. |
| `metadata.information_content_class` | Generated content class such as OS junk, empty marker, empty file, metadata-only observation, extracted content, binary metadata, or content-bearing file. |
| `metadata.information_content` | Generated bounded text/token/semantic evidence used by the current score methodology. |
| `metadata.content_profile` | Generated bounded line, symbol, import, code-role, and workflow-subtype evidence for scoring and review routing. |
| `metadata.score_methodology` | Methodology version, inputs, normalization, uncertainty posture, and candidate-only status for the current calculated score. |
| `metadata.score_discount_reasons` | Generated reasons for multiplicative score discounts; candidate-only and not source truth. |
| `metadata.heuristic_strength` | Preferred label for uncalibrated confidence-like values until human labels support probability calibration. |
| `first_seen_at` / `last_seen_at` | Catalog observation times. |
| `modified_at` | Source-reported modification time when available. |

## Relationship evidence

Every edge records `edge_type`, source and target IDs, method, confidence, evidence, scan identity, creation time, and review status. A generated edge is a retrieval and review candidate; it does not transfer authority.
