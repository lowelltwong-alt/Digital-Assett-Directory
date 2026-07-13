from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from digital_asset_directory import cli

pytestmark = pytest.mark.unit


def test_recovery_commands_are_public() -> None:
    runner = CliRunner()
    for command in ("decide", "decision-retract", "recovery-packet", "recovery-result"):
        result = runner.invoke(cli.app, ["os", command, "--help"])
        assert result.exit_code == 0, result.output


def test_decide_routes_exact_snapshot_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    shaping = {"schema_version": "dad.portfolio_workstream_shaping.v2"}
    monkeypatch.setattr(cli, "_cfg", lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path))
    monkeypatch.setattr(
        cli,
        "_rebuild_current_recovery_shaping",
        lambda _cfg: ({}, {}, {}, shaping, {}),
    )

    def record(hub: Path, current: dict[str, object], **kwargs: object) -> dict[str, object]:
        captured.update({"hub": hub, "shaping": current, **kwargs})
        return {"status": "recorded", "decision_id": "dad:portfolio-decision:test"}

    monkeypatch.setattr(cli, "record_shaping_decision", record)
    result = CliRunner().invoke(
        cli.app,
        [
            "os",
            "decide",
            "dad:case:test",
            "--revision-id",
            "dad:revision:test",
            "--choice-id",
            "dad:choice:test",
            "--source-snapshot-digest",
            "sha256:" + "1" * 64,
            "--preconditions-digest",
            "sha256:" + "2" * 64,
            "--approver",
            "human",
            "--approval-ref",
            "approval:test",
            "--request-id",
            "request:test",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["hub"] == tmp_path
    assert captured["shaping"] is shaping
    assert captured["case_id"] == "dad:case:test"
    assert captured["case_revision_id"] == "dad:revision:test"
    assert captured["expected_source_snapshot_digest"] == "sha256:" + "1" * 64
    assert captured["expected_preconditions_digest"] == "sha256:" + "2" * 64


def test_recovery_result_requires_matching_transient_packet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps({"packet_id": "packet:one"}), encoding="utf-8")
    monkeypatch.setattr(cli, "_cfg", lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path))
    called = False

    def rebuild(_cfg):
        nonlocal called
        called = True
        return {}, {}, {}, {}, {}

    monkeypatch.setattr(cli, "_rebuild_current_recovery_shaping", rebuild)
    result = CliRunner().invoke(
        cli.app,
        [
            "os",
            "recovery-result",
            "packet:other",
            "--packet-file",
            str(packet_path),
            "--status",
            "verified",
            "--before-snapshot-digest",
            "sha256:" + "3" * 64,
            "--after-snapshot-digest",
            "sha256:" + "4" * 64,
            "--worker-id",
            "worker",
            "--checker-id",
            "checker",
            "--evidence-ref",
            "evidence:test",
            "--request-id",
            "request:test",
        ],
    )
    assert result.exit_code == 2
    assert "does not match" in result.output
    assert called is False


def test_recovery_rebuild_checks_freshness_at_current_observation_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_snapshot_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    observed_at = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
    prior_shaping = {
        "schema_version": "dad.portfolio_workstream_shaping.v2",
        "generated_at": source_snapshot_at.isoformat(),
        "methodology": {
            "case_limit": 250,
            "review_limit": 3,
            "fresh_after_hours": 26,
            "future_tolerance_hours": 1,
        },
    }
    observed_calls: list[tuple[str, datetime]] = []
    monkeypatch.setattr(cli, "data_path", lambda *_args: tmp_path)
    monkeypatch.setattr(cli, "_read_review_json", lambda _path: prior_shaping)
    monkeypatch.setattr(cli, "_v1_attention_report", lambda _root: {"report": True})

    def load_state(*_args, now: datetime, **_kwargs):
        observed_calls.append(("state", now))
        return {"state": True}

    def build_cockpit(*_args, now: datetime, **_kwargs):
        observed_calls.append(("cockpit", now))
        return {"cockpit": True}

    def build_reconciliation(*_args, now: datetime, **_kwargs):
        observed_calls.append(("reconciliation", now))
        return {"reconciliation": True}

    shaping_count = 0

    def build_shaping(*_args, now: datetime, **_kwargs):
        nonlocal shaping_count
        shaping_count += 1
        observed_calls.append((f"shaping-{shaping_count}", now))
        return {"schema_version": "dad.portfolio_workstream_shaping.v2"}

    def load_decisions(*_args, now: datetime, **_kwargs):
        observed_calls.append(("decisions", now))
        return {"decisions": []}

    monkeypatch.setattr(cli, "load_workstream_state", load_state)
    monkeypatch.setattr(cli, "build_portfolio_cockpit", build_cockpit)
    monkeypatch.setattr(cli, "build_portfolio_reconciliation", build_reconciliation)
    monkeypatch.setattr(cli, "build_portfolio_shaping", build_shaping)
    monkeypatch.setattr(cli, "load_recovery_projection", load_decisions)

    cli._rebuild_current_recovery_shaping(
        SimpleNamespace(repo_root=tmp_path),
        now=observed_at,
    )

    assert observed_calls[:3] == [
        ("state", source_snapshot_at),
        ("cockpit", source_snapshot_at),
        ("reconciliation", source_snapshot_at),
    ]
    assert observed_calls[3:] == [
        ("shaping-1", observed_at),
        ("decisions", observed_at),
        ("shaping-2", observed_at),
    ]
