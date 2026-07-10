from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for
import pytest

from digital_asset_directory.learning import build_lesson_graph
from digital_asset_directory.models import LessonRecord
from digital_asset_directory.transport import apply_data_migration

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _validate_lesson_graph(payload: dict) -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    schema = json.loads((ROOT / registry["schemas"]["lesson_graph"]).read_text())
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _validate_graph_edge_registry(payload: dict) -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    schema = json.loads((ROOT / registry["schemas"]["graph_edge_registry"]).read_text())
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _validate_graph_surface_manifest(payload: dict) -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    schema = json.loads(
        (ROOT / registry["schemas"]["graph_surface_manifest"]).read_text()
    )
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _write_lesson(hub: Path, record: LessonRecord) -> None:
    dated = record.created_at[:10]
    path = hub / "raw" / "lessons" / dated / f"{record.lesson_id.split(':')[-1]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(), encoding="utf-8")


def _graph_hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    hub.mkdir()
    patterns = {
        "registry_version": "0.1.0",
        "status": "seed",
        "patterns": [
            {
                "id": "governed_learning_loop_system",
                "label": "Governed learning loop system",
                "description": "Lessons and review loops that improve future agent behavior.",
                "leverage": "very_high",
                "recognition_mode": "repository_composite",
                "positive_signals": ["lesson or workflow assets"],
                "missing_evidence": ["repeated feedback records"],
            }
        ],
        "rule": "Pattern matches are generated candidate evidence.",
    }
    offerings = {
        "schema_version": "0.1.0",
        "registry_id": "dad-offerings-registry",
        "offerings": [
            {
                "offering_id": "dad:offering:test-asset",
                "name": "Test Asset",
                "offering_type": "asset",
                "path": "assets/test-asset",
            }
        ],
    }
    (hub / "registry").mkdir()
    (hub / "registry" / "asset-pattern-registry.json").write_text(
        json.dumps(patterns), encoding="utf-8"
    )
    (hub / "registry" / "dad-offerings-registry.json").write_text(
        json.dumps(offerings), encoding="utf-8"
    )
    repo_path = tmp_path / "repo-one"
    repo_path.mkdir()
    _write_lesson(
        hub,
        LessonRecord(
            lesson_id="dad:lesson:graph-test-1",
            created_at="2026-07-02T00:00:00+00:00",
            repository=str(repo_path),
            task="build the loop",
            agent="test",
            summary="Learned a governed loop shape worth reusing",
            lessons=["capture pattern sightings during builds"],
            reusable_patterns=["governed_learning_loop_system", "brand_new_pattern_idea"],
            evidence=["asset:dad:offering:test-asset", "asset:dad:offering:missing"],
        ),
    )
    usage_path = hub / "processed" / "usage" / "repo-asset-usage.jsonl"
    usage_path.parent.mkdir(parents=True)
    usage_rows = [
        {
            "usage_id": "dad:usage:test-1",
            "repo": str(repo_path),
            "asset_id": "dad:offering:test-asset",
            "status": "using",
        },
        {
            "usage_id": "dad:usage:test-2",
            "repo": str(repo_path),
            "asset_id": "dad:offering:test-asset",
            "status": "watching",
        },
    ]
    usage_path.write_text(
        "".join(json.dumps(row) + "\n" for row in usage_rows), encoding="utf-8"
    )
    return hub


def test_build_lesson_graph_compiles_candidate_nodes_and_edges(tmp_path: Path):
    hub = _graph_hub(tmp_path)

    result = build_lesson_graph(hub)
    graph = result["graph"]
    _validate_lesson_graph(graph)

    assert Path(result["path"]).exists()
    assert Path(result["manifest_path"]).exists()
    assert graph["edge_registry_version"]
    assert graph["manifest_path"] == "processed/learning/lesson-graph-manifest.json"
    node_ids = {node["node_id"] for node in graph["nodes"]}
    assert "lesson:dad:lesson:graph-test-1" in node_ids
    assert "pattern:governed_learning_loop_system" in node_ids
    assert "offering:dad:offering:test-asset" in node_ids
    assert "repo:repo_one" in node_ids

    assert graph["edges_by_type"] == {
        "learned_in": 1,
        "matches_pattern": 1,
        "about_asset": 1,
        "uses_asset": 1,
        "watches_asset": 1,
    }
    for edge in graph["edges"]:
        assert edge["review_status"] == "candidate"
        assert edge["edge_class"] == "join"
        assert edge["edge_basis"]
        assert isinstance(edge["evidence_refs"], list)

    assert graph["pattern_gap_candidates"] == [
        {"reusable_pattern": "brand_new_pattern_idea", "lesson_mentions": 1}
    ]
    assert graph["unmatched_asset_refs"] == [
        {"asset_id": "dad:offering:missing", "lesson_mentions": 1}
    ]
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    _validate_graph_surface_manifest(manifest)
    assert manifest["surface_id"] == "lesson-graph"
    assert manifest["ontology_id"] == "knowledge"
    assert manifest["graph_content_hash"].startswith("sha256:")
    assert manifest["edge_registry_hash"] == "missing" or manifest[
        "edge_registry_hash"
    ].startswith("sha256:")
    assert manifest["freshness"]["state"] == "fresh"
    assert manifest["input_hashes"]["raw/lessons"].startswith("sha256:")
    assert "learned_in" in manifest["edge_definitions_present"]
    assert "about_asset" in manifest["edge_definitions_present"]


def test_build_lesson_graph_is_idempotent_and_survives_missing_inputs(tmp_path: Path):
    hub = _graph_hub(tmp_path)
    first = build_lesson_graph(hub)["graph"]
    second = build_lesson_graph(hub)["graph"]
    assert first["nodes"] == second["nodes"]
    assert first["edges"] == second["edges"]

    bare_hub = tmp_path / "bare-hub"
    bare_hub.mkdir()
    empty = build_lesson_graph(bare_hub)["graph"]
    _validate_lesson_graph(empty)
    assert empty["lesson_count"] == 0
    assert empty["node_count"] == 0
    assert empty["edge_count"] == 0


def test_build_lesson_graph_writes_to_initialized_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = _graph_hub(tmp_path)
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))

    result = build_lesson_graph(hub)

    assert Path(result["path"]).is_relative_to(data_root)
    assert Path(result["manifest_path"]).is_relative_to(data_root)
    assert (data_root / "processed" / "learning" / "lesson-graph.json").exists()
    assert (data_root / "processed" / "learning" / "lesson-graph-manifest.json").exists()
    assert not (hub / "processed" / "learning" / "lesson-graph.json").exists()
    assert not (hub / "processed" / "learning" / "lesson-graph-manifest.json").exists()


def test_graph_edge_registry_matches_schema_enum():
    registry_payload = json.loads(
        (ROOT / "registry" / "graph-edge-registry.json").read_text(encoding="utf-8")
    )
    _validate_graph_edge_registry(registry_payload)

    lesson_graph_schema = json.loads(
        (ROOT / "schemas" / "lesson-graph.schema.json").read_text(encoding="utf-8")
    )
    schema_edge_types = set(
        lesson_graph_schema["properties"]["edges"]["items"]["properties"]["edge_type"]["enum"]
    )
    registry_edge_types = {row["edge_type"] for row in registry_payload["edge_types"]}
    assert schema_edge_types <= registry_edge_types
    forbidden_claims = {
        row["claim"] for row in registry_payload["forbidden_edge_claims"]
    }
    assert {
        "approved_by",
        "verified",
        "trusted",
        "production_ready",
        "better_than",
        "recommended",
        "canonical",
        "authorized_by",
        "depends_on",
        "replaces",
        "causes",
    } <= forbidden_claims


def test_lesson_graph_schema_rejects_inference_without_method_version():
    payload = {
        "schema_version": "0.1.0",
        "generated_at": "2026-07-02T00:00:00+00:00",
        "edge_registry_version": "0.1.0",
        "manifest_path": "processed/learning/lesson-graph-manifest.json",
        "pattern_library_version": "0.1.0",
        "lesson_count": 0,
        "node_count": 2,
        "edge_count": 1,
        "nodes_by_type": {"offering": 2},
        "edges_by_type": {"complements": 1},
        "nodes": [
            {"node_id": "offering:a", "node_type": "offering", "label": "A"},
            {"node_id": "offering:b", "node_type": "offering", "label": "B"},
        ],
        "edges": [
            {
                "edge_id": "edge:test",
                "source": "offering:a",
                "target": "offering:b",
                "edge_type": "complements",
                "edge_class": "inference",
                "edge_basis": "workflow-stage-adjacency-v1",
                "method_version": "",
                "created_at": "",
                "evidence_refs": ["trace:test"],
                "review_status": "candidate",
            }
        ],
        "pattern_gap_candidates": [],
        "unmatched_asset_refs": [],
        "edge_rule": "candidate only",
        "authority_boundary": "candidate only",
    }

    with pytest.raises(Exception):
        _validate_lesson_graph(payload)
