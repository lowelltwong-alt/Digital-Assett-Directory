from pathlib import Path

import pytest

from digital_asset_directory.governance import (
    BEGIN,
    enforce_postflight,
    install_governance,
    scaffold_new_repo,
)
from digital_asset_directory.learning import preflight, postflight

pytestmark = pytest.mark.integration


def test_downstream_install_is_idempotent_and_enforces_open_session(tmp_path: Path):
    hub = tmp_path / "hub"
    (hub / "scripts").mkdir(parents=True)
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    install_governance(target, hub)
    install_governance(target, hub)
    assert (target / "AGENTS.md").read_text().count(BEGIN) == 1
    session = preflight(hub, target, hub / "state" / "catalog.sqlite3", "codex", "change")
    ok, _ = enforce_postflight(hub, target)
    assert not ok
    postflight(hub, hub / "state" / "catalog.sqlite3", session["session_id"], "done", lessons=["x"])
    ok, _ = enforce_postflight(hub, target)
    assert ok


def test_scaffold_new_repo_wires_starter_files_and_governance(tmp_path: Path):
    hub = tmp_path / "hub"
    (hub / "scripts").mkdir(parents=True)
    target = tmp_path / "fresh"
    changed = scaffold_new_repo(target, hub, name="Fresh Project")
    assert (target / "README.md").exists()
    assert (target / ".gitignore").exists()
    assert BEGIN in (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "hub_path" in (target / ".digital-asset-directory.yml").read_text(encoding="utf-8")
    assert (target / ".githooks" / "pre-push").exists()
    assert any("README.md" in str(path) for path in changed)
