from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.config import LocalSource
from digital_asset_directory.lesson_automation_coverage import build_lesson_automation_coverage
from digital_asset_directory.models import AssetRecord
from digital_asset_directory.repo_learning_scope import (
    build_repo_learning_loop_install_scope,
    write_repo_learning_loop_install_scope_outputs,
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
        description="synthetic repo learning scope asset",
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


def scope_assets() -> list[AssetRecord]:
    return [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:agents", "git-projects/repo-a/AGENTS.md"),
        make_asset("dad:asset:front", "git-projects/repo-a/AI_FRONT_DOOR.md"),
        make_asset("dad:asset:toc", "git-projects/repo-a/AI_TABLE_OF_CONTENTS.md"),
        make_asset("dad:asset:test", "git-projects/repo-a/tests/test_item.py", asset_type="test"),
        make_repo("dad:asset:repo-b", "git-projects/repo-b", ["AGENTS.md"]),
        make_asset(
            "dad:asset:learning-readme",
            "git-projects/repo-b/.digital-asset-directory/learning/README.md",
        ),
        make_repo("dad:asset:repo-c", "git-projects/repo-c"),
        make_asset(
            "dad:asset:learning-events",
            "git-projects/repo-c/.digital-asset-directory/learning/events.jsonl",
        ),
        make_repo("dad:asset:noise", "git-projects/.pytest-tmp-root/pytest-1/repo-copy"),
        make_asset(
            "dad:asset:noise-agents",
            "git-projects/.pytest-tmp-root/pytest-1/repo-copy/AGENTS.md",
            repository_root="git-projects/.pytest-tmp-root/pytest-1/repo-copy",
        ),
    ]


def test_repo_learning_loop_scope_ranks_missing_learning_surfaces_without_mutation():
    result = build_repo_learning_loop_install_scope(
        Path("."),
        scope_assets(),
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert result["review_status"] == "generated_candidate"
    assert result["summary"]["source_repos_mutated"] == 0
    assert result["summary"]["hooks_installed"] == 0
    assert result["summary"]["content_files_read"] == 0
    assert result["summary"]["skipped_noise_repo_count"] == 1
    assert ".digital-asset-directory/learning/events.jsonl" in result["target_write_paths"]
    by_repo = {candidate["repo_key"]: candidate for candidate in result["repo_candidates"]}
    assert by_repo["git-projects/repo-a"]["install_status"] == "missing_learning_loop_surface"
    assert by_repo["git-projects/repo-b"]["install_status"] == "partial_learning_loop_surface"
    assert by_repo["git-projects/repo-c"]["install_status"] == "already_has_event_log"
    assert by_repo["git-projects/repo-a"]["priority_score"] > by_repo["git-projects/repo-c"]["priority_score"]
    assert "agent install-learning-loop" in by_repo["git-projects/repo-a"]["proposed_install_command"]


def test_repo_learning_loop_scope_writer_and_coverage_status(tmp_path: Path):
    result = write_repo_learning_loop_install_scope_outputs(
        tmp_path,
        scope_assets(),
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        limit=10,
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"scope_markdown", "scope_json", "approval_prompt"}
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["scope_json"]).read_text(encoding="utf-8"))
    assert payload["summary"]["source_repos_mutated"] == 0
    assert "downstream repo writes" in payload["intentionally_not_done"]

    coverage = build_lesson_automation_coverage(
        tmp_path,
        [
            make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
            make_asset("dad:asset:agents", "git-projects/repo-a/AGENTS.md"),
        ],
        [local_source(max_file_bytes=0)],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    by_family = {item["signal_family_id"]: item for item in coverage["signal_families"]}
    assert by_family["repo_learning_events"]["current_status"] == "installation_scope_ready"
    assert (
        by_family["repo_learning_events"]["evidence"][
            "repo_learning_loop_install_scope_present"
        ]
        is True
    )
