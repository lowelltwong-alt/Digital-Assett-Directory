from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

import digital_asset_directory.daemon as daemon_mod
import digital_asset_directory.exception_capture as exception_capture_mod
import digital_asset_directory.journal as journal_mod
from digital_asset_directory.cli import app
from digital_asset_directory.daemon import (
    daemon_heartbeat_path,
    daemon_status,
    run_daemon_cycle,
    scheduled_tasks_report_path,
    scheduled_tasks_status,
    task_scheduler_plan,
    task_scheduler_status,
)
from digital_asset_directory.exception_capture import (
    PHASE6_MACHINE_EVIDENCE_SUMMARY_JSON,
    write_phase6_machine_evidence_summary,
)
from digital_asset_directory.journal import (
    checkpoint_journal,
    ingest_remote_outbox,
    journal_repo_status,
    journal_status,
)
from digital_asset_directory.transport import (
    DATA_ROOT_MARKER,
    TRANSPORT_IMPLEMENTATION_VERSION,
    TRANSPORT_SURFACE_VERSION,
    apply_data_migration,
    audit_all_repo_transport,
    audit_repo_transport,
    build_transport_version_status,
    data_path,
    data_relative_path,
    init_data_root,
    plan_data_migration,
    resolve_data_root,
    run_synthetic_transport_rollout,
    transport_contract_payload,
    transport_upgrade_queue_path,
)
from digital_asset_directory.utils import sha256_file
from digital_asset_directory.validation import _stale_report_input_hash_errors

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


def test_exception_capture_report_defaults_use_initialized_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))

    result = write_phase6_machine_evidence_summary(hub)

    output_path = data_root / PHASE6_MACHINE_EVIDENCE_SUMMARY_JSON
    assert output_path.exists()
    assert result["report_id"] == "dad:phase6-exception-capture-machine-evidence-summary"
    assert not (hub / PHASE6_MACHINE_EVIDENCE_SUMMARY_JSON).exists()


def test_validation_report_hashes_use_active_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    legacy_events = hub / "processed" / "exceptions" / "lake" / "events.jsonl"
    legacy_events.parent.mkdir(parents=True)
    legacy_events.write_text('{"event":"legacy"}\n', encoding="utf-8")

    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    active_events = data_root / "processed" / "exceptions" / "lake" / "events.jsonl"
    active_events.write_text('{"event":"active"}\n', encoding="utf-8")
    legacy_events.write_text('{"event":"stale-legacy"}\n', encoding="utf-8")

    report_path = data_root / "processed" / "reports" / "example.json"
    report_path.parent.mkdir(parents=True)
    payload = {
        "input_hashes": {
            "processed/exceptions/lake/events.jsonl": f"sha256:{sha256_file(active_events)}"
        }
    }

    assert _stale_report_input_hash_errors(hub, report_path, payload) == []


def test_exception_capture_plan_defaults_refresh_companion_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    readiness_outputs: list[Path | None] = []
    observed_outputs: list[Path | None] = []

    def fake_readiness(*args, output=None, **kwargs):
        readiness_outputs.append(output)
        return {"repos": []}

    def fake_observed(*args, output=None, **kwargs):
        observed_outputs.append(output)
        return {"repos": []}

    monkeypatch.setattr(
        exception_capture_mod, "write_exception_backfill_readiness", fake_readiness
    )
    monkeypatch.setattr(
        exception_capture_mod, "write_observed_capture_audit", fake_observed
    )
    monkeypatch.setattr(
        exception_capture_mod,
        "build_exception_capture_remediation_plan",
        lambda readiness, per_lane_repo_limit=25: {"report_id": "remediation"},
    )
    monkeypatch.setattr(
        exception_capture_mod,
        "build_exception_capture_gap_review_queue",
        lambda observed, per_group_example_limit=5: {"report_id": "gap"},
    )
    monkeypatch.setattr(
        exception_capture_mod,
        "build_exception_backfill_wave_plan",
        lambda readiness, per_wave_repo_limit=25: {"report_id": "wave"},
    )
    monkeypatch.setattr(
        exception_capture_mod, "_capture_remediation_plan_markdown", lambda report: ""
    )
    monkeypatch.setattr(
        exception_capture_mod, "_capture_gap_review_queue_markdown", lambda report: ""
    )
    monkeypatch.setattr(
        exception_capture_mod, "_backfill_wave_plan_markdown", lambda report: ""
    )

    exception_capture_mod.write_exception_capture_remediation_plan(hub, [])
    exception_capture_mod.write_exception_capture_gap_review_queue(hub, [])
    exception_capture_mod.write_exception_backfill_wave_plan(hub, [])

    assert (
        exception_capture_mod.CAPTURE_REMEDIATION_PLAN_JSON.with_name(
            "exception_capture_remediation_plan_readiness.json"
        )
        in readiness_outputs
    )
    assert (
        exception_capture_mod.BACKFILL_WAVE_PLAN_JSON.with_name(
            "exception_backfill_wave_plan_readiness.json"
        )
        in readiness_outputs
    )
    assert observed_outputs == [
        exception_capture_mod.CAPTURE_GAP_REVIEW_QUEUE_JSON.with_name(
            "exception_capture_gap_review_queue_observed_audit.json"
        )
    ]


def _write_transport_upgrade_config(hub: Path, repo_a: Path, repo_b: Path) -> None:
    (hub / "config" / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "mail:",
                "  repos:",
                "    - id: repo-a",
                f"      path: {repo_a}",
                "      mail_enabled: true",
                "    - id: repo-b",
                f"      path: {repo_b}",
                "      mail_enabled: true",
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
    assert rows[0]["expected_implementation_version"] == TRANSPORT_IMPLEMENTATION_VERSION


def test_transport_audit_flags_stale_contract_repo_path_without_exposing_paths(tmp_path: Path):
    repo = tmp_path / "canonical-repo"
    mail = repo / ".digital-asset" / "mail"
    mail.mkdir(parents=True)
    (mail / ".gitignore").write_text("*.jsonl\n", encoding="utf-8")
    contract = repo / ".digital-asset" / "dad-integration.json"
    contract.write_text(
        json.dumps(
            {
                "repo_path": str(tmp_path / "obsolete-checkout"),
                "transport": {
                    "surface_version": TRANSPORT_SURFACE_VERSION,
                    "implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                },
            }
        ),
        encoding="utf-8",
    )

    record = audit_repo_transport(repo, repo_id="repo-a")

    assert record["classification"] == "upgrade_recommended"
    assert [signal["signal"] for signal in record["signals"]] == ["repo_path_stale"]
    signal = record["signals"][0]
    assert signal["recorded_path_exists"] is False
    assert "obsolete-checkout" not in json.dumps(record)


def test_transport_audit_queue_dedupe_survives_concurrent_runs(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    repo = tmp_path / "repo-a"
    (repo / ".digital-asset" / "mail").mkdir(parents=True)
    (repo / ".digital-asset" / "mail" / ".gitignore").write_text("*.jsonl\n", encoding="utf-8")
    repos = [{"id": "repo-a", "path": str(repo), "write_protected": False}]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _index: audit_all_repo_transport(hub, repos), range(4)))

    rows = [
        json.loads(line)
        for line in transport_upgrade_queue_path(hub).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(result["queue_appended"] for result in results) == 1
    assert [row["repo_id"] for row in rows] == ["repo-a"]


def test_transport_version_status_and_synthetic_rollout(tmp_path: Path):
    hub = _hub_for_cli(tmp_path / "hub")
    current = tmp_path / "current"
    (current / ".digital-asset" / "mail").mkdir(parents=True)
    (current / ".digital-asset" / "mail" / ".gitignore").write_text("*.jsonl\n", encoding="utf-8")
    (current / ".digital-asset" / "dad-integration.json").write_text(
        json.dumps({"repo_id": "current", "transport": transport_contract_payload()}),
        encoding="utf-8",
    )
    missing_impl = tmp_path / "missing-implementation"
    (missing_impl / ".digital-asset" / "mail").mkdir(parents=True)
    (missing_impl / ".digital-asset" / "mail" / ".gitignore").write_text("*.jsonl\n", encoding="utf-8")
    (missing_impl / ".digital-asset" / "dad-integration.json").write_text(
        json.dumps(
            {
                "repo_id": "missing-implementation",
                "transport": {
                    "surface_version": TRANSPORT_SURFACE_VERSION,
                    "mode": "local_pull",
                    "journal_fallback": True,
                },
            }
        ),
        encoding="utf-8",
    )

    status = build_transport_version_status(
        hub,
        [
            {"id": "current", "path": str(current), "write_protected": False},
            {"id": "missing-implementation", "path": str(missing_impl), "write_protected": False},
        ],
    )
    missing_row = next(
        row for row in status["repo_versions"] if row["repo_id"] == "missing-implementation"
    )
    assert status["transport_implementation_version"] == TRANSPORT_IMPLEMENTATION_VERSION
    assert status["status"] == "upgrade_needed"
    assert missing_row["transport_implementation_version_seen"] == "missing"

    synthetic = run_synthetic_transport_rollout(hub)
    assert synthetic["status"] == "passed"
    assert synthetic["case_count"] == synthetic["passed_count"]
    assert synthetic["queue_dedupe_second_run_appended"] == 0


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


def test_transport_upgrade_status_reports_reviewed_queue_and_plan_artifacts(tmp_path: Path):
    hub = _hub_for_cli(tmp_path / "hub")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    _write_transport_upgrade_config(hub, repo_a, repo_b)
    report_path = data_path(hub, "central_reports") / "transport_audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "transport_surface_version": TRANSPORT_SURFACE_VERSION,
                "repo_count": 2,
                "classification_counts": {"upgrade_recommended": 2},
                "hub": {"classification": "upgrade_required"},
            }
        ),
        encoding="utf-8",
    )
    queue_path = transport_upgrade_queue_path(hub)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"repo_id": "repo-a", "review_status": "candidate"},
        {"repo_id": "repo-b", "review_status": "candidate"},
        {"repo_id": "repo-protected", "review_status": "candidate", "write_protected": True},
        {"repo_id": "repo-missing", "review_status": "candidate"},
    ]
    queue_path.write_text(
        "".join(
            json.dumps(
                {
                    "queue_key": f"queue:{row['repo_id']}",
                    "classification": "upgrade_recommended",
                    "expected_surface_version": TRANSPORT_SURFACE_VERSION,
                    "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                    **row,
                }
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )

    plan_result = RUNNER.invoke(
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
    assert plan_result.exit_code == 0, plan_result.output

    result = RUNNER.invoke(
        app,
        ["transport", "upgrade-status", "--hub", str(hub), "--wave", "wave-a"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "dad.transport.upgrade_status.v1"
    assert payload["status"] == "ready_for_update_plan"
    assert payload["plan_artifacts"]["repo_ids"] == ["repo-a"]
    assert payload["selection"]["selected_repo_ids"] == ["repo-a"]
    assert payload["selection"]["skipped_by_reason"] == {
        "wrong_wave": 1,
        "write_protected_central_only": 1,
        "no_reviewed_enrollment_policy": 1,
    }
    assert payload["operator_next_steps"] == [
        "asset-dir enroll update-plan --wave wave-a --from-transport-queue"
    ]


def test_transport_upgrade_status_obeys_policy_holds_even_when_queue_is_stale(
    tmp_path: Path,
):
    hub = _hub_for_cli(tmp_path / "hub")
    repo_hold = tmp_path / "repo-hold"
    repo_no_update = tmp_path / "repo-no-update"
    repo_hold.mkdir()
    repo_no_update.mkdir()
    (hub / "config" / "sources.example.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  database: state/catalog.sqlite3",
                "enrollment:",
                "  repos:",
                "    - id: repo-hold",
                f"      path: {repo_hold}",
                "      wave: wave-a",
                "      update_allowed: true",
                "      active_hold: true",
                "      active_hold_reason: active work paused writes",
                "      approved_approval_ids: [APPROVED-1]",
                "    - id: repo-no-update",
                f"      path: {repo_no_update}",
                "      wave: wave-a",
                "      update_allowed: false",
                "      approved_approval_ids: [APPROVED-1]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    report_path = data_path(hub, "central_reports") / "transport_audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "transport_surface_version": TRANSPORT_SURFACE_VERSION,
                "transport_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                "repo_count": 2,
                "classification_counts": {"upgrade_required": 2},
                "hub": {"classification": "upgrade_required"},
                "records": [
                    {"repo_id": "repo-hold", "classification": "upgrade_required"},
                    {"repo_id": "repo-no-update", "classification": "upgrade_required"},
                ],
            }
        ),
        encoding="utf-8",
    )
    queue_path = transport_upgrade_queue_path(hub)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_rows = [
        {
            "queue_key": "queue:repo-hold",
            "repo_id": "repo-hold",
            "classification": "upgrade_required",
            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
            "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
            "review_status": "candidate",
        },
        {
            "queue_key": "queue:repo-no-update",
            "repo_id": "repo-no-update",
            "classification": "upgrade_required",
            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
            "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
            "review_status": "candidate",
        },
    ]
    queue_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in queue_rows),
        encoding="utf-8",
    )

    result = RUNNER.invoke(
        app,
        ["transport", "upgrade-status", "--hub", str(hub), "--wave", "wave-a"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "review_required"
    assert payload["selection"]["selected_count"] == 0
    assert payload["selection"]["skipped_by_reason"] == {
        "active_hold_central_only": 1,
        "update_not_allowed": 1,
    }

def test_transport_upgrade_status_supersedes_stale_queue_rows_with_current_audit(
    tmp_path: Path,
):
    hub = _hub_for_cli(tmp_path / "hub")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    _write_transport_upgrade_config(hub, repo_a, repo_b)
    report_path = data_path(hub, "central_reports") / "transport_audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "transport_surface_version": TRANSPORT_SURFACE_VERSION,
                "transport_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                "repo_count": 2,
                "classification_counts": {"current": 1, "upgrade_required": 1},
                "hub": {"classification": "upgrade_required"},
                "records": [
                    {"repo_id": "repo-a", "classification": "current"},
                    {"repo_id": "repo-b", "classification": "upgrade_required"},
                ],
            }
        ),
        encoding="utf-8",
    )
    queue_path = transport_upgrade_queue_path(hub)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_rows = [
        {
            "queue_key": "queue:repo-a:old",
            "repo_id": "repo-a",
            "classification": "upgrade_recommended",
            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
            "expected_implementation_version": "old-implementation",
            "review_status": "candidate",
        },
        {
            "queue_key": "queue:repo-a:new",
            "repo_id": "repo-a",
            "classification": "upgrade_recommended",
            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
            "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
            "review_status": "candidate",
        },
        {
            "queue_key": "queue:repo-b:new",
            "repo_id": "repo-b",
            "classification": "upgrade_required",
            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
            "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
            "review_status": "candidate",
            "write_protected": True,
        },
    ]
    queue_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in queue_rows),
        encoding="utf-8",
    )

    result = RUNNER.invoke(
        app,
        ["transport", "upgrade-status", "--hub", str(hub), "--wave", "wave-a"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "protected_repos_central_only"
    assert payload["queue"]["row_count"] == 3
    assert payload["queue"]["effective_row_count"] == 2
    assert payload["selection"]["selected_count"] == 0
    assert payload["selection"]["skipped_by_reason"] == {
        "superseded_by_current_audit": 1,
        "write_protected_central_only": 1,
    }
    assert payload["selection"]["audit_filter"]["filter_applied"] is True
    assert payload["operator_next_steps"] == [
        "review protected repo rows centrally; do not write target repos"
    ]


def test_transport_readiness_includes_upgrade_wave_status(tmp_path: Path):
    hub = _hub_for_cli(tmp_path / "hub")
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    _write_transport_upgrade_config(hub, repo_a, repo_b)
    report_path = data_path(hub, "central_reports") / "transport_audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "transport_surface_version": TRANSPORT_SURFACE_VERSION,
                "repo_count": 2,
                "classification_counts": {"upgrade_recommended": 2},
                "hub": {"classification": "upgrade_required"},
            }
        ),
        encoding="utf-8",
    )
    queue_path = transport_upgrade_queue_path(hub)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        json.dumps(
            {
                "queue_key": "queue:repo-a",
                "repo_id": "repo-a",
                "classification": "upgrade_recommended",
                "expected_surface_version": TRANSPORT_SURFACE_VERSION,
                "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                "review_status": "candidate",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = RUNNER.invoke(
        app,
        ["transport", "readiness", "--hub", str(hub), "--wave", "wave-a"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["upgrade_wave"]["status"] == "ready_for_update_plan"
    assert payload["human_gates"]["repo_upgrade_wave"]["evidence"]["selected_count"] == 1


def test_transport_upgrade_status_reads_report_from_active_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = _hub_for_cli(tmp_path / "hub")
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    report_path = data_path(hub, "central_reports") / "transport_audit.json"
    queue_path = transport_upgrade_queue_path(hub)
    assert report_path.is_relative_to(data_root)
    assert queue_path.is_relative_to(data_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "transport_surface_version": TRANSPORT_SURFACE_VERSION,
                "repo_count": 0,
                "classification_counts": {},
                "hub": {"classification": "current"},
            }
        ),
        encoding="utf-8",
    )
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text("", encoding="utf-8")

    result = RUNNER.invoke(app, ["transport", "upgrade-status", "--hub", str(hub)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["audit"]["report_status"] == "readable"
    assert payload["queue"]["queue_path"] == str(queue_path)


def test_plan_data_migration_emits_review_commands_without_deleting(tmp_path: Path):
    hub = tmp_path / "hub"
    target = tmp_path / "data-root"
    (hub / "processed" / "reports").mkdir(parents=True)
    (hub / "processed" / "reports" / "scan_summary.json").write_text("{}\n", encoding="utf-8")

    plan = plan_data_migration(hub, target)

    assert plan["total_files"] == 1
    assert plan["untrack_scope"] == "tracked_and_gitignored_data_plane_files_only"
    assert "git ls-files -ci --exclude-standard" in plan["untrack_commands_after_verified_copy"][0]
    assert "git rm --cached -- $trackedRuntime" in plan["untrack_commands_after_verified_copy"][1]
    assert "This plan never deletes source files" in plan["rule"]


def test_daemon_cycle_writes_heartbeat_and_daily_queue(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()

    first = run_daemon_cycle(hub, mail_repos=[], exception_repos=[], transport_repos=[])
    heartbeat_path = Path(first["heartbeat_path"])
    non_heartbeat_before = {
        path.relative_to(hub).as_posix(): path.read_bytes()
        for path in hub.rglob("*")
        if path.is_file() and path != heartbeat_path
    }
    second = run_daemon_cycle(hub, mail_repos=[], exception_repos=[], transport_repos=[])
    non_heartbeat_after = {
        path.relative_to(hub).as_posix(): path.read_bytes()
        for path in hub.rglob("*")
        if path.is_file() and path != heartbeat_path
    }

    assert Path(first["heartbeat_path"]).exists()
    assert Path(second["heartbeat_path"]).exists()
    assert second["idle"] is True
    assert second["cycle_order"] == ["heartbeat"]
    assert non_heartbeat_after == non_heartbeat_before
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
        "weekly_asset_coverage",
        "scheduled_task_registry",
        "daily_review_queue",
        "heartbeat",
        "journal_checkpoint",
    ]
    assert Path(first["daily_review_queue"]["markdown_path"]).exists()
    assert first["graph_surface_status"]["schema_version"] == "dad.graph_surface.status.v1"
    assert "graph_surfaces" in first["daily_review_queue"]["report"]
    assert "weekly_asset_coverage" in first["daily_review_queue"]["report"]
    assert (
        "Graph surface freshness"
        in Path(first["daily_review_queue"]["markdown_path"]).read_text(encoding="utf-8")
    )
    assert "Weekly asset coverage" in Path(first["daily_review_queue"]["markdown_path"]).read_text(
        encoding="utf-8"
    )
    assert first["journal_status"]["schema_version"] == "dad.journal.status.v1"
    assert first["scheduled_tasks"]["schema_version"] == "dad.daemon.scheduled_tasks.v1"
    assert first["scheduled_tasks"]["task_count"] == 1
    assert first["scheduled_tasks"]["tasks"][0]["health"] == "heartbeat_fresh_scheduler_not_inspected"
    assert Path(first["scheduled_tasks"]["report_path"]).exists()
    assert (
        Path(first["scheduled_tasks"]["report_path"])
        == hub / "processed" / "reports" / "scheduled_tasks.json"
    )
    assert first["journal"]["checkpoint_skipped_reason"] in {
        "journal_repo_not_configured",
        "threshold_not_met",
    }
    status = daemon_status(hub)
    assert status["status"] == "fresh"
    assert status["transport_audit_ran"] is True
    assert status["weekly_asset_coverage_status"] in {"ok", "skipped"}
    assert "graph_surface_freshness_counts" in status["last_cycle"]
    assert status["scheduled_tasks_report_path"].endswith("scheduled_tasks.json")
    assert status["scheduled_task_count"] == 1
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
    assert (data_root / "processed" / "reports" / "scheduled_tasks.json").exists()
    assert (data_root / "processed" / "reports" / "weekly_asset_coverage.json").exists()
    assert not (hub / "processed" / "reports" / "daemon-heartbeat.json").exists()
    assert not (hub / "processed" / "reports" / "scheduled_tasks.json").exists()
    assert not (hub / "processed" / "reports" / "weekly_asset_coverage.json").exists()


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
    assert payload["graph_surfaces"]["schema_version"] == "dad.graph_surface.status.v1"
    assert payload["local_checks"]["graph_surface_status_readable"] is True
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
    assert plan["wrapper_path"] in plan["command"]
    assert "daemon run-cycle" not in plan["command"]
    assert plan["wrapper_path"] == str(shim.with_name("dad-daemon-run-cycle.ps1"))
    assert str(shim) in plan["wrapper_script"]
    assert "daemon run-cycle" in plan["wrapper_script"]
    assert str(hub.resolve()) in plan["wrapper_script"]
    assert "--hub" in plan["run_cycle_args"]
    assert "--quiet" in plan["run_cycle_args"]
    settings_script = plan["settings_command"][-1]
    assert "AllowStartIfOnBatteries" in settings_script
    assert "DontStopIfGoingOnBatteries" in settings_script
    assert "StartWhenAvailable" in settings_script


def test_daemon_run_cycle_quiet_writes_reports_without_rendering_payload(tmp_path: Path):
    hub = _hub_for_cli(tmp_path / "hub")

    result = RUNNER.invoke(
        app,
        [
            "daemon",
            "run-cycle",
            "--hub",
            str(hub),
            "--quiet",
            "--skip-graphs",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert daemon_heartbeat_path(hub).exists()


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


def test_daemon_task_status_reads_wrapper_for_long_scheduler_commands(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    shim = tmp_path / "asset-dir.ps1"
    wrapper = tmp_path / "dad-daemon-run-cycle.ps1"
    wrapper.write_text(
        f"& '{shim}' daemon run-cycle --hub '{hub.resolve()}' --checkpoint-apply\n",
        encoding="utf-8",
    )

    class Result:
        returncode = 0
        stdout = (
            "TaskName: DAD Daemon Run Cycle\n"
            "Status: Ready\n"
            f'Task To Run: powershell -File "{wrapper}"\n'
            "Next Run Time: 7/7/2026 9:00:00 AM\n"
        )
        stderr = ""

    status = task_scheduler_status(
        hub,
        task_name="DAD Daemon Run Cycle",
        shim=shim,
        runner=lambda *_args, **_kwargs: Result(),
    )

    assert status["wrapper_found"] is True
    assert status["command_mentions_run_cycle"] is True
    assert status["expected_hub_found"] is True
    assert status["expected_shim_found"] is True


def test_scheduled_tasks_status_lists_daemon_for_ui(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    shim = tmp_path / "asset-dir.ps1"
    wrapper = tmp_path / "dad-daemon-run-cycle.ps1"
    wrapper.write_text(
        f"& '{shim}' daemon run-cycle --hub '{hub.resolve()}'\n",
        encoding="utf-8",
    )
    run_daemon_cycle(hub, mail_repos=[], exception_repos=[], transport_repos=[])

    class Result:
        returncode = 0
        stdout = (
            "TaskName: DAD Daemon Run Cycle\n"
            "Status: Ready\n"
            f'Task To Run: powershell -File "{wrapper}"\n'
            "Next Run Time: 7/9/2026 9:00:00 AM\n"
        )
        stderr = ""

    status = scheduled_tasks_status(
        hub,
        shim=shim,
        inspect_scheduler=True,
        runner=lambda *_args, **_kwargs: Result(),
    )

    assert status["schema_version"] == "dad.daemon.scheduled_tasks.v1"
    assert status["report_path"] == str(scheduled_tasks_report_path(hub))
    assert status["task_count"] == 1
    assert status["healthy_count"] == 1
    task = status["tasks"][0]
    assert task["task_id"] == "dad-daemon-run-cycle"
    assert task["health"] == "ready"
    assert task["ui_ready"] is True
    assert task["scheduler"]["installed"] is True
    assert task["scheduler"]["command_mentions_run_cycle"] is True
    assert "stdout" not in task["scheduler"]
    assert "wrapper_text" not in task["scheduler"]
    assert "phase-13-daemon-schedule-approved" in task["human_gate_ids"]


def test_daemon_scheduled_tasks_cli_can_write_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub = _hub_for_cli(tmp_path / "hub")
    shim = tmp_path / "asset-dir.ps1"
    wrapper = tmp_path / "dad-daemon-run-cycle.ps1"
    wrapper.write_text(
        f"& '{shim}' daemon run-cycle --hub '{hub.resolve()}'\n",
        encoding="utf-8",
    )
    run_daemon_cycle(hub, mail_repos=[], exception_repos=[], transport_repos=[])

    class Result:
        returncode = 0
        stdout = (
            "TaskName: DAD Daemon Run Cycle\n"
            "Status: Ready\n"
            f'Task To Run: powershell -File "{wrapper}"\n'
            "Next Run Time: 7/9/2026 9:00:00 AM\n"
        )
        stderr = ""

    monkeypatch.setattr(daemon_mod.subprocess, "run", lambda *_args, **_kwargs: Result())

    result = RUNNER.invoke(
        app,
        [
            "daemon",
            "scheduled-tasks",
            "--hub",
            str(hub),
            "--inspect-scheduler",
            "--shim",
            str(shim),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "dad.daemon.scheduled_tasks.v1"
    assert payload["tasks"][0]["health"] == "ready"
    report_path = scheduled_tasks_report_path(hub)
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["tasks"][0]["scheduler"]["next_run_time"] == "7/9/2026 9:00:00 AM"


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


def test_journal_checkpoint_time_threshold_ages_first_pending_checkpoint(tmp_path: Path):
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("\n".join(json.dumps({"i": i}) for i in range(199)) + "\n", encoding="utf-8")
    status_path = data_path(hub, "central_reports") / "journal_checkpoint_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    old_pending = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    status_path.write_text(
        json.dumps({"checkpoint_record_count": 0, "generated_at": old_pending}),
        encoding="utf-8",
    )

    due = checkpoint_journal(
        hub,
        tmp_path / "dad-journal",
        apply=False,
        min_records=200,
        min_hours=24,
    )

    assert due["checkpoint_due"] is True
    assert due["checkpoint_skipped_reason"] == "plan_only"
    assert due["new_record_count"] == 199
    assert due["pending_since"] == old_pending


def test_journal_below_threshold_status_preserves_last_checkpoint(tmp_path: Path):
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("\n".join(json.dumps({"i": i}) for i in range(200)) + "\n", encoding="utf-8")
    status_path = data_path(hub, "central_reports") / "journal_checkpoint_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    checkpointed_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    status_path.write_text(
        json.dumps(
            {
                "checkpoint_record_count": 199,
                "last_checkpoint_at": checkpointed_at,
            }
        ),
        encoding="utf-8",
    )

    status = checkpoint_journal(
        hub,
        tmp_path / "dad-journal",
        apply=False,
        min_records=200,
        min_hours=24,
    )

    assert status["checkpoint_skipped_reason"] == "threshold_not_met"
    assert status["checkpointed_at"] == checkpointed_at
    saved = json.loads(status_path.read_text(encoding="utf-8"))
    assert saved["checkpointed_at"] == checkpointed_at
    assert journal_status(hub, min_records=200, min_hours=24)["last_checkpoint_at"] == checkpointed_at


def test_daemon_checkpoint_failure_finalizes_degraded_heartbeat(tmp_path: Path):
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("\n".join(json.dumps({"i": i}) for i in range(200)) + "\n", encoding="utf-8")
    journal_repo = tmp_path / "not-a-git-journal"
    journal_repo.mkdir()

    result = run_daemon_cycle(
        hub,
        mail_repos=[],
        exception_repos=[],
        transport_repos=[],
        journal_repo=journal_repo,
        checkpoint_apply=True,
    )

    heartbeat = json.loads((hub / "processed" / "reports" / "daemon-heartbeat.json").read_text(encoding="utf-8"))
    assert result["journal"]["status"] == "error"
    assert heartbeat["status"] == "complete_with_errors"
    assert heartbeat["cycle_completed_at"]
    assert heartbeat["heartbeat_finalized"] is True
    assert heartbeat["journal_checkpoint_applied"] is False
    assert daemon_status(hub)["status"] == "degraded"


def test_journal_locked_copy_does_not_advance_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    hub = tmp_path / "hub"
    inbox = hub / "processed" / "mail" / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        "\n".join(json.dumps({"i": i}) for i in range(200)) + "\n",
        encoding="utf-8",
    )
    journal_repo = tmp_path / "dad-journal"
    subprocess.run(["git", "init", "-b", "journal-data", str(journal_repo)], check=True)

    def locked_copy(_source: Path, _destination: Path) -> None:
        error = PermissionError("synthetic live-file lock")
        error.winerror = 32
        raise error

    monkeypatch.setattr(journal_mod, "_copy_checkpoint_file", locked_copy)

    result = checkpoint_journal(
        hub,
        journal_repo,
        apply=True,
        min_records=200,
        min_hours=999,
    )

    assert result["status"] == "blocked"
    assert result["checkpoint_applied"] is False
    assert result["checkpoint_skipped_reason"] == "copy_incomplete"
    assert result["copy_error_count"] == 1
    assert result["copy_errors"][0]["winerror"] == 32
    assert result["checkpoint_due"] is True
    assert result["checkpoint_record_count"] == 0
    assert "git_apply_results" not in result
    assert not (journal_repo / "journal_checkpoint_manifest.json").exists()


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
    nested_git_object = (
        hub
        / "processed"
        / "mail"
        / "_synthetic"
        / "temp-repo"
        / ".git"
        / "objects"
        / "aa"
        / "object-file"
    )
    nested_git_object.parent.mkdir(parents=True)
    nested_git_object.write_text("must-not-journal-vcs-internals", encoding="utf-8")
    remote = tmp_path / "dad-journal-remote.git"
    journal_repo = tmp_path / "dad-journal"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-b", "journal-data", str(journal_repo)], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "config", "user.email", "dad@example.test"], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "config", "user.name", "DAD Test"], check=True)
    subprocess.run(["git", "-C", str(journal_repo), "remote", "add", "origin", str(remote)], check=True)

    result = checkpoint_journal(hub, journal_repo, apply=True, min_records=200, min_hours=999)

    assert result["checkpoint_applied"] is True
    assert result["commands"][0].endswith("config core.longpaths true")
    assert result["git_apply_results"][0]["returncode"] == 0
    assert journal_status(hub, min_records=200, min_hours=999)["checkpoint_due"] is False
    assert (journal_repo / "data" / "processed" / "mail" / "inbox" / "rows.jsonl").exists()
    assert not (journal_repo / "data" / "src" / "not-data-plane.jsonl").exists()
    assert not (
        journal_repo
        / "data"
        / "processed"
        / "mail"
        / "_synthetic"
        / "temp-repo"
        / ".git"
        / "objects"
        / "aa"
        / "object-file"
    ).exists()
    manifest = json.loads((journal_repo / "journal_checkpoint_manifest.json").read_text())
    assert manifest["checkpoint_scope"] == "DATA_PLANE_PATHS"
    head = subprocess.run(
        ["git", "-C", str(journal_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    remote_head = subprocess.run(
        ["git", "-C", str(remote), "rev-parse", "journal-data"],
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
