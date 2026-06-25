from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Literal

from .ids import edge_id, stable_id
from .models import AssetRecord, EdgeRecord, LearningLoopRecord
from .utils import atomic_write_text, utc_now, write_jsonl

AUTHORITY_BOUNDARY = (
    "Generated candidate only; source repositories retain authority; no source mutation, "
    "promotion, or implementation is authorized by this record."
)
ASSET_FAMILY_METHOD = "asset_family_recognizer_v1"
LEVERAGE_RANK = {"very_high": 3, "high": 2, "medium": 1, "low": 0}


@dataclass(frozen=True)
class AssetFamilyDefinition:
    pattern_id: str
    label: str
    leverage: Literal["high", "very_high"]
    useful_to_future_agents: str
    could_be_used_for: str
    missing_to_be_more_useful: str
    upside_range: tuple[int, int]
    lift_conditions: tuple[str, ...]
    asset_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()
    pattern_aliases: tuple[str, ...] = ()


FAMILY_DEFINITIONS: tuple[AssetFamilyDefinition, ...] = (
    AssetFamilyDefinition(
        pattern_id="governed_learning_loop_system",
        label="Governed learning loop system",
        leverage="very_high",
        useful_to_future_agents=(
            "Shows how an asset family improves itself through feedback, exceptions, "
            "review gates, and promoted rules."
        ),
        could_be_used_for="Agent memory, calibration, postflight lessons, and safer reuse.",
        missing_to_be_more_useful=(
            "Needs repeated before/after use records, reviewed promotion decisions, and "
            "failure-mode coverage."
        ),
        upside_range=(82, 96),
        lift_conditions=(
            "before/after asset-use feedback is captured",
            "human-reviewed promotions exist",
            "validators enforce the promoted rule",
        ),
        asset_types=("lesson", "workflow", "test", "document"),
        tags=("learning-loop", "governance"),
        capabilities=("capture_lessons", "govern_agents", "validate_contracts"),
        terms=("learning loop", "lesson", "handoff", "postflight", "feedback"),
        pattern_aliases=("governed_learning_loop",),
    ),
    AssetFamilyDefinition(
        pattern_id="route_isolated_evaluation_harness",
        label="Route-isolated evaluation harness",
        leverage="very_high",
        useful_to_future_agents=(
            "Separates asset forms and evaluation routes so one corpus, workflow, or "
            "authority layer does not contaminate another."
        ),
        could_be_used_for="Chunking, route-specific evals, context packets, and safer retrieval.",
        missing_to_be_more_useful=(
            "Needs labeled route outcomes, gold cases, fallback tests, and contamination tests."
        ),
        upside_range=(80, 95),
        lift_conditions=(
            "route-level precision and recall are measured",
            "gold or review packets exist for each route",
            "fallback behavior is tested",
        ),
        asset_types=("evaluation", "test", "workflow", "code", "document"),
        tags=("evaluation", "retrieval", "workflow"),
        capabilities=("validate_contracts", "retrieve_context"),
        terms=(
            "route",
            "routing",
            "form classification",
            "chunking",
            "context packet",
            "scorecard",
            "gold case",
        ),
    ),
    AssetFamilyDefinition(
        pattern_id="agent_skill_graph_system",
        label="Agent and skill graph system",
        leverage="very_high",
        useful_to_future_agents=(
            "Makes agent, skill, tool, and capability relationships discoverable instead "
            "of relying on a single top-down orchestrator."
        ),
        could_be_used_for="Skill selection, role routing, swarm planning, and capability gap review.",
        missing_to_be_more_useful=(
            "Needs observed asset-use feedback, conflict rules, and discovery-quality evals."
        ),
        upside_range=(82, 97),
        lift_conditions=(
            "agents report which skills/assets they used",
            "capability conflicts are modeled",
            "useful-at-K discovery metrics improve",
        ),
        asset_types=("agent", "skill", "workflow", "ontology", "taxonomy", "document"),
        tags=("agent", "skill", "knowledge-graph", "workflow"),
        capabilities=("govern_agents", "retrieve_context", "build_knowledge_graph"),
        terms=("agent", "skill", "capability registry", "tool route", "handoff", "orchestration"),
        pattern_aliases=("ai_agent_workflow", "knowledge_graph_system"),
    ),
    AssetFamilyDefinition(
        pattern_id="boundary_contamination_firewall",
        label="Boundary and contamination firewall",
        leverage="very_high",
        useful_to_future_agents=(
            "Tells future agents what evidence may support a source and what must never "
            "override source authority."
        ),
        could_be_used_for="Prompt-injection defense, source authority control, and review gates.",
        missing_to_be_more_useful=(
            "Needs attack tests, bypass policy, and reviewed enforcement boundaries."
        ),
        upside_range=(78, 94),
        lift_conditions=(
            "contamination cases are tested",
            "authority transfer is explicitly blocked",
            "bypass behavior is documented",
        ),
        asset_types=("workflow", "configuration", "test", "document", "schema"),
        tags=("security", "governance", "provenance"),
        capabilities=("protect_sensitive_data", "govern_agents", "validate_contracts"),
        terms=(
            "authority boundary",
            "source authority",
            "candidate-only",
            "contamination",
            "prompt injection",
            "quarantine",
        ),
        pattern_aliases=("security_governance_gate",),
    ),
    AssetFamilyDefinition(
        pattern_id="proposal_promotion_workflow",
        label="Proposal-to-promotion workflow",
        leverage="very_high",
        useful_to_future_agents=(
            "Shows how candidate observations become reviewed changes through a gate "
            "instead of silently becoming truth."
        ),
        could_be_used_for="Governed schema changes, rule updates, agent improvements, and roadmap gates.",
        missing_to_be_more_useful=(
            "Needs accepted, rejected, and rolled-back examples with evidence links."
        ),
        upside_range=(76, 93),
        lift_conditions=(
            "promotion decisions are logged",
            "rejections preserve lessons",
            "validators test the promoted behavior",
        ),
        asset_types=("workflow", "decision", "schema", "document", "code"),
        tags=("governance", "workflow", "provenance"),
        capabilities=("govern_agents", "validate_contracts", "capture_lessons"),
        terms=("proposal", "promotion", "human review", "review gate", "approval", "rollback"),
    ),
    AssetFamilyDefinition(
        pattern_id="frontier_signal_intake_loop",
        label="Frontier signal intake loop",
        leverage="high",
        useful_to_future_agents=(
            "Captures outside signals as candidates with provenance before deciding "
            "whether they deserve implementation."
        ),
        could_be_used_for="Research radar, missing-part discovery, and future capability watchlists.",
        missing_to_be_more_useful=(
            "Needs source terms review, freshness review, and false-positive calibration."
        ),
        upside_range=(68, 88),
        lift_conditions=(
            "source terms are reviewed",
            "watch items are compared against actual future usefulness",
            "license/security gates block unsafe imports",
        ),
        asset_types=("research", "document", "workflow", "dataset"),
        tags=("research-radar", "provenance"),
        capabilities=("research_missing_parts",),
        terms=("frontier", "signal", "watch item", "literature", "source terms", "license review"),
        pattern_aliases=("research_discovery",),
    ),
    AssetFamilyDefinition(
        pattern_id="gold_review_packet_system",
        label="Gold set and review packet system",
        leverage="very_high",
        useful_to_future_agents=(
            "Provides reusable reviewed examples that keep scoring, chunking, and "
            "proposal generation calibrated."
        ),
        could_be_used_for="Regression tests, review queues, calibration, and eval benchmarks.",
        missing_to_be_more_useful="Needs reviewed labels, sampling rationale, and calibration history.",
        upside_range=(78, 95),
        lift_conditions=(
            "labels are human-reviewed",
            "review samples cover hard negatives",
            "reports show precision/recall over time",
        ),
        asset_types=("evaluation", "test", "dataset", "document"),
        tags=("evaluation",),
        capabilities=("validate_contracts",),
        terms=("gold", "golden", "review packet", "label", "scorecard", "calibration"),
        pattern_aliases=("evaluation_harness",),
    ),
    AssetFamilyDefinition(
        pattern_id="duplicate_variant_preservation_system",
        label="Duplicate and variant preservation system",
        leverage="high",
        useful_to_future_agents=(
            "Keeps similar assets instead of deleting them, while surfacing shared core, "
            "strengths, neutral differences, and weaker parts."
        ),
        could_be_used_for="Cluster review, consolidation planning, and variant-aware reuse.",
        missing_to_be_more_useful=(
            "Needs human-reviewed deltas and merge/variant/supersession decisions."
        ),
        upside_range=(70, 90),
        lift_conditions=(
            "delta summaries identify better and different parts",
            "variants stay linked to source provenance",
            "reviewers choose keep, merge, or supersede",
        ),
        asset_types=("document", "code", "dataset", "archive"),
        tags=("provenance", "knowledge-graph"),
        capabilities=("catalog_assets", "build_knowledge_graph"),
        terms=("duplicate", "variant", "delta", "cluster", "shingle", "fingerprint", "hash"),
        pattern_aliases=("asset_cluster_delta",),
    ),
)

ROLE_TERMS: dict[str, tuple[str, ...]] = {
    "expectation_source": (
        "expectation",
        "expected",
        "evaluation",
        "test",
        "validator",
        "scorecard",
        "gold",
        "acceptance criteria",
        "contract",
    ),
    "exception_signal": (
        "exception",
        "failure",
        "failed",
        "error",
        "regression",
        "false positive",
        "false negative",
        "gap",
        "risk",
        "drift",
    ),
    "adaptation_proposal": (
        "adaptation",
        "proposal",
        "change proposal",
        "improvement",
        "rule update",
        "fix",
        "patch",
        "candidate",
        "upgrade",
    ),
    "review_gate": (
        "human review",
        "review gate",
        "approval",
        "gate",
        "preflight",
        "postflight",
        "governance",
        "accepted",
        "rejected",
    ),
    "promotion_target": (
        "promotion",
        "promote",
        "registry",
        "validator",
        "workflow",
        "schema",
        "policy",
        "contract",
        "roadmap evidence",
    ),
}


def _asset_text(asset: AssetRecord) -> str:
    metadata = asset.metadata
    metadata_text = " ".join(
        [
            str(metadata.get("excerpt", ""))[:8000],
            str(metadata.get("chunk_text", ""))[:12000],
            " ".join(str(token) for token in metadata.get("text_tokens", [])[:500]),
        ]
    )
    return " ".join(
        [
            asset.title,
            asset.description,
            asset.logical_path,
            " ".join(asset.tags),
            " ".join(asset.capabilities),
            " ".join(asset.needs),
            " ".join(asset.outcomes),
            metadata_text,
        ]
    ).lower()


def _declared_patterns(asset: AssetRecord) -> set[str]:
    metadata = asset.metadata
    result = {str(value) for value in metadata.get("asset_patterns", [])}
    for item in metadata.get("composite_patterns", []):
        if isinstance(item, dict) and item.get("pattern_id"):
            result.add(str(item["pattern_id"]))
    result.update(tag for tag in asset.tags if tag.endswith("_system") or tag.endswith("_workflow"))
    return result


def _term_evidence(text: str, terms_: Iterable[str]) -> list[str]:
    return [f"text:{term}" for term in sorted(set(terms_)) if term.lower() in text]


def _asset_family_evidence(asset: AssetRecord, definition: AssetFamilyDefinition) -> list[str]:
    evidence: list[str] = []
    declared = _declared_patterns(asset)
    pattern_ids = {definition.pattern_id, *definition.pattern_aliases}
    for pattern_id in sorted(declared & pattern_ids):
        evidence.append(f"declared_pattern:{pattern_id}")
    if asset.asset_type in definition.asset_types:
        evidence.append(f"asset_type:{asset.asset_type}")
    evidence.extend(f"tag:{tag}" for tag in sorted(set(asset.tags) & set(definition.tags)))
    evidence.extend(
        f"capability:{capability}"
        for capability in sorted(set(asset.capabilities) & set(definition.capabilities))
    )
    evidence.extend(_term_evidence(_asset_text(asset), definition.terms)[:8])
    return sorted(dict.fromkeys(evidence))


def detect_asset_family_matches(asset: AssetRecord) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for definition in FAMILY_DEFINITIONS:
        evidence = _asset_family_evidence(asset, definition)
        declared_match = any(item.startswith("declared_pattern:") for item in evidence)
        if not declared_match and len(evidence) < 2:
            continue
        matches.append(
            {
                "pattern_id": definition.pattern_id,
                "label": definition.label,
                "leverage": definition.leverage,
                "asset_id": asset.asset_id,
                "evidence": evidence,
                "review_status": "generated_candidate",
            }
        )
    return sorted(
        matches,
        key=lambda item: (
            -LEVERAGE_RANK[str(item["leverage"])],
            str(item["pattern_id"]),
            str(item["asset_id"]),
        ),
    )


def _filter_assets(assets: list[AssetRecord], source_id: str) -> list[AssetRecord]:
    if source_id == "all":
        return list(assets)
    return [asset for asset in assets if asset.source_id == source_id]


def _score_summary(assets: list[AssetRecord]) -> dict[str, Any]:
    scores = sorted(asset.value_score for asset in assets)
    if not scores:
        return {"current_score_range": [0.0, 0.0], "current_score_midpoint": 0.0}
    return {
        "current_score_range": [round(scores[0], 2), round(scores[-1], 2)],
        "current_score_midpoint": round(float(median(scores)), 2),
    }


def build_asset_family_candidates(
    assets: list[AssetRecord], *, source_id: str = "all", review_sample: int = 50
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filtered = _filter_assets(assets, source_id)
    matches_by_pattern: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_id = {asset.asset_id: asset for asset in filtered}
    for asset in filtered:
        for match in detect_asset_family_matches(asset):
            matches_by_pattern[str(match["pattern_id"])].append(match)

    candidates: list[dict[str, Any]] = []
    for definition in FAMILY_DEFINITIONS:
        matches = sorted(
            matches_by_pattern.get(definition.pattern_id, []),
            key=lambda item: (
                -by_id[str(item["asset_id"])].value_score,
                by_id[str(item["asset_id"])].logical_path,
            ),
        )
        if not matches:
            continue
        matched_assets = [by_id[str(match["asset_id"])] for match in matches if match["asset_id"] in by_id]
        score_summary = _score_summary(matched_assets)
        candidates.append(
            {
                "pattern_id": definition.pattern_id,
                "label": definition.label,
                "leverage": definition.leverage,
                "matched_asset_count": len(matched_assets),
                **score_summary,
                "upside_score_range": list(definition.upside_range),
                "delta_to_upside_midpoint": round(
                    (sum(definition.upside_range) / 2)
                    - float(score_summary["current_score_midpoint"]),
                    2,
                ),
                "useful_to_future_agents": definition.useful_to_future_agents,
                "could_be_used_for": definition.could_be_used_for,
                "missing_to_be_more_useful": definition.missing_to_be_more_useful,
                "lift_conditions": list(definition.lift_conditions),
                "sample_matches": matches[:review_sample],
                "review_status": "generated_candidate",
            }
        )
    candidates.sort(
        key=lambda item: (
            -LEVERAGE_RANK[str(item["leverage"])],
            -float(item["current_score_midpoint"]),
            str(item["pattern_id"]),
        )
    )
    summary = {
        "source_id": source_id,
        "assets_considered": len(filtered),
        "candidate_family_count": len(candidates),
        "candidate_asset_matches": sum(len(item["sample_matches"]) for item in candidates),
        "output_type": "generated_candidate_report",
    }
    return candidates, summary


def _asset_groups(assets: list[AssetRecord]) -> dict[str, list[AssetRecord]]:
    by_id = {asset.asset_id: asset for asset in assets}
    groups: dict[str, list[AssetRecord]] = {
        asset.asset_id: [asset] for asset in assets if asset.asset_type == "repository"
    }
    source_groups: dict[str, list[AssetRecord]] = defaultdict(list)
    for asset in assets:
        if asset.asset_type == "repository":
            continue
        if asset.parent_asset_id and asset.parent_asset_id in by_id:
            groups.setdefault(asset.parent_asset_id, [by_id[asset.parent_asset_id]]).append(asset)
        else:
            source_groups[f"source:{asset.source_id}"].append(asset)
    for key, values in source_groups.items():
        if values:
            groups[key] = values
    return groups


def _role_evidence(asset: AssetRecord, role: str) -> list[str]:
    evidence = _term_evidence(_asset_text(asset), ROLE_TERMS[role])[:10]
    if role == "expectation_source" and asset.asset_type in {"evaluation", "test", "schema"}:
        evidence.append(f"asset_type:{asset.asset_type}")
    if role == "exception_signal" and asset.asset_type in {"lesson", "test"}:
        evidence.append(f"asset_type:{asset.asset_type}")
    if role == "review_gate" and {"governance", "security"} & set(asset.tags):
        evidence.extend(f"tag:{tag}" for tag in sorted({"governance", "security"} & set(asset.tags)))
    if role == "promotion_target" and asset.asset_type in {"schema", "workflow", "decision"}:
        evidence.append(f"asset_type:{asset.asset_type}")
    if role == "adaptation_proposal" and asset.asset_type in {"decision", "workflow", "document"}:
        evidence.append(f"asset_type:{asset.asset_type}")
    return sorted(dict.fromkeys(evidence))


def _best_role_assets(group_assets: list[AssetRecord]) -> dict[str, list[dict[str, Any]]]:
    roles: dict[str, list[dict[str, Any]]] = {}
    for role in ROLE_TERMS:
        scored: list[dict[str, Any]] = []
        for asset in group_assets:
            evidence = _role_evidence(asset, role)
            if evidence:
                scored.append(
                    {
                        "asset_id": asset.asset_id,
                        "title": asset.title,
                        "logical_path": asset.logical_path,
                        "asset_type": asset.asset_type,
                        "evidence": evidence,
                        "score": len(evidence),
                    }
                )
        scored.sort(key=lambda item: (-int(item["score"]), str(item["logical_path"])))
        if scored:
            roles[role] = scored[:5]
    return roles


def _role_label(role_assets: dict[str, list[dict[str, Any]]], role: str) -> str:
    values = role_assets.get(role, [])
    if not values:
        return f"Not detected in current catalog for {role}; human review needed."
    first = values[0]
    return f"{first['title']} ({first['logical_path']})"


def _loop_type(role_assets: dict[str, list[dict[str, Any]]]) -> str:
    if {"exception_signal", "adaptation_proposal"}.issubset(role_assets):
        return "exception_to_adaptation_loop"
    if {"expectation_source", "promotion_target"}.issubset(role_assets):
        return "evaluation_promotion_loop"
    return "governed_learning_loop"


def _risk_label(assets: list[AssetRecord]) -> Literal["low", "medium", "high"]:
    if any(asset.sensitivity in {"confidential", "restricted"} for asset in assets):
        return "high"
    if any(asset.confidence == "low" for asset in assets):
        return "medium"
    return "medium"


def build_learning_loop_candidates(
    assets: list[AssetRecord],
    *,
    scan_id: str,
    source_id: str = "all",
    generated_at: str | None = None,
) -> list[LearningLoopRecord]:
    filtered = _filter_assets(assets, source_id)
    generated = generated_at or utc_now()
    records: list[LearningLoopRecord] = []
    for group_id, group_assets in sorted(_asset_groups(filtered).items()):
        role_assets = _best_role_assets(group_assets)
        if len(role_assets) < 4 or "review_gate" not in role_assets:
            continue
        source_ids = sorted(
            {
                str(item["asset_id"])
                for values in role_assets.values()
                for item in values[:2]
            }
        )
        if not source_ids:
            continue
        loop_type = _loop_type(role_assets)
        role_counts = {role: len(values) for role, values in sorted(role_assets.items())}
        record = LearningLoopRecord(
            learning_loop_id=stable_id(
                "learning-loop",
                scan_id,
                group_id,
                loop_type,
                ",".join(source_ids),
            ),
            learning_loop_type=loop_type,  # type: ignore[arg-type]
            source_asset_ids=source_ids,
            expectation_source=_role_label(role_assets, "expectation_source"),
            exception_signal=_role_label(role_assets, "exception_signal"),
            adaptation_proposal=_role_label(role_assets, "adaptation_proposal"),
            review_gate=_role_label(role_assets, "review_gate"),
            promotion_target=_role_label(role_assets, "promotion_target"),
            evidence={
                "group_id": group_id,
                "role_assets": role_assets,
                "role_counts": role_counts,
                "candidate_only": True,
                "source_mutation_forbidden": True,
            },
            confidence="high" if len(role_assets) == len(ROLE_TERMS) else "medium",
            risk=_risk_label(group_assets),
            authority_boundary=AUTHORITY_BOUNDARY,
            generated_at=generated,
            scan_id=scan_id,
        )
        records.append(record)
    return sorted(records, key=lambda item: item.learning_loop_id)


def _edge_record(
    edge_type: str,
    source_asset_id: str,
    target_asset_id: str,
    *,
    evidence: dict[str, Any],
    scan_id: str,
    created_at: str,
    confidence: float = 0.64,
) -> EdgeRecord | None:
    if source_asset_id == target_asset_id:
        return None
    return EdgeRecord(
        edge_id=edge_id(edge_type, source_asset_id, target_asset_id),
        edge_type=edge_type,
        source_asset_id=source_asset_id,
        target_asset_id=target_asset_id,
        method=ASSET_FAMILY_METHOD,
        confidence=confidence,
        evidence={**evidence, "candidate_only": True, "source_mutation_forbidden": True},
        created_at=created_at,
        scan_id=scan_id,
    )


def _first_role_asset(record: LearningLoopRecord, role: str) -> str | None:
    values = record.evidence.get("role_assets", {}).get(role, [])
    if not values:
        return None
    first = values[0]
    if isinstance(first, dict) and first.get("asset_id"):
        return str(first["asset_id"])
    return None


def build_learning_loop_edges(
    learning_loops: list[LearningLoopRecord], *, scan_id: str, created_at: str | None = None
) -> list[EdgeRecord]:
    generated = created_at or utc_now()
    edges: dict[str, EdgeRecord] = {}
    for record in learning_loops:
        exception = _first_role_asset(record, "exception_signal")
        adaptation = _first_role_asset(record, "adaptation_proposal")
        review = _first_role_asset(record, "review_gate")
        promotion = _first_role_asset(record, "promotion_target")
        edge_specs = [
            ("produces_learning_signal", exception, adaptation),
            ("requires_human_gate", adaptation, review),
            ("supports_but_cannot_override", review, promotion),
        ]
        for edge_type, source_asset_id, target_asset_id in edge_specs:
            if not source_asset_id or not target_asset_id:
                continue
            edge = _edge_record(
                edge_type,
                source_asset_id,
                target_asset_id,
                evidence={
                    "learning_loop_id": record.learning_loop_id,
                    "learning_loop_type": record.learning_loop_type,
                },
                scan_id=scan_id,
                created_at=generated,
            )
            if edge:
                edges[edge.edge_id] = edge
    return sorted(edges.values(), key=lambda edge: edge.edge_id)


def _asset_label(asset_id: str, by_id: dict[str, AssetRecord]) -> str:
    asset = by_id.get(asset_id)
    if not asset:
        return asset_id
    return f"{asset.title} [{asset.asset_type}] `{asset.logical_path}`"


def asset_family_markdown(
    candidates: list[dict[str, Any]],
    assets: list[AssetRecord],
    *,
    source_id: str,
    generated_at: str,
) -> str:
    by_id = {asset.asset_id: asset for asset in assets}
    lines = [
        "# Asset Family Recognition",
        "",
        "Generated candidate report only. Current score is shown before upside.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Source filter: `{source_id}`",
        f"- Candidate families: **{len(candidates)}**",
        "- No source repository mutation, promotion, or GitHub scanning is implied.",
        "",
    ]
    if not candidates:
        lines.append("No asset-family candidates were detected in the current catalog.")
        lines.append("")
        return "\n".join(lines)
    for candidate in candidates:
        lines.extend(
            [
                f"## {candidate['label']}",
                "",
                f"- Pattern ID: `{candidate['pattern_id']}`",
                f"- Leverage: `{candidate['leverage']}`",
                f"- Matched assets: **{candidate['matched_asset_count']}**",
                f"- Current value score range: `{candidate['current_score_range']}`",
                f"- Current value score midpoint: **{candidate['current_score_midpoint']}**",
                f"- Candidate upside score range: `{candidate['upside_score_range']}`",
                f"- Delta to upside midpoint: **{candidate['delta_to_upside_midpoint']}**",
                f"- Useful to future agents: {candidate['useful_to_future_agents']}",
                f"- Could be used for: {candidate['could_be_used_for']}",
                f"- Missing to be more useful: {candidate['missing_to_be_more_useful']}",
                "- Lift conditions:",
            ]
        )
        for condition in candidate["lift_conditions"]:
            lines.append(f"  - {condition}")
        lines.extend(["", "### Review Sample", ""])
        for match in candidate["sample_matches"][:10]:
            asset = by_id.get(str(match["asset_id"]))
            evidence = ", ".join(match["evidence"][:6])
            label = _asset_label(str(match["asset_id"]), by_id) if asset else str(match["asset_id"])
            lines.append(f"- {label}: {evidence}")
        lines.append("")
    return "\n".join(lines)


def logos_asset_family_markdown(
    candidates: list[dict[str, Any]],
    assets: list[AssetRecord],
    *,
    generated_at: str,
) -> str:
    logos_asset_ids = {
        asset.asset_id
        for asset in assets
        if "logos" in f"{asset.title} {asset.logical_path} {asset.source_id}".lower()
    }
    lines = [
        "# Logos Asset Family Candidates",
        "",
        "Generated candidate report only. Logos is treated as a seed example, not a hard-coded domain.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Logos-like assets in current catalog: **{len(logos_asset_ids)}**",
        "",
    ]
    if not logos_asset_ids:
        lines.extend(
            [
                "No Logos-like assets were found in the current catalog.",
                "",
                "## Source-Scope Gate",
                "",
                "Do not broaden scanning automatically. Review `config/sources.local.yaml` and "
                "authorize a bounded local source scope before scanning Logos repositories.",
                "",
            ]
        )
        return "\n".join(lines)
    for candidate in candidates:
        logos_matches = [
            match
            for match in candidate["sample_matches"]
            if str(match["asset_id"]) in logos_asset_ids
        ]
        if not logos_matches:
            continue
        lines.extend(
            [
                f"## {candidate['label']}",
                "",
                f"- Pattern ID: `{candidate['pattern_id']}`",
                f"- Current value score midpoint: **{candidate['current_score_midpoint']}**",
                f"- Candidate upside score range: `{candidate['upside_score_range']}`",
                f"- Missing to be more useful: {candidate['missing_to_be_more_useful']}",
                "",
            ]
        )
        for match in logos_matches[:10]:
            lines.append(f"- `{match['asset_id']}`: {', '.join(match['evidence'][:6])}")
        lines.append("")
    return "\n".join(lines)


def learning_loop_markdown(
    records: list[LearningLoopRecord], generated_at: str, *, review_sample: int
) -> str:
    lines = [
        "# Learning Loop Candidates",
        "",
        "Generated candidate report only. These records do not promote lessons or rules.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Candidate learning loops: **{len(records)}**",
        f"- Review sample shown: **{min(len(records), review_sample)}**",
        "",
    ]
    if not records:
        lines.append("No learning-loop candidates were detected in the current catalog.")
        lines.append("")
        return "\n".join(lines)
    for record in records[:review_sample]:
        lines.extend(
            [
                f"## {record.learning_loop_id}",
                "",
                f"- Type: `{record.learning_loop_type}`",
                f"- Confidence: `{record.confidence}`",
                f"- Risk: `{record.risk}`",
                f"- Source assets: {', '.join(record.source_asset_ids[:10])}",
                f"- Expectation source: {record.expectation_source}",
                f"- Exception signal: {record.exception_signal}",
                f"- Adaptation proposal: {record.adaptation_proposal}",
                f"- Review gate: {record.review_gate}",
                f"- Promotion target: {record.promotion_target}",
                "",
            ]
        )
    return "\n".join(lines)


def write_asset_family_reports(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    source_id: str = "all",
    review_sample: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    filtered = _filter_assets(assets, source_id)
    candidates, summary = build_asset_family_candidates(
        assets,
        source_id=source_id,
        review_sample=review_sample,
    )
    reports_dir = repo_root / "processed" / "reports"
    asset_family_path = reports_dir / "asset_family_recognition.md"
    logos_path = reports_dir / "logos_asset_family_candidates.md"
    atomic_write_text(
        asset_family_path,
        asset_family_markdown(
            candidates,
            filtered,
            source_id=source_id,
            generated_at=generated,
        )
        + "\n",
    )
    atomic_write_text(
        logos_path,
        logos_asset_family_markdown(candidates, filtered, generated_at=generated) + "\n",
    )
    return {
        **summary,
        "asset_family_report": str(asset_family_path),
        "logos_report": str(logos_path),
    }


def write_learning_loop_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    scan_id: str,
    source_id: str = "all",
    review_sample: int = 25,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    records = build_learning_loop_candidates(
        assets,
        scan_id=scan_id,
        source_id=source_id,
        generated_at=generated,
    )
    edges = build_learning_loop_edges(records, scan_id=scan_id, created_at=generated)
    learning_dir = repo_root / "processed" / "learning"
    reports_dir = repo_root / "processed" / "reports"
    jsonl_path = learning_dir / "learning_loop_candidates.jsonl"
    edges_path = learning_dir / "asset_family_candidate_edges.jsonl"
    report_path = reports_dir / "learning_loop_candidates.md"
    write_jsonl(jsonl_path, [record.model_dump(mode="json") for record in records])
    write_jsonl(edges_path, [edge.model_dump(mode="json") for edge in edges])
    atomic_write_text(
        report_path,
        learning_loop_markdown(records, generated, review_sample=review_sample) + "\n",
    )
    return {
        "source_id": source_id,
        "scan_id": scan_id,
        "candidate_learning_loop_count": len(records),
        "candidate_edge_count": len(edges),
        "review_sample_size": min(len(records), review_sample),
        "learning_loop_candidates": str(jsonl_path),
        "candidate_edges": str(edges_path),
        "learning_loop_report": str(report_path),
        "output_type": "generated_candidate_report",
    }
