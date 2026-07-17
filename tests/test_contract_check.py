from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest
from typer.testing import CliRunner

from digital_asset_directory import cli
from digital_asset_directory.contract_check import (
    ContractCheckInfrastructureError,
    classify_paths,
    effective_mode,
    load_policy,
    protected_path_specs,
    render_text,
    resolve_base,
    run_contract_check,
)

ROOT = Path(__file__).resolve().parents[1]

POLICY = {
    "schema_version": "0.1.0",
    "policy_id": "test-contract-check",
    "mode": "warn",
    "authority_boundary": "test",
    "protected_paths_source": ".ci/module-boundaries.yaml",
    "extra_protected_globs": [".githooks/**"],
    "exempt_globs": ["processed/**"],
    "trailer_key": "DAD-Session",
    "trailer_pattern": "^dad:session:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    "bypass_key": "DAD-Bypass",
    "bypass_pattern": "^[^:]+:\\s*\\S.+$",
    "remediation": "run preflight/postflight and add the trailer",
    "probation": {
        "owner": "test",
        "started": "2026-07-17",
        "review_after": "2026-08-14",
        "promotion_criteria": "test",
        "kill_criteria": "test",
    },
}

MANIFEST = """
modules:
  - module_id: python
    roots: [src, tests, pyproject.toml]
  - module_id: governance
    roots: [registry, schemas]
workflow_paths: [.github/workflows/**]
"""

VALID_SESSION = "dad:session:0f0e0d0c-0b0a-4213-8888-777766665555"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout


def _hub_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "registry").mkdir(parents=True)
    (repo / ".ci").mkdir()
    (repo / "registry" / "contract-check-policy.json").write_text(
        json.dumps(POLICY), encoding="utf-8"
    )
    (repo / ".ci" / "module-boundaries.yaml").write_text(MANIFEST, encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Contract Check Test")
    _git(repo, "config", "core.hooksPath", ".git/no-hooks")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def _commit(repo: Path, relpath: str, message: str) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("content\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _set_policy_mode(repo: Path, mode: str) -> None:
    path = repo / "registry" / "contract-check-policy.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["mode"] = mode
    path.write_text(json.dumps(policy), encoding="utf-8")


def _run_standalone(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    mode: str = "policy",
) -> tuple[int, str]:
    spec = importlib.util.spec_from_file_location(
        "dad_contract_check_runner_test", ROOT / "scripts" / "contract_check.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "contract_check.py",
            "--hub",
            str(repo),
            "--repo",
            str(repo),
            "--mode",
            mode,
        ],
    )
    return int(module.main()), capsys.readouterr().out


def test_cold_agent_protected_change_without_trailer_is_violation(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "src/thing.py", "cold agent change with no lifecycle trace")
    report = run_contract_check(repo, repo, base)
    assert report["status"] == "violation"
    assert report["violation"] is True
    assert report["protected_paths"] == ["src/thing.py"]
    assert "remediation" in report
    assert "preflight" in render_text(report)


def test_trailer_in_commit_message_clears_check(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "registry/x.json", f"governed change\n\nDAD-Session: {VALID_SESSION}")
    report = run_contract_check(repo, repo, base)
    assert report["status"] == "traced"
    assert report["session_trailers"] == [VALID_SESSION]
    assert report["violation"] is False


def test_unprotected_change_is_not_applicable(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "notes/idea.md", "free-form notes")
    report = run_contract_check(repo, repo, base)
    assert report["status"] == "not_applicable"
    assert report["violation"] is False


def test_exempt_glob_wins_over_protected_spec(tmp_path: Path) -> None:
    protected, unprotected = classify_paths(
        ["processed/reports/out.json", "src/a.py"],
        ["src", "processed"],
        ["processed/**"],
    )
    assert protected == ["src/a.py"]
    assert unprotected == ["processed/reports/out.json"]


def test_bypass_trailer_is_allowed_and_flagged(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "src/hotfix.py", "emergency\n\nDAD-Bypass: lowell: prod incident 42")
    report = run_contract_check(repo, repo, base)
    assert report["status"] == "bypassed"
    assert report["bypass_used"] is True
    assert report["violation"] is False


def test_malformed_trailer_is_still_a_violation(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "src/thing.py", "sloppy\n\nDAD-Session: not-a-real-session-id")
    report = run_contract_check(repo, repo, base)
    assert report["status"] == "violation"
    assert report["malformed_session_trailers"] == ["not-a-real-session-id"]


def test_pr_body_extra_text_supplies_trailer(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "schemas/x.schema.json", "change whose trailer lives in the PR body")
    report = run_contract_check(
        repo, repo, base, extra_text=f"summary\n\nDAD-Session: {VALID_SESSION}"
    )
    assert report["status"] == "traced"


def test_enforce_mode_flag_overrides_policy(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "src/thing.py", "no trace")
    report = run_contract_check(repo, repo, base, mode="enforce")
    assert report["mode"] == "enforce"
    assert report["violation"] is True


def test_effective_mode_resolves_policy_and_explicit_override() -> None:
    assert effective_mode({"mode": "enforce"}, "policy") == "enforce"
    assert effective_mode({"mode": "warn"}, None) == "warn"
    assert effective_mode({"mode": "enforce"}, "warn") == "warn"
    with pytest.raises(ContractCheckInfrastructureError, match="Unsupported"):
        effective_mode({"mode": "invalid"}, "policy")


def test_resolve_base_uses_configured_non_origin_upstream(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "src/change.py", "change after upstream")
    _git(repo, "remote", "add", "central", "https://example.invalid/repo.git")
    _git(repo, "update-ref", "refs/remotes/central/trunk", base)
    _git(repo, "config", "branch.main.remote", "central")
    _git(repo, "config", "branch.main.merge", "refs/heads/trunk")

    assert resolve_base(repo) == base


def test_resolve_base_uses_single_recorded_remote_head(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "src/change.py", "change after remote default")
    _git(repo, "remote", "add", "source", "https://example.invalid/repo.git")
    _git(repo, "update-ref", "refs/remotes/source/trunk", base)
    _git(
        repo,
        "symbolic-ref",
        "refs/remotes/source/HEAD",
        "refs/remotes/source/trunk",
    )

    assert resolve_base(repo) == base


def test_resolve_base_never_guesses_origin_main(tmp_path: Path) -> None:
    repo = _hub_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", base)

    with pytest.raises(ContractCheckInfrastructureError, match="--base"):
        resolve_base(repo)


def test_policy_enforce_runner_fails_closed_on_base_resolution_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _hub_repo(tmp_path)
    _set_policy_mode(repo, "enforce")

    exit_code, output = _run_standalone(repo, monkeypatch, capsys)

    assert exit_code == 2
    assert "failed to run in enforce mode" in output
    assert "--base" in output


def test_policy_warn_runner_does_not_block_on_base_resolution_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _hub_repo(tmp_path)

    exit_code, output = _run_standalone(repo, monkeypatch, capsys)

    assert exit_code == 0
    assert "not blocking during probation" in output
    assert "--base" in output


def test_policy_runner_fails_closed_when_policy_cannot_be_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _hub_repo(tmp_path)
    (repo / "registry" / "contract-check-policy.json").unlink()

    exit_code, output = _run_standalone(repo, monkeypatch, capsys)

    assert exit_code == 2
    assert "failed to run in enforce mode" in output


def test_explicit_warn_runner_does_not_block_when_policy_cannot_be_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _hub_repo(tmp_path)
    (repo / "registry" / "contract-check-policy.json").unlink()

    exit_code, output = _run_standalone(
        repo, monkeypatch, capsys, mode="warn"
    )

    assert exit_code == 0
    assert "not blocking during probation" in output


@pytest.mark.parametrize(("policy_mode", "expected_exit"), [("warn", 0), ("enforce", 2)])
def test_cli_uses_effective_policy_mode_for_base_resolution_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy_mode: str,
    expected_exit: int,
) -> None:
    repo = _hub_repo(tmp_path)
    _set_policy_mode(repo, policy_mode)
    monkeypatch.setattr(cli, "_cfg", lambda **_kwargs: SimpleNamespace(repo_root=repo))

    result = CliRunner().invoke(
        cli.app,
        ["agent", "contract-check", "--repo", str(repo)],
    )

    assert result.exit_code == expected_exit
    assert "--base" in result.output
    if policy_mode == "warn":
        assert "not blocking in effective warn mode" in result.output
    else:
        assert "failed to run in enforce mode" in result.output


@pytest.mark.parametrize(
    ("requested_mode", "remove_policy", "expected_fragment"),
    [
        ("banana", False, "Unsupported contract-check mode"),
        ("policy", True, "contract-check-policy.json"),
    ],
)
def test_cli_fails_closed_before_effective_policy_mode_is_known(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requested_mode: str,
    remove_policy: bool,
    expected_fragment: str,
) -> None:
    repo = _hub_repo(tmp_path)
    if remove_policy:
        (repo / "registry" / "contract-check-policy.json").unlink()
    monkeypatch.setattr(cli, "_cfg", lambda **_kwargs: SimpleNamespace(repo_root=repo))

    result = CliRunner().invoke(
        cli.app,
        [
            "agent",
            "contract-check",
            "--repo",
            str(repo),
            "--mode",
            requested_mode,
        ],
    )

    assert result.exit_code == 2
    normalized_output = " ".join(result.output.split())
    assert "failed to run in enforce mode" in normalized_output
    # Rich may wrap long paths inside a token at different terminal widths.
    compact_output = "".join(result.output.split())
    assert "".join(expected_fragment.split()) in compact_output


def test_cli_explicit_warn_does_not_block_when_policy_cannot_be_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _hub_repo(tmp_path)
    (repo / "registry" / "contract-check-policy.json").unlink()
    monkeypatch.setattr(cli, "_cfg", lambda **_kwargs: SimpleNamespace(repo_root=repo))

    result = CliRunner().invoke(
        cli.app,
        [
            "agent",
            "contract-check",
            "--repo",
            str(repo),
            "--mode",
            "warn",
        ],
    )

    assert result.exit_code == 0
    assert "not blocking in effective warn mode" in result.output


def test_shipped_policy_validates_against_schema() -> None:
    policy = json.loads(
        (ROOT / "registry" / "contract-check-policy.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (ROOT / "schemas" / "contract-check-policy.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(policy, schema)
    assert policy["mode"] == "warn", "probation must start warn-only"


def test_shipped_protected_specs_cover_core_surfaces() -> None:
    policy = load_policy(ROOT)
    specs = protected_path_specs(ROOT, policy)
    for expected in ("src", "tests", "registry", "schemas", ".githooks/**", ".github/**"):
        assert expected in specs, f"missing protected spec {expected}"
