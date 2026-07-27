"""Boot verb: guard, report assembly, plain-language rendering."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from digital_asset_directory import boot as boot_mod
from digital_asset_directory.boot import (
    data_root_guard,
    plain_reasons,
    render_boot_text,
    run_boot,
    today_items,
)


def _write_cockpit_fixture(hub: Path, *, generated_at: str, count: int = 4) -> Path:
    path = hub / "processed" / "reports" / "portfolio_os" / "cockpit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    today = [
        {
            "project_name": f"project-{index}",
            "label": f"project-{index} / branch-{index}",
            "inactive_days": index,
            "reasons": ["dirty_worktree_idle", "upstream_gone"],
            "next_action": "Review the diff; resume or park it.",
        }
        for index in range(count)
    ]
    path.write_text(
        json.dumps({"generated_at": generated_at, "today": today}),
        encoding="utf-8",
    )
    return path


def test_onedrive_guard_blocks_until_overridden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fake_root = Path("C:/Users/example/OneDrive/dad-data")
    monkeypatch.setattr(
        boot_mod, "resolve_data_root", lambda hub_root: (fake_root, "data_root")
    )
    blocked = data_root_guard(tmp_path)
    assert blocked["status"] == "blocked"
    assert "OneDrive" in blocked["plain_language"]
    allowed = data_root_guard(tmp_path, allow_onedrive=True)
    assert allowed["status"] == "ok"
    assert allowed["onedrive"] is True


def test_run_boot_blocked_on_onedrive_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setattr(
        boot_mod,
        "resolve_data_root",
        lambda hub_root: (Path("C:/Users/example/OneDrive/dad-data"), "data_root"),
    )
    report = run_boot(hub, apply_checkpoint=False)
    assert report["status"] == "blocked"
    assert not (hub / "processed" / "reports" / "boot_health.json").exists()
    lines = render_boot_text(report)
    assert lines[0] == "DAD did not start."


def test_plain_reasons_translates_and_caps():
    text = plain_reasons(
        ["conflicted_worktree", "upstream_gone", "stale_branch"], limit=2
    )
    assert text == "has a merge conflict and lost its matching GitHub branch"
    assert plain_reasons(["unknown_reason_code"]) == "unknown reason code"


def test_today_items_caps_at_three_and_reports_age(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    now = datetime.now(timezone.utc)
    _write_cockpit_fixture(hub, generated_at=now.isoformat(), count=4)
    summary = today_items(hub, now=now)
    assert summary["status"] == "ok"
    assert len(summary["items"]) == 3
    assert summary["age_hours"] == pytest.approx(0.0, abs=0.1)
    assert summary["items"][0]["plain_reason"].startswith("has unsaved work")


def test_run_boot_assembles_report_and_health_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setattr(boot_mod, "default_journal_repo", lambda: None)
    now = datetime.now(timezone.utc)
    _write_cockpit_fixture(hub, generated_at=now.isoformat())

    report = run_boot(hub, apply_checkpoint=False, now=now)

    assert report["status"] == "attention"
    assert len(report["today"]["items"]) == 3
    assert any("backup journal repo" in line for line in report["attention"])
    assert any("restore" in line.lower() for line in report["attention"])
    health_path = hub / "processed" / "reports" / "boot_health.json"
    assert health_path.is_file()
    persisted = json.loads(health_path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "dad.boot_health.v1"
    assert persisted["candidate_only"] is True
    assert persisted["thresholds"]["today_limit"] == 3

    lines = render_boot_text(report)
    rendered = "\n".join(lines)
    assert all(ord(char) < 128 for char in rendered), "terminal output must be ASCII"
    assert "Today (top 3" in rendered
    assert "1. project-0" in rendered


def test_run_boot_applies_due_checkpoint_through_real_journal(tmp_path: Path):
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        "\n".join(json.dumps({"i": i}) for i in range(200)) + "\n",
        encoding="utf-8",
    )
    journal_repo = tmp_path / "dad-journal"
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-b", "journal-data", str(journal_repo)], check=True)
    subprocess.run(
        ["git", "-C", str(journal_repo), "config", "user.email", "dad@example.test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(journal_repo), "config", "user.name", "DAD Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(journal_repo), "remote", "add", "origin", str(origin)],
        check=True,
    )

    report = run_boot(hub, journal_repo=journal_repo, apply_checkpoint=True)

    assert report["journal"]["checkpoint_applied"] is True
    assert report["journal"]["journal_repo_source"] == "explicit"
    lines = render_boot_text(report)
    assert any("backed up just now" in line.lower() for line in lines)
