from pathlib import Path

import pytest

from digital_asset_directory import research

pytestmark = pytest.mark.unit


def test_missing_part_research_requires_external_enablement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fail_get(*_args, **_kwargs):
        raise AssertionError("external GitHub request should not run without enablement")

    monkeypatch.setattr(research.requests, "get", fail_get)

    report = research.research_missing_parts(tmp_path, tmp_path / "catalog.sqlite3")

    assert report["status"] == "blocked_external_research_not_enabled"
    assert "Live GitHub research requires --enable-external." in report["rules"]
    assert not (tmp_path / "raw" / "research").exists()
    assert not (tmp_path / "processed" / "reports" / "missing_part_research.md").exists()
