from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import ValidationError
from jsonschema.validators import validator_for
import pytest
import yaml

from digital_asset_directory.ml_agent_family import (
    ml_catalog,
    ml_dependency_graph,
    ml_family_status,
    ml_fit_route,
    ml_research_plan,
    ml_specialist_route,
    validate_ml_fit_receipt,
)


ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validate(schema_rel: str, payload: dict) -> None:
    schema = load_json(schema_rel)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER).validate(payload)


def test_ml_schemas_are_registered_and_registries_conform() -> None:
    schema_registry = load_json("registry/schema-registry.json")["schemas"]
    assert schema_registry["ml_agent_family_registry"] == "schemas/ml-agent-family-registry.schema.json"
    assert schema_registry["ml_technique_registry"] == "schemas/ml-technique-registry.schema.json"
    assert schema_registry["ml_workflow_decision"] == "schemas/ml-workflow-decision.schema.json"
    assert schema_registry["ml_fit_routing_assessment"] == "schemas/ml-fit-routing-assessment.schema.json"
    assert schema_registry["ml_fit_routing_request"] == "schemas/ml-fit-routing-request.schema.json"
    validate(
        "schemas/ml-agent-family-registry.schema.json",
        load_json("registry/ml-agent-family-registry.json"),
    )
    validate(
        "schemas/ml-technique-registry.schema.json",
        load_json("registry/ml-technique-registry.json"),
    )


def test_technique_registry_is_context_bounded_and_incomplete_by_design() -> None:
    registry = load_json("registry/ml-technique-registry.json")
    techniques = registry["techniques"]
    ids = [row["technique_id"] for row in techniques]
    revisions = [row["revision_id"] for row in techniques]
    assert len(techniques) == 20
    assert len(ids) == len(set(ids))
    assert len(revisions) == len(set(revisions))
    assert "intentionally incomplete" in registry["coverage_statement"]
    assert "ml-technique:no-ml-baseline" in ids
    for row in techniques:
        assert row["applies_when"]
        assert row["does_not_apply_when"]
        assert row["danger_if_misapplied"]
        assert row["baseline_refs"]
        assert row["split_and_leakage_controls"]
        assert row["evaluation_requirements"]
        assert row["operational_requirements"]
        assert row["source_refs"]


def test_specialist_suite_and_frontier_techniques_are_discoverable() -> None:
    registry = load_json("registry/ml-technique-registry.json")
    ids = {row["technique_id"] for row in registry["techniques"]}
    assert {
        "ml-technique:wide-deep-tabular-learning",
        "ml-technique:representation-tabular-hybrids",
        "ml-technique:calibrated-conformal-uncertainty",
        "ml-technique:active-learning",
        "ml-technique:automl-hyperparameter-optimization",
    } <= ids
    boosting = next(
        row for row in registry["techniques"]
        if row["technique_id"] == "ml-technique:tree-ensembles"
    )
    assert "XGBoost" in boosting["implementation_options"]


def test_runtime_observations_are_expiring_hints_not_identity() -> None:
    current = ml_family_status(
        ROOT, now=datetime(2026, 7, 20, tzinfo=timezone.utc)
    )
    stale = ml_family_status(
        ROOT, now=datetime(2026, 7, 29, tzinfo=timezone.utc)
    )
    assert current["ai_agnostic"] is True
    assert current["runtime_adapter_observations"][0]["freshness"] == "current"
    assert stale["runtime_adapter_observations"][0]["freshness"] == "stale"
    observation = current["runtime_adapter_observations"][0]
    assert observation["authoritative"] is False
    assert {row["capability_alias"] for row in observation["mappings"]} == {
        "luna",
        "terra",
        "sol",
    }
    assert "capability aliases" in current["routing_authority"]["legacy_field_semantics"]
    assert "preferred_model_family" in current["routing_authority"]["legacy_field_semantics"]


def test_declared_role_pack_is_ai_agnostic_and_uses_closed_capabilities() -> None:
    pack = yaml.safe_load(
        (ROOT / "assets/agent-skills/ml-workflow-agent-family/subagents.yaml").read_text(
            encoding="utf-8"
        )
    )
    validate("schemas/subagent-pack.schema.json", pack)
    capability_ids = {
        row["id"]
        for row in load_json("registry/subagent-capability-registry.json")["capabilities"]
    }
    declared = {item for role in pack["roles"] for item in role["capability_ids"]}
    assert declared <= capability_ids
    assert pack["ai_agnostic"] is True
    assert pack["routing_policy"]["one_writer"] is True
    assert pack["routing_policy"]["independent_checker_required"] is True
    assert pack["routing_policy"]["model_ids_are_attempt_metadata_only"] is True
    role_ids = {row["role_id"] for row in pack["roles"]}
    assert {
        "ml-tabular-boosting-specialist",
        "ml-wide-deep-representation-specialist",
        "ml-graph-ranking-specialist",
        "ml-temporal-uncertainty-specialist",
        "ml-causal-decision-specialist",
        "ml-active-online-learning-specialist",
        "ml-privacy-federated-specialist",
        "ml-operations-evaluation-specialist",
    } <= role_ids


def test_specialist_workflows_are_candidate_only_and_human_gated() -> None:
    family = load_json("registry/ml-agent-family-registry.json")
    workflows = {row["workflow_id"]: row for row in family["workflow_cards"]}
    assert {
        "workflow:ml-specialist-champion-challenger",
        "workflow:ml-hybrid-composition-review",
        "workflow:ml-operational-monitoring-and-retraining",
    } <= workflows.keys()
    operations = workflows["workflow:ml-operational-monitoring-and-retraining"]
    assert operations["activation_status"] == "manual"
    assert "gate:human-deployment" in operations["gate_refs"]
    routines = yaml.safe_load(
        (ROOT / "assets/agent-skills/ml-workflow-agent-family/routines.yaml").read_text(
            encoding="utf-8"
        )
    )
    operational = next(
        row for row in routines["routines"]
        if row["routine_id"] == "ml-operational-monitoring-and-retraining"
    )
    assert operational["auto_deploy"] is False
    assert operational["auto_retrain"] is False
    assert operational["auto_schedule"] is False


def test_experiment_predict_and_hybrid_contracts_are_explicit() -> None:
    contract = (
        ROOT / "assets/agent-skills/ml-workflow-agent-family/references/ML_WORKFLOW_CONTRACT.md"
    ).read_text(encoding="utf-8")
    assert "MLExperimentContract" in contract
    assert "PredictContract" in contract
    assert "component ablations" in contract
    playbook = (ROOT / "docs/ML_SPECIALIST_MESH_AND_HYBRIDS.md").read_text(
        encoding="utf-8"
    )
    assert "Embeddings + XGBoost" in playbook
    assert "Retrieval/graph + ranker" in playbook
    assert "Forecast + conformal interval" in playbook


def test_catalog_search_is_read_only_relevance_not_dispatch() -> None:
    result = ml_catalog(ROOT, "time series")
    technique_ids = {row["technique_id"] for row in result["techniques"]}
    assert technique_ids == {"ml-technique:time-series-forecasting"}
    assert result["candidate_only"] is True


def test_dependency_graph_returns_transitive_upstream_and_downstream() -> None:
    root = "skill:ml-workflow-agent-family"
    result = ml_dependency_graph(ROOT, root)
    upstream_targets = {edge["target"] for edge in result["upstream_edges"]}
    assert "skill:personal-hierarchical-agent-mesh" in upstream_targets
    assert "skill:subagent-continuous-improvement" in upstream_targets
    assert "registry:ml-technique-registry" in upstream_targets
    registry_view = ml_dependency_graph(ROOT, "registry:ml-technique-registry")
    assert any(edge["source"] == root for edge in registry_view["downstream_edges"])
    role_view = ml_dependency_graph(ROOT, "role:ml-workflow-foreman")
    assert any(
        edge["target"] == "capability:ml_workflow_decomposition"
        for edge in role_view["upstream_edges"]
    )
    gate_view = ml_dependency_graph(ROOT, "gate:human-deployment")
    assert any(
        edge["source"] == "workflow:ml-deployment-readiness"
        and edge["edge_type"] == "requires_human_gate"
        for edge in gate_view["downstream_edges"]
    )
    assert result["candidate_only"] is True
    assert result["forbidden_claims"]


def test_graph_edge_types_are_closed_and_midflight_is_explicit() -> None:
    family = load_json("registry/ml-agent-family-registry.json")
    graph = family["graph_contract"]
    assert {edge["edge_type"] for edge in graph["dependency_edges"]} <= set(
        graph["allowed_edge_types"]
    )
    payload = json.loads(json.dumps(family))
    payload["graph_contract"]["dependency_edges"][0]["edge_type"] = "invented_authority"
    with pytest.raises(ValidationError):
        validate("schemas/ml-agent-family-registry.schema.json", payload)

    experiment = next(
        row
        for row in family["workflow_cards"]
        if row["workflow_id"] == "workflow:ml-experiment-and-build"
    )
    assert "gate:midflight-contract-relock" in experiment["gate_refs"]
    assert any("midflight" in step.lower() for step in experiment["steps"])
    contract = (
        ROOT / "assets/agent-skills/ml-workflow-agent-family/references/ML_WORKFLOW_CONTRACT.md"
    ).read_text(encoding="utf-8")
    assert "## 6. Recheck At Midflight" in contract
    for trigger in ["data", "split", "metric", "technique", "runtime", "authority", "scope"]:
        assert trigger in contract.lower()


def test_unknown_dependency_node_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unknown ML family graph node"):
        ml_dependency_graph(ROOT, "model:invented")


def test_research_plan_is_p14d_and_never_scheduled_by_catalog() -> None:
    result = ml_research_plan(ROOT)
    assert result["contract"]["cadence"] == "P14D"
    assert result["contract"]["activation_status"] == "human_activation_required"
    assert result["scheduled"] is False
    assert result["activation_required"] is True
    assert result["workflow"]["workflow_id"] == "workflow:ml-frontier-research-refresh"


def test_fit_route_is_mandatory_first_hop_and_schema_valid() -> None:
    result = ml_fit_route(
        ROOT,
        objective="Prioritize bounded synthetic rows for review.",
        problem_shape="tabular_prediction",
        execution_scale="local",
        label_status="available",
        consequence="medium",
        named_tool_preference="XGBoost",
    )
    validate("schemas/ml-fit-routing-assessment.schema.json", result)
    assert result["first_hop_workflow_id"] == "workflow:ml-opportunity-review"
    assert result["first_hop_completed"] is True
    assert result["dispatch_authorized"] is False
    assert result["specialist_route"]["assessment_digest"] == result["assessment_digest"]
    assert result["specialist_route"]["role_id"] == "ml-tabular-boosting-specialist"
    assert any("XGBoost" in row["alternative"] for row in result["rejected_alternatives"])
    assert validate_ml_fit_receipt(ROOT, result) == result
    specialist = ml_specialist_route(ROOT, result)
    assert specialist["assessment_digest"] == result["assessment_digest"]
    assert specialist["dispatch_authorized"] is False


@pytest.mark.parametrize(
    ("problem_shape", "expected_role", "required_techniques"),
    [
        ("tabular_prediction", "ml-tabular-boosting-specialist", {"ml-technique:tree-ensembles"}),
        ("high_cardinality_tabular", "ml-wide-deep-representation-specialist", {"ml-technique:tree-ensembles", "ml-technique:wide-deep-tabular-learning"}),
        ("deep_representation", "ml-wide-deep-representation-specialist", {"ml-technique:deep-representation-learning", "ml-technique:representation-tabular-hybrids"}),
        ("graph_ranking", "ml-graph-ranking-specialist", {"ml-technique:ranking-recommendation", "ml-technique:graph-geometric-learning"}),
        ("temporal_forecasting", "ml-temporal-uncertainty-specialist", {"ml-technique:time-series-forecasting", "ml-technique:calibrated-conformal-uncertainty"}),
        ("causal_decision", "ml-causal-decision-specialist", {"ml-technique:causal-uplift-learning"}),
        ("active_online_learning", "ml-active-online-learning-specialist", {"ml-technique:active-learning", "ml-technique:online-learning-bandits"}),
        ("privacy_federated_learning", "ml-privacy-federated-specialist", {"ml-technique:privacy-preserving-federated-learning"}),
        ("operational_evaluation", "ml-operations-evaluation-specialist", {"ml-technique:calibrated-conformal-uncertainty"}),
    ],
)
def test_fit_route_deterministically_selects_specialist_mesh(
    problem_shape: str, expected_role: str, required_techniques: set[str]
) -> None:
    result = ml_fit_route(
        ROOT,
        objective=f"Route a bounded {problem_shape} fixture.",
        problem_shape=problem_shape,
        execution_scale="local",
        label_status="available",
    )
    assert result["specialist_route"]["role_id"] == expected_role
    assert required_techniques <= set(result["candidate_technique_ids"])
    assert validate_ml_fit_receipt(ROOT, result) == result

@pytest.mark.parametrize("field", ["disposition", "ordered_toolchain", "required_gates"])
def test_fit_receipt_rejects_material_tampering(field: str) -> None:
    receipt = ml_fit_route(
        ROOT,
        objective="Predict a bounded synthetic outcome.",
        problem_shape="tabular_prediction",
        execution_scale="local",
        label_status="available",
    )
    tampered = deepcopy(receipt)
    if field == "disposition":
        tampered[field] = "no_ml"
    elif field == "ordered_toolchain":
        tampered[field][0]["stop_criteria"] = ["Accept without evidence."]
    else:
        tampered[field].append("unreviewed automatic approval")
    with pytest.raises(ValueError, match="deterministic policy replay"):
        validate_ml_fit_receipt(ROOT, tampered)


def test_fit_receipt_rejects_nested_digest_and_stale_policy() -> None:
    receipt = ml_fit_route(
        ROOT,
        objective="Predict a bounded synthetic outcome.",
        problem_shape="tabular_prediction",
        execution_scale="local",
        label_status="available",
    )
    nested = deepcopy(receipt)
    nested["specialist_route"]["assessment_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="not bound"):
        validate_ml_fit_receipt(ROOT, nested)
    stale = deepcopy(receipt)
    stale["policy_revision_id"] = "ml-fit-routing-policy:0.1.0"
    with pytest.raises(ValueError, match="missing or stale"):
        validate_ml_fit_receipt(ROOT, stale)
    with pytest.raises(ValueError, match="missing or stale"):
        ml_specialist_route(ROOT, {})
    with pytest.raises(ValueError, match="must be a JSON object"):
        ml_specialist_route(ROOT, [])


def test_fit_receipt_rejects_forged_but_self_consistent_policy_output() -> None:
    receipt = ml_fit_route(
        ROOT,
        objective="Predict a bounded synthetic outcome.",
        problem_shape="tabular_prediction",
        execution_scale="local",
        label_status="available",
    )
    forged = deepcopy(receipt)
    forged["ordered_toolchain"][0]["stop_criteria"] = ["Accept the named tool without comparison."]
    material = {
        key: value
        for key, value in forged.items()
        if key not in {"assessment_id", "assessment_digest"}
    }
    material["specialist_route"] = {
        key: value
        for key, value in material["specialist_route"].items()
        if key != "assessment_digest"
    }
    digest_hex = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    forged["assessment_digest"] = f"sha256:{digest_hex}"
    forged["assessment_id"] = f"ml-fit-assessment:{digest_hex[:16]}"
    forged["specialist_route"]["assessment_digest"] = forged["assessment_digest"]
    with pytest.raises(ValueError, match="deterministic policy replay"):
        validate_ml_fit_receipt(ROOT, forged)


def test_fit_receipt_rejects_self_consistent_specialist_substitution() -> None:
    receipt = ml_fit_route(
        ROOT,
        objective="Predict a bounded synthetic outcome.",
        problem_shape="tabular_prediction",
        execution_scale="local",
        label_status="available",
    )
    forged = deepcopy(receipt)
    forged["specialist_route"]["role_id"] = "ml-graph-ranking-specialist"
    material = {
        key: value
        for key, value in forged.items()
        if key not in {"assessment_id", "assessment_digest"}
    }
    material["specialist_route"] = {
        key: value
        for key, value in material["specialist_route"].items()
        if key != "assessment_digest"
    }
    digest_hex = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    forged["assessment_digest"] = f"sha256:{digest_hex}"
    forged["assessment_id"] = f"ml-fit-assessment:{digest_hex[:16]}"
    forged["specialist_route"]["assessment_digest"] = forged["assessment_digest"]
    with pytest.raises(ValueError, match="deterministic policy replay"):
        validate_ml_fit_receipt(ROOT, forged)

def test_fit_workflow_interfaces_resolve_and_request_maps_to_cli_inputs() -> None:
    family = load_json("registry/ml-agent-family-registry.json")
    workflow = next(
        row for row in family["workflow_cards"] if row["workflow_id"] == "workflow:ml-opportunity-review"
    )
    assert workflow["inputs_ref"] == "schemas/ml-fit-routing-request.schema.json"
    assert workflow["outputs_ref"] == "schemas/ml-fit-routing-assessment.schema.json"
    assert (ROOT / workflow["inputs_ref"]).is_file()
    assert (ROOT / workflow["outputs_ref"]).is_file()
    result = ml_fit_route(ROOT, objective="Clarify a fixture.")
    request = {
        "schema_version": "ml.fit.routing_request.v1",
        **{
            key: result[key]
            for key in (
                "objective",
                "problem_shape",
                "execution_scale",
                "label_status",
                "consequence",
                "named_tool_preference",
            )
        },
    }
    validate("schemas/ml-fit-routing-request.schema.json", request)


def test_fit_route_no_ml_stops_before_specialist() -> None:
    result = ml_fit_route(
        ROOT,
        objective="Render a deterministic report.",
        problem_shape="deterministic_transform",
        execution_scale="local",
        label_status="not_applicable",
        consequence="low",
    )
    assert result["disposition"] == "no_ml"
    assert result["specialist_route"] is None
    assert result["candidate_technique_ids"] == ["ml-technique:no-ml-baseline"]
    assert result["ordered_toolchain"][0]["stage_id"] == "ml-stage:deterministic-baseline"


def test_fit_route_orders_baseline_before_optional_tabular_ensemble() -> None:
    result = ml_fit_route(
        ROOT,
        objective="Predict a reviewed synthetic outcome.",
        problem_shape="high_cardinality_tabular",
        execution_scale="large_local",
        label_status="available",
        consequence="medium",
    )
    stages = result["ordered_toolchain"]
    assert [row["order"] for row in stages] == [1, 2]
    assert stages[0]["stage_id"] == "ml-stage:credible-baseline"
    assert stages[0]["required"] is True
    assert stages[1]["stage_id"] == "ml-stage:tabular-ensemble-candidate"
    assert stages[1]["required"] is False
    assert stages[1]["entry_criteria"] and stages[1]["stop_criteria"]


def test_fit_route_stops_predictive_route_without_applicable_labels() -> None:
    result = ml_fit_route(
        ROOT,
        objective="Predict a reviewed synthetic outcome.",
        problem_shape="tabular_prediction",
        execution_scale="local",
        label_status="not_applicable",
        consequence="medium",
    )
    assert result["disposition"] == "data_work_first"
    assert result["specialist_route"] is None
    assert result["candidate_technique_ids"] == ["ml-technique:no-ml-baseline"]


def test_fit_route_sends_semantic_retrieval_to_existing_knowledge_family() -> None:
    result = ml_fit_route(
        ROOT,
        objective="Retrieve cited passages from an approved corpus.",
        problem_shape="semantic_retrieval",
        execution_scale="local",
        label_status="not_applicable",
        consequence="medium",
    )
    assert result["disposition"] == "route_to_knowledge_engineering"
    assert result["specialist_route"] is None
    assert result["ordered_toolchain"][0]["stage_id"] == "ml-stage:knowledge-route-handoff"


def test_fit_route_rejects_unjustified_distribution_and_limits_deep_backend() -> None:
    result = ml_fit_route(
        ROOT,
        objective="Learn a synthetic image representation.",
        problem_shape="deep_representation",
        execution_scale="local",
        label_status="partial",
        consequence="high",
    )
    assert result["human_decision_required"] is True
    assert any(row["alternative"] == "distributed compute stack" for row in result["rejected_alternatives"])
    deep = next(row for row in result["ordered_toolchain"] if "deep-backend" in row["stage_id"])
    assert "do not add a second backend by default" in deep["stop_criteria"][0]


def test_fit_route_fails_closed_on_unknown_enum_value() -> None:
    with pytest.raises(ValueError, match="problem_shape must be one of"):
        ml_fit_route(ROOT, objective="Fixture", problem_shape="use-whatever-tool-was-named")


def test_family_contract_declares_non_bypass_and_receipt_binding() -> None:
    family = load_json("registry/ml-agent-family-registry.json")
    contract = family["fit_routing_contract"]
    assert contract["mandatory_before_specialist"] is True
    assert "named tool" in contract["non_bypass_rule"].lower()
    graph = family["graph_contract"]["dependency_edges"]
    assert any(
        edge["source"] == "workflow:ml-opportunity-review"
        and edge["target"] == "role:ml-technique-router"
        for edge in graph
    )


    routed_specialists = {
        edge["target"]
        for edge in graph
        if edge["source"] == "role:ml-technique-router" and edge["edge_type"] == "routes_to"
    }
    assert routed_specialists == {
        "role:ml-tabular-boosting-specialist",
        "role:ml-wide-deep-representation-specialist",
        "role:ml-graph-ranking-specialist",
        "role:ml-temporal-uncertainty-specialist",
        "role:ml-causal-decision-specialist",
        "role:ml-active-online-learning-specialist",
        "role:ml-privacy-federated-specialist",
        "role:ml-operations-evaluation-specialist",
    }

def test_workflow_decision_requires_no_ml_and_human_gates() -> None:
    payload = {
        "schema_version": "0.2.0",
        "decision_id": "ml-workflow-decision:synthetic-tabular",
        "created_at": "2026-07-14T00:00:00Z",
        "goal": "Predict a synthetic outcome for a bounded experiment.",
        "decision_owner": "named synthetic owner",
        "authority_and_sensitivity": "synthetic public fixture only",
        "supported_action": "Send a synthetic candidate to human review.",
        "action_reversibility": "reversible",
        "abstention_behavior": "Abstain to human review when evidence is insufficient.",
        "decision_costs": {
            "false_positive": "Unnecessary synthetic review.",
            "false_negative": "Missed synthetic candidate.",
            "delay": "One fixture cycle.",
            "human_review": "One bounded fixture review.",
        },
        "prediction_time_availability": "Only synthetic features observed before the prediction timestamp.",
        "maintenance_owner": "named synthetic owner",
        "no_ml_baseline": "Compare with a deterministic rule and regularized linear model.",
        "candidate_technique_ids": ["ml-technique:tree-ensembles"],
        "recommendation": "bounded_experiment",
        "applies_when": ["Synthetic data and a locked split are available."],
        "does_not_apply_when": ["The target changes after evaluation begins."],
        "danger_if_misapplied": "A random row split could leak duplicate entities.",
        "data_and_split_contract": "Group split synthetic entities before preprocessing.",
        "evaluation_contract": "Compare held-out calibration and task metric to the baseline.",
        "human_gates": ["Named owner approves any non-synthetic continuation."],
        "rollback_and_kill_criteria": ["Stop if leakage guard fails."],
        "unknowns": [],
        "evidence_refs": ["source://synthetic-fixture"],
        "review_status": "candidate",
        "authority_boundary": "Fixture evidence authorizes no real data use or deployment.",
    }
    validate("schemas/ml-workflow-decision.schema.json", payload)
    payload.pop("no_ml_baseline")
    with pytest.raises(ValidationError):
        validate("schemas/ml-workflow-decision.schema.json", payload)


def test_skill_and_offering_are_discoverable_but_not_installed() -> None:
    skills = load_json("registry/agent-skill-library.json")["skills"]
    skill = next(row for row in skills if row["skill_id"] == "skill:ml-workflow-agent-family")
    assert skill["status"] == "candidate"
    assert skill["checkout_modes"] == ["pointer", "wrapper"]
    assert (ROOT / skill["entrypoint"]).exists()
    assert (ROOT / skill["subagent_pack"]).exists()
    offerings = load_json("registry/dad-offerings-registry.json")["offerings"]
    offering = next(
        row for row in offerings if row["offering_id"] == "dad:offering:ml-workflow-agent-family"
    )
    assert offering["review_status"] == "candidate"
    assert "do not activate research automation" in offering["adoption_semantics"]
    metadata = yaml.safe_load(
        (ROOT / "assets/agent-skills/ml-workflow-agent-family/agents/openai.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert "$ml-workflow-agent-family" in metadata["interface"]["default_prompt"]


@pytest.mark.parametrize("command", [["status"], ["catalog", "--query", "leakage"], ["graph"], ["research-plan"]])
def test_ml_cli_commands_are_read_only_and_succeed(command: list[str]) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT / "src"), env.get("PYTHONPATH", "")) if part
    )
    result = subprocess.run(
        [sys.executable, "-m", "digital_asset_directory.cli", "ml", *command, "--hub", str(ROOT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidate_only"] is True


def test_ml_fit_cli_is_read_only_and_cannot_be_bypassed_by_named_tool() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT / "src"), env.get("PYTHONPATH", "")) if part
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "digital_asset_directory.cli",
            "ml",
            "fit",
            "--objective",
            "Predict a synthetic review outcome.",
            "--problem-shape",
            "tabular_prediction",
            "--execution-scale",
            "local",
            "--label-status",
            "available",
            "--named-tool",
            "PyTorch",
            "--hub",
            str(ROOT),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["first_hop_completed"] is True
    assert payload["dispatch_authorized"] is False
    assert payload["specialist_route"]["assessment_digest"] == payload["assessment_digest"]


def test_ml_specialist_cli_requires_and_replays_complete_receipt(tmp_path: Path) -> None:
    receipt = ml_fit_route(
        ROOT,
        objective="Predict a bounded synthetic review outcome.",
        problem_shape="tabular_prediction",
        execution_scale="local",
        label_status="available",
    )
    receipt_path = tmp_path / "fit-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT / "src"), env.get("PYTHONPATH", "")) if part
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "digital_asset_directory.cli",
            "ml",
            "specialist-route",
            "--receipt",
            str(receipt_path),
            "--hub",
            str(ROOT),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["assessment_digest"] == receipt["assessment_digest"]
    assert payload["dispatch_authorized"] is False

    receipt_path.write_text("[]", encoding="utf-8")
    blocked = subprocess.run(
        [
            sys.executable,
            "-m",
            "digital_asset_directory.cli",
            "ml",
            "specialist-route",
            "--receipt",
            str(receipt_path),
            "--hub",
            str(ROOT),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert blocked.returncode == 2
    blocked_payload = json.loads(blocked.stdout)
    assert blocked_payload["status"] == "blocked"
    assert "must be a JSON object" in blocked_payload["error"]
