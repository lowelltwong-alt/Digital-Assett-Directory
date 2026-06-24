from pathlib import Path

from digital_asset_directory.config import LocalSource, Settings
from digital_asset_directory.local_scan import scan_local_source
from digital_asset_directory.scoring import DEFAULT_WEIGHTS
from digital_asset_directory.utils import sha256_file

import pytest

pytestmark = pytest.mark.integration


def test_local_scan_is_read_only_and_redacts_excerpt(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    readme = repo / "README.md"
    readme.write_text(
        "# Project\nsecret=do-not-store\nknowledge graph evaluation harness", encoding="utf-8"
    )
    empty_note = repo / "empty.md"
    empty_note.write_text("", encoding="utf-8")
    before = sha256_file(readme)
    source = LocalSource(id="test", path=tmp_path, path_alias="test", exclude=["**/.git/**"])
    assets, hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})
    assert sha256_file(readme) == before
    assert hashes[str(readme)] == before
    file_asset = next(a for a in assets if a.logical_path.endswith("README.md"))
    assert "do-not-store" not in file_asset.metadata["excerpt"]
    assert file_asset.parent_asset_id is not None
    empty_asset = next(a for a in assets if a.logical_path.endswith("empty.md"))
    assert empty_asset.metadata["content_skipped_for_size"] is False
    assert empty_asset.metadata["excerpt"] == ""
    assert "exceeded the configured size limit" not in empty_asset.description


def test_local_scan_adds_candidate_composite_patterns_to_repository(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "schemas").mkdir()
    (repo / "tests").mkdir()
    (repo / "workflows").mkdir()
    (repo / "docs").mkdir()
    (repo / "schemas" / "asset.schema.json").write_text(
        '{"title":"Asset schema","description":"json schema contract validation"}',
        encoding="utf-8",
    )
    (repo / "tests" / "test_graph.py").write_text(
        "def test_graph():\n    assert 'knowledge graph evaluation'\n",
        encoding="utf-8",
    )
    (repo / "workflows" / "agent_pipeline.md").write_text(
        "# Agent Workflow\npreflight postflight handoff agent orchestration learning loop",
        encoding="utf-8",
    )
    (repo / "docs" / "LESSONS.md").write_text(
        "# Lessons\nfeedback learning loop postflight lesson learned",
        encoding="utf-8",
    )
    source = LocalSource(id="test", path=tmp_path, path_alias="test", exclude=["**/.git/**"])

    assets, _hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})

    repo_asset = next(asset for asset in assets if asset.asset_type == "repository")
    pattern_ids = {
        str(pattern["pattern_id"])
        for pattern in repo_asset.metadata.get("composite_patterns", [])
    }
    assert "evaluation_contract_system" in pattern_ids
    assert "governed_learning_loop_system" in pattern_ids
    assert repo_asset.metadata["composite_asset_hint"]["child_asset_count"] >= 4
    assert repo_asset.metadata["composite_asset_hint"]["authority"].startswith("Generated")
    assert "composite-asset" in repo_asset.tags
