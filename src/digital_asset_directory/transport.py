"""Transport kernel: data-root resolution and legacy-transport detection.

Implements the hard core of docs/DAD_TRANSPORT_AND_COMMS_REDESIGN.md:

1. A data-root resolver that lets ALL runtime data (mail spools, exception lake,
   lessons, reports, ledgers) live outside the git-tracked code repo under
   ``DAD_DATA_ROOT``. Resolution is fail-safe: until a marker file proves an
   initialized data root, every path resolves to today's legacy location, so
   nothing changes behavior until a human runs the migration.

2. A read-only legacy-transport auditor that checks enrolled repos for the old
   way of communicating (mailbox/event JSONL tracked in git, missing gitignore,
   missing transport contract version) and marks them for upgrade in a central
   queue plus staged candidate notices. It never writes to target repos.

Everything here is deterministic and candidate-only. Migration copies first,
verifies, activates the marker last, and NEVER deletes or runs git commands
itself - it emits the exact untrack commands for a human/Codex to run.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .ids import stable_id
from .utils import atomic_write_text, json_dumps, utc_now

TRANSPORT_SURFACE_VERSION = "1.0.0"
TRANSPORT_IMPLEMENTATION_VERSION = "1.0.0-m0m1m2"
TRANSPORT_TARGET_IMPLEMENTATION_VERSION = "1.0.0-m0m1m2"
DATA_ROOT_ENV = "DAD_DATA_ROOT"
DATA_ROOT_MARKER = ".dad-data-root.json"
USER_HUB_CONFIG = Path.home() / ".dad" / "hub.json"
TRANSPORT_QUEUE_LOCK_TIMEOUT_SECONDS = 10.0
TRANSPORT_QUEUE_LOCK_STALE_SECONDS = 30.0
TRANSPORT_QUEUE_LOCK_CLEANUP_ATTEMPTS = 10

TRANSPORT_IMPLEMENTATION_CAPABILITIES = [
    "fail_safe_data_root_resolver",
    "copy_verify_marker_last_migration",
    "reviewed_data_plane_path_registry",
    "legacy_transport_detector",
    "contract_missing_detector",
    "deduped_upgrade_queue",
    "implementation_version_tracking",
    "synthetic_rollout_harness",
    "runtime_writer_data_root_reroute",
    "daemon_run_cycle",
    "task_scheduler_status_surface",
    "journal_checkpoint_threshold",
    "journal_incremental_verified_file_index",
    "journal_detached_worktree_transaction",
    "catalog_database_journal_snapshot",
    "remote_outbox_screening",
]

TRANSPORT_TARGET_CAPABILITIES = list(TRANSPORT_IMPLEMENTATION_CAPABILITIES)

# Logical name -> hub-relative path. This is THE registry of data-plane
# surfaces; Codex reroutes writer modules through data_path() using these names.
DATA_PLANE_PATHS: dict[str, str] = {
    "central_mail": "processed/mail",
    "central_reports": "processed/reports",
    "events": "processed/events",
    "usage": "processed/usage",
    "learning": "processed/learning",
    "exceptions": "processed/exceptions",
    "research": "processed/research",
    "harness_reports": "processed/harnesses",
    "repo_inventory": "processed/repo_inventory",
    "cadence": "processed/cadence",
    "fable_packets": "processed/fable5",
    "agents": "processed/agents",
    "raw_lessons": "raw/lessons",
    "raw_handoffs": "raw/handoffs",
    "raw_exceptions": "raw/exceptions",
    "raw_agent_evaluations": "raw/agent-evaluations",
    "audit_events": "audit/events",
    "agent_sessions": "state/agent_sessions",
    "catalog_database": "state/catalog.sqlite3",
}
DATA_PLANE_FILE_SURFACES = frozenset({"catalog_database"})

AUTHORITY_BOUNDARY = (
    "Transport audit records and upgrade queue rows are central candidate "
    "metadata. They never authorize writes to target repos; upgrade delivery "
    "goes through reviewed mail/enrollment gates like any other notice."
)


# ---------------------------------------------------------------------------
# Data-root resolution
# ---------------------------------------------------------------------------


def _default_data_root() -> Path:
    return Path.home() / ".dad" / "data"


def _candidate_data_root(env: dict[str, str] | None = None) -> Path | None:
    if env is not None:
        raw = env.get(DATA_ROOT_ENV, "").strip()
        return Path(raw) if raw else None
    raw = os.environ.get(DATA_ROOT_ENV, "").strip()
    if raw:
        return Path(raw)
    if USER_HUB_CONFIG.exists():
        try:
            payload = json.loads(USER_HUB_CONFIG.read_text(encoding="utf-8"))
            configured = str(payload.get("data_root", "")).strip()
            if configured:
                return Path(configured)
        except (OSError, json.JSONDecodeError):
            return None
    return _default_data_root()


def resolve_data_root(
    hub_root: Path, *, env: dict[str, str] | None = None
) -> tuple[Path, str]:
    """Return (root, mode). mode is 'data_root' only for an INITIALIZED root.

    Fail-safe rule: a configured-but-uninitialized root still resolves legacy,
    so a typo in DAD_DATA_ROOT can never silently split state across two roots.
    The marker must also belong to this hub; a data root initialized for another
    checkout is treated as unavailable instead of cross-wiring runtime state.
    """
    candidate = _candidate_data_root(env)
    if candidate is not None and _data_root_marker_matches_hub(candidate, hub_root):
        return candidate, "data_root"
    return hub_root, "legacy"


def _data_root_marker_matches_hub(candidate: Path, hub_root: Path) -> bool:
    marker = candidate / DATA_ROOT_MARKER
    if not marker.exists():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    hub_ref = str(payload.get("hub_ref", "")).strip()
    if not hub_ref:
        return False
    expected = os.path.normcase(str(hub_root.resolve()))
    configured = os.path.normcase(str(Path(hub_ref).resolve()))
    return configured == expected


def data_path(
    hub_root: Path, logical_name: str, *, env: dict[str, str] | None = None
) -> Path:
    if logical_name not in DATA_PLANE_PATHS:
        raise KeyError(
            f"Unknown data-plane surface '{logical_name}'. Add it to "
            "DATA_PLANE_PATHS with review; do not invent paths inline."
        )
    root, _mode = resolve_data_root(hub_root, env=env)
    return root / DATA_PLANE_PATHS[logical_name]


def data_relative_path(
    hub_root: Path, relative_path: Path | str, *, env: dict[str, str] | None = None
) -> Path:
    """Resolve a repo-relative path through the data plane when reviewed.

    This is for generated runtime outputs whose historical repo-relative paths
    must stay stable. Paths outside ``DATA_PLANE_PATHS`` remain hub-relative so
    schemas, registries, docs, templates, and source reads keep repo authority.
    Absolute paths are already explicit and are returned unchanged.
    """
    path = Path(relative_path)
    if path.is_absolute():
        return path
    normalized = Path(*path.parts)
    for logical_name, reviewed_root in sorted(
        DATA_PLANE_PATHS.items(),
        key=lambda item: len(Path(item[1]).parts),
        reverse=True,
    ):
        surface = Path(reviewed_root)
        try:
            suffix = normalized.relative_to(surface)
        except ValueError:
            continue
        return data_path(hub_root, logical_name, env=env) / suffix
    return hub_root / normalized


def _looks_like_onedrive(path: Path) -> bool:
    return "onedrive" in str(path).lower()


def init_data_root(
    target: Path, *, hub_root: Path, force_onedrive: bool = False
) -> dict[str, Any]:
    """Create and mark a data root. Refuses unsafe empty-root activation.

    OneDrive sync locks race SQLite WAL and JSONL appends; the data root should
    live outside sync scope (e.g. %USERPROFILE%/.dad/data).

    If the hub already has legacy data-plane files, this only writes the marker
    after the target contains byte-identical copies. That keeps standalone
    ``data init`` from silently splitting state; ``data migrate --apply`` is the
    ordinary copy-verify-activate path.
    """
    if _looks_like_onedrive(target) and not force_onedrive:
        raise ValueError(
            "Data root is inside a OneDrive-synced path; sync locks race "
            "SQLite/JSONL writes. Choose a path outside OneDrive or pass "
            "force_onedrive=True after accepting the risk."
        )
    unverified = _unverified_target_copies(hub_root, target)
    if unverified:
        sample = ", ".join(unverified[:5])
        raise ValueError(
            "Refusing to activate data root before legacy data is copied and "
            f"hash-verified ({len(unverified)} missing or mismatched file(s); "
            f"sample: {sample}). Run `data migrate --apply` for copy -> verify "
            "-> marker-last activation."
        )
    target.mkdir(parents=True, exist_ok=True)
    marker = {
        "schema_version": "0.1.0",
        "created_at": utc_now(),
        "hub_ref": str(hub_root.resolve()),
        "transport_surface_version": TRANSPORT_SURFACE_VERSION,
        "transport_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_text(target / DATA_ROOT_MARKER, json_dumps(marker, pretty=True) + "\n")
    return {"data_root": str(target), "marker": str(target / DATA_ROOT_MARKER)}


# ---------------------------------------------------------------------------
# Migration (copy-first, verify, activate last, never delete, never run git)
# ---------------------------------------------------------------------------


def _iter_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    if base.is_file():
        return [base]
    return sorted(p for p in base.rglob("*") if p.is_file())


def _legacy_data_files(hub_root: Path) -> list[tuple[str, Path, Path]]:
    files: list[tuple[str, Path, Path]] = []
    for _logical, rel in sorted(DATA_PLANE_PATHS.items()):
        src_base = hub_root / rel
        for src in _iter_files(src_base):
            files.append((rel, src, src.relative_to(src_base)))
    return files


def _unverified_target_copies(hub_root: Path, target: Path) -> list[str]:
    unverified: list[str] = []
    for rel, src, rel_file in _legacy_data_files(hub_root):
        dst = target / rel / rel_file
        if not dst.exists():
            unverified.append(str(src.relative_to(hub_root)))
            continue
        if _file_digest(dst) != _file_digest(src):
            unverified.append(str(src.relative_to(hub_root)))
    return unverified


def plan_data_migration(
    hub_root: Path, target: Path, *, env: dict[str, str] | None = None
) -> dict[str, Any]:
    surfaces = []
    total = 0
    for logical, rel in sorted(DATA_PLANE_PATHS.items()):
        files = _iter_files(hub_root / rel)
        total += len(files)
        surfaces.append(
            {
                "logical_name": logical,
                "source": rel,
                "destination": str(target / rel),
                "file_count": len(files),
            }
        )
    top_dirs = sorted({s["source"].split("/")[0] for s in surfaces})
    quoted_dirs = " ".join(f'"{rel}"' for rel in top_dirs)
    untrack_commands = [
        f"$trackedRuntime = @(git ls-files -ci --exclude-standard -- {quoted_dirs})",
        "if ($trackedRuntime.Count -gt 0) { git rm --cached -- $trackedRuntime }",
    ]
    return {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "hub_root": str(hub_root.resolve()),
        "target_data_root": str(target),
        "onedrive_warning": _looks_like_onedrive(target),
        "total_files": total,
        "surfaces": surfaces,
        "untrack_commands_after_verified_copy": untrack_commands,
        "untrack_scope": "tracked_and_gitignored_data_plane_files_only",
        "gitignore_lines_to_add": sorted(
            {f"/{s['source'].split('/')[0]}/" for s in surfaces}
        ),
        "rule": (
            "Copy first, verify counts and hashes, write the activation marker "
            "LAST, run untrack commands only after a verified journal/backup "
            "checkpoint exists. This plan never deletes source files."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _file_digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def apply_data_migration(
    hub_root: Path,
    target: Path,
    *,
    force_onedrive: bool = False,
) -> dict[str, Any]:
    """Copy all data-plane surfaces to the target root, verify, then activate.

    Idempotent: files whose destination already exists with an identical hash
    are skipped. Sources are never deleted; git is never invoked. Activation
    (the marker) happens only after every copied file verifies.
    """
    if _looks_like_onedrive(target) and not force_onedrive:
        raise ValueError(
            "Refusing to migrate into a OneDrive-synced data root without "
            "force_onedrive=True."
        )
    copied = 0
    skipped = 0
    verified_failures: list[str] = []
    for logical, rel in sorted(DATA_PLANE_PATHS.items()):
        src_base = hub_root / rel
        dst_base = target / rel
        for src in _iter_files(src_base):
            rel_file = src.relative_to(src_base)
            dst = dst_base / rel_file
            if dst.exists() and _file_digest(dst) == _file_digest(src):
                skipped += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if _file_digest(dst) != _file_digest(src):
                verified_failures.append(str(src))
                continue
            copied += 1
    if verified_failures:
        raise RuntimeError(
            "Migration verification failed for "
            f"{len(verified_failures)} file(s); marker NOT written: "
            + ", ".join(verified_failures[:5])
        )
    init_data_root(target, hub_root=hub_root, force_onedrive=force_onedrive)
    plan = plan_data_migration(hub_root, target)
    return {
        "copied": copied,
        "skipped_identical": skipped,
        "activated": True,
        "data_root": str(target),
        "next_manual_steps": {
            "untrack_commands": plan["untrack_commands_after_verified_copy"],
            "gitignore_lines": plan["gitignore_lines_to_add"],
            "note": (
                "Run these in the hub repo ONLY after a verified backup/journal "
                "checkpoint of the new data root exists."
            ),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


# ---------------------------------------------------------------------------
# Legacy-transport audit (read-only over enrolled repos)
# ---------------------------------------------------------------------------

_LEGACY_SPOOL_DIRS = (".digital-asset/mail", ".digital-asset/events", ".digital-asset/exceptions")


def _git_tracked(repo: Path, subpath: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--", subpath],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _mail_gitignore_covers_jsonl(repo: Path) -> bool:
    gitignore = repo / ".digital-asset" / "mail" / ".gitignore"
    if not gitignore.exists():
        return False
    try:
        body = gitignore.read_text(encoding="utf-8")
    except OSError:
        return False
    return "*.jsonl" in body


def _contract_payload(repo: Path) -> dict[str, Any]:
    contract = repo / ".digital-asset" / "dad-integration.json"
    if not contract.exists():
        return {}
    try:
        payload = json.loads(contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _contract_transport_fields(repo: Path) -> dict[str, Any]:
    transport = _contract_payload(repo).get("transport")
    return transport if isinstance(transport, dict) else {}


def _contract_transport_version(repo: Path) -> str:
    return str(_contract_transport_fields(repo).get("surface_version", ""))


def _contract_transport_implementation_version(repo: Path) -> str:
    return str(_contract_transport_fields(repo).get("implementation_version", ""))


def audit_repo_transport(
    repo: Path, *, repo_id: str = "", write_protected: bool = False
) -> dict[str, Any]:
    """Read-only legacy-transport signals for one repo. Never mutates the repo."""
    if not repo.exists() or not repo.is_dir():
        return {
            "repo_id": repo_id or repo.name,
            "repo_name": repo.name,
            "classification": "unreachable",
            "signals": [],
            "transport_surface_version_seen": "",
            "transport_implementation_version_seen": "",
            "write_protected": write_protected,
        }
    signals: list[dict[str, Any]] = []
    tracked_spool_files: list[str] = []
    for spool in _LEGACY_SPOOL_DIRS:
        tracked_spool_files.extend(_git_tracked(repo, spool))
    if tracked_spool_files:
        jsonl_tracked = [f for f in tracked_spool_files if f.endswith(".jsonl")]
        if jsonl_tracked:
            signals.append(
                {
                    "signal": "spool_jsonl_tracked_in_git",
                    "severity": "high",
                    "detail_count": len(jsonl_tracked),
                    "examples": jsonl_tracked[:3],
                    "meaning": (
                        "Mail/event/exception JSONL is committed to git - the old "
                        "PR-transport path. Spools must be gitignored local caches."
                    ),
                }
            )
    has_mailbox = (repo / ".digital-asset" / "mail").exists()
    if has_mailbox and not _mail_gitignore_covers_jsonl(repo):
        signals.append(
            {
                "signal": "mail_gitignore_missing_or_incomplete",
                "severity": "medium",
                "meaning": "Mailbox exists but *.jsonl is not gitignored; next commit re-enters PR transport.",
            }
        )
    seen_version = _contract_transport_version(repo)
    seen_implementation_version = _contract_transport_implementation_version(repo)
    has_contract = (repo / ".digital-asset" / "dad-integration.json").exists()
    contract_repo_path = str(_contract_payload(repo).get("repo_path") or "").strip()
    if has_contract and contract_repo_path:
        configured = os.path.normcase(os.path.normpath(str(repo.resolve())))
        recorded = os.path.normcase(os.path.normpath(str(Path(contract_repo_path).resolve())))
        if configured != recorded:
            signals.append(
                {
                    "signal": "repo_path_stale",
                    "severity": "medium",
                    "recorded_path_exists": Path(contract_repo_path).exists(),
                    "meaning": (
                        "Enrollment contract repo_path does not match the reviewed "
                        "canonical checkout; refresh the contract without changing "
                        "transport or repo authority."
                    ),
                }
            )
    if has_contract and seen_version != TRANSPORT_SURFACE_VERSION:
        signals.append(
            {
                "signal": "transport_surface_version_stale",
                "severity": "medium",
                "seen": seen_version or "absent",
                "expected": TRANSPORT_SURFACE_VERSION,
                "meaning": "Enrollment contract predates the transport redesign; repo needs the upgrade wave.",
            }
        )
    if has_contract and seen_implementation_version != TRANSPORT_IMPLEMENTATION_VERSION:
        signals.append(
            {
                "signal": "transport_implementation_version_stale",
                "severity": "medium",
                "seen": seen_implementation_version or "absent",
                "expected": TRANSPORT_IMPLEMENTATION_VERSION,
                "meaning": (
                    "Enrollment contract does not pin the current transport "
                    "implementation bundle; future upgrade waves cannot be "
                    "tracked efficiently."
                ),
            }
        )
    if has_mailbox and not has_contract:
        signals.append(
            {
                "signal": "contract_missing",
                "severity": "medium",
                "expected": TRANSPORT_SURFACE_VERSION,
                "meaning": (
                    "Mailbox exists without a DAD enrollment contract; repo needs "
                    "the transport upgrade wave before it can be considered current."
                ),
            }
        )
    if not has_contract and not has_mailbox:
        classification = "no_dad_surface"
    elif any(s["severity"] == "high" for s in signals):
        classification = "upgrade_required"
    elif signals:
        classification = "upgrade_recommended"
    else:
        classification = "current"
    return {
        "repo_id": repo_id or repo.name,
        "repo_name": repo.name,
        "classification": classification,
        "signals": signals,
        "transport_surface_version_seen": seen_version,
        "transport_implementation_version_seen": seen_implementation_version,
        "write_protected": write_protected,
    }


def transport_upgrade_queue_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_mail") / "staged" / "transport-upgrade-queue.jsonl"


def _transport_queue_lock_path(queue_path: Path) -> Path:
    digest = hashlib.sha256(str(queue_path.resolve()).encode("utf-8")).hexdigest()[:24]
    lock_dir = Path(tempfile.gettempdir()) / "dad-transport-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"transport-upgrade-queue-{digest}.lock"


def _unlink_transport_queue_lock(lock_path: Path, *, ignore_failure: bool) -> None:
    for attempt in range(TRANSPORT_QUEUE_LOCK_CLEANUP_ATTEMPTS):
        try:
            lock_path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == TRANSPORT_QUEUE_LOCK_CLEANUP_ATTEMPTS - 1:
                if ignore_failure:
                    return
                raise
            time.sleep(0.05 * (attempt + 1))


def _acquire_transport_queue_lock(queue_path: Path) -> tuple[int, Path]:
    lock_path = _transport_queue_lock_path(queue_path)
    deadline = time.monotonic() + TRANSPORT_QUEUE_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
            return fd, lock_path
        except FileExistsError:
            try:
                lock_age = time.time() - lock_path.stat().st_mtime
            except OSError:
                lock_age = 0.0
            if lock_age > TRANSPORT_QUEUE_LOCK_STALE_SECONDS:
                _unlink_transport_queue_lock(lock_path, ignore_failure=True)
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for transport queue lock: {lock_path}")
            time.sleep(0.05)


def _release_transport_queue_lock(fd: int, lock_path: Path) -> None:
    try:
        os.close(fd)
    finally:
        _unlink_transport_queue_lock(lock_path, ignore_failure=True)


def _hub_self_audit(hub_root: Path) -> dict[str, Any]:
    tracked = 0
    intentionally_tracked = 0
    top_dirs = sorted({rel.split("/")[0] for rel in DATA_PLANE_PATHS.values()})
    per_dir: dict[str, int] = {}
    for top in top_dirs:
        all_tracked = set(_git_tracked(hub_root, top))
        ignored_result = subprocess.run(
            ["git", "-C", str(hub_root), "ls-files", "-ci", "--exclude-standard", "--", top],
            check=False,
            capture_output=True,
            text=True,
        )
        ignored_tracked = {
            line.strip().replace("\\", "/")
            for line in ignored_result.stdout.splitlines()
            if line.strip()
        }
        count = len(ignored_tracked)
        per_dir[top] = count
        tracked += count
        intentionally_tracked += len(all_tracked - ignored_tracked)
    _root, mode = resolve_data_root(hub_root)
    return {
        "repo_id": "dad-hub",
        "data_root_mode": mode,
        "tracked_data_plane_files": tracked,
        "tracked_by_top_dir": per_dir,
        "intentionally_tracked_evidence_files": intentionally_tracked,
        "classification": (
            "current"
            if mode == "data_root" and tracked == 0
            else "upgrade_required"
        ),
        "meaning": (
            "The hub itself uses PR transport while data-plane files remain "
            "git-tracked or the data root is not activated."
        ),
    }


def audit_all_repo_transport(
    hub_root: Path,
    repos: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit hub + repos; write the central report and the upgrade queue.

    ``repos``: [{"id", "path", "write_protected"}] from reviewed policy only -
    callers pass config-derived rows; this function never discovers repos.
    Queue rows dedupe on (repo_id, expected surface version, expected
    implementation version) so re-runs do not spam; a repo upgrading resets
    naturally when its expected version changes.
    """
    records = [
        audit_repo_transport(
            Path(str(row.get("path", ""))),
            repo_id=str(row.get("id", "")),
            write_protected=bool(row.get("write_protected", False)),
        )
        for row in repos
    ]
    records.sort(key=lambda r: r["repo_id"])
    hub_record = _hub_self_audit(hub_root)
    needs_upgrade = [
        r
        for r in records
        if r["classification"] in {"upgrade_required", "upgrade_recommended"}
    ]
    report = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "transport_surface_version": TRANSPORT_SURFACE_VERSION,
        "transport_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
        "hub": hub_record,
        "repo_count": len(records),
        "classification_counts": _count(records, "classification"),
        "records": records,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    report_dir = data_path(hub_root, "central_reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "transport_audit.json"
    atomic_write_text(report_path, json_dumps(report, pretty=True) + "\n")

    queue_path = transport_upgrade_queue_path(hub_root)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    appended = 0
    lock_fd, lock_path = _acquire_transport_queue_lock(queue_path)
    try:
        existing = set()
        if queue_path.exists():
            for line in queue_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        row = json.loads(line)
                        existing.add(str(row.get("queue_key", "")))
                    except json.JSONDecodeError:
                        continue
        with queue_path.open("a", encoding="utf-8") as handle:
            for record in needs_upgrade:
                queue_key = stable_id(
                    "transport-upgrade",
                    record["repo_id"],
                    TRANSPORT_SURFACE_VERSION,
                    TRANSPORT_IMPLEMENTATION_VERSION,
                )
                if queue_key in existing:
                    continue
                handle.write(
                    json.dumps(
                        {
                            "queue_key": queue_key,
                            "repo_id": record["repo_id"],
                            "classification": record["classification"],
                            "signals": [s["signal"] for s in record["signals"]],
                            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
                            "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                            "staged_at": report["generated_at"],
                            "delivery_rule": (
                                "central_only for write-protected repos; otherwise "
                                "candidate mail via reviewed delivery gates"
                            ),
                            "write_protected": record["write_protected"],
                            "review_status": "candidate",
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                existing.add(queue_key)
                appended += 1
    finally:
        _release_transport_queue_lock(lock_fd, lock_path)
    return {
        "report_path": str(report_path),
        "queue_path": str(queue_path),
        "upgrade_required_count": len(needs_upgrade),
        "queue_appended": appended,
        "hub_classification": hub_record["classification"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }

def read_transport_upgrade_queue(hub_root: Path) -> dict[str, Any]:
    path = transport_upgrade_queue_path(hub_root)
    rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    if path.exists():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                invalid_rows.append(
                    {
                        "line_number": line_number,
                        "error": str(exc),
                    }
                )
                continue
            if isinstance(payload, dict):
                rows.append(payload)
            else:
                invalid_rows.append(
                    {
                        "line_number": line_number,
                        "error": "queue row is not an object",
                    }
                )
    return {
        "schema_version": "dad.transport.upgrade_queue.v1",
        "queue_path": str(path),
        "row_count": len(rows),
        "invalid_row_count": len(invalid_rows),
        "rows": rows,
        "invalid_rows": invalid_rows,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_transport_version_status(
    hub_root: Path,
    repos: list[dict[str, Any]],
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Summarize repo transport versions from reviewed repo rows only."""
    records = [
        audit_repo_transport(
            Path(str(row.get("path", ""))),
            repo_id=str(row.get("id", "")),
            write_protected=bool(row.get("write_protected", False)),
        )
        for row in repos
    ]
    records.sort(key=lambda row: row["repo_id"])
    repo_versions = [
        {
            "repo_id": record["repo_id"],
            "classification": record["classification"],
            "transport_surface_version_seen": record.get("transport_surface_version_seen", "")
            or "missing",
            "transport_implementation_version_seen": record.get(
                "transport_implementation_version_seen", ""
            )
            or "missing",
            "expected_surface_version": TRANSPORT_SURFACE_VERSION,
            "expected_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
            "write_protected": bool(record.get("write_protected", False)),
            "signals": [signal["signal"] for signal in record.get("signals", [])],
        }
        for record in records
    ]
    status = {
        "schema_version": "dad.transport.version_status.v1",
        "generated_at": utc_now(),
        "status": "current"
        if all(row["classification"] == "current" for row in repo_versions)
        else "upgrade_needed",
        "repo_count": len(repo_versions),
        "classification_counts": _count(repo_versions, "classification"),
        "transport_surface_version": TRANSPORT_SURFACE_VERSION,
        "transport_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
        "target_implementation_version": TRANSPORT_TARGET_IMPLEMENTATION_VERSION,
        "implementation_registry": {
            "version": TRANSPORT_IMPLEMENTATION_VERSION,
            "surface_version": TRANSPORT_SURFACE_VERSION,
            "capabilities": TRANSPORT_IMPLEMENTATION_CAPABILITIES,
            "target_m0_m2_capabilities": TRANSPORT_TARGET_CAPABILITIES,
            "version_semantics": (
                "surface_version pins the downstream contract shape; "
                "implementation_version pins the DAD transport bundle/capability set."
            ),
        },
        "repo_versions": repo_versions,
        "operator_next_steps": [
            "Run `asset-dir transport audit` to refresh upgrade queue rows.",
            "Use reviewed enrollment update waves for real repos; do not write target repos from this report.",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if write:
        report_dir = data_path(hub_root, "central_reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "transport_version_status.json"
        atomic_write_text(report_path, json_dumps(status, pretty=True) + "\n")
        status["report_path"] = str(report_path)
    return status


def run_synthetic_transport_rollout(hub_root: Path) -> dict[str, Any]:
    """Exercise transport detection/versioning with synthetic temp repos only."""
    report_dir = data_path(hub_root, "central_reports")
    with tempfile.TemporaryDirectory(prefix="dad-transport-synthetic-") as tmp_name:
        tmp = Path(tmp_name)
        synthetic_hub = tmp / "hub"
        (synthetic_hub / "processed" / "usage").mkdir(parents=True)
        (synthetic_hub / "processed" / "usage" / "usage.jsonl").write_text(
            '{"usage_id":"synthetic"}\n', encoding="utf-8"
        )
        data_root = tmp / "data-root"
        apply_data_migration(synthetic_hub, data_root, force_onedrive=True)
        root, mode = resolve_data_root(
            synthetic_hub, env={DATA_ROOT_ENV: str(data_root)}
        )
        data_root_ok = mode == "data_root" and root == data_root
        data_root_writer_paths_ok = (
            data_path(synthetic_hub, "usage", env={DATA_ROOT_ENV: str(data_root)})
            == data_root / "processed" / "usage"
        )

        case_specs = [
            {
                "case_id": "current",
                "gitignore": True,
                "contract": transport_contract_payload(),
                "expected_classification": "current",
                "expected_signals": [],
            },
            {
                "case_id": "stale-surface",
                "gitignore": True,
                "contract": {
                    "surface_version": "0.0.1",
                    "implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
                    "mode": "local_pull",
                    "journal_fallback": True,
                },
                "expected_classification": "upgrade_recommended",
                "expected_signals": ["transport_surface_version_stale"],
            },
            {
                "case_id": "missing-implementation",
                "gitignore": True,
                "contract": {
                    "surface_version": TRANSPORT_SURFACE_VERSION,
                    "mode": "local_pull",
                    "journal_fallback": True,
                },
                "expected_classification": "upgrade_recommended",
                "expected_signals": ["transport_implementation_version_stale"],
            },
            {
                "case_id": "tracked-spool-protected",
                "track_mail": True,
                "gitignore": False,
                "contract": transport_contract_payload(),
                "write_protected": True,
                "expected_classification": "upgrade_required",
                "expected_signals": ["spool_jsonl_tracked_in_git"],
            },
            {
                "case_id": "mailbox-contract-missing",
                "gitignore": True,
                "contract": None,
                "expected_classification": "upgrade_recommended",
                "expected_signals": ["contract_missing"],
            },
            {
                "case_id": "no-dad-surface",
                "no_mailbox": True,
                "contract": None,
                "expected_classification": "no_dad_surface",
                "expected_signals": [],
            },
        ]
        repos: list[dict[str, Any]] = []
        expectations: dict[str, dict[str, Any]] = {}
        for spec in case_specs:
            repo = tmp / str(spec["case_id"])
            _write_synthetic_transport_repo(repo, spec)
            repos.append(
                {
                    "id": spec["case_id"],
                    "path": str(repo),
                    "write_protected": bool(spec.get("write_protected", False)),
                }
            )
            expectations[str(spec["case_id"])] = spec
        repos.append({"id": "unreachable", "path": str(tmp / "missing"), "write_protected": False})
        expectations["unreachable"] = {
            "expected_classification": "unreachable",
            "expected_signals": [],
        }

        previous_data_root = os.environ.get(DATA_ROOT_ENV)
        os.environ[DATA_ROOT_ENV] = str(data_root)
        try:
            first = audit_all_repo_transport(synthetic_hub, repos)
            second = audit_all_repo_transport(synthetic_hub, repos)
            status = build_transport_version_status(synthetic_hub, repos, write=False)
        finally:
            if previous_data_root is None:
                os.environ.pop(DATA_ROOT_ENV, None)
            else:
                os.environ[DATA_ROOT_ENV] = previous_data_root
        report = json.loads(Path(first["report_path"]).read_text(encoding="utf-8"))
        case_results = []
        for record in report["records"]:
            expected = expectations[record["repo_id"]]
            signals = {signal["signal"] for signal in record.get("signals", [])}
            expected_signals = set(expected.get("expected_signals", []))
            case_results.append(
                {
                    "case_id": record["repo_id"],
                    "expected_classification": expected["expected_classification"],
                    "actual_classification": record["classification"],
                    "expected_signals": sorted(expected_signals),
                    "actual_signals": sorted(signals),
                    "passed": record["classification"] == expected["expected_classification"]
                    and expected_signals <= signals,
                }
            )

    payload = {
        "schema_version": "dad.transport.synthetic_rollout.v1",
        "generated_at": utc_now(),
        "status": "passed"
        if data_root_ok
        and data_root_writer_paths_ok
        and all(row["passed"] for row in case_results)
        and second["queue_appended"] == 0
        else "failed",
        "synthetic_only": True,
        "case_count": len(case_results),
        "passed_count": sum(1 for row in case_results if row["passed"]),
        "data_root_activation_passed": data_root_ok,
        "data_root_writer_paths_passed": data_root_writer_paths_ok,
        "queue_dedupe_second_run_appended": second["queue_appended"],
        "version_status_schema": status["schema_version"],
        "transport_surface_version": TRANSPORT_SURFACE_VERSION,
        "transport_implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
        "case_results": sorted(case_results, key=lambda row: row["case_id"]),
        "authority_boundary": (
            "Synthetic rollout creates temporary repos only. It proves detector, "
            "version, and queue behavior; it does not approve or mutate real repos."
        ),
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "transport_synthetic_rollout.json"
    atomic_write_text(report_path, json_dumps(payload, pretty=True) + "\n")
    payload["report_path"] = str(report_path)
    return payload


def transport_contract_payload(
    *,
    mode: str = "local_pull",
    journal_fallback: bool = True,
) -> dict[str, Any]:
    """Return the reviewed downstream contract block for this implementation."""
    return {
        "surface_version": TRANSPORT_SURFACE_VERSION,
        "implementation_version": TRANSPORT_IMPLEMENTATION_VERSION,
        "mode": mode,
        "journal_fallback": journal_fallback,
    }


def _write_synthetic_transport_repo(repo: Path, spec: dict[str, Any]) -> None:
    repo.mkdir(parents=True)
    if not spec.get("no_mailbox"):
        mail = repo / ".digital-asset" / "mail"
        mail.mkdir(parents=True)
        (mail / "outbox.jsonl").write_text('{"mail_id":"synthetic"}\n', encoding="utf-8")
        if spec.get("gitignore"):
            (mail / ".gitignore").write_text("*.jsonl\nlast_checked.json\n", encoding="utf-8")
    contract = spec.get("contract")
    if contract is not None:
        dad = repo / ".digital-asset"
        dad.mkdir(parents=True, exist_ok=True)
        (dad / "dad-integration.json").write_text(
            json.dumps({"repo_id": repo.name, "transport": contract}, sort_keys=True),
            encoding="utf-8",
        )
    subprocess.run(["git", "-C", str(repo), "init", "-q", "--template="], check=True)
    if spec.get("track_mail"):
        subprocess.run(
            ["git", "-C", str(repo), "add", "-f", ".digital-asset/mail/outbox.jsonl"],
            check=True,
        )


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts
