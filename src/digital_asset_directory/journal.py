"""Data-plane journal checkpoint and remote-outbox ingest helpers.

The journal is a private data-only replication log for DAD_DATA_ROOT. These
helpers keep git explicit: checkpoint commands are emitted for review by
default, and any local write stays inside the hub data root or the named journal
repo.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graph_surfaces import (
    GRAPH_SNAPSHOT_ROOT,
    graph_surface_checkpoint_plan,
    write_graph_surface_checkpoint_artifacts,
)
from .mail_center import collect_mail_payloads
from .transport import (
    AUTHORITY_BOUNDARY,
    DATA_PLANE_FILE_SURFACES,
    DATA_PLANE_PATHS,
    data_path,
    resolve_data_root,
)
from .utils import (
    append_jsonl,
    atomic_write_text,
    json_dumps,
    sha256_bytes,
    sha256_file,
    utc_now,
)

JOURNAL_STATUS_NAME = "journal_checkpoint_status.json"
REMOTE_OUTBOX_QUARANTINE_NAME = "remote-outbox-quarantine.jsonl"
VCS_CONTROL_DIR_NAMES = {".git", ".hg", ".svn"}
CHECKPOINT_COPY_ATTEMPTS = 10
CHECKPOINT_COPY_CHUNK_SIZE = 1024 * 1024
SQLITE_CHECKPOINT_SUFFIXES = {".sqlite", ".sqlite3"}
SQLITE_SIDECAR_SUFFIXES = {".sqlite-wal", ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm"}
CHECKPOINT_FILE_INDEX_VERSION = "1.0.0"
JOURNAL_ENGINE_VERSION = "1.1.0"
JOURNAL_ENGINE_CAPABILITIES = [
    "verified_incremental_file_index",
    "no_checkout_git_index_transaction",
    "exact_staged_path_reconciliation",
    "byte_preserving_git_staging",
    "safe_remote_descendant_recovery",
    "content_addressed_graph_manifests",
]


def _reports_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports")


def _journal_status_path(hub_root: Path) -> Path:
    return _reports_dir(hub_root) / JOURNAL_STATUS_NAME


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iter_data_plane_files(hub_root: Path) -> list[tuple[Path, Path]]:
    files: list[tuple[Path, Path]] = []
    for logical, relative_root in sorted(DATA_PLANE_PATHS.items()):
        surface_root = data_path(hub_root, logical)
        if not surface_root.exists():
            continue
        if surface_root.is_file():
            if not surface_root.is_symlink():
                files.append((surface_root, Path(relative_root)))
            continue
        for source in sorted(path for path in surface_root.rglob("*") if path.is_file()):
            relative = source.relative_to(surface_root)
            if (
                source.is_symlink()
                or any(part.lower() in VCS_CONTROL_DIR_NAMES for part in relative.parts)
                or any(source.name.lower().endswith(suffix) for suffix in SQLITE_SIDECAR_SUFFIXES)
            ):
                continue
            files.append((source, Path(relative_root) / relative))
    return files


def _copy_checkpoint_file_once(source: Path, destination: Path) -> None:
    """Copy one live data-plane file through an atomic destination temp file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.checkpoint.",
        dir=str(destination.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        if source.suffix.lower() in SQLITE_CHECKPOINT_SUFFIXES:
            source_uri = source.resolve().as_uri() + "?mode=ro"
            with closing(
                sqlite3.connect(source_uri, uri=True, timeout=5.0)
            ) as source_db:
                with closing(sqlite3.connect(temp_path, timeout=5.0)) as target_db:
                    source_db.backup(target_db)
                    integrity = target_db.execute("PRAGMA integrity_check").fetchone()
                    if not integrity or str(integrity[0]).lower() != "ok":
                        raise OSError("SQLite checkpoint failed integrity_check")
        else:
            with source.open("rb") as source_handle, temp_path.open("wb") as target_handle:
                shutil.copyfileobj(
                    source_handle,
                    target_handle,
                    length=CHECKPOINT_COPY_CHUNK_SIZE,
                )
                target_handle.flush()
                os.fsync(target_handle.fileno())
            try:
                shutil.copystat(source, temp_path)
            except OSError:
                pass
        os.replace(temp_path, destination)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _copy_checkpoint_file(source: Path, destination: Path) -> None:
    last_error: OSError | None = None
    for attempt in range(CHECKPOINT_COPY_ATTEMPTS):
        try:
            _copy_checkpoint_file_once(source, destination)
            return
        except OSError as exc:
            last_error = exc
            if attempt == CHECKPOINT_COPY_ATTEMPTS - 1:
                break
            time.sleep(0.05 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise OSError(f"Checkpoint copy failed without an error: {source.name}")


def _checkpoint_source_fingerprint(source: Path) -> dict[str, int]:
    stat = source.stat()
    return {
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
    }


def _checkpoint_file_entry(source: Path, destination: Path) -> dict[str, Any]:
    fingerprint = _checkpoint_source_fingerprint(source)
    destination_stat = destination.stat()
    return {
        **fingerprint,
        "checkpoint_size": destination_stat.st_size,
        "checkpoint_sha256": f"sha256:{sha256_file(destination)}",
    }


def _copy_and_index_checkpoint_file(source: Path, destination: Path) -> dict[str, Any]:
    for _attempt in range(CHECKPOINT_COPY_ATTEMPTS):
        before = _checkpoint_source_fingerprint(source)
        _copy_checkpoint_file(source, destination)
        after = _checkpoint_source_fingerprint(source)
        if source.suffix.lower() in SQLITE_CHECKPOINT_SUFFIXES or before == after:
            return _checkpoint_file_entry(source, destination)
    raise OSError(f"Checkpoint source changed during every copy attempt: {source.name}")


def _can_reuse_checkpoint_file(
    source: Path,
    destination: Path,
    previous: Any,
    *,
    journal_worktree_clean: bool,
) -> bool:
    if not journal_worktree_clean or source.suffix.lower() in SQLITE_CHECKPOINT_SUFFIXES:
        return False
    if not isinstance(previous, dict) or not destination.is_file():
        return False
    try:
        fingerprint = _checkpoint_source_fingerprint(source)
        destination_size = destination.stat().st_size
        expected_hash = str(previous.get("checkpoint_sha256") or "")
        source_hash_before = f"sha256:{sha256_file(source)}"
        destination_hash = f"sha256:{sha256_file(destination)}"
        source_hash_after = f"sha256:{sha256_file(source)}"
        final_fingerprint = _checkpoint_source_fingerprint(source)
    except OSError:
        return False
    return (
        previous.get("source_size") == fingerprint["source_size"]
        and previous.get("source_mtime_ns") == fingerprint["source_mtime_ns"]
        and final_fingerprint == fingerprint
        and previous.get("checkpoint_size") == destination_size
        and expected_hash.startswith("sha256:")
        and source_hash_before == expected_hash
        and source_hash_after == expected_hash
        and destination_hash == expected_hash
    )


def _remove_empty_checkpoint_dirs(data_root: Path, paths: list[Path]) -> None:
    parents = {
        parent
        for path in paths
        for parent in path.parents
        if parent != data_root and data_root in parent.parents
    }
    for parent in sorted(parents, key=lambda item: len(item.parts), reverse=True):
        try:
            parent.rmdir()
        except OSError:
            pass


def _validated_checkpoint_file_index(manifest: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict):
        return {}
    if manifest.get("file_index_version") != CHECKPOINT_FILE_INDEX_VERSION:
        return {}
    raw_index = manifest.get("file_index")
    if not isinstance(raw_index, dict):
        return {}
    validated: dict[str, dict[str, Any]] = {}
    for relative_text, entry in raw_index.items():
        if not isinstance(relative_text, str) or not isinstance(entry, dict):
            return {}
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != relative_text:
            return {}
        if not isinstance(entry.get("source_size"), int):
            return {}
        if not isinstance(entry.get("source_mtime_ns"), int):
            return {}
        if not isinstance(entry.get("checkpoint_size"), int):
            return {}
        checkpoint_hash = entry.get("checkpoint_sha256")
        if not isinstance(checkpoint_hash, str) or not checkpoint_hash.startswith("sha256:"):
            return {}
        validated[relative_text] = dict(entry)
    return validated


def _managed_checkpoint_relative_paths(checkpoint_repo: Path) -> set[str]:
    data_root = checkpoint_repo / "data"
    managed: set[str] = set()
    for logical, relative_root in DATA_PLANE_PATHS.items():
        candidate = data_root / relative_root
        if logical in DATA_PLANE_FILE_SURFACES:
            if candidate.is_file():
                managed.add(Path(relative_root).as_posix())
            continue
        if not candidate.is_dir():
            continue
        for path in candidate.rglob("*"):
            if path.is_file() and not path.is_symlink():
                managed.add(path.relative_to(data_root).as_posix())
    return managed


def _checkpoint_file_index_integrity(
    checkpoint_repo: Path, manifest: Any
) -> dict[str, Any]:
    file_index = _validated_checkpoint_file_index(manifest)
    actual_paths = _managed_checkpoint_relative_paths(checkpoint_repo)
    if not file_index:
        return {
            "valid": False,
            "reason": "missing_or_invalid_file_index",
            "indexed_file_count": 0,
            "actual_managed_file_count": len(actual_paths),
            "errors": [],
        }
    indexed_paths = set(file_index)
    errors: list[dict[str, str]] = []
    for relative_text in sorted(indexed_paths):
        path = checkpoint_repo / "data" / relative_text
        entry = file_index[relative_text]
        try:
            actual_hash = f"sha256:{sha256_file(path)}"
            actual_size = path.stat().st_size
        except OSError as exc:
            errors.append({"relative_path": relative_text, "error": type(exc).__name__})
            continue
        if actual_hash != entry["checkpoint_sha256"] or actual_size != entry["checkpoint_size"]:
            errors.append({"relative_path": relative_text, "error": "hash_or_size_mismatch"})
    missing_from_index = sorted(actual_paths - indexed_paths)
    missing_from_data = sorted(indexed_paths - actual_paths)
    return {
        "valid": not errors and not missing_from_index and not missing_from_data,
        "reason": "ok" if not errors and not missing_from_index and not missing_from_data else "mismatch",
        "indexed_file_count": len(indexed_paths),
        "actual_managed_file_count": len(actual_paths),
        "missing_from_index": missing_from_index,
        "missing_from_data": missing_from_data,
        "errors": errors,
    }


def _build_checkpoint_snapshot(
    hub_root: Path,
    checkpoint_repo: Path,
    status: dict[str, Any],
    *,
    baseline_checkpoint_repo: Path | None = None,
) -> dict[str, Any]:
    baseline = baseline_checkpoint_repo or checkpoint_repo
    target = checkpoint_repo / "data"
    target.mkdir(parents=True, exist_ok=True)
    previous_manifest = _read_checkpoint_manifest(baseline).get("manifest", {})
    previous_file_index = _validated_checkpoint_file_index(previous_manifest)
    source_files = _iter_data_plane_files(hub_root)
    current_relative_paths = {relative.as_posix() for _source, relative in source_files}
    stale_relative_paths = sorted(
        _managed_checkpoint_relative_paths(baseline) - current_relative_paths
    )
    removed_relative_paths: list[str] = []
    copied_relative_paths: list[str] = []
    copied_files = 0
    unchanged_files = 0
    verified_files = 0
    file_index: dict[str, dict[str, Any]] = {}
    copy_errors: list[dict[str, Any]] = []
    for source, relative in source_files:
        destination = target / relative
        baseline_destination = baseline / "data" / relative
        relative_text = relative.as_posix()
        previous_entry = previous_file_index.get(relative_text)
        if _can_reuse_checkpoint_file(
            source,
            baseline_destination,
            previous_entry,
            journal_worktree_clean=True,
        ):
            file_index[relative_text] = dict(previous_entry)
            unchanged_files += 1
            verified_files += 1
            continue
        try:
            file_index[relative_text] = _copy_and_index_checkpoint_file(source, destination)
        except OSError as exc:
            copy_errors.append(
                {
                    "relative_path": relative_text,
                    "error_type": type(exc).__name__,
                    "winerror": getattr(exc, "winerror", None),
                    "errno": getattr(exc, "errno", None),
                }
            )
        else:
            copied_files += 1
            verified_files += 1
            copied_relative_paths.append(relative_text)
    if not copy_errors:
        for relative_text in stale_relative_paths:
            removed_relative_paths.append(relative_text)
    return {
        "copied_file_count": copied_files,
        "unchanged_file_count": unchanged_files,
        "verified_file_count": verified_files,
        "removed_file_count": len(removed_relative_paths),
        "copy_error_count": len(copy_errors),
        "copy_errors": copy_errors,
        "file_index": file_index,
        "copied_relative_paths": copied_relative_paths,
        "removed_relative_paths": removed_relative_paths,
        "previous_file_index_valid": bool(previous_file_index) or not previous_manifest,
    }


def _graph_checkpoint_stage_paths(plan: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    wrote_index = False
    for snapshot in plan.get("snapshots", []):
        if snapshot.get("status") != "ready":
            continue
        paths.add(str(snapshot["manifest_json_snapshot_path"]))
        if snapshot.get("body_upload_action") != "skip_unchanged":
            paths.add(str(snapshot["body_gzip_snapshot_path"]))
        wrote_index = True
    if wrote_index:
        paths.add(f"data/{GRAPH_SNAPSHOT_ROOT.as_posix()}/index.jsonl")
    return paths


def _stage_checkpoint_paths(
    checkpoint_worktree: Path,
    baseline_checkpoint_repo: Path,
    paths: set[str],
    pathspec_file: Path,
) -> dict[str, Any]:
    normalized = sorted(path.replace("\\", "/") for path in paths)
    attribute_directories = {Path(".")}
    for relative_text in normalized:
        parent = Path(relative_text).parent
        attribute_directories.update([parent, *parent.parents])
    for directory in attribute_directories:
        if (checkpoint_worktree / directory / ".gitattributes").exists() or (
            baseline_checkpoint_repo / directory / ".gitattributes"
        ).exists():
            raise RuntimeError(
                "Journal staging blocked because a path-relevant .gitattributes file exists."
            )
    expected_staged: set[str] = set()
    for relative_text in normalized:
        candidate = checkpoint_worktree / Path(relative_text)
        baseline = baseline_checkpoint_repo / Path(relative_text)
        if candidate.is_file() != baseline.is_file():
            expected_staged.add(relative_text)
            continue
        if candidate.is_file():
            if candidate.stat().st_size != baseline.stat().st_size:
                expected_staged.add(relative_text)
            elif sha256_file(candidate) != sha256_file(baseline):
                expected_staged.add(relative_text)
    pathspec_file.write_bytes(b"\0".join(path.encode("utf-8") for path in normalized) + b"\0")
    result = _run_git_write(
        [
            "git",
            "--literal-pathspecs",
            "-c",
            "core.autocrlf=false",
            "-c",
            f"core.attributesFile={os.devnull}",
            "-C",
            str(checkpoint_worktree),
            "add",
            "--all",
            f"--pathspec-from-file={pathspec_file}",
            "--pathspec-file-nul",
        ]
    )
    staged = _run_git_readonly(checkpoint_worktree, ["diff", "--cached", "--name-only", "-z"])
    if staged["returncode"] != 0:
        raise RuntimeError(f"Unable to inspect staged journal paths: {staged['stderr']}")
    staged_paths = {item for item in staged["stdout"].split("\0") if item}
    if staged_paths != expected_staged:
        raise RuntimeError(
            "Journal staged-path reconciliation failed: "
            f"expected={len(expected_staged)} actual={len(staged_paths)}"
        )
    result["staged_path_count"] = len(staged_paths)
    return result


def _journal_attributes_are_disabled(journal_repo: Path) -> bool:
    if (journal_repo / ".gitattributes").exists():
        return False
    attributes = _run_git_readonly(
        journal_repo,
        [
            "ls-files",
            "--cached",
            "-z",
            "--",
            ".gitattributes",
            ":(glob)**/.gitattributes",
        ],
    )
    if attributes["returncode"] != 0 or attributes["stdout"]:
        return False
    info_attributes = _run_git_readonly(
        journal_repo, ["rev-parse", "--git-path", "info/attributes"]
    )
    if info_attributes["returncode"] != 0:
        return False
    path = Path(info_attributes["stdout"])
    if not path.is_absolute():
        path = journal_repo / path
    try:
        return not path.exists() or path.stat().st_size == 0
    except OSError:
        return False


def _recover_safe_remote_descendant(
    journal_repo: Path,
    branch: str,
    results: list[dict[str, Any]],
) -> str:
    local = _run_git_readonly(journal_repo, ["rev-parse", "HEAD"])
    if local["returncode"] != 0:
        return ""
    remote = _run_git_readonly(
        journal_repo,
        ["ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"],
    )
    if remote["returncode"] == 2:
        return local["stdout"]
    if remote["returncode"] != 0:
        raise RuntimeError("Unable to inspect the remote journal branch for recovery.")
    return _sync_known_remote_checkpoint(
        journal_repo,
        branch,
        local["stdout"],
        results,
    )


def _jsonl_record_count(hub_root: Path) -> int:
    count = 0
    for path, _relative in _iter_data_plane_files(hub_root):
        if path.suffix != ".jsonl":
            continue
        try:
            count += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            continue
    return count


def _last_checkpoint_status(hub_root: Path) -> dict[str, Any]:
    path = _journal_status_path(hub_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def journal_status(hub_root: Path, *, min_records: int = 200, min_hours: int = 24) -> dict[str, Any]:
    data_root, mode = resolve_data_root(hub_root)
    current_record_count = _jsonl_record_count(hub_root)
    previous = _last_checkpoint_status(hub_root)
    last_count = int(previous.get("checkpoint_record_count") or 0)
    new_records = max(0, current_record_count - last_count)
    checkpointed_at = str(
        previous.get("checkpointed_at") or previous.get("last_checkpoint_at") or ""
    )
    pending_since = str(previous.get("pending_since") or previous.get("generated_at") or "")
    last_at = _parse_time(checkpointed_at) or _parse_time(pending_since)
    now = datetime.now(timezone.utc)
    hours_since = 0.0 if last_at is None else max(0.0, (now - last_at).total_seconds() / 3600.0)
    if not checkpointed_at and current_record_count > 0 and not pending_since:
        pending_since = now.isoformat()
    due = new_records >= min_records or hours_since >= min_hours
    return {
        "schema_version": "dad.journal.status.v1",
        "journal_engine_version": JOURNAL_ENGINE_VERSION,
        "journal_engine_capabilities": JOURNAL_ENGINE_CAPABILITIES,
        "generated_at": utc_now(),
        "data_root": str(data_root),
        "data_root_mode": mode,
        "checkpoint_scope": "DATA_PLANE_PATHS",
        "current_record_count": current_record_count,
        "checkpoint_record_count": last_count,
        "new_record_count": new_records,
        "checkpointed_at": checkpointed_at,
        "last_checkpoint_at": checkpointed_at,
        "pending_since": pending_since if not checkpointed_at and current_record_count > 0 else "",
        "hours_since_checkpoint": hours_since,
        "thresholds": {"min_records": min_records, "min_hours": min_hours},
        "checkpoint_due": due,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _current_journal_branch(journal_repo: Path) -> str | None:
    branch = _run_git_readonly(journal_repo, ["branch", "--show-current"])
    if branch["returncode"] != 0:
        return None
    current = branch["stdout"].strip()
    return current or None


def _checkpoint_commands(journal_repo: Path, branch: str) -> list[str]:
    return [
        f'git -C "{journal_repo}" config core.longpaths true',
        f'git -C "{journal_repo}" add data journal_checkpoint_manifest.json',
        f'git -C "{journal_repo}" commit -m "Checkpoint DAD data root"',
        f'git -C "{journal_repo}" push origin {branch}',
    ]


def _checkpoint_command_args(journal_repo: Path, branch: str) -> list[list[str]]:
    return [
        ["git", "-C", str(journal_repo), "config", "core.longpaths", "true"],
        ["git", "-C", str(journal_repo), "add", "data", "journal_checkpoint_manifest.json"],
        ["git", "-C", str(journal_repo), "commit", "-m", "Checkpoint DAD data root"],
        ["git", "-C", str(journal_repo), "push", "origin", branch],
    ]


def _run_git_write(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    record = {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        raise RuntimeError(
            "Journal git command failed: "
            + " ".join(command)
            + f"\nstdout: {record['stdout']}\nstderr: {record['stderr']}"
        )
    return record


def _run_git_readonly(journal_repo: Path, args: list[str]) -> dict[str, Any]:
    command = ["git", "-C", str(journal_repo), *args]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return {
            "command": command,
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _checkpoint_remote_diff_is_safe(
    journal_repo: Path, checkpoint_head: str, remote_head: str
) -> bool:
    ancestor = _run_git_readonly(
        journal_repo, ["merge-base", "--is-ancestor", checkpoint_head, remote_head]
    )
    if ancestor["returncode"] != 0:
        return False
    changed = _run_git_readonly(
        journal_repo, ["diff", "--name-only", checkpoint_head, remote_head]
    )
    if changed["returncode"] != 0:
        return False
    allowed_files = {"journal_checkpoint_manifest.json", "README.md"}
    return all(
        path in allowed_files
        or path.startswith("data/")
        or path.startswith("remote-outbox/")
        for path in changed["stdout"].splitlines()
        if path
    )


def _sync_known_remote_checkpoint(
    journal_repo: Path,
    branch: str,
    checkpoint_head: str,
    results: list[dict[str, Any]],
    *,
    max_attempts: int = 3,
) -> str:
    last_error = "remote branch kept moving"
    for _attempt in range(max_attempts):
        results.append(
            _run_git_write(
                ["git", "-C", str(journal_repo), "fetch", "origin", branch]
            )
        )
        remote = _run_git_readonly(journal_repo, ["rev-parse", f"origin/{branch}"])
        local = _run_git_readonly(journal_repo, ["rev-parse", "HEAD"])
        if remote["returncode"] != 0 or local["returncode"] != 0:
            raise RuntimeError("Unable to resolve local and remote checkpoint heads.")
        remote_head = remote["stdout"]
        if local["stdout"] == remote_head:
            return remote_head
        if not _checkpoint_remote_diff_is_safe(
            journal_repo, checkpoint_head, remote_head
        ):
            raise RuntimeError(
                "Remote journal head is not a safe descendant of the known checkpoint."
            )
        try:
            results.append(
                _run_git_write(
                    [
                        "git",
                        "-C",
                        str(journal_repo),
                        "merge",
                        "--ff-only",
                        remote_head,
                    ]
                )
            )
        except RuntimeError as exc:
            last_error = str(exc)
            continue
    raise RuntimeError(f"Could not synchronize known remote checkpoint: {last_error}")


def _read_checkpoint_manifest(journal_repo: Path) -> dict[str, Any]:
    path = journal_repo / "journal_checkpoint_manifest.json"
    if not path.exists():
        return {
            "path": str(path),
            "status": "missing",
            "manifest": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(path),
            "status": "invalid",
            "error": str(exc),
            "manifest": {},
        }
    if not isinstance(payload, dict):
        return {
            "path": str(path),
            "status": "invalid",
            "error": "manifest is not a JSON object",
            "manifest": {},
        }
    return {
        "path": str(path),
        "status": "readable",
        "manifest": payload,
    }


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def journal_repo_status(
    hub_root: Path,
    journal_repo: Path,
    *,
    min_records: int = 200,
    min_hours: int = 24,
) -> dict[str, Any]:
    """Read-only verification of a candidate dad-journal repository."""
    journal_repo = journal_repo.resolve()
    status = journal_status(hub_root, min_records=min_records, min_hours=min_hours)
    if not journal_repo.exists():
        return {
            "schema_version": "dad.journal.repo_status.v1",
            "generated_at": utc_now(),
            "journal_repo": str(journal_repo),
            "exists": False,
            "status": "missing",
            "git_repository": False,
            "checkpoint_manifest": {
                "path": str(journal_repo / "journal_checkpoint_manifest.json"),
                "status": "missing",
                "manifest": {},
            },
            "journal_status": status,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }

    git_inside = _run_git_readonly(journal_repo, ["rev-parse", "--is-inside-work-tree"])
    is_git_repo = git_inside["returncode"] == 0 and git_inside["stdout"] == "true"
    branch = _run_git_readonly(journal_repo, ["branch", "--show-current"])
    head = _run_git_readonly(journal_repo, ["rev-parse", "HEAD"])
    remote = _run_git_readonly(journal_repo, ["remote", "get-url", "origin"])
    worktree = _run_git_readonly(journal_repo, ["status", "--short"])
    manifest_result = _read_checkpoint_manifest(journal_repo)
    manifest = manifest_result["manifest"]
    top_level_entries = sorted(
        path.name for path in journal_repo.iterdir() if path.name != ".git"
    )
    allowed_top_level = {"data", "journal_checkpoint_manifest.json", "remote-outbox", "README.md"}
    unexpected_top_level = [
        name for name in top_level_entries if name not in allowed_top_level
    ]
    data_dir = journal_repo / "data"
    data_file_count = (
        len([path for path in data_dir.rglob("*") if path.is_file()])
        if data_dir.exists()
        else 0
    )
    manifest_schema_ok = (
        manifest_result["status"] == "readable"
        and manifest.get("schema_version") == "dad.journal.checkpoint.v1"
        and manifest.get("checkpoint_scope") == "DATA_PLANE_PATHS"
    )
    file_index_integrity = _checkpoint_file_index_integrity(journal_repo, manifest)
    manifest_record_count = _int_or_zero(manifest.get("record_count"))
    checkpoint_current_for_threshold = (
        manifest_schema_ok
        and file_index_integrity["valid"]
        and manifest_record_count >= _int_or_zero(status.get("checkpoint_record_count"))
        and not bool(status.get("checkpoint_due"))
    )
    checkpoint_present = (
        manifest_schema_ok and file_index_integrity["valid"] and data_file_count > 0
    )
    working_tree_clean = worktree["returncode"] == 0 and not worktree["stdout"]
    machine_ready = (
        is_git_repo
        and checkpoint_present
        and remote["returncode"] == 0
        and working_tree_clean
    )
    if not is_git_repo:
        repo_status = "not_git_repository"
    elif not checkpoint_present:
        repo_status = "checkpoint_missing_or_invalid"
    elif status.get("checkpoint_due"):
        repo_status = "checkpoint_present_but_due"
    elif unexpected_top_level:
        repo_status = "unexpected_non_data_entries"
    elif remote["returncode"] != 0:
        repo_status = "remote_missing"
    else:
        repo_status = "checkpoint_current_machine_condition_met"
    return {
        "schema_version": "dad.journal.repo_status.v1",
        "generated_at": utc_now(),
        "journal_repo": str(journal_repo),
        "exists": True,
        "status": repo_status,
        "git_repository": is_git_repo,
        "current_branch": branch["stdout"] if branch["returncode"] == 0 else "",
        "head": head["stdout"] if head["returncode"] == 0 else "",
        "origin_url": remote["stdout"] if remote["returncode"] == 0 else "",
        "origin_configured": remote["returncode"] == 0,
        "working_tree_clean": working_tree_clean,
        "working_tree_status": worktree["stdout"],
        "checkpoint_manifest": manifest_result,
        "file_index_integrity": file_index_integrity,
        "checkpoint_present": checkpoint_present,
        "checkpoint_current_for_threshold": checkpoint_current_for_threshold,
        "data_dir": str(data_dir),
        "data_dir_exists": data_dir.exists(),
        "data_file_count": data_file_count,
        "top_level_entries": top_level_entries,
        "unexpected_top_level_entries": unexpected_top_level,
        "machine_ready": machine_ready,
        "journal_status": status,
        "read_only_git_checks": {
            "is_inside_work_tree": git_inside,
            "branch": branch,
            "head": head,
            "origin": remote,
            "status_short": worktree,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def checkpoint_journal(
    hub_root: Path,
    journal_repo: Path | None,
    *,
    apply: bool = False,
    min_records: int = 200,
    min_hours: int = 24,
) -> dict[str, Any]:
    status = journal_status(hub_root, min_records=min_records, min_hours=min_hours)
    if not status["checkpoint_due"]:
        status["checkpoint_applied"] = False
        status["checkpoint_skipped_reason"] = "threshold_not_met"
        atomic_write_text(_journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n")
        return status
    if journal_repo is None:
        status["checkpoint_applied"] = False
        status["checkpoint_skipped_reason"] = "journal_repo_not_configured"
        status["commands"] = []
        status["graph_surfaces"] = graph_surface_checkpoint_plan(hub_root, None)
        atomic_write_text(_journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n")
        return status

    journal_repo = journal_repo.resolve()
    status["journal_repo"] = str(journal_repo)
    status["graph_surfaces"] = graph_surface_checkpoint_plan(hub_root, journal_repo)
    planned_branch = _current_journal_branch(journal_repo) or "<current-branch>"
    status["journal_branch"] = planned_branch
    status["commands"] = _checkpoint_commands(journal_repo, planned_branch)
    status["checkpoint_applied"] = False

    if not apply:
        status["checkpoint_skipped_reason"] = "plan_only"
        atomic_write_text(_journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n")
        return status

    if apply:
        current_branch = _current_journal_branch(journal_repo)
        if current_branch is None:
            raise ValueError("Refusing journal checkpoint apply: journal repo has no current branch.")
        status["journal_branch"] = current_branch
        status["commands"] = _checkpoint_commands(journal_repo, current_branch)
        status["git_apply_results"] = []
        worktree_status = _run_git_readonly(journal_repo, ["status", "--short"])
        if worktree_status["returncode"] != 0 or worktree_status["stdout"]:
            status.update(
                {
                    "status": "blocked",
                    "checkpoint_skipped_reason": "journal_worktree_not_clean",
                    "journal_worktree_status": worktree_status,
                }
            )
            atomic_write_text(
                _journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n"
            )
            return status

        if not _journal_attributes_are_disabled(journal_repo):
            status.update(
                {
                    "status": "blocked",
                    "checkpoint_skipped_reason": "journal_attributes_unsupported",
                    "git_byte_preservation": "blocked_by_repository_or_info_attributes",
                }
            )
            atomic_write_text(
                _journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n"
            )
            return status
        status["git_byte_preservation"] = (
            "repository_attributes_absent; global_attributes_disabled; autocrlf_disabled"
        )

        pending_remote_head = str(
            _last_checkpoint_status(hub_root).get("remote_checkpoint_head") or ""
        )
        if pending_remote_head:
            try:
                recovered_head = _sync_known_remote_checkpoint(
                    journal_repo,
                    current_branch,
                    pending_remote_head,
                    status["git_apply_results"],
                )
                status["recovered_remote_checkpoint_head"] = recovered_head
            except RuntimeError as exc:
                status.update(
                    {
                        "status": "blocked",
                        "checkpoint_skipped_reason": "remote_checkpoint_recovery_failed",
                        "git_transaction_error": str(exc),
                        "remote_checkpoint_head": pending_remote_head,
                    }
                )
                atomic_write_text(
                    _journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n"
                )
                return status
        try:
            recovered_head = _recover_safe_remote_descendant(
                journal_repo,
                current_branch,
                status["git_apply_results"],
            )
            status["synchronized_start_head"] = recovered_head
        except RuntimeError as exc:
            status.update(
                {
                    "status": "blocked",
                    "checkpoint_skipped_reason": "remote_descendant_recovery_failed",
                    "git_transaction_error": str(exc),
                }
            )
            atomic_write_text(
                _journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n"
            )
            return status
        try:
            status["git_apply_results"].append(
                _run_git_write(
                    ["git", "-C", str(journal_repo), "config", "core.longpaths", "true"]
                )
            )
            head = _run_git_readonly(journal_repo, ["rev-parse", "HEAD"])
            if head["returncode"] != 0:
                status["git_apply_results"].append(
                    _run_git_write(
                        [
                            "git",
                            "-C",
                            str(journal_repo),
                            "commit",
                            "--allow-empty",
                            "-m",
                            "Initialize DAD journal",
                        ]
                    )
                )

            with tempfile.TemporaryDirectory(prefix="dad-journal-checkpoint-") as temp_dir:
                checkpoint_worktree = Path(temp_dir) / "worktree"
                status["git_apply_results"].append(
                    _run_git_write(
                        [
                            "git",
                            "-C",
                            str(journal_repo),
                            "worktree",
                            "add",
                            "--detach",
                            "--no-checkout",
                            str(checkpoint_worktree),
                            "HEAD",
                        ]
                    )
                )
                try:
                    status["git_apply_results"].append(
                        _run_git_write(
                            ["git", "-C", str(checkpoint_worktree), "read-tree", "HEAD"]
                        )
                    )
                    snapshot = _build_checkpoint_snapshot(
                        hub_root,
                        checkpoint_worktree,
                        status,
                        baseline_checkpoint_repo=journal_repo,
                    )
                    status.update(
                        {
                            key: value
                            for key, value in snapshot.items()
                            if key != "file_index"
                        }
                    )
                    if snapshot["copy_errors"]:
                        status.update(
                            {
                                "status": "blocked",
                                "checkpoint_skipped_reason": "copy_incomplete",
                            }
                        )
                        atomic_write_text(
                            _journal_status_path(hub_root),
                            json_dumps(status, pretty=True) + "\n",
                        )
                        return status

                    graph_surfaces = write_graph_surface_checkpoint_artifacts(
                        hub_root,
                        checkpoint_worktree,
                        baseline_journal_repo=journal_repo,
                    )
                    status["graph_surfaces"] = graph_surfaces
                    manifest = {
                        "schema_version": "dad.journal.checkpoint.v1",
                        "journal_engine_version": JOURNAL_ENGINE_VERSION,
                        "journal_engine_capabilities": JOURNAL_ENGINE_CAPABILITIES,
                        "checkpointed_at": utc_now(),
                        "source_data_root": str(Path(str(status["data_root"]))),
                        "checkpoint_scope": "DATA_PLANE_PATHS",
                        "record_count": status["current_record_count"],
                        "copied_file_count": snapshot["copied_file_count"],
                        "unchanged_file_count": snapshot["unchanged_file_count"],
                        "verified_file_count": snapshot["verified_file_count"],
                        "removed_file_count": snapshot["removed_file_count"],
                        "file_index_version": CHECKPOINT_FILE_INDEX_VERSION,
                        "file_index": snapshot["file_index"],
                        "graph_surfaces": graph_surfaces,
                        "authority_boundary": AUTHORITY_BOUNDARY,
                    }
                    atomic_write_text(
                        checkpoint_worktree / "journal_checkpoint_manifest.json",
                        json_dumps(manifest, pretty=True) + "\n",
                    )
                    stage_paths = {
                        "journal_checkpoint_manifest.json",
                        *(f"data/{path}" for path in snapshot["copied_relative_paths"]),
                        *(f"data/{path}" for path in snapshot["removed_relative_paths"]),
                        *_graph_checkpoint_stage_paths(graph_surfaces),
                    }
                    status["git_apply_results"].append(
                        _stage_checkpoint_paths(
                            checkpoint_worktree,
                            journal_repo,
                            stage_paths,
                            Path(temp_dir) / "checkpoint-pathspec.bin",
                        )
                    )
                    transaction_commands = [
                        [
                            "git",
                            "-C",
                            str(checkpoint_worktree),
                            "commit",
                            "-m",
                            "Checkpoint DAD data root",
                        ],
                    ]
                    for command in transaction_commands:
                        status["git_apply_results"].append(_run_git_write(command))
                    checkpoint_head = _run_git_readonly(
                        checkpoint_worktree, ["rev-parse", "HEAD"]
                    )["stdout"]
                    status["git_apply_results"].append(
                        _run_git_write(
                            [
                                "git",
                                "-C",
                                str(checkpoint_worktree),
                                "push",
                                "origin",
                                f"HEAD:refs/heads/{current_branch}",
                            ]
                        )
                    )
                    status["remote_checkpoint_head"] = checkpoint_head
                    status["transaction_phase"] = "remote_push_complete_local_sync_pending"
                    atomic_write_text(
                        _journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n"
                    )
                    synchronized_head = _sync_known_remote_checkpoint(
                        journal_repo,
                        current_branch,
                        checkpoint_head,
                        status["git_apply_results"],
                    )
                    status["synchronized_remote_head"] = synchronized_head
                    status.pop("remote_checkpoint_head", None)
                    status.pop("transaction_phase", None)
                finally:
                    cleanup = _run_git_readonly(
                        journal_repo,
                        ["worktree", "remove", "--force", str(checkpoint_worktree)],
                    )
                    status["worktree_cleanup"] = cleanup
        except (OSError, RuntimeError) as exc:
            status.update(
                {
                    "status": "blocked",
                    "checkpoint_applied": False,
                    "checkpoint_skipped_reason": "git_transaction_failed",
                    "git_transaction_error": str(exc),
                }
            )
            atomic_write_text(
                _journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n"
            )
            return status
        status["checkpoint_applied"] = True

    checkpointed_at = utc_now()
    status["checkpointed_at"] = checkpointed_at
    status["last_checkpoint_at"] = checkpointed_at
    status["checkpoint_record_count"] = status["current_record_count"]
    status["new_record_count"] = 0
    status["hours_since_checkpoint"] = 0.0
    status["checkpoint_due"] = False
    atomic_write_text(_journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n")
    return status


def ingest_remote_outbox(hub_root: Path, journal_repo: Path) -> dict[str, Any]:
    remote_root = journal_repo / "remote-outbox"
    quarantine_path = data_path(hub_root, "central_mail") / "quarantine" / REMOTE_OUTBOX_QUARANTINE_NAME
    accepted = 0
    duplicates = 0
    quarantined = 0
    files_seen = 0
    errors: list[dict[str, Any]] = []
    collection_results: list[dict[str, Any]] = []
    if remote_root.exists():
        for source in sorted(remote_root.rglob("*.jsonl")):
            files_seen += 1
            try:
                lines = source.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                append_jsonl(
                    quarantine_path,
                    {
                        "event_type": "remote_outbox_unreadable",
                        "created_at": utc_now(),
                        "source": str(source),
                        "error": str(exc),
                    },
                )
                quarantined += 1
                continue
            payloads: list[Any] = []
            for line_number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    payloads.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    append_jsonl(
                        quarantine_path,
                        {
                            "event_type": "remote_outbox_invalid_row",
                            "created_at": utc_now(),
                            "source": str(source),
                            "line_number": line_number,
                            "error": str(exc),
                            "raw_sha256": sha256_bytes(line.encode("utf-8")),
                        },
                    )
                    quarantined += 1
                    continue
            if not payloads:
                continue
            result = collect_mail_payloads(
                hub_root,
                journal_repo,
                source,
                payloads,
                repo_policies=None,
            )
            collection_results.append(
                {
                    "source": str(source),
                    "collected_count": result["collected_count"],
                    "duplicate_count": result["duplicate_count"],
                    "quarantined_invalid_count": result["quarantined_invalid_count"],
                    "error_count": result["error_count"],
                }
            )
            accepted += int(result["collected_count"])
            duplicates += int(result["duplicate_count"])
            quarantined += int(result["quarantined_invalid_count"])
            errors.extend(result["errors"])
    return {
        "schema_version": "dad.journal.remote_outbox_ingest.v1",
        "generated_at": utc_now(),
        "journal_repo": str(journal_repo),
        "remote_outbox": str(remote_root),
        "files_seen": files_seen,
        "accepted_count": accepted,
        "duplicate_count": duplicates,
        "quarantined_count": quarantined,
        "quarantine_path": str(quarantine_path),
        "collection_results": collection_results,
        "error_count": len(errors),
        "errors": errors,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
