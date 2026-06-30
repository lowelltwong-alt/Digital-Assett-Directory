from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.ci_release_scope import (
    build_ci_release_artifact_scope,
    write_ci_release_artifact_scope_outputs,
)
from digital_asset_directory.config import LocalSource
from digital_asset_directory.lesson_automation_coverage import build_lesson_automation_coverage
from digital_asset_directory.models import AssetRecord

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(
    asset_id: str,
    path: str,
    *,
    asset_type: str = "document",
    title: str | None = None,
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
        description="synthetic CI release scope asset",
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
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=value_score,
        value_components={},
        confidence="medium",
        metadata={"repository_root": root, "instance_class": "source"},
    )


def make_repo(asset_id: str, path: str) -> AssetRecord:
    return make_asset(
        asset_id,
        path,
        asset_type="repository",
        title=Path(path).name,
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


def scope_assets() -> list[AssetRecord]:
    return [
        make_repo("dad:asset:repo-a", "git-projects/repo-a"),
        make_asset("dad:asset:ci", "git-projects/repo-a/.github/workflows/validate.yml", asset_type="workflow"),
        make_asset("dad:asset:changelog", "git-projects/repo-a/CHANGELOG.md"),
        make_asset("dad:asset:verification", "git-projects/repo-a/VERIFICATION_REPORT.md"),
        make_asset("dad:asset:lock", "git-projects/repo-a/package-lock.json", asset_type="config"),
        make_asset("dad:asset:code", "git-projects/repo-a/src/app.py", asset_type="code"),
        make_repo("dad:asset:noise-repo", "git-projects/.pytest-tmp-root/pytest-1/repo-copy"),
        make_asset(
            "dad:asset:noise-ci",
            "git-projects/.pytest-tmp-root/pytest-1/repo-copy/.github/workflows/validate.yml",
            asset_type="workflow",
            repository_root="git-projects/.pytest-tmp-root/pytest-1/repo-copy",
        ),
    ]


def test_ci_release_scope_lists_artifacts_without_reading_content():
    result = build_ci_release_artifact_scope(
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
    assert result["summary"]["github_calls"] == 0
    assert result["summary"]["ci_service_calls"] == 0
    assert result["summary"]["skipped_noise_repo_count"] == 1
    paths = {
        candidate["relative_path"]
        for scope in result["repo_scopes"]
        for candidate in scope["candidates"]
    }
    assert ".github/workflows/validate.yml" in paths
    assert "changelog.md" in paths
    assert "verification_report.md" in paths
    assert "package-lock.json" in paths
    assert "src/app.py" not in paths
    assert result["danger_if_misapplied"]


def test_ci_release_scope_writer_and_coverage_status(tmp_path: Path):
    result = write_ci_release_artifact_scope_outputs(
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
    assert "GitHub, CI, or package registry calls" in payload["intentionally_not_done"]

    coverage = build_lesson_automation_coverage(
        tmp_path,
        scope_assets(),
        [local_source(max_file_bytes=0)],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    by_family = {item["signal_family_id"]: item for item in coverage["signal_families"]}
    assert by_family["ci_and_release_artifacts"]["current_status"] == "scoped_not_extracted"
    assert (
        by_family["ci_and_release_artifacts"]["evidence"]["ci_release_artifact_scope_present"]
        is True
    )
