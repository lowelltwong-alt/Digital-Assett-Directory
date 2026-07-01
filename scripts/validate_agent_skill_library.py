from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_KEY = "agent_skill_library"
SCHEMA_REL = "schemas/agent-skill-library.schema.json"
POINTER_SCHEMA_KEY = "agent_skill_checkout_pointer"
POINTER_SCHEMA_REL = "schemas/agent-skill-checkout-pointer.schema.json"
CHECKOUT_RECORD_SCHEMA_KEY = "agent_skill_checkout_record"
CHECKOUT_RECORD_SCHEMA_REL = "schemas/agent-skill-checkout-record.schema.json"
REGISTRY_REL = "registry/agent-skill-library.json"
SKILL_MAIL_TEMPLATES = {
    "templates/mail/skill-checkout-request.mail.template.json",
    "templates/mail/skill-update-available.mail.template.json",
    "templates/mail/skill-retirement-notice.mail.template.json",
}


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validate_with_schema(payload: Any, schema_rel: str, label: str, errors: list[str]) -> None:
    try:
        schema = load_json(schema_rel)
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator_cls(schema).validate(payload)
    except Exception as exc:  # pragma: no cover - command failure path
        errors.append(f"{label} failed schema validation against {schema_rel}: {exc}")


def require_path(rel: str, label: str, errors: list[str]) -> None:
    if not (ROOT / rel).exists():
        errors.append(f"{label} path does not exist: {rel}")


def require_local_evidence_path(value: str, label: str, errors: list[str]) -> None:
    if value.startswith(("http://", "https://")):
        return
    rel = value.split("#", 1)[0]
    if rel.startswith(("docs/", "registry/", "schemas/", "templates/", "assets/", "scripts/")):
        require_path(rel, label, errors)


def require_unique(values: list[str], label: str, errors: list[str]) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        errors.append(f"{label} has duplicate values: {duplicates}")


def validate_skill_frontmatter(entrypoint: str, skill_id: str, errors: list[str]) -> None:
    text = (ROOT / entrypoint).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{skill_id} SKILL.md missing YAML frontmatter")
        return
    frontmatter = text.split("---", 2)[1]
    if "name:" not in frontmatter or "description:" not in frontmatter:
        errors.append(f"{skill_id} SKILL.md frontmatter needs name and description")
    if len(frontmatter.split("description:", 1)[-1].strip()) < 40:
        errors.append(f"{skill_id} SKILL.md description is too short to route reliably")


def main() -> int:
    errors: list[str] = []

    schema_registry = load_json("registry/schema-registry.json")
    if schema_registry.get("schemas", {}).get(SCHEMA_KEY) != SCHEMA_REL:
        errors.append(f"schema registry missing {SCHEMA_KEY}: {SCHEMA_REL}")
    if schema_registry.get("schemas", {}).get(POINTER_SCHEMA_KEY) != POINTER_SCHEMA_REL:
        errors.append(f"schema registry missing {POINTER_SCHEMA_KEY}: {POINTER_SCHEMA_REL}")
    if (
        schema_registry.get("schemas", {}).get(CHECKOUT_RECORD_SCHEMA_KEY)
        != CHECKOUT_RECORD_SCHEMA_REL
    ):
        errors.append(
            f"schema registry missing {CHECKOUT_RECORD_SCHEMA_KEY}: {CHECKOUT_RECORD_SCHEMA_REL}"
        )

    registry = load_json(REGISTRY_REL)
    validate_with_schema(registry, SCHEMA_REL, "agent skill library", errors)
    pointer_template = load_json("templates/downstream/AGENT_SKILL_POINTER.template.json")
    validate_with_schema(
        pointer_template,
        POINTER_SCHEMA_REL,
        "agent skill pointer template",
        errors,
    )

    skills = registry.get("skills", [])
    skill_ids = [skill["skill_id"] for skill in skills]
    require_unique(skill_ids, "agent skill library", errors)

    known_skill_ids = set(skill_ids)
    for skill in skills:
        skill_id = skill["skill_id"]
        require_path(skill["path"], skill_id, errors)
        require_path(skill["entrypoint"], skill_id, errors)
        for evidence in skill["source_evidence"]:
            require_local_evidence_path(evidence, f"{skill_id} evidence", errors)
        for dependency in skill.get("dependencies", []):
            require_local_evidence_path(dependency, f"{skill_id} dependency", errors)
        if skill["skill_format"] == "codex_skill":
            validate_skill_frontmatter(skill["entrypoint"], skill_id, errors)
        if skill["status"] == "replaced" and not skill["lifecycle"]["replacement_skill_id"]:
            errors.append(f"{skill_id} is replaced without replacement_skill_id")
        if skill["status"] == "active" and skill["review_status"] != "reviewed":
            errors.append(f"{skill_id} is active without reviewed status")
        if skill["status"] in {"retired", "replaced"} and not skill["lifecycle"]["retirement_reason"]:
            errors.append(f"{skill_id} is {skill['status']} without retirement_reason")
        replacement = skill["lifecycle"].get("replacement_skill_id", "")
        if replacement and replacement not in known_skill_ids:
            errors.append(f"{skill_id} references unknown replacement skill {replacement}")
        for template in skill["lifecycle"].get("change_notice_templates", []):
            require_path(template, f"{skill_id} change notice", errors)

    require_path("templates/downstream/AGENT_SKILL_POINTER.template.json", "skill pointer", errors)
    require_path("templates/downstream/AGENT_SKILL_MANAGED_BLOCK.md", "skill managed block", errors)

    managed_block = (ROOT / "templates/downstream/AGENT_SKILL_MANAGED_BLOCK.md").read_text(
        encoding="utf-8"
    )
    if "Do not copy full DAD skills" not in managed_block:
        errors.append("AGENT_SKILL_MANAGED_BLOCK.md missing no-full-skill-copy warning")
    if "candidate evidence only" not in managed_block:
        errors.append("AGENT_SKILL_MANAGED_BLOCK.md missing candidate-only mail boundary")

    mail_schema = "schemas/mail-message.schema.json"
    for rel in sorted(SKILL_MAIL_TEMPLATES):
        payload = load_json(rel)
        validate_with_schema(payload, mail_schema, rel, errors)
        command_kind = payload.get("payload", {}).get("command_kind", "")
        if not command_kind.startswith("skill_"):
            errors.append(f"{rel} missing skill command_kind")
        if payload.get("review_status") != "generated_candidate":
            errors.append(f"{rel} must stay generated_candidate")
        if "full copied assets" not in json.dumps(payload):
            errors.append(f"{rel} missing full-copied-assets warning")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"agent skill library valid: {len(skill_ids)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
