from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from digital_asset_directory.logos_write_guard import LogosWriteBlocked, assert_dad_write_allowed, authority_registry
from digital_asset_directory.archaeology import append_repo_learning_event
from digital_asset_directory.governance import install_governance
from digital_asset_directory.mail_center import append_jsonl_locked, ensure_repo_mailbox
from digital_asset_directory.transport import apply_data_migration
from digital_asset_directory.learning import rebuild_lesson_routes
from digital_asset_directory.daemon import install_task_scheduler
from digital_asset_directory.utils import append_jsonl, atomic_write_text


def _protect(repo: Path, *, approval_ids: list[str] | None = None) -> Path:
    marker = repo / ".digital-asset/dad-write-policy.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps(
            {
                "schema_version": "dad.logos.write-policy.v1",
                "repo_id": "logos-synthetic",
                "dad_write_allowed": False,
                "approval_mode": "fresh_explicit_owner_approval",
                "approved_explicit_approval_ids": approval_ids or [],
            }
        ),
        encoding="utf-8",
    )
    return marker


def test_shared_writers_fail_before_creating_any_logos_path(tmp_path: Path) -> None:
    repo = tmp_path / "logos"
    _protect(repo)
    target = repo / ".digital-asset/mail/inbox.jsonl"

    with pytest.raises(LogosWriteBlocked):
        atomic_write_text(target, "blocked\n")
    with pytest.raises(LogosWriteBlocked):
        append_jsonl(target, {"blocked": True})

    assert not target.exists()


def test_guard_allows_reads_and_writes_outside_protected_repo(tmp_path: Path) -> None:
    repo = tmp_path / "logos"
    marker = _protect(repo)
    assert json.loads(marker.read_text())["dad_write_allowed"] is False

    central = tmp_path / "dad-data/processed/lessons.jsonl"
    atomic_write_text(central, "central\n")
    assert central.read_text() == "central\n"


def test_static_or_environment_approval_cannot_bypass_guard(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "logos"
    _protect(repo, approval_ids=["OWNER-APPROVAL-123"])
    target = repo / "candidate.txt"

    monkeypatch.setenv("DAD_LOGOS_WRITE_APPROVAL_ID", "OWNER-APPROVAL-123")
    with pytest.raises(LogosWriteBlocked):
        assert_dad_write_allowed(target)
    with pytest.raises(LogosWriteBlocked):
        assert_dad_write_allowed(target, approval_id="OWNER-APPROVAL-123")


def test_invalid_policy_fails_closed(tmp_path: Path) -> None:
    repo = tmp_path / "logos"
    marker = repo / ".digital-asset/dad-write-policy.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("not-json", encoding="utf-8")

    with pytest.raises(LogosWriteBlocked, match="unreadable Logos policy"):
        assert_dad_write_allowed(repo / "anything.txt")


def test_unmarked_renamed_clone_is_blocked_by_remote_identity(tmp_path: Path) -> None:
    repo = tmp_path / "innocent-looking-clone"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/lowelltwong-alt/logos-scripture-graph.git"],
        check=True,
    )
    target = repo / "new/path.txt"

    with pytest.raises(LogosWriteBlocked):
        atomic_write_text(target, "blocked\n")
    assert not (repo / "new").exists()


def test_unmarked_known_logos_directory_is_blocked(tmp_path: Path) -> None:
    repo = tmp_path / "logos-boundary-literature"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    with pytest.raises(LogosWriteBlocked):
        append_jsonl(repo / ".digital-asset/events/outbox.jsonl", {"blocked": True})
    assert not (repo / ".digital-asset").exists()


def test_mail_lock_and_mailbox_fail_before_any_directory_side_effect(tmp_path: Path) -> None:
    repo = tmp_path / "logos-scripture-graph"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    with pytest.raises(LogosWriteBlocked):
        append_jsonl_locked(repo / ".digital-asset/events/outbox.jsonl", {"blocked": True})
    with pytest.raises(LogosWriteBlocked):
        ensure_repo_mailbox(repo)
    assert not (repo / ".digital-asset").exists()


def test_legacy_installers_and_learning_event_are_blocked(tmp_path: Path) -> None:
    repo = tmp_path / "logos-doctrine-genealogy"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    hub = tmp_path / "hub"
    with pytest.raises(LogosWriteBlocked):
        install_governance(repo, hub)
    with pytest.raises(LogosWriteBlocked):
        append_repo_learning_event(
            repo,
            stage="after_work",
            task="synthetic",
            agent="test",
            context_tags=["synthetic"],
        )
    assert not (repo / "AGENTS.md").exists()
    assert not (repo / ".digital-asset-directory").exists()


def test_data_migration_cannot_target_logos_repo(tmp_path: Path) -> None:
    repo = tmp_path / "logos-governance-architecture"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    hub = tmp_path / "hub"
    source = hub / "processed/mail/inbox/row.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text("{}\n", encoding="utf-8")

    with pytest.raises(LogosWriteBlocked):
        apply_data_migration(hub, repo)
    assert not (repo / "processed").exists()


def test_reviewed_authority_registry_has_no_write_or_standing_grant() -> None:
    registry = authority_registry()
    assert registry["surface_version"] == "1.0.0"
    assert registry["default_dad_write_mode"] == "deny"
    assert registry["dad_scheduled_write_grants_allowed"] is False
    assert {row["repo_id"] for row in registry["repos"]} == {
        "logos-governance-architecture",
        "logos-scripture-graph",
        "logos-boundary-literature",
        "logos-doctrine-genealogy",
    }
    assert all(row["dad_write_mode"] == "deny" for row in registry["repos"])
    assert registry["approval_state"]["standing_approval_ids"] == []
    assert registry["approval_state"]["environment_override_allowed"] is False
    assert registry["approval_state"]["single_use_grant_implemented"] is False


def test_lesson_route_rebuild_cannot_delete_logos_indexes(tmp_path: Path) -> None:
    repo = tmp_path / "logos-scripture-graph"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    index = repo / "raw/lessons/by-repo/existing.jsonl"
    index.parent.mkdir(parents=True)
    index.write_text('{"lesson_id":"keep"}\n', encoding="utf-8")

    with pytest.raises(LogosWriteBlocked):
        rebuild_lesson_routes(repo)
    assert index.read_text(encoding="utf-8") == '{"lesson_id":"keep"}\n'


def test_known_alias_is_blocked_before_git_or_marker_exists(tmp_path: Path) -> None:
    repo = tmp_path / "logos-scripture-graph"
    repo.mkdir()
    target = repo / "new/probe.txt"
    with pytest.raises(LogosWriteBlocked):
        atomic_write_text(target, "blocked\n")
    assert not (repo / "new").exists()


def test_nested_non_logos_git_cannot_mask_outer_logos_remote(tmp_path: Path) -> None:
    outer = tmp_path / "renamed-outer"
    inner = outer / "nested"
    subprocess.run(["git", "init", str(outer)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(outer), "remote", "add", "origin", "https://github.com/lowelltwong-alt/logos-governance-architecture.git"], check=True)
    subprocess.run(["git", "init", str(inner)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(inner), "remote", "add", "origin", "https://github.com/example/not-logos.git"], check=True)
    with pytest.raises(LogosWriteBlocked):
        atomic_write_text(inner / "probe.txt", "blocked\n")
    assert not (inner / "probe.txt").exists()


def test_scheduler_install_fails_before_parent_directory_creation(tmp_path: Path) -> None:
    repo = tmp_path / "logos-doctrine-genealogy"
    repo.mkdir()
    wrapper = repo / ".dad/bin/dad-daemon-run-cycle.ps1"
    plan = {
        "wrapper_path": str(wrapper),
        "wrapper_script": "Write-Output blocked\n",
        "command": "exit 0",
        "settings_command": ["powershell", "-NoProfile", "-Command", "exit 0"],
    }
    with pytest.raises(LogosWriteBlocked):
        install_task_scheduler(plan)
    assert not wrapper.parent.exists()
