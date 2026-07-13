from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from digital_asset_directory.portfolio_authority import VerifiedApprovals
from digital_asset_directory.portfolio_execution import (
    DEFAULT_FORBIDDEN_ACTIONS,
    dispatch_scope_digest,
    _fold_execution_control_for_test as fold_execution_control,
    fold_execution_control as public_fold_execution_control,
    lease_scope_digest,
)

from portfolio_execution_test_support import trusted_test_approvals


T0 = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
WS_A = "dad:portfolio-workstream:a"
WS_B = "dad:portfolio-workstream:b"
LEASE_A = "dad:portfolio-lease:00000000-0000-0000-0000-000000000001"
LEASE_B = "dad:portfolio-lease:00000000-0000-0000-0000-000000000002"
DISPATCH_A = "dad:portfolio-dispatch:00000000-0000-0000-0000-000000000001"


def _workstream(workstream_id: str, *binding_ids: str) -> dict:
    return {
        "workstream_id": workstream_id,
        "lifecycle_state": "active",
        "bindings": [
            {
                "binding_id": binding_id,
                "binding_kind": "repo",
                "assertion_status": "accepted",
            }
            for binding_id in binding_ids
        ],
    }


def _lease(
    workstream_id: str,
    lease_id: str,
    *,
    actions: tuple[str, ...] = ("validate",),
    paths: tuple[str, ...] = ("tests",),
    owner_id: str = "role:worker:v1",
    supersedes: str = "",
    expires_at: datetime | None = None,
) -> dict:
    payload = {
        "workstream_id": workstream_id,
        "lease_id": lease_id,
        "owner_id": owner_id,
        "owner_kind": "agent",
        "repo_binding_id": "binding:repo",
        "action_classes": list(actions),
        "requested_paths": list(paths),
        "not_before": T0.isoformat(),
        "expires_at": (expires_at or T0 + timedelta(days=1)).isoformat(),
        "return_state": "paused",
        "rationale_code": "authority_invariant_test",
        "supersedes_lease_id": supersedes,
    }
    payload["scope_digest"] = lease_scope_digest(payload)
    return payload


def _grant(lease: dict, approval_id: str) -> dict:
    return {
        "workstream_id": lease["workstream_id"],
        "lease_id": lease["lease_id"],
        "scope_digest": lease["scope_digest"],
        "granted_by": "human:reviewer",
        "approval_id": approval_id,
    }


def _dispatch(
    lease: dict,
    *,
    workstream_id: str | None = None,
    action: str = "validate",
    repo_binding_id: str = "binding:repo",
    paths: tuple[str, ...] = ("tests",),
    worker_revision_id: str = "role:worker:v1",
    forbidden_actions: tuple[str, ...] = DEFAULT_FORBIDDEN_ACTIONS,
    task_summary: str = "Run bounded validation.",
) -> dict:
    payload = {
        "workstream_id": workstream_id or lease["workstream_id"],
        "dispatch_revision_id": DISPATCH_A,
        "lease_id": lease["lease_id"],
        "repo_binding_id": repo_binding_id,
        "action": action,
        "worker_revision_id": worker_revision_id,
        "checker_revision_id": "role:checker:v1",
        "task_summary": task_summary,
        "requested_paths": list(paths),
        "acceptance_refs": ["test:authority-invariants"],
        "validation_commands": ["pytest"],
        "authority_refs": ["AGENTS.md"],
        "expected_repo_snapshot": "git:head:abc;dirty:false",
        "forbidden_actions": list(forbidden_actions),
    }
    payload["scope_digest"] = dispatch_scope_digest(payload)
    return payload


def _approval(dispatch: dict, lease: dict, approval_id: str) -> dict:
    return {
        "workstream_id": dispatch["workstream_id"],
        "dispatch_revision_id": dispatch["dispatch_revision_id"],
        "lease_id": lease["lease_id"],
        "proposal_scope_digest": dispatch["scope_digest"],
        "lease_scope_digest": lease["scope_digest"],
        "approved_by": "human:reviewer",
        "approval_id": approval_id,
        "expires_at": (T0 + timedelta(hours=8)).isoformat(),
    }


def _event(kind: str, payload: dict, at: datetime = T0) -> dict:
    return {"event_kind": kind, "payload": payload, "recorded_at": at.isoformat()}


def _verified(kind: str, payload: dict, *, at: datetime = T0) -> VerifiedApprovals:
    return trusted_test_approvals([_event(kind, payload, at)], [str(payload["approval_id"])])


def test_cross_workstream_grant_cannot_attach_by_business_id() -> None:
    lease = _lease(WS_A, LEASE_A)
    cross_stream_grant = _grant(lease, "approval:cross") | {"workstream_id": WS_B}
    projection = fold_execution_control(
        [
            _event("execution_lease_requested", lease),
            _event("execution_lease_granted", cross_stream_grant),
        ],
        [_workstream(WS_A, "binding:repo"), _workstream(WS_B, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[_verified("execution_lease_granted", cross_stream_grant)],
    )
    assert projection["leases"][0]["status"] == "requested"
    assert projection["leases"][0]["authorization_valid"] is False
    assert any(item.startswith("grant_without_request:") for item in projection["diagnostics"])


def test_dispatch_scope_is_revalidated_during_fold() -> None:
    lease = _lease(WS_A, LEASE_A)
    grant = _grant(lease, "approval:lease")
    dispatch = _dispatch(
        lease,
        action="implement",
        repo_binding_id="binding:other",
        paths=("src/secret.py",),
        worker_revision_id="role:other-worker:v1",
        forbidden_actions=(),
    )
    approval = _approval(dispatch, lease, "approval:dispatch")
    projection = fold_execution_control(
        [
            _event("execution_lease_requested", lease),
            _event("execution_lease_granted", grant),
            _event("dispatch_intent_proposed", dispatch),
            _event("dispatch_intent_approved", approval),
        ],
        [_workstream(WS_A, "binding:repo", "binding:other")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[
            _verified("execution_lease_granted", grant),
            _verified("dispatch_intent_approved", approval),
        ],
    )
    row = projection["dispatches"][0]
    assert row["status"] == "blocked_scope"
    assert row["authorization_valid"] is False
    diagnostics = "\n".join(projection["diagnostics"])
    assert "dispatch_action_outside_lease" in diagnostics
    assert "dispatch_repo_binding_outside_lease" in diagnostics
    assert "dispatch_path_outside_lease" in diagnostics
    assert "dispatch_mandatory_forbidden_action_missing" in diagnostics
    assert "dispatch_worker_not_lease_owner" in diagnostics


def test_duplicate_lease_request_cannot_erase_revocation_or_resurrect() -> None:
    lease = _lease(WS_A, LEASE_A)
    grant = _grant(lease, "approval:lease")
    revoke = {
        "workstream_id": WS_A,
        "lease_id": LEASE_A,
        "revoked_by": "human:reviewer",
        "approval_id": "approval:revoke",
        "reason_code": "scope_changed",
    }
    projection = fold_execution_control(
        [
            _event("execution_lease_requested", lease),
            _event("execution_lease_granted", grant, T0 + timedelta(minutes=1)),
            _event("execution_lease_revoked", revoke, T0 + timedelta(minutes=2)),
            _event("execution_lease_requested", lease, T0 + timedelta(minutes=3)),
            _event("execution_lease_granted", grant, T0 + timedelta(minutes=4)),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[_verified("execution_lease_granted", grant)],
    )
    row = projection["leases"][0]
    assert row["status"] == "blocked_identity_conflict"
    assert row["revocation"] is not None
    assert row["authorization_valid"] is False


def test_bare_ids_never_verify_and_reused_typed_ids_invalidate_all_uses() -> None:
    lease_a = _lease(WS_A, LEASE_A)
    lease_b = _lease(WS_B, LEASE_B)
    grant_a = _grant(lease_a, "approval:reused")
    grant_b = _grant(lease_b, "approval:reused")
    events = [
        _event("execution_lease_requested", lease_a),
        _event("execution_lease_granted", grant_a),
        _event("execution_lease_requested", lease_b),
        _event("execution_lease_granted", grant_b),
    ]
    workstreams = [_workstream(WS_A, "binding:repo"), _workstream(WS_B, "binding:repo")]
    with pytest.raises(TypeError):
        public_fold_execution_control(
            events,
            workstreams,
            as_of=T0 + timedelta(hours=1),
            verified_approval_ids=["approval:reused"],
        )
    bare = public_fold_execution_control(
        events,
        workstreams,
        as_of=T0 + timedelta(hours=1),
    )
    assert all(row["status"] == "approval_unverified" for row in bare["leases"])
    assert "approval_verifier:trusted_verifier_not_supplied" in bare["diagnostics"]

    reused = fold_execution_control(
        events,
        workstreams,
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[
            _verified("execution_lease_granted", grant_a),
            _verified("execution_lease_granted", grant_b),
        ],
    )
    assert all(row["status"] == "approval_unverified" for row in reused["leases"])
    assert "approval_id_reused:approval:reused" in reused["diagnostics"]


def test_scope_digest_is_byte_exact_and_does_not_normalize_backslashes() -> None:
    lease = _lease(WS_A, LEASE_A)
    backslash = _dispatch(lease, task_summary="a\\b")
    double_slash = _dispatch(lease, task_summary="a//b")
    assert backslash["scope_digest"] != double_slash["scope_digest"]


def test_future_authority_event_is_ignored_for_historical_projection() -> None:
    lease = _lease(WS_A, LEASE_A)
    grant = _grant(lease, "approval:future")
    projection = fold_execution_control(
        [
            _event("execution_lease_requested", lease),
            _event("execution_lease_granted", grant, T0 + timedelta(hours=2)),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[_verified("execution_lease_granted", grant)],
    )
    assert projection["leases"][0]["status"] == "requested"
    assert any(item.startswith("future_event_ignored:") for item in projection["diagnostics"])


def test_only_active_valid_replacement_supersedes_prior_lease() -> None:
    old = _lease(WS_A, LEASE_A)
    old_grant = _grant(old, "approval:old")
    invalid = _lease(WS_A, LEASE_B, supersedes=LEASE_A)
    invalid["scope_digest"] = "dad:portfolio-lease-scope:" + "0" * 64
    invalid_grant = _grant(invalid, "approval:invalid")
    invalid_projection = fold_execution_control(
        [
            _event("execution_lease_requested", old),
            _event("execution_lease_granted", old_grant),
            _event("execution_lease_requested", invalid, T0 + timedelta(minutes=1)),
            _event("execution_lease_granted", invalid_grant, T0 + timedelta(minutes=2)),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[
            _verified("execution_lease_granted", old_grant),
            _verified("execution_lease_granted", invalid_grant),
        ],
    )
    by_id = {row["lease_id"]: row for row in invalid_projection["leases"]}
    assert by_id[LEASE_A]["status"] == "active"
    assert by_id[LEASE_B]["status"] == "blocked_scope"

    replacement = _lease(WS_A, LEASE_B, supersedes=LEASE_A)
    replacement_grant = _grant(replacement, "approval:new")
    valid_projection = fold_execution_control(
        [
            _event("execution_lease_requested", old),
            _event("execution_lease_granted", old_grant),
            _event("execution_lease_requested", replacement, T0 + timedelta(minutes=1)),
            _event("execution_lease_granted", replacement_grant, T0 + timedelta(minutes=2)),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[
            _verified("execution_lease_granted", old_grant),
            _verified(
                "execution_lease_granted",
                replacement_grant,
                at=T0 + timedelta(minutes=2),
            ),
        ],
    )
    by_id = {row["lease_id"]: row for row in valid_projection["leases"]}
    assert by_id[LEASE_A]["status"] == "superseded"
    assert by_id[LEASE_B]["status"] == "active"


def test_fold_problems_and_overlong_interval_block_authority() -> None:
    lease = _lease(WS_A, LEASE_A, expires_at=T0 + timedelta(days=32))
    grant = _grant(lease, "approval:lease")
    overlong = fold_execution_control(
        [
            _event("execution_lease_requested", lease),
            _event("execution_lease_granted", grant),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[_verified("execution_lease_granted", grant)],
    )
    assert overlong["leases"][0]["status"] == "blocked_interval"

    normal = _lease(WS_A, LEASE_A)
    normal_grant = _grant(normal, "approval:normal")
    fold_problem = fold_execution_control(
        [
            _event("execution_lease_requested", normal),
            _event("execution_lease_granted", normal_grant),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[_verified("execution_lease_granted", normal_grant)],
        ledger_diagnostics={"fold_problems": ["binding fold uncertain"]},
    )
    assert fold_problem["leases"][0]["status"] == "blocked_ledger_integrity"


def test_reconciliation_cannot_claim_outcome_without_attempt_journal() -> None:
    lease = _lease(WS_A, LEASE_A)
    dispatch = _dispatch(lease)
    reconciliation = {
        "workstream_id": WS_A,
        "dispatch_revision_id": DISPATCH_A,
        "attempt_id": "attempt:synthetic:1",
        "dispatch_scope_digest": dispatch["scope_digest"],
        "observed_disposition": "succeeded",
        "evidence_refs": ["test:synthetic"],
        "decided_by": "human:reviewer",
        "approval_id": "approval:reconcile",
    }
    projection = fold_execution_control(
        [
            _event("dispatch_intent_proposed", dispatch),
            _event("dispatch_reconciliation_recorded", reconciliation),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[_verified("dispatch_reconciliation_recorded", reconciliation)],
    )
    row = projection["dispatches"][0]
    assert row["status"] == "reconciliation_pending_attempt_journal"
    assert row["authorization_valid"] is False
    assert row["dispatch_allowed"] is False


def test_traversal_paths_are_blocked_when_events_bypass_writer_helpers() -> None:
    invalid_lease = _lease(WS_A, LEASE_A, paths=("../outside",))
    invalid_grant = _grant(invalid_lease, "approval:invalid-path")
    lease_projection = fold_execution_control(
        [
            _event("execution_lease_requested", invalid_lease),
            _event("execution_lease_granted", invalid_grant),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[_verified("execution_lease_granted", invalid_grant)],
    )
    assert lease_projection["leases"][0]["status"] == "blocked_scope"
    assert any(
        item.startswith("lease_invalid_requested_paths:")
        for item in lease_projection["diagnostics"]
    )

    valid_lease = _lease(WS_A, LEASE_A)
    valid_grant = _grant(valid_lease, "approval:valid-path")
    invalid_dispatch = _dispatch(valid_lease, paths=("../outside",))
    dispatch_approval = _approval(invalid_dispatch, valid_lease, "approval:invalid-dispatch-path")
    dispatch_projection = fold_execution_control(
        [
            _event("execution_lease_requested", valid_lease),
            _event("execution_lease_granted", valid_grant),
            _event("dispatch_intent_proposed", invalid_dispatch),
            _event("dispatch_intent_approved", dispatch_approval),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[
            _verified("execution_lease_granted", valid_grant),
            _verified("dispatch_intent_approved", dispatch_approval),
        ],
    )
    row = dispatch_projection["dispatches"][0]
    assert row["status"] == "blocked_scope"
    assert row["authorization_valid"] is False
    assert any(
        "dispatch_invalid_requested_paths:" in item for item in dispatch_projection["diagnostics"]
    )


def test_repo_root_scope_allows_nested_dispatch_paths() -> None:
    lease = _lease(WS_A, LEASE_A, paths=(".",))
    grant = _grant(lease, "approval:root-lease")
    dispatch = _dispatch(lease, paths=("src/module.py",))
    approval = _approval(dispatch, lease, "approval:root-dispatch")
    projection = fold_execution_control(
        [
            _event("execution_lease_requested", lease),
            _event("execution_lease_granted", grant),
            _event("dispatch_intent_proposed", dispatch),
            _event("dispatch_intent_approved", approval),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[
            _verified("execution_lease_granted", grant),
            _verified("dispatch_intent_approved", approval),
        ],
    )
    assert projection["dispatches"][0]["status"] == "ready_manual"
    assert projection["dispatches"][0]["dispatch_allowed"] is False


def test_multiple_active_successors_require_a_human_choice() -> None:
    lease_c = "dad:portfolio-lease:00000000-0000-0000-0000-000000000003"
    old = _lease(WS_A, LEASE_A)
    first = _lease(WS_A, LEASE_B, supersedes=LEASE_A)
    second = _lease(WS_A, lease_c, supersedes=LEASE_A)
    old_grant = _grant(old, "approval:branch-old")
    first_grant = _grant(first, "approval:branch-first")
    second_grant = _grant(second, "approval:branch-second")
    projection = fold_execution_control(
        [
            _event("execution_lease_requested", old),
            _event("execution_lease_granted", old_grant),
            _event("execution_lease_requested", first, T0 + timedelta(minutes=1)),
            _event("execution_lease_granted", first_grant, T0 + timedelta(minutes=2)),
            _event("execution_lease_requested", second, T0 + timedelta(minutes=1)),
            _event("execution_lease_granted", second_grant, T0 + timedelta(minutes=2)),
        ],
        [_workstream(WS_A, "binding:repo")],
        as_of=T0 + timedelta(hours=1),
        verified_approval_records=[
            _verified("execution_lease_granted", old_grant),
            _verified(
                "execution_lease_granted",
                first_grant,
                at=T0 + timedelta(minutes=2),
            ),
            _verified(
                "execution_lease_granted",
                second_grant,
                at=T0 + timedelta(minutes=2),
            ),
        ],
    )
    by_id = {row["lease_id"]: row for row in projection["leases"]}
    assert by_id[LEASE_A]["status"] == "active"
    assert by_id[LEASE_B]["status"] == "blocked_supersession_conflict"
    assert by_id[lease_c]["status"] == "blocked_supersession_conflict"
