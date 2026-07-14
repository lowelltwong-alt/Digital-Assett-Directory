from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory.mcp_graph_server import DADGraphMCPServer
from digital_asset_directory.transport import data_path
from digital_asset_directory.utils import sha256_file

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
RUNNER = CliRunner()
FORBIDDEN_KEYS = {"score", "rank", "centrality", "best", "top"}


def _assert_no_forbidden_keys(value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert key.lower() not in FORBIDDEN_KEYS
            _assert_no_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_keys(child)


def _mcp_hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    (hub / "registry").mkdir(parents=True)
    (hub / "registry" / "graph-surface-registry.json").write_text(
        (ROOT / "registry" / "graph-surface-registry.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (hub / "registry" / "graph-edge-registry.json").write_text(
        (ROOT / "registry" / "graph-edge-registry.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (hub / "registry" / "schema-registry.json").write_text(
        (ROOT / "registry" / "schema-registry.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    graph = {
        "schema_version": "0.1.0",
        "generated_at": "2026-07-07T00:00:00+00:00",
        "manifest_path": "processed/learning/lesson-graph-manifest.json",
        "nodes": [
            {
                "node_id": "lesson:alpha",
                "node_type": "lesson",
                "label": "Alpha lesson",
                "review_status": "candidate",
            },
            {
                "node_id": "repo:demo",
                "node_type": "repo",
                "label": "Demo repo",
                "review_status": "candidate",
            },
        ],
        "edges": [
            {
                "edge_id": "edge:alpha-demo",
                "source": "lesson:alpha",
                "target": "repo:demo",
                "edge_type": "learned_in",
                "edge_class": "join",
                "edge_basis": "lesson.repository",
                "method_version": "",
                "review_status": "candidate",
            }
        ],
        "authority_boundary": "candidate only",
    }
    learning = data_path(hub, "learning")
    learning.mkdir(parents=True, exist_ok=True)
    graph_path = learning / "lesson-graph.json"
    graph_path.write_text(json.dumps(graph, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema_version": "0.1.0",
        "surface_id": "lesson-graph",
        "ontology_id": "knowledge",
        "generated_at": "2026-07-07T00:00:00+00:00",
        "builder_version": "test-builder",
        "graph_path": "processed/learning/lesson-graph.json",
        "manifest_path": "processed/learning/lesson-graph-manifest.json",
        "input_hashes": {},
        "methodology_hashes": {},
        "edge_registry_hash": "missing",
        "graph_content_hash": f"sha256:{sha256_file(graph_path)}",
        "freshness": {
            "state": "fresh",
            "computed_at": "2026-07-07T00:00:00+00:00",
            "reasons": [],
        },
        "counts": {"node_count": 2, "edge_count": 1},
        "authority_boundary": "candidate only",
    }
    (learning / "lesson-graph-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    return hub


def _request(server: DADGraphMCPServer, method: str, params: dict | None = None):
    return server.handle_request({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})


def _call_tool(server: DADGraphMCPServer, name: str, arguments: dict | None = None) -> dict:
    response = _request(
        server,
        "tools/call",
        {"name": name, "arguments": arguments or {}},
    )
    assert "error" not in response, response
    return response["result"]["structuredContent"]


def test_graph_mcp_initialize_lists_tools_and_resources(tmp_path: Path):
    server = DADGraphMCPServer(_mcp_hub(tmp_path))

    initialized = _request(server, "initialize")
    assert initialized["result"]["serverInfo"]["name"] == "dad-local-graph-surfaces"
    tools = _request(server, "tools/list")["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "dad_graph_surface_status",
        "dad_graph_get_node",
        "dad_graph_neighbors",
        "dad_graph_search_nodes",
        "dad_mcp_dependency_status",
        "dad_mcp_dependency_impact",
        "dad_mcp_dependency_refresh_candidate",
    }
    resources = _request(server, "resources/list")["result"]["resources"]
    uris = {resource["uri"] for resource in resources}
    assert "dad://registry/graph-surface-registry" in uris
    assert "dad://surface/lesson-graph/manifest" in uris
    assert "dad://report/scheduled-tasks" in uris
    assert "dad://report/surface-version-status" in uris
    manifest = _request(
        server,
        "resources/read",
        {"uri": "dad://surface/lesson-graph/manifest"},
    )
    assert manifest["result"]["contents"][0]["mimeType"] == "application/json"
    surface_status = _request(
        server,
        "resources/read",
        {"uri": "dad://report/surface-version-status"},
    )
    assert surface_status["result"]["contents"][0]["mimeType"] == "application/json"
    scheduled_tasks = _request(
        server,
        "resources/read",
        {"uri": "dad://report/scheduled-tasks"},
    )
    assert scheduled_tasks["result"]["contents"][0]["mimeType"] == "application/json"
    scheduled_payload = json.loads(scheduled_tasks["result"]["contents"][0]["text"])
    assert scheduled_payload["schema_version"] == "dad.daemon.scheduled_tasks.v1"


def test_graph_mcp_rejects_unknown_and_hostile_resource_uris(tmp_path: Path):
    server = DADGraphMCPServer(_mcp_hub(tmp_path))

    for uri in [
        "dad://surface/../manifest",
        "dad://surface/lesson-graph/not-manifest",
        "dad://registry/graph-surface-registry-extra",
        "dad://surface/lesson-graph/manifest?at=anything",
    ]:
        response = _request(server, "resources/read", {"uri": uri})
        assert response["error"]["code"] == -32602


def test_graph_mcp_tools_return_candidate_boundaries_without_false_authority(
    tmp_path: Path,
):
    server = DADGraphMCPServer(_mcp_hub(tmp_path))

    status = _call_tool(server, "dad_graph_surface_status")
    node = _call_tool(
        server,
        "dad_graph_get_node",
        {"surface_id": "lesson-graph", "node_id": "lesson:alpha"},
    )
    neighbors = _call_tool(
        server,
        "dad_graph_neighbors",
        {"surface_id": "lesson-graph", "node_id": "lesson:alpha", "limit": 1},
    )
    search = _call_tool(
        server,
        "dad_graph_search_nodes",
        {"surface_id": "lesson-graph", "query": "Alpha", "limit": 5},
    )

    for payload in [status, node, neighbors, search]:
        assert payload["authority_boundary"]
        _assert_no_forbidden_keys(payload)
    assert node["review_status"] == "candidate"
    assert neighbors["edges"][0]["edge_class"] == "join"
    assert "method_version" in neighbors["edges"][0]
    assert search["result_count"] == 1


def test_graph_mcp_limit_enforced_and_no_vendor_env_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    server = DADGraphMCPServer(_mcp_hub(tmp_path))

    assert _request(server, "tools/list")["result"]["tools"]
    response = _request(
        server,
        "tools/call",
        {
            "name": "dad_graph_neighbors",
            "arguments": {
                "surface_id": "lesson-graph",
                "node_id": "lesson:alpha",
                "limit": 101,
            },
        },
    )
    assert response["error"]["code"] == -32602


def test_graph_mcp_cli_help_exposes_stdio_server():
    result = RUNNER.invoke(app, ["mcp", "graph-stdio", "--help"])

    assert result.exit_code == 0, result.output
    assert "stdio" in result.output.lower()
