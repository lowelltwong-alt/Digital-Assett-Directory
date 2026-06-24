from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from .models import AlertRecord, AssetRecord, SynergyRecord
from .utils import atomic_write_text, utc_now


def _asset_context(asset: AssetRecord) -> str:
    return (
        f"{asset.title} [{asset.asset_type}] `{asset.logical_path}` "
        f"(score {asset.value_score}, {asset.lifecycle_state}/{asset.freshness_status}, "
        f"confidence {asset.confidence})"
    )


def _value_band(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _component_averages(assets: list[AssetRecord]) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for asset in assets:
        for component, value in asset.value_components.items():
            values[component].append(float(value))
    return {
        component: round(mean(component_values), 2)
        for component, component_values in values.items()
    }


def scoring_calibration_markdown(assets: list[AssetRecord], sample_size: int = 25) -> str:
    generated_at = utc_now()
    sorted_assets = sorted(
        assets, key=lambda asset: (asset.value_score, asset.asset_id), reverse=True
    )
    low_assets = sorted(assets, key=lambda asset: (asset.value_score, asset.asset_id))
    band_counts = Counter(_value_band(asset.value_score) for asset in assets)
    type_counts = Counter(asset.asset_type for asset in assets)
    freshness_counts = Counter(asset.freshness_status for asset in assets)
    component_averages = _component_averages(assets)

    lines = [
        "# Scoring Calibration Review",
        "",
        "Generated candidate review artifact. Scores are heuristics, not proof of truth or value.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Asset count: **{len(assets)}**",
        f"- Value bands: `{dict(band_counts)}`",
        f"- Asset types: `{dict(type_counts)}`",
        f"- Freshness counts: `{dict(freshness_counts)}`",
        f"- Component averages: `{component_averages}`",
        "",
        "## High-Score Review Sample",
        "",
    ]
    for asset in sorted_assets[:sample_size]:
        lines.extend(
            [
                f"### {asset.asset_id}",
                f"- Asset: {_asset_context(asset)}",
                f"- Capabilities: {', '.join(asset.capabilities) or 'none'}",
                f"- Needs: {', '.join(asset.needs) or 'none'}",
                f"- Outcomes: {', '.join(asset.outcomes) or 'none'}",
                f"- Components: `{asset.value_components}`",
                "- Human rating: `[ ] too high  [ ] about right  [ ] too low  [ ] unsure`",
                "- Notes:",
                "",
            ]
        )
    lines.extend(["## Low-Score Review Sample", ""])
    for asset in low_assets[:sample_size]:
        lines.extend(
            [
                f"### {asset.asset_id}",
                f"- Asset: {_asset_context(asset)}",
                f"- Capabilities: {', '.join(asset.capabilities) or 'none'}",
                f"- Needs: {', '.join(asset.needs) or 'none'}",
                f"- Components: `{asset.value_components}`",
                "- Human rating: `[ ] too high  [ ] about right  [ ] too low  [ ] unsure`",
                "- Notes:",
                "",
            ]
        )
    lines.extend(
        [
            "## Calibration Questions",
            "",
            "- Which high-score assets are false positives?",
            "- Which low-score assets are false negatives?",
            "- Which value components appear overweighted or underweighted?",
            "- What weight changes should be tested before any roadmap status changes?",
            "",
        ]
    )
    return "\n".join(lines)


def orphan_review_sample_markdown(
    assets: list[AssetRecord], alerts: list[AlertRecord], sample_size: int = 25
) -> str:
    by_id = {asset.asset_id: asset for asset in assets}
    orphan_alerts = [
        alert for alert in alerts if alert.alert_type == "orphan_asset" and alert.status == "open"
    ]
    orphan_alerts = sorted(
        orphan_alerts,
        key=lambda alert: (
            {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[alert.severity],
            max((by_id[aid].value_score for aid in alert.asset_ids if aid in by_id), default=0),
            alert.alert_id,
        ),
        reverse=True,
    )
    lines = [
        "# Orphan Review Sample",
        "",
        "Generated candidate orphan review sample. Confirm authority boundaries before acting.",
        "",
        f"- Open orphan alerts: **{len(orphan_alerts)}**",
        f"- Sample size: **{min(len(orphan_alerts), sample_size)}**",
        "",
    ]
    for alert in orphan_alerts[:sample_size]:
        assets_text = [
            _asset_context(by_id[asset_id]) for asset_id in alert.asset_ids if asset_id in by_id
        ]
        lines.extend(
            [
                f"## {alert.alert_id}",
                f"- Severity: `{alert.severity}`",
                f"- Title: {alert.title}",
                f"- Assets: {' | '.join(assets_text) or ', '.join(alert.asset_ids)}",
                f"- Evidence: `{alert.evidence}`",
                f"- Recommended action: {alert.recommended_action}",
                (
                    "- Human decision: `[ ] true orphan  [ ] intentional isolation  "
                    "[ ] false positive  [ ] needs more context`"
                ),
                "- Missing relationship or metadata:",
                "- Notes:",
                "",
            ]
        )
    return "\n".join(lines)


def synergy_review_sample_markdown(
    assets: list[AssetRecord], synergies: list[SynergyRecord], sample_size: int = 25
) -> str:
    by_id = {asset.asset_id: asset for asset in assets}
    ranked = sorted(synergies, key=lambda record: (record.score, record.synergy_id), reverse=True)
    lines = [
        "# Synergy Review Sample",
        "",
        "Generated candidate synergy review sample. A synergy score is not proof of value.",
        "",
        f"- Synergy candidates: **{len(ranked)}**",
        f"- Sample size: **{min(len(ranked), sample_size)}**",
        "",
    ]
    for record in ranked[:sample_size]:
        assets_text = [
            _asset_context(by_id[asset_id]) for asset_id in record.asset_ids if asset_id in by_id
        ]
        lines.extend(
            [
                f"## {record.synergy_id}",
                f"- Score: **{record.score}**",
                f"- Confidence: `{record.confidence}`",
                f"- Assets: {' | '.join(assets_text) or ', '.join(record.asset_ids)}",
                f"- Shared outcomes: {', '.join(record.shared_outcomes) or 'none'}",
                f"- Needs covered: {', '.join(record.needs_covered) or 'none'}",
                f"- Complementary capabilities: {', '.join(record.complementary_capabilities) or 'none'}",
                f"- Missing parts: {', '.join(record.missing_parts) or 'none'}",
                f"- Hypothesis: {record.integration_hypothesis}",
                f"- Evidence: `{record.evidence}`",
                (
                    "- Human decision: `[ ] useful  [ ] duplicate/obvious  "
                    "[ ] false positive  [ ] unsafe/too broad`"
                ),
                "- Smallest bounded experiment:",
                "- Notes:",
                "",
            ]
        )
    return "\n".join(lines)


def write_phase2_calibration_reports(
    repo_root: Path,
    assets: list[AssetRecord],
    alerts: list[AlertRecord],
    synergies: list[SynergyRecord],
    *,
    sample_size: int = 25,
) -> dict[str, Any]:
    reports_dir = repo_root / "processed" / "reports"
    scoring_path = reports_dir / "scoring_calibration.md"
    orphan_path = reports_dir / "orphan_review_sample.md"
    synergy_path = reports_dir / "synergy_review_sample.md"

    atomic_write_text(scoring_path, scoring_calibration_markdown(assets, sample_size) + "\n")
    atomic_write_text(
        orphan_path, orphan_review_sample_markdown(assets, alerts, sample_size) + "\n"
    )
    atomic_write_text(
        synergy_path, synergy_review_sample_markdown(assets, synergies, sample_size) + "\n"
    )

    orphan_count = sum(
        1
        for alert in alerts
        if alert.alert_type == "orphan_asset" and alert.status == "open"
    )
    return {
        "asset_count": len(assets),
        "open_orphan_alert_count": orphan_count,
        "synergy_count": len(synergies),
        "sample_size": sample_size,
        "outputs": {
            "scoring_calibration": str(scoring_path),
            "orphan_review_sample": str(orphan_path),
            "synergy_review_sample": str(synergy_path),
        },
    }
