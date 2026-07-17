from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from digital_asset_directory import portfolio_continuity_inventory as continuity


def _git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "DAD Test",
        "GIT_AUTHOR_EMAIL": "dad@example.invalid",
        "GIT_COMMITTER_NAME": "DAD Test",
        "GIT_COMMITTER_EMAIL": "dad@example.invalid",
    }
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise AssertionError(f"git {args[0]} failed: {completed.stderr}")
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "private-repository-name"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    return repo


def test_inventory_deduplicates_ref_oids_and_observes_detached_dirty_worktree(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    linked = tmp_path / "secret-linked-worktree"
    _git(repo, "worktree", "add", "--detach", str(linked), head)
    private_name = "unfinished-hybrid-cloud-idea.md"
    (linked / private_name).write_text("private unfinished details\n", encoding="utf-8")

    packet = continuity.build_continuity_inventory(repo)

    observed = next(row for row in packet["objects"] if row["object_id"] == head)
    assert observed["ref_count"] == 2
    assert observed["ref_kinds"] == ["head", "remote"]
    assert observed["worktree_count"] == 2
    assert observed["detached_worktree"] is True
    detached = next(row for row in packet["worktrees"] if row["detached"])
    assert detached["dirty"] is True
    assert detached["changes"]["untracked"] == 1
    assert packet["coverage"]["network_calls"] == 0
    assert packet["coverage"]["git_writes"] == 0
    assert "codex_metadata_not_supplied" in packet["coverage"]["gaps"]
    assert packet["coverage"]["codex_source"] == "not_supplied"

    serialized = json.dumps(packet, sort_keys=True)
    assert str(repo.resolve()) not in serialized
    assert str(linked.resolve()) not in serialized
    assert private_name not in serialized
    assert "private unfinished details" not in serialized


def test_inventory_accepts_only_explicit_codex_metadata_and_persists_no_title(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    secret_task_id = "codex-task-private-123"
    secret_title = r"Confidential plan C:\Users\lowel\private\idea"

    packet = continuity.build_continuity_inventory(
        repo,
        codex_metadata=[
            {
                "task_id": secret_task_id,
                "title": secret_title,
                "state": "active",
                "updated_at": "2026-07-16T12:00:00Z",
            }
        ],
    )

    assert len(packet["codex_items"]) == 1
    assert packet["codex_items"][0]["state"] == "active"
    serialized = json.dumps(packet, sort_keys=True)
    assert secret_task_id not in serialized
    assert secret_title not in serialized
    assert r"C:\Users\lowel" not in serialized


def test_inventory_aggregates_porcelain_v2_staged_and_unstaged_counts(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    tracked = repo / "base.txt"
    tracked.write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    tracked.write_text("staged and then modified\n", encoding="utf-8")

    packet = continuity.build_continuity_inventory(repo)

    current = next(row for row in packet["worktrees"] if not row["detached"])
    assert current["dirty"] is True
    assert current["changes"]["staged"] == 1
    assert current["changes"]["unstaged"] == 1


def test_inventory_uses_only_allowlisted_read_only_git_commands(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    commands: list[tuple[str, ...]] = []

    def recording_runner(cwd: Path, args: list[str] | tuple[str, ...]) -> continuity.GitResult:
        commands.append(tuple(args))
        return continuity._default_git_runner(cwd, args)

    continuity.build_continuity_inventory(repo, runner=recording_runner)

    assert commands
    assert {row[0] for row in commands} <= {
        "rev-parse",
        "for-each-ref",
        "worktree",
        "status",
    }
    assert not ({"fetch", "pull", "push", "remote", "update-ref"} & {row[0] for row in commands})


def test_default_runner_disables_optional_git_locks(monkeypatch, tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(continuity.subprocess, "run", fake_run)
    continuity._default_git_runner(tmp_path, ["status", "--porcelain=v2", "-z"])

    assert observed["env"]["GIT_OPTIONAL_LOCKS"] == "0"
