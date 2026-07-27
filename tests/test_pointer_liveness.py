from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import digital_asset_directory.cli as cli
from digital_asset_directory.pointer_liveness import (
    ISSUE_MISSING_DEFAULT_BRANCH,
    ISSUE_MISSING_WORKTREE,
    ISSUE_UNPARSEABLE,
    ISSUE_UNTRACKED,
    validate_pointer_liveness,
)

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, **_GIT_ENV},
    )


def _navigation_registry(route_after: list[str], *, path: str = "AI_FRONT_DOOR.md") -> str:
    return json.dumps(
        {
            "singular_entrypoint": {"path": "AI_FRONT_DOOR.md"},
            "branch_map": [
                {
                    "branch_id": "fixture",
                    "path": path,
                    "route_after": route_after,
                }
            ],
        }
    )


def _init_repo(tmp_path: Path, *, route_after: list[str], branch_path: str = "AI_FRONT_DOOR.md") -> Path:
    repo = tmp_path / "repo"
    (repo / "registry").mkdir(parents=True)
    (repo / "AI_FRONT_DOOR.md").write_text("front door\n", encoding="utf-8")
    (repo / "registry" / "ai-navigation-registry.json").write_text(
        _navigation_registry(route_after, path=branch_path), encoding="utf-8"
    )
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial")
    return repo


def test_pointer_liveness_flags_orchestration_missing_on_default_branch(tmp_path: Path):
    """THE incident regression: a registry pointer at orchestration/ whose only

    copy lives on a preserve branch must fail with the headline code."""
    repo = _init_repo(tmp_path, route_after=["orchestration/TASK_BOARD.jsonl"])
    _git(repo, "checkout", "-b", "codex/preserve-parallel-orchestration-20260710")
    board = repo / "orchestration" / "TASK_BOARD.jsonl"
    board.parent.mkdir()
    board.write_text('{"task_id":"T-0001"}\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "checkpoint orchestration layer")
    _git(repo, "checkout", "main")

    result = validate_pointer_liveness(repo, mode="both")

    assert result["valid"] is False
    assert ISSUE_MISSING_DEFAULT_BRANCH in result["issue_codes"]
    assert ISSUE_MISSING_WORKTREE in result["issue_codes"]
    assert any(
        "orchestration/TASK_BOARD.jsonl" in error
        and error.startswith(ISSUE_MISSING_DEFAULT_BRANCH)
        for error in result["errors"]
    )


def test_pointer_liveness_untracked_is_distinct_from_missing(tmp_path: Path):
    repo = _init_repo(tmp_path, route_after=["docs/NEW_GUIDE.md"])
    guide = repo / "docs" / "NEW_GUIDE.md"
    guide.parent.mkdir()
    guide.write_text("present locally, never committed\n", encoding="utf-8")

    worktree_only = validate_pointer_liveness(repo, mode="worktree")
    assert worktree_only["valid"] is True

    result = validate_pointer_liveness(repo, mode="both")
    assert result["valid"] is False
    assert ISSUE_UNTRACKED in result["issue_codes"]
    assert ISSUE_MISSING_DEFAULT_BRANCH not in result["issue_codes"]


def test_pointer_liveness_skips_commands_uris_and_data_plane(tmp_path: Path):
    repo = _init_repo(
        tmp_path,
        route_after=[
            "asset-dir doctor",
            "dad://surface/lesson-graph/manifest",
            "processed/reports/scheduled_tasks.json",
            ".digital-asset/assets/index.jsonl",
            "~/.dad/bin/asset-dir",
        ],
    )

    result = validate_pointer_liveness(repo, mode="both")

    assert result["valid"] is True
    assert result["skipped"]["command_or_prose"] >= 1
    assert result["skipped"]["logical_uri"] >= 1
    assert result["skipped"]["data_plane"] >= 1
    assert result["skipped"]["repo_local_runtime"] >= 1
    assert result["skipped"]["placeholder"] >= 1


def test_pointer_liveness_directory_pointers_resolve_via_tree(tmp_path: Path):
    repo = _init_repo(tmp_path, route_after=["tools/scanner/"])
    scanner = repo / "tools" / "scanner" / "main.rs"
    scanner.parent.mkdir(parents=True)
    scanner.write_text("fn main() {}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add scanner")

    result = validate_pointer_liveness(repo, mode="both")

    assert result["valid"] is True


def test_pointer_liveness_unparseable_registry(tmp_path: Path):
    repo = _init_repo(tmp_path, route_after=[])
    (repo / "registry" / "ai-navigation-registry.json").write_text(
        "{not json", encoding="utf-8"
    )

    result = validate_pointer_liveness(repo, mode="worktree")

    assert result["valid"] is False
    assert ISSUE_UNPARSEABLE in result["issue_codes"]


def test_pointer_liveness_degrades_without_git(tmp_path: Path):
    repo = tmp_path / "plain"
    (repo / "registry").mkdir(parents=True)
    (repo / "AI_FRONT_DOOR.md").write_text("front door\n", encoding="utf-8")
    (repo / "registry" / "ai-navigation-registry.json").write_text(
        _navigation_registry([]), encoding="utf-8"
    )

    result = validate_pointer_liveness(repo, mode="both")

    assert result["valid"] is True
    assert result["default_branch"] is None
    # Non-git roots (fixtures, exports) skip silently; only a git repo whose
    # observation fails warns.
    assert result["warnings"] == []


def test_pointer_liveness_cli_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path, route_after=["orchestration/TASK_BOARD.jsonl"])
    monkeypatch.setattr(cli, "_cfg", lambda **_kwargs: SimpleNamespace(repo_root=repo))

    result = CliRunner().invoke(cli.app, ["pointer-liveness", "--mode", "both"])

    assert result.exit_code == 2
    assert ISSUE_MISSING_DEFAULT_BRANCH in result.output
