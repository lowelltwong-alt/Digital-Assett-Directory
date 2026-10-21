"""Source-zero-write attempt coordination for the Portfolio OS.

The journal is deliberately separate from the authority ledger. It records only
local dry-run claim selection and simulated results. It never launches a worker,
executes a command, touches Git, writes a source repository, or grants authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from html import escape
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable
import uuid

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .portfolio_events import LedgerIntegrityError, LedgerLock, minimize_payload
from .transport import data_path
from .utils import atomic_write_text, json_dumps

SCHEMA_VERSION = "dad.portfolio_attempt_event.v1"
PROJECTION_VERSION = "dad.portfolio_attempt_projection.v1"
AUTHORITY_BOUNDARY = (
    "Attempt rows are non-authoritative source-zero-write dry-run observations. "
    "Claim selection is not approval, execution, reconciliation, or permission."
)
RESULT_DISPOSITIONS = (
    "simulated_succeeded",
    "simulated_failed",
    "aborted",
    "outcome_unknown",
)


class AttemptConflictError(LedgerIntegrityError):
    """An attempt identity or command was reused for different content."""


def _now(value: datetime | None) -> datetime:
    observed = value or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return observed.astimezone(timezone.utc)


def attempt_journal_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports") / "portfolio_os" / "execution_attempts.jsonl"


def _strict_json_loads(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / "portfolio-attempt-event.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _event_validator() -> Any:
    """Compile the immutable attempt-event schema once per process.

    Claim attempts still validate every existing ledger event while holding the
    cross-process ledger lock.  Reusing only the compiled schema validator
    removes repeated schema I/O and construction without weakening that full
    chain validation.
    """

    schema = _schema()
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    return validator_cls(schema, format_checker=FormatChecker())


def _event_id(event_without_id: dict[str, Any]) -> str:
    canonical = json.dumps(
        event_without_id,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"dad:portfolio-attempt-event:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _event_problems(event: Any) -> list[str]:
    problems = [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}:{error.message}"
        for error in sorted(
            _event_validator().iter_errors(event),
            key=lambda item: list(item.absolute_path),
        )
    ]
    if isinstance(event, dict):
        unsigned = {key: value for key, value in event.items() if key != "event_id"}
        if event.get("event_id") != _event_id(unsigned):
            problems.append("event_id:digest_mismatch")
        payload = event.get("payload", {})
        if isinstance(payload, dict) and event.get("event_kind") == "dry_run_claim_recorded":
            selected = bool(payload.get("claim_selected"))
            if selected != (payload.get("attempt_id") == payload.get("selected_attempt_id")):
                problems.append("payload:claim_selection_identity_mismatch")
    return sorted(set(problems))


def _build_event(
    *,
    event_kind: str,
    prev_event_id: str,
    command_id: str,
    recorded_at: str,
    payload: dict[str, Any],
    redaction_count: int | None = None,
) -> dict[str, Any]:
    if redaction_count is None:
        minimized, redaction_count = minimize_payload(payload)
    else:
        minimized = deepcopy(payload)
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "event_kind": event_kind,
        "prev_event_id": prev_event_id,
        "command_id": command_id,
        "recorded_at": recorded_at,
        "redaction_count": redaction_count,
        "authority_boundary": "source_zero_write_candidate_only",
        "payload": minimized,
    }
    event = {"event_id": _event_id(unsigned), **unsigned}
    problems = _event_problems(event)
    if problems:
        raise ValueError("invalid attempt event: " + "|".join(problems))
    return event


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        try:
            count = os.write(fd, view[offset:])
        except InterruptedError:
            continue
        if count <= 0:
            raise OSError("os.write made no forward progress")
        offset += count


def read_attempt_events(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read and verify the global attempt chain without repairing ambiguity."""

    diagnostics: dict[str, Any] = {
        "corrupt_line_count": 0,
        "invalid_event_count": 0,
        "complete_unsealed_tail": False,
        "ambiguous_tail": False,
        "problems": [],
    }
    if not path.exists():
        return [], diagnostics
    raw = path.read_bytes()
    if not raw:
        return [], diagnostics

    sealed = raw.endswith(b"\n")
    lines = raw.split(b"\n")
    if sealed:
        lines = lines[:-1]
    events: list[dict[str, Any]] = []
    previous = ""
    seen: set[str] = set()
    seen_commands: set[str] = set()
    claims: dict[str, dict[str, Any]] = {}
    selected_by_dispatch: dict[str, dict[str, Any]] = {}
    results: set[str] = set()
    dispatch_scopes: dict[str, str] = {}

    for index, raw_line in enumerate(lines):
        if not raw_line:
            diagnostics["corrupt_line_count"] += 1
            diagnostics["problems"].append(f"line:{index + 1}:empty")
            continue
        is_unsealed_tail = not sealed and index == len(lines) - 1
        try:
            event = _strict_json_loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            if is_unsealed_tail:
                diagnostics["ambiguous_tail"] = True
                diagnostics["problems"].append("tail:partial_or_invalid_json")
            else:
                diagnostics["corrupt_line_count"] += 1
                diagnostics["problems"].append(f"line:{index + 1}:invalid_json")
            continue
        problems = _event_problems(event)
        if not isinstance(event, dict):
            problems.append("event:not_object")
        elif event.get("prev_event_id") != previous:
            problems.append("prev_event_id:chain_mismatch")
        event_id = str(event.get("event_id", "")) if isinstance(event, dict) else ""
        if event_id in seen:
            problems.append("event_id:duplicate")
        command_id = str(event.get("command_id", "")) if isinstance(event, dict) else ""
        if command_id in seen_commands:
            problems.append("command_id:duplicate")
        payload = event.get("payload", {}) if isinstance(event, dict) else {}
        kind = str(event.get("event_kind", "")) if isinstance(event, dict) else ""
        attempt_id = ""
        dispatch_id = ""
        scope_digest = ""
        if isinstance(payload, dict):
            attempt_id = str(payload.get("attempt_id", ""))
            dispatch_id = str(payload.get("dispatch_revision_id", ""))
            scope_digest = str(payload.get("dispatch_scope_digest", ""))
            prior_scope = dispatch_scopes.get(dispatch_id)
            if prior_scope is not None and prior_scope != scope_digest:
                problems.append("dispatch_scope_digest:changed")
            if kind == "dry_run_claim_recorded":
                if attempt_id in claims:
                    problems.append("attempt_id:duplicate_claim")
                selected = selected_by_dispatch.get(dispatch_id)
                if payload.get("claim_selected") is True:
                    if selected is not None:
                        problems.append("dispatch_revision_id:multiple_selected_claims")
                elif selected is None:
                    problems.append("dispatch_revision_id:losing_claim_precedes_selection")
                elif payload.get("selected_attempt_id") != selected.get("attempt_id"):
                    problems.append("selected_attempt_id:dispatch_winner_mismatch")
            elif kind == "dry_run_result_recorded":
                selected = selected_by_dispatch.get(dispatch_id)
                claim = claims.get(attempt_id)
                if selected is None or selected.get("attempt_id") != attempt_id:
                    problems.append("attempt_id:result_not_for_selected_claim")
                if claim is None:
                    problems.append("attempt_id:result_claim_missing")
                elif any(
                    payload.get(field) != claim.get(field)
                    for field in (
                        "dispatch_revision_id",
                        "dispatch_scope_digest",
                        "worker_revision_id",
                        "execution_mode",
                        "source_write_policy",
                        "execution_performed",
                        "source_write_count",
                        "non_authoritative",
                    )
                ):
                    problems.append("payload:result_claim_mismatch")
                if attempt_id in results:
                    problems.append("attempt_id:duplicate_result")
        if problems:
            if is_unsealed_tail:
                diagnostics["ambiguous_tail"] = True
                diagnostics["problems"].append("tail:ambiguous:" + "|".join(problems))
            else:
                diagnostics["invalid_event_count"] += 1
                diagnostics["problems"].append(f"line:{index + 1}:" + "|".join(problems))
            continue
        events.append(event)
        seen.add(event_id)
        seen_commands.add(command_id)
        dispatch_scopes.setdefault(dispatch_id, scope_digest)
        if kind == "dry_run_claim_recorded":
            claim_row = dict(payload)
            claims[attempt_id] = claim_row
            if payload["claim_selected"] is True:
                selected_by_dispatch[dispatch_id] = claim_row
        elif kind == "dry_run_result_recorded":
            results.add(attempt_id)
        previous = event_id
        if is_unsealed_tail:
            diagnostics["complete_unsealed_tail"] = True

    return events, diagnostics


def _assert_appendable(diagnostics: dict[str, Any]) -> None:
    if (
        diagnostics["corrupt_line_count"]
        or diagnostics["invalid_event_count"]
        or diagnostics["ambiguous_tail"]
    ):
        raise LedgerIntegrityError(
            "Attempt journal is ambiguous or corrupt; refusing append: "
            + "|".join(diagnostics["problems"])
        )


def _seal_complete_tail(path: Path, diagnostics: dict[str, Any]) -> None:
    if not diagnostics["complete_unsealed_tail"]:
        return
    fd = os.open(path, os.O_APPEND | os.O_WRONLY)
    try:
        _write_all(fd, b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)


def _append_event(path: Path, event: dict[str, Any]) -> None:
    buffer = (json_dumps(event) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
    try:
        _write_all(fd, buffer)
        os.fsync(fd)
    finally:
        os.close(fd)


def _dispatch_row(projection: dict[str, Any], dispatch_revision_id: str) -> dict[str, Any]:
    matches = [
        row
        for row in projection.get("dispatches", [])
        if row.get("dispatch_revision_id") == dispatch_revision_id
    ]
    if len(matches) != 1:
        raise ValueError("dispatch revision must resolve to exactly one execution projection row")
    return matches[0]


def _attempt_id(value: str) -> str:
    return value or f"dad:portfolio-attempt:{uuid.uuid4()}"


def _command_id(value: str) -> str:
    return value or f"dad:portfolio-attempt-command:{uuid.uuid4()}"


def claim_dry_run_attempt(
    hub_root: Path,
    execution_projection: dict[str, Any],
    dispatch_revision_id: str,
    *,
    worker_revision_id: str,
    attempt_id: str = "",
    command_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Select at most one dry-run claim under the journal lock."""

    observed = _now(now)
    dispatch = _dispatch_row(execution_projection, dispatch_revision_id)
    scope_digest = str(dispatch.get("scope_digest", ""))
    if not scope_digest.startswith("dad:portfolio-dispatch-scope:"):
        raise ValueError("dispatch projection lacks a valid scope digest")
    requested_attempt_id = _attempt_id(attempt_id)
    requested_command_id = _command_id(command_id)
    path = attempt_journal_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    with LedgerLock(path):
        events, diagnostics = read_attempt_events(path)
        _assert_appendable(diagnostics)
        _seal_complete_tail(path, diagnostics)

        prior_command = next(
            (event for event in events if event.get("command_id") == requested_command_id),
            None,
        )
        if prior_command is not None:
            stored_payload = prior_command.get("payload", {})
            expected_raw = {
                "attempt_id": requested_attempt_id,
                "dispatch_revision_id": dispatch_revision_id,
                "dispatch_scope_digest": scope_digest,
                "worker_revision_id": worker_revision_id,
                "execution_mode": "dry_run",
                "source_write_policy": "source_zero_write",
                "execution_performed": False,
                "source_write_count": 0,
                "non_authoritative": True,
                "claim_selected": stored_payload.get("claim_selected"),
                "selected_attempt_id": stored_payload.get("selected_attempt_id"),
            }
            expected_payload, _ = minimize_payload(expected_raw)
            if (
                prior_command.get("event_kind") != "dry_run_claim_recorded"
                or stored_payload != expected_payload
            ):
                raise AttemptConflictError(f"attempt command_id conflict: {requested_command_id}")
            return {
                "status": (
                    "claim_selected" if stored_payload["claim_selected"] else "claim_not_selected"
                ),
                "events_appended": 0,
                "events_deduplicated": 1,
                **stored_payload,
            }

        if any(
            event.get("payload", {}).get("attempt_id") == requested_attempt_id for event in events
        ):
            raise AttemptConflictError(f"attempt_id conflict: {requested_attempt_id}")

        selected = next(
            (
                event["payload"]
                for event in events
                if event.get("event_kind") == "dry_run_claim_recorded"
                and event.get("payload", {}).get("dispatch_revision_id") == dispatch_revision_id
                and event.get("payload", {}).get("claim_selected") is True
            ),
            None,
        )
        claim_selected = selected is None
        selected_attempt_id = (
            requested_attempt_id if claim_selected else str(selected["attempt_id"])
        )
        payload, redaction_count = minimize_payload(
            {
                "attempt_id": requested_attempt_id,
                "dispatch_revision_id": dispatch_revision_id,
                "dispatch_scope_digest": scope_digest,
                "worker_revision_id": worker_revision_id,
                "execution_mode": "dry_run",
                "source_write_policy": "source_zero_write",
                "execution_performed": False,
                "source_write_count": 0,
                "non_authoritative": True,
                "claim_selected": claim_selected,
                "selected_attempt_id": selected_attempt_id,
            }
        )
        event = _build_event(
            event_kind="dry_run_claim_recorded",
            prev_event_id=str(events[-1]["event_id"]) if events else "",
            command_id=requested_command_id,
            recorded_at=observed.isoformat(),
            payload=payload,
            redaction_count=redaction_count,
        )
        _append_event(path, event)
        return {
            "status": "claim_selected" if claim_selected else "claim_not_selected",
            "events_appended": 1,
            "events_deduplicated": 0,
            **payload,
        }


def record_dry_run_result(
    hub_root: Path,
    attempt_id: str,
    *,
    result_disposition: str,
    evidence_refs: Iterable[str] = (),
    command_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record a simulated result for the selected dry-run claim only."""

    if result_disposition not in RESULT_DISPOSITIONS:
        raise ValueError(f"result_disposition must be one of {RESULT_DISPOSITIONS}")
    refs = sorted({str(value).strip() for value in evidence_refs if str(value).strip()})
    observed = _now(now)
    requested_command_id = _command_id(command_id)
    path = attempt_journal_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    with LedgerLock(path):
        events, diagnostics = read_attempt_events(path)
        _assert_appendable(diagnostics)
        _seal_complete_tail(path, diagnostics)
        claim = next(
            (
                event["payload"]
                for event in events
                if event.get("event_kind") == "dry_run_claim_recorded"
                and event.get("payload", {}).get("attempt_id") == attempt_id
                and event.get("payload", {}).get("claim_selected") is True
            ),
            None,
        )
        if claim is None:
            raise ValueError("only the selected dry-run attempt can record a result")

        payload = {
            key: claim[key]
            for key in (
                "attempt_id",
                "dispatch_revision_id",
                "dispatch_scope_digest",
                "worker_revision_id",
                "execution_mode",
                "source_write_policy",
                "execution_performed",
                "source_write_count",
                "non_authoritative",
            )
        }
        payload["result_disposition"] = result_disposition
        payload["evidence_refs"] = refs
        payload, redaction_count = minimize_payload(payload)

        prior_command = next(
            (event for event in events if event.get("command_id") == requested_command_id),
            None,
        )
        if prior_command is not None:
            if (
                prior_command.get("event_kind") != "dry_run_result_recorded"
                or prior_command.get("payload") != payload
            ):
                raise AttemptConflictError(f"attempt command_id conflict: {requested_command_id}")
            return {
                "status": "result_recorded",
                "events_appended": 0,
                "events_deduplicated": 1,
                **payload,
            }
        if any(
            event.get("event_kind") == "dry_run_result_recorded"
            and event.get("payload", {}).get("attempt_id") == attempt_id
            for event in events
        ):
            raise AttemptConflictError(f"dry-run result already exists: {attempt_id}")

        event = _build_event(
            event_kind="dry_run_result_recorded",
            prev_event_id=str(events[-1]["event_id"]) if events else "",
            command_id=requested_command_id,
            recorded_at=observed.isoformat(),
            payload=payload,
            redaction_count=redaction_count,
        )
        _append_event(path, event)
        return {
            "status": "result_recorded",
            "events_appended": 1,
            "events_deduplicated": 0,
            **payload,
        }


def project_attempts(
    events: Iterable[dict[str, Any]],
    *,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dispatches: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event["payload"]
        dispatch_id = str(payload["dispatch_revision_id"])
        row = dispatches.setdefault(
            dispatch_id,
            {
                "dispatch_revision_id": dispatch_id,
                "dispatch_scope_digest": str(payload["dispatch_scope_digest"]),
                "claim_count": 0,
                "selected_attempt_id": "",
                "selected_worker_revision_id": "",
                "simulated_result": None,
                "non_authoritative": True,
                "source_write_count": 0,
            },
        )
        if event["event_kind"] == "dry_run_claim_recorded":
            row["claim_count"] += 1
            if payload["claim_selected"]:
                row["selected_attempt_id"] = payload["attempt_id"]
                row["selected_worker_revision_id"] = payload["worker_revision_id"]
        else:
            row["simulated_result"] = {
                "attempt_id": payload["attempt_id"],
                "result_disposition": payload["result_disposition"],
                "evidence_refs": payload["evidence_refs"],
                "execution_performed": False,
                "source_write_count": 0,
                "non_authoritative": True,
            }
    rows = sorted(dispatches.values(), key=lambda item: item["dispatch_revision_id"])
    selected_count = sum(bool(row["selected_attempt_id"]) for row in rows)
    return {
        "schema_version": PROJECTION_VERSION,
        "status": "generated_candidate",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "executor": {"available": False, "dispatch_allowed": False},
        "summary": {
            "event_count": sum(
                row["claim_count"] + (1 if row["simulated_result"] else 0) for row in rows
            ),
            "dispatch_count": len(rows),
            "selected_claim_count": selected_count,
            "real_execution_count": 0,
            "source_write_count": 0,
        },
        "dispatches": rows,
        "ledger_diagnostics": diagnostics or {},
    }


def load_attempt_projection(hub_root: Path) -> dict[str, Any]:
    events, diagnostics = read_attempt_events(attempt_journal_path(hub_root))
    return project_attempts(events, diagnostics=diagnostics)


def annotate_execution_projection(
    execution_projection: dict[str, Any],
    attempt_projection: dict[str, Any],
) -> dict[str, Any]:
    """Add dry-run observations without granting authority or a real outcome."""

    result = deepcopy(execution_projection)
    attempts = {
        row["dispatch_revision_id"]: row for row in attempt_projection.get("dispatches", [])
    }
    for dispatch in result.get("dispatches", []):
        observed = attempts.get(dispatch["dispatch_revision_id"])
        dispatch["dry_run_attempt"] = observed
        reconciliation = dispatch.get("reconciliation")
        if (
            dispatch.get("status") == "reconciliation_pending_attempt_journal"
            and reconciliation
            and observed
            and reconciliation.get("attempt_id") == observed.get("selected_attempt_id")
        ):
            dispatch["status"] = "reconciliation_dry_run_only"
            dispatch["authorization_valid"] = False
            dispatch["manual_packet_ready"] = False
            dispatch["dispatch_allowed"] = False
    result["attempt_journal"] = {
        "status": "source_zero_write_candidate_only",
        "summary": attempt_projection.get("summary", {}),
        "ledger_diagnostics": attempt_projection.get("ledger_diagnostics", {}),
    }
    result["executor"] = {"available": False, "dispatch_allowed": False}
    return result


def simulate_claim_race(candidates: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Pure deterministic claim-order simulation; no journal is written."""

    rows = [dict(item) for item in candidates]
    if not rows:
        raise ValueError("at least one candidate is required")
    sequences = [item.get("sequence") for item in rows]
    if any(not isinstance(value, int) or value < 0 for value in sequences):
        raise ValueError("candidate sequence values must be non-negative integers")
    if len(set(sequences)) != len(sequences):
        raise ValueError("candidate sequence values must be unique")
    attempt_ids = [str(item.get("attempt_id", "")) for item in rows]
    if any(not value.startswith("dad:portfolio-attempt:") for value in attempt_ids):
        raise ValueError("every candidate needs a Portfolio attempt ID")
    if len(set(attempt_ids)) != len(attempt_ids):
        raise ValueError("candidate attempt IDs must be unique")
    ordered = sorted(
        rows,
        key=lambda item: (
            int(item["sequence"]),
            str(item["attempt_id"]),
            str(item.get("worker_revision_id", "")),
        ),
    )
    selected_id = str(ordered[0]["attempt_id"])
    return {
        "schema_version": "dad.portfolio_attempt_race_simulation.v1",
        "status": "generated_candidate",
        "selected_attempt_id": selected_id,
        "non_authoritative": True,
        "execution_mode": "dry_run",
        "source_write_policy": "source_zero_write",
        "execution_performed": False,
        "source_write_count": 0,
        "ordered_claims": [
            {
                **item,
                "claim_selected": str(item["attempt_id"]) == selected_id,
                "selected_attempt_id": selected_id,
                "non_authoritative": True,
            }
            for item in ordered
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def write_attempt_outputs(hub_root: Path, projection: dict[str, Any]) -> dict[str, str]:
    root = data_path(hub_root, "central_reports") / "portfolio_os"
    json_path = root / "execution_attempts.json"
    html_path = root / "execution_attempts.html"
    atomic_write_text(json_path, json_dumps(projection, indent=2) + "\n")
    rows = (
        "".join(
            "<tr>"
            f"<td><code>{escape(row['dispatch_revision_id'])}</code></td>"
            f"<td><code>{escape(row['selected_attempt_id'])}</code></td>"
            f"<td>{row['claim_count']}</td>"
            "<td>no</td>"
            "</tr>"
            for row in projection["dispatches"]
        )
        or "<tr><td colspan='4'>No dry-run attempts</td></tr>"
    )
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>DAD Source-Zero-Write Attempts</title>
<style>body{{font:15px system-ui;margin:2rem;background:#101418;color:#eef}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #3a4652;padding:.5rem;text-align:left}}code{{color:#9de}}</style></head><body>
<h1>Source-Zero-Write Attempts</h1><p>{escape(AUTHORITY_BOUNDARY)}</p>
<p>Executor available: <strong>no</strong>. Source writes: <strong>0</strong>.</p>
<table><tr><th>Dispatch</th><th>Selected dry-run attempt</th><th>Claims</th><th>Authoritative</th></tr>{rows}</table>
</body></html>"""
    atomic_write_text(html_path, html)
    return {"json_path": str(json_path), "html_path": str(html_path)}


__all__ = [
    "AUTHORITY_BOUNDARY",
    "AttemptConflictError",
    "RESULT_DISPOSITIONS",
    "annotate_execution_projection",
    "attempt_journal_path",
    "claim_dry_run_attempt",
    "load_attempt_projection",
    "project_attempts",
    "read_attempt_events",
    "record_dry_run_result",
    "simulate_claim_race",
    "write_attempt_outputs",
]
