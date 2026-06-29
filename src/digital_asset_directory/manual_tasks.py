from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .models import AlertRecord, AssetRecord
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "manual-task-priority-v0.1"

SEVERITY_WEIGHT = {
    "critical": 100.0,
    "high": 80.0,
    "medium": 55.0,
    "low": 20.0,
    "info": 5.0,
}

ALERT_TYPE_BONUS = {
    "synergy_candidate": 18.0,
    "missing_part_candidate": 14.0,
    "orphan_asset": 10.0,
    "stale_asset": 4.0,
}

ASSET_TYPE_BONUS = {
    "workflow": 12.0,
    "skill": 11.0,
    "agent": 11.0,
    "schema": 10.0,
    "test": 9.0,
    "code": 8.0,
    "algorithm": 8.0,
    "decision": 7.0,
    "lesson": 7.0,
    "document": 4.0,
    "dataset": 3.0,
    "media": 0.0,
}

NOISE_TERMS = (
    ".pytest-tmp-root",
    "pytest-of-",
    "_codex_worktrees",
    ".worktrees",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".gitkeep",
    "__init__.py",
)


def _score_range(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _path_text(asset: AssetRecord | None, alert: AlertRecord) -> str:
    evidence_path = str(alert.evidence.get("logical_path") or "")
    return evidence_path or (asset.logical_path if asset else "")


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def classify_alert_family(asset: AssetRecord | None, alert: AlertRecord) -> dict[str, Any]:
    path = _path_text(asset, alert)
    title = f"{alert.title} {asset.title if asset else ''}"
    haystack = f"{path} {title}".lower()

    if "04_digital_assett_directory" in haystack and "workflow" in haystack:
        return {
            "family_key": "dad_workflow_part_relationships",
            "family_label": "DAD workflow-part relationship cleanup",
            "review_posture": "DAD-owned metadata improvement; safe to fix in this repo.",
            "suggested_action": (
                "Connect DAD workflow-part code, registry, guidance, and evidence surfaces "
                "through explicit generated relationships or documentation links."
            ),
            "priority_bonus": 15.0,
            "source_boundary": "dad_owned",
        }
    if "logos-scripture-graph-repo" in haystack or "logos-" in haystack:
        if any(
            term in haystack
            for term in (
                "validate",
                "chunk",
                "usfm",
                "textual",
                "route",
                "wj_",
                "gold",
                "review_packet",
            )
        ):
            return {
                "family_key": "logos_route_validation_harness",
                "family_label": "Logos route-isolated validation and chunking harness",
                "review_posture": "Read-only source-owned candidate; generalize the workflow, not Bible facts.",
                "suggested_action": (
                    "Review as reusable validation, route-isolation, chunking, and gold/review "
                    "packet workflow evidence."
                ),
                "priority_bonus": 13.0,
                "source_boundary": "source_owned_read_only",
            }
        return {
            "family_key": "logos_general_workflow_assets",
            "family_label": "Logos general reusable workflow assets",
            "review_posture": "Read-only source-owned candidate.",
            "suggested_action": "Review for reusable governance, chunking, or learning-loop patterns.",
            "priority_bonus": 8.0,
            "source_boundary": "source_owned_read_only",
        }
    if "mock trial4.26" in haystack or "mock-trial" in haystack:
        return {
            "family_key": "mock_trial_simulation_validation",
            "family_label": "Mock Trial simulation and validation workflow",
            "review_posture": "Read-only while active; do not mutate Mock Trial from DAD.",
            "suggested_action": (
                "Review simulation validators and runners as candidate workflow parts and "
                "missing relationship metadata only."
            ),
            "priority_bonus": 10.0,
            "source_boundary": "active_source_read_only",
        }
    if "lawfirm_os" in haystack or "lawfirm-os" in haystack:
        return {
            "family_key": "lawfirm_governance_validation",
            "family_label": "LawFirm OS governance, validation, and learning workflows",
            "review_posture": "Source-owned candidate; use DAD public-safe metadata only.",
            "suggested_action": (
                "Review for reusable validation, governance, exception, and learning-loop "
                "patterns without importing private rows or source truth."
            ),
            "priority_bonus": 8.0,
            "source_boundary": "source_owned_read_only",
        }
    if "workflow-atlas" in haystack:
        return {
            "family_key": "workflow_atlas_skills",
            "family_label": "Workflow atlas skill candidates",
            "review_posture": "Source-owned candidate.",
            "suggested_action": "Review whether skill docs should be connected to capability/provider records.",
            "priority_bonus": 7.0,
            "source_boundary": "source_owned_read_only",
        }
    if "obsidian-knowledge-vault" in haystack:
        return {
            "family_key": "knowledge_vault_workflows",
            "family_label": "Knowledge vault workflow candidates",
            "review_posture": "Source-owned candidate; avoid private note import.",
            "suggested_action": "Review as metadata-only workflow evidence.",
            "priority_bonus": 5.0,
            "source_boundary": "source_owned_read_only",
        }
    parts = path.split("/")
    root = "/".join(parts[:3]) if len(parts) >= 3 else (path or "unknown")
    return {
        "family_key": f"general:{root}".lower().replace(" ", "_"),
        "family_label": root or "General alert family",
        "review_posture": "Generated candidate; review source boundary before acting.",
        "suggested_action": alert.recommended_action,
        "priority_bonus": 0.0,
        "source_boundary": "source_owned_review_first",
    }


def _noise_penalty(path: str) -> tuple[float, list[str]]:
    matched = [term for term in NOISE_TERMS if term.lower() in path.lower()]
    if not matched:
        return 0.0, []
    if any(term in {".gitkeep", "__init__.py"} for term in matched):
        return 18.0, matched
    return 25.0, matched


def prioritize_alert(
    alert: AlertRecord, asset: AssetRecord | None, *, scan_changed_count: int = 0
) -> dict[str, Any]:
    path = _path_text(asset, alert)
    family = classify_alert_family(asset, alert)
    value_score = _score_range(alert.evidence.get("value_score", asset.value_score if asset else 0))
    noise_penalty, noise_terms = _noise_penalty(path)
    severity_weight = SEVERITY_WEIGHT.get(alert.severity, 0.0)
    alert_bonus = ALERT_TYPE_BONUS.get(alert.alert_type, 0.0)
    asset_bonus = ASSET_TYPE_BONUS.get(asset.asset_type if asset else "", 0.0)
    score = (
        severity_weight * 0.40
        + value_score * 0.30
        + alert_bonus
        + asset_bonus
        + float(family["priority_bonus"])
        - noise_penalty
    )
    score = round(max(0.0, min(100.0, score)), 2)
    blockers: list[str] = []
    if family["source_boundary"] == "active_source_read_only":
        blockers.append("active_source_read_only")
    if family["source_boundary"].startswith("source_owned"):
        blockers.append("source_authority_review_required")
    if noise_terms:
        blockers.append("noise_or_marker_path")
    if scan_changed_count:
        blockers.append("scan_changed_during_run_caveat")
    if alert.alert_type == "stale_asset":
        blockers.append("freshness_review_required")
    recommended_manual_action = family["suggested_action"]
    if blockers:
        recommended_manual_action = f"{recommended_manual_action} Blockers: {', '.join(blockers)}."
    return {
        "alert_id": alert.alert_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "asset_id": alert.asset_ids[0] if alert.asset_ids else "",
        "asset_type": asset.asset_type if asset else "unknown",
        "value_score": value_score,
        "degree": alert.evidence.get("degree"),
        "logical_path": path,
        "priority_score": score,
        "priority_components": {
            "severity_weight": severity_weight,
            "value_score": value_score,
            "alert_type_bonus": alert_bonus,
            "asset_type_bonus": asset_bonus,
            "family_bonus": family["priority_bonus"],
            "noise_penalty": noise_penalty,
        },
        "family_key": family["family_key"],
        "family_label": family["family_label"],
        "review_posture": family["review_posture"],
        "source_boundary": family["source_boundary"],
        "blockers": blockers,
        "recommended_manual_action": recommended_manual_action,
        "candidate_only": True,
        "methodology_version": METHODOLOGY_VERSION,
    }


def rank_alerts_for_manual_review(
    alerts: list[AlertRecord],
    assets: list[AssetRecord],
    *,
    latest_scan_id: str | None = None,
    scan_changed_count: int = 0,
    limit: int = 25,
    family_limit: int = 12,
) -> dict[str, Any]:
    asset_by_id = {asset.asset_id: asset for asset in assets}
    scoped_alerts = [
        alert
        for alert in alerts
        if alert.status == "open" and (not latest_scan_id or alert.scan_id == latest_scan_id)
    ]
    scored = [
        prioritize_alert(
            alert,
            asset_by_id.get(alert.asset_ids[0]) if alert.asset_ids else None,
            scan_changed_count=scan_changed_count,
        )
        for alert in scoped_alerts
    ]
    ranked = sorted(
        scored,
        key=lambda item: (
            item["priority_score"],
            item["value_score"],
            item["severity"],
            item["title"],
        ),
        reverse=True,
    )
    family_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in ranked:
        family_groups[item["family_key"]].append(item)
    families = []
    for key, items in family_groups.items():
        highest = items[0]
        families.append(
            {
                "family_key": key,
                "family_label": highest["family_label"],
                "representative_path": highest["logical_path"],
                "representative_title": highest["title"],
                "alert_count": len(items),
                "max_priority_score": highest["priority_score"],
                "max_value_score": highest["value_score"],
                "source_boundary": highest["source_boundary"],
                "review_posture": highest["review_posture"],
                "recommended_manual_action": highest["recommended_manual_action"],
                "top_alert_ids": [item["alert_id"] for item in items[: min(5, len(items))]],
                "blockers": sorted({blocker for item in items for blocker in item["blockers"]}),
            }
        )
    families = sorted(
        families,
        key=lambda item: (item["max_priority_score"], item["alert_count"], item["family_label"]),
        reverse=True,
    )
    severity_counts = Counter(alert.severity for alert in scoped_alerts)
    type_counts = Counter(alert.alert_type for alert in scoped_alerts)
    return {
        "schema": "manual_task_queue.v1",
        "generated_at": utc_now(),
        "methodology_version": METHODOLOGY_VERSION,
        "candidate_only": True,
        "authority_boundary": (
            "Generated manual-review priorities only. They do not mutate source repositories, "
            "promote graph edges to truth, change current value scores, or mark roadmap phases complete."
        ),
        "formula": (
            "priority_score = 0.40*severity_weight + 0.30*value_score + "
            "alert_type_bonus + asset_type_bonus + family_bonus - noise_penalty; clamped 0..100"
        ),
        "scan_id": latest_scan_id,
        "scan_changed_during_count": scan_changed_count,
        "alert_count": len(scoped_alerts),
        "severity_counts": dict(sorted(severity_counts.items())),
        "alert_type_counts": dict(sorted(type_counts.items())),
        "ranked_alerts": ranked[:limit],
        "family_tasks": families[:family_limit],
        "literal_inbox_note": (
            "The generated alert inbox is sorted by severity and title. This report re-ranks "
            "for human review priority using value score, asset/workflow role, family context, "
            "source-boundary risk, and noise penalties."
        ),
    }


def _guidance_items(guidance: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = guidance.get(key) if isinstance(guidance, dict) else []
    return values if isinstance(values, list) else []


def summarize_workflow_guidance(guidance: dict[str, Any], *, limit: int = 25) -> dict[str, Any]:
    accepted = _guidance_items(guidance, "review_use_candidates")
    human_gated = _guidance_items(guidance, "human_gated_candidates")
    rejected = _guidance_items(guidance, "rejected_patterns")
    deferred = _guidance_items(guidance, "deferred_candidates")
    missing_dataflow = [
        item
        for item in accepted
        if str(item.get("dataflow_completeness") or "").startswith("missing")
        or item.get("dataflow_completeness") == "unsure"
    ]
    return {
        "schema": "workflow_part_manual_task_summary.v1",
        "source_methodology": guidance.get("methodology_version"),
        "summary": guidance.get("summary", {}),
        "review_use_examples": accepted[:limit],
        "missing_dataflow_tasks": missing_dataflow[:limit],
        "human_gated_tasks": human_gated[:limit],
        "deferred_tasks": deferred[:limit],
        "false_positive_patterns": rejected[:limit],
        "manual_use_policy": guidance.get("manual_use_policy", {}),
        "authority_boundary": guidance.get("authority_boundary", ""),
        "danger_if_misapplied": guidance.get("danger_if_misapplied", ""),
    }


def _markdown_table(items: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not items:
        return ["No items."]
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for item in items:
        values = []
        for _, key in columns:
            value = item.get(key, "")
            if isinstance(value, float):
                text = f"{value:.2f}"
            elif isinstance(value, list):
                text = ", ".join(str(part) for part in value) or ""
            else:
                text = str(value)
            text = text.replace("\n", " ").replace("|", "\\|")
            if key in {"logical_path", "representative_path"} and text:
                text = f"`{text}`"
            elif key in {"sample_id", "asset_type", "source_boundary", "dataflow_completeness"} and text:
                text = f"`{text}`"
            values.append(text)
        lines.append("| " + " | ".join(values) + " |")
    return lines


def manual_task_queue_markdown(result: dict[str, Any]) -> str:
    workflow = result["workflow_part_guidance"]
    lines = [
        "# Manual Task Queue",
        "",
        f"Generated at: `{result['generated_at']}`",
        f"Methodology: `{result['methodology_version']}`",
        "",
        result["authority_boundary"],
        "",
        "## Why This Order",
        "",
        f"- Formula: `{result['formula']}`",
        "- Alerts are candidate routing signals; graph degree, similarity, and score do not prove source truth.",
        "- Repeated families are grouped before human review so one cluster does not consume the whole budget.",
        "- Source-owned and active repos stay read-only unless a human separately authorizes mutation.",
        "- Workflow-part examples are manual review context only; assembly requires declared dataflow and gates.",
        "",
        "## Local Research Support",
        "",
        "- `docs/ORPHAN_ACTIVATION_AND_SYNERGY_RADAR.md`: orphan alerts mean hidden or under-described assets, not emergencies.",
        "- `docs/KNOWLEDGE_GRAPH_MODEL.md`: graph edges are candidate evidence and do not transfer authority.",
        "- `docs/LOGOS_REUSABLE_ASSET_FINDINGS.md`: Logos chunking and validation generalize as route-isolated evaluation patterns.",
        "- `roadmap/evidence/workflow-part-usage-guidance.md`: reviewed workflow parts are usable only as manual review context unless gates are satisfied.",
        "- `roadmap/evidence/claude-workflow-composition-red-team.md`: reuse existing vocabulary and avoid over-building the ontology.",
        "- `roadmap/evidence/claude-background-connection-radar-review.md`: gates-before-score, family dedup, and privacy-first evidence reduce false positives.",
        "",
        "## Scan Caveats",
        "",
        f"- Scan id: `{result.get('scan_id')}`",
        f"- Alerts considered: **{result['alert_count']}**",
        f"- Severity counts: `{result['severity_counts']}`",
        f"- Alert type counts: `{result['alert_type_counts']}`",
        f"- Changed during scan: **{result['scan_changed_during_count']}**",
        f"- Inbox order caveat: {result['literal_inbox_note']}",
        "",
        "## Top Alert Families",
        "",
    ]
    lines.extend(
        _markdown_table(
            result["family_tasks"],
            [
                ("family", "family_label"),
                ("alerts", "alert_count"),
                ("priority", "max_priority_score"),
                ("boundary", "source_boundary"),
                ("representative", "representative_path"),
                ("action", "recommended_manual_action"),
            ],
        )
    )
    lines.extend(["", "## Top Alert Items", ""])
    lines.extend(
        _markdown_table(
            result["ranked_alerts"],
            [
                ("score", "priority_score"),
                ("severity", "severity"),
                ("type", "alert_type"),
                ("asset type", "asset_type"),
                ("value", "value_score"),
                ("family", "family_label"),
                ("path", "logical_path"),
                ("action", "recommended_manual_action"),
            ],
        )
    )
    lines.extend(["", "## Workflow Parts: Review-Use Examples", ""])
    lines.extend(
        _markdown_table(
            workflow["review_use_examples"],
            [
                ("sample", "sample_id"),
                ("part", "part_type"),
                ("pattern", "asset_pattern_id"),
                ("dataflow", "dataflow_completeness"),
                ("path", "representative_path"),
                ("action", "action"),
            ],
        )
    )
    lines.extend(["", "## Workflow Parts: Missing Dataflow Before Assembly", ""])
    lines.extend(
        _markdown_table(
            workflow["missing_dataflow_tasks"],
            [
                ("sample", "sample_id"),
                ("part", "part_type"),
                ("dataflow", "dataflow_completeness"),
                ("path", "representative_path"),
                ("missing note", "missing_dataflow_note"),
            ],
        )
    )
    lines.extend(["", "## Workflow Parts: Human-Gated", ""])
    lines.extend(
        _markdown_table(
            workflow["human_gated_tasks"],
            [
                ("sample", "sample_id"),
                ("part", "part_type"),
                ("pattern", "asset_pattern_id"),
                ("dataflow", "dataflow_completeness"),
                ("path", "representative_path"),
                ("note", "note"),
            ],
        )
    )
    lines.extend(["", "## Workflow Parts: False-Positive Patterns", ""])
    lines.extend(
        _markdown_table(
            workflow["false_positive_patterns"],
            [
                ("sample", "sample_id"),
                ("part", "part_type"),
                ("path", "representative_path"),
                ("reason", "false_positive_reason"),
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Red Team And Premortem",
            "",
            "- False positive: DAD could over-prioritize repeated validators from one repo. Guard: family grouping and representative tasks.",
            "- Authority failure: a source-owned alert could be treated as permission to edit. Guard: source-boundary blockers and read-only posture.",
            "- Workflow assembly risk: useful parts with missing inputs, outputs, or side effects could be installed unsafely. Guard: missing-dataflow section blocks assembly.",
            "- Privacy/public risk: private legal or source-specific material could leak into DAD evidence. Guard: metadata-only paths and no raw source content in this report.",
            "- Score overtrust: priority score is review order, not value truth. Guard: methodology label and candidate-only boundary.",
            "- Stale snapshot: files changed during the scan. Guard: treat this as operational triage, not frozen acceptance evidence.",
            "",
            "## Completion Posture",
            "",
            "This completes the manual review triage step by converting the alert and workflow-part queues into bounded, reviewable tasks with reasons and red-team guards. It does not complete source-repo fixes, workflow assembly, automatic preflight surfacing, or cross-repo mutation.",
            "",
        ]
    )
    return "\n".join(lines)


def build_manual_task_queue(
    alerts: list[AlertRecord],
    assets: list[AssetRecord],
    workflow_guidance: dict[str, Any],
    *,
    latest_scan_id: str | None = None,
    scan_changed_count: int = 0,
    limit: int = 25,
    family_limit: int = 12,
) -> dict[str, Any]:
    alert_result = rank_alerts_for_manual_review(
        alerts,
        assets,
        latest_scan_id=latest_scan_id,
        scan_changed_count=scan_changed_count,
        limit=limit,
        family_limit=family_limit,
    )
    workflow_summary = summarize_workflow_guidance(workflow_guidance, limit=limit)
    return {
        **alert_result,
        "workflow_part_guidance": workflow_summary,
        "review_status": "generated_candidate",
    }


def write_manual_task_queue(
    repo_root: Path,
    alerts: list[AlertRecord],
    assets: list[AssetRecord],
    workflow_guidance: dict[str, Any],
    *,
    latest_scan_id: str | None = None,
    scan_changed_count: int = 0,
    limit: int = 25,
    family_limit: int = 12,
) -> dict[str, Any]:
    result = build_manual_task_queue(
        alerts,
        assets,
        workflow_guidance,
        latest_scan_id=latest_scan_id,
        scan_changed_count=scan_changed_count,
        limit=limit,
        family_limit=family_limit,
    )
    report = repo_root / "processed" / "reports" / "manual_task_queue.md"
    payload = repo_root / "processed" / "reports" / "manual_task_queue.json"
    atomic_write_text(report, manual_task_queue_markdown(result) + "\n")
    atomic_write_text(payload, json_dumps(result, pretty=True) + "\n")
    return {
        "report": str(report),
        "payload": str(payload),
        "alert_count": result["alert_count"],
        "family_task_count": len(result["family_tasks"]),
        "ranked_alert_count": len(result["ranked_alerts"]),
        "workflow_review_use_count": len(result["workflow_part_guidance"]["review_use_examples"]),
        "workflow_missing_dataflow_count": len(
            result["workflow_part_guidance"]["missing_dataflow_tasks"]
        ),
        "workflow_human_gated_count": len(result["workflow_part_guidance"]["human_gated_tasks"]),
        "candidate_only": True,
        "methodology_version": METHODOLOGY_VERSION,
    }
