from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml
from jsonschema.validators import validator_for


FAMILY_REGISTRY = Path("registry/ml-agent-family-registry.json")
FAMILY_SCHEMA = Path("schemas/ml-agent-family-registry.schema.json")
TECHNIQUE_REGISTRY = Path("registry/ml-technique-registry.json")
TECHNIQUE_SCHEMA = Path("schemas/ml-technique-registry.schema.json")
FIT_SCHEMA = Path("schemas/ml-fit-routing-assessment.schema.json")
FIT_REQUEST_SCHEMA = Path("schemas/ml-fit-routing-request.schema.json")
SUBAGENT_PACK = Path("assets/agent-skills/ml-workflow-agent-family/subagents.yaml")
ML_FIT_POLICY_REVISION = "ml-fit-routing-policy:0.2.0"

PROBLEM_SHAPES = {
    "deterministic_transform",
    "tabular_prediction",
    "high_cardinality_tabular",
    "semantic_retrieval",
    "deep_representation",
    "unknown",
}
EXECUTION_SCALES = {"local", "large_local", "distributed_required", "unknown"}
LABEL_STATUSES = {"available", "partial", "unavailable", "not_applicable", "unknown"}
CONSEQUENCES = {"low", "medium", "high"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_validated(repo_root: Path, registry: Path, schema: Path) -> dict[str, Any]:
    payload = _load_json(repo_root / registry)
    schema_payload = _load_json(repo_root / schema)
    validator_cls = validator_for(schema_payload)
    validator_cls.check_schema(schema_payload)
    validator_cls(schema_payload).validate(payload)
    return payload


def load_ml_family(repo_root: Path) -> dict[str, Any]:
    return _load_validated(repo_root, FAMILY_REGISTRY, FAMILY_SCHEMA)


def load_ml_techniques(repo_root: Path) -> dict[str, Any]:
    return _load_validated(repo_root, TECHNIQUE_REGISTRY, TECHNIQUE_SCHEMA)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _matches(query: str, row: dict[str, Any]) -> bool:
    wanted = _tokens(query)
    if not wanted:
        return True
    searchable = _tokens(json.dumps(row, sort_keys=True))
    return wanted <= searchable


def ml_catalog(repo_root: Path, query: str = "") -> dict[str, Any]:
    family = load_ml_family(repo_root)
    techniques = load_ml_techniques(repo_root)
    pack = yaml.safe_load((repo_root / SUBAGENT_PACK).read_text(encoding="utf-8"))
    role_rows = [row for row in pack["roles"] if _matches(query, row)]
    technique_rows = [row for row in techniques["techniques"] if _matches(query, row)]
    workflow_rows = [row for row in family["workflow_cards"] if _matches(query, row)]
    return {
        "schema_version": "ml.catalog.v1",
        "query": query,
        "candidate_only": True,
        "counts": {
            "roles": len(role_rows),
            "techniques": len(technique_rows),
            "workflows": len(workflow_rows),
        },
        "roles": role_rows,
        "techniques": technique_rows,
        "workflows": workflow_rows,
        "authority_boundary": family["authority_boundary"],
    }


def ml_family_status(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    family = load_ml_family(repo_root)
    techniques = load_ml_techniques(repo_root)
    pack = yaml.safe_load((repo_root / SUBAGENT_PACK).read_text(encoding="utf-8"))
    observed_now = now or datetime.now(timezone.utc)
    observations: list[dict[str, Any]] = []
    for row in family["runtime_adapter_observations"]:
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        observations.append(
            {
                **row,
                "freshness": "current" if observed_now < expires_at else "stale",
            }
        )
    return {
        "schema_version": "ml.family.status.v1",
        "registry_version": family["registry_version"],
        "status": family["status"],
        "ai_agnostic": family["ai_agnostic"],
        "routing_authority": family["routing_authority"],
        "runtime_adapter_observations": observations,
        "role_count": len(pack["roles"]),
        "technique_count": len(techniques["techniques"]),
        "workflow_count": len(family["workflow_cards"]),
        "research_activation_status": family["research_contract"]["activation_status"],
        "research_cadence": family["research_contract"]["cadence"],
        "candidate_only": True,
        "authority_boundary": family["authority_boundary"],
    }


def _walk_dependencies(
    start: str, edges: list[dict[str, Any]], *, direction: str
) -> list[dict[str, Any]]:
    if direction not in {"upstream", "downstream"}:
        raise ValueError("direction must be upstream or downstream")
    queue: deque[str] = deque([start])
    visited_nodes = {start}
    found: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    while queue:
        current = queue.popleft()
        for edge in edges:
            matches = edge["source"] == current if direction == "upstream" else edge["target"] == current
            if not matches:
                continue
            key = (edge["source"], edge["edge_type"], edge["target"])
            if key not in seen_edges:
                found.append(edge)
                seen_edges.add(key)
            next_node = edge["target"] if direction == "upstream" else edge["source"]
            if next_node not in visited_nodes:
                visited_nodes.add(next_node)
                queue.append(next_node)
    return sorted(found, key=lambda row: (row["source"], row["edge_type"], row["target"]))


def ml_dependency_graph(repo_root: Path, node: str | None = None) -> dict[str, Any]:
    family = load_ml_family(repo_root)
    graph = family["graph_contract"]
    edges = graph["dependency_edges"]
    nodes = sorted({value for edge in edges for value in (edge["source"], edge["target"])})
    if node is not None and node not in nodes:
        raise ValueError(f"Unknown ML family graph node: {node}")
    upstream = _walk_dependencies(node, edges, direction="upstream") if node else edges
    downstream = _walk_dependencies(node, edges, direction="downstream") if node else edges
    return {
        "schema_version": "ml.family.dependency_graph.v1",
        "focus_node": node,
        "candidate_only": True,
        "node_types": graph["node_types"],
        "nodes": nodes,
        "upstream_edges": upstream,
        "downstream_edges": downstream,
        "forbidden_claims": graph["forbidden_claims"],
        "authority_boundary": family["authority_boundary"],
    }


def ml_research_plan(repo_root: Path) -> dict[str, Any]:
    family = load_ml_family(repo_root)
    workflow = next(
        row
        for row in family["workflow_cards"]
        if row["workflow_id"] == "workflow:ml-frontier-research-refresh"
    )
    return {
        "schema_version": "ml.research.plan.v1",
        "workflow": workflow,
        "contract": family["research_contract"],
        "scheduled": False,
        "activation_required": True,
        "candidate_only": True,
        "authority_boundary": family["authority_boundary"],
    }


def _require_choice(name: str, value: str, choices: set[str]) -> None:
    if value not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(choices))}")


def _stage(
    order: int,
    stage_id: str,
    *,
    required: bool,
    entry: list[str],
    stop: list[str],
    techniques: list[str],
) -> dict[str, Any]:
    return {
        "order": order,
        "stage_id": f"ml-stage:{stage_id}",
        "required": required,
        "entry_criteria": entry,
        "stop_criteria": stop,
        "candidate_technique_ids": techniques,
    }


def ml_fit_route(
    repo_root: Path,
    *,
    objective: str,
    problem_shape: str = "unknown",
    execution_scale: str = "unknown",
    label_status: str = "unknown",
    consequence: str = "medium",
    named_tool_preference: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, non-authorizing ML-fit first-hop receipt.

    The public route always completes ``workflow:ml-opportunity-review`` before
    it can name the downstream technique router. A named tool is retained only
    as a preference observation and never changes the route.
    """
    objective = objective.strip()
    if not objective:
        raise ValueError("objective must not be empty")
    _require_choice("problem_shape", problem_shape, PROBLEM_SHAPES)
    _require_choice("execution_scale", execution_scale, EXECUTION_SCALES)
    _require_choice("label_status", label_status, LABEL_STATUSES)
    _require_choice("consequence", consequence, CONSEQUENCES)
    named_tool = named_tool_preference.strip() if named_tool_preference else None
    family = load_ml_family(repo_root)
    known_techniques = {
        row["technique_id"] for row in load_ml_techniques(repo_root)["techniques"]
    }

    baseline = "ml-technique:no-ml-baseline"
    techniques: list[str] = [baseline]
    stages: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    unknowns: list[str] = []
    required_gates = ["decision owner", "no-ML baseline", "source and data authority"]

    if problem_shape == "deterministic_transform":
        disposition = "no_ml"
        stages.append(
            _stage(
                1,
                "deterministic-baseline",
                required=True,
                entry=["The required output can be specified as deterministic rules or transforms."],
                stop=["Stop if validation shows the deterministic path satisfies the locked outcome."],
                techniques=[baseline],
            )
        )
        rejected.append(
            {
                "alternative": "trained model",
                "reason": "A deterministic implementation is inspectable and sufficient on the supplied problem shape.",
                "reconsider_when": "Measured residual cases cannot be specified deterministically and have an owned target and evaluation set.",
            }
        )
    elif problem_shape == "semantic_retrieval":
        disposition = "route_to_knowledge_engineering"
        stages.append(
            _stage(
                1,
                "knowledge-route-handoff",
                required=True,
                entry=["The outcome is retrieval or evidence assembly rather than a learned predictive decision."],
                stop=["Stop ML routing and run the Knowledge Engineering route before selecting retrieval components."],
                techniques=[baseline],
            )
        )
        rejected.append(
            {
                "alternative": "ML tool specialist",
                "reason": "DAD owns retrieval, RAG, long-context, vector, and graph routing in the Knowledge Engineering family.",
                "reconsider_when": "A separately owned learned prediction or ranking target remains after the knowledge route is locked.",
            }
        )
    elif problem_shape == "unknown":
        disposition = "insufficient_evidence"
        unknowns.append("problem shape")
        stages.append(
            _stage(
                1,
                "clarify-decision-shape",
                required=True,
                entry=["The objective is present but the decision shape is unknown."],
                stop=["Stop until the supported downstream action and measurable output are explicit."],
                techniques=[baseline],
            )
        )
    elif label_status in {"unavailable", "unknown", "not_applicable"}:
        disposition = "data_work_first"
        if label_status in {"unknown", "not_applicable"}:
            unknowns.append("label availability and provenance")
        stages.append(
            _stage(
                1,
                "data-and-label-readiness",
                required=True,
                entry=["A predictive or representation-learning objective was named without ready labels or label evidence."],
                stop=["Stop before technique selection until label provenance, prediction time, and split boundaries are reviewable."],
                techniques=[baseline],
            )
        )
    else:
        disposition = "bounded_ml_candidate"
        required_gates.extend(["locked evaluation contract", "independent checker"])
        stages.append(
            _stage(
                1,
                "credible-baseline",
                required=True,
                entry=["The target, labels, split boundary, and supported action can be investigated."],
                stop=["Stop if the no-ML or simplest statistical baseline meets the locked acceptance criteria."],
                techniques=[baseline, "ml-technique:linear-generalized-models"],
            )
        )
        techniques.append("ml-technique:linear-generalized-models")
        if problem_shape in {"tabular_prediction", "high_cardinality_tabular"}:
            techniques.append("ml-technique:tree-ensembles")
            stages.append(
                _stage(
                    2,
                    "tabular-ensemble-candidate",
                    required=False,
                    entry=["The locked baseline is insufficient on held-out evidence and nonlinear tabular interactions are plausible."],
                    stop=["Stop when comparable held-out gain does not justify added calibration, latency, explanation, and maintenance cost."],
                    techniques=["ml-technique:tree-ensembles"],
                )
            )
        elif problem_shape == "deep_representation":
            techniques.append("ml-technique:deep-representation-learning")
            stages.append(
                _stage(
                    2,
                    "single-deep-backend-candidate",
                    required=False,
                    entry=["Simpler baselines fail and the modality or representation requirement justifies deep learning."],
                    stop=["Stop if one selected backend cannot beat the baseline under the locked quality, cost, and latency budget; do not add a second backend by default."],
                    techniques=["ml-technique:deep-representation-learning"],
                )
            )

    if execution_scale != "distributed_required":
        rejected.append(
            {
                "alternative": "distributed compute stack",
                "reason": "No explicit evidence says a measured local path is insufficient.",
                "reconsider_when": "A reproducible benchmark or hard platform constraint establishes distributed execution as required.",
            }
        )
    elif disposition == "bounded_ml_candidate":
        stages.append(
            _stage(
                len(stages) + 1,
                "distributed-execution-candidate",
                required=False,
                entry=["Measured local execution is insufficient or an approved platform constraint requires distribution."],
                stop=["Stop if distributed overhead, reliability, cost, or reproducibility fails the locked budget."],
                techniques=[],
            )
        )
    if named_tool:
        rejected.append(
            {
                "alternative": f"automatic selection of named tool: {named_tool}",
                "reason": "A tool preference is not evidence of ML fit, technique fit, runtime qualification, or authority.",
                "reconsider_when": "The mandatory fit gate passes and a versioned benchmark against the contract supports that tool.",
            }
        )

    missing = sorted(set(techniques) - known_techniques)
    if missing:
        raise ValueError(f"Unknown technique IDs in ML fit route: {missing}")
    canonical_input = {
        "objective": objective,
        "problem_shape": problem_shape,
        "execution_scale": execution_scale,
        "label_status": label_status,
        "consequence": consequence,
        "named_tool_preference": named_tool,
    }
    request_payload = {"schema_version": "ml.fit.routing_request.v1", **canonical_input}
    request_schema = _load_json(repo_root / FIT_REQUEST_SCHEMA)
    request_validator_cls = validator_for(request_schema)
    request_validator_cls.check_schema(request_schema)
    request_validator_cls(request_schema).validate(request_payload)
    specialist_route_material = (
        {
            "role_id": "ml-technique-router",
            "route_status": "candidate_not_dispatched",
        }
        if disposition == "bounded_ml_candidate"
        else None
    )
    receipt_material = {
        "schema_version": "ml.fit.routing_assessment.v1",
        "policy_revision_id": ML_FIT_POLICY_REVISION,
        "first_hop_workflow_id": "workflow:ml-opportunity-review",
        "first_hop_completed": True,
        **canonical_input,
        "disposition": disposition,
        "candidate_only": True,
        "dispatch_authorized": False,
        "candidate_technique_ids": techniques,
        "ordered_toolchain": stages,
        "rejected_alternatives": rejected,
        "required_gates": sorted(set(required_gates)),
        "unknowns": sorted(set(unknowns)),
        "specialist_route": specialist_route_material,
        "human_decision_required": disposition in {"insufficient_evidence", "data_work_first"}
        or consequence == "high",
        "authority_boundary": family["authority_boundary"],
    }
    digest_hex = hashlib.sha256(
        json.dumps(receipt_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    digest = f"sha256:{digest_hex}"
    specialist_route = (
        {**specialist_route_material, "assessment_digest": digest}
        if specialist_route_material is not None
        else None
    )
    result = {
        **receipt_material,
        "assessment_id": f"ml-fit-assessment:{digest_hex[:16]}",
        "assessment_digest": digest,
        "specialist_route": specialist_route,
    }
    schema_payload = _load_json(repo_root / FIT_SCHEMA)
    validator_cls = validator_for(schema_payload)
    validator_cls.check_schema(schema_payload)
    validator_cls(schema_payload).validate(result)
    return result


def _fit_receipt_material(receipt: dict[str, Any]) -> dict[str, Any]:
    material = {
        key: value
        for key, value in receipt.items()
        if key not in {"assessment_id", "assessment_digest"}
    }
    route = material.get("specialist_route")
    if isinstance(route, dict):
        material["specialist_route"] = {
            key: value for key, value in route.items() if key != "assessment_digest"
        }
    return material


def validate_ml_fit_receipt(repo_root: Path, receipt: Any) -> dict[str, Any]:
    """Validate schema, policy replay, full-payload digest, and nested binding."""
    if not isinstance(receipt, dict):
        raise ValueError("ML fit receipt must be a JSON object")
    if receipt.get("policy_revision_id") != ML_FIT_POLICY_REVISION:
        raise ValueError("ML fit receipt policy revision is missing or stale")
    schema_payload = _load_json(repo_root / FIT_SCHEMA)
    validator_cls = validator_for(schema_payload)
    validator_cls.check_schema(schema_payload)
    validator_cls(schema_payload).validate(receipt)
    expected = ml_fit_route(
        repo_root,
        objective=receipt["objective"],
        problem_shape=receipt["problem_shape"],
        execution_scale=receipt["execution_scale"],
        label_status=receipt["label_status"],
        consequence=receipt["consequence"],
        named_tool_preference=receipt["named_tool_preference"],
    )
    if _fit_receipt_material(receipt) != _fit_receipt_material(expected):
        raise ValueError("ML fit receipt does not match deterministic policy replay")
    digest_hex = hashlib.sha256(
        json.dumps(
            _fit_receipt_material(receipt),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    expected_digest = f"sha256:{digest_hex}"
    if receipt.get("assessment_digest") != expected_digest:
        raise ValueError("ML fit receipt digest does not match the complete assessment payload")
    if receipt.get("assessment_id") != f"ml-fit-assessment:{digest_hex[:16]}":
        raise ValueError("ML fit receipt identity does not match its digest")
    route = receipt.get("specialist_route")
    if isinstance(route, dict) and route.get("assessment_digest") != expected_digest:
        raise ValueError("ML specialist route is not bound to the assessment digest")
    return receipt


def ml_specialist_route(repo_root: Path, receipt: Any) -> dict[str, Any]:
    """Return the only DAD-governed ML specialist route after receipt validation."""
    validated = validate_ml_fit_receipt(repo_root, receipt)
    route = validated.get("specialist_route")
    if validated.get("disposition") != "bounded_ml_candidate" or not isinstance(route, dict):
        raise ValueError("ML fit receipt does not permit a specialist route candidate")
    return {
        "schema_version": "ml.specialist.route.v1",
        "policy_revision_id": ML_FIT_POLICY_REVISION,
        "first_hop_workflow_id": validated["first_hop_workflow_id"],
        "assessment_digest": validated["assessment_digest"],
        "role_id": route["role_id"],
        "route_status": "candidate_not_dispatched",
        "candidate_only": True,
        "dispatch_authorized": False,
        "authority_boundary": validated["authority_boundary"],
    }
