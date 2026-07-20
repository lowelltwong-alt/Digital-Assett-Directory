from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from digital_asset_directory.learning_yield_report import (
    build_learning_yield_report,
    write_learning_yield_report,
)
from digital_asset_directory.routine_health import evaluate_contract, load_contracts

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    (hub / "raw" / "lessons" / "2026-07-15").mkdir(parents=True)
    (hub / "raw" / "handoffs" / "2026-07-15").mkdir(parents=True)
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    (hub / "processed" / "usage").mkdir(parents=True)
    lesson = {
        "lesson_id": "dad:lesson:yield-1",
        "created_at": "2026-07-15T10:00:00+00:00",
        "review_status": "reviewed",
        "lessons": ["reuse source records"],
        "observed_usefulness": 0.99,
    }
    (hub / "raw" / "lessons" / "2026-07-15" / "lesson.json").write_text(
        json.dumps(lesson), encoding="utf-8"
    )
    session = {
        "session_id": "dad:session:yield-1",
        "created_at": "2026-07-18T11:00:00+00:00",
        "learning_rule_acknowledgements": ["learning-rule:example"],
        "summary": "cited dad:lesson:yield-1",
    }
    (hub / "state" / "agent_sessions" / "session.json").write_text(
        json.dumps(session), encoding="utf-8"
    )
    return hub


def test_yield_report_counts_source_records_and_ignores_self_scores(tmp_path: Path) -> None:
    hub = _hub(tmp_path)
    report = build_learning_yield_report(hub, window_days=30, now=NOW)
    assert report["model_call_count"] == 0
    assert report["candidate_only"] is True
    assert report["execution_authorized"] is False
    assert report["routine_registration"] == {
        "routine_id": "dad-learning-loop-yield-report",
        "enabled": False,
        "scheduled": False,
    }
    lesson_loop = next(
        row for row in report["loops"] if row["loop_id"] == "loop:lessons-and-handoffs"
    )
    assert lesson_loop["records_written"] == 1
    assert lesson_loop["records_reused"] == 1
    assert lesson_loop["records_promoted"] == 1
    assert "observed_usefulness" not in json.dumps(report["loops"])
    schema = json.loads(
        (ROOT / "schemas/learning-loop-yield-report.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(report, schema)


def test_missing_usage_ledger_is_coverage_unavailable(tmp_path: Path) -> None:
    hub = _hub(tmp_path)
    report = build_learning_yield_report(hub, window_days=30, now=NOW)
    usage_loop = next(
        row for row in report["loops"] if row["loop_id"] == "loop:usage-decision-traces"
    )
    assert usage_loop["reuse_coverage"] == "coverage_unavailable"
    assert "loop:usage-decision-traces" in report["unknown_coverage"]


def test_write_learning_yield_report_is_report_only(tmp_path: Path) -> None:
    hub = _hub(tmp_path)
    result = write_learning_yield_report(hub, window_days=30, now=NOW)
    assert Path(result["json_path"]).is_file()
    assert Path(result["markdown_path"]).is_file()
    assert Path(result["history_path"]).is_file()
    lesson_path = hub / "raw" / "lessons" / "2026-07-15" / "lesson.json"
    assert "observed_usefulness" in lesson_path.read_text(encoding="utf-8")


def test_routine_contract_is_registered_disabled() -> None:
    contracts = load_contracts(ROOT)["contracts"]
    contract = next(
        row
        for row in contracts
        if row["routine_id"] == "dad-learning-loop-yield-report"
    )
    assert contract["enabled"] is False
    assert contract["kind"] == "cli_on_demand"
    assert contract["freshness_hours"] is None
    status = evaluate_contract(ROOT, contract)
    assert status["status"] == "disabled"
