"""Typed, deterministic entity graph projection and safety validation."""

from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import json
from typing import Any

from .entity_identity import AUTHORITY_BOUNDARY

ACYCLIC_RELATIONS = frozenset(
    {"contains", "part_of", "specializes", "continues", "merged_into", "supersedes", "depends_on"}
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _assert_acyclic(relations: list[dict[str, Any]], relation_type: str) -> None:
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = defaultdict(int)
    nodes: set[str] = set()
    for relation in relations:
        if relation.get("relation_type") != relation_type:
            continue
        source, target = str(relation["source_entity_id"]), str(relation["target_entity_id"])
        nodes.update({source, target})
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1
            indegree.setdefault(source, 0)
    queue = deque(sorted(node for node in nodes if indegree[node] == 0))
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        raise ValueError(f"Cycle detected in {relation_type} relations")


def build_entity_graph(state: dict[str, Any]) -> dict[str, Any]:
    entities = list(state.get("entities", []))
    relations = list(state.get("relations", []))
    entity_ids = {str(row["entity_id"]) for row in entities}
    for relation in relations:
        if relation["source_entity_id"] not in entity_ids or relation["target_entity_id"] not in entity_ids:
            raise ValueError("Relation refers to a missing entity")
        if relation.get("review_status") != "candidate":
            raise ValueError("Generated graph accepts candidate relations only")
    for relation_type in ACYCLIC_RELATIONS:
        _assert_acyclic(relations, relation_type)
    nodes = [
        {
            "node_id": row["entity_id"],
            "node_type": row["semantic_card"]["entity_kind"],
            "label": row["semantic_card"]["label"],
            "revision_id": row["entity_revision_id"],
            "privacy_partition": row["semantic_card"]["privacy_partition"],
            "review_status": row.get("review_status", "candidate"),
        }
        for row in entities
    ]
    edges = [
        {
            "edge_id": row["relation_id"],
            "source": row["source_entity_id"],
            "target": row["target_entity_id"],
            "edge_type": row["relation_type"],
            "review_status": "candidate",
            "evidence_refs": row.get("evidence_refs", []),
        }
        for row in relations
    ]
    body = {"nodes": sorted(nodes, key=lambda row: row["node_id"]), "edges": sorted(edges, key=lambda row: row["edge_id"])}
    return {
        "schema_version": "dad.entity_graph.v1",
        **body,
        "graph_digest": "sha256:" + hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest(),
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def reverse_blast_radius(graph: dict[str, Any], entity_id: str) -> list[str]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for edge in graph.get("edges", []):
        reverse[str(edge["target"])].add(str(edge["source"]))
    seen: set[str] = set()
    queue = deque([entity_id])
    while queue:
        current = queue.popleft()
        for parent in sorted(reverse[current]):
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)
    return sorted(seen)


__all__ = ["ACYCLIC_RELATIONS", "build_entity_graph", "reverse_blast_radius"]
