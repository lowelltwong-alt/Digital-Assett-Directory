from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
import os
from threading import Event, Thread, current_thread
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from jsonschema import ValidationError
from typer.testing import CliRunner

import digital_asset_directory.cli as cli_module
import digital_asset_directory.operational_cockpit as cockpit_module
from digital_asset_directory.cli import app
from digital_asset_directory.portfolio_cockpit import build_portfolio_cockpit
from digital_asset_directory.operational_cockpit import (
    MAX_SOURCE_BYTES,
    build_operational_cockpit,
    build_operational_cockpit_server,
    operational_cockpit_html,
    validate_operational_cockpit,
    write_operational_cockpit,
)
from digital_asset_directory.portfolio_convergence import (
    BranchEvidence,
    PairDistance,
    branch_pair_key,
    finalize_report,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 19, 4, tzinfo=timezone.utc)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _source_paths(hub: Path) -> dict[str, Path]:
    return {
        "portfolio_v1": hub / "processed/reports/portfolio_os/cockpit.json",
        "portfolio_v2": hub / "processed/reports/portfolio_os/cockpit-v2.json",
        "convergence_radar": hub / "processed/reports/portfolio_os/convergence-radar.json",
        "capability_os": hub / "processed/portfolio_os/capability-os-cockpit.json",
        "daemon": hub / "processed/reports/daemon-heartbeat.json",
        "event_pipeline": hub / "processed/events/reports/event_pipeline.json",
    }


def _seed_sources(hub: Path, *, timestamp: datetime = NOW) -> None:
    for schema_name in (
        "portfolio-convergence-report.schema.json",
        "operational-cockpit.schema.json",
        "portfolio-cockpit.schema.json",
        "portfolio-cockpit-v2.schema.json",
        "capability-os-cockpit.schema.json",
    ):
        schema_target = hub / "schemas" / schema_name
        schema_target.parent.mkdir(parents=True, exist_ok=True)
        schema_target.write_text(
            (ROOT / "schemas" / schema_name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    generated = timestamp.isoformat()
    paths = _source_paths(hub)
    portfolio_v1 = build_portfolio_cockpit(
        None,
        None,
        now=timestamp,
        schema_root=ROOT / "schemas",
    )
    portfolio_v1["summary"].update(
        {
            "project_count": 12,
            "branch_count": 48,
            "worktree_count": 17,
            "workstream_count": 9,
            "attention_item_count": 6,
            "unknown_count": 2,
            "unassigned_attention_count": 1,
            "all_clear": False,
        }
    )
    _write_json(paths["portfolio_v1"], portfolio_v1)
    item_fingerprint = "sha256:" + "a" * 64
    v2_item = {
        "attention_id": "dad:attention:test",
        "source": "portfolio_v1",
        "band": "human_decision",
        "label": "Review stale branch evidence",
        "family_id": "",
        "reasons": ["fixture"],
        "next_action": "inspect",
        "human_decision_required": True,
        "selected_now": True,
        "fingerprint": item_fingerprint,
        "evidence_refs": ["portfolio-v1:today"],
    }
    _write_json(
        paths["portfolio_v2"],
        {
            "schema_version": "dad.portfolio_cockpit.v2",
            "generated_at": generated,
            "status": "generated_candidate",
            "candidate_only": True,
            "execution_authorized": False,
            "authority_boundary": "Candidate-only portfolio overlay; no execution authority.",
            "sources": {
                "portfolio_v1": {
                    "status": "observed",
                    "schema_version": "dad.portfolio_cockpit.v1",
                    "fingerprint": item_fingerprint,
                    "problems": [],
                },
                "agent_families": {
                    "status": "observed",
                    "schema_version": "dad.agent_family_health.v1",
                    "fingerprint": item_fingerprint,
                    "problems": [],
                },
            },
            "summary": {
                "now_count": 1,
                "digest_count": 1,
                "family_count": 0,
                "family_issue_count": 0,
                "portfolio_item_count": 1,
                "capability_item_count": 0,
            },
            "now": [v2_item],
            "digest": [v2_item],
            "source_refs": {
                "portfolio_v1": item_fingerprint,
                "agent_families": item_fingerprint,
            },
        },
    )
    _write_json(
        paths["capability_os"],
        {
            "schema_version": "dad.capability_os_cockpit.v1",
            "generated_at": generated,
            "cockpit_id": "dad:capability-os-cockpit:test",
            "views": {},
            "decisions": [{"title": "Review portability gap", "recommended_action": "inspect"}],
            "controls": [],
            "maximum_immediate_decisions": 3,
            "local_bind": "127.0.0.1",
            "external_javascript": False,
            "candidate_only": True,
            "execution_authorized": False,
            "authority_boundary": "Candidate-only local cockpit; no execution authority.",
        },
    )
    left = BranchEvidence(
        project_id="dad:project:test",
        project_name="DAD",
        branch_name="codex/cockpit-refresh-a",
        head="a" * 40,
        default_branch="main",
        name_tokens=("cockpit", "refresh"),
        touched_paths=("src/cockpit.py", "tests/test_cockpit.py"),
    )
    right = BranchEvidence(
        project_id="dad:project:test",
        project_name="DAD",
        branch_name="codex/cockpit-refresh-b",
        head="b" * 40,
        default_branch="main",
        name_tokens=("cockpit", "refresh"),
        touched_paths=("src/cockpit.py",),
    )
    convergence_report = finalize_report(
        generated_at=generated,
        source={
            "schema_version": "dad.portfolio_attention.v1",
            "generated_at": generated,
            "fingerprint": "sha256:" + "d" * 64,
            "project_count": 1,
        },
        branches=[left, right],
        distances={
            branch_pair_key(left, right): PairDistance(
                status="observed",
                merge_base="c" * 40,
                left_commits=2,
                right_commits=3,
            )
        },
        producer={
            "producer_id": "test-observer",
            "producer_revision_id": "test-observer:0.1.0",
            "observation_count": 2,
            "source_write_count": 0,
            "bounded": True,
            "problems_recorded": True,
            "details": {},
        },
    )
    _write_json(paths["convergence_radar"], convergence_report)
    _write_json(
        paths["daemon"],
        {
            "schema_version": "dad.daemon.heartbeat.v1",
            "generated_at": generated,
            "cycle_completed_at": generated,
            "status": "complete",
            "reporting_privacy": {},
            "authority_boundary": "read-only local daemon heartbeat evidence",
            "heartbeat_finalized": True,
        },
    )
    _write_json(
        paths["event_pipeline"],
        {
            "schema_version": "dad.event_pipeline.report.v1",
            "generated_at": generated,
            "event_count": 8,
            "response_state_count": 3,
            "notice_without_response_state_count": 1,
            "authority_boundary": "candidate-only event evidence",
        },
    )


def _stub_refresh_producers(monkeypatch: pytest.MonkeyPatch, *, fail_at: str = "") -> list[str]:
    calls: list[str] = []

    def called(name: str, value: object) -> object:
        calls.append(name)
        if name == fail_at:
            raise ValueError(f"{name}_failed")
        return value

    monkeypatch.setattr(
        cli_module,
        "_v1_attention_report",
        lambda _root: called("portfolio_v1_read", {"attention": []}),
    )
    monkeypatch.setattr(
        cli_module,
        "load_workstream_state",
        lambda _root, portfolio_snapshot: called(
            "portfolio_v1_fold", {"snapshot": portfolio_snapshot}
        ),
    )
    monkeypatch.setattr(
        cli_module,
        "build_portfolio_cockpit",
        lambda *_args, **_kwargs: called("portfolio_v1_build", {"v1": True}),
    )
    monkeypatch.setattr(
        cli_module,
        "write_portfolio_cockpit_outputs",
        lambda *_args: called("portfolio_v1", {"json_path": "v1.json"}),
    )
    monkeypatch.setattr(
        cli_module,
        "agent_family_health",
        lambda _root: called("portfolio_v2_health", {"health": True}),
    )
    monkeypatch.setattr(
        cli_module,
        "build_capability_portfolio_snapshot",
        lambda _root: called("portfolio_v2_snapshot", {"capabilities": []}),
    )
    monkeypatch.setattr(
        cli_module,
        "build_portfolio_cockpit_v2",
        lambda *_args: called("portfolio_v2_build", {"v2": True}),
    )
    monkeypatch.setattr(
        cli_module,
        "write_agent_family_health",
        lambda *_args: called("portfolio_v2_health_write", {"json_path": "health.json"}),
    )
    monkeypatch.setattr(
        cli_module,
        "write_portfolio_cockpit_v2",
        lambda *_args: called("portfolio_v2", {"json_path": "v2.json"}),
    )
    monkeypatch.setattr(
        cli_module,
        "build_capability_os_cockpit",
        lambda *_args, **_kwargs: called("capability_os_build", {"capability": True}),
    )
    monkeypatch.setattr(
        cli_module,
        "write_capability_os_cockpit",
        lambda *_args: called("capability_os", {"json_path": "capability.json"}),
    )
    monkeypatch.setattr(
        cli_module,
        "write_event_pipeline_report",
        lambda _root: called("event_pipeline", {"json_path": "events.json"}),
    )
    monkeypatch.setattr(
        cli_module,
        "build_operational_cockpit",
        lambda _root: called(
            "operational_cockpit_build",
            {"status": "partial_candidate", "summary": {"current_count": 4}},
        ),
    )
    monkeypatch.setattr(
        cli_module,
        "write_operational_cockpit",
        lambda *_args: called("operational_cockpit", {"json_path": "operational.json"}),
    )
    for forbidden in (
        "run_daemon_cycle",
        "collect_events",
        "build_portfolio_attention_report",
    ):
        monkeypatch.setattr(
            cli_module,
            forbidden,
            lambda *_args, _name=forbidden, **_kwargs: pytest.fail(
                f"forbidden producer called: {_name}"
            ),
        )
    return calls


def test_missing_sources_are_partial_and_never_false_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    cockpit = build_operational_cockpit(tmp_path, now=NOW)

    validate_operational_cockpit(ROOT, cockpit)
    assert cockpit["status"] == "partial_candidate"
    assert cockpit["summary"] == {
        "source_count": 6,
        "current_count": 0,
        "stale_count": 0,
        "missing_count": 6,
        "invalid_count": 0,
        "immediate_decision_count": 0,
        "all_sources_current": False,
    }
    assert all(row["status"] == "missing" for row in cockpit["sources"].values())
    overview = cockpit["operator_overview"]
    assert overview["portfolio_scope"]["availability"] == "unavailable"
    assert overview["portfolio_scope"]["project_count"] is None
    assert overview["convergence"]["availability"] == "unavailable"
    assert overview["convergence"]["candidate_count"] is None
    assert overview["convergence"]["top_candidates"] == []
    assert overview["readiness"]["source_gap_count"] == 6
    assert len(overview["readiness"]["source_actions"]) == 6
    assert cockpit["execution_authorized"] is False


def test_current_sources_compose_bounded_decisions_and_event_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)

    first = build_operational_cockpit(tmp_path, now=NOW)
    second = build_operational_cockpit(tmp_path, now=NOW)

    validate_operational_cockpit(ROOT, first)
    assert first == second
    assert first["status"] == "current_candidate"
    assert first["summary"]["all_sources_current"] is True
    assert len(first["decisions"]) == 2
    assert first["event_pulse"]["event_count"] == 8
    assert first["event_pulse"]["cursor_fingerprint"].startswith("sha256:")
    assert first["operator_overview"]["portfolio_scope"] == {
        "availability": "current",
        "source_id": "portfolio_v1",
        "source_fingerprint": first["sources"]["portfolio_v1"]["fingerprint"],
        "project_count": 12,
        "branch_count": 48,
        "worktree_count": 17,
        "workstream_count": 9,
        "attention_item_count": 6,
        "unknown_count": 2,
        "unassigned_attention_count": 1,
        "all_clear": False,
    }
    assert first["operator_overview"]["readiness"]["source_gap_count"] == 0
    convergence = first["operator_overview"]["convergence"]
    assert convergence["availability"] == "current"
    assert convergence["candidate_count"] == 1
    assert convergence["evaluated_pair_count"] == 1
    assert len(convergence["top_candidates"]) == 1
    assert convergence["top_candidates"][0]["shared_touched_path_count"] == 1
    assert convergence["top_candidates"][0]["execution_authorized"] is False

    assert first["adapter_contract"]["core_kind"] == "portable_core"
    assert first["adapter_contract"]["rollout"] == "reviewed_opt_in_enrollment_wave"


def test_stale_and_invalid_sources_remain_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path, timestamp=NOW - timedelta(days=2))
    event_path = _source_paths(tmp_path)["event_pipeline"]
    event_path.write_text("not-json", encoding="utf-8")

    cockpit = build_operational_cockpit(
        tmp_path,
        now=NOW,
        stale_after_seconds=60,
    )

    validate_operational_cockpit(ROOT, cockpit)
    assert cockpit["status"] == "partial_candidate"
    assert cockpit["summary"]["stale_count"] == 5
    assert cockpit["summary"]["invalid_count"] == 1
    assert cockpit["sources"]["event_pipeline"]["problems"] == ["source_unreadable_or_invalid_json"]


def test_source_read_budget_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    event_path = _source_paths(tmp_path)["event_pipeline"]
    event_path.write_bytes(b" " * (MAX_SOURCE_BYTES + 1))

    cockpit = build_operational_cockpit(tmp_path, now=NOW)

    assert cockpit["status"] == "partial_candidate"
    assert cockpit["sources"]["event_pipeline"]["status"] == "invalid"
    assert cockpit["sources"]["event_pipeline"]["problems"] == ["source_exceeds_read_budget"]
    assert cockpit["event_pulse"]["event_count"] is None

    _seed_sources(tmp_path)
    assert event_path.stat().st_size < MAX_SOURCE_BYTES
    original_open = Path.open

    def growing_open(path: Path, *args: object, **kwargs: object) -> object:
        if path == event_path and args and args[0] == "rb":
            return BytesIO(b" " * (MAX_SOURCE_BYTES + 1))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", growing_open)
    raced = build_operational_cockpit(tmp_path, now=NOW)
    assert raced["sources"]["event_pipeline"]["problems"] == ["source_exceeds_read_budget"]


def test_cli_check_reports_readiness_without_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".dad-data-root.json").write_text(
        json.dumps({"hub_ref": str(ROOT.resolve())}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DAD_DATA_ROOT", str(tmp_path))
    _seed_sources(tmp_path)
    output_root = tmp_path / "processed/reports/portfolio_os"
    output_paths = [
        output_root / "operational-cockpit.json",
        output_root / "operational-cockpit.html",
        output_root / "operational-cockpit.receipt.json",
    ]

    result = CliRunner().invoke(
        app,
        ["os", "operational-cockpit", "--check", "--hub", str(ROOT)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["published"] is False
    assert payload["status"] == "current_candidate"
    assert payload["operator_overview"]["portfolio_scope"]["project_count"] == 12
    assert all(not path.exists() for path in output_paths)


def test_refresh_now_runs_only_bounded_producers_in_dependency_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _stub_refresh_producers(monkeypatch)
    cfg = type("Cfg", (), {"repo_root": tmp_path})()

    result = cli_module._refresh_operational_cockpit_now(cfg)

    assert result["status"] == "refreshed"
    assert result["completed_sources"] == [
        "portfolio_v1",
        "portfolio_v2",
        "capability_os",
        "event_pipeline",
    ]
    assert result["excluded_source"] == "daemon"
    assert result["evidence_status"] == "partial_candidate"
    assert result["operational_cockpit_published"] is True
    assert result["daemon_cycle_run"] is False
    assert result["cross_repo_scan_run"] is False
    assert result["event_collection_run"] is False
    assert calls == [
        "portfolio_v1_read",
        "portfolio_v1_fold",
        "portfolio_v1_build",
        "portfolio_v1",
        "portfolio_v2_health",
        "portfolio_v2_snapshot",
        "portfolio_v2_build",
        "portfolio_v2_health_write",
        "portfolio_v2",
        "capability_os_build",
        "capability_os",
        "event_pipeline",
        "operational_cockpit_build",
        "operational_cockpit",
    ]


@pytest.mark.parametrize(
    ("fail_at", "completed"),
    [
        ("portfolio_v1", []),
        ("portfolio_v2", ["portfolio_v1"]),
        ("capability_os", ["portfolio_v1", "portfolio_v2"]),
        (
            "event_pipeline",
            ["portfolio_v1", "portfolio_v2", "capability_os"],
        ),
        (
            "operational_cockpit_build",
            ["portfolio_v1", "portfolio_v2", "capability_os", "event_pipeline"],
        ),
        (
            "operational_cockpit",
            ["portfolio_v1", "portfolio_v2", "capability_os", "event_pipeline"],
        ),
    ],
)
def test_refresh_failure_never_publishes_a_new_operational_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_at: str,
    completed: list[str],
) -> None:
    calls = _stub_refresh_producers(monkeypatch, fail_at=fail_at)
    cfg = type("Cfg", (), {"repo_root": tmp_path})()

    result = cli_module._refresh_operational_cockpit_now(cfg)

    assert result["status"] == "refresh_failed"
    assert result["completed_sources"] == completed
    assert result["operational_cockpit_published"] is False
    assert result["daemon_cycle_run"] is False
    assert result["cross_repo_scan_run"] is False
    assert result["event_collection_run"] is False
    assert calls.count("operational_cockpit") == (1 if fail_at == "operational_cockpit" else 0)


def test_in_progress_daemon_heartbeat_cannot_make_cockpit_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    daemon_path = _source_paths(tmp_path)["daemon"]
    heartbeat = json.loads(daemon_path.read_text(encoding="utf-8"))
    heartbeat.update(
        {
            "status": "in_progress",
            "generated_at": NOW.isoformat(),
            "cycle_completed_at": "",
            "heartbeat_finalized": False,
        }
    )
    _write_json(daemon_path, heartbeat)

    cockpit = build_operational_cockpit(tmp_path, now=NOW)

    assert cockpit["status"] == "partial_candidate"
    assert cockpit["summary"]["current_count"] == 5
    assert cockpit["summary"]["invalid_count"] == 1
    assert cockpit["sources"]["daemon"]["status"] == "invalid"
    assert cockpit["sources"]["daemon"]["freshness"] == "unknown"
    assert cockpit["sources"]["daemon"]["problems"] == [
        "authority_contract_violation:heartbeat_finalized,status"
    ]


def test_timezone_less_producer_timestamps_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    paths = _source_paths(tmp_path)

    heartbeat = json.loads(paths["daemon"].read_text(encoding="utf-8"))
    heartbeat["cycle_completed_at"] = "2026-07-19T04:00:00"
    _write_json(paths["daemon"], heartbeat)

    event = json.loads(paths["event_pipeline"].read_text(encoding="utf-8"))
    event["generated_at"] = "2026-07-19"
    _write_json(paths["event_pipeline"], event)

    cockpit = build_operational_cockpit(tmp_path, now=NOW)

    assert cockpit["status"] == "partial_candidate"
    assert cockpit["summary"]["invalid_count"] == 2
    for source_id in ("daemon", "event_pipeline"):
        assert cockpit["sources"][source_id]["problems"] == ["timestamp_missing_or_invalid"]


def test_authoritative_schema_range_and_future_violations_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    paths = _source_paths(tmp_path)
    originals = {
        name: json.loads(paths[name].read_text(encoding="utf-8"))
        for name in ("portfolio_v1", "portfolio_v2", "capability_os", "event_pipeline")
    }

    portfolio_v1 = dict(originals["portfolio_v1"])
    portfolio_v1["status"] = "false_green"
    _write_json(paths["portfolio_v1"], portfolio_v1)

    portfolio_v2 = dict(originals["portfolio_v2"])
    portfolio_v2.pop("authority_boundary")
    _write_json(paths["portfolio_v2"], portfolio_v2)

    capability = dict(originals["capability_os"])
    capability["local_bind"] = "0.0.0.0"
    _write_json(paths["capability_os"], capability)

    event = dict(originals["event_pipeline"])
    event["event_count"] = -1
    _write_json(paths["event_pipeline"], event)

    cockpit = build_operational_cockpit(tmp_path, now=NOW)

    assert cockpit["status"] == "partial_candidate"
    assert cockpit["summary"]["invalid_count"] == 4
    for source_id in ("portfolio_v1", "portfolio_v2", "capability_os"):
        assert cockpit["sources"][source_id]["problems"] == [
            "authoritative_schema_validation_failed"
        ]
    assert cockpit["sources"]["event_pipeline"]["problems"] == ["invalid_field_ranges:event_count"]
    assert cockpit["decisions"] == []
    assert cockpit["event_pulse"]["event_count"] is None

    for name, value in originals.items():
        _write_json(paths[name], value)
    future_v2 = dict(originals["portfolio_v2"])
    future_v2["generated_at"] = (NOW + timedelta(days=365)).isoformat()
    _write_json(paths["portfolio_v2"], future_v2)
    future_only = build_operational_cockpit(tmp_path, now=NOW)
    assert future_only["sources"]["portfolio_v2"]["problems"] == ["timestamp_too_far_in_future"]


def test_semantically_inconsistent_snapshot_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    cockpit = build_operational_cockpit(tmp_path, now=NOW)
    cockpit["summary"]["invalid_count"] = 1

    with pytest.raises((ValidationError, ValueError)):
        validate_operational_cockpit(ROOT, cockpit)

    missing_privacy = build_operational_cockpit(tmp_path, now=NOW)
    missing_privacy.pop("data_classification")
    with pytest.raises(ValidationError):
        validate_operational_cockpit(ROOT, missing_privacy)

    contradictory = build_operational_cockpit(tmp_path, now=NOW)
    contradictory["status"] = "partial_candidate"
    contradictory["summary"]["current_count"] = 5
    contradictory["summary"]["stale_count"] = 1
    contradictory["summary"]["all_sources_current"] = False
    contradictory["sources"]["portfolio_v1"]["status"] = "stale"
    contradictory["sources"]["portfolio_v1"]["freshness"] = "current"
    contradictory["sources"]["portfolio_v1"]["problems"] = ["source_stale"]
    with pytest.raises(ValidationError):
        validate_operational_cockpit(ROOT, contradictory)

    mismatched_readiness = build_operational_cockpit(tmp_path, now=NOW)
    mismatched_readiness["operator_overview"]["readiness"]["source_gap_count"] = 1
    with pytest.raises((ValidationError, ValueError)):
        validate_operational_cockpit(ROOT, mismatched_readiness)

    misdirected = build_operational_cockpit(tmp_path / "missing-sources", now=NOW)
    misdirected["operator_overview"]["readiness"]["source_actions"][0]["owner"] = "wrong-owner"
    with pytest.raises(ValueError, match="operator readiness"):
        validate_operational_cockpit(ROOT, misdirected)


def test_operational_publication_failure_restores_prior_coherent_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    prior = build_operational_cockpit(tmp_path, now=NOW)
    outputs = write_operational_cockpit(tmp_path, prior)
    paths = [
        Path(outputs["html_path"]),
        Path(outputs["json_path"]),
        Path(outputs["receipt_path"]),
    ]
    prior_text = {path: path.read_text(encoding="utf-8") for path in paths}

    capability_path = _source_paths(tmp_path)["capability_os"]
    capability = json.loads(capability_path.read_text(encoding="utf-8"))
    capability["decisions"][0]["title"] = "Changed generation"
    _write_json(capability_path, capability)
    replacement = build_operational_cockpit(tmp_path, now=NOW)
    assert replacement["snapshot_id"] != prior["snapshot_id"]

    original_atomic_write = cockpit_module.atomic_write_text
    write_count = 0

    def fail_on_json(path: Path, value: str) -> None:
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("injected publication interruption")
        original_atomic_write(path, value)

    monkeypatch.setattr(cockpit_module, "atomic_write_text", fail_on_json)

    with pytest.raises(OSError, match="injected publication interruption"):
        write_operational_cockpit(tmp_path, replacement)

    assert write_count == 5
    assert {path: path.read_text(encoding="utf-8") for path in paths} == prior_text


def test_operational_publication_lock_preserves_newer_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    prior = build_operational_cockpit(tmp_path, now=NOW)
    write_operational_cockpit(tmp_path, prior)

    capability_path = _source_paths(tmp_path)["capability_os"]
    capability = json.loads(capability_path.read_text(encoding="utf-8"))
    capability["decisions"][0]["title"] = "Interrupted generation"
    _write_json(capability_path, capability)
    interrupted = build_operational_cockpit(tmp_path, now=NOW)
    capability["decisions"][0]["title"] = "Newer generation"
    _write_json(capability_path, capability)
    newer = build_operational_cockpit(tmp_path, now=NOW)

    original_atomic_write = cockpit_module.atomic_write_text
    first_write_started = Event()
    release_first_writer = Event()
    newer_writer_done = Event()
    errors: list[BaseException] = []
    interrupted_write_count = 0

    def controlled_write(path: Path, value: str) -> None:
        nonlocal interrupted_write_count
        if current_thread().name == "interrupted-cockpit-writer":
            interrupted_write_count += 1
            if interrupted_write_count == 1:
                original_atomic_write(path, value)
                first_write_started.set()
                assert release_first_writer.wait(timeout=2)
                return
            if interrupted_write_count == 2:
                raise OSError("injected publication interruption")
        original_atomic_write(path, value)

    def publish_interrupted() -> None:
        try:
            write_operational_cockpit(tmp_path, interrupted)
        except OSError as exc:
            errors.append(exc)

    def publish_newer() -> None:
        try:
            write_operational_cockpit(tmp_path, newer)
        finally:
            newer_writer_done.set()

    monkeypatch.setattr(cockpit_module, "atomic_write_text", controlled_write)
    interrupted_thread = Thread(target=publish_interrupted, name="interrupted-cockpit-writer")
    newer_thread = Thread(target=publish_newer, name="newer-cockpit-writer")
    interrupted_thread.start()
    newer_started = False
    try:
        assert first_write_started.wait(timeout=20)
        newer_thread.start()
        newer_started = True
        assert not newer_writer_done.wait(timeout=0.1)
    finally:
        release_first_writer.set()
        interrupted_thread.join(timeout=20)
        if newer_started:
            newer_thread.join(timeout=20)

    assert newer_started

    assert not interrupted_thread.is_alive()
    assert not newer_thread.is_alive()
    assert len(errors) == 1
    assert "injected publication interruption" in str(errors[0])
    root = tmp_path / "processed/reports/portfolio_os"
    bundle = cockpit_module._validated_bundle(
        tmp_path,
        root / "operational-cockpit.json",
        root / "operational-cockpit.html",
        root / "operational-cockpit.receipt.json",
    )
    assert bundle is not None
    assert bundle[2]["snapshot_id"] == newer["snapshot_id"]


def test_publication_lock_blocks_a_separate_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    root = tmp_path / "processed/reports/portfolio_os"
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from digital_asset_directory.operational_cockpit import _publication_lock\n"
        "with _publication_lock(Path(sys.argv[1])):\n"
        "    print('locked', flush=True)\n"
        "    sys.stdin.readline()\n"
    )
    env = os.environ.copy()
    env.pop("DAD_DATA_ROOT", None)
    env["PYTHONPATH"] = str(ROOT / "src")
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(root)],
        cwd=ROOT,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready = Event()
    ready_line: list[str] = []
    attempted = Event()
    acquired = Event()
    contender_errors: list[BaseException] = []

    def read_ready() -> None:
        assert child.stdout is not None
        ready_line.append(child.stdout.readline())
        ready.set()

    def contend() -> None:
        try:
            attempted.set()
            with cockpit_module._publication_lock(root):
                acquired.set()
        except BaseException as exc:
            contender_errors.append(exc)

    reader = Thread(target=read_ready, name="cockpit-lock-child-reader")
    contender = Thread(target=contend, name="cockpit-lock-contender")
    reader.start()
    try:
        assert ready.wait(timeout=20)
        assert ready_line == ["locked\n"]
        contender.start()
        assert attempted.wait(timeout=20)
        assert not acquired.wait(timeout=0.1)
    finally:
        if child.stdin is not None and child.poll() is None:
            child.stdin.write("\n")
            child.stdin.flush()
        child.wait(timeout=20)
    reader.join(timeout=20)
    contender.join(timeout=20)

    assert not reader.is_alive()
    assert not contender.is_alive()
    assert child.returncode == 0, child.stderr.read() if child.stderr is not None else ""
    assert not contender_errors
    assert acquired.is_set()


def test_html_is_accessible_script_free_and_escapes_source_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    cockpit = build_operational_cockpit(tmp_path, now=NOW)
    cockpit["decisions"][0]["label"] = "<script>alert(1)</script>"

    html = operational_cockpit_html(cockpit)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script" not in html.lower()
    assert "<button" not in html.lower()
    assert 'scope="col"' in html
    assert 'role="status"' in html
    assert "prefers-reduced-motion" in html
    assert "DAD Â·" not in html
    assert "&middot;" in html
    assert 'href="#main"' in html
    assert 'aria-label="Cockpit sections"' in html
    for section in ("decisions", "portfolio", "convergence", "signals", "sources", "contract"):
        assert f'href="#{section}"' in html
        assert f'id="{section}"' in html
    assert "Unknown is never shown as zero." in html
    assert "12</strong>projects" in html
    assert "Evidence references" in html

    assert "Convergence candidates" in html
    assert "codex/cockpit-refresh-a" in html
    assert "src/cockpit.py" not in html
    assert "No action is authorized" in html


def test_foreground_host_is_loopback_read_only_and_route_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    _seed_sources(tmp_path)
    cockpit = build_operational_cockpit(tmp_path, now=NOW)
    write_operational_cockpit(tmp_path, cockpit)
    server = build_operational_cockpit_server(tmp_path, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/", timeout=2) as response:
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert b"DAD Operational Cockpit" in response.read()
        with urlopen(base + "/api/snapshot", timeout=2) as response:
            payload = json.loads(response.read())
            assert payload["snapshot_id"] == cockpit["snapshot_id"]
        with urlopen(base + "/healthz", timeout=2) as response:
            health = json.loads(response.read())
            assert health["execution_authorized"] is False
            assert health["serving_status"] == "coherent"
            assert health["evidence_status"] == "current_candidate"
            assert health["snapshot_id"] == cockpit["snapshot_id"]
        with pytest.raises(HTTPError) as disallowed_host:
            urlopen(Request(base + "/", headers={"Host": "evil.example"}), timeout=2)
        assert disallowed_host.value.code == 421
        for method in (
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
            "TRACE",
            "CONNECT",
            "MKCOL",
            "PROPFIND",
            "PROPPATCH",
            "COPY",
            "MOVE",
            "LOCK",
            "UNLOCK",
        ):
            with pytest.raises(HTTPError) as denied:
                urlopen(Request(base + "/api/snapshot", method=method), timeout=2)
            assert denied.value.code == 405
            assert denied.value.headers["Allow"] == "GET, HEAD"
        with pytest.raises(HTTPError) as missing:
            urlopen(base + "/../secret", timeout=2)
        assert missing.value.code == 404

        html_path = tmp_path / "processed/reports/portfolio_os/operational-cockpit.html"
        html_path.write_text("transient mismatched generation", encoding="utf-8")
        with urlopen(base + "/", timeout=2) as response:
            assert b"DAD Operational Cockpit" in response.read()
        with urlopen(base + "/api/snapshot", timeout=2) as response:
            assert json.loads(response.read())["snapshot_id"] == cockpit["snapshot_id"]
        with urlopen(base + "/healthz", timeout=2) as response:
            assert json.loads(response.read())["status"] == "serving"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    invalid_server = build_operational_cockpit_server(tmp_path, port=0)
    invalid_thread = Thread(target=invalid_server.serve_forever, daemon=True)
    invalid_thread.start()
    invalid_base = f"http://127.0.0.1:{invalid_server.server_port}"
    try:
        for route in ("/", "/api/snapshot", "/healthz"):
            with pytest.raises(HTTPError) as invalid_bundle:
                urlopen(invalid_base + route, timeout=2)
            assert invalid_bundle.value.code == 503
    finally:
        invalid_server.shutdown()
        invalid_server.server_close()
        invalid_thread.join(timeout=2)

    with pytest.raises(ValueError, match="must bind 127.0.0.1"):
        build_operational_cockpit_server(tmp_path, host="0.0.0.0", port=0)
