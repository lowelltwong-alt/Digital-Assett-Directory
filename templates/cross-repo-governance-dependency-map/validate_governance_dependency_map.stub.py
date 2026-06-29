#!/usr/bin/env python3
"""Validate a repo-family governance dependency map.

Adapt placeholders and required path sets to the adopting repo. Keep this
validator fail-closed: missing authority fields, missing companion surfaces, or
watched governance paths without map coverage should return a non-zero exit.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "governance" / "GOVERNANCE_DEPENDENCY_MAP.yaml"

REQUIRED_TOP_LEVEL = {
    "object_type",
    "trust_zone",
    "lifecycle_status",
    "schema_version",
    "map_id",
    "source_repo",
    "map_authority",
    "update_policy",
    "artifacts",
}


class GovernanceDependencyMapError(ValueError):
    """Raised when the governance dependency map is invalid."""


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GovernanceDependencyMapError(f"{path}: expected a YAML mapping")
    return data


def validate_dependency_map(path: Path = MAP) -> dict[str, Any]:
    data = _read_yaml(path)
    missing = sorted(REQUIRED_TOP_LEVEL - set(data))
    if missing:
        raise GovernanceDependencyMapError(f"{path}: missing keys {missing}")
    if data["object_type"] != "governance_dependency_map":
        raise GovernanceDependencyMapError(f"{path}: object_type must be governance_dependency_map")
    authority = data["map_authority"]
    if not isinstance(authority, dict):
        raise GovernanceDependencyMapError(f"{path}: map_authority must be a mapping")
    if authority.get("records_governance_dependencies") is not True:
        raise GovernanceDependencyMapError(
            f"{path}: map_authority.records_governance_dependencies must be true"
        )
    for key in (
        "authorizes_child_repo_override",
        "authorizes_source_data_change",
        "authorizes_external_import",
    ):
        if authority.get(key) is not False:
            raise GovernanceDependencyMapError(f"{path}: map_authority.{key} must be false")
    policy = data["update_policy"]
    if not isinstance(policy, dict) or policy.get("changed_path_gate_enabled") is not True:
        raise GovernanceDependencyMapError(f"{path}: update_policy.changed_path_gate_enabled must be true")
    if not data.get("artifacts"):
        raise GovernanceDependencyMapError(f"{path}: artifacts must be non-empty")
    return data


def main() -> int:
    try:
        validate_dependency_map()
    except (OSError, yaml.YAMLError, GovernanceDependencyMapError) as exc:
        print(f"Governance dependency map validation failed: {exc}", file=sys.stderr)
        return 1
    print("Governance dependency map validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

