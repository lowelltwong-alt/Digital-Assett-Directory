from __future__ import annotations

from contextlib import contextmanager
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterator

from pydantic import ValidationError

from .ids import stable_id
from .models import MailDecisionRecord, MailMessageRecord
from .utils import append_jsonl, atomic_write_text, json_dumps, redact_sensitive_text, utc_now

MAIL_MIRROR_DIR = Path(".digital-asset") / "mail"
MAIL_README_NAME = "README.md"
CENTRAL_MAIL_DIR = Path("processed") / "mail"
REPORTS_DIR = Path("processed") / "reports"
DISALLOWED_SENSITIVITIES = {"confidential", "restricted", "unknown"}
CENTRAL_ONLY_TARGETS = {"central_only", "dad"}
MAIL_FILE_NAMES = {"inbox.jsonl", "outbox.jsonl", "archive.jsonl", "README.md", "last_checked.json"}
MAX_MAIL_RECORD_BYTES = 64_000
LOCK_TIMEOUT_SECONDS = 5.0
AUTHORITY_BOUNDARY = (
    "DAD mail is append-only candidate evidence. It may suggest lessons, assets, "
    "workflows, taxonomy, capabilities, or governance notices, but it does not "
    "override target repo authority or mutate source files outside .digital-asset/mail/."
)


def _normalized_repo(value: str | Path, *, preserve_named_target: bool = False) -> str:
    text = str(value).strip()
    if preserve_named_target and (
        text in CENTRAL_ONLY_TARGETS
        or (not re.match(r"^[A-Za-z]:", text) and "/" not in text and "\\" not in text)
    ):
        return text
    try:
        text = str(Path(text).resolve())
    except OSError:
        pass
    return text.replace("\\", "/").strip()


def _repo_delivery_keys(repo: Path) -> set[str]:
    return {_normalized_repo(repo), repo.name}


def repo_mail_dir(repo: Path) -> Path:
    return _safe_repo_mail_dir(repo)


def _safe_repo_mail_dir(repo: Path) -> Path:
    repo_root = repo.resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError(f"Repository does not exist or is not a directory: {repo}")
    mail_dir = repo_root / MAIL_MIRROR_DIR
    resolved = mail_dir.resolve(strict=False)
    if not resolved.is_relative_to(repo_root):
        raise ValueError(f"Mail directory escapes repository boundary: {mail_dir}")
    return mail_dir


def _mail_file(repo: Path, name: str) -> Path:
    if name not in MAIL_FILE_NAMES:
        raise ValueError(f"Unsupported mail file: {name}")
    mail_dir = _safe_repo_mail_dir(repo)
    path = mail_dir / name
    resolved_mail_dir = mail_dir.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    if not resolved_path.is_relative_to(resolved_mail_dir):
        raise ValueError(f"Mail file escapes mailbox boundary: {path}")
    return path


def ensure_repo_mailbox(repo: Path) -> Path:
    mail_dir = repo_mail_dir(repo)
    mail_dir.mkdir(parents=True, exist_ok=True)
    readme = _mail_file(repo, MAIL_README_NAME)
    if not readme.exists():
        atomic_write_text(readme, mail_readme_text())
    return mail_dir


def mail_readme_text() -> str:
    return """# DAD Mailbox

This directory is the repo-local mailbox for Digital Asset Directory suggestions.

- `outbox.jsonl`: append-only suggestions this repo wants DAD or another repo to review.
- `inbox.jsonl`: append-only suggestions delivered to this repo.
- `archive.jsonl`: acknowledgements and local review decisions.
- `last_checked.json`: timestamp written by `asset-dir mail digest`.

Mail is candidate evidence only. It must not override this repo's source truth,
governance files, schemas, source code, hooks, secrets, or human gates.

Run a digest at most once per day unless a human asks for an immediate check:

```text
asset-dir mail digest --repo .
```
"""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        records.append(json.loads(stripped))
    return records


def _dedupe_identity(record: dict[str, Any]) -> str:
    return f"{record.get('mail_id', '')}|{record.get('dedupe_key', '')}"


@contextmanager
def _jsonl_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    started = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() - started > LOCK_TIMEOUT_SECONDS:
                raise TimeoutError(f"Timed out waiting for JSONL lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _validate_record_size(record: MailMessageRecord) -> None:
    size = len(json_dumps(record.model_dump(mode="json")).encode("utf-8"))
    if size > MAX_MAIL_RECORD_BYTES:
        raise ValueError(f"Mail record exceeds {MAX_MAIL_RECORD_BYTES} byte limit.")


def _append_unique(path: Path, record: MailMessageRecord) -> bool:
    _validate_record_size(record)
    with _jsonl_lock(path):
        payload = record.model_dump(mode="json")
        existing = {_dedupe_identity(item) for item in _read_jsonl(path)}
        identity = _dedupe_identity(payload)
        if identity in existing:
            return False
        append_jsonl(path, payload)
        return True


def _append_unique_decision(path: Path, record: MailDecisionRecord) -> bool:
    with _jsonl_lock(path):
        payload = record.model_dump(mode="json")
        existing = {str(item.get("decision_id", "")) for item in _read_jsonl(path)}
        if payload["decision_id"] in existing:
            return False
        append_jsonl(path, payload)
        return True


def _redact_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        output: list[Any] = []
        count = 0
        for item in value:
            redacted, item_count = _redact_value(item)
            output.append(redacted)
            count += item_count
        return output, count
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            redacted, item_count = _redact_value(item)
            output[str(key)] = redacted
            count += item_count
        return output, count
    return value, 0


def _build_mail_record(
    *,
    message_type: str,
    source_repo: str,
    target_repo: str,
    payload: dict[str, Any],
    evidence: list[str] | None = None,
    suggested_actions: list[str] | None = None,
    sensitivity: str = "internal",
    thread_id: str | None = None,
    dedupe_key: str | None = None,
    review_status: str = "generated_candidate",
    created_at: str | None = None,
) -> MailMessageRecord:
    if sensitivity in DISALLOWED_SENSITIVITIES:
        raise ValueError(
            "DAD mail cannot carry confidential or restricted payloads, or unknown sensitivity."
        )
    source = _normalized_repo(source_repo)
    target = _normalized_repo(target_repo, preserve_named_target=True)
    redacted_payload, redaction_count = _redact_value(payload)
    redacted_evidence, evidence_redactions = _redact_value(evidence or [])
    redacted_actions, action_redactions = _redact_value(suggested_actions or [])
    total_redactions = redaction_count + evidence_redactions + action_redactions
    if total_redactions:
        redacted_payload = {
            **redacted_payload,
            "redaction_count": total_redactions,
            "redaction_note": "Secret-like text was redacted before mail persistence.",
        }
    dedupe = dedupe_key or stable_id(
        "mail-dedupe",
        message_type,
        source,
        target,
        json_dumps(redacted_payload),
        "|".join(str(item) for item in redacted_evidence),
    )
    return MailMessageRecord(
        mail_id=stable_id("mail", message_type, source, target, dedupe),
        thread_id=thread_id or stable_id("mail-thread", source, target, dedupe),
        message_type=message_type,  # type: ignore[arg-type]
        source_repo=source,
        target_repo=target,
        created_at=created_at or utc_now(),
        dedupe_key=dedupe,
        sensitivity=sensitivity,  # type: ignore[arg-type]
        review_status=review_status,  # type: ignore[arg-type]
        payload=redacted_payload,
        evidence=[str(item) for item in redacted_evidence],
        suggested_actions=[str(item) for item in redacted_actions],
    )


def compose_mail(
    repo: Path,
    *,
    message_type: str,
    target_repo: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    evidence: list[str] | None = None,
    suggested_actions: list[str] | None = None,
    sensitivity: str = "internal",
    thread_id: str | None = None,
    dedupe_key: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    mail_dir = ensure_repo_mailbox(repo)
    record = _build_mail_record(
        message_type=message_type,
        source_repo=str(repo),
        target_repo=target_repo,
        payload={"summary": summary, **(payload or {})},
        evidence=evidence,
        suggested_actions=suggested_actions,
        sensitivity=sensitivity,
        thread_id=thread_id,
        dedupe_key=dedupe_key,
        created_at=created_at,
    )
    appended = _append_unique(_mail_file(repo, "outbox.jsonl"), record)
    return {
        "record": record.model_dump(mode="json"),
        "appended": appended,
        "outbox": str(mail_dir / "outbox.jsonl"),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def central_inbox_path(hub_root: Path, repo: Path) -> Path:
    slug = _normalized_repo(repo).replace(":", "").replace("/", "__")
    return hub_root / CENTRAL_MAIL_DIR / "inbox" / f"{slug}.jsonl"


def _canonical_collected_record(repo: Path, payload: dict[str, Any]) -> MailMessageRecord:
    incoming = MailMessageRecord(**payload)
    return _build_mail_record(
        message_type=incoming.message_type,
        source_repo=str(repo),
        target_repo=incoming.target_repo,
        payload=incoming.payload,
        evidence=incoming.evidence,
        suggested_actions=incoming.suggested_actions,
        sensitivity=incoming.sensitivity,
        review_status="collected_candidate",
        created_at=incoming.created_at,
    )


def collect_mail(hub_root: Path, repos: list[Path]) -> dict[str, Any]:
    collected = 0
    duplicates = 0
    errors: list[dict[str, str]] = []
    for repo in repos:
        try:
            outbox = _mail_file(repo, "outbox.jsonl")
            payloads = _read_jsonl(outbox)
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append({"repo": str(repo), "error": f"Invalid JSONL outbox: {exc}"})
            continue
        for payload in payloads:
            try:
                record = _canonical_collected_record(repo, payload)
            except (ValidationError, ValueError) as exc:
                errors.append({"repo": str(repo), "error": str(exc)})
                continue
            if _append_unique(central_inbox_path(hub_root, repo), record):
                collected += 1
            else:
                duplicates += 1
    report = write_mail_center_report(hub_root)
    return {
        "collected_count": collected,
        "duplicate_count": duplicates,
        "error_count": len(errors),
        "errors": errors,
        "report": report,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _all_central_messages_with_errors(
    hub_root: Path, bucket: str
) -> tuple[list[MailMessageRecord], list[dict[str, str]]]:
    directory = hub_root / CENTRAL_MAIL_DIR / bucket
    records: list[MailMessageRecord] = []
    errors: list[dict[str, str]] = []
    if not directory.exists():
        return records, errors
    for path in sorted(directory.glob("*.jsonl")):
        try:
            payloads = _read_jsonl(path)
        except json.JSONDecodeError as exc:
            errors.append({"path": str(path), "error": f"Invalid JSONL: {exc}"})
            continue
        for payload in payloads:
            try:
                records.append(MailMessageRecord(**payload))
            except ValidationError as exc:
                errors.append({"path": str(path), "error": str(exc)})
                continue
    return records, errors


def _all_central_messages(hub_root: Path, bucket: str) -> list[MailMessageRecord]:
    records, _ = _all_central_messages_with_errors(hub_root, bucket)
    return records


def route_mail(hub_root: Path, *, default_target_repo: str = "central_only") -> dict[str, Any]:
    routed = 0
    duplicates = 0
    outbox = hub_root / CENTRAL_MAIL_DIR / "outbox" / "routed.jsonl"
    records, errors = _all_central_messages_with_errors(hub_root, "inbox")
    if errors:
        report = write_mail_center_report(hub_root)
        return {
            "routed_count": routed,
            "duplicate_count": duplicates,
            "error_count": len(errors),
            "errors": errors,
            "blocked": True,
            "outbox": str(outbox),
            "report": report,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    for record in records:
        if not record.target_repo.strip():
            routed_record = _build_mail_record(
                message_type=record.message_type,
                source_repo=record.source_repo,
                target_repo=default_target_repo,
                payload=record.payload,
                evidence=record.evidence,
                suggested_actions=record.suggested_actions,
                sensitivity=record.sensitivity,
                review_status="routed_candidate",
                created_at=record.created_at,
            )
        else:
            routed_record = record.model_copy(update={"review_status": "routed_candidate"})
        if _append_unique(outbox, routed_record):
            routed += 1
        else:
            duplicates += 1
    report = write_mail_center_report(hub_root)
    return {
        "routed_count": routed,
        "duplicate_count": duplicates,
        "error_count": 0,
        "errors": [],
        "blocked": False,
        "outbox": str(outbox),
        "report": report,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _mail_exists(repo: Path, record: MailMessageRecord) -> bool:
    identity = _dedupe_identity(record.model_dump(mode="json"))
    inbox_path = _mail_file(repo, "inbox.jsonl")
    if identity in {_dedupe_identity(item) for item in _read_jsonl(inbox_path)}:
        return True
    for item in _read_jsonl(_mail_file(repo, "archive.jsonl")):
        if identity == _dedupe_identity(item):
            return True
        try:
            decision = MailDecisionRecord(**item)
        except ValidationError:
            continue
        if decision.mail_id == record.mail_id:
            return True
    return False


def _ack_record(target_repo: Path, record: MailMessageRecord) -> MailMessageRecord:
    return _build_mail_record(
        message_type="inbox_ack",
        source_repo=str(target_repo),
        target_repo=record.source_repo,
        payload={
            "summary": "Duplicate delivery acknowledged.",
            "acknowledged_mail_id": record.mail_id,
        },
        evidence=[record.mail_id],
        suggested_actions=["No duplicate inbox entry was created."],
        sensitivity="internal",
        dedupe_key=stable_id("mail-ack", str(target_repo), record.mail_id, record.dedupe_key),
        review_status="archived",
    )


def deliver_mail(hub_root: Path, repos: list[Path]) -> dict[str, Any]:
    repo_by_normalized: dict[str, Path] = {}
    for repo in repos:
        for key in _repo_delivery_keys(repo):
            repo_by_normalized[key] = repo
    delivered = 0
    acknowledged_duplicates = 0
    central_only = 0
    skipped: list[dict[str, str]] = []
    delivery_log = hub_root / CENTRAL_MAIL_DIR / "archive" / "delivery_log.jsonl"
    records, errors = _all_central_messages_with_errors(hub_root, "outbox")
    if errors:
        report = write_mail_center_report(hub_root)
        return {
            "delivered_count": delivered,
            "acknowledged_duplicate_count": acknowledged_duplicates,
            "central_only_count": central_only,
            "skipped": skipped,
            "error_count": len(errors),
            "errors": errors,
            "blocked": True,
            "report": report,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    for record in records:
        target_key = _normalized_repo(record.target_repo, preserve_named_target=True)
        if target_key in CENTRAL_ONLY_TARGETS:
            central_only += 1
            continue
        target_repo = repo_by_normalized.get(target_key)
        if target_repo is None:
            skipped.append(
                {
                    "mail_id": record.mail_id,
                    "reason": "target repo is not in the allowed delivery list",
                }
            )
            continue
        try:
            ensure_repo_mailbox(target_repo)
        except (OSError, ValueError) as exc:
            append_jsonl(
                delivery_log,
                {
                    "event_type": "central_only",
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "reason": f"target repo mailbox write failed: {exc}",
                },
            )
            central_only += 1
            continue
        if _mail_exists(target_repo, record):
            ack = _ack_record(target_repo, record)
            _append_unique(_mail_file(target_repo, "archive.jsonl"), ack)
            append_jsonl(delivery_log, {"event_type": "duplicate_ack", "mail_id": record.mail_id})
            acknowledged_duplicates += 1
            continue
        delivered_record = record.model_copy(update={"review_status": "delivered_candidate"})
        _append_unique(_mail_file(target_repo, "inbox.jsonl"), delivered_record)
        append_jsonl(
            delivery_log,
            {"event_type": "delivered", "mail_id": record.mail_id, "target_repo": str(target_repo)},
        )
        delivered += 1
    report = write_mail_center_report(hub_root)
    return {
        "delivered_count": delivered,
        "acknowledged_duplicate_count": acknowledged_duplicates,
        "central_only_count": central_only,
        "skipped": skipped,
        "error_count": 0,
        "errors": [],
        "blocked": False,
        "report": report,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def review_mail(
    repo: Path,
    *,
    mail_id: str,
    decision: str,
    decided_by: str = "unknown",
    notes: str = "",
    decided_at: str | None = None,
) -> dict[str, Any]:
    ensure_repo_mailbox(repo)
    matching = [
        item
        for item in _read_jsonl(_mail_file(repo, "inbox.jsonl"))
        if str(item.get("mail_id")) == mail_id
    ]
    if not matching:
        raise ValueError(f"No inbox mail found for {mail_id}.")
    record = MailDecisionRecord(
        decision_id=stable_id("mail-decision", str(repo), mail_id, decision),
        mail_id=mail_id,
        repository=_normalized_repo(repo),
        decision=decision,  # type: ignore[arg-type]
        decided_at=decided_at or utc_now(),
        decided_by=decided_by,
        notes=notes,
    )
    archive_path = _mail_file(repo, "archive.jsonl")
    appended = _append_unique_decision(archive_path, record)
    return {
        "decision": record.model_dump(mode="json"),
        "appended": appended,
        "archive": str(archive_path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def digest_mail(repo: Path, *, checked_at: str | None = None) -> dict[str, Any]:
    ensure_repo_mailbox(repo)
    inbox = _read_jsonl(_mail_file(repo, "inbox.jsonl"))
    archive = _read_jsonl(_mail_file(repo, "archive.jsonl"))
    reviewed_ids: set[str] = set()
    for item in archive:
        try:
            reviewed_ids.add(MailDecisionRecord(**item).mail_id)
        except ValidationError:
            continue
    unread = [item for item in inbox if str(item.get("mail_id")) not in reviewed_ids]
    timestamp = checked_at or utc_now()
    last_checked = _mail_file(repo, "last_checked.json")
    atomic_write_text(
        last_checked,
        json_dumps({"last_checked_at": timestamp, "unread_count": len(unread)}, pretty=True) + "\n",
    )
    return {
        "repo": _normalized_repo(repo),
        "checked_at": timestamp,
        "inbox_count": len(inbox),
        "unread_count": len(unread),
        "reviewed_count": len(reviewed_ids),
        "unread": unread,
        "last_checked": str(last_checked),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def mail_digest_status(repo: Path, *, now: str | None = None, stale_hours: int = 24) -> dict[str, Any]:
    from datetime import datetime, timezone

    try:
        last_checked = _mail_file(repo, "last_checked.json")
    except ValueError as exc:
        return {"status": "invalid", "stale": True, "last_checked_at": None, "error": str(exc)}
    if not last_checked.exists():
        return {"status": "missing", "stale": True, "last_checked_at": None}
    try:
        payload = json.loads(last_checked.read_text(encoding="utf-8"))
        checked = datetime.fromisoformat(str(payload.get("last_checked_at")))
    except (ValueError, OSError, json.JSONDecodeError):
        return {"status": "invalid", "stale": True, "last_checked_at": None}
    current = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    if checked.tzinfo is None or current.tzinfo is None:
        return {"status": "invalid", "stale": True, "last_checked_at": checked.isoformat()}
    if checked > current:
        return {"status": "future", "stale": True, "last_checked_at": checked.isoformat()}
    age_hours = (current - checked).total_seconds() / 3600
    return {
        "status": "stale" if age_hours > stale_hours else "fresh",
        "stale": age_hours > stale_hours,
        "last_checked_at": checked.isoformat(),
        "age_hours": round(age_hours, 2),
    }


def write_mail_center_report(hub_root: Path) -> dict[str, str]:
    inbox = _all_central_messages(hub_root, "inbox")
    outbox = _all_central_messages(hub_root, "outbox")
    archive_dir = hub_root / CENTRAL_MAIL_DIR / "archive"
    archive_count = (
        sum(len(_read_jsonl(path)) for path in archive_dir.glob("*.jsonl"))
        if archive_dir.exists()
        else 0
    )
    summary = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inbox_count": len(inbox),
        "outbox_count": len(outbox),
        "archive_count": archive_count,
        "message_type_counts": {},
    }
    counts: dict[str, int] = {}
    for record in [*inbox, *outbox]:
        counts[record.message_type] = counts.get(record.message_type, 0) + 1
    summary["message_type_counts"] = dict(sorted(counts.items()))
    report_json = hub_root / REPORTS_DIR / "mail_center.json"
    report_md = hub_root / REPORTS_DIR / "mail_center.md"
    atomic_write_text(report_json, json_dumps(summary, pretty=True) + "\n")
    lines = [
        "# DAD Mail Center",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Central inbox messages: **{summary['inbox_count']}**",
        f"- Central outbox messages: **{summary['outbox_count']}**",
        f"- Archive events: **{summary['archive_count']}**",
        "",
        "## Message Types",
        "",
    ]
    for message_type, count in summary["message_type_counts"].items():
        lines.append(f"- `{message_type}`: **{count}**")
    atomic_write_text(report_md, "\n".join(lines) + "\n")
    return {"report_markdown": str(report_md), "report_json": str(report_json)}
