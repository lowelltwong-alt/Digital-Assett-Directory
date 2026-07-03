from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

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


class ReviewLaneRecord(BaseModel):
    lane_id: Literal[
        "review-lane:red-team-and-premortem",
        "review-lane:lesson-asset-harness-scout",
    ]
    status: Literal["subagent", "checklist", "not_applicable", "not_run"]
    reviewer: str = ""
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    candidate_outputs: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)


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
    review_lanes: list[ReviewLaneRecord] = Field(default_factory=list)
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


class WorkflowPartRecord(BaseModel):
    schema_version: str = "0.1.0"
    part_id: str
    part_type: Literal[
        "validator",
        "contract",
        "gate",
        "runner",
        "orchestrator",
        "prompt_part",
        "capability_provider",
        "human_gate",
        "eval_gold",
        "learning_signal",
        "boundary_map",
        "decision_record",
        "lesson_part",
        "calibration_gate",
        "quarantine_gate",
    ]
    source_asset_ids: list[str] = Field(min_length=1)
    asset_pattern_id: str = Field(min_length=1)
    role_in_workflow: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    authority_boundary: str = Field(min_length=1)
    human_gates: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(min_length=1)
    danger_if_misapplied: str = Field(min_length=1)
    composition_affordances: list[str] = Field(default_factory=list)
    incompatible_parts: list[str] = Field(default_factory=list)
    example_workflows: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    maturity: Literal["recognized", "validated", "reused", "reviewed"] = "recognized"
    confidence: ConfidenceLabel = "medium"
    risk: Literal["low", "medium", "high"] = "medium"
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "workflow-part-recognition-v1"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class WorkflowPartReviewRecord(BaseModel):
    schema_version: str = "0.1.0"
    review_id: str
    sample_id: str
    part_id: str
    part_type: Literal[
        "validator",
        "contract",
        "gate",
        "runner",
        "orchestrator",
        "prompt_part",
        "capability_provider",
        "human_gate",
        "eval_gold",
        "learning_signal",
        "boundary_map",
        "decision_record",
        "lesson_part",
        "calibration_gate",
        "quarantine_gate",
    ]
    asset_pattern_id: str
    reviewer: str = ""
    reviewed_at: str | None = None
    usefulness: Literal["unreviewed", "useful", "not_useful", "unsure"] = "unreviewed"
    safety: Literal["unreviewed", "safe", "unsafe", "needs_more_review"] = "unreviewed"
    specificity: Literal[
        "unreviewed", "right_level", "too_broad", "too_narrow", "unsure"
    ] = "unreviewed"
    dataflow_completeness: Literal[
        "unreviewed",
        "adequate_for_now",
        "missing_inputs",
        "missing_outputs",
        "missing_side_effects",
        "not_applicable",
        "unsure",
    ] = "unreviewed"
    decision: Literal[
        "pending",
        "accept_for_review_use",
        "reject_candidate",
        "defer",
        "needs_human_gate",
    ] = "pending"
    notes: str = ""
    false_positive_reason: str = ""
    false_negative_note: str = ""
    useful_example_note: str = ""
    missing_dataflow_note: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ContextTagRecord(BaseModel):
    schema_version: str = "0.1.0"
    context_tag_id: str
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(default_factory=list)
    risk_if_misapplied: str = Field(min_length=1)


class TemplateRecord(BaseModel):
    schema_version: str = "0.1.0"
    template_id: str
    path: str = Field(min_length=1)
    template_name: str = Field(min_length=1)
    template_type: Literal[
        "repo_scaffold",
        "ai_navigation",
        "governance",
        "learning_loop",
        "handoff",
        "lesson",
        "review_gate",
        "checklist",
        "feedback",
        "automation",
    ]
    purpose: str = Field(min_length=1)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(min_length=1)
    danger_if_misapplied: str = Field(min_length=1)
    depends_on_template_ids: list[str] = Field(default_factory=list)
    dependent_template_ids: list[str] = Field(default_factory=list)
    depends_on_contracts: list[str] = Field(default_factory=list)
    upgrade_triggers: list[str] = Field(min_length=1)
    recommended_review_interval_days: int = Field(ge=1)
    last_reviewed_at: str
    next_review_due_at: str
    upgrade_policy: Literal[
        "recommend_only",
        "human_approved_patch",
        "managed_block_only",
    ] = "recommend_only"
    deterministic_update_rule: str = Field(min_length=1)
    validation_commands: list[str] = Field(default_factory=list)
    authority_boundary: str = Field(min_length=1)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "reviewed"


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


class PriorityContentLessonReviewRecord(BaseModel):
    schema_version: str = "0.1.0"
    review_id: str
    sample_id: str = Field(min_length=1)
    lesson_candidate_id: str = Field(min_length=1)
    reviewer: str = ""
    reviewed_at: str | None = None
    applicability: Literal[
        "unreviewed",
        "valid_context",
        "too_broad",
        "too_narrow",
        "unsafe_context",
        "unsure",
    ] = "unreviewed"
    usefulness: Literal["unreviewed", "useful", "not_useful", "unsure"] = "unreviewed"
    safety: Literal["unreviewed", "safe", "unsafe", "needs_more_review"] = "unreviewed"
    actionability: Literal["unreviewed", "actionable", "not_actionable", "unsure"] = "unreviewed"
    decision: Literal[
        "pending",
        "accept_for_review_use",
        "reject_candidate",
        "defer",
        "needs_revision",
    ] = "pending"
    notes: str = ""
    false_positive_reason: str = ""
    missing_context_note: str = ""
    useful_example_note: str = ""
    promotion_blocker_note: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class LessonAutomationDecisionRecord(BaseModel):
    schema_version: str = "0.1.0"
    decision_id: str
    sample_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    signal_family_id: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    reviewer: str = ""
    reviewed_at: str | None = None
    decision: Literal["pending", "approve", "defer", "reject"] = "pending"
    approval_id: str = ""
    approved_scope_file: str = ""
    approved_repo_keys: list[str] = Field(default_factory=list)
    approved_categories: list[str] = Field(default_factory=list)
    approved_repo_paths: list[str] = Field(default_factory=list)
    approved_include_paths: list[str] = Field(default_factory=list)
    approved_exclude_paths: list[str] = Field(default_factory=list)
    max_bytes_per_file: int = Field(default=0, ge=0)
    max_files: int = Field(default=0, ge=0)
    allow_content_read: bool = False
    allow_source_mutation: bool = False
    allow_external_api: bool = False
    allow_model_call: bool = False
    redaction_required: bool = True
    token_scope_note: str = ""
    privacy_boundary_note: str = ""
    rationale: str = ""
    notes: str = ""
    stop_conditions: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class LearningRulePromotionCandidateRecord(BaseModel):
    schema_version: str = "0.1.0"
    promotion_candidate_id: str
    source_lesson_candidate_id: str = Field(min_length=1)
    source_review_id: str = Field(min_length=1)
    proposed_rule: LearningRuleRecord
    promotion_readiness: Literal[
        "eligible_for_human_promotion",
        "blocked",
        "needs_more_evidence",
    ]
    blockers: list[str] = Field(default_factory=list)
    required_human_gates: list[str] = Field(min_length=1)
    registry_mutated: Literal[False] = False
    authority_boundary: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ExceptionBackfillReviewDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "0.1.0"
    decision_id: str
    review_group_id: str = Field(min_length=1)
    decision: Literal[
        "confirm",
        "reject",
        "needs_source_packet",
        "needs_classifier_refresh",
        "defer",
        "archive",
    ]
    reviewer: str = "unknown"
    reviewer_type: Literal["human", "agent", "source_repo", "unknown"] = "agent"
    review_authority_ref: str = Field(min_length=1)
    reviewed_at: str
    source_repo: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    source_queue_status: str = Field(min_length=1)
    current_classifier_version: str = ""
    candidate_count: int = Field(default=0, ge=0)
    public_release_required_count: int = Field(default=0, ge=0)
    readable_path_ref_count: int = Field(default=0, ge=0)
    notes: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    promotion_blockers_snapshot: list[str] = Field(default_factory=list)
    recommended_next_action_snapshot: str = ""
    source_queue_input_hashes: dict[str, str] = Field(default_factory=dict)
    source_queue_fingerprint: str = Field(min_length=1)
    result_effect: Literal[
        "source_review_confirmed_candidate_only",
        "rejected_candidate_no_learning",
        "source_packet_requested_no_learning",
        "classifier_refresh_required_no_learning",
        "deferred_no_learning",
        "archived_no_learning",
    ]
    authority_boundary: str = Field(min_length=1)
    screening: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal["agent_triage", "source_reviewed", "human_reviewed"] = "agent_triage"


class ScanCycleEventRecord(BaseModel):
    schema_version: str = "0.1.0"
    event_id: str
    event_type: Literal["coverage_cycle_run"] = "coverage_cycle_run"
    pass_type: str = Field(min_length=1)
    methodology_version: str = Field(min_length=1)
    scan_id: str
    generated_at: str
    checked_inputs: list[str] = Field(min_length=1)
    intentionally_not_checked: list[str] = Field(default_factory=list)
    signal_family_statuses: list[dict[str, Any]] = Field(min_length=1)
    recommended_next_signal_family_ids: list[str] = Field(default_factory=list)
    blocked_or_gated_signal_family_ids: list[str] = Field(default_factory=list)
    next_scan_guidance: list[str] = Field(default_factory=list)
    authority_boundary: str = Field(min_length=1)
    applies_when: list[str] = Field(min_length=1)
    does_not_apply_when: list[str] = Field(min_length=1)
    danger_if_misapplied: str = Field(min_length=1)
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


def default_mail_source_provenance() -> dict[str, Any]:
    return {
        "canonical_source_repo": "unknown",
        "source_repo_id": "",
        "source_repo_alias": "",
        "source_visibility": "unknown",
        "original_source_chain": [],
        "return_address": "",
        "original_mail_id": "",
        "composed_by": "unknown",
        "collected_by": "",
        "collected_at": "",
        "received_at": "",
    }


def default_mail_public_release() -> dict[str, Any]:
    return {
        "target_visibility": "unknown",
        "target_public_facing": False,
        "public_release_required": False,
        "public_release_status": "not_required",
        "human_release_id": "",
        "release_reason": "public_release_not_required",
    }


class MailMessageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "0.1.0"
    mail_id: str
    thread_id: str
    message_type: Literal[
        "lesson_suggestion",
        "asset_suggestion",
        "workflow_suggestion",
        "taxonomy_suggestion",
        "capability_suggestion",
        "governance_notice",
        "inbox_ack",
        "review_decision",
    ]
    source_repo: str = Field(min_length=1)
    target_repo: str = Field(min_length=1)
    created_at: str
    dedupe_key: str = Field(min_length=1)
    sensitivity: Literal["public", "internal", "confidential", "restricted", "unknown"] = "internal"
    review_status: Literal[
        "generated_candidate",
        "collected_candidate",
        "routed_candidate",
        "delivered_candidate",
        "reviewed",
        "rejected",
        "archived",
    ] = "generated_candidate"
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    source_provenance: dict[str, Any] = Field(default_factory=default_mail_source_provenance)
    public_release: dict[str, Any] = Field(default_factory=default_mail_public_release)


class MailDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "0.1.0"
    decision_id: str
    mail_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    decision: Literal["accept", "defer", "reject", "archive"]
    decided_at: str
    decided_by: str = "unknown"
    decision_actor_type: Literal["human", "agent", "unknown"] = "agent"
    human_verified: bool = False
    notes: str = ""
    review_status: Literal["agent_triage", "human_reviewed"] = "agent_triage"


class MailAdoptionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "0.1.0"
    adoption_id: str
    mail_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    intake_decision: Literal["implement_now", "save_for_future", "defer", "reject", "archive"]
    importance: Literal["now", "future", "not_relevant", "unknown"] = "unknown"
    recorded_at: str
    recorded_by: str = "unknown"
    human_verified: bool = False
    planned_use: str = ""
    implementation_plan: list[str] = Field(default_factory=list)
    implementation_status: Literal[
        "not_started",
        "planned",
        "watching",
        "deferred",
        "rejected",
        "archived",
    ] = "not_started"
    source_asset_refs: list[str] = Field(default_factory=list)
    source_repo: str = ""
    source_provenance: dict[str, Any] = Field(default_factory=dict)
    update_tracking: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    review_status: Literal["agent_triage", "human_reviewed"] = "agent_triage"


class AttentionSeedRecord(BaseModel):
    schema_version: str = "0.1.0"
    attention_seed_id: str
    source_kind: Literal[
        "git_recent_asset",
        "recent_asset",
        "roadmap_state",
        "review_record",
        "lesson_or_postflight",
        "preflight_task",
        "approved_source_scope",
    ]
    source_ref: str = Field(min_length=1)
    seed_asset_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)
    half_life_days: int = Field(default=7, ge=1)
    attention_weight: float = Field(ge=0, le=1)
    raw_text_persisted: Literal[False] = False
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "background-connection-connectivity-v1"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ConnectionCandidateRecord(BaseModel):
    schema_version: str = "0.1.0"
    connection_candidate_id: str
    connection_type: Literal[
        "activates_cold_asset",
        "bridges_orphan_to_attention_seed",
        "composes_with",
        "duplicate_variant_delta",
        "same_workflow_different_domain",
        "lesson_applies_when",
        "lesson_does_not_apply_when",
        "workflow_part_of",
        "missing_capability_for",
        "dangerous_composition_with",
        "requires_human_gate",
        "supports_but_cannot_override",
    ]
    source_asset_ids: list[str] = Field(min_length=1)
    target_asset_ids: list[str] = Field(min_length=1)
    endpoint_family_keys: list[str] = Field(min_length=2)
    attention_seed_ids: list[str] = Field(default_factory=list)
    cold_asset_ids: list[str] = Field(default_factory=list)
    cheap_signal_evidence: dict[str, Any] = Field(min_length=1)
    component_scores: dict[str, float] = Field(min_length=1)
    connectivity_score: float = Field(ge=0, le=1)
    gates: dict[str, bool] = Field(min_length=1)
    gate_failures: list[str] = Field(default_factory=list)
    escalation_eligible: bool = False
    reuse_first_edge_mapping: list[str] = Field(default_factory=list)
    why_might_matter_now: str = Field(min_length=1)
    why_might_be_false: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "background-connection-connectivity-v1"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class EscalationPacketRecord(BaseModel):
    schema_version: str = "0.1.0"
    packet_id: str
    connection_candidate_id: str
    scan_id_watermark: str = Field(min_length=1)
    attention_seed_ids: list[str] = Field(default_factory=list)
    cold_memory_cue: str = Field(min_length=1)
    source_asset_ids: list[str] = Field(min_length=1)
    target_asset_ids: list[str] = Field(min_length=1)
    deduped_member_candidate_ids: list[str] = Field(default_factory=list)
    minimal_context: list[dict[str, Any]] = Field(min_length=1)
    redacted_evidence_snippets: list[str] = Field(default_factory=list)
    cheap_signal_evidence: dict[str, Any] = Field(min_length=1)
    component_scores: dict[str, float] = Field(min_length=1)
    connectivity_score: float = Field(ge=0, le=1)
    proposed_connection_type: str = Field(min_length=1)
    reuse_first_edge_mapping: list[str] = Field(default_factory=list)
    why_might_matter_now: str = Field(min_length=1)
    why_might_be_false: str = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
    safety_cleared: Literal[True] = True
    requested_verifier_tasks: list[str] = Field(min_length=1)
    budget_priority: int = Field(ge=1)
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "background-connection-connectivity-v1"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ExpansionMapRecord(BaseModel):
    schema_version: str = "0.1.0"
    expansion_map_id: str
    packet_id: str
    root_connection_candidate_id: str
    direct_asset_ids: list[str] = Field(default_factory=list)
    second_hop_asset_ids: list[str] = Field(default_factory=list)
    max_hops: int = Field(default=2, ge=0, le=2)
    max_nodes: int = Field(default=25, ge=1, le=25)
    per_hop_confidence: dict[str, float] = Field(default_factory=dict)
    why_useful: list[str] = Field(default_factory=list)
    why_wrong: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "background-connection-connectivity-v1"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class RepoBuildoutRecommendationRecord(BaseModel):
    schema_version: str = "0.1.0"
    recommendation_id: str
    target_repo_key: str = Field(min_length=1)
    target_repo_label: str = Field(min_length=1)
    recommendation_type: Literal[
        "front_door_ai_navigation",
        "governance_human_gates",
        "schemas_contracts_validators",
        "workflow_parts_reusable_subsystems",
        "learning_pay_forward_loops",
        "dataflow_normalization",
        "testing_qa_ci",
        "duplicate_variant_semantic_evolution",
        "security_privacy_public_safe",
        "internal_composition",
        "cross_repo_inspiration",
        "manual_task_alert",
        "proposal_or_background_connection",
    ]
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    priority_score: float = Field(ge=0, le=100)
    priority_components: dict[str, float] = Field(min_length=1)
    gates: dict[str, bool] = Field(min_length=1)
    gate_failures: list[str] = Field(default_factory=list)
    risk: Literal["low", "medium", "high"] = "medium"
    evidence_asset_ids: list[str] = Field(min_length=1)
    current_value_summary: str = Field(min_length=1)
    upside_lift_conditions: list[str] = Field(min_length=1)
    smallest_bounded_experiment: str = Field(min_length=1)
    validation_plan: list[str] = Field(min_length=1)
    human_gates: list[str] = Field(default_factory=list)
    red_team_note: str = Field(min_length=1)
    authority_boundary: str = Field(min_length=1)
    source_boundary: str = Field(min_length=1)
    cross_repo_inspiration: bool = False
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "repo-buildout-advisor-v0.1"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ReferenceArchitectureRecord(BaseModel):
    schema_version: str = "0.1.0"
    reference_architecture_id: str
    architecture_key: str = Field(min_length=1)
    architecture_label: str = Field(min_length=1)
    repository_key: str = Field(min_length=1)
    architecture_type: Literal[
        "repo_system_architecture",
        "governance_control_plane",
        "workflow_reference_architecture",
        "schema_contract_architecture",
        "agent_skill_architecture",
        "dataflow_normalization_architecture",
        "evaluation_quality_architecture",
        "learning_loop_architecture",
        "public_safe_private_source_architecture",
        "template_scaffold_architecture",
        "unknown_reference_architecture",
    ]
    component_asset_ids: list[str] = Field(min_length=1)
    component_roles: dict[str, list[str]] = Field(min_length=1)
    detected_patterns: list[str] = Field(min_length=1)
    composition_summary: str = Field(min_length=1)
    why_it_is_good_reference: list[str] = Field(min_length=1)
    missing_or_weak_pieces: list[str] = Field(default_factory=list)
    reuse_guidance: list[str] = Field(min_length=1)
    novelty_score: float = Field(ge=0, le=1)
    usefulness_score: float = Field(ge=0, le=1)
    completeness_score: float = Field(ge=0, le=1)
    reusability_score: float = Field(ge=0, le=1)
    composition_score: float = Field(ge=0, le=1)
    validation_readiness: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    reference_score: float = Field(ge=0, le=100)
    score_components: dict[str, float] = Field(min_length=1)
    gates: dict[str, bool] = Field(min_length=1)
    gate_failures: list[str] = Field(default_factory=list)
    smallest_bounded_experiment: str = Field(min_length=1)
    validation_plan: list[str] = Field(min_length=1)
    human_gates: list[str] = Field(default_factory=list)
    authority_boundary: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "reference-architecture-recognition-v0.1"
    generated_at: str
    scan_id: str
    review_status: Literal["generated_candidate", "reviewed", "rejected"] = "generated_candidate"


class ArchitectureConsultRecord(BaseModel):
    schema_version: str = "0.1.0"
    consult_id: str
    intent_file: str = Field(min_length=1)
    intent_hash: str = Field(min_length=1)
    new_repo_purpose: str = Field(min_length=1)
    domain: str = "unknown"
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    data_sensitivity: Literal["public", "internal", "restricted", "unknown"] = "unknown"
    expected_users_agents: list[str] = Field(default_factory=list)
    workflows_needed: list[str] = Field(default_factory=list)
    validation_needs: list[str] = Field(default_factory=list)
    matched_reference_architectures: list[dict[str, Any]] = Field(default_factory=list)
    recommended_templates: list[dict[str, Any]] = Field(default_factory=list)
    recommended_workflow_parts: list[dict[str, Any]] = Field(default_factory=list)
    background_connection_cues: list[dict[str, Any]] = Field(default_factory=list)
    governance_map_cues: list[dict[str, Any]] = Field(default_factory=list)
    learning_rule_cues: list[dict[str, Any]] = Field(default_factory=list)
    what_to_reuse: list[str] = Field(min_length=1)
    what_not_to_copy: list[str] = Field(min_length=1)
    architecture_combination_plan: list[str] = Field(min_length=1)
    starter_repo_structure: list[str] = Field(min_length=1)
    template_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    validation_checklist: list[str] = Field(min_length=1)
    required_human_gates: list[str] = Field(default_factory=list)
    gates: dict[str, bool] = Field(min_length=1)
    gate_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    seed_prompt_path: str = ""
    authority_boundary: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(min_length=1)
    methodology_version: str = "architecture-consult-v0.1"
    generated_at: str
    scan_id: str
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
