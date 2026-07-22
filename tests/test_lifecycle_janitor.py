"""Tests for the lifecycle janitor: honest, bounded, config-gated cleanup."""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digital_asset_directory import lifecycle_janitor as lj
from digital_asset_directory.database import CatalogDB
from digital_asset_directory.learning import agent_sessions_dir
from digital_asset_directory.models import EdgeRecord

_TS = "2026-07-21T00:00:00+00:00"


def _write_session(hub: Path, sid: str, *, idle_hours: float, status: str = "open",
                   agent: str = "codex", task: str = "build a feature") -> Path:
    d = agent_sessions_dir(hub)
    d.mkdir(parents=True, exist_ok=True)
    p = d / (sid.replace("dad:session:", "") + ".json")
    p.write_text(json.dumps({
        "session_id": sid, "status": status, "agent": agent, "task": task,
        "repository": str(hub.resolve()), "created_at": _TS,
    }), encoding="utf-8")
    ts = (datetime.now(timezone.utc) - timedelta(hours=idle_hours)).timestamp()
    os.utime(p, (ts, ts))
    return p


def _edge(scan_id: str, i: int) -> EdgeRecord:
    return EdgeRecord(edge_id=f"edge:{scan_id}:{i}", edge_type="related_to",
                      source_asset_id=f"a{i}", target_asset_id=f"b{i}", method="test",
                      confidence=0.5, created_at=_TS, scan_id=scan_id)


# --- sessions ---------------------------------------------------------------

def test_session_plan_splits_by_idle_threshold(tmp_path: Path) -> None:
    _write_session(tmp_path, "dad:session:live", idle_hours=1.0)
    _write_session(tmp_path, "dad:session:review", idle_hours=10.0)
    _write_session(tmp_path, "dad:session:auto", idle_hours=48.0)
    plan = lj.plan_session_reap(tmp_path, repository=tmp_path.resolve(),
                                idle_live_hours=6.0, autoapply_idle_hours=24.0)
    assert {e["session_id"] for e in plan["auto_eligible"]} == {"dad:session:auto"}
    assert {e["session_id"] for e in plan["review_needed"]} == {"dad:session:review"}


def test_session_apply_closes_honestly_and_preserves_live(tmp_path: Path) -> None:
    p_auto = _write_session(tmp_path, "dad:session:auto", idle_hours=48.0)
    p_live = _write_session(tmp_path, "dad:session:live", idle_hours=1.0)
    plan = lj.plan_session_reap(tmp_path, repository=tmp_path.resolve(),
                                idle_live_hours=6.0, autoapply_idle_hours=24.0)
    result = lj.apply_session_reap(tmp_path, plan, approval_ref="test")
    assert result["closed"] == ["dad:session:auto"]
    closed = json.loads(p_auto.read_text(encoding="utf-8"))
    # Honest: abandoned, NOT a fabricated completion/postflight.
    assert closed["status"] == "abandoned_reaped"
    assert closed["reaped_reason"] and closed["reaped_at"]
    assert json.loads(p_live.read_text(encoding="utf-8"))["status"] == "open"


def test_session_reap_skips_exception_held(tmp_path: Path) -> None:
    p = _write_session(tmp_path, "dad:session:leased", idle_hours=99.0, status="leased")
    plan = lj.plan_session_reap(tmp_path, repository=tmp_path.resolve(),
                                idle_live_hours=6.0, autoapply_idle_hours=24.0)
    # 'leased' is not status 'open' so it is never even considered open.
    assert not plan["auto_eligible"] and not plan["review_needed"]
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "leased"


# --- catalog ----------------------------------------------------------------

def test_catalog_retention_prunes_and_vacuums(tmp_path: Path) -> None:
    db_path = tmp_path / "c.sqlite3"
    with CatalogDB(db_path) as db:
        db.start_scan("s_old")
        db.replace_scan_edges("s_old", [_edge("s_old", 1), _edge("s_old", 2)])
        db.complete_scan("s_old", "complete", {"scan_id": "s_old"})
        db.start_scan("s_new")
        db.replace_scan_edges("s_new", [_edge("s_new", 1)])
        db.complete_scan("s_new", "complete", {"scan_id": "s_new"})
    # Drive the pure retention primitives directly (module resolves via config).
    with CatalogDB(db_path) as db:
        keep = db.latest_complete_scan()["scan_id"]
        assert keep == "s_new"
        removed = db.prune_generated_records(keep)
        assert removed["edges"] == 2
        db.vacuum()
        assert {e.scan_id for e in db.edges()} == {"s_new"}


# --- worktrees --------------------------------------------------------------

def test_worktree_prune_detects_orphaned_admin_entry(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    def git(*a):
        subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, env=env)
    git("init", "-q")
    (repo / "f.txt").write_text("x", encoding="utf-8")
    git("add", "."); git("commit", "-qm", "init")
    wt = tmp_path / "wt"
    git("worktree", "add", "-q", str(wt))
    # Simulate a worktree whose directory was deleted out from under git.
    import shutil
    shutil.rmtree(wt)
    plan = lj.plan_worktree_prune(repo)
    assert plan["prunable_count"] >= 1
    applied = lj.apply_worktree_prune(repo)
    assert applied["ran"]
    assert lj.plan_worktree_prune(repo)["prunable_count"] == 0


# --- orchestration ----------------------------------------------------------

def test_cycle_dry_run_never_mutates(tmp_path: Path) -> None:
    p = _write_session(tmp_path, "dad:session:auto", idle_hours=48.0)
    report = lj.run_janitor_cycle(tmp_path, repository=tmp_path.resolve(), apply=False)
    assert report["applied"] is False
    assert report["candidate_only"] is True
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "open"


def test_cycle_apply_gates_session_reap_behind_optin(tmp_path: Path) -> None:
    p = _write_session(tmp_path, "dad:session:auto", idle_hours=48.0)
    # Default config: session_reap.apply is False -> even apply=True leaves sessions.
    report = lj.run_janitor_cycle(tmp_path, repository=tmp_path.resolve(), apply=True)
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "open"
    assert "skipped" in report["actions"]["session_reap"]
    # apply=True but blank approval_ref -> STILL blocked (F2/G5 gate is load-bearing).
    cfg = lj.load_janitor_config(tmp_path)
    cfg["session_reap"]["apply"] = True
    report2 = lj.run_janitor_cycle(tmp_path, repository=tmp_path.resolve(), apply=True, config=cfg)
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "open"
    assert "approval_ref is empty" in report2["actions"]["session_reap"]["skipped"]
    # Named human approval -> now it reaps.
    cfg["session_reap"]["approval_ref"] = "human:lowell:2026-07-22:reap-idle"
    lj.run_janitor_cycle(tmp_path, repository=tmp_path.resolve(), apply=True, config=cfg)
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "abandoned_reaped"


def test_apply_session_reap_refuses_empty_approval_ref(tmp_path: Path) -> None:
    _write_session(tmp_path, "dad:session:auto", idle_hours=48.0)
    plan = lj.plan_session_reap(tmp_path, repository=tmp_path.resolve(),
                                idle_live_hours=6.0, autoapply_idle_hours=24.0)
    result = lj.apply_session_reap(tmp_path, plan, approval_ref="   ")
    assert result["closed_count"] == 0
    assert "skipped" in result
