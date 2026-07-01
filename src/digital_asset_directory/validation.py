from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema.validators import validator_for


def _load_schema(repo_root: Path, registry: dict[str, Any], name: str) -> dict[str, Any]:
    return json.loads((repo_root / registry["schemas"][name]).read_text(encoding="utf-8"))


def _validate_payload(
    repo_root: Path,
    registry: dict[str, Any],
    schema_name: str,
    payload: Any,
) -> None:
    schema = _load_schema(repo_root, registry, schema_name)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


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
        surfaces = [
            ("dad_need_registry", "registry/dad-needs-registry.json"),
            ("dad_offering_registry", "registry/dad-offerings-registry.json"),
            ("dad_usefulness_methodology", "registry/dad-usefulness-methodology.json"),
            ("asset_recognition_methodology", "registry/asset-recognition-methodology.json"),
            ("harness_discovery_methodology", "registry/harness-discovery-methodology.json"),
        ]
        for schema_name, rel in surfaces:
            payload = json.loads((repo_root / rel).read_text(encoding="utf-8"))
            _validate_payload(repo_root, registry, schema_name, payload)
            checked.append(rel)
        harness_schema = _load_schema(repo_root, registry, "coding_harness")
        harness_validator_cls = validator_for(harness_schema)
        harness_validator_cls.check_schema(harness_schema)
        harness_validator = harness_validator_cls(harness_schema)
        harness_eval_schema = _load_schema(repo_root, registry, "coding_harness_eval")
        harness_eval_validator_cls = validator_for(harness_eval_schema)
        harness_eval_validator_cls.check_schema(harness_eval_schema)
        harness_eval_validator = harness_eval_validator_cls(harness_eval_schema)
        harness_registry = json.loads(
            (repo_root / "registry" / "coding-harness-registry.json").read_text(
                encoding="utf-8"
            )
        )
        harness_ids: list[str] = []
        for harness in harness_registry.get("harnesses", []):
            harness_validator.validate(harness)
            harness_ids.append(harness["harness_id"])
            harness_path = repo_root / harness["path"]
            if not harness_path.exists():
                errors.append(f"Coding harness path missing: {harness['path']}")
                continue
            for folder in ["scripts", "tests-or-evals", "examples"]:
                artifacts = [
                    item
                    for item in (harness_path / folder).glob("*")
                    if item.is_file() and item.name != "README.md"
                ]
                if not artifacts:
                    errors.append(
                        f"Coding harness {folder} has no real artifact: {harness['path']}"
                    )
            harness_json = harness_path / "harness.json"
            if not harness_json.exists():
                errors.append(f"Coding harness missing harness.json: {harness['path']}")
            else:
                harness_payload = json.loads(harness_json.read_text(encoding="utf-8"))
                harness_validator.validate(harness_payload)
                if harness_payload["harness_id"] != harness["harness_id"]:
                    errors.append(
                        "Coding harness registry/id mismatch: "
                        f"{harness['harness_id']} vs {harness_payload['harness_id']}"
                    )
            for eval_path in sorted((harness_path / "tests-or-evals").glob("*.json")):
                eval_payload = json.loads(eval_path.read_text(encoding="utf-8"))
                harness_eval_validator.validate(eval_payload)
                if eval_payload["harness_id"] != harness["harness_id"]:
                    errors.append(
                        "Coding harness eval/id mismatch: "
                        f"{harness['harness_id']} vs {eval_payload['harness_id']}"
                    )
            checked.append(harness["path"])
        if len(harness_ids) != len(set(harness_ids)):
            errors.append("Coding harness registry has duplicate harness_id values")
        offering_registry = json.loads(
            (repo_root / "registry" / "dad-offerings-registry.json").read_text(
                encoding="utf-8"
            )
        )
        offering_ids = [item["offering_id"] for item in offering_registry.get("offerings", [])]
        if len(offering_ids) != len(set(offering_ids)):
            errors.append("DAD offerings registry has duplicate offering_id values")
        for offering in offering_registry.get("offerings", []):
            path = repo_root / offering["path"]
            if not path.exists():
                errors.append(f"DAD offering path missing: {offering['path']}")
        usage_schema = _load_schema(repo_root, registry, "repo_asset_usage")
        usage_validator_cls = validator_for(usage_schema)
        usage_validator_cls.check_schema(usage_schema)
        usage_validator = usage_validator_cls(usage_schema)
        usage_path = repo_root / "processed" / "usage" / "repo-asset-usage.jsonl"
        if usage_path.exists():
            for line_number, line in enumerate(
                usage_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if line.strip():
                    usage_validator.validate(json.loads(line))
                    checked.append("processed/usage/repo-asset-usage.jsonl")
    except Exception as exc:
        errors.append(f"Invalid DAD library or harness registry: {exc}")
    try:
        registry = json.loads(
            (repo_root / "registry" / "schema-registry.json").read_text(encoding="utf-8")
        )
        schema_path = repo_root / registry["schemas"]["control_plane_registry"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(
            (repo_root / "registry" / "control-plane-registry.json").read_text(
                encoding="utf-8"
            )
        )
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator_cls(schema).validate(payload)
        plane_ids = [item["control_plane_id"] for item in payload.get("control_planes", [])]
        if len(plane_ids) != len(set(plane_ids)):
            errors.append("Control-plane registry has duplicate control_plane_id values")
        checked.append("registry/control-plane-registry.json")
    except Exception as exc:
        errors.append(f"Invalid control-plane registry: {exc}")
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
