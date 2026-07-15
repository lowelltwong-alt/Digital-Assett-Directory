"""Read-only weekly capacity review sidecar for the DAD Portfolio OS.

The sidecar consumes only normalized, metadata-only evidence. It never scans
arbitrary source contents, dispatches an agent, records a decision, changes a
repository, or activates a schedule. Missing mission authority is represented
as unknown rather than inferred from activity, age, similarity, or volume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from .ids import stable_id
from .portfolio_cockpit import schema_validation_problems
from .transport import data_path
from .utils import atomic_write_text, json_dumps


SCHEMA_VERSION = "dad.portfolio_capacity_review.v0_1"
MISSION_SCHEMA_VERSION = "dad.repo-missions.v1"
METHOD_ID = "dad.portfolio-capacity-review.v0_1"
BUILDER_CONTRACT_REVISION = "dad.portfolio-capacity-review.builder.v0_1"
METHODOLOGY_REF = (
    "assets/agent-skills/personal-portfolio-capacity-review/"
    "references/PORTFOLIO_CAPACITY_REVIEW_CONTRACT.md"
)
MISSION_RELATIVE_PATH = Path(".digital-asset") / "portfolio" / "missions.json"

SOURCE_CONTRACT: dict[str, dict[str, Any]] = {
    "portfolio_review": {
        "lane_id": "portfolio_flow",
        "source_kind": "portfolio_projection",
        "schema_versions": ("dad.portfolio_review_packet.v2",),
        "required": True,
    },
    "portfolio_attention": {
        "lane_id": "git_and_worktree_state",
        "source_kind": "worktree",
        "schema_versions": ("dad.portfolio_attention.v1",),
        "required": True,
    },
    "roadmap": {
        "lane_id": "roadmap_and_acceptance_state",
        "source_kind": "roadmap",
        "schema_versions": ("dad.roadmap.status.adapter.v1",),
        "required": True,
    },
    "subagent_role_directory": {
        "lane_id": "role_revision_and_evaluation_state",
        "source_kind": "subagent_evaluation",
        "schema_versions": (
            "dad.subagent.role_directory.v1",
            "dad.subagent_role_directory.v1",
        ),
        "required": True,
    },
    "agent_skill_registry": {
        "lane_id": "skill_and_library_state",
        "source_kind": "skill_library",
        "schema_versions": ("0.1.0",),
        "required": True,
    },
    "asset_registry": {
        "lane_id": "skill_and_library_state",
        "source_kind": "registry",
        "schema_versions": ("0.1.0",),
        "required": True,
    },
    "coding_asset_registry": {
        "lane_id": "skill_and_library_state",
        "source_kind": "registry",
        "schema_versions": ("0.1.0",),
        "required": True,
    },
    "subagent_evaluation_profiles": {
        "lane_id": "role_revision_and_evaluation_state",
        "source_kind": "subagent_evaluation",
        "schema_versions": ("0.1.0",),
        "required": True,
    },
    "learning_loop_status": {
        "lane_id": "learning_loop_outcomes",
        "source_kind": "learning_loop",
        "schema_versions": ("dad.learning_loop.status.v1",),
        "required": True,
    },
    "iteration_measurements": {
        "lane_id": "measured_iteration_evidence",
        "source_kind": "measurement",
        "schema_versions": ("dad.iteration_measurements.v1",),
        "required": True,
    },
    "daemon": {
        "lane_id": "routine_and_daemon_health",
        "source_kind": "daemon",
        "schema_versions": ("dad.daemon.status.v1",),
        "required": True,
    },
    "scheduled_tasks": {
        "lane_id": "routine_and_daemon_health",
        "source_kind": "routine",
        "schema_versions": ("dad.daemon.scheduled_tasks.v1",),
        "required": True,
    },
    "research_freshness": {
        "lane_id": "research_and_mission_freshness",
        "source_kind": "repository",
        "schema_versions": ("dad.research_freshness.v1",),
        "required": True,
    },
    "daily_review": {
        "lane_id": "portfolio_flow",
        "source_kind": "portfolio_projection",
        "schema_versions": ("dad.daily_review_queue.v1",),
        "required": False,
    },
    "mail": {
        "lane_id": "operational_health",
        "source_kind": "repository",
        "schema_versions": ("dad.mail.digest.status.v1",),
        "required": False,
    },
    "journal": {
        "lane_id": "operational_health",
        "source_kind": "routine",
        "schema_versions": ("dad.journal.status.v1",),
        "required": False,
    },
    "transport": {
        "lane_id": "authority_privacy_and_integrity",
        "source_kind": "repository",
        "schema_versions": ("0.1.0", "dad.transport.audit.v1"),
        "required": False,
    },
    "execution": {
        "lane_id": "authority_privacy_and_integrity",
        "source_kind": "repository",
        "schema_versions": ("dad.portfolio_execution_control.v1",),
        "required": False,
    },
}
REQUIRED_SOURCE_IDS = tuple(
    source_id for source_id, contract in SOURCE_CONTRACT.items() if contract["required"]
)

PRECEDENCE_BANDS = (
    "authority_privacy_security_integrity_gate",
    "human_decision_wait",
    "dirty_or_conflicted_unique_value_risk",
    "accepted_dependency_unlock",
    "accepted_outcome_capability_learning_gap",
    "measured_iteration_cycle_drag",
    "routine_or_daemon_degradation",
    "research_or_mission_freshness_debt",
)
_BAND_ORDER = {band: index for index, band in enumerate(PRECEDENCE_BANDS)}
MISSION_STATES = ("current", "stale", "missing", "invalid", "unknown")
MATURITY_STATES = (
    "planned_only",
    "partially_implemented",
    "implemented_unvalidated",
    "validated_not_adopted",
    "active_current",
    "stale",
    "superseded",
    "unknown",
)
PRIVACY_CLASSES = ("C0", "C1", "C2")
BOTTLENECK_CATEGORIES = (
    "human_decision",
    "worktree_or_handoff",
    "planned_or_partial_buildout",
    "skill_or_subagent_maturity",
    "learning_loop",
    "iteration_cycle",
    "routine_or_daemon",
    "dependency_frontier",
    "attention_or_compute",
    "mission_or_architecture_drift",
)
CATEGORY_PRECEDENCE = {
    "human_decision": "human_decision_wait",
    "worktree_or_handoff": "dirty_or_conflicted_unique_value_risk",
    "planned_or_partial_buildout": "accepted_outcome_capability_learning_gap",
    "skill_or_subagent_maturity": "accepted_outcome_capability_learning_gap",
    "learning_loop": "accepted_outcome_capability_learning_gap",
    "iteration_cycle": "measured_iteration_cycle_drag",
    "routine_or_daemon": "routine_or_daemon_degradation",
    "dependency_frontier": "accepted_dependency_unlock",
    "attention_or_compute": "research_or_mission_freshness_debt",
    "mission_or_architecture_drift": "research_or_mission_freshness_debt",
}
_KNOWN_SOURCE_CURRENT_STATES = {
    "active",
    "available",
    "candidate",
    "candidate_seed",
    "complete",
    "current",
    "fresh",
    "generated",
    "generated_candidate",
    "healthy",
    "installed_candidate",
    "observed",
    "ok",
    "passed",
    "ready",
}
_SAFE_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,299}$")
_RAW_PATH_RE = re.compile(
    r"(?:(?:[A-Za-z]:[\\/])|(?:\\\\[^\\/\s]+[\\/])|"
    r"(?:^|(?<=[\s\"'=(]))/(?!/)[^\s\"'<>]+|(?:^|(?<=[\s\"'=(]))~[\\/])",
    re.IGNORECASE,
)
_FORBIDDEN_ACTION_FIELDS = frozenset(
    {
        "apply",
        "approve",
        "approval_granted",
        "dispatch",
        "execute",
        "execution_enabled",
        "notify",
        "schedule",
    }
)
_FORBIDDEN_SCORE_FIELDS = frozenset(
    {"score", "priority_score", "capacity_score", "leverage_score", "risk_score"}
)
_C3_FIELD_NAMES = frozenset(
    {"c3_payload_included", "client_payload_included", "raw_payload_included"}
)
_WORKER_ROLE_IDS = frozenset(
    {
        "capability-maturity-and-cycle-auditor",
        "delivery-closeout-resumption-steward",
        "dependency-critical-frontier-analyst",
        "evaluation-integrity-auditor",
        "improvement-layer-router",
        "luna-trigger-observer",
        "neglected-worktree-triage-manager",
        "portfolio-scrum-board-curator",
        "research-project-workflow-steward",
    }
)
_EVIDENCE_STATUS_ORDER = {"confirmed": 0, "inferred": 1, "disputed": 2, "unknown": 3}
_MEASUREMENT_UNITS = frozenset(
    {"seconds", "milliseconds", "minutes", "items_per_second", "requests_per_second"}
)
_MISSING = object()
_SOURCE_REQUIRED_SHAPES: dict[str, dict[str, type]] = {
    "portfolio_review": {"dashboard": dict, "blockers": list, "unknowns": list, "health": list},
    "portfolio_attention": {"attention_queue": list, "projects": list},
    "roadmap": {"last_checked_at": str, "phases": dict},
    "subagent_role_directory": {"roles": list},
    "agent_skill_registry": {"skills": list},
    "asset_registry": {"assets": list},
    "coding_asset_registry": {"assets": list},
    "subagent_evaluation_profiles": {"profiles": list},
    "learning_loop_status": {"open_without_outcome_count": int},
    "iteration_measurements": {"observations": list},
    "daemon": {"generated_at": str, "stale": bool, "status": str},
    "scheduled_tasks": {"generated_at": str, "inspect_scheduler": bool, "tasks": list},
    "research_freshness": {"generated_at": str, "sources": list},
}
_SOURCE_FRESH_AFTER_HOURS: dict[str, int] = {
    "portfolio_review": 26,
    "portfolio_attention": 168,
    "roadmap": 26,
    "subagent_role_directory": 168,
    "learning_loop_status": 168,
    "iteration_measurements": 168,
    "daemon": 26,
    "scheduled_tasks": 26,
    "research_freshness": 168,
}
_ROADMAP_DECLARED_STATES = frozenset(
    {
        "active",
        "awaiting_human_gate",
        "blocked",
        "boundary_deferred",
        "complete",
        "in_progress",
        "planned",
        "superseded",
    }
)
_ROADMAP_COMPUTED_STATES = frozenset(
    {
        "awaiting_human_gate",
        "awaiting_validation_evidence",
        "blocked",
        "boundary_deferred",
        "complete",
        "planned",
    }
)
_REGISTRY_RECORD_STATES = frozenset(
    {"active", "candidate", "planned", "partial", "superseded", "retired"}
)
_REGISTRY_REVIEW_STATES = frozenset(
    {
        "candidate",
        "installed_for_local_reuse",
        "reviewed",
        "superseded",
        "retired",
        "unreviewed",
        "insufficient_evidence",
        "wave_0_installed_for_candidate_rollout_planning",
    }
)
_RESEARCH_SOURCE_STATES = frozenset(
    {"current", "fresh", "reviewed", "stale", "expired", "missing", "invalid", "unknown"}
)
_ATTENTION_REASONS = frozenset(
    {
        "conflicted_worktree",
        "dirty_worktree",
        "dirty_worktree_idle",
        "diverged_from_upstream",
        "merged_branch_cleanup_candidate",
        "no_upstream_tracking",
        "stale_branch",
        "stale_branch_in_active_project",
        "unpushed_or_unmerged_commits",
        "upstream_gone",
    }
)
_VOLATILE_TIME_KEYS = frozenset(
    {
        "audited_at",
        "checked_at",
        "created_at",
        "generated_at",
        "last_checked_at",
        "observed_at",
        "updated_at",
        "verified_at",
    }
)

AUTHORITY_BOUNDARY = (
    "This local-private weekly capacity report is candidate evidence only. It cannot "
    "infer repository missions, establish priority, approve dependencies, mutate source "
    "repositories, dispatch agents, record decisions, schedule routines, notify people, "
    "or authorize execution. Source owners and Lowell retain those authorities."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CapacityReviewSettings:
    human_ask_limit: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.human_ask_limit <= 3:
            raise ValueError("human_ask_limit must be between 1 and 3")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _material_value(value: Any) -> Any:
    """Drop presentation timestamps while retaining state and freshness labels."""

    if isinstance(value, dict):
        return {
            str(key): _material_value(child)
            for key, child in value.items()
            if str(key).casefold() not in _VOLATILE_TIME_KEYS
        }
    if isinstance(value, list):
        return [_material_value(child) for child in value]
    return value


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _safe_code(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text if _SAFE_CODE_RE.fullmatch(text) else fallback


def _safe_non_path_code(value: Any, fallback: str) -> str:
    text = _safe_code(value, "")
    return text if text and not _RAW_PATH_RE.search(text) else fallback


def _safe_codes(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return sorted(
        {
            _safe_code(value, "detail_omitted")
            for value in values
            if str(value or "").strip()
        }
    )


def _safe_relative_ref(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text or _RAW_PATH_RE.search(text) or text.startswith("../") or "/../" in text:
        return ""
    return text if _SAFE_CODE_RE.fullmatch(text) else ""


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _strict_bool(value: Any = _MISSING, *, field: str, default: bool = False) -> bool:
    if value is _MISSING:
        return default
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")
    return value


def _reject_prohibited_input(
    value: Any, *, context: str, allow_score_fields: bool = False
) -> None:
    for path, child in _walk(value):
        if not path:
            continue
        field = path[-1].casefold()
        if field in _FORBIDDEN_ACTION_FIELDS:
            raise ValueError(f"forbidden action field in {context}: {field}")
        if field in _FORBIDDEN_SCORE_FIELDS and not allow_score_fields:
            raise ValueError(f"composite or priority scores are prohibited in {context}")
        if field in _C3_FIELD_NAMES and child is not False:
            raise ValueError(f"C3 payload flag is prohibited in {context}")
        if field in {"privacy_class", "data_classification", "maximum_classification"}:
            classification = str(child or "").strip().upper()
            if classification.startswith("C3") or classification.startswith("C4"):
                raise ValueError(f"C3/C4 input is prohibited in {context}")


def _capacity_source_projection(source_id: str, value: Any) -> Any:
    """Project trusted source fields before fingerprinting or candidate creation."""

    if source_id != "portfolio_attention" or not isinstance(value, Mapping):
        return value

    # The upstream portfolio report contains presentation-only priority and
    # similarity scores plus absolute worktree paths. They are not capacity
    # evidence. Still inspect the complete raw envelope for action and C3/C4
    # violations before discarding fields the capacity contract does not use.
    _reject_prohibited_input(
        value,
        context="source:portfolio_attention:raw_envelope",
        allow_score_fields=True,
    )
    projected_rows: list[Any] = []
    for row in value.get("attention_queue", []):
        if not isinstance(row, Mapping):
            projected_rows.append(row)
            continue
        projected_rows.append(
            {
                "project_id": row.get("project_id"),
                "branch": row.get("branch"),
                "reasons": row.get("reasons"),
            }
        )
    projected: dict[str, Any] = {
        "schema_version": value.get("schema_version"),
        "generated_at": value.get("generated_at"),
        "status": value.get("status"),
        "attention_queue": projected_rows,
        "projects": [],
    }
    if "stale" in value:
        projected["stale"] = value.get("stale")
    return projected


def _source_schema_version(value: Mapping[str, Any]) -> str:
    for key in ("schema_version", "registry_version"):
        text = str(value.get(key, "")).strip()
        if text:
            return text
    return ""


def _scheduled_state(source_id: str, value: Mapping[str, Any]) -> str:
    if source_id != "scheduled_tasks":
        scheduled = value.get("scheduled", _MISSING)
        if scheduled is _MISSING:
            return "unknown"
        return "scheduled" if _strict_bool(scheduled, field="scheduled") else "not_scheduled"
    inspected = value.get("inspect_scheduler")
    if inspected is not True:
        return "unknown"
    tasks = value.get("tasks")
    if not isinstance(tasks, list):
        return "unknown"
    installed = [
        task.get("scheduler", {}).get("installed")
        for task in tasks
        if isinstance(task, Mapping) and isinstance(task.get("scheduler"), Mapping)
    ]
    if any(item is True for item in installed):
        return "scheduled"
    if installed and all(item is False for item in installed):
        return "not_scheduled"
    return "unknown"


def _nested_source_problems(source_id: str, value: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if source_id == "portfolio_attention":
        for row in value.get("attention_queue", []):
            if not isinstance(row, Mapping):
                problems.append("attention_row_not_object")
                continue
            reasons = row.get("reasons")
            if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
                problems.append("attention_reasons_not_string_list")
            elif set(reasons) - _ATTENTION_REASONS:
                problems.append("attention_reason_unknown")
            for field in ("project_id", "branch"):
                field_value = row.get(field)
                if not isinstance(field_value, str) or not _safe_non_path_code(field_value, ""):
                    problems.append(f"attention_{field}_invalid")
    elif source_id == "roadmap":
        for phase_id, phase in value.get("phases", {}).items():
            if not isinstance(phase_id, str) or not _safe_non_path_code(phase_id, ""):
                problems.append("roadmap_phase_id_invalid")
            if not isinstance(phase, Mapping):
                problems.append("roadmap_phase_not_object")
                continue
            if str(phase.get("declared_status", "")) not in _ROADMAP_DECLARED_STATES:
                problems.append("roadmap_declared_status_unknown")
            if str(phase.get("computed_status", "")) not in _ROADMAP_COMPUTED_STATES:
                problems.append("roadmap_computed_status_unknown")
            dependencies = phase.get("blocked_dependencies", [])
            if not isinstance(dependencies, list) or any(
                not isinstance(item, str) or not _safe_non_path_code(item, "")
                for item in dependencies
            ):
                problems.append("roadmap_blocked_dependencies_invalid")
    elif source_id in {
        "agent_skill_registry",
        "asset_registry",
        "coding_asset_registry",
        "subagent_evaluation_profiles",
    }:
        collection_name = "skills" if source_id == "agent_skill_registry" else "assets"
        if source_id == "subagent_evaluation_profiles":
            collection_name = "profiles"
        for row in value.get(collection_name, []):
            if not isinstance(row, Mapping):
                problems.append("registry_record_not_object")
                continue
            status = row.get("status", _MISSING)
            review_status = row.get("review_status", _MISSING)
            if status is not _MISSING and str(status) not in _REGISTRY_RECORD_STATES:
                problems.append("registry_status_unknown")
            if review_status is not _MISSING and str(review_status) not in _REGISTRY_REVIEW_STATES:
                problems.append("registry_review_status_unknown")
    elif source_id == "learning_loop_status":
        count = value.get("open_without_outcome_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            problems.append("learning_outcome_count_invalid")
    elif source_id == "iteration_measurements":
        for row in value.get("observations", []):
            if not isinstance(row, Mapping) or set(row) != {"subject_ref", "measurement"}:
                problems.append("iteration_observation_shape_invalid")
                continue
            if not isinstance(row.get("subject_ref"), str) or not _safe_non_path_code(
                row.get("subject_ref"), ""
            ):
                problems.append("iteration_subject_ref_invalid")
            try:
                _validated_iteration_measurement(row.get("measurement"))
            except ValueError:
                problems.append("iteration_measurement_invalid")
    elif source_id == "research_freshness":
        for row in value.get("sources", []):
            if not isinstance(row, Mapping):
                problems.append("research_source_not_object")
                continue
            source_ref = row.get("source_id")
            status = row.get("status")
            if not isinstance(source_ref, str) or not _safe_non_path_code(source_ref, ""):
                problems.append("research_source_id_invalid")
            if not isinstance(status, str) or status not in _RESEARCH_SOURCE_STATES:
                problems.append("research_source_status_unknown")
    return sorted(set(problems))


def _source_descriptor(
    source_id: str, value: Any, *, observed_at: datetime
) -> dict[str, Any]:
    if source_id not in SOURCE_CONTRACT:
        raise ValueError(f"unknown capacity source id: {source_id}")
    contract = SOURCE_CONTRACT[source_id]
    if value is None:
        return {
            "source_id": source_id,
            "lane_id": contract["lane_id"],
            "source_kind": contract["source_kind"],
            "schema_version": "",
            "required": bool(contract["required"]),
            "status": "missing",
            "freshness_status": (
                "unknown"
                if source_id in _SOURCE_FRESH_AFTER_HOURS
                else "not_applicable"
            ),
            "fresh_after_hours": _SOURCE_FRESH_AFTER_HOURS.get(source_id),
            "consumption_status": "unavailable",
            "scheduled_state": "unknown",
            "evidence_refs": [f"source:{source_id}"],
            "problems": ["source_missing"],
        }
    if not isinstance(value, Mapping):
        return {
            "source_id": source_id,
            "lane_id": contract["lane_id"],
            "source_kind": contract["source_kind"],
            "schema_version": "",
            "required": bool(contract["required"]),
            "status": "invalid",
            "scheduled_state": "unknown",
            "freshness_status": (
                "unknown"
                if source_id in _SOURCE_FRESH_AFTER_HOURS
                else "not_applicable"
            ),
            "fresh_after_hours": _SOURCE_FRESH_AFTER_HOURS.get(source_id),
            "consumption_status": "invalid",
            "evidence_refs": [f"source:{source_id}:invalid_scalar"],
            "problems": ["source_not_structured"],
        }
    _reject_prohibited_input(value, context=f"source:{source_id}")
    schema_version = _source_schema_version(value)
    raw_status = str(value.get("status") or "observed").strip().casefold()
    try:
        stale_flag = _strict_bool(
            value.get("stale", _MISSING), field=f"{source_id}.stale"
        )
        scheduled_state = _scheduled_state(source_id, value)
    except ValueError:
        stale_flag = False
        scheduled_state = "unknown"
        raw_status = "invalid"
    problems: list[str] = []
    required_shape = _SOURCE_REQUIRED_SHAPES.get(source_id, {})
    shape_valid = True
    for field, expected_type in required_shape.items():
        field_value = value.get(field, _MISSING)
        if field_value is _MISSING or type(field_value) is not expected_type:
            shape_valid = False
            problems.append(f"source_shape_invalid:{field}")
    nested_problems = _nested_source_problems(source_id, value) if shape_valid else []
    if nested_problems:
        problems.extend(nested_problems)
    status_known = raw_status in _KNOWN_SOURCE_CURRENT_STATES or raw_status in {
        "invalid",
        "error",
        "failed",
        "missing",
        "unavailable",
        "stale",
        "in_progress",
        "skipped",
        "dirty_needs_review",
    }
    if not status_known:
        problems.append("unknown_source_status")
    if schema_version not in contract["schema_versions"]:
        status = "invalid"
        problems.append("unsupported_source_schema_version")
    elif not shape_valid or nested_problems:
        status = "invalid"
    elif not status_known or raw_status in {"invalid", "error", "failed"}:
        status = "invalid"
    elif raw_status in {"missing", "unavailable"}:
        status = "missing"
    elif stale_flag or raw_status in {"stale", "in_progress", "skipped", "dirty_needs_review"}:
        status = "stale"
    elif raw_status in _KNOWN_SOURCE_CURRENT_STATES:
        status = "current"
    else:
        status = "invalid"

    freshness_limit = _SOURCE_FRESH_AFTER_HOURS.get(source_id)
    freshness_status = "not_applicable" if freshness_limit is None else "unknown"
    if freshness_limit is not None and status not in {"invalid", "missing"}:
        timestamp = next(
            (
                _parse_time(value.get(field))
                for field in ("generated_at", "last_checked_at", "checked_at", "observed_at")
                if value.get(field)
            ),
            None,
        )
        if timestamp is None:
            status = "stale"
            freshness_status = "unknown"
            problems.append("source_freshness_timestamp_missing")
        else:
            age_hours = (observed_at - timestamp).total_seconds() / 3_600
            if age_hours < -1:
                status = "invalid"
                freshness_status = "invalid"
                problems.append("source_freshness_timestamp_in_future")
            elif age_hours > freshness_limit:
                status = "stale"
                freshness_status = "stale"
                problems.append("source_freshness_expired")
            else:
                freshness_status = "current"
    if status != "current" and f"source_{status}" not in problems:
        problems.append(f"source_{status}")
    return {
        "source_id": source_id,
        "lane_id": contract["lane_id"],
        "source_kind": contract["source_kind"],
        "schema_version": schema_version,
        "required": bool(contract["required"]),
        "status": status,
        "freshness_status": freshness_status,
        "fresh_after_hours": freshness_limit,
        "consumption_status": (
            "consumed"
            if status == "current"
            else "invalid"
            if status == "invalid"
            else "unavailable"
        ),
        "scheduled_state": scheduled_state,
        "evidence_refs": [
            f"source:{source_id}:hash:{_canonical_hash(_material_value(value))}"
        ],
        "problems": problems,
    }


def load_repo_mission_coverage(
    repo_roots: Sequence[Path],
    *,
    schema_root: Path,
    now: datetime | None = None,
    fresh_after_days: int = 120,
) -> list[dict[str, Any]]:
    """Read only source-owned mission manifests from explicitly supplied roots."""

    if fresh_after_days < 1:
        raise ValueError("fresh_after_days must be at least 1")
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in repo_roots:
        try:
            resolved = Path(root).expanduser().resolve()
        except OSError:
            resolved = Path(root).absolute()
        path_key = os.path.normcase(str(resolved))
        if path_key in seen:
            continue
        seen.add(path_key)
        repo_id = stable_id(METHOD_ID, "repo", path_key)
        mission_path = resolved / MISSION_RELATIVE_PATH
        if not mission_path.exists():
            rows.append(
                {
                    "repo_id": repo_id,
                    "mission_id": "",
                    "status": "missing",
                    "source_ref": MISSION_RELATIVE_PATH.as_posix(),
                    "verified_at": None,
                    "problems": ["mission_contract_missing"],
                }
            )
            continue
        try:
            raw = mission_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            rows.append(
                {
                    "repo_id": repo_id,
                    "mission_id": "",
                    "status": "invalid",
                    "source_ref": MISSION_RELATIVE_PATH.as_posix(),
                    "verified_at": None,
                    "problems": ["mission_contract_invalid_json"],
                }
            )
            continue
        if not isinstance(payload, dict):
            problems = ["mission_contract_not_object"]
        else:
            problems = schema_validation_problems(payload, schema_root, "repo_missions")
        if problems:
            rows.append(
                {
                    "repo_id": repo_id,
                    "mission_id": "",
                    "status": "invalid",
                    "source_ref": MISSION_RELATIVE_PATH.as_posix(),
                    "verified_at": None,
                    "problems": ["mission_contract_schema_invalid"],
                }
            )
            continue

        repo_ref = str(payload.get("repo_ref", ""))
        declared_repo_id = _safe_code(repo_ref.rsplit("/", 1)[-1], repo_id)
        mission_id = stable_id(METHOD_ID, "mission", repo_ref or declared_repo_id)
        tracks = payload.get("tracks", [])
        registry_reviewed = str(payload.get("status", "")).casefold() == "reviewed"
        tracks_reviewed = bool(tracks) and all(
            isinstance(track, dict)
            and str(track.get("review_status", "")).casefold() == "reviewed"
            for track in tracks
        )
        reviewed_at = _parse_time(payload.get("reviewed_at"))
        if registry_reviewed and tracks_reviewed and reviewed_at is not None:
            age_days = (observed_at - reviewed_at).total_seconds() / 86_400
            if age_days < 0:
                status = "invalid"
                status_problems = ["mission_reviewed_at_in_future"]
            elif age_days > fresh_after_days:
                status = "stale"
                status_problems = ["mission_review_expired"]
            else:
                status = "current"
                status_problems = []
            verified_at = observed_at.isoformat()
        else:
            status = "unknown"
            status_problems = ["mission_contract_not_human_reviewed"]
            verified_at = None
        rows.append(
            {
                "repo_id": declared_repo_id,
                "mission_id": mission_id,
                "status": status,
                "source_ref": MISSION_RELATIVE_PATH.as_posix(),
                "verified_at": verified_at,
                "problems": status_problems,
            }
        )
    return sorted(rows, key=lambda row: row["repo_id"])


def _candidate(
    *,
    category: str,
    subject_ref: str,
    evidence_refs: Sequence[str],
    human_decision_required: bool = False,
    accepted_dependency: bool = False,
    privacy_class: str = "C1",
    state: str = "open",
    counterevidence: Sequence[str] = (),
    unknowns: Sequence[str] = (),
    agent_revision_ids: Sequence[str] = (),
    evaluation_status: str = "insufficient_evidence",
    title: str = "capacity_bottleneck_candidate",
    why_it_constrains_capacity: str = "bounded_evidence_requires_review",
    expected_unlock: str = "validated_next_action_or_quiet_default",
    smallest_next_action: str = "inspect_bounded_evidence",
    quiet_option: str = "keep_visible_without_nudge",
    falsifier: str = "new_authoritative_evidence",
    authority_gate: str = "source_owner_or_lowell",
    evidence_status: str = "inferred",
    precedence_class: str = "",
    rollback_ref: str = "",
    accepted_unlock_ref: str = "",
    falsifier_ref: str = "",
    suppress_reason: str = "",
    wake_conditions: Sequence[str] = (),
) -> dict[str, Any]:
    if category not in BOTTLENECK_CATEGORIES:
        raise ValueError(f"unknown capacity category: {category}")
    if privacy_class not in PRIVACY_CLASSES:
        raise ValueError("C3 and unknown privacy classes are prohibited from capacity reports")
    if evidence_status not in {"confirmed", "inferred", "disputed", "unknown"}:
        raise ValueError(f"unknown evidence status: {evidence_status}")
    precedence = precedence_class or CATEGORY_PRECEDENCE[category]
    if precedence not in PRECEDENCE_BANDS:
        raise ValueError(f"unknown precedence class: {precedence}")
    subject = _safe_code(subject_ref, stable_id(METHOD_ID, "subject"))
    evidence = _safe_codes(evidence_refs)
    bottleneck_id = stable_id(METHOD_ID, "bottleneck", category, subject)
    return {
        "bottleneck_id": bottleneck_id,
        "category": category,
        "precedence_class": precedence,
        "evidence_status": evidence_status,
        "title": _safe_code(title, "capacity_bottleneck_candidate"),
        "why_it_constrains_capacity": _safe_code(
            why_it_constrains_capacity, "bounded_evidence_requires_review"
        ),
        "expected_unlock": _safe_code(
            expected_unlock, "validated_next_action_or_quiet_default"
        ),
        "evidence_refs": evidence,
        "counterevidence": _safe_codes(counterevidence),
        "falsifier": _safe_code(falsifier, "new_authoritative_evidence"),
        "safe_default": _safe_code(quiet_option, "keep_visible_without_nudge"),
        "smallest_next_action": _safe_code(
            smallest_next_action, "inspect_bounded_evidence"
        ),
        "authority_gate": _safe_code(authority_gate, "source_owner_or_lowell"),
        "_subject_ref": subject,
        "_state": state,
        "_human_decision_required": bool(human_decision_required),
        "_accepted_dependency": bool(accepted_dependency),
        "_privacy_class": privacy_class,
        "_source_fingerprint": _canonical_hash([category, subject, evidence]),
        "_unknowns": _safe_codes(unknowns),
        "_agent_revision_ids": _safe_codes(agent_revision_ids),
        "_evaluation_status": _safe_code(evaluation_status, "insufficient_evidence"),
        "_rollback_ref": _safe_code(rollback_ref, "") if rollback_ref else "",
        "_accepted_unlock_ref": (
            _safe_code(accepted_unlock_ref, "") if accepted_unlock_ref else ""
        ),
        "_falsifier_ref": _safe_code(falsifier_ref, "") if falsifier_ref else "",
        "_suppress_reason": _safe_code(suppress_reason, "") if suppress_reason else "",
        "_wake_conditions": _safe_codes(wake_conditions),
    }


def _public_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in row.items() if not str(key).startswith("_")}


def _review_candidates(review_packet: Any) -> list[dict[str, Any]]:
    if not isinstance(review_packet, dict):
        return []
    candidates: list[dict[str, Any]] = []
    dashboard = review_packet.get("dashboard", {})
    if isinstance(dashboard, dict):
        for row in dashboard.get("now", []):
            if not isinstance(row, dict):
                continue
            subject = _safe_code(
                row.get("subject_ref"), stable_id(METHOD_ID, "review-now", str(len(candidates)))
            )
            candidates.append(
                _candidate(
                    category="human_decision",
                    subject_ref=subject,
                    evidence_refs=["portfolio_review:dashboard:now"],
                    human_decision_required=True,
                    title="human_decision_wait",
                    why_it_constrains_capacity="accepted_work_waits_for_human_authority",
                    expected_unlock="decision_packet_releases_or_quiets_blocked_work",
                    smallest_next_action="prepare_decision_ready_packet",
                    falsifier="decision_no_longer_blocks_accepted_work",
                )
            )
    for collection, default_category in (
        ("blockers", "human_decision"),
        ("unknowns", "attention_or_compute"),
    ):
        for row in review_packet.get(collection, []):
            if not isinstance(row, dict):
                continue
            subject = _safe_code(
                row.get("ref") or row.get("issue_id"),
                stable_id(METHOD_ID, collection, str(len(candidates))),
            )
            candidates.append(
                _candidate(
                    category=default_category,
                    subject_ref=subject,
                    evidence_refs=[f"portfolio_review:{collection}"],
                    human_decision_required=collection == "blockers",
                    unknowns=[str(row.get("kind") or "source_issue")],
                    title=f"portfolio_review_{collection}",
                    why_it_constrains_capacity="review_packet_contains_unresolved_evidence",
                    expected_unlock="current_source_receipt_or_explicit_disposition",
                    smallest_next_action="inspect_source_health",
                    falsifier="source_health_receipt_is_current_and_valid",
                )
            )
    for row in review_packet.get("health", []):
        if not isinstance(row, dict) or str(row.get("status", "")) in {
            "ready",
            "not_applicable",
        }:
            continue
        subject = _safe_code(
            row.get("health_id") or row.get("lane_id"),
            stable_id(METHOD_ID, "health", str(len(candidates))),
        )
        candidates.append(
            _candidate(
                category="routine_or_daemon",
                subject_ref=subject,
                evidence_refs=["portfolio_review:health"],
                unknowns=[str(row.get("reason_code") or "health_not_ready")],
                title="portfolio_operational_health_gap",
                why_it_constrains_capacity="operational_evidence_is_not_ready",
                expected_unlock="current_health_receipt_restores_review_coverage",
                smallest_next_action="refresh_or_validate_health_receipt",
                falsifier="health_receipt_becomes_current_and_ready",
            )
        )
    return candidates


def _mission_candidates(missions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for row in missions:
        status = str(row.get("status", "unknown"))
        if status == "current":
            continue
        repo_id = _safe_code(row.get("repo_id"), stable_id(METHOD_ID, "repo-unknown"))
        candidates.append(
            _candidate(
                category="mission_or_architecture_drift",
                subject_ref=repo_id,
                evidence_refs=[f"repo_mission:{status}"],
                human_decision_required=status in {"missing", "invalid", "unknown"},
                unknowns=list(row.get("problems", [])) if isinstance(row.get("problems"), list) else [],
                evidence_status="unknown" if status != "stale" else "confirmed",
                title=f"repo_mission_{status}",
                why_it_constrains_capacity="portfolio_leverage_cannot_be_claimed_without_source_owned_mission",
                expected_unlock="reviewed_mission_allows_bounded_alignment_checks",
                smallest_next_action="source_owner_reviews_repo_mission",
                quiet_option="retain_mission_unknown_without_priority_claim",
                falsifier="reviewed_source_owned_mission_is_current",
            )
        )
    return candidates


def _role_maturity(role_directory: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(role_directory, dict):
        return [], []
    roles = role_directory.get("roles", [])
    if not isinstance(roles, list):
        return [], []
    maturity_rows: list[dict[str, Any]] = []
    insufficient: list[str] = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        role_id = _safe_code(role.get("role_id"), stable_id(METHOD_ID, "role"))
        evaluation_status = _safe_code(
            role.get("evaluation_status"), "insufficient_evidence"
        )
        state = (
            "active_current"
            if evaluation_status in {"evaluated_current", "current_evidence"}
            else "implemented_unvalidated"
        )
        if state != "active_current":
            insufficient.append(role_id)
        maturity_rows.append(
            {
                "capability_ref": role_id,
                "stage": state,
                "evidence_refs": ["subagent_role_directory"],
                "missing_next_proof": (
                    "" if state == "active_current" else "reviewed_comparable_attempts"
                ),
                "promotion_authority": "lowell_or_reviewed_dad_governance",
            }
        )
    candidates = []
    if insufficient:
        candidates.append(
            _candidate(
                category="skill_or_subagent_maturity",
                subject_ref="subagent_role_evaluation_coverage",
                evidence_refs=["subagent_role_directory:insufficient_evidence"],
                unknowns=["declared_role_is_not_competence_evidence"],
                title="subagent_roles_lack_evaluated_revisions",
                why_it_constrains_capacity="declared_roles_cannot_support_competence_claims",
                expected_unlock="comparable_shadow_attempts_support_bounded_routing_evidence",
                smallest_next_action="run_comparable_shadow_attempts",
                falsifier="reviewed_evaluation_revisions_are_current",
            )
        )
    return maturity_rows, candidates


def _portfolio_attention_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    hard_reasons = {
        "conflicted_worktree",
        "dirty_worktree",
        "dirty_worktree_idle",
        "diverged_from_upstream",
        "unpushed_or_unmerged_commits",
        "upstream_gone",
    }
    rows = payload.get("attention_queue", [])
    candidates: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError("portfolio_attention row must be an object")
        reasons = set(_strict_string_list(row.get("reasons"), field="attention.reasons"))
        material_reasons = sorted(reasons & hard_reasons)
        project_id = _safe_code(row.get("project_id"), f"project-{index}")
        branch = _safe_code(row.get("branch"), f"branch-{index}")
        candidate = _candidate(
            category="worktree_or_handoff",
            subject_ref=stable_id(METHOD_ID, "worktree", project_id, branch),
            evidence_refs=[f"portfolio_attention:{reason}" for reason in sorted(reasons)],
            state="open" if material_reasons else "suppressed",
            title="worktree_capacity_risk",
            why_it_constrains_capacity=(
                "dirty_conflicted_or_unique_unpushed_work_requires_disposition"
                if material_reasons
                else "age_or_cleanup_signal_requires_more_evidence"
            ),
            expected_unlock="resume_handoff_archive_or_quiet_disposition",
            smallest_next_action="inspect_bounded_worktree_metadata",
            falsifier="worktree_is_clean_merged_or_source_owned_active_work",
            evidence_status="confirmed" if material_reasons else "unknown",
            suppress_reason="" if material_reasons else "insufficient_evidence",
            wake_conditions=["new_commit", "worktree_status_changes", "explicit_human_request"],
        )
        candidates.append(candidate)
    return candidates


def _roadmap_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    phases = payload.get("phases", {})
    candidates: list[dict[str, Any]] = []
    for phase_id, phase in sorted(phases.items()):
        if not isinstance(phase, Mapping):
            raise ValueError("roadmap phase must be an object")
        subject = _safe_code(phase_id, stable_id(METHOD_ID, "roadmap-phase"))
        computed = str(phase.get("computed_status", "unknown"))
        declared = str(phase.get("declared_status", "unknown"))
        if computed == "awaiting_human_gate":
            candidates.append(
                _candidate(
                    category="human_decision",
                    subject_ref=f"roadmap:{subject}",
                    evidence_refs=[f"roadmap:{subject}:awaiting_human_gate"],
                    human_decision_required=True,
                    evidence_status="confirmed",
                    title="roadmap_human_gate_wait",
                    why_it_constrains_capacity="accepted_roadmap_phase_waits_for_human_authority",
                    expected_unlock="reviewed_gate_disposition",
                    smallest_next_action="prepare_source_owned_gate_packet",
                    falsifier="roadmap_phase_no_longer_awaits_human_gate",
                )
            )
        blocked_dependencies = phase.get("blocked_dependencies", [])
        if not isinstance(blocked_dependencies, list):
            raise ValueError("roadmap blocked_dependencies must be a list")
        for dependency in blocked_dependencies:
            dep = _safe_code(dependency, stable_id(METHOD_ID, "dependency", subject))
            candidates.append(
                _candidate(
                    category="dependency_frontier",
                    subject_ref=f"roadmap-dependency:{dep}",
                    evidence_refs=[f"roadmap:{subject}:blocked_by:{dep}"],
                    accepted_dependency=True,
                    evidence_status="confirmed",
                    title="accepted_roadmap_dependency_block",
                    why_it_constrains_capacity="source_owned_roadmap_declares_blocked_dependency",
                    expected_unlock="validated_dependency_disposition",
                    smallest_next_action="inspect_dependency_acceptance_evidence",
                    falsifier="roadmap_dependency_is_complete_or_no_longer_required",
                    accepted_unlock_ref=f"roadmap:{subject}:dependency:{dep}",
                )
            )
        if computed in {"blocked", "awaiting_validation_evidence"} and declared in {
            "active",
            "complete",
            "in_progress",
        }:
            candidates.append(
                _candidate(
                    category="planned_or_partial_buildout",
                    subject_ref=f"roadmap:{subject}",
                    evidence_refs=[f"roadmap:{subject}:{declared}:{computed}"],
                    evidence_status="confirmed",
                    title="accepted_roadmap_phase_lacks_current_acceptance_evidence",
                    why_it_constrains_capacity="declared_accepted_work_lacks_current_completion_proof",
                    expected_unlock="current_acceptance_receipt_or_revised_roadmap_state",
                    smallest_next_action="inspect_missing_acceptance_evidence",
                    falsifier="roadmap_computed_status_matches_reviewed_source_state",
                )
            )
    return candidates


def _registry_maturity_candidates(
    source_id: str, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    collection_name = "skills" if source_id == "agent_skill_registry" else "assets"
    if source_id == "subagent_evaluation_profiles":
        collection_name = "profiles"
    rows = payload.get(collection_name, [])
    incomplete = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{source_id} record must be an object")
        status = str(row.get("status", "")).casefold()
        review_status = str(row.get("review_status", "")).casefold()
        if status in {"candidate", "planned", "partial"} or review_status in {
            "candidate",
            "unreviewed",
            "insufficient_evidence",
        }:
            incomplete.append(row)
    if not incomplete:
        return []
    category = (
        "skill_or_subagent_maturity"
        if source_id in {"agent_skill_registry", "subagent_evaluation_profiles"}
        else "planned_or_partial_buildout"
    )
    return [
        _candidate(
            category=category,
            subject_ref=f"registry:{source_id}",
            evidence_refs=[f"registry:{source_id}:candidate_count:{len(incomplete)}"],
            evidence_status="confirmed",
            title="registry_records_need_review_or_adoption_evidence",
            why_it_constrains_capacity="declared_capabilities_are_not_yet_reviewed_active_proof",
            expected_unlock="review_adopt_supersede_or_keep_candidate_disposition",
            smallest_next_action="sample_candidate_registry_records",
            falsifier="all_relevant_records_have_current_review_and_adoption_evidence",
        )
    ]


def _learning_loop_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    count = payload.get("open_without_outcome_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("learning open_without_outcome_count must be a non-negative integer")
    if count == 0:
        return []
    return [
        _candidate(
            category="learning_loop",
            subject_ref="learning-loops-without-outcomes",
            evidence_refs=[f"learning_loop:open_without_outcome_count:{count}"],
            evidence_status="confirmed",
            title="learning_loops_lack_outcome_receipts",
            why_it_constrains_capacity="unclosed_learning_cannot_safely_change_future_routing",
            expected_unlock="outcome_receipt_or_explicit_non_applicability",
            smallest_next_action="sample_oldest_unclosed_learning_loop",
            falsifier="all_open_learning_loops_have_outcome_or_non_applicability_receipts",
        )
    ]


def _iteration_report_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, row in enumerate(payload.get("observations", [])):
        if not isinstance(row, Mapping) or set(row) != {"subject_ref", "measurement"}:
            raise ValueError("iteration report observation must match the typed input contract")
        observation = _validated_iteration_measurement(row.get("measurement"))
        subject = _safe_code(row.get("subject_ref"), f"iteration-observation-{index}")
        drag_confirmed = observation["status"] == "confirmed" and observation["drag_observed"]
        candidate = _candidate(
            category="iteration_cycle",
            subject_ref=subject,
            evidence_refs=[
                observation["measurement_ref"],
                observation["same_workload_comparison_ref"],
                observation["correctness_or_parity_oracle_ref"],
                observation["failure_path_ref"],
            ],
            state="open" if drag_confirmed else "suppressed",
            evidence_status=observation["status"],
            title="measured_iteration_cycle_drag",
            why_it_constrains_capacity="typed_same_workload_measurement_requires_review",
            expected_unlock="bounded_parity_preserving_iteration_experiment",
            smallest_next_action="route_to_iteration_optimizer",
            falsifier="repeat_measurement_does_not_reproduce_the_drag",
            rollback_ref="iteration:rollback-required",
            falsifier_ref="iteration:repeat-measurement",
            suppress_reason=(
                ""
                if drag_confirmed
                else "no_material_drag"
                if observation["status"] == "confirmed"
                else "insufficient_evidence"
            ),
            wake_conditions=["new_measurement_receipt", "parity_or_failure_status_changes"],
        )
        candidate["_iteration_observation"] = observation
        candidates.append(candidate)
    return candidates


def _research_freshness_candidates(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    stale_refs = []
    for index, row in enumerate(payload.get("sources", [])):
        if not isinstance(row, Mapping):
            raise ValueError("research freshness source must be an object")
        status = str(row.get("status", "unknown")).casefold()
        if status in {"stale", "expired", "missing", "invalid", "unknown"}:
            stale_refs.append(_safe_code(row.get("source_id"), f"research-source-{index}"))
    if not stale_refs:
        return []
    return [
        _candidate(
            category="mission_or_architecture_drift",
            subject_ref="research-freshness-debt",
            evidence_refs=[f"research:{source}:not_current" for source in stale_refs],
            evidence_status="confirmed",
            title="research_inputs_are_not_current",
            why_it_constrains_capacity="architecture_or_decision_evidence_may_be_obsolete",
            expected_unlock="refreshed_provenance_and_freshness_receipts",
            smallest_next_action="refresh_highest_relevance_expired_source",
            falsifier="all_required_research_sources_are_current_and_reviewed",
        )
    ]


def _source_lane_candidates(
    source_payloads: Mapping[str, Any], source_coverage: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    current = {
        str(row["source_id"])
        for row in source_coverage
        if row.get("status") == "current" and row.get("consumption_status") == "consumed"
    }
    if "portfolio_attention" in current:
        candidates.extend(_portfolio_attention_candidates(source_payloads["portfolio_attention"]))
    if "roadmap" in current:
        candidates.extend(_roadmap_candidates(source_payloads["roadmap"]))
    for source_id in (
        "agent_skill_registry",
        "asset_registry",
        "coding_asset_registry",
        "subagent_evaluation_profiles",
    ):
        if source_id in current:
            candidates.extend(_registry_maturity_candidates(source_id, source_payloads[source_id]))
    if "learning_loop_status" in current:
        candidates.extend(_learning_loop_candidates(source_payloads["learning_loop_status"]))
    if "iteration_measurements" in current:
        candidates.extend(_iteration_report_candidates(source_payloads["iteration_measurements"]))
    if "research_freshness" in current:
        candidates.extend(_research_freshness_candidates(source_payloads["research_freshness"]))
    for source in source_coverage:
        if not source.get("required") or source.get("status") == "current":
            continue
        source_id = str(source["source_id"])
        category = (
            "routine_or_daemon"
            if source_id in {"daemon", "scheduled_tasks"}
            else "mission_or_architecture_drift"
            if source_id == "research_freshness"
            else "attention_or_compute"
        )
        candidates.append(
            _candidate(
                category=category,
                subject_ref=f"source-coverage:{source_id}",
                evidence_refs=list(source.get("evidence_refs", [])),
                evidence_status="confirmed",
                title="required_capacity_source_is_not_current",
                why_it_constrains_capacity="required_lane_cannot_support_a_complete_weekly_review",
                expected_unlock="current_schema_valid_source_receipt",
                smallest_next_action="refresh_or_repair_required_source",
                falsifier="required_source_becomes_current_schema_valid_and_consumed",
            )
        )
    return candidates


_WORKER_PACKET_FIELDS = frozenset(
    {
        "attempt_id",
        "c3_payload_included",
        "candidates",
        "privacy_class",
        "role_id",
        "role_revision_id",
        "source_fingerprint",
    }
)
_WORKER_CANDIDATE_FIELDS = frozenset(
    {
        "accepted_dependency",
        "accepted_unlock_ref",
        "age_only",
        "authority_gate",
        "category",
        "counterevidence",
        "evaluation_status",
        "evidence_refs",
        "evidence_status",
        "expected_unlock",
        "falsifier",
        "falsifier_ref",
        "human_decision_required",
        "iteration_measurement",
        "outcome_receipt_present",
        "precedence_class",
        "privacy_class",
        "quiet_option",
        "rollback_ref",
        "smallest_next_action",
        "state",
        "subject_ref",
        "title",
        "unknowns",
        "wake_conditions",
        "why_it_constrains_capacity",
    }
)


def _strict_string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return value


def _measurement_number(value: Any, *, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise ValueError(f"{field} must be a non-negative measurement number")
    return float(value)


def _validated_iteration_measurement(value: Any) -> dict[str, Any]:
    unknown = {
        "evidence_kind": "wall_time",
        "metric_kind": "wall_time",
        "better_is": "lower",
        "drag_observed": False,
        "measurement_ref": "missing_measured_baseline",
        "baseline_value": None,
        "comparison_value": None,
        "measurement_unit": "seconds",
        "same_workload_comparison_ref": "missing_same_workload_comparison",
        "workload_ref": "missing_workload_ref",
        "correctness_or_parity_oracle_ref": "missing_parity_oracle",
        "oracle_status": "unknown",
        "failure_path_ref": "missing_failure_path",
        "failure_path_status": "unknown",
        "status": "unknown",
    }
    if value is None:
        return unknown
    if not isinstance(value, Mapping):
        raise ValueError("iteration_measurement must be an object")
    allowed = {
        "metric_kind",
        "better_is",
        "baseline",
        "comparison",
        "correctness_or_parity",
        "failure_path",
    }
    if set(value) != allowed:
        raise ValueError("iteration_measurement fields do not match the typed receipt contract")
    metric_kind = str(value.get("metric_kind", ""))
    better_is = str(value.get("better_is", ""))
    expected_direction = {
        "wall_time": "lower",
        "queue_delay": "lower",
        "handoff_latency": "lower",
        "throughput": "higher",
    }.get(metric_kind)
    if expected_direction is None or better_is != expected_direction:
        raise ValueError("iteration metric kind and direction do not match")
    baseline = value.get("baseline")
    comparison = value.get("comparison")
    oracle = value.get("correctness_or_parity")
    failure = value.get("failure_path")
    if not all(isinstance(item, Mapping) for item in (baseline, comparison, oracle, failure)):
        return unknown
    if set(baseline) != {"value", "unit", "workload_ref", "receipt_ref"}:
        raise ValueError("iteration baseline fields do not match the typed receipt contract")
    if set(comparison) != {"value", "unit", "workload_ref", "receipt_ref"}:
        raise ValueError("iteration comparison fields do not match the typed receipt contract")
    if set(oracle) != {"oracle_ref", "status"}:
        raise ValueError("iteration oracle fields do not match the typed receipt contract")
    if set(failure) != {"failure_path_ref", "status"}:
        raise ValueError("iteration failure fields do not match the typed receipt contract")
    baseline_unit = str(baseline.get("unit", ""))
    comparison_unit = str(comparison.get("unit", ""))
    if baseline_unit not in _MEASUREMENT_UNITS or comparison_unit != baseline_unit:
        raise ValueError("iteration measurements require one supported common unit")
    time_units = {"seconds", "milliseconds", "minutes"}
    throughput_units = {"items_per_second", "requests_per_second"}
    if (metric_kind == "throughput" and baseline_unit not in throughput_units) or (
        metric_kind != "throughput" and baseline_unit not in time_units
    ):
        raise ValueError("iteration metric kind and unit do not match")
    baseline_workload = _safe_code(baseline.get("workload_ref"), "")
    comparison_workload = _safe_code(comparison.get("workload_ref"), "")
    if not baseline_workload or comparison_workload != baseline_workload:
        raise ValueError("iteration measurements require the same explicit workload ref")
    baseline_ref = _safe_code(baseline.get("receipt_ref"), "")
    comparison_ref = _safe_code(comparison.get("receipt_ref"), "")
    oracle_ref = _safe_code(oracle.get("oracle_ref"), "")
    failure_ref = _safe_code(failure.get("failure_path_ref"), "")
    oracle_status = str(oracle.get("status", "")).casefold()
    failure_status = str(failure.get("status", "")).casefold()
    if oracle_status not in {"passed", "failed", "not_run", "unknown"}:
        raise ValueError("unknown iteration oracle status")
    if failure_status not in {"preserved", "failed", "not_run", "unknown"}:
        raise ValueError("unknown iteration failure-path status")
    complete = bool(baseline_ref and comparison_ref and oracle_ref and failure_ref)
    confirmed = complete and oracle_status == "passed" and failure_status == "preserved"
    baseline_value = _measurement_number(baseline.get("value"), field="baseline.value")
    comparison_value = _measurement_number(
        comparison.get("value"), field="comparison.value"
    )
    drag_observed = (
        comparison_value > baseline_value
        if better_is == "lower"
        else comparison_value < baseline_value
    )
    return {
        "evidence_kind": "before_after_parity",
        "metric_kind": metric_kind,
        "better_is": better_is,
        "drag_observed": drag_observed,
        "measurement_ref": baseline_ref or "missing_measured_baseline",
        "baseline_value": baseline_value,
        "comparison_value": comparison_value,
        "measurement_unit": baseline_unit,
        "same_workload_comparison_ref": (
            comparison_ref or "missing_same_workload_comparison"
        ),
        "workload_ref": baseline_workload,
        "correctness_or_parity_oracle_ref": oracle_ref or "missing_parity_oracle",
        "oracle_status": oracle_status,
        "failure_path_ref": failure_ref or "missing_failure_path",
        "failure_path_status": failure_status,
        "status": "confirmed" if confirmed else "unknown",
    }


def _normalized_worker_candidates(
    worker_packets: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    candidates: list[dict[str, Any]] = []
    worker_roles: set[str] = set()
    worker_revisions: set[str] = set()
    for packet in worker_packets:
        if not isinstance(packet, Mapping):
            raise ValueError("worker packet must be an object")
        unknown_packet_fields = set(packet) - _WORKER_PACKET_FIELDS
        if unknown_packet_fields:
            raise ValueError(
                "worker packet contains unknown fields: "
                + ", ".join(sorted(str(field) for field in unknown_packet_fields))
            )
        _reject_prohibited_input(packet, context="worker packet")
        if str(packet.get("privacy_class", "C1")) not in PRIVACY_CLASSES:
            raise ValueError("C3 worker payloads are prohibited from the capacity digest")
        role_id = _safe_code(packet.get("role_id"), "")
        if role_id not in _WORKER_ROLE_IDS:
            raise ValueError(f"worker role is not repo-authoritative: {role_id or 'missing'}")
        revision_id = _safe_code(packet.get("role_revision_id"), "")
        worker_roles.add(role_id)
        if revision_id:
            worker_revisions.add(revision_id)
        rows = packet.get("candidates", [])
        if not isinstance(rows, list):
            raise ValueError("worker candidates must be a list")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("worker candidate must be an object")
            unknown_candidate_fields = set(row) - _WORKER_CANDIDATE_FIELDS
            if unknown_candidate_fields:
                raise ValueError(
                    "worker candidate contains unknown fields: "
                    + ", ".join(sorted(str(field) for field in unknown_candidate_fields))
                )
            privacy_class = str(row.get("privacy_class", packet.get("privacy_class", "C1")))
            category = str(row.get("category", ""))
            if category not in BOTTLENECK_CATEGORIES:
                raise ValueError(f"unknown capacity category: {category}")
            accepted_dependency = _strict_bool(
                row.get("accepted_dependency", _MISSING), field="accepted_dependency"
            )
            raw_state = str(row.get("state", "open")).casefold()
            if raw_state not in {
                "open",
                "snoozed",
                "paused",
                "quiet",
                "dismissed",
                "cooldown",
                "suppressed",
            }:
                raise ValueError(f"unknown worker candidate state: {raw_state}")
            state = raw_state
            suppress_reason = ""
            unknowns = _strict_string_list(row.get("unknowns"), field="unknowns")
            if _strict_bool(row.get("age_only", _MISSING), field="age_only"):
                state = "suppressed"
                suppress_reason = "insufficient_evidence"
                unknowns.append("age_only_signal")
            if category == "dependency_frontier" and not accepted_dependency:
                state = "suppressed"
                suppress_reason = "insufficient_evidence"
                unknowns.append("dependency_not_accepted")
            if raw_state in {"snoozed", "paused", "quiet", "dismissed", "cooldown"}:
                state = "suppressed"
                suppress_reason = {
                    "snoozed": "snoozed",
                    "paused": "quiet_state",
                    "quiet": "quiet_state",
                    "dismissed": "dismissed",
                    "cooldown": "cooldown",
                }[raw_state]
            evidence_status = str(row.get("evidence_status", "inferred"))
            if category == "learning_loop" and not _strict_bool(
                row.get("outcome_receipt_present", _MISSING),
                field="outcome_receipt_present",
            ):
                evidence_status = "unknown"
                unknowns.append("learning_outcome_receipt_missing")
            precedence_class = str(row.get("precedence_class", ""))
            if precedence_class and precedence_class != CATEGORY_PRECEDENCE[category]:
                raise ValueError("worker precedence override is prohibited")
            iteration_observation = None
            if category == "iteration_cycle":
                iteration_observation = _validated_iteration_measurement(
                    row.get("iteration_measurement")
                )
                if iteration_observation["status"] != "confirmed":
                    state = "suppressed"
                    suppress_reason = "insufficient_evidence"
                    evidence_status = "unknown"
                    unknowns.append("typed_iteration_receipt_incomplete")
                elif not iteration_observation["drag_observed"]:
                    state = "suppressed"
                    suppress_reason = "no_material_drag"
            candidate = _candidate(
                    category=category,
                    subject_ref=str(row.get("subject_ref", "")),
                    evidence_refs=_strict_string_list(
                        row.get("evidence_refs"), field="evidence_refs"
                    ),
                    human_decision_required=_strict_bool(
                        row.get("human_decision_required", _MISSING),
                        field="human_decision_required",
                    ),
                    accepted_dependency=accepted_dependency,
                    privacy_class=privacy_class,
                    state=state,
                    counterevidence=_strict_string_list(
                        row.get("counterevidence"), field="counterevidence"
                    ),
                    unknowns=unknowns,
                    agent_revision_ids=[revision_id] if revision_id else [],
                    evaluation_status=str(
                        row.get("evaluation_status", "insufficient_evidence")
                    ),
                    evidence_status=evidence_status,
                    title=str(row.get("title", f"{category}_candidate")),
                    why_it_constrains_capacity=str(
                        row.get("why_it_constrains_capacity", "bounded_evidence_requires_review")
                    ),
                    expected_unlock=str(
                        row.get("expected_unlock", "validated_next_action_or_quiet_default")
                    ),
                    smallest_next_action=str(
                        row.get("smallest_next_action", "inspect_bounded_evidence")
                    ),
                    quiet_option=str(row.get("quiet_option", "keep_visible_without_nudge")),
                    falsifier=str(row.get("falsifier", "new_authoritative_evidence")),
                    authority_gate=str(row.get("authority_gate", "source_owner_or_lowell")),
                    precedence_class=precedence_class,
                    rollback_ref=str(row.get("rollback_ref", "")),
                    accepted_unlock_ref=str(row.get("accepted_unlock_ref", "")),
                    falsifier_ref=str(row.get("falsifier_ref", "")),
                    suppress_reason=suppress_reason,
                    wake_conditions=_strict_string_list(
                        row.get("wake_conditions"), field="wake_conditions"
                    ),
                )
            if iteration_observation is not None:
                candidate["_iteration_observation"] = iteration_observation
            candidates.append(candidate)
    return candidates, sorted(worker_roles), sorted(worker_revisions)


def _dedupe_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in candidates:
        row = dict(raw)
        identifier = str(row["bottleneck_id"])
        prior = by_id.get(identifier)
        if prior is None:
            by_id[identifier] = row
            continue
        prior["evidence_refs"] = sorted(
            set(prior.get("evidence_refs", [])) | set(row.get("evidence_refs", []))
        )
        prior["counterevidence"] = sorted(
            set(prior.get("counterevidence", [])) | set(row.get("counterevidence", []))
        )
        prior["_unknowns"] = sorted(
            set(prior.get("_unknowns", [])) | set(row.get("_unknowns", []))
        )
        prior["_agent_revision_ids"] = sorted(
            set(prior.get("_agent_revision_ids", []))
            | set(row.get("_agent_revision_ids", []))
        )
        prior["_human_decision_required"] = bool(
            prior.get("_human_decision_required") or row.get("_human_decision_required")
        )
        prior["_source_fingerprint"] = _canonical_hash(
            [identifier, prior["evidence_refs"], prior["counterevidence"], prior["_unknowns"]]
        )
        prior["_wake_conditions"] = sorted(
            set(prior.get("_wake_conditions", [])) | set(row.get("_wake_conditions", []))
        )
        prior["_suppress_reason"] = prior.get("_suppress_reason") or row.get(
            "_suppress_reason", ""
        )
        prior_observation = prior.get("_iteration_observation", {})
        row_observation = row.get("_iteration_observation", {})
        if (
            isinstance(row_observation, Mapping)
            and row_observation.get("status") == "confirmed"
            and (
                not isinstance(prior_observation, Mapping)
                or prior_observation.get("status") != "confirmed"
            )
        ):
            prior["_iteration_observation"] = dict(row_observation)
    return sorted(
        by_id.values(),
        key=lambda row: (
            _BAND_ORDER[str(row["precedence_class"])],
            *_ranking_signature(row),
            str(row["_subject_ref"]),
        ),
    )


def _ranking_signature(row: Mapping[str, Any]) -> tuple[int, int, int, int]:
    return (
        _EVIDENCE_STATUS_ORDER.get(str(row.get("evidence_status", "unknown")), 3),
        0 if row.get("_rollback_ref") else 1,
        0 if row.get("_accepted_unlock_ref") else 1,
        0 if row.get("_falsifier_ref") else 1,
    )


def _tie_disagreements(
    candidates: Sequence[Mapping[str, Any]], selected_ids: set[str]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, tuple[int, int, int, int]], list[Mapping[str, Any]]] = {}
    for row in candidates:
        key = (str(row["precedence_class"]), _ranking_signature(row))
        groups.setdefault(key, []).append(row)
    disagreements = []
    for (precedence, signature), rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        row_ids = {str(row["bottleneck_id"]) for row in rows}
        crosses_frontier = bool(row_ids & selected_ids) and bool(row_ids - selected_ids)
        disagreements.append(
            {
                "disagreement_id": stable_id(
                    METHOD_ID, "within-class-tie", precedence, json.dumps(signature)
                ),
                "subject_ref": precedence,
                "positions": sorted(str(row["_subject_ref"]) for row in rows),
                "material": crosses_frontier,
                "resolution_status": "unresolved",
                "next_review_lane": "human_decision" if crosses_frontier else "foreman_revision",
            }
        )
    return disagreements


def _routine_health(source_coverage: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in source_coverage:
        source_id = str(source.get("source_id", ""))
        if not any(
            token in source_id for token in ("daemon", "routine", "trigger", "journal", "scheduled")
        ):
            continue
        status = str(source.get("status", "unknown"))
        rows.append(
            {
                "routine_id": source_id,
                "kind": "daemon" if "daemon" in source_id else "routine",
                "status": status,
                "scheduled": str(source.get("scheduled_state", "unknown")),
                "evidence_refs": list(source.get("evidence_refs", [])),
                "problems": list(source.get("problems", [])),
            }
        )
    return rows


def _iteration_evidence(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in candidates:
        if row.get("category") != "iteration_cycle":
            continue
        observation = row.get("_iteration_observation")
        if not isinstance(observation, Mapping):
            observation = _validated_iteration_measurement(None)
        rows.append(
            {
                "observation_id": stable_id(METHOD_ID, "iteration", row["bottleneck_id"]),
                "bottleneck_ref": row["bottleneck_id"],
                "evidence_kind": observation["evidence_kind"],
                "metric_kind": observation["metric_kind"],
                "better_is": observation["better_is"],
                "drag_observed": observation["drag_observed"],
                "scope": row["_subject_ref"],
                "measurement_ref": observation["measurement_ref"],
                "baseline_value": observation["baseline_value"],
                "comparison_value": observation["comparison_value"],
                "measurement_unit": observation["measurement_unit"],
                "same_workload_comparison_ref": observation[
                    "same_workload_comparison_ref"
                ],
                "workload_ref": observation["workload_ref"],
                "correctness_or_parity_oracle_ref": observation[
                    "correctness_or_parity_oracle_ref"
                ],
                "oracle_status": observation["oracle_status"],
                "failure_path_ref": observation["failure_path_ref"],
                "failure_path_status": observation["failure_path_status"],
                "layer_hypotheses": ["workflow"],
                "parity_required": True,
                "status": observation["status"],
            }
        )
    return rows


def build_portfolio_capacity_review(
    *,
    source_payloads: Mapping[str, Any],
    mission_coverage: Sequence[Mapping[str, Any]],
    worker_packets: Sequence[Mapping[str, Any]] = (),
    prior_packet: Mapping[str, Any] | None = None,
    checker_revision_id: str = "",
    now: datetime | None = None,
    settings: CapacityReviewSettings | None = None,
) -> dict[str, Any]:
    """Build a deterministic JSON-only shadow report without dispatching agents."""

    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    policy = settings or CapacityReviewSettings()
    unknown_source_ids = sorted(set(source_payloads) - set(SOURCE_CONTRACT))
    if unknown_source_ids:
        raise ValueError("unknown capacity source ids: " + ", ".join(unknown_source_ids))
    projected_source_payloads = {
        source_id: _capacity_source_projection(source_id, value)
        for source_id, value in source_payloads.items()
    }
    source_ids = sorted(set(REQUIRED_SOURCE_IDS) | set(projected_source_payloads))
    sources = [
        _source_descriptor(
            source_id, projected_source_payloads.get(source_id), observed_at=observed_at
        )
        for source_id in source_ids
    ]
    missions = [dict(row) for row in mission_coverage]
    for row in missions:
        if row.get("status") not in MISSION_STATES:
            raise ValueError(f"unknown mission coverage status: {row.get('status')}")

    review_packet = projected_source_payloads.get("portfolio_review")
    role_directory = projected_source_payloads.get("subagent_role_directory")
    maturity_rows, maturity_candidates = _role_maturity(role_directory)
    worker_candidates, worker_roles, worker_revisions = _normalized_worker_candidates(
        worker_packets
    )
    candidates = _dedupe_candidates(
        [
            *_review_candidates(review_packet),
            *_source_lane_candidates(projected_source_payloads, sources),
            *_mission_candidates(missions),
            *maturity_candidates,
            *worker_candidates,
        ]
    )
    mission_material = [
        {
            key: row.get(key)
            for key in ("repo_id", "mission_id", "status", "source_ref", "problems")
        }
        for row in missions
    ]

    material_fingerprint = _canonical_hash(
        {
            "builder_contract_revision": BUILDER_CONTRACT_REVISION,
            "sources": sources,
            "missions": mission_material,
            "worker_packets": [
                _canonical_hash(_material_value(packet)) for packet in worker_packets
            ],
        }
    )
    unchanged = bool(
        prior_packet and str(prior_packet.get("material_fingerprint", "")) == material_fingerprint
    )

    checker_revision = _safe_code(checker_revision_id, "")
    checker_lineage_distinct = not checker_revision or checker_revision not in worker_revisions
    suppressed: list[dict[str, Any]] = []
    for row in candidates:
        if unchanged or row.get("_state") == "suppressed":
            reason = (
                "unchanged_fingerprint"
                if unchanged
                else (row.get("_suppress_reason") or "insufficient_evidence")
            )
            suppressed.append(
                {
                    "candidate_id": row["bottleneck_id"],
                    "reason": reason,
                    "material_fingerprint": row["_source_fingerprint"],
                    "cooldown_until": None,
                    "evidence_refs": row["evidence_refs"],
                    "wake_conditions": row.get("_wake_conditions")
                    or ["material_fingerprint_changes", "explicit_human_request"],
                }
            )

    active_candidates = [] if unchanged else [
        row for row in candidates if row.get("_state") != "suppressed"
    ]
    eligible_human = [
        row
        for row in active_candidates
        if row["_human_decision_required"]
    ]
    selected_human = eligible_human[: policy.human_ask_limit]
    human_asks = [
        {
            "ask_id": stable_id(METHOD_ID, "human-ask", row["bottleneck_id"]),
            "bottleneck_ref": row["bottleneck_id"],
            "precedence_class": row["precedence_class"],
            "question": "choose_source_owned_disposition",
            "why_human_required": row["authority_gate"],
            "options": ["review_now", "keep_quiet_until_wake_condition"],
            "strongest_counterargument": (
                row["counterevidence"][0]
                if row["counterevidence"]
                else "current_evidence_may_not_justify_attention"
            ),
            "safe_default": row["safe_default"],
            "review_or_expiry_condition": row["falsifier"],
            "smallest_reversible_next_action": row["smallest_next_action"],
            "evidence_refs": row["evidence_refs"],
        }
        for row in selected_human
    ]
    selected_ids = {row["bottleneck_id"] for row in selected_human}
    disagreements = _tie_disagreements(active_candidates, selected_ids)
    overflow_items = [
        {
            "candidate_id": row["bottleneck_id"],
            "bottleneck_ref": row["bottleneck_id"],
            "disposition": (
                "lower_precedence" if row["_human_decision_required"] else "needs_evidence"
            ),
            "reason": "not_selected_for_bounded_human_frontier",
            "wake_conditions": ["material_fingerprint_changes", "explicit_human_request"],
        }
        for row in active_candidates
        if row["bottleneck_id"] not in selected_ids
    ]

    has_invalid = any(row["status"] == "invalid" for row in sources) or any(
        row.get("status") == "invalid" for row in missions
    )
    has_incomplete = any(row["status"] != "current" for row in sources) or any(
        row.get("status") != "current" for row in missions
    )
    if has_invalid or not checker_lineage_distinct:
        status = "blocked_candidate"
    elif has_incomplete:
        status = "partial_candidate"
    else:
        status = "shadow_candidate"

    selected_worker_roles = sorted(
        set(worker_roles)
        | {
            {
                "human_decision": "delivery-closeout-resumption-steward",
                "worktree_or_handoff": "neglected-worktree-triage-manager",
                "planned_or_partial_buildout": "capability-maturity-and-cycle-auditor",
                "skill_or_subagent_maturity": "capability-maturity-and-cycle-auditor",
                "learning_loop": "improvement-layer-router",
                "iteration_cycle": "capability-maturity-and-cycle-auditor",
                "routine_or_daemon": "luna-trigger-observer",
                "dependency_frontier": "dependency-critical-frontier-analyst",
                "attention_or_compute": "portfolio-scrum-board-curator",
                "mission_or_architecture_drift": "research-project-workflow-steward",
            }[str(row["category"])]
            for row in active_candidates
        }
    )

    unavailable_source_ids = [row["source_id"] for row in sources if row["status"] != "current"]
    unavailable_lane_ids = sorted(
        {str(row["lane_id"]) for row in sources if row["status"] != "current"}
    )
    required_sources_current = all(
        row["status"] == "current" for row in sources if row["required"]
    )
    coverage_fingerprint = _canonical_hash(
        {"sources": sources, "missions": mission_material}
    )

    packet = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": stable_id("capacity-review", material_fingerprint),
        "generated_at": observed_at.isoformat(),
        "status": status,
        "data_classification": "C2_private_metadata",
        "public_safe": False,
        "execution_authorized": False,
        "mutations_performed": False,
        "source_authority_mutated": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "methodology": {
            "method_id": METHOD_ID,
            "builder_contract_revision": BUILDER_CONTRACT_REVISION,
            "methodology_ref": METHODOLOGY_REF,
            "mode": "manual_shadow",
            "numeric_or_composite_score_used": False,
            "categorical_precedence": list(PRECEDENCE_BANDS),
            "within_class_rule": (
                "evidence_then_reversibility_then_traced_unlock_then_falsifiability_"
                "then_disagreement_then_lexical_stability"
            ),
        },
        "source_coverage": {
            "configured_root_ids": sorted({row["repo_id"] for row in missions}),
            "required_source_ids": list(REQUIRED_SOURCE_IDS),
            "required_lane_ids": sorted(
                {str(SOURCE_CONTRACT[source_id]["lane_id"]) for source_id in REQUIRED_SOURCE_IDS}
            ),
            "sources": sources,
            "coverage_complete": required_sources_current
            and not unavailable_source_ids
            and all(row.get("status") == "current" for row in missions),
            "unavailable_source_ids": unavailable_source_ids,
            "unavailable_lane_ids": unavailable_lane_ids,
            "coverage_fingerprint": coverage_fingerprint,
        },
        "mission_coverage": missions,
        "bottlenecks": [_public_candidate(row) for row in active_candidates],
        "human_asks": human_asks,
        "overflow": {
            "complete": True,
            "unrepresented_candidate_count": 0,
            "items": overflow_items,
        },
        "suppressed": suppressed,
        "disagreements": disagreements,
        "capability_maturity": maturity_rows,
        "iteration_evidence": _iteration_evidence(candidates),
        "routine_health": _routine_health(sources),
        "routing": {
            "semantic_agent_fanout": 0,
            "fanout_status": "deterministic_v0_not_dispatched",
            "frozen_input_fingerprint": "",
            "worker_role_ids": selected_worker_roles,
            "foreman": {
                "role_id": "portfolio-capacity-foreman",
                "attempt_id": "not_dispatched",
            },
            "boss": {
                "role_id": "sol-automation-workflow-architect",
                "invocation": "not_needed",
            },
            "frontier_review": "not_recommended",
            "checker_lineage": {
                "role_id": "independent-capacity-review-checker",
                "attempt_id": "not_dispatched",
                "distinct_from_foreman": False,
                "checker_is_author": False,
                "blind_to_foreman_conclusions": False,
                "received_inputs": [],
                "lineage_complete": False,
                "verdict": "not_run",
            },
        },
        "privacy": {
            "maximum_classification": "C2_private_metadata",
            "c3_payload_included": False,
            "raw_payload_copied": False,
            "private_absolute_paths_exposed": False,
            "redaction_status": "complete",
        },
        "feedback_template": {
            "allowed_labels": ["useful", "noisy", "missed", "harmful", "incomplete", "defer"],
            "records_feedback": False,
            "changes_instructions": False,
            "activates_routine": False,
        },
        "unknowns": [
            {
                "unknown_id": stable_id(METHOD_ID, "unknown", row["repo_id"], row["status"]),
                "question": "what_is_the_reviewed_source_owned_repo_mission",
                "why_unknown": (row.get("problems") or [f"mission_{row['status']}"])[0],
                "needed_evidence": "reviewed_repo_mission_contract",
                "owner_candidate": row["repo_id"],
                "wake_condition": "repo_mission_contract_becomes_reviewed_and_valid",
            }
            for row in missions
            if row.get("status") != "current"
        ],
        "material_fingerprint": material_fingerprint,
    }
    problems = portfolio_capacity_review_semantic_problems(packet)
    if problems:
        raise ValueError("Invalid portfolio capacity review semantics: " + "; ".join(problems))
    return packet


def portfolio_capacity_review_semantic_problems(packet: Mapping[str, Any]) -> list[str]:
    """Check noncompensatory privacy, authority, identity, and completeness gates."""

    problems: set[str] = set()
    if packet.get("schema_version") != SCHEMA_VERSION:
        problems.add("unexpected_schema_version")
    human_asks = packet.get("human_asks", [])
    if not isinstance(human_asks, list) or len(human_asks) > 3:
        problems.add("human_ask_limit_exceeded")
    if packet.get("execution_authorized") is not False:
        problems.add("execution_authorized")
    if packet.get("mutations_performed") is not False:
        problems.add("mutations_performed")
    if packet.get("source_authority_mutated") is not False:
        problems.add("source_authority_mutated")
    privacy = packet.get("privacy", {})
    if not isinstance(privacy, Mapping) or privacy.get("c3_payload_included") is not False:
        problems.add("c3_payload_present")
    if isinstance(privacy, Mapping) and privacy.get("private_absolute_paths_exposed") is not False:
        problems.add("private_absolute_paths_exposed")
    methodology = packet.get("methodology", {})
    if (
        not isinstance(methodology, Mapping)
        or methodology.get("numeric_or_composite_score_used") is not False
    ):
        problems.add("numeric_score_used")
    if isinstance(methodology, Mapping) and methodology.get(
        "builder_contract_revision"
    ) != BUILDER_CONTRACT_REVISION:
        problems.add("builder_contract_revision_changed")
    if isinstance(methodology, Mapping) and methodology.get("categorical_precedence") != list(
        PRECEDENCE_BANDS
    ):
        problems.add("categorical_precedence_changed")
    if isinstance(methodology, Mapping) and methodology.get("within_class_rule") != (
        "evidence_then_reversibility_then_traced_unlock_then_falsifiability_"
        "then_disagreement_then_lexical_stability"
    ):
        problems.add("within_class_rule_changed")

    source_coverage = packet.get("source_coverage", {})
    if not isinstance(source_coverage, Mapping):
        problems.add("source_coverage_not_object")
        source_rows: list[Any] = []
    else:
        source_rows = source_coverage.get("sources", [])
        if not isinstance(source_rows, list):
            problems.add("source_rows_not_list")
            source_rows = []
    source_by_id = {
        str(row.get("source_id")): row for row in source_rows if isinstance(row, Mapping)
    }
    if set(REQUIRED_SOURCE_IDS) - set(source_by_id):
        problems.add("required_source_coverage_missing")
    for source_id, row in source_by_id.items():
        contract = SOURCE_CONTRACT.get(source_id)
        if contract is None:
            problems.add("unknown_source_id")
            continue
        if row.get("lane_id") != contract["lane_id"]:
            problems.add("source_lane_mismatch")
        if row.get("source_kind") != contract["source_kind"]:
            problems.add("source_kind_mismatch")
        if row.get("required") is not bool(contract["required"]):
            problems.add("source_required_flag_mismatch")
        if row.get("status") not in MISSION_STATES:
            problems.add("unknown_source_status")
        expected_fresh_after = _SOURCE_FRESH_AFTER_HOURS.get(source_id)
        if row.get("fresh_after_hours") != expected_fresh_after:
            problems.add("source_freshness_contract_changed")
        if row.get("status") == "current" and row.get("consumption_status") != "consumed":
            problems.add("current_source_not_consumed")
        if expected_fresh_after is None and row.get("freshness_status") != "not_applicable":
            problems.add("static_source_freshness_mismatch")
        if expected_fresh_after is not None and row.get("status") == "current" and row.get(
            "freshness_status"
        ) != "current":
            problems.add("current_source_without_freshness")
        if row.get("status") in {"current", "stale"} and row.get("schema_version") not in contract[
            "schema_versions"
        ]:
            problems.add("unsupported_source_schema_version")
    expected_unavailable = sorted(
        source_id
        for source_id, row in source_by_id.items()
        if row.get("status") != "current"
    )
    if isinstance(source_coverage, Mapping):
        if source_coverage.get("required_source_ids") != list(REQUIRED_SOURCE_IDS):
            problems.add("required_source_contract_changed")
        expected_lanes = sorted(
            {str(SOURCE_CONTRACT[source_id]["lane_id"]) for source_id in REQUIRED_SOURCE_IDS}
        )
        if source_coverage.get("required_lane_ids") != expected_lanes:
            problems.add("required_lane_contract_changed")
        if source_coverage.get("unavailable_source_ids") != expected_unavailable:
            problems.add("unavailable_source_ids_incomplete")
        expected_unavailable_lanes = sorted(
            {
                str(source_by_id[source_id].get("lane_id"))
                for source_id in expected_unavailable
            }
        )
        if source_coverage.get("unavailable_lane_ids") != expected_unavailable_lanes:
            problems.add("unavailable_lane_ids_incomplete")
        missions = packet.get("mission_coverage", [])
        missions_current = isinstance(missions, list) and bool(missions) and all(
            isinstance(row, Mapping) and row.get("status") == "current" for row in missions
        )
        expected_complete = (
            not expected_unavailable
            and all(
                source_by_id.get(source_id, {}).get("status") == "current"
                for source_id in REQUIRED_SOURCE_IDS
            )
            and missions_current
        )
        if source_coverage.get("coverage_complete") is not expected_complete:
            problems.add("coverage_complete_mismatch")

    bottlenecks = packet.get("bottlenecks", [])
    if not isinstance(bottlenecks, list):
        problems.add("bottlenecks_not_list")
        bottlenecks = []
    ids = [str(row.get("bottleneck_id", "")) for row in bottlenecks if isinstance(row, Mapping)]
    if len(ids) != len(set(ids)):
        problems.add("duplicate_bottleneck_id")
    id_set = set(ids)
    for ask in human_asks if isinstance(human_asks, list) else []:
        if not isinstance(ask, Mapping) or ask.get("bottleneck_ref") not in id_set:
            problems.add("human_ask_without_bottleneck")
    selected = {
        str(ask.get("bottleneck_ref"))
        for ask in human_asks
        if isinstance(ask, Mapping)
    }
    overflow = packet.get("overflow", {})
    overflow_items = overflow.get("items", []) if isinstance(overflow, Mapping) else []
    overflow_refs = {
        str(row.get("bottleneck_ref"))
        for row in overflow_items
        if isinstance(row, Mapping)
    }
    if (
        not isinstance(overflow, Mapping)
        or overflow.get("complete") is not True
        or overflow.get("unrepresented_candidate_count") != 0
        or overflow_refs != id_set - selected
    ):
        problems.add("overflow_incomplete")

    for row in bottlenecks:
        if not isinstance(row, Mapping):
            problems.add("bottleneck_not_object")
            continue
        category = row.get("category")
        if category not in BOTTLENECK_CATEGORIES:
            problems.add("unknown_bottleneck_category")
        if row.get("precedence_class") not in PRECEDENCE_BANDS:
            problems.add("unknown_precedence_class")
        elif category in CATEGORY_PRECEDENCE and row.get("precedence_class") != CATEGORY_PRECEDENCE[
            str(category)
        ]:
            problems.add("category_precedence_mismatch")

    for row in packet.get("iteration_evidence", []):
        if not isinstance(row, Mapping):
            problems.add("iteration_evidence_not_object")
            continue
        if row.get("status") == "confirmed":
            required_refs = (
                row.get("measurement_ref"),
                row.get("same_workload_comparison_ref"),
                row.get("workload_ref"),
                row.get("correctness_or_parity_oracle_ref"),
                row.get("failure_path_ref"),
            )
            if any(not ref or str(ref).startswith("missing_") for ref in required_refs):
                problems.add("confirmed_iteration_without_measurement")
            if row.get("oracle_status") != "passed":
                problems.add("confirmed_iteration_without_parity")
            if row.get("failure_path_status") != "preserved":
                problems.add("confirmed_iteration_without_failure_path")
            for field in ("baseline_value", "comparison_value"):
                value = row.get(field)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or value < 0
                ):
                    problems.add("confirmed_iteration_without_numeric_measurement")
        expected_direction = {
            "wall_time": "lower",
            "queue_delay": "lower",
            "handoff_latency": "lower",
            "throughput": "higher",
        }.get(str(row.get("metric_kind")))
        if expected_direction is None or row.get("better_is") != expected_direction:
            problems.add("iteration_metric_direction_mismatch")
        active_iteration_ids = {
            str(item.get("bottleneck_id"))
            for item in bottlenecks
            if isinstance(item, Mapping) and item.get("category") == "iteration_cycle"
        }
        if row.get("bottleneck_ref") in active_iteration_ids and (
            row.get("status") != "confirmed" or row.get("drag_observed") is not True
        ):
            problems.add("iteration_bottleneck_without_measured_drag")

    routing = packet.get("routing", {})
    if isinstance(routing, Mapping):
        worker_role_ids = routing.get("worker_role_ids", [])
        if not isinstance(worker_role_ids, list) or set(worker_role_ids) - _WORKER_ROLE_IDS:
            problems.add("unresolved_worker_role_id")
        fanout_status = routing.get("fanout_status")
        checker = routing.get("checker_lineage", {})
        if fanout_status == "deterministic_v0_not_dispatched":
            if routing.get("semantic_agent_fanout") != 0:
                problems.add("deterministic_builder_claimed_agent_fanout")
            if not isinstance(checker, Mapping) or checker.get("verdict") != "not_run":
                problems.add("deterministic_builder_claimed_checker_verdict")
            if isinstance(checker, Mapping) and checker.get("lineage_complete") is not False:
                problems.add("deterministic_builder_claimed_complete_lineage")
        elif fanout_status == "agent_assisted_frozen_input":
            if not isinstance(checker, Mapping) or not checker.get("lineage_complete"):
                problems.add("agent_assisted_lineage_incomplete")
            if isinstance(checker, Mapping) and not checker.get("distinct_from_foreman"):
                problems.add("lineage_collision_not_blocked")
        else:
            problems.add("unknown_fanout_status")

    for path, value in _walk(packet):
        if path and path[-1].casefold() in _FORBIDDEN_ACTION_FIELDS:
            problems.add("forbidden_action_field")
        if path and path[-1].casefold() in _FORBIDDEN_SCORE_FIELDS:
            problems.add("forbidden_score_field")
        if isinstance(value, str) and _RAW_PATH_RE.search(value):
            problems.add("raw_path_exposed")
    ask_ids = [
        str(row.get("ask_id", "")) for row in human_asks if isinstance(row, Mapping)
    ]
    ask_refs = [
        str(row.get("bottleneck_ref", "")) for row in human_asks if isinstance(row, Mapping)
    ]
    if len(ask_ids) != len(set(ask_ids)) or len(ask_refs) != len(set(ask_refs)):
        problems.add("duplicate_human_ask")
    overflow_ref_list = [
        str(row.get("bottleneck_ref", ""))
        for row in overflow_items
        if isinstance(row, Mapping)
    ]
    if len(overflow_ref_list) != len(set(overflow_ref_list)):
        problems.add("duplicate_overflow_reference")
    return sorted(problems)


def write_portfolio_capacity_review_output(
    hub_root: Path,
    packet: Mapping[str, Any],
    *,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    """Validate and atomically publish only the derived local JSON sidecar."""

    validation_root = schema_root or hub_root
    structural = schema_validation_problems(
        dict(packet), validation_root, "portfolio_capacity_review"
    )
    if structural:
        raise ValueError("Invalid portfolio capacity review packet: " + "; ".join(structural))
    semantic = portfolio_capacity_review_semantic_problems(packet)
    if semantic:
        raise ValueError("Invalid portfolio capacity review semantics: " + "; ".join(semantic))
    output_path = data_path(hub_root, "central_reports") / "portfolio_os" / "capacity_review.json"
    atomic_write_text(output_path, json_dumps(dict(packet), pretty=True) + "\n")
    return {
        "status": packet["status"],
        "output_ref": "DAD_DATA_ROOT/processed/reports/portfolio_os/capacity_review.json",
        "human_ask_count": len(packet["human_asks"]),
        "bottleneck_count": len(packet["bottlenecks"]),
        "suppressed_count": len(packet["suppressed"]),
        "material_fingerprint": packet["material_fingerprint"],
        "authority_boundary": packet["authority_boundary"],
        "generated_at": packet["generated_at"],
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BUILDER_CONTRACT_REVISION",
    "CapacityReviewSettings",
    "MATURITY_STATES",
    "MISSION_SCHEMA_VERSION",
    "MISSION_STATES",
    "PRECEDENCE_BANDS",
    "SCHEMA_VERSION",
    "build_portfolio_capacity_review",
    "load_repo_mission_coverage",
    "portfolio_capacity_review_semantic_problems",
    "write_portfolio_capacity_review_output",
]
