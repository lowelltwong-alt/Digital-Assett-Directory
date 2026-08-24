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
from datetime import datetime, timedelta, timezone
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
from .mcp_dependency_map import (
    HOST_EVIDENCE_PATH,
    MAP_PATH,
    MCPDependencyMapError,
    build_mcp_dependency_refresh_candidate,
    mcp_dependency_impact,
    validate_mcp_dependency_map,
)
from .surface_versions import surface_version_status_report_path
from .utils import json_dumps
from .portfolio_intents import fold_plan_index, load_plan_revision, read_events as read_intent_events
from .portfolio_weekly_digest import build_weekly_digest
from .entity_identity import fold_state as fold_entity_state, read_events as read_entity_events
from .entity_graph import build_entity_graph, reverse_blast_radius
from .mcp_packets import (
    MCPPacketError,
    prepare_lifecycle_packet,
    record_lifecycle_result,
)

MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "dad-local-graph-surfaces"
SERVER_VERSION = "0.1.0"
MAX_QUERY_LIMIT = 100
DEFAULT_QUERY_LIMIT = 25
FORBIDDEN_RESPONSE_KEYS = {"score", "rank", "centrality", "best", "top"}
SENSITIVE_RESPONSE_KEY = re.compile(
    r"(?:authorization|api[_-]?key|password|secret|private[_-]?key|token)",
    re.IGNORECASE,
)
LOCAL_PATH_TEXT = re.compile(r"(?i)(?:[A-Z]:[\\/]|\\\\)[^\s<>\"']+")
SENSITIVE_ERROR_TEXT = re.compile(
    r"(?i)(?:authorization|api[_-]?key|password|secret|private[_-]?key|token)"
    r"\s*[:=]\s*[^\s,;]+"
)
PROMPT_SENSITIVE_TEXT = re.compile(
    r"(?i)(?:raw\s+(?:conversation|payload|source)|private(?:[_ -]?(?:source|data|payload|file))?|"
    r"(?:authorization|api[_ -]?key|password|secret|private[_ -]?key|token)\s*(?:[:=]|\s+))"
)
POSIX_PATH_TEXT = re.compile(r"(?<![A-Za-z0-9])/(?:[^\s/]+/)+[^\s]*")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")

_REGISTRY_RESOURCES = {
    "graph-surface-registry": Path("registry") / "graph-surface-registry.json",
    "graph-edge-registry": Path("registry") / "graph-edge-registry.json",
    "schema-registry": Path("registry") / "schema-registry.json",
    "mcp-surface-contract": Path("registry") / "mcp-surface-contract.json",
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
    def __init__(self, code: int, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.error_code = error_code or {
            -32601: "method_or_tool_not_found",
            -32602: "invalid_request",
            -32603: "resource_or_server_error",
            -32010: "dependency_map_stale",
        }.get(code, "mcp_error")


def _validate_id(value: str, label: str) -> str:
    if not value or "/" in value or "\\" in value or ".." in value or not ID_PATTERN.match(value):
        raise MCPError(-32602, f"Invalid {label}")
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
            and not SENSITIVE_RESPONSE_KEY.search(key)
        }
    if isinstance(value, list):
        return [_strip_forbidden_fields(child) for child in value]
    if isinstance(value, str):
        sanitized = LOCAL_PATH_TEXT.sub("<local-path-redacted>", value)
        if sanitized.startswith(("/", "file://")):
            return "<local-path-redacted>"
        return sanitized
    return value


def _sanitize_resource_text(mime_type: str, text: str) -> str:
    if mime_type == "application/json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPError(-32603, "JSON resource is invalid") from exc
        return json_dumps(_strip_forbidden_fields(payload), pretty=True)
    return LOCAL_PATH_TEXT.sub("<local-path-redacted>", text)


def _sanitize_error_message(message: str) -> str:
    sanitized = str(_strip_forbidden_fields(message))
    sanitized = SENSITIVE_ERROR_TEXT.sub("<credential-redacted>", sanitized)
    return sanitized[:200] if sanitized else "MCP request failed"


def _prompt_argument(value: Any, name: str, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise MCPError(-32602, f"{name} must be a string")
    text = value.strip()
    if required and not text:
        raise MCPError(-32602, f"{name} is required")
    if len(text) > 240:
        raise MCPError(-32602, f"{name} is too long")
    if (
        LOCAL_PATH_TEXT.search(text)
        or POSIX_PATH_TEXT.search(text)
        or text.casefold().startswith("file://")
        or PROMPT_SENSITIVE_TEXT.search(text)
    ):
        raise MCPError(-32602, f"{name} contains disallowed private or credential-like content")
    return text


def _surface_by_id(hub_root: Path, surface_id: str) -> dict[str, Any]:
    _validate_id(surface_id, "surface_id")
    registry = load_graph_surface_registry(hub_root)
    for surface in registry.get("surfaces", []):
        if surface.get("surface_id") == surface_id:
            return surface
    raise MCPError(-32602, "Unknown graph surface")


def _surface_paths(hub_root: Path, surface: dict[str, Any]) -> tuple[Path, Path]:
    outputs = surface.get("outputs", {})
    try:
        manifest = resolve_graph_surface_path(hub_root, str(outputs["manifest_logical_path"]))
        body = resolve_graph_surface_path(hub_root, str(outputs["body_logical_path"]))
    except (KeyError, ValueError) as exc:
        raise MCPError(-32603, "Invalid graph surface registry output") from exc
    return manifest, body


def _load_surface_graph(hub_root: Path, surface_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    surface = _surface_by_id(hub_root, surface_id)
    _manifest_path, body_path = _surface_paths(hub_root, surface)
    if not body_path.exists():
        raise MCPError(-32602, "Graph surface body is missing")
    try:
        graph = json.loads(body_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MCPError(-32603, "Graph surface body is unreadable") from exc
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
    raise MCPError(-32602, "Unknown node on graph surface")


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


def _read_resource_payload(
    hub_root: Path, uri: str, *, approved_private_partitions: frozenset[str]
) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "dad" or parsed.params or parsed.query or parsed.fragment:
        raise MCPError(-32602, "Unsupported resource URI")
    kind = parsed.netloc
    parts = [part for part in parsed.path.split("/") if part]
    if any(part in {".", ".."} or "\\" in part for part in parts):
        raise MCPError(-32602, "Invalid resource URI")

    if kind == "registry" and len(parts) == 1:
        registry_id = _validate_id(parts[0], "registry_id")
        path = _REGISTRY_RESOURCES.get(registry_id)
        if path is None:
            raise MCPError(-32602, "Unknown registry resource")
        return "application/json", (hub_root / path).read_text(encoding="utf-8")

    if kind == "plans":
        if not approved_private_partitions:
            raise MCPError(-32600, "Private plan resource access is not approved for this MCP host")
        events = read_intent_events(hub_root)
        index = fold_plan_index(events)
        if parts == ["search"]:
            filtered = [
                row for row in index["plans"]
                if row.get("privacy_class") in approved_private_partitions
            ]
            return "application/json", json_dumps(
                {**index, "plans": filtered, "plan_count": len(filtered)}, pretty=True
            )
        if len(parts) in {1, 2}:
            plan_id = _validate_id(parts[0], "plan_id")
            indexed = next((row for row in index["plans"] if row["plan_id"] == plan_id), None)
            if indexed is None or indexed.get("privacy_class") not in approved_private_partitions:
                raise MCPError(-32602, "Unknown plan resource")
            if len(parts) == 2 and parts[1] == "lineage":
                lineage = [row for row in events if row.get("plan_id") == plan_id]
                if not lineage:
                    raise MCPError(-32602, "Unknown plan resource")
                return "application/json", json_dumps(
                    {
                        "schema_version": "dad.mcp.plan_lineage.v1",
                        "plan_id": plan_id,
                        "events": lineage,
                        "execution_authorized": False,
                    },
                    pretty=True,
                )
            if len(parts) == 1:
                try:
                    plan = load_plan_revision(hub_root, plan_id)
                except (KeyError, OSError, RuntimeError) as exc:
                    raise MCPError(-32602, "Unknown plan resource") from exc
                plan.pop("plan_markdown", None)
                return "application/json", json_dumps(plan, pretty=True)

    if kind == "identity" and len(parts) in {1, 2}:
        if not approved_private_partitions:
            raise MCPError(-32600, "Private identity resource access is not approved for this MCP host")
        entity_id = _validate_id(parts[0], "entity_id")
        state = fold_entity_state(read_entity_events(hub_root))
        entity = next((row for row in state["entities"] if row["entity_id"] == entity_id), None)
        if (
            entity is None
            or entity.get("semantic_card", {}).get("privacy_partition")
            not in approved_private_partitions
        ):
            raise MCPError(-32602, "Unknown identity resource")
        graph = build_entity_graph(state)
        if len(parts) == 1:
            return "application/json", json_dumps(entity, pretty=True)
        if parts[1] == "neighbors":
            edges = [row for row in graph["edges"] if entity_id in {row["source"], row["target"]}]
            return "application/json", json_dumps({"entity_id": entity_id, "edges": edges, "execution_authorized": False}, pretty=True)
        if parts[1] == "blast-radius":
            return "application/json", json_dumps({"entity_id": entity_id, "reverse_dependencies": reverse_blast_radius(graph, entity_id), "execution_authorized": False}, pretty=True)

    if kind == "recovery" and parts == ["candidates"]:
        if not approved_private_partitions:
            raise MCPError(-32600, "Private recovery access is not approved for this MCP host")
        index = fold_plan_index(read_intent_events(hub_root))
        filtered = [row for row in index["plans"] if row.get("privacy_class") in approved_private_partitions]
        return "application/json", json_dumps(build_weekly_digest({**index, "plans": filtered, "plan_count": len(filtered)}), pretty=True)

    if kind == "report" and parts == ["unfinished-intent"]:
        if not approved_private_partitions:
            raise MCPError(-32600, "Private recovery access is not approved for this MCP host")
        index = fold_plan_index(read_intent_events(hub_root))
        filtered = [row for row in index["plans"] if row.get("privacy_class") in approved_private_partitions]
        return "application/json", json_dumps(build_weekly_digest({**index, "plans": filtered, "plan_count": len(filtered)}), pretty=True)

    if kind == "surface" and len(parts) == 2 and parts[1] == "manifest":
        surface = _surface_by_id(hub_root, parts[0])
        manifest_path, _body_path = _surface_paths(hub_root, surface)
        if not manifest_path.exists():
            raise MCPError(-32602, "Surface manifest is missing")
        return "application/json", manifest_path.read_text(encoding="utf-8")

    if kind == "report" and len(parts) == 1:
        report_id = _validate_id(parts[0], "report_id")
        if report_id not in _REPORT_RESOURCES:
            raise MCPError(-32602, "Unknown report resource")
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
            raise MCPError(-32602, "Unknown kernel resource")
        return "text/markdown", (hub_root / path).read_text(encoding="utf-8")

    if kind == "packet" and len(parts) == 1:
        packet_id = _validate_id(parts[0], "packet_id")
        path = _PACKET_RESOURCES.get(packet_id)
        if path is None:
            raise MCPError(-32602, "Unknown packet resource")
        return "text/markdown", (hub_root / path).read_text(encoding="utf-8")

    if kind == "mcp" and len(parts) == 1:
        if parts[0] == "dependency-map":
            return "application/json", (hub_root / MAP_PATH).read_text(encoding="utf-8")
        if parts[0] == "installed-host-status":
            evidence = json.loads((hub_root / HOST_EVIDENCE_PATH).read_text(encoding="utf-8"))
            status = validate_mcp_dependency_map(hub_root)
            payload = {
                "schema_version": "dad.mcp.installed_host_status.v1",
                "observation_state": (
                    "current" if status["installed_host_claims_allowed"] else "stale"
                ),
                "installed_or_active_claims_allowed": status[
                    "installed_host_claims_allowed"
                ],
                "issue_codes": status["scoped_host_issue_codes"],
                "evidence": evidence,
                "authority": "metadata_only_no_activation_inference",
            }
            return "application/json", json_dumps(payload, pretty=True)

    raise MCPError(-32602, "Unsupported resource URI")


class DADGraphMCPServer:
    def __init__(
        self, hub_root: Path, *, approved_private_partitions: tuple[str, ...] = ()
    ) -> None:
        self.hub_root = hub_root.resolve()
        self.approved_private_partitions = frozenset(approved_private_partitions)
        self._packet_requests: dict[str, str] = {}

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
            [
                {"uri": "dad://plans/search", "name": "Private plan index", "mimeType": "application/json"},
                {"uri": "dad://recovery/candidates", "name": "Unfinished plan recovery candidates", "mimeType": "application/json"},
                {"uri": "dad://report/unfinished-intent", "name": "Unfinished intent digest", "mimeType": "application/json"},
            ]
        )
        try:
            plan_index = fold_plan_index(read_intent_events(self.hub_root))
            for row in plan_index["plans"]:
                if row.get("privacy_class") not in self.approved_private_partitions:
                    continue
                resources.extend(
                    [
                        {"uri": f"dad://plans/{row['plan_id']}", "name": f"Plan {row['plan_id']}", "mimeType": "application/json"},
                        {"uri": f"dad://plans/{row['plan_id']}/lineage", "name": f"Plan lineage {row['plan_id']}", "mimeType": "application/json"},
                    ]
                )
            entity_state = fold_entity_state(read_entity_events(self.hub_root))
            for row in entity_state["entities"]:
                entity_id = row["entity_id"]
                if (
                    row.get("semantic_card", {}).get("privacy_partition")
                    not in self.approved_private_partitions
                ):
                    continue
                resources.extend(
                    [
                        {"uri": f"dad://identity/{entity_id}", "name": f"Identity {entity_id}", "mimeType": "application/json"},
                        {"uri": f"dad://identity/{entity_id}/neighbors", "name": f"Identity neighbors {entity_id}", "mimeType": "application/json"},
                        {"uri": f"dad://identity/{entity_id}/blast-radius", "name": f"Identity blast radius {entity_id}", "mimeType": "application/json"},
                    ]
                )
        except (OSError, RuntimeError, ValueError):
            pass
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
        resources.extend(
            [
                {
                    "uri": "dad://mcp/dependency-map",
                    "name": "MCP dependency and blast-radius map",
                    "mimeType": "application/json",
                },
                {
                    "uri": "dad://mcp/dependency-status",
                    "name": "MCP dependency freshness status",
                    "mimeType": "application/json",
                },
                {
                    "uri": "dad://mcp/dependency-refresh-candidate",
                    "name": "MCP review-only fingerprint refresh candidate",
                    "mimeType": "application/json",
                },
                {
                    "uri": "dad://mcp/installed-host-status",
                    "name": "MCP privacy-safe installed-host evidence",
                    "mimeType": "application/json",
                },
            ]
        )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "dad://mcp/dependency-status":
            mime_type = "application/json"
            text = json_dumps(self._dependency_status(), pretty=True)
        elif uri == "dad://mcp/dependency-refresh-candidate":
            mime_type = "application/json"
            text = json_dumps(build_mcp_dependency_refresh_candidate(self.hub_root), pretty=True)
        else:
            mime_type, text = _read_resource_payload(
                self.hub_root,
                uri,
                approved_private_partitions=self.approved_private_partitions,
            )
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": mime_type,
                    "text": _sanitize_resource_text(mime_type, text),
                }
            ]
        }

    def _dependency_status(self) -> dict[str, Any]:
        return validate_mcp_dependency_map(
            self.hub_root,
            runtime_tools=[row["name"] for row in self.list_tools()],
            runtime_resources=[row["uri"] for row in self.list_resources()],
        )

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
            {
                "name": "dad_mcp_dependency_status",
                "description": "Read categorical MCP dependency-map freshness and coverage status.",
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
            },
            {
                "name": "dad_mcp_dependency_impact",
                "description": "Read deterministic downstream change effects; refuses claims while the map is stale.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["node_id"],
                    "properties": {
                        "node_id": {"type": "string", "pattern": "^mcp\\.[a-z][a-z0-9_.-]*$"},
                        "max_depth": {"type": "integer", "minimum": 1, "maximum": 16},
                    },
                },
            },
            {
                "name": "dad_mcp_dependency_refresh_candidate",
                "description": "Calculate review-only dependency fingerprint candidates without writing or authorizing changes.",
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
            },
            {
                "name": "dad_lifecycle_packet_prepare",
                "description": "Prepare a non-authorizing lifecycle action packet; no action is executed.",
                "inputSchema": {
                    "type": "object", "additionalProperties": False,
                    "required": ["request_id", "action_kind", "repository_id", "source_snapshot_digest", "expected_preconditions_digest", "approval_ref"],
                    "properties": {
                        "request_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "action_kind": {"enum": ["preflight", "midflight", "postflight", "dependency_refresh"]},
                        "repository_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "case_id": {"type": "string", "maxLength": 160},
                        "source_snapshot_digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                        "expected_preconditions_digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                        "approval_ref": {"type": "string", "minLength": 1, "maxLength": 160},
                        "rollback_ref": {"type": "string", "maxLength": 160},
                        "expires_hours": {"type": "integer", "minimum": 1, "maximum": 168},
                    },
                },
            },
            {
                "name": "dad_recovery_packet_prepare",
                "description": "Prepare one digest-bound recovery packet from current approved shaping evidence.",
                "inputSchema": {
                    "type": "object", "additionalProperties": False,
                    "required": ["decision_id"],
                    "properties": {
                        "decision_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "expires_hours": {"type": "integer", "minimum": 1, "maximum": 168},
                    },
                },
            },
            {
                "name": "dad_lifecycle_result_record",
                "description": "Record a checked result for one exact packet; never executes the packet.",
                "inputSchema": {
                    "type": "object", "additionalProperties": False,
                    "required": ["packet", "result_status", "before_snapshot_digest", "after_snapshot_digest", "worker_id", "checker_id", "evidence_refs"],
                    "properties": {
                        "packet": {"type": "object"},
                        "result_status": {"enum": ["verified", "failed", "aborted"]},
                        "before_snapshot_digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                        "after_snapshot_digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                        "worker_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "checker_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "evidence_refs": {"type": "array", "minItems": 1, "maxItems": 32, "items": {"type": "string", "maxLength": 160}},
                    },
                },
            },
            {
                "name": "dad_recovery_result_record",
                "description": "Record one independently checked recovery result for an exact packet.",
                "inputSchema": {
                    "type": "object", "additionalProperties": False,
                    "required": ["packet", "result_status", "before_snapshot_digest", "after_snapshot_digest", "worker_id", "checker_id", "evidence_refs", "command_id"],
                    "properties": {
                        "packet": {"type": "object"},
                        "result_status": {"enum": ["verified", "failed", "aborted"]},
                        "before_snapshot_digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                        "after_snapshot_digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                        "worker_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "checker_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "evidence_refs": {"type": "array", "minItems": 1, "maxItems": 32, "items": {"type": "string", "maxLength": 160}},
                        "command_id": {"type": "string", "minLength": 1, "maxLength": 160},
                    },
                },
            },
        ]

    def list_prompts(self) -> list[dict[str, Any]]:
        """Return provider-neutral, read-only workflow prompt templates."""
        return [
            {
                "name": "dad_preflight_briefing",
                "description": (
                    "Prepare a bounded DAD preflight briefing; local repository authority "
                    "and human gates remain in force."
                ),
                "arguments": [
                    {"name": "task", "description": "Short task description.", "required": True},
                    {"name": "agent", "description": "Non-empty runtime-neutral agent identifier.", "required": True},
                ],
            },
            {
                "name": "dad_review_lane_checklist",
                "description": "Prepare an independent review checklist for a proposed DAD change.",
                "arguments": [
                    {"name": "change", "description": "Short change description.", "required": True},
                ],
            },
            {
                "name": "dad_postflight_draft",
                "description": "Draft a privacy-safe DAD postflight record without recording it.",
                "arguments": [
                    {"name": "summary", "description": "Short outcome summary.", "required": True},
                    {"name": "tests", "description": "Tests or checks that were run.", "required": False},
                ],
            },
        ]

    def get_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Render a generic prompt; never executes a command or mutates DAD."""
        arguments = arguments or {}
        if name == "dad_preflight_briefing":
            if set(arguments) != {"task", "agent"}:
                raise MCPError(-32602, "Unexpected preflight prompt argument")
            task = _prompt_argument(arguments.get("task"), "task")
            agent = _prompt_argument(arguments.get("agent"), "agent")
            return {
                "description": "Read-only DAD preflight briefing",
                "messages": [{"role": "user", "content": {"type": "text", "text": (
                    f"Prepare a DAD preflight briefing for agent {agent!r} and task {task!r}. "
                    "Inspect local source authority, relevant manifests and registries, "
                    "privacy boundaries, validation commands, review lanes, and stop conditions. "
                    "Do not mutate files, register MCP, execute tools, or treat recommendations as authority."
                )}}],
            }
        if name == "dad_review_lane_checklist":
            if set(arguments) != {"change"}:
                raise MCPError(-32602, "Unexpected review prompt argument")
            change = _prompt_argument(arguments.get("change"), "change")
            return {
                "description": "Independent DAD review-lane checklist",
                "messages": [{"role": "user", "content": {"type": "text", "text": (
                    f"Independently review the proposed change {change!r}. Check correctness, "
                    "scope discipline, source authority, privacy leakage, portability, deterministic "
                    "tests, dependency freshness, and rollback. Report evidence and unknowns; "
                    "do not approve execution or merge."
                )}}],
            }
        if name == "dad_postflight_draft":
            if set(arguments) - {"summary", "tests"} or "summary" not in arguments:
                raise MCPError(-32602, "Unexpected postflight prompt argument")
            summary = _prompt_argument(arguments.get("summary"), "summary")
            tests = _prompt_argument(arguments.get("tests"), "tests", required=False) or "not supplied"
            return {
                "description": "Privacy-safe DAD postflight draft",
                "messages": [{"role": "user", "content": {"type": "text", "text": (
                    f"Draft a DAD postflight for outcome {summary!r}. Tests/checks: {tests!r}. "
                    "Include files changed, exact validation evidence, findings, assumptions, "
                    "unknowns, reusable lessons, review-lane status, and remaining risks. "
                    "Exclude secrets, raw conversations, private payloads, absolute paths, and commands. "
                    "This is a draft only; do not record or publish it."
                )}}],
            }
        raise MCPError(-32601, "Unknown prompt")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = arguments or {}
        if name in {
            "dad_mcp_dependency_status",
            "dad_mcp_dependency_refresh_candidate",
        } and arguments:
            raise MCPError(-32602, "This tool accepts no arguments")
        if name == "dad_mcp_dependency_impact" and not set(arguments).issubset(
            {"node_id", "max_depth"}
        ):
            raise MCPError(-32602, "Unexpected dependency impact argument")
        if name == "dad_lifecycle_packet_prepare":
            allowed = {"request_id", "action_kind", "repository_id", "case_id", "source_snapshot_digest", "expected_preconditions_digest", "approval_ref", "rollback_ref", "expires_hours"}
            if not set(arguments).issubset(allowed):
                raise MCPError(-32602, "Unexpected lifecycle packet argument")
            packet = prepare_lifecycle_packet(**arguments)
            request_id = str(arguments["request_id"])
            body = json_dumps({key: value for key, value in packet.items() if key != "packet_id"})
            prior = self._packet_requests.get(request_id)
            if prior is not None and prior != body:
                raise MCPError(-32602, "request_id was reused with conflicting packet data")
            self._packet_requests[request_id] = body
            return {"content": [{"type": "text", "text": json_dumps(packet, pretty=True)}], "structuredContent": packet}
        if name == "dad_recovery_packet_prepare":
            if not set(arguments).issubset({"decision_id", "expires_hours"}):
                raise MCPError(-32602, "Unexpected recovery packet argument")
            try:
                from .cli import _cfg, _rebuild_current_recovery_shaping
                from .portfolio_recovery import build_recovery_packet
                cfg = _cfg(hub=self.hub_root)
                _state, _cockpit, _reconciliation, shaping, _decisions = _rebuild_current_recovery_shaping(cfg)
                now = datetime.now(timezone.utc)
                packet = build_recovery_packet(
                    cfg.repo_root,
                    shaping,
                    str(arguments["decision_id"]),
                    now=now,
                    expires_at=now + timedelta(hours=int(arguments.get("expires_hours", 24))),
                )
            except (OSError, ValueError, RuntimeError) as exc:
                raise MCPError(-32602, "Recovery packet is unavailable") from exc
            return {"content": [{"type": "text", "text": json_dumps(packet, pretty=True)}], "structuredContent": _strip_forbidden_fields(packet)}
        if name == "dad_lifecycle_result_record":
            if not set(arguments).issubset({"packet", "result_status", "before_snapshot_digest", "after_snapshot_digest", "worker_id", "checker_id", "evidence_refs"}):
                raise MCPError(-32602, "Unexpected lifecycle result argument")
            try:
                payload = record_lifecycle_result(self.hub_root, arguments["packet"], result_status=str(arguments["result_status"]), before_snapshot_digest=str(arguments["before_snapshot_digest"]), after_snapshot_digest=str(arguments["after_snapshot_digest"]), worker_id=str(arguments["worker_id"]), checker_id=str(arguments["checker_id"]), evidence_refs=arguments["evidence_refs"])
            except (MCPPacketError, OSError, ValueError) as exc:
                raise MCPError(-32602, "Lifecycle result was rejected") from exc
            return {"content": [{"type": "text", "text": json_dumps(payload, pretty=True)}], "structuredContent": payload}
        if name == "dad_recovery_result_record":
            allowed = {"packet", "result_status", "before_snapshot_digest", "after_snapshot_digest", "worker_id", "checker_id", "evidence_refs", "command_id"}
            if not set(arguments).issubset(allowed):
                raise MCPError(-32602, "Unexpected recovery result argument")
            try:
                from .cli import _cfg, _rebuild_current_recovery_shaping
                from .portfolio_recovery import record_recovery_result
                cfg = _cfg(hub=self.hub_root)
                _state, _cockpit, _reconciliation, shaping, _decisions = _rebuild_current_recovery_shaping(cfg)
                payload = record_recovery_result(cfg.repo_root, shaping, arguments["packet"], result_status=str(arguments["result_status"]), before_snapshot_digest=str(arguments["before_snapshot_digest"]), after_snapshot_digest=str(arguments["after_snapshot_digest"]), worker_id=str(arguments["worker_id"]), checker_id=str(arguments["checker_id"]), evidence_refs=arguments["evidence_refs"], command_id=str(arguments["command_id"]))
            except (OSError, ValueError, RuntimeError) as exc:
                raise MCPError(-32602, "Recovery result was rejected") from exc
            return {"content": [{"type": "text", "text": json_dumps(payload, pretty=True)}], "structuredContent": _strip_forbidden_fields(payload)}
        if name == "dad_graph_surface_status":
            payload = graph_surface_status(self.hub_root)
        elif name == "dad_graph_get_node":
            payload = dad_graph_get_node(self.hub_root, **arguments)
        elif name == "dad_graph_neighbors":
            payload = dad_graph_neighbors(self.hub_root, **arguments)
        elif name == "dad_graph_search_nodes":
            payload = dad_graph_search_nodes(self.hub_root, **arguments)
        elif name == "dad_mcp_dependency_status":
            payload = self._dependency_status()
        elif name == "dad_mcp_dependency_impact":
            status = self._dependency_status()
            if not status["structural_claims_allowed"]:
                raise MCPError(-32010, "MCP dependency map is stale; current impact claims refused")
            try:
                payload = mcp_dependency_impact(self.hub_root, **arguments)
            except MCPDependencyMapError as exc:
                if str(exc) == "dependency_map_stale":
                    raise MCPError(
                        -32010,
                        "MCP dependency evidence is stale for the requested claim",
                    ) from exc
                raise MCPError(-32602, "Invalid dependency impact request") from exc
        elif name == "dad_mcp_dependency_refresh_candidate":
            payload = build_mcp_dependency_refresh_candidate(self.hub_root)
        else:
            raise MCPError(-32601, "Unknown tool")
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
                    "capabilities": {"resources": {}, "tools": {}, "prompts": {}},
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
            elif method == "prompts/list":
                result = {"prompts": self.list_prompts()}
            elif method == "prompts/get":
                result = self.get_prompt(
                    str(params.get("name", "")),
                    params.get("arguments") if isinstance(params.get("arguments"), dict) else {},
                )
            elif method == "tools/call":
                result = self.call_tool(
                    str(params.get("name", "")),
                    params.get("arguments") if isinstance(params.get("arguments"), dict) else {},
                )
            else:
                raise MCPError(-32601, "Method not found")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except MCPError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": exc.code,
                    "message": _sanitize_error_message(exc.message),
                    "data": {"error_code": exc.error_code},
                },
            }
        except Exception:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Internal MCP error",
                    "data": {"error_code": "internal_error"},
                },
            }


def run_stdio_server(hub_root: Path) -> None:
    server = DADGraphMCPServer(hub_root)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Invalid JSON request",
                    "data": {"error_code": "parse_error"},
                },
            }
        else:
            response = server.handle_request(request)
        if response is not None:
            sys.stdout.write(json_dumps(response) + "\n")
            sys.stdout.flush()
