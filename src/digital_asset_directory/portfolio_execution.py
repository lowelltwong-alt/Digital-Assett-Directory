"""Guarded public execution-control facade for the Portfolio OS.

The established fold remains in a private compatibility module. The public
boundary accepts raw attestations only through ``load_execution_control`` and
recomputes them against the fixed repository trust path. No public fold accepts
a caller-supplied verifier result, raw verified dictionary, or bare approval ID.
Every dispatch flag remains false, and no source repository is mutated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import _portfolio_execution_legacy as _legacy
from .portfolio_attempts import annotate_execution_projection, load_attempt_projection
from .portfolio_authority import (
    VerifiedApprovals,
    authority_event_digest,
    load_trust_registry,
    verify_approval_attestations,
    _verified_event_keys,
)

ACTION_CLASSES = _legacy.ACTION_CLASSES
AUTHORITY_BOUNDARY = _legacy.AUTHORITY_BOUNDARY
DEFAULT_FORBIDDEN_ACTIONS = _legacy.DEFAULT_FORBIDDEN_ACTIONS
MAX_LEASE_DURATION = _legacy.MAX_LEASE_DURATION
OWNER_KINDS = _legacy.OWNER_KINDS
SCHEMA_VERSION = _legacy.SCHEMA_VERSION

approve_dispatch_intent = _legacy.approve_dispatch_intent
authority_attestation_digest = _legacy.authority_attestation_digest
dispatch_packet = _legacy.dispatch_packet
dispatch_scope_digest = _legacy.dispatch_scope_digest
grant_execution_lease = _legacy.grant_execution_lease
lease_scope_digest = _legacy.lease_scope_digest
propose_dispatch_intent = _legacy.propose_dispatch_intent
revoke_dispatch_intent = _legacy.revoke_dispatch_intent
revoke_execution_lease = _legacy.revoke_execution_lease
write_execution_control_outputs = _legacy.write_execution_control_outputs

CAMPAIGN_BINDING_SCHEMA = "dad.campaign.execution_control_binding.v1"


def request_execution_lease(
    hub_root: Path,
    *args: Any,
    portability_artifact_ids: Iterable[str] = (),
    **kwargs: Any,
) -> dict[str, Any]:
    """Request a lease only after any applicable portability disposition passes.

    Repositories without the portability control plane retain the legacy
    behavior. Once the registry exists, governed paths fail closed unless the
    caller binds the request to exact, known artifact identities.
    """

    registry = hub_root / "registry" / "portable-capability-registry.json"
    if registry.exists():
        from .portability_control import assess_lifecycle

        assessment = assess_lifecycle(
            hub_root,
            stage="implementation_lease",
            task=str(kwargs.get("rationale_code", "")),
            paths=kwargs.get("requested_paths", ()),
            artifact_ids=portability_artifact_ids,
            protected_transition=True,
        )
        if assessment["gate_outcome"] == "block":
            return {
                "status": "portability_disposition_required",
                "events_appended": 0,
                "assessment_id": assessment["assessment_id"],
                "finding_codes": assessment["finding_codes"],
                "execution_authorized": False,
            }
        kwargs["portability_assessment_id"] = assessment["assessment_id"]
        kwargs["portability_artifact_ids"] = assessment["bound_artifact_ids"]
        kwargs["portability_scope_digest"] = assessment["requested_scope_digest"]
    return _legacy.request_execution_lease(hub_root, *args, **kwargs)


def _now(value: datetime | None) -> datetime:
    observed = value or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return observed.astimezone(timezone.utc)


def validate_campaign_execution_control(
    projection: Mapping[str, Any],
    campaign_binding: Mapping[str, Any],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Qualify one campaign binding against the existing deny-all authority fold.

    This is a pure bridge.  A successful result means only that one exact
    Portfolio OS manual packet candidate is current; it never changes the
    public executor boundary or authorizes a dispatch.
    """

    observed = _now(as_of)
    reasons: list[str] = []
    binding = dict(campaign_binding)
    authority_approval_ids = binding.get("authority_approval_ids", {})
    if not isinstance(authority_approval_ids, Mapping):
        authority_approval_ids = {}
    if binding.get("schema_version") != CAMPAIGN_BINDING_SCHEMA:
        reasons.append("campaign_binding_schema_invalid")

    executor = projection.get("executor", {})
    if not isinstance(executor, Mapping) or executor.get("dispatch_allowed") is not False:
        reasons.append("portfolio_executor_boundary_invalid")

    leases = [row for row in projection.get("leases", []) if isinstance(row, Mapping)]
    dispatches = [
        row for row in projection.get("dispatches", []) if isinstance(row, Mapping)
    ]
    campaign_id = binding.get("campaign_id")
    job_id = binding.get("job_id")

    def same_subject(row: Mapping[str, Any]) -> bool:
        row_binding = row.get("campaign_binding")
        return (
            isinstance(row_binding, Mapping)
            and row_binding.get("campaign_id") == campaign_id
            and row_binding.get("job_id") == job_id
        )

    subject_active = [
        row for row in leases if same_subject(row) and row.get("status") == "active"
    ]
    exact_leases = [
        row
        for row in subject_active
        if dict(row.get("campaign_binding", {})) == binding
    ]
    if len(subject_active) != 1:
        reasons.append("campaign_lease_count_invalid")
    if len(exact_leases) != 1:
        reasons.append("campaign_lease_binding_missing")

    exact_dispatches = [
        row
        for row in dispatches
        if same_subject(row) and dict(row.get("campaign_binding", {})) == binding
    ]
    if len(exact_dispatches) != 1:
        reasons.append("campaign_dispatch_binding_missing")

    lease = exact_leases[0] if len(exact_leases) == 1 else None
    dispatch = exact_dispatches[0] if len(exact_dispatches) == 1 else None
    if lease is not None:
        if lease.get("authorization_valid") is not True or lease.get("status") != "active":
            reasons.append("campaign_lease_not_active")
        try:
            heartbeat = datetime.fromisoformat(
                str(binding.get("heartbeat_at", "")).replace("Z", "+00:00")
            )
            if heartbeat.tzinfo is None:
                raise ValueError
            heartbeat = heartbeat.astimezone(timezone.utc)
            heartbeat_minutes = int(binding.get("heartbeat_minutes", 0))
        except (TypeError, ValueError):
            reasons.append("campaign_heartbeat_invalid")
        else:
            if (
                heartbeat_minutes < 1
                or heartbeat > observed
                or observed - heartbeat > timedelta(minutes=heartbeat_minutes)
            ):
                reasons.append("campaign_heartbeat_stale")
        if sorted(lease.get("requested_paths", [])) != sorted(
            binding.get("allowed_paths", [])
        ):
            reasons.append("campaign_lease_paths_mismatch")
        if sorted(lease.get("action_classes", [])) != [binding.get("action_class")]:
            reasons.append("campaign_lease_action_mismatch")
        if lease.get("owner_id") != binding.get("worker_revision_id"):
            reasons.append("campaign_lease_worker_identity_mismatch")
        grant = lease.get("grant", {})
        if not isinstance(grant, Mapping) or grant.get(
            "approval_id"
        ) != authority_approval_ids.get("lease_approval_id"):
            reasons.append("campaign_lease_approval_mismatch")
        if isinstance(grant, Mapping) and grant.get("granted_by") != binding.get(
            "named_approver"
        ):
            reasons.append("campaign_lease_approver_mismatch")
        try:
            lease_start = datetime.fromisoformat(
                str(lease.get("not_before", "")).replace("Z", "+00:00")
            )
            lease_expiry = datetime.fromisoformat(
                str(lease.get("expires_at", "")).replace("Z", "+00:00")
            )
            lease_minutes = int(binding.get("lease_minutes", 0))
            if (
                lease_start.tzinfo is None
                or lease_expiry.tzinfo is None
                or lease_minutes < 1
                or lease_expiry <= lease_start
                or lease_expiry - lease_start > timedelta(minutes=lease_minutes)
            ):
                raise ValueError
        except (TypeError, ValueError):
            reasons.append("campaign_lease_interval_mismatch")
        else:
            heartbeat_value = binding.get("heartbeat_at")
            try:
                heartbeat_for_lease = datetime.fromisoformat(
                    str(heartbeat_value).replace("Z", "+00:00")
                )
            except ValueError:
                heartbeat_for_lease = observed
            if not lease_start <= heartbeat_for_lease < lease_expiry:
                reasons.append("campaign_heartbeat_outside_lease")

    if dispatch is not None:
        if lease is None or dispatch.get("lease_id") != lease.get("lease_id"):
            reasons.append("campaign_dispatch_lease_mismatch")
        if (
            dispatch.get("status") != "ready_manual"
            or dispatch.get("authorization_valid") is not True
            or dispatch.get("manual_packet_ready") is not True
        ):
            reasons.append("campaign_dispatch_not_ready_manual")
        if dispatch.get("dispatch_allowed") is not False:
            reasons.append("campaign_dispatch_boundary_invalid")
        if sorted(dispatch.get("requested_paths", [])) != sorted(
            binding.get("allowed_paths", [])
        ):
            reasons.append("campaign_dispatch_paths_mismatch")
        if dispatch.get("action") != binding.get("action_class"):
            reasons.append("campaign_dispatch_action_mismatch")
        if sorted(dispatch.get("acceptance_refs", [])) != sorted(
            binding.get("acceptance_evidence_paths", [])
        ):
            reasons.append("campaign_dispatch_acceptance_scope_mismatch")
        if dispatch.get("worker_revision_id") != binding.get("worker_revision_id"):
            reasons.append("campaign_dispatch_worker_identity_mismatch")
        if dispatch.get("checker_revision_id") != binding.get("checker_revision_id"):
            reasons.append("campaign_dispatch_checker_identity_mismatch")
        if binding.get("worker_revision_id") == binding.get("checker_revision_id"):
            reasons.append("campaign_dispatch_identity_not_independent")
        approval = dispatch.get("approval", {})
        if not isinstance(approval, Mapping) or approval.get(
            "approval_id"
        ) != authority_approval_ids.get("dispatch_approval_id"):
            reasons.append("campaign_dispatch_approval_mismatch")
        if isinstance(approval, Mapping) and approval.get("approved_by") != binding.get(
            "named_approver"
        ):
            reasons.append("campaign_dispatch_approver_mismatch")
        if dispatch.get("expected_repo_snapshot") != binding.get("source_revision"):
            reasons.append("campaign_dispatch_source_snapshot_mismatch")
        expected_authority_refs = sorted(
            {
                str(binding.get("authorization_id", "")),
                str(binding.get("authorization_receipt_digest", "")),
                str(authority_approval_ids.get("lease_approval_id", "")),
                str(authority_approval_ids.get("dispatch_approval_id", "")),
            }
            - {""}
        )
        if sorted(dispatch.get("authority_refs", [])) != expected_authority_refs:
            reasons.append("campaign_dispatch_authority_refs_mismatch")

    if not set(binding.get("output_paths", [])).issubset(
        set(binding.get("allowed_paths", []))
    ):
        reasons.append("campaign_output_scope_invalid")

    repair_attempt = binding.get("repair_attempt")
    max_repairs = binding.get("max_repairs")
    if (
        isinstance(repair_attempt, bool)
        or not isinstance(repair_attempt, int)
        or isinstance(max_repairs, bool)
        or not isinstance(max_repairs, int)
        or repair_attempt < 0
        or max_repairs < 0
        or repair_attempt > max_repairs
    ):
        reasons.append("campaign_repair_limit_invalid")
    elif repair_attempt == 0:
        if binding.get("reissue_of_attempt_id") or binding.get(
            "prior_reconciliation_digest"
        ):
            reasons.append("campaign_initial_attempt_reconciliation_invalid")
    elif not binding.get("reissue_of_attempt_id") or not str(
        binding.get("prior_reconciliation_digest", "")
    ).startswith("sha256:"):
        reasons.append("campaign_reissue_reconciliation_missing")
    if binding.get("partial_effects_reconciled") is not True:
        reasons.append("campaign_partial_effects_unreconciled")

    reasons = sorted(set(reasons))
    return {
        "status": "blocked" if reasons else "ready-manual",
        "reason_codes": reasons,
        "manual_packet_ready": not reasons,
        "dispatch_allowed": False,
        "executor_available": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _campaign_reconciliation_digest(value: Mapping[str, Any]) -> str:
    material = json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def campaign_runtime_state_from_projection(
    projection: Mapping[str, Any],
    *,
    campaign_id: str,
    campaign_revision: str,
    job_id: str,
    campaign_binding: Mapping[str, Any],
    durable_attempts: Iterable[Mapping[str, Any]] = (),
    receipt_evidence_complete: bool = True,
) -> dict[str, Any]:
    """Project campaign runtime facts from existing Portfolio journals only.

    Attempt rows remain source-zero-write observations. Because that journal
    does not measure cost, wall time, context, or output size, any selected
    attempt makes budget evidence incomplete and therefore blocks readiness.
    """

    def campaign_row(row: Any) -> bool:
        binding = row.get("campaign_binding") if isinstance(row, Mapping) else None
        return (
            isinstance(binding, Mapping)
            and binding.get("campaign_id") == campaign_id
            and binding.get("campaign_revision") == campaign_revision
        )

    def target_row(row: Any) -> bool:
        return campaign_row(row) and row["campaign_binding"].get("job_id") == job_id

    leases = [row for row in projection.get("leases", []) if campaign_row(row)]
    dispatches = [row for row in projection.get("dispatches", []) if campaign_row(row)]
    target_leases = [row for row in leases if target_row(row)]
    target_dispatches = [row for row in dispatches if target_row(row)]
    durable_by_id: dict[str, dict[str, Any]] = {}
    durable_attempts_invalid = False
    for row in durable_attempts:
        attempt_id = str(row.get("attempt_id", "")) if isinstance(row, Mapping) else ""
        measurements = (
            row.get("cost_units"),
            row.get("wall_seconds"),
            row.get("context_tokens"),
            row.get("output_mb"),
            row.get("attempt_count"),
        ) if isinstance(row, Mapping) else ()
        if (
            not isinstance(row, Mapping)
            or not attempt_id
            or attempt_id in durable_by_id
            or len(measurements) != 5
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
                for value in measurements
            )
            or row.get("budget_evidence_complete") is not True
        ):
            durable_attempts_invalid = True
            continue
        durable_by_id[attempt_id] = dict(row)
    attempts: list[dict[str, Any]] = []
    issued_packets: list[dict[str, str]] = []
    for dispatch in dispatches:
        observed = dispatch.get("dry_run_attempt")
        if not isinstance(observed, Mapping) or not observed.get("selected_attempt_id"):
            continue
        binding = dispatch.get("campaign_binding", {})
        reconciliation = dispatch.get("reconciliation")
        attempt = {
            "job_id": binding.get("job_id"),
            "attempt_id": observed.get("selected_attempt_id"),
            "attempt_count": 1,
            "cost_units": 0,
            "wall_seconds": 0,
            "context_tokens": 0,
            "output_mb": 0,
            "budget_evidence_complete": False,
            "reconciled": dispatch.get("status") == "reconciliation_dry_run_only",
            "reconciliation_digest": (
                _campaign_reconciliation_digest(reconciliation)
                if isinstance(reconciliation, Mapping)
                else ""
            ),
        }
        measured = durable_by_id.pop(str(observed.get("selected_attempt_id")), None)
        if measured is not None:
            attempt.update(measured)
        attempts.append(attempt)
        issued_packets.append(
            {
                "idempotency_key": str(binding.get("idempotency_key", "")),
                "packet_digest": str(binding.get("packet_digest", "")),
            }
        )

    ledger_errors: list[str] = []
    if "ledger_diagnostics" not in projection:
        ledger_errors.append("execution_ledger_diagnostics_missing")
    attempt_journal = projection.get("attempt_journal", {})
    if not isinstance(attempt_journal, Mapping):
        attempt_journal = {}
    if "ledger_diagnostics" not in attempt_journal:
        ledger_errors.append("attempt_ledger_diagnostics_missing")
    for label, diagnostics in (
        ("execution", projection.get("ledger_diagnostics", {})),
        ("attempt", attempt_journal.get("ledger_diagnostics", {})),
    ):
        if not isinstance(diagnostics, Mapping):
            ledger_errors.append(f"{label}_ledger_diagnostics_invalid")
            continue
        if any(
            bool(diagnostics.get(key))
            for key in (
                "corrupt_line_count",
                "invalid_envelope_count",
                "invalid_event_count",
                "torn_tail_pending",
                "ambiguous_tail",
                "problems",
                "fold_problems",
            )
        ):
            ledger_errors.append(f"{label}_ledger_integrity_invalid")

    for measured in durable_by_id.values():
        attempts.append(
            {
                **measured,
                "reconciled": False,
                "reconciliation_digest": "",
            }
        )

    exact_leases = [
        row for row in target_leases if dict(row.get("campaign_binding", {})) == dict(campaign_binding)
    ]
    exact_dispatches = [
        row
        for row in target_dispatches
        if dict(row.get("campaign_binding", {})) == dict(campaign_binding)
    ]
    requested_paths = sorted(
        {
            str(path)
            for row in (*exact_leases, *exact_dispatches)
            for path in row.get("requested_paths", [])
        }
    )
    requested_effects = sorted(
        {str(value) for value in campaign_binding.get("allowed_effects", [])}
    )
    has_active_target = any(row.get("status") == "active" for row in target_leases)
    stop_requested = not has_active_target and any(
        row.get("status") == "revoked" for row in (*target_leases, *target_dispatches)
    )
    return {
        "attempts": attempts,
        "issued_packets": issued_packets,
        "leases": [
            {"job_id": row.get("campaign_binding", {}).get("job_id"), "state": "active"}
            for row in leases
            if row.get("status") == "active"
        ],
        "requested_paths": requested_paths,
        "requested_effects": requested_effects,
        "stop_requested": stop_requested,
        "budget_evidence_complete": (
            receipt_evidence_complete
            and not durable_attempts_invalid
            and not ledger_errors
            and all(row.get("budget_evidence_complete") is True for row in attempts)
        ),
        "runtime_state_errors": sorted(set(ledger_errors)),
    }


def _legacy_verified_records(
    events: Iterable[dict[str, Any]],
    bundles: Iterable[VerifiedApprovals],
    *,
    observed: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    keys: set[tuple[str, str, str, str]] = set()
    diagnostics: set[str] = set()
    reports: list[dict[str, Any]] = []
    for approvals in bundles:
        bundle_keys, report = _verified_event_keys(approvals)
        keys.update(bundle_keys)
        diagnostics.update(str(item) for item in report.get("diagnostics", []))
        reports.append(report)

    records: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        event_id = str(event.get("event_id", ""))
        event_kind = str(event.get("event_kind", ""))
        approval_id = str(payload.get("approval_id", ""))
        exact_digest = authority_event_digest(event)
        if (event_id, event_kind, exact_digest, approval_id) not in keys:
            continue
        records.append(
            {
                "approval_id": approval_id,
                "event_kind": event_kind,
                "event_digest": authority_attestation_digest(event_kind, payload),
                "verified_by": "ed25519_exact_event_shadow",
                "not_before": (observed - timedelta(seconds=1)).isoformat(),
                "expires_at": (observed + timedelta(seconds=1)).isoformat(),
            }
        )

    if not reports:
        diagnostics.add("trusted_verifier_not_supplied")
    single_report = reports[0] if len(reports) == 1 else {}
    report = {
        "schema_version": "dad.portfolio_approval_verification.v1",
        "status": "verified_shadow_candidates" if records else "deny_all",
        "trust_registry_status": single_report.get("trust_registry_status", "test_or_unavailable"),
        "trust_anchor_status": single_report.get("trust_anchor_status", "unanchored_shadow"),
        "attestation_count": sum(int(item.get("attestation_count", 0)) for item in reports),
        "verified_attestation_count": len(records),
        "diagnostics": sorted(diagnostics),
        "authority_boundary": (
            "Signatures are unanchored shadow evidence only; public folds do not "
            "accept verifier-result injection and no executor exists."
        ),
    }
    return records, report


def _fold_execution_control_verified(
    events: list[dict[str, Any]],
    workstreams: Iterable[dict[str, Any]],
    *,
    as_of: datetime | None,
    verified_bundles: Iterable[VerifiedApprovals],
    ledger_diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    observed = _now(as_of)
    legacy_records, report = _legacy_verified_records(
        events,
        verified_bundles,
        observed=observed,
    )
    projection = _legacy.fold_execution_control(
        events,
        workstreams,
        as_of=observed,
        verified_approval_records=legacy_records,
        ledger_diagnostics=ledger_diagnostics,
    )
    projection["ledger_diagnostics"] = dict(ledger_diagnostics or {})
    projection["approval_verification"] = {
        **report,
        "mode": "ed25519_exact_event_shadow",
        "default": "deny_all",
        "bare_ids_authorize": False,
        "raw_verified_records_authorize": False,
        "verifier_result_injection_public": False,
        "real_execution_authority": False,
    }
    projection["diagnostics"] = sorted(
        {
            *projection.get("diagnostics", []),
            *(f"approval_verifier:{item}" for item in report["diagnostics"]),
        }
    )
    projection["executor"] = {"available": False, "dispatch_allowed": False}
    for dispatch in projection.get("dispatches", []):
        dispatch["dispatch_allowed"] = False
    return projection


def fold_execution_control(
    events: list[dict[str, Any]],
    workstreams: Iterable[dict[str, Any]],
    *,
    as_of: datetime | None = None,
    ledger_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fold public deny-all shadow state without an authority injection surface."""

    return _fold_execution_control_verified(
        events,
        workstreams,
        as_of=as_of,
        verified_bundles=(),
        ledger_diagnostics=ledger_diagnostics,
    )


def _fold_execution_control_for_test(
    events: list[dict[str, Any]],
    workstreams: Iterable[dict[str, Any]],
    *,
    as_of: datetime | None = None,
    verified_approval_records: Any = (),
    ledger_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Private compatibility harness; production callers must use raw attestations."""

    values = (
        [verified_approval_records]
        if isinstance(verified_approval_records, VerifiedApprovals)
        else list(verified_approval_records)
    )
    if any(not isinstance(value, VerifiedApprovals) for value in values):
        raise TypeError("test approval records must be verifier result objects")
    return _fold_execution_control_verified(
        events,
        workstreams,
        as_of=as_of,
        verified_bundles=values,
        ledger_diagnostics=ledger_diagnostics,
    )


def load_execution_control(
    hub_root: Path,
    *,
    as_of: datetime | None = None,
    attestations: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Verify raw envelopes at the fixed repo trust path, then load dry-run observations."""

    observed = _now(as_of)
    events, state = _legacy._kernel_state(hub_root, now=observed)
    verified = verify_approval_attestations(
        events,
        attestations,
        load_trust_registry(hub_root),
        as_of=observed,
    )
    projection = _fold_execution_control_verified(
        events,
        state.get("workstreams", []),
        as_of=observed,
        verified_bundles=(verified,),
        ledger_diagnostics=state.get("ledger_diagnostics", {}),
    )
    return annotate_execution_projection(projection, load_attempt_projection(hub_root))


def _load_execution_control_for_test(
    hub_root: Path,
    *,
    as_of: datetime | None = None,
    verified_approval_records: Any = (),
) -> dict[str, Any]:
    """Private fixture loader; it is not exported and never permits real dispatch."""

    observed = _now(as_of)
    events, state = _legacy._kernel_state(hub_root, now=observed)
    projection = _fold_execution_control_for_test(
        events,
        state.get("workstreams", []),
        as_of=observed,
        verified_approval_records=verified_approval_records,
        ledger_diagnostics=state.get("ledger_diagnostics", {}),
    )
    return annotate_execution_projection(projection, load_attempt_projection(hub_root))


__all__ = [
    "ACTION_CLASSES",
    "AUTHORITY_BOUNDARY",
    "DEFAULT_FORBIDDEN_ACTIONS",
    "MAX_LEASE_DURATION",
    "OWNER_KINDS",
    "SCHEMA_VERSION",
    "CAMPAIGN_BINDING_SCHEMA",
    "approve_dispatch_intent",
    "authority_attestation_digest",
    "authority_event_digest",
    "campaign_runtime_state_from_projection",
    "dispatch_packet",
    "dispatch_scope_digest",
    "fold_execution_control",
    "grant_execution_lease",
    "lease_scope_digest",
    "load_execution_control",
    "propose_dispatch_intent",
    "request_execution_lease",
    "revoke_dispatch_intent",
    "revoke_execution_lease",
    "validate_campaign_execution_control",
    "write_execution_control_outputs",
]
