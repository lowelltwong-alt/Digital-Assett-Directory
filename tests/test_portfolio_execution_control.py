from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from digital_asset_directory import cli
from digital_asset_directory import _portfolio_execution_legacy as execution_legacy

from digital_asset_directory.portfolio_events import (
    EXECUTION_EVENT_SCHEMA_VERSION,
    build_event,
    envelope_problems,
    ledger_path,
    read_events,
)
from digital_asset_directory.portfolio_authority import VerifiedApprovals
from digital_asset_directory.portfolio_execution import (
    CAMPAIGN_BINDING_SCHEMA,
    approve_dispatch_intent,
    dispatch_packet,
    _fold_execution_control_for_test as fold_execution_control,
    grant_execution_lease,
    _load_execution_control_for_test as load_execution_control,
    propose_dispatch_intent,
    request_execution_lease,
    revoke_dispatch_intent,
    revoke_execution_lease,
)

from digital_asset_directory.portfolio_workstreams import (
    capture_ideas,
    load_state,
    record_binding,
    record_feedback,
)
from portfolio_execution_test_support import trusted_test_approvals

T0 = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _verified_records(hub: Path, *approval_ids: str) -> VerifiedApprovals:
    events, _diagnostics = read_events(ledger_path(hub))
    return trusted_test_approvals(events, approval_ids)


def _active_bound_workstream(hub: Path) -> tuple[str, str]:
    captured = capture_ideas(
        hub,
        ["Implement bounded execution control"],
        conversation_id="execution-control-test",
        now=T0,
    )
    workstream_id = captured["proposals"][0]["workstream_id"]
    record_feedback(hub, workstream_id, "resume", now=T0, command_id="resume")
    binding = record_binding(
        hub,
        workstream_id,
        "repo",
        "repo:dad",
        assertion_status="accepted",
        asserted_by="Lowell",
        approval_ref="human:binding:1",
        now=T0,
        command_id="bind-repo",
    )
    return workstream_id, binding["binding_id"]


def _requested_and_granted(hub: Path) -> tuple[str, str, str]:
    workstream_id, binding_id = _active_bound_workstream(hub)
    requested = request_execution_lease(
        hub,
        workstream_id,
        owner_id="role:builder:v1",
        owner_kind="agent",
        repo_binding_id=binding_id,
        action_classes=["implement", "validate"],
        requested_paths=["src", "tests"],
        not_before=T0,
        expires_at=T0 + timedelta(days=1),
        return_state="paused",
        rationale_code="bounded_build",
        command_id="lease-request-1",
        now=T0,
    )
    assert requested["status"] == "requested"
    granted = grant_execution_lease(
        hub,
        workstream_id,
        requested["lease_id"],
        granted_by="Lowell",
        approval_id="human:lease:1",
        command_id="lease-grant-1",
        now=T0,
    )
    assert granted["status"] == "recorded_approval_unverified"
    return workstream_id, binding_id, requested["lease_id"]


def _run_two_concurrent(call):
    start = Barrier(2)

    def run(index: int) -> dict:
        start.wait(timeout=10)
        return call(index)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, range(2)))


def _campaign_binding() -> dict:
    digest = "sha256:" + "a" * 64
    return {
        "schema_version": CAMPAIGN_BINDING_SCHEMA,
        "campaign_id": "campaign:test",
        "campaign_revision": "revision:test",
        "manifest_digest": digest,
        "job_id": "J-100",
        "packet_digest": digest,
        "source_revision": digest,
        "authorization_id": "authorization:test:r1",
        "named_approver": "Lowell",
        "authorization_receipt_digest": digest,
        "authority_approval_ids": {
            "lease_approval_id": "human:lease:campaign",
            "dispatch_approval_id": "human:dispatch:campaign",
        },
        "budget_receipt_digests": {},
        "input_digests": {"input.json": digest},
        "dependency_receipt_digests": {},
        "qualification_evidence_digests": {"qualification.json": digest},
        "idempotency_key": "campaign:test:J-100:r1",
        "worker_revision_id": "role:builder:v1",
        "checker_revision_id": "role:checker:v1",
        "action_class": "implement",
        "lease_minutes": 90,
        "output_paths": ["src"],
        "acceptance_evidence_paths": ["evidence/J-100.json"],
        "checkpoint_path": "state/J-100.json",
        "receipt_path": "state/J-100.receipts.jsonl",
        "allowed_paths": ["src"],
        "allowed_effects": ["bounded local implementation"],
        "campaign_budget_digest": digest,
        "job_budget_digest": digest,
        "durability_verifier_digest": digest,
        "evidence_snapshot_digest": digest,
        "adapter_revision": "adapter:test:r1",
        "heartbeat_at": (T0 + timedelta(minutes=1)).isoformat(),
        "heartbeat_minutes": 15,
        "repair_attempt": 0,
        "max_repairs": 1,
        "reissue_of_attempt_id": "",
        "prior_reconciliation_digest": "",
        "partial_effects_reconciled": True,
    }


def _synchronize_legacy_prelock_projection(monkeypatch) -> None:
    """Make the former read-before-lock implementation lose deterministically."""

    real_load = execution_legacy.load_execution_control
    both_read = Barrier(2)

    def synchronized_load(*args, **kwargs):
        projection = real_load(*args, **kwargs)
        both_read.wait(timeout=10)
        return projection

    monkeypatch.setattr(execution_legacy, "load_execution_control", synchronized_load)


def test_concurrent_duplicate_lease_identity_appends_exactly_once(
    tmp_path: Path, monkeypatch
) -> None:
    workstream_id, binding_id = _active_bound_workstream(tmp_path)
    lease_id = "dad:portfolio-lease:00000000-0000-0000-0000-000000000099"
    _synchronize_legacy_prelock_projection(monkeypatch)

    results = _run_two_concurrent(
        lambda index: request_execution_lease(
            tmp_path,
            workstream_id,
            owner_id="role:builder:v1",
            owner_kind="agent",
            repo_binding_id=binding_id,
            action_classes=["implement"],
            requested_paths=["src"],
            not_before=T0,
            expires_at=T0 + timedelta(days=1),
            return_state="paused",
            rationale_code="concurrency_regression",
            lease_id=lease_id,
            command_id=f"concurrent-lease-{index}",
            now=T0,
        )
    )

    assert sorted(result["status"] for result in results) == ["lease_id_exists", "requested"]
    events, diagnostics = read_events(ledger_path(tmp_path))
    requests = [
        event
        for event in events
        if event["event_kind"] == "execution_lease_requested"
        and event["payload"]["lease_id"] == lease_id
    ]
    assert len(requests) == 1
    assert diagnostics["problems"] == []
    assert load_execution_control(tmp_path, as_of=T0)["leases"][0]["identity_conflict"] is False


@pytest.mark.parametrize(
    ("operation", "event_kind", "winner", "loser"),
    [
        (
            "lease_grant",
            "execution_lease_granted",
            "recorded_approval_unverified",
            "lease_already_granted",
        ),
        ("lease_revoke", "execution_lease_revoked", "revoked_fail_closed", "already_revoked"),
        (
            "dispatch_propose",
            "dispatch_intent_proposed",
            "proposed",
            "dispatch_revision_id_exists",
        ),
        (
            "dispatch_approve",
            "dispatch_intent_approved",
            "recorded_approval_unverified",
            "dispatch_already_approved",
        ),
        ("dispatch_revoke", "dispatch_intent_revoked", "revoked_fail_closed", "already_revoked"),
    ],
)
def test_concurrent_one_shot_control_transitions_append_exactly_once(
    tmp_path: Path,
    monkeypatch,
    operation: str,
    event_kind: str,
    winner: str,
    loser: str,
) -> None:
    if operation == "lease_grant":
        workstream_id, binding_id = _active_bound_workstream(tmp_path)
        requested = request_execution_lease(
            tmp_path,
            workstream_id,
            owner_id="role:builder:v1",
            owner_kind="agent",
            repo_binding_id=binding_id,
            action_classes=["implement", "validate"],
            requested_paths=["src", "tests"],
            not_before=T0,
            expires_at=T0 + timedelta(days=1),
            return_state="paused",
            rationale_code="concurrent_grant_test",
            command_id="lease-request-before-concurrent-grant",
            now=T0,
        )
        lease_id = requested["lease_id"]
    else:
        workstream_id, binding_id, lease_id = _requested_and_granted(tmp_path)
    dispatch_id = "dad:portfolio-dispatch:00000000-0000-0000-0000-000000000099"

    if operation in {"dispatch_approve", "dispatch_revoke"}:
        proposed = propose_dispatch_intent(
            tmp_path,
            workstream_id,
            lease_id=lease_id,
            repo_binding_id=binding_id,
            action="implement",
            worker_revision_id="role:builder:v1",
            checker_revision_id="role:checker:v2",
            task_summary="Prepare concurrent one-shot transition coverage.",
            requested_paths=["src"],
            acceptance_refs=["test:concurrency"],
            validation_commands=["pytest"],
            authority_refs=["AGENTS.md"],
            expected_repo_snapshot="git:head:test;dirty:false",
            dispatch_revision_id=dispatch_id,
            command_id="prepare-concurrent-dispatch",
            now=T0 + timedelta(minutes=30),
        )
        assert proposed["status"] == "proposed"

    _synchronize_legacy_prelock_projection(monkeypatch)

    if operation == "lease_grant":
        def call(index: int) -> dict:
            return grant_execution_lease(
                tmp_path,
                workstream_id,
                lease_id,
                granted_by=f"human:{index}",
                approval_id=f"human:concurrent-grant:{index}",
                command_id=f"concurrent-grant-{index}",
                now=T0 + timedelta(hours=1),
            )
    elif operation == "lease_revoke":
        def call(index: int) -> dict:
            return revoke_execution_lease(
                tmp_path,
                workstream_id,
                lease_id,
                revoked_by=f"human:{index}",
                approval_id=f"human:concurrent-lease-revoke:{index}",
                reason_code="concurrency_regression",
                command_id=f"concurrent-lease-revoke-{index}",
                now=T0 + timedelta(hours=1),
            )
    elif operation == "dispatch_propose":
        def call(index: int) -> dict:
            return propose_dispatch_intent(
                tmp_path,
                workstream_id,
                lease_id=lease_id,
                repo_binding_id=binding_id,
                action="implement",
                worker_revision_id="role:builder:v1",
                checker_revision_id="role:checker:v2",
                task_summary="Exercise the dispatch identity gate.",
                requested_paths=["src"],
                acceptance_refs=["test:concurrency"],
                validation_commands=["pytest"],
                authority_refs=["AGENTS.md"],
                expected_repo_snapshot="git:head:test;dirty:false",
                dispatch_revision_id=dispatch_id,
                command_id=f"concurrent-dispatch-{index}",
                now=T0 + timedelta(hours=1),
            )
    elif operation == "dispatch_approve":
        def call(index: int) -> dict:
            return approve_dispatch_intent(
                tmp_path,
                workstream_id,
                dispatch_id,
                approved_by=f"human:{index}",
                approval_id=f"human:concurrent-dispatch-approve:{index}",
                expires_at=T0 + timedelta(hours=8),
                command_id=f"concurrent-dispatch-approve-{index}",
                now=T0 + timedelta(hours=1),
            )
    else:
        def call(index: int) -> dict:
            return revoke_dispatch_intent(
                tmp_path,
                workstream_id,
                dispatch_id,
                revoked_by=f"human:{index}",
                approval_id=f"human:concurrent-dispatch-revoke:{index}",
                reason_code="concurrency_regression",
                command_id=f"concurrent-dispatch-revoke-{index}",
                now=T0 + timedelta(hours=1),
            )

    results = _run_two_concurrent(call)

    assert sorted(result["status"] for result in results) == sorted([winner, loser])
    events, diagnostics = read_events(ledger_path(tmp_path))
    assert sum(event["event_kind"] == event_kind for event in events) == 1
    assert diagnostics["problems"] == []


def test_lease_is_deny_all_until_exact_approval_is_verified(tmp_path: Path) -> None:
    workstream_id, _binding_id, lease_id = _requested_and_granted(tmp_path)

    denied = load_execution_control(tmp_path, as_of=T0 + timedelta(hours=1))
    lease = next(row for row in denied["leases"] if row["lease_id"] == lease_id)
    assert lease["status"] == "approval_unverified"
    assert lease["authorization_valid"] is False

    allowed = load_execution_control(
        tmp_path,
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=_verified_records(tmp_path, "human:lease:1"),
    )
    lease = next(row for row in allowed["leases"] if row["lease_id"] == lease_id)
    assert lease["status"] == "active"
    assert lease["authorization_valid"] is True
    assert allowed["executor"] == {"available": False, "dispatch_allowed": False}
    assert workstream_id == lease["workstream_id"]


def test_dispatch_needs_separate_exact_approval_and_never_executes(tmp_path: Path) -> None:
    workstream_id, binding_id, lease_id = _requested_and_granted(tmp_path)
    proposed = propose_dispatch_intent(
        tmp_path,
        workstream_id,
        lease_id=lease_id,
        repo_binding_id=binding_id,
        action="implement",
        worker_revision_id="role:builder:v1",
        checker_revision_id="role:checker:v2",
        task_summary="Implement only the execution-control projection.",
        requested_paths=["src", "tests"],
        acceptance_refs=["test:execution-control"],
        validation_commands=["python -m pytest tests/test_portfolio_execution_control.py"],
        authority_refs=["AGENTS.md", "AI_FRONT_DOOR.md"],
        expected_repo_snapshot="git:head:abc123;dirty:false",
        command_id="dispatch-propose-1",
        now=T0 + timedelta(hours=1),
    )
    assert proposed["status"] == "proposed"
    approved = approve_dispatch_intent(
        tmp_path,
        workstream_id,
        proposed["dispatch_revision_id"],
        approved_by="Lowell",
        approval_id="human:dispatch:1",
        expires_at=T0 + timedelta(hours=8),
        command_id="dispatch-approve-1",
        now=T0 + timedelta(hours=1),
    )
    assert approved["status"] == "recorded_approval_unverified"

    one_approval = load_execution_control(
        tmp_path,
        as_of=T0 + timedelta(hours=2),
        verified_approval_records=_verified_records(tmp_path, "human:lease:1"),
    )
    row = one_approval["dispatches"][0]
    assert row["status"] == "approval_unverified"

    both = load_execution_control(
        tmp_path,
        as_of=T0 + timedelta(hours=2),
        verified_approval_records=_verified_records(tmp_path, "human:lease:1", "human:dispatch:1"),
    )
    row = both["dispatches"][0]
    assert row["status"] == "ready_manual"
    assert row["manual_packet_ready"] is True
    assert row["dispatch_allowed"] is False
    packet = dispatch_packet(both, proposed["dispatch_revision_id"])
    assert packet["manual_packet_ready"] is True
    assert packet["dispatch_allowed"] is False


def test_campaign_binding_is_hash_bound_across_lease_and_dispatch(tmp_path: Path) -> None:
    from digital_asset_directory.portfolio_execution import lease_scope_digest

    workstream_id, binding_id = _active_bound_workstream(tmp_path)
    campaign_binding = _campaign_binding()
    requested = request_execution_lease(
        tmp_path,
        workstream_id,
        owner_id="role:builder:v1",
        owner_kind="agent",
        repo_binding_id=binding_id,
        action_classes=["implement"],
        requested_paths=["src"],
        not_before=T0,
        expires_at=T0 + timedelta(hours=2),
        return_state="paused",
        rationale_code="campaign-bridge-test",
        campaign_binding=campaign_binding,
        command_id="campaign-binding-lease",
        now=T0,
    )
    assert requested["status"] == "requested"
    events, diagnostics = read_events(ledger_path(tmp_path))
    assert diagnostics["problems"] == []
    lease_payload = next(
        event["payload"]
        for event in events
        if event["event_kind"] == "execution_lease_requested"
    )
    assert lease_payload["campaign_binding"] == campaign_binding
    changed = {**lease_payload, "campaign_binding": {**campaign_binding, "job_id": "J-110"}}
    assert lease_scope_digest(changed) != lease_payload["scope_digest"]

    grant_execution_lease(
        tmp_path,
        workstream_id,
        requested["lease_id"],
        granted_by="Lowell",
        approval_id="human:campaign-lease",
        command_id="campaign-binding-grant",
        now=T0,
    )
    mismatch = propose_dispatch_intent(
        tmp_path,
        workstream_id,
        lease_id=requested["lease_id"],
        repo_binding_id=binding_id,
        action="implement",
        worker_revision_id="role:builder:v1",
        checker_revision_id="role:checker:v2",
        task_summary="Campaign binding mismatch must fail closed.",
        requested_paths=["src"],
        acceptance_refs=["test:campaign-binding"],
        validation_commands=["python -m pytest tests/test_campaign_controller.py"],
        authority_refs=["campaign:test"],
        expected_repo_snapshot="sha256:" + "b" * 64,
        campaign_binding={**campaign_binding, "job_id": "J-110"},
        command_id="campaign-binding-mismatch",
        now=T0 + timedelta(minutes=1),
    )
    assert mismatch["status"] == "campaign_binding_scope_mismatch"
    accepted = propose_dispatch_intent(
        tmp_path,
        workstream_id,
        lease_id=requested["lease_id"],
        repo_binding_id=binding_id,
        action="implement",
        worker_revision_id="role:builder:v1",
        checker_revision_id="role:checker:v2",
        task_summary="Campaign binding remains exact and non-dispatching.",
        requested_paths=["src"],
        acceptance_refs=["test:campaign-binding"],
        validation_commands=["python -m pytest tests/test_campaign_controller.py"],
        authority_refs=["campaign:test"],
        expected_repo_snapshot="sha256:" + "b" * 64,
        campaign_binding=campaign_binding,
        command_id="campaign-binding-match",
        now=T0 + timedelta(minutes=1),
    )
    assert accepted["status"] == "proposed"


def test_revocation_and_expiry_fail_closed(tmp_path: Path) -> None:
    workstream_id, _binding_id, lease_id = _requested_and_granted(tmp_path)
    exact_expiry = load_execution_control(
        tmp_path,
        as_of=T0 + timedelta(days=1),
        verified_approval_records=_verified_records(tmp_path, "human:lease:1"),
    )
    assert exact_expiry["leases"][0]["status"] == "expired"

    revoked = revoke_execution_lease(
        tmp_path,
        workstream_id,
        lease_id,
        revoked_by="Lowell",
        approval_id="human:revoke:1",
        reason_code="scope_changed",
        command_id="lease-revoke-1",
        now=T0 + timedelta(hours=2),
    )
    assert revoked["status"] == "revoked_fail_closed"
    projection = load_execution_control(
        tmp_path,
        as_of=T0 + timedelta(hours=3),
        verified_approval_records=_verified_records(tmp_path, "human:lease:1"),
    )
    assert projection["leases"][0]["status"] == "revoked"


def test_dispatch_revocation_blocks_even_when_prior_approvals_verify(tmp_path: Path) -> None:
    workstream_id, binding_id, lease_id = _requested_and_granted(tmp_path)
    proposed = propose_dispatch_intent(
        tmp_path,
        workstream_id,
        lease_id=lease_id,
        repo_binding_id=binding_id,
        action="validate",
        worker_revision_id="role:builder:v1",
        checker_revision_id="role:checker:v1",
        task_summary="Run bounded validation.",
        requested_paths=["tests"],
        acceptance_refs=["test:pass"],
        validation_commands=["python -m pytest tests/test_portfolio_execution_control.py"],
        authority_refs=["AGENTS.md"],
        expected_repo_snapshot="git:head:abc123;dirty:false",
        command_id="dispatch-propose-2",
        now=T0 + timedelta(hours=1),
    )
    approve_dispatch_intent(
        tmp_path,
        workstream_id,
        proposed["dispatch_revision_id"],
        approved_by="Lowell",
        approval_id="human:dispatch:2",
        expires_at=T0 + timedelta(hours=6),
        command_id="dispatch-approve-2",
        now=T0 + timedelta(hours=1),
    )
    revoke_dispatch_intent(
        tmp_path,
        workstream_id,
        proposed["dispatch_revision_id"],
        revoked_by="Lowell",
        approval_id="human:dispatch-revoke:2",
        reason_code="repo_drift",
        command_id="dispatch-revoke-2",
        now=T0 + timedelta(hours=2),
    )
    projection = load_execution_control(
        tmp_path,
        as_of=T0 + timedelta(hours=3),
        verified_approval_records=_verified_records(tmp_path, "human:lease:1", "human:dispatch:2"),
    )
    assert projection["dispatches"][0]["status"] == "revoked"
    assert projection["dispatches"][0]["manual_packet_ready"] is False


def test_scope_and_checker_guards_reject_before_append(tmp_path: Path) -> None:
    workstream_id, binding_id, lease_id = _requested_and_granted(tmp_path)
    before, _ = read_events(ledger_path(tmp_path))
    with pytest.raises(ValueError, match="traversal-free"):
        propose_dispatch_intent(
            tmp_path,
            workstream_id,
            lease_id=lease_id,
            repo_binding_id=binding_id,
            action="implement",
            worker_revision_id="role:builder:v1",
            checker_revision_id="checker",
            task_summary="bad path",
            requested_paths=["../outside"],
            acceptance_refs=["test:x"],
            validation_commands=["pytest"],
            authority_refs=["AGENTS.md"],
            expected_repo_snapshot="head:x",
            now=T0,
        )
    rejected = propose_dispatch_intent(
        tmp_path,
        workstream_id,
        lease_id=lease_id,
        repo_binding_id=binding_id,
        action="implement",
        worker_revision_id="same",
        checker_revision_id="same",
        task_summary="self check",
        requested_paths=["src"],
        acceptance_refs=["test:x"],
        validation_commands=["pytest"],
        authority_refs=["AGENTS.md"],
        expected_repo_snapshot="head:x",
        now=T0,
    )
    after, _ = read_events(ledger_path(tmp_path))
    assert rejected["status"] == "independent_checker_required"
    assert len(after) == len(before)


def test_mixed_v1_and_execution_events_are_reader_first_compatible(tmp_path: Path) -> None:
    workstream_id, _binding_id, _lease_id = _requested_and_granted(tmp_path)
    events, diagnostics = read_events(ledger_path(tmp_path))
    assert diagnostics["problems"] == []
    versions = {event["schema_version"] for event in events}
    assert "dad.portfolio_workstream_event.v1" in versions
    assert EXECUTION_EVENT_SCHEMA_VERSION in versions
    assert load_state(tmp_path, now=T0)["summary"]["workstream_count"] == 1
    assert all(envelope_problems(event) == [] for event in events)
    assert all(
        event["stream_id"] == workstream_id
        for event in events
        if event["event_kind"].startswith("execution_")
    )


def test_fold_detects_scope_digest_tampering_without_granting_authority() -> None:
    workstream = {
        "workstream_id": "dad:portfolio-workstream:test",
        "lifecycle_state": "active",
        "bindings": [
            {"binding_id": "binding:repo", "binding_kind": "repo", "assertion_status": "accepted"}
        ],
    }
    payload = {
        "workstream_id": workstream["workstream_id"],
        "lease_id": "dad:portfolio-lease:00000000-0000-0000-0000-000000000001",
        "owner_id": "agent",
        "owner_kind": "agent",
        "repo_binding_id": "binding:repo",
        "action_classes": ["validate"],
        "requested_paths": ["tests"],
        "not_before": T0.isoformat(),
        "expires_at": (T0 + timedelta(hours=1)).isoformat(),
        "return_state": "paused",
        "rationale_code": "test",
        "supersedes_lease_id": "",
        "scope_digest": "dad:portfolio-lease-scope:00000000-0000-0000-0000-000000000099",
    }
    forged_grant = {
        "workstream_id": workstream["workstream_id"],
        "lease_id": payload["lease_id"],
        "approval_id": "verified",
        "granted_by": "human",
        "scope_digest": payload["scope_digest"],
    }
    projection = fold_execution_control(
        [
            {
                "event_kind": "execution_lease_requested",
                "payload": payload,
                "recorded_at": T0.isoformat(),
            },
            {
                "event_kind": "execution_lease_granted",
                "payload": forged_grant,
                "recorded_at": T0.isoformat(),
            },
        ],
        [workstream],
        as_of=T0,
    )
    assert projection["leases"][0]["authorization_valid"] is False
    assert projection["leases"][0]["status"] == "blocked_scope"
    assert (
        f"lease_scope_digest_mismatch:{workstream['workstream_id']}:{payload['lease_id']}"
        in projection["diagnostics"]
    )


def test_execution_event_builder_uses_strict_v2_schema() -> None:
    payload = {
        "workstream_id": "dad:portfolio-workstream:test",
        "lease_id": "dad:portfolio-lease:00000000-0000-0000-0000-000000000001",
        "owner_id": "agent",
        "owner_kind": "agent",
        "repo_binding_id": "binding:repo",
        "action_classes": ["validate"],
        "requested_paths": ["tests"],
        "not_before": T0.isoformat(),
        "expires_at": (T0 + timedelta(hours=1)).isoformat(),
        "return_state": "paused",
        "rationale_code": "test",
        "supersedes_lease_id": "",
    }
    from digital_asset_directory.portfolio_execution import lease_scope_digest

    payload["scope_digest"] = lease_scope_digest(payload)
    event, _ = build_event(
        event_kind="execution_lease_requested",
        stream_id=payload["workstream_id"],
        payload=payload,
        prev_event_id="",
        recorded_at=T0.isoformat(),
        command_id="schema-test",
    )
    assert event["schema_version"] == EXECUTION_EVENT_SCHEMA_VERSION
    assert envelope_problems(event) == []
    event["payload"]["unexpected"] = True
    assert envelope_problems(event)


def test_dependency_route_id_is_required_only_for_j600_campaign_bindings() -> None:
    from digital_asset_directory.portfolio_execution import lease_scope_digest

    binding = {
        **_campaign_binding(),
        "job_id": "J-600",
        "dependency_route_id": "p5c-pass",
    }
    payload = {
        "workstream_id": "dad:portfolio-workstream:route-schema-test",
        "lease_id": "dad:portfolio-lease:00000000-0000-0000-0000-000000000071",
        "owner_id": "agent",
        "owner_kind": "agent",
        "repo_binding_id": "binding:repo",
        "action_classes": ["validate"],
        "requested_paths": ["tests"],
        "not_before": T0.isoformat(),
        "expires_at": (T0 + timedelta(hours=1)).isoformat(),
        "return_state": "paused",
        "rationale_code": "terminal-route-schema-test",
        "supersedes_lease_id": "",
        "campaign_binding": binding,
    }
    payload["scope_digest"] = lease_scope_digest(payload)
    event, _ = build_event(
        event_kind="execution_lease_requested",
        stream_id=payload["workstream_id"],
        payload=payload,
        prev_event_id="",
        recorded_at=T0.isoformat(),
        command_id="terminal-route-schema-test",
    )
    assert envelope_problems(event) == []

    missing = {**event, "payload": {**event["payload"]}}
    missing["payload"]["campaign_binding"] = {
        key: value
        for key, value in event["payload"]["campaign_binding"].items()
        if key != "dependency_route_id"
    }
    assert any("dependency_route_id" in problem for problem in envelope_problems(missing))

    ordinary = {**event, "payload": {**event["payload"]}}
    ordinary["payload"]["campaign_binding"] = {
        **event["payload"]["campaign_binding"],
        "job_id": "J-100",
    }
    assert any("dependency_route_id" in problem for problem in envelope_problems(ordinary))

    for invalid in (None, "P5C_PASS", "9bad-route"):
        malformed = {**event, "payload": {**event["payload"]}}
        malformed["payload"]["campaign_binding"] = {
            **event["payload"]["campaign_binding"],
            "dependency_route_id": invalid,
        }
        assert any(
            "dependency_route_id" in problem
            for problem in envelope_problems(malformed)
        )


def test_atomic_case_binding_is_required_for_lease_and_dispatch_only() -> None:
    from digital_asset_directory.portfolio_execution import (
        dispatch_scope_digest,
        lease_scope_digest,
    )

    digest = "sha256:" + "b" * 64
    atomic_fields = {
        "case_id": "case:shadow:001",
        "case_digest": digest,
        "case_binding_table_digest": digest,
        "case_envelope_path": (
            "processed/reports/dad-high-value-recovery/"
            "pilot-case-envelopes/J-510-C01.json"
        ),
    }
    binding = {
        **_campaign_binding(),
        "job_id": "J-510-C01",
        "idempotency_key": f"campaign:test:J-510-C01:{digest}:r1",
        **atomic_fields,
    }
    lease_payload = {
        "workstream_id": "dad:portfolio-workstream:atomic-schema-test",
        "lease_id": "dad:portfolio-lease:00000000-0000-0000-0000-000000000072",
        "owner_id": "agent",
        "owner_kind": "agent",
        "repo_binding_id": "binding:repo",
        "action_classes": ["implement"],
        "requested_paths": [atomic_fields["case_envelope_path"]],
        "not_before": T0.isoformat(),
        "expires_at": (T0 + timedelta(hours=1)).isoformat(),
        "return_state": "paused",
        "rationale_code": "atomic-schema-test",
        "supersedes_lease_id": "",
        "campaign_binding": binding,
    }
    lease_payload["scope_digest"] = lease_scope_digest(lease_payload)
    lease_event, _ = build_event(
        event_kind="execution_lease_requested",
        stream_id=lease_payload["workstream_id"],
        payload=lease_payload,
        prev_event_id="",
        recorded_at=T0.isoformat(),
        command_id="atomic-lease-schema-test",
    )
    assert envelope_problems(lease_event) == []

    dispatch_payload = {
        "workstream_id": lease_payload["workstream_id"],
        "dispatch_revision_id": (
            "dad:portfolio-dispatch:00000000-0000-0000-0000-000000000072"
        ),
        "lease_id": lease_payload["lease_id"],
        "repo_binding_id": "binding:repo",
        "action": "implement",
        "worker_revision_id": "role:builder:v1",
        "checker_revision_id": "role:checker:v1",
        "task_summary": "Validate exact atomic binding propagation.",
        "requested_paths": [atomic_fields["case_envelope_path"]],
        "acceptance_refs": ["gate:atomic"],
        "validation_commands": ["pytest atomic"],
        "authority_refs": ["human:atomic"],
        "expected_repo_snapshot": digest,
        "forbidden_actions": ["external effects"],
        "campaign_binding": binding,
    }
    dispatch_payload["scope_digest"] = dispatch_scope_digest(dispatch_payload)
    dispatch_event, _ = build_event(
        event_kind="dispatch_intent_proposed",
        stream_id=dispatch_payload["workstream_id"],
        payload=dispatch_payload,
        prev_event_id="",
        recorded_at=T0.isoformat(),
        command_id="atomic-dispatch-schema-test",
    )
    assert envelope_problems(dispatch_event) == []

    for field in atomic_fields:
        omitted = {**lease_event, "payload": {**lease_event["payload"]}}
        omitted_binding = dict(lease_event["payload"]["campaign_binding"])
        omitted_binding.pop(field)
        omitted["payload"]["campaign_binding"] = omitted_binding
        assert any(field in problem for problem in envelope_problems(omitted))

        null_value = {**lease_event, "payload": {**lease_event["payload"]}}
        null_binding = dict(lease_event["payload"]["campaign_binding"])
        null_binding[field] = None
        null_value["payload"]["campaign_binding"] = null_binding
        assert any(field in problem for problem in envelope_problems(null_value))

    ordinary = {**lease_event, "payload": {**lease_event["payload"]}}
    ordinary["payload"]["campaign_binding"] = {
        **lease_event["payload"]["campaign_binding"],
        "job_id": "J-100",
    }
    assert any("case_" in problem for problem in envelope_problems(ordinary))


def test_cohort_reconciliation_digest_is_required_only_for_parent_jobs() -> None:
    from digital_asset_directory.portfolio_execution import lease_scope_digest

    digest = "sha256:" + "c" * 64
    binding = {
        **_campaign_binding(),
        "job_id": "J-510",
        "cohort_reconciliation_projection_digest": digest,
    }
    payload = {
        "workstream_id": "dad:portfolio-workstream:cohort-schema-test",
        "lease_id": "dad:portfolio-lease:00000000-0000-0000-0000-000000000073",
        "owner_id": "agent",
        "owner_kind": "agent",
        "repo_binding_id": "binding:repo",
        "action_classes": ["validate"],
        "requested_paths": ["processed/reports/dad-high-value-recovery"],
        "not_before": T0.isoformat(),
        "expires_at": (T0 + timedelta(hours=1)).isoformat(),
        "return_state": "paused",
        "rationale_code": "cohort-schema-test",
        "supersedes_lease_id": "",
        "campaign_binding": binding,
    }
    payload["scope_digest"] = lease_scope_digest(payload)
    event, _ = build_event(
        event_kind="execution_lease_requested",
        stream_id=payload["workstream_id"],
        payload=payload,
        prev_event_id="",
        recorded_at=T0.isoformat(),
        command_id="cohort-schema-test",
    )
    assert envelope_problems(event) == []

    for parent_id in ("J-510", "J-520", "J-530"):
        parent = {**event, "payload": {**event["payload"]}}
        parent["payload"]["campaign_binding"] = {
            **event["payload"]["campaign_binding"],
            "job_id": parent_id,
        }
        assert envelope_problems(parent) == []

    missing = {**event, "payload": {**event["payload"]}}
    missing_binding = dict(event["payload"]["campaign_binding"])
    missing_binding.pop("cohort_reconciliation_projection_digest")
    missing["payload"]["campaign_binding"] = missing_binding
    assert any(
        "cohort_reconciliation_projection_digest" in problem
        for problem in envelope_problems(missing)
    )

    for job_id, extras in (
        ("J-100", {}),
        ("J-600", {"dependency_route_id": "p5c-pass"}),
        (
            "J-510-C01",
            {
                "case_id": "case:shadow:001",
                "case_digest": digest,
                "case_binding_table_digest": digest,
                "case_envelope_path": (
                    "processed/reports/dad-high-value-recovery/"
                    "pilot-case-envelopes/J-510-C01.json"
                ),
            },
        ),
    ):
        forbidden = {**event, "payload": {**event["payload"]}}
        forbidden["payload"]["campaign_binding"] = {
            **event["payload"]["campaign_binding"],
            "job_id": job_id,
            **extras,
        }
        assert any(
            "cohort_reconciliation_projection_digest" in problem
            for problem in envelope_problems(forbidden)
        )


def test_cli_execution_is_deny_all_and_missing_packet_fails(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(cli, "_cfg", lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path))
    execution = runner.invoke(cli.app, ["os", "execution"])
    assert execution.exit_code == 0
    assert '"available": false' in execution.output.lower()
    assert '"default": "deny_all"' in execution.output.lower()

    missing = runner.invoke(cli.app, ["os", "dispatch-packet", "dad:portfolio-dispatch:missing"])
    assert missing.exit_code == 2
    assert "unknown_dispatch" in missing.output
