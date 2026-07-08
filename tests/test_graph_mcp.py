from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from digital_asset_directory.cli import app
from digital_asset_directory.mcp_graph_server import DADGraphMCPServer
from digital_asset_directory.transport import data_path

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "processed" / "harnesses" / ".mcp-compat-tests"
RUNNER = CliRunner()


def _mcp_hub() -> Path:
    hub = TEST_ROOT / f"hub-{uuid.uuid4().hex}"
    hub.mkdir(parents=True)
    registry = hub / "registry"
    registry.mkdir()
    learning = data_path(hub, "learning")
    learning.mkdir(parents=True)
    (learning / "lesson-graph.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "nodes": [
                    {
                        "node_id": "lesson:alpha",
                        "node_type": "lesson",
                        "label": "Alpha lesson",
                    },
                    {"node_id": "repo:demo", "node_type": "repo", "label": "Demo repo"},
                ],
                "edges": [
                    {
                        "edge_id": "edge:alpha-demo",
                        "source": "lesson:alpha",
                        "target": "repo:demo",
                        "edge_type": "learned_in",
                        "edge_class": "join",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (learning / "lesson-graph-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "surface_id": "lesson-graph",
                "freshness": {"state": "fresh", "reasons": []},
                "counts": {"node_count": 2, "edge_count": 1},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (registry / "graph-surface-registry.json").write_text(
        json.dumps(
            {
                "registry_version": "0.1.0",
                "surfaces": [
                    {
                        "surface_id": "lesson-graph",
                        "status": "active",
                        "outputs": {
                            "manifest_logical_path": "learning/lesson-graph-manifest.json",
                            "body_logical_path": "learning/lesson-graph.json",
                        },
                        "review_status": "candidate",
                        "authority_boundary": "candidate graph evidence only",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return hub


def _request(server: DADGraphMCPServer, method: str, params: dict | None = None):
    return server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    )


def test_graph_mcp_compatibility_facade_uses_canonical_server() -> None:
    hub = _mcp_hub()
    try:
        server = DADGraphMCPServer(hub)

        tools = _request(server, "tools/list")["result"]["tools"]
        assert {tool["name"] for tool in tools} == {
            "dad_graph_surface_status",
            "dad_graph_get_node",
            "dad_graph_neighbors",
            "dad_graph_search_nodes",
        }
        resources = _request(server, "resources/list")["result"]["resources"]
        assert "dad://surface/lesson-graph/manifest" in {
            resource["uri"] for resource in resources
        }

        node = _request(
            server,
            "tools/call",
            {
                "name": "dad_graph_get_node",
                "arguments": {"surface_id": "lesson-graph", "node_id": "lesson:alpha"},
            },
        )["result"]["structuredContent"]
        assert node["node"]["node_id"] == "lesson:alpha"
        assert node["authority_boundary"]
        assert node["adapter_authority"] == "optional_wrapper_only"

        hostile = _request(
            server,
            "resources/read",
            {"uri": "dad://registry/../source-of-truth"},
        )
        assert "error" in hostile
    finally:
        shutil.rmtree(hub, ignore_errors=True)


def test_graph_mcp_cli_alias_exposes_stdio_server() -> None:
    result = RUNNER.invoke(app, ["mcp", "graph-stdio", "--help"])

    assert result.exit_code == 0, result.output
    assert "stdio" in result.output.lower()
