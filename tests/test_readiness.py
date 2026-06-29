from pathlib import Path

import pytest

from digital_asset_directory.config import AppConfig, Settings
from digital_asset_directory.models import AssetRecord
from digital_asset_directory.operational import (
    build_operational_readiness,
    operational_readiness_markdown,
    write_operational_readiness_report,
)
from digital_asset_directory.readiness import (
    phase4_readiness_markdown,
    phase5_readiness_markdown,
    write_downstream_pilot_candidates,
    write_phase45_readiness_reports,
)

pytestmark = pytest.mark.integration


def make_repo_asset(asset_id: str, title: str, logical_path: str) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"rev-{asset_id}",
        source_id="local-test",
        source_kind="local",
        asset_type="repository",
        title=title,
        description="test repository",
        logical_path=logical_path,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        entrypoints=["AGENTS.md", "CLAUDE.md", "README.md"],
        lifecycle_state="active",
        freshness_status="watch",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=75,
        confidence="high",
    )


def test_downstream_pilot_report_excludes_mock_trial_and_installs_no_hooks(tmp_path: Path):
    assets = [
        make_repo_asset("repo-a", "Stable Repo", "git-projects/stable-repo"),
        make_repo_asset("repo-b", "Mock Trial4.26", "git-projects/Mock Trial4.26"),
    ]

    result = write_downstream_pilot_candidates(tmp_path, assets, limit=10)
    output = Path(result["output"])
    text = output.read_text(encoding="utf-8")

    assert result["candidate_count"] == 1
    assert result["excluded_count"] == 1
    assert "Stable Repo" in text
    assert "Mock Trial4.26" in text
    assert "excluded by active Mock Trial safety rule" in text
    assert not (tmp_path / ".githooks").exists()


def test_phase45_readiness_reports_are_planning_only(tmp_path: Path):
    result = write_phase45_readiness_reports(tmp_path)

    assert Path(result["phase4_readiness"]).exists()
    assert Path(result["phase5_readiness"]).exists()
    assert "Do not enable embeddings" in phase4_readiness_markdown()
    assert "Do not schedule scans" in phase5_readiness_markdown()


def test_operational_readiness_fails_closed_for_empty_repo(tmp_path: Path):
    cfg = AppConfig(
        repo_root=tmp_path,
        raw={},
        database_path=tmp_path / "state" / "catalog.sqlite3",
        local_sources=[],
        github_sources=[],
        settings=Settings(),
    )

    result = build_operational_readiness(cfg, include_git=False)
    text = operational_readiness_markdown(result)

    assert result["ready"] is False
    assert result["missing_surfaces"]
    assert any("Catalog database is missing or empty" in warning for warning in result["warnings"])
    assert "python -m pytest" in text
    assert "Operational readiness summarizes current local evidence" in text


def test_operational_readiness_report_is_generated_output(tmp_path: Path):
    cfg = AppConfig(
        repo_root=tmp_path,
        raw={},
        database_path=tmp_path / "state" / "catalog.sqlite3",
        local_sources=[],
        github_sources=[],
        settings=Settings(),
    )

    result = write_operational_readiness_report(cfg)

    assert Path(result["report"]).is_relative_to(tmp_path / "processed")
    assert Path(result["payload"]).is_relative_to(tmp_path / "processed")
    assert Path(result["report"]).exists()
    assert Path(result["payload"]).exists()
    assert result["candidate_only"] is True
