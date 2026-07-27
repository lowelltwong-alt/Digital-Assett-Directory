"""Restore drill: prove the committed checkpoint restores intact, catch tampering."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from digital_asset_directory.journal import (
    checkpoint_journal,
    restore_drill,
    restore_drill_status,
)
from digital_asset_directory.transport import DATA_PLANE_PATHS, data_path


def _make_hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        "\n".join(json.dumps({"i": i}) for i in range(200)) + "\n",
        encoding="utf-8",
    )
    if "catalog_database" in DATA_PLANE_PATHS:
        catalog = data_path(hub, "catalog_database")
        catalog.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(catalog) as db:
            db.execute("CREATE TABLE assets (asset_id TEXT PRIMARY KEY)")
            db.execute("INSERT INTO assets VALUES ('dad:asset:example')")
    return hub


def _make_journal_repo(tmp_path: Path) -> Path:
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
    return journal_repo


def test_restore_drill_verifies_committed_checkpoint(tmp_path: Path):
    hub = _make_hub(tmp_path)
    journal_repo = _make_journal_repo(tmp_path)
    applied = checkpoint_journal(
        hub, journal_repo, apply=True, min_records=200, min_hours=999
    )
    assert applied["checkpoint_applied"] is True

    scratch = tmp_path / "scratch"
    result = restore_drill(hub, journal_repo, scratch_root=scratch)

    assert result["status"] == "verified"
    assert result["integrity"]["valid"] is True
    assert result["file_count"] >= 1
    assert result["restored_bytes"] > 0
    assert result["duration_seconds"] >= 0
    assert result["narrative"], "drill must explain itself in plain language"
    assert "checkpoint_freshness_see_journal_status" in result["does_not_prove"]
    if "catalog_database" in DATA_PLANE_PATHS:
        assert any(row["status"] == "ok" for row in result["sqlite_checks"])
    # scratch is cleaned up by default
    assert not (scratch / "restore-drill").exists() or not any(
        (scratch / "restore-drill").iterdir()
    )
    # persisted so boot can surface drill age
    persisted = restore_drill_status(hub)
    assert persisted["status"] == "verified"
    assert persisted["schema_version"] == "dad.journal.restore_drill.v1"


def test_restore_drill_fails_on_tampered_checkpoint(tmp_path: Path):
    hub = _make_hub(tmp_path)
    journal_repo = _make_journal_repo(tmp_path)
    applied = checkpoint_journal(
        hub, journal_repo, apply=True, min_records=200, min_hours=999
    )
    assert applied["checkpoint_applied"] is True

    # Materialize the working tree, corrupt one checkpointed file, commit the
    # corruption so HEAD no longer matches the manifest file index.
    subprocess.run(["git", "-C", str(journal_repo), "checkout", "-f"], check=True)
    tampered = journal_repo / "data" / "processed" / "mail" / "inbox" / "rows.jsonl"
    assert tampered.is_file()
    tampered.write_text("tampered\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(journal_repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(journal_repo), "commit", "-m", "synthetic tamper"],
        check=True,
    )

    result = restore_drill(hub, journal_repo, scratch_root=tmp_path / "scratch")

    assert result["status"] == "failed"
    assert result["integrity"]["valid"] is False
    assert any(
        row.get("error") == "hash_or_size_mismatch"
        for row in result["integrity"]["errors"]
    )
    assert any("NOT match" in line for line in result["narrative"])


def test_checkpoint_commits_files_ignored_by_embedded_gitignore(tmp_path: Path):
    """Regression: 2026-07-25 drill found indexed files silently dropped from HEAD.

    Data-plane payloads can contain their own .gitignore rows (synthetic
    transport workspaces do). Staging must force-add indexed paths so ignore
    rules that arrived as data never hollow out the committed checkpoint.
    """

    hub = _make_hub(tmp_path)
    mail_dir = (
        hub
        / "processed"
        / "reports"
        / "_synthetic_workspaces"
        / "ws-example"
        / "current"
        / ".digital-asset"
        / "mail"
    )
    mail_dir.mkdir(parents=True)
    (mail_dir / ".gitignore").write_text("*.jsonl\n", encoding="utf-8")
    (mail_dir / "outbox.jsonl").write_text('{"row": 1}\n', encoding="utf-8")
    journal_repo = _make_journal_repo(tmp_path)

    applied = checkpoint_journal(
        hub, journal_repo, apply=True, min_records=200, min_hours=999
    )
    assert applied["checkpoint_applied"] is True

    committed = subprocess.run(
        [
            "git",
            "-C",
            str(journal_repo),
            "ls-tree",
            "--name-only",
            "HEAD",
            "data/processed/reports/_synthetic_workspaces/ws-example/current/"
            ".digital-asset/mail/",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "outbox.jsonl" in committed

    drill_first = restore_drill(hub, journal_repo, scratch_root=tmp_path / "s1")
    assert drill_first["status"] == "verified"

    # A second due cycle with unchanged data must reuse files and stay verified.
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    with inbox.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps({"j": i}) for i in range(200)) + "\n")
    applied_again = checkpoint_journal(
        hub, journal_repo, apply=True, min_records=200, min_hours=999
    )
    assert applied_again["checkpoint_applied"] is True
    assert applied_again["unchanged_file_count"] >= 1
    drill_second = restore_drill(hub, journal_repo, scratch_root=tmp_path / "s2")
    assert drill_second["status"] == "verified"


def test_restore_drill_blocked_without_journal_repo(tmp_path: Path):
    hub = _make_hub(tmp_path)
    result = restore_drill(hub, None)
    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "journal_repo_not_configured"
    assert restore_drill_status(hub)["status"] == "blocked"
