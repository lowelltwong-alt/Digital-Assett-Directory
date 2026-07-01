from __future__ import annotations

import json
import subprocess
from pathlib import Path

from jsonschema.validators import validator_for
import pytest
import yaml

from digital_asset_directory.config import AppConfig, EnrollmentRepoPolicy, Settings
from digital_asset_directory.enrollment import (
    APPROVED_RELATIVE_PATHS,
    apply_enrollment,
    build_enrollment_plan,
    enrollment_status,
    select_enrollment_policies,
)
from digital_asset_directory.mail_center import compose_mail

ROOT = Path(__file__).resolve().parents[1]


def _policy(
    repo: Path,
    repo_id: str = "repo-a",
    *,
    visibility: str = "internal",
    public_facing: bool = False,
    wave: str = "wave-a",
    apply_allowed: bool = True,
    update_allowed: bool = True,
    approval_ids: list[str] | None = None,
    local_paths_allowed: bool = False,
    active_hold: bool = False,
    active_hold_reason: str = "",
    allow_dirty_worktree: bool = False,
    allow_non_main_branch: bool = False,
) -> EnrollmentRepoPolicy:
    return EnrollmentRepoPolicy(
        id=repo_id,
        path=repo,
        alias=repo_id,
        visibility=visibility,
        public_facing=public_facing,
        enrollment_enabled=True,
        apply_allowed=apply_allowed,
        update_allowed=update_allowed,
        active_hold=active_hold,
        active_hold_reason=active_hold_reason,
        allow_dirty_worktree=allow_dirty_worktree,
        allow_non_main_branch=allow_non_main_branch,
        wave=wave,
        approved_approval_ids=approval_ids or ["APPROVED-1"],
        local_paths_allowed=local_paths_allowed,
        repo_type="application",
        languages=["python"],
        domains=["test"],
        context_tags=["persistent_repo"],
        validation_commands=["python -m pytest"],
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _cfg(hub: Path, policies: list[EnrollmentRepoPolicy]) -> AppConfig:
    return AppConfig(
        repo_root=hub,
        raw={},
        database_path=hub / "state" / "catalog.sqlite3",
        local_sources=[],
        github_sources=[],
        settings=Settings(),
        enrollment_repos=policies,
    )


def _load_schema(name: str) -> dict:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    return json.loads((ROOT / registry["schemas"][name]).read_text())


def _validate(schema_name: str, payload: dict) -> None:
    schema = _load_schema(schema_name)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _all_files(repo: Path) -> set[str]:
    return {
        path.relative_to(repo).as_posix()
        for path in repo.rglob("*")
        if path.is_file()
    }


def test_enrollment_schema_registry_and_control_plane_registry_conform():
    expected = {
        "repo_enrollment_contract": "schemas/repo-enrollment-contract.schema.json",
        "repo_enrollment_policy": "schemas/repo-enrollment-policy.schema.json",
        "repo_context_map": "schemas/repo-context-map.schema.json",
        "control_plane_registry": "schemas/control-plane-registry.schema.json",
        "governance_map_adoption": "schemas/governance-map-adoption.schema.json",
        "data_map_adoption": "schemas/data-map-adoption.schema.json",
    }
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    for key, rel in expected.items():
        assert registry["schemas"][key] == rel
        validator_for(_load_schema(key)).check_schema(_load_schema(key))

    payload = json.loads((ROOT / "registry" / "control-plane-registry.json").read_text())
    _validate("control_plane_registry", payload)
    plane_ids = [item["control_plane_id"] for item in payload["control_planes"]]
    assert len(plane_ids) == len(set(plane_ids))
    assert "mail_center" in plane_ids


def test_repo_all_requires_reviewed_wave_and_policy(tmp_path: Path):
    hub = tmp_path / "hub"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    cfg = _cfg(
        hub,
        [
            _policy(repo_a, "repo-a", wave="wave-a"),
            _policy(repo_b, "repo-b", wave="wave-b"),
        ],
    )

    with pytest.raises(ValueError, match="requires --wave"):
        select_enrollment_policies(["all"], cfg)

    selected = select_enrollment_policies(["all"], cfg, wave="wave-a")
    assert [policy.id for policy in selected] == ["repo-a"]

    with pytest.raises(ValueError, match="reviewed enrollment.repos"):
        select_enrollment_policies([str(tmp_path / "stray")], cfg)


def test_plan_writes_only_central_reports_and_no_target_files(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)

    result = build_enrollment_plan(hub, [policy], wave="wave-a")

    assert (hub / result["plan_path"]).exists()
    assert (hub / result["plan_markdown_path"]).exists()
    assert not (repo / ".digital-asset").exists()
    assert result["items"][0]["hook_install_disclosed"] is True
    assert result["items"][0]["normal_operation_write_boundary"] == ".digital-asset/mail/**"


def test_apply_requires_approval_and_writes_only_approved_paths(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    (repo / "AGENTS.md").write_text("# Local Rules\n\nKeep this line.\n", encoding="utf-8")
    policy = _policy(repo)

    with pytest.raises(ValueError, match="Approval ID"):
        apply_enrollment(hub, policy, approval_id="WRONG")

    before = _all_files(repo)
    result = apply_enrollment(hub, policy, approval_id="APPROVED-1")
    after = _all_files(repo)
    created = after - before

    assert set(result["changed_paths"]) <= set(APPROVED_RELATIVE_PATHS)
    assert created <= set(APPROVED_RELATIVE_PATHS)
    assert "Keep this line." in (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert result["hook_install_disclosed"] is True
    assert (repo / ".githooks" / "pre-push").exists()
    assert (hub / "processed" / "enrollment" / "audit.jsonl").exists()

    contract = json.loads((repo / ".digital-asset" / "dad-integration.json").read_text())
    context_map = json.loads((repo / ".digital-asset" / "context-map.json").read_text())
    governance_map = yaml.safe_load((repo / ".digital-asset" / "governance-map.yaml").read_text())
    data_map = yaml.safe_load((repo / ".digital-asset" / "data-map.yaml").read_text())
    _validate("repo_enrollment_contract", contract)
    _validate("repo_context_map", context_map)
    _validate("governance_map_adoption", governance_map)
    _validate("data_map_adoption", data_map)
    assert contract["enrollment"]["normal_write_boundary"] == ".digital-asset/mail/**"
    assert "software-work-preflight" in {route["route_id"] for route in context_map["routes"]}


def test_apply_fails_closed_when_policy_path_does_not_exist(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    missing_repo = tmp_path / "missing-repo"
    policy = _policy(missing_repo)

    with pytest.raises(ValueError, match="does not exist"):
        apply_enrollment(hub, policy, approval_id="APPROVED-1")

    assert not missing_repo.exists()
    audit_rows = [
        json.loads(line)
        for line in (hub / "processed" / "enrollment" / "audit.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert audit_rows[-1]["event_type"] == "failed"


def test_update_apply_is_idempotent(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)

    first = apply_enrollment(hub, policy, approval_id="APPROVED-1")
    second = apply_enrollment(hub, policy, approval_id="APPROVED-1")
    update = apply_enrollment(hub, policy, approval_id="APPROVED-1", update=True)

    assert first["changed_count"] > 0
    assert second["changed_paths"] == []
    assert update["changed_paths"] == [
        ".digital-asset/dad-integration.json",
    ]


def test_public_facing_enrollment_omits_local_absolute_paths(tmp_path: Path):
    hub = tmp_path / "hub with spaces"
    repo = tmp_path / "public repo"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(
        repo,
        "public-repo",
        visibility="public",
        public_facing=True,
        local_paths_allowed=False,
    )

    result = apply_enrollment(hub, policy, approval_id="APPROVED-1")

    serialized_result = json.dumps(result)
    assert str(tmp_path).replace("\\", "/") not in serialized_result.replace("\\", "/")
    for rel in result["changed_paths"]:
        text = (repo / rel).read_text(encoding="utf-8")
        assert str(tmp_path).replace("\\", "/") not in text.replace("\\", "/")
    contract = json.loads((repo / ".digital-asset" / "dad-integration.json").read_text())
    assert contract["dad_hub"]["hub_ref"] == "dad://hub/Digital-Assett-Directory"
    assert "repo_path" not in contract
    assert contract["return_address"].startswith("dad://repo/public-repo/")


def test_daily_mail_operation_writes_only_mailbox_after_enrollment(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)
    apply_enrollment(hub, policy, approval_id="APPROVED-1")
    before = _all_files(repo)

    compose_mail(
        repo,
        message_type="lesson_suggestion",
        target_repo="central_only",
        summary="Candidate daily mail note.",
    )
    after = _all_files(repo)
    touched_or_created = after - before

    assert touched_or_created <= {".digital-asset/mail/outbox.jsonl"}
    status = enrollment_status(policy)
    assert status["mail_digest"]["status"] == "missing"


def test_copied_contract_keeps_repo_id_but_split_requires_policy(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    split = tmp_path / "repo-a-split"
    hub.mkdir()
    repo.mkdir()
    split.mkdir()
    policy = _policy(repo, "stable-repo-id")
    cfg = _cfg(hub, [policy])

    apply_enrollment(hub, policy, approval_id="APPROVED-1")
    contract = json.loads((repo / ".digital-asset" / "dad-integration.json").read_text())
    assert contract["repo_id"] == "stable-repo-id"

    with pytest.raises(ValueError, match="reviewed enrollment.repos"):
        select_enrollment_policies([str(split)], cfg)


def test_active_hold_blocks_logos_enrollment_even_with_approval(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "logos-scripture-graph"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(
        repo,
        "logos-scripture-graph",
        active_hold=True,
        active_hold_reason="explicit local-write approval required for Logos repair",
    )

    plan = build_enrollment_plan(hub, [policy], wave="wave-logos")

    assert plan["items"][0]["apply_ready"] is False
    assert "active_hold" in plan["items"][0]["hold_reasons"][0]
    with pytest.raises(ValueError, match="Enrollment is held"):
        apply_enrollment(hub, policy, approval_id="APPROVED-1")


def test_dirty_worktree_blocks_enrollment_unless_policy_allows_it(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    _git(repo, "init")
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")
    policy = _policy(repo)

    with pytest.raises(ValueError, match="dirty_worktree"):
        apply_enrollment(hub, policy, approval_id="APPROVED-1")

    allowed = _policy(repo, allow_dirty_worktree=True)
    result = apply_enrollment(hub, allowed, approval_id="APPROVED-1")
    assert result["changed_count"] > 0


def test_non_main_branch_blocks_enrollment_unless_policy_allows_it(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "checkout", "-b", "feature/dad")
    policy = _policy(repo)

    with pytest.raises(ValueError, match="non_main_branch"):
        apply_enrollment(hub, policy, approval_id="APPROVED-1")

    allowed = _policy(repo, allow_non_main_branch=True)
    result = apply_enrollment(hub, allowed, approval_id="APPROVED-1")
    assert result["changed_count"] > 0
