from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for
import pytest

from digital_asset_directory.graph_inference import (
    infer_graph,
    load_inference_methodology,
    write_inference_outputs,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    return json.loads((ROOT / registry["schemas"][name]).read_text())


def _validate(schema_name: str, payload: dict) -> None:
    schema = _schema(schema_name)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _offering(oid: str, **facets) -> dict:
    row = {
        "offering_id": oid,
        "name": oid,
        "version": "0.1.0",
        "offering_type": "asset",
        "path": f"assets/{oid.split(':')[-1]}",
        "languages": ["python"],
        "repo_types": ["application"],
        "domains": ["software_engineering"],
        "context_tags": [],
        "task_types": facets.get("task_types", ["coding"]),
        "capabilities": ["c"],
        "applies_when": ["always"],
        "does_not_apply_when": ["never"],
        "public_safe": True,
        "upgrade_channel": "dad_mail",
        "known_upgrades": [],
        "source_refs": ["x"],
        "review_status": "reviewed",
        "authority_boundary": "b",
    }
    for key in ("workflow_stages", "produces", "consumes"):
        if key in facets:
            row[key] = facets[key]
    return row


def _planted_hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    (hub / "registry").mkdir(parents=True)
    (hub / "registry" / "graph-inference-methodology.json").write_text(
        (ROOT / "registry" / "graph-inference-methodology.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    offerings = {
        "schema_version": "0.1.0",
        "registry_id": "dad-offerings-registry",
        "authority_boundary": "b",
        "offerings": [
            # Planted produces/consumes chain: idioms -> mutation -> feedback
            _offering(
                "dad:offering:idioms",
                task_types=["python", "coding"],
                workflow_stages=["generate"],
                produces=["code_change"],
                consumes=["registry_row"],
            ),
            _offering(
                "dad:offering:mutation",
                task_types=["python", "testing"],
                workflow_stages=["validate"],
                produces=["test", "eval_case"],
                consumes=["code_change"],
            ),
            _offering(
                "dad:offering:feedback",
                task_types=["python", "review"],
                workflow_stages=["learn"],
                produces=["lesson"],
                consumes=["eval_case"],
            ),
            # Planted complements pair by stage adjacency (plan <-> generate), shared task token.
            _offering(
                "dad:offering:planner",
                task_types=["python", "coding"],
                workflow_stages=["plan"],
                produces=["report"],
                consumes=["context_pack"],
            ),
            # Noise: unrelated asset, non-adjacent stage, no artifact handoff, different task tokens.
            _offering(
                "dad:offering:noise",
                task_types=["governance"],
                workflow_stages=["ship"],
                produces=["mail_packet"],
                consumes=["fix_outcome"],
            ),
        ],
    }
    (hub / "registry" / "dad-offerings-registry.json").write_text(
        json.dumps(offerings), encoding="utf-8"
    )
    ledger = hub / "processed" / "usage" / "repo-asset-usage.jsonl"
    ledger.parent.mkdir(parents=True)
    # Co-use: idioms + mutation both used in repo-one.
    rows = [
        {"usage_id": "u1", "repo": "/x/repo-one", "asset_id": "dad:offering:idioms", "status": "using"},
        {"usage_id": "u2", "repo": "/x/repo-one", "asset_id": "dad:offering:mutation", "status": "using"},
        {"usage_id": "u3", "repo": "/x/repo-two", "asset_id": "dad:offering:noise", "status": "using"},
    ]
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return hub


def test_methodology_validates():
    _validate(
        "graph_inference_methodology",
        json.loads((ROOT / "registry" / "graph-inference-methodology.json").read_text(encoding="utf-8")),
    )
    methodology = load_inference_methodology(ROOT)
    assert methodology["thresholds"]["min_chain_length"] == 3
    assert methodology["workflow_stages"]["ordered"][0] == "orient"


def test_produces_consumes_chain_is_found_and_ordered(tmp_path: Path):
    hub = _planted_hub(tmp_path)
    result = infer_graph(hub)
    combos = result["inference_nodes"]
    chain_combos = [c for c in combos if c["discovery_basis"] == "combination-produces-consumes-chain-v1"]
    assert len(chain_combos) == 1
    combo = chain_combos[0]
    assert combo["ordered_member_ids"] == [
        "dad:offering:idioms",
        "dad:offering:mutation",
        "dad:offering:feedback",
    ]
    assert combo["chain_length"] == 3
    # noise asset is never a member
    assert "dad:offering:noise" not in combo["ordered_member_ids"]
    handoff_kinds = {h["artifact_kinds"][0] for h in combo["artifact_handoffs"]}
    assert handoff_kinds == {"code_change", "eval_case"}
    # member_of edges exist for all three members
    member_edges = [e for e in result["inference_edges"] if e["edge_type"] == "member_of"]
    assert len({e["source"] for e in member_edges}) == 3
    for edge in result["inference_edges"]:
        assert edge["method_version"]  # every inference edge cites a method version


def test_complements_and_co_used_precision(tmp_path: Path):
    hub = _planted_hub(tmp_path)
    result = infer_graph(hub)
    complements = [e for e in result["inference_edges"] if e["edge_type"] == "complements"]
    # planner (plan) is adjacent to idioms (generate) and shares token "python","coding"
    pairs = {frozenset([e["source"], e["target"]]) for e in complements}
    assert frozenset(["offering:dad:offering:planner", "offering:dad:offering:idioms"]) in pairs
    # noise (ship) is not adjacent to anything relevant and shares no task token
    for edge in complements:
        assert "dad:offering:noise" not in edge["source"] and "dad:offering:noise" not in edge["target"]
    co_used = [e for e in result["inference_edges"] if e["edge_type"] == "co_used_with"]
    assert len(co_used) == 1
    assert co_used[0]["evidence"]["distinct_repo_count"] == 1
    assert frozenset([co_used[0]["source"], co_used[0]["target"]]) == frozenset(
        ["offering:dad:offering:idioms", "offering:dad:offering:mutation"]
    )


def test_inference_is_deterministic(tmp_path: Path):
    hub = _planted_hub(tmp_path)
    first = infer_graph(hub)
    second = infer_graph(hub)
    assert first["inference_edges"] == second["inference_edges"]
    assert first["inference_nodes"] == second["inference_nodes"]


def test_write_outputs_appends_queue_without_duplicates(tmp_path: Path):
    hub = _planted_hub(tmp_path)
    first = write_inference_outputs(hub)
    assert first["combinations_appended"] == first["combinations_total"]
    assert Path(first["report_path"]).exists()
    manifest = json.loads(Path(first["manifest_path"]).read_text(encoding="utf-8"))
    _validate("graph_surface_manifest", manifest)
    assert manifest["surface_id"] == "graph-inference-overlay"
    assert all(isinstance(value, int) for value in manifest["counts"].values())
    assert manifest["counts"]["edge_count"] == len(
        json.loads(Path(first["report_path"]).read_text(encoding="utf-8"))["inference_edges"]
    )
    # second run appends nothing new (dedupe by combination_id)
    second = write_inference_outputs(hub)
    assert second["combinations_appended"] == 0
    queue_lines = [
        line
        for line in Path(second["queue_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(queue_lines) == first["combinations_total"]


def test_live_offering_registry_facets_use_valid_vocab():
    """A1 guard: any facets present on live offerings must use the closed vocabularies."""
    methodology = load_inference_methodology(ROOT)
    valid_stages = set(methodology["workflow_stages"]["ordered"])
    valid_kinds = set(methodology["artifact_kinds"]["values"])
    offerings = json.loads(
        (ROOT / "registry" / "dad-offerings-registry.json").read_text(encoding="utf-8")
    )["offerings"]
    for row in offerings:
        assert set(row.get("workflow_stages", [])) <= valid_stages, row["offering_id"]
        assert set(row.get("produces", [])) <= valid_kinds, row["offering_id"]
        assert set(row.get("consumes", [])) <= valid_kinds, row["offering_id"]
