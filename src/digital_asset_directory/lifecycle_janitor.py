"""Lifecycle janitor: the automated cleanup that keeps DAD's governance gates
satisfiable.

DAD accumulates state in several places and puts a governance *gate* in front of
each, but historically shipped the gate without the *janitor* that keeps the
resource clean. The result is predictable deadlock: the pre-push gate demands
zero open sessions while nothing ever closes them, the catalog grows without
retention, and worktrees pile up. See docs/LIFECYCLE_JANITOR.md.

This module pairs every accumulating resource with a deterministic reaper:

- agent sessions   -> honest "abandoned_reaped" close of provably-idle sessions
- git worktrees    -> `git worktree prune` (+ opt-in remove of merged/clean ones)
- catalog rows     -> retention prune to the latest complete scan + VACUUM

Design invariants:
- Deterministic. Zero model calls.
- Dry-run by default. Session apply is a named human approval (honoring the
  agent_session_reaper F2/G5 boundary); the daemon only auto-reaps sessions when
  the operator has opted in via config.
- Honest statuses. Idle sessions become ``abandoned_reaped`` — never a fabricated
  postflight that would falsely claim completed learning review lanes.
- Conservative liveness. Sessions are only auto-closed when idle past a margin
  ABOVE the reaper's dry-run classification threshold, and never when leased,
  parked, lifecycle-held, or on the keep list.
- Never destroys work. ``git worktree prune`` only removes admin metadata for
  already-deleted directories; present worktrees are reported, never force-removed.
  Optional merged-worktree removal runs without ``--force`` so it refuses on any
  dirty/untracked state.
- Catalog retention preserves lessons/handoffs and keys on the latest COMPLETE scan.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .agent_session_reaper import build_agent_session_reaper_report
from .config import load_config
from .database import CatalogDB
from .transport import data_path, data_relative_path
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

SCHEMA_VERSION = "dad.lifecycle_janitor_report.v1"
METHOD_ID = "dad.lifecycle-janitor.v1"
REPORT_JSON = "lifecycle_janitor.json"
REPORT_MD = "lifecycle_janitor.md"
RECEIPT_JSONL = "lifecycle_janitor_receipts.jsonl"

# Auto-reap only sessions idle past this margin ABOVE the reaper's dry-run flag
# (DEFAULT_IDLE_LIVE_HOURS = 6h). Extra safety against closing a briefly-idle
# but still-live session.
DEFAULT_SESSION_AUTOAPPLY_IDLE_HOURS = 24.0
REAPED_STATUS = "abandoned_reaped"

AUTHORITY_BOUNDARY = (
    "Lifecycle janitor cleans the hub's own accumulating state (idle session "
    "records, orphaned worktree metadata, superseded per-scan catalog rows). It "
    "never mutates scanned source repositories, never force-removes a worktree "
    "with uncommitted or untracked work, never deletes lessons/handoffs, and "
    "marks reaped sessions 'abandoned_reaped' rather than fabricating a completed "
    "postflight. Session apply requires an explicit operator opt-in (F2/G5)."
)

_JANITOR_CONFIG_REL = Path("config") / "janitor.yaml"

_DEFAULT_CONFIG: dict[str, Any] = {
    "session_reap": {
        "apply": False,  # F2/G5: session close is opt-in
        "idle_hours": DEFAULT_SESSION_AUTOAPPLY_IDLE_HOURS,
        "approval_ref": "",
    },
    "worktree_prune": {
        "apply": True,  # `git worktree prune` is admin-only and safe
        "remove_merged_clean": False,  # removing present worktrees is opt-in
    },
    "catalog_retention": {
        "apply": True,  # prune superseded per-scan rows + VACUUM (hub's own data)
    },
}


def load_janitor_config(hub_root: Path) -> dict[str, Any]:
    """Load config/janitor.yaml over conservative defaults."""
    cfg = {section: dict(values) for section, values in _DEFAULT_CONFIG.items()}
    path = hub_root / _JANITOR_CONFIG_REL
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            raw = {}
        janitor = raw.get("janitor", raw) if isinstance(raw, dict) else {}
        for section, values in janitor.items():
            if section in cfg and isinstance(values, dict):
                cfg[section].update(values)
    return cfg


# --------------------------------------------------------------------------- #
# Agent sessions
# --------------------------------------------------------------------------- #


def _append_janitor_audit(hub_root: Path, event_type: str, payload: dict[str, Any]) -> None:
    created_at = payload.get("created_at") or utc_now()
    append_jsonl(
        data_relative_path(hub_root, Path("audit") / "events" / f"{created_at[:10]}.jsonl"),
        {"event_type": event_type, "created_at": created_at, **payload},
    )


def _close_session_file(path: Path, reason: str, now_iso: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or payload.get("status") != "open":
        return False
    payload["status"] = REAPED_STATUS
    payload["reaped_reason"] = reason
    payload["reaped_at"] = now_iso
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return True


def plan_session_reap(
    hub_root: Path,
    *,
    repository: Path | None,
    idle_live_hours: float,
    autoapply_idle_hours: float,
    keep_session_ids: set[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify open sessions and split candidate closes into auto-eligible vs
    review-needed, using the reaper's classification as the source of truth."""
    report = build_agent_session_reaper_report(
        hub_root,
        repository=repository,
        idle_live_hours=idle_live_hours,
        keep_session_ids=keep_session_ids,
        now=now,
    )
    auto_eligible: list[dict[str, Any]] = []
    review_needed: list[dict[str, Any]] = []
    for row in report["candidates"]:
        if row.get("classification") != "candidate_close":
            continue
        idle = row.get("idle_hours") or 0.0
        entry = {
            "session_id": row.get("session_id"),
            "path": row.get("path"),
            "tier": row.get("tier"),
            "idle_hours": idle,
            "agent": row.get("agent"),
        }
        if idle >= autoapply_idle_hours:
            auto_eligible.append(entry)
        else:
            review_needed.append(entry)
    return {
        "reaper_summary": report["summary"],
        "idle_live_hours": idle_live_hours,
        "autoapply_idle_hours": autoapply_idle_hours,
        "auto_eligible": auto_eligible,
        "review_needed": review_needed,
    }


def apply_session_reap(hub_root: Path, plan: dict[str, Any], *, approval_ref: str) -> dict[str, Any]:
    """Close auto-eligible idle sessions honestly (status 'abandoned_reaped')."""
    now_iso = utc_now()
    closed: list[str] = []
    failed: list[dict[str, str]] = []
    for entry in plan.get("auto_eligible", []):
        reason = (
            f"Reaped idle agent session (idle {entry.get('idle_hours')}h >= "
            f"{plan.get('autoapply_idle_hours')}h) by lifecycle janitor "
            f"(approval={approval_ref or 'config'}). Marked abandoned, not completed; "
            "any work remains on its branch/worktree."
        )
        path = Path(str(entry.get("path")))
        if _close_session_file(path, reason, now_iso):
            closed.append(str(entry.get("session_id")))
        else:
            failed.append({"session_id": str(entry.get("session_id")), "path": str(path)})
    if closed:
        _append_janitor_audit(
            hub_root,
            "lifecycle_janitor_session_reap",
            {"created_at": now_iso, "closed_count": len(closed), "approval_ref": approval_ref},
        )
    return {"closed": closed, "closed_count": len(closed), "failed": failed}


# --------------------------------------------------------------------------- #
# Git worktrees
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _list_worktrees(repo: Path) -> list[dict[str, str]]:
    out = _git(repo, "worktree", "list", "--porcelain")
    if out.returncode != 0:
        return []
    trees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in out.stdout.splitlines():
        if not line.strip():
            if current:
                trees.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        trees.append(current)
    return trees


def plan_worktree_prune(repo: Path) -> dict[str, Any]:
    """Report worktrees whose admin metadata is prunable (directory gone) and
    those still present on disk (never auto-removed).

    Uses the ``prunable`` marker from ``git worktree list --porcelain`` (git
    emits the prune-dry-run message on stderr, which varies by platform)."""
    prunable: list[str] = []
    present: list[dict[str, str]] = []
    for tree in _list_worktrees(repo):
        wt = tree.get("worktree", "")
        if "prunable" in tree:
            prunable.append(wt)
        elif wt and Path(wt).resolve() != repo.resolve():
            present.append({"path": wt, "branch": tree.get("branch", "")})
    return {
        "prunable_admin_entries": prunable,
        "prunable_count": len(prunable),
        "present_worktree_count": len(present),
        "present_worktrees_sample": present[:25],
    }


def apply_worktree_prune(repo: Path) -> dict[str, Any]:
    """Run `git worktree prune` (admin-only; never deletes present directories)."""
    before = len(_list_worktrees(repo))
    result = _git(repo, "worktree", "prune", "-v")
    after = len(_list_worktrees(repo))
    return {
        "ran": result.returncode == 0,
        "worktrees_before": before,
        "worktrees_after": after,
        "pruned_admin_entries": max(0, before - after),
        "output": result.stdout.strip()[:2000],
    }


# --------------------------------------------------------------------------- #
# Catalog retention
# --------------------------------------------------------------------------- #


def _catalog_db_path(hub_root: Path) -> Path | None:
    """Resolve the catalog DB path, tolerating a hub without a usable config."""
    try:
        return load_config(repo_root=hub_root).database_path
    except (FileNotFoundError, ValueError, KeyError):
        return None


def plan_catalog_retention(hub_root: Path) -> dict[str, Any]:
    db_path = _catalog_db_path(hub_root)
    if db_path is None:
        return {"exists": False, "skipped": "no_catalog_config"}
    if not db_path.exists():
        return {"database": str(db_path), "exists": False}
    with CatalogDB(db_path) as db:
        counts = db.table_counts()
        latest = db.latest_complete_scan()
    return {
        "database": str(db_path),
        "exists": True,
        "size_bytes": db_path.stat().st_size,
        "table_counts": counts,
        "latest_complete_scan": (latest or {}).get("scan_id"),
        "prunes_generated_rows": bool(latest and latest.get("scan_id")),
    }


def apply_catalog_retention(hub_root: Path) -> dict[str, Any]:
    db_path = _catalog_db_path(hub_root)
    if db_path is None:
        return {"exists": False, "skipped": "no_catalog_config"}
    if not db_path.exists():
        return {"database": str(db_path), "exists": False, "skipped": "no_catalog"}
    size_before = db_path.stat().st_size
    with CatalogDB(db_path) as db:
        latest = db.latest_complete_scan()
        removed: dict[str, Any] = {}
        if latest and latest.get("scan_id"):
            keep = str(latest["scan_id"])
            removed = db.prune_generated_records(keep)
            removed["stale_running_scans"] = db.prune_stale_running_scans(keep)
        else:
            removed = {"skipped": "no_complete_scan"}
        db.vacuum()
    size_after = db_path.stat().st_size
    return {
        "database": str(db_path),
        "latest_complete_scan": (latest or {}).get("scan_id"),
        "removed": removed,
        "size_before": size_before,
        "size_after": size_after,
        "reclaimed_bytes": max(0, size_before - size_after),
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def run_janitor_cycle(
    hub_root: Path,
    *,
    repository: Path | None = None,
    apply: bool = False,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Plan (and, per config, apply) all janitor sweeps.

    ``apply=False`` (default) plans only. ``apply=True`` executes the sweeps the
    config authorizes: catalog retention and `git worktree prune` are on by
    default (safe); session reap runs only when session_reap.apply is true.
    """
    repo = (repository or hub_root).resolve()
    cfg = config or load_janitor_config(hub_root)
    generated_at = utc_now()

    session_cfg = cfg["session_reap"]
    session_plan = plan_session_reap(
        hub_root,
        repository=repo,
        idle_live_hours=6.0,
        autoapply_idle_hours=float(session_cfg.get("idle_hours", DEFAULT_SESSION_AUTOAPPLY_IDLE_HOURS)),
        now=now,
    )
    worktree_plan = plan_worktree_prune(repo)
    catalog_plan = plan_catalog_retention(hub_root)

    actions: dict[str, Any] = {"applied": apply}
    if apply:
        if bool(session_cfg.get("apply")):
            actions["session_reap"] = apply_session_reap(
                hub_root, session_plan, approval_ref=str(session_cfg.get("approval_ref", ""))
            )
        else:
            actions["session_reap"] = {"skipped": "session_reap.apply=false (F2/G5 opt-in required)"}
        if bool(cfg["worktree_prune"].get("apply", True)):
            actions["worktree_prune"] = apply_worktree_prune(repo)
        else:
            actions["worktree_prune"] = {"skipped": "worktree_prune.apply=false"}
        if bool(cfg["catalog_retention"].get("apply", True)):
            actions["catalog_retention"] = apply_catalog_retention(hub_root)
        else:
            actions["catalog_retention"] = {"skipped": "catalog_retention.apply=false"}

    report = {
        "schema_version": SCHEMA_VERSION,
        "method_id": METHOD_ID,
        "generated_at": generated_at,
        "model_call_count": 0,
        "candidate_only": not apply,
        "applied": apply,
        "repository": str(repo),
        "config": cfg,
        "plan": {
            "sessions": session_plan,
            "worktrees": worktree_plan,
            "catalog": catalog_plan,
        },
        "actions": actions,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return report


def write_janitor_report(hub_root: Path, report: dict[str, Any]) -> dict[str, str]:
    reports_dir = data_path(hub_root, "central_reports")
    cadence_dir = data_path(hub_root, "cadence")
    reports_dir.mkdir(parents=True, exist_ok=True)
    cadence_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    receipt_path = cadence_dir / RECEIPT_JSONL
    atomic_write_text(json_path, json_dumps(report, pretty=True) + "\n")
    atomic_write_text(md_path, render_janitor_markdown(report))
    append_jsonl(
        receipt_path,
        {
            "recorded_at": report["generated_at"],
            "applied": report["applied"],
            "session_auto_eligible": len(report["plan"]["sessions"]["auto_eligible"]),
            "session_closed": report["actions"].get("session_reap", {}).get("closed_count", 0),
            "worktree_pruned": report["actions"].get("worktree_prune", {}).get("pruned_admin_entries", 0),
            "catalog_reclaimed_bytes": report["actions"].get("catalog_retention", {}).get("reclaimed_bytes", 0),
        },
    )
    return {"json_path": str(json_path), "markdown_path": str(md_path), "receipt_path": str(receipt_path)}


def render_janitor_markdown(report: dict[str, Any]) -> str:
    s = report["plan"]["sessions"]
    w = report["plan"]["worktrees"]
    c = report["plan"]["catalog"]
    lines = [
        "# Lifecycle janitor report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied: `{report['applied']}`",
        "",
        "## Sessions",
        f"- open considered: `{s['reaper_summary'].get('open_considered')}`",
        f"- auto-eligible (idle >= {s['autoapply_idle_hours']}h): `{len(s['auto_eligible'])}`",
        f"- review-needed (idle {s['idle_live_hours']}-{s['autoapply_idle_hours']}h): `{len(s['review_needed'])}`",
        "",
        "## Worktrees",
        f"- prunable admin entries: `{w['prunable_count']}`",
        f"- present worktrees: `{w['present_worktree_count']}`",
        "",
        "## Catalog",
        f"- size_bytes: `{c.get('size_bytes')}`",
        f"- latest_complete_scan: `{c.get('latest_complete_scan')}`",
        "",
        "## Authority boundary",
        "",
        report["authority_boundary"],
        "",
    ]
    return "\n".join(lines)
