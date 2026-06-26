from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from .ids import stable_id
from .models import (
    AssetRecord,
    AttentionSeedRecord,
    ConnectionCandidateRecord,
    EdgeRecord,
    EscalationPacketRecord,
    ExpansionMapRecord,
)
from .utils import atomic_write_text, redact_sensitive_text, tokens, utc_now, write_jsonl

METHODOLOGY_VERSION = "background-connection-connectivity-v1"
DUPLICATE_EDGE_TYPES = {
    "exact_duplicate_of",
    "near_duplicate_of",
    "variant_of",
    "semantic_variant_of",
    "noise_variant_of",
    "lineage_evidence_for",
    "contained_in",
    "has_delta_candidate",
}
UNSAFE_PATH_MARKERS = (
    ".env",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "private_key",
    "raw/",
    "data/",
    "output/",
    "outputs/",
)
@dataclass(frozen=True)
class BackgroundConnectionResult:
    attention_seeds: list[AttentionSeedRecord]
    candidates: list[ConnectionCandidateRecord]
    packets: list[EscalationPacketRecord]
    expansion_maps: list[ExpansionMapRecord]
    summary: dict[str, Any]


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent.setdefault(value, value)
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        winner, loser = sorted([left_root, right_root])
        self.parent[loser] = winner


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _asset_terms(asset: AssetRecord) -> set[str]:
    structured = set(asset.tags) | set(asset.capabilities) | set(asset.needs) | set(asset.outcomes)
    structured.update(str(value) for value in asset.metadata.get("asset_patterns", []) or [])
    structured.update(tokens(f"{asset.asset_type} {asset.title} {asset.logical_path}"))
    return {term.lower() for term in structured if term}


def _source_compatible(left: AssetRecord, right: AssetRecord) -> bool:
    if left.source_id == right.source_id:
        return True
    if left.trust_zone != "source_owned" and right.trust_zone != "source_owned":
        return True
    return False


def _is_cold_asset(asset: AssetRecord, seed_asset_ids: set[str]) -> bool:
    if asset.asset_id in seed_asset_ids:
        return False
    if asset.freshness_status in {"stale", "watch"}:
        return True
    if asset.value_components.get("ceiling_score", 0.0) > asset.value_score:
        return True
    return False


def _safety_gate(left: AssetRecord, right: AssetRecord) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for asset in (left, right):
        lowered = asset.logical_path.replace("\\", "/").lower()
        if asset.sensitivity in {"confidential", "restricted"}:
            failures.append(f"sensitive_asset:{asset.asset_id}:{asset.sensitivity}")
        if any(marker in lowered for marker in UNSAFE_PATH_MARKERS):
            failures.append(f"sensitive_path:{asset.asset_id}")
    return not failures, failures


def _content_identity_present(asset: AssetRecord) -> bool:
    return bool(asset.content_sha256 or asset.content_hash or asset.metadata_fingerprint)


def _family_keys(assets: list[AssetRecord], edges: list[EdgeRecord]) -> dict[str, str]:
    uf = _UnionFind(asset.asset_id for asset in assets)
    asset_ids = {asset.asset_id for asset in assets}
    for edge in edges:
        if edge.edge_type in DUPLICATE_EDGE_TYPES and edge.source_asset_id in asset_ids:
            if edge.target_asset_id in asset_ids:
                uf.union(edge.source_asset_id, edge.target_asset_id)
    keys: dict[str, str] = {}
    root_counts: dict[str, int] = defaultdict(int)
    for asset in assets:
        root_counts[uf.find(asset.asset_id)] += 1
    for asset in assets:
        root = uf.find(asset.asset_id)
        identity = root if root_counts[root] > 1 else asset.content_sha256 or asset.content_hash or root
        keys[asset.asset_id] = f"{asset.asset_type}:{identity}"
    return keys


def build_attention_seeds(
    assets: list[AssetRecord],
    *,
    scan_id: str,
    generated_at: str,
    attention: str = "recent",
    hot_limit: int = 200,
) -> list[AttentionSeedRecord]:
    if attention != "recent":
        return []
    ranked = sorted(
        assets,
        key=lambda asset: (
            _parse_time(asset.modified_at or asset.last_seen_at),
            asset.value_score,
            asset.asset_id,
        ),
        reverse=True,
    )[:hot_limit]
    total = max(1, len(ranked) - 1)
    seeds: list[AttentionSeedRecord] = []
    for index, asset in enumerate(ranked):
        weight = 1.0 if len(ranked) == 1 else max(0.1, 1.0 - (index / total))
        seeds.append(
            AttentionSeedRecord(
                attention_seed_id=stable_id("attention-seed", scan_id, asset.asset_id),
                source_kind="recent_asset",
                source_ref=asset.asset_id,
                seed_asset_ids=[asset.asset_id],
                tags=sorted(set(asset.tags)),
                capabilities=sorted(set(asset.capabilities)),
                needs=sorted(set(asset.needs)),
                attention_weight=round(weight, 4),
                raw_text_persisted=False,
                evidence={
                    "source": "catalog_artifact_recency",
                    "attention": attention,
                    "logical_path": asset.logical_path,
                },
                generated_at=generated_at,
                scan_id=scan_id,
            )
        )
    return seeds


def _edge_indexes(edges: list[EdgeRecord]) -> tuple[dict[str, set[str]], set[tuple[str, str]], dict[tuple[str, str], list[EdgeRecord]]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    pair_types: dict[tuple[str, str], list[EdgeRecord]] = defaultdict(list)
    pairs: set[tuple[str, str]] = set()
    for edge in edges:
        pair = tuple(sorted([edge.source_asset_id, edge.target_asset_id]))
        pairs.add(pair)
        pair_types[pair].append(edge)
        adjacency[edge.source_asset_id].add(edge.target_asset_id)
        adjacency[edge.target_asset_id].add(edge.source_asset_id)
    return adjacency, pairs, pair_types


def _candidate_type(
    left: AssetRecord, right: AssetRecord, pair_edges: list[EdgeRecord], cold: bool, authority_gate: bool
) -> Literal[
    "activates_cold_asset",
    "bridges_orphan_to_attention_seed",
    "composes_with",
    "duplicate_variant_delta",
    "same_workflow_different_domain",
    "lesson_applies_when",
    "lesson_does_not_apply_when",
    "workflow_part_of",
    "missing_capability_for",
    "dangerous_composition_with",
    "requires_human_gate",
    "supports_but_cannot_override",
]:
    edge_types = {edge.edge_type for edge in pair_edges}
    if not authority_gate:
        return "requires_human_gate"
    if edge_types & DUPLICATE_EDGE_TYPES:
        return "duplicate_variant_delta"
    if set(left.needs) & set(right.capabilities) or set(right.needs) & set(left.capabilities):
        return "missing_capability_for"
    if cold:
        return "activates_cold_asset"
    if left.source_id != right.source_id and _asset_terms(left) & _asset_terms(right):
        return "same_workflow_different_domain"
    return "composes_with"


def _connection_components(
    left: AssetRecord,
    right: AssetRecord,
    seed: AttentionSeedRecord,
    pair_edges: list[EdgeRecord],
    adjacency: dict[str, set[str]],
    cold: bool,
    *,
    left_terms: set[str] | None = None,
    right_terms: set[str] | None = None,
) -> tuple[dict[str, float], dict[str, Any]]:
    left_terms = left_terms if left_terms is not None else _asset_terms(left)
    right_terms = right_terms if right_terms is not None else _asset_terms(right)
    seed_terms = set(seed.tags) | set(seed.capabilities) | set(seed.needs)
    shared_terms = left_terms & right_terms
    attention_terms = (left_terms | right_terms) & seed_terms
    attention_relevance = min(1.0, (len(attention_terms) / max(1, len(seed_terms))) + 0.25)
    attention_relevance = max(attention_relevance, seed.attention_weight * 0.5)
    cold_lift = 1.0 if cold else 0.0
    need_cap_matches = (set(left.needs) & set(right.capabilities)) | (
        set(right.needs) & set(left.capabilities)
    )
    duplicate_similarity = 1.0 if any(edge.edge_type in DUPLICATE_EDGE_TYPES for edge in pair_edges) else 0.0
    complementarity_raw = min(1.0, (0.5 if need_cap_matches else 0.0) + min(0.5, len(shared_terms) / 8))
    complementarity = max(0.0, complementarity_raw - duplicate_similarity)
    neighbors = (adjacency.get(left.asset_id, set()) | adjacency.get(right.asset_id, set())) - {
        left.asset_id,
        right.asset_id,
    }
    multi_hop_potential = min(1.0, math.log1p(len(neighbors)) / math.log1p(25))
    novelty = 0.0 if pair_edges else 1.0
    components = {
        "attention_relevance": round(attention_relevance, 4),
        "cold_lift": round(cold_lift, 4),
        "complementarity": round(complementarity, 4),
        "multi_hop_potential": round(multi_hop_potential, 4),
        "novelty": round(novelty, 4),
    }
    evidence = {
        "shared_terms": sorted(shared_terms)[:20],
        "attention_terms": sorted(attention_terms)[:20],
        "need_capability_matches": sorted(need_cap_matches),
        "existing_edge_types": sorted({edge.edge_type for edge in pair_edges}),
        "duplicate_similarity_penalty": duplicate_similarity,
        "two_hop_neighbor_count": len(neighbors),
    }
    return components, evidence


def connectivity_score(component_scores: dict[str, float]) -> float:
    score = (
        0.30 * component_scores.get("attention_relevance", 0.0)
        + 0.20 * component_scores.get("cold_lift", 0.0)
        + 0.25 * component_scores.get("complementarity", 0.0)
        + 0.15 * component_scores.get("multi_hop_potential", 0.0)
        + 0.10 * component_scores.get("novelty", 0.0)
    )
    return round(min(1.0, max(0.0, score)), 4)


def _reuse_mapping(connection_type: str) -> list[str]:
    mapping = {
        "activates_cold_asset": ["activates", "satisfies_need", "blocked_by"],
        "bridges_orphan_to_attention_seed": ["activates", "satisfies_need"],
        "composes_with": ["composes_with", "complements"],
        "duplicate_variant_delta": ["variant_of", "near_duplicate_of", "lineage_evidence_for"],
        "same_workflow_different_domain": ["plays_same_architecture_role_as", "composes_with"],
        "lesson_applies_when": ["applies_when"],
        "lesson_does_not_apply_when": ["does_not_apply_when"],
        "workflow_part_of": ["has_workflow_step", "has_member_asset"],
        "missing_capability_for": ["satisfies_need"],
        "dangerous_composition_with": ["unsafe_composition_with", "contaminates_if_default"],
        "requires_human_gate": ["requires_human_gate", "governed_by"],
        "supports_but_cannot_override": ["supports_but_cannot_override"],
    }
    return mapping.get(connection_type, ["related_to"])


def build_connection_candidates(
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    seeds: list[AttentionSeedRecord],
    *,
    scan_id: str,
    generated_at: str,
    cold: str = "older",
    per_seed_cap: int = 50,
    tau: float = 0.70,
) -> list[ConnectionCandidateRecord]:
    assets_by_id = {asset.asset_id: asset for asset in assets}
    family_keys = _family_keys(assets, edges)
    adjacency, edge_pairs, pair_edges = _edge_indexes(edges)
    seed_asset_ids = {asset_id for seed in seeds for asset_id in seed.seed_asset_ids}
    cold_ids = {
        asset.asset_id for asset in assets if cold == "older" and _is_cold_asset(asset, seed_asset_ids)
    }
    terms_by_asset = {asset.asset_id: _asset_terms(asset) for asset in assets}
    index: dict[str, set[str]] = defaultdict(set)
    capability_index: dict[str, set[str]] = defaultdict(set)
    need_index: dict[str, set[str]] = defaultdict(set)
    for asset in assets:
        for term in terms_by_asset[asset.asset_id]:
            index[term].add(asset.asset_id)
        for capability in asset.capabilities:
            capability_index[capability].add(asset.asset_id)
        for need in asset.needs:
            need_index[need].add(asset.asset_id)

    max_postings = max(per_seed_cap * 20, 500)

    def add_ranked_postings(pool: set[str], postings: set[str]) -> None:
        if len(postings) > max_postings:
            return
        for asset_id in sorted(
            postings,
            key=lambda candidate_id: (
                candidate_id not in cold_ids,
                -assets_by_id[candidate_id].value_score,
                assets_by_id[candidate_id].logical_path,
            ),
        )[:per_seed_cap]:
            pool.add(asset_id)

    candidates: dict[str, ConnectionCandidateRecord] = {}
    for seed in seeds:
        if not seed.seed_asset_ids:
            continue
        source = assets_by_id.get(seed.seed_asset_ids[0])
        if not source:
            continue
        seed_terms = terms_by_asset[source.asset_id]
        pool: set[str] = set()
        for need in source.needs:
            add_ranked_postings(pool, capability_index.get(need, set()))
        for capability in source.capabilities:
            add_ranked_postings(pool, need_index.get(capability, set()))
        for term in sorted(seed_terms, key=lambda value: (len(index.get(value, set())), value)):
            add_ranked_postings(pool, index.get(term, set()))
            if len(pool) >= per_seed_cap * 3:
                break
        ranked_neighbors = sorted(
            adjacency.get(source.asset_id, set()),
            key=lambda asset_id: (
                asset_id not in cold_ids,
                -assets_by_id.get(asset_id, source).value_score,
                asset_id,
            ),
        )[:per_seed_cap]
        pool.update(asset_id for asset_id in ranked_neighbors if asset_id in assets_by_id)
        for neighbor in ranked_neighbors:
            neighbor_edges = adjacency.get(neighbor, set())
            for asset_id in sorted(neighbor_edges)[:per_seed_cap]:
                if asset_id in assets_by_id:
                    pool.add(asset_id)
        ranked_pool = sorted(
            (asset_id for asset_id in pool if asset_id != source.asset_id),
            key=lambda asset_id: (
                asset_id not in cold_ids,
                -assets_by_id[asset_id].value_score,
                assets_by_id[asset_id].logical_path,
            ),
        )[:per_seed_cap]
        for target_id in ranked_pool:
            target = assets_by_id[target_id]
            pair = tuple(sorted([source.asset_id, target.asset_id]))
            pair_edge_records = pair_edges.get(pair, [])
            target_cold = target.asset_id in cold_ids
            safety_ok, safety_failures = _safety_gate(source, target)
            evidence_signals: list[str] = []
            source_terms = terms_by_asset[source.asset_id]
            target_terms = terms_by_asset[target.asset_id]
            terms_overlap = source_terms & target_terms
            if terms_overlap:
                evidence_signals.append("term_overlap")
            if set(source.needs) & set(target.capabilities) or set(target.needs) & set(source.capabilities):
                evidence_signals.append("need_capability")
            if pair in edge_pairs:
                evidence_signals.append("existing_graph_edge")
            if target_cold:
                evidence_signals.append("cold_lift")
            components, signal_evidence = _connection_components(
                source,
                target,
                seed,
                pair_edge_records,
                adjacency,
                target_cold,
                left_terms=source_terms,
                right_terms=target_terms,
            )
            score = connectivity_score(components)
            evidence_gate = (
                len(set(evidence_signals)) >= 2
                and _content_identity_present(source)
                and _content_identity_present(target)
                and all(edge.scan_id == scan_id for edge in pair_edge_records)
            )
            authority_compatible = _source_compatible(source, target)
            connection_type = _candidate_type(
                source, target, pair_edge_records, target_cold, authority_compatible
            )
            authority_gate = authority_compatible
            gates = {
                "safety_gate": safety_ok,
                "evidence_gate": evidence_gate,
                "authority_gate": authority_gate,
            }
            failures = [name for name, ok in gates.items() if not ok]
            failures.extend(safety_failures)
            eligible = all(gates.values()) and score >= tau
            candidate = ConnectionCandidateRecord(
                connection_candidate_id=stable_id(
                    "background-connection",
                    scan_id,
                    connection_type,
                    source.asset_id,
                    target.asset_id,
                ),
                connection_type=connection_type,
                source_asset_ids=[source.asset_id],
                target_asset_ids=[target.asset_id],
                endpoint_family_keys=[family_keys[source.asset_id], family_keys[target.asset_id]],
                attention_seed_ids=[seed.attention_seed_id],
                cold_asset_ids=[target.asset_id] if target_cold else [],
                cheap_signal_evidence={
                    **signal_evidence,
                    "signals": sorted(set(evidence_signals)),
                    "source_path": source.logical_path,
                    "target_path": target.logical_path,
                },
                component_scores=components,
                connectivity_score=score,
                gates=gates,
                gate_failures=sorted(set(failures)),
                escalation_eligible=eligible,
                reuse_first_edge_mapping=_reuse_mapping(connection_type),
                why_might_matter_now=(
                    f"{target.title} may connect to current attention around {source.title}."
                ),
                why_might_be_false=(
                    "This may be lexical or graph-neighbor coincidence; generated candidate only."
                ),
                evidence={
                    "methodology": METHODOLOGY_VERSION,
                    "gate_before_score": True,
                    "score_threshold": tau,
                },
                generated_at=generated_at,
                scan_id=scan_id,
            )
            existing = candidates.get(candidate.connection_candidate_id)
            if existing is None or candidate.connectivity_score > existing.connectivity_score:
                candidates[candidate.connection_candidate_id] = candidate
    return sorted(
        candidates.values(),
        key=lambda record: (
            not record.escalation_eligible,
            -record.connectivity_score,
            record.connection_type,
            record.source_asset_ids,
            record.target_asset_ids,
        ),
    )


def _minimal_context(asset: AssetRecord) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "title": asset.title,
        "asset_type": asset.asset_type,
        "logical_path": asset.logical_path,
        "authority_boundary": asset.trust_zone,
        "source_id": asset.source_id,
        "sensitivity": asset.sensitivity,
    }


def _snippet(asset: AssetRecord) -> str:
    redacted, _ = redact_sensitive_text(
        f"{asset.title} | {asset.asset_type} | {asset.logical_path} | "
        f"tags={','.join(asset.tags[:8])} | capabilities={','.join(asset.capabilities[:8])}"
    )
    return redacted[:500]


def select_escalation_packets(
    candidates: list[ConnectionCandidateRecord],
    assets: list[AssetRecord],
    *,
    scan_id: str,
    generated_at: str,
    escalation_budget: int = 5,
    reserve_cold: int = 2,
) -> list[EscalationPacketRecord]:
    assets_by_id = {asset.asset_id: asset for asset in assets}
    families: dict[tuple[str, tuple[str, ...]], list[ConnectionCandidateRecord]] = defaultdict(list)
    for candidate in candidates:
        key = (candidate.connection_type, tuple(sorted(candidate.endpoint_family_keys)))
        families[key].append(candidate)
    representatives: list[tuple[ConnectionCandidateRecord, list[ConnectionCandidateRecord]]] = []
    for members in families.values():
        sorted_members = sorted(
            members,
            key=lambda record: (-record.connectivity_score, record.connection_candidate_id),
        )
        if sorted_members[0].escalation_eligible:
            representatives.append((sorted_members[0], sorted_members[1:]))
    cold_reps = [item for item in representatives if item[0].cold_asset_ids]
    other_reps = [item for item in representatives if not item[0].cold_asset_ids]
    cold_reps.sort(key=lambda item: (-item[0].connectivity_score, item[0].connection_candidate_id))
    other_reps.sort(key=lambda item: (-item[0].connectivity_score, item[0].connection_candidate_id))
    selected = cold_reps[: min(reserve_cold, escalation_budget)]
    remaining_budget = max(0, escalation_budget - len(selected))
    selected_ids = {item[0].connection_candidate_id for item in selected}
    fill = [
        item
        for item in sorted(
            [*cold_reps[min(reserve_cold, escalation_budget) :], *other_reps],
            key=lambda item: (-item[0].connectivity_score, item[0].connection_candidate_id),
        )
        if item[0].connection_candidate_id not in selected_ids
    ][:remaining_budget]
    selected.extend(fill)

    packets: list[EscalationPacketRecord] = []
    for index, (candidate, members) in enumerate(selected, start=1):
        asset_ids = [*candidate.source_asset_ids, *candidate.target_asset_ids]
        packet_assets = [assets_by_id[asset_id] for asset_id in asset_ids if asset_id in assets_by_id]
        packets.append(
            EscalationPacketRecord(
                packet_id=stable_id("background-escalation-packet", scan_id, candidate.connection_candidate_id),
                connection_candidate_id=candidate.connection_candidate_id,
                scan_id_watermark=scan_id,
                attention_seed_ids=candidate.attention_seed_ids,
                cold_memory_cue=(
                    "cold_asset_present" if candidate.cold_asset_ids else "current_attention_bridge"
                ),
                source_asset_ids=candidate.source_asset_ids,
                target_asset_ids=candidate.target_asset_ids,
                deduped_member_candidate_ids=[
                    member.connection_candidate_id for member in members
                ],
                minimal_context=[_minimal_context(asset) for asset in packet_assets],
                redacted_evidence_snippets=[_snippet(asset) for asset in packet_assets],
                cheap_signal_evidence=candidate.cheap_signal_evidence,
                component_scores=candidate.component_scores,
                connectivity_score=candidate.connectivity_score,
                proposed_connection_type=candidate.connection_type,
                reuse_first_edge_mapping=candidate.reuse_first_edge_mapping,
                why_might_matter_now=candidate.why_might_matter_now,
                why_might_be_false=candidate.why_might_be_false,
                stop_conditions=[
                    "Stop if evidence is lexical coincidence.",
                    "Stop if source authority would be crossed without human review.",
                    "Stop if duplicate similarity explains the connection better than complementarity.",
                ],
                safety_cleared=True,
                requested_verifier_tasks=[
                    "confirm_or_reject_connection",
                    "classify_reuse_first_edge_mapping",
                    "bounded_two_hop_expansion",
                    "separate_duplicate_similarity_from_complementarity",
                    "estimate_ceiling_or_edge_candidacy_only",
                    "red_team_false_positive",
                ],
                budget_priority=index,
                evidence={
                    "source_candidate": candidate.connection_candidate_id,
                    "family_dedup_before_budget": True,
                },
                generated_at=generated_at,
                scan_id=scan_id,
            )
        )
    return packets


def build_expansion_maps(
    packets: list[EscalationPacketRecord],
    edges: list[EdgeRecord],
    *,
    scan_id: str,
    generated_at: str,
    max_hops: int = 2,
    max_nodes: int = 25,
) -> list[ExpansionMapRecord]:
    adjacency, _, _ = _edge_indexes(edges)
    maps: list[ExpansionMapRecord] = []
    for packet in packets:
        roots = set(packet.source_asset_ids) | set(packet.target_asset_ids)
        direct = sorted({neighbor for root in roots for neighbor in adjacency.get(root, set())} - roots)
        second: set[str] = set()
        if max_hops >= 2:
            for node in direct[:max_nodes]:
                second.update(adjacency.get(node, set()))
        second = second - roots - set(direct)
        direct_limited = direct[:max_nodes]
        remaining = max(0, max_nodes - len(direct_limited))
        second_limited = sorted(second)[:remaining]
        maps.append(
            ExpansionMapRecord(
                expansion_map_id=stable_id("background-expansion-map", scan_id, packet.packet_id),
                packet_id=packet.packet_id,
                root_connection_candidate_id=packet.connection_candidate_id,
                direct_asset_ids=direct_limited,
                second_hop_asset_ids=second_limited,
                max_hops=min(max_hops, 2),
                max_nodes=min(max_nodes, 25),
                per_hop_confidence={"1": 0.7, "2": 0.49 if second_limited else 0.0},
                why_useful=[
                    "Shows immediate and second-hop graph neighbors for manual review.",
                    "Keeps expansion bounded before any strong-model verification.",
                ],
                why_wrong=[
                    "Graph neighbors may be generated candidates rather than reviewed relationships."
                ],
                stop_conditions=[
                    "Stop at max 2 hops.",
                    "Stop at max 25 nodes.",
                    "Stop when authority or evidence weakens.",
                ],
                evidence={"packet_id": packet.packet_id, "bounded_expansion": True},
                generated_at=generated_at,
                scan_id=scan_id,
            )
        )
    return maps


def background_connection_markdown(
    candidates: list[ConnectionCandidateRecord],
    packets: list[EscalationPacketRecord],
    generated_at: str,
    *,
    limit: int,
) -> str:
    lines = [
        "# Background Connection Candidates",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "Generated candidates only. These records do not promote graph edges, scores, or source truth.",
        "",
        "## Summary",
        "",
        f"- Candidate count: {len(candidates)}",
        f"- Escalation packet count: {len(packets)}",
        f"- Review sample limit: {limit}",
        "",
        "## Top Candidates",
        "",
        "| Candidate | Type | Score | Gates | Source | Target | Why now |",
        "|---|---|---:|---|---|---|---|",
    ]
    for candidate in candidates[:limit]:
        gates = ",".join(name for name, ok in candidate.gates.items() if ok) or "none"
        source = ", ".join(candidate.source_asset_ids)
        target = ", ".join(candidate.target_asset_ids)
        lines.append(
            f"| `{candidate.connection_candidate_id}` | `{candidate.connection_type}` | "
            f"{candidate.connectivity_score:.3f} | {gates} | `{source}` | `{target}` | "
            f"{candidate.why_might_matter_now} |"
        )
    lines.extend(["", "## Red-Team Notes", ""])
    lines.extend(
        [
            "- Gate-before-score: failed safety, evidence, or authority gates block escalation.",
            "- Family dedup happens before escalation budget allocation.",
            "- Verified candidates may inform ceiling or edge-candidacy review, not current score.",
            "- No daemon, GitHub scan, source mutation, or autonomous model call is part of v1.",
        ]
    )
    return "\n".join(lines)


def escalation_packet_markdown(
    packets: list[EscalationPacketRecord],
    generated_at: str,
) -> str:
    lines = [
        "# Background Connection Escalation Packets",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "Manual review packets only. Tier 2 model verification remains outside v1.",
        "",
    ]
    if not packets:
        lines.extend(["No escalation packets selected.", ""])
        return "\n".join(lines)
    for packet in packets:
        lines.extend(
            [
                f"## Packet `{packet.packet_id}`",
                "",
                f"- Candidate: `{packet.connection_candidate_id}`",
                f"- Type: `{packet.proposed_connection_type}`",
                f"- Score: `{packet.connectivity_score:.3f}`",
                f"- Budget priority: `{packet.budget_priority}`",
                f"- Cold cue: `{packet.cold_memory_cue}`",
                f"- Deduped members: `{len(packet.deduped_member_candidate_ids)}`",
                f"- Why now: {packet.why_might_matter_now}",
                f"- Why false: {packet.why_might_be_false}",
                "",
                "Verifier tasks:",
                "",
            ]
        )
        lines.extend(f"- {task}" for task in packet.requested_verifier_tasks)
        lines.append("")
    return "\n".join(lines)


def run_background_connection_radar(
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    *,
    scan_id: str,
    attention: str = "recent",
    cold: str = "older",
    limit: int = 50,
    escalation_budget: int = 5,
    tau: float = 0.70,
    max_hops: int = 2,
    reserve_cold: int = 2,
    generated_at: str | None = None,
) -> BackgroundConnectionResult:
    generated = generated_at or utc_now()
    seeds = build_attention_seeds(
        assets,
        scan_id=scan_id,
        generated_at=generated,
        attention=attention,
        hot_limit=200,
    )
    candidates = build_connection_candidates(
        assets,
        edges,
        seeds,
        scan_id=scan_id,
        generated_at=generated,
        cold=cold,
        per_seed_cap=50,
        tau=tau,
    )
    packets = select_escalation_packets(
        candidates,
        assets,
        scan_id=scan_id,
        generated_at=generated,
        escalation_budget=escalation_budget,
        reserve_cold=reserve_cold,
    )
    expansion_maps = build_expansion_maps(
        packets,
        edges,
        scan_id=scan_id,
        generated_at=generated,
        max_hops=max_hops,
        max_nodes=25,
    )
    summary = {
        "methodology_version": METHODOLOGY_VERSION,
        "scan_id": scan_id,
        "attention_seed_count": len(seeds),
        "candidate_count": len(candidates),
        "eligible_candidate_count": sum(1 for candidate in candidates if candidate.escalation_eligible),
        "packet_count": len(packets),
        "expansion_map_count": len(expansion_maps),
        "tau": tau,
        "escalation_budget": escalation_budget,
        "reserve_cold": reserve_cold,
        "max_hops": max_hops,
        "limit": limit,
        "generated_at": generated,
        "gate_failures": {
            "safety_gate": sum(1 for candidate in candidates if not candidate.gates["safety_gate"]),
            "evidence_gate": sum(1 for candidate in candidates if not candidate.gates["evidence_gate"]),
            "authority_gate": sum(1 for candidate in candidates if not candidate.gates["authority_gate"]),
        },
        "output_type": "generated_candidate_report",
    }
    return BackgroundConnectionResult(seeds, candidates, packets, expansion_maps, summary)


def write_background_connection_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    edges: list[EdgeRecord],
    *,
    scan_id: str,
    attention: str = "recent",
    cold: str = "older",
    limit: int = 50,
    escalation_budget: int = 5,
    tau: float = 0.70,
    max_hops: int = 2,
    reserve_cold: int = 2,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = run_background_connection_radar(
        assets,
        edges,
        scan_id=scan_id,
        attention=attention,
        cold=cold,
        limit=limit,
        escalation_budget=escalation_budget,
        tau=tau,
        max_hops=max_hops,
        reserve_cold=reserve_cold,
        generated_at=generated_at,
    )
    learning_dir = repo_root / "processed" / "learning"
    reports_dir = repo_root / "processed" / "reports"
    attention_path = learning_dir / "background_attention_seeds.jsonl"
    candidates_path = learning_dir / "background_connection_candidates.jsonl"
    packets_path = learning_dir / "background_escalation_packets.jsonl"
    expansion_path = learning_dir / "background_expansion_maps.jsonl"
    candidates_report_path = reports_dir / "background_connection_candidates.md"
    packets_report_path = reports_dir / "background_connection_escalation_packets.md"
    write_jsonl(attention_path, [record.model_dump(mode="json") for record in result.attention_seeds])
    write_jsonl(candidates_path, [record.model_dump(mode="json") for record in result.candidates])
    write_jsonl(packets_path, [record.model_dump(mode="json") for record in result.packets])
    write_jsonl(expansion_path, [record.model_dump(mode="json") for record in result.expansion_maps])
    atomic_write_text(
        candidates_report_path,
        background_connection_markdown(
            result.candidates,
            result.packets,
            str(result.summary["generated_at"]),
            limit=limit,
        )
        + "\n",
    )
    atomic_write_text(
        packets_report_path,
        escalation_packet_markdown(
            result.packets,
            str(result.summary["generated_at"]),
        )
        + "\n",
    )
    return {
        **result.summary,
        "outputs": {
            "attention_seeds": str(attention_path),
            "connection_candidates": str(candidates_path),
            "escalation_packets": str(packets_path),
            "expansion_maps": str(expansion_path),
            "connection_report": str(candidates_report_path),
            "packet_report": str(packets_report_path),
        },
    }
