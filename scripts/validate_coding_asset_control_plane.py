from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema.validators import validator_for


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCHEMA_KEYS = {
    "coding_asset_registry": "schemas/coding-asset-registry.schema.json",
    "coding_harness": "schemas/coding-harness.schema.json",
    "coding_harness_eval": "schemas/coding-harness-eval.schema.json",
    "coding_tactic": "schemas/coding-tactic.schema.json",
    "language_coding_advantage_registry": "schemas/language-coding-advantage-registry.schema.json",
    "preflight_profile_router": "schemas/preflight-profile-router.schema.json",
    "tactic_use_feedback": "schemas/tactic-use-feedback.schema.json",
}


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validate_with_schema(payload: Any, schema_rel: str, label: str, errors: list[str]) -> None:
    try:
        schema = load_json(schema_rel)
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator_cls(schema).validate(payload)
    except Exception as exc:  # pragma: no cover - exercised by command failures
        errors.append(f"{label} failed schema validation against {schema_rel}: {exc}")


def require_unique(values: list[str], label: str, errors: list[str]) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        errors.append(f"{label} has duplicate values: {duplicates}")


def require_path(rel: str, label: str, errors: list[str]) -> None:
    if not (ROOT / rel).exists():
        errors.append(f"{label} path does not exist: {rel}")


def require_local_evidence_path(value: str, label: str, errors: list[str]) -> None:
    if value.startswith(("dad://", "source-archive-sha256:", "https://")):
        return
    if value.startswith("http://"):
        errors.append(f"{label} evidence must use https or dad:// refs, not http: {value}")
        return
    if len(value) > 2 and value[1:3] in {":/", ":\\"}:
        errors.append(f"{label} evidence contains local absolute path: {value}")
        return
    rel = value.split("#", 1)[0]
    if rel.startswith(("docs/", "registry/", "schemas/", "templates/", "assets/", "examples/", "scripts/")):
        require_path(rel, label, errors)


def source_ref_matches_patterns(ref: str, url_patterns: list[str]) -> bool:
    if not ref.startswith("https://"):
        return False
    parsed = urlparse(ref)
    ref_host = (parsed.hostname or "").casefold()
    ref_path = parsed.path.strip("/").casefold()
    for pattern in url_patterns:
        pattern_text = pattern.removeprefix("https://").strip("/").casefold()
        pattern_host, _, pattern_path = pattern_text.partition("/")
        host_matches = ref_host == pattern_host or ref_host.endswith(f".{pattern_host}")
        if not host_matches:
            continue
        if pattern_path and not ref_path.startswith(pattern_path):
            continue
        return True
    return False


def require_language_output_channel(value: str, label: str, errors: list[str]) -> None:
    if not (
        value.startswith("dad:need:")
        or value.startswith(("registry/", "assets/", "docs/", "templates/"))
    ):
        errors.append(f"{label} uses disallowed output channel: {value}")
    require_local_evidence_path(value, label, errors)


def main() -> int:
    errors: list[str] = []

    schema_registry = load_json("registry/schema-registry.json")
    asset_registry = load_json("registry/coding-asset-registry.json")
    tactic_registry = load_json("registry/coding-tactics-radar.json")
    router = load_json("registry/preflight-profile-router.json")
    trusted_sources = load_json("registry/trusted-source-registry.json")
    language_registry = load_json("registry/language-coding-advantage-registry.json")
    harness_registry = load_json("registry/coding-harness-registry.json")
    dad_offerings = load_json("registry/dad-offerings-registry.json")
    reusable_assets = load_json("assets/asset-registry.json")
    feedback_template = load_json("templates/tactic-use-feedback.template.json")

    registered_schemas = schema_registry.get("schemas", {})
    for key, rel in REQUIRED_SCHEMA_KEYS.items():
        if registered_schemas.get(key) != rel:
            errors.append(f"schema registry missing {key}: {rel}")

    validate_with_schema(
        asset_registry,
        "schemas/coding-asset-registry.schema.json",
        "coding asset registry",
        errors,
    )
    validate_with_schema(
        router,
        "schemas/preflight-profile-router.schema.json",
        "preflight profile router",
        errors,
    )
    validate_with_schema(
        trusted_sources,
        "schemas/trusted-source-registry.schema.json",
        "trusted source registry",
        errors,
    )
    validate_with_schema(
        language_registry,
        "schemas/language-coding-advantage-registry.schema.json",
        "language coding advantage registry",
        errors,
    )
    validate_with_schema(
        feedback_template,
        "schemas/tactic-use-feedback.schema.json",
        "tactic use feedback template",
        errors,
    )

    asset_ids = [asset["asset_id"] for asset in asset_registry.get("assets", [])]
    tactic_ids = [tactic["tactic_id"] for tactic in tactic_registry.get("tactics", [])]
    harness_ids = [harness["harness_id"] for harness in harness_registry.get("harnesses", [])]
    route_ids = [route["route_id"] for route in router.get("routes", [])]

    require_unique(asset_ids, "coding asset registry", errors)
    require_unique(tactic_ids, "coding tactics radar", errors)
    require_unique(harness_ids, "coding harness registry", errors)
    require_unique(route_ids, "preflight profile router", errors)

    known_assets = set(asset_ids)
    known_tactics = set(tactic_ids)
    offering_ids = {offering["offering_id"] for offering in dad_offerings.get("offerings", [])}
    reusable_asset_ids = {asset["asset_id"] for asset in reusable_assets.get("assets", [])}
    known_related_assets = (
        known_assets
        | reusable_asset_ids
        | offering_ids
        | set(harness_ids)
    )
    known_language_assets = (
        known_assets
        | reusable_asset_ids
        | offering_ids
    )
    trusted_source_ids = {source["source_id"] for source in trusted_sources.get("sources", [])}
    trusted_sources_by_id = {
        source["source_id"]: source for source in trusted_sources.get("sources", [])
    }

    for asset in asset_registry.get("assets", []):
        require_path(asset["path"], f"asset {asset['asset_id']}", errors)
        for evidence in asset["source_evidence"]:
            require_local_evidence_path(evidence, f"asset {asset['asset_id']} evidence", errors)
        for related_asset in asset.get("related_assets", []):
            if related_asset not in known_related_assets:
                errors.append(
                    f"asset {asset['asset_id']} references unknown related asset "
                    f"{related_asset}"
                )

    harness_schema_rel = "schemas/coding-harness.schema.json"
    harness_eval_schema_rel = "schemas/coding-harness-eval.schema.json"
    for harness in harness_registry.get("harnesses", []):
        harness_id = harness["harness_id"]
        validate_with_schema(harness, harness_schema_rel, f"harness {harness_id}", errors)
        require_path(harness["path"], f"harness {harness_id}", errors)
        harness_path = ROOT / harness["path"]
        harness_json_path = harness_path / "harness.json"
        if harness_json_path.exists():
            harness_payload = load_json(str(harness_json_path.relative_to(ROOT)).replace("\\", "/"))
            validate_with_schema(
                harness_payload,
                harness_schema_rel,
                f"harness package {harness_id}",
                errors,
            )
            if harness_payload.get("harness_id") != harness_id:
                errors.append(
                    f"harness package id mismatch: {harness_id} != "
                    f"{harness_payload.get('harness_id')}"
                )
        else:
            errors.append(f"harness {harness_id} missing harness.json")
        for folder in ["scripts", "tests-or-evals", "examples"]:
            folder_path = harness_path / folder
            if not folder_path.exists():
                errors.append(f"harness {harness_id} missing {folder}/")
                continue
            real_artifacts = [
                item for item in folder_path.glob("*") if item.is_file() and item.name != "README.md"
            ]
            if not real_artifacts:
                errors.append(f"harness {harness_id} has no real artifact in {folder}/")
        for eval_path in sorted((harness_path / "tests-or-evals").glob("*.json")):
            eval_payload = load_json(str(eval_path.relative_to(ROOT)).replace("\\", "/"))
            validate_with_schema(
                eval_payload,
                harness_eval_schema_rel,
                f"harness eval {harness_id} {eval_path.name}",
                errors,
            )
            if eval_payload.get("harness_id") != harness_id:
                errors.append(
                    f"harness eval/id mismatch: {harness_id} != "
                    f"{eval_payload.get('harness_id')}"
                )

    for language in language_registry.get("languages", []):
        language_id = language["language_id"]
        language_status = language["status"]
        if language_status == "template" and language.get("recommendable") is not False:
            errors.append(f"language {language_id} template row must be recommendable=false")
        if language_status != "template" and language.get("recommendable") is not True:
            errors.append(f"language {language_id} non-template row must be recommendable=true")
        for source_id in language["trusted_source_ids"]:
            if source_id not in trusted_source_ids:
                errors.append(
                    f"language {language_id} references unknown trusted source {source_id}"
                )
        for asset_id in language["primary_assets"]:
            if asset_id not in known_language_assets:
                errors.append(
                    f"language {language_id} references unknown primary asset {asset_id}"
                )
        for harness_route in language.get("harness_routes", []):
            harness_id = str(harness_route.get("harness_id", ""))
            if harness_id != "candidate-required" and harness_id not in harness_ids:
                errors.append(
                    f"language {language_id} references unknown harness route {harness_id}"
                )
        require_unique(
            [item["guideline_id"] for item in language["agent_coding_guidelines"]],
            f"language {language_id} agent coding guidelines",
            errors,
        )
        require_unique(
            [item["operation_id"] for item in language["ai_overlooked_operations"]],
            f"language {language_id} overlooked operations",
            errors,
        )
        require_unique(
            [item["target_id"] for item in language["codebase_watch_targets"]],
            f"language {language_id} codebase watch targets",
            errors,
        )
        for operation in language["ai_overlooked_operations"]:
            for source_id in operation["source_ids"]:
                if source_id not in trusted_source_ids:
                    errors.append(
                        f"language {language_id} operation {operation['operation_id']} "
                        f"references unknown trusted source {source_id}"
                    )
            for route in operation["route_to"]:
                if route.startswith("registry/trusted-source-registry.json"):
                    errors.append(
                        f"language {language_id} operation {operation['operation_id']} "
                        "routes directly to trusted-source registry; use dad:need, harness, "
                        "or reviewed asset docs instead"
                    )
                require_language_output_channel(
                    route,
                    f"language {language_id} operation {operation['operation_id']} route",
                    errors,
                )
        for target in language["codebase_watch_targets"]:
            target_source_ids = set(target["source_ids"])
            for source_id in target["source_ids"]:
                if source_id not in trusted_source_ids:
                    errors.append(
                        f"language {language_id} watch target {target['target_id']} "
                        f"references unknown trusted source {source_id}"
                    )
            for example in target["example_refs"]:
                ref_source_id = example["source_id"]
                ref = example["ref"]
                label = (
                    f"language {language_id} watch target {target['target_id']} "
                    f"example ref"
                )
                if ref_source_id not in target_source_ids:
                    errors.append(
                        f"{label} source {ref_source_id} is not declared on target"
                    )
                if ref_source_id not in trusted_sources_by_id:
                    errors.append(f"{label} references unknown trusted source {ref_source_id}")
                    continue
                if language_status == "template":
                    if example["review_status"] != "template_placeholder":
                        errors.append(f"{label} template ref must be template_placeholder")
                    if not ref.startswith("replace-with-"):
                        errors.append(f"{label} template ref must use replace-with-* placeholder")
                    continue
                if example["review_status"] == "template_placeholder":
                    errors.append(f"{label} placeholder leaked into non-template row: {ref}")
                require_local_evidence_path(ref, label, errors)
                source = trusted_sources_by_id[ref_source_id]
                if not source_ref_matches_patterns(
                    ref,
                    [str(item) for item in source.get("url_patterns", [])],
                ):
                    errors.append(
                        f"{label} does not match trusted source {ref_source_id} "
                        f"url_patterns: {ref}"
                    )
        for channel in language["frontier_promotion_policy"]["output_channels"]:
            require_language_output_channel(
                channel,
                f"language {language_id} output_channel",
                errors,
            )

    for tactic in tactic_registry.get("tactics", []):
        validate_with_schema(
            tactic,
            "schemas/coding-tactic.schema.json",
            f"tactic {tactic.get('tactic_id', '<missing>')}",
            errors,
        )
        require_path(tactic["minimal_code_example_path"], tactic["tactic_id"], errors)
        require_path(tactic["counterexample_path"], tactic["tactic_id"], errors)
        for evidence in tactic["source_evidence"]:
            require_local_evidence_path(evidence, f"tactic {tactic['tactic_id']} evidence", errors)
        if tactic["status"] == "promoted" and tactic["review_status"] != "reviewed":
            errors.append(f"{tactic['tactic_id']} is promoted without reviewed status")
        if tactic["maturity"] == "confirmed_underused":
            evidence_text = " ".join(tactic["source_evidence"]).lower()
            if "measurement" not in evidence_text and "study" not in evidence_text:
                errors.append(
                    f"{tactic['tactic_id']} claims confirmed underuse without measurement evidence"
                )

    for route in router.get("routes", []):
        for profile in route["required_preflight_profiles"]:
            if profile not in known_assets:
                errors.append(f"{route['route_id']} references unknown asset {profile}")
        for asset_id in route["optional_tactic_bundles"]:
            if asset_id not in known_assets:
                errors.append(f"{route['route_id']} references unknown optional asset {asset_id}")
        for tactic_id in route["recommended_tactic_ids"]:
            if tactic_id not in known_tactics:
                errors.append(f"{route['route_id']} references unknown tactic {tactic_id}")

    pointer = load_json("templates/downstream/AI_ASSETS_POINTER.template.json")
    for asset in pointer.get("assets", []):
        if asset["asset_id"] not in known_assets:
            errors.append(f"downstream pointer references unknown asset {asset['asset_id']}")

    managed_block = (ROOT / "templates/downstream/CODING_ASSET_MANAGED_BLOCK.md").read_text(
        encoding="utf-8"
    )
    if "--tests" in managed_block:
        errors.append("CODING_ASSET_MANAGED_BLOCK.md uses invalid --tests option; use --test")
    if "Do not copy full DAD assets" not in managed_block:
        errors.append("CODING_ASSET_MANAGED_BLOCK.md missing no-full-asset-copy warning")

    mail_schema = "schemas/mail-message.schema.json"
    for rel in sorted(Path("templates/mail").glob("*.mail.template.json")):
        payload = load_json(str(rel).replace("\\", "/"))
        validate_with_schema(payload, mail_schema, str(rel), errors)
        command_kind = payload.get("payload", {}).get("command_kind", "")
        if not command_kind:
            errors.append(f"{rel} missing payload.command_kind")
        if payload.get("sensitivity") not in {"public", "internal"}:
            errors.append(f"{rel} uses disallowed default sensitivity")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(
        "coding asset control plane valid: "
        f"{len(asset_ids)} assets, {len(tactic_ids)} tactics, "
        f"{len(route_ids)} routes, {len(language_registry.get('languages', []))} languages"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
