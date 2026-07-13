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


def test_agent_skill_library_validator_passes():
    result = subprocess.run(
        [sys.executable, "scripts/validate_agent_skill_library.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "agent skill library valid" in result.stdout


def test_agent_skill_schema_is_registered_and_registry_conforms():
    schema_registry = load_json("registry/schema-registry.json")["schemas"]
    assert schema_registry["agent_skill_library"] == "schemas/agent-skill-library.schema.json"
    assert (
        schema_registry["agent_skill_checkout_pointer"]
        == "schemas/agent-skill-checkout-pointer.schema.json"
    )
    assert (
        schema_registry["agent_skill_checkout_record"]
        == "schemas/agent-skill-checkout-record.schema.json"
    )
    validate(
        "schemas/agent-skill-library.schema.json",
        load_json("registry/agent-skill-library.json"),
    )


def test_registered_skill_paths_and_lifecycle_templates_exist():
    registry = load_json("registry/agent-skill-library.json")
    skill_ids = [skill["skill_id"] for skill in registry["skills"]]
    assert len(skill_ids) == len(set(skill_ids))

    for skill in registry["skills"]:
        assert (ROOT / skill["path"]).exists(), skill["skill_id"]
        assert (ROOT / skill["entrypoint"]).exists(), skill["skill_id"]
        if skill["status"] == "replaced":
            assert skill["lifecycle"]["replacement_skill_id"]
        for template in skill["lifecycle"]["change_notice_templates"]:
            assert (ROOT / template).exists(), template


def test_personal_hierarchical_agent_mesh_is_a_candidate_global_source_adaptation():
    registry = load_json("registry/agent-skill-library.json")
    skill = next(
        row
        for row in registry["skills"]
        if row["skill_id"] == "skill:personal-hierarchical-agent-mesh"
    )

    assert skill["skill_format"] == "generic_agent_skill"
    assert skill["status"] == "candidate"
    assert skill["review_status"] == "candidate"
    assert "personal-skill-source:personal-hierarchical-agent-mesh" in skill[
        "source_evidence"
    ]
    assert "personal-skill-source:subagent-peer-review-routing" in skill[
        "dependencies"
    ]
    assert set(skill["capabilities"]) >= {
        "plan_mode_mesh_routing",
        "execution_plan_reconciliation",
        "token_efficient_delegation",
    }
    text = (ROOT / skill["entrypoint"]).read_text(encoding="utf-8")
    assert "planning mode" in text
    assert "activation does not require" in text
    assert "delegation." in text
    assert "Ultra always requires explicit human approval" in text


def test_render_agent_skill_checkout_pointer_and_wrapper_handle_spaced_hub_path():
    skill_id = "skill:dad-coding-asset-control-plane"
    pointer = subprocess.run(
        [
            sys.executable,
            "scripts/render_agent_skill_checkout.py",
            "--skill-id",
            skill_id,
            "--hub",
            str(ROOT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert pointer.returncode == 0, pointer.stdout + pointer.stderr
    payload = json.loads(pointer.stdout)
    validate("schemas/agent-skill-checkout-pointer.schema.json", payload)
    assert payload["checked_out_skills"][0]["skill_id"] == skill_id
    assert payload["hub"] == "dad://hub/Digital-Assett-Directory"
    assert payload["source_provenance"]["return_address"] == "dad://mail/outbox"
    assert payload["do_not_copy_full_skills_without_approval"] is True
    assert str(ROOT) not in pointer.stdout
    assert "C:\\Users" not in pointer.stdout

    wrapper = subprocess.run(
        [
            sys.executable,
            "scripts/render_agent_skill_checkout.py",
            "--skill-id",
            skill_id,
            "--mode",
            "wrapper",
            "--hub",
            str(ROOT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert wrapper.returncode == 0, wrapper.stdout + wrapper.stderr
    assert "lightweight wrapper, not a full skill copy" in wrapper.stdout
    assert "Do not copy full DAD skills" in wrapper.stdout
    assert str(ROOT) not in wrapper.stdout
    assert "C:\\Users" not in wrapper.stdout

    internal_pointer = subprocess.run(
        [
            sys.executable,
            "scripts/render_agent_skill_checkout.py",
            "--skill-id",
            skill_id,
            "--hub",
            str(ROOT),
            "--include-local-paths",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert internal_pointer.returncode == 0, internal_pointer.stdout + internal_pointer.stderr
    internal_payload = json.loads(internal_pointer.stdout)
    validate("schemas/agent-skill-checkout-pointer.schema.json", internal_payload)
    assert internal_payload["source_provenance"]["local_paths_included"] is True
    assert internal_payload["local_hub_path"] == str(ROOT)


def test_render_agent_skill_notice_outputs_schema_valid_candidate_mail():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_agent_skill_notice.py",
            "--notice-kind",
            "update",
            "--skill-id",
            "skill:dad-coding-asset-control-plane",
            "--target-repo",
            "repo:example target",
            "--from-version",
            "0.0.9",
            "--hub",
            str(ROOT),
            "--created-at",
            "2026-07-01T00:00:00Z",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    validate("schemas/mail-message.schema.json", payload)
    assert payload["review_status"] == "generated_candidate"
    assert payload["payload"]["command_kind"] == "skill_update_available"
    assert payload["dedupe_key"].startswith("skill-update:")
    assert (
        payload["source_provenance"]["canonical_source_repo"]
        == "dad://hub/Digital-Assett-Directory"
    )
    assert payload["public_release"]["public_release_status"] == "pending_human"
    assert str(ROOT) not in result.stdout
    assert "C:\\Users" not in result.stdout
    assert "SKILL.md" in payload["payload"]["exact_managed_block_or_pointer_content"]


def test_static_agent_skill_pointer_template_conforms():
    validate(
        "schemas/agent-skill-checkout-pointer.schema.json",
        load_json("templates/downstream/AGENT_SKILL_POINTER.template.json"),
    )


def test_check_agent_skill_checkouts_reports_update_candidates(tmp_path):
    record = {
        "schema_version": "0.1.0",
        "checkout_id": "checkout:example",
        "repo_id": "repo:example",
        "repo_alias": "example",
        "repo_visibility": "internal",
        "public_facing": False,
        "skill_id": "skill:dad-coding-asset-control-plane",
        "checked_out_version": "0.0.9",
        "checkout_mode": "pointer",
        "local_pointer_path": ".digital-asset/skills/checkout.json",
        "checked_out_at": "2026-07-01T00:00:00Z",
        "last_checked_at": "2026-07-01T00:00:00Z",
        "source_provenance": {
            "source_repo_id": "dad",
            "source_repo_alias": "Digital-Assett-Directory",
            "source_visibility": "internal",
            "source_registry": "dad://registry/agent-skill-library",
            "return_address": "dad://mail/outbox",
        },
        "review_status": "active",
        "notes": "Fixture checkout.",
    }
    checkout_log = tmp_path / "checkouts.jsonl"
    checkout_log.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_agent_skill_checkouts.py",
            "--checkout-log",
            str(checkout_log),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["records_checked"] == 1
    assert report["notice_candidates"][0]["recommended_notice"] == "update"
    assert report["notice_candidates"][0]["status"] == "update_available"


def test_skill_mail_templates_conform_and_stay_candidate_only():
    mail_schema = load_json("schemas/mail-message.schema.json")
    validator_cls = validator_for(mail_schema)
    validator_cls.check_schema(mail_schema)
    validator = validator_cls(mail_schema)

    for rel in [
        "templates/mail/skill-checkout-request.mail.template.json",
        "templates/mail/skill-update-available.mail.template.json",
        "templates/mail/skill-retirement-notice.mail.template.json",
    ]:
        payload = load_json(rel)
        validator.validate(payload)
        assert payload["review_status"] == "generated_candidate"
        assert payload["payload"]["command_kind"].startswith("skill_")
        text = json.dumps(payload).lower()
        assert "candidate" in text
        assert "full copied assets" in text
