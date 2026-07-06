"""Graph inference: complement, co-use, and combination discovery.

Deterministic structural discovery over DAD offerings and the usage ledger. It
finds pairs of assets that complement each other (adjacent workflow stages or
shared-need coverage), assets that are co-used across repos, and multi-asset
workflow combinations (produces/consumes chains and contiguous stage coverage).

Every inference edge and combination carries the method_version from
``registry/graph-inference-methodology.json``. Nothing here promotes itself; the
combination review queue and a human decide adoption. The engine is fully
deterministic: set membership, integer counts, and ordered-stage index math only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .dad_library import PATTERN_MATCH_STOPWORDS, _tokenize, load_offerings
from .ids import stable_id
from .utils import utc_now, write_json

INFERENCE_METHODOLOGY = Path("registry") / "graph-inference-methodology.json"
CENTRAL_USAGE_LEDGER = Path("processed") / "usage" / "repo-asset-usage.jsonl"
COMBINATION_QUEUE_PATH = Path("processed") / "learning" / "combination-candidates.jsonl"
INFERENCE_REPORT_PATH = Path("processed") / "learning" / "graph-inference.json"

AUTHORITY_BOUNDARY = (
    "Inference edges and combination candidates are generated candidate evidence. "
    "They are deterministic structural signals, not proof of value. Nothing here "
    "promotes itself; the combination review queue and a human decide adoption."
)


def load_inference_methodology(hub_root: Path) -> dict[str, Any]:
    return json.loads((hub_root / INFERENCE_METHODOLOGY).read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _offering_node(offering_id: str) -> str:
    return f"offering:{offering_id}"


def _repo_node(repository: str) -> str:
    name = Path(repository).name if repository else "unknown"
    import re

    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "unknown"
    return f"repo:{slug}"


class _AssetCard:
    """Facet projection of one offering used for structural inference."""

    __slots__ = ("asset_id", "node_id", "task_tokens", "stages", "produces", "consumes")

    def __init__(self, offering: dict[str, Any]) -> None:
        self.asset_id = str(offering["offering_id"])
        self.node_id = _offering_node(self.asset_id)
        self.task_tokens = _tokenize(offering.get("task_types", [])) - PATTERN_MATCH_STOPWORDS
        self.stages = list(dict.fromkeys(offering.get("workflow_stages", []) or []))
        self.produces = set(offering.get("produces", []) or [])
        self.consumes = set(offering.get("consumes", []) or [])


def _build_cards(hub_root: Path) -> list[_AssetCard]:
    offerings = load_offerings(hub_root).get("offerings", [])
    cards = [_AssetCard(o) for o in offerings if o.get("offering_id")]
    cards.sort(key=lambda c: c.asset_id)
    return cards


def _min_stage_gap(
    stages_a: list[str], stages_b: list[str], order: dict[str, int]
) -> int | None:
    idx_a = [order[s] for s in stages_a if s in order]
    idx_b = [order[s] for s in stages_b if s in order]
    if not idx_a or not idx_b:
        return None
    return min(abs(a - b) for a in idx_a for b in idx_b)


def _edge_id(source: str, target: str, method_version: str) -> str:
    return stable_id("graph-inference-edge", source, target, method_version)


def _symmetric_pair(node_a: str, node_b: str) -> tuple[str, str]:
    return (node_a, node_b) if node_a <= node_b else (node_b, node_a)


def _complements_stage_adjacency(
    cards: list[_AssetCard], methodology: dict[str, Any]
) -> list[dict[str, Any]]:
    order = {
        stage: i
        for i, stage in enumerate(methodology["workflow_stages"]["ordered"])
    }
    thresholds = methodology["thresholds"]
    min_tokens = int(thresholds["min_shared_task_tokens"])
    method_version = "workflow-stage-adjacency-v1"
    edges: list[dict[str, Any]] = []
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            a, b = cards[i], cards[j]
            if not a.stages or not b.stages:
                continue
            if set(a.stages) & set(b.stages):
                continue  # stages must be disjoint
            gap = _min_stage_gap(a.stages, b.stages, order)
            if gap != 1:
                continue
            shared = sorted(a.task_tokens & b.task_tokens)
            if len(shared) < min_tokens:
                continue
            source, target = _symmetric_pair(a.node_id, b.node_id)
            edges.append(
                {
                    "edge_id": _edge_id(source, target, method_version),
                    "source": source,
                    "target": target,
                    "edge_type": "complements",
                    "edge_class": "inference",
                    "method_version": method_version,
                    "edge_basis": "workflow-stage-adjacency-v1",
                    "evidence": {
                        "shared_task_tokens": shared,
                        "stage_pair": sorted(a.stages + b.stages),
                    },
                    "review_status": "candidate",
                }
            )
    edges.sort(key=lambda e: e["edge_id"])
    return edges


def _co_used(
    hub_root: Path, cards: list[_AssetCard], methodology: dict[str, Any]
) -> list[dict[str, Any]]:
    known_assets = {c.asset_id for c in cards}
    thresholds = methodology["thresholds"]
    min_repos = int(thresholds["min_distinct_repos_for_co_use"])
    method_version = "usage-cooccurrence-v1"
    # asset_id -> set of repo node ids
    repos_by_asset: dict[str, set[str]] = {}
    for row in _read_jsonl(hub_root / CENTRAL_USAGE_LEDGER):
        if str(row.get("status", "")) not in {"using", "watching"}:
            continue
        asset_id = str(row.get("asset_id", ""))
        if asset_id not in known_assets:
            continue
        repos_by_asset.setdefault(asset_id, set()).add(_repo_node(str(row.get("repo", ""))))
    edges: list[dict[str, Any]] = []
    asset_ids = sorted(repos_by_asset)
    for i in range(len(asset_ids)):
        for j in range(i + 1, len(asset_ids)):
            shared_repos = sorted(repos_by_asset[asset_ids[i]] & repos_by_asset[asset_ids[j]])
            if len(shared_repos) < min_repos:
                continue
            source, target = _symmetric_pair(
                _offering_node(asset_ids[i]), _offering_node(asset_ids[j])
            )
            edges.append(
                {
                    "edge_id": _edge_id(source, target, method_version),
                    "source": source,
                    "target": target,
                    "edge_type": "co_used_with",
                    "edge_class": "inference",
                    "method_version": method_version,
                    "edge_basis": "usage-cooccurrence-v1",
                    "evidence": {
                        "distinct_repo_count": len(shared_repos),
                        "repo_node_ids": shared_repos,
                    },
                    "review_status": "candidate",
                }
            )
    edges.sort(key=lambda e: e["edge_id"])
    return edges


def _enumerate_chains(
    cards: list[_AssetCard], min_len: int, max_len: int
) -> list[list[_AssetCard]]:
    """All maximal simple produces->consumes chains with node count in [min_len, max_len].

    A directed edge A->B exists iff A.produces & B.consumes is non-empty. A chain is
    kept only if it is not a contiguous subpath of a longer kept chain.
    """
    by_id = {c.asset_id: c for c in cards}
    adj: dict[str, list[str]] = {c.asset_id: [] for c in cards}
    for a in cards:
        for b in cards:
            if a.asset_id == b.asset_id:
                continue
            if a.produces & b.consumes:
                adj[a.asset_id].append(b.asset_id)
    for k in adj:
        adj[k].sort()

    paths: list[tuple[str, ...]] = []

    def dfs(path: list[str]) -> None:
        if len(path) >= 2:
            paths.append(tuple(path))
        if len(path) >= max_len:
            return
        for nxt in adj[path[-1]]:
            if nxt in path:
                continue
            path.append(nxt)
            dfs(path)
            path.pop()

    for start in sorted(adj):
        dfs([start])

    # keep length >= min_len
    candidate_tuples = sorted({p for p in paths if len(p) >= min_len})

    def is_contiguous_subpath(short: tuple[str, ...], long: tuple[str, ...]) -> bool:
        if len(short) >= len(long):
            return False
        n = len(short)
        return any(long[i : i + n] == short for i in range(len(long) - n + 1))

    maximal: list[tuple[str, ...]] = []
    for p in candidate_tuples:
        if any(is_contiguous_subpath(p, q) for q in candidate_tuples if q != p):
            continue
        maximal.append(p)
    maximal.sort()
    return [[by_id[aid] for aid in tup] for tup in maximal]


def _combinations(
    cards: list[_AssetCard], methodology: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (combination_nodes, member_of_edges)."""
    thresholds = methodology["thresholds"]
    min_len = int(thresholds["min_chain_length"])
    max_len = int(thresholds["max_chain_length"])
    method_version = "combination-candidate-v1"

    combos: dict[frozenset[str], dict[str, Any]] = {}

    # Rule combination-produces-consumes-chain-v1 (primary, engine_enabled).
    # Rule combination-stage-coverage-v1 is engine_enabled=false in v0.1: shared-token
    # stage coverage over-groups on common tokens (python, coding) and is reserved for
    # v0.2 with a specificity guard. The strong signal is the explicit artifact handoff.
    for chain in _enumerate_chains(cards, min_len, max_len):
        member_ids = [c.asset_id for c in chain]
        handoffs = []
        for a, b in zip(chain, chain[1:]):
            handoffs.append(
                {"from": a.asset_id, "to": b.asset_id, "artifact_kinds": sorted(a.produces & b.consumes)}
            )
        key = frozenset(member_ids)
        combos[key] = {
            "ordered_member_ids": member_ids,
            "discovery_basis": "combination-produces-consumes-chain-v1",
            "artifact_handoffs": handoffs,
            "chain_length": len(member_ids),
        }

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for key in sorted(combos, key=lambda k: sorted(k)):
        detail = combos[key]
        member_ids = detail["ordered_member_ids"]
        combo_id = "dad:combo:" + stable_id(
            "combination", *sorted(member_ids), detail["discovery_basis"]
        ).rsplit(":", 1)[-1][:12]
        combo_node_id = f"combination:{combo_id}"
        node = {
            "node_id": combo_node_id,
            "node_type": "combination_candidate",
            "combination_id": combo_id,
            "method_version": method_version,
            "combination_status": "hypothesized",
            "review_status": "candidate",
            **detail,
        }
        nodes.append(node)
        for member_id in member_ids:
            source = _offering_node(member_id)
            edges.append(
                {
                    "edge_id": _edge_id(source, combo_node_id, method_version),
                    "source": source,
                    "target": combo_node_id,
                    "edge_type": "member_of",
                    "edge_class": "inference",
                    "method_version": method_version,
                    "edge_basis": detail["discovery_basis"],
                    "evidence": {"combination_id": combo_id},
                    "review_status": "candidate",
                }
            )
    nodes.sort(key=lambda n: n["node_id"])
    edges.sort(key=lambda e: e["edge_id"])
    return nodes, edges


def infer_graph(hub_root: Path) -> dict[str, Any]:
    """Run all inference rules; return nodes, edges, and combination candidates."""
    methodology = load_inference_methodology(hub_root)
    cards = _build_cards(hub_root)
    complements = _complements_stage_adjacency(cards, methodology)
    co_used = _co_used(hub_root, cards, methodology)
    combo_nodes, member_edges = _combinations(cards, methodology)
    edges = sorted(
        [*complements, *co_used, *member_edges], key=lambda e: e["edge_id"]
    )
    return {
        "methodology_id": methodology["methodology_id"],
        "methodology_version": methodology["methodology_version"],
        "inference_nodes": combo_nodes,
        "inference_edges": edges,
        "edges_by_type": _count_by(edges, "edge_type"),
        "combination_count": len(combo_nodes),
        "asset_card_count": len(cards),
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row.get(key, ""))] = counts.get(str(row.get(key, "")), 0) + 1
    return counts


def write_inference_outputs(hub_root: Path) -> dict[str, Any]:
    """Write the inference report and append new combination candidates to the queue."""
    result = infer_graph(hub_root)
    report = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "methodology_id": result["methodology_id"],
        "methodology_version": result["methodology_version"],
        "asset_card_count": result["asset_card_count"],
        "combination_count": result["combination_count"],
        "edges_by_type": result["edges_by_type"],
        "inference_nodes": result["inference_nodes"],
        "inference_edges": result["inference_edges"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    report_path = hub_root / INFERENCE_REPORT_PATH
    write_json(report_path, report, allow_direct_fallback=True)

    # Append only combination candidates not already in the queue (by combination_id).
    queue_path = hub_root / COMBINATION_QUEUE_PATH
    existing = {str(row.get("combination_id", "")) for row in _read_jsonl(queue_path)}
    appended = 0
    new_rows = []
    for node in result["inference_nodes"]:
        if node["combination_id"] in existing:
            continue
        new_rows.append(
            {
                "combination_id": node["combination_id"],
                "first_seen_at": report["generated_at"],
                "method_version": node["method_version"],
                "discovery_basis": node["discovery_basis"],
                "ordered_member_ids": node["ordered_member_ids"],
                "combination_status": "hypothesized",
                "review_status": "candidate",
                "authority_boundary": AUTHORITY_BOUNDARY,
            }
        )
        appended += 1
    if new_rows:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        with queue_path.open("a", encoding="utf-8") as handle:
            for row in new_rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return {
        "report_path": str(report_path),
        "queue_path": str(queue_path),
        "combinations_total": result["combination_count"],
        "combinations_appended": appended,
        "edges_by_type": result["edges_by_type"],
    }
