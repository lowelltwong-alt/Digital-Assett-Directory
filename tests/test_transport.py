from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import digital_asset_directory.daemon as daemon_mod
from digital_asset_directory.cli import app
from digital_asset_directory.daemon import (
    daemon_status,
    run_daemon_cycle,
    task_scheduler_plan,
    task_scheduler_status,
)
from digital_asset_directory.transport import (
    DATA_ROOT_MARKER,
    TRANSPORT_SURFACE_VERSION,
    apply_data_migration,
    audit_all_repo_transport,
    audit_repo_transport,
    data_path,
    data_relative_path,
    init_data_root,
    plan_data_migration,
    resolve_data_root,
    transport_upgrade_queue_path,
)

RUNNER = CliRunner()


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
    (path / "config" / "sources.example.yaml").write_text(
        "\n".join(["project:", "  database: state/catalog.sqlite3", ""]),
        encoding="utf-8",
    )
    return path


def test_uninitialized_data_root_falls_back_to_legacy(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    ghost = tmp_path / "data-root"

    root, mode = resolve_data_root(hub, env={"DAD_DATA_ROOT": str(ghost)})

    assert root == hub
    assert mode == "legacy"
    assert data_path(hub, "central_reports", env={"DAD_DATA_ROOT": str(ghost)}) == (
        hub / "processed" / "reports"
    )


def test_data_init_refuses_unsafe_activation_until_legacy_data_verified(tmp_path: Path):
    hub = tmp_path / "hub"
    source = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text('{"event_type":"test"}\n', encoding="utf-8")
    data_root = tmp_path / "data-root"

    with pytest.raises(ValueError, match="Refusing to activate data root"):
        init_data_root(data_root, hub_root=hub)

    assert not (data_root / DATA_ROOT_MARKER).exists()

    applied = apply_data_migration(hub, data_root)

    assert applied["activated"] is True
    assert (data_root / DATA_ROOT_MARKER).exists()
    assert (data_root / "processed" / "mail" / "inbox" / "rows.jsonl").read_text(
        encoding="utf-8"
    ) == source.read_text(encoding="utf-8")
    assert resolve_data_root(hub, env={"DAD_DATA_ROOT": str(data_root)}) == (
        data_root,
        "data_root",
    )


def test_data_relative_path_routes_only_reviewed_surfaces(tmp_path: Path):
    hub = tmp_path / "hub"
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    env = {"DAD_DATA_ROOT": str(data_root)}

    assert data_relative_path(hub, "processed/reports/transport_audit.json", env=env) == (
        data_root / "processed" / "reports" / "transport_audit.json"
    )
    assert data_relative_path(hub, "processed/learning/actions.jsonl", env=env) == (
        data_root / "processed" / "learning" / "actions.jsonl"
    )
    assert data_relative_path(hub, "docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md", env=env) == (
        hub / "docs" / "DAD_TRANSPORT_AND_COMMS_REDESIGN.md"
    )


def test_transport_audit_flags_mailbox_without_contract_and_writes_queue(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    repo = tmp_path / "repo-a"
    (repo / ".digital-asset" / "mail").mkdir(parents=True)
    (repo / ".digital-asset" / "mail" / ".gitignore").write_text("*.jsonl\n", encoding="utf-8")

    record = audit_repo_transport(repo, repo_id="repo-a")

    assert record["classification"] == "upgrade_recommended"
    assert [signal["signal"] for signal in record["signals"]] == ["contract_missing"]

    summary = audit_all_repo_transport(
        hub,
        [{"id": "repo-a", "path": str(repo), "write_protected": False}],
    )

    assert summary["upgrade_required_count"] == 1
    queue_path = transport_upgrade_queue_path(hub)
    rows = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["repo_id"] == "repo-a"
    assert rows[0]["expected_surface_version"] == TRANSPORT_SURFACE_VERSION


def test_data_and_transport_cli_commands(tmp_path: Path):
    hub = _hub_for_cli(tmp_path / "hub")
    target = tmp_path / "data-root"

    status = RUNNER.invoke(app, ["data", "status", "--hub", str(hub)])
    assert status.exit_code == 0, status.output
    assert json.loads(status.stdout)["mode"] == "legacy"

    plan = RUNNER.invoke(
        app,
        ["data", "migrate", "--hub", str(hub), "--target", str(target), "--plan-only"],
    )
    assert plan.exit_code == 0, plan.output
    assert json.loads(plan.stdout)["target_data_root"] == str(target)

    init = RUNNER.invoke(app, ["data", "init", "--hub", str(hub), "--target", str(target)])
    assert init.exit_code == 0, init.output
    assert (target / DATA_ROOT_MARKER).exists()

    audit = RUNNER.invoke(app, ["transport", "audit", "--hub", str(hub)])
    assert audit.exit_code == 0, audit.output
    payload = json.loads(audit.stdout)
    assert payload["hub_classification"] == "upgrade_required"


def test_plan_data_migration_emits_review_commands_without_deleting(tmp_path: Path):
    hub = tmp_path / "hub"
    target = tmp_path / "data-root"
    (hub / "processed" / "reports").mkdir(parents=True)
    (hub / "processed" / "reports" / "scan_summary.json").write_text("{}\n", encoding="utf-8")

    plan = plan_data_migration(hub, target)

    assert plan["total_files"] == 1
    assert all(command.startswith("git rm -r --cached") for command in plan["untrack_commands_after_verified_copy"])
    assert "This plan never deletes source files" in plan["rule"]


def test_daemon_cycle_writes_heartbeat_and_daily_queue(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()

    first = run_daemon_cycle(hub, mail_repos=[], exception_repos=[], transport_repos=[])
    second = run_daemon_cycle(hub, mail_repos=[], exception_repos=[], transport_repos=[])

    assert Path(first["heartbeat_path"]).exists()
    assert Path(second["heartbeat_path"]).exists()
    assert first["cycle_order"] == [
        "mail_collect",
        "mail_route",
        "mail_deliver",
        "mail_follow_through_audit",
        "events_collect",
        "exceptions_collect",
        "lesson_graph_rebuild",
        "graph_inference",
        "transport_audit",
        "daily_review_queue",
        "heartbeat",
    ]
    assert Path(first["daily_review_queue"]["markdown_path"]).exists()
    status = daemon_status(hub)
    assert status["status"] == "fresh"
    assert status["transport_audit_ran"] is True
    assert "journal_checkpoint_due" not in status


def test_daemon_cycle_with_initialized_data_root_writes_only_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))

    result = run_daemon_cycle(
        hub,
        mail_repos=[],
        exception_repos=[],
        transport_repos=[],
    )

    assert Path(result["heartbeat_path"]).is_relative_to(data_root)
    assert (data_root / "processed" / "reports" / "daemon-heartbeat.json").exists()
    assert not (hub / "processed" / "reports" / "daemon-heartbeat.json").exists()


def test_transport_readiness_cli_reports_local_ready_with_human_gates_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = _hub_for_cli(tmp_path / "hub")
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    run_daemon_cycle(
        hub,
        mail_repos=[],
        exception_repos=[],
        transport_repos=[],
    )

    result = RUNNER.invoke(app, ["transport", "readiness", "--hub", str(hub)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "dad.transport.readiness.v1"
    assert payload["local_ready"] is True
    assert payload["overall_status"] == "local_ready_human_gates_pending"
    assert payload["daemon"]["status"] == "fresh"
    assert payload["journal"]["status"] == "deferred_to_journal_stack_pr"
    assert "daemon_schedule" in payload["human_gate_summary"]["pending"]


def test_transport_readiness_can_include_scheduler_machine_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = _hub_for_cli(tmp_path / "hub")
    run_daemon_cycle(
        hub,
        mail_repos=[],
        exception_repos=[],
        transport_repos=[],
    )

    class Result:
        returncode = 0
        stdout = (
            "TaskName: DAD Daemon Run Cycle\n"
            "Status: Ready\n"
            f"Task To Run: powershell -File asset-dir.ps1 daemon run-cycle --hub '{hub.resolve()}'\n"
            "Next Run Time: 7/7/2026 9:00:00 AM\n"
        )
        stderr = ""

    def fake_run(*_args, **_kwargs):
        return Result()

    monkeypatch.setattr(daemon_mod.subprocess, "run", fake_run)

    result = RUNNER.invoke(
        app,
        [
            "transport",
            "readiness",
            "--hub",
            str(hub),
            "--inspect-scheduler",
            "--shim",
            "asset-dir.ps1",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    scheduler = payload["daemon"]["scheduler_status"]
    assert scheduler["installed"] is True
    assert scheduler["command_mentions_run_cycle"] is True
    gate = payload["human_gates"]["daemon_schedule"]
    assert gate["status"] == "scheduler_installed_machine_condition_met_pending_human_gate_record"


def test_daemon_install_plan_uses_stable_shim_and_run_cycle(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    shim = tmp_path / "asset-dir.ps1"

    plan = task_scheduler_plan(
        hub,
        task_name="DAD Test Cycle",
        schedule_time="10:30",
        shim=shim,
    )

    assert plan["schema_version"] == "dad.daemon.task_scheduler_plan.v1"
    assert str(shim) in plan["command"]
    assert "daemon run-cycle" in plan["command"]
    assert str(hub.resolve()) in plan["command"]


def test_daemon_task_status_parses_read_only_scheduler_query(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    shim = tmp_path / "asset-dir.ps1"

    class Result:
        returncode = 0
        stdout = (
            "TaskName: DAD Daemon Run Cycle\n"
            "Status: Ready\n"
            f"Task To Run: powershell -File '{shim}' daemon run-cycle --hub '{hub.resolve()}'\n"
            "Next Run Time: 7/7/2026 9:00:00 AM\n"
        )
        stderr = ""

    status = task_scheduler_status(
        hub,
        task_name="DAD Daemon Run Cycle",
        shim=shim,
        runner=lambda *_args, **_kwargs: Result(),
    )

    assert status["schema_version"] == "dad.daemon.task_scheduler_status.v1"
    assert status["installed"] is True
    assert status["command_mentions_run_cycle"] is True
    assert status["expected_hub_found"] is True
    assert status["expected_shim_found"] is True
