"""Bounded local-file adapter for the Portfolio OS capture inbox.

The adapter reads only an explicit path, never creates or edits that path, and
writes DAD-local append-only candidate evidence plus a privacy-safe report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .portfolio_capture_core import CaptureCoreLimits, structure_capture_lines
from .portfolio_events import LedgerLock
from .transport import data_path
from .utils import atomic_write_text, json_dumps

REPORT_SCHEMA_VERSION = "dad.portfolio_capture_inbox_report.v1"
DEFAULT_MAX_INBOX_BYTES = 512_000
MAX_LEDGER_BYTES = 16_000_000
MAX_LEDGER_RECORDS = 20_000

AUTHORITY_BOUNDARY = (
    "This adapter reads one explicitly supplied local inbox without changing or "
    "acknowledging it. It writes only DAD-local candidate evidence and a sanitized "
    "report; it cannot create workstreams, dispatch agents, schedule itself, activate "
    "a daemon, mutate repositories, clear an inbox, or grant execution authority."
)


class CaptureInboxError(ValueError):
    """A bounded input, ledger-integrity, or schema condition blocked the run."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureInboxSettings:
    max_inbox_bytes: int = DEFAULT_MAX_INBOX_BYTES
    max_lines: int = 500
    max_line_chars: int = 2_000

    def __post_init__(self) -> None:
        if not 1_024 <= self.max_inbox_bytes <= 8_000_000:
            raise ValueError("max_inbox_bytes must be between 1024 and 8000000")
        CaptureCoreLimits(
            max_lines=self.max_lines,
            max_line_chars=self.max_line_chars,
        )


def _observed_at(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + sha256(value).hexdigest()


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return _digest_bytes(payload)


def report_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports") / "portfolio_os" / "capture-inbox.json"


def candidate_ledger_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports") / "portfolio_os" / "structured-captures.jsonl"


def _reject_output_alias(hub_root: Path, inbox_path: Path) -> None:
    """Fail before reading when the declared source aliases a DAD output."""

    if not inbox_path.exists():
        return
    try:
        source = inbox_path.resolve(strict=True)
    except OSError as exc:
        raise CaptureInboxError("capture inbox path could not be resolved") from exc
    for output in (report_path(hub_root), candidate_ledger_path(hub_root)):
        try:
            output_resolved = output.resolve(strict=output.exists())
        except OSError as exc:
            raise CaptureInboxError("capture output path could not be resolved") from exc
        aliases = source == output_resolved
        if not aliases and output.exists():
            try:
                aliases = os.path.samefile(source, output)
            except OSError as exc:
                raise CaptureInboxError("capture output identity could not be verified") from exc
        if aliases:
            raise CaptureInboxError(
                "capture inbox must not alias the capture report or candidate ledger"
            )


def _load_schema(hub_root: Path, name: str) -> dict[str, Any]:
    return json.loads((hub_root / "schemas" / name).read_text(encoding="utf-8"))


def _validate(hub_root: Path, value: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(hub_root, schema_name)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=FormatChecker()).validate(value)


def _read_explicit_inbox(path: Path, *, max_bytes: int) -> tuple[bytes, str]:
    if not path.exists():
        raise CaptureInboxError("capture inbox does not exist")
    if not path.is_file():
        raise CaptureInboxError("capture inbox is not a regular file")
    try:
        with path.open("rb") as handle:
            payload = handle.read(max_bytes + 1)
    except OSError as exc:
        raise CaptureInboxError("capture inbox could not be read") from exc
    if len(payload) > max_bytes:
        return payload[:max_bytes], "byte_budget_exhausted"
    return payload, ""


def inspect_capture_inbox(
    inbox_path: Path,
    *,
    settings: CaptureInboxSettings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build an in-memory bounded batch without writing any file."""

    settings = settings or CaptureInboxSettings()
    observed = _observed_at(now)
    payload, byte_problem = _read_explicit_inbox(inbox_path, max_bytes=settings.max_inbox_bytes)
    problems = [byte_problem] if byte_problem else []
    text = ""
    if not problems:
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            problems.append("invalid_utf8")
    source_fingerprint = _digest_bytes(payload) if not problems else ""
    core = structure_capture_lines(
        text.splitlines() if not problems else (),
        source_fingerprint=source_fingerprint,
        captured_at=observed.isoformat(),
        limits=CaptureCoreLimits(
            max_lines=settings.max_lines,
            max_line_chars=settings.max_line_chars,
        ),
    )
    problems.extend(core["coverage"]["problems"])
    complete = not problems and core["coverage"]["complete"]
    return {
        "observed_at": observed.isoformat(),
        "source_byte_count": len(payload),
        "source_fingerprint": source_fingerprint if complete else "",
        "core": core if complete else {**core, "candidates": []},
        "complete": complete,
        "problems": sorted(set(problems)),
        "limits": {
            "max_inbox_bytes": settings.max_inbox_bytes,
            "max_lines": settings.max_lines,
            "max_line_chars": settings.max_line_chars,
        },
    }


def _read_existing_candidates(path: Path) -> tuple[list[dict[str, Any]], bytes]:
    if not path.exists():
        return [], b""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CaptureInboxError("structured capture ledger could not be inspected") from exc
    if size > MAX_LEDGER_BYTES:
        raise CaptureInboxError("structured capture ledger byte budget exhausted")
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise CaptureInboxError("structured capture ledger has a torn tail")
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(data.splitlines(), start=1):
        if line_number > MAX_LEDGER_RECORDS:
            raise CaptureInboxError("structured capture ledger record budget exhausted")
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CaptureInboxError("structured capture ledger is malformed") from exc
        if not isinstance(value, dict):
            raise CaptureInboxError("structured capture ledger contains a non-object")
        rows.append(value)
    return rows, data


def _append_new_candidates(
    hub_root: Path,
    path: Path,
    candidates: list[dict[str, Any]],
) -> tuple[int, int, int, str]:
    for candidate in candidates:
        _validate(hub_root, candidate, "portfolio-capture-candidate.schema.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with LedgerLock(path):
        existing, existing_bytes = _read_existing_candidates(path)
        existing_by_id: dict[str, dict[str, Any]] = {}
        for row in existing:
            _validate(hub_root, row, "portfolio-capture-candidate.schema.json")
            candidate_id = str(row["candidate_id"])
            prior = existing_by_id.get(candidate_id)
            if prior is not None and prior != row:
                raise CaptureInboxError("structured capture ledger has an identity conflict")
            existing_by_id[candidate_id] = row
        pending = [row for row in candidates if str(row["candidate_id"]) not in existing_by_id]
        buffer = "".join(json_dumps(row) + "\n" for row in pending).encode("utf-8")
        if len(existing_bytes) + len(buffer) > MAX_LEDGER_BYTES:
            raise CaptureInboxError("structured capture ledger append exceeds byte budget")
        if len(existing) + len(pending) > MAX_LEDGER_RECORDS:
            raise CaptureInboxError("structured capture ledger append exceeds record budget")
        if buffer:
            fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
            try:
                view = memoryview(buffer)
                while view:
                    written = os.write(fd, view)
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
        final_bytes = existing_bytes + buffer
    return (
        len(pending),
        len(candidates) - len(pending),
        len(existing) + len(pending),
        _digest_bytes(final_bytes),
    )


def build_capture_inbox_report(
    hub_root: Path,
    inbox_path: Path,
    *,
    settings: CaptureInboxSettings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Inspect, append complete candidates, and return a path-free report."""

    _reject_output_alias(hub_root, inbox_path)
    inspected = inspect_capture_inbox(inbox_path, settings=settings, now=now)
    core = inspected["core"]
    candidates = list(core["candidates"])
    appended = deduplicated = ledger_count = 0
    ledger_fingerprint = ""
    if inspected["complete"]:
        appended, deduplicated, ledger_count, ledger_fingerprint = _append_new_candidates(
            hub_root,
            candidate_ledger_path(hub_root),
            candidates,
        )
    summary = {
        "observed_line_count": core["summary"]["observed_line_count"],
        "candidate_count": len(candidates),
        "new_candidate_count": appended,
        "duplicate_candidate_count": deduplicated + core["summary"]["duplicate_line_count"],
        "blank_line_count": core["summary"]["blank_line_count"],
        "redaction_count": core["summary"]["redaction_count"],
        "human_decision_count": len(candidates),
    }
    body = {
        "generated_at": inspected["observed_at"],
        "status": "current_candidate" if inspected["complete"] else "partial_candidate",
        "source": {
            "fingerprint": inspected["source_fingerprint"],
            "byte_count": inspected["source_byte_count"],
            "mutated": False,
        },
        "summary": summary,
        "coverage": {
            "complete": inspected["complete"],
            "problems": inspected["problems"],
            "limits": inspected["limits"],
        },
        "ledger": {
            "record_count": ledger_count,
            "fingerprint": ledger_fingerprint,
            "schema_version": "dad.portfolio_capture_candidate.v1",
        },
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        **body,
        "report_id": "dad:portfolio-capture-inbox:" + _canonical_digest(body).split(":", 1)[1],
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _validate(hub_root, report, "portfolio-capture-inbox-report.schema.json")
    return report


def write_capture_inbox_outputs(
    hub_root: Path,
    inbox_path: Path,
    *,
    settings: CaptureInboxSettings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    report = build_capture_inbox_report(hub_root, inbox_path, settings=settings, now=now)
    target = report_path(hub_root)
    atomic_write_text(target, json_dumps(report, pretty=True) + "\n")
    return {
        "status": report["status"],
        "report_path": str(target),
        "candidate_ledger_path": str(candidate_ledger_path(hub_root)),
        "summary": report["summary"],
        "coverage": report["coverage"],
        "source_mutated": False,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CaptureInboxError",
    "CaptureInboxSettings",
    "build_capture_inbox_report",
    "candidate_ledger_path",
    "inspect_capture_inbox",
    "report_path",
    "write_capture_inbox_outputs",
]
