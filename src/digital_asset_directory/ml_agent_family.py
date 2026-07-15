from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import yaml
from jsonschema.validators import validator_for


FAMILY_REGISTRY = Path("registry/ml-agent-family-registry.json")
FAMILY_SCHEMA = Path("schemas/ml-agent-family-registry.schema.json")
TECHNIQUE_REGISTRY = Path("registry/ml-technique-registry.json")
TECHNIQUE_SCHEMA = Path("schemas/ml-technique-registry.schema.json")
SUBAGENT_PACK = Path("assets/agent-skills/ml-workflow-agent-family/subagents.yaml")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_validated(repo_root: Path, registry: Path, schema: Path) -> dict[str, Any]:
    payload = _load_json(repo_root / registry)
    schema_payload = _load_json(repo_root / schema)
    validator_cls = validator_for(schema_payload)
    validator_cls.check_schema(schema_payload)
    validator_cls(schema_payload).validate(payload)
    return payload


def load_ml_family(repo_root: Path) -> dict[str, Any]:
    return _load_validated(repo_root, FAMILY_REGISTRY, FAMILY_SCHEMA)


def load_ml_techniques(repo_root: Path) -> dict[str, Any]:
    return _load_validated(repo_root, TECHNIQUE_REGISTRY, TECHNIQUE_SCHEMA)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _matches(query: str, row: dict[str, Any]) -> bool:
    wanted = _tokens(query)
    if not wanted:
        return True
    searchable = _tokens(json.dumps(row, sort_keys=True))
    return wanted <= searchable


def ml_catalog(repo_root: Path, query: str = "") -> dict[str, Any]:
    family = load_ml_family(repo_root)
    techniques = load_ml_techniques(repo_root)
    pack = yaml.safe_load((repo_root / SUBAGENT_PACK).read_text(encoding="utf-8"))
    role_rows = [row for row in pack["roles"] if _matches(query, row)]
    technique_rows = [row for row in techniques["techniques"] if _matches(query, row)]
    workflow_rows = [row for row in family["workflow_cards"] if _matches(query, row)]
    return {
        "schema_version": "ml.catalog.v1",
        "query": query,
        "candidate_only": True,
        "counts": {
            "roles": len(role_rows),
            "techniques": len(technique_rows),
            "workflows": len(workflow_rows),
        },
        "roles": role_rows,
        "techniques": technique_rows,
        "workflows": workflow_rows,
        "authority_boundary": family["authority_boundary"],
    }


def ml_family_status(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    family = load_ml_family(repo_root)
    techniques = load_ml_techniques(repo_root)
    pack = yaml.safe_load((repo_root / SUBAGENT_PACK).read_text(encoding="utf-8"))
    observed_now = now or datetime.now(timezone.utc)
    observations: list[dict[str, Any]] = []
    for row in family["runtime_adapter_observations"]:
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        observations.append(
            {
                **row,
                "freshness": "current" if observed_now < expires_at else "stale",
            }
        )
    return {
        "schema_version": "ml.family.status.v1",
        "registry_version": family["registry_version"],
        "status": family["status"],
        "ai_agnostic": family["ai_agnostic"],
        "routing_authority": family["routing_authority"],
        "runtime_adapter_observations": observations,
        "role_count": len(pack["roles"]),
        "technique_count": len(techniques["techniques"]),
        "workflow_count": len(family["workflow_cards"]),
        "research_activation_status": family["research_contract"]["activation_status"],
        "research_cadence": family["research_contract"]["cadence"],
        "candidate_only": True,
        "authority_boundary": family["authority_boundary"],
    }


def _walk_dependencies(
    start: str, edges: list[dict[str, Any]], *, direction: str
) -> list[dict[str, Any]]:
    if direction not in {"upstream", "downstream"}:
        raise ValueError("direction must be upstream or downstream")
    queue: deque[str] = deque([start])
    visited_nodes = {start}
    found: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    while queue:
        current = queue.popleft()
        for edge in edges:
            matches = edge["source"] == current if direction == "upstream" else edge["target"] == current
            if not matches:
                continue
            key = (edge["source"], edge["edge_type"], edge["target"])
            if key not in seen_edges:
                found.append(edge)
                seen_edges.add(key)
            next_node = edge["target"] if direction == "upstream" else edge["source"]
            if next_node not in visited_nodes:
                visited_nodes.add(next_node)
                queue.append(next_node)
    return sorted(found, key=lambda row: (row["source"], row["edge_type"], row["target"]))


def ml_dependency_graph(repo_root: Path, node: str | None = None) -> dict[str, Any]:
    family = load_ml_family(repo_root)
    graph = family["graph_contract"]
    edges = graph["dependency_edges"]
    nodes = sorted({value for edge in edges for value in (edge["source"], edge["target"])})
    if node is not None and node not in nodes:
        raise ValueError(f"Unknown ML family graph node: {node}")
    upstream = _walk_dependencies(node, edges, direction="upstream") if node else edges
    downstream = _walk_dependencies(node, edges, direction="downstream") if node else edges
    return {
        "schema_version": "ml.family.dependency_graph.v1",
        "focus_node": node,
        "candidate_only": True,
        "node_types": graph["node_types"],
        "nodes": nodes,
        "upstream_edges": upstream,
        "downstream_edges": downstream,
        "forbidden_claims": graph["forbidden_claims"],
        "authority_boundary": family["authority_boundary"],
    }


def ml_research_plan(repo_root: Path) -> dict[str, Any]:
    family = load_ml_family(repo_root)
    workflow = next(
        row
        for row in family["workflow_cards"]
        if row["workflow_id"] == "workflow:ml-frontier-research-refresh"
    )
    return {
        "schema_version": "ml.research.plan.v1",
        "workflow": workflow,
        "contract": family["research_contract"],
        "scheduled": False,
        "activation_required": True,
        "candidate_only": True,
        "authority_boundary": family["authority_boundary"],
    }
