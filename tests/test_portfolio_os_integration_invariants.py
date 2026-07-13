"""Cross-module invariants for the DAD Portfolio OS kernel."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from typer.testing import CliRunner

from digital_asset_directory import cli
from digital_asset_directory import portfolio_workstreams as pw


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
RUNNER = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def _validate_state(state: dict[str, object]) -> None:
    schema = json.loads(
        (ROOT / "schemas" / "portfolio-workstream-state.schema.json").read_text(encoding="utf-8")
    )
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=FormatChecker()).validate(state)


def _capture(hub, ideas: list[str] | None = None) -> list[str]:
    result = pw.capture_ideas(
        hub,
        ideas or ["durable personal project operating system"],
        conversation_id="integration-conversation",
        now=T0,
    )
    return [row["workstream_id"] for row in result["proposals"]]


def test_changed_blocker_changes_today_fingerprint(tmp_path) -> None:
    ws_id = _capture(tmp_path)[0]
    pw.record_capsule(tmp_path, ws_id, blocker="waiting for Alice", now=T0 + timedelta(days=1))
    first = pw.refresh(tmp_path, now=T0 + timedelta(days=2))
    pw.record_capsule(tmp_path, ws_id, blocker="waiting for Bob", now=T0 + timedelta(days=2, hours=1))
    second = pw.refresh(tmp_path, now=T0 + timedelta(days=2, hours=2))

    assert first["today_changed"] is True
    assert second["today_changed"] is True
    assert second["today"][0]["reasons"] == ["Blocked: waiting for Bob"]


def test_dependency_proposal_acceptance_and_retraction_are_distinct(tmp_path) -> None:
    ws_a, ws_b = _capture(
        tmp_path,
        ["alpha dependency source engine", "beta dependency target interface"],
    )
    proposed = pw.record_binding(tmp_path, ws_a, "blocks", ws_b, now=T0)
    assert proposed["assertion_status"] == "proposed"
    assert pw.load_state(tmp_path, now=T0)["dependencies"]["bottlenecks"] == []

    accepted = pw.record_binding(
        tmp_path,
        ws_a,
        "blocks",
        ws_b,
        assertion_status="accepted",
        asserted_by="Lowell",
        approval_ref="decision:test:accept",
        now=T0 + timedelta(minutes=1),
    )
    assert accepted["events_appended"] == 1
    state = pw.load_state(tmp_path, now=T0 + timedelta(minutes=1))
    assert state["dependencies"]["bottlenecks"][0]["workstream_id"] == ws_a

    retracted = pw.record_binding_retraction(
        tmp_path,
        ws_a,
        "blocks",
        ws_b,
        reason="edge was asserted backwards",
        retracted_by="Lowell",
        now=T0 + timedelta(minutes=2),
    )
    assert retracted["status"] == "retracted"
    assert pw.load_state(tmp_path, now=T0 + timedelta(minutes=2))["dependencies"][
        "bottlenecks"
    ] == []


def test_pause_does_not_resolve_conflict_but_keep_does(tmp_path) -> None:
    pw.capture_ideas(
        tmp_path,
        ["rust parser cache for tokenizer speedup"],
        conversation_id="prior",
        now=T0,
    )
    result = pw.capture_ideas(
        tmp_path,
        ["scrap the rust parser cache tokenizer approach and revert"],
        conversation_id="contradiction",
        now=T0 + timedelta(minutes=1),
    )
    ws_id = result["proposals"][0]["workstream_id"]
    assert result["proposals"][0]["needs_human_decision"] is True

    pw.record_feedback(tmp_path, ws_id, "pause", now=T0 + timedelta(days=1))
    paused = next(row for row in pw.load_state(tmp_path, now=T0 + timedelta(days=2))["workstreams"] if row["workstream_id"] == ws_id)
    assert paused["conflict_resolved"] is False

    pw.record_feedback(tmp_path, ws_id, "keep", now=T0 + timedelta(days=3))
    kept = next(row for row in pw.load_state(tmp_path, now=T0 + timedelta(days=3))["workstreams"] if row["workstream_id"] == ws_id)
    assert kept["conflict_resolved"] is True
    assert kept["lifecycle_state"] == "active"


def test_project_sovereignty_is_explicit_and_transition_checked(tmp_path) -> None:
    registered = pw.register_project(tmp_path, "LawFirm OS", note="DAD-governed child", now=T0)
    project_id = registered["project_id"]

    illegal = pw.record_sovereignty(
        tmp_path,
        project_id,
        "client_sovereign",
        decided_by="Lowell",
        approval_ref="decision:test:too-early",
        now=T0 + timedelta(minutes=1),
    )
    assert illegal["status"] == "illegal_transition"

    recorded = pw.record_sovereignty(
        tmp_path,
        project_id,
        "dad_governed_child",
        decided_by="Lowell",
        approval_ref="decision:test:dad-child",
        now=T0 + timedelta(minutes=2),
    )
    assert recorded["status"] == "recorded"
    project = pw.load_state(tmp_path, now=T0 + timedelta(minutes=2))["projects"][0]
    assert project["name"] == "LawFirm OS"
    assert project["sovereignty_state"] == "dad_governed_child"
    assert project["sovereignty_history"][0]["approval_ref"] == "decision:test:dad-child"
    _validate_state(pw.load_state(tmp_path, now=T0 + timedelta(minutes=2)))


def test_cli_rejected_write_exits_nonzero(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "_cfg", lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path))
    result = RUNNER.invoke(
        cli.app,
        ["os", "capsule", "dad:portfolio-workstream:missing", "--next-action", "x"],
    )

    assert result.exit_code == 2
    assert "unknown_workstream" in result.output
