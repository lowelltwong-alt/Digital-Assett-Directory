from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema.validators import validator_for

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validate(schema_rel: str, payload: dict) -> None:
    schema = load_json(schema_rel)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def test_coding_asset_control_plane_validator_passes():
    result = subprocess.run(
        [sys.executable, "scripts/validate_coding_asset_control_plane.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "coding asset control plane valid" in result.stdout


def test_coding_asset_schemas_are_registered_and_payloads_conform():
    schema_registry = load_json("registry/schema-registry.json")["schemas"]
    expected = {
        "coding_asset_registry": "schemas/coding-asset-registry.schema.json",
        "coding_tactic": "schemas/coding-tactic.schema.json",
        "preflight_profile_router": "schemas/preflight-profile-router.schema.json",
        "tactic_use_feedback": "schemas/tactic-use-feedback.schema.json",
    }
    for key, rel in expected.items():
        assert schema_registry[key] == rel

    validate(
        "schemas/coding-asset-registry.schema.json",
        load_json("registry/coding-asset-registry.json"),
    )
    validate(
        "schemas/preflight-profile-router.schema.json",
        load_json("registry/preflight-profile-router.json"),
    )
    validate(
        "schemas/tactic-use-feedback.schema.json",
        load_json("templates/tactic-use-feedback.template.json"),
    )
    tactic_schema = "schemas/coding-tactic.schema.json"
    for tactic in load_json("registry/coding-tactics-radar.json")["tactics"]:
        validate(tactic_schema, tactic)


def test_router_references_registered_assets_and_tactics():
    asset_ids = {
        asset["asset_id"] for asset in load_json("registry/coding-asset-registry.json")["assets"]
    }
    tactic_ids = {
        tactic["tactic_id"] for tactic in load_json("registry/coding-tactics-radar.json")["tactics"]
    }

    for route in load_json("registry/preflight-profile-router.json")["routes"]:
        assert set(route["required_preflight_profiles"]).issubset(asset_ids)
        assert set(route["optional_tactic_bundles"]).issubset(asset_ids)
        assert set(route["recommended_tactic_ids"]).issubset(tactic_ids)


def test_control_plane_paths_and_templates_exist():
    for asset in load_json("registry/coding-asset-registry.json")["assets"]:
        assert (ROOT / asset["path"]).exists(), asset["asset_id"]
    for tactic in load_json("registry/coding-tactics-radar.json")["tactics"]:
        assert (ROOT / tactic["minimal_code_example_path"]).exists(), tactic["tactic_id"]
        assert (ROOT / tactic["counterexample_path"]).exists(), tactic["tactic_id"]

    managed_block = (ROOT / "templates/downstream/CODING_ASSET_MANAGED_BLOCK.md").read_text(
        encoding="utf-8"
    )
    assert "--test " in managed_block
    assert "--tests" not in managed_block
    assert "Do not copy full DAD assets" in managed_block


def test_mail_templates_conform_to_mail_schema_and_stay_candidate_only():
    mail_schema = load_json("schemas/mail-message.schema.json")
    validator_cls = validator_for(mail_schema)
    validator_cls.check_schema(mail_schema)
    validator = validator_cls(mail_schema)

    for path in sorted((ROOT / "templates/mail").glob("*.mail.template.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(payload)
        assert payload["review_status"] == "generated_candidate"
        assert payload["sensitivity"] in {"public", "internal"}
        text = json.dumps(payload).lower()
        assert "candidate" in text
        assert "copy full dad asset" in text or "full copied assets" in text
