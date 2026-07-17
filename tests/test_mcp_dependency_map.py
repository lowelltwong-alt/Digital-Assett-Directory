from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digital_asset_directory.mcp_dependency_map import (
    MAP_PATH,
    MCPDependencyMapError,
    _mcp_cli_routes,
    _structure_errors,
    build_mcp_dependency_refresh_candidate,
    mcp_dependency_impact,
    validate_mcp_dependency_map,
)
from digital_asset_directory.mcp_server import (
    DADGraphMCPServer,
    _sanitize_resource_text,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "dad_graph_surface_status",
    "dad_graph_get_node",
    "dad_graph_neighbors",
    "dad_graph_search_nodes",
    "dad_mcp_dependency_status",
    "dad_mcp_dependency_impact",
    "dad_mcp_dependency_refresh_candidate",
    "dad_lifecycle_packet_prepare",
    "dad_recovery_packet_prepare",
    "dad_lifecycle_result_record",
    "dad_recovery_result_record",
}


def _runtime(root: Path) -> tuple[list[str], list[str]]:
    server = DADGraphMCPServer(root)
    return (
        [row["name"] for row in server.list_tools()],
        [row["uri"] for row in server.list_resources()],
    )


def _copy_contract(tmp_path: Path) -> Path:
    target = tmp_path / "hub"
    dependency_map = json.loads((ROOT / MAP_PATH).read_text(encoding="utf-8"))
    files = {
        "registry/mcp-dependency-map.json",
        "schemas/mcp-dependency-map.schema.json",
        "assets/mcp/dad-local-readonly/contract.json",
        "assets/mcp/dad-local-readonly/contract.schema.json",
        "assets/mcp/dad-local-readonly/installed-host-evidence.json",
        "assets/mcp/dad-local-readonly/installed-host-evidence.schema.json",
        "registry/graph-surface-registry.json",
    }
    for node in dependency_map["nodes"]:
        if node.get("fingerprint") and node["fingerprint"]["kind"] != "tree_sha256":
            files.add(node["fingerprint"]["path"])
    for relative in sorted(files):
        source = ROOT / relative
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copytree(
        ROOT / "assets/mcp/dad-local-readonly/templates",
        target / "assets/mcp/dad-local-readonly/templates",
    )
    shutil.copy2(
        ROOT / "assets/mcp/dad-local-readonly/validate.py",
        target / "assets/mcp/dad-local-readonly/validate.py",
    )
    shutil.copy2(
        ROOT / "assets/mcp/dad-local-readonly/README.md",
        target / "assets/mcp/dad-local-readonly/README.md",
    )
    return target


def _mutate_map(root: Path, mutate) -> None:
    path = root / MAP_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _status(root: Path, *, now: datetime | None = None) -> dict:
    tools, resources = _runtime(root)
    return validate_mcp_dependency_map(
        root, runtime_tools=tools, runtime_resources=resources, now=now
    )


def test_dependency_map_is_current_and_covers_every_required_category() -> None:
    status = _status(ROOT)
    dependency_map = json.loads((ROOT / MAP_PATH).read_text(encoding="utf-8"))
    routes = _mcp_cli_routes(ROOT / "src/digital_asset_directory/cli.py")

    assert status["state"] == "current", status
    assert status["current_claims_allowed"] is True
    assert status["issue_codes"] == []
    assert set(routes) == {"graph-stdio"}
    assert routes["graph-stdio"]["function"] == "mcp_graph_stdio"
    assert {node["category"] for node in dependency_map["nodes"]} == set(
        dependency_map["required_categories"]
    )


@pytest.mark.parametrize(
    "category",
    [
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
    ],
)
def test_every_required_category_is_fail_closed_when_removed(
    category: str,
) -> None:
    payload = deepcopy(json.loads((ROOT / MAP_PATH).read_text(encoding="utf-8")))
    payload["nodes"] = [node for node in payload["nodes"] if node["category"] != category]

    assert "category_coverage_invalid" in _structure_errors(payload)


def test_semantic_and_exact_fingerprint_drift_fail_closed(tmp_path: Path) -> None:
    root = _copy_contract(tmp_path)
    registry = root / "registry/graph-surface-registry.json"
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["surfaces"][0]["purpose"] += " changed"
    registry.write_text(json.dumps(payload), encoding="utf-8")

    assert "fingerprint_stale" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "exact")
    server = root / "src/digital_asset_directory/mcp_server.py"
    server.write_text(server.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    assert "fingerprint_stale" in _status(root)["issue_codes"]


def test_import_tool_resource_and_cli_inventory_drift_fail_closed(tmp_path: Path) -> None:
    root = _copy_contract(tmp_path)
    server = root / "src/digital_asset_directory/mcp_server.py"
    server.write_text(
        server.read_text(encoding="utf-8") + "\nfrom .unmapped_backend import value\n",
        encoding="utf-8",
    )
    assert "python_import_inventory_stale" in _status(root)["issue_codes"]

    tools, resources = _runtime(ROOT)
    assert (
        "tool_inventory_stale"
        in validate_mcp_dependency_map(
            ROOT,
            runtime_tools=[*tools, "dad_fake_tool"],
            runtime_resources=resources,
        )["issue_codes"]
    )
    assert (
        "resource_inventory_uncovered"
        in validate_mcp_dependency_map(
            ROOT,
            runtime_tools=tools,
            runtime_resources=[*resources, "dad://unmapped/resource"],
        )["issue_codes"]
    )

    root = _copy_contract(tmp_path / "cli")
    cli = root / "src/digital_asset_directory/cli.py"
    cli.write_text(
        cli.read_text(encoding="utf-8").replace(
            '@mcp_app.command("graph-stdio")', '@mcp_app.command("renamed")'
        ),
        encoding="utf-8",
    )
    assert "cli_entrypoint_stale" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "route")
    cli = root / "src/digital_asset_directory/cli.py"
    cli.write_text(
        cli.read_text(encoding="utf-8")
        + '\n@mcp_app.command("remote-write")\n'
        + "def mcp_remote_write() -> None:\n"
        + "    from .mcp_graph_server import run_stdio_server\n"
        + "    run_stdio_server(Path('.'))\n",
        encoding="utf-8",
    )
    assert "mcp_cli_route_inventory_stale" in _status(root)["issue_codes"]


@pytest.mark.parametrize(
    ("decorator", "function_name", "expected_route"),
    [
        ("@mcp_app.command()", "remote_write", "remote-write"),
        (
            '@mcp_app.command(name="keyword-write")',
            "keyword_writer",
            "keyword-write",
        ),
    ],
)
def test_implicit_and_keyword_mcp_routes_make_inventory_stale(
    tmp_path: Path,
    decorator: str,
    function_name: str,
    expected_route: str,
) -> None:
    root = _copy_contract(tmp_path)
    cli = root / "src/digital_asset_directory/cli.py"
    cli.write_text(
        cli.read_text(encoding="utf-8")
        + f"\n{decorator}\n"
        + f"def {function_name}() -> None:\n"
        + "    from .mcp_graph_server import run_stdio_server\n"
        + "    run_stdio_server(Path('.'))\n",
        encoding="utf-8",
    )

    assert expected_route in _mcp_cli_routes(cli)
    assert "mcp_cli_route_inventory_stale" in _status(root)["issue_codes"]


@pytest.mark.parametrize(
    "decorator",
    [
        "@mcp_app.command(name=DYNAMIC_ROUTE)",
        '@mcp_app.command("first", name="second")',
    ],
)
def test_dynamic_or_ambiguous_mcp_route_names_fail_closed(tmp_path: Path, decorator: str) -> None:
    root = _copy_contract(tmp_path)
    cli = root / "src/digital_asset_directory/cli.py"
    cli.write_text(
        cli.read_text(encoding="utf-8")
        + f"\n{decorator}\n"
        + "def dynamic_writer() -> None:\n"
        + "    pass\n",
        encoding="utf-8",
    )

    with pytest.raises(MCPDependencyMapError, match="mcp_cli_route_name_ambiguous"):
        _mcp_cli_routes(cli)
    assert "mcp_cli_route_name_ambiguous" in _status(root)["issue_codes"]


def test_repository_validation_behavior_not_success_marker_is_bound(tmp_path: Path) -> None:
    root = _copy_contract(tmp_path)
    validation = root / "src/digital_asset_directory/validation.py"
    validation.write_text(
        validation.read_text(encoding="utf-8").replace(
            "mcp_status = validate_mcp_dependency_map(",
            "mcp_status = dict(",
            1,
        ),
        encoding="utf-8",
    )

    issues = _status(root)["issue_codes"]
    assert "repository_validation_gate_stale" in issues
    assert "fingerprint_stale" in issues


def test_adapter_authority_flow_and_cycle_mutations_fail_closed(tmp_path: Path) -> None:
    root = _copy_contract(tmp_path)
    contract = root / "assets/mcp/dad-local-readonly/contract.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["server_contract"]["allowed_tools"].append("dad_write_anything")
    contract.write_text(json.dumps(payload), encoding="utf-8")
    assert "host_contract_invalid" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "authority")
    _mutate_map(
        root,
        lambda payload: payload["authority_policy"].update({"execution_authority": True}),
    )
    status = _status(root)
    assert (
        "authority_direction_invalid" in status["issue_codes"]
        or "schema_invalid" in status["issue_codes"]
    )

    root = _copy_contract(tmp_path / "flow")
    _mutate_map(
        root,
        lambda payload: payload["data_flows"][0]["steps"].reverse(),
    )
    assert "data_flow_direction_invalid" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "cycle")

    def add_cycle(payload: dict) -> None:
        payload["edges"].append(
            {
                "edge_id": "mcp.edge.synthetic-cycle",
                "source": "mcp.node.navigation.machine-route",
                "target": "mcp.node.registry.dependency-map",
                "edge_type": "routes_to",
                "change_effect": "registry_semantic_review",
            }
        )

    _mutate_map(root, add_cycle)
    assert "unsafe_cycle" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "effect")
    _mutate_map(
        root,
        lambda payload: payload["edges"][0].update({"change_effect": "navigation_refresh"}),
    )
    assert "edge_direction_contract_stale" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "privacy")
    _mutate_map(
        root,
        lambda payload: payload["nodes"][0].update({"label": "C:\\Users\\example\\private"}),
    )
    assert "absolute_path_prohibited" in _status(root)["issue_codes"]


def test_impact_refuses_stale_map_and_refresh_is_review_only(tmp_path: Path) -> None:
    current = mcp_dependency_impact(ROOT, "mcp.node.registry.graph-surfaces")
    assert current["claim_state"] == "current"
    assert "mcp.node.implementation.server" in current["affected_node_ids"]

    root = _copy_contract(tmp_path)
    before = hashlib.sha256((root / MAP_PATH).read_bytes()).hexdigest()
    _mutate_map(
        root,
        lambda payload: payload["nodes"][0]["fingerprint"].update({"sha256": "sha256:" + "f" * 64}),
    )
    with pytest.raises(MCPDependencyMapError, match="dependency_map_stale"):
        mcp_dependency_impact(root, "mcp.node.registry.graph-surfaces")
    candidate = build_mcp_dependency_refresh_candidate(root)
    after = hashlib.sha256((root / MAP_PATH).read_bytes()).hexdigest()
    assert candidate["review_only"] is True
    assert candidate["writes_performed"] is False
    assert candidate["authorization_granted"] is False
    assert before != after  # the test mutation changed it before the candidate call
    stable = hashlib.sha256((root / MAP_PATH).read_bytes()).hexdigest()
    build_mcp_dependency_refresh_candidate(root)
    assert hashlib.sha256((root / MAP_PATH).read_bytes()).hexdigest() == stable


def test_server_initialize_tool_resource_parity_and_fake_mutation_denial() -> None:
    server = DADGraphMCPServer(ROOT)
    initialized = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert initialized["result"]["serverInfo"]["name"] == "dad-local-graph-surfaces"
    tools = {row["name"] for row in server.list_tools()}
    assert tools == EXPECTED_TOOLS
    resources = {row["uri"] for row in server.list_resources()}
    assert {
        "dad://mcp/dependency-map",
        "dad://mcp/dependency-status",
        "dad://mcp/dependency-refresh-candidate",
        "dad://mcp/installed-host-status",
    }.issubset(resources)
    status = server.call_tool("dad_mcp_dependency_status")["structuredContent"]
    assert status["state"] == "current"
    impact = server.call_tool(
        "dad_mcp_dependency_impact",
        {"node_id": "mcp.node.registry.graph-surfaces"},
    )["structuredContent"]
    assert impact["claim_state"] == "current"
    denied = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "dad_mcp_apply_dependency_refresh", "arguments": {}},
        }
    )
    assert denied["error"]["code"] == -32601
    invalid = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "dad_mcp_dependency_impact",
                "arguments": {
                    "node_id": "mcp.node.registry.graph-surfaces",
                    "max_depth": 99,
                },
            },
        }
    )
    assert invalid["error"]["code"] == -32602


def test_all_mcp_response_sanitization_removes_local_paths_and_credentials(
    tmp_path: Path,
) -> None:
    sanitized = _sanitize_resource_text(
        "application/json",
        json.dumps(
            {
                "report_path": "C:\\Users\\example\\private.json",
                "nested": {"api_key": "do-not-return", "safe": "candidate"},
            }
        ),
    )
    assert "C:\\Users" not in sanitized
    assert "do-not-return" not in sanitized
    assert "api_key" not in sanitized
    assert "candidate" in sanitized

    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "schema-registry.json").write_text(
        json.dumps(
            {
                "report_path": "C:\\Users\\example\\private.json",
                "password": "do-not-return",
                "state": "candidate",
            }
        ),
        encoding="utf-8",
    )
    resource = DADGraphMCPServer(tmp_path).read_resource("dad://registry/schema-registry")
    resource_text = resource["contents"][0]["text"]
    assert "C:\\Users" not in resource_text
    assert "do-not-return" not in resource_text
    assert "password" not in resource_text


def test_installed_host_evidence_does_not_claim_unavailable_copilot_is_active() -> None:
    evidence = json.loads(
        (ROOT / "assets/mcp/dad-local-readonly/installed-host-evidence.json").read_text(
            encoding="utf-8"
        )
    )
    rows = {row["adapter_id"]: row for row in evidence["hosts"]}
    assert rows["vscode_github_copilot"]["activation_state"] == "host_unavailable"
    assert rows["github_copilot_cli"]["activation_state"] == "host_unavailable"
    assert evidence["observation_policy"]["unrelated_config_read"] is False
    assert evidence["observation_policy"]["config_payload_retained"] is False


def test_installed_host_evidence_expires_instead_of_becoming_false_current(
    tmp_path: Path,
) -> None:
    root = _copy_contract(tmp_path)
    path = root / "assets/mcp/dad-local-readonly/installed-host-evidence.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence["captured_at"] = "2020-01-01T00:00:00Z"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    assert "installed_host_evidence_stale" in _status(root)["issue_codes"]


def test_installed_host_evidence_uses_exact_seconds_and_rejects_future(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 13, 21, 0, tzinfo=timezone.utc)
    cases = [
        ("boundary", now - timedelta(days=7), None),
        ("late", now - timedelta(days=7, hours=1), "installed_host_evidence_stale"),
        ("future", now + timedelta(days=30), "installed_host_evidence_from_future"),
    ]
    for name, captured, expected in cases:
        root = _copy_contract(tmp_path / name)
        path = root / "assets/mcp/dad-local-readonly/installed-host-evidence.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))
        evidence["captured_at"] = captured.isoformat().replace("+00:00", "Z")
        path.write_text(json.dumps(evidence), encoding="utf-8")
        issues = _status(root, now=now)["issue_codes"]
        if expected is None:
            assert "installed_host_evidence_stale" not in issues
            assert "installed_host_evidence_from_future" not in issues
        else:
            assert expected in issues


def test_navigation_consumers_are_semantically_fingerprinted(tmp_path: Path) -> None:
    root = _copy_contract(tmp_path)
    toc = root / "AI_TABLE_OF_CONTENTS.md"
    toc.write_text(
        toc.read_text(encoding="utf-8").replace("reverse blast-radius map", "untracked route", 1),
        encoding="utf-8",
    )
    assert "fingerprint_stale" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "registry")
    navigation = root / "registry/ai-navigation-registry.json"
    navigation.write_text(
        navigation.read_text(encoding="utf-8").replace(
            '        "schemas/mcp-dependency-map.schema.json",\n', "", 1
        ),
        encoding="utf-8",
    )
    assert "fingerprint_unreadable" in _status(root)["issue_codes"]

    root = _copy_contract(tmp_path / "consumer")
    _mutate_map(
        root,
        lambda payload: payload["coverage"]["consumer_node_ids"].pop(),
    )
    assert "consumer_coverage_stale" in _status(root)["issue_codes"]


def test_json_rpc_generic_errors_are_categorical_and_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = DADGraphMCPServer(tmp_path)
    missing = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": "dad://registry/schema-registry"},
        }
    )
    assert missing["error"]["data"]["error_code"] == "internal_error"
    assert str(tmp_path) not in missing["error"]["message"]
    assert "schema-registry" not in missing["error"]["message"]

    def private_failure(_uri: str) -> dict:
        raise RuntimeError(f"{tmp_path} api_key=private-value confidential private prose")

    monkeypatch.setattr(server, "read_resource", private_failure)
    private = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/read",
            "params": {"uri": "dad://registry/schema-registry"},
        }
    )
    encoded = json.dumps(private)
    assert "private-value" not in encoded
    assert "confidential private prose" not in encoded
    assert str(tmp_path) not in encoded
    assert private["error"]["data"]["error_code"] == "internal_error"
