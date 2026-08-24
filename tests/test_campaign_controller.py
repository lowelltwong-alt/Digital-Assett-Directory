from __future__ import annotations

import ast
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil

import pytest

import digital_asset_directory.campaign_codex_shell_adapter as shell_adapter

from digital_asset_directory.campaign_codex_shell_adapter import (
    assert_no_execution_effect,
    build_execution_evidence_snapshot,
    build_local_host_snapshot,
    prepare_dry_run,
    prepare_shutdown,
)
from digital_asset_directory.campaign_controller import (
    AUTHORIZATION_SCHEMA,
    EVIDENCE_SNAPSHOT_SCHEMA,
    build_campaign_dry_run,
    build_execution_control_binding_candidate,
    canonical_digest,
    evidence_snapshot_digest,
    file_digest,
    flatten_campaign_jobs,
    load_campaign_manifest,
    reconcile_campaign_budget,
    required_authorization_effects,
    validate_campaign_state,
)
from digital_asset_directory.portfolio_execution import CAMPAIGN_BINDING_SCHEMA
from digital_asset_directory.portfolio_execution import (
    campaign_runtime_state_from_projection,
)


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "docs/campaigns/dad-high-value-recovery/campaign.json"
DECISION = (
    ROOT
    / "docs/campaigns/dad-high-value-recovery/checks/evidence/decision/"
    "human-decision-receipt.json"
)


def _manifest() -> dict:
    return load_campaign_manifest(CAMPAIGN)


def _observed_source_revision(manifest: dict) -> str:
    return canonical_digest(
        {
            "manifest_digest": file_digest(CAMPAIGN),
            "source_authority": {
                row["path"]: file_digest(ROOT / row["path"])
                for row in manifest["source_authority"]
            },
        }
    )


def test_manifest_flattens_all_atomic_children_without_cohort_lease() -> None:
    jobs = flatten_campaign_jobs(_manifest())
    children = [job for job in jobs.values() if job.get("is_atomic_child")]
    assert len(children) == 70
    assert len(jobs) == 85
    assert all(child["lease_minutes"] == 90 for child in children)
    assert all(child["heartbeat_minutes"] == 15 for child in children)
    assert jobs["J-510"]["case_execution"]["parent_semantics"] == (
        "cohort-reconciliation-gate-only"
    )


def test_prelaunch_dry_run_is_blocked_by_non_execution_authorization_and_has_zero_effects() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    result = build_campaign_dry_run(ROOT, _manifest(), "J-100", decision)
    assert result["status"] == "blocked"
    assert {
        "human_authorization_schema_invalid",
        "human_authorization_not_active",
    }.issubset(result["packet"]["readiness"]["reason_codes"])
    assert set(result["effects"].values()) == {0}
    assert result["dispatch_allowed"] is False
    assert result["execution_authorized"] is False

    decision["prohibited_effects"] = []
    still_blocked = build_campaign_dry_run(ROOT, _manifest(), "J-100", decision)
    assert still_blocked["status"] == "blocked"
    assert "human_authorization_schema_invalid" in still_blocked["packet"][
        "readiness"
    ]["reason_codes"]


def _authorization(manifest: dict, now: datetime) -> dict:
    return {
        "schema_version": AUTHORIZATION_SCHEMA,
        "status": "authorized",
        "authorization_id": "test-only-positive-authorization",
        "portfolio_approval_refs": {
            "lease_approval_id": "test-lease-approval",
            "dispatch_approval_id": "test-dispatch-approval",
        },
        "campaign_id": manifest["campaign_id"],
        "campaign_revision": manifest["revision"],
        "manifest_digest": file_digest(CAMPAIGN),
        "job_id": "J-100",
        "approved_effects": required_authorization_effects(manifest),
        "prohibited_effects": list(manifest["authority"]["prohibited_effects"]),
        "named_approver": "Lowell",
        "approved_by": "Lowell",
        "approved_at": (now - timedelta(minutes=5)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }


def _positive_state(manifest: dict, authorization: dict, now: datetime) -> dict:
    job = flatten_campaign_jobs(manifest)["J-100"]
    manifest_digest = file_digest(CAMPAIGN)
    authorization_digest = canonical_digest(authorization)
    qualifications = {}
    for relative in job["qualification_evidence"]:
        path = ROOT / relative
        qualifications[relative] = {
            **json.loads(path.read_text(encoding="utf-8")),
            "digest": file_digest(path),
        }
    snapshot_material = {
        "schema_version": EVIDENCE_SNAPSHOT_SCHEMA,
        "campaign_id": manifest["campaign_id"],
        "campaign_revision": manifest["revision"],
        "manifest_digest": manifest_digest,
        "job_id": "J-100",
        "authorization_id": authorization["authorization_id"],
        "named_approver": authorization["named_approver"],
        "authorization_receipt_digest": authorization_digest,
        "authority_approval_ids": authorization["portfolio_approval_refs"],
        "campaign_budget_attempts": [],
        "budget_receipt_digests": {},
        "source_revision": _observed_source_revision(manifest),
        "resolved_input_digests": dict(job["input_digests"]),
        "dependency_receipts": {},
        "qualification_evidence": qualifications,
        "durability_verifier_digest": file_digest(
            ROOT
            / "docs/campaigns/dad-high-value-recovery/checks/verify_receipt_durability.py"
        ),
        "adapter_revision": manifest["execution"]["adapter"]["revision"],
        "observed_paths": [],
        "observed_effects": [],
        "observed_at": now.isoformat(),
        "verification_errors": [],
        "authority_boundary": "test-only inert evidence",
    }
    snapshot = {
        **snapshot_material,
        "snapshot_digest": evidence_snapshot_digest(snapshot_material),
    }
    state = {
        "attempts": [],
        "issued_packets": [],
        "requested_paths": [],
        "requested_effects": [],
        "budget_evidence_complete": True,
        "evidence_snapshot": snapshot,
        "campaign_binding": {},
        "execution_control": {
            "executor": {"available": False, "dispatch_allowed": False},
            "leases": [],
            "dispatches": [],
        },
    }
    first = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        authorization,
        state=state,
        authorization_receipt_digest=authorization_digest,
        as_of=now,
    )
    packet = first["packet"]
    binding = {
        "schema_version": CAMPAIGN_BINDING_SCHEMA,
        "campaign_id": packet["campaign_id"],
        "campaign_revision": packet["campaign_revision"],
        "manifest_digest": packet["manifest_digest"],
        "job_id": packet["job_id"],
        "packet_digest": packet["packet_digest"],
        "source_revision": packet["source_revision"],
        "authorization_id": packet["authorization_id"],
        "named_approver": packet["named_approver"],
        "authorization_receipt_digest": packet["authorization_receipt_digest"],
        "authority_approval_ids": packet["authority_approval_ids"],
        "budget_receipt_digests": packet["budget_receipt_digests"],
        "input_digests": packet["input_digests"],
        "dependency_receipt_digests": packet["dependency_receipt_digests"],
        "qualification_evidence_digests": packet["qualification_evidence_digests"],
        "idempotency_key": packet["idempotency_key"],
        "worker_revision_id": packet["worker_revision_id"],
        "checker_revision_id": packet["checker_revision_id"],
        "action_class": packet["action_class"],
        "lease_minutes": packet["lease_minutes"],
        "output_paths": packet["output_paths"],
        "acceptance_evidence_paths": packet["acceptance_evidence_paths"],
        "checkpoint_path": packet["checkpoint"],
        "receipt_path": packet["receipt"],
        "allowed_paths": packet["allowed_paths"],
        "allowed_effects": packet["allowed_effects"],
        "campaign_budget_digest": packet["campaign_budget_digest"],
        "job_budget_digest": packet["job_budget_digest"],
        "durability_verifier_digest": packet["durability_verifier_digest"],
        "evidence_snapshot_digest": packet["evidence_snapshot_digest"],
        "adapter_revision": packet["adapter_revision"],
        "heartbeat_at": now.isoformat(),
        "heartbeat_minutes": job["heartbeat_minutes"],
        "repair_attempt": 0,
        "max_repairs": job["repair_limit"],
        "reissue_of_attempt_id": "",
        "prior_reconciliation_digest": "",
        "partial_effects_reconciled": True,
    }
    lease = {
        "lease_id": "dad:portfolio-lease:00000000-0000-0000-0000-000000000001",
        "status": "active",
        "authorization_valid": True,
        "requested_paths": list(packet["allowed_paths"]),
        "action_classes": [packet["action_class"]],
        "owner_id": packet["worker_revision_id"],
        "grant": {
            "approval_id": "test-lease-approval",
            "granted_by": authorization["named_approver"],
        },
        "not_before": now.isoformat(),
        "expires_at": (now + timedelta(minutes=job["lease_minutes"])).isoformat(),
        "campaign_binding": binding,
    }
    dispatch = {
        "lease_id": lease["lease_id"],
        "status": "ready_manual",
        "authorization_valid": True,
        "manual_packet_ready": True,
        "dispatch_allowed": False,
        "requested_paths": list(packet["allowed_paths"]),
        "action": packet["action_class"],
        "worker_revision_id": packet["worker_revision_id"],
        "checker_revision_id": packet["checker_revision_id"],
        "acceptance_refs": packet["acceptance_evidence_paths"],
        "expected_repo_snapshot": packet["source_revision"],
        "authority_refs": sorted(
            [
                authorization["authorization_id"],
                authorization_digest,
                authorization["portfolio_approval_refs"]["lease_approval_id"],
                authorization["portfolio_approval_refs"]["dispatch_approval_id"],
            ]
        ),
        "approval": {
            "approval_id": "test-dispatch-approval",
            "approved_by": authorization["named_approver"],
        },
        "campaign_binding": binding,
    }
    state["campaign_binding"] = binding
    state["execution_control"] = {
        "executor": {"available": False, "dispatch_allowed": False},
        "ledger_diagnostics": {},
        "attempt_journal": {"ledger_diagnostics": {}},
        "leases": [lease],
        "dispatches": [dispatch],
    }
    return state


def test_exact_positive_control_evidence_can_only_yield_ready_manual() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    state = _positive_state(manifest, authorization, now)
    result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        authorization,
        state=state,
        authorization_receipt_digest=canonical_digest(authorization),
        as_of=now,
    )
    assert result["status"] == "ready-manual", result["packet"]["readiness"][
        "reason_codes"
    ]
    assert result["packet"]["readiness"]["manual_packet_ready"] is True
    assert result["execution_authorized"] is False
    assert result["dispatch_allowed"] is False
    assert set(result["effects"].values()) == {0}


def test_stale_heartbeat_or_qualification_blocks_ready_manual() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    state = _positive_state(manifest, authorization, now)
    stale_binding = {
        **state["campaign_binding"],
        "heartbeat_at": (now - timedelta(hours=1)).isoformat(),
    }
    state["campaign_binding"] = stale_binding
    state["execution_control"]["leases"][0]["campaign_binding"] = stale_binding
    state["execution_control"]["dispatches"][0]["campaign_binding"] = stale_binding
    result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        authorization,
        state=state,
        authorization_receipt_digest=canonical_digest(authorization),
        as_of=now,
    )
    assert result["status"] == "blocked"
    assert "campaign_heartbeat_stale" in result["packet"]["readiness"]["reason_codes"]

    state = _positive_state(manifest, authorization, now)
    first = next(iter(state["evidence_snapshot"]["qualification_evidence"].values()))
    first["status"] = "expired"
    material = dict(state["evidence_snapshot"])
    material.pop("snapshot_digest")
    state["evidence_snapshot"]["snapshot_digest"] = evidence_snapshot_digest(
        material
    )
    result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        authorization,
        state=state,
        authorization_receipt_digest=canonical_digest(authorization),
        as_of=now,
    )
    assert result["status"] == "blocked"
    assert any(
        reason.startswith("qualification_invalid:")
        for reason in result["packet"]["readiness"]["reason_codes"]
    )


def test_existing_idempotency_key_blocks_reissue_even_for_same_packet() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    state = _positive_state(manifest, authorization, now)
    state["execution_control"]["dispatches"][0]["dry_run_attempt"] = {
        "selected_attempt_id": "dad:portfolio-attempt:00000000-0000-0000-0000-000000000001"
    }
    result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        authorization,
        state=state,
        authorization_receipt_digest=canonical_digest(authorization),
        as_of=now,
    )
    assert result["status"] == "blocked"
    assert "idempotent_packet_already_issued" in result["packet"]["readiness"][
        "reason_codes"
    ]


def test_paths_effects_budgets_stop_and_reissue_all_fail_closed() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    authorization_digest = canonical_digest(authorization)
    baseline = _positive_state(manifest, authorization, now)

    def reasons(state: dict) -> set[str]:
        result = build_campaign_dry_run(
            ROOT,
            manifest,
            "J-100",
            authorization,
            state=state,
            authorization_receipt_digest=authorization_digest,
            as_of=now,
        )
        assert result["status"] == "blocked"
        return set(result["packet"]["readiness"]["reason_codes"])

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["requested_paths"] = [
        "outside/authorized-job.txt"
    ]
    assert "requested_path_outside_job_scope" in reasons(state)

    state = deepcopy(baseline)
    effect_binding = {**state["campaign_binding"], "allowed_effects": ["deploy"]}
    state["campaign_binding"] = effect_binding
    state["execution_control"]["leases"][0]["campaign_binding"] = effect_binding
    state["execution_control"]["dispatches"][0]["campaign_binding"] = effect_binding
    assert "requested_effect_outside_authorization" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["dry_run_attempt"] = {
        "selected_attempt_id": "dad:portfolio-attempt:00000000-0000-0000-0000-000000000002"
    }
    assert "portfolio_budget_evidence_incomplete" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["leases"][0]["status"] = "revoked"
    state["execution_control"]["leases"][0]["authorization_valid"] = False
    assert "stop_transition_active" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["executor"]["dispatch_allowed"] = True
    assert "portfolio_executor_boundary_invalid" in reasons(state)

    state = deepcopy(baseline)
    reconciliation = "sha256:" + "9" * 64
    binding = {
        **state["campaign_binding"],
        "repair_attempt": 1,
        "reissue_of_attempt_id": "J-100:attempt:1",
        "prior_reconciliation_digest": reconciliation,
    }
    state["campaign_binding"] = binding
    state["execution_control"]["leases"][0]["campaign_binding"] = binding
    state["execution_control"]["dispatches"][0]["campaign_binding"] = binding
    state["execution_control"]["dispatches"][0]["dry_run_attempt"] = {
        "selected_attempt_id": "J-100:attempt:1"
    }
    state["execution_control"]["dispatches"][0]["reconciliation"] = {
        "attempt_id": "J-100:attempt:1"
    }
    assert "prior_attempt_reconciliation_missing" in reasons(state)


def test_portfolio_scope_identity_and_verified_approval_refs_are_exact() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    authorization_digest = canonical_digest(authorization)
    baseline = _positive_state(manifest, authorization, now)

    def reasons(state: dict) -> set[str]:
        result = build_campaign_dry_run(
            ROOT,
            manifest,
            "J-100",
            authorization,
            state=state,
            authorization_receipt_digest=authorization_digest,
            as_of=now,
        )
        assert result["status"] == "blocked"
        return set(result["packet"]["readiness"]["reason_codes"])

    state = deepcopy(baseline)
    state["execution_control"]["leases"][0]["requested_paths"].append("extra.txt")
    assert "campaign_lease_paths_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["action"] = "validate"
    assert "campaign_dispatch_action_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["acceptance_refs"] = [
        "wrong-evidence.json"
    ]
    assert "campaign_dispatch_acceptance_scope_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["worker_revision_id"] = (
        "different-worker:r1"
    )
    assert "campaign_dispatch_worker_identity_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["approval"]["approval_id"] = (
        "unverified-substitute"
    )
    assert "campaign_dispatch_approval_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["approval"]["approved_by"] = (
        "different-trusted-actor"
    )
    assert "campaign_dispatch_approver_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["expected_repo_snapshot"] = (
        "sha256:" + "0" * 64
    )
    assert "campaign_dispatch_source_snapshot_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["dispatches"][0]["authority_refs"] = [
        authorization["authorization_id"]
    ]
    assert "campaign_dispatch_authority_refs_mismatch" in reasons(state)

    state = deepcopy(baseline)
    state["execution_control"]["leases"][0]["expires_at"] = (
        now + timedelta(minutes=91)
    ).isoformat()
    assert "campaign_lease_interval_mismatch" in reasons(state)


def test_packet_binds_outputs_acceptance_and_distinct_qualified_identities() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    state = _positive_state(manifest, authorization, now)
    result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        authorization,
        state=state,
        authorization_receipt_digest=canonical_digest(authorization),
        as_of=now,
    )
    packet = result["packet"]
    job = flatten_campaign_jobs(manifest)["J-100"]
    assert packet["output_paths"] == sorted(job["outputs"])
    assert packet["acceptance_evidence_paths"] == sorted(
        row["evidence"] for row in job["acceptance"]
    )
    assert packet["worker_revision_id"] != packet["checker_revision_id"]


def test_self_asserted_authorization_without_portfolio_refs_is_blocked() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    state = _positive_state(manifest, authorization, now)
    del authorization["portfolio_approval_refs"]
    result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        authorization,
        state=state,
        authorization_receipt_digest=canonical_digest(authorization),
        as_of=now,
    )
    assert result["status"] == "blocked"
    assert "human_authorization_portfolio_refs_invalid" in result["packet"][
        "readiness"
    ]["reason_codes"]


def test_source_revision_is_measured_and_false_expected_digest_blocks() -> None:
    manifest = _manifest()
    fake = "sha256:" + "f" * 64
    snapshot = build_execution_evidence_snapshot(
        ROOT,
        manifest,
        "J-100",
        DECISION,
        source_revision=fake,
        as_of=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
    )
    assert snapshot["source_revision"] == _observed_source_revision(manifest)
    assert snapshot["source_revision"] != fake
    assert "source-revision-expected-mismatch" in snapshot["verification_errors"]


def test_observation_time_is_nonbinding_but_must_not_be_in_the_future() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    later = now + timedelta(seconds=1)
    first = build_execution_evidence_snapshot(
        ROOT, manifest, "J-100", DECISION, as_of=now
    )
    second = build_execution_evidence_snapshot(
        ROOT, manifest, "J-100", DECISION, as_of=later
    )
    assert first["observed_at"] != second["observed_at"]
    assert first["snapshot_digest"] == second["snapshot_digest"]

    execution_control = {
        "executor": {"available": False, "dispatch_allowed": False},
        "ledger_diagnostics": {},
        "attempt_journal": {"ledger_diagnostics": {}},
        "leases": [],
        "dispatches": [],
    }
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    first_result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        decision,
        state={
            "evidence_snapshot": first,
            "campaign_binding": {},
            "execution_control": execution_control,
        },
        authorization_receipt_digest=file_digest(DECISION),
        as_of=now,
    )
    second_result = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        decision,
        state={
            "evidence_snapshot": second,
            "campaign_binding": {},
            "execution_control": execution_control,
        },
        authorization_receipt_digest=file_digest(DECISION),
        as_of=later,
    )
    assert first_result["packet"]["packet_digest"] == second_result["packet"][
        "packet_digest"
    ]

    future = {**first, "observed_at": (later + timedelta(hours=1)).isoformat()}
    blocked = build_campaign_dry_run(
        ROOT,
        manifest,
        "J-100",
        decision,
        state={
            "evidence_snapshot": future,
            "campaign_binding": {},
            "execution_control": execution_control,
        },
        authorization_receipt_digest=file_digest(DECISION),
        as_of=later,
    )
    assert "evidence_snapshot_observed_at_invalid" in blocked["packet"][
        "readiness"
    ]["reason_codes"]


def test_noncanonical_manifest_and_unresolved_atomic_child_fail_closed() -> None:
    manifest = _manifest()
    mutated = deepcopy(manifest)
    mutated["phases"][0]["waves"][0]["subwaves"][0]["jobs"][0][
        "allowed_paths"
    ].append("laundered-path.txt")
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    result = build_campaign_dry_run(ROOT, mutated, "J-100", decision)
    assert "campaign_manifest_not_canonical" in result["packet"]["readiness"][
        "reason_codes"
    ]

    child_id = next(
        job_id
        for job_id, job in flatten_campaign_jobs(manifest).items()
        if job.get("is_atomic_child")
    )
    decision["job_id"] = child_id
    child = build_campaign_dry_run(ROOT, manifest, child_id, decision)
    assert "atomic_child_execution_binding_not_implemented" in child["packet"][
        "readiness"
    ]["reason_codes"]


def test_adapter_rejects_noncanonical_manifest_path(tmp_path: Path) -> None:
    alternate = tmp_path / "campaign.json"
    alternate.write_bytes(CAMPAIGN.read_bytes())
    with pytest.raises(ValueError, match="canonical repository campaign.json"):
        prepare_dry_run(ROOT, alternate, DECISION, job_id="J-100")


def test_adapter_forwards_explicit_repo_local_attestation_to_trusted_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_load(repo_root: Path, *, as_of: datetime, attestations: list[dict]) -> dict:
        captured["repo_root"] = repo_root
        captured["attestations"] = attestations
        return {
            "executor": {"available": False, "dispatch_allowed": False},
            "ledger_diagnostics": {},
            "attempt_journal": {"ledger_diagnostics": {}},
            "leases": [],
            "dispatches": [],
        }

    monkeypatch.setattr(shell_adapter, "load_execution_control", fake_load)
    relative = DECISION.relative_to(ROOT)
    prepare_dry_run(
        ROOT,
        CAMPAIGN,
        DECISION,
        job_id="J-100",
        authority_attestation_paths=[relative],
    )
    assert captured["repo_root"] == ROOT
    assert captured["attestations"] == [
        json.loads(DECISION.read_text(encoding="utf-8"))
    ]


def test_real_adapter_reaches_ready_manual_through_signed_public_fold(
    tmp_path: Path,
) -> None:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from digital_asset_directory import portfolio_authority
    from digital_asset_directory.portfolio_events import ledger_path, read_events
    from digital_asset_directory.portfolio_execution import (
        approve_dispatch_intent,
        grant_execution_lease,
        propose_dispatch_intent,
        request_execution_lease,
    )
    from digital_asset_directory.portfolio_workstreams import (
        capture_ideas,
        record_binding,
        record_feedback,
    )

    manifest = _manifest()
    job = flatten_campaign_jobs(manifest)["J-100"]

    def copy(relative: str) -> None:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    required_paths = {
        "docs/campaigns/dad-high-value-recovery/campaign.json",
        "docs/campaigns/dad-high-value-recovery/checks/verify_receipt_durability.py",
        "registry/runtime-adapter-registry.json",
        *job["inputs"],
        *job["qualification_evidence"],
        *(row["path"] for row in manifest["source_authority"]),
    }
    for qualification in job["qualification_evidence"]:
        row = json.loads((ROOT / qualification).read_text(encoding="utf-8"))
        required_paths.update(row["source_digests"])
    for relative in sorted(required_paths):
        copy(relative)

    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    decision_path = (
        tmp_path
        / "docs/campaigns/dad-high-value-recovery/checks/evidence/decision/"
        "test-execution-authorization.json"
    )
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(json.dumps(authorization, indent=2) + "\n", encoding="utf-8")
    manifest_path = tmp_path / "docs/campaigns/dad-high-value-recovery/campaign.json"
    evidence = build_execution_evidence_snapshot(
        tmp_path, manifest, "J-100", decision_path, as_of=now
    )
    initial = build_campaign_dry_run(
        tmp_path,
        manifest,
        "J-100",
        authorization,
        state={
            "evidence_snapshot": evidence,
            "campaign_binding": {},
            "execution_control": {
                "executor": {"available": False, "dispatch_allowed": False},
                "ledger_diagnostics": {},
                "attempt_journal": {"ledger_diagnostics": {}},
                "leases": [],
                "dispatches": [],
            },
        },
        authorization_receipt_digest=file_digest(decision_path),
        as_of=now,
    )
    packet = initial["packet"]
    binding = build_execution_control_binding_candidate(
        packet,
        heartbeat_at=now,
        max_repairs=job["repair_limit"],
    )

    captured = capture_ideas(
        tmp_path,
        ["Signed revision-6 campaign bridge integration"],
        conversation_id="campaign-bridge-signed-integration",
        now=now - timedelta(minutes=10),
    )
    workstream_id = captured["proposals"][0]["workstream_id"]
    record_feedback(
        tmp_path,
        workstream_id,
        "resume",
        now=now - timedelta(minutes=9),
        command_id="campaign-bridge-resume",
    )
    repo_binding = record_binding(
        tmp_path,
        workstream_id,
        "repo",
        "repo:dad-signed-integration",
        assertion_status="accepted",
        asserted_by="Lowell",
        approval_ref="human:campaign-bridge-binding",
        now=now - timedelta(minutes=8),
        command_id="campaign-bridge-bind",
    )
    requested = request_execution_lease(
        tmp_path,
        workstream_id,
        owner_id=packet["worker_revision_id"],
        owner_kind="agent",
        repo_binding_id=repo_binding["binding_id"],
        action_classes=[packet["action_class"]],
        requested_paths=packet["allowed_paths"],
        not_before=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=85),
        return_state="paused",
        rationale_code="signed_campaign_bridge_integration",
        campaign_binding=binding,
        command_id="campaign-bridge-lease-request",
        now=now - timedelta(minutes=7),
    )
    grant_execution_lease(
        tmp_path,
        workstream_id,
        requested["lease_id"],
        granted_by="Lowell",
        approval_id=authorization["portfolio_approval_refs"]["lease_approval_id"],
        command_id="campaign-bridge-lease-grant",
        now=now - timedelta(minutes=6),
    )
    authority_refs = sorted(
        [
            authorization["authorization_id"],
            file_digest(decision_path),
            *authorization["portfolio_approval_refs"].values(),
        ]
    )
    proposed = propose_dispatch_intent(
        tmp_path,
        workstream_id,
        lease_id=requested["lease_id"],
        repo_binding_id=repo_binding["binding_id"],
        action=packet["action_class"],
        worker_revision_id=packet["worker_revision_id"],
        checker_revision_id=packet["checker_revision_id"],
        task_summary="Inert signed campaign bridge integration candidate",
        requested_paths=packet["allowed_paths"],
        acceptance_refs=packet["acceptance_evidence_paths"],
        validation_commands=["python -m pytest tests/test_campaign_controller.py"],
        authority_refs=authority_refs,
        expected_repo_snapshot=packet["source_revision"],
        campaign_binding=binding,
        command_id="campaign-bridge-dispatch-propose",
        now=now - timedelta(minutes=5),
    )
    approve_dispatch_intent(
        tmp_path,
        workstream_id,
        proposed["dispatch_revision_id"],
        approved_by="Lowell",
        approval_id=authorization["portfolio_approval_refs"]["dispatch_approval_id"],
        expires_at=now + timedelta(minutes=60),
        command_id="campaign-bridge-dispatch-approve",
        now=now - timedelta(minutes=4),
    )

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    registry = {
        "schema_version": "dad.portfolio_approval_trust_registry.v1",
        "registry_id": "dad:registry:portfolio-approval-trust",
        "registry_sequence": 1,
        "previous_registry_digest": "",
        "root_anchor_status": "unanchored_shadow",
        "status": "reviewed_shadow_active",
        "authority_boundary": "Test-only reviewed unanchored shadow trust.",
        "keys": [
            {
                "key_id": portfolio_authority.approval_key_id(public_key),
                "algorithm": "ed25519",
                "public_key_base64": encode(public_key),
                "authority_domain": "dad.campaign.test",
                "approver_ids": ["Lowell"],
                "allowed_event_kinds": [
                    "execution_lease_granted",
                    "dispatch_intent_approved",
                ],
                "valid_from": (now - timedelta(days=1)).isoformat(),
                "valid_until": (now + timedelta(days=1)).isoformat(),
                "revoked_at": None,
                "key_status": "active",
                "review_status": "reviewed",
                "authority_refs": ["test:campaign-bridge-human-review"],
            }
        ],
    }
    trust_path = tmp_path / "registry/portfolio-approval-trust-registry.json"
    trust_path.parent.mkdir(parents=True, exist_ok=True)
    trust_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    events, diagnostics = read_events(ledger_path(tmp_path))
    assert diagnostics["problems"] == []
    approval_events = [
        event
        for event in events
        if event["event_kind"]
        in {"execution_lease_granted", "dispatch_intent_approved"}
    ]
    attestation_paths: list[Path] = []
    for index, event in enumerate(approval_events, start=1):
        attestation = {
            "schema_version": "dad.portfolio_approval_attestation.v1",
            "authority_context": "dad.portfolio_execution_authority.v1",
            "signature_algorithm": "ed25519",
            "canonicalization": "dad-ascii-json.v1",
            "digest_algorithm": "sha256",
            "audience": "dad.portfolio.execution-control",
            "execution_mode": "dry_run",
            "trust_registry_digest": portfolio_authority.trust_registry_digest(registry),
            "attestation_id": f"dad:portfolio-attestation:00000000-0000-0000-0000-{index:012d}",
            "approval_id": event["payload"]["approval_id"],
            "authority_domain": "dad.campaign.test",
            "event_id": event["event_id"],
            "event_kind": event["event_kind"],
            "event_digest": portfolio_authority.authority_event_digest(event),
            "event_schema_version": event["schema_version"],
            "stream_id": event["stream_id"],
            "prev_event_id": event["prev_event_id"],
            "command_id": event["command_id"],
            "event_recorded_at": event["recorded_at"],
            "key_id": registry["keys"][0]["key_id"],
            "approver_id": "Lowell",
            "issued_at": (now - timedelta(minutes=3)).isoformat(),
            "not_before": (now - timedelta(minutes=5)).isoformat(),
            "expires_at": (now + timedelta(minutes=60)).isoformat(),
            "nonce": f"campaign-bridge-{index:04d}",
            "signature": "pending",
        }
        attestation["signature"] = encode(
            private_key.sign(
                portfolio_authority.canonical_attestation_bytes(attestation)
            )
        )
        relative = Path(f"checks/authority-attestation-{index}.json")
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(attestation, indent=2) + "\n", encoding="utf-8")
        attestation_paths.append(relative)

    result = prepare_dry_run(
        tmp_path,
        manifest_path,
        decision_path,
        job_id="J-100",
        authority_attestation_paths=attestation_paths,
        as_of=now,
    )
    assert result["status"] == "ready-manual", result["packet"]["readiness"][
        "reason_codes"
    ]
    assert result["packet"]["packet_digest"] == packet["packet_digest"]
    assert result["packet"]["readiness"]["manual_packet_ready"] is True
    assert result["execution_authorized"] is False
    assert result["dispatch_allowed"] is False
    assert set(result["effects"].values()) == {0}


def test_runtime_state_comes_from_existing_portfolio_projection() -> None:
    manifest = _manifest()
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    authorization = _authorization(manifest, now)
    state = _positive_state(manifest, authorization, now)
    binding = state["campaign_binding"]
    projection = deepcopy(state["execution_control"])
    projection["ledger_diagnostics"] = {}
    projection["attempt_journal"] = {"ledger_diagnostics": {}}
    projection["dispatches"][0]["dry_run_attempt"] = {
        "selected_attempt_id": "dad:portfolio-attempt:00000000-0000-0000-0000-000000000001"
    }
    runtime = campaign_runtime_state_from_projection(
        projection,
        campaign_id=manifest["campaign_id"],
        campaign_revision=manifest["revision"],
        job_id="J-100",
        campaign_binding=binding,
    )
    assert runtime["attempts"][0]["job_id"] == "J-100"
    assert runtime["issued_packets"] == [
        {
            "idempotency_key": binding["idempotency_key"],
            "packet_digest": binding["packet_digest"],
        }
    ]
    assert runtime["requested_paths"] == binding["allowed_paths"]
    assert runtime["requested_effects"] == binding["allowed_effects"]
    assert runtime["budget_evidence_complete"] is False
    measured = campaign_runtime_state_from_projection(
        projection,
        campaign_id=manifest["campaign_id"],
        campaign_revision=manifest["revision"],
        job_id="J-100",
        campaign_binding=binding,
        durable_attempts=[
            {
                "job_id": "J-100",
                "attempt_id": runtime["attempts"][0]["attempt_id"],
                "attempt_count": 1,
                "cost_units": 1,
                "wall_seconds": 30,
                "context_tokens": 100,
                "output_mb": 0.25,
                "budget_evidence_complete": True,
            }
        ],
    )
    assert measured["budget_evidence_complete"] is True
    assert measured["attempts"][0]["cost_units"] == 1


def test_budget_and_state_fail_closed_before_packet_issue() -> None:
    manifest = _manifest()
    budget = reconcile_campaign_budget(
        manifest,
        {
            "attempts": [
                {
                    "attempt_count": manifest["budgets"]["max_attempts_total"],
                    "cost_units": 0,
                    "output_mb": 0,
                }
            ]
        },
    )
    assert budget.within_budget is False
    assert budget.reason_codes == ("attempt_budget_exhausted",)

    errors = validate_campaign_state(
        manifest,
        {
            "leases": [
                {"job_id": "J-100", "state": "active"},
                {"job_id": "J-110", "state": "active"},
            ],
            "issued_packets": [
                {"idempotency_key": "same", "packet_digest": "sha256:" + "1" * 64},
                {"idempotency_key": "same", "packet_digest": "sha256:" + "2" * 64},
            ],
        },
    )
    assert errors == ["idempotency_conflict", "parallel_lease_limit_exceeded"]


def test_codex_adapter_is_registered_inert_and_shutdown_is_projection_only() -> None:
    snapshot = build_local_host_snapshot(ROOT)
    assert snapshot["adapter_id"] == "adapter:codex-host"
    assert snapshot["execution_authorized"] is False
    assert snapshot["launch_available"] is False

    dry_run = prepare_dry_run(ROOT, CAMPAIGN, DECISION, job_id="J-100")
    assert_no_execution_effect(dry_run)
    assert dry_run["adapter"]["execution_authorized"] is False

    shutdown = prepare_shutdown(CAMPAIGN, reason_code="qualification-test")
    assert shutdown["checkpoint_write_performed"] is False
    assert shutdown["successors_blocked"] is True
    assert shutdown["execution_authorized"] is False
    assert shutdown["partial_effect_reconciliation_required"] is True


@pytest.mark.parametrize(
    "relative",
    [
        "src/digital_asset_directory/campaign_controller.py",
        "src/digital_asset_directory/campaign_codex_shell_adapter.py",
    ],
)
def test_controller_modules_have_no_execution_or_network_import(relative: str) -> None:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (
            node.names
            if isinstance(node, ast.Import)
            else [ast.alias(name=str(node.module or ""))]
        )
    }
    assert imported.isdisjoint(
        {"subprocess", "socket", "requests", "httpx", "urllib", "git", "openai"}
    )
