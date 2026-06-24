from pathlib import Path

from digital_asset_directory.governance import BEGIN, install_governance, enforce_postflight
from digital_asset_directory.learning import preflight, postflight


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
