from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema.validators import validator_for

from .config import load_config
from .graph_surfaces import resolve_graph_surface_path
from .transport import DATA_PLANE_PATHS, data_relative_path
from .exception_capture import (
    BACKFILL_ROUTE_REQUIRED_FIELDS,
    audit_observed_capture_repo,
    build_phase6_machine_evidence_summary,
    build_exception_capture_gap_review_queue,
    build_exception_capture_remediation_plan,
    build_exception_backfill_wave_plan,
    capture_route_registry_from_registries,
    load_capture_pattern_registry,
    observed_capture_audit_gap_count,
)
from .utils import sha256_bytes, sha256_file, sha256_text_file_lf

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
EXCEPTION_TAXONOMY_AXIS_KEYS = (
    "origin_surface",
    "detection_mode",
    "impact_domain",
    "learning_route",
    "default_handling",
    "review_priority",
)
LOCAL_PATH_FRAGMENTS = (
    "c:/users/",
    "c__users__",
    "/users/",
    "appdata/",
    "git projects/",
    "onedrive/",
)
GENERATED_LESSON_INDEX_DIRS = {"by-repo", "by-capability"}
TEXT_LF_NORMALIZED_HASH_POLICY = "text-lf-normalized-v1"


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


def _file_hash_for_policy(path: Path, hash_policy: str | None = None) -> str:
    if hash_policy == TEXT_LF_NORMALIZED_HASH_POLICY:
        return sha256_text_file_lf(path)
    return sha256_file(path)


def _hash_path(path: Path, hash_policy: str | None = None) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return f"sha256:{_file_hash_for_policy(path, hash_policy)}"
    parts: list[str] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        try:
            rel = child.relative_to(path).as_posix()
        except ValueError:
            rel = child.name
        if path.name == "lessons" and rel.split("/", 1)[0] in GENERATED_LESSON_INDEX_DIRS:
            continue
        parts.append(f"{rel}\0{_file_hash_for_policy(child, hash_policy)}")
    digest_input = "\n".join(parts).encode("utf-8")
    return f"sha256:{sha256_bytes(digest_input)}"


def _module_ref_exists(module_ref: str) -> bool:
    module_name, separator, attr_name = module_ref.rpartition(".")
    if not separator or not module_name or not attr_name:
        return False
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return False
    return hasattr(module, attr_name)


def _validate_graph_surface_registry_contract(
    repo_root: Path,
    registry: dict[str, Any],
    errors: list[str],
    checked: list[str],
) -> None:
    surface_registry_path = repo_root / "registry" / "graph-surface-registry.json"
    if not surface_registry_path.exists():
        errors.append("Missing graph surface registry: registry/graph-surface-registry.json")
        return
    payload = json.loads(surface_registry_path.read_text(encoding="utf-8"))
    _validate_payload(repo_root, registry, "graph_surface_registry", payload)
    checked.append("registry/graph-surface-registry.json")
    surfaces = payload.get("surfaces", [])
    surface_ids = [str(surface.get("surface_id", "")) for surface in surfaces]
    if len(surface_ids) != len(set(surface_ids)):
        errors.append("Graph surface registry has duplicate surface_id values")

    for surface in surfaces:
        surface_id = str(surface.get("surface_id", ""))
        builder = surface.get("builder", {})
        availability = str(builder.get("availability", ""))
        command = str(builder.get("command", ""))
        module_ref = str(builder.get("module", ""))
        if availability == "wired":
            if command.startswith("planned:"):
                errors.append(f"Graph surface {surface_id} has planned command but is wired")
            if not _module_ref_exists(module_ref):
                errors.append(
                    f"Graph surface {surface_id} builder module is not importable: {module_ref}"
                )
        for schema_ref in surface.get("schema_refs", []):
            schema_path = repo_root / str(schema_ref)
            if not schema_path.exists():
                errors.append(
                    f"Graph surface {surface_id} schema ref missing: {schema_ref}"
                )
        for source_input in surface.get("source_inputs", []):
            kind = str(source_input.get("kind", ""))
            ref = str(source_input.get("ref", ""))
            required = bool(source_input.get("required", False))
            if kind == "data_surface":
                if ref not in DATA_PLANE_PATHS:
                    errors.append(
                        f"Graph surface {surface_id} uses unknown data surface: {ref}"
                    )
                continue
            if kind == "registry_path" and not ref.startswith("registry/"):
                errors.append(
                    f"Graph surface {surface_id} registry input is outside registry/: {ref}"
                )
            if kind == "schema_path" and not ref.startswith("schemas/"):
                errors.append(
                    f"Graph surface {surface_id} schema input is outside schemas/: {ref}"
                )
            if required and not (repo_root / ref).exists():
                errors.append(f"Graph surface {surface_id} required input missing: {ref}")
        outputs = surface.get("outputs", {})
        for key in ("manifest_logical_path", "body_logical_path"):
            value = str(outputs.get(key, ""))
            if value.startswith(("processed/", "raw/", "state/", "audit/")):
                errors.append(
                    f"Graph surface {surface_id} {key} must be data-plane logical, not {value}"
                )


def _repo_policy_identity_errors(label: str, policies: list[Any]) -> list[str]:
    errors: list[str] = []
    by_id: dict[str, list[str]] = {}
    by_alias: dict[str, list[str]] = {}
    by_path: dict[str, list[str]] = {}
    for policy in policies:
        policy_id = str(getattr(policy, "id", "") or "").strip()
        alias = str(getattr(policy, "alias", "") or "").strip()
        try:
            path_key = Path(getattr(policy, "path")).resolve(strict=False).as_posix()
        except (TypeError, OSError):
            path_key = ""
        if policy_id:
            by_id.setdefault(policy_id.casefold(), []).append(policy_id)
        if alias:
            by_alias.setdefault(alias.casefold(), []).append(
                f"{alias} ({policy_id or 'missing-id'})"
            )
        if path_key:
            by_path.setdefault(path_key.casefold(), []).append(policy_id or "missing-id")
    for key, values in sorted(by_id.items()):
        if len(values) > 1:
            errors.append(f"{label} has duplicate repo id: {key}")
    for key, values in sorted(by_alias.items()):
        if len(values) > 1:
            errors.append(f"{label} has duplicate repo alias: {key}")
    for path_key, values in sorted(by_path.items()):
        unique_ids = sorted(set(values))
        if len(values) > 1 and len(unique_ids) > 1:
            errors.append(
                f"{label} maps one resolved path to multiple repo ids: "
                f"{path_key} {unique_ids}"
            )
    return errors


def _read_jsonl_records_with_errors(
    path: Path,
) -> tuple[list[tuple[int, dict[str, Any]]], list[dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    errors: list[dict[str, Any]] = []
    if not path.exists():
        return records, errors
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped_bytes = raw_line.strip()
            if not stripped_bytes:
                continue
            try:
                payload = json.loads(stripped_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(
                    {
                        "line": line_number,
                        "error": str(exc),
                        "raw_sha256": sha256_bytes(stripped_bytes),
                    }
                )
                continue
            if isinstance(payload, dict):
                records.append((line_number, payload))
            else:
                errors.append(
                    {
                        "line": line_number,
                        "error": "JSONL row is not an object",
                        "raw_sha256": sha256_bytes(stripped_bytes),
                    }
                )
    return records, errors


def _stale_report_input_hash_errors(
    repo_root: Path,
    report_path: Path,
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        report_label = report_path.relative_to(repo_root).as_posix()
    except ValueError:
        report_label = report_path.as_posix()
    hash_policy = payload.get("hash_policy")
    if not isinstance(hash_policy, str):
        hash_policy = None
    for input_ref, input_hash in payload.get("input_hashes", {}).items():
        actual = _hash_path(repo_root / str(input_ref), hash_policy=hash_policy)
        if actual != input_hash:
            errors.append(
                f"Stale report input hash {report_label} "
                f"{input_ref}: {input_hash} != {actual}"
            )
    return errors


def _path_identity_hash(path: Path) -> str:
    return f"sha256:{sha256_bytes(path.resolve().as_posix().encode('utf-8'))}"


def _looks_like_local_path_text(text: str) -> bool:
    normalized = text.replace("\\", "/").casefold()
    return (
        bool(normalized.startswith("/"))
        or bool(re.search(r"(?:^|[\s\"'(\[])[a-z]:/", normalized))
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
    proof_surface_ids = [
        str(item.get("category_id", ""))
        for item in language_registry.get("proof_surface_categories", [])
    ]
    if len(proof_surface_ids) != len(set(proof_surface_ids)):
        errors.append(
            "Language coding advantage registry has duplicate "
            "proof_surface_categories category_id values"
        )
    known_proof_surface_ids = set(proof_surface_ids)
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
        proof_refs = [
            str(item)
            for item in language.get("proof_surface_refs", [])
        ]
        if len(proof_refs) != len(set(proof_refs)):
            errors.append(
                "Language coding advantage registry has duplicate "
                f"proof_surface_refs values: {language_id}"
            )
        for proof_ref in proof_refs:
            if proof_ref not in known_proof_surface_ids:
                errors.append(
                    "Language coding advantage registry references unknown "
                    f"proof surface {proof_ref}: {language_id}"
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
    return bool(
        re.search(
            r"\brepo-relative:(?!sha256:)[^\s,;\"')\]]+",
            text,
            flags=re.IGNORECASE,
        )
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


def _exception_event_taxonomy_by_type(
    exception_type_registry: dict[str, Any],
) -> dict[str, dict[str, str]]:
    taxonomy_dimensions = exception_type_registry.get("taxonomy_dimensions", {})
    category_defaults = (
        taxonomy_dimensions.get("category_defaults", {})
        if isinstance(taxonomy_dimensions, dict)
        else {}
    )
    event_taxonomy: dict[str, dict[str, str]] = {}
    for item in exception_type_registry.get("event_types", []):
        if not isinstance(item, dict) or not item.get("event_type"):
            continue
        event_type = str(item["event_type"])
        category = str(item.get("category") or "")
        defaults = category_defaults.get(category, {})
        if isinstance(defaults, dict):
            event_taxonomy[event_type] = {
                axis: str(defaults.get(axis, "unknown"))
                for axis in EXCEPTION_TAXONOMY_AXIS_KEYS
            }
    return event_taxonomy


def _exception_lake_taxonomy_consistency_errors(
    event: dict[str, Any],
    event_taxonomy_by_type: dict[str, dict[str, str]],
    *,
    line_number: int,
) -> list[str]:
    expected_dimensions = event_taxonomy_by_type.get(str(event.get("event_type")))
    if expected_dimensions and event.get("taxonomy_dimensions") != expected_dimensions:
        return [
            "Exception lake event taxonomy_dimensions do not match "
            f"registry defaults on line {line_number}: {event.get('event_type')}"
        ]
    return []


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


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if str(item)}


def _exception_route_bundle_errors(
    *,
    exception_type_registry: dict[str, Any],
    capture_pattern_registry: dict[str, Any],
    capture_scenarios: dict[str, Any],
    downstream_readme_text: str,
) -> list[str]:
    errors: list[str] = []
    event_types = {
        str(item.get("event_type") or "")
        for item in exception_type_registry.get("event_types", [])
        if isinstance(item, dict)
    }
    category_by_event_type = {
        str(item.get("event_type") or ""): str(item.get("category") or "")
        for item in exception_type_registry.get("event_types", [])
        if isinstance(item, dict)
    }
    route_registry = capture_route_registry_from_registries(
        capture_pattern_registry,
        exception_type_registry,
    )
    rules = [
        rule
        for rule in route_registry.get("rules", [])
        if isinstance(rule, dict)
    ]
    rules_by_id = {str(rule.get("rule_id") or ""): rule for rule in rules}
    reviewed_cases = [
        case
        for case in capture_scenarios.get("cases", [])
        if isinstance(case, dict) and case.get("review_status") == "reviewed"
    ]
    cases_by_rule: dict[str, list[dict[str, Any]]] = {}
    for case in reviewed_cases:
        case_id = str(case.get("scenario_id") or "<unknown>")
        for rule_id in _string_set(case.get("covered_rule_ids")):
            if rule_id not in rules_by_id:
                errors.append(
                    "Exception route bundle scenario covers unknown rule_id: "
                    f"{case_id} {rule_id}"
                )
                continue
            cases_by_rule.setdefault(rule_id, []).append(case)

    readme_lower = downstream_readme_text.casefold()
    for rule in rules:
        if rule.get("review_status") != "reviewed":
            continue
        emit = rule.get("emit") if isinstance(rule.get("emit"), dict) else {}
        packet_classes = _string_set(emit.get("packet_classes"))
        if not packet_classes or packet_classes == {"no_packet"}:
            continue
        rule_id = str(rule.get("rule_id") or "<unknown>")
        rule_cases = cases_by_rule.get(rule_id, [])
        if not rule_cases:
            errors.append(
                "Exception route bundle missing reviewed synthetic scenario "
                f"for emitting rule: {rule_id}"
            )
            continue
        emitted_event_type = str(emit.get("exception_event_type") or "")
        emitted_mail_type = str(emit.get("mail_message_type") or "")
        emitted_contract = str(emit.get("capture_contract") or "")
        required_fields = _string_set(emit.get("required_fields"))
        suppress_signals = _string_set(rule.get("suppress_signals"))

        for case in rule_cases:
            case_id = str(case.get("scenario_id") or "<unknown>")
            if not _capture_rule_matches_case(rule, case):
                errors.append(
                    "Exception route bundle scenario does not match claimed rule: "
                    f"{case_id} {rule_id}"
                )
            expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
            expected_packet_classes = _string_set(expected.get("packet_classes"))
            if "no_packet" in expected_packet_classes or expected.get("blocked") is True:
                continue
            missing_packet_classes = sorted(packet_classes - expected_packet_classes)
            if missing_packet_classes:
                errors.append(
                    "Exception route bundle scenario expected packet_classes omit "
                    f"{missing_packet_classes}: {case_id} {rule_id}"
                )
            if emitted_event_type:
                if emitted_event_type not in event_types:
                    errors.append(
                        "Exception route bundle rule emits unregistered event_type: "
                        f"{rule_id} {emitted_event_type}"
                    )
                if emitted_event_type not in _string_set(expected.get("event_types")):
                    errors.append(
                        "Exception route bundle scenario expected event_types omit "
                        f"{emitted_event_type}: {case_id} {rule_id}"
                    )
                if emitted_event_type.casefold() not in readme_lower:
                    errors.append(
                        "Exception route bundle downstream README omits event_type: "
                        f"{emitted_event_type}"
                    )
            if emitted_mail_type and emitted_mail_type not in _string_set(
                expected.get("mail_message_types")
            ):
                errors.append(
                    "Exception route bundle scenario expected mail_message_types omit "
                    f"{emitted_mail_type}: {case_id} {rule_id}"
                )
            if emitted_contract and emitted_contract not in _string_set(
                expected.get("capture_contracts")
            ):
                errors.append(
                    "Exception route bundle scenario expected capture_contracts omit "
                    f"{emitted_contract}: {case_id} {rule_id}"
                )
            missing_required_fields = sorted(
                required_fields - _string_set(expected.get("required_fields"))
            )
            if missing_required_fields:
                errors.append(
                    "Exception route bundle scenario expected required_fields omit "
                    f"{missing_required_fields}: {case_id} {rule_id}"
                )
            event_category = category_by_event_type.get(emitted_event_type, "")
            missing_negative_controls = sorted(
                suppress_signals - _string_set(case.get("negative_controls"))
            )
            if missing_negative_controls and event_category != "security_privacy":
                errors.append(
                    "Exception route bundle scenario negative_controls omit "
                    f"{missing_negative_controls}: {case_id} {rule_id}"
                )
            if rule_id.startswith("backfill-rule:"):
                expected_required_fields = _string_set(expected.get("required_fields"))
                missing_backfill_fields = sorted(
                    set(BACKFILL_ROUTE_REQUIRED_FIELDS) - expected_required_fields
                )
                if missing_backfill_fields:
                    errors.append(
                        "Exception route bundle backfill scenario required_fields omit "
                        f"{missing_backfill_fields}: {case_id} {rule_id}"
                    )
                missing_backfill_negative_controls = sorted(
                    {
                        "contains_private_rows",
                        "contains_raw_log_blob",
                        "contains_secret_or_pii",
                    }
                    - _string_set(case.get("negative_controls"))
                )
                if missing_backfill_negative_controls:
                    errors.append(
                        "Exception route bundle backfill scenario negative_controls omit "
                        f"{missing_backfill_negative_controls}: {case_id} {rule_id}"
                    )
    return errors


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


def _observed_audit_label(
    report_path: Path,
    repo_root: Path,
    row: dict[str, Any],
    outbox: dict[str, Any],
) -> str:
    repo_info = row.get("repo", {}) if isinstance(row.get("repo"), dict) else {}
    repo_id = str(repo_info.get("repo_id") or repo_info.get("path_hint") or "unknown")
    return f"{report_path.relative_to(repo_root)} {repo_id}:{outbox.get('path', '')}"


def _observed_audit_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _observed_audit_machine_evidence_errors(
    report_path: Path,
    repo_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    label = str(report_path.relative_to(repo_root))
    errors: list[str] = []
    recomputed_gap = observed_capture_audit_gap_count(payload, strict=False)
    recomputed_strict_gap = observed_capture_audit_gap_count(payload, strict=True)
    if (
        _observed_audit_int(payload.get("gap_flag_count", payload.get("gap_count")))
        != recomputed_gap
    ):
        errors.append(f"Observed audit gap_flag_count mismatch: {label}")
    if (
        _observed_audit_int(
            payload.get("strict_gap_flag_count", payload.get("strict_gap_count"))
        )
        != recomputed_strict_gap
    ):
        errors.append(f"Observed audit strict_gap_flag_count mismatch: {label}")
    rows = payload.get("repos", [])
    if not isinstance(rows, list):
        rows = []
    repo_count = _observed_audit_int(payload.get("repo_count"), 0)
    actual_reviewed_repo_count = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("repo"), dict)
        and row["repo"].get("reviewed_policy")
    )
    payload_scope = payload.get("audit_scope") if isinstance(payload.get("audit_scope"), dict) else {}
    expected_repo_count = _observed_audit_int(payload_scope.get("expected_repo_count"))
    audited_repo_count = _observed_audit_int(payload_scope.get("audited_repo_count"))
    reviewed_policy_repo_count = _observed_audit_int(
        payload_scope.get("reviewed_policy_repo_count")
    )
    reviewed_policy_scope = bool(payload_scope.get("reviewed_policy_scope"))
    recomputed_scope_satisfied = (
        reviewed_policy_scope
        and expected_repo_count > 0
        and audited_repo_count == expected_repo_count
        and reviewed_policy_repo_count == expected_repo_count
        and repo_count == expected_repo_count
    )
    if audited_repo_count != repo_count:
        errors.append(f"Observed audit scope audited count mismatch: {label}")
    if reviewed_policy_repo_count != actual_reviewed_repo_count:
        errors.append(f"Observed audit scope reviewed policy count mismatch: {label}")
    if bool(payload_scope.get("scope_satisfied")) != recomputed_scope_satisfied:
        errors.append(f"Observed audit scope_satisfied mismatch: {label}")
    evidence = payload.get("phase6_machine_gate_evidence")
    if not isinstance(evidence, dict):
        return [*errors, f"Observed audit missing phase6_machine_gate_evidence: {label}"]
    gates = evidence.get("gates")
    if not isinstance(gates, dict):
        return [*errors, f"Observed audit missing machine evidence gates: {label}"]
    gate = gates.get("machine-evidence:phase-6-observed-repo-capture-audit-reviewed")
    if not isinstance(gate, dict):
        return [
            *errors,
            f"Observed audit missing observed-repo capture machine evidence gate: {label}",
        ]
    if gate.get("evidence_scope") != "machine_only_not_roadmap_gate_evidence":
        errors.append(f"Observed audit machine evidence has invalid scope: {label}")
    if gate.get("human_gate_satisfied") is not False:
        errors.append(f"Observed audit machine evidence may satisfy human gate: {label}")
    if "roadmap_gate_id" in gate or "status" in gate:
        errors.append(f"Observed audit machine evidence is human-gate shaped: {label}")
    gate_evidence = gate.get("evidence") if isinstance(gate.get("evidence"), dict) else {}
    if _observed_audit_int(gate_evidence.get("strict_gap_flag_count")) != recomputed_strict_gap:
        errors.append(f"Observed audit machine strict gap mismatch: {label}")
    gate_scope = gate_evidence.get("scope") if isinstance(gate_evidence, dict) else {}
    if isinstance(gate_scope, dict) and gate_scope != payload_scope:
        errors.append(f"Observed audit machine scope mismatch: {label}")
    expected_status = (
        "passed"
        if repo_count and recomputed_scope_satisfied and recomputed_strict_gap == 0
        else "failed"
    )
    if gate.get("machine_status") != expected_status:
        errors.append(
            f"Observed audit machine_status mismatch: {label} "
            f"{gate.get('machine_status')} != {expected_status}"
        )
    return errors


def _capture_emission_simulation_errors(
    report_path: Path,
    repo_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    label = _report_path_label(report_path, repo_root)
    errors: list[str] = []
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        return [f"Capture emission simulation cases must be a list: {label}"]
    passed_count = sum(1 for case in cases if isinstance(case, dict) and case.get("passed"))
    failed_count = sum(
        1 for case in cases if isinstance(case, dict) and case.get("passed") is not True
    )
    if payload.get("case_count") != len(cases):
        errors.append(f"Capture emission simulation case_count mismatch: {label}")
    if payload.get("passed_count") != passed_count:
        errors.append(f"Capture emission simulation passed_count mismatch: {label}")
    if payload.get("failed_count") != failed_count:
        errors.append(f"Capture emission simulation failed_count mismatch: {label}")
    full_reviewed_case_count = _observed_audit_int(payload.get("full_reviewed_case_count"))
    emitted_reviewed_case_count = _observed_audit_int(payload.get("emitted_reviewed_case_count"))
    omitted_reviewed_scenario_ids = payload.get("omitted_reviewed_scenario_ids", [])
    if not isinstance(omitted_reviewed_scenario_ids, list):
        errors.append(f"Capture emission simulation omitted ids must be a list: {label}")
        omitted_reviewed_scenario_ids = []
    limited = bool(omitted_reviewed_scenario_ids) or bool(payload.get("limited"))
    if full_reviewed_case_count and full_reviewed_case_count < len(cases):
        errors.append(f"Capture emission simulation full case count is too small: {label}")
    if emitted_reviewed_case_count and emitted_reviewed_case_count != len(cases):
        errors.append(f"Capture emission simulation emitted case count mismatch: {label}")
    if limited and str(payload.get("coverage_status", "")) != "limited_diagnostic":
        errors.append(f"Capture emission simulation limited report has invalid coverage: {label}")
    if not limited and str(payload.get("coverage_status", "")) == "limited_diagnostic":
        errors.append(f"Capture emission simulation full report marked limited: {label}")
    required_provenance = {
        "suggestion_id",
        "methodology_hash",
        "matched_rule_ids",
        "update_required",
    }
    if set(payload.get("required_provenance_fields", []) or []) != required_provenance:
        errors.append(f"Capture emission simulation provenance contract mismatch: {label}")
    update_required_count = sum(
        1
        for case in cases
        if isinstance(case, dict) and case.get("initial_update_required") is True
    )
    if payload.get("initial_update_required_count") != update_required_count:
        errors.append(
            f"Capture emission simulation initial_update_required_count mismatch: {label}"
        )
    refreshed_count = sum(
        1
        for case in cases
        if isinstance(case, dict)
        and case.get("initial_repo_capture_surface_version")
        != case.get("emission_repo_capture_surface_version")
    )
    if payload.get("refreshed_emission_count") != refreshed_count:
        errors.append(f"Capture emission simulation refreshed_emission_count mismatch: {label}")
    evidence = payload.get("phase6_machine_gate_evidence")
    if not isinstance(evidence, dict):
        errors.append(f"Capture emission simulation missing phase6 evidence: {label}")
    else:
        expected_status = "passed" if cases and failed_count == 0 and not limited else "failed"
        if evidence.get("machine_status") != expected_status:
            errors.append(f"Capture emission simulation machine_status mismatch: {label}")
        if evidence.get("evidence_scope") != "machine_only_not_roadmap_gate_evidence":
            errors.append(f"Capture emission simulation invalid evidence scope: {label}")
        if evidence.get("human_gate_satisfied") is not False:
            errors.append(f"Capture emission simulation may satisfy human gate: {label}")
        if bool(evidence.get("limited")) != limited:
            errors.append(f"Capture emission simulation evidence limited mismatch: {label}")
        if str(evidence.get("coverage_status", "")) != str(payload.get("coverage_status", "")):
            errors.append(f"Capture emission simulation evidence coverage mismatch: {label}")
        gate_ids = set(evidence.get("supports_human_gate_ids", []) or [])
        expected_gate_ids = {
            "phase-6-capture-completeness-harness-reviewed",
            "phase-6-pattern-update-simulation-reviewed",
        }
        if limited and gate_ids:
            errors.append(f"Capture emission simulation limited report lists gate ids: {label}")
        if not limited and not expected_gate_ids <= gate_ids:
            errors.append(f"Capture emission simulation missing supported gate ids: {label}")
        legacy_gate_ids = {
            "synthetic-harness-proves-dad-worthy-patterns-become-packets",
            "pattern-update-simulation-proves-new-required-fields",
        }
        if legacy_gate_ids & gate_ids:
            errors.append(f"Capture emission simulation uses non-roadmap gate ids: {label}")
    for case in cases:
        if not isinstance(case, dict):
            errors.append(f"Capture emission simulation case is not an object: {label}")
            continue
        case_id = case.get("scenario_id", "<unknown>")
        suggestion_comparisons = case.get("suggestion_comparisons")
        if not isinstance(suggestion_comparisons, dict) or not all(
            suggestion_comparisons.values()
        ):
            errors.append(
                "Capture emission simulation suggestion comparison failed: "
                f"{label} {case_id}"
            )
        observed = case.get("observed")
        if not isinstance(observed, dict) or observed.get("passed") is not True:
            errors.append(
                f"Capture emission simulation observed check failed: {label} {case_id}"
            )
        emitted_packets = case.get("emitted_packets", [])
        if not isinstance(emitted_packets, list):
            errors.append(
                f"Capture emission simulation emitted_packets not list: {label} {case_id}"
            )
            emitted_packets = []
        emitted_screening_issues = [
            packet.get("screening_issues")
            for packet in emitted_packets
            if isinstance(packet, dict)
        ]
        if any(emitted_screening_issues):
            errors.append(
                f"Capture emission simulation emitted packet has screening issues: {label} {case_id}"
            )
        expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
        expected_classes = set(expected.get("packet_classes", []) or [])
        if "no_packet" not in expected_classes:
            required = set(expected.get("required_fields", []) or [])
            if not required_provenance <= required:
                errors.append(
                    "Capture emission simulation missing provenance fields in expected "
                    f"required_fields: {label} {case_id}"
                )
        elif emitted_packets:
            errors.append(
                f"Capture emission simulation no-packet case emitted packets: {label} {case_id}"
            )
    return errors


def _report_path_label(report_path: Path, repo_root: Path) -> str:
    try:
        return report_path.relative_to(repo_root).as_posix()
    except ValueError:
        return report_path.name


def _candidate_scan_repo_info(row: dict[str, Any]) -> dict[str, Any]:
    repo_info = row.get("repo")
    if isinstance(repo_info, dict):
        return repo_info
    return {
        "repo_id": row.get("repo_id"),
        "path_hint": row.get("path_hint"),
        "path_hash": row.get("path_hash"),
    }


def _candidate_scan_drift_is_tolerated(repo_info: dict[str, Any]) -> bool:
    return bool(repo_info.get("write_protected")) or str(repo_info.get("repo_id", "")) in {
        "logos-scripture-graph",
        "logos-governance-architecture",
    }


def _candidate_path_scan_staleness_errors(
    repo_root: Path,
    report_path: Path,
    row: dict[str, Any],
    *,
    registry: dict[str, Any],
    repo_policies: list[Any],
    policy_paths: dict[str, Path],
) -> list[str]:
    expected_scan = row.get("candidate_path_scan", {})
    if not isinstance(expected_scan, dict):
        return []
    repo_info = _candidate_scan_repo_info(row)
    audited_repo, resolve_error = _resolve_observed_audit_repo(
        repo_root,
        repo_info,
        policy_paths,
    )
    label = (
        f"{_report_path_label(report_path, repo_root)} "
        f"{repo_info.get('repo_id') or repo_info.get('path_hint') or 'unknown'}"
    )
    if audited_repo is None:
        return [f"Candidate path scan stale for {label}: {resolve_error}"]
    raw_limit = expected_scan.get("limit", 50)
    if raw_limit is None:
        candidate_limit = None
    else:
        try:
            parsed_limit = int(raw_limit)
        except (TypeError, ValueError):
            return [f"Candidate path scan stale for {label}: invalid candidate scan limit"]
        candidate_limit = parsed_limit if parsed_limit > 0 else None
    raw_max_scanned_files = expected_scan.get("max_scanned_files", 50_000)
    if raw_max_scanned_files is None:
        max_scanned_files = None
    else:
        try:
            parsed_max_scanned_files = int(raw_max_scanned_files)
        except (TypeError, ValueError):
            return [f"Candidate path scan stale for {label}: invalid max scanned files"]
        max_scanned_files = (
            parsed_max_scanned_files if parsed_max_scanned_files > 0 else None
        )
    current = audit_observed_capture_repo(
        repo_root,
        audited_repo,
        registry,
        repo_policies=repo_policies,
        candidate_limit=candidate_limit,
        max_scanned_files=max_scanned_files,
    )
    current_scan = current.get("candidate_path_scan", {})
    errors: list[str] = []
    bounded_same_evidence = (
        expected_scan.get("stopped_reason")
        == current_scan.get("stopped_reason")
        == "candidate_limit_reached"
        and expected_scan.get("limit_mode") == current_scan.get("limit_mode") == "bounded"
        and expected_scan.get("scan_hash") == current_scan.get("scan_hash")
    )
    for key in [
        "scan_hash",
        "scanned_file_count",
        "truncated",
        "path_hash_only",
        "limit_mode",
        "max_scanned_files",
        "stopped_reason",
    ]:
        if key == "scanned_file_count" and bounded_same_evidence:
            continue
        expected = expected_scan.get(key)
        actual = current_scan.get(key)
        if expected != actual:
            errors.append(
                f"Candidate path scan stale for {label} {key}: {expected} != {actual}"
            )
    expected_count = row.get("candidate_path_signal_count")
    actual_count = current.get("candidate_path_signal_count")
    if expected_count != actual_count:
        errors.append(
            f"Candidate path scan stale for {label} candidate_path_signal_count: "
            f"{expected_count} != {actual_count}"
        )
    if errors and _candidate_scan_drift_is_tolerated(repo_info):
        return []
    return errors


def _exception_wave_plan_readiness_path(report_path: Path) -> Path:
    if report_path.name == "exception_backfill_wave_plan.json":
        return report_path.with_name("exception_backfill_readiness.json")
    return report_path.with_name(report_path.stem + "_readiness.json")


def _json_stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _phase6_machine_evidence_summary_errors(
    report_path: Path,
    repo_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    label = _report_path_label(report_path, repo_root)
    expected = build_phase6_machine_evidence_summary(
        repo_root,
        generated_at=str(payload.get("generated_at") or ""),
    )
    errors: list[str] = []
    for key in [
        "report_id",
        "phase_id",
        "evidence_scope",
        "overall_machine_status",
        "human_review_required",
        "human_gate_satisfied",
        "phase6_human_gate_ids",
        "blocked_gate_ids",
        "source_report_failures",
        "source_reports",
        "gates",
        "input_hashes",
        "pass_condition",
        "recommended_next_actions",
        "authority_boundary",
    ]:
        if _json_stable(payload.get(key)) != _json_stable(expected.get(key)):
            errors.append(f"Phase 6 machine evidence summary stale for {label}: {key} mismatch")
    if payload.get("human_gate_satisfied") is not False:
        errors.append(f"Phase 6 machine evidence summary may satisfy human gate: {label}")
    if (
        payload.get("overall_machine_status") == "passed"
        and payload.get("blocked_gate_ids")
    ):
        errors.append(
            "Phase 6 machine evidence summary passed with blocked gates: "
            f"{label}"
        )
    return errors


def _exception_backfill_wave_plan_staleness_errors(
    repo_root: Path,
    report_path: Path,
    payload: dict[str, Any],
) -> list[str]:
    readiness_path = _exception_wave_plan_readiness_path(report_path)
    label = _report_path_label(report_path, repo_root)
    if not readiness_path.exists():
        return [
            f"Exception backfill wave plan stale for {label}: missing readiness report "
            f"{_report_path_label(readiness_path, repo_root)}"
        ]
    try:
        readiness_payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            f"Exception backfill wave plan stale for {label}: malformed readiness report "
            f"{exc.msg}"
        ]
    try:
        per_wave_repo_limit = int(payload.get("per_wave_repo_limit") or 25)
    except (TypeError, ValueError):
        return [f"Exception backfill wave plan stale for {label}: invalid per_wave_repo_limit"]
    expected = build_exception_backfill_wave_plan(
        readiness_payload,
        per_wave_repo_limit=per_wave_repo_limit,
    )
    errors: list[str] = []
    for key in [
        "source_report_id",
        "repo_count",
        "per_wave_repo_limit",
        "current_wave_id",
        "wave_order",
        "readiness_counts",
        "status_counts",
        "capture_surface_action_counts",
        "candidate_path_signal_summary",
        "input_hashes",
        "methodology_ref",
        "methodology_hash",
        "waves",
        "proof_backlogs",
    ]:
        if _json_stable(payload.get(key)) != _json_stable(expected.get(key)):
            errors.append(f"Exception backfill wave plan stale for {label}: {key} mismatch")
    return errors


def _exception_capture_remediation_plan_readiness_path(report_path: Path) -> Path:
    if report_path.name == "exception_capture_remediation_plan.json":
        return report_path.with_name("exception_backfill_readiness.json")
    return report_path.with_name(report_path.stem + "_readiness.json")


def _exception_capture_remediation_plan_staleness_errors(
    repo_root: Path,
    report_path: Path,
    payload: dict[str, Any],
) -> list[str]:
    readiness_path = _exception_capture_remediation_plan_readiness_path(report_path)
    label = _report_path_label(report_path, repo_root)
    if not readiness_path.exists():
        return [
            f"Exception capture remediation plan stale for {label}: missing readiness report "
            f"{_report_path_label(readiness_path, repo_root)}"
        ]
    try:
        readiness_payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            f"Exception capture remediation plan stale for {label}: malformed readiness report "
            f"{exc.msg}"
        ]
    try:
        per_lane_repo_limit = int(payload.get("per_lane_repo_limit") or 25)
    except (TypeError, ValueError):
        return [
            f"Exception capture remediation plan stale for {label}: invalid per_lane_repo_limit"
        ]
    expected = build_exception_capture_remediation_plan(
        readiness_payload,
        per_lane_repo_limit=per_lane_repo_limit,
    )
    errors: list[str] = []
    for key in [
        "source_report_id",
        "repo_count",
        "per_lane_repo_limit",
        "current_lane_id",
        "lane_order",
        "readiness_counts",
        "status_counts",
        "capture_surface_action_counts",
        "candidate_path_signal_summary",
        "input_hashes",
        "methodology_ref",
        "methodology_hash",
        "lanes",
        "pass_condition",
    ]:
        if _json_stable(payload.get(key)) != _json_stable(expected.get(key)):
            errors.append(
                f"Exception capture remediation plan stale for {label}: {key} mismatch"
            )
    return errors


def _exception_capture_gap_review_queue_observed_path(report_path: Path) -> Path:
    if report_path.name == "exception_capture_gap_review_queue.json":
        return report_path.with_name("exception_capture_observed_audit.json")
    return report_path.with_name(report_path.stem + "_observed_audit.json")


def _exception_capture_gap_review_queue_staleness_errors(
    repo_root: Path,
    report_path: Path,
    payload: dict[str, Any],
) -> list[str]:
    observed_path = _exception_capture_gap_review_queue_observed_path(report_path)
    label = _report_path_label(report_path, repo_root)
    if not observed_path.exists():
        return [
            f"Exception capture gap review queue stale for {label}: missing observed audit "
            f"{_report_path_label(observed_path, repo_root)}"
        ]
    try:
        observed_payload = json.loads(observed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            f"Exception capture gap review queue stale for {label}: malformed observed audit "
            f"{exc.msg}"
        ]
    try:
        per_group_example_limit = int(payload.get("per_group_example_limit") or 5)
    except (TypeError, ValueError):
        return [
            f"Exception capture gap review queue stale for {label}: invalid per_group_example_limit"
        ]
    expected = build_exception_capture_gap_review_queue(
        observed_payload,
        per_group_example_limit=per_group_example_limit,
    )
    errors: list[str] = []
    for key in [
        "report_id",
        "source_report_id",
        "repo_count",
        "review_group_count",
        "candidate_signal_count",
        "per_group_example_limit",
        "capture_surface_version",
        "status_counts",
        "candidate_path_signal_summary",
        "input_hashes",
        "methodology_ref",
        "methodology_hash",
        "groups",
        "authority_boundary",
    ]:
        if _json_stable(payload.get(key)) != _json_stable(expected.get(key)):
            errors.append(
                f"Exception capture gap review queue stale for {label}: {key} mismatch"
            )
    return errors


def _validate_lesson_graph_contract(
    repo_root: Path,
    registry: dict[str, Any],
    errors: list[str],
    checked: list[str],
    warnings: list[str] | None = None,
) -> None:
    warnings = warnings if warnings is not None else []
    edge_registry_path = repo_root / "registry" / "graph-edge-registry.json"
    edge_registry = json.loads(edge_registry_path.read_text(encoding="utf-8"))
    _validate_payload(repo_root, registry, "graph_edge_registry", edge_registry)
    checked.append("registry/graph-edge-registry.json")
    edge_defs = {row["edge_type"]: row for row in edge_registry.get("edge_types", [])}
    forbidden_edge_claims = {
        str(row.get("claim", "")): row
        for row in edge_registry.get("forbidden_edge_claims", [])
    }
    if len(edge_defs) != len(edge_registry.get("edge_types", [])):
        errors.append("Graph edge registry has duplicate edge_type values")

    graph_path = repo_root / "processed" / "learning" / "lesson-graph.json"
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        for edge in graph.get("edges", []):
            edge_type = str(edge.get("edge_type", ""))
            if edge_type in forbidden_edge_claims and (
                edge_type != "depends_on" or edge.get("edge_basis") != "declared.depends_on"
            ):
                errors.append(
                    "Lesson graph uses forbidden generated edge claim: "
                    f"{edge_type} ({forbidden_edge_claims[edge_type].get('reason', '')})"
                )
        try:
            _validate_payload(repo_root, registry, "lesson_graph", graph)
        except Exception as exc:
            errors.append(f"Invalid lesson graph schema: {exc}")
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

    _validate_graph_surface_manifest_contracts(repo_root, registry, errors, checked, warnings)


def _builder_source_hash(module_ref: str) -> str:
    module_name, separator, _attr_name = module_ref.rpartition(".")
    if not separator or not module_name:
        return "missing"
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return "missing"
    module_file = getattr(module, "__file__", "")
    return _hash_path(Path(module_file)) if module_file else "missing"


def _graph_surface_manifest_specs(repo_root: Path) -> list[tuple[dict[str, Any], Path]]:
    registry_path = repo_root / "registry" / "graph-surface-registry.json"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        specs: list[tuple[dict[str, Any], Path]] = []
        for surface in registry.get("surfaces", []):
            if not isinstance(surface, dict):
                continue
            outputs = surface.get("outputs", {})
            try:
                manifest_path = resolve_graph_surface_path(
                    repo_root, str(outputs["manifest_logical_path"])
                )
            except (KeyError, ValueError):
                continue
            if manifest_path.exists():
                specs.append((surface, manifest_path))
        return specs

    manifest_path = repo_root / "processed" / "learning" / "lesson-graph-manifest.json"
    if manifest_path.exists():
        return [
            (
                {
                    "surface_id": "lesson-graph",
                    "builder": {
                        "module": "digital_asset_directory.learning.build_lesson_graph"
                    },
                    "outputs": {
                        "manifest_logical_path": "learning/lesson-graph-manifest.json",
                        "body_logical_path": "learning/lesson-graph.json",
                    },
                },
                manifest_path,
            )
        ]
    return []


def _validate_graph_surface_manifest_contracts(
    repo_root: Path,
    registry: dict[str, Any],
    errors: list[str],
    checked: list[str],
    warnings: list[str],
) -> None:
    edge_registry_path = repo_root / "registry" / "graph-edge-registry.json"
    actual_edge_registry_hash = _hash_path(edge_registry_path)
    for surface, manifest_path in _graph_surface_manifest_specs(repo_root):
        surface_id = str(surface.get("surface_id", "unknown"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checked.append(_report_path_label(manifest_path, repo_root))
        if "graph_surface_manifest" in registry.get("schemas", {}) and manifest.get(
            "surface_id"
        ):
            try:
                _validate_payload(repo_root, registry, "graph_surface_manifest", manifest)
            except Exception as exc:
                errors.append(f"Invalid graph surface manifest {surface_id}: {exc}")
        expected_edge_registry_hash = manifest.get("edge_registry_hash")
        if (
            expected_edge_registry_hash
            and expected_edge_registry_hash != actual_edge_registry_hash
        ):
            errors.append(
                f"Inconsistent graph surface manifest {surface_id} edge registry hash: "
                f"{expected_edge_registry_hash} != {actual_edge_registry_hash}"
            )
        methodology_hashes = manifest.get("methodology_hashes", {})
        if isinstance(methodology_hashes, dict) and methodology_hashes.get(
            "builder_source"
        ):
            actual_builder_hash = _builder_source_hash(
                str(surface.get("builder", {}).get("module", ""))
            )
            if methodology_hashes["builder_source"] != actual_builder_hash:
                errors.append(
                    f"Inconsistent graph surface manifest {surface_id} methodology hash "
                    f"builder_source: {methodology_hashes['builder_source']} "
                    f"!= {actual_builder_hash}"
                )
        graph_content_hash = manifest.get("graph_content_hash")
        graph_path_value = str(manifest.get("graph_path") or "")
        if graph_path_value:
            manifest_graph_path = data_relative_path(repo_root, graph_path_value)
        else:
            try:
                manifest_graph_path = resolve_graph_surface_path(
                    repo_root,
                    str(surface.get("outputs", {}).get("body_logical_path", "")),
                )
            except ValueError:
                manifest_graph_path = repo_root / "__missing_graph_surface_body__"
        if graph_content_hash and manifest_graph_path.exists():
            actual_graph_hash = _hash_path(manifest_graph_path)
            if graph_content_hash != actual_graph_hash:
                errors.append(
                    f"Inconsistent graph surface manifest {surface_id} graph content hash: "
                    f"{graph_content_hash} != {actual_graph_hash}"
                )
        for rel, expected in manifest.get("input_hashes", {}).items():
            actual = _hash_path(data_relative_path(repo_root, rel))
            if actual != expected:
                message = (
                    f"Graph surface manifest {surface_id} stale input hash "
                    f"{rel}: {expected} != {actual}"
                )
                freshness = manifest.get("freshness", {})
                if isinstance(freshness, dict) and freshness.get("state") == "fresh":
                    errors.append(
                        "Inconsistent graph surface manifest "
                        f"{surface_id} fresh claim over stale input {rel}: "
                        f"{expected} != {actual}"
                    )
                else:
                    warnings.append(message)


def _validate_jsonl_with_registered_schema(
    repo_root: Path,
    registry: dict[str, Any],
    schema_name: str,
    rel: str,
    errors: list[str],
    checked: list[str],
) -> None:
    path = repo_root / rel
    if not path.exists():
        return
    schema_rel = registry.get("schemas", {}).get(schema_name)
    if not schema_rel:
        errors.append(f"Schema registry missing {schema_name} for {rel}")
        return
    try:
        schema = json.loads((repo_root / schema_rel).read_text(encoding="utf-8"))
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
    except Exception as exc:
        errors.append(f"Invalid registered schema {schema_name}: {exc}")
        return
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception as exc:
            errors.append(f"Invalid JSONL {rel}:{line_number}: {exc}")
            continue
        try:
            validator.validate(payload)
        except Exception as exc:
            errors.append(f"Invalid {schema_name} row {rel}:{line_number}: {exc}")
    checked.append(rel)


def _phase_command_evidence_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []
    roadmap_path = repo_root / "roadmap" / "roadmap.yaml"
    if not roadmap_path.exists():
        return errors
    try:
        roadmap = yaml.safe_load(roadmap_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return [f"Could not read roadmap command contracts: {exc}"]
    phases = {
        str(phase.get("id")): phase
        for phase in roadmap.get("phases", [])
        if isinstance(phase, dict)
    }
    phase8 = phases.get("phase-8-dad-local-deployment")
    if not phase8:
        return errors
    evidence_path = repo_root / "roadmap" / "evidence" / "phase-8-dad-local-deployment.commands.json"
    if not evidence_path.exists():
        errors.append("Phase 8 command evidence JSON is missing")
        return errors
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Invalid Phase 8 command evidence JSON: {exc}")
        return errors
    if evidence.get("schema_version") != "dad.phase8.command-evidence.v1":
        errors.append("Phase 8 command evidence has unexpected schema_version")
    if evidence.get("human_review_status") != "pending":
        errors.append("Phase 8 command evidence must remain pending until human gate review")
    authority = str(evidence.get("authority_boundary") or "").lower()
    for required_phrase in ["does not enroll", "satisfy human gates"]:
        if required_phrase not in authority:
            errors.append(
                "Phase 8 command evidence authority boundary must state it "
                f"{required_phrase}"
            )
    expected_commands = list(phase8.get("acceptance", {}).get("commands", []) or [])
    rows = evidence.get("commands")
    if not isinstance(rows, list):
        errors.append("Phase 8 command evidence commands must be a list")
        return errors
    observed_commands = [str(row.get("command") or "") for row in rows if isinstance(row, dict)]
    if set(observed_commands) != set(expected_commands):
        errors.append(
            "Phase 8 command evidence commands differ from roadmap acceptance: "
            f"missing={sorted(set(expected_commands) - set(observed_commands))} "
            f"extra={sorted(set(observed_commands) - set(expected_commands))}"
        )
    if len(observed_commands) != len(set(observed_commands)):
        errors.append("Phase 8 command evidence has duplicate command rows")
    for row in rows:
        if not isinstance(row, dict):
            errors.append("Phase 8 command evidence command row must be an object")
            continue
        command = str(row.get("command") or "")
        if row.get("status") != "passed":
            errors.append(f"Phase 8 command evidence is not passed: {command}")
        if not str(row.get("evidence_summary") or "").strip():
            errors.append(f"Phase 8 command evidence lacks summary: {command}")
    return errors


def validate_repo(repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
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
    phase_command_errors = _phase_command_evidence_errors(repo_root)
    if phase_command_errors:
        errors.extend(phase_command_errors)
    else:
        checked.append("roadmap/evidence/phase-8-dad-local-deployment.commands.json")
    try:
        cfg = load_config(repo_root=repo_root)
        errors.extend(_repo_policy_identity_errors("mail.repos", cfg.mail_repos))
        errors.extend(_repo_policy_identity_errors("exceptions.repos", cfg.exception_repos))
        errors.extend(_repo_policy_identity_errors("enrollment.repos", cfg.enrollment_repos))
        checked.append("config/sources.example.yaml:repo-policy-identities")
    except Exception as exc:
        errors.append(f"Invalid repo policy identity config: {exc}")
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
            ("ai_navigation_registry", "registry/ai-navigation-registry.json"),
            ("dad_address_model_registry", "registry/dad-address-model-registry.json"),
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
            ("graph_surface_registry", "registry/graph-surface-registry.json"),
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
        lesson_payload_fixture = "examples/mail/lesson-payload.golden.json"
        _validate_payload(
            repo_root,
            registry,
            "lesson_payload",
            json.loads((repo_root / lesson_payload_fixture).read_text(encoding="utf-8")),
        )
        checked.append(lesson_payload_fixture)
        _validate_jsonl_with_registered_schema(
            repo_root,
            registry,
            "rust_rollout_lesson",
            "lessons/rust_rollout/lesson_ledger.jsonl",
            errors,
            checked,
        )
        _validate_jsonl_with_registered_schema(
            repo_root,
            registry,
            "dad_pipeline_event",
            "processed/events/event_log.jsonl",
            errors,
            checked,
        )
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
        event_taxonomy_by_type = _exception_event_taxonomy_by_type(
            exception_type_registry
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
            downstream_exceptions_readme = repo_root / "templates" / "downstream" / "EXCEPTIONS_README.md"
            downstream_exceptions_readme_text = (
                downstream_exceptions_readme.read_text(encoding="utf-8")
                if downstream_exceptions_readme.exists()
                else ""
            )
            errors.extend(
                _exception_route_bundle_errors(
                    exception_type_registry=exception_type_registry,
                    capture_pattern_registry=capture_pattern_registry,
                    capture_scenarios=capture_scenarios,
                    downstream_readme_text=downstream_exceptions_readme_text,
                )
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
                errors.extend(
                    _exception_lake_taxonomy_consistency_errors(
                        event,
                        event_taxonomy_by_type,
                        line_number=line_number,
                    )
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
        backfill_decision_schema = _load_schema(
            repo_root,
            registry,
            "exception_backfill_review_decision",
        )
        backfill_decision_validator_cls = validator_for(backfill_decision_schema)
        backfill_decision_validator_cls.check_schema(backfill_decision_schema)
        backfill_decision_validator = backfill_decision_validator_cls(
            backfill_decision_schema
        )
        backfill_decisions_path = (
            repo_root
            / "processed"
            / "exceptions"
            / "review-queue"
            / "backfill_review_decisions.jsonl"
        )
        if backfill_decisions_path.exists():
            checked.append(
                "processed/exceptions/review-queue/backfill_review_decisions.jsonl"
            )
            for line_number, line in enumerate(
                backfill_decisions_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                decision = json.loads(line)
                backfill_decision_validator.validate(decision)
                if _contains_local_path_ref(decision):
                    errors.append(
                        "Exception backfill review decision contains local path-like "
                        f"metadata on line {line_number}"
                    )
                if _contains_readable_repo_relative_ref(decision):
                    errors.append(
                        "Exception backfill review decision contains readable "
                        f"repo-relative path metadata on line {line_number}"
                    )
        mail_message_schema = _load_schema(repo_root, registry, "mail_message")
        mail_message_validator_cls = validator_for(mail_message_schema)
        mail_message_validator_cls.check_schema(mail_message_schema)
        mail_message_validator = mail_message_validator_cls(mail_message_schema)
        source_packet_requests_path = (
            repo_root / "processed" / "mail" / "staged" / "source_packet_requests.jsonl"
        )
        if source_packet_requests_path.exists():
            checked.append("processed/mail/staged/source_packet_requests.jsonl")
            packets, packet_errors = _read_jsonl_records_with_errors(source_packet_requests_path)
            for error in packet_errors:
                errors.append(
                    "Exception source-packet request staged mail has malformed "
                    f"JSONL on line {error['line']}: {error['error']}"
                )
            active_report_mail_ids: set[str] = set()
            source_packet_report_path = (
                repo_root / "processed" / "reports" / "exception_source_packet_requests.json"
            )
            if source_packet_report_path.exists():
                try:
                    source_packet_report = json.loads(
                        source_packet_report_path.read_text(encoding="utf-8")
                    )
                    active_report_mail_ids = {
                        str(request.get("mail_id") or "")
                        for request in source_packet_report.get("requests", [])
                        if str(request.get("mail_id") or "")
                    }
                except json.JSONDecodeError as exc:
                    errors.append(
                        "Invalid JSON processed/reports/exception_source_packet_requests.json: "
                        f"{exc}"
                    )
            else:
                errors.append(
                    "processed/mail/staged/source_packet_requests.jsonl exists but "
                    "processed/reports/exception_source_packet_requests.json is missing"
                )
            canceled_mail_ids: set[str] = set()
            for _line_number, packet in packets:
                payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
                if (
                    str(packet.get("message_type") or "") == "review_decision"
                    and str(payload.get("superseded_reason") or "").startswith(
                        "source_packet_request_"
                    )
                    and str(payload.get("superseded_mail_id") or "")
                ):
                    canceled_mail_ids.add(str(payload.get("superseded_mail_id") or ""))
            for line_number, packet in packets:
                mail_message_validator.validate(packet)
                if _contains_local_path_ref(packet):
                    errors.append(
                        "Exception source-packet request mail contains local path-like "
                        f"metadata on line {line_number}"
                    )
                if _contains_readable_repo_relative_ref(packet):
                    errors.append(
                        "Exception source-packet request mail contains readable "
                        f"repo-relative path metadata on line {line_number}"
                    )
                payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
                if (
                    str(packet.get("message_type") or "") == "governance_notice"
                    and str(payload.get("source_ref") or "").startswith(
                        "dad://exceptions/backfill-review-groups/"
                    )
                ):
                    mail_id = str(packet.get("mail_id") or "")
                    if mail_id not in canceled_mail_ids and mail_id not in active_report_mail_ids:
                        errors.append(
                            "Exception source-packet request staged mail is not active "
                            "in the current request report and has no cancellation: "
                            f"{mail_id}"
                        )
        capture_refresh_notices_path = (
            repo_root
            / "processed"
            / "mail"
            / "staged"
            / "capture_surface_refresh_notices.jsonl"
        )
        if capture_refresh_notices_path.exists():
            checked.append("processed/mail/staged/capture_surface_refresh_notices.jsonl")
            notices, notice_errors = _read_jsonl_records_with_errors(
                capture_refresh_notices_path
            )
            for error in notice_errors:
                errors.append(
                    "Exception capture-surface refresh staged mail has malformed "
                    f"JSONL on line {error['line']}: {error['error']}"
                )
            active_notice_mail_ids: set[str] = set()
            capture_refresh_report_path = (
                repo_root
                / "processed"
                / "reports"
                / "exception_capture_surface_refresh_notices.json"
            )
            if capture_refresh_report_path.exists():
                try:
                    capture_refresh_report = json.loads(
                        capture_refresh_report_path.read_text(encoding="utf-8")
                    )
                    active_notice_mail_ids = {
                        str(notice.get("mail_id") or "")
                        for notice in capture_refresh_report.get("notices", [])
                        if str(notice.get("mail_id") or "")
                    }
                except json.JSONDecodeError as exc:
                    errors.append(
                        "Invalid JSON "
                        "processed/reports/exception_capture_surface_refresh_notices.json: "
                        f"{exc}"
                    )
            else:
                errors.append(
                    "processed/mail/staged/capture_surface_refresh_notices.jsonl exists "
                    "but processed/reports/exception_capture_surface_refresh_notices.json "
                    "is missing"
                )
            for line_number, notice in notices:
                mail_message_validator.validate(notice)
                if _contains_local_path_ref(notice):
                    errors.append(
                        "Exception capture-surface refresh mail contains local path-like "
                        f"metadata on line {line_number}"
                    )
                if _contains_readable_repo_relative_ref(notice):
                    errors.append(
                        "Exception capture-surface refresh mail contains readable "
                        f"repo-relative path metadata on line {line_number}"
                    )
                payload = notice.get("payload") if isinstance(notice.get("payload"), dict) else {}
                if (
                    str(notice.get("message_type") or "") == "governance_notice"
                    and str(payload.get("source_ref") or "")
                    == "dad://exceptions/capture-surface-refresh-notices"
                ):
                    mail_id = str(notice.get("mail_id") or "")
                    if mail_id not in active_notice_mail_ids:
                        errors.append(
                            "Exception capture-surface refresh staged mail is not active "
                            "in the current refresh notice report: "
                            f"{mail_id}"
                        )
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
        try:
            exception_cfg = load_config(repo_root=repo_root)
            exception_repo_policies = exception_cfg.exception_repos
        except Exception:
            exception_repo_policies = []
        capture_registry = load_capture_pattern_registry(repo_root)
        for report_path in [
            *sorted((repo_root / "processed" / "reports").glob("*.json")),
            *sorted((repo_root / "processed" / "events" / "reports").glob("*.json")),
            *sorted((repo_root / "processed" / "harnesses").glob("*.json")),
            *sorted((repo_root / "processed" / "repo_inventory").glob("*.json")),
        ]:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                checked.append(str(report_path.relative_to(repo_root)))
                continue
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
                    hash_policy = payload.get("hash_policy")
                    if not isinstance(hash_policy, str):
                        hash_policy = None
                    actual = f"sha256:{_file_hash_for_policy(methodology_path, hash_policy)}"
                    if actual != expected:
                        errors.append(
                            f"Stale methodology report {report_path.relative_to(repo_root)}: "
                            f"{expected} != {actual}"
                        )
                checked.append(str(report_path.relative_to(repo_root)))
            if payload.get("input_hashes"):
                errors.extend(_stale_report_input_hash_errors(repo_root, report_path, payload))
                checked.append(str(report_path.relative_to(repo_root)))
            elif report_path.is_relative_to(repo_root / "processed" / "events" / "reports"):
                errors.append(
                    f"Event pipeline report missing input_hashes: "
                    f"{report_path.relative_to(repo_root)}"
                )
                checked.append(str(report_path.relative_to(repo_root)))
            if payload.get("audit_id") == "dad:exception-capture-observed-audit":
                errors.extend(
                    _observed_audit_machine_evidence_errors(report_path, repo_root, payload)
                )
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
                    errors.extend(
                        _candidate_path_scan_staleness_errors(
                            repo_root,
                            report_path,
                            row,
                            registry=capture_registry,
                            repo_policies=exception_repo_policies,
                            policy_paths=policy_paths,
                        )
                    )
            elif payload.get("report_id") == "dad:phase6-exception-capture-machine-evidence-summary":
                errors.extend(
                    _phase6_machine_evidence_summary_errors(report_path, repo_root, payload)
                )
                checked.append(str(report_path.relative_to(repo_root)))
            elif payload.get("report_id") == "dad:exception-backfill-readiness":
                policy_paths = _observed_audit_policy_paths(repo_root)
                for row in payload.get("repos", []):
                    if isinstance(row, dict):
                        errors.extend(
                            _candidate_path_scan_staleness_errors(
                                repo_root,
                                report_path,
                                row,
                                registry=capture_registry,
                                repo_policies=exception_repo_policies,
                                policy_paths=policy_paths,
                            )
                        )
            elif payload.get("report_id") == "dad:exception-backfill-wave-plan":
                errors.extend(
                    _exception_backfill_wave_plan_staleness_errors(
                        repo_root,
                        report_path,
                        payload,
                    )
                )
            elif payload.get("report_id") == "dad:exception-capture-remediation-plan":
                errors.extend(
                    _exception_capture_remediation_plan_staleness_errors(
                        repo_root,
                        report_path,
                        payload,
                    )
                )
            elif payload.get("report_id") == "dad:exception-capture-gap-review-queue":
                errors.extend(
                    _exception_capture_gap_review_queue_staleness_errors(
                        repo_root,
                        report_path,
                        payload,
                    )
                )
            elif payload.get("report_id") == "dad:exception-capture-emission-simulation":
                errors.extend(
                    _capture_emission_simulation_errors(report_path, repo_root, payload)
                )
        _validate_graph_surface_registry_contract(repo_root, registry, errors, checked)
        _validate_lesson_graph_contract(repo_root, registry, errors, checked, warnings)
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
    return {
        "valid": not errors,
        "checked_count": len(set(checked)),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
