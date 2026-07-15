from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from jsonschema import ValidationError
from jsonschema.validators import validator_for
import pytest
import yaml

from digital_asset_directory.knowledge_engineering import (
    BASELINE_TECHNIQUE_IDS,
    knowledge_catalog,
    knowledge_dependency_graph,
    knowledge_research_plan,
    knowledge_route,
    knowledge_status,
)


ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validate(schema_rel: str, payload: dict) -> None:
    schema = load_json(schema_rel)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER).validate(payload)


def test_knowledge_engineering_schemas_are_registered_and_conform() -> None:
    schemas = load_json("registry/schema-registry.json")["schemas"]
    expected = {
        "knowledge_engineering_family_registry": "schemas/knowledge-engineering-family-registry.schema.json",
        "knowledge_engineering_technique_registry": "schemas/knowledge-engineering-technique-registry.schema.json",
        "knowledge_engineering_source_registry": "schemas/knowledge-engineering-source-registry.schema.json",
        "knowledge_system_decision": "schemas/knowledge-system-decision.schema.json",
    }
    assert expected.items() <= schemas.items()
    validate(expected["knowledge_engineering_family_registry"], load_json("registry/knowledge-engineering-family-registry.json"))
    validate(expected["knowledge_engineering_technique_registry"], load_json("registry/knowledge-engineering-technique-registry.json"))
    validate(expected["knowledge_engineering_source_registry"], load_json("registry/knowledge-engineering-source-registry.json"))


def test_technique_library_is_bounded_sourced_and_baseline_first() -> None:
    registry = load_json("registry/knowledge-engineering-technique-registry.json")
    rows = registry["techniques"]
    ids = [row["technique_id"] for row in rows]
    revisions = [row["revision_id"] for row in rows]
    assert len(rows) == 24
    assert len(ids) == len(set(ids))
    assert len(revisions) == len(set(revisions))
    assert "intentionally incomplete" in registry["coverage_statement"]
    assert set(BASELINE_TECHNIQUE_IDS) <= set(ids)
    categories = {row["category"] for row in rows}
    assert {"baseline", "chunking", "retrieval", "context", "vector_index", "graph", "agentic", "evaluation", "security", "lifecycle"} <= categories
    for row in rows:
        assert row["applies_when"]
        assert row["does_not_apply_when"]
        assert row["danger_if_misapplied"]
        assert row["baseline_refs"]
        assert row["evaluation_requirements"]
        assert row["operational_requirements"]
        assert row["privacy_security_requirements"]
        assert row["source_refs"]


def test_portable_role_pack_is_closed_provider_neutral_and_independently_checked() -> None:
    pack_text = (ROOT / "assets/agent-skills/knowledge-engineering-ops/subagents.yaml").read_text(encoding="utf-8")
    pack = yaml.safe_load(pack_text)
    validate("schemas/subagent-pack.schema.json", pack)
    known = {row["id"] for row in load_json("registry/subagent-capability-registry.json")["capabilities"]}
    declared = {cap for role in pack["roles"] for cap in role["capability_ids"]}
    assert declared <= known
    assert pack["ai_agnostic"] is True
    assert pack["routing_policy"]["max_delegation_depth"] == 1
    assert pack["routing_policy"]["one_writer"] is True
    assert pack["routing_policy"]["independent_checker_required"] is True
    assert pack["routing_policy"]["model_ids_are_attempt_metadata_only"] is True
    role_ids = {row["role_id"] for row in pack["roles"]}
    assert {"knowledge-engineering-router", "knowledge-authority-boss", "knowledge-system-architect", "knowledge-workflow-foreman", "knowledge-implementation-worker", "knowledge-independent-checker", "knowledge-frontier-sentinel"} <= role_ids
    assert not any(value in pack_text.lower() for value in ("gpt-5", "claude-", "gemini-", "model_id:"))


def test_family_is_child_pack_with_research_quality_and_security_peers() -> None:
    status = knowledge_status(ROOT)
    assert status["ai_agnostic"] is True
    assert status["parent_family_id"] == "family:data-schema-knowledge-graph"
    assert {"family:knowledge-research-provenance", "family:quality-verification-release", "family:security-privacy-supply-chain"} <= set(status["peer_family_ids"])
    assert status["role_count"] == 14
    assert status["technique_count"] == 24
    assert status["scheduled"] is False

    portfolio = load_json("registry/agent-family-portfolio-registry.json")
    parent = next(row for row in portfolio["families"] if row["family_id"] == "family:data-schema-knowledge-graph")
    assert "pack:knowledge-engineering-ops" in parent["specialist_packs"]
    edges = portfolio["graph_contract"]["dependency_edges"]
    assert {edge["edge_type"] for edge in edges} <= set(portfolio["graph_contract"]["edge_types"])
    assert any(edge["source"] == "pack:knowledge-engineering-ops" and edge["edge_type"] == "member_of" and edge["target"] == parent["family_id"] for edge in edges)


@pytest.mark.parametrize(
    ("query", "profile", "route_kind"),
    [
        ("hybrid rag with rerank for enterprise search", "ke-route:hybrid-reranked", "hybrid"),
        ("long context whole document synthesis", "ke-route:long-context", "long_context"),
        ("graphrag global themes and multi hop relationships", "ke-route:global-multihop-graph", "graph"),
        ("temporal as of history and superseded fact", "ke-route:temporal-graph", "temporal_graph"),
    ],
)
def test_deterministic_route_selects_smallest_candidate_without_dispatch(query: str, profile: str, route_kind: str) -> None:
    result = knowledge_route(ROOT, query)
    assert result["selected_profile_id"] == profile
    assert result["route_kind"] == route_kind
    assert result["dispatch_authorized"] is False
    assert result["candidate_only"] is True
    assert set(BASELINE_TECHNIQUE_IDS) <= set(result["candidate_technique_ids"])
    assert {"source authority", "independent evaluation", "privacy and access"} <= set(result["required_gates"])


def test_unknown_route_preserves_baselines_and_requires_human_decision() -> None:
    result = knowledge_route(ROOT, "flibbertigibbet zxqv")
    assert result["disposition"] == "insufficient_evidence"
    assert result["selected_profile_id"] is None
    assert result["human_decision_required"] is True
    assert result["candidate_technique_ids"] == list(BASELINE_TECHNIQUE_IDS)


@pytest.mark.parametrize(
    "query",
    ["bragging rights", "storage backup", "fragmentation policy", "courage and trust"],
)
def test_route_terms_require_token_boundaries(query: str) -> None:
    result = knowledge_route(ROOT, query)
    assert result["disposition"] == "insufficient_evidence"
    assert result["selected_profile_id"] is None
    assert result["human_decision_required"] is True


def test_equal_best_route_selects_no_winner() -> None:
    result = knowledge_route(ROOT, "citation semantic")
    assert result["disposition"] == "ambiguous_equal_best"
    assert result["route_kind"] is None
    assert result["selected_profile_id"] is None
    assert result["equal_best_profile_ids"] == [
        "ke-route:exact-lexical",
        "ke-route:semantic-vector",
    ]
    assert result["human_decision_required"] is True


def test_catalog_searches_roles_techniques_workflows_and_sources_read_only() -> None:
    result = knowledge_catalog(ROOT, "late chunking")
    assert "ke-technique:late-chunking" in {row["technique_id"] for row in result["techniques"]}
    assert result["roles"]
    assert result["sources"]
    assert result["candidate_only"] is True


def test_dependency_graph_is_typed_transitive_and_fails_closed() -> None:
    graph = knowledge_dependency_graph(ROOT, "skill:knowledge-engineering-ops")
    targets = {edge["target"] for edge in graph["upstream_edges"]}
    assert "skill:data-schema-knowledge-graph-agent-family" in targets
    assert "registry:knowledge-engineering-technique-registry" in targets
    assert "family:quality-verification-release" in targets
    pack_view = knowledge_dependency_graph(ROOT, "family:data-schema-knowledge-graph")
    assert any(edge["source"] == "pack:knowledge-engineering-ops" and edge["edge_type"] == "member_of" for edge in pack_view["downstream_edges"])
    with pytest.raises(ValueError, match="Unknown Knowledge Engineering graph node"):
        knowledge_dependency_graph(ROOT, "vector-store:universal-winner")


def test_weekly_research_is_pointer_only_delta_first_and_not_scheduled() -> None:
    plan = knowledge_research_plan(ROOT)
    assert plan["contract"]["cadence"] == "P7D"
    assert plan["contract"]["activation_status"] == "human_activation_required"
    assert plan["watch_policy"]["delta_first"] is True
    assert plan["watch_policy"]["content_retention"] == "pointers_and_bounded_claims_only"
    assert plan["scheduled"] is False
    assert plan["activation_required"] is True
    assert len(plan["source_ids"]) >= 20


def test_source_watchlist_is_primary_pointer_only_and_has_no_media_payloads() -> None:
    registry = load_json("registry/knowledge-engineering-source-registry.json")
    assert registry["candidate_only"] is True
    assert registry["watch_policy"]["activation_status"] == "human_activation_required"
    urls = [row["url"] for row in registry["sources"]]
    assert len(urls) == len(set(urls))
    assert not any("youtube.com" in url for url in urls)
    assert {row["source_type"] for row in registry["sources"]} <= {"official_standard", "official_documentation", "official_repository", "original_paper", "official_security_guidance"}


def test_knowledge_system_decision_requires_source_no_rag_and_human_gates() -> None:
    payload = {
        "schema_version": "0.1.0",
        "decision_id": "knowledge-system-decision:synthetic-retrieval",
        "created_at": "2026-07-15T00:00:00Z",
        "goal": "Retrieve synthetic policy clauses with exact citations.",
        "decision_owner": "named synthetic owner",
        "source_authority": "synthetic public fixture",
        "authority_and_sensitivity": "public synthetic data only",
        "query_shapes": ["exact phrase", "semantic paraphrase"],
        "no_retrieval_baseline": "Direct bounded source lookup and lexical BM25.",
        "candidate_technique_ids": ["ke-technique:lexical-bm25", "ke-technique:hybrid-rank-fusion"],
        "recommendation": "bounded_experiment",
        "ingestion_contract": "Versioned synthetic source, parser, chunk, delete, and rebuild manifest.",
        "evaluation_contract": "Recall, citation entailment, abstention, latency, cost, and negative ACL fixtures.",
        "human_gates": ["Named owner approves any non-synthetic continuation."],
        "rollback_and_kill_criteria": ["Stop on source mismatch, access failure, or citation regression."],
        "unknowns": [],
        "evidence_refs": ["source://synthetic-fixture"],
        "review_status": "candidate",
        "authority_boundary": "Fixture evidence authorizes no real corpus or deployment.",
    }
    validate("schemas/knowledge-system-decision.schema.json", payload)
    payload.pop("no_retrieval_baseline")
    with pytest.raises(ValidationError):
        validate("schemas/knowledge-system-decision.schema.json", payload)


def test_skill_offering_evaluation_profile_and_global_allowlist_are_discoverable() -> None:
    skills = load_json("registry/agent-skill-library.json")["skills"]
    skill = next(row for row in skills if row["skill_id"] == "skill:knowledge-engineering-ops")
    assert skill["status"] == "candidate"
    assert (ROOT / skill["entrypoint"]).exists()
    assert (ROOT / skill["subagent_pack"]).exists()
    offerings = load_json("registry/dad-offerings-registry.json")["offerings"]
    offering = next(row for row in offerings if row["offering_id"] == "dad:offering:knowledge-engineering-ops")
    assert offering["review_status"] == "candidate"
    assert "does not activate weekly research" in offering["adoption_semantics"]
    profiles = load_json("registry/subagent-evaluation-profile-registry.json")["profiles"]
    profile = next(row for row in profiles if row["profile_id"] == "dad:evaluation-profile:knowledge-engineering-workflow")
    assert profile["domain_expert_required"] is True
    personal = load_json("config/global-personal-skills.json")["skills"]
    assert any(row["skill_id"] == "personal-skill:knowledge-engineering-ops" and row["source_path"] == "knowledge-engineering-ops" for row in personal)


def test_portable_dad_skill_has_no_sensitive_paths_or_runtime_binding() -> None:
    skill_root = ROOT / "assets/agent-skills/knowledge-engineering-ops"
    text = "\n".join(path.read_text(encoding="utf-8") for path in skill_root.rglob("*") if path.is_file())
    lowered = text.lower()
    assert "c:\\users\\" not in lowered
    assert "/users/lowel" not in lowered
    assert "gpt-5.6" not in lowered
    assert "execution_authorized=true" not in lowered
    assert "auto_schedule: true" not in lowered


@pytest.mark.parametrize(
    "command",
    [
        ["status"],
        ["catalog", "--query", "temporal graph"],
        ["route", "--query", "hybrid rag rerank"],
        ["graph"],
        ["research-plan"],
    ],
)
def test_knowledge_engineering_cli_commands_are_read_only_and_succeed(command: list[str]) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(part for part in (str(ROOT / "src"), env.get("PYTHONPATH", "")) if part)
    result = subprocess.run(
        [sys.executable, "-m", "digital_asset_directory.cli", "knowledge-engineering", *command, "--hub", str(ROOT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidate_only"] is True
