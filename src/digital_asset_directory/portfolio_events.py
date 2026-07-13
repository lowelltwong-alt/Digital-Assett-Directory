"""Durable, privacy-safe event substrate for the portfolio OS.

``append_events`` is the single persistence transaction.  Under one owned
lock it optionally repairs a torn tail, validates and verifies the existing ledger,
normalizes incoming events, rebases them onto the current per-stream heads,
deduplicates explicit command retries, and writes the complete buffer.

The module never touches Git or the network.  All persisted user-controlled
strings are minimized before identity is derived.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
import hashlib
import json
import math
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .ids import stable_id
from .transport import data_path
from .utils import json_dumps, redact_sensitive_text

EVENT_SCHEMA_VERSION = "dad.portfolio_workstream_event.v1"
EXECUTION_EVENT_SCHEMA_VERSION = "dad.portfolio_execution_control_event.v1"
RECOVERY_EVENT_SCHEMA_VERSION = "dad.portfolio_shaping_decision_event.v1"

EVENT_KINDS = (
    "idea_captured",
    "workstream_proposed",
    "capsule_recorded",
    "focus_feedback",
    "binding_asserted",
    "binding_retracted",
    "project_registered",
    "sovereignty_recorded",
    "execution_lease_requested",
    "execution_lease_granted",
    "execution_lease_revoked",
    "dispatch_intent_proposed",
    "dispatch_intent_approved",
    "dispatch_intent_revoked",
    "dispatch_reconciliation_recorded",
    "shaping_decision_recorded",
    "shaping_decision_retracted",
    "manual_recovery_result_recorded",
)

EXECUTION_EVENT_KINDS = frozenset(
    {
        "execution_lease_requested",
        "execution_lease_granted",
        "execution_lease_revoked",
        "dispatch_intent_proposed",
        "dispatch_intent_approved",
        "dispatch_intent_revoked",
        "dispatch_reconciliation_recorded",
    }
)

RECOVERY_EVENT_KINDS = frozenset(
    {
        "shaping_decision_recorded",
        "shaping_decision_retracted",
        "manual_recovery_result_recorded",
    }
)


_DETERMINISTIC_COMMAND_KINDS = {
    "idea_captured",
    "workstream_proposed",
    "project_registered",
}
_COMMAND_ID_RE = re.compile(r"^dad:portfolio-command:[0-9a-f-]{36}$")
_LOCAL_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\[\w.$-]+[\\/]|/(?:home|Users|mnt|tmp|var|opt|srv)/)"
    r"[^\s\"'<>|?*]*"
)


class LedgerValidationError(ValueError):
    """An event failed the registered runtime contract."""


class LedgerIntegrityError(RuntimeError):
    """Existing ledger state is unsafe to extend."""


class EventConflictError(LedgerIntegrityError):
    """One identity or idempotency key describes conflicting content."""


class _DuplicateJSONKeyError(ValueError):
    """One serialized JSON object repeated a key."""


def _strict_json_loads(text: str) -> Any:
    """Parse JSON without Python's last-value-wins duplicate-key behavior."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateJSONKeyError
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=reject_duplicates)


def _redact_paths(text: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        basename = re.split(r"[\\/]", match.group(0).rstrip("\\/"))[-1]
        return f"[LOCAL_PATH]/{basename}" if basename else "[LOCAL_PATH]"

    return _LOCAL_PATH_RE.sub(repl, text), count


def minimize_text(text: str) -> tuple[str, int]:
    """Redact credentials/PII and minimize absolute local paths."""

    redacted, secret_count = redact_sensitive_text(text)
    redacted, path_count = _redact_paths(redacted)
    return redacted, secret_count + path_count


def minimize_payload(value: Any) -> tuple[Any, int]:
    """Recursively minimize string values in a JSON-shaped value."""

    if isinstance(value, str):
        return minimize_text(value)
    if isinstance(value, list):
        result: list[Any] = []
        total = 0
        for item in value:
            minimized, count = minimize_payload(item)
            result.append(minimized)
            total += count
        return result, total
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        total = 0
        for key, item in value.items():
            if not isinstance(key, str):
                raise LedgerValidationError("Event payload keys must be strings.")
            minimized, count = minimize_payload(item)
            result[key] = minimized
            total += count
        return result, total
    if isinstance(value, float) and not math.isfinite(value):
        raise LedgerValidationError("Event payload contains a non-finite number.")
    if value is None or isinstance(value, (bool, int, float)):
        return value, 0
    raise LedgerValidationError(f"Event payload contains non-JSON value: {type(value).__name__}")


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_command_id(command_id: str) -> str:
    if _COMMAND_ID_RE.fullmatch(command_id):
        return command_id
    minimized, _ = minimize_text(command_id)
    if not minimized:
        raise LedgerValidationError("command_id must not be empty.")
    return stable_id("portfolio-command", minimized)


def canonical_command_id(command_id: str) -> str:
    """Return the persisted opaque identity for one explicit command key."""

    return _canonical_command_id(command_id)


def _new_command_id(event_kind: str, stream_id: str, payload: dict[str, Any]) -> str:
    if event_kind in _DETERMINISTIC_COMMAND_KINDS:
        return stable_id(
            "portfolio-command",
            event_kind,
            stream_id,
            _canonical_payload(payload),
        )
    return stable_id("portfolio-command", uuid.uuid4().hex)


def chain_event_id(
    event_kind: str,
    stream_id: str,
    payload: dict[str, Any],
    prev_event_id: str,
    command_id: str = "",
) -> str:
    """Derive identity from minimized content, predecessor, and command intent.

    ``command_id`` is explicit idempotency.  Legacy rows without it retain the
    former identity formula and remain readable.
    """

    parts = [event_kind, stream_id, _canonical_payload(payload), prev_event_id]
    if command_id:
        parts.append(command_id)
    return stable_id("portfolio-event", *parts)


@lru_cache(maxsize=3)
def _event_validator(schema_version: str) -> Any:
    schema_name = {
        EVENT_SCHEMA_VERSION: "portfolio-workstream-event.schema.json",
        EXECUTION_EVENT_SCHEMA_VERSION: "portfolio-execution-control-event.schema.json",
        RECOVERY_EVENT_SCHEMA_VERSION: "portfolio-shaping-decision-event.schema.json",
    }[schema_version]
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema, format_checker=FormatChecker())


def envelope_problems(event: Any) -> list[str]:
    """Return stable, path-qualified registered-schema problems."""

    if not isinstance(event, dict):
        return ["$: not_an_object"]
    problems: list[str] = []
    schema_version = str(event.get("schema_version", ""))
    if schema_version not in {
        EVENT_SCHEMA_VERSION,
        EXECUTION_EVENT_SCHEMA_VERSION,
        RECOVERY_EVENT_SCHEMA_VERSION,
    }:
        return [f"$['schema_version']: unsupported event schema version {schema_version!r}"]
    for error in sorted(
        _event_validator(schema_version).iter_errors(event), key=lambda item: list(item.path)
    ):
        path = "$" + "".join(f"[{part!r}]" for part in error.path)
        problems.append(f"{path}: {error.message}")
    if not problems:
        payload = event.get("payload", {})
        identity_fields = {
            "idea_captured": "idea_id",
            "workstream_proposed": "workstream_id",
            "capsule_recorded": "workstream_id",
            "focus_feedback": "workstream_id",
            "binding_asserted": "workstream_id",
            "binding_retracted": "workstream_id",
            "project_registered": "project_id",
            "sovereignty_recorded": "project_id",
            "execution_lease_requested": "workstream_id",
            "execution_lease_granted": "workstream_id",
            "execution_lease_revoked": "workstream_id",
            "dispatch_intent_proposed": "workstream_id",
            "dispatch_intent_approved": "workstream_id",
            "dispatch_intent_revoked": "workstream_id",
            "dispatch_reconciliation_recorded": "workstream_id",
            "shaping_decision_recorded": "case_id",
            "shaping_decision_retracted": "case_id",
            "manual_recovery_result_recorded": "case_id",
        }
        identity_field = identity_fields.get(str(event.get("event_kind", "")))
        if identity_field and str(event.get("stream_id", "")) != str(
            payload.get(identity_field, "")
        ):
            problems.append(f"$: stream_id must equal payload.{identity_field}")
    return problems


def build_event(
    *,
    event_kind: str,
    stream_id: str,
    payload: dict[str, Any],
    prev_event_id: str,
    recorded_at: str,
    command_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Build and strictly validate one minimized event.

    Callers that need retry idempotency must reuse an explicit ``command_id``.
    Without one, mutable human commands are new intent; naturally idempotent
    assertion/root kinds receive a deterministic command id.
    """

    if event_kind not in EVENT_KINDS:
        raise LedgerValidationError(
            f"Unknown event kind '{event_kind}'. Expected one of {EVENT_KINDS}."
        )
    minimized_stream, stream_redactions = minimize_text(stream_id)
    minimized_payload, payload_redactions = minimize_payload(payload)
    if not isinstance(minimized_payload, dict):
        raise LedgerValidationError("Event payload must be an object.")
    normalized_command_id = (
        _canonical_command_id(command_id)
        if command_id
        else _new_command_id(event_kind, minimized_stream, minimized_payload)
    )
    redaction_count = stream_redactions + payload_redactions
    event = {
        "event_id": chain_event_id(
            event_kind,
            minimized_stream,
            minimized_payload,
            prev_event_id,
            normalized_command_id,
        ),
        "event_kind": event_kind,
        "schema_version": (
            EXECUTION_EVENT_SCHEMA_VERSION
            if event_kind in EXECUTION_EVENT_KINDS
            else RECOVERY_EVENT_SCHEMA_VERSION
            if event_kind in RECOVERY_EVENT_KINDS
            else EVENT_SCHEMA_VERSION
        ),
        "stream_id": minimized_stream,
        "prev_event_id": prev_event_id,
        "command_id": normalized_command_id,
        "recorded_at": recorded_at,
        "redaction_count": redaction_count,
        "payload": minimized_payload,
    }
    problems = envelope_problems(event)
    if problems:
        raise LedgerValidationError("Invalid event: " + "; ".join(problems))
    return event, redaction_count


def ledger_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports") / "portfolio_os" / "workstream_events.jsonl"


def quarantine_path(ledger: Path) -> Path:
    return ledger.with_suffix(ledger.suffix + ".quarantine")


def lock_path(ledger: Path) -> Path:
    return ledger.with_suffix(ledger.suffix + ".lock")


def _write_all(fd: int, data: bytes) -> None:
    """Write every byte or raise; never turn a legal short write into success."""

    view = memoryview(data)
    written = 0
    while written < len(view):
        try:
            count = os.write(fd, view[written:])
        except InterruptedError:
            continue
        if count <= 0:
            raise OSError("os.write made no forward progress")
        written += count


def _pid_is_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return ctypes.windll.kernel32.GetLastError() == 5
            try:
                exit_code = wintypes.DWORD()
                ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                return bool(ok) and exit_code.value == 259
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


def _read_lock_record(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _unlink_matching_lock(path: Path, nonce: str | None, *, attempts: int = 6) -> bool:
    """Delete only the lock generation observed by the caller."""

    for attempt in range(attempts):
        if not path.exists():
            return True
        current = _read_lock_record(path)
        current_nonce = str(current.get("nonce", "")) if current else None
        if current_nonce != nonce:
            return False
        try:
            path.unlink()
            return not path.exists()
        except FileNotFoundError:
            return True
        except PermissionError:
            if attempt == attempts - 1:
                return False
            time.sleep(0.03 * (attempt + 1))
        except OSError:
            return False
    return False


class LedgerLock:
    """Owned single-host lock with dead-owner recovery and Windows retries."""

    def __init__(
        self,
        ledger: Path,
        *,
        timeout: float = 10.0,
        stale_seconds: float = 300.0,
    ) -> None:
        self._path = lock_path(ledger)
        self._timeout = timeout
        self._stale_seconds = stale_seconds
        self._fd: int | None = None
        self._nonce = uuid.uuid4().hex

    def __enter__(self) -> "LedgerLock":
        deadline = time.monotonic() + self._timeout
        self._path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self._fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                record = {
                    "pid": os.getpid(),
                    "nonce": self._nonce,
                    "created_at_epoch": time.time(),
                }
                _write_all(self._fd, json_dumps(record).encode("utf-8"))
                os.fsync(self._fd)
                return self
            except FileExistsError:
                record = _read_lock_record(self._path)
                try:
                    age = time.time() - self._path.stat().st_mtime
                except OSError:
                    age = 0.0
                owner_pid = 0
                if record:
                    try:
                        owner_pid = int(record.get("pid") or 0)
                    except (TypeError, ValueError):
                        owner_pid = 0
                owner_alive = _pid_is_alive(owner_pid) if owner_pid else False
                if age > self._stale_seconds and not owner_alive:
                    observed_nonce = str(record.get("nonce", "")) if record else None
                    if _unlink_matching_lock(self._path, observed_nonce):
                        continue
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Ledger lock busy: {self._path}") from None
                time.sleep(0.02)
            except PermissionError:
                # Windows/OneDrive can transiently deny creation while a just-
                # removed lock is still being released. Retry within the same
                # bounded acquisition window; persistent denials still surface.
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.03)
            except Exception:
                if self._fd is not None:
                    os.close(self._fd)
                    self._fd = None
                _unlink_matching_lock(self._path, self._nonce)
                raise

    def __exit__(self, *_exc: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        _unlink_matching_lock(self._path, self._nonce)


def repair_tail(ledger: Path, *, recorded_at: str) -> int:
    """Quarantine and truncate one no-newline tail fragment under the lock."""

    if not ledger.exists():
        return 0
    data = ledger.read_bytes()
    if not data or data.endswith(b"\n"):
        return 0
    cut = data.rfind(b"\n") + 1
    fragment = data[cut:]
    minimized_fragment, redaction_count = minimize_text(fragment.decode("utf-8", errors="replace"))
    record = {
        "quarantined_at": recorded_at,
        "reason": "torn_tail_fragment",
        "fragment_sha256": hashlib.sha256(fragment).hexdigest(),
        "fragment": minimized_fragment,
        "redaction_count": redaction_count,
    }
    qpath = quarantine_path(ledger)
    with qpath.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json_dumps(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    with ledger.open("r+b") as handle:
        handle.truncate(cut)
        handle.flush()
        os.fsync(handle.fileno())
    return 1


def _event_fingerprint(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_events(ledger: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Strictly validate identity and linear per-stream chains while reading."""

    diagnostics: dict[str, Any] = {
        "corrupt_line_count": 0,
        "invalid_envelope_count": 0,
        "torn_tail_pending": False,
        "problems": [],
    }
    if not ledger.exists():
        return [], diagnostics
    raw = ledger.read_bytes()
    torn_tail = bool(raw and not raw.endswith(b"\n"))
    diagnostics["torn_tail_pending"] = torn_tail
    lines = raw.split(b"\n")
    if torn_tail:
        lines = lines[:-1]

    events: list[dict[str, Any]] = []
    heads: dict[str, str] = {}
    seen: dict[str, str] = {}
    commands: dict[tuple[str, str], str] = {}
    for index, raw_line in enumerate(lines):
        if not raw_line.strip():
            continue
        try:
            line = raw_line.decode("utf-8")
            event = _strict_json_loads(line)
        except _DuplicateJSONKeyError:
            diagnostics["corrupt_line_count"] += 1
            diagnostics["problems"].append(f"line:{index + 1}:duplicate_json_object_key")
            continue
        except (UnicodeDecodeError, json.JSONDecodeError):
            diagnostics["corrupt_line_count"] += 1
            diagnostics["problems"].append(f"line:{index + 1}:not_valid_utf8_json")
            continue
        problems = envelope_problems(event)
        if problems:
            diagnostics["invalid_envelope_count"] += 1
            diagnostics["problems"].append(f"line:{index + 1}:schema:" + "|".join(problems))
            continue

        event_id = str(event["event_id"])
        fingerprint = _event_fingerprint(event)
        if event_id in seen:
            if seen[event_id] != fingerprint:
                diagnostics["invalid_envelope_count"] += 1
                diagnostics["problems"].append(
                    f"line:{index + 1}:duplicate_event_id_conflict:{event_id}"
                )
            continue

        stream_id = str(event["stream_id"])
        command_id = str(event.get("command_id", ""))
        command_key = (stream_id, command_id)
        if command_id and command_key in commands:
            diagnostics["invalid_envelope_count"] += 1
            diagnostics["problems"].append(
                f"line:{index + 1}:command_id_conflict:{stream_id}:{command_id}"
            )
            continue
        expected_prev = heads.get(stream_id, "")
        actual_prev = str(event["prev_event_id"])
        if actual_prev != expected_prev:
            diagnostics["invalid_envelope_count"] += 1
            diagnostics["problems"].append(
                f"line:{index + 1}:chain_predecessor_mismatch:{stream_id}"
            )
            continue
        expected_id = chain_event_id(
            str(event["event_kind"]),
            stream_id,
            event["payload"],
            actual_prev,
            command_id,
        )
        if event_id != expected_id:
            diagnostics["invalid_envelope_count"] += 1
            diagnostics["problems"].append(f"line:{index + 1}:event_id_mismatch:{event_id}")
            continue
        seen[event_id] = fingerprint
        if command_id:
            commands[command_key] = event_id
        heads[stream_id] = event_id
        events.append(event)
    return events, diagnostics


def stream_heads(events: list[dict[str, Any]]) -> dict[str, str]:
    heads: dict[str, str] = {}
    for event in events:
        heads[str(event["stream_id"])] = str(event["event_id"])
    return heads


def head_event(events: list[dict[str, Any]], stream_id: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if str(event.get("stream_id", "")) == stream_id:
            return event
    return None


def is_head_retry(
    events: list[dict[str, Any]],
    stream_id: str,
    event_kind: str,
    payload: dict[str, Any],
    *,
    recorded_at: str,
    command_id: str | None = None,
) -> bool:
    """Check an explicit command id only; wall-clock buckets never infer intent."""

    del recorded_at
    if not command_id:
        return False
    head = head_event(events, stream_id)
    if head is None or head.get("event_kind") != event_kind:
        return False
    minimized, _ = minimize_payload(payload)
    return head.get("payload") == minimized and head.get("command_id") == _canonical_command_id(
        command_id
    )


def _prepare_incoming(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise LedgerValidationError("Incoming event must be an object.")
    problems = envelope_problems(event)
    if problems:
        raise LedgerValidationError("Invalid incoming event: " + "; ".join(problems))
    minimized_stream, stream_count = minimize_text(str(event["stream_id"]))
    minimized_payload, payload_count = minimize_payload(event["payload"])
    if not isinstance(minimized_payload, dict):
        raise LedgerValidationError("Incoming payload must be an object.")
    incoming_command = str(event.get("command_id", ""))
    expected_incoming_id = chain_event_id(
        str(event["event_kind"]),
        minimized_stream,
        minimized_payload,
        str(event["prev_event_id"]),
        incoming_command,
    )
    if str(event["event_id"]) != expected_incoming_id:
        raise LedgerValidationError("Incoming event_id does not match minimized event content.")
    command_id = (
        _canonical_command_id(incoming_command)
        if incoming_command
        else _new_command_id(str(event["event_kind"]), minimized_stream, minimized_payload)
    )
    return {
        "event_kind": str(event["event_kind"]),
        "stream_id": minimized_stream,
        "payload": minimized_payload,
        "recorded_at": str(event["recorded_at"]),
        "command_id": command_id,
        "redaction_count": int(event["redaction_count"]) + stream_count + payload_count,
    }


def append_events(
    ledger: Path,
    events_to_append: list[dict[str, Any]],
    *,
    recorded_at: str,
    validate_existing: Callable[[list[dict[str, Any]], dict[str, Any]], None] | None = None,
    repair_torn_tail: bool = True,
) -> dict[str, Any]:
    """Validate, rebase, deduplicate, and durably append one command batch.

    ``validate_existing`` runs after the existing ledger has passed integrity
    checks and while the ledger lock is still owned.  Raising from the callback
    aborts the append and releases the lock.  Callbacks must treat the supplied
    events and diagnostics as read-only.  Strict callers can disable tail
    repair; a torn tail then blocks the transaction without changing either the
    ledger or quarantine file.
    """

    ledger.parent.mkdir(parents=True, exist_ok=True)
    with LedgerLock(ledger):
        quarantined = repair_tail(ledger, recorded_at=recorded_at) if repair_torn_tail else 0
        existing, diagnostics = read_events(ledger)
        if (
            diagnostics["torn_tail_pending"]
            or diagnostics["corrupt_line_count"]
            or diagnostics["invalid_envelope_count"]
        ):
            integrity_problems = list(diagnostics["problems"])
            if diagnostics["torn_tail_pending"]:
                integrity_problems.insert(0, "torn_tail_pending")
            raise LedgerIntegrityError(
                "Ledger contains an unrepaired tail, interior corruption, or invalid event "
                "chains; refusing append: "
                + "|".join(integrity_problems)
            )
        if validate_existing is not None:
            validate_existing(existing, diagnostics)

        prepared = [_prepare_incoming(event) for event in events_to_append]
        heads = stream_heads(existing)
        by_id = {str(event["event_id"]): event for event in existing}
        by_command = {
            (str(event["stream_id"]), str(event.get("command_id", ""))): event
            for event in existing
            if event.get("command_id")
        }
        pending: list[dict[str, Any]] = []
        deduplicated = 0

        for command in prepared:
            command_key = (command["stream_id"], command["command_id"])
            prior = by_command.get(command_key)
            if prior is not None:
                if (
                    prior["event_kind"] == command["event_kind"]
                    and prior["payload"] == command["payload"]
                ):
                    deduplicated += 1
                    continue
                raise EventConflictError(
                    f"command_id conflict for stream {command['stream_id']}: {command['command_id']}"
                )

            event, _ = build_event(
                event_kind=command["event_kind"],
                stream_id=command["stream_id"],
                payload=command["payload"],
                prev_event_id=heads.get(command["stream_id"], ""),
                recorded_at=command["recorded_at"],
                command_id=command["command_id"],
            )
            event["redaction_count"] = command["redaction_count"]
            problems = envelope_problems(event)
            if problems:
                raise LedgerValidationError("Invalid normalized event: " + "; ".join(problems))
            event_id = str(event["event_id"])
            if event_id in by_id:
                if _event_fingerprint(by_id[event_id]) != _event_fingerprint(event):
                    raise EventConflictError(f"event_id conflict: {event_id}")
                deduplicated += 1
                continue
            pending.append(event)
            by_id[event_id] = event
            by_command[command_key] = event
            heads[command["stream_id"]] = event_id

        if pending:
            buffer = "".join(json_dumps(event) + "\n" for event in pending).encode("utf-8")
            fd = os.open(ledger, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
            try:
                _write_all(fd, buffer)
                os.fsync(fd)
            finally:
                os.close(fd)
        return {
            "events_appended": len(pending),
            "events_deduplicated": deduplicated,
            "tail_fragments_quarantined": quarantined,
            "corrupt_line_count": diagnostics["corrupt_line_count"],
            "invalid_envelope_count": diagnostics["invalid_envelope_count"],
        }


__all__ = [
    "EVENT_KINDS",
    "EVENT_SCHEMA_VERSION",
    "EXECUTION_EVENT_KINDS",
    "EXECUTION_EVENT_SCHEMA_VERSION",
    "RECOVERY_EVENT_KINDS",
    "RECOVERY_EVENT_SCHEMA_VERSION",
    "EventConflictError",
    "LedgerIntegrityError",
    "LedgerLock",
    "LedgerValidationError",
    "append_events",
    "build_event",
    "canonical_command_id",
    "chain_event_id",
    "envelope_problems",
    "head_event",
    "is_head_retry",
    "ledger_path",
    "lock_path",
    "minimize_payload",
    "minimize_text",
    "quarantine_path",
    "read_events",
    "repair_tail",
    "stream_heads",
]
