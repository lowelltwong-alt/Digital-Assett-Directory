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
