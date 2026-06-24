from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any, Literal

from .ids import stable_id
from .models import AlertRecord, AssetRecord, EdgeRecord, ProposalRecord, ProposalReviewRecord
from .utils import atomic_write_text, jaccard, tokens, utc_now, write_jsonl

ProposalEngineOption = Literal["bottom-up", "top-down", "both"]
ProposalEngineName = Literal["bottom_up_self_proposal", "top_down_orchestration"]
CalibrationDefaultPath = Literal["bottom_up_self_proposal", "top_down_orchestration", "hybrid"]
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
REVIEW_LABELS = {
    "usefulness": {"unreviewed", "useful", "not_useful", "unsure"},
    "safety": {"unreviewed", "safe", "unsafe", "needs_more_review"},
    "novelty": {"unreviewed", "novel", "already_known", "unsure"},
    "actionability": {"unreviewed", "actionable", "not_actionable", "unsure"},
    "decision": {"pending", "accept_candidate", "reject_candidate", "defer"},
}
REVIEW_DEFAULT_LABELS = {
    "usefulness": "unreviewed",
    "safety": "unreviewed",
    "novelty": "unreviewed",
    "actionability": "unreviewed",
    "decision": "pending",
}
REVIEW_CALIBRATION_NOTE_FIELDS = [
    "false_positive_reason",
    "false_negative_note",
    "useful_example_note",
]
REVIEW_CSV_COLUMNS = [
    "sample_id",
    "proposal_id",
    "proposal_engine",
    "proposal_type",
    "source_asset_ids",
    "target_asset_ids",
    "need_ids",
    "confidence",
    "risk",
    "rationale",
    "smallest_bounded_experiment",
    "reviewer",
    "usefulness",
    "safety",
    "novelty",
    "actionability",
    "decision",
    "notes",
    "false_positive_reason",
    "false_negative_note",
    "useful_example_note",
]
BLINDED_REVIEW_CSV_COLUMNS = [
    column for column in REVIEW_CSV_COLUMNS if column != "proposal_engine"
]
REVIEW_UNBLIND_CSV_COLUMNS = ["sample_id", "proposal_id", "proposal_engine"]
CALIBRATION_DEFAULT_PATHS = {
    "bottom_up_self_proposal",
    "top_down_orchestration",
    "hybrid",
}


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
    actionable_experiments = [
        bool(proposal.smallest_bounded_experiment.strip()) for proposal in proposals
    ]
    candidate_status_passes = [
        proposal.review_status == "generated_candidate" for proposal in proposals
    ]
    authority_boundary_passes = [
        "source repositories retain authority" in proposal.authority_boundary
        and "no source mutation" in proposal.authority_boundary
        for proposal in proposals
    ]
    external_review_risks = [
        proposal
        for proposal in proposals
        if any(
            term in " ".join(proposal.known_risks).lower()
            for term in ("external", "license", "security", "compatibility")
        )
    ]
    research_missing_part = [
        proposal for proposal in proposals if proposal.proposal_type == "research_missing_part"
    ]
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
        "actionable_experiment_rate": round(sum(actionable_experiments) / total, 4)
        if total
        else 1.0,
        "candidate_status_pass_rate": round(sum(candidate_status_passes) / total, 4)
        if total
        else 1.0,
        "authority_boundary_pass_rate": round(sum(authority_boundary_passes) / total, 4)
        if total
        else 1.0,
        "estimated_review_cost_counts": dict(
            Counter(proposal.estimated_review_cost for proposal in proposals)
        ),
        "estimated_integration_cost_counts": dict(
            Counter(proposal.estimated_integration_cost for proposal in proposals)
        ),
        "external_review_risk_count": len(external_review_risks),
        "research_missing_part_count": len(research_missing_part),
        "human_usefulness_metrics_available": False,
        "proposal_types": dict(Counter(proposal.proposal_type for proposal in proposals)),
    }


def build_proposal_review_template(
    bottom_up: list[ProposalRecord],
    top_down: list[ProposalRecord],
    per_engine_sample: int = 25,
) -> list[ProposalReviewRecord]:
    selected: list[ProposalRecord] = [
        *sorted(bottom_up, key=lambda record: record.proposal_id)[:per_engine_sample],
        *sorted(top_down, key=lambda record: record.proposal_id)[:per_engine_sample],
    ]
    records: list[ProposalReviewRecord] = []
    for index, proposal in enumerate(selected, start=1):
        sample_id = f"review-{index:03d}"
        records.append(
            ProposalReviewRecord(
                review_id=stable_id("proposal-review", sample_id, proposal.proposal_id),
                sample_id=sample_id,
                proposal_id=proposal.proposal_id,
                proposal_engine=proposal.proposal_engine,
                evidence={
                    "proposal_type": proposal.proposal_type,
                    "scan_id": proposal.scan_id,
                    "source_asset_ids": proposal.source_asset_ids,
                    "target_asset_ids": proposal.target_asset_ids,
                    "need_ids": proposal.need_ids,
                },
            )
        )
    return records


def build_proposal_comparison(
    bottom_up: list[ProposalRecord],
    top_down: list[ProposalRecord],
    review_sample: int = 25,
) -> dict[str, Any]:
    review_template = build_proposal_review_template(bottom_up, top_down, review_sample)
    by_id = {proposal.proposal_id: proposal for proposal in bottom_up + top_down}
    sample = [
        {
            "sample_id": record.sample_id,
            "proposal_id": record.proposal_id,
            "proposal_type": record.evidence.get("proposal_type", ""),
            "source_asset_ids": record.evidence.get("source_asset_ids", []),
            "target_asset_ids": record.evidence.get("target_asset_ids", []),
            "need_ids": record.evidence.get("need_ids", []),
            "rationale": by_id[record.proposal_id].rationale,
            "smallest_bounded_experiment": by_id[
                record.proposal_id
            ].smallest_bounded_experiment,
        }
        for record in review_template
        if record.proposal_id in by_id
    ]
    engine_sample_counts = Counter(record.proposal_engine for record in review_template)
    combined = sorted(bottom_up + top_down, key=lambda record: record.proposal_id)
    return {
        "bottom_up": _proposal_metrics(bottom_up),
        "top_down": _proposal_metrics(top_down),
        "combined": _proposal_metrics(combined),
        "review_sample_per_engine_requested": review_sample,
        "review_sample_size": len(sample),
        "review_sample_engine_counts": {
            "bottom_up_self_proposal": engine_sample_counts.get("bottom_up_self_proposal", 0),
            "top_down_orchestration": engine_sample_counts.get("top_down_orchestration", 0),
        },
        "calibration_gate_ready": (
            engine_sample_counts.get("bottom_up_self_proposal", 0) >= review_sample
            and engine_sample_counts.get("top_down_orchestration", 0) >= review_sample
        ),
        "review_sample": sample,
        "review_sample_note": (
            "Engine labels are omitted from review sample markdown; proposal review JSONL retains them."
        ),
    }


def _review_record_for_markdown(
    record: ProposalReviewRecord, proposals_by_id: dict[str, ProposalRecord]
) -> dict[str, Any]:
    proposal = proposals_by_id[record.proposal_id]
    return {
        "sample_id": record.sample_id,
        "proposal_id": record.proposal_id,
        "proposal_type": proposal.proposal_type,
        "source_asset_ids": proposal.source_asset_ids,
        "target_asset_ids": proposal.target_asset_ids,
        "need_ids": proposal.need_ids,
        "rationale": proposal.rationale,
        "smallest_bounded_experiment": proposal.smallest_bounded_experiment,
    }


def summarize_proposal_reviews(reviews: list[ProposalReviewRecord]) -> dict[str, Any]:
    reviewed = [
        review
        for review in reviews
        if review.usefulness != "unreviewed"
        or review.safety != "unreviewed"
        or review.novelty != "unreviewed"
        or review.actionability != "unreviewed"
        or review.decision != "pending"
        or any(getattr(review, field) for field in REVIEW_CALIBRATION_NOTE_FIELDS)
    ]
    by_engine: dict[str, list[ProposalReviewRecord]] = defaultdict(list)
    for review in reviewed:
        by_engine[review.proposal_engine].append(review)
    useful = [review for review in reviewed if review.usefulness == "useful"]
    safe = [review for review in reviewed if review.safety == "safe"]
    actionable = [review for review in reviewed if review.actionability == "actionable"]
    false_positive_note_count = sum(1 for review in reviews if review.false_positive_reason)
    false_negative_note_count = sum(1 for review in reviews if review.false_negative_note)
    useful_example_note_count = sum(1 for review in reviews if review.useful_example_note)
    calibration_gate_complete = (
        len(by_engine.get("bottom_up_self_proposal", [])) >= 25
        and len(by_engine.get("top_down_orchestration", [])) >= 25
    )
    structured_calibration_notes_complete = (
        false_positive_note_count > 0
        and false_negative_note_count > 0
        and useful_example_note_count > 0
    )
    return {
        "template_count": len(reviews),
        "reviewed_count": len(reviewed),
        "reviewed_by_engine": {
            "bottom_up_self_proposal": len(by_engine.get("bottom_up_self_proposal", [])),
            "top_down_orchestration": len(by_engine.get("top_down_orchestration", [])),
        },
        "useful_count": len(useful),
        "safe_count": len(safe),
        "actionable_count": len(actionable),
        "calibration_gate_complete": calibration_gate_complete,
        "structured_calibration_notes_complete": structured_calibration_notes_complete,
        "usefulness_counts": dict(Counter(review.usefulness for review in reviews)),
        "safety_counts": dict(Counter(review.safety for review in reviews)),
        "novelty_counts": dict(Counter(review.novelty for review in reviews)),
        "actionability_counts": dict(Counter(review.actionability for review in reviews)),
        "decision_counts": dict(Counter(review.decision for review in reviews)),
        "false_positive_note_count": false_positive_note_count,
        "false_negative_note_count": false_negative_note_count,
        "useful_example_note_count": useful_example_note_count,
    }


def load_proposal_reviews(path: Path) -> list[ProposalReviewRecord]:
    reviews: list[ProposalReviewRecord] = []
    if not path.exists():
        raise FileNotFoundError(f"Proposal review file not found: {path}")
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            reviews.append(ProposalReviewRecord.model_validate(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"Invalid proposal review record at {path}:{line_number}: {exc}") from exc
    return reviews


def load_proposals(path: Path) -> list[ProposalRecord]:
    proposals: list[ProposalRecord] = []
    if not path.exists():
        raise FileNotFoundError(f"Proposal file not found: {path}")
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            proposals.append(ProposalRecord.model_validate(json.loads(line)))
        except Exception as exc:
            raise ValueError(f"Invalid proposal record at {path}:{line_number}: {exc}") from exc
    return proposals


def load_generated_proposals(bottom_up_path: Path, top_down_path: Path) -> list[ProposalRecord]:
    return [*load_proposals(bottom_up_path), *load_proposals(top_down_path)]


def write_proposal_reviews(path: Path, reviews: list[ProposalReviewRecord]) -> None:
    write_jsonl(path, [review.model_dump(mode="json") for review in reviews])


def _validate_review_label(field: str, value: str | None) -> str | None:
    if value is None:
        return None
    allowed = REVIEW_LABELS[field]
    if value not in allowed:
        raise ValueError(f"Invalid {field} `{value}`. Expected one of: {', '.join(sorted(allowed))}")
    return value


def update_proposal_review_record(
    reviews: list[ProposalReviewRecord],
    *,
    sample_id: str | None = None,
    proposal_id: str | None = None,
    reviewer: str | None = None,
    usefulness: str | None = None,
    safety: str | None = None,
    novelty: str | None = None,
    actionability: str | None = None,
    decision: str | None = None,
    notes: str | None = None,
    false_positive_reason: str | None = None,
    false_negative_note: str | None = None,
    useful_example_note: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[list[ProposalReviewRecord], ProposalReviewRecord]:
    if not sample_id and not proposal_id:
        raise ValueError("Provide --sample-id or --proposal-id to select one review record.")
    matches = [
        index
        for index, review in enumerate(reviews)
        if (sample_id and review.sample_id == sample_id)
        or (proposal_id and review.proposal_id == proposal_id)
    ]
    if not matches:
        raise ValueError("No proposal review record matched the provided identifier.")
    if len(matches) > 1:
        raise ValueError("Multiple proposal review records matched; provide both identifiers.")

    updates: dict[str, Any] = {}
    for field, value in {
        "usefulness": usefulness,
        "safety": safety,
        "novelty": novelty,
        "actionability": actionability,
        "decision": decision,
    }.items():
        cleaned = _validate_review_label(field, value)
        if cleaned is not None:
            updates[field] = cleaned
    if reviewer is not None:
        updates["reviewer"] = reviewer
    if notes is not None:
        updates["notes"] = notes
    for field, value in {
        "false_positive_reason": false_positive_reason,
        "false_negative_note": false_negative_note,
        "useful_example_note": useful_example_note,
    }.items():
        if value is not None:
            updates[field] = value
    if reviewed_at is not None:
        updates["reviewed_at"] = reviewed_at

    label_update_present = any(field in updates for field in REVIEW_LABELS)
    calibration_note_present = any(field in updates for field in REVIEW_CALIBRATION_NOTE_FIELDS)
    if (label_update_present or calibration_note_present) and "reviewed_at" not in updates:
        updates["reviewed_at"] = utc_now()
    if label_update_present or calibration_note_present:
        updates["review_status"] = "reviewed"
    if not updates:
        raise ValueError("No review fields were provided to update.")

    selected_index = matches[0]
    updated = reviews[selected_index].model_copy(update=updates)
    # Re-validate after model_copy because copy skips assignment validation by default.
    updated = ProposalReviewRecord.model_validate(updated.model_dump(mode="json"))
    new_reviews = list(reviews)
    new_reviews[selected_index] = updated
    return new_reviews, updated


def update_proposal_review_file(
    path: Path,
    *,
    sample_id: str | None = None,
    proposal_id: str | None = None,
    reviewer: str | None = None,
    usefulness: str | None = None,
    safety: str | None = None,
    novelty: str | None = None,
    actionability: str | None = None,
    decision: str | None = None,
    notes: str | None = None,
    false_positive_reason: str | None = None,
    false_negative_note: str | None = None,
    useful_example_note: str | None = None,
    reviewed_at: str | None = None,
) -> tuple[ProposalReviewRecord, dict[str, Any]]:
    reviews = load_proposal_reviews(path)
    updated_reviews, updated = update_proposal_review_record(
        reviews,
        sample_id=sample_id,
        proposal_id=proposal_id,
        reviewer=reviewer,
        usefulness=usefulness,
        safety=safety,
        novelty=novelty,
        actionability=actionability,
        decision=decision,
        notes=notes,
        false_positive_reason=false_positive_reason,
        false_negative_note=false_negative_note,
        useful_example_note=useful_example_note,
        reviewed_at=reviewed_at,
    )
    write_proposal_reviews(path, updated_reviews)
    return updated, summarize_proposal_reviews(updated_reviews)


def _review_is_pending(review: ProposalReviewRecord) -> bool:
    return (
        review.usefulness == "unreviewed"
        and review.safety == "unreviewed"
        and review.novelty == "unreviewed"
        and review.actionability == "unreviewed"
        and review.decision == "pending"
        and not any(getattr(review, field) for field in REVIEW_CALIBRATION_NOTE_FIELDS)
    )


def build_proposal_review_queue(
    reviews: list[ProposalReviewRecord],
    proposals: list[ProposalRecord],
    *,
    status: Literal["pending", "reviewed", "all"] = "pending",
    engine: Literal["bottom_up_self_proposal", "top_down_orchestration", "all"] = "all",
    limit: int = 10,
) -> dict[str, Any]:
    proposals_by_id = {proposal.proposal_id: proposal for proposal in proposals}
    if status not in {"pending", "reviewed", "all"}:
        raise ValueError("Status must be one of: pending, reviewed, all")
    if engine not in {"bottom_up_self_proposal", "top_down_orchestration", "all"}:
        raise ValueError("Engine must be one of: bottom_up_self_proposal, top_down_orchestration, all")

    items: list[dict[str, Any]] = []
    missing_proposal_ids: list[str] = []
    for review in sorted(reviews, key=lambda record: record.sample_id):
        pending = _review_is_pending(review)
        if status == "pending" and not pending:
            continue
        if status == "reviewed" and pending:
            continue
        if engine != "all" and review.proposal_engine != engine:
            continue
        proposal = proposals_by_id.get(review.proposal_id)
        if not proposal:
            missing_proposal_ids.append(review.proposal_id)
            continue
        items.append(
            {
                "sample_id": review.sample_id,
                "proposal_id": review.proposal_id,
                "proposal_engine": review.proposal_engine,
                "proposal_type": proposal.proposal_type,
                "review_status": review.review_status,
                "labels": {
                    "usefulness": review.usefulness,
                    "safety": review.safety,
                    "novelty": review.novelty,
                    "actionability": review.actionability,
                    "decision": review.decision,
                    "false_positive_reason": review.false_positive_reason,
                    "false_negative_note": review.false_negative_note,
                    "useful_example_note": review.useful_example_note,
                },
                "source_asset_ids": proposal.source_asset_ids,
                "target_asset_ids": proposal.target_asset_ids,
                "need_ids": proposal.need_ids,
                "confidence": proposal.confidence,
                "risk": proposal.risk,
                "rationale": proposal.rationale,
                "smallest_bounded_experiment": proposal.smallest_bounded_experiment,
            }
        )
        if len(items) >= limit:
            break

    summary = summarize_proposal_reviews(reviews)
    return {
        "status_filter": status,
        "engine_filter": engine,
        "limit": limit,
        "returned_count": len(items),
        "missing_proposal_count": len(set(missing_proposal_ids)),
        "missing_proposal_ids": sorted(set(missing_proposal_ids))[:25],
        "summary": summary,
        "items": items,
    }


def _join_values(values: list[str]) -> str:
    return ";".join(values)


def proposal_review_csv_rows(
    reviews: list[ProposalReviewRecord],
    proposals: list[ProposalRecord],
    *,
    blind: bool = False,
) -> list[dict[str, str]]:
    proposals_by_id = {proposal.proposal_id: proposal for proposal in proposals}
    rows: list[dict[str, str]] = []
    for review in sorted(reviews, key=lambda record: record.sample_id):
        proposal = proposals_by_id.get(review.proposal_id)
        row = {
            "sample_id": review.sample_id,
            "proposal_id": review.proposal_id,
            "proposal_engine": review.proposal_engine,
            "proposal_type": (
                proposal.proposal_type if proposal else str(review.evidence.get("proposal_type", ""))
            ),
            "source_asset_ids": _join_values(
                proposal.source_asset_ids if proposal else review.evidence.get("source_asset_ids", [])
            ),
            "target_asset_ids": _join_values(
                proposal.target_asset_ids if proposal else review.evidence.get("target_asset_ids", [])
            ),
            "need_ids": _join_values(
                proposal.need_ids if proposal else review.evidence.get("need_ids", [])
            ),
            "confidence": proposal.confidence if proposal else "",
            "risk": proposal.risk if proposal else "",
            "rationale": proposal.rationale if proposal else "",
            "smallest_bounded_experiment": (
                proposal.smallest_bounded_experiment if proposal else ""
            ),
            "reviewer": review.reviewer,
            "usefulness": review.usefulness,
            "safety": review.safety,
            "novelty": review.novelty,
            "actionability": review.actionability,
            "decision": review.decision,
            "notes": review.notes,
            "false_positive_reason": review.false_positive_reason,
            "false_negative_note": review.false_negative_note,
            "useful_example_note": review.useful_example_note,
        }
        if blind:
            row.pop("proposal_engine")
        rows.append(row)
    return rows


def write_proposal_review_csv(
    path: Path,
    reviews: list[ProposalReviewRecord],
    proposals: list[ProposalRecord],
    *,
    blind: bool = False,
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = BLINDED_REVIEW_CSV_COLUMNS if blind else REVIEW_CSV_COLUMNS
    rows = proposal_review_csv_rows(reviews, proposals, blind=blind)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def write_proposal_review_unblind_map(path: Path, reviews: list[ProposalReviewRecord]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "sample_id": review.sample_id,
            "proposal_id": review.proposal_id,
            "proposal_engine": review.proposal_engine,
        }
        for review in sorted(reviews, key=lambda record: record.sample_id)
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_UNBLIND_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def _csv_value(row: dict[str, str], field: str) -> str | None:
    value = (row.get(field) or "").strip()
    return value or None


def import_proposal_review_csv(
    review_path: Path,
    csv_path: Path,
    *,
    default_reviewer: str | None = None,
) -> dict[str, Any]:
    reviews = load_proposal_reviews(review_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Proposal review CSV not found: {csv_path}")

    updated_count = 0
    skipped_count = 0
    errors: list[str] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = {
            "sample_id",
            "proposal_id",
            "usefulness",
            "safety",
            "novelty",
            "actionability",
            "decision",
        } - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"Review CSV missing required columns: {', '.join(sorted(missing_columns))}")
        for row_number, row in enumerate(reader, start=2):
            has_label = any(
                (value := _csv_value(row, field)) is not None
                and value != REVIEW_DEFAULT_LABELS[field]
                for field in REVIEW_LABELS
            )
            has_calibration_note = any(
                _csv_value(row, field) for field in REVIEW_CALIBRATION_NOTE_FIELDS
            )
            has_metadata = any(_csv_value(row, field) for field in {"reviewer", "notes"})
            if not has_label and not has_metadata and not has_calibration_note:
                skipped_count += 1
                continue
            try:
                reviews, _ = update_proposal_review_record(
                    reviews,
                    sample_id=_csv_value(row, "sample_id"),
                    proposal_id=_csv_value(row, "proposal_id"),
                    reviewer=_csv_value(row, "reviewer") or default_reviewer,
                    usefulness=_csv_value(row, "usefulness"),
                    safety=_csv_value(row, "safety"),
                    novelty=_csv_value(row, "novelty"),
                    actionability=_csv_value(row, "actionability"),
                    decision=_csv_value(row, "decision"),
                    notes=_csv_value(row, "notes"),
                    false_positive_reason=_csv_value(row, "false_positive_reason"),
                    false_negative_note=_csv_value(row, "false_negative_note"),
                    useful_example_note=_csv_value(row, "useful_example_note"),
                )
                updated_count += 1
            except ValueError as exc:
                errors.append(f"row {row_number}: {exc}")

    if errors:
        raise ValueError("Review CSV import failed: " + "; ".join(errors[:10]))
    write_proposal_reviews(review_path, reviews)
    summary = summarize_proposal_reviews(reviews)
    return {
        "review_file": str(review_path),
        "csv_file": str(csv_path),
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "summary": summary,
    }


def proposal_review_results_markdown(reviews: list[ProposalReviewRecord], source_path: Path) -> str:
    summary = summarize_proposal_reviews(reviews)
    lines = [
        "# Proposal Review Results Summary",
        "",
        f"- Source review file: `{source_path}`",
        f"- Template records: **{summary['template_count']}**",
        f"- Reviewed records: **{summary['reviewed_count']}**",
        f"- Reviewed bottom-up records: **{summary['reviewed_by_engine']['bottom_up_self_proposal']}**",
        f"- Reviewed top-down records: **{summary['reviewed_by_engine']['top_down_orchestration']}**",
        f"- Calibration gate complete: **{summary['calibration_gate_complete']}**",
        "",
        "## Label Counts",
        "",
        f"- Usefulness: `{summary['usefulness_counts']}`",
        f"- Safety: `{summary['safety_counts']}`",
        f"- Novelty: `{summary['novelty_counts']}`",
        f"- Actionability: `{summary['actionability_counts']}`",
        f"- Decisions: `{summary['decision_counts']}`",
        "",
        "## Calibration Notes",
        "",
        f"- False positive notes: **{summary['false_positive_note_count']}**",
        f"- False negative notes: **{summary['false_negative_note_count']}**",
        f"- Useful example notes: **{summary['useful_example_note_count']}**",
        f"- Structured calibration notes complete: **{summary['structured_calibration_notes_complete']}**",
        "",
        "Generated summary only. Track curated evidence separately after human review.",
        "",
    ]
    return "\n".join(lines)


def write_proposal_review_results_summary(
    repo_root: Path, reviews: list[ProposalReviewRecord], source_path: Path
) -> tuple[dict[str, Any], str]:
    summary = summarize_proposal_reviews(reviews)
    output = repo_root / "processed" / "reports" / "proposal_review_results_summary.md"
    atomic_write_text(output, proposal_review_results_markdown(reviews, source_path))
    return summary, str(output)


def _calibration_note_lines(
    reviews: list[ProposalReviewRecord], field: str, empty_message: str
) -> list[str]:
    noted = [review for review in reviews if getattr(review, field)]
    if not noted:
        return [f"- {empty_message}", ""]
    lines: list[str] = []
    for review in sorted(noted, key=lambda record: record.sample_id)[:10]:
        note = str(getattr(review, field))
        lines.append(
            f"- `{review.sample_id}` `{review.proposal_engine}` `{review.proposal_id}`: {note}"
        )
    lines.append("")
    return lines


def _review_acceptance_counts(reviews: list[ProposalReviewRecord]) -> dict[str, Any]:
    by_engine: dict[str, list[ProposalReviewRecord]] = defaultdict(list)
    for review in reviews:
        if review.decision == "accept_candidate":
            by_engine[review.proposal_engine].append(review)
    return {
        "bottom_up_self_proposal": len(by_engine.get("bottom_up_self_proposal", [])),
        "top_down_orchestration": len(by_engine.get("top_down_orchestration", [])),
    }


def _candidate_default_path(reviews: list[ProposalReviewRecord]) -> str:
    accepted = _review_acceptance_counts(reviews)
    bottom = accepted["bottom_up_self_proposal"]
    top = accepted["top_down_orchestration"]
    if bottom == top:
        return "hybrid"
    return "bottom_up_self_proposal" if bottom > top else "top_down_orchestration"


def _normalize_calibration_default_path(default_path: str | None) -> CalibrationDefaultPath:
    if not default_path:
        raise ValueError(
            "Proposal calibration evidence requires --default-path with one of: "
            "bottom-up, top-down, hybrid."
        )
    normalized = default_path.strip().lower().replace("_", "-")
    aliases = {
        "bottom-up": "bottom_up_self_proposal",
        "bottom-up-self-proposal": "bottom_up_self_proposal",
        "bottom_up_self_proposal": "bottom_up_self_proposal",
        "top-down": "top_down_orchestration",
        "top-down-orchestration": "top_down_orchestration",
        "top_down_orchestration": "top_down_orchestration",
        "hybrid": "hybrid",
    }
    selected = aliases.get(normalized)
    if selected not in CALIBRATION_DEFAULT_PATHS:
        raise ValueError(
            "Proposal calibration default path must be one of: bottom-up, top-down, hybrid."
        )
    return selected  # type: ignore[return-value]


def proposal_calibration_evidence_markdown(
    reviews: list[ProposalReviewRecord],
    source_path: Path,
    *,
    default_path: str | None = None,
    default_rationale: str | None = None,
) -> str:
    summary = summarize_proposal_reviews(reviews)
    if not summary["calibration_gate_complete"]:
        raise ValueError(
            "Proposal calibration evidence requires at least 25 reviewed records from each engine."
        )
    if not summary["structured_calibration_notes_complete"]:
        raise ValueError(
            "Proposal calibration evidence requires false positive, false negative, "
            "and useful example notes."
        )
    selected_default_path = _normalize_calibration_default_path(default_path)
    cleaned_default_rationale = (default_rationale or "").strip()
    if not cleaned_default_rationale:
        raise ValueError("Proposal calibration evidence requires --default-rationale.")
    accepted = _review_acceptance_counts(reviews)
    candidate_default = _candidate_default_path(reviews)
    lines = [
        "# Proposal Engine Calibration Evidence",
        "",
        f"Evidence date: {utc_now()}",
        "",
        "## Source Review File",
        "",
        f"- Review file: `{source_path}`",
        "- Source review records are human labels over generated candidate proposals.",
        "- This evidence does not promote source-repository changes or generated proposals to truth.",
        "",
        "## Gate Coverage",
        "",
        f"- Reviewed records: **{summary['reviewed_count']}**",
        f"- Reviewed bottom-up records: **{summary['reviewed_by_engine']['bottom_up_self_proposal']}**",
        f"- Reviewed top-down records: **{summary['reviewed_by_engine']['top_down_orchestration']}**",
        f"- Calibration gate complete: **{summary['calibration_gate_complete']}**",
        "",
        "## Review Outcomes",
        "",
        f"- Usefulness: `{summary['usefulness_counts']}`",
        f"- Safety: `{summary['safety_counts']}`",
        f"- Novelty: `{summary['novelty_counts']}`",
        f"- Actionability: `{summary['actionability_counts']}`",
        f"- Decisions: `{summary['decision_counts']}`",
        f"- Accepted bottom-up candidates: **{accepted['bottom_up_self_proposal']}**",
        f"- Accepted top-down candidates: **{accepted['top_down_orchestration']}**",
        f"- Candidate default path from accepted counts: **{candidate_default}**",
        f"- Human-selected default path: **{selected_default_path}**",
        f"- Human default rationale: {cleaned_default_rationale}",
        "",
        "## Calibration Findings",
        "",
        f"- False positive notes: **{summary['false_positive_note_count']}**",
        f"- False negative notes: **{summary['false_negative_note_count']}**",
        f"- Useful example notes: **{summary['useful_example_note_count']}**",
        f"- Structured calibration notes complete: **{summary['structured_calibration_notes_complete']}**",
        "",
        "### False Positive Notes",
        "",
        *_calibration_note_lines(
            reviews, "false_positive_reason", "No false positive notes were recorded."
        ),
        "### False Negative Notes",
        "",
        *_calibration_note_lines(
            reviews, "false_negative_note", "No false negative notes were recorded."
        ),
        "### Useful Examples",
        "",
        *_calibration_note_lines(
            reviews, "useful_example_note", "No useful example notes were recorded."
        ),
        "## Remaining Risks",
        "",
        "- Human labels are calibration evidence, not proof that any source repo should change.",
        "- External code, license, security, and compatibility review remain required before reuse.",
        "- Roadmap status should change only if the relevant phase acceptance criteria are otherwise met.",
        "",
    ]
    return "\n".join(lines)


def write_proposal_calibration_evidence(
    repo_root: Path,
    reviews: list[ProposalReviewRecord],
    source_path: Path,
    output_path: Path | None = None,
    *,
    default_path: str | None = None,
    default_rationale: str | None = None,
) -> tuple[dict[str, Any], str]:
    output = output_path or repo_root / "roadmap" / "evidence" / "proposal-engine-calibration.md"
    if not output.is_absolute():
        output = repo_root / output
    text = proposal_calibration_evidence_markdown(
        reviews,
        source_path,
        default_path=default_path,
        default_rationale=default_rationale,
    )
    atomic_write_text(output, text)
    return summarize_proposal_reviews(reviews), str(output)


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
                f"- Actionable experiment rate: **{metrics['actionable_experiment_rate']}**",
                f"- Candidate status pass rate: **{metrics['candidate_status_pass_rate']}**",
                f"- Authority boundary pass rate: **{metrics['authority_boundary_pass_rate']}**",
                f"- Estimated review cost counts: `{metrics['estimated_review_cost_counts']}`",
                f"- Estimated integration cost counts: `{metrics['estimated_integration_cost_counts']}`",
                f"- External review risk count: **{metrics['external_review_risk_count']}**",
                f"- Research missing-part count: **{metrics['research_missing_part_count']}**",
                f"- Human usefulness metrics available: **{metrics['human_usefulness_metrics_available']}**",
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
            f"- Requested per engine: **{comparison['review_sample_per_engine_requested']}**",
            f"- Sample size: **{comparison['review_sample_size']}**",
            f"- Bottom-up sample count: **{comparison['review_sample_engine_counts']['bottom_up_self_proposal']}**",
            f"- Top-down sample count: **{comparison['review_sample_engine_counts']['top_down_orchestration']}**",
            f"- Calibration gate ready: **{comparison['calibration_gate_ready']}**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def review_sample_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Proposal Review Sample",
        "",
        "Engine labels are hidden here for review calibration. Use proposal IDs and `processed/proposals/proposal_review_template.jsonl` to unblind after scoring.",
        "",
        f"- Requested per engine: **{comparison['review_sample_per_engine_requested']}**",
        f"- Bottom-up sample count: **{comparison['review_sample_engine_counts']['bottom_up_self_proposal']}**",
        f"- Top-down sample count: **{comparison['review_sample_engine_counts']['top_down_orchestration']}**",
        f"- Calibration gate ready: **{comparison['calibration_gate_ready']}**",
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


def calibration_summary_markdown(
    comparison: dict[str, Any], review_template: list[ProposalReviewRecord]
) -> str:
    review_summary = summarize_proposal_reviews(review_template)
    missing_bottom_up = max(
        0,
        comparison["review_sample_per_engine_requested"]
        - comparison["review_sample_engine_counts"]["bottom_up_self_proposal"],
    )
    missing_top_down = max(
        0,
        comparison["review_sample_per_engine_requested"]
        - comparison["review_sample_engine_counts"]["top_down_orchestration"],
    )
    lines = [
        "# Proposal Calibration Summary",
        "",
        "Generated candidate calibration workspace. This file does not claim human review is complete.",
        "",
        "## Sample Coverage",
        "",
        f"- Requested per engine: **{comparison['review_sample_per_engine_requested']}**",
        f"- Bottom-up sample count: **{comparison['review_sample_engine_counts']['bottom_up_self_proposal']}**",
        f"- Top-down sample count: **{comparison['review_sample_engine_counts']['top_down_orchestration']}**",
        f"- Missing bottom-up samples: **{missing_bottom_up}**",
        f"- Missing top-down samples: **{missing_top_down}**",
        f"- Calibration gate ready for human review: **{comparison['calibration_gate_ready']}**",
        "",
        "## Human Review Status",
        "",
        f"- Review template records: **{review_summary['template_count']}**",
        f"- Reviewed records: **{review_summary['reviewed_count']}**",
        f"- Reviewed bottom-up records: **{review_summary['reviewed_by_engine']['bottom_up_self_proposal']}**",
        f"- Reviewed top-down records: **{review_summary['reviewed_by_engine']['top_down_orchestration']}**",
        f"- Useful records: **{review_summary['useful_count']}**",
        f"- Safe records: **{review_summary['safe_count']}**",
        f"- Actionable records: **{review_summary['actionable_count']}**",
        f"- Calibration gate complete: **{review_summary['calibration_gate_complete']}**",
        f"- Structured calibration notes complete: **{review_summary['structured_calibration_notes_complete']}**",
        "",
        "## How To Complete The Gate",
        "",
        "- Generate at least 25 proposals from each engine, raising `--portfolio-limit` if needed.",
        "- Review the hidden Markdown sample before looking at engine labels.",
        "- Record labels and structured calibration notes in `processed/proposals/proposal_review_template.jsonl` or a copied curated evidence file.",
        "- Select the default path explicitly when exporting evidence: `bottom-up`, `top-down`, or `hybrid`.",
        "- Track curated evidence only after human labels, structured notes, and the default-path decision are entered; do not track generated proposal outputs.",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_proposal_outputs(
    repo_root: Path,
    bottom_up: list[ProposalRecord],
    top_down: list[ProposalRecord],
    comparison: dict[str, Any],
) -> dict[str, str]:
    bottom_path = repo_root / "processed" / "proposals" / "bottom_up_proposals.jsonl"
    top_path = repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
    review_template_path = repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    comparison_path = repo_root / "processed" / "reports" / "proposal_engine_comparison.md"
    review_path = repo_root / "processed" / "reports" / "proposal_review_sample.md"
    calibration_path = repo_root / "processed" / "reports" / "proposal_calibration_summary.md"
    review_template = build_proposal_review_template(
        bottom_up, top_down, comparison["review_sample_per_engine_requested"]
    )
    write_jsonl(bottom_path, [proposal.model_dump(mode="json") for proposal in bottom_up])
    write_jsonl(top_path, [proposal.model_dump(mode="json") for proposal in top_down])
    write_jsonl(
        review_template_path, [review.model_dump(mode="json") for review in review_template]
    )
    atomic_write_text(comparison_path, comparison_markdown(comparison))
    atomic_write_text(review_path, review_sample_markdown(comparison))
    atomic_write_text(calibration_path, calibration_summary_markdown(comparison, review_template))
    return {
        "bottom_up": str(bottom_path),
        "top_down": str(top_path),
        "review_template": str(review_template_path),
        "comparison": str(comparison_path),
        "review_sample": str(review_path),
        "calibration_summary": str(calibration_path),
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
