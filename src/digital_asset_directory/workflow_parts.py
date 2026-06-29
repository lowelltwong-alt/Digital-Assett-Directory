from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from .asset_families import detect_asset_family_matches
from .ids import edge_id, stable_id
from .models import AssetRecord, EdgeRecord, WorkflowPartRecord
from .utils import atomic_write_text, utc_now, write_jsonl

METHODOLOGY_VERSION = "workflow-part-recognition-v1"
AUTHORITY_BOUNDARY = (
    "Generated candidate only; source repositories retain authority; no source mutation, "
    "promotion, implementation, or cross-authority composition is authorized by this record."
)

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

NOISE_PATH_MARKERS = (
    "/.pytest-tmp-root/",
    "/pytest-of-",
    "/__pycache__/",
    "/.pytest_cache/",
    "/_codex_worktrees/",
    "/.worktrees/",
    "/node_modules/",
    "/.venv/",
    "/venv/",
)

PUBLIC_SAFE_EXCLUDED_MARKERS = (
    "/raw/",
    "/data/",
    "/output/",
    "/outputs/",
    "/processed/",
    "/state/",
    "/audit/events/",
    ".env",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "private_key",
)

VALIDATION_PATH_PREFIXES = ("tests/", "test/", "scripts/validate", "scripts/audit", "noxfile")


@dataclass(frozen=True)
class PartDefinition:
    part_type: Literal[
        "validator",
        "contract",
        "gate",
        "runner",
        "orchestrator",
        "prompt_part",
        "capability_provider",
        "human_gate",
        "eval_gold",
        "learning_signal",
        "boundary_map",
        "decision_record",
        "lesson_part",
        "calibration_gate",
        "quarantine_gate",
    ]
    role_in_workflow: str
    default_pattern_id: str
    context_tags: tuple[str, ...]
    applies_when: tuple[str, ...]
    does_not_apply_when: tuple[str, ...]
    danger_if_misapplied: str
    composition_affordances: tuple[str, ...]
    asset_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    path_terms: tuple[str, ...] = ()
    text_terms: tuple[str, ...] = ()
    min_evidence: int = 2


PART_DEFINITIONS: tuple[PartDefinition, ...] = (
    PartDefinition(
        part_type="validator",
        role_in_workflow="Checks behavior, schema conformance, generated outputs, or safety boundaries.",
        default_pattern_id="evaluation_contract_system",
        context_tags=("schema_contract", "software_repo_checklist"),
        applies_when=("A workflow needs deterministic proof that an output or contract still holds.",),
        does_not_apply_when=("The task is exploratory and no contract or output is being relied on.",),
        danger_if_misapplied="A validator candidate may be mistaken for passing evidence when it has not been run.",
        composition_affordances=("tests", "stabilized_by", "should_precede"),
        asset_types=("test",),
        capabilities=("validate_contracts",),
        path_terms=("test", "tests/", "validate", "audit", "check"),
        text_terms=("pytest", "validate", "validator", "schema conformance", "fixture"),
    ),
    PartDefinition(
        part_type="contract",
        role_in_workflow="Constrains record shape, graph meaning, or interface expectations.",
        default_pattern_id="evaluation_contract_system",
        context_tags=("schema_contract", "source_authority"),
        applies_when=("A workflow emits structured data, graph edges, or reusable records.",),
        does_not_apply_when=("The work is unstructured prose and no downstream consumer depends on shape.",),
        danger_if_misapplied="A contract can freeze a bad abstraction before the domain is understood.",
        composition_affordances=("implements", "governed_by", "tests"),
        asset_types=("schema", "ontology", "taxonomy"),
        tags=("schema", "knowledge-graph"),
        path_terms=("schema", "schemas/", "ontology", "taxonomy"),
        text_terms=("json schema", "schema", "ontology", "taxonomy", "contract"),
        min_evidence=1,
    ),
    PartDefinition(
        part_type="gate",
        role_in_workflow="Blocks unsafe promotion, mutation, default changes, or release until checks pass.",
        default_pattern_id="ai_work_cycle_governance_system",
        context_tags=("human_gate", "load_bearing_decision", "software_repo_checklist"),
        applies_when=("A workflow can affect downstream repos, source authority, or future defaults.",),
        does_not_apply_when=("The task is a trivial reversible edit with no shared behavior.",),
        danger_if_misapplied="Too much ceremony can hide the actual risk or slow harmless work.",
        composition_affordances=("requires_human_gate", "governed_by", "blocked_by"),
        asset_types=("workflow", "configuration", "test", "document"),
        tags=("governance", "security"),
        path_terms=(".github/workflows", "hooks", "preflight", "postflight", "gate"),
        text_terms=("preflight", "postflight", "approval", "human gate", "stop condition"),
    ),
    PartDefinition(
        part_type="runner",
        role_in_workflow="Runs one or more workflow steps through a command, task file, or script.",
        default_pattern_id="ai_work_cycle_governance_system",
        context_tags=("software_repo_checklist", "dependency_ordering"),
        applies_when=("A workflow needs a repeatable command surface or ordered execution step.",),
        does_not_apply_when=("The asset only documents behavior and is not intended to run anything.",),
        danger_if_misapplied="A runner can execute side effects if treated as safe without inspecting scope.",
        composition_affordances=("has_workflow_step", "depends_on", "should_precede"),
        asset_types=("code", "configuration", "workflow"),
        path_terms=("scripts/", "noxfile", "makefile", "justfile", "taskfile", "build"),
        text_terms=("run", "build", "execute", "command", "task"),
    ),
    PartDefinition(
        part_type="orchestrator",
        role_in_workflow="Orders several parts into a repeatable work cycle or runbook.",
        default_pattern_id="ai_work_cycle_governance_system",
        context_tags=("ai_navigation", "software_repo_checklist", "dependency_ordering"),
        applies_when=("An agent or human must choose steps, routes, validations, and stop conditions.",),
        does_not_apply_when=("Only one isolated action is needed.",),
        danger_if_misapplied="The orchestrator may become top-heavy process rather than helpful ordering.",
        composition_affordances=("has_workflow_step", "routes_to", "should_precede"),
        asset_types=("workflow", "document"),
        tags=("workflow", "governance"),
        path_terms=("runbook", "workflow", "start_here", "front_door"),
        text_terms=("workflow", "runbook", "orchestration", "preflight", "postflight", "route"),
    ),
    PartDefinition(
        part_type="prompt_part",
        role_in_workflow="Guides an AI or agent through a bounded prompt, instruction, or front-door surface.",
        default_pattern_id="ai_agent_workflow_system",
        context_tags=("ai_navigation", "source_authority"),
        applies_when=("An AI needs deterministic instructions, routing, or role boundaries.",),
        does_not_apply_when=("No agent or prompt surface is involved.",),
        danger_if_misapplied="Prompt text can override source authority if copied into the wrong context.",
        composition_affordances=("governed_by", "routes_to", "supports_but_cannot_override"),
        asset_types=("prompt", "agent", "document"),
        tags=("agent", "skill", "workflow"),
        path_terms=("prompt", "prompts/", "ai_front_door", "agents.md", "start_here"),
        text_terms=("system prompt", "agent", "codex", "claude", "front door", "instructions"),
    ),
    PartDefinition(
        part_type="capability_provider",
        role_in_workflow="Provides a reusable capability through an agent, skill, adapter, code path, or registry.",
        default_pattern_id="agent_skill_graph_system",
        context_tags=("asset_use_pay_forward", "software_repo_checklist"),
        applies_when=("A workflow needs a reusable capability and must find the right provider.",),
        does_not_apply_when=("The asset is passive evidence or a one-off output.",),
        danger_if_misapplied="A capability provider may be reused outside its authority or dependency boundary.",
        composition_affordances=("satisfies_need", "composes_with", "depends_on"),
        asset_types=("agent", "skill", "code"),
        tags=("agent", "skill"),
        path_terms=("skills", "agents", "adapters", "plugins"),
        text_terms=("capability", "adapter", "provider", "skill", "agent"),
    ),
    PartDefinition(
        part_type="human_gate",
        role_in_workflow="Requires human review before promotion, mutation, default change, or downstream use.",
        default_pattern_id="proposal_promotion_workflow",
        context_tags=("human_gate", "load_bearing_decision", "fresh_eyes_review"),
        applies_when=("A candidate could change source truth, defaults, scoring, schema, or downstream repos.",),
        does_not_apply_when=("The output is generated-only and no promotion or default change is proposed.",),
        danger_if_misapplied="A human gate label can be faked or overused unless evidence identifies the reviewer.",
        composition_affordances=("requires_human_gate", "governed_by", "blocked_by"),
        asset_types=("workflow", "decision", "document"),
        tags=("governance",),
        path_terms=("gate", "review", "evidence", "roadmap"),
        text_terms=("human review", "approval", "reviewer", "verified", "gate evidence"),
    ),
    PartDefinition(
        part_type="eval_gold",
        role_in_workflow="Supplies expected, gold, fixture, benchmark, or review examples for evaluation.",
        default_pattern_id="gold_review_packet_system",
        context_tags=("gold_promotion", "calibration", "schema_contract"),
        applies_when=("A workflow needs reusable expected examples or measured behavior.",),
        does_not_apply_when=("Examples are exploratory, synthetic noise, or not reviewed.",),
        danger_if_misapplied="A weak example set can lock in false confidence and hide missing cases.",
        composition_affordances=("has_gold_set", "has_review_packet", "tests"),
        asset_types=("evaluation", "test", "dataset", "document"),
        tags=("evaluation",),
        path_terms=("gold", "golden", "fixture", "fixtures", "eval", "benchmark"),
        text_terms=("gold", "golden", "expected output", "scorecard", "benchmark", "fixture"),
    ),
    PartDefinition(
        part_type="learning_signal",
        role_in_workflow="Surfaces failures, exceptions, feedback, postflights, or lessons for future adaptation.",
        default_pattern_id="governed_learning_loop_system",
        context_tags=("learning_loop", "asset_use_pay_forward", "repeated_failure"),
        applies_when=("A workflow should remember why an issue happened or how an asset was used.",),
        does_not_apply_when=("No reusable future behavior is implied.",),
        danger_if_misapplied="A lesson stripped from context can become a dangerous universal rule.",
        composition_affordances=("produces_learning_signal", "learned_from", "applies_when"),
        asset_types=("lesson", "document", "workflow"),
        tags=("learning-loop",),
        path_terms=("lesson", "handoff", "postflight", "feedback", "learning"),
        text_terms=("lesson", "handoff", "postflight", "feedback", "exception", "failure"),
    ),
    PartDefinition(
        part_type="boundary_map",
        role_in_workflow="Defines source authority, privacy, public-safe, or cross-repo boundaries.",
        default_pattern_id="boundary_contamination_firewall",
        context_tags=("source_authority", "human_gate"),
        applies_when=("A workflow crosses source, privacy, public/private, or generated/truth boundaries.",),
        does_not_apply_when=("The task stays inside one safe generated-output boundary.",),
        danger_if_misapplied="A boundary map can be mistaken for permission to transfer authority.",
        composition_affordances=("supports_but_cannot_override", "contaminates_if_default", "governed_by"),
        asset_types=("workflow", "document", "configuration", "schema"),
        tags=("governance", "security", "provenance"),
        path_terms=("authority", "privacy", "security", "public_safe", "data_flow"),
        text_terms=("source authority", "authority boundary", "public-safe", "privacy", "trust zone"),
    ),
    PartDefinition(
        part_type="decision_record",
        role_in_workflow="Records a chosen path, rejection, gate outcome, roadmap decision, or design rationale.",
        default_pattern_id="load_bearing_decision_review_system",
        context_tags=("load_bearing_decision", "human_gate"),
        applies_when=("Future agents need to know why a choice was made or deferred.",),
        does_not_apply_when=("No durable decision or rationale exists.",),
        danger_if_misapplied="A stale decision can be treated as permanent even after conditions change.",
        composition_affordances=("governed_by", "supports_but_cannot_override", "learned_from"),
        asset_types=("decision", "document"),
        path_terms=("decision", "decisions", "adr", "roadmap/evidence", "gate-evidence"),
        text_terms=("decision", "rationale", "accepted", "rejected", "deferred"),
    ),
    PartDefinition(
        part_type="lesson_part",
        role_in_workflow="Carries a reusable rule or lesson with applicability and non-applicability limits.",
        default_pattern_id="governed_learning_loop_system",
        context_tags=("learning_loop", "counterfactual_sequence", "source_authority"),
        applies_when=("A future task resembles the recorded context and risks repeating the same mistake.",),
        does_not_apply_when=("The context differs or the lesson lacks evidence.",),
        danger_if_misapplied="A context-bound lesson can cause the wrong fix in a different domain.",
        composition_affordances=("applies_when", "does_not_apply_when", "dangerous_out_of_context"),
        asset_types=("lesson", "document"),
        tags=("learning-loop",),
        path_terms=("lesson", "learning-rule", "deterministic-learning"),
        text_terms=("applies_when", "does_not_apply_when", "danger_if", "lesson"),
    ),
    PartDefinition(
        part_type="calibration_gate",
        role_in_workflow="Connects scores, labels, thresholds, false positives, and false negatives to review.",
        default_pattern_id="calibration_ab_gate_system",
        context_tags=("calibration", "score_methodology", "fresh_eyes_review"),
        applies_when=("Generated scores or thresholds are used for review, ranking, or defaults.",),
        does_not_apply_when=("Only raw observations are stored and no score or threshold is used.",),
        danger_if_misapplied="Uncalibrated labels can bless a broken scoring or sampling process.",
        composition_affordances=("tests", "has_review_packet", "requires_human_gate"),
        asset_types=("evaluation", "workflow", "document", "test"),
        tags=("calibration", "evaluation"),
        path_terms=("calibration", "score", "threshold", "review"),
        text_terms=("false positive", "false-negative", "threshold", "calibration", "precision"),
    ),
    PartDefinition(
        part_type="quarantine_gate",
        role_in_workflow="Routes noisy, sensitive, unsafe, or untrusted material out of default use.",
        default_pattern_id="security_scanner_quarantine_system",
        context_tags=("source_authority", "temp_fixture_noise", "human_gate"),
        applies_when=("Inputs may be sensitive, malicious, noisy, fixture-only, or unsafe by default.",),
        does_not_apply_when=("The source and safety posture are already reviewed and bounded.",),
        danger_if_misapplied="Over-quarantine can hide useful lineage evidence; under-quarantine can leak or execute bad data.",
        composition_affordances=("quarantines", "blocked_by", "unsafe_composition_with"),
        asset_types=("workflow", "configuration", "test", "code", "document"),
        tags=("security", "governance"),
        path_terms=("quarantine", "exclude", "security", "secret", "privacy"),
        text_terms=("quarantine", "exclude", "secret", "prompt injection", "untrusted input"),
    ),
)


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


def _asset_text(asset: AssetRecord) -> str:
    metadata = asset.metadata or {}
    metadata_text = " ".join(
        [
            str(metadata.get("excerpt", ""))[:4000],
            str(metadata.get("chunk_text", ""))[:8000],
            " ".join(str(token) for token in metadata.get("text_tokens", [])[:250]),
            " ".join(str(value) for value in metadata.get("asset_patterns", [])[:25]),
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


def _normalized_path(logical_path: str) -> str:
    return logical_path.replace("\\", "/").lower()


def _path_class(asset: AssetRecord) -> str:
    path = _normalized_path(asset.logical_path)
    if any(marker in path for marker in NOISE_PATH_MARKERS):
        return "noise_or_temp"
    if any(marker in path for marker in PUBLIC_SAFE_EXCLUDED_MARKERS):
        return "public_safe_excluded"
    if "/99_archive/" in path or "/archive/" in path or "/zips/" in path:
        return "archive_variant"
    if "/repos/" in path:
        return "repo_collection_variant"
    return "canonical_or_active_source"


def _public_safe(asset: AssetRecord) -> bool:
    if asset.sensitivity in {"confidential", "restricted"}:
        return False
    return _path_class(asset) == "canonical_or_active_source"


def _term_evidence(prefix: str, text: str, terms_: Iterable[str]) -> list[str]:
    return [f"{prefix}:{term}" for term in sorted(set(terms_)) if term.lower() in text]


def _definition_evidence(asset: AssetRecord, definition: PartDefinition) -> list[str]:
    path = _normalized_path(asset.logical_path)
    text = _asset_text(asset)
    evidence: list[str] = []
    if asset.asset_type in definition.asset_types:
        evidence.append(f"asset_type:{asset.asset_type}")
    evidence.extend(f"tag:{tag}" for tag in sorted(set(asset.tags) & set(definition.tags)))
    evidence.extend(
        f"capability:{capability}"
        for capability in sorted(set(asset.capabilities) & set(definition.capabilities))
    )
    evidence.extend(_term_evidence("path", path, definition.path_terms)[:8])
    evidence.extend(_term_evidence("text", text, definition.text_terms)[:10])
    return sorted(dict.fromkeys(evidence))


def _pattern_id(asset: AssetRecord, definition: PartDefinition) -> tuple[str, list[str]]:
    matches = detect_asset_family_matches(asset)
    match_ids = [str(match["pattern_id"]) for match in matches]
    if definition.default_pattern_id in match_ids:
        return definition.default_pattern_id, [f"asset_family_match:{definition.default_pattern_id}"]
    if match_ids:
        return match_ids[0], [f"asset_family_match:{match_ids[0]}"]
    return definition.default_pattern_id, [f"default_pattern:{definition.default_pattern_id}"]


def detect_workflow_part_matches(asset: AssetRecord) -> list[dict[str, Any]]:
    if not _public_safe(asset):
        return []
    matches: list[dict[str, Any]] = []
    for definition in PART_DEFINITIONS:
        evidence = _definition_evidence(asset, definition)
        if len(evidence) < definition.min_evidence:
            continue
        pattern_id, pattern_evidence = _pattern_id(asset, definition)
        matches.append(
            {
                "part_type": definition.part_type,
                "asset_id": asset.asset_id,
                "asset_pattern_id": pattern_id,
                "role_in_workflow": definition.role_in_workflow,
                "evidence": [*pattern_evidence, *evidence],
                "path_class": _path_class(asset),
                "review_status": "generated_candidate",
            }
        )
    return sorted(matches, key=lambda item: (str(item["part_type"]), str(item["asset_id"])))


def _family_keys(assets: list[AssetRecord], edges: list[EdgeRecord]) -> dict[str, str]:
    asset_ids = {asset.asset_id for asset in assets}
    uf = _UnionFind(asset_ids)
    for edge in edges:
        if edge.edge_type in DUPLICATE_EDGE_TYPES:
            if edge.source_asset_id in asset_ids and edge.target_asset_id in asset_ids:
                uf.union(edge.source_asset_id, edge.target_asset_id)
    root_counts: Counter[str] = Counter(uf.find(asset.asset_id) for asset in assets)
    keys: dict[str, str] = {}
    for asset in assets:
        root = uf.find(asset.asset_id)
        if root_counts[root] > 1:
            keys[asset.asset_id] = f"duplicate-family:{root}"
        elif asset.content_sha256 and asset.size_bytes > 0:
            keys[asset.asset_id] = f"sha256:{asset.content_sha256}"
        elif asset.content_hash:
            keys[asset.asset_id] = f"content-hash:{asset.content_hash}"
        else:
            keys[asset.asset_id] = f"path:{asset.source_id}:{_normalized_path(asset.logical_path)}"
    return keys


def _definition_by_part_type(part_type: str) -> PartDefinition:
    for definition in PART_DEFINITIONS:
        if definition.part_type == part_type:
            return definition
    raise KeyError(part_type)


def _source_filter(assets: list[AssetRecord], source_id: str) -> list[AssetRecord]:
    if source_id == "all":
        return list(assets)
    return [asset for asset in assets if asset.source_id == source_id]


def _validation_commands(asset: AssetRecord, part_type: str) -> list[str]:
    path = asset.logical_path.replace("\\", "/")
    lowered = path.lower()
    if part_type != "validator":
        return []
    if lowered.endswith(".py") and lowered.startswith(VALIDATION_PATH_PREFIXES):
        if "/test" in lowered or lowered.startswith(("tests/", "test/")):
            return [f"python -m pytest {path}"]
        return [f"python {path}"]
    return []


def _human_gates(asset: AssetRecord, part_type: str, evidence: list[str]) -> list[str]:
    if part_type not in {"gate", "human_gate", "calibration_gate"}:
        return []
    gates = [item for item in evidence if "human" in item or "review" in item or "approval" in item]
    if gates:
        return sorted(dict.fromkeys(gates))[:5]
    if part_type == "human_gate":
        return ["human_review_required_candidate"]
    return []


def _confidence(evidence_count: int, source_count: int) -> Literal["low", "medium", "high"]:
    if evidence_count >= 5 and source_count >= 2:
        return "high"
    if evidence_count >= 3:
        return "medium"
    return "low"


def _risk(part_type: str, assets: list[AssetRecord]) -> Literal["low", "medium", "high"]:
    if any(asset.sensitivity in {"confidential", "restricted"} for asset in assets):
        return "high"
    if part_type in {"gate", "human_gate", "boundary_map", "calibration_gate", "quarantine_gate"}:
        return "medium"
    return "low"


def build_workflow_part_records(
    assets: list[AssetRecord],
    edges: list[EdgeRecord] | None = None,
    *,
    scan_id: str,
    source_id: str = "all",
    generated_at: str | None = None,
) -> list[WorkflowPartRecord]:
    filtered = _source_filter(assets, source_id)
    family_keys = _family_keys(filtered, edges or [])
    generated = generated_at or utc_now()
    by_id = {asset.asset_id: asset for asset in filtered}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for asset in filtered:
        for match in detect_workflow_part_matches(asset):
            grouped[
                (
                    str(match["part_type"]),
                    str(match["asset_pattern_id"]),
                    family_keys.get(asset.asset_id, asset.asset_id),
                )
            ].append(match)

    records: list[WorkflowPartRecord] = []
    for (part_type, pattern_id, family_key), matches in sorted(grouped.items()):
        definition = _definition_by_part_type(part_type)
        matches = sorted(
            matches,
            key=lambda item: (
                -by_id[str(item["asset_id"])].value_score,
                by_id[str(item["asset_id"])].logical_path,
                str(item["asset_id"]),
            ),
        )
        source_asset_ids = sorted({str(match["asset_id"]) for match in matches})[:8]
        source_assets = [by_id[asset_id] for asset_id in source_asset_ids if asset_id in by_id]
        evidence_by_asset = {
            str(match["asset_id"]): match["evidence"]
            for match in matches
            if str(match["asset_id"]) in source_asset_ids
        }
        all_evidence = sorted({item for values in evidence_by_asset.values() for item in values})
        representative_paths = [asset.logical_path for asset in source_assets[:5]]
        record = WorkflowPartRecord(
            part_id=stable_id("workflow-part", part_type, pattern_id, family_key),
            part_type=part_type,  # type: ignore[arg-type]
            source_asset_ids=source_asset_ids,
            asset_pattern_id=pattern_id,
            role_in_workflow=definition.role_in_workflow,
            authority_boundary=AUTHORITY_BOUNDARY,
            human_gates=_human_gates(source_assets[0], part_type, all_evidence) if source_assets else [],
            validation_commands=[
                command
                for asset in source_assets
                for command in _validation_commands(asset, part_type)
            ],
            applies_when=list(definition.applies_when),
            does_not_apply_when=list(definition.does_not_apply_when),
            danger_if_misapplied=definition.danger_if_misapplied,
            composition_affordances=list(definition.composition_affordances),
            example_workflows=source_asset_ids,
            context_tags=list(definition.context_tags),
            confidence=_confidence(len(all_evidence), len(source_asset_ids)),
            risk=_risk(part_type, source_assets),
            evidence={
                "methodology_version": METHODOLOGY_VERSION,
                "candidate_only": True,
                "source_mutation_forbidden": True,
                "public_safe_metadata_only": True,
                "same_family_first": True,
                "family_key": family_key,
                "path_classes": {
                    asset.asset_id: _path_class(asset)
                    for asset in source_assets
                },
                "representative_paths": representative_paths,
                "evidence_by_asset": evidence_by_asset,
                "dataflow_inference": "not_inferred_unless_declared_or_human_reviewed",
            },
            generated_at=generated,
            scan_id=scan_id,
        )
        records.append(record)
    return sorted(records, key=lambda record: (record.part_type, record.part_id))


def build_workflow_part_edges(
    records: list[WorkflowPartRecord], *, scan_id: str, created_at: str | None = None
) -> list[EdgeRecord]:
    created = created_at or utc_now()
    edges: list[EdgeRecord] = []
    for record in records:
        for asset_id in record.source_asset_ids:
            edges.append(
                EdgeRecord(
                    edge_id=edge_id("has_member_asset", record.part_id, asset_id),
                    edge_type="has_member_asset",
                    source_asset_id=record.part_id,
                    target_asset_id=asset_id,
                    method=METHODOLOGY_VERSION,
                    confidence={"low": 0.45, "medium": 0.65, "high": 0.8}[record.confidence],
                    evidence={
                        "part_type": record.part_type,
                        "asset_pattern_id": record.asset_pattern_id,
                        "candidate_only": True,
                    },
                    created_at=created,
                    scan_id=scan_id,
                )
            )
    return sorted(edges, key=lambda edge: edge.edge_id)


def workflow_part_markdown(
    records: list[WorkflowPartRecord],
    *,
    source_id: str,
    generated_at: str,
    review_sample: int,
) -> str:
    counts = Counter(record.part_type for record in records)
    pattern_counts = Counter(record.asset_pattern_id for record in records)
    lines = [
        "# Workflow Part Recognition",
        "",
        f"Generated at: `{generated_at}`",
        f"Source filter: `{source_id}`",
        "",
        "Candidate-only workflow sub-units detected from existing catalog metadata. This report does not rescan sources, mutate source repositories, or promote any part into source truth.",
        "",
        "## Methodology",
        "",
        f"- Methodology version: `{METHODOLOGY_VERSION}`",
        "- Public-safe metadata only: paths, asset IDs, types, tags, capabilities, and bounded evidence cues.",
        "- Dataflow, side effects, preconditions, outputs, and failure modes are left empty unless declared or reviewed.",
        "- Same-family/deduped recognition happens before review sampling, so repeated copies do not multiply review burden.",
        "",
        "## Counts By Part Type",
        "",
    ]
    if counts:
        for part_type, count in sorted(counts.items()):
            lines.append(f"- `{part_type}`: **{count}**")
    else:
        lines.append("No workflow-part candidates were detected.")
    lines.extend(["", "## Counts By Asset Pattern", ""])
    for pattern_id, count in sorted(pattern_counts.items()):
        lines.append(f"- `{pattern_id}`: **{count}**")
    lines.extend(["", "## Review Sample", ""])
    for record in records[:review_sample]:
        lines.extend(
            [
                f"### `{record.part_type}` - `{record.part_id}`",
                "",
                f"- Pattern: `{record.asset_pattern_id}`",
                f"- Maturity: `{record.maturity}`",
                f"- Confidence: `{record.confidence}`",
                f"- Risk: `{record.risk}`",
                f"- Source assets: {', '.join(f'`{asset_id}`' for asset_id in record.source_asset_ids)}",
                f"- Role: {record.role_in_workflow}",
                f"- Applies when: {'; '.join(record.applies_when)}",
                f"- Does not apply when: {'; '.join(record.does_not_apply_when)}",
                f"- Danger if misapplied: {record.danger_if_misapplied}",
                f"- Context tags: {', '.join(f'`{tag}`' for tag in record.context_tags)}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def workflow_part_review_sample_markdown(
    records: list[WorkflowPartRecord], *, generated_at: str, review_sample: int
) -> str:
    lines = [
        "# Workflow Part Review Sample",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "Use this sample to decide whether a detected part is useful, safe, too broad, too narrow, or missing declared dataflow. Do not promote records by editing generated outputs.",
        "",
        "| part_id | part_type | pattern | confidence | risk | source_assets | review prompt |",
        "|---|---|---|---|---|---:|---|",
    ]
    for record in records[:review_sample]:
        lines.append(
            "| "
            f"`{record.part_id}` | `{record.part_type}` | `{record.asset_pattern_id}` | "
            f"`{record.confidence}` | `{record.risk}` | {len(record.source_asset_ids)} | "
            "Is this a real reusable workflow part, and what declared inputs/outputs or dangers are missing? |"
        )
    return "\n".join(lines) + "\n"


def write_workflow_part_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    edges: list[EdgeRecord] | None = None,
    *,
    scan_id: str,
    source_id: str = "all",
    review_sample: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    records = build_workflow_part_records(
        assets,
        edges or [],
        scan_id=scan_id,
        source_id=source_id,
        generated_at=generated,
    )
    candidate_edges = build_workflow_part_edges(records, scan_id=scan_id, created_at=generated)
    learning_dir = repo_root / "processed" / "learning"
    reports_dir = repo_root / "processed" / "reports"
    records_path = learning_dir / "workflow_parts.jsonl"
    edges_path = learning_dir / "workflow_part_candidate_edges.jsonl"
    report_path = reports_dir / "workflow_part_recognition.md"
    sample_path = reports_dir / "workflow_part_review_sample.md"

    write_jsonl(records_path, [record.model_dump(mode="json") for record in records])
    write_jsonl(edges_path, [edge.model_dump(mode="json") for edge in candidate_edges])
    atomic_write_text(
        report_path,
        workflow_part_markdown(
            records,
            source_id=source_id,
            generated_at=generated,
            review_sample=review_sample,
        ),
    )
    atomic_write_text(
        sample_path,
        workflow_part_review_sample_markdown(
            records,
            generated_at=generated,
            review_sample=review_sample,
        ),
    )
    return {
        "schema": "workflow_part_recognition_result.v1",
        "source_id": source_id,
        "methodology_version": METHODOLOGY_VERSION,
        "candidate_part_count": len(records),
        "candidate_edge_count": len(candidate_edges),
        "review_sample_size": min(review_sample, len(records)),
        "part_type_counts": dict(sorted(Counter(record.part_type for record in records).items())),
        "asset_pattern_counts": dict(
            sorted(Counter(record.asset_pattern_id for record in records).items())
        ),
        "outputs": {
            "workflow_parts": str(records_path),
            "candidate_edges": str(edges_path),
            "report": str(report_path),
            "review_sample": str(sample_path),
        },
        "candidate_only": True,
    }
