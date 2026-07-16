"""Human-gated execution control for the Portfolio OS.

Authority events share the existing per-workstream hash-chained ledger.  This
module derives a separate projection; it never runs a command, touches Git,
launches an agent, or writes another repository.  Approval identifiers are
attestations until an explicit trusted-verifier input supplies the exact IDs,
so the default projection is deny-all.
"""

from __future__ import annotations
import hashlib

from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Callable, Iterable
import uuid

from .ids import stable_id
from .portfolio_events import (
    EventConflictError,
    LedgerIntegrityError,
    LedgerLock,
    build_event,
    ledger_path,
    read_events,
    repair_tail,
    stream_heads,
)
from .utils import atomic_write_text, json_dumps

SCHEMA_VERSION = "dad.portfolio_execution_control.v1"
MAX_LEASE_DURATION = timedelta(days=31)
ACTION_CLASSES = ("inspect", "plan", "implement", "validate")
OWNER_KINDS = ("human", "agent", "team")
DEFAULT_FORBIDDEN_ACTIONS = (
    "cross_repo_write",
    "delete_or_cleanup",
    "direct_push_or_merge_protected_branch",
    "external_connector_write",
    "permission_or_dependency_expansion",
    "public_release",
)
AUTHORITY_BOUNDARY = (
    "Execution-control events are local candidate authority metadata. The kernel never executes "
    "them. Exact lease and dispatch approvals must be independently verified, current, scoped, "
    "and unretracted before a separately gated executor may consider a manual packet."
)
_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _now(value: datetime | None) -> datetime:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _canonical_strings(
    values: Iterable[str], *, field: str, allow_empty: bool = False
) -> list[str]:
    result = sorted({str(value).strip() for value in values if str(value).strip()})
    if not result and not allow_empty:
        raise ValueError(f"{field} must contain at least one non-empty value")
    return result


def _repo_relative_paths(values: Iterable[str]) -> list[str]:
    paths = _canonical_strings(values, field="requested_paths")
    normalized: list[str] = []
    for value in paths:
        candidate = value.replace("\\", "/")
        pure = PurePosixPath(candidate)
        if candidate.startswith("/") or _DRIVE_RE.match(value) or ".." in pure.parts:
            raise ValueError(
                f"requested path must be repository-relative and traversal-free: {value}"
            )
        normalized.append(candidate)
    return sorted(set(normalized))


def _scope_digest(kind: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"dad:portfolio-{kind}-scope:{digest}"


def lease_scope_digest(payload: dict[str, Any]) -> str:
    fields = [
        "workstream_id",
        "owner_id",
        "owner_kind",
        "repo_binding_id",
        "action_classes",
        "requested_paths",
        "not_before",
        "expires_at",
        "return_state",
        "rationale_code",
        "supersedes_lease_id",
    ]
    fields.extend(
        key
        for key in (
            "portability_assessment_id",
            "portability_artifact_ids",
            "portability_scope_digest",
        )
        if key in payload
    )
    return _scope_digest(
        "lease",
        {key: payload[key] for key in fields},
    )


def dispatch_scope_digest(payload: dict[str, Any]) -> str:
    return _scope_digest(
        "dispatch",
        {
            key: payload[key]
            for key in (
                "workstream_id",
                "lease_id",
                "repo_binding_id",
                "action",
                "worker_revision_id",
                "checker_revision_id",
                "task_summary",
                "requested_paths",
                "acceptance_refs",
                "validation_commands",
                "authority_refs",
                "expected_repo_snapshot",
                "forbidden_actions",
            )
        },
    )


def _accepted_repo_binding(workstream: dict[str, Any], binding_id: str) -> dict[str, Any] | None:
    for binding in workstream.get("bindings", []):
        if (
            binding.get("binding_id") == binding_id
            and binding.get("binding_kind") == "repo"
            and binding.get("assertion_status") == "accepted"
        ):
            return binding
    return None


def _kernel_state(hub_root: Path, *, now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from .portfolio_workstreams import load_state

    events, diagnostics = read_events(ledger_path(hub_root))
    state = load_state(hub_root, now=now)
    state["ledger_diagnostics"] = diagnostics | {
        "fold_problems": state.get("ledger_diagnostics", {}).get("fold_problems", [])
    }
    return events, state


def _append_bytes(path: Path, data: bytes) -> None:
    """Durably append one buffer while the caller owns the ledger lock."""

    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short write while appending portfolio control event")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_control_event(
    hub_root: Path,
    *,
    event_kind: str,
    workstream_id: str,
    observed: datetime,
    command_id: str | None,
    prepare: Callable[
        [list[dict[str, Any]], dict[str, Any]],
        tuple[dict[str, Any], dict[str, Any]] | dict[str, Any],
    ],
) -> dict[str, Any]:
    """Validate current identity state and append under one ledger lock."""

    path = ledger_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    recorded_at = observed.isoformat()
    with LedgerLock(path):
        quarantined = repair_tail(path, recorded_at=recorded_at)
        events, diagnostics = read_events(path)
        if diagnostics["corrupt_line_count"] or diagnostics["invalid_envelope_count"]:
            raise LedgerIntegrityError(
                "Ledger contains interior corruption or invalid event chains; refusing append: "
                + "|".join(diagnostics["problems"])
            )

        from .portfolio_workstreams import load_state

        state = load_state(hub_root, now=observed)
        state["ledger_diagnostics"] = diagnostics | {
            "fold_problems": state.get("ledger_diagnostics", {}).get("fold_problems", [])
        }
        prepared = prepare(events, state)
        if isinstance(prepared, dict):
            return prepared
        payload, response = prepared

        event, _ = build_event(
            event_kind=event_kind,
            stream_id=workstream_id,
            payload=payload,
            prev_event_id=stream_heads(events).get(workstream_id, ""),
            recorded_at=recorded_at,
            command_id=command_id,
        )
        prior = next(
            (
                row
                for row in events
                if row.get("stream_id") == workstream_id
                and row.get("command_id") == event.get("command_id")
            ),
            None,
        )
        if prior is not None:
            if prior.get("event_kind") != event_kind or prior.get("payload") != event["payload"]:
                raise EventConflictError(
                    f"command_id conflict for stream {workstream_id}: {event['command_id']}"
                )
            appended = 0
            deduplicated = 1
        else:
            prior_by_id = next(
                (row for row in events if row.get("event_id") == event["event_id"]), None
            )
            if prior_by_id is not None:
                if json_dumps(prior_by_id) != json_dumps(event):
                    raise EventConflictError(f"event_id conflict: {event['event_id']}")
                appended = 0
                deduplicated = 1
            else:
                _append_bytes(path, (json_dumps(event) + "\n").encode("utf-8"))
                appended = 1
                deduplicated = 0

        return {
            **response,
            "events_appended": appended,
            "events_deduplicated": deduplicated,
            "tail_fragments_quarantined": quarantined,
            "corrupt_line_count": diagnostics["corrupt_line_count"],
            "invalid_envelope_count": diagnostics["invalid_envelope_count"],
        }


def authority_attestation_digest(event_kind: str, payload: dict[str, Any]) -> str:
    """Return a byte-exact digest for an external verifier to attest."""

    canonical = json.dumps(
        {"event_kind": event_kind, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _control_key(workstream_id: str, subject_id: str) -> tuple[str, str]:
    return workstream_id, subject_id


def _find_control_row(
    rows: Iterable[dict[str, Any]],
    *,
    workstream_id: str,
    id_field: str,
    subject_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in rows
            if row.get("workstream_id") == workstream_id and row.get(id_field) == subject_id
        ),
        None,
    )


def _subject_label(workstream_id: str, subject_id: str) -> str:
    return f"{workstream_id}:{subject_id}"


def _verified_event_keys(
    records: Iterable[dict[str, Any] | str],
    *,
    observed: datetime,
    diagnostics: list[str],
) -> frozenset[tuple[str, str, str]]:
    """Validate typed, time-bounded attestations; bare IDs never grant authority."""

    by_approval: dict[str, set[tuple[str, str, str]]] = {}
    for record in records:
        if not isinstance(record, dict):
            diagnostics.append(f"unscoped_approval_ignored:{str(record)}")
            continue
        required = (
            "approval_id",
            "event_kind",
            "event_digest",
            "verified_by",
            "not_before",
            "expires_at",
        )
        if any(not str(record.get(field, "")).strip() for field in required):
            diagnostics.append(
                f"malformed_verified_attestation:{record.get('approval_id', 'missing')}"
            )
            continue
        approval_id = str(record["approval_id"])
        try:
            not_before = _parse_time(str(record["not_before"]))
            expires_at = _parse_time(str(record["expires_at"]))
        except ValueError:
            diagnostics.append(f"malformed_verified_attestation:{approval_id}")
            continue
        if expires_at <= not_before:
            diagnostics.append(f"malformed_verified_attestation:{approval_id}")
            continue
        if not (not_before <= observed < expires_at):
            continue
        key = (str(record["event_kind"]), str(record["event_digest"]), approval_id)
        by_approval.setdefault(approval_id, set()).add(key)

    verified: set[tuple[str, str, str]] = set()
    for approval_id, keys in by_approval.items():
        if len(keys) != 1:
            diagnostics.append(f"approval_id_reused:{approval_id}")
            continue
        verified.update(keys)
    return frozenset(verified)


def _event_is_verified(
    event_kind: str,
    payload: dict[str, Any],
    verified: frozenset[tuple[str, str, str]],
) -> bool:
    event_payload = {key: value for key, value in payload.items() if key != "recorded_at"}
    return (
        event_kind,
        authority_attestation_digest(event_kind, event_payload),
        str(payload.get("approval_id", "")),
    ) in verified


def _path_is_within(requested: str, allowed: str) -> bool:
    allowed_root = allowed.rstrip("/")
    return (
        allowed_root == "." or requested == allowed_root or requested.startswith(allowed_root + "/")
    )


def _repo_paths_are_canonical(values: Any) -> bool:
    if not isinstance(values, list) or not values:
        return False
    try:
        normalized = _repo_relative_paths(str(value) for value in values)
    except ValueError:
        return False
    return normalized == values


def _dispatch_scope_problems(dispatch: dict[str, Any], lease: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if dispatch.get("action") not in lease.get("action_classes", []):
        problems.append("action_outside_lease")
    if dispatch.get("repo_binding_id") != lease.get("repo_binding_id"):
        problems.append("repo_binding_outside_lease")
    if not _repo_paths_are_canonical(dispatch.get("requested_paths")):
        problems.append("invalid_requested_paths")
    allowed_paths = [str(path) for path in lease.get("requested_paths", [])]
    for requested in dispatch.get("requested_paths", []):
        if not any(_path_is_within(str(requested), allowed) for allowed in allowed_paths):
            problems.append("path_outside_lease")
            break
    if not set(DEFAULT_FORBIDDEN_ACTIONS).issubset(dispatch.get("forbidden_actions", [])):
        problems.append("mandatory_forbidden_action_missing")
    for field in ("acceptance_refs", "validation_commands", "authority_refs"):
        if not dispatch.get(field):
            problems.append(f"{field}_required")
    if lease.get("owner_kind") == "agent" and dispatch.get("worker_revision_id") != lease.get(
        "owner_id"
    ):
        problems.append("worker_not_lease_owner")
    return sorted(set(problems))


def fold_execution_control(
    events: list[dict[str, Any]],
    workstreams: Iterable[dict[str, Any]],
    *,
    as_of: datetime | None = None,
    verified_approval_records: Iterable[dict[str, Any] | str] = (),
    verified_approval_ids: Iterable[str] = (),
    ledger_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure projection of authority events; default approval verification denies all."""

    observed = _now(as_of)
    workstream_map = {str(item.get("workstream_id", "")): item for item in workstreams}
    leases: dict[tuple[str, str], dict[str, Any]] = {}
    dispatches: dict[tuple[str, str], dict[str, Any]] = {}
    diagnostics: list[str] = []

    verification_inputs: list[dict[str, Any] | str] = list(verified_approval_records)
    verification_inputs.extend(str(value) for value in verified_approval_ids if str(value))
    verified = _verified_event_keys(
        verification_inputs,
        observed=observed,
        diagnostics=diagnostics,
    )

    for event in events:
        kind = str(event.get("event_kind", ""))
        if kind not in {
            "execution_lease_requested",
            "execution_lease_granted",
            "execution_lease_revoked",
            "dispatch_intent_proposed",
            "dispatch_intent_approved",
            "dispatch_intent_revoked",
            "dispatch_reconciliation_recorded",
        }:
            continue
        payload = event.get("payload", {})
        recorded_at = str(event.get("recorded_at", ""))
        workstream_id = str(payload.get("workstream_id", ""))
        try:
            event_time = _parse_time(recorded_at)
        except ValueError:
            diagnostics.append(f"invalid_recorded_at:{kind}:{event.get('event_id', '')}")
            continue
        if event_time > observed:
            diagnostics.append(f"future_event_ignored:{kind}:{event.get('event_id', '')}")
            continue

        if kind == "execution_lease_requested":
            lease_id = str(payload.get("lease_id", ""))
            key = _control_key(workstream_id, lease_id)
            expected = lease_scope_digest(payload)
            if key in leases:
                leases[key]["identity_conflict"] = True
                diagnostics.append(f"duplicate_lease_request:{_subject_label(*key)}")
                continue
            if expected != payload.get("scope_digest"):
                diagnostics.append(f"lease_scope_digest_mismatch:{_subject_label(*key)}")
            leases[key] = {
                **payload,
                "scope_valid": expected == payload.get("scope_digest"),
                "identity_conflict": False,
                "requested_at": recorded_at,
                "grant": None,
                "revocation": None,
                "status": "requested",
                "authorization_valid": False,
            }
        elif kind == "execution_lease_granted":
            lease_id = str(payload.get("lease_id", ""))
            key = _control_key(workstream_id, lease_id)
            lease = leases.get(key)
            if lease is None:
                diagnostics.append(f"grant_without_request:{_subject_label(*key)}")
            elif lease.get("grant") is not None:
                lease["identity_conflict"] = True
                diagnostics.append(f"duplicate_lease_grant:{_subject_label(*key)}")
            elif payload.get("scope_digest") != lease.get("scope_digest"):
                lease["scope_valid"] = False
                diagnostics.append(f"grant_scope_digest_mismatch:{_subject_label(*key)}")
            else:
                lease["grant"] = {**payload, "recorded_at": recorded_at}
        elif kind == "execution_lease_revoked":
            lease_id = str(payload.get("lease_id", ""))
            key = _control_key(workstream_id, lease_id)
            lease = leases.get(key)
            if lease is None:
                diagnostics.append(f"revoke_without_lease:{_subject_label(*key)}")
            elif lease.get("revocation") is None:
                lease["revocation"] = {**payload, "recorded_at": recorded_at}
            else:
                diagnostics.append(f"duplicate_lease_revocation:{_subject_label(*key)}")
        elif kind == "dispatch_intent_proposed":
            dispatch_id = str(payload.get("dispatch_revision_id", ""))
            key = _control_key(workstream_id, dispatch_id)
            expected = dispatch_scope_digest(payload)
            if key in dispatches:
                dispatches[key]["identity_conflict"] = True
                diagnostics.append(f"duplicate_dispatch_proposal:{_subject_label(*key)}")
                continue
            if expected != payload.get("scope_digest"):
                diagnostics.append(f"dispatch_scope_digest_mismatch:{_subject_label(*key)}")
            dispatches[key] = {
                **payload,
                "scope_valid": expected == payload.get("scope_digest"),
                "identity_conflict": False,
                "proposed_at": recorded_at,
                "approval": None,
                "revocation": None,
                "reconciliation": None,
                "status": "proposed",
                "authorization_valid": False,
                "manual_packet_ready": False,
                "dispatch_allowed": False,
            }
        elif kind == "dispatch_intent_approved":
            dispatch_id = str(payload.get("dispatch_revision_id", ""))
            key = _control_key(workstream_id, dispatch_id)
            dispatch = dispatches.get(key)
            if dispatch is None:
                diagnostics.append(f"approval_without_dispatch:{_subject_label(*key)}")
            elif dispatch.get("approval") is not None:
                dispatch["identity_conflict"] = True
                diagnostics.append(f"duplicate_dispatch_approval:{_subject_label(*key)}")
            else:
                dispatch["approval"] = {**payload, "recorded_at": recorded_at}
        elif kind == "dispatch_intent_revoked":
            dispatch_id = str(payload.get("dispatch_revision_id", ""))
            key = _control_key(workstream_id, dispatch_id)
            dispatch = dispatches.get(key)
            if dispatch is None:
                diagnostics.append(f"revoke_without_dispatch:{_subject_label(*key)}")
            elif dispatch.get("revocation") is None:
                dispatch["revocation"] = {**payload, "recorded_at": recorded_at}
            else:
                diagnostics.append(f"duplicate_dispatch_revocation:{_subject_label(*key)}")
        elif kind == "dispatch_reconciliation_recorded":
            dispatch_id = str(payload.get("dispatch_revision_id", ""))
            key = _control_key(workstream_id, dispatch_id)
            dispatch = dispatches.get(key)
            if dispatch is None:
                diagnostics.append(f"reconciliation_without_dispatch:{_subject_label(*key)}")
            elif dispatch.get("reconciliation") is None:
                dispatch["reconciliation"] = {**payload, "recorded_at": recorded_at}
            else:
                diagnostics.append(f"duplicate_dispatch_reconciliation:{_subject_label(*key)}")

    ledger_blocked = bool(
        ledger_diagnostics
        and (
            ledger_diagnostics.get("corrupt_line_count")
            or ledger_diagnostics.get("invalid_envelope_count")
            or ledger_diagnostics.get("torn_tail_pending")
            or ledger_diagnostics.get("problems")
            or ledger_diagnostics.get("fold_problems")
        )
    )

    for key, lease in leases.items():
        workstream = workstream_map.get(key[0])
        grant = lease.get("grant")
        try:
            not_before = _parse_time(str(lease["not_before"]))
            expires_at = _parse_time(str(lease["expires_at"]))
            interval_valid = (
                expires_at > not_before and expires_at - not_before <= MAX_LEASE_DURATION
            )
        except (KeyError, ValueError):
            not_before = observed
            expires_at = observed
            interval_valid = False
        lease_paths_valid = _repo_paths_are_canonical(lease.get("requested_paths"))
        if not lease_paths_valid:
            diagnostics.append(f"lease_invalid_requested_paths:{_subject_label(*key)}")
        if lease.get("identity_conflict"):
            status = "blocked_identity_conflict"
        elif not lease.get("scope_valid", False):
            status = "blocked_scope"
        elif not lease_paths_valid:
            status = "blocked_scope"
        elif not interval_valid:
            status = "blocked_interval"
        elif ledger_blocked:
            status = "blocked_ledger_integrity"
        elif lease.get("revocation"):
            status = "revoked"
        elif grant is None:
            status = "requested"
        elif not _event_is_verified("execution_lease_granted", grant, verified):
            status = "approval_unverified"
        elif workstream is None or workstream.get("lifecycle_state") != "active":
            status = "blocked_workstream_state"
        elif _accepted_repo_binding(workstream, str(lease.get("repo_binding_id", ""))) is None:
            status = "blocked_repo_binding"
        elif observed < not_before:
            status = "scheduled"
        elif observed >= expires_at:
            status = "expired"
        else:
            status = "active"
        lease["status"] = status
        lease["authorization_valid"] = status == "active"

    active_replacements = sorted(
        (
            (key, lease)
            for key, lease in leases.items()
            if lease.get("status") == "active" and lease.get("supersedes_lease_id")
        ),
        key=lambda item: item[1]["requested_at"],
    )
    valid_successors: dict[tuple[str, str], list[tuple[tuple[str, str], dict[str, Any]]]] = {}
    for key, replacement in active_replacements:
        target_key = _control_key(key[0], str(replacement["supersedes_lease_id"]))
        target = leases.get(target_key)
        if (
            target is None
            or target_key == key
            or _parse_time(str(replacement["requested_at"]))
            <= _parse_time(str(target["requested_at"]))
        ):
            replacement["status"] = "blocked_supersession"
            replacement["authorization_valid"] = False
            diagnostics.append(f"invalid_lease_supersession:{_subject_label(*key)}")
            continue
        valid_successors.setdefault(target_key, []).append((key, replacement))

    for target_key, successors in sorted(valid_successors.items()):
        if len(successors) != 1:
            for key, replacement in successors:
                replacement["status"] = "blocked_supersession_conflict"
                replacement["authorization_valid"] = False
                diagnostics.append(f"multiple_lease_successors:{_subject_label(*key)}")
            continue
        target = leases[target_key]
        if target.get("status") == "active":
            target["status"] = "superseded"
            target["authorization_valid"] = False

    for key, dispatch in dispatches.items():
        dispatch_id = key[1]
        lease = leases.get(_control_key(key[0], str(dispatch.get("lease_id", ""))))
        approval = dispatch.get("approval")
        if dispatch.get("identity_conflict"):
            status = "blocked_identity_conflict"
        elif not dispatch.get("scope_valid", False):
            status = "blocked_scope"
        elif ledger_blocked:
            status = "blocked_ledger_integrity"
        elif dispatch.get("revocation"):
            status = "revoked"
        elif dispatch.get("reconciliation"):
            reconciliation = dispatch["reconciliation"]
            if reconciliation.get("dispatch_scope_digest") != dispatch.get(
                "scope_digest"
            ) or not reconciliation.get("attempt_id"):
                status = "blocked_reconciliation_scope"
            elif not _event_is_verified(
                "dispatch_reconciliation_recorded", reconciliation, verified
            ):
                status = "reconciliation_unverified"
            else:
                status = "reconciliation_pending_attempt_journal"
        elif approval is None:
            status = "proposed"
        elif lease is None or not lease.get("authorization_valid"):
            status = "blocked_lease"
        else:
            scope_problems = _dispatch_scope_problems(dispatch, lease)
            if scope_problems:
                status = "blocked_scope"
                diagnostics.extend(
                    f"dispatch_{problem}:{_subject_label(*key)}" for problem in scope_problems
                )
            elif (
                approval.get("workstream_id") != dispatch.get("workstream_id")
                or approval.get("dispatch_revision_id") != dispatch_id
                or approval.get("proposal_scope_digest") != dispatch.get("scope_digest")
                or approval.get("lease_scope_digest") != lease.get("scope_digest")
                or approval.get("lease_id") != lease.get("lease_id")
            ):
                status = "blocked_scope"
                diagnostics.append(f"dispatch_approval_scope_mismatch:{_subject_label(*key)}")
            elif not _event_is_verified("dispatch_intent_approved", approval, verified):
                status = "approval_unverified"
            else:
                try:
                    approval_expiry = _parse_time(str(approval["expires_at"]))
                    lease_expiry = _parse_time(str(lease["expires_at"]))
                except (KeyError, ValueError):
                    status = "blocked_interval"
                else:
                    if observed >= min(approval_expiry, lease_expiry):
                        status = "expired"
                    elif dispatch.get("worker_revision_id") == dispatch.get("checker_revision_id"):
                        status = "blocked_checker_independence"
                    else:
                        status = "ready_manual"
        dispatch["status"] = status
        dispatch["authorization_valid"] = status == "ready_manual"
        dispatch["manual_packet_ready"] = status == "ready_manual"
        dispatch["dispatch_allowed"] = False

    lease_rows = sorted(
        leases.values(),
        key=lambda item: (item["requested_at"], item["workstream_id"], item["lease_id"]),
    )
    dispatch_rows = sorted(
        dispatches.values(),
        key=lambda item: (
            item["proposed_at"],
            item["workstream_id"],
            item["dispatch_revision_id"],
        ),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": observed.isoformat(),
        "status": "generated_candidate",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "approval_verification": {
            "mode": "typed_event_digest_attestations",
            "default": "deny_all",
            "verified_attestation_count": len(verified),
            "bare_ids_authorize": False,
        },
        "executor": {"available": False, "dispatch_allowed": False},
        "summary": {
            "lease_count": len(lease_rows),
            "active_lease_count": sum(row["status"] == "active" for row in lease_rows),
            "dispatch_count": len(dispatch_rows),
            "manual_packet_ready_count": sum(
                row["status"] == "ready_manual" for row in dispatch_rows
            ),
        },
        "leases": lease_rows,
        "dispatches": dispatch_rows,
        "diagnostics": sorted(set(diagnostics)),
    }


def load_execution_control(
    hub_root: Path,
    *,
    as_of: datetime | None = None,
    verified_approval_records: Iterable[dict[str, Any] | str] = (),
    verified_approval_ids: Iterable[str] = (),
) -> dict[str, Any]:
    observed = _now(as_of)
    events, state = _kernel_state(hub_root, now=observed)
    return fold_execution_control(
        events,
        state.get("workstreams", []),
        as_of=observed,
        verified_approval_ids=verified_approval_ids,
        verified_approval_records=verified_approval_records,
        ledger_diagnostics=state.get("ledger_diagnostics", {}),
    )


def _transaction_projection(
    events: list[dict[str, Any]], state: dict[str, Any], *, observed: datetime
) -> dict[str, Any]:
    return fold_execution_control(
        events,
        state.get("workstreams", []),
        as_of=observed,
        ledger_diagnostics=state.get("ledger_diagnostics", {}),
    )


def request_execution_lease(
    hub_root: Path,
    workstream_id: str,
    *,
    owner_id: str,
    owner_kind: str,
    repo_binding_id: str,
    action_classes: Iterable[str],
    requested_paths: Iterable[str],
    not_before: datetime,
    expires_at: datetime,
    return_state: str,
    rationale_code: str,
    portability_assessment_id: str = "",
    portability_artifact_ids: Iterable[str] = (),
    portability_scope_digest: str = "",
    supersedes_lease_id: str = "",
    lease_id: str = "",
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(now)
    start = _now(not_before)
    expiry = _now(expires_at)
    if expiry <= start or expiry - start > MAX_LEASE_DURATION:
        raise ValueError("lease interval must be positive and at most 31 days")
    if owner_kind not in OWNER_KINDS:
        raise ValueError(f"owner_kind must be one of {OWNER_KINDS}")
    actions = _canonical_strings(action_classes, field="action_classes")
    if any(action not in ACTION_CLASSES for action in actions):
        raise ValueError(f"action_classes must be drawn from {ACTION_CLASSES}")
    paths = _repo_relative_paths(requested_paths)
    from .portfolio_attention import LIFECYCLE_STATES, TERMINAL_STATES

    if return_state not in LIFECYCLE_STATES:
        raise ValueError(f"return_state must be one of {LIFECYCLE_STATES}")
    candidate_id = lease_id or stable_id(
        "portfolio-lease", workstream_id, command_id or uuid.uuid4().hex
    )
    payload = {
        "workstream_id": workstream_id,
        "lease_id": candidate_id,
        "owner_id": owner_id,
        "owner_kind": owner_kind,
        "repo_binding_id": repo_binding_id,
        "action_classes": actions,
        "requested_paths": paths,
        "not_before": start.isoformat(),
        "expires_at": expiry.isoformat(),
        "return_state": return_state,
        "rationale_code": rationale_code,
        "supersedes_lease_id": supersedes_lease_id,
    }
    if portability_assessment_id:
        payload["portability_assessment_id"] = portability_assessment_id
        payload["portability_artifact_ids"] = _canonical_strings(
            portability_artifact_ids, field="portability_artifact_ids"
        )
        payload["portability_scope_digest"] = portability_scope_digest
    payload["scope_digest"] = lease_scope_digest(payload)

    def prepare(
        events: list[dict[str, Any]], state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        workstream = next(
            (
                row
                for row in state.get("workstreams", [])
                if row.get("workstream_id") == workstream_id
            ),
            None,
        )
        if workstream is None:
            return {"status": "unknown_workstream", "events_appended": 0}
        if workstream.get("lifecycle_state") in TERMINAL_STATES:
            return {"status": "terminal_workstream", "events_appended": 0}
        if _accepted_repo_binding(workstream, repo_binding_id) is None:
            return {"status": "accepted_repo_binding_required", "events_appended": 0}
        existing = _transaction_projection(events, state, observed=observed)
        if any(
            row.get("workstream_id") == workstream_id and row.get("lease_id") == candidate_id
            for row in existing["leases"]
        ):
            return {"status": "lease_id_exists", "events_appended": 0}
        return payload, {
            "status": "requested",
            "lease_id": candidate_id,
            "scope_digest": payload["scope_digest"],
        }

    return _atomic_control_event(
        hub_root,
        event_kind="execution_lease_requested",
        workstream_id=workstream_id,
        observed=observed,
        command_id=command_id,
        prepare=prepare,
    )


def grant_execution_lease(
    hub_root: Path,
    workstream_id: str,
    lease_id: str,
    *,
    granted_by: str,
    approval_id: str,
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(now)

    def prepare(
        events: list[dict[str, Any]], state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        projection = _transaction_projection(events, state, observed=observed)
        lease = _find_control_row(
            projection["leases"],
            workstream_id=workstream_id,
            id_field="lease_id",
            subject_id=lease_id,
        )
        if lease is None or lease.get("workstream_id") != workstream_id:
            return {"status": "unknown_lease", "events_appended": 0}
        if not lease.get("scope_valid") or lease.get("identity_conflict"):
            return {"status": "lease_invalid", "events_appended": 0}
        if lease.get("grant") is not None:
            return {"status": "lease_already_granted", "events_appended": 0}
        workstream = next(
            (
                row
                for row in state.get("workstreams", [])
                if row.get("workstream_id") == workstream_id
            ),
            None,
        )
        if workstream is None or workstream.get("lifecycle_state") != "active":
            return {"status": "active_workstream_required", "events_appended": 0}
        if _accepted_repo_binding(workstream, str(lease["repo_binding_id"])) is None:
            return {"status": "accepted_repo_binding_required", "events_appended": 0}
        if observed >= _parse_time(str(lease["expires_at"])):
            return {"status": "lease_expired", "events_appended": 0}
        payload = {
            "workstream_id": workstream_id,
            "lease_id": lease_id,
            "scope_digest": lease["scope_digest"],
            "granted_by": granted_by,
            "approval_id": approval_id,
        }
        return payload, {"status": "recorded_approval_unverified", "lease_id": lease_id}

    return _atomic_control_event(
        hub_root,
        event_kind="execution_lease_granted",
        workstream_id=workstream_id,
        observed=observed,
        command_id=command_id,
        prepare=prepare,
    )


def revoke_execution_lease(
    hub_root: Path,
    workstream_id: str,
    lease_id: str,
    *,
    revoked_by: str,
    approval_id: str,
    reason_code: str,
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(now)

    def prepare(
        events: list[dict[str, Any]], state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        projection = _transaction_projection(events, state, observed=observed)
        lease = _find_control_row(
            projection["leases"],
            workstream_id=workstream_id,
            id_field="lease_id",
            subject_id=lease_id,
        )
        if lease is None or lease.get("workstream_id") != workstream_id:
            return {"status": "unknown_lease", "events_appended": 0}
        if lease.get("revocation") is not None:
            return {"status": "already_revoked", "events_appended": 0}
        payload = {
            "workstream_id": workstream_id,
            "lease_id": lease_id,
            "revoked_by": revoked_by,
            "approval_id": approval_id,
            "reason_code": reason_code,
        }
        return payload, {"status": "revoked_fail_closed", "lease_id": lease_id}

    return _atomic_control_event(
        hub_root,
        event_kind="execution_lease_revoked",
        workstream_id=workstream_id,
        observed=observed,
        command_id=command_id,
        prepare=prepare,
    )


def propose_dispatch_intent(
    hub_root: Path,
    workstream_id: str,
    *,
    lease_id: str,
    repo_binding_id: str,
    action: str,
    worker_revision_id: str,
    checker_revision_id: str,
    task_summary: str,
    requested_paths: Iterable[str],
    acceptance_refs: Iterable[str],
    validation_commands: Iterable[str],
    authority_refs: Iterable[str],
    expected_repo_snapshot: str,
    forbidden_actions: Iterable[str] = (),
    dispatch_revision_id: str = "",
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(now)
    if worker_revision_id == checker_revision_id:
        return {"status": "independent_checker_required", "events_appended": 0}
    paths = _repo_relative_paths(requested_paths)
    dispatch_id = dispatch_revision_id or stable_id(
        "portfolio-dispatch", workstream_id, command_id or uuid.uuid4().hex
    )

    def prepare(
        events: list[dict[str, Any]], state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        projection = _transaction_projection(events, state, observed=observed)
        lease = _find_control_row(
            projection["leases"],
            workstream_id=workstream_id,
            id_field="lease_id",
            subject_id=lease_id,
        )
        if lease is None or lease.get("workstream_id") != workstream_id:
            return {"status": "unknown_lease", "events_appended": 0}
        if lease.get("identity_conflict") or not lease.get("scope_valid"):
            return {"status": "lease_invalid", "events_appended": 0}
        if lease.get("owner_kind") == "agent" and worker_revision_id != lease.get("owner_id"):
            return {"status": "worker_not_lease_owner", "events_appended": 0}
        if lease.get("grant") is None:
            return {"status": "lease_grant_required", "events_appended": 0}
        if action not in lease.get("action_classes", []):
            return {"status": "action_outside_lease", "events_appended": 0}
        if repo_binding_id != lease.get("repo_binding_id"):
            return {"status": "repo_binding_scope_mismatch", "events_appended": 0}
        if any(
            not any(_path_is_within(path, str(root)) for root in lease.get("requested_paths", []))
            for path in paths
        ):
            return {"status": "path_outside_lease", "events_appended": 0}
        if any(
            row.get("workstream_id") == workstream_id
            and row.get("dispatch_revision_id") == dispatch_id
            for row in projection["dispatches"]
        ):
            return {"status": "dispatch_revision_id_exists", "events_appended": 0}
        payload = {
            "workstream_id": workstream_id,
            "dispatch_revision_id": dispatch_id,
            "lease_id": lease_id,
            "repo_binding_id": repo_binding_id,
            "action": action,
            "worker_revision_id": worker_revision_id,
            "checker_revision_id": checker_revision_id,
            "task_summary": task_summary.strip(),
            "requested_paths": paths,
            "acceptance_refs": _canonical_strings(acceptance_refs, field="acceptance_refs"),
            "validation_commands": _canonical_strings(
                validation_commands, field="validation_commands"
            ),
            "authority_refs": _canonical_strings(authority_refs, field="authority_refs"),
            "expected_repo_snapshot": expected_repo_snapshot.strip(),
            "forbidden_actions": sorted(
                set(DEFAULT_FORBIDDEN_ACTIONS)
                | set(
                    _canonical_strings(
                        forbidden_actions, field="forbidden_actions", allow_empty=True
                    )
                )
            ),
        }
        payload["scope_digest"] = dispatch_scope_digest(payload)
        return payload, {
            "status": "proposed",
            "dispatch_revision_id": dispatch_id,
            "scope_digest": payload["scope_digest"],
        }

    return _atomic_control_event(
        hub_root,
        event_kind="dispatch_intent_proposed",
        workstream_id=workstream_id,
        observed=observed,
        command_id=command_id,
        prepare=prepare,
    )


def approve_dispatch_intent(
    hub_root: Path,
    workstream_id: str,
    dispatch_revision_id: str,
    *,
    approved_by: str,
    approval_id: str,
    expires_at: datetime,
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(now)
    expiry = _now(expires_at)

    def prepare(
        events: list[dict[str, Any]], state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        projection = _transaction_projection(events, state, observed=observed)
        dispatch = _find_control_row(
            projection["dispatches"],
            workstream_id=workstream_id,
            id_field="dispatch_revision_id",
            subject_id=dispatch_revision_id,
        )
        if dispatch is None or dispatch.get("workstream_id") != workstream_id:
            return {"status": "unknown_dispatch", "events_appended": 0}
        if dispatch.get("identity_conflict") or not dispatch.get("scope_valid"):
            return {"status": "dispatch_invalid", "events_appended": 0}
        if dispatch.get("approval") is not None:
            return {"status": "dispatch_already_approved", "events_appended": 0}
        lease = _find_control_row(
            projection["leases"],
            workstream_id=workstream_id,
            id_field="lease_id",
            subject_id=str(dispatch["lease_id"]),
        )
        if lease is None or expiry <= observed or expiry > _parse_time(str(lease["expires_at"])):
            return {"status": "approval_expiry_outside_lease", "events_appended": 0}
        payload = {
            "workstream_id": workstream_id,
            "dispatch_revision_id": dispatch_revision_id,
            "lease_id": dispatch["lease_id"],
            "proposal_scope_digest": dispatch["scope_digest"],
            "lease_scope_digest": lease["scope_digest"],
            "approved_by": approved_by,
            "approval_id": approval_id,
            "expires_at": expiry.isoformat(),
        }
        return payload, {
            "status": "recorded_approval_unverified",
            "dispatch_revision_id": dispatch_revision_id,
        }

    return _atomic_control_event(
        hub_root,
        event_kind="dispatch_intent_approved",
        workstream_id=workstream_id,
        observed=observed,
        command_id=command_id,
        prepare=prepare,
    )


def revoke_dispatch_intent(
    hub_root: Path,
    workstream_id: str,
    dispatch_revision_id: str,
    *,
    revoked_by: str,
    approval_id: str,
    reason_code: str,
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = _now(now)

    def prepare(
        events: list[dict[str, Any]], state: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        projection = _transaction_projection(events, state, observed=observed)
        dispatch = _find_control_row(
            projection["dispatches"],
            workstream_id=workstream_id,
            id_field="dispatch_revision_id",
            subject_id=dispatch_revision_id,
        )
        if dispatch is None or dispatch.get("workstream_id") != workstream_id:
            return {"status": "unknown_dispatch", "events_appended": 0}
        if dispatch.get("revocation") is not None:
            return {"status": "already_revoked", "events_appended": 0}
        payload = {
            "workstream_id": workstream_id,
            "dispatch_revision_id": dispatch_revision_id,
            "revoked_by": revoked_by,
            "approval_id": approval_id,
            "reason_code": reason_code,
        }
        return payload, {
            "status": "revoked_fail_closed",
            "dispatch_revision_id": dispatch_revision_id,
        }

    return _atomic_control_event(
        hub_root,
        event_kind="dispatch_intent_revoked",
        workstream_id=workstream_id,
        observed=observed,
        command_id=command_id,
        prepare=prepare,
    )


def dispatch_packet(projection: dict[str, Any], dispatch_revision_id: str) -> dict[str, Any]:
    matches = [
        row
        for row in projection["dispatches"]
        if row["dispatch_revision_id"] == dispatch_revision_id
    ]
    if not matches:
        return {"status": "unknown_dispatch", "dispatch_revision_id": dispatch_revision_id}
    if len(matches) != 1:
        return {"status": "ambiguous_dispatch", "dispatch_revision_id": dispatch_revision_id}
    dispatch = matches[0]
    return {
        "schema_version": "dad.portfolio_dispatch_packet.v1",
        "status": dispatch["status"],
        "manual_packet_ready": dispatch["manual_packet_ready"],
        "dispatch_allowed": False,
        "dispatch": dispatch,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def write_execution_control_outputs(hub_root: Path, projection: dict[str, Any]) -> dict[str, str]:
    root = hub_root / "processed" / "reports" / "portfolio_os"
    json_path = root / "execution_control.json"
    html_path = root / "execution_control.html"
    atomic_write_text(json_path, json_dumps(projection, indent=2) + "\n")
    lease_rows = (
        "".join(
            f"<tr><td><code>{escape(row['lease_id'])}</code></td><td>{escape(row['status'])}</td><td>{escape(row['owner_id'])}</td></tr>"
            for row in projection["leases"]
        )
        or "<tr><td colspan='3'>No leases</td></tr>"
    )
    dispatch_rows = (
        "".join(
            f"<tr><td><code>{escape(row['dispatch_revision_id'])}</code></td><td>{escape(row['status'])}</td><td>{escape(row['action'])}</td></tr>"
            for row in projection["dispatches"]
        )
        or "<tr><td colspan='3'>No dispatch intents</td></tr>"
    )
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>DAD Execution Control</title>
<style>body{{font:15px system-ui;margin:2rem;background:#101418;color:#eef}}table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}th,td{{border:1px solid #3a4652;padding:.5rem;text-align:left}}code{{color:#9de}}</style></head><body>
<h1>Execution Control</h1><p>{escape(AUTHORITY_BOUNDARY)}</p>
<p>Executor available: <strong>no</strong>. Verified attestations: {projection["approval_verification"]["verified_attestation_count"]}.</p>
<h2>Leases</h2><table><tr><th>ID</th><th>Status</th><th>Owner</th></tr>{lease_rows}</table>
<h2>Dispatch intents</h2><table><tr><th>ID</th><th>Status</th><th>Action</th></tr>{dispatch_rows}</table></body></html>"""
    atomic_write_text(html_path, html)
    return {"json_path": str(json_path), "html_path": str(html_path)}


__all__ = [
    "ACTION_CLASSES",
    "AUTHORITY_BOUNDARY",
    "DEFAULT_FORBIDDEN_ACTIONS",
    "MAX_LEASE_DURATION",
    "SCHEMA_VERSION",
    "approve_dispatch_intent",
    "dispatch_packet",
    "dispatch_scope_digest",
    "fold_execution_control",
    "grant_execution_lease",
    "lease_scope_digest",
    "load_execution_control",
    "propose_dispatch_intent",
    "request_execution_lease",
    "revoke_dispatch_intent",
    "authority_attestation_digest",
    "revoke_execution_lease",
    "write_execution_control_outputs",
]
