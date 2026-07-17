from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect

import pytest

from digital_asset_directory import portfolio_continuity_stage_activation as stages
from digital_asset_directory import portfolio_continuity_trial as trial
from digital_asset_directory.portfolio_continuity_attention import (
    build_progressive_attention_readiness,
)


ZERO_FAILURES = {
    "missed_captures": 0,
    "missed_recoveries": 0,
    "unnecessary_captures": 0,
    "harmful_captures": 0,
    "false_duplicate_suggestions": 0,
    "false_merges": 0,
    "accidental_mutations": 0,
    "unauthorized_mutations": 0,
    "repeated_unchanged_asks": 0,
    "privacy_escapes": 0,
    "blind_delivery_retries": 0,
    "model_calls_on_unchanged_cycles": 0,
}


def _eligible_state(
    evaluated_at: str = "2026-07-08T01:00:00+00:00",
) -> dict:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    reviews = [
        trial._review_record(
            trial_id="trial:stage-v1",
            reviewer_id="human:fixture",
            snapshot_digest="sha256:" + f"{index + 1:064x}",
            failure_metrics=ZERO_FAILURES,
            hook_sample_count=5,
            hook_latency_ms_p95=20.0,
            performance_evidence_digest="sha256:" + "d" * 64,
            adapter_interface_digest="sha256:" + "a" * 64,
            performance_measurement_origin="instrumented_harness",
            supervisor_attestation_id=f"attestation:{index + 1}",
            useful_capture_count=1,
            eligible_plan_count=1,
            max_asks_in_digest=1,
            notification_content_safe=True,
            recorded_at=(start + timedelta(days=(0, 2, 4, 6, 7)[index])).isoformat(),
            fixture_only=False,
        )
        for index in range(5)
    ]
    return trial.evaluate_trial(
        reviews,
        trial_id="trial:stage-v1",
        evaluated_at=evaluated_at,
        host_readiness={
            "status": "ready_for_supervised_trial",
            "assessment_digest": "sha256:" + "e" * 64,
            "assessed_at": "2026-06-30T00:00:00+00:00",
            "gate_failures": [],
            "adapter_binding": {
                "computed_interface_digest": "sha256:" + "a" * 64,
            },
        },
    )


def _approval(
    activation: dict,
    stage_id: str,
    recorded_at: str,
    predecessor: str = "",
    *,
    decision: str = "approve",
    adapter_digest: str = "sha256:" + "a" * 64,
) -> dict:
    return stages._stage_approval_record(
        stage_id=stage_id,
        decision=decision,
        approved_by="human:fixture",
        approval_ref="approval:fixture",
        trial_id=activation["trial_id"],
        eligibility_state_digest=stages.eligibility_state_digest(activation),
        adapter_interface_digest=adapter_digest,
        predecessor_approval_event_id=predecessor,
        rollback_criteria=["latency_budget_exceeded"],
        kill_criteria=["unauthorized_mutation_observed"],
        recorded_at=recorded_at,
        valid_until="2026-08-01T00:00:00+00:00",
        fixture_only=False,
    )


def _projection() -> dict:
    return {
        "projection_fingerprint": "sha256:" + "f" * 64,
        "queues": {
            "current_state": [],
            "interrupted_resume": [],
            "next_actions": [],
        },
    }


def test_ordered_approvals_activate_only_their_exact_scoped_stages() -> None:
    activation = _eligible_state()
    session = _approval(
        activation, "session_start_summary", "2026-07-08T02:00:00+00:00"
    )
    weekly = _approval(
        activation,
        "weekly_changed_only_digest",
        "2026-07-08T03:00:00+00:00",
        session["approval_event_id"],
    )
    breakpoint = _approval(
        activation,
        "breakpoint_prompts",
        "2026-07-08T04:00:00+00:00",
        weekly["approval_event_id"],
    )

    state = stages.fold_stage_activation(
        [session, weekly, breakpoint],
        activation_state=activation,
        adapter_interface_digest="sha256:" + "a" * 64,
        evaluated_at="2026-07-09T00:00:00+00:00",
    )

    by_id = {row["stage_id"]: row for row in state["stages"]}
    assert all(by_id[stage_id]["activation_authorized"] for stage_id in stages.STAGE_ORDER)
    assert by_id["breakpoint_prompts"]["status"] == "active"
    assert state["automatic_cleanup_allowed"] is False
    assert state["execution_authorized"] is False
    stages.validate_stage_activation_state(state)

    packet = build_progressive_attention_readiness(
        _projection(),
        activation_state=activation,
        stage_approvals=[session, weekly, breakpoint],
        adapter_interface_digest="sha256:" + "a" * 64,
        stage_evaluated_at="2026-07-09T00:00:00+00:00",
    )
    packet_stages = {row["stage_id"]: row for row in packet["stages"]}
    assert packet_stages["weekly_changed_only_digest"]["status"] == "active"
    assert packet_stages["weekly_changed_only_digest"]["approval_event_id"]
    assert packet["stage_activation_state_digest"] == state["state_digest"]
    assert packet["automatic_cleanup_allowed"] is False
    assert packet["execution_authorized"] is False


def test_stale_adapter_or_revocation_fails_closed_and_blocks_downstream() -> None:
    activation = _eligible_state()
    stale = _approval(
        activation,
        "session_start_summary",
        "2026-07-08T02:00:00+00:00",
        adapter_digest="sha256:" + "b" * 64,
    )
    state = stages.fold_stage_activation(
        [stale],
        activation_state=activation,
        adapter_interface_digest="sha256:" + "a" * 64,
        evaluated_at="2026-07-09T00:00:00+00:00",
    )
    by_id = {row["stage_id"]: row for row in state["stages"]}
    assert by_id["session_start_summary"]["status"] == "stale_binding"
    assert by_id["weekly_changed_only_digest"]["status"] == "blocked_by_predecessor_stage"

    approved = _approval(
        activation, "session_start_summary", "2026-07-08T02:00:00+00:00"
    )
    revoked = _approval(
        activation,
        "session_start_summary",
        "2026-07-08T03:00:00+00:00",
        decision="revoke",
    )
    revoked_state = stages.fold_stage_activation(
        [approved, revoked],
        activation_state=activation,
        adapter_interface_digest="sha256:" + "a" * 64,
        evaluated_at="2026-07-09T00:00:00+00:00",
    )
    revoked_by_id = {row["stage_id"]: row for row in revoked_state["stages"]}
    assert revoked_by_id["session_start_summary"]["status"] == "revoked"
    assert revoked_by_id["session_start_summary"]["activation_authorized"] is False


def test_approval_binding_is_stable_across_status_checks_but_duplicates_fail() -> None:
    activation = _eligible_state()
    later_activation = _eligible_state("2026-07-10T01:00:00+00:00")
    approval = _approval(
        activation, "session_start_summary", "2026-07-08T02:00:00+00:00"
    )

    assert stages.eligibility_state_digest(activation) == (
        stages.eligibility_state_digest(later_activation)
    )
    state = stages.fold_stage_activation(
        [approval],
        activation_state=later_activation,
        adapter_interface_digest="sha256:" + "a" * 64,
        evaluated_at="2026-07-10T01:00:00+00:00",
    )
    assert state["stages"][2]["status"] == "active"
    with pytest.raises(stages.ContinuityIntegrityError, match="duplicate"):
        stages.fold_stage_activation(
            [approval, approval],
            activation_state=later_activation,
            adapter_interface_digest="sha256:" + "a" * 64,
            evaluated_at="2026-07-10T01:00:00+00:00",
        )


def test_later_appended_kill_wins_even_when_its_clock_moves_backwards() -> None:
    activation = _eligible_state()
    approved = _approval(
        activation, "session_start_summary", "2026-07-08T03:00:00+00:00"
    )
    killed = _approval(
        activation,
        "session_start_summary",
        "2026-07-08T02:59:00+00:00",
        decision="kill",
    )

    state = stages.fold_stage_activation(
        [approved, killed],
        activation_state=activation,
        adapter_interface_digest="sha256:" + "a" * 64,
        evaluated_at="2026-07-09T00:00:00+00:00",
    )

    session = state["stages"][2]
    assert session["status"] == "killed"
    assert session["activation_authorized"] is False
    assert session["approval_event_id"] == killed["approval_event_id"]


def test_fixture_approval_never_authorizes_and_production_clock_is_not_injectable() -> None:
    activation = _eligible_state()
    fixture = stages.build_fixture_stage_approval(
        stage_id="session_start_summary",
        decision="approve",
        approved_by="human:fixture",
        approval_ref="approval:fixture",
        trial_id=activation["trial_id"],
        eligibility_state_digest=stages.eligibility_state_digest(activation),
        adapter_interface_digest="sha256:" + "a" * 64,
        predecessor_approval_event_id="",
        rollback_criteria=["latency_budget_exceeded"],
        kill_criteria=["unauthorized_mutation_observed"],
        recorded_at="2026-07-08T02:00:00+00:00",
        valid_until="2026-08-01T00:00:00+00:00",
    )
    state = stages.fold_stage_activation(
        [fixture],
        activation_state=activation,
        adapter_interface_digest="sha256:" + "a" * 64,
        evaluated_at="2026-07-09T00:00:00+00:00",
    )
    by_id = {row["stage_id"]: row for row in state["stages"]}
    assert state["fixture_approval_count"] == 1
    assert by_id["session_start_summary"]["status"] == "separate_human_approval_required"
    assert "recorded_at" not in inspect.signature(stages.record_stage_approval).parameters
