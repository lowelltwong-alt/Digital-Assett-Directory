from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.lesson_action_queue import (
    PRIORITY_FORMULA,
    build_lesson_automation_approval_packet,
    build_lesson_automation_next_action_queue,
    build_lesson_automation_decision_template,
    build_lesson_automation_execution_plan,
    load_lesson_automation_decisions,
    update_lesson_automation_decision_record,
    write_lesson_automation_approval_packet_outputs,
    write_lesson_automation_decision_template_outputs,
    write_lesson_automation_decisions,
    write_lesson_automation_execution_plan_outputs,
    write_lesson_automation_next_action_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def seed_scope_outputs(repo_root: Path) -> None:
    reports = repo_root / "processed" / "reports"
    write_json(
        reports / "scan_coverage_cycle.json",
        {
            "cycle_entries": [
                {
                    "signal_family_id": "catalog_metadata",
                    "label": "Catalog metadata",
                    "cycle_order": 1,
                    "current_status": "covered_by_current_catalog",
                    "requires_human_approval": False,
                    "next_action": "Use existing catalog metadata first.",
                },
                {
                    "signal_family_id": "priority_content_extracts",
                    "label": "Priority content extracts",
                    "cycle_order": 2,
                    "current_status": "scoped_not_extracted",
                    "requires_human_approval": True,
                    "next_action": "Run a bounded content pass after approval.",
                },
                {
                    "signal_family_id": "repo_learning_events",
                    "label": "Repo-local learning events",
                    "cycle_order": 3,
                    "current_status": "installation_scope_ready",
                    "requires_human_approval": True,
                    "next_action": "Install files-only learning loops in selected repos.",
                },
                {
                    "signal_family_id": "governance_map_adoption",
                    "label": "Governance maps",
                    "cycle_order": 4,
                    "current_status": "adoption_scope_ready",
                    "requires_human_approval": True,
                    "next_action": "Review candidate repo families.",
                },
                {
                    "signal_family_id": "ci_and_release_artifacts",
                    "label": "CI and release artifacts",
                    "cycle_order": 5,
                    "current_status": "scoped_not_extracted",
                    "requires_human_approval": True,
                    "next_action": "Add a bounded artifact ingestion plan.",
                },
                {
                    "signal_family_id": "github_pr_issue_metadata",
                    "label": "GitHub PR and issue metadata",
                    "cycle_order": 6,
                    "current_status": "deferred_by_human_gate",
                    "requires_human_approval": True,
                    "next_action": "Keep deferred until token scope is approved.",
                },
            ]
        },
    )
    write_json(
        reports / "priority_content_extract_scope.json",
        {
            "summary": {"candidate_count": 100, "content_files_read": 0, "source_repos_mutated": 0},
            "repo_scopes": [
                {
                    "repo_key": "git-projects/repo-a",
                    "candidate_count": 8,
                    "candidates": [
                        {"primary_category_id": "ai_navigation"},
                        {"primary_category_id": "schemas_contracts"},
                    ],
                }
            ],
        },
    )
    write_json(
        reports / "repo_learning_loop_install_scope.json",
        {
            "summary": {
                "reported_repo_count": 30,
                "source_repos_mutated": 0,
                "content_files_read": 0,
            },
            "repo_candidates": [
                {
                    "repo_key": "git-projects/repo-a",
                    "priority_score": 95,
                    "install_status": "missing_learning_loop_surface",
                }
            ],
        },
    )
    write_json(
        reports / "governance_map_adoption_scope.json",
        {
            "summary": {"reported_repo_count": 20, "source_repos_mutated": 0, "content_files_read": 0},
            "repo_candidates": [
                {
                    "repo_key": "git-projects/family/control",
                    "priority_score": 85,
                    "adoption_status": "missing_governance_dependency_surface",
                    "family_key": "git-projects/family",
                }
            ],
        },
    )
    write_json(
        reports / "ci_release_artifact_scope.json",
        {
            "summary": {"candidate_count": 120, "content_files_read": 0, "source_repos_mutated": 0},
            "repo_scopes": [
                {
                    "repo_key": "git-projects/repo-a",
                    "candidate_count": 12,
                    "candidates": [{"primary_category_id": "ci_workflow_config"}],
                }
            ],
        },
    )


def test_next_action_queue_ranks_scope_ready_actions_with_explicit_gates(tmp_path: Path):
    seed_scope_outputs(tmp_path)

    result = build_lesson_automation_next_action_queue(
        tmp_path,
        generated_at=TIMESTAMP,
    )

    assert result["review_status"] == "generated_candidate"
    assert result["priority_formula"] == PRIORITY_FORMULA
    assert result["summary"]["source_repos_mutated"] == 0
    assert result["summary"]["content_files_read"] == 0
    assert result["summary"]["github_calls"] == 0
    assert result["summary"]["scope_files_present"] == [
        "ci_and_release_artifacts",
        "governance_map_adoption",
        "priority_content_extracts",
        "repo_learning_events",
    ]
    actions = result["actions"]
    assert [action["signal_family_id"] for action in actions[:2]] == [
        "priority_content_extracts",
        "repo_learning_events",
    ]
    priority = actions[0]
    assert priority["priority_score"] == 93.93
    assert priority["priority_components"] == {
        "approval_specificity": 1.0,
        "cycle_urgency": 0.833,
        "lesson_yield": 1.0,
        "safety_margin": 0.78,
        "scope_readiness": 1.0,
    }
    assert "approval-id" in priority["recommended_command_or_next_step"]
    assert all(action["review_status"] == "generated_candidate" for action in actions)
    assert all(action["applies_when"] for action in actions)
    assert all(action["does_not_apply_when"] for action in actions)
    assert all(action["danger_if_misapplied"] for action in actions)


def test_next_action_queue_writer_stays_under_processed_reports(tmp_path: Path):
    seed_scope_outputs(tmp_path)

    result = write_lesson_automation_next_action_outputs(
        tmp_path,
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"queue_markdown", "queue_json", "approval_prompt"}
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["queue_json"]).read_text(encoding="utf-8"))
    assert payload["medium_risk_review"]["risk_tier"] == "medium"
    assert "source repo mutation" in payload["intentionally_not_done"]
    assert "priority_content_extracts" in Path(outputs["queue_markdown"]).read_text(encoding="utf-8")


def test_decision_template_and_label_fail_closed_for_content_read(tmp_path: Path):
    seed_scope_outputs(tmp_path)
    queue = build_lesson_automation_next_action_queue(tmp_path, generated_at=TIMESTAMP)
    records = build_lesson_automation_decision_template(queue["actions"])

    assert records[0].sample_id == "lesson-automation-decision-001"
    assert records[0].signal_family_id == "priority_content_extracts"
    assert records[0].decision == "pending"
    assert records[0].review_status == "generated_candidate"

    with pytest.raises(ValueError, match="positive byte and file caps"):
        update_lesson_automation_decision_record(
            records,
            sample_id="lesson-automation-decision-001",
            reviewer="Lowell",
            decision="approve",
            reviewed_at=TIMESTAMP,
            approval_id="approval:test",
            approved_repo_keys=["git-projects/repo-a"],
            approved_categories=["ai_navigation"],
            allow_content_read=True,
            max_bytes_per_file=0,
            max_files=10,
        )

    updated_records, updated = update_lesson_automation_decision_record(
        records,
        sample_id="lesson-automation-decision-001",
        reviewer="Lowell",
        decision="approve",
        reviewed_at=TIMESTAMP,
        approval_id="approval:test",
        approved_repo_keys=["git-projects/repo-a"],
        approved_categories=["ai_navigation"],
        allow_content_read=True,
        max_bytes_per_file=20000,
        max_files=10,
        rationale="Bounded front-door review approved.",
    )

    assert updated.review_status == "reviewed"
    assert updated.allow_content_read is True
    assert updated.allow_source_mutation is False
    assert updated.redaction_required is True
    assert updated.approved_repo_keys == ["git-projects/repo-a"]
    assert updated.approved_categories == ["ai_navigation"]
    assert updated_records[0].decision == "approve"


def test_decision_template_writer_and_jsonl_round_trip(tmp_path: Path):
    seed_scope_outputs(tmp_path)

    result = write_lesson_automation_decision_template_outputs(
        tmp_path,
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"decision_template", "report_markdown", "report_json"}
    assert Path(outputs["decision_template"]).is_relative_to(tmp_path / "processed" / "learning")
    assert Path(outputs["report_markdown"]).is_relative_to(tmp_path / "processed" / "reports")
    records = load_lesson_automation_decisions(Path(outputs["decision_template"]))
    assert len(records) == 5
    assert records[0].evidence["generated_candidate_only"] is True

    write_lesson_automation_decisions(Path(outputs["decision_template"]), records)
    reloaded = load_lesson_automation_decisions(Path(outputs["decision_template"]))
    assert [record.sample_id for record in reloaded] == [record.sample_id for record in records]


def test_approval_packet_prepares_labels_without_applying_them(tmp_path: Path):
    seed_scope_outputs(tmp_path)
    template = write_lesson_automation_decision_template_outputs(
        tmp_path,
        generated_at=TIMESTAMP,
    )
    records = load_lesson_automation_decisions(Path(template["outputs"]["decision_template"]))

    packet = build_lesson_automation_approval_packet(
        tmp_path,
        records,
        generated_at=TIMESTAMP,
        repo_limit=1,
        max_bytes_per_file=20000,
        max_files=50,
    )

    assert packet["review_status"] == "generated_candidate"
    assert packet["summary"]["pending_count"] == 5
    assert packet["summary"]["recommended_approve_count"] == 1
    assert packet["summary"]["recommended_defer_count"] == 4
    assert packet["summary"]["labels_applied"] == 0
    assert packet["summary"]["commands_executed"] == 0
    assert packet["summary"]["content_files_read"] == 0
    assert packet["summary"]["source_repos_mutated"] == 0
    first = packet["approval_entries"][0]
    assert first["sample_id"] == "lesson-automation-decision-001"
    assert first["recommended_decision"] == "approve"
    assert first["approval_fields"]["approved_repo_keys"] == ["git-projects/repo-a"]
    assert first["approval_fields"]["approved_categories"] == [
        "ai_navigation",
        "schemas_contracts",
    ]
    assert "--allow-content-read" in first["label_command"]
    assert "--max-bytes-per-file 20000" in first["label_command"]
    assert "--max-files 50" in first["label_command"]
    assert all(record.decision == "pending" for record in records)


def test_approval_packet_writer_stays_under_processed_reports(tmp_path: Path):
    seed_scope_outputs(tmp_path)
    template = write_lesson_automation_decision_template_outputs(
        tmp_path,
        generated_at=TIMESTAMP,
    )

    result = write_lesson_automation_approval_packet_outputs(
        tmp_path,
        decisions_file=Path(template["outputs"]["decision_template"]),
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"packet_markdown", "packet_json"}
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["packet_json"]).read_text(encoding="utf-8"))
    assert payload["summary"]["labels_applied"] == 0
    assert payload["summary"]["commands_executed"] == 0
    assert "decision-label command execution" in payload["intentionally_not_done"]


def test_execution_plan_is_empty_until_decision_is_approved(tmp_path: Path):
    seed_scope_outputs(tmp_path)
    result = write_lesson_automation_decision_template_outputs(
        tmp_path,
        generated_at=TIMESTAMP,
    )
    records = load_lesson_automation_decisions(Path(result["outputs"]["decision_template"]))

    plan = build_lesson_automation_execution_plan(
        tmp_path,
        records,
        generated_at=TIMESTAMP,
    )

    assert plan["summary"]["approved_count"] == 0
    assert plan["summary"]["ready_for_manual_run_count"] == 0
    assert plan["summary"]["commands_executed"] == 0
    assert plan["summary"]["source_repos_mutated"] == 0
    assert plan["summary"]["content_files_read"] == 0
    assert plan["execution_entries"] == []


def test_execution_plan_generates_approved_content_command_without_running_it(tmp_path: Path):
    seed_scope_outputs(tmp_path)
    queue = build_lesson_automation_next_action_queue(tmp_path, generated_at=TIMESTAMP)
    records = build_lesson_automation_decision_template(queue["actions"])
    records, _updated = update_lesson_automation_decision_record(
        records,
        sample_id="lesson-automation-decision-001",
        reviewer="Lowell",
        decision="approve",
        reviewed_at=TIMESTAMP,
        approval_id="approval:test",
        approved_repo_keys=["git-projects/repo-a"],
        approved_categories=["ai_navigation"],
        allow_content_read=True,
        max_bytes_per_file=20000,
        max_files=10,
        rationale="Bounded front-door review approved.",
    )

    plan = build_lesson_automation_execution_plan(
        tmp_path,
        records,
        generated_at=TIMESTAMP,
    )

    assert plan["summary"]["approved_count"] == 1
    assert plan["summary"]["ready_for_manual_run_count"] == 1
    assert plan["summary"]["commands_executed"] == 0
    assert plan["summary"]["content_files_read"] == 0
    entry = plan["execution_entries"][0]
    assert entry["execution_status"] == "ready_for_manual_run"
    assert "priority-content-extract" in entry["command"]
    assert "--approval-id \"approval:test\"" in entry["command"]
    assert "--repo-key \"git-projects/repo-a\"" in entry["command"]
    assert "--category \"ai_navigation\"" in entry["command"]
    assert "--max-bytes-per-file 20000" in entry["command"]
    assert "--limit 10" in entry["command"]


def test_execution_plan_writer_stays_under_processed_reports(tmp_path: Path):
    seed_scope_outputs(tmp_path)
    template = write_lesson_automation_decision_template_outputs(
        tmp_path,
        generated_at=TIMESTAMP,
    )

    result = write_lesson_automation_execution_plan_outputs(
        tmp_path,
        decisions_file=Path(template["outputs"]["decision_template"]),
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"plan_markdown", "plan_json"}
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["plan_json"]).read_text(encoding="utf-8"))
    assert payload["summary"]["commands_executed"] == 0
    assert "command execution" in payload["intentionally_not_done"]
