"""Local read-only MCP adapter for DAD graph surfaces.

This module intentionally has no vendor SDK dependency. It exposes DAD
registries and generated graph surfaces through a small MCP-compatible JSON-RPC
stdio server while keeping DAD schemas, registries, audit records, and human
gates as the authority.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, BinaryIO, TextIO
from urllib.parse import unquote, urlparse

from .transport import DATA_PLANE_PATHS, data_path, data_relative_path
from .utils import json_dumps

MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "dad-local-readonly"
SERVER_VERSION = "0.1.0"
MCP_AUTHORITY_BOUNDARY = (
    "DAD MCP responses are read-only candidate context from registered DAD "
    "surfaces. They do not authorize writes, approvals, ranking claims, remote "
    "MCP, vendor lock-in, downstream mutation, or promotion of generated graph "
    "content to source authority."
)
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,160}$")
MAX_NEIGHBORS_LIMIT = 50
MAX_SEARCH_LIMIT = 25
QUERYABLE_SURFACE_STATUSES = {"active", "partial"}


class MCPError(ValueError):
    def __init__(self, message: str, *, code: int = -32602) -> None:
        super().__init__(message)
        self.code = code


def _safe_id(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text or not SAFE_ID_RE.fullmatch(text):
        raise MCPError(f"Invalid {label}: {text!r}")
    if ".." in text or "/" in text or "\\" in text:
        raise MCPError(f"Invalid {label}: path traversal is not allowed")
    return text


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MCPError(f"Resource not found: {path}", code=-32002) from exc
    except json.JSONDecodeError as exc:
        raise MCPError(f"Invalid JSON resource: {path}: {exc.msg}", code=-32000) from exc
    if not isinstance(payload, dict):
        raise MCPError(f"JSON resource is not an object: {path}", code=-32000)
    return payload


def _graph_surface_registry(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / "registry" / "graph-surface-registry.json")


def _surface_rows(hub_root: Path) -> list[dict[str, Any]]:
    registry = _graph_surface_registry(hub_root)
    rows = registry.get("surfaces", [])
    return [row for row in rows if isinstance(row, dict)]


def _surface_by_id(
    hub_root: Path, surface_id: str, *, require_queryable: bool = False
) -> dict[str, Any]:
    wanted = _safe_id(surface_id, "surface_id")
    for surface in _surface_rows(hub_root):
        if str(surface.get("surface_id", "")) == wanted:
            if require_queryable and str(surface.get("status", "")) not in QUERYABLE_SURFACE_STATUSES:
                raise MCPError(
                    f"Graph surface is not available for MCP queries: {wanted}",
                    code=-32002,
                )
            return surface
    raise MCPError(f"Unknown graph surface: {wanted}", code=-32002)


def _logical_output_path(hub_root: Path, logical_path: str) -> Path:
    path = Path(logical_path)
    if path.is_absolute():
        return path
    if not path.parts:
        return hub_root
    first = path.parts[0]
    aliases = {"reports": "central_reports", "mail": "central_mail"}
    logical = first if first in DATA_PLANE_PATHS else aliases.get(first, "")
    if logical:
        suffix = Path(*path.parts[1:]) if len(path.parts) > 1 else Path()
        return data_path(hub_root, logical) / suffix
    return data_relative_path(hub_root, path)


def _surface_output_path(hub_root: Path, surface: dict[str, Any], key: str) -> Path:
    outputs = surface.get("outputs", {})
    if not isinstance(outputs, dict):
        raise MCPError(f"Surface has no outputs map: {surface.get('surface_id', '')}")
    logical = str(outputs.get(key, "")).strip()
    if not logical:
        raise MCPError(
            f"Surface output missing {key}: {surface.get('surface_id', '')}"
        )
    return _logical_output_path(hub_root, logical)


def _surface_manifest(hub_root: Path, surface_id: str) -> dict[str, Any]:
    surface = _surface_by_id(hub_root, surface_id, require_queryable=True)
    manifest_path = _surface_output_path(hub_root, surface, "manifest_logical_path")
    return _load_json(manifest_path)


def _surface_graph(hub_root: Path, surface_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    surface = _surface_by_id(hub_root, surface_id, require_queryable=True)
    graph_path = _surface_output_path(hub_root, surface, "body_logical_path")
    return surface, _load_json(graph_path)


def _surface_freshness(hub_root: Path, surface_id: str) -> dict[str, Any]:
    try:
        manifest = _surface_manifest(hub_root, surface_id)
    except MCPError:
        return {"state": "unknown", "reasons": ["manifest_missing_or_unreadable"]}
    freshness = manifest.get("freshness", {})
    if isinstance(freshness, dict):
        return freshness
    return {"state": "unknown", "reasons": ["manifest_freshness_missing"]}


def _response_base(
    hub_root: Path, surface_id: str | None = None, surface: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "authority_boundary": MCP_AUTHORITY_BOUNDARY,
        "adapter_authority": "optional_wrapper_only",
        "write_capability": "none",
    }
    if surface_id is not None:
        payload["surface_id"] = surface_id
        payload["surface_freshness"] = _surface_freshness(hub_root, surface_id)
    if surface is not None:
        payload["review_status"] = surface.get("review_status", "candidate")
        payload["surface_authority_boundary"] = surface.get(
            "authority_boundary", MCP_AUTHORITY_BOUNDARY
        )
    return payload


def _limit(value: Any, *, default: int = 25, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < 1:
        return 1
    return min(parsed, maximum)


def _node_matches(node: dict[str, Any], node_id: str) -> bool:
    return str(node.get("node_id", "")) == node_id


def _public_node(node: dict[str, Any]) -> dict[str, Any]:
    public = dict(node)
    public.setdefault("review_status", "candidate")
    return public


def _public_edge(edge: dict[str, Any]) -> dict[str, Any]:
    public = dict(edge)
    public.setdefault("review_status", "candidate")
    public.setdefault("edge_class", "")
    public.setdefault("method_version", "")
    return public


def dad_graph_surface_status(
    hub_root: Path, surface_id: str | None = None
) -> dict[str, Any]:
    rows = []
    for surface in _surface_rows(hub_root):
        sid = str(surface.get("surface_id", ""))
        if surface_id is not None and sid != surface_id:
            continue
        manifest_status = "unread"
        counts: dict[str, Any] = {}
        try:
            manifest = _surface_manifest(hub_root, sid)
            manifest_status = "readable"
            counts = manifest.get("counts", {}) if isinstance(manifest.get("counts"), dict) else {}
        except MCPError:
            manifest = {}
        rows.append(
            {
                "surface_id": sid,
                "surface_status": surface.get("status", ""),
                "ontology_id": surface.get("ontology_id", ""),
                "manifest_status": manifest_status,
                "freshness": manifest.get(
                    "freshness",
                    {"state": "unknown", "reasons": ["manifest_missing_or_unreadable"]},
                ),
                "counts": counts,
                "review_status": surface.get("review_status", "candidate"),
                "authority_boundary": surface.get(
                    "authority_boundary", MCP_AUTHORITY_BOUNDARY
                ),
            }
        )
    if surface_id is not None and not rows:
        raise MCPError(f"Unknown graph surface: {surface_id}", code=-32002)
    return {**_response_base(hub_root), "surfaces": rows}


def dad_graph_get_node(hub_root: Path, surface_id: str, node_id: str) -> dict[str, Any]:
    surface, graph = _surface_graph(hub_root, surface_id)
    wanted = str(node_id or "").strip()
    if not wanted:
        raise MCPError("node_id is required")
    for node in graph.get("nodes", []):
        if isinstance(node, dict) and _node_matches(node, wanted):
            return {
                **_response_base(hub_root, surface_id, surface),
                "node": _public_node(node),
            }
    raise MCPError(f"Node not found: {wanted}", code=-32002)


def dad_graph_neighbors(
    hub_root: Path,
    surface_id: str,
    node_id: str,
    direction: str = "both",
    limit: int = 25,
) -> dict[str, Any]:
    surface, graph = _surface_graph(hub_root, surface_id)
    wanted = str(node_id or "").strip()
    if not wanted:
        raise MCPError("node_id is required")
    direction = str(direction or "both")
    if direction not in {"both", "incoming", "outgoing"}:
        raise MCPError("direction must be one of: both, incoming, outgoing")
    max_rows = _limit(limit, default=25, maximum=MAX_NEIGHBORS_LIMIT)
    nodes = {
        str(node.get("node_id", "")): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict)
    }
    if wanted not in nodes:
        raise MCPError(f"Node not found: {wanted}", code=-32002)
    rows: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        include = (
            (direction in {"both", "outgoing"} and source == wanted)
            or (direction in {"both", "incoming"} and target == wanted)
        )
        if not include:
            continue
        neighbor_id = target if source == wanted else source
        rows.append(
            {
                "neighbor": _public_node(nodes.get(neighbor_id, {"node_id": neighbor_id})),
                "edge": _public_edge(edge),
            }
        )
        if len(rows) >= max_rows:
            break
    return {
        **_response_base(hub_root, surface_id, surface),
        "node_id": wanted,
        "direction": direction,
        "limit": max_rows,
        "neighbors": rows,
    }


def dad_graph_search_nodes(
    hub_root: Path, surface_id: str, query: str, limit: int = 25
) -> dict[str, Any]:
    surface, graph = _surface_graph(hub_root, surface_id)
    needle = str(query or "").strip().casefold()
    if not needle:
        raise MCPError("query is required")
    max_rows = _limit(limit, default=25, maximum=MAX_SEARCH_LIMIT)
    matches: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        haystack = " ".join(
            str(node.get(key, "")) for key in ("node_id", "node_type", "label")
        ).casefold()
        if needle not in haystack:
            continue
        match_fields = [
            key
            for key in ("node_id", "node_type", "label")
            if needle in str(node.get(key, "")).casefold()
        ]
        matches.append({"node": _public_node(node), "match_fields": match_fields})
        if len(matches) >= max_rows:
            break
    return {
        **_response_base(hub_root, surface_id, surface),
        "query": query,
        "limit": max_rows,
        "nodes": matches,
    }


TOOL_HANDLERS = {
    "dad_graph_surface_status": dad_graph_surface_status,
    "dad_graph_get_node": dad_graph_get_node,
    "dad_graph_neighbors": dad_graph_neighbors,
    "dad_graph_search_nodes": dad_graph_search_nodes,
}


def mcp_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "dad_graph_surface_status",
            "description": "Read registered DAD graph surface status and freshness.",
            "inputSchema": {
                "type": "object",
                "properties": {"surface_id": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        {
            "name": "dad_graph_get_node",
            "description": "Read one node from a registered graph surface.",
            "inputSchema": {
                "type": "object",
                "required": ["surface_id", "node_id"],
                "properties": {
                    "surface_id": {"type": "string"},
                    "node_id": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "dad_graph_neighbors",
            "description": "Read bounded incoming/outgoing graph neighbors.",
            "inputSchema": {
                "type": "object",
                "required": ["surface_id", "node_id"],
                "properties": {
                    "surface_id": {"type": "string"},
                    "node_id": {"type": "string"},
                    "direction": {"enum": ["both", "incoming", "outgoing"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_NEIGHBORS_LIMIT},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "dad_graph_search_nodes",
            "description": "Search node id/type/label text without ranking fields.",
            "inputSchema": {
                "type": "object",
                "required": ["surface_id", "query"],
                "properties": {
                    "surface_id": {"type": "string"},
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_LIMIT},
                },
                "additionalProperties": False,
            },
        },
    ]


def _registry_resource(hub_root: Path, registry_id: str) -> tuple[str, str]:
    rid = _safe_id(registry_id, "registry_id")
    path = hub_root / "registry" / f"{rid}.json"
    return "application/json", json_dumps(_load_json(path), pretty=True)


def _surface_manifest_resource(hub_root: Path, surface_id: str) -> tuple[str, str]:
    sid = _safe_id(surface_id, "surface_id")
    return "application/json", json_dumps(_surface_manifest(hub_root, sid), pretty=True)


def _report_resource(hub_root: Path, report_id: str) -> tuple[str, str]:
    wanted = _safe_id(report_id, "report_id")
    report_root = data_path(hub_root, "central_reports")
    for path in sorted(report_root.rglob("*.json")) if report_root.exists() else []:
        payload = _load_json(path)
        if str(payload.get("report_id", path.stem)) == wanted or path.stem == wanted:
            return "application/json", json_dumps(payload, pretty=True)
    raise MCPError(f"Report not found: {wanted}", code=-32002)


def _kernel_resource(hub_root: Path, kernel_id: str) -> tuple[str, str]:
    kid = _safe_id(kernel_id, "kernel_id")
    if kid != "aios-governance":
        raise MCPError(f"Unknown kernel: {kid}", code=-32002)
    return (
        "application/json",
        json_dumps(_load_json(hub_root / "registry" / "aios-governance-kernel.json"), pretty=True),
    )


def _packet_resource(hub_root: Path, packet_id: str) -> tuple[str, str]:
    pid = _safe_id(packet_id, "packet_id")
    packet_root = data_path(hub_root, "fable_packets")
    candidates = []
    if packet_root.exists():
        candidates.extend(path for path in packet_root.rglob("*") if path.is_file())
    candidates.extend(path for path in hub_root.glob(f"{pid}.*") if path.is_file())
    for path in sorted(candidates):
        if path.stem != pid:
            continue
        mime = "application/json" if path.suffix == ".json" else "text/markdown"
        return mime, path.read_text(encoding="utf-8")
    raise MCPError(f"Packet not found: {pid}", code=-32002)


def read_mcp_resource(hub_root: Path, uri: str) -> dict[str, Any]:
    parsed = urlparse(uri)
    if parsed.scheme != "dad":
        raise MCPError("Only dad:// resources are supported")
    host = parsed.netloc
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if host == "registry" and len(parts) == 1:
        mime, text = _registry_resource(hub_root, parts[0])
    elif host == "surface" and len(parts) == 2 and parts[1] == "manifest":
        mime, text = _surface_manifest_resource(hub_root, parts[0])
    elif host == "report" and len(parts) == 1:
        mime, text = _report_resource(hub_root, parts[0])
    elif host == "kernel" and len(parts) == 1:
        mime, text = _kernel_resource(hub_root, parts[0])
    elif host == "packet" and len(parts) == 1:
        mime, text = _packet_resource(hub_root, parts[0])
    else:
        raise MCPError(f"Unknown DAD MCP resource URI: {uri}", code=-32002)
    return {
        "uri": uri,
        "mimeType": mime,
        "text": f"authority_boundary: {MCP_AUTHORITY_BOUNDARY}\n{text}",
    }


def list_mcp_resources(hub_root: Path) -> list[dict[str, Any]]:
    resources = [
        {
            "uri": "dad://registry/graph-surface-registry",
            "name": "Graph Surface Registry",
            "mimeType": "application/json",
        },
        {
            "uri": "dad://registry/graph-edge-registry",
            "name": "Graph Edge Registry",
            "mimeType": "application/json",
        },
        {
            "uri": "dad://kernel/aios-governance",
            "name": "AIOS Governance Kernel",
            "mimeType": "application/json",
        },
    ]
    for surface in _surface_rows(hub_root):
        if str(surface.get("status", "")) not in QUERYABLE_SURFACE_STATUSES:
            continue
        sid = str(surface.get("surface_id", ""))
        try:
            manifest_path = _surface_output_path(
                hub_root, surface, "manifest_logical_path"
            )
        except MCPError:
            continue
        if sid and manifest_path.exists():
            resources.append(
                {
                    "uri": f"dad://surface/{sid}/manifest",
                    "name": f"{sid} Manifest",
                    "mimeType": "application/json",
                }
            )
    return resources


def call_mcp_tool(hub_root: Path, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in TOOL_HANDLERS:
        raise MCPError(f"Unknown tool: {name}", code=-32601)
    args = arguments or {}
    if not isinstance(args, dict):
        raise MCPError("Tool arguments must be an object")
    return TOOL_HANDLERS[name](hub_root, **args)


def _jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_mcp_request(hub_root: Path, request: dict[str, Any]) -> dict[str, Any] | None:
    method = str(request.get("method", ""))
    request_id = request.get("id")
    params = request.get("params", {})
    try:
        if method == "initialize":
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"resources": {}, "tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "resources/list":
            return _jsonrpc_result(request_id, {"resources": list_mcp_resources(hub_root)})
        if method == "resources/read":
            uri = str(params.get("uri", "")) if isinstance(params, dict) else ""
            return _jsonrpc_result(
                request_id, {"contents": [read_mcp_resource(hub_root, uri)]}
            )
        if method == "tools/list":
            return _jsonrpc_result(request_id, {"tools": mcp_tool_definitions()})
        if method == "tools/call":
            if not isinstance(params, dict):
                raise MCPError("tools/call params must be an object")
            result = call_mcp_tool(
                hub_root,
                str(params.get("name", "")),
                params.get("arguments", {}),
            )
            return _jsonrpc_result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json_dumps(result, pretty=True),
                        }
                    ],
                    "isError": False,
                },
            )
        raise MCPError(f"Unsupported MCP method: {method}", code=-32601)
    except MCPError as exc:
        return _jsonrpc_error(request_id, exc.code, str(exc))
    except TypeError as exc:
        return _jsonrpc_error(request_id, -32602, str(exc))


def _read_content_length_message(stream: TextIO | BinaryIO) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line in ("", b""):
            return None
        if isinstance(line, bytes):
            stripped = line.decode("ascii", errors="replace").strip()
        else:
            stripped = line.strip()
        if not stripped:
            break
        name, separator, value = stripped.partition(":")
        if separator:
            headers[name.casefold()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = stream.read(length)
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return json.loads(body)


def _write_content_length_message(stream: TextIO | BinaryIO, payload: dict[str, Any]) -> None:
    body = json_dumps(payload, pretty=False)
    body_bytes = body.encode("utf-8")
    header = f"Content-Length: {len(body_bytes)}\r\n\r\n".encode("ascii")
    try:
        stream.write(header + body_bytes)
    except TypeError:
        stream.write((header + body_bytes).decode("utf-8"))
    stream.flush()


def serve_stdio(
    hub_root: Path,
    *,
    input_stream: TextIO | BinaryIO | None = None,
    output_stream: TextIO | BinaryIO | None = None,
) -> None:
    reader = input_stream or sys.stdin.buffer
    writer = output_stream or sys.stdout.buffer
    while True:
        request = _read_content_length_message(reader)
        if request is None:
            return
        response = handle_mcp_request(hub_root, request)
        if response is not None:
            _write_content_length_message(writer, response)
