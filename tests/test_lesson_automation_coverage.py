from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.config import GitHubSource, LocalSource
from digital_asset_directory.lesson_automation_coverage import (
    build_lesson_automation_coverage,
    write_lesson_automation_coverage_outputs,
)
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
    entrypoints: list[str] | None = None,
    repository_root: str | None = None,
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
        description="synthetic lesson automation coverage asset",
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
        value_score=60,
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


def test_coverage_identifies_metadata_only_gaps_and_scan_cycle(tmp_path: Path):
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md", "AI_FRONT_DOOR.md"]),
        make_asset("dad:asset:toc", "git-projects/repo-a/AI_TABLE_OF_CONTENTS.md"),
        make_repo("dad:asset:repo-b", "git-projects/repo-b", ["AGENTS.md"]),
        make_asset(
            "dad:asset:learning-readme",
            "git-projects/repo-b/.digital-asset-directory/learning/README.md",
        ),
        make_asset(
            "dad:asset:learning-events",
            "git-projects/repo-b/.digital-asset-directory/learning/events.jsonl",
        ),
        make_repo(
            "dad:asset:temp",
            "git-projects/.pytest-tmp-root/pytest-1/repo-copy",
            [],
        ),
    ]

    result = build_lesson_automation_coverage(
        tmp_path,
        assets,
        [local_source(max_file_bytes=0)],
        [GitHubSource(id="github", owner="owner", enabled=False)],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert result["review_status"] == "generated_candidate"
    assert result["summary"]["cataloged_repo_count"] == 2
    assert result["summary"]["noise_repo_count_skipped"] == 1
    assert result["summary"]["metadata_only_local_sources"] == ["git-projects"]
    priority_content = {
        item["signal_family_id"]: item for item in result["signal_families"]
    }["priority_content_extracts"]
    assert priority_content["current_status"] == "not_scanned_metadata_only"
    assert "source file contents" in result["scan_cycle_log"]["intentionally_not_checked"]
    assert all("applies_when" in item for item in result["signal_families"])
    assert any(
        "learning_loop_missing" in record["flags"]
        for record in result["repo_records"]
        if record["repo_key"] == "git-projects/repo-a"
    )


def test_coverage_is_deterministic_with_fixed_generated_at():
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:front", "git-projects/repo-a/AI_FRONT_DOOR.md"),
    ]

    left = build_lesson_automation_coverage(
        Path("nonexistent-hub-for-deterministic-test"),
        assets,
        [local_source(max_file_bytes=0)],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    right = build_lesson_automation_coverage(
        Path("nonexistent-hub-for-deterministic-test"),
        assets,
        [local_source(max_file_bytes=0)],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert left == right


def test_writer_creates_generated_reports_only_under_processed(tmp_path: Path):
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:front", "git-projects/repo-a/AI_FRONT_DOOR.md"),
    ]

    result = write_lesson_automation_coverage_outputs(
        tmp_path,
        assets,
        [local_source(max_file_bytes=0)],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {
        "coverage_markdown",
        "coverage_json",
        "scan_cycle_markdown",
        "scan_cycle_json",
    }
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["scan_cycle_json"]).read_text(encoding="utf-8"))
    assert payload["pass_type"] == "no_rescan_catalog_coverage"
    assert "GitHub PR/issue APIs" in payload["intentionally_not_checked"]
