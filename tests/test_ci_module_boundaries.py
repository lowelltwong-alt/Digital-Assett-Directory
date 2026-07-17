from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from shutil import copytree

import yaml

from digital_asset_directory.ci_module_boundaries import (
    build_metadata_only_adoption_audit,
    evaluate_changes,
    load_manifest,
    parse_changes,
    scope_digest,
    validate_manifest,
)
from digital_asset_directory.ci_module_boundary_github import validate_github_workflows


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = (
    ROOT
    / "assets"
    / "coding-harnesses"
    / "ci-module-boundary-governance"
    / "examples"
    / "module-boundaries.yaml"
)


def manifest() -> dict:
    return load_manifest(EXAMPLE)


def error_codes(result: dict) -> set[str]:
    return {item["code"] for item in result["diagnostics"] if item["severity"] == "error"}


def test_yaml12_manifest_loader_does_not_mutate_pyyaml_safe_loader():
    assert yaml.safe_load("ai_agnostic: true\n") == {"ai_agnostic": True}


def test_example_contract_is_valid_and_reports_dependency_coverage_limit():
    result = validate_manifest(manifest(), today=date(2026, 7, 16))
    assert result["status"] == "valid"
    assert result["dependency_coverage"] == "coverage_unavailable"
    assert result["summary"] == {"errors": 0, "warnings": 0, "modules": 3, "suites": 7, "workflows": 2}


def test_ocr_only_does_not_trigger_simulator_or_browser():
    result = evaluate_changes(manifest(), ["modules/ocr/src/reader.py"])
    assert result["selected_modules"] == ["ocr"]
    assert result["selected_suites"] == ["ci-contract", "ocr"]


def test_simulator_and_ui_changes_select_only_owned_module_suites():
    simulator = evaluate_changes(manifest(), ["modules/simulator/src/engine.py"])
    ui = evaluate_changes(manifest(), ["modules/ui/src/facade.ts"])
    assert simulator["selected_suites"] == ["ci-contract", "simulator"]
    assert ui["selected_suites"] == ["browser", "ci-contract"]


def test_declared_contract_edge_selects_downstream_browser_and_integration():
    result = evaluate_changes(manifest(), ["modules/ocr/contracts/result.json"])
    assert result["selected_modules"] == ["ocr", "simulator", "ui"]
    assert result["selected_suites"] == ["browser", "ci-contract", "ocr", "simulator", "ui-integration"]
    propagated = [reason for reason in result["reasons"] if reason["kind"] == "direct_dependent"]
    assert [(reason["from_module_id"], reason["module_id"]) for reason in propagated] == [
        ("ocr", "simulator"),
        ("simulator", "ui"),
    ]


def test_dependency_cycles_and_cross_module_edges_outside_scope_fail_closed():
    cyclic = manifest()
    cyclic["dependencies"].append(
        {
            "edge_id": "ui-to-ocr",
            "from": "ui",
            "to": "ocr",
            "edge_type": "direct_dependent",
            "on": ["contract"],
            "evidence": "Synthetic negative cycle.",
        }
    )
    escaped = manifest()
    escaped["suites"][5]["scope_modules"] = ["ocr", "ui"]
    assert "dependency_cycle" in error_codes(validate_manifest(cyclic, today=date(2026, 7, 16)))
    assert "suite_dependency_outside_scope" in error_codes(validate_manifest(escaped, today=date(2026, 7, 16)))


def test_workflow_change_runs_lightweight_contract_only():
    result = evaluate_changes(manifest(), [".github/workflows/selector.yml"])
    assert result["selected_modules"] == []
    assert result["selected_suites"] == ["ci-contract"]


def test_scheduled_full_regression_is_separate_and_available():
    result = evaluate_changes(manifest(), [], event="schedule")
    assert result["selected_suites"] == ["scheduled-full"]


def test_generated_artifact_is_ignored_without_authoritative_input_change():
    result = evaluate_changes(manifest(), ["modules/simulator/generated/stale.json"])
    assert result["selected_modules"] == []
    assert result["selected_suites"] == ["ci-contract"]
    assert result["generated_artifacts_ignored"] == ["modules/simulator/generated/stale.json"]


def test_renamed_paths_are_both_evaluated_and_moved_out_path_fails_contract():
    inside = evaluate_changes(
        manifest(),
        parse_changes(["R100\tmodules/ocr/src/old.py\tmodules/ocr/src/new.py"]),
    )
    moved_out = evaluate_changes(
        manifest(),
        parse_changes(["R100\tmodules/ocr/src/old.py\tmisc/new.py"]),
    )
    assert inside["status"] == "ok"
    assert inside["selected_suites"] == ["ci-contract", "ocr"]
    assert moved_out["status"] == "contract_failed"
    assert {item["code"] for item in moved_out["diagnostics"]} == {"unowned_changed_path"}


def test_observed_missing_dependency_fails_closed():
    result = validate_manifest(
        manifest(),
        observed_dependencies=[("simulator", "ocr")],
        today=date(2026, 7, 16),
    )
    assert result["status"] == "invalid"
    assert "missing_dependency_edge" in error_codes(result)


def test_broad_glob_duplicate_events_and_required_deadlock_are_rejected():
    broad = manifest()
    broad["modules"][0]["triggers"][0]["paths"] = ["modules/**"]
    events = manifest()
    events["workflows"][0]["events"] = ["pull_request", "push_all_branches"]
    events["workflows"][0]["always_reports"] = False
    assert "overly_broad_glob" in error_codes(validate_manifest(broad, today=date(2026, 7, 16)))
    codes = error_codes(validate_manifest(events, today=date(2026, 7, 16)))
    assert {"duplicate_push_pull_request", "required_check_deadlock"}.issubset(codes)


def test_provider_workflow_scan_rejects_unscoped_modules_and_required_path_filters(tmp_path: Path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    broad_path = workflow_dir / "broad.yml"
    broad_path.write_text("on:\n  pull_request: {}\njobs: {}\n", encoding="utf-8")
    required_path = workflow_dir / "required.yml"
    required_path.write_text(
        "on:\n  pull_request:\n    paths: [modules/ocr/**]\njobs: {}\n",
        encoding="utf-8",
    )
    current = manifest()
    current["workflows"] = [
        {
            "workflow_id": "broad",
            "provider_path": ".github/workflows/broad.yml",
            "lane": "module",
            "events": ["pull_request"],
            "required_check": False,
            "always_reports": False,
            "scope": "module",
        },
        {
            "workflow_id": "required",
            "provider_path": ".github/workflows/required.yml",
            "lane": "ci_contract",
            "events": ["pull_request"],
            "required_check": True,
            "always_reports": True,
            "scope": "selector",
        },
    ]
    codes = {item["code"] for item in validate_github_workflows(tmp_path, current)}
    assert {"module_workflow_bypasses_selector", "required_check_deadlock"}.issubset(codes)


def test_scope_cannot_silently_broaden_and_exception_must_be_current_and_reviewed():
    base = manifest()
    head = deepcopy(base)
    head["modules"][0]["triggers"][0]["paths"].append("modules/ocr/experimental/**")
    assert scope_digest(base) != scope_digest(head)
    blocked = validate_manifest(head, base_manifest=base, today=date(2026, 7, 16))
    assert "scope_broadening" in error_codes(blocked)

    head["exceptions"] = [
        {
            "exception_id": "reviewed-scope-change",
            "codes": ["scope_broadening"],
            "diagnostic_scopes": ["manifest:scope"],
            "owner": "ocr-owner",
            "reason": "Shadow validation before baseline approval.",
            "expires_on": "2026-07-31",
            "reviewed_by": "platform-owner",
            "reviewed_at": "2026-07-16T12:00:00-04:00",
            "review_ref": "review:ci-scope-1",
        }
    ]
    allowed = validate_manifest(head, base_manifest=base, today=date(2026, 7, 16))
    assert allowed["status"] == "valid"
    assert {item["exception_id"] for item in allowed["diagnostics"]} == {"reviewed-scope-change"}


def test_exception_is_exactly_scoped_and_cannot_be_future_reviewed():
    current = manifest()
    current["modules"][0]["triggers"][0]["paths"] = ["modules/**"]
    current["modules"][1]["triggers"][0]["paths"] = ["modules/**"]
    current["exceptions"] = [
        {
            "exception_id": "one-module-only",
            "codes": ["overly_broad_glob"],
            "diagnostic_scopes": ["module:ocr:modules/**"],
            "owner": "ocr-owner",
            "reason": "Synthetic exact-scope test.",
            "expires_on": "2026-07-31",
            "reviewed_by": "platform-owner",
            "reviewed_at": "2026-07-16T12:00:00-04:00",
            "review_ref": "review:exact-scope",
        }
    ]
    result = validate_manifest(current, today=date(2026, 7, 16))
    assert result["status"] == "invalid"
    assert sum(item["code"] == "overly_broad_glob" and item["severity"] == "warning" for item in result["diagnostics"]) == 1
    assert sum(item["code"] == "overly_broad_glob" and item["severity"] == "error" for item in result["diagnostics"]) == 1

    current["exceptions"][0]["reviewed_at"] = "2099-07-16T12:00:00-04:00"
    future = validate_manifest(current, today=date(2026, 7, 16))
    assert "invalid_exception" in error_codes(future)


def test_revision_suite_events_workflow_identity_and_generated_lineage_fail_closed():
    revision = manifest()
    revision["capability_revision"] = "9.9.9"
    assert "capability_revision" in error_codes(validate_manifest(revision, today=date(2026, 7, 16)))

    suite_event = manifest()
    suite_event["suites"][1]["events"] = ["schedule"]
    selected = evaluate_changes(suite_event, ["modules/ocr/src/reader.py"])
    assert "ocr" not in selected["selected_suites"]

    duplicate_workflow = manifest()
    duplicate_workflow["workflows"][1]["provider_path"] = duplicate_workflow["workflows"][0]["provider_path"]
    assert "workflow_provider_path_identity" in error_codes(
        validate_manifest(duplicate_workflow, today=date(2026, 7, 16))
    )

    lineage = manifest()
    lineage["generated_artifacts"][0]["authoritative_inputs"] = ["modules/ocr/inputs/**"]
    assert "invalid_generated_lineage" in error_codes(validate_manifest(lineage, today=date(2026, 7, 16)))


def test_scope_digest_includes_trigger_relevant_repository_metadata():
    base = manifest()
    changed = deepcopy(base)
    changed["repository"]["default_branch"] = "develop"
    assert scope_digest(base) != scope_digest(changed)


def test_dad_rust_selection_is_enforced_by_fail_closed_selector_adapter():
    dad_manifest = load_manifest(ROOT / ".ci" / "module-boundaries.yaml")
    selected = evaluate_changes(dad_manifest, ["tools/dad_scan_core/src/lib.rs"])
    assert selected["selected_suites"] == ["ci-contract", "rust-scan"]

    repository_contract = evaluate_changes(dad_manifest, [".gitattributes"])
    assert repository_contract["status"] == "ok"
    assert repository_contract["selected_suites"] == [
        "ci-contract",
        "governance",
        "python-control-plane",
    ]
    assert validate_github_workflows(ROOT, dad_manifest) == []

    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    assert 'git cat-file -e "${base_commit}^{commit}"' in workflow
    assert "git show" in workflow
    assert "|| true" not in workflow
    assert "needs: [selector, python, governance, rust]" in workflow


def test_provider_contract_digests_reject_condition_body_and_branch_drift(tmp_path: Path):
    workflow_root = tmp_path / ".github" / "workflows"
    copytree(ROOT / ".github" / "workflows", workflow_root)
    current = load_manifest(ROOT / ".ci" / "module-boundaries.yaml")
    validate_path = workflow_root / "validate.yml"
    original = validate_path.read_text(encoding="utf-8")

    validate_path.write_text(
        original.replace("needs.selector.outputs.run_rust == 'true'", "false", 1),
        encoding="utf-8",
    )
    condition_codes = {item["code"] for item in validate_github_workflows(tmp_path, current)}
    assert {"workflow_contract_digest_drift", "job_contract_digest_drift"}.issubset(condition_codes)

    validate_path.write_text(
        original.replace("python -m pytest", "echo tests-disabled", 1),
        encoding="utf-8",
    )
    body_codes = {item["code"] for item in validate_github_workflows(tmp_path, current)}
    assert {"workflow_contract_digest_drift", "job_contract_digest_drift"}.issubset(body_codes)

    validate_path.write_text(original.replace("branches: [main]", "branches: [develop]", 1), encoding="utf-8")
    branch_codes = {item["code"] for item in validate_github_workflows(tmp_path, current)}
    assert {"workflow_contract_digest_drift", "push_default_branch_drift"}.issubset(branch_codes)


def test_metadata_only_audit_never_claims_downstream_compliance(tmp_path: Path):
    audit = tmp_path / "processed" / "enrollment"
    audit.mkdir(parents=True)
    (audit / "audit.jsonl").write_text(
        '{"repo_id":"dad","status":"applied"}\n'
        '{"repo_id":"lawfirm-os-orchestrator","status":"updated"}\n',
        encoding="utf-8",
    )
    result = build_metadata_only_adoption_audit(tmp_path)
    assert result["repo_count"] == 2
    assert result["workflow_contents_read"] == 0
    assert result["source_mutations"] == 0
    assert {item["manifest_status"] for item in result["findings"]} == {"not_evidenced"}
    lawfirm = next(item for item in result["findings"] if item["repo_id"] == "lawfirm-os-orchestrator")
    assert lawfirm["recommended_patch"] == "multi-repo-law-firm-os"
