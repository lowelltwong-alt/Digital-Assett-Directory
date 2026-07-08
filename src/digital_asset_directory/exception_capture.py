from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .ids import stable_id
from .exceptions_lake import (
    BACKFILL_EXCLUDE_DIRS,
    BACKFILL_SENSITIVE_PATH_TERMS,
    EXCEPTION_OUTBOX,
    FIX_OUTCOME_PATH,
    backfill_classifier_rules,
    backfill_path_signal_terms,
    load_event_type_registry,
    path_term_matches,
    record_exception_event,
    record_exception_fix_outcome,
    screen_exception_record,
)
from .mail_center import MAIL_MIRROR_DIR, compose_mail
from .mail_center import _build_mail_record, _jsonl_lock
from .models import MailMessageRecord
from .transport import data_relative_path
from .utils import (
    append_jsonl,
    safe_relative,
    sha256_bytes,
    sha256_file,
    write_json,
    write_jsonl,
    utc_now,
)

CAPTURE_PATTERN_REGISTRY = Path("registry") / "exception-capture-pattern-registry.json"
EVENT_TYPE_REGISTRY = Path("registry") / "exception-event-type-registry.json"
CAPTURE_ROUTE_METHODOLOGY_REF = (
    f"{CAPTURE_PATTERN_REGISTRY.as_posix()} + "
    f"{EVENT_TYPE_REGISTRY.as_posix()}#backfill_classifier"
)
CAPTURE_REPORT_JSON = Path("processed") / "reports" / "exception_capture_completeness.json"
CAPTURE_REPORT_MD = Path("processed") / "reports" / "exception_capture_completeness.md"
TAXONOMY_COVERAGE_REPORT_JSON = (
    Path("processed") / "reports" / "exception_taxonomy_coverage.json"
)
TAXONOMY_COVERAGE_REPORT_MD = Path("processed") / "reports" / "exception_taxonomy_coverage.md"
OBSERVED_AUDIT_JSON = Path("processed") / "reports" / "exception_capture_observed_audit.json"
OBSERVED_AUDIT_MD = Path("processed") / "reports" / "exception_capture_observed_audit.md"
BACKFILL_READINESS_JSON = Path("processed") / "reports" / "exception_backfill_readiness.json"
BACKFILL_READINESS_MD = Path("processed") / "reports" / "exception_backfill_readiness.md"
BACKFILL_WAVE_PLAN_JSON = Path("processed") / "reports" / "exception_backfill_wave_plan.json"
BACKFILL_WAVE_PLAN_MD = Path("processed") / "reports" / "exception_backfill_wave_plan.md"
CAPTURE_REMEDIATION_PLAN_JSON = (
    Path("processed") / "reports" / "exception_capture_remediation_plan.json"
)
CAPTURE_REMEDIATION_PLAN_MD = (
    Path("processed") / "reports" / "exception_capture_remediation_plan.md"
)
CAPTURE_SURFACE_REFRESH_NOTICES_JSON = (
    Path("processed") / "reports" / "exception_capture_surface_refresh_notices.json"
)
CAPTURE_SURFACE_REFRESH_NOTICES_MD = (
    Path("processed") / "reports" / "exception_capture_surface_refresh_notices.md"
)
CAPTURE_SURFACE_REFRESH_NOTICES_STAGED = (
    Path("processed") / "mail" / "staged" / "capture_surface_refresh_notices.jsonl"
)
CAPTURE_SURFACE_REFRESH_NOTICE_QUARANTINE = (
    Path("processed")
    / "exceptions"
    / "quarantine"
    / "capture_surface_refresh_notices_malformed_jsonl.jsonl"
)
CAPTURE_GAP_REVIEW_QUEUE_JSON = (
    Path("processed") / "reports" / "exception_capture_gap_review_queue.json"
)
CAPTURE_GAP_REVIEW_QUEUE_MD = (
    Path("processed") / "reports" / "exception_capture_gap_review_queue.md"
)
CAPTURE_EMISSION_SIMULATION_JSON = (
    Path("processed") / "reports" / "exception_capture_emission_simulation.json"
)
CAPTURE_EMISSION_SIMULATION_MD = (
    Path("processed") / "reports" / "exception_capture_emission_simulation.md"
)
PHASE6_MACHINE_EVIDENCE_SUMMARY_JSON = (
    Path("processed") / "reports" / "phase6_exception_capture_machine_evidence_summary.json"
)
PHASE6_MACHINE_EVIDENCE_SUMMARY_MD = (
    Path("processed") / "reports" / "phase6_exception_capture_machine_evidence_summary.md"
)
PHASE6_LAWFIRM_MISSED_CAPTURE_SCENARIO_ID = "lawfirm-review-issue-missed-capture"
PHASE6_HUMAN_GATE_IDS = (
    "phase-6-capture-completeness-harness-reviewed",
    "phase-6-lawfirm-intake-missed-capture-regression",
    "phase-6-pattern-update-simulation-reviewed",
    "phase-6-all-asset-pattern-coverage-reviewed",
    "phase-6-sensitive-payload-negative-tests-reviewed",
    "phase-6-observed-repo-capture-audit-reviewed",
    "phase-6-taxonomy-route-coverage-reviewed",
)
PHASE6_REQUIRED_UPDATE_FAMILIES = {
    "workflow",
    "mail_pattern",
    "exception_pattern",
    "learning_loop_candidate",
}
PHASE6_REQUIRED_UPDATE_VECTORS = {
    "dad_needs_registry",
    "dad_offerings_registry",
    "downstream_template",
    "exception_taxonomy",
}
PHASE6_REQUIRED_NEGATIVE_CONTROLS = {
    "contains_hidden_chain_of_thought",
    "contains_private_rows",
    "contains_prompt_injection_like_text",
    "contains_raw_log_blob",
    "contains_secret_or_pii",
    "contains_source_or_diff",
}
PHASE6_NEGATIVE_CONTROL_ISSUES = {
    "contains_hidden_chain_of_thought": {"hidden_reasoning_like_payload"},
    "contains_private_rows": {"table_like_value"},
    "contains_prompt_injection_like_text": {"prompt_injection_like_payload"},
    "contains_raw_log_blob": {"long_string", "raw_blob_like_multiline_value"},
    "contains_secret_or_pii": {"credential_or_pii_pattern"},
    "contains_source_or_diff": {"source_or_diff_like_payload"},
}
PHASE6_MACHINE_EVIDENCE_SCOPE = "machine_only_not_roadmap_gate_evidence"
PHASE6_GATE_BOUNDARY = (
    "Machine evidence only. These statuses show whether deterministic reports "
    "contain the expected support for Phase 6 gates; they do not satisfy the "
    "separate human-reviewed roadmap gates."
)
PHASE6_SUMMARY_REPORTS = {
    "capture_completeness": CAPTURE_REPORT_JSON,
    "emission_simulation": CAPTURE_EMISSION_SIMULATION_JSON,
    "taxonomy_coverage": TAXONOMY_COVERAGE_REPORT_JSON,
    "observed_audit": OBSERVED_AUDIT_JSON,
}
PHASE6_SUMMARY_REQUIRED_CONTRIBUTORS = {
    "phase-6-capture-completeness-harness-reviewed": (
        ("capture_completeness", "gate"),
        ("emission_simulation", "support"),
    ),
    "phase-6-lawfirm-intake-missed-capture-regression": (
        ("capture_completeness", "gate"),
    ),
    "phase-6-pattern-update-simulation-reviewed": (
        ("capture_completeness", "gate"),
        ("emission_simulation", "support"),
    ),
    "phase-6-all-asset-pattern-coverage-reviewed": (
        ("capture_completeness", "gate"),
    ),
    "phase-6-sensitive-payload-negative-tests-reviewed": (
        ("capture_completeness", "gate"),
    ),
    "phase-6-observed-repo-capture-audit-reviewed": (
        ("observed_audit", "gate"),
    ),
    "phase-6-taxonomy-route-coverage-reviewed": (
        ("taxonomy_coverage", "gate"),
    ),
}
OBSERVED_CAPTURE_AUDIT_GAP_FLAGS = {
    "capture_surface_version_unknown",
    "candidate_path_scan_truncated",
    "mail_present_exception_gap_candidate",
    "malformed_jsonl",
    "missed_capture_candidate",
    "pattern_gap_candidate",
    "stale_capture_surface",
}
OBSERVED_CAPTURE_AUDIT_STRICT_EXTRA_FLAGS = {
    "emission_unverified",
    "type_present_uncorrelated",
}
ACTIONABLE_CAPTURE_GAP_EMISSION_STATUSES = {
    "gap_candidate",
    "type_present_uncorrelated",
    "unverified",
}

PACKET_CLASSES = {
    "ordinary_mail",
    "exception_event",
    "fix_outcome",
    "local_usage_only",
    "no_packet",
}
CAPTURE_SIGNAL_RE = re.compile(r"^[a-z][a-z0-9_:-]{0,80}$")
CAPTURE_NOTICE_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,180}$")
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore (all )?(previous|prior|above) instructions\b"),
    re.compile(r"(?i)\b(system|developer) prompt\b"),
    re.compile(r"(?i)\bexecute (this )?(tool|command)\b"),
]


def exception_capture_data_path(hub_root: Path, relative_path: Path | str) -> Path:
    return data_relative_path(hub_root, relative_path)


def _capture_output_path(
    hub_root: Path,
    output: Path | None,
    default_relative_path: Path,
) -> Path:
    if output is not None:
        return output if output.is_absolute() else exception_capture_data_path(hub_root, output)
    return exception_capture_data_path(hub_root, default_relative_path)
CAPTURE_AUDIT_EXCLUDE_DIRS = set(BACKFILL_EXCLUDE_DIRS) | {
    ".digital-asset",
    ".idea",
    ".tmp",
    ".vscode",
    "coverage",
    "htmlcov",
}
PLACEHOLDER_REQUIRED_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "placeholder",
    "metadata-only placeholder",
    "tbd",
    "todo",
}
SIMULATED_EMISSION_PROVENANCE_FIELDS = {
    "suggestion_id",
    "methodology_hash",
    "matched_rule_ids",
    "update_required",
}
BACKFILL_ROUTE_REQUIRED_FIELDS = [
    "false_positive_risk",
    "path_signal",
    "safe_path_hash_or_pointer",
    "source_rule_id",
]
PRIVATE_PATH_FRAGMENTS = (
    "c:/users/",
    "c:\\users\\",
    "/users/",
    "\\users\\",
    "onedrive/",
    "onedrive\\",
    "git projects/",
    "git projects\\",
    "appdata/",
    "appdata\\",
)
CAPTURE_AUDIT_PATH_TERMS: dict[str, dict[str, str]] = {
    "red-team": {
        "pattern_family": "harness",
        "signal": "path_keyword:red-team",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "red_team": {
        "pattern_family": "harness",
        "signal": "path_keyword:red_team",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "review-finding": {
        "pattern_family": "review_finding",
        "signal": "path_keyword:review-finding",
        "expected_review": "exception_event_or_no_packet",
        "suggested_event_type": "review_finding",
    },
    "review_finding": {
        "pattern_family": "review_finding",
        "signal": "path_keyword:review_finding",
        "expected_review": "exception_event_or_no_packet",
        "suggested_event_type": "review_finding",
    },
    ".ai-assets": {
        "pattern_family": "asset",
        "signal": "path_keyword:.ai-assets",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "asset-registry": {
        "pattern_family": "asset",
        "signal": "path_keyword:asset-registry",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "asset.json": {
        "pattern_family": "asset",
        "signal": "path_keyword:asset.json",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "harness": {
        "pattern_family": "harness",
        "signal": "path_keyword:harness",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "skill": {
        "pattern_family": "skill",
        "signal": "path_keyword:skill",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "template": {
        "pattern_family": "template",
        "signal": "path_keyword:template",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "architecture": {
        "pattern_family": "architecture_reference",
        "signal": "path_keyword:architecture",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "",
    },
    "governance": {
        "pattern_family": "governance_map",
        "signal": "path_keyword:governance",
        "expected_review": "ordinary_mail_exception_or_no_packet",
        "suggested_event_type": "roadmap_gate_mismatch",
    },
    "data-map": {
        "pattern_family": "data_map",
        "signal": "path_keyword:data-map",
        "expected_review": "ordinary_mail_exception_or_no_packet",
        "suggested_event_type": "sensitive_boundary_block",
    },
    "data_map": {
        "pattern_family": "data_map",
        "signal": "path_keyword:data_map",
        "expected_review": "ordinary_mail_exception_or_no_packet",
        "suggested_event_type": "sensitive_boundary_block",
    },
    "lesson": {
        "pattern_family": "learning_loop_candidate",
        "signal": "path_keyword:lesson",
        "expected_review": "ordinary_mail_or_local_usage",
        "suggested_event_type": "",
    },
    "learning": {
        "pattern_family": "learning_loop_candidate",
        "signal": "path_keyword:learning",
        "expected_review": "ordinary_mail_or_local_usage",
        "suggested_event_type": "",
    },
    "workflow": {
        "pattern_family": "workflow",
        "signal": "path_keyword:workflow",
        "expected_review": "ordinary_mail_or_no_packet",
        "suggested_event_type": "review_finding",
    },
    "review-issue": {
        "pattern_family": "workflow",
        "signal": "path_keyword:review-issue",
        "expected_review": "ordinary_mail_exception_or_no_packet",
        "suggested_event_type": "review_finding",
    },
    "review_issue": {
        "pattern_family": "workflow",
        "signal": "path_keyword:review_issue",
        "expected_review": "ordinary_mail_exception_or_no_packet",
        "suggested_event_type": "review_finding",
    },
    "capture-gap": {
        "pattern_family": "workflow",
        "signal": "path_keyword:capture-gap",
        "expected_review": "ordinary_mail_exception_or_no_packet",
        "suggested_event_type": "review_finding",
    },
    "exception-lake": {
        "pattern_family": "workflow",
        "signal": "path_keyword:exception-lake",
        "expected_review": "ordinary_mail_exception_or_no_packet",
        "suggested_event_type": "review_finding",
    },
}


def load_capture_pattern_registry(hub_root: Path) -> dict[str, Any]:
    return json.loads((hub_root / CAPTURE_PATTERN_REGISTRY).read_text(encoding="utf-8"))


def capture_route_registry_from_registries(
    capture_registry: dict[str, Any],
    event_registry: dict[str, Any],
) -> dict[str, Any]:
    """Return capture rules plus backfill-only reviewed learnable route rules."""
    capture_events = {
        str((rule.get("emit") or {}).get("exception_event_type") or "")
        for rule in capture_registry.get("rules", [])
        if isinstance(rule, dict)
        and rule.get("review_status") == "reviewed"
        and str((rule.get("emit") or {}).get("exception_event_type") or "")
    }
    events_by_type = {
        str(event.get("event_type") or ""): event
        for event in event_registry.get("event_types", [])
        if isinstance(event, dict)
    }
    route_rules = list(capture_registry.get("rules", []))
    classifier = event_registry.get("backfill_classifier")
    classifier_rules = classifier.get("rules", []) if isinstance(classifier, dict) else []
    for backfill_rule in classifier_rules:
        if not isinstance(backfill_rule, dict):
            continue
        event_type = str(backfill_rule.get("event_type") or "")
        event = events_by_type.get(event_type, {})
        if event_type in capture_events:
            continue
        if event.get("review_status") != "reviewed" or not bool(event.get("learnable")):
            continue
        rule_id = str(backfill_rule.get("rule_id") or "")
        terms = [str(term) for term in backfill_rule.get("terms", []) if str(term)]
        if not rule_id or not event_type or not terms:
            continue
        route_rules.append(
            {
                "rule_id": rule_id,
                "pattern_family": "exception_pattern",
                "description": (
                    "Backfill-only path-signal route for reviewed learnable "
                    f"exception event `{event_type}`."
                ),
                "min_capture_surface_version": str(
                    capture_registry.get("capture_surface_version") or "0.4.0"
                ),
                "match_signals": [],
                "any_signals": [f"path_keyword:{term}" for term in terms],
                "suppress_signals": [],
                "emit": {
                    "packet_classes": ["exception_event"],
                    "mail_message_type": "",
                    "exception_event_type": event_type,
                    "capture_contract": str(
                        backfill_rule.get("capture_contract") or "backfill_candidate"
                    ),
                    "severity": str(backfill_rule.get("severity") or ""),
                    "required_fields": BACKFILL_ROUTE_REQUIRED_FIELDS,
                    "rationale": (
                        "Backfill path-signal candidates use safe metadata only "
                        "and require source review before learning promotion."
                    ),
                },
                "applies_when": list(backfill_rule.get("applies_when", [])),
                "does_not_apply_when": list(backfill_rule.get("does_not_apply_when", [])),
                "danger_if_missed": (
                    "Backfill-only exception evidence can appear covered by taxonomy "
                    "while no deterministic scenario proves the route."
                ),
                "review_status": "reviewed",
                "route_kind": "backfill_path_signal",
                "classification_confidence": str(
                    backfill_rule.get("classification_confidence")
                    or "path_name_signal_only"
                ),
                "false_positive_risk": str(backfill_rule.get("false_positive_risk") or ""),
            }
        )
    return {
        **capture_registry,
        "rules": route_rules,
    }


def load_capture_route_registry(hub_root: Path) -> dict[str, Any]:
    capture_registry = load_capture_pattern_registry(hub_root)
    try:
        event_registry = load_event_type_registry(hub_root)
    except FileNotFoundError:
        return capture_registry
    return capture_route_registry_from_registries(capture_registry, event_registry)


def capture_route_methodology_hash(hub_root: Path) -> str:
    refs = [CAPTURE_PATTERN_REGISTRY]
    if (hub_root / EVENT_TYPE_REGISTRY).exists():
        refs.append(EVENT_TYPE_REGISTRY)
    payload = [
        {
            "path": ref.as_posix(),
            "sha256": sha256_file(hub_root / ref),
        }
        for ref in refs
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256_bytes(encoded)}"


def load_capture_scenarios(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _version_tuple(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("v")
    parts: list[int] = []
    for item in cleaned.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            parts.append(0)
    return tuple(parts or [0])


def _rule_matches(rule: dict[str, Any], signals: set[str]) -> bool:
    required = set(rule.get("match_signals", []))
    any_signals = set(rule.get("any_signals", []))
    suppressed = set(rule.get("suppress_signals", []))
    return (
        required <= signals
        and (not any_signals or bool(any_signals & signals))
        and not bool(suppressed & signals)
    )


def _rule_would_match_without_suppression(
    rule: dict[str, Any],
    signals: set[str],
) -> bool:
    required = set(rule.get("match_signals", []))
    any_signals = set(rule.get("any_signals", []))
    return required <= signals and (not any_signals or bool(any_signals & signals))


def _empty_actual(blocked: bool = False, blocked_reason: str = "") -> dict[str, Any]:
    return {
        "packet_classes": ["no_packet"] if blocked else [],
        "event_types": [],
        "mail_message_types": [],
        "capture_contracts": [],
        "required_fields": [],
        "blocked": blocked,
        "blocked_reason": blocked_reason,
    }


def _sorted(values: set[str]) -> list[str]:
    return sorted(item for item in values if item)


def _looks_like_local_path_payload(text: str) -> bool:
    normalized = text.casefold()
    slash_normalized = normalized.replace("\\", "/")
    return (
        bool(re.search(r"(?:^|[\s\"'(\[])[a-z]:[\\/]", normalized))
        or slash_normalized.startswith("/")
        or any(fragment in normalized for fragment in PRIVATE_PATH_FRAGMENTS)
        or any(fragment in slash_normalized for fragment in PRIVATE_PATH_FRAGMENTS)
    )


def _iter_payload_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_payload_strings(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_payload_strings(item)


def _unsafe_capture_text_issues(text: str) -> set[str]:
    issues: set[str] = set()
    _, screen_issues = screen_exception_record({"sample": text})
    issues.update(screen_issues)
    if any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS):
        issues.add("prompt_injection_like_payload")
    if _looks_like_local_path_payload(text):
        issues.add("local_path_like_payload")
    return issues


def _payload_sample_issues(case: dict[str, Any]) -> list[str]:
    issues: set[str] = set()
    for sample in case.get("payload_samples", []) or []:
        text = str(sample.get("text", "") if isinstance(sample, dict) else sample)
        if not text:
            continue
        issues.update(_unsafe_capture_text_issues(text))
    return sorted(issues)


def _rule_actual(
    case: dict[str, Any],
    registry: dict[str, Any],
) -> tuple[dict[str, Any], list[str], bool]:
    signals = set(case.get("signals", []))
    packet_classes: set[str] = set()
    event_types: set[str] = set()
    mail_message_types: set[str] = set()
    capture_contracts: set[str] = set()
    required_fields: set[str] = set()
    matched_rules: list[str] = []
    update_required = _version_tuple(case.get("repo_capture_surface_version", "0")) < _version_tuple(
        registry.get("capture_surface_version", "0")
    )
    for rule in registry.get("rules", []):
        if rule.get("review_status") != "reviewed":
            continue
        if not _rule_matches(rule, signals):
            continue
        matched_rules.append(rule["rule_id"])
        if _version_tuple(case.get("repo_capture_surface_version", "0")) < _version_tuple(
            rule.get("min_capture_surface_version", "0")
        ):
            update_required = True
        emit = rule.get("emit", {})
        packet_classes.update(str(item) for item in emit.get("packet_classes", []))
        if emit.get("exception_event_type"):
            event_types.add(str(emit["exception_event_type"]))
        if emit.get("mail_message_type"):
            mail_message_types.add(str(emit["mail_message_type"]))
        if emit.get("capture_contract"):
            capture_contracts.add(str(emit["capture_contract"]))
        required_fields.update(str(item) for item in emit.get("required_fields", []))
    if not packet_classes:
        packet_classes.add("no_packet")
    return (
        {
            "packet_classes": _sorted(packet_classes),
            "event_types": _sorted(event_types),
            "mail_message_types": _sorted(mail_message_types),
            "capture_contracts": _sorted(capture_contracts),
            "required_fields": _sorted(required_fields),
            "blocked": False,
            "blocked_reason": "",
        },
        matched_rules,
        update_required,
    )


def _suppressed_rule_actual(
    case: dict[str, Any],
    registry: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    signals = set(case.get("signals", []))
    packet_classes: set[str] = set()
    event_types: set[str] = set()
    capture_contracts: set[str] = set()
    required_fields: set[str] = set()
    suppressed_rule_ids: list[str] = []
    for rule in registry.get("rules", []):
        if rule.get("review_status") != "reviewed":
            continue
        suppressed = set(rule.get("suppress_signals", []))
        if not suppressed or not bool(suppressed & signals):
            continue
        if not _rule_would_match_without_suppression(rule, signals):
            continue
        suppressed_rule_ids.append(str(rule["rule_id"]))
        emit = rule.get("emit", {})
        packet_classes.update(str(item) for item in emit.get("packet_classes", []))
        if emit.get("exception_event_type"):
            event_types.add(str(emit["exception_event_type"]))
        if emit.get("capture_contract"):
            capture_contracts.add(str(emit["capture_contract"]))
        required_fields.update(str(item) for item in emit.get("required_fields", []))
    if not packet_classes:
        packet_classes.add("no_packet")
    return (
        {
            "packet_classes": _sorted(packet_classes),
            "event_types": _sorted(event_types),
            "mail_message_types": [],
            "capture_contracts": _sorted(capture_contracts),
            "required_fields": _sorted(required_fields),
            "blocked": False,
            "blocked_reason": "",
        },
        sorted(suppressed_rule_ids),
    )


def _compare_actual(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, bool]:
    comparisons = {
        "packet_classes": actual["packet_classes"] == sorted(expected.get("packet_classes", [])),
        "event_types": actual["event_types"] == sorted(expected.get("event_types", [])),
        "mail_message_types": actual["mail_message_types"]
        == sorted(expected.get("mail_message_types", [])),
        "capture_contracts": actual["capture_contracts"]
        == sorted(expected.get("capture_contracts", [])),
    }
    if "required_fields" in expected:
        comparisons["required_fields"] = actual.get("required_fields", []) == sorted(
            expected.get("required_fields", [])
        )
    if "blocked" in actual:
        comparisons["blocked"] = actual["blocked"] == bool(expected.get("blocked", False))
    if expected.get("blocked_reason"):
        comparisons["blocked_reason"] = actual.get("blocked_reason", "") == expected[
            "blocked_reason"
        ]
    return comparisons


def _blocked_audit_plan(
    *,
    actual: dict[str, Any],
    audit_actual: dict[str, Any],
    suppressed_rule_ids: list[str],
) -> dict[str, Any]:
    if not actual.get("blocked"):
        return {
            "should_record": False,
            "audit_scope": "none",
            "blocked_reason": "",
            "safe_packet_classes": [],
            "event_types": [],
            "capture_contracts": [],
            "required_fields": [],
            "suppressed_rule_ids": [],
            "instructions": [],
        }
    return {
        "should_record": True,
        "audit_scope": "repo_local_quarantine_or_audit",
        "blocked_reason": str(actual.get("blocked_reason") or ""),
        "safe_packet_classes": ["local_usage_only"],
        "event_types": sorted(str(item) for item in audit_actual.get("event_types", [])),
        "capture_contracts": sorted(
            str(item) for item in audit_actual.get("capture_contracts", [])
        ),
        "required_fields": sorted(str(item) for item in audit_actual.get("required_fields", [])),
        "suppressed_rule_ids": sorted(suppressed_rule_ids),
        "instructions": [
            "Record only blocker class, source repo id, reviewed rule ids, safe refs, "
            "hashes, gate states, and review ids in a repo-local quarantine/audit record.",
            "Do not emit outbound mail, exception packets, raw payloads, raw signals, "
            "private rows, logs, credentials, or copied source blobs.",
        ],
    }


def _declared_covered_rules(case: dict[str, Any]) -> list[str]:
    return sorted(str(item) for item in case.get("covered_rule_ids", []) or [])


def _reviewed_rule_ids(registry: dict[str, Any]) -> list[str]:
    return sorted(
        str(rule["rule_id"])
        for rule in registry.get("rules", [])
        if rule.get("review_status") == "reviewed"
    )


def evaluate_capture_case(
    case: dict[str, Any],
    registry: dict[str, Any],
    *,
    scenario_base: Path | None = None,
) -> dict[str, Any]:
    signals = set(case.get("signals", []))
    rule_actual, matched_rules, update_required = _rule_actual(case, registry)
    block_signals = set(registry.get("global_block_signals", []))
    blocking_hits = sorted(block_signals & signals)
    payload_issues = _payload_sample_issues(case)
    if blocking_hits:
        actual = _empty_actual(
            blocked=True,
            blocked_reason="global_block_signal:" + ",".join(blocking_hits),
        )
    elif payload_issues:
        actual = _empty_actual(
            blocked=True,
            blocked_reason="payload_screen:" + ",".join(payload_issues),
        )
    else:
        actual = rule_actual
    coverage_declared = "covered_rule_ids" in case
    declared_rules = _declared_covered_rules(case)
    matched_rule_ids = sorted(matched_rules)
    expected = case.get("expected", {})
    comparisons = {
        **_compare_actual(actual, expected),
        "update_required": update_required == bool(expected.get("update_required", False)),
        "covered_rule_ids": (declared_rules == matched_rule_ids) if coverage_declared else True,
    }
    passed = all(comparisons.values())
    result = {
        "scenario_id": case["scenario_id"],
        "pattern_family": case["pattern_family"],
        "covered_rule_ids": declared_rules,
        "coverage_declared": coverage_declared,
        "matched_rules": matched_rule_ids,
        "negative_controls": sorted(str(item) for item in case.get("negative_controls", [])),
        "phase6_update_vectors": sorted(
            str(item) for item in case.get("phase6_update_vectors", [])
        ),
        "payload_screen_issues": payload_issues,
        "repo_capture_surface_version": case.get("repo_capture_surface_version"),
        "registry_capture_surface_version": registry.get("capture_surface_version"),
        "update_required": update_required,
        "actual": actual,
        "expected": expected,
        "comparisons": comparisons,
        "passed": passed,
    }
    if case.get("observed"):
        observed = evaluate_observed_capture(
            case["observed"],
            scenario_base=scenario_base,
            expected=expected,
        )
        observed_comparisons = _compare_actual(observed["actual"], expected)
        observed["comparisons"] = observed_comparisons
        observed["passed"] = all(observed_comparisons.values()) and not observed["errors"]
        result["observed"] = observed
        result["passed"] = bool(result["passed"] and observed["passed"])
    return result


def suggest_exception_capture(
    hub_root: Path,
    *,
    signals: list[str],
    repo_capture_surface_version: str = "",
    payload_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile observable signals into a candidate capture plan.

    This is the repo-agent-facing read path for the capture-pattern registry. It
    does not prove the event occurred and does not authorize DAD or a repo to
    emit anything unsafe.
    """
    registry = load_capture_route_registry(hub_root)
    normalized_signals, signal_screen_issues = _normalized_capture_signals(signals)
    capture_surface_unknown = not str(repo_capture_surface_version or "").strip()
    surface_version = (
        str(repo_capture_surface_version).strip() if not capture_surface_unknown else "unknown"
    )
    case = {
        "signals": normalized_signals,
        "repo_capture_surface_version": surface_version,
        "payload_samples": payload_samples or [],
    }
    rule_actual, matched_rule_ids, update_required = _rule_actual(case, registry)
    suppressed_actual, suppressed_rule_ids = _suppressed_rule_actual(case, registry)
    block_signals = set(registry.get("global_block_signals", []))
    blocking_hits = sorted(block_signals & set(normalized_signals))
    payload_issues = _payload_sample_issues(case)
    if signal_screen_issues:
        actual = _empty_actual(
            blocked=True,
            blocked_reason="signal_screen:" + ",".join(signal_screen_issues),
        )
    elif capture_surface_unknown:
        actual = rule_actual
        update_required = True
    elif blocking_hits:
        actual = _empty_actual(
            blocked=True,
            blocked_reason="global_block_signal:" + ",".join(blocking_hits),
        )
    elif payload_issues:
        actual = _empty_actual(
            blocked=True,
            blocked_reason="payload_screen:" + ",".join(payload_issues),
        )
    else:
        actual = rule_actual
    audit_actual = rule_actual if matched_rule_ids else suppressed_actual

    reviewed_rules = {
        str(rule.get("rule_id") or ""): rule
        for rule in registry.get("rules", [])
        if isinstance(rule, dict)
    }
    matched_rules: list[dict[str, Any]] = []
    recommended_packets: list[dict[str, Any]] = []
    for rule_id in matched_rule_ids:
        rule = reviewed_rules.get(rule_id, {})
        emit = rule.get("emit") if isinstance(rule.get("emit"), dict) else {}
        matched_rules.append(
            {
                "rule_id": rule_id,
                "pattern_family": str(rule.get("pattern_family") or ""),
                "review_status": str(rule.get("review_status") or ""),
                "min_capture_surface_version": str(
                    rule.get("min_capture_surface_version") or ""
                ),
                "required_fields": sorted(str(item) for item in emit.get("required_fields", [])),
                "danger_if_missed": str(rule.get("danger_if_missed") or ""),
                "rationale": str(emit.get("rationale") or ""),
            }
        )
        if actual["blocked"]:
            continue
        recommended_packets.append(
            {
                "rule_id": rule_id,
                "packet_classes": sorted(str(item) for item in emit.get("packet_classes", [])),
                "mail_message_type": str(emit.get("mail_message_type") or ""),
                "exception_event_type": str(emit.get("exception_event_type") or ""),
                "capture_contract": str(emit.get("capture_contract") or ""),
                "severity": str(emit.get("severity") or ""),
                "required_fields": sorted(str(item) for item in emit.get("required_fields", [])),
            }
        )

    return {
        "generated_at": utc_now(),
        "suggestion_id": "dad:exception-capture-suggestion",
        "registry_ref": CAPTURE_PATTERN_REGISTRY.as_posix(),
        "methodology_ref": CAPTURE_ROUTE_METHODOLOGY_REF,
        "methodology_hash": capture_route_methodology_hash(hub_root),
        "repo_capture_surface_version": surface_version,
        "capture_surface_version_unknown": capture_surface_unknown,
        "registry_capture_surface_version": str(registry.get("capture_surface_version") or ""),
        "update_required": update_required,
        "signals": normalized_signals,
        "signal_screen_issues": signal_screen_issues,
        "matched_rule_ids": sorted(matched_rule_ids),
        "suppressed_rule_ids": suppressed_rule_ids,
        "matched_rules": matched_rules,
        "payload_screen_issues": payload_issues,
        "blocking_signals": blocking_hits,
        "actual": actual,
        "recommended_packets": recommended_packets,
        "blocked_audit": _blocked_audit_plan(
            actual=actual,
            audit_actual=audit_actual,
            suppressed_rule_ids=suppressed_rule_ids,
        ),
        "next_actions": _capture_suggest_next_actions(
            actual=actual,
            update_required=update_required,
            matched_rule_ids=matched_rule_ids,
            capture_surface_unknown=capture_surface_unknown,
        ),
        "authority_boundary": (
            "Capture suggestions are deterministic candidate guidance compiled from "
            "the reviewed capture-pattern registry. They do not prove source truth, "
            "approve public release, authorize source mutation, or permit raw logs, "
            "secrets, private rows, hidden reasoning, or copied source blobs."
        ),
    }


def _capture_suggest_next_actions(
    *,
    actual: dict[str, Any],
    update_required: bool,
    matched_rule_ids: list[str],
    capture_surface_unknown: bool = False,
) -> list[str]:
    actions: list[str] = []
    if actual.get("blocked"):
        actions.append(
            "Do not emit outbound mail or exception packets until the blocked "
            "payload/signal is reduced to safe metadata or reviewed locally."
        )
        actions.append(
            "Write only a repo-local quarantine/audit metadata record with blocker "
            "class, safe refs, hashes, gate states, and review ids."
        )
        return actions
    if capture_surface_unknown:
        actions.append(
            "Read .digital-asset/dad-integration.json and pass the repo capture "
            "surface version before treating this suggestion as complete."
        )
    if update_required:
        actions.append(
            "Refresh the repo capture surface before treating this suggestion as "
            "complete; older surfaces may omit required fields."
        )
    if not matched_rule_ids:
        actions.append(
            "No reviewed capture rule matched. Use direct exception record guidance "
            "or send a taxonomy_suggestion only if existing types cannot represent "
            "the safe metadata."
        )
    else:
        actions.append(
            "Populate every required field with short safe metadata, pointers, or "
            "hashes before appending candidate mail, exception, or fix-outcome JSONL."
        )
    actions.append("Keep the repo-local packet candidate-only until local review.")
    return actions


def _normalized_capture_signals(signals: list[str]) -> tuple[list[str], list[str]]:
    normalized: set[str] = set()
    issues: set[str] = set()
    for value in signals:
        text = str(value or "").strip()
        if not text:
            continue
        if not CAPTURE_SIGNAL_RE.fullmatch(text):
            issues.add("unsafe_signal_token")
            continue
        _, screen_issues = screen_exception_record({"signal": text})
        if screen_issues:
            issues.add("unsafe_signal_payload")
            continue
        normalized.add(text)
    return sorted(normalized), sorted(issues)


def _resolve_observed_path(value: str, scenario_base: Path | None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if scenario_base is not None:
        return scenario_base / path
    return path


def _read_jsonl(path: Path, errors: list[str], *, path_label: str = "") -> list[dict[str, Any]]:
    label = path_label or path.name
    if not path.exists():
        errors.append(f"missing_observed_file:{label}")
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"malformed_jsonl:{label}:{line_number}:{exc.msg}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"non_object_jsonl:{label}:{line_number}")
            continue
        records.append(payload)
    return records


def _required_value_is_usable(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in PLACEHOLDER_REQUIRED_VALUES
    if isinstance(value, list):
        return any(_required_value_is_usable(item) for item in value)
    if isinstance(value, dict):
        return any(_required_value_is_usable(item) for item in value.values())
    return True


def _usable_field_names(record: dict[str, Any]) -> set[str]:
    fields = {str(key) for key, value in record.items() if _required_value_is_usable(value)}
    payload = record.get("payload")
    if isinstance(payload, dict):
        fields.update(
            str(key) for key, value in payload.items() if _required_value_is_usable(value)
        )
    for ref_key in [
        "trace_refs",
        "context_refs",
        "validation_refs",
        "asset_refs",
        "harness_refs",
        "lesson_refs",
        "fix_refs",
    ]:
        for ref in record.get(ref_key, []) or []:
            text = str(ref or "")
            if text.startswith("capture-field:") and text.endswith(":present"):
                field = text.removeprefix("capture-field:").removesuffix(":present")
                if field:
                    fields.add(field)
            elif ":" in text:
                field, value = text.split(":", 1)
                if field and _required_value_is_usable(value):
                    fields.add(field)
    return fields


def _observed_record_matches_expected(
    record: dict[str, Any],
    outbox_key: str,
    expected: dict[str, Any] | None,
) -> bool:
    if expected is None:
        return False
    if outbox_key == "mail_outbox":
        expected_types = {str(item) for item in expected.get("mail_message_types", [])}
        return bool(record.get("message_type") and str(record["message_type"]) in expected_types)
    if outbox_key == "exception_outbox":
        expected_events = {str(item) for item in expected.get("event_types", [])}
        expected_contracts = {str(item) for item in expected.get("capture_contracts", [])}
        return bool(
            (record.get("event_type") and str(record["event_type"]) in expected_events)
            or (
                record.get("capture_contract")
                and str(record["capture_contract"]) in expected_contracts
            )
        )
    if outbox_key == "fix_outcomes":
        expected_classes = {str(item) for item in expected.get("packet_classes", [])}
        expected_contracts = {str(item) for item in expected.get("capture_contracts", [])}
        return _is_fix_outcome_row(record) and (
            "fix_outcome" in expected_classes or "fix_outcome" in expected_contracts
        )
    return False


def _observed_local_path_screen_values(
    record: dict[str, Any],
    expected_required_fields: set[str],
) -> Iterable[str]:
    payload = record.get("payload")
    payload_fields: set[str] = set()
    if isinstance(payload, dict):
        payload_fields = set(str(key) for key in payload)
        yield from _iter_payload_strings(payload)
    for field in sorted(expected_required_fields):
        if field in payload_fields:
            continue
        if field in record:
            yield from _iter_payload_strings(record[field])
    for field in ["safe_summary", "summary"]:
        if field in record:
            yield from _iter_payload_strings(record[field])


def _observed_payload_issues(
    record: dict[str, Any],
    expected_required_fields: set[str],
) -> list[str]:
    _, issues = screen_exception_record(record)
    text = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
    if any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS):
        issues.append("prompt_injection_like_text")
    for value in _observed_local_path_screen_values(record, expected_required_fields):
        if _looks_like_local_path_payload(value):
            issues.append("local_path_like_payload")
    return sorted(set(issues))


def _is_fix_outcome_row(record: dict[str, Any]) -> bool:
    return (
        str(record.get("fix_id", "")).startswith("dad:exception-fix:")
        and str(record.get("event_id", "")).startswith("dad:exception-event:")
        and str(record.get("capture_contract", "")) == "fix_outcome"
        and bool(str(record.get("decision", "")).strip())
    )


def evaluate_observed_capture(
    observed: dict[str, Any],
    *,
    scenario_base: Path | None = None,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet_classes: set[str] = set()
    event_types: set[str] = set()
    mail_message_types: set[str] = set()
    capture_contracts: set[str] = set()
    expected_required_fields = {
        str(item) for item in (expected or {}).get("required_fields", []) or []
    }
    best_matching_required_fields: set[str] = set()
    complete_required_row_found = not expected_required_fields
    errors: list[str] = []
    observed_paths: list[str] = []

    for key, packet_class in [
        ("mail_outbox", "ordinary_mail"),
        ("exception_outbox", "exception_event"),
        ("fix_outcomes", "fix_outcome"),
    ]:
        raw_path = observed.get(key)
        if not raw_path:
            continue
        path = _resolve_observed_path(str(raw_path), scenario_base)
        path_label = safe_relative(path, scenario_base) if scenario_base else path.name
        observed_paths.append(path_label)
        rows = _read_jsonl(path, errors, path_label=path_label)
        has_valid_packet_row = False
        if rows and key != "fix_outcomes":
            has_valid_packet_row = True
        elif key == "fix_outcomes":
            has_valid_packet_row = any(_is_fix_outcome_row(row) for row in rows)
        if has_valid_packet_row:
            packet_classes.add(packet_class)
        for row in rows:
            for issue in _observed_payload_issues(row, expected_required_fields):
                errors.append(f"unsafe_observed_payload:{path_label}:{issue}")
            if _observed_record_matches_expected(row, key, expected):
                usable_fields = _usable_field_names(row)
                row_required_fields = usable_fields & expected_required_fields
                if len(row_required_fields) > len(best_matching_required_fields):
                    best_matching_required_fields = row_required_fields
                if expected_required_fields <= usable_fields:
                    complete_required_row_found = True
            if key == "mail_outbox" and row.get("message_type"):
                mail_message_types.add(str(row["message_type"]))
            if key == "exception_outbox":
                if row.get("event_type"):
                    event_types.add(str(row["event_type"]))
                if row.get("capture_contract"):
                    capture_contracts.add(str(row["capture_contract"]))
            if key == "fix_outcomes":
                if _is_fix_outcome_row(row):
                    capture_contracts.add("fix_outcome")
    if not packet_classes:
        packet_classes.add("no_packet")
    return {
        "paths": observed_paths,
        "actual": {
            "packet_classes": _sorted(packet_classes),
            "event_types": _sorted(event_types),
            "mail_message_types": _sorted(mail_message_types),
            "capture_contracts": _sorted(capture_contracts),
            "required_fields": sorted(expected_required_fields)
            if complete_required_row_found
            else sorted(best_matching_required_fields),
            "blocked": False,
            "blocked_reason": "",
        },
        "errors": errors,
        "passed": False,
    }


def _simulation_expected(case: dict[str, Any]) -> dict[str, Any]:
    expected = json.loads(json.dumps(case.get("expected", {})))
    if expected.get("packet_classes") != ["no_packet"]:
        required = set(str(item) for item in expected.get("required_fields", []) or [])
        required.update(SIMULATED_EMISSION_PROVENANCE_FIELDS)
        expected["required_fields"] = sorted(required)
    return expected


def _simulation_field_value(
    field: str,
    *,
    scenario_id: str,
    rule_id: str,
    suggestion: dict[str, Any],
    initial_update_required: bool,
) -> Any:
    values: dict[str, Any] = {
        "suggestion_id": suggestion["suggestion_id"],
        "methodology_hash": suggestion["methodology_hash"],
        "matched_rule_ids": suggestion["matched_rule_ids"],
        "update_required": bool(suggestion.get("update_required", False)),
        "initial_update_required": initial_update_required,
        "source_repo": "dad-capture-emission-simulation",
        "source_visibility": "internal",
        "safe_summary": f"Safe simulated metadata for {scenario_id}.",
        "validation_refs": [f"simulated-validation:{scenario_id}"],
        "regression_test_refs": [f"simulated-regression:{scenario_id}"],
        "event_id": "created-by-simulation-writer",
        "decision": "deferred",
        "validation_status": "writer_computed",
        "owner_authority": "source_repo_local_review",
        "event_lookup_status": "writer_computed",
        "remaining_risks": ["candidate_metadata_only"],
        "language": "rust",
        "proof_surface": "synthetic-capture-emission-simulation",
        "source_id_or_url": f"dad://capture-scenario/{scenario_id}",
        "target_dad_surface": "exception-capture-pattern-registry",
        "validation_or_eval_idea": "Run capture-simulate-emission and observed-check.",
        "why_ai_coding_may_improve": "Captures reusable language-frontier evidence as safe metadata.",
        "applicability_limits": "Synthetic metadata only; local review decides adoption.",
    }
    if field in values:
        return values[field]
    return f"simulated-{field}-for-{scenario_id}-via-{rule_id.rsplit(':', 1)[-1]}"


def _simulation_payload(
    *,
    required_fields: list[str],
    scenario_id: str,
    rule_id: str,
    suggestion: dict[str, Any],
    initial_update_required: bool,
) -> dict[str, Any]:
    payload = {
        field: _simulation_field_value(
            field,
            scenario_id=scenario_id,
            rule_id=rule_id,
            suggestion=suggestion,
            initial_update_required=initial_update_required,
        )
        for field in sorted(set(required_fields) | SIMULATED_EMISSION_PROVENANCE_FIELDS)
    }
    payload["source_scenario_id"] = scenario_id
    payload["source_rule_id"] = rule_id
    payload["emission_mode"] = "synthetic_temp_repo_real_writer"
    return payload


def _simulation_trace_refs(
    *,
    required_fields: list[str],
    payload: dict[str, Any],
    scenario_id: str,
    rule_id: str,
    initial_update_required: bool,
) -> list[str]:
    refs = [
        f"suggestion_id:{payload['suggestion_id']}",
        f"methodology_hash:{payload['methodology_hash']}",
        "matched_rule_ids:" + ",".join(str(item) for item in payload["matched_rule_ids"]),
        f"update_required:{str(payload['update_required']).lower()}",
        f"initial_update_required:{str(initial_update_required).lower()}",
        f"scenario_id:{scenario_id}",
        f"matched_rule_id:{rule_id}",
    ]
    refs.extend(
        f"capture-field:{field}:present"
        for field in sorted(set(required_fields) | SIMULATED_EMISSION_PROVENANCE_FIELDS)
    )
    return refs


def _emit_simulated_capture_packet(
    hub_root: Path,
    repo: Path,
    *,
    scenario_id: str,
    packet: dict[str, Any],
    suggestion: dict[str, Any],
    initial_update_required: bool,
) -> dict[str, Any]:
    rule_id = str(packet.get("rule_id") or "")
    packet_classes = {str(item) for item in packet.get("packet_classes", []) or []}
    required_fields = [str(item) for item in packet.get("required_fields", []) or []]
    payload = _simulation_payload(
        required_fields=required_fields,
        scenario_id=scenario_id,
        rule_id=rule_id,
        suggestion=suggestion,
        initial_update_required=initial_update_required,
    )
    trace_refs = _simulation_trace_refs(
        required_fields=required_fields,
        payload=payload,
        scenario_id=scenario_id,
        rule_id=rule_id,
        initial_update_required=initial_update_required,
    )
    emitted: dict[str, Any] = {
        "rule_id": rule_id,
        "packet_classes": sorted(packet_classes),
        "outbox_paths": [],
        "screening_issues": [],
    }
    if "ordinary_mail" in packet_classes:
        result = compose_mail(
            repo,
            message_type=str(packet.get("mail_message_type") or "capability_suggestion"),
            target_repo="dad-central",
            summary=f"Simulated capture emission for {scenario_id}.",
            payload=payload,
            evidence=[f"dad://capture-scenario/{scenario_id}", rule_id],
            suggested_actions=[
                "Review as candidate exception-capture simulation evidence.",
            ],
            sensitivity="internal",
            dedupe_key=f"dad-capture-emission:{scenario_id}:{rule_id}:mail",
            composed_by="codex",
            allow_similar=True,
        )
        emitted["outbox_paths"].append(MAIL_MIRROR_DIR.joinpath("outbox.jsonl").as_posix())
        emitted.setdefault("mail_ids", []).append(result["record"]["mail_id"])
    if "exception_event" in packet_classes:
        change_context = None
        if str(packet.get("exception_event_type") or "") == "code_change_exception":
            change_context = {
                "change_ref": payload.get("change_ref"),
                "changed_surface": payload.get("changed_surface"),
                "exception_reason": payload.get("exception_reason"),
                "validation_ref_or_gap": payload.get("validation_ref_or_gap"),
            }
        result = record_exception_event(
            hub_root,
            repo,
            event_type=str(packet.get("exception_event_type") or "failed_command"),
            summary=f"Simulated capture emission for {scenario_id}.",
            stage="postflight",
            severity=str(packet.get("severity") or "medium"),
            capture_contract=str(packet.get("capture_contract") or "postflight_exception"),
            agent="codex",
            source_visibility="internal",
            command=["asset-dir", "exceptions", "capture-simulate-emission"],
            exit_code=0,
            duration_ms=1,
            context_refs=[f"dad://capture-scenario/{scenario_id}", rule_id],
            validation_refs=[f"simulated-validation:{scenario_id}"],
            trace_refs=trace_refs,
            change_context=change_context,
        )
        emitted["outbox_paths"].append(EXCEPTION_OUTBOX.as_posix())
        emitted["screening_issues"].extend(result.get("screening_issues", []))
        emitted.setdefault("event_ids", []).append(result["event"]["event_id"])
    if "fix_outcome" in packet_classes:
        event = record_exception_event(
            hub_root,
            repo,
            event_type="failed_command",
            summary=f"Synthetic source event for fix outcome {scenario_id}.",
            stage="postflight",
            severity="medium",
            capture_contract="failed_command",
            agent="codex",
            source_visibility="internal",
            command=["asset-dir", "exceptions", "capture-simulate-emission"],
            exit_code=1,
            duration_ms=1,
            context_refs=[f"dad://capture-scenario/{scenario_id}", rule_id],
            validation_refs=[f"simulated-validation:{scenario_id}"],
            trace_refs=trace_refs,
        )
        result = record_exception_fix_outcome(
            hub_root,
            repo,
            event_id=str(event["event"]["event_id"]),
            decision="deferred",
            summary=f"Simulated fix outcome for {scenario_id}.",
            recorded_by="codex",
            validation_refs=[f"simulated-validation:{scenario_id}"],
            regression_test_refs=[f"simulated-regression:{scenario_id}"],
            fix_refs=[f"dad://capture-scenario/{scenario_id}/fix"],
            asset_refs=trace_refs,
            owner_authority="source_repo_local_review",
            expiry=f"revisit-after:{scenario_id}",
            remaining_risks=["candidate_metadata_only"],
        )
        emitted["outbox_paths"].append(FIX_OUTCOME_PATH.as_posix())
        emitted["screening_issues"].extend(event.get("screening_issues", []))
        emitted["screening_issues"].extend(result.get("screening_issues", []))
        emitted.setdefault("event_ids", []).append(event["event"]["event_id"])
        emitted.setdefault("fix_ids", []).append(result["fix_outcome"]["fix_id"])
    return emitted


def _case_emission_suggestion(
    hub_root: Path,
    case: dict[str, Any],
    *,
    repo_capture_surface_version: str,
) -> dict[str, Any]:
    return suggest_exception_capture(
        hub_root,
        signals=[str(item) for item in case.get("signals", []) or []],
        repo_capture_surface_version=repo_capture_surface_version,
        payload_samples=[
            sample for sample in case.get("payload_samples", []) or [] if isinstance(sample, dict)
        ],
    )


def _simulate_capture_case_emission(
    hub_root: Path,
    case: dict[str, Any],
    registry: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    scenario_id = str(case["scenario_id"])
    repo = workspace / re.sub(r"[^a-zA-Z0-9_.-]+", "-", scenario_id).strip("-")
    repo.mkdir(parents=True, exist_ok=True)
    initial_suggestion = _case_emission_suggestion(
        hub_root,
        case,
        repo_capture_surface_version=str(case.get("repo_capture_surface_version") or ""),
    )
    emission_surface_version = str(case.get("repo_capture_surface_version") or "")
    if initial_suggestion["update_required"]:
        emission_surface_version = str(registry.get("capture_surface_version") or "")
    emission_suggestion = (
        _case_emission_suggestion(
            hub_root,
            case,
            repo_capture_surface_version=emission_surface_version,
        )
        if emission_surface_version != initial_suggestion["repo_capture_surface_version"]
        else initial_suggestion
    )
    emitted_packets: list[dict[str, Any]] = []
    for packet in emission_suggestion.get("recommended_packets", []):
        emitted_packets.append(
            _emit_simulated_capture_packet(
                hub_root,
                repo,
                scenario_id=scenario_id,
                packet=packet,
                suggestion=emission_suggestion,
                initial_update_required=bool(initial_suggestion["update_required"]),
            )
        )
    emitted_packet_classes = {
        packet_class
        for packet in emitted_packets
        for packet_class in packet.get("packet_classes", [])
    }
    candidate_observed_paths: dict[str, Path] = {}
    if "ordinary_mail" in emitted_packet_classes:
        candidate_observed_paths["mail_outbox"] = MAIL_MIRROR_DIR.joinpath("outbox.jsonl")
    if "exception_event" in emitted_packet_classes:
        candidate_observed_paths["exception_outbox"] = EXCEPTION_OUTBOX
    if "fix_outcome" in emitted_packet_classes:
        candidate_observed_paths["fix_outcomes"] = FIX_OUTCOME_PATH
    observed_paths = {
        key: path.as_posix()
        for key, path in candidate_observed_paths.items()
        if (repo / path).exists()
    }
    expected = _simulation_expected(case)
    observed_expected = json.loads(json.dumps(expected))
    if expected.get("blocked"):
        observed_expected["blocked"] = False
        observed_expected.pop("blocked_reason", None)
    observed = evaluate_observed_capture(
        observed_paths,
        scenario_base=repo,
        expected=observed_expected,
    )
    observed["comparisons"] = _compare_actual(observed["actual"], observed_expected)
    observed["passed"] = all(observed["comparisons"].values()) and not observed["errors"]
    suggestion_matches_expected = _compare_actual(emission_suggestion["actual"], case["expected"])
    suggestion_matches_expected["update_required"] = (
        bool(initial_suggestion["update_required"])
        == bool(case.get("expected", {}).get("update_required", False))
    )
    passed = (
        all(suggestion_matches_expected.values())
        and observed["passed"]
        and not any(item.get("screening_issues") for item in emitted_packets)
    )
    return {
        "scenario_id": scenario_id,
        "pattern_family": str(case.get("pattern_family") or ""),
        "initial_repo_capture_surface_version": initial_suggestion[
            "repo_capture_surface_version"
        ],
        "emission_repo_capture_surface_version": emission_surface_version,
        "registry_capture_surface_version": initial_suggestion[
            "registry_capture_surface_version"
        ],
        "initial_update_required": bool(initial_suggestion["update_required"]),
        "emission_update_required": bool(emission_suggestion["update_required"]),
        "matched_rule_ids": emission_suggestion["matched_rule_ids"],
        "recommended_packet_count": len(emission_suggestion.get("recommended_packets", [])),
        "emitted_packet_count": len(emitted_packets),
        "emitted_packet_classes": sorted(
            {
                packet_class
                for packet in emitted_packets
                for packet_class in packet.get("packet_classes", [])
            }
        )
        or ["no_packet"],
        "emitted_packets": emitted_packets,
        "expected": expected,
        "observed_expected": observed_expected,
        "suggestion_comparisons": suggestion_matches_expected,
        "observed": observed,
        "passed": passed,
        "authority_boundary": (
            "Simulation writes only to a temporary repo using DAD packet writers, "
            "then validates observed JSONL output. It does not deliver mail, mutate "
            "source repos, approve public release, or prove the synthetic event occurred."
        ),
    }


def write_exception_capture_emission_simulation(
    hub_root: Path,
    scenarios_path: Path,
    *,
    output: Path | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    scenarios = load_capture_scenarios(scenarios_path)
    registry = load_capture_route_registry(hub_root)
    cases = [
        case
        for case in scenarios.get("cases", [])
        if isinstance(case, dict) and case.get("review_status") == "reviewed"
    ]
    full_reviewed_case_count = len(cases)
    full_reviewed_scenario_ids = [str(case.get("scenario_id", "")) for case in cases]
    if limit is not None and limit > 0:
        cases = cases[:limit]
    emitted_scenario_ids = [str(case.get("scenario_id", "")) for case in cases]
    emitted_scenario_id_set = set(emitted_scenario_ids)
    omitted_reviewed_scenario_ids = [
        scenario_id
        for scenario_id in full_reviewed_scenario_ids
        if scenario_id and scenario_id not in emitted_scenario_id_set
    ]
    limited = bool(omitted_reviewed_scenario_ids)
    temp_parent = hub_root / ".tmp" / "capture-emission"
    temp_parent.mkdir(parents=True, exist_ok=True)
    workspace = temp_parent / f"dad-capture-emission-{uuid4().hex[:12]}"
    workspace.mkdir(parents=True, exist_ok=False)
    rows = [
        _simulate_capture_case_emission(hub_root, case, registry, workspace)
        for case in cases
    ]
    failed = [row for row in rows if not row["passed"]]
    initial_update_required_count = sum(1 for row in rows if row["initial_update_required"])
    gate_supporting = bool(rows) and not failed and not limited
    report = {
        "generated_at": utc_now(),
        "report_id": "dad:exception-capture-emission-simulation",
        "scenario_path": safe_relative(scenarios_path, hub_root),
        "registry_ref": CAPTURE_PATTERN_REGISTRY.as_posix(),
        "methodology_ref": CAPTURE_ROUTE_METHODOLOGY_REF,
        "methodology_hash": capture_route_methodology_hash(hub_root),
        "input_hashes": _input_hashes(hub_root, scenarios_path),
        "coverage_status": "limited_diagnostic" if limited else "full_reviewed_scenario_set",
        "limited": limited,
        "full_reviewed_case_count": full_reviewed_case_count,
        "emitted_reviewed_case_count": len(rows),
        "omitted_reviewed_scenario_ids": omitted_reviewed_scenario_ids,
        "case_count": len(rows),
        "passed_count": len(rows) - len(failed),
        "failed_count": len(failed),
        "initial_update_required_count": initial_update_required_count,
        "refreshed_emission_count": sum(
            1
            for row in rows
            if row["initial_repo_capture_surface_version"]
            != row["emission_repo_capture_surface_version"]
        ),
        "required_provenance_fields": sorted(SIMULATED_EMISSION_PROVENANCE_FIELDS),
        "cases": rows,
        "phase6_machine_gate_evidence": {
            "evidence_scope": PHASE6_MACHINE_EVIDENCE_SCOPE,
            "machine_status": "passed" if gate_supporting else "failed",
            "coverage_status": "limited_diagnostic"
            if limited
            else "full_reviewed_scenario_set",
            "limited": limited,
            "human_review_required": True,
            "human_gate_satisfied": False,
            "supports_human_gate_ids": [
                "phase-6-capture-completeness-harness-reviewed",
                "phase-6-pattern-update-simulation-reviewed",
            ]
            if gate_supporting
            else [],
            "missing_reviewed_scenario_ids": omitted_reviewed_scenario_ids,
        },
        "authority_boundary": (
            "Machine simulation evidence only. This gate proves reviewed synthetic "
            "signals can flow through capture-suggest into real DAD packet writers "
            "and back through observed JSONL checks in a temp repo. It does not "
            "approve human roadmap gates, mutate target repos, or certify source truth."
        ),
    }
    output_path = _capture_output_path(hub_root, output, CAPTURE_EMISSION_SIMULATION_JSON)
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, CAPTURE_EMISSION_SIMULATION_MD)
    )
    lines = [
        "# Exception Capture Emission Simulation",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Cases: {report['case_count']}",
        f"- Passed: {report['passed_count']}",
        f"- Failed: {report['failed_count']}",
        f"- Initial update-required cases: {report['initial_update_required_count']}",
        f"- Refreshed before emission: {report['refreshed_emission_count']}",
        f"- Methodology hash: `{report['methodology_hash']}`",
        "",
        "Boundary: temp-repo writer simulation only. This report does not deliver mail "
        "or approve roadmap human gates.",
        "",
        "## Cases",
        "",
        "| Scenario | Pattern | Initial Update | Emitted | Observed | Result |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        emitted = ", ".join(f"`{item}`" for item in row["emitted_packet_classes"])
        observed_status = "passed" if row["observed"]["passed"] else "failed"
        result = "passed" if row["passed"] else "failed"
        lines.append(
            "| "
            + f"`{row['scenario_id']}` | `{row['pattern_family']}` | "
            + f"`{row['initial_update_required']}` | {emitted} | "
            + f"`{observed_status}` | `{result}` |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _phase6_source_report(
    hub_root: Path,
    key: str,
    rel_path: Path,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path = exception_capture_data_path(hub_root, rel_path)
    row: dict[str, Any] = {
        "report_key": key,
        "path": rel_path.as_posix(),
        "exists": path.exists(),
        "content_hash": "",
        "generated_at": "",
        "report_id": "",
        "audit_id": "",
        "read_status": "missing",
        "error": "",
    }
    if not path.exists():
        return row, None
    try:
        row["content_hash"] = f"sha256:{sha256_file(path)}"
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        row["read_status"] = "malformed"
        row["error"] = f"{type(exc).__name__}:{exc}"
        return row, None
    row["read_status"] = "loaded"
    row["generated_at"] = str(payload.get("generated_at", ""))
    row["report_id"] = str(payload.get("report_id", ""))
    row["audit_id"] = str(payload.get("audit_id", ""))
    return row, payload


def _phase6_gate_status_from_report(
    payload: dict[str, Any] | None,
    gate_id: str,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return "missing_report", {}
    evidence = payload.get("phase6_machine_gate_evidence")
    if not isinstance(evidence, dict):
        return "missing_phase6_evidence", {}
    gates = evidence.get("gates")
    if not isinstance(gates, dict):
        return "missing_gate_map", {}
    gate = gates.get(_phase6_machine_evidence_key(gate_id))
    if not isinstance(gate, dict):
        return "missing_gate", {}
    return str(gate.get("machine_status") or "unknown"), {
        "evidence_id": str(gate.get("evidence_id", "")),
        "human_gate_satisfied": bool(gate.get("human_gate_satisfied", False)),
        "evidence_scope": str(gate.get("evidence_scope", "")),
    }


def _phase6_emission_support_status(
    payload: dict[str, Any] | None,
    gate_id: str,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return "missing_report", {}
    evidence = payload.get("phase6_machine_gate_evidence")
    if not isinstance(evidence, dict):
        return "missing_phase6_evidence", {}
    gate_ids = {str(item) for item in evidence.get("supports_human_gate_ids", []) or []}
    machine_status = str(evidence.get("machine_status") or "unknown")
    limited = bool(evidence.get("limited") or payload.get("limited"))
    status = "passed" if machine_status == "passed" and gate_id in gate_ids and not limited else "failed"
    if gate_id not in gate_ids:
        status = "missing_gate_support"
    if limited:
        status = "limited_diagnostic"
    return status, {
        "machine_status": machine_status,
        "coverage_status": str(evidence.get("coverage_status") or payload.get("coverage_status") or ""),
        "limited": limited,
        "human_gate_satisfied": bool(evidence.get("human_gate_satisfied", False)),
        "evidence_scope": str(evidence.get("evidence_scope", "")),
    }


def build_phase6_machine_evidence_summary(
    hub_root: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    source_reports: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any] | None] = {}
    input_hashes: dict[str, str] = {}
    for key, rel_path in PHASE6_SUMMARY_REPORTS.items():
        row, payload = _phase6_source_report(hub_root, key, rel_path)
        source_reports.append(row)
        payloads[key] = payload
        if row["content_hash"]:
            input_hashes[row["path"]] = str(row["content_hash"])

    gates: list[dict[str, Any]] = []
    for gate_id in PHASE6_HUMAN_GATE_IDS:
        contributors: list[dict[str, Any]] = []
        for report_key, contributor_kind in PHASE6_SUMMARY_REQUIRED_CONTRIBUTORS[gate_id]:
            if contributor_kind == "support":
                status, details = _phase6_emission_support_status(payloads.get(report_key), gate_id)
            else:
                status, details = _phase6_gate_status_from_report(payloads.get(report_key), gate_id)
            contributors.append(
                {
                    "report_key": report_key,
                    "report_path": PHASE6_SUMMARY_REPORTS[report_key].as_posix(),
                    "contributor_kind": contributor_kind,
                    "machine_status": status,
                    "details": details,
                }
            )
        effective_status = (
            "passed"
            if contributors and all(row["machine_status"] == "passed" for row in contributors)
            else "failed"
        )
        gates.append(
            {
                "gate_id": gate_id,
                "machine_status": effective_status,
                "human_review_required": True,
                "human_gate_satisfied": False,
                "contributors": contributors,
            }
        )

    blocked_gate_ids = [row["gate_id"] for row in gates if row["machine_status"] != "passed"]
    source_report_failures = [
        row["report_key"] for row in source_reports if row["read_status"] != "loaded"
    ]
    overall_machine_status = (
        "passed" if not blocked_gate_ids and not source_report_failures else "failed"
    )
    return {
        "generated_at": generated_at or utc_now(),
        "report_id": "dad:phase6-exception-capture-machine-evidence-summary",
        "phase_id": "phase-6-exceptions-lake-and-capture-completeness",
        "evidence_scope": PHASE6_MACHINE_EVIDENCE_SCOPE,
        "overall_machine_status": overall_machine_status,
        "human_review_required": True,
        "human_gate_satisfied": False,
        "phase6_human_gate_ids": list(PHASE6_HUMAN_GATE_IDS),
        "blocked_gate_ids": blocked_gate_ids,
        "source_report_failures": source_report_failures,
        "source_reports": source_reports,
        "gates": gates,
        "input_hashes": input_hashes,
        "pass_condition": (
            "All required Phase 6 source reports load successfully and every Phase 6 "
            "human gate has all required machine contributors with machine_status=passed. "
            "This remains machine evidence only and never satisfies human gates."
        ),
        "recommended_next_actions": [
            "Review blocked_gate_ids before any Phase 6 human gate decision.",
            "If observed-audit is blocked, resolve current-surface gaps or document protected/policy-blocked status before claiming all-repo capture completeness.",
        ],
        "authority_boundary": (
            "This summary compiles machine evidence from Phase 6 reports. It does not "
            "satisfy roadmap human gates, mutate repos, deliver mail, approve public "
            "release, or certify source truth."
        ),
    }


def _phase6_machine_evidence_summary_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 6 Exception Capture Machine Evidence Summary",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Overall machine status: `{report['overall_machine_status']}`",
        f"- Human gate satisfied: `{report['human_gate_satisfied']}`",
        "",
        "Boundary: this is machine evidence only. It does not satisfy roadmap human gates.",
        "",
        "## Gates",
        "",
        "| Gate | Machine status | Contributors |",
        "| --- | --- | --- |",
    ]
    for gate in report["gates"]:
        contributors = ", ".join(
            f"{row['report_key']}:{row['machine_status']}" for row in gate["contributors"]
        )
        lines.append(
            f"| `{gate['gate_id']}` | `{gate['machine_status']}` | {contributors} |"
        )
    lines.extend(["", "## Source Reports", "", "| Report | Status | Generated |", "| --- | --- | --- |"])
    for row in report["source_reports"]:
        lines.append(
            f"| `{row['path']}` | `{row['read_status']}` | `{row['generated_at']}` |"
        )
    if report["blocked_gate_ids"]:
        lines.extend(["", "## Blocked Gates", ""])
        for gate_id in report["blocked_gate_ids"]:
            lines.append(f"- `{gate_id}`")
    lines.extend(["", "## Authority Boundary", "", str(report["authority_boundary"]), ""])
    return "\n".join(lines)


def write_phase6_machine_evidence_summary(
    hub_root: Path,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    report = build_phase6_machine_evidence_summary(hub_root)
    output_path = _capture_output_path(
        hub_root, output, PHASE6_MACHINE_EVIDENCE_SUMMARY_JSON
    )
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, PHASE6_MACHINE_EVIDENCE_SUMMARY_MD)
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_phase6_machine_evidence_summary_markdown(report), encoding="utf-8")
    return report


def _policy_for_repo(repo: Path, repo_policies: list[Any] | None) -> Any | None:
    resolved = repo.resolve()
    for policy in repo_policies or []:
        try:
            if Path(policy.path).resolve() == resolved:
                return policy
        except OSError:
            continue
    return None


def _policy_summary(repo: Path, repo_policies: list[Any] | None) -> dict[str, Any]:
    policy = _policy_for_repo(repo, repo_policies)
    if policy is None:
        return {
            "reviewed_policy": False,
            "repo_id": repo.name,
            "repo_alias": repo.name,
            "visibility": "unknown",
            "public_facing": False,
            "exceptions_enabled": False,
            "collect_allowed": False,
            "capture_audit_allowed": False,
            "backfill_allowed": False,
            "approved_approval_id_count": 0,
            "write_protected": False,
            "write_protection_reason": "",
        }
    approved_ids = [str(item) for item in getattr(policy, "approved_approval_ids", []) or []]
    return {
        "reviewed_policy": True,
        "repo_id": str(getattr(policy, "id", repo.name)),
        "repo_alias": str(getattr(policy, "alias", getattr(policy, "id", repo.name))),
        "visibility": str(getattr(policy, "visibility", "unknown")),
        "public_facing": bool(getattr(policy, "public_facing", False)),
        "exceptions_enabled": bool(getattr(policy, "exceptions_enabled", True)),
        "collect_allowed": bool(getattr(policy, "collect_allowed", False)),
        "capture_audit_allowed": bool(getattr(policy, "capture_audit_allowed", False)),
        "backfill_allowed": bool(getattr(policy, "backfill_allowed", False)),
        "approved_approval_id_count": len(approved_ids),
        "write_protected": bool(getattr(policy, "write_protected", False)),
        "write_protection_reason": str(getattr(policy, "write_protection_reason", "")),
    }


def _repo_ref(repo: Path, hub_root: Path) -> dict[str, Any]:
    resolved = repo.resolve()
    rel = safe_relative(resolved, hub_root)
    return {
        "path_hint": rel if rel != resolved.name else resolved.name,
        "path_hash": f"sha256:{sha256_bytes(resolved.as_posix().encode('utf-8'))}",
        "absolute_path_included": False,
    }


def _load_contract_summary(repo: Path) -> dict[str, Any]:
    path = repo / ".digital-asset" / "dad-integration.json"
    summary: dict[str, Any] = {
        "exists": path.exists(),
        "schema_version": "",
        "enrollment_version": "",
        "capture_surface_version": "",
        "repo_id": "",
        "read_error": "",
    }
    if not path.exists():
        return summary
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        summary["read_error"] = f"{type(exc).__name__}:{exc}"
        return summary
    enrollment = payload.get("enrollment") if isinstance(payload.get("enrollment"), dict) else {}
    capture = payload.get("capture") if isinstance(payload.get("capture"), dict) else {}
    summary.update(
        {
            "schema_version": str(payload.get("schema_version", "")),
            "enrollment_version": str(
                payload.get("enrollment_version")
                or enrollment.get("version")
                or payload.get("version")
                or ""
            ),
            "capture_surface_version": str(
                payload.get("capture_surface_version")
                or capture.get("surface_version")
                or capture.get("version")
                or ""
            ),
            "repo_id": str(payload.get("repo_id") or payload.get("id") or ""),
        }
    )
    return summary


def _correlation_ref_hashes(payload: dict[str, Any]) -> list[str]:
    refs: set[str] = set()
    for field in (
        "context_refs",
        "evidence",
        "validation_refs",
        "asset_refs",
        "harness_refs",
        "trace_refs",
    ):
        value = payload.get(field)
        if isinstance(value, list):
            refs.update(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            refs.add(value.strip())
    hashes: set[str] = set()
    for ref in refs:
        hashes.add(f"sha256:{sha256_bytes(ref.encode('utf-8'))}")
        if ref.startswith("sha256:"):
            hashes.add(ref)
        if ref.startswith("repo-relative-sha256:"):
            digest = ref.removeprefix("repo-relative-sha256:")
            if digest:
                hashes.add(f"sha256:{digest}")
        if ref.startswith("repo-relative:"):
            bare = ref.removeprefix("repo-relative:")
            if bare:
                hashes.add(f"sha256:{sha256_bytes(bare.encode('utf-8'))}")
    return sorted(hashes)


def _jsonl_summary(path: Path, kind: str, *, repo: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": safe_relative(path, repo),
        "kind": kind,
        "exists": path.exists(),
        "content_hash": "",
        "mtime_ns": None,
        "record_count": 0,
        "valid_record_count": 0,
        "malformed_count": 0,
        "non_object_count": 0,
        "message_types": [],
        "event_types": [],
        "capture_contracts": [],
        "record_refs": [],
        "errors": [],
    }
    if not path.exists():
        return summary
    try:
        summary["content_hash"] = f"sha256:{sha256_file(path)}"
        summary["mtime_ns"] = path.stat().st_mtime_ns
    except OSError as exc:
        summary["errors"].append(f"metadata_error:{type(exc).__name__}")
    message_types: set[str] = set()
    event_types: set[str] = set()
    capture_contracts: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        summary["errors"].append(f"read_error:{type(exc).__name__}")
        return summary
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            summary["malformed_count"] += 1
            summary["errors"].append(f"malformed_jsonl:{line_number}")
            continue
        if not isinstance(payload, dict):
            summary["non_object_count"] += 1
            summary["errors"].append(f"non_object_jsonl:{line_number}")
            continue
        summary["record_count"] += 1
        is_valid_kind_row = kind != "fix_outcome" or _is_fix_outcome_row(payload)
        if is_valid_kind_row:
            summary["valid_record_count"] += 1
        if payload.get("message_type"):
            message_types.add(str(payload["message_type"]))
        if payload.get("event_type"):
            event_types.add(str(payload["event_type"]))
        if payload.get("capture_contract") and (kind != "fix_outcome" or is_valid_kind_row):
            capture_contracts.add(str(payload["capture_contract"]))
        elif kind == "fix_outcome" and is_valid_kind_row:
            capture_contracts.add("fix_outcome")
        summary["record_refs"].append(
            {
                "message_type": str(payload.get("message_type") or ""),
                "event_type": str(payload.get("event_type") or ""),
                "capture_contract": str(payload.get("capture_contract") or ""),
                "correlation_ref_hashes": _correlation_ref_hashes(payload),
            }
        )
    summary["message_types"] = sorted(message_types)
    summary["event_types"] = sorted(event_types)
    summary["capture_contracts"] = sorted(capture_contracts)
    return summary


def _is_capture_audit_excluded(path: Path, repo: Path) -> bool:
    try:
        scoped = path.resolve().relative_to(repo.resolve())
    except (ValueError, OSError):
        scoped = path
    normalized = scoped.as_posix().casefold()
    return (
        any(part.casefold() in CAPTURE_AUDIT_EXCLUDE_DIRS for part in scoped.parts)
        or any(part.casefold().startswith(".tmp") for part in scoped.parts)
        or any(part.casefold().startswith("pytest-of-") for part in scoped.parts)
        or any(term in normalized for term in BACKFILL_SENSITIVE_PATH_TERMS)
    )


def _path_ref_looks_private(value: str) -> bool:
    normalized = value.replace("\\", "/").casefold()
    return any(fragment.replace("\\", "/") in normalized for fragment in PRIVATE_PATH_FRAGMENTS)


def _report_path_ref(path: Path, root: Path) -> str:
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        return resolved.relative_to(root_resolved).as_posix()
    except (OSError, ValueError):
        return f"path-sha256:{sha256_bytes(str(path).encode('utf-8'))}"


def _path_signal_record(
    path: Path,
    repo: Path,
    term: str,
    metadata: dict[str, str],
    *,
    include_path: bool,
) -> dict[str, str]:
    rel = safe_relative(path, repo)
    include_safe_path = include_path and not _path_ref_looks_private(rel)
    record = {
        "term": term,
        "signal": metadata["signal"],
        "pattern_family": metadata["pattern_family"],
        "expected_review": metadata["expected_review"],
        "suggested_event_type": metadata["suggested_event_type"],
        "path_hash": f"sha256:{sha256_bytes(rel.encode('utf-8'))}",
        "path_redacted": str(not include_safe_path).lower(),
    }
    for optional_key in (
        "source_rule_id",
        "source_registry",
        "classification_source",
    ):
        value = str(metadata.get(optional_key, "")).strip()
        if value:
            record[optional_key] = value
    if include_path and not include_safe_path:
        record["path_redacted_reason"] = "private_path_fragment"
    if include_safe_path:
        record["path"] = rel
    return record


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _top_counter_items(values: dict[str, int], *, limit: int = 5) -> dict[str, int]:
    return dict(sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit])


def _candidate_signal_summary(
    signals: list[dict[str, Any]],
    *,
    candidate_limit: int | None = None,
    truncated_repo_count: int = 0,
) -> dict[str, Any]:
    suggested_event_types = Counter(
        str(item.get("suggested_event_type") or "<none>") for item in signals
    )
    source_rule_ids = Counter(
        str(item.get("source_rule_id") or "<builtin_path_term>") for item in signals
    )
    capture_suggest_rule_ids = Counter(
        str(rule_id)
        for item in signals
        for rule_id in (item.get("capture_suggestion") or {}).get("matched_rule_ids", [])
    )
    summary: dict[str, Any] = {
        "total": len(signals),
        "count_scope": (
            "bounded_first_n_path_matches"
            if truncated_repo_count
            else "complete_for_scanned_paths"
        ),
        "truncated_repo_count": truncated_repo_count,
        "omitted_signal_count_unknown": bool(truncated_repo_count),
        "by_pattern_family": _counter_dict(
            Counter(str(item.get("pattern_family") or "<unknown>") for item in signals)
        ),
        "by_suggested_event_type": _counter_dict(suggested_event_types),
        "by_expected_review": _counter_dict(
            Counter(str(item.get("expected_review") or "<unknown>") for item in signals)
        ),
        "by_emission_status": _counter_dict(
            Counter(str(item.get("emission_status") or "<unannotated>") for item in signals)
        ),
        "by_source_rule_id": _counter_dict(source_rule_ids),
        "by_capture_suggest_rule_id": _counter_dict(capture_suggest_rule_ids),
        "by_term": _counter_dict(Counter(str(item.get("term") or "<unknown>") for item in signals)),
        "redacted_path_count": sum(
            1 for item in signals if str(item.get("path_redacted", "")).lower() == "true"
        ),
        "unredacted_path_count": sum(
            1 for item in signals if str(item.get("path_redacted", "")).lower() == "false"
        ),
    }
    if candidate_limit is not None:
        summary["candidate_limit"] = candidate_limit
    return summary


def _normalize_candidate_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    return limit if limit > 0 else None


def _candidate_limit_label(limit: int | None) -> str:
    return "exhaustive metadata-only scan" if _normalize_candidate_limit(limit) is None else str(limit)


def _merge_candidate_signal_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "by_pattern_family",
        "by_suggested_event_type",
        "by_expected_review",
        "by_emission_status",
        "by_source_rule_id",
        "by_capture_suggest_rule_id",
        "by_term",
    ]
    counters = {key: Counter() for key in keys}
    total = 0
    redacted = 0
    unredacted = 0
    truncated_repo_count = 0
    limits: set[int] = set()
    for row in rows:
        summary = row.get("candidate_path_signal_summary", {})
        if not isinstance(summary, dict):
            continue
        total += int(summary.get("total") or 0)
        redacted += int(summary.get("redacted_path_count") or 0)
        unredacted += int(summary.get("unredacted_path_count") or 0)
        truncated_repo_count += int(summary.get("truncated_repo_count") or 0)
        if isinstance(summary.get("candidate_limit"), int):
            limits.add(int(summary["candidate_limit"]))
        for key in keys:
            values = summary.get(key, {})
            if isinstance(values, dict):
                counters[key].update({str(name): int(count) for name, count in values.items()})
    merged: dict[str, Any] = {
        "total": total,
        "count_scope": (
            "bounded_first_n_path_matches"
            if truncated_repo_count
            else "complete_for_scanned_paths"
        ),
        "truncated_repo_count": truncated_repo_count,
        "omitted_signal_count_unknown": bool(truncated_repo_count),
        "redacted_path_count": redacted,
        "unredacted_path_count": unredacted,
    }
    for key, counter in counters.items():
        merged[key] = _counter_dict(counter)
    if len(limits) == 1:
        merged["candidate_limit"] = next(iter(limits))
    elif len(limits) > 1:
        merged["candidate_limits"] = sorted(limits)
    return merged


def _candidate_signal_summary_from_rows(
    rows: list[dict[str, Any]],
    *,
    signal_key: str = "candidate_path_signals",
) -> dict[str, Any]:
    signals = [signal for row in rows for signal in row.get(signal_key, [])]
    scan_rows = [
        row.get("candidate_path_scan", {})
        for row in rows
        if isinstance(row.get("candidate_path_scan", {}), dict)
    ]
    truncated_repo_count = sum(1 for scan in scan_rows if scan.get("truncated"))
    limits = sorted(
        {
            int(scan["limit"])
            for scan in scan_rows
            if isinstance(scan.get("limit"), int)
        }
    )
    summary = _candidate_signal_summary(
        signals,
        candidate_limit=limits[0] if len(limits) == 1 else None,
        truncated_repo_count=truncated_repo_count,
    )
    if len(limits) > 1:
        summary["candidate_limits"] = limits
    return summary


def _signal_correlation_ref_hashes(signal: dict[str, str]) -> set[str]:
    refs: set[str] = set()
    path = str(signal.get("path") or "").strip()
    if path:
        refs.update(
            {
                path,
                f"repo-relative:{path}",
                f"path:{path}",
                f"evidence:{path}",
            }
        )
    path_hash = str(signal.get("path_hash") or "").strip()
    normalized_hashes: set[str] = set()
    if path_hash:
        normalized_hashes.add(path_hash)
        if path_hash.startswith("sha256:"):
            normalized_hashes.add(
                f"repo-relative-sha256:{path_hash.removeprefix('sha256:')}"
            )
    hashed_refs = {f"sha256:{sha256_bytes(ref.encode('utf-8'))}" for ref in refs}
    hashed_refs.update(normalized_hashes)
    return hashed_refs


def _candidate_capture_path_scan(
    repo: Path,
    *,
    limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
    include_paths: bool = False,
    path_terms: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    normalized_limit = _normalize_candidate_limit(limit)
    normalized_max_scanned = (
        max_scanned_files if max_scanned_files is not None and max_scanned_files > 0 else None
    )
    if not repo.exists() or not repo.is_dir():
        return {
            "signals": [],
            "truncated": False,
            "scanned_file_count": 0,
            "limit": normalized_limit,
            "limit_mode": "exhaustive" if normalized_limit is None else "bounded",
            "max_scanned_files": normalized_max_scanned,
            "stopped_reason": "repo_missing",
        }
    findings: list[dict[str, str]] = []
    terms = path_terms or CAPTURE_AUDIT_PATH_TERMS
    scanned_file_count = 0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(repo):
        dir_path = Path(dirpath)
        dirnames[:] = [
            name
            for name in sorted(dirnames)
            if not _is_capture_audit_excluded(dir_path / name, repo)
        ]
        for filename in sorted(filenames):
            path = dir_path / filename
            if _is_capture_audit_excluded(path, repo):
                continue
            if normalized_max_scanned is not None and scanned_file_count >= normalized_max_scanned:
                truncated = True
                return {
                    "signals": findings,
                    "truncated": truncated,
                    "scanned_file_count": scanned_file_count,
                    "limit": normalized_limit,
                    "limit_mode": "exhaustive" if normalized_limit is None else "bounded",
                    "max_scanned_files": normalized_max_scanned,
                    "stopped_reason": "max_scanned_files_reached",
                }
            scanned_file_count += 1
            rel_path = safe_relative(path, repo)
            for term, metadata in sorted(
                terms.items(),
                key=lambda item: len(item[0]),
                reverse=True,
            ):
                if not path_term_matches(rel_path, term):
                    continue
                findings.append(_path_signal_record(path, repo, term, metadata, include_path=include_paths))
                break
            if normalized_limit is not None and len(findings) >= normalized_limit:
                truncated = True
                return {
                    "signals": findings,
                    "truncated": truncated,
                    "scanned_file_count": scanned_file_count,
                    "limit": normalized_limit,
                    "limit_mode": "bounded",
                    "max_scanned_files": normalized_max_scanned,
                    "stopped_reason": "candidate_limit_reached",
                }
    return {
        "signals": findings,
        "truncated": truncated,
        "scanned_file_count": scanned_file_count,
        "limit": normalized_limit,
        "limit_mode": "exhaustive" if normalized_limit is None else "bounded",
        "max_scanned_files": normalized_max_scanned,
        "stopped_reason": "exhausted_walk",
    }


def _packet_classes_from_outboxes(outboxes: dict[str, dict[str, Any]]) -> list[str]:
    packet_classes: set[str] = set()
    if outboxes["mail_outbox"]["record_count"]:
        packet_classes.add("ordinary_mail")
    if outboxes["exception_outbox"]["record_count"]:
        packet_classes.add("exception_event")
    if outboxes["fix_outcomes"].get("valid_record_count"):
        packet_classes.add("fix_outcome")
    if not packet_classes:
        packet_classes.add("no_packet")
    return sorted(packet_classes)


def _expected_outputs_by_family(registry: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    outputs: dict[str, dict[str, set[str]]] = {}
    for rule in registry.get("rules", []):
        family = str(rule.get("pattern_family", ""))
        if not family:
            continue
        family_outputs = outputs.setdefault(
            family,
            {
                "packet_classes": set(),
                "mail_message_types": set(),
                "event_types": set(),
                "capture_contracts": set(),
            },
        )
        emit = rule.get("emit", {})
        family_outputs["packet_classes"].update(str(item) for item in emit.get("packet_classes", []))
        if emit.get("mail_message_type"):
            family_outputs["mail_message_types"].add(str(emit["mail_message_type"]))
        if emit.get("exception_event_type"):
            family_outputs["event_types"].add(str(emit["exception_event_type"]))
        if emit.get("capture_contract"):
            family_outputs["capture_contracts"].add(str(emit["capture_contract"]))
    return {
        family: {key: sorted(values) for key, values in family_outputs.items()}
        for family, family_outputs in outputs.items()
    }


def _reviewed_capture_rules_for_signal(
    signal: dict[str, str],
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    pattern_family = str(signal.get("pattern_family") or "")
    event_type = str(signal.get("suggested_event_type") or "")
    reviewed_rules = [
        rule
        for rule in registry.get("rules", [])
        if isinstance(rule, dict) and rule.get("review_status") == "reviewed"
    ]
    family_rules = [
        rule for rule in reviewed_rules if str(rule.get("pattern_family") or "") == pattern_family
    ]
    if pattern_family == "exception_pattern":
        event_rules = [
            rule
            for rule in reviewed_rules
            if str((rule.get("emit") or {}).get("exception_event_type") or "") == event_type
        ]
        if len(event_rules) <= 1:
            return sorted(event_rules, key=lambda item: str(item.get("rule_id") or ""))
        preferred_rules = [
            rule for rule in event_rules if str(rule.get("pattern_family") or "") == event_type
        ]
        if len(preferred_rules) == 1:
            return preferred_rules
        return []
    scoped_rules = family_rules or reviewed_rules
    event_rules = [
        rule
        for rule in scoped_rules
        if str((rule.get("emit") or {}).get("exception_event_type") or "") == event_type
    ]
    if event_rules:
        return sorted(event_rules, key=lambda item: str(item.get("rule_id") or ""))
    if len(family_rules) == 1:
        return sorted(family_rules, key=lambda item: str(item.get("rule_id") or ""))
    return []


def _capture_suggest_signals_for_path_signal(
    signal: dict[str, str],
    registry: dict[str, Any],
) -> list[str]:
    selected_signals: list[str] = []
    selected_set: set[str] = set()
    signal_text = json.dumps(signal, sort_keys=True).replace("-", "_").casefold()
    for rule in _reviewed_capture_rules_for_signal(signal, registry):
        for item in rule.get("match_signals", []) or []:
            text = str(item).strip()
            if text and text not in selected_set:
                selected_set.add(text)
                selected_signals.append(text)
        any_signals = [str(item).strip() for item in rule.get("any_signals", []) or [] if str(item).strip()]
        preferred = ""
        for item in any_signals:
            if item.replace("-", "_").casefold() in signal_text:
                preferred = item
                break
        if not preferred and any_signals:
            preferred = any_signals[0]
        if preferred and preferred not in selected_set:
            selected_set.add(preferred)
            selected_signals.append(preferred)
    if selected_signals:
        return selected_signals
    fallback = str(signal.get("signal") or "").strip()
    return [fallback] if fallback else []


def _candidate_signal_capture_suggestion(
    hub_root: Path,
    signal: dict[str, str],
    registry: dict[str, Any],
    *,
    repo_capture_surface_version: str,
) -> dict[str, Any]:
    suggestion = suggest_exception_capture(
        hub_root,
        signals=_capture_suggest_signals_for_path_signal(signal, registry),
        repo_capture_surface_version=repo_capture_surface_version,
    )
    suggested_event_type = str(signal.get("suggested_event_type") or "")
    actual_event_types = set(suggestion["actual"]["event_types"])
    ambiguous_exception_signal = (
        signal.get("pattern_family") == "exception_pattern"
        and suggested_event_type not in actual_event_types
        and not suggestion["matched_rule_ids"]
    )
    next_actions = list(suggestion["next_actions"])
    if ambiguous_exception_signal:
        next_actions.insert(
            0,
            "Treat this as a broad exception path signal only. Add event-specific "
            "safe metadata before choosing a concrete capture rule.",
        )
    return {
        "suggestion_id": suggestion["suggestion_id"],
        "methodology_hash": suggestion["methodology_hash"],
        "repo_capture_surface_version": suggestion["repo_capture_surface_version"],
        "capture_surface_version_unknown": suggestion["capture_surface_version_unknown"],
        "registry_capture_surface_version": suggestion["registry_capture_surface_version"],
        "update_required": suggestion["update_required"],
        "signals": suggestion["signals"],
        "signal_screen_issues": suggestion["signal_screen_issues"],
        "matched_rule_ids": suggestion["matched_rule_ids"],
        "ambiguous_exception_signal": ambiguous_exception_signal,
        "actual": suggestion["actual"],
        "recommended_packets": suggestion["recommended_packets"],
        "next_actions": next_actions,
        "authority_boundary": (
            "Nested capture suggestions are candidate packet plans for the path "
            "signal only. They do not prove the file contains an exception and do "
            "not authorize source mutation, delivery, or promotion."
        ),
    }


def _outbox_actual_outputs(outboxes: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    contracts = set(outboxes["exception_outbox"].get("capture_contracts", []))
    contracts.update(str(item) for item in outboxes["fix_outcomes"].get("capture_contracts", []))
    return {
        "mail_message_types": set(outboxes["mail_outbox"].get("message_types", [])),
        "event_types": set(outboxes["exception_outbox"].get("event_types", [])),
        "capture_contracts": contracts,
    }


def _record_matches_signal(record: dict[str, Any], signal: dict[str, str]) -> bool:
    signal_hashes = _signal_correlation_ref_hashes(signal)
    if not signal_hashes:
        return False
    record_hashes = {
        str(item) for item in record.get("correlation_ref_hashes", []) if str(item).strip()
    }
    return bool(signal_hashes.intersection(record_hashes))


def _has_correlated_record(
    records: list[dict[str, Any]],
    field: str,
    expected_values: list[str],
    signal: dict[str, str],
) -> bool:
    expected = set(expected_values)
    return any(
        str(record.get(field) or "") in expected and _record_matches_signal(record, signal)
        for record in records
    )


def _annotate_candidate_signals(
    hub_root: Path,
    signals: list[dict[str, str]],
    registry: dict[str, Any],
    outboxes: dict[str, dict[str, Any]],
    *,
    repo_capture_surface_version: str,
) -> list[dict[str, Any]]:
    expected_by_family = _expected_outputs_by_family(registry)
    actual = _outbox_actual_outputs(outboxes)
    annotated: list[dict[str, Any]] = []
    for signal in signals:
        expected = expected_by_family.get(
            signal["pattern_family"],
            {
                "packet_classes": [],
                "mail_message_types": [],
                "event_types": [],
                "capture_contracts": [],
            },
        )
        strict = signal["expected_review"] in {
            "ordinary_mail_exception_or_no_packet",
            "exception_event_or_no_packet",
        }
        missing_outputs: list[str] = []
        matching_outputs: list[str] = []
        uncorrelated_outputs: list[str] = []
        if expected["mail_message_types"]:
            if _has_correlated_record(
                outboxes["mail_outbox"].get("record_refs", []),
                "message_type",
                expected["mail_message_types"],
                signal,
            ):
                matching_outputs.append("mail_message_type")
            elif actual["mail_message_types"].intersection(expected["mail_message_types"]):
                uncorrelated_outputs.append("mail_message_type")
                if strict:
                    missing_outputs.append("mail_message_type")
            elif strict:
                missing_outputs.append("mail_message_type")
        if expected["event_types"]:
            if _has_correlated_record(
                outboxes["exception_outbox"].get("record_refs", []),
                "event_type",
                expected["event_types"],
                signal,
            ):
                matching_outputs.append("event_type")
            elif actual["event_types"].intersection(expected["event_types"]):
                uncorrelated_outputs.append("event_type")
                if strict:
                    missing_outputs.append("event_type")
            elif strict:
                missing_outputs.append("event_type")
        if expected["capture_contracts"]:
            exception_records = outboxes["exception_outbox"].get("record_refs", [])
            fix_records = outboxes["fix_outcomes"].get("record_refs", [])
            if _has_correlated_record(
                [*exception_records, *fix_records],
                "capture_contract",
                expected["capture_contracts"],
                signal,
            ):
                matching_outputs.append("capture_contract")
            elif actual["capture_contracts"].intersection(expected["capture_contracts"]):
                uncorrelated_outputs.append("capture_contract")
                if strict:
                    missing_outputs.append("capture_contract")
            elif strict:
                missing_outputs.append("capture_contract")
        emission_status = "matched" if matching_outputs and not missing_outputs else "unverified"
        if missing_outputs:
            emission_status = "gap_candidate"
        elif uncorrelated_outputs:
            emission_status = "type_present_uncorrelated"
        annotated.append(
            {
                **signal,
                "expected_outputs": expected,
                "capture_suggestion": _candidate_signal_capture_suggestion(
                    hub_root,
                    signal,
                    registry,
                    repo_capture_surface_version=repo_capture_surface_version,
                ),
                "matching_outputs": matching_outputs,
                "missing_outputs": missing_outputs,
                "uncorrelated_outputs": uncorrelated_outputs,
                "emission_status": emission_status,
            }
        )
    return annotated


def audit_observed_capture_repo(
    hub_root: Path,
    repo: Path,
    registry: dict[str, Any],
    *,
    repo_policies: list[Any] | None = None,
    candidate_limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
) -> dict[str, Any]:
    resolved = repo.resolve()
    policy = _policy_summary(resolved, repo_policies)
    contract = _load_contract_summary(resolved)
    outboxes = {
        "mail_outbox": _jsonl_summary(
            resolved / MAIL_MIRROR_DIR / "outbox.jsonl",
            "mail",
            repo=resolved,
        ),
        "exception_outbox": _jsonl_summary(
            resolved / EXCEPTION_OUTBOX,
            "exception",
            repo=resolved,
        ),
        "fix_outcomes": _jsonl_summary(
            resolved / "processed" / "exceptions" / "fix-outcomes" / "outcomes.jsonl",
            "fix_outcome",
            repo=resolved,
        ),
    }
    include_candidate_paths = policy["reviewed_policy"] and policy["visibility"] in {
        "public",
        "internal",
    }
    path_terms = {
        **CAPTURE_AUDIT_PATH_TERMS,
        **backfill_path_signal_terms(hub_root),
    }
    candidate_scan = _candidate_capture_path_scan(
        resolved,
        limit=candidate_limit,
        max_scanned_files=max_scanned_files,
        include_paths=include_candidate_paths,
        path_terms=path_terms,
    )
    candidate_paths = _annotate_candidate_signals(
        hub_root,
        candidate_scan["signals"],
        registry,
        outboxes,
        repo_capture_surface_version=contract.get("capture_surface_version", ""),
    )
    packet_classes = _packet_classes_from_outboxes(outboxes)
    capture_surface_version = contract.get("capture_surface_version", "")
    registry_version = str(registry.get("capture_surface_version", ""))
    malformed_count = sum(int(item["malformed_count"]) for item in outboxes.values())
    status_flags: list[str] = []
    if not contract["exists"] and all(not item["exists"] for item in outboxes.values()):
        status_flags.append("legacy_or_not_enrolled")
    if contract.get("read_error"):
        status_flags.append("contract_read_error")
    if not capture_surface_version:
        status_flags.append("capture_surface_version_unknown")
    elif _version_tuple(capture_surface_version) < _version_tuple(registry_version):
        status_flags.append("stale_capture_surface")
    if "exception_event" in packet_classes or "ordinary_mail" in packet_classes:
        status_flags.append("outbox_emission_present")
    if any(item["emission_status"] == "gap_candidate" for item in candidate_paths):
        status_flags.append("pattern_gap_candidate")
    if any(item["emission_status"] == "type_present_uncorrelated" for item in candidate_paths):
        status_flags.append("type_present_uncorrelated")
    if any(item["emission_status"] == "unverified" for item in candidate_paths):
        status_flags.append("emission_unverified")
    if candidate_scan["truncated"]:
        status_flags.append("candidate_path_scan_truncated")
    if (
        outboxes["mail_outbox"]["record_count"]
        and not outboxes["exception_outbox"]["record_count"]
        and any(
            item["expected_review"] == "ordinary_mail_exception_or_no_packet"
            for item in candidate_paths
        )
    ):
        status_flags.append("mail_present_exception_gap_candidate")
    if candidate_paths and packet_classes == ["no_packet"]:
        status_flags.append("missed_capture_candidate")
    if malformed_count:
        status_flags.append("malformed_jsonl")
    if policy["write_protected"]:
        status_flags.append("protected_repo_central_only")
    if not status_flags:
        status_flags.append("no_capture_concern_detected")
    return {
        "repo": {
            **_repo_ref(resolved, hub_root),
            **policy,
            "contract_repo_id": contract.get("repo_id", ""),
        },
        "contract": contract,
        "registry_capture_surface_version": registry_version,
        "packet_classes": packet_classes,
        "outboxes": outboxes,
        "candidate_path_signal_count": len(candidate_paths),
        "candidate_path_scan": {
            "truncated": candidate_scan["truncated"],
            "scanned_file_count": candidate_scan["scanned_file_count"],
            "limit": candidate_scan["limit"],
            "limit_mode": candidate_scan["limit_mode"],
            "max_scanned_files": candidate_scan["max_scanned_files"],
            "stopped_reason": candidate_scan["stopped_reason"],
            "path_hash_only": not include_candidate_paths,
            "scan_hash": f"sha256:{sha256_bytes(json.dumps(candidate_paths, sort_keys=True).encode('utf-8'))}",
        },
        "candidate_path_signal_summary": _candidate_signal_summary(
            candidate_paths,
            candidate_limit=candidate_scan["limit"],
            truncated_repo_count=1 if candidate_scan["truncated"] else 0,
        ),
        "candidate_path_signals": candidate_paths,
        "status_flags": status_flags,
        "authority_boundary": (
            "Observed capture audit is read-only candidate evidence. Path signals do "
            "not prove a DAD packet should be sent; they identify repos and patterns "
            "that need deterministic repo-side capture review."
        ),
    }


def discover_capture_audit_repos(
    roots: list[Path],
    *,
    limit: int = 200,
) -> list[Path]:
    repos: dict[str, Path] = {}
    for root in roots:
        resolved_root = root.resolve()
        if not resolved_root.exists():
            continue
        if (resolved_root / ".git").exists() or (resolved_root / ".digital-asset").exists():
            repos[str(resolved_root)] = resolved_root
        for dirpath, dirnames, _ in os.walk(resolved_root):
            dir_path = Path(dirpath)
            dirnames[:] = [
                name
                for name in sorted(dirnames)
                if name.casefold() not in CAPTURE_AUDIT_EXCLUDE_DIRS
                and not name.casefold().startswith("pytest-of-")
            ]
            if (dir_path / ".git").exists() or (dir_path / ".digital-asset").exists():
                repos[str(dir_path.resolve())] = dir_path.resolve()
                dirnames[:] = []
                if len(repos) >= limit:
                    return list(repos.values())
    return list(repos.values())[:limit]


def _observed_audit_input_hashes(hub_root: Path) -> dict[str, str]:
    refs = [
        CAPTURE_PATTERN_REGISTRY,
        Path("registry") / "exception-event-type-registry.json",
        Path("src") / "digital_asset_directory" / "exception_capture.py",
    ]
    hashes: dict[str, str] = {}
    for ref in refs:
        path = hub_root / ref
        if path.exists() and path.is_file():
            hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}"
    return hashes


def _observed_audit_status_flags(row: dict[str, Any]) -> set[str]:
    flags = row.get("status_flags", [])
    if not isinstance(flags, list):
        return set()
    return {str(flag) for flag in flags}


def observed_capture_audit_gap_count(report: dict[str, Any], *, strict: bool = False) -> int:
    rows = report.get("repos", [])
    if isinstance(rows, list) and rows:
        status_counts = Counter(
            str(flag)
            for row in rows
            if isinstance(row, dict)
            for flag in _observed_audit_status_flags(row)
        )
    else:
        raw_status_counts = report.get("status_counts", {})
        status_counts = raw_status_counts if isinstance(raw_status_counts, dict) else {}
    flags = set(OBSERVED_CAPTURE_AUDIT_GAP_FLAGS)
    if strict:
        flags.update(OBSERVED_CAPTURE_AUDIT_STRICT_EXTRA_FLAGS)
    status_gap_count = sum(int(status_counts.get(flag, 0) or 0) for flag in flags)
    repos = report.get("repos", [])
    truncated_scan_count = 0
    if isinstance(repos, list):
        for row in repos:
            if not isinstance(row, dict):
                continue
            scan = row.get("candidate_path_scan") or row.get("candidate_scan")
            if isinstance(scan, dict) and scan.get("truncated") is True:
                truncated_scan_count += 1
    recorded_truncation_count = int(
        status_counts.get("candidate_path_scan_truncated", 0) or 0
    )
    return status_gap_count + max(0, truncated_scan_count - recorded_truncation_count)


def _normalized_observed_audit_scope(
    scope: dict[str, Any] | None,
    *,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reviewed_repo_count = sum(
        1 for row in rows if (row.get("repo") or {}).get("reviewed_policy")
    )
    normalized = {
        "scope_id": "ad_hoc",
        "scope_kind": "ad_hoc",
        "reviewed_policy_scope": False,
        "expected_repo_count": len(rows),
        "audited_repo_count": len(rows),
        "reviewed_policy_repo_count": reviewed_repo_count,
    }
    if isinstance(scope, dict):
        normalized.update(
            {
                key: value
                for key, value in scope.items()
                if key
                in {
                    "scope_id",
                    "scope_kind",
                    "reviewed_policy_scope",
                    "expected_repo_count",
                }
            }
        )
    try:
        expected_repo_count = int(normalized.get("expected_repo_count") or 0)
    except (TypeError, ValueError):
        expected_repo_count = 0
    audited_repo_count = len(rows)
    reviewed_scope = bool(normalized.get("reviewed_policy_scope"))
    scope_satisfied = (
        reviewed_scope
        and expected_repo_count > 0
        and audited_repo_count == expected_repo_count
        and reviewed_repo_count == expected_repo_count
    )
    normalized.update(
        {
            "expected_repo_count": expected_repo_count,
            "audited_repo_count": audited_repo_count,
            "reviewed_policy_repo_count": reviewed_repo_count,
            "scope_satisfied": scope_satisfied,
        }
    )
    return normalized


def _observed_audit_phase6_machine_gate_evidence(
    *,
    rows: list[dict[str, Any]],
    status_counts: Counter[str],
    signal_summary: dict[str, Any],
    gap_flag_count: int,
    strict_gap_flag_count: int,
    gap_repo_count: int,
    strict_gap_repo_count: int,
    gap_signal_count: int,
    scope: dict[str, Any],
) -> dict[str, Any]:
    reviewed_policy_count = sum(
        1 for row in rows if (row.get("repo") or {}).get("reviewed_policy")
    )
    write_protected_count = sum(
        1 for row in rows if (row.get("repo") or {}).get("write_protected")
    )
    gap_flags = sorted(
        flag
        for flag in OBSERVED_CAPTURE_AUDIT_GAP_FLAGS
        if int(status_counts.get(flag, 0) or 0)
    )
    strict_extra_flags = sorted(
        flag
        for flag in OBSERVED_CAPTURE_AUDIT_STRICT_EXTRA_FLAGS
        if int(status_counts.get(flag, 0) or 0)
    )
    passed = bool(rows) and scope["scope_satisfied"] and strict_gap_flag_count == 0
    return {
        "authority_boundary": PHASE6_GATE_BOUNDARY,
        "gates": {
            _phase6_machine_evidence_key(
                "phase-6-observed-repo-capture-audit-reviewed"
            ): _phase6_gate_row(
                "phase-6-observed-repo-capture-audit-reviewed",
                passed=passed,
                evidence={
                    "repo_count": len(rows),
                    "reviewed_policy_repo_count": reviewed_policy_count,
                    "write_protected_repo_count": write_protected_count,
                    "scope": scope,
                    "gap_flag_count": gap_flag_count,
                    "strict_gap_flag_count": strict_gap_flag_count,
                    "gap_repo_count": gap_repo_count,
                    "strict_gap_repo_count": strict_gap_repo_count,
                    "gap_signal_count": gap_signal_count,
                    "gap_flags_present": gap_flags,
                    "strict_extra_flags_present": strict_extra_flags,
                    "status_counts": dict(sorted(status_counts.items())),
                    "candidate_path_signal_total": signal_summary.get("total", 0),
                    "candidate_path_count_scope": signal_summary.get("count_scope", ""),
                    "truncated_repo_count": signal_summary.get("truncated_repo_count", 0),
                    "omitted_signal_count_unknown": bool(
                        signal_summary.get("omitted_signal_count_unknown")
                    ),
                    "outbox_surfaces_checked": [
                        "mail_outbox",
                        "exception_outbox",
                        "fix_outcomes",
                    ],
                    "non_mutating_audit": True,
                    "pass_condition": (
                        "repo_count > 0, reviewed policy scope satisfied, "
                        "and strict_gap_flag_count == 0"
                    ),
                },
            )
        },
    }


def write_observed_capture_audit(
    hub_root: Path,
    repos: list[Path],
    *,
    repo_policies: list[Any] | None = None,
    output: Path | None = None,
    candidate_limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = load_capture_pattern_registry(hub_root)
    rows = [
        audit_observed_capture_repo(
            hub_root,
            repo,
            registry,
            repo_policies=repo_policies,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
        )
        for repo in repos
    ]
    status_counts = Counter(flag for row in rows for flag in row["status_flags"])
    family_counts = Counter(
        item["pattern_family"] for row in rows for item in row["candidate_path_signals"]
    )
    signal_summary = _candidate_signal_summary_from_rows(rows)
    partial_report = {
        "status_counts": dict(sorted(status_counts.items())),
        "repos": rows,
    }
    gap_flag_count = observed_capture_audit_gap_count(partial_report, strict=False)
    strict_gap_flag_count = observed_capture_audit_gap_count(partial_report, strict=True)
    gap_flags = OBSERVED_CAPTURE_AUDIT_GAP_FLAGS
    strict_flags = gap_flags | OBSERVED_CAPTURE_AUDIT_STRICT_EXTRA_FLAGS
    gap_repo_count = sum(1 for row in rows if bool(_observed_audit_status_flags(row) & gap_flags))
    strict_gap_repo_count = sum(
        1 for row in rows if bool(_observed_audit_status_flags(row) & strict_flags)
    )
    gap_signal_count = sum(
        1
        for row in rows
        for signal in row.get("candidate_path_signals", [])
        if signal.get("emission_status") in {"gap_candidate", "type_present_uncorrelated"}
    )
    normalized_scope = _normalized_observed_audit_scope(scope, rows=rows)
    phase6_machine_gate_evidence = _observed_audit_phase6_machine_gate_evidence(
        rows=rows,
        status_counts=status_counts,
        signal_summary=signal_summary,
        gap_flag_count=gap_flag_count,
        strict_gap_flag_count=strict_gap_flag_count,
        gap_repo_count=gap_repo_count,
        strict_gap_repo_count=strict_gap_repo_count,
        gap_signal_count=gap_signal_count,
        scope=normalized_scope,
    )
    report = {
        "generated_at": utc_now(),
        "audit_id": "dad:exception-capture-observed-audit",
        "repo_count": len(rows),
        "registry_ref": CAPTURE_PATTERN_REGISTRY.as_posix(),
        "methodology_ref": CAPTURE_ROUTE_METHODOLOGY_REF,
        "methodology_hash": capture_route_methodology_hash(hub_root),
        "input_hashes": _observed_audit_input_hashes(hub_root),
        "capture_surface_version": registry.get("capture_surface_version"),
        "status_counts": dict(sorted(status_counts.items())),
        "gap_count": gap_flag_count,
        "strict_gap_count": strict_gap_flag_count,
        "gap_count_semantics": "status_flag_count",
        "gap_flag_count": gap_flag_count,
        "strict_gap_flag_count": strict_gap_flag_count,
        "gap_repo_count": gap_repo_count,
        "strict_gap_repo_count": strict_gap_repo_count,
        "gap_signal_count": gap_signal_count,
        "audit_scope": normalized_scope,
        "candidate_path_family_counts": dict(sorted(family_counts.items())),
        "candidate_path_signal_summary": signal_summary,
        "phase6_machine_gate_evidence": phase6_machine_gate_evidence,
        "repos": rows,
        "authority_boundary": (
            "This report reads repo-local mailbox, exception, and fix-outcome JSONL "
            "metadata plus path names only. It is not source truth, does not copy raw "
            "private content, and does not mutate target repos."
        ),
        "testing_purpose": (
            "Catch cases where a repo had DAD-worthy patterns but no ordinary mail, "
            "exception event, or fix-outcome packet was emitted, including after DAD "
            "capture-pattern updates."
        ),
    }
    output_path = _capture_output_path(hub_root, output, OBSERVED_AUDIT_JSON)
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, OBSERVED_AUDIT_MD)
    )
    lines = [
        "# Exception Capture Observed Audit",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Repos audited: {report['repo_count']}",
        f"- Capture surface version: `{report['capture_surface_version']}`",
        f"- Methodology hash: `{report['methodology_hash']}`",
        f"- Gap flag count: {report['gap_flag_count']}",
        f"- Strict gap flag count: {report['strict_gap_flag_count']}",
        f"- Gap repo count: {report['gap_repo_count']}",
        f"- Gap signal count: {report['gap_signal_count']}",
        f"- Scope: `{report['audit_scope']['scope_id']}` "
        f"({report['audit_scope']['scope_kind']}, "
        f"satisfied={report['audit_scope']['scope_satisfied']})",
        "",
        "Boundary: read-only candidate evidence. Path signals are prompts for review, "
        "not proof that a packet should have been sent.",
        "",
        "## Phase 6 Machine Gate Evidence",
        "",
    ]
    for gate in report["phase6_machine_gate_evidence"]["gates"].values():
        lines.append(
            f"- `{gate['supports_human_gate_id']}`: `{gate['machine_status']}` "
            "(human review still required)"
        )
    lines.extend(
        [
            "",
            "## Status Counts",
            "",
        ]
    )
    if status_counts:
        lines.extend(f"- `{flag}`: {count}" for flag, count in sorted(status_counts.items()))
    else:
        lines.append("- No repos audited.")
    if family_counts:
        lines.extend(["", "## Candidate Path Families", ""])
        lines.extend(f"- `{family}`: {count}" for family, count in sorted(family_counts.items()))
    if signal_summary.get("omitted_signal_count_unknown"):
        lines.extend(
            [
                "",
                "Warning: candidate path counts are bounded first-N samples because "
                f"{signal_summary['truncated_repo_count']} repo scan(s) hit the "
                "candidate limit. Treat these counts as review-routing hints, not "
                "complete distributions.",
            ]
        )
    event_type_counts = signal_summary.get("by_suggested_event_type", {})
    if event_type_counts:
        heading = (
            "## Candidate Suggested Event Types (Bounded Sample)"
            if signal_summary.get("omitted_signal_count_unknown")
            else "## Candidate Suggested Event Types"
        )
        lines.extend(["", heading, ""])
        lines.extend(
            f"- `{event_type}`: {count}"
            for event_type, count in sorted(event_type_counts.items())
        )
    source_rule_counts = signal_summary.get("by_source_rule_id", {})
    if source_rule_counts:
        heading = (
            "## Candidate Source Rules (Bounded Sample)"
            if signal_summary.get("omitted_signal_count_unknown")
            else "## Candidate Source Rules"
        )
        lines.extend(["", heading, ""])
        lines.extend(
            f"- `{rule_id}`: {count}" for rule_id, count in sorted(source_rule_counts.items())
        )
    capture_suggest_rule_counts = signal_summary.get("by_capture_suggest_rule_id", {})
    if capture_suggest_rule_counts:
        heading = (
            "## Candidate Capture-Suggest Rules (Bounded Sample)"
            if signal_summary.get("omitted_signal_count_unknown")
            else "## Candidate Capture-Suggest Rules"
        )
        lines.extend(["", heading, ""])
        lines.extend(
            f"- `{rule_id}`: {count}"
            for rule_id, count in sorted(capture_suggest_rule_counts.items())
        )
    flagged = [
        row
        for row in rows
        if any(
            flag
            in {
                "missed_capture_candidate",
                "mail_present_exception_gap_candidate",
                "pattern_gap_candidate",
                "type_present_uncorrelated",
                "emission_unverified",
                "candidate_path_scan_truncated",
                "stale_capture_surface",
                "capture_surface_version_unknown",
                "malformed_jsonl",
            }
            for flag in row["status_flags"]
        )
    ]
    if flagged:
        lines.extend(["", "## Repos Needing Review", ""])
        for row in flagged:
            repo = row["repo"]
            lines.append(
                "- `"
                + str(repo["repo_id"])
                + "` "
                + f"({repo['path_hint']}): "
                + ", ".join(f"`{flag}`" for flag in row["status_flags"])
            )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _backfill_readiness_action(row: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    repo = row["repo"]
    status_flags = set(row.get("status_flags", []))
    reasons: list[str] = []
    evidence_blockers: list[str] = []
    next_actions: list[str] = []
    if not repo.get("reviewed_policy"):
        reasons.append("repo lacks reviewed exceptions.repos policy")
    if not repo.get("exceptions_enabled"):
        reasons.append("exceptions_enabled=false")
    if repo.get("write_protected"):
        reasons.append("write_protected repo; keep central-only unless explicitly approved")
    if not repo.get("backfill_allowed"):
        reasons.append("backfill_allowed=false")
    if not row.get("candidate_path_signal_count"):
        reasons.append("no candidate path signals in observed audit")
    if "candidate_path_scan_truncated" in status_flags:
        evidence_blockers.append("candidate path scan truncated")
        next_actions.append(
            "rerun observed audit with --candidate-limit 0 or a higher limit before review"
        )
    if row.get("contract", {}).get("capture_surface_version") != row.get(
        "registry_capture_surface_version"
    ):
        evidence_blockers.append("capture surface is stale or unknown")
        next_actions.append("refresh repo capture surface before treating no-packet results as current")
    gap_flags = {
        "missed_capture_candidate",
        "pattern_gap_candidate",
        "mail_present_exception_gap_candidate",
        "emission_unverified",
        "type_present_uncorrelated",
    }
    if any(flag in status_flags for flag in gap_flags):
        evidence_blockers.append("candidate emissions are missing, unverified, or uncorrelated")
        next_actions.append("review observed capture gaps and decide whether repo should emit mail or exception packets")
    if reasons:
        if repo.get("write_protected"):
            return "central_only_or_blocked", reasons, next_actions
        return "blocked_by_policy_or_no_signals", reasons, next_actions
    if evidence_blockers:
        return "needs_full_scan_review", evidence_blockers, sorted(set(next_actions))
    if str(repo.get("repo_id")) == "dad" and str(repo.get("path_hint")) == ".":
        next_actions.append("metadata-only backfill may run without non-DAD approval")
        return "ready_now", reasons, next_actions
    if int(repo.get("approved_approval_id_count", 0) or 0) > 0:
        next_actions.append("run metadata-only backfill only with a reviewed approval id from policy")
        return "ready_with_reviewed_approval", reasons, next_actions
    next_actions.append("add a reviewed exception backfill approval id before running backfill")
    return "approval_needed", reasons, next_actions


def _capture_surface_action(row: dict[str, Any]) -> str:
    contract_version = str(row.get("contract", {}).get("capture_surface_version") or "")
    registry_version = str(row.get("registry_capture_surface_version") or "")
    if not contract_version:
        return "install_or_refresh_capture_surface"
    if _version_tuple(contract_version) < _version_tuple(registry_version):
        return "refresh_capture_surface"
    return "current"


BACKFILL_WAVE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "wave_id": "bounded_sample_rescan_wave",
        "label": "Rerun bounded historical scans",
        "human_gate": "No source write approval needed; this is central read-only evidence refresh.",
        "generated_next_step": (
            "Run backfill-readiness or capture-audit with --candidate-limit 0, or "
            "with a higher reviewed limit, before treating event/source-rule counts "
            "as representative."
        ),
        "danger_if_misapplied": (
            "A first-N sample can hide dominant exception families and make a broad "
            "backfill wave look safer or more complete than it is."
        ),
        "proof_to_advance": [
            "candidate_path_signal_summary.omitted_signal_count_unknown is false",
            "candidate_path_scan.truncated is false for repos advancing to backfill",
        ],
    },
    {
        "wave_id": "capture_surface_refresh_wave",
        "label": "Refresh repo exception capture surfaces",
        "human_gate": "Requires reviewed enrollment/update approval before writing any target repo.",
        "generated_next_step": (
            "Refresh DAD exception/mail capture guidance before using no-packet "
            "results as evidence that repo-side capture is current."
        ),
        "danger_if_misapplied": (
            "Old or missing capture surfaces can make repos appear noncompliant "
            "when they never received the current deterministic emit rules."
        ),
        "proof_to_advance": [
            "repo contract capture_surface_version matches registry capture_surface_version",
            "repo-local capture surface was updated through an approved enrollment/update path",
        ],
    },
    {
        "wave_id": "capture_gap_review_wave",
        "label": "Review missing or unverified emissions",
        "human_gate": "No backfill execution until source repo capture behavior is reviewed.",
        "generated_next_step": (
            "Inspect why candidate path signals did not correlate to exception, "
            "fix-outcome, or mail packets; update repo capture rules if needed."
        ),
        "danger_if_misapplied": (
            "DAD could backfill historical candidates when the current repo-side "
            "automatic capture loop is still failing."
        ),
        "proof_to_advance": [
            "candidate emissions are verified or intentionally rejected",
            "source repo has current capture rules for the matched pattern families",
        ],
    },
    {
        "wave_id": "protected_central_only_review_wave",
        "label": "Protected repo central-only review",
        "human_gate": (
            "Protected repo local writes require explicit repo-specific approval; "
            "central-only analysis may continue."
        ),
        "generated_next_step": (
            "Keep evidence central, summarize candidate signals, and request "
            "repo-specific approval before any local enrollment or backfill action."
        ),
        "danger_if_misapplied": (
            "A useful exception signal could become an unauthorized protected-repo write."
        ),
        "proof_to_advance": [
            "protected repo approval id is recorded, or the action remains central-only",
            "public/private release and write-protection gates are satisfied",
        ],
    },
    {
        "wave_id": "policy_enablement_wave",
        "label": "Resolve reviewed policy blockers",
        "human_gate": "Requires reviewed exceptions.repos policy change or explicit approval id.",
        "generated_next_step": (
            "Classify the repo, enable exception collection/backfill if appropriate, "
            "or keep it blocked with a reason."
        ),
        "danger_if_misapplied": (
            "DAD could backfill from repos that were never reviewed for visibility, "
            "sensitivity, or source authority."
        ),
        "proof_to_advance": [
            "exceptions.repos policy exists for the repo",
            "exceptions_enabled, capture_audit_allowed, and backfill_allowed match the reviewed decision",
        ],
    },
    {
        "wave_id": "approval_review_wave",
        "label": "Add reviewed backfill approval ids",
        "human_gate": "Requires a specific reviewed approval id before non-DAD backfill.",
        "generated_next_step": (
            "Create or attach a reviewed approval id for repos that are otherwise "
            "eligible but cannot run historical backfill yet."
        ),
        "danger_if_misapplied": (
            "A generic or invented approval string could bypass the historical-backfill gate."
        ),
        "proof_to_advance": [
            "approved_approval_ids includes the exact id used for backfill",
            "approval scope names repo, visibility, path-ref policy, and candidate limits",
        ],
    },
    {
        "wave_id": "metadata_backfill_candidate_wave",
        "label": "Run metadata-only candidate backfill",
        "human_gate": "DAD self-backfill may run now; non-DAD repos need reviewed approval ids.",
        "generated_next_step": (
            "Run metadata-only backfill with hash-only path refs, bounded limits, "
            "and reviewed approval ids where required."
        ),
        "danger_if_misapplied": (
            "Path-name candidates could be mistaken for confirmed incidents or learning-ready data."
        ),
        "proof_to_advance": [
            "backfill events remain capture_contract=backfill_candidate",
            "learning queue keeps backfill-only clusters in source-review status",
        ],
    },
    {
        "wave_id": "watch_or_no_signal_wave",
        "label": "Watch repos with no actionable historical signal",
        "human_gate": "No action unless new evidence or policy changes appear.",
        "generated_next_step": (
            "Do not backfill now; revisit after capture-surface updates, new mail, "
            "or a higher-signal scan."
        ),
        "danger_if_misapplied": "Low-signal repos can consume review time without improving the lake.",
        "proof_to_advance": [
            "new candidate signals appear",
            "repo sends exception/fix packets through the current capture surface",
        ],
    },
]


def _primary_backfill_wave(row: dict[str, Any]) -> str:
    if row.get("write_protected") or row.get("backfill_readiness") == "central_only_or_blocked":
        return "protected_central_only_review_wave"
    if (
        not row.get("reviewed_policy")
        or not row.get("exceptions_enabled")
        or not row.get("backfill_allowed")
    ):
        return "policy_enablement_wave"
    if not row.get("candidate_path_signal_count"):
        return "watch_or_no_signal_wave"
    scan = row.get("candidate_path_scan", {})
    if isinstance(scan, dict) and scan.get("truncated"):
        return "bounded_sample_rescan_wave"
    if row.get("capture_surface_action") != "current":
        return "capture_surface_refresh_wave"
    if row.get("backfill_readiness") == "needs_full_scan_review":
        return "capture_gap_review_wave"
    if row.get("backfill_readiness") in {"ready_now", "ready_with_reviewed_approval"}:
        return "metadata_backfill_candidate_wave"
    if row.get("backfill_readiness") == "approval_needed":
        return "approval_review_wave"
    return "watch_or_no_signal_wave"


EMISSION_REVIEW_FLAGS = {
    "missed_capture_candidate",
    "pattern_gap_candidate",
    "mail_present_exception_gap_candidate",
    "emission_unverified",
    "type_present_uncorrelated",
}


def _repo_proof_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    scan = row.get("candidate_path_scan", {})
    summary = row.get("candidate_path_signal_summary", {})
    status_flags = set(row.get("status_flags", []))
    if row.get("capture_surface_action") != "current":
        blockers.append("capture_surface_not_current")
    if isinstance(scan, dict) and scan.get("truncated"):
        blockers.append("observed_audit_truncated")
    if isinstance(summary, dict) and summary.get("omitted_signal_count_unknown"):
        blockers.append("observed_audit_omitted_signal_count_unknown")
    if status_flags & EMISSION_REVIEW_FLAGS:
        blockers.append("emissions_missing_unverified_or_uncorrelated")
    if (
        row.get("classifier_version_missing")
        or row.get("classifier_version_stale")
        or int(row.get("classifier_version_missing_count") or 0)
        or int(row.get("classifier_version_stale_count") or 0)
    ):
        blockers.append("classifier_provenance_missing_or_stale")
    return blockers


def _repo_wave_ref(row: dict[str, Any]) -> dict[str, Any]:
    summary = row.get("candidate_path_signal_summary", {})
    return {
        "repo_id": row.get("repo_id"),
        "repo_alias": row.get("repo_alias"),
        "path_hash": row.get("path_hash"),
        "visibility": row.get("visibility"),
        "public_facing": row.get("public_facing"),
        "backfill_readiness": row.get("backfill_readiness"),
        "capture_surface_action": row.get("capture_surface_action"),
        "candidate_path_signal_count": row.get("candidate_path_signal_count"),
        "proof_blockers": _repo_proof_blockers(row),
        "classifier_version_missing_count": row.get("classifier_version_missing_count", 0),
        "classifier_version_stale_count": row.get("classifier_version_stale_count", 0),
        "status_flags": row.get("status_flags", []),
        "blocked_reasons": row.get("blocked_reasons", []),
        "next_actions": row.get("next_actions", []),
        "top_suggested_event_types": _top_counter_items(
            summary.get("by_suggested_event_type", {})
            if isinstance(summary, dict)
            else {}
        ),
        "top_source_rule_ids": _top_counter_items(
            summary.get("by_source_rule_id", {})
            if isinstance(summary, dict)
            else {}
        ),
    }


PROOF_BACKLOG_DEFINITIONS: list[dict[str, Any]] = [
    {
        "backlog_id": "capture_surface_refresh_backlog",
        "label": "Capture surface refresh proof backlog",
        "reason": "Repos need a current capture surface before no-packet or missing-packet evidence can be trusted.",
    },
    {
        "backlog_id": "exhaustive_audit_backlog",
        "label": "Exhaustive observed-audit proof backlog",
        "reason": "Bounded first-N scans cannot prove historical exception-pattern coverage.",
    },
    {
        "backlog_id": "emission_review_backlog",
        "label": "Emission review proof backlog",
        "reason": "Missing, unverified, or uncorrelated emissions need source/local review before backfill promotion.",
    },
    {
        "backlog_id": "classifier_refresh_backlog",
        "label": "Classifier refresh proof backlog",
        "reason": "Backfill review evidence with missing or stale classifier provenance must be rerun or invalidated before source review.",
    },
    {
        "backlog_id": "ready_for_source_packet_request",
        "label": "Ready for source-packet request planning",
        "reason": "Repos with current surfaces, complete scans, and no emission blockers can advance toward source confirmation or explicit rejection.",
    },
]


CAPTURE_REMEDIATION_LANE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "lane_id": "protected_central_only_review",
        "label": "Protected or central-only repo review",
        "why_it_exists": "Protected repos can be audited centrally, but local repair or enrollment writes need explicit repo-specific approval.",
        "safe_next_actions": [
            "Keep the candidate evidence in DAD reports only.",
            "Request explicit protected-repo approval before local capture-surface repair.",
        ],
        "write_policy": "central_only_until_explicit_approval",
    },
    {
        "lane_id": "capture_surface_refresh_required",
        "label": "Capture surface refresh required",
        "why_it_exists": "A repo cannot be judged for missing packets until it has the current DAD capture rules.",
        "safe_next_actions": [
            "Plan a reviewed enrollment/update repair for the repo capture surface.",
            "Rerun observed audit after the repo reports the current capture surface version.",
        ],
        "write_policy": "enrollment_update_requires_approval",
    },
    {
        "lane_id": "exhaustive_rescan_required",
        "label": "Exhaustive metadata rescan required",
        "why_it_exists": "Bounded first-N path scans can hide important exception families and create false confidence.",
        "safe_next_actions": [
            "Rerun capture-audit or backfill-readiness with --candidate-limit 0.",
            "Treat existing counts as routing hints, not complete evidence.",
        ],
        "write_policy": "central_only_read_only",
    },
    {
        "lane_id": "emission_review_required",
        "label": "Emission review required",
        "why_it_exists": "Candidate path signals are not correlated to current mail, exception, or fix-outcome packets.",
        "safe_next_actions": [
            "Review whether the source repo should emit ordinary mail, exception events, or fix outcomes for the matched families.",
            "Add or update synthetic capture scenarios before declaring the pattern fixed.",
        ],
        "write_policy": "central_only_until_repo_capture_policy_is_current",
    },
    {
        "lane_id": "classifier_provenance_refresh_required",
        "label": "Classifier provenance refresh required",
        "why_it_exists": "Historical backfill evidence with missing or stale classifier provenance is not promotion-ready.",
        "safe_next_actions": [
            "Refresh or invalidate stale classifier outputs.",
            "Keep learning-queue promotion blocked until classifier provenance is current.",
        ],
        "write_policy": "central_only_read_only",
    },
    {
        "lane_id": "policy_or_approval_review_required",
        "label": "Policy or approval review required",
        "why_it_exists": "The repo is not allowed to collect, audit, or backfill exceptions under reviewed policy yet.",
        "safe_next_actions": [
            "Classify the repo in reviewed exceptions policy.",
            "Add a scoped approval id only if metadata backfill is intentional.",
        ],
        "write_policy": "central_only_until_reviewed_policy",
    },
    {
        "lane_id": "ready_for_source_packet_request",
        "label": "Ready for source-packet request planning",
        "why_it_exists": "Current capture surfaces and clean proof blockers allow DAD to ask for source-confirmation packets instead of guessing.",
        "safe_next_actions": [
            "Generate source-packet requests through DAD's reviewed request report.",
            "Keep source content local; DAD should receive safe summaries, paths, hashes, and review decisions.",
        ],
        "write_policy": "mailbox_candidate_only_when_policy_allows",
    },
    {
        "lane_id": "watch_or_no_action",
        "label": "Watch or no action",
        "why_it_exists": "No current candidate signals require a repair lane.",
        "safe_next_actions": [
            "Leave the repo in daily/weekly watch.",
            "Revisit when capture patterns, repo mail, or exception events change.",
        ],
        "write_policy": "no_target_repo_write",
    },
]


def _proof_backlog_ids(row: dict[str, Any]) -> list[str]:
    backlog_ids: list[str] = []
    blockers = set(_repo_proof_blockers(row))
    if "capture_surface_not_current" in blockers:
        backlog_ids.append("capture_surface_refresh_backlog")
    if blockers & {
        "observed_audit_truncated",
        "observed_audit_omitted_signal_count_unknown",
    }:
        backlog_ids.append("exhaustive_audit_backlog")
    if "emissions_missing_unverified_or_uncorrelated" in blockers:
        backlog_ids.append("emission_review_backlog")
    if "classifier_provenance_missing_or_stale" in blockers:
        backlog_ids.append("classifier_refresh_backlog")
    if (
        row.get("candidate_path_signal_count")
        and row.get("capture_surface_action") == "current"
        and not blockers
        and row.get("backfill_readiness") in {"ready_now", "ready_with_reviewed_approval"}
    ):
        backlog_ids.append("ready_for_source_packet_request")
    return backlog_ids


def _capture_remediation_lane_ids(row: dict[str, Any]) -> list[str]:
    lane_ids: list[str] = []
    blockers = set(_repo_proof_blockers(row))
    if row.get("write_protected") or row.get("backfill_readiness") == "central_only_or_blocked":
        lane_ids.append("protected_central_only_review")
    if "capture_surface_not_current" in blockers:
        lane_ids.append("capture_surface_refresh_required")
    if blockers & {
        "observed_audit_truncated",
        "observed_audit_omitted_signal_count_unknown",
    }:
        lane_ids.append("exhaustive_rescan_required")
    if "emissions_missing_unverified_or_uncorrelated" in blockers:
        lane_ids.append("emission_review_required")
    if "classifier_provenance_missing_or_stale" in blockers:
        lane_ids.append("classifier_provenance_refresh_required")
    if (
        not row.get("reviewed_policy")
        or not row.get("exceptions_enabled")
        or not row.get("capture_audit_allowed", True)
        or not row.get("backfill_allowed")
        or row.get("backfill_readiness") == "approval_needed"
    ):
        lane_ids.append("policy_or_approval_review_required")
    if _proof_backlog_ids(row) == ["ready_for_source_packet_request"]:
        lane_ids.append("ready_for_source_packet_request")
    if not lane_ids:
        lane_ids.append("watch_or_no_action")
    return sorted(dict.fromkeys(lane_ids))


def _repo_write_policy(row: dict[str, Any]) -> str:
    if row.get("write_protected") or row.get("backfill_readiness") == "central_only_or_blocked":
        return "protected_central_only"
    if row.get("public_facing"):
        return "public_safe_metadata_only"
    if not row.get("reviewed_policy") or not row.get("exceptions_enabled"):
        return "central_only_until_reviewed_policy"
    if row.get("collect_allowed") and row.get("capture_audit_allowed", True):
        return "mailbox_or_exception_candidate_only"
    return "central_only_until_policy_allows_collection"


def _repo_capture_remediation_ref(row: dict[str, Any]) -> dict[str, Any]:
    summary = row.get("candidate_path_signal_summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return {
        "repo_id": row.get("repo_id"),
        "repo_alias": row.get("repo_alias"),
        "path_hash": row.get("path_hash"),
        "visibility": row.get("visibility"),
        "public_facing": row.get("public_facing"),
        "write_policy": _repo_write_policy(row),
        "remediation_lanes": _capture_remediation_lane_ids(row),
        "backfill_readiness": row.get("backfill_readiness"),
        "capture_surface_action": row.get("capture_surface_action"),
        "candidate_path_signal_count": row.get("candidate_path_signal_count"),
        "candidate_path_scan": row.get("candidate_path_scan", {}),
        "proof_blockers": _repo_proof_blockers(row),
        "status_flags": row.get("status_flags", []),
        "blocked_reasons": row.get("blocked_reasons", []),
        "next_actions": sorted(set(row.get("next_actions", []))),
        "top_pattern_families": _top_counter_items(
            summary.get("by_pattern_family", {}),
        ),
        "top_suggested_event_types": _top_counter_items(
            summary.get("by_suggested_event_type", {}),
        ),
        "top_source_rule_ids": _top_counter_items(
            summary.get("by_source_rule_id", {}),
        ),
    }


def build_exception_capture_remediation_plan(
    readiness_report: dict[str, Any],
    *,
    per_lane_repo_limit: int = 25,
) -> dict[str, Any]:
    rows = [
        row
        for row in readiness_report.get("repos", [])
        if isinstance(row, dict)
    ]
    per_lane_repo_limit = max(1, per_lane_repo_limit)
    rows_by_lane: dict[str, list[dict[str, Any]]] = {
        lane["lane_id"]: [] for lane in CAPTURE_REMEDIATION_LANE_DEFINITIONS
    }
    for row in rows:
        for lane_id in _capture_remediation_lane_ids(row):
            rows_by_lane.setdefault(lane_id, []).append(row)
    lanes: list[dict[str, Any]] = []
    for order, definition in enumerate(CAPTURE_REMEDIATION_LANE_DEFINITIONS, start=1):
        lane_rows = sorted(
            rows_by_lane.get(definition["lane_id"], []),
            key=lambda row: (
                -int(row.get("candidate_path_signal_count") or 0),
                str(row.get("repo_id") or ""),
            ),
        )
        shown = lane_rows[:per_lane_repo_limit]
        lanes.append(
            {
                **definition,
                "sequence_order": order,
                "repo_count": len(lane_rows),
                "reported_repo_count": len(shown),
                "omitted_repo_count": max(0, len(lane_rows) - len(shown)),
                "candidate_path_signal_summary": _merge_candidate_signal_summaries(
                    lane_rows,
                ),
                "repos": [_repo_capture_remediation_ref(row) for row in shown],
                "review_status": "planning_only",
            }
        )
    return {
        "generated_at": utc_now(),
        "report_id": "dad:exception-capture-remediation-plan",
        "source_report_id": readiness_report.get("report_id"),
        "repo_count": len(rows),
        "per_lane_repo_limit": per_lane_repo_limit,
        "current_lane_id": next(
            (lane["lane_id"] for lane in lanes if lane["repo_count"]),
            "watch_or_no_action",
        ),
        "lane_order": [lane["lane_id"] for lane in lanes],
        "readiness_counts": readiness_report.get("readiness_counts", {}),
        "status_counts": readiness_report.get("status_counts", {}),
        "capture_surface_action_counts": readiness_report.get(
            "capture_surface_action_counts",
            {},
        ),
        "candidate_path_signal_summary": readiness_report.get(
            "candidate_path_signal_summary",
            {},
        ),
        "input_hashes": readiness_report.get("input_hashes", {}),
        "methodology_ref": readiness_report.get("methodology_ref"),
        "methodology_hash": readiness_report.get("methodology_hash"),
        "lanes": lanes,
        "pass_condition": (
            "No repos in capture_surface_refresh_required, exhaustive_rescan_required, "
            "emission_review_required, classifier_provenance_refresh_required, or "
            "policy_or_approval_review_required; protected repos remain central-only "
            "unless explicitly approved."
        ),
        "authority_boundary": (
            "Capture remediation planning is central-only candidate evidence. It "
            "does not mutate target repos, approve protected-repo writes, copy raw "
            "private content, or prove that path-name signals are real exceptions."
        ),
    }


def _capture_remediation_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Exception Capture Remediation Plan",
        "",
        f"- Generated: {plan['generated_at']}",
        f"- Repos planned: {plan['repo_count']}",
        f"- Current lane: `{plan['current_lane_id']}`",
        f"- Methodology hash: `{plan.get('methodology_hash', '')}`",
        "",
        "Boundary: central-only candidate evidence. This report does not write "
        "target repos or approve historical backfill.",
        "",
        "Purpose: identify what must be repaired so repo agents emit the right "
        "mail, exception, or fix-outcome packets without human rescue from chat.",
        "",
        "## Lane Order",
        "",
    ]
    lines.extend(f"- `{lane_id}`" for lane_id in plan["lane_order"])
    for lane in plan["lanes"]:
        lines.extend(
            [
                "",
                f"## {lane['sequence_order']}. {lane['label']}",
                "",
                f"- Lane id: `{lane['lane_id']}`",
                f"- Repo count: **{lane['repo_count']}**",
                f"- Candidate path signals: **{lane['candidate_path_signal_summary']['total']}**",
                f"- Write policy: `{lane['write_policy']}`",
                f"- Why: {lane['why_it_exists']}",
                "",
                "Safe next actions:",
            ]
        )
        lines.extend(f"- {action}" for action in lane["safe_next_actions"])
        if lane["candidate_path_signal_summary"].get("omitted_signal_count_unknown"):
            lines.append(
                "- Count scope: bounded first-N sample; rerun before treating "
                "counts as complete."
            )
        if lane["repos"]:
            lines.extend(["", "Repos in this lane:"])
            for repo in lane["repos"]:
                blockers = ", ".join(f"`{item}`" for item in repo["proof_blockers"]) or "-"
                lines.append(
                    "- `"
                    + str(repo["repo_id"])
                    + "` "
                    + f"signals={repo['candidate_path_signal_count']} "
                    + f"surface=`{repo['capture_surface_action']}` "
                    + f"write_policy=`{repo['write_policy']}` "
                    + f"blockers={blockers}"
                )
    return "\n".join(lines) + "\n"


def write_exception_capture_remediation_plan(
    hub_root: Path,
    repos: list[Path],
    *,
    repo_policies: list[Any] | None = None,
    output: Path | None = None,
    candidate_limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
    per_lane_repo_limit: int = 25,
) -> dict[str, Any]:
    plan_output = output or CAPTURE_REMEDIATION_PLAN_JSON
    readiness_output = plan_output.with_name(plan_output.stem + "_readiness.json")
    readiness_report = write_exception_backfill_readiness(
        hub_root,
        repos,
        repo_policies=repo_policies,
        output=readiness_output,
        candidate_limit=candidate_limit,
        max_scanned_files=max_scanned_files,
    )
    plan = build_exception_capture_remediation_plan(
        readiness_report,
        per_lane_repo_limit=per_lane_repo_limit,
    )
    output_path = _capture_output_path(hub_root, output, CAPTURE_REMEDIATION_PLAN_JSON)
    write_json(output_path, plan)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, CAPTURE_REMEDIATION_PLAN_MD)
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_capture_remediation_plan_markdown(plan), encoding="utf-8")
    return plan


def _staged_mail_identity(record: dict[str, Any]) -> tuple[str, str]:
    return str(record.get("mail_id") or ""), str(record.get("dedupe_key") or "")


def _safe_capture_notice_ref(value: Any, issues: list[str], *, field: str) -> str:
    text = str(value or "").strip()
    if text and CAPTURE_NOTICE_SAFE_REF_RE.fullmatch(text):
        return text
    digest = sha256_bytes(text.encode("utf-8"))
    issues.append(f"{field}_redacted_to_hash_ref")
    return f"path-ref-sha256:{digest}"


def _safe_capture_notice_list(values: Any, issues: list[str], *, field: str) -> list[str]:
    safe: list[str] = []
    for index, item in enumerate(values or []):
        text = str(item or "").strip()
        if text and CAPTURE_SIGNAL_RE.fullmatch(text):
            safe.append(text)
        elif text:
            issues.append(f"{field}_{index}_redacted")
            safe.append(f"redacted-signal-sha256:{sha256_bytes(text.encode('utf-8'))}")
    return safe


def _safe_capture_notice_counter(values: Any, issues: list[str], *, field: str) -> dict[str, int]:
    if not isinstance(values, dict):
        return {}
    safe: Counter[str] = Counter()
    for key, value in values.items():
        text = str(key or "").strip()
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        if not count:
            continue
        if text and CAPTURE_SIGNAL_RE.fullmatch(text):
            safe[text] += count
        else:
            issues.append(f"{field}_redacted_key")
            safe[f"redacted-key-sha256:{sha256_bytes(text.encode('utf-8'))}"] += count
    return dict(sorted(safe.items()))


def _append_unique_capture_surface_refresh_notice(
    hub_root: Path,
    record: dict[str, Any],
) -> str:
    payload = MailMessageRecord(**record).model_dump(mode="json")
    identity = _staged_mail_identity(payload)
    dedupe_key = identity[1]
    stage_path = exception_capture_data_path(
        hub_root, CAPTURE_SURFACE_REFRESH_NOTICES_STAGED
    )
    with _jsonl_lock(stage_path):
        rows: list[dict[str, Any]] = []
        replaced = False
        exact_found = False
        if stage_path.exists():
            for line_number, line in enumerate(
                stage_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError as exc:
                    append_jsonl(
                        exception_capture_data_path(
                            hub_root, CAPTURE_SURFACE_REFRESH_NOTICE_QUARANTINE
                        ),
                        {
                            "event_type": "capture_surface_refresh_notice_malformed_jsonl",
                            "created_at": utc_now(),
                            "path": CAPTURE_SURFACE_REFRESH_NOTICES_STAGED.as_posix(),
                            "line_number": line_number,
                            "error": exc.msg,
                        },
                    )
                    continue
                if not isinstance(existing, dict):
                    continue
                existing_identity = _staged_mail_identity(existing)
                if existing_identity == identity:
                    if not exact_found:
                        rows.append(existing)
                        exact_found = True
                    continue
                if dedupe_key and existing_identity[1] == dedupe_key:
                    replaced = True
                    continue
                rows.append(existing)
        if exact_found:
            if replaced:
                write_jsonl(stage_path, rows, allow_direct_fallback=True)
                return "replaced"
            return "duplicate"
        if replaced:
            rows.append(payload)
            write_jsonl(stage_path, rows, allow_direct_fallback=True)
            return "replaced"
        append_jsonl(stage_path, payload)
    return "appended"


def _prune_inactive_capture_surface_refresh_notices(
    hub_root: Path,
    active_identities: set[tuple[str, str]],
) -> int:
    stage_path = exception_capture_data_path(
        hub_root, CAPTURE_SURFACE_REFRESH_NOTICES_STAGED
    )
    if not stage_path.exists():
        return 0
    with _jsonl_lock(stage_path):
        rows: list[dict[str, Any]] = []
        pruned = 0
        seen: set[tuple[str, str]] = set()
        for line_number, line in enumerate(
            stage_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError as exc:
                append_jsonl(
                    exception_capture_data_path(
                        hub_root, CAPTURE_SURFACE_REFRESH_NOTICE_QUARANTINE
                    ),
                    {
                        "event_type": "capture_surface_refresh_notice_malformed_jsonl",
                        "created_at": utc_now(),
                        "path": CAPTURE_SURFACE_REFRESH_NOTICES_STAGED.as_posix(),
                        "line_number": line_number,
                        "error": exc.msg,
                    },
                )
                pruned += 1
                continue
            if not isinstance(existing, dict):
                pruned += 1
                continue
            identity = _staged_mail_identity(existing)
            if identity not in active_identities or identity in seen:
                pruned += 1
                continue
            rows.append(existing)
            seen.add(identity)
        write_jsonl(stage_path, rows, allow_direct_fallback=True)
    return pruned


def _capture_surface_refresh_notice_mail(
    repo: dict[str, Any],
    plan: dict[str, Any],
    *,
    registry_capture_surface_version: str,
) -> dict[str, Any]:
    created_at = utc_now()
    screening_issues: list[str] = []
    repo_id = _safe_capture_notice_ref(
        repo.get("repo_id") or repo.get("path_hash") or "unknown",
        screening_issues,
        field="repo_id",
    )
    repo_alias = _safe_capture_notice_ref(
        repo.get("repo_alias") or repo_id,
        screening_issues,
        field="repo_alias",
    )
    target_visibility = str(repo.get("visibility") or "unknown")
    target_public_facing = bool(repo.get("public_facing"))
    public_release_required = target_public_facing
    dedupe_key = stable_id(
        "exception-capture-surface-refresh",
        repo_id,
        str(repo.get("path_hash") or ""),
        registry_capture_surface_version,
    )
    payload = {
        "summary": "DAD exception capture surface is stale or missing for this repo.",
        "notice_type": "capture_surface_refresh_required",
        "source_ref": "dad://exceptions/capture-surface-refresh-notices",
        "repo_id": repo_id,
        "repo_alias": repo_alias,
        "visibility": target_visibility,
        "public_facing": target_public_facing,
        "write_policy": str(repo.get("write_policy") or ""),
        "capture_surface_action": str(repo.get("capture_surface_action") or ""),
        "registry_capture_surface_version": registry_capture_surface_version,
        "candidate_path_signal_count": int(repo.get("candidate_path_signal_count") or 0),
        "proof_blockers": _safe_capture_notice_list(
            repo.get("proof_blockers", [])[:12],
            screening_issues,
            field="proof_blockers",
        ),
        "status_flags": _safe_capture_notice_list(
            repo.get("status_flags", [])[:12],
            screening_issues,
            field="status_flags",
        ),
        "top_pattern_families": _safe_capture_notice_counter(
            repo.get("top_pattern_families"),
            screening_issues,
            field="top_pattern_families",
        ),
        "top_source_rule_ids": _safe_capture_notice_counter(
            repo.get("top_source_rule_ids"),
            screening_issues,
            field="top_source_rule_ids",
        ),
        "top_suggested_event_types": _safe_capture_notice_counter(
            repo.get("top_suggested_event_types"),
            screening_issues,
            field="top_suggested_event_types",
        ),
        "hash": str(plan.get("methodology_hash") or ""),
        "authority_boundary": "staged_central_candidate_only_no_target_repo_write",
        "promotion_boundary": "requires_reviewed_public_safe_transform_before_delivery",
    }
    if screening_issues:
        payload["screening_issues"] = sorted(set(screening_issues))
    record = _build_mail_record(
        message_type="governance_notice",
        source_repo="dad://hub/Digital-Assett-Directory",
        target_repo=repo_id,
        payload=payload,
        dedupe_key=dedupe_key,
        thread_id=stable_id("mail-thread", "dad", repo_id, "capture-surface-refresh"),
        sensitivity="internal",
        review_status="routed_candidate",
        evidence=[
            CAPTURE_REMEDIATION_PLAN_JSON.as_posix(),
            BACKFILL_WAVE_PLAN_JSON.as_posix(),
            CAPTURE_PATTERN_REGISTRY.as_posix(),
            f"repo_path_hash:{repo.get('path_hash', '')}",
            f"methodology_hash:{plan.get('methodology_hash', '')}",
        ],
        suggested_actions=[
            "Plan a reviewed enrollment/update repair before writing the repo.",
            "Refresh the repo capture surface to the current registry version.",
            "Rerun observed capture audit after the repo reports the current surface.",
            "Do not treat existing no-packet evidence as complete until this refresh is done.",
        ],
        source_provenance={
            "canonical_source_repo": "dad://hub/Digital-Assett-Directory",
            "source_repo_id": "dad",
            "source_repo_alias": "dad",
            "source_visibility": "internal",
            "original_source_chain": ["dad://hub/Digital-Assett-Directory"],
            "return_address": "dad://exceptions/capture-surface-refresh-notices",
            "original_mail_id": "",
            "composed_by": "dad-exception-capture",
            "collected_by": "dad",
            "collected_at": "",
            "received_at": created_at,
        },
        public_release={
            "target_visibility": target_visibility
            if target_visibility in {"public", "internal", "private", "restricted", "unknown"}
            else "unknown",
            "target_public_facing": target_public_facing,
            "public_release_required": public_release_required,
            "public_release_status": "pending_human"
            if public_release_required
            else "not_required",
            "human_release_id": "",
            "release_reason": "staged_capture_surface_refresh_notice",
        },
    )
    return record.model_copy(update={"source_repo": "dad"}).model_dump(mode="json")


def _capture_surface_refresh_notice_target_selection(
    remediation_plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets: dict[tuple[str, str], dict[str, Any]] = {}
    coverage = {
        "source_lane_repo_count": 0,
        "reported_repo_count": 0,
        "omitted_repo_count": 0,
        "partial": False,
    }
    for lane in remediation_plan.get("lanes", []):
        if not isinstance(lane, dict):
            continue
        if lane.get("lane_id") != "capture_surface_refresh_required":
            continue
        coverage = {
            "source_lane_repo_count": int(lane.get("repo_count") or 0),
            "reported_repo_count": int(lane.get("reported_repo_count") or 0),
            "omitted_repo_count": int(lane.get("omitted_repo_count") or 0),
            "partial": bool(int(lane.get("omitted_repo_count") or 0)),
        }
        for repo in lane.get("repos", []) or []:
            if not isinstance(repo, dict):
                continue
            key = (
                str(repo.get("repo_id") or ""),
                str(repo.get("path_hash") or ""),
            )
            targets[key] = repo
    return (
        sorted(
            targets.values(),
            key=lambda repo: (
                str(repo.get("repo_id") or ""),
                str(repo.get("path_hash") or ""),
            ),
        ),
        coverage,
    )


def _capture_surface_refresh_notices_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Exception Capture Surface Refresh Notices",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Target repos staged: {report['target_repo_count']}",
        f"- Source lane repos: {report['source_lane_repo_count']}",
        f"- Omitted repos: {report['omitted_repo_count']}",
        f"- Mail appended: {report['mail_appended_count']}",
        f"- Duplicate mail: {report['duplicate_mail_count']}",
        f"- Mail stage: `{report['mail_stage']}`",
        "",
        "Boundary: staged central candidate mail only. These notices are not under "
        "`processed/mail/outbox`, do not deliver mail, do not mutate target repos, "
        "and do not approve enrollment updates.",
        "",
    ]
    if report["partial"]:
        lines.extend(
            [
                "Warning: notice coverage is partial because the remediation lane "
                "was capped. Increase `--per-lane-repo-limit` and rerun before "
                "treating the staged notice set as complete.",
                "",
            ]
        )
    lines.extend(
        [
            "## Notices",
            "",
            "| Repo | Surface Action | Signals | Public Gate | Mail | Appended |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for notice in report["notices"]:
        lines.append(
            "| "
            + f"`{notice['repo_id']}` | "
            + f"`{notice['capture_surface_action']}` | "
            + f"{notice['candidate_path_signal_count']} | "
            + f"`{notice['public_release_status']}` | "
            + f"`{notice['mail_id']}` | "
            + f"{notice['mail_appended']} |"
        )
    if not report["notices"]:
        lines.append("| _none_ |  |  |  |  |  |")
    return "\n".join(lines) + "\n"


def write_exception_capture_surface_refresh_notices(
    hub_root: Path,
    repos: list[Path],
    *,
    repo_policies: list[Any] | None = None,
    output: Path | None = None,
    candidate_limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
    per_lane_repo_limit: int = 500,
    write_mail: bool = True,
) -> dict[str, Any]:
    registry = load_capture_pattern_registry(hub_root)
    remediation_plan = write_exception_capture_remediation_plan(
        hub_root,
        repos,
        repo_policies=repo_policies,
        candidate_limit=candidate_limit,
        max_scanned_files=max_scanned_files,
        per_lane_repo_limit=per_lane_repo_limit,
    )
    registry_capture_surface_version = str(registry.get("capture_surface_version") or "")
    targets, coverage = _capture_surface_refresh_notice_target_selection(remediation_plan)
    notices: list[dict[str, Any]] = []
    appended_count = 0
    duplicate_count = 0
    replaced_count = 0
    active_identities: set[tuple[str, str]] = set()
    for repo in targets:
        mail_record = _capture_surface_refresh_notice_mail(
            repo,
            remediation_plan,
            registry_capture_surface_version=registry_capture_surface_version,
        )
        active_identities.add(_staged_mail_identity(mail_record))
        append_status = "not_written"
        if write_mail:
            append_status = _append_unique_capture_surface_refresh_notice(hub_root, mail_record)
            if append_status == "appended":
                appended_count += 1
            elif append_status == "duplicate":
                duplicate_count += 1
            elif append_status == "replaced":
                replaced_count += 1
        public_release = mail_record["public_release"]
        notices.append(
            {
                "repo_id": mail_record["target_repo"],
                "mail_id": mail_record["mail_id"],
                "dedupe_key": mail_record["dedupe_key"],
                "mail_appended": append_status == "appended",
                "append_status": append_status,
                "capture_surface_action": str(repo.get("capture_surface_action") or ""),
                "candidate_path_signal_count": int(
                    repo.get("candidate_path_signal_count") or 0
                ),
                "write_policy": str(repo.get("write_policy") or ""),
                "public_release_required": public_release["public_release_required"],
                "public_release_status": public_release["public_release_status"],
            }
        )
    stale_pruned_count = (
        _prune_inactive_capture_surface_refresh_notices(hub_root, active_identities)
        if write_mail
        else 0
    )
    report = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "report_id": "dad:exception-capture-surface-refresh-notices",
        "source_report_id": remediation_plan.get("report_id"),
        "target_repo_count": len(targets),
        "source_lane_repo_count": coverage["source_lane_repo_count"],
        "reported_repo_count": coverage["reported_repo_count"],
        "omitted_repo_count": coverage["omitted_repo_count"],
        "partial": coverage["partial"],
        "coverage_status": (
            "partial_bounded_lane"
            if coverage["partial"]
            else "complete_for_reported_remediation_lane"
        ),
        "mail_appended_count": appended_count,
        "duplicate_mail_count": duplicate_count,
        "mail_replaced_count": replaced_count,
        "stale_mail_pruned_count": stale_pruned_count,
        "mail_stage": CAPTURE_SURFACE_REFRESH_NOTICES_STAGED.as_posix(),
        "registry_capture_surface_version": registry_capture_surface_version,
        "methodology_ref": remediation_plan.get("methodology_ref"),
        "methodology_hash": remediation_plan.get("methodology_hash"),
        "input_hashes": remediation_plan.get("input_hashes", {}),
        "notices": notices,
        "authority_boundary": (
            "Capture-surface refresh notices are DAD-authored staged candidate mail. "
            "They are intentionally not written to processed/mail/outbox and are not "
            "deliverable until a separate reviewed promotion path exists. They do not "
            "mutate target repos, approve enrollment updates, or prove that path-name "
            "signals are real exceptions."
        ),
    }
    output_path = _capture_output_path(
        hub_root, output, CAPTURE_SURFACE_REFRESH_NOTICES_JSON
    )
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, CAPTURE_SURFACE_REFRESH_NOTICES_MD)
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_capture_surface_refresh_notices_markdown(report), encoding="utf-8")
    return report


def _observed_row_write_policy(row: dict[str, Any]) -> str:
    repo = row.get("repo", {})
    if not isinstance(repo, dict):
        repo = {}
    if repo.get("write_protected"):
        return "protected_central_only"
    if repo.get("public_facing"):
        return "public_safe_metadata_only"
    if not repo.get("reviewed_policy") or not repo.get("exceptions_enabled"):
        return "central_only_until_reviewed_policy"
    if repo.get("collect_allowed") and repo.get("capture_audit_allowed", True):
        return "mailbox_or_exception_candidate_only"
    return "central_only_until_policy_allows_collection"


def _observed_row_remediation_lanes(row: dict[str, Any]) -> list[str]:
    repo = row.get("repo", {})
    if not isinstance(repo, dict):
        repo = {}
    lane_ids: list[str] = []
    if repo.get("write_protected") or "protected_repo_central_only" in row.get("status_flags", []):
        lane_ids.append("protected_central_only_review")
    if _capture_surface_action(row) != "current":
        lane_ids.append("capture_surface_refresh_required")
    scan = row.get("candidate_path_scan", {})
    if isinstance(scan, dict) and scan.get("truncated"):
        lane_ids.append("exhaustive_rescan_required")
    if set(row.get("status_flags", [])) & EMISSION_REVIEW_FLAGS:
        lane_ids.append("emission_review_required")
    if (
        not repo.get("reviewed_policy")
        or not repo.get("exceptions_enabled")
        or not repo.get("capture_audit_allowed", True)
        or not repo.get("backfill_allowed", False)
    ):
        lane_ids.append("policy_or_approval_review_required")
    return sorted(dict.fromkeys(lane_ids or ["watch_or_no_action"]))


def _capture_gap_next_actions(
    *,
    capture_surface_action: str,
    emission_status: str,
    suggested_event_type: str,
    expected_review: str,
    remediation_lanes: list[str],
) -> list[str]:
    actions: list[str] = []
    if capture_surface_action != "current":
        actions.append("refresh or install the repo capture surface before treating the gap as current")
    if "protected_central_only_review" in remediation_lanes:
        actions.append("keep protected-repo evidence central-only unless explicit local-write approval exists")
    if "policy_or_approval_review_required" in remediation_lanes:
        actions.append("resolve reviewed exceptions policy or approval blockers before any source request")
    if emission_status == "gap_candidate":
        actions.append("decide whether this path signal should emit candidate mail, an exception event, or no packet")
    elif emission_status == "type_present_uncorrelated":
        actions.append("correlate existing packet type to this path signal or mark the signal as intentionally no-packet")
    elif emission_status == "unverified":
        actions.append("ask the source repo or reviewer to confirm whether the signal is real before backfill")
    if suggested_event_type != "<none>":
        actions.append(f"if confirmed, route through `{suggested_event_type}` with source-owned context")
    elif "ordinary_mail" in expected_review:
        actions.append("if useful but not an exception, route as candidate ordinary mail or local usage evidence")
    return sorted(dict.fromkeys(actions))


def build_exception_capture_gap_review_queue(
    observed_report: dict[str, Any],
    *,
    per_group_example_limit: int = 5,
) -> dict[str, Any]:
    rows = [
        row
        for row in observed_report.get("repos", [])
        if isinstance(row, dict)
    ]
    per_group_example_limit = max(1, per_group_example_limit)
    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        repo = row.get("repo", {})
        if not isinstance(repo, dict):
            repo = {}
        repo_id = str(repo.get("repo_id") or "")
        repo_path_hash = str(repo.get("path_hash") or "<missing_path_hash>")
        remediation_lanes = _observed_row_remediation_lanes(row)
        capture_surface_action = _capture_surface_action(row)
        write_policy = _observed_row_write_policy(row)
        for signal in row.get("candidate_path_signals", []):
            if not isinstance(signal, dict):
                continue
            emission_status = str(signal.get("emission_status") or "<unannotated>")
            if emission_status not in ACTIONABLE_CAPTURE_GAP_EMISSION_STATUSES:
                continue
            pattern_family = str(signal.get("pattern_family") or "<unknown>")
            suggested_event_type = str(signal.get("suggested_event_type") or "<none>")
            source_rule_id = str(signal.get("source_rule_id") or "<builtin_path_term>")
            expected_review = str(signal.get("expected_review") or "<unknown>")
            capture_rule_ids = tuple(
                sorted(
                    str(rule_id)
                    for rule_id in (signal.get("capture_suggestion") or {}).get(
                        "matched_rule_ids",
                        [],
                    )
                )
            )
            capture_rule_key = ",".join(capture_rule_ids) or "<none>"
            key = (
                repo_id,
                repo_path_hash,
                pattern_family,
                suggested_event_type,
                source_rule_id,
                expected_review,
                emission_status,
                capture_rule_key,
            )
            group = grouped.setdefault(
                key,
                {
                    "repo_id": repo_id,
                    "repo_alias": repo.get("repo_alias"),
                    "path_hash": repo_path_hash,
                    "visibility": repo.get("visibility"),
                    "public_facing": repo.get("public_facing"),
                    "write_policy": write_policy,
                    "capture_surface_action": capture_surface_action,
                    "remediation_lanes": remediation_lanes,
                    "pattern_family": pattern_family,
                    "suggested_event_type": suggested_event_type,
                    "source_rule_id": source_rule_id,
                    "expected_review": expected_review,
                    "emission_status": emission_status,
                    "capture_rule_ids": list(capture_rule_ids),
                    "candidate_signal_count": 0,
                    "term_counts": Counter(),
                    "path_hashes": [],
                    "path_hash_seen": set(),
                    "redacted_path_count": 0,
                    "unredacted_path_count": 0,
                    "unknown_path_redaction_count": 0,
                },
            )
            group["candidate_signal_count"] += 1
            group["term_counts"].update([str(signal.get("term") or "<unknown>")])
            path_redacted = str(signal.get("path_redacted", "")).lower()
            if path_redacted == "true":
                group["redacted_path_count"] += 1
            elif path_redacted == "false":
                group["unredacted_path_count"] += 1
            else:
                group["unknown_path_redaction_count"] += 1
            path_hash = str(signal.get("path_hash") or "")
            if (
                path_hash
                and path_hash not in group["path_hash_seen"]
                and len(group["path_hashes"]) < per_group_example_limit
            ):
                group["path_hash_seen"].add(path_hash)
                group["path_hashes"].append(path_hash)
    groups: list[dict[str, Any]] = []
    for key, group in grouped.items():
        term_counts = group.pop("term_counts")
        group.pop("path_hash_seen", None)
        group["review_group_id"] = stable_id("exception-capture-gap-review-group", *key)
        group["top_terms"] = _top_counter_items(_counter_dict(term_counts))
        group["next_actions"] = _capture_gap_next_actions(
            capture_surface_action=str(group["capture_surface_action"]),
            emission_status=str(group["emission_status"]),
            suggested_event_type=str(group["suggested_event_type"]),
            expected_review=str(group["expected_review"]),
            remediation_lanes=[
                str(item) for item in group.get("remediation_lanes", [])
            ],
        )
        groups.append(group)
    groups.sort(
        key=lambda group: (
            -int(group["candidate_signal_count"]),
            str(group["repo_id"]),
            str(group["pattern_family"]),
            str(group["suggested_event_type"]),
            str(group["emission_status"]),
        )
    )
    return {
        "generated_at": utc_now(),
        "report_id": "dad:exception-capture-gap-review-queue",
        "source_report_id": observed_report.get("audit_id"),
        "repo_count": len(rows),
        "review_group_count": len(groups),
        "candidate_signal_count": sum(int(group["candidate_signal_count"]) for group in groups),
        "per_group_example_limit": per_group_example_limit,
        "capture_surface_version": observed_report.get("capture_surface_version"),
        "status_counts": observed_report.get("status_counts", {}),
        "candidate_path_signal_summary": observed_report.get(
            "candidate_path_signal_summary",
            {},
        ),
        "input_hashes": observed_report.get("input_hashes", {}),
        "methodology_ref": observed_report.get("methodology_ref"),
        "methodology_hash": observed_report.get("methodology_hash"),
        "groups": groups,
        "authority_boundary": (
            "Capture gap review queues are central-only candidate evidence. "
            "They group path-hash signals for source review, do not copy readable "
            "paths or raw source content, and do not approve repo writes, delivery, "
            "backfill, or learning promotion."
        ),
    }


def _markdown_table_cell(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _capture_gap_review_queue_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Exception Capture Gap Review Queue",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Repos: {report['repo_count']}",
        f"- Review groups: {report['review_group_count']}",
        f"- Candidate signals grouped: {report['candidate_signal_count']}",
        f"- Methodology hash: `{report.get('methodology_hash', '')}`",
        "",
        "Boundary: central-only candidate evidence. This queue stores path hashes "
        "and safe metadata for review; it does not write target repos, deliver "
        "mail, run backfill, or promote learning.",
        "",
        "## Top Groups",
        "",
        "| Group | Repo | Family | Event Type | Status | Signals | Next Actions |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for group in report.get("groups", [])[:50]:
        actions = "<br>".join(
            _markdown_table_cell(item) for item in group.get("next_actions", [])
        ) or "-"
        lines.append(
            "| "
            + f"`{_markdown_table_cell(group['review_group_id'])}` | "
            + f"`{_markdown_table_cell(group['repo_id'])}` | "
            + f"`{_markdown_table_cell(group['pattern_family'])}` | "
            + f"`{_markdown_table_cell(group['suggested_event_type'])}` | "
            + f"`{_markdown_table_cell(group['emission_status'])}` | "
            + f"{group['candidate_signal_count']} | "
            + actions
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_exception_capture_gap_review_queue(
    hub_root: Path,
    repos: list[Path],
    *,
    repo_policies: list[Any] | None = None,
    output: Path | None = None,
    candidate_limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
    per_group_example_limit: int = 5,
) -> dict[str, Any]:
    queue_output = output or CAPTURE_GAP_REVIEW_QUEUE_JSON
    observed_output = queue_output.with_name(queue_output.stem + "_observed_audit.json")
    observed_report = write_observed_capture_audit(
        hub_root,
        repos,
        repo_policies=repo_policies,
        output=observed_output,
        candidate_limit=candidate_limit,
        max_scanned_files=max_scanned_files,
    )
    report = build_exception_capture_gap_review_queue(
        observed_report,
        per_group_example_limit=per_group_example_limit,
    )
    output_path = _capture_output_path(hub_root, output, CAPTURE_GAP_REVIEW_QUEUE_JSON)
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, CAPTURE_GAP_REVIEW_QUEUE_MD)
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_capture_gap_review_queue_markdown(report), encoding="utf-8")
    return report


def _build_proof_backlogs(
    rows: list[dict[str, Any]],
    *,
    per_backlog_repo_limit: int,
) -> list[dict[str, Any]]:
    rows_by_backlog: dict[str, list[dict[str, Any]]] = {
        definition["backlog_id"]: [] for definition in PROOF_BACKLOG_DEFINITIONS
    }
    for row in rows:
        for backlog_id in _proof_backlog_ids(row):
            rows_by_backlog.setdefault(backlog_id, []).append(row)
    backlogs: list[dict[str, Any]] = []
    for definition in PROOF_BACKLOG_DEFINITIONS:
        backlog_rows = sorted(
            rows_by_backlog.get(definition["backlog_id"], []),
            key=lambda row: (
                -int(row.get("candidate_path_signal_count") or 0),
                str(row.get("repo_id") or ""),
            ),
        )
        shown = backlog_rows[:per_backlog_repo_limit]
        backlogs.append(
            {
                **definition,
                "repo_count": len(backlog_rows),
                "reported_repo_count": len(shown),
                "omitted_repo_count": max(0, len(backlog_rows) - len(shown)),
                "candidate_path_signal_summary": _merge_candidate_signal_summaries(
                    backlog_rows
                ),
                "repos": [_repo_wave_ref(row) for row in shown],
                "review_status": "planning_only",
            }
        )
    return backlogs


def build_exception_backfill_wave_plan(
    readiness_report: dict[str, Any],
    *,
    per_wave_repo_limit: int = 25,
) -> dict[str, Any]:
    rows = [
        row
        for row in readiness_report.get("repos", [])
        if isinstance(row, dict)
    ]
    per_wave_repo_limit = max(1, per_wave_repo_limit)
    rows_by_wave: dict[str, list[dict[str, Any]]] = {wave["wave_id"]: [] for wave in BACKFILL_WAVE_DEFINITIONS}
    for row in rows:
        rows_by_wave.setdefault(_primary_backfill_wave(row), []).append(row)
    waves: list[dict[str, Any]] = []
    for order, definition in enumerate(BACKFILL_WAVE_DEFINITIONS, start=1):
        wave_rows = sorted(
            rows_by_wave.get(definition["wave_id"], []),
            key=lambda row: (
                -int(row.get("candidate_path_signal_count") or 0),
                str(row.get("repo_id") or ""),
            ),
        )
        shown = wave_rows[:per_wave_repo_limit]
        wave_summary = _merge_candidate_signal_summaries(wave_rows)
        waves.append(
            {
                **definition,
                "sequence_order": order,
                "repo_count": len(wave_rows),
                "reported_repo_count": len(shown),
                "omitted_repo_count": max(0, len(wave_rows) - len(shown)),
                "candidate_path_signal_summary": wave_summary,
                "repos": [_repo_wave_ref(row) for row in shown],
                "review_status": "planning_only",
            }
        )
    current_wave_id = next(
        (wave["wave_id"] for wave in waves if wave["repo_count"]),
        "watch_or_no_signal_wave",
    )
    proof_backlogs = _build_proof_backlogs(
        rows,
        per_backlog_repo_limit=per_wave_repo_limit,
    )
    return {
        "generated_at": utc_now(),
        "report_id": "dad:exception-backfill-wave-plan",
        "source_report_id": readiness_report.get("report_id"),
        "repo_count": len(rows),
        "per_wave_repo_limit": per_wave_repo_limit,
        "current_wave_id": current_wave_id,
        "wave_order": [wave["wave_id"] for wave in waves],
        "readiness_counts": readiness_report.get("readiness_counts", {}),
        "status_counts": readiness_report.get("status_counts", {}),
        "capture_surface_action_counts": readiness_report.get(
            "capture_surface_action_counts",
            {},
        ),
        "candidate_path_signal_summary": readiness_report.get(
            "candidate_path_signal_summary",
            {},
        ),
        "proof_backlogs": proof_backlogs,
        "input_hashes": readiness_report.get("input_hashes", {}),
        "methodology_ref": readiness_report.get("methodology_ref"),
        "methodology_hash": readiness_report.get("methodology_hash"),
        "waves": waves,
        "authority_boundary": (
            "Backfill wave planning is central planning evidence only. It does "
            "not approve backfill, mutate target repos, promote learning, or "
            "prove that path-name signals are real exceptions."
        ),
    }


def _backfill_wave_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Exception Backfill Wave Plan",
        "",
        f"- Generated: {plan['generated_at']}",
        f"- Repos planned: {plan['repo_count']}",
        f"- Current wave: `{plan['current_wave_id']}`",
        f"- Methodology hash: `{plan.get('methodology_hash', '')}`",
        "",
        "Boundary: central planning evidence only. This report does not approve "
        "or run historical backfill.",
        "",
        "## Wave Order",
        "",
    ]
    lines.extend(f"- `{wave_id}`" for wave_id in plan["wave_order"])
    proof_backlogs = plan.get("proof_backlogs", [])
    if proof_backlogs:
        lines.extend(["", "## Proof Backlogs", ""])
        lines.append(
            "These backlogs are cross-cutting proof requirements. A repo can appear "
            "here even when its primary wave is protected, policy-blocked, or waiting."
        )
        for backlog in proof_backlogs:
            lines.extend(
                [
                    "",
                    f"### {backlog['label']}",
                    "",
                    f"- Backlog id: `{backlog['backlog_id']}`",
                    f"- Repo count: **{backlog['repo_count']}**",
                    f"- Candidate path signals: **{backlog['candidate_path_signal_summary']['total']}**",
                    f"- Reason: {backlog['reason']}",
                ]
            )
            if backlog["repos"]:
                lines.append("- Repos: " + ", ".join(f"`{repo['repo_id']}`" for repo in backlog["repos"]))
    for wave in plan["waves"]:
        lines.extend(
            [
                "",
                f"## {wave['sequence_order']}. {wave['label']}",
                "",
                f"- Wave id: `{wave['wave_id']}`",
                f"- Repo count: **{wave['repo_count']}**",
                f"- Candidate path signals: **{wave['candidate_path_signal_summary']['total']}**",
                f"- Human gate: {wave['human_gate']}",
                f"- Danger if misapplied: {wave['danger_if_misapplied']}",
                f"- Generated next step: {wave['generated_next_step']}",
            ]
        )
        if wave["candidate_path_signal_summary"].get("omitted_signal_count_unknown"):
            lines.append(
                "- Count scope: bounded first-N sample; rerun before treating "
                "counts as complete."
            )
        if wave["proof_to_advance"]:
            lines.extend(["", "Proof to advance:"])
            lines.extend(f"- {item}" for item in wave["proof_to_advance"])
        if wave["repos"]:
            lines.extend(["", "Repos in this wave:"])
            for repo in wave["repos"]:
                lines.append(
                    "- `"
                    + str(repo["repo_id"])
                    + "` "
                    + f"signals={repo['candidate_path_signal_count']} "
                    + f"readiness=`{repo['backfill_readiness']}` "
                    + f"surface=`{repo['capture_surface_action']}`"
                )
    return "\n".join(lines) + "\n"


def write_exception_backfill_wave_plan(
    hub_root: Path,
    repos: list[Path],
    *,
    repo_policies: list[Any] | None = None,
    output: Path | None = None,
    candidate_limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
    per_wave_repo_limit: int = 25,
) -> dict[str, Any]:
    plan_output = output or BACKFILL_WAVE_PLAN_JSON
    readiness_output = plan_output.with_name(plan_output.stem + "_readiness.json")
    readiness_report = write_exception_backfill_readiness(
        hub_root,
        repos,
        repo_policies=repo_policies,
        output=readiness_output,
        candidate_limit=candidate_limit,
        max_scanned_files=max_scanned_files,
    )
    plan = build_exception_backfill_wave_plan(
        readiness_report,
        per_wave_repo_limit=per_wave_repo_limit,
    )
    output_path = _capture_output_path(hub_root, output, BACKFILL_WAVE_PLAN_JSON)
    write_json(output_path, plan)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, BACKFILL_WAVE_PLAN_MD)
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_backfill_wave_plan_markdown(plan), encoding="utf-8")
    return plan


def write_exception_backfill_readiness(
    hub_root: Path,
    repos: list[Path],
    *,
    repo_policies: list[Any] | None = None,
    output: Path | None = None,
    candidate_limit: int | None = 50,
    max_scanned_files: int | None = 50_000,
) -> dict[str, Any]:
    """Write a compact central plan for safe historical exception backfill.

    This is intentionally read-only with respect to target repos. It summarizes
    what the observed audit saw and which reviewed policy gates still block a
    metadata-only backfill wave.
    """
    registry = load_capture_pattern_registry(hub_root)
    audited_rows = [
        audit_observed_capture_repo(
            hub_root,
            repo,
            registry,
            repo_policies=repo_policies,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
        )
        for repo in repos
    ]
    rows: list[dict[str, Any]] = []
    for audited in audited_rows:
        readiness, blocked_reasons, next_actions = _backfill_readiness_action(audited)
        repo = audited["repo"]
        outboxes = audited["outboxes"]
        rows.append(
            {
                "repo_id": repo["repo_id"],
                "repo_alias": repo["repo_alias"],
                "path_hint": repo["path_hint"],
                "path_hash": repo["path_hash"],
                "visibility": repo["visibility"],
                "public_facing": repo["public_facing"],
                "reviewed_policy": repo["reviewed_policy"],
                "exceptions_enabled": repo["exceptions_enabled"],
                "collect_allowed": repo["collect_allowed"],
                "capture_audit_allowed": repo["capture_audit_allowed"],
                "backfill_allowed": repo["backfill_allowed"],
                "write_protected": repo["write_protected"],
                "candidate_path_signal_count": audited["candidate_path_signal_count"],
                "candidate_path_scan": audited["candidate_path_scan"],
                "candidate_path_signal_summary": audited["candidate_path_signal_summary"],
                "status_flags": audited["status_flags"],
                "capture_surface_action": _capture_surface_action(audited),
                "backfill_readiness": readiness,
                "blocked_reasons": blocked_reasons,
                "next_actions": sorted(set(next_actions)),
                "packet_counts": {
                    "mail": outboxes["mail_outbox"]["record_count"],
                    "exception": outboxes["exception_outbox"]["record_count"],
                    "fix_outcome": outboxes["fix_outcomes"]["record_count"],
                },
            }
        )
    readiness_counts = Counter(str(row["backfill_readiness"]) for row in rows)
    capture_surface_counts = Counter(str(row["capture_surface_action"]) for row in rows)
    status_counts = Counter(flag for audited in audited_rows for flag in audited["status_flags"])
    signal_summary = _candidate_signal_summary_from_rows(audited_rows)
    report = {
        "generated_at": utc_now(),
        "report_id": "dad:exception-backfill-readiness",
        "repo_count": len(rows),
        "registry_ref": CAPTURE_PATTERN_REGISTRY.as_posix(),
        "methodology_ref": CAPTURE_ROUTE_METHODOLOGY_REF,
        "methodology_hash": capture_route_methodology_hash(hub_root),
        "input_hashes": _observed_audit_input_hashes(hub_root),
        "candidate_limit": _normalize_candidate_limit(candidate_limit),
        "max_scanned_files": (
            max_scanned_files
            if max_scanned_files is not None and max_scanned_files > 0
            else None
        ),
        "readiness_counts": dict(sorted(readiness_counts.items())),
        "capture_surface_action_counts": dict(sorted(capture_surface_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "candidate_path_signal_summary": signal_summary,
        "repos": rows,
        "authority_boundary": (
            "Backfill readiness is central planning evidence only. It does not run "
            "backfill, approve a repo, write target repos, promote candidate events, "
            "or prove path-signal truth."
        ),
    }
    output_path = _capture_output_path(hub_root, output, BACKFILL_READINESS_JSON)
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, BACKFILL_READINESS_MD)
    )
    lines = [
        "# Exception Backfill Readiness",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Repos evaluated: {report['repo_count']}",
        f"- Candidate limit per repo: `{_candidate_limit_label(candidate_limit)}`",
        "- Max scanned files per repo: `"
        + str(report["max_scanned_files"] if report["max_scanned_files"] is not None else "unbounded")
        + "`",
        f"- Methodology hash: `{report['methodology_hash']}`",
        "",
        "Boundary: central planning evidence only. This report never approves or runs "
        "historical backfill.",
        "",
        "## Readiness Counts",
        "",
    ]
    lines.extend(f"- `{key}`: {count}" for key, count in report["readiness_counts"].items())
    if signal_summary.get("omitted_signal_count_unknown"):
        lines.extend(
            [
                "",
                "Warning: candidate path counts are bounded first-N samples because "
                f"{signal_summary['truncated_repo_count']} repo scan(s) hit the "
                "candidate limit. Treat these counts as review-routing hints, not "
                "complete distributions.",
            ]
        )
    event_type_counts = signal_summary.get("by_suggested_event_type", {})
    if event_type_counts:
        heading = (
            "## Candidate Suggested Event Types (Bounded Sample)"
            if signal_summary.get("omitted_signal_count_unknown")
            else "## Candidate Suggested Event Types"
        )
        lines.extend(["", heading, ""])
        lines.extend(
            f"- `{event_type}`: {count}"
            for event_type, count in sorted(event_type_counts.items())
        )
    source_rule_counts = signal_summary.get("by_source_rule_id", {})
    if source_rule_counts:
        heading = (
            "## Candidate Source Rules (Bounded Sample)"
            if signal_summary.get("omitted_signal_count_unknown")
            else "## Candidate Source Rules"
        )
        lines.extend(["", heading, ""])
        lines.extend(
            f"- `{rule_id}`: {count}" for rule_id, count in sorted(source_rule_counts.items())
        )
    lines.extend(["", "## Repo Matrix", ""])
    lines.append(
        "| Repo | Readiness | Capture Surface | Signals | Flags | Next Actions |"
    )
    lines.append("| --- | --- | --- | ---: | --- | --- |")
    for row in rows:
        flags = ", ".join(f"`{flag}`" for flag in row["status_flags"]) or "-"
        actions = "<br>".join(row["next_actions"]) or "-"
        lines.append(
            "| "
            + f"`{row['repo_id']}` | `{row['backfill_readiness']}` | "
            + f"`{row['capture_surface_action']}` | {row['candidate_path_signal_count']} | "
            + f"{flags} | {actions} |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _input_hashes(hub_root: Path, scenarios_path: Path) -> dict[str, str]:
    refs = [
        CAPTURE_PATTERN_REGISTRY,
        Path("registry") / "exception-event-type-registry.json",
        Path("src") / "digital_asset_directory" / "exception_capture.py",
        Path("src") / "digital_asset_directory" / "exceptions_lake.py",
        Path("schemas") / "exception-capture-pattern-registry.schema.json",
        Path("schemas") / "exception-capture-scenarios.schema.json",
    ]
    scenario_ref = Path(safe_relative(scenarios_path, hub_root))
    if scenario_ref.as_posix() != scenarios_path.name or (hub_root / scenario_ref).exists():
        refs.append(scenario_ref)
    hashes: dict[str, str] = {}
    for ref in refs:
        path = hub_root / ref
        if path.exists() and path.is_file():
            hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}"
    return hashes


def _taxonomy_coverage_input_hashes(hub_root: Path, scenarios_path: Path) -> dict[str, str]:
    refs = [
        Path("registry") / "exception-event-type-registry.json",
        CAPTURE_PATTERN_REGISTRY,
        Path("src") / "digital_asset_directory" / "exception_capture.py",
        Path("src") / "digital_asset_directory" / "exceptions_lake.py",
    ]
    scenario_ref = Path(safe_relative(scenarios_path, hub_root))
    if scenario_ref.as_posix() != scenarios_path.name or (hub_root / scenario_ref).exists():
        refs.append(scenario_ref)
    hashes: dict[str, str] = {}
    for ref in refs:
        path = hub_root / ref
        if path.exists() and path.is_file():
            hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}"
    return hashes


def _event_route_status(
    *,
    capture_rule_ids: list[str],
    backfill_rule_ids: list[str],
    direct_record_contracts: list[str],
    scenario_ids: list[str],
) -> str:
    if capture_rule_ids and scenario_ids:
        return "capture_rule_with_synthetic_case"
    if capture_rule_ids:
        return "capture_rule_missing_synthetic_case"
    if backfill_rule_ids:
        return "backfill_path_signal"
    if direct_record_contracts:
        return "direct_record_contract_only"
    return "unrouted"


def _phase6_gate_row(
    gate_id: str,
    *,
    passed: bool,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_id": f"machine-evidence:{gate_id}",
        "evidence_scope": PHASE6_MACHINE_EVIDENCE_SCOPE,
        "supports_human_gate_id": gate_id,
        "machine_status": "passed" if passed else "failed",
        "human_review_required": True,
        "human_gate_satisfied": False,
        "evidence": evidence,
    }


def _phase6_machine_evidence_key(gate_id: str) -> str:
    return f"machine-evidence:{gate_id}"


def _case_payload_issue_set(case: dict[str, Any]) -> set[str]:
    issues = {str(issue) for issue in case.get("payload_screen_issues", []) if issue}
    blocked_reason = str((case.get("actual") or {}).get("blocked_reason") or "")
    if blocked_reason.startswith("payload_screen:"):
        issues.update(
            item.strip()
            for item in blocked_reason.removeprefix("payload_screen:").split(",")
            if item.strip()
        )
    return issues


def _capture_phase6_machine_gate_evidence(
    *,
    cases: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    observed_failed: list[dict[str, Any]],
    missing_families: list[str],
    missing_reviewed_rule_ids: list[str],
    undeclared_matched_rule_ids: list[str],
    unknown_declared_rule_ids: list[str],
    by_family: Counter[str],
    required_families: list[str],
    covered_rule_ids: list[str],
    reviewed_rule_ids: list[str],
) -> dict[str, Any]:
    case_by_id = {str(case.get("scenario_id")): case for case in cases}
    update_cases = [case for case in cases if case.get("update_required")]
    update_failed = [case for case in update_cases if not case.get("passed")]
    update_families = sorted(
        {str(case.get("pattern_family")) for case in update_cases if case.get("passed")}
    )
    missing_update_families = sorted(
        PHASE6_REQUIRED_UPDATE_FAMILIES - set(update_families)
    )
    update_vectors = sorted(
        {
            str(vector)
            for case in update_cases
            if case.get("passed")
            for vector in case.get("phase6_update_vectors", [])
            if vector
        }
    )
    missing_update_vectors = sorted(PHASE6_REQUIRED_UPDATE_VECTORS - set(update_vectors))
    passing_by_family = Counter(
        str(case.get("pattern_family")) for case in cases if case.get("passed")
    )
    missing_passing_families = sorted(set(required_families) - set(passing_by_family))
    negative_controls = sorted(
        {
            str(control)
            for case in cases
            for control in case.get("negative_controls", [])
            if control
        }
    )
    missing_negative_controls = sorted(
        PHASE6_REQUIRED_NEGATIVE_CONTROLS - set(negative_controls)
    )
    blocked_cases = [
        case
        for case in cases
        if case.get("passed")
        and (case.get("expected") or {}).get("blocked")
        and (case.get("actual") or {}).get("blocked")
        and str((case.get("actual") or {}).get("blocked_reason") or "").startswith(
            ("payload_screen:", "global_block_signal:")
        )
    ]
    blocked_negative_control_coverage: dict[str, list[dict[str, Any]]] = {
        control: [] for control in sorted(PHASE6_REQUIRED_NEGATIVE_CONTROLS)
    }
    for case in blocked_cases:
        issue_set = _case_payload_issue_set(case)
        for control in case.get("negative_controls", []):
            control = str(control)
            expected_issues = PHASE6_NEGATIVE_CONTROL_ISSUES.get(control, set())
            matched_issues = sorted(issue_set & expected_issues)
            if matched_issues:
                blocked_negative_control_coverage.setdefault(control, []).append(
                    {
                        "scenario_id": str(case.get("scenario_id")),
                        "matched_issues": matched_issues,
                    }
                )
    missing_negative_control_blocks = sorted(
        control
        for control in PHASE6_REQUIRED_NEGATIVE_CONTROLS
        if not blocked_negative_control_coverage.get(control)
    )
    lawfirm_case = case_by_id.get(PHASE6_LAWFIRM_MISSED_CAPTURE_SCENARIO_ID)
    lawfirm_observed = (
        lawfirm_case.get("observed")
        if isinstance(lawfirm_case, dict) and isinstance(lawfirm_case.get("observed"), dict)
        else {}
    )
    capture_clean = (
        not failed
        and not observed_failed
        and not missing_families
        and not missing_reviewed_rule_ids
        and not undeclared_matched_rule_ids
        and not unknown_declared_rule_ids
        and len(covered_rule_ids) == len(reviewed_rule_ids)
    )
    lawfirm_passed = bool(
        lawfirm_case
        and lawfirm_case.get("passed")
        and lawfirm_case.get("update_required")
        and lawfirm_observed.get("passed")
    )
    pattern_update_passed = bool(
        update_cases
        and not update_failed
        and not missing_update_families
        and not missing_update_vectors
    )
    all_family_passed = not missing_families and not missing_passing_families
    sensitive_payload_passed = (
        bool(blocked_cases)
        and not missing_negative_controls
        and not missing_negative_control_blocks
    )
    return {
        "authority_boundary": PHASE6_GATE_BOUNDARY,
        "gates": {
            _phase6_machine_evidence_key(
                "phase-6-capture-completeness-harness-reviewed"
            ): _phase6_gate_row(
                "phase-6-capture-completeness-harness-reviewed",
                passed=capture_clean,
                evidence={
                    "case_count": len(cases),
                    "failed_scenario_ids": [
                        str(case.get("scenario_id")) for case in failed
                    ],
                    "observed_failed_scenario_ids": [
                        str(case.get("scenario_id")) for case in observed_failed
                    ],
                    "covered_reviewed_rule_count": len(covered_rule_ids),
                    "reviewed_rule_count": len(reviewed_rule_ids),
                    "missing_reviewed_rule_ids": missing_reviewed_rule_ids,
                    "undeclared_matched_rule_ids": undeclared_matched_rule_ids,
                    "unknown_declared_rule_ids": unknown_declared_rule_ids,
                },
            ),
            _phase6_machine_evidence_key(
                "phase-6-lawfirm-intake-missed-capture-regression"
            ): _phase6_gate_row(
                "phase-6-lawfirm-intake-missed-capture-regression",
                passed=lawfirm_passed,
                evidence={
                    "scenario_id": PHASE6_LAWFIRM_MISSED_CAPTURE_SCENARIO_ID,
                    "scenario_present": bool(lawfirm_case),
                    "scenario_passed": bool(lawfirm_case and lawfirm_case.get("passed")),
                    "update_required": bool(
                        lawfirm_case and lawfirm_case.get("update_required")
                    ),
                    "observed_outbox_compared": bool(lawfirm_observed),
                    "observed_passed": bool(lawfirm_observed.get("passed")),
                },
            ),
            _phase6_machine_evidence_key(
                "phase-6-pattern-update-simulation-reviewed"
            ): _phase6_gate_row(
                "phase-6-pattern-update-simulation-reviewed",
                passed=pattern_update_passed,
                evidence={
                    "required_update_pattern_families": sorted(
                        PHASE6_REQUIRED_UPDATE_FAMILIES
                    ),
                    "covered_update_pattern_families": update_families,
                    "missing_update_pattern_families": missing_update_families,
                    "required_update_vectors": sorted(PHASE6_REQUIRED_UPDATE_VECTORS),
                    "covered_update_vectors": update_vectors,
                    "missing_update_vectors": missing_update_vectors,
                    "update_required_scenario_ids": [
                        str(case.get("scenario_id")) for case in update_cases
                    ],
                    "failed_update_required_scenario_ids": [
                        str(case.get("scenario_id")) for case in update_failed
                    ],
                },
            ),
            _phase6_machine_evidence_key(
                "phase-6-all-asset-pattern-coverage-reviewed"
            ): _phase6_gate_row(
                "phase-6-all-asset-pattern-coverage-reviewed",
                passed=all_family_passed,
                evidence={
                    "required_pattern_family_count": len(required_families),
                    "required_pattern_families": required_families,
                    "covered_pattern_families": dict(sorted(by_family.items())),
                    "passing_pattern_families": dict(sorted(passing_by_family.items())),
                    "missing_required_pattern_families": missing_families,
                    "missing_passing_required_pattern_families": missing_passing_families,
                },
            ),
            _phase6_machine_evidence_key(
                "phase-6-sensitive-payload-negative-tests-reviewed"
            ): _phase6_gate_row(
                "phase-6-sensitive-payload-negative-tests-reviewed",
                passed=sensitive_payload_passed,
                evidence={
                    "required_negative_controls": sorted(PHASE6_REQUIRED_NEGATIVE_CONTROLS),
                    "covered_negative_controls": negative_controls,
                    "missing_negative_controls": missing_negative_controls,
                    "blocked_negative_control_coverage": blocked_negative_control_coverage,
                    "missing_negative_control_blocks": missing_negative_control_blocks,
                    "blocked_negative_scenario_ids": [
                        str(case.get("scenario_id")) for case in blocked_cases
                    ],
                    "blocked_reasons": sorted(
                        {
                            str((case.get("actual") or {}).get("blocked_reason") or "")
                            for case in blocked_cases
                        }
                    ),
                },
            ),
        },
    }


def _taxonomy_phase6_machine_gate_evidence(
    *,
    reviewed_unrouted: list[str],
    learnable_unrouted: list[str],
    missing_scenarios: list[str],
    unrouted: list[str],
) -> dict[str, Any]:
    passed = (
        not reviewed_unrouted
        and not learnable_unrouted
        and not missing_scenarios
        and not unrouted
    )
    return {
        "authority_boundary": PHASE6_GATE_BOUNDARY,
        "gates": {
            _phase6_machine_evidence_key(
                "phase-6-taxonomy-route-coverage-reviewed"
            ): _phase6_gate_row(
                "phase-6-taxonomy-route-coverage-reviewed",
                passed=passed,
                evidence={
                    "unrouted_event_types": unrouted,
                    "reviewed_unrouted_event_types": reviewed_unrouted,
                    "learnable_unrouted_event_types": learnable_unrouted,
                    "capture_rule_events_missing_synthetic_cases": missing_scenarios,
                },
            )
        },
    }


def _taxonomy_route_review_summaries(
    records: list[dict[str, Any]],
    status_counts: Counter[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    route_kind_counts: Counter[str] = Counter(
        route_kind
        for record in records
        for route_kind in record["route_kinds"]
    )
    category_summary: dict[str, Any] = {}
    high_or_critical_direct_only: list[str] = []
    for category in sorted({record["category"] for record in records}):
        category_records = [
            record for record in records if record["category"] == category
        ]
        category_status_counts: Counter[str] = Counter(
            record["coverage_status"] for record in category_records
        )
        category_route_counts: Counter[str] = Counter(
            route_kind
            for record in category_records
            for route_kind in record["route_kinds"]
        )
        direct_only_event_types = sorted(
            record["event_type"]
            for record in category_records
            if record["coverage_status"] == "direct_record_contract_only"
        )
        backfill_signal_event_types = sorted(
            record["event_type"]
            for record in category_records
            if "backfill_path_signal" in record["route_kinds"]
        )
        capture_rule_event_types = sorted(
            record["event_type"]
            for record in category_records
            if record["capture_rule_ids"]
        )
        learnable_direct_only_event_types = sorted(
            record["event_type"]
            for record in category_records
            if record["coverage_status"] == "direct_record_contract_only"
            and record["learnable"]
        )
        high_or_critical_category_direct_only = sorted(
            record["event_type"]
            for record in category_records
            if record["coverage_status"] == "direct_record_contract_only"
            and record["default_severity"] in {"high", "critical"}
        )
        high_or_critical_direct_only.extend(high_or_critical_category_direct_only)
        category_summary[category] = {
            "event_type_count": len(category_records),
            "event_types": sorted(record["event_type"] for record in category_records),
            "coverage_status_counts": dict(sorted(category_status_counts.items())),
            "route_kind_counts": dict(sorted(category_route_counts.items())),
            "capture_rule_count": len(capture_rule_event_types),
            "backfill_path_signal_count": len(backfill_signal_event_types),
            "direct_record_only_count": len(direct_only_event_types),
            "unrouted_count": sum(1 for record in category_records if record["unrouted"]),
            "capture_rule_event_types": capture_rule_event_types,
            "backfill_path_signal_event_types": backfill_signal_event_types,
            "direct_record_only_event_types": direct_only_event_types,
            "learnable_direct_record_only_event_types": learnable_direct_only_event_types,
            "high_or_critical_direct_record_only_event_types": (
                high_or_critical_category_direct_only
            ),
        }

    categories_without_capture_rules = sorted(
        category
        for category, row in category_summary.items()
        if row["capture_rule_count"] == 0
    )
    categories_without_detector_or_backfill = sorted(
        category
        for category, row in category_summary.items()
        if row["capture_rule_count"] == 0 and row["backfill_path_signal_count"] == 0
    )
    backfill_heavy_categories = sorted(
        category
        for category, row in category_summary.items()
        if row["backfill_path_signal_count"] > row["capture_rule_count"]
    )
    direct_only_by_category = {
        category: row["direct_record_only_event_types"]
        for category, row in category_summary.items()
        if row["direct_record_only_event_types"]
    }
    backfill_signal_by_category = {
        category: row["backfill_path_signal_event_types"]
        for category, row in category_summary.items()
        if row["backfill_path_signal_event_types"]
    }
    review_attention: list[dict[str, Any]] = []
    high_or_critical_direct_only = sorted(high_or_critical_direct_only)
    if high_or_critical_direct_only:
        review_attention.append(
            {
                "attention_id": "high_or_critical_direct_record_only",
                "event_types": high_or_critical_direct_only,
                "why": (
                    "High or critical event types currently rely on intentional "
                    "direct records rather than reviewed automatic capture rules."
                ),
            }
        )
    if categories_without_capture_rules:
        review_attention.append(
            {
                "attention_id": "categories_without_capture_rules",
                "categories": categories_without_capture_rules,
                "why": (
                    "These categories have no reviewed automatic capture rule; "
                    "manual records or backfill signals may still exist."
                ),
            }
        )
    if categories_without_detector_or_backfill:
        review_attention.append(
            {
                "attention_id": "categories_without_detector_or_backfill",
                "categories": categories_without_detector_or_backfill,
                "why": (
                    "These categories have no reviewed capture rule and no "
                    "backfill path-signal route."
                ),
            }
        )
    if backfill_heavy_categories:
        review_attention.append(
            {
                "attention_id": "backfill_path_signal_heavy_categories",
                "categories": backfill_heavy_categories,
                "why": (
                    "Backfill path-signal routes outnumber reviewed capture "
                    "rules in these categories; source review is still required."
                ),
            }
        )

    review_summary = {
        "category_count": len(category_summary),
        "route_kind_counts": dict(sorted(route_kind_counts.items())),
        "coverage_status_counts": dict(sorted(status_counts.items())),
        "categories_without_capture_rules": categories_without_capture_rules,
        "categories_without_detector_or_backfill": categories_without_detector_or_backfill,
        "backfill_path_signal_heavy_categories": backfill_heavy_categories,
        "direct_record_only_event_types_by_category": direct_only_by_category,
        "backfill_path_signal_event_types_by_category": backfill_signal_by_category,
        "high_or_critical_direct_record_only_event_types": high_or_critical_direct_only,
        "review_attention": review_attention,
        "authority_boundary": (
            "Review attention fields are triage aids. They do not fail or pass "
            "the human gate, promote lessons, or prove automatic capture."
        ),
    }
    return category_summary, review_summary


def evaluate_exception_taxonomy_coverage(
    hub_root: Path,
    scenarios_path: Path,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    event_registry = load_event_type_registry(hub_root)
    capture_registry = load_capture_pattern_registry(hub_root)
    scenarios = load_capture_scenarios(scenarios_path)
    capture_rules_by_event: dict[str, list[str]] = {}
    for rule in capture_registry.get("rules", []):
        event_type = str((rule.get("emit") or {}).get("exception_event_type") or "")
        rule_id = str(rule.get("rule_id") or "")
        if event_type and rule_id and rule.get("review_status") == "reviewed":
            capture_rules_by_event.setdefault(event_type, []).append(rule_id)
    backfill_rules_by_event: dict[str, list[str]] = {}
    for rule in backfill_classifier_rules(hub_root):
        event_type = str(rule.get("event_type") or "")
        rule_id = str(rule.get("rule_id") or "")
        if event_type and rule_id:
            backfill_rules_by_event.setdefault(event_type, []).append(rule_id)
    scenarios_by_event: dict[str, list[str]] = {}
    for case in scenarios.get("cases", []):
        scenario_id = str(case.get("scenario_id") or "")
        for event_type in (case.get("expected") or {}).get("event_types", []):
            scenarios_by_event.setdefault(str(event_type), []).append(scenario_id)

    records: list[dict[str, Any]] = []
    for event in event_registry.get("event_types", []):
        if not isinstance(event, dict) or not event.get("event_type"):
            continue
        event_type = str(event["event_type"])
        capture_rule_ids = sorted(capture_rules_by_event.get(event_type, []))
        backfill_rule_ids = sorted(backfill_rules_by_event.get(event_type, []))
        scenario_ids = sorted(scenarios_by_event.get(event_type, []))
        direct_record_contracts = sorted(str(item) for item in event.get("capture_contracts", []))
        route_kinds = []
        if direct_record_contracts:
            route_kinds.append("direct_record_contract")
        if capture_rule_ids:
            route_kinds.append("capture_rule")
        if backfill_rule_ids:
            route_kinds.append("backfill_path_signal")
        route_bundle_required = bool(
            capture_rule_ids
            or (
                backfill_rule_ids
                and str(event.get("review_status") or "") == "reviewed"
                and bool(event.get("learnable", False))
            )
        )
        status = _event_route_status(
            capture_rule_ids=capture_rule_ids,
            backfill_rule_ids=backfill_rule_ids,
            direct_record_contracts=direct_record_contracts,
            scenario_ids=scenario_ids,
        )
        records.append(
            {
                "event_type": event_type,
                "category": str(event.get("category") or "unknown"),
                "review_status": str(event.get("review_status") or "unknown"),
                "learnable": bool(event.get("learnable", False)),
                "default_severity": str(event.get("default_severity") or ""),
                "direct_record_contracts": direct_record_contracts,
                "capture_rule_ids": capture_rule_ids,
                "backfill_rule_ids": backfill_rule_ids,
                "synthetic_scenario_ids": scenario_ids,
                "route_kinds": route_kinds,
                "coverage_status": status,
                "route_bundle_required": route_bundle_required,
                "missing_synthetic_case": bool(route_bundle_required and not scenario_ids),
                "manual_only": status == "direct_record_contract_only",
                "unrouted": status == "unrouted",
            }
        )

    status_counts = Counter(record["coverage_status"] for record in records)
    manual_only = sorted(record["event_type"] for record in records if record["manual_only"])
    unrouted = sorted(record["event_type"] for record in records if record["unrouted"])
    missing_scenarios = sorted(
        record["event_type"] for record in records if record["missing_synthetic_case"]
    )
    reviewed_unrouted = sorted(
        record["event_type"]
        for record in records
        if record["unrouted"] and record["review_status"] == "reviewed"
    )
    learnable_unrouted = sorted(
        record["event_type"]
        for record in records
        if record["unrouted"] and record["learnable"]
    )
    automated_route_count = sum(
        1
        for record in records
        if record["capture_rule_ids"] or record["backfill_rule_ids"]
    )
    category_route_summary, taxonomy_review_summary = _taxonomy_route_review_summaries(
        records,
        status_counts,
    )
    report = {
        "generated_at": utc_now(),
        "event_registry_ref": "registry/exception-event-type-registry.json",
        "capture_registry_ref": CAPTURE_PATTERN_REGISTRY.as_posix(),
        "methodology_ref": CAPTURE_ROUTE_METHODOLOGY_REF,
        "methodology_hash": capture_route_methodology_hash(hub_root),
        "scenario_path": _report_path_ref(scenarios_path, hub_root),
        "input_hashes": _taxonomy_coverage_input_hashes(hub_root, scenarios_path),
        "event_type_count": len(records),
        "automated_route_count": automated_route_count,
        "manual_only_count": len(manual_only),
        "unrouted_count": len(unrouted),
        "missing_synthetic_case_count": len(missing_scenarios),
        "coverage_status_counts": dict(sorted(status_counts.items())),
        "route_kind_counts": taxonomy_review_summary["route_kind_counts"],
        "taxonomy_review_summary": taxonomy_review_summary,
        "category_route_summary": category_route_summary,
        "manual_only_event_types": manual_only,
        "unrouted_event_types": unrouted,
        "reviewed_unrouted_event_types": reviewed_unrouted,
        "learnable_unrouted_event_types": learnable_unrouted,
        "capture_rule_events_missing_synthetic_cases": missing_scenarios,
        "routed_events_missing_synthetic_cases": missing_scenarios,
        "phase6_machine_gate_evidence": _taxonomy_phase6_machine_gate_evidence(
            reviewed_unrouted=reviewed_unrouted,
            learnable_unrouted=learnable_unrouted,
            missing_scenarios=missing_scenarios,
            unrouted=unrouted,
        ),
        "events": records,
        "authority_boundary": (
            "Taxonomy coverage shows available capture routes. A direct record "
            "contract means an agent can intentionally emit safe metadata; it is "
            "not proof of deterministic auto-detection. Backfill path signals are "
            "candidate-only and do not prove source truth."
        ),
    }
    output_path = _capture_output_path(hub_root, output, TAXONOMY_COVERAGE_REPORT_JSON)
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, TAXONOMY_COVERAGE_REPORT_MD)
    )
    lines = [
        "# Exception Taxonomy Coverage",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Event types: {report['event_type_count']}",
        f"- Event types with detector/backfill routes: {report['automated_route_count']}",
        f"- Direct-record-only event types: {report['manual_only_count']}",
        f"- Unrouted event types: {report['unrouted_count']}",
        f"- Routed event types missing synthetic cases: {report['missing_synthetic_case_count']}",
        f"- Methodology hash: `{report['methodology_hash']}`",
        "",
        "Boundary: direct-record coverage is a safe manual emission route, not an "
        "automatic detector. Backfill routes are path-signal candidates only.",
        "",
        "## Phase 6 Machine Gate Evidence",
        "",
    ]
    for gate in report["phase6_machine_gate_evidence"]["gates"].values():
        lines.append(
            f"- `{gate['supports_human_gate_id']}`: `{gate['machine_status']}` "
            "(human review still required)"
        )
    lines.extend(
        [
            "",
            "## Coverage Status Counts",
            "",
        ]
    )
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Route Kind Counts", ""])
    for route_kind, count in taxonomy_review_summary["route_kind_counts"].items():
        lines.append(f"- `{route_kind}`: {count}")
    if taxonomy_review_summary["review_attention"]:
        lines.extend(["", "## Review Attention", ""])
        for item in taxonomy_review_summary["review_attention"]:
            label = item["attention_id"].replace("_", " ")
            values = item.get("event_types") or item.get("categories") or []
            lines.append(f"### {label.title()}")
            lines.append("")
            lines.append(item["why"])
            lines.append("")
            for value in values:
                lines.append(f"- `{value}`")
            lines.append("")
    lines.extend(["", "## Category Route Summary", ""])
    lines.append(
        "| Category | Events | Capture Rules | Backfill Signals | Direct Only | Unrouted |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for category, row in category_route_summary.items():
        lines.append(
            f"| `{category}` | {row['event_type_count']} | {row['capture_rule_count']} | "
            f"{row['backfill_path_signal_count']} | {row['direct_record_only_count']} | "
            f"{row['unrouted_count']} |"
        )
    if manual_only:
        lines.extend(["", "## Direct Record Only", ""])
        lines.extend(f"- `{event_type}`" for event_type in manual_only)
    if missing_scenarios:
        lines.extend(["", "## Capture Rules Missing Synthetic Cases", ""])
        lines.extend(f"- `{event_type}`" for event_type in missing_scenarios)
    if unrouted:
        lines.extend(["", "## Unrouted Event Types", ""])
        lines.extend(f"- `{event_type}`" for event_type in unrouted)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def evaluate_capture_scenarios(
    hub_root: Path,
    scenarios_path: Path,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    registry = load_capture_route_registry(hub_root)
    scenarios = load_capture_scenarios(scenarios_path)
    cases = [
        evaluate_capture_case(case, registry, scenario_base=scenarios_path.parent)
        for case in scenarios.get("cases", [])
    ]
    required_families = sorted(str(item) for item in scenarios.get("required_pattern_families", []))
    by_family = Counter(case["pattern_family"] for case in cases)
    missing_families = sorted(set(required_families) - set(by_family))
    reviewed_rule_ids = _reviewed_rule_ids(registry)
    reviewed_rule_id_set = set(reviewed_rule_ids)
    covered_rule_ids = sorted(
        {
            str(rule_id)
            for case in cases
            if case.get("passed")
            for rule_id in case.get("covered_rule_ids", [])
        }
    )
    missing_reviewed_rule_ids = sorted(reviewed_rule_id_set - set(covered_rule_ids))
    undeclared_matched_rule_ids = sorted(
        {
            str(rule_id)
            for case in cases
            for rule_id in case.get("matched_rules", [])
            if rule_id not in set(case.get("covered_rule_ids", []))
        }
    )
    unknown_declared_rule_ids = sorted(
        {
            str(rule_id)
            for case in cases
            for rule_id in case.get("covered_rule_ids", [])
            if rule_id not in reviewed_rule_id_set
        }
    )
    failed = [case for case in cases if not case["passed"]]
    observed_cases = [case for case in cases if "observed" in case]
    observed_failed = [case for case in observed_cases if not case["observed"]["passed"]]
    input_hashes = _input_hashes(hub_root, scenarios_path)
    phase6_machine_gate_evidence = _capture_phase6_machine_gate_evidence(
        cases=cases,
        failed=failed,
        observed_failed=observed_failed,
        missing_families=missing_families,
        missing_reviewed_rule_ids=missing_reviewed_rule_ids,
        undeclared_matched_rule_ids=undeclared_matched_rule_ids,
        unknown_declared_rule_ids=unknown_declared_rule_ids,
        by_family=by_family,
        required_families=required_families,
        covered_rule_ids=covered_rule_ids,
        reviewed_rule_ids=reviewed_rule_ids,
    )
    report = {
        "generated_at": utc_now(),
        "scenario_set_id": scenarios.get("scenario_set_id"),
        "scenario_path": _report_path_ref(scenarios_path, hub_root),
        "registry_ref": CAPTURE_PATTERN_REGISTRY.as_posix(),
        "methodology_ref": CAPTURE_ROUTE_METHODOLOGY_REF,
        "methodology_hash": capture_route_methodology_hash(hub_root),
        "input_hashes": input_hashes,
        "capture_surface_version": registry.get("capture_surface_version"),
        "case_count": len(cases),
        "passed_count": len(cases) - len(failed),
        "failed_count": len(failed),
        "observed_case_count": len(observed_cases),
        "observed_failed_count": len(observed_failed),
        "missing_required_pattern_families": missing_families,
        "reviewed_rule_count": len(reviewed_rule_ids),
        "covered_reviewed_rule_count": len(covered_rule_ids),
        "covered_reviewed_rule_ids": covered_rule_ids,
        "missing_reviewed_rule_ids": missing_reviewed_rule_ids,
        "undeclared_matched_rule_ids": undeclared_matched_rule_ids,
        "unknown_declared_rule_ids": unknown_declared_rule_ids,
        "by_pattern_family": dict(sorted(by_family.items())),
        "phase6_machine_gate_evidence": phase6_machine_gate_evidence,
        "cases": cases,
        "authority_boundary": (
            "Capture-completeness output is a deterministic harness report. Synthetic "
            "cases prove rule coverage only. Observed cases compare expected packets to "
            "actual JSONL outboxes, but still do not prove all real repos are complete."
        ),
    }
    output_path = _capture_output_path(hub_root, output, CAPTURE_REPORT_JSON)
    write_json(output_path, report)
    md_path = (
        output_path.with_suffix(".md")
        if output
        else _capture_output_path(hub_root, None, CAPTURE_REPORT_MD)
    )
    lines = [
        "# Exception Capture Completeness Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Scenario set: `{report['scenario_set_id']}`",
        f"- Cases: {report['case_count']}",
        f"- Passed: {report['passed_count']}",
        f"- Failed: {report['failed_count']}",
        f"- Reviewed rules covered: {report['covered_reviewed_rule_count']} / {report['reviewed_rule_count']}",
        f"- Observed emission cases: {report['observed_case_count']}",
        f"- Observed emission failures: {report['observed_failed_count']}",
        f"- Capture surface version: `{report['capture_surface_version']}`",
        f"- Methodology hash: `{report['methodology_hash']}`",
        "",
        "Boundary: synthetic cases prove rule coverage only. Observed cases compare "
        "expected packets to actual JSONL outboxes, but this report is not proof that "
        "all real repos are complete or public-safe.",
        "",
        "## Phase 6 Machine Gate Evidence",
        "",
    ]
    for gate in report["phase6_machine_gate_evidence"]["gates"].values():
        lines.append(
            f"- `{gate['supports_human_gate_id']}`: `{gate['machine_status']}` "
            "(human review still required)"
        )
    lines.extend(
        [
            "",
            "## Pattern Families",
            "",
        ]
    )
    for family, count in sorted(by_family.items()):
        lines.append(f"- `{family}`: {count}")
    if missing_families:
        lines.extend(["", "## Missing Required Families", ""])
        lines.extend(f"- `{family}`" for family in missing_families)
    if missing_reviewed_rule_ids:
        lines.extend(["", "## Missing Reviewed Rule Coverage", ""])
        lines.extend(f"- `{rule_id}`" for rule_id in missing_reviewed_rule_ids)
    if undeclared_matched_rule_ids:
        lines.extend(["", "## Undeclared Matched Rules", ""])
        lines.extend(f"- `{rule_id}`" for rule_id in undeclared_matched_rule_ids)
    if unknown_declared_rule_ids:
        lines.extend(["", "## Unknown Declared Rules", ""])
        lines.extend(f"- `{rule_id}`" for rule_id in unknown_declared_rule_ids)
    if failed:
        lines.extend(["", "## Failed Cases", ""])
        for case in failed:
            lines.append(f"- `{case['scenario_id']}`")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
