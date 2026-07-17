"""Dormant progressive-attention readiness and preview packets.

This module renders what later stages *would* show.  It never records approval,
activates a stage, schedules work, sends a notification, or mutates a task.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .portfolio_weekly_digest import build_weekly_digest
from .portfolio_continuity_stage_activation import fold_stage_activation


AUTHORITY_BOUNDARY = (
    "Progressive attention output is a read-only candidate preview. It cannot "
    "approve or activate a stage, schedule or send a summary, interrupt a user, "
    "archive a task, remove a worktree, mutate Git, or authorize execution."
)
STAGE_IDS = (
    "manual",
    "supervised_silent_shadow",
    "session_start_summary",
    "weekly_changed_only_digest",
    "breakpoint_prompts",
)
MAX_WEEKLY_FINGERPRINT_HISTORY = 1000


def _session_items(queues: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, rows in (
        ("interrupted_resume", queues.get("interrupted_resume", [])),
        ("next_actions", queues.get("next_actions", [])),
    ):
        for row in rows:
            plan_id = str(row.get("plan_id", ""))
            if not plan_id or plan_id in seen:
                continue
            seen.add(plan_id)
            items.append(
                {
                    "plan_id": plan_id,
                    "workstream_id": str(row.get("workstream_id", "")),
                    "next_action": str(row.get("next_action", "")),
                    "reason_codes": list(row.get("reason_codes", [])),
                    "source_queue": source,
                }
            )
            if len(items) == 3:
                return items
    return items


def build_progressive_attention_readiness(
    projection: Mapping[str, Any],
    *,
    activation_state: Mapping[str, Any] | None = None,
    stage_approvals: Iterable[Mapping[str, Any]] | None = None,
    adapter_interface_digest: str = "",
    stage_evaluated_at: str | None = None,
    previous_weekly_fingerprints: Iterable[str] = (),
) -> dict[str, Any]:
    """Build stage gates plus non-deliverable session/digest/prompt previews."""

    activation = activation_state or {}
    previous_fingerprints = list(previous_weekly_fingerprints)
    trial_status = str(activation.get("status", "inactive_shadow"))
    trial_eligible = trial_status == "eligible_for_human_activation"
    stages = [
        {
            "stage_id": "manual",
            "order": 1,
            "status": "available",
            "gate_failures": [],
            "separate_human_approval_required": False,
        },
        {
            "stage_id": "supervised_silent_shadow",
            "order": 2,
            "status": trial_status,
            "gate_failures": list(activation.get("gate_failures", [])),
            "separate_human_approval_required": True,
        },
        {
            "stage_id": "session_start_summary",
            "order": 3,
            "status": (
                "separate_human_approval_required"
                if trial_eligible
                else "blocked_by_supervised_trial"
            ),
            "gate_failures": [] if trial_eligible else ["supervised_trial_not_eligible"],
            "separate_human_approval_required": True,
        },
        {
            "stage_id": "weekly_changed_only_digest",
            "order": 4,
            "status": "blocked_by_session_summary_activation",
            "gate_failures": ["session_start_summary_not_separately_activated"],
            "separate_human_approval_required": True,
        },
        {
            "stage_id": "breakpoint_prompts",
            "order": 5,
            "status": "blocked_by_weekly_digest_activation",
            "gate_failures": ["weekly_changed_only_digest_not_separately_activated"],
            "separate_human_approval_required": True,
        },
    ]
    for stage in stages:
        stage.update(
            {
                "activation_authorized": (
                    stage["stage_id"] == "manual"
                    or (
                        stage["stage_id"] == "supervised_silent_shadow"
                        and trial_eligible
                    )
                ),
                "approval_event_id": "",
                "valid_until": "",
                "rollback_criteria": [],
                "kill_criteria": [],
            }
        )
    stage_activation_state_digest = ""
    if stage_approvals is not None:
        if activation_state is None or not adapter_interface_digest:
            raise ValueError(
                "stage approvals require activation_state and adapter_interface_digest"
            )
        stage_activation_state = fold_stage_activation(
            list(stage_approvals),
            activation_state=activation_state,
            adapter_interface_digest=adapter_interface_digest,
            evaluated_at=stage_evaluated_at,
        )
        stage_activation_state_digest = str(stage_activation_state["state_digest"])
        activated_by_id = {
            str(row["stage_id"]): row for row in stage_activation_state["stages"]
        }
        for stage in stages:
            activated = activated_by_id[str(stage["stage_id"])]
            stage.update(
                {
                    "status": str(activated["status"]),
                    "gate_failures": list(activated["gate_failures"]),
                    "activation_authorized": bool(
                        activated["activation_authorized"]
                    ),
                    "approval_event_id": str(activated["approval_event_id"]),
                    "valid_until": str(activated["valid_until"]),
                    "rollback_criteria": list(activated["rollback_criteria"]),
                    "kill_criteria": list(activated["kill_criteria"]),
                }
            )
    queues = projection.get("queues", {})
    session_items = _session_items(queues)
    today_items = [
        {
            "decision_key": row["plan_id"],
            "title": "Interrupted plan" if row["source_queue"] == "interrupted_resume" else "Plan next action",
            "source_fingerprint": str(projection.get("projection_fingerprint", "")),
            "recommended_action": "inspect",
        }
        for row in session_items
    ]
    weekly = build_weekly_digest(
        {"plans": list(queues.get("current_state", []))},
        today_items=today_items,
        previous_fingerprints=previous_fingerprints,
    )
    fingerprint_history = list(dict.fromkeys(str(value) for value in previous_fingerprints))
    fingerprint_history.extend(
        row["fingerprint"]
        for row in weekly["asks"]
        if row["fingerprint"] not in fingerprint_history
    )
    history_truncated = len(fingerprint_history) > MAX_WEEKLY_FINGERPRINT_HISTORY
    fingerprint_history = fingerprint_history[-MAX_WEEKLY_FINGERPRINT_HISTORY:]
    interrupted = list(queues.get("interrupted_resume", []))
    breakpoint = {
        "status": "candidate_preview" if interrupted else "no_interruption_candidate",
        "plan_id": str(interrupted[0].get("plan_id", "")) if interrupted else "",
        "workstream_id": str(interrupted[0].get("workstream_id", "")) if interrupted else "",
        "question": "Return to the interrupted plan now?" if interrupted else "",
        "allowed_responses": ["resume", "keep_current", "snooze"] if interrupted else [],
        "delivery_attempted": False,
        "delivery_authorized": False,
    }
    return {
        "schema_version": "dad.portfolio_continuity_attention_readiness.v1",
        "trial_status": trial_status,
        "stage_activation_state_digest": stage_activation_state_digest,
        "stages": stages,
        "session_start_summary_preview": {
            "status": "candidate_preview",
            "items": session_items,
            "item_count": len(session_items),
            "delivery_attempted": False,
            "delivery_authorized": False,
        },
        "weekly_digest_preview": weekly,
        "weekly_seen_fingerprints": fingerprint_history,
        "weekly_fingerprint_history_truncated": history_truncated,
        "breakpoint_prompt_preview": breakpoint,
        "automatic_cleanup_allowed": False,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "MAX_WEEKLY_FINGERPRINT_HISTORY",
    "STAGE_IDS",
    "build_progressive_attention_readiness",
]
