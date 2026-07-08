from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

from digital_asset_directory.mcp_server import (
    call_mcp_tool,
    handle_mcp_request,
    list_mcp_resources,
    mcp_tool_definitions,
    read_mcp_resource,
)
from digital_asset_directory.transport import data_path


pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "processed" / "harnesses" / ".mcp-tests"


def _mcp_hub() -> Path:
    hub = TEST_ROOT / f"hub-{uuid.uuid4().hex}"
    hub.mkdir(parents=True)
    registry = hub / "registry"
    registry.mkdir()
    graph_dir = data_path(hub, "learning")
    graph_dir.mkdir(parents=True)
    graph = {
        "schema_version": "0.1.0",
        "generated_at": "2026-07-07T00:00:00+00:00",
        "authority_boundary": "candidate graph evidence only",
        "nodes": [
            {
                "node_id": "lesson:one",
                "node_type": "lesson",
                "label": "One lesson",
                "review_status": "candidate",
            },
            {
                "node_id": "pattern:loop",
                "node_type": "pattern",
                "label": "Loop pattern",
            },
        ],
        "edges": [
            {
                "edge_id": "edge:one-loop",
                "source": "lesson:one",
                "target": "pattern:loop",
                "edge_type": "matches_pattern",
                "edge_class": "join",
                "edge_basis": "lesson.reusable_patterns.pattern-id-or-label",
                "method_version": "",
                "created_at": "",
                "evidence_refs": ["dad:lesson:one"],
                "review_status": "candidate",
            }
        ],
    }
    manifest = {
        "schema_version": "0.1.0",
        "surface_id": "lesson-graph",
        "ontology_id": "knowledge",
        "generated_at": "2026-07-07T00:00:00+00:00",
        "builder_version": "test-builder.v1",
        "graph_path": "processed/learning/lesson-graph.json",
        "manifest_path": "processed/learning/lesson-graph-manifest.json",
        "input_hashes": {},
        "methodology_hashes": {},
        "edge_registry_hash": "missing",
        "graph_content_hash": "missing",
        "freshness": {
            "state": "fresh",
            "computed_at": "2026-07-07T00:00:00+00:00",
            "reasons": [],
        },
        "counts": {
            "node_count": 2,
            "edge_count": 1,
            "nodes_by_type": {"lesson": 1, "pattern": 1},
            "edges_by_type": {"matches_pattern": 1},
        },
        "coverage": {},
        "authority_boundary": "candidate graph evidence only",
    }
    (graph_dir / "lesson-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (graph_dir / "lesson-graph-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (registry / "graph-surface-registry.json").write_text(
        json.dumps(
            {
                "registry_version": "0.1.0",
                "surfaces": [
                    {
                        "surface_id": "lesson-graph",
                        "status": "active",
                        "ontology_id": "knowledge",
                        "outputs": {
                            "manifest_logical_path": "learning/lesson-graph-manifest.json",
                            "body_logical_path": "learning/lesson-graph.json",
                        },
                        "review_status": "candidate",
                        "authority_boundary": "candidate graph evidence only",
                    },
                    {
                        "surface_id": "repo-status",
                        "status": "planned",
                        "ontology_id": "operations",
                        "outputs": {
                            "manifest_logical_path": "reports/repo-status-surface-manifest.json",
                            "body_logical_path": "reports/repo-status-surface.json",
                        },
                        "review_status": "candidate",
                        "authority_boundary": "planned placeholder only",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (registry / "graph-edge-registry.json").write_text(
        json.dumps({"registry_version": "0.1.0", "edge_types": []}),
        encoding="utf-8",
    )
    (registry / "aios-governance-kernel.json").write_text(
        json.dumps({"registry_id": "aios-governance-kernel"}),
        encoding="utf-8",
    )
    return hub


def _walk_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def _resource_json(resource: dict) -> dict:
    text = resource["text"].split("\n", 1)[1]
    return json.loads(text)


def test_mcp_resources_are_registry_resolved_and_reject_traversal():
    hub = _mcp_hub()
    try:
        report_dir = data_path(hub, "central_reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "mcp-smoke.json").write_text(
            json.dumps({"report_id": "mcp-smoke", "status": "candidate"}),
            encoding="utf-8",
        )
        packet_dir = data_path(hub, "fable_packets")
        packet_dir.mkdir(parents=True, exist_ok=True)
        (packet_dir / "aios-graph-surface.md").write_text(
            "# AIOS Graph Surface Packet\n", encoding="utf-8"
        )
        resources = list_mcp_resources(hub)
        uris = {row["uri"] for row in resources}

        assert "dad://registry/graph-surface-registry" in uris
        assert "dad://surface/lesson-graph/manifest" in uris
        assert "dad://surface/repo-status/manifest" not in uris
        assert "dad://kernel/aios-governance" in uris

        manifest = read_mcp_resource(hub, "dad://surface/lesson-graph/manifest")
        assert manifest["mimeType"] == "application/json"
        assert manifest["text"].startswith("authority_boundary:")
        assert _resource_json(manifest)["surface_id"] == "lesson-graph"

        report = read_mcp_resource(hub, "dad://report/mcp-smoke")
        assert report["mimeType"] == "application/json"
        assert report["text"].startswith("authority_boundary:")
        assert _resource_json(report)["report_id"] == "mcp-smoke"

        kernel = read_mcp_resource(hub, "dad://kernel/aios-governance")
        assert kernel["mimeType"] == "application/json"
        assert kernel["text"].startswith("authority_boundary:")
        assert _resource_json(kernel)["registry_id"] == "aios-governance-kernel"

        packet = read_mcp_resource(hub, "dad://packet/aios-graph-surface")
        assert packet["mimeType"] == "text/markdown"
        assert packet["text"].startswith("authority_boundary:")
        assert "AIOS Graph Surface Packet" in packet["text"]

        with pytest.raises(Exception, match="path traversal|Unknown DAD MCP resource"):
            read_mcp_resource(hub, "dad://registry/../source-of-truth")
        with pytest.raises(Exception, match="Unknown"):
            read_mcp_resource(hub, "dad://surface/lesson/graph/manifest")
        with pytest.raises(Exception, match="not available"):
            read_mcp_resource(hub, "dad://surface/repo-status/manifest")
        with pytest.raises(Exception, match="Report not found"):
            read_mcp_resource(hub, "dad://report/mcp")
    finally:
        shutil.rmtree(hub, ignore_errors=True)


def test_mcp_graph_tools_include_boundaries_limits_and_no_ranking_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    for env_name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "CLAUDE_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)
    hub = _mcp_hub()
    try:
        status = call_mcp_tool(hub, "dad_graph_surface_status", {})
        assert status["authority_boundary"]
        assert status["surfaces"][0]["freshness"]["state"] == "fresh"
        assert status["surfaces"][0]["review_status"] == "candidate"

        node = call_mcp_tool(
            hub,
            "dad_graph_get_node",
            {"surface_id": "lesson-graph", "node_id": "lesson:one"},
        )
        assert node["authority_boundary"]
        assert node["surface_freshness"]["state"] == "fresh"
        assert node["review_status"] == "candidate"
        assert node["node"]["review_status"] == "candidate"

        neighbors = call_mcp_tool(
            hub,
            "dad_graph_neighbors",
            {
                "surface_id": "lesson-graph",
                "node_id": "lesson:one",
                "direction": "outgoing",
                "limit": 9999,
            },
        )
        assert neighbors["limit"] == 50
        edge = neighbors["neighbors"][0]["edge"]
        assert edge["edge_class"] == "join"
        assert "method_version" in edge
        assert edge["review_status"] == "candidate"

        search = call_mcp_tool(
            hub,
            "dad_graph_search_nodes",
            {"surface_id": "lesson-graph", "query": "loop", "limit": 0},
        )
        assert search["limit"] == 1
        forbidden = {"score", "rank", "centrality", "best", "top"}
        assert forbidden.isdisjoint(set(_walk_keys(search)))
        assert search["nodes"][0]["node"]["node_id"] == "pattern:loop"

        tool_names = {tool["name"] for tool in mcp_tool_definitions()}
        assert tool_names == {
            "dad_graph_surface_status",
            "dad_graph_get_node",
            "dad_graph_neighbors",
            "dad_graph_search_nodes",
        }
        assert not any(
            verb in name
            for name in tool_names
            for verb in ("write", "create", "update", "delete", "checkpoint", "push")
        )
    finally:
        shutil.rmtree(hub, ignore_errors=True)


def test_mcp_jsonrpc_tools_call_returns_text_payload():
    hub = _mcp_hub()
    try:
        response = handle_mcp_request(
            hub,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "dad_graph_surface_status",
                    "arguments": {"surface_id": "lesson-graph"},
                },
            },
        )

        assert response is not None
        assert response["result"]["isError"] is False
        payload = json.loads(response["result"]["content"][0]["text"])
        assert payload["surfaces"][0]["surface_id"] == "lesson-graph"
    finally:
        shutil.rmtree(hub, ignore_errors=True)
