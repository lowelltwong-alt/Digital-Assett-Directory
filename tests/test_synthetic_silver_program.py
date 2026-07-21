from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def program_registry() -> dict:
    return _load("registry/synthetic-silver-program-registry.json")


def _validate(schema_rel: str, payload: dict) -> None:
    schema = _load(schema_rel)
    jsonschema.validate(
        payload,
        schema,
        format_checker=jsonschema.FormatChecker(),
    )


def test_program_registry_validates_against_schema(program_registry: dict) -> None:
    _validate("schemas/synthetic-silver-program-registry.schema.json", program_registry)


def test_schema_registry_has_all_three_schemas() -> None:
    registry = _load("registry/schema-registry.json")["schemas"]
    for name, rel in (
        ("synthetic_silver_program_registry", "schemas/synthetic-silver-program-registry.schema.json"),
        ("synthetic_silver_provenance_record", "schemas/synthetic-silver-provenance-record.schema.json"),
        ("synthetic_silver_release_manifest", "schemas/synthetic-silver-release-manifest.schema.json"),
    ):
        assert registry[name] == rel
        assert (ROOT / rel).is_file()


def test_tier_ladder_keeps_human_authority(program_registry: dict) -> None:
    tiers = {row["tier_id"]: row for row in program_registry["tier_ladder"]}
    assert set(tiers) == {"S0", "S1", "S2", "S3", "G1", "G2"}
    # Nothing above S2 moves without a human gate.
    for tier_id in ("S3", "G1", "G2"):
        assert tiers[tier_id]["human_gate_required"] is True
    # G2 is the only promoted tier; S tiers never map to promoted.
    for tier_id in ("S0", "S1", "S2", "S3", "G1"):
        assert tiers[tier_id]["dad_lifecycle"] != "promoted"
    assert tiers["G2"]["dad_lifecycle"] == "promoted"


def test_adapters_never_authorize_dad_writes(program_registry: dict) -> None:
    adapters = {row["adapter_id"]: row for row in program_registry["adapters"]}
    assert all(row["write_policy"] == "dad_never_writes" for row in adapters.values())
    assert adapters["adapter:logos"]["mode"] == "read_only_pointer"
    assert adapters["adapter:world-builder"]["mode"] == "target_unresolved"


def test_registry_carries_no_numeric_thresholds(program_registry: dict) -> None:
    policy = program_registry["threshold_policy"]
    assert policy["numeric_thresholds_in_registry"] is False
    assert policy["calibration_required"] is True


def test_recipes_are_deterministic_first(program_registry: dict) -> None:
    recipes = {row["recipe_id"] for row in program_registry["recipes"]}
    assert recipes >= {
        "recipe:discrete-labels",
        "recipe:lossless-transformations",
        "recipe:open-ended-outputs",
    }
    assert all(row["deterministic_first"] is True for row in program_registry["recipes"])


def test_provenance_golden_fixture_validates() -> None:
    record = _load("examples/synthetic-silver/provenance-record.golden.json")
    _validate("schemas/synthetic-silver-provenance-record.schema.json", record)
    # Independence tracking is structural: producer and judge families required.
    assert record["candidate"]["producer_family"]
    assert all(row["judge_family"] for row in record["judge_results"])


def test_provenance_schema_rejects_source_text_payloads() -> None:
    record = _load("examples/synthetic-silver/provenance-record.golden.json")
    record["text"] = "smuggled corpus content"
    with pytest.raises(jsonschema.ValidationError):
        _validate("schemas/synthetic-silver-provenance-record.schema.json", record)


def test_provenance_schema_requires_adjudication_for_g_tiers() -> None:
    record = _load("examples/synthetic-silver/provenance-record.golden.json")
    record["status"] = "g1_human_adjudicated"
    with pytest.raises(jsonschema.ValidationError):
        _validate("schemas/synthetic-silver-provenance-record.schema.json", record)


def test_release_manifest_golden_fixture_validates() -> None:
    manifest = _load("examples/synthetic-silver/release-manifest.golden.json")
    _validate("schemas/synthetic-silver-release-manifest.schema.json", manifest)
    # Release manifests are S-tier only; G-tier promotion is a human decision,
    # not a release artifact.
    assert manifest["tier"] in {"S0", "S1", "S2", "S3"}


def test_program_doc_and_navigation_are_wired() -> None:
    doc = (ROOT / "docs/SYNTHETIC_SILVER_PROGRAM.md").read_text(encoding="utf-8")
    assert "read-only to DAD" in doc
    toc = (ROOT / "AI_TABLE_OF_CONTENTS.md").read_text(encoding="utf-8")
    assert "docs/SYNTHETIC_SILVER_PROGRAM.md" in toc
    nav = _load("registry/ai-navigation-registry.json")
    branch_ids = {row["branch_id"] for row in nav["branch_map"]}
    assert "synthetic_silver_program" in branch_ids
