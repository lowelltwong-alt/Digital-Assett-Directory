from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import os
import re
import subprocess
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
LEGACY_OUTBOX_MESSAGE_TYPES = {
    "fork_experiment_announcement": "workflow_suggestion",
    "lesson_and_asset_candidate": "lesson_suggestion",
    "review_request": "governance_notice",
}
LEGACY_PAYLOAD_KEYS = (
    "summary",
    "subject",
    "status",
    "task_id",
    "fork_id",
    "parent_message_id",
    "context_map_entry",
    "lesson_learned_slot",
    "asset_candidates",
    "method_steps",
    "purpose",
    "known_limits",
    "non_authorizations",
    "follow_up_messages_expected",
    "requested_output_path",
)
MAIL_FILE_NAMES = {
    "inbox.jsonl",
    "outbox.jsonl",
    "archive.jsonl",
    "adoption.jsonl",
    "README.md",
    "last_checked.json",
    ".gitignore",
}
LIVE_MAIL_JSONL_NAMES = {"inbox.jsonl", "outbox.jsonl", "archive.jsonl", "adoption.jsonl"}
MAX_MAIL_RECORD_BYTES = 64_000
MAX_PUBLIC_PAYLOAD_STRING = 500
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 300.0
COLLECTION_AUDIT_ENFORCED_AT = "2026-07-05T00:00:00+00:00"
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
LOCAL_PATH_FRAGMENTS = (
    "c:/users/",
    "c__users__",
    "/users/",
    "appdata/",
    "git projects/",
    "onedrive/",
)
AUTHORITY_BOUNDARY = (
    "DAD mail is append-only candidate evidence. It may suggest lessons, assets, "
    "workflows, taxonomy, capabilities, or governance notices, but it does not "
    "override target repo authority or mutate source files outside .digital-asset/mail/."
)
_ACTIVE_JSONL_LOCKS: set[Path] = set()


class MailOutboxUnstableError(ValueError):
    """Raised when a repo outbox changes while DAD is trying to collect it."""


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
            aliases.add(f"repo:{value}")
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


def _path_hash_ref(value: str) -> str:
    normalized = str(value).replace("\\", "/").strip()
    return f"path-sha256:{sha256_bytes(normalized.encode('utf-8'))}"


def _looks_local_path_like(value: str) -> bool:
    text = str(value).strip()
    if not text or text.startswith(("dad://", "repo:", "repo-path-sha256:", "path-sha256:")):
        return False
    normalized = text.replace("\\", "/").casefold()
    return (
        bool(re.match(r"^[A-Za-z]:[\\/]", text))
        or text.startswith(("/", "\\"))
        or any(fragment in normalized for fragment in LOCAL_PATH_FRAGMENTS)
    )


def _safe_repo_ref(value: str | Path, policies: Sequence[Any] | None = None) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if text in CENTRAL_ONLY_TARGETS or text.startswith("dad://"):
        return text
    policy = _policy_for_repo(text, policies)
    if policy is not None:
        return f"repo:{getattr(policy, 'id', 'unknown')}"
    normalized = text.replace("\\", "/")
    for suffix in (
        "/.digital-asset/mail/outbox.jsonl",
        "/.digital-asset/mail/inbox.jsonl",
        "/.digital-asset/mail/archive.jsonl",
    ):
        if normalized.endswith(suffix):
            repo_part = normalized[: -len(suffix)]
            return f"{_safe_repo_ref(repo_part, policies)}:{suffix.removeprefix('/')}"
    if _looks_local_path_like(text):
        return f"repo-path-sha256:{sha256_bytes(normalized.encode('utf-8'))}"
    return text


def _sanitize_central_review_value(value: Any, policies: Sequence[Any] | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_central_review_value(item, policies) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_central_review_value(item, policies) for item in value]
    if isinstance(value, str):
        return _safe_repo_ref(value, policies) if _looks_local_path_like(value) else value
    return value


def sanitize_central_review_record(
    payload: dict[str, Any], policies: Sequence[Any] | None = None
) -> dict[str, Any]:
    sanitized = dict(payload)
    for key in ("source_repo", "target_repo"):
        if key in sanitized:
            sanitized[key] = _safe_repo_ref(str(sanitized[key]), policies)
    for key in ("payload", "evidence", "suggested_actions"):
        if key in sanitized:
            sanitized[key] = _sanitize_central_review_value(sanitized[key], policies)
    if isinstance(sanitized.get("source_provenance"), dict):
        sanitized["source_provenance"] = _sanitize_central_review_value(
            sanitized["source_provenance"],
            policies,
        )
    return sanitized


def _sanitize_mail_record_for_storage(
    record: MailMessageRecord,
    policies: Sequence[Any] | None = None,
) -> MailMessageRecord:
    payload = sanitize_central_review_record(record.model_dump(mode="json"), policies)
    return MailMessageRecord(**payload)


def _central_repo_file_slug(repo: Path, policies: Sequence[Any] | None = None) -> str:
    ref = _safe_repo_ref(repo, policies)
    if ref.startswith("repo:"):
        slug = ref.removeprefix("repo:")
    elif ref.startswith("repo-path-sha256:"):
        slug = "repo-path-" + ref.removeprefix("repo-path-sha256:")[:24]
    else:
        slug = "repo-key-" + sha256_bytes(ref.encode("utf-8"))[:24]
    return re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-") or "repo"


def _delivery_key_map(
    repos: list[Path], policies: Sequence[Any] | None
) -> tuple[dict[str, Path], dict[str, list[str]]]:
    repo_by_key: dict[str, Path] = {}
    collisions: dict[str, list[str]] = {}
    candidate_keys: dict[str, list[Path]] = {}
    for repo in repos:
        normalized = _normalized_repo(repo)
        candidate_keys.setdefault(normalized, []).append(repo)
        candidate_keys.setdefault(_safe_repo_ref(repo, policies), []).append(repo)
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
        atomic_write_text(readme, mail_readme_text(), allow_direct_fallback=True)
    gitignore = _mail_file(repo, MAIL_GITIGNORE_NAME)
    if not gitignore.exists():
        atomic_write_text(gitignore, mail_gitignore_text(), allow_direct_fallback=True)
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

If `asset-dir` is not available on `PATH`, first try the stable DAD user shim:

```text
& "$HOME\\.dad\\bin\\asset-dir.ps1" mail digest --repo .
$HOME/.dad/bin/asset-dir mail digest --repo .
```

If the shim is unavailable too, run the same command from the DAD source
checkout with `PYTHONPATH=src`:

```text
python -m digital_asset_directory.cli mail digest --repo .
```

If neither command is available, append pointer-safe JSONL to this repo's
`outbox.jsonl` and note `dad_cli_unavailable` plus the attempted command in the
payload. DAD should collect it later as candidate mail and may record a
`validation_command_missing` exception. Do not include raw logs, secrets,
private rows, hidden reasoning, or copied source blobs in that fallback packet.

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

Before composing outbox mail, check what this repo already sent so a reworded
near-duplicate is not sent again. If the new message is a true upgrade of an
earlier one (new evidence, new findings), send it with `--supersedes <mail-id>`
so it joins the original thread instead of duplicating it:

```text
asset-dir mail outbox-check --repo . --summary "<proposed summary>"
asset-dir mail compose --repo . --type asset_suggestion --summary "<upgrade>" --supersedes <mail-id>
```

During concurrent work, multiple agents may retry the same outbox candidate.
That is acceptable as a source-outbox storm signal: DAD collection canonicalizes
one row and records duplicate audit evidence. Do not write directly to DAD's
`processed/mail/inbox/*.jsonl` or any repo's `.digital-asset/mail/inbox.jsonl`;
DAD collection and delivery own those files.

If DAD or a repo looks "very dirty" during Rust rollout or cross-repo learning
work, use the DAD runbook at
`dad://hub/docs/DAD_MAIL_STORM_AND_DIRTY_STATE_RUNBOOK.md`. The key distinction
is that dirty git worktree state is not automatically mailbox corruption; DAD
mail decisions use `asset-dir mail storm-gate` for the first go/no-go answer
and `asset-dir mail doctor --repo all --summary-only --fail-on-dirty --fail-on-coverage-gap`
for full diagnostics.

Only `inbox.jsonl`, `outbox.jsonl`, `archive.jsonl`, and `adoption.jsonl` are
live mailbox streams. Keep backup, damaged, or repair files outside this
directory, or rename them without a `.jsonl` suffix, so they do not look like
mail streams during DAD storm diagnostics.

Send red-team, premortem, audit, security-review, and code-review findings from
any agent (Fable, Opus, Codex, Claude, Cursor, human) back to DAD as structured
lessons so repeated failure patterns can be mined:

```text
asset-dir lesson review-feedback --repo . --agent <agent> --review-type red_team --finding "<summary>"
```

Do not commit mailbox JSONL to a public-facing repo unless a human explicitly
reviews the packet provenance and public-release status.
"""


def _parse_jsonl_bytes(path: Path, content: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records, _ = _read_jsonl_with_errors(path)
    return records


def _read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        return [], []
    return _parse_jsonl_bytes(path, path.read_bytes())


def _jsonl_file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_size, stat.st_mtime_ns


def _read_stable_jsonl_with_errors(
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records, errors, _signature = _read_stable_jsonl_snapshot(path)
    return records, errors


def _read_stable_jsonl_snapshot(
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[int, int] | None]:
    """Read a JSONL file only when its bytes are stable across the read.

    Repo agents may append to their outboxes from different branches or tools. If
    the file moves while DAD is collecting, the safe behavior is to leave it for
    the next collection pass rather than promoting a partial snapshot.
    """

    before = _jsonl_file_signature(path)
    if before is None:
        return [], [], None
    try:
        first_read = path.read_bytes()
        after_first = _jsonl_file_signature(path)
        second_read = path.read_bytes()
        after_second = _jsonl_file_signature(path)
    except OSError as exc:
        raise MailOutboxUnstableError(
            "Source outbox became unavailable while it was being collected."
        ) from exc
    if before != after_first or after_first != after_second or first_read != second_read:
        raise MailOutboxUnstableError("Source outbox changed while it was being collected.")
    records, errors = _parse_jsonl_bytes(path, first_read)
    return records, errors, after_second


def _quarantine_jsonl_errors(hub_root: Path, errors: list[dict[str, Any]]) -> None:
    if not errors:
        return
    quarantine = hub_root / CENTRAL_MAIL_DIR / "quarantine" / "malformed_jsonl.jsonl"
    for error in errors:
        safe_error = dict(error)
        if safe_error.get("path"):
            safe_error["path"] = _relative_path_ref(hub_root, Path(str(safe_error["path"])))
        append_jsonl_locked(
            quarantine,
            {"event_type": "malformed_jsonl", "created_at": utc_now(), **safe_error},
        )


def _quarantine_invalid_mail_packet(
    hub_root: Path,
    *,
    source_path: Path,
    record: Any,
    reason: str,
    repo: Path | None = None,
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    record_hash = _invalid_mail_record_hash(record)
    record_obj = record if isinstance(record, dict) else {}
    payload = {
        "event_type": "invalid_mail_packet",
        "created_at": utc_now(),
        "path": _relative_path_ref(hub_root, source_path),
        "repo": _safe_repo_ref(str(repo), repo_policies) if repo is not None else "",
        "mail_id": str(record_obj.get("mail_id", "")),
        "dedupe_key": str(record_obj.get("dedupe_key", "")),
        "record_hash": record_hash,
        "reason": reason,
        "raw_payload_copied": False,
        "authority_boundary": (
            "Invalid mail packets are quarantined by metadata and hash only. "
            "Raw payload content is not copied into DAD quarantine records."
        ),
    }
    append_jsonl_locked(
        invalid_mail_quarantine_path(hub_root),
        sanitize_central_review_record(payload, repo_policies),
    )
    return payload


def invalid_mail_quarantine_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "quarantine" / "invalid_mail_packet.jsonl"


def _invalid_mail_record_hash(record: Any) -> str:
    return f"sha256:{sha256_bytes(json_dumps(record).encode('utf-8'))}"


def _dedupe_identity(record: dict[str, Any]) -> str:
    return f"{record.get('mail_id', '')}|{record.get('dedupe_key', '')}"


def _jsonl_lock_owner_pid(lock_path: Path) -> int | None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _jsonl_lock_pid_is_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            still_active = 259
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information,
                False,
                pid,
            )
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                ok = ctypes.windll.kernel32.GetExitCodeProcess(
                    handle,
                    ctypes.byref(exit_code),
                )
                return bool(ok) and exit_code.value == still_active
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _unlink_jsonl_lock(lock_path: Path) -> bool:
    for attempt in range(5):
        try:
            lock_path.unlink()
            if not lock_path.exists():
                return True
        except FileNotFoundError:
            return True
        except PermissionError:
            if attempt == 4:
                return False
            time.sleep(0.05 * (attempt + 1))
        except OSError:
            return False
        if attempt == 4:
            return False
        time.sleep(0.05 * (attempt + 1))
    return False


def _lock_diagnostic_allows_tombstone_takeover(diagnostic: dict[str, Any]) -> bool:
    status = str(diagnostic.get("status", ""))
    if status in {"dead_owner", "same_process_leftover"}:
        return True
    if status == "stale":
        owner_pid = diagnostic.get("owner_pid")
        return owner_pid in ("", None, 0) or diagnostic.get("owner_alive") is False
    return False


@contextmanager
def _jsonl_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    lock_key = lock_path.resolve()
    using_tombstone_takeover = False
    started = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json_dumps({"pid": os.getpid(), "created_at": utc_now()}))
            _ACTIVE_JSONL_LOCKS.add(lock_key)
            break
        except FileExistsError:
            lock_wait_exceeded = time.monotonic() - started > LOCK_TIMEOUT_SECONDS
            try:
                diagnostic = _lock_diagnostic(lock_path, stale_lock_seconds=STALE_LOCK_SECONDS)
                if _lock_diagnostic_allows_tombstone_takeover(diagnostic):
                    if _unlink_jsonl_lock(lock_path):
                        continue
                    using_tombstone_takeover = True
                    _ACTIVE_JSONL_LOCKS.add(lock_key)
                    break
            except OSError:
                pass
            if lock_wait_exceeded:
                raise TimeoutError(f"Timed out waiting for JSONL lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if not using_tombstone_takeover:
            _unlink_jsonl_lock(lock_path)
        _ACTIVE_JSONL_LOCKS.discard(lock_key)


def append_jsonl_locked(path: Path, payload: dict[str, Any]) -> None:
    with _jsonl_lock(path):
        append_jsonl(path, payload)


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


def _append_unique_central_decision(path: Path, payload: dict[str, Any]) -> bool:
    with _jsonl_lock(path):
        existing = {str(item.get("decision_id", "")) for item in _read_jsonl(path)}
        if str(payload.get("decision_id", "")) in existing:
            return False
        append_jsonl(path, payload)
        return True


def _append_central_audit_record(
    path: Path,
    payload: dict[str, Any],
    repo_policies: Sequence[Any] | None = None,
) -> None:
    append_jsonl_locked(path, sanitize_central_review_record(payload, repo_policies))


def _append_unique_by_key(path: Path, payload: dict[str, Any], key: str) -> bool:
    with _jsonl_lock(path):
        existing = {str(item.get(key, "")) for item in _read_jsonl(path)}
        if str(payload.get(key, "")) in existing:
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
            if _looks_local_path_like(text):
                violations.append(f"payload_contains_local_path_ref:{key}")
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


def _legacy_outbox_target(payload: dict[str, Any]) -> str:
    target = str(payload.get("target_repo") or payload.get("to_repo") or "").strip()
    if target:
        return target
    hub = str(payload.get("to_hub") or "").strip()
    if hub.startswith("dad://hub/"):
        return "dad"
    return "central_only"


def _legacy_outbox_evidence_ref(source_ref: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("repo:", "dad://", "path-sha256:", "repo-path-sha256:")):
        return text
    return f"{source_ref}:{text}"


def _legacy_outbox_record(
    repo: Path,
    payload: dict[str, Any],
    repo_policies: Sequence[Any] | None = None,
) -> MailMessageRecord | None:
    original_mail_id = str(payload.get("message_id") or "").strip()
    if not original_mail_id or "mail_id" in payload:
        return None
    raw_type = str(payload.get("message_type") or "").strip()
    message_type = LEGACY_OUTBOX_MESSAGE_TYPES.get(raw_type)
    if not message_type:
        raise ValueError(f"Unsupported fallback mail message_type: {raw_type or '<missing>'}")

    source_policy = _policy_for_repo(repo, repo_policies)
    source_ref = _safe_repo_ref(repo, repo_policies)
    summary = str(payload.get("summary") or payload.get("subject") or original_mail_id).strip()
    if not summary:
        raise ValueError(f"Fallback mail {original_mail_id} is missing a summary or subject.")

    converted_payload: dict[str, Any] = {
        "summary": summary,
        "original_message_type": raw_type,
        "legacy_fallback_mail": True,
    }
    for key in LEGACY_PAYLOAD_KEYS:
        if key in payload and payload[key] not in ("", None, [], {}):
            converted_payload[key] = payload[key]

    evidence = [
        f"{source_ref}:.digital-asset/mail/outbox.jsonl#{original_mail_id}",
    ]
    for key in ("artifacts",):
        values = payload.get(key) or []
        if isinstance(values, str):
            values = [values]
        for item in values:
            ref = _legacy_outbox_evidence_ref(source_ref, item)
            if ref:
                evidence.append(ref)
    for key in ("requested_output_path", "lesson_learned_slot", "context_map_entry"):
        ref = _legacy_outbox_evidence_ref(source_ref, payload.get(key))
        if ref:
            evidence.append(ref)

    suggested_actions = [
        "Review this fallback mail as candidate DAD evidence, not source authority.",
        "Convert useful parts into reviewed DAD lessons, assets, harnesses, or workflow guidance before reuse.",
    ]
    if payload.get("non_authorizations"):
        suggested_actions.append("Carry forward non-authorizations before any downstream adoption.")

    created_at = str(payload.get("timestamp") or payload.get("created_at") or utc_now())
    source_provenance = {
        "canonical_source_repo": source_ref,
        "source_repo_id": str(getattr(source_policy, "id", "") if source_policy else ""),
        "source_repo_alias": str(
            getattr(source_policy, "alias", "") if source_policy else Path(repo).name
        ),
        "source_visibility": _policy_visibility(source_policy),
        "original_source_chain": [
            item
            for item in (
                source_ref,
                str(payload.get("parent_message_id") or "").strip(),
                original_mail_id,
            )
            if item
        ],
        "return_address": f"{source_ref}:.digital-asset/mail/outbox.jsonl#{original_mail_id}",
        "original_mail_id": original_mail_id,
        "composed_by": str(payload.get("composed_by") or "legacy_outbox_fallback"),
        "collected_by": "dad",
        "collected_at": "",
        "received_at": created_at,
    }

    return _build_mail_record(
        message_type=message_type,
        source_repo=str(repo),
        target_repo=_legacy_outbox_target(payload),
        payload=converted_payload,
        evidence=evidence,
        suggested_actions=suggested_actions,
        sensitivity=str(payload.get("sensitivity") or "internal"),
        review_status="generated_candidate",
        created_at=created_at,
        dedupe_key=f"legacy:{original_mail_id}",
        source_provenance=source_provenance,
    )


OUTBOX_NOVELTY_BASIS = (
    "deterministic token Jaccard (|intersection|/|union|) between the proposed message's "
    "summary/payload-value/evidence tokens and each previously sent outbox message after "
    "stopword removal; thresholds: >=0.6 near_duplicate, >=0.3 related. Routing aid for "
    "send decisions, not a value score; content-level deltas still belong to "
    "semantic-evolution grading."
)
NEAR_DUPLICATE_THRESHOLD = 0.6
RELATED_THRESHOLD = 0.3


def _payload_value_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_payload_value_strings(item))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for item in value:
            strings.extend(_payload_value_strings(item))
        return strings
    if isinstance(value, (int, float, bool)) or value is None:
        return []
    return [str(value)]


def _message_tokens(
    *,
    message_type: str,
    summary: str,
    payload: dict[str, Any] | None,
    evidence: list[str] | None,
) -> set[str]:
    from .dad_library import PATTERN_MATCH_STOPWORDS, _tokenize

    return _tokenize(
        [
            message_type,
            summary,
            _payload_value_strings(payload or {}),
            list(evidence or []),
        ]
    ) - PATTERN_MATCH_STOPWORDS


def check_outbox_novelty(
    repo: Path,
    *,
    message_type: str = "",
    summary: str = "",
    payload: dict[str, Any] | None = None,
    evidence: list[str] | None = None,
    limit: int = 5,
    exclude_mail_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Compare a proposed message against this repo's previously sent outbox mail.

    Catches semantic near-duplicates that different wording (and therefore a different
    dedupe_key) would slip past exact dedupe, and surfaces the prior thread so a true
    upgrade can be sent as a supersede instead of a parallel message.
    """
    candidate_tokens = _message_tokens(
        message_type=message_type, summary=summary, payload=payload, evidence=evidence
    )
    matches: list[dict[str, Any]] = []
    sent_rows = _read_jsonl(_mail_file(repo, "outbox.jsonl"))
    for row in sent_rows:
        mail_id = str(row.get("mail_id", ""))
        if exclude_mail_ids and mail_id in exclude_mail_ids:
            continue
        sent_tokens = _message_tokens(
            message_type=str(row.get("message_type", "")),
            summary="",
            payload=row.get("payload") if isinstance(row.get("payload"), dict) else {},
            evidence=[str(item) for item in row.get("evidence", []) or []],
        )
        union = candidate_tokens | sent_tokens
        if not union:
            continue
        similarity = len(candidate_tokens & sent_tokens) / len(union)
        if similarity < RELATED_THRESHOLD:
            continue
        matches.append(
            {
                "mail_id": mail_id,
                "thread_id": str(row.get("thread_id", "")),
                "message_type": str(row.get("message_type", "")),
                "created_at": str(row.get("created_at", "")),
                "similarity": round(similarity, 3),
                "relation": (
                    "near_duplicate"
                    if similarity >= NEAR_DUPLICATE_THRESHOLD
                    else "related"
                ),
                "new_terms": sorted(candidate_tokens - sent_tokens)[:12],
            }
        )
    matches.sort(key=lambda item: (-item["similarity"], item["mail_id"]))
    if any(item["relation"] == "near_duplicate" for item in matches):
        verdict = "already_sent_similar"
    elif matches:
        verdict = "possible_upgrade"
    else:
        verdict = "new"
    return {
        "verdict": verdict,
        "check_basis": OUTBOX_NOVELTY_BASIS,
        "sent_count": len(sent_rows),
        "matches": matches[:limit],
        "guidance": (
            "already_sent_similar: do not re-send without new evidence; use supersedes "
            "for a true upgrade. possible_upgrade: send with supersedes=<mail_id> so the "
            "receiver sees the lineage in one thread. new: send normally."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


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
    supersedes: str = "",
    allow_similar: bool = False,
) -> dict[str, Any]:
    policy = _policy_for_repo(repo, repo_policies)
    _raise_if_write_protected(repo, policy, operation="compose")
    mail_dir = ensure_repo_mailbox(repo)
    created = created_at or utc_now()
    superseded_row: dict[str, Any] | None = None
    if supersedes:
        superseded_row = next(
            (
                row
                for row in _read_jsonl(_mail_file(repo, "outbox.jsonl"))
                if str(row.get("mail_id", "")) == supersedes
            ),
            None,
        )
        if superseded_row is None:
            raise ValueError(f"Cannot supersede unknown outbox mail: {supersedes}")
        if thread_id is None:
            thread_id = str(superseded_row.get("thread_id", "")) or None
    novelty = check_outbox_novelty(
        repo,
        message_type=message_type,
        summary=summary,
        payload=payload,
        evidence=evidence,
        exclude_mail_ids={supersedes} if supersedes else None,
    )
    if (
        novelty["verdict"] == "already_sent_similar"
        and not supersedes
        and not allow_similar
    ):
        top = novelty["matches"][0]
        raise ValueError(
            f"Near-duplicate of previously sent mail {top['mail_id']} "
            f"(similarity {top['similarity']}). Re-send with supersedes=<mail_id> if this "
            "is a true upgrade, or allow_similar=True to send anyway."
        )
    outgoing_payload = {"summary": summary, **(payload or {})}
    if supersedes:
        outgoing_payload["supersedes"] = supersedes
    record = _build_mail_record(
        message_type=message_type,
        source_repo=str(repo),
        target_repo=target_repo,
        payload=outgoing_payload,
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
        "novelty_check": {
            "verdict": novelty["verdict"],
            "matches": novelty["matches"][:3],
            "check_basis": novelty["check_basis"],
        },
        "supersedes": supersedes,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


ASSET_SUGGESTION_DELIVERY_MODEL = (
    "pointer_not_copy: this message carries the asset's library address, version, "
    "context, and graph evidence. Asset bodies are never mailed; fetch from the DAD "
    "library after local review."
)


def _asset_graph_context(hub_root: Path, asset_id: str) -> dict[str, Any]:
    graph_path = hub_root / "processed" / "learning" / "lesson-graph.json"
    if not graph_path.exists():
        return {"available": False, "reason": "lesson graph not built"}
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False, "reason": "lesson graph unreadable"}
    node_id = f"offering:{asset_id}"
    labels = {node["node_id"]: str(node.get("label", "")) for node in graph.get("nodes", [])}
    used_by: list[str] = []
    lesson_samples: list[str] = []
    lesson_count = 0
    for edge in graph.get("edges", []):
        if edge.get("target") != node_id:
            continue
        if edge.get("edge_type") == "uses_asset":
            used_by.append(labels.get(str(edge.get("source", "")), str(edge.get("source", ""))))
        elif edge.get("edge_type") == "about_asset":
            lesson_count += 1
            if len(lesson_samples) < 2:
                lesson_samples.append(
                    labels.get(str(edge.get("source", "")), str(edge.get("source", "")))[:120]
                )
    return {
        "available": True,
        "graph_generated_at": str(graph.get("generated_at", "")),
        "used_by_repos": sorted(used_by)[:3],
        "used_by_repo_count": len(used_by),
        "lesson_count": lesson_count,
        "lesson_samples": lesson_samples,
        "edge_rule": (
            "Graph evidence is generated candidate metadata from the DAD lesson graph, "
            "not proof of value."
        ),
    }


def compose_asset_suggestion(
    hub_root: Path,
    *,
    asset_id: str,
    target_repo: str,
    note: str = "",
    repo_policies: Sequence[Any] | None = None,
    composed_by: str = "dad_hub",
    supersedes: str = "",
    allow_similar: bool = False,
) -> dict[str, Any]:
    """Compose the standard repo-facing asset suggestion: pointer + context + graph edges.

    The message tells a repo what the asset does, where it lives in the library, its
    version and latest upgrade, when to use it, and what the lesson graph shows about
    who already uses it - never the asset body itself.
    """
    from .dad_library import load_offerings

    offering = next(
        (
            item
            for item in load_offerings(hub_root).get("offerings", [])
            if item.get("offering_id") == asset_id
        ),
        None,
    )
    if offering is None:
        raise ValueError(f"Unknown DAD offering: {asset_id}")
    known_upgrades = offering.get("known_upgrades") or []
    payload: dict[str, Any] = {
        "asset_id": asset_id,
        "asset_name": offering.get("name", ""),
        "version": str(offering.get("version", "")),
        "offering_type": str(offering.get("offering_type", "")),
        "library_path": str(offering.get("path", "")),
        "library_ref": f"dad://hub/Digital-Assett-Directory/{offering.get('path', '')}",
        "what_it_does": (offering.get("applies_when") or [""])[0],
        "capabilities": list(offering.get("capabilities", []))[:6],
        "use_when": list(offering.get("applies_when", []))[:3],
        "avoid_when": list(offering.get("does_not_apply_when", []))[:2],
        "latest_upgrade": (
            str(known_upgrades[-1].get("upgrade_id", "")) if known_upgrades else ""
        ),
        "graph_context": _asset_graph_context(hub_root, asset_id),
        "note": note,
        "delivery_model": ASSET_SUGGESTION_DELIVERY_MODEL,
        "next_step": (
            "Triage with asset-dir mail triage; if adopting, record usage with "
            "asset-dir usage record so upgrade notices stay targeted."
        ),
    }
    return compose_mail(
        hub_root,
        message_type="asset_suggestion",
        target_repo=target_repo,
        summary=(
            f"DAD asset suggestion: {offering.get('name', asset_id)} "
            f"v{offering.get('version', '')} ({asset_id})"
        ),
        payload=payload,
        evidence=[
            str(offering.get("path", "")),
            "registry/dad-offerings-registry.json",
            *list(offering.get("source_refs", []))[:2],
        ],
        suggested_actions=[
            "Review the asset at its library path before any local adoption.",
            "Record a usage row if this repo adopts or watches the asset.",
        ],
        repo_policies=repo_policies,
        composed_by=composed_by,
        supersedes=supersedes,
        allow_similar=allow_similar,
    )


def central_inbox_path(
    hub_root: Path,
    repo: Path,
    repo_policies: Sequence[Any] | None = None,
) -> Path:
    slug = _central_repo_file_slug(repo, repo_policies)
    return hub_root / CENTRAL_MAIL_DIR / "inbox" / f"{slug}.jsonl"


def _collection_log_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "archive" / "collection_log.jsonl"


def _route_log_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "archive" / "route_log.jsonl"


def _collection_logical_lock_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "archive" / "collection_logical_identity.lock"


def _legacy_collection_allowlist_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "archive" / "legacy_collection_allowlist.jsonl"


def legacy_delivery_allowlist_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "archive" / "legacy_delivery_allowlist.jsonl"


def _mail_record_hash(record: MailMessageRecord | dict[str, Any]) -> str:
    payload = record.model_dump(mode="json") if isinstance(record, MailMessageRecord) else record
    return f"sha256:{sha256_bytes(json_dumps(payload).encode('utf-8'))}"


def _collection_audit_id(record: MailMessageRecord, record_hash: str, event_type: str) -> str:
    return stable_id("mail-collection", event_type, record.mail_id, record.dedupe_key, record_hash)


def _append_collection_audit(
    hub_root: Path,
    repo: Path,
    record: MailMessageRecord,
    *,
    central_path: Path,
    event_type: str,
    repo_policies: Sequence[Any] | None = None,
) -> None:
    record_hash = _mail_record_hash(record)
    payload = {
        "schema_version": "dad_mail_collection_audit.v1",
        "collection_audit_id": _collection_audit_id(record, record_hash, event_type),
        "event_type": event_type,
        "recorded_at": utc_now(),
        "mail_id": record.mail_id,
        "dedupe_key": record.dedupe_key,
        "record_hash": record_hash,
        "source_repo": record.source_repo,
        "target_repo": record.target_repo,
        "source_outbox": _safe_repo_ref(str(_mail_file(repo, "outbox.jsonl")), repo_policies),
        "central_inbox": _relative_path_ref(hub_root, central_path),
        "source_provenance": record.source_provenance,
        "public_release": record.public_release,
        "authority_boundary": (
            "Collection audit proves DAD collect saw this canonical candidate row; "
            "it does not approve adoption, delivery, or public release."
        ),
    }
    _append_unique_by_key(
        _collection_log_path(hub_root),
        sanitize_central_review_record(payload, repo_policies),
        "collection_audit_id",
    )


def _route_audit_id(
    record: MailMessageRecord,
    *,
    source_record_hash: str,
    routed_record_hash: str,
    event_type: str,
) -> str:
    return stable_id(
        "mail-route",
        event_type,
        record.mail_id,
        record.dedupe_key,
        source_record_hash,
        routed_record_hash,
    )


def _append_route_audit(
    hub_root: Path,
    source_inbox_path: Path,
    source_record: MailMessageRecord,
    routed_record: MailMessageRecord,
    *,
    routed_outbox: Path,
    event_type: str,
    repo_policies: Sequence[Any] | None = None,
    operator_ack: str = "",
) -> None:
    source_record_hash = _mail_record_hash(source_record)
    routed_record_hash = _mail_record_hash(routed_record)
    payload = {
        "schema_version": "dad_mail_route_audit.v1",
        "route_audit_id": _route_audit_id(
            routed_record,
            source_record_hash=source_record_hash,
            routed_record_hash=routed_record_hash,
            event_type=event_type,
        ),
        "event_type": event_type,
        "recorded_at": utc_now(),
        "mail_id": routed_record.mail_id,
        "dedupe_key": routed_record.dedupe_key,
        "source_inbox": _relative_path_ref(hub_root, source_inbox_path),
        "source_record_hash": source_record_hash,
        "routed_outbox": _relative_path_ref(hub_root, routed_outbox),
        "routed_record_hash": routed_record_hash,
        "target_repo": routed_record.target_repo,
        "source_provenance": routed_record.source_provenance,
        "public_release": routed_record.public_release,
        "operator_ack": operator_ack,
        "authority_boundary": (
            "Route audit proves DAD route derived this central outbox candidate "
            "from a collected central inbox row. It does not approve adoption, "
            "delivery, or public release."
        ),
    }
    _append_unique_by_key(
        _route_log_path(hub_root),
        sanitize_central_review_record(payload, repo_policies),
        "route_audit_id",
    )


def _route_log_rows(hub_root: Path, *, quarantine_errors: bool = True) -> list[dict[str, Any]]:
    rows, errors = _read_jsonl_with_errors(_route_log_path(hub_root))
    if quarantine_errors:
        _quarantine_jsonl_errors(hub_root, errors)
    return rows


def _central_inbox_record_hashes(
    hub_root: Path,
    *,
    quarantine_errors: bool = True,
) -> set[str]:
    hashes: set[str] = set()
    inbox_dir = hub_root / CENTRAL_MAIL_DIR / "inbox"
    if not inbox_dir.exists():
        return hashes
    for path in sorted(inbox_dir.glob("*.jsonl")):
        rows, errors = _read_jsonl_with_errors(path)
        if quarantine_errors:
            _quarantine_jsonl_errors(hub_root, errors)
        for row in rows:
            try:
                record = MailMessageRecord(**row)
            except ValidationError:
                continue
            hashes.add(_mail_record_hash(record))
    return hashes


def _route_audit_match_status(
    record: MailMessageRecord,
    *,
    route_rows: Sequence[dict[str, Any]],
    central_inbox_hashes: set[str],
) -> tuple[str, dict[str, Any] | None]:
    record_hash = _mail_record_hash(record)
    identity_rows = [
        row
        for row in route_rows
        if str(row.get("mail_id", "")) == record.mail_id
        and str(row.get("dedupe_key", "")) == record.dedupe_key
    ]
    exact_rows = [
        row
        for row in identity_rows
        if str(row.get("routed_record_hash", "")) == record_hash
    ]
    if not exact_rows:
        return ("route_hash_mismatch" if identity_rows else "missing_route_audit"), None
    for row in exact_rows:
        if str(row.get("source_record_hash", "")) in central_inbox_hashes:
            return "verified", row
    return "missing_source_inbox", exact_rows[0]


def _route_repair_equivalent_ignoring_policy_envelope(
    routed_record: MailMessageRecord,
    derived_record: MailMessageRecord,
) -> bool:
    routed_payload = routed_record.model_dump(mode="json")
    derived_payload = derived_record.model_dump(mode="json")
    routed_payload.pop("public_release", None)
    derived_payload.pop("public_release", None)
    return routed_payload == derived_payload


def _stored_mail_record_by_identity(
    path: Path,
    record: MailMessageRecord,
) -> MailMessageRecord | None:
    identity = _dedupe_identity(record.model_dump(mode="json"))
    for row in _read_jsonl(path):
        if _dedupe_identity(row) != identity:
            continue
        try:
            return MailMessageRecord(**row)
        except ValidationError:
            continue
    return None


def _collection_logical_identity(record: MailMessageRecord) -> str:
    original_mail_id = str(record.source_provenance.get("original_mail_id", "") or "").strip()
    if original_mail_id:
        return stable_id(
            "mail-logical-original",
            original_mail_id,
            record.message_type,
            record.target_repo,
        )
    source_key = str(record.source_provenance.get("source_repo_id", "") or "").strip()
    if not source_key:
        source_key = str(record.source_provenance.get("canonical_source_repo", "") or "").strip()
    return stable_id(
        "mail-logical-candidate",
        source_key,
        record.message_type,
        record.target_repo,
        record.dedupe_key,
    )


def _collection_source_policy_key(record: MailMessageRecord) -> str:
    source_repo_id = str(record.source_provenance.get("source_repo_id", "") or "").strip()
    if source_repo_id:
        return f"repo:{source_repo_id}"
    return ""


def _collection_logical_content_hash(record: MailMessageRecord) -> str:
    content = {
        "message_type": record.message_type,
        "target_repo": record.target_repo,
        "sensitivity": record.sensitivity,
        "payload": record.payload,
        "evidence": record.evidence,
        "suggested_actions": record.suggested_actions,
        "original_mail_id": str(record.source_provenance.get("original_mail_id", "") or ""),
    }
    return f"sha256:{sha256_bytes(json_dumps(content).encode('utf-8'))}"


def _stored_central_mail_by_logical_identity(
    hub_root: Path,
    record: MailMessageRecord,
) -> tuple[Path, MailMessageRecord] | None:
    identity = _collection_logical_identity(record)
    directory = hub_root / CENTRAL_MAIL_DIR / "inbox"
    if not directory.exists():
        return None
    for path in sorted(directory.glob("*.jsonl")):
        for row in _read_jsonl(path):
            try:
                stored = MailMessageRecord(**row)
            except ValidationError:
                continue
            if _collection_logical_identity(stored) == identity:
                return path, stored
    return None


def _canonical_collected_record(
    repo: Path, payload: dict[str, Any], repo_policies: Sequence[Any] | None = None
) -> MailMessageRecord:
    try:
        incoming = MailMessageRecord(**payload)
    except ValidationError:
        fallback = _legacy_outbox_record(repo, payload, repo_policies)
        if fallback is None:
            raise
        incoming = fallback
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
    collected_record = _build_mail_record(
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
    return _sanitize_mail_record_for_storage(collected_record, repo_policies)


def _raise_if_source_outbox_has_active_lock(outbox: Path) -> None:
    lock_path = outbox.with_name(f".{outbox.name}.lock")
    if not lock_path.exists():
        return
    diagnostic = _lock_diagnostic(lock_path, stale_lock_seconds=STALE_LOCK_SECONDS)
    if _lock_diagnostic_allows_tombstone_takeover(diagnostic):
        return
    raise TimeoutError(
        f"Timed out waiting for JSONL lock: {lock_path} "
        f"(status={diagnostic.get('status')})"
    )


def collect_mail(
    hub_root: Path, repos: list[Path], repo_policies: Sequence[Any] | None = None
) -> dict[str, Any]:
    collected = 0
    duplicates = 0
    quarantined_invalid = 0
    errors: list[dict[str, str]] = []
    invalid_quarantine_keys = _invalid_mail_quarantine_index(hub_root)
    for repo in repos:
        try:
            outbox = _mail_file(repo, "outbox.jsonl")
            if outbox.exists():
                _raise_if_source_outbox_has_active_lock(outbox)
                payloads, parse_errors, source_signature = _read_stable_jsonl_snapshot(outbox)
            else:
                payloads, parse_errors, source_signature = [], [], None
            if _jsonl_file_signature(outbox) != source_signature:
                raise MailOutboxUnstableError(
                    f"Source outbox changed after snapshot and before collection promotion: {outbox}"
                )
            _quarantine_jsonl_errors(hub_root, parse_errors)
            errors.extend(
                {
                    "repo": _safe_repo_ref(str(repo), repo_policies),
                    **{
                        key: _sanitize_central_review_value(value, repo_policies)
                        for key, value in error.items()
                    },
                }
                for error in parse_errors
            )
        except MailOutboxUnstableError as exc:
            errors.append(
                {
                    "repo": _safe_repo_ref(str(repo), repo_policies),
                    "outbox": _safe_repo_ref(str(outbox), repo_policies),
                    "error_type": "source_outbox_unstable",
                    "error": str(exc),
                    "recommendation": (
                        "Do not promote a moving outbox snapshot; retry collection after the "
                        "source repo agent finishes appending candidate mail."
                    ),
                }
            )
            continue
        except ValueError as exc:
            errors.append(
                {
                    "repo": _safe_repo_ref(str(repo), repo_policies),
                    "error": f"Invalid JSONL outbox: {exc}",
                }
            )
            continue
        except TimeoutError as exc:
            errors.append(
                {
                    "repo": _safe_repo_ref(str(repo), repo_policies),
                    "outbox": _safe_repo_ref(str(outbox), repo_policies),
                    "error_type": "source_outbox_locked",
                    "error": str(exc),
                    "recommendation": (
                        "Do not promote mail while the source outbox lock is active; retry "
                        "collection after the source repo agent finishes writing."
                    ),
                }
            )
            continue
        for payload in payloads:
            try:
                if not isinstance(payload, dict):
                    raise ValueError("JSONL row is not a mail packet object")
                record = _canonical_collected_record(repo, payload, repo_policies)
            except (ValidationError, ValueError) as exc:
                record_hash = _invalid_mail_record_hash(payload)
                source_path_ref = _relative_path_ref(hub_root, outbox)
                if (source_path_ref, record_hash) in invalid_quarantine_keys:
                    quarantined_invalid += 1
                    continue
                safe_error = "Mail packet schema validation failed; row quarantined by hash."
                if "confidential or restricted" in str(exc):
                    safe_error = str(exc)
                quarantine = _quarantine_invalid_mail_packet(
                    hub_root,
                    source_path=outbox,
                    record=payload,
                    repo=repo,
                    repo_policies=repo_policies,
                    reason=safe_error,
                )
                errors.append(
                    {
                        "repo": _safe_repo_ref(str(repo), repo_policies),
                        "error_type": "invalid_mail_packet",
                        "mail_id": str(payload.get("mail_id", ""))
                        if isinstance(payload, dict)
                        else "",
                        "dedupe_key": str(payload.get("dedupe_key", ""))
                        if isinstance(payload, dict)
                        else "",
                        "record_hash": quarantine["record_hash"],
                        "error": safe_error,
                        "quarantine": _relative_path_ref(
                            hub_root,
                            hub_root
                            / CENTRAL_MAIL_DIR
                            / "quarantine"
                            / "invalid_mail_packet.jsonl",
                        ),
                    }
                )
                invalid_quarantine_keys.add((source_path_ref, quarantine["record_hash"]))
                continue
            try:
                with _jsonl_lock(_collection_logical_lock_path(hub_root)):
                    central_path = central_inbox_path(hub_root, repo, repo_policies)
                    stored_logical = _stored_central_mail_by_logical_identity(hub_root, record)
                    if stored_logical is not None:
                        stored_path, stored_record = stored_logical
                        stored_source_key = _collection_source_policy_key(stored_record)
                        incoming_source_key = _collection_source_policy_key(record)
                        if (
                            stored_source_key
                            and incoming_source_key
                            and stored_source_key != incoming_source_key
                        ):
                            errors.append(
                                {
                                    "repo": _safe_repo_ref(str(repo), repo_policies),
                                    "mail_id": record.mail_id,
                                    "error_type": "cross_source_original_identity_conflict",
                                    "error": (
                                        "A central inbox row already exists for this original mail "
                                        "identity from a different reviewed source repo."
                                    ),
                                    "existing_central_inbox": _relative_path_ref(hub_root, stored_path),
                                    "existing_source": stored_source_key,
                                    "incoming_source": incoming_source_key,
                                    "logical_identity": _collection_logical_identity(record),
                                    "recommendation": (
                                        "Treat as a provenance conflict during mail storms; review "
                                        "which repo owns the outbox row before collecting a duplicate."
                                    ),
                                }
                            )
                            continue
                        if _collection_logical_content_hash(
                            stored_record
                        ) != _collection_logical_content_hash(record):
                            errors.append(
                                {
                                    "repo": _safe_repo_ref(str(repo), repo_policies),
                                    "mail_id": record.mail_id,
                                    "error_type": "logical_duplicate_conflict",
                                    "error": (
                                        "A central inbox row already exists for this logical original "
                                        "mail identity but has different canonical content."
                                    ),
                                    "existing_central_inbox": _relative_path_ref(hub_root, stored_path),
                                    "logical_identity": _collection_logical_identity(record),
                                    "recommendation": (
                                        "Review as a possible conflicting branch/worktree variant before "
                                        "promoting a second central candidate."
                                    ),
                                }
                            )
                            continue
                        duplicates += 1
                        _append_collection_audit(
                            hub_root,
                            repo,
                            stored_record,
                            central_path=stored_path,
                            event_type="duplicate_seen",
                            repo_policies=repo_policies,
                        )
                    elif _append_unique(central_path, record):
                        collected += 1
                        _append_collection_audit(
                            hub_root,
                            repo,
                            record,
                            central_path=central_path,
                            event_type="collected",
                            repo_policies=repo_policies,
                        )
                    else:
                        duplicates += 1
                        stored_record = _stored_mail_record_by_identity(central_path, record) or record
                        _append_collection_audit(
                            hub_root,
                            repo,
                            stored_record,
                            central_path=central_path,
                            event_type="duplicate_seen",
                            repo_policies=repo_policies,
                        )
            except TimeoutError as exc:
                errors.append(
                    {
                        "repo": _safe_repo_ref(str(repo), repo_policies),
                        "mail_id": record.mail_id,
                        "error": str(exc),
                    }
                )
    report = write_mail_center_report(hub_root)
    return {
        "collected_count": collected,
        "duplicate_count": duplicates,
        "quarantined_invalid_count": quarantined_invalid,
        "error_count": len(errors),
        "errors": errors,
        "report": report,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _all_central_messages_with_errors(
    hub_root: Path, bucket: str
) -> tuple[list[MailMessageRecord], list[dict[str, str]]]:
    records_with_paths, errors = _all_central_messages_with_paths_and_errors(hub_root, bucket)
    return [record for _path, record in records_with_paths], errors


def _all_central_messages_with_paths_and_errors(
    hub_root: Path, bucket: str
) -> tuple[list[tuple[Path, MailMessageRecord]], list[dict[str, str]]]:
    directory = hub_root / CENTRAL_MAIL_DIR / bucket
    records: list[tuple[Path, MailMessageRecord]] = []
    errors: list[dict[str, str]] = []
    if not directory.exists():
        return records, errors
    for path in sorted(directory.glob("*.jsonl")):
        payloads, parse_errors = _read_jsonl_with_errors(path)
        _quarantine_jsonl_errors(hub_root, parse_errors)
        errors.extend({"path": str(path), "error": str(error["error"])} for error in parse_errors)
        for payload in payloads:
            try:
                records.append((path, MailMessageRecord(**payload)))
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
    repo_policies: Sequence[Any] | None = None,
) -> None:
    _append_central_audit_record(
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
        repo_policies,
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


def _routed_record_from_source(
    record: MailMessageRecord,
    *,
    default_target_repo: str,
    repo_policies: Sequence[Any] | None = None,
) -> MailMessageRecord:
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
    return _sanitize_mail_record_for_storage(routed_record, repo_policies)


def route_mail(
    hub_root: Path,
    *,
    default_target_repo: str = "central_only",
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    routed = 0
    duplicates = 0
    outbox = hub_root / CENTRAL_MAIL_DIR / "outbox" / "routed.jsonl"
    records, errors = _all_central_messages_with_paths_and_errors(hub_root, "inbox")
    collection_audit_keys = _collection_audit_index(hub_root)
    legacy_collection_allowlist_keys = _legacy_collection_allowlist_index(hub_root)
    for source_inbox_path, record in records:
        collection_status, record_hash = _collection_audit_match_status(
            hub_root,
            record,
            collection_audit_keys=collection_audit_keys,
            legacy_collection_allowlist_keys=legacy_collection_allowlist_keys,
        )
        if collection_status not in {"verified", "legacy_allowlisted"}:
            errors.append(
                {
                    "path": _relative_path_ref(hub_root, source_inbox_path),
                    "mail_id": record.mail_id,
                    "dedupe_key": record.dedupe_key,
                    "record_hash": record_hash,
                    "error_type": collection_status,
                    "error": (
                        "Central inbox row is not backed by collection audit "
                        "or reviewed legacy allowlist evidence."
                    ),
                    "recommendation": (
                        "Re-collect from the source repo outbox or quarantine the "
                        "wrong-box central inbox row before routing."
                    ),
                }
            )
            continue
        routed_record = _routed_record_from_source(
            record,
            default_target_repo=default_target_repo,
            repo_policies=repo_policies,
        )
        try:
            if _append_unique(outbox, routed_record):
                routed += 1
                _append_route_audit(
                    hub_root,
                    source_inbox_path,
                    record,
                    routed_record,
                    routed_outbox=outbox,
                    event_type="routed",
                    repo_policies=repo_policies,
                )
            else:
                duplicates += 1
                stored_record = _stored_mail_record_by_identity(outbox, routed_record)
                _append_route_audit(
                    hub_root,
                    source_inbox_path,
                    record,
                    stored_record or routed_record,
                    routed_outbox=outbox,
                    event_type="duplicate_seen",
                    repo_policies=repo_policies,
                )
        except TimeoutError as exc:
            errors.append({"path": str(outbox), "error": str(exc)})
    report = write_mail_center_report(hub_root)
    return {
        "routed_count": routed,
        "duplicate_count": duplicates,
        "error_count": len(errors),
        "errors": errors,
        "blocked": bool(errors),
        "outbox": str(outbox),
        "report": report,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def repair_route_audit_gaps(
    hub_root: Path,
    *,
    default_target_repo: str = "central_only",
    repo_policies: Sequence[Any] | None = None,
    operator_ack: str,
) -> dict[str, Any]:
    """Repair pre-enforcement route audit gaps when source inbox lineage is exact."""

    ack = operator_ack.strip()
    if not ack:
        raise ValueError("operator_ack is required for route audit repair.")
    source_records, source_errors = _all_central_messages_with_paths_and_errors(hub_root, "inbox")
    outbox_records, outbox_errors = _all_central_messages_with_paths_and_errors(hub_root, "outbox")
    route_rows = _route_log_rows(hub_root, quarantine_errors=False)
    central_inbox_hashes = _central_inbox_record_hashes(hub_root, quarantine_errors=False)
    repaired = 0
    skipped: list[dict[str, str]] = []
    routed_outbox = hub_root / CENTRAL_MAIL_DIR / "outbox" / "routed.jsonl"
    derived_records: list[tuple[Path, MailMessageRecord, MailMessageRecord]] = []
    for source_path, source_record in source_records:
        derived = _routed_record_from_source(
            source_record,
            default_target_repo=default_target_repo,
            repo_policies=repo_policies,
        )
        derived_records.append((source_path, source_record, derived))
    for outbox_path, routed_record in outbox_records:
        route_status, _route_row = _route_audit_match_status(
            routed_record,
            route_rows=route_rows,
            central_inbox_hashes=central_inbox_hashes,
        )
        if route_status == "verified":
            continue
        if route_status != "missing_route_audit":
            skipped.append(
                {
                    "mail_id": routed_record.mail_id,
                    "reason": route_status,
                    "path": _relative_path_ref(hub_root, outbox_path),
                }
            )
            continue
        match = next(
            (
                (source_path, source_record)
                for source_path, source_record, derived in derived_records
                if _mail_record_hash(derived) == _mail_record_hash(routed_record)
                or _route_repair_equivalent_ignoring_policy_envelope(
                    routed_record,
                    derived,
                )
            ),
            None,
        )
        if match is None:
            skipped.append(
                {
                    "mail_id": routed_record.mail_id,
                    "reason": "no_exact_source_inbox_match",
                    "path": _relative_path_ref(hub_root, outbox_path),
                }
            )
            continue
        source_path, source_record = match
        _append_route_audit(
            hub_root,
            source_path,
            source_record,
            routed_record,
            routed_outbox=routed_outbox,
            event_type="legacy_route_audit_repaired",
            repo_policies=repo_policies,
            operator_ack=ack,
        )
        route_rows = _route_log_rows(hub_root)
        repaired += 1
    return {
        "schema_version": "dad_mail_route_audit_repair.v1",
        "repaired_count": repaired,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "error_count": len(source_errors) + len(outbox_errors),
        "errors": [*source_errors, *outbox_errors],
        "route_log": _relative_path_ref(hub_root, _route_log_path(hub_root)),
        "operator_ack": ack,
        "authority_boundary": (
            "Route audit repair only records exact lineage from existing collected "
            "central inbox rows to existing routed central outbox rows. It does not "
            "approve delivery, adoption, or public release."
        ),
    }


def _delivery_logged(
    hub_root: Path,
    repo: Path,
    record: MailMessageRecord,
    repo_policies: Sequence[Any] | None = None,
) -> bool:
    log_path = hub_root / CENTRAL_MAIL_DIR / "archive" / "delivery_log.jsonl"
    rows, errors = _read_jsonl_with_errors(log_path)
    _quarantine_jsonl_errors(hub_root, errors)
    target_refs = {_normalized_repo(repo), _safe_repo_ref(repo, repo_policies)}
    expected_record = _sanitize_mail_record_for_storage(
        record.model_copy(update={"review_status": "delivered_candidate"}),
        repo_policies,
    )
    expected_hash = _mail_record_hash(expected_record)
    for row in rows:
        if row.get("event_type") != "delivered":
            continue
        row_target = str(row.get("target_repo", ""))
        if str(row.get("mail_id")) == record.mail_id and (
            _normalized_repo(row_target, preserve_named_target=True) in target_refs
            or row_target in target_refs
        ):
            row_dedupe_key = str(row.get("dedupe_key", ""))
            row_hash = str(row.get("record_hash", ""))
            if row_dedupe_key and row_hash:
                return row_dedupe_key == expected_record.dedupe_key and row_hash == expected_hash
    return False


def _mail_exists(
    repo: Path,
    record: MailMessageRecord,
    hub_root: Path | None = None,
    repo_policies: Sequence[Any] | None = None,
) -> bool:
    identity = _dedupe_identity(record.model_dump(mode="json"))
    inbox_path = _mail_file(repo, "inbox.jsonl")
    if identity in {_dedupe_identity(item) for item in _read_jsonl(inbox_path)}:
        return True
    for item in _read_jsonl(_mail_file(repo, "archive.jsonl")):
        if identity == _dedupe_identity(item):
            return True
    if hub_root and _delivery_logged(hub_root, repo, record, repo_policies):
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
    route_block_count = 0
    skipped: list[dict[str, str]] = []
    delivery_log = hub_root / CENTRAL_MAIL_DIR / "archive" / "delivery_log.jsonl"
    records, errors = _all_central_messages_with_errors(hub_root, "outbox")
    route_rows = _route_log_rows(hub_root, quarantine_errors=False)
    central_inbox_hashes = _central_inbox_record_hashes(hub_root, quarantine_errors=False)
    release_decisions = _release_decisions(hub_root)
    for record in records:
        route_status, route_row = _route_audit_match_status(
            record,
            route_rows=route_rows,
            central_inbox_hashes=central_inbox_hashes,
        )
        if route_status != "verified":
            route_block_count += 1
            skipped.append(
                {
                    "mail_id": record.mail_id,
                    "reason": route_status,
                    "recommendation": (
                        "Rerun route from collected central inbox rows or quarantine the "
                        "central outbox row; deliver only accepts route-audited candidates."
                    ),
                }
            )
            _append_central_audit_record(
                delivery_log,
                {
                    "event_type": "route_audit_block",
                    "created_at": utc_now(),
                    "mail_id": record.mail_id,
                    "dedupe_key": record.dedupe_key,
                    "route_status": route_status,
                    "route_audit_id": str(route_row.get("route_audit_id", ""))
                    if route_row
                    else "",
                    "target_repo": record.target_repo,
                    "source_provenance": record.source_provenance,
                    "public_release": record.public_release,
                },
                repo_policies,
            )
            continue
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
            _append_central_audit_record(
                delivery_log,
                {
                    "event_type": "central_only",
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "reason": _write_protection_reason(target_policy),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": policy_record.public_release,
                },
                repo_policies,
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
                repo_policies=repo_policies,
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
            _append_central_audit_record(
                delivery_log,
                {
                    "event_type": "public_release_rejected",
                    "created_at": utc_now(),
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
                repo_policies,
            )
            rejected_release += 1
            continue
        if release.get("public_release_required") and release.get("public_release_status") != "approved":
            _quarantine_public_hold(
                hub_root,
                policy_record,
                reason="human_release_required",
                repo_policies=repo_policies,
            )
            _append_central_audit_record(
                delivery_log,
                {
                    "event_type": "held_for_public_release",
                    "created_at": utc_now(),
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
                repo_policies,
            )
            held_for_release += 1
            continue
        try:
            ensure_repo_mailbox(target_repo)
        except (OSError, ValueError) as exc:
            _append_central_audit_record(
                delivery_log,
                {
                    "event_type": "central_only",
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "reason": f"target repo mailbox write failed: {exc}",
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
                repo_policies,
            )
            central_only += 1
            continue
        if _mail_exists(target_repo, policy_record, hub_root, repo_policies):
            ack = _ack_record(target_repo, policy_record)
            try:
                _append_unique(_mail_file(target_repo, "archive.jsonl"), ack)
            except (OSError, TimeoutError, ValueError) as exc:
                _append_central_audit_record(
                    delivery_log,
                    {
                        "event_type": "central_only",
                        "mail_id": record.mail_id,
                        "target_repo": str(target_repo),
                        "reason": f"target repo duplicate ack write failed: {exc}",
                        "source_provenance": policy_record.source_provenance,
                        "public_release": release,
                    },
                    repo_policies,
                )
                central_only += 1
                continue
            _append_central_audit_record(
                delivery_log,
                {
                    "event_type": "duplicate_ack",
                    "created_at": utc_now(),
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "source_provenance": policy_record.source_provenance,
                    "public_release": release,
                },
                repo_policies,
            )
            acknowledged_duplicates += 1
            continue
        delivered_record = _sanitize_mail_record_for_storage(
            policy_record.model_copy(update={"review_status": "delivered_candidate"}),
            repo_policies,
        )
        try:
            _append_unique(_mail_file(target_repo, "inbox.jsonl"), delivered_record)
        except (OSError, TimeoutError, ValueError) as exc:
            _append_central_audit_record(
                delivery_log,
                {
                    "event_type": "central_only",
                    "mail_id": record.mail_id,
                    "target_repo": str(target_repo),
                    "reason": f"target repo inbox write failed: {exc}",
                    "source_provenance": delivered_record.source_provenance,
                    "public_release": release,
                },
                repo_policies,
            )
            central_only += 1
            continue
        _append_central_audit_record(
            delivery_log,
            {
                "event_type": "delivered",
                "created_at": utc_now(),
                "mail_id": record.mail_id,
                "dedupe_key": delivered_record.dedupe_key,
                "record_hash": _mail_record_hash(delivered_record),
                "target_repo": str(target_repo),
                "source_provenance": delivered_record.source_provenance,
                "public_release": release,
            },
            repo_policies,
        )
        delivered += 1
    report = write_mail_center_report(hub_root)
    return {
        "delivered_count": delivered,
        "acknowledged_duplicate_count": acknowledged_duplicates,
        "central_only_count": central_only,
        "held_for_release_count": held_for_release,
        "rejected_release_count": rejected_release,
        "route_block_count": route_block_count,
        "skipped": skipped,
        "error_count": len(errors),
        "errors": errors,
        "blocked": bool(route_block_count),
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


def _central_review_log_path(hub_root: Path) -> Path:
    return hub_root / CENTRAL_MAIL_DIR / "archive" / "central_review_decisions.jsonl"


def _central_message_matches_id(record: MailMessageRecord, mail_id: str) -> bool:
    return (
        record.mail_id == mail_id
        or str(record.source_provenance.get("original_mail_id") or "") == mail_id
    )


def review_central_mail(
    hub_root: Path,
    *,
    mail_id: str,
    decision: str,
    decided_by: str = "unknown",
    human_verified: bool = False,
    notes: str = "",
    decided_at: str | None = None,
    repo_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    normalized_decision = decision.replace("-", "_").lower()
    if normalized_decision not in {"accept", "defer", "reject", "archive"}:
        raise ValueError("central mail decision must be accept, defer, reject, or archive")
    records = [
        record
        for record in [
            *_all_central_messages(hub_root, "inbox"),
            *_all_central_messages(hub_root, "outbox"),
        ]
        if _central_message_matches_id(record, mail_id)
    ]
    if not records:
        raise ValueError(f"No central mail found for {mail_id}.")
    record = records[0]
    timestamp = decided_at or utc_now()
    decision_record = MailDecisionRecord(
        decision_id=stable_id(
            "central-mail-decision",
            record.mail_id,
            normalized_decision,
            "human" if human_verified else "agent",
        ),
        mail_id=record.mail_id,
        repository="dad://central-mail",
        decision=normalized_decision,  # type: ignore[arg-type]
        decided_at=timestamp,
        decided_by=decided_by,
        decision_actor_type="human" if human_verified else "agent",
        human_verified=human_verified,
        notes=notes,
        review_status="human_reviewed" if human_verified else "agent_triage",
    )
    payload = sanitize_central_review_record(
        {
            **decision_record.model_dump(mode="json"),
            "schema_version": "0.1.0",
            "requested_mail_id": mail_id,
            "central_review": True,
            "message_type": record.message_type,
            "source_repo": record.source_repo,
            "target_repo": record.target_repo,
            "dedupe_key": record.dedupe_key,
            "source_provenance": record.source_provenance,
            "public_release": record.public_release,
            "public_release_gate_satisfied": False,
            "target_repo_adoption_satisfied": False,
            "authority_boundary": (
                "Central mail review is DAD triage only. It does not satisfy human "
                "public release, deliver mail to a target repo, or create target repo adoption."
            ),
        },
        repo_policies,
    )
    log_path = _central_review_log_path(hub_root)
    appended = _append_unique_central_decision(log_path, payload)
    report = write_mail_center_report(hub_root)
    return {
        "decision": payload,
        "appended": appended,
        "archive": (CENTRAL_MAIL_DIR / "archive" / "central_review_decisions.jsonl").as_posix(),
        "report": report,
        "authority_boundary": payload["authority_boundary"],
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
    repo_policies: Sequence[Any] | None = None,
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
    record = sanitize_central_review_record(record, repo_policies)
    append_jsonl_locked(_release_record_path(hub_root), record)
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
        allow_direct_fallback=True,
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


DEFERRED_TRIAGE_DECISIONS = {"save_for_future", "defer"}
DEFERRED_MAIL_PAYLOAD_KEYS = (
    "summary",
    "note",
    "notes",
    "path",
    "paths",
    "asset_id",
    "asset_ids",
    "capability",
    "taxonomy",
    "source_ref",
)
DEFERRED_MATCH_BASIS = (
    "deterministic keyword overlap between current task tokens and the deferred message's "
    "type, payload, evidence, suggested actions, and adoption notes after stopword removal; "
    "count-ranked routing aid, not a value score. repo_watches_asset comes from central "
    "usage-ledger rows with status using or watching for an asset the message references."
)


def _latest_adoption_by_mail(repo: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(_mail_file(repo, "adoption.jsonl")):
        mail_id = str(row.get("mail_id", ""))
        if not mail_id:
            continue
        current = latest.get(mail_id)
        if current is None or str(row.get("recorded_at", "")) >= str(current.get("recorded_at", "")):
            latest[mail_id] = row
    return latest


def _deferred_message_index(repo: Path) -> dict[str, dict[str, Any]]:
    messages: dict[str, dict[str, Any]] = {}
    for name in ("inbox.jsonl", "archive.jsonl"):
        for row in _read_jsonl(_mail_file(repo, name)):
            mail_id = str(row.get("mail_id", ""))
            if mail_id:
                messages.setdefault(mail_id, row)
    return messages


def _watched_assets_for_repo(hub_root: Path, repo: Path) -> set[str]:
    ledger = hub_root / "processed" / "usage" / "repo-asset-usage.jsonl"
    normalized = str(repo.resolve()).replace("\\", "/")
    watched: set[str] = set()
    for row in _read_jsonl(ledger):
        if str(row.get("status", "")) not in {"using", "watching"}:
            continue
        row_repo = str(row.get("repo", ""))
        if row_repo == normalized or Path(row_repo).name == repo.name:
            asset_id = str(row.get("asset_id", ""))
            if asset_id:
                watched.add(asset_id)
    return watched


def resurface_deferred_mail(
    repo: Path,
    *,
    task: str,
    hub_root: Path | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Bring back save_for_future/defer mail when the current task or watched assets make it relevant.

    Combines two signals: the repo's own triage records (its read mail) and the central
    usage ledger (library edges showing the repo now uses or watches a referenced asset).
    Resurfaced items are candidates to re-triage, not obligations.
    """
    from .dad_library import PATTERN_MATCH_STOPWORDS, _tokenize

    adoption = _latest_adoption_by_mail(repo)
    deferred = {
        mail_id: row
        for mail_id, row in adoption.items()
        if str(row.get("intake_decision", "")) in DEFERRED_TRIAGE_DECISIONS
    }
    result = {
        "deferred_total": len(deferred),
        "match_basis": DEFERRED_MATCH_BASIS,
        "items": [],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if not deferred:
        return result
    messages = _deferred_message_index(repo)
    task_tokens = _tokenize(task) - PATTERN_MATCH_STOPWORDS
    watched = _watched_assets_for_repo(hub_root, repo) if hub_root else set()
    items: list[dict[str, Any]] = []
    for mail_id, row in deferred.items():
        message = messages.get(mail_id, {})
        payload = message.get("payload", {}) if isinstance(message.get("payload"), dict) else {}
        asset_refs = sorted(
            {
                str(value)
                for value in [
                    payload.get("asset_id", ""),
                    *(payload.get("asset_ids") or []),
                    *(row.get("source_asset_refs") or []),
                ]
                if str(value)
            }
        )
        message_tokens = _tokenize(
            [
                str(message.get("message_type", "")),
                *[payload.get(key) for key in DEFERRED_MAIL_PAYLOAD_KEYS],
                message.get("evidence", []),
                message.get("suggested_actions", []),
                str(row.get("planned_use", "")),
                str(row.get("notes", "")),
                asset_refs,
            ]
        ) - PATTERN_MATCH_STOPWORDS
        matched = sorted(task_tokens & message_tokens)
        repo_watches_asset = bool(watched & set(asset_refs))
        if not matched and not repo_watches_asset:
            continue
        summary = str(payload.get("summary") or payload.get("note") or "")[:160]
        items.append(
            {
                "mail_id": mail_id,
                "message_type": str(message.get("message_type", "unknown")),
                "summary": summary,
                "intake_decision": str(row.get("intake_decision", "")),
                "recorded_at": str(row.get("recorded_at", "")),
                "matched_terms": matched,
                "repo_watches_asset": repo_watches_asset,
                "source_asset_refs": asset_refs,
                "why_now": (
                    "repo now uses or watches a referenced asset"
                    if repo_watches_asset
                    else "previously deferred mail matches the current task context"
                ),
                "next_step": "Re-triage with asset-dir mail triage; resurfacing is a reminder, not an obligation.",
            }
        )
    items.sort(
        key=lambda item: (
            not item["repo_watches_asset"],
            -len(item["matched_terms"]),
            item["mail_id"],
        )
    )
    result["items"] = items[:limit]
    return result


def _relative_path_ref(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return _safe_repo_ref(str(path))


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return False
    return True


def _mail_packet_identity(record: dict[str, Any]) -> str | None:
    """Return a dedupe identity only for actual mail packet rows."""

    required = {"mail_id", "thread_id", "message_type", "source_repo", "target_repo", "dedupe_key"}
    if not required.issubset(record):
        return None
    try:
        MailMessageRecord(**record)
    except ValidationError:
        return None
    identity = _dedupe_identity(record)
    return None if identity == "|" else identity


def _mail_path_stage(hub_root: Path, path: Path) -> str:
    if path.name == "outbox.jsonl" and path.parent.name == "mail" and path.parent.parent.name == ".digital-asset":
        return "repo_mirror_outbox"
    if path.name == "inbox.jsonl" and path.parent.name == "mail" and path.parent.parent.name == ".digital-asset":
        return "repo_mirror_inbox"
    if path.name == "archive.jsonl" and path.parent.name == "mail" and path.parent.parent.name == ".digital-asset":
        return "repo_mirror_archive"
    rel = _relative_path_ref(hub_root, path)
    normalized = rel.replace("\\", "/")
    if normalized == ".digital-asset/mail/outbox.jsonl" or normalized.endswith(
        "/.digital-asset/mail/outbox.jsonl"
    ):
        return "repo_mirror_outbox"
    if normalized == ".digital-asset/mail/inbox.jsonl" or normalized.endswith(
        "/.digital-asset/mail/inbox.jsonl"
    ):
        return "repo_mirror_inbox"
    if normalized == ".digital-asset/mail/archive.jsonl" or normalized.endswith(
        "/.digital-asset/mail/archive.jsonl"
    ):
        return "repo_mirror_archive"
    if normalized.startswith((CENTRAL_MAIL_DIR / "inbox").as_posix() + "/"):
        return "central_inbox"
    if normalized.startswith((CENTRAL_MAIL_DIR / "outbox").as_posix() + "/"):
        return "central_outbox"
    if normalized.startswith((CENTRAL_MAIL_DIR / "archive").as_posix() + "/"):
        return "central_archive"
    if normalized.startswith((CENTRAL_MAIL_DIR / "quarantine").as_posix() + "/"):
        return "central_quarantine"
    if normalized.startswith((CENTRAL_MAIL_DIR / "releases").as_posix() + "/"):
        return "central_release"
    return "other_jsonl"


def _rust_rollout_path_class(hub_root: Path, path: Path) -> str:
    normalized = _relative_path_ref(hub_root, path).replace("\\", "/")
    if normalized.startswith("processed/mail/staged/rust_rollout/"):
        return "ignored_staging"
    if normalized.startswith("mail/outbox/rust_rollout/"):
        return "tracked_reference_snapshot"
    return "rust_rollout_packet"


def _rust_rollout_semantic_identity(record: MailMessageRecord) -> str | None:
    payload = record.payload
    packet_type = str(payload.get("rust_rollout_packet_type", "") or "")
    if not packet_type:
        return None
    return "|".join(
        [
            str(record.source_repo),
            str(record.target_repo),
            str(record.thread_id),
            packet_type,
            str(payload.get("rollout_mode", "") or ""),
        ]
    )


def _rust_rollout_semantic_content_hash(record: MailMessageRecord) -> str:
    stable_record = record.model_dump(mode="json")
    for key in ("mail_id", "dedupe_key", "created_at", "review_status"):
        stable_record.pop(key, None)
    source_provenance = stable_record.get("source_provenance")
    if isinstance(source_provenance, dict):
        for key in ("collected_at", "received_at"):
            source_provenance.pop(key, None)
    payload_obj = stable_record.get("payload")
    if isinstance(payload_obj, dict):
        for key in ("packet_identity_basis", "rust_rollout_revision_id"):
            payload_obj.pop(key, None)
    payload = json.dumps(stable_record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256_bytes(payload)}"


def _is_unexpected_repo_mail_jsonl(path: Path) -> bool:
    return (
        path.suffix == ".jsonl"
        and path.parent.name == "mail"
        and path.parent.parent.name == ".digital-asset"
        and path.name not in LIVE_MAIL_JSONL_NAMES
    )


def _repo_root_for_mail_mirror_path(path: Path) -> Path | None:
    if (
        path.name in {"inbox.jsonl", "outbox.jsonl", "archive.jsonl", "adoption.jsonl"}
        and path.parent.name == "mail"
        and path.parent.parent.name == ".digital-asset"
    ):
        return path.parent.parent.parent
    return None


def _delivery_log_matches_repo(
    row: dict[str, Any],
    *,
    hub_root: Path,
    repo: Path,
    mail_id: str,
    repo_policies: Sequence[Any] | None = None,
) -> bool:
    if row.get("event_type") != "delivered" or str(row.get("mail_id", "")) != mail_id:
        return False
    row_target = str(row.get("target_repo", "")).strip()
    target_refs = {
        _normalized_repo(repo),
        _safe_repo_ref(repo, repo_policies),
    }
    policy = _policy_for_repo(repo, repo_policies)
    if policy is not None:
        target_refs.update(_policy_aliases(policy))
        target_refs.add(f"repo:{getattr(policy, 'id', 'unknown')}")
    if repo.resolve() == hub_root.resolve():
        target_refs.add("dad")
    normalized_row_target = _normalized_repo(row_target, preserve_named_target=True)
    return row_target in target_refs or normalized_row_target in target_refs


def _delivery_log_match_status_for_repo_inbox(
    row: dict[str, Any],
    *,
    hub_root: Path,
    repo: Path,
    record: dict[str, Any],
    repo_policies: Sequence[Any] | None = None,
) -> str:
    mail_id = str(record.get("mail_id", ""))
    if not _delivery_log_matches_repo(
        row,
        hub_root=hub_root,
        repo=repo,
        mail_id=mail_id,
        repo_policies=repo_policies,
    ):
        return "no_match"
    row_dedupe_key = str(row.get("dedupe_key", ""))
    row_hash = str(row.get("record_hash", ""))
    if not row_dedupe_key and not row_hash:
        return "legacy_unhashed"
    expected_dedupe_key = str(record.get("dedupe_key", ""))
    expected_hash = _mail_record_hash(record)
    if row_dedupe_key == expected_dedupe_key and row_hash == expected_hash:
        return "verified"
    return "hash_mismatch"


def _legacy_delivery_allowlist_index(hub_root: Path) -> set[tuple[str, str, str, str]]:
    rows, _ = _read_jsonl_with_errors(legacy_delivery_allowlist_path(hub_root))
    return {
        (
            str(row.get("mail_id", "")),
            str(row.get("dedupe_key", "")),
            str(row.get("record_hash", "")),
            str(row.get("target_repo", "")),
        )
        for row in rows
        if str(row.get("mail_id", ""))
        and str(row.get("dedupe_key", ""))
        and str(row.get("record_hash", ""))
        and str(row.get("target_repo", ""))
        and str(row.get("review_status", "")) in {"reviewed_legacy", "allowed_legacy"}
    }


def _invalid_mail_quarantine_index(hub_root: Path) -> set[tuple[str, str]]:
    rows, _ = _read_jsonl_with_errors(invalid_mail_quarantine_path(hub_root))
    return {
        (
            str(row.get("path", "")),
            str(row.get("record_hash", "")),
        )
        for row in rows
        if str(row.get("event_type", "")) == "invalid_mail_packet"
        and str(row.get("path", ""))
        and str(row.get("record_hash", ""))
        and row.get("raw_payload_copied") is False
    }


def _lock_diagnostic(lock_path: Path, *, stale_lock_seconds: float) -> dict[str, Any]:
    try:
        age_seconds = max(0.0, time.time() - lock_path.stat().st_mtime)
    except OSError as exc:
        return {
            "status": "unreadable",
            "age_seconds": None,
            "owner_pid": None,
            "owner_alive": None,
            "error": str(exc),
        }
    owner_pid = _jsonl_lock_owner_pid(lock_path)
    owner_alive = _jsonl_lock_pid_is_alive(owner_pid) if owner_pid else None
    lock_key = lock_path.resolve()
    if owner_pid == os.getpid() and lock_key not in _ACTIVE_JSONL_LOCKS:
        status = "same_process_leftover"
    elif owner_pid and owner_alive is False:
        status = "dead_owner"
    elif age_seconds > stale_lock_seconds:
        status = "stale"
    else:
        status = "active"
    return {
        "status": status,
        "age_seconds": round(age_seconds, 3),
        "owner_pid": owner_pid,
        "owner_alive": owner_alive,
        "error": "",
    }


def _parse_iso_datetime(value: str) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _collection_audit_index(hub_root: Path) -> set[tuple[str, str, str]]:
    rows, _ = _read_jsonl_with_errors(_collection_log_path(hub_root))
    return {
        (
            str(row.get("mail_id", "")),
            str(row.get("dedupe_key", "")),
            str(row.get("record_hash", "")),
        )
        for row in rows
        if str(row.get("mail_id", ""))
        and str(row.get("dedupe_key", ""))
        and str(row.get("record_hash", ""))
    }


def _legacy_collection_allowlist_index(hub_root: Path) -> set[tuple[str, str, str]]:
    rows, _ = _read_jsonl_with_errors(_legacy_collection_allowlist_path(hub_root))
    return {
        (
            str(row.get("mail_id", "")),
            str(row.get("dedupe_key", "")),
            str(row.get("record_hash", "")),
        )
        for row in rows
        if str(row.get("mail_id", ""))
        and str(row.get("dedupe_key", ""))
        and str(row.get("record_hash", ""))
        and str(row.get("review_status", "")) in {"reviewed_legacy", "allowed_legacy"}
    }


def _collection_audit_match_status(
    hub_root: Path,
    record: MailMessageRecord,
    *,
    collection_audit_keys: set[tuple[str, str, str]] | None = None,
    legacy_collection_allowlist_keys: set[tuple[str, str, str]] | None = None,
) -> tuple[str, str]:
    record_hash = _mail_record_hash(record)
    audit_key = (record.mail_id, record.dedupe_key, record_hash)
    if collection_audit_keys is None:
        collection_audit_keys = _collection_audit_index(hub_root)
    if legacy_collection_allowlist_keys is None:
        legacy_collection_allowlist_keys = _legacy_collection_allowlist_index(hub_root)
    if audit_key in collection_audit_keys:
        return "verified", record_hash

    collected_at_text = str(record.source_provenance.get("collected_at", "") or "")
    collected_at = _parse_iso_datetime(collected_at_text)
    if collected_at is None:
        return "missing_collection_provenance", record_hash
    collection_audit_enforced_at = _parse_iso_datetime(COLLECTION_AUDIT_ENFORCED_AT)
    if (
        collection_audit_enforced_at
        and collected_at < collection_audit_enforced_at
        and audit_key in legacy_collection_allowlist_keys
    ):
        return "legacy_allowlisted", record_hash
    return "missing_collection_audit", record_hash


def _mail_dirty_issue_severity(issue_type: str) -> str:
    if issue_type in {
        "central_inbox_uncollected_row",
        "central_inbox_missing_collection_audit",
        "central_inbox_missing_collection_provenance",
        "central_outbox_missing_route_audit",
        "central_outbox_unrouted_row",
        "repo_inbox_without_delivery_log",
        "rust_rollout_packet_write_claim",
    }:
        return "critical"
    if issue_type in {
        "central_inbox_duplicate_logical_identity",
        "central_outbox_route_hash_mismatch",
        "central_outbox_missing_source_inbox",
        "unknown_source_outbox_duplicate_identity",
        "source_outbox_unstable",
        "invalid_mail_packet",
        "malformed_jsonl",
        "oversized_jsonl_record",
        "duplicate_jsonl_identity",
        "cross_file_same_stage_duplicate_identity",
        "cross_source_outbox_duplicate_identity",
        "repo_inbox_delivery_hash_mismatch",
        "rust_rollout_packet_invalid",
        "rust_rollout_packet_delivery_status",
        "rust_rollout_duplicate_packet_identity",
        "rust_rollout_semantic_identity_conflict",
    }:
        return "high"
    if issue_type in {"jsonl_lock", "atomic_temp_fragment"}:
        return "medium"
    return "low"


def _mail_dirty_action_summary(
    *,
    issues: Sequence[dict[str, Any]],
    summary: dict[str, Any],
    repaired: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    issue_types = {str(issue.get("issue_type", "")) for issue in issues}
    for issue in issues:
        severity = _mail_dirty_issue_severity(str(issue.get("issue_type", "")))
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    legacy_observation_count = int(summary.get("legacy_collection_audit_gap_count", 0)) + int(
        summary.get("repo_inbox_legacy_delivery_allowlist_count", 0)
    )
    quarantine_observation_count = int(summary.get("invalid_mail_packet_quarantine_count", 0))
    lock_tombstone_observation_count = int(summary.get("lock_tombstone_observation_count", 0))

    next_actions: list[str] = []
    if not issues:
        if lock_tombstone_observation_count:
            next_actions.append(
                "Proceed with normal collection/routing, but clean up dead lock tombstones "
                "when the filesystem permits; active locks still fail closed."
            )
        if quarantine_observation_count:
            next_actions.append(
                "Proceed with normal collection/routing only after confirming quarantined "
                "source-outbox rows are hash-bound metadata records; source repos should "
                "fix or replay those invalid rows through their own outbox."
            )
        if int(summary.get("legacy_collection_audit_gap_count", 0)):
            next_actions.append(
                "Proceed with normal collection/routing; legacy central inbox rows predate "
                "collection-audit enforcement and should not be rewritten by default."
            )
        if int(summary.get("repo_inbox_legacy_delivery_allowlist_count", 0)):
            next_actions.append(
                "Proceed with normal collection/routing, but remember reviewed legacy repo "
                "inbox allowlist rows are migration evidence only and remain hash-bound "
                "candidate mail."
            )
        if int(summary.get("unexpected_repo_mail_jsonl_count", 0)):
            next_actions.append(
                "Proceed with live mailbox operations, but move backup or repair JSONL files "
                "out of .digital-asset/mail or rename them without a .jsonl extension."
            )
        if int(summary.get("source_outbox_duplicate_identity_count", 0)):
            next_actions.append(
                "Proceed with collection when repo policy allows; duplicate source outbox rows "
                "are storm/backpressure observations and DAD collection will canonicalize one "
                "row while recording duplicate_seen audit evidence."
            )
        if not next_actions:
            next_actions.append("Proceed with normal collection/routing when repo policy allows.")
    if issue_types & {
        "central_inbox_uncollected_row",
        "central_inbox_missing_collection_audit",
        "central_inbox_missing_collection_provenance",
    }:
        next_actions.append(
            "Pause collection promotion; re-collect from the source repo outbox or quarantine "
            "central inbox rows that lack collection provenance/audit hash."
        )
    if "repo_inbox_without_delivery_log" in issue_types:
        next_actions.append(
            "Treat repo inbox rows without delivery logs as wrong-box writes; move decisions "
            "back through repo outbox/DAD delivery after review."
        )
    if issue_types & {
        "central_outbox_missing_route_audit",
        "central_outbox_unrouted_row",
        "central_outbox_route_hash_mismatch",
        "central_outbox_missing_source_inbox",
    }:
        next_actions.append(
            "Pause delivery; central outbox rows must be route-audited from collected "
            "central inbox rows. Rerun route to repair missing route audit when the source "
            "inbox row still exists, or quarantine direct/mutated routed rows."
        )
    if "repo_inbox_delivery_hash_mismatch" in issue_types:
        next_actions.append(
            "Treat repo inbox rows whose delivery log hash no longer matches as mutated or "
            "stale delivery evidence; re-deliver from central outbox or quarantine after review."
        )
    if "central_inbox_duplicate_logical_identity" in issue_types:
        next_actions.append(
            "Pause collection promotion; review central inbox rows that share one logical original "
            "mail identity and keep only the provenance-correct canonical candidate."
        )
    if issue_types & {"malformed_jsonl", "oversized_jsonl_record"}:
        next_actions.append(
            "Quarantine malformed or oversized rows by hash/metadata only; continue processing "
            "well-formed rows."
        )
    if "invalid_mail_packet" in issue_types:
        next_actions.append(
            "Quarantine valid JSON rows that fail the mail packet schema by hash/metadata only; "
            "continue processing well-formed mail rows."
        )
    if "source_outbox_unstable" in issue_types:
        next_actions.append(
            "Pause collection until source repo outboxes stop changing; retry after repo agents "
            "finish appending candidate mail."
        )
    if issue_types & {"duplicate_jsonl_identity", "cross_file_same_stage_duplicate_identity"}:
        next_actions.append(
            "Deduplicate same-stage packet identities before delivery so repeated agents do not spam inboxes."
        )
    if "cross_source_outbox_duplicate_identity" in issue_types:
        next_actions.append(
            "Treat matching packet identities from different reviewed source repo IDs as a "
            "provenance conflict; collect from the owning repo only after review."
        )
    if "unknown_source_outbox_duplicate_identity" in issue_types:
        next_actions.append(
            "Treat matching packet identities across outboxes without one reviewed source repo ID "
            "as a provenance conflict. Add reviewed mail.repos policy or inspect the copied "
            "worktree lineage before collection."
        )
    if issue_types & {"jsonl_lock", "atomic_temp_fragment"}:
        next_actions.append(
            "Repair only stale/dead locks or stale atomic temp fragments; leave active locks alone."
        )
    if issue_types & {
        "rust_rollout_packet_invalid",
        "rust_rollout_packet_delivery_status",
        "rust_rollout_packet_write_claim",
        "rust_rollout_duplicate_packet_identity",
        "rust_rollout_semantic_identity_conflict",
    }:
        next_actions.append(
            "Regenerate Rust rollout packets into ignored staging, then review the tracked snapshot; "
            "do not treat Rust rollout packets as delivered mail."
        )

    if severity_counts["critical"]:
        status = "blocked"
        can_collect = False
        can_route = False
        can_deliver = False
    elif severity_counts["high"]:
        status = "dirty_needs_review"
        can_collect = False
        can_route = False
        can_deliver = False
    elif severity_counts["medium"]:
        status = "dirty_repairable"
        can_collect = False
        can_route = False
        can_deliver = False
    elif legacy_observation_count:
        status = "clean_with_legacy_observations"
        can_collect = True
        can_route = True
        can_deliver = True
    elif quarantine_observation_count:
        status = "clean_with_quarantine_observations"
        can_collect = True
        can_route = True
        can_deliver = True
    elif int(summary.get("unexpected_repo_mail_jsonl_count", 0)):
        status = "clean_with_mailbox_hygiene_observations"
        can_collect = True
        can_route = True
        can_deliver = True
    elif int(summary.get("source_outbox_duplicate_identity_count", 0)):
        status = "clean_with_source_outbox_duplicates"
        can_collect = True
        can_route = True
        can_deliver = True
    elif lock_tombstone_observation_count:
        status = "clean_with_lock_tombstone_observations"
        can_collect = True
        can_route = True
        can_deliver = True
    else:
        status = "clean"
        can_collect = True
        can_route = True
        can_deliver = True

    return {
        "schema_version": "dad_mail_dirty_action_summary.v1",
        "status": status,
        "severity_counts": severity_counts,
        "blocking_issue_count": severity_counts["critical"] + severity_counts["high"],
        "repairable_issue_count": severity_counts["medium"],
        "legacy_observation_count": legacy_observation_count,
        "quarantine_observation_count": quarantine_observation_count,
        "lock_tombstone_observation_count": lock_tombstone_observation_count,
        "mailbox_hygiene_observation_count": int(
            summary.get("unexpected_repo_mail_jsonl_count", 0)
        ),
        "lifecycle_observation_count": int(summary.get("lifecycle_observation_count", 0)),
        "repaired_count": len(repaired),
        "safe_to_collect": can_collect,
        "safe_to_route": can_route,
        "safe_to_deliver": can_deliver,
        "next_actions": next_actions,
    }


def _mail_diagnostic_roots(hub_root: Path, repos: Sequence[Path] | None) -> list[Path]:
    roots = [
        hub_root / MAIL_MIRROR_DIR,
        hub_root / CENTRAL_MAIL_DIR,
        hub_root / "mail" / "outbox" / "rust_rollout",
        hub_root / CENTRAL_MAIL_DIR / "staged" / "rust_rollout",
    ]
    for repo in repos or []:
        roots.append(repo / MAIL_MIRROR_DIR)
    seen: set[Path] = set()
    output: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        output.append(root)
    return output


def _worktree_dirty_category(path_ref: str) -> str:
    normalized = path_ref.replace("\\", "/")
    if " -> " in normalized:
        normalized = normalized.rsplit(" -> ", 1)[-1]
    if normalized.startswith(".digital-asset/mail/"):
        return "repo_local_mail_mirror"
    if normalized.startswith("processed/mail/staged/rust_rollout/"):
        return "ignored_rust_rollout_staging"
    if normalized.startswith("processed/mail/"):
        return "central_mail_spool"
    if normalized.startswith("mail/outbox/rust_rollout/"):
        return "rust_rollout_reference_snapshot"
    if normalized.startswith(("raw/", "processed/")):
        return "generated_or_collected_evidence"
    if normalized.startswith(
        (
            "tools/dad_scan_core/",
            "src/digital_asset_directory/rust_bridge/",
            "src/digital_asset_directory/rust_rollout/",
            "assets/dad-rust-upgrade-starter-pack/",
            "docs/rust/",
            "lessons/rust_rollout/",
        )
    ):
        return "rust_buildout_surface"
    if normalized.startswith(("assets/coding-harnesses/", "assets/agent-skills/")):
        return "dad_asset_or_skill_library"
    if normalized.startswith("assets/"):
        return "dad_asset_library"
    if normalized in {
        "AGENTS.md",
        "CLAUDE.md",
        "AI_FRONT_DOOR.md",
        "AI_TABLE_OF_CONTENTS.md",
        "MACHINE_NAVIGATION_MANIFEST.json",
        "pyproject.toml",
        "uv.lock",
    }:
        return "dad_source_or_governance"
    if normalized.startswith(
        (
            "src/",
            "tests/",
            "schemas/",
            "registry/",
            "docs/",
            "roadmap/",
            "config/",
            "templates/",
            "scripts/",
        )
    ):
        return "dad_source_or_governance"
    return "other_worktree_change"


def _git_worktree_dirty_state(hub_root: Path, *, sample_limit: int = 25) -> dict[str, Any]:
    base = {
        "schema_version": "dad_git_worktree_dirty_state.v1",
        "evaluated": False,
        "is_git_worktree": False,
        "is_dirty": False,
        "changed_count": 0,
        "counts_by_category": {},
        "samples": [],
        "guidance": [
            "Mail dirty state and git worktree dirty state are separate. A dirty git tree "
            "does not by itself mean DAD mail spools are corrupt."
        ],
    }
    try:
        root = hub_root.resolve()
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**base, "evaluated": True, "status": "unavailable", "error": str(exc)}
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return {
            **base,
            "evaluated": True,
            "status": "not_git_worktree",
            "guidance": base["guidance"] + ["No git worktree was detected for the DAD hub root."],
        }
    try:
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--short", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            **base,
            "evaluated": True,
            "is_git_worktree": True,
            "status": "unavailable",
            "error": str(exc),
        }
    if status.returncode != 0:
        return {
            **base,
            "evaluated": True,
            "is_git_worktree": True,
            "status": "unavailable",
            "error": (status.stderr or status.stdout).strip(),
        }
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    counts: dict[str, int] = {}
    samples: list[dict[str, str]] = []
    for line in lines:
        state = line[:2].strip() or line[:2]
        path_ref = line[3:].strip() if len(line) > 3 else line.strip()
        category = _worktree_dirty_category(path_ref)
        counts[category] = counts.get(category, 0) + 1
        if len(samples) < sample_limit:
            samples.append({"status": state, "path": path_ref, "category": category})
    guidance = list(base["guidance"])
    if counts.get("rust_rollout_reference_snapshot"):
        guidance.append(
            "Tracked mail/outbox/rust_rollout changes are reference-snapshot churn; "
            "routine branch work should regenerate Rust rollout packets under ignored "
            "processed/mail/staged/rust_rollout and promote the snapshot deliberately. "
            "Intentional promotions should have metadata-only audit rows in "
            "processed/mail/archive/rust_rollout_snapshot_promotion.jsonl."
        )
    if counts.get("central_mail_spool") or counts.get("repo_local_mail_mirror"):
        guidance.append(
            "Mail-path git changes deserve mailbox review, but the authoritative "
            "block/allow decision still comes from mail doctor issue checks and delivery audits."
        )
    if lines and not (counts.get("central_mail_spool") or counts.get("repo_local_mail_mirror")):
        guidance.append(
            "The worktree is dirty outside mailbox spools; review with git status/diff, "
            "but do not treat it as mail corruption."
        )
    return {
        **base,
        "evaluated": True,
        "is_git_worktree": True,
        "status": "dirty" if lines else "clean",
        "is_dirty": bool(lines),
        "changed_count": len(lines),
        "counts_by_category": counts,
        "samples": samples,
        "guidance": guidance,
    }


def diagnose_mail_dirty_state(
    hub_root: Path,
    repos: Sequence[Path] | None = None,
    *,
    repo_policies: Sequence[Any] | None = None,
    repair_stale_locks: bool = False,
    repair_temp_fragments: bool = False,
    stale_lock_seconds: float = STALE_LOCK_SECONDS,
) -> dict[str, Any]:
    """Inspect DAD mail spools for dirty concurrent-write symptoms.

    This is an operator diagnostic. It does not collect, route, deliver, review,
    or promote mail, and by default it does not mutate any mailbox.
    """

    issues: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    repaired: list[dict[str, Any]] = []
    roots = _mail_diagnostic_roots(hub_root, repos)
    jsonl_paths: list[Path] = []
    rust_packet_paths: list[Path] = []

    for root in roots:
        if not root.exists():
            continue
        jsonl_paths.extend(path for path in root.rglob("*.jsonl") if path.is_file())
        rust_packet_paths.extend(
            path
            for path in root.rglob("*.json")
            if path.is_file() and "rust_rollout" in path.as_posix().replace("\\", "/")
        )
        for lock_path in sorted(root.rglob("*.lock")):
            diagnostic = _lock_diagnostic(lock_path, stale_lock_seconds=stale_lock_seconds)
            path_ref = _relative_path_ref(hub_root, lock_path)
            if _lock_diagnostic_allows_tombstone_takeover(diagnostic):
                repair_attempted = bool(repair_stale_locks)
                repair_removed = False
                if repair_stale_locks:
                    repair_removed = _unlink_jsonl_lock(lock_path)
                    repaired.append(
                        {
                            "action": "remove_stale_lock",
                            "path": path_ref,
                            "removed": repair_removed,
                            "status": diagnostic["status"],
                        }
                    )
                    if repair_removed:
                        continue
                observations.append(
                    {
                        "observation_type": "jsonl_lock_tombstone",
                        "path": path_ref,
                        **diagnostic,
                        "repair_attempted": repair_attempted,
                        "repair_removed": repair_removed if repair_attempted else None,
                        "meaning": (
                            "This lock owner is gone or the lock is a same-process leftover. "
                            "It is mailbox hygiene evidence, but it does not block collection "
                            "because DAD can take over dead lock tombstones without writing "
                            "outside the mailbox stream."
                        ),
                    }
                )
                continue
            issue = {
                "issue_type": "jsonl_lock",
                "path": path_ref,
                **diagnostic,
            }
            if repair_stale_locks and diagnostic["status"] == "stale":
                removed = _unlink_jsonl_lock(lock_path)
                repaired.append(
                    {
                        "action": "remove_stale_lock",
                        "path": path_ref,
                        "removed": removed,
                        "status": diagnostic["status"],
                    }
                )
                if removed:
                    continue
                issue["repair_attempted"] = True
                issue["repair_removed"] = False
            issues.append(issue)
        for temp_path in sorted(root.rglob(".*")):
            if not temp_path.is_file():
                continue
            name = temp_path.name
            if name in {MAIL_GITIGNORE_NAME, ".gitkeep"} or name.endswith(".lock"):
                continue
            if "json" not in name:
                continue
            try:
                temp_age_seconds: float | None = max(0.0, time.time() - temp_path.stat().st_mtime)
            except OSError:
                temp_age_seconds = None
            temp_record = {
                "path": _relative_path_ref(hub_root, temp_path),
                "age_seconds": round(temp_age_seconds, 3)
                if temp_age_seconds is not None
                else None,
            }
            if "jsonl" not in name:
                observations.append(
                    {
                        "observation_type": "metadata_atomic_temp_fragment",
                        **temp_record,
                        "filename": name,
                        "meaning": (
                            "This is an interrupted JSON metadata write, not a live mail "
                            "JSONL stream. It is mailbox hygiene evidence but does not block "
                            "collect, route, or deliver."
                        ),
                    }
                )
                continue
            issue = {
                "issue_type": "atomic_temp_fragment",
                **temp_record,
                "recommendation": (
                    "Inspect before deleting; temp fragments usually indicate an interrupted "
                    "atomic write or concurrent mailbox update."
                ),
            }
            if (
                repair_temp_fragments
                and temp_age_seconds is not None
                and temp_age_seconds > stale_lock_seconds
            ):
                removed = False
                try:
                    temp_path.unlink()
                    removed = True
                except OSError:
                    removed = False
                repaired.append(
                    {
                        "action": "remove_stale_atomic_temp_fragment",
                        "path": _relative_path_ref(hub_root, temp_path),
                        "removed": removed,
                        "age_seconds": round(temp_age_seconds, 3),
                    }
                )
                if removed:
                    continue
                observations.append(
                    {
                        "observation_type": "atomic_temp_fragment_tombstone",
                        **temp_record,
                        "repair_attempted": True,
                        "repair_removed": False,
                        "meaning": (
                            "This stale atomic JSONL temp fragment could not be removed by "
                            "the explicit repair lane. Treat it as mailbox hygiene evidence, "
                            "not a live mail stream or delivery authority; review local file "
                            "permissions or sync locks if it persists."
                        ),
                    }
                )
                continue
            issues.append(issue)

    duplicate_identities: dict[str, list[dict[str, str]]] = {}
    malformed_count = 0
    oversized_count = 0
    direct_central_count = 0
    direct_repo_inbox_count = 0
    missing_collection_audit_count = 0
    legacy_collection_audit_gap_count = 0
    missing_collection_provenance_count = 0
    central_inbox_duplicate_logical_identity_count = 0
    repo_inbox_delivery_hash_mismatch_count = 0
    repo_inbox_legacy_delivery_log_count = 0
    repo_inbox_legacy_delivery_allowlist_count = 0
    source_outbox_duplicate_identity_count = 0
    cross_source_outbox_duplicate_identity_count = 0
    unknown_source_outbox_duplicate_identity_count = 0
    source_outbox_unstable_count = 0
    invalid_mail_packet_count = 0
    invalid_mail_packet_quarantine_count = 0
    central_inbox_logical_identities: dict[str, list[dict[str, str]]] = {}
    collection_audit_keys = _collection_audit_index(hub_root)
    legacy_collection_allowlist_keys = _legacy_collection_allowlist_index(hub_root)
    legacy_delivery_allowlist_keys = _legacy_delivery_allowlist_index(hub_root)
    invalid_mail_quarantine_keys = _invalid_mail_quarantine_index(hub_root)
    collection_audit_enforced_at = _parse_iso_datetime(COLLECTION_AUDIT_ENFORCED_AT)
    route_rows = _route_log_rows(hub_root, quarantine_errors=False)
    central_inbox_hashes = _central_inbox_record_hashes(hub_root, quarantine_errors=False)
    delivery_log_path = hub_root / CENTRAL_MAIL_DIR / "archive" / "delivery_log.jsonl"
    delivery_log_rows, _ = _read_jsonl_with_errors(delivery_log_path)
    unexpected_repo_mail_jsonl_count = 0
    central_outbox_missing_route_audit_count = 0
    central_outbox_route_hash_mismatch_count = 0
    central_outbox_missing_source_inbox_count = 0
    central_outbox_unrouted_count = 0
    for path in sorted(set(jsonl_paths)):
        if _is_unexpected_repo_mail_jsonl(path):
            unexpected_repo_mail_jsonl_count += 1
            try:
                file_hash = f"sha256:{sha256_bytes(path.read_bytes())}"
            except OSError:
                file_hash = ""
            observations.append(
                {
                    "observation_type": "unexpected_repo_mail_jsonl",
                    "path": _relative_path_ref(hub_root, path),
                    "filename": path.name,
                    "file_hash": file_hash,
                    "meaning": (
                        "Only inbox.jsonl, outbox.jsonl, archive.jsonl, and adoption.jsonl "
                        "are live repo mailbox streams. Backup or repair JSONL files should "
                        "be moved outside .digital-asset/mail or renamed without a .jsonl "
                        "extension so they do not look like mailbox streams."
                    ),
                }
            )
            continue
        stage = _mail_path_stage(hub_root, path)
        if stage == "repo_mirror_outbox":
            try:
                records, parse_errors, _source_signature = _read_stable_jsonl_snapshot(path)
            except MailOutboxUnstableError as exc:
                source_outbox_unstable_count += 1
                issues.append(
                    {
                        "issue_type": "source_outbox_unstable",
                        "path": _relative_path_ref(hub_root, path),
                        "error": str(exc),
                        "recommendation": (
                            "Do not collect from a source outbox while it is changing; retry "
                            "after the repo agent finishes writing."
                        ),
                    }
                )
                continue
        else:
            records, parse_errors = _read_jsonl_with_errors(path)
        for error in parse_errors:
            malformed_count += 1
            issues.append(
                {
                    "issue_type": "malformed_jsonl",
                    "path": _relative_path_ref(hub_root, path),
                    "line": error.get("line"),
                    "error": error.get("error", ""),
                    "raw_sha256": error.get("raw_sha256", ""),
                }
            )
        try:
            lines = path.read_bytes().splitlines()
        except OSError:
            lines = []
        for line_number, line in enumerate(lines, start=1):
            if len(line) > MAX_MAIL_RECORD_BYTES:
                oversized_count += 1
                issues.append(
                    {
                        "issue_type": "oversized_jsonl_record",
                        "path": _relative_path_ref(hub_root, path),
                        "line": line_number,
                        "bytes": len(line),
                        "max_bytes": MAX_MAIL_RECORD_BYTES,
                    }
                )
        seen_in_file: dict[str, int] = {}
        for record in records:
            identity = _mail_packet_identity(record)
            if not identity:
                if stage in {
                    "repo_mirror_outbox",
                    "repo_mirror_inbox",
                    "central_inbox",
                    "central_outbox",
                }:
                    record_hash = _invalid_mail_record_hash(record)
                    path_ref = _relative_path_ref(hub_root, path)
                    if stage == "repo_mirror_outbox" and (
                        path_ref,
                        record_hash,
                    ) in invalid_mail_quarantine_keys:
                        invalid_mail_packet_quarantine_count += 1
                        observations.append(
                            {
                                "observation_type": "invalid_source_outbox_packet_quarantined",
                                "path": path_ref,
                                "stage": stage,
                                "mail_id": str(record.get("mail_id", ""))
                                if isinstance(record, dict)
                                else "",
                                "dedupe_key": str(record.get("dedupe_key", ""))
                                if isinstance(record, dict)
                                else "",
                                "record_hash": record_hash,
                                "quarantine": _relative_path_ref(
                                    hub_root,
                                    invalid_mail_quarantine_path(hub_root),
                                ),
                                "meaning": (
                                    "This source outbox row is still invalid mail, but its "
                                    "current path and hash have been quarantined without copying "
                                    "raw payload content. It should be fixed or replayed by the "
                                    "source repo, not delivered as mail."
                                ),
                            }
                        )
                        continue
                    invalid_mail_packet_count += 1
                    issues.append(
                        {
                            "issue_type": "invalid_mail_packet",
                            "path": path_ref,
                            "stage": stage,
                            "mail_id": str(record.get("mail_id", ""))
                            if isinstance(record, dict)
                            else "",
                            "dedupe_key": str(record.get("dedupe_key", ""))
                            if isinstance(record, dict)
                            else "",
                            "record_hash": record_hash,
                            "recommendation": (
                                "Treat valid JSON rows that fail the mail packet schema as "
                                "untrusted. Quarantine by metadata/hash and replay through "
                                "the source repo outbox after review."
                            ),
                        }
                    )
                continue
            seen_in_file[identity] = seen_in_file.get(identity, 0) + 1
            duplicate_identities.setdefault(identity, []).append(
                {
                    "path": _relative_path_ref(hub_root, path),
                    "stage": stage,
                    "source_policy_key": "",
                }
            )
            if stage == "repo_mirror_outbox":
                source_repo_root = _repo_root_for_mail_mirror_path(path)
                source_policy = (
                    _policy_for_repo(source_repo_root, repo_policies)
                    if source_repo_root is not None
                    else None
                )
                source_repo_id = str(getattr(source_policy, "id", "") if source_policy else "")
                duplicate_identities[identity][-1]["source_policy_key"] = (
                    f"repo:{source_repo_id}" if source_repo_id else ""
                )
            if stage == "repo_mirror_inbox":
                repo_root = _repo_root_for_mail_mirror_path(path)
                mail_id = str(record.get("mail_id", ""))
                delivery_statuses = (
                    [
                        _delivery_log_match_status_for_repo_inbox(
                            row,
                            hub_root=hub_root,
                            repo=repo_root,
                            record=record,
                            repo_policies=repo_policies,
                        )
                        for row in delivery_log_rows
                    ]
                    if repo_root is not None
                    else []
                )
                delivery_logged = any(
                    status in {"verified", "hash_mismatch"} for status in delivery_statuses
                )
                expected_target_repo = (
                    _safe_repo_ref(str(repo_root), repo_policies) if repo_root is not None else ""
                )
                legacy_delivery_key = (
                    mail_id,
                    str(record.get("dedupe_key", "")),
                    _mail_record_hash(record),
                    expected_target_repo,
                )
                legacy_allowlisted = (
                    "legacy_unhashed" in delivery_statuses
                    and "verified" not in delivery_statuses
                    and legacy_delivery_key in legacy_delivery_allowlist_keys
                )
                if legacy_allowlisted:
                    delivery_logged = True
                    repo_inbox_legacy_delivery_allowlist_count += 1
                    observations.append(
                        {
                            "observation_type": "reviewed_legacy_repo_inbox_delivery_allowlisted",
                            "path": _relative_path_ref(hub_root, path),
                            "mail_id": mail_id,
                            "dedupe_key": str(record.get("dedupe_key", "")),
                            "record_hash": _mail_record_hash(record),
                            "target_repo": expected_target_repo,
                            "legacy_allowlist": _relative_path_ref(
                                hub_root,
                                legacy_delivery_allowlist_path(hub_root),
                            ),
                            "meaning": (
                                "This inbox row has only pre-hash delivery-log evidence, but "
                                "the current row hash and target repo were explicitly reviewed "
                                "in the legacy delivery allowlist. It remains candidate mail, "
                                "not adoption or public-release proof."
                            ),
                        }
                    )
                if "hash_mismatch" in delivery_statuses and "verified" not in delivery_statuses:
                    repo_inbox_delivery_hash_mismatch_count += 1
                    issues.append(
                        {
                            "issue_type": "repo_inbox_delivery_hash_mismatch",
                            "path": _relative_path_ref(hub_root, path),
                            "mail_id": mail_id,
                            "dedupe_key": str(record.get("dedupe_key", "")),
                            "expected_record_hash": _mail_record_hash(record),
                            "expected_target_repo": expected_target_repo,
                            "recommendation": (
                                "A delivery log exists for this mail_id/target, but its dedupe key "
                                "or delivered-row hash does not match the current repo inbox row."
                            ),
                        }
                    )
                if (
                    "legacy_unhashed" in delivery_statuses
                    and "verified" not in delivery_statuses
                    and not legacy_allowlisted
                ):
                    repo_inbox_legacy_delivery_log_count += 1
                    observations.append(
                        {
                            "observation_type": "repo_inbox_legacy_unhashed_delivery_log",
                            "path": _relative_path_ref(hub_root, path),
                            "mail_id": mail_id,
                            "meaning": (
                                "This inbox row has a pre-hash delivery log. It is legacy "
                                "context only, not proof that the current row was delivered "
                                "unchanged."
                            ),
                        }
                    )
            else:
                delivery_logged = True
            if stage == "central_outbox":
                try:
                    central_outbox_record = MailMessageRecord(**record)
                except ValidationError as exc:
                    central_outbox_missing_route_audit_count += 1
                    issues.append(
                        {
                            "issue_type": "central_outbox_missing_route_audit",
                            "path": _relative_path_ref(hub_root, path),
                            "mail_id": str(record.get("mail_id", "")),
                            "error": str(exc),
                            "recommendation": (
                                "Central outbox rows should be produced by DAD route from "
                                "collected central inbox rows and carry matching route audit."
                            ),
                        }
                    )
                    central_outbox_record = None
                if central_outbox_record is not None:
                    if central_outbox_record.review_status != "routed_candidate":
                        central_outbox_unrouted_count += 1
                        issues.append(
                            {
                                "issue_type": "central_outbox_unrouted_row",
                                "path": _relative_path_ref(hub_root, path),
                                "mail_id": central_outbox_record.mail_id,
                                "review_status": central_outbox_record.review_status,
                                "recommendation": (
                                    "DAD route should write central outbox candidates with "
                                    "review_status=routed_candidate."
                                ),
                            }
                        )
                    route_status, route_row = _route_audit_match_status(
                        central_outbox_record,
                        route_rows=route_rows,
                        central_inbox_hashes=central_inbox_hashes,
                    )
                    if route_status == "missing_route_audit":
                        central_outbox_missing_route_audit_count += 1
                        issues.append(
                            {
                                "issue_type": "central_outbox_missing_route_audit",
                                "path": _relative_path_ref(hub_root, path),
                                "mail_id": central_outbox_record.mail_id,
                                "dedupe_key": central_outbox_record.dedupe_key,
                                "record_hash": _mail_record_hash(central_outbox_record),
                                "audit_log": _relative_path_ref(hub_root, _route_log_path(hub_root)),
                                "recommendation": (
                                    "Rerun DAD route from collected central inbox rows or quarantine "
                                    "this direct central outbox row before delivery."
                                ),
                            }
                        )
                    elif route_status == "route_hash_mismatch":
                        central_outbox_route_hash_mismatch_count += 1
                        issues.append(
                            {
                                "issue_type": "central_outbox_route_hash_mismatch",
                                "path": _relative_path_ref(hub_root, path),
                                "mail_id": central_outbox_record.mail_id,
                                "dedupe_key": central_outbox_record.dedupe_key,
                                "record_hash": _mail_record_hash(central_outbox_record),
                                "audit_log": _relative_path_ref(hub_root, _route_log_path(hub_root)),
                                "recommendation": (
                                    "A route audit exists for this identity but not this row hash. "
                                    "Treat the central outbox row as mutated or stale until rerouted."
                                ),
                            }
                        )
                    elif route_status == "missing_source_inbox":
                        central_outbox_missing_source_inbox_count += 1
                        issues.append(
                            {
                                "issue_type": "central_outbox_missing_source_inbox",
                                "path": _relative_path_ref(hub_root, path),
                                "mail_id": central_outbox_record.mail_id,
                                "dedupe_key": central_outbox_record.dedupe_key,
                                "route_audit_id": str(route_row.get("route_audit_id", ""))
                                if route_row
                                else "",
                                "recommendation": (
                                    "The route audit no longer points to an existing collected "
                                    "central inbox record hash; reroute from current central inbox "
                                    "or quarantine the stale routed row."
                                ),
                            }
                        )
            if stage == "repo_mirror_inbox" and not delivery_logged:
                direct_repo_inbox_count += 1
                issues.append(
                    {
                        "issue_type": "repo_inbox_without_delivery_log",
                        "path": _relative_path_ref(hub_root, path),
                        "mail_id": str(record.get("mail_id", "")),
                        "dedupe_key": str(record.get("dedupe_key", "")),
                        "record_hash": _mail_record_hash(record),
                        "message_type": str(record.get("message_type", "")),
                        "review_status": str(record.get("review_status", "")),
                        "expected_target_repo": expected_target_repo,
                        "legacy_delivery_log_present": "legacy_unhashed" in delivery_statuses,
                        "legacy_allowlist": _relative_path_ref(
                            hub_root,
                            legacy_delivery_allowlist_path(hub_root),
                        ),
                        "recommendation": (
                            "Repo inbox rows should be written by DAD delivery and backed by a "
                            "processed/mail/archive/delivery_log.jsonl delivered event for the "
                            "same target repo. Pre-enforcement legacy delivery rows may be "
                            "reviewed into the legacy delivery allowlist only when keyed by "
                            "mail_id, dedupe_key, current row hash, and target repo."
                        ),
                    }
                )
            in_central_inbox = _path_is_relative_to(path, hub_root / CENTRAL_MAIL_DIR / "inbox")
            if in_central_inbox and str(record.get("review_status", "")) != "collected_candidate":
                direct_central_count += 1
                issues.append(
                    {
                        "issue_type": "central_inbox_uncollected_row",
                        "path": _relative_path_ref(hub_root, path),
                        "mail_id": str(record.get("mail_id", "")),
                        "review_status": str(record.get("review_status", "")),
                        "recommendation": (
                            "Repo agents should write to their own .digital-asset/mail/outbox.jsonl; "
                            "DAD collect writes processed/mail/inbox/*.jsonl."
                        ),
                    }
                )
            elif in_central_inbox:
                try:
                    central_mail_record = MailMessageRecord(**record)
                except ValidationError:
                    central_mail_record = None
                if central_mail_record is not None:
                    central_logical_identity = _collection_logical_identity(central_mail_record)
                    central_inbox_logical_identities.setdefault(
                        central_logical_identity, []
                    ).append(
                        {
                            "path": _relative_path_ref(hub_root, path),
                            "mail_id": str(record.get("mail_id", "")),
                            "dedupe_key": str(record.get("dedupe_key", "")),
                            "record_hash": _mail_record_hash(record),
                        }
                    )
                source_provenance = record.get("source_provenance")
                if not isinstance(source_provenance, dict):
                    source_provenance = {}
                collected_at_text = str(source_provenance.get("collected_at", ""))
                collected_at = _parse_iso_datetime(collected_at_text)
                if collected_at is None:
                    missing_collection_provenance_count += 1
                    issues.append(
                        {
                            "issue_type": "central_inbox_missing_collection_provenance",
                            "path": _relative_path_ref(hub_root, path),
                            "mail_id": str(record.get("mail_id", "")),
                            "recommendation": (
                                "Central inbox rows should be produced by DAD collect and carry "
                                "source_provenance.collected_at."
                            ),
                        }
                    )
                elif collection_audit_enforced_at and collected_at >= collection_audit_enforced_at:
                    record_hash = _mail_record_hash(record)
                    audit_key = (
                        str(record.get("mail_id", "")),
                        str(record.get("dedupe_key", "")),
                        record_hash,
                    )
                    if audit_key not in collection_audit_keys:
                        missing_collection_audit_count += 1
                        issues.append(
                            {
                                "issue_type": "central_inbox_missing_collection_audit",
                                "path": _relative_path_ref(hub_root, path),
                                "mail_id": str(record.get("mail_id", "")),
                                "dedupe_key": str(record.get("dedupe_key", "")),
                                "record_hash": record_hash,
                                "audit_log": _relative_path_ref(
                                    hub_root,
                                    _collection_log_path(hub_root),
                                ),
                                "recommendation": (
                                    "Fresh central inbox rows need a matching collection audit row. "
                                    "Repo agents should write to repo outboxes; DAD collect creates "
                                    "the central inbox row and audit hash."
                                ),
                            }
                        )
                else:
                    record_hash = _mail_record_hash(record)
                    audit_key = (
                        str(record.get("mail_id", "")),
                        str(record.get("dedupe_key", "")),
                        record_hash,
                    )
                    if (
                        audit_key not in collection_audit_keys
                        and audit_key not in legacy_collection_allowlist_keys
                    ):
                        legacy_collection_audit_gap_count += 1
                        issues.append(
                            {
                                "issue_type": "central_inbox_missing_collection_audit",
                                "path": _relative_path_ref(hub_root, path),
                                "mail_id": str(record.get("mail_id", "")),
                                "dedupe_key": str(record.get("dedupe_key", "")),
                                "record_hash": record_hash,
                                "collected_at": collected_at_text,
                                "audit_log": _relative_path_ref(
                                    hub_root,
                                    _collection_log_path(hub_root),
                                ),
                                "legacy_allowlist": _relative_path_ref(
                                    hub_root,
                                    _legacy_collection_allowlist_path(hub_root),
                                ),
                                "recommendation": (
                                    "Backdated central inbox rows are not trusted from packet "
                                    "contents alone. Add a reviewed legacy allowlist row keyed by "
                                    "mail_id, dedupe_key, and record_hash, or re-collect from the "
                                    "source repo outbox."
                                ),
                            }
                        )
                    elif audit_key in legacy_collection_allowlist_keys:
                        legacy_collection_audit_gap_count += 1
                        observations.append(
                            {
                                "observation_type": "reviewed_legacy_central_inbox_without_collection_audit",
                                "path": _relative_path_ref(hub_root, path),
                                "mail_id": str(record.get("mail_id", "")),
                                "dedupe_key": str(record.get("dedupe_key", "")),
                                "record_hash": record_hash,
                                "collected_at": collected_at_text,
                                "meaning": (
                                    "This central inbox row predates collection-audit enforcement "
                                    "and is explicitly reviewed in the legacy allowlist. It remains "
                                    "candidate evidence, not adoption or delivery proof."
                                ),
                            }
                        )
        for identity, count in seen_in_file.items():
            if count > 1:
                if stage == "repo_mirror_outbox":
                    source_outbox_duplicate_identity_count += 1
                    observations.append(
                        {
                            "observation_type": "source_outbox_duplicate_identity",
                            "path": _relative_path_ref(hub_root, path),
                            "identity": identity,
                            "count": count,
                            "meaning": (
                                "Repeated source outbox rows are expected during mail storms or "
                                "agent retries. DAD collect should canonicalize one row and "
                                "record duplicate_seen audit evidence instead of blocking."
                            ),
                        }
                    )
                else:
                    issues.append(
                        {
                            "issue_type": "duplicate_jsonl_identity",
                            "path": _relative_path_ref(hub_root, path),
                            "identity": identity,
                            "count": count,
                        }
                    )

    for identity, entries in sorted(central_inbox_logical_identities.items()):
        if len(entries) <= 1:
            continue
        central_inbox_duplicate_logical_identity_count += 1
        issues.append(
            {
                "issue_type": "central_inbox_duplicate_logical_identity",
                "logical_identity": identity,
                "rows": entries[:10],
                "row_count": len(entries),
                "recommendation": (
                    "Multiple central inbox rows share one logical original mail identity. "
                    "This can happen after concurrent collection races; review and retain one "
                    "canonical collected candidate with the matching collection audit."
                ),
            }
        )

    cross_file_duplicates = {
        identity: sorted(
            {entry["path"] for entry in entries},
        )
        for identity, entries in duplicate_identities.items()
        if len({entry["path"] for entry in entries}) > 1
    }
    for identity, paths in cross_file_duplicates.items():
        stage_counts: dict[str, int] = {}
        for entry in duplicate_identities[identity]:
            if entry["path"] in paths:
                stage = entry["stage"]
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
        duplicate_stages = {stage for stage, count in stage_counts.items() if count > 1}
        if duplicate_stages == {"repo_mirror_outbox"}:
            source_entries = [
                entry
                for entry in duplicate_identities[identity]
                if entry["path"] in paths and entry["stage"] == "repo_mirror_outbox"
            ]
            source_policy_keys = sorted(
                {
                    entry.get("source_policy_key", "")
                    for entry in source_entries
                    if entry.get("source_policy_key")
                }
            )
            if len(source_policy_keys) > 1:
                cross_source_outbox_duplicate_identity_count += 1
                issues.append(
                    {
                        "issue_type": "cross_source_outbox_duplicate_identity",
                        "identity": identity,
                        "paths": paths[:10],
                        "path_count": len(paths),
                        "stage_counts": stage_counts,
                        "source_policy_keys": source_policy_keys,
                        "recommendation": (
                            "The same source-outbox packet identity appears under more than one "
                            "reviewed repo ID. This may be a copied worktree, wrong outbox, or "
                            "provenance spoof; review before collection."
                        ),
                    }
                )
                continue
            if len(source_policy_keys) != 1 or any(
                not entry.get("source_policy_key") for entry in source_entries
            ):
                unknown_source_outbox_duplicate_identity_count += 1
                issues.append(
                    {
                        "issue_type": "unknown_source_outbox_duplicate_identity",
                        "identity": identity,
                        "paths": paths[:10],
                        "path_count": len(paths),
                        "stage_counts": stage_counts,
                        "source_policy_keys": source_policy_keys,
                        "recommendation": (
                            "The same source-outbox packet identity appears under multiple "
                            "outboxes, but DAD cannot prove one reviewed source repo ID owns "
                            "all copies. Treat as copied worktree or wrong-outbox provenance "
                            "until reviewed."
                        ),
                    }
                )
                continue
            source_outbox_duplicate_identity_count += 1
            observations.append(
                {
                    "observation_type": "source_outbox_cross_file_duplicate_identity",
                    "identity": identity,
                    "paths": paths[:10],
                    "path_count": len(paths),
                    "stage_counts": stage_counts,
                    "meaning": (
                        "The same source-outbox packet identity appears in more than one "
                        "repo outbox. This is a storm/backpressure observation; collection "
                        "canonicalizes source provenance from the owning outbox path."
                    ),
                }
            )
            continue
        if duplicate_stages:
            issues.append(
                {
                    "issue_type": "cross_file_same_stage_duplicate_identity",
                    "identity": identity,
                    "paths": paths[:10],
                    "path_count": len(paths),
                    "stage_counts": stage_counts,
                    "recommendation": (
                        "Duplicate packet identities in the same lifecycle stage can indicate "
                        "concurrent collection, repeated route output, or mailbox spam."
                    ),
                }
            )
            continue
        observations.append(
            {
                "observation_type": "mail_packet_lifecycle_identity",
                "identity": identity,
                "paths": paths[:10],
                "path_count": len(paths),
                "stage_counts": stage_counts,
                "meaning": (
                    "The same packet identity appears across different lifecycle stages. "
                    "That is normal audit trail evidence unless the same stage repeats."
                ),
            }
        )

    rust_invalid_count = 0
    rust_duplicate_identities: dict[str, list[dict[str, str]]] = {}
    rust_semantic_identities: dict[str, list[dict[str, str]]] = {}
    for path in sorted(set(rust_packet_paths)):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = MailMessageRecord(**payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            rust_invalid_count += 1
            issues.append(
                {
                    "issue_type": "rust_rollout_packet_invalid",
                    "path": _relative_path_ref(hub_root, path),
                    "error": str(exc),
                }
            )
            continue
        identity = _dedupe_identity(record.model_dump(mode="json"))
        path_ref = _relative_path_ref(hub_root, path)
        path_class = _rust_rollout_path_class(hub_root, path)
        rust_duplicate_identities.setdefault(identity, []).append(
            {
                "path": path_ref,
                "path_class": path_class,
            }
        )
        semantic_identity = _rust_rollout_semantic_identity(record)
        if semantic_identity:
            rust_semantic_identities.setdefault(semantic_identity, []).append(
                {
                    "path": path_ref,
                    "path_class": path_class,
                    "identity": identity,
                    "semantic_content_hash": _rust_rollout_semantic_content_hash(record),
                    "revision_id": str(
                        payload.get("rust_rollout_revision_id")
                        or record.payload.get("rust_rollout_revision_id")
                        or ""
                    ),
                }
            )
        payload_dict = record.payload
        if payload_dict.get("delivery_status") != "staged_not_deliverable":
            issues.append(
                {
                    "issue_type": "rust_rollout_packet_delivery_status",
                    "path": _relative_path_ref(hub_root, path),
                    "delivery_status": payload_dict.get("delivery_status"),
                }
            )
        if payload_dict.get("external_send_performed") or payload_dict.get("github_write_performed"):
            issues.append(
                {
                    "issue_type": "rust_rollout_packet_write_claim",
                    "path": _relative_path_ref(hub_root, path),
                    "external_send_performed": payload_dict.get("external_send_performed"),
                    "github_write_performed": payload_dict.get("github_write_performed"),
                }
            )
    for identity, entries in rust_duplicate_identities.items():
        if len(entries) > 1:
            path_classes = sorted({entry["path_class"] for entry in entries})
            paths = [entry["path"] for entry in entries]
            if path_classes == ["ignored_staging", "tracked_reference_snapshot"]:
                observations.append(
                    {
                        "observation_type": "rust_rollout_staged_reference_same_identity",
                        "identity": identity,
                        "paths": paths,
                        "path_count": len(paths),
                        "meaning": (
                            "The ignored staging packet and tracked reference snapshot "
                            "share the same Rust rollout identity. This is not delivered "
                            "mail and is safe when semantic identities also match."
                        ),
                    }
                )
                continue
            issues.append(
                {
                    "issue_type": "rust_rollout_duplicate_packet_identity",
                    "identity": identity,
                    "paths": paths,
                    "path_count": len(paths),
                    "path_classes": path_classes,
                }
            )
    for semantic_identity, entries in rust_semantic_identities.items():
        identities = sorted({entry["identity"] for entry in entries})
        if len(identities) <= 1:
            continue
        path_classes = sorted({entry["path_class"] for entry in entries})
        revision_ids = sorted({entry["revision_id"] for entry in entries if entry["revision_id"]})
        semantic_content_hashes = sorted(
            {entry["semantic_content_hash"] for entry in entries}
        )
        class_counts = {
            path_class: sum(1 for entry in entries if entry["path_class"] == path_class)
            for path_class in path_classes
        }
        if (
            path_classes == ["ignored_staging", "tracked_reference_snapshot"]
            and class_counts == {"ignored_staging": 1, "tracked_reference_snapshot": 1}
            and len(revision_ids) <= 1
            and len(semantic_content_hashes) <= 1
        ):
            observations.append(
                {
                    "observation_type": "rust_rollout_staged_reference_semantic_pair",
                    "semantic_identity": semantic_identity,
                    "identities": identities,
                    "paths": [entry["path"] for entry in entries],
                    "path_classes": path_classes,
                    "revision_ids": revision_ids,
                    "semantic_content_hashes": semantic_content_hashes,
                    "path_count": len(entries),
                    "meaning": (
                        "One ignored staging packet and one tracked reference snapshot "
                        "describe the same Rust rollout target. This is normal comparison "
                        "evidence when there is no revision or stable-content disagreement, "
                        "and it is not delivered mail."
                    ),
                }
            )
            continue
        issues.append(
            {
                "issue_type": "rust_rollout_semantic_identity_conflict",
                "semantic_identity": semantic_identity,
                "identities": identities,
                "paths": [entry["path"] for entry in entries],
                "path_classes": path_classes,
                "revision_ids": revision_ids,
                "semantic_content_hashes": semantic_content_hashes,
                "path_count": len(entries),
                "recommendation": (
                    "Only one active Rust rollout packet identity should describe a given "
                    "source, target, thread, packet type, and rollout mode. Regenerate "
                    "ignored staging, then deliberately promote or retire the tracked "
                    "reference snapshot."
                ),
            }
        )

    lock_issue_count = sum(1 for issue in issues if issue["issue_type"] == "jsonl_lock")
    temp_fragment_count = sum(
        1 for issue in issues if issue["issue_type"] == "atomic_temp_fragment"
    )
    active_lock_count = sum(
        1 for issue in issues if issue["issue_type"] == "jsonl_lock" and issue.get("status") == "active"
    )
    stale_repairable_lock_count = sum(
        1
        for issue in issues
        if issue["issue_type"] == "jsonl_lock"
        and issue.get("status") in {"stale", "dead_owner", "same_process_leftover"}
    )
    stale_repairable_temp_fragment_count = sum(
        1
        for issue in issues
        if issue["issue_type"] == "atomic_temp_fragment"
        and isinstance(issue.get("age_seconds"), int | float)
        and float(issue["age_seconds"]) > stale_lock_seconds
    )
    lock_tombstone_observation_count = sum(
        1
        for observation in observations
        if observation.get("observation_type") == "jsonl_lock_tombstone"
    )
    summary = {
        "root_count": len([root for root in roots if root.exists()]),
        "jsonl_file_count": len(set(jsonl_paths)),
        "rust_packet_count": len(set(rust_packet_paths)),
        "issue_count": len(issues),
        "lock_issue_count": lock_issue_count,
        "temp_fragment_count": temp_fragment_count,
        "active_lock_count": active_lock_count,
        "stale_repairable_lock_count": stale_repairable_lock_count,
        "lock_tombstone_observation_count": lock_tombstone_observation_count,
        "stale_repairable_temp_fragment_count": stale_repairable_temp_fragment_count,
        "malformed_jsonl_count": malformed_count,
        "oversized_record_count": oversized_count,
        "central_inbox_uncollected_count": direct_central_count,
        "repo_inbox_without_delivery_log_count": direct_repo_inbox_count,
        "central_inbox_missing_collection_audit_count": missing_collection_audit_count,
        "central_inbox_missing_collection_provenance_count": missing_collection_provenance_count,
        "central_inbox_duplicate_logical_identity_count": (
            central_inbox_duplicate_logical_identity_count
        ),
        "central_outbox_missing_route_audit_count": central_outbox_missing_route_audit_count,
        "central_outbox_route_hash_mismatch_count": central_outbox_route_hash_mismatch_count,
        "central_outbox_missing_source_inbox_count": central_outbox_missing_source_inbox_count,
        "central_outbox_unrouted_count": central_outbox_unrouted_count,
        "repo_inbox_delivery_hash_mismatch_count": repo_inbox_delivery_hash_mismatch_count,
        "repo_inbox_legacy_delivery_log_count": repo_inbox_legacy_delivery_log_count,
        "repo_inbox_legacy_delivery_allowlist_count": repo_inbox_legacy_delivery_allowlist_count,
        "legacy_collection_audit_gap_count": legacy_collection_audit_gap_count,
        "source_outbox_duplicate_identity_count": source_outbox_duplicate_identity_count,
        "cross_source_outbox_duplicate_identity_count": cross_source_outbox_duplicate_identity_count,
        "unknown_source_outbox_duplicate_identity_count": (
            unknown_source_outbox_duplicate_identity_count
        ),
        "source_outbox_unstable_count": source_outbox_unstable_count,
        "invalid_mail_packet_count": invalid_mail_packet_count,
        "invalid_mail_packet_quarantine_count": invalid_mail_packet_quarantine_count,
        "rust_invalid_packet_count": rust_invalid_count,
        "unexpected_repo_mail_jsonl_count": unexpected_repo_mail_jsonl_count,
        "lifecycle_observation_count": len(observations),
        "repaired_count": len(repaired),
    }
    action_summary = _mail_dirty_action_summary(
        issues=issues,
        summary=summary,
        repaired=repaired,
    )
    dirty = bool(issues)
    worktree_state = _git_worktree_dirty_state(hub_root)
    repo_scope = {
        "schema_version": "dad_mail_dirty_repo_scope.v1",
        "hub_local_spools_checked": True,
        "included_repo_count": len(repos or []),
        "external_repo_mailboxes_checked": bool(repos),
        "warning": ""
        if repos
        else (
            "Hub-local doctor scope only. Pass --repo all or explicit --repo values to "
            "inspect reviewed external repo outboxes/inboxes during a mail storm."
        ),
    }
    return {
        "schema_version": "dad_mail_dirty_state.v1",
        "generated_at": utc_now(),
        "status": action_summary["status"],
        "dirty": dirty,
        "spool_dirty": dirty,
        "worktree_dirty": bool(worktree_state.get("is_dirty")),
        "worktree_dirty_does_not_change_mail_dirty": True,
        "authority_boundary": (
            "Mail dirty-state diagnostics inspect append-only DAD mail spools and Rust rollout "
            "instruction packets. They do not collect, route, deliver, review, or promote mail. "
            "Repo agents should write candidate messages to their own .digital-asset/mail/outbox.jsonl."
        ),
        "write_target_guidance": {
            "repo_agents_write": ".digital-asset/mail/outbox.jsonl",
            "dad_collects_to": "processed/mail/inbox/*.jsonl",
            "dad_routes_to": "processed/mail/outbox/routed.jsonl",
            "dad_delivers_to": ".digital-asset/mail/inbox.jsonl",
            "rust_rollout_packets": (
                "processed/mail/staged/rust_rollout/**/*.json are generated ignored "
                "staging packets; mail/outbox/rust_rollout/**/*.json is the tracked "
                "reference snapshot. Neither is delivered inbox mail."
            ),
        },
        "summary": summary,
        "repo_scope": repo_scope,
        "action_summary": action_summary,
        "worktree_state": worktree_state,
        "issues": issues,
        "observations": observations,
        "repaired": repaired,
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
    return {
        "report_markdown": (REPORTS_DIR / "mail_center.md").as_posix(),
        "report_json": (REPORTS_DIR / "mail_center.json").as_posix(),
    }
