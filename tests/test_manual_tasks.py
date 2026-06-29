from __future__ import annotations

from pathlib import Path

import pytest

from digital_asset_directory.manual_tasks import (
    build_manual_task_queue,
    manual_task_queue_markdown,
    rank_alerts_for_manual_review,
    write_manual_task_queue,
)
from digital_asset_directory.models import AlertRecord, AssetRecord

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(
    asset_id: str,
    title: str,
    path: str,
    *,
    asset_type: str = "code",
    value_score: float = 50.0,
) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        source_kind="local",
        asset_type=asset_type,
        title=title,
        description="Synthetic asset.",
        logical_path=path,
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=value_score,
    )


def make_alert(asset: AssetRecord, *, title: str | None = None, severity: str = "medium") -> AlertRecord:
    return AlertRecord(
        alert_id=f"dad:alert:{asset.asset_id}",
        created_at=TIMESTAMP,
        alert_type="orphan_asset",
        severity=severity,  # type: ignore[arg-type]
        title=title or f"Orphan candidate: {asset.title}",
        description="Few graph connections.",
        asset_ids=[asset.asset_id],
        evidence={"degree": 1, "logical_path": asset.logical_path, "value_score": asset.value_score},
        recommended_action="Review relationships.",
        scan_id=SCAN_ID,
    )


def sample_workflow_guidance() -> dict:
    return {
        "methodology_version": "workflow-part-usage-guidance-v0.1",
        "authority_boundary": "Manual review guidance only.",
        "danger_if_misapplied": "Do not assemble without gates.",
        "manual_use_policy": {"automatic_preflight_surfacing": "Deferred."},
        "summary": {
            "reviewed_count": 4,
            "accepted_count": 1,
            "human_gated_count": 1,
            "rejected_count": 1,
            "deferred_count": 1,
        },
        "review_use_candidates": [
            {
                "sample_id": "workflow-part-review-001",
                "part_type": "validator",
                "asset_pattern_id": "evaluation_contract_system",
                "representative_path": "repo/tests/test_contract.py",
                "dataflow_completeness": "missing_inputs",
                "missing_dataflow_note": "Needs fixtures.",
                "action": "usable_as_review_context_but_declare_dataflow_before_assembly",
            }
        ],
        "human_gated_candidates": [
            {
                "sample_id": "workflow-part-review-002",
                "part_type": "boundary_map",
                "asset_pattern_id": "agent_skill_graph_system",
                "representative_path": "repo/docs/privacy.md",
                "dataflow_completeness": "adequate_for_now",
                "note": "Authority sensitive.",
            }
        ],
        "rejected_patterns": [
            {
                "sample_id": "workflow-part-review-003",
                "part_type": "quarantine_gate",
                "representative_path": "repo/security/.gitkeep",
                "false_positive_reason": "Marker file only.",
            }
        ],
        "deferred_candidates": [
            {
                "sample_id": "workflow-part-review-004",
                "part_type": "eval_gold",
                "representative_path": "repo/eval/run.json",
                "dataflow_completeness": "unsure",
            }
        ],
    }


def test_manual_task_priority_prefers_dad_and_workflow_context_over_literal_order():
    generic = make_asset("generic", "world", "git-projects/orphan_radar/orphan-radar/world.py")
    dad = make_asset(
        "dad-workflow",
        "workflow_parts",
        "git-projects/04_Digital_Assett_Directory/src/digital_asset_directory/workflow_parts.py",
        asset_type="workflow",
        value_score=61.9,
    )
    alerts = [make_alert(generic), make_alert(dad)]

    result = rank_alerts_for_manual_review(alerts, [generic, dad], latest_scan_id=SCAN_ID)

    assert result["ranked_alerts"][0]["asset_id"] == "dad-workflow"
    assert result["ranked_alerts"][0]["family_key"] == "dad_workflow_part_relationships"
    assert result["ranked_alerts"][0]["source_boundary"] == "dad_owned"
    assert "severity and title" in result["literal_inbox_note"]


def test_manual_task_family_grouping_keeps_mock_trial_read_only():
    mock_validator = make_asset(
        "mock-validator",
        "validate_graph_simulation",
        "git-projects/02_Other_Git_Projects/Mock Trial4.26/simulation/validate_graph_simulation.py",
        value_score=61.5,
    )
    logos_validator = make_asset(
        "logos-validator",
        "validate_task_scope",
        "git-projects/03_World_View/logos-scripture-graph-repo/scripts/validate_task_scope.py",
        value_score=58.7,
    )

    result = rank_alerts_for_manual_review(
        [make_alert(mock_validator), make_alert(logos_validator)],
        [mock_validator, logos_validator],
        latest_scan_id=SCAN_ID,
        scan_changed_count=12,
    )
    family_by_key = {item["family_key"]: item for item in result["family_tasks"]}

    assert family_by_key["mock_trial_simulation_validation"]["source_boundary"] == (
        "active_source_read_only"
    )
    assert "active_source_read_only" in family_by_key["mock_trial_simulation_validation"]["blockers"]
    assert family_by_key["logos_route_validation_harness"]["review_posture"].startswith("Read-only")


def test_manual_task_queue_includes_workflow_guidance_boundaries():
    asset = make_asset(
        "dad-workflow",
        "workflow_parts",
        "git-projects/04_Digital_Assett_Directory/src/digital_asset_directory/workflow_parts.py",
        asset_type="workflow",
        value_score=61.9,
    )

    result = build_manual_task_queue(
        [make_alert(asset)],
        [asset],
        sample_workflow_guidance(),
        latest_scan_id=SCAN_ID,
        limit=10,
    )

    workflow = result["workflow_part_guidance"]
    assert result["candidate_only"] is True
    assert workflow["review_use_examples"][0]["sample_id"] == "workflow-part-review-001"
    assert workflow["missing_dataflow_tasks"][0]["missing_dataflow_note"] == "Needs fixtures."
    assert workflow["human_gated_tasks"][0]["sample_id"] == "workflow-part-review-002"
    assert workflow["false_positive_patterns"][0]["false_positive_reason"] == "Marker file only."

    text = manual_task_queue_markdown(result)
    assert "Local Research Support" in text
    assert "Red Team And Premortem" in text
    assert "source truth" in text


def test_manual_task_writer_outputs_generated_candidate_files(tmp_path: Path):
    asset = make_asset(
        "logos-validator",
        "validate_task_scope",
        "git-projects/03_World_View/logos-scripture-graph-repo/scripts/validate_task_scope.py",
        value_score=58.7,
    )

    result = write_manual_task_queue(
        tmp_path,
        [make_alert(asset)],
        [asset],
        sample_workflow_guidance(),
        latest_scan_id=SCAN_ID,
        limit=10,
    )

    report = Path(result["report"])
    payload = Path(result["payload"])
    assert report.exists()
    assert payload.exists()
    assert report.is_relative_to(tmp_path / "processed")
    assert payload.is_relative_to(tmp_path / "processed")
    assert result["candidate_only"] is True
    assert "Generated manual-review priorities only" in report.read_text(encoding="utf-8")
