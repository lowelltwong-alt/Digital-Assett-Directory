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
