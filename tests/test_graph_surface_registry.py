from __future__ import annotations

import importlib
import json
from pathlib import Path

from jsonschema.validators import validator_for
import pytest

from digital_asset_directory.transport import DATA_PLANE_PATHS

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _validate(schema_name: str, payload: dict) -> None:
    registry = _load_json("registry/schema-registry.json")
    schema = _load_json(registry["schemas"][schema_name])
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def test_graph_surface_registry_is_registered_and_schema_validates() -> None:
    schema_registry = _load_json("registry/schema-registry.json")["schemas"]
    assert (
        schema_registry["graph_surface_registry"]
        == "schemas/graph-surface-registry.schema.json"
    )
    assert (
        schema_registry["graph_surface_manifest"]
        == "schemas/graph-surface-manifest.schema.json"
    )

    _validate("graph_surface_registry", _load_json("registry/graph-surface-registry.json"))


def test_graph_surface_registry_uses_reviewed_inputs_and_logical_outputs() -> None:
    registry = _load_json("registry/graph-surface-registry.json")
    surface_ids = {surface["surface_id"] for surface in registry["surfaces"]}
    assert {
        "lesson-graph",
        "graph-inference-overlay",
        "research-intake-graph",
        "exception-clusters",
        "repo-status",
    } <= surface_ids

    for surface in registry["surfaces"]:
        for source_input in surface["source_inputs"]:
            kind = source_input["kind"]
            ref = source_input["ref"]
            if kind == "data_surface":
                assert ref in DATA_PLANE_PATHS
            elif kind == "registry_path":
                assert ref.startswith("registry/")
                assert (ROOT / ref).exists()
            elif kind == "schema_path":
                assert ref.startswith("schemas/")
                assert (ROOT / ref).exists()
        for output in surface["outputs"].values():
            assert not output.startswith(("processed/", "raw/", "state/", "audit/"))


def test_wired_graph_surface_builders_resolve_to_real_code() -> None:
    registry = _load_json("registry/graph-surface-registry.json")
    wired = [
        surface
        for surface in registry["surfaces"]
        if surface["builder"]["availability"] == "wired"
    ]
    assert {surface["surface_id"] for surface in wired} == {
        "lesson-graph",
        "research-intake-graph",
    }
    for surface in wired:
        module_ref = surface["builder"]["module"]
        module_name, _, attr_name = module_ref.rpartition(".")
        assert module_name and attr_name
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name)
