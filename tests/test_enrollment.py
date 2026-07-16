from __future__ import annotations

import json
import subprocess
from pathlib import Path

from jsonschema.validators import validator_for
import pytest
import yaml
from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory.config import AppConfig, EnrollmentRepoPolicy, Settings
from digital_asset_directory.enrollment import (
    APPROVED_RELATIVE_PATHS,
    REPO_LOCAL_ONLY_PATHS,
    apply_enrollment,
    build_enrollment_plan,
    enrollment_status,
    select_enrollment_policies,
)
from digital_asset_directory.mail_center import compose_mail
from digital_asset_directory.surface_versions import (
    build_surface_version_status,
    expected_contract_surface_blocks,
    surface_version_upgrade_queue_path,
)
from digital_asset_directory.transport import (
    TRANSPORT_IMPLEMENTATION_VERSION,
    TRANSPORT_SURFACE_VERSION,
    transport_upgrade_queue_path,
)
from digital_asset_directory.utils import append_jsonl

ROOT = Path(__file__).resolve().parents[1]
RUNNER = CliRunner()


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


def _copy_capture_registry(hub: Path) -> None:
    target = hub / "registry" / "exception-capture-pattern-registry.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        (ROOT / "registry" / "exception-capture-pattern-registry.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
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


def _hub_for_cli(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "registry").mkdir()
    (path / "registry" / "source-of-truth.json").write_text("{}", encoding="utf-8")
    (path / "AI_FRONT_DOOR.md").write_text("# AI Front Door\n", encoding="utf-8")
    (path / "MACHINE_NAVIGATION_MANIFEST.json").write_text("{}", encoding="utf-8")
    (path / "src" / "digital_asset_directory").mkdir(parents=True)
    (path / "src" / "digital_asset_directory" / "cli.py").write_text("", encoding="utf-8")
    (path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "digital-asset-directory"',
                "[project.scripts]",
                'asset-dir = "digital_asset_directory.cli:app"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (path / "config").mkdir()
    return path


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
    _copy_capture_registry(hub)
    (repo / "AGENTS.md").write_text("# Local Rules\n\nKeep this line.\n", encoding="utf-8")
    policy = _policy(repo)

    with pytest.raises(ValueError, match="Approval ID"):
        apply_enrollment(hub, policy, approval_id="WRONG")

    before = _all_files(repo)
    result = apply_enrollment(hub, policy, approval_id="APPROVED-1")
    after = _all_files(repo)
    created = after - before

    allowed_enrollment_bootstrap = set(APPROVED_RELATIVE_PATHS) | set(REPO_LOCAL_ONLY_PATHS)
    assert set(result["changed_paths"]) <= allowed_enrollment_bootstrap
    assert created <= allowed_enrollment_bootstrap
    assert "Keep this line." in (repo / "AGENTS.md").read_text(encoding="utf-8")
    agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "~/.dad/bin/asset-dir" in agents_text
    assert "~/.dad/bin/asset-dir.ps1" in agents_text
    assert "PYTHONPATH=src python -m digital_asset_directory.cli" in agents_text
    assert "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli" in agents_text
    assert (
        'PYTHONPATH=src python -m digital_asset_directory.cli agent preflight --repo . '
        '--agent <agent-id> --task "<task>"'
    ) in agents_text
    assert (
        "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli agent preflight "
        '--repo . --agent <agent-id> --task "<task>"'
    ) in agents_text
    assert agents_text.index("~/.dad/bin/asset-dir") < agents_text.index(
        "PYTHONPATH=src python -m digital_asset_directory.cli"
    )
    assert "not permission to bypass the" in agents_text
    assert "fail-closed boundaries below." in agents_text
    assert result["hook_install_disclosed"] is True
    assert result["repo_local_only_paths"] == REPO_LOCAL_ONLY_PATHS
    assert (repo / ".githooks" / "pre-push").exists()
    assert "~/.dad/hub.json" in (repo / ".githooks" / "pre-push").read_text(
        encoding="utf-8"
    )
    assert "~/.dad/hub.json" in (repo / ".githooks" / "pre-push.ps1").read_text(
        encoding="utf-8"
    )
    assert (hub / "processed" / "enrollment" / "audit.jsonl").exists()

    contract = json.loads((repo / ".digital-asset" / "dad-integration.json").read_text())
    context_map = json.loads((repo / ".digital-asset" / "context-map.json").read_text())
    governance_map = yaml.safe_load((repo / ".digital-asset" / "governance-map.yaml").read_text())
    data_map = yaml.safe_load((repo / ".digital-asset" / "data-map.yaml").read_text())
    _validate("repo_enrollment_contract", contract)
    legacy_contract = dict(contract)
    legacy_contract.pop("agent_runtime_policy")
    _validate("repo_enrollment_contract", legacy_contract)
    old_agent_policy_contract = dict(contract)
    old_agent_policy_contract["agent_runtime_policy"] = {
        "core_contract": "AGENTS.md",
        "adapter_authority": "optional_wrapper_only",
        "agent_id_policy": "arbitrary_non_empty_string",
        "vendor_lock_in_prohibited": True,
    }
    _validate("repo_enrollment_contract", old_agent_policy_contract)
    _validate("repo_context_map", context_map)
    _validate("governance_map_adoption", governance_map)
    _validate("data_map_adoption", data_map)
    assert contract["enrollment"]["normal_write_boundary"] == ".digital-asset/mail/**"
    assert contract["agent_runtime_policy"] == {
        "core_contract": "AGENTS.md",
        "adapter_authority": "optional_wrapper_only",
        "agent_id_policy": "arbitrary_non_empty_string",
        "vendor_lock_in_prohibited": True,
        "internal_integration_default": "mcp_over_direct_api",
        "mcp_authority": "neutral_tool_resource_prompt_boundary",
        "direct_api_policy": "external_adapter_fallback_only",
        "mcp_audit_policy": "dad_lifecycle_and_audit_required_for_side_effects",
    }
    assert contract["transport"]["surface_version"] == TRANSPORT_SURFACE_VERSION
    for surface, expected in expected_contract_surface_blocks().items():
        assert contract[surface] == expected
    assert governance_map["agent_runtime_policy"] == contract["agent_runtime_policy"]
    capture_registry = json.loads(
        (ROOT / "registry" / "exception-capture-pattern-registry.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["capture"]["surface_version"] == capture_registry["capture_surface_version"]
    assert contract["capture"]["pattern_registry_ref"].endswith(
        "/registry/exception-capture-pattern-registry.json"
    )
    assert contract["capture"]["mail_outbox"] == ".digital-asset/mail/outbox.jsonl"
    assert "~/.dad/bin/asset-dir" in contract["capture"]["cli_fallback"]
    assert "~/.dad/bin/asset-dir.ps1" in contract["capture"]["cli_fallback"]
    assert "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli" in contract[
        "capture"
    ]["cli_fallback"]
    assert contract["capture"]["repo_local_only_paths"] == REPO_LOCAL_ONLY_PATHS
    assert "processed/exceptions/fix-outcomes/outcomes.jsonl" in contract["capture"][
        "repo_local_only_paths"
    ]
    assert not (set(REPO_LOCAL_ONLY_PATHS) & set(contract["approved_dad_managed_paths"]))
    assert (repo / ".digital-asset" / "exceptions" / "README.md").exists()
    assert (repo / ".digital-asset" / "exceptions" / ".gitignore").exists()
    assert (repo / ".digital-asset" / "exceptions" / "outbox.jsonl").exists()
    assert (repo / ".digital-asset" / "exceptions" / "inbox.jsonl").exists()
    assert (repo / ".digital-asset" / "exceptions" / "archive.jsonl").exists()
    assert "Never Send" in (
        repo / ".digital-asset" / "exceptions" / "README.md"
    ).read_text(encoding="utf-8")
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


def test_update_plan_can_select_from_transport_upgrade_queue(tmp_path: Path):
    hub = _hub_for_cli(tmp_path / "hub")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    (hub / "config" / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "enrollment:",
                "  repos:",
                "    - id: repo-a",
                f"      path: {repo_a}",
                "      wave: wave-a",
                "      update_allowed: true",
                "      approved_approval_ids: [APPROVED-1]",
                "    - id: repo-b",
                f"      path: {repo_b}",
                "      wave: wave-b",
                "      update_allowed: true",
                "      approved_approval_ids: [APPROVED-1]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    queue_path = transport_upgrade_queue_path(hub)
    for row in [
        {"repo_id": "repo-a", "review_status": "candidate"},
        {"repo_id": "repo-b", "review_status": "candidate"},
        {"repo_id": "repo-protected", "review_status": "candidate", "write_protected": True},
        {"repo_id": "repo-missing", "review_status": "candidate"},
    ]:
        append_jsonl(
            queue_path,
            {
                "queue_key": f"queue:{row['repo_id']}",
                "classification": "upgrade_recommended",
                "expected_surface_version": TRANSPORT_SURFACE_VERSION,
                "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                **row,
            },
        )

    result = RUNNER.invoke(
        app,
        [
            "enroll",
            "update-plan",
            "--hub",
            str(hub),
            "--wave",
            "wave-a",
            "--from-transport-queue",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["operation"] == "update"
    assert payload["item_count"] == 1
    assert payload["items"][0]["repo_id"] == "repo-a"
    selection = payload["transport_upgrade_queue_selection"]
    assert selection["queue_row_count"] == 4
    assert selection["selected_count"] == 1
    skipped = {item["repo_id"]: item["reason"] for item in selection["skipped"]}
    assert skipped == {
        "repo-b": "wrong_wave",
        "repo-protected": "write_protected_central_only",
        "repo-missing": "no_reviewed_enrollment_policy",
    }
    assert (hub / payload["plan_path"]).exists()


def test_enrollment_status_reports_schema_stale_contract(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)
    apply_enrollment(hub, policy, approval_id="APPROVED-1")

    contract_path = repo / ".digital-asset" / "dad-integration.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    del contract["capture"]["repo_local_only_paths"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    status = enrollment_status(policy)

    assert status["update_available"] is True
    assert any("schema validation failed" in error for error in status["errors"])


def test_enrollment_status_reports_missing_transport_contract(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)
    apply_enrollment(hub, policy, approval_id="APPROVED-1")

    contract_path = repo / ".digital-asset" / "dad-integration.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    del contract["transport"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    status = enrollment_status(policy)

    assert status["update_available"] is True
    assert status["transport"]["status"] == "contract_missing"
    assert "Enrollment contract missing transport.surface_version" in status["errors"]


def test_enrollment_status_reports_missing_surface_versions_as_legacy(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)
    apply_enrollment(hub, policy, approval_id="APPROVED-1")

    contract_path = repo / ".digital-asset" / "dad-integration.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    for surface in ("graph", "mcp", "journal", "events"):
        del contract[surface]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    status = enrollment_status(policy)

    assert status["update_available"] is True
    for surface in ("graph", "mcp", "journal", "events"):
        assert status["surface_versions"][surface]["status"] == "legacy"
        assert status["surface_versions"][surface]["update_needed"] is True
    assert any("graph.surface_version is legacy" in error for error in status["errors"])


def test_enrollment_update_refuses_to_downgrade_newer_repo_contract(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)
    apply_enrollment(hub, policy, approval_id="APPROVED-1")
    contract_path = repo / ".digital-asset" / "dad-integration.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["graph"]["surface_version"] = "9.0.0"
    contract["approved_dad_managed_paths"].append(
        ".digital-asset/future-surface.json"
    )
    contract["enabled_control_planes"].append("future_control_plane")
    contract_path.write_text(json.dumps(contract, sort_keys=True), encoding="utf-8")
    before = contract_path.read_bytes()

    with pytest.raises(ValueError, match="would downgrade or remove") as exc:
        apply_enrollment(
            hub,
            policy,
            approval_id="APPROVED-1",
            update=True,
        )

    message = str(exc.value)
    assert "graph.surface_version:9.0.0>1.0.0" in message
    assert ".digital-asset/future-surface.json" in message
    assert "future_control_plane" in message
    assert contract_path.read_bytes() == before


def test_surface_version_status_writes_queue_by_repo_surface_and_expected_version(
    tmp_path: Path,
):
    hub = tmp_path / "hub"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    hub.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    policy_a = _policy(repo_a, "repo-a")
    policy_b = _policy(repo_b, "repo-b")
    apply_enrollment(hub, policy_a, approval_id="APPROVED-1")
    apply_enrollment(hub, policy_b, approval_id="APPROVED-1")

    contract_a = json.loads((repo_a / ".digital-asset" / "dad-integration.json").read_text())
    del contract_a["graph"]
    del contract_a["mcp"]
    (repo_a / ".digital-asset" / "dad-integration.json").write_text(
        json.dumps(contract_a),
        encoding="utf-8",
    )
    contract_b = json.loads((repo_b / ".digital-asset" / "dad-integration.json").read_text())
    del contract_b["journal"]
    (repo_b / ".digital-asset" / "dad-integration.json").write_text(
        json.dumps(contract_b),
        encoding="utf-8",
    )

    result = build_surface_version_status(
        hub,
        enrollment_policies=[policy_a, policy_b],
        transport_repos=[
            {"id": "repo-a", "path": str(repo_a), "write_protected": False},
            {"id": "repo-b", "path": str(repo_b), "write_protected": True},
        ],
        wave="wave-a",
    )

    assert Path(result["report_path"]).exists()
    assert result["surface_update_counts"]["graph"] == 1
    assert result["surface_update_counts"]["mcp"] == 1
    assert result["surface_update_counts"]["journal"] == 1
    assert result["queue_appended"] == 3
    queue_rows = [
        json.loads(line)
        for line in surface_version_upgrade_queue_path(hub).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {
        (row["repo_id"], row["surface"], row["expected_surface_version"])
        for row in queue_rows
    } == {
        ("repo-a", "graph", "1.0.0"),
        ("repo-a", "mcp", "1.0.0"),
        ("repo-b", "journal", "1.0.0"),
    }
    protected = [row for row in queue_rows if row["repo_id"] == "repo-b"][0]
    assert protected["write_protected"] is True
    assert protected["delivery_rule"].startswith("central_only")

    deduped = build_surface_version_status(
        hub,
        enrollment_policies=[policy_a, policy_b],
        transport_repos=[],
        wave="wave-a",
    )

    assert deduped["queue_appended"] == 0


def test_enrollment_status_reports_missing_exception_surface(tmp_path: Path):
    hub = tmp_path / "hub"
    repo = tmp_path / "repo-a"
    hub.mkdir()
    repo.mkdir()
    policy = _policy(repo)
    apply_enrollment(hub, policy, approval_id="APPROVED-1")

    (repo / ".digital-asset" / "exceptions" / "inbox.jsonl").unlink()
    status = enrollment_status(policy)

    assert status["update_available"] is True
    assert (
        "Missing repo-local exception surface path: "
        ".digital-asset/exceptions/inbox.jsonl"
    ) in status["errors"]


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
    assert "C:/Users/" not in json.dumps(contract)
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
