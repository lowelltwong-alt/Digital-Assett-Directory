import json
from pathlib import Path

from jsonschema.validators import validator_for

from digital_asset_directory.models import (
    AssetChunkRecord,
    AssetDeltaRecord,
    AssetRecord,
    ChangePatternRecord,
    ContextTagRecord,
    CounterfactualLessonRecord,
    DuplicateClusterRecord,
    FailureSignalRecord,
    LearningLoopRecord,
    LearningRuleRecord,
    RepoLearningEventRecord,
    RepoTimelineEventRecord,
    RootCauseHypothesisRecord,
    SemanticEvolutionRecord,
    WorktreeAttemptRecord,
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
