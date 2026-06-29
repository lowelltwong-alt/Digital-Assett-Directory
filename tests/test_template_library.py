from __future__ import annotations

import json
from pathlib import Path
from shutil import copytree

import pytest

from digital_asset_directory.template_library import (
    build_template_library_report,
    validate_template_registry,
    write_template_library_report,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def copy_template_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    copytree(ROOT / "registry", target / "registry")
    copytree(ROOT / "schemas", target / "schemas")
    copytree(ROOT / "templates", target / "templates")
    copytree(ROOT / "docs", target / "docs")
    (target / "AI_FRONT_DOOR.md").write_text("front door", encoding="utf-8")
    (target / "AI_TABLE_OF_CONTENTS.md").write_text("toc", encoding="utf-8")
    (target / "AGENTS.md").write_text("agents", encoding="utf-8")
    (target / "scripts").mkdir()
    for name in ("new_repo.ps1", "enforce_postflight.py"):
        (target / "scripts" / name).write_text("echo test", encoding="utf-8")
    (target / "src" / "digital_asset_directory").mkdir(parents=True)
    (target / "src" / "digital_asset_directory" / "governance.py").write_text(
        "# governance", encoding="utf-8"
    )
    (target / "tests").mkdir()
    (target / "tests" / "test_ai_navigation.py").write_text("# test", encoding="utf-8")
    (target / "tests" / "test_governance.py").write_text("# test", encoding="utf-8")
    return target


def test_template_registry_is_valid_and_reverse_dependencies_match():
    result = validate_template_registry(ROOT)

    assert result["valid"] is True
    assert result["template_count"] >= 8
    assert result["errors"] == []
    assert "template:downstream-agents-managed-block" in result["reverse_dependencies"]
    assert result["reverse_dependencies"]["template:downstream-agents-managed-block"] == [
        "template:downstream-pre-push-hook"
    ]


def test_template_registry_rejects_reverse_dependency_mismatch(tmp_path: Path):
    repo = copy_template_fixture(tmp_path)
    registry_path = repo / "registry" / "template-registry.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    for record in payload["templates"]:
        if record["template_id"] == "template:software-repo-checklist-tree":
            record["dependent_template_ids"] = []
    registry_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_template_registry(repo)

    assert result["valid"] is False
    assert any("reverse dependency mismatch" in error for error in result["errors"])


def test_template_library_report_flags_due_dates_deterministically():
    result = build_template_library_report(ROOT, generated_at="2027-01-01T00:00:00+00:00")

    assert result["due_for_review_count"] == result["template_count"]
    assert result["validation"]["valid"] is True
    assert "Template IDs must be unique." in result["deterministic_enforcement"]


def test_template_library_writer_outputs_generated_reports(tmp_path: Path):
    repo = copy_template_fixture(tmp_path)

    result = write_template_library_report(repo, generated_at="2026-06-29T00:00:00+00:00")

    report = Path(result["report"])
    payload = Path(result["payload"])
    assert result["valid"] is True
    assert report.exists()
    assert payload.exists()
    assert report.is_relative_to(repo / "processed")
    assert payload.is_relative_to(repo / "processed")
    text = report.read_text(encoding="utf-8")
    assert "Dependency Graph" in text
    assert "Automation Boundary" in text
