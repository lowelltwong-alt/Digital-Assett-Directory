from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.config import LocalSource
from digital_asset_directory.governance_map_scope import (
    build_governance_map_adoption_scope,
    write_governance_map_adoption_scope_outputs,
)
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
    entrypoints: list[str] | None = None,
    repository_root: str | None = None,
) -> AssetRecord:
    root = repository_root or "/".join(path.split("/")[:3])
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=None,
        source_kind="local",
        asset_type=asset_type,
        title=title or Path(path).stem,
        description="synthetic governance map scope asset",
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
        make_repo(
            "dad:asset:control-repo",
            "git-projects/family/control-plane",
            ["AGENTS.md", "AI_FRONT_DOOR.md"],
        ),
        make_asset("dad:asset:control-agents", "git-projects/family/control-plane/AGENTS.md"),
        make_asset("dad:asset:control-front", "git-projects/family/control-plane/AI_FRONT_DOOR.md"),
        make_asset("dad:asset:control-toc", "git-projects/family/control-plane/AI_TABLE_OF_CONTENTS.md"),
        make_asset("dad:asset:policy", "git-projects/family/control-plane/docs/GOVERNANCE.md"),
        make_repo("dad:asset:child-repo", "git-projects/family/child"),
        make_asset(
            "dad:asset:child-mirror",
            "git-projects/family/child/.ai/control/governance_dependency_map_mirror.yaml",
        ),
        make_asset(
            "dad:asset:child-test",
            "git-projects/family/child/tests/test_governance_dependency_map_mirror.py",
            asset_type="test",
        ),
        make_repo("dad:asset:single-repo", "git-projects/other/single"),
        make_asset("dad:asset:single-readme", "git-projects/other/single/README.md"),
        make_repo("dad:asset:noise", "git-projects/.pytest-tmp-root/pytest-1/repo-copy"),
        make_asset(
            "dad:asset:noise-map",
            "git-projects/.pytest-tmp-root/pytest-1/repo-copy/governance/GOVERNANCE_DEPENDENCY_MAP.yaml",
            repository_root="git-projects/.pytest-tmp-root/pytest-1/repo-copy",
        ),
    ]


def test_governance_map_scope_detects_family_candidates_without_mutation():
    result = build_governance_map_adoption_scope(
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
    assert result["summary"]["filesystem_recursions"] == 0
    assert result["summary"]["github_calls"] == 0
    assert result["summary"]["model_calls"] == 0
    assert result["summary"]["skipped_noise_repo_count"] == 1

    by_repo = {candidate["repo_key"]: candidate for candidate in result["repo_candidates"]}
    control = by_repo["git-projects/family/control-plane"]
    child = by_repo["git-projects/family/child"]
    assert control["adoption_status"] == "governance_surface_without_dependency_map"
    assert control["proposed_role"] == "repo_family_map_candidate"
    assert child["adoption_status"] == "child_mirror_with_validation_observed"
    assert child["surface_flags"]["has_child_mirror"] is True
    assert child["surface_flags"]["has_governance_test"] is True
    assert control["priority_score"] > by_repo["git-projects/other/single"]["priority_score"]
    assert "governance_validator" in control["missing_surface_ids"]
    assert result["target_template_paths"]
    assert "downstream repo writes" in result["intentionally_not_done"]


def test_governance_map_scope_writer_and_coverage_status(tmp_path: Path):
    result = write_governance_map_adoption_scope_outputs(
        tmp_path,
        [
            make_repo("dad:asset:repo-a", "git-projects/family/repo-a"),
            make_asset("dad:asset:agents", "git-projects/family/repo-a/AGENTS.md"),
        ],
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
    assert "governance map or mirror installation" in payload["intentionally_not_done"]

    coverage = build_lesson_automation_coverage(
        tmp_path,
        [
            make_repo("dad:asset:repo-a", "git-projects/family/repo-a"),
            make_asset("dad:asset:agents", "git-projects/family/repo-a/AGENTS.md"),
        ],
        [local_source(max_file_bytes=0)],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    by_family = {item["signal_family_id"]: item for item in coverage["signal_families"]}
    assert by_family["governance_map_adoption"]["current_status"] == "adoption_scope_ready"
    assert (
        by_family["governance_map_adoption"]["evidence"][
            "governance_map_adoption_scope_present"
        ]
        is True
    )


def test_existing_governance_map_and_mirror_are_detected():
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/family/repo-a"),
        make_asset(
            "dad:asset:map",
            "git-projects/family/repo-a/governance/GOVERNANCE_DEPENDENCY_MAP.yaml",
        ),
        make_asset(
            "dad:asset:mirror",
            "git-projects/family/repo-a/.ai/control/governance_dependency_map_mirror.yaml",
        ),
        make_asset(
            "dad:asset:validator",
            "git-projects/family/repo-a/scripts/validate_governance_dependency_map.py",
            asset_type="code",
        ),
    ]

    result = build_governance_map_adoption_scope(
        Path("."),
        assets,
        [local_source(max_file_bytes=0)],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    candidate = result["repo_candidates"][0]
    assert candidate["adoption_status"] == "map_and_mirror_with_validation_observed"
    assert candidate["proposed_role"] == "upstream_map_maintenance_candidate"
    assert candidate["surface_flags"]["has_upstream_map"] is True
    assert candidate["surface_flags"]["has_child_mirror"] is True
    assert candidate["surface_flags"]["has_governance_validator"] is True
