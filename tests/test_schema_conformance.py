import json
from pathlib import Path

from jsonschema.validators import validator_for
from pydantic import ValidationError

from digital_asset_directory.models import (
    AssetChunkRecord,
    AssetDeltaRecord,
    AssetRecord,
    ArchitectureConsultRecord,
    AttentionSeedRecord,
    ChangePatternRecord,
    ConnectionCandidateRecord,
    ContextTagRecord,
    CounterfactualLessonRecord,
    DuplicateClusterRecord,
    EscalationPacketRecord,
    ExpansionMapRecord,
    FailureSignalRecord,
    LessonAutomationDecisionRecord,
    LearningRulePromotionCandidateRecord,
    LearningLoopRecord,
    LearningRuleRecord,
    PriorityContentLessonReviewRecord,
    RepoLearningEventRecord,
    RepoBuildoutRecommendationRecord,
    RepoTimelineEventRecord,
    ReferenceArchitectureRecord,
    RootCauseHypothesisRecord,
    ScanCycleEventRecord,
    SemanticEvolutionRecord,
    TemplateRecord,
    WorktreeAttemptRecord,
    WorkflowPartRecord,
    WorkflowPartReviewRecord,
)

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[1]


def validate_registered_schema(schema_name: str, payload: dict) -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text(encoding="utf-8"))
    schema_path = ROOT / registry["schemas"][schema_name]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def test_asset_model_dump_matches_registered_schema():
    record = AssetRecord(
        asset_id="dad:asset:test",
        revision_id="dad:revision:test",
        source_id="local",
        source_kind="local",
        asset_type="document",
        title="Asset",
        logical_path="repo/asset.md",
        content_hash="hash",
        metadata_fingerprint="metadata-hash",
        content_sha256="sha",
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        tags=[],
        capabilities=[],
        needs=[],
        outcomes=[],
        lifecycle_state="active",
        freshness_status="current",
        trust_zone="source_owned",
        value_score=50,
        value_components={},
        source_provenance={"observed_by": "test"},
        metadata={},
    )

    validate_registered_schema("asset", record.model_dump(mode="json"))


def test_identity_layer_model_dumps_match_registered_schemas():
    chunk = AssetChunkRecord(
        chunk_id="dad:chunk:test",
        asset_id="dad:asset:test",
        revision_id="dad:revision:test",
        source_id="local",
        logical_path="repo/asset.md",
        chunk_index=0,
        chunk_kind="text",
        content_hash="hash",
        char_start=0,
        char_end=10,
        text_excerpt="alpha beta",
        evidence={"source": "test"},
        created_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )
    cluster = DuplicateClusterRecord(
        cluster_id="dad:duplicate-cluster:test",
        cluster_type="near_duplicate_candidate",
        asset_ids=["dad:asset:a", "dad:asset:b"],
        methods=["token_shingle_minhash"],
        evidence={"source": "test"},
        confidence=0.7,
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )
    delta = AssetDeltaRecord(
        delta_id="dad:delta:test",
        left_asset_id="dad:asset:a",
        right_asset_id="dad:asset:b",
        delta_type="containment_candidate",
        summary="A is contained in B.",
        shared_chunk_hashes=["shared"],
        left_only_chunk_hashes=[],
        right_only_chunk_hashes=["right-only"],
        evidence={"source": "test"},
        confidence=0.8,
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("asset_chunk", chunk.model_dump(mode="json"))
    validate_registered_schema("duplicate_cluster", cluster.model_dump(mode="json"))
    validate_registered_schema("asset_delta", delta.model_dump(mode="json"))


def test_semantic_evolution_model_dump_matches_registered_schema():
    record = SemanticEvolutionRecord(
        evolution_id="dad:semantic-evolution:test",
        family_key="example.schema.json",
        asset_type="schema",
        source_asset_ids=["dad:asset:a", "dad:asset:b"],
        representative_paths=["repo/schemas/example.schema.json"],
        path_class_counts={"canonicalish_source": 1, "temp_fixture": 1},
        raw_version_count=2,
        normalized_version_count=1,
        semantic_version_count=1,
        evolution_grade="none",
        noise_class="fixture_lineage_noise",
        semantic_change_score=0.0,
        noise_score=0.8,
        grading_summary="Raw copies differ, but normalized structured JSON is equivalent.",
        structural_changes={},
        current_instance_score_guidance="Do not score copied fixtures as independent assets.",
        family_value_guidance="No semantic evolution detected.",
        graph_edge_suggestions=["lineage_evidence_for", "noise_variant_of"],
        applies_when=["A temp copy is being compared."],
        does_not_apply_when=["Only one asset exists."],
        evidence={"source": "test"},
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("semantic_evolution", record.model_dump(mode="json"))


def test_identity_layer_registry_matches_registered_schema():
    payload = json.loads(
        (ROOT / "registry" / "identity-layer-registry.json").read_text(encoding="utf-8")
    )

    validate_registered_schema("asset_identity_layer", payload)
    layer_ids = {layer["id"] for layer in payload["layers"]}
    assert {
        "metadata_fingerprint",
        "sha256",
        "chunk_hashes",
        "extracted_text",
        "embeddings",
        "knowledge_graph",
        "audit_log",
    }.issubset(layer_ids)
    assert next(layer for layer in payload["layers"] if layer["id"] == "embeddings")[
        "status"
    ] == "deferred"
    assert (ROOT / payload["authority_doc"]).exists()
    assert len({layer["id"] for layer in payload["layers"]}) == len(payload["layers"])
    assert len({layer["order"] for layer in payload["layers"]}) == len(payload["layers"])


def test_learning_loop_model_dump_matches_registered_schema():
    record = LearningLoopRecord(
        learning_loop_id="dad:learning-loop:test",
        learning_loop_type="exception_to_adaptation_loop",
        source_asset_ids=["dad:asset:evaluation", "dad:asset:lesson"],
        expectation_source="Evaluation harness",
        exception_signal="Failure case",
        adaptation_proposal="Candidate rule update",
        review_gate="Human review gate",
        promotion_target="Validator",
        evidence={"source": "test"},
        confidence="medium",
        risk="medium",
        authority_boundary="Generated candidate only; source repositories retain authority.",
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("learning_loop", record.model_dump(mode="json"))


def test_workflow_part_model_dump_matches_registered_schema():
    record = WorkflowPartRecord(
        part_id="dad:workflow-part:test",
        part_type="validator",
        source_asset_ids=["dad:asset:test"],
        asset_pattern_id="evaluation_contract_system",
        role_in_workflow="Checks generated outputs before promotion.",
        authority_boundary="Generated candidate only; source repositories retain authority.",
        validation_commands=["python -m pytest tests/test_example.py"],
        applies_when=["A workflow emits a structured output."],
        does_not_apply_when=["The task is exploratory prose."],
        danger_if_misapplied="May be mistaken for passing validation when it has not run.",
        composition_affordances=["tests", "stabilized_by"],
        example_workflows=["dad:asset:test"],
        context_tags=["schema_contract"],
        maturity="recognized",
        confidence="medium",
        risk="low",
        evidence={"source": "test"},
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("workflow_part", record.model_dump(mode="json"))


def test_workflow_part_review_model_dump_matches_registered_schema():
    record = WorkflowPartReviewRecord(
        review_id="dad:workflow-part-review:test",
        sample_id="workflow-part-review-001",
        part_id="dad:workflow-part:test",
        part_type="validator",
        asset_pattern_id="evaluation_contract_system",
        reviewer="Lowell",
        reviewed_at="2026-06-29T00:00:00+00:00",
        usefulness="useful",
        safety="safe",
        specificity="right_level",
        dataflow_completeness="adequate_for_now",
        decision="accept_for_review_use",
        notes="Good review fixture.",
        false_positive_reason="",
        false_negative_note="",
        useful_example_note="Useful validator example.",
        missing_dataflow_note="",
        evidence={"methodology_version": "workflow-part-review-sampling-v0.1-stratified"},
        review_status="reviewed",
    )

    validate_registered_schema("workflow_part_review", record.model_dump(mode="json"))


def test_learning_rule_model_dump_matches_registered_schema():
    record = LearningRuleRecord(
        rule_id="learning-rule:test",
        title="Test rule",
        summary="A deterministic rule used by preflight and midflight.",
        trigger_terms=["calibration"],
        trigger_path_patterns=["processed/calibration/"],
        context_tags=["human_gate"],
        applies_when=["Calibration is assigning score labels."],
        does_not_apply_when=["No score label is being assigned."],
        required_actions=["Review current score before upside."],
        danger_if_ignored="Future value may inflate current score.",
        evidence=["test"],
        enforcement_level="require_ack",
        review_status="reviewed",
    )

    validate_registered_schema("learning_rule", record.model_dump(mode="json"))


def test_learning_rule_promotion_candidate_model_dump_matches_registered_schema():
    proposed_rule = LearningRuleRecord(
        rule_id="learning-rule:generated-test",
        title="Generated candidate rule",
        summary="A generated candidate rule that still needs human promotion.",
        trigger_terms=["priority-content", "lesson-review"],
        trigger_path_patterns=[],
        context_tags=["human_gate"],
        applies_when=["The reviewed context still matches."],
        does_not_apply_when=["The source lesson cannot be verified."],
        required_actions=["Verify context before promotion."],
        danger_if_ignored="A rule may be promoted without source context.",
        evidence=["dad:lesson:test", "dad:review:test"],
        enforcement_level="surface",
        review_status="generated_candidate",
    )
    record = LearningRulePromotionCandidateRecord(
        promotion_candidate_id="dad:learning-rule-promotion-candidate:test",
        source_lesson_candidate_id="dad:lesson:test",
        source_review_id="dad:review:test",
        proposed_rule=proposed_rule,
        promotion_readiness="eligible_for_human_promotion",
        blockers=[],
        required_human_gates=["Human approval before registry edit."],
        registry_mutated=False,
        authority_boundary="Generated candidate only.",
        evidence={"methodology_version": "learning-rule-promotion-candidate-v0.1"},
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("learning_rule_promotion_candidate", record.model_dump(mode="json"))


def test_scan_cycle_event_model_dump_matches_registered_schema():
    record = ScanCycleEventRecord(
        event_id="dad:scan-cycle-event:test",
        pass_type="no_rescan_catalog_coverage",
        methodology_version="lesson-automation-coverage-v0.1",
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
        checked_inputs=["state/catalog.sqlite3 assets table"],
        intentionally_not_checked=["source file contents"],
        signal_family_statuses=[
            {
                "signal_family_id": "priority_content_extracts",
                "current_status": "scoped_not_extracted",
            }
        ],
        recommended_next_signal_family_ids=["priority_content_extracts"],
        blocked_or_gated_signal_family_ids=["priority_content_extracts"],
        next_scan_guidance=["priority_content_extracts: run only after approval"],
        authority_boundary="Generated routing event only.",
        applies_when=["A future agent needs the scan cycle history."],
        does_not_apply_when=["The user authorizes a fresh broad scan."],
        danger_if_misapplied="The event is not permission to scan.",
    )

    validate_registered_schema("scan_cycle_event", record.model_dump(mode="json"))


def test_contextual_archaeology_model_dumps_match_registered_schemas():
    timestamp = "2026-01-01T00:00:00+00:00"
    context_tag = ContextTagRecord(
        context_tag_id="schema_contract",
        label="Schema contract",
        description="Schemas govern structured records.",
        applies_when=["Structured output is required."],
        does_not_apply_when=["Exploratory prose."],
        risk_if_misapplied="May overfit too early.",
    )
    attempt = WorktreeAttemptRecord(
        attempt_id="dad:attempt:test",
        attempt_kind="worktree",
        repo_lineage_key="feature",
        attempt_path="local/_codex_worktrees/feature-t1",
        task_hint="feature-t1",
        source_asset_ids=["dad:asset:a"],
        context_tags=["dependency_ordering"],
        evidence={"source": "test"},
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    timeline_event = RepoTimelineEventRecord(
        timeline_event_id="dad:timeline:test",
        repository_path="local/repo",
        event_type="commit",
        occurred_at=timestamp,
        asset_ids=["dad:asset:repo"],
        changed_paths=["tests/test_gate.py"],
        summary="add validator",
        evidence={"commit": "abc"},
        context_tags=["late_stabilizer"],
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    change_pattern = ChangePatternRecord(
        change_pattern_id="dad:change-pattern:test",
        pattern_type="late_stabilizer",
        asset_ids=["dad:asset:a"],
        paths=["tests/test_gate.py"],
        summary="Validator appears after failure.",
        evidence={"source": "test"},
        context_tags=["late_stabilizer"],
        confidence="low",
        risk="high",
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    failure_signal = FailureSignalRecord(
        failure_signal_id="dad:failure-signal:test",
        signal_type="test_failure",
        asset_ids=["dad:asset:a"],
        signal_terms=["failure"],
        summary="Failure term appears in test.",
        evidence={"source": "test"},
        context_tags=["repeated_failure"],
        confidence="medium",
        risk="medium",
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    root_cause = RootCauseHypothesisRecord(
        root_cause_id="dad:root-cause:test",
        hypothesis="Validation may have arrived late.",
        evidence_asset_ids=["dad:asset:a"],
        source_events=["dad:change-pattern:test"],
        context_tags=["late_stabilizer"],
        applies_when=["Similar schema-sensitive tasks."],
        does_not_apply_when=["The sequence is unknown."],
        confidence="low",
        risk="high",
        authority_boundary="Generated candidate only.",
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    lesson = CounterfactualLessonRecord(
        lesson_candidate_id="dad:counterfactual-lesson:test",
        lesson_candidate="Add the smallest validator before promotion.",
        applies_when=["Similar schema-sensitive tasks."],
        does_not_apply_when=["The sequence is unknown."],
        danger_if_misapplied="May over-govern exploratory work.",
        counterfactual_better_order=["Define gate", "Implement", "Review"],
        evidence_asset_ids=["dad:asset:a"],
        source_events=["dad:change-pattern:test"],
        context_tags=["late_stabilizer", "counterfactual_sequence"],
        confidence="low",
        risk="high",
        authority_boundary="Generated candidate only.",
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    repo_event = RepoLearningEventRecord(
        event_id="dad:repo-learning-event:test",
        repository="C:/repo",
        stage="after_work",
        task="Test task",
        agent="test",
        context_tags=["schema_contract"],
        assets_used=["dad:asset:a"],
        expected_value="Expected validator reuse.",
        actual_value="Validator helped.",
        evidence=["unit test"],
        safety_confirmation="Data only.",
        created_at=timestamp,
    )

    validate_registered_schema("context_tag", context_tag.model_dump(mode="json"))
    validate_registered_schema("worktree_attempt", attempt.model_dump(mode="json"))
    validate_registered_schema("repo_timeline_event", timeline_event.model_dump(mode="json"))
    validate_registered_schema("change_pattern", change_pattern.model_dump(mode="json"))
    validate_registered_schema("failure_signal", failure_signal.model_dump(mode="json"))
    validate_registered_schema("root_cause_hypothesis", root_cause.model_dump(mode="json"))
    validate_registered_schema("counterfactual_lesson", lesson.model_dump(mode="json"))
    validate_registered_schema("repo_learning_event", repo_event.model_dump(mode="json"))


def test_background_connection_model_dumps_match_registered_schemas():
    timestamp = "2026-01-01T00:00:00+00:00"
    seed = AttentionSeedRecord(
        attention_seed_id="dad:attention-seed:test",
        source_kind="recent_asset",
        source_ref="dad:asset:source",
        seed_asset_ids=["dad:asset:source"],
        tags=["governance"],
        capabilities=["review"],
        needs=["calibration"],
        attention_weight=0.8,
        raw_text_persisted=False,
        evidence={"source": "catalog_artifact_recency"},
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    candidate = ConnectionCandidateRecord(
        connection_candidate_id="dad:connection-candidate:test",
        connection_type="activates_cold_asset",
        source_asset_ids=["dad:asset:source"],
        target_asset_ids=["dad:asset:target"],
        endpoint_family_keys=["workflow:source", "workflow:target"],
        attention_seed_ids=[seed.attention_seed_id],
        cold_asset_ids=["dad:asset:target"],
        cheap_signal_evidence={"signals": ["term_overlap", "cold_lift"]},
        component_scores={
            "attention_relevance": 0.8,
            "cold_lift": 1.0,
            "complementarity": 0.5,
            "multi_hop_potential": 0.2,
            "novelty": 1.0,
        },
        connectivity_score=0.695,
        gates={"safety_gate": True, "evidence_gate": True, "authority_gate": True},
        gate_failures=[],
        escalation_eligible=False,
        reuse_first_edge_mapping=["activates", "satisfies_need"],
        why_might_matter_now="Target may help the current attention seed.",
        why_might_be_false="Signals may be coincidental.",
        evidence={"methodology": "background-connection-connectivity-v1"},
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    packet = EscalationPacketRecord(
        packet_id="dad:escalation-packet:test",
        connection_candidate_id=candidate.connection_candidate_id,
        scan_id_watermark="dad:scan:test",
        attention_seed_ids=[seed.attention_seed_id],
        cold_memory_cue="cold_asset_present",
        source_asset_ids=["dad:asset:source"],
        target_asset_ids=["dad:asset:target"],
        deduped_member_candidate_ids=[],
        minimal_context=[{"asset_id": "dad:asset:source"}],
        redacted_evidence_snippets=["source workflow"],
        cheap_signal_evidence={"signals": ["term_overlap", "cold_lift"]},
        component_scores=candidate.component_scores,
        connectivity_score=candidate.connectivity_score,
        proposed_connection_type=candidate.connection_type,
        reuse_first_edge_mapping=candidate.reuse_first_edge_mapping,
        why_might_matter_now=candidate.why_might_matter_now,
        why_might_be_false=candidate.why_might_be_false,
        stop_conditions=["Stop if authority is unclear."],
        safety_cleared=True,
        requested_verifier_tasks=["confirm_or_reject_connection"],
        budget_priority=1,
        evidence={"source_candidate": candidate.connection_candidate_id},
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )
    expansion = ExpansionMapRecord(
        expansion_map_id="dad:expansion-map:test",
        packet_id=packet.packet_id,
        root_connection_candidate_id=candidate.connection_candidate_id,
        direct_asset_ids=["dad:asset:neighbor"],
        second_hop_asset_ids=[],
        max_hops=2,
        max_nodes=25,
        per_hop_confidence={"1": 0.7},
        why_useful=["Shows immediate graph neighbors."],
        why_wrong=["Graph neighbors may be unreviewed."],
        stop_conditions=["Stop at max 2 hops."],
        evidence={"packet_id": packet.packet_id},
        generated_at=timestamp,
        scan_id="dad:scan:test",
    )

    validate_registered_schema("attention_seed", seed.model_dump(mode="json"))
    validate_registered_schema("connection_candidate", candidate.model_dump(mode="json"))
    validate_registered_schema("escalation_packet", packet.model_dump(mode="json"))
    validate_registered_schema("expansion_map", expansion.model_dump(mode="json"))


def test_background_connection_models_reject_privacy_and_safety_constant_violations():
    with pytest.raises(ValidationError):
        AttentionSeedRecord(
            attention_seed_id="dad:attention-seed:bad",
            source_kind="recent_asset",
            source_ref="dad:asset:source",
            attention_weight=0.8,
            raw_text_persisted=True,
            evidence={"source": "test"},
            generated_at="2026-01-01T00:00:00+00:00",
            scan_id="dad:scan:test",
        )
    with pytest.raises(ValidationError):
        EscalationPacketRecord(
            packet_id="dad:escalation-packet:bad",
            connection_candidate_id="dad:connection-candidate:test",
            scan_id_watermark="dad:scan:test",
            cold_memory_cue="cold_asset_present",
            source_asset_ids=["dad:asset:source"],
            target_asset_ids=["dad:asset:target"],
            minimal_context=[{"asset_id": "dad:asset:source"}],
            cheap_signal_evidence={"signals": ["term_overlap"]},
            component_scores={"attention_relevance": 0.5},
            connectivity_score=0.5,
            proposed_connection_type="activates_cold_asset",
            why_might_matter_now="Target may help.",
            why_might_be_false="Could be false.",
            stop_conditions=["Stop if unsafe."],
            safety_cleared=False,
            requested_verifier_tasks=["confirm_or_reject_connection"],
            budget_priority=1,
            evidence={"source": "test"},
            generated_at="2026-01-01T00:00:00+00:00",
            scan_id="dad:scan:test",
        )


def test_priority_content_lesson_review_model_dump_matches_registered_schema():
    record = PriorityContentLessonReviewRecord(
        review_id="dad:priority-content-lesson-review:test",
        sample_id="priority-content-lesson-review-001",
        lesson_candidate_id="dad:lesson-candidate:test",
        reviewer="Lowell",
        reviewed_at="2026-01-01T00:00:00+00:00",
        applicability="valid_context",
        usefulness="useful",
        safety="safe",
        actionability="actionable",
        decision="accept_for_review_use",
        notes="Looks useful with context.",
        false_positive_reason="",
        missing_context_note="",
        useful_example_note="Useful review example.",
        promotion_blocker_note="Needs separate promotion gate.",
        evidence={"candidate_only": True},
        review_status="reviewed",
    )

    validate_registered_schema(
        "priority_content_lesson_review", record.model_dump(mode="json")
    )


def test_lesson_automation_decision_model_dump_matches_registered_schema():
    record = LessonAutomationDecisionRecord(
        decision_id="dad:lesson-automation-decision:test",
        sample_id="lesson-automation-decision-001",
        action_id="dad:lesson-automation-action:test",
        signal_family_id="priority_content_extracts",
        action_kind="bounded_content_extract",
        reviewer="Lowell",
        reviewed_at="2026-01-01T00:00:00+00:00",
        decision="approve",
        approval_id="approval:test",
        approved_scope_file="processed/reports/priority_content_extract_scope.json",
        approved_repo_keys=["git-projects/repo-a"],
        approved_categories=["ai_navigation"],
        approved_repo_paths=[],
        max_bytes_per_file=20000,
        max_files=10,
        allow_content_read=True,
        allow_source_mutation=False,
        allow_external_api=False,
        allow_model_call=False,
        redaction_required=True,
        token_scope_note="",
        privacy_boundary_note="No external provider; local generated observations only.",
        rationale="Bounded content pass approved for AI navigation.",
        notes="Candidate-only generated observations.",
        stop_conditions=["Stop on secrets."],
        validation_commands=["PYTHONPATH=src python -m digital_asset_directory.cli validate"],
        evidence={"candidate_only": True},
        review_status="reviewed",
    )

    validate_registered_schema(
        "lesson_automation_decision", record.model_dump(mode="json")
    )


def test_repo_buildout_recommendation_model_dump_matches_registered_schema():
    record = RepoBuildoutRecommendationRecord(
        recommendation_id="dad:repo-buildout-recommendation:test",
        target_repo_key="git-projects/example",
        target_repo_label="example",
        recommendation_type="testing_qa_ci",
        title="Add smallest validator",
        rationale="A repo-local validator would make the buildout safer.",
        priority_score=72.5,
        priority_components={
            "repo_relevance": 1.0,
            "gap_severity": 0.8,
            "workflow_leverage": 0.7,
            "validation_readiness": 0.4,
            "evidence_strength": 0.5,
            "low_risk_bonus": 0.55,
        },
        gates={
            "evidence_gate": True,
            "source_boundary_gate": True,
            "privacy_gate": True,
            "no_target_mutation_gate": True,
            "no_external_call_gate": True,
            "scan_watermark_gate": True,
        },
        gate_failures=[],
        risk="medium",
        evidence_asset_ids=["dad:asset:test"],
        current_value_summary="Current scoped evidence before upside.",
        upside_lift_conditions=["Add a validator and rerun tests."],
        smallest_bounded_experiment="Review one file and one test.",
        validation_plan=["python -m pytest"],
        human_gates=["human review before mutation"],
        red_team_note="The validator may not cover the real workflow.",
        authority_boundary="Generated candidate only; source repositories retain authority.",
        source_boundary="same_repo_report_only",
        cross_repo_inspiration=False,
        evidence={"methodology_version": "repo-buildout-advisor-v0.1"},
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("repo_buildout_recommendation", record.model_dump(mode="json"))


def test_reference_architecture_model_dump_matches_registered_schema():
    record = ReferenceArchitectureRecord(
        reference_architecture_id="dad:reference-architecture:test",
        architecture_key="git-projects/example::governance_control_plane",
        architecture_label="example governance control plane",
        repository_key="git-projects/example",
        architecture_type="governance_control_plane",
        component_asset_ids=["dad:asset:front", "dad:asset:schema", "dad:asset:test"],
        component_roles={
            "agent_navigation": ["dad:asset:front"],
            "schemas_contracts": ["dad:asset:schema"],
            "validators_tests": ["dad:asset:test"],
        },
        detected_patterns=["contracts-backed-by-validation"],
        composition_summary="Front door routes agents; schemas define contracts; tests validate.",
        why_it_is_good_reference=["It has cooperating architecture roles."],
        missing_or_weak_pieces=["template or scaffold for reuse"],
        reuse_guidance=["Reuse the architecture shape, not source-owned facts."],
        novelty_score=0.4,
        usefulness_score=0.7,
        completeness_score=0.5,
        reusability_score=0.6,
        composition_score=0.55,
        validation_readiness=0.8,
        risk_score=0.2,
        reference_score=57.8,
        score_components={
            "novelty_score": 0.4,
            "usefulness_score": 0.7,
            "completeness_score": 0.5,
            "reusability_score": 0.6,
            "composition_score": 0.55,
            "validation_readiness": 0.8,
            "risk_score": 0.2,
        },
        gates={
            "evidence_gate": True,
            "source_boundary_gate": True,
            "privacy_gate": True,
            "no_content_read_gate": True,
            "no_external_call_gate": True,
            "candidate_only_gate": True,
        },
        gate_failures=[],
        smallest_bounded_experiment="Human reviews the component roles.",
        validation_plan=["python -m pytest"],
        human_gates=["human review before promotion"],
        authority_boundary="Generated candidate only; source repositories retain authority.",
        evidence={"methodology_version": "reference-architecture-recognition-v0.1"},
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("reference_architecture", record.model_dump(mode="json"))


def test_architecture_consult_model_dump_matches_registered_schema():
    record = ArchitectureConsultRecord(
        consult_id="dad:architecture-consult:test",
        intent_file="C:/intent/new-repo-intent.md",
        intent_hash="hash",
        new_repo_purpose="Seed a governed AI workflow repository.",
        domain="ai governance",
        risk_level="high",
        data_sensitivity="internal",
        expected_users_agents=["Codex", "Claude", "human maintainer"],
        workflows_needed=["AI navigation", "schema contracts", "learning loop"],
        validation_needs=["pytest", "schema validation"],
        matched_reference_architectures=[
            {
                "reference_architecture_id": "dad:reference-architecture:test",
                "architecture_label": "example governance control plane",
                "architecture_type": "governance_control_plane",
                "match_score": 88.5,
                "candidate_only": True,
            }
        ],
        recommended_templates=[
            {
                "template_id": "template:ai-table-of-contents",
                "template_name": "AI table of contents",
                "match_score": 45.0,
            }
        ],
        recommended_workflow_parts=[],
        background_connection_cues=[],
        governance_map_cues=[],
        learning_rule_cues=[],
        what_to_reuse=["Reuse architecture shape only."],
        what_not_to_copy=["Do not copy source-owned facts."],
        architecture_combination_plan=["Start with AI navigation and authority boundaries."],
        starter_repo_structure=["AI_FRONT_DOOR.md", "schemas/", "tests/"],
        template_dependencies=[
            {
                "template_id": "template:ai-table-of-contents",
                "depends_on_template_ids": [],
                "dependent_template_ids": [],
                "depends_on_contracts": ["docs/AI_ENTRYPOINT_AND_TOC_ROUTING_STANDARD.md"],
            }
        ],
        validation_checklist=["python -m pytest"],
        required_human_gates=["Human review before treating consult as canon."],
        gates={
            "intent_present_gate": True,
            "source_boundary_gate": True,
            "privacy_gate": True,
            "no_source_mutation_gate": True,
            "no_external_call_gate": True,
            "candidate_only_gate": True,
        },
        gate_failures=[],
        warnings=[],
        seed_prompt_path="processed/reports/architecture_consults/test_seed_prompt.md",
        authority_boundary="Generated consult only; the new repo owns its own canon.",
        evidence={"methodology_version": "architecture-consult-v0.1"},
        methodology_version="architecture-consult-v0.1",
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("architecture_consult", record.model_dump(mode="json"))


def test_template_record_model_dump_matches_registered_schema():
    record = TemplateRecord(
        template_id="template:test",
        path="templates/test.template.md",
        template_name="Test Template",
        template_type="checklist",
        purpose="Test template governance.",
        applies_when=["A template is under review."],
        does_not_apply_when=["No template exists."],
        danger_if_misapplied="May imply authority where none exists.",
        depends_on_template_ids=[],
        dependent_template_ids=[],
        depends_on_contracts=["docs/TEMPLATE_LIBRARY_GOVERNANCE.md"],
        upgrade_triggers=["Template schema changes."],
        recommended_review_interval_days=180,
        last_reviewed_at="2026-06-29",
        next_review_due_at="2026-12-26",
        upgrade_policy="recommend_only",
        deterministic_update_rule="Review before patching.",
        validation_commands=["python -m digital_asset_directory.cli validate"],
        authority_boundary="Template metadata only.",
    )

    validate_registered_schema("template_record", record.model_dump(mode="json"))
