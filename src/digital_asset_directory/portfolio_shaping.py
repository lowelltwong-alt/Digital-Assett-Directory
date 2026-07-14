"""Candidate-only workstream shaping for the DAD Portfolio OS.

This pure projection turns strict current snapshots into inert review cases. It
never records or executes a decision and never mutates Git or source state.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import base64
import hashlib
import itertools
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from .ids import stable_id
from .portfolio_cockpit import (
    SCHEMA_VERSION as COCKPIT_SCHEMA_VERSION,
    projection_hash,
    schema_validation_problems,
)
from .portfolio_reconciliation import (
    SCHEMA_VERSION as RECONCILIATION_SCHEMA_VERSION,
    cockpit_projection_hash,
    portfolio_reconciliation_semantic_problems,
)
from .portfolio_relations import RelationTarget, classify_relations
from .transport import data_path
from .utils import atomic_write_text, json_dumps

SCHEMA_VERSION = "dad.portfolio_workstream_shaping.v2"
WORKSTREAM_SCHEMA_VERSION = "dad.portfolio_workstreams.v1"
METHOD_ID = "dad.portfolio-workstream-shaping.v2"
METHODOLOGY_REF = "docs/frontier/collaboration/13_PORTFOLIO_WORKSTREAM_SHAPING.md"
TERMINAL_STATES = frozenset({"merged", "superseded", "archived"})
QUIET_STATES = frozenset({"paused", "snoozed", "incubating"})
SPECIFIC_RESOURCE_KINDS = frozenset({"branch", "worktree"})
CASE_KINDS = ("split", "rescope", "possible_duplicate", "recovery")
_CASE_ORDER = {kind: index for index, kind in enumerate(CASE_KINDS)}
_ABSOLUTE_PATH_RE = re.compile(
    r"(?:"
    r"(?:[A-Za-z]:[\\/])|"
    r"(?:\\\\(?:[?.]\\)?[^\\/\s]+[\\/])|"
    r"(?:^|(?<=[\s\"'=(]))/(?!/)[^\s\"'<>]+|"
    r"(?:^|(?<=[\s\"'=(]))~[\\/]"
    r")",
    re.IGNORECASE,
)
_SAFE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,99}$")
_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,999}$")
_AGE_ONLY_REASONS = frozenset({"stale_branch", "stale_branch_in_active_project"})
_DECISION_STATES = frozenset({"active", "retracted", "stale"})
_RESULT_STATES = frozenset({"verified", "failed", "aborted"})
_RECOVERY_PROJECTION_SCHEMA_VERSION = "dad.portfolio_recovery_projection.v1"
_MANUAL_ACTION_STATES = frozenset(
    {"none", "pending", "verified", "failed", "aborted", "not_required"}
)
_TIER_CONTRACTS: dict[str, tuple[str, str, str]] = {
    "PD0_shared_exact_specific_resource": (
        "possible_duplicate",
        "review",
        "possible_duplicate",
    ),
    "PD1_reciprocal_exact_pair_split_between_workstreams": (
        "possible_duplicate",
        "review",
        "possible_duplicate",
    ),
    "PD2_similarity_only": (
        "possible_duplicate",
        "inspect_only",
        "possible_duplicate",
    ),
    "SP0_disconnected_exact_owned_components": ("split", "review", "split"),
    "RS0_exact_contextual_unassigned_bundle": ("rescope", "review", "rescope"),
    "RS1_repo_context_only": ("rescope", "inspect_only", "rescope"),
    "RC0_integrity_unknown_attention": ("recovery", "review", "integrity_unknown"),
    "RC1_dirty_exact_attention": ("recovery", "review", "recovery"),
    "RC2_existing_workstream_trigger": ("recovery", "review", "recovery"),
    "RC3_unassigned_observed_bundle": (
        "recovery",
        "review",
        "unassigned_recovery",
    ),
}
_CASE_LABELS = {
    "PD0_shared_exact_specific_resource": "Exact resource ownership collision",
    "PD1_reciprocal_exact_pair_split_between_workstreams": (
        "Reciprocal branch and worktree ownership split"
    ),
    "PD2_similarity_only": "Possible intent overlap",
    "SP0_disconnected_exact_owned_components": "Disconnected exact scope review",
    "RS0_exact_contextual_unassigned_bundle": "Exact contextual scope review",
    "RS1_repo_context_only": "Repository-context scope inspection",
    "RC0_integrity_unknown_attention": "Integrity evidence review",
    "RC1_dirty_exact_attention": "Dirty exact work recovery",
    "RC2_existing_workstream_trigger": "Existing workstream trigger review",
    "RC3_unassigned_observed_bundle": "Unassigned observed work review",
}

AUTHORITY_BOUNDARY = (
    "This is a local, snapshot-bound candidate projection. It cannot append ledger "
    "events, record or apply decisions, choose a canonical workstream, or mutate Git, "
    "tasks, schedules, notifications, agents, bindings, or source authority. The CLI "
    "may publish read-only derived reports."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ShapingSettings:
    """Bounded display and freshness policy for shaping cases."""

    case_limit: int = 250
    review_limit: int = 3
    fresh_after_hours: int = 26
    future_tolerance_hours: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.case_limit <= 500:
            raise ValueError("case_limit must be between 1 and 500")
        if not 1 <= self.review_limit <= 3:
            raise ValueError("review_limit must be between 1 and 3")
        if self.fresh_after_hours < 1:
            raise ValueError("fresh_after_hours must be at least 1")
        if self.future_tolerance_hours < 0:
            raise ValueError("future_tolerance_hours cannot be negative")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_descriptor(
    name: str,
    value: Any,
    *,
    expected_schema: str,
    schema_name: str,
    schema_root: Path,
    now: datetime,
    fresh_after_hours: int,
    future_tolerance_hours: int,
    hash_fn: Callable[[dict[str, Any]], str] = projection_hash,
    semantic_validator: Callable[[dict[str, Any]], list[str]] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "name": name,
            "status": "invalid" if value is not None else "unavailable",
            "freshness": "unknown",
            "schema_version": "",
            "generated_at": "",
            "source_hash": _canonical_hash(value) if value is not None else "",
            "problems": ["source_not_object" if value is not None else "source_unavailable"],
        }
    structural: list[str] = []
    schema_version = str(value.get("schema_version", ""))
    if schema_version != expected_schema:
        structural.append("unexpected_schema")
    schema_problems = schema_validation_problems(value, schema_root, schema_name)
    if schema_problems:
        structural.append("schema_invalid")
    if not schema_problems and semantic_validator is not None and semantic_validator(value):
        structural.append("semantic_invalid")
    generated = _parse_datetime(value.get("generated_at"))
    freshness_problems: list[str] = []
    if generated is None:
        freshness = "unknown"
        freshness_problems.append("generated_at_invalid_or_missing")
    else:
        age_hours = (now - generated).total_seconds() / 3600
        if age_hours < -future_tolerance_hours:
            freshness = "future"
            freshness_problems.append("generated_at_in_future")
        elif age_hours > fresh_after_hours:
            freshness = "stale"
            freshness_problems.append("source_stale")
        else:
            freshness = "current"
    return {
        "name": name,
        "status": "observed" if not structural else "invalid",
        "freshness": freshness,
        "schema_version": schema_version if schema_version == expected_schema else "",
        "generated_at": generated.isoformat() if generated is not None else "",
        "source_hash": hash_fn(value),
        "problems": sorted(set([*structural, *freshness_problems])),
    }


def _canonical_strings(values: Any) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _safe_token(value: Any, fallback: str) -> str:
    text = str(value or "").strip().casefold()
    return text if _SAFE_TOKEN_RE.fullmatch(text) else fallback


def _opaque_ref(value: Any, namespace: str) -> str:
    text = str(value or "")
    return stable_id(METHOD_ID, namespace, _canonical_hash(text)) if text else ""


def _choice(case_id: str, choice_kind: str, label: str, effect: str) -> dict[str, Any]:
    return {
        "choice_id": stable_id(case_id, choice_kind),
        "choice_kind": choice_kind,
        "label": label,
        "effect_preview": effect,
        "execution_available": False,
        "requires_human_decision": True,
    }


_CHOICE_SPECS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "split": (
        ("keep_one_scope", "Keep one scope", "Leave the current boundary unchanged."),
        (
            "draft_split_plan",
            "Draft a split plan",
            "Describe separate future workstreams without creating them.",
        ),
        (
            "consider_move_component",
            "Consider moving a component",
            "Review one exact component for later reassignment.",
        ),
        ("defer", "Defer", "Make no state change and revisit with better evidence."),
    ),
    "rescope": (
        (
            "include_bundle_later",
            "Include later",
            "Consider an exact bundle for later accepted ownership.",
        ),
        (
            "create_sibling_later",
            "Create sibling later",
            "Consider a separate workstream after human review.",
        ),
        (
            "leave_unassigned",
            "Leave unassigned",
            "Preserve the current lack of accepted ownership.",
        ),
        ("defer", "Defer", "Make no state change and revisit with better evidence."),
    ),
    "possible_duplicate": (
        (
            "compare_side_by_side",
            "Compare side by side",
            "Inspect boundaries without selecting a winner.",
        ),
        ("keep_distinct", "Keep distinct", "Preserve both workstreams as separate intent."),
        ("link_later", "Link later", "Consider a sibling or experiment relation after review."),
        (
            "choose_canonical_later",
            "Choose canonical later",
            "Defer any canonical decision to a human.",
        ),
        ("defer", "Defer", "Make no state change and revisit with better evidence."),
    ),
    "recovery": (
        ("resume_later", "Resume later", "Consider resuming after inspecting local evidence."),
        (
            "checkpoint_and_pause_later",
            "Checkpoint and pause later",
            "Consider a reversible authorized checkpoint.",
        ),
        (
            "snooze_later",
            "Snooze later",
            "Consider an explicit review date through a separate command.",
        ),
        ("review", "Review", "Inspect exact local evidence without changing state."),
        ("defer", "Defer", "Make no state change and revisit with better evidence."),
    ),
    "integrity_unknown": (
        (
            "inspect_evidence",
            "Inspect evidence",
            "Resolve the evidence gap before a lifecycle choice.",
        ),
        ("defer", "Defer", "Make no state change while evidence remains uncertain."),
    ),
    "unassigned_recovery": (
        (
            "review_as_new_workstream",
            "Review as new workstream",
            "Consider intake without creating a workstream.",
        ),
        (
            "associate_after_review",
            "Associate after review",
            "Compare exact ownership candidates before binding.",
        ),
        (
            "leave_unassigned",
            "Leave unassigned",
            "Preserve the current lack of accepted ownership.",
        ),
        ("defer", "Defer", "Make no state change and revisit with better evidence."),
    ),
}


def _make_case(
    *,
    case_kind: str,
    evidence_tier: str,
    disposition: str,
    label: str,
    subject_workstream_ids: list[str] | tuple[str, ...] = (),
    subject_resource_ids: list[str] | tuple[str, ...] = (),
    source_attention_ids: list[str] | tuple[str, ...] = (),
    source_bundle_ids: list[str] | tuple[str, ...] = (),
    signals: list[str] | tuple[str, ...] = (),
    counterevidence: list[str] | tuple[str, ...] = (),
    evidence_summary: dict[str, Any],
    choice_profile: str | None = None,
) -> dict[str, Any]:
    workstream_ids = _canonical_strings(subject_workstream_ids)
    resource_ids = _canonical_strings(subject_resource_ids)
    attention_ids = _canonical_strings(source_attention_ids)
    bundle_ids = _canonical_strings(source_bundle_ids)
    case_id = stable_id(
        METHOD_ID,
        case_kind,
        "|".join(workstream_ids),
        "|".join(resource_ids),
        "|".join(attention_ids),
        "|".join(bundle_ids),
    )
    profile = choice_profile or case_kind
    choices = [_choice(case_id, *spec) for spec in _CHOICE_SPECS[profile]]
    row = {
        "case_id": case_id,
        "revision_id": "",
        "case_kind": case_kind,
        "evidence_tier": evidence_tier,
        "disposition": disposition,
        "label": _CASE_LABELS[evidence_tier],
        "subject_workstream_ids": workstream_ids,
        "subject_resource_ids": resource_ids,
        "source_attention_ids": attention_ids,
        "source_bundle_ids": bundle_ids,
        "signals": _canonical_strings(signals),
        "counterevidence": _canonical_strings(counterevidence),
        "evidence_summary": {
            "exact_component_count": int(evidence_summary.get("exact_component_count", 0)),
            "project_count": int(evidence_summary.get("project_count", 0)),
            "shared_specific_resource_count": int(
                evidence_summary.get("shared_specific_resource_count", 0)
            ),
            "shared_token_count": int(evidence_summary.get("shared_token_count", 0)),
            "shared_token_hashes": _canonical_strings(
                evidence_summary.get("shared_token_hashes", [])
            ),
            "attention_bands": _canonical_strings(evidence_summary.get("attention_bands", [])),
            "trigger_kinds": _canonical_strings(evidence_summary.get("trigger_kinds", [])),
            "context_basis": str(evidence_summary.get("context_basis", "none")),
        },
        "choices": choices,
    }
    material = {
        key: row[key]
        for key in (
            "case_kind",
            "evidence_tier",
            "disposition",
            "subject_workstream_ids",
            "subject_resource_ids",
            "source_attention_ids",
            "source_bundle_ids",
            "signals",
            "counterevidence",
            "evidence_summary",
        )
    }
    material["choice_kinds"] = [choice["choice_kind"] for choice in choices]
    row["revision_id"] = stable_id(case_id, _canonical_hash(material))
    return row


def _attention_specific_ids(
    item: dict[str, Any], resources: dict[str, dict[str, Any]]
) -> list[str]:
    return sorted(
        resource_id
        for resource_id in _canonical_strings(item.get("resource_ids", []))
        if resource_id in resources
        and resources[resource_id]["resource_kind"] in SPECIFIC_RESOURCE_KINDS
    )


def _components(resource_ids: list[str], resources: dict[str, dict[str, Any]]) -> list[list[str]]:
    remaining = set(resource_ids)
    components: list[list[str]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        stack = [start]
        component = {start}
        while stack:
            current = stack.pop()
            row = resources[current]
            for linked_id in row.get("linked_resource_ids", []):
                linked = str(linked_id)
                if linked not in remaining or linked not in resources:
                    continue
                target = resources[linked]
                reciprocal = current in set(
                    str(value) for value in target.get("linked_resource_ids", [])
                )
                compatible = (
                    row["resource_kind"] in SPECIFIC_RESOURCE_KINDS
                    and target["resource_kind"] in SPECIFIC_RESOURCE_KINDS
                    and row["resource_kind"] != target["resource_kind"]
                    and row["project_id"] == target["project_id"]
                )
                if reciprocal and compatible:
                    remaining.remove(linked)
                    component.add(linked)
                    stack.append(linked)
        components.append(sorted(component))
    return sorted(components, key=lambda values: tuple(values))


def _case_sort_key(row: dict[str, Any], today_order: dict[str, int]) -> tuple[Any, ...]:
    positions = [
        today_order[value] for value in row["source_attention_ids"] if value in today_order
    ]
    return (
        0 if positions else 1,
        min(positions) if positions else 10_000,
        _CASE_ORDER[row["case_kind"]],
        row["evidence_tier"],
        row["case_id"],
    )


def _unknown_row(row: dict[str, Any]) -> dict[str, str]:
    severity = str(row.get("severity", "warning"))
    return {
        "source": "reconciliation",
        "kind": _safe_token(row.get("kind"), "unknown"),
        "ref": _opaque_ref(row.get("ref"), "unknown-ref"),
        "note": "Evidence remains incomplete; inspect the source projection locally.",
        "severity": severity if severity in {"info", "warning", "danger"} else "warning",
    }


def _empty_decision_annotation() -> dict[str, str]:
    return {
        "state": "none",
        "decision_id": "",
        "choice_id": "",
        "choice_kind": "",
        "disposition": "",
        "review_after": "",
        "manual_action_state": "none",
        "result_ref": "",
    }


def _safe_ref(value: Any, namespace: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if _SAFE_REF_RE.fullmatch(text) else _opaque_ref(text, namespace)


def _shaping_source_snapshot_digest(
    sources: Mapping[str, Any], source_coupling: Mapping[str, Any]
) -> str:
    required = ("workstreams", "cockpit", "reconciliation")
    source_refs = {
        name: str(sources.get(name, {}).get("source_hash", "")) for name in required
    }
    descriptors = {
        name: {
            key: sources.get(name, {}).get(key, "")
            for key in (
                "status",
                "freshness",
                "schema_version",
                "generated_at",
                "source_hash",
            )
        }
        for name in required
    }
    return _canonical_hash(
        {
            "schema_version": SCHEMA_VERSION,
            "source_refs": source_refs,
            "sources": descriptors,
            "source_coupling": source_coupling,
        }
    )


def _case_preconditions_digest(case: Mapping[str, Any]) -> str:
    keys = (
        "case_id",
        "revision_id",
        "case_kind",
        "evidence_tier",
        "disposition",
        "subject_workstream_ids",
        "subject_resource_ids",
        "source_attention_ids",
        "source_bundle_ids",
        "signals",
        "counterevidence",
        "evidence_summary",
        "choices",
    )
    return _canonical_hash({key: case.get(key) for key in keys})


def _decision_annotations(
    decisions: Mapping[str, Any] | None,
    cases: list[dict[str, Any]],
    *,
    source_snapshot_digest: str,
) -> tuple[dict[str, Any], dict[str, dict[str, str]], list[dict[str, str]]]:
    """Minimize a recovery fold into case-bound, non-authorizing annotations."""

    annotations = {str(row["case_id"]): _empty_decision_annotation() for row in cases}
    if decisions is None:
        return (
            {
                "source_status": "unavailable",
                "source_schema_version": "",
                "source_hash": "",
                "source_snapshot_digest": source_snapshot_digest,
                "decision_count": 0,
                "historical_decision_count": 0,
                "active_count": 0,
                "retracted_count": 0,
                "stale_count": 0,
                "pending_manual_action_count": 0,
                "verified_result_count": 0,
                "failed_result_count": 0,
                "aborted_result_count": 0,
                "unmatched_decision_count": 0,
                "problems": [],
            },
            annotations,
            [],
        )
    source_hash = _canonical_hash(decisions)
    if not isinstance(decisions, Mapping):
        descriptor = {
            "source_status": "invalid",
            "source_schema_version": "",
            "source_hash": source_hash,
            "source_snapshot_digest": source_snapshot_digest,
            "decision_count": 0,
            "historical_decision_count": 0,
            "active_count": 0,
            "retracted_count": 0,
            "stale_count": 0,
            "pending_manual_action_count": 0,
            "verified_result_count": 0,
            "failed_result_count": 0,
            "aborted_result_count": 0,
            "unmatched_decision_count": 0,
            "problems": ["decision_projection_not_object"],
        }
        return descriptor, annotations, [
            {
                "kind": "decision_projection_invalid",
                "ref": source_hash,
                "note": "Decision evidence is structurally invalid and was not applied.",
            }
        ]

    schema_version = _safe_token(decisions.get("schema_version"), "")
    raw_decisions = decisions.get("decisions", [])
    raw_results = decisions.get("results", [])
    problems: set[str] = set()
    if schema_version != _RECOVERY_PROJECTION_SCHEMA_VERSION:
        problems.add("decision_schema_invalid")
    if _safe_token(decisions.get("status"), "") != "ready":
        problems.add("decision_projection_not_ready")
    for field in ("execution_authorized", "mutations_performed", "source_authority_mutated"):
        if decisions.get(field) is not False:
            problems.add(f"decision_projection_{field}_invalid")
    if not isinstance(raw_decisions, list):
        problems.add("decisions_not_array")
        raw_decisions = []
    if not isinstance(raw_results, list):
        problems.add("results_not_array")
        raw_results = []

    result_by_decision: dict[str, dict[str, Any]] = {}
    for raw in raw_results:
        if not isinstance(raw, dict):
            problems.add("result_not_object")
            continue
        decision_id = _safe_ref(raw.get("decision_id"), "decision-result")
        if not decision_id:
            problems.add("result_decision_id_missing")
            continue
        if decision_id in result_by_decision:
            problems.add("duplicate_result_for_decision")
            continue
        result_by_decision[decision_id] = raw

    case_by_id = {str(row["case_id"]): row for row in cases}
    seen_decisions: set[str] = set()
    unmatched_count = 0
    for raw in raw_decisions:
        if not isinstance(raw, dict):
            problems.add("decision_not_object")
            continue
        decision_id = _safe_ref(raw.get("decision_id"), "decision")
        case_id = _safe_ref(raw.get("case_id"), "decision-case")
        if not decision_id or not case_id:
            problems.add("decision_identity_missing")
            continue
        if decision_id in seen_decisions:
            problems.add("duplicate_decision_id")
            continue
        seen_decisions.add(decision_id)
        case = case_by_id.get(case_id)
        if case is None:
            unmatched_count += 1
            continue

        raw_state = _safe_token(raw.get("status", raw.get("state", "active")), "stale")
        choice_id = _safe_ref(raw.get("choice_id"), "decision-choice")
        choice_kind = _safe_token(raw.get("choice_kind"), "unknown_choice")
        disposition = _safe_token(raw.get("disposition"), "review")
        review_after_value = _parse_datetime(raw.get("review_after"))
        review_after = review_after_value.isoformat() if review_after_value else ""
        canonical_choices = {
            str(choice.get("choice_id", "")): str(choice.get("choice_kind", ""))
            for choice in case.get("choices", [])
            if isinstance(choice, dict)
        }
        bound_snapshot = str(
            raw.get("source_snapshot_digest", raw.get("shaping_source_snapshot_digest", ""))
        )
        binding_valid = bool(
            str(raw.get("case_revision_id", "")) == str(case.get("revision_id", ""))
            and bound_snapshot == source_snapshot_digest
            and str(raw.get("expected_preconditions_digest", ""))
            == _case_preconditions_digest(case)
            and choice_id in canonical_choices
            and canonical_choices.get(choice_id) == choice_kind
        )
        state = (
            "retracted"
            if raw_state == "retracted"
            else "active"
            if raw_state == "active" and binding_valid
            else "stale"
        )

        result = result_by_decision.get(decision_id, {})
        if result.get("case_id") and str(result.get("case_id")) != case_id:
            problems.add("result_case_mismatch")
        result_state = _safe_token(
            result.get("result_status", result.get("status", "")), ""
        )
        result_ref = _safe_ref(
            result.get("result_id", result.get("packet_id", "")), "decision-result"
        )
        if result and result_state not in _RESULT_STATES:
            problems.add("result_status_invalid")
            result_state = ""
        if result and not result_ref:
            problems.add("result_ref_missing")
        if state == "retracted":
            manual_action_state = "none"
        elif result_state:
            manual_action_state = result_state
        elif choice_kind == "defer":
            manual_action_state = "not_required"
        else:
            manual_action_state = "pending"
        candidate = {
            "state": state,
            "decision_id": decision_id,
            "choice_id": choice_id,
            "choice_kind": choice_kind,
            "disposition": disposition,
            "review_after": review_after,
            "manual_action_state": manual_action_state,
            "result_ref": result_ref,
        }
        existing = annotations[case_id]
        if existing["state"] in {"active", "stale"} and state in {"active", "stale"}:
            problems.add("multiple_current_decisions_for_case")
        elif state in {"active", "stale"} or existing["state"] in {"none", "retracted"}:
            annotations[case_id] = candidate

    if set(result_by_decision) - seen_decisions:
        problems.add("result_decision_unmatched")
    selected_decision_count = sum(
        row["state"] != "none" for row in annotations.values()
    )
    historical_decision_count = max(
        0,
        len(seen_decisions) - unmatched_count - selected_decision_count,
    )
    if problems:
        annotations = {case_id: _empty_decision_annotation() for case_id in annotations}
    values = list(annotations.values())
    source_status = "invalid" if problems else "observed"
    descriptor = {
        "source_status": source_status,
        "source_schema_version": schema_version,
        "source_hash": source_hash,
        "source_snapshot_digest": source_snapshot_digest,
        "decision_count": len(seen_decisions),
        "historical_decision_count": historical_decision_count,
        "active_count": sum(row["state"] == "active" for row in values),
        "retracted_count": sum(row["state"] == "retracted" for row in values),
        "stale_count": sum(row["state"] == "stale" for row in values),
        "pending_manual_action_count": sum(
            row["manual_action_state"] == "pending" for row in values
        ),
        "verified_result_count": sum(
            row["manual_action_state"] == "verified" for row in values
        ),
        "failed_result_count": sum(row["manual_action_state"] == "failed" for row in values),
        "aborted_result_count": sum(
            row["manual_action_state"] == "aborted" for row in values
        ),
        "unmatched_decision_count": unmatched_count,
        "problems": sorted(problems),
    }
    blockers: list[dict[str, str]] = []
    if problems:
        blockers.append(
            {
                "kind": "decision_projection_invalid",
                "ref": source_hash,
                "note": "Decision evidence is structurally invalid and was not trusted.",
            }
        )
    if unmatched_count:
        blockers.append(
            {
                "kind": "decision_case_unmatched",
                "ref": stable_id(METHOD_ID, "unmatched-decisions", str(unmatched_count)),
                "note": "One or more decisions do not match a visible source case.",
            }
        )
    return descriptor, annotations, blockers


def build_portfolio_shaping(
    workstream_state: dict[str, Any] | None,
    cockpit: dict[str, Any] | None,
    reconciliation: dict[str, Any] | None,
    *,
    decisions: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    settings: ShapingSettings | None = None,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    """Build deterministic shaping choices without recording or executing one."""

    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    policy = settings or ShapingSettings()
    root = schema_root or Path(__file__).parents[2]
    sources = {
        "workstreams": _source_descriptor(
            "workstreams",
            workstream_state,
            expected_schema=WORKSTREAM_SCHEMA_VERSION,
            schema_name="portfolio_workstream_state",
            schema_root=root,
            now=observed,
            fresh_after_hours=policy.fresh_after_hours,
            future_tolerance_hours=policy.future_tolerance_hours,
        ),
        "cockpit": _source_descriptor(
            "cockpit",
            cockpit,
            expected_schema=COCKPIT_SCHEMA_VERSION,
            schema_name="portfolio_cockpit",
            schema_root=root,
            now=observed,
            fresh_after_hours=policy.fresh_after_hours,
            future_tolerance_hours=policy.future_tolerance_hours,
            hash_fn=cockpit_projection_hash,
        ),
        "reconciliation": _source_descriptor(
            "reconciliation",
            reconciliation,
            expected_schema=RECONCILIATION_SCHEMA_VERSION,
            schema_name="portfolio_reconciliation",
            schema_root=root,
            now=observed,
            fresh_after_hours=policy.fresh_after_hours,
            future_tolerance_hours=policy.future_tolerance_hours,
            semantic_validator=portfolio_reconciliation_semantic_problems,
        ),
    }
    blockers: list[dict[str, str]] = []
    for name, descriptor in sources.items():
        if descriptor["status"] != "observed" or descriptor["freshness"] != "current":
            blockers.append(
                {
                    "kind": "source_not_ready",
                    "ref": name,
                    "note": f"The {name} projection is invalid, stale, future-dated, or unavailable.",
                }
            )
    cockpit_value = cockpit if isinstance(cockpit, dict) else {}
    reconciliation_value = reconciliation if isinstance(reconciliation, dict) else {}
    cockpit_refs = cockpit_value.get("source_refs", {})
    if not isinstance(cockpit_refs, dict):
        cockpit_refs = {}
    reconciliation_refs = reconciliation_value.get("source_refs", {})
    if not isinstance(reconciliation_refs, dict):
        reconciliation_refs = {}
    reconciliation_summary = reconciliation_value.get("summary", {})
    if not isinstance(reconciliation_summary, dict):
        reconciliation_summary = {}
    source_coupling = {
        "workstreams_to_cockpit": {
            "actual_source_hash": sources["workstreams"]["source_hash"],
            "claimed_source_hash": str(cockpit_refs.get("workstreams", "")),
            "matches": bool(
                sources["workstreams"]["source_hash"]
                and sources["workstreams"]["source_hash"]
                == str(cockpit_refs.get("workstreams", ""))
            ),
        },
        "cockpit_to_reconciliation": {
            "actual_source_hash": sources["cockpit"]["source_hash"],
            "claimed_source_hash": str(reconciliation_refs.get("cockpit", "")),
            "matches": bool(
                sources["cockpit"]["source_hash"]
                and sources["cockpit"]["source_hash"] == str(reconciliation_refs.get("cockpit", ""))
            ),
        },
        "reconciliation_fully_reconciled": (reconciliation_summary.get("fully_reconciled") is True),
    }
    source_snapshot_digest = _shaping_source_snapshot_digest(sources, source_coupling)
    coupling_checks = (
        ("workstream_cockpit_hash_mismatch", source_coupling["workstreams_to_cockpit"]),
        (
            "cockpit_reconciliation_hash_mismatch",
            source_coupling["cockpit_to_reconciliation"],
        ),
    )
    for kind, link in coupling_checks:
        if not link["matches"]:
            blockers.append(
                {
                    "kind": kind,
                    "ref": stable_id("portfolio-shaping-source-coupling", kind),
                    "note": "Dependent projections do not describe the same frozen source snapshot.",
                }
            )
    source_ready = not any(
        row["kind"] == "source_not_ready" or "hash_mismatch" in row["kind"] for row in blockers
    )
    for row in reconciliation_value.get("blockers", []):
        if isinstance(row, dict):
            blockers.append(
                {
                    "kind": f"reconciliation:{_safe_token(row.get('kind'), 'blocker')}",
                    "ref": _opaque_ref(row.get("ref"), "blocker-ref"),
                    "note": "Reconciliation evidence remains blocked; inspect its local projection.",
                }
            )
    unknowns = sorted(
        (
            _unknown_row(row)
            for row in reconciliation_value.get("unknowns", [])
            if isinstance(row, dict)
        ),
        key=lambda row: (row["source"], row["kind"], row["ref"]),
    )
    workstreams = {
        str(row["workstream_id"]): row
        for row in cockpit_value.get("workstreams", [])
        if isinstance(row, dict) and row.get("workstream_id")
    }
    eligible = {
        workstream_id: row
        for workstream_id, row in workstreams.items()
        if str(row.get("lifecycle_state", "")) not in TERMINAL_STATES | QUIET_STATES
    }
    resources = {
        str(row["resource_id"]): row
        for row in cockpit_value.get("resources", [])
        if isinstance(row, dict) and row.get("resource_id")
    }
    attention = {
        str(row["attention_id"]): row
        for row in cockpit_value.get("attention_queue", [])
        if isinstance(row, dict) and row.get("attention_id")
    }
    today_ids = [
        str(row["attention_id"])
        for row in cockpit_value.get("today", [])
        if isinstance(row, dict) and row.get("attention_id")
    ]
    today_order = {attention_id: index for index, attention_id in enumerate(today_ids)}
    bundles = [
        row for row in reconciliation_value.get("unassigned_bundles", []) if isinstance(row, dict)
    ]
    cases: list[dict[str, Any]] = []
    pair_has_exact_evidence: set[tuple[str, str]] = set()
    label_pair_count = 0
    unevaluated_label_pair_count = 0
    workstreams_without_exact_bindings: list[str] = []
    exact_context_bundle_count = 0
    repo_context_bundle_count = 0

    if source_ready:
        for resource_id, resource in sorted(resources.items()):
            if resource.get("resource_kind") not in SPECIFIC_RESOURCE_KINDS:
                continue
            owners = sorted(
                value
                for value in _canonical_strings(resource.get("accepted_workstream_ids", []))
                if value in eligible
            )
            for left, right in itertools.combinations(owners, 2):
                pair_has_exact_evidence.add((left, right))
                cases.append(
                    _make_case(
                        case_kind="possible_duplicate",
                        evidence_tier="PD0_shared_exact_specific_resource",
                        disposition="review",
                        label="Two workstreams claim the same exact resource",
                        subject_workstream_ids=[left, right],
                        subject_resource_ids=[resource_id],
                        signals=["shared_exact_accepted_ownership"],
                        counterevidence=[
                            "canonical_workstream_not_selected",
                            "human_identity_decision_required",
                        ],
                        evidence_summary={
                            "shared_specific_resource_count": 1,
                            "project_count": 1,
                            "context_basis": "accepted_exact_collision",
                        },
                    )
                )

        seen_structural_pairs: set[tuple[str, str]] = set()
        for resource_id, resource in sorted(resources.items()):
            if resource.get("resource_kind") != "branch":
                continue
            for linked_id in _canonical_strings(resource.get("linked_resource_ids", [])):
                linked = resources.get(linked_id)
                if not linked or linked.get("resource_kind") != "worktree":
                    continue
                if resource_id not in set(
                    str(value) for value in linked.get("linked_resource_ids", [])
                ):
                    continue
                if resource.get("project_id") != linked.get("project_id"):
                    continue
                structural_key = (resource_id, linked_id)
                if structural_key in seen_structural_pairs:
                    continue
                seen_structural_pairs.add(structural_key)
                branch_owners = [
                    v
                    for v in _canonical_strings(resource.get("accepted_workstream_ids", []))
                    if v in eligible
                ]
                worktree_owners = [
                    v
                    for v in _canonical_strings(linked.get("accepted_workstream_ids", []))
                    if v in eligible
                ]
                for left in branch_owners:
                    for right in worktree_owners:
                        if left == right:
                            continue
                        pair = tuple(sorted((left, right)))
                        pair_has_exact_evidence.add(pair)
                        cases.append(
                            _make_case(
                                case_kind="possible_duplicate",
                                evidence_tier="PD1_reciprocal_exact_pair_split_between_workstreams",
                                disposition="review",
                                label="A reciprocal branch/worktree pair is split between workstreams",
                                subject_workstream_ids=list(pair),
                                subject_resource_ids=[resource_id, linked_id],
                                signals=["reciprocal_exact_pair_split_ownership"],
                                counterevidence=[
                                    "canonical_workstream_not_selected",
                                    "scope_intent_not_observed",
                                ],
                                evidence_summary={
                                    "project_count": 1,
                                    "exact_component_count": 1,
                                    "context_basis": "reciprocal_exact_pair",
                                },
                            )
                        )

        for left, right in itertools.combinations(sorted(eligible), 2):
            pair = (left, right)
            if pair in pair_has_exact_evidence:
                continue
            label_pair_count += 1
            source_label = str(eligible[left].get("label", ""))
            target_label = str(eligible[right].get("label", ""))
            relations, coverage_notes = classify_relations(
                left,
                source_label,
                [
                    RelationTarget(
                        target_kind="workstream",
                        target_id=right,
                        target_label=target_label,
                        text=target_label,
                        mature=False,
                    )
                ],
                limit=1,
            )
            if coverage_notes:
                unevaluated_label_pair_count += 1
            if not relations or relations[0]["relationship_type"] != "duplicate":
                continue
            shared = _canonical_strings(relations[0].get("shared_tokens", []))
            if len(shared) < 3:
                continue
            cases.append(
                _make_case(
                    case_kind="possible_duplicate",
                    evidence_tier="PD2_similarity_only",
                    disposition="inspect_only",
                    label="Two workstream labels may describe overlapping intent",
                    subject_workstream_ids=[left, right],
                    signals=["deterministic_label_similarity"],
                    counterevidence=[
                        "similarity_is_not_identity",
                        "shortened_labels_may_omit_scope",
                    ],
                    evidence_summary={
                        "shared_token_count": len(shared),
                        "shared_token_hashes": [_canonical_hash(token) for token in shared],
                        "context_basis": "similarity_only",
                    },
                )
            )

        for workstream_id, workstream in sorted(eligible.items()):
            owned = sorted(
                resource_id
                for resource_id in _canonical_strings(workstream.get("accepted_resource_ids", []))
                if resource_id in resources
                and resources[resource_id].get("resource_kind") in SPECIFIC_RESOURCE_KINDS
            )
            if not owned:
                workstreams_without_exact_bindings.append(workstream_id)
                continue
            components = _components(owned, resources)
            project_ids = {
                str(resources[resource_id].get("project_id", "")) for resource_id in owned
            }
            attention_component_count = sum(
                any(
                    set(component) & set(_attention_specific_ids(item, resources))
                    for item in attention.values()
                )
                for component in components
            )
            if len(components) < 2 or (len(project_ids) < 2 and attention_component_count < 2):
                continue
            source_attention_ids = [
                attention_id
                for attention_id, item in attention.items()
                if set(owned) & set(_attention_specific_ids(item, resources))
            ]
            cases.append(
                _make_case(
                    case_kind="split",
                    evidence_tier="SP0_disconnected_exact_owned_components",
                    disposition="review",
                    label=f"{workstream.get('label', 'Workstream')} spans disconnected exact components",
                    subject_workstream_ids=[workstream_id],
                    subject_resource_ids=owned,
                    source_attention_ids=source_attention_ids,
                    signals=["disconnected_exact_owned_components"],
                    counterevidence=[
                        "cross_project_scope_may_be_intentional",
                        "typed_dependency_scope_not_observed",
                    ],
                    evidence_summary={
                        "exact_component_count": len(components),
                        "project_count": len(project_ids),
                        "attention_bands": [
                            item.get("band", "")
                            for item in attention.values()
                            if set(owned) & set(_attention_specific_ids(item, resources))
                        ],
                        "context_basis": "accepted_exact_components",
                    },
                )
            )

        attention_in_bundles: set[str] = set()
        for bundle in bundles:
            bundle_id = str(bundle.get("bundle_id", ""))
            attention_ids = _canonical_strings(bundle.get("attention_ids", []))
            attention_in_bundles.update(attention_ids)
            context_workstream_id = str(bundle.get("context_workstream_id", ""))
            resource_ids = _canonical_strings(bundle.get("resource_ids", []))
            bundle_attention = [attention[value] for value in attention_ids if value in attention]
            if context_workstream_id in eligible:
                exact_context = any(
                    str(item.get("workstream_id", "")) == context_workstream_id
                    and bool(set(resource_ids) & set(_attention_specific_ids(item, resources)))
                    for item in bundle_attention
                )
                tier = (
                    "RS0_exact_contextual_unassigned_bundle"
                    if exact_context
                    else "RS1_repo_context_only"
                )
                exact_context_bundle_count += int(exact_context)
                repo_context_bundle_count += int(not exact_context)
                cases.append(
                    _make_case(
                        case_kind="rescope",
                        evidence_tier=tier,
                        disposition="review" if exact_context else "inspect_only",
                        label=str(bundle.get("label", "Unassigned exact resource bundle")),
                        subject_workstream_ids=[context_workstream_id],
                        subject_resource_ids=resource_ids,
                        source_attention_ids=attention_ids,
                        source_bundle_ids=[bundle_id],
                        signals=["unassigned_exact_bundle_with_context"],
                        counterevidence=(
                            ["accepted_ownership_not_observed"]
                            if exact_context
                            else [
                                "accepted_ownership_not_observed",
                                "repo_context_is_not_specific_identity",
                            ]
                        ),
                        evidence_summary={
                            "project_count": len(
                                {
                                    str(resources[value].get("project_id", ""))
                                    for value in resource_ids
                                    if value in resources
                                }
                            ),
                            "attention_bands": [item.get("band", "") for item in bundle_attention],
                            "context_basis": "exact_attention_assignment"
                            if exact_context
                            else "repo_context_only",
                        },
                    )
                )
                continue

            bands = _canonical_strings(item.get("band", "") for item in bundle_attention)
            observed_reasons = {
                str(reason)
                for item in bundle_attention
                for reason in item.get("reasons", [])
                if str(reason)
            }
            any_integrity = "integrity_unknown" in bands
            any_dirty_recovery = any(
                item.get("band") == "dirty_recovery"
                and item.get("evidence", {}).get("git", {}).get("dirty") is True
                for item in bundle_attention
            )
            if any_integrity:
                tier, profile = "RC0_integrity_unknown_attention", "integrity_unknown"
                signals = ["integrity_evidence_unknown"]
            elif any_dirty_recovery:
                tier, profile = "RC1_dirty_exact_attention", "recovery"
                signals = ["dirty_exact_attention"]
            elif observed_reasons - _AGE_ONLY_REASONS:
                tier, profile = "RC3_unassigned_observed_bundle", "unassigned_recovery"
                signals = ["observed_exact_bundle_without_workstream"]
            else:
                continue
            cases.append(
                _make_case(
                    case_kind="recovery",
                    evidence_tier=tier,
                    disposition="review",
                    label=str(bundle.get("label", "Unassigned observed work")),
                    subject_resource_ids=resource_ids,
                    source_attention_ids=attention_ids,
                    source_bundle_ids=[bundle_id],
                    signals=signals,
                    counterevidence=["workstream_identity_not_observed", "age_is_annotation_only"],
                    evidence_summary={
                        "project_count": len(
                            {
                                str(resources[value].get("project_id", ""))
                                for value in resource_ids
                                if value in resources
                            }
                        ),
                        "attention_bands": bands,
                        "context_basis": "unassigned_exact_bundle",
                    },
                    choice_profile=profile,
                )
            )

        for attention_id, item in sorted(attention.items()):
            if attention_id in attention_in_bundles:
                continue
            workstream_id = str(item.get("workstream_id", ""))
            band = str(item.get("band", ""))
            specific_ids = _attention_specific_ids(item, resources)
            evidence = item.get("evidence", {})
            workstream_evidence = (
                evidence.get("workstream", {}) if isinstance(evidence, dict) else {}
            )
            trigger_kind_value = str(workstream_evidence.get("trigger_kind", ""))
            trigger_kind = (
                _safe_token(trigger_kind_value, "other_trigger") if trigger_kind_value else ""
            )
            trigger_signature = str(workstream_evidence.get("trigger_signature", ""))
            if band == "integrity_unknown":
                tier, profile, signals = (
                    "RC0_integrity_unknown_attention",
                    "integrity_unknown",
                    ["integrity_evidence_unknown"],
                )
            elif (
                band == "dirty_recovery"
                and evidence.get("git", {}).get("dirty") is True
                and specific_ids
            ):
                tier, profile, signals = (
                    "RC1_dirty_exact_attention",
                    "recovery",
                    ["dirty_exact_attention"],
                )
            elif (
                workstream_id in eligible
                and trigger_kind
                and trigger_signature
                and band in {"human_decision", "related_active_neglect", "weekly_maintenance"}
            ):
                tier, profile, signals = (
                    "RC2_existing_workstream_trigger",
                    "recovery",
                    ["existing_workstream_trigger"],
                )
            else:
                continue
            cases.append(
                _make_case(
                    case_kind="recovery",
                    evidence_tier=tier,
                    disposition="review",
                    label=str(item.get("label", "Work needing recovery review")),
                    subject_workstream_ids=[workstream_id] if workstream_id in eligible else [],
                    subject_resource_ids=specific_ids,
                    source_attention_ids=[attention_id],
                    signals=signals,
                    counterevidence=["age_is_annotation_only", "lifecycle_change_not_authorized"],
                    evidence_summary={
                        "project_count": len(
                            {str(resources[value].get("project_id", "")) for value in specific_ids}
                        ),
                        "attention_bands": [band],
                        "trigger_kinds": [trigger_kind] if trigger_kind else [],
                        "context_basis": "accepted_attention_join"
                        if workstream_id
                        else "observed_attention",
                    },
                    choice_profile=profile,
                )
            )

    deduplicated: dict[str, dict[str, Any]] = {}
    for row in cases:
        deduplicated.setdefault(row["case_id"], row)
    all_cases = sorted(deduplicated.values(), key=lambda row: _case_sort_key(row, today_order))
    decision_projection, decision_annotations, decision_blockers = _decision_annotations(
        decisions,
        all_cases,
        source_snapshot_digest=source_snapshot_digest,
    )
    blockers.extend(decision_blockers)
    for row in all_cases:
        row["decision"] = decision_annotations[row["case_id"]]
    visible_cases = all_cases[: policy.case_limit]
    hidden_case_count = len(all_cases) - len(visible_cases)
    review_queue: list[dict[str, Any]] = []
    for row in visible_cases:
        if row["decision"]["state"] in {"active", "stale"}:
            continue
        matched_today = [value for value in row["source_attention_ids"] if value in today_order]
        if not matched_today:
            continue
        review_queue.append(
            {
                "review_id": stable_id(METHOD_ID, "review", row["case_id"], *matched_today),
                "case_id": row["case_id"],
                "case_kind": row["case_kind"],
                "evidence_tier": row["evidence_tier"],
                "attention_ids": matched_today,
                "label": row["label"],
                "next_action": "Review the inert choices; any later work requires a separate human gate.",
            }
        )
        if len(review_queue) >= policy.review_limit:
            break

    workstream_cards = []
    for workstream_id, workstream in sorted(eligible.items()):
        accepted_specific = sorted(
            value
            for value in _canonical_strings(workstream.get("accepted_resource_ids", []))
            if value in resources
            and resources[value].get("resource_kind") in SPECIFIC_RESOURCE_KINDS
        )
        workstream_cards.append(
            {
                "card_id": stable_id(METHOD_ID, "workstream-card", workstream_id),
                "workstream_id": workstream_id,
                "label": "Workstream",
                "lifecycle_state": str(workstream.get("lifecycle_state", "")),
                "accepted_specific_resource_ids": accepted_specific,
                "case_ids": [
                    row["case_id"]
                    for row in visible_cases
                    if workstream_id in row["subject_workstream_ids"]
                ],
                "missing_exact_scope": not accepted_specific,
            }
        )

    visible_counts = Counter(row["case_kind"] for row in visible_cases)
    shaping_complete = bool(
        source_ready
        and not blockers
        and not unknowns
        and eligible
        and not all_cases
        and not bundles
        and not workstreams_without_exact_bindings
        and source_coupling["workstreams_to_cockpit"]["matches"]
        and source_coupling["cockpit_to_reconciliation"]["matches"]
        and source_coupling["reconciliation_fully_reconciled"]
    )
    summary = {
        "workstream_count": len(workstreams),
        "eligible_workstream_count": len(eligible),
        "case_count": len(visible_cases),
        "hidden_case_count": hidden_case_count,
        "split_case_count": visible_counts["split"],
        "rescope_case_count": visible_counts["rescope"],
        "possible_duplicate_case_count": visible_counts["possible_duplicate"],
        "recovery_case_count": visible_counts["recovery"],
        "review_count": len(review_queue),
        "blocker_count": len(blockers),
        "unknown_count": len(unknowns),
        "shaping_complete": shaping_complete,
        "intake_needed": source_ready and not workstreams,
        "no_cases_generated": not all_cases,
    }
    status = (
        "blocked_candidate"
        if not source_ready
        else "partial_candidate"
        if blockers or unknowns
        else "generated_candidate"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "status": status,
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "execution_authorized": False,
        "mutations_performed": False,
        "decision_recorded": False,
        "source_authority_mutated": False,
        "publication_scope": "derived_reports_only",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "methodology": {
            "method_id": METHOD_ID,
            "methodology_ref": METHODOLOGY_REF,
            "case_limit": policy.case_limit,
            "review_limit": policy.review_limit,
            "fresh_after_hours": policy.fresh_after_hours,
            "future_tolerance_hours": policy.future_tolerance_hours,
            "evidence_precedence": [
                "exact accepted identity",
                "reciprocal exact structure",
                "exact attention context",
                "observed integrity or dirty state",
                "similarity inspect only",
            ],
            "age_creates_case": False,
            "critical_path_claimed": False,
        },
        "sources": sources,
        "source_coupling": source_coupling,
        "source_snapshot_digest": source_snapshot_digest,
        "decision_projection": decision_projection,
        "summary": summary,
        "review_queue": review_queue,
        "workstream_cards": workstream_cards,
        "cases": visible_cases,
        "coverage": {
            "eligible_workstream_ids": sorted(eligible),
            "source_resource_ids": sorted(resources),
            "source_attention_ids": sorted(attention),
            "source_bundle_ids": sorted(
                str(row.get("bundle_id", "")) for row in bundles if row.get("bundle_id")
            ),
            "today_attention_ids": today_ids,
            "quiet_workstream_ids": sorted(
                w
                for w, row in workstreams.items()
                if str(row.get("lifecycle_state", "")) in QUIET_STATES
            ),
            "terminal_workstream_ids": sorted(
                w
                for w, row in workstreams.items()
                if str(row.get("lifecycle_state", "")) in TERMINAL_STATES
            ),
            "workstreams_without_exact_bindings": sorted(workstreams_without_exact_bindings),
            "label_pair_count": label_pair_count,
            "unevaluated_label_pair_count": unevaluated_label_pair_count,
            "exact_context_bundle_count": exact_context_bundle_count,
            "repo_context_bundle_count": repo_context_bundle_count,
            "unassigned_bundle_count": len(bundles),
            "source_case_count": len(all_cases),
            "cases_truncated_count": hidden_case_count,
            "typed_relation_evidence_available": False,
        },
        "blockers": sorted(blockers, key=lambda row: (row["kind"], row["ref"])),
        "unknowns": unknowns,
        "source_refs": {name: descriptor["source_hash"] for name, descriptor in sources.items()},
    }


_STYLE = """
:root{color-scheme:dark;--bg:#08110f;--panel:#12211d;--line:#2b4a40;--text:#f5f7f4;--muted:#a9bbb5;--mint:#75e0b7;--amber:#ffd078}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 0,#183f34 0,transparent 34%),var(--bg);color:var(--text);font:15px/1.55 system-ui,sans-serif}.skip{position:absolute;left:-999px;top:8px;background:#fff;color:#000;padding:10px}.skip:focus{left:8px}.shell{width:min(1400px,94vw);margin:auto;padding:44px 0 80px}.eyebrow{text-transform:uppercase;letter-spacing:.13em;color:var(--mint);font-size:.72rem;font-weight:800}h1{font-size:clamp(2.5rem,6vw,5.5rem);line-height:.93;margin:.3rem 0 1rem}h2{margin-top:3rem}.muted{color:var(--muted);max-width:960px}.banner{border:2px solid var(--amber);border-radius:17px;padding:16px 18px;margin:24px 0;background:#2a2818}.stats,.cards{display:grid;gap:14px}.stats{grid-template-columns:repeat(6,1fr);margin:28px 0}.cards{grid-template-columns:repeat(3,1fr)}.card,.stat,.table-wrap,details{background:var(--panel);border:1px solid var(--line);border-radius:17px}.card,.stat{padding:18px}.stat strong{display:block;font-size:1.8rem}.stat span{color:var(--muted)}code{color:#b7ead7;overflow-wrap:anywhere}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}caption{text-align:left;padding:12px 14px;font-weight:700}th,td{padding:12px 14px;border-top:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted);font-size:.74rem;text-transform:uppercase}footer{margin-top:48px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted)}:focus-visible{outline:3px solid var(--amber);outline-offset:3px}@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.cards{grid-template-columns:1fr}}
""".strip()


def _csp() -> str:
    digest = base64.b64encode(hashlib.sha256(_STYLE.encode("utf-8")).digest()).decode("ascii")
    return (
        "default-src 'none'; "
        f"style-src 'sha256-{digest}'; "
        "img-src 'none'; connect-src 'none'; script-src 'none'; object-src 'none'; "
        "frame-src 'none'; base-uri 'none'; form-action 'none'"
    )


def portfolio_shaping_html(projection: dict[str, Any]) -> str:
    """Render an inert, script-free shaping review surface."""

    summary = projection["summary"]
    review_cards = (
        "".join(
            '<article class="card">'
            f'<div class="eyebrow">{escape(row["case_kind"].replace("_", " "))} ? {escape(row["evidence_tier"])}</div>'
            f"<h3>{escape(row['label'])}</h3><p>{escape(row['next_action'])}</p>"
            f"<code>{escape(row['case_id'])}</code></article>"
            for row in projection["review_queue"]
        )
        or '<article class="card"><h3>No added Today review</h3><p>The full inventory may still contain shaping cases.</p></article>'
    )
    case_rows = (
        "".join(
            "<tr>"
            f"<td>{escape(row['case_kind'])}</td><td>{escape(row['evidence_tier'])}</td>"
            f"<td>{escape(row['label'])}</td><td>{escape(row['disposition'])}</td>"
            f"<td>{escape(', '.join(choice['label'] for choice in row['choices']))}</td>"
            f"<td>{escape(row['decision']['state'])}</td>"
            f"<td>{escape(row['decision']['manual_action_state'])}</td>"
            f"<td><code>{escape(row['case_id'])}</code></td></tr>"
            for row in projection["cases"]
        )
        or '<tr><td colspan="8">No shaping case was generated. This is not automatically an all-clear.</td></tr>'
    )
    card_rows = (
        "".join(
            "<tr>"
            f"<td>{escape(row['label'])}</td><td>{escape(row['lifecycle_state'])}</td>"
            f"<td>{len(row['accepted_specific_resource_ids'])}</td><td>{len(row['case_ids'])}</td>"
            f"<td>{'yes' if row['missing_exact_scope'] else 'no'}</td></tr>"
            for row in projection["workstream_cards"]
        )
        or '<tr><td colspan="5">No eligible workstream card is visible.</td></tr>'
    )
    blocker_rows = (
        "".join(
            f"<tr><td>{escape(row['kind'])}</td><td><code>{escape(row['ref'])}</code></td><td>{escape(row['note'])}</td></tr>"
            for row in projection["blockers"]
        )
        or '<tr><td colspan="3">No shaping blocker reported.</td></tr>'
    )
    unknown_rows = (
        "".join(
            f"<tr><td>{escape(row['severity'])}</td><td>{escape(row['kind'])}</td>"
            f"<td><code>{escape(row['ref'])}</code></td><td>{escape(row['note'])}</td></tr>"
            for row in projection["unknowns"]
        )
        or '<tr><td colspan="4">No source unknown reported.</td></tr>'
    )
    source_rows = "".join(
        "<tr>"
        f"<td>{escape(name)}</td><td>{escape(row['status'])}</td>"
        f"<td>{escape(row['freshness'])}</td><td>{escape(row['schema_version'])}</td>"
        f"<td>{escape(', '.join(row['problems']))}</td></tr>"
        for name, row in projection["sources"].items()
    )
    complete = "yes" if summary["shaping_complete"] else "no"
    status = escape(projection["status"])
    classification = escape(projection["data_classification"])
    decision_projection = projection["decision_projection"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(_csp(), quote=True)}"><title>DAD Workstream Shaping</title><style>{_STYLE}</style></head>
<body><a class="skip" href="#main">Skip to main content</a><main id="main" class="shell"><div class="eyebrow">DAD ? Creative sprawl shaping</div>
<h1>Shape the sprawl. Keep the decision yours.</h1><p class="muted">Candidate split, rescope, duplicate-comparison, and recovery choices over one frozen Portfolio OS snapshot. Every menu is descriptive; this page has no active controls.</p>
<div class="banner"><strong>Status: {status}. Shaping complete: {complete}.</strong> Classification: {classification}. There are {summary["unknown_count"]} source unknowns and {summary["blocker_count"]} blockers. Until status is generated_candidate, every card is inventory-only and must not be treated as a decision or all-clear.</div>
<p class="muted">Decision source: {escape(decision_projection["source_status"])}. Pending manual actions: {decision_projection["pending_manual_action_count"]}. Stale decisions: {decision_projection["stale_count"]}.</p>
<p class="muted">No-cases is reported separately and never means the portfolio is organized.</p>
<section class="stats"><div class="stat"><strong>{summary["case_count"]}</strong><span>visible cases</span></div><div class="stat"><strong>{summary["hidden_case_count"]}</strong><span>hidden cases</span></div><div class="stat"><strong>{summary["split_case_count"]}</strong><span>split</span></div><div class="stat"><strong>{summary["rescope_case_count"]}</strong><span>rescope</span></div><div class="stat"><strong>{summary["possible_duplicate_case_count"]}</strong><span>possible duplicate</span></div><div class="stat"><strong>{summary["recovery_case_count"]}</strong><span>recovery</span></div></section>
<h2>Source readiness</h2><div class="table-wrap"><table><caption>Frozen source status and freshness.</caption><thead><tr><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Freshness</th><th scope="col">Schema</th><th scope="col">Problems</th></tr></thead><tbody>{source_rows}</tbody></table></div>
<h2>Today review</h2><section class="cards">{review_cards}</section>
<h2>Workstream scope</h2><div class="table-wrap"><table><caption>Exact accepted scope and shaping coverage.</caption><thead><tr><th scope="col">Workstream</th><th scope="col">State</th><th scope="col">Exact resources</th><th scope="col">Cases</th><th scope="col">Missing exact scope</th></tr></thead><tbody>{card_rows}</tbody></table></div>
<h2>Full shaping inventory</h2><details><summary>{summary["case_count"]} visible cases; {summary["hidden_case_count"]} hidden by the configured bound</summary><div class="table-wrap"><table><caption>Evidence-tiered cases. Similarity remains inspect-only.</caption><thead><tr><th scope="col">Kind</th><th scope="col">Tier</th><th scope="col">Subject</th><th scope="col">Disposition</th><th scope="col">Inert choices</th><th scope="col">Decision state</th><th scope="col">Manual state</th><th scope="col">Case ID</th></tr></thead><tbody>{case_rows}</tbody></table></div></details>
<h2>Blockers</h2><div class="table-wrap"><table><caption>Source, identity, and reconciliation blockers that prevent false confidence.</caption><thead><tr><th scope="col">Kind</th><th scope="col">Ref</th><th scope="col">Explanation</th></tr></thead><tbody>{blocker_rows}</tbody></table></div>
<h2>Unknowns</h2><div class="table-wrap"><table><caption>Incomplete source evidence retained as an explicit limit.</caption><thead><tr><th scope="col">Severity</th><th scope="col">Kind</th><th scope="col">Opaque ref</th><th scope="col">Explanation</th></tr></thead><tbody>{unknown_rows}</tbody></table></div>
<footer>Generated {escape(projection["generated_at"])}. Derived local report with no active controls.</footer></main></body></html>"""


_PATH_RE = _ABSOLUTE_PATH_RE
_FORBIDDEN_FIELD_PARTS = frozenset({"command", "apply", "accept", "dispatch", "execute"})


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    rows = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(_walk(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk(child, (*path, str(index))))
    return rows


def portfolio_shaping_semantic_problems(projection: dict[str, Any]) -> list[str]:
    """Validate cross-field authority, identity, and false-green invariants."""

    problems: set[str] = set()
    sources = projection.get("sources", {})
    source_refs = projection.get("source_refs", {})
    for name in ("workstreams", "cockpit", "reconciliation"):
        descriptor = sources.get(name, {}) if isinstance(sources, dict) else {}
        if source_refs.get(name) != descriptor.get("source_hash"):
            problems.add(f"source_hash_reference_mismatch:{name}")

    coupling = projection.get("source_coupling", {})
    expected_snapshot_digest = _shaping_source_snapshot_digest(sources, coupling)
    if projection.get("source_snapshot_digest") != expected_snapshot_digest:
        problems.add("source_snapshot_digest_mismatch")
    decision_projection = projection.get("decision_projection", {})
    if not isinstance(decision_projection, dict):
        problems.add("decision_projection_not_object")
        decision_projection = {}
    if decision_projection.get("source_snapshot_digest") != expected_snapshot_digest:
        problems.add("decision_snapshot_digest_mismatch")
    if decision_projection.get("source_status") not in {"observed", "invalid", "unavailable"}:
        problems.add("decision_source_status_invalid")
    if decision_projection.get("problems") != sorted(
        set(decision_projection.get("problems", []))
    ):
        problems.add("decision_problems_not_canonical")
    expected_links = {
        "workstreams_to_cockpit": (
            sources.get("workstreams", {}).get("source_hash", "")
            if isinstance(sources, dict)
            else ""
        ),
        "cockpit_to_reconciliation": (
            sources.get("cockpit", {}).get("source_hash", "") if isinstance(sources, dict) else ""
        ),
    }
    coupling_ready = True
    blocker_kinds = {
        str(row.get("kind", "")) for row in projection.get("blockers", []) if isinstance(row, dict)
    }
    for link_name, actual_hash in expected_links.items():
        link = coupling.get(link_name, {}) if isinstance(coupling, dict) else {}
        expected_match = bool(
            actual_hash
            and actual_hash == str(link.get("claimed_source_hash", ""))
            and link.get("actual_source_hash") == actual_hash
        )
        if link.get("matches") is not expected_match:
            problems.add(f"source_coupling_mismatch:{link_name}")
        coupling_ready = coupling_ready and expected_match
        blocker_kind = (
            "workstream_cockpit_hash_mismatch"
            if link_name == "workstreams_to_cockpit"
            else "cockpit_reconciliation_hash_mismatch"
        )
        if (blocker_kind in blocker_kinds) is expected_match:
            problems.add(f"source_coupling_blocker_mismatch:{link_name}")

    coverage = projection.get("coverage", {})
    eligible_ids = set(coverage.get("eligible_workstream_ids", []))
    resource_ids = set(coverage.get("source_resource_ids", []))
    attention_ids_inventory = set(coverage.get("source_attention_ids", []))
    bundle_ids = set(coverage.get("source_bundle_ids", []))
    cases = [row for row in projection.get("cases", []) if isinstance(row, dict)]
    case_by_id: dict[str, dict[str, Any]] = {}
    for row in cases:
        case_id = str(row.get("case_id", ""))
        if case_id in case_by_id:
            problems.add("duplicate_case_id")
        case_by_id[case_id] = row
        for key in (
            "subject_workstream_ids",
            "subject_resource_ids",
            "source_attention_ids",
            "source_bundle_ids",
            "signals",
            "counterevidence",
        ):
            values = row.get(key, [])
            if values != sorted(set(str(value) for value in values)):
                problems.add(f"case_collection_not_canonical:{key}")
        expected_case_id = stable_id(
            METHOD_ID,
            str(row.get("case_kind", "")),
            "|".join(row.get("subject_workstream_ids", [])),
            "|".join(row.get("subject_resource_ids", [])),
            "|".join(row.get("source_attention_ids", [])),
            "|".join(row.get("source_bundle_ids", [])),
        )
        if case_id != expected_case_id:
            problems.add("case_identity_mismatch")
        tier = str(row.get("evidence_tier", ""))
        contract = _TIER_CONTRACTS.get(tier)
        if contract is None:
            problems.add("unknown_evidence_tier")
            profile = ""
        else:
            expected_kind, expected_disposition, profile = contract
            if row.get("case_kind") != expected_kind:
                problems.add("tier_case_kind_mismatch")
            if row.get("disposition") != expected_disposition:
                problems.add("tier_disposition_mismatch")
            if row.get("label") != _CASE_LABELS[tier]:
                problems.add("case_label_mismatch")
        choices = row.get("choices", [])
        choice_kinds = [
            str(choice.get("choice_kind", "")) for choice in choices if isinstance(choice, dict)
        ]
        expected_choices = [_choice(case_id, *spec) for spec in _CHOICE_SPECS.get(profile, ())]
        if choices != expected_choices:
            problems.add("case_choice_vocabulary_mismatch")
        for choice in choices:
            if choice.get("choice_id") != stable_id(case_id, str(choice.get("choice_kind", ""))):
                problems.add("choice_identity_mismatch")
            if (
                choice.get("execution_available") is not False
                or choice.get("requires_human_decision") is not True
            ):
                problems.add("choice_authority_mismatch")
        if not set(row.get("subject_workstream_ids", [])) <= eligible_ids:
            problems.add("case_workstream_subject_missing")
        if not set(row.get("subject_resource_ids", [])) <= resource_ids:
            problems.add("case_resource_subject_missing")
        if not set(row.get("source_attention_ids", [])) <= attention_ids_inventory:
            problems.add("case_attention_source_missing")
        if not set(row.get("source_bundle_ids", [])) <= bundle_ids:
            problems.add("case_bundle_source_missing")
        material = {
            key: row.get(key)
            for key in (
                "case_kind",
                "evidence_tier",
                "disposition",
                "subject_workstream_ids",
                "subject_resource_ids",
                "source_attention_ids",
                "source_bundle_ids",
                "signals",
                "counterevidence",
                "evidence_summary",
            )
        }
        material["choice_kinds"] = choice_kinds
        if row.get("revision_id") != stable_id(case_id, _canonical_hash(material)):
            problems.add("case_revision_identity_mismatch")

        decision = row.get("decision", {})
        if not isinstance(decision, dict):
            problems.add("case_decision_not_object")
            decision = {}
        state = str(decision.get("state", ""))
        manual_state = str(decision.get("manual_action_state", ""))
        if state not in {*_DECISION_STATES, "none"}:
            problems.add("case_decision_state_invalid")
        if manual_state not in _MANUAL_ACTION_STATES:
            problems.add("case_manual_action_state_invalid")
        if state == "none" and decision != _empty_decision_annotation():
            problems.add("empty_case_decision_mismatch")
        if state == "retracted" and manual_state != "none":
            problems.add("retracted_decision_action_mismatch")
        if state in {"active", "stale"}:
            choice_map = {
                str(choice.get("choice_id", "")): str(choice.get("choice_kind", ""))
                for choice in choices
                if isinstance(choice, dict)
            }
            if (
                not decision.get("decision_id")
                or decision.get("choice_id") not in choice_map
                or choice_map.get(decision.get("choice_id")) != decision.get("choice_kind")
            ):
                problems.add("case_decision_choice_mismatch")
        if manual_state in _RESULT_STATES and not decision.get("result_ref"):
            problems.add("case_decision_result_ref_missing")
        if decision.get("choice_kind") == "defer" and state == "active" and manual_state not in {
            "not_required",
            *_RESULT_STATES,
        }:
            problems.add("defer_manual_action_mismatch")

        evidence = row.get("evidence_summary", {})
        workstream_count = len(row.get("subject_workstream_ids", []))
        resource_count = len(row.get("subject_resource_ids", []))
        if tier == "PD0_shared_exact_specific_resource" and not (
            workstream_count == 2
            and resource_count >= 1
            and evidence.get("shared_specific_resource_count", 0) >= 1
        ):
            problems.add("pd0_evidence_predicate_failed")
        elif tier == "PD1_reciprocal_exact_pair_split_between_workstreams" and not (
            workstream_count == 2 and resource_count >= 2
        ):
            problems.add("pd1_evidence_predicate_failed")
        elif tier == "PD2_similarity_only" and not (
            workstream_count == 2
            and resource_count == 0
            and evidence.get("shared_token_count", 0) >= 3
            and row.get("disposition") == "inspect_only"
        ):
            problems.add("pd2_evidence_predicate_failed")
        elif tier == "SP0_disconnected_exact_owned_components" and not (
            workstream_count == 1
            and resource_count >= 2
            and evidence.get("exact_component_count", 0) >= 2
        ):
            problems.add("sp0_evidence_predicate_failed")
        elif tier == "RS0_exact_contextual_unassigned_bundle" and not (
            workstream_count == 1
            and row.get("source_bundle_ids")
            and evidence.get("context_basis") == "exact_attention_assignment"
        ):
            problems.add("rs0_evidence_predicate_failed")
        elif tier == "RS1_repo_context_only" and not (
            workstream_count == 1
            and row.get("source_bundle_ids")
            and evidence.get("context_basis") == "repo_context_only"
            and row.get("disposition") == "inspect_only"
        ):
            problems.add("rs1_evidence_predicate_failed")
        elif tier == "RC0_integrity_unknown_attention" and not (
            row.get("source_attention_ids")
            and "integrity_unknown" in evidence.get("attention_bands", [])
        ):
            problems.add("rc0_evidence_predicate_failed")
        elif tier == "RC1_dirty_exact_attention" and not (
            row.get("source_attention_ids")
            and resource_count >= 1
            and "dirty_exact_attention" in row.get("signals", [])
        ):
            problems.add("rc1_evidence_predicate_failed")
        elif tier == "RC2_existing_workstream_trigger" and not (
            workstream_count == 1
            and row.get("source_attention_ids")
            and evidence.get("trigger_kinds")
        ):
            problems.add("rc2_evidence_predicate_failed")
        elif tier == "RC3_unassigned_observed_bundle" and not (
            workstream_count == 0 and row.get("source_bundle_ids")
        ):
            problems.add("rc3_evidence_predicate_failed")

    cards = [row for row in projection.get("workstream_cards", []) if isinstance(row, dict)]
    seen_card_workstreams: set[str] = set()
    for card in cards:
        workstream_id = str(card.get("workstream_id", ""))
        if workstream_id in seen_card_workstreams:
            problems.add("duplicate_workstream_card")
        seen_card_workstreams.add(workstream_id)
        if card.get("card_id") != stable_id(METHOD_ID, "workstream-card", workstream_id):
            problems.add("workstream_card_identity_mismatch")
        if any(case_id not in case_by_id for case_id in card.get("case_ids", [])):
            problems.add("workstream_card_case_missing")
        expected_case_ids = [
            row["case_id"]
            for row in cases
            if workstream_id in row.get("subject_workstream_ids", [])
        ]
        if card.get("case_ids") != expected_case_ids:
            problems.add("workstream_card_case_reciprocity_mismatch")
        if card.get("missing_exact_scope") != (not card.get("accepted_specific_resource_ids")):
            problems.add("workstream_card_scope_flag_mismatch")
        if card.get("label") != "Workstream":
            problems.add("workstream_card_label_mismatch")
        if not set(card.get("accepted_specific_resource_ids", [])) <= resource_ids:
            problems.add("workstream_card_resource_missing")
    if seen_card_workstreams != eligible_ids:
        problems.add("workstream_card_coverage_mismatch")

    today_ids = coverage.get("today_attention_ids", [])
    if not set(today_ids) <= attention_ids_inventory:
        problems.add("today_attention_source_missing")
    reviews = [row for row in projection.get("review_queue", []) if isinstance(row, dict)]
    if len(reviews) > 3 or len(reviews) > int(
        projection.get("methodology", {}).get("review_limit", 0)
    ):
        problems.add("review_queue_limit_exceeded")
    seen_review_ids: set[str] = set()
    for review in reviews:
        review_id = str(review.get("review_id", ""))
        if review_id in seen_review_ids:
            problems.add("duplicate_review_id")
        seen_review_ids.add(review_id)
        case_id = str(review.get("case_id", ""))
        attention_ids = review.get("attention_ids", [])
        if case_id not in case_by_id:
            problems.add("review_case_missing")
            continue
        if case_by_id[case_id].get("decision", {}).get("state") in {"active", "stale"}:
            problems.add("decided_case_in_review_queue")
        if not attention_ids or not set(attention_ids) <= set(today_ids):
            problems.add("review_not_subset_of_today")
        if not set(attention_ids) <= set(case_by_id[case_id].get("source_attention_ids", [])):
            problems.add("review_attention_not_in_case")
        if review.get("review_id") != stable_id(METHOD_ID, "review", case_id, *attention_ids):
            problems.add("review_identity_mismatch")
        case = case_by_id[case_id]
        if (
            review.get("case_kind") != case.get("case_kind")
            or review.get("evidence_tier") != case.get("evidence_tier")
            or review.get("label") != case.get("label")
            or review.get("next_action")
            != "Review the inert choices; any later work requires a separate human gate."
        ):
            problems.add("review_case_metadata_mismatch")

    visible_decisions = [
        row.get("decision", {})
        for row in cases
        if isinstance(row.get("decision"), dict) and row["decision"].get("state") != "none"
    ]
    for key, expected in {
        "active_count": sum(row.get("state") == "active" for row in visible_decisions),
        "retracted_count": sum(row.get("state") == "retracted" for row in visible_decisions),
        "stale_count": sum(row.get("state") == "stale" for row in visible_decisions),
        "pending_manual_action_count": sum(
            row.get("manual_action_state") == "pending" for row in visible_decisions
        ),
        "verified_result_count": sum(
            row.get("manual_action_state") == "verified" for row in visible_decisions
        ),
        "failed_result_count": sum(
            row.get("manual_action_state") == "failed" for row in visible_decisions
        ),
        "aborted_result_count": sum(
            row.get("manual_action_state") == "aborted" for row in visible_decisions
        ),
    }.items():
        if int(decision_projection.get(key, 0) or 0) < expected:
            problems.add(f"decision_projection_count_too_small:{key}")
    if decision_projection.get("source_status") == "invalid" and not any(
        row.get("kind") == "decision_projection_invalid"
        for row in projection.get("blockers", [])
        if isinstance(row, dict)
    ):
        problems.add("decision_projection_blocker_missing")
    if decision_projection.get("source_status") == "observed":
        counted_decisions = sum(
            int(decision_projection.get(key, 0) or 0)
            for key in ("active_count", "retracted_count", "stale_count")
        ) + sum(
            int(decision_projection.get(key, 0) or 0)
            for key in ("historical_decision_count", "unmatched_decision_count")
        )
        if decision_projection.get("decision_count") != counted_decisions:
            problems.add("decision_projection_count_mismatch")

    summary = projection.get("summary", {})
    counts = Counter(row.get("case_kind") for row in cases)
    expected_summary = {
        "case_count": len(cases),
        "split_case_count": counts["split"],
        "rescope_case_count": counts["rescope"],
        "possible_duplicate_case_count": counts["possible_duplicate"],
        "recovery_case_count": counts["recovery"],
        "review_count": len(reviews),
        "blocker_count": len(projection.get("blockers", [])),
        "unknown_count": len(projection.get("unknowns", [])),
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            problems.add(f"summary_mismatch:{key}")
    if summary.get("hidden_case_count") != coverage.get("cases_truncated_count"):
        problems.add("hidden_case_count_mismatch")
    if coverage.get("source_case_count") != len(cases) + int(summary.get("hidden_case_count", 0)):
        problems.add("source_case_count_mismatch")
    if summary.get("no_cases_generated") != (coverage.get("source_case_count") == 0):
        problems.add("no_cases_generated_mismatch")
    sources_ready = len(sources) == 3 and all(
        isinstance(descriptor, dict)
        and descriptor.get("status") == "observed"
        and descriptor.get("freshness") == "current"
        for descriptor in sources.values()
    )
    expected_status = (
        "blocked_candidate"
        if not sources_ready or not coupling_ready
        else "partial_candidate"
        if projection.get("blockers") or projection.get("unknowns")
        else "generated_candidate"
    )
    if projection.get("status") != expected_status:
        problems.add("projection_status_mismatch")
    expected_complete = bool(
        sources_ready
        and coupling_ready
        and coupling.get("reconciliation_fully_reconciled") is True
        and not projection.get("blockers")
        and not projection.get("unknowns")
        and summary.get("eligible_workstream_count", 0) > 0
        and coverage.get("source_case_count") == 0
        and coverage.get("unassigned_bundle_count") == 0
        and not coverage.get("workstreams_without_exact_bindings")
    )
    if summary.get("shaping_complete") is not expected_complete:
        problems.add("shaping_complete_mismatch")
    expected_intake = bool(
        sources_ready and coupling_ready and summary.get("workstream_count") == 0
    )
    if summary.get("intake_needed") is not expected_intake:
        problems.add("intake_needed_mismatch")
    if (
        projection.get("execution_authorized") is not False
        or projection.get("mutations_performed") is not False
        or projection.get("decision_recorded") is not False
        or projection.get("source_authority_mutated") is not False
        or projection.get("publication_scope") != "derived_reports_only"
        or projection.get("authority_boundary") != AUTHORITY_BOUNDARY
    ):
        problems.add("projection_authority_mismatch")
    if projection.get("methodology", {}).get("age_creates_case") is not False:
        problems.add("age_policy_mismatch")
    for path, value in _walk(projection):
        if path and path[-1].casefold() in _FORBIDDEN_FIELD_PARTS:
            problems.add("forbidden_action_field")
        if isinstance(value, str) and _PATH_RE.search(value):
            problems.add("raw_path_exposed")
    return sorted(problems)


def write_portfolio_shaping_outputs(
    hub_root: Path,
    projection: dict[str, Any],
    *,
    workstream_state: dict[str, Any],
    cockpit: dict[str, Any],
    reconciliation: dict[str, Any],
    decisions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate against frozen sources and publish HTML, then the JSON cursor."""

    problems = schema_validation_problems(projection, hub_root, "portfolio_workstream_shaping")
    if problems:
        raise ValueError("Invalid portfolio shaping projection: " + "; ".join(problems))
    semantic_problems = portfolio_shaping_semantic_problems(projection)
    if semantic_problems:
        raise ValueError("Invalid portfolio shaping semantics: " + "; ".join(semantic_problems))
    generated_at = _parse_datetime(projection.get("generated_at"))
    if generated_at is None:
        raise ValueError("Invalid portfolio shaping projection: generated_at")
    methodology = projection["methodology"]
    expected = build_portfolio_shaping(
        workstream_state,
        cockpit,
        reconciliation,
        decisions=decisions,
        now=generated_at,
        settings=ShapingSettings(
            case_limit=int(methodology["case_limit"]),
            review_limit=int(methodology["review_limit"]),
            fresh_after_hours=int(methodology["fresh_after_hours"]),
            future_tolerance_hours=int(methodology["future_tolerance_hours"]),
        ),
        schema_root=hub_root,
    )
    if projection != expected:
        raise ValueError("Invalid portfolio shaping semantics: projection_source_rebuild_mismatch")
    base = data_path(hub_root, "central_reports") / "portfolio_os"
    json_path = base / "shaping.json"
    html_path = base / "shaping.html"
    atomic_write_text(html_path, portfolio_shaping_html(projection))
    atomic_write_text(json_path, json_dumps(projection, pretty=True) + "\n")
    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "status": projection["status"],
        "summary": projection["summary"],
        "review_queue": projection["review_queue"],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "generated_at": projection["generated_at"],
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "METHOD_ID",
    "SCHEMA_VERSION",
    "ShapingSettings",
    "build_portfolio_shaping",
    "portfolio_shaping_html",
    "portfolio_shaping_semantic_problems",
    "write_portfolio_shaping_outputs",
]
