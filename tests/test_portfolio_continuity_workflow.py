from __future__ import annotations

from datetime import datetime, timezone

from digital_asset_directory.portfolio_continuity_workflow import (
    assess_closeout,
    build_manual_workflow_status,
    project_continuity_state,
    recommend_worktree,
)


def _plan(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "plan_id": "plan:one",
        "revision_id": "revision:two",
        "lifecycle": "decision_complete",
        "implementation_state": "partial",
        "outcome": "Build continuity",
        "smallest_next_action": "Run the recovery fixture",
        "acceptance_evidence": ["fixture passes"],
        "independent_check_ref": "",
        "producer_ref": "",
        "independent_checker_ref": "",
        "validated_plan_revision_id": "",
    }
    value.update(updates)
    return value


def _workstream(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "workstream_id": "ws:one",
        "lifecycle_state": "active",
        "next_action": "Run the recovery fixture",
        "bindings": [],
        "capsule": {},
    }
    value.update(updates)
    return value


def test_durable_lifecycle_and_overlays_are_not_collapsed() -> None:
    state = project_continuity_state(
        plan=_plan(implementation_state="validation_pending"),
        workstream=_workstream(lifecycle_state="paused", capsule={"blocker": "waiting"}),
        execution_control={"leases": []},
        focus_window_active=True,
    )
    assert state["durable_lifecycle"] == "paused"
    assert state["overlays"]["blocking"] == "blocked"
    assert state["overlays"]["validation"] == "validation_pending"
    assert state["overlays"]["focus"] == "outside-focus-window"
    assert state["execution_authorized"] is False


def test_verified_completion_requires_independent_evidence() -> None:
    incomplete = project_continuity_state(
        plan=_plan(implementation_state="verified_complete"),
        workstream=_workstream(),
    )
    assert incomplete["overlays"]["delivery"] == "not_delivered"
    assert "independent_check_missing" in incomplete["completion_blockers"]

    complete = project_continuity_state(
        plan=_plan(
            implementation_state="verified_complete",
            independent_check_ref="check:one",
            producer_ref="agent:builder",
            independent_checker_ref="agent:checker",
            validated_plan_revision_id="revision:one",
        ),
        workstream=_workstream(),
    )
    assert complete["overlays"]["delivery"] == "delivered"


def test_clean_git_and_closed_task_do_not_make_closeout_ready() -> None:
    result = assess_closeout(
        plan=_plan(),
        workstream=_workstream(),
        recovery_bundle={
            "snapshot_current": True,
            "classification": "contained_in_main",
            "completion_supported": False,
        },
        task_observation={"task_id": "task:one", "status": "closed", "observed_at": "2026-07-17T00:00:00Z"},
        preserved_handoff_ref="handoff:one",
        branch_pr_disposition_ref="pr:merged",
        now=datetime(2026, 7, 17, 1, tzinfo=timezone.utc),
    )
    assert result["task_archive"]["ready_for_human_decision"] is False
    assert result["worktree_remove"]["ready_for_human_decision"] is False
    assert "plan_not_evidence_terminal" in result["task_archive"]["blockers"]
    assert result["task_archive"]["action_executed"] is False


def test_task_archive_and_worktree_remove_are_separate_human_gates() -> None:
    complete = _plan(
        implementation_state="verified_complete",
        independent_check_ref="check:one",
        producer_ref="agent:builder",
        independent_checker_ref="agent:checker",
        validated_plan_revision_id="revision:one",
    )
    result = assess_closeout(
        plan=complete,
        workstream=_workstream(),
        recovery_bundle={
            "snapshot_current": True,
            "classification": "contained_in_main",
            "completion_supported": True,
        },
        task_observation={
            "task_id": "task:one",
            "observed_at": "2026-07-17T00:00:00Z",
            "snapshot_current": True,
            "snapshot_valid_until": "2026-07-18T00:00:00Z",
            "snapshot_receipt_ref": "receipt:task-one",
        },
        preserved_handoff_ref="handoff:one",
        branch_pr_disposition_ref="pr:merged",
        now=datetime(2026, 7, 17, 1, tzinfo=timezone.utc),
    )
    assert result["task_archive"]["ready_for_human_decision"] is True
    assert result["worktree_remove"]["ready_for_human_decision"] is True
    assert result["task_archive"]["requires_exact_human_approval"] is True
    assert result["worktree_remove"]["requires_exact_human_approval"] is True
    assert result["branch_delete"]["ready_for_human_decision"] is False


def test_stale_task_observation_cannot_make_archive_ready() -> None:
    complete = _plan(
        implementation_state="verified_complete",
        independent_check_ref="check:one",
        producer_ref="agent:builder",
        independent_checker_ref="agent:checker",
        validated_plan_revision_id="revision:one",
    )
    result = assess_closeout(
        plan=complete,
        workstream=_workstream(),
        recovery_bundle={
            "snapshot_current": True,
            "classification": "contained_in_main",
            "completion_supported": True,
        },
        task_observation={
            "task_id": "task:one",
            "observed_at": "2000-01-01T00:00:00Z",
            "snapshot_current": True,
            "snapshot_valid_until": "2000-01-01T01:00:00Z",
            "snapshot_receipt_ref": "receipt:stale",
        },
        preserved_handoff_ref="handoff:one",
        branch_pr_disposition_ref="pr:merged",
    )
    assert result["task_archive"]["ready_for_human_decision"] is False
    assert "task_snapshot_freshness_unverified" in result["task_archive"]["blockers"]


def test_new_worktree_recommendation_never_acts_and_requires_promotion() -> None:
    proposed = recommend_worktree(
        workstream=_workstream(lifecycle_state="proposed"),
        repository_id="repo:one",
        material_multi_session=True,
        isolation_useful=True,
    )
    assert proposed["recommend_open_worktree"] is False
    assert "workstream_not_promoted" in proposed["blockers"]

    active = recommend_worktree(
        workstream=_workstream(),
        repository_id="repo:one",
        material_multi_session=True,
        isolation_useful=True,
    )
    assert active["recommend_open_worktree"] is True
    assert active["requires_exact_human_approval"] is True
    assert active["action_executed"] is False

    already_bound = recommend_worktree(
        workstream=_workstream(),
        repository_id="repo:one",
        existing_bindings=[
            {
                "binding_kind": "worktree",
                "assertion_status": "accepted",
                "ref": "worktree:one",
            }
        ],
        material_multi_session=True,
        isolation_useful=True,
    )
    assert already_bound["recommend_open_worktree"] is False
    assert "accepted_worktree_already_bound" in already_bound["blockers"]


def test_manual_workflow_reports_every_stage_without_mutation() -> None:
    result = build_manual_workflow_status(
        plan=_plan(),
        roadmap={"item_count": 3, "accepted_count": 1, "remaining_count": 2},
        workstream=_workstream(),
    )
    assert result["stages"] == {
        "checkpoint": True,
        "plan_revision": True,
        "resume": True,
        "acceptance": False,
        "archive_assessment": True,
    }
    assert result["roadmap"]["remaining_count"] == 2
    assert result["execution_authorized"] is False
