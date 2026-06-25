from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

ConfidenceLabel = Literal["low", "medium", "high"]


class AssetRecord(BaseModel):
    schema_version: str = "0.1.0"
    asset_id: str
    revision_id: str
    source_id: str
    parent_asset_id: str | None = None
    source_kind: Literal["local", "github", "lesson", "research", "generated"]
    asset_type: str
    title: str
    description: str = ""
    logical_path: str
    uri: str = ""
    content_hash: str = ""
    metadata_fingerprint: str = ""
    content_sha256: str | None = None
    size_bytes: int = 0
    modified_at: str | None = None
    first_seen_at: str
    last_seen_at: str
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    lifecycle_state: str = "discovered"
    freshness_status: Literal["current", "watch", "stale", "unknown"] = "unknown"
    sensitivity: Literal["public", "internal", "confidential", "restricted", "unknown"] = "unknown"
    trust_zone: str = "source_owned"
    value_score: float = 0.0
    value_components: dict[str, float] = Field(default_factory=dict)
    confidence: ConfidenceLabel = "medium"
    source_provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeRecord(BaseModel):
    schema_version: str = "0.1.0"
    edge_id: str
    edge_type: str
    source_asset_id: str
    target_asset_id: str
    method: str
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class AssetChunkRecord(BaseModel):
    schema_version: str = "0.1.0"
    chunk_id: str
    asset_id: str
    revision_id: str
    source_id: str
    logical_path: str
    chunk_index: int = Field(ge=0)
    chunk_kind: Literal["text", "metadata"]
    content_hash: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    text_excerpt: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class DuplicateClusterRecord(BaseModel):
    schema_version: str = "0.1.0"
    cluster_id: str
    cluster_type: Literal["exact_content_duplicate", "near_duplicate_candidate"]
    asset_ids: list[str] = Field(min_length=2)
    methods: list[str] = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class AssetDeltaRecord(BaseModel):
    schema_version: str = "0.1.0"
    delta_id: str
    left_asset_id: str
    right_asset_id: str
    delta_type: Literal["exact_duplicate", "near_duplicate_candidate", "containment_candidate"]
    summary: str = Field(min_length=1)
    shared_chunk_hashes: list[str] = Field(default_factory=list)
    left_only_chunk_hashes: list[str] = Field(default_factory=list)
    right_only_chunk_hashes: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class SemanticEvolutionRecord(BaseModel):
    schema_version: str = "0.1.0"
    evolution_id: str
    family_key: str = Field(min_length=1)
    asset_type: str = ""
    source_asset_ids: list[str] = Field(min_length=1)
    representative_paths: list[str] = Field(default_factory=list)
    path_class_counts: dict[str, int] = Field(default_factory=dict)
    raw_version_count: int = Field(ge=0)
    normalized_version_count: int = Field(ge=0)
    semantic_version_count: int = Field(ge=0)
    evolution_grade: Literal[
        "insufficient_evidence",
        "none",
        "cosmetic_metadata",
        "minor_semantic",
        "moderate_semantic",
        "major_semantic",
        "breaking_semantic",
    ]
    noise_class: Literal[
        "insufficient_evidence",
        "exact_copy",
        "format_or_order_noise",
        "path_or_metadata_noise",
        "fixture_lineage_noise",
        "mixed_signal",
    ]
    semantic_change_score: float = Field(ge=0, le=1)
    noise_score: float = Field(ge=0, le=1)
    methodology_version: str = "semantic-evolution-grading-v1"
    grading_summary: str = Field(min_length=1)
    structural_changes: dict[str, Any] = Field(default_factory=dict)
    current_instance_score_guidance: str = Field(min_length=1)
    family_value_guidance: str = Field(min_length=1)
    graph_edge_suggestions: list[str] = Field(default_factory=list)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class SynergyRecord(BaseModel):
    synergy_id: str
    asset_ids: list[str] = Field(min_length=2, max_length=3)
    score: float = Field(ge=0, le=1)
    confidence: ConfidenceLabel
    shared_outcomes: list[str] = Field(default_factory=list)
    complementary_capabilities: list[str] = Field(default_factory=list)
    needs_covered: list[str] = Field(default_factory=list)
    missing_parts: list[str] = Field(default_factory=list)
    integration_hypothesis: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ActivationTrigger(BaseModel):
    trigger_id: str
    asset_id: str
    trigger_type: str
    condition: str
    missing_parts: list[str] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)
    status: Literal["watching", "fired", "dismissed", "resolved"] = "watching"


class AlertRecord(BaseModel):
    schema_version: str = "0.1.0"
    alert_id: str
    created_at: str
    alert_type: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    title: str
    description: str = ""
    asset_ids: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str
    status: Literal["open", "acknowledged", "resolved", "dismissed"] = "open"
    scan_id: str


class LessonRecord(BaseModel):
    schema_version: str = "0.1.0"
    lesson_id: str
    created_at: str
    repository: str
    task: str
    agent: str
    model: str | None = None
    summary: str
    lessons: list[str] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    tests_not_run: list[str] = Field(default_factory=list)
    discoveries: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    reusable_patterns: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    review_status: Literal["auto_captured_unreviewed", "candidate", "reviewed", "rejected"] = (
        "candidate"
    )
    session_id: str | None = None


class LearningRuleRecord(BaseModel):
    schema_version: str = "0.1.0"
    rule_id: str
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    trigger_terms: list[str] = Field(default_factory=list)
    trigger_path_patterns: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(min_length=1)
    required_actions: list[str] = Field(min_length=1)
    danger_if_ignored: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    enforcement_level: Literal["surface", "require_ack", "human_gate"] = "surface"
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "reviewed"


class HandoffRecord(BaseModel):
    schema_version: str = "0.1.0"
    handoff_id: str
    session_id: str
    created_at: str
    repository: str
    agent: str
    task: str
    summary: str
    files_changed: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    tests_not_run: list[str] = Field(default_factory=list)
    confirmed: list[str] = Field(default_factory=list)
    inferred: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    review_status: Literal["auto_captured_unreviewed", "candidate", "reviewed"] = "candidate"


class CapabilityRecommendation(BaseModel):
    recommendation_id: str
    kind: Literal["skill", "agent", "swarm", "research"]
    name: str
    rationale: str
    evidence_asset_ids: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    suggested_roles: list[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ProposalRecord(BaseModel):
    schema_version: str = "0.1.0"
    proposal_id: str
    proposal_engine: Literal["bottom_up_self_proposal", "top_down_orchestration"]
    proposal_type: Literal[
        "satisfies_need",
        "strengthens_capability",
        "activates_orphan",
        "reduces_risk",
        "adds_test",
        "documents",
        "bundles_assets",
        "research_missing_part",
    ]
    source_asset_ids: list[str] = Field(min_length=1)
    target_asset_ids: list[str] = Field(default_factory=list)
    need_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    smallest_bounded_experiment: str = Field(min_length=1)
    expected_benefit: str = ""
    known_risks: list[str] = Field(default_factory=list)
    authority_boundary: str = Field(min_length=1)
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    estimated_review_cost: Literal["low", "medium", "high"] = "medium"
    estimated_integration_cost: Literal["low", "medium", "high"] = "medium"
    safety_flags: list[str] = Field(default_factory=list)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"
    generated_at: str
    scan_id: str


class ProposalReviewRecord(BaseModel):
    schema_version: str = "0.1.0"
    review_id: str
    sample_id: str
    proposal_id: str
    proposal_engine: Literal["bottom_up_self_proposal", "top_down_orchestration"]
    reviewer: str = ""
    reviewed_at: str | None = None
    usefulness: Literal["unreviewed", "useful", "not_useful", "unsure"] = "unreviewed"
    safety: Literal["unreviewed", "safe", "unsafe", "needs_more_review"] = "unreviewed"
    novelty: Literal["unreviewed", "novel", "already_known", "unsure"] = "unreviewed"
    actionability: Literal["unreviewed", "actionable", "not_actionable", "unsure"] = "unreviewed"
    decision: Literal["pending", "accept_candidate", "reject_candidate", "defer"] = "pending"
    notes: str = ""
    false_positive_reason: str = ""
    false_negative_note: str = ""
    useful_example_note: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class LearningLoopRecord(BaseModel):
    schema_version: str = "0.1.0"
    learning_loop_id: str
    learning_loop_type: Literal[
        "governed_learning_loop",
        "asset_use_feedback_loop",
        "evaluation_promotion_loop",
        "exception_to_adaptation_loop",
    ]
    source_asset_ids: list[str] = Field(min_length=1)
    expectation_source: str = Field(min_length=1)
    exception_signal: str = Field(min_length=1)
    adaptation_proposal: str = Field(min_length=1)
    review_gate: str = Field(min_length=1)
    promotion_target: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    authority_boundary: str = Field(min_length=1)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ContextTagRecord(BaseModel):
    schema_version: str = "0.1.0"
    context_tag_id: str
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(default_factory=list)
    risk_if_misapplied: str = Field(min_length=1)


class WorktreeAttemptRecord(BaseModel):
    schema_version: str = "0.1.0"
    attempt_id: str
    attempt_kind: Literal["repository", "worktree", "temp", "archive"]
    repo_lineage_key: str = Field(min_length=1)
    attempt_path: str = Field(min_length=1)
    task_hint: str = ""
    branch_name: str = ""
    source_asset_ids: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(min_length=1)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class RepoTimelineEventRecord(BaseModel):
    schema_version: str = "0.1.0"
    timeline_event_id: str
    repository_path: str = Field(min_length=1)
    event_type: Literal[
        "commit",
        "merge",
        "revert",
        "file_change",
        "changelog",
        "ci_artifact",
        "learning_event",
    ]
    occurred_at: str
    asset_ids: list[str] = Field(default_factory=list)
    changed_paths: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    context_tags: list[str] = Field(default_factory=list)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ChangePatternRecord(BaseModel):
    schema_version: str = "0.1.0"
    change_pattern_id: str
    pattern_type: Literal[
        "co_change",
        "repeated_edit",
        "variant_file",
        "late_stabilizer",
        "changelog_theme",
    ]
    asset_ids: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    context_tags: list[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class FailureSignalRecord(BaseModel):
    schema_version: str = "0.1.0"
    failure_signal_id: str
    signal_type: Literal[
        "test_failure",
        "error_word",
        "todo_fixme",
        "revert",
        "drift",
        "missing_gate",
    ]
    asset_ids: list[str] = Field(default_factory=list)
    signal_terms: list[str] = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    context_tags: list[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class RootCauseHypothesisRecord(BaseModel):
    schema_version: str = "0.1.0"
    root_cause_id: str
    hypothesis: str = Field(min_length=1)
    evidence_asset_ids: list[str] = Field(default_factory=list)
    source_events: list[str] = Field(min_length=1)
    context_tags: list[str] = Field(min_length=1)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(min_length=1)
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    authority_boundary: str = Field(min_length=1)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class CounterfactualLessonRecord(BaseModel):
    schema_version: str = "0.1.0"
    lesson_candidate_id: str
    lesson_candidate: str = Field(min_length=1)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(min_length=1)
    danger_if_misapplied: str = Field(min_length=1)
    counterfactual_better_order: list[str] = Field(min_length=1)
    evidence_asset_ids: list[str] = Field(default_factory=list)
    source_events: list[str] = Field(min_length=1)
    context_tags: list[str] = Field(min_length=1)
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    authority_boundary: str = Field(min_length=1)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class RepoLearningEventRecord(BaseModel):
    schema_version: str = "0.1.0"
    event_id: str
    repository: str = Field(min_length=1)
    stage: Literal["before_work", "during_failure", "after_work", "review"]
    task: str = Field(min_length=1)
    agent: str = "unknown"
    context_tags: list[str] = Field(min_length=1)
    assets_used: list[str] = Field(default_factory=list)
    expected_value: str = ""
    actual_value: str = ""
    failure_class: str = ""
    dependency_order_notes: str = ""
    evidence: list[str] = Field(default_factory=list)
    safety_confirmation: str = Field(min_length=1)
    created_at: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class AssetCalibrationReviewRecord(BaseModel):
    schema_version: str = "0.1.0"
    review_id: str
    sample_id: str
    asset_id: str
    asset_title: str
    logical_path: str
    asset_type: str
    generated_value_score: float
    generated_value_band: Literal["low", "medium", "high"]
    reviewer: str = ""
    reviewed_at: str | None = None
    score_rating: Literal["unreviewed", "too_high", "about_right", "too_low", "unsure"] = (
        "unreviewed"
    )
    false_positive_reason: str = ""
    false_negative_note: str = ""
    weight_change_note: str = ""
    notes: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"
