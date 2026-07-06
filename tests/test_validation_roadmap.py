from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner
import yaml

from digital_asset_directory.cli import app
from digital_asset_directory.config import ExceptionRepoPolicy
from digital_asset_directory.exception_capture import (
    build_phase6_machine_evidence_summary,
    load_capture_pattern_registry,
    write_exception_backfill_readiness,
    write_exception_backfill_wave_plan,
    write_exception_capture_gap_review_queue,
    write_exception_capture_remediation_plan,
    write_observed_capture_audit,
)
from digital_asset_directory.learning import _hash_path as _lesson_graph_hash_path
from digital_asset_directory.roadmap import (
    build_human_gate_review_packet,
    check_roadmap,
    record_human_gate_evidence,
)
from digital_asset_directory.validation import (
    _candidate_path_scan_staleness_errors,
    _capture_emission_simulation_errors,
    _contains_local_path_ref,
    _contains_readable_repo_relative_ref,
    _exception_capture_gap_review_queue_staleness_errors,
    _exception_capture_remediation_plan_staleness_errors,
    _exception_backfill_wave_plan_staleness_errors,
    _exception_event_taxonomy_by_type,
    _exception_lake_taxonomy_consistency_errors,
    _exception_route_bundle_errors,
    _fix_outcome_semantic_errors,
    _hash_path as _validation_hash_path,
    _language_registry_semantic_errors,
    _observed_audit_machine_evidence_errors,
    _path_identity_hash,
    _phase6_machine_evidence_summary_errors,
    _phase_command_evidence_errors,
    _repo_policy_identity_errors,
    _resolve_observed_audit_repo,
    _source_provenance_consistency_errors,
    _stale_report_input_hash_errors,
    _validate_lesson_graph_contract,
    validate_repo,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
RUNNER = CliRunner()


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


def _phase6_validation_gate(gate_id: str, status: str = "passed") -> dict:
    return {
        "evidence_id": f"machine-evidence:{gate_id}",
        "supports_human_gate_id": gate_id,
        "machine_status": status,
        "evidence_scope": "machine_only_not_roadmap_gate_evidence",
        "human_review_required": True,
        "human_gate_satisfied": False,
        "evidence": {},
    }


def _write_phase6_validation_sources(
    hub: Path,
    *,
    observed_status: str = "failed",
) -> None:
    reports = hub / "processed" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    capture_gate_ids = [
        "phase-6-capture-completeness-harness-reviewed",
        "phase-6-lawfirm-intake-missed-capture-regression",
        "phase-6-pattern-update-simulation-reviewed",
        "phase-6-all-asset-pattern-coverage-reviewed",
        "phase-6-sensitive-payload-negative-tests-reviewed",
    ]
    taxonomy_gate_id = "phase-6-taxonomy-route-coverage-reviewed"
    observed_gate_id = "phase-6-observed-repo-capture-audit-reviewed"
    payloads = {
        "exception_capture_completeness.json": {
            "generated_at": "2026-07-05T00:00:00+00:00",
            "report_id": "dad:exception-capture-completeness",
            "phase6_machine_gate_evidence": {
                "gates": {
                    gate["evidence_id"]: gate
                    for gate in [
                        _phase6_validation_gate(gate_id) for gate_id in capture_gate_ids
                    ]
                }
            },
        },
        "exception_capture_emission_simulation.json": {
            "generated_at": "2026-07-05T00:00:00+00:00",
            "report_id": "dad:exception-capture-emission-simulation",
            "limited": False,
            "coverage_status": "full_reviewed_case_set",
            "phase6_machine_gate_evidence": {
                "machine_status": "passed",
                "coverage_status": "full_reviewed_case_set",
                "limited": False,
                "human_gate_satisfied": False,
                "evidence_scope": "machine_only_not_roadmap_gate_evidence",
                "supports_human_gate_ids": [
                    "phase-6-capture-completeness-harness-reviewed",
                    "phase-6-pattern-update-simulation-reviewed",
                ],
            },
        },
        "exception_taxonomy_coverage.json": {
            "generated_at": "2026-07-05T00:00:00+00:00",
            "report_id": "dad:exception-taxonomy-coverage",
            "phase6_machine_gate_evidence": {
                "gates": {
                    f"machine-evidence:{taxonomy_gate_id}": _phase6_validation_gate(
                        taxonomy_gate_id
                    )
                }
            },
        },
        "exception_capture_observed_audit.json": {
            "generated_at": "2026-07-05T00:00:00+00:00",
            "audit_id": "dad:exception-capture-observed-audit",
            "phase6_machine_gate_evidence": {
                "gates": {
                    f"machine-evidence:{observed_gate_id}": _phase6_validation_gate(
                        observed_gate_id,
                        observed_status,
                    )
                }
            },
        },
    }
    for filename, payload in payloads.items():
        (reports / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def test_repo_contracts_validate():
    result = validate_repo(ROOT)
    assert result["valid"], result["errors"]


def test_phase8_requires_goal1_command_evidence():
    roadmap = yaml.safe_load((ROOT / "roadmap" / "roadmap.yaml").read_text(encoding="utf-8"))
    phase8 = next(
        phase for phase in roadmap["phases"] if phase["id"] == "phase-8-dad-local-deployment"
    )
    command_evidence = _load_json("roadmap/evidence/phase-8-dad-local-deployment.commands.json")
    evidence_commands = {item["command"] for item in command_evidence["commands"]}

    required_commands = {
        "python -m pytest tests/test_dad_local_deployment.py -q",
        "python -m digital_asset_directory.cli doctor --hub . --scope deployment",
        "user-shim asset-dir doctor --scope deployment from two non-DAD repos",
        (
            "user-shim asset-dir doctor --scope deployment from Mock Trial4.26 "
            "and LawFirm-os-intake without target worktree changes"
        ),
        (
            'user-shim asset-dir agent preflight --repo . --agent codex --task '
            '"Goal 1 deployment smoke from outside DAD"'
        ),
    }
    assert set(phase8["acceptance"]["required_files"]) >= {
        "roadmap/evidence/phase-8-dad-local-deployment.commands.json",
    }
    assert set(phase8["acceptance"]["commands"]) >= required_commands
    assert evidence_commands >= required_commands
    assert command_evidence["human_review_status"] == "pending"


def test_phase8_human_gate_review_packet_is_review_only():
    packet = build_human_gate_review_packet(ROOT, "phase-8-dad-local-deployment")

    assert packet["schema_version"] == "dad.roadmap.human-gate-review-packet.v1"
    assert packet["phase_id"] == "phase-8-dad-local-deployment"
    assert packet["packet_status"] == "review_input_only"
    assert packet["recommended_declared_status"] == "awaiting_human_gate"
    assert packet["computed_status"] == "awaiting_human_gate"
    assert packet["human_gate_satisfied"] is False
    assert packet["agent_review_satisfies_gate"] is False
    assert any("cannot approve a human gate" in risk for risk in packet["false_confidence_risks"])
    assert "roadmap/gate-evidence.json" in packet["human_recording_instructions"]
    assert "approve public release" in packet["authority_boundary"]
    assert "authorize enrollment" in packet["authority_boundary"]
    assert "cross-repo writes" in packet["authority_boundary"]
    assert all(gate["current_status"] == "unverified" for gate in packet["human_gates"])
    assert all(gate["human_review_required"] is True for gate in packet["human_gates"])
    assert all(gate["agent_review_satisfies_gate"] is False for gate in packet["human_gates"])
    assert all(
        gate["recommended_gate_evidence_if_verified"]["status"] == "verified"
        for gate in packet["human_gates"]
    )
    assert {
        "phase-8-local-install-reviewed",
        "phase-8-hub-locator-reviewed",
        "phase-8-doctor-smoke-reviewed",
        "phase-8-unavailable-policy-reviewed",
    } == {gate["gate_id"] for gate in packet["human_gates"]}


def test_roadmap_human_gate_review_packet_cli_writes_review_only_packet(tmp_path: Path):
    output = tmp_path / "phase8.packet.json"

    result = RUNNER.invoke(
        app,
        [
            "roadmap",
            "human-gate-review-packet",
            "phase-8-dad-local-deployment",
            "--output",
            str(output),
            "--hub",
            str(ROOT),
        ],
    )

    assert result.exit_code == 0, result.output
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["phase_id"] == "phase-8-dad-local-deployment"
    assert packet["packet_status"] == "review_input_only"
    assert packet["human_gate_satisfied"] is False
    assert packet["agent_review_satisfies_gate"] is False
    gate_evidence = _load_json("roadmap/gate-evidence.json")
    assert "phase-8-local-install-reviewed" not in gate_evidence["human_gates"]


def test_phase8_command_evidence_validation_rejects_stale_or_promoted_packet(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "roadmap" / "evidence").mkdir(parents=True)
    roadmap = yaml.safe_load((ROOT / "roadmap" / "roadmap.yaml").read_text(encoding="utf-8"))
    command_evidence = _load_json("roadmap/evidence/phase-8-dad-local-deployment.commands.json")
    mutated = deepcopy(command_evidence)
    mutated["human_review_status"] = "approved_by_agent"
    mutated["commands"] = mutated["commands"][:-1]
    (repo / "roadmap" / "roadmap.yaml").write_text(
        yaml.safe_dump(roadmap, sort_keys=False),
        encoding="utf-8",
    )
    (repo / "roadmap" / "evidence" / "phase-8-dad-local-deployment.commands.json").write_text(
        json.dumps(mutated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    errors = _phase_command_evidence_errors(repo)

    assert any("commands differ from roadmap acceptance" in error for error in errors)
    assert any("must remain pending" in error for error in errors)


def test_repo_policy_identity_validation_rejects_duplicate_ids_aliases_and_paths(
    tmp_path: Path,
) -> None:
    shared_path = tmp_path / "same"
    policies = [
        SimpleNamespace(id="repo-a", alias="shared", path=shared_path),
        SimpleNamespace(id="repo-a", alias="unique-a", path=tmp_path / "other"),
        SimpleNamespace(id="repo-b", alias="shared", path=tmp_path / "third"),
        SimpleNamespace(id="repo-c", alias="unique-c", path=shared_path),
    ]

    errors = _repo_policy_identity_errors("mail.repos", policies)

    assert any("duplicate repo id: repo-a" in error for error in errors)
    assert any("duplicate repo alias: shared" in error for error in errors)
    assert any("maps one resolved path to multiple repo ids" in error for error in errors)


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


def test_language_registry_semantics_reject_duplicate_proof_surface_categories():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    duplicate = deepcopy(payload["proof_surface_categories"][0])
    duplicate["label"] = "Duplicate proof surface with same id"
    payload["proof_surface_categories"].append(duplicate)

    errors = _language_semantic_errors_for(payload)

    assert any("duplicate proof_surface_categories category_id" in error for error in errors)


def test_language_registry_semantics_reject_unknown_proof_surface_ref():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    payload["languages"][0]["proof_surface_refs"].append("proof:does-not-exist")

    errors = _language_semantic_errors_for(payload)

    assert any("unknown proof surface proof:does-not-exist" in error for error in errors)


def test_language_registry_semantics_reject_duplicate_proof_surface_ref():
    payload = deepcopy(_load_json("registry/language-coding-advantage-registry.json"))
    payload["languages"][0]["proof_surface_refs"].append(
        payload["languages"][0]["proof_surface_refs"][0]
    )

    errors = _language_semantic_errors_for(payload)

    assert any("duplicate proof_surface_refs values" in error for error in errors)


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
    assert _contains_readable_repo_relative_ref(
        {"notes": "See Repo-Relative:docs/private-postmortem.md before review."}
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
    assert _contains_local_path_ref(
        {"notes": "private file is C:/Users/lowel/private/report.txt"}
    )
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


def _exception_route_bundle_inputs() -> tuple[dict, dict, dict, str]:
    return (
        _load_json("registry/exception-event-type-registry.json"),
        _load_json("registry/exception-capture-pattern-registry.json"),
        _load_json(
            "assets/coding-harnesses/exception-capture-completeness/examples/"
            "synthetic-capture-scenarios.json"
        ),
        (ROOT / "templates" / "downstream" / "EXCEPTIONS_README.md").read_text(
            encoding="utf-8"
        ),
    )


def test_exception_route_bundle_validation_accepts_current_bundle():
    event_registry, capture_registry, scenarios, readme = _exception_route_bundle_inputs()

    errors = _exception_route_bundle_errors(
        exception_type_registry=event_registry,
        capture_pattern_registry=capture_registry,
        capture_scenarios=scenarios,
        downstream_readme_text=readme,
    )

    assert errors == []
    assert "$HOME/.dad/bin/asset-dir" in readme
    assert "$HOME\\.dad\\bin\\asset-dir.ps1" in readme


def test_exception_route_bundle_validation_rejects_missing_required_field():
    event_registry, capture_registry, scenarios, readme = _exception_route_bundle_inputs()
    case = next(
        item for item in scenarios["cases"] if item["scenario_id"] == "code-change-exception"
    )
    case["expected"]["required_fields"].remove("validation_ref_or_gap")

    errors = _exception_route_bundle_errors(
        exception_type_registry=event_registry,
        capture_pattern_registry=capture_registry,
        capture_scenarios=scenarios,
        downstream_readme_text=readme,
    )

    assert any(
        "expected required_fields omit ['validation_ref_or_gap']" in error
        for error in errors
    )


def test_exception_route_bundle_validation_rejects_claimed_rule_signal_mismatch():
    event_registry, capture_registry, scenarios, readme = _exception_route_bundle_inputs()
    case = next(
        item for item in scenarios["cases"] if item["scenario_id"] == "code-change-exception"
    )
    case["signals"].remove("code_change_exception")

    errors = _exception_route_bundle_errors(
        exception_type_registry=event_registry,
        capture_pattern_registry=capture_registry,
        capture_scenarios=scenarios,
        downstream_readme_text=readme,
    )

    assert any(
        "scenario does not match claimed rule: code-change-exception "
        "exception-capture-rule:code-change-exception" in error
        for error in errors
    )


def test_exception_route_bundle_validation_rejects_missing_downstream_event_guidance():
    event_registry, capture_registry, scenarios, readme = _exception_route_bundle_inputs()
    readme = readme.replace("code_change_exception", "removed_code_change_route")

    errors = _exception_route_bundle_errors(
        exception_type_registry=event_registry,
        capture_pattern_registry=capture_registry,
        capture_scenarios=scenarios,
        downstream_readme_text=readme,
    )

    assert any(
        "downstream README omits event_type: code_change_exception" in error
        for error in errors
    )


def test_exception_route_bundle_validation_rejects_missing_backfill_only_scenario():
    event_registry, capture_registry, scenarios, readme = _exception_route_bundle_inputs()
    scenarios["cases"] = [
        case
        for case in scenarios["cases"]
        if case["scenario_id"] != "backfill-command-timeout"
    ]

    errors = _exception_route_bundle_errors(
        exception_type_registry=event_registry,
        capture_pattern_registry=capture_registry,
        capture_scenarios=scenarios,
        downstream_readme_text=readme,
    )

    assert any(
        "missing reviewed synthetic scenario for emitting rule: "
        "backfill-rule:command-timeout" in error
        for error in errors
    )


def test_exception_route_bundle_validation_rejects_backfill_missing_required_field():
    event_registry, capture_registry, scenarios, readme = _exception_route_bundle_inputs()
    case = next(
        item
        for item in scenarios["cases"]
        if item["scenario_id"] == "backfill-command-timeout"
    )
    case["expected"]["required_fields"].remove("source_rule_id")

    errors = _exception_route_bundle_errors(
        exception_type_registry=event_registry,
        capture_pattern_registry=capture_registry,
        capture_scenarios=scenarios,
        downstream_readme_text=readme,
    )

    assert any(
        "backfill scenario required_fields omit ['source_rule_id']" in error
        for error in errors
    )


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


def test_lesson_graph_hash_ignores_generated_lesson_indexes(tmp_path: Path):
    lessons = tmp_path / "raw" / "lessons"
    dated = lessons / "2026-07-03"
    by_repo = lessons / "by-repo"
    by_capability = lessons / "by-capability"
    dated.mkdir(parents=True)
    by_repo.mkdir(parents=True)
    by_capability.mkdir(parents=True)
    (dated / "canonical.json").write_text('{"lesson_id":"dad:lesson:x"}\n', encoding="utf-8")
    (by_repo / "repo.jsonl").write_text('{"lesson_id":"dad:lesson:x"}\n', encoding="utf-8")
    (by_capability / "cap.jsonl").write_text('{"lesson_id":"dad:lesson:x"}\n', encoding="utf-8")

    before = (_lesson_graph_hash_path(lessons), _validation_hash_path(lessons))
    (by_repo / "repo.jsonl").write_text('{"lesson_id":"dad:lesson:y"}\n', encoding="utf-8")
    (by_capability / "cap.jsonl").write_text('{"lesson_id":"dad:lesson:y"}\n', encoding="utf-8")

    assert (_lesson_graph_hash_path(lessons), _validation_hash_path(lessons)) == before


def test_lesson_graph_manifest_validation_fails_closed_on_stale_input_hash(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    (repo / "registry").mkdir(parents=True)
    (repo / "schemas").mkdir()
    for rel in [
        "registry/graph-edge-registry.json",
        "schemas/graph-edge-registry.schema.json",
        "schemas/lesson-graph.schema.json",
    ]:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    registry = {
        "schemas": {
            "graph_edge_registry": "schemas/graph-edge-registry.schema.json",
            "lesson_graph": "schemas/lesson-graph.schema.json",
        }
    }
    lessons = repo / "raw" / "lessons" / "2026-07-03"
    lessons.mkdir(parents=True)
    (lessons / "lesson.json").write_text('{"lesson_id":"dad:lesson:test"}\n', encoding="utf-8")
    manifest_path = repo / "processed" / "learning" / "lesson-graph-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"input_hashes": {"raw/lessons": "sha256:stale"}}),
        encoding="utf-8",
    )
    errors: list[str] = []
    checked: list[str] = []

    _validate_lesson_graph_contract(repo, registry, errors, checked)

    assert "processed/learning/lesson-graph-manifest.json" in checked
    assert errors == [
        "Stale lesson graph manifest input hash raw/lessons: "
        f"sha256:stale != {_validation_hash_path(repo / 'raw' / 'lessons')}"
    ]


def test_repo_inventory_report_input_hashes_are_validated(tmp_path: Path):
    repo = tmp_path / "repo"
    input_path = repo / "src" / "digital_asset_directory" / "dad_library.py"
    report_path = repo / "processed" / "repo_inventory" / "reconciled_inventory.json"
    input_path.parent.mkdir(parents=True)
    report_path.parent.mkdir(parents=True)
    input_path.write_text("print('changed')\n", encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "input_hashes": {
                    "src/digital_asset_directory/dad_library.py": "sha256:stale"
                },
            }
        ),
        encoding="utf-8",
    )

    errors = _stale_report_input_hash_errors(
        repo,
        report_path,
        json.loads(report_path.read_text(encoding="utf-8")),
    )

    assert errors == [
        "Stale report input hash processed/repo_inventory/reconciled_inventory.json "
        "src/digital_asset_directory/dad_library.py: sha256:stale != "
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


def test_observed_audit_candidate_path_scan_tolerates_protected_repo_drift(
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
    row = report["repos"][0]
    row["repo"]["repo_id"] = "logos-scripture-graph"
    row["repo"]["write_protected"] = True

    (docs / "incident-review.md").write_text("metadata-only\n", encoding="utf-8")
    errors = _candidate_path_scan_staleness_errors(
        ROOT,
        report_path,
        row,
        registry=load_capture_pattern_registry(ROOT),
        repo_policies=[policy],
        policy_paths={_path_identity_hash(repo): repo.resolve()},
    )

    assert errors == []


def test_observed_audit_bounded_scan_tolerates_same_evidence_file_count_drift(
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
        candidate_limit=1,
    )

    assert report["repos"][0]["candidate_path_scan"]["stopped_reason"] == (
        "candidate_limit_reached"
    )
    (docs / "aaa-note.txt").write_text("metadata-only\n", encoding="utf-8")
    errors = _candidate_path_scan_staleness_errors(
        ROOT,
        report_path,
        report["repos"][0],
        registry=load_capture_pattern_registry(ROOT),
        repo_policies=[policy],
        policy_paths={_path_identity_hash(repo): repo.resolve()},
    )

    assert errors == []


def test_observed_audit_exhaustive_candidate_scan_staleness_recomputes_exhaustive(
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
        candidate_limit=0,
    )

    assert report["repos"][0]["candidate_path_scan"]["limit"] is None
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
    assert any("candidate_path_signal_count" in error for error in errors)


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


def test_phase6_machine_evidence_summary_validation_recomputes_source_reports(
    tmp_path: Path,
) -> None:
    _write_phase6_validation_sources(tmp_path, observed_status="failed")
    summary = build_phase6_machine_evidence_summary(
        tmp_path,
        generated_at="2026-07-05T01:00:00+00:00",
    )
    report_path = (
        tmp_path
        / "processed"
        / "reports"
        / "phase6_exception_capture_machine_evidence_summary.json"
    )
    report_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _write_phase6_validation_sources(tmp_path, observed_status="passed")
    errors = _phase6_machine_evidence_summary_errors(report_path, tmp_path, summary)

    assert any("overall_machine_status mismatch" in error for error in errors)
    assert any("blocked_gate_ids mismatch" in error for error in errors)
    assert any("source_reports mismatch" in error for error in errors)


def test_capture_emission_simulation_validation_rejects_legacy_gate_slugs(
    tmp_path: Path,
) -> None:
    payload = {
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "required_provenance_fields": [
            "matched_rule_ids",
            "methodology_hash",
            "suggestion_id",
            "update_required",
        ],
        "initial_update_required_count": 0,
        "refreshed_emission_count": 0,
        "cases": [
            {
                "scenario_id": "legacy-gate-slug",
                "passed": True,
                "initial_update_required": False,
                "initial_repo_capture_surface_version": "0.4.0",
                "emission_repo_capture_surface_version": "0.4.0",
                "suggestion_comparisons": {"packet_classes": True},
                "observed": {"passed": True},
                "emitted_packets": [],
            }
        ],
        "phase6_machine_gate_evidence": {
            "evidence_scope": "machine_only_not_roadmap_gate_evidence",
            "machine_status": "passed",
            "human_gate_satisfied": False,
            "supports_human_gate_ids": [
                "synthetic-harness-proves-dad-worthy-patterns-become-packets",
                "pattern-update-simulation-proves-new-required-fields",
            ],
        },
    }

    errors = _capture_emission_simulation_errors(
        tmp_path / "emission.json",
        tmp_path,
        payload,
    )

    assert any("missing supported gate ids" in error for error in errors)
    assert any("non-roadmap gate ids" in error for error in errors)


def test_capture_emission_simulation_validation_rejects_partial_gate_support(
    tmp_path: Path,
) -> None:
    payload = {
        "coverage_status": "limited_diagnostic",
        "limited": True,
        "full_reviewed_case_count": 70,
        "emitted_reviewed_case_count": 1,
        "omitted_reviewed_scenario_ids": ["omitted-scenario"],
        "case_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "required_provenance_fields": [
            "matched_rule_ids",
            "methodology_hash",
            "suggestion_id",
            "update_required",
        ],
        "initial_update_required_count": 0,
        "refreshed_emission_count": 0,
        "cases": [
            {
                "scenario_id": "partial-run",
                "passed": True,
                "initial_update_required": False,
                "initial_repo_capture_surface_version": "0.4.0",
                "emission_repo_capture_surface_version": "0.4.0",
                "suggestion_comparisons": {"packet_classes": True},
                "observed": {"passed": True},
                "emitted_packets": [],
            }
        ],
        "phase6_machine_gate_evidence": {
            "evidence_scope": "machine_only_not_roadmap_gate_evidence",
            "coverage_status": "limited_diagnostic",
            "limited": True,
            "machine_status": "passed",
            "human_gate_satisfied": False,
            "supports_human_gate_ids": [
                "phase-6-capture-completeness-harness-reviewed",
                "phase-6-pattern-update-simulation-reviewed",
            ],
        },
    }

    errors = _capture_emission_simulation_errors(
        tmp_path / "emission.json",
        tmp_path,
        payload,
    )

    assert any("machine_status mismatch" in error for error in errors)
    assert any("limited report lists gate ids" in error for error in errors)


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


def test_backfill_wave_plan_validation_detects_stale_proof_backlogs(tmp_path: Path):
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only\n", encoding="utf-8")
    policy = _exception_policy(repo)
    report_path = tmp_path / "backfill-wave-plan.json"
    plan = write_exception_backfill_wave_plan(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=report_path,
        candidate_limit=0,
        max_scanned_files=10,
    )
    mutated = deepcopy(plan)
    mutated["proof_backlogs"] = []

    errors = _exception_backfill_wave_plan_staleness_errors(
        ROOT,
        report_path,
        mutated,
    )

    assert len(errors) == 1
    assert errors[0].endswith("backfill-wave-plan.json: proof_backlogs mismatch")


def test_capture_remediation_plan_validation_detects_stale_lanes(tmp_path: Path):
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only\n", encoding="utf-8")
    policy = _exception_policy(repo)
    report_path = tmp_path / "capture-remediation.json"
    plan = write_exception_capture_remediation_plan(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=report_path,
        candidate_limit=0,
        max_scanned_files=10,
    )
    mutated = deepcopy(plan)
    mutated["lanes"] = []

    errors = _exception_capture_remediation_plan_staleness_errors(
        ROOT,
        report_path,
        mutated,
    )

    assert len(errors) == 1
    assert errors[0].endswith("capture-remediation.json: lanes mismatch")


def test_capture_gap_review_queue_validation_detects_stale_groups(tmp_path: Path):
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only\n", encoding="utf-8")
    policy = _exception_policy(repo)
    report_path = tmp_path / "capture-gap-queue.json"
    report = write_exception_capture_gap_review_queue(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=report_path,
        candidate_limit=0,
        max_scanned_files=10,
    )
    mutated = deepcopy(report)
    mutated["groups"] = []

    errors = _exception_capture_gap_review_queue_staleness_errors(
        ROOT,
        report_path,
        mutated,
    )

    assert len(errors) == 1
    assert errors[0].endswith("capture-gap-queue.json: groups mismatch")


def test_capture_gap_review_queue_validation_detects_authority_tampering(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "postmortem.md").write_text("metadata-only\n", encoding="utf-8")
    policy = _exception_policy(repo)
    report_path = tmp_path / "capture-gap-queue.json"
    report = write_exception_capture_gap_review_queue(
        ROOT,
        [repo],
        repo_policies=[policy],
        output=report_path,
        candidate_limit=0,
        max_scanned_files=10,
    )
    mutated = deepcopy(report)
    mutated["authority_boundary"] = "Approved to write target repos."

    errors = _exception_capture_gap_review_queue_staleness_errors(
        ROOT,
        report_path,
        mutated,
    )

    assert len(errors) == 1
    assert errors[0].endswith("capture-gap-queue.json: authority_boundary mismatch")


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
