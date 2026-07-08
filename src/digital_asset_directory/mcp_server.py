"""Local read-only MCP server for DAD graph surfaces.

This is intentionally dependency-free and stdio-only. It implements the MCP
JSON-RPC methods DAD needs for local graph resources and query tools while
keeping all authority in DAD registries, schemas, lifecycle commands, audit
records, Git/CI gates, and human gates.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .daemon import daemon_status, scheduled_tasks_report_path, scheduled_tasks_status
from .graph_surfaces import (
    GRAPH_SURFACE_AUTHORITY_BOUNDARY,
    graph_surface_freshness,
    graph_surface_status,
    load_graph_surface_registry,
    resolve_graph_surface_path,
)
from .journal import journal_status
from .surface_versions import surface_version_status_report_path
from .utils import json_dumps

MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "dad-local-graph-surfaces"
SERVER_VERSION = "0.1.0"
MAX_QUERY_LIMIT = 100
DEFAULT_QUERY_LIMIT = 25
FORBIDDEN_RESPONSE_KEYS = {"score", "rank", "centrality", "best", "top"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")

_REGISTRY_RESOURCES = {
    "graph-surface-registry": Path("registry") / "graph-surface-registry.json",
    "graph-edge-registry": Path("registry") / "graph-edge-registry.json",
    "schema-registry": Path("registry") / "schema-registry.json",
}
_REPORT_RESOURCES = {
    "journal-status",
    "daemon-status",
    "graph-surface-status",
    "scheduled-tasks",
    "surface-version-status",
}
_KERNEL_RESOURCES = {
    "aios-governance": Path("processed")
    / "fable5"
    / "deep-dives"
    / "2026-07-07-graph-surface-mcp-handoff"
    / "fable-output"
    / "graph-surface-mcp-kernels.md",
}
_PACKET_RESOURCES = {
    "graph-surface-mcp-handoff": Path("processed")
    / "fable5"
    / "deep-dives"
    / "2026-07-07-graph-surface-mcp-handoff"
    / "README.md",
    "2026-07-07-graph-surface-mcp-handoff": Path("processed")
    / "fable5"
    / "deep-dives"
    / "2026-07-07-graph-surface-mcp-handoff"
    / "README.md",
}


class MCPError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _validate_id(value: str, label: str) -> str:
    if not value or "/" in value or "\\" in value or ".." in value or not ID_PATTERN.match(value):
        raise MCPError(-32602, f"Invalid {label}: {value}")
    return value


def _bounded_limit(raw: Any) -> int:
    try:
        limit = int(raw if raw is not None else DEFAULT_QUERY_LIMIT)
    except (TypeError, ValueError) as exc:
        raise MCPError(-32602, "limit must be an integer") from exc
    if limit < 1 or limit > MAX_QUERY_LIMIT:
        raise MCPError(-32602, f"limit must be between 1 and {MAX_QUERY_LIMIT}")
    return limit


def _strip_forbidden_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_forbidden_fields(child)
            for key, child in value.items()
            if key.lower() not in FORBIDDEN_RESPONSE_KEYS
        }
    if isinstance(value, list):
        return [_strip_forbidden_fields(child) for child in value]
    return value


def _surface_by_id(hub_root: Path, surface_id: str) -> dict[str, Any]:
    _validate_id(surface_id, "surface_id")
    registry = load_graph_surface_registry(hub_root)
    for surface in registry.get("surfaces", []):
        if surface.get("surface_id") == surface_id:
            return surface
    raise MCPError(-32602, f"Unknown graph surface: {surface_id}")


def _surface_paths(hub_root: Path, surface: dict[str, Any]) -> tuple[Path, Path]:
    outputs = surface.get("outputs", {})
    try:
        manifest = resolve_graph_surface_path(hub_root, str(outputs["manifest_logical_path"]))
        body = resolve_graph_surface_path(hub_root, str(outputs["body_logical_path"]))
    except (KeyError, ValueError) as exc:
        raise MCPError(-32603, f"Invalid graph surface registry output: {exc}") from exc
    return manifest, body


def _load_surface_graph(hub_root: Path, surface_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    surface = _surface_by_id(hub_root, surface_id)
    _manifest_path, body_path = _surface_paths(hub_root, surface)
    if not body_path.exists():
        raise MCPError(-32602, f"Graph surface body is missing: {surface_id}")
    try:
        graph = json.loads(body_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MCPError(-32603, f"Graph surface body is unreadable: {exc}") from exc
    return surface, graph


def _graph_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    rows = graph.get("nodes")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    rows = graph.get("inference_nodes")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _graph_edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    rows = graph.get("edges")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    rows = graph.get("inference_edges")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _sanitize_node(node: dict[str, Any]) -> dict[str, Any]:
    sanitized = _strip_forbidden_fields(node)
    sanitized.setdefault("review_status", node.get("review_status", "candidate"))
    return sanitized


def _sanitize_edge(edge: dict[str, Any]) -> dict[str, Any]:
    return _strip_forbidden_fields(
        {
            "edge_id": edge.get("edge_id", ""),
            "source": edge.get("source", ""),
            "target": edge.get("target", ""),
            "edge_type": edge.get("edge_type", ""),
            "edge_class": edge.get("edge_class", "context"),
            "method_version": edge.get("method_version", ""),
            "edge_basis": edge.get("edge_basis", ""),
            "relationship": edge.get("relationship", ""),
            "review_status": edge.get("review_status", "candidate"),
        }
    )


def dad_graph_get_node(hub_root: Path, *, surface_id: str, node_id: str) -> dict[str, Any]:
    _validate_id(node_id.replace(":", "_"), "node_id")
    surface, graph = _load_surface_graph(hub_root, surface_id)
    for node in _graph_nodes(graph):
        if node.get("node_id") == node_id:
            return _strip_forbidden_fields(
                {
                    "schema_version": "dad.mcp.graph_get_node.v1",
                    "surface_id": surface_id,
                    "surface_freshness": graph_surface_freshness(hub_root, surface),
                    "node": _sanitize_node(node),
                    "review_status": node.get("review_status", "candidate"),
                    "authority_boundary": surface.get(
                        "authority_boundary", GRAPH_SURFACE_AUTHORITY_BOUNDARY
                    ),
                }
            )
    raise MCPError(-32602, f"Unknown node on surface {surface_id}: {node_id}")


def dad_graph_neighbors(
    hub_root: Path,
    *,
    surface_id: str,
    node_id: str,
    limit: int | None = None,
) -> dict[str, Any]:
    _validate_id(node_id.replace(":", "_"), "node_id")
    bounded = _bounded_limit(limit)
    surface, graph = _load_surface_graph(hub_root, surface_id)
    matches = [
        edge
        for edge in _graph_edges(graph)
        if edge.get("source") == node_id or edge.get("target") == node_id
    ][:bounded]
    return _strip_forbidden_fields(
        {
            "schema_version": "dad.mcp.graph_neighbors.v1",
            "surface_id": surface_id,
            "surface_freshness": graph_surface_freshness(hub_root, surface),
            "node_id": node_id,
            "limit_applied": bounded,
            "edge_count": len(matches),
            "edges": [_sanitize_edge(edge) for edge in matches],
            "review_status": "candidate",
            "authority_boundary": surface.get(
                "authority_boundary", GRAPH_SURFACE_AUTHORITY_BOUNDARY
            ),
        }
    )


def dad_graph_search_nodes(
    hub_root: Path,
    *,
    surface_id: str,
    query: str,
    limit: int | None = None,
) -> dict[str, Any]:
    if not query or not str(query).strip():
        raise MCPError(-32602, "query is required")
    bounded = _bounded_limit(limit)
    needle = str(query).casefold()
    surface, graph = _load_surface_graph(hub_root, surface_id)
    results: list[dict[str, Any]] = []
    for node in _graph_nodes(graph):
        haystack = json_dumps(node).casefold()
        if needle in haystack:
            results.append(_sanitize_node(node))
        if len(results) >= bounded:
            break
    return _strip_forbidden_fields(
        {
            "schema_version": "dad.mcp.graph_search_nodes.v1",
            "surface_id": surface_id,
            "surface_freshness": graph_surface_freshness(hub_root, surface),
            "query": query,
            "limit_applied": bounded,
            "result_count": len(results),
            "results": results,
            "review_status": "candidate",
            "authority_boundary": surface.get(
                "authority_boundary", GRAPH_SURFACE_AUTHORITY_BOUNDARY
            ),
        }
    )


def _read_resource_payload(hub_root: Path, uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "dad" or parsed.params or parsed.query or parsed.fragment:
        raise MCPError(-32602, f"Unsupported resource URI: {uri}")
    kind = parsed.netloc
    parts = [part for part in parsed.path.split("/") if part]
    if any(part in {".", ".."} or "\\" in part for part in parts):
        raise MCPError(-32602, f"Invalid resource URI: {uri}")

    if kind == "registry" and len(parts) == 1:
        registry_id = _validate_id(parts[0], "registry_id")
        path = _REGISTRY_RESOURCES.get(registry_id)
        if path is None:
            raise MCPError(-32602, f"Unknown registry resource: {registry_id}")
        return "application/json", (hub_root / path).read_text(encoding="utf-8")

    if kind == "surface" and len(parts) == 2 and parts[1] == "manifest":
        surface = _surface_by_id(hub_root, parts[0])
        manifest_path, _body_path = _surface_paths(hub_root, surface)
        if not manifest_path.exists():
            raise MCPError(-32602, f"Surface manifest is missing: {parts[0]}")
        return "application/json", manifest_path.read_text(encoding="utf-8")

    if kind == "report" and len(parts) == 1:
        report_id = _validate_id(parts[0], "report_id")
        if report_id not in _REPORT_RESOURCES:
            raise MCPError(-32602, f"Unknown report resource: {report_id}")
        if report_id == "journal-status":
            return "application/json", json_dumps(journal_status(hub_root), pretty=True)
        if report_id == "daemon-status":
            return "application/json", json_dumps(daemon_status(hub_root), pretty=True)
        if report_id == "scheduled-tasks":
            path = scheduled_tasks_report_path(hub_root)
            if path.exists():
                return "application/json", path.read_text(encoding="utf-8")
            return "application/json", json_dumps(scheduled_tasks_status(hub_root), pretty=True)
        if report_id == "surface-version-status":
            path = surface_version_status_report_path(hub_root)
            if path.exists():
                return "application/json", path.read_text(encoding="utf-8")
            return "application/json", json_dumps(
                {
                    "schema_version": "dad.surface_versions.status.v1",
                    "status": "missing",
                    "report_path": str(path),
                    "authority_boundary": (
                        "Surface-version status is a central read-only report. "
                        "Generate it with `asset-dir enroll surface-status`; "
                        "missing status does not authorize repo writes."
                    ),
                },
                pretty=True,
            )
        return "application/json", json_dumps(graph_surface_status(hub_root), pretty=True)

    if kind == "kernel" and len(parts) == 1:
        kernel_id = _validate_id(parts[0], "kernel_id")
        path = _KERNEL_RESOURCES.get(kernel_id)
        if path is None:
            raise MCPError(-32602, f"Unknown kernel resource: {kernel_id}")
        return "text/markdown", (hub_root / path).read_text(encoding="utf-8")

    if kind == "packet" and len(parts) == 1:
        packet_id = _validate_id(parts[0], "packet_id")
        path = _PACKET_RESOURCES.get(packet_id)
        if path is None:
            raise MCPError(-32602, f"Unknown packet resource: {packet_id}")
        return "text/markdown", (hub_root / path).read_text(encoding="utf-8")

    raise MCPError(-32602, f"Unsupported resource URI: {uri}")


class DADGraphMCPServer:
    def __init__(self, hub_root: Path) -> None:
        self.hub_root = hub_root.resolve()

    def list_resources(self) -> list[dict[str, Any]]:
        registry = load_graph_surface_registry(self.hub_root)
        resources = [
            {
                "uri": f"dad://registry/{registry_id}",
                "name": registry_id,
                "mimeType": "application/json",
            }
            for registry_id in sorted(_REGISTRY_RESOURCES)
        ]
        resources.extend(
            {
                "uri": f"dad://surface/{surface['surface_id']}/manifest",
                "name": f"{surface['surface_id']} manifest",
                "mimeType": "application/json",
            }
            for surface in registry.get("surfaces", [])
        )
        resources.extend(
            {
                "uri": f"dad://report/{report_id}",
                "name": report_id,
                "mimeType": "application/json",
            }
            for report_id in sorted(_REPORT_RESOURCES)
        )
        resources.append(
            {
                "uri": "dad://kernel/aios-governance",
                "name": "AIOS governance kernels",
                "mimeType": "text/markdown",
            }
        )
        resources.append(
            {
                "uri": "dad://packet/graph-surface-mcp-handoff",
                "name": "Graph surface MCP handoff packet",
                "mimeType": "text/markdown",
            }
        )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        mime_type, text = _read_resource_payload(self.hub_root, uri)
        return {"contents": [{"uri": uri, "mimeType": mime_type, "text": text}]}

    def list_tools(self) -> list[dict[str, Any]]:
        surface_schema = {"type": "string", "minLength": 1}
        limit_schema = {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_LIMIT}
        return [
            {
                "name": "dad_graph_surface_status",
                "description": "Read registered DAD graph surface availability and freshness.",
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
            },
            {
                "name": "dad_graph_get_node",
                "description": "Read one node from a registered DAD graph surface.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["surface_id", "node_id"],
                    "properties": {"surface_id": surface_schema, "node_id": surface_schema},
                },
            },
            {
                "name": "dad_graph_neighbors",
                "description": "Read bounded incident edges for one node.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["surface_id", "node_id"],
                    "properties": {
                        "surface_id": surface_schema,
                        "node_id": surface_schema,
                        "limit": limit_schema,
                    },
                },
            },
            {
                "name": "dad_graph_search_nodes",
                "description": "Search nodes on a registered DAD graph surface with a bounded limit.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["surface_id", "query"],
                    "properties": {
                        "surface_id": surface_schema,
                        "query": {"type": "string", "minLength": 1},
                        "limit": limit_schema,
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = arguments or {}
        if name == "dad_graph_surface_status":
            payload = graph_surface_status(self.hub_root)
        elif name == "dad_graph_get_node":
            payload = dad_graph_get_node(self.hub_root, **arguments)
        elif name == "dad_graph_neighbors":
            payload = dad_graph_neighbors(self.hub_root, **arguments)
        elif name == "dad_graph_search_nodes":
            payload = dad_graph_search_nodes(self.hub_root, **arguments)
        else:
            raise MCPError(-32601, f"Unknown tool: {name}")
        return {
            "content": [
                {
                    "type": "text",
                    "text": json_dumps(_strip_forbidden_fields(payload), pretty=True),
                }
            ],
            "structuredContent": _strip_forbidden_fields(payload),
        }

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = str(request.get("method", ""))
        params = request.get("params") or {}
        try:
            if method == "notifications/initialized":
                return None
            if method == "initialize":
                result = {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"resources": {}, "tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                }
            elif method == "ping":
                result = {}
            elif method == "resources/list":
                result = {"resources": self.list_resources()}
            elif method == "resources/read":
                result = self.read_resource(str(params.get("uri", "")))
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                result = self.call_tool(
                    str(params.get("name", "")),
                    params.get("arguments") if isinstance(params.get("arguments"), dict) else {},
                )
            else:
                raise MCPError(-32601, f"Method not found: {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except MCPError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(exc)},
            }


def run_stdio_server(hub_root: Path) -> None:
    server = DADGraphMCPServer(hub_root)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }
        else:
            response = server.handle_request(request)
        if response is not None:
            sys.stdout.write(json_dumps(response) + "\n")
            sys.stdout.flush()
