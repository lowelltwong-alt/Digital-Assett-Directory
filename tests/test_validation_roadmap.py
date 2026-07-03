from pathlib import Path

from digital_asset_directory.roadmap import check_roadmap, record_human_gate_evidence
from digital_asset_directory.validation import (
    _contains_readable_repo_relative_ref,
    _fix_outcome_semantic_errors,
    _path_identity_hash,
    _resolve_observed_audit_repo,
    validate_repo,
)

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def test_repo_contracts_validate():
    result = validate_repo(ROOT)
    assert result["valid"], result["errors"]


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
    assert any("validated but event link" in error for error in errors)


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
