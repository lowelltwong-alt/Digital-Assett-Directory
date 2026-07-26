from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest

from digital_asset_directory.agent_session_reaper import (
    build_agent_session_reaper_report,
    classify_session_tier,
    proposed_close_summary,
    write_agent_session_reaper_report,
)
from digital_asset_directory.routine_health import evaluate_contract, load_contracts
from digital_asset_directory.transport import DATA_ROOT_MARKER

ROOT = Path(__file__).resolve().parents[1]


def _write_session(path: Path, *, mtime: float | None = None, **fields: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "0.1.0",
        "session_id": f"dad:session:{path.stem}",
        "created_at": "2026-07-01T12:00:00+00:00",
        "repository": str(ROOT),
        "agent": "cursor",
        "task": "n2 build work",
        "status": "open",
        "required_postflight": True,
    }
    payload.update(fields)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _hub_with_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hub = tmp_path / "hub"
    data_root = tmp_path / "data-root"
    hub.mkdir()
    data_root.mkdir()
    (data_root / DATA_ROOT_MARKER).write_text(
        json.dumps({"hub_ref": str(hub.resolve())}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    return hub


def test_tier_classification() -> None:
    assert classify_session_tier({"agent": "redteam", "task": "x"}) == "E"
    assert classify_session_tier({"agent": "cursor", "task": "read-only check"}) == "E"
    assert classify_session_tier({"agent": "cursor", "task": "implement feature"}) == "B"


def test_proposed_summary_is_nonblank() -> None:
    text = proposed_close_summary(
        {"agent": "cursor", "task": "build something"},
        idle_hours=12.0,
        idle_live_hours=6.0,
        preservation_pointer="preserve://test",
    )
    assert "Administrative reaper close candidate" in text
    assert "preserve://test" in text
    assert text.strip()


def test_dry_run_classifies_idle_live_exception_and_keep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _hub_with_data_root(tmp_path, monkeypatch)
    sessions = Path(os.environ["DAD_DATA_ROOT"]) / "state" / "agent_sessions"
    now = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=10)).timestamp()
    fresh = (now - timedelta(hours=1)).timestamp()

    _write_session(sessions / "stale-build.json", mtime=stale, agent="cursor", task="ship feature")
    _write_session(
        sessions / "live.json",
        mtime=fresh,
        agent="cursor",
        task="still working",
    )
    _write_session(
        sessions / "parked.json",
        mtime=stale,
        agent="cursor",
        task="paused",
        parked=True,
    )
    _write_session(
        sessions / "reviewer.json",
        mtime=stale,
        agent="checker",
        task="independent read-only review",
    )
    keep_id = "dad:session:keep-me"
    _write_session(
        sessions / "keep-me.json",
        mtime=stale,
        session_id=keep_id,
        agent="cursor",
        task="keep open",
    )

    report = build_agent_session_reaper_report(
        hub,
        idle_live_hours=6.0,
        keep_session_ids={keep_id},
        now=now,
    )
    assert report["apply_authorized"] is False
    assert report["dry_run"] is True
    assert report["summary"]["candidate_close"] == 2
    assert report["summary"]["skipped_live"] == 1
    assert report["summary"]["skipped_exception"] == 1
    assert report["summary"]["skipped_keep"] == 1

    by_file = {row["session_file"]: row for row in report["candidates"]}
    assert by_file["stale-build.json"]["classification"] == "candidate_close"
    assert by_file["stale-build.json"]["tier"] == "B"
    assert by_file["stale-build.json"]["proposed_summary"]
    assert by_file["reviewer.json"]["classification"] == "candidate_close"
    assert by_file["reviewer.json"]["tier"] == "E"
    assert by_file["live.json"]["classification"] == "skipped_live"
    assert by_file["parked.json"]["classification"] == "skipped_exception"
    assert by_file["keep-me.json"]["classification"] == "skipped_keep"

    schema = json.loads(
        (ROOT / "schemas/agent-session-reaper-report.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(report, schema)


def test_write_report_does_not_mutate_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _hub_with_data_root(tmp_path, monkeypatch)
    sessions = Path(os.environ["DAD_DATA_ROOT"]) / "state" / "agent_sessions"
    path = sessions / "open.json"
    stale = time.time() - 10 * 3600
    _write_session(path, mtime=stale, status="open")
    before = path.read_text(encoding="utf-8")
    result = write_agent_session_reaper_report(hub)
    assert Path(result["json_path"]).is_file()
    assert Path(result["markdown_path"]).is_file()
    assert Path(result["receipt_path"]).is_file()
    assert Path(result["history_path"]).is_file()
    assert path.read_text(encoding="utf-8") == before
    assert result["report"]["apply_authorized"] is False


def test_repo_filter_excludes_other_repositories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _hub_with_data_root(tmp_path, monkeypatch)
    sessions = Path(os.environ["DAD_DATA_ROOT"]) / "state" / "agent_sessions"
    now = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=10)).timestamp()
    other = tmp_path / "other-repo"
    other.mkdir()
    _write_session(sessions / "here.json", mtime=stale, repository=str(ROOT))
    _write_session(sessions / "elsewhere.json", mtime=stale, repository=str(other))
    report = build_agent_session_reaper_report(hub, repository=ROOT, now=now)
    assert report["summary"]["candidate_close"] == 1
    assert report["summary"]["repo_mismatch"] == 1


def test_routine_contract_disabled() -> None:
    contracts = load_contracts(ROOT)["contracts"]
    contract = next(row for row in contracts if row["routine_id"] == "dad-agent-session-reaper")
    assert contract["enabled"] is False
    assert contract["freshness_hours"] is None
    assert evaluate_contract(ROOT, contract)["status"] == "disabled"


def test_idle_hours_must_be_positive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _hub_with_data_root(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        build_agent_session_reaper_report(hub, idle_live_hours=0)
