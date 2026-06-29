from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from .catalog import catalog_status
from .config import AppConfig
from .roadmap import check_roadmap
from .utils import atomic_write_text, json_dumps, utc_now
from .validation import validate_repo

CORE_SURFACES = [
    {
        "path": "AI_FRONT_DOOR.md",
        "purpose": "single AI entrypoint",
        "kind": "tracked",
        "required_for": "front_door",
    },
    {
        "path": "AI_TABLE_OF_CONTENTS.md",
        "purpose": "deterministic AI routing map",
        "kind": "tracked",
        "required_for": "front_door",
    },
    {
        "path": "MACHINE_NAVIGATION_MANIFEST.json",
        "purpose": "machine-readable navigation map",
        "kind": "tracked",
        "required_for": "front_door",
    },
    {
        "path": "state/catalog.sqlite3",
        "purpose": "local catalog database",
        "kind": "generated",
        "required_for": "catalog",
    },
    {
        "path": "processed/catalog/assets.jsonl",
        "purpose": "generated asset catalog",
        "kind": "generated",
        "required_for": "catalog",
    },
    {
        "path": "processed/graph/graph.json",
        "purpose": "generated candidate graph",
        "kind": "generated",
        "required_for": "knowledge_graph",
    },
    {
        "path": "processed/reports/scan_summary.md",
        "purpose": "latest local scan summary",
        "kind": "generated",
        "required_for": "scan_evidence",
    },
    {
        "path": "processed/alerts/alert_inbox.md",
        "purpose": "reviewable alert inbox",
        "kind": "generated",
        "required_for": "review_queue",
    },
    {
        "path": "processed/reports/workflow_part_usage_guidance.md",
        "purpose": "manual reviewed workflow-part guidance",
        "kind": "generated",
        "required_for": "workflow_part_guidance",
    },
    {
        "path": "roadmap/evidence/workflow-part-usage-guidance.md",
        "purpose": "tracked workflow-part guidance evidence",
        "kind": "tracked",
        "required_for": "workflow_part_guidance",
    },
]

VALIDATION_COMMANDS = [
    "python -m pytest",
    "python -m ruff check src tests scripts noxfile.py",
    "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate",
    "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update",
]


def _git_state(repo_root: Path) -> dict[str, Any]:
    try:
        status = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return {"available": False, "clean": False, "details": [str(exc)]}
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    changed = [line for line in lines[1:] if not line.startswith("!! ")]
    return {
        "available": status.returncode == 0,
        "clean": status.returncode == 0 and not changed,
        "details": lines,
    }


def _surface_statuses(repo_root: Path) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for surface in CORE_SURFACES:
        path = repo_root / surface["path"]
        statuses.append(
            {
                **surface,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
            }
        )
    return statuses


def _safe_validation(repo_root: Path) -> dict[str, Any]:
    try:
        return validate_repo(repo_root)
    except Exception as exc:
        return {"valid": False, "checked_count": 0, "errors": [str(exc)]}


def _safe_roadmap(repo_root: Path) -> dict[str, Any]:
    try:
        return check_roadmap(repo_root, update=False)
    except Exception as exc:
        return {"error": str(exc), "phases": {}}


def _compact_catalog_status(status: dict[str, Any]) -> dict[str, Any]:
    latest = status.get("latest_scan")
    compact = {key: value for key, value in status.items() if key != "latest_scan"}
    if not latest:
        compact["latest_scan"] = None
        return compact
    latest_summary: dict[str, Any] = {}
    try:
        latest_summary = json.loads(latest.get("summary_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        latest_summary = {}
    compact["latest_scan"] = {
        "scan_id": latest.get("scan_id"),
        "started_at": latest.get("started_at"),
        "completed_at": latest.get("completed_at"),
        "status": latest.get("status"),
        "asset_count": latest_summary.get("asset_count"),
        "edge_count": latest_summary.get("edge_count"),
        "alert_count": latest_summary.get("alert_count"),
        "changed_during_scan_count": latest_summary.get("changed_during_scan_count"),
        "source_files_mutated": latest_summary.get("source_files_mutated"),
    }
    return compact


def build_operational_readiness(
    config: AppConfig, *, include_git: bool = True
) -> dict[str, Any]:
    repo_root = config.repo_root
    validation = _safe_validation(repo_root)
    roadmap = _safe_roadmap(repo_root)
    try:
        catalog = _compact_catalog_status(catalog_status(config))
    except Exception as exc:
        catalog = {
            "database": str(config.database_path),
            "exists": False,
            "assets": 0,
            "edges": 0,
            "alerts": 0,
            "latest_scan": None,
            "error": str(exc),
        }
    surfaces = _surface_statuses(repo_root)
    missing_required = [surface for surface in surfaces if not surface["exists"]]
    phases = roadmap.get("phases", {}) if isinstance(roadmap, dict) else {}
    phase_status_counts = Counter(
        phase.get("computed_status", "unknown") for phase in phases.values()
    )
    unverified_phase_gates = {
        phase_id: phase.get("human_gate_ids_unverified", [])
        for phase_id, phase in phases.items()
        if phase.get("human_gate_ids_unverified")
    }
    github_enabled = [
        source.id for source in config.github_sources if getattr(source, "enabled", False)
    ]
    local_enabled = [
        source.id for source in config.local_sources if getattr(source, "enabled", False)
    ]
    git = _git_state(repo_root) if include_git else {"available": False, "clean": None, "details": []}

    warnings: list[str] = []
    if not validation.get("valid"):
        warnings.append("Repository contract validation is failing.")
    if not catalog.get("exists") or catalog.get("assets", 0) <= 0:
        warnings.append("Catalog database is missing or empty; run a bounded local scan.")
    if missing_required:
        warnings.append("One or more front-door or generated readiness surfaces are missing.")
    if unverified_phase_gates:
        warnings.append("Roadmap still has unverified human gates.")
    if github_enabled:
        warnings.append("One or more GitHub sources are enabled; confirm token scope before scanning.")
    if git.get("clean") is False:
        warnings.append("Git worktree has tracked changes.")

    core_ready = (
        validation.get("valid") is True
        and bool(catalog.get("exists"))
        and catalog.get("assets", 0) > 0
        and not missing_required
        and not unverified_phase_gates
        and not github_enabled
        and (not include_git or git.get("clean") is True)
    )
    return {
        "schema": "operational_readiness.v1",
        "generated_at": utc_now(),
        "repo_root": str(repo_root),
        "ready": core_ready,
        "candidate_only": True,
        "authority_boundary": (
            "Operational readiness summarizes current local evidence. It does not scan, "
            "mutate source repositories, mark roadmap gates complete, or promote generated "
            "outputs to truth."
        ),
        "validation": validation,
        "roadmap_phase_status_counts": dict(sorted(phase_status_counts.items())),
        "roadmap_unverified_phase_gates": unverified_phase_gates,
        "catalog": catalog,
        "configured_sources": {
            "local_enabled": local_enabled,
            "github_enabled": github_enabled,
        },
        "surfaces": surfaces,
        "missing_surfaces": missing_required,
        "git": git,
        "warnings": warnings,
        "validation_commands": VALIDATION_COMMANDS,
        "recommended_next_commands": [
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend workflow-part-guidance --limit 50",
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update",
        ],
    }


def operational_readiness_markdown(result: dict[str, Any]) -> str:
    ready = "yes" if result["ready"] else "no"
    lines = [
        "# Operational Readiness",
        "",
        f"Generated at: `{result['generated_at']}`",
        f"Ready: **{ready}**",
        "",
        result["authority_boundary"],
        "",
        "## Summary",
        "",
        f"- Catalog assets: **{result['catalog'].get('assets', 0)}**",
        f"- Catalog edges: **{result['catalog'].get('edges', 0)}**",
        f"- Open alerts: **{result['catalog'].get('alerts', 0)}**",
        f"- Validation valid: **{result['validation'].get('valid')}**",
        f"- Roadmap statuses: `{result['roadmap_phase_status_counts']}`",
        f"- Local sources enabled: `{result['configured_sources']['local_enabled']}`",
        f"- GitHub sources enabled: `{result['configured_sources']['github_enabled']}`",
        "",
        "## Warnings",
        "",
    ]
    if result["warnings"]:
        lines.extend(f"- {warning}" for warning in result["warnings"])
    else:
        lines.append("- No readiness warnings.")
    lines.extend(["", "## Required Surfaces", ""])
    lines.extend(
        [
            "| path | kind | purpose | exists |",
            "|---|---|---|---|",
        ]
    )
    for surface in result["surfaces"]:
        lines.append(
            f"| `{surface['path']}` | `{surface['kind']}` | {surface['purpose']} | "
            f"`{surface['exists']}` |"
        )
    lines.extend(["", "## Validation Commands", ""])
    lines.extend(f"- `{command}`" for command in result["validation_commands"])
    lines.extend(["", "## Recommended Next Commands", ""])
    lines.extend(f"- `{command}`" for command in result["recommended_next_commands"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This report is evidence for operating the DAD hub. It is not acceptance evidence "
            "for new source scopes, GitHub scanning, automatic workflow assembly, embeddings, "
            "scheduled scans, or external research.",
            "",
        ]
    )
    return "\n".join(lines)


def write_operational_readiness_report(config: AppConfig) -> dict[str, Any]:
    result = build_operational_readiness(config)
    report_path = config.repo_root / "processed" / "reports" / "operational_readiness.md"
    payload_path = config.repo_root / "processed" / "reports" / "operational_readiness.json"
    atomic_write_text(report_path, operational_readiness_markdown(result))
    atomic_write_text(payload_path, json_dumps(result, pretty=True) + "\n")
    return {**result, "report": str(report_path), "payload": str(payload_path)}
