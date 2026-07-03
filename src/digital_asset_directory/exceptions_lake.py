from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from .ids import stable_id
from .utils import (
    append_jsonl,
    json_dumps,
    redact_sensitive_text,
    safe_relative,
    sha256_bytes,
    sha256_file,
    utc_now,
)

EXCEPTION_OUTBOX = Path(".digital-asset") / "exceptions" / "outbox.jsonl"
RAW_EXCEPTION_DIR = Path("raw") / "exceptions" / "repo-events"
QUARANTINE_DIR = Path("processed") / "exceptions" / "quarantine"
LAKE_PATH = Path("processed") / "exceptions" / "lake" / "events.jsonl"
FIX_OUTCOME_PATH = Path("processed") / "exceptions" / "fix-outcomes" / "outcomes.jsonl"
REPORT_JSON = Path("processed") / "reports" / "exceptions_lake.json"
REPORT_MD = Path("processed") / "reports" / "exceptions_lake.md"
LEARNING_QUEUE_JSON = Path("processed") / "reports" / "exception_learning_queue.json"
LEARNING_QUEUE_MD = Path("processed") / "reports" / "exception_learning_queue.md"
LEARNING_READINESS_JSON = Path("processed") / "reports" / "exception_learning_readiness_check.json"
LEARNING_READINESS_MD = Path("processed") / "reports" / "exception_learning_readiness_check.md"
LEARNING_READINESS_SCENARIOS_SCHEMA = (
    Path("schemas") / "exception-learning-readiness-scenarios.schema.json"
)
EXCEPTION_EVENT_SCHEMA = Path("schemas") / "exception-event.schema.json"
EXCEPTION_FIX_SCHEMA = Path("schemas") / "exception-fix-outcome.schema.json"
BACKFILL_RUNS_DIR = Path("processed") / "exceptions" / "backfill-runs"
EXCEPTION_EVENT_TYPE_REGISTRY = Path("registry") / "exception-event-type-registry.json"
EXCEPTION_LEARNING_METHODOLOGY = Path("registry") / "exception-learning-methodology.json"

SCHEMA_VERSION = "0.1.0"
MAX_STRING_CHARS = 1200
MAX_RECORD_BYTES = 16_000
MAX_BACKFILL_EVENTS = 1000
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore (all )?(previous|prior|above) instructions\b"),
    re.compile(r"(?i)\b(system|developer) prompt\b"),
    re.compile(r"(?i)\bexecute (this )?(tool|command)\b"),
    re.compile(r"(?i)\bdo not (tell|show) (the )?(user|developer)\b"),
]

SOURCE_VISIBILITIES = {"public", "internal", "private", "restricted", "unknown"}
SEVERITIES = {"critical", "high", "medium", "low", "info"}
STATUSES = {"open", "triaged", "fixed", "accepted", "rejected", "duplicate", "archived"}
STAGES = {"preflight", "midflight", "postflight", "ci", "runtime", "review", "release", "backfill"}
AGENTS = {"codex", "claude", "cursor", "human", "ci", "runtime", "fable", "other"}
SENSITIVITIES = {"public_safe", "internal", "private", "restricted", "unknown"}
CAPTURE_CONTRACTS = {
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
FIX_DECISIONS = {"fixed", "accepted_risk", "deferred", "duplicate", "rejected", "rollback"}
FIX_REVIEW_STATUSES = {
    "candidate",
    "source_repo_confirmed",
    "human_reviewed",
    "rejected",
    "quarantine_candidate",
    "quarantined",
}
FIX_VALIDATION_STATUSES = {"validated", "validation_missing", "not_applicable", "failed"}
FIX_EVENT_LOOKUP_STATUSES = {"found_in_lake", "missing_from_lake"}
FALLBACK_EVENT_TYPE = "other"
BACKFILL_RULES = [
    {
        "rule_id": "backfill-rule:rust-shadow-parity",
        "terms": [
            "rust-shadow",
            "rust_shadow",
            "parity-mismatch",
            "parity_mismatch",
            "parity",
        ],
        "event_type": "rust_shadow_parity_mismatch",
        "severity": "high",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:test-timeout",
        "terms": [
            "test-timeout",
            "test_timeout",
            "pytest-timeout",
            "pytest_timeout",
            "slow-test",
            "slow_test",
        ],
        "event_type": "test_timeout",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:command-timeout",
        "terms": ["timeout", "hung", "hang"],
        "event_type": "command_timeout",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:mail-quarantine",
        "terms": ["mail-quarantine", "mail_quarantine", "quarantine"],
        "event_type": "mail_quarantine",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:stale-report",
        "terms": ["stale-report", "stale_report", "stale-artifact", "stale_artifact", "stale"],
        "event_type": "stale_generated_artifact",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:artifact-registration-drift",
        "terms": [
            "artifact-registration-drift",
            "artifact_registration_drift",
            "manifest-enrollment-gap",
            "manifest_enrollment_gap",
            "suite-membership-gap",
            "suite_membership_gap",
            "front-door-toc-gap",
            "front_door_toc_gap",
            "catalog-registration-gap",
            "catalog_registration_gap",
        ],
        "event_type": "artifact_registration_drift",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:rollback",
        "terms": ["rollback", "rolled-back", "rolled_back", "revert"],
        "event_type": "rollback",
        "severity": "high",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:dependency-install",
        "terms": [
            "dependency-failure",
            "dependency_failure",
            "install-failure",
            "install_failure",
            "pip-error",
            "cargo-error",
            "npm-error",
        ],
        "event_type": "dependency_install_failure",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:schema-validation",
        "terms": [
            "schema-validation",
            "schema_validation",
            "schema-error",
            "schema_error",
            "validation-error",
            "validation_error",
        ],
        "event_type": "schema_validation_failure",
        "severity": "high",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:review-finding",
        "terms": [
            "review-finding",
            "review_finding",
            "red-team",
            "red_team",
            "audit-finding",
            "audit_finding",
        ],
        "event_type": "review_finding",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:premortem",
        "terms": ["premortem", "failure-story", "failure_story"],
        "event_type": "premortem_failure_story",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:ci-failure",
        "terms": ["ci-failure", "ci_failure", "workflow-failure", "workflow_failure", "actions-failure", "actions_failure"],
        "event_type": "ci_failure",
        "severity": "medium",
        "capture_contract": "backfill_candidate",
    },
    {
        "rule_id": "backfill-rule:generic-exception",
        "terms": ["postmortem", "incident", "exception", "failure", "failed", "error", "bug"],
        "event_type": "backfill_exception_candidate",
        "severity": "info",
        "capture_contract": "backfill_candidate",
    },
]
BACKFILL_TERMS = {
    term: str(rule["event_type"])
    for rule in BACKFILL_RULES
    for term in rule["terms"]
}
BACKFILL_CLASSIFIER_REF = "registry/exception-event-type-registry.json#backfill_classifier"


@dataclass(frozen=True)
class BackfillAuthorization:
    """Reviewed authorization required before historical backfill writes events."""

    root: Path
    approval_id: str
    include_path_refs: bool = False
    repo_policies: Iterable[Any] | None = None
    approved_by: str = "reviewed_policy"
    reason: str = ""
    allow_public_facing: bool = False


BACKFILL_EXCLUDE_DIRS = {
    ".git",
    ".digital-asset",
    ".mypy_cache",
    ".pytest_cache",
    ".pytest-tmp-root",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "processed",
    "raw",
    "target",
    "temp",
    "tmp",
    "venv",
}
BACKFILL_SENSITIVE_PATH_TERMS = {
    ".env",
    "credential",
    "credentials",
    "password",
    "private-key",
    "private_key",
    "secret",
    "secrets",
    "session",
    "token",
}
LOCAL_PATH_FRAGMENTS = (
    "c:/users/",
    "c__users__",
    "/users/",
    "appdata/",
    "git projects/",
    "onedrive/",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")[:80] or "repo"


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().replace("\\", "/")).casefold()


def _path_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _path_phrase(value: str) -> str:
    return " ".join(_path_words(value))


def path_term_matches(path_text: str, term: str) -> bool:
    """Match path signals on token boundaries, not arbitrary substrings."""
    term_text = str(term).casefold()
    if not term_text:
        return False
    term_words = _path_words(term_text)
    if not term_words:
        return False
    if len(term_words) == 1:
        return term_words[0] in set(_path_words(path_text))
    haystack = f" {_path_phrase(path_text)} "
    needle = f" {' '.join(term_words)} "
    return needle in haystack


def _repo_root_for(path: Path) -> Path:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _safe_repo_path_ref(repo: Path) -> str:
    digest = sha256_bytes(repo.resolve().as_posix().encode("utf-8"))
    return f"repo-path-sha256:{digest}"


def _looks_like_local_path_ref(value: str) -> bool:
    normalized = value.replace("\\", "/").casefold()
    return (
        bool(re.match(r"^[a-z]:/", normalized))
        or normalized.startswith("/")
        or any(fragment in normalized for fragment in LOCAL_PATH_FRAGMENTS)
    )


def _safe_external_ref(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return value
    if _looks_like_local_path_ref(value):
        return f"path-ref-sha256:{sha256_bytes(value.encode('utf-8'))}"
    return value


def _safe_ref_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [_safe_external_ref(item) for item in value]


def _repo_policy_for(repo: Path, repo_policies: Iterable[Any] | None) -> Any | None:
    target = repo.resolve()
    for policy in repo_policies or []:
        try:
            if Path(policy.path).resolve() == target:
                return policy
        except OSError:
            continue
    return None


def _repo_policy_covering_path(repo: Path, repo_policies: Iterable[Any] | None) -> Any | None:
    target = repo.resolve()
    for policy in repo_policies or []:
        try:
            policy_path = Path(policy.path).resolve()
        except OSError:
            continue
        try:
            if target == policy_path or target.is_relative_to(policy_path):
                return policy
        except AttributeError:
            if target == policy_path or str(target).startswith(str(policy_path)):
                return policy
    return None


def _repo_identity(repo: Path, repo_policies: Iterable[Any] | None = None) -> tuple[str, str, bool]:
    policy = _repo_policy_for(repo, repo_policies) or _repo_policy_covering_path(
        repo,
        repo_policies,
    )
    if policy is not None:
        return str(policy.id), str(policy.visibility), bool(policy.public_facing)
    contract = repo / ".digital-asset" / "dad-integration.json"
    if contract.exists():
        try:
            payload = _load_json(contract)
            return (
                str(payload.get("repo_id") or payload.get("id") or repo.name),
                str(payload.get("visibility") or "unknown"),
                bool(payload.get("public_facing", False)),
            )
        except (OSError, json.JSONDecodeError):
            pass
    return repo.name, "unknown", False


def _is_path_relative_to(path: Path, base: Path) -> bool:
    try:
        return path.is_relative_to(base)
    except AttributeError:
        return path == base or str(path).startswith(str(base))


def validate_backfill_authorization(
    hub_root: Path,
    search_root: Path,
    *,
    include_path_refs: bool,
    authorization: BackfillAuthorization | None,
) -> list[Any]:
    """Validate historical backfill authorization before any lake writes happen."""

    if authorization is None:
        raise ValueError("Historical exception backfill requires BackfillAuthorization.")
    root = search_root.resolve()
    authorized_root = authorization.root.resolve()
    if not (root == authorized_root or _is_path_relative_to(root, authorized_root)):
        raise ValueError("BackfillAuthorization root does not cover requested search root.")
    approval = str(authorization.approval_id or "").strip()
    if not approval:
        raise ValueError("BackfillAuthorization lacks reviewed approval_id.")
    if include_path_refs and not authorization.include_path_refs:
        raise ValueError("Readable path refs require explicit BackfillAuthorization.")
    repo_policies = list(authorization.repo_policies or [])
    hub_resolved = hub_root.resolve()
    root_inside_dad = root == hub_resolved or _is_path_relative_to(root, hub_resolved)
    if root_inside_dad and approval == "dad-self-backfill":
        return repo_policies
    policy = _repo_policy_covering_path(root, repo_policies)
    if policy is None:
        raise ValueError("Backfill root is not covered by reviewed exceptions.repos policy.")
    policy_id = str(getattr(policy, "id", root))
    if not getattr(policy, "exceptions_enabled", True):
        raise ValueError(f"{policy_id} has exceptions_enabled=false.")
    if getattr(policy, "write_protected", False):
        raise ValueError(f"{policy_id} is write_protected for exception backfill.")
    if getattr(policy, "public_facing", False) and not authorization.allow_public_facing:
        raise ValueError(
            f"{policy_id} is public_facing and requires explicit public-facing backfill authorization."
        )
    if not getattr(policy, "backfill_allowed", False):
        raise ValueError(f"{policy_id} has backfill_allowed=false.")
    approved_ids = [str(value) for value in getattr(policy, "approved_approval_ids", []) or []]
    if approval not in approved_ids:
        raise ValueError(f"{approval!r} is not approved for exceptions repo policy {policy_id}.")
    if include_path_refs and getattr(policy, "visibility", "unknown") == "public":
        raise ValueError("Readable path refs are blocked for public exception backfill.")
    return repo_policies


def _backfill_policy_snapshot(repo_policies: Iterable[Any] | None) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for policy in repo_policies or []:
        try:
            path_ref = _safe_repo_path_ref(Path(policy.path))
        except (AttributeError, OSError):
            path_ref = "repo-path-sha256:unknown"
        snapshot.append(
            {
                "id": str(getattr(policy, "id", "")),
                "path_ref": path_ref,
                "visibility": str(getattr(policy, "visibility", "unknown")),
                "public_facing": bool(getattr(policy, "public_facing", False)),
                "exceptions_enabled": bool(getattr(policy, "exceptions_enabled", True)),
                "backfill_allowed": bool(getattr(policy, "backfill_allowed", False)),
                "write_protected": bool(getattr(policy, "write_protected", False)),
                "approved_approval_id_count": len(
                    getattr(policy, "approved_approval_ids", []) or []
                ),
            }
        )
    return sorted(snapshot, key=lambda item: item["id"])


def load_event_type_registry(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / "registry" / "exception-event-type-registry.json")


def backfill_classifier_rules(hub_root: Path) -> list[dict[str, Any]]:
    """Return reviewed backfill rules from the hub registry.

    DAD's hub registry is the source of truth for classification behavior. A
    missing or malformed classifier fails closed so hidden Python constants do
    not silently replace reviewed taxonomy policy.
    """
    try:
        registry = load_event_type_registry(hub_root)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "Exception backfill classifier registry is unavailable or malformed."
        ) from exc
    classifier = registry.get("backfill_classifier")
    if not isinstance(classifier, dict):
        raise ValueError("Exception event type registry lacks backfill_classifier.")
    rules = classifier.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("Exception backfill_classifier has no rules.")
    return [rule for rule in rules if isinstance(rule, dict)]


def backfill_classifier_version(hub_root: Path) -> str:
    registry = load_event_type_registry(hub_root)
    classifier = registry.get("backfill_classifier")
    if not isinstance(classifier, dict):
        raise ValueError("Exception event type registry lacks backfill_classifier.")
    return str(classifier.get("methodology_version") or "unknown")


def backfill_terms(hub_root: Path) -> dict[str, str]:
    return {
        str(term): str(rule.get("event_type", ""))
        for rule in backfill_classifier_rules(hub_root)
        for term in rule.get("terms", [])
        if str(term)
    }


def backfill_path_signal_terms(hub_root: Path) -> dict[str, dict[str, str]]:
    terms: dict[str, dict[str, str]] = {}
    for rule in backfill_classifier_rules(hub_root):
        event_type = str(rule.get("event_type", "")).strip()
        rule_id = str(rule.get("rule_id", "")).strip()
        rule_terms = rule.get("terms", [])
        if not rule_id:
            raise ValueError("Exception backfill_classifier rule lacks rule_id.")
        if not event_type:
            raise ValueError(f"Exception backfill_classifier rule {rule_id} lacks event_type.")
        if not isinstance(rule_terms, list) or not rule_terms:
            raise ValueError(f"Exception backfill_classifier rule {rule_id} lacks terms.")
        for term_value in rule_terms:
            term = str(term_value)
            if not term:
                continue
            terms[term] = {
                "pattern_family": "exception_pattern",
                "signal": f"path_keyword:{term}",
                "expected_review": "exception_event_or_no_packet",
                "suggested_event_type": event_type,
                "source_rule_id": rule_id,
                "source_registry": "registry/exception-event-type-registry.json#backfill_classifier",
                "classification_source": "backfill_classifier",
            }
    return terms


def load_learning_methodology(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / "registry" / "exception-learning-methodology.json")


def _exception_event_schema_path(hub_root: Path) -> Path:
    hub_schema = hub_root / EXCEPTION_EVENT_SCHEMA
    if hub_schema.exists():
        return hub_schema
    repo_schema = Path(__file__).resolve().parents[2] / EXCEPTION_EVENT_SCHEMA
    if repo_schema.exists():
        return repo_schema
    return hub_schema


def _exception_fix_schema_path(hub_root: Path) -> Path:
    hub_schema = hub_root / EXCEPTION_FIX_SCHEMA
    if hub_schema.exists():
        return hub_schema
    repo_schema = Path(__file__).resolve().parents[2] / EXCEPTION_FIX_SCHEMA
    if repo_schema.exists():
        return repo_schema
    return hub_schema


def _learning_readiness_scenarios_schema_path(hub_root: Path) -> Path:
    hub_schema = hub_root / LEARNING_READINESS_SCENARIOS_SCHEMA
    if hub_schema.exists():
        return hub_schema
    repo_schema = Path(__file__).resolve().parents[2] / LEARNING_READINESS_SCENARIOS_SCHEMA
    if repo_schema.exists():
        return repo_schema
    return hub_schema


def validate_exception_event_record(hub_root: Path, record: dict[str, Any]) -> None:
    schema = _load_json(_exception_event_schema_path(hub_root))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    try:
        validator_cls(schema).validate(record)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        location = path or "<record>"
        raise ValueError(f"Exception event schema validation failed at {location}: {exc.message}") from exc


def validate_exception_fix_outcome_record(hub_root: Path, record: dict[str, Any]) -> None:
    schema = _load_json(_exception_fix_schema_path(hub_root))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    try:
        validator_cls(schema).validate(record)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        location = path or "<record>"
        raise ValueError(
            f"Exception fix outcome schema validation failed at {location}: {exc.message}"
        ) from exc


def event_type_set(hub_root: Path) -> set[str]:
    registry = load_event_type_registry(hub_root)
    return {str(row["event_type"]) for row in registry.get("event_types", [])}


def event_type_categories(hub_root: Path) -> dict[str, str]:
    registry = load_event_type_registry(hub_root)
    return {
        str(row["event_type"]): str(row.get("category") or "unknown")
        for row in registry.get("event_types", [])
        if isinstance(row, dict) and row.get("event_type")
    }


TAXONOMY_AXIS_KEYS = [
    "origin_surface",
    "detection_mode",
    "impact_domain",
    "learning_route",
    "default_handling",
    "review_priority",
]


def _unknown_taxonomy_dimensions() -> dict[str, str]:
    return {
        "origin_surface": "unknown",
        "detection_mode": "unknown",
        "impact_domain": "unknown",
        "learning_route": "unknown",
        "default_handling": "unknown",
        "review_priority": "info",
    }


def exception_taxonomy_dimension_axes(hub_root: Path) -> dict[str, Any]:
    registry = load_event_type_registry(hub_root)
    taxonomy = registry.get("taxonomy_dimensions")
    if not isinstance(taxonomy, dict):
        return {}
    axes = taxonomy.get("axes")
    return axes if isinstance(axes, dict) else {}


def exception_category_taxonomy_defaults(hub_root: Path) -> dict[str, dict[str, str]]:
    registry = load_event_type_registry(hub_root)
    taxonomy = registry.get("taxonomy_dimensions")
    if not isinstance(taxonomy, dict):
        return {}
    defaults = taxonomy.get("category_defaults")
    if not isinstance(defaults, dict):
        return {}
    return {
        str(category): {
            axis: str(values.get(axis, _unknown_taxonomy_dimensions()[axis]))
            for axis in TAXONOMY_AXIS_KEYS
        }
        for category, values in defaults.items()
        if isinstance(values, dict)
    }


def event_type_taxonomy_dimensions(hub_root: Path) -> dict[str, dict[str, str]]:
    category_by_type = event_type_categories(hub_root)
    defaults_by_category = exception_category_taxonomy_defaults(hub_root)
    unknown = _unknown_taxonomy_dimensions()
    return {
        event_type: {
            **unknown,
            **defaults_by_category.get(category, {}),
        }
        for event_type, category in category_by_type.items()
    }


def taxonomy_dimensions_for_event_type(hub_root: Path, event_type: str) -> dict[str, str]:
    taxonomy_by_type = event_type_taxonomy_dimensions(hub_root)
    return dict(taxonomy_by_type.get(event_type, _unknown_taxonomy_dimensions()))


def normalize_event_type(hub_root: Path, event_type: str) -> str:
    cleaned = _slug(event_type.replace(":", "_")).replace("-", "_")
    return cleaned if cleaned in event_type_set(hub_root) else FALLBACK_EVENT_TYPE


def stable_exception_event_id(record: dict[str, Any]) -> str:
    command = record.get("command") or {}
    argv = command.get("argv") if isinstance(command, dict) else []
    identity = [
        str(record.get("source_repo", "")),
        str(record.get("capture_contract", "")),
        str(record.get("stage", "")),
        str(record.get("event_type", "")),
        _normal(" ".join(str(item) for item in argv or [])),
        _normal("|".join(str(item) for item in record.get("context_refs", []) or [])),
        _normal(str(record.get("error_fingerprint", ""))),
    ]
    return stable_id("exception-event", *identity)


def stable_exception_fix_id(record: dict[str, Any]) -> str:
    identity = [
        str(record.get("source_repo", "")),
        str(record.get("event_id", "")),
        str(record.get("decision", "")),
        str(record.get("owner_authority", "")),
        str(record.get("canonical_event_id", "")),
        _normal(str(record.get("summary", ""))),
        _normal("|".join(str(item) for item in record.get("validation_refs", []) or [])),
        _normal("|".join(str(item) for item in record.get("regression_test_refs", []) or [])),
        _normal("|".join(str(item) for item in record.get("fix_refs", []) or [])),
    ]
    return stable_id("exception-fix", *identity)


def _redact_and_limit(value: Any, issues: list[str]) -> tuple[Any, int]:
    if isinstance(value, str):
        redacted, count = redact_sensitive_text(value)
        if any(pattern.search(redacted) for pattern in PROMPT_INJECTION_PATTERNS):
            issues.append("prompt_injection_like_payload")
            digest = sha256_bytes(redacted.encode("utf-8"))
            redacted = f"[PROMPT_INJECTION_LIKE_TEXT_REJECTED_SHA256:{digest}]"
        if len(redacted) > MAX_STRING_CHARS:
            issues.append("long_string")
            digest = sha256_bytes(redacted.encode("utf-8"))
            redacted = f"[LONG_VALUE_REJECTED_SHA256:{digest}]"
        if redacted.count("\n") > 8:
            issues.append("raw_blob_like_multiline_value")
            digest = sha256_bytes(redacted.encode("utf-8"))
            redacted = f"[MULTILINE_VALUE_REJECTED_SHA256:{digest}]"
        if redacted.count("|") >= 8 and redacted.count("\n") >= 2:
            issues.append("table_like_value")
            digest = sha256_bytes(redacted.encode("utf-8"))
            redacted = f"[TABLE_LIKE_VALUE_REJECTED_SHA256:{digest}]"
        return redacted, count
    if isinstance(value, list):
        output: list[Any] = []
        total = 0
        for item in value:
            cleaned, count = _redact_and_limit(item, issues)
            output.append(cleaned)
            total += count
        return output, total
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        total = 0
        for key, item in value.items():
            cleaned, count = _redact_and_limit(item, issues)
            output[str(key)] = cleaned
            total += count
        return output, total
    return value, 0


def _append_prompt_injection_issues(value: Any, issues: list[str], *, path: str = "record") -> None:
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in PROMPT_INJECTION_PATTERNS):
            issues.append(f"prompt_injection_like_payload:{path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _append_prompt_injection_issues(item, issues, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _append_prompt_injection_issues(item, issues, path=f"{path}.{key}")


def screen_exception_record(record: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    cleaned, redaction_count = _redact_and_limit(record, issues)
    if not isinstance(cleaned, dict):
        raise TypeError("Exception record must be a JSON object.")
    _append_prompt_injection_issues(cleaned, issues)
    screening = dict(cleaned.get("screening") or {})
    if redaction_count:
        issues.append("credential_or_pii_pattern")
    raw_blob_blocked = any(
        issue in {"long_string", "raw_blob_like_multiline_value", "table_like_value"}
        for issue in issues
    )
    screening.update(
        {
            "credential_pii_screen": "blocked" if redaction_count else "pass",
            "raw_blob_policy": "blocked" if raw_blob_blocked else "pass",
            "redaction_count": redaction_count,
            "screened_at": utc_now(),
            "screening_note": (
                "Best-effort credential/PII screening only; pass does not prove content is safe."
            ),
        }
    )
    cleaned["screening"] = screening
    size = len(json_dumps(cleaned).encode("utf-8"))
    if size > MAX_RECORD_BYTES:
        issues.append("record_too_large")
    return cleaned, sorted(set(issues))


def build_exception_event(
    hub_root: Path,
    repo: Path,
    *,
    event_type: str,
    summary: str,
    stage: str = "midflight",
    severity: str = "medium",
    capture_contract: str = "failed_command",
    agent: str = "codex",
    source_visibility: str | None = None,
    task: str = "",
    command: list[str] | None = None,
    exit_code: int | None = None,
    duration_ms: int | None = None,
    context_refs: list[str] | None = None,
    validation_refs: list[str] | None = None,
    asset_refs: list[str] | None = None,
    harness_refs: list[str] | None = None,
    trace_refs: list[str] | None = None,
    symptoms: list[str] | None = None,
    error_fingerprint: str = "",
    suspected_cause: str = "",
    dedupe_key: str = "",
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    source_repo, policy_visibility, public_facing = _repo_identity(repo, repo_policies)
    # Packet-supplied source_visibility is advisory only. Reviewed policy or the
    # repo-local DAD contract decides visibility; unreviewed packets stay unknown.
    visibility = policy_visibility
    if visibility not in SOURCE_VISIBILITIES:
        visibility = "unknown"
    normalized_event_type = normalize_event_type(hub_root, event_type)
    if stage not in STAGES:
        stage = "midflight"
    if severity not in SEVERITIES:
        severity = "medium"
    if capture_contract not in CAPTURE_CONTRACTS:
        capture_contract = "failed_command"
    if agent not in AGENTS:
        agent = "other"
    cmd: dict[str, Any] = {"argv": command or []}
    if exit_code is not None:
        cmd["exit_code"] = exit_code
    if duration_ms is not None:
        cmd["duration_ms"] = duration_ms
    event_time = utc_now()
    provenance = {
        "canonical_repo_id": source_repo,
        "canonical_repo_path": _safe_repo_path_ref(repo),
        "source_visibility": visibility,
        "origin_chain": [{"repo": source_repo, "visibility": visibility, "observed_at": event_time}],
        "return_address": f"{source_repo}:{EXCEPTION_OUTBOX.as_posix()}",
        "composed_by": agent,
        "collected_by": "",
        "collected_at": "",
        "received_at": "",
    }
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": "",
        "event_time": event_time,
        "source_repo": source_repo,
        "source_visibility": visibility,
        "public_facing_source": public_facing,
        "source_provenance": provenance,
        "origin_chain": provenance["origin_chain"],
        "return_address": provenance["return_address"],
        "agent": agent,
        "actor": agent,
        "model": "",
        "task": summary[:220] if not task else task[:220],
        "stage": stage,
        "surface": capture_contract,
        "evidence_kind": "metadata_pointer",
        "event_type": normalized_event_type,
        "taxonomy_dimensions": taxonomy_dimensions_for_event_type(
            hub_root,
            normalized_event_type,
        ),
        "severity": severity,
        "status": "open",
        "outcome_status": "unresolved",
        "context_refs": context_refs or [],
        "capture_contract": capture_contract,
        "event_identity": {
            "identity_version": "exception-event-identity-v1",
            "identity_inputs": [
                "source_repo",
                "capture_contract",
                "stage",
                "event_type",
                "normalized_command",
                "normalized_path_refs",
                "error_fingerprint",
            ],
            "collision_policy": (
                "Same identity but materially different context becomes duplicate_suspect "
                "and requires review."
            ),
        },
        "command": cmd,
        "safe_summary": summary[:MAX_STRING_CHARS],
        "symptoms": symptoms or [],
        "error_fingerprint": error_fingerprint,
        "suspected_cause": suspected_cause,
        "fix_refs": [],
        "validation_refs": validation_refs or [],
        "asset_refs": asset_refs or [],
        "harness_refs": harness_refs or [],
        "trace_refs": trace_refs or [],
        "sensitivity": "public_safe" if visibility == "public" else visibility,
        "retention_class": "candidate_metadata",
        "screening": {
            "credential_pii_screen": "pending",
            "raw_blob_policy": "pass",
            "public_release_required": False,
            "human_release_id": "",
        },
        "public_release": {
            "target_visibility": "unknown",
            "public_release_required": False,
            "public_release_status": "not_required",
            "human_release_id": "",
            "release_reason": "",
        },
        "dedupe_key": dedupe_key,
        "review_status": "candidate",
    }
    record["event_id"] = stable_exception_event_id(record)
    record["dedupe_key"] = dedupe_key or stable_id("exception-dedupe", record["event_id"])
    return record


def _canonicalize_normalized_packet(
    record: dict[str, Any],
    repo: Path,
    *,
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    policy = _repo_policy_for(repo, repo_policies)
    source_repo, policy_visibility, public_facing = _repo_identity(repo, repo_policies)
    submitted_repo = str(record.get("source_repo") or "")
    if submitted_repo and submitted_repo != source_repo:
        raise ValueError(
            "Normalized exception packet source_repo does not match reviewed repo policy."
        )
    submitted_visibility = str(record.get("source_visibility") or "")
    if policy is not None and submitted_visibility and submitted_visibility != policy_visibility:
        raise ValueError(
            "Normalized exception packet source_visibility does not match reviewed repo policy."
        )
    # Packet-supplied source_visibility is advisory only. Reviewed policy or the
    # repo-local DAD contract decides visibility; unreviewed packets stay unknown.
    visibility = policy_visibility
    if visibility not in SOURCE_VISIBILITIES:
        visibility = "unknown"
    record["source_repo"] = source_repo
    record["source_visibility"] = visibility
    record["public_facing_source"] = public_facing
    event_time = str(record.get("event_time") or utc_now())
    provenance = dict(record.get("source_provenance") or {})
    provenance.update(
        {
            "canonical_repo_id": source_repo,
            "canonical_repo_path": _safe_repo_path_ref(repo),
            "source_visibility": visibility,
            "return_address": f"{source_repo}:{EXCEPTION_OUTBOX.as_posix()}",
        }
    )
    origin_chain = provenance.get("origin_chain")
    if not isinstance(origin_chain, list) or not origin_chain:
        origin_chain = [
            {"repo": source_repo, "visibility": visibility, "observed_at": event_time}
        ]
    sanitized_origin_chain: list[Any] = []
    for item in origin_chain:
        if isinstance(item, dict):
            sanitized = dict(item)
            if "repo" in sanitized:
                sanitized["repo"] = _safe_external_ref(sanitized["repo"])
            sanitized_origin_chain.append(sanitized)
        else:
            sanitized_origin_chain.append(_safe_external_ref(item))
    origin_chain = sanitized_origin_chain
    provenance["origin_chain"] = origin_chain
    provenance.setdefault("composed_by", str(record.get("agent") or "other"))
    provenance.setdefault("collected_by", "")
    provenance.setdefault("collected_at", "")
    provenance.setdefault("received_at", "")
    record["source_provenance"] = provenance
    record["origin_chain"] = origin_chain
    record["return_address"] = provenance["return_address"]
    for field in (
        "context_refs",
        "validation_refs",
        "asset_refs",
        "harness_refs",
        "trace_refs",
        "fix_refs",
    ):
        if field in record:
            record[field] = _safe_ref_list(record.get(field))
    command = record.get("command")
    if isinstance(command, dict) and isinstance(command.get("argv"), list):
        command = dict(command)
        command["argv"] = [_safe_external_ref(item) for item in command["argv"]]
        record["command"] = command
    return record


def normalize_exception_packet(
    hub_root: Path,
    repo: Path,
    packet: dict[str, Any],
    *,
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    if "event_id" in packet and "schema_version" in packet and "safe_summary" in packet:
        record = dict(packet)
        record = _canonicalize_normalized_packet(record, repo, repo_policies=repo_policies)
        record["event_type"] = normalize_event_type(hub_root, str(record.get("event_type", "")))
        record["taxonomy_dimensions"] = taxonomy_dimensions_for_event_type(
            hub_root,
            str(record["event_type"]),
        )
        record["event_id"] = stable_exception_event_id(record)
        if not record.get("dedupe_key"):
            record["dedupe_key"] = stable_id("exception-dedupe", str(record["event_id"]))
        return record
    summary = str(packet.get("safe_summary") or packet.get("summary") or "").strip()
    if not summary:
        raise ValueError("Exception packet requires safe_summary or summary.")
    command = packet.get("command", {})
    argv = command.get("argv", []) if isinstance(command, dict) else []
    exit_code = command.get("exit_code") if isinstance(command, dict) else None
    duration_ms = command.get("duration_ms") if isinstance(command, dict) else None
    return build_exception_event(
        hub_root,
        repo,
        event_type=str(packet.get("event_type") or packet.get("type") or FALLBACK_EVENT_TYPE),
        summary=summary,
        stage=str(packet.get("stage") or "midflight"),
        severity=str(packet.get("severity") or "medium"),
        capture_contract=str(packet.get("capture_contract") or "failed_command"),
        agent=str(packet.get("agent") or "other"),
        source_visibility=str(packet.get("source_visibility") or "unknown"),
        task=str(packet.get("task") or ""),
        command=[str(item) for item in argv] if isinstance(argv, list) else [],
        exit_code=exit_code if isinstance(exit_code, int) else None,
        duration_ms=duration_ms if isinstance(duration_ms, int) else None,
        context_refs=[str(item) for item in packet.get("context_refs", []) or []],
        validation_refs=[str(item) for item in packet.get("validation_refs", []) or []],
        asset_refs=[str(item) for item in packet.get("asset_refs", []) or []],
        harness_refs=[str(item) for item in packet.get("harness_refs", []) or []],
        trace_refs=[str(item) for item in packet.get("trace_refs", []) or []],
        symptoms=[str(item) for item in packet.get("symptoms", []) or []],
        error_fingerprint=str(packet.get("error_fingerprint") or ""),
        suspected_cause=str(packet.get("suspected_cause") or ""),
        dedupe_key=str(packet.get("dedupe_key") or ""),
        repo_policies=repo_policies,
    )


def record_exception_event(
    hub_root: Path,
    repo: Path,
    *,
    event_type: str,
    summary: str,
    stage: str = "midflight",
    severity: str = "medium",
    capture_contract: str = "failed_command",
    agent: str = "codex",
    source_visibility: str | None = None,
    command: list[str] | None = None,
    exit_code: int | None = None,
    duration_ms: int | None = None,
    context_refs: list[str] | None = None,
    validation_refs: list[str] | None = None,
    asset_refs: list[str] | None = None,
    harness_refs: list[str] | None = None,
    trace_refs: list[str] | None = None,
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    record = build_exception_event(
        hub_root,
        repo,
        event_type=event_type,
        summary=summary,
        stage=stage,
        severity=severity,
        capture_contract=capture_contract,
        agent=agent,
        source_visibility=source_visibility,
        command=command,
        exit_code=exit_code,
        duration_ms=duration_ms,
        context_refs=context_refs,
        validation_refs=validation_refs,
        asset_refs=asset_refs,
        harness_refs=harness_refs,
        trace_refs=trace_refs,
        repo_policies=repo_policies,
    )
    screened, issues = screen_exception_record(record)
    if issues:
        screened["review_status"] = "quarantine_candidate"
        screened["screening"]["issues"] = issues
    validate_exception_event_record(hub_root, screened)
    outbox = repo / EXCEPTION_OUTBOX
    append_jsonl(outbox, screened)
    return {
        "event": screened,
        "repo_path_ref": _safe_repo_path_ref(repo),
        "outbox_path": EXCEPTION_OUTBOX.as_posix(),
        "screening_issues": issues,
    }


def _event_lookup_status(hub_root: Path, event_id: str) -> str:
    return "found_in_lake" if any(
        str(event.get("event_id")) == event_id for event in load_lake_events(hub_root)
    ) else "missing_from_lake"


def _safe_origin_chain(
    origin_chain: Any,
    *,
    source_repo: str,
    visibility: str,
    observed_at: str,
) -> list[dict[str, str]]:
    if not isinstance(origin_chain, list) or not origin_chain:
        origin_chain = [
            {
                "repo": source_repo,
                "visibility": visibility,
                "observed_at": observed_at,
            }
        ]
    safe_chain: list[dict[str, str]] = []
    for item in origin_chain:
        if isinstance(item, dict):
            repo_ref = _safe_external_ref(item.get("repo") or source_repo)
            item_visibility = str(item.get("visibility") or visibility)
            if item_visibility not in SOURCE_VISIBILITIES:
                item_visibility = "unknown"
            safe_chain.append(
                {
                    "repo": str(repo_ref),
                    "visibility": item_visibility,
                    "observed_at": str(item.get("observed_at") or observed_at),
                }
            )
        else:
            safe_chain.append(
                {
                    "repo": str(_safe_external_ref(item)),
                    "visibility": visibility,
                    "observed_at": observed_at,
                }
            )
    return safe_chain


def _fix_validation_status(
    decision: str,
    validation_refs: list[str],
    regression_test_refs: list[str],
    event_lookup_status: str,
) -> str:
    if decision in {"fixed", "rollback"}:
        return (
            "validated"
            if validation_refs
            and regression_test_refs
            and event_lookup_status == "found_in_lake"
            else "validation_missing"
        )
    if decision in {"accepted_risk", "deferred", "duplicate", "rejected"}:
        return "not_applicable"
    return "validation_missing"


def _validate_fix_outcome_policy(
    *,
    decision: str,
    validation_refs: list[str],
    regression_test_refs: list[str],
    expiry: str,
    owner_authority: str,
    event_lookup_status: str,
    canonical_event_id: str,
    canonical_event_lookup_status: str,
) -> None:
    if not owner_authority.strip():
        raise ValueError("Exception fix outcome requires an explicit owner_authority.")
    if decision in {"fixed", "rollback"}:
        if not validation_refs:
            raise ValueError(
                f"Exception fix outcome decision '{decision}' requires at least one validation_ref."
            )
        if not regression_test_refs:
            raise ValueError(
                f"Exception fix outcome decision '{decision}' requires at least one regression_test_ref."
            )
        if event_lookup_status != "found_in_lake":
            raise ValueError(
                f"Exception fix outcome decision '{decision}' requires event_id to exist in the central lake."
            )
    if decision in {"accepted_risk", "deferred"} and not expiry.strip():
        raise ValueError(
            f"Exception fix outcome decision '{decision}' requires an expiry or revisit marker."
        )
    if decision == "duplicate":
        if not canonical_event_id.startswith("dad:exception-event:"):
            raise ValueError(
                "Exception fix outcome decision 'duplicate' requires canonical_event_id."
            )
        if canonical_event_lookup_status != "found_in_lake":
            raise ValueError(
                "Exception fix outcome decision 'duplicate' requires canonical_event_id to exist in the central lake."
            )


def build_exception_fix_outcome(
    hub_root: Path,
    repo: Path,
    *,
    event_id: str,
    decision: str,
    summary: str,
    recorded_by: str = "codex",
    validation_refs: list[str] | None = None,
    regression_test_refs: list[str] | None = None,
    fix_refs: list[str] | None = None,
    asset_refs: list[str] | None = None,
    lesson_refs: list[str] | None = None,
    owner_authority: str = "",
    canonical_event_id: str = "",
    expiry: str = "",
    remaining_risks: list[str] | None = None,
    review_status: str = "candidate",
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    if not event_id.startswith("dad:exception-event:"):
        raise ValueError("Exception fix outcome event_id must start with dad:exception-event:.")
    normalized_decision = decision.replace("-", "_").lower()
    if normalized_decision not in FIX_DECISIONS:
        raise ValueError(
            "decision must be fixed, accepted_risk, deferred, duplicate, rejected, or rollback"
        )
    normalized_review = review_status.replace("-", "_").lower()
    if normalized_review not in FIX_REVIEW_STATUSES:
        normalized_review = "candidate"
    refs_validation = [str(item) for item in validation_refs or [] if str(item).strip()]
    refs_regression = [str(item) for item in regression_test_refs or [] if str(item).strip()]
    refs_fix = [str(item) for item in fix_refs or [] if str(item).strip()]
    refs_asset = [str(item) for item in asset_refs or [] if str(item).strip()]
    refs_lesson = [str(item) for item in lesson_refs or [] if str(item).strip()]
    risks = [str(item) for item in remaining_risks or [] if str(item).strip()]
    source_repo, policy_visibility, _public_facing = _repo_identity(repo, repo_policies)
    visibility = policy_visibility if policy_visibility in SOURCE_VISIBILITIES else "unknown"
    event_status = _event_lookup_status(hub_root, event_id)
    canonical_event = canonical_event_id.strip()
    canonical_status = (
        _event_lookup_status(hub_root, canonical_event)
        if canonical_event.startswith("dad:exception-event:")
        else "missing_from_lake"
    )
    _validate_fix_outcome_policy(
        decision=normalized_decision,
        validation_refs=refs_validation,
        regression_test_refs=refs_regression,
        expiry=expiry,
        owner_authority=owner_authority,
        event_lookup_status=event_status,
        canonical_event_id=canonical_event,
        canonical_event_lookup_status=canonical_status,
    )
    recorded_at = utc_now()
    validation_status = _fix_validation_status(
        normalized_decision,
        refs_validation,
        refs_regression,
        event_status,
    )
    provenance = {
        "canonical_repo_id": source_repo,
        "canonical_repo_path": _safe_repo_path_ref(repo),
        "source_visibility": visibility,
        "origin_chain": _safe_origin_chain(
            None,
            source_repo=source_repo,
            visibility=visibility,
            observed_at=recorded_at,
        ),
        "return_address": f"{source_repo}:{FIX_OUTCOME_PATH.as_posix()}",
        "composed_by": recorded_by,
        "collected_by": "",
        "collected_at": "",
        "received_at": "",
    }
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "fix_id": "",
        "event_id": event_id,
        "recorded_at": recorded_at,
        "source_repo": source_repo,
        "source_visibility": visibility,
        "source_provenance": provenance,
        "recorded_by": recorded_by,
        "decision": normalized_decision,
        "summary": summary[:MAX_STRING_CHARS],
        "validation_status": validation_status,
        "validation_refs": _safe_ref_list(refs_validation),
        "regression_test_refs": _safe_ref_list(refs_regression),
        "fix_refs": _safe_ref_list(refs_fix),
        "asset_refs": _safe_ref_list(refs_asset),
        "lesson_refs": _safe_ref_list(refs_lesson),
        "remaining_risks": _safe_ref_list(risks),
        "owner_authority": owner_authority.strip(),
        "canonical_event_id": canonical_event,
        "canonical_event_lookup_status": canonical_status,
        "expiry": expiry.strip(),
        "event_lookup_status": event_status,
        "capture_contract": "fix_outcome",
        "dedupe_key": "",
        "screening": {
            "credential_pii_screen": "pending",
            "raw_blob_policy": "pass",
            "redaction_count": 0,
            "screened_at": "",
            "screening_note": (
                "Best-effort credential/PII screening only; pass does not prove content is safe."
            ),
        },
        "review_status": normalized_review,
        "authority_boundary": (
            "Fix outcome records are candidate metadata. A fixed decision requires validation "
            "refs and regression test refs but still does not override the source repo or "
            "prove factual truth outside that evidence."
        ),
    }
    record["fix_id"] = stable_exception_fix_id(record)
    record["dedupe_key"] = stable_id("exception-fix-dedupe", record["fix_id"])
    return record


def _canonicalize_fix_outcome_packet(
    record: dict[str, Any],
    repo: Path,
    hub_root: Path,
    *,
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    if "fix_id" not in record or "schema_version" not in record:
        return build_exception_fix_outcome(
            hub_root,
            repo,
            event_id=str(record.get("event_id") or ""),
            decision=str(record.get("decision") or ""),
            summary=str(record.get("summary") or ""),
            recorded_by=str(record.get("recorded_by") or "other"),
            validation_refs=[str(item) for item in record.get("validation_refs", []) or []],
            regression_test_refs=[
                str(item) for item in record.get("regression_test_refs", []) or []
            ],
            fix_refs=[str(item) for item in record.get("fix_refs", []) or []],
            asset_refs=[str(item) for item in record.get("asset_refs", []) or []],
            lesson_refs=[str(item) for item in record.get("lesson_refs", []) or []],
            owner_authority=str(record.get("owner_authority") or ""),
            canonical_event_id=str(record.get("canonical_event_id") or ""),
            expiry=str(record.get("expiry") or ""),
            remaining_risks=[str(item) for item in record.get("remaining_risks", []) or []],
            review_status=str(record.get("review_status") or "candidate"),
            repo_policies=repo_policies,
        )
    normalized = dict(record)
    source_repo, visibility, _public_facing = _repo_identity(repo, repo_policies)
    submitted_repo = str(normalized.get("source_repo") or "")
    if submitted_repo and submitted_repo != source_repo:
        raise ValueError(
            "Exception fix outcome source_repo does not match reviewed repo policy."
        )
    if str(normalized.get("source_visibility") or visibility) not in SOURCE_VISIBILITIES:
        visibility = "unknown"
    normalized["source_repo"] = source_repo
    normalized["source_visibility"] = visibility
    normalized["event_lookup_status"] = _event_lookup_status(
        hub_root,
        str(normalized.get("event_id") or ""),
    )
    canonical_event = str(normalized.get("canonical_event_id") or "").strip()
    normalized["canonical_event_id"] = canonical_event
    normalized["canonical_event_lookup_status"] = (
        _event_lookup_status(hub_root, canonical_event)
        if canonical_event.startswith("dad:exception-event:")
        else "missing_from_lake"
    )
    for field in (
        "validation_refs",
        "regression_test_refs",
        "fix_refs",
        "asset_refs",
        "lesson_refs",
        "remaining_risks",
    ):
        normalized[field] = _safe_ref_list(normalized.get(field))
    decision = str(normalized.get("decision") or "").replace("-", "_").lower()
    if decision not in FIX_DECISIONS:
        raise ValueError(
            "decision must be fixed, accepted_risk, deferred, duplicate, rejected, or rollback"
        )
    normalized["decision"] = decision
    _validate_fix_outcome_policy(
        decision=decision,
        validation_refs=[str(item) for item in normalized.get("validation_refs", [])],
        regression_test_refs=[
            str(item) for item in normalized.get("regression_test_refs", [])
        ],
        expiry=str(normalized.get("expiry") or ""),
        owner_authority=str(normalized.get("owner_authority") or ""),
        event_lookup_status=str(normalized.get("event_lookup_status") or ""),
        canonical_event_id=str(normalized.get("canonical_event_id") or ""),
        canonical_event_lookup_status=str(
            normalized.get("canonical_event_lookup_status") or ""
        ),
    )
    normalized["validation_status"] = _fix_validation_status(
        decision,
        [str(item) for item in normalized.get("validation_refs", [])],
        [str(item) for item in normalized.get("regression_test_refs", [])],
        str(normalized.get("event_lookup_status") or ""),
    )
    provenance = dict(normalized.get("source_provenance") or {})
    provenance.update(
        {
            "canonical_repo_id": source_repo,
            "canonical_repo_path": _safe_repo_path_ref(repo),
            "source_visibility": visibility,
            "return_address": f"{source_repo}:{FIX_OUTCOME_PATH.as_posix()}",
        }
    )
    provenance["origin_chain"] = _safe_origin_chain(
        provenance.get("origin_chain"),
        source_repo=source_repo,
        visibility=visibility,
        observed_at=str(normalized.get("recorded_at") or utc_now()),
    )
    provenance.setdefault("composed_by", str(normalized.get("recorded_by") or "other"))
    provenance.setdefault("collected_by", "")
    provenance.setdefault("collected_at", "")
    provenance.setdefault("received_at", "")
    normalized["source_provenance"] = provenance
    normalized["capture_contract"] = "fix_outcome"
    normalized["fix_id"] = stable_exception_fix_id(normalized)
    normalized["dedupe_key"] = normalized.get("dedupe_key") or stable_id(
        "exception-fix-dedupe", str(normalized["fix_id"])
    )
    normalized.setdefault(
        "authority_boundary",
        (
            "Fix outcome records are candidate metadata. A fixed decision requires validation "
            "refs and regression test refs but still does not override the source repo or "
            "prove factual truth outside that evidence."
        ),
    )
    return normalized


def record_exception_fix_outcome(
    hub_root: Path,
    repo: Path,
    *,
    event_id: str,
    decision: str,
    summary: str,
    recorded_by: str = "codex",
    validation_refs: list[str] | None = None,
    regression_test_refs: list[str] | None = None,
    fix_refs: list[str] | None = None,
    asset_refs: list[str] | None = None,
    lesson_refs: list[str] | None = None,
    owner_authority: str = "",
    canonical_event_id: str = "",
    expiry: str = "",
    remaining_risks: list[str] | None = None,
    review_status: str = "candidate",
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    record = build_exception_fix_outcome(
        hub_root,
        repo,
        event_id=event_id,
        decision=decision,
        summary=summary,
        recorded_by=recorded_by,
        validation_refs=validation_refs,
        regression_test_refs=regression_test_refs,
        fix_refs=fix_refs,
        asset_refs=asset_refs,
        lesson_refs=lesson_refs,
        owner_authority=owner_authority,
        canonical_event_id=canonical_event_id,
        expiry=expiry,
        remaining_risks=remaining_risks,
        review_status=review_status,
        repo_policies=repo_policies,
    )
    screened, issues = screen_exception_record(record)
    if issues:
        screened["review_status"] = "quarantine_candidate"
        screened["screening"]["issues"] = issues
    validate_exception_fix_outcome_record(hub_root, screened)
    outbox = repo / FIX_OUTCOME_PATH
    append_jsonl(outbox, screened)
    return {
        "fix_outcome": screened,
        "repo_path_ref": _safe_repo_path_ref(repo),
        "outbox_path": FIX_OUTCOME_PATH.as_posix(),
        "screening_issues": issues,
        "authority_boundary": screened["authority_boundary"],
    }


def _read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not path.exists():
        return records, errors
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped_bytes = raw_line.strip()
            if not stripped_bytes:
                continue
            try:
                stripped = stripped_bytes.decode("utf-8")
                payload = json.loads(stripped)
            except UnicodeDecodeError as exc:
                errors.append(
                    {
                        "line": line_number,
                        "error": f"Invalid UTF-8: {exc}",
                        "raw_sha256": sha256_bytes(stripped_bytes),
                    }
                )
                continue
            except json.JSONDecodeError as exc:
                errors.append(
                    {"line": line_number, "error": str(exc), "raw_sha256": sha256_bytes(stripped_bytes)}
                )
                continue
            if not isinstance(payload, dict):
                errors.append(
                    {
                        "line": line_number,
                        "error": "JSONL row must be an object.",
                        "raw_sha256": sha256_bytes(stripped_bytes),
                    }
                )
                continue
            records.append(payload)
    return records, errors


def _existing_events_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    events: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event_id"):
            events[str(payload["event_id"])] = payload
    return events


def _collision_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_repo": record.get("source_repo"),
        "source_visibility": record.get("source_visibility"),
        "event_type": record.get("event_type"),
        "severity": record.get("severity"),
        "status": record.get("status"),
        "outcome_status": record.get("outcome_status"),
        "capture_contract": record.get("capture_contract"),
        "context_refs": record.get("context_refs") or [],
        "validation_refs": record.get("validation_refs") or [],
        "asset_refs": record.get("asset_refs") or [],
        "harness_refs": record.get("harness_refs") or [],
        "trace_refs": record.get("trace_refs") or [],
        "safe_summary": record.get("safe_summary"),
        "public_release": record.get("public_release") or {},
    }


def _append_lake_event(hub_root: Path, record: dict[str, Any]) -> str:
    lake = hub_root / LAKE_PATH
    existing = _existing_events_by_id(lake).get(str(record["event_id"]))
    if existing is not None:
        if _collision_fields(existing) == _collision_fields(record):
            return "duplicate"
        append_jsonl(
            hub_root / QUARANTINE_DIR / "duplicate_collision_suspect.jsonl",
            {
                "event_type": "duplicate_collision_suspect",
                "created_at": utc_now(),
                "event_id": record["event_id"],
                "source_repo": record.get("source_repo", "unknown"),
                "existing_record_sha256": sha256_bytes(
                    json_dumps(existing).encode("utf-8")
                ),
                "incoming_record_sha256": sha256_bytes(
                    json_dumps(record).encode("utf-8")
                ),
                "reason": "same event_id with materially different event fields",
                "changed_fields": sorted(
                    key
                    for key in _collision_fields(record)
                    if _collision_fields(existing).get(key)
                    != _collision_fields(record).get(key)
                ),
            },
        )
        return "collision"
    append_jsonl(lake, record)
    raw_path = (
        hub_root
        / RAW_EXCEPTION_DIR
        / str(record["event_time"])[:10]
        / f"{_slug(str(record['source_repo']))}.jsonl"
    )
    append_jsonl(raw_path, record)
    return "created"


def _existing_fix_outcomes_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    outcomes: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("fix_id"):
            outcomes[str(payload["fix_id"])] = payload
    return outcomes


def _fix_collision_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": record.get("event_id"),
        "source_repo": record.get("source_repo"),
        "source_visibility": record.get("source_visibility"),
        "decision": record.get("decision"),
        "summary": record.get("summary"),
        "validation_status": record.get("validation_status"),
        "validation_refs": record.get("validation_refs") or [],
        "regression_test_refs": record.get("regression_test_refs") or [],
        "fix_refs": record.get("fix_refs") or [],
        "asset_refs": record.get("asset_refs") or [],
        "lesson_refs": record.get("lesson_refs") or [],
        "owner_authority": record.get("owner_authority"),
        "canonical_event_id": record.get("canonical_event_id"),
        "canonical_event_lookup_status": record.get("canonical_event_lookup_status"),
        "expiry": record.get("expiry"),
        "event_lookup_status": record.get("event_lookup_status"),
        "review_status": record.get("review_status"),
    }


def _append_fix_outcome_record(hub_root: Path, record: dict[str, Any]) -> str:
    path = hub_root / FIX_OUTCOME_PATH
    existing = _existing_fix_outcomes_by_id(path).get(str(record["fix_id"]))
    if existing is not None:
        if _fix_collision_fields(existing) == _fix_collision_fields(record):
            return "duplicate"
        append_jsonl(
            hub_root / QUARANTINE_DIR / "fix_outcome_duplicate_collision_suspect.jsonl",
            {
                "event_type": "fix_outcome_duplicate_collision_suspect",
                "created_at": utc_now(),
                "fix_id": record["fix_id"],
                "event_id": record.get("event_id", ""),
                "source_repo": record.get("source_repo", "unknown"),
                "existing_record_sha256": sha256_bytes(
                    json_dumps(existing).encode("utf-8")
                ),
                "incoming_record_sha256": sha256_bytes(
                    json_dumps(record).encode("utf-8")
                ),
                "reason": "same fix_id with materially different fix outcome fields",
                "changed_fields": sorted(
                    key
                    for key in _fix_collision_fields(record)
                    if _fix_collision_fields(existing).get(key)
                    != _fix_collision_fields(record).get(key)
                ),
            },
        )
        return "collision"
    append_jsonl(path, record)
    raw_path = (
        hub_root
        / RAW_EXCEPTION_DIR
        / str(record["recorded_at"])[:10]
        / f"{_slug(str(record['source_repo']))}-fix-outcomes.jsonl"
    )
    append_jsonl(raw_path, record)
    return "created"


def collect_exception_fix_outcomes(
    hub_root: Path,
    repo: Path,
    *,
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    outbox = repo / FIX_OUTCOME_PATH
    records, malformed = _read_jsonl_with_errors(outbox)
    repo_id, _, _ = _repo_identity(repo, repo_policies)
    malformed_path = hub_root / QUARANTINE_DIR / "fix_outcome_malformed_jsonl.jsonl"
    for error in malformed:
        append_jsonl(
            malformed_path,
            {
                "event_type": "fix_outcome_malformed_jsonl",
                "created_at": utc_now(),
                "source_repo": repo_id,
                "repo_path_ref": _safe_repo_path_ref(repo),
                "outbox_path": FIX_OUTCOME_PATH.as_posix(),
                **error,
            },
        )
    collected = 0
    duplicates = 0
    duplicate_collisions = 0
    quarantined = 0
    quarantine_path = hub_root / QUARANTINE_DIR / f"{_slug(repo_id)}-fix-outcomes.jsonl"
    for packet in records:
        try:
            normalized = _canonicalize_fix_outcome_packet(
                packet,
                repo,
                hub_root,
                repo_policies=repo_policies,
            )
            provenance = dict(normalized.get("source_provenance") or {})
            provenance["collected_by"] = "dad-exceptions-collect"
            provenance["collected_at"] = utc_now()
            provenance["received_at"] = provenance["collected_at"]
            normalized["source_provenance"] = provenance
            screened, issues = screen_exception_record(normalized)
        except (TypeError, ValueError) as exc:
            quarantined += 1
            append_jsonl(
                quarantine_path,
                {
                    "event_type": "fix_outcome_packet_rejected",
                    "created_at": utc_now(),
                    "source_repo": repo_id,
                    "reason": str(exc),
                    "packet_sha256": sha256_bytes(json_dumps(packet).encode("utf-8")),
                },
            )
            continue
        prior_screening = screened.get("screening") if isinstance(screened.get("screening"), dict) else {}
        inherited_issues = [str(item) for item in prior_screening.get("issues", []) or []]
        if prior_screening.get("credential_pii_screen") == "blocked":
            inherited_issues.append("credential_or_pii_pattern")
        if prior_screening.get("raw_blob_policy") == "blocked":
            inherited_issues.append("raw_blob_policy_blocked")
        if screened.get("review_status") in {"quarantine_candidate", "quarantined"}:
            inherited_issues.append(str(screened.get("review_status")))
        all_issues = sorted(set([*issues, *inherited_issues]))
        if all_issues:
            quarantined += 1
            screened["review_status"] = "quarantined"
            screened["screening"]["issues"] = all_issues
            append_jsonl(quarantine_path, screened)
            continue
        try:
            validate_exception_fix_outcome_record(hub_root, screened)
        except ValueError as exc:
            quarantined += 1
            screened["review_status"] = "quarantined"
            screened["screening"]["issues"] = [
                *all_issues,
                "schema_validation_failed",
            ]
            append_jsonl(
                quarantine_path,
                {
                    **screened,
                    "quarantine_reason": str(exc),
                },
            )
            continue
        append_status = _append_fix_outcome_record(hub_root, screened)
        if append_status == "created":
            collected += 1
        elif append_status == "collision":
            quarantined += 1
            duplicate_collisions += 1
        else:
            duplicates += 1
    return {
        "repo": repo_id,
        "repo_path_ref": _safe_repo_path_ref(repo),
        "outbox_path": FIX_OUTCOME_PATH.as_posix(),
        "collected_count": collected,
        "duplicate_count": duplicates,
        "duplicate_collision_count": duplicate_collisions,
        "quarantined_count": quarantined,
        "malformed_count": len(malformed),
        "fix_outcomes_path": FIX_OUTCOME_PATH.as_posix(),
        "quarantine_path": safe_relative(quarantine_path, hub_root),
    }


def collect_exception_events(
    hub_root: Path,
    repo: Path,
    *,
    repo_policies: Iterable[Any] | None = None,
) -> dict[str, Any]:
    outbox = repo / EXCEPTION_OUTBOX
    records, malformed = _read_jsonl_with_errors(outbox)
    repo_id, _, _ = _repo_identity(repo, repo_policies)
    malformed_path = hub_root / QUARANTINE_DIR / "malformed_jsonl.jsonl"
    for error in malformed:
        append_jsonl(
            malformed_path,
            {
                "event_type": "malformed_jsonl",
                "created_at": utc_now(),
                "source_repo": repo_id,
                "repo_path_ref": _safe_repo_path_ref(repo),
                "outbox_path": EXCEPTION_OUTBOX.as_posix(),
                **error,
            },
        )
    collected = 0
    duplicates = 0
    duplicate_collisions = 0
    quarantined = 0
    quarantine_path = hub_root / QUARANTINE_DIR / f"{_slug(repo_id)}.jsonl"
    for packet in records:
        try:
            normalized = normalize_exception_packet(
                hub_root, repo, packet, repo_policies=repo_policies
            )
            provenance = dict(normalized.get("source_provenance") or {})
            provenance["collected_by"] = "dad-exceptions-collect"
            provenance["collected_at"] = utc_now()
            provenance["received_at"] = provenance["collected_at"]
            normalized["source_provenance"] = provenance
            screened, issues = screen_exception_record(normalized)
        except (TypeError, ValueError) as exc:
            quarantined += 1
            append_jsonl(
                quarantine_path,
                {
                    "event_type": "exception_packet_rejected",
                    "created_at": utc_now(),
                    "source_repo": repo_id,
                    "reason": str(exc),
                    "packet_sha256": sha256_bytes(json_dumps(packet).encode("utf-8")),
                },
            )
            continue
        prior_screening = screened.get("screening") if isinstance(screened.get("screening"), dict) else {}
        inherited_issues = [str(item) for item in prior_screening.get("issues", []) or []]
        if prior_screening.get("credential_pii_screen") == "blocked":
            inherited_issues.append("credential_or_pii_pattern")
        if prior_screening.get("raw_blob_policy") == "blocked":
            inherited_issues.append("raw_blob_policy_blocked")
        if screened.get("review_status") in {"quarantine_candidate", "quarantined"}:
            inherited_issues.append(str(screened.get("review_status")))
        all_issues = sorted(set([*issues, *inherited_issues]))
        if all_issues:
            quarantined += 1
            screened["review_status"] = "quarantined"
            screened["screening"]["issues"] = all_issues
            append_jsonl(quarantine_path, screened)
            continue
        try:
            validate_exception_event_record(hub_root, screened)
        except ValueError as exc:
            quarantined += 1
            screened["review_status"] = "quarantined"
            screened["screening"]["issues"] = [
                *all_issues,
                "schema_validation_failed",
            ]
            append_jsonl(
                quarantine_path,
                {
                    **screened,
                    "quarantine_reason": str(exc),
                },
            )
            continue
        append_status = _append_lake_event(hub_root, screened)
        if append_status == "created":
            collected += 1
        elif append_status == "collision":
            quarantined += 1
            duplicate_collisions += 1
        else:
            duplicates += 1
    return {
        "repo": repo_id,
        "repo_path_ref": _safe_repo_path_ref(repo),
        "outbox_path": EXCEPTION_OUTBOX.as_posix(),
        "collected_count": collected,
        "duplicate_count": duplicates,
        "duplicate_collision_count": duplicate_collisions,
        "quarantined_count": quarantined,
        "malformed_count": len(malformed),
        "lake_path": LAKE_PATH.as_posix(),
        "quarantine_path": safe_relative(quarantine_path, hub_root),
    }


def _candidate_classification(hub_root: Path, path: Path) -> dict[str, str] | None:
    for rule in backfill_classifier_rules(hub_root):
        for term in sorted(rule["terms"], key=len, reverse=True):
            if path_term_matches(path.as_posix(), str(term)):
                return {
                    "term": str(term),
                    "rule_id": str(rule["rule_id"]),
                    "event_type": str(rule["event_type"]),
                    "severity": str(rule["severity"]),
                    "capture_contract": str(rule["capture_contract"]),
                    "classifier_ref": BACKFILL_CLASSIFIER_REF,
                    "classifier_version": backfill_classifier_version(hub_root),
                }
    return None


def _candidate_keyword(hub_root: Path, path: Path) -> tuple[str, str] | None:
    classification = _candidate_classification(hub_root, path)
    if classification is None:
        return None
    return classification["term"], classification["event_type"]


def _backfill_context_refs(
    rel: str,
    keyword: str,
    rule_id: str,
    classifier_version: str,
    *,
    include_path_refs: bool,
) -> list[str]:
    refs = [
        f"path-keyword:{keyword}",
        f"backfill-rule-id:{rule_id}",
        f"backfill-classifier-ref:{BACKFILL_CLASSIFIER_REF}",
        f"backfill-classifier-version:{classifier_version}",
        f"repo-relative-sha256:{sha256_bytes(rel.encode('utf-8'))}",
    ]
    if include_path_refs:
        refs.insert(0, f"repo-relative:{rel}")
    else:
        refs.append("repo-relative-path-redacted:true")
    return refs


def _is_excluded(path: Path, base: Path | None = None) -> bool:
    try:
        scoped = path.resolve().relative_to(base.resolve()) if base is not None else path
    except ValueError:
        scoped = path
    normalized = scoped.as_posix().casefold()
    return (
        any(part.casefold() in BACKFILL_EXCLUDE_DIRS for part in scoped.parts)
        or any(part.casefold().startswith("pytest-of-") for part in scoped.parts)
        or any(term in normalized for term in BACKFILL_SENSITIVE_PATH_TERMS)
    )


def backfill_exception_candidates(
    hub_root: Path,
    search_root: Path,
    *,
    limit: int = 200,
    per_repo_limit: int = 50,
    include_path_refs: bool = False,
    repo_policies: Iterable[Any] | None = None,
    max_scanned_files: int = 0,
    authorization: BackfillAuthorization | None = None,
) -> dict[str, Any]:
    effective_repo_policies = validate_backfill_authorization(
        hub_root,
        search_root,
        include_path_refs=include_path_refs,
        authorization=authorization,
    )
    if repo_policies is None:
        repo_policies = effective_repo_policies
    limit = max(1, min(limit, MAX_BACKFILL_EVENTS))
    per_repo_limit = max(1, min(per_repo_limit, limit))
    max_scanned_files = max(0, max_scanned_files)
    existing_by_repo = Counter(
        str(event.get("source_repo", "unknown"))
        for event in load_lake_events(hub_root)
        if event.get("capture_contract") == "backfill_candidate"
        or event.get("stage") == "backfill"
    )
    created = 0
    skipped_duplicates = 0
    duplicate_collisions = 0
    skipped_repo_cap = 0
    scanned_file_count = 0
    stopped_reason = ""
    classification_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    for dirpath, dirnames, filenames in os.walk(search_root):
        dir_path = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if name.casefold() not in BACKFILL_EXCLUDE_DIRS
            and not _is_excluded(dir_path / name, search_root)
        ]
        for filename in sorted(filenames):
            if created >= limit:
                stopped_reason = "created_limit_reached"
                break
            path = dir_path / filename
            if _is_excluded(path, search_root):
                continue
            if max_scanned_files and scanned_file_count >= max_scanned_files:
                stopped_reason = "scanned_file_limit_reached"
                break
            scanned_file_count += 1
            classification = _candidate_classification(hub_root, path)
            if classification is None:
                continue
            keyword = classification["term"]
            rule_id = classification["rule_id"]
            event_type = classification["event_type"]
            source_root = _repo_root_for(path)
            source_repo, _, _ = _repo_identity(source_root, repo_policies)
            if existing_by_repo[source_repo] >= per_repo_limit:
                skipped_repo_cap += 1
                continue
            rel = safe_relative(path, source_root)
            rel_hash = sha256_bytes(rel.encode("utf-8"))
            record = build_exception_event(
                hub_root,
                source_root,
                event_type=event_type,
                summary=(
                    f"Backfill candidate from path keyword '{keyword}' "
                    f"classified as '{event_type}'."
                ),
                stage="backfill",
                severity=classification["severity"],
                capture_contract=classification["capture_contract"],
                agent="other",
                context_refs=_backfill_context_refs(
                    rel,
                    keyword,
                    rule_id,
                    classification["classifier_version"],
                    include_path_refs=include_path_refs,
                ),
                symptoms=[
                    f"path keyword: {keyword}",
                    f"backfill rule: {rule_id}",
                    f"backfill classifier: {classification['classifier_version']}",
                    f"classified event type: {event_type}",
                ],
                error_fingerprint=stable_id(
                    "exception-backfill-path",
                    source_repo,
                    rel_hash,
                    keyword,
                    event_type,
                ),
                repo_policies=repo_policies,
            )
            record["evidence_kind"] = "backfill_path_signal"
            screened, issues = screen_exception_record(record)
            if issues:
                screened["review_status"] = "quarantined"
                screened["screening"]["issues"] = issues
                append_jsonl(hub_root / QUARANTINE_DIR / "backfill.jsonl", screened)
                continue
            try:
                validate_exception_event_record(hub_root, screened)
            except ValueError as exc:
                screened["review_status"] = "quarantined"
                screened["screening"]["issues"] = ["schema_validation_failed"]
                append_jsonl(
                    hub_root / QUARANTINE_DIR / "backfill.jsonl",
                    {
                        **screened,
                        "quarantine_reason": str(exc),
                    },
                )
                continue
            append_status = _append_lake_event(hub_root, screened)
            if append_status == "created":
                created += 1
                existing_by_repo[source_repo] += 1
                classification_counts[event_type] += 1
                rule_counts[rule_id] += 1
            elif append_status == "collision":
                duplicate_collisions += 1
            else:
                skipped_duplicates += 1
        if stopped_reason:
            break
    stopped = stopped_reason or "walk_exhausted"
    policy_snapshot = _backfill_policy_snapshot(repo_policies)
    classifier_path = hub_root / "registry" / "exception-event-type-registry.json"
    run_record = {
        "schema_version": "0.1.0",
        "run_id": stable_id("exception-backfill-run", utc_now(), search_root.resolve().as_posix()),
        "created_at": utc_now(),
        "search_root_path_ref": _safe_repo_path_ref(search_root),
        "created_count": created,
        "duplicate_count": skipped_duplicates,
        "duplicate_collision_count": duplicate_collisions,
        "skipped_repo_cap_count": skipped_repo_cap,
        "scanned_file_count": scanned_file_count,
        "max_scanned_files": max_scanned_files,
        "stopped_reason": stopped,
        "per_repo_limit": per_repo_limit,
        "include_path_refs": include_path_refs,
        "classification_counts": dict(sorted(classification_counts.items())),
        "rule_counts": dict(sorted(rule_counts.items())),
        "classifier_ref": BACKFILL_CLASSIFIER_REF,
        "classifier_version": backfill_classifier_version(hub_root),
        "classifier_hash": f"sha256:{sha256_file(classifier_path)}",
        "exception_repo_policy_hash": f"sha256:{sha256_bytes(json_dumps(policy_snapshot).encode('utf-8'))}",
        "authorization": {
            "approval_id": authorization.approval_id,
            "approved_by": authorization.approved_by,
            "include_path_refs": authorization.include_path_refs,
            "allow_public_facing": authorization.allow_public_facing,
            "reason": authorization.reason,
        },
        "lake_path": LAKE_PATH.as_posix(),
        "coverage_warning": "partial_backfill_wave" if stopped != "walk_exhausted" else "",
    }
    latest_run = hub_root / BACKFILL_RUNS_DIR / "latest.json"
    latest_run.parent.mkdir(parents=True, exist_ok=True)
    latest_run.write_text(json_dumps(run_record, pretty=True) + "\n", encoding="utf-8")
    append_jsonl(hub_root / BACKFILL_RUNS_DIR / "runs.jsonl", run_record)
    report = write_exception_report(hub_root)
    return {
        **run_record,
        "report": report,
    }


def load_lake_events(hub_root: Path) -> list[dict[str, Any]]:
    path = hub_root / LAKE_PATH
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def load_fix_outcomes(hub_root: Path) -> list[dict[str, Any]]:
    path = hub_root / FIX_OUTCOME_PATH
    records, errors = _read_jsonl_with_errors(path)
    for error in errors:
        append_jsonl(
            hub_root / QUARANTINE_DIR / "fix_outcome_report_malformed_jsonl.jsonl",
            {
                "event_type": "fix_outcome_report_malformed_jsonl",
                "created_at": utc_now(),
                "path": FIX_OUTCOME_PATH.as_posix(),
                **error,
            },
        )
    valid_records: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        try:
            validate_exception_fix_outcome_record(hub_root, record)
        except ValueError as exc:
            append_jsonl(
                hub_root / QUARANTINE_DIR / "fix_outcome_report_invalid_records.jsonl",
                {
                    "event_type": "fix_outcome_report_invalid_record",
                    "created_at": utc_now(),
                    "path": FIX_OUTCOME_PATH.as_posix(),
                    "line_number": index,
                    "reason": str(exc),
                    "record_sha256": sha256_bytes(json_dumps(record).encode("utf-8")),
                },
            )
            continue
        valid_records.append(record)
    return valid_records


def _is_backfill_candidate_event(event: dict[str, Any]) -> bool:
    return (
        event.get("capture_contract") == "backfill_candidate"
        or event.get("stage") == "backfill"
        or event.get("evidence_kind") == "backfill_path_signal"
    )


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def _is_validated_fixed_outcome(row: dict[str, Any]) -> bool:
    return (
        row.get("decision") == "fixed"
        and row.get("validation_status") == "validated"
        and _non_empty_string_list(row.get("validation_refs"))
        and _non_empty_string_list(row.get("regression_test_refs"))
        and row.get("event_lookup_status") == "found_in_lake"
        and row.get("review_status") not in {"quarantine_candidate", "quarantined", "rejected"}
    )


def write_exception_report(hub_root: Path) -> dict[str, Any]:
    events = load_lake_events(hub_root)
    fix_outcomes = load_fix_outcomes(hub_root)
    backfill_candidate_count = sum(1 for event in events if _is_backfill_candidate_event(event))
    observed_exception_count = len(events) - backfill_candidate_count
    reviewed_exception_count = sum(
        1
        for event in events
        if not _is_backfill_candidate_event(event)
        and event.get("review_status") in {"triaged", "reviewed", "promoted"}
    )
    by_type = Counter(str(event.get("event_type", "unknown")) for event in events)
    category_by_type = event_type_categories(hub_root)
    taxonomy_by_type = event_type_taxonomy_dimensions(hub_root)
    by_category = Counter(
        category_by_type.get(str(event.get("event_type", "unknown")), "unknown")
        for event in events
    )
    by_taxonomy_dimension: dict[str, dict[str, int]] = {}
    for axis in TAXONOMY_AXIS_KEYS:
        by_taxonomy_dimension[axis] = dict(
            sorted(
                Counter(
                    taxonomy_by_type.get(
                        str(event.get("event_type", "unknown")),
                        _unknown_taxonomy_dimensions(),
                    ).get(axis, _unknown_taxonomy_dimensions()[axis])
                    for event in events
                ).items()
            )
        )
    by_repo = Counter(str(event.get("source_repo", "unknown")) for event in events)
    by_severity = Counter(str(event.get("severity", "unknown")) for event in events)
    fix_by_decision = Counter(str(row.get("decision", "unknown")) for row in fix_outcomes)
    fix_by_validation = Counter(
        str(row.get("validation_status", "unknown")) for row in fix_outcomes
    )
    event_ids_with_fix_outcomes = {
        str(row.get("event_id")) for row in fix_outcomes if row.get("event_id")
    }
    validated_fixed_count = sum(
        1
        for row in fix_outcomes
        if _is_validated_fixed_outcome(row)
    )
    fixed_without_validation_count = sum(
        1
        for row in fix_outcomes
        if row.get("decision") == "fixed" and not _is_validated_fixed_outcome(row)
    )
    missing_event_link_count = sum(
        1 for row in fix_outcomes if row.get("event_lookup_status") == "missing_from_lake"
    )
    unresolved_observed_count = sum(
        1
        for event in events
        if not _is_backfill_candidate_event(event)
        and str(event.get("event_id", "")) not in event_ids_with_fix_outcomes
        and event.get("outcome_status") not in {"fixed", "accepted_risk", "duplicate", "rejected"}
    )
    private_origin = sum(
        1
        for event in events
        if event.get("source_visibility") in {"private", "internal", "restricted", "unknown"}
    )
    latest_backfill_wave: dict[str, Any] = {}
    latest_path = hub_root / BACKFILL_RUNS_DIR / "latest.json"
    if latest_path.exists():
        try:
            latest_backfill_wave = json.loads(latest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            latest_backfill_wave = {"read_error": "latest backfill wave is unreadable"}
    report = {
        "generated_at": utc_now(),
        "event_count": len(events),
        "observed_exception_count": observed_exception_count,
        "backfill_candidate_count": backfill_candidate_count,
        "reviewed_exception_count": reviewed_exception_count,
        "evidence_quality": {
            "observed_exception_count": observed_exception_count,
            "backfill_candidate_count": backfill_candidate_count,
            "reviewed_exception_count": reviewed_exception_count,
            "fix_outcome_count": len(fix_outcomes),
            "validated_fixed_count": validated_fixed_count,
            "fixed_without_validation_count": fixed_without_validation_count,
            "backfill_boundary": (
                "Backfill candidates are path/name metadata only and cannot feed "
                "learning promotion until source-reviewed or human-confirmed."
            ),
            "fix_outcome_boundary": (
                "Fix outcomes are append-only candidate metadata. Only fixed outcomes "
                "with validation_status=validated, validation_refs, regression_test_refs, "
                "and event_lookup_status=found_in_lake count as validated fixes; they "
                "still do not override source-repo authority."
            ),
        },
        "fix_outcome_count": len(fix_outcomes),
        "validated_fixed_count": validated_fixed_count,
        "fixed_without_validation_count": fixed_without_validation_count,
        "fix_outcome_missing_event_link_count": missing_event_link_count,
        "events_with_fix_outcomes_count": len(event_ids_with_fix_outcomes),
        "unresolved_observed_without_fix_outcome_count": unresolved_observed_count,
        "private_or_unknown_origin_count": private_origin,
        "by_event_type": dict(sorted(by_type.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_taxonomy_dimension": by_taxonomy_dimension,
        "by_source_repo": dict(sorted(by_repo.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "fix_outcomes_by_decision": dict(sorted(fix_by_decision.items())),
        "fix_outcomes_by_validation_status": dict(sorted(fix_by_validation.items())),
        "latest_backfill_wave": latest_backfill_wave,
        "input_hashes": _exception_report_input_hashes(hub_root),
        "lake_path": LAKE_PATH.as_posix(),
        "fix_outcomes_path": FIX_OUTCOME_PATH.as_posix(),
        "quarantine_path": QUARANTINE_DIR.as_posix(),
        "authority_boundary": (
            "Exception records are candidate evidence. They store safe metadata and pointers, "
            "not raw logs, secrets, private rows, tool transcripts, or source authority."
        ),
    }
    report_path = hub_root / REPORT_JSON
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    lines = [
        "# Exceptions Lake Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Events: {report['event_count']}",
        f"- Observed/non-backfill exceptions: {observed_exception_count}",
        f"- Path-signal backfill candidates: {backfill_candidate_count}",
        f"- Reviewed observed exceptions: {reviewed_exception_count}",
        f"- Fix outcomes: {len(fix_outcomes)}",
        f"- Validated fixed outcomes: {validated_fixed_count}",
        f"- Fixed-without-validation outcomes: {fixed_without_validation_count}",
        f"- Fix outcomes missing event link: {missing_event_link_count}",
        f"- Observed exceptions without fix outcome: {unresolved_observed_count}",
        f"- Private/internal/restricted/unknown origin: {private_origin}",
        f"- Lake: `{LAKE_PATH.as_posix()}`",
        f"- Fix outcomes: `{FIX_OUTCOME_PATH.as_posix()}`",
        f"- Quarantine: `{QUARANTINE_DIR.as_posix()}`",
        *(
            [
                f"- Latest backfill stopped: `{latest_backfill_wave.get('stopped_reason', '')}`",
                f"- Latest backfill scanned files: {latest_backfill_wave.get('scanned_file_count', 0)}",
                f"- Latest backfill created events: {latest_backfill_wave.get('created_count', 0)}",
            ]
            if latest_backfill_wave
            else []
        ),
        "",
        "## By Event Type",
        "",
    ]
    for event_type, count in sorted(by_type.items()):
        lines.append(f"- `{event_type}`: {count}")
    lines.extend(["", "## By Category", ""])
    for category, count in sorted(by_category.items()):
        lines.append(f"- `{category}`: {count}")
    lines.extend(["", "## By Taxonomy Dimension", ""])
    lines.append(
        "Taxonomy dimensions are analytic groupings for triage and learning routes; "
        "they do not prove source truth or promote backfill candidates."
    )
    for axis in TAXONOMY_AXIS_KEYS:
        lines.extend(["", f"### {axis}", ""])
        for value, count in by_taxonomy_dimension.get(axis, {}).items():
            lines.append(f"- `{value}`: {count}")
    lines.extend(["", "## Fix Outcomes", ""])
    lines.append(
        "Fix outcomes are candidate metadata. Validated fixes require validation refs "
        "and still do not override source-repo authority."
    )
    lines.extend(["", "### By Decision", ""])
    for decision, count in sorted(fix_by_decision.items()):
        lines.append(f"- `{decision}`: {count}")
    lines.extend(["", "### By Validation Status", ""])
    for status, count in sorted(fix_by_validation.items()):
        lines.append(f"- `{status}`: {count}")
    (hub_root / REPORT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _exception_report_input_hashes(hub_root: Path) -> dict[str, str]:
    refs = [
        LAKE_PATH,
        FIX_OUTCOME_PATH,
        EXCEPTION_EVENT_TYPE_REGISTRY,
        EXCEPTION_LEARNING_METHODOLOGY,
    ]
    return {
        ref.as_posix(): (
            f"sha256:{sha256_file(hub_root / ref)}" if (hub_root / ref).exists() else "missing"
        )
        for ref in refs
    }


def _exception_learning_queue_input_hashes(hub_root: Path) -> dict[str, str]:
    refs = [
        EXCEPTION_EVENT_TYPE_REGISTRY,
        EXCEPTION_LEARNING_METHODOLOGY,
        LAKE_PATH,
        FIX_OUTCOME_PATH,
        Path("src") / "digital_asset_directory" / "exceptions_lake.py",
    ]
    hashes: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parents[2]
    for ref in refs:
        path = hub_root / ref
        if not path.exists() and ref.parts[:1] == ("src",):
            path = repo_root / ref
        hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}" if path.exists() else "missing"
    return hashes


def _exception_learning_status(
    *,
    observed_count: int,
    backfill_count: int,
    validated_fix_count: int,
    fixed_without_validation_count: int,
    unresolved_observed_count: int,
    public_release_required_count: int,
    sample_below_threshold: bool,
) -> tuple[str, list[str], str]:
    blockers: list[str] = []
    if fixed_without_validation_count:
        blockers.append("fixed outcome lacks validated status, validation refs, or regression evidence")
    if unresolved_observed_count:
        blockers.append("observed exception lacks validated fix outcome")
    if backfill_count:
        blockers.append("same event-type cluster includes backfill path-signal candidates")
    if public_release_required_count:
        blockers.append("non-public origin evidence needs human release before public-facing reuse")
    if unresolved_observed_count:
        return (
            "needs_fix_outcome",
            blockers,
            "Ask source repo or owner to record a fix outcome, accepted risk, or rejection.",
        )
    if fixed_without_validation_count:
        return (
            "needs_fix_validation",
            blockers,
            "Add validation refs and regression evidence before learning from this fix.",
        )
    if public_release_required_count:
        return (
            "needs_human_release",
            blockers,
            "Record human release before public-facing reuse of non-public-origin evidence.",
        )
    if backfill_count and not observed_count:
        blockers.append("backfill path-signal candidates are not source-reviewed incidents")
        return (
            "needs_source_review",
            blockers,
            "Review source context or ask source repo to confirm before learning promotion.",
        )
    if backfill_count:
        return (
            "needs_source_review",
            blockers,
            "Review or split backfill path-signal candidates before learning from this cluster.",
        )
    if sample_below_threshold:
        return (
            "needs_more_evidence",
            blockers,
            "Keep counts and examples until the comparable-event threshold is met.",
        )
    if validated_fix_count and observed_count:
        return (
            "validated_fix_review_candidate",
            blockers,
            "Review validated fix evidence and decide whether to promote a bounded lesson.",
        )
    return ("watch_only", blockers, "Keep counts only until stronger evidence exists.")


def write_exception_learning_queue(
    hub_root: Path,
    *,
    output: Path | None = None,
    sample_size_threshold: int = 10,
) -> dict[str, Any]:
    """Write a candidate learning queue from exception events and fix outcomes.

    The queue is deliberately conservative: backfill-only clusters are review
    candidates, not lessons, and validated fixes are required before a cluster can
    become a candidate lesson.
    """
    events = load_lake_events(hub_root)
    fix_outcomes = load_fix_outcomes(hub_root)
    taxonomy_by_type = event_type_taxonomy_dimensions(hub_root)
    category_by_type = event_type_categories(hub_root)
    fix_outcomes_by_event: dict[str, list[dict[str, Any]]] = {}
    for outcome in fix_outcomes:
        event_id = str(outcome.get("event_id") or "")
        if event_id:
            fix_outcomes_by_event.setdefault(event_id, []).append(outcome)

    clusters: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event_type") or "unknown")
        cluster = clusters.setdefault(
            event_type,
            {
                "event_type": event_type,
                "category": category_by_type.get(event_type, "unknown"),
                "taxonomy_dimensions": taxonomy_by_type.get(
                    event_type,
                    _unknown_taxonomy_dimensions(),
                ),
                "event_count": 0,
                "observed_count": 0,
                "backfill_candidate_count": 0,
                "validated_fix_count": 0,
                "fixed_without_validation_count": 0,
                "unresolved_observed_count": 0,
                "reviewed_exception_count": 0,
                "public_release_required_count": 0,
                "source_repo_count": 0,
                "source_repos": set(),
                "source_visibility_counts": Counter(),
                "severity_counts": Counter(),
                "example_event_ids": [],
                "validated_fix_ids": [],
            },
        )
        cluster["event_count"] += 1
        cluster["source_repos"].add(str(event.get("source_repo") or "unknown"))
        cluster["source_repo_count"] = len(cluster["source_repos"])
        source_visibility = str(event.get("source_visibility") or "unknown")
        cluster["source_visibility_counts"][source_visibility] += 1
        cluster["severity_counts"][str(event.get("severity") or "unknown")] += 1
        public_release = event.get("public_release") if isinstance(event.get("public_release"), dict) else {}
        human_release_id = str(public_release.get("human_release_id") or "").strip()
        if source_visibility in {"private", "internal", "restricted", "unknown"} and not human_release_id:
            cluster["public_release_required_count"] += 1
        if len(cluster["example_event_ids"]) < 5:
            cluster["example_event_ids"].append(str(event.get("event_id") or ""))
        event_fix_outcomes = fix_outcomes_by_event.get(str(event.get("event_id") or ""), [])
        validated_fixes = [row for row in event_fix_outcomes if _is_validated_fixed_outcome(row)]
        unvalidated_fixes = [
            row
            for row in event_fix_outcomes
            if row.get("decision") == "fixed" and not _is_validated_fixed_outcome(row)
        ]
        cluster["validated_fix_count"] += len(validated_fixes)
        cluster["fixed_without_validation_count"] += len(unvalidated_fixes)
        for row in validated_fixes:
            if len(cluster["validated_fix_ids"]) < 5:
                cluster["validated_fix_ids"].append(str(row.get("fix_id") or ""))
        if _is_backfill_candidate_event(event):
            cluster["backfill_candidate_count"] += 1
        else:
            cluster["observed_count"] += 1
            if event.get("review_status") in {"triaged", "reviewed", "promoted"}:
                cluster["reviewed_exception_count"] += 1
            if not event_fix_outcomes and event.get("outcome_status") not in {
                "fixed",
                "accepted_risk",
                "duplicate",
                "rejected",
            }:
                cluster["unresolved_observed_count"] += 1

    queue_counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for cluster in clusters.values():
        sample_below_threshold = (
            int(cluster["observed_count"]) + int(cluster["backfill_candidate_count"])
        ) < sample_size_threshold
        status, blockers, next_action = _exception_learning_status(
            observed_count=int(cluster["observed_count"]),
            backfill_count=int(cluster["backfill_candidate_count"]),
            validated_fix_count=int(cluster["validated_fix_count"]),
            fixed_without_validation_count=int(cluster["fixed_without_validation_count"]),
            unresolved_observed_count=int(cluster["unresolved_observed_count"]),
            public_release_required_count=int(cluster["public_release_required_count"]),
            sample_below_threshold=sample_below_threshold,
        )
        if sample_below_threshold:
            blockers.append(
                f"sample size below comparable-event threshold N={sample_size_threshold}; counts only"
            )
        queue_counts[status] += 1
        severity_counts = dict(sorted(cluster["severity_counts"].items()))
        source_visibility_counts = dict(sorted(cluster["source_visibility_counts"].items()))
        row = {
            "event_type": cluster["event_type"],
            "category": cluster["category"],
            "taxonomy_dimensions": cluster["taxonomy_dimensions"],
            "event_count": cluster["event_count"],
            "observed_count": cluster["observed_count"],
            "backfill_candidate_count": cluster["backfill_candidate_count"],
            "reviewed_exception_count": cluster["reviewed_exception_count"],
            "validated_fix_count": cluster["validated_fix_count"],
            "fixed_without_validation_count": cluster["fixed_without_validation_count"],
            "unresolved_observed_count": cluster["unresolved_observed_count"],
            "public_release_required_count": cluster["public_release_required_count"],
            "source_repo_count": cluster["source_repo_count"],
            "source_visibility_counts": source_visibility_counts,
            "severity_counts": severity_counts,
            "learning_status": status,
            "promotion_blockers": sorted(set(blockers)),
            "recommended_next_action": next_action,
            "example_event_ids": [item for item in cluster["example_event_ids"] if item],
            "validated_fix_ids": [item for item in cluster["validated_fix_ids"] if item],
        }
        rows.append(row)
    status_rank = {
        "validated_fix_review_candidate": 0,
        "needs_fix_outcome": 1,
        "needs_fix_validation": 2,
        "needs_source_review": 3,
        "needs_human_release": 4,
        "needs_more_evidence": 5,
        "watch_only": 6,
    }
    rows.sort(
        key=lambda row: (
            status_rank.get(str(row["learning_status"]), 9),
            -int(row["observed_count"]),
            -int(row["backfill_candidate_count"]),
            str(row["event_type"]),
        )
    )
    report = {
        "generated_at": utc_now(),
        "report_id": "dad:exception-learning-queue",
        "input_hashes": _exception_learning_queue_input_hashes(hub_root),
        "event_count": len(events),
        "fix_outcome_count": len(fix_outcomes),
        "cluster_count": len(rows),
        "sample_size_threshold": sample_size_threshold,
        "queue_counts": dict(sorted(queue_counts.items())),
        "learning_queue": rows,
        "promotion_policy_boundary": (
            "This queue is candidate evidence. A clean cluster with validated fixes "
            "may enter lesson review, but it does not become a global rule, harness, "
            "or repo instruction without human review. Backfill-only and mixed "
            "backfill clusters are path-signal review candidates and cannot promote "
            "learning."
        ),
    }
    output_path = hub_root / (output or LEARNING_QUEUE_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = output_path.with_suffix(".md") if output else hub_root / LEARNING_QUEUE_MD
    lines = [
        "# Exception Learning Queue",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Events: {report['event_count']}",
        f"- Fix outcomes: {report['fix_outcome_count']}",
        f"- Event-type clusters: {report['cluster_count']}",
        f"- Sample-size threshold: N={sample_size_threshold}",
        "",
        "Boundary: candidate evidence only. Clean validated-fix clusters can enter "
        "lesson review; backfill-only or mixed backfill clusters need source review "
        "and cannot promote learning.",
        "",
        "## Queue Counts",
        "",
    ]
    lines.extend(f"- `{status}`: {count}" for status, count in report["queue_counts"].items())
    lines.extend(["", "## Clusters", ""])
    lines.append("| Event Type | Status | Observed | Backfill | Validated Fixes | Learning Route | Next Action |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- | --- |")
    for row in rows:
        dimensions = row["taxonomy_dimensions"]
        lines.append(
            "| "
            + f"`{row['event_type']}` | `{row['learning_status']}` | "
            + f"{row['observed_count']} | {row['backfill_candidate_count']} | "
            + f"{row['validated_fix_count']} | `{dimensions.get('learning_route', 'unknown')}` | "
            + f"{row['recommended_next_action']} |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _copy_learning_check_contracts(source_hub: Path, target_hub: Path) -> None:
    for ref in [
        Path("registry") / "exception-event-type-registry.json",
        Path("registry") / "exception-learning-methodology.json",
    ]:
        source = source_hub / ref
        target = target_hub / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _write_learning_check_contract(
    repo: Path,
    *,
    repo_id: str,
    visibility: str,
    public_facing: bool,
) -> None:
    contract = repo / ".digital-asset" / "dad-integration.json"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        json_dumps(
            {
                "repo_id": repo_id,
                "visibility": visibility,
                "public_facing": public_facing,
            },
            pretty=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _learning_case_repo(case: dict[str, Any], workspace: Path) -> Path:
    repo_config = case.get("repo") if isinstance(case.get("repo"), dict) else {}
    repo_id = str(repo_config.get("repo_id") or case["case_id"])
    repo = workspace / _slug(repo_id)
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    _write_learning_check_contract(
        repo,
        repo_id=repo_id,
        visibility=str(repo_config.get("visibility") or "unknown"),
        public_facing=bool(repo_config.get("public_facing", False)),
    )
    return repo


def _record_learning_check_event(
    hub_root: Path,
    repo: Path,
    spec: dict[str, Any],
) -> dict[str, Any]:
    return record_exception_event(
        hub_root,
        repo,
        event_type=str(spec.get("event_type") or "other"),
        summary=str(spec.get("summary") or spec.get("event_key") or "Synthetic exception event."),
        stage=str(spec.get("stage") or "midflight"),
        severity=str(spec.get("severity") or "medium"),
        capture_contract=str(spec.get("capture_contract") or "failed_command"),
        agent=str(spec.get("agent") or "codex"),
        source_visibility=str(spec.get("source_visibility") or "unknown"),
        command=[str(item) for item in spec.get("command", []) or []],
        exit_code=spec.get("exit_code"),
        duration_ms=spec.get("duration_ms"),
        context_refs=[str(item) for item in spec.get("context_refs", []) or []],
        validation_refs=[str(item) for item in spec.get("validation_refs", []) or []],
        asset_refs=[str(item) for item in spec.get("asset_refs", []) or []],
        harness_refs=[str(item) for item in spec.get("harness_refs", []) or []],
        trace_refs=[str(item) for item in spec.get("trace_refs", []) or []],
    )


def _record_learning_check_fix(
    hub_root: Path,
    repo: Path,
    event_by_key: dict[str, dict[str, Any]],
    spec: dict[str, Any],
) -> None:
    event_key = str(spec.get("event_key") or "")
    event = event_by_key.get(event_key, {})
    event_id = str(event.get("event", {}).get("event_id") or spec.get("event_id") or "")
    fix_kwargs = {
        "event_id": event_id,
        "decision": str(spec.get("decision") or "fixed"),
        "summary": str(spec.get("summary") or "Synthetic fix outcome."),
        "recorded_by": str(spec.get("recorded_by") or "codex"),
        "validation_refs": [str(item) for item in spec.get("validation_refs", []) or []],
        "regression_test_refs": [
            str(item) for item in spec.get("regression_test_refs", []) or []
        ],
        "fix_refs": [str(item) for item in spec.get("fix_refs", []) or []],
        "asset_refs": [str(item) for item in spec.get("asset_refs", []) or []],
        "lesson_refs": [str(item) for item in spec.get("lesson_refs", []) or []],
        "owner_authority": str(spec.get("owner_authority") or "repo"),
        "canonical_event_id": str(spec.get("canonical_event_id") or ""),
        "expiry": str(spec.get("expiry") or ""),
        "remaining_risks": [str(item) for item in spec.get("remaining_risks", []) or []],
        "review_status": str(spec.get("review_status") or "candidate"),
    }
    if spec.get("append_direct"):
        record = build_exception_fix_outcome(hub_root, repo, **fix_kwargs)
        mutations = spec.get("mutations") if isinstance(spec.get("mutations"), dict) else {}
        record.update(mutations)
        append_jsonl(hub_root / FIX_OUTCOME_PATH, record)
        return
    record_exception_fix_outcome(hub_root, repo, **fix_kwargs)


def _queue_rows_by_event_type(queue_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("event_type")): row
        for row in queue_report.get("learning_queue", [])
        if isinstance(row, dict) and row.get("event_type")
    }


def _substring_checks(actual_values: list[str], expected_substrings: list[str]) -> bool:
    return all(
        any(substring in value for value in actual_values)
        for substring in expected_substrings
    )


def _validate_learning_readiness_scenarios(
    hub_root: Path,
    scenarios: dict[str, Any],
    scenarios_path: Path,
) -> None:
    schema = _load_json(_learning_readiness_scenarios_schema_path(hub_root))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    try:
        validator_cls(schema).validate(scenarios)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        location = path or "<scenario-set>"
        raise ValueError(
            f"Exception learning-readiness scenario validation failed at {location}: "
            f"{exc.message}"
        ) from exc

    case_ids: list[str] = []
    for index, case in enumerate(scenarios.get("cases", [])):
        case_id = str(case.get("case_id") or "").strip()
        case_ids.append(case_id)
        expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
        assertion_keys = {
            "status_by_event_type",
            "blocker_substrings_by_event_type",
            "row_fields_by_event_type",
            "queue_counts",
            "quarantine_event_types",
        }
        if not any(expected.get(key) for key in assertion_keys):
            raise ValueError(
                "Exception learning-readiness scenario "
                f"{case_id or index} in {scenarios_path} has no expected assertions."
            )
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicates:
        raise ValueError(
            "Exception learning-readiness scenarios contain duplicate case_id values: "
            + ", ".join(duplicates)
        )


def _evaluate_learning_check_case(
    source_hub: Path,
    case: dict[str, Any],
    *,
    sample_size_threshold: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dad-exception-learning-check-") as tmp:
        workspace = Path(tmp)
        hub = workspace / "hub"
        _copy_learning_check_contracts(source_hub, hub)
        repo = _learning_case_repo(case, workspace)
        event_by_key: dict[str, dict[str, Any]] = {}
        for event_spec in case.get("events", []) or []:
            if not isinstance(event_spec, dict):
                continue
            event_key = str(event_spec.get("event_key") or len(event_by_key))
            event_by_key[event_key] = _record_learning_check_event(hub, repo, event_spec)
        collect_exception_events(hub, repo)
        for fix_spec in case.get("fix_outcomes", []) or []:
            if isinstance(fix_spec, dict):
                _record_learning_check_fix(hub, repo, event_by_key, fix_spec)
        collect_exception_fix_outcomes(hub, repo)
        queue = write_exception_learning_queue(
            hub,
            output=workspace / "learning-queue.json",
            sample_size_threshold=sample_size_threshold,
        )
        rows_by_type = _queue_rows_by_event_type(queue)
        expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
        status_expected = {
            str(key): str(value)
            for key, value in (expected.get("status_by_event_type") or {}).items()
        }
        blocker_expected = {
            str(key): [str(item) for item in value or []]
            for key, value in (expected.get("blocker_substrings_by_event_type") or {}).items()
        }
        row_fields_expected = {
            str(key): value
            for key, value in (expected.get("row_fields_by_event_type") or {}).items()
            if isinstance(value, dict)
        }
        comparisons: dict[str, bool] = {}
        for event_type, expected_status in status_expected.items():
            actual_status = str(rows_by_type.get(event_type, {}).get("learning_status") or "")
            comparisons[f"status:{event_type}"] = actual_status == expected_status
        for event_type, substrings in blocker_expected.items():
            blockers = [
                str(item)
                for item in rows_by_type.get(event_type, {}).get("promotion_blockers", [])
            ]
            comparisons[f"blockers:{event_type}"] = _substring_checks(blockers, substrings)
        for event_type, fields in row_fields_expected.items():
            row = rows_by_type.get(event_type, {})
            for field, expected_value in fields.items():
                comparisons[f"row:{event_type}:{field}"] = row.get(field) == expected_value
        if isinstance(expected.get("queue_counts"), dict):
            comparisons["queue_counts"] = queue.get("queue_counts") == expected["queue_counts"]
        quarantine_expectations = expected.get("quarantine_event_types") or []
        if quarantine_expectations:
            quarantine_text = ""
            quarantine_dir = hub / QUARANTINE_DIR
            if quarantine_dir.exists():
                quarantine_text = "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in quarantine_dir.glob("*.jsonl")
                )
            for event_type in quarantine_expectations:
                comparisons[f"quarantine:{event_type}"] = str(event_type) in quarantine_text
        passed = bool(comparisons) and all(comparisons.values())
        actual_rows = {
            event_type: {
                "learning_status": row.get("learning_status"),
                "promotion_blockers": row.get("promotion_blockers", []),
                "observed_count": row.get("observed_count"),
                "backfill_candidate_count": row.get("backfill_candidate_count"),
                "validated_fix_count": row.get("validated_fix_count"),
                "fixed_without_validation_count": row.get("fixed_without_validation_count"),
                "public_release_required_count": row.get("public_release_required_count"),
                "source_visibility_counts": row.get("source_visibility_counts", {}),
            }
            for event_type, row in rows_by_type.items()
        }
        return {
            "case_id": str(case.get("case_id") or case.get("scenario_id") or "unknown"),
            "description": str(case.get("description") or ""),
            "passed": passed,
            "comparisons": comparisons,
            "expected": expected,
            "actual_rows_by_event_type": actual_rows,
            "queue_counts": queue.get("queue_counts", {}),
        }


def _learning_readiness_scenario_ref(hub_root: Path, scenarios_path: Path) -> str:
    try:
        return scenarios_path.resolve().relative_to(hub_root.resolve()).as_posix()
    except (OSError, ValueError):
        path_hash = sha256_bytes(str(scenarios_path.resolve()).encode("utf-8"))[:16]
        return f"external-scenario:{path_hash}:{scenarios_path.name}"


def _learning_readiness_input_hashes(hub_root: Path, scenarios_path: Path) -> dict[str, str]:
    refs = [
        Path("registry") / "exception-event-type-registry.json",
        Path("registry") / "exception-learning-methodology.json",
        Path("schemas") / "exception-event.schema.json",
        Path("schemas") / "exception-fix-outcome.schema.json",
        Path("schemas") / "exception-event-type-registry.schema.json",
        Path("schemas") / "exception-learning-methodology.schema.json",
        LEARNING_READINESS_SCENARIOS_SCHEMA,
        Path("schemas") / "coding-harness.schema.json",
        Path("schemas") / "coding-harness-eval.schema.json",
        Path("src") / "digital_asset_directory" / "exceptions_lake.py",
        Path("src") / "digital_asset_directory" / "cli.py",
        Path("assets")
        / "coding-harnesses"
        / "exception-learning-readiness"
        / "harness.json",
        Path("assets")
        / "coding-harnesses"
        / "exception-learning-readiness"
        / "tests-or-evals"
        / "minimum-eval.json",
    ]
    hashes: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parents[2]
    for ref in refs:
        path = hub_root / ref
        if not path.exists() and ref.parts[:1] in {
            ("src",),
            ("schemas",),
            ("assets",),
        }:
            path = repo_root / ref
        if path.exists() and path.is_file():
            hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}"
    if scenarios_path.exists() and scenarios_path.is_file():
        hashes[_learning_readiness_scenario_ref(hub_root, scenarios_path)] = (
            f"sha256:{sha256_file(scenarios_path)}"
        )
    return hashes


def evaluate_exception_learning_readiness_scenarios(
    hub_root: Path,
    scenarios_path: Path,
    *,
    output: Path | None = None,
    sample_size_threshold: int | None = None,
) -> dict[str, Any]:
    """Run synthetic learning-readiness cases against the exception learning queue."""
    scenarios = _load_json(scenarios_path)
    if not isinstance(scenarios, dict):
        raise ValueError("Exception learning-readiness scenario file must contain a JSON object.")
    _validate_learning_readiness_scenarios(hub_root, scenarios, scenarios_path)
    effective_threshold = int(
        sample_size_threshold
        if sample_size_threshold is not None
        else scenarios.get("sample_size_threshold", 10)
    )
    if effective_threshold < 1:
        raise ValueError("sample_size_threshold must be at least 1.")
    cases = [case for case in scenarios.get("cases", []) if isinstance(case, dict)]
    results = [
        _evaluate_learning_check_case(
            hub_root,
            case,
            sample_size_threshold=effective_threshold,
        )
        for case in cases
    ]
    failed = [case for case in results if not case["passed"]]
    report = {
        "generated_at": utc_now(),
        "report_id": "dad:exception-learning-readiness-check",
        "scenario_set_id": scenarios.get("scenario_set_id", scenarios_path.stem),
        "scenario_count": len(results),
        "passed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "sample_size_threshold": effective_threshold,
        "scenario_path_ref": _learning_readiness_scenario_ref(hub_root, scenarios_path),
        "input_hashes": _learning_readiness_input_hashes(hub_root, scenarios_path),
        "cases": results,
        "authority_boundary": (
            "This generated report checks only that supplied synthetic learning-queue "
            "cases produce expected conservative statuses. It does not promote a "
            "lesson, prove real repo completeness, or override source authority."
        ),
    }
    output_path = hub_root / (output or LEARNING_READINESS_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = output_path.with_suffix(".md") if output else hub_root / LEARNING_READINESS_MD
    lines = [
        "# Exception Learning Readiness Check",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Scenario set: `{report['scenario_set_id']}`",
        f"- Scenarios: {report['scenario_count']}",
        f"- Passed: {report['passed_count']}",
        f"- Failed: {report['failed_count']}",
        "",
        "Boundary: synthetic generated evidence only. This check gives evidence "
        "against false-green learning-queue readiness; it does not promote "
        "lessons or prove real repo completeness.",
        "",
        "## Cases",
        "",
    ]
    lines.append("| Case | Result | Expected Statuses |")
    lines.append("| --- | --- | --- |")
    for case in results:
        expected_statuses = (case.get("expected") or {}).get("status_by_event_type", {})
        lines.append(
            "| "
            + f"`{case['case_id']}` | {'passed' if case['passed'] else 'failed'} | "
            + f"`{expected_statuses}` |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def exception_lake_paths() -> dict[str, str]:
    return {
        "repo_outbox": EXCEPTION_OUTBOX.as_posix(),
        "raw_repo_events": RAW_EXCEPTION_DIR.as_posix(),
        "canonical_lake": LAKE_PATH.as_posix(),
        "quarantine": QUARANTINE_DIR.as_posix(),
        "fix_outcomes": FIX_OUTCOME_PATH.as_posix(),
        "learning_queue_json": LEARNING_QUEUE_JSON.as_posix(),
        "learning_queue_markdown": LEARNING_QUEUE_MD.as_posix(),
        "learning_readiness_json": LEARNING_READINESS_JSON.as_posix(),
        "learning_readiness_markdown": LEARNING_READINESS_MD.as_posix(),
        "report_json": REPORT_JSON.as_posix(),
        "report_markdown": REPORT_MD.as_posix(),
    }
