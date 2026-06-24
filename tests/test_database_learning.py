from pathlib import Path

from digital_asset_directory.database import CatalogDB
from digital_asset_directory.learning import preflight, postflight

import pytest

pytestmark = pytest.mark.integration


def test_preflight_postflight_closes_session_and_persists(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = hub / "state" / "catalog.sqlite3"
    session = preflight(hub, repo, db_path, "codex", "test work")
    handoff, lesson = postflight(
        hub,
        db_path,
        session["session_id"],
        "completed",
        tests_run=["pytest"],
        lessons=["capture state transitions"],
    )
    assert handoff.session_id == session["session_id"]
    assert lesson.lessons == ["capture state transitions"]
    with CatalogDB(db_path) as db:
        assert db.connection.execute("select count(*) from handoffs").fetchone()[0] == 1
        assert db.connection.execute("select count(*) from lessons").fetchone()[0] == 1
