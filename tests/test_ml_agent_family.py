from __future__ import annotations

from datetime import datetime, timezone
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
    ml_research_plan,
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
    assert len(techniques) == 15
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


def test_workflow_decision_requires_no_ml_and_human_gates() -> None:
    payload = {
        "schema_version": "0.1.0",
        "decision_id": "ml-workflow-decision:synthetic-tabular",
        "created_at": "2026-07-14T00:00:00Z",
        "goal": "Predict a synthetic outcome for a bounded experiment.",
        "decision_owner": "named synthetic owner",
        "authority_and_sensitivity": "synthetic public fixture only",
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
