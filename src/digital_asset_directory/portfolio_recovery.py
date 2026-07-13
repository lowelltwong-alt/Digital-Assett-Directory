"""Strict, non-executing recovery decisions for the Portfolio OS.

Recovery decisions share the existing hash-chained workstream ledger but use a
separate registered envelope family.  This module can record a human decision,
retract it, emit a transient digest-bound manual packet, and record an
independently checked result.  It never resolves a filesystem path, constructs
a command, touches Git, or grants execution authority.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .ids import stable_id
from .portfolio_events import (
    EventConflictError,
    LedgerIntegrityError,
    RECOVERY_EVENT_KINDS,
    append_events,
    build_event,
    canonical_command_id,
    ledger_path,
    read_events,
)

PACKET_SCHEMA_VERSION = "dad.portfolio_recovery_packet.v1"
DECISION_STATES = frozenset({"active", "retracted", "stale"})
RESULT_STATUSES = frozenset({"verified", "failed", "aborted"})
DISPOSITIONS = frozenset({"approved", "deferred", "rejected"})
PACKET_PRECONDITIONS = (
    "case_revision_matches",
    "expected_preconditions_match",
    "human_approval_required",
    "independent_checker_required",
    "source_snapshot_matches",
)
MAX_PACKET_LIFETIME = timedelta(days=7)
MAX_SHAPING_SOURCE_AGE = timedelta(hours=26)
MAX_SHAPING_SOURCE_FUTURE_SKEW = timedelta(hours=1)

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,199}$")
_STABLE_ID_RE = re.compile(r"^dad:[A-Za-z0-9_.:-]+:[0-9a-f-]{36}$")
_DECISION_ID_RE = re.compile(r"^dad:portfolio-decision:[0-9a-f-]{36}$")
_PACKET_ID_RE = re.compile(r"^dad:portfolio-recovery-packet:[0-9a-f-]{36}$")
_FORBIDDEN_PACKET_KEYS = frozenset(
    {
        "command",
        "commands",
        "file",
        "filename",
        "files",
        "instruction",
        "instructions",
        "path",
        "paths",
        "prose",
        "script",
        "shell",
    }
)


class RecoveryValidationError(ValueError):
    """A requested recovery operation failed its strict input contract."""


class RecoveryStateError(LedgerIntegrityError):
    """Current decision or shaping state makes the operation unsafe."""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RecoveryValidationError("Recovery input must be finite JSON data.") from exc


def _digest(value: Any) -> str:
    encoded = _canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _utc(value: datetime | None) -> datetime:
    observed = value or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise RecoveryValidationError("timestamps must include a timezone")
    return observed.astimezone(timezone.utc)


def _parse_time(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryValidationError(f"{field} must be an ISO date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecoveryValidationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _optional_time(value: datetime | str | None, *, field: str) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    return _parse_time(str(value), field=field).isoformat()


def _require_token(value: Any, *, field: str) -> str:
    token = str(value).strip()
    if not _TOKEN_RE.fullmatch(token):
        raise RecoveryValidationError(f"{field} must be an opaque categorical token")
    return token


def _require_digest(value: Any, *, field: str) -> str:
    digest = str(value)
    if not _DIGEST_RE.fullmatch(digest):
        raise RecoveryValidationError(f"{field} must be a sha256 digest")
    return digest


def _case_rows(shaping: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for value in shaping.get("cases", []):
        if not isinstance(value, dict) or not value.get("case_id"):
            continue
        case_id = str(value["case_id"])
        if case_id in rows:
            raise RecoveryValidationError(f"duplicate shaping case: {case_id}")
        rows[case_id] = value
    return rows


def shaping_source_snapshot_digest(
    shaping: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    """Digest only the frozen source plane, never decision-derived v2 fields."""

    observed = _utc(now)
    schema_version = str(shaping.get("schema_version", ""))
    if not schema_version.startswith("dad.portfolio_workstream_shaping.v"):
        raise RecoveryValidationError("unsupported shaping projection schema")
    if shaping.get("status") not in {"generated_candidate", "partial_candidate"}:
        raise RecoveryValidationError("shaping projection is not decision-ready")
    source_refs = shaping.get("source_refs")
    sources = shaping.get("sources")
    if not isinstance(source_refs, dict) or not isinstance(sources, dict):
        raise RecoveryValidationError("shaping projection lacks strict source descriptors")
    required_sources = ("workstreams", "cockpit", "reconciliation")
    if any(not str(source_refs.get(name, "")) for name in required_sources):
        raise RecoveryValidationError("shaping source snapshot is incomplete")
    descriptors: dict[str, dict[str, Any]] = {}
    for name in required_sources:
        descriptor = sources.get(name)
        if not isinstance(descriptor, dict):
            raise RecoveryValidationError(f"shaping source descriptor is missing: {name}")
        if str(descriptor.get("source_hash", "")) != str(source_refs[name]):
            raise RecoveryValidationError(f"shaping source hash mismatch: {name}")
        if descriptor.get("status") != "observed" or descriptor.get("freshness") != "current":
            raise RecoveryValidationError(f"shaping source is not current: {name}")
        if not _DIGEST_RE.fullmatch(str(descriptor.get("source_hash", ""))):
            raise RecoveryValidationError(f"shaping source digest is invalid: {name}")
        generated_at = _parse_time(
            str(descriptor.get("generated_at", "")), field=f"sources.{name}.generated_at"
        )
        if generated_at > observed + MAX_SHAPING_SOURCE_FUTURE_SKEW:
            raise RecoveryValidationError(f"shaping source is future-dated: {name}")
        if observed - generated_at > MAX_SHAPING_SOURCE_AGE:
            raise RecoveryValidationError(f"shaping source is stale by observed time: {name}")
        descriptors[name] = {
            key: descriptor.get(key, "")
            for key in (
                "status",
                "freshness",
                "schema_version",
                "generated_at",
                "source_hash",
            )
        }
    coupling = shaping.get("source_coupling")
    if not isinstance(coupling, dict):
        raise RecoveryValidationError("shaping source coupling is missing")
    for name in ("workstreams_to_cockpit", "cockpit_to_reconciliation"):
        link = coupling.get(name)
        if not isinstance(link, dict) or link.get("matches") is not True:
            raise RecoveryValidationError(f"shaping source coupling is not exact: {name}")
    return _digest(
        {
            "schema_version": schema_version,
            "source_refs": {name: source_refs[name] for name in required_sources},
            "sources": descriptors,
            "source_coupling": coupling,
        }
    )


def case_preconditions_digest(case: Mapping[str, Any]) -> str:
    """Digest case evidence and canonical choices, excluding decision overlays."""

    keys = (
        "case_id",
        "revision_id",
        "case_kind",
        "evidence_tier",
        "disposition",
        "subject_workstream_ids",
        "subject_resource_ids",
        "source_attention_ids",
        "source_bundle_ids",
        "signals",
        "counterevidence",
        "evidence_summary",
        "choices",
    )
    return _digest({key: case.get(key) for key in keys})


def validate_shaping_selection(
    shaping: Mapping[str, Any],
    *,
    case_id: str,
    case_revision_id: str,
    source_snapshot_digest: str,
    expected_preconditions_digest: str,
    choice_id: str,
    choice_kind: str,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reject every stale or noncanonical part of one requested choice."""

    if shaping.get("execution_authorized") is not False:
        raise RecoveryStateError("shaping projection does not preserve deny-all authority")
    if shaping.get("source_authority_mutated") is not False:
        raise RecoveryStateError("shaping projection reports source-authority mutation")
    current_source_digest = shaping_source_snapshot_digest(shaping, now=now)
    if source_snapshot_digest != current_source_digest:
        raise RecoveryStateError("stale shaping source snapshot")
    case = _case_rows(shaping).get(case_id)
    if case is None:
        raise RecoveryStateError(f"shaping case is missing: {case_id}")
    if str(case.get("revision_id", "")) != case_revision_id:
        raise RecoveryStateError("stale shaping case revision")
    if case_preconditions_digest(case) != expected_preconditions_digest:
        raise RecoveryStateError("stale shaping case preconditions")
    choices = [
        row
        for row in case.get("choices", [])
        if isinstance(row, dict) and str(row.get("choice_id", "")) == choice_id
    ]
    if len(choices) != 1:
        raise RecoveryStateError("choice is not canonical for the shaping case")
    choice = choices[0]
    if str(choice.get("choice_kind", "")) != choice_kind:
        raise RecoveryStateError("choice kind does not match the canonical choice")
    if choice.get("execution_available") is not False:
        raise RecoveryStateError("shaping choice unexpectedly exposes execution")
    if choice.get("requires_human_decision") is not True:
        raise RecoveryStateError("shaping choice bypasses the human decision gate")
    return case, choice


def _ledger_diagnostic_problems(diagnostics: Mapping[str, Any] | None) -> list[str]:
    if not diagnostics:
        return []
    problems = [str(value) for value in diagnostics.get("problems", [])]
    if diagnostics.get("torn_tail_pending"):
        problems.append("torn_tail_pending")
    return sorted(set(problems))


def fold_recovery_events(
    events: Iterable[dict[str, Any]],
    shaping: Mapping[str, Any] | None = None,
    *,
    ledger_diagnostics: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Purely fold decision events and optionally mark stale active decisions."""

    decisions: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}
    packet_ids: set[str] = set()
    problems = _ledger_diagnostic_problems(ledger_diagnostics)

    for event in events:
        kind = str(event.get("event_kind", ""))
        if kind not in RECOVERY_EVENT_KINDS:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            problems.append(f"invalid_recovery_payload:{event.get('event_id', '')}")
            continue
        decision_id = str(payload.get("decision_id", ""))
        case_id = str(payload.get("case_id", ""))

        if kind == "shaping_decision_recorded":
            if decision_id in decisions:
                problems.append(f"duplicate_decision_id:{decision_id}")
                continue
            supersedes = str(payload.get("supersedes_decision_id", ""))
            active_for_case = [
                row
                for row in decisions.values()
                if row["case_id"] == case_id and row["status"] == "active"
            ]
            if supersedes:
                prior = decisions.get(supersedes)
                if prior is None or prior["case_id"] != case_id or prior["status"] != "active":
                    problems.append(f"invalid_superseded_decision:{decision_id}")
                    continue
                prior["status"] = "retracted"
                prior["retraction_reason"] = "superseded"
                prior["superseded_by_decision_id"] = decision_id
            elif active_for_case:
                problems.append(f"active_decision_requires_supersession:{case_id}")
                continue
            decisions[decision_id] = {
                "decision_id": decision_id,
                "case_id": case_id,
                "case_revision_id": str(payload.get("case_revision_id", "")),
                "source_snapshot_digest": str(payload.get("source_snapshot_digest", "")),
                "shaping_source_snapshot_digest": str(payload.get("source_snapshot_digest", "")),
                "expected_preconditions_digest": str(
                    payload.get("expected_preconditions_digest", "")
                ),
                "choice_id": str(payload.get("choice_id", "")),
                "choice_kind": str(payload.get("choice_kind", "")),
                "status": "active",
                "disposition": str(payload.get("disposition", "")),
                "review_after": str(payload.get("review_after", "")),
                "approver": str(payload.get("approver", "")),
                "approval_ref": str(payload.get("approval_ref", "")),
                "supersedes_decision_id": supersedes,
                "recorded_at": str(event.get("recorded_at", "")),
                "event_id": str(event.get("event_id", "")),
            }
            continue

        decision = decisions.get(decision_id)
        if decision is None or decision["case_id"] != case_id:
            problems.append(f"unknown_decision_reference:{decision_id}")
            continue
        if kind == "shaping_decision_retracted":
            if decision["status"] == "retracted":
                problems.append(f"decision_already_retracted:{decision_id}")
                continue
            decision["status"] = "retracted"
            decision["retracted_at"] = str(event.get("recorded_at", ""))
            decision["retracted_by"] = str(payload.get("retracted_by", ""))
            decision["retraction_reason"] = str(payload.get("reason_code", ""))
            decision["retraction_event_id"] = str(event.get("event_id", ""))
            continue

        packet_id = str(payload.get("packet_id", ""))
        result_id = str(payload.get("result_id", ""))
        if decision["status"] != "active":
            problems.append(f"result_for_inactive_decision:{decision_id}")
            continue
        if str(payload.get("worker_id", "")) == str(payload.get("checker_id", "")):
            problems.append(f"worker_checker_not_distinct:{result_id}")
            continue
        if result_id in results or packet_id in packet_ids:
            problems.append(f"duplicate_recovery_result:{result_id or packet_id}")
            continue
        status = str(payload.get("result_status", ""))
        results[result_id] = {
            "result_id": result_id,
            "decision_id": decision_id,
            "case_id": case_id,
            "packet_id": packet_id,
            "status": status,
            "result_status": status,
            "before_snapshot_digest": str(payload.get("before_snapshot_digest", "")),
            "after_snapshot_digest": str(payload.get("after_snapshot_digest", "")),
            "worker_id": str(payload.get("worker_id", "")),
            "checker_id": str(payload.get("checker_id", "")),
            "evidence_refs": list(payload.get("evidence_refs", [])),
            "recorded_at": str(event.get("recorded_at", "")),
            "event_id": str(event.get("event_id", "")),
        }
        packet_ids.add(packet_id)

    if shaping is not None:
        for decision in decisions.values():
            if decision["status"] != "active":
                continue
            try:
                validate_shaping_selection(
                    shaping,
                    case_id=decision["case_id"],
                    case_revision_id=decision["case_revision_id"],
                    source_snapshot_digest=decision["source_snapshot_digest"],
                    expected_preconditions_digest=decision["expected_preconditions_digest"],
                    choice_id=decision["choice_id"],
                    choice_kind=decision["choice_kind"],
                    now=now,
                )
            except (RecoveryStateError, RecoveryValidationError):
                decision["status"] = "stale"

    ordered_decisions = sorted(
        decisions.values(), key=lambda row: (row["recorded_at"], row["decision_id"])
    )
    ordered_results = sorted(
        results.values(), key=lambda row: (row["recorded_at"], row["result_id"])
    )
    return {
        "schema_version": "dad.portfolio_recovery_projection.v1",
        "status": "blocked" if problems else "ready",
        "execution_authorized": False,
        "mutations_performed": False,
        "source_authority_mutated": False,
        "decisions": ordered_decisions,
        "results": ordered_results,
        "diagnostics": sorted(set(problems)),
    }


def load_recovery_projection(
    hub_root: Path,
    shaping: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    events, diagnostics = read_events(ledger_path(hub_root))
    return fold_recovery_events(events, shaping, ledger_diagnostics=diagnostics, now=now)


def _load_projection_before_append(
    hub_root: Path,
    shaping: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read the strict ledger prefix without concealing any integrity diagnostic."""

    events, diagnostics = read_events(ledger_path(hub_root))
    return fold_recovery_events(
        events,
        shaping,
        ledger_diagnostics=diagnostics,
        now=now,
    )


def _prior_command_event(
    events: Iterable[dict[str, Any]], event: Mapping[str, Any]
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in events
            if row.get("stream_id") == event.get("stream_id")
            and row.get("command_id") == event.get("command_id")
        ),
        None,
    )


def _strict_prior_command_event(
    hub_root: Path,
    *,
    command_id: str,
    stream_id: str | None,
) -> dict[str, Any] | None:
    """Find a prior command without repairing or ignoring unsafe ledger state."""

    events, diagnostics = read_events(ledger_path(hub_root))
    problems = _ledger_diagnostic_problems(diagnostics)
    if problems:
        raise RecoveryStateError("Recovery ledger is unsafe to extend: " + "|".join(problems))
    normalized_command_id = canonical_command_id(command_id)
    matches = [
        event
        for event in events
        if event.get("command_id") == normalized_command_id
        and (stream_id is None or event.get("stream_id") == stream_id)
    ]
    if len(matches) > 1:
        raise EventConflictError("command_id is ambiguous without an exact recovery stream")
    return matches[0] if matches else None


def _require_exact_retry(
    prior: Mapping[str, Any],
    *,
    event_kind: str,
    payload: Mapping[str, Any],
) -> None:
    if prior.get("event_kind") != event_kind or prior.get("payload") != payload:
        raise EventConflictError("command_id conflicts with an earlier recovery operation")


def _deduplicated_append_result() -> dict[str, int]:
    return {
        "events_appended": 0,
        "events_deduplicated": 1,
        "tail_fragments_quarantined": 0,
        "corrupt_line_count": 0,
        "invalid_envelope_count": 0,
    }


def _append_recovery_event(
    hub_root: Path,
    event: dict[str, Any],
    *,
    recorded_at: str,
    shaping: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = event["payload"]
    kind = str(event["event_kind"])
    operation_time = _parse_time(recorded_at, field="recorded_at")

    def validate_existing(events: list[dict[str, Any]], diagnostics: dict[str, Any]) -> None:
        diagnostic_problems = _ledger_diagnostic_problems(diagnostics)
        if diagnostic_problems:
            raise RecoveryStateError(
                "Recovery decision ledger is not safe to extend: "
                + "|".join(diagnostic_problems)
            )
        prior_command = _prior_command_event(events, event)
        if prior_command is not None:
            if prior_command.get("event_kind") == event.get("event_kind") and prior_command.get(
                "payload"
            ) == event.get("payload"):
                return
            raise EventConflictError("command_id conflicts with an earlier recovery operation")
        projection = fold_recovery_events(
            events,
            shaping,
            ledger_diagnostics=diagnostics,
            now=operation_time,
        )
        if projection["diagnostics"]:
            raise RecoveryStateError(
                "Recovery decision fold is not safe to extend: "
                + "|".join(projection["diagnostics"])
            )
        decisions = {row["decision_id"]: row for row in projection["decisions"]}
        decision_id = str(payload["decision_id"])
        case_id = str(payload["case_id"])
        if kind == "shaping_decision_recorded":
            if decision_id in decisions:
                raise RecoveryStateError(f"decision_id already exists: {decision_id}")
            unretracted = [
                row
                for row in decisions.values()
                if row["case_id"] == case_id and row["status"] in {"active", "stale"}
            ]
            supersedes = str(payload["supersedes_decision_id"])
            if supersedes:
                prior = decisions.get(supersedes)
                if (
                    prior is None
                    or prior["case_id"] != case_id
                    or prior["status"] not in {"active", "stale"}
                ):
                    raise RecoveryStateError("superseded decision is not the active case decision")
            elif unretracted:
                raise RecoveryStateError("an active case decision requires explicit supersession")
            return
        decision = decisions.get(decision_id)
        if decision is None or decision["case_id"] != case_id:
            raise RecoveryStateError(f"decision is missing for case: {decision_id}")
        if kind == "shaping_decision_retracted":
            if decision["status"] == "retracted":
                raise RecoveryStateError(f"decision is already retracted: {decision_id}")
            return
        if decision["status"] != "active":
            raise RecoveryStateError("manual result requires a current active decision")
        if any(row["packet_id"] == payload["packet_id"] for row in projection["results"]):
            raise RecoveryStateError("recovery packet already has a recorded result")

    return append_events(
        ledger_path(hub_root),
        [event],
        recorded_at=recorded_at,
        validate_existing=validate_existing,
        repair_torn_tail=False,
    )


def record_shaping_decision(
    hub_root: Path,
    shaping: Mapping[str, Any],
    *,
    case_id: str,
    case_revision_id: str,
    choice_id: str,
    approver: str,
    approval_ref: str,
    command_id: str,
    choice_kind: str | None = None,
    disposition: str | None = None,
    review_after: datetime | str | None = None,
    supersedes_decision_id: str = "",
    expected_source_snapshot_digest: str | None = None,
    expected_preconditions_digest: str | None = None,
    decision_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record one exact canonical shaping choice in the shared ledger."""

    observed = _utc(now)
    review_value = _optional_time(review_after, field="review_after")
    approver_value = _require_token(approver, field="approver")
    approval_value = _require_token(approval_ref, field="approval_ref")
    supersedes_value = str(supersedes_decision_id)
    prior_command = _strict_prior_command_event(
        hub_root,
        command_id=command_id,
        stream_id=case_id,
    )
    if prior_command is not None:
        prior_payload = prior_command.get("payload")
        if not isinstance(prior_payload, dict):
            raise EventConflictError("prior recovery command has no valid payload")
        requested_source = expected_source_snapshot_digest or str(
            prior_payload.get("source_snapshot_digest", "")
        )
        requested_preconditions = expected_preconditions_digest or str(
            prior_payload.get("expected_preconditions_digest", "")
        )
        canonical_choice_kind = choice_kind or str(prior_payload.get("choice_kind", ""))
        final_disposition = disposition or str(prior_payload.get("disposition", ""))
        resolved_decision_id = decision_id or stable_id(
            "portfolio-decision",
            case_id,
            case_revision_id,
            requested_source,
            requested_preconditions,
            choice_id,
            canonical_choice_kind,
            final_disposition,
            review_value,
            approver_value,
            approval_value,
        )
        payload = {
            "decision_id": resolved_decision_id,
            "case_id": case_id,
            "case_revision_id": case_revision_id,
            "source_snapshot_digest": requested_source,
            "expected_preconditions_digest": requested_preconditions,
            "choice_id": choice_id,
            "choice_kind": canonical_choice_kind,
            "disposition": final_disposition,
            "review_after": review_value,
            "approver": approver_value,
            "approval_ref": approval_value,
            "supersedes_decision_id": supersedes_value,
        }
        _require_exact_retry(
            prior_command,
            event_kind="shaping_decision_recorded",
            payload=payload,
        )
        return {
            "status": "deduplicated",
            "decision_id": resolved_decision_id,
            "case_id": case_id,
            "source_snapshot_digest": requested_source,
            "expected_preconditions_digest": requested_preconditions,
            **_deduplicated_append_result(),
        }

    case = _case_rows(shaping).get(case_id)
    if case is None:
        raise RecoveryStateError(f"shaping case is missing: {case_id}")
    matching = [
        row
        for row in case.get("choices", [])
        if isinstance(row, dict) and str(row.get("choice_id", "")) == choice_id
    ]
    if len(matching) != 1:
        raise RecoveryStateError("choice is not canonical for the shaping case")
    canonical_choice_kind = str(matching[0].get("choice_kind", ""))
    if choice_kind is not None and choice_kind != canonical_choice_kind:
        raise RecoveryStateError("requested choice kind does not match the canonical choice")
    source_digest = shaping_source_snapshot_digest(shaping, now=observed)
    preconditions_digest = case_preconditions_digest(case)
    requested_source = expected_source_snapshot_digest or source_digest
    requested_preconditions = expected_preconditions_digest or preconditions_digest
    validate_shaping_selection(
        shaping,
        case_id=case_id,
        case_revision_id=case_revision_id,
        source_snapshot_digest=requested_source,
        expected_preconditions_digest=requested_preconditions,
        choice_id=choice_id,
        choice_kind=canonical_choice_kind,
        now=observed,
    )
    final_disposition = disposition or (
        "deferred" if canonical_choice_kind == "defer" else "approved"
    )
    if final_disposition not in DISPOSITIONS:
        raise RecoveryValidationError(f"unknown decision disposition: {final_disposition}")
    resolved_decision_id = decision_id or stable_id(
        "portfolio-decision",
        case_id,
        case_revision_id,
        requested_source,
        requested_preconditions,
        choice_id,
        canonical_choice_kind,
        final_disposition,
        review_value,
        approver_value,
        approval_value,
    )
    payload = {
        "decision_id": resolved_decision_id,
        "case_id": case_id,
        "case_revision_id": case_revision_id,
        "source_snapshot_digest": requested_source,
        "expected_preconditions_digest": requested_preconditions,
        "choice_id": choice_id,
        "choice_kind": canonical_choice_kind,
        "disposition": final_disposition,
        "review_after": review_value,
        "approver": approver_value,
        "approval_ref": approval_value,
        "supersedes_decision_id": supersedes_value,
    }
    event, _ = build_event(
        event_kind="shaping_decision_recorded",
        stream_id=case_id,
        payload=payload,
        prev_event_id="",
        recorded_at=observed.isoformat(),
        command_id=command_id,
    )
    result = _append_recovery_event(
        hub_root,
        event,
        recorded_at=observed.isoformat(),
        shaping=shaping,
    )
    return {
        "status": "recorded" if result["events_appended"] else "deduplicated",
        "decision_id": resolved_decision_id,
        "case_id": case_id,
        "source_snapshot_digest": requested_source,
        "expected_preconditions_digest": requested_preconditions,
        **result,
    }


def retract_shaping_decision(
    hub_root: Path,
    decision_id: str,
    *,
    retracted_by: str,
    approval_ref: str,
    reason_code: str,
    command_id: str,
    case_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Retract an existing decision without requiring the old case to survive."""

    retracted_by_value = _require_token(retracted_by, field="retracted_by")
    approval_value = _require_token(approval_ref, field="approval_ref")
    reason_value = _require_token(reason_code, field="reason_code")
    prior_command = _strict_prior_command_event(
        hub_root,
        command_id=command_id,
        stream_id=case_id,
    )
    if prior_command is not None:
        resolved_case_id = case_id or str(prior_command.get("stream_id", ""))
        payload = {
            "decision_id": decision_id,
            "case_id": resolved_case_id,
            "retracted_by": retracted_by_value,
            "approval_ref": approval_value,
            "reason_code": reason_value,
        }
        _require_exact_retry(
            prior_command,
            event_kind="shaping_decision_retracted",
            payload=payload,
        )
        return {
            "status": "deduplicated",
            "decision_id": decision_id,
            "case_id": resolved_case_id,
            **_deduplicated_append_result(),
        }

    projection = _load_projection_before_append(hub_root, now=now)
    if projection["diagnostics"]:
        raise RecoveryStateError(
            "Recovery ledger is unsafe to extend: " + "|".join(projection["diagnostics"])
        )
    decision = next(
        (row for row in projection["decisions"] if row["decision_id"] == decision_id),
        None,
    )
    if decision is None:
        raise RecoveryStateError(f"decision does not exist: {decision_id}")
    resolved_case_id = case_id or str(decision["case_id"])
    if resolved_case_id != decision["case_id"]:
        raise RecoveryStateError("decision does not belong to the requested case")
    observed = _utc(now)
    payload = {
        "decision_id": decision_id,
        "case_id": resolved_case_id,
        "retracted_by": retracted_by_value,
        "approval_ref": approval_value,
        "reason_code": reason_value,
    }
    event, _ = build_event(
        event_kind="shaping_decision_retracted",
        stream_id=resolved_case_id,
        payload=payload,
        prev_event_id="",
        recorded_at=observed.isoformat(),
        command_id=command_id,
    )
    result = _append_recovery_event(
        hub_root,
        event,
        recorded_at=observed.isoformat(),
    )
    return {
        "status": "retracted" if result["events_appended"] else "deduplicated",
        "decision_id": decision_id,
        "case_id": resolved_case_id,
        **result,
    }


def recovery_packet_problems(packet: Any) -> list[str]:
    """Return privacy and deny-all problems for a transient manual packet."""

    if not isinstance(packet, dict):
        return ["packet_not_object"]
    expected_keys = {
        "schema_version",
        "packet_id",
        "decision_id",
        "case_id",
        "case_revision_id",
        "source_snapshot_digest",
        "expected_preconditions_digest",
        "choice_id",
        "choice_kind",
        "action_kind",
        "disposition",
        "precondition_codes",
        "issued_at",
        "expires_at",
        "human_gate_required",
        "approval_ref",
        "independent_checker_required",
        "execution_authorized",
        "mutations_performed",
        "source_authority_mutated",
    }
    problems: set[str] = set()
    if set(packet) != expected_keys:
        problems.add("packet_fields_mismatch")
    if packet.get("schema_version") != PACKET_SCHEMA_VERSION:
        problems.add("packet_schema_mismatch")
    if packet.get("execution_authorized") is not False:
        problems.add("packet_execution_authority_mismatch")
    if packet.get("mutations_performed") is not False:
        problems.add("packet_mutation_claim_mismatch")
    if packet.get("source_authority_mutated") is not False:
        problems.add("packet_source_authority_mismatch")
    if packet.get("human_gate_required") is not True:
        problems.add("packet_human_gate_missing")
    if packet.get("independent_checker_required") is not True:
        problems.add("packet_independent_checker_missing")
    if packet.get("precondition_codes") != list(PACKET_PRECONDITIONS):
        problems.add("packet_preconditions_mismatch")
    try:
        if str(packet.get("packet_id", "")) != _deterministic_packet_id(packet):
            problems.add("packet_id_does_not_bind_exact_receipt")
    except RecoveryValidationError:
        problems.add("packet_identity_not_canonical_json")
    for key, value in packet.items():
        if key.casefold() in _FORBIDDEN_PACKET_KEYS:
            problems.add("packet_forbidden_field")
        if isinstance(value, str) and (
            "/" in value or "\\" in value or "\n" in value or "\r" in value
        ):
            problems.add("packet_path_or_prose_exposed")
    for field in ("source_snapshot_digest", "expected_preconditions_digest"):
        if not _DIGEST_RE.fullmatch(str(packet.get(field, ""))):
            problems.add(f"packet_invalid_digest:{field}")
    id_patterns = {
        "packet_id": _PACKET_ID_RE,
        "decision_id": _DECISION_ID_RE,
        "case_id": _STABLE_ID_RE,
        "case_revision_id": _STABLE_ID_RE,
        "choice_id": _STABLE_ID_RE,
    }
    for field, pattern in id_patterns.items():
        if not pattern.fullmatch(str(packet.get(field, ""))):
            problems.add(f"packet_invalid_id:{field}")
    for field in ("choice_kind", "action_kind", "approval_ref"):
        if not _TOKEN_RE.fullmatch(str(packet.get(field, ""))):
            problems.add(f"packet_invalid_token:{field}")
    if packet.get("disposition") not in DISPOSITIONS:
        problems.add("packet_invalid_disposition")
    try:
        issued_at = _parse_time(str(packet.get("issued_at", "")), field="issued_at")
        expires_at = _parse_time(str(packet.get("expires_at", "")), field="expires_at")
        if not issued_at < expires_at <= issued_at + MAX_PACKET_LIFETIME:
            problems.add("packet_expiry_invalid")
    except RecoveryValidationError:
        problems.add("packet_time_invalid")
    return sorted(problems)


def _deterministic_packet_id(packet: Mapping[str, Any]) -> str:
    """Bind every approved receipt field except the identifier itself."""

    identity_payload = {key: packet.get(key) for key in sorted(packet) if key != "packet_id"}
    return stable_id("portfolio-recovery-packet", _canonical_json(identity_payload))


def build_recovery_packet(
    hub_root: Path,
    shaping: Mapping[str, Any],
    decision_id: str,
    *,
    now: datetime | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    """Build an inert, path-free receipt for one current active decision."""

    observed = _utc(now)
    expiry = _utc(expires_at) if expires_at is not None else observed + timedelta(hours=24)
    if not observed < expiry <= observed + MAX_PACKET_LIFETIME:
        raise RecoveryValidationError("packet expiry must be within seven days")
    projection = load_recovery_projection(hub_root, shaping, now=observed)
    if projection["diagnostics"]:
        raise RecoveryStateError(
            "Recovery projection is unsafe: " + "|".join(projection["diagnostics"])
        )
    decision = next(
        (row for row in projection["decisions"] if row["decision_id"] == decision_id),
        None,
    )
    if decision is None or decision["status"] != "active":
        raise RecoveryStateError("recovery packet requires a current active decision")
    validate_shaping_selection(
        shaping,
        case_id=decision["case_id"],
        case_revision_id=decision["case_revision_id"],
        source_snapshot_digest=decision["source_snapshot_digest"],
        expected_preconditions_digest=decision["expected_preconditions_digest"],
        choice_id=decision["choice_id"],
        choice_kind=decision["choice_kind"],
        now=observed,
    )
    packet_without_id = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "decision_id": decision_id,
        "case_id": decision["case_id"],
        "case_revision_id": decision["case_revision_id"],
        "source_snapshot_digest": decision["source_snapshot_digest"],
        "expected_preconditions_digest": decision["expected_preconditions_digest"],
        "choice_id": decision["choice_id"],
        "choice_kind": decision["choice_kind"],
        "action_kind": decision["choice_kind"],
        "disposition": decision["disposition"],
        "precondition_codes": list(PACKET_PRECONDITIONS),
        "issued_at": observed.isoformat(),
        "expires_at": expiry.isoformat(),
        "human_gate_required": True,
        "approval_ref": decision["approval_ref"],
        "independent_checker_required": True,
        "execution_authorized": False,
        "mutations_performed": False,
        "source_authority_mutated": False,
    }
    packet = {
        **packet_without_id,
        "packet_id": _deterministic_packet_id(packet_without_id),
    }
    problems = recovery_packet_problems(packet)
    if problems:
        raise RecoveryValidationError("Invalid recovery packet: " + "; ".join(problems))
    return packet


def record_recovery_result(
    hub_root: Path,
    shaping: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    result_status: str,
    before_snapshot_digest: str,
    after_snapshot_digest: str,
    worker_id: str,
    checker_id: str,
    evidence_refs: Iterable[str],
    command_id: str,
    result_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record a checked manual outcome; never treat it as execution authority."""

    packet_value = dict(packet)
    problems = recovery_packet_problems(packet_value)
    if problems:
        raise RecoveryValidationError("Invalid recovery packet: " + "; ".join(problems))
    observed = _utc(now)
    if result_status not in RESULT_STATUSES:
        raise RecoveryValidationError(f"unknown result status: {result_status}")
    worker = _require_token(worker_id, field="worker_id")
    checker = _require_token(checker_id, field="checker_id")
    if worker == checker:
        raise RecoveryValidationError("worker and checker must be distinct")
    evidence = sorted({_require_token(value, field="evidence_ref") for value in evidence_refs})
    if not evidence:
        raise RecoveryValidationError("at least one privacy-safe evidence ref is required")
    before_digest = _require_digest(before_snapshot_digest, field="before_snapshot_digest")
    after_digest = _require_digest(after_snapshot_digest, field="after_snapshot_digest")
    resolved_result_id = result_id or stable_id(
        "portfolio-recovery-result",
        str(packet_value["packet_id"]),
        result_status,
        before_digest,
        after_digest,
        worker,
        checker,
        *evidence,
    )
    payload = {
        "result_id": resolved_result_id,
        "decision_id": packet_value["decision_id"],
        "case_id": packet_value["case_id"],
        "packet_id": packet_value["packet_id"],
        "before_snapshot_digest": before_digest,
        "after_snapshot_digest": after_digest,
        "result_status": result_status,
        "worker_id": worker,
        "checker_id": checker,
        "evidence_refs": evidence,
    }
    prior_command = _strict_prior_command_event(
        hub_root,
        command_id=command_id,
        stream_id=str(packet_value["case_id"]),
    )
    if prior_command is not None:
        _require_exact_retry(
            prior_command,
            event_kind="manual_recovery_result_recorded",
            payload=payload,
        )
        return {
            "status": "deduplicated",
            "result_id": resolved_result_id,
            "decision_id": packet_value["decision_id"],
            "packet_id": packet_value["packet_id"],
            "execution_authorized": False,
            **_deduplicated_append_result(),
        }

    if observed >= _parse_time(str(packet_value["expires_at"]), field="expires_at"):
        raise RecoveryStateError("recovery packet has expired")
    projection = _load_projection_before_append(hub_root, shaping, now=observed)
    if projection["diagnostics"]:
        raise RecoveryStateError(
            "Recovery projection is unsafe: " + "|".join(projection["diagnostics"])
        )
    decision = next(
        (
            row
            for row in projection["decisions"]
            if row["decision_id"] == packet_value["decision_id"]
        ),
        None,
    )
    if decision is None or decision["status"] != "active":
        raise RecoveryStateError("manual result requires a current active decision")
    for field in (
        "case_id",
        "case_revision_id",
        "source_snapshot_digest",
        "expected_preconditions_digest",
        "choice_id",
        "choice_kind",
        "disposition",
        "approval_ref",
    ):
        if packet_value[field] != decision[field]:
            raise RecoveryStateError(f"recovery packet no longer matches decision: {field}")
    validate_shaping_selection(
        shaping,
        case_id=decision["case_id"],
        case_revision_id=decision["case_revision_id"],
        source_snapshot_digest=decision["source_snapshot_digest"],
        expected_preconditions_digest=decision["expected_preconditions_digest"],
        choice_id=decision["choice_id"],
        choice_kind=decision["choice_kind"],
        now=observed,
    )
    event, _ = build_event(
        event_kind="manual_recovery_result_recorded",
        stream_id=str(packet_value["case_id"]),
        payload=payload,
        prev_event_id="",
        recorded_at=observed.isoformat(),
        command_id=command_id,
    )
    result = _append_recovery_event(
        hub_root,
        event,
        recorded_at=observed.isoformat(),
        shaping=shaping,
    )
    return {
        "status": result_status if result["events_appended"] else "deduplicated",
        "result_id": resolved_result_id,
        "decision_id": decision["decision_id"],
        "packet_id": packet_value["packet_id"],
        "execution_authorized": False,
        **result,
    }


__all__ = [
    "DECISION_STATES",
    "DISPOSITIONS",
    "MAX_PACKET_LIFETIME",
    "PACKET_PRECONDITIONS",
    "PACKET_SCHEMA_VERSION",
    "RESULT_STATUSES",
    "RecoveryStateError",
    "RecoveryValidationError",
    "build_recovery_packet",
    "case_preconditions_digest",
    "fold_recovery_events",
    "load_recovery_projection",
    "record_recovery_result",
    "record_shaping_decision",
    "recovery_packet_problems",
    "retract_shaping_decision",
    "shaping_source_snapshot_digest",
    "validate_shaping_selection",
]
