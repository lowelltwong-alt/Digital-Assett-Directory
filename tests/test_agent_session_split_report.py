from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema

from digital_asset_directory.agent_session_split_report import (
    build_agent_session_split_report,
    canonical_agent_session_path,
    write_agent_session_split_report,
)
from digital_asset_directory.routine_health import evaluate_contract, load_contracts
from digital_asset_directory.transport import DATA_ROOT_MARKER

ROOT = Path(__file__).resolve().parents[1]


def _write_session(path: Path, **fields: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "0.1.0",
        "session_id": f"dad:session:{path.stem}",
        "created_at": "2026-07-20T12:00:00+00:00",
        "repository": str(ROOT),
        "agent": "cursor",
        "task": "n1",
        "status": "open",
        "required_postflight": True,
    }
    payload.update(fields)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _hub_with_data_root(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    data_root = tmp_path / "data-root"
    hub.mkdir()
    data_root.mkdir()
    (data_root / DATA_ROOT_MARKER).write_text(
        json.dumps({"hub_ref": str(hub.resolve())}),
        encoding="utf-8",
    )
    os.environ["DAD_DATA_ROOT"] = str(data_root)
    return hub


def test_split_report_classifies_agree_disagree_and_only(tmp_path: Path) -> None:
    hub = _hub_with_data_root(tmp_path)
    legacy = hub / "state" / "agent_sessions"
    canonical = Path(os.environ["DAD_DATA_ROOT"]) / "state" / "agent_sessions"
    _write_session(legacy / "agree.json", status="closed", closed_at="2026-07-20T13:00:00+00:00")
    _write_session(
        canonical / "agree.json",
        status="closed",
        closed_at="2026-07-20T13:00:00+00:00",
    )
    _write_session(legacy / "split.json", status="open")
    _write_session(
        canonical / "split.json",
        status="closed",
        closed_at="2026-07-20T14:00:00+00:00",
        handoff_id="dad:handoff:x",
    )
    _write_session(legacy / "legacy-only.json", status="open")
    _write_session(canonical / "data-only.json", status="open")

    report = build_agent_session_split_report(hub)
    assert report["apply_authorized"] is False
    assert report["execution_authorized"] is False
    assert report["data_plane"]["mode"] == "data_root"
    assert report["summary"]["agree"] == 1
    assert report["summary"]["open_closed_split"] == 1
    assert report["summary"]["legacy_only"] == 1
    assert report["summary"]["data_root_only"] == 1
    assert report["summary"]["split_evidence"] == "present"
    schema = json.loads(
        (ROOT / "schemas/agent-session-split-report.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(report, schema)


def test_same_location_reports_absent_split(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    os.environ.pop("DAD_DATA_ROOT", None)
    _write_session(hub / "state" / "agent_sessions" / "one.json")
    report = build_agent_session_split_report(hub)
    assert report["data_plane"]["same_location"] is True
    assert report["summary"]["split_evidence"] == "absent"


def test_one_sided_orphan_is_present_split_evidence(tmp_path: Path) -> None:
    hub = _hub_with_data_root(tmp_path)
    legacy = hub / "state" / "agent_sessions"
    _write_session(legacy / "orphan.json", status="open")
    report = build_agent_session_split_report(hub)
    assert report["summary"]["legacy_only"] == 1
    assert report["summary"]["data_root_only"] == 0
    assert report["summary"]["split_evidence"] == "present"


def test_write_report_does_not_mutate_sessions(tmp_path: Path) -> None:
    hub = _hub_with_data_root(tmp_path)
    legacy = hub / "state" / "agent_sessions" / "keep.json"
    _write_session(legacy, status="open")
    before = legacy.read_text(encoding="utf-8")
    result = write_agent_session_split_report(hub)
    assert Path(result["json_path"]).is_file()
    assert Path(result["markdown_path"]).is_file()
    assert Path(result["history_path"]).is_file()
    assert legacy.read_text(encoding="utf-8") == before


def test_canonical_write_path_uses_data_root(tmp_path: Path) -> None:
    hub = _hub_with_data_root(tmp_path)
    path = canonical_agent_session_path(hub, "abc")
    assert str(path).replace("\\", "/").endswith("state/agent_sessions/abc.json")
    assert Path(os.environ["DAD_DATA_ROOT"]) in path.parents


def test_routine_contract_disabled() -> None:
    contracts = load_contracts(ROOT)["contracts"]
    contract = next(
        row for row in contracts if row["routine_id"] == "dad-agent-session-split-report"
    )
    assert contract["enabled"] is False
    assert contract["freshness_hours"] is None
    assert evaluate_contract(ROOT, contract)["status"] == "disabled"
