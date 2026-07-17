from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema

from digital_asset_directory.routine_health import (
    evaluate_contract,
    load_contracts,
    run_health_check,
)

ROOT = Path(__file__).resolve().parents[1]


def _hub(tmp_path: Path, contracts: list[dict]) -> Path:
    hub = tmp_path / "hub"
    (hub / "registry").mkdir(parents=True)
    payload = {
        "schema_version": "0.1.0",
        "registry_id": "dad-routine-contracts",
        "authority_boundary": "test",
        "methodology": {
            "version": "dad.routine-health.v0.1.0",
            "statuses": {"alive": "ok"},
            "notes": "test",
        },
        "contracts": contracts,
    }
    (hub / "registry" / "routine-contract-registry.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return hub


def _env(tmp_path: Path) -> dict[str, str]:
    # Point DAD_DATA_ROOT at an uninitialized directory so resolution falls
    # back to the hub checkout and never touches the real user data root.
    return {"DAD_DATA_ROOT": str(tmp_path / "uninitialized-data-root")}


def _contract(**overrides) -> dict:
    base = {
        "routine_id": "test-routine",
        "kind": "daemon_step",
        "enabled": True,
        "owner": "test",
        "artifact": {"root": "repo", "path": "processed/reports/out.json", "parse_json": True},
        "freshness_hours": 24,
    }
    base.update(overrides)
    return base


def _write_artifact(hub: Path, relpath: str, content: str = "{}", age_hours: float = 0) -> Path:
    path = hub / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if age_hours:
        stamp = time.time() - age_hours * 3600
        os.utime(path, (stamp, stamp))
    return path


def test_alive_when_artifact_fresh(tmp_path: Path) -> None:
    hub = _hub(tmp_path, [_contract()])
    _write_artifact(hub, "processed/reports/out.json")
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "alive"


def test_stale_when_artifact_old(tmp_path: Path) -> None:
    hub = _hub(tmp_path, [_contract()])
    _write_artifact(hub, "processed/reports/out.json", age_hours=48)
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "stale"
    assert result["artifact_age_hours"] > 24


def test_dead_when_artifact_missing_on_cadence(tmp_path: Path) -> None:
    hub = _hub(tmp_path, [_contract()])
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "dead"


def test_dead_when_artifact_unparseable(tmp_path: Path) -> None:
    hub = _hub(tmp_path, [_contract()])
    _write_artifact(hub, "processed/reports/out.json", content="not json {")
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "dead"
    assert "parse" in result["reason"]


def test_never_ran_for_on_demand_routine(tmp_path: Path) -> None:
    hub = _hub(tmp_path, [_contract(freshness_hours=None)])
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "never_ran"


def test_missing_dependency_beats_artifact_state(tmp_path: Path) -> None:
    hub = _hub(
        tmp_path,
        [
            _contract(
                dependency_paths=["scripts/does_not_exist.py"],
                dependency_commands=["definitely-not-a-real-command-xyz"],
            )
        ],
    )
    _write_artifact(hub, "processed/reports/out.json")
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "missing_dependency"
    assert "scripts/does_not_exist.py" in result["missing_dependencies"]
    assert "command:definitely-not-a-real-command-xyz" in result["missing_dependencies"]


def test_disabled_contract_is_inventory_only(tmp_path: Path) -> None:
    hub = _hub(tmp_path, [_contract(enabled=False)])
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "disabled"


def test_glob_artifact_uses_newest_match(tmp_path: Path) -> None:
    hub = _hub(
        tmp_path,
        [_contract(artifact={"root": "repo", "path": "raw/events/run-*/out.json", "parse_json": True})],
    )
    _write_artifact(hub, "raw/events/run-a/out.json", age_hours=100)
    fresh = _write_artifact(hub, "raw/events/run-b/out.json", age_hours=1)
    result = evaluate_contract(hub, load_contracts(hub)["contracts"][0], env=_env(tmp_path))
    assert result["status"] == "alive"
    assert result["artifact_path"] == str(fresh)


def test_run_health_check_writes_reports_and_summary(tmp_path: Path) -> None:
    hub = _hub(
        tmp_path,
        [
            _contract(routine_id="ok-routine"),
            _contract(routine_id="dead-routine", artifact={"root": "repo", "path": "missing/nope.json"}),
        ],
    )
    _write_artifact(hub, "processed/reports/out.json")
    report = run_health_check(hub, env=_env(tmp_path))
    assert report["summary"]["total"] == 2
    assert report["summary"]["unhealthy_count"] == 1
    assert report["summary"]["by_status"]["alive"] == 1
    assert report["summary"]["by_status"]["dead"] == 1
    assert report["methodology_version"] == "dad.routine-health.v0.1.0"
    json_report = Path(report["report_json"])
    md_report = Path(report["report_markdown"])
    assert json_report.exists() and md_report.exists()
    # Fallback resolution must keep reports inside the temp hub, never the
    # real user data root.
    assert str(json_report).startswith(str(hub))
    assert "dead-routine" in md_report.read_text(encoding="utf-8")


def test_shipped_registry_validates_against_schema() -> None:
    registry = json.loads(
        (ROOT / "registry" / "routine-contract-registry.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (ROOT / "schemas" / "routine-contract-registry.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(registry, schema)


def test_shipped_registry_covers_known_orphan_radar_surfaces() -> None:
    registry = json.loads(
        (ROOT / "registry" / "routine-contract-registry.json").read_text(encoding="utf-8")
    )
    ids = {contract["routine_id"] for contract in registry["contracts"]}
    assert {"weekly-skill-orphan-radar", "orphan-radar-wrapper", "dad-daemon-run-cycle"} <= ids


def test_freshness_boundary_uses_now_parameter(tmp_path: Path) -> None:
    hub = _hub(tmp_path, [_contract()])
    _write_artifact(hub, "processed/reports/out.json")
    future = datetime.now(timezone.utc) + timedelta(hours=25)
    result = evaluate_contract(
        hub, load_contracts(hub)["contracts"][0], now=future, env=_env(tmp_path)
    )
    assert result["status"] == "stale"
