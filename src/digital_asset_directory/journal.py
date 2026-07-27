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
from concurrent.futures import ThreadPoolExecutor
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
RESTORE_DRILL_STATUS_NAME = "restore_drill_status.json"
DEFAULT_JOURNAL_REPO_DIRNAME = "dad-journal"
REMOTE_OUTBOX_QUARANTINE_NAME = "remote-outbox-quarantine.jsonl"
VCS_CONTROL_DIR_NAMES = {".git", ".hg", ".svn"}
CHECKPOINT_COPY_ATTEMPTS = 10
CHECKPOINT_COPY_CHUNK_SIZE = 1024 * 1024
SQLITE_CHECKPOINT_SUFFIXES = {".sqlite", ".sqlite3"}
SQLITE_SIDECAR_SUFFIXES = {".sqlite-wal", ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm"}
CHECKPOINT_FILE_INDEX_VERSION = "1.0.0"
JOURNAL_ENGINE_VERSION = "1.3.0"
JOURNAL_ENGINE_CAPABILITIES = [
    "verified_incremental_file_index",
    "no_checkout_git_index_transaction",
    "exact_staged_path_reconciliation",
    "byte_preserving_git_staging",
    "safe_remote_descendant_recovery",
    "content_addressed_graph_manifests",
    "bounded_parallel_integrity_verification",
    "compact_transport_readiness_summary",
    "forced_staging_immune_to_embedded_ignores",
    "tracked_aware_reuse_gate",
]
JOURNAL_INTEGRITY_MAX_WORKERS = 4


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


def _checkpoint_manifest_structure_valid(manifest: Any) -> bool:
    if not isinstance(manifest, dict):
        return False
    if manifest.get("schema_version") != "dad.journal.checkpoint.v1":
        return False
    if manifest.get("checkpoint_scope") != "DATA_PLANE_PATHS":
        return False
    raw_index = manifest.get("file_index")
    if not isinstance(raw_index, dict):
        return False
    return not raw_index or bool(_validated_checkpoint_file_index(manifest))


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
    checkpoint_repo: Path,
    manifest: Any,
    *,
    max_workers: int | None = None,
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
    sorted_entries = [(relative_text, file_index[relative_text]) for relative_text in sorted(indexed_paths)]
    worker_count = max_workers
    if worker_count is None:
        worker_count = min(JOURNAL_INTEGRITY_MAX_WORKERS, max(1, os.cpu_count() or 1))
    worker_count = max(1, worker_count)

    def verify_entry(item: tuple[str, dict[str, Any]]) -> dict[str, str] | None:
        relative_text, entry = item
        path = checkpoint_repo / "data" / relative_text
        try:
            actual_hash = f"sha256:{sha256_file(path)}"
            actual_size = path.stat().st_size
        except OSError as exc:
            return {"relative_path": relative_text, "error": type(exc).__name__}
        if actual_hash != entry["checkpoint_sha256"] or actual_size != entry["checkpoint_size"]:
            return {"relative_path": relative_text, "error": "hash_or_size_mismatch"}
        return None

    def verify_serially() -> list[dict[str, str] | None]:
        return [verify_entry(item) for item in sorted_entries]

    if worker_count == 1:
        verification_rows = verify_serially()
        backend = "python_serial"
    else:
        try:
            executor = ThreadPoolExecutor(max_workers=worker_count)
        except (OSError, RuntimeError):
            verification_rows = verify_serially()
            worker_count = 1
            backend = "python_serial_executor_fallback"
        else:
            try:
                futures = [executor.submit(verify_entry, item) for item in sorted_entries]
            except (OSError, RuntimeError):
                executor.shutdown(wait=True, cancel_futures=True)
                verification_rows = verify_serially()
                worker_count = 1
                backend = "python_serial_executor_fallback"
            else:
                try:
                    verification_rows = [future.result() for future in futures]
                finally:
                    executor.shutdown(wait=True)
                backend = "python_thread_pool"
    errors = [row for row in verification_rows if row is not None]
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
        "verification_backend": backend,
        "verification_worker_count": worker_count,
    }


def _build_checkpoint_snapshot(
    hub_root: Path,
    checkpoint_repo: Path,
    status: dict[str, Any],
    *,
    baseline_checkpoint_repo: Path | None = None,
    tracked_paths: set[str] | None = None,
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
        # A baseline working file that is not tracked in HEAD must be re-copied
        # and staged, or an index/commit divergence survives forever.
        tracked_in_head = (
            tracked_paths is None or f"data/{relative_text}" in tracked_paths
        )
        if tracked_in_head and _can_reuse_checkpoint_file(
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
    tracked_result = _run_git_readonly(checkpoint_worktree, ["ls-files", "-z"])
    if tracked_result["returncode"] != 0:
        raise RuntimeError(
            f"Unable to list tracked journal paths: {tracked_result['stderr']}"
        )
    tracked_paths = {item for item in tracked_result["stdout"].split("\0") if item}
    expected_staged: set[str] = set()
    for relative_text in normalized:
        candidate = checkpoint_worktree / Path(relative_text)
        baseline = baseline_checkpoint_repo / Path(relative_text)
        if relative_text not in tracked_paths:
            # Untracked in HEAD: any present file is a new staging, regardless
            # of whether an identical stray copy sits in the baseline worktree.
            if candidate.is_file():
                expected_staged.add(relative_text)
            continue
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
            # Data may legitimately contain .gitignore files; ignore rules that
            # arrived as data must never drop indexed checkpoint paths.
            "--force",
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
        f'git -C "{journal_repo}" config core.autocrlf false',
        f'git -C "{journal_repo}" add --force data journal_checkpoint_manifest.json',
        f'git -C "{journal_repo}" commit -m "Checkpoint DAD data root"',
        f'git -C "{journal_repo}" push origin {branch}',
    ]


def _checkpoint_command_args(journal_repo: Path, branch: str) -> list[list[str]]:
    return [
        ["git", "-C", str(journal_repo), "config", "core.longpaths", "true"],
        ["git", "-C", str(journal_repo), "config", "core.autocrlf", "false"],
        [
            "git",
            "-C",
            str(journal_repo),
            "add",
            "--force",
            "data",
            "journal_checkpoint_manifest.json",
        ],
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
    manifest_schema_ok = manifest_result["status"] == "readable" and (
        _checkpoint_manifest_structure_valid(manifest)
    )
    manifest_engine_version = str(manifest.get("journal_engine_version") or "")
    engine_version_current = manifest_engine_version == JOURNAL_ENGINE_VERSION
    file_index_integrity = _checkpoint_file_index_integrity(journal_repo, manifest)
    manifest_record_count = _int_or_zero(manifest.get("record_count"))
    checkpoint_current_for_threshold = (
        manifest_schema_ok
        and engine_version_current
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
        and engine_version_current
    )
    if not is_git_repo:
        repo_status = "not_git_repository"
    elif not checkpoint_present:
        repo_status = "checkpoint_missing_or_invalid"
    elif not engine_version_current:
        repo_status = "checkpoint_engine_version_stale"
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
        "journal_engine_version_seen": manifest_engine_version,
        "journal_engine_version_expected": JOURNAL_ENGINE_VERSION,
        "journal_engine_version_current": engine_version_current,
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
    if journal_repo is not None:
        manifest_result = _read_checkpoint_manifest(journal_repo.resolve())
        manifest = manifest_result.get("manifest", {})
        manifest_structure_valid = _checkpoint_manifest_structure_valid(manifest)
        manifest_recovery_due = manifest_result.get("status") == "invalid" or (
            manifest_result.get("status") == "readable" and not manifest_structure_valid
        )
        engine_upgrade_due = (
            isinstance(manifest, dict)
            and bool(manifest)
            and manifest.get("journal_engine_version") != JOURNAL_ENGINE_VERSION
        )
        status["journal_manifest_status"] = manifest_result.get("status")
        status["journal_manifest_structure_valid"] = manifest_structure_valid
        status["journal_manifest_recovery_due"] = manifest_recovery_due
        status["journal_engine_upgrade_due"] = engine_upgrade_due
        if manifest_recovery_due:
            status["checkpoint_due"] = True
            status["checkpoint_due_reason"] = "journal_manifest_recovery"
        elif engine_upgrade_due:
            status["checkpoint_due"] = True
            status["checkpoint_due_reason"] = "journal_engine_upgrade"
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
            # Pin byte-preserving checkouts locally so a system-level
            # autocrlf=true can never CRLF-convert synced or restored data.
            status["git_apply_results"].append(
                _run_git_write(
                    ["git", "-C", str(journal_repo), "config", "core.autocrlf", "false"]
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
                    tracked_result = _run_git_readonly(
                        checkpoint_worktree, ["ls-files", "-z"]
                    )
                    if tracked_result["returncode"] != 0:
                        raise RuntimeError(
                            "Unable to list tracked journal paths: "
                            + tracked_result["stderr"]
                        )
                    tracked_paths = {
                        item
                        for item in tracked_result["stdout"].split("\0")
                        if item
                    }
                    snapshot = _build_checkpoint_snapshot(
                        hub_root,
                        checkpoint_worktree,
                        status,
                        baseline_checkpoint_repo=journal_repo,
                        tracked_paths=tracked_paths,
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


def default_journal_repo() -> Path | None:
    """Return the conventional user-level journal repo when it exists locally."""

    candidate = Path.home() / ".dad" / DEFAULT_JOURNAL_REPO_DIRNAME
    if (candidate / ".git").exists():
        return candidate
    return None


def _restore_drill_status_path(hub_root: Path) -> Path:
    return _reports_dir(hub_root) / RESTORE_DRILL_STATUS_NAME


def restore_drill_status(hub_root: Path) -> dict[str, Any]:
    """Read the last restore-drill report, or a never_run placeholder."""

    path = _restore_drill_status_path(hub_root)
    if not path.is_file():
        return {"status": "never_run", "report_path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid", "report_path": str(path)}
    if not isinstance(payload, dict):
        return {"status": "invalid", "report_path": str(path)}
    return payload


def restore_drill(
    hub_root: Path,
    journal_repo: Path | None,
    *,
    scratch_root: Path | None = None,
    keep: bool = False,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Materialize the committed checkpoint into scratch and prove it restores intact.

    Proves: the committed checkpoint is complete against its file index, every
    restored file matches its recorded sha256/size, and restored SQLite files
    open and pass integrity_check. Does not prove the checkpoint is fresh (that
    is journal status) or that a network clone from the remote works.
    """

    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_version": "dad.journal.restore_drill.v1",
        "generated_at": utc_now(),
        "status": "blocked",
        "duration_methodology": "wall_seconds_time_perf_counter_single_run",
        "proves": [
            "committed_checkpoint_complete_against_file_index",
            "restored_files_match_recorded_sha256_and_size",
            "restored_sqlite_files_open_and_pass_integrity_check",
        ],
        "does_not_prove": [
            "checkpoint_freshness_see_journal_status",
            "remote_clone_from_origin_works",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }

    def _finish(payload: dict[str, Any]) -> dict[str, Any]:
        payload["duration_seconds"] = round(time.perf_counter() - started, 3)
        payload["report_path"] = str(_restore_drill_status_path(hub_root))
        atomic_write_text(
            _restore_drill_status_path(hub_root), json_dumps(payload, pretty=True) + "\n"
        )
        return payload

    if journal_repo is None:
        report["blocked_reason"] = "journal_repo_not_configured"
        report["narrative"] = [
            "No backup journal repository was named, so nothing could be restored.",
        ]
        return _finish(report)
    journal_repo = journal_repo.resolve()
    report["journal_repo"] = str(journal_repo)
    if not (journal_repo / ".git").exists():
        report["blocked_reason"] = "journal_repo_not_a_git_repository"
        report["narrative"] = [
            f"{journal_repo} is not a Git repository, so no checkpoint history exists there.",
        ]
        return _finish(report)
    head = _run_git_readonly(journal_repo, ["rev-parse", "HEAD"])
    if head["returncode"] != 0:
        report["blocked_reason"] = "journal_repo_has_no_commits"
        report["narrative"] = [
            "The backup journal has no committed checkpoint yet; run a checkpoint first.",
        ]
        return _finish(report)
    checkpoint_head = head["stdout"]
    report["checkpoint_head"] = checkpoint_head

    scratch_base = (scratch_root or (Path.home() / ".dad" / "tmp")).resolve()
    drill_dir = (
        scratch_base
        / "restore-drill"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    restored_worktree = drill_dir / "restored"
    drill_dir.mkdir(parents=True, exist_ok=True)
    report["restored_path"] = str(restored_worktree)
    report["kept"] = keep

    materialize = _run_git_readonly(
        journal_repo,
        [
            # Byte-preserving checkout: system-level autocrlf=true would CRLF-
            # convert LF blobs and break hash verification (and a real disaster
            # recovery); the journal stores exact bytes, never text.
            "-c",
            "core.autocrlf=false",
            "-c",
            f"core.attributesFile={os.devnull}",
            "worktree",
            "add",
            "--detach",
            "--force",
            str(restored_worktree),
            checkpoint_head,
        ],
    )
    if materialize["returncode"] != 0:
        report["blocked_reason"] = "worktree_materialization_failed"
        report["git_error"] = materialize["stderr"]
        report["narrative"] = [
            "Git could not materialize the checkpoint into a scratch folder.",
        ]
        shutil.rmtree(drill_dir, ignore_errors=True)
        return _finish(report)

    try:
        manifest_result = _read_checkpoint_manifest(restored_worktree)
        manifest = manifest_result.get("manifest", {})
        if manifest_result.get(
            "status"
        ) != "readable" or not _checkpoint_manifest_structure_valid(manifest):
            report["blocked_reason"] = "checkpoint_manifest_invalid"
            report["narrative"] = [
                "The restored checkpoint manifest is missing or malformed; the backup "
                "cannot be trusted as-is.",
            ]
            return _finish(report)
        report["checkpointed_at"] = str(manifest.get("checkpointed_at") or "")

        integrity = _checkpoint_file_index_integrity(
            restored_worktree, manifest, max_workers=max_workers
        )
        report["integrity"] = integrity

        file_index = _validated_checkpoint_file_index(manifest)
        restored_bytes = sum(entry["checkpoint_size"] for entry in file_index.values())
        report["file_count"] = len(file_index)
        report["restored_bytes"] = restored_bytes

        sqlite_checks: list[dict[str, str]] = []
        for relative_text in sorted(file_index):
            if Path(relative_text).suffix.lower() not in SQLITE_CHECKPOINT_SUFFIXES:
                continue
            restored_db = restored_worktree / "data" / relative_text
            row: dict[str, str] = {"relative_path": relative_text}
            try:
                source_uri = restored_db.resolve().as_uri() + "?mode=ro"
                with closing(sqlite3.connect(source_uri, uri=True, timeout=5.0)) as db:
                    outcome = db.execute("PRAGMA integrity_check").fetchone()
                row["status"] = (
                    "ok"
                    if outcome and str(outcome[0]).lower() == "ok"
                    else "integrity_check_failed"
                )
            except (OSError, sqlite3.Error) as exc:
                row["status"] = "open_failed"
                row["error"] = type(exc).__name__
            sqlite_checks.append(row)
        report["sqlite_checks"] = sqlite_checks

        sqlite_ok = all(row["status"] == "ok" for row in sqlite_checks)
        verified = bool(integrity.get("valid")) and sqlite_ok
        report["status"] = "verified" if verified else "failed"
        report.pop("blocked_reason", None)

        megabytes = restored_bytes / (1024 * 1024)
        narrative = [
            f"Restored {len(file_index)} files ({megabytes:.1f} MB) from the backup "
            "journal into a scratch folder.",
        ]
        if integrity.get("valid"):
            narrative.append("Every restored file matched its recorded fingerprint.")
        else:
            narrative.append(
                "Some restored files did NOT match the recorded fingerprints; "
                "this backup cannot be fully trusted."
            )
        if sqlite_checks:
            narrative.append(
                "Restored database files opened and passed their integrity check."
                if sqlite_ok
                else "A restored database file failed its integrity check."
            )
        if report["checkpointed_at"]:
            narrative.append(f"This backup was taken at {report['checkpointed_at']}.")
        report["narrative"] = narrative
        return _finish(report)
    finally:
        if not keep:
            _run_git_readonly(
                journal_repo, ["worktree", "remove", "--force", str(restored_worktree)]
            )
            _run_git_readonly(journal_repo, ["worktree", "prune"])
            shutil.rmtree(drill_dir, ignore_errors=True)


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
