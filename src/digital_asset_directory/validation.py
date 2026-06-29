from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema.validators import validator_for


def validate_repo(repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    checked: list[str] = []
    required = [
        "README.md",
        "AI_FRONT_DOOR.md",
        "AGENTS.md",
        "MACHINE_NAVIGATION_MANIFEST.json",
        "registry/source-of-truth.json",
        "registry/design-authority.json",
        "registry/identity-layer-registry.json",
        "registry/schema-registry.json",
        "registry/template-registry.json",
        "docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md",
        "config/sources.example.yaml",
        "roadmap/roadmap.yaml",
        "src/digital_asset_directory/cli.py",
    ]
    for rel in required:
        if not (repo_root / rel).exists():
            errors.append(f"Missing required path: {rel}")
        else:
            checked.append(rel)
    for path in sorted((repo_root / "schemas").glob("*.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            validator_for(schema).check_schema(schema)
            checked.append(str(path.relative_to(repo_root)))
        except Exception as exc:
            errors.append(f"Invalid JSON Schema {path.name}: {exc}")
    for path in sorted((repo_root / "registry").glob("*.json")) + [
        repo_root / "MACHINE_NAVIGATION_MANIFEST.json"
    ]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            checked.append(str(path.relative_to(repo_root)))
        except Exception as exc:
            errors.append(f"Invalid JSON {path}: {exc}")
    for path in sorted((repo_root / "config").glob("*.yaml")) + sorted(
        (repo_root / "roadmap").glob("*.yaml")
    ):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
            checked.append(str(path.relative_to(repo_root)))
        except Exception as exc:
            errors.append(f"Invalid YAML {path}: {exc}")
    try:
        registry = json.loads(
            (repo_root / "registry" / "schema-registry.json").read_text(encoding="utf-8")
        )
        for name, rel in registry.get("schemas", {}).items():
            if not (repo_root / rel).exists():
                errors.append(f"Schema registry entry missing ({name}): {rel}")
    except Exception:
        pass
    try:
        registry = json.loads(
            (repo_root / "registry" / "schema-registry.json").read_text(encoding="utf-8")
        )
        schema_path = repo_root / registry["schemas"]["learning_rule"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(
            (repo_root / "registry" / "learning-rule-registry.json").read_text(
                encoding="utf-8"
            )
        )
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        rule_ids: list[str] = []
        for rule in payload.get("rules", []):
            validator.validate(rule)
            rule_ids.append(rule["rule_id"])
        if len(rule_ids) != len(set(rule_ids)):
            errors.append("Learning rule registry has duplicate rule IDs")
        checked.append("registry/learning-rule-registry.json")
    except Exception as exc:
        errors.append(f"Invalid learning rule registry: {exc}")
    try:
        registry = json.loads(
            (repo_root / "registry" / "schema-registry.json").read_text(encoding="utf-8")
        )
        schema_path = repo_root / registry["schemas"]["asset_identity_layer"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(
            (repo_root / "registry" / "identity-layer-registry.json").read_text(
                encoding="utf-8"
            )
        )
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator_cls(schema).validate(payload)
        authority_doc = repo_root / payload["authority_doc"]
        if not authority_doc.exists():
            errors.append(f"Identity layer authority doc missing: {payload['authority_doc']}")
        layers = payload.get("layers", [])
        layer_ids = [layer["id"] for layer in layers]
        layer_orders = [layer["order"] for layer in layers]
        required_layers = {
            "metadata_fingerprint",
            "sha256",
            "chunk_hashes",
            "extracted_text",
            "embeddings",
            "knowledge_graph",
            "audit_log",
        }
        missing_layers = sorted(required_layers - set(layer_ids))
        if missing_layers:
            errors.append(f"Identity layer registry missing required layers: {missing_layers}")
        if len(layer_ids) != len(set(layer_ids)):
            errors.append("Identity layer registry has duplicate layer IDs")
        if len(layer_orders) != len(set(layer_orders)):
            errors.append("Identity layer registry has duplicate layer order values")
        checked.append("registry/identity-layer-registry.json")
    except Exception as exc:
        errors.append(f"Invalid identity layer registry: {exc}")
    proposal_schema_path = repo_root / "schemas" / "proposal.schema.json"
    proposal_examples_dir = repo_root / "examples" / "proposals"
    if proposal_schema_path.exists() and proposal_examples_dir.exists():
        try:
            schema = json.loads(proposal_schema_path.read_text(encoding="utf-8"))
            validator_cls = validator_for(schema)
            validator_cls.check_schema(schema)
            validator = validator_cls(schema)
            for path in sorted(proposal_examples_dir.glob("*.example.json")):
                try:
                    validator.validate(json.loads(path.read_text(encoding="utf-8")))
                    checked.append(str(path.relative_to(repo_root)))
                except Exception as exc:
                    errors.append(f"Invalid proposal example {path.name}: {exc}")
        except Exception as exc:
            errors.append(f"Could not validate proposal examples: {exc}")
    try:
        from .template_library import validate_template_registry

        result = validate_template_registry(repo_root)
        checked.append("registry/template-registry.json")
        checked.extend(
            str((repo_root / row["path"]).relative_to(repo_root))
            for row in json.loads(
                (repo_root / "registry" / "template-registry.json").read_text(
                    encoding="utf-8"
                )
            ).get("templates", [])
            if (repo_root / row["path"]).exists()
        )
        errors.extend(result["errors"])
    except Exception as exc:
        errors.append(f"Invalid template registry: {exc}")
    return {"valid": not errors, "checked_count": len(set(checked)), "errors": errors}
