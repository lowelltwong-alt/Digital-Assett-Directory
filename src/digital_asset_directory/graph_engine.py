from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable

import networkx as nx

from .ids import edge_id
from .models import AssetRecord, EdgeRecord
from .utils import idf_weighted_cosine, idf_weights, rarest_tokens, tokens, utc_now


def _asset_tokens(asset: AssetRecord) -> set[str]:
    metadata_tokens = set(asset.metadata.get("text_tokens", []))
    return (
        tokens(f"{asset.title} {asset.description} {asset.logical_path}")
        | set(asset.tags)
        | set(asset.capabilities)
        | set(asset.needs)
        | set(asset.outcomes)
        | metadata_tokens
    )


def build_edges(
    assets: list[AssetRecord], scan_id: str, threshold: float = 0.34, max_related: int = 20
) -> list[EdgeRecord]:
    edges: dict[str, EdgeRecord] = {}
    now = utc_now()
    by_id = {asset.asset_id: asset for asset in assets}
    for asset in assets:
        if asset.parent_asset_id and asset.parent_asset_id in by_id:
            e = EdgeRecord(
                edge_id=edge_id("contains", asset.parent_asset_id, asset.asset_id),
                edge_type="contains",
                source_asset_id=asset.parent_asset_id,
                target_asset_id=asset.asset_id,
                method="source_hierarchy",
                confidence=1.0,
                evidence={"logical_path": asset.logical_path},
                created_at=now,
                scan_id=scan_id,
                review_status="reviewed",
            )
            edges[e.edge_id] = e

    token_map = {asset.asset_id: _asset_tokens(asset) for asset in assets}
    weights = idf_weights(token_map.values())
    candidate_token_map = {
        aid: set(rarest_tokens(toks, weights, 500)) for aid, toks in token_map.items()
    }
    postings: dict[str, list[str]] = defaultdict(list)
    for aid, toks in candidate_token_map.items():
        for token in sorted(toks):
            postings[token].append(aid)
    candidates: set[tuple[str, str]] = set()
    for ids in postings.values():
        if len(ids) > 100:
            continue
        for pair_left, pair_right in combinations(sorted(set(ids)), 2):
            candidates.add((pair_left, pair_right))

    per_asset: dict[str, list[tuple[float, EdgeRecord]]] = defaultdict(list)
    for left_id, right_id in candidates:
        left, right = by_id[left_id], by_id[right_id]
        if left.parent_asset_id == right.asset_id or right.parent_asset_id == left.asset_id:
            continue
        similarity = idf_weighted_cosine(
            candidate_token_map[left_id], candidate_token_map[right_id], weights
        )
        shared = rarest_tokens(
            candidate_token_map[left_id] & candidate_token_map[right_id], weights, 30
        )
        if similarity >= threshold:
            e = EdgeRecord(
                edge_id=edge_id("related_to", left_id, right_id),
                edge_type="related_to",
                source_asset_id=left_id,
                target_asset_id=right_id,
                method="idf_weighted_token_cosine",
                confidence=round(min(0.95, similarity), 4),
                evidence={
                    "similarity": round(similarity, 4),
                    "shared_terms": shared,
                    "token_weighting": "idf",
                    "candidate_tokens": "rarest_500_per_asset",
                },
                created_at=now,
                scan_id=scan_id,
            )
            per_asset[left_id].append((similarity, e))
            per_asset[right_id].append((similarity, e))
        left_covers = sorted(set(left.capabilities) & set(right.needs))
        right_covers = sorted(set(right.capabilities) & set(left.needs))
        if left_covers:
            e = EdgeRecord(
                edge_id=edge_id("satisfies_need", left_id, right_id),
                edge_type="satisfies_need",
                source_asset_id=left_id,
                target_asset_id=right_id,
                method="capability_need_match",
                confidence=min(0.95, 0.60 + 0.08 * len(left_covers)),
                evidence={"matched": left_covers},
                created_at=now,
                scan_id=scan_id,
            )
            edges[e.edge_id] = e
        if right_covers:
            e = EdgeRecord(
                edge_id=edge_id("satisfies_need", right_id, left_id),
                edge_type="satisfies_need",
                source_asset_id=right_id,
                target_asset_id=left_id,
                method="capability_need_match",
                confidence=min(0.95, 0.60 + 0.08 * len(right_covers)),
                evidence={"matched": right_covers},
                created_at=now,
                scan_id=scan_id,
            )
            edges[e.edge_id] = e

    selected_ids: set[str] = set()
    for aid, ranked in per_asset.items():
        for _, edge in sorted(ranked, key=lambda item: item[0], reverse=True)[:max_related]:
            selected_ids.add(edge.edge_id)
    for ranked in per_asset.values():
        for _, edge in ranked:
            if edge.edge_id in selected_ids:
                edges[edge.edge_id] = edge
    return sorted(edges.values(), key=lambda e: (e.edge_type, e.source_asset_id, e.target_asset_id))


def to_networkx(assets: Iterable[AssetRecord], edges: Iterable[EdgeRecord]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for asset in assets:
        graph.add_node(
            asset.asset_id,
            title=asset.title,
            asset_type=asset.asset_type,
            value_score=asset.value_score,
            freshness_status=asset.freshness_status,
        )
    for edge in edges:
        graph.add_edge(
            edge.source_asset_id,
            edge.target_asset_id,
            edge_type=edge.edge_type,
            confidence=edge.confidence,
        )
    return graph


def graph_export(assets: list[AssetRecord], edges: list[EdgeRecord]) -> dict:
    return {
        "directed": True,
        "multigraph": False,
        "nodes": [
            {
                "id": a.asset_id,
                "title": a.title,
                "asset_type": a.asset_type,
                "logical_path": a.logical_path,
                "value_score": a.value_score,
                "freshness_status": a.freshness_status,
                "metadata_fingerprint": a.metadata_fingerprint,
                "has_content_sha256": bool(a.content_sha256),
            }
            for a in assets
        ],
        "edges": [e.model_dump(mode="json") for e in edges],
    }
