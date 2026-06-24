from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Literal

from .ids import stable_id
from .models import (
    ActivationTrigger,
    AlertRecord,
    AssetRecord,
    ConfidenceLabel,
    EdgeRecord,
    SynergyRecord,
)
from .utils import jaccard, utc_now


def _confidence(score: float) -> ConfidenceLabel:
    return "high" if score >= 0.78 else "medium" if score >= 0.55 else "low"


def _synergy_candidate_pairs(
    assets: list[AssetRecord], max_candidates: int
) -> list[tuple[AssetRecord, AssetRecord]]:
    """Generate bounded candidates through inverted semantic facets, not full all-pairs."""
    eligible = [
        asset
        for asset in assets
        if asset.asset_type != "repository"
        and (asset.capabilities or asset.needs or asset.outcomes)
    ]
    by_id = {asset.asset_id: asset for asset in eligible}
    postings: dict[str, set[str]] = {}
    providers: dict[str, set[str]] = {}
    needers: dict[str, set[str]] = {}
    for asset in eligible:
        for value in asset.outcomes:
            postings.setdefault(f"outcome:{value}", set()).add(asset.asset_id)
        for value in asset.tags:
            postings.setdefault(f"tag:{value}", set()).add(asset.asset_id)
        for value in asset.capabilities:
            providers.setdefault(value, set()).add(asset.asset_id)
        for value in asset.needs:
            needers.setdefault(value, set()).add(asset.asset_id)

    pairs: set[tuple[str, str]] = set()
    for ids in postings.values():
        if len(ids) > 100:
            continue
        for left, right in combinations(sorted(ids), 2):
            pairs.add((left, right))
    for capability, provider_ids in providers.items():
        for provider in provider_ids:
            for needer in needers.get(capability, set()):
                if provider != needer:
                    left_id, right_id = sorted((provider, needer))
                    pairs.add((left_id, right_id))

    ranked = sorted(
        pairs,
        key=lambda pair: (
            by_id[pair[0]].value_score + by_id[pair[1]].value_score,
            pair,
        ),
        reverse=True,
    )[:max_candidates]
    return [(by_id[left], by_id[right]) for left, right in ranked]


def detect_synergies(assets: list[AssetRecord], max_candidates: int = 20000) -> list[SynergyRecord]:
    records: list[SynergyRecord] = []
    for left, right in _synergy_candidate_pairs(assets, max_candidates):
        shared_outcomes = sorted(set(left.outcomes) & set(right.outcomes))
        left_covers = set(left.capabilities) & set(right.needs)
        right_covers = set(right.capabilities) & set(left.needs)
        needs_covered = sorted(left_covers | right_covers)
        capability_union = set(left.capabilities) | set(right.capabilities)
        capability_overlap = set(left.capabilities) & set(right.capabilities)
        complementary = sorted(capability_union - capability_overlap)
        tag_overlap = jaccard(left.tags, right.tags)
        outcome_score = min(1.0, len(shared_outcomes) / 2) if shared_outcomes else 0.0
        need_score = min(1.0, len(needs_covered) / 2) if needs_covered else 0.0
        diversity = min(1.0, len(complementary) / 5) if complementary else 0.0
        score = 0.35 * outcome_score + 0.35 * need_score + 0.20 * diversity + 0.10 * tag_overlap
        if score < 0.35:
            continue
        missing = sorted(
            (set(left.needs) | set(right.needs)) - set(left.capabilities) - set(right.capabilities)
        )
        records.append(
            SynergyRecord(
                synergy_id=stable_id("synergy", *sorted([left.asset_id, right.asset_id])),
                asset_ids=[left.asset_id, right.asset_id],
                score=round(score, 4),
                confidence=_confidence(score),
                shared_outcomes=shared_outcomes,
                complementary_capabilities=complementary,
                needs_covered=needs_covered,
                missing_parts=missing,
                integration_hypothesis=f"Combine '{left.title}' and '{right.title}' to pursue {', '.join(shared_outcomes or needs_covered or complementary[:3])}.",
                evidence={
                    "left": left.logical_path,
                    "right": right.logical_path,
                    "tag_overlap": round(tag_overlap, 4),
                    "candidate_generation": "inverted_semantic_facets",
                    "heuristic_only": True,
                },
            )
        )
    return sorted(records, key=lambda record: record.score, reverse=True)


def activation_triggers(assets: list[AssetRecord]) -> list[ActivationTrigger]:
    all_capabilities = set().union(*(set(a.capabilities) for a in assets)) if assets else set()
    triggers: list[ActivationTrigger] = []
    for asset in assets:
        missing = sorted(set(asset.needs) - all_capabilities)
        if asset.lifecycle_state in {"dormant", "stale"} or missing:
            triggers.append(
                ActivationTrigger(
                    trigger_id=stable_id(
                        "trigger", asset.asset_id, *(missing or [asset.freshness_status])
                    ),
                    asset_id=asset.asset_id,
                    trigger_type="missing_dependency_available"
                    if missing
                    else "related_asset_created",
                    condition=(
                        f"Re-evaluate when capabilities become available: {', '.join(missing)}"
                        if missing
                        else "Re-evaluate when a new related asset, user goal, standard, or model capability appears."
                    ),
                    missing_parts=missing,
                    evidence_required=[
                        "new asset or source revision",
                        "reviewed relationship evidence",
                        "updated value and risk score",
                    ],
                )
            )
    return triggers


def generate_alerts(
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    synergies: list[SynergyRecord],
    triggers: list[ActivationTrigger],
    scan_id: str,
    orphan_degree_threshold: int,
    synergy_threshold: float,
    high_value_threshold: float,
) -> list[AlertRecord]:
    now = utc_now()
    degree: Counter[str] = Counter()
    for edge in edges:
        degree[edge.source_asset_id] += 1
        degree[edge.target_asset_id] += 1
    alerts: list[AlertRecord] = []
    by_id = {a.asset_id: a for a in assets}
    for asset in assets:
        if asset.asset_type != "repository" and degree[asset.asset_id] <= orphan_degree_threshold:
            severity: Literal["high", "medium", "low"] = (
                "high"
                if asset.value_score >= high_value_threshold
                else "medium"
                if asset.value_score >= 45
                else "low"
            )
            alerts.append(
                AlertRecord(
                    alert_id=stable_id("alert", scan_id, "orphan", asset.asset_id),
                    created_at=now,
                    alert_type="orphan_asset",
                    severity=severity,
                    title=f"Orphan candidate: {asset.title}",
                    description="The asset has few graph connections and may be hidden, under-described, intentionally isolated, or missing relationship metadata.",
                    asset_ids=[asset.asset_id],
                    evidence={
                        "degree": degree[asset.asset_id],
                        "value_score": asset.value_score,
                        "logical_path": asset.logical_path,
                    },
                    recommended_action="Review the asset, declare intentional isolation or add evidence-backed relationships and missing metadata.",
                    scan_id=scan_id,
                )
            )
        if asset.freshness_status == "stale" and asset.lifecycle_state != "archived":
            alerts.append(
                AlertRecord(
                    alert_id=stable_id("alert", scan_id, "stale", asset.asset_id),
                    created_at=now,
                    alert_type="stale_asset",
                    severity="medium" if asset.value_score >= 50 else "low",
                    title=f"Stale asset review: {asset.title}",
                    description="The asset exceeded its type-specific staleness threshold.",
                    asset_ids=[asset.asset_id],
                    evidence={
                        "modified_at": asset.modified_at,
                        "asset_type": asset.asset_type,
                        "value_score": asset.value_score,
                    },
                    recommended_action="Confirm whether it remains valid, needs refresh, should be deprecated, or is intentionally archival.",
                    scan_id=scan_id,
                )
            )
        if asset.needs:
            alerts.append(
                AlertRecord(
                    alert_id=stable_id("alert", scan_id, "needs", asset.asset_id),
                    created_at=now,
                    alert_type="missing_part_candidate",
                    severity="medium",
                    title=f"Missing-part candidate: {asset.title}",
                    description=f"Declared or inferred needs: {', '.join(asset.needs)}.",
                    asset_ids=[asset.asset_id],
                    evidence={"needs": asset.needs, "capabilities": asset.capabilities},
                    recommended_action="Review the missing parts, search internal assets first, then use bounded external research if still unresolved.",
                    scan_id=scan_id,
                )
            )
    for synergy in synergies:
        if synergy.score >= synergy_threshold:
            titles = [by_id[aid].title for aid in synergy.asset_ids if aid in by_id]
            alerts.append(
                AlertRecord(
                    alert_id=stable_id("alert", scan_id, "synergy", synergy.synergy_id),
                    created_at=now,
                    alert_type="synergy_candidate",
                    severity="high" if synergy.score >= 0.8 else "medium",
                    title=f"Candidate synergy: {' + '.join(titles)}",
                    description=synergy.integration_hypothesis,
                    asset_ids=synergy.asset_ids,
                    evidence={
                        "synergy_id": synergy.synergy_id,
                        "score": synergy.score,
                        "needs_covered": synergy.needs_covered,
                        "missing_parts": synergy.missing_parts,
                    },
                    recommended_action="Create a bounded integration hypothesis, define success measures, identify authority boundaries, and test before promotion.",
                    scan_id=scan_id,
                )
            )
    return sorted(
        alerts,
        key=lambda a: (
            {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[a.severity],
            a.title,
        ),
        reverse=True,
    )


def missing_need_counts(assets: list[AssetRecord]) -> list[tuple[str, int]]:
    capabilities = set().union(*(set(a.capabilities) for a in assets)) if assets else set()
    counts: Counter[str] = Counter(
        need for asset in assets for need in asset.needs if need not in capabilities
    )
    return counts.most_common()
