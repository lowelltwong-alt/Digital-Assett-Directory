from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from .ids import stable_id
from .models import AlertRecord, AssetCalibrationReviewRecord, AssetRecord, SynergyRecord
from .utils import atomic_write_text, utc_now, write_jsonl

CALIBRATION_SCORE_RATINGS = {"unreviewed", "too_high", "about_right", "too_low", "unsure"}
CALIBRATION_NOTE_FIELDS = [
    "false_positive_reason",
    "false_negative_note",
    "weight_change_note",
]


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


def _review_status(record: AssetCalibrationReviewRecord) -> str:
    if (
        record.score_rating == "unreviewed"
        and not record.false_positive_reason
        and not record.false_negative_note
        and not record.weight_change_note
    ):
        return "generated_candidate"
    return "reviewed"


def _review_is_pending(record: AssetCalibrationReviewRecord) -> bool:
    return _review_status(record) == "generated_candidate"


def _asset_calibration_record(
    asset: AssetRecord, index: int
) -> AssetCalibrationReviewRecord:
    sample_id = f"asset-review-{index:03d}"
    return AssetCalibrationReviewRecord(
        review_id=stable_id("asset-calibration-review", sample_id, asset.asset_id),
        sample_id=sample_id,
        asset_id=asset.asset_id,
        asset_title=asset.title,
        logical_path=asset.logical_path,
        asset_type=asset.asset_type,
        generated_value_score=asset.value_score,
        generated_value_band=_value_band(asset.value_score),  # type: ignore[arg-type]
        evidence={
            "value_components": asset.value_components,
            "capabilities": asset.capabilities,
            "needs": asset.needs,
            "outcomes": asset.outcomes,
            "lifecycle_state": asset.lifecycle_state,
            "freshness_status": asset.freshness_status,
            "confidence": asset.confidence,
            "authority": "Generated calibration candidate; human review required.",
        },
    )


def build_asset_calibration_review_template(
    assets: list[AssetRecord], per_band_sample: int = 25
) -> list[AssetCalibrationReviewRecord]:
    high_assets = sorted(
        assets, key=lambda asset: (asset.value_score, asset.asset_id), reverse=True
    )[:per_band_sample]
    low_assets = sorted(assets, key=lambda asset: (asset.value_score, asset.asset_id))[
        :per_band_sample
    ]
    selected: list[AssetRecord] = []
    seen: set[str] = set()
    for asset in [*high_assets, *low_assets]:
        if asset.asset_id in seen:
            continue
        seen.add(asset.asset_id)
        selected.append(asset)
    return [
        _asset_calibration_record(asset, index)
        for index, asset in enumerate(selected, start=1)
    ]


def load_asset_calibration_reviews(path: Path) -> list[AssetCalibrationReviewRecord]:
    records: list[AssetCalibrationReviewRecord] = []
    if not path.exists():
        raise FileNotFoundError(f"Asset calibration review file not found: {path}")
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(AssetCalibrationReviewRecord.model_validate(json.loads(line)))
        except Exception as exc:
            raise ValueError(
                f"Invalid asset calibration review record at {path}:{line_number}: {exc}"
            ) from exc
    return records


def write_asset_calibration_reviews(
    path: Path, records: list[AssetCalibrationReviewRecord]
) -> None:
    write_jsonl(path, [record.model_dump(mode="json") for record in records])


def summarize_asset_calibration_reviews(
    records: list[AssetCalibrationReviewRecord],
) -> dict[str, Any]:
    reviewed = [record for record in records if not _review_is_pending(record)]
    false_positive_count = sum(1 for record in records if record.false_positive_reason)
    false_negative_count = sum(1 for record in records if record.false_negative_note)
    weight_change_count = sum(1 for record in records if record.weight_change_note)
    return {
        "template_count": len(records),
        "reviewed_count": len(reviewed),
        "calibration_gate_complete": (
            len(reviewed) >= 50
            and false_positive_count > 0
            and false_negative_count > 0
            and weight_change_count > 0
        ),
        "structured_notes_complete": (
            false_positive_count > 0
            and false_negative_count > 0
            and weight_change_count > 0
        ),
        "score_rating_counts": dict(Counter(record.score_rating for record in records)),
        "value_band_counts": dict(Counter(record.generated_value_band for record in records)),
        "false_positive_note_count": false_positive_count,
        "false_negative_note_count": false_negative_count,
        "weight_change_note_count": weight_change_count,
    }


def _validate_score_rating(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in CALIBRATION_SCORE_RATINGS:
        raise ValueError(
            "Invalid score_rating "
            f"`{value}`. Expected one of: {', '.join(sorted(CALIBRATION_SCORE_RATINGS))}"
        )
    return value


def update_asset_calibration_review_record(
    records: list[AssetCalibrationReviewRecord],
    *,
    sample_id: str | None = None,
    asset_id: str | None = None,
    reviewer: str | None = None,
    score_rating: str | None = None,
    false_positive_reason: str | None = None,
    false_negative_note: str | None = None,
    weight_change_note: str | None = None,
    notes: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[list[AssetCalibrationReviewRecord], AssetCalibrationReviewRecord]:
    if not sample_id and not asset_id:
        raise ValueError("Provide --sample-id or --asset-id to select one review record.")
    matches = [
        index
        for index, record in enumerate(records)
        if (sample_id and record.sample_id == sample_id)
        or (asset_id and record.asset_id == asset_id)
    ]
    if not matches:
        raise ValueError("No asset calibration review record matched the provided identifier.")
    if len(matches) > 1:
        raise ValueError("Multiple asset calibration review records matched.")

    updates: dict[str, Any] = {}
    cleaned_rating = _validate_score_rating(score_rating)
    if cleaned_rating is not None:
        updates["score_rating"] = cleaned_rating
    for field, value in {
        "reviewer": reviewer,
        "false_positive_reason": false_positive_reason,
        "false_negative_note": false_negative_note,
        "weight_change_note": weight_change_note,
        "notes": notes,
        "reviewed_at": reviewed_at,
    }.items():
        if value is not None:
            updates[field] = value
    if not updates:
        raise ValueError("No calibration review fields were provided to update.")
    if (
        "score_rating" in updates
        or any(field in updates for field in CALIBRATION_NOTE_FIELDS)
    ) and "reviewed_at" not in updates:
        updates["reviewed_at"] = utc_now()
    if "score_rating" in updates or any(field in updates for field in CALIBRATION_NOTE_FIELDS):
        updates["review_status"] = "reviewed"

    selected_index = matches[0]
    updated = records[selected_index].model_copy(update=updates)
    updated = AssetCalibrationReviewRecord.model_validate(updated.model_dump(mode="json"))
    new_records = list(records)
    new_records[selected_index] = updated
    return new_records, updated


def update_asset_calibration_review_file(
    path: Path,
    *,
    sample_id: str | None = None,
    asset_id: str | None = None,
    reviewer: str | None = None,
    score_rating: str | None = None,
    false_positive_reason: str | None = None,
    false_negative_note: str | None = None,
    weight_change_note: str | None = None,
    notes: str | None = None,
) -> tuple[AssetCalibrationReviewRecord, dict[str, Any]]:
    records = load_asset_calibration_reviews(path)
    updated_records, updated = update_asset_calibration_review_record(
        records,
        sample_id=sample_id,
        asset_id=asset_id,
        reviewer=reviewer,
        score_rating=score_rating,
        false_positive_reason=false_positive_reason,
        false_negative_note=false_negative_note,
        weight_change_note=weight_change_note,
        notes=notes,
    )
    write_asset_calibration_reviews(path, updated_records)
    return updated, summarize_asset_calibration_reviews(updated_records)


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


def asset_calibration_summary_markdown(
    records: list[AssetCalibrationReviewRecord], source_path: Path
) -> str:
    summary = summarize_asset_calibration_reviews(records)
    lines = [
        "# Asset Scoring Calibration Summary",
        "",
        "Generated summary only. Human calibration evidence must be curated before roadmap promotion.",
        "",
        f"- Source review file: `{source_path}`",
        f"- Template records: **{summary['template_count']}**",
        f"- Reviewed records: **{summary['reviewed_count']}**",
        f"- Calibration gate complete: **{summary['calibration_gate_complete']}**",
        f"- Structured notes complete: **{summary['structured_notes_complete']}**",
        f"- Score rating counts: `{summary['score_rating_counts']}`",
        f"- Value band counts: `{summary['value_band_counts']}`",
        f"- False positive notes: **{summary['false_positive_note_count']}**",
        f"- False negative notes: **{summary['false_negative_note_count']}**",
        f"- Weight change notes: **{summary['weight_change_note_count']}**",
        "",
        "## Remaining Gate Work",
        "",
        "- Review at least 50 asset rating records.",
        "- Capture false-positive and false-negative notes.",
        "- Document any scoring weight changes before treating calibration as complete.",
        "",
    ]
    return "\n".join(lines)


def write_asset_calibration_summary(
    repo_root: Path, records: list[AssetCalibrationReviewRecord], source_path: Path
) -> tuple[dict[str, Any], str]:
    output = repo_root / "processed" / "reports" / "asset_rating_calibration_summary.md"
    atomic_write_text(output, asset_calibration_summary_markdown(records, source_path) + "\n")
    return summarize_asset_calibration_reviews(records), str(output)


def write_phase2_calibration_reports(
    repo_root: Path,
    assets: list[AssetRecord],
    alerts: list[AlertRecord],
    synergies: list[SynergyRecord],
    *,
    sample_size: int = 25,
) -> dict[str, Any]:
    reports_dir = repo_root / "processed" / "reports"
    calibration_dir = repo_root / "processed" / "calibration"
    scoring_path = reports_dir / "scoring_calibration.md"
    orphan_path = reports_dir / "orphan_review_sample.md"
    synergy_path = reports_dir / "synergy_review_sample.md"
    asset_review_path = calibration_dir / "asset_rating_template.jsonl"

    atomic_write_text(scoring_path, scoring_calibration_markdown(assets, sample_size) + "\n")
    atomic_write_text(
        orphan_path, orphan_review_sample_markdown(assets, alerts, sample_size) + "\n"
    )
    atomic_write_text(
        synergy_path, synergy_review_sample_markdown(assets, synergies, sample_size) + "\n"
    )
    asset_reviews = build_asset_calibration_review_template(assets, sample_size)
    write_asset_calibration_reviews(asset_review_path, asset_reviews)
    review_summary, review_summary_path = write_asset_calibration_summary(
        repo_root, asset_reviews, asset_review_path
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
        "asset_review_template_count": len(asset_reviews),
        "asset_review_summary": review_summary,
        "outputs": {
            "scoring_calibration": str(scoring_path),
            "orphan_review_sample": str(orphan_path),
            "synergy_review_sample": str(synergy_path),
            "asset_rating_template": str(asset_review_path),
            "asset_rating_summary": review_summary_path,
        },
    }
