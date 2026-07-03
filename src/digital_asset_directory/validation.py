from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema.validators import validator_for

from .config import load_config
from .utils import sha256_bytes, sha256_file

MAIL_MESSAGE_TYPES = {
    "lesson_suggestion",
    "asset_suggestion",
    "workflow_suggestion",
    "taxonomy_suggestion",
    "capability_suggestion",
    "governance_notice",
    "inbox_ack",
    "review_decision",
}
EXCEPTION_CAPTURE_CONTRACTS = {
    "failed_command",
    "retry_or_plan_change",
    "postflight_exception",
    "ci_failure",
    "governance_block",
    "review_finding",
    "fix_outcome",
    "dad_recommendation_outcome",
    "backfill_candidate",
}
LOCAL_PATH_FRAGMENTS = (
    "c:/users/",
    "c__users__",
    "/users/",
    "appdata/",
    "git projects/",
    "onedrive/",
)


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


def _hash_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return f"sha256:{sha256_file(path)}"
    parts: list[str] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        try:
            rel = child.relative_to(path).as_posix()
        except ValueError:
            rel = child.name
        parts.append(f"{rel}\0{sha256_file(child)}")
    digest_input = "\n".join(parts).encode("utf-8")
    return f"sha256:{sha256_bytes(digest_input)}"


def _path_identity_hash(path: Path) -> str:
    return f"sha256:{sha256_bytes(path.resolve().as_posix().encode('utf-8'))}"


def _looks_like_local_path_text(text: str) -> bool:
    normalized = text.replace("\\", "/").casefold()
    return (
        bool(normalized.startswith("/"))
        or bool(len(normalized) > 2 and normalized[1:3] == ":/")
        or any(fragment in normalized for fragment in LOCAL_PATH_FRAGMENTS)
    )


def _repo_prefixed_value_contains_local_path(text: str) -> bool:
    if not text.startswith("repo:"):
        return False
    tail = text.removeprefix("repo:").strip()
    return bool(tail) and _looks_like_local_path_text(tail)


def _contains_local_path_ref(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_local_path_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_local_path_ref(item) for item in value)
    if not isinstance(value, str):
        return False
    text = value.strip()
    if _repo_prefixed_value_contains_local_path(text):
        return True
    if text.startswith(("repo-path-sha256:", "path-ref-sha256:", "path-sha256:", "dad://", "repo:")):
        return False
    return _looks_like_local_path_text(text)


def _is_local_absolute_ref(value: str) -> bool:
    text = value.strip()
    if _repo_prefixed_value_contains_local_path(text):
        return True
    if text.startswith(("http://", "https://", "dad://", "repo:", "source-archive-sha256:")):
        return False
    return _looks_like_local_path_text(text)


def _validate_public_safe_source_ref(
    value: str,
    label: str,
    errors: list[str],
) -> None:
    if value.startswith("http://"):
        errors.append(f"{label} uses non-HTTPS source reference: {value}")
    if _is_local_absolute_ref(value):
        errors.append(f"{label} contains local absolute source reference: {value}")


def _source_ref_matches_patterns(ref: str, url_patterns: list[str]) -> bool:
    if not ref.startswith("https://"):
        return False
    normalized = ref.removeprefix("https://").strip("/").casefold()
    return any(pattern.strip("/").casefold() in normalized for pattern in url_patterns)


def _validate_language_frontier_channel(
    value: str,
    label: str,
    errors: list[str],
) -> None:
    if not (
        value.startswith("dad:need:")
        or value.startswith(("registry/", "assets/", "docs/", "templates/"))
    ):
        errors.append(f"{label} uses disallowed output channel: {value}")
    _validate_public_safe_source_ref(value, label, errors)


def _language_registry_semantic_errors(
    language_registry: dict[str, Any],
    trusted_source_registry: dict[str, Any],
    known_language_assets: set[str],
) -> list[str]:
    errors: list[str] = []
    trusted_source_ids = {
        str(item.get("source_id", "")) for item in trusted_source_registry.get("sources", [])
    }
    trusted_sources_by_id = {
        str(item.get("source_id", "")): item
        for item in trusted_source_registry.get("sources", [])
    }
    language_ids = [
        str(item.get("language_id", ""))
        for item in language_registry.get("languages", [])
    ]
    if len(language_ids) != len(set(language_ids)):
        errors.append("Language coding advantage registry has duplicate language_id values")
    for language in language_registry.get("languages", []):
        language_id = str(language.get("language_id", ""))
        language_status = str(language.get("status", ""))
        if language_status == "template" and language.get("recommendable") is not False:
            errors.append(
                "Language coding advantage template row must be recommendable=false: "
                f"{language_id}"
            )
        if language_status != "template" and language.get("recommendable") is not True:
            errors.append(
                "Language coding advantage non-template row must be recommendable=true: "
                f"{language_id}"
            )
        for source_id in language.get("trusted_source_ids", []):
            if source_id not in trusted_source_ids:
                errors.append(
                    "Language coding advantage registry references unknown "
                    f"trusted source {source_id}: {language_id}"
                )
        for asset_id in language.get("primary_assets", []):
            if asset_id not in known_language_assets:
                errors.append(
                    "Language coding advantage registry references unknown "
                    f"primary asset {asset_id}: {language_id}"
                )
        guideline_ids = [
            str(item.get("guideline_id", ""))
            for item in language.get("agent_coding_guidelines", [])
        ]
        if len(guideline_ids) != len(set(guideline_ids)):
            errors.append(
                "Language coding advantage registry has duplicate "
                f"agent_coding_guidelines guideline_id values: {language_id}"
            )
        target_ids = [
            str(item.get("target_id", ""))
            for item in language.get("codebase_watch_targets", [])
        ]
        if len(target_ids) != len(set(target_ids)):
            errors.append(
                "Language coding advantage registry has duplicate "
                f"codebase_watch_targets target_id values: {language_id}"
            )
        for target in language.get("codebase_watch_targets", []):
            target_id = str(target.get("target_id", ""))
            target_source_ids = {str(item) for item in target.get("source_ids", [])}
            for source_id in target_source_ids:
                if source_id not in trusted_source_ids:
                    errors.append(
                        "Language coding advantage watch target references unknown "
                        f"trusted source {source_id}: {language_id}/{target_id}"
                    )
            for ref_record in target.get("example_refs", []):
                ref_source_id = str(ref_record.get("source_id", ""))
                ref = str(ref_record.get("ref", ""))
                review_status = str(ref_record.get("review_status", ""))
                label = (
                    "Language coding advantage watch target "
                    f"{language_id}/{target_id} example_ref"
                )
                if ref_source_id not in target_source_ids:
                    errors.append(f"{label} source {ref_source_id} is not declared on target")
                if ref_source_id not in trusted_sources_by_id:
                    errors.append(f"{label} references unknown trusted source {ref_source_id}")
                    continue
                if language_status == "template":
                    if review_status != "template_placeholder":
                        errors.append(f"{label} template ref must be template_placeholder")
                    if not ref.startswith("replace-with-"):
                        errors.append(f"{label} template ref must use replace-with-* placeholder")
                    continue
                if review_status == "template_placeholder":
                    errors.append(f"{label} placeholder leaked into non-template row: {ref}")
                _validate_public_safe_source_ref(ref, label, errors)
                source = trusted_sources_by_id[ref_source_id]
                patterns = [str(item) for item in source.get("url_patterns", [])]
                if not _source_ref_matches_patterns(ref, patterns):
                    errors.append(
                        f"{label} does not match trusted source {ref_source_id} "
                        f"url_patterns: {ref}"
                    )
        for channel in language.get("frontier_promotion_policy", {}).get(
            "output_channels", []
        ):
            _validate_language_frontier_channel(
                str(channel),
                f"Language coding advantage {language_id} output_channel",
                errors,
            )
    return errors


def _contains_readable_repo_relative_ref(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_readable_repo_relative_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_readable_repo_relative_ref(item) for item in value)
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text.startswith("repo-relative:") and not text.startswith(
        "repo-relative-sha256:"
    )


def _fix_outcome_semantic_errors(fix: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    decision = str(fix.get("decision") or "")
    event_lookup = str(fix.get("event_lookup_status") or "")
    canonical_event_id = str(fix.get("canonical_event_id") or "")
    canonical_lookup = str(fix.get("canonical_event_lookup_status") or "")
    owner = str(fix.get("owner_authority") or "").strip()
    validation_refs = fix.get("validation_refs") or []
    regression_test_refs = fix.get("regression_test_refs") or []
    if not owner:
        errors.append(f"Exception fix outcome missing owner_authority on line {line_number}")
    if decision in {"fixed", "rollback"}:
        if event_lookup != "found_in_lake":
            errors.append(
                "Exception fix outcome claims validated fix for missing event "
                f"on line {line_number}"
            )
        if not validation_refs:
            errors.append(
                "Exception fix outcome fixed/rollback row lacks validation_refs "
                f"on line {line_number}"
            )
        if not regression_test_refs:
            errors.append(
                "Exception fix outcome fixed/rollback row lacks regression_test_refs "
                f"on line {line_number}"
            )
        if fix.get("validation_status") == "validated" and (
            event_lookup != "found_in_lake" or not validation_refs or not regression_test_refs
        ):
            errors.append(
                "Exception fix outcome validation_status is validated without complete "
                f"event, validation, and regression evidence on line {line_number}"
            )
    if decision == "duplicate":
        if not canonical_event_id.startswith("dad:exception-event:"):
            errors.append(
                "Exception fix outcome duplicate row lacks canonical_event_id "
                f"on line {line_number}"
            )
        if canonical_lookup != "found_in_lake":
            errors.append(
                "Exception fix outcome duplicate canonical event is missing "
                f"on line {line_number}"
            )
    if decision in {"accepted_risk", "deferred"} and not str(fix.get("expiry") or "").strip():
        errors.append(
            "Exception fix outcome accepted-risk/deferred row lacks expiry "
            f"on line {line_number}"
        )
    return errors


def _source_provenance_consistency_errors(
    record: dict[str, Any],
    *,
    label: str,
    line_number: int,
) -> list[str]:
    errors: list[str] = []
    provenance = record.get("source_provenance")
    if not isinstance(provenance, dict):
        return errors
    source_repo = str(record.get("source_repo") or "")
    provenance_repo = str(provenance.get("canonical_repo_id") or "")
    if source_repo and provenance_repo and source_repo != provenance_repo:
        errors.append(
            f"{label} source_repo does not match source_provenance.canonical_repo_id "
            f"on line {line_number}"
        )
    source_visibility = str(record.get("source_visibility") or "")
    provenance_visibility = str(provenance.get("source_visibility") or "")
    if source_visibility and provenance_visibility and source_visibility != provenance_visibility:
        errors.append(
            f"{label} source_visibility does not match source_provenance.source_visibility "
            f"on line {line_number}"
        )
    return errors


def _capture_rule_matches_case(rule: dict[str, Any], case: dict[str, Any]) -> bool:
    signals = {str(item) for item in case.get("signals", [])}
    required = {str(item) for item in rule.get("match_signals", [])}
    any_signals = {str(item) for item in rule.get("any_signals", [])}
    suppress = {str(item) for item in rule.get("suppress_signals", [])}
    return (
        required <= signals
        and (not any_signals or bool(any_signals & signals))
        and not bool(suppress & signals)
    )


def _observed_audit_policy_paths(repo_root: Path) -> dict[str, Path]:
    paths = {_path_identity_hash(repo_root): repo_root.resolve()}
    try:
        cfg = load_config(repo_root=repo_root)
    except Exception:
        return paths
    for policy in [*cfg.mail_repos, *cfg.exception_repos, *cfg.enrollment_repos]:
        try:
            resolved = Path(policy.path).resolve()
        except OSError:
            continue
        paths[_path_identity_hash(resolved)] = resolved
    return paths


def _resolve_observed_audit_repo(
    repo_root: Path,
    repo_info: dict[str, Any],
    policy_paths: dict[str, Path],
) -> tuple[Path | None, str]:
    expected_hash = str(repo_info.get("path_hash") or "")
    path_hint = str(repo_info.get("path_hint") or "")
    if path_hint == ".":
        candidate = repo_root.resolve()
        if not expected_hash or _path_identity_hash(candidate) == expected_hash:
            return candidate, ""
        return None, "current repo path hash mismatch"
    if expected_hash and expected_hash in policy_paths:
        candidate = policy_paths[expected_hash]
        if candidate.exists() and candidate.is_dir():
            return candidate, ""
        return None, "reviewed policy path missing"
    hinted = (repo_root / path_hint).resolve()
    if hinted.exists() and hinted.is_dir():
        if not expected_hash or _path_identity_hash(hinted) == expected_hash:
            return hinted, ""
        return None, "path_hint resolved but path hash mismatch"
    return None, "unresolved external audited repo"


def _observed_audit_label(report_path: Path, repo_root: Path, row: dict[str, Any], outbox: dict[str, Any]) -> str:
    repo_info = row.get("repo", {}) if isinstance(row.get("repo"), dict) else {}
    repo_id = str(repo_info.get("repo_id") or repo_info.get("path_hint") or "unknown")
    return f"{report_path.relative_to(repo_root)} {repo_id}:{outbox.get('path', '')}"


def _validate_lesson_graph_contract(
    repo_root: Path,
    registry: dict[str, Any],
    errors: list[str],
    checked: list[str],
) -> None:
    edge_registry_path = repo_root / "registry" / "graph-edge-registry.json"
    edge_registry = json.loads(edge_registry_path.read_text(encoding="utf-8"))
    _validate_payload(repo_root, registry, "graph_edge_registry", edge_registry)
    checked.append("registry/graph-edge-registry.json")
    edge_defs = {row["edge_type"]: row for row in edge_registry.get("edge_types", [])}
    if len(edge_defs) != len(edge_registry.get("edge_types", [])):
        errors.append("Graph edge registry has duplicate edge_type values")

    graph_path = repo_root / "processed" / "learning" / "lesson-graph.json"
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        _validate_payload(repo_root, registry, "lesson_graph", graph)
        checked.append("processed/learning/lesson-graph.json")
        for edge in graph.get("edges", []):
            edge_type = edge.get("edge_type")
            edge_def = edge_defs.get(edge_type)
            if not edge_def:
                errors.append(f"Lesson graph uses unregistered edge type: {edge_type}")
                continue
            if edge.get("edge_class") != edge_def.get("edge_class"):
                errors.append(
                    "Lesson graph edge class mismatch for "
                    f"{edge.get('edge_id')}: {edge.get('edge_class')} "
                    f"!= {edge_def.get('edge_class')}"
                )
            if edge.get("edge_basis") not in edge_def.get("allowed_bases", []):
                errors.append(
                    "Lesson graph edge basis not allowed for "
                    f"{edge.get('edge_id')}: {edge.get('edge_basis')}"
                )
            if edge.get("edge_class") == "inference" and not edge.get("method_version"):
                errors.append(
                    f"Lesson graph inference edge lacks method_version: {edge.get('edge_id')}"
                )
    lesson_schema = _load_schema(repo_root, registry, "lesson_graph")
    schema_edge_enum = set(
        lesson_schema["properties"]["edges"]["items"]["properties"]["edge_type"]["enum"]
    )
    registry_edge_types = set(edge_defs)
    if schema_edge_enum != registry_edge_types:
        errors.append(
            "Lesson graph schema edge enum differs from graph-edge registry: "
            f"schema_only={sorted(schema_edge_enum - registry_edge_types)} "
            f"registry_only={sorted(registry_edge_types - schema_edge_enum)}"
        )

    manifest_path = repo_root / "processed" / "learning" / "lesson-graph-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checked.append("processed/learning/lesson-graph-manifest.json")
        for rel, expected in manifest.get("input_hashes", {}).items():
            actual = _hash_path(repo_root / rel)
            if actual != expected:
                errors.append(
                    "Stale lesson graph manifest input hash "
                    f"{rel}: {expected} != {actual}"
                )


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
            ("trusted_source_registry", "registry/trusted-source-registry.json"),
            ("coding_asset_registry", "registry/coding-asset-registry.json"),
            ("preflight_profile_router", "registry/preflight-profile-router.json"),
            (
                "language_coding_advantage_registry",
                "registry/language-coding-advantage-registry.json",
            ),
            ("non_negotiables", "registry/non-negotiables.json"),
            ("graph_edge_registry", "registry/graph-edge-registry.json"),
            ("exception_event_type_registry", "registry/exception-event-type-registry.json"),
            ("exception_learning_methodology", "registry/exception-learning-methodology.json"),
            (
                "exception_capture_pattern_registry",
                "registry/exception-capture-pattern-registry.json",
            ),
        ]
        for schema_name, rel in surfaces:
            payload = json.loads((repo_root / rel).read_text(encoding="utf-8"))
            _validate_payload(repo_root, registry, schema_name, payload)
            checked.append(rel)
        trusted_source_registry = json.loads(
            (repo_root / "registry" / "trusted-source-registry.json").read_text(
                encoding="utf-8"
            )
        )
        trusted_source_ids = [
            str(item.get("source_id", ""))
            for item in trusted_source_registry.get("sources", [])
        ]
        if len(trusted_source_ids) != len(set(trusted_source_ids)):
            errors.append("Trusted source registry has duplicate source_id values")
        for source in trusted_source_registry.get("sources", []):
            if source.get("language_focus"):
                for field in ["check_cadence", "frontier_watch", "intake_actions"]:
                    if not source.get(field):
                        errors.append(
                            "Language-focused trusted source lacks "
                            f"{field}: {source.get('source_id')}"
                        )
        coding_asset_registry = json.loads(
            (repo_root / "registry" / "coding-asset-registry.json").read_text(
                encoding="utf-8"
            )
        )
        coding_asset_ids = [
            str(item.get("asset_id", ""))
            for item in coding_asset_registry.get("assets", [])
        ]
        if len(coding_asset_ids) != len(set(coding_asset_ids)):
            errors.append("Coding asset registry has duplicate asset_id values")
        for asset in coding_asset_registry.get("assets", []):
            for evidence in asset.get("source_evidence", []):
                _validate_public_safe_source_ref(
                    str(evidence),
                    f"Coding asset {asset.get('asset_id')} source_evidence",
                    errors,
                )
        tactic_schema = _load_schema(repo_root, registry, "coding_tactic")
        tactic_validator_cls = validator_for(tactic_schema)
        tactic_validator_cls.check_schema(tactic_schema)
        tactic_validator = tactic_validator_cls(tactic_schema)
        tactic_registry = json.loads(
            (repo_root / "registry" / "coding-tactics-radar.json").read_text(
                encoding="utf-8"
            )
        )
        tactic_ids: list[str] = []
        for tactic in tactic_registry.get("tactics", []):
            tactic_validator.validate(tactic)
            tactic_ids.append(str(tactic.get("tactic_id", "")))
            for evidence in tactic.get("source_evidence", []):
                _validate_public_safe_source_ref(
                    str(evidence),
                    f"Coding tactic {tactic.get('tactic_id')} source_evidence",
                    errors,
                )
        if len(tactic_ids) != len(set(tactic_ids)):
            errors.append("Coding tactics radar has duplicate tactic_id values")
        checked.append("registry/coding-tactics-radar.json")
        reusable_asset_registry = json.loads(
            (repo_root / "assets" / "asset-registry.json").read_text(encoding="utf-8")
        )
        reusable_asset_ids = {
            str(item.get("asset_id", "")) for item in reusable_asset_registry.get("assets", [])
        }
        offering_registry = json.loads(
            (repo_root / "registry" / "dad-offerings-registry.json").read_text(
                encoding="utf-8"
            )
        )
        offering_ids = {
            str(item.get("offering_id", ""))
            for item in offering_registry.get("offerings", [])
        }
        language_registry = json.loads(
            (repo_root / "registry" / "language-coding-advantage-registry.json").read_text(
                encoding="utf-8"
            )
        )
        known_language_assets = set(coding_asset_ids) | reusable_asset_ids | offering_ids
        errors.extend(
            _language_registry_semantic_errors(
                language_registry,
                trusted_source_registry,
                known_language_assets,
            )
        )
        exception_type_registry = json.loads(
            (repo_root / "registry" / "exception-event-type-registry.json").read_text(
                encoding="utf-8"
            )
        )
        exception_types = [
            item["event_type"] for item in exception_type_registry.get("event_types", [])
        ]
        if len(exception_types) != len(set(exception_types)):
            errors.append("Exception event type registry has duplicate event_type values")
        event_categories = {
            str(item.get("category", ""))
            for item in exception_type_registry.get("event_types", [])
            if isinstance(item, dict) and item.get("category")
        }
        taxonomy_dimensions = exception_type_registry.get("taxonomy_dimensions", {})
        taxonomy_axes = taxonomy_dimensions.get("axes", {}) if isinstance(taxonomy_dimensions, dict) else {}
        required_taxonomy_axes = {
            "origin_surface",
            "detection_mode",
            "impact_domain",
            "learning_route",
            "default_handling",
            "review_priority",
        }
        missing_axes = sorted(required_taxonomy_axes - set(taxonomy_axes))
        if missing_axes:
            errors.append(f"Exception taxonomy dimensions missing axes: {missing_axes}")
        axis_values: dict[str, set[str]] = {
            axis: {str(value) for value in meta.get("values", [])}
            for axis, meta in taxonomy_axes.items()
            if isinstance(meta, dict)
        }
        category_defaults = (
            taxonomy_dimensions.get("category_defaults", {})
            if isinstance(taxonomy_dimensions, dict)
            else {}
        )
        missing_category_defaults = sorted(event_categories - set(category_defaults))
        if missing_category_defaults:
            errors.append(
                "Exception taxonomy dimensions missing category defaults: "
                f"{missing_category_defaults}"
            )
        for category, defaults in category_defaults.items():
            if category not in event_categories:
                errors.append(
                    "Exception taxonomy dimensions define unused category default: "
                    f"{category}"
                )
            if not isinstance(defaults, dict):
                continue
            for axis in required_taxonomy_axes:
                value = str(defaults.get(axis, ""))
                if not value:
                    errors.append(
                        "Exception taxonomy category default lacks "
                        f"{axis}: {category}"
                    )
                    continue
                if axis_values.get(axis) and value not in axis_values[axis]:
                    errors.append(
                        "Exception taxonomy category default uses unknown "
                        f"{axis} value {value}: {category}"
                    )
        classifier = exception_type_registry.get("backfill_classifier", {})
        backfill_rules = classifier.get("rules", []) if isinstance(classifier, dict) else []
        backfill_rule_ids: list[str] = []
        backfill_terms: dict[str, str] = {}
        for rule in backfill_rules:
            if not isinstance(rule, dict):
                continue
            rule_id = str(rule.get("rule_id") or "")
            backfill_rule_ids.append(rule_id)
            event_type = str(rule.get("event_type") or "")
            if event_type not in set(exception_types):
                errors.append(
                    "Exception backfill classifier references unregistered event_type: "
                    f"{event_type}"
                )
            capture_contract = str(rule.get("capture_contract") or "")
            matching_event = next(
                (
                    item
                    for item in exception_type_registry.get("event_types", [])
                    if item.get("event_type") == event_type
                ),
                {},
            )
            if (
                isinstance(matching_event, dict)
                and matching_event
                and capture_contract not in matching_event.get("capture_contracts", [])
                and capture_contract != "backfill_candidate"
            ):
                errors.append(
                    "Exception backfill classifier rule uses capture_contract not "
                    f"declared by event_type {event_type}: {capture_contract}"
                )
            for term in rule.get("terms", []) or []:
                term_key = str(term).casefold()
                existing = backfill_terms.get(term_key)
                if existing and existing != rule_id:
                    errors.append(
                        f"Exception backfill term {term} appears in multiple rules: "
                        f"{existing}, {rule_id}"
                    )
                backfill_terms[term_key] = rule_id
        if len(backfill_rule_ids) != len(set(backfill_rule_ids)):
            errors.append("Exception backfill classifier has duplicate rule_id values")
        capture_pattern_registry = json.loads(
            (repo_root / "registry" / "exception-capture-pattern-registry.json").read_text(
                encoding="utf-8"
            )
        )
        capture_rule_ids = [
            item["rule_id"] for item in capture_pattern_registry.get("rules", [])
        ]
        if len(capture_rule_ids) != len(set(capture_rule_ids)):
            errors.append("Exception capture pattern registry has duplicate rule_id values")
        emitting_rule_ids: set[str] = set()
        for rule in capture_pattern_registry.get("rules", []):
            emit = rule.get("emit", {})
            packet_classes = set(emit.get("packet_classes", []) or [])
            if packet_classes and packet_classes != {"no_packet"}:
                emitting_rule_ids.add(str(rule.get("rule_id", "")))
                required_fields = [
                    str(item).strip() for item in emit.get("required_fields", []) or []
                ]
                if not any(required_fields):
                    errors.append(
                        "Exception capture emitting rule lacks required_fields: "
                        f"{rule.get('rule_id')}"
                    )
        capture_rule_event_types = {
            str(item.get("emit", {}).get("exception_event_type"))
            for item in capture_pattern_registry.get("rules", [])
            if item.get("emit", {}).get("exception_event_type")
        }
        for event_type in sorted(capture_rule_event_types - set(exception_types)):
            errors.append(
                "Exception capture pattern emits unregistered event_type: "
                f"{event_type}"
            )
        capture_rule_mail_types = {
            str(item.get("emit", {}).get("mail_message_type"))
            for item in capture_pattern_registry.get("rules", [])
            if item.get("emit", {}).get("mail_message_type")
        }
        for message_type in sorted(capture_rule_mail_types - MAIL_MESSAGE_TYPES):
            errors.append(
                "Exception capture pattern emits unregistered mail message_type: "
                f"{message_type}"
            )
        capture_rule_contracts = {
            str(item.get("emit", {}).get("capture_contract"))
            for item in capture_pattern_registry.get("rules", [])
            if item.get("emit", {}).get("capture_contract")
        }
        for contract in sorted(capture_rule_contracts - EXCEPTION_CAPTURE_CONTRACTS):
            errors.append(
                "Exception capture pattern emits unknown capture_contract: "
                f"{contract}"
            )
        capture_scenario_schema = _load_schema(
            repo_root, registry, "exception_capture_scenarios"
        )
        capture_scenario_validator_cls = validator_for(capture_scenario_schema)
        capture_scenario_validator_cls.check_schema(capture_scenario_schema)
        capture_scenario_validator = capture_scenario_validator_cls(capture_scenario_schema)
        capture_scenario_path = (
            repo_root
            / "assets"
            / "coding-harnesses"
            / "exception-capture-completeness"
            / "examples"
            / "synthetic-capture-scenarios.json"
        )
        if capture_scenario_path.exists():
            capture_scenarios = json.loads(
                capture_scenario_path.read_text(encoding="utf-8")
            )
            capture_scenario_validator.validate(capture_scenarios)
            if capture_scenarios.get("target_registry") != (
                "registry/exception-capture-pattern-registry.json"
            ):
                errors.append(
                    "Exception capture scenarios target unexpected registry: "
                    f"{capture_scenarios.get('target_registry')}"
                )
            scenario_families = {
                item.get("pattern_family") for item in capture_scenarios.get("cases", [])
            }
            required_families = set(capture_scenarios.get("required_pattern_families", []))
            missing_scenario_families = sorted(required_families - scenario_families)
            if missing_scenario_families:
                errors.append(
                    "Exception capture scenarios missing required families: "
                    f"{missing_scenario_families}"
                )
            registry_families = {
                item.get("pattern_family")
                for item in capture_pattern_registry.get("rules", [])
            }
            unknown_scenario_families = sorted(scenario_families - registry_families)
            if unknown_scenario_families:
                errors.append(
                    "Exception capture scenarios use families with no capture rule: "
                    f"{unknown_scenario_families}"
                )
            scenario_rule_ids = {
                str(rule.get("rule_id", ""))
                for rule in capture_pattern_registry.get("rules", [])
                for case in capture_scenarios.get("cases", [])
                if _capture_rule_matches_case(rule, case)
            }
            missing_rule_scenarios = sorted(emitting_rule_ids - scenario_rule_ids)
            if missing_rule_scenarios:
                errors.append(
                    "Exception capture emitting rules have no matching synthetic scenario: "
                    f"{missing_rule_scenarios}"
                )
            expected_event_types: set[str] = set()
            expected_mail_types: set[str] = set()
            expected_contracts: set[str] = set()
            for item in capture_scenarios.get("cases", []):
                expected = item.get("expected", {})
                expected_event_types.update(expected.get("event_types", []))
                expected_mail_types.update(expected.get("mail_message_types", []))
                expected_contracts.update(expected.get("capture_contracts", []))
            for event_type in sorted(expected_event_types - set(exception_types)):
                errors.append(
                    "Exception capture scenario expects unregistered event_type: "
                    f"{event_type}"
                )
            for message_type in sorted(expected_mail_types - MAIL_MESSAGE_TYPES):
                errors.append(
                    "Exception capture scenario expects unknown mail message_type: "
                    f"{message_type}"
                )
            for contract in sorted(expected_contracts - EXCEPTION_CAPTURE_CONTRACTS):
                errors.append(
                    "Exception capture scenario expects unknown capture_contract: "
                    f"{contract}"
                )
            checked.append(str(capture_scenario_path.relative_to(repo_root)))
        exception_event_schema = _load_schema(repo_root, registry, "exception_event")
        exception_event_validator_cls = validator_for(exception_event_schema)
        exception_event_validator_cls.check_schema(exception_event_schema)
        exception_event_validator = exception_event_validator_cls(exception_event_schema)
        exception_lake_path = repo_root / "processed" / "exceptions" / "lake" / "events.jsonl"
        if exception_lake_path.exists():
            for line_number, line in enumerate(
                exception_lake_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                event = json.loads(line)
                exception_event_validator.validate(event)
                if _contains_local_path_ref(event):
                    errors.append(
                        "Exception lake event contains local path-like metadata "
                        f"on line {line_number}"
                    )
                if _contains_readable_repo_relative_ref(event):
                    errors.append(
                        "Exception lake event contains readable repo-relative path "
                        f"metadata on line {line_number}"
                    )
                errors.extend(
                    _source_provenance_consistency_errors(
                        event,
                        label="Exception lake event",
                        line_number=line_number,
                    )
                )
                if event.get("event_type") not in set(exception_types):
                    errors.append(
                        "Exception lake event uses unregistered event_type "
                        f"on line {line_number}: {event.get('event_type')}"
                    )
                checked.append("processed/exceptions/lake/events.jsonl")
        exception_fix_schema = _load_schema(repo_root, registry, "exception_fix_outcome")
        exception_fix_validator_cls = validator_for(exception_fix_schema)
        exception_fix_validator_cls.check_schema(exception_fix_schema)
        exception_fix_validator = exception_fix_validator_cls(exception_fix_schema)
        fix_path = repo_root / "processed" / "exceptions" / "fix-outcomes" / "outcomes.jsonl"
        if fix_path.exists():
            for line_number, line in enumerate(
                fix_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if line.strip():
                    fix = json.loads(line)
                    exception_fix_validator.validate(fix)
                    if _contains_local_path_ref(fix):
                        errors.append(
                            "Exception fix outcome contains local path-like metadata "
                            f"on line {line_number}"
                        )
                    if _contains_readable_repo_relative_ref(fix):
                        errors.append(
                            "Exception fix outcome contains readable repo-relative path "
                            f"metadata on line {line_number}"
                        )
                    errors.extend(
                        _source_provenance_consistency_errors(
                            fix,
                            label="Exception fix outcome",
                            line_number=line_number,
                        )
                    )
                    errors.extend(_fix_outcome_semantic_errors(fix, line_number))
                    checked.append("processed/exceptions/fix-outcomes/outcomes.jsonl")
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
        context_pack_schema = _load_schema(repo_root, registry, "context_pack")
        context_pack_validator_cls = validator_for(context_pack_schema)
        context_pack_validator_cls.check_schema(context_pack_schema)
        context_pack_validator = context_pack_validator_cls(context_pack_schema)
        for session_path in sorted((repo_root / "state" / "agent_sessions").glob("*.json")):
            session = json.loads(session_path.read_text(encoding="utf-8"))
            if "context_pack" in session:
                context_pack_validator.validate(session["context_pack"])
                checked.append(str(session_path.relative_to(repo_root)))
        for report_path in [
            *sorted((repo_root / "processed" / "reports").glob("*.json")),
            *sorted((repo_root / "processed" / "harnesses").glob("*.json")),
        ]:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            ref = payload.get("methodology_ref")
            expected = payload.get("methodology_hash")
            if ref and not expected:
                errors.append(
                    f"Methodology report missing hash: {report_path.relative_to(repo_root)}"
                )
                checked.append(str(report_path.relative_to(repo_root)))
            elif ref and expected:
                methodology_path = repo_root / str(ref)
                if methodology_path.exists():
                    actual = f"sha256:{sha256_file(methodology_path)}"
                    if actual != expected:
                        errors.append(
                            f"Stale methodology report {report_path.relative_to(repo_root)}: "
                            f"{expected} != {actual}"
                        )
                checked.append(str(report_path.relative_to(repo_root)))
            for input_ref, input_hash in payload.get("input_hashes", {}).items():
                input_path = repo_root / str(input_ref)
                if input_path.exists():
                    actual = f"sha256:{sha256_file(input_path)}"
                    if actual != input_hash:
                        errors.append(
                            f"Stale report input hash {report_path.relative_to(repo_root)} "
                            f"{input_ref}: {input_hash} != {actual}"
                        )
                checked.append(str(report_path.relative_to(repo_root)))
            if payload.get("audit_id") == "dad:exception-capture-observed-audit":
                policy_paths = _observed_audit_policy_paths(repo_root)
                for row in payload.get("repos", []):
                    repo_info = row.get("repo", {})
                    if not isinstance(repo_info, dict):
                        repo_info = {}
                    audited_repo, resolve_error = _resolve_observed_audit_repo(
                        repo_root,
                        repo_info,
                        policy_paths,
                    )
                    if audited_repo is None:
                        errors.append(
                            f"Observed audit stale for {report_path.relative_to(repo_root)}: "
                            f"{resolve_error} {repo_info.get('repo_id') or repo_info.get('path_hint')}"
                        )
                        continue
                    for outbox in row.get("outboxes", {}).values():
                        if not outbox.get("exists") or not outbox.get("content_hash"):
                            continue
                        observed_path = audited_repo / str(outbox.get("path", ""))
                        if not observed_path.exists() or not observed_path.is_file():
                            errors.append(
                                f"Observed audit stale for "
                                f"{_observed_audit_label(report_path, repo_root, row, outbox)}: "
                                "missing observed outbox"
                            )
                            continue
                        actual = f"sha256:{sha256_file(observed_path)}"
                        if actual != outbox.get("content_hash"):
                            errors.append(
                                f"Observed audit stale for "
                                f"{_observed_audit_label(report_path, repo_root, row, outbox)}: "
                                f"{outbox.get('content_hash')} != {actual}"
                            )
        _validate_lesson_graph_contract(repo_root, registry, errors, checked)
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
