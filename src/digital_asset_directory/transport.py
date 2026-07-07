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
from pathlib import Path
from typing import Any

from .ids import stable_id
from .utils import atomic_write_text, json_dumps, utc_now

TRANSPORT_SURFACE_VERSION = "1.0.0"
DATA_ROOT_ENV = "DAD_DATA_ROOT"
DATA_ROOT_MARKER = ".dad-data-root.json"
USER_HUB_CONFIG = Path.home() / ".dad" / "hub.json"

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
    "raw_lessons": "raw/lessons",
    "raw_handoffs": "raw/handoffs",
    "raw_exceptions": "raw/exceptions",
    "audit_events": "audit/events",
    "agent_sessions": "state/agent_sessions",
}

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
    untrack_commands = [
        f'git rm -r --cached --quiet -- "{rel}"'
        for rel in sorted({s["source"].split("/")[0] for s in surfaces})
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


def _contract_transport_version(repo: Path) -> str:
    contract = repo / ".digital-asset" / "dad-integration.json"
    if not contract.exists():
        return ""
    try:
        payload = json.loads(contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str((payload.get("transport") or {}).get("surface_version", ""))


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
    has_contract = (repo / ".digital-asset" / "dad-integration.json").exists()
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
        "write_protected": write_protected,
    }


def _hub_self_audit(hub_root: Path) -> dict[str, Any]:
    tracked = 0
    top_dirs = sorted({rel.split("/")[0] for rel in DATA_PLANE_PATHS.values()})
    per_dir: dict[str, int] = {}
    for top in top_dirs:
        count = len(_git_tracked(hub_root, top))
        per_dir[top] = count
        tracked += count
    _root, mode = resolve_data_root(hub_root)
    return {
        "repo_id": "dad-hub",
        "data_root_mode": mode,
        "tracked_data_plane_files": tracked,
        "tracked_by_top_dir": per_dir,
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
    Queue rows dedupe on (repo_id, expected surface version) so re-runs do not
    spam; a repo upgrading resets naturally when its classification changes.
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
    existing = set()
    if queue_path.exists():
        for line in queue_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                    existing.add(str(row.get("queue_key", "")))
                except json.JSONDecodeError:
                    continue
    appended = 0
    with queue_path.open("a", encoding="utf-8") as handle:
        for record in needs_upgrade:
            queue_key = stable_id(
                "transport-upgrade", record["repo_id"], TRANSPORT_SURFACE_VERSION
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
            appended += 1
    return {
        "report_path": str(report_path),
        "queue_path": str(queue_path),
        "upgrade_required_count": len(needs_upgrade),
        "queue_appended": appended,
        "hub_classification": hub_record["classification"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def transport_upgrade_queue_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_mail") / "staged" / "transport-upgrade-queue.jsonl"


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


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts
