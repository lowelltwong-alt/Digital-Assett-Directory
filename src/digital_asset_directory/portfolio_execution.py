"""Guarded public execution-control facade for the Portfolio OS.

The established fold remains in a private compatibility module. The public
boundary accepts raw attestations only through ``load_execution_control`` and
recomputes them against the fixed repository trust path. No public fold accepts
a caller-supplied verifier result, raw verified dictionary, or bare approval ID.
Every dispatch flag remains false, and no source repository is mutated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

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
    "approve_dispatch_intent",
    "authority_attestation_digest",
    "authority_event_digest",
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
    "write_execution_control_outputs",
]
