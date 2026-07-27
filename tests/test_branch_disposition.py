from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import digital_asset_directory.branch_disposition as branch_disposition_mod
import digital_asset_directory.cli as cli
import digital_asset_directory.pointer_liveness as pointer_liveness_mod
from digital_asset_directory.branch_disposition import (
    ISSUE_ACTIVE_OVERDUE,
    ISSUE_ACTIVE_UNDATED,
    ISSUE_DISPOSITION_STALE,
    ISSUE_INTEGRATE_PENDING,
    ISSUE_REASON_MISSING,
    ISSUE_STRANDED,
    check_branch_dispositions,
)

INCIDENT_BRANCH = "codex/preserve-parallel-orchestration-20260710"
NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)
STALE_DATE = "2026-06-15T00:00:00 +0000"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def _git(repo: Path, *args: str, commit_date: str | None = None) -> None:
    env = {**os.environ, **_GIT_ENV}
    if commit_date:
        env["GIT_AUTHOR_DATE"] = commit_date
        env["GIT_COMMITTER_DATE"] = commit_date
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, env=env
    )


def _repo_with_stale_preserve_branch(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial", commit_date=STALE_DATE)
    _git(repo, "checkout", "-b", INCIDENT_BRANCH)
    board = repo / "orchestration" / "TASK_BOARD.jsonl"
    board.parent.mkdir()
    board.write_text('{"task_id":"T-0001"}\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "checkpoint orchestration", commit_date=STALE_DATE)
    _git(repo, "checkout", "main")
    return repo


def _write_disposition(repo: Path, row: dict) -> None:
    registry = repo / "registry" / "branch-disposition-registry.json"
    registry.parent.mkdir(exist_ok=True)
    registry.write_text(
        json.dumps(
            {"registry_version": "0.1.0", "status": "candidate", "dispositions": [row]}
        ),
        encoding="utf-8",
    )


def test_detects_stranded_preserve_branch_when_undispositioned(tmp_path: Path):
    """THE incident regression: the preserve branch must be flagged."""
    repo = _repo_with_stale_preserve_branch(tmp_path)

    result = check_branch_dispositions(repo, now=NOW)

    assert result["valid"] is False
    assert result["scoped_branch_count"] == 1
    assert ISSUE_STRANDED in result["issue_codes"]
    assert any(INCIDENT_BRANCH in error for error in result["errors"])
    finding = result["findings"][0]
    assert finding["branch"] == INCIDENT_BRANCH
    assert finding["status"] == ISSUE_STRANDED


def test_tombstone_with_reason_clears_and_empty_reason_fails(tmp_path: Path):
    repo = _repo_with_stale_preserve_branch(tmp_path)
    _write_disposition(
        repo,
        {
            "branch": INCIDENT_BRANCH,
            "disposition": "tombstone",
            "reason": "Quarantined draft; content re-landed via PR #999.",
            "decided_by": "Lowell",
            "decided_at": "2026-07-27",
        },
    )
    cleared = check_branch_dispositions(repo, now=NOW)
    assert cleared["valid"] is True
    assert cleared["scoped_branch_count"] == 1

    _write_disposition(
        repo,
        {
            "branch": INCIDENT_BRANCH,
            "disposition": "tombstone",
            "reason": "   ",
            "decided_by": "Lowell",
            "decided_at": "2026-07-27",
        },
    )
    rejected = check_branch_dispositions(repo, now=NOW)
    assert rejected["valid"] is False
    assert ISSUE_REASON_MISSING in rejected["issue_codes"]
    # An unexplained disposition does not clear the underlying finding.
    assert ISSUE_STRANDED in rejected["issue_codes"]


def test_integrate_keeps_blocking_until_reachable_from_default(tmp_path: Path):
    repo = _repo_with_stale_preserve_branch(tmp_path)
    _write_disposition(
        repo,
        {
            "branch": INCIDENT_BRANCH,
            "disposition": "integrate",
            "reason": "Orchestration layer must land on main.",
            "decided_by": "Lowell",
            "decided_at": "2026-07-27",
        },
    )
    pending = check_branch_dispositions(repo, now=NOW)
    assert pending["valid"] is False
    assert ISSUE_INTEGRATE_PENDING in pending["issue_codes"]

    _git(repo, "merge", "--no-ff", "-m", "integrate orchestration", INCIDENT_BRANCH)
    integrated = check_branch_dispositions(repo, now=NOW)
    assert integrated["valid"] is True
    assert integrated["scoped_branch_count"] == 0


def test_active_respects_review_after(tmp_path: Path):
    repo = _repo_with_stale_preserve_branch(tmp_path)
    base_row = {
        "branch": INCIDENT_BRANCH,
        "disposition": "active",
        "reason": "Still being reworked on the branch.",
        "decided_by": "Lowell",
        "decided_at": "2026-07-20",
    }

    _write_disposition(repo, {**base_row, "review_after": "2026-08-26"})
    assert check_branch_dispositions(repo, now=NOW)["valid"] is True

    _write_disposition(repo, {**base_row, "review_after": "2026-07-01"})
    overdue = check_branch_dispositions(repo, now=NOW)
    assert overdue["valid"] is False
    assert ISSUE_ACTIVE_OVERDUE in overdue["issue_codes"]

    _write_disposition(repo, base_row)
    undated = check_branch_dispositions(repo, now=NOW)
    assert undated["valid"] is False
    assert ISSUE_ACTIVE_UNDATED in undated["issue_codes"]


def test_fresh_or_merged_branches_are_not_scoped(tmp_path: Path):
    repo = _repo_with_stale_preserve_branch(tmp_path)
    _git(repo, "checkout", "-b", "wip/fresh-work")
    (repo / "fresh.md").write_text("fresh\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "fresh", commit_date="2026-07-26T00:00:00 +0000")
    _git(repo, "checkout", "main")

    result = check_branch_dispositions(repo, now=NOW)

    scoped_names = {finding["branch"] for finding in result["findings"]}
    assert scoped_names == {INCIDENT_BRANCH}


def test_check_is_read_only_by_construction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every git call the check makes must use an allowlisted read-only subcommand."""
    repo = _repo_with_stale_preserve_branch(tmp_path)
    observed: list[tuple[str, ...]] = []

    real = branch_disposition_mod._git_worktree

    def spy(**kwargs):
        observed.append(tuple(kwargs["args"]))
        return real(**kwargs)

    monkeypatch.setattr(branch_disposition_mod, "_git_worktree", spy)
    monkeypatch.setattr(pointer_liveness_mod, "_git_worktree", spy)

    check_branch_dispositions(repo, now=NOW, include_sensitive_diff_scope=True)

    read_only = {
        "for-each-ref", "rev-parse", "diff", "rev-list",
        "show-ref", "symbolic-ref", "ls-tree", "ls-files",
    }
    assert observed, "check made no git observations"
    assert {args[0] for args in observed} <= read_only

    with pytest.raises(ValueError):
        branch_disposition_mod._read_only_git(
            repo,
            ("push", "origin", "main"),
            settings=branch_disposition_mod.GitConvergenceSettings(),
            counter=branch_disposition_mod._GitCounter(),
        )


def test_degrades_without_git(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()

    result = check_branch_dispositions(plain, now=NOW)

    assert result["valid"] is True
    assert result["default_branch"] is None
    # Non-git roots (fixtures, exports) skip silently; only a git repo whose
    # observation fails warns.
    assert result["warnings"] == []


def test_branch_disposition_cli_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _repo_with_stale_preserve_branch(tmp_path)
    monkeypatch.setattr(cli, "_cfg", lambda **_kwargs: SimpleNamespace(repo_root=repo))

    result = CliRunner().invoke(cli.app, ["branch-disposition"])

    assert result.exit_code == 2
    assert ISSUE_STRANDED in result.output


def _tip_sha(repo: Path, ref: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", ref],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
    )
    return out.stdout.strip()


def test_disposition_goes_stale_when_tip_moves(tmp_path: Path):
    """The commit field is load-bearing: a disposition applies to the recorded
    tip. New commits on a tombstoned branch re-raise the finding — otherwise
    'tombstone once, keep committing' hides new work, which is the original
    incident with paperwork."""
    repo = _repo_with_stale_preserve_branch(tmp_path)
    decided_tip = _tip_sha(repo, INCIDENT_BRANCH)
    _write_disposition(
        repo,
        {
            "branch": INCIDENT_BRANCH,
            "commit": decided_tip,
            "disposition": "tombstone",
            "reason": "quarantined checkpoint; content superseded",
            "decided_by": "Fixture Human",
            "decided_at": "2026-07-26",
        },
    )
    clean = check_branch_dispositions(repo, now=NOW)
    assert clean["valid"], clean["errors"]

    _git(repo, "checkout", INCIDENT_BRANCH)
    extra = repo / "orchestration" / "EXTRA.md"
    extra.write_text("new work after the decision\n", encoding="utf-8")
    # Add only the new file: `add -A` would sweep the (deliberately untracked)
    # disposition registry into the branch commit and lose it on checkout.
    _git(repo, "add", "orchestration/EXTRA.md")
    _git(repo, "commit", "-m", "more work after tombstone", commit_date=STALE_DATE)
    _git(repo, "checkout", "main")

    result = check_branch_dispositions(repo, now=NOW)

    assert not result["valid"]
    assert ISSUE_DISPOSITION_STALE in result["issue_codes"]
    assert any(ISSUE_DISPOSITION_STALE in error for error in result["errors"])


def test_disposition_short_commit_prefix_matches(tmp_path: Path):
    repo = _repo_with_stale_preserve_branch(tmp_path)
    decided_tip = _tip_sha(repo, INCIDENT_BRANCH)
    _write_disposition(
        repo,
        {
            "branch": INCIDENT_BRANCH,
            "commit": decided_tip[:7],
            "disposition": "tombstone",
            "reason": "quarantined checkpoint; content superseded",
            "decided_by": "Fixture Human",
            "decided_at": "2026-07-26",
        },
    )

    result = check_branch_dispositions(repo, now=NOW)

    assert result["valid"], result["errors"]
