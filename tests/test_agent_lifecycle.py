import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from digital_asset_directory.agent_lifecycle import (
    handle_lifecycle_event,
    stable_lifecycle_session_id,
)
from digital_asset_directory.learning import postflight

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _init_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)


def _audit_rows(hub: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted((hub / "audit" / "events").glob("*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return rows


def test_neutral_lifecycle_records_generic_agent_and_blocks_dirty_stop(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    _init_repo(repo)

    result = handle_lifecycle_event(
        "session-start",
        hub_root=hub,
        repo=repo,
        agent="other",
        external_session_id="generic-session",
        task="generic agent task",
    )
    _, internal_uuid = stable_lifecycle_session_id(
        repo,
        agent="other",
        external_session_id="generic-session",
    )
    session = json.loads(
        (hub / "state" / "agent_sessions" / f"{internal_uuid}.json").read_text()
    )

    assert result.session_id == session["session_id"]
    assert session["agent"] == "other"
    assert session["task"] == "generic agent task"
    assert "postflight" in result.message

    handle_lifecycle_event(
        "post-tool",
        hub_root=hub,
        repo=repo,
        agent="other",
        external_session_id="generic-session",
        tool="shell",
        tool_input_keys=["command"],
    )
    rows = _audit_rows(hub)
    assert "agent_lifecycle_session_start" in {row["event_type"] for row in rows}
    assert "agent_lifecycle_post_tool" in {row["event_type"] for row in rows}

    (repo / "changed.txt").write_text("changed\n", encoding="utf-8")
    stop_result = handle_lifecycle_event(
        "stop",
        hub_root=hub,
        repo=repo,
        agent="other",
        external_session_id="generic-session",
    )
    assert stop_result.payload
    assert stop_result.payload["decision"] == "block"
    drafts = list((hub / "raw" / "handoffs").glob("*/*.json"))
    assert drafts
    draft = json.loads(drafts[0].read_text())
    assert draft["agent"] == "other"
    assert "changed.txt" in draft["files_changed"]

    postflight(
        hub,
        hub / "state" / "catalog.sqlite3",
        result.session_id,
        "neutral lifecycle closed",
        tests_run=["not run: lifecycle unit path"],
    )
    closed_stop = handle_lifecycle_event(
        "stop",
        hub_root=hub,
        repo=repo,
        agent="other",
        external_session_id="generic-session",
    )
    assert closed_stop.payload is None


def test_lifecycle_accepts_custom_agent_id_and_default_external_session(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    _init_repo(repo)

    result = handle_lifecycle_event(
        "session-start",
        hub_root=hub,
        repo=repo,
        agent="local-frontier-agent",
    )
    _, internal_uuid = stable_lifecycle_session_id(
        repo,
        agent="local-frontier-agent",
        external_session_id="default",
    )
    session = json.loads(
        (hub / "state" / "agent_sessions" / f"{internal_uuid}.json").read_text()
    )

    assert result.session_id == session["session_id"]
    assert session["agent"] == "local-frontier-agent"
    assert session["external_session_id"] == "default"


def test_claude_hook_delegates_to_neutral_lifecycle(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo"
    _init_repo(repo)
    env = os.environ.copy()
    env["DAD_HUB"] = str(hub)

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "claude_hook.py"), "session-start"],
        input=json.dumps({"cwd": str(repo), "session_id": "claude-session"}),
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    _, internal_uuid = stable_lifecycle_session_id(
        repo,
        agent="claude-code",
        external_session_id="claude-session",
        session_key_agent="claude",
    )
    session = json.loads(
        (hub / "state" / "agent_sessions" / f"{internal_uuid}.json").read_text()
    )

    assert "Digital Asset Directory session" in completed.stdout
    assert session["agent"] == "claude-code"
    assert session["external_session_id"] == "claude-session"
    assert "agent_lifecycle_session_start" in {
        row["event_type"] for row in _audit_rows(hub)
    }
