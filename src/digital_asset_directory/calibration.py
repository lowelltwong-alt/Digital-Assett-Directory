from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Literal

from .ids import stable_id
from .models import AlertRecord, AssetCalibrationReviewRecord, AssetRecord, SynergyRecord
from .roadmap import record_human_gate_evidence
from .utils import atomic_write_text, utc_now, write_jsonl

CALIBRATION_SCORE_RATINGS = {"unreviewed", "too_high", "about_right", "too_low", "unsure"}
CALIBRATION_NOTE_FIELDS = [
    "false_positive_reason",
    "false_negative_note",
    "weight_change_note",
]
CALIBRATION_REVIEW_CSV_COLUMNS = [
    "sample_id",
    "asset_id",
    "asset_title",
    "logical_path",
    "asset_type",
    "generated_value_score",
    "generated_value_band",
    "value_components",
    "capabilities",
    "needs",
    "outcomes",
    "lifecycle_state",
    "freshness_status",
    "confidence",
    "pattern_key",
    "current_graph_role",
    "useful_to_future_agents",
    "missing_or_combine_with",
    "projected_value_lift",
    "current_floor",
    "current_floor_basis",
    "current_score_range",
    "current_score_midpoint",
    "current_score_uncertainty",
    "current_score_range_basis",
    "review_order",
    "current_score_first_prompt",
    "potential_ceiling",
    "potential_ceiling_range",
    "potential_ceiling_basis",
    "ceiling_confidence",
    "upside_gap",
    "upside_delta",
    "upside_delta_range",
    "upside_delta_meaning",
    "activation_requirements",
    "development_posture",
    "score_warning",
    "score_justification",
    "ceiling_justification",
    "ceiling_activation_conditions",
    "projection_review_cadence",
    "usage_feedback_prompt",
    "usage_feedback_command",
    "usage_feedback_fields",
    "usage_feedback_instructions",
    "usage_feedback_scoring_methodology",
    "edge_evidence_summary",
    "calibration_caution",
    "duplicate_review_prompt",
    "cluster_delta_prompt",
    "review_status",
    "reviewer",
    "score_rating",
    "notes",
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


def _evidence_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _top_component_names(value_components: Any, limit: int = 2) -> list[str]:
    if not isinstance(value_components, dict):
        return []
    ranked = sorted(
        ((str(component), float(score)) for component, score in value_components.items()),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    return [component for component, _score in ranked[:limit]]


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _asset_role_hints(
    asset_type: str, title: str, logical_path: str
) -> tuple[str, str, list[str], str]:
    text = f"{title} {logical_path}".lower()
    if asset_type == "schema":
        return (
            "Contract node for structured asset interoperability.",
            "Keeps agents aligned on record shape, authority, confidence, and provenance.",
            [
                "schema examples",
                "migration/version tests",
                "edge and proposal schema links",
            ],
            "very_high",
        )
    if asset_type == "lesson":
        return (
            "Agent memory and doctrine node.",
            "Preserves reusable decision logic without promoting lessons to truth automatically.",
            [
                "linked postflight examples",
                "lesson reindex evidence",
                "outcome follow-up records",
            ],
            "high",
        )
    if asset_type == "test":
        if _contains_any(text, ("graph", "radar", "synergy", "orphan")):
            return (
                "Graph-edge validation node.",
                "Helps agents separate useful relationship signals from noisy matches.",
                [
                    "false-positive labels",
                    "false-negative labels",
                    "bounded edge-quality fixtures",
                ],
                "very_high",
            )
        if _contains_any(text, ("governance", "pre-push", "downstream")):
            return (
                "Governance safety validation node.",
                "Lets agents test downstream controls before touching active repositories.",
                [
                    "sandbox pilot evidence",
                    "bypass/failure policy",
                    "postflight-clears-gate examples",
                ],
                "very_high",
            )
        if _contains_any(text, ("catalog", "pipeline")):
            return (
                "Catalog pipeline acceptance node.",
                "Shows future agents the outputs and safety boundaries a scan must preserve.",
                [
                    "failure-mode fixtures",
                    "roadmap gate traceability",
                    "larger source matrix",
                ],
                "high",
            )
        if _contains_any(text, ("extract", "local_scan", "scan", "redact")):
            return (
                "Extraction and privacy validation node.",
                "Protects the asset metadata and redaction edges that feed the graph.",
                [
                    "adversarial secret corpus",
                    "semantic gold labels",
                    "file-type coverage",
                ],
                "high",
            )
        if _contains_any(text, ("database", "learning", "lesson", "handoff")):
            return (
                "Agent memory persistence validation node.",
                "Tests whether preflight, postflight, lessons, and handoffs survive as usable context.",
                [
                    "lesson reindex tests",
                    "downstream hub arrival evidence",
                    "multi-agent handoff examples",
                ],
                "high",
            )
        if _contains_any(text, ("recommend", "proposal", "skill", "swarm")):
            return (
                "Recommendation behavior validation node.",
                "Checks how repeated needs become candidate skills, swarms, or upgrade proposals.",
                [
                    "human usefulness labels",
                    "rejected recommendation examples",
                    "proposal calibration outcomes",
                ],
                "high",
            )
        return (
            "Verification node.",
            "Gives future agents a runnable check for one behavior boundary.",
            [
                "failure cases",
                "coverage rationale",
                "human review notes",
            ],
            "medium",
        )
    if asset_type == "code":
        if _contains_any(text, ("extract", "semantic", "classif")):
            return (
                "Semantic edge factory.",
                "Creates asset type, capability, need, freshness, and privacy signals for the graph.",
                [
                    "gold semantic labels",
                    "precision/recall evaluation harness",
                    "human calibration outcomes",
                ],
                "very_high",
            )
        return (
            "Executable behavior node.",
            "Provides reusable implementation that other agents can call, test, or constrain.",
            [
                "public contract tests",
                "usage examples",
                "authority boundary notes",
            ],
            "high",
        )
    if asset_type in {"doc", "markdown"}:
        return (
            "Human-readable guidance node.",
            "Explains behavior and decisions that future agents may need before changing code.",
            [
                "linked examples",
                "acceptance checks",
                "owner-reviewed decisions",
            ],
            "medium",
        )
    return (
        "Cataloged asset node.",
        "May help future agents if its capabilities, needs, and outcomes connect to a task.",
        [
            "clear usage example",
            "validated relationship edges",
            "authority boundary notes",
        ],
        "medium",
    )


def _score_level(score: float) -> str:
    if score >= 90:
        return "very_high"
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _lift_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "very_high": 3}.get(level, 1)


def _upside_gap(current_floor: str, potential_ceiling: str) -> str:
    gap = _lift_rank(potential_ceiling) - _lift_rank(current_floor)
    if gap >= 2:
        return "large"
    if gap == 1:
        return "medium"
    return "small"


def _upside_delta(current_floor: str, potential_ceiling: str) -> int:
    return max(0, _lift_rank(potential_ceiling) - _lift_rank(current_floor))


def _upside_delta_meaning(delta: int, ceiling_confidence: str) -> str:
    if delta == 0:
        return (
            "Current generated floor and conditional ceiling are in the same band; "
            "review should focus on whether the current score itself is accurate."
        )
    if delta == 1:
        return (
            "One-band upside: useful development opportunity if activation conditions "
            "are concrete and current score is not already inflated."
        )
    if ceiling_confidence == "low":
        return (
            "Large but low-confidence upside: do not raise current score; create a "
            "validation experiment before directing major development attention."
        )
    return (
        "Large grounded upside: candidate for active development after current score "
        "label and activation conditions are reviewed."
    )


def _current_score_uncertainty(record: AssetCalibrationReviewRecord) -> tuple[float, str]:
    evidence = record.evidence or {}
    value_components = evidence.get("value_components", {})
    verification = 0.0
    if isinstance(value_components, dict):
        verification = float(value_components.get("verification", 0.0))
    needs = _evidence_list(evidence.get("needs", []))
    confidence = str(evidence.get("confidence", "")).lower()
    if confidence == "high" and verification >= 80 and len(needs) <= 2:
        return 5.0, "narrow"
    if confidence in {"high", "medium"} and verification >= 40:
        return 10.0, "medium"
    return 15.0, "wide"


def _current_score_range(record: AssetCalibrationReviewRecord) -> dict[str, float]:
    radius, _label = _current_score_uncertainty(record)
    midpoint = float(record.generated_value_score)
    return {
        "low": round(max(0.0, midpoint - radius), 2),
        "midpoint": round(midpoint, 2),
        "high": round(min(100.0, midpoint + radius), 2),
    }


def _ceiling_confidence(record: AssetCalibrationReviewRecord, missing_parts: list[str]) -> str:
    evidence = record.evidence or {}
    value_components = evidence.get("value_components", {})
    verification = 0.0
    if isinstance(value_components, dict):
        verification = float(value_components.get("verification", 0.0))
    needs = _evidence_list(evidence.get("needs", []))
    if verification >= 80 and len(needs) <= 2 and len(missing_parts) <= 3:
        return "medium"
    return "low"


def _development_posture(
    record: AssetCalibrationReviewRecord,
    *,
    potential_ceiling: str,
    ceiling_confidence: str,
    upside_gap: str,
) -> str:
    if ceiling_confidence == "low":
        return "validate_first"
    if record.asset_type == "schema" and potential_ceiling == "very_high":
        return "actively_develop"
    if upside_gap in {"large", "medium"}:
        return "prototype_bounded_experiment"
    return "monitor"


def _potential_ceiling_range(potential_ceiling: str, ceiling_confidence: str) -> dict[str, str]:
    rank_to_level = {0: "low", 1: "medium", 2: "high", 3: "very_high"}
    ceiling_rank = _lift_rank(potential_ceiling)
    if ceiling_confidence == "low":
        low_rank = max(0, ceiling_rank - 1)
    else:
        low_rank = ceiling_rank
    return {"low": rank_to_level[low_rank], "high": potential_ceiling}


def _upside_delta_range(current_floor: str, ceiling_range: dict[str, str]) -> dict[str, int]:
    current_rank = _lift_rank(current_floor)
    return {
        "low": max(0, _lift_rank(ceiling_range["low"]) - current_rank),
        "high": max(0, _lift_rank(ceiling_range["high"]) - current_rank),
    }


def _score_justification(record: AssetCalibrationReviewRecord) -> str:
    evidence = record.evidence or {}
    components = evidence.get("value_components", {})
    top_components = _top_component_names(components, limit=3)
    capabilities = _evidence_list(evidence.get("capabilities", []))
    needs = _evidence_list(evidence.get("needs", []))
    parts = [
        f"Generated score is {record.generated_value_score} ({record.generated_value_band})",
    ]
    if top_components:
        parts.append("because top components are " + ", ".join(top_components))
    if capabilities:
        parts.append("with capabilities " + ", ".join(capabilities[:3]))
    if needs:
        parts.append("and inferred needs " + ", ".join(needs[:3]))
    parts.append("human review decides whether this current score is too_high, about_right, or too_low")
    return "; ".join(parts) + "."


def _ceiling_justification(
    current_role: str,
    future_use: str,
    potential_ceiling: str,
    missing_parts: list[str],
) -> str:
    missing_text = ", ".join(missing_parts) if missing_parts else "no obvious missing parts"
    return (
        f"Potential ceiling is {potential_ceiling} because the asset's role is "
        f"{current_role.lower()} and it could help future agents by: {future_use} "
        f"Conditions still needed: {missing_text}."
    )


def build_asset_calibration_review_lens(
    record: AssetCalibrationReviewRecord,
) -> dict[str, Any]:
    evidence = record.evidence or {}
    capabilities = _evidence_list(evidence.get("capabilities", []))
    needs = _evidence_list(evidence.get("needs", []))
    outcomes = _evidence_list(evidence.get("outcomes", []))
    value_components = evidence.get("value_components", {})
    top_components = _top_component_names(value_components)
    current_role, future_use, missing_parts, projected_lift = _asset_role_hints(
        record.asset_type,
        record.asset_title,
        record.logical_path,
    )
    current_score_range = _current_score_range(record)
    _score_radius, current_score_uncertainty = _current_score_uncertainty(record)
    current_floor = _score_level(record.generated_value_score)
    potential_ceiling = projected_lift
    upside_gap = _upside_gap(current_floor, potential_ceiling)
    ceiling_confidence = _ceiling_confidence(record, missing_parts)
    potential_ceiling_range = _potential_ceiling_range(potential_ceiling, ceiling_confidence)
    upside_delta = _upside_delta(current_floor, potential_ceiling)
    upside_delta_range = _upside_delta_range(current_floor, potential_ceiling_range)
    development_posture = _development_posture(
        record,
        potential_ceiling=potential_ceiling,
        ceiling_confidence=ceiling_confidence,
        upside_gap=upside_gap,
    )
    component_part = "+".join(top_components) or "no-components"
    need_part = "needs-" + "+".join(needs[:2]) if needs else "no-needs"
    capability_part = "caps-" + "+".join(capabilities[:2]) if capabilities else "no-caps"
    pattern_key = (
        f"{record.asset_type}/{record.generated_value_band}/"
        f"{component_part}/{capability_part}/{need_part}"
    )

    high_signal_edges: list[dict[str, str]] = []
    for capability in capabilities[:3]:
        high_signal_edges.append(
            {
                "edge": f"provides_capability:{capability}",
                "evidence_level": "direct",
                "why": "Capability is present in generated asset evidence.",
            }
        )
    for need in needs[:2]:
        high_signal_edges.append(
            {
                "edge": f"needs:{need}",
                "evidence_level": "derived",
                "why": "Need was inferred from source text and needs human calibration.",
            }
        )
    for outcome in outcomes[:2]:
        high_signal_edges.append(
            {
                "edge": f"supports_outcome:{outcome}",
                "evidence_level": "derived",
                "why": "Outcome links the asset to future task value.",
            }
        )
    if record.asset_type == "schema":
        high_signal_edges.append(
            {
                "edge": "constrains:catalog_contracts",
                "evidence_level": "direct",
                "why": "Schema assets define interoperable record structure.",
            }
        )
    elif record.asset_type == "test":
        high_signal_edges.append(
            {
                "edge": "validates:behavior_boundary",
                "evidence_level": "direct",
                "why": "Test assets are executable checks for catalog behavior.",
            }
        )
    elif record.asset_type == "lesson":
        high_signal_edges.append(
            {
                "edge": "informs:agent_decision_memory",
                "evidence_level": "direct",
                "why": "Lesson assets preserve candidate guidance for future agents.",
            }
        )

    layers = [
        {
            "layer": "grounded_current_role",
            "role": current_role,
            "evidence_level": "direct",
            "score_use": "eligible_for_current_score",
        },
        {
            "layer": "latent_role",
            "role": (
                "A smaller signal in this asset may become more valuable when paired "
                "with calibrated labels, examples, or validators."
            ),
            "evidence_level": "derived",
            "score_use": "light_weight_until_verified",
        },
        {
            "layer": "bridge_role",
            "role": future_use,
            "evidence_level": "projected",
            "score_use": "review_note_only",
        },
    ]

    return {
        "pattern_key": pattern_key,
        "current_graph_role": current_role,
        "useful_to_future_agents": future_use,
        "layers": layers,
        "high_signal_edges": high_signal_edges[:8],
        "missing_or_combine_with": missing_parts,
        "projected_value_lift": projected_lift,
        "current_floor": current_floor,
        "current_floor_basis": (
            "Generated pre-review score band; reviewer may mark it too_high, "
            "about_right, too_low, or unsure."
        ),
        "current_score_range": current_score_range,
        "current_score_midpoint": current_score_range["midpoint"],
        "current_score_uncertainty": current_score_uncertainty,
        "current_score_range_basis": (
            "Deterministic uncertainty interval around the generated score. It is "
            "not a statistical confidence interval until calibrated against human labels."
        ),
        "review_order": [
            "Judge current generated score using direct and cautiously derived evidence.",
            "Assign score_rating before considering conditional upside.",
            "Use ceiling, delta, and activation conditions only for future development notes.",
        ],
        "current_score_first_prompt": (
            "Review the current value score first. Do not use potential ceiling or "
            "upside gap to justify about_right or too_low unless current evidence supports it."
        ),
        "potential_ceiling": potential_ceiling,
        "potential_ceiling_range": potential_ceiling_range,
        "potential_ceiling_basis": (
            "Conditional upside inferred from asset type, path, capabilities, needs, "
            "and likely graph role; not proof of current value."
        ),
        "ceiling_confidence": ceiling_confidence,
        "upside_gap": upside_gap,
        "upside_delta": upside_delta,
        "upside_delta_range": upside_delta_range,
        "upside_delta_meaning": _upside_delta_meaning(upside_delta, ceiling_confidence),
        "activation_requirements": missing_parts,
        "development_posture": development_posture,
        "score_warning": (
            "High ceiling does not justify a high current score unless direct evidence "
            "already proves the asset works in that role."
        ),
        "score_justification": _score_justification(record),
        "ceiling_justification": _ceiling_justification(
            current_role,
            future_use,
            potential_ceiling,
            missing_parts,
        ),
        "ceiling_activation_conditions": missing_parts,
        "projection_review_cadence": (
            "Reevaluate floor, ceiling, upside gap, and development posture at least "
            "every 6 months or after major source, roadmap, or usage changes."
        ),
        "usage_feedback_prompt": (
            "Asset-use contract: before using this asset, record expected value and "
            "planned use; after using it, record actual use, difficulty, lessons, "
            "usefulness, futurefulness, upgrades, and score/ceiling feedback."
        ),
        "usage_feedback_command": (
            "python -m digital_asset_directory.cli lesson asset-use --asset-id "
            f"{record.asset_id} --stage before_use|after_use --repo <repo> "
            "--task <task> --agent <agent> "
            "--found-by <context|queue|search|memory|human> --found-query <query> "
            "--planned-use <plan> --expected-usefulness low|medium|high|unknown "
            "--expected-futurefulness low|medium|high|unknown "
            "--expected-value-reason <why> "
            "--used-for <use> --part-used <part> --part-not-used <part> "
            "--not-used-reason <reason> --upgrade-made <upgrade> "
            "--difficulty <difficulty> --thing-learned <lesson> "
            "--use-outcome helped|blocked|no_effect|unknown "
            "--observed-usefulness low|medium|high|unknown "
            "--observed-futurefulness low|medium|high|unknown"
        ),
        "usage_feedback_fields": [
            "feedback_code",
            "interaction_stage",
            "asset_id",
            "task",
            "agent",
            "found_by",
            "found_query",
            "planned_use",
            "expected_usefulness",
            "expected_futurefulness",
            "expected_value_reason",
            "used_for",
            "parts_used",
            "parts_not_used",
            "not_used_reason",
            "upgrades_made",
            "difficulties",
            "things_learned",
            "use_outcome",
            "observed_usefulness",
            "observed_futurefulness",
            "missing_parts_seen",
            "score_feedback",
            "ceiling_feedback",
            "evidence",
        ],
        "usage_feedback_instructions": [
            "Complete a before_use record before material use whenever possible.",
            "Complete an after_use record after material use; if impossible, note the missing follow-up in postflight.",
            "Use the exact allowed values for categorical fields.",
            "Base observed_usefulness on what happened in this task, not predicted future value.",
            "Base observed_futurefulness on new evidence about future reuse or activation.",
            "List concrete parts used; write none if the whole asset was only inspected.",
            "List concrete parts not used when a relevant part was skipped or unsuitable.",
            "Use evidence entries for files, commands, review IDs, or observed outputs.",
            "Do not change source repo code or asset scores from this feedback record.",
        ],
        "usage_feedback_scoring_methodology": {
            "observed_usefulness": {
                "high": "Asset directly saved time, reduced risk, enabled a decision, or provided reusable implementation/evidence.",
                "medium": "Asset helped with context or partial work but required extra verification or adaptation.",
                "low": "Asset was mostly unhelpful, stale, misleading, duplicative, or too incomplete for the task.",
                "unknown": "Agent inspected the asset but cannot judge usefulness from this task.",
            },
            "observed_futurefulness": {
                "high": "Use revealed strong future reuse, graph leverage, or activation potential if clear conditions are met.",
                "medium": "Use revealed plausible future value with missing examples, tests, labels, adapters, or review.",
                "low": "Use suggested limited future reuse or a narrow context-specific role.",
                "unknown": "Future value could not be assessed from this use.",
            },
            "use_outcome": {
                "helped": "The asset contributed positively to the task outcome.",
                "blocked": "The asset caused delay, confusion, failed assumptions, or exposed missing prerequisites.",
                "no_effect": "The asset was tried but did not materially affect the task.",
                "unknown": "The effect cannot be determined.",
            },
        },
        "calibration_caution": (
            "Projected lift is review context only; current score should be justified "
            "by direct or cautiously derived evidence."
        ),
        "duplicate_review_prompt": (
            "If another asset solves the same problem, record whether this should be "
            "near_duplicate, variant_of, superseded_by, or merge_candidate before "
            "treating both scores as independent value."
        ),
        "cluster_delta_prompt": (
            "For close assets, create a candidate cluster delta that separates shared "
            "core, stronger parts, neutral differences, weaker parts, context-specific "
            "roles, and a bounded merge-or-keep-variant experiment."
        ),
        "authority": "Generated review guidance only; human labels remain required.",
    }


def _review_lens(record: AssetCalibrationReviewRecord) -> dict[str, Any]:
    lens = record.evidence.get("review_lens")
    if isinstance(lens, dict):
        return lens
    return build_asset_calibration_review_lens(record)


def _asset_calibration_record(
    asset: AssetRecord, index: int
) -> AssetCalibrationReviewRecord:
    sample_id = f"asset-review-{index:03d}"
    evidence = {
        "value_components": asset.value_components,
        "capabilities": asset.capabilities,
        "needs": asset.needs,
        "outcomes": asset.outcomes,
        "lifecycle_state": asset.lifecycle_state,
        "freshness_status": asset.freshness_status,
        "confidence": asset.confidence,
        "authority": "Generated calibration candidate; human review required.",
    }
    record = AssetCalibrationReviewRecord(
        review_id=stable_id("asset-calibration-review", sample_id, asset.asset_id),
        sample_id=sample_id,
        asset_id=asset.asset_id,
        asset_title=asset.title,
        logical_path=asset.logical_path,
        asset_type=asset.asset_type,
        generated_value_score=asset.value_score,
        generated_value_band=_value_band(asset.value_score),  # type: ignore[arg-type]
        evidence=evidence,
    )
    evidence["review_lens"] = build_asset_calibration_review_lens(record)
    return record.model_copy(update={"evidence": evidence})


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


def build_asset_calibration_review_queue(
    records: list[AssetCalibrationReviewRecord],
    *,
    status: Literal["pending", "reviewed", "all"] = "pending",
    band: Literal["low", "medium", "high", "all"] = "all",
    limit: int = 10,
) -> dict[str, Any]:
    if status not in {"pending", "reviewed", "all"}:
        raise ValueError("Status must be one of: pending, reviewed, all")
    if band not in {"low", "medium", "high", "all"}:
        raise ValueError("Band must be one of: low, medium, high, all")

    items: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item.sample_id):
        pending = _review_is_pending(record)
        if status == "pending" and not pending:
            continue
        if status == "reviewed" and pending:
            continue
        if band != "all" and record.generated_value_band != band:
            continue
        lens = _review_lens(record)
        items.append(
            {
                "sample_id": record.sample_id,
                "asset_id": record.asset_id,
                "asset_title": record.asset_title,
                "logical_path": record.logical_path,
                "asset_type": record.asset_type,
                "generated_value_score": record.generated_value_score,
                "generated_value_band": record.generated_value_band,
                "pattern_key": lens["pattern_key"],
                "review_status": _review_status(record),
                "labels": {
                    "score_rating": record.score_rating,
                    "false_positive_reason": record.false_positive_reason,
                    "false_negative_note": record.false_negative_note,
                    "weight_change_note": record.weight_change_note,
                    "notes": record.notes,
                },
                "reviewer": record.reviewer,
                "reviewed_at": record.reviewed_at,
                "evidence": {
                    "value_components": record.evidence.get("value_components", {}),
                    "capabilities": record.evidence.get("capabilities", []),
                    "needs": record.evidence.get("needs", []),
                    "outcomes": record.evidence.get("outcomes", []),
                    "lifecycle_state": record.evidence.get("lifecycle_state", ""),
                    "freshness_status": record.evidence.get("freshness_status", ""),
                    "confidence": record.evidence.get("confidence", ""),
                    "authority": record.evidence.get(
                        "authority",
                        "Generated calibration candidate; human review required.",
                    ),
                    "review_lens": lens,
                },
            }
        )
        if len(items) >= limit:
            break

    return {
        "status_filter": status,
        "band_filter": band,
        "limit": limit,
        "returned_count": len(items),
        "summary": summarize_asset_calibration_reviews(records),
        "items": items,
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
    rating_counts_as_review = updates.get("score_rating") not in {None, "unreviewed"}
    structured_note_present = any(field in updates for field in CALIBRATION_NOTE_FIELDS)
    if (rating_counts_as_review or structured_note_present) and "reviewed_at" not in updates:
        updates["reviewed_at"] = utc_now()
    if rating_counts_as_review or structured_note_present:
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


def _join_values(values: Any) -> str:
    if isinstance(values, list):
        return ";".join(str(value) for value in values)
    return ""


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _csv_value(row: dict[str, str], field: str) -> str | None:
    value = (row.get(field) or "").strip()
    return value or None


def asset_calibration_review_csv_rows(
    records: list[AssetCalibrationReviewRecord],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in sorted(records, key=lambda item: item.sample_id):
        evidence = record.evidence
        lens = _review_lens(record)
        rows.append(
            {
                "sample_id": record.sample_id,
                "asset_id": record.asset_id,
                "asset_title": record.asset_title,
                "logical_path": record.logical_path,
                "asset_type": record.asset_type,
                "generated_value_score": str(record.generated_value_score),
                "generated_value_band": record.generated_value_band,
                "value_components": _json_cell(evidence.get("value_components", {})),
                "capabilities": _join_values(evidence.get("capabilities", [])),
                "needs": _join_values(evidence.get("needs", [])),
                "outcomes": _join_values(evidence.get("outcomes", [])),
                "lifecycle_state": str(evidence.get("lifecycle_state", "")),
                "freshness_status": str(evidence.get("freshness_status", "")),
                "confidence": str(evidence.get("confidence", "")),
                "pattern_key": str(lens.get("pattern_key", "")),
                "current_graph_role": str(lens.get("current_graph_role", "")),
                "useful_to_future_agents": str(lens.get("useful_to_future_agents", "")),
                "missing_or_combine_with": _json_cell(
                    lens.get("missing_or_combine_with", [])
                ),
                "projected_value_lift": str(lens.get("projected_value_lift", "")),
                "current_floor": str(lens.get("current_floor", "")),
                "current_floor_basis": str(lens.get("current_floor_basis", "")),
                "current_score_range": _json_cell(lens.get("current_score_range", {})),
                "current_score_midpoint": str(lens.get("current_score_midpoint", "")),
                "current_score_uncertainty": str(
                    lens.get("current_score_uncertainty", "")
                ),
                "current_score_range_basis": str(
                    lens.get("current_score_range_basis", "")
                ),
                "review_order": _json_cell(lens.get("review_order", [])),
                "current_score_first_prompt": str(
                    lens.get("current_score_first_prompt", "")
                ),
                "potential_ceiling": str(lens.get("potential_ceiling", "")),
                "potential_ceiling_range": _json_cell(
                    lens.get("potential_ceiling_range", {})
                ),
                "potential_ceiling_basis": str(lens.get("potential_ceiling_basis", "")),
                "ceiling_confidence": str(lens.get("ceiling_confidence", "")),
                "upside_gap": str(lens.get("upside_gap", "")),
                "upside_delta": str(lens.get("upside_delta", "")),
                "upside_delta_range": _json_cell(lens.get("upside_delta_range", {})),
                "upside_delta_meaning": str(lens.get("upside_delta_meaning", "")),
                "activation_requirements": _json_cell(
                    lens.get("activation_requirements", [])
                ),
                "development_posture": str(lens.get("development_posture", "")),
                "score_warning": str(lens.get("score_warning", "")),
                "score_justification": str(lens.get("score_justification", "")),
                "ceiling_justification": str(lens.get("ceiling_justification", "")),
                "ceiling_activation_conditions": _json_cell(
                    lens.get("ceiling_activation_conditions", [])
                ),
                "projection_review_cadence": str(
                    lens.get("projection_review_cadence", "")
                ),
                "usage_feedback_prompt": str(lens.get("usage_feedback_prompt", "")),
                "usage_feedback_command": str(lens.get("usage_feedback_command", "")),
                "usage_feedback_fields": _json_cell(lens.get("usage_feedback_fields", [])),
                "usage_feedback_instructions": _json_cell(
                    lens.get("usage_feedback_instructions", [])
                ),
                "usage_feedback_scoring_methodology": _json_cell(
                    lens.get("usage_feedback_scoring_methodology", {})
                ),
                "edge_evidence_summary": _json_cell(lens.get("high_signal_edges", [])),
                "calibration_caution": str(lens.get("calibration_caution", "")),
                "duplicate_review_prompt": str(lens.get("duplicate_review_prompt", "")),
                "cluster_delta_prompt": str(lens.get("cluster_delta_prompt", "")),
                "review_status": _review_status(record),
                "reviewer": record.reviewer,
                "score_rating": record.score_rating,
                "notes": record.notes,
                "false_positive_reason": record.false_positive_reason,
                "false_negative_note": record.false_negative_note,
                "weight_change_note": record.weight_change_note,
            }
        )
    return rows


def write_asset_calibration_review_csv(
    path: Path, records: list[AssetCalibrationReviewRecord]
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = asset_calibration_review_csv_rows(records)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CALIBRATION_REVIEW_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def import_asset_calibration_review_csv(
    review_path: Path,
    csv_path: Path,
    *,
    default_reviewer: str | None = None,
) -> dict[str, Any]:
    records = load_asset_calibration_reviews(review_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Asset calibration review CSV not found: {csv_path}")

    updated_count = 0
    skipped_count = 0
    errors: list[str] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = {"sample_id", "asset_id", "score_rating"} - set(
            reader.fieldnames or []
        )
        if missing_columns:
            raise ValueError(
                "Asset calibration review CSV missing required columns: "
                + ", ".join(sorted(missing_columns))
            )
        for row_number, row in enumerate(reader, start=2):
            score_rating = _csv_value(row, "score_rating")
            has_rating = score_rating is not None and score_rating != "unreviewed"
            has_structured_note = any(_csv_value(row, field) for field in CALIBRATION_NOTE_FIELDS)
            has_metadata = any(_csv_value(row, field) for field in {"reviewer", "notes"})
            if not has_rating and not has_structured_note and not has_metadata:
                skipped_count += 1
                continue
            try:
                records, _ = update_asset_calibration_review_record(
                    records,
                    sample_id=_csv_value(row, "sample_id"),
                    asset_id=_csv_value(row, "asset_id"),
                    reviewer=_csv_value(row, "reviewer") or default_reviewer,
                    score_rating=score_rating,
                    false_positive_reason=_csv_value(row, "false_positive_reason"),
                    false_negative_note=_csv_value(row, "false_negative_note"),
                    weight_change_note=_csv_value(row, "weight_change_note"),
                    notes=_csv_value(row, "notes"),
                )
                updated_count += 1
            except ValueError as exc:
                errors.append(f"row {row_number}: {exc}")

    if errors:
        raise ValueError("Asset calibration review CSV import failed: " + "; ".join(errors[:10]))
    write_asset_calibration_reviews(review_path, records)
    return {
        "review_file": str(review_path),
        "csv_file": str(csv_path),
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "summary": summarize_asset_calibration_reviews(records),
    }


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
        lens = _review_lens(_asset_calibration_record(asset, 0))
        lines.extend(
            [
                f"### {asset.asset_id}",
                f"- Asset: {_asset_context(asset)}",
                f"- Capabilities: {', '.join(asset.capabilities) or 'none'}",
                f"- Needs: {', '.join(asset.needs) or 'none'}",
                f"- Outcomes: {', '.join(asset.outcomes) or 'none'}",
                f"- Components: `{asset.value_components}`",
                f"- Current graph role: {lens['current_graph_role']}",
                f"- Useful to future agents: {lens['useful_to_future_agents']}",
                f"- Missing/combine with: {', '.join(lens['missing_or_combine_with'])}",
                f"- Projected value lift: `{lens['projected_value_lift']}`",
                f"- Current-score-first prompt: {lens['current_score_first_prompt']}",
                f"- Current score range: `{lens['current_score_range']['low']}.."
                f"{lens['current_score_range']['high']}` "
                f"(midpoint `{lens['current_score_midpoint']}`, "
                f"{lens['current_score_uncertainty']} uncertainty)",
                f"- Floor/ceiling: `{lens['current_floor']}` current, "
                f"`{lens['potential_ceiling_range']['low']}.."
                f"{lens['potential_ceiling_range']['high']}` ceiling range, "
                f"`{lens['ceiling_confidence']}` ceiling confidence",
                f"- Upside delta: `{lens['upside_delta_range']['low']}.."
                f"{lens['upside_delta_range']['high']}` band(s), "
                f"`{lens['upside_gap']}` gap. {lens['upside_delta_meaning']}",
                f"- Development posture: `{lens['development_posture']}`",
                f"- Score warning: {lens['score_warning']}",
                f"- Score justification: {lens['score_justification']}",
                f"- Ceiling justification: {lens['ceiling_justification']}",
                (
                    "- Ceiling activation conditions: "
                    f"{', '.join(lens['ceiling_activation_conditions']) or 'none'}"
                ),
                f"- Duplicate/variant check: {lens['duplicate_review_prompt']}",
                f"- Cluster delta check: {lens['cluster_delta_prompt']}",
                "- Human rating: `[ ] too high  [ ] about right  [ ] too low  [ ] unsure`",
                "- Notes:",
                "",
            ]
        )
    lines.extend(["## Low-Score Review Sample", ""])
    for asset in low_assets[:sample_size]:
        lens = _review_lens(_asset_calibration_record(asset, 0))
        lines.extend(
            [
                f"### {asset.asset_id}",
                f"- Asset: {_asset_context(asset)}",
                f"- Capabilities: {', '.join(asset.capabilities) or 'none'}",
                f"- Needs: {', '.join(asset.needs) or 'none'}",
                f"- Components: `{asset.value_components}`",
                f"- Current graph role: {lens['current_graph_role']}",
                f"- Useful to future agents: {lens['useful_to_future_agents']}",
                f"- Missing/combine with: {', '.join(lens['missing_or_combine_with'])}",
                f"- Projected value lift: `{lens['projected_value_lift']}`",
                f"- Current-score-first prompt: {lens['current_score_first_prompt']}",
                f"- Current score range: `{lens['current_score_range']['low']}.."
                f"{lens['current_score_range']['high']}` "
                f"(midpoint `{lens['current_score_midpoint']}`, "
                f"{lens['current_score_uncertainty']} uncertainty)",
                f"- Floor/ceiling: `{lens['current_floor']}` current, "
                f"`{lens['potential_ceiling_range']['low']}.."
                f"{lens['potential_ceiling_range']['high']}` ceiling range, "
                f"`{lens['ceiling_confidence']}` ceiling confidence",
                f"- Upside delta: `{lens['upside_delta_range']['low']}.."
                f"{lens['upside_delta_range']['high']}` band(s), "
                f"`{lens['upside_gap']}` gap. {lens['upside_delta_meaning']}",
                f"- Development posture: `{lens['development_posture']}`",
                f"- Score warning: {lens['score_warning']}",
                f"- Score justification: {lens['score_justification']}",
                f"- Ceiling justification: {lens['ceiling_justification']}",
                (
                    "- Ceiling activation conditions: "
                    f"{', '.join(lens['ceiling_activation_conditions']) or 'none'}"
                ),
                f"- Duplicate/variant check: {lens['duplicate_review_prompt']}",
                f"- Cluster delta check: {lens['cluster_delta_prompt']}",
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
            "- Which assets are near duplicates, variants, superseded copies, or merge candidates?",
            "- Which clusters need a delta review before any merge or deletion decision?",
            "- Which projected future-value edges should stay notes until direct evidence exists?",
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


def _path_for_evidence(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _noted_review_lines(
    records: list[AssetCalibrationReviewRecord], field: str, empty_message: str
) -> list[str]:
    noted = [record for record in records if getattr(record, field)]
    if not noted:
        return [f"- {empty_message}"]
    lines: list[str] = []
    for record in sorted(noted, key=lambda item: item.sample_id)[:10]:
        lines.append(
            f"- `{record.sample_id}` `{record.asset_id}` `{record.asset_title}`: "
            f"{getattr(record, field)}"
        )
    return lines


def asset_calibration_evidence_markdown(
    repo_root: Path, records: list[AssetCalibrationReviewRecord], source_path: Path
) -> str:
    summary = summarize_asset_calibration_reviews(records)
    if summary["reviewed_count"] < 50:
        raise ValueError("Asset calibration evidence requires at least 50 reviewed asset ratings.")
    if not summary["structured_notes_complete"]:
        raise ValueError(
            "Asset calibration evidence requires false-positive, false-negative, "
            "and weight-change notes."
        )
    reviewed = [record for record in records if not _review_is_pending(record)]
    missing_reviewers = [record.sample_id for record in reviewed if not record.reviewer]
    if missing_reviewers:
        raise ValueError(
            "Asset calibration evidence requires reviewer values for reviewed records: "
            + ", ".join(missing_reviewers[:10])
        )

    reviewers = sorted({record.reviewer for record in reviewed if record.reviewer})
    lines = [
        "# Phase 2 Asset Calibration Evidence",
        "",
        "Human-reviewed asset score calibration evidence. Generated scores remain "
        "heuristics and do not become source-repository truth.",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Source review file: `{_path_for_evidence(repo_root, source_path)}`",
        f"- Reviewers: {', '.join(reviewers)}",
        f"- Template records: **{summary['template_count']}**",
        f"- Reviewed records: **{summary['reviewed_count']}**",
        f"- Calibration gate complete: **{summary['calibration_gate_complete']}**",
        f"- Score rating counts: `{summary['score_rating_counts']}`",
        f"- Value band counts: `{summary['value_band_counts']}`",
        f"- False positive notes: **{summary['false_positive_note_count']}**",
        f"- False negative notes: **{summary['false_negative_note_count']}**",
        f"- Weight change notes: **{summary['weight_change_note_count']}**",
        "",
        "## Authority Boundary",
        "",
        "- Human labels calibrate the catalog scoring model.",
        "- They do not mutate source repositories.",
        "- They do not promote generated metadata, alerts, synergies, or scores to truth.",
        "",
        "## False Positive Notes",
        "",
        *_noted_review_lines(
            records, "false_positive_reason", "No false positive notes were recorded."
        ),
        "",
        "## False Negative Notes",
        "",
        *_noted_review_lines(
            records, "false_negative_note", "No false negative notes were recorded."
        ),
        "",
        "## Weight Change Notes",
        "",
        *_noted_review_lines(
            records, "weight_change_note", "No weight change notes were recorded."
        ),
        "",
        "## Remaining Risks",
        "",
        "- Calibration reflects this review set and should be revisited after broader scans.",
        "- GitHub inventory remains deferred until separately approved.",
        "",
    ]
    return "\n".join(lines)


def write_asset_calibration_evidence(
    repo_root: Path,
    records: list[AssetCalibrationReviewRecord],
    source_path: Path,
    output: Path | None = None,
) -> tuple[dict[str, Any], str]:
    output_path = output or repo_root / "roadmap" / "evidence" / "phase-2-asset-calibration.md"
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    text = asset_calibration_evidence_markdown(repo_root, records, source_path)
    atomic_write_text(output_path, text + "\n")
    evidence_path = _path_for_evidence(repo_root, output_path)
    source_evidence_path = _path_for_evidence(repo_root, source_path)
    reviewer = ", ".join(sorted({record.reviewer for record in records if record.reviewer}))
    record_human_gate_evidence(
        repo_root,
        phase_id="phase-2-calibration",
        gate_id="phase-2-asset-ratings-reviewed",
        reviewer=reviewer,
        summary="At least 50 asset calibration review records have human ratings.",
        evidence=[evidence_path, source_evidence_path],
    )
    record_human_gate_evidence(
        repo_root,
        phase_id="phase-2-calibration",
        gate_id="phase-2-false-positive-negative-notes-captured",
        reviewer=reviewer,
        summary="False-positive and false-negative calibration notes were captured.",
        evidence=[evidence_path, source_evidence_path],
    )
    record_human_gate_evidence(
        repo_root,
        phase_id="phase-2-calibration",
        gate_id="phase-2-weight-changes-documented",
        reviewer=reviewer,
        summary="Asset scoring weight-change notes were documented.",
        evidence=[evidence_path, source_evidence_path],
    )
    return summarize_asset_calibration_reviews(records), str(output_path)


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
