from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def _load(relpath: str) -> dict:
    return json.loads((ROOT / relpath).read_text(encoding="utf-8"))


def test_registry_validates_against_schema() -> None:
    jsonschema.validate(
        _load("config/intelligence-routing-registry.json"),
        _load("schemas/intelligence-routing-registry.schema.json"),
    )


def test_top_tiers_are_human_approval_gated() -> None:
    registry = _load("config/intelligence-routing-registry.json")
    gated = {
        tier["tier_id"]
        for vendor in registry["vendors"].values()
        for tier in vendor["tiers"]
        if tier.get("requires_human_approval")
    }
    assert "codex-ultra" in gated
    assert "claude-fable" in gated
    # The maximum rank of every vendor must be approval-gated: reserved
    # capacity can never become a silent default.
    for vendor in registry["vendors"].values():
        top = max(vendor["tiers"], key=lambda tier: tier["rank"])
        assert top.get("requires_human_approval") is True, top["tier_id"]


def test_task_class_defaults_reference_real_tiers() -> None:
    registry = _load("config/intelligence-routing-registry.json")
    known = {
        tier["tier_id"]
        for vendor in registry["vendors"].values()
        for tier in vendor["tiers"]
    }
    for row in registry["task_class_defaults"]:
        for tier_id in row["start_tier"]:
            assert tier_id in known, f"unknown tier {tier_id} in {row['task_class']}"


def test_load_bearing_class_is_approval_gated() -> None:
    registry = _load("config/intelligence-routing-registry.json")
    row = next(
        r
        for r in registry["task_class_defaults"]
        if r["task_class"] == "load_bearing_or_reflexive_or_irreversible"
    )
    assert row.get("requires_human_approval") is True


def test_ranks_are_unique_and_ascending_per_vendor() -> None:
    registry = _load("config/intelligence-routing-registry.json")
    for vendor_id, vendor in registry["vendors"].items():
        ranks = [tier["rank"] for tier in vendor["tiers"]]
        assert len(ranks) == len(set(ranks)), f"duplicate ranks in {vendor_id}"
        assert ranks == sorted(ranks), f"ranks not ascending in {vendor_id}"


def test_recommend_start_tiers_is_advice_only_and_registry_bound() -> None:
    from digital_asset_directory.intelligence_routing import (
        classify_task_class,
        recommend_start_tiers,
        validate_declared_default_tiers,
    )

    mechanical = recommend_start_tiers(
        "mechanical formatting and capture structuring",
        ROOT,
    )
    assert mechanical["advice_only"] is True
    assert mechanical["execution_authorized"] is False
    assert mechanical["task_class"] == "mechanical_edit_or_capture_structuring"
    assert mechanical["recommended_start_tiers"] == ["codex-luna", "claude-haiku-4.5"]

    standard = recommend_start_tiers("implement feature with tests", ROOT)
    assert standard["task_class"] == "standard_build_with_tests"
    assert "codex-terra" in standard["recommended_start_tiers"]

    load_bearing = recommend_start_tiers(
        "load-bearing irreversible authority model change",
        ROOT,
    )
    assert load_bearing["task_class"] == "load_bearing_or_reflexive_or_irreversible"
    assert load_bearing["requires_human_approval"] is True

    assert classify_task_class("unrelated wording") == "standard_build_with_tests"
    assert validate_declared_default_tiers(ROOT) == []


def test_compile_context_pack_includes_intelligence_routing_advice() -> None:
    from digital_asset_directory.dad_library import compile_context_pack

    pack = compile_context_pack(
        ROOT,
        ROOT,
        session_id="dad:session:test-n7",
        task="red-team premortem of architecture-adjacent change",
    )
    advice = pack["intelligence_routing_advice"]
    assert advice is not None
    assert advice["advice_only"] is True
    assert advice["task_class"] == "red_team_premortem_architecture_adjacent"
    assert advice["recommended_start_tiers"] == ["codex-sol", "claude-sonnet-high"]
    assert advice["execution_authorized"] is False


def test_skill_and_subagent_schemas_accept_optional_default_tier() -> None:
    skill_schema = _load("schemas/agent-skill-library.schema.json")
    subagent_schema = _load("schemas/subagent-pack.schema.json")
    skill_props = skill_schema["properties"]["skills"]["items"]["properties"]
    role_props = subagent_schema["properties"]["roles"]["items"]["properties"]
    assert "default_tier" in skill_props
    assert "default_tier" in role_props
    assert skill_props["default_tier"]["minItems"] == 1
    assert role_props["default_tier"]["minItems"] == 1
