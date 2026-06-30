from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.models import AssetRecord
from digital_asset_directory.repo_completion import (
    build_repo_completion_dashboard,
    build_repo_completion_wave_plan,
    write_repo_completion_dashboard_outputs,
    write_repo_completion_wave_plan_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def make_asset(
    asset_id: str,
    logical_path: str,
    *,
    asset_type: str = "document",
    repository_root: str | None = None,
    entrypoints: list[str] | None = None,
) -> AssetRecord:
    root = repository_root or "/".join(logical_path.split("/")[:2])
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=None,
        source_kind="local",
        asset_type=asset_type,
        title=Path(logical_path).name,
        description="synthetic repo completion asset",
        logical_path=logical_path,
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
        value_score=50,
        value_components={},
        confidence="medium",
        metadata={"repository_root": root, "instance_class": "source"},
    )


def make_repo(asset_id: str, repo_key: str, entrypoints: list[str] | None = None) -> AssetRecord:
    return make_asset(
        asset_id,
        repo_key,
        asset_type="repository",
        repository_root=repo_key,
        entrypoints=entrypoints,
    )


def seed_generated_outputs(repo_root: Path) -> None:
    reports = repo_root / "processed" / "reports"
    write_json(
        reports / "priority_content_extract_scope.json",
        {
            "repo_scopes": [
                {"repo_key": "git-projects/repo-a", "candidate_count": 3},
            ],
        },
    )
    write_json(
        reports / "repo_learning_loop_install_scope.json",
        {
            "repo_candidates": [
                {
                    "repo_key": "git-projects/repo-a",
                    "install_status": "missing_learning_loop_surface",
                },
            ],
        },
    )
    write_json(
        reports / "governance_map_adoption_scope.json",
        {
            "repo_candidates": [
                {
                    "repo_key": "git-projects/repo-a",
                    "adoption_status": "missing_governance_dependency_surface",
                },
            ],
        },
    )
    write_json(
        reports / "ci_release_artifact_scope.json",
        {"repo_scopes": [{"repo_key": "git-projects/repo-b", "candidate_count": 1}]},
    )
    write_json(reports / "lesson_automation_approval_packet.json", {"summary": {}})
    write_json(reports / "lesson_automation_execution_plan.json", {"summary": {}})
    write_jsonl(
        repo_root / "processed" / "learning" / "lesson_automation_action_decisions.jsonl",
        [
            {
                "decision": "pending",
                "allow_content_read": False,
                "allow_source_mutation": False,
                "allow_external_api": False,
            }
        ],
    )


def test_repo_completion_dashboard_reports_repo_blockers(tmp_path: Path):
    seed_generated_outputs(tmp_path)
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:repo-a-agent", "git-projects/repo-a/AGENTS.md"),
        make_asset("dad:asset:repo-a-front", "git-projects/repo-a/AI_FRONT_DOOR.md"),
        make_repo("dad:asset:repo-b", "git-projects/repo-b", ["AGENTS.md"]),
        make_asset("dad:asset:repo-b-agent", "git-projects/repo-b/AGENTS.md"),
        make_asset("dad:asset:repo-b-front", "git-projects/repo-b/AI_FRONT_DOOR.md"),
        make_asset("dad:asset:repo-b-toc", "git-projects/repo-b/AI_TABLE_OF_CONTENTS.md"),
        make_asset(
            "dad:asset:repo-b-learn-readme",
            "git-projects/repo-b/.digital-asset-directory/learning/README.md",
        ),
        make_asset(
            "dad:asset:repo-b-learn-tags",
            "git-projects/repo-b/.digital-asset-directory/learning/context-tags.yaml",
        ),
        make_asset(
            "dad:asset:repo-b-learn-events",
            "git-projects/repo-b/.digital-asset-directory/learning/events.jsonl",
        ),
        make_asset(
            "dad:asset:repo-b-gov",
            "git-projects/repo-b/governance/GOVERNANCE_DEPENDENCY_MAP.yaml",
        ),
        make_asset("dad:asset:repo-b-test", "git-projects/repo-b/tests/test_repo.py"),
    ]

    result = build_repo_completion_dashboard(
        tmp_path,
        assets,
        generated_at=TIMESTAMP,
    )

    assert result["review_status"] == "generated_candidate"
    assert result["status_methodology"]["score_used"] is False
    assert result["summary"]["source_repos_mutated"] == 0
    assert result["summary"]["content_files_read"] == 0
    assert result["summary"]["github_calls"] == 0
    by_repo = {record["repo_key"]: record for record in result["repo_records"]}
    assert by_repo["git-projects/repo-a"]["completion_state"] == "blocked_by_content_read_gate"
    assert "content_extract_human_gate" in by_repo["git-projects/repo-a"]["blockers"]
    assert "repo_learning_loop_missing" in by_repo["git-projects/repo-a"]["blockers"]
    assert (
        by_repo["git-projects/repo-b"]["completion_state"]
        == "metadata_completion_ready_for_human_review"
    )
    assert by_repo["git-projects/repo-b"]["blockers"] == []


def test_repo_completion_dashboard_writer_stays_under_processed_reports(tmp_path: Path):
    seed_generated_outputs(tmp_path)
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:repo-a-agent", "git-projects/repo-a/AGENTS.md"),
    ]

    result = write_repo_completion_dashboard_outputs(
        tmp_path,
        assets,
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"dashboard_markdown", "dashboard_json"}
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["dashboard_json"]).read_text(encoding="utf-8"))
    assert payload["summary"]["source_repos_mutated"] == 0
    assert payload["summary"]["content_files_read"] == 0
    assert "source repo mutation" in payload["intentionally_not_done"]


def test_repo_completion_wave_plan_orders_blockers_without_executing(tmp_path: Path):
    seed_generated_outputs(tmp_path)
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:repo-a-agent", "git-projects/repo-a/AGENTS.md"),
        make_asset("dad:asset:repo-a-front", "git-projects/repo-a/AI_FRONT_DOOR.md"),
        make_repo("dad:asset:repo-b", "git-projects/repo-b", ["AGENTS.md"]),
        make_asset("dad:asset:repo-b-agent", "git-projects/repo-b/AGENTS.md"),
        make_asset("dad:asset:repo-b-front", "git-projects/repo-b/AI_FRONT_DOOR.md"),
        make_asset("dad:asset:repo-b-toc", "git-projects/repo-b/AI_TABLE_OF_CONTENTS.md"),
        make_asset(
            "dad:asset:repo-b-learn-readme",
            "git-projects/repo-b/.digital-asset-directory/learning/README.md",
        ),
        make_asset(
            "dad:asset:repo-b-learn-tags",
            "git-projects/repo-b/.digital-asset-directory/learning/context-tags.yaml",
        ),
        make_asset(
            "dad:asset:repo-b-learn-events",
            "git-projects/repo-b/.digital-asset-directory/learning/events.jsonl",
        ),
        make_asset(
            "dad:asset:repo-b-gov",
            "git-projects/repo-b/governance/GOVERNANCE_DEPENDENCY_MAP.yaml",
        ),
        make_asset("dad:asset:repo-b-test", "git-projects/repo-b/tests/test_repo.py"),
    ]

    result = build_repo_completion_wave_plan(
        tmp_path,
        assets,
        generated_at=TIMESTAMP,
        per_wave_repo_limit=10,
    )

    assert result["review_status"] == "generated_candidate"
    assert result["status_methodology"]["score_used"] is False
    assert result["summary"]["source_repos_mutated"] == 0
    assert result["summary"]["content_files_read"] == 0
    assert result["summary"]["github_calls"] == 0
    assert [wave["wave_id"] for wave in result["waves"][:3]] == [
        "content_read_approval_wave",
        "lesson_candidate_synthesis_wave",
        "repo_learning_loop_selection_wave",
    ]
    content_wave = result["waves"][0]
    assert content_wave["repo_count"] == 1
    assert content_wave["reported_repo_keys"] == ["git-projects/repo-a"]
    assert "approval-packet" in content_wave["generated_next_step"]
    assert content_wave["review_status"] == "generated_candidate"


def test_repo_completion_wave_plan_writer_stays_under_processed_reports(tmp_path: Path):
    seed_generated_outputs(tmp_path)
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", ["AGENTS.md"]),
        make_asset("dad:asset:repo-a-agent", "git-projects/repo-a/AGENTS.md"),
    ]

    result = write_repo_completion_wave_plan_outputs(
        tmp_path,
        assets,
        generated_at=TIMESTAMP,
    )

    outputs = result["outputs"]
    assert set(outputs) == {"wave_markdown", "wave_json"}
    assert all(Path(path).is_relative_to(tmp_path / "processed" / "reports") for path in outputs.values())
    payload = json.loads(Path(outputs["wave_json"]).read_text(encoding="utf-8"))
    assert payload["summary"]["source_repos_mutated"] == 0
    assert payload["summary"]["content_files_read"] == 0
    assert "decision approval" in payload["intentionally_not_done"]
