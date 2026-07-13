from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess

from jsonschema.validators import validator_for
from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory import portfolio_os
from digital_asset_directory.portfolio_os import (
    PortfolioScanSettings,
    build_portfolio_attention_report,
    portfolio_attention_html,
    write_portfolio_attention_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = CliRunner()


def run_git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return result.stdout.strip()


def init_repo(path: Path, *, initial_date: str = "2026-07-01T12:00:00+00:00") -> Path:
    path.mkdir(parents=True)
    run_git(path, "init", "-b", "main")
    run_git(path, "config", "user.email", "dad-test@example.invalid")
    run_git(path, "config", "user.name", "DAD Test")
    (path / "README.md").write_text(f"# {path.name}\n", encoding="utf-8")
    run_git(path, "add", "README.md")
    run_git(
        path,
        "commit",
        "-m",
        "Initial project",
        env={"GIT_AUTHOR_DATE": initial_date, "GIT_COMMITTER_DATE": initial_date},
    )
    return path


def test_git_scanner_disables_optional_locks(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(portfolio_os.subprocess, "run", fake_run)

    result = portfolio_os._run_git_bytes(Path("C:/synthetic/repo"), ["status"])

    assert result.returncode == 0
    assert captured["command"] == [
        "git",
        "-C",
        str(Path("C:/synthetic/repo")),
        "-c",
        "core.quotepath=false",
        "status",
    ]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["GIT_OPTIONAL_LOCKS"] == "0"


def test_report_groups_worktrees_and_flags_forgotten_dirty_branch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "creative-os")
    run_git(repo, "switch", "-c", "forgotten-idea")
    (repo / "idea.txt").write_text("candidate\n", encoding="utf-8")
    run_git(repo, "add", "idea.txt")
    run_git(
        repo,
        "commit",
        "-m",
        "Prototype attention memory",
        env={
            "GIT_AUTHOR_DATE": "2026-07-02T12:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-07-02T12:00:00+00:00",
        },
    )
    run_git(repo, "switch", "main")
    worktree = tmp_path / "creative-os-forgotten"
    run_git(repo, "worktree", "add", str(worktree), "forgotten-idea")
    dirty = worktree / "unfinished.txt"
    dirty.write_text("unfinished\n", encoding="utf-8")
    old_activity = datetime(2026, 7, 5, 12, tzinfo=timezone.utc).timestamp()
    os.utime(dirty, (old_activity, old_activity))
    (repo / "active.txt").write_text("active\n", encoding="utf-8")
    run_git(repo, "add", "active.txt")
    run_git(
        repo,
        "commit",
        "-m",
        "Continue active project",
        env={
            "GIT_AUTHOR_DATE": "2026-07-10T12:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-07-10T12:00:00+00:00",
        },
    )
    before = run_git(worktree, "status", "--porcelain=v1")

    report = build_portfolio_attention_report(
        PortfolioScanSettings(roots=(tmp_path,), stale_days=3, max_depth=2),
        now=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )

    assert report["summary"]["project_count"] == 1
    assert report["summary"]["worktree_count"] == 2
    assert report["summary"]["dirty_worktree_count"] == 1
    forgotten = next(
        item for item in report["attention_queue"] if item["branch"] == "forgotten-idea"
    )
    assert "dirty_worktree_idle" in forgotten["reasons"]
    assert "stale_branch_in_active_project" in forgotten["reasons"]
    assert forgotten["worktree_path"] == str(worktree.resolve())
    assert run_git(worktree, "status", "--porcelain=v1") == before


def test_report_matches_registered_schema_and_writes_local_html(tmp_path: Path) -> None:
    init_repo(tmp_path / "portfolio" / "alpha-project")
    report = build_portfolio_attention_report(
        PortfolioScanSettings(roots=(tmp_path / "portfolio",), max_depth=2),
        now=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )
    schema = json.loads(
        (ROOT / "schemas" / "portfolio-attention-report.schema.json").read_text(encoding="utf-8")
    )
    validator = validator_for(schema)(schema, format_checker=validator_for(schema).FORMAT_CHECKER)
    assert list(validator.iter_errors(report)) == []
    malformed = deepcopy(report)
    malformed["projects"][0]["branches"] = [{"garbage": True}]
    assert list(validator.iter_errors(malformed))

    hub = tmp_path / "hub"
    outputs = write_portfolio_attention_outputs(hub, report)
    json_path = Path(outputs["json_path"])
    html_path = Path(outputs["html_path"])
    assert json_path.exists()
    assert html_path.exists()
    assert (
        json.loads(json_path.read_text(encoding="utf-8"))["schema_version"]
        == report["schema_version"]
    )
    assert "What needs your attention?" in html_path.read_text(encoding="utf-8")


def test_discovery_excludes_repo_local_tmp_git_fixtures(tmp_path: Path) -> None:
    visible = tmp_path / "visible-project"
    synthetic = tmp_path / ".tmp" / "synthetic-project"
    (visible / ".git").mkdir(parents=True)
    (synthetic / ".git").mkdir(parents=True)

    discovered, errors = portfolio_os.discover_git_checkouts([tmp_path], max_depth=5)

    assert errors == []
    assert discovered == [visible.resolve()]


def test_explicit_aggregate_git_root_still_discovers_nested_projects(tmp_path: Path) -> None:
    portfolio = init_repo(tmp_path / "git-projects")
    init_repo(portfolio / "family" / "nested-project")

    report = build_portfolio_attention_report(
        PortfolioScanSettings(roots=(portfolio,), max_depth=3),
        now=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )

    assert {project["name"] for project in report["projects"]} == {
        "git-projects",
        "nested-project",
    }


def test_related_project_candidates_require_explainable_shared_metadata(tmp_path: Path) -> None:
    portfolio = tmp_path / "portfolio"
    init_repo(portfolio / "lawfirm-os-intake")
    init_repo(portfolio / "lawfirm-os-orchestrator")
    init_repo(portfolio / "unrelated-garden")

    report = build_portfolio_attention_report(
        PortfolioScanSettings(roots=(portfolio,), max_depth=2, related_limit=3),
        now=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )
    by_name = {project["name"]: project for project in report["projects"]}
    related = by_name["lawfirm-os-intake"]["related_projects"]
    assert [item["project_name"] for item in related] == ["lawfirm-os-orchestrator"]
    assert {"lawfirm", "os"}.issubset(set(related[0]["shared_metadata_tokens"]))
    assert by_name["unrelated-garden"]["related_projects"] == []


def test_remote_userinfo_is_removed_from_report(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "safe-remote")
    secret = "SYNTHETIC_PAT_DO_NOT_STORE"
    run_git(repo, "remote", "add", "origin", f"https://user:{secret}@example.invalid/team/repo.git")

    report = build_portfolio_attention_report(
        PortfolioScanSettings(roots=(repo,), max_depth=1),
        now=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )

    serialized = json.dumps(report)
    assert secret not in serialized
    assert "user:" not in serialized
    assert report["projects"][0]["remote_url"] == "https://example.invalid/team/repo.git"
    cases = {
        "https://user:token@example.invalid/team/repo.git?auth=query#fragment": (
            "https://example.invalid/team/repo.git"
        ),
        "https://user:token@example.invalid:notaport/team/repo.git": (
            "https://example.invalid:notaport/team/repo.git"
        ),
        "SYNTHETIC_TOKEN@host.invalid:org/repo.git": "host.invalid:org/repo.git",
    }
    for candidate, expected in cases.items():
        assert portfolio_os._sanitize_remote_url(candidate) == expected
        assert "token" not in portfolio_os._sanitize_remote_url(candidate).casefold()
        assert "query" not in portfolio_os._sanitize_remote_url(candidate).casefold()
        assert "fragment" not in portfolio_os._sanitize_remote_url(candidate).casefold()


def test_unknown_worktree_status_is_error_and_attention(tmp_path: Path, monkeypatch) -> None:
    repo = init_repo(tmp_path / "status-unknown")
    original = portfolio_os._worktree_state

    def unknown_status(record):
        state = original(record)
        state.update(
            {
                "status_known": False,
                "dirty": None,
                "status_error": "synthetic status failure",
            }
        )
        return state

    monkeypatch.setattr(portfolio_os, "_worktree_state", unknown_status)
    report = build_portfolio_attention_report(
        PortfolioScanSettings(roots=(repo,), max_depth=1),
        now=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )

    assert report["projects"][0]["worktrees"][0]["dirty"] is None
    assert any("git_status_failed" in item["error"] for item in report["scan"]["errors"])
    branch_item = next(item for item in report["attention_queue"] if item["branch"] == "main")
    assert branch_item["reasons"] == ["worktree_status_unknown"]
    assert branch_item["evidence"]["dirty"] is None
    assert branch_item["evidence"]["worktree_locked"] is False


def test_html_escapes_local_metadata() -> None:
    report = {
        "generated_at": "2026-07-11T12:00:00+00:00",
        "summary": {
            "project_count": 1,
            "branch_count": 1,
            "worktree_count": 1,
            "dirty_worktree_count": 1,
            "attention_item_count": 1,
        },
        "today": [
            {
                "priority": 95,
                "project_name": "<script>alert(1)</script>",
                "branch": "unsafe&branch",
                "reasons": ["dirty_worktree_idle"],
                "next_action": "Review <now>",
                "worktree_path": "C:/private&path",
            }
        ],
        "attention_queue": [
            {
                "priority": 95,
                "project_name": "<script>alert(1)</script>",
                "branch": "unsafe&branch",
                "reasons": ["dirty_worktree_idle"],
                "next_action": "Review <now>",
                "worktree_path": "C:/private&path",
                "inactive_days": 4,
            }
        ],
        "projects": [
            {
                "name": "<script>alert(1)</script>",
                "branches": [{}],
                "worktrees": [{}],
                "default_branch": "main",
                "related_projects": [],
            }
        ],
        "authority_boundary": "candidate only",
    }
    rendered = portfolio_attention_html(report)
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "unsafe&amp;branch" in rendered
    assert "querySelectorAll('#queue-body [data-search]')" in rendered


def test_os_command_is_discoverable() -> None:
    result = RUNNER.invoke(app, ["os", "--help"])
    assert result.exit_code == 0
    assert "status" in result.output
