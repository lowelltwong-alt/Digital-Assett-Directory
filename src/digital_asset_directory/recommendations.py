from __future__ import annotations

from collections import defaultdict

from .context_pack import rank_assets
from .ids import stable_id
from .models import AssetRecord, CapabilityRecommendation


def recommend_skills_and_agents(
    assets: list[AssetRecord], repeat_threshold: int = 3
) -> list[CapabilityRecommendation]:
    capability_assets: dict[str, list[str]] = defaultdict(list)
    need_assets: dict[str, list[str]] = defaultdict(list)
    for asset in assets:
        for capability in asset.capabilities:
            capability_assets[capability].append(asset.asset_id)
        for need in asset.needs:
            need_assets[need].append(asset.asset_id)

    recommendations: list[CapabilityRecommendation] = []
    for capability, evidence in sorted(capability_assets.items()):
        if len(evidence) < repeat_threshold:
            continue
        recommendations.append(
            CapabilityRecommendation(
                recommendation_id=stable_id("recommendation", "skill", capability),
                kind="skill",
                name=f"{capability.replace('_', ' ').title()} Skill",
                rationale=f"The capability appears across {len(evidence)} assets. A governed reusable skill may reduce repeated implementation and preserve lessons.",
                evidence_asset_ids=evidence[:50],
                capabilities=[capability],
                missing_capabilities=[],
                suggested_roles=["skill maintainer", "evaluation owner", "governance reviewer"],
                confidence="high" if len(evidence) >= repeat_threshold * 2 else "medium",
                risk="medium",
            )
        )

    all_capabilities = set(capability_assets)
    for need, evidence in sorted(need_assets.items()):
        if need in all_capabilities or len(evidence) < 2:
            continue
        recommendations.append(
            CapabilityRecommendation(
                recommendation_id=stable_id("recommendation", "research", need),
                kind="research",
                name=f"Research or Build: {need.replace('_', ' ').title()}",
                rationale=f"The need appears in {len(evidence)} assets but no cataloged asset currently declares the matching capability.",
                evidence_asset_ids=evidence[:50],
                capabilities=[],
                missing_capabilities=[need],
                suggested_roles=[
                    "research scout",
                    "license and security reviewer",
                    "integration architect",
                ],
                confidence="medium",
                risk="medium",
            )
        )
    return recommendations


def recommend_swarm(
    goal: str, assets: list[AssetRecord], limit: int = 12
) -> CapabilityRecommendation:
    ranked = rank_assets(goal, assets)[:limit]
    selected = [asset for _, asset, _ in ranked]
    capabilities = (
        sorted(set().union(*(set(asset.capabilities) for asset in selected))) if selected else []
    )
    needs = sorted(set().union(*(set(asset.needs) for asset in selected))) if selected else []
    missing = sorted(set(needs) - set(capabilities))
    roles = ["portfolio context scout", "source-authority and provenance reviewer"]
    if "build_knowledge_graph" in capabilities or "knowledge-graph" in {
        tag for asset in selected for tag in asset.tags
    }:
        roles.append("knowledge-graph curator")
    if "validate_contracts" in capabilities or "evaluation_harness" in needs:
        roles.append("evaluation and red-team engineer")
    if "govern_agents" in capabilities or any("governance" in asset.tags for asset in selected):
        roles.append("governance and authority-boundary reviewer")
    if missing:
        roles.append("missing-part research scout")
    if len(selected) > 1:
        roles.append("integration architect and synthesis lead")
    roles.append("lesson and handoff recorder")
    return CapabilityRecommendation(
        recommendation_id=stable_id("recommendation", "swarm", goal),
        kind="swarm",
        name=f"Candidate Swarm for: {goal[:100]}",
        rationale="Roles are derived from the highest-matching catalog assets, their capabilities, declared needs, and governance requirements. This is a planning candidate, not autonomous authority.",
        evidence_asset_ids=[asset.asset_id for asset in selected],
        capabilities=capabilities,
        missing_capabilities=missing,
        suggested_roles=list(dict.fromkeys(roles)),
        confidence="medium" if selected else "low",
        risk="medium",
    )
