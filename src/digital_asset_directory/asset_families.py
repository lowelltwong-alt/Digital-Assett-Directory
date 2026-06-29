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
WORKFLOW_USEFULNESS_METHOD = "workflow-sweep-usefulness-v1"
WORKFLOW_SWEEP_NOISE_PATH_PARTS = (
    "/.pytest-tmp-root/",
    "\\.pytest-tmp-root\\",
    "/pytest-of-",
    "\\pytest-of-",
    "/__pycache__/",
    "\\__pycache__\\",
    "/.pytest_cache/",
    "\\.pytest_cache\\",
    "/_codex_worktrees/",
    "\\_codex_worktrees\\",
    "/.worktrees/",
    "\\.worktrees\\",
    "/node_modules/",
    "\\node_modules\\",
    "/.venv/",
    "\\.venv\\",
    "/venv/",
    "\\venv\\",
)
WORKFLOW_USEFULNESS_ASSET_TYPE_BONUS = {
    "workflow": 12.0,
    "schema": 10.0,
    "test": 9.0,
    "code": 8.0,
    "configuration": 7.0,
    "decision": 7.0,
    "evaluation": 7.0,
    "document": 5.0,
    "repository": 4.0,
}
WORKFLOW_USEFULNESS_PATH_ADJUSTMENT = {
    "canonical_or_active_source": 8.0,
    "repo_collection_variant": -4.0,
    "archive_variant": -14.0,
    "generated_output": -16.0,
    "noise_or_temp": -35.0,
}
WORKFLOW_SWEEP_PRIORITY_BONUS = {
    "governance_workflows": 8.0,
    "learning_feedback_workflows": 6.0,
    "evaluation_calibration_workflows": 6.0,
    "security_privacy_workflows": 6.0,
    "scoring_ranking_workflows": 4.0,
}


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


@dataclass(frozen=True)
class WorkflowSweepDefinition:
    sweep_id: str
    label: str
    priority: int
    rationale: str
    useful_to_future_agents: str
    follow_up_sweep: str
    asset_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()


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
    AssetFamilyDefinition(
        pattern_id="cross_repo_governance_dependency_map_pattern",
        label="Cross-repo governance dependency map pattern",
        leverage="very_high",
        useful_to_future_agents=(
            "Shows how an upstream governance authority, child mirrors, AI discovery "
            "surfaces, repo contracts, PR descriptions, validators, and tests stay aligned."
        ),
        could_be_used_for=(
            "Future repo scaffolds, multi-repo governance reviews, child-repo mirror checks, "
            "and PR drift prevention."
        ),
        missing_to_be_more_useful=(
            "Needs repo-specific authority approval, watched path lists, companion surfaces, "
            "and child mirror validators for the adopting repo family."
        ),
        upside_range=(84, 98),
        lift_conditions=(
            "upstream map names real authority and watched governance paths",
            "child mirrors are validator-backed",
            "front doors, TOCs, repo contracts, and PR descriptions route to the map",
            "tests prove governance-facing drift fails closed",
        ),
        asset_types=("workflow", "configuration", "document", "test", "code", "schema"),
        tags=("governance", "governance-map", "provenance", "workflow", "ai-navigation"),
        capabilities=("govern_agents", "validate_contracts", "catalog_assets"),
        terms=(
            "governance dependency map",
            "governance_dependency_map",
            "governance dependency-map mirror",
            "changed path gate",
            "required companion surfaces",
            "child repo mirror",
            "upstream governance",
            "pr description",
        ),
    ),
)

WORKFLOW_SWEEPS: tuple[WorkflowSweepDefinition, ...] = (
    WorkflowSweepDefinition(
        sweep_id="governance_workflows",
        label="Governance workflows",
        priority=10,
        rationale=(
            "Run first because governance, authority boundaries, review gates, and "
            "promotion rules shape what future agents are allowed to trust or change."
        ),
        useful_to_future_agents=(
            "Finds preflight/postflight gates, human review paths, source authority "
            "rules, approval flows, and load-bearing decision checks."
        ),
        follow_up_sweep="learning_feedback_workflows",
        asset_types=("workflow", "decision", "configuration", "document", "test", "schema"),
        tags=("governance", "security", "provenance"),
        capabilities=("govern_agents", "validate_contracts", "protect_sensitive_data"),
        terms=(
            "governance",
            "preflight",
            "postflight",
            "human review",
            "review gate",
            "approval",
            "source authority",
            "authority boundary",
            "candidate-only",
            "load-bearing",
            "risk tier",
            "promotion",
            "rollback",
            "governance dependency map",
            "governance_dependency_map",
            "governance dependency-map mirror",
            "changed path gate",
            "required companion surfaces",
            "child repo mirror",
            "pr description",
        ),
        patterns=(
            "governed_learning_loop_system",
            "boundary_contamination_firewall",
            "proposal_promotion_workflow",
            "load_bearing_decision_review_system",
            "security_governance_system",
            "cross_repo_governance_dependency_map_pattern",
        ),
    ),
    WorkflowSweepDefinition(
        sweep_id="learning_feedback_workflows",
        label="Learning and feedback workflows",
        priority=20,
        rationale=(
            "Run after governance because learning loops should improve behavior without "
            "overriding authority or promoting candidates automatically."
        ),
        useful_to_future_agents=(
            "Finds lessons, handoffs, asset-use feedback, pay-forward notes, and "
            "exception-to-adaptation loops."
        ),
        follow_up_sweep="evaluation_calibration_workflows",
        asset_types=("lesson", "workflow", "document", "test"),
        tags=("learning-loop", "governance", "provenance"),
        capabilities=("capture_lessons", "govern_agents"),
        terms=(
            "learning loop",
            "lesson learned",
            "handoff",
            "postflight",
            "asset-use feedback",
            "pay-forward",
            "reuse when",
            "avoid when",
            "exception",
            "adaptation",
        ),
        patterns=(
            "governed_learning_loop_system",
            "asset_use_pay_forward_loop",
            "asset_use_instance",
        ),
    ),
    WorkflowSweepDefinition(
        sweep_id="evaluation_calibration_workflows",
        label="Evaluation and calibration workflows",
        priority=30,
        rationale=(
            "Run early because tests, scorecards, review packets, and labels determine "
            "whether generated candidates can be trusted enough for review."
        ),
        useful_to_future_agents=(
            "Finds gold sets, validation commands, review queues, scorecards, and "
            "calibration evidence."
        ),
        follow_up_sweep="agent_skill_orchestration_workflows",
        asset_types=("evaluation", "test", "dataset", "workflow", "document"),
        tags=("evaluation", "workflow"),
        capabilities=("validate_contracts", "score_assets"),
        terms=(
            "evaluation",
            "calibration",
            "gold",
            "golden",
            "review packet",
            "scorecard",
            "label",
            "precision",
            "recall",
            "validator",
            "pytest",
            "ruff",
        ),
        patterns=("gold_review_packet_system", "route_isolated_evaluation_harness"),
    ),
    WorkflowSweepDefinition(
        sweep_id="agent_skill_orchestration_workflows",
        label="Agent and skill orchestration workflows",
        priority=40,
        rationale=(
            "Run after governance and evaluation so agent composition is discovered "
            "with boundaries and quality checks attached."
        ),
        useful_to_future_agents=(
            "Finds agent routes, skill graphs, capability registries, orchestration "
            "plans, and handoff surfaces."
        ),
        follow_up_sweep="retrieval_context_workflows",
        asset_types=("agent", "skill", "workflow", "prompt", "document", "ontology"),
        tags=("agent", "skill", "workflow", "knowledge-graph"),
        capabilities=("govern_agents", "retrieve_context", "build_knowledge_graph"),
        terms=(
            "agent",
            "skill",
            "capability registry",
            "orchestration",
            "handoff",
            "tool route",
            "swarm",
            "planner",
            "worker",
        ),
        patterns=("agent_skill_graph_system", "ai_agent_workflow_system"),
    ),
    WorkflowSweepDefinition(
        sweep_id="retrieval_context_workflows",
        label="Retrieval and context workflows",
        priority=50,
        rationale=(
            "Run after orchestration because agents need the right retrieval and "
            "context routes before composing assets."
        ),
        useful_to_future_agents=(
            "Finds chunking, route classification, context packets, search, graph, and "
            "retrieval pipelines."
        ),
        follow_up_sweep="security_privacy_workflows",
        asset_types=("workflow", "code", "evaluation", "document", "ontology", "taxonomy"),
        tags=("retrieval", "knowledge-graph", "workflow"),
        capabilities=("retrieve_context", "build_knowledge_graph", "catalog_assets"),
        terms=(
            "retrieval",
            "context pack",
            "context packet",
            "chunking",
            "route classification",
            "embedding",
            "rerank",
            "knowledge graph",
            "ontology",
        ),
        patterns=("route_isolated_evaluation_harness", "knowledge_graph_retrieval_system"),
    ),
    WorkflowSweepDefinition(
        sweep_id="security_privacy_workflows",
        label="Security and privacy workflows",
        priority=60,
        rationale=(
            "Run before external intake and automation because untrusted inputs and "
            "sensitive data can contaminate every downstream workflow."
        ),
        useful_to_future_agents=(
            "Finds prompt-injection defenses, secret handling, redaction, access "
            "control, and unsafe-composition warnings."
        ),
        follow_up_sweep="research_intake_workflows",
        asset_types=("workflow", "configuration", "test", "document", "schema", "code"),
        tags=("security", "governance", "provenance"),
        capabilities=("protect_sensitive_data", "govern_agents", "validate_contracts"),
        terms=(
            "security",
            "privacy",
            "secret",
            "redact",
            "prompt injection",
            "untrusted",
            "access control",
            "credential",
            "pii",
            "unsafe composition",
        ),
        patterns=("boundary_contamination_firewall", "security_governance_system"),
    ),
    WorkflowSweepDefinition(
        sweep_id="research_intake_workflows",
        label="Research and external-intake workflows",
        priority=70,
        rationale=(
            "Run after security because external sources, papers, repos, and ideas "
            "need provenance, license, and source-terms review."
        ),
        useful_to_future_agents=(
            "Finds frontier signal loops, research radars, source terms checks, and "
            "license/security review gates."
        ),
        follow_up_sweep="duplicate_variant_workflows",
        asset_types=("research", "document", "workflow", "dataset"),
        tags=("research-radar", "provenance"),
        capabilities=("research_missing_parts",),
        terms=(
            "research",
            "frontier",
            "signal",
            "watch item",
            "literature",
            "source terms",
            "license review",
            "external",
        ),
        patterns=("frontier_signal_intake_loop",),
    ),
    WorkflowSweepDefinition(
        sweep_id="duplicate_variant_workflows",
        label="Duplicate and variant workflows",
        priority=80,
        rationale=(
            "Run before consolidation because near-duplicates may be lineage evidence, "
            "semantic evolution, or different useful variants."
        ),
        useful_to_future_agents=(
            "Finds duplicate clusters, deltas, variant families, semantic evolution, "
            "and merge-or-keep review paths."
        ),
        follow_up_sweep="scoring_ranking_workflows",
        asset_types=("workflow", "code", "document", "dataset", "archive", "schema"),
        tags=("provenance", "knowledge-graph"),
        capabilities=("catalog_assets", "build_knowledge_graph"),
        terms=(
            "duplicate",
            "variant",
            "delta",
            "cluster",
            "shingle",
            "fingerprint",
            "semantic evolution",
            "near-duplicate",
            "lineage",
        ),
        patterns=("duplicate_variant_preservation_system", "asset_cluster_delta"),
    ),
    WorkflowSweepDefinition(
        sweep_id="scoring_ranking_workflows",
        label="Scoring and ranking workflows",
        priority=90,
        rationale=(
            "Run after evidence-gathering sweeps because scores and rankings should be "
            "grounded in explicit methodology and calibration."
        ),
        useful_to_future_agents=(
            "Finds value-score methodology, ranking models, confidence bands, upside "
            "ranges, and score calibration workflows."
        ),
        follow_up_sweep="ci_validation_workflows",
        asset_types=("model", "algorithm", "workflow", "document", "code", "configuration"),
        tags=("evaluation", "governance"),
        capabilities=("score_assets", "validate_contracts"),
        terms=(
            "value score",
            "ranking",
            "calibration",
            "confidence",
            "threshold",
            "methodology",
            "ceiling",
            "upside",
            "risk score",
        ),
        patterns=("model_algorithm_system",),
    ),
    WorkflowSweepDefinition(
        sweep_id="ci_validation_workflows",
        label="CI and validation workflows",
        priority=100,
        rationale=(
            "Run as the closing operational sweep because CI and validation show what "
            "actually checks the system repeatedly."
        ),
        useful_to_future_agents=(
            "Finds GitHub Actions, test orchestration, lint, validate commands, and "
            "pre-push or enforcement wrappers."
        ),
        follow_up_sweep="human review of sweep results",
        asset_types=("workflow", "configuration", "test", "code", "document"),
        tags=("evaluation", "governance", "workflow"),
        capabilities=("validate_contracts", "govern_agents"),
        terms=(
            ".github/workflows",
            "ci",
            "github actions",
            "pytest",
            "ruff",
            "validate",
            "pre-push",
            "nox",
            "test orchestration",
        ),
        patterns=("evaluation_contract_system", "security_governance_system"),
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


def _workflow_sweep_evidence(asset: AssetRecord, definition: WorkflowSweepDefinition) -> list[str]:
    evidence: list[str] = []
    declared = _declared_patterns(asset)
    if asset.asset_type in definition.asset_types:
        evidence.append(f"asset_type:{asset.asset_type}")
    evidence.extend(f"tag:{tag}" for tag in sorted(set(asset.tags) & set(definition.tags)))
    evidence.extend(
        f"capability:{capability}"
        for capability in sorted(set(asset.capabilities) & set(definition.capabilities))
    )
    for pattern_id in sorted(declared & set(definition.patterns)):
        evidence.append(f"declared_pattern:{pattern_id}")
    evidence.extend(_term_evidence(_asset_text(asset), definition.terms)[:10])
    return sorted(dict.fromkeys(evidence))


def _repository_label(asset: AssetRecord, by_id: dict[str, AssetRecord]) -> str:
    path_hint = _repository_hint_from_logical_path(asset.logical_path)
    if asset.asset_type == "repository":
        return path_hint or asset.logical_path or asset.title or asset.source_id
    if asset.parent_asset_id and asset.parent_asset_id in by_id:
        parent = by_id[asset.parent_asset_id]
        parent_path = parent.logical_path.strip().replace("\\", "/")
        if parent_path in {"", ".", "git-projects", "git-projects/."}:
            return path_hint or parent.source_id
        return parent.logical_path or parent.title or parent.source_id
    return path_hint or asset.source_id


def _repository_hint_from_logical_path(logical_path: str) -> str:
    parts = [part for part in logical_path.replace("\\", "/").split("/") if part and part != "."]
    if not parts:
        return ""
    if parts[0] != "git-projects":
        return "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
    if len(parts) < 3:
        return "/".join(parts)
    category = parts[1]
    package = parts[2]
    if package in {"repos", "zips", "_codex_worktrees"} and len(parts) >= 4:
        return "/".join(parts[:4])
    return f"{parts[0]}/{category}/{package}"


def _is_workflow_sweep_noise(asset: AssetRecord) -> bool:
    path = asset.logical_path.replace("\\", "/").lower()
    return any(part.replace("\\", "/").lower() in path for part in WORKFLOW_SWEEP_NOISE_PATH_PARTS)


def _workflow_path_class(logical_path: str) -> str:
    path = logical_path.replace("\\", "/").lower()
    if any(part.replace("\\", "/").lower() in path for part in WORKFLOW_SWEEP_NOISE_PATH_PARTS):
        return "noise_or_temp"
    if "/processed/" in path or "/raw/" in path or "/state/" in path:
        return "generated_output"
    if "/99_archive/" in path or "/archive/" in path or "/zips/" in path:
        return "archive_variant"
    if "/repos/" in path:
        return "repo_collection_variant"
    return "canonical_or_active_source"


def _workflow_usefulness_tier(score: float) -> str:
    if score >= 72:
        return "high_usefulness_candidate"
    if score >= 58:
        return "medium_usefulness_candidate"
    if score >= 40:
        return "context_dependent_candidate"
    return "low_signal_candidate"


def _workflow_usefulness_category(tier: str, path_class: str) -> str:
    if path_class == "noise_or_temp":
        return "exclude_from_default_review"
    if path_class in {"archive_variant", "repo_collection_variant"}:
        return "variant_or_delta_review"
    if tier == "high_usefulness_candidate":
        return "review_first_for_reuse"
    if tier == "medium_usefulness_candidate":
        return "review_after_first_batch"
    if tier == "context_dependent_candidate":
        return "keep_for_contextual_review"
    return "low_signal_keep_as_evidence"


def _workflow_usefulness_record(
    sweep: dict[str, Any], match: dict[str, Any]
) -> dict[str, Any]:
    path_class = _workflow_path_class(str(match["logical_path"]))
    evidence_count = len(match.get("evidence", []))
    declared_pattern_bonus = (
        8.0
        if any(str(item).startswith("declared_pattern:") for item in match.get("evidence", []))
        else 0.0
    )
    utility_score = (
        float(match["value_score"])
        + WORKFLOW_USEFULNESS_ASSET_TYPE_BONUS.get(str(match["asset_type"]), 3.0)
        + min(evidence_count * 3.0, 18.0)
        + declared_pattern_bonus
        + WORKFLOW_USEFULNESS_PATH_ADJUSTMENT.get(path_class, 0.0)
        + WORKFLOW_SWEEP_PRIORITY_BONUS.get(str(sweep["sweep_id"]), 0.0)
    )
    utility_score = round(max(0.0, min(100.0, utility_score)), 2)
    tier = _workflow_usefulness_tier(utility_score)
    category = _workflow_usefulness_category(tier, path_class)
    return {
        "methodology_version": WORKFLOW_USEFULNESS_METHOD,
        "sweep_id": sweep["sweep_id"],
        "sweep_label": sweep["label"],
        "asset_id": match["asset_id"],
        "title": match["title"],
        "repository": match["repository"],
        "logical_path": match["logical_path"],
        "asset_type": match["asset_type"],
        "current_value_score": match["value_score"],
        "utility_score": utility_score,
        "usefulness_tier": tier,
        "usefulness_category": category,
        "path_class": path_class,
        "evidence": match.get("evidence", []),
        "review_status": "generated_candidate",
        "why_useful": _workflow_why_useful(str(sweep["sweep_id"]), str(match["asset_type"])),
        "review_guidance": _workflow_review_guidance(category),
    }


def _workflow_why_useful(sweep_id: str, asset_type: str) -> str:
    if sweep_id == "governance_workflows":
        return "May define authority, review, approval, or promotion behavior that constrains later workflow use."
    if sweep_id == "learning_feedback_workflows":
        return "May preserve how an asset was used, improved, blocked, or paid forward for future agents."
    if sweep_id == "evaluation_calibration_workflows":
        return "May provide tests, labels, scorecards, or validation evidence for candidate quality."
    if sweep_id == "agent_skill_orchestration_workflows":
        return "May show how agents, skills, prompts, tools, or handoffs compose into a reusable workflow."
    if sweep_id == "retrieval_context_workflows":
        return "May help future agents find, chunk, route, or ground the right context."
    if sweep_id == "security_privacy_workflows":
        return "May reduce prompt-injection, secret-handling, unsafe-composition, or privacy risk."
    if sweep_id == "research_intake_workflows":
        return "May bring external ideas into the asset graph with provenance and review gates."
    if sweep_id == "duplicate_variant_workflows":
        return "May explain whether similar assets are copies, variants, semantic evolution, or merge candidates."
    if sweep_id == "scoring_ranking_workflows":
        return "May define score, rank, confidence, upside, or calibration behavior future agents will inherit."
    if asset_type == "workflow":
        return "May be a reusable multi-step workflow asset."
    return "May support a larger workflow family as a component asset."


def _workflow_review_guidance(category: str) -> str:
    if category == "review_first_for_reuse":
        return "Inspect first for direct reuse, pay-forward notes, and missing validation."
    if category == "review_after_first_batch":
        return "Review after high-usefulness candidates or when this sweep becomes active."
    if category == "variant_or_delta_review":
        return "Compare against nearby canonical variants before reuse; preserve useful deltas."
    if category == "keep_for_contextual_review":
        return "Keep as contextual evidence until a task needs this workflow family."
    if category == "exclude_from_default_review":
        return "Exclude from ordinary workflow review; use only for archaeology or lineage analysis."
    return "Keep as low-signal evidence; do not spend human review first."


def build_workflow_sweep_candidates(
    assets: list[AssetRecord],
    *,
    source_id: str = "all",
    review_sample: int = 50,
    include_noise: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_filtered = _filter_assets(assets, source_id)
    filtered = [
        asset for asset in source_filtered if include_noise or not _is_workflow_sweep_noise(asset)
    ]
    excluded_noise_count = len(source_filtered) - len(filtered)
    by_id = {asset.asset_id: asset for asset in filtered}
    sweep_records: list[dict[str, Any]] = []
    for definition in sorted(WORKFLOW_SWEEPS, key=lambda sweep: sweep.priority):
        matches: list[dict[str, Any]] = []
        for asset in filtered:
            evidence = _workflow_sweep_evidence(asset, definition)
            declared_match = any(item.startswith("declared_pattern:") for item in evidence)
            if not declared_match and len(evidence) < 2:
                continue
            matches.append(
                {
                    "asset_id": asset.asset_id,
                    "title": asset.title,
                    "logical_path": asset.logical_path,
                    "asset_type": asset.asset_type,
                    "repository": _repository_label(asset, by_id),
                    "value_score": round(asset.value_score, 2),
                    "confidence": asset.confidence,
                    "evidence": evidence,
                    "review_status": "generated_candidate",
                }
            )
        matches.sort(
            key=lambda item: (
                -float(item["value_score"]),
                str(item["repository"]),
                str(item["logical_path"]),
            )
        )
        repo_count = len({str(item["repository"]) for item in matches})
        score_summary = _score_summary([by_id[str(item["asset_id"])] for item in matches])
        sweep_records.append(
            {
                "sweep_id": definition.sweep_id,
                "label": definition.label,
                "priority": definition.priority,
                "rationale": definition.rationale,
                "useful_to_future_agents": definition.useful_to_future_agents,
                "follow_up_sweep": definition.follow_up_sweep,
                "matched_asset_count": len(matches),
                "matched_repository_count": repo_count,
                **score_summary,
                "sample_matches": matches[:review_sample],
                "review_status": "generated_candidate",
            }
        )
    summary = {
        "source_id": source_id,
        "assets_considered": len(filtered),
        "noise_assets_excluded": excluded_noise_count,
        "include_noise": include_noise,
        "workflow_sweep_count": len(sweep_records),
        "candidate_asset_matches": sum(len(item["sample_matches"]) for item in sweep_records),
        "first_sweep": WORKFLOW_SWEEPS[0].sweep_id,
        "output_type": "generated_candidate_report",
    }
    return sweep_records, summary


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


def workflow_sweeps_index_markdown(
    sweep_records: list[dict[str, Any]],
    *,
    source_id: str,
    generated_at: str,
    include_noise: bool = False,
) -> str:
    lines = [
        "# Workflow Sweeps",
        "",
        "Generated candidate report only. Governance workflows are intentionally first.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Source filter: `{source_id}`",
        f"- Include temp/noise paths: `{include_noise}`",
        f"- Sweep count: **{len(sweep_records)}**",
        "- No source repository mutation, promotion, hook installation, or GitHub scanning is implied.",
        "",
        "## Sweep Order",
        "",
    ]
    for item in sweep_records:
        lines.extend(
            [
                f"### {item['priority']}. {item['label']}",
                "",
                f"- Sweep ID: `{item['sweep_id']}`",
                f"- Matched assets: **{item['matched_asset_count']}**",
                f"- Matched repositories: **{item['matched_repository_count']}**",
                f"- Current score midpoint: **{item['current_score_midpoint']}**",
                f"- Why this sweep exists: {item['rationale']}",
                f"- Useful to future agents: {item['useful_to_future_agents']}",
                f"- Next sweep: `{item['follow_up_sweep']}`",
                "",
            ]
        )
    return "\n".join(lines)


def workflow_sweep_detail_markdown(
    sweep: dict[str, Any],
    *,
    generated_at: str,
) -> str:
    lines = [
        f"# {sweep['label']}",
        "",
        "Generated candidate workflow-sweep report only.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Sweep ID: `{sweep['sweep_id']}`",
        f"- Priority: `{sweep['priority']}`",
        f"- Matched assets: **{sweep['matched_asset_count']}**",
        f"- Matched repositories: **{sweep['matched_repository_count']}**",
        f"- Current score range: `{sweep['current_score_range']}`",
        f"- Current score midpoint: **{sweep['current_score_midpoint']}**",
        f"- Why this sweep exists: {sweep['rationale']}",
        f"- Useful to future agents: {sweep['useful_to_future_agents']}",
        f"- Next sweep: `{sweep['follow_up_sweep']}`",
        "",
        "## Review Sample",
        "",
    ]
    if not sweep["sample_matches"]:
        lines.append("No candidates were detected for this sweep in the current catalog.")
        lines.append("")
        return "\n".join(lines)
    for match in sweep["sample_matches"]:
        evidence = ", ".join(match["evidence"][:8])
        lines.extend(
            [
                f"### {match['title']}",
                "",
                f"- Asset ID: `{match['asset_id']}`",
                f"- Repository: `{match['repository']}`",
                f"- Path: `{match['logical_path']}`",
                f"- Asset type: `{match['asset_type']}`",
                f"- Current value score: **{match['value_score']}**",
                f"- Confidence: `{match['confidence']}`",
                f"- Evidence: {evidence}",
                f"- Review status: `{match['review_status']}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_workflow_usefulness_review(
    sweep_records: list[dict[str, Any]],
    *,
    per_sweep_limit: int = 25,
    global_limit: int = 75,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for sweep in sweep_records:
        sweep_candidates = [
            _workflow_usefulness_record(sweep, match)
            for match in sweep.get("sample_matches", [])
        ]
        sweep_candidates.sort(
            key=lambda item: (
                -float(item["utility_score"]),
                str(item["usefulness_category"]),
                str(item["repository"]),
                str(item["logical_path"]),
            )
        )
        records.extend(sweep_candidates[:per_sweep_limit])
    records.sort(
        key=lambda item: (
            -float(item["utility_score"]),
            str(item["sweep_id"]),
            str(item["repository"]),
            str(item["logical_path"]),
        )
    )
    category_counts: dict[str, int] = defaultdict(int)
    tier_counts: dict[str, int] = defaultdict(int)
    path_class_counts: dict[str, int] = defaultdict(int)
    sweep_counts: dict[str, int] = defaultdict(int)
    for record in records:
        category_counts[str(record["usefulness_category"])] += 1
        tier_counts[str(record["usefulness_tier"])] += 1
        path_class_counts[str(record["path_class"])] += 1
        sweep_counts[str(record["sweep_id"])] += 1
    return {
        "methodology_version": WORKFLOW_USEFULNESS_METHOD,
        "records_considered": len(records),
        "category_counts": dict(sorted(category_counts.items())),
        "tier_counts": dict(sorted(tier_counts.items())),
        "path_class_counts": dict(sorted(path_class_counts.items())),
        "sweep_counts": dict(sorted(sweep_counts.items())),
        "records": records[:global_limit],
        "review_status": "generated_candidate",
    }


def workflow_usefulness_markdown(
    review: dict[str, Any],
    *,
    generated_at: str,
) -> str:
    records = review["records"]
    lines = [
        "# Workflow Sweep Usefulness Review",
        "",
        "Generated candidate report only. This ranks review priority; it does not label assets as truth.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Methodology: `{review['methodology_version']}`",
        f"- Candidate records counted: **{review['records_considered']}**",
        f"- Candidate records shown: **{len(records)}**",
        "- The same asset may appear under multiple sweeps when it has multiple useful roles.",
        "",
        "## Methodology",
        "",
        "Utility score range: `0..100`, clamped.",
        "",
        "Formula:",
        "",
        "```text",
        "utility_score = current_value_score",
        "  + asset_type_bonus",
        "  + min(evidence_count * 3, 18)",
        "  + declared_pattern_bonus",
        "  + path_class_adjustment",
        "  + sweep_priority_bonus",
        "```",
        "",
        "Important adjustments:",
        "",
        "- `canonical_or_active_source`: `+8`",
        "- `repo_collection_variant`: `-4`",
        "- `archive_variant`: `-14`",
        "- `generated_output`: `-16`",
        "- `noise_or_temp`: `-35`",
        "- Governance, learning, evaluation, security, and scoring sweeps receive small priority bonuses.",
        "- Archive and copied repo variants can still be useful, but are routed to delta review before reuse.",
        "",
        "## Counts",
        "",
        "### By Category",
        "",
    ]
    for key, value in review["category_counts"].items():
        lines.append(f"- `{key}`: **{value}**")
    lines.extend(["", "### By Tier", ""])
    for key, value in review["tier_counts"].items():
        lines.append(f"- `{key}`: **{value}**")
    lines.extend(["", "### By Path Class", ""])
    for key, value in review["path_class_counts"].items():
        lines.append(f"- `{key}`: **{value}**")
    lines.extend(["", "## Highest Utility Candidates", ""])
    if not records:
        lines.append("No workflow usefulness candidates were available from the current sweep sample.")
        lines.append("")
        return "\n".join(lines)
    for record in records:
        evidence = ", ".join(record["evidence"][:8])
        lines.extend(
            [
                f"### {record['title']}",
                "",
                f"- Utility score: **{record['utility_score']}**",
                f"- Current value score: **{record['current_value_score']}**",
                f"- Tier: `{record['usefulness_tier']}`",
                f"- Category: `{record['usefulness_category']}`",
                f"- Path class: `{record['path_class']}`",
                f"- Sweep: `{record['sweep_id']}`",
                f"- Repository: `{record['repository']}`",
                f"- Path: `{record['logical_path']}`",
                f"- Asset type: `{record['asset_type']}`",
                f"- Why useful: {record['why_useful']}",
                f"- Review guidance: {record['review_guidance']}",
                f"- Evidence: {evidence}",
                "",
            ]
        )
    return "\n".join(lines)


def write_workflow_sweep_reports(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    source_id: str = "all",
    review_sample: int = 50,
    include_noise: bool = False,
    usefulness_per_sweep_limit: int = 25,
    usefulness_global_limit: int = 75,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    sweep_records, summary = build_workflow_sweep_candidates(
        assets,
        source_id=source_id,
        review_sample=review_sample,
        include_noise=include_noise,
    )
    sweep_dir = repo_root / "processed" / "reports" / "workflow_sweeps"
    index_path = sweep_dir / "workflow_sweeps_index.md"
    atomic_write_text(
        index_path,
        workflow_sweeps_index_markdown(
            sweep_records,
            source_id=source_id,
            generated_at=generated,
            include_noise=include_noise,
        )
        + "\n",
    )
    detail_paths: dict[str, str] = {}
    for sweep in sweep_records:
        detail_path = sweep_dir / f"{sweep['sweep_id']}.md"
        atomic_write_text(
            detail_path,
            workflow_sweep_detail_markdown(sweep, generated_at=generated) + "\n",
        )
        detail_paths[str(sweep["sweep_id"])] = str(detail_path)
    usefulness_review = build_workflow_usefulness_review(
        sweep_records,
        per_sweep_limit=usefulness_per_sweep_limit,
        global_limit=usefulness_global_limit,
    )
    usefulness_report_path = sweep_dir / "workflow_usefulness_review.md"
    usefulness_jsonl_path = sweep_dir / "workflow_usefulness_candidates.jsonl"
    atomic_write_text(
        usefulness_report_path,
        workflow_usefulness_markdown(usefulness_review, generated_at=generated) + "\n",
    )
    write_jsonl(usefulness_jsonl_path, usefulness_review["records"])
    return {
        **summary,
        "workflow_sweeps_index": str(index_path),
        "workflow_sweep_reports": detail_paths,
        "workflow_usefulness_report": str(usefulness_report_path),
        "workflow_usefulness_candidates": str(usefulness_jsonl_path),
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
