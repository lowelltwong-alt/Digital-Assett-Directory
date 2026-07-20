"""Advice-only consumers of the intelligence routing registry (N7).

This module never dispatches a model, never grants approval, and never binds a
portable core to a permanent vendor or model name. It only maps a task string to
a recommended starting tier list from config/intelligence-routing-registry.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROUTING_REGISTRY_REL = Path("config/intelligence-routing-registry.json")
DEFAULT_TASK_CLASS = "standard_build_with_tests"

_TASK_CLASS_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "load_bearing_or_reflexive_or_irreversible",
        (
            "load-bearing",
            "load bearing",
            "irreversible",
            "reflexive",
            "authority model",
            "fable",
            "self-modifying",
            "activation packet",
        ),
    ),
    (
        "red_team_premortem_architecture_adjacent",
        (
            "red-team",
            "red team",
            "premortem",
            "architecture",
            "cross-module",
            "hard debugging",
        ),
    ),
    (
        "review_of_other_vendor_work",
        (
            "cross-vendor review",
            "review of other vendor",
            "independent review",
            "terra review",
            "checker review",
        ),
    ),
    (
        "mechanical_edit_or_capture_structuring",
        (
            "mechanical",
            "formatting",
            "file move",
            "capture structuring",
            "capture inbox",
            "single-file fix",
            "typo",
        ),
    ),
)


def load_intelligence_routing_registry(hub_root: Path) -> dict[str, Any]:
    path = hub_root / ROUTING_REGISTRY_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("intelligence routing registry must be an object")
    return payload


def known_tier_ids(registry: dict[str, Any]) -> set[str]:
    return {
        str(tier["tier_id"])
        for vendor in registry.get("vendors", {}).values()
        for tier in vendor.get("tiers", [])
        if isinstance(tier, dict) and tier.get("tier_id")
    }


def validate_tier_ids(tier_ids: list[str], registry: dict[str, Any]) -> list[str]:
    """Return unknown tier ids; empty means every id is registered."""

    known = known_tier_ids(registry)
    return [tier_id for tier_id in tier_ids if tier_id not in known]


def classify_task_class(task: str, registry: dict[str, Any] | None = None) -> str:
    """Deterministic keyword routing aid; defaults to standard_build_with_tests."""

    lowered = " ".join(task.casefold().split())
    available = {
        str(row["task_class"])
        for row in (registry or {}).get("task_class_defaults", [])
        if isinstance(row, dict) and row.get("task_class")
    }
    for task_class, hints in _TASK_CLASS_HINTS:
        if available and task_class not in available:
            continue
        if any(hint in lowered for hint in hints):
            return task_class
    if available and DEFAULT_TASK_CLASS in available:
        return DEFAULT_TASK_CLASS
    if available:
        return sorted(available)[0]
    return DEFAULT_TASK_CLASS


def _task_class_row(registry: dict[str, Any], task_class: str) -> dict[str, Any]:
    for row in registry.get("task_class_defaults", []):
        if isinstance(row, dict) and row.get("task_class") == task_class:
            return row
    raise KeyError(f"unknown task_class: {task_class}")


def recommend_start_tiers(task: str, hub_root: Path) -> dict[str, Any]:
    """Return advice-only start-tier guidance for a preflight context pack."""

    registry = load_intelligence_routing_registry(hub_root)
    task_class = classify_task_class(task, registry)
    row = _task_class_row(registry, task_class)
    start_tiers = [str(tier_id) for tier_id in row.get("start_tier", [])]
    unknown = validate_tier_ids(start_tiers, registry)
    if unknown:
        raise ValueError(f"task class {task_class} references unknown tiers: {unknown}")
    requires_approval = bool(row.get("requires_human_approval"))
    return {
        "schema_version": "dad.intelligence_routing_advice.v1",
        "advice_only": True,
        "execution_authorized": False,
        "task_class": task_class,
        "recommended_start_tiers": start_tiers,
        "requires_human_approval": requires_approval,
        "rule": str(row.get("rule", "")),
        "registry_id": str(registry.get("registry_id", "")),
        "registry_status": str(registry.get("status", "")),
        "match_basis": (
            "deterministic keyword overlap against task_class hints, then "
            "task_class_defaults.start_tier from config/intelligence-routing-registry.json; "
            "advice only, not a difficulty score or dispatch authorization"
        ),
        "authority_boundary": str(
            registry.get(
                "authority_boundary",
                "Routing advice is candidate policy only; humans and local repo authority override.",
            )
        ),
    }


def collect_declared_default_tiers(hub_root: Path) -> list[tuple[str, list[str]]]:
    """Return (source_ref, default_tier) pairs declared on skill library rows."""

    library_path = hub_root / "registry" / "agent-skill-library.json"
    if not library_path.is_file():
        return []
    library = json.loads(library_path.read_text(encoding="utf-8"))
    rows: list[tuple[str, list[str]]] = []
    for skill in library.get("skills", []):
        if not isinstance(skill, dict):
            continue
        tiers = skill.get("default_tier")
        if tiers is None:
            continue
        if not isinstance(tiers, list):
            raise ValueError(f"{skill.get('skill_id')}: default_tier must be an array")
        rows.append(
            (str(skill.get("skill_id", library_path.as_posix())), [str(t) for t in tiers])
        )
    return rows


def validate_declared_default_tiers(hub_root: Path) -> list[str]:
    """Return finding strings for any skill default_tier outside the registry."""

    registry = load_intelligence_routing_registry(hub_root)
    findings: list[str] = []
    for source_ref, tiers in collect_declared_default_tiers(hub_root):
        unknown = validate_tier_ids(tiers, registry)
        if unknown:
            findings.append(f"{source_ref}: unknown default_tier ids {unknown}")
        if not tiers:
            findings.append(f"{source_ref}: default_tier must be non-empty when present")
    return findings


__all__ = [
    "ROUTING_REGISTRY_REL",
    "classify_task_class",
    "collect_declared_default_tiers",
    "known_tier_ids",
    "load_intelligence_routing_registry",
    "recommend_start_tiers",
    "validate_declared_default_tiers",
    "validate_tier_ids",
]
