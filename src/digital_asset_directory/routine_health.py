"""Deterministic routine-contract health checks (the "foreman" layer).

Every registered routine declares an output contract: the artifact it must
produce, how fresh that artifact must be, and the dependencies it needs to run.
This module verifies those contracts with pure filesystem checks — no model
judgment, no scores, zero token cost — and writes a report-only health surface.

Statuses are defined by ``registry/routine-contract-registry.json`` under
``methodology`` (dad.routine-health.v0.1.0). A healthy status never proves the
routine's output is correct or valuable; it only proves the routine is actually
producing its contracted artifact.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .transport import resolve_data_root
from .utils import utc_now, write_json

REGISTRY_RELPATH = Path("registry") / "routine-contract-registry.json"
REPORT_BASENAME = "routine_health"

_HEALTHY = {"alive", "never_ran", "disabled"}


def load_contracts(hub_root: Path) -> dict[str, Any]:
    registry_path = hub_root / REGISTRY_RELPATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("contracts"), list):
        raise ValueError(f"{registry_path} has no contracts list")
    return payload


def _artifact_candidates(
    hub_root: Path, artifact: dict[str, Any], env: dict[str, str] | None
) -> list[Path]:
    """Resolve the artifact pattern under its root, newest matches first.

    ``data`` artifacts are looked up under the active data root and, as a
    legacy fallback, under the hub checkout itself so pre-data-root surfaces
    still count as evidence.
    """

    relative = str(artifact.get("path", ""))
    roots: list[Path] = []
    if artifact.get("root") == "data":
        active, _mode = resolve_data_root(hub_root, env=env)
        roots.append(active)
        if active != hub_root:
            roots.append(hub_root)
    else:
        roots.append(hub_root)
    found: list[Path] = []
    for root in roots:
        if any(ch in relative for ch in "*?["):
            found.extend(path for path in root.glob(relative) if path.is_file())
        else:
            candidate = root / relative
            if candidate.is_file():
                found.append(candidate)
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def _missing_dependencies(hub_root: Path, contract: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for raw in contract.get("dependency_paths", []) or []:
        path = Path(raw)
        if not path.is_absolute():
            path = hub_root / raw
        if not path.exists():
            missing.append(str(raw))
    for command in contract.get("dependency_commands", []) or []:
        if not shutil.which(command):
            missing.append(f"command:{command}")
    return missing


def evaluate_contract(
    hub_root: Path,
    contract: dict[str, Any],
    *,
    now: datetime | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "routine_id": contract.get("routine_id"),
        "kind": contract.get("kind"),
        "enabled": bool(contract.get("enabled")),
        "artifact_path": None,
        "artifact_age_hours": None,
        "missing_dependencies": _missing_dependencies(hub_root, contract),
        "reason": "",
    }
    artifact = contract.get("artifact", {}) or {}
    candidates = _artifact_candidates(hub_root, artifact, env)
    freshness = contract.get("freshness_hours")

    if candidates:
        newest = candidates[0]
        result["artifact_path"] = str(newest)
        age_hours = (
            current - datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)
        ).total_seconds() / 3600
        result["artifact_age_hours"] = round(age_hours, 2)

    if not result["enabled"]:
        result["status"] = "disabled"
        result["reason"] = "contract disabled; inventory record only"
        return result
    if result["missing_dependencies"]:
        result["status"] = "missing_dependency"
        result["reason"] = "missing: " + ", ".join(result["missing_dependencies"])
        return result
    if not candidates:
        if freshness is None:
            result["status"] = "never_ran"
            result["reason"] = "on-demand routine with no artifact yet"
        else:
            result["status"] = "dead"
            result["reason"] = f"no artifact matched {artifact.get('path')}"
        return result
    if artifact.get("parse_json"):
        try:
            json.loads(candidates[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            result["status"] = "dead"
            result["reason"] = f"artifact failed JSON parse: {exc}"
            return result
    if freshness is not None and result["artifact_age_hours"] > float(freshness):
        result["status"] = "stale"
        result["reason"] = (
            f"artifact age {result['artifact_age_hours']}h exceeds {freshness}h"
        )
        return result
    result["status"] = "alive"
    return result


def run_health_check(
    hub_root: Path,
    *,
    now: datetime | None = None,
    env: dict[str, str] | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    hub_root = hub_root.resolve()
    registry = load_contracts(hub_root)
    results = [
        evaluate_contract(hub_root, contract, now=now, env=env)
        for contract in registry["contracts"]
    ]
    unhealthy = [row for row in results if row["status"] not in _HEALTHY]
    report: dict[str, Any] = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "methodology_version": registry.get("methodology", {}).get("version", ""),
        "registry_path": str(hub_root / REGISTRY_RELPATH),
        "authority_boundary": registry.get("authority_boundary", ""),
        "results": results,
        "summary": {
            "total": len(results),
            "unhealthy_count": len(unhealthy),
            "by_status": {
                status: sum(1 for row in results if row["status"] == status)
                for status in sorted({row["status"] for row in results})
            },
        },
    }
    if write_report:
        reports_dir, _mode = resolve_data_root(hub_root, env=env)
        reports_dir = reports_dir / "processed" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        write_json(reports_dir / f"{REPORT_BASENAME}.json", report)
        (reports_dir / f"{REPORT_BASENAME}.md").write_text(
            _markdown(report), encoding="utf-8"
        )
        report["report_json"] = str(reports_dir / f"{REPORT_BASENAME}.json")
        report["report_markdown"] = str(reports_dir / f"{REPORT_BASENAME}.md")
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Routine Health",
        "",
        f"Generated: {report['generated_at']}",
        f"Methodology: {report['methodology_version']} (see registry/routine-contract-registry.json)",
        "",
        "Statuses are deterministic file checks; healthy never proves output quality.",
        "",
        "| routine | kind | status | age (h) | reason |",
        "|---|---|---|---|---|",
    ]
    for row in report["results"]:
        lines.append(
            "| {0} | {1} | {2} | {3} | {4} |".format(
                row["routine_id"],
                row["kind"],
                row["status"],
                row["artifact_age_hours"] if row["artifact_age_hours"] is not None else "-",
                row["reason"] or "-",
            )
        )
    summary = report["summary"]
    lines += [
        "",
        f"Total: {summary['total']}; unhealthy: {summary['unhealthy_count']}.",
        "",
    ]
    return "\n".join(lines)
