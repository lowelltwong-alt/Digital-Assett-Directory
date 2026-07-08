"""Data-plane journal checkpoint and remote-outbox ingest helpers.

The journal is a private data-only replication log for DAD_DATA_ROOT. These
helpers keep git explicit: checkpoint commands are emitted for review by
default, and any local write stays inside the hub data root or the named journal
repo.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graph_surfaces import (
    graph_surface_checkpoint_plan,
    write_graph_surface_checkpoint_artifacts,
)
from .mail_center import collect_mail_payloads
from .transport import AUTHORITY_BOUNDARY, DATA_PLANE_PATHS, data_path, resolve_data_root
from .utils import append_jsonl, atomic_write_text, json_dumps, sha256_bytes, utc_now

JOURNAL_STATUS_NAME = "journal_checkpoint_status.json"
REMOTE_OUTBOX_QUARANTINE_NAME = "remote-outbox-quarantine.jsonl"


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
        for source in sorted(path for path in surface_root.rglob("*") if path.is_file()):
            files.append((source, Path(relative_root) / source.relative_to(surface_root)))
    return files


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
    last_at = _parse_time(str(previous.get("checkpointed_at") or ""))
    now = datetime.now(timezone.utc)
    hours_since = 0.0 if last_at is None else max(0.0, (now - last_at).total_seconds() / 3600.0)
    due = new_records >= min_records or hours_since >= min_hours
    return {
        "schema_version": "dad.journal.status.v1",
        "generated_at": utc_now(),
        "data_root": str(data_root),
        "data_root_mode": mode,
        "checkpoint_scope": "DATA_PLANE_PATHS",
        "current_record_count": current_record_count,
        "checkpoint_record_count": last_count,
        "new_record_count": new_records,
        "last_checkpoint_at": previous.get("checkpointed_at", ""),
        "hours_since_checkpoint": hours_since,
        "thresholds": {"min_records": min_records, "min_hours": min_hours},
        "checkpoint_due": due,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _checkpoint_commands(journal_repo: Path) -> list[str]:
    return [
        f'git -C "{journal_repo}" add data journal_checkpoint_manifest.json',
        f'git -C "{journal_repo}" commit -m "Checkpoint DAD data root"',
        f'git -C "{journal_repo}" push origin main',
    ]


def _checkpoint_command_args(journal_repo: Path) -> list[list[str]]:
    return [
        ["git", "-C", str(journal_repo), "add", "data", "journal_checkpoint_manifest.json"],
        ["git", "-C", str(journal_repo), "commit", "-m", "Checkpoint DAD data root"],
        ["git", "-C", str(journal_repo), "push", "origin", "main"],
    ]


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
    manifest_record_count = _int_or_zero(manifest.get("record_count"))
    checkpoint_current_for_threshold = (
        manifest_schema_ok
        and manifest_record_count >= _int_or_zero(status.get("checkpoint_record_count"))
        and not bool(status.get("checkpoint_due"))
    )
    checkpoint_present = manifest_schema_ok and data_file_count > 0
    machine_ready = is_git_repo and checkpoint_present and remote["returncode"] == 0
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
        "working_tree_clean": worktree["returncode"] == 0 and not worktree["stdout"],
        "working_tree_status": worktree["stdout"],
        "checkpoint_manifest": manifest_result,
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
    status["commands"] = _checkpoint_commands(journal_repo)
    status["graph_surfaces"] = graph_surface_checkpoint_plan(hub_root, journal_repo)
    status["checkpoint_applied"] = False

    if not apply:
        status["checkpoint_skipped_reason"] = "plan_only"
        atomic_write_text(_journal_status_path(hub_root), json_dumps(status, pretty=True) + "\n")
        return status

    if apply:
        data_root = Path(str(status["data_root"]))
        target = journal_repo / "data"
        target.mkdir(parents=True, exist_ok=True)
        copied_files = 0
        for source, relative in _iter_data_plane_files(hub_root):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied_files += 1
        graph_surfaces = write_graph_surface_checkpoint_artifacts(hub_root, journal_repo)
        status["graph_surfaces"] = graph_surfaces
        manifest = {
            "schema_version": "dad.journal.checkpoint.v1",
            "checkpointed_at": utc_now(),
            "source_data_root": str(data_root),
            "checkpoint_scope": "DATA_PLANE_PATHS",
            "record_count": status["current_record_count"],
            "copied_file_count": copied_files,
            "graph_surfaces": graph_surfaces,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        atomic_write_text(
            journal_repo / "journal_checkpoint_manifest.json",
            json_dumps(manifest, pretty=True) + "\n",
        )
        for command in _checkpoint_command_args(journal_repo):
            subprocess.run(command, check=True)
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
