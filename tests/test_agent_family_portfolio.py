from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path

from jsonschema.validators import validator_for
import yaml

from digital_asset_directory.agent_families import (
    agent_family_catalog,
    agent_family_dependency_graph,
    agent_family_health,
    build_portfolio_cockpit_v2,
    inspect_agent_family_pilot,
    portfolio_cockpit_v2_html,
    route_agent_families,
)


ROOT = Path(__file__).resolve().parents[1]
FAMILY_SKILLS = [
    "full-stack-engineering-agent-family",
    "platform-cloud-sre-agent-family",
    "quality-verification-release-agent-family",
    "security-privacy-supply-chain-agent-family",
    "knowledge-research-provenance-agent-family",
    "data-schema-knowledge-graph-agent-family",
    "integration-mcp-automation-agent-family",
    "product-ux-accessibility-agent-family",
    "legal-evidence-governance-overlay",
]


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validate(schema_rel: str, payload: dict) -> None:
    schema = load_json(schema_rel)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER).validate(payload)


def test_registry_and_all_family_schemas_are_registered_and_valid() -> None:
    schema_registry = load_json("registry/schema-registry.json")["schemas"]
    expected = {
        "agent_family_portfolio_registry": "schemas/agent-family-portfolio-registry.schema.json",
        "agent_family_routing_decision": "schemas/agent-family-routing-decision.schema.json",
        "agent_family_health": "schemas/agent-family-health.schema.json",
        "agent_family_pilot": "schemas/agent-family-pilot.schema.json",
        "portfolio_cockpit_v2": "schemas/portfolio-cockpit-v2.schema.json",
    }
    for key, path in expected.items():
        assert schema_registry[key] == path
    validate(
        expected["agent_family_portfolio_registry"],
        load_json("registry/agent-family-portfolio-registry.json"),
    )


def test_portfolio_is_small_model_neutral_and_wip_bounded() -> None:
    registry = load_json("registry/agent-family-portfolio-registry.json")
    assert len(registry["families"]) == 10
    assert registry["ai_agnostic"] is True
    assert registry["runtime_routing"]["capability_aliases"] == ["luna", "terra", "sol"]
    assert set(registry["runtime_routing"]["attempt_only_fields"]) >= {
        "provider",
        "model_id",
        "expires_at",
    }
    assert registry["portfolio_wip_policy"]["maximum_active_family_builds"] == 1
    assert registry["portfolio_wip_policy"]["maximum_active_family_pilots"] == 1
    assert sum(pilot["status"] == "active_candidate_pilot" for pilot in registry["pilots"]) <= 1
    stable = json.dumps(
        {
            "families": registry["families"],
            "roles": registry["shared_contract"]["roles"],
        }
    ).lower()
    for vendor_term in ("openai", "anthropic", "gemini", "gpt-", "claude-"):
        assert vendor_term not in stable


def test_each_new_skill_has_the_shared_roles_and_distinct_checker() -> None:
    capability_ids = {
        row["id"]
        for row in load_json("registry/subagent-capability-registry.json")["capabilities"]
    }
    expected_suffixes = {
        "router",
        "boss",
        "architect",
        "foreman",
        "worker",
        "independent-checker",
        "sentinel",
    }
    for skill_name in FAMILY_SKILLS:
        base = ROOT / "assets" / "agent-skills" / skill_name
        pack = yaml.safe_load((base / "subagents.yaml").read_text(encoding="utf-8"))
        validate("schemas/subagent-pack.schema.json", pack)
        role_ids = [role["role_id"] for role in pack["roles"]]
        assert len(role_ids) == 7 == len(set(role_ids))
        assert {role_id.removeprefix(f"{skill_name.removesuffix('-agent-family')}-") for role_id in role_ids} != set()
        assert {next(s for s in expected_suffixes if role_id.endswith(f"-{s}")) for role_id in role_ids} == expected_suffixes
        worker = next(role_id for role_id in role_ids if role_id.endswith("-worker"))
        checker = next(role_id for role_id in role_ids if role_id.endswith("-independent-checker"))
        assert worker != checker
        declared = {item for role in pack["roles"] for item in role["capability_ids"]}
        assert declared <= capability_ids
        assert pack["ai_agnostic"] is True
        assert pack["routing_policy"]["one_writer"] is True
        assert pack["routing_policy"]["independent_checker_required"] is True
        assert pack["routing_policy"]["model_ids_are_attempt_metadata_only"] is True


def test_skill_library_and_offering_expose_pointer_only_adoption() -> None:
    skills = load_json("registry/agent-skill-library.json")["skills"]
    by_id = {row["skill_id"]: row for row in skills}
    for skill_name in FAMILY_SKILLS:
        row = by_id[f"skill:{skill_name}"]
        assert row["status"] == "candidate"
        assert row["checkout_modes"] == ["pointer", "wrapper"]
        assert (ROOT / row["entrypoint"]).exists()
        assert (ROOT / row["subagent_pack"]).exists()
    offerings = load_json("registry/dad-offerings-registry.json")["offerings"]
    offering = next(
        row
        for row in offerings
        if row["offering_id"] == "dad:offering:agent-family-portfolio-control-plane"
    )
    assert offering["offering_type"] == "control_plane"
    assert offering["review_status"] == "candidate"


def test_mcp_and_ui_specialist_packs_are_members_not_new_families() -> None:
    registry = load_json("registry/agent-family-portfolio-registry.json")
    families = {row["family_id"]: row for row in registry["families"]}
    expected = {
        "pack:mcp-integration-specialist-pack": "family:integration-mcp-automation",
        "pack:ui-ux-specialist-pack": "family:product-ux-accessibility",
    }
    assert len(families) == 10
    for pack_id, family_id in expected.items():
        assert pack_id in families[family_id]["specialist_packs"]
        assert pack_id not in families
        assert any(
            edge["source"] == pack_id
            and edge["edge_type"] == "member_of"
            and edge["target"] == family_id
            for edge in registry["graph_contract"]["dependency_edges"]
        )


def test_routing_selects_the_smallest_combination_and_separate_assurance() -> None:
    ml = route_agent_families(ROOT, "train a machine learning classifier")
    assert ml["selected_family_ids"] == ["family:ml-workflow"]
    assert ml["supporting_family_ids"] == ["family:quality-verification-release"]
    assert ml["checker_family_id"] == "family:quality-verification-release"
    assert ml["execution_authorized"] is False

    exact_research = route_agent_families(ROOT, "research a white paper", material=False)
    assert exact_research["selected_family_ids"] == ["family:knowledge-research-provenance"]
    assert exact_research["supporting_family_ids"] == []

    legal = route_agent_families(ROOT, "review privilege for a matter")
    assert legal["selected_family_ids"] == ["family:legal-evidence-governance"]
    assert legal["supporting_family_ids"] == ["family:quality-verification-release"]
    assert "legal_human_review" in legal["human_gates"]

    empty = route_agent_families(ROOT, "rename a local variable", material=False)
    assert empty["selected_family_ids"] == []
    assert empty["supporting_family_ids"] == []


def test_catalog_and_dependency_graph_are_read_only_candidate_projections() -> None:
    catalog = agent_family_catalog(ROOT, "accessibility")
    assert [row["family_id"] for row in catalog["families"]] == [
        "family:quality-verification-release",
        "family:product-ux-accessibility",
    ]
    graph = agent_family_dependency_graph(ROOT, "family:full-stack-engineering")
    assert graph["candidate_only"] is True
    assert graph["execution_authorized"] is False
    assert any(
        edge["edge_type"] == "validated_by"
        and edge["target"] == "family:quality-verification-release"
        for edge in graph["edges"]
    )
    allowed = set(load_json("registry/agent-family-portfolio-registry.json")["graph_contract"]["edge_types"])
    assert {edge["edge_type"] for edge in graph["edges"]} <= allowed
    registered = {row["edge_type"] for row in load_json("registry/graph-edge-registry.json")["edge_types"]}
    assert allowed <= registered


def test_health_is_semantically_deduplicated_and_timestamp_independent() -> None:
    first = agent_family_health(ROOT, now=datetime(2026, 7, 14, tzinfo=timezone.utc))
    second = agent_family_health(ROOT, now=datetime(2026, 7, 28, tzinfo=timezone.utc))
    validate("schemas/agent-family-health.schema.json", first)
    assert first["summary"]["family_count"] == 10
    assert first["summary"]["stale_count"] == 0
    assert first["summary"]["unknown_count"] == 0
    assert first["summary"]["issue_count"] == 10
    assert len({row["fingerprint"] for row in first["issues"]}) == 10
    assert [row["fingerprint"] for row in first["issues"]] == [
        row["fingerprint"] for row in second["issues"]
    ]


def test_cockpit_v2_limits_now_to_three_preserves_digest_and_escapes_html() -> None:
    health = agent_family_health(ROOT, now=datetime(2026, 7, 14, tzinfo=timezone.utc))
    cockpit = build_portfolio_cockpit_v2(
        health,
        {"schema_version": "dad.portfolio_cockpit.v1", "today": []},
        now=datetime(2026, 7, 14, tzinfo=timezone.utc),
    )
    cockpit["now"][0]["reasons"] = ["<script>alert(1)</script>"]
    validate("schemas/portfolio-cockpit-v2.schema.json", cockpit)
    assert len(cockpit["now"]) == 3
    assert len(cockpit["digest"]) == 10
    assert sum(item["selected_now"] for item in cockpit["digest"]) == 3
    html = portfolio_cockpit_v2_html(cockpit)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<form" not in html.lower()
    assert "<button" not in html.lower()


def test_metadata_only_pilot_preserves_source_git_state(tmp_path: Path) -> None:
    repo = tmp_path / "pilot"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    (repo / "app.tsx").write_text("export const secret = 'not-returned';\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    before = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    result = inspect_agent_family_pilot(
        ROOT,
        repo,
        "pilot:dad-agent-family-portfolio",
        now=datetime(2026, 7, 14, tzinfo=timezone.utc),
    )
    after = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    validate("schemas/agent-family-pilot.schema.json", result)
    assert before == after
    assert result["mutation_observed"] is False
    assert result["source_git_fingerprint_before"] == result["source_git_fingerprint_after"]
    assert result["observed_metadata"]["tracked_file_count"] == 2
    assert set(result["observed_metadata"]["stack_indicators"]) == {"frontend", "python"}
    serialized = json.dumps(result)
    assert str(repo) not in serialized
    assert "not-returned" not in serialized
