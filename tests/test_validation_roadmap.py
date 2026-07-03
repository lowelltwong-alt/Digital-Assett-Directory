from copy import deepcopy
import json
from pathlib import Path

import pytest

from digital_asset_directory.config import ExceptionRepoPolicy
from digital_asset_directory.exception_capture import (
    load_capture_pattern_registry,
    write_exception_backfill_readiness,
    write_observed_capture_audit,
)
from digital_asset_directory.roadmap import check_roadmap, record_human_gate_evidence
from digital_asset_directory.validation import (
    _candidate_path_scan_staleness_errors,
    _contains_local_path_ref,
    _contains_readable_repo_relative_ref,
    _exception_event_taxonomy_by_type,
    _exception_lake_taxonomy_consistency_errors,
    _fix_outcome_semantic_errors,
    _language_registry_semantic_errors,
    _observed_audit_machine_evidence_errors,
    _path_identity_hash,
    _resolve_observed_audit_repo,
    _source_provenance_consistency_errors,
    _stale_report_input_hash_errors,
    validate_repo,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _language_semantic_errors_for(payload: dict) -> list[str]:
    trusted = _load_json("registry/trusted-source-registry.json")
    coding_assets = {
        item["asset_id"] for item in _load_json("registry/coding-asset-registry.json")["assets"]
    }
    reusable_assets = {
        item["asset_id"] for item in _load_json("assets/asset-registry.json")["assets"]
    }
    offerings = {
        item["offering_id"] for item in _load_json("registry/dad-offerings-registry.json")["offerings"]
    }
    return _language_registry_semantic_errors(
        payload,
        trusted,
        coding_assets | reusable_assets | offerings,
    )


def _exception_policy(repo: Path) -> ExceptionRepoPolicy:
    return ExceptionRepoPolicy(
        id="repo",
        path=repo,
        alias="repo",
        visibility="internal",
        exceptions_enabled=True,
        collect_allowed=True,
        capture_audit_allowed=True,
        backfill_allowed=True,
        approved_approval_ids=["APPROVED"],
    )


def test_repo_contracts_validate():
    result = validate_repo(ROOT)
    assert result["valid"], result["errors"]


def test_language_registry_semantics_reject_unknown_watch_source():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    target = payload["languages"][0]["codebase_watch_targets"][0]
    target["source_ids"].append("unknown-frontier-source")

    errors = _language_semantic_errors_for(payload)

    assert any("unknown trusted source unknown-frontier-source" in error for error in errors)


def test_language_registry_semantics_reject_source_url_mismatch():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    example = payload["languages"][0]["codebase_watch_targets"][0]["example_refs"][0]
    example["source_id"] = "python-core"
    example["ref"] = "https://github.com/astral-sh/ruff"

    errors = _language_semantic_errors_for(payload)

    assert any("does not match trusted source python-core" in error for error in errors)


def test_language_registry_semantics_reject_template_placeholder_leak():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    example = payload["languages"][0]["codebase_watch_targets"][0]["example_refs"][0]
    example["review_status"] = "template_placeholder"
    example["ref"] = "replace-with-language-official-docs"

    errors = _language_semantic_errors_for(payload)

    assert any("placeholder leaked into non-template row" in error for error in errors)


def test_language_registry_semantics_reject_disallowed_output_channel():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    payload["languages"][0]["frontier_promotion_policy"]["output_channels"].append(
        "C:/Users/lowel/private"
    )

    errors = _language_semantic_errors_for(payload)

    assert any("disallowed output channel" in error for error in errors)
    assert any("local absolute source reference" in error for error in errors)


def test_language_registry_semantics_reject_recommendable_template():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    template = next(
        language
        for language in payload["languages"]
        if language["language_id"] == "future-language-template"
    )
    template["recommendable"] = True

    errors = _language_semantic_errors_for(payload)

    assert any("template row must be recommendable=false" in error for error in errors)


def test_exception_lake_validation_flags_readable_repo_relative_refs():
    assert _contains_readable_repo_relative_ref(
        {"context_refs": ["repo-relative:docs/private-postmortem.md"]}
    )
    assert not _contains_readable_repo_relative_ref(
        {"context_refs": ["repo-relative-sha256:abc123"]}
    )


def test_exception_fix_outcome_semantic_validation_flags_false_validated_fix():
    errors = _fix_outcome_semantic_errors(
        {
            "decision": "fixed",
            "validation_status": "validated",
            "validation_refs": ["python -m pytest tests/test_fix.py"],
            "owner_authority": "repo",
            "event_lookup_status": "missing_from_lake",
            "canonical_event_id": "",
            "canonical_event_lookup_status": "missing_from_lake",
        },
        7,
    )

    assert any("missing event" in error for error in errors)
    assert any("lacks regression_test_refs" in error for error in errors)
    assert any("validated without complete" in error for error in errors)


def test_exception_validation_rejects_repo_prefixed_absolute_paths():
    assert _contains_local_path_ref({"return_address": "repo:C:/Users/lowel/private"})
    assert _contains_local_path_ref({"context_refs": ["repo:C:\\Users\\lowel\\private"]})
    assert not _contains_local_path_ref(
        {"return_address": "repo:.digital-asset/exceptions/outbox.jsonl"}
    )


def test_exception_validation_flags_provenance_mismatch():
    errors = _source_provenance_consistency_errors(
        {
            "source_repo": "repo-a",
            "source_visibility": "private",
            "source_provenance": {
                "canonical_repo_id": "repo-b",
                "source_visibility": "public",
            },
        },
        label="Exception lake event",
        line_number=3,
    )

    assert any("source_repo does not match" in error for error in errors)
    assert any("source_visibility does not match" in error for error in errors)


def test_exception_lake_taxonomy_validation_rejects_stale_dimensions():
    registry = _load_json("registry/exception-event-type-registry.json")
    event_taxonomy = _exception_event_taxonomy_by_type(registry)
    event = {
        "event_type": "secret_or_pii_detected",
        "taxonomy_dimensions": {
            "origin_surface": "unknown",
            "detection_mode": "unknown",
            "impact_domain": "unknown",
            "learning_route": "unknown",
            "default_handling": "unknown",
            "review_priority": "info",
        },
    }

    errors = _exception_lake_taxonomy_consistency_errors(
        event,
        event_taxonomy,
        line_number=12,
    )

    assert errors == [
        "Exception lake event taxonomy_dimensions do not match "
        "registry defaults on line 12: secret_or_pii_detected"
    ]


def test_stale_report_input_hash_errors_detect_changed_exception_report_input(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    input_path = repo / "processed" / "exceptions" / "lake" / "events.jsonl"
    report_path = repo / "processed" / "reports" / "exceptions_lake.json"
    input_path.parent.mkdir(parents=True)
    report_path.parent.mkdir(parents=True)
    input_path.write_text("{}\n", encoding="utf-8")
    report = {
        "input_hashes": {
            "processed/exceptions/lake/events.jsonl": "sha256:stale",
        }
    }

    errors = _stale_report_input_hash_errors(repo, report_path, report)

    assert errors == [
        "Stale report input hash processed/reports/exceptions_lake.json "
        "processed/exceptions/lake/events.jsonl: sha256:stale != "
        f"{_load_current_hash(input_path)}"
    ]


def _load_current_hash(path: Path) -> str:
    from digital_asset_directory.validation import _hash_path

    return _hash_path(path)


def test_observed_audit_external_repo_resolves_by_reviewed_path_hash(tmp_path: Path):
    hub = tmp_path / "hub"
    external = tmp_path / "elsewhere" / "Mock Trial4.26"
    hub.mkdir()
    external.mkdir(parents=True)
    repo_info = {
        "repo_id": "mock-trial-4-26",
        "path_hint": "Mock Trial4.26",
        "path_hash": _path_identity_hash(external),
    }

    resolved, error = _resolve_observed_audit_repo(
        hub,
        repo_info,
        {_path_identity_hash(external): external},
    )
    unresolved, unresolved_error = _resolve_observed_audit_repo(hub, repo_info, {})

    assert resolved == external.resolve()
    assert error == ""
    assert unresolved is None
    assert unresolved_error == "unresolved external audited repo"


def test_observed_audit_candidate_path_scan_staleness_detects_new_signal(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only\n", encoding="utf-8")
    policy = _exception_policy(repo)
    report_path = tmp_path / "observed-audit.json"
    report = write_observed_capture_audit(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=report_path,
        candidate_limit=10,
    )

    (docs / "incident-review.md").write_text("metadata-only\n", encoding="utf-8")
    errors = _candidate_path_scan_staleness_errors(
        ROOT,
        report_path,
        report["repos"][0],
        registry=load_capture_pattern_registry(ROOT),
        repo_policies=[policy],
        policy_paths={_path_identity_hash(repo): repo.resolve()},
    )

    assert any("Candidate path scan stale" in error for error in errors)
    assert any("scan_hash" in error for error in errors)


def test_observed_audit_machine_evidence_validation_recomputes_gap_counts(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "observed-audit.json"
    payload = {
        "audit_id": "dad:exception-capture-observed-audit",
        "repo_count": 1,
        "gap_count": 0,
        "gap_flag_count": 0,
        "strict_gap_count": 0,
        "strict_gap_flag_count": 0,
        "audit_scope": {"scope_satisfied": True},
        "repos": [
            {
                "status_flags": ["missed_capture_candidate"],
                "candidate_path_scan": {"truncated": False},
            }
        ],
        "phase6_machine_gate_evidence": {
            "gates": {
                "machine-evidence:phase-6-observed-repo-capture-audit-reviewed": {
                    "evidence_scope": "machine_only_not_roadmap_gate_evidence",
                    "human_gate_satisfied": False,
                    "machine_status": "passed",
                    "evidence": {"strict_gap_flag_count": 0},
                }
            }
        },
    }

    errors = _observed_audit_machine_evidence_errors(report_path, tmp_path, payload)

    assert any("gap_flag_count mismatch" in error for error in errors)
    assert any("strict_gap_flag_count mismatch" in error for error in errors)
    assert any("machine strict gap mismatch" in error for error in errors)
    assert any("machine_status mismatch" in error for error in errors)
    assert any("scope_satisfied mismatch" in error for error in errors)


def test_backfill_readiness_candidate_path_scan_staleness_detects_new_signal(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only\n", encoding="utf-8")
    policy = _exception_policy(repo)
    report_path = tmp_path / "backfill-readiness.json"
    report = write_exception_backfill_readiness(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=report_path,
        candidate_limit=10,
    )

    (docs / "governance-block.md").write_text("metadata-only\n", encoding="utf-8")
    errors = _candidate_path_scan_staleness_errors(
        ROOT,
        report_path,
        report["repos"][0],
        registry=load_capture_pattern_registry(ROOT),
        repo_policies=[policy],
        policy_paths={_path_identity_hash(repo): repo.resolve()},
    )

    assert any("Candidate path scan stale" in error for error in errors)
    assert any("scan_hash" in error for error in errors)


def test_seed_roadmap_file_gate_is_complete():
    result = check_roadmap(ROOT, update=False)
    assert result["phases"]["phase-0-seed"]["computed_status"] == "complete"


def test_roadmap_human_gate_requires_tracked_evidence(tmp_path: Path):
    (tmp_path / "roadmap").mkdir()
    (tmp_path / "required.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "roadmap" / "roadmap.yaml").write_text(
        """
roadmap_version: test
phases:
  - id: phase-test
    status: planned
    acceptance:
      required_files:
        - required.txt
      human_gates:
        - id: gate-test
          description: human reviewed the thing
""",
        encoding="utf-8",
    )

    missing = check_roadmap(tmp_path, update=False)
    assert missing["phases"]["phase-test"]["computed_status"] == "awaiting_human_gate"
    assert missing["phases"]["phase-test"]["human_gate_ids_unverified"] == ["gate-test"]

    record_human_gate_evidence(
        tmp_path,
        phase_id="phase-test",
        gate_id="gate-test",
        reviewer="Human",
        summary="Reviewed.",
        evidence=["roadmap/evidence/test.md"],
    )
    verified = check_roadmap(tmp_path, update=False)
    assert verified["phases"]["phase-test"]["computed_status"] == "complete"
    assert verified["phases"]["phase-test"]["human_gate_ids_verified"] == ["gate-test"]


def test_roadmap_human_gate_rejects_agent_reviewer(tmp_path: Path):
    (tmp_path / "roadmap").mkdir()
    (tmp_path / "required.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "roadmap" / "roadmap.yaml").write_text(
        """
roadmap_version: test
phases:
  - id: phase-test
    status: planned
    acceptance:
      required_files:
        - required.txt
      human_gates:
        - id: gate-test
          description: human reviewed the thing
""",
        encoding="utf-8",
    )

    record_human_gate_evidence(
        tmp_path,
        phase_id="phase-test",
        gate_id="gate-test",
        reviewer="codex",
        summary="Agent-observed, not human-reviewed.",
        evidence=["roadmap/evidence/test.md"],
    )
    result = check_roadmap(tmp_path, update=False)

    assert result["phases"]["phase-test"]["computed_status"] == "awaiting_human_gate"
    assert result["phases"]["phase-test"]["human_gate_ids_unverified"] == ["gate-test"]
    assert result["phases"]["phase-test"]["human_gate_unverified_details"] == [
        {
            "gate_id": "gate-test",
            "description": "human reviewed the thing",
            "reviewer": "codex",
            "reason": "missing_human_reviewer",
        }
    ]


def test_boundary_deferred_phase_does_not_compute_complete(tmp_path: Path):
    (tmp_path / "roadmap").mkdir()
    (tmp_path / "roadmap" / "roadmap.yaml").write_text(
        """
roadmap_version: test
phases:
  - id: phase-deferred
    status: boundary_deferred
    acceptance: {}
""",
        encoding="utf-8",
    )

    result = check_roadmap(tmp_path, update=False)

    assert result["phases"]["phase-deferred"]["computed_status"] == "boundary_deferred"
    assert result["phases"]["phase-deferred"]["status_warnings"] == []


def test_boundary_deferred_phase_accepts_human_deferred_gates(tmp_path: Path):
    (tmp_path / "roadmap").mkdir()
    (tmp_path / "roadmap" / "roadmap.yaml").write_text(
        """
roadmap_version: test
phases:
  - id: phase-deferred
    status: boundary_deferred
    acceptance:
      human_gates:
        - id: gate-deferred
          description: capability remains deferred behind boundary
""",
        encoding="utf-8",
    )
    record_human_gate_evidence(
        tmp_path,
        phase_id="phase-deferred",
        gate_id="gate-deferred",
        reviewer="Lowell",
        status="boundary_deferred",
        summary="Human approved keeping this capability deferred.",
        evidence=["roadmap/evidence/deferred.md"],
    )

    result = check_roadmap(tmp_path, update=False)

    assert result["phases"]["phase-deferred"]["computed_status"] == "boundary_deferred"
    assert result["phases"]["phase-deferred"]["human_gate_ids_boundary_deferred"] == [
        "gate-deferred"
    ]
    assert result["phases"]["phase-deferred"]["human_gate_ids_unverified"] == []


def test_boundary_deferred_phase_rejects_agent_deferred_gates(tmp_path: Path):
    (tmp_path / "roadmap").mkdir()
    (tmp_path / "roadmap" / "roadmap.yaml").write_text(
        """
roadmap_version: test
phases:
  - id: phase-deferred
    status: boundary_deferred
    acceptance:
      human_gates:
        - id: gate-deferred
          description: capability remains deferred behind boundary
""",
        encoding="utf-8",
    )
    record_human_gate_evidence(
        tmp_path,
        phase_id="phase-deferred",
        gate_id="gate-deferred",
        reviewer="codex",
        status="boundary_deferred",
        summary="Agent cannot approve deferred human gate.",
        evidence=["roadmap/evidence/deferred.md"],
    )

    result = check_roadmap(tmp_path, update=False)

    assert result["phases"]["phase-deferred"]["computed_status"] == "awaiting_human_gate"
    assert result["phases"]["phase-deferred"]["human_gate_unverified_details"] == [
        {
            "gate_id": "gate-deferred",
            "description": "capability remains deferred behind boundary",
            "reviewer": "codex",
            "reason": "missing_human_reviewer",
        }
    ]


def test_roadmap_command_requires_validation_evidence(tmp_path: Path):
    (tmp_path / "roadmap").mkdir()
    (tmp_path / "roadmap" / "roadmap.yaml").write_text(
        """
roadmap_version: test
phases:
  - id: phase-command
    status: planned
    acceptance:
      commands:
        - python -m pytest
""",
        encoding="utf-8",
    )

    result = check_roadmap(tmp_path, update=False)
    assert result["phases"]["phase-command"]["computed_status"] == ("awaiting_validation_evidence")
    assert result["phases"]["phase-command"]["commands_declared_not_executed_by_check"] == [
        "python -m pytest"
    ]


def test_roadmap_dependencies_block_later_phases(tmp_path: Path):
    (tmp_path / "roadmap").mkdir()
    (tmp_path / "roadmap" / "roadmap.yaml").write_text(
        """
roadmap_version: test
phases:
  - id: phase-1.5
    status: planned
    acceptance:
      human_gates:
        - id: gate-1-5
          description: scoring discipline reviewed
  - id: phase-2
    status: planned
    acceptance:
      depends_on:
        - phase-1.5
""",
        encoding="utf-8",
    )

    blocked = check_roadmap(tmp_path, update=False)
    assert blocked["phases"]["phase-2"]["computed_status"] == "blocked"
    assert blocked["phases"]["phase-2"]["blocked_dependencies"] == ["phase-1.5"]

    record_human_gate_evidence(
        tmp_path,
        phase_id="phase-1.5",
        gate_id="gate-1-5",
        reviewer="Human",
        summary="Reviewed.",
        evidence=["roadmap/evidence/phase-1.5.md"],
    )
    unblocked = check_roadmap(tmp_path, update=False)
    assert unblocked["phases"]["phase-1.5"]["computed_status"] == "complete"
    assert unblocked["phases"]["phase-2"]["computed_status"] == "complete"
