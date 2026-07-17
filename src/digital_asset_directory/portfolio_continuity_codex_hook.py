"""Privacy-minimized Codex lifecycle hook bridge for supervised shadow trials."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .portfolio_continuity_adapter import ingest_receipt
from .portfolio_continuity_events import _append_line, _exclusive_lock
from .transport import data_path
CODEX_HOOK_ADAPTER_ID = "adapter:intent-continuity-shadow"
CODEX_HOOK_ADAPTER_REVISION_ID = "adapter-revision:intent-continuity-codex-host:0.3.5"
MAX_HOOK_INPUT_BYTES = 64 * 1024
HOOK_LOCK_TIMEOUT_SECONDS = 1.5
AUTHORITY_BOUNDARY = (
    "The Codex shadow hook hashes only event identity metadata and ignores cwd, model, "
    "permission mode, transcript paths, prompts, messages, and source content. It cannot "
    "notify, schedule, call a model or network, mutate Git or tasks, or clean up work."
)

_EVENT_KIND = {
    "SessionStart": "session_started",
    "PreCompact": "interruption_observed",
    "PostCompact": "resumption_observed",
    "Stop": "turn_stopped",
}
_REASON_CODE = {
    "SessionStart": "codex_session_start",
    "PreCompact": "codex_pre_compact",
    "PostCompact": "codex_post_compact",
    "Stop": "codex_turn_stop",
}


class CodexHookInputError(ValueError):
    """The hook input cannot be represented by the minimized receipt contract."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bounded_string(payload: Mapping[str, Any], key: str, *, required: bool) -> str:
    value = payload.get(key, "")
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value) or len(value) > 512:
        raise CodexHookInputError(f"Codex hook field {key!r} is invalid")
    return value


_REPOSITORY_ID = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")


def _identity_material(
    hook_input: Mapping[str, Any], repository_id: str
) -> dict[str, str]:
    event_name = _bounded_string(hook_input, "hook_event_name", required=True)
    if event_name not in _EVENT_KIND:
        raise CodexHookInputError(f"Unsupported Codex hook event: {event_name}")
    session_id = _bounded_string(hook_input, "session_id", required=True)
    turn_id = _bounded_string(
        hook_input,
        "turn_id",
        required=event_name != "SessionStart",
    )
    qualifier_key = "source" if event_name == "SessionStart" else "trigger"
    qualifier = _bounded_string(hook_input, qualifier_key, required=False)
    if repository_id and _REPOSITORY_ID.fullmatch(repository_id) is None:
        raise CodexHookInputError("repository_id is invalid")
    return {
        "adapter_revision_id": CODEX_HOOK_ADAPTER_REVISION_ID,
        "event_name": event_name,
        "session_id": session_id,
        "turn_id": turn_id,
        "qualifier": qualifier,
        "repository_id": repository_id,
    }


def build_codex_hook_receipt(
    hook_input: Mapping[str, Any],
    *,
    observed_at: str | None = None,
    repository_id: str = "",
) -> dict[str, Any]:
    """Convert one Codex hook payload into a content-free provider-neutral receipt."""

    identity = _identity_material(hook_input, repository_id)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    event_name = identity["event_name"]
    identity_digest = _digest(identity)
    opaque_session = "codex-session:" + _digest(identity["session_id"]).split(":", 1)[1]
    coverage_gaps = ["codex_task_metadata_not_supplied", "hook_input_content_fields_ignored"]
    if not repository_id:
        coverage_gaps.append("repository_enrollment_id_not_supplied")
    payload = {
        "session_id": opaque_session,
        "reason_code": _REASON_CODE[event_name],
        "source_digest": identity_digest,
        "coverage_status": "partial",
        "coverage_gaps": coverage_gaps,
    }
    if repository_id:
        payload["repository_id"] = repository_id
    return {
        "schema_version": "dad.portfolio_continuity_adapter_receipt.v1",
        "request_id": "codex-shadow:" + identity_digest.split(":", 1)[1],
        "adapter_id": CODEX_HOOK_ADAPTER_ID,
        "adapter_revision_id": CODEX_HOOK_ADAPTER_REVISION_ID,
        "source_kind": "runtime_hook",
        "source_id": opaque_session,
        "source_revision": "codex-hook:" + identity_digest.split(":", 1)[1],
        "event_kind": _EVENT_KIND[event_name],
        "observed_at": observed,
        "privacy_partition": "private:personal",
        "payload": payload,
    }


def ingest_codex_hook(
    hub_root: Path,
    hook_input: Mapping[str, Any],
    *,
    repository_id: str = "",
) -> dict[str, Any]:
    """Ingest one real Codex event with stable retry behavior and no action surface."""

    receipt = build_codex_hook_receipt(hook_input, repository_id=repository_id)
    return ingest_receipt(
        hub_root,
        receipt,
        lock_timeout_seconds=HOOK_LOCK_TIMEOUT_SECONDS,
        retry_clock_tolerant=True,
    )


def hook_failure_ledger_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_portfolio_intents") / "continuity-hook-failures.jsonl"


def _validate_hook_failure_marker(marker: Mapping[str, Any]) -> None:
    from jsonschema import FormatChecker
    from jsonschema.validators import validator_for

    schema_path = (
        Path(__file__).resolve().parents[2]
        / "schemas/intent-continuity-hook-failure-marker.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(dict(marker)), key=lambda error: list(error.path))
    if errors:
        rendered = "; ".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise CodexHookInputError("Invalid hook failure marker: " + rendered)
    if marker.get("failure_id") != _expected_failure_id(marker):
        raise CodexHookInputError("Hook failure marker identity does not match material")


def _expected_failure_id(marker: Mapping[str, Any]) -> str:
    material = {key: item for key, item in marker.items() if key != "failure_id"}
    return "dad:hook-failure:" + hashlib.sha256(
        _canonical(material).encode("utf-8")
    ).hexdigest()


def record_codex_hook_failure(
    hub_root: Path,
    hook_input: Mapping[str, Any],
    *,
    repository_id: str = "",
    reason_code: str,
) -> dict[str, Any]:
    """Append one content-free best-effort marker when normal hook ingestion fails."""

    if reason_code not in {"hook_ingest_failed"}:
        raise CodexHookInputError("Unsupported hook failure reason")
    identity = _identity_material(hook_input, repository_id)
    identity_digest = _digest(identity)
    material = {
        "schema_version": "dad.intent_continuity_hook_failure_marker.v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "adapter_revision_id": CODEX_HOOK_ADAPTER_REVISION_ID,
        "runtime_event": identity["event_name"],
        "repository_id": repository_id,
        "source_digest": identity_digest,
        "reason_code": reason_code,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    marker = {
        **material,
        "failure_id": _expected_failure_id(material),
    }
    _validate_hook_failure_marker(marker)
    path = hook_failure_ledger_path(hub_root)
    with _exclusive_lock(path, timeout_seconds=0.5):
        _append_line(path, marker)
    return marker


def read_codex_hook_failures(hub_root: Path) -> list[dict[str, Any]]:
    path = hook_failure_ledger_path(hub_root)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CodexHookInputError(
                f"Invalid hook failure marker at line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise CodexHookInputError(
                f"Non-object hook failure marker at line {line_number}"
            )
        _validate_hook_failure_marker(value)
        rows.append(value)
    return rows


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CODEX_HOOK_ADAPTER_ID",
    "CODEX_HOOK_ADAPTER_REVISION_ID",
    "HOOK_LOCK_TIMEOUT_SECONDS",
    "CodexHookInputError",
    "MAX_HOOK_INPUT_BYTES",
    "build_codex_hook_receipt",
    "hook_failure_ledger_path",
    "ingest_codex_hook",
    "read_codex_hook_failures",
    "record_codex_hook_failure",
]
