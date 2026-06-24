from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any, Literal

from .ids import stable_id
from .models import AlertRecord, AssetRecord, EdgeRecord, ProposalRecord
from .utils import atomic_write_text, jaccard, tokens, utc_now, write_jsonl

ProposalEngineOption = Literal["bottom-up", "top-down", "both"]
ProposalEngineName = Literal["bottom_up_self_proposal", "top_down_orchestration"]
ProposalType = Literal[
    "satisfies_need",
    "strengthens_capability",
    "activates_orphan",
    "reduces_risk",
    "adds_test",
    "documents",
    "bundles_assets",
    "research_missing_part",
]

AUTHORITY_BOUNDARY = (
    "Generated candidate only; source repositories retain authority; no source mutation, "
    "graph promotion, or implementation is authorized by this proposal."
)
SAFETY_FLAGS = ["candidate_only", "source_mutation_forbidden", "human_review_required"]


@dataclass
class ProposalIndexes:
    by_id: dict[str, AssetRecord]
    eligible: dict[str, AssetRecord]
    providers_by_capability: dict[str, list[AssetRecord]]
    needers_by_need: dict[str, list[AssetRecord]]
    assets_by_outcome: dict[str, list[AssetRecord]]
    neighbors_by_asset: dict[str, set[str]]
    edge_evidence_by_pair: dict[tuple[str, str], list[dict[str, Any]]]
    alerts_by_asset: dict[str, list[AlertRecord]]
    orphan_asset_ids: set[str]
    weak_asset_ids: set[str]


def _logical_name(asset: AssetRecord) -> str:
    normalized = asset.logical_path.replace("\\", "/")
    return PurePosixPath(normalized).name.lower()


def _is_eligible(asset: AssetRecord) -> bool:
    if asset.source_kind == "generated":
        return False
    if _logical_name(asset) in {".gitkeep", ".gitignore", "thumbs.db", ".ds_store"}:
        return False
    if not asset.asset_id or not asset.logical_path:
        return False
    return True


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


def build_proposal_indexes(
    assets: list[AssetRecord], edges: list[EdgeRecord], alerts: list[AlertRecord]
) -> ProposalIndexes:
    by_id = {asset.asset_id: asset for asset in assets}
    eligible = {asset.asset_id: asset for asset in assets if _is_eligible(asset)}
    providers_by_capability: dict[str, list[AssetRecord]] = defaultdict(list)
    needers_by_need: dict[str, list[AssetRecord]] = defaultdict(list)
    assets_by_outcome: dict[str, list[AssetRecord]] = defaultdict(list)
    for asset in sorted(eligible.values(), key=lambda record: record.asset_id):
        for capability in sorted(set(asset.capabilities)):
            providers_by_capability[capability].append(asset)
        for need in sorted(set(asset.needs)):
            needers_by_need[need].append(asset)
        for outcome in sorted(set(asset.outcomes)):
            assets_by_outcome[outcome].append(asset)

    neighbors_by_asset: dict[str, set[str]] = defaultdict(set)
    edge_evidence_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        if edge.source_asset_id not in by_id or edge.target_asset_id not in by_id:
            continue
        neighbors_by_asset[edge.source_asset_id].add(edge.target_asset_id)
        neighbors_by_asset[edge.target_asset_id].add(edge.source_asset_id)
        edge_payload = {
            "edge_id": edge.edge_id,
            "edge_type": edge.edge_type,
            "method": edge.method,
            "confidence": edge.confidence,
            "evidence": edge.evidence,
        }
        edge_evidence_by_pair[(edge.source_asset_id, edge.target_asset_id)].append(edge_payload)
        edge_evidence_by_pair[(edge.target_asset_id, edge.source_asset_id)].append(edge_payload)

    alerts_by_asset: dict[str, list[AlertRecord]] = defaultdict(list)
    orphan_asset_ids: set[str] = set()
    weak_asset_ids: set[str] = set()
    for alert in alerts:
        for asset_id in alert.asset_ids:
            alerts_by_asset[asset_id].append(alert)
            if alert.alert_type == "orphan_asset":
                orphan_asset_ids.add(asset_id)
            if alert.alert_type in {"orphan_asset", "stale_asset", "missing_part_candidate"}:
                weak_asset_ids.add(asset_id)

    return ProposalIndexes(
        by_id=by_id,
        eligible=eligible,
        providers_by_capability={k: v for k, v in providers_by_capability.items()},
        needers_by_need={k: v for k, v in needers_by_need.items()},
        assets_by_outcome={k: v for k, v in assets_by_outcome.items()},
        neighbors_by_asset={k: v for k, v in neighbors_by_asset.items()},
        edge_evidence_by_pair={k: v for k, v in edge_evidence_by_pair.items()},
        alerts_by_asset={k: v for k, v in alerts_by_asset.items()},
        orphan_asset_ids=orphan_asset_ids,
        weak_asset_ids=weak_asset_ids,
    )


def _cost_label(count: int) -> Literal["low", "medium", "high"]:
    if count <= 2:
        return "low"
    if count <= 10:
        return "medium"
    return "high"


def _risk_label(assets: list[AssetRecord]) -> Literal["low", "medium", "high"]:
    if any(asset.sensitivity in {"confidential", "restricted"} for asset in assets):
        return "high"
    if any(asset.freshness_status == "stale" for asset in assets):
        return "medium"
    if any(asset.confidence == "low" for asset in assets):
        return "medium"
    return "low"


def _confidence_label(score: float) -> Literal["low", "medium", "high"]:
    if score >= 0.78:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _proposal_id(
    engine: str,
    scan_id: str,
    proposal_type: str,
    source_asset_ids: list[str],
    target_asset_ids: list[str],
    need_ids: list[str],
    capability_ids: list[str],
) -> str:
    return stable_id(
        "proposal",
        engine,
        scan_id,
        proposal_type,
        ",".join(sorted(source_asset_ids)),
        ",".join(sorted(target_asset_ids)),
        ",".join(sorted(need_ids)),
        ",".join(sorted(capability_ids)),
    )


def _new_proposal(
    *,
    engine: ProposalEngineName,
    proposal_type: ProposalType,
    source_asset_ids: list[str],
    target_asset_ids: list[str],
    need_ids: list[str],
    capability_ids: list[str],
    rationale: str,
    evidence: dict[str, Any],
    smallest_bounded_experiment: str,
    expected_benefit: str,
    assets_by_id: dict[str, AssetRecord],
    scan_id: str,
    generated_at: str,
    score: float,
    known_risks: list[str] | None = None,
) -> ProposalRecord | None:
    source_ids = sorted(dict.fromkeys(source_asset_ids))
    target_ids = sorted(dict.fromkeys(target_asset_ids))
    if not source_ids or set(source_ids) & set(target_ids):
        return None
    if not evidence:
        return None
    involved = [assets_by_id[aid] for aid in source_ids + target_ids if aid in assets_by_id]
    proposal = ProposalRecord(
        proposal_id=_proposal_id(
            engine,
            scan_id,
            proposal_type,
            source_ids,
            target_ids,
            need_ids,
            capability_ids,
        ),
        proposal_engine=engine,
        proposal_type=proposal_type,
        source_asset_ids=source_ids,
        target_asset_ids=target_ids,
        need_ids=sorted(dict.fromkeys(need_ids)),
        capability_ids=sorted(dict.fromkeys(capability_ids)),
        rationale=rationale,
        evidence={"score": round(score, 4), **evidence},
        smallest_bounded_experiment=smallest_bounded_experiment,
        expected_benefit=expected_benefit,
        known_risks=known_risks or [
            "Generated proposal may be a false positive; review provenance before acting."
        ],
        authority_boundary=AUTHORITY_BOUNDARY,
        confidence=_confidence_label(score),
        risk=_risk_label(involved),
        estimated_review_cost=_cost_label(len(involved)),
        estimated_integration_cost=_cost_label(len(source_ids) + len(target_ids)),
        safety_flags=SAFETY_FLAGS.copy(),
        generated_at=generated_at,
        scan_id=scan_id,
    )
    if proposal.review_status != "generated_candidate":
        return None
    return proposal


def generate_bottom_up_proposals(
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    alerts: list[AlertRecord],
    scan_id: str,
    per_asset_limit: int = 3,
    generated_at: str | None = None,
) -> list[ProposalRecord]:
    indexes = build_proposal_indexes(assets, edges, alerts)
    generated = generated_at or utc_now()
    proposals: list[ProposalRecord] = []
    for target in sorted(indexes.eligible.values(), key=lambda record: record.asset_id):
        candidates: list[tuple[float, ProposalRecord]] = []
        target_tokens = _asset_tokens(target)
        target_alerts = indexes.alerts_by_asset.get(target.asset_id, [])
        alert_ids = [alert.alert_id for alert in target_alerts]
        is_weak = target.asset_id in indexes.weak_asset_ids or not indexes.neighbors_by_asset.get(
            target.asset_id
        )

        for need in sorted(set(target.needs)):
            for provider in indexes.providers_by_capability.get(need, []):
                if provider.asset_id == target.asset_id:
                    continue
                shared_outcomes = sorted(set(provider.outcomes) & set(target.outcomes))
                edge_evidence = indexes.edge_evidence_by_pair.get(
                    (provider.asset_id, target.asset_id), []
                )
                score = 0.72 + 0.05 * len(shared_outcomes) + 0.03 * len(edge_evidence)
                if target.asset_id in indexes.orphan_asset_ids:
                    score += 0.08
                proposal_type = "activates_orphan" if is_weak else "satisfies_need"
                proposal = _new_proposal(
                    engine="bottom_up_self_proposal",
                    proposal_type=proposal_type,
                    source_asset_ids=[provider.asset_id],
                    target_asset_ids=[target.asset_id],
                    need_ids=[need],
                    capability_ids=[need],
                    rationale=(
                        f"{provider.title} declares `{need}` capability that may address "
                        f"{target.title}'s declared need."
                    ),
                    evidence={
                        "matched_need": need,
                        "provider_capabilities": provider.capabilities,
                        "target_needs": target.needs,
                        "shared_outcomes": shared_outcomes,
                        "edge_evidence": edge_evidence[:5],
                        "alert_ids": alert_ids,
                    },
                    smallest_bounded_experiment=(
                        "Review the provider and target assets together, then draft a one-page "
                        "candidate integration note without changing either source artifact."
                    ),
                    expected_benefit="A declared missing capability may become actionable.",
                    assets_by_id=indexes.by_id,
                    scan_id=scan_id,
                    generated_at=generated,
                    score=min(score, 0.95),
                )
                if proposal:
                    candidates.append((float(proposal.evidence["score"]), proposal))

        for provider in indexes.eligible.values():
            if provider.asset_id == target.asset_id:
                continue
            shared_outcomes = sorted(set(provider.outcomes) & set(target.outcomes))
            if not shared_outcomes:
                continue
            similarity = jaccard(target_tokens, _asset_tokens(provider))
            if similarity < 0.08:
                continue
            shared_capabilities = sorted(set(provider.capabilities) & set(target.capabilities))
            if shared_capabilities and not target.needs:
                proposal_type = "strengthens_capability"
            elif provider.asset_type == "test":
                proposal_type = "adds_test"
            elif provider.asset_type == "document":
                proposal_type = "documents"
            else:
                proposal_type = "strengthens_capability"
            score = min(0.72, 0.32 + similarity + 0.08 * len(shared_outcomes))
            proposal = _new_proposal(
                engine="bottom_up_self_proposal",
                proposal_type=proposal_type,
                source_asset_ids=[provider.asset_id],
                target_asset_ids=[target.asset_id],
                need_ids=[],
                capability_ids=provider.capabilities[:8],
                rationale=(
                    f"{provider.title} and {target.title} share outcomes that may support "
                    "a bounded reuse or strengthening proposal."
                ),
                evidence={
                    "shared_outcomes": shared_outcomes,
                    "similarity": round(similarity, 4),
                    "provider_asset_type": provider.asset_type,
                    "target_asset_type": target.asset_type,
                    "alert_ids": alert_ids,
                },
                smallest_bounded_experiment=(
                    "Compare the two assets' entrypoints and capture one concrete reuse, "
                    "test, or documentation candidate for human review."
                ),
                expected_benefit="Related assets may reduce duplicated effort or clarify reuse paths.",
                assets_by_id=indexes.by_id,
                scan_id=scan_id,
                generated_at=generated,
                score=score,
            )
            if proposal:
                candidates.append((float(proposal.evidence["score"]), proposal))

        unique: dict[str, ProposalRecord] = {}
        for _, proposal in sorted(
            candidates,
            key=lambda item: (
                item[0],
                bool(item[1].need_ids),
                item[1].proposal_type,
                item[1].proposal_id,
            ),
            reverse=True,
        ):
            unique.setdefault(proposal.proposal_id, proposal)
            if len(unique) >= per_asset_limit:
                break
        proposals.extend(unique.values())
    return sorted(proposals, key=lambda record: (record.source_asset_ids, record.target_asset_ids))


def generate_top_down_proposals(
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    alerts: list[AlertRecord],
    scan_id: str,
    portfolio_limit: int = 20,
    generated_at: str | None = None,
) -> list[ProposalRecord]:
    indexes = build_proposal_indexes(assets, edges, alerts)
    generated = generated_at or utc_now()
    candidates: list[tuple[float, ProposalRecord]] = []

    for need, needers in sorted(indexes.needers_by_need.items()):
        providers = indexes.providers_by_capability.get(need, [])
        source_ids = [provider.asset_id for provider in providers[:10]]
        target_ids = [needer.asset_id for needer in needers[:10] if needer.asset_id not in source_ids]
        if providers and target_ids:
            score = min(0.96, 0.58 + 0.06 * len(needers) + 0.04 * len(providers))
            proposal = _new_proposal(
                engine="top_down_orchestration",
                proposal_type="bundles_assets" if len(source_ids) + len(target_ids) > 2 else "satisfies_need",
                source_asset_ids=source_ids,
                target_asset_ids=target_ids,
                need_ids=[need],
                capability_ids=[need],
                rationale=(
                    f"Portfolio scan found `{need}` as both a declared need and a declared "
                    "capability; a governed review can connect providers to needers."
                ),
                evidence={
                    "need": need,
                    "provider_count": len(providers),
                    "needer_count": len(needers),
                    "provider_asset_ids": [provider.asset_id for provider in providers],
                    "needer_asset_ids": [needer.asset_id for needer in needers],
                },
                smallest_bounded_experiment=(
                    "Review the top provider and top needer for this need, then accept, reject, "
                    "or split the proposed bundle into smaller candidate links."
                ),
                expected_benefit="A repeated portfolio need may be connected to existing assets.",
                assets_by_id=indexes.by_id,
                scan_id=scan_id,
                generated_at=generated,
                score=score,
            )
            if proposal:
                candidates.append((float(proposal.evidence["score"]), proposal))
        elif needers:
            score = min(0.86, 0.48 + 0.06 * len(needers))
            proposal = _new_proposal(
                engine="top_down_orchestration",
                proposal_type="research_missing_part",
                source_asset_ids=[needer.asset_id for needer in needers[:20]],
                target_asset_ids=[],
                need_ids=[need],
                capability_ids=[],
                rationale=(
                    f"`{need}` appears as a declared need, but no cataloged eligible asset "
                    "currently declares the matching capability."
                ),
                evidence={
                    "need": need,
                    "needer_count": len(needers),
                    "needer_asset_ids": [needer.asset_id for needer in needers],
                    "provider_count": 0,
                },
                smallest_bounded_experiment=(
                    "Create a human-reviewed research note for this missing part before "
                    "searching external repositories or importing code."
                ),
                expected_benefit="A repeated missing capability can become a governed research task.",
                assets_by_id=indexes.by_id,
                scan_id=scan_id,
                generated_at=generated,
                score=score,
                known_risks=[
                    "External research may require license, provenance, security, and compatibility review."
                ],
            )
            if proposal:
                candidates.append((float(proposal.evidence["score"]), proposal))

    for orphan_id in sorted(indexes.orphan_asset_ids):
        orphan = indexes.eligible.get(orphan_id)
        if not orphan:
            continue
        helper_ids: list[str] = []
        matched_needs: list[str] = []
        for need in orphan.needs:
            for provider in indexes.providers_by_capability.get(need, []):
                if provider.asset_id != orphan.asset_id:
                    helper_ids.append(provider.asset_id)
                    matched_needs.append(need)
        if not helper_ids:
            for outcome in orphan.outcomes:
                helper_ids.extend(
                    asset.asset_id
                    for asset in indexes.assets_by_outcome.get(outcome, [])
                    if asset.asset_id != orphan.asset_id
                )
        helper_ids = sorted(dict.fromkeys(helper_ids))[:5]
        if not helper_ids:
            continue
        proposal = _new_proposal(
            engine="top_down_orchestration",
            proposal_type="activates_orphan",
            source_asset_ids=helper_ids,
            target_asset_ids=[orphan.asset_id],
            need_ids=matched_needs,
            capability_ids=matched_needs,
            rationale=(
                f"{orphan.title} is flagged as weak or orphaned; candidate helpers may provide "
                "an activation path."
            ),
            evidence={
                "orphan_asset_id": orphan.asset_id,
                "helper_asset_ids": helper_ids,
                "matched_needs": matched_needs,
                "alert_ids": [alert.alert_id for alert in indexes.alerts_by_asset[orphan.asset_id]],
            },
            smallest_bounded_experiment=(
                "Open the orphan asset with the top helper and decide whether to add a reviewed "
                "activation note or dismiss the candidate."
            ),
            expected_benefit="A disconnected asset may gain a reviewable activation path.",
            assets_by_id=indexes.by_id,
            scan_id=scan_id,
            generated_at=generated,
            score=0.7 + 0.03 * len(helper_ids),
        )
        if proposal:
            candidates.append((float(proposal.evidence["score"]), proposal))

    stale_alerts = [alert for alert in alerts if alert.alert_type == "stale_asset"]
    for alert in sorted(stale_alerts, key=lambda record: record.alert_id):
        source_ids = [aid for aid in alert.asset_ids if aid in indexes.eligible]
        if not source_ids:
            continue
        proposal = _new_proposal(
            engine="top_down_orchestration",
            proposal_type="reduces_risk",
            source_asset_ids=source_ids,
            target_asset_ids=[],
            need_ids=[],
            capability_ids=[],
            rationale=f"{alert.title} may need a freshness or risk review.",
            evidence={
                "alert_id": alert.alert_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "recommended_action": alert.recommended_action,
            },
            smallest_bounded_experiment=(
                "Review freshness evidence and either renew, archive, or dismiss the stale alert."
            ),
            expected_benefit="Risky or stale assets can be triaged without source mutation.",
            assets_by_id=indexes.by_id,
            scan_id=scan_id,
            generated_at=generated,
            score=0.62,
        )
        if proposal:
            candidates.append((float(proposal.evidence["score"]), proposal))

    unique: dict[str, ProposalRecord] = {}
    for _, proposal in sorted(
        candidates,
        key=lambda item: (item[0], len(item[1].source_asset_ids), item[1].proposal_id),
        reverse=True,
    ):
        unique.setdefault(proposal.proposal_id, proposal)
        if len(unique) >= portfolio_limit:
            break
    return list(unique.values())


def _proposal_metrics(proposals: list[ProposalRecord]) -> dict[str, Any]:
    total = len(proposals)
    unique_ids = {proposal.proposal_id for proposal in proposals}
    needs = {need for proposal in proposals for need in proposal.need_ids}
    orphan_targets = {
        asset_id
        for proposal in proposals
        if proposal.proposal_type == "activates_orphan"
        for asset_id in proposal.target_asset_ids
    }
    safety_passes = [
        proposal.review_status == "generated_candidate"
        and not (set(proposal.source_asset_ids) & set(proposal.target_asset_ids))
        and "source repositories retain authority" in proposal.authority_boundary
        for proposal in proposals
    ]
    evidence_complete = [bool(proposal.evidence) for proposal in proposals]
    return {
        "proposal_count": total,
        "distinct_needs_covered": len(needs),
        "orphan_activation_coverage": len(orphan_targets),
        "duplicate_count": total - len(unique_ids),
        "self_match_violations": sum(
            1 for proposal in proposals if set(proposal.source_asset_ids) & set(proposal.target_asset_ids)
        ),
        "safety_pass_rate": round(sum(safety_passes) / total, 4) if total else 1.0,
        "evidence_completeness_rate": round(sum(evidence_complete) / total, 4) if total else 1.0,
        "proposal_types": dict(Counter(proposal.proposal_type for proposal in proposals)),
    }


def build_proposal_comparison(
    bottom_up: list[ProposalRecord],
    top_down: list[ProposalRecord],
    review_sample: int = 25,
) -> dict[str, Any]:
    combined = sorted(bottom_up + top_down, key=lambda record: record.proposal_id)
    sample = [
        {
            "sample_id": f"review-{index:03d}",
            "proposal_id": proposal.proposal_id,
            "proposal_type": proposal.proposal_type,
            "source_asset_ids": proposal.source_asset_ids,
            "target_asset_ids": proposal.target_asset_ids,
            "need_ids": proposal.need_ids,
            "rationale": proposal.rationale,
            "smallest_bounded_experiment": proposal.smallest_bounded_experiment,
        }
        for index, proposal in enumerate(combined[:review_sample], start=1)
    ]
    return {
        "bottom_up": _proposal_metrics(bottom_up),
        "top_down": _proposal_metrics(top_down),
        "combined": _proposal_metrics(combined),
        "review_sample_size": len(sample),
        "review_sample": sample,
        "review_sample_note": "Engine labels are omitted from review sample items; JSONL retains them.",
    }


def _proposal_lines(title: str, proposals: list[ProposalRecord]) -> list[str]:
    lines = [f"## {title}", ""]
    if not proposals:
        lines.extend(["- No proposals generated.", ""])
        return lines
    for proposal in proposals[:25]:
        lines.extend(
            [
                f"### {proposal.proposal_type}: {proposal.proposal_id}",
                f"- Confidence: `{proposal.confidence}`",
                f"- Risk: `{proposal.risk}`",
                f"- Needs: {', '.join(proposal.need_ids) or 'none'}",
                f"- Sources: {', '.join(proposal.source_asset_ids)}",
                f"- Targets: {', '.join(proposal.target_asset_ids) or 'none'}",
                f"- Rationale: {proposal.rationale}",
                f"- Smallest experiment: {proposal.smallest_bounded_experiment}",
                "",
            ]
        )
    return lines


def comparison_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Proposal Engine Comparison",
        "",
        "Generated proposal candidates only. Review before acting; no source mutation or promotion is implied.",
        "",
    ]
    for label, metrics in [
        ("Bottom-up self-proposal", comparison["bottom_up"]),
        ("Top-down orchestration", comparison["top_down"]),
        ("Combined", comparison["combined"]),
    ]:
        lines.extend(
            [
                f"## {label}",
                f"- Proposals: **{metrics['proposal_count']}**",
                f"- Distinct needs covered: **{metrics['distinct_needs_covered']}**",
                f"- Orphan activation coverage: **{metrics['orphan_activation_coverage']}**",
                f"- Duplicate count: **{metrics['duplicate_count']}**",
                f"- Self-match violations: **{metrics['self_match_violations']}**",
                f"- Safety pass rate: **{metrics['safety_pass_rate']}**",
                f"- Evidence completeness rate: **{metrics['evidence_completeness_rate']}**",
                f"- Proposal types: `{metrics['proposal_types']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Review Sample",
            "",
            comparison["review_sample_note"],
            "",
            f"- Sample size: **{comparison['review_sample_size']}**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def review_sample_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Proposal Review Sample",
        "",
        "Engine labels are hidden here for review calibration. Use proposal IDs to unblind after scoring.",
        "",
    ]
    for item in comparison["review_sample"]:
        lines.extend(
            [
                f"## {item['sample_id']}",
                f"- Proposal ID: `{item['proposal_id']}`",
                f"- Type: `{item['proposal_type']}`",
                f"- Needs: {', '.join(item['need_ids']) or 'none'}",
                f"- Sources: {', '.join(item['source_asset_ids'])}",
                f"- Targets: {', '.join(item['target_asset_ids']) or 'none'}",
                f"- Rationale: {item['rationale']}",
                f"- Smallest experiment: {item['smallest_bounded_experiment']}",
                "- Human useful? `[ ] yes  [ ] no  [ ] unsure`",
                "- Safe to pursue? `[ ] yes  [ ] no  [ ] needs more review`",
                "- Notes:",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_proposal_outputs(
    repo_root: Path,
    bottom_up: list[ProposalRecord],
    top_down: list[ProposalRecord],
    comparison: dict[str, Any],
) -> dict[str, str]:
    bottom_path = repo_root / "processed" / "proposals" / "bottom_up_proposals.jsonl"
    top_path = repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
    comparison_path = repo_root / "processed" / "reports" / "proposal_engine_comparison.md"
    review_path = repo_root / "processed" / "reports" / "proposal_review_sample.md"
    write_jsonl(bottom_path, [proposal.model_dump(mode="json") for proposal in bottom_up])
    write_jsonl(top_path, [proposal.model_dump(mode="json") for proposal in top_down])
    atomic_write_text(comparison_path, comparison_markdown(comparison))
    atomic_write_text(review_path, review_sample_markdown(comparison))
    return {
        "bottom_up": str(bottom_path),
        "top_down": str(top_path),
        "comparison": str(comparison_path),
        "review_sample": str(review_path),
    }


def run_proposal_engines(
    *,
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    alerts: list[AlertRecord],
    scan_id: str,
    engine: ProposalEngineOption = "both",
    per_asset_limit: int = 3,
    portfolio_limit: int = 20,
    review_sample: int = 25,
    generated_at: str | None = None,
) -> tuple[list[ProposalRecord], list[ProposalRecord], dict[str, Any]]:
    generated = generated_at or utc_now()
    bottom_up: list[ProposalRecord] = []
    top_down: list[ProposalRecord] = []
    if engine in {"bottom-up", "both"}:
        bottom_up = generate_bottom_up_proposals(
            assets, edges, alerts, scan_id, per_asset_limit, generated
        )
    if engine in {"top-down", "both"}:
        top_down = generate_top_down_proposals(
            assets, edges, alerts, scan_id, portfolio_limit, generated
        )
    comparison = build_proposal_comparison(bottom_up, top_down, review_sample)
    return bottom_up, top_down, comparison
