from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import traceback

from .config import AppConfig
from .database import CatalogDB
from .github_scan import scan_github_source
from .graph_engine import build_edges, graph_export
from .ids import scan_id as new_scan_id
from .identity_layers import build_identity_layers
from .local_scan import scan_local_source
from .radars import activation_triggers, detect_synergies, generate_alerts
from .recommendations import recommend_skills_and_agents
from .scoring import load_scoring, score_asset
from .models import AssetRecord
from .utils import append_jsonl, atomic_write_text, safe_relative, utc_now, write_json, write_jsonl


def _append_scan_audit(repo_root: Path, event_type: str, payload: dict[str, Any]) -> None:
    created_at = payload.get("created_at") or utc_now()
    append_jsonl(
        repo_root / "audit" / "events" / f"{created_at[:10]}.jsonl",
        {"event_type": event_type, "created_at": created_at, **payload},
    )


def _write_raw_scan_observations(
    repo_root: Path, sid: str, source_kind: str, assets: list[AssetRecord]
) -> list[str]:
    if not assets:
        return []
    path = repo_root / "raw" / source_kind / f"{sid.replace(':', '-')}.jsonl"
    observed_at = utc_now()
    for asset in assets:
        append_jsonl(
            path,
            {
                "schema_version": "0.1.0",
                "observation_type": "normalized_asset_candidate",
                "scan_id": sid,
                "observed_at": observed_at,
                "source_id": asset.source_id,
                "source_kind": asset.source_kind,
                "asset_id": asset.asset_id,
                "revision_id": asset.revision_id,
                "logical_path": asset.logical_path,
                "candidate_asset": asset.model_dump(mode="json"),
                "authority_note": "Raw scan observation; source repository remains authoritative.",
            },
        )
    return [safe_relative(path, repo_root)]


def run_scan(
    config: AppConfig, *, local: bool = True, github: bool = True, max_files: int | None = None
) -> dict[str, Any]:
    sid = new_scan_id()
    started = utc_now()
    assets: list[AssetRecord] = []
    errors: list[dict[str, str]] = []
    raw_observation_files: list[str] = []
    scoring = load_scoring(config.repo_root)
    _append_scan_audit(
        config.repo_root,
        "scan_started",
        {
            "scan_id": sid,
            "created_at": started,
            "local_enabled": local,
            "github_enabled": github,
            "max_files": max_files,
        },
    )
    with CatalogDB(config.database_path) as db:
        db.start_scan(sid, {"local": local, "github": github, "max_files": max_files})
        try:
            if local:
                for local_source in config.local_sources:
                    if not local_source.enabled:
                        continue
                    if not local_source.path.exists():
                        errors.append(
                            {
                                "source": local_source.id,
                                "error": f"Path not found: {local_source.path}",
                            }
                        )
                        continue
                    try:
                        discovered, _ = scan_local_source(
                            local_source, config.settings, scoring, max_files=max_files
                        )
                        raw_observation_files.extend(
                            _write_raw_scan_observations(
                                config.repo_root, sid, "local", discovered
                            )
                        )
                        assets.extend(discovered)
                    except Exception as exc:
                        errors.append(
                            {
                                "source": local_source.id,
                                "error": str(exc),
                                "trace": traceback.format_exc(limit=3),
                            }
                        )
            if github:
                for github_source in config.github_sources:
                    if not github_source.enabled:
                        continue
                    try:
                        discovered = scan_github_source(
                            github_source, config.settings, scoring, max_files=max_files
                        )
                        raw_observation_files.extend(
                            _write_raw_scan_observations(
                                config.repo_root, sid, "github", discovered
                            )
                        )
                        assets.extend(discovered)
                    except Exception as exc:
                        errors.append(
                            {
                                "source": github_source.id,
                                "error": str(exc),
                                "trace": traceback.format_exc(limit=3),
                            }
                        )
            unique = {asset.asset_id: asset for asset in assets}
            assets = list(unique.values())
            chunks, duplicate_clusters, deltas, identity_edges = build_identity_layers(assets, sid)
            # Re-score with duplicate context so `uniqueness` reflects cluster membership
            # instead of a constant. Identity layers are already built, so this only
            # updates value_score/value_components.
            duplicate_counts: dict[str, int] = {}
            for cluster in duplicate_clusters:
                cluster_size = len(cluster.asset_ids)
                for member_id in cluster.asset_ids:
                    duplicate_counts[member_id] = max(
                        duplicate_counts.get(member_id, 1), cluster_size
                    )
            for asset in assets:
                score_asset(asset, scoring, duplicate_counts)
            graph_edges = build_edges(
                assets,
                sid,
                config.settings.related_similarity_threshold,
                config.settings.max_related_edges_per_asset,
            )
            edge_by_id = {edge.edge_id: edge for edge in [*graph_edges, *identity_edges]}
            edges = sorted(
                edge_by_id.values(),
                key=lambda e: (e.edge_type, e.source_asset_id, e.target_asset_id),
            )
            duplicate_asset_pairs = {
                tuple(sorted((edge.source_asset_id, edge.target_asset_id)))
                for edge in identity_edges
                if edge.edge_type in {"exact_duplicate_of", "near_duplicate_of"}
            }
            synergies = detect_synergies(assets, duplicate_asset_pairs=duplicate_asset_pairs)
            triggers = activation_triggers(assets)
            recommendations = recommend_skills_and_agents(
                assets, config.settings.skill_candidate_repeat_threshold
            )
            changed_during_scan_count = sum(
                1 for asset in assets if asset.metadata.get("changed_during_scan") is True
            )
            alerts = generate_alerts(
                assets,
                edges,
                synergies,
                triggers,
                sid,
                config.settings.orphan_degree_threshold,
                config.settings.synergy_alert_threshold,
                config.settings.high_value_threshold,
            )
            db.upsert_assets(assets)
            db.replace_scan_edges(sid, edges)
            db.replace_scan_identity_records(sid, chunks, duplicate_clusters, deltas)
            db.upsert_synergies(synergies)
            db.upsert_triggers(triggers)
            db.upsert_alerts(alerts)
            summary: dict[str, Any] = {
                "scan_id": sid,
                "started_at": started,
                "completed_at": utc_now(),
                "status": "completed_with_errors" if errors else "complete",
                "asset_count": len(assets),
                "edge_count": len(edges),
                "chunk_count": len(chunks),
                "duplicate_cluster_count": len(duplicate_clusters),
                "delta_count": len(deltas),
                "synergy_count": len(synergies),
                "activation_trigger_count": len(triggers),
                "alert_count": len(alerts),
                "capability_recommendation_count": len(recommendations),
                "changed_during_scan_count": changed_during_scan_count,
                "raw_observation_files": sorted(set(raw_observation_files)),
                "asset_types": dict(Counter(a.asset_type for a in assets)),
                "sources": dict(Counter(a.source_id for a in assets)),
                "errors": errors,
                "source_files_mutated": False,
            }
            db.complete_scan(sid, str(summary["status"]), summary)
            _append_scan_audit(
                config.repo_root,
                "scan_completed",
                {
                    "scan_id": sid,
                    "created_at": summary["completed_at"],
                    "status": summary["status"],
                    "asset_count": summary["asset_count"],
                    "edge_count": summary["edge_count"],
                    "alert_count": summary["alert_count"],
                    "changed_during_scan_count": summary["changed_during_scan_count"],
                    "error_count": len(errors),
                    "raw_observation_files": summary["raw_observation_files"],
                    "source_files_mutated": summary["source_files_mutated"],
                },
            )
        except Exception as exc:
            summary = {
                "scan_id": sid,
                "started_at": started,
                "completed_at": utc_now(),
                "status": "failed",
                "error": str(exc),
                "raw_observation_files": sorted(set(raw_observation_files)),
            }
            db.complete_scan(sid, "failed", summary)
            _append_scan_audit(
                config.repo_root,
                "scan_failed",
                {
                    "scan_id": sid,
                    "created_at": summary["completed_at"],
                    "status": "failed",
                    "error": str(exc),
                    "raw_observation_files": summary["raw_observation_files"],
                },
            )
            raise
    export_outputs(
        config.repo_root,
        assets,
        edges,
        chunks,
        duplicate_clusters,
        deltas,
        synergies,
        triggers,
        alerts,
        recommendations,
        summary,
    )
    return summary


def export_outputs(
    repo_root: Path,
    assets,
    edges,
    chunks,
    duplicate_clusters,
    deltas,
    synergies,
    triggers,
    alerts,
    recommendations,
    summary,
) -> None:
    write_jsonl(
        repo_root / "processed" / "catalog" / "assets.jsonl",
        [a.model_dump(mode="json") for a in assets],
    )
    write_jsonl(
        repo_root / "processed" / "graph" / "edges.jsonl",
        [e.model_dump(mode="json") for e in edges],
    )
    write_json(repo_root / "processed" / "graph" / "graph.json", graph_export(assets, edges))
    write_jsonl(
        repo_root / "processed" / "catalog" / "chunks.jsonl",
        [c.model_dump(mode="json") for c in chunks],
    )
    write_jsonl(
        repo_root / "processed" / "graph" / "duplicate_clusters.jsonl",
        [c.model_dump(mode="json") for c in duplicate_clusters],
    )
    write_jsonl(
        repo_root / "processed" / "graph" / "deltas.jsonl",
        [d.model_dump(mode="json") for d in deltas],
    )
    write_jsonl(
        repo_root / "processed" / "graph" / "synergies.jsonl",
        [s.model_dump(mode="json") for s in synergies],
    )
    write_jsonl(
        repo_root / "processed" / "graph" / "activation_triggers.jsonl",
        [t.model_dump(mode="json") for t in triggers],
    )
    write_jsonl(
        repo_root / "processed" / "reports" / "capability_recommendations.jsonl",
        [record.model_dump(mode="json") for record in recommendations],
    )
    write_jsonl(
        repo_root / "processed" / "alerts" / "alerts.jsonl",
        [a.model_dump(mode="json") for a in alerts],
    )
    write_json(repo_root / "processed" / "reports" / "scan_summary.json", summary)
    lines = [
        "# Digital Asset Directory Scan Summary",
        "",
        f"- Scan: `{summary['scan_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Assets: **{summary['asset_count']}**",
        f"- Edges: **{summary['edge_count']}**",
        f"- Chunks: **{summary.get('chunk_count', 0)}**",
        f"- Duplicate clusters: **{summary.get('duplicate_cluster_count', 0)}**",
        f"- Delta records: **{summary.get('delta_count', 0)}**",
        f"- Synergies: **{summary['synergy_count']}**",
        f"- Activation triggers: **{summary['activation_trigger_count']}**",
        f"- Alerts: **{summary['alert_count']}**",
        f"- Source files mutated: **{summary['source_files_mutated']}**",
        f"- Changed during scan: **{summary.get('changed_during_scan_count', 0)}**",
        "",
        "## Errors",
        "",
    ]
    lines.extend(
        [f"- `{e['source']}`: {e['error']}" for e in summary.get("errors", [])] or ["- None"]
    )
    atomic_write_text(
        repo_root / "processed" / "reports" / "scan_summary.md", "\n".join(lines) + "\n"
    )
    identity_lines = [
        "# Identity Layers",
        "",
        "Generated candidate records only. Hashes prove bounded identity facts; graph and delta records remain reviewable evidence.",
        "",
        f"- Assets: **{summary['asset_count']}**",
        f"- Chunks: **{summary.get('chunk_count', 0)}**",
        f"- Duplicate clusters: **{summary.get('duplicate_cluster_count', 0)}**",
        f"- Delta records: **{summary.get('delta_count', 0)}**",
        "",
        "## Layers",
        "",
        "- `metadata_fingerprint`: fast observable-state fingerprint for broad scans and change detection.",
        "- `content_sha256`: exact content identity only when bytes were read safely.",
        "- `chunks.jsonl`: deterministic text or metadata chunks per observed revision.",
        "- `duplicate_clusters.jsonl`: exact-content or near-duplicate candidate clusters.",
        "- `deltas.jsonl`: bounded pairwise exact/near duplicate delta records.",
        "",
        "## Authority",
        "",
        "Source repositories remain authoritative. Generated duplicate, near-duplicate, and delta records do not select a canonical asset or delete any duplicate.",
        "",
    ]
    atomic_write_text(
        repo_root / "processed" / "reports" / "identity_layers.md",
        "\n".join(identity_lines),
    )
    alert_lines = ["# Alert Inbox", "", "Generated candidate alerts. Review before acting.", ""]
    for alert in alerts:
        alert_lines.extend(
            [
                f"## [{alert.severity.upper()}] {alert.title}",
                alert.description,
                "",
                f"**Action:** {alert.recommended_action}",
                "",
            ]
        )
    atomic_write_text(
        repo_root / "processed" / "alerts" / "alert_inbox.md", "\n".join(alert_lines) + "\n"
    )
    recommendation_lines = [
        "# Skill, Agent, and Research Recommendations",
        "",
        "Generated candidates only. Review evidence, risk, and authority boundaries before implementation.",
        "",
    ]
    for record in recommendations:
        recommendation_lines.extend(
            [
                f"## {record.name}",
                f"- Kind: `{record.kind}`",
                f"- Confidence: `{record.confidence}`",
                f"- Risk: `{record.risk}`",
                f"- Capabilities: {', '.join(record.capabilities) or 'none'}",
                f"- Missing: {', '.join(record.missing_capabilities) or 'none'}",
                f"- Roles: {', '.join(record.suggested_roles)}",
                f"- Rationale: {record.rationale}",
                "",
            ]
        )
    atomic_write_text(
        repo_root / "processed" / "reports" / "capability_recommendations.md",
        "\n".join(recommendation_lines) + "\n",
    )


def catalog_status(config: AppConfig) -> dict[str, Any]:
    if not config.database_path.exists():
        return {
            "database": str(config.database_path),
            "exists": False,
            "assets": 0,
            "edges": 0,
            "alerts": 0,
            "latest_scan": None,
        }
    with CatalogDB(config.database_path) as db:
        return {
            "database": str(config.database_path),
            "exists": True,
            "assets": len(db.assets()),
            "edges": len(db.edges()),
            "alerts": len(db.alerts(open_only=True)),
            "latest_scan": db.latest_scan(),
        }
