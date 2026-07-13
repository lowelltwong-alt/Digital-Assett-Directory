"""Adversarial tests for the read-only Portfolio Review Packet."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import runpy

import pytest

from digital_asset_directory import portfolio_review as review
from digital_asset_directory.portfolio_cockpit import schema_validation_problems

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = runpy.run_path(str(ROOT / "tests" / "test_portfolio_shaping.py"))
NOW = SUPPORT["NOW"]


def _sources():
    project = SUPPORT["_project"]("review")
    pair = SUPPORT["_workstream"]("workstream:review", "private client Alpha C:/private/client")
    state, cockpit, reconciliation = SUPPORT["_triple"]([project], [pair])
    shaping = SUPPORT["_shape"]((state, cockpit, reconciliation))
    return cockpit, reconciliation, shaping


def _health(**overrides):
    values = {
        "daemon": {
            "schema_version": "dad.daemon.status.v1",
            "generated_at": NOW.isoformat(),
            "cycle_completed_at": NOW.isoformat(),
            "status": "fresh",
            "stale": False,
        },
        "daily_review": {
            "schema_version": "dad.daily_review_queue.v1",
            "generated_at": NOW.isoformat(),
            "status": "observed",
        },
        "mail": {
            "schema_version": "dad.mail.digest.status.v1",
            "last_checked_at": NOW.isoformat(),
            "status": "fresh",
            "stale": False,
        },
        "journal": {
            "schema_version": "dad.journal.status.v1",
            "generated_at": NOW.isoformat(),
            "status": "observed",
            "checkpoint_due": False,
            "new_record_count": 0,
        },
        "transport": {
            "schema_version": "dad.transport.audit.v1",
            "generated_at": NOW.isoformat(),
            "status": "observed",
        },
        "execution": {
            "schema_version": "dad.portfolio_execution_control.v1",
            "as_of": NOW.isoformat(),
            "status": "generated_candidate",
            "summary": {"dispatch_count": 0, "active_lease_count": 0},
            "attempt_journal": {"summary": {"dispatch_count": 0}},
            "executor": {"available": False},
        },
        "roadmap": {
            "schema_version": "dad.roadmap.status.v1",
            "last_checked_at": NOW.isoformat(),
            "status": "observed",
            "phases": {},
        },
    }
    values.update(overrides)
    return values


def _packet(*, health=None, now=NOW):
    return review.build_portfolio_review(
        *_sources(), health or _health(), now=now, schema_root=ROOT
    )


def _validate(packet):
    assert schema_validation_problems(packet, ROOT, "portfolio_review_packet") == []
    assert review.portfolio_review_semantic_problems(packet) == []


def test_packet_is_strict_private_minimized_and_reuses_today() -> None:
    cockpit, reconciliation, shaping = _sources()
    packet = review.build_portfolio_review(
        cockpit, reconciliation, shaping, _health(), now=NOW, schema_root=ROOT
    )
    _validate(packet)
    serialized = json.dumps(packet)
    assert packet["summary"]["all_clear"] is False
    assert len(packet["dashboard"]["now"]) == len(cockpit["today"]) <= 3
    assert all(row["source_refs"] == ["cockpit"] for row in packet["dashboard"]["now"])
    assert "private client Alpha" not in serialized
    assert "C:/private/client" not in serialized
    assert packet["methodology"]["numeric_score_used"] is False
    assert packet["methodology"]["creates_second_today_queue"] is False
    assert packet["execution_authorized"] is False


def test_missing_stale_and_applicable_checker_evidence_never_clear() -> None:
    missing = review.build_portfolio_review(None, None, None, {}, now=NOW, schema_root=ROOT)
    _validate(missing)
    assert missing["status"] == "blocked_candidate"
    assert missing["summary"]["all_clear"] is False
    stale_mail = deepcopy(_health()["mail"])
    stale_mail["last_checked_at"] = (NOW - timedelta(days=3)).isoformat()
    stale = _packet(health=_health(mail=stale_mail))
    _validate(stale)
    assert next(row for row in stale["health"] if row["lane_id"] == "mail")["status"] == "blocked"
    execution = deepcopy(_health()["execution"])
    execution["summary"]["dispatch_count"] = 1
    packet = _packet(health=_health(execution=execution))
    checker = next(row for row in packet["health"] if row["lane_id"] == "checker")
    assert checker["status"] == "unavailable" and checker["blocks_clearance"] is True
    assert packet["summary"]["all_clear"] is False


def test_semantic_validator_rejects_forged_clearance_identity_and_fingerprint() -> None:
    forged = deepcopy(_packet())
    forged["summary"]["all_clear"] = True
    forged["dashboard"]["now"][0]["item_id"] = "forged"
    forged["material_fingerprints"] = []
    problems = review.portfolio_review_semantic_problems(forged)
    assert {
        "all_clear_mismatch",
        "dashboard_item_identity_mismatch",
        "material_fingerprint_mismatch",
    } <= set(problems)


def test_html_is_inert_accessible_and_script_free() -> None:
    html = review.portfolio_review_html(_packet())
    lowered = html.casefold()
    assert "content-security-policy" in lowered
    assert "<main" in lowered and "aria-label" in lowered
    assert all(
        token not in lowered for token in ("<script", "<form", "<button", "http://", "https://")
    )
    assert "C:/private" not in html


def test_publication_is_stable_and_rolls_back_late_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cockpit, reconciliation, shaping = _sources()
    health = _health()
    packet = review.build_portfolio_review(
        cockpit, reconciliation, shaping, health, now=NOW, schema_root=ROOT
    )
    monkeypatch.setattr(review, "data_path", lambda _root, _logical: tmp_path)
    first = review.write_portfolio_review_outputs(
        ROOT,
        packet,
        cockpit=cockpit,
        reconciliation=reconciliation,
        shaping=shaping,
        health_inputs=health,
    )
    assert first["today_changed"] is True
    later = review.build_portfolio_review(
        cockpit, reconciliation, shaping, health, now=NOW + timedelta(minutes=1), schema_root=ROOT
    )
    second = review.write_portfolio_review_outputs(
        ROOT,
        later,
        cockpit=cockpit,
        reconciliation=reconciliation,
        shaping=shaping,
        health_inputs=health,
    )
    assert second["today_changed"] is False
    json_path, html_path = (
        tmp_path / "portfolio_os" / "review.json",
        tmp_path / "portfolio_os" / "review.html",
    )
    prior_json, prior_html = json_path.read_text("utf-8"), html_path.read_text("utf-8")
    real_write, failed = review.atomic_write_text, False

    def fail_once(path: Path, text: str) -> None:
        nonlocal failed
        if path.name == "review.json" and not failed:
            failed = True
            raise OSError("injected late review cursor failure")
        real_write(path, text)

    monkeypatch.setattr(review, "atomic_write_text", fail_once)
    with pytest.raises(OSError, match="injected"):
        review.write_portfolio_review_outputs(
            ROOT,
            packet,
            cockpit=cockpit,
            reconciliation=reconciliation,
            shaping=shaping,
            health_inputs=health,
        )
    assert json_path.read_text("utf-8") == prior_json
    assert html_path.read_text("utf-8") == prior_html


def test_os_review_cli_is_read_only_and_path_minimized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    from digital_asset_directory import cli

    sources = _sources()
    health = _health()
    monkeypatch.setattr(cli, "_cfg", lambda *args, **kwargs: type("Cfg", (), {"repo_root": ROOT})())
    monkeypatch.setattr(cli, "_current_portfolio_review_sources", lambda _cfg: sources)
    monkeypatch.setattr(cli, "_portfolio_review_health_inputs", lambda _cfg: health)
    monkeypatch.setattr(
        cli,
        "write_portfolio_review_outputs",
        lambda *_args, **_kwargs: {
            "status": "partial_candidate",
            "summary": _packet()["summary"],
            "today_changed": False,
            "review_response_template": _packet()["review_response_template"],
            "authority_boundary": review.AUTHORITY_BOUNDARY,
            "generated_at": NOW.isoformat(),
        },
    )
    result = CliRunner().invoke(cli.app, ["os", "review"])
    assert result.exit_code == 0, result.output
    assert "today_changed" in result.output
    assert "C:\\" not in result.output and "C:/" not in result.output
