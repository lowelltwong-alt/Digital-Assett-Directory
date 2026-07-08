from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from .ids import stable_id
from .models import MailMessageRecord
from .transport import data_path
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
FIX_OUTCOME_REQUESTS_JSON = Path("processed") / "reports" / "exception_fix_outcome_requests.json"
FIX_OUTCOME_REQUESTS_MD = Path("processed") / "reports" / "exception_fix_outcome_requests.md"
FIX_OUTCOME_REQUESTS_STAGED = (
    Path("processed") / "mail" / "staged" / "fix_outcome_requests.jsonl"
)
BACKFILL_REVIEW_QUEUE_JSON = Path("processed") / "reports" / "exception_backfill_review_queue.json"
BACKFILL_REVIEW_QUEUE_MD = Path("processed") / "reports" / "exception_backfill_review_queue.md"
BACKFILL_REFRESH_PLAN_JSON = (
    Path("processed") / "reports" / "exception_backfill_classifier_refresh_plan.json"
)
BACKFILL_REFRESH_PLAN_MD = (
    Path("processed") / "reports" / "exception_backfill_classifier_refresh_plan.md"
)
BACKFILL_REVIEW_DECISIONS = (
    Path("processed") / "exceptions" / "review-queue" / "backfill_review_decisions.jsonl"
)
SOURCE_PACKET_OPPORTUNITIES_JSON = (
    Path("processed") / "reports" / "exception_source_packet_opportunities.json"
)
SOURCE_PACKET_OPPORTUNITIES_MD = (
    Path("processed") / "reports" / "exception_source_packet_opportunities.md"
)
SOURCE_PACKET_REQUESTS_JSON = Path("processed") / "reports" / "exception_source_packet_requests.json"
SOURCE_PACKET_REQUESTS_MD = Path("processed") / "reports" / "exception_source_packet_requests.md"
SOURCE_PACKET_REQUESTS_STAGED = (
    Path("processed") / "mail" / "staged" / "source_packet_requests.jsonl"
)
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


def exception_data_path(hub_root: Path, relative_path: Path) -> Path:
    parts = relative_path.parts
    if parts[:2] == ("raw", "exceptions"):
        return data_path(hub_root, "raw_exceptions").joinpath(*parts[2:])
    if parts[:2] == ("processed", "exceptions"):
        return data_path(hub_root, "exceptions").joinpath(*parts[2:])
    if parts[:2] == ("processed", "reports"):
        return data_path(hub_root, "central_reports").joinpath(*parts[2:])
    if parts[:2] == ("processed", "mail"):
        return data_path(hub_root, "central_mail").joinpath(*parts[2:])
    raise ValueError(f"Unsupported exception data-plane path: {relative_path}")


def _default_or_requested_path(
    hub_root: Path,
    output: Path | None,
    default_relative_path: Path,
) -> Path:
    if output is not None:
        if output.is_absolute():
            return output
        if output.parts[:2] in {
            ("raw", "exceptions"),
            ("processed", "exceptions"),
            ("processed", "reports"),
            ("processed", "mail"),
        }:
            return exception_data_path(hub_root, output)
        return hub_root / output
    return exception_data_path(hub_root, default_relative_path)


def _exception_input_ref_path(hub_root: Path, ref: Path) -> Path:
    if ref.parts[:2] in {
        ("raw", "exceptions"),
        ("processed", "exceptions"),
        ("processed", "reports"),
        ("processed", "mail"),
    }:
        return exception_data_path(hub_root, ref)
    return hub_root / ref

SCHEMA_VERSION = "0.1.0"
HARD_ISSUE_LOOKUP_BASIS = (
    "Deterministic candidate lookup over exception events and validated fix outcomes. "
    "Ranking uses event-type/signal matches and token overlap only; it is not confidence, "
    "truth, source authority, or approval to apply a fix."
)
MAX_STRING_CHARS = 1200
MAX_RECORD_BYTES = 16_000
MAX_BACKFILL_EVENTS = 1000
LOCAL_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?:\b[A-Z]:[\\/]|\\\\[A-Za-z0-9_.-]+[\\/]|/Users/|/home/|/var/folders/)"
)
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore (all )?(previous|prior|above) instructions\b"),
    re.compile(r"(?i)\b(system|developer) prompt\b"),
    re.compile(r"(?i)\bexecute (this )?(tool|command)\b"),
    re.compile(r"(?i)\bdo not (tell|show) (the )?(user|developer)\b"),
]
HIDDEN_REASONING_PATTERNS = [
    re.compile(r"(?i)\b(hidden|private|internal) (chain[- ]of[- ]thought|reasoning)\b"),
    re.compile(r"(?i)\b(chain[- ]of[- ]thought|scratchpad) (transcript|notes|dump)\b"),
]
SOURCE_OR_DIFF_PATTERNS = [
    re.compile(r"(?im)^\s*diff --git\b"),
    re.compile(r"(?m)^\s*@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@"),
    re.compile(r"(?im)^\s*```(?:python|py|rust|rs|javascript|js|typescript|ts|go|java|c|cpp|csharp|cs|sql)?\s*$"),
]
SOURCE_LINE_PATTERN = re.compile(
    r"(?m)^\s*(?:"
    r"def\s+\w+\s*\(|class\s+\w+|"
    r"pub\s+(?:async\s+)?fn\s+\w+\s*\(|fn\s+\w+\s*\(|impl(?:\s+|\<)|"
    r"(?:from\s+\S+\s+)?import\s+\S+|use\s+\S+::|"
    r"(?:const|let|var)\s+[$A-Za-z_][\w$]*\s*=|"
    r"return\s+.+[;)]?$"
    r")"
)

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
HARD_ISSUE_LOOKUP_TRIGGER_TERMS = {
    "blocked",
    "blocker",
    "bug",
    "conflict",
    "debug",
    "denied",
    "error",
    "exception",
    "fail",
    "failed",
    "failure",
    "flaky",
    "hard",
    "issue",
    "malformed",
    "non-obvious",
    "os.replace",
    "permission",
    "regression",
    "retry",
    "stale",
    "timeout",
    "unavailable",
    "validation",
    "winerror",
}
HARD_ISSUE_SIGNAL_EVENT_TYPES = {
    "failed_command": {"failed_command", "runtime_exception", "validation_command_missing"},
    "runtime_exception": {"runtime_exception"},
    "permission_denied": {"permission_denied", "runtime_exception", "environment_config_missing"},
    "permission_error": {"permission_denied", "runtime_exception", "environment_config_missing"},
    "stale_report": {"stale_report", "stale_generated_artifact"},
    "stale_generated_artifact": {"stale_report", "stale_generated_artifact"},
    "malformed_jsonl": {"malformed_jsonl", "runtime_exception"},
    "lock_timeout": {"runtime_exception", "command_timeout", "permission_denied"},
    "retry_loop": {"command_timeout", "runtime_exception", "external_service_failure"},
    "test_failure": {"test_failure", "test_timeout", "pytest_performance_hotspot"},
    "tool_unavailable": {"tool_unavailable", "environment_config_missing"},
    "review_finding": {"review_finding", "premortem_failure_story"},
    "artifact_registration_drift": {"artifact_registration_drift", "stale_generated_artifact"},
    "validation_failure": {"schema_validation_failure", "validation_command_missing", "test_failure"},
}
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
        bool(re.search(r"(?:^|[\s\"'(\[])[a-z]:/", normalized))
        or normalized.startswith("/")
        or any(fragment in normalized for fragment in LOCAL_PATH_FRAGMENTS)
    )


READABLE_REPO_RELATIVE_REF_RE = re.compile(
    r"\brepo-relative:(?!sha256:)[^\s,;\"')\]]+",
    re.IGNORECASE,
)
SOURCE_PACKET_SAFE_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,180}$")


def _contains_readable_repo_relative_text(value: str) -> bool:
    return bool(READABLE_REPO_RELATIVE_REF_RE.search(value))


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


def _safe_change_context_value(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    cleaned = _safe_external_ref(str(value).strip())
    return str(cleaned)[:limit]


def _normalize_change_context(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    limits = {
        "change_ref": 240,
        "changed_surface": 160,
        "exception_reason": 600,
        "validation_ref_or_gap": 300,
    }
    normalized: dict[str, str] = {}
    for field, limit in limits.items():
        cleaned = _safe_change_context_value(value.get(field), limit=limit)
        if cleaned:
            normalized[field] = cleaned
    return normalized


def _change_context_from_packet(packet: dict[str, Any]) -> dict[str, str]:
    candidate: dict[str, Any] = {}
    if isinstance(packet.get("change_context"), dict):
        candidate.update(packet["change_context"])
    for field in (
        "change_ref",
        "changed_surface",
        "exception_reason",
        "validation_ref_or_gap",
    ):
        if field in packet:
            candidate[field] = packet[field]
    return _normalize_change_context(candidate)


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
    change_context = json.dumps(record.get("change_context") or {}, sort_keys=True)
    identity = [
        str(record.get("source_repo", "")),
        str(record.get("capture_contract", "")),
        str(record.get("stage", "")),
        str(record.get("event_type", "")),
        _normal(" ".join(str(item) for item in argv or [])),
        _normal("|".join(str(item) for item in record.get("context_refs", []) or [])),
        _normal(str(record.get("error_fingerprint", ""))),
        _normal(change_context),
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
        if any(pattern.search(redacted) for pattern in HIDDEN_REASONING_PATTERNS):
            issues.append("hidden_reasoning_like_payload")
            digest = sha256_bytes(redacted.encode("utf-8"))
            redacted = f"[HIDDEN_REASONING_LIKE_TEXT_REJECTED_SHA256:{digest}]"
        if _looks_like_source_or_diff(redacted):
            issues.append("source_or_diff_like_payload")
            digest = sha256_bytes(redacted.encode("utf-8"))
            redacted = f"[SOURCE_OR_DIFF_LIKE_TEXT_REJECTED_SHA256:{digest}]"
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


def _looks_like_source_or_diff(value: str) -> bool:
    if any(pattern.search(value) for pattern in SOURCE_OR_DIFF_PATTERNS):
        return True
    source_line_count = sum(1 for line in value.splitlines() if SOURCE_LINE_PATTERN.search(line))
    if source_line_count >= 2:
        return True
    return source_line_count == 1 and ("\n" in value or "{" in value or ";" in value)


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
        issue in {
            "long_string",
            "raw_blob_like_multiline_value",
            "source_or_diff_like_payload",
            "table_like_value",
        }
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
    change_context: dict[str, Any] | None = None,
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
    normalized_change_context = _normalize_change_context(change_context)
    if normalized_change_context:
        record["change_context"] = normalized_change_context
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
    if isinstance(record.get("change_context"), dict):
        record["change_context"] = _normalize_change_context(record.get("change_context"))
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
    event_type = str(packet.get("event_type") or packet.get("type") or FALLBACK_EVENT_TYPE)
    command = packet.get("command", {})
    argv = command.get("argv", []) if isinstance(command, dict) else []
    exit_code = command.get("exit_code") if isinstance(command, dict) else None
    duration_ms = command.get("duration_ms") if isinstance(command, dict) else None
    return build_exception_event(
        hub_root,
        repo,
        event_type=event_type,
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
        change_context=_change_context_from_packet(packet)
        if event_type.replace("-", "_") == "code_change_exception"
        else None,
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
    change_context: dict[str, Any] | None = None,
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
        change_context=change_context,
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


def _source_repo_report_key(value: Any) -> str:
    text = str(value or "unknown").strip()
    return text.casefold() if text else "unknown"


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
    lake = exception_data_path(hub_root, LAKE_PATH)
    existing = _existing_events_by_id(lake).get(str(record["event_id"]))
    if existing is not None:
        if _collision_fields(existing) == _collision_fields(record):
            return "duplicate"
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR) / "duplicate_collision_suspect.jsonl",
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
        exception_data_path(hub_root, RAW_EXCEPTION_DIR)
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
    path = exception_data_path(hub_root, FIX_OUTCOME_PATH)
    existing = _existing_fix_outcomes_by_id(path).get(str(record["fix_id"]))
    if existing is not None:
        if _fix_collision_fields(existing) == _fix_collision_fields(record):
            return "duplicate"
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "fix_outcome_duplicate_collision_suspect.jsonl",
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
        exception_data_path(hub_root, RAW_EXCEPTION_DIR)
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
    malformed_path = (
        exception_data_path(hub_root, QUARANTINE_DIR) / "fix_outcome_malformed_jsonl.jsonl"
    )
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
    quarantine_path = (
        exception_data_path(hub_root, QUARANTINE_DIR) / f"{_slug(repo_id)}-fix-outcomes.jsonl"
    )
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
    malformed_path = exception_data_path(hub_root, QUARANTINE_DIR) / "malformed_jsonl.jsonl"
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
    quarantine_path = exception_data_path(hub_root, QUARANTINE_DIR) / f"{_slug(repo_id)}.jsonl"
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
                append_jsonl(
                    exception_data_path(hub_root, QUARANTINE_DIR) / "backfill.jsonl",
                    screened,
                )
                continue
            try:
                validate_exception_event_record(hub_root, screened)
            except ValueError as exc:
                screened["review_status"] = "quarantined"
                screened["screening"]["issues"] = ["schema_validation_failed"]
                append_jsonl(
                    exception_data_path(hub_root, QUARANTINE_DIR) / "backfill.jsonl",
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
    latest_run = exception_data_path(hub_root, BACKFILL_RUNS_DIR) / "latest.json"
    latest_run.parent.mkdir(parents=True, exist_ok=True)
    latest_run.write_text(json_dumps(run_record, pretty=True) + "\n", encoding="utf-8")
    append_jsonl(exception_data_path(hub_root, BACKFILL_RUNS_DIR) / "runs.jsonl", run_record)
    report = write_exception_report(hub_root)
    return {
        **run_record,
        "report": report,
    }


def load_lake_events(hub_root: Path) -> list[dict[str, Any]]:
    path = exception_data_path(hub_root, LAKE_PATH)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def load_fix_outcomes(hub_root: Path) -> list[dict[str, Any]]:
    path = exception_data_path(hub_root, FIX_OUTCOME_PATH)
    records, errors = _read_jsonl_with_errors(path)
    for error in errors:
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "fix_outcome_report_malformed_jsonl.jsonl",
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
                exception_data_path(hub_root, QUARANTINE_DIR)
                / "fix_outcome_report_invalid_records.jsonl",
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


def _lookup_tokens(*values: Any) -> set[str]:
    text_parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            text_parts.extend(str(item) for item in value.values())
        elif isinstance(value, (list, tuple, set)):
            text_parts.extend(str(item) for item in value)
        else:
            text_parts.append(str(value))
    text = " ".join(text_parts).lower()
    tokens = {
        token.strip("/\\.:_-")
        for token in re.findall(r"[a-z][a-z0-9_.+-]{1,63}", text)
        if len(token.strip("/\\.:_-")) > 1
    }
    stopwords = {
        "and",
        "are",
        "command",
        "dad",
        "file",
        "files",
        "for",
        "from",
        "into",
        "local",
        "path",
        "paths",
        "repo",
        "repository",
        "run",
        "that",
        "the",
        "this",
        "with",
    }
    return tokens - stopwords


def looks_like_hard_issue_lookup_context(*values: Any) -> bool:
    tokens = _lookup_tokens(*values)
    if tokens & HARD_ISSUE_LOOKUP_TRIGGER_TERMS:
        return True
    text = " ".join(str(value) for value in values if value is not None).lower()
    return any(
        phrase in text
        for phrase in (
            "hard issue",
            "non obvious",
            "non-obvious",
            "test failed",
            "tests failed",
            "validation failed",
            "tool unavailable",
            "permissionerror",
            "permission error",
            "winerror",
        )
    )


def _safe_lookup_text(value: Any, *, max_chars: int = 320) -> tuple[str, int]:
    text = " ".join(str(value or "").split())
    redacted, redaction_count = redact_sensitive_text(text)
    if len(redacted) > max_chars:
        digest = sha256_bytes(redacted.encode("utf-8"))
        redacted = f"{redacted[: max_chars - 28].rstrip()}... sha256:{digest[:16]}"
    return redacted, redaction_count


def _safe_lookup_ref(value: Any) -> tuple[str, int]:
    text, redaction_count = _safe_lookup_text(value, max_chars=240)
    if not text:
        return "", redaction_count
    if LOCAL_ABSOLUTE_PATH_PATTERN.search(text) or _lookup_screening_issues(text):
        return f"ref-sha256:{sha256_bytes(text.encode('utf-8'))}", redaction_count
    return text, redaction_count


def _safe_lookup_refs(values: Any, *, limit: int = 8) -> tuple[list[str], int]:
    refs: list[str] = []
    redactions = 0
    if not isinstance(values, list):
        values = [] if values in (None, "") else [values]
    for value in values[:limit]:
        ref, count = _safe_lookup_ref(value)
        redactions += count
        if ref:
            refs.append(ref)
    return refs, redactions


def _lookup_screening_issues(*values: Any) -> list[str]:
    text = "\n".join(str(value or "") for value in values)
    issues: set[str] = set()
    if not text.strip():
        return []
    if LOCAL_ABSOLUTE_PATH_PATTERN.search(text):
        issues.add("local_absolute_path_hashed")
    if any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS):
        issues.add("prompt_injection_like_text_suppressed")
    if any(pattern.search(text) for pattern in HIDDEN_REASONING_PATTERNS):
        issues.add("hidden_reasoning_reference_suppressed")
    if any(pattern.search(text) for pattern in SOURCE_OR_DIFF_PATTERNS):
        issues.add("source_or_diff_blob_suppressed")
    if SOURCE_LINE_PATTERN.search(text):
        issues.add("source_like_text_suppressed")
    if len([line for line in text.splitlines() if "|" in line]) >= 3:
        issues.add("table_like_payload_suppressed")
    if re.search(r"(?m)^\s*(?:traceback|at\s+\S+\(|file\s+\".+\", line \d+)", text, re.I):
        issues.add("stack_trace_like_text_suppressed")
    return sorted(issues)


def _lookup_query_summary(value: Any, issues: list[str]) -> tuple[str, int]:
    text = " ".join(str(value or "").split())
    if issues:
        return f"text-sha256:{sha256_bytes(text.encode('utf-8'))}", 0
    return _safe_lookup_text(value, max_chars=240)


def _load_lake_events_for_lookup(hub_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records, errors = _read_jsonl_with_errors(exception_data_path(hub_root, LAKE_PATH))
    warnings: list[str] = []
    if errors:
        warnings.append("malformed exception lake rows were skipped during lookup")
    valid_records: list[dict[str, Any]] = []
    for record in records:
        try:
            validate_exception_event_record(hub_root, record)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            warnings.append("invalid exception lake rows were skipped during lookup")
            continue
        valid_records.append(record)
    return valid_records, sorted(set(warnings))


def _load_fix_outcomes_for_lookup(hub_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records, errors = _read_jsonl_with_errors(exception_data_path(hub_root, FIX_OUTCOME_PATH))
    warnings: list[str] = []
    if errors:
        warnings.append("malformed fix-outcome rows were skipped during lookup")
    valid_records: list[dict[str, Any]] = []
    for record in records:
        try:
            validate_exception_fix_outcome_record(hub_root, record)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            warnings.append("invalid fix-outcome rows were skipped during lookup")
            continue
        valid_records.append(record)
    return valid_records, sorted(set(warnings))


def _event_lookup_text(event: dict[str, Any]) -> str:
    command = event.get("command") if isinstance(event.get("command"), dict) else {}
    taxonomy = event.get("taxonomy_dimensions") if isinstance(event.get("taxonomy_dimensions"), dict) else {}
    values: list[Any] = [
        event.get("event_id"),
        event.get("event_type"),
        event.get("capture_contract"),
        event.get("stage"),
        event.get("severity"),
        event.get("safe_summary"),
        event.get("symptoms"),
        event.get("error_fingerprint"),
        event.get("suspected_cause"),
        event.get("task"),
        event.get("context_refs"),
        event.get("validation_refs"),
        event.get("asset_refs"),
        event.get("harness_refs"),
        taxonomy,
        command.get("argv") if isinstance(command, dict) else [],
    ]
    return " ".join(str(value) for value in values if value)


def _fix_lookup_text(outcome: dict[str, Any]) -> str:
    values: list[Any] = [
        outcome.get("fix_id"),
        outcome.get("summary"),
        outcome.get("validation_refs"),
        outcome.get("regression_test_refs"),
        outcome.get("fix_refs"),
        outcome.get("asset_refs"),
        outcome.get("lesson_refs"),
        outcome.get("remaining_risks"),
    ]
    return " ".join(str(value) for value in values if value)


def _expanded_lookup_event_types(signals: Iterable[str], event_types: Iterable[str]) -> set[str]:
    expanded = {str(value).strip() for value in event_types if str(value).strip()}
    for signal in signals:
        key = str(signal).strip().lower().replace("-", "_")
        if not key:
            continue
        mapped = HARD_ISSUE_SIGNAL_EVENT_TYPES.get(key)
        if mapped:
            expanded.update(mapped)
        else:
            expanded.add(key)
    return expanded


def _severity_sort_value(value: Any) -> int:
    return {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}.get(str(value), 0)


def _lookup_fix_summary(outcome: dict[str, Any]) -> tuple[dict[str, Any], int]:
    redactions = 0
    summary, count = _safe_lookup_text(outcome.get("summary"))
    redactions += count
    validation_refs, count = _safe_lookup_refs(outcome.get("validation_refs"))
    redactions += count
    regression_refs, count = _safe_lookup_refs(outcome.get("regression_test_refs"))
    redactions += count
    fix_refs, count = _safe_lookup_refs(outcome.get("fix_refs"))
    redactions += count
    asset_refs, count = _safe_lookup_refs(outcome.get("asset_refs"))
    redactions += count
    lesson_refs, count = _safe_lookup_refs(outcome.get("lesson_refs"))
    redactions += count
    remaining_risks, count = _safe_lookup_refs(outcome.get("remaining_risks"))
    redactions += count
    return (
        {
            "fix_id": outcome.get("fix_id", ""),
            "event_id": outcome.get("event_id", ""),
            "decision": outcome.get("decision", ""),
            "validation_status": outcome.get("validation_status", ""),
            "review_status": outcome.get("review_status", ""),
            "summary": summary,
            "validation_refs": validation_refs,
            "regression_test_refs": regression_refs,
            "fix_refs": fix_refs,
            "asset_refs": asset_refs,
            "lesson_refs": lesson_refs,
            "remaining_risks": remaining_risks,
            "owner_authority": outcome.get("owner_authority", ""),
        },
        redactions,
    )


def hard_issue_lookup(
    hub_root: Path,
    *,
    query: str = "",
    signals: Iterable[str] | None = None,
    event_types: Iterable[str] | None = None,
    command: Iterable[str] | None = None,
    path_refs: Iterable[str] | None = None,
    limit: int = 5,
    include_backfill: bool = False,
    target_public_facing: bool = False,
) -> dict[str, Any]:
    signal_values = [str(value) for value in (signals or []) if str(value).strip()]
    event_type_values = [str(value) for value in (event_types or []) if str(value).strip()]
    command_values = [str(value) for value in (command or []) if str(value).strip()]
    path_values = [str(value) for value in (path_refs or []) if str(value).strip()]
    expanded_event_types = _expanded_lookup_event_types(signal_values, event_type_values)
    query_tokens = _lookup_tokens(query, signal_values, event_type_values, command_values, path_values)

    screening_issues = _lookup_screening_issues(query, command_values, path_values)
    query_summary, redaction_count = _lookup_query_summary(query, screening_issues)
    safe_command, count = _safe_lookup_refs(command_values)
    redaction_count += count
    safe_paths, count = _safe_lookup_refs(path_values)
    redaction_count += count

    events, event_warnings = _load_lake_events_for_lookup(hub_root)
    fix_outcomes, fix_warnings = _load_fix_outcomes_for_lookup(hub_root)
    fix_by_event: dict[str, list[dict[str, Any]]] = {}
    for outcome in fix_outcomes:
        if not _is_validated_fixed_outcome(outcome):
            continue
        event_id = str(outcome.get("event_id") or "")
        if event_id:
            fix_by_event.setdefault(event_id, []).append(outcome)

    matches: list[dict[str, Any]] = []
    for event in events:
        if _is_backfill_candidate_event(event) and not include_backfill:
            continue
        event_type = str(event.get("event_type") or "")
        event_tokens = _lookup_tokens(_event_lookup_text(event))
        fix_tokens = set()
        for fix in fix_by_event.get(str(event.get("event_id") or ""), []):
            fix_tokens.update(_lookup_tokens(_fix_lookup_text(fix)))
        overlap = sorted(query_tokens & (event_tokens | fix_tokens))
        event_type_match = bool(expanded_event_types and event_type in expanded_event_types)
        if not event_type_match and not overlap:
            continue
        public_release_gate = "not_required"
        source_visibility = str(event.get("source_visibility") or "unknown")
        if target_public_facing and source_visibility in {"private", "internal", "restricted", "unknown"}:
            public_release_gate = "needs_human_release"
        event_screening_issues = _lookup_screening_issues(event.get("safe_summary"), event.get("validation_refs"))
        if public_release_gate == "needs_human_release" or event_screening_issues:
            event_summary = f"event-summary-sha256:{sha256_bytes(str(event.get('safe_summary') or '').encode('utf-8'))}"
            count = 0
        else:
            event_summary, count = _safe_lookup_text(event.get("safe_summary"))
        redaction_count += count
        if public_release_gate == "needs_human_release":
            validation_refs = []
            asset_refs = []
        else:
            validation_refs, count = _safe_lookup_refs(event.get("validation_refs"), limit=4)
            redaction_count += count
            asset_refs, count = _safe_lookup_refs(event.get("asset_refs"), limit=4)
            redaction_count += count
        fix_summaries: list[dict[str, Any]] = []
        held_fix_count = len(fix_by_event.get(str(event.get("event_id") or ""), []))
        if public_release_gate != "needs_human_release":
            for fix in fix_by_event.get(str(event.get("event_id") or ""), []):
                fix_summary, count = _lookup_fix_summary(fix)
                redaction_count += count
                fix_summaries.append(fix_summary)
        lookup_review_status = "prior_exception_only"
        if held_fix_count:
            if public_release_gate == "needs_human_release":
                lookup_review_status = "held_pending_human_release"
            elif len(overlap) >= 2:
                lookup_review_status = "validated_fix_review_candidate"
            else:
                lookup_review_status = "related_pattern_only"
        matches.append(
            {
                "event_id": event.get("event_id", ""),
                "event_type": event_type,
                "source_repo": event.get("source_repo", ""),
                "source_visibility": source_visibility,
                "stage": event.get("stage", ""),
                "capture_contract": event.get("capture_contract", ""),
                "severity": event.get("severity", ""),
                "status": event.get("status", ""),
                "review_status": event.get("review_status", ""),
                "lookup_review_status": lookup_review_status,
                "public_release_gate": public_release_gate,
                "screening_issues": event_screening_issues,
                "safe_summary": event_summary,
                "validation_refs": validation_refs,
                "asset_refs": asset_refs,
                "match_basis": {
                    "event_type_signal_match": event_type_match,
                    "token_overlap_terms": overlap[:12],
                    "token_overlap_count": len(overlap),
                    "validated_fix_count": held_fix_count,
                    "validated_fix_details_held": public_release_gate == "needs_human_release",
                },
                "validated_fix_outcomes": fix_summaries,
                "revalidation_status": (
                    "human_release_required_before_public_target_delivery"
                    if public_release_gate == "needs_human_release"
                    else "requires_local_revalidation_before_adoption"
                ),
                "candidate_use": (
                    "Review the event and validated fix refs before improvising. "
                    "Apply only when the local repo context matches and local authority agrees."
                    if lookup_review_status == "validated_fix_review_candidate"
                    else "Use as related candidate evidence only; do not reuse fix details as instructions."
                ),
                "non_applicability_check": (
                    "Do not reuse this fix when event type, failing surface, validation refs, "
                    "or owner authority differ in a material way."
                ),
                "_sort": (
                    1 if event_type_match else 0,
                    held_fix_count,
                    len(overlap),
                    _severity_sort_value(event.get("severity")),
                    str(event.get("event_time") or ""),
                ),
            }
        )
    matches.sort(key=lambda item: item["_sort"], reverse=True)
    limited_matches = []
    for item in matches[: max(0, limit)]:
        item.pop("_sort", None)
        limited_matches.append(item)

    warnings: list[str] = [*event_warnings, *fix_warnings]
    if include_backfill:
        warnings.append("backfill candidates are path-signal evidence only and are not observed exceptions")
    if redaction_count:
        warnings.append("lookup input or refs had best-effort credential/PII redactions or path hashing")
    if screening_issues:
        warnings.append("lookup input contained suppressible sensitive or raw-context signals")
    if limited_matches and not any(item["validated_fix_outcomes"] for item in limited_matches):
        warnings.append("matched prior exception events but no validated fixed outcomes in the returned window")
    if not limited_matches:
        warnings.append("no prior matching exception evidence found; record a new exception/fix outcome if material")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "lookup_basis": HARD_ISSUE_LOOKUP_BASIS,
        "query": query_summary,
        "signals": signal_values,
        "requested_event_types": event_type_values,
        "expanded_event_types": sorted(expanded_event_types),
        "command_refs": safe_command,
        "path_refs": safe_paths,
        "target_public_facing": target_public_facing,
        "include_backfill": include_backfill,
        "event_count_considered": len(events),
        "validated_fix_outcome_count": sum(len(values) for values in fix_by_event.values()),
        "match_count": len(matches),
        "returned_count": len(limited_matches),
        "matches": limited_matches,
        "screening_issues": screening_issues,
        "warnings": warnings,
        "authority_boundary": (
            "Exception lookup output is candidate evidence. It must not override local source "
            "authority, human release gates, protected-repo policies, or validation requirements."
        ),
    }


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
    by_repo = Counter(_source_repo_report_key(event.get("source_repo")) for event in events)
    source_repo_alias_counts: dict[str, Counter[str]] = {}
    for event in events:
        source_repo = str(event.get("source_repo") or "unknown").strip() or "unknown"
        source_key = _source_repo_report_key(source_repo)
        source_repo_alias_counts.setdefault(source_key, Counter())[source_repo] += 1
    by_source_repo_aliases = [
        {
            "source_repo": source_repo,
            "count": sum(alias_counts.values()),
            "observed_aliases": [
                {"alias": alias, "count": count}
                for alias, count in sorted(alias_counts.items())
            ],
        }
        for source_repo, alias_counts in sorted(source_repo_alias_counts.items())
    ]
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
    current_classifier_version = backfill_classifier_version(hub_root)
    backfill_classifier_missing_count = 0
    backfill_classifier_stale_count = 0
    backfill_public_release_required_count = 0
    for event in events:
        if not _is_backfill_candidate_event(event):
            continue
        classifier_versions = _context_ref_values(event, "backfill-classifier-version:")
        if not classifier_versions:
            backfill_classifier_missing_count += 1
        elif any(version != current_classifier_version for version in classifier_versions):
            backfill_classifier_stale_count += 1
        visibility = str(event.get("source_visibility") or "unknown")
        public_release = (
            event.get("public_release") if isinstance(event.get("public_release"), dict) else {}
        )
        if (
            visibility in {"private", "internal", "restricted", "unknown"}
            and not _public_release_is_approved(public_release)
        ):
            backfill_public_release_required_count += 1
    backfill_refresh_required_count = (
        backfill_classifier_missing_count + backfill_classifier_stale_count
    )
    backfill_current_classifier_count = max(
        0,
        backfill_candidate_count - backfill_refresh_required_count,
    )
    next_actions: list[str] = []
    if backfill_refresh_required_count:
        next_actions.append(
            "Refresh or invalidate backfill candidates with missing/stale classifier provenance before source review."
        )
    if backfill_current_classifier_count:
        next_actions.append(
            "Review current-classifier backfill groups and request source packets for confirmed candidates."
        )
    if backfill_public_release_required_count:
        next_actions.append(
            "Keep non-public or unknown-origin backfill evidence behind human release before public-facing reuse."
        )
    if unresolved_observed_count:
        next_actions.append(
            "Record fix outcomes or accepted-risk decisions for observed exceptions that remain unresolved."
        )
    if missing_event_link_count:
        next_actions.append(
            "Repair or reject fix outcomes whose linked event is missing from the canonical lake."
        )
    if not next_actions:
        next_actions.append(
            "No exception-lake action blockers were detected from current candidate metadata."
        )
    next_action_summary = {
        "current_classifier_version": current_classifier_version,
        "backfill_candidate_count": backfill_candidate_count,
        "backfill_current_classifier_count": backfill_current_classifier_count,
        "backfill_classifier_missing_count": backfill_classifier_missing_count,
        "backfill_classifier_stale_count": backfill_classifier_stale_count,
        "backfill_refresh_required_count": backfill_refresh_required_count,
        "backfill_public_release_required_count": backfill_public_release_required_count,
        "unresolved_observed_without_fix_outcome_count": unresolved_observed_count,
        "fix_outcome_missing_event_link_count": missing_event_link_count,
        "validated_fixed_count": validated_fixed_count,
        "recommended_next_actions": next_actions,
        "authority_boundary": (
            "Next-action counts are routing evidence only. They do not confirm "
            "backfill incidents, promote lessons, approve public release, or mutate "
            "source repos."
        ),
    }
    latest_backfill_wave: dict[str, Any] = {}
    latest_path = exception_data_path(hub_root, BACKFILL_RUNS_DIR) / "latest.json"
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
        "by_source_repo_aliases": by_source_repo_aliases,
        "by_severity": dict(sorted(by_severity.items())),
        "fix_outcomes_by_decision": dict(sorted(fix_by_decision.items())),
        "fix_outcomes_by_validation_status": dict(sorted(fix_by_validation.items())),
        "next_action_summary": next_action_summary,
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
    report_path = exception_data_path(hub_root, REPORT_JSON)
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
        f"- Backfill current classifier candidates: {backfill_current_classifier_count}",
        f"- Backfill classifier refresh required: {backfill_refresh_required_count}",
        f"- Backfill public release required: {backfill_public_release_required_count}",
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
    lines.extend(["", "## Next Action Summary", ""])
    lines.append(
        "These counts route review work. They do not confirm backfill incidents, "
        "promote lessons, approve release, or mutate source repos."
    )
    lines.extend(
        [
            "",
            f"- Current classifier version: `{current_classifier_version}`",
            f"- Backfill candidates with current classifier: {backfill_current_classifier_count}",
            f"- Backfill candidates needing classifier refresh: {backfill_refresh_required_count}",
            f"- Backfill candidates requiring public release: {backfill_public_release_required_count}",
            f"- Observed exceptions without fix outcome: {unresolved_observed_count}",
            f"- Fix outcomes missing event link: {missing_event_link_count}",
            "",
            "### Recommended Next Actions",
            "",
        ]
    )
    lines.extend(f"- {action}" for action in next_actions)
    exception_data_path(hub_root, REPORT_MD).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
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
            f"sha256:{sha256_file(_exception_input_ref_path(hub_root, ref))}"
            if _exception_input_ref_path(hub_root, ref).exists()
            else "missing"
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
        path = _exception_input_ref_path(hub_root, ref)
        if not path.exists() and ref.parts[:1] == ("src",):
            path = repo_root / ref
        hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}" if path.exists() else "missing"
    return hashes


def _exception_backfill_review_queue_input_hashes(hub_root: Path) -> dict[str, str]:
    refs = [
        EXCEPTION_EVENT_TYPE_REGISTRY,
        LAKE_PATH,
        BACKFILL_RUNS_DIR / "latest.json",
        Path("src") / "digital_asset_directory" / "exceptions_lake.py",
    ]
    hashes: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parents[2]
    for ref in refs:
        path = _exception_input_ref_path(hub_root, ref)
        if not path.exists() and ref.parts[:1] == ("src",):
            path = repo_root / ref
        hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}" if path.exists() else "missing"
    return hashes


def _exception_source_packet_opportunity_input_hashes(hub_root: Path) -> dict[str, str]:
    hashes = _exception_backfill_review_queue_input_hashes(hub_root)
    decisions_path = exception_data_path(hub_root, BACKFILL_REVIEW_DECISIONS)
    hashes[BACKFILL_REVIEW_DECISIONS.as_posix()] = (
        f"sha256:{sha256_file(decisions_path)}" if decisions_path.exists() else "missing"
    )
    return hashes


def _latest_backfill_run_summary(hub_root: Path) -> dict[str, Any]:
    path = exception_data_path(hub_root, BACKFILL_RUNS_DIR) / "latest.json"
    if not path.exists():
        return {
            "available": False,
            "path": (BACKFILL_RUNS_DIR / "latest.json").as_posix(),
            "coverage_warning": "missing_latest_backfill_run",
        }
    try:
        latest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "available": False,
            "path": (BACKFILL_RUNS_DIR / "latest.json").as_posix(),
            "coverage_warning": "malformed_latest_backfill_run",
        }
    return {
        "available": True,
        "path": (BACKFILL_RUNS_DIR / "latest.json").as_posix(),
        "run_id": latest.get("run_id", ""),
        "created_at": latest.get("created_at", ""),
        "classifier_version": latest.get("classifier_version", ""),
        "created_count": latest.get("created_count", 0),
        "scanned_file_count": latest.get("scanned_file_count", 0),
        "max_scanned_files": latest.get("max_scanned_files", 0),
        "stopped_reason": latest.get("stopped_reason", ""),
        "coverage_warning": latest.get("coverage_warning", ""),
        "include_path_refs": latest.get("include_path_refs", False),
    }


def _context_ref_values(event: dict[str, Any], prefix: str) -> list[str]:
    refs = event.get("context_refs", [])
    if not isinstance(refs, list):
        return []
    values: list[str] = []
    for ref in refs:
        if isinstance(ref, str) and ref.startswith(prefix):
            values.append(ref.removeprefix(prefix))
    return values


def _public_release_is_approved(public_release: dict[str, Any]) -> bool:
    return (
        str(public_release.get("human_release_id") or "").strip() != ""
        and str(public_release.get("public_release_status") or "").strip() == "approved"
    )


def _backfill_group_status(
    *,
    missing_classifier_version: bool,
    stale_classifier_version: bool,
    classifier_version_unreconciled_count: int,
    public_release_required_count: int,
    readable_path_ref_count: int,
    source_visibility_counts: dict[str, int],
) -> tuple[str, list[str], str]:
    blockers = [
        "backfill rows are path/name metadata only, not confirmed incidents",
        "source review or source-repo confirmation is required before learning promotion",
    ]
    if public_release_required_count:
        blockers.append(
            "non-public or unknown origin requires human release before public-facing reuse"
        )
    if missing_classifier_version and classifier_version_unreconciled_count:
        blockers.append("classifier version provenance is missing; rerun or invalidate old candidate rows")
    if stale_classifier_version and classifier_version_unreconciled_count:
        blockers.append("classifier version provenance is stale or mixed; rerun or invalidate old candidate rows")
    if (missing_classifier_version or stale_classifier_version) and not classifier_version_unreconciled_count:
        blockers.append(
            "classifier provenance was reconciled from immutable backfill rule and keyword metadata"
        )
    if readable_path_ref_count:
        blockers.append("readable path refs exist in source evidence and require central-only handling")
    if source_visibility_counts.get("unknown"):
        blockers.append("source visibility is unknown for at least one candidate")
    if classifier_version_unreconciled_count:
        return (
            "needs_classifier_refresh",
            blockers,
            (
                "Rerun bounded backfill, reconcile classifier metadata, or invalidate old "
                "rows before source-reviewing this group."
            ),
        )
    if readable_path_ref_count:
        return (
            "source_review_central_only",
            blockers,
            "Review central-only path refs, then confirm, reject, or ask the source repo to emit an observed packet.",
        )
    return (
        "source_review_required",
        blockers,
        "Confirm or reject the source path signals; if confirmed, ask the source repo to emit an observed exception or fix outcome.",
    )


def _backfill_rule_lookup(hub_root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(rule.get("rule_id") or ""): rule
        for rule in backfill_classifier_rules(hub_root)
        if str(rule.get("rule_id") or "")
    }


def _backfill_classifier_reconciliation(
    group: dict[str, Any],
    *,
    current_classifier_version: str,
    rules_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidate_count = int(group.get("candidate_count") or 0)
    missing_count = int(group.get("classifier_version_missing_count") or 0)
    stale_count = int(group.get("classifier_version_stale_count") or 0)
    old_count = missing_count + stale_count
    if not old_count:
        return {
            "classifier_reconciliation_status": "not_needed",
            "classifier_version_reconciled_count": 0,
            "classifier_version_unreconciled_count": 0,
            "classifier_reconciliation_reasons": [
                "all backfill rows already cite the current classifier version"
            ],
            "classifier_reconciliation_blockers": [],
            "classifier_reconciliation_evidence": {
                "current_classifier_version": current_classifier_version,
            },
        }

    reasons: list[str] = []
    blockers: list[str] = []
    rule_id = str(group.get("rule_id") or "")
    event_type = str(group.get("event_type") or "")
    keyword_counts = {
        str(key): int(value)
        for key, value in (group.get("keyword_counts") or {}).items()
    }
    severity_counts = {
        str(key): int(value)
        for key, value in (group.get("severity_counts") or {}).items()
    }
    capture_contract_counts = {
        str(key): int(value)
        for key, value in (group.get("capture_contract_counts") or {}).items()
    }
    keyword_total = sum(keyword_counts.values())
    if keyword_total < candidate_count:
        blockers.append("not every candidate has path keyword metadata")
    rule = rules_by_id.get(rule_id)
    if rule is None:
        blockers.append("current classifier rule id is missing or unknown")
    else:
        rule_terms = {str(term) for term in rule.get("terms", []) if str(term)}
        unknown_terms = sorted(term for term in keyword_counts if term not in rule_terms)
        if unknown_terms:
            blockers.append("candidate path keyword is not in the current classifier rule")
        if str(rule.get("event_type") or "") != event_type:
            blockers.append("current classifier rule maps to a different event_type")
        rule_severity = str(rule.get("severity") or "")
        if rule_severity and any(severity != rule_severity for severity in severity_counts):
            blockers.append("candidate severity no longer matches the current classifier rule")
        rule_capture_contract = str(rule.get("capture_contract") or "")
        if rule_capture_contract and any(
            capture_contract != rule_capture_contract
            for capture_contract in capture_contract_counts
        ):
            blockers.append(
                "candidate capture_contract no longer matches the current classifier rule"
            )
        reasons.append(
            "stored backfill rule id, path keyword, event type, severity, and "
            "capture contract match the current classifier"
        )

    if blockers:
        return {
            "classifier_reconciliation_status": "unreconciled",
            "classifier_version_reconciled_count": 0,
            "classifier_version_unreconciled_count": old_count,
            "classifier_reconciliation_reasons": sorted(set(reasons)),
            "classifier_reconciliation_blockers": sorted(set(blockers)),
            "classifier_reconciliation_evidence": {
                "current_classifier_version": current_classifier_version,
                "rule_id": rule_id,
                "event_type": event_type,
                "keyword_count": keyword_total,
                "candidate_count": candidate_count,
            },
        }

    status = (
        "mixed_current_and_reconciled_classifier"
        if old_count < candidate_count
        else "reconciled_to_current_classifier"
    )
    return {
        "classifier_reconciliation_status": status,
        "classifier_version_reconciled_count": old_count,
        "classifier_version_unreconciled_count": 0,
        "classifier_reconciliation_reasons": sorted(set(reasons)),
        "classifier_reconciliation_blockers": [],
        "classifier_reconciliation_evidence": {
            "current_classifier_version": current_classifier_version,
            "rule_id": rule_id,
            "event_type": event_type,
            "keyword_count": keyword_total,
            "candidate_count": candidate_count,
            "reconciled_without_lake_rewrite": True,
        },
    }


def write_exception_backfill_review_queue(
    hub_root: Path,
    *,
    output: Path | None = None,
    limit: int = 100,
    example_limit: int = 5,
    include_readable_path_refs: bool = False,
    readable_path_refs_authorized: bool = False,
    write_outputs: bool = True,
) -> dict[str, Any]:
    """Write a source-review queue for historical path-signal backfill candidates.

    Backfill candidates are intentionally separated from the learning queue so a
    path/name hit cannot look like a confirmed incident or validated lesson.
    """
    if include_readable_path_refs and not readable_path_refs_authorized:
        raise ValueError(
            "include_readable_path_refs requires a reviewed approval gate; "
            "default backfill review queue output is hash-only."
        )
    events = [event for event in load_lake_events(hub_root) if _is_backfill_candidate_event(event)]
    taxonomy_by_type = event_type_taxonomy_dimensions(hub_root)
    category_by_type = event_type_categories(hub_root)
    current_classifier_version = backfill_classifier_version(hub_root)
    classifier_rules_by_id = _backfill_rule_lookup(hub_root)
    latest_backfill_run = _latest_backfill_run_summary(hub_root)
    limit = max(1, min(limit, MAX_BACKFILL_EVENTS))
    example_limit = max(1, min(example_limit, 25))
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event_type") or "unknown")
        source_repo = str(event.get("source_repo") or "unknown")
        rule_ids = _context_ref_values(event, "backfill-rule-id:")
        rule_id = rule_ids[0] if rule_ids else "unknown"
        group_key = (source_repo, event_type, rule_id)
        group = groups.setdefault(
            group_key,
            {
                "review_group_id": stable_id(
                    "exception-backfill-review-group",
                    source_repo,
                    event_type,
                    rule_id,
                ),
                "source_repo": source_repo,
                "event_type": event_type,
                "rule_id": rule_id,
                "category": category_by_type.get(event_type, "unknown"),
                "taxonomy_dimensions": taxonomy_by_type.get(
                    event_type,
                    _unknown_taxonomy_dimensions(),
                ),
                "candidate_count": 0,
                "source_visibility_counts": Counter(),
                "severity_counts": Counter(),
                "capture_contract_counts": Counter(),
                "keyword_counts": Counter(),
                "classifier_versions": set(),
                "classifier_version_missing_count": 0,
                "classifier_version_stale_count": 0,
                "event_ids": [],
                "path_hash_refs": [],
                "readable_path_ref_count": 0,
                "readable_path_refs": [],
                "public_release_required_count": 0,
            },
        )
        group["candidate_count"] += 1
        visibility = str(event.get("source_visibility") or "unknown")
        group["source_visibility_counts"][visibility] += 1
        group["severity_counts"][str(event.get("severity") or "unknown")] += 1
        group["capture_contract_counts"][
            str(event.get("capture_contract") or "unknown")
        ] += 1
        for keyword in _context_ref_values(event, "path-keyword:"):
            group["keyword_counts"][keyword] += 1
        classifier_versions = _context_ref_values(event, "backfill-classifier-version:")
        if not classifier_versions:
            group["classifier_version_missing_count"] += 1
        elif any(version != current_classifier_version for version in classifier_versions):
            group["classifier_version_stale_count"] += 1
        for version in classifier_versions:
            group["classifier_versions"].add(version)
        public_release = event.get("public_release") if isinstance(event.get("public_release"), dict) else {}
        if (
            visibility in {"private", "internal", "restricted", "unknown"}
            and not _public_release_is_approved(public_release)
        ):
            group["public_release_required_count"] += 1
        for rel_hash in _context_ref_values(event, "repo-relative-sha256:"):
            if len(group["path_hash_refs"]) < example_limit:
                group["path_hash_refs"].append(f"repo-relative-sha256:{rel_hash}")
        readable_refs = [
            f"repo-relative:{value}" for value in _context_ref_values(event, "repo-relative:")
        ]
        group["readable_path_ref_count"] += len(readable_refs)
        if include_readable_path_refs:
            for ref in readable_refs:
                if len(group["readable_path_refs"]) < example_limit:
                    group["readable_path_refs"].append(ref)
        if len(group["event_ids"]) < example_limit:
            event_id = str(event.get("event_id") or "")
            if event_id:
                group["event_ids"].append(event_id)

    queue_counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    for group in groups.values():
        source_visibility_counts = dict(sorted(group["source_visibility_counts"].items()))
        classifier_versions = sorted(group["classifier_versions"])
        classifier_version_missing_count = int(group["classifier_version_missing_count"])
        classifier_version_stale_count = int(group["classifier_version_stale_count"])
        classifier_reconciliation = _backfill_classifier_reconciliation(
            group,
            current_classifier_version=current_classifier_version,
            rules_by_id=classifier_rules_by_id,
        )
        status, blockers, next_action = _backfill_group_status(
            missing_classifier_version=classifier_version_missing_count > 0,
            stale_classifier_version=classifier_version_stale_count > 0,
            classifier_version_unreconciled_count=int(
                classifier_reconciliation["classifier_version_unreconciled_count"]
            ),
            public_release_required_count=int(group["public_release_required_count"]),
            readable_path_ref_count=int(group["readable_path_ref_count"]),
            source_visibility_counts=source_visibility_counts,
        )
        queue_counts[status] += 1
        severity_counts = dict(sorted(group["severity_counts"].items()))
        capture_contract_counts = dict(sorted(group["capture_contract_counts"].items()))
        review_priority = str(group["taxonomy_dimensions"].get("review_priority") or "info")
        row = {
            "review_group_id": group["review_group_id"],
            "source_repo": group["source_repo"],
            "event_type": group["event_type"],
            "rule_id": group["rule_id"],
            "category": group["category"],
            "taxonomy_dimensions": group["taxonomy_dimensions"],
            "review_priority": review_priority,
            "review_status": status,
            "candidate_count": group["candidate_count"],
            "source_visibility_counts": source_visibility_counts,
            "severity_counts": severity_counts,
            "capture_contract_counts": capture_contract_counts,
            "keyword_counts": dict(sorted(group["keyword_counts"].items())),
            "classifier_versions": classifier_versions,
            "current_classifier_version": current_classifier_version,
            "classifier_version_missing": classifier_version_missing_count > 0,
            "classifier_version_missing_count": classifier_version_missing_count,
            "classifier_version_stale": classifier_version_stale_count > 0,
            "classifier_version_stale_count": classifier_version_stale_count,
            **classifier_reconciliation,
            "public_release_required_count": group["public_release_required_count"],
            "readable_path_ref_count": group["readable_path_ref_count"],
            "path_hash_refs": group["path_hash_refs"],
            "readable_path_refs": group["readable_path_refs"],
            "example_event_ids": group["event_ids"],
            "promotion_blockers": sorted(set(blockers)),
            "recommended_next_action": next_action,
            "authority_boundary": (
                "Backfill review groups are source-review candidates only. They do not "
                "confirm incidents, promote lessons, or authorize source repo mutation."
            ),
        }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            priority_rank.get(str(row["review_priority"]), 9),
            str(row["review_status"]),
            -int(row["candidate_count"]),
            str(row["source_repo"]),
            str(row["event_type"]),
            str(row["rule_id"]),
        )
    )
    rows = rows[:limit]
    report = {
        "generated_at": utc_now(),
        "report_id": "dad:exception-backfill-review-queue",
        "input_hashes": _exception_backfill_review_queue_input_hashes(hub_root),
        "backfill_candidate_count": len(events),
        "review_group_count": len(groups),
        "reported_group_count": len(rows),
        "omitted_group_count": max(0, len(groups) - len(rows)),
        "queue_counts": dict(sorted(queue_counts.items())),
        "current_classifier_version": current_classifier_version,
        "latest_backfill_run": latest_backfill_run,
        "include_readable_path_refs": include_readable_path_refs,
        "example_limit": example_limit,
        "review_queue": rows,
        "promotion_policy_boundary": (
            "Backfill candidates are path/name metadata only. They require source "
            "review or source-repo confirmation before they can become observed "
            "exceptions, fix-outcome evidence, lessons, harness cases, or DAD rules."
        ),
    }
    if not write_outputs:
        return report
    output_path = _default_or_requested_path(hub_root, output, BACKFILL_REVIEW_QUEUE_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = (
        output_path.with_suffix(".md")
        if output
        else exception_data_path(hub_root, BACKFILL_REVIEW_QUEUE_MD)
    )
    lines = [
        "# Exception Backfill Review Queue",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Path-signal backfill candidates: {report['backfill_candidate_count']}",
        f"- Review groups: {report['review_group_count']}",
        f"- Reported groups: {report['reported_group_count']}",
        f"- Omitted groups: {report['omitted_group_count']}",
        f"- Current classifier version: `{current_classifier_version}`",
        f"- Latest backfill stopped reason: `{latest_backfill_run.get('stopped_reason', '')}`",
        f"- Latest backfill coverage warning: `{latest_backfill_run.get('coverage_warning', '')}`",
        "",
        "Boundary: backfill rows are candidate metadata only. Source review or "
        "source-repo confirmation is required before learning promotion.",
        "",
        "## Queue Counts",
        "",
    ]
    lines.extend(f"- `{status}`: {count}" for status, count in report["queue_counts"].items())
    lines.extend(["", "## Review Groups", ""])
    lines.append(
        "| Source Repo | Event Type | Rule | Status | Candidates | Priority | Next Action |"
    )
    lines.append("| --- | --- | --- | --- | ---: | --- | --- |")
    for row in rows:
        lines.append(
            "| "
            + f"`{row['source_repo']}` | `{row['event_type']}` | `{row['rule_id']}` | "
            + f"`{row['review_status']}` | {row['candidate_count']} | "
            + f"`{row['review_priority']}` | {row['recommended_next_action']} |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _backfill_refresh_plan_action(
    row: dict[str, Any],
) -> tuple[str, list[str], list[str], list[str]]:
    candidate_count = int(row.get("candidate_count") or 0)
    missing_count = int(row.get("classifier_version_missing_count") or 0)
    stale_count = int(row.get("classifier_version_stale_count") or 0)
    unreconciled_count = int(
        row.get("classifier_version_unreconciled_count")
        if row.get("classifier_version_unreconciled_count") is not None
        else missing_count + stale_count
    )
    reconciled_count = int(row.get("classifier_version_reconciled_count") or 0)
    current_count = max(0, candidate_count - missing_count - stale_count)
    readable_path_ref_count = int(row.get("readable_path_ref_count") or 0)
    public_release_required_count = int(row.get("public_release_required_count") or 0)
    reasons: list[str] = []
    commands: list[str] = []
    operator_next_steps: list[str] = []
    if missing_count:
        reasons.append("classifier provenance missing")
    if stale_count:
        reasons.append("classifier provenance stale")
    if readable_path_ref_count:
        reasons.append("readable path refs require central-only review")
    if public_release_required_count:
        reasons.append("non-public or unknown origin remains human-release gated")
    review_group_id = str(row.get("review_group_id") or "")
    if unreconciled_count:
        if current_count:
            action = "split_current_subset_then_rerun_old_subset"
            reasons.append(
                "current-classifier rows exist but old rows block source review for the group"
            )
            operator_next_steps.append(
                "Review the current-classifier subset separately from old rows before requesting source packets."
            )
        else:
            action = "rerun_or_invalidate_old_group"
            reasons.append("no current-classifier rows exist for this review group")
        operator_next_steps.extend(
            [
                "Rerun bounded backfill only with a reviewed source root, approval ID, and scope.",
                "If the candidate no longer reproduces or source review rejects it, append a reject/archive decision with notes instead of editing lake rows.",
            ]
        )
        return action, reasons, commands, operator_next_steps
    if reconciled_count:
        reasons.append(
            "old classifier provenance was reconciled from stored rule and keyword metadata"
        )
    if str(row.get("review_status") or "") == "source_review_required":
        action = "source_packet_possible"
        reasons.append("classifier provenance matches the current reviewed classifier")
        operator_next_steps.append(
            "If source confirmation is needed, append a needs_source_packet review decision for this current queue fingerprint."
        )
        commands.append(
            "asset-dir exceptions backfill-review-decision "
            f"--review-group-id {review_group_id} --decision needs_source_packet"
        )
        return action, reasons, commands, operator_next_steps
    action = "central_review_required"
    reasons.append("classifier provenance is current but another gate blocks direct source review")
    operator_next_steps.append(
        "Resolve central-only readable path review, source visibility, or release gates before requesting source packets."
    )
    return action, reasons, commands, operator_next_steps


def _select_backfill_refresh_plan_rows(
    rows: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return rows
    selected = list(rows[:limit])
    if not selected:
        return selected
    selected_ids = {str(row.get("plan_item_id") or "") for row in selected}
    action_order = sorted({str(row.get("recommended_refresh_action") or "") for row in rows})
    counts = Counter(str(row.get("recommended_refresh_action") or "") for row in selected)
    for action in action_order:
        if counts[action]:
            continue
        candidate = next(
            (
                row
                for row in rows
                if str(row.get("recommended_refresh_action") or "") == action
                and str(row.get("plan_item_id") or "") not in selected_ids
            ),
            None,
        )
        if candidate is None:
            continue
        replace_index = None
        for index in range(len(selected) - 1, -1, -1):
            selected_action = str(selected[index].get("recommended_refresh_action") or "")
            if counts[selected_action] > 1:
                replace_index = index
                break
        if replace_index is None:
            continue
        replaced = selected[replace_index]
        counts[str(replaced.get("recommended_refresh_action") or "")] -= 1
        selected_ids.discard(str(replaced.get("plan_item_id") or ""))
        selected[replace_index] = candidate
        counts[action] += 1
        selected_ids.add(str(candidate.get("plan_item_id") or ""))
    order = {str(row.get("plan_item_id") or ""): index for index, row in enumerate(rows)}
    return sorted(selected, key=lambda row: order.get(str(row.get("plan_item_id") or ""), 0))


def write_exception_backfill_refresh_plan(
    hub_root: Path,
    *,
    output: Path | None = None,
    limit: int = 100,
    example_limit: int = 5,
) -> dict[str, Any]:
    """Write a candidate-only plan for stale historical backfill rows.

    The plan deliberately does not rewrite lake records. It turns the immutable
    review queue into explicit next actions so old rows can be rerun,
    source-packeted, or invalidated through append-only decisions.
    """
    queue = write_exception_backfill_review_queue(
        hub_root,
        limit=MAX_BACKFILL_EVENTS,
        example_limit=example_limit,
        write_outputs=False,
    )
    limit = max(1, min(limit, MAX_BACKFILL_EVENTS))
    action_counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    for queue_row in queue.get("review_queue", []):
        if not isinstance(queue_row, dict):
            continue
        action, reasons, commands, operator_next_steps = _backfill_refresh_plan_action(queue_row)
        action_counts[action] += 1
        candidate_count = int(queue_row.get("candidate_count") or 0)
        missing_count = int(queue_row.get("classifier_version_missing_count") or 0)
        stale_count = int(queue_row.get("classifier_version_stale_count") or 0)
        rows.append(
            {
                "plan_item_id": stable_id(
                    "exception-backfill-refresh-plan-item",
                    str(queue_row.get("review_group_id") or ""),
                    action,
                    str(candidate_count),
                    str(missing_count),
                    str(stale_count),
                ),
                "review_group_id": queue_row.get("review_group_id", ""),
                "source_repo": queue_row.get("source_repo", ""),
                "event_type": queue_row.get("event_type", ""),
                "rule_id": queue_row.get("rule_id", ""),
                "review_priority": queue_row.get("review_priority", "info"),
                "review_status": queue_row.get("review_status", ""),
                "recommended_refresh_action": action,
                "source_repo_ref_policy": (
                    "central_internal_identifier_not_public_safe; path refs are "
                    "hash-only by default"
                ),
                "candidate_count": candidate_count,
                "current_classifier_candidate_count": max(
                    0,
                    candidate_count - missing_count - stale_count,
                ),
                "classifier_version_missing_count": missing_count,
                "classifier_version_stale_count": stale_count,
                "classifier_version_reconciled_count": queue_row.get(
                    "classifier_version_reconciled_count",
                    0,
                ),
                "classifier_version_unreconciled_count": queue_row.get(
                    "classifier_version_unreconciled_count",
                    missing_count + stale_count,
                ),
                "classifier_reconciliation_status": queue_row.get(
                    "classifier_reconciliation_status",
                    "",
                ),
                "classifier_reconciliation_blockers": queue_row.get(
                    "classifier_reconciliation_blockers",
                    [],
                ),
                "public_release_required_count": queue_row.get(
                    "public_release_required_count",
                    0,
                ),
                "readable_path_ref_count": queue_row.get("readable_path_ref_count", 0),
                "path_hash_refs": queue_row.get("path_hash_refs", []),
                "example_event_ids": queue_row.get("example_event_ids", []),
                "reasons": sorted(set(reasons)),
                "operator_next_steps": operator_next_steps,
                "command_hints": commands,
                "authority_boundary": (
                    "This item is routing evidence only. It does not mutate lake rows, "
                    "invalidate candidates, confirm incidents, approve public release, "
                    "or authorize source repo writes."
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            priority_rank.get(str(row.get("review_priority")), 9),
            str(row.get("recommended_refresh_action")),
            -int(row.get("candidate_count") or 0),
            str(row.get("source_repo")),
            str(row.get("event_type")),
            str(row.get("rule_id")),
        )
    )
    all_rows = rows
    rows = _select_backfill_refresh_plan_rows(all_rows, limit)
    reported_action_counts = Counter(
        str(row.get("recommended_refresh_action") or "") for row in rows
    )
    omitted_action_counts = {
        action: count - reported_action_counts.get(action, 0)
        for action, count in action_counts.items()
        if count - reported_action_counts.get(action, 0) > 0
    }
    report = {
        "generated_at": utc_now(),
        "report_id": "dad:exception-backfill-classifier-refresh-plan",
        "input_hashes": _exception_backfill_review_queue_input_hashes(hub_root),
        "generated_by_command": "asset-dir exceptions backfill-refresh-plan",
        "generation_parameters": {
            "limit": limit,
            "example_limit": example_limit,
            "row_selection": "priority_sorted_with_action_coverage_when_limit_permits",
        },
        "freshness_guidance": (
            "Regenerate this plan before review if any input hash, classifier version, "
            "latest backfill run, review queue logic, or lake contents changed."
        ),
        "path_ref_policy": (
            "Path references in plan rows are hash-only by default. Source repo IDs "
            "may be readable central/internal policy identifiers and are not a "
            "public-safe export."
        ),
        "current_classifier_version": queue.get("current_classifier_version", ""),
        "latest_backfill_run": queue.get("latest_backfill_run", {}),
        "backfill_candidate_count": queue.get("backfill_candidate_count", 0),
        "review_group_count": queue.get("review_group_count", 0),
        "reported_plan_item_count": len(rows),
        "omitted_plan_item_count": max(
            0,
            int(queue.get("review_group_count") or 0) - len(rows),
        ),
        "action_counts": dict(sorted(action_counts.items())),
        "reported_action_counts": dict(sorted(reported_action_counts.items())),
        "omitted_action_counts": dict(sorted(omitted_action_counts.items())),
        "plan_items": rows,
        "authority_boundary": (
            "The refresh plan is a generated review aid. It does not mutate lake "
            "rows; reviewers must rerun bounded backfill or append review "
            "decisions instead of editing historical lake rows."
        ),
    }
    output_path = _default_or_requested_path(hub_root, output, BACKFILL_REFRESH_PLAN_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = (
        output_path.with_suffix(".md")
        if output
        else exception_data_path(hub_root, BACKFILL_REFRESH_PLAN_MD)
    )
    lines = [
        "# Exception Backfill Classifier Refresh Plan",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Path-signal backfill candidates: {report['backfill_candidate_count']}",
        f"- Review groups: {report['review_group_count']}",
        f"- Reported plan items: {report['reported_plan_item_count']}",
        f"- Omitted plan items: {report['omitted_plan_item_count']}",
        f"- Current classifier version: `{report['current_classifier_version']}`",
        f"- Generated by: `{report['generated_by_command']}`",
        f"- Limit: {limit}",
        f"- Example limit: {example_limit}",
        "- Boundary: this report does not mutate lake rows, confirm incidents, "
        "invalidate candidates, approve release, or write to source repos.",
        "- Path policy: path references are hash-only by default; source repo IDs "
        "may be readable central/internal identifiers and are not public-safe exports.",
        f"- Freshness: {report['freshness_guidance']}",
        "",
        "## Action Counts",
        "",
    ]
    lines.extend(f"- `{action}`: {count}" for action, count in report["action_counts"].items())
    lines.extend(["", "## Reported Action Counts", ""])
    lines.extend(
        f"- `{action}`: {count}"
        for action, count in report["reported_action_counts"].items()
    )
    if report["omitted_action_counts"]:
        lines.extend(["", "## Omitted Action Counts", ""])
        lines.extend(
            f"- `{action}`: {count}"
            for action, count in report["omitted_action_counts"].items()
        )
    lines.extend(["", "## Plan Items", ""])
    lines.append(
        "| Source Repo | Event Type | Rule | Action | Candidates | Current | Missing | Stale | Reconciled | Unreconciled |"
    )
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in rows:
        lines.append(
            "| "
            + f"`{row['source_repo']}` | `{row['event_type']}` | `{row['rule_id']}` | "
            + f"`{row['recommended_refresh_action']}` | {row['candidate_count']} | "
            + f"{row['current_classifier_candidate_count']} | "
            + f"{row['classifier_version_missing_count']} | "
            + f"{row['classifier_version_stale_count']} | "
            + f"{row['classifier_version_reconciled_count']} | "
            + f"{row['classifier_version_unreconciled_count']} |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


BACKFILL_REVIEW_DECISION_VALUES = {
    "confirm",
    "reject",
    "needs_source_packet",
    "needs_classifier_refresh",
    "defer",
    "archive",
}
BACKFILL_REVIEWER_TYPES = {"human", "agent", "source_repo", "unknown"}
BACKFILL_DECISION_EFFECTS = {
    "confirm": "source_review_confirmed_candidate_only",
    "reject": "rejected_candidate_no_learning",
    "needs_source_packet": "source_packet_requested_no_learning",
    "needs_classifier_refresh": "classifier_refresh_required_no_learning",
    "defer": "deferred_no_learning",
    "archive": "archived_no_learning",
}


def _review_status_for_reviewer_type(reviewer_type: str) -> str:
    if reviewer_type == "human":
        return "human_reviewed"
    if reviewer_type == "source_repo":
        return "source_reviewed"
    return "agent_triage"


def _sanitize_backfill_decision_text(value: str, issues: list[str]) -> tuple[str, int]:
    redacted, redaction_count = redact_sensitive_text(value)
    if _contains_readable_repo_relative_text(redacted):
        issues.append("readable_repo_relative_ref_rejected")
        digest = sha256_bytes(redacted.encode("utf-8"))
        return f"[READABLE_REPO_RELATIVE_REF_REJECTED_SHA256:{digest}]", redaction_count
    if _looks_like_local_path_ref(redacted):
        issues.append("local_path_like_ref_rejected")
        digest = sha256_bytes(redacted.encode("utf-8"))
        return f"[LOCAL_PATH_LIKE_REF_REJECTED_SHA256:{digest}]", redaction_count
    limited, limit_redactions = _redact_and_limit(redacted, issues)
    return str(limited), redaction_count + limit_redactions


def _backfill_review_queue_fingerprint(
    *,
    review_group_id: str,
    group: dict[str, Any],
    input_hashes: dict[str, str],
) -> str:
    return stable_id(
        "exception-backfill-review-queue-fingerprint",
        review_group_id,
        json_dumps(dict(sorted(input_hashes.items()))),
        str(group.get("review_status", "")),
        str(group.get("current_classifier_version", "")),
        str(group.get("candidate_count", "")),
        str(group.get("public_release_required_count", "")),
        str(group.get("readable_path_ref_count", "")),
        "|".join(str(item) for item in group.get("path_hash_refs", []) or []),
        "|".join(str(item) for item in group.get("example_event_ids", []) or []),
    )


def _append_unique_backfill_review_decision(hub_root: Path, record: dict[str, Any]) -> bool:
    path = exception_data_path(hub_root, BACKFILL_REVIEW_DECISIONS)
    existing_ids: set[str] = set()
    if path.exists():
        for row in _read_jsonl_with_errors(path)[0]:
            if isinstance(row, dict) and row.get("decision_id"):
                existing_ids.add(str(row["decision_id"]))
    if str(record["decision_id"]) in existing_ids:
        return False
    append_jsonl(path, record)
    return True


def load_exception_backfill_review_decisions(hub_root: Path) -> list[dict[str, Any]]:
    path = exception_data_path(hub_root, BACKFILL_REVIEW_DECISIONS)
    if not path.exists():
        return []
    records, errors = _read_jsonl_with_errors(path)
    for error in errors:
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "backfill_review_decisions_malformed_jsonl.jsonl",
            {
                "event_type": "backfill_review_decision_malformed_jsonl",
                "created_at": utc_now(),
                "path": BACKFILL_REVIEW_DECISIONS.as_posix(),
                **error,
            },
        )
    return records


def _find_backfill_review_group(report: dict[str, Any], review_group_id: str) -> dict[str, Any]:
    for row in report.get("review_queue", []):
        if str(row.get("review_group_id")) == review_group_id:
            return row
    raise ValueError(f"Unknown backfill review_group_id: {review_group_id}")


def record_exception_backfill_review_decision(
    hub_root: Path,
    *,
    review_group_id: str,
    decision: str,
    reviewer: str = "unknown",
    reviewer_type: str = "agent",
    approval_id: str = "",
    source_packet_id: str = "",
    notes: str = "",
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    normalized_decision = decision.strip().lower()
    if normalized_decision not in BACKFILL_REVIEW_DECISION_VALUES:
        raise ValueError(
            "decision must be one of: " + ", ".join(sorted(BACKFILL_REVIEW_DECISION_VALUES))
        )
    normalized_reviewer_type = reviewer_type.strip().lower() or "unknown"
    if normalized_reviewer_type not in BACKFILL_REVIEWER_TYPES:
        raise ValueError(
            "reviewer_type must be one of: " + ", ".join(sorted(BACKFILL_REVIEWER_TYPES))
        )
    if normalized_reviewer_type == "human" and not approval_id.strip():
        raise ValueError("Human backfill review decisions require --approval-id.")
    if normalized_reviewer_type == "source_repo" and not source_packet_id.strip():
        raise ValueError("Source-repo backfill review decisions require --source-packet-id.")
    report = write_exception_backfill_review_queue(
        hub_root,
        limit=MAX_BACKFILL_EVENTS,
        example_limit=5,
    )
    group = _find_backfill_review_group(report, review_group_id)
    if normalized_decision == "confirm" and group.get("review_status") == "needs_classifier_refresh":
        raise ValueError(
            "Cannot confirm a backfill review group while classifier provenance needs refresh."
        )
    if (
        normalized_decision == "confirm"
        and int(group.get("readable_path_ref_count") or 0) > 0
        and normalized_reviewer_type == "agent"
    ):
        raise ValueError(
            "Agent triage cannot confirm a central-only readable-ref backfill group."
    )

    issues: list[str] = []
    total_redactions = 0
    safe_reviewer, count = _sanitize_backfill_decision_text(reviewer, issues)
    total_redactions += count
    raw_authority_ref = "agent_triage"
    if normalized_reviewer_type == "human":
        raw_authority_ref = f"human_approval:{approval_id.strip()}"
    elif normalized_reviewer_type == "source_repo":
        raw_authority_ref = f"source_packet:{source_packet_id.strip()}"
    elif normalized_reviewer_type == "unknown":
        raw_authority_ref = "unknown_triage"
    safe_authority_ref, count = _sanitize_backfill_decision_text(raw_authority_ref, issues)
    total_redactions += count
    safe_notes, count = _sanitize_backfill_decision_text(notes, issues)
    total_redactions += count
    safe_evidence_refs: list[str] = []
    for value in evidence_refs or []:
        safe_value, count = _sanitize_backfill_decision_text(value, issues)
        total_redactions += count
        safe_evidence_refs.append(safe_value)
    reviewed_at = utc_now()
    source_queue_input_hashes = {
        str(key): str(value) for key, value in report.get("input_hashes", {}).items()
    }
    source_queue_fingerprint = _backfill_review_queue_fingerprint(
        review_group_id=review_group_id,
        group=group,
        input_hashes=source_queue_input_hashes,
    )
    decision_id = stable_id(
        "exception-backfill-review-decision",
        review_group_id,
        source_queue_fingerprint,
        normalized_decision,
        safe_reviewer,
        normalized_reviewer_type,
        safe_authority_ref,
        safe_notes,
        "|".join(safe_evidence_refs),
    )
    record = {
        "schema_version": "0.1.0",
        "decision_id": decision_id,
        "review_group_id": review_group_id,
        "decision": normalized_decision,
        "reviewer": safe_reviewer,
        "reviewer_type": normalized_reviewer_type,
        "review_authority_ref": safe_authority_ref,
        "reviewed_at": reviewed_at,
        "source_repo": group.get("source_repo", "unknown"),
        "event_type": group.get("event_type", "unknown"),
        "rule_id": group.get("rule_id", "unknown"),
        "source_queue_status": group.get("review_status", "unknown"),
        "current_classifier_version": group.get("current_classifier_version", ""),
        "candidate_count": int(group.get("candidate_count") or 0),
        "public_release_required_count": int(group.get("public_release_required_count") or 0),
        "readable_path_ref_count": int(group.get("readable_path_ref_count") or 0),
        "notes": safe_notes,
        "evidence_refs": safe_evidence_refs,
        "promotion_blockers_snapshot": group.get("promotion_blockers", []),
        "recommended_next_action_snapshot": group.get("recommended_next_action", ""),
        "source_queue_input_hashes": source_queue_input_hashes,
        "source_queue_fingerprint": source_queue_fingerprint,
        "result_effect": BACKFILL_DECISION_EFFECTS[normalized_decision],
        "authority_boundary": (
            "Backfill review decisions label candidate path-signal groups only. "
            "They do not create observed exceptions, fix outcomes, lessons, rules, "
            "public releases, or source-repo mutations."
        ),
        "screening": {
            "screened_at": reviewed_at,
            "credential_pii_screen": "best_effort",
            "redaction_count": total_redactions,
            "issues": sorted(set(issues)),
            "screening_note": (
                "Best-effort credential/PII screening only; absence of redactions "
                "does not prove the decision text is safe."
            ),
        },
        "review_status": _review_status_for_reviewer_type(normalized_reviewer_type),
    }
    appended = _append_unique_backfill_review_decision(hub_root, record)
    return {
        "decision": record,
        "appended": appended,
        "ledger": BACKFILL_REVIEW_DECISIONS.as_posix(),
    }


def summarize_exception_backfill_review_decisions(
    hub_root: Path,
    *,
    review_group_id: str = "",
) -> dict[str, Any]:
    rows = load_exception_backfill_review_decisions(hub_root)
    if review_group_id:
        rows = [row for row in rows if str(row.get("review_group_id")) == review_group_id]
    latest_by_group: dict[str, dict[str, Any]] = {}
    for row in rows:
        group_id = str(row.get("review_group_id") or "")
        if not group_id:
            continue
        previous = latest_by_group.get(group_id)
        if previous is None or str(row.get("reviewed_at", "")) >= str(
            previous.get("reviewed_at", "")
        ):
            latest_by_group[group_id] = row
    return {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "ledger": BACKFILL_REVIEW_DECISIONS.as_posix(),
        "review_group_id": review_group_id,
        "decision_count": len(rows),
        "review_group_count": len({str(row.get("review_group_id")) for row in rows}),
        "decision_counts": dict(Counter(str(row.get("decision", "unknown")) for row in rows)),
        "review_status_counts": dict(
            Counter(str(row.get("review_status", "unknown")) for row in rows)
        ),
        "latest_decisions": sorted(
            latest_by_group.values(),
            key=lambda row: (str(row.get("review_group_id", "")), str(row.get("reviewed_at", ""))),
        ),
        "authority_boundary": (
            "Decision summaries are review labels for backfill candidates only; "
            "they do not promote lessons or prove incidents."
        ),
    }


def _latest_backfill_review_decisions_by_group(
    hub_root: Path,
    *,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    source_rows = rows if rows is not None else load_exception_backfill_review_decisions(hub_root)
    for row in source_rows:
        group_id = str(row.get("review_group_id") or "")
        if not group_id:
            continue
        previous = latest.get(group_id)
        if previous is None or str(row.get("reviewed_at", "")) >= str(
            previous.get("reviewed_at", "")
        ):
            latest[group_id] = row
    return latest


def _mail_record_identity(record: dict[str, Any]) -> tuple[str, str]:
    return str(record.get("mail_id", "")), str(record.get("dedupe_key", ""))


def _source_packet_request_group_id(record: dict[str, Any]) -> str:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    source_ref = str(payload.get("source_ref") or "")
    prefix = "dad://exceptions/backfill-review-groups/"
    if source_ref.startswith(prefix):
        return source_ref.removeprefix(prefix)
    return ""


def _source_packet_request_is_cancellation(record: dict[str, Any]) -> bool:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return (
        str(record.get("message_type") or "") == "review_decision"
        and bool(payload.get("superseded_mail_id"))
        and str(payload.get("superseded_reason") or "").startswith("source_packet_request_")
    )


def _safe_source_packet_target_ref(value: Any, issues: list[str]) -> str:
    text = str(_safe_external_ref(str(value or "unknown")) or "unknown").strip()
    redacted, redaction_count = redact_sensitive_text(text)
    if redaction_count:
        issues.append("target_ref_credential_or_pii_hashed")
        return f"target-ref-sha256:{sha256_bytes(text.encode('utf-8'))}"
    if _contains_readable_repo_relative_text(redacted):
        issues.append("target_ref_readable_repo_relative_hashed")
        return f"target-ref-sha256:{sha256_bytes(text.encode('utf-8'))}"
    if not SOURCE_PACKET_SAFE_TARGET_RE.fullmatch(redacted):
        issues.append("target_ref_unsafe_shape_hashed")
        return f"target-ref-sha256:{sha256_bytes(text.encode('utf-8'))}"
    return redacted


def _source_packet_mail_semantic_issues(record: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    text = json_dumps(record)
    if _looks_like_local_path_ref(text):
        issues.append("local_path_like_ref")
    if _contains_readable_repo_relative_text(text):
        issues.append("readable_repo_relative_ref")
    _, redaction_count = redact_sensitive_text(text)
    if redaction_count:
        issues.append("credential_or_pii_pattern")
    cleaned, _ = _redact_and_limit(record, issues)
    if len(json_dumps(cleaned).encode("utf-8")) > 64_000:
        issues.append("record_too_large")
    return sorted(set(issues))


def _quarantine_source_packet_request_decision(
    hub_root: Path,
    *,
    event_type: str,
    decision: dict[str, Any],
    reason: str,
    current_fingerprint: str = "",
    current_group: dict[str, Any] | None = None,
) -> None:
    append_jsonl(
        exception_data_path(hub_root, QUARANTINE_DIR)
        / "source_packet_request_decision_mismatches.jsonl",
        {
            "event_type": event_type,
            "created_at": utc_now(),
            "reason": reason,
            "decision_id": str(decision.get("decision_id") or ""),
            "review_group_id": str(decision.get("review_group_id") or ""),
            "decision": str(decision.get("decision") or ""),
            "decision_line_number": int(decision.get("_dad_line_number") or 0),
            "decision_source_queue_fingerprint": str(
                decision.get("source_queue_fingerprint") or ""
            ),
            "current_source_queue_fingerprint": current_fingerprint,
            "current_review_status": str((current_group or {}).get("review_status") or ""),
            "record_sha256": sha256_bytes(json_dumps(decision).encode("utf-8")),
            "authority_boundary": (
                "Rejected source-packet request decisions are not source truth, "
                "not deliverable mail, and not learning-promotion evidence."
            ),
        },
    )


def _validate_backfill_review_decision_for_request(
    hub_root: Path,
    row: dict[str, Any],
    *,
    line_number: int,
) -> bool:
    schema_path = hub_root / "schemas" / "exception-backfill-review-decision.schema.json"
    if not schema_path.exists():
        schema_path = Path(__file__).resolve().parents[2] / "schemas" / "exception-backfill-review-decision.schema.json"
    try:
        schema = _load_json(schema_path)
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        validator_cls(schema).validate(row)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "source_packet_request_invalid_decisions.jsonl",
            {
                "event_type": "source_packet_request_invalid_decision",
                "created_at": utc_now(),
                "path": BACKFILL_REVIEW_DECISIONS.as_posix(),
                "line_number": line_number,
                "reason": str(exc),
                "record_sha256": sha256_bytes(json_dumps(row).encode("utf-8")),
            },
        )
        return False
    return True


def _load_valid_backfill_review_decisions_for_requests(hub_root: Path) -> list[dict[str, Any]]:
    path = exception_data_path(hub_root, BACKFILL_REVIEW_DECISIONS)
    if not path.exists():
        return []
    valid_rows: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped_bytes = raw_line.strip()
            if not stripped_bytes:
                continue
            try:
                row = json.loads(stripped_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                append_jsonl(
                    exception_data_path(hub_root, QUARANTINE_DIR)
                    / "source_packet_request_malformed_decisions.jsonl",
                    {
                        "event_type": "source_packet_request_malformed_decision_jsonl",
                        "created_at": utc_now(),
                        "path": BACKFILL_REVIEW_DECISIONS.as_posix(),
                        "line": line_number,
                        "error": str(exc),
                        "raw_sha256": sha256_bytes(stripped_bytes),
                    },
                )
                continue
            if not isinstance(row, dict):
                append_jsonl(
                    exception_data_path(hub_root, QUARANTINE_DIR)
                    / "source_packet_request_invalid_decisions.jsonl",
                    {
                        "event_type": "source_packet_request_invalid_decision",
                        "created_at": utc_now(),
                        "path": BACKFILL_REVIEW_DECISIONS.as_posix(),
                        "line_number": line_number,
                        "reason": "JSONL row is not an object",
                        "record_sha256": sha256_bytes(json_dumps(row).encode("utf-8")),
                    },
                )
                continue
            if _validate_backfill_review_decision_for_request(
                hub_root,
                row,
                line_number=line_number,
            ):
                row["_dad_line_number"] = line_number
                valid_rows.append(row)
    return valid_rows


def _append_unique_source_packet_mail(hub_root: Path, record: dict[str, Any]) -> str:
    path = exception_data_path(hub_root, SOURCE_PACKET_REQUESTS_STAGED)
    mail_record = MailMessageRecord(**record)
    payload = mail_record.model_dump(mode="json")
    issues = _source_packet_mail_semantic_issues(payload)
    if issues:
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "source_packet_request_mail_rejected.jsonl",
            {
                "event_type": "source_packet_request_mail_rejected",
                "created_at": utc_now(),
                "mail_id": str(payload.get("mail_id") or ""),
                "dedupe_key": str(payload.get("dedupe_key") or ""),
                "issues": issues,
                "record_sha256": sha256_bytes(json_dumps(payload).encode("utf-8")),
            },
        )
        return "rejected"
    new_identity = _mail_record_identity(record)
    if path.exists():
        rows, errors = _read_jsonl_with_errors(path)
        for error in errors:
            append_jsonl(
                exception_data_path(hub_root, QUARANTINE_DIR)
                / "source_packet_requests_malformed_jsonl.jsonl",
                {
                    "event_type": "source_packet_request_malformed_jsonl",
                    "created_at": utc_now(),
                    "path": SOURCE_PACKET_REQUESTS_STAGED.as_posix(),
                    **error,
                },
            )
        for row in rows:
            if _mail_record_identity(row) == new_identity:
                return "duplicate"
    append_jsonl(path, payload)
    return "appended"


def _source_packet_request_mail(
    decision: dict[str, Any],
    current_group: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    source_repo = _safe_source_packet_target_ref(
        current_group.get("source_repo") or "unknown",
        issues,
    )
    group_id = str(decision.get("review_group_id") or "unknown")
    created_at = utc_now()
    dedupe_key = stable_id(
        "exception-source-packet-request",
        group_id,
        str(decision.get("source_queue_fingerprint") or ""),
        str(decision.get("decision_id") or ""),
    )
    payload = {
        "summary": "DAD needs source-repo evidence before learning from an exception backfill group.",
        "source_ref": f"dad://exceptions/backfill-review-groups/{group_id}",
        "hash": str(decision.get("source_queue_fingerprint") or ""),
        "note": (
            "Send a safe exception packet or review decision if this path-signal "
            "group is a real incident; do not include secrets, private rows, raw "
            "logs, or long source snippets."
        ),
        "taxonomy": str(current_group.get("event_type") or "unknown"),
    }
    if issues:
        payload["screening_issues"] = sorted(set(issues))
    evidence = [
        f"decision_id:{decision.get('decision_id', '')}",
        f"review_group_id:{group_id}",
        f"rule_id:{current_group.get('rule_id', '')}",
        f"source_queue_fingerprint:{decision.get('source_queue_fingerprint', '')}",
    ]
    record = MailMessageRecord(
        mail_id=stable_id("mail", "governance_notice", "dad", source_repo, dedupe_key),
        thread_id=stable_id("mail-thread", "dad", source_repo, group_id),
        message_type="governance_notice",
        source_repo="dad",
        target_repo=source_repo,
        created_at=created_at,
        dedupe_key=dedupe_key,
        sensitivity="internal",
        review_status="routed_candidate",
        payload=payload,
        evidence=evidence,
        suggested_actions=[
            "Review the source context locally.",
            "If real, send a public-safe exception packet or a source_repo backfill review decision.",
            "If not real, reject or archive the backfill review group.",
        ],
        source_provenance={
            "canonical_source_repo": "dad://hub/Digital-Assett-Directory",
            "source_repo_id": "dad",
            "source_repo_alias": "dad",
            "source_visibility": "internal",
            "original_source_chain": ["dad://hub/Digital-Assett-Directory"],
            "return_address": "dad://exceptions/source-packet-requests",
            "original_mail_id": "",
            "composed_by": "dad-exceptions-lake",
            "collected_by": "dad",
            "collected_at": "",
            "received_at": created_at,
        },
        public_release={
            "target_visibility": "unknown",
            "target_public_facing": False,
            "public_release_required": False,
            "public_release_status": "not_required",
            "human_release_id": "",
            "release_reason": "central_source_packet_request_only",
        },
    )
    return record.model_dump(mode="json")


def _source_packet_request_cancellation_mail(
    original: dict[str, Any],
    *,
    reason: str,
    latest_decision: dict[str, Any] | None,
) -> dict[str, Any]:
    created_at = utc_now()
    group_id = _source_packet_request_group_id(original)
    latest_decision_id = str((latest_decision or {}).get("decision_id") or "")
    original_mail_id = str(original.get("mail_id") or "")
    target_repo = str(original.get("target_repo") or "central_only")
    dedupe_key = stable_id(
        "exception-source-packet-request-cancellation",
        original_mail_id,
        latest_decision_id,
        reason,
    )
    return MailMessageRecord(
        mail_id=stable_id("mail", "review_decision", "dad", target_repo, dedupe_key),
        thread_id=str(original.get("thread_id") or stable_id("mail-thread", "dad", target_repo, group_id)),
        message_type="review_decision",
        source_repo="dad",
        target_repo=target_repo,
        created_at=created_at,
        dedupe_key=dedupe_key,
        sensitivity="internal",
        review_status="archived",
        payload={
            "summary": "Staged source-packet request was superseded before delivery.",
            "source_ref": f"dad://exceptions/backfill-review-groups/{group_id}",
            "hash": str((original.get("payload") or {}).get("hash") or ""),
            "superseded_mail_id": original_mail_id,
            "superseded_reason": f"source_packet_request_{reason}",
            "latest_decision_id": latest_decision_id,
            "latest_decision": str((latest_decision or {}).get("decision") or ""),
        },
        evidence=[
            f"superseded_mail_id:{original_mail_id}",
            f"review_group_id:{group_id}",
            f"latest_decision_id:{latest_decision_id}",
        ],
        suggested_actions=[
            "Do not promote the superseded staged request into deliverable mail.",
            "Regenerate source-packet requests from the latest backfill review decision ledger.",
        ],
        source_provenance={
            "canonical_source_repo": "dad://hub/Digital-Assett-Directory",
            "source_repo_id": "dad",
            "source_repo_alias": "dad",
            "source_visibility": "internal",
            "original_source_chain": ["dad://hub/Digital-Assett-Directory"],
            "return_address": "dad://exceptions/source-packet-requests",
            "original_mail_id": original_mail_id,
            "composed_by": "dad-exceptions-lake",
            "collected_by": "dad",
            "collected_at": "",
            "received_at": created_at,
        },
        public_release={
            "target_visibility": "unknown",
            "target_public_facing": False,
            "public_release_required": False,
            "public_release_status": "not_required",
            "human_release_id": "",
            "release_reason": "superseded_staged_request",
        },
    ).model_dump(mode="json")


def _current_backfill_review_group_state(
    hub_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, str]]:
    report = write_exception_backfill_review_queue(hub_root, limit=MAX_BACKFILL_EVENTS)
    groups = {
        str(row.get("review_group_id") or ""): row
        for row in report.get("review_queue", [])
        if str(row.get("review_group_id") or "")
    }
    input_hashes = report.get("input_hashes", {})
    fingerprints = {
        group_id: _backfill_review_queue_fingerprint(
            review_group_id=group_id,
            group=group,
            input_hashes=input_hashes,
        )
        for group_id, group in groups.items()
    }
    return report, groups, fingerprints


def _source_packet_request_decision_matches_current_group(
    decision: dict[str, Any],
    current_group: dict[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    for field in ("source_repo", "event_type", "rule_id"):
        decision_value = str(decision.get(field) or "")
        current_value = str(current_group.get(field) or "")
        if decision_value != current_value:
            mismatches.append(field)
    if str(decision.get("source_queue_status") or "") != str(
        current_group.get("review_status") or ""
    ):
        mismatches.append("source_queue_status")
    return mismatches


def _source_packet_opportunity_for_group(
    group: dict[str, Any],
    *,
    latest_decision: dict[str, Any] | None,
    source_queue_fingerprint: str,
) -> dict[str, Any]:
    group_id = str(group.get("review_group_id") or "")
    missing_count = int(group.get("classifier_version_missing_count") or 0)
    stale_count = int(group.get("classifier_version_stale_count") or 0)
    unreconciled_count = int(
        group.get("classifier_version_unreconciled_count")
        if group.get("classifier_version_unreconciled_count") is not None
        else missing_count + stale_count
    )
    readable_path_ref_count = int(group.get("readable_path_ref_count") or 0)
    public_release_required_count = int(group.get("public_release_required_count") or 0)
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []
    command_hints: list[str] = []
    latest_decision_value = str((latest_decision or {}).get("decision") or "")
    latest_decision_id = str((latest_decision or {}).get("decision_id") or "")

    if unreconciled_count:
        status = "blocked_classifier_refresh"
        if missing_count:
            blockers.append("classifier provenance missing")
        if stale_count:
            blockers.append("classifier provenance stale")
        for blocker in group.get("classifier_reconciliation_blockers", []) or []:
            blockers.append(str(blocker))
        next_actions.append(
            "Rerun bounded backfill, reconcile classifier metadata, or append a reject/archive decision before requesting source packets."
        )
    elif readable_path_ref_count:
        status = "blocked_central_readable_ref_review"
        blockers.append("readable path refs require central-only review before source-packet planning")
        next_actions.append(
            "Regenerate the review queue without readable refs or complete central-only path review."
        )
    elif latest_decision_value == "needs_source_packet":
        status = "decision_exists_request_compilable"
        next_actions.append(
            "Run asset-dir exceptions source-packet-requests to compile this latest decision into staged candidate mail."
        )
    elif latest_decision_value:
        status = f"blocked_latest_decision_{latest_decision_value}"
        blockers.append("latest review decision is not needs_source_packet")
        next_actions.append(
            "Append a newer decision only if the source review state materially changed."
        )
    elif str(group.get("review_status") or "") == "source_review_required":
        status = "source_packet_decision_recommended"
        next_actions.append(
            "Append a needs_source_packet decision if source-repo confirmation is needed."
        )
        command_hints.append(
            "asset-dir exceptions backfill-review-decision "
            f"--review-group-id {group_id} "
            "--decision needs_source_packet "
            "--reviewer <agent-or-human> "
            "--reviewer-type agent "
            '--notes "<safe metadata-only rationale>"'
        )
    else:
        status = "central_review_required_first"
        blockers.append("review group is not currently in source_review_required status")
        next_actions.append(
            "Resolve queue status blockers before deciding whether a source packet is appropriate."
        )

    if public_release_required_count:
        warnings.append(
            "non-public or unknown-origin backfill evidence remains public-release gated"
        )

    return {
        "opportunity_id": stable_id(
            "exception-source-packet-opportunity",
            group_id,
            source_queue_fingerprint,
            status,
            latest_decision_id,
        ),
        "review_group_id": group_id,
        "source_repo": group.get("source_repo", ""),
        "event_type": group.get("event_type", ""),
        "rule_id": group.get("rule_id", ""),
        "review_priority": group.get("review_priority", "info"),
        "review_status": group.get("review_status", ""),
        "candidate_count": int(group.get("candidate_count") or 0),
        "classifier_version_missing_count": missing_count,
        "classifier_version_stale_count": stale_count,
        "classifier_version_reconciled_count": int(
            group.get("classifier_version_reconciled_count") or 0
        ),
        "classifier_version_unreconciled_count": unreconciled_count,
        "classifier_reconciliation_status": group.get(
            "classifier_reconciliation_status",
            "",
        ),
        "public_release_required_count": public_release_required_count,
        "readable_path_ref_count": readable_path_ref_count,
        "path_hash_refs": group.get("path_hash_refs", []),
        "example_event_ids": group.get("example_event_ids", []),
        "source_queue_fingerprint": source_queue_fingerprint,
        "latest_decision": latest_decision_value,
        "latest_decision_id": latest_decision_id,
        "latest_decision_review_status": str((latest_decision or {}).get("review_status") or ""),
        "source_packet_opportunity_status": status,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "command_hints": command_hints,
        "next_actions": next_actions,
        "authority_boundary": (
            "This opportunity is planning evidence only. It does not append review "
            "decisions, stage mail, deliver mail, confirm incidents, approve public "
            "release, or mutate any source repo."
        ),
    }


def _source_packet_opportunity_md_cell(value: Any) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|")


def write_exception_source_packet_opportunities(
    hub_root: Path,
    *,
    output: Path | None = None,
    limit: int = 100,
    example_limit: int = 5,
) -> dict[str, Any]:
    """Report which backfill groups are ready or blocked for source packets."""
    queue = write_exception_backfill_review_queue(
        hub_root,
        limit=MAX_BACKFILL_EVENTS,
        example_limit=example_limit,
        write_outputs=False,
    )
    latest = _latest_backfill_review_decisions_by_group(hub_root)
    input_hashes = {
        str(key): str(value)
        for key, value in _exception_source_packet_opportunity_input_hashes(
            hub_root
        ).items()
    }
    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    status_rank = {
        "source_packet_decision_recommended": 0,
        "decision_exists_request_compilable": 1,
        "blocked_classifier_refresh": 2,
        "blocked_central_readable_ref_review": 3,
        "central_review_required_first": 4,
    }
    for group in queue.get("review_queue", []):
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("review_group_id") or "")
        if not group_id:
            continue
        fingerprint = _backfill_review_queue_fingerprint(
            review_group_id=group_id,
            group=group,
            input_hashes={
                str(key): str(value) for key, value in queue.get("input_hashes", {}).items()
            },
        )
        row = _source_packet_opportunity_for_group(
            group,
            latest_decision=latest.get(group_id),
            source_queue_fingerprint=fingerprint,
        )
        status_counts[str(row["source_packet_opportunity_status"])] += 1
        rows.append(row)

    rows.sort(
        key=lambda row: (
            status_rank.get(str(row.get("source_packet_opportunity_status") or ""), 9),
            priority_rank.get(str(row.get("review_priority") or ""), 9),
            -int(row.get("candidate_count") or 0),
            str(row.get("source_repo") or ""),
            str(row.get("event_type") or ""),
        )
    )
    limit = max(1, min(limit, MAX_BACKFILL_EVENTS))
    reported_rows = rows[:limit]
    report = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "report_id": "dad:exception-source-packet-opportunities",
        "input_hashes": input_hashes,
        "backfill_candidate_count": queue.get("backfill_candidate_count", 0),
        "review_group_count": len(rows),
        "reported_opportunity_count": len(reported_rows),
        "omitted_opportunity_count": max(0, len(rows) - len(reported_rows)),
        "status_counts": dict(sorted(status_counts.items())),
        "current_classifier_version": queue.get("current_classifier_version", ""),
        "decision_ledger": BACKFILL_REVIEW_DECISIONS.as_posix(),
        "source_packet_request_report": SOURCE_PACKET_REQUESTS_JSON.as_posix(),
        "opportunities": reported_rows,
        "authority_boundary": (
            "Source-packet opportunities are read-only planning evidence. They "
            "do not append decisions, stage mail, deliver mail, confirm incidents, "
            "approve public release, promote learning, or mutate source repos."
        ),
    }
    output_path = _default_or_requested_path(hub_root, output, SOURCE_PACKET_OPPORTUNITIES_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = (
        output_path.with_suffix(".md")
        if output
        else exception_data_path(hub_root, SOURCE_PACKET_OPPORTUNITIES_MD)
    )
    lines = [
        "# Exception Source Packet Opportunities",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Review groups: {report['review_group_count']}",
        f"- Reported opportunities: {report['reported_opportunity_count']}",
        f"- Current classifier version: `{report['current_classifier_version']}`",
        "",
        "Boundary: read-only planning evidence. This report does not append review "
        "decisions, stage mail, deliver mail, confirm incidents, or mutate source repos.",
        "",
        "## Status Counts",
        "",
    ]
    lines.extend(f"- `{status}`: {count}" for status, count in report["status_counts"].items())
    lines.extend(["", "## Opportunities", ""])
    lines.append(
        "| Source Repo | Event Type | Status | Candidates | Priority | Next Action |"
    )
    lines.append("| --- | --- | --- | ---: | --- | --- |")
    for row in reported_rows:
        next_action = _source_packet_opportunity_md_cell(
            "; ".join(str(action) for action in row.get("next_actions", []))
        )
        lines.append(
            "| "
            + f"`{_source_packet_opportunity_md_cell(row['source_repo'])}` | "
            + f"`{_source_packet_opportunity_md_cell(row['event_type'])}` | "
            + f"`{_source_packet_opportunity_md_cell(row['source_packet_opportunity_status'])}` | "
            + f"{row['candidate_count']} | "
            + f"`{_source_packet_opportunity_md_cell(row['review_priority'])}` | "
            + f"{next_action} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _append_source_packet_request_cancellations(
    hub_root: Path,
    *,
    latest_decisions: dict[str, dict[str, Any]],
    active_mail_ids: set[str],
) -> int:
    path = exception_data_path(hub_root, SOURCE_PACKET_REQUESTS_STAGED)
    if not path.exists():
        return 0
    rows, errors = _read_jsonl_with_errors(path)
    for error in errors:
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "source_packet_requests_malformed_jsonl.jsonl",
            {
                "event_type": "source_packet_request_malformed_jsonl",
                "created_at": utc_now(),
                "path": SOURCE_PACKET_REQUESTS_STAGED.as_posix(),
                **error,
            },
        )
    canceled = {
        str((row.get("payload") or {}).get("superseded_mail_id") or "")
        for row in rows
        if isinstance(row, dict) and _source_packet_request_is_cancellation(row)
    }
    appended = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("message_type") or "") != "governance_notice":
            continue
        mail_id = str(row.get("mail_id") or "")
        if not mail_id or mail_id in active_mail_ids or mail_id in canceled:
            continue
        group_id = _source_packet_request_group_id(row)
        latest_decision = latest_decisions.get(group_id)
        reason = (
            "latest_decision_changed"
            if latest_decision is not None
            else "no_current_needs_source_packet_decision"
        )
        result = _append_unique_source_packet_mail(
            hub_root,
            _source_packet_request_cancellation_mail(
                row,
                reason=reason,
                latest_decision=latest_decision,
            ),
        )
        if result == "appended":
            appended += 1
    return appended


def write_exception_source_packet_requests(
    hub_root: Path,
    *,
    output: Path | None = None,
    write_mail: bool = True,
) -> dict[str, Any]:
    valid_decisions = _load_valid_backfill_review_decisions_for_requests(hub_root)
    latest = _latest_backfill_review_decisions_by_group(hub_root, rows=valid_decisions)
    _, current_groups, current_fingerprints = _current_backfill_review_group_state(hub_root)
    request_decisions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    skipped_decision_count = 0
    for row in latest.values():
        if str(row.get("decision") or "") != "needs_source_packet":
            continue
        group_id = str(row.get("review_group_id") or "")
        current_group = current_groups.get(group_id)
        if current_group is None:
            skipped_decision_count += 1
            _quarantine_source_packet_request_decision(
                hub_root,
                event_type="source_packet_request_unknown_group",
                decision=row,
                reason="decision review_group_id is absent from the current backfill review queue",
            )
            continue
        mismatches = _source_packet_request_decision_matches_current_group(row, current_group)
        if mismatches:
            skipped_decision_count += 1
            _quarantine_source_packet_request_decision(
                hub_root,
                event_type="source_packet_request_stale_decision",
                decision=row,
                reason="decision fields no longer match current queue group: "
                + ",".join(sorted(mismatches)),
                current_fingerprint=current_fingerprints.get(group_id, ""),
                current_group=current_group,
            )
            continue
        current_fingerprint = current_fingerprints.get(group_id, "")
        if str(row.get("source_queue_fingerprint") or "") != current_fingerprint:
            skipped_decision_count += 1
            _quarantine_source_packet_request_decision(
                hub_root,
                event_type="source_packet_request_fingerprint_mismatch",
                decision=row,
                reason="decision source_queue_fingerprint does not match current queue evidence",
                current_fingerprint=current_fingerprint,
                current_group=current_group,
            )
            continue
        request_decisions.append((row, current_group))
    request_decisions.sort(key=lambda item: str(item[0].get("review_group_id", "")))
    requests: list[dict[str, Any]] = []
    appended_count = 0
    duplicate_count = 0
    rejected_mail_count = 0
    active_mail_ids: set[str] = set()
    for decision, current_group in request_decisions:
        mail_record = _source_packet_request_mail(decision, current_group)
        appended = False
        if write_mail:
            append_status = _append_unique_source_packet_mail(hub_root, mail_record)
            if append_status == "appended":
                appended = True
                appended_count += 1
            elif append_status == "duplicate":
                duplicate_count += 1
            else:
                rejected_mail_count += 1
        active_mail_ids.add(mail_record["mail_id"])
        requests.append(
            {
                "review_group_id": decision.get("review_group_id"),
                "decision_id": decision.get("decision_id"),
                "source_repo": mail_record["target_repo"],
                "event_type": decision.get("event_type"),
                "rule_id": decision.get("rule_id"),
                "mail_id": mail_record["mail_id"],
                "target_repo": mail_record["target_repo"],
                "dedupe_key": mail_record["dedupe_key"],
                "mail_appended": appended,
                "source_queue_fingerprint": decision.get("source_queue_fingerprint"),
            }
        )
    superseded_count = (
        _append_source_packet_request_cancellations(
            hub_root,
            latest_decisions=latest,
            active_mail_ids=active_mail_ids,
        )
        if write_mail
        else 0
    )
    report = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "report_id": "dad:exception-source-packet-requests",
        "decision_count": len(load_exception_backfill_review_decisions(hub_root)),
        "valid_decision_count": len(valid_decisions),
        "latest_group_count": len(latest),
        "request_count": len(requests),
        "skipped_decision_count": skipped_decision_count,
        "mail_appended_count": appended_count,
        "duplicate_mail_count": duplicate_count,
        "rejected_mail_count": rejected_mail_count,
        "superseded_mail_count": superseded_count,
        "mail_stage": SOURCE_PACKET_REQUESTS_STAGED.as_posix(),
        "requests": requests,
        "authority_boundary": (
            "Source-packet requests are DAD-authored staged candidate mail asking a "
            "source repo to confirm, reject, or replace backfill path-signal evidence. "
            "They are intentionally not written to processed/mail/outbox and therefore "
            "are not deliverable by mail deliver until a separate reviewed promotion "
            "step exists. They do not mutate the source repo, create observed "
            "exceptions, or promote lessons."
        ),
    }
    output_path = _default_or_requested_path(hub_root, output, SOURCE_PACKET_REQUESTS_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = (
        output_path.with_suffix(".md")
        if output
        else exception_data_path(hub_root, SOURCE_PACKET_REQUESTS_MD)
    )
    lines = [
        "# Exception Source Packet Requests",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Requests: {report['request_count']}",
        f"- Mail appended: {report['mail_appended_count']}",
        f"- Duplicate mail: {report['duplicate_mail_count']}",
        f"- Mail stage: `{report['mail_stage']}`",
        "",
        "Boundary: staged central candidate mail only. These requests ask for "
        "source confirmation; they are not under processed/mail/outbox, do not "
        "deliver mail, mutate source repos, create observed exceptions, or promote "
        "lessons.",
        "",
        "## Requests",
        "",
        "| Review Group | Source Repo | Event Type | Mail | Appended |",
        "| --- | --- | --- | --- | --- |",
    ]
    for request in requests:
        lines.append(
            "| "
            + f"`{request['review_group_id']}` | `{request['source_repo']}` | "
            + f"`{request['event_type']}` | `{request['mail_id']}` | "
            + f"{request['mail_appended']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


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
        if (
            source_visibility in {"private", "internal", "restricted", "unknown"}
            and not _public_release_is_approved(public_release)
        ):
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
    output_path = _default_or_requested_path(hub_root, output, LEARNING_QUEUE_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = (
        output_path.with_suffix(".md")
        if output
        else exception_data_path(hub_root, LEARNING_QUEUE_MD)
    )
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


def _exception_fix_outcome_request_input_hashes(hub_root: Path) -> dict[str, str]:
    refs = [
        LAKE_PATH,
        FIX_OUTCOME_PATH,
        EXCEPTION_EVENT_TYPE_REGISTRY,
        EXCEPTION_LEARNING_METHODOLOGY,
        Path("schemas") / "exception-event.schema.json",
        Path("schemas") / "exception-fix-outcome.schema.json",
        Path("src") / "digital_asset_directory" / "exceptions_lake.py",
    ]
    hashes: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parents[2]
    for ref in refs:
        path = _exception_input_ref_path(hub_root, ref)
        if not path.exists() and ref.parts[:1] in {("src",), ("schemas",)}:
            path = repo_root / ref
        if path.exists() and path.is_file():
            hashes[ref.as_posix()] = f"sha256:{sha256_file(path)}"
    return hashes


def _fix_outcomes_by_event_id(fix_outcomes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_event: dict[str, list[dict[str, Any]]] = {}
    for outcome in fix_outcomes:
        event_id = str(outcome.get("event_id") or "")
        if event_id:
            by_event.setdefault(event_id, []).append(outcome)
    return by_event


def _event_needs_fix_outcome_request(
    event: dict[str, Any],
    fix_outcomes_by_event: dict[str, list[dict[str, Any]]],
) -> bool:
    event_id = str(event.get("event_id") or "")
    if not event_id or _is_backfill_candidate_event(event):
        return False
    if fix_outcomes_by_event.get(event_id):
        return False
    return str(event.get("outcome_status") or "unresolved") not in {
        "fixed",
        "accepted_risk",
        "duplicate",
        "rejected",
    }


def _fix_outcome_request_event_id(record: dict[str, Any]) -> str:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    source_ref = str(payload.get("source_ref") or "")
    prefix = "dad://exceptions/lake/events/"
    if source_ref.startswith(prefix):
        return source_ref.removeprefix(prefix)
    return str(payload.get("event_id") or "")


def _fix_outcome_request_is_cancellation(record: dict[str, Any]) -> bool:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return (
        str(record.get("message_type") or "") == "review_decision"
        and bool(payload.get("superseded_mail_id"))
        and str(payload.get("superseded_reason") or "").startswith("fix_outcome_request_")
    )


def _append_unique_fix_outcome_request_mail(hub_root: Path, record: dict[str, Any]) -> str:
    path = exception_data_path(hub_root, FIX_OUTCOME_REQUESTS_STAGED)
    mail_record = MailMessageRecord(**record)
    payload = mail_record.model_dump(mode="json")
    issues = _source_packet_mail_semantic_issues(payload)
    if issues:
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "fix_outcome_request_mail_rejected.jsonl",
            {
                "event_type": "fix_outcome_request_mail_rejected",
                "created_at": utc_now(),
                "mail_id": str(payload.get("mail_id") or ""),
                "dedupe_key": str(payload.get("dedupe_key") or ""),
                "issues": issues,
                "record_sha256": sha256_bytes(json_dumps(payload).encode("utf-8")),
            },
        )
        return "rejected"
    new_identity = _mail_record_identity(payload)
    if path.exists():
        rows, errors = _read_jsonl_with_errors(path)
        for error in errors:
            append_jsonl(
                exception_data_path(hub_root, QUARANTINE_DIR)
                / "fix_outcome_requests_malformed_jsonl.jsonl",
                {
                    "event_type": "fix_outcome_request_malformed_jsonl",
                    "created_at": utc_now(),
                    "path": FIX_OUTCOME_REQUESTS_STAGED.as_posix(),
                    **error,
                },
            )
        for row in rows:
            if _mail_record_identity(row) == new_identity:
                return "duplicate"
    append_jsonl(path, payload)
    return "appended"


def _fix_outcome_request_mail(event: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    raw_source_repo = str(event.get("source_repo") or "unknown")
    source_repo = _safe_source_packet_target_ref(raw_source_repo, issues)
    if source_repo != raw_source_repo:
        issues.append("target_ref_redacted_to_hash")
    event_id = str(event.get("event_id") or "unknown")
    event_type = str(event.get("event_type") or "unknown")
    created_at = utc_now()
    event_hash = sha256_bytes(json_dumps(_collision_fields(event)).encode("utf-8"))
    dedupe_key = stable_id(
        "exception-fix-outcome-request",
        event_id,
        event_hash,
    )
    safe_summary = str(event.get("safe_summary") or "")[:300]
    payload = {
        "summary": "DAD needs the source repo or owner to record how this exception was resolved.",
        "source_ref": f"dad://exceptions/lake/events/{event_id}",
        "hash": f"sha256:{event_hash}",
        "event_id": event_id,
        "event_type": event_type,
        "capture_contract": str(event.get("capture_contract") or ""),
        "stage": str(event.get("stage") or ""),
        "severity": str(event.get("severity") or ""),
        "source_visibility": str(event.get("source_visibility") or "unknown"),
        "safe_summary": safe_summary,
        "expected_response_path": FIX_OUTCOME_PATH.as_posix(),
        "allowed_decisions": ["fixed", "rollback", "accepted_risk", "deferred", "duplicate", "rejected"],
        "note": (
            "Record a metadata-only fix outcome, accepted risk, deferral, duplicate, "
            "rejection, or rollback. Do not include diffs, raw logs, private rows, "
            "credentials, or source bodies."
        ),
        "authority_boundary": (
            "This is a staged DAD request for source-owned closure evidence. It does "
            "not prove the exception is fixed and does not authorize repo mutation."
        ),
    }
    if issues:
        payload["screening_issues"] = sorted(set(issues))
    record = MailMessageRecord(
        mail_id=stable_id("mail", "governance_notice", "dad", source_repo, dedupe_key),
        thread_id=stable_id("mail-thread", "dad", source_repo, "fix-outcome", event_id),
        message_type="governance_notice",
        source_repo="dad",
        target_repo=source_repo,
        created_at=created_at,
        dedupe_key=dedupe_key,
        sensitivity="internal",
        review_status="routed_candidate",
        payload=payload,
        evidence=[
            f"event_id:{event_id}",
            f"event_type:{event_type}",
            f"event_hash:sha256:{event_hash}",
            LEARNING_QUEUE_JSON.as_posix(),
            REPORT_JSON.as_posix(),
        ],
        suggested_actions=[
            "Review the event locally in the source repo or with the named owner.",
            "If resolved, append a metadata-only fix outcome with validation and regression refs.",
            "If accepted, deferred, duplicate, or rejected, append that decision with owner authority and expiry where required.",
            "If the event is not real or belongs elsewhere, record a rejection or duplicate outcome rather than editing lake history.",
        ],
        source_provenance={
            "canonical_source_repo": "dad://hub/Digital-Assett-Directory",
            "source_repo_id": "dad",
            "source_repo_alias": "dad",
            "source_visibility": "internal",
            "original_source_chain": ["dad://hub/Digital-Assett-Directory"],
            "return_address": "dad://exceptions/fix-outcome-requests",
            "original_mail_id": "",
            "composed_by": "dad-exceptions-lake",
            "collected_by": "dad",
            "collected_at": "",
            "received_at": created_at,
        },
        public_release={
            "target_visibility": "unknown",
            "target_public_facing": False,
            "public_release_required": False,
            "public_release_status": "not_required",
            "human_release_id": "",
            "release_reason": "central_fix_outcome_request_only",
        },
    )
    return record.model_dump(mode="json")


def _fix_outcome_request_cancellation_mail(
    original: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    created_at = utc_now()
    event_id = _fix_outcome_request_event_id(original)
    original_mail_id = str(original.get("mail_id") or "")
    target_repo = str(original.get("target_repo") or "central_only")
    dedupe_key = stable_id(
        "exception-fix-outcome-request-cancellation",
        original_mail_id,
        event_id,
        reason,
    )
    return MailMessageRecord(
        mail_id=stable_id("mail", "review_decision", "dad", target_repo, dedupe_key),
        thread_id=str(
            original.get("thread_id")
            or stable_id("mail-thread", "dad", target_repo, "fix-outcome", event_id)
        ),
        message_type="review_decision",
        source_repo="dad",
        target_repo=target_repo,
        created_at=created_at,
        dedupe_key=dedupe_key,
        sensitivity="internal",
        review_status="archived",
        payload={
            "summary": "Staged fix-outcome request was superseded before delivery.",
            "source_ref": f"dad://exceptions/lake/events/{event_id}",
            "hash": str((original.get("payload") or {}).get("hash") or ""),
            "superseded_mail_id": original_mail_id,
            "superseded_reason": f"fix_outcome_request_{reason}",
        },
        evidence=[
            f"superseded_mail_id:{original_mail_id}",
            f"event_id:{event_id}",
        ],
        suggested_actions=[
            "Do not promote the superseded staged request into deliverable mail.",
            "Regenerate fix-outcome requests from the current exception lake and fix-outcome ledger.",
        ],
        source_provenance={
            "canonical_source_repo": "dad://hub/Digital-Assett-Directory",
            "source_repo_id": "dad",
            "source_repo_alias": "dad",
            "source_visibility": "internal",
            "original_source_chain": ["dad://hub/Digital-Assett-Directory"],
            "return_address": "dad://exceptions/fix-outcome-requests",
            "original_mail_id": original_mail_id,
            "composed_by": "dad-exceptions-lake",
            "collected_by": "dad",
            "collected_at": "",
            "received_at": created_at,
        },
        public_release={
            "target_visibility": "unknown",
            "target_public_facing": False,
            "public_release_required": False,
            "public_release_status": "not_required",
            "human_release_id": "",
            "release_reason": "superseded_staged_fix_outcome_request",
        },
    ).model_dump(mode="json")


def _append_fix_outcome_request_cancellations(
    hub_root: Path,
    *,
    active_mail_ids: set[str],
) -> int:
    path = exception_data_path(hub_root, FIX_OUTCOME_REQUESTS_STAGED)
    if not path.exists():
        return 0
    rows, errors = _read_jsonl_with_errors(path)
    for error in errors:
        append_jsonl(
            exception_data_path(hub_root, QUARANTINE_DIR)
            / "fix_outcome_requests_malformed_jsonl.jsonl",
            {
                "event_type": "fix_outcome_request_malformed_jsonl",
                "created_at": utc_now(),
                "path": FIX_OUTCOME_REQUESTS_STAGED.as_posix(),
                **error,
            },
        )
    canceled = {
        str((row.get("payload") or {}).get("superseded_mail_id") or "")
        for row in rows
        if isinstance(row, dict) and _fix_outcome_request_is_cancellation(row)
    }
    appended = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("message_type") or "") != "governance_notice":
            continue
        mail_id = str(row.get("mail_id") or "")
        if not mail_id or mail_id in active_mail_ids or mail_id in canceled:
            continue
        result = _append_unique_fix_outcome_request_mail(
            hub_root,
            _fix_outcome_request_cancellation_mail(
                row,
                reason="event_now_has_fix_outcome_or_terminal_status",
            ),
        )
        if result == "appended":
            appended += 1
    return appended


def write_exception_fix_outcome_requests(
    hub_root: Path,
    *,
    output: Path | None = None,
    write_mail: bool = True,
    limit: int = 100,
) -> dict[str, Any]:
    """Stage candidate mail asking source repos to close observed exception events."""
    events = load_lake_events(hub_root)
    fix_outcomes = load_fix_outcomes(hub_root)
    fix_outcomes_by_event = _fix_outcomes_by_event_id(fix_outcomes)
    unresolved_events = [
        event
        for event in events
        if _event_needs_fix_outcome_request(event, fix_outcomes_by_event)
    ]
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    unresolved_events.sort(
        key=lambda event: (
            severity_rank.get(str(event.get("severity") or ""), 9),
            str(event.get("source_repo") or ""),
            str(event.get("event_type") or ""),
            str(event.get("event_id") or ""),
        )
    )
    limit = max(1, min(limit, MAX_BACKFILL_EVENTS))
    reported_events = unresolved_events[:limit]
    requests: list[dict[str, Any]] = []
    appended_count = 0
    duplicate_count = 0
    rejected_mail_count = 0
    active_mail_ids = {
        str(_fix_outcome_request_mail(event).get("mail_id") or "")
        for event in unresolved_events
    }
    for event in reported_events:
        mail_record = _fix_outcome_request_mail(event)
        appended = False
        if write_mail:
            append_status = _append_unique_fix_outcome_request_mail(hub_root, mail_record)
            if append_status == "appended":
                appended = True
                appended_count += 1
            elif append_status == "duplicate":
                duplicate_count += 1
            else:
                rejected_mail_count += 1
        requests.append(
            {
                "event_id": event.get("event_id", ""),
                "event_type": event.get("event_type", ""),
                "source_repo": mail_record["target_repo"],
                "source_visibility": event.get("source_visibility", "unknown"),
                "severity": event.get("severity", "unknown"),
                "mail_id": mail_record["mail_id"],
                "target_repo": mail_record["target_repo"],
                "dedupe_key": mail_record["dedupe_key"],
                "mail_appended": appended,
            }
        )
    superseded_count = (
        _append_fix_outcome_request_cancellations(
            hub_root,
            active_mail_ids=active_mail_ids,
        )
        if write_mail
        else 0
    )
    report = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "report_id": "dad:exception-fix-outcome-requests",
        "input_hashes": _exception_fix_outcome_request_input_hashes(hub_root),
        "observed_event_count": sum(1 for event in events if not _is_backfill_candidate_event(event)),
        "fix_outcome_count": len(fix_outcomes),
        "unresolved_event_count": len(unresolved_events),
        "reported_request_count": len(requests),
        "omitted_request_count": max(0, len(unresolved_events) - len(requests)),
        "mail_appended_count": appended_count,
        "duplicate_mail_count": duplicate_count,
        "rejected_mail_count": rejected_mail_count,
        "superseded_mail_count": superseded_count,
        "mail_stage": FIX_OUTCOME_REQUESTS_STAGED.as_posix(),
        "requests": requests,
        "authority_boundary": (
            "Fix-outcome requests are staged central candidate mail asking the source "
            "repo or owner to record closure evidence. They are not deliverable mail, "
            "not fix outcomes, not proof of repair, and not authorization to mutate "
            "any source repo."
        ),
    }
    output_path = _default_or_requested_path(hub_root, output, FIX_OUTCOME_REQUESTS_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = (
        output_path.with_suffix(".md")
        if output
        else exception_data_path(hub_root, FIX_OUTCOME_REQUESTS_MD)
    )
    lines = [
        "# Exception Fix Outcome Requests",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Observed events: {report['observed_event_count']}",
        f"- Fix outcomes: {report['fix_outcome_count']}",
        f"- Unresolved events: {report['unresolved_event_count']}",
        f"- Reported requests: {report['reported_request_count']}",
        f"- Omitted requests: {report['omitted_request_count']}",
        f"- Mail appended: {report['mail_appended_count']}",
        f"- Duplicate mail: {report['duplicate_mail_count']}",
        f"- Superseded mail: {report['superseded_mail_count']}",
        f"- Mail stage: `{report['mail_stage']}`",
        "",
        "Boundary: staged central candidate mail only. These requests ask for "
        "source-owned closure evidence; they do not deliver mail, mutate source "
        "repos, create fix outcomes, or promote lessons.",
        "",
        "## Requests",
        "",
        "| Event | Source Repo | Type | Severity | Mail | Appended |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for request in requests:
        lines.append(
            "| "
            + f"`{request['event_id']}` | `{request['source_repo']}` | "
            + f"`{request['event_type']}` | `{request['severity']}` | "
            + f"`{request['mail_id']}` | {request['mail_appended']} |"
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
        append_jsonl(exception_data_path(hub_root, FIX_OUTCOME_PATH), record)
        return
    record_exception_fix_outcome(hub_root, repo, **fix_kwargs)


def _record_learning_check_backfill_decision(
    hub_root: Path,
    spec: dict[str, Any],
) -> dict[str, Any]:
    queue = write_exception_backfill_review_queue(
        hub_root,
        output=Path("processed") / "reports" / "synthetic-backfill-review-queue.json",
    )
    event_type = str(spec.get("event_type") or "")
    rule_id = str(spec.get("rule_id") or "")
    matches = [
        row
        for row in queue.get("review_queue", [])
        if isinstance(row, dict)
        and str(row.get("event_type") or "") == event_type
        and (not rule_id or str(row.get("rule_id") or "") == rule_id)
    ]
    if len(matches) != 1:
        raise ValueError(
            "Synthetic backfill review decision expected exactly one matching "
            f"group for event_type={event_type!r}, rule_id={rule_id!r}; found {len(matches)}."
        )
    return record_exception_backfill_review_decision(
        hub_root,
        review_group_id=str(matches[0]["review_group_id"]),
        decision=str(spec.get("decision") or "defer"),
        reviewer=str(spec.get("reviewer") or "synthetic"),
        reviewer_type=str(spec.get("reviewer_type") or "agent"),
        approval_id=str(spec.get("approval_id") or ""),
        source_packet_id=str(spec.get("source_packet_id") or ""),
        notes=str(spec.get("notes") or ""),
        evidence_refs=[str(item) for item in spec.get("evidence_refs", []) or []],
    )


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
            "backfill_decision_counts",
            "quarantine_event_types",
        }
        if not any(expected.get(key) for key in assertion_keys):
            raise ValueError(
                "Exception learning-readiness scenario "
                f"{case_id or index} in {scenarios_path} has no expected assertions."
            )
        decision_event_types = {
            str(item.get("event_type") or "")
            for item in case.get("backfill_review_decisions", []) or []
            if isinstance(item, dict)
        } - {""}
        if decision_event_types:
            status_expected = expected.get("status_by_event_type")
            blocker_expected = expected.get("blocker_substrings_by_event_type")
            if not isinstance(status_expected, dict) or not isinstance(
                blocker_expected,
                dict,
            ):
                raise ValueError(
                    "Exception learning-readiness scenario "
                    f"{case_id or index} with backfill_review_decisions must assert "
                    "status_by_event_type and blocker_substrings_by_event_type."
                )
            missing = sorted(
                event_type
                for event_type in decision_event_types
                if event_type not in status_expected or event_type not in blocker_expected
            )
            if missing:
                raise ValueError(
                    "Exception learning-readiness scenario "
                    f"{case_id or index} lacks promotion-boundary assertions for: "
                    + ", ".join(missing)
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
    temp_parent = source_hub / ".tmp" / "exception-learning-check"
    temp_parent.mkdir(parents=True, exist_ok=True)
    workspace_dir = temp_parent / f"dad-exception-learning-check-{uuid4().hex[:12]}"
    workspace_dir.mkdir(parents=True, exist_ok=False)
    with nullcontext(workspace_dir) as tmp:
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
        for decision_spec in case.get("backfill_review_decisions", []) or []:
            if isinstance(decision_spec, dict):
                _record_learning_check_backfill_decision(hub, decision_spec)
        queue = write_exception_learning_queue(
            hub,
            output=workspace / "learning-queue.json",
            sample_size_threshold=sample_size_threshold,
        )
        decision_summary = summarize_exception_backfill_review_decisions(hub)
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
        if isinstance(expected.get("backfill_decision_counts"), dict):
            comparisons["backfill_decision_counts"] = (
                decision_summary.get("decision_counts") == expected["backfill_decision_counts"]
            )
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
            "backfill_decision_counts": decision_summary.get("decision_counts", {}),
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
        path = _exception_input_ref_path(hub_root, ref)
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
    output_path = _default_or_requested_path(hub_root, output, LEARNING_READINESS_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_dumps(report, pretty=True) + "\n", encoding="utf-8")
    md_path = (
        output_path.with_suffix(".md")
        if output
        else exception_data_path(hub_root, LEARNING_READINESS_MD)
    )
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
        "backfill_review_decisions": BACKFILL_REVIEW_DECISIONS.as_posix(),
        "source_packet_opportunities_json": SOURCE_PACKET_OPPORTUNITIES_JSON.as_posix(),
        "source_packet_opportunities_markdown": SOURCE_PACKET_OPPORTUNITIES_MD.as_posix(),
        "source_packet_requests_json": SOURCE_PACKET_REQUESTS_JSON.as_posix(),
        "source_packet_requests_markdown": SOURCE_PACKET_REQUESTS_MD.as_posix(),
        "source_packet_requests_mail_stage": SOURCE_PACKET_REQUESTS_STAGED.as_posix(),
        "fix_outcome_requests_json": FIX_OUTCOME_REQUESTS_JSON.as_posix(),
        "fix_outcome_requests_markdown": FIX_OUTCOME_REQUESTS_MD.as_posix(),
        "fix_outcome_requests_mail_stage": FIX_OUTCOME_REQUESTS_STAGED.as_posix(),
        "backfill_review_queue_json": BACKFILL_REVIEW_QUEUE_JSON.as_posix(),
        "backfill_review_queue_markdown": BACKFILL_REVIEW_QUEUE_MD.as_posix(),
        "backfill_refresh_plan_json": BACKFILL_REFRESH_PLAN_JSON.as_posix(),
        "backfill_refresh_plan_markdown": BACKFILL_REFRESH_PLAN_MD.as_posix(),
        "learning_queue_json": LEARNING_QUEUE_JSON.as_posix(),
        "learning_queue_markdown": LEARNING_QUEUE_MD.as_posix(),
        "learning_readiness_json": LEARNING_READINESS_JSON.as_posix(),
        "learning_readiness_markdown": LEARNING_READINESS_MD.as_posix(),
        "report_json": REPORT_JSON.as_posix(),
        "report_markdown": REPORT_MD.as_posix(),
    }
