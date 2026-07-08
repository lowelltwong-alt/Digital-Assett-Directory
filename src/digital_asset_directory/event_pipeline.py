from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field, ValidationError, model_validator

from .ids import stable_id
from .mail_center import (
    _policy_for_repo,
    _policy_public_facing,
    _policy_visibility,
    append_jsonl_locked,
)
from .transport import data_path
from .utils import (
    append_jsonl,
    atomic_write_text,
    json_dumps,
    redact_sensitive_text,
    sha256_bytes,
    sha256_file,
    utc_now,
)

EVENT_MIRROR_DIR = Path(".digital-asset") / "events"
EVENT_OUTBOX_NAME = "outbox.jsonl"
CENTRAL_EVENTS_DIR = Path("processed") / "events"
EVENT_LOG_PATH = CENTRAL_EVENTS_DIR / "event_log.jsonl"
RESPONSE_STATE_PATH = CENTRAL_EVENTS_DIR / "response_state.jsonl"
REPORT_JSON_PATH = CENTRAL_EVENTS_DIR / "reports" / "event_pipeline.json"
REPORT_MD_PATH = CENTRAL_EVENTS_DIR / "reports" / "event_pipeline.md"
QUARANTINE_DIR = CENTRAL_EVENTS_DIR / "quarantine"

EVENT_TYPES = {
    "lesson_found",
    "exception_seen",
    "fix_outcome",
    "asset_used",
    "asset_rejected",
    "harness_needed",
    "dad_notice_ack",
    "dad_notice_saved_for_future",
    "dad_notice_implemented",
    "dad_notice_rejected",
    "governance_drift",
    "pipeline_health",
}
RESPONSE_STATES = {
    "not_applicable",
    "acknowledged",
    "saved_for_future",
    "implementing",
    "implemented",
    "rejected",
    "deferred",
    "needs_human_review",
}
NOTICE_RESPONSE_BY_TYPE = {
    "dad_notice_ack": "acknowledged",
    "dad_notice_saved_for_future": "saved_for_future",
    "dad_notice_implemented": "implemented",
    "dad_notice_rejected": "rejected",
}
VISIBILITIES = {"public", "internal", "private", "restricted", "unknown"}
SENSITIVITIES = {"public_metadata", "internal_metadata", "private_metadata"}
PUBLIC_FACING_HOLD_VISIBILITIES = {"internal", "private", "restricted", "unknown"}
PUBLIC_TARGET_VISIBILITIES = {"public", "unknown"}
PUBLIC_SAFE_PAYLOAD_KEYS = {
    "summary",
    "note",
    "notes",
    "path",
    "paths",
    "asset_id",
    "asset_ids",
    "hash",
    "sha256",
    "source_ref",
    "source_refs",
    "notice_id",
    "event_ref",
    "status",
    "category",
    "reason",
    "review_note",
    "validation",
    "tags",
}
MAX_EVENT_RECORD_BYTES = 64_000
MAX_PAYLOAD_STRING_CHARS = 500
LOCAL_PATH_FRAGMENTS = (
    "c:/users/",
    "c__users__",
    "/users/",
    "appdata/",
    "git projects/",
    "onedrive/",
)
AUTHORITY_BOUNDARY = (
    "DAD pipeline events are append-only candidate metadata. They do not override "
    "source repo authority, satisfy human gates, approve public release, or authorize "
    "writes outside repo-local event/mail adapters."
)


def event_data_path(hub_root: Path, relative_path: Path) -> Path:
    if relative_path.parts[:2] != ("processed", "events"):
        raise ValueError(f"Unsupported event data-plane path: {relative_path}")
    return data_path(hub_root, "events").joinpath(*relative_path.parts[2:])


EventType = Literal[
    "lesson_found",
    "exception_seen",
    "fix_outcome",
    "asset_used",
    "asset_rejected",
    "harness_needed",
    "dad_notice_ack",
    "dad_notice_saved_for_future",
    "dad_notice_implemented",
    "dad_notice_rejected",
    "governance_drift",
    "pipeline_health",
]
Visibility = Literal["public", "internal", "private", "restricted", "unknown"]
Sensitivity = Literal["public_metadata", "internal_metadata", "private_metadata"]
ResponseState = Literal[
    "not_applicable",
    "acknowledged",
    "saved_for_future",
    "implementing",
    "implemented",
    "rejected",
    "deferred",
    "needs_human_review",
]


class DadPipelineEventRecord(BaseModel):
    schema_version: Literal["0.1.0"] = "0.1.0"
    event_id: str = Field(min_length=1)
    event_type: EventType
    dedupe_key: str = Field(min_length=1)
    source_repo: str = Field(min_length=1)
    source_repo_id: str = ""
    source_visibility: Visibility = "unknown"
    target_repo: str = ""
    target_repo_id: str = ""
    target_visibility: Visibility = "unknown"
    notice_id: str = ""
    actionable: bool = False
    response_state: ResponseState = "not_applicable"
    sensitivity: Sensitivity = "internal_metadata"
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    created_at: str
    collected_at: str | None = None
    collection_provenance: dict[str, Any] = Field(default_factory=dict)
    public_release: dict[str, Any] = Field(default_factory=dict)
    review_status: Literal[
        "candidate",
        "collected_candidate",
        "reviewed",
        "rejected",
        "quarantined",
    ] = "candidate"
    authority_boundary: str = AUTHORITY_BOUNDARY

    @model_validator(mode="after")
    def _notice_response_contract(self) -> "DadPipelineEventRecord":
        expected = NOTICE_RESPONSE_BY_TYPE.get(self.event_type)
        if expected and self.response_state in {"not_applicable", ""}:
            self.response_state = expected  # type: ignore[assignment]
        if self.event_type.startswith("dad_notice_") and not self.notice_id:
            raise ValueError("dad_notice response events require notice_id")
        if self.event_type.startswith("dad_notice_"):
            self.actionable = True
        return self


def repo_event_outbox(repo: Path) -> Path:
    repo_root = repo.resolve()
    events_dir = repo_root / EVENT_MIRROR_DIR
    resolved_dir = events_dir.resolve(strict=False)
    if not resolved_dir.is_relative_to(repo_root):
        raise ValueError(f"Event outbox escapes repository boundary: {events_dir}")
    outbox = events_dir / EVENT_OUTBOX_NAME
    resolved_outbox = outbox.resolve(strict=False)
    if not resolved_outbox.is_relative_to(resolved_dir):
        raise ValueError(f"Event outbox escapes event directory: {outbox}")
    return outbox


def build_event_record(
    *,
    event_type: str,
    source_repo: str,
    dedupe_key: str,
    payload: dict[str, Any] | None = None,
    evidence: list[str] | None = None,
    source_repo_id: str = "",
    source_visibility: str = "unknown",
    target_repo: str = "",
    target_repo_id: str = "",
    target_visibility: str = "unknown",
    notice_id: str = "",
    actionable: bool = False,
    response_state: str = "not_applicable",
    sensitivity: str = "internal_metadata",
    event_id: str = "",
    created_at: str | None = None,
) -> DadPipelineEventRecord:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported event_type: {event_type}")
    if source_visibility not in VISIBILITIES:
        raise ValueError(f"Unsupported source_visibility: {source_visibility}")
    if target_visibility not in VISIBILITIES:
        raise ValueError(f"Unsupported target_visibility: {target_visibility}")
    if sensitivity not in SENSITIVITIES:
        raise ValueError(f"Unsupported sensitivity: {sensitivity}")
    if response_state not in RESPONSE_STATES:
        raise ValueError(f"Unsupported response_state: {response_state}")
    event_id = event_id or stable_id("pipeline-event", source_repo, event_type, dedupe_key)
    record = DadPipelineEventRecord(
        event_id=event_id,
        event_type=event_type,  # type: ignore[arg-type]
        dedupe_key=dedupe_key,
        source_repo=source_repo,
        source_repo_id=source_repo_id,
        source_visibility=source_visibility,  # type: ignore[arg-type]
        target_repo=target_repo,
        target_repo_id=target_repo_id,
        target_visibility=target_visibility,  # type: ignore[arg-type]
        notice_id=notice_id,
        actionable=actionable,
        response_state=response_state,  # type: ignore[arg-type]
        sensitivity=sensitivity,  # type: ignore[arg-type]
        payload=payload or {},
        evidence=evidence or [],
        created_at=created_at or utc_now(),
    )
    _raise_if_unsafe_event(record.model_dump(mode="json"))
    return record


def record_repo_event(repo: Path, record: DadPipelineEventRecord) -> dict[str, Any]:
    payload = record.model_dump(mode="json")
    _raise_if_unsafe_event(payload)
    outbox = repo_event_outbox(repo)
    append_jsonl_locked(outbox, payload)
    return {
        "schema_version": "dad.event_pipeline.record.v1",
        "status": "recorded",
        "event_id": record.event_id,
        "event_type": record.event_type,
        "outbox_path": str(EVENT_MIRROR_DIR / EVENT_OUTBOX_NAME).replace("\\", "/"),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def collect_events(
    hub_root: Path,
    repos: list[Path],
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    existing_by_event_id, existing_by_dedupe = _event_log_indexes(hub_root)
    notice_index = _notice_index(hub_root)
    collected = 0
    duplicate_count = 0
    quarantined_count = 0
    response_state_count = 0
    errors: list[dict[str, Any]] = []
    for repo in repos:
        outbox = repo_event_outbox(repo)
        if not outbox.exists():
            continue
        rows, parse_errors = _read_event_jsonl(outbox)
        for error in parse_errors:
            quarantine = _quarantine_event_issue(
                hub_root,
                "malformed_event_rows.jsonl",
                {
                    "issue_type": "malformed_jsonl",
                    "source_repo": repo.name,
                    "source_path": (EVENT_MIRROR_DIR / EVENT_OUTBOX_NAME).as_posix(),
                    **error,
                },
            )
            errors.append(quarantine)
            quarantined_count += 1
        for row in rows:
            record_hash = sha256_bytes(json_dumps(row["payload"]).encode("utf-8"))
            try:
                if not isinstance(row["payload"], dict):
                    raise ValueError("event JSONL row is not an object")
                incoming = DadPipelineEventRecord(**row["payload"])
                _raise_if_unsafe_event(incoming.model_dump(mode="json"))
            except (ValidationError, ValueError) as exc:
                quarantine = _quarantine_event_issue(
                    hub_root,
                    "invalid_event_rows.jsonl",
                    {
                        "issue_type": "invalid_event_record",
                        "source_repo": repo.name,
                        "source_path": (EVENT_MIRROR_DIR / EVENT_OUTBOX_NAME).as_posix(),
                        "line_number": row["line_number"],
                        **_unsafe_identifier_hashes(row["payload"]),
                        "record_hash": record_hash,
                        "reason_code": _safe_error_code(exc),
                    },
                )
                errors.append(quarantine)
                quarantined_count += 1
                continue
            collected_record = _collected_event(
                repo,
                incoming,
                row["line_number"],
                record_hash,
                repo_policies,
            )
            try:
                _raise_if_unsafe_event(collected_record.model_dump(mode="json"))
                response_error = _response_event_error(collected_record, notice_index)
                if response_error:
                    raise ValueError(response_error)
            except ValueError as exc:
                quarantine = _quarantine_event_issue(
                    hub_root,
                    "invalid_event_rows.jsonl",
                    {
                        "issue_type": "invalid_event_record",
                        "source_repo": repo.name,
                        "source_path": (EVENT_MIRROR_DIR / EVENT_OUTBOX_NAME).as_posix(),
                        "line_number": row["line_number"],
                        "event_id": collected_record.event_id,
                        "dedupe_key": collected_record.dedupe_key,
                        "record_hash": record_hash,
                        "reason_code": _safe_error_code(exc),
                    },
                )
                errors.append(quarantine)
                quarantined_count += 1
                continue
            existing_hash = existing_by_event_id.get(incoming.event_id)
            if existing_hash is not None:
                if existing_hash != record_hash:
                    quarantine = _quarantine_event_issue(
                        hub_root,
                        "duplicate_conflicts.jsonl",
                        {
                            "issue_type": "duplicate_event_id_conflict",
                            "source_repo": repo.name,
                            "event_id": incoming.event_id,
                            "dedupe_key": incoming.dedupe_key,
                            "incoming_hash": record_hash,
                            "existing_hash": existing_hash,
                        },
                    )
                    errors.append(quarantine)
                    quarantined_count += 1
                else:
                    duplicate_count += 1
                continue
            existing_hash = existing_by_dedupe.get(incoming.dedupe_key)
            if existing_hash is not None:
                if existing_hash != record_hash:
                    quarantine = _quarantine_event_issue(
                        hub_root,
                        "duplicate_conflicts.jsonl",
                        {
                            "issue_type": "dedupe_key_conflict",
                            "source_repo": repo.name,
                            "event_id": incoming.event_id,
                            "dedupe_key": incoming.dedupe_key,
                            "incoming_hash": record_hash,
                            "existing_hash": existing_hash,
                        },
                    )
                    errors.append(quarantine)
                    quarantined_count += 1
                else:
                    duplicate_count += 1
                continue
            append_jsonl_locked(
                event_data_path(hub_root, EVENT_LOG_PATH),
                collected_record.model_dump(mode="json"),
            )
            existing_by_event_id[collected_record.event_id] = record_hash
            existing_by_dedupe[collected_record.dedupe_key] = record_hash
            if _is_notice_event(collected_record.model_dump(mode="json")):
                notice_index[collected_record.notice_id] = _notice_descriptor(collected_record)
            collected += 1
            if _write_response_state(hub_root, collected_record):
                response_state_count += 1
    report = write_event_pipeline_report(hub_root)
    return {
        "schema_version": "dad.event_pipeline.collect.v1",
        "collected_count": collected,
        "duplicate_count": duplicate_count,
        "quarantined_count": quarantined_count,
        "response_state_count": response_state_count,
        "errors": errors,
        "event_log_path": EVENT_LOG_PATH.as_posix(),
        "response_state_path": RESPONSE_STATE_PATH.as_posix(),
        "report_path": report["json_path"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def write_event_pipeline_report(hub_root: Path) -> dict[str, Any]:
    events = load_event_log(hub_root)
    response_rows = _load_jsonl(event_data_path(hub_root, RESPONSE_STATE_PATH))
    by_type = Counter(str(row.get("event_type", "unknown")) for row in events)
    by_response = Counter(str(row.get("response_state", "unknown")) for row in response_rows)
    actionable_notice_ids = {
        str(row.get("notice_id"))
        for row in events
        if _is_notice_event(row)
    }
    response_notice_ids = {
        str(row.get("notice_id"))
        for row in response_rows
        if row.get("notice_id") and str(row.get("response_state")) in RESPONSE_STATES
    }
    stale_notice_ids = sorted(actionable_notice_ids - response_notice_ids)
    report = {
        "schema_version": "dad.event_pipeline.report.v1",
        "generated_at": utc_now(),
        "event_count": len(events),
        "response_state_count": len(response_rows),
        "event_type_counts": dict(sorted(by_type.items())),
        "response_state_counts": dict(sorted(by_response.items())),
        "actionable_notice_count": len(actionable_notice_ids),
        "notice_without_response_state_count": len(stale_notice_ids),
        "notice_without_response_state_ids": stale_notice_ids[:25],
        "input_hashes": _event_report_input_hashes(hub_root),
        "event_log_path": EVENT_LOG_PATH.as_posix(),
        "response_state_path": RESPONSE_STATE_PATH.as_posix(),
        "quarantine_dir": QUARANTINE_DIR.as_posix(),
        "mailbox_edge_boundary": (
            "Mail remains the repo-facing presentation adapter; the event log is central "
            "candidate state and does not imply target adoption."
        ),
        "cloud_boundary": (
            "Cloud mirrors are deferred and may carry only public-safe metadata after human review."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    write_json_path = event_data_path(hub_root, REPORT_JSON_PATH)
    write_json_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(write_json_path, json_dumps(report, pretty=True) + "\n")
    md = [
        "# DAD Event Pipeline Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"- Events: {report['event_count']}",
        f"- Response states: {report['response_state_count']}",
        f"- Actionable notices without response state: {report['notice_without_response_state_count']}",
        f"- Event log: `{EVENT_LOG_PATH.as_posix()}`",
        f"- Response state: `{RESPONSE_STATE_PATH.as_posix()}`",
        f"- Quarantine: `{QUARANTINE_DIR.as_posix()}`",
        "",
        "## Boundary",
        "",
        AUTHORITY_BOUNDARY,
        "",
    ]
    atomic_write_text(event_data_path(hub_root, REPORT_MD_PATH), "\n".join(md))
    return {
        "schema_version": "dad.event_pipeline.report_result.v1",
        "json_path": REPORT_JSON_PATH.as_posix(),
        "markdown_path": REPORT_MD_PATH.as_posix(),
        **report,
    }


def load_event_log(hub_root: Path) -> list[dict[str, Any]]:
    return _load_jsonl(event_data_path(hub_root, EVENT_LOG_PATH))


def _collected_event(
    repo: Path,
    record: DadPipelineEventRecord,
    line_number: int,
    record_hash: str,
    repo_policies: Sequence[Any] | None,
) -> DadPipelineEventRecord:
    payload = record.model_dump(mode="json")
    source_policy = _policy_for_repo(repo, repo_policies)
    target_policy = _policy_for_repo(record.target_repo, repo_policies)
    claimed_source_visibility = str(payload.get("source_visibility", "unknown"))
    claimed_target_visibility = str(payload.get("target_visibility", "unknown"))
    if source_policy is not None:
        payload["source_repo"] = f"repo:{getattr(source_policy, 'id', 'unknown')}"
        payload["source_repo_id"] = str(getattr(source_policy, "id", ""))
        payload["source_visibility"] = _policy_visibility(source_policy)
    else:
        payload["source_repo"] = repo.name
        payload["source_repo_id"] = ""
        payload["source_visibility"] = "unknown"
    if target_policy is not None:
        payload["target_repo"] = f"repo:{getattr(target_policy, 'id', 'unknown')}"
        payload["target_repo_id"] = str(getattr(target_policy, "id", ""))
        payload["target_visibility"] = (
            "public" if _policy_public_facing(target_policy) else _policy_visibility(target_policy)
        )
    elif payload.get("target_repo"):
        payload["target_repo_id"] = ""
        payload["target_visibility"] = (
            "public" if claimed_target_visibility == "public" else "unknown"
        )
    payload["review_status"] = "collected_candidate"
    payload["collected_at"] = utc_now()
    payload["collection_provenance"] = {
        "source_repo_ref": f"repo:{repo.name}",
        "source_path": (EVENT_MIRROR_DIR / EVENT_OUTBOX_NAME).as_posix(),
        "line_number": line_number,
        "record_hash": record_hash,
        "collector": "dad_event_pipeline",
        "source_policy_status": "reviewed" if source_policy is not None else "unreviewed",
        "target_policy_status": (
            "reviewed" if target_policy is not None else "unreviewed_or_not_targeted"
        ),
        "source_claimed_visibility": claimed_source_visibility,
        "target_claimed_visibility": claimed_target_visibility,
    }
    payload["public_release"] = _public_release_status(payload)
    return DadPipelineEventRecord(**payload)


def _public_release_status(payload: dict[str, Any]) -> dict[str, Any]:
    source_visibility = str(payload.get("source_visibility", "unknown"))
    target_visibility = str(payload.get("target_visibility", "unknown"))
    target_repo = str(payload.get("target_repo", ""))
    release_required = bool(
        target_repo
        and target_visibility in PUBLIC_TARGET_VISIBILITIES
        and source_visibility in PUBLIC_FACING_HOLD_VISIBILITIES
    )
    return {
        "target_visibility": target_visibility,
        "public_release_required": release_required,
        "public_release_status": "pending_human" if release_required else "not_required",
        "human_release_id": "",
        "release_reason": (
            "non_public_or_unknown_source_to_public_target"
            if release_required
            else "local_first_candidate_metadata"
        ),
    }


def _is_response_event(record: DadPipelineEventRecord | dict[str, Any]) -> bool:
    event_type = (
        record.event_type if isinstance(record, DadPipelineEventRecord) else record.get("event_type")
    )
    return str(event_type) in NOTICE_RESPONSE_BY_TYPE


def _is_notice_event(row: dict[str, Any]) -> bool:
    return bool(row.get("notice_id")) and bool(row.get("actionable")) and not _is_response_event(row)


def _notice_descriptor(record: DadPipelineEventRecord) -> dict[str, str]:
    return {
        "notice_id": record.notice_id,
        "target_repo": record.target_repo,
        "target_repo_id": record.target_repo_id,
        "event_id": record.event_id,
    }


def _notice_index(hub_root: Path) -> dict[str, dict[str, str]]:
    notices: dict[str, dict[str, str]] = {}
    for row in load_event_log(hub_root):
        if _is_notice_event(row):
            notices[str(row["notice_id"])] = {
                "notice_id": str(row.get("notice_id", "")),
                "target_repo": str(row.get("target_repo", "")),
                "target_repo_id": str(row.get("target_repo_id", "")),
                "event_id": str(row.get("event_id", "")),
            }
    return notices


def _response_event_error(
    record: DadPipelineEventRecord,
    notices: dict[str, dict[str, str]],
) -> str:
    if not _is_response_event(record):
        return ""
    notice = notices.get(record.notice_id)
    if not notice:
        return "unknown_notice_response"
    valid_targets = {
        value
        for value in (
            notice.get("target_repo", ""),
            notice.get("target_repo_id", ""),
            f"repo:{notice.get('target_repo_id', '')}" if notice.get("target_repo_id") else "",
        )
        if value
    }
    if record.source_repo not in valid_targets and record.source_repo_id not in valid_targets:
        return "notice_response_source_target_mismatch"
    return ""


def _write_response_state(hub_root: Path, record: DadPipelineEventRecord) -> bool:
    if not record.notice_id or record.response_state == "not_applicable":
        return False
    row = {
        "schema_version": "dad.event_pipeline.response_state.v1",
        "state_id": stable_id(
            "pipeline-response",
            record.notice_id,
            record.source_repo,
            record.response_state,
            record.event_id,
        ),
        "event_id": record.event_id,
        "notice_id": record.notice_id,
        "source_repo": record.source_repo,
        "target_repo": record.target_repo,
        "response_state": record.response_state,
        "event_type": record.event_type,
        "recorded_at": record.collected_at or utc_now(),
        "review_status": "collected_candidate",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    existing = {
        str(item.get("state_id"))
        for item in _load_jsonl(event_data_path(hub_root, RESPONSE_STATE_PATH))
        if isinstance(item, dict)
    }
    if row["state_id"] in existing:
        return False
    append_jsonl_locked(event_data_path(hub_root, RESPONSE_STATE_PATH), row)
    return True


def _event_log_indexes(hub_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    by_event_id: dict[str, str] = {}
    by_dedupe: dict[str, str] = {}
    for row in _load_jsonl(event_data_path(hub_root, EVENT_LOG_PATH)):
        provenance = row.get("collection_provenance", {})
        record_hash = str(provenance.get("record_hash") or "")
        if row.get("event_id") and record_hash:
            by_event_id[str(row["event_id"])] = record_hash
        if row.get("dedupe_key") and record_hash:
            by_dedupe[str(row["dedupe_key"])] = record_hash
    return by_event_id, by_dedupe


def _event_report_input_hashes(hub_root: Path) -> dict[str, str]:
    inputs = [
        EVENT_LOG_PATH,
        RESPONSE_STATE_PATH,
        Path("schemas") / "dad-pipeline-event.schema.json",
        Path("src") / "digital_asset_directory" / "event_pipeline.py",
    ]
    return {
        path.as_posix(): _hash_path(
            event_data_path(hub_root, path)
            if path.parts[:2] == ("processed", "events")
            else hub_root / path
        )
        for path in inputs
    }


def _hash_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return f"sha256:{sha256_file(path)}"
    parts: list[str] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        try:
            rel = child.relative_to(path).as_posix()
        except ValueError:
            rel = child.name
        parts.append(f"{rel}\0{sha256_file(child)}")
    return f"sha256:{sha256_bytes(chr(10).join(parts).encode('utf-8'))}"


def _read_event_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        raw_lines = path.read_bytes().splitlines()
    except OSError as exc:
        return [], [
            {
                "line_number": 0,
                "row_hash": "",
                "reason": f"Could not read event outbox: {exc}",
            }
        ]
    for line_number, raw_line in enumerate(raw_lines, start=1):
        if not raw_line.strip():
            continue
        try:
            encoding = "utf-8-sig" if line_number == 1 else "utf-8"
            line = raw_line.decode(encoding)
        except UnicodeDecodeError:
            errors.append(
                {
                    "line_number": line_number,
                    "row_hash": sha256_bytes(raw_line),
                    "reason": "UTF-8 decode failed",
                }
            )
            continue
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "line_number": line_number,
                    "row_hash": sha256_bytes(line.encode("utf-8", errors="replace")),
                    "reason": f"JSON parse failed: {exc.msg}",
                }
            )
            continue
        rows.append({"line_number": line_number, "payload": payload})
    return rows, errors


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _quarantine_event_issue(
    hub_root: Path,
    filename: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "schema_version": "dad.event_pipeline.quarantine.v1",
        "quarantine_id": stable_id(
            "event-quarantine",
            str(payload.get("issue_type", "")),
            str(payload.get("source_repo", "")),
            str(payload.get("line_number", "")),
            str(payload.get("record_hash") or payload.get("row_hash") or ""),
        ),
        "created_at": utc_now(),
        **payload,
        "authority_boundary": (
            "Quarantine rows store metadata and hashes only; they do not copy raw event content."
        ),
    }
    path = event_data_path(hub_root, QUARANTINE_DIR) / filename
    append_jsonl(path, record)
    return {
        "issue_type": record["issue_type"],
        "quarantine": (QUARANTINE_DIR / filename).as_posix(),
        "quarantine_id": record["quarantine_id"],
        "event_id": record.get("event_id", ""),
        "dedupe_key": record.get("dedupe_key", ""),
    }


def _unsafe_identifier_hashes(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    output: dict[str, str] = {}
    for key in ("event_id", "dedupe_key", "notice_id"):
        value = str(payload.get(key, "") or "")
        if value:
            output[f"{key}_sha256"] = f"sha256:{sha256_bytes(value.encode('utf-8'))}"
    return output


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "schema_validation_failed"
    text = str(exc).strip()
    allowed = {
        "event JSONL row is not an object",
        "event record exceeds maximum metadata size",
        "event record failed best-effort credential/PII screening",
        "event record contains local absolute path-like text",
        "event record contains a long free-form string",
        "event record contains multi-line raw text",
        "event record looks like copied table/raw row data",
        "event record contains keys outside the public-safe payload policy",
        "unknown_notice_response",
        "notice_response_source_target_mismatch",
    }
    return text if text in allowed else "event_policy_validation_failed"


def _raise_if_unsafe_event(payload: dict[str, Any]) -> None:
    encoded = json_dumps(payload)
    if len(encoded.encode("utf-8")) > MAX_EVENT_RECORD_BYTES:
        raise ValueError("event record exceeds maximum metadata size")
    redacted, redaction_count = redact_sensitive_text(encoded)
    if redaction_count or redacted != encoded:
        raise ValueError("event record failed best-effort credential/PII screening")
    lowered = encoded.lower().replace("\\", "/")
    if any(fragment in lowered for fragment in LOCAL_PATH_FRAGMENTS):
        raise ValueError("event record contains local absolute path-like text")
    if _requires_public_safe_payload(payload):
        _check_public_payload_policy(payload.get("payload", {}))
    _check_payload_strings(payload)


def _requires_public_safe_payload(payload: dict[str, Any]) -> bool:
    public_release = payload.get("public_release", {})
    return bool(
        (isinstance(public_release, dict) and public_release.get("public_release_required"))
        or (payload.get("target_repo") and payload.get("target_visibility") == "public")
    )


def _check_public_payload_policy(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("event record contains keys outside the public-safe payload policy")
    disallowed = [key for key in payload if str(key) not in PUBLIC_SAFE_PAYLOAD_KEYS]
    if disallowed:
        raise ValueError("event record contains keys outside the public-safe payload policy")


def _check_payload_strings(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _check_payload_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            _check_payload_strings(item)
        return
    if not isinstance(value, str):
        return
    if len(value) > MAX_PAYLOAD_STRING_CHARS:
        raise ValueError("event record contains a long free-form string")
    if "\n" in value or "\r" in value:
        raise ValueError("event record contains multi-line raw text")
    if "\t" in value or value.count("|") >= 4 or value.count(",") >= 4:
        raise ValueError("event record looks like copied table/raw row data")
