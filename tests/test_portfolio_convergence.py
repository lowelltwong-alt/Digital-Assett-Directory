from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import digital_asset_directory.cli as cli_module
from digital_asset_directory.cli import app
from digital_asset_directory.portfolio_convergence import (
    BranchEvidence,
    PairDistance,
    branch_pair_key,
    finalize_report,
    rank_candidates,
)
from digital_asset_directory.portfolio_convergence_git import (
    _GitCounter,
    _GitObservationError,
    _run_git,
    GitConvergenceSettings,
    build_git_convergence_report,
    validate_convergence_report,
)
from digital_asset_directory.portfolio_os import (
    PortfolioScanSettings,
    build_portfolio_attention_report,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)


def _branch(
    name: str,
    head: str,
    *,
    paths: tuple[str, ...],
    tokens: tuple[str, ...],
) -> BranchEvidence:
    return BranchEvidence(
        project_id="dad:project:test",
        project_name="DAD",
        branch_name=name,
        head=head,
        default_branch="main",
        name_tokens=tokens,
        touched_paths=paths,
    )


def _producer() -> dict[str, object]:
    return {
        "producer_id": "runtime-adapter:git-convergence-readonly",
        "producer_revision_id": "runtime-adapter-revision:git-convergence-readonly:0.2.0",
        "observation_count": 0,
        "source_write_count": 0,
        "bounded": True,
        "problems_recorded": True,
        "details": {
            "git_command_count": 0,
            "git_output_bytes": 0,
            "truncated_command_count": 0,
            "git_timeout_seconds": 20.0,
            "max_projects": 64,
            "max_branches_per_project": 64,
            "max_candidate_distances": 64,
            "max_paths_per_branch": 500,
            "max_git_commands": 512,
            "max_output_bytes_per_command": 1_048_576,
            "max_total_output_bytes": 8_388_608,
            "max_total_seconds": 60.0,
            "git_optional_locks": False,
        },
    }


def _source() -> dict[str, object]:
    return {
        "schema_version": "dad.portfolio_attention.v1",
        "generated_at": NOW.isoformat(),
        "fingerprint": "sha256:" + "a" * 64,
        "project_count": 1,
    }


def test_pure_ranking_is_deterministic_bounded_and_not_authority() -> None:
    left = _branch(
        "codex/cockpit-refresh-a",
        "a" * 40,
        paths=("src/cockpit.py", "tests/test_cockpit.py"),
        tokens=("cockpit", "refresh"),
    )
    right = _branch(
        "codex/cockpit-refresh-b",
        "b" * 40,
        paths=("src/cockpit.py",),
        tokens=("cockpit", "refresh"),
    )
    unrelated = _branch(
        "codex/mail-doctor",
        "c" * 40,
        paths=("src/mail.py",),
        tokens=("doctor", "mail"),
    )
    distance = PairDistance(
        status="observed",
        merge_base="d" * 40,
        left_commits=2,
        right_commits=3,
    )
    distances = {branch_pair_key(left, right): distance}

    first, coverage = rank_candidates([left, right, unrelated], distances)
    second, _ = rank_candidates([unrelated, right, left], distances)

    assert first == second
    assert coverage == {
        "evaluated_pair_count": 3,
        "qualified_pair_count": 1,
        "suppressed_pair_count": 2,
    }
    assert len(first) == 1
    candidate = first[0]
    assert candidate["evidence"]["shared_touched_paths"] == ["src/cockpit.py"]
    assert candidate["evidence"]["merge_base_distance"] == 5
    assert candidate["score_kind"] == "ordinal_review_priority_not_probability"
    assert candidate["human_decision_required"] is True
    assert candidate["candidate_only"] is True
    assert candidate["execution_authorized"] is False
    assert "requires explicit human approval" in candidate["next_action"]


def test_top_five_limit_and_unknown_distance_are_explicit() -> None:
    branches = [
        _branch(
            f"codex/cockpit-variant-{index}",
            f"{index + 1:040x}",
            paths=("src/cockpit.py",),
            tokens=("cockpit", "variant"),
        )
        for index in range(7)
    ]

    candidates, coverage = rank_candidates(branches, {})

    assert len(candidates) == 5
    assert coverage["evaluated_pair_count"] == 21
    assert coverage["qualified_pair_count"] == 21
    assert all(row["evidence"]["merge_base_status"] == "unknown" for row in candidates)
    assert all("merge_base_distance_not_evaluated" in row["problems"] for row in candidates)


def test_final_report_passes_strict_schema() -> None:
    report = finalize_report(
        generated_at=NOW.isoformat(),
        source=_source(),
        branches=[],
        distances={},
        producer=_producer(),
    )

    validate_convergence_report(ROOT, report)

    assert report["summary"]["proposal_count"] == 0
    assert report["model_call_count"] == 0
    assert report["model_token_count"] == 0
    assert report["execution_authorized"] is False


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _seed_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "DAD Test")
    (repo / "src").mkdir()
    (repo / "src/cockpit.py").write_text("BASE = 1\n", encoding="utf-8")
    _git(repo, "add", "src/cockpit.py")
    _git(repo, "commit", "-m", "base")

    _git(repo, "checkout", "-b", "codex/cockpit-refresh-a")
    (repo / "src/cockpit.py").write_text("A = 1\n", encoding="utf-8")
    _git(repo, "add", "src/cockpit.py")
    _git(repo, "commit", "-m", "refresh cockpit a")

    _git(repo, "checkout", "main")
    _git(repo, "checkout", "-b", "codex/cockpit-refresh-b")
    (repo / "src/cockpit.py").write_text("B = 1\n", encoding="utf-8")
    _git(repo, "add", "src/cockpit.py")
    _git(repo, "commit", "-m", "refresh cockpit b")
    _git(repo, "checkout", "main")


def test_git_adapter_is_read_only_and_collects_all_three_evidence_signals(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _seed_repo(repo)
    attention = build_portfolio_attention_report(
        PortfolioScanSettings(
            roots=(repo,),
            stale_days=3,
            max_depth=1,
            related_limit=0,
        ),
        now=NOW,
    )
    before_status = _git(repo, "status", "--porcelain=v1")
    before_refs = _git(
        repo,
        "for-each-ref",
        "--format=%(refname):%(objectname)",
        "refs/heads",
    )

    report = build_git_convergence_report(
        attention,
        schema_root=ROOT,
        settings=GitConvergenceSettings(),
        now=NOW,
    )

    after_status = _git(repo, "status", "--porcelain=v1")
    after_refs = _git(
        repo,
        "for-each-ref",
        "--format=%(refname):%(objectname)",
        "refs/heads",
    )
    validate_convergence_report(ROOT, report)

    assert before_status == after_status == ""
    assert before_refs == after_refs
    assert report["producer"]["source_write_count"] == 0
    assert report["producer"]["details"]["git_optional_locks"] is False
    assert report["summary"]["proposal_count"] == 1
    proposal = report["proposals"][0]
    assert proposal["evidence"]["shared_name_token_count"] >= 2
    assert proposal["evidence"]["shared_touched_paths"] == ["src/cockpit.py"]
    assert proposal["evidence"]["merge_base_status"] == "observed"
    assert proposal["evidence"]["merge_base_distance"] == 2


def test_git_adapter_rejects_unvalidated_attention_source() -> None:
    with pytest.raises(ValueError, match="not schema-valid"):
        build_git_convergence_report(
            {"schema_version": "dad.portfolio_attention.v1"},
            schema_root=ROOT,
        )


def test_cli_requires_attention_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module, "_cfg", lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path)
    )
    monkeypatch.setattr(cli_module, "_v1_attention_report", lambda _root: None)

    result = CliRunner().invoke(app, ["os", "convergence-radar"])

    assert result.exit_code == 2
    assert "Run 'asset-dir os status' first" in result.stdout


def test_cli_publishes_report_only_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = finalize_report(
        generated_at=NOW.isoformat(),
        source=_source(),
        branches=[],
        distances={},
        producer=_producer(),
    )
    monkeypatch.setattr(
        cli_module, "_cfg", lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path)
    )
    monkeypatch.setattr(cli_module, "_v1_attention_report", lambda _root: {"source": "fixture"})
    monkeypatch.setattr(
        cli_module,
        "build_git_convergence_report",
        lambda *_args, **_kwargs: report,
    )
    monkeypatch.setattr(
        cli_module,
        "write_convergence_report",
        lambda *_args, **_kwargs: {
            "path": "convergence-radar.json",
            "status": "generated_candidate",
            "summary": report["summary"],
            "candidate_only": True,
            "execution_authorized": False,
        },
    )

    result = CliRunner().invoke(app, ["os", "convergence-radar"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["proposals"] == []
    assert payload["candidate_only"] is True
    assert payload["execution_authorized"] is False


def test_git_capture_enforces_command_and_wall_time_budgets() -> None:
    settings = GitConvergenceSettings(
        max_git_commands=1,
        max_output_bytes_per_command=1_024,
        max_total_output_bytes=1_024,
    )
    counter = _GitCounter()
    result = _run_git(
        [sys.executable, "-c", "print(1)"],
        settings=settings,
        counter=counter,
    )
    assert result.returncode == 0
    with pytest.raises(_GitObservationError, match="observation_budget_exhausted"):
        _run_git([sys.executable, "-c", "print(2)"], settings=settings, counter=counter)

    expired = _GitCounter()
    expired.started_at -= 2
    with pytest.raises(_GitObservationError, match="observation_budget_exhausted"):
        _run_git(
            [sys.executable, "-c", "print(3)"],
            settings=GitConvergenceSettings(
                max_total_seconds=1,
                max_output_bytes_per_command=1_024,
                max_total_output_bytes=1_024,
            ),
            counter=expired,
        )


def test_git_capture_stops_at_the_output_byte_limit() -> None:
    counter = _GitCounter()
    settings = GitConvergenceSettings(
        max_output_bytes_per_command=1_024,
        max_total_output_bytes=1_024,
    )
    with pytest.raises(_GitObservationError, match="git_output_truncated"):
        _run_git(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 4096)"],
            settings=settings,
            counter=counter,
        )
    assert counter.output_bytes == 1_024
    assert counter.truncated_command_count == 1
    assert counter.exhausted is True
