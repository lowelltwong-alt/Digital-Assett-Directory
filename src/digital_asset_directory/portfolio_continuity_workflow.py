"""Manual continuity workflow and evidence-gated lifecycle overlays.

The durable lifecycle remains the implemented Portfolio OS state machine.
Readiness, focus, blocking, validation, delivery, interruption, and archive
readiness are orthogonal projections so evidence cannot silently rewrite
history or grant authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from .ids import stable_id
from .portfolio_attention import LIFECYCLE_STATES


SCHEMA_VERSION = "dad.portfolio_continuity_workflow.v1"
AUTHORITY_BOUNDARY = (
    "Continuity workflow outputs are read-only candidate evidence. They do not "
    "transition lifecycle, grant a lease, create or remove a worktree, archive "
    "a task, delete a branch, notify a person, or establish source authority."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_observation_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _task_snapshot_fresh(
    task_observation: dict[str, Any], *, now: datetime
) -> bool:
    observed = _parse_observation_time(task_observation.get("observed_at", ""))
    valid_until = _parse_observation_time(task_observation.get("snapshot_valid_until", ""))
    if observed is None or valid_until is None:
        return False
    return (
        task_observation.get("snapshot_current") is True
        and bool(str(task_observation.get("snapshot_receipt_ref", "")))
        and observed <= now <= valid_until
        and timedelta(0) <= valid_until - observed <= timedelta(hours=24)
    )


def _active_lease(execution_control: dict[str, Any] | None, workstream_id: str) -> bool:
    if not execution_control or not workstream_id:
        return False
    return any(
        str(row.get("workstream_id", "")) == workstream_id
        and str(row.get("status", "")) == "active"
        for row in execution_control.get("leases", [])
    )


def project_continuity_state(
    *,
    plan: dict[str, Any] | None,
    workstream: dict[str, Any] | None,
    execution_control: dict[str, Any] | None = None,
    focus_window_active: bool = False,
) -> dict[str, Any]:
    """Join lifecycle and overlay evidence without collapsing their meanings."""

    plan = plan or {}
    workstream = workstream or {}
    lifecycle = str(workstream.get("lifecycle_state", ""))
    lifecycle_known = lifecycle in LIFECYCLE_STATES
    implementation = str(plan.get("implementation_state", "unknown"))
    next_action = str(
        workstream.get("next_action", "") or plan.get("smallest_next_action", "")
    )
    expected_acceptance = list(plan.get("acceptance_evidence", []))
    workstream_id = str(workstream.get("workstream_id", ""))
    lease_active = _active_lease(execution_control, workstream_id)
    capsule = workstream.get("capsule", {}) if isinstance(workstream.get("capsule"), dict) else {}
    blocker = str(capsule.get("blocker", ""))

    if next_action and expected_acceptance:
        readiness = "leased" if lease_active else "ready_for_lease_request"
    else:
        readiness = "not_ready"

    if implementation == "blocked" or blocker:
        blocking = "blocked"
    elif lifecycle == "paused":
        blocking = "waiting"
    elif lifecycle_known:
        blocking = "clear"
    else:
        blocking = "unknown"

    if implementation == "verified_complete":
        validation = "verified"
    elif implementation in {"validation_pending", "implemented_candidate"}:
        validation = "validation_pending"
    elif implementation in {"unstarted", "partial", "blocked", "drifted", "superseded"}:
        validation = "not_ready"
    else:
        validation = "unknown"

    completion_blockers: list[str] = []
    if implementation == "verified_complete":
        if not expected_acceptance:
            completion_blockers.append("acceptance_evidence_missing")
        if not str(plan.get("independent_check_ref", "")):
            completion_blockers.append("independent_check_missing")
        producer = str(plan.get("producer_ref", ""))
        checker = str(plan.get("independent_checker_ref", ""))
        if not producer or not checker:
            completion_blockers.append("producer_or_checker_missing")
        elif producer == checker:
            completion_blockers.append("checker_not_independent")
        if not str(plan.get("validated_plan_revision_id", "")):
            completion_blockers.append("validated_plan_revision_missing")
    delivery = (
        "delivered"
        if implementation == "verified_complete" and not completion_blockers
        else "not_delivered"
    )

    result = {
        "schema_version": "dad.portfolio_continuity_state.v1",
        "plan_id": str(plan.get("plan_id", "")),
        "plan_revision_id": str(plan.get("revision_id", "")),
        "workstream_id": workstream_id,
        "durable_lifecycle": lifecycle if lifecycle_known else None,
        "lifecycle_known": lifecycle_known,
        "overlays": {
            "plan_lifecycle": str(plan.get("lifecycle", "")) or "unknown",
            "implementation": implementation,
            "readiness": readiness,
            "focus": "focus-window" if focus_window_active and lease_active else "outside-focus-window",
            "blocking": blocking,
            "validation": validation,
            "delivery": delivery,
        },
        "next_action": next_action,
        "completion_blockers": sorted(set(completion_blockers)),
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    result["state_fingerprint"] = _digest(result)
    return result


def build_resume_packet(
    *,
    plan: dict[str, Any],
    workstream: dict[str, Any] | None = None,
    execution_control: dict[str, Any] | None = None,
    recovery_bundle: dict[str, Any] | None = None,
    activity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = project_continuity_state(
        plan=plan, workstream=workstream, execution_control=execution_control
    )
    workstream = workstream or {}
    capsule = workstream.get("capsule", {}) if isinstance(workstream.get("capsule"), dict) else {}
    recovery_bundle = recovery_bundle or {}
    activity = activity or {}
    unknowns = list(state["completion_blockers"])
    if recovery_bundle and not recovery_bundle.get("snapshot_current"):
        unknowns.append("recovery_snapshot_stale")
    packet = {
        "schema_version": "dad.portfolio_resume_packet.v1",
        "created_at": _now(),
        "plan_id": str(plan.get("plan_id", "")),
        "plan_revision_id": str(plan.get("revision_id", "")),
        "workstream_id": str(workstream.get("workstream_id", "")),
        "last_verified_intent": str(plan.get("outcome", "")),
        "durable_lifecycle": state["durable_lifecycle"],
        "overlays": state["overlays"],
        "last_material_activity_at": str(activity.get("last_material_activity_at", "")),
        "session_count": int(activity.get("session_count", 0)),
        "interruption_count": int(activity.get("interruption_count", 0)),
        "last_check": str(capsule.get("last_check", "")),
        "next_bounded_action": state["next_action"],
        "blocker": str(capsule.get("blocker", "")),
        "recovery_classification": str(recovery_bundle.get("classification", "")),
        "recovery_snapshot_current": bool(recovery_bundle.get("snapshot_current", False)),
        "unknowns": sorted(set(unknowns)),
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    packet["packet_id"] = stable_id("portfolio-resume-packet", _digest(packet))
    return packet


def assess_closeout(
    *,
    plan: dict[str, Any],
    workstream: dict[str, Any] | None = None,
    execution_control: dict[str, Any] | None = None,
    recovery_bundle: dict[str, Any] | None = None,
    task_observation: dict[str, Any] | None = None,
    preserved_handoff_ref: str = "",
    branch_pr_disposition_ref: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assess task archive and worktree removal as separate human decisions."""

    state = project_continuity_state(
        plan=plan, workstream=workstream, execution_control=execution_control
    )
    recovery_bundle = recovery_bundle or {}
    task_observation = task_observation or {}
    observed_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    preserved = bool(preserved_handoff_ref)
    plan_terminal = (
        state["overlays"]["delivery"] == "delivered"
        or str(plan.get("lifecycle", "")) in {"superseded", "withdrawn"}
    )
    common: list[str] = []
    if not plan_terminal:
        common.append("plan_not_evidence_terminal")
    if not preserved:
        common.append("preserved_handoff_missing")

    task_blockers = list(common)
    if not str(task_observation.get("task_id", "")):
        task_blockers.append("task_observation_missing")
    observed_at = task_observation.get("observed_at", "")
    if not observed_at:
        task_blockers.append("task_observation_time_missing")
    elif _parse_observation_time(observed_at) is None:
        task_blockers.append("task_observation_time_invalid_or_future")
    if not _task_snapshot_fresh(task_observation, now=observed_now):
        task_blockers.append("task_snapshot_freshness_unverified")

    worktree_blockers = list(common)
    if not recovery_bundle:
        worktree_blockers.append("recovery_bundle_missing")
    else:
        if not recovery_bundle.get("snapshot_current"):
            worktree_blockers.append("worktree_snapshot_stale_or_unknown")
        if str(recovery_bundle.get("classification", "")) not in {
            "contained_in_main",
            "patch_equivalent",
        }:
            worktree_blockers.append("worktree_unique_value_not_proven_preserved")
        if not recovery_bundle.get("completion_supported") and state["overlays"]["delivery"] == "delivered":
            worktree_blockers.append("completion_not_supported_by_recovery")
    if not branch_pr_disposition_ref:
        worktree_blockers.append("branch_pr_disposition_missing")

    result = {
        "schema_version": "dad.portfolio_closeout_assessment.v1",
        "assessed_at": observed_now.isoformat(),
        "plan_id": str(plan.get("plan_id", "")),
        "plan_revision_id": str(plan.get("revision_id", "")),
        "task_archive": {
            "ready_for_human_decision": not task_blockers,
            "blockers": sorted(set(task_blockers)),
            "requires_exact_human_approval": True,
            "action_executed": False,
        },
        "worktree_remove": {
            "ready_for_human_decision": not worktree_blockers,
            "blockers": sorted(set(worktree_blockers)),
            "requires_exact_human_approval": True,
            "action_executed": False,
        },
        "branch_delete": {
            "ready_for_human_decision": False,
            "blockers": ["separate_branch_delete_review_required"],
            "requires_exact_human_approval": True,
            "action_executed": False,
        },
        "preserved_handoff_ref": preserved_handoff_ref,
        "branch_pr_disposition_ref": branch_pr_disposition_ref,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    result["assessment_id"] = stable_id("portfolio-closeout-assessment", _digest(result))
    return result


def recommend_worktree(
    *,
    workstream: dict[str, Any],
    repository_id: str,
    existing_bindings: list[dict[str, Any]] | None = None,
    material_multi_session: bool,
    isolation_useful: bool,
) -> dict[str, Any]:
    bindings = existing_bindings or []
    has_worktree = any(
        str(row.get("binding_kind", "")) == "worktree"
        and str(row.get("assertion_status", "")) == "accepted"
        for row in bindings
    )
    blockers: list[str] = []
    if str(workstream.get("lifecycle_state", "")) == "proposed":
        blockers.append("workstream_not_promoted")
    if not repository_id:
        blockers.append("repository_unknown")
    if has_worktree:
        blockers.append("accepted_worktree_already_bound")
    if not material_multi_session:
        blockers.append("work_not_material_multi_session")
    if not isolation_useful:
        blockers.append("isolation_value_not_evidenced")
    return {
        "schema_version": "dad.portfolio_worktree_recommendation.v1",
        "workstream_id": str(workstream.get("workstream_id", "")),
        "repository_id": repository_id,
        "recommend_open_worktree": not blockers,
        "blockers": sorted(set(blockers)),
        "requires_exact_human_approval": True,
        "action_executed": False,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_manual_workflow_status(
    *,
    plan: dict[str, Any],
    roadmap: dict[str, Any] | None = None,
    workstream: dict[str, Any] | None = None,
    execution_control: dict[str, Any] | None = None,
    recovery_bundle: dict[str, Any] | None = None,
    task_observation: dict[str, Any] | None = None,
    activity: dict[str, Any] | None = None,
    preserved_handoff_ref: str = "",
    branch_pr_disposition_ref: str = "",
) -> dict[str, Any]:
    """Return capture -> resume -> acceptance -> archive-assessment truth."""

    resume = build_resume_packet(
        plan=plan,
        workstream=workstream,
        execution_control=execution_control,
        recovery_bundle=recovery_bundle,
        activity=activity,
    )
    closeout = assess_closeout(
        plan=plan,
        workstream=workstream,
        execution_control=execution_control,
        recovery_bundle=recovery_bundle,
        task_observation=task_observation,
        preserved_handoff_ref=preserved_handoff_ref,
        branch_pr_disposition_ref=branch_pr_disposition_ref,
    )
    roadmap = roadmap or {"item_count": 0, "accepted_count": 0, "remaining_count": 0}
    stages = {
        "checkpoint": bool(plan.get("plan_id")),
        "plan_revision": bool(plan.get("revision_id")),
        "resume": bool(resume.get("next_bounded_action") or resume.get("last_verified_intent")),
        "acceptance": str(plan.get("implementation_state", "")) == "verified_complete",
        "archive_assessment": True,
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "plan_id": str(plan.get("plan_id", "")),
        "plan_revision_id": str(plan.get("revision_id", "")),
        "stages": stages,
        "roadmap": {
            "item_count": int(roadmap.get("item_count", 0)),
            "accepted_count": int(roadmap.get("accepted_count", 0)),
            "remaining_count": int(roadmap.get("remaining_count", 0)),
        },
        "resume_packet": resume,
        "closeout_assessment": closeout,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    result["workflow_fingerprint"] = _digest(result)
    return result


__all__ = [
    "AUTHORITY_BOUNDARY",
    "SCHEMA_VERSION",
    "assess_closeout",
    "build_manual_workflow_status",
    "build_resume_packet",
    "project_continuity_state",
    "recommend_worktree",
]
