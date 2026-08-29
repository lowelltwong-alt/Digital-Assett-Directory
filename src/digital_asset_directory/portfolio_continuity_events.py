"""Provider-neutral, append-only observation ledger for intent continuity.

This module persists minimized metadata evidence only.  It deliberately has no
Git, network, notification, scheduler, model, or task-system integration.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Any, Iterator, Mapping

from .transport import data_path, resolve_data_root
from .utils import atomic_write_text, json_dumps


RECEIPT_SCHEMA_VERSION = "dad.portfolio_continuity_adapter_receipt.v1"
EVENT_SCHEMA_VERSION = "dad.portfolio_continuity_event.v1"
AUTHORITY_BOUNDARY = (
    "Continuity observations are private, minimized, candidate evidence only. "
    "They cannot authorize execution, notification, scheduling, task mutation, "
    "Git mutation, identity merge, worktree creation, or archival."
)
LOCK_STALE_SECONDS = 30.0
LEDGER_INDEX_SCHEMA_VERSION = "dad.continuity_ledger_index.v1"
RECEIPT_SCHEMA_SHA256 = (
    "sha256:77f66f512fe3ad8fa1a51c7a97a9c3f49c2d722c67613e7403d784a142abc11d"
)
EVENT_SCHEMA_SHA256 = (
    "sha256:5c6b007f3353cf8faebeb29bf9d11897bc43e3e7087d8c86bdae6d81d5ce8ca0"
)
_CODEX_FAST_ADAPTER_ID = "adapter:intent-continuity-shadow"
_CODEX_FAST_ADAPTER_REVISION_ID = (
    "adapter-revision:intent-continuity-codex-host:0.3.11"
)

_DENIED_FIELD_PARTS = frozenset(
    {
        "authorization",
        "body",
        "content",
        "conversation",
        "credential",
        "diff",
        "message",
        "password",
        "patch",
        "prompt",
        "raw",
        "secret",
        "sourcecontent",
        "token",
        "transcript",
    }
)
_PATH_SHAPED = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|/(?:Users|home|tmp|mnt|var|etc|opt)(?:/|$))",
    re.IGNORECASE,
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ContinuityValidationError(ValueError):
    """An incoming receipt or event violates the minimized contract."""


class ContinuityIntegrityError(RuntimeError):
    """The append-only ledger is malformed or its hash chain is invalid."""


class ContinuityConflictError(ContinuityIntegrityError):
    """A command ID was reused for different semantic material."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


@lru_cache(maxsize=2)
def _validator(name: str) -> Any:
    from jsonschema import FormatChecker
    from jsonschema.validators import validator_for

    schema = json.loads(_schema_path(name).read_text(encoding="utf-8"))
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema, format_checker=FormatChecker())


def _schema_digest(name: str) -> str:
    data = _schema_path(name).read_bytes().replace(b"\r\n", b"\n")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _assert_fast_schema_contract() -> None:
    expected = {
        "portfolio-continuity-adapter-receipt.schema.json": RECEIPT_SCHEMA_SHA256,
        "portfolio-continuity-event.schema.json": EVENT_SCHEMA_SHA256,
    }
    stale = [
        name for name, digest in expected.items() if _schema_digest(name) != digest
    ]
    if stale:
        raise ContinuityValidationError(
            "Codex hook fast validation is stale for: " + ", ".join(stale)
        )


def _schema_problems(value: Any, name: str) -> list[str]:
    problems: list[str] = []
    for error in sorted(_validator(name).iter_errors(value), key=lambda item: list(item.path)):
        path = "$" + "".join(f"[{part!r}]" for part in error.path)
        problems.append(f"{path}: {error.message}")
    return problems


def _normalized_field_part(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


@lru_cache(maxsize=1024)
def _field_name_is_denied(value: str) -> bool:
    normalized = _normalized_field_part(value)
    return any(part in normalized for part in _DENIED_FIELD_PARTS)


def _privacy_problems(value: Any, *, path: str = "$") -> list[str]:
    problems: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if _field_name_is_denied(str(key)):
                problems.append(f"{path}[{key!r}]: forbidden raw or sensitive field")
            problems.extend(_privacy_problems(item, path=f"{path}[{key!r}]"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            problems.extend(_privacy_problems(item, path=f"{path}[{index}]"))
    elif isinstance(value, str) and _PATH_SHAPED.search(value):
        problems.append(f"{path}: path-shaped value is forbidden")
    return problems


def _minimize(value: Any) -> tuple[Any, int]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        changes = 0
        for key in sorted(value):
            minimized, count = _minimize(value[key])
            result[str(key)] = minimized
            changes += count
        return result, changes
    if isinstance(value, list):
        result_list: list[Any] = []
        changes = 0
        for item in value:
            minimized, count = _minimize(item)
            result_list.append(minimized)
            changes += count
        return result_list, changes
    if isinstance(value, str):
        cleaned = _CONTROL.sub("", " ".join(value.split()))
        return cleaned, int(cleaned != value)
    return value, 0


def validate_adapter_receipt(receipt: Any) -> None:
    privacy = _privacy_problems(receipt)
    if privacy:
        raise ContinuityValidationError("; ".join(privacy))
    problems = _schema_problems(receipt, "portfolio-continuity-adapter-receipt.schema.json")
    if problems:
        raise ContinuityValidationError("Invalid continuity receipt: " + "; ".join(problems))


def normalize_receipt(receipt: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    """Validate before hashing, then normalize bounded metadata strings."""

    validate_adapter_receipt(receipt)
    minimized, redaction_count = _minimize(dict(receipt))
    if not isinstance(minimized, dict):  # defensive: Mapping always minimizes to dict
        raise ContinuityValidationError("Continuity receipt must be an object")
    validate_adapter_receipt(minimized)
    return minimized, redaction_count


def _event_material(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: event[key] for key in event if key != "event_id"}


def _command_material(event: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {"event_id", "prev_event_id", "recorded_at", "redaction_count"}
    return {key: event[key] for key in event if key not in excluded}


def _expected_event_id(event: Mapping[str, Any]) -> str:
    return "dad:continuity-event:" + _sha256(_canonical(_event_material(event)))


def validate_event(event: Any) -> None:
    privacy = _privacy_problems(event)
    if privacy:
        raise ContinuityValidationError("; ".join(privacy))
    problems = _schema_problems(event, "portfolio-continuity-event.schema.json")
    if problems:
        raise ContinuityValidationError("Invalid continuity event: " + "; ".join(problems))
    validate_adapter_receipt(
        {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "request_id": "event-validation",
            "adapter_id": event["adapter_id"],
            "adapter_revision_id": event["adapter_revision_id"],
            "source_kind": event["source_kind"],
            "source_id": event["source_id"],
            "source_revision": event["source_revision"],
            "event_kind": event["event_kind"],
            "observed_at": event["observed_at"],
            "privacy_partition": event["privacy_partition"],
            "payload": event["payload"],
        }
    )
    if event["payload_digest"] != canonical_digest(event["payload"]):
        raise ContinuityValidationError("payload_digest does not match payload")
    if event["event_id"] != _expected_event_id(event):
        raise ContinuityValidationError("event_id does not match event material")


@lru_cache(maxsize=1)
def _event_schema_contract() -> dict[str, Any]:
    return json.loads(_schema_path("portfolio-continuity-event.schema.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _receipt_payload_schema_contract() -> dict[str, Any]:
    schema = json.loads(
        _schema_path("portfolio-continuity-adapter-receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    return schema["properties"]["payload"]


@lru_cache(maxsize=1)
def _receipt_schema_contract() -> dict[str, Any]:
    return json.loads(
        _schema_path("portfolio-continuity-adapter-receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )


def _fast_string_rule_problems(value: str, rule: Mapping[str, Any], label: str) -> list[str]:
    problems: list[str] = []
    if len(value) < int(rule.get("minLength", 0)):
        problems.append(f"{label} is too short")
    if "maxLength" in rule and len(value) > int(rule["maxLength"]):
        problems.append(f"{label} is too long")
    if "pattern" in rule and re.fullmatch(str(rule["pattern"]), value) is None:
        problems.append(f"{label} violates pattern")
    return problems


def _fast_receipt_schema_problems(receipt: Any) -> list[str]:
    """Validate every rule in the pinned receipt schema without jsonschema."""

    if not isinstance(receipt, dict):
        return ["receipt is not an object"]
    schema = _receipt_schema_contract()
    required = set(schema["required"])
    properties = schema["properties"]
    problems = [f"missing required field {key}" for key in sorted(required - set(receipt))]
    if schema.get("additionalProperties") is False:
        problems.extend(
            f"unexpected field {key}" for key in sorted(set(receipt) - set(properties))
        )
    for key, value in receipt.items():
        rule = properties.get(key)
        if not isinstance(rule, dict) or key == "payload":
            continue
        expected_type = rule.get("type")
        if expected_type == "string" and not isinstance(value, str):
            problems.append(f"field {key} has invalid type")
            continue
        if "const" in rule and value != rule["const"]:
            problems.append(f"field {key} violates const")
        if "enum" in rule and value not in rule["enum"]:
            problems.append(f"field {key} violates enum")
        if isinstance(value, str):
            problems.extend(_fast_string_rule_problems(value, rule, f"field {key}"))
    if "payload" in receipt:
        problems.extend(_fast_payload_schema_problems(receipt["payload"]))
    return problems


def _validate_codex_hook_receipt_fast(receipt: Any) -> None:
    _assert_fast_schema_contract()
    privacy = _privacy_problems(receipt)
    if privacy:
        raise ContinuityValidationError("; ".join(privacy))
    problems = _fast_receipt_schema_problems(receipt)
    if problems:
        raise ContinuityValidationError("Invalid continuity receipt: " + "; ".join(problems))
    if (
        receipt["adapter_id"] != _CODEX_FAST_ADAPTER_ID
        or receipt["adapter_revision_id"] != _CODEX_FAST_ADAPTER_REVISION_ID
        or receipt["source_kind"] != "runtime_hook"
    ):
        raise ContinuityValidationError(
            "Codex hook fast validation is unavailable for this adapter receipt"
        )


def _normalize_codex_hook_receipt(receipt: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    _validate_codex_hook_receipt_fast(receipt)
    minimized, redaction_count = _minimize(dict(receipt))
    if not isinstance(minimized, dict):
        raise ContinuityValidationError("Continuity receipt must be an object")
    _validate_codex_hook_receipt_fast(minimized)
    return minimized, redaction_count


def _fast_event_schema_problems(event: Any) -> list[str]:
    """Validate the simple top-level event schema without general JSON-Schema overhead."""

    if not isinstance(event, dict):
        return ["event is not an object"]
    schema = _event_schema_contract()
    required = set(schema["required"])
    properties = schema["properties"]
    problems = [f"missing required field {key}" for key in sorted(required - set(event))]
    if schema.get("additionalProperties") is False:
        problems.extend(
            f"unexpected field {key}" for key in sorted(set(event) - set(properties))
        )
    for key, value in event.items():
        rule = properties.get(key)
        if not isinstance(rule, dict):
            continue
        expected_type = rule.get("type")
        type_ok = {
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "object": isinstance(value, dict),
        }.get(str(expected_type), True)
        if not type_ok:
            problems.append(f"field {key} has invalid type")
            continue
        if "const" in rule and value != rule["const"]:
            problems.append(f"field {key} violates const")
        if "enum" in rule and value not in rule["enum"]:
            problems.append(f"field {key} violates enum")
        if isinstance(value, str):
            if len(value) < int(rule.get("minLength", 0)):
                problems.append(f"field {key} is too short")
            if "maxLength" in rule and len(value) > int(rule["maxLength"]):
                problems.append(f"field {key} is too long")
            if "pattern" in rule and re.fullmatch(str(rule["pattern"]), value) is None:
                problems.append(f"field {key} violates pattern")
        if isinstance(value, int) and not isinstance(value, bool):
            if "minimum" in rule and value < int(rule["minimum"]):
                problems.append(f"field {key} is below minimum")
    return problems


def _fast_payload_schema_problems(payload: Any) -> list[str]:
    """Enforce the receipt payload contract during cold replay.

    The event schema intentionally leaves payload shape provider-neutral, while
    append validation also applies the adapter-receipt payload schema.  Replay
    must preserve that second boundary without invoking a general JSON-Schema
    validator for every historical row.
    """

    if not isinstance(payload, dict):
        return ["payload is not an object"]
    rule = _receipt_payload_schema_contract()
    properties = rule["properties"]
    problems: list[str] = []
    if len(payload) < int(rule.get("minProperties", 0)):
        problems.append("payload has too few properties")
    if rule.get("additionalProperties") is False:
        problems.extend(
            f"unexpected payload field {key}"
            for key in sorted(set(payload) - set(properties))
        )
    for key, value in payload.items():
        field_rule = properties.get(key)
        if not isinstance(field_rule, dict):
            continue
        expected_type = field_rule.get("type")
        type_ok = {
            "string": isinstance(value, str),
            "array": isinstance(value, list),
        }.get(str(expected_type), True)
        if not type_ok:
            problems.append(f"payload field {key} has invalid type")
            continue
        if "enum" in field_rule and value not in field_rule["enum"]:
            problems.append(f"payload field {key} violates enum")
        if isinstance(value, str):
            if "maxLength" in field_rule and len(value) > int(field_rule["maxLength"]):
                problems.append(f"payload field {key} is too long")
            if "pattern" in field_rule and re.fullmatch(
                str(field_rule["pattern"]), value
            ) is None:
                problems.append(f"payload field {key} violates pattern")
        if isinstance(value, list):
            if "maxItems" in field_rule and len(value) > int(field_rule["maxItems"]):
                problems.append(f"payload field {key} has too many items")
            if field_rule.get("uniqueItems") is True:
                canonical_items = [_canonical(item) for item in value]
                if len(canonical_items) != len(set(canonical_items)):
                    problems.append(f"payload field {key} has duplicate items")
            item_rule = field_rule.get("items", {})
            for index, item in enumerate(value):
                if item_rule.get("type") == "string" and not isinstance(item, str):
                    problems.append(f"payload field {key}[{index}] has invalid type")
                    continue
                if isinstance(item, str):
                    if len(item) < int(item_rule.get("minLength", 0)):
                        problems.append(f"payload field {key}[{index}] is too short")
                    if "maxLength" in item_rule and len(item) > int(
                        item_rule["maxLength"]
                    ):
                        problems.append(f"payload field {key}[{index}] is too long")
    return problems


def _validate_event_for_replay(event: Any) -> None:
    privacy = _privacy_problems(event)
    if privacy:
        raise ContinuityValidationError("; ".join(privacy))
    problems = _fast_event_schema_problems(event)
    if isinstance(event, dict) and "payload" in event:
        problems.extend(_fast_payload_schema_problems(event["payload"]))
    if problems:
        raise ContinuityValidationError("Invalid continuity event: " + "; ".join(problems))
    if event["payload_digest"] != canonical_digest(event["payload"]):
        raise ContinuityValidationError("payload_digest does not match payload")
    if event["event_id"] != _expected_event_id(event):
        raise ContinuityValidationError("event_id does not match event material")


def _validate_codex_hook_event_fast(event: Any) -> None:
    _assert_fast_schema_contract()
    _validate_event_for_replay(event)
    if (
        event["adapter_id"] != _CODEX_FAST_ADAPTER_ID
        or event["adapter_revision_id"] != _CODEX_FAST_ADAPTER_REVISION_ID
        or event["source_kind"] != "runtime_hook"
    ):
        raise ContinuityValidationError(
            "Codex hook fast validation is unavailable for this event"
        )


def continuity_ledger_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_portfolio_intents") / "continuity-events.jsonl"


def read_observation_events(ledger: Path) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    events: list[dict[str, Any]] = []
    prior = ""
    commands: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            raise ContinuityIntegrityError(f"blank ledger row at line {line_number}")
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContinuityIntegrityError(
                f"invalid JSON at continuity ledger line {line_number}"
            ) from exc
        try:
            _validate_event_for_replay(event)
        except ContinuityValidationError as exc:
            raise ContinuityIntegrityError(
                f"invalid event at continuity ledger line {line_number}: {exc}"
            ) from exc
        if event["prev_event_id"] != prior:
            raise ContinuityIntegrityError(f"broken continuity ledger chain at line {line_number}")
        command_id = str(event["command_id"])
        prior_command = commands.get(command_id)
        if prior_command is not None:
            if _command_material(prior_command) != _command_material(event):
                raise ContinuityIntegrityError(
                    f"conflicting command_id in continuity ledger: {command_id}"
                )
            raise ContinuityIntegrityError(
                f"duplicate command_id in continuity ledger: {command_id}"
            )
        commands[command_id] = event
        events.append(event)
        prior = str(event["event_id"])
    return events


def validate_continuity_ledger_full(ledger: Path) -> list[dict[str, Any]]:
    """Replay one ledger through the authoritative JSON Schema validators."""

    if not ledger.exists():
        return []
    events: list[dict[str, Any]] = []
    prior = ""
    commands: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(
        ledger.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            raise ContinuityIntegrityError(f"blank ledger row at line {line_number}")
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContinuityIntegrityError(
                f"invalid JSON at continuity ledger line {line_number}"
            ) from exc
        try:
            validate_event(event)
        except ContinuityValidationError as exc:
            raise ContinuityIntegrityError(
                f"invalid event at continuity ledger line {line_number}: {exc}"
            ) from exc
        if event["prev_event_id"] != prior:
            raise ContinuityIntegrityError(
                f"broken continuity ledger chain at line {line_number}"
            )
        command_id = str(event["command_id"])
        prior_command = commands.get(command_id)
        if prior_command is not None:
            if _command_material(prior_command) != _command_material(event):
                raise ContinuityIntegrityError(
                    f"conflicting command_id in continuity ledger: {command_id}"
                )
            raise ContinuityIntegrityError(
                f"duplicate command_id in continuity ledger: {command_id}"
            )
        commands[command_id] = event
        events.append(event)
        prior = str(event["event_id"])
    return events


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _stale_lock_can_be_recovered(lock_path: Path, *, stale_after_seconds: float) -> bool:
    try:
        stat = lock_path.stat()
    except FileNotFoundError:
        return False
    if time.time() - stat.st_mtime < stale_after_seconds:
        return False
    try:
        raw = lock_path.read_text(encoding="ascii").strip()
        try:
            payload = json.loads(raw)
            pid = int(payload.get("pid", 0)) if isinstance(payload, dict) else 0
        except json.JSONDecodeError:
            pid = int(raw) if raw.isdigit() else 0
    except (OSError, ValueError):
        pid = 0
    return not _process_is_alive(pid)


@contextmanager
def _stale_recovery_guard(lock_path: Path, *, deadline: float) -> Iterator[None]:
    """Serialize stale-lock decisions without replacing the durable guard file."""

    guard_path = lock_path.with_suffix(lock_path.suffix + ".recovery")
    descriptor = os.open(
        str(guard_path),
        os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0),
        0o600,
    )
    acquired = False
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"0")
            os.fsync(descriptor)
        while not acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise ContinuityIntegrityError(
                        "timed out serializing continuity lock recovery"
                    )
                time.sleep(0.01)
        yield
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _recover_stale_lock(
    lock_path: Path, *, stale_after_seconds: float, deadline: float
) -> bool:
    with _stale_recovery_guard(lock_path, deadline=deadline):
        if not _stale_lock_can_be_recovered(
            lock_path, stale_after_seconds=stale_after_seconds
        ):
            return False
        try:
            lock_path.unlink()
        except FileNotFoundError:
            return False
        return True


def _unlink_owned_lock(lock_path: Path, owner_token: str) -> None:
    try:
        payload = json.loads(lock_path.read_text(encoding="ascii"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return
    if not isinstance(payload, dict) or payload.get("owner_token") != owner_token:
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def _exclusive_lock(
    path: Path,
    *,
    timeout_seconds: float = 5.0,
    stale_after_seconds: float = LOCK_STALE_SECONDS,
) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    owner_token = secrets.token_hex(16)
    while descriptor is None:
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except (FileExistsError, PermissionError) as exc:
            if isinstance(exc, PermissionError) and not lock_path.exists():
                raise
            if _recover_stale_lock(
                lock_path,
                stale_after_seconds=stale_after_seconds,
                deadline=deadline,
            ):
                continue
            if time.monotonic() >= deadline:
                raise ContinuityIntegrityError("timed out acquiring continuity ledger lock")
            time.sleep(0.01)
    try:
        lock_owner = json.dumps(
            {
                "pid": os.getpid(),
                "created_at_epoch": time.time(),
                "owner_token": owner_token,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        os.write(descriptor, lock_owner)
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        _unlink_owned_lock(lock_path, owner_token)


def _append_line(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (_canonical(value) + "\n").encode("utf-8")
    descriptor = os.open(
        str(path),
        os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_BINARY", 0),
        0o600,
    )
    try:
        view = memoryview(payload)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("short write while appending continuity ledger")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ledger_index_path(ledger: Path) -> Path:
    return ledger.with_suffix(ledger.suffix + ".index.json")


def _ledger_bytes_and_digest(ledger: Path) -> tuple[bytes, str]:
    data = ledger.read_bytes() if ledger.exists() else b""
    return data, "sha256:" + hashlib.sha256(data).hexdigest()


def _indexed_event(ledger: Path, entry: Any) -> dict[str, Any]:
    if (
        not isinstance(entry, list)
        or len(entry) != 2
        or not all(isinstance(value, int) and value >= 0 for value in entry)
    ):
        raise ContinuityIntegrityError("invalid continuity ledger index entry")
    offset, length = entry
    with ledger.open("rb") as handle:
        handle.seek(offset)
        raw = handle.read(length)
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContinuityIntegrityError("indexed continuity event is invalid JSON") from exc
    try:
        _validate_event_for_replay(event)
    except ContinuityValidationError as exc:
        raise ContinuityIntegrityError("indexed continuity event is invalid") from exc
    return event


def _build_ledger_index(ledger: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    data, digest = _ledger_bytes_and_digest(ledger)
    commands: dict[str, list[int]] = {}
    offset = 0
    lines = data.splitlines(keepends=True)
    if len(lines) != len(events):
        raise ContinuityIntegrityError("continuity ledger/index line count mismatch")
    last_entry: list[int] = []
    for raw, event in zip(lines, events, strict=True):
        entry = [offset, len(raw)]
        commands[str(event["command_id"])] = entry
        last_entry = entry
        offset += len(raw)
    index = {
        "schema_version": LEDGER_INDEX_SCHEMA_VERSION,
        "ledger_size": len(data),
        "ledger_sha256": digest,
        "event_count": len(events),
        "last_event_id": str(events[-1]["event_id"]) if events else "",
        "last_entry": last_entry,
        "commands": commands,
        "candidate_only": True,
        "execution_authorized": False,
    }
    index["index_digest"] = canonical_digest(index)
    return index


def _write_ledger_index(ledger: Path, index: Mapping[str, Any]) -> None:
    value = {key: item for key, item in dict(index).items() if key != "index_digest"}
    value["index_digest"] = canonical_digest(value)
    atomic_write_text(
        _ledger_index_path(ledger),
        json_dumps(value, pretty=False) + "\n",
    )


def _load_ledger_index(ledger: Path) -> dict[str, Any] | None:
    path = _ledger_index_path(ledger)
    if not path.exists():
        return None
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(index, dict) or index.get("schema_version") != LEDGER_INDEX_SCHEMA_VERSION:
        return None
    expected_index_digest = canonical_digest(
        {key: item for key, item in index.items() if key != "index_digest"}
    )
    if index.get("index_digest") != expected_index_digest:
        return None
    commands = index.get("commands")
    try:
        event_count = int(index.get("event_count", -1))
        ledger_size = int(index.get("ledger_size", -1))
    except (TypeError, ValueError):
        return None
    if not isinstance(commands, dict) or event_count != len(commands):
        return None
    if any(
        re.fullmatch(r"dad:continuity-command:[0-9a-f]{64}", str(command_id)) is None
        or not isinstance(entry, list)
        or len(entry) != 2
        or not all(isinstance(value, int) and value >= 0 for value in entry)
        for command_id, entry in commands.items()
    ):
        return None
    data, digest = _ledger_bytes_and_digest(ledger)
    if ledger_size != len(data) or index.get("ledger_sha256") != digest:
        return None
    if commands:
        try:
            last = _indexed_event(ledger, index.get("last_entry"))
        except ContinuityIntegrityError:
            return None
        if last.get("event_id") != index.get("last_event_id"):
            return None
    elif index.get("last_event_id") or index.get("last_entry"):
        return None
    return index


def _load_or_rebuild_ledger_index(ledger: Path) -> dict[str, Any]:
    index = _load_ledger_index(ledger)
    if index is not None:
        return index
    events = read_observation_events(ledger)
    index = _build_ledger_index(ledger, events)
    _write_ledger_index(ledger, index)
    return index


def _refresh_continuity_ledger_path_index(ledger: Path) -> dict[str, Any]:
    with _exclusive_lock(ledger):
        events = read_observation_events(ledger)
        index = _build_ledger_index(ledger, events)
        _write_ledger_index(ledger, index)
    return {
        "event_count": int(index["event_count"]),
        "ledger_sha256": str(index["ledger_sha256"]),
        "candidate_only": True,
        "execution_authorized": False,
    }


def refresh_continuity_ledger_index(hub_root: Path) -> dict[str, Any]:
    """Validate the full ledger once and write an exact-content append index."""

    return _refresh_continuity_ledger_path_index(continuity_ledger_path(hub_root))


def _append_normalized_observation_to_ledger(
    ledger: Path,
    normalized: Mapping[str, Any],
    *,
    redaction_count: int,
    validate_new_event: Any,
    recorded_at: str | None = None,
    lock_timeout_seconds: float = 5.0,
    retry_clock_tolerant: bool = False,
) -> dict[str, Any]:
    command_id = "dad:continuity-command:" + _sha256(str(normalized["request_id"]))
    stream_id = "dad:continuity-stream:" + _sha256(
        "|".join(
            [
                str(normalized["privacy_partition"]),
                str(normalized["source_kind"]),
                str(normalized["source_id"]),
            ]
        )
    )
    recorded = recorded_at or datetime.now(timezone.utc).isoformat()
    payload = normalized["payload"]
    with _exclusive_lock(ledger, timeout_seconds=lock_timeout_seconds):
        index = _load_or_rebuild_ledger_index(ledger)
        candidate_material = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_kind": normalized["event_kind"],
            "stream_id": stream_id,
            "command_id": command_id,
            "observed_at": normalized["observed_at"],
            "adapter_id": normalized["adapter_id"],
            "adapter_revision_id": normalized["adapter_revision_id"],
            "source_kind": normalized["source_kind"],
            "source_id": normalized["source_id"],
            "source_revision": normalized["source_revision"],
            "privacy_partition": normalized["privacy_partition"],
            "payload_digest": canonical_digest(payload),
            "payload": payload,
            "candidate_only": True,
            "execution_authorized": False,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        prior_entry = index["commands"].get(command_id)
        if prior_entry is not None:
            prior = _indexed_event(ledger, prior_entry)
            prior_material = _command_material(prior)
            comparison_material = candidate_material
            if retry_clock_tolerant:
                prior_material = {k: v for k, v in prior_material.items() if k != "observed_at"}
                comparison_material = {
                    k: v for k, v in candidate_material.items() if k != "observed_at"
                }
            if prior_material == comparison_material:
                return {"status": "deduplicated", "event": prior}
            raise ContinuityConflictError(
                f"request_id was reused for different continuity material: {normalized['request_id']}"
            )
        event = {
            **candidate_material,
            "prev_event_id": str(index["last_event_id"]),
            "recorded_at": recorded,
            "redaction_count": redaction_count,
        }
        event["event_id"] = _expected_event_id(event)
        validate_new_event(event)
        offset = int(index["ledger_size"])
        length = len((_canonical(event) + "\n").encode("utf-8"))
        _append_line(ledger, event)
        _data, ledger_digest = _ledger_bytes_and_digest(ledger)
        index["ledger_size"] = offset + length
        index["ledger_sha256"] = ledger_digest
        index["event_count"] = int(index["event_count"]) + 1
        index["last_event_id"] = event["event_id"]
        index["last_entry"] = [offset, length]
        index["commands"][command_id] = [offset, length]
        _write_ledger_index(ledger, index)
    return {"status": "appended", "event": event}


def _append_observation_to_ledger(
    ledger: Path,
    receipt: Mapping[str, Any],
    *,
    recorded_at: str | None = None,
    lock_timeout_seconds: float = 5.0,
    retry_clock_tolerant: bool = False,
) -> dict[str, Any]:
    """Append one fully validated receipt or return its exact prior event."""

    normalized, redaction_count = normalize_receipt(receipt)
    return _append_normalized_observation_to_ledger(
        ledger,
        normalized,
        redaction_count=redaction_count,
        validate_new_event=validate_event,
        recorded_at=recorded_at,
        lock_timeout_seconds=lock_timeout_seconds,
        retry_clock_tolerant=retry_clock_tolerant,
    )


def _append_codex_hook_observation_to_ledger(
    ledger: Path,
    receipt: Mapping[str, Any],
    *,
    recorded_at: str | None = None,
    lock_timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Append only a native Codex hook receipt under the pinned fast contract."""

    normalized, redaction_count = _normalize_codex_hook_receipt(receipt)
    return _append_normalized_observation_to_ledger(
        ledger,
        normalized,
        redaction_count=redaction_count,
        validate_new_event=_validate_codex_hook_event_fast,
        recorded_at=recorded_at,
        lock_timeout_seconds=lock_timeout_seconds,
        retry_clock_tolerant=True,
    )


def append_observation(
    hub_root: Path,
    receipt: Mapping[str, Any],
    *,
    lock_timeout_seconds: float = 5.0,
    retry_clock_tolerant: bool = False,
) -> dict[str, Any]:
    """Append a production observation only to this hub's private data root."""

    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Continuity writes require an initialized DAD_DATA_ROOT for this hub"
        )
    return _append_observation_to_ledger(
        continuity_ledger_path(hub_root),
        receipt,
        lock_timeout_seconds=lock_timeout_seconds,
        retry_clock_tolerant=retry_clock_tolerant,
    )


def _append_codex_hook_observation(
    hub_root: Path,
    receipt: Mapping[str, Any],
    *,
    lock_timeout_seconds: float,
) -> dict[str, Any]:
    """Private production entrypoint for the schema-pinned Codex hook."""

    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Continuity writes require an initialized DAD_DATA_ROOT for this hub"
        )
    return _append_codex_hook_observation_to_ledger(
        continuity_ledger_path(hub_root),
        receipt,
        lock_timeout_seconds=lock_timeout_seconds,
    )


def _append_record_exact(
    ledger: Path,
    record: Mapping[str, Any],
    *,
    identity_field: str,
) -> str:
    """Append a strict JSON record with exact replay/conflict handling."""

    identity = str(record.get(identity_field, ""))
    if not identity:
        raise ContinuityValidationError(f"record missing {identity_field}")
    with _exclusive_lock(ledger):
        existing: list[dict[str, Any]] = []
        if ledger.exists():
            for line_number, raw in enumerate(
                ledger.read_text(encoding="utf-8").splitlines(), start=1
            ):
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ContinuityIntegrityError(
                        f"invalid JSON at record ledger line {line_number}"
                    ) from exc
                if not isinstance(row, dict):
                    raise ContinuityIntegrityError(
                        f"non-object record at record ledger line {line_number}"
                    )
                existing.append(row)
        for prior in existing:
            if str(prior.get(identity_field, "")) != identity:
                continue
            if prior == dict(record):
                return "deduplicated"
            raise ContinuityConflictError(f"conflicting record identity: {identity}")
        _append_line(ledger, record)
        return "appended"


__all__ = [
    "AUTHORITY_BOUNDARY",
    "ContinuityConflictError",
    "ContinuityIntegrityError",
    "ContinuityValidationError",
    "append_observation",
    "canonical_digest",
    "continuity_ledger_path",
    "normalize_receipt",
    "read_observation_events",
    "refresh_continuity_ledger_index",
    "validate_continuity_ledger_full",
    "validate_adapter_receipt",
    "validate_event",
]
