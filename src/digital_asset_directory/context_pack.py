from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import AssetRecord, EdgeRecord, AlertRecord
from .utils import idf_weighted_cosine, idf_weights, rarest_tokens, tokens, utc_now, write_json, atomic_write_text


def _asset_tokens(asset: AssetRecord) -> set[str]:
    return (
        tokens(f"{asset.title} {asset.description} {asset.logical_path}")
        | set(asset.tags)
        | set(asset.capabilities)
        | set(asset.needs)
        | set(asset.outcomes)
        | set(asset.metadata.get("text_tokens", []))
    )


def rank_assets(
    query: str, assets: list[AssetRecord]
) -> list[tuple[float, AssetRecord, list[str]]]:
    q = tokens(query)
    token_map = {asset.asset_id: _asset_tokens(asset) for asset in assets}
    weights = idf_weights([*token_map.values(), q])
    ranked = []
    for asset in assets:
        hay = token_map[asset.asset_id]
        overlap = rarest_tokens(q & hay, weights, 30)
        lexical_score = idf_weighted_cosine(q, hay, weights)
        score = lexical_score * 0.75 + (asset.value_score / 100) * 0.25
        if overlap or query.casefold() in asset.title.casefold():
            ranked.append((score, asset, overlap))
    return sorted(ranked, key=lambda row: row[0], reverse=True)


def build_context_pack(
    query: str,
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    alerts: list[AlertRecord],
    limit: int = 20,
) -> dict[str, Any]:
    ranked = rank_assets(query, assets)[:limit]
    ids = {asset.asset_id for _, asset, _ in ranked}
    relevant_edges = [
        edge for edge in edges if edge.source_asset_id in ids and edge.target_asset_id in ids
    ]
    relevant_alerts = [alert for alert in alerts if ids.intersection(alert.asset_ids)]
    return {
        "schema_version": "0.1.0",
        "created_at": utc_now(),
        "query": query,
        "confirmed_scope": "Generated from the current local catalog; source repos remain authoritative.",
        "assets": [
            {
                "rank_score": round(score, 4),
                "matched_terms": matched,
                **asset.model_dump(mode="json"),
            }
            for score, asset, matched in ranked
        ],
        "edges": [edge.model_dump(mode="json") for edge in relevant_edges],
        "alerts": [alert.model_dump(mode="json") for alert in relevant_alerts],
        "usage_rules": [
            "Treat generated relationships as candidates.",
            "Open source assets before relying on a claim.",
            "Preserve source-repo authority and sensitivity boundaries.",
        ],
    }


def write_context_pack(repo_root: Path, pack: dict[str, Any], name: str) -> tuple[Path, Path]:
    json_path = repo_root / "processed" / "context_packs" / f"{name}.json"
    md_path = repo_root / "processed" / "context_packs" / f"{name}.md"
    write_json(json_path, pack)
    lines = [
        f"# Context Pack: {pack['query']}",
        "",
        f"Generated: {pack['created_at']}",
        "",
        "## Assets",
    ]
    for index, asset in enumerate(pack["assets"], 1):
        lines.extend(
            [
                f"### {index}. {asset['title']}",
                f"- Path: `{asset['logical_path']}`",
                f"- Type: `{asset['asset_type']}`",
                f"- Value: `{asset['value_score']}`",
                f"- Match: `{asset['rank_score']}` ({', '.join(asset['matched_terms'])})",
                f"- Description: {asset.get('description', '')}",
                "",
            ]
        )
    lines.extend(["## Candidate relationships", ""])
    for edge in pack["edges"]:
        lines.append(
            f"- `{edge['edge_type']}`: `{edge['source_asset_id']}` → `{edge['target_asset_id']}` ({edge['confidence']})"
        )
    lines.extend(["", "## Open alerts", ""])
    for alert in pack["alerts"]:
        lines.append(f"- **{alert['severity']}** — {alert['title']}: {alert['recommended_action']}")
    atomic_write_text(md_path, "\n".join(lines) + "\n")
    return json_path, md_path
