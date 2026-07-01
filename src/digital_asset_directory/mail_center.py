from __future__ import annotations

from contextlib import contextmanager
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterator, Sequence

from pydantic import ValidationError

from .ids import stable_id
from .models import MailAdoptionRecord, MailDecisionRecord, MailMessageRecord
from .utils import (
    append_jsonl,
    atomic_write_text,
    json_dumps,
    redact_sensitive_text,
    sha256_bytes,
    utc_now,
)

MAIL_MIRROR_DIR = Path(".digital-asset") / "mail"
MAIL_README_NAME = "README.md"
MAIL_GITIGNORE_NAME = ".gitignore"
CENTRAL_MAIL_DIR = Path("processed") / "mail"
REPORTS_DIR = Path("processed") / "reports"
DISALLOWED_SENSITIVITIES = {"confidential", "restricted", "unknown"}
CENTRAL_ONLY_TARGETS = {"central_only", "dad"}
MAIL_FILE_NAMES = {
    "inbox.jsonl",
    "outbox.jsonl",
    "archive.jsonl",
    "adoption.jsonl",
    "README.md",
    "last_checked.json",
    ".gitignore",
}
MAX_MAIL_RECORD_BYTES = 64_000
MAX_PUBLIC_PAYLOAD_STRING = 500
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 300.0
VISIBILITIES = {"public", "internal", "private", "restricted", "unknown"}
NON_PUBLIC_VISIBILITIES = {"internal", "private", "restricted", "unknown"}
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
    "capability",
    "taxonomy",
    "redaction_count",
    "redaction_note",
}
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


def _policy_path(policy: Any) -> str:
    try:
        return _normalized_repo(getattr(policy, "path"))
    except (AttributeError, TypeError):
        return ""


def _policy_aliases(policy: Any) -> set[str]:
    aliases = set()
    for attr in ("id", "alias"):
        value = str(getattr(policy, attr, "") or "").strip()
        if value:
            aliases.add(value)
    path = _policy_path(policy)
    if path:
        aliases.add(Path(path).name)
    return aliases


def _policy_visibility(policy: Any | None) -> str:
    value = str(getattr(policy, "visibility", "unknown") if policy else "unknown")
    return value if value in VISIBILITIES else "unknown"


def _policy_public_facing(policy: Any | None) -> bool:
    return bool(getattr(policy, "public_facing", False)) if policy else False


def _policy_write_protected(policy: Any | None) -> bool:
    return bool(getattr(policy, "write_protected", False)) if policy else False


def _write_protection_reason(policy: Any | None) -> str:
    reason = str(getattr(policy, "write_protection_reason", "") if policy else "").strip()
    return reason or "repo mailbox is write-protected by reviewed DAD policy"


def _raise_if_write_protected(repo: Path | str, policy: Any | None, *, operation: str) -> None:
    if _policy_write_protected(policy):
        raise ValueError(
            f"DAD mail {operation} is write-protected for {repo}: "
            f"{_write_protection_reason(policy)}"
        )


def _policy_by_path(policies: Sequence[Any] | None) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for policy in policies or []:
        if not getattr(policy, "mail_enabled", True):
            continue
        path = _policy_path(policy)
        if path:
            output[path] = policy
    return output


def _policy_for_repo(repo: Path | str, policies: Sequence[Any] | None) -> Any | None:
    normalized = _normalized_repo(repo, preserve_named_target=True)
    by_path = _policy_by_path(policies)
    if normalized in by_path:
        return by_path[normalized]
    matches = [
        policy
        for policy in policies or []
        if normalized in _policy_aliases(policy) and getattr(policy, "mail_enabled", True)
    ]
    return matches[0] if len(matches) == 1 else None


def _delivery_key_map(
    repos: list[Path], policies: Sequence[Any] | None
) -> tuple[dict[str, Path], dict[str, list[str]]]:
    repo_by_key: dict[str, Path] = {}
    collisions: dict[str, list[str]] = {}
    candidate_keys: dict[str, list[Path]] = {}
    for repo in repos:
        normalized = _normalized_repo(repo)
        candidate_keys.setdefault(normalized, []).append(repo)
        policy = _policy_for_repo(repo, policies)
        if policy:
            for alias in _policy_aliases(policy):
                candidate_keys.setdefault(alias, []).append(repo)
        else:
            candidate_keys.setdefault(repo.name, []).append(repo)
    for key, values in candidate_keys.items():
        unique = {str(path.resolve()): path for path in values}
        if len(unique) == 1:
            repo_by_key[key] = next(iter(unique.values()))
        else:
            collisions[key] = sorted(unique)
    return repo_by_key, collisions


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
    gitignore = _mail_file(repo, MAIL_GITIGNORE_NAME)
    if not gitignore.exists():
        atomic_write_text(gitignore, mail_gitignore_text())
    return mail_dir


def mail_gitignore_text() -> str:
    return """*.jsonl
last_checked.json
"""


def mail_readme_text() -> str:
    return """# DAD Mailbox

This directory is the repo-local mailbox for Digital Asset Directory suggestions.

- `outbox.jsonl`: append-only suggestions this repo wants DAD or another repo to review.
- `inbox.jsonl`: append-only suggestions delivered to this repo.
- `archive.jsonl`: acknowledgements and local review decisions.
- `adoption.jsonl`: local triage, implementation, and future-use asset pointers.
- `last_checked.json`: timestamp written by `asset-dir mail digest`.
- `.gitignore`: keeps operational mailbox data local by default.

Mail is candidate evidence only. It must not override this repo's source truth,
governance files, schemas, source code, hooks, secrets, or human gates.
Agent review is triage only. Human review is required for any local adoption,
and private/internal/restricted/unknown-origin mail cannot be released to a
public-facing target unless DAD records an explicit human release.

Run a digest at most once per day unless a human asks for an immediate check:

```text
asset-dir mail digest --repo .
```

After reading inbox mail, record whether the suggestion should be implemented
now, saved for future, deferred, rejected, or archived:

```text
asset-dir mail triage --repo . --mail-id <id> --decision save_for_future
```

If this repo uses or watches a DAD asset, record that separately so DAD can send
targeted upgrade notices later:

```text
asset-dir usage record --repo . --asset <dad-offering-or-asset-id> --status watching
```

Do not commit mailbox JSONL to a public-facing repo unless a human explicitly
reviews the packet provenance and public-release status.
"""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records, _ = _read_jsonl_with_errors(path)
    return records


def _read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_bytes().splitlines(), start=1):
        stripped_bytes = line.strip()
        if not stripped_bytes:
            continue
        try:
            stripped = stripped_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "error": f"Invalid UTF-8: {exc}",
                    "raw_sha256": sha256_bytes(stripped_bytes),
                }
            )
            continue
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "error": str(exc),
                    "raw_sha256": sha256_bytes(stripped_bytes),
                }
            )
    return records, errors


def _quarantine_jsonl_errors(hub_root: Path, errors: list[dict[str, Any]]) -> None:
    if not errors:
        return
    quarantine = hub_root / CENTRAL_MAIL_DIR / "quarantine" / "malformed_jsonl.jsonl"
    for error in errors:
        append_jsonl(quarantine, {"event_type": "malformed_jsonl", "created_at": utc_now(), **error})


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
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json_dumps({"pid": os.getpid(), "created_at": utc_now()}))
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > STALE_LOCK_SECONDS:
                    lock_path.unlink()
                    continue
            except OSError:
                pass
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


def _append_unique_adoption(path: Path, record: MailAdoptionRecord) -> bool:
    with _jsonl_lock(path):
        payload = record.model_dump(mode="json")
        existing = {str(item.get("adoption_id", "")) for item in _read_jsonl(path)}
        if payload["adoption_id"] in existing:
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


def _source_provenance(
    repo: Path | str,
    *,
    policy: Any | None = None,
    incoming: dict[str, Any] | None = None,
    composed_by: str = "unknown",
    collected_by: str = "dad",
    collected_at: str | None = None,
    received_at: str | None = None,
) -> dict[str, Any]:
    existing = incoming or {}
    canonical = _normalized_repo(repo)
    chain = [str(item) for item in existing.get("original_source_chain", []) if str(item)]
    previous = str(existing.get("canonical_source_repo", "") or "").strip()
    if previous and previous not in chain:
        chain.append(previous)
    if canonical not in chain:
        chain.append(canonical)
    visibility = (
        _policy_visibility(policy)
        if policy
        else str(existing.get("source_visibility", "unknown") or "unknown")
    )
    if visibility not in VISIBILITIES:
        visibility = "unknown"
    return {
        "canonical_source_repo": canonical,
        "source_repo_id": str(getattr(policy, "id", "") if policy else ""),
        "source_repo_alias": str(getattr(policy, "alias", "") if policy else Path(canonical).name),
        "source_visibility": visibility,
        "original_source_chain": chain,
        "return_address": str(existing.get("return_address") or f"{canonical}/.digital-asset/mail/inbox.jsonl"),
        "original_mail_id": str(existing.get("original_mail_id") or ""),
        "composed_by": str(existing.get("composed_by") or composed_by),
        "collected_by": str(existing.get("collected_by") or collected_by),
        "collected_at": str(existing.get("collected_at") or collected_at or ""),
        "received_at": str(existing.get("received_at") or received_at or ""),
    }


def _public_release_envelope(
    *,
    source_visibility: str,
    target_policy: Any | None,
    existing: dict[str, Any] | None = None,
    release_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_visibility = _policy_visibility(target_policy)
    target_public = _policy_public_facing(target_policy)
    required = target_public and source_visibility in NON_PUBLIC_VISIBILITIES
    status = "pending_human" if required else "not_required"
    human_release_id = ""
    release_reason = (
        "non_public_source_to_public_target"
        if required
        else "public_release_not_required"
    )
    if release_decision:
        if release_decision.get("decision") == "approve":
            status = "approved"
        elif release_decision.get("decision") == "reject":
            status = "rejected"
        human_release_id = str(release_decision.get("release_id", ""))
        release_reason = str(release_decision.get("notes") or release_reason)
    return {
        "target_visibility": target_visibility,
        "target_public_facing": target_public,
        "public_release_required": required,
        "public_release_status": status,
        "human_release_id": human_release_id,
        "release_reason": release_reason,
    }


def _public_payload_violations(record: MailMessageRecord, target_policy: Any | None) -> list[str]:
    if not _policy_public_facing(target_policy):
        return []
    violations: list[str] = []
    unknown_keys = sorted(set(record.payload) - PUBLIC_SAFE_PAYLOAD_KEYS)
    if unknown_keys:
        violations.append("payload_keys_not_public_safe:" + ",".join(unknown_keys))
    values_to_check: list[tuple[str, Any]] = [
        *(("payload." + key, value) for key, value in record.payload.items()),
        *(("evidence", value) for value in record.evidence),
        *(("suggested_actions", value) for value in record.suggested_actions),
    ]
    for key, value in values_to_check:
        strings: list[str]
        if isinstance(value, str):
            strings = [value]
        elif isinstance(value, list):
            strings = [str(item) for item in value]
        else:
            strings = [str(value)]
        for text in strings:
            if len(text) > MAX_PUBLIC_PAYLOAD_STRING:
                violations.append(f"payload_value_too_long:{key}")
            if "\t" in text or text.count(",") >= 4 or text.count("\n") >= 4:
                violations.append(f"payload_looks_like_table_or_blob:{key}")
    if int(record.payload.get("redaction_count", 0) or 0) > 0:
        violations.append("screening_redactions_present")
    return sorted(set(violations))


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
    source_provenance: dict[str, Any] | None = None,
    public_release: dict[str, Any] | None = None,
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
            "redaction_note": "Best-effort credential/PII screening changed this packet before mail persistence.",
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
        source_provenance=source_provenance
        or _source_provenance(source, received_at=created_at or utc_now()),
        public_release=public_release
        or _public_release_envelope(source_visibility="unknown", target_policy=None),
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
    repo_policies: Sequence[Any] | None = None,
    composed_by: str = "unknown",
) -> dict[str, Any]:
    policy = _policy_for_repo(repo, repo_policies)
    _raise_if_write_protected(repo, policy, operation="compose")
    mail_dir = ensure_repo_mailbox(repo)
    created = created_at or utc_now()
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
        created_at=created,
        source_provenance=_source_provenance(
            repo,
            policy=policy,
            composed_by=composed_by,
            received_at=created,
        ),
        public_release=_public_release_envelope(
            source_visibility=_policy_visibility(policy),
            target_policy=_policy_for_repo(target_repo, repo_policies),
        ),
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


def _canonical_collected_record(
    repo: Path, payload: dict[str, Any], repo_policies: Sequence[Any] | None = None
) -> MailMessageRecord:
    incoming = MailMessageRecord(**payload)
    source_policy = _policy_for_repo(repo, repo_policies)
    target_policy = _policy_for_repo(incoming.target_repo, repo_policies)
    collected = utc_now()
    incoming_provenance = dict(incoming.source_provenance)
    if not incoming_provenance.get("original_mail_id"):
        incoming_provenance["original_mail_id"] = incoming.mail_id
    if source_policy is None:
        incoming_provenance["source_visibility"] = "unknown"
        incoming_provenance["source_repo_id"] = ""
        incoming_provenance["source_repo_alias"] = repo.name
    source_provenance = _source_provenance(
        repo,
        policy=source_policy,
        incoming=incoming_provenance,
        composed_by=str(incoming_provenance.get("composed_by", "unknown")),
        collected_at=collected,
        received_at=collected,
    )
    release = _public_release_envelope(
        source_visibility=str(source_provenance["source_visibility"]),
        target_policy=target_policy,
        existing=incoming.public_release,
    )
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
        source_provenance=source_provenance,
        public_release=release,
    )


def collect_mail(
    hub_root: Path, repos: list[Path], repo_policies: Sequence[Any] | None = None
) -> dict[str, Any]:
    collected = 0
    duplicates = 0
    errors: list[dict[str, str]] = []
    for repo in repos:
        try:
            outbox = _mail_file(repo, "outbox.jsonl")
            payloads, parse_errors = _read_jsonl_with_errors(outbox)
            _quarantine_jsonl_errors(hub_root, parse_errors)
            errors.extend({"repo": str(repo), **error} for error in parse_errors)
        except ValueError as exc:
            errors.append({"repo": str(repo), "error": f"Invalid JSONL outbox: {exc}"})
            continue
        for payload in payloads:
            try:
                record = _canonical_collected_record(repo, payload, repo_policies)
            except (ValidationError, ValueError) as exc:
                errors.append({"repo": str(repo), "error": str(exc)})
                continue
            try:
                if _append_unique(central_inbox_path(hub_root, repo), record):
                    collected += 1
                else:
                    duplicates += 1
            except TimeoutError as exc:
                errors.append({"repo": str(repo), "mail_id": record.mail_id, "error": str(exc)})
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
        payloads, parse_errors = _read_jsonl_with_errors(path)
        _quarantine_jsonl_errors(hub_root, parse_errors)
        errors.extend({"path": str(path), "error": str(error["error"])} for error in parse_errors)
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


def _release_decisions(hub_root: Path) -> dict[str, dict[str, Any]]:
    releases = hub_root / CENTRAL_MAIL_DIR / "releases" / "mail_releases.jsonl"
    rows, errors = _read_jsonl_with_errors(releases)
    _quarantine_jsonl_errors(hub_root, errors)
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        mail_id = str(row.get("mail_id", ""))
        if mail_id:
            latest[mail_id] = row
    return latest


def _release_record_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "releases" / "mail_releases.jsonl"


def _quarantine_public_hold(
    hub_root: Path,
    record: MailMessageRecord,
    *,
    reason: str,
    violations: list[str] | None = None,
) -> None:
    append_jsonl(
        hub_root / CENTRAL_MAIL_DIR / "quarantine" / "public_release_holds.jsonl",
        {
            "event_type": "public_release_hold",
            "created_at": utc_now(),
            "mail_id": record.mail_id,
            "source_provenance": record.source_provenance,
            "public_release": record.public_release,
            "reason": reason,
            "violations": violations or [],
        },
    )


def _record_with_policy(
    record: MailMessageRecord,
    repo_policies: Sequence[Any] | None,
    *,
    release_decision: dict[str, Any] | None = None,
) -> MailMessageRecord:
    target_policy = _policy_for_repo(record.target_repo, repo_policies)
    source_visibility = str(record.source_provenance.get("source_visibility", "unknown"))
    if source_visibility not in VISIBILITIES:
        source_visibility = "unknown"
    release = _public_release_envelope(
        source_visibility=source_visibility,
        target_policy=target_policy,
        existing=record.public_release,
        release_decision=release_decision,
    )
    return record.model_copy(update={"public_release": release})


def route_mail(
    hub_root: Path,
    *,
    default_target_repo: str = "central_only",
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    routed = 0
    duplicates = 0
    outbox = hub_root / CENTRAL_MAIL_DIR / "outbox" / "routed.jsonl"
    records, errors = _all_central_messages_with_errors(hub_root, "inbox")
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
                source_provenance=record.source_provenance,
                public_release=record.public_release,
            )
        else:
            routed_record = record.model_copy(update={"review_status": "routed_candidate"})
        routed_record = _record_with_policy(routed_record, repo_policies)
        try:
            if _append_unique(outbox, routed_record):
                routed += 1
            else:
                duplicates += 1
        except TimeoutError as exc:
            errors.append({"path": str(outbox), "error": str(exc)})
    report = write_mail_center_report(hub_root)
    return {
        "routed_count": routed,
        "duplicate_count": duplicates,
        "error_count": len(errors),
        "errors": errors,
        "blocked": False,
        "outbox": str(outbox),
        "report": report,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _delivery_logged(hub_root: Path, repo: Path, record: MailMessageRecord) -> bool:
    log_path = hub_root / CENTRAL_MAIL_DIR / "archive" / "delivery_log.jsonl"
    rows, errors = _read_jsonl_with_errors(log_path)
    _quarantine_jsonl_errors(hub_root, errors)
    target = _normalized_repo(repo)
    for row in rows:
        if row.get("event_type") != "delivered":
            continue
        if str(row.get("mail_id")) == record.mail_id and _normalized_repo(
            str(row.get("target_repo", ""))
        ) == target:
            return True
    return False


def _mail_exists(repo: Path, record: MailMessageRecord, hub_root: Path | None = None) -> bool:
    identity = _dedupe_identity(record.model_dump(mode="json"))
    inbox_path = _mail_file(repo, "inbox.jsonl")
    if identity in {_dedupe_identity(item) for item in _read_jsonl(inbox_path)}:
        return True
    for item in _read_jsonl(_mail_file(repo, "archive.jsonl")):
        if identity == _dedupe_identity(item):
            return True
    if hub_root and _delivery_logged(hub_root, repo, record):
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


def _source_asset_refs(record: MailMessageRecord) -> list[str]:
    refs: list[str] = []
    payload = record.payload
    for key in ("asset_id", "source_ref", "hash", "sha256", "path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())
    for key in ("asset_ids", "paths"):
        value = payload.get(key)
        if isinstance(value, list):
            refs.extend(str(item).strip() for item in value if str(item).strip())
    refs.extend(str(item).strip() for item in record.evidence if str(item).strip())
    if record.source_provenance.get("return_address"):
        refs.append(str(record.source_provenance["return_address"]))
    seen: set[str] = set()
    output: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            output.append(ref)
    return output


def _triage_to_review_decision(intake_decision: str) -> str:
    return {
        "implement_now": "accept",
        "save_for_future": "defer",
        "defer": "defer",
        "reject": "reject",
        "archive": "archive",
    }[intake_decision]


def _triage_status(intake_decision: str) -> str:
    return {
        "implement_now": "planned",
        "save_for_future": "watching",
        "defer": "deferred",
        "reject": "rejected",
        "archive": "archived",
    }[intake_decision]


def deliver_mail(
    hub_root: Path,
    repos: list[Path],
    repo_policies: Sequence[Any] | None = None,
    *,
    require_target_policy: bool = False,
) -> dict[str, Any]:
    repo_by_normalized, key_collisions = _delivery_key_map(repos, repo_policies)
    delivered = 0
    acknowledged_duplicates = 0
    central_only = 0
    held_for_release = 0
    rejected_release = 0
    skipped: list[dict[str, str]] = []
    delivery_log = hub_root / CENTRAL_MAIL_DIR / "archive" / "delivery_log.jsonl"
    records, errors = _all_central_messages_with_errors(hub_root, "outbox")
    release_decisions = _release_decisions(hub_root)
    for record in records:
        target_key = _normalized_repo(record.target_repo, preserve_named_target=True)
        if target_key in CENTRAL_ONLY_TARGETS:
            central_only += 1
            continue
        if target_key in key_collisions:
            skipped.append(
                {
                    "mail_id": record.mail_id,
                    "reason": "target repo key is ambiguous",
                    "target_key": target_key,
                }
            )
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
        target_policy = _policy_for_repo(target_repo, repo_policies)
        if require_target_policy and target_policy is None:
            skipped.append(
                {
                    "mail_id": record.mail_id,
                    "reason": "target repo lacks reviewed mail policy",
                    "target_repo": str(target_repo),
                }
            )
            continue
        release_decision = release_decisions.get(record.mail_id)
        policy_record = _record_with_policy(
            record, repo_policies, release_decision=release_decision
        )
        if _policy_write_protected(target_policy):
            append_jsonl(
                delivery_log,
                {
                    "event_type": "central_only",
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "reason": _write_protection_reason(target_policy),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": policy_record.public_release,
                },
            )
            skipped.append(
                {
                    "mail_id": record.mail_id,
                    "reason": "target repo mailbox is write-protected",
                    "target_repo": str(target_repo),
                }
            )
            central_only += 1
            continue
        public_violations = _public_payload_violations(policy_record, target_policy)
        release = policy_record.public_release
        if public_violations:
            _quarantine_public_hold(
                hub_root,
                policy_record,
                reason="public_safe_payload_violation",
                violations=public_violations,
            )
            skipped.append(
                {
                    "mail_id": record.mail_id,
                    "reason": "public-safe payload violations",
                    "violations": ",".join(public_violations),
                }
            )
            held_for_release += 1
            continue
        if release.get("public_release_status") == "rejected":
            append_jsonl(
                delivery_log,
                {
                    "event_type": "public_release_rejected",
                    "created_at": utc_now(),
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
            )
            rejected_release += 1
            continue
        if release.get("public_release_required") and release.get("public_release_status") != "approved":
            _quarantine_public_hold(
                hub_root,
                policy_record,
                reason="human_release_required",
            )
            append_jsonl(
                delivery_log,
                {
                    "event_type": "held_for_public_release",
                    "created_at": utc_now(),
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
            )
            held_for_release += 1
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
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
            )
            central_only += 1
            continue
        if _mail_exists(target_repo, policy_record, hub_root):
            ack = _ack_record(target_repo, policy_record)
            try:
                _append_unique(_mail_file(target_repo, "archive.jsonl"), ack)
            except TimeoutError as exc:
                errors.append({"mail_id": record.mail_id, "error": str(exc)})
                continue
            append_jsonl(
                delivery_log,
                {
                    "event_type": "duplicate_ack",
                    "created_at": utc_now(),
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
            )
            acknowledged_duplicates += 1
            continue
        delivered_record = policy_record.model_copy(update={"review_status": "delivered_candidate"})
        try:
            _append_unique(_mail_file(target_repo, "inbox.jsonl"), delivered_record)
        except TimeoutError as exc:
            errors.append({"mail_id": record.mail_id, "error": str(exc)})
            continue
        append_jsonl(
            delivery_log,
            {
                "event_type": "delivered",
                "created_at": utc_now(),
                "mail_id": record.mail_id,
                "target_repo": str(target_repo),
                "source_provenance": delivered_record.source_provenance,
                "public_release": release,
            },
        )
        delivered += 1
    report = write_mail_center_report(hub_root)
    return {
        "delivered_count": delivered,
        "acknowledged_duplicate_count": acknowledged_duplicates,
        "central_only_count": central_only,
        "held_for_release_count": held_for_release,
        "rejected_release_count": rejected_release,
        "skipped": skipped,
        "error_count": len(errors),
        "errors": errors,
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
    human_verified: bool = False,
    notes: str = "",
    decided_at: str | None = None,
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    _raise_if_write_protected(
        repo,
        _policy_for_repo(repo, repo_policies),
        operation="review",
    )
    ensure_repo_mailbox(repo)
    matching = [
        item
        for item in _read_jsonl(_mail_file(repo, "inbox.jsonl"))
        if str(item.get("mail_id")) == mail_id
    ]
    if not matching:
        raise ValueError(f"No inbox mail found for {mail_id}.")
    record = MailDecisionRecord(
        decision_id=stable_id(
            "mail-decision",
            str(repo),
            mail_id,
            decision,
            "human" if human_verified else "agent",
        ),
        mail_id=mail_id,
        repository=_normalized_repo(repo),
        decision=decision,  # type: ignore[arg-type]
        decided_at=decided_at or utc_now(),
        decided_by=decided_by,
        decision_actor_type="human" if human_verified else "agent",
        human_verified=human_verified,
        notes=notes,
        review_status="human_reviewed" if human_verified else "agent_triage",
    )
    archive_path = _mail_file(repo, "archive.jsonl")
    appended = _append_unique_decision(archive_path, record)
    return {
        "decision": record.model_dump(mode="json"),
        "appended": appended,
        "archive": str(archive_path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def triage_mail(
    repo: Path,
    *,
    mail_id: str,
    intake_decision: str,
    importance: str = "unknown",
    planned_use: str = "",
    implementation_plan: list[str] | None = None,
    recorded_by: str = "unknown",
    human_verified: bool = False,
    notes: str = "",
    recorded_at: str | None = None,
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    normalized_decision = intake_decision.replace("-", "_").lower()
    if normalized_decision not in {
        "implement_now",
        "save_for_future",
        "defer",
        "reject",
        "archive",
    }:
        raise ValueError(
            "intake_decision must be implement_now, save_for_future, defer, reject, or archive"
        )
    normalized_importance = importance.replace("-", "_").lower()
    if normalized_importance not in {"now", "future", "not_relevant", "unknown"}:
        raise ValueError("importance must be now, future, not_relevant, or unknown")
    _raise_if_write_protected(
        repo,
        _policy_for_repo(repo, repo_policies),
        operation="triage",
    )
    ensure_repo_mailbox(repo)
    matching = [
        item
        for item in _read_jsonl(_mail_file(repo, "inbox.jsonl"))
        if str(item.get("mail_id")) == mail_id
    ]
    if not matching:
        raise ValueError(f"No inbox mail found for {mail_id}.")
    mail_record = MailMessageRecord(**matching[0])
    timestamp = recorded_at or utc_now()
    review_decision = MailDecisionRecord(
        decision_id=stable_id(
            "mail-decision",
            str(repo),
            mail_id,
            _triage_to_review_decision(normalized_decision),
            "human" if human_verified else "agent",
        ),
        mail_id=mail_id,
        repository=_normalized_repo(repo),
        decision=_triage_to_review_decision(normalized_decision),  # type: ignore[arg-type]
        decided_at=timestamp,
        decided_by=recorded_by,
        decision_actor_type="human" if human_verified else "agent",
        human_verified=human_verified,
        notes=notes,
        review_status="human_reviewed" if human_verified else "agent_triage",
    )
    archive_path = _mail_file(repo, "archive.jsonl")
    decision_appended = _append_unique_decision(archive_path, review_decision)
    adoption = MailAdoptionRecord(
        adoption_id=stable_id(
            "mail-adoption",
            str(repo),
            mail_id,
            normalized_decision,
            planned_use,
        ),
        mail_id=mail_id,
        repository=_normalized_repo(repo),
        intake_decision=normalized_decision,  # type: ignore[arg-type]
        importance=normalized_importance,  # type: ignore[arg-type]
        recorded_at=timestamp,
        recorded_by=recorded_by,
        human_verified=human_verified,
        planned_use=planned_use,
        implementation_plan=implementation_plan or [],
        implementation_status=_triage_status(normalized_decision),  # type: ignore[arg-type]
        source_asset_refs=_source_asset_refs(mail_record),
        source_repo=mail_record.source_repo,
        source_provenance=mail_record.source_provenance,
        update_tracking={
            "watch_source": normalized_decision in {"implement_now", "save_for_future", "defer"},
            "update_channel": "dad_mail",
            "original_mail_id": mail_record.source_provenance.get("original_mail_id")
            or mail_record.mail_id,
            "dedupe_key": mail_record.dedupe_key,
            "return_address": mail_record.source_provenance.get("return_address", ""),
            "upgrade_policy": "notify_via_dad_mail_before_local_change",
        },
        notes=notes,
        review_status="human_reviewed" if human_verified else "agent_triage",
    )
    adoption_path = _mail_file(repo, "adoption.jsonl")
    adoption_appended = _append_unique_adoption(adoption_path, adoption)
    return {
        "decision": review_decision.model_dump(mode="json"),
        "adoption": adoption.model_dump(mode="json"),
        "decision_appended": decision_appended,
        "adoption_appended": adoption_appended,
        "archive": str(archive_path),
        "adoption_path": str(adoption_path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def release_mail(
    hub_root: Path,
    *,
    mail_id: str,
    decision: str,
    human_reviewed_by: str,
    notes: str = "",
    decided_at: str | None = None,
) -> dict[str, Any]:
    normalized_decision = decision.lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("release decision must be approve or reject")
    if not human_reviewed_by.strip():
        raise ValueError("human_reviewed_by is required for mail release")
    records = [
        record
        for record in [
            *_all_central_messages(hub_root, "inbox"),
            *_all_central_messages(hub_root, "outbox"),
        ]
        if record.mail_id == mail_id or record.source_provenance.get("original_mail_id") == mail_id
    ]
    if not records:
        raise ValueError(f"No central mail found for {mail_id}.")
    decided = decided_at or utc_now()
    release_id = stable_id("mail-release", mail_id, normalized_decision, decided)
    record = {
        "schema_version": "0.1.0",
        "release_id": release_id,
        "mail_id": records[0].mail_id,
        "requested_mail_id": mail_id,
        "decision": normalized_decision,
        "human_reviewed_by": human_reviewed_by,
        "decided_at": decided,
        "notes": notes,
        "source_provenance": records[0].source_provenance,
        "public_release": records[0].public_release,
        "authority_boundary": "Human release gates private/internal/unknown-origin mail before public-facing delivery.",
    }
    append_jsonl(_release_record_path(hub_root), record)
    return {
        "release": record,
        "release_log": str(_release_record_path(hub_root)),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def digest_mail(
    repo: Path,
    *,
    checked_at: str | None = None,
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    _raise_if_write_protected(
        repo,
        _policy_for_repo(repo, repo_policies),
        operation="digest",
    )
    ensure_repo_mailbox(repo)
    inbox, inbox_errors = _read_jsonl_with_errors(_mail_file(repo, "inbox.jsonl"))
    archive, archive_errors = _read_jsonl_with_errors(_mail_file(repo, "archive.jsonl"))
    reviewed_ids: set[str] = set()
    agent_triage_ids: set[str] = set()
    for item in archive:
        try:
            decision = MailDecisionRecord(**item)
        except ValidationError:
            continue
        if decision.human_verified and decision.review_status == "human_reviewed":
            reviewed_ids.add(decision.mail_id)
        else:
            agent_triage_ids.add(decision.mail_id)
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
        "agent_triage_count": len(agent_triage_ids),
        "parse_warning_count": len(inbox_errors) + len(archive_errors),
        "parse_warnings": [*inbox_errors, *archive_errors],
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
    quarantine_dir = hub_root / CENTRAL_MAIL_DIR / "quarantine"
    release_rows, _ = _read_jsonl_with_errors(_release_record_path(hub_root))
    archive_count = (
        sum(len(_read_jsonl(path)) for path in archive_dir.glob("*.jsonl"))
        if archive_dir.exists()
        else 0
    )
    quarantine_count = (
        sum(len(_read_jsonl(path)) for path in quarantine_dir.glob("*.jsonl"))
        if quarantine_dir.exists()
        else 0
    )
    all_messages = [*inbox, *outbox]
    private_origin_count = sum(
        1
        for record in all_messages
        if record.source_provenance.get("source_visibility") in NON_PUBLIC_VISIBILITIES
    )
    release_required_count = sum(
        1
        for record in all_messages
        if record.public_release.get("public_release_required") is True
    )
    summary = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inbox_count": len(inbox),
        "outbox_count": len(outbox),
        "archive_count": archive_count,
        "quarantine_count": quarantine_count,
        "private_origin_count": private_origin_count,
        "public_release_required_count": release_required_count,
        "release_decision_count": len(release_rows),
        "message_type_counts": {},
    }
    counts: dict[str, int] = {}
    for record in all_messages:
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
        f"- Quarantine events: **{summary['quarantine_count']}**",
        f"- Non-public-origin messages: **{summary['private_origin_count']}**",
        f"- Public-release-required messages: **{summary['public_release_required_count']}**",
        f"- Release decisions: **{summary['release_decision_count']}**",
        "",
        "## Message Types",
        "",
    ]
    for message_type, count in summary["message_type_counts"].items():
        lines.append(f"- `{message_type}`: **{count}**")
    atomic_write_text(report_md, "\n".join(lines) + "\n")
    return {"report_markdown": str(report_md), "report_json": str(report_json)}
