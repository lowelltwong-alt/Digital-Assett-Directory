from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import re
from typing import Any

from jsonschema.validators import validator_for
import yaml


FAMILY_REGISTRY = Path("registry/knowledge-engineering-family-registry.json")
FAMILY_SCHEMA = Path("schemas/knowledge-engineering-family-registry.schema.json")
TECHNIQUE_REGISTRY = Path("registry/knowledge-engineering-technique-registry.json")
TECHNIQUE_SCHEMA = Path("schemas/knowledge-engineering-technique-registry.schema.json")
SOURCE_REGISTRY = Path("registry/knowledge-engineering-source-registry.json")
SOURCE_SCHEMA = Path("schemas/knowledge-engineering-source-registry.schema.json")
SUBAGENT_PACK = Path("assets/agent-skills/knowledge-engineering-ops/subagents.yaml")

BASELINE_TECHNIQUE_IDS = (
    "ke-technique:no-retrieval-direct-source",
    "ke-technique:lexical-bm25",
    "ke-technique:retrieval-evaluation-observability",
    "ke-technique:retrieval-security-and-poisoning-controls",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_validated(repo_root: Path, registry: Path, schema: Path) -> dict[str, Any]:
    payload = _load_json(repo_root / registry)
    schema_payload = _load_json(repo_root / schema)
    validator_cls = validator_for(schema_payload)
    validator_cls.check_schema(schema_payload)
    validator_cls(schema_payload, format_checker=validator_cls.FORMAT_CHECKER).validate(payload)
    return payload


def load_knowledge_family(repo_root: Path) -> dict[str, Any]:
    return _load_validated(repo_root, FAMILY_REGISTRY, FAMILY_SCHEMA)


def load_knowledge_techniques(repo_root: Path) -> dict[str, Any]:
    return _load_validated(repo_root, TECHNIQUE_REGISTRY, TECHNIQUE_SCHEMA)


def load_knowledge_sources(repo_root: Path) -> dict[str, Any]:
    return _load_validated(repo_root, SOURCE_REGISTRY, SOURCE_SCHEMA)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _token_sequence(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.lower()))


def _contains_token_sequence(query: tuple[str, ...], term: tuple[str, ...]) -> bool:
    if not term or len(term) > len(query):
        return False
    width = len(term)
    return any(query[index : index + width] == term for index in range(len(query) - width + 1))


def _matches(query: str, row: dict[str, Any]) -> bool:
    wanted = _tokens(query)
    if not wanted:
        return True
    searchable = _tokens(json.dumps(row, sort_keys=True))
    return wanted <= searchable


def knowledge_catalog(repo_root: Path, query: str = "") -> dict[str, Any]:
    family = load_knowledge_family(repo_root)
    techniques = load_knowledge_techniques(repo_root)
    sources = load_knowledge_sources(repo_root)
    pack = yaml.safe_load((repo_root / SUBAGENT_PACK).read_text(encoding="utf-8"))
    roles = [row for row in pack["roles"] if _matches(query, row)]
    technique_rows = [row for row in techniques["techniques"] if _matches(query, row)]
    workflows = [row for row in family["workflow_cards"] if _matches(query, row)]
    source_rows = [row for row in sources["sources"] if _matches(query, row)]
    return {
        "schema_version": "knowledge.engineering.catalog.v1",
        "query": query,
        "candidate_only": True,
        "counts": {
            "roles": len(roles),
            "techniques": len(technique_rows),
            "workflows": len(workflows),
            "sources": len(source_rows),
        },
        "roles": roles,
        "techniques": technique_rows,
        "workflows": workflows,
        "sources": source_rows,
        "authority_boundary": family["authority_boundary"],
    }


def knowledge_status(repo_root: Path) -> dict[str, Any]:
    family = load_knowledge_family(repo_root)
    techniques = load_knowledge_techniques(repo_root)
    sources = load_knowledge_sources(repo_root)
    pack = yaml.safe_load((repo_root / SUBAGENT_PACK).read_text(encoding="utf-8"))
    return {
        "schema_version": "knowledge.engineering.status.v1",
        "registry_version": family["registry_version"],
        "status": family["status"],
        "candidate_only": True,
        "ai_agnostic": family["ai_agnostic"],
        "parent_family_id": family["parent_family_id"],
        "peer_family_ids": family["peer_family_ids"],
        "role_count": len(pack["roles"]),
        "technique_count": len(techniques["techniques"]),
        "workflow_count": len(family["workflow_cards"]),
        "source_count": len(sources["sources"]),
        "research_cadence": family["research_contract"]["cadence"],
        "research_activation_status": family["research_contract"]["activation_status"],
        "scheduled": False,
        "routing_authority": family["routing_authority"],
        "authority_boundary": family["authority_boundary"],
    }


def _profile_score(query: str, profile: dict[str, Any]) -> int:
    query_sequence = _token_sequence(query)
    query_tokens = _tokens(query)
    score = 0
    for term in profile["query_terms"]:
        term_sequence = _token_sequence(term)
        term_tokens = _tokens(term)
        overlap = len(query_tokens & term_tokens)
        score += overlap
        if _contains_token_sequence(query_sequence, term_sequence):
            score += 3 + len(term_tokens)
    return score


def knowledge_route(repo_root: Path, query: str) -> dict[str, Any]:
    family = load_knowledge_family(repo_root)
    techniques = load_knowledge_techniques(repo_root)
    known_ids = {row["technique_id"] for row in techniques["techniques"]}
    scored = [
        {"profile": profile, "score": _profile_score(query, profile)}
        for profile in family["routing_profiles"]
    ]
    candidates = sorted(
        (row for row in scored if row["score"] > 0),
        key=lambda row: (-row["score"], row["profile"]["profile_id"]),
    )
    top = candidates[0]["score"] if candidates else 0
    equal_best = [row for row in candidates if row["score"] == top]
    selected = equal_best[0]["profile"] if len(equal_best) == 1 else None
    candidate_profiles = [row["profile"] for row in equal_best] if equal_best else []

    technique_ids = list(BASELINE_TECHNIQUE_IDS)
    for profile in ([selected] if selected else candidate_profiles):
        if profile is None:
            continue
        for technique_id in profile["technique_ids"]:
            if technique_id not in technique_ids:
                technique_ids.append(technique_id)
    unknown = sorted(set(technique_ids) - known_ids)
    if unknown:
        raise ValueError(f"Unknown technique IDs in routing profiles: {unknown}")

    required_gates = sorted(
        {
            gate
            for profile in ([selected] if selected else candidate_profiles)
            if profile is not None
            for gate in profile["required_gates"]
        }
        | {"source authority", "independent evaluation", "privacy and access"}
    )
    if selected is not None:
        disposition = "bounded_candidate_route"
        route_kind: str | None = selected["route_kind"]
        reason = selected["reason"]
    elif candidate_profiles:
        disposition = "ambiguous_equal_best"
        route_kind = None
        reason = "Equal-best deterministic profiles preserve multiple candidates; no winner is selected."
    else:
        disposition = "insufficient_evidence"
        route_kind = None
        reason = "No routing profile has positive deterministic evidence; retain baselines and investigate."

    return {
        "schema_version": "knowledge.engineering.route.v1",
        "query": query,
        "candidate_only": True,
        "dispatch_authorized": False,
        "disposition": disposition,
        "route_kind": route_kind,
        "selected_profile_id": selected["profile_id"] if selected else None,
        "equal_best_profile_ids": [row["profile_id"] for row in candidate_profiles],
        "reason": reason,
        "baseline_technique_ids": list(BASELINE_TECHNIQUE_IDS),
        "candidate_technique_ids": technique_ids,
        "required_gates": required_gates,
        "human_decision_required": selected is None,
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


def knowledge_dependency_graph(repo_root: Path, node: str | None = None) -> dict[str, Any]:
    family = load_knowledge_family(repo_root)
    graph = family["graph_contract"]
    edges = graph["dependency_edges"]
    nodes = sorted({value for edge in edges for value in (edge["source"], edge["target"])})
    if node is not None and node not in nodes:
        raise ValueError(f"Unknown Knowledge Engineering graph node: {node}")
    upstream = _walk_dependencies(node, edges, direction="upstream") if node else edges
    downstream = _walk_dependencies(node, edges, direction="downstream") if node else edges
    return {
        "schema_version": "knowledge.engineering.dependency_graph.v1",
        "focus_node": node,
        "candidate_only": True,
        "node_types": graph["node_types"],
        "nodes": nodes,
        "upstream_edges": upstream,
        "downstream_edges": downstream,
        "forbidden_claims": graph["forbidden_claims"],
        "authority_boundary": family["authority_boundary"],
    }


def knowledge_research_plan(repo_root: Path) -> dict[str, Any]:
    family = load_knowledge_family(repo_root)
    sources = load_knowledge_sources(repo_root)
    workflow = next(
        row
        for row in family["workflow_cards"]
        if row["workflow_id"] == "workflow:ke-frontier-weekly-refresh"
    )
    return {
        "schema_version": "knowledge.engineering.research_plan.v1",
        "workflow": workflow,
        "contract": family["research_contract"],
        "watch_policy": sources["watch_policy"],
        "source_ids": [row["source_id"] for row in sources["sources"]],
        "scheduled": False,
        "activation_required": True,
        "candidate_only": True,
        "authority_boundary": family["authority_boundary"],
    }
