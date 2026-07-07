from __future__ import annotations

import json
import subprocess
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
from digital_asset_directory.journal import (
    checkpoint_journal,
    ingest_remote_outbox,
    journal_repo_status,
    journal_status,
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
        "journal_remote_outbox_ingest",
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
        "journal_checkpoint",
    ]
    assert Path(first["daily_review_queue"]["markdown_path"]).exists()
    assert first["journal_status"]["schema_version"] == "dad.journal.status.v1"
    assert first["journal"]["checkpoint_skipped_reason"] in {
        "journal_repo_not_configured",
        "threshold_not_met",
    }
    status = daemon_status(hub)
    assert status["status"] == "fresh"
    assert status["transport_audit_ran"] is True
    assert status["journal_checkpoint_due"] in {True, False}
    assert status["journal_checkpoint_status"]["schema_version"] == "dad.journal.status.v1"


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
    assert payload["journal"]["checkpoint_due"] in {True, False}
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


def test_journal_threshold_and_remote_outbox_quarantine(tmp_path: Path):
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("\n".join(json.dumps({"i": i}) for i in range(199)) + "\n", encoding="utf-8")

    assert journal_status(hub, min_records=200, min_hours=999)["checkpoint_due"] is False
    journal_repo = tmp_path / "dad-journal"
    plan_199 = checkpoint_journal(hub, journal_repo, min_records=200, min_hours=999)
    assert plan_199["checkpoint_skipped_reason"] == "threshold_not_met"

    with inbox.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"i": 199}) + "\n")

    assert journal_status(hub, min_records=200, min_hours=999)["checkpoint_due"] is True
    plan_200 = checkpoint_journal(hub, journal_repo, min_records=200, min_hours=999)
    assert plan_200["checkpoint_skipped_reason"] == "plan_only"
    assert plan_200["commands"]

    remote = journal_repo / "remote-outbox"
    remote.mkdir(parents=True)
    (remote / "hostile.jsonl").write_text('{"bad": "packet"}\n{broken\n', encoding="utf-8")
    ingest = ingest_remote_outbox(hub, journal_repo)

    assert ingest["accepted_count"] == 0
    assert ingest["quarantined_count"] >= 2
    assert Path(ingest["quarantine_path"]).exists()


def test_daemon_cycle_ingests_journal_remote_outbox(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    journal_repo = tmp_path / "dad-journal"
    remote = journal_repo / "remote-outbox"
    remote.mkdir(parents=True)
    (remote / "bad.jsonl").write_text("{broken\n", encoding="utf-8")

    result = run_daemon_cycle(
        hub,
        mail_repos=[],
        exception_repos=[],
        transport_repos=[],
        journal_repo=journal_repo,
    )

    assert result["cycle_order"].index("journal_remote_outbox_ingest") < result[
        "cycle_order"
    ].index("mail_collect")
    assert result["remote_outbox_ingest"]["quarantined_count"] == 1
    assert result["cycle_order"][-2:] == ["heartbeat", "journal_checkpoint"]


def test_journal_apply_threshold_commits_and_pushes_to_data_repo(tmp_path: Path):
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("\n".join(json.dumps({"i": i}) for i in range(200)) + "\n", encoding="utf-8")
    source_fixture = hub / "src" / "not-data-plane.jsonl"
    source_fixture.parent.mkdir(parents=True)
    source_fixture.write_text('{"source": "must-not-journal"}\n', encoding="utf-8")
    remote = tmp_path / "dad-journal-remote.git"
    journal_repo = tmp_path / "dad-journal"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-b", "main", str(journal_repo)], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "config", "user.email", "dad@example.test"], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "config", "user.name", "DAD Test"], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "remote", "add", "origin", str(remote)], check=True)

    result = checkpoint_journal(hub, journal_repo, apply=True, min_records=200, min_hours=999)

    assert result["checkpoint_applied"] is True
    assert journal_status(hub, min_records=200, min_hours=999)["checkpoint_due"] is False
    assert (journal_repo / "data" / "processed" / "mail" / "inbox" / "rows.jsonl").exists()
    assert not (journal_repo / "data" / "src" / "not-data-plane.jsonl").exists()
    manifest = json.loads((journal_repo / "journal_checkpoint_manifest.json").read_text())
    assert manifest["checkpoint_scope"] == "DATA_PLANE_PATHS"
    head = subprocess.run(
        ["git", "-C", str(journal_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    remote_head = subprocess.run(
        ["git", "-C", str(remote), "rev-parse", "main"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == remote_head


def test_journal_repo_status_reports_missing_repo(tmp_path: Path):
    hub = tmp_path / "hub"
    missing = tmp_path / "dad-journal"

    status = journal_repo_status(hub, missing)

    assert status["schema_version"] == "dad.journal.repo_status.v1"
    assert status["status"] == "missing"
    assert status["exists"] is False


def test_transport_readiness_can_include_journal_repo_machine_evidence(tmp_path: Path):
    hub = _hub_for_cli(tmp_path / "hub")
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("\n".join(json.dumps({"i": i}) for i in range(200)) + "\n", encoding="utf-8")
    remote = tmp_path / "dad-journal-remote.git"
    journal_repo = tmp_path / "dad-journal"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-b", "main", str(journal_repo)], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "config", "user.email", "dad@example.test"], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "config", "user.name", "DAD Test"], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "remote", "add", "origin", str(remote)], check=True)
    checkpoint_journal(hub, journal_repo, apply=True, min_records=200, min_hours=999)
    run_daemon_cycle(
        hub,
        mail_repos=[],
        exception_repos=[],
        transport_repos=[],
        journal_repo=None,
    )

    result = RUNNER.invoke(
        app,
        [
            "transport",
            "readiness",
            "--hub",
            str(hub),
            "--journal-repo",
            str(journal_repo),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    repo_status = payload["journal"]["repo_status"]
    assert repo_status["machine_ready"] is True
    gate = payload["human_gates"]["journal_repo_checkpoint"]
    assert gate["status"] == "journal_repo_machine_condition_met_pending_human_gate_record"
