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
        "registry/schema-registry.json",
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
    return {"valid": not errors, "checked_count": len(set(checked)), "errors": errors}
