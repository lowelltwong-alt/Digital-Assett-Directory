"""Pure validation and narrowly scoped receipts for supervised MCP actions."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .mail_center import append_jsonl_locked

PACKET_SCHEMA_VERSION = "dad.mcp.action_packet.v1"
RESULT_SCHEMA_VERSION = "dad.mcp.action_result.v1"
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
_KINDS = frozenset({"preflight", "midflight", "postflight", "recovery", "dependency_refresh"})
_STATUSES = frozenset({"verified", "failed", "aborted"})
_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "packet_id",
        "request_id",
        "action_kind",
        "repository_id",
        "case_id",
        "source_snapshot_digest",
        "expected_preconditions_digest",
        "issued_at",
        "expires_at",
        "human_gate_required",
        "approval_ref",
        "independent_checker_required",
        "execution_authorized",
        "mutations_performed",
        "rollback_ref",
    }
)


class MCPPacketError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()
    return f"dad:{prefix}:{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise MCPPacketError(f"{label} is invalid")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise MCPPacketError(f"{label} is invalid")
    return value


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise MCPPacketError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def prepare_lifecycle_packet(
    *,
    request_id: str,
    action_kind: str,
    repository_id: str,
    source_snapshot_digest: str,
    expected_preconditions_digest: str,
    approval_ref: str,
    case_id: str = "",
    rollback_ref: str = "",
    now: datetime | None = None,
    expires_hours: int = 24,
) -> dict[str, Any]:
    request_id = _token(request_id, "request_id")
    repository_id = _token(repository_id, "repository_id")
    approval_ref = _token(approval_ref, "approval_ref")
    if action_kind not in _KINDS:
        raise MCPPacketError("action_kind is invalid")
    _digest(source_snapshot_digest, "source_snapshot_digest")
    _digest(expected_preconditions_digest, "expected_preconditions_digest")
    if case_id:
        _token(case_id, "case_id")
    if rollback_ref:
        _token(rollback_ref, "rollback_ref")
    if not isinstance(expires_hours, int) or not 1 <= expires_hours <= 168:
        raise MCPPacketError("expires_hours must be between 1 and 168")
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires = observed + timedelta(hours=expires_hours)
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "request_id": request_id,
        "action_kind": action_kind,
        "repository_id": repository_id,
        "case_id": case_id,
        "source_snapshot_digest": source_snapshot_digest,
        "expected_preconditions_digest": expected_preconditions_digest,
        "issued_at": observed.isoformat(),
        "expires_at": expires.isoformat(),
        "human_gate_required": True,
        "approval_ref": approval_ref,
        "independent_checker_required": True,
        "execution_authorized": False,
        "mutations_performed": False,
    }
    if rollback_ref:
        packet["rollback_ref"] = rollback_ref
    identity = {key: value for key, value in packet.items() if key not in {"issued_at", "expires_at"}}
    packet["packet_id"] = _id("mcp-action-packet", identity)
    return packet


def record_lifecycle_result(
    hub_root: Path,
    packet: Mapping[str, Any],
    *,
    result_status: str,
    before_snapshot_digest: str,
    after_snapshot_digest: str,
    worker_id: str,
    checker_id: str,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    unknown = set(packet) - _PACKET_FIELDS
    if unknown:
        raise MCPPacketError("packet contains unknown fields")
    if packet.get("schema_version") != PACKET_SCHEMA_VERSION or packet.get("execution_authorized") is not False:
        raise MCPPacketError("packet is not a non-authorizing MCP packet")
    if result_status not in _STATUSES:
        raise MCPPacketError("result_status is invalid")
    packet_id = _token(packet.get("packet_id"), "packet_id")
    worker_id = _token(worker_id, "worker_id")
    checker_id = _token(checker_id, "checker_id")
    if worker_id == checker_id:
        raise MCPPacketError("worker and checker must be distinct")
    before_snapshot_digest = _digest(before_snapshot_digest, "before_snapshot_digest")
    after_snapshot_digest = _digest(after_snapshot_digest, "after_snapshot_digest")
    if not evidence_refs or len(evidence_refs) > 32:
        raise MCPPacketError("evidence_refs must contain 1 to 32 references")
    evidence = sorted({_token(ref, "evidence_ref") for ref in evidence_refs})
    now = datetime.now(timezone.utc)
    if now >= _time(str(packet.get("expires_at", ""))):
        raise MCPPacketError("packet has expired")
    path = hub_root / "audit" / "events" / "mcp-action-results.jsonl"
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise MCPPacketError("result ledger contains a non-object row")
                rows.append(row)
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "packet_id": packet_id,
        "result_status": result_status,
        "before_snapshot_digest": before_snapshot_digest,
        "after_snapshot_digest": after_snapshot_digest,
        "worker_id": worker_id,
        "checker_id": checker_id,
        "evidence_refs": evidence,
        "execution_authorized": False,
    }
    result_id = _id("mcp-action-result", payload)
    payload["result_id"] = result_id
    for row in rows:
        if row.get("packet_id") != packet_id:
            continue
        if row == payload:
            return {"status": "deduplicated", **payload}
        raise MCPPacketError("packet already has a conflicting result")
    append_jsonl_locked(path, payload)
    return {"status": "recorded", **payload}


__all__ = ["MCPPacketError", "prepare_lifecycle_packet", "record_lifecycle_result"]
