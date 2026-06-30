from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.config import LocalSource
from digital_asset_directory.lesson_automation_coverage import build_lesson_automation_coverage
from digital_asset_directory.models import AssetRecord
from digital_asset_directory.priority_content_scope import (
    build_priority_content_extract_scope,
    run_priority_content_extract,
    write_priority_content_extract_outputs,
    write_priority_content_extract_scope_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(
    asset_id: str,
    path: str,
    *,
    asset_type: str = "document",
    title: str | None = None,
    entrypoints: list[str] | None = None,
    repository_root: str | None = None,
    value_score: float = 60,
) -> AssetRecord:
    root = repository_root or "/".join(path.split("/")[:2])
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=None,
        source_kind="local",
        asset_type=asset_type,
        title=title or Path(path).stem,
        description="synthetic priority content scope asset",
        logical_path=path,
        content_hash=f"hash-{asset_id}",
        metadata_fingerprint=f"metadata-{asset_id}",
        content_sha256=f"sha-{asset_id}",
        size_bytes=100,
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        tags=[],
        capabilities=[],
        needs=[],
        outcomes=[],
        entrypoints=entrypoints or [],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=value_score,
        value_components={},
        confidence="medium",
        metadata={"repository_root": root, "instance_class": "source"},
    )


def make_repo(asset_id: str, path: str, entrypoints: list[str] | None = None) -> AssetRecord:
    return make_asset(
        asset_id,
        path,
        asset_type="repository",
        title=Path(path).name,
        entrypoints=entrypoints,
        repository_root=path,
    )


def local_source(max_file_bytes: int = 0) -> LocalSource:
    return LocalSource(
        id="git-projects",
        path=Path("C:/Git Projects"),
        path_alias="git-projects",
        enabled=True,
        max_file_bytes=max_file_bytes,
    )


def local_source_at(path: Path, max_file_bytes: int = 0) -> LocalSource:
    return LocalSource(
        id="git-projects",
        path=path,
        path_alias="git-projects",
        enabled=True,
        max_file_bytes=max_file_bytes,
    )


def scope_assets() -> list[AssetRecord]:
    return [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:agents", "git-projects/repo-a/AGENTS.md", value_score=80),
        make_asset("dad:asset:front", "git-projects/repo-a/AI_FRONT_DOOR.md", value_score=78),
        make_asset("dad:asset:schema", "git-projects/repo-a/schemas/item.schema.json", asset_type="schema"),
        make_asset("dad:asset:test", "git-projects/repo-a/tests/test_item.py", asset_type="test"),
        make_asset("dad:asset:workflow", "git-projects/repo-a/docs/DATA_FLOW.md"),
        make_asset("dad:asset:ordinary", "git-projects/repo-a/src/app.py", asset_type="code"),
        make_repo("dad:asset:noise", "git-projects/.pytest-tmp-root/pytest-1/repo-copy"),
        make_asset(
            "dad:asset:noise-agents",
            "git-projects/.pytest-tmp-root/pytest-1/repo-copy/AGENTS.md",
            repository_root="git-projects/.pytest-tmp-root/pytest-1/repo-copy",
        ),
    ]


def test_priority_content_scope_lists_candidate_paths_without_reading_content():
    result = build_priority_content_extract_scope(
        Path("."),
        scope_assets(),
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        per_repo_limit=10,
        generated_at=TIMESTAMP,
    )

    assert result["review_status"] == "generated_candidate"
    assert result["summary"]["content_files_read"] == 0
    assert result["summary"]["source_repos_mutated"] == 0
    assert result["summary"]["skipped_noise_repo_count"] == 1
    assert sum(result["summary"]["category_counts"].values()) == result["summary"]["candidate_count"]
    scoped_paths = {
        candidate["relative_path"]
        for repo in result["repo_scopes"]
        for candidate in repo["candidates"]
    }
    assert "agents.md" in scoped_paths
    assert "ai_front_door.md" in scoped_paths
    assert "schemas/item.schema.json" in scoped_paths
    assert "tests/test_item.py" in scoped_paths
    assert "src/app.py" not in scoped_paths


def test_priority_content_scope_uses_logical_path_prefix_when_metadata_root_is_short():
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a"),
        make_asset(
            "dad:asset:short-root",
            "git-projects/repo-a/AGENTS.md",
            repository_root="repo-a",
        ),
    ]

    result = build_priority_content_extract_scope(
        Path("."),
        assets,
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        per_repo_limit=10,
        generated_at=TIMESTAMP,
    )

    assert result["summary"]["candidate_count"] == 1
    assert result["repo_scopes"][0]["repo_key"] == "git-projects/repo-a"
    assert result["repo_scopes"][0]["candidates"][0]["relative_path"] == "agents.md"


def test_priority_content_scope_writer_outputs_generated_scope_and_prompt(tmp_path: Path):
    result = write_priority_content_extract_scope_outputs(
        tmp_path,
        scope_assets(),
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        limit=10,
        per_repo_limit=10,
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"scope_markdown", "scope_json", "approval_prompt"}
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["scope_json"]).read_text(encoding="utf-8"))
    assert payload["summary"]["content_files_read"] == 0
    assert "source file content reads" in payload["intentionally_not_done"]
    prompt = Path(outputs["approval_prompt"]).read_text(encoding="utf-8")
    assert "Do not read source file contents" in prompt


def test_lesson_automation_coverage_marks_priority_content_as_scoped(tmp_path: Path):
    write_priority_content_extract_scope_outputs(
        tmp_path,
        scope_assets(),
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        limit=10,
        per_repo_limit=10,
        generated_at=TIMESTAMP,
    )

    coverage = build_lesson_automation_coverage(
        tmp_path,
        scope_assets(),
        [local_source(max_file_bytes=0)],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    by_family = {item["signal_family_id"]: item for item in coverage["signal_families"]}

    assert by_family["priority_content_extracts"]["current_status"] == "scoped_not_extracted"
    assert by_family["priority_content_extracts"]["evidence"]["priority_content_scope_present"] is True


def test_priority_content_extract_requires_approval_and_allowlists():
    scope = build_priority_content_extract_scope(
        Path("."),
        scope_assets(),
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        per_repo_limit=10,
        generated_at=TIMESTAMP,
    )

    with pytest.raises(ValueError, match="approval-id"):
        run_priority_content_extract(
            scope,
            [local_source(max_file_bytes=0)],
            approval_id="",
            repo_keys=["git-projects/repo-a"],
            category_ids=["ai_navigation"],
            scan_id=SCAN_ID,
            generated_at=TIMESTAMP,
        )
    with pytest.raises(ValueError, match="repo-key"):
        run_priority_content_extract(
            scope,
            [local_source(max_file_bytes=0)],
            approval_id="approval:test",
            repo_keys=[],
            category_ids=["ai_navigation"],
            scan_id=SCAN_ID,
            generated_at=TIMESTAMP,
        )
    with pytest.raises(ValueError, match="category"):
        run_priority_content_extract(
            scope,
            [local_source(max_file_bytes=0)],
            approval_id="approval:test",
            repo_keys=["git-projects/repo-a"],
            category_ids=[],
            scan_id=SCAN_ID,
            generated_at=TIMESTAMP,
        )


def test_priority_content_extract_reads_only_approved_paths_with_redaction(tmp_path: Path):
    source_root = tmp_path / "source"
    repo = source_root / "repo-a"
    (repo / "schemas").mkdir(parents=True)
    (repo / "AGENTS.md").write_text(
        "Read first. Run preflight and postflight. API_KEY=SECRET_VALUE_12345\n",
        encoding="utf-8",
    )
    (repo / "schemas" / "item.schema.json").write_text(
        '{"title": "Item", "required": ["name"], "api_key": "SECRET_VALUE_12345"}',
        encoding="utf-8",
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_item.py").write_text("def test_item(): assert True\n", encoding="utf-8")
    local = local_source_at(source_root)
    scope_result = write_priority_content_extract_scope_outputs(
        tmp_path,
        scope_assets(),
        [local],
        scan_id=SCAN_ID,
        limit=10,
        per_repo_limit=10,
        generated_at=TIMESTAMP,
    )

    result = write_priority_content_extract_outputs(
        tmp_path,
        [local],
        scope_file=Path(scope_result["outputs"]["scope_json"]),
        approval_id="approval:lowell:test",
        repo_keys=["git-projects/repo-a"],
        category_ids=["ai_navigation", "schemas_contracts"],
        scan_id=SCAN_ID,
        max_bytes_per_file=80,
        max_excerpt_chars=200,
        limit=10,
        generated_at=TIMESTAMP,
    )

    assert result["summary"]["observation_count"] == 2
    assert result["summary"]["source_repos_mutated"] == 0
    assert result["summary"]["redaction_count"] >= 1
    observations_path = Path(result["outputs"]["observations"])
    observations = [
        json.loads(line) for line in observations_path.read_text(encoding="utf-8").splitlines()
    ]
    assert {item["category_id"] for item in observations} == {"ai_navigation", "schemas_contracts"}
    assert all("SECRET_VALUE_12345" not in item["content_excerpt"] for item in observations)
    assert any("preflight" in item["content_token_sample"] for item in observations)
    assert all(item["review_status"] == "generated_candidate" for item in observations)


def test_lesson_automation_coverage_marks_priority_content_as_extracted(tmp_path: Path):
    source_root = tmp_path / "source"
    repo = source_root / "repo-a"
    repo.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("Read first. Run preflight.\n", encoding="utf-8")
    local = local_source_at(source_root)
    scope_result = write_priority_content_extract_scope_outputs(
        tmp_path,
        scope_assets(),
        [local],
        scan_id=SCAN_ID,
        limit=10,
        per_repo_limit=10,
        generated_at=TIMESTAMP,
    )
    write_priority_content_extract_outputs(
        tmp_path,
        [local],
        scope_file=Path(scope_result["outputs"]["scope_json"]),
        approval_id="approval:lowell:test",
        repo_keys=["git-projects/repo-a"],
        category_ids=["ai_navigation"],
        scan_id=SCAN_ID,
        max_bytes_per_file=80,
        max_excerpt_chars=200,
        limit=10,
        generated_at=TIMESTAMP,
    )

    coverage = build_lesson_automation_coverage(
        tmp_path,
        scope_assets(),
        [local],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    by_family = {item["signal_family_id"]: item for item in coverage["signal_families"]}

    assert (
        by_family["priority_content_extracts"]["current_status"]
        == "extracted_candidate_observations_present"
    )
    assert (
        by_family["priority_content_extracts"]["evidence"][
            "priority_content_observations_present"
        ]
        is True
    )
