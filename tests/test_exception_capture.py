from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from jsonschema.validators import validator_for

from digital_asset_directory.cli import (
    _capture_audit_gap_count,
    _exception_backfill_approval_block_reason,
    _discover_exception_repos,
    _exception_backfill_policy_block_reason,
    _exception_record_policy_block_reason,
)
from digital_asset_directory.config import ExceptionRepoPolicy, MailRepoPolicy
from digital_asset_directory.exception_capture import (
    evaluate_exception_taxonomy_coverage,
    evaluate_capture_case,
    evaluate_capture_scenarios,
    load_capture_pattern_registry,
    load_capture_scenarios,
    write_exception_backfill_readiness,
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

    assert report["failed_count"] == 0
    assert report["missing_required_pattern_families"] == []
    assert report["missing_reviewed_rule_ids"] == []
    assert report["undeclared_matched_rule_ids"] == []
    assert report["unknown_declared_rule_ids"] == []
    assert report["covered_reviewed_rule_count"] == report["reviewed_rule_count"]
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()


def test_exception_taxonomy_coverage_distinguishes_manual_and_signal_routes(
    tmp_path: Path,
) -> None:
    report = evaluate_exception_taxonomy_coverage(
        ROOT,
        SCENARIOS,
        output=tmp_path / "taxonomy-coverage.json",
    )

    assert report["event_type_count"] >= 50
    assert report["reviewed_unrouted_event_types"] == []
    assert report["learnable_unrouted_event_types"] == []
    assert report["capture_rule_events_missing_synthetic_cases"] == []
    assert "failed_command" not in report["manual_only_event_types"]
    assert "tool_unavailable" not in report["manual_only_event_types"]
    assert "validation_command_missing" in report["manual_only_event_types"]
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


def test_observed_capture_audit_reports_existing_repo_outbox_emission(tmp_path: Path) -> None:
    repo = tmp_path / "repo-with-outboxes"
    repo.mkdir()
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
    row = report["repos"][0]

    assert "outbox_emission_present" in row["status_flags"]
    assert "missed_capture_candidate" not in row["status_flags"]
    assert row["packet_classes"] == ["exception_event", "ordinary_mail"]
    assert (tmp_path / "audit.json").exists()
    assert (tmp_path / "audit.md").exists()


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

    assert "missed_capture_candidate" in row["status_flags"]
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
    assert row_summary["by_emission_status"]["gap_candidate"] == 2
    assert report_summary == row_summary
    assert "## Candidate Suggested Event Types" in md_text
    assert "`tool_unavailable`: 1" in md_text
    assert "`review_finding`: 1" in md_text
    assert "`backfill-rule:tool-unavailable`: 1" in md_text
    assert "`backfill-rule:review-finding`: 1" in md_text


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
    assert "candidate_path_scan_truncated" in audit_md
    assert "bounded first-N samples" in audit_md


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

    assert rows["ready-external"]["backfill_readiness"] == "ready_with_reviewed_approval"
    assert rows["ready-external"]["blocked_reasons"] == []
    assert rows["ready-external"]["candidate_path_signal_count"] == 1
    assert rows["ready-external"]["candidate_path_signal_summary"]["total"] == 1
    assert rows["protected"]["backfill_readiness"] == "central_only_or_blocked"
    assert any("write_protected" in reason for reason in rows["protected"]["blocked_reasons"])
    assert rows["blocked"]["backfill_readiness"] == "blocked_by_policy_or_no_signals"
    assert "backfill_allowed=false" in rows["blocked"]["blocked_reasons"]
    assert report["readiness_counts"]["ready_with_reviewed_approval"] == 1
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
