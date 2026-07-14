from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys

import jsonschema
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PACK = ROOT / "assets/agent-skills/dad-manifest-graph-engineering/subagents.yaml"
ASSET_PACK = ROOT / "assets/agent-skills/dad-digital-asset-radar/subagents.yaml"
MESH_ROOT = ROOT / "assets/agent-skills/dad-manifest-graph-engineering"
MESH_SCHEMA = MESH_ROOT / "references/agent-mesh-manifest.schema.json"
MESH_TEMPLATE = MESH_ROOT / "assets/agent-mesh-manifest.template.json"
MESH_VALIDATOR_PATH = MESH_ROOT / "scripts/validate_agent_mesh_manifest.py"
SPEC = importlib.util.spec_from_file_location("dad_agent_mesh_validator", MESH_VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
MESH_VALIDATOR = importlib.util.module_from_spec(SPEC)
_DONT_WRITE_BYTECODE = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    SPEC.loader.exec_module(MESH_VALIDATOR)
finally:
    sys.dont_write_bytecode = _DONT_WRITE_BYTECODE


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _mesh() -> dict:
    return json.loads(MESH_TEMPLATE.read_text(encoding="utf-8"))


def _execution(prior: dict) -> dict:
    current = copy.deepcopy(prior)
    current["revision_id"] = "dad:agent-mesh-revision:example-task:v2"
    current["supersedes_revision_id"] = prior["revision_id"]
    current["phase"] = "execution"
    current["status"] = "active"
    current["reconciliations"] = [
        {
            "prior_role_id": role["role_id"],
            "disposition": "reused",
            "current_role_ids": [role["role_id"]],
            "reason": "The planned role remains necessary and bounded.",
            "evidence_refs": ["execution-preflight"],
            "material_drift": False,
        }
        for role in prior["roles"]
    ]
    current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
    return current


def _derived_role(base: dict, role_id: str, relation: str = "specialist") -> dict:
    role = copy.deepcopy(base)
    role["role_id"] = role_id
    role["writer_checker_relation"] = relation
    role["why_needed"] = f"{role_id} is required by the revised decomposition."
    return role


def _replaced_execution(prior: dict) -> dict:
    current = _execution(prior)
    replacement = _derived_role(prior["roles"][0], "replacement-writer", "writer")
    current["roles"][0] = replacement
    current["writer_role_id"] = replacement["role_id"]
    current["roles"][1]["dependencies"] = [replacement["role_id"]]
    current["proof_obligations"][0]["owner_role_id"] = replacement["role_id"]
    current["reconciliations"][0].update(
        disposition="replaced",
        current_role_ids=[replacement["role_id"]],
        material_drift=True,
    )
    current["reconciliations"][1]["material_drift"] = True
    current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
    return current


def _split_execution(prior: dict) -> dict:
    current = _execution(prior)
    first = _derived_role(prior["roles"][0], "split-writer", "writer")
    second = _derived_role(prior["roles"][0], "split-specialist")
    current["roles"] = [first, second, current["roles"][1]]
    current["writer_role_id"] = first["role_id"]
    current["roles"][2]["dependencies"] = [first["role_id"], second["role_id"]]
    current["proof_obligations"][0]["owner_role_id"] = first["role_id"]
    current["reconciliations"][0].update(
        disposition="split",
        current_role_ids=[first["role_id"], second["role_id"]],
        material_drift=True,
    )
    current["reconciliations"][1]["material_drift"] = True
    current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
    return current


def _prior_with_specialist() -> dict:
    prior = _mesh()
    specialist = _derived_role(prior["roles"][0], "bounded-specialist")
    specialist["dependencies"] = [prior["writer_role_id"]]
    prior["roles"].append(specialist)
    prior["manifest_digest"] = MESH_VALIDATOR.canonical_digest(prior)
    return prior


def _removed_execution(prior: dict) -> dict:
    current = _execution(prior)
    removed_id = "bounded-specialist"
    current["roles"] = [role for role in current["roles"] if role["role_id"] != removed_id]
    row = next(row for row in current["reconciliations"] if row["prior_role_id"] == removed_id)
    row.update(disposition="removed", current_role_ids=[], material_drift=True)
    current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
    return current


def _added_execution(prior: dict) -> dict:
    current = _execution(prior)
    specialist = _derived_role(prior["roles"][0], "added-specialist")
    specialist["dependencies"] = [prior["writer_role_id"]]
    current["roles"].append(specialist)
    current["reconciliations"].append(
        {
            "disposition": "added",
            "current_role_ids": [specialist["role_id"]],
            "reason": "New evidence requires a bounded specialist.",
            "evidence_refs": ["execution-preflight"],
            "material_drift": True,
        }
    )
    current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
    return current


def test_structured_artifact_packs_are_ai_agnostic_and_schema_valid():
    schema = json.loads((ROOT / "schemas/subagent-pack.schema.json").read_text(encoding="utf-8"))
    registered = {
        row["id"]
        for row in json.loads(
            (ROOT / "registry/subagent-capability-registry.json").read_text(encoding="utf-8")
        )["capabilities"]
    }

    for path in (MANIFEST_PACK, ASSET_PACK):
        pack = _yaml(path)
        jsonschema.Draft202012Validator(schema).validate(pack)
        assert pack["ai_agnostic"] is True
        assert pack["routing_policy"]["deterministic_first"] is True
        assert pack["routing_policy"]["max_delegation_depth"] == 1
        writer = pack["routing_policy"]["writer_role_id"]
        checker = pack["routing_policy"]["checker_role_id"]
        assert writer != checker
        roles = {row["role_id"]: row for row in pack["roles"]}
        assert writer in roles and checker in roles
        assert "independent" in roles[checker]["mission"].casefold()
        assert "checker_is_writer" in roles[checker]["stop_conditions"]
        assert all(set(row["capability_ids"]) <= registered for row in pack["roles"])
        assert len(roles) == len(pack["roles"])
        assert len({row["profile_role_id"] for row in pack["roles"]}) == len(pack["roles"])
        text = path.read_text(encoding="utf-8").casefold()
        assert "self_grade_authority: none" in text or "self-grades as proof" in text
        assert "raw private" in text or "raw_private_data" in text


def test_manifest_pack_has_complete_engineering_decomposition():
    pack = _yaml(MANIFEST_PACK)
    assert {row["role_id"] for row in pack["roles"]} == {
        "manifest-mission-authority-steward",
        "identity-address-ontology-steward",
        "dependency-dataflow-extractor",
        "typed-graph-provenance-modeler",
        "schema-contract-engineer",
        "deterministic-manifest-graph-builder",
        "fingerprint-freshness-version-steward",
        "reverse-blast-radius-analyst",
        "query-mcp-projection-engineer",
        "independent-manifest-graph-auditor",
    }


def test_plan_execution_mesh_contract_is_revisioned_and_reconciled():
    skill = (ROOT / "assets/agent-skills/dad-manifest-graph-engineering/SKILL.md").read_text(
        encoding="utf-8"
    )
    contract = (
        ROOT
        / "assets/agent-skills/dad-manifest-graph-engineering/references/AGENT_MESH_MANIFEST_CONTRACT.md"
    ).read_text(encoding="utf-8")
    pack = _yaml(MANIFEST_PACK)

    assert "AGENT_MESH_MANIFEST_CONTRACT.md" in skill
    for field in (
        "role_id",
        "why_needed",
        "mission",
        "inputs",
        "dependencies",
        "authority",
        "model_effort_class",
        "writer_checker_relation",
        "acceptance_conditions",
        "stop_conditions",
        "handoff",
    ):
        assert f"`{field}`" in contract
    for disposition in ("reused", "replaced", "split", "added", "removed", "blocked"):
        assert f"`{disposition}`" in contract
    assert "append a new manifest revision" in contract.casefold()
    assert "postflight decomposition grade" in contract.casefold()
    assert pack["routing_policy"]["material_drift_requires_new_mesh_revision"] is True


def test_mesh_template_schema_digest_and_prior_reconciliation_are_valid():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    prior = _mesh()
    assert MESH_VALIDATOR.validate_manifest(prior, schema) == prior["manifest_digest"]
    current = _execution(prior)
    assert MESH_VALIDATOR.validate_manifest(current, schema, prior=prior) == current["manifest_digest"]


def test_mesh_schema_and_digest_fail_closed():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    extra = _mesh()
    extra["unexpected"] = True
    with pytest.raises(jsonschema.ValidationError):
        MESH_VALIDATOR.validate_manifest(extra, schema)
    tampered = _mesh()
    tampered["roles"][0]["mission"] = "Changed without refreshing the digest."
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="digest mismatch"):
        MESH_VALIDATOR.validate_manifest(tampered, schema)


def test_mesh_writer_checker_conflict_fails_closed():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    manifest = _mesh()
    manifest["checker_role_id"] = manifest["writer_role_id"]
    manifest["manifest_digest"] = MESH_VALIDATOR.canonical_digest(manifest)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="distinct"):
        MESH_VALIDATOR.validate_manifest(manifest, schema)


def test_mesh_prior_missing_role_and_reconciliation_conflict_fail_closed():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    prior = _mesh()
    missing = _execution(prior)
    missing["reconciliations"] = missing["reconciliations"][:1]
    missing["manifest_digest"] = MESH_VALIDATOR.canonical_digest(missing)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="missing prior role"):
        MESH_VALIDATOR.validate_manifest(missing, schema, prior=prior)

    conflict = _execution(prior)
    conflict["reconciliations"].append(copy.deepcopy(conflict["reconciliations"][0]))
    conflict["manifest_digest"] = MESH_VALIDATOR.canonical_digest(conflict)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="exactly once"):
        MESH_VALIDATOR.validate_manifest(conflict, schema, prior=prior)


def test_mesh_material_role_drift_requires_explicit_flag_and_new_revision():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    prior = _mesh()
    current = _execution(prior)
    current["roles"][0]["mission"] = "Execute the revised bounded mission."
    current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="drift flag"):
        MESH_VALIDATOR.validate_manifest(current, schema, prior=prior)
    current["reconciliations"][0]["material_drift"] = True
    current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
    MESH_VALIDATOR.validate_manifest(current, schema, prior=prior)


def test_structural_reconciliation_happy_paths_and_material_drift_gate():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    cases = [
        (_mesh(), _replaced_execution, "replaced"),
        (_mesh(), _split_execution, "split"),
        (_prior_with_specialist(), _removed_execution, "removed"),
        (_mesh(), _added_execution, "added"),
    ]
    for prior, factory, disposition in cases:
        current = factory(prior)
        MESH_VALIDATOR.validate_manifest(current, schema, prior=prior)
        row = next(row for row in current["reconciliations"] if row["disposition"] == disposition)
        row["material_drift"] = False
        current["manifest_digest"] = MESH_VALIDATOR.canonical_digest(current)
        with pytest.raises(
            MESH_VALIDATOR.ManifestValidationError,
            match=f"{disposition} reconciliation requires material_drift=true",
        ):
            MESH_VALIDATOR.validate_manifest(current, schema, prior=prior)


def test_replaced_is_exactly_one_to_one_and_split_cannot_preserve_prior_role():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    prior = _mesh()
    replaced = _replaced_execution(prior)
    second = _derived_role(prior["roles"][0], "second-replacement")
    replaced["roles"].append(second)
    replaced["reconciliations"][0]["current_role_ids"].append(second["role_id"])
    replaced["manifest_digest"] = MESH_VALIDATOR.canonical_digest(replaced)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="exactly one new"):
        MESH_VALIDATOR.validate_manifest(replaced, schema, prior=prior)

    split = _split_execution(prior)
    prior_writer = _derived_role(prior["roles"][0], prior["writer_role_id"], "writer")
    split["roles"][0] = prior_writer
    split["writer_role_id"] = prior_writer["role_id"]
    split["roles"][2]["dependencies"][0] = prior_writer["role_id"]
    split["proof_obligations"][0]["owner_role_id"] = prior_writer["role_id"]
    split["reconciliations"][0]["current_role_ids"][0] = prior_writer["role_id"]
    split["manifest_digest"] = MESH_VALIDATOR.canonical_digest(split)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="new child"):
        MESH_VALIDATOR.validate_manifest(split, schema, prior=prior)


def test_proof_obligation_uses_top_level_checker_and_dependencies_are_acyclic():
    schema = json.loads(MESH_SCHEMA.read_text(encoding="utf-8"))
    wrong_checker = _mesh()
    specialist = _derived_role(wrong_checker["roles"][0], "alternate-checker")
    wrong_checker["roles"].append(specialist)
    wrong_checker["proof_obligations"][0]["checker_role_id"] = specialist["role_id"]
    wrong_checker["manifest_digest"] = MESH_VALIDATOR.canonical_digest(wrong_checker)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="top-level checker"):
        MESH_VALIDATOR.validate_manifest(wrong_checker, schema)

    cyclic = _mesh()
    cyclic["roles"][0]["dependencies"] = [cyclic["checker_role_id"]]
    cyclic["manifest_digest"] = MESH_VALIDATOR.canonical_digest(cyclic)
    with pytest.raises(MESH_VALIDATOR.ManifestValidationError, match="cycle"):
        MESH_VALIDATOR.validate_manifest(cyclic, schema)


def test_digital_asset_pack_roles_and_extensible_facets_are_complete():
    pack = _yaml(ASSET_PACK)
    assert {row["role_id"] for row in pack["roles"]} == {
        "digital-asset-discovery-observer",
        "asset-identity-revision-steward",
        "asset-facet-classification-steward",
        "asset-provenance-license-privacy-reviewer",
        "asset-dedupe-variant-synergy-analyst",
        "asset-evidence-value-adoption-analyst",
        "asset-lifecycle-routing-steward",
        "asset-taxonomy-drift-analyst",
        "independent-digital-asset-auditor",
    }
    taxonomy = (
        ROOT / "assets/agent-skills/dad-digital-asset-radar/references/DIGITAL_ASSET_TAXONOMY.md"
    ).read_text(encoding="utf-8")
    for facet in (
        "form",
        "capability_domain",
        "composition",
        "execution_dataflow_role",
        "lifecycle_maturity",
        "authority_trust",
        "sensitivity_release",
        "provenance_license",
        "runtime_platform",
        "freshness_maintenance",
        "reuse_adoption",
        "typed_relationships",
    ):
        assert f"`{facet}`" in taxonomy
    assert "multi-label" in taxonomy
    assert "`dad.digital_asset_taxonomy.v0_1`" in taxonomy
    assert "`unknown`" in taxonomy
    assert "`unclassified`" in taxonomy


def test_agent_skill_library_routes_both_registered_packs():
    library = json.loads((ROOT / "registry/agent-skill-library.json").read_text(encoding="utf-8"))
    skills = {row["skill_id"]: row for row in library["skills"]}

    manifest = skills["skill:dad-manifest-graph-engineering"]
    radar = skills["skill:dad-digital-asset-radar"]
    assert manifest["subagent_pack"] == MANIFEST_PACK.relative_to(ROOT).as_posix()
    assert radar["subagent_pack"] == ASSET_PACK.relative_to(ROOT).as_posix()
    assert manifest["review_status"] == "candidate"
    assert radar["review_status"] == "reviewed"
    assert any("AGENT_MESH_MANIFEST_CONTRACT.md" in value for value in manifest["dependencies"])
    assert any("DIGITAL_ASSET_TAXONOMY.md" in value for value in radar["dependencies"])
