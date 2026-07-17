from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema

from digital_asset_directory.contract_check import (
    classify_paths,
    load_policy,
    protected_path_specs,
    render_text,
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
