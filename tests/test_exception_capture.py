from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from jsonschema.validators import validator_for
from typer.testing import CliRunner

from digital_asset_directory.cli import (
    _capture_audit_gap_count,
    _exception_backfill_approval_block_reason,
    _discover_exception_repos,
    _exception_backfill_policy_block_reason,
    _exception_record_policy_block_reason,
    app,
)
from digital_asset_directory.config import ExceptionRepoPolicy, MailRepoPolicy
from digital_asset_directory.exception_capture import (
    build_exception_capture_remediation_plan,
    build_exception_capture_gap_review_queue,
    build_exception_backfill_wave_plan,
    evaluate_exception_taxonomy_coverage,
    evaluate_capture_case,
    evaluate_capture_scenarios,
    load_capture_pattern_registry,
    load_capture_scenarios,
    suggest_exception_capture,
    write_exception_backfill_readiness,
    write_exception_backfill_wave_plan,
    write_exception_capture_gap_review_queue,
    write_exception_capture_remediation_plan,
    write_observed_capture_audit,
)
from digital_asset_directory.exceptions_lake import record_exception_event
from digital_asset_directory.mail_center import compose_mail

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    ROOT
    / "assets"
    / "coding-harnesses"
    / "exception-capture-completeness"
    / "examples"
    / "synthetic-capture-scenarios.json"
)
RUNNER = CliRunner()


def _phase6_gate(report: dict, gate_id: str) -> dict:
    for gate in report["phase6_machine_gate_evidence"]["gates"].values():
        if gate["supports_human_gate_id"] == gate_id:
            return gate
    raise KeyError(gate_id)


def _assert_machine_only_phase6_evidence(report: dict) -> None:
    for key, gate in report["phase6_machine_gate_evidence"]["gates"].items():
        assert key.startswith("machine-evidence:")
        assert gate["evidence_id"] == key
        assert gate["evidence_scope"] == "machine_only_not_roadmap_gate_evidence"
        assert gate["human_review_required"] is True
        assert gate["human_gate_satisfied"] is False
        assert "roadmap_gate_id" not in gate
        assert "status" not in gate
        assert gate["machine_status"] in {"passed", "failed"}


def _validate(schema_name: str, payload: dict) -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / registry["schemas"][schema_name]).read_text(encoding="utf-8"))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def test_exception_repo_policy_is_separate_from_mail_policy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(
        mail_repos=[
            MailRepoPolicy(
                id="mail-only",
                path=repo,
                alias="repo",
                mail_enabled=True,
            )
        ],
        exception_repos=[],
    )

    with pytest.raises(typer.BadParameter, match="exceptions.repos"):
        _discover_exception_repos(["all"], cfg, collect=True)
    with pytest.raises(typer.BadParameter, match="reviewed exceptions.repos"):
        _discover_exception_repos([str(repo)], cfg, collect=True)

    cfg.exception_repos = [
        ExceptionRepoPolicy(
            id="exception-enabled",
            path=repo,
            alias="repo",
            exceptions_enabled=True,
            collect_allowed=True,
        )
    ]

    assert _discover_exception_repos(["all"], cfg, collect=True) == [repo.resolve()]
    assert _discover_exception_repos(["repo"], cfg, collect=True) == [repo.resolve()]


def test_exception_repo_policy_blocks_collection_independently(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(
        mail_repos=[],
        exception_repos=[
            ExceptionRepoPolicy(
                id="blocked",
                path=repo,
                alias="repo",
                exceptions_enabled=True,
                collect_allowed=False,
                capture_audit_allowed=True,
            )
        ],
    )

    assert _discover_exception_repos(["all"], cfg, capture_audit=True) == [repo.resolve()]
    with pytest.raises(typer.BadParameter, match="blocked"):
        _discover_exception_repos(["repo"], cfg, collect=True)


def test_exception_repo_policy_blocks_explicit_capture_audit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(
        mail_repos=[],
        exception_repos=[
            ExceptionRepoPolicy(
                id="audit-blocked",
                path=repo,
                alias="repo",
                exceptions_enabled=True,
                collect_allowed=True,
                capture_audit_allowed=False,
            )
        ],
    )

    with pytest.raises(typer.BadParameter, match="audit-blocked"):
        _discover_exception_repos(["repo"], cfg, capture_audit=True)
    with pytest.raises(typer.BadParameter, match="exceptions.repos"):
        _discover_exception_repos(["all"], cfg, capture_audit=True)


def test_exception_backfill_policy_requires_reviewed_allowance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(
        exception_repos=[
            ExceptionRepoPolicy(
                id="backfill-blocked",
                path=repo,
                alias="repo",
                exceptions_enabled=True,
                backfill_allowed=False,
            )
        ],
    )

    reason = _exception_backfill_policy_block_reason(cfg, repo)

    assert reason == "backfill-blocked has backfill_allowed=false"


def test_exception_backfill_policy_blocks_write_protected_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(
        exception_repos=[
            ExceptionRepoPolicy(
                id="protected",
                path=repo,
                alias="repo",
                exceptions_enabled=True,
                backfill_allowed=True,
                write_protected=True,
            )
        ],
    )

    reason = _exception_backfill_policy_block_reason(cfg, repo / "docs")

    assert reason == "protected is write_protected for exception backfill"


def test_exception_backfill_approval_requires_reviewed_policy_id(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(
        exception_repos=[
            ExceptionRepoPolicy(
                id="protected",
                path=repo,
                alias="repo",
                exceptions_enabled=True,
                backfill_allowed=False,
                write_protected=True,
                approved_approval_ids=["APPROVED-EXCEPTION-BACKFILL"],
            )
        ],
    )

    fake_reason = _exception_backfill_approval_block_reason(cfg, repo, "FAKE")
    approved_reason = _exception_backfill_approval_block_reason(
        cfg,
        repo,
        "APPROVED-EXCEPTION-BACKFILL",
    )

    assert "not approved" in fake_reason
    assert approved_reason == ""


def test_exception_backfill_approval_rejects_unreviewed_roots(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(exception_repos=[])

    reason = _exception_backfill_approval_block_reason(cfg, repo, "APPROVED")

    assert reason == "root is not covered by reviewed exceptions.repos policy"


def test_exception_record_policy_blocks_write_protected_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = SimpleNamespace(
        exception_repos=[
            ExceptionRepoPolicy(
                id="protected",
                path=repo,
                alias="repo",
                exceptions_enabled=True,
                write_protected=True,
            )
        ],
    )

    reason = _exception_record_policy_block_reason(cfg, repo)

    assert reason == "protected is write_protected for exception recording"


def test_strict_capture_audit_counts_uncorrelated_and_unverified_statuses() -> None:
    result = {
        "status_counts": {
            "type_present_uncorrelated": 2,
            "emission_unverified": 3,
            "capture_surface_version_unknown": 1,
        }
    }

    assert _capture_audit_gap_count(result, strict=False) == 1
    assert _capture_audit_gap_count(result, strict=True) == 6


def test_capture_audit_gap_count_fails_closed_on_truncated_scan() -> None:
    result = {
        "status_counts": {},
        "repos": [
            {
                "candidate_path_scan": {
                    "truncated": True,
                    "scanned_file_count": 50,
                    "limit": 50,
                }
            }
        ],
    }

    assert _capture_audit_gap_count(result, strict=False) == 1
    assert _capture_audit_gap_count(result, strict=True) == 1


def test_capture_registry_and_scenarios_validate() -> None:
    _validate("exception_capture_pattern_registry", load_capture_pattern_registry(ROOT))
    _validate("exception_capture_scenarios", load_capture_scenarios(SCENARIOS))


def test_synthetic_scenarios_cover_required_pattern_families() -> None:
    scenarios = load_capture_scenarios(SCENARIOS)
    actual = {case["pattern_family"] for case in scenarios["cases"]}

    assert set(scenarios["required_pattern_families"]) <= actual


def test_synthetic_scenarios_pin_required_fields_for_emitted_packets() -> None:
    scenarios = load_capture_scenarios(SCENARIOS)

    for case in scenarios["cases"]:
        expected = case["expected"]
        if expected["packet_classes"] == ["no_packet"]:
            assert expected["required_fields"] == []
        else:
            assert expected["required_fields"], case["scenario_id"]


def test_capture_completeness_scenarios_all_pass(tmp_path: Path) -> None:
    report = evaluate_capture_scenarios(ROOT, SCENARIOS, output=tmp_path / "report.json")

    _assert_machine_only_phase6_evidence(report)
    assert report["failed_count"] == 0
    assert report["missing_required_pattern_families"] == []
    assert report["missing_reviewed_rule_ids"] == []
    assert report["undeclared_matched_rule_ids"] == []
    assert report["unknown_declared_rule_ids"] == []
    assert report["covered_reviewed_rule_count"] == report["reviewed_rule_count"]
    assert _phase6_gate(
        report,
        "phase-6-capture-completeness-harness-reviewed",
    )["machine_status"] == "passed"
    lawfirm_gate = _phase6_gate(
        report,
        "phase-6-lawfirm-intake-missed-capture-regression",
    )
    assert lawfirm_gate["machine_status"] == "passed"
    assert lawfirm_gate["human_gate_satisfied"] is False
    assert lawfirm_gate["evidence"]["observed_outbox_compared"]
    pattern_gate = _phase6_gate(
        report,
        "phase-6-pattern-update-simulation-reviewed",
    )
    assert pattern_gate["machine_status"] == "passed"
    assert pattern_gate["evidence"]["missing_update_pattern_families"] == []
    assert pattern_gate["evidence"]["missing_update_vectors"] == []
    assert {
        "dad_needs_registry",
        "dad_offerings_registry",
        "downstream_template",
        "exception_taxonomy",
        "language_coding_advantage_registry",
    } == set(pattern_gate["evidence"]["covered_update_vectors"])
    assert {
        "asset-pointer-created",
        "lawfirm-review-issue-missed-capture",
        "language-frontier-signal",
        "mail-pattern-update-required",
        "new-exception-pattern-needed",
        "template-managed-block-change",
        "learning-loop-candidate",
    } <= set(pattern_gate["evidence"]["update_required_scenario_ids"])
    family_gate = _phase6_gate(
        report,
        "phase-6-all-asset-pattern-coverage-reviewed",
    )
    assert family_gate["machine_status"] == "passed"
    assert family_gate["evidence"]["missing_required_pattern_families"] == []
    assert family_gate["evidence"]["missing_passing_required_pattern_families"] == []
    sensitive_gate = _phase6_gate(
        report,
        "phase-6-sensitive-payload-negative-tests-reviewed",
    )
    assert sensitive_gate["machine_status"] == "passed"
    assert sensitive_gate["evidence"]["missing_negative_controls"] == []
    assert sensitive_gate["evidence"]["missing_negative_control_blocks"] == []
    assert {
        "contains_hidden_chain_of_thought",
        "contains_private_rows",
        "contains_prompt_injection_like_text",
        "contains_raw_log_blob",
        "contains_secret_or_pii",
    } <= set(sensitive_gate["evidence"]["covered_negative_controls"])
    blocked_by_control = sensitive_gate["evidence"]["blocked_negative_control_coverage"]
    assert blocked_by_control["contains_secret_or_pii"][0]["scenario_id"] == (
        "secret-payload-suppressed"
    )
    assert blocked_by_control["contains_private_rows"][0]["scenario_id"] == (
        "private-row-payload-suppressed"
    )
    assert blocked_by_control["contains_raw_log_blob"][0]["scenario_id"] == (
        "raw-log-payload-suppressed"
    )
    assert blocked_by_control["contains_hidden_chain_of_thought"][0]["scenario_id"] == (
        "hidden-reasoning-payload-suppressed"
    )
    assert blocked_by_control["contains_prompt_injection_like_text"][0]["scenario_id"] == (
        "unsafe-positive-match-suppressed"
    )
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()


def test_phase6_pattern_update_gate_fails_without_update_scenarios(
    tmp_path: Path,
) -> None:
    scenarios = load_capture_scenarios(SCENARIOS)
    scenarios["cases"] = [
        case for case in scenarios["cases"] if not case["expected"].get("update_required")
    ]
    scenario_path = tmp_path / "no-update-scenarios.json"
    scenario_path.write_text(json.dumps(scenarios), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    gate = _phase6_gate(report, "phase-6-pattern-update-simulation-reviewed")

    assert gate["machine_status"] == "failed"
    assert set(gate["evidence"]["missing_update_pattern_families"]) == {
        "workflow",
        "mail_pattern",
        "exception_pattern",
        "learning_loop_candidate",
    }
    assert set(gate["evidence"]["missing_update_vectors"]) == {
        "dad_needs_registry",
        "dad_offerings_registry",
        "downstream_template",
        "exception_taxonomy",
    }
    assert gate["evidence"]["update_required_scenario_ids"] == []


def test_phase6_family_gate_requires_passing_family_case(tmp_path: Path) -> None:
    scenarios = load_capture_scenarios(SCENARIOS)
    for case in scenarios["cases"]:
        if case.get("observed"):
            case.pop("observed")
    bad_case = next(
        case for case in scenarios["cases"] if case["pattern_family"] == "harness"
    )
    bad_case["expected"]["required_fields"] = ["missing_required_field"]
    scenario_path = tmp_path / "bad-family-scenarios.json"
    scenario_path.write_text(json.dumps(scenarios), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    gate = _phase6_gate(report, "phase-6-all-asset-pattern-coverage-reviewed")

    assert report["missing_required_pattern_families"] == []
    assert gate["machine_status"] == "failed"
    assert gate["evidence"]["missing_passing_required_pattern_families"] == ["harness"]


def test_phase6_sensitive_gate_requires_declared_negative_control_set(
    tmp_path: Path,
) -> None:
    scenarios = load_capture_scenarios(SCENARIOS)
    for case in scenarios["cases"]:
        case["negative_controls"] = [
            control
            for control in case.get("negative_controls", [])
            if control != "contains_raw_log_blob"
        ]
    scenario_path = tmp_path / "missing-negative-control.json"
    scenario_path.write_text(json.dumps(scenarios), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    gate = _phase6_gate(report, "phase-6-sensitive-payload-negative-tests-reviewed")

    assert gate["machine_status"] == "failed"
    assert gate["evidence"]["missing_negative_controls"] == ["contains_raw_log_blob"]
    assert gate["evidence"]["missing_negative_control_blocks"] == ["contains_raw_log_blob"]


def test_phase6_sensitive_gate_requires_blocked_case_per_negative_control(
    tmp_path: Path,
) -> None:
    scenarios = load_capture_scenarios(SCENARIOS)
    raw_log_case = next(
        case for case in scenarios["cases"] if case["scenario_id"] == "raw-log-payload-suppressed"
    )
    raw_log_case.pop("payload_samples")
    scenario_path = tmp_path / "missing-raw-log-block.json"
    scenario_path.write_text(json.dumps(scenarios), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    gate = _phase6_gate(report, "phase-6-sensitive-payload-negative-tests-reviewed")

    assert gate["machine_status"] == "failed"
    assert gate["evidence"]["missing_negative_controls"] == []
    assert gate["evidence"]["missing_negative_control_blocks"] == ["contains_raw_log_blob"]


def test_exception_taxonomy_coverage_distinguishes_manual_and_signal_routes(
    tmp_path: Path,
) -> None:
    report = evaluate_exception_taxonomy_coverage(
        ROOT,
        SCENARIOS,
        output=tmp_path / "taxonomy-coverage.json",
    )

    _assert_machine_only_phase6_evidence(report)
    assert report["methodology_ref"] == "registry/exception-event-type-registry.json"
    assert report["methodology_hash"].startswith("sha256:")
    assert report["event_type_count"] >= 50
    assert report["reviewed_unrouted_event_types"] == []
    assert report["learnable_unrouted_event_types"] == []
    assert report["capture_rule_events_missing_synthetic_cases"] == []
    assert report["route_kind_counts"]["capture_rule"] >= 1
    assert report["route_kind_counts"]["backfill_path_signal"] >= 1
    assert report["taxonomy_review_summary"]["category_count"] >= 10
    assert report["taxonomy_review_summary"]["coverage_status_counts"] == (
        report["coverage_status_counts"]
    )
    category_backfill_count = sum(
        row["backfill_path_signal_count"]
        for row in report["category_route_summary"].values()
    )
    assert category_backfill_count == report["route_kind_counts"]["backfill_path_signal"]
    category_backfill_events = {
        event_type
        for row in report["category_route_summary"].values()
        for event_type in row["backfill_path_signal_event_types"]
    }
    assert "artifact_registration_drift" in category_backfill_events
    assert "security_privacy" in report["category_route_summary"]
    security_privacy = report["category_route_summary"]["security_privacy"]
    assert security_privacy["capture_rule_count"] == 3
    assert security_privacy["direct_record_only_count"] == 0
    assert security_privacy["capture_rule_event_types"] == [
        "prompt_injection_like_payload",
        "raw_blob_rejected",
        "secret_or_pii_detected",
    ]
    dad_recommendation = report["category_route_summary"]["dad_recommendation"]
    assert dad_recommendation["capture_rule_count"] == 3
    assert dad_recommendation["direct_record_only_count"] == 0
    assert report["automated_route_count"] >= 51
    assert report["coverage_status_counts"]["capture_rule_with_synthetic_case"] >= 26
    assert report["taxonomy_review_summary"][
        "high_or_critical_direct_record_only_event_types"
    ] == []
    newly_covered_event_types = {
        "duplicate_mail_delivery",
        "malformed_jsonl",
        "pytest_performance_hotspot",
        "validation_command_missing",
    }
    assert not newly_covered_event_types.intersection(report["manual_only_event_types"])
    assert report["manual_only_event_types"] == []
    assert "malformed_jsonl" in report["category_route_summary"]["schema_config"][
        "capture_rule_event_types"
    ]
    assert report["category_route_summary"]["schema_config"]["direct_record_only_count"] == 0
    assert "duplicate_mail_delivery" in report["category_route_summary"]["mail_enrollment"][
        "capture_rule_event_types"
    ]
    assert report["category_route_summary"]["mail_enrollment"]["direct_record_only_count"] == 0
    assert "pytest_performance_hotspot" in report["category_route_summary"]["harness_parity"][
        "capture_rule_event_types"
    ]
    assert report["category_route_summary"]["harness_parity"]["direct_record_only_count"] == 0
    assert "validation_command_missing" in report["category_route_summary"]["roadmap_validation"][
        "capture_rule_event_types"
    ]
    assert (
        report["category_route_summary"]["roadmap_validation"]["direct_record_only_count"]
        == 0
    )
    assert "dirty_worktree_block" in report["category_route_summary"]["repo_state"][
        "capture_rule_event_types"
    ]
    assert "protected_repo_write_block" in report["category_route_summary"]["governance"][
        "capture_rule_event_types"
    ]
    assert "private_origin_public_target" in report["category_route_summary"][
        "public_private"
    ]["capture_rule_event_types"]
    assert "stale_report" in report["category_route_summary"]["data_integrity"][
        "capture_rule_event_types"
    ]
    attention_ids = {
        item["attention_id"]
        for item in report["taxonomy_review_summary"]["review_attention"]
    }
    assert "high_or_critical_direct_record_only" not in attention_ids
    assert "categories_without_capture_rules" in attention_ids
    categories_without_capture = next(
        item["categories"]
        for item in report["taxonomy_review_summary"]["review_attention"]
        if item["attention_id"] == "categories_without_capture_rules"
    )
    assert not {
        "harness_parity",
        "mail_enrollment",
        "roadmap_validation",
        "schema_config",
    }.intersection(categories_without_capture)
    assert "failed_command" not in report["manual_only_event_types"]
    assert "tool_unavailable" not in report["manual_only_event_types"]
    assert "dirty_worktree_block" not in report["manual_only_event_types"]
    assert "private_origin_public_target" not in report["manual_only_event_types"]
    assert "protected_repo_write_block" not in report["manual_only_event_types"]
    assert "stale_report" not in report["manual_only_event_types"]
    assert "validation_command_missing" not in report["manual_only_event_types"]
    taxonomy_gate = _phase6_gate(report, "phase-6-taxonomy-route-coverage-reviewed")
    assert taxonomy_gate["machine_status"] == "passed"
    assert taxonomy_gate["human_gate_satisfied"] is False
    assert taxonomy_gate["evidence"]["unrouted_event_types"] == []
    assert (tmp_path / "taxonomy-coverage.json").exists()
    assert (tmp_path / "taxonomy-coverage.md").exists()


def test_taxonomy_coverage_reports_capture_rule_without_scenario(
    tmp_path: Path,
) -> None:
    scenarios = load_capture_scenarios(SCENARIOS)
    scenarios["cases"] = [
        case for case in scenarios["cases"] if case["scenario_id"] != "tool-unavailable-metadata"
    ]
    scenario_path = tmp_path / "missing-tool-scenario.json"
    scenario_path.write_text(json.dumps(scenarios), encoding="utf-8")

    report = evaluate_exception_taxonomy_coverage(
        ROOT,
        scenario_path,
        output=tmp_path / "taxonomy-coverage.json",
    )

    assert "tool_unavailable" in report["capture_rule_events_missing_synthetic_cases"]
    tool_row = next(
        row for row in report["events"] if row["event_type"] == "tool_unavailable"
    )
    assert tool_row["coverage_status"] == "capture_rule_missing_synthetic_case"


def test_capture_completeness_fails_when_reviewed_rule_has_no_scenario(
    tmp_path: Path,
) -> None:
    scenarios = load_capture_scenarios(SCENARIOS)
    scenarios["cases"] = [
        case
        for case in scenarios["cases"]
        if case["scenario_id"] != "artifact-registration-drift"
    ]
    scenario_path = tmp_path / "missing-rule-scenarios.json"
    scenario_path.write_text(json.dumps(scenarios), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")

    assert "exception-capture-rule:artifact-registration-drift" in report[
        "missing_reviewed_rule_ids"
    ]
    assert report["missing_required_pattern_families"] == []


def test_capture_case_fails_when_declared_rule_coverage_does_not_match() -> None:
    registry = load_capture_pattern_registry(ROOT)
    scenarios = load_capture_scenarios(SCENARIOS)
    case = next(item for item in scenarios["cases"] if item["scenario_id"] == "artifact-registration-drift")
    bad_case = json.loads(json.dumps(case))
    bad_case["covered_rule_ids"] = ["exception-capture-rule:governance-map-drift"]

    result = evaluate_capture_case(bad_case, registry)

    assert not result["passed"]
    assert result["comparisons"]["covered_rule_ids"] is False
    assert result["matched_rules"] == ["exception-capture-rule:artifact-registration-drift"]


def test_lawfirm_missed_capture_case_emits_mail_and_exception() -> None:
    registry = load_capture_pattern_registry(ROOT)
    scenarios = load_capture_scenarios(SCENARIOS)
    case = next(item for item in scenarios["cases"] if item["scenario_id"] == "lawfirm-review-issue-missed-capture")

    result = evaluate_capture_case(case, registry, scenario_base=SCENARIOS.parent)

    assert result["passed"]
    assert result["actual"]["packet_classes"] == ["exception_event", "ordinary_mail"]
    assert result["actual"]["mail_message_types"] == ["workflow_suggestion"]
    assert result["actual"]["event_types"] == ["review_finding"]
    assert result["actual"]["required_fields"] == [
        "exception_mapping_gap",
        "issue_classes",
        "validation_refs",
        "workflow_summary",
    ]
    assert result["update_required"]
    assert result["observed"]["passed"]


def test_global_block_signals_suppress_positive_matches() -> None:
    registry = load_capture_pattern_registry(ROOT)
    case = {
        "scenario_id": "secret-bearing-asset",
        "pattern_family": "asset",
        "repo_capture_surface_version": "0.2.0",
        "signals": ["new_reusable_asset", "cross_repo_reuse", "asset_docs", "contains_secret_or_pii"],
        "expected": {
            "packet_classes": ["no_packet"],
            "event_types": [],
            "mail_message_types": [],
            "capture_contracts": [],
            "required_fields": [],
            "update_required": False,
            "blocked": True,
            "blocked_reason": "global_block_signal:contains_secret_or_pii",
        },
    }

    result = evaluate_capture_case(case, registry)

    assert result["passed"]
    assert result["actual"]["blocked"]
    assert result["actual"]["packet_classes"] == ["no_packet"]


def test_payload_screening_blocks_unsafe_sample_without_manual_signal() -> None:
    registry = load_capture_pattern_registry(ROOT)
    credential_like = "api" + "_key=" + "example-value"
    case = {
        "scenario_id": "unsafe-payload",
        "pattern_family": "asset",
        "repo_capture_surface_version": "0.2.0",
        "signals": ["new_reusable_asset", "cross_repo_reuse", "asset_docs"],
        "payload_samples": [{"field": "safe_summary", "text": credential_like}],
        "expected": {
            "packet_classes": ["no_packet"],
            "event_types": [],
            "mail_message_types": [],
            "capture_contracts": [],
            "required_fields": [],
            "update_required": False,
            "blocked": True,
            "blocked_reason": "payload_screen:credential_or_pii_pattern",
        },
    }

    result = evaluate_capture_case(case, registry)

    assert result["passed"]
    assert result["matched_rules"] == ["exception-capture-rule:asset-suggestion"]
    assert result["actual"]["packet_classes"] == ["no_packet"]


def test_observed_outboxes_are_compared_against_expected_packets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Structured review workflow should be sent to DAD.",
        payload={
            "exception_mapping_gap": "metadata-only mapping gap",
            "issue_classes": ["review_finding"],
            "validation_refs": ["docs/review.md"],
            "workflow_summary": "metadata-only",
        },
        evidence=["docs/review.md"],
        suggested_actions=["Review as candidate workflow."],
        allow_similar=True,
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Structured review workflow exposed an exception-lake mapping gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review.md"],
    )
    scenario = {
        "schema_version": "0.1.0",
        "scenario_set_id": "observed-lawfirm-style",
        "target_registry": "registry/exception-capture-pattern-registry.json",
        "required_pattern_families": ["workflow"],
        "cases": [
            {
                "scenario_id": "observed-lawfirm-style",
                "pattern_family": "workflow",
                "description": "Observed repo outboxes contain both workflow mail and review exception.",
                "repo_capture_surface_version": "0.2.0",
                "signals": [
                    "structured_review_issue_workflow",
                    "exception_lake_mapping_gap",
                    "schema_model_cli_tests_docs",
                ],
                "expected": {
                    "packet_classes": ["exception_event", "ordinary_mail"],
                    "event_types": ["review_finding"],
                    "mail_message_types": ["workflow_suggestion"],
                    "capture_contracts": ["review_finding"],
                    "required_fields": [
                        "exception_mapping_gap",
                        "issue_classes",
                        "validation_refs",
                        "workflow_summary",
                    ],
                    "update_required": False,
                    "blocked": False,
                },
                "negative_controls": [],
                "observed": {
                    "mail_outbox": str(repo / ".digital-asset" / "mail" / "outbox.jsonl"),
                    "exception_outbox": str(repo / ".digital-asset" / "exceptions" / "outbox.jsonl"),
                },
                "source_context": {
                    "repo_visibility": "private",
                    "public_facing": False,
                    "notes": "Temp repo generated observed outboxes through DAD helpers.",
                },
                "review_status": "reviewed",
            }
        ],
        "authority_boundary": "Observed fixture compares JSONL outboxes only.",
    }
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    case = report["cases"][0]

    assert report["failed_count"] == 0
    assert report["observed_case_count"] == 1
    assert case["observed"]["passed"]
    assert case["observed"]["actual"]["packet_classes"] == [
        "exception_event",
        "ordinary_mail",
    ]


def test_observed_outboxes_fail_when_required_fields_are_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Structured review workflow should be sent to DAD.",
        payload={
            "issue_classes": ["review_finding"],
            "validation_refs": ["docs/review.md"],
            "workflow_summary": "metadata-only",
        },
        evidence=["docs/review.md"],
        suggested_actions=["Review as candidate workflow."],
        allow_similar=True,
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Structured review workflow exposed an exception-lake mapping gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review.md"],
    )
    scenario = {
        "schema_version": "0.1.0",
        "scenario_set_id": "observed-missing-required-fields",
        "target_registry": "registry/exception-capture-pattern-registry.json",
        "required_pattern_families": ["workflow"],
        "cases": [
            {
                "scenario_id": "observed-missing-required-fields",
                "pattern_family": "workflow",
                "description": "Observed outboxes have the right packet labels but omit a required field.",
                "repo_capture_surface_version": "0.2.0",
                "signals": [
                    "structured_review_issue_workflow",
                    "exception_lake_mapping_gap",
                    "schema_model_cli_tests_docs",
                ],
                "expected": {
                    "packet_classes": ["exception_event", "ordinary_mail"],
                    "event_types": ["review_finding"],
                    "mail_message_types": ["workflow_suggestion"],
                    "capture_contracts": ["review_finding"],
                    "required_fields": [
                        "exception_mapping_gap",
                        "issue_classes",
                        "validation_refs",
                        "workflow_summary",
                    ],
                    "update_required": False,
                    "blocked": False,
                },
                "negative_controls": [],
                "observed": {
                    "mail_outbox": str(repo / ".digital-asset" / "mail" / "outbox.jsonl"),
                    "exception_outbox": str(repo / ".digital-asset" / "exceptions" / "outbox.jsonl"),
                },
                "source_context": {
                    "repo_visibility": "private",
                    "public_facing": False,
                    "notes": "Temp repo intentionally omits exception_mapping_gap.",
                },
                "review_status": "reviewed",
            }
        ],
        "authority_boundary": "Observed fixture compares JSONL outboxes only.",
    }
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    case = report["cases"][0]

    assert report["failed_count"] == 1
    assert case["comparisons"]["required_fields"]
    assert case["observed"]["comparisons"]["required_fields"] is False
    assert case["observed"]["actual"]["required_fields"] == [
        "issue_classes",
        "validation_refs",
        "workflow_summary",
    ]


def test_observed_required_fields_must_be_on_one_matching_packet(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Structured review workflow should be sent to DAD.",
        payload={
            "issue_classes": ["review_finding"],
            "validation_refs": ["docs/review.md"],
            "workflow_summary": "metadata-only",
        },
        evidence=["docs/review.md"],
        suggested_actions=["Review as candidate workflow."],
        allow_similar=True,
    )
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="A separate partial row cannot complete the first row.",
        payload={"exception_mapping_gap": "metadata-only mapping gap"},
        evidence=["docs/other-review.md"],
        suggested_actions=["Review as candidate workflow."],
        allow_similar=True,
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Structured review workflow exposed an exception-lake mapping gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review.md"],
    )
    scenario = {
        "schema_version": "0.1.0",
        "scenario_set_id": "observed-split-required-fields",
        "target_registry": "registry/exception-capture-pattern-registry.json",
        "required_pattern_families": ["workflow"],
        "cases": [
            {
                "scenario_id": "observed-split-required-fields",
                "pattern_family": "workflow",
                "description": "Observed outboxes split required fields across matching rows.",
                "repo_capture_surface_version": "0.2.0",
                "signals": [
                    "structured_review_issue_workflow",
                    "exception_lake_mapping_gap",
                    "schema_model_cli_tests_docs",
                ],
                "expected": {
                    "packet_classes": ["exception_event", "ordinary_mail"],
                    "event_types": ["review_finding"],
                    "mail_message_types": ["workflow_suggestion"],
                    "capture_contracts": ["review_finding"],
                    "required_fields": [
                        "exception_mapping_gap",
                        "issue_classes",
                        "validation_refs",
                        "workflow_summary",
                    ],
                    "update_required": False,
                    "blocked": False,
                },
                "negative_controls": [],
                "observed": {
                    "mail_outbox": str(repo / ".digital-asset" / "mail" / "outbox.jsonl"),
                    "exception_outbox": str(repo / ".digital-asset" / "exceptions" / "outbox.jsonl"),
                },
                "source_context": {
                    "repo_visibility": "private",
                    "public_facing": False,
                    "notes": "No single workflow_suggestion row contains all required metadata.",
                },
                "review_status": "reviewed",
            }
        ],
        "authority_boundary": "Observed fixture compares JSONL outboxes only.",
    }
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    case = report["cases"][0]

    assert report["failed_count"] == 1
    assert case["observed"]["comparisons"]["required_fields"] is False
    assert case["observed"]["actual"]["required_fields"] == [
        "issue_classes",
        "validation_refs",
        "workflow_summary",
    ]


def test_observed_required_fields_reject_blank_values(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text(
        json.dumps(
            {
                "message_type": "workflow_suggestion",
                "payload": {
                    "exception_mapping_gap": "",
                    "issue_classes": ["review_finding"],
                    "validation_refs": ["docs/review.md"],
                    "workflow_summary": "metadata-only",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Structured review workflow exposed an exception-lake mapping gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review.md"],
    )
    scenario = {
        "schema_version": "0.1.0",
        "scenario_set_id": "observed-blank-required-field",
        "target_registry": "registry/exception-capture-pattern-registry.json",
        "required_pattern_families": ["workflow"],
        "cases": [
            {
                "scenario_id": "observed-blank-required-field",
                "pattern_family": "workflow",
                "description": "Observed outbox has a blank required field.",
                "repo_capture_surface_version": "0.2.0",
                "signals": [
                    "structured_review_issue_workflow",
                    "exception_lake_mapping_gap",
                    "schema_model_cli_tests_docs",
                ],
                "expected": {
                    "packet_classes": ["exception_event", "ordinary_mail"],
                    "event_types": ["review_finding"],
                    "mail_message_types": ["workflow_suggestion"],
                    "capture_contracts": ["review_finding"],
                    "required_fields": [
                        "exception_mapping_gap",
                        "issue_classes",
                        "validation_refs",
                        "workflow_summary",
                    ],
                    "update_required": False,
                    "blocked": False,
                },
                "negative_controls": [],
                "observed": {
                    "mail_outbox": str(outbox),
                    "exception_outbox": str(repo / ".digital-asset" / "exceptions" / "outbox.jsonl"),
                },
                "source_context": {
                    "repo_visibility": "private",
                    "public_facing": False,
                    "notes": "Blank required fields do not satisfy the contract.",
                },
                "review_status": "reviewed",
            }
        ],
        "authority_boundary": "Observed fixture compares JSONL outboxes only.",
    }
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    case = report["cases"][0]

    assert report["failed_count"] == 1
    assert "exception_mapping_gap" not in case["observed"]["actual"]["required_fields"]


def test_observed_outbox_payload_screening_blocks_secret_like_text(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text(
        json.dumps(
            {
                "message_type": "workflow_suggestion",
                "payload": {
                    "exception_mapping_gap": "metadata-only mapping gap",
                    "issue_classes": ["review_finding"],
                    "validation_refs": ["docs/review.md"],
                    "workflow_summary": "metadata-only",
                    "safe_summary": "api_key=example-value",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Structured review workflow exposed an exception-lake mapping gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review.md"],
    )
    scenario = {
        "schema_version": "0.1.0",
        "scenario_set_id": "observed-unsafe-payload",
        "target_registry": "registry/exception-capture-pattern-registry.json",
        "required_pattern_families": ["workflow"],
        "cases": [
            {
                "scenario_id": "observed-unsafe-payload",
                "pattern_family": "workflow",
                "description": "Observed outbox carries secret-like text.",
                "repo_capture_surface_version": "0.2.0",
                "signals": [
                    "structured_review_issue_workflow",
                    "exception_lake_mapping_gap",
                    "schema_model_cli_tests_docs",
                ],
                "expected": {
                    "packet_classes": ["exception_event", "ordinary_mail"],
                    "event_types": ["review_finding"],
                    "mail_message_types": ["workflow_suggestion"],
                    "capture_contracts": ["review_finding"],
                    "required_fields": [
                        "exception_mapping_gap",
                        "issue_classes",
                        "validation_refs",
                        "workflow_summary",
                    ],
                    "update_required": False,
                    "blocked": False,
                },
                "negative_controls": [],
                "observed": {
                    "mail_outbox": str(outbox),
                    "exception_outbox": str(repo / ".digital-asset" / "exceptions" / "outbox.jsonl"),
                },
                "source_context": {
                    "repo_visibility": "private",
                    "public_facing": False,
                    "notes": "Observed payload screening is part of capture completeness.",
                },
                "review_status": "reviewed",
            }
        ],
        "authority_boundary": "Observed fixture compares JSONL outboxes only.",
    }
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    case = report["cases"][0]

    assert report["failed_count"] == 1
    assert case["observed"]["comparisons"]["required_fields"]
    assert any("credential_or_pii_pattern" in error for error in case["observed"]["errors"])


def test_observed_fix_outcomes_require_valid_fix_outcome_row(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outcomes = repo / "processed" / "exceptions" / "fix-outcomes" / "outcomes.jsonl"
    outcomes.parent.mkdir(parents=True)
    outcomes.write_text(
        json.dumps(
            {
                "event_id": "dad:exception-event:fake",
                "fix_type": "fixed",
                "lesson_candidate_limits": "metadata-only",
                "validation_refs": ["python -m pytest tests/test_fix.py"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    scenario = {
        "schema_version": "0.1.0",
        "scenario_set_id": "observed-invalid-fix-outcome",
        "target_registry": "registry/exception-capture-pattern-registry.json",
        "required_pattern_families": ["fix_outcome"],
        "cases": [
            {
                "scenario_id": "observed-invalid-fix-outcome",
                "pattern_family": "fix_outcome",
                "description": "A partial outcome-looking row is not a real fix outcome.",
                "repo_capture_surface_version": "0.2.0",
                "signals": ["fix_outcome_recorded", "validation_passed"],
                "expected": {
                    "packet_classes": ["fix_outcome"],
                    "event_types": [],
                    "mail_message_types": [],
                    "capture_contracts": ["fix_outcome"],
                "required_fields": [
                    "event_id",
                    "decision",
                    "validation_status",
                    "validation_refs",
                    "regression_test_refs",
                    "owner_authority",
                    "event_lookup_status",
                    "remaining_risks",
                ],
                    "update_required": False,
                    "blocked": False,
                },
                "negative_controls": [],
                "observed": {"fix_outcomes": str(outcomes)},
                "source_context": {
                    "repo_visibility": "internal",
                    "public_facing": False,
                    "notes": "Missing fix_id and decision must prevent false-green.",
                },
                "review_status": "reviewed",
            }
        ],
        "authority_boundary": "Observed fixture compares JSONL outboxes only.",
    }
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

    report = evaluate_capture_scenarios(ROOT, scenario_path, output=tmp_path / "report.json")
    case = report["cases"][0]

    assert report["failed_count"] == 1
    assert case["observed"]["actual"]["packet_classes"] == ["no_packet"]
    assert case["observed"]["actual"]["capture_contracts"] == []
    assert case["observed"]["actual"]["required_fields"] == []


def test_pattern_update_scenario_marks_old_repo_surface_stale() -> None:
    registry = load_capture_pattern_registry(ROOT)
    scenarios = load_capture_scenarios(SCENARIOS)
    case = next(item for item in scenarios["cases"] if item["scenario_id"] == "mail-pattern-update-required")

    result = evaluate_capture_case(case, registry)

    assert result["passed"]
    assert result["update_required"]
    assert "taxonomy_suggestion" in result["actual"]["mail_message_types"]
    assert result["actual"]["required_fields"] == [
        "affected_message_type",
        "mail_contract_gap",
        "update_path",
    ]


def test_dad_cli_unavailable_fallback_is_mail_pattern_signal() -> None:
    registry = load_capture_pattern_registry(ROOT)
    scenarios = load_capture_scenarios(SCENARIOS)
    case = next(
        item
        for item in scenarios["cases"]
        if item["scenario_id"] == "dad-cli-unavailable-mail-fallback-needed"
    )

    result = evaluate_capture_case(case, registry)

    assert result["passed"]
    assert not result["update_required"]
    assert result["actual"]["mail_message_types"] == ["taxonomy_suggestion"]
    assert result["actual"]["event_types"] == ["review_finding"]


def test_required_fields_are_part_of_pattern_update_contract() -> None:
    registry = load_capture_pattern_registry(ROOT)
    scenarios = load_capture_scenarios(SCENARIOS)
    case = next(
        item for item in scenarios["cases"] if item["scenario_id"] == "mail-pattern-update-required"
    )
    stale_case = json.loads(json.dumps(case))
    stale_case["expected"]["required_fields"] = [
        "affected_message_type",
        "mail_contract_gap",
    ]

    result = evaluate_capture_case(stale_case, registry)

    assert not result["passed"]
    assert result["comparisons"]["required_fields"] is False


def test_artifact_registration_drift_scenario_emits_governance_mail_and_exception() -> None:
    registry = load_capture_pattern_registry(ROOT)
    scenarios = load_capture_scenarios(SCENARIOS)
    case = next(item for item in scenarios["cases"] if item["scenario_id"] == "artifact-registration-drift")

    result = evaluate_capture_case(case, registry)

    assert result["passed"]
    assert result["actual"]["packet_classes"] == ["exception_event", "ordinary_mail"]
    assert result["actual"]["event_types"] == ["artifact_registration_drift"]
    assert result["actual"]["mail_message_types"] == ["governance_notice"]
    assert result["actual"]["capture_contracts"] == ["governance_block"]
    assert result["actual"]["required_fields"] == [
        "artifact_ref",
        "candidate_fix_checklist",
        "missing_registration_surfaces",
        "validation_refs",
    ]


def test_report_hashes_scenario_and_evaluator_inputs(tmp_path: Path) -> None:
    report = evaluate_capture_scenarios(ROOT, SCENARIOS, output=tmp_path / "report.json")

    assert report["scenario_path"] == (
        "assets/coding-harnesses/exception-capture-completeness/examples/"
        "synthetic-capture-scenarios.json"
    )
    assert "C:" not in report["scenario_path"]
    assert "Users" not in report["scenario_path"]
    assert "registry/exception-capture-pattern-registry.json" in report["input_hashes"]
    assert (
        "assets/coding-harnesses/exception-capture-completeness/examples/synthetic-capture-scenarios.json"
        in report["input_hashes"]
    )
    assert "src/digital_asset_directory/exception_capture.py" in report["input_hashes"]


def test_capture_suggest_maps_tool_unavailable_to_required_packet() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=["tool_unavailable", "dad_cli_unavailable", "fallback_used"],
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["matched_rule_ids"] == ["exception-capture-rule:tool-unavailable-metadata"]
    assert suggestion["update_required"] is False
    assert suggestion["capture_surface_version_unknown"] is False
    assert suggestion["actual"]["packet_classes"] == ["exception_event"]
    assert suggestion["actual"]["event_types"] == ["tool_unavailable"]
    assert suggestion["actual"]["capture_contracts"] == ["retry_or_plan_change"]
    assert suggestion["actual"]["required_fields"] == [
        "attempted_command",
        "fallback_path",
        "safe_summary",
        "tool_name",
    ]
    assert suggestion["recommended_packets"][0]["exception_event_type"] == "tool_unavailable"
    assert "source truth" in suggestion["authority_boundary"]


def test_capture_suggest_maps_language_frontier_signal_to_capability_mail() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=[
            "language_frontier_signal",
            "rust_coding_advantage",
            "ai_overlooked_operation",
            "frontier_source_pointer",
        ],
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["matched_rule_ids"] == [
        "exception-capture-rule:language-frontier-signal"
    ]
    assert suggestion["update_required"] is False
    assert suggestion["actual"]["packet_classes"] == ["ordinary_mail"]
    assert suggestion["actual"]["mail_message_types"] == ["capability_suggestion"]
    assert suggestion["actual"]["required_fields"] == [
        "applicability_limits",
        "language",
        "proof_surface",
        "safe_summary",
        "source_id_or_url",
        "target_dad_surface",
        "validation_or_eval_idea",
        "why_ai_coding_may_improve",
    ]
    assert suggestion["recommended_packets"][0]["mail_message_type"] == (
        "capability_suggestion"
    )


def test_capture_suggest_maps_harmful_dad_recommendation_to_exception() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=["dad_recommendation_outcome", "harmful_recommendation"],
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["matched_rule_ids"] == [
        "exception-capture-rule:harmful-dad-recommendation"
    ]
    assert suggestion["actual"]["packet_classes"] == ["exception_event"]
    assert suggestion["actual"]["event_types"] == ["harmful_dad_recommendation"]
    assert suggestion["actual"]["capture_contracts"] == ["dad_recommendation_outcome"]
    assert suggestion["actual"]["required_fields"] == [
        "harm_summary",
        "outcome_note",
        "recommendation_id",
        "trace_id",
        "validation_or_review_ref",
    ]


def test_capture_suggest_maps_safe_security_block_metadata_to_exception() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=["sensitive_payload_blocked", "credential_pii_screen_blocked"],
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["matched_rule_ids"] == [
        "exception-capture-rule:secret-or-pii-blocked-metadata"
    ]
    assert suggestion["actual"]["packet_classes"] == ["exception_event"]
    assert suggestion["actual"]["event_types"] == ["secret_or_pii_detected"]
    assert suggestion["actual"]["capture_contracts"] == ["governance_block"]
    assert suggestion["actual"]["required_fields"] == [
        "blocked_field",
        "remediation_path",
        "safe_pointer",
        "screening_gate",
        "source_visibility",
    ]


def test_capture_suggest_still_blocks_unsafe_security_payload_signal() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=[
            "sensitive_payload_blocked",
            "credential_pii_screen_blocked",
            "contains_secret_or_pii",
        ],
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["actual"]["packet_classes"] == ["no_packet"]
    assert suggestion["actual"]["blocked"] is True
    assert suggestion["actual"]["blocked_reason"] == (
        "global_block_signal:contains_secret_or_pii"
    )
    assert suggestion["recommended_packets"] == []


@pytest.mark.parametrize(
    ("signals", "rule_id", "event_type", "capture_contract", "required_fields"),
    [
        (
            [
                "protected_repo_write_block",
                "protected_repo_local_write_attempt",
                "approval_id_missing",
            ],
            "exception-capture-rule:protected-repo-write-block",
            "protected_repo_write_block",
            "governance_block",
            [
                "approval_state",
                "attempted_write_surface",
                "block_reason",
                "protected_repo_id",
                "review_ref",
            ],
        ),
        (
            [
                "dirty_worktree_block",
                "uncommitted_changes_present",
                "active_repo_blocked",
            ],
            "exception-capture-rule:dirty-worktree-block",
            "dirty_worktree_block",
            "governance_block",
            [
                "blocked_operation",
                "branch_ref",
                "dirty_state_summary",
                "next_safe_action",
                "repo_id",
            ],
        ),
        (
            [
                "private_origin_public_target",
                "public_facing_target",
                "human_release_missing",
            ],
            "exception-capture-rule:private-origin-public-target",
            "private_origin_public_target",
            "governance_block",
            [
                "release_status",
                "source_provenance_ref",
                "source_visibility",
                "target_repo_ref",
                "target_visibility",
            ],
        ),
        (
            [
                "stale_report_detected",
                "input_hash_mismatch",
                "freshness_check_failed",
            ],
            "exception-capture-rule:stale-report-freshness-failure",
            "stale_report",
            "postflight_exception",
            [
                "actual_hash",
                "expected_hash",
                "freshness_evidence_ref",
                "regeneration_command",
                "report_ref",
            ],
        ),
    ],
)
def test_capture_suggest_maps_high_priority_governance_and_freshness_blocks(
    signals: list[str],
    rule_id: str,
    event_type: str,
    capture_contract: str,
    required_fields: list[str],
) -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=signals,
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["matched_rule_ids"] == [rule_id]
    assert suggestion["actual"]["packet_classes"] == ["exception_event"]
    assert suggestion["actual"]["event_types"] == [event_type]
    assert suggestion["actual"]["capture_contracts"] == [capture_contract]
    assert suggestion["actual"]["required_fields"] == required_fields


def test_capture_suggest_flags_stale_capture_surface_for_new_rule() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=["tool_unavailable", "dad_cli_unavailable", "fallback_used"],
        repo_capture_surface_version="0.1.0",
    )

    assert suggestion["update_required"] is True
    assert "Refresh the repo capture surface" in suggestion["next_actions"][0]


def test_capture_suggest_missing_capture_surface_version_fails_loud() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=["tool_unavailable", "dad_cli_unavailable", "fallback_used"],
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["repo_capture_surface_version"] == "unknown"
    assert suggestion["capture_surface_version_unknown"] is True
    assert suggestion["update_required"] is True
    assert suggestion["next_actions"][0].startswith("Read .digital-asset/dad-integration.json")


def test_capture_suggest_blocks_unsafe_payload_without_echoing_sample() -> None:
    unsafe = "AWS key AKIAIOSFODNN7EXAMPLE should not leave the source repo"
    suggestion = suggest_exception_capture(
        ROOT,
        signals=["new_reusable_asset", "cross_repo_reuse", "asset_docs"],
        repo_capture_surface_version="0.2.0",
        payload_samples=[{"field": "safe_summary", "text": unsafe}],
    )
    serialized = json.dumps(suggestion)

    assert suggestion["actual"]["packet_classes"] == ["no_packet"]
    assert suggestion["actual"]["blocked"] is True
    assert suggestion["actual"]["blocked_reason"] == "payload_screen:credential_or_pii_pattern"
    assert suggestion["recommended_packets"] == []
    assert "credential_or_pii_pattern" in suggestion["payload_screen_issues"]
    assert suggestion["blocked_audit"]["should_record"] is True
    assert suggestion["blocked_audit"]["safe_packet_classes"] == ["local_usage_only"]
    assert unsafe not in serialized
    assert "AKIAIOSFODNN7EXAMPLE" not in serialized


def test_capture_suggest_sensitive_private_public_attempt_has_local_only_audit() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=[
            "private_origin_public_target",
            "public_facing_target",
            "human_release_missing",
            "contains_secret_or_pii",
        ],
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["actual"]["blocked"] is True
    assert suggestion["actual"]["packet_classes"] == ["no_packet"]
    assert suggestion["recommended_packets"] == []
    assert suggestion["suppressed_rule_ids"] == [
        "exception-capture-rule:private-origin-public-target"
    ]
    assert suggestion["blocked_audit"]["should_record"] is True
    assert suggestion["blocked_audit"]["audit_scope"] == "repo_local_quarantine_or_audit"
    assert suggestion["blocked_audit"]["safe_packet_classes"] == ["local_usage_only"]
    assert suggestion["blocked_audit"]["event_types"] == ["private_origin_public_target"]
    assert suggestion["blocked_audit"]["capture_contracts"] == ["governance_block"]
    assert "release_status" in suggestion["blocked_audit"]["required_fields"]
    assert any("repo-local quarantine/audit" in item for item in suggestion["next_actions"])


def test_capture_suggest_blocks_unsafe_signal_without_echoing_value() -> None:
    unsafe_signal = "api_key=AKIAIOSFODNN7EXAMPLE"
    suggestion = suggest_exception_capture(
        ROOT,
        signals=[unsafe_signal],
        repo_capture_surface_version="0.2.0",
    )
    serialized = json.dumps(suggestion)

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["signals"] == []
    assert suggestion["signal_screen_issues"] == ["unsafe_signal_token"]
    assert suggestion["actual"]["packet_classes"] == ["no_packet"]
    assert suggestion["actual"]["blocked"] is True
    assert suggestion["actual"]["blocked_reason"] == "signal_screen:unsafe_signal_token"
    assert suggestion["recommended_packets"] == []
    assert unsafe_signal not in serialized
    assert "AKIAIOSFODNN7EXAMPLE" not in serialized


def test_capture_suggest_ignores_candidate_and_rejected_rules(tmp_path: Path) -> None:
    registry = json.loads(
        (ROOT / "registry" / "exception-capture-pattern-registry.json").read_text(
            encoding="utf-8"
        )
    )
    base_rule = registry["rules"][0]
    candidate_rule = {
        **base_rule,
        "rule_id": "exception-capture-rule:candidate-only-test",
        "match_signals": ["candidate_only_signal"],
        "any_signals": [],
        "review_status": "candidate",
    }
    rejected_rule = {
        **base_rule,
        "rule_id": "exception-capture-rule:rejected-test",
        "match_signals": ["rejected_signal"],
        "any_signals": [],
        "review_status": "rejected",
    }
    registry["rules"] = [candidate_rule, rejected_rule]
    registry_path = tmp_path / "registry" / "exception-capture-pattern-registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    suggestion = suggest_exception_capture(
        tmp_path,
        signals=["candidate_only_signal", "rejected_signal"],
        repo_capture_surface_version="0.2.0",
    )

    _validate("exception_capture_suggestion", suggestion)
    assert suggestion["matched_rule_ids"] == []
    assert suggestion["actual"]["packet_classes"] == ["no_packet"]
    assert suggestion["recommended_packets"] == []


def test_capture_suggest_unknown_signals_stay_candidate_no_packet() -> None:
    suggestion = suggest_exception_capture(
        ROOT,
        signals=["uncataloged_signal"],
        repo_capture_surface_version="0.2.0",
    )

    assert suggestion["matched_rule_ids"] == []
    assert suggestion["actual"]["packet_classes"] == ["no_packet"]
    assert suggestion["recommended_packets"] == []
    assert "No reviewed capture rule matched" in suggestion["next_actions"][0]


def test_capture_suggest_cli_blocks_unsafe_signal_without_echoing_value() -> None:
    unsafe_signal = "api_key=AKIAIOSFODNN7EXAMPLE"
    result = RUNNER.invoke(
        app,
        [
            "exceptions",
            "capture-suggest",
            "--signal",
            unsafe_signal,
            "--repo-capture-surface-version",
            "0.2.0",
        ],
    )

    assert result.exit_code == 0, result.output
    assert unsafe_signal not in result.output
    assert "AKIAIOSFODNN7EXAMPLE" not in result.output
    payload = json.loads(result.output)
    _validate("exception_capture_suggestion", payload)
    assert payload["signal_screen_issues"] == ["unsafe_signal_token"]
    assert payload["recommended_packets"] == []


def test_observed_capture_audit_reports_existing_repo_outbox_emission(tmp_path: Path) -> None:
    repo = tmp_path / "repo-with-outboxes"
    repo.mkdir()
    dad_dir = repo / ".digital-asset"
    dad_dir.mkdir(parents=True)
    (dad_dir / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "repo-with-outboxes",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.2.0",
            }
        ),
        encoding="utf-8",
    )
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Reusable review workflow should be mailed to DAD.",
        payload={"workflow_summary": "metadata-only"},
        evidence=["docs/review-workflow.md"],
        suggested_actions=["Review this workflow."],
        allow_similar=True,
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Review workflow exposed a capture gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review-workflow.md"],
    )

    policy = SimpleNamespace(
        id="repo-with-outboxes",
        path=repo,
        alias="repo-with-outboxes",
        visibility="private",
        public_facing=False,
        write_protected=False,
        write_protection_reason="",
    )
    report = write_observed_capture_audit(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=tmp_path / "audit.json",
        scope={
            "scope_id": "test-reviewed-scope",
            "scope_kind": "reviewed_exception_policy",
            "reviewed_policy_scope": True,
            "expected_repo_count": 1,
            "audited_repo_count": 1,
        },
    )
    row = report["repos"][0]
    gate = _phase6_gate(report, "phase-6-observed-repo-capture-audit-reviewed")

    _assert_machine_only_phase6_evidence(report)
    assert "outbox_emission_present" in row["status_flags"]
    assert "missed_capture_candidate" not in row["status_flags"]
    assert row["packet_classes"] == ["exception_event", "ordinary_mail"]
    assert report["gap_count"] == 0
    assert report["strict_gap_count"] == 0
    assert gate["machine_status"] == "passed"
    assert gate["evidence"]["non_mutating_audit"] is True
    assert gate["evidence"]["outbox_surfaces_checked"] == [
        "mail_outbox",
        "exception_outbox",
        "fix_outcomes",
    ]
    assert (tmp_path / "audit.json").exists()
    assert (tmp_path / "audit.md").exists()


def test_observed_capture_audit_clean_ad_hoc_scope_fails_machine_gate(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-with-outboxes"
    repo.mkdir()
    dad_dir = repo / ".digital-asset"
    dad_dir.mkdir(parents=True)
    (dad_dir / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "repo-with-outboxes",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.2.0",
            }
        ),
        encoding="utf-8",
    )
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Reusable review workflow should be mailed to DAD.",
        payload={"workflow_summary": "metadata-only"},
        evidence=["docs/review-workflow.md"],
        suggested_actions=["Review this workflow."],
        allow_similar=True,
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Review workflow exposed a capture gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review-workflow.md"],
    )

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    gate = _phase6_gate(report, "phase-6-observed-repo-capture-audit-reviewed")

    assert report["gap_count"] == 0
    assert report["strict_gap_count"] == 0
    assert report["audit_scope"]["reviewed_policy_scope"] is False
    assert report["audit_scope"]["scope_satisfied"] is False
    assert gate["machine_status"] == "failed"
    assert gate["evidence"]["pass_condition"] == (
        "repo_count > 0, reviewed policy scope satisfied, and strict_gap_flag_count == 0"
    )


def test_observed_capture_audit_scope_counts_come_from_rows(tmp_path: Path) -> None:
    repo = tmp_path / "repo-with-outboxes"
    repo.mkdir()
    dad_dir = repo / ".digital-asset"
    dad_dir.mkdir(parents=True)
    (dad_dir / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "repo-with-outboxes",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.2.0",
            }
        ),
        encoding="utf-8",
    )
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Reusable review workflow should be mailed to DAD.",
        payload={"workflow_summary": "metadata-only"},
        evidence=["docs/review-workflow.md"],
        suggested_actions=["Review this workflow."],
        allow_similar=True,
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Review workflow exposed a capture gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=["docs/review-workflow.md"],
    )

    report = write_observed_capture_audit(
        ROOT,
        [repo],
        output=tmp_path / "audit.json",
        scope={
            "scope_id": "spoofed-reviewed-scope",
            "scope_kind": "reviewed_exception_policy",
            "reviewed_policy_scope": True,
            "expected_repo_count": 1,
            "audited_repo_count": 1,
            "reviewed_policy_repo_count": 1,
        },
    )
    gate = _phase6_gate(report, "phase-6-observed-repo-capture-audit-reviewed")

    assert report["gap_count"] == 0
    assert report["strict_gap_count"] == 0
    assert report["repos"][0]["repo"]["reviewed_policy"] is False
    assert report["audit_scope"]["reviewed_policy_repo_count"] == 0
    assert report["audit_scope"]["audited_repo_count"] == 1
    assert report["audit_scope"]["scope_satisfied"] is False
    assert gate["machine_status"] == "failed"


def test_observed_capture_audit_does_not_match_hang_inside_changelog(tmp_path: Path) -> None:
    repo = tmp_path / "repo-with-changelog"
    repo.mkdir()
    (repo / "CHANGELOG.md").write_text("Routine release notes only.\n", encoding="utf-8")

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    row = report["repos"][0]

    terms = {item["term"] for item in row["candidate_path_signals"]}
    suggested_types = {
        item["suggested_event_type"] for item in row["candidate_path_signals"]
    }
    assert "hang" not in terms
    assert "command_timeout" not in suggested_types


def test_observed_capture_audit_flags_candidate_path_without_outbox(tmp_path: Path) -> None:
    repo = tmp_path / "repo-missed-capture"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")

    policy = SimpleNamespace(
        id="repo-missed-capture",
        path=repo,
        alias="repo-missed-capture",
        visibility="private",
        public_facing=False,
        write_protected=False,
        write_protection_reason="",
    )
    report = write_observed_capture_audit(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=tmp_path / "audit.json",
    )
    row = report["repos"][0]
    gate = _phase6_gate(report, "phase-6-observed-repo-capture-audit-reviewed")

    _assert_machine_only_phase6_evidence(report)
    assert "missed_capture_candidate" in row["status_flags"]
    assert report["gap_count"] >= 1
    assert report["strict_gap_count"] >= report["gap_count"]
    assert _capture_audit_gap_count(report, strict=False) == report["gap_count"]
    assert _capture_audit_gap_count(report, strict=True) == report["strict_gap_count"]
    assert gate["machine_status"] == "failed"
    assert "missed_capture_candidate" in gate["evidence"]["gap_flags_present"]
    assert row["repo"]["reviewed_policy"]
    assert row["repo"]["visibility"] == "private"
    assert row["candidate_path_signal_count"] == 1
    assert "path" not in row["candidate_path_signals"][0]
    assert row["candidate_path_signals"][0]["path_redacted"] == "true"
    assert row["candidate_path_signals"][0]["path_hash"].startswith("sha256:")
    assert row["candidate_path_signals"][0]["pattern_family"] == "exception_pattern"


def test_observed_capture_audit_uses_registry_backfill_classifier(tmp_path: Path) -> None:
    repo = tmp_path / "repo-cli-fallback"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "asset-dir-unavailable.md").write_text(
        "metadata-only pointer to DAD CLI fallback behavior",
        encoding="utf-8",
    )
    policy = SimpleNamespace(
        id="repo-cli-fallback",
        path=repo,
        alias="repo-cli-fallback",
        visibility="private",
        public_facing=False,
        write_protected=False,
        write_protection_reason="",
    )

    report = write_observed_capture_audit(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=tmp_path / "audit.json",
    )
    signal = report["repos"][0]["candidate_path_signals"][0]

    assert signal["term"] == "asset-dir-unavailable"
    assert signal["suggested_event_type"] == "tool_unavailable"
    assert signal["pattern_family"] == "exception_pattern"
    assert signal["path_redacted"] == "true"
    assert signal["source_rule_id"] == "backfill-rule:tool-unavailable"
    assert signal["classification_source"] == "backfill_classifier"
    suggestion = signal["capture_suggestion"]
    assert suggestion["matched_rule_ids"] == ["exception-capture-rule:tool-unavailable-metadata"]
    assert suggestion["actual"]["event_types"] == ["tool_unavailable"]
    assert suggestion["actual"]["capture_contracts"] == ["retry_or_plan_change"]
    assert suggestion["actual"]["required_fields"] == [
        "attempted_command",
        "fallback_path",
        "safe_summary",
        "tool_name",
    ]
    assert suggestion["capture_surface_version_unknown"] is True
    assert suggestion["update_required"] is True


def test_observed_capture_audit_does_not_expand_broad_exception_signal(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-generic-exception"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    signal = report["repos"][0]["candidate_path_signals"][0]
    suggestion = signal["capture_suggestion"]

    assert signal["pattern_family"] == "exception_pattern"
    assert signal["suggested_event_type"] == "backfill_exception_candidate"
    assert suggestion["ambiguous_exception_signal"] is True
    assert suggestion["matched_rule_ids"] == []
    assert suggestion["actual"]["packet_classes"] == ["no_packet"]
    assert suggestion["recommended_packets"] == []
    assert "broad exception path signal" in suggestion["next_actions"][0]


def test_observed_capture_audit_summarizes_candidate_signal_mix(tmp_path: Path) -> None:
    repo = tmp_path / "repo-signal-summary"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "asset-dir-unavailable.md").write_text(
        "metadata-only pointer to DAD CLI fallback behavior",
        encoding="utf-8",
    )
    (docs / "red-team-review.md").write_text("metadata-only review pointer", encoding="utf-8")

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    row = report["repos"][0]
    row_summary = row["candidate_path_signal_summary"]
    report_summary = report["candidate_path_signal_summary"]
    md_text = (tmp_path / "audit.md").read_text(encoding="utf-8")

    assert row_summary["total"] == 2
    assert row_summary["by_suggested_event_type"]["tool_unavailable"] == 1
    assert row_summary["by_suggested_event_type"]["review_finding"] == 1
    assert row_summary["by_source_rule_id"]["backfill-rule:tool-unavailable"] == 1
    assert row_summary["by_source_rule_id"]["backfill-rule:review-finding"] == 1
    assert (
        row_summary["by_capture_suggest_rule_id"][
            "exception-capture-rule:tool-unavailable-metadata"
        ]
        == 1
    )
    assert (
        row_summary["by_capture_suggest_rule_id"]["exception-capture-rule:review-finding"]
        == 1
    )
    assert row_summary["by_emission_status"]["gap_candidate"] == 2
    assert report_summary == row_summary
    assert "## Candidate Suggested Event Types" in md_text
    assert "`tool_unavailable`: 1" in md_text
    assert "`review_finding`: 1" in md_text
    assert "`backfill-rule:tool-unavailable`: 1" in md_text
    assert "`backfill-rule:review-finding`: 1" in md_text


def test_observed_capture_audit_carries_reviewed_workflow_capture_suggestion(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-review-workflow"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "review-issue-workflow.md").write_text(
        "metadata-only pointer to a structured review issue workflow",
        encoding="utf-8",
    )
    (repo / ".digital-asset").mkdir()
    (repo / ".digital-asset" / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "repo-review-workflow",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.2.0",
            }
        ),
        encoding="utf-8",
    )

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    signal = report["repos"][0]["candidate_path_signals"][0]
    suggestion = signal["capture_suggestion"]

    assert signal["pattern_family"] == "workflow"
    assert suggestion["matched_rule_ids"] == [
        "exception-capture-rule:structured-workflow-review-gap"
    ]
    assert suggestion["update_required"] is False
    assert suggestion["actual"]["packet_classes"] == ["exception_event", "ordinary_mail"]
    assert suggestion["actual"]["mail_message_types"] == ["workflow_suggestion"]
    assert suggestion["actual"]["event_types"] == ["review_finding"]
    assert suggestion["actual"]["required_fields"] == [
        "exception_mapping_gap",
        "issue_classes",
        "validation_refs",
        "workflow_summary",
    ]


def test_observed_capture_audit_redacts_embedded_local_paths_even_internal(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-with-embedded-local-path"
    marker_dir = repo / "notes" / "Users" / "lowel" / "OneDrive" / "Desktop" / "Git Projects"
    marker_dir.mkdir(parents=True)
    (marker_dir / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")
    policy = SimpleNamespace(
        id="repo-with-embedded-local-path",
        path=repo,
        alias="repo-with-embedded-local-path",
        visibility="internal",
        public_facing=False,
        write_protected=False,
        write_protection_reason="",
    )

    report = write_observed_capture_audit(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=tmp_path / "audit.json",
    )
    row = report["repos"][0]
    signal = row["candidate_path_signals"][0]
    report_text = json.dumps(report)

    assert signal["path_redacted"] == "true"
    assert signal["path_redacted_reason"] == "private_path_fragment"
    assert "path" not in signal
    assert "Users" not in report_text
    assert "OneDrive" not in report_text


def test_observed_capture_audit_flags_specific_gap_despite_unrelated_mail(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-unrelated-mail"
    dad_dir = repo / ".digital-asset"
    docs = repo / "docs"
    dad_dir.mkdir(parents=True)
    docs.mkdir(parents=True)
    (dad_dir / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "repo-unrelated-mail",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.2.0",
            }
        ),
        encoding="utf-8",
    )
    (docs / "review-issue-workflow.md").write_text(
        "metadata-only pointer to a review issue workflow and exception lake capture gap",
        encoding="utf-8",
    )
    compose_mail(
        repo,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Unrelated old asset mail.",
        payload={"asset_id_or_path": "assets/old.json", "safe_summary": "metadata-only"},
        evidence=["assets/old.json"],
        suggested_actions=["Review unrelated asset."],
        allow_similar=True,
    )

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    row = report["repos"][0]
    gap_signal = row["candidate_path_signals"][0]

    assert "outbox_emission_present" in row["status_flags"]
    assert "missed_capture_candidate" not in row["status_flags"]
    assert "pattern_gap_candidate" in row["status_flags"]
    assert "mail_message_type" in gap_signal["missing_outputs"]
    assert "event_type" in gap_signal["missing_outputs"]
    assert "capture_contract" in gap_signal["missing_outputs"]
    assert gap_signal["emission_status"] == "gap_candidate"


def test_observed_capture_audit_requires_same_type_mail_to_correlate_to_signal(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-same-type-unrelated-mail"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    signal_path = docs / "review-issue-workflow.md"
    signal_path.write_text(
        "metadata-only pointer to a review issue workflow and exception lake capture gap",
        encoding="utf-8",
    )
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Old unrelated workflow mail.",
        payload={"workflow_summary": "metadata-only unrelated workflow"},
        evidence=["docs/old-workflow.md"],
        suggested_actions=["Review unrelated workflow."],
        allow_similar=True,
    )

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    row = report["repos"][0]
    signal = row["candidate_path_signals"][0]

    assert "pattern_gap_candidate" in row["status_flags"]
    assert signal["emission_status"] == "gap_candidate"
    assert "mail_message_type" in signal["uncorrelated_outputs"]
    assert "mail_message_type" in signal["missing_outputs"]


def test_private_hash_only_signal_correlates_to_readable_packet_ref(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-private-correlated"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    signal_ref = "docs/review-issue-workflow.md"
    (repo / signal_ref).write_text(
        "metadata-only pointer to a review issue workflow and exception lake capture gap",
        encoding="utf-8",
    )
    compose_mail(
        repo,
        message_type="workflow_suggestion",
        target_repo="central_only",
        summary="Workflow mail points to the same repo-relative evidence.",
        payload={"workflow_summary": "metadata-only correlated workflow"},
        evidence=[signal_ref],
        suggested_actions=["Review the correlated workflow."],
        allow_similar=True,
    )
    record_exception_event(
        ROOT,
        repo,
        event_type="review_finding",
        summary="Review workflow exposed an exception-lake capture gap.",
        stage="review",
        severity="high",
        capture_contract="review_finding",
        source_visibility="private",
        context_refs=[signal_ref],
    )
    policy = SimpleNamespace(
        id="repo-private-correlated",
        path=repo,
        alias="repo-private-correlated",
        visibility="private",
        public_facing=False,
        write_protected=False,
        write_protection_reason="",
    )

    report = write_observed_capture_audit(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=tmp_path / "audit.json",
    )
    row = report["repos"][0]
    signal = row["candidate_path_signals"][0]
    report_text = json.dumps(report)

    assert signal["path_redacted"] == "true"
    assert "path" not in signal
    assert signal["emission_status"] == "matched"
    assert "pattern_gap_candidate" not in row["status_flags"]
    assert "type_present_uncorrelated" not in row["status_flags"]
    assert "emission_unverified" not in row["status_flags"]
    assert signal_ref not in report_text


def test_observed_capture_audit_flags_stale_capture_surface(tmp_path: Path) -> None:
    repo = tmp_path / "repo-stale-surface"
    dad_dir = repo / ".digital-asset"
    dad_dir.mkdir(parents=True)
    (dad_dir / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "repo-stale-surface",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    row = report["repos"][0]

    assert "stale_capture_surface" in row["status_flags"]
    assert row["contract"]["capture_surface_version"] == "0.1.0"
    assert row["registry_capture_surface_version"] == "0.2.0"


def test_observed_capture_audit_tolerates_malformed_jsonl_without_raw_line(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-malformed-outbox"
    outbox = repo / ".digital-asset" / "mail" / "outbox.jsonl"
    outbox.parent.mkdir(parents=True)
    outbox.write_text('{"message_type":"workflow_suggestion"}\n{bad json}\n', encoding="utf-8")

    report = write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    row = report["repos"][0]

    assert "malformed_jsonl" in row["status_flags"]
    assert row["outboxes"]["mail_outbox"]["record_count"] == 1
    assert row["outboxes"]["mail_outbox"]["malformed_count"] == 1
    assert row["outboxes"]["mail_outbox"]["errors"] == ["malformed_jsonl:2"]
    assert "{bad json}" not in json.dumps(report)


def test_observed_capture_audit_does_not_write_target_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo-read-only-audit"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    marker = docs / "postmortem.md"
    marker.write_text("metadata-only placeholder", encoding="utf-8")
    before = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))

    write_observed_capture_audit(ROOT, [repo], output=tmp_path / "audit.json")
    after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))

    assert after == before


def test_observed_capture_audit_flags_truncated_candidate_scan(tmp_path: Path) -> None:
    repo = tmp_path / "repo-truncated-audit"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "incident-one.md").write_text("metadata-only placeholder", encoding="utf-8")
    (docs / "incident-two.md").write_text("metadata-only placeholder", encoding="utf-8")

    report = write_observed_capture_audit(
        ROOT,
        [repo],
        output=tmp_path / "audit.json",
        candidate_limit=1,
    )
    row = report["repos"][0]
    audit_md = (tmp_path / "audit.md").read_text(encoding="utf-8")

    assert row["candidate_path_scan"]["truncated"] is True
    assert row["candidate_path_signal_summary"]["count_scope"] == "bounded_first_n_path_matches"
    assert row["candidate_path_signal_summary"]["truncated_repo_count"] == 1
    assert row["candidate_path_signal_summary"]["omitted_signal_count_unknown"] is True
    assert report["candidate_path_signal_summary"]["count_scope"] == "bounded_first_n_path_matches"
    assert report["candidate_path_signal_summary"]["truncated_repo_count"] == 1
    assert "candidate_path_scan_truncated" in row["status_flags"]
    assert report["status_counts"]["candidate_path_scan_truncated"] == 1
    assert _capture_audit_gap_count(report, strict=False) >= 1
    assert report["gap_count"] >= 1
    assert report["strict_gap_count"] >= report["gap_count"]
    assert _phase6_gate(
        report,
        "phase-6-observed-repo-capture-audit-reviewed",
    )["machine_status"] == "failed"
    assert "candidate_path_scan_truncated" in audit_md
    assert "bounded first-N samples" in audit_md


def test_observed_capture_audit_candidate_limit_zero_exhausts_metadata_scan(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-exhaustive-audit"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    for name in ["incident-one.md", "incident-two.md", "incident-three.md"]:
        (docs / name).write_text("metadata-only placeholder", encoding="utf-8")

    report = write_observed_capture_audit(
        ROOT,
        [repo],
        output=tmp_path / "audit.json",
        candidate_limit=0,
    )
    row = report["repos"][0]
    audit_md = (tmp_path / "audit.md").read_text(encoding="utf-8")

    assert row["candidate_path_scan"]["limit"] is None
    assert row["candidate_path_scan"]["limit_mode"] == "exhaustive"
    assert row["candidate_path_scan"]["max_scanned_files"] == 50000
    assert row["candidate_path_scan"]["stopped_reason"] == "exhausted_walk"
    assert row["candidate_path_scan"]["truncated"] is False
    assert row["candidate_path_signal_count"] == 3
    assert row["candidate_path_signal_summary"]["count_scope"] == "complete_for_scanned_paths"
    assert row["candidate_path_signal_summary"]["omitted_signal_count_unknown"] is False
    assert report["candidate_path_signal_summary"]["count_scope"] == "complete_for_scanned_paths"
    assert report["candidate_path_signal_summary"]["truncated_repo_count"] == 0
    assert "candidate_path_scan_truncated" not in row["status_flags"]
    assert "bounded first-N samples" not in audit_md


def test_exception_backfill_readiness_reports_policy_gates(tmp_path: Path) -> None:
    ready_repo = tmp_path / "ready-external"
    protected_repo = tmp_path / "protected-repo"
    blocked_repo = tmp_path / "blocked-repo"
    for repo in [ready_repo, protected_repo, blocked_repo]:
        docs = repo / "docs"
        docs.mkdir(parents=True)
        (docs / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")
    policies = [
        ExceptionRepoPolicy(
            id="ready-external",
            path=ready_repo,
            alias="ready",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=True,
            approved_approval_ids=["APPROVED-BACKFILL"],
        ),
        ExceptionRepoPolicy(
            id="protected",
            path=protected_repo,
            alias="protected",
            visibility="public",
            public_facing=True,
            exceptions_enabled=True,
            collect_allowed=False,
            capture_audit_allowed=True,
            backfill_allowed=True,
            write_protected=True,
        ),
        ExceptionRepoPolicy(
            id="blocked",
            path=blocked_repo,
            alias="blocked",
            visibility="public",
            public_facing=True,
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=False,
        ),
    ]

    report = write_exception_backfill_readiness(
        ROOT,
        [ready_repo, protected_repo, blocked_repo],
        repo_policies=policies,
        output=tmp_path / "readiness.json",
        candidate_limit=5,
    )
    rows = {row["repo_id"]: row for row in report["repos"]}
    md_text = (tmp_path / "readiness.md").read_text(encoding="utf-8")

    assert rows["ready-external"]["backfill_readiness"] == "needs_full_scan_review"
    assert "capture surface is stale or unknown" in rows["ready-external"]["blocked_reasons"]
    assert rows["ready-external"]["candidate_path_signal_count"] == 1
    assert rows["ready-external"]["candidate_path_signal_summary"]["total"] == 1
    assert rows["protected"]["backfill_readiness"] == "central_only_or_blocked"
    assert any("write_protected" in reason for reason in rows["protected"]["blocked_reasons"])
    assert rows["blocked"]["backfill_readiness"] == "blocked_by_policy_or_no_signals"
    assert "backfill_allowed=false" in rows["blocked"]["blocked_reasons"]
    assert report["readiness_counts"]["needs_full_scan_review"] == 1
    assert report["candidate_path_signal_summary"]["total"] == 3
    assert (
        "registry/exception-event-type-registry.json"
        in report["input_hashes"]
    )
    assert (
        report["candidate_path_signal_summary"]["by_suggested_event_type"][
            "backfill_exception_candidate"
        ]
        == 3
    )
    assert (
        report["candidate_path_signal_summary"]["by_source_rule_id"][
            "backfill-rule:generic-exception"
        ]
        == 3
    )
    assert "Boundary: central planning evidence only" in md_text
    assert "## Candidate Suggested Event Types" in md_text
    assert "`backfill_exception_candidate`: 3" in md_text
    assert str(tmp_path) not in json.dumps(report)
    assert str(tmp_path) not in md_text


def test_exception_backfill_wave_plan_orders_review_gates(tmp_path: Path) -> None:
    refresh_repo = tmp_path / "refresh-repo"
    protected_repo = tmp_path / "protected-repo"
    blocked_repo = tmp_path / "blocked-repo"
    for repo in [refresh_repo, protected_repo, blocked_repo]:
        docs = repo / "docs"
        docs.mkdir(parents=True)
        (docs / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")
    policies = [
        ExceptionRepoPolicy(
            id="refresh",
            path=refresh_repo,
            alias="refresh",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=True,
            approved_approval_ids=["APPROVED-BACKFILL"],
        ),
        ExceptionRepoPolicy(
            id="protected",
            path=protected_repo,
            alias="protected",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=False,
            capture_audit_allowed=True,
            backfill_allowed=True,
            write_protected=True,
        ),
        ExceptionRepoPolicy(
            id="blocked",
            path=blocked_repo,
            alias="blocked",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=False,
        ),
    ]
    before = {
        repo: sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
        for repo in [refresh_repo, protected_repo, blocked_repo]
    }

    plan = write_exception_backfill_wave_plan(
        ROOT,
        [refresh_repo, protected_repo, blocked_repo],
        repo_policies=policies,
        output=tmp_path / "wave-plan.json",
        candidate_limit=5,
        per_wave_repo_limit=10,
    )
    waves = {wave["wave_id"]: wave for wave in plan["waves"]}
    md_text = (tmp_path / "wave-plan.md").read_text(encoding="utf-8")

    assert plan["report_id"] == "dad:exception-backfill-wave-plan"
    assert plan["current_wave_id"] == "capture_surface_refresh_wave"
    assert waves["capture_surface_refresh_wave"]["repos"][0]["repo_id"] == "refresh"
    assert waves["protected_central_only_review_wave"]["repos"][0]["repo_id"] == "protected"
    assert waves["policy_enablement_wave"]["repos"][0]["repo_id"] == "blocked"
    assert waves["metadata_backfill_candidate_wave"]["repo_count"] == 0
    backlogs = {backlog["backlog_id"]: backlog for backlog in plan["proof_backlogs"]}
    assert backlogs["capture_surface_refresh_backlog"]["repo_count"] == 3
    assert {
        repo["repo_id"]
        for repo in backlogs["capture_surface_refresh_backlog"]["repos"]
    } == {"refresh", "protected", "blocked"}
    assert backlogs["emission_review_backlog"]["repo_count"] == 3
    assert backlogs["classifier_refresh_backlog"]["repo_count"] == 0
    assert backlogs["ready_for_source_packet_request"]["repo_count"] == 0
    assert "capture_surface_not_current" in waves["protected_central_only_review_wave"][
        "repos"
    ][0]["proof_blockers"]
    assert "## Proof Backlogs" in md_text
    assert "Capture surface refresh proof backlog" in md_text
    assert "Boundary: central planning evidence only" in md_text
    assert "Run metadata-only candidate backfill" in md_text
    for repo in [refresh_repo, protected_repo, blocked_repo]:
        after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
        assert after == before[repo]


def test_exception_capture_remediation_plan_routes_repair_lanes_without_repo_writes(
    tmp_path: Path,
) -> None:
    stale_repo = tmp_path / "stale-repo"
    protected_repo = tmp_path / "protected-repo"
    ready_repo = tmp_path / "ready-repo"
    for repo in [stale_repo, protected_repo, ready_repo]:
        docs = repo / "docs"
        docs.mkdir(parents=True)
        (docs / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")
    (ready_repo / ".digital-asset").mkdir()
    (ready_repo / ".digital-asset" / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "ready",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.2.0",
            }
        ),
        encoding="utf-8",
    )
    record_exception_event(
        ROOT,
        ready_repo,
        event_type="backfill_exception_candidate",
        summary="Historical candidate needs source review.",
        stage="discovery",
        severity="low",
        capture_contract="backfill_candidate",
        source_visibility="internal",
        context_refs=["docs/postmortem.md"],
    )
    policies = [
        ExceptionRepoPolicy(
            id="stale",
            path=stale_repo,
            alias="stale",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=True,
        ),
        ExceptionRepoPolicy(
            id="protected",
            path=protected_repo,
            alias="protected",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=False,
            capture_audit_allowed=True,
            backfill_allowed=True,
            write_protected=True,
        ),
        ExceptionRepoPolicy(
            id="ready",
            path=ready_repo,
            alias="ready",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=True,
            approved_approval_ids=["APPROVED-BACKFILL"],
        ),
    ]
    before = {
        repo: sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
        for repo in [stale_repo, protected_repo, ready_repo]
    }

    plan = write_exception_capture_remediation_plan(
        ROOT,
        [stale_repo, protected_repo, ready_repo],
        repo_policies=policies,
        output=tmp_path / "capture-remediation.json",
        candidate_limit=0,
        per_lane_repo_limit=10,
    )
    lanes = {lane["lane_id"]: lane for lane in plan["lanes"]}
    md_text = (tmp_path / "capture-remediation.md").read_text(encoding="utf-8")

    assert plan["report_id"] == "dad:exception-capture-remediation-plan"
    assert plan["current_lane_id"] == "protected_central_only_review"
    assert lanes["protected_central_only_review"]["repos"][0]["repo_id"] == "protected"
    assert lanes["protected_central_only_review"]["repos"][0]["write_policy"] == (
        "protected_central_only"
    )
    assert {
        repo["repo_id"]
        for repo in lanes["capture_surface_refresh_required"]["repos"]
    } == {"stale", "protected"}
    assert {
        repo["repo_id"]
        for repo in lanes["emission_review_required"]["repos"]
    } == {"stale", "protected", "ready"}
    assert lanes["ready_for_source_packet_request"]["repo_count"] == 0
    assert "central-only candidate evidence" in plan["authority_boundary"]
    assert "without human rescue from chat" in md_text
    assert str(tmp_path) not in json.dumps(plan)
    assert str(tmp_path) not in md_text
    for repo in [stale_repo, protected_repo, ready_repo]:
        after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
        assert after == before[repo]


def test_build_exception_capture_remediation_plan_stays_ready_when_proof_clears() -> None:
    readiness = {
        "report_id": "dad:exception-backfill-readiness",
        "repos": [
            {
                "repo_id": "ready",
                "repo_alias": "ready",
                "path_hash": "sha256:ready",
                "visibility": "internal",
                "public_facing": False,
                "reviewed_policy": True,
                "exceptions_enabled": True,
                "collect_allowed": True,
                "capture_audit_allowed": True,
                "backfill_allowed": True,
                "write_protected": False,
                "backfill_readiness": "ready_with_reviewed_approval",
                "capture_surface_action": "current",
                "candidate_path_signal_count": 1,
                "candidate_path_scan": {"truncated": False},
                "candidate_path_signal_summary": {
                    "total": 1,
                    "by_pattern_family": {"workflow": 1},
                    "by_source_rule_id": {"backfill-rule:generic-exception": 1},
                    "by_suggested_event_type": {"backfill_exception_candidate": 1},
                },
                "status_flags": [],
                "blocked_reasons": [],
                "next_actions": [],
            }
        ],
    }

    plan = build_exception_capture_remediation_plan(readiness)
    lanes = {lane["lane_id"]: lane for lane in plan["lanes"]}

    assert lanes["ready_for_source_packet_request"]["repo_count"] == 1
    assert lanes["watch_or_no_action"]["repo_count"] == 0
    assert lanes["ready_for_source_packet_request"]["repos"][0]["top_pattern_families"] == {
        "workflow": 1
    }


def test_exception_capture_gap_review_queue_groups_signals_without_readable_paths(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")
    (docs / "governance-map.md").write_text("metadata-only placeholder", encoding="utf-8")
    policy = ExceptionRepoPolicy(
        id="gap-repo",
        path=repo,
        alias="gap-repo",
        visibility="internal",
        exceptions_enabled=True,
        collect_allowed=True,
        capture_audit_allowed=True,
        backfill_allowed=True,
    )
    before = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))

    report = write_exception_capture_gap_review_queue(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=tmp_path / "gap-queue.json",
        candidate_limit=0,
        per_group_example_limit=2,
    )
    md_text = (tmp_path / "gap-queue.md").read_text(encoding="utf-8")

    assert report["report_id"] == "dad:exception-capture-gap-review-queue"
    assert report["review_group_count"] >= 1
    assert report["candidate_signal_count"] >= 2
    assert report["per_group_example_limit"] == 2
    assert any(
        group["suggested_event_type"] == "backfill_exception_candidate"
        for group in report["groups"]
    )
    assert any(
        "capture_surface_refresh_required" in group["remediation_lanes"]
        for group in report["groups"]
    )
    for group in report["groups"]:
        assert len(group["path_hashes"]) <= 2
        assert all(path_hash.startswith("sha256:") for path_hash in group["path_hashes"])
        assert "next_actions" in group
        assert "path" not in group
    assert "central-only candidate evidence" in report["authority_boundary"]
    assert "Top Groups" in md_text
    assert str(tmp_path) not in json.dumps(report)
    assert str(tmp_path) not in md_text
    after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
    assert after == before


def test_build_exception_capture_gap_review_queue_is_stable_and_actionable() -> None:
    observed_report = {
        "audit_id": "dad:exception-capture-observed-audit",
        "repo_count": 1,
        "capture_surface_version": "0.2.0",
        "status_counts": {"pattern_gap_candidate": 1},
        "input_hashes": {"registry/exception-capture-pattern-registry.json": "sha256:test"},
        "methodology_ref": "registry/exception-capture-pattern-registry.json",
        "methodology_hash": "sha256:test",
        "candidate_path_signal_summary": {"total": 2},
        "repos": [
            {
                "repo": {
                    "repo_id": "repo",
                    "repo_alias": "repo",
                    "path_hash": "sha256:repo",
                    "visibility": "internal",
                    "public_facing": False,
                    "reviewed_policy": True,
                    "exceptions_enabled": True,
                    "collect_allowed": True,
                    "capture_audit_allowed": True,
                    "backfill_allowed": True,
                    "write_protected": False,
                },
                "contract": {"capture_surface_version": "0.2.0"},
                "registry_capture_surface_version": "0.2.0",
                "status_flags": ["pattern_gap_candidate"],
                "candidate_path_scan": {"truncated": False},
                "candidate_path_signals": [
                    {
                        "term": "postmortem",
                        "pattern_family": "exception_pattern",
                        "suggested_event_type": "backfill_exception_candidate",
                        "source_rule_id": "backfill-rule:generic-exception",
                        "expected_review": "exception_event_or_no_packet",
                        "emission_status": "gap_candidate",
                        "path_hash": "sha256:path-a",
                        "path_redacted": "false",
                        "capture_suggestion": {
                            "matched_rule_ids": [
                                "exception-capture-rule:runtime-exception-metadata"
                            ]
                        },
                    },
                    {
                        "term": "postmortem",
                        "pattern_family": "exception_pattern",
                        "suggested_event_type": "backfill_exception_candidate",
                        "source_rule_id": "backfill-rule:generic-exception",
                        "expected_review": "exception_event_or_no_packet",
                        "emission_status": "gap_candidate",
                        "path_hash": "sha256:path-b",
                        "path_redacted": "false",
                        "capture_suggestion": {
                            "matched_rule_ids": [
                                "exception-capture-rule:runtime-exception-metadata"
                            ]
                        },
                    },
                ],
            }
        ],
    }

    first = build_exception_capture_gap_review_queue(observed_report)
    second = build_exception_capture_gap_review_queue(observed_report)

    assert first["groups"] == second["groups"]
    group = first["groups"][0]
    assert group["candidate_signal_count"] == 2
    assert group["top_terms"] == {"postmortem": 2}
    assert group["path_hashes"] == ["sha256:path-a", "sha256:path-b"]
    assert any("route through `backfill_exception_candidate`" in action for action in group["next_actions"])


def test_capture_gap_review_queue_separates_same_repo_id_by_path_hash() -> None:
    def repo_row(path_hash: str, visibility: str) -> dict:
        return {
            "repo": {
                "repo_id": "copied-repo",
                "repo_alias": "copied-repo",
                "path_hash": path_hash,
                "visibility": visibility,
                "public_facing": visibility == "public",
                "reviewed_policy": True,
                "exceptions_enabled": True,
                "collect_allowed": True,
                "capture_audit_allowed": True,
                "backfill_allowed": True,
                "write_protected": False,
            },
            "contract": {"capture_surface_version": "0.2.0"},
            "registry_capture_surface_version": "0.2.0",
            "status_flags": ["pattern_gap_candidate"],
            "candidate_path_scan": {"truncated": False},
            "candidate_path_signals": [
                {
                    "term": "postmortem",
                    "pattern_family": "exception_pattern",
                    "suggested_event_type": "backfill_exception_candidate",
                    "source_rule_id": "backfill-rule:generic-exception",
                    "expected_review": "exception_event_or_no_packet",
                    "emission_status": "gap_candidate",
                    "path_hash": f"sha256:path-{visibility}",
                    "capture_suggestion": {"matched_rule_ids": []},
                }
            ],
        }

    report = build_exception_capture_gap_review_queue(
        {
            "audit_id": "dad:exception-capture-observed-audit",
            "capture_surface_version": "0.2.0",
            "status_counts": {"pattern_gap_candidate": 2},
            "input_hashes": {},
            "methodology_ref": "registry/exception-capture-pattern-registry.json",
            "methodology_hash": "sha256:test",
            "candidate_path_signal_summary": {"total": 2},
            "repos": [
                repo_row("sha256:path-private", "private"),
                repo_row("sha256:path-public", "public"),
            ],
        }
    )

    assert report["review_group_count"] == 2
    assert {group["path_hash"] for group in report["groups"]} == {
        "sha256:path-private",
        "sha256:path-public",
    }
    assert {group["visibility"] for group in report["groups"]} == {"private", "public"}
    assert len({group["review_group_id"] for group in report["groups"]}) == 2
    assert all(group["unknown_path_redaction_count"] == 1 for group in report["groups"])


def test_exception_backfill_wave_plan_keeps_metadata_wave_empty_until_proof_clears(
    tmp_path: Path,
) -> None:
    blocked_repo = tmp_path / "blocked"
    ready_repo = tmp_path / "ready"
    for repo in [blocked_repo, ready_repo]:
        docs = repo / "docs"
        docs.mkdir(parents=True)
        (docs / "postmortem.md").write_text("metadata-only placeholder", encoding="utf-8")
    (ready_repo / ".digital-asset").mkdir()
    (ready_repo / ".digital-asset" / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "ready",
                "schema_version": "0.1.0",
                "capture_surface_version": "0.2.0",
            }
        ),
        encoding="utf-8",
    )
    record_exception_event(
        ROOT,
        ready_repo,
        event_type="backfill_exception_candidate",
        summary="Historical candidate needs source review.",
        stage="discovery",
        severity="low",
        capture_contract="backfill_candidate",
        source_visibility="internal",
        context_refs=["docs/postmortem.md"],
    )
    policies = [
        ExceptionRepoPolicy(
            id="blocked",
            path=blocked_repo,
            alias="blocked",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=True,
        ),
        ExceptionRepoPolicy(
            id="ready",
            path=ready_repo,
            alias="ready",
            visibility="internal",
            exceptions_enabled=True,
            collect_allowed=True,
            capture_audit_allowed=True,
            backfill_allowed=True,
            approved_approval_ids=["APPROVED-BACKFILL"],
        ),
    ]

    plan = write_exception_backfill_wave_plan(
        ROOT,
        [blocked_repo, ready_repo],
        repo_policies=policies,
        output=tmp_path / "wave-plan.json",
        candidate_limit=0,
        per_wave_repo_limit=10,
    )
    waves = {wave["wave_id"]: wave for wave in plan["waves"]}
    backlogs = {backlog["backlog_id"]: backlog for backlog in plan["proof_backlogs"]}

    assert waves["metadata_backfill_candidate_wave"]["repo_count"] == 0
    assert waves["capture_surface_refresh_wave"]["repo_count"] == 1
    assert waves["capture_surface_refresh_wave"]["repos"][0]["repo_id"] == "blocked"
    assert "capture_surface_not_current" in waves["capture_surface_refresh_wave"][
        "repos"
    ][0]["proof_blockers"]
    assert waves["capture_gap_review_wave"]["repo_count"] == 1
    assert waves["capture_gap_review_wave"]["repos"][0]["repo_id"] == "ready"
    assert "emissions_missing_unverified_or_uncorrelated" in waves[
        "capture_gap_review_wave"
    ]["repos"][0]["proof_blockers"]
    assert backlogs["capture_surface_refresh_backlog"]["repo_count"] == 1
    assert backlogs["exhaustive_audit_backlog"]["repo_count"] == 0
    assert backlogs["emission_review_backlog"]["repo_count"] == 2
    assert backlogs["classifier_refresh_backlog"]["repo_count"] == 0
    assert backlogs["ready_for_source_packet_request"]["repo_count"] == 0


def test_exception_backfill_wave_plan_classifier_refresh_requires_stale_provenance() -> None:
    report = {
        "report_id": "dad:exception-backfill-readiness",
        "repos": [
            {
                "repo_id": "current-classifier",
                "repo_alias": "current-classifier",
                "path_hash": "sha256:current",
                "visibility": "internal",
                "public_facing": False,
                "backfill_readiness": "ready_with_reviewed_approval",
                "capture_surface_action": "current",
                "candidate_path_signal_count": 1,
                "candidate_path_scan": {
                    "truncated": False,
                    "limit": None,
                    "limit_mode": "exhaustive",
                    "max_scanned_files": 50000,
                    "stopped_reason": "exhausted_walk",
                },
                "candidate_path_signal_summary": {
                    "total": 1,
                    "count_scope": "complete_for_scanned_paths",
                    "truncated_repo_count": 0,
                    "omitted_signal_count_unknown": False,
                    "redacted_path_count": 0,
                    "unredacted_path_count": 1,
                    "by_source_rule_id": {"backfill-rule:generic-exception": 1},
                    "by_suggested_event_type": {"backfill_exception_candidate": 1},
                },
                "status_flags": [],
                "blocked_reasons": [],
                "next_actions": [],
            },
            {
                "repo_id": "stale-classifier",
                "repo_alias": "stale-classifier",
                "path_hash": "sha256:stale",
                "visibility": "internal",
                "public_facing": False,
                "backfill_readiness": "needs_full_scan_review",
                "capture_surface_action": "current",
                "candidate_path_signal_count": 1,
                "candidate_path_scan": {
                    "truncated": False,
                    "limit": None,
                    "limit_mode": "exhaustive",
                    "max_scanned_files": 50000,
                    "stopped_reason": "exhausted_walk",
                },
                "candidate_path_signal_summary": {
                    "total": 1,
                    "count_scope": "complete_for_scanned_paths",
                    "truncated_repo_count": 0,
                    "omitted_signal_count_unknown": False,
                    "redacted_path_count": 0,
                    "unredacted_path_count": 1,
                    "by_source_rule_id": {"backfill-rule:generic-exception": 1},
                    "by_suggested_event_type": {"backfill_exception_candidate": 1},
                },
                "classifier_version_stale": True,
                "classifier_version_stale_count": 1,
                "status_flags": [],
                "blocked_reasons": [],
                "next_actions": [],
            },
        ],
    }

    plan = build_exception_backfill_wave_plan(report, per_wave_repo_limit=10)
    backlogs = {backlog["backlog_id"]: backlog for backlog in plan["proof_backlogs"]}

    assert backlogs["classifier_refresh_backlog"]["repo_count"] == 1
    assert backlogs["classifier_refresh_backlog"]["repos"][0]["repo_id"] == "stale-classifier"
    assert "classifier_provenance_missing_or_stale" in backlogs[
        "classifier_refresh_backlog"
    ]["repos"][0]["proof_blockers"]
    assert backlogs["ready_for_source_packet_request"]["repo_count"] == 1
    assert backlogs["ready_for_source_packet_request"]["repos"][0]["repo_id"] == (
        "current-classifier"
    )


def test_observed_capture_audit_exhaustive_scan_has_file_ceiling(tmp_path: Path) -> None:
    repo = tmp_path / "repo-exhaustive-capped"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    for name in ["incident-one.md", "incident-two.md", "incident-three.md"]:
        (docs / name).write_text("metadata-only placeholder", encoding="utf-8")

    report = write_observed_capture_audit(
        ROOT,
        [repo],
        output=tmp_path / "audit.json",
        candidate_limit=0,
        max_scanned_files=2,
    )
    row = report["repos"][0]

    assert row["candidate_path_scan"]["limit"] is None
    assert row["candidate_path_scan"]["limit_mode"] == "exhaustive"
    assert row["candidate_path_scan"]["max_scanned_files"] == 2
    assert row["candidate_path_scan"]["scanned_file_count"] == 2
    assert row["candidate_path_scan"]["truncated"] is True
    assert row["candidate_path_scan"]["stopped_reason"] == "max_scanned_files_reached"
    assert "candidate_path_scan_truncated" in row["status_flags"]
