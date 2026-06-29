from __future__ import annotations

__test__ = False


def _load_validator():
    from scripts.validate_governance_dependency_map import validate_dependency_map

    return validate_dependency_map


def test_governance_dependency_map_blocks_child_override() -> None:
    validate_dependency_map = _load_validator()
    data = validate_dependency_map()

    assert data["map_authority"]["records_governance_dependencies"] is True
    assert data["map_authority"]["authorizes_child_repo_override"] is False


def test_governance_dependency_map_has_validator_backing() -> None:
    validate_dependency_map = _load_validator()
    data = validate_dependency_map()

    policy = data["update_policy"]
    assert policy["changed_path_gate_enabled"] is True
    assert "scripts/validate_governance_dependency_map.py" in policy["validator"]
    assert policy["required_companion_surfaces_when_governance_changes"]
