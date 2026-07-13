"""Deterministic freshness and blast-radius checks for DAD's local MCP server.

The dependency map is review-owned repository metadata.  This module may
calculate fingerprints and impact candidates, but it never rewrites the map,
host configuration, source files, or authority records.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import tomllib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema.validators import validator_for


MAP_PATH = Path("registry/mcp-dependency-map.json")
MAP_SCHEMA_PATH = Path("schemas/mcp-dependency-map.schema.json")
HOST_CONTRACT_PATH = Path("assets/mcp/dad-local-readonly/contract.json")
HOST_CONTRACT_SCHEMA_PATH = Path("assets/mcp/dad-local-readonly/contract.schema.json")
HOST_EVIDENCE_PATH = Path("assets/mcp/dad-local-readonly/installed-host-evidence.json")
HOST_EVIDENCE_SCHEMA_PATH = Path(
    "assets/mcp/dad-local-readonly/installed-host-evidence.schema.json"
)
REQUIRED_CATEGORIES = {
    "identity",
    "protocol",
    "entrypoint",
    "implementation",
    "backend",
    "runtime_data",
    "schema",
    "registry",
    "governance",
    "host_adapter",
    "packaging",
    "navigation",
    "validation",
    "security_authority",
}
_ID = re.compile(r"^mcp\.[a-z][a-z0-9_.-]*$")
_ABSOLUTE_WINDOWS = re.compile(r"(?:^|[^A-Za-z0-9])[A-Za-z]:[\\/]")
_SENSITIVE = re.compile(
    r"(?:authorization|api[_-]?key|password|secret|private[_-]?key|token)",
    re.IGNORECASE,
)
_FLOW_PHASE = {"source": 0, "transform": 1, "sink": 2}
# These reviewed digests bind direction, not content fingerprints. A legitimate
# graph/flow direction change therefore requires an explicit code-and-map review.
_EXPECTED_EDGE_DIRECTION = "sha256:14ebd821cdb1706168f951e3588edc70e6f3331391aede6233b292ff2696ec38"
_EXPECTED_FLOW_DIRECTION = "sha256:d00ba08f2e41ce68bd679a8cf91ef766cdd5579795d8494dc72ea07f20891f2f"


class MCPDependencyMapError(ValueError):
    """Raised when the dependency map cannot support a current claim."""


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise MCPDependencyMapError("invalid_json_pointer")
    current = value
    for raw in pointer[1:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, Mapping):
            current = current[part]
        else:
            raise MCPDependencyMapError("json_pointer_not_found")
    return current


def _python_symbol(path: Path, symbol: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                return ast.dump(node, annotate_fields=True, include_attributes=False)
    raise MCPDependencyMapError("python_symbol_not_found")


def _python_symbols(path: Path, symbols: Iterable[str]) -> list[Any]:
    return [_python_symbol(path, symbol) for symbol in sorted(symbols)]


def _tree_payload(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for child in sorted(path.rglob("*")):
        if not child.is_file() or "__pycache__" in child.parts or child.suffix == ".pyc":
            continue
        rows.append((child.relative_to(path).as_posix(), _sha256(child.read_bytes())))
    return rows


def compute_fingerprint(repo_root: Path, spec: Mapping[str, Any]) -> str:
    """Compute one declared exact or semantic fingerprint."""

    relative = str(spec.get("path", ""))
    if not relative or "\\" in relative or relative.startswith(("/", "~")):
        raise MCPDependencyMapError("unsafe_fingerprint_path")
    path = repo_root / relative
    kind = str(spec.get("kind", ""))
    if kind == "exact_sha256":
        return _sha256(path.read_bytes())
    if kind == "tree_sha256":
        return _sha256(_canonical(_tree_payload(path)))
    if kind == "json_pointer_sha256":
        return _sha256(_canonical(_json_pointer(_load_json(path), str(spec.get("pointer", "")))))
    if kind == "python_symbol_sha256":
        return _sha256(_canonical(_python_symbol(path, str(spec.get("symbol", "")))))
    if kind == "python_symbols_sha256":
        return _sha256(_canonical(_python_symbols(path, spec.get("symbols", []))))
    if kind == "toml_pointer_sha256":
        value = _json_pointer(
            tomllib.loads(path.read_text(encoding="utf-8")), str(spec.get("pointer", ""))
        )
        return _sha256(_canonical(value))
    if kind == "text_line_sha256":
        needle = str(spec.get("contains", ""))
        matches = [
            line.strip() for line in path.read_text(encoding="utf-8").splitlines() if needle in line
        ]
        if len(matches) != 1:
            raise MCPDependencyMapError("text_selector_not_unique")
        return _sha256(_canonical(matches[0]))
    if kind == "text_lines_sha256":
        lines = path.read_text(encoding="utf-8").splitlines()
        selected: list[str] = []
        for needle in spec.get("contains", []):
            matches = [line.strip() for line in lines if str(needle) in line]
            if len(matches) != 1:
                raise MCPDependencyMapError("text_selector_not_unique")
            selected.append(matches[0])
        return _sha256(_canonical(selected))
    raise MCPDependencyMapError("unsupported_fingerprint_kind")


def load_mcp_dependency_map(repo_root: Path) -> dict[str, Any]:
    value = _load_json(repo_root / MAP_PATH)
    if not isinstance(value, dict):
        raise MCPDependencyMapError("map_not_object")
    return value


def _schema_errors(repo_root: Path, dependency_map: Mapping[str, Any]) -> list[str]:
    try:
        schema = _load_json(repo_root / MAP_SCHEMA_PATH)
        cls = validator_for(schema)
        cls.check_schema(schema)
        cls(schema).validate(dependency_map)
    except Exception:
        return ["schema_invalid"]
    return []


def _structure_errors(dependency_map: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = dependency_map.get("nodes", [])
    edges = dependency_map.get("edges", [])
    node_ids = [str(row.get("node_id", "")) for row in nodes if isinstance(row, Mapping)]
    edge_ids = [str(row.get("edge_id", "")) for row in edges if isinstance(row, Mapping)]
    if len(node_ids) != len(set(node_ids)) or any(not _ID.fullmatch(item) for item in node_ids):
        errors.append("node_identity_invalid")
    if len(edge_ids) != len(set(edge_ids)) or any(not _ID.fullmatch(item) for item in edge_ids):
        errors.append("edge_identity_invalid")
    categories = {str(row.get("category", "")) for row in nodes if isinstance(row, Mapping)}
    if (
        categories != REQUIRED_CATEGORIES
        or set(dependency_map.get("required_categories", [])) != REQUIRED_CATEGORIES
    ):
        errors.append("category_coverage_invalid")
    known = set(node_ids)
    degree = {item: 0 for item in known}
    graph: dict[str, set[str]] = {item: set() for item in known}
    for edge in edges:
        if not isinstance(edge, Mapping):
            errors.append("edge_invalid")
            continue
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if source not in known or target not in known or source == target:
            errors.append("edge_endpoint_invalid")
            continue
        degree[source] += 1
        degree[target] += 1
        graph[source].add(target)
        if not edge.get("edge_type") or not edge.get("change_effect"):
            errors.append("edge_type_missing")
    if any(value == 0 for value in degree.values()):
        errors.append("orphan_node")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        if any(visit(child) for child in graph[node_id]):
            return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    if any(visit(node_id) for node_id in sorted(known)):
        errors.append("unsafe_cycle")

    edge_direction = sorted(
        (
            str(edge.get("edge_id", "")),
            str(edge.get("source", "")),
            str(edge.get("target", "")),
            str(edge.get("edge_type", "")),
            str(edge.get("change_effect", "")),
        )
        for edge in edges
        if isinstance(edge, Mapping)
    )
    if _sha256(_canonical(edge_direction)) != _EXPECTED_EDGE_DIRECTION:
        errors.append("edge_direction_contract_stale")

    for flow in dependency_map.get("data_flows", []):
        steps = flow.get("steps", []) if isinstance(flow, Mapping) else []
        phases = [_FLOW_PHASE.get(str(step.get("phase", "")), -1) for step in steps]
        if not steps or phases != sorted(phases) or phases[0] != 0 or phases[-1] != 2:
            errors.append("data_flow_direction_invalid")
        if any(str(step.get("node_id", "")) not in known for step in steps):
            errors.append("data_flow_node_missing")
    flow_direction = sorted(
        (
            str(flow.get("flow_id", "")),
            tuple(
                (
                    str(step.get("phase", "")),
                    str(step.get("node_id", "")),
                    str(step.get("data_class", "")),
                )
                for step in flow.get("steps", [])
            ),
        )
        for flow in dependency_map.get("data_flows", [])
        if isinstance(flow, Mapping)
    )
    if _sha256(_canonical(flow_direction)) != _EXPECTED_FLOW_DIRECTION:
        errors.append("data_flow_direction_contract_stale")

    authority = dependency_map.get("authority_policy", {})
    expected_authority = {
        "local_only": True,
        "read_only": True,
        "remote_enabled": False,
        "execution_authority": False,
        "self_authorizing_refresh": False,
        "host_configuration_write": False,
    }
    if authority != expected_authority:
        errors.append("authority_direction_invalid")
    return sorted(set(errors))


def _privacy_errors(value: Any) -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _SENSITIVE.search(str(key)):
                errors.append("sensitive_field_prohibited")
            errors.extend(_privacy_errors(child))
    elif isinstance(value, list):
        for child in value:
            errors.extend(_privacy_errors(child))
    elif isinstance(value, str):
        lowered = value.casefold()
        if (
            _ABSOLUTE_WINDOWS.search(value)
            or value.startswith(("\\\\", "file://"))
            or "/users/" in lowered
            or "/home/" in lowered
        ):
            errors.append("absolute_path_prohibited")
    return errors


def _local_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            imports.add(str(node.module or ""))
    return imports


def _function_node(path: Path, function: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function:
            return node
    raise MCPDependencyMapError("python_function_not_found")


def _mcp_cli_route_name(decorator: ast.expr, function_name: str) -> str | None:
    if not (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and isinstance(decorator.func.value, ast.Name)
        and decorator.func.value.id == "mcp_app"
        and decorator.func.attr == "command"
    ):
        return None

    name_keywords = [row for row in decorator.keywords if row.arg == "name"]
    if (
        len(decorator.args) > 1
        or len(name_keywords) > 1
        or (decorator.args and name_keywords)
        or any(row.arg is None for row in decorator.keywords)
    ):
        raise MCPDependencyMapError("mcp_cli_route_name_ambiguous")

    if decorator.args:
        name_node = decorator.args[0]
    elif name_keywords:
        name_node = name_keywords[0].value
    else:
        return function_name.lower().replace("_", "-")

    if (
        not isinstance(name_node, ast.Constant)
        or not isinstance(name_node.value, str)
        or not name_node.value
    ):
        raise MCPDependencyMapError("mcp_cli_route_name_ambiguous")
    return name_node.value


def _mcp_cli_routes(path: Path) -> dict[str, dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    routes: dict[str, dict[str, Any]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        command_names: list[str] = []
        for decorator in node.decorator_list:
            command_name = _mcp_cli_route_name(decorator, node.name)
            if command_name is not None:
                command_names.append(command_name)
        if not command_names:
            continue
        if len(command_names) != 1:
            raise MCPDependencyMapError("mcp_cli_route_name_ambiguous")
        command_name = command_names[0]
        if command_name in routes:
            raise MCPDependencyMapError("mcp_cli_route_duplicate")
        imports = {
            str(child.module or "")
            for child in ast.walk(node)
            if isinstance(child, ast.ImportFrom) and child.level
        }
        calls = {
            child.func.id
            for child in ast.walk(node)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }
        routes[command_name] = {
            "function": node.name,
            "imports": imports,
            "calls": calls,
        }
    return routes


def _coverage_errors(repo_root: Path, dependency_map: Mapping[str, Any]) -> list[str]:
    coverage = dependency_map.get("coverage", {})
    errors: list[str] = []
    for row in coverage.get("python_local_imports", []):
        try:
            observed = _local_imports(repo_root / str(row["path"]))
            declared = {str(item) for item in row["modules"]}
        except Exception:
            errors.append("python_import_inventory_unreadable")
            continue
        if observed != declared:
            errors.append("python_import_inventory_stale")

    cli = coverage.get("cli_entrypoint", {})
    observed_routes: dict[str, dict[str, Any]] | None = None
    try:
        observed_routes = _mcp_cli_routes(repo_root / str(cli["path"]))
        entrypoint = observed_routes.get(str(cli.get("command", "")), {})
        if entrypoint.get("function") != cli.get("function"):
            errors.append("cli_entrypoint_stale")
    except MCPDependencyMapError as exc:
        code = str(exc)
        errors.append(
            code
            if code in {"mcp_cli_route_duplicate", "mcp_cli_route_name_ambiguous"}
            else "mcp_cli_route_inventory_unreadable"
        )
    except Exception:
        errors.append("cli_entrypoint_unreadable")

    if observed_routes is not None:
        route_rows = coverage.get("mcp_cli_routes", [])
        declared = {str(row["command"]): row for row in route_rows}
        if set(observed_routes) != set(declared):
            errors.append("mcp_cli_route_inventory_stale")
        for command, row in declared.items():
            actual = observed_routes.get(command, {})
            if (
                actual.get("function") != row.get("function")
                or row.get("module", "").removeprefix("digital_asset_directory.")
                not in actual.get("imports", set())
                or row.get("call") not in actual.get("calls", set())
            ):
                errors.append("mcp_cli_route_contract_stale")

    gate = coverage.get("repository_validation_gate", {})
    try:
        function = _function_node(repo_root / str(gate["path"]), str(gate["function"]))
        imports = {
            str(node.module or "")
            for node in ast.walk(function)
            if isinstance(node, ast.ImportFrom) and node.level
        }
        calls = {
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        string_constants = {
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        if (
            "mcp_dependency_map" not in imports
            or "mcp_server" not in imports
            or "validate_mcp_dependency_map" not in calls
            or "DADGraphMCPServer" not in calls
            or "current_claims_allowed" not in string_constants
        ):
            errors.append("repository_validation_gate_stale")
    except Exception:
        errors.append("repository_validation_gate_unreadable")

    consumer_ids = {str(item) for item in coverage.get("consumer_node_ids", [])}
    node_ids = {
        str(node.get("node_id", ""))
        for node in dependency_map.get("nodes", [])
        if isinstance(node, Mapping)
    }
    if (
        consumer_ids
        != {
            "mcp.node.host-adapter.installed-evidence",
            "mcp.node.host-adapter.templates",
            "mcp.node.navigation.ai-registry",
            "mcp.node.navigation.ai-toc",
            "mcp.node.navigation.machine-route",
            "mcp.node.validation.deterministic-suite",
            "mcp.node.validation.repository-gate",
        }
        or not consumer_ids <= node_ids
    ):
        errors.append("consumer_coverage_stale")
    return errors


def _resource_covered(uri: str, row: Mapping[str, Any]) -> bool:
    mode, value = str(row.get("match", "")), str(row.get("value", ""))
    return uri == value if mode == "exact" else uri.startswith(value)


def _runtime_errors(
    dependency_map: Mapping[str, Any],
    runtime_tools: Iterable[str] | None,
    runtime_resources: Iterable[str] | None,
) -> list[str]:
    errors: list[str] = []
    interfaces = dependency_map.get("interfaces", {})
    if runtime_tools is not None and set(runtime_tools) != set(interfaces.get("tools", [])):
        errors.append("tool_inventory_stale")
    if runtime_resources is not None:
        resources = list(runtime_resources)
        coverage = interfaces.get("resource_coverage", [])
        if any(not any(_resource_covered(uri, row) for row in coverage) for uri in resources):
            errors.append("resource_inventory_uncovered")
        for row in coverage:
            if not row.get("allow_empty") and not any(
                _resource_covered(uri, row) for uri in resources
            ):
                errors.append("resource_inventory_stale")
    return errors


def _host_errors(
    repo_root: Path,
    dependency_map: Mapping[str, Any],
    runtime_tools: Iterable[str] | None,
    *,
    now: datetime | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        contract = _load_json(repo_root / HOST_CONTRACT_PATH)
        contract_schema = _load_json(repo_root / HOST_CONTRACT_SCHEMA_PATH)
        cls = validator_for(contract_schema)
        cls.check_schema(contract_schema)
        cls(contract_schema).validate(contract)
        evidence = _load_json(repo_root / HOST_EVIDENCE_PATH)
        evidence_schema = _load_json(repo_root / HOST_EVIDENCE_SCHEMA_PATH)
        evidence_cls = validator_for(evidence_schema)
        evidence_cls.check_schema(evidence_schema)
        evidence_cls(evidence_schema).validate(evidence)
    except Exception:
        return ["host_contract_invalid"]
    declared_tools = set(contract.get("server_contract", {}).get("allowed_tools", []))
    mapped_tools = set(dependency_map.get("interfaces", {}).get("tools", []))
    if declared_tools != mapped_tools or (
        runtime_tools is not None and declared_tools != set(runtime_tools)
    ):
        errors.append("host_tool_allowlist_drift")
    adapter_ids = {str(row.get("adapter_id", "")) for row in contract.get("adapters", [])}
    evidence_ids = {str(row.get("adapter_id", "")) for row in evidence.get("hosts", [])}
    if adapter_ids != evidence_ids:
        errors.append("installed_host_evidence_incomplete")
    clock = now or datetime.now(timezone.utc)
    try:
        captured = datetime.fromisoformat(str(evidence["captured_at"]).replace("Z", "+00:00"))
        age_seconds = (clock - captured.astimezone(timezone.utc)).total_seconds()
        max_age_seconds = int(evidence["observation_max_age_days"]) * 86400
        future_skew_seconds = int(evidence["future_skew_seconds"])
        if age_seconds < -future_skew_seconds:
            errors.append("installed_host_evidence_from_future")
        elif age_seconds > max_age_seconds:
            errors.append("installed_host_evidence_stale")
    except (KeyError, TypeError, ValueError):
        errors.append("installed_host_evidence_freshness_invalid")
    source_hosts = {str(row.get("host", "")) for row in contract.get("first_party_sources", [])}
    contract_hosts = {str(row.get("host", "")) for row in contract.get("adapters", [])}
    if not contract_hosts.issubset(source_hosts):
        errors.append("first_party_source_coverage_stale")
    today = datetime.now(timezone.utc).date()
    for row in contract.get("first_party_sources", []):
        try:
            checked = date.fromisoformat(str(row["checked_at"]))
            maximum = int(row["max_age_days"])
        except (KeyError, TypeError, ValueError):
            errors.append("first_party_source_freshness_invalid")
            continue
        if (today - checked).days > maximum:
            errors.append("first_party_source_stale")
    return errors


def validate_mcp_dependency_map(
    repo_root: Path,
    *,
    runtime_tools: Iterable[str] | None = None,
    runtime_resources: Iterable[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a path-safe categorical freshness report; never mutate source."""

    try:
        dependency_map = load_mcp_dependency_map(repo_root)
    except Exception:
        return {
            "schema_version": "dad.mcp.dependency_status.v1",
            "state": "invalid",
            "current_claims_allowed": False,
            "issue_codes": ["map_unreadable"],
        }
    errors = _schema_errors(repo_root, dependency_map)
    errors.extend(_structure_errors(dependency_map))
    errors.extend(_privacy_errors(dependency_map))
    errors.extend(_coverage_errors(repo_root, dependency_map))
    errors.extend(_runtime_errors(dependency_map, runtime_tools, runtime_resources))
    errors.extend(_host_errors(repo_root, dependency_map, runtime_tools, now=now))
    for node in dependency_map.get("nodes", []):
        fingerprint = node.get("fingerprint") if isinstance(node, Mapping) else None
        if not fingerprint:
            continue
        try:
            observed = compute_fingerprint(repo_root, fingerprint)
        except Exception:
            errors.append("fingerprint_unreadable")
            continue
        if observed != fingerprint.get("sha256"):
            errors.append("fingerprint_stale")
    issue_codes = sorted(set(errors))
    current = not issue_codes
    return {
        "schema_version": "dad.mcp.dependency_status.v1",
        "state": "current" if current else "stale",
        "map_revision": str(dependency_map.get("map_revision", "unknown")),
        "current_claims_allowed": current,
        "issue_codes": issue_codes,
        "counts": {
            "categories": len({row.get("category") for row in dependency_map.get("nodes", [])}),
            "nodes": len(dependency_map.get("nodes", [])),
            "edges": len(dependency_map.get("edges", [])),
            "flows": len(dependency_map.get("data_flows", [])),
        },
        "authority": "review_only_no_execution",
    }


def build_mcp_dependency_refresh_candidate(repo_root: Path) -> dict[str, Any]:
    """Calculate, but never apply, review-only replacement fingerprints."""

    dependency_map = load_mcp_dependency_map(repo_root)
    candidates: list[dict[str, str]] = []
    for node in dependency_map.get("nodes", []):
        fingerprint = node.get("fingerprint") if isinstance(node, Mapping) else None
        if not fingerprint:
            continue
        try:
            current = compute_fingerprint(repo_root, fingerprint)
            state = "unchanged" if current == fingerprint.get("sha256") else "review_required"
        except Exception:
            current, state = "unavailable", "blocked"
        candidates.append(
            {
                "node_id": str(node.get("node_id", "")),
                "state": state,
                "declared_fingerprint": str(fingerprint.get("sha256", "")),
                "candidate_fingerprint": current,
            }
        )
    return {
        "schema_version": "dad.mcp.dependency_refresh_candidate.v1",
        "map_revision": str(dependency_map.get("map_revision", "unknown")),
        "review_only": True,
        "writes_performed": False,
        "authorization_granted": False,
        "candidates": sorted(candidates, key=lambda row: row["node_id"]),
    }


def mcp_dependency_impact(repo_root: Path, node_id: str, *, max_depth: int = 8) -> dict[str, Any]:
    """Return deterministic downstream change effects only while the map is current."""

    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 1 <= max_depth <= 16:
        raise MCPDependencyMapError("invalid_max_depth")
    status = validate_mcp_dependency_map(repo_root)
    if not status["current_claims_allowed"]:
        raise MCPDependencyMapError("dependency_map_stale")
    dependency_map = load_mcp_dependency_map(repo_root)
    nodes = {str(row["node_id"]): row for row in dependency_map["nodes"]}
    if node_id not in nodes:
        raise MCPDependencyMapError("unknown_dependency_node")
    outgoing: dict[str, list[Mapping[str, Any]]] = {}
    for edge in dependency_map["edges"]:
        outgoing.setdefault(str(edge["source"]), []).append(edge)
    seen = {node_id}
    frontier = [(node_id, 0)]
    effects: list[dict[str, Any]] = []
    while frontier:
        current, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        for edge in sorted(outgoing.get(current, []), key=lambda row: str(row["edge_id"])):
            target = str(edge["target"])
            effects.append(
                {
                    "edge_id": str(edge["edge_id"]),
                    "target_node_id": target,
                    "target_category": str(nodes[target]["category"]),
                    "change_effect": str(edge["change_effect"]),
                    "depth": depth + 1,
                }
            )
            if target not in seen:
                seen.add(target)
                frontier.append((target, depth + 1))
    return {
        "schema_version": "dad.mcp.dependency_impact.v1",
        "claim_state": "current",
        "map_revision": dependency_map["map_revision"],
        "source_node_id": node_id,
        "source_category": nodes[node_id]["category"],
        "affected_node_ids": sorted(seen - {node_id}),
        "effects": effects,
        "authority": "candidate_review_only",
    }
