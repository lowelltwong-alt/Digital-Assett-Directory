from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from digital_asset_directory.models import (
    AssetRecord,
    EdgeRecord,
    WorkflowPartRecord,
    WorkflowPartReviewRecord,
)
from digital_asset_directory.workflow_parts import (
    build_workflow_part_usage_guidance,
    build_workflow_part_review_queue,
    build_workflow_part_review_template,
    build_workflow_part_edges,
    build_workflow_part_records,
    detect_workflow_part_matches,
    load_workflow_part_reviews,
    summarize_workflow_part_reviews,
    update_workflow_part_review_record,
    workflow_part_calibration_evidence_markdown,
    write_workflow_part_calibration_evidence,
    write_workflow_part_usage_guidance,
    write_workflow_part_review_template_outputs,
    write_workflow_part_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(
    asset_id: str,
    *,
    title: str,
    logical_path: str,
    asset_type: str = "document",
    parent_asset_id: str | None = None,
    text: str = "",
    tags: list[str] | None = None,
    capabilities: list[str] | None = None,
    sensitivity: str = "internal",
    content_hash: str | None = None,
    content_sha256: str | None = None,
    value_score: float = 60.0,
) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=parent_asset_id,
        source_kind="local",
        asset_type=asset_type,
        title=title,
        description=text[:200],
        logical_path=logical_path,
        content_hash=content_hash or f"hash-{asset_id}",
        metadata_fingerprint=f"metadata-{asset_id}",
        content_sha256=content_sha256,
        size_bytes=100 if content_sha256 else 0,
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        tags=tags or [],
        capabilities=capabilities or [],
        outcomes=["repeatable_quality"],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity=sensitivity,  # type: ignore[arg-type]
        trust_zone="source_owned",
        value_score=value_score,
        value_components={},
        metadata={
            "excerpt": text,
            "chunk_text": text,
            "text_tokens": sorted(text.lower().split()),
            "asset_patterns": [],
        },
    )


def make_duplicate_edge(left: str, right: str) -> EdgeRecord:
    return EdgeRecord(
        edge_id=f"dad:edge:{left}:{right}:near_duplicate_of",
        edge_type="near_duplicate_of",
        source_asset_id=left,
        target_asset_id=right,
        method="test",
        confidence=0.9,
        evidence={"source": "synthetic"},
        created_at=TIMESTAMP,
        scan_id=SCAN_ID,
    )


def test_workflow_part_model_requires_context_bound_safety_fields():
    with pytest.raises(ValidationError):
        WorkflowPartRecord(
            part_id="dad:workflow-part:bad",
            part_type="validator",
            source_asset_ids=["dad:asset:test"],
            asset_pattern_id="evaluation_contract_system",
            role_in_workflow="Checks behavior.",
            authority_boundary="Generated candidate only.",
            evidence={"source": "test"},
            generated_at=TIMESTAMP,
            scan_id=SCAN_ID,
        )


def test_detect_workflow_parts_allows_multiple_roles_without_private_content():
    asset = make_asset(
        "dad:asset:validator",
        title="Schema Validator And Review Gate",
        logical_path="tests/test_schema_contract.py",
        asset_type="test",
        text=(
            "pytest validates JSON schema conformance and requires human review before "
            "promotion through a gate."
        ),
        tags=["governance"],
        capabilities=["validate_contracts"],
    )

    matches = detect_workflow_part_matches(asset)
    part_types = {match["part_type"] for match in matches}

    assert {"validator", "contract", "gate", "human_gate"}.issubset(part_types)
    assert all(match["review_status"] == "generated_candidate" for match in matches)
    assert "pytest validates" not in json.dumps(matches)


def test_workflow_part_records_are_candidate_only_and_skip_noise_or_private_lanes():
    canonical = make_asset(
        "dad:asset:canonical-validator",
        title="Canonical Validator",
        logical_path="repo/tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
    )
    temp_copy = make_asset(
        "dad:asset:temp-validator",
        title="Temp Validator Copy",
        logical_path="repo/.pytest-tmp-root/pytest-of-lowell/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
        value_score=99,
    )
    raw_data = make_asset(
        "dad:asset:raw-data",
        title="Raw Output Validator",
        logical_path="repo/data/output/validator_notes.md",
        asset_type="document",
        text="validator review notes",
    )

    records = build_workflow_part_records(
        [canonical, temp_copy, raw_data],
        [make_duplicate_edge(canonical.asset_id, temp_copy.asset_id)],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert records
    assert all(record.review_status == "generated_candidate" for record in records)
    assert all(record.methodology_version == "workflow-part-recognition-v1" for record in records)
    assert all("dad:asset:temp-validator" not in record.source_asset_ids for record in records)
    assert all("dad:asset:raw-data" not in record.source_asset_ids for record in records)
    assert all(record.maturity == "recognized" for record in records)
    assert all(record.inputs == [] and record.outputs == [] for record in records)


def test_workflow_part_family_dedup_groups_duplicate_canonical_assets():
    left = make_asset(
        "dad:asset:left",
        title="Validator Left",
        logical_path="repo-a/tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
    )
    right = make_asset(
        "dad:asset:right",
        title="Validator Right",
        logical_path="repo-b/tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
    )

    records = build_workflow_part_records(
        [left, right],
        [make_duplicate_edge(left.asset_id, right.asset_id)],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    validators = [record for record in records if record.part_type == "validator"]

    assert len(validators) == 1
    assert set(validators[0].source_asset_ids) == {left.asset_id, right.asset_id}
    assert validators[0].confidence in {"medium", "high"}


def test_workflow_part_edges_and_writer_create_generated_outputs(tmp_path: Path):
    asset = make_asset(
        "dad:asset:gate",
        title="Preflight Gate",
        logical_path="docs/preflight-gate.md",
        asset_type="workflow",
        text="preflight postflight human review gate approval stop condition.",
        tags=["governance"],
    )
    records = build_workflow_part_records([asset], [], scan_id=SCAN_ID, generated_at=TIMESTAMP)
    edges = build_workflow_part_edges(records, scan_id=SCAN_ID, created_at=TIMESTAMP)

    assert edges
    assert {edge.edge_type for edge in edges} == {"has_member_asset"}
    assert all(edge.source_asset_id.startswith("dad:workflow-part:") for edge in edges)
    assert all(edge.review_status == "generated_candidate" for edge in edges)

    result = write_workflow_part_outputs(
        tmp_path,
        [asset],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        review_sample=10,
    )

    assert result["candidate_part_count"] == len(records)
    for path_text in result["outputs"].values():
        path = Path(path_text)
        assert path.exists()
        assert path.is_relative_to(tmp_path / "processed")
    payload = Path(result["outputs"]["workflow_parts"]).read_text(encoding="utf-8")
    assert "Generated candidate only" in payload


def test_workflow_part_review_template_is_stratified_and_candidate_only():
    assets = [
        make_asset(
            "dad:asset:validator",
            title="Validator",
            logical_path="tests/test_contract.py",
            asset_type="test",
            text="pytest validator schema conformance fixture.",
            capabilities=["validate_contracts"],
        ),
        make_asset(
            "dad:asset:gate",
            title="Gate",
            logical_path="docs/preflight-gate.md",
            asset_type="workflow",
            text="preflight postflight human review gate approval stop condition.",
            tags=["governance"],
        ),
        make_asset(
            "dad:asset:learning",
            title="Learning Loop",
            logical_path="docs/lesson-handoff.md",
            asset_type="lesson",
            text="lesson handoff postflight feedback exception failure applies_when does_not_apply_when.",
            tags=["learning-loop"],
        ),
    ]
    records = build_workflow_part_records(assets, [], scan_id=SCAN_ID, generated_at=TIMESTAMP)

    reviews = build_workflow_part_review_template(records, sample_size=6)

    assert reviews
    assert len({review.part_type for review in reviews}) > 1
    assert all(review.review_status == "generated_candidate" for review in reviews)
    assert all(
        review.evidence["methodology_version"]
        == "workflow-part-review-sampling-v0.1-stratified"
        for review in reviews
    )
    assert all(review.evidence["generated_candidate_only"] is True for review in reviews)


def test_workflow_part_review_update_summary_and_queue():
    asset = make_asset(
        "dad:asset:validator",
        title="Validator",
        logical_path="tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
    )
    records = build_workflow_part_records([asset], [], scan_id=SCAN_ID, generated_at=TIMESTAMP)
    reviews = build_workflow_part_review_template(records, sample_size=1)

    updated_reviews, updated = update_workflow_part_review_record(
        reviews,
        sample_id=reviews[0].sample_id,
        reviewer="Lowell",
        usefulness="useful",
        safety="safe",
        specificity="right_level",
        dataflow_completeness="missing_inputs",
        decision="accept_for_review_use",
        useful_example_note="Good validator part.",
        missing_dataflow_note="Inputs should be declared before assembly.",
    )
    summary = summarize_workflow_part_reviews(updated_reviews)
    queue = build_workflow_part_review_queue(updated_reviews, records, status="reviewed", limit=5)

    assert updated.review_status == "reviewed"
    assert updated.reviewed_at
    assert summary["reviewed_count"] == 1
    assert summary["useful_example_note_count"] == 1
    assert summary["missing_dataflow_note_count"] == 1
    assert queue["returned_count"] == 1
    assert queue["items"][0]["labels"]["usefulness"] == "useful"


def test_workflow_part_calibration_evidence_fails_closed_without_labels():
    asset = make_asset(
        "dad:asset:validator",
        title="Validator",
        logical_path="tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
    )
    records = build_workflow_part_records([asset], [], scan_id=SCAN_ID, generated_at=TIMESTAMP)
    reviews = build_workflow_part_review_template(records, sample_size=1)

    with pytest.raises(ValueError, match="requires reviewed records"):
        workflow_part_calibration_evidence_markdown(reviews, Path("review.jsonl"))


def make_reviewed_workflow_part_reviews() -> list[WorkflowPartReviewRecord]:
    return [
        WorkflowPartReviewRecord(
            review_id="dad:workflow-part-review:001",
            sample_id="workflow-part-review-001",
            part_id="dad:workflow-part:accepted",
            part_type="validator",
            asset_pattern_id="evaluation_contract_system",
            reviewer="Lowell",
            reviewed_at=TIMESTAMP,
            usefulness="useful",
            safety="safe",
            specificity="right_level",
            dataflow_completeness="missing_inputs",
            decision="accept_for_review_use",
            notes="Accepted for review-use only.",
            false_negative_note="Composite validator/runner role should be surfaced.",
            useful_example_note="Useful validator example.",
            missing_dataflow_note="Needs declared input fixtures before assembly.",
            evidence={"representative_paths": ["repo/tests/test_validator.py"]},
            review_status="reviewed",
        ),
        WorkflowPartReviewRecord(
            review_id="dad:workflow-part-review:002",
            sample_id="workflow-part-review-002",
            part_id="dad:workflow-part:rejected",
            part_type="quarantine_gate",
            asset_pattern_id="security_scanner_quarantine_system",
            reviewer="Lowell",
            reviewed_at=TIMESTAMP,
            usefulness="not_useful",
            safety="needs_more_review",
            specificity="too_broad",
            dataflow_completeness="not_applicable",
            decision="reject_candidate",
            notes="Reject marker-file candidate.",
            false_positive_reason="Empty marker file does not prove a quarantine gate.",
            evidence={"representative_paths": ["repo/security/.gitkeep"]},
            review_status="reviewed",
        ),
        WorkflowPartReviewRecord(
            review_id="dad:workflow-part-review:003",
            sample_id="workflow-part-review-003",
            part_id="dad:workflow-part:human-gated",
            part_type="boundary_map",
            asset_pattern_id="agent_skill_graph_system",
            reviewer="Lowell",
            reviewed_at=TIMESTAMP,
            usefulness="useful",
            safety="needs_more_review",
            specificity="right_level",
            dataflow_completeness="missing_side_effects",
            decision="needs_human_gate",
            notes="Authority-sensitive boundary map.",
            evidence={"representative_paths": ["repo/docs/security-boundary.md"]},
            review_status="reviewed",
        ),
        WorkflowPartReviewRecord(
            review_id="dad:workflow-part-review:004",
            sample_id="workflow-part-review-004",
            part_id="dad:workflow-part:deferred",
            part_type="eval_gold",
            asset_pattern_id="route_isolated_evaluation_harness",
            reviewer="Lowell",
            reviewed_at=TIMESTAMP,
            usefulness="unsure",
            safety="needs_more_review",
            specificity="too_narrow",
            dataflow_completeness="unsure",
            decision="defer",
            notes="Generated eval output might not be gold.",
            evidence={"representative_paths": ["repo/eval/run.json"]},
            review_status="reviewed",
        ),
    ]


def test_workflow_part_calibration_evidence_preserves_review_notes(tmp_path: Path):
    reviews = make_reviewed_workflow_part_reviews()
    review_path = tmp_path / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    review_path.parent.mkdir(parents=True)
    review_path.write_text("", encoding="utf-8")

    _, output = write_workflow_part_calibration_evidence(tmp_path, reviews, review_path)
    text = Path(output).read_text(encoding="utf-8")

    assert "processed/workflow_parts/workflow_part_review_template.jsonl" in text
    assert "Composite validator/runner role should be surfaced." in text
    assert "Empty marker file does not prove a quarantine gate." in text
    assert "Useful validator example." in text
    assert "Needs declared input fixtures before assembly." in text
    assert str(tmp_path) not in text


def test_workflow_part_usage_guidance_is_manual_and_decision_aware(tmp_path: Path):
    reviews = make_reviewed_workflow_part_reviews()

    guidance = build_workflow_part_usage_guidance(reviews, limit=10)

    assert guidance["review_status"] == "generated_candidate"
    assert guidance["risk_tier"] == "medium"
    assert guidance["manual_use_policy"]["automatic_preflight_surfacing"].startswith("Deferred")
    assert guidance["summary"]["accepted_count"] == 1
    assert guidance["summary"]["human_gated_count"] == 1
    assert guidance["summary"]["rejected_count"] == 1
    assert guidance["summary"]["deferred_count"] == 1
    assert guidance["review_use_candidates"][0]["action"] == (
        "usable_as_review_context_but_declare_dataflow_before_assembly"
    )
    assert guidance["human_gated_candidates"][0]["action"] == "requires_human_gate_before_reuse"
    assert guidance["rejected_patterns"][0]["action"] == (
        "use_as_false_positive_or_lineage_evidence_only"
    )

    review_path = tmp_path / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    review_path.parent.mkdir(parents=True)
    review_path.write_text("", encoding="utf-8")
    _, report, payload = write_workflow_part_usage_guidance(tmp_path, reviews, review_path)
    report_text = Path(report).read_text(encoding="utf-8")
    payload_text = Path(payload).read_text(encoding="utf-8")

    assert Path(report).is_relative_to(tmp_path / "processed")
    assert Path(payload).is_relative_to(tmp_path / "processed")
    assert "Automatic preflight surfacing" in report_text
    assert "requires_human_gate_before_reuse" in payload_text
    assert str(tmp_path) not in report_text


def test_workflow_part_review_template_writer_outputs_generated_files(tmp_path: Path):
    asset = make_asset(
        "dad:asset:validator",
        title="Validator",
        logical_path="tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
    )
    records = build_workflow_part_records([asset], [], scan_id=SCAN_ID, generated_at=TIMESTAMP)

    result = write_workflow_part_review_template_outputs(
        tmp_path, records, sample_size=1, generated_at=TIMESTAMP
    )

    assert result["review_template_count"] == 1
    review_path = Path(result["outputs"]["review_template"])
    assert review_path.exists()
    assert review_path.is_relative_to(tmp_path / "processed")
    loaded = load_workflow_part_reviews(review_path)
    assert loaded[0].sample_id == "workflow-part-review-001"


def test_workflow_part_edge_types_are_registered():
    registry = json.loads(Path("registry/edge-type-registry.json").read_text(encoding="utf-8"))
    edge_types = {item["id"] for item in registry["edge_types"]}

    assert {
        "produces_input_for",
        "substitutes_for",
        "specializes",
        "generalizes",
        "quarantines",
    }.issubset(edge_types)
