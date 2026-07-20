"""Dry-run agent session reaper (N2 / F2 groundwork).

Classifies open sessions with bounded tiering and idle/liveness evidence.
Never closes, migrates, or deletes sessions. Apply mode is intentionally absent.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ids import stable_id
from .learning import agent_sessions_dir
from .transport import data_path, legacy_data_path, resolve_data_root
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

SCHEMA_VERSION = "dad.agent_session_reaper_report.v1"
METHOD_ID = "dad.agent-session-reaper.v1"
REPORT_JSON = "agent_session_reaper.json"
REPORT_MD = "agent_session_reaper.md"
RECEIPT_JSONL = "agent_session_reaper_receipts.jsonl"
HISTORY_JSONL = "agent_session_reaper_history.jsonl"
DEFAULT_IDLE_LIVE_HOURS = 6.0
DEFAULT_PRESERVATION_POINTER = (
    "Preservation pointer: builds must be captured under ~/.dad/preserve/ "
    "(patches, untracked copies, disposition table, and/or all-refs bundle) "
    "before any future apply. Dry-run does not close sessions."
)
AUTHORITY_BOUNDARY = (
    "Agent session reaper dry-run is report-only evidence. It classifies open "
    "sessions, proposes nonblank administrative summaries with a preservation "
    "pointer, and appends a JSONL receipt. It never postflights, closes, "
    "deletes, migrates, or rewrites session files. Apply mode is out of scope "
    "until a separate named human approval and load-bearing gate (F2/G5)."
)

_EXCEPTION_STATUSES = frozenset({"leased", "long_running", "parked"})
_EXCEPTION_FLAGS = frozenset(
    {
        "leased",
        "long_running",
        "parked",
        "lifecycle_hold",
        "does_not_apply_reaper",
    }
)
_REVIEWER_AGENT = re.compile(r"redteam|checker|review|reader|scout|audit", re.I)
_REVIEWER_TASK = re.compile(r"^(read-only|independent read-only)", re.I)


def classify_session_tier(payload: dict[str, Any]) -> str:
    """Bounded tier: E = ephemeral reviewer; B = build/general."""

    agent = str(payload.get("agent", "") or "")
    task = str(payload.get("task", "") or "")
    if _REVIEWER_AGENT.search(agent) or _REVIEWER_TASK.search(task):
        return "E"
    return "B"


def proposed_close_summary(
    payload: dict[str, Any],
    *,
    idle_hours: float,
    idle_live_hours: float,
    preservation_pointer: str,
) -> str:
    """Nonblank administrative summary candidate (never written by dry-run)."""

    task = (str(payload.get("task", "") or "unspecified task").strip()[:160])
    base = (
        f"Administrative reaper close candidate (dry-run only; session file idle "
        f"{idle_hours:.1f}h, liveness rule: idle >= {idle_live_hours:g}h). "
        f"Original task: {task}. "
    )
    if classify_session_tier(payload) == "E":
        detail = (
            "Tier-E ephemeral reviewer session with no owned build; any findings "
            "live in the records of the session that spawned it. "
        )
    else:
        detail = (
            "Tier-B session never postflighted by its agent; work, if any, lives "
            "on its branch/worktree and must remain preserved before any apply. "
        )
    pointer = preservation_pointer.strip() or DEFAULT_PRESERVATION_POINTER
    return base + detail + pointer


def _parse_exception_reason(payload: dict[str, Any]) -> str | None:
    status = str(payload.get("status", "") or "").strip().lower()
    if status in _EXCEPTION_STATUSES:
        return f"status:{status}"
    for flag in _EXCEPTION_FLAGS:
        if payload.get(flag) is True:
            return f"flag:{flag}"
    lifecycle = payload.get("lifecycle")
    if isinstance(lifecycle, dict):
        hold = str(lifecycle.get("hold") or lifecycle.get("mode") or "").strip().lower()
        if hold in _EXCEPTION_STATUSES or hold in {"hold", "leased", "parked"}:
            return f"lifecycle:{hold}"
    return None


def _idle_hours(path: Path, now: datetime) -> float:
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (now - mtime).total_seconds() / 3600.0


def _session_paths(hub_root: Path) -> dict[str, Path]:
    primary = agent_sessions_dir(hub_root)
    legacy = legacy_data_path(hub_root, "agent_sessions")
    paths: dict[str, Path] = {}
    if legacy.exists() and legacy != primary:
        for path in legacy.glob("*.json"):
            paths[path.name] = path
    if primary.exists():
        for path in primary.glob("*.json"):
            paths[path.name] = path
    return paths


def build_agent_session_reaper_report(
    hub_root: Path,
    *,
    repository: Path | None = None,
    idle_live_hours: float = DEFAULT_IDLE_LIVE_HOURS,
    keep_session_ids: frozenset[str] | set[str] | None = None,
    preservation_pointer: str = DEFAULT_PRESERVATION_POINTER,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify open sessions for a dry-run reaper report (no mutation)."""

    if idle_live_hours <= 0:
        raise ValueError("idle_live_hours must be > 0")
    observed = now or utc_now()
    if isinstance(observed, datetime):
        observed_at_dt = observed.astimezone(timezone.utc)
        observed_at = observed_at_dt.isoformat()
    else:
        observed_at = str(observed)
        observed_at_dt = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if observed_at_dt.tzinfo is None:
            observed_at_dt = observed_at_dt.replace(tzinfo=timezone.utc)

    keep = {str(item) for item in (keep_session_ids or ())}
    root, mode = resolve_data_root(hub_root)
    repo_filter = repository.resolve() if repository is not None else None

    candidates: list[dict[str, Any]] = []
    counts = {
        "open_considered": 0,
        "candidate_close": 0,
        "skipped_live": 0,
        "skipped_exception": 0,
        "skipped_keep": 0,
        "parse_error": 0,
        "repo_mismatch": 0,
    }

    for name, path in sorted(_session_paths(hub_root).items()):
        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            counts["parse_error"] += 1
            candidates.append(
                {
                    "session_file": name,
                    "session_id": None,
                    "path": str(path),
                    "classification": "parse_error",
                    "tier": None,
                    "idle_hours": None,
                    "exception_reason": None,
                    "proposed_summary": None,
                    "proposed_action": "none",
                }
            )
            continue
        if not isinstance(payload, dict):
            counts["parse_error"] += 1
            candidates.append(
                {
                    "session_file": name,
                    "session_id": None,
                    "path": str(path),
                    "classification": "parse_error",
                    "tier": None,
                    "idle_hours": None,
                    "exception_reason": None,
                    "proposed_summary": None,
                    "proposed_action": "none",
                }
            )
            continue
        status = str(payload.get("status", "") or "").strip().lower()
        if status != "open":
            continue
        if repo_filter is not None:
            try:
                session_repo = Path(str(payload.get("repository", "") or "")).resolve()
            except OSError:
                session_repo = None
            if session_repo != repo_filter:
                counts["repo_mismatch"] += 1
                continue

        sid = str(payload.get("session_id") or f"dad:session:{path.stem}")
        try:
            idle_h = round(_idle_hours(path, observed_at_dt), 2)
        except OSError:
            counts["parse_error"] += 1
            candidates.append(
                {
                    "session_file": name,
                    "session_id": sid,
                    "path": str(path),
                    "classification": "parse_error",
                    "tier": None,
                    "idle_hours": None,
                    "exception_reason": None,
                    "proposed_summary": None,
                    "proposed_action": "none",
                }
            )
            continue

        counts["open_considered"] += 1

        row: dict[str, Any] = {
            "session_file": name,
            "session_id": sid,
            "path": str(path),
            "agent": payload.get("agent"),
            "task": (str(payload.get("task", "") or "")[:200] or None),
            "repository": payload.get("repository"),
            "tier": classify_session_tier(payload),
            "idle_hours": idle_h,
            "idle_live_hours_threshold": idle_live_hours,
            "exception_reason": None,
            "proposed_summary": None,
            "proposed_action": "none",
            "classification": "skipped_live",
        }

        if sid in keep:
            row["classification"] = "skipped_keep"
            counts["skipped_keep"] += 1
            candidates.append(row)
            continue

        exception = _parse_exception_reason(payload)
        if exception:
            row["classification"] = "skipped_exception"
            row["exception_reason"] = exception
            counts["skipped_exception"] += 1
            candidates.append(row)
            continue

        if idle_h < idle_live_hours:
            row["classification"] = "skipped_live"
            counts["skipped_live"] += 1
            candidates.append(row)
            continue

        row["classification"] = "candidate_close"
        row["proposed_action"] = "administrative_postflight_if_apply_approved"
        row["proposed_summary"] = proposed_close_summary(
            payload,
            idle_hours=idle_h,
            idle_live_hours=idle_live_hours,
            preservation_pointer=preservation_pointer,
        )
        counts["candidate_close"] += 1
        candidates.append(row)

    report_id = stable_id(
        "dad:agent-session-reaper",
        observed_at,
        mode,
        str(repo_filter or ""),
        json_dumps(counts),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed_at,
        "report_id": report_id,
        "status": "generated_candidate",
        "method_id": METHOD_ID,
        "model_call_count": 0,
        "model_token_count": 0,
        "candidate_only": True,
        "execution_authorized": False,
        "apply_authorized": False,
        "dry_run": True,
        "data_classification": "local_private_metadata",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "liveness_rule": {
            "signal": "session_file_mtime",
            "idle_live_hours": idle_live_hours,
            "note": "Session file idle time is the liveness signal; created_at is not.",
        },
        "preservation_pointer": preservation_pointer.strip() or DEFAULT_PRESERVATION_POINTER,
        "data_plane": {
            "mode": mode,
            "data_root": str(root),
            "sessions_dir": str(agent_sessions_dir(hub_root)),
            "legacy_sessions_dir": str(legacy_data_path(hub_root, "agent_sessions")),
        },
        "scope": {
            "repository": str(repo_filter) if repo_filter else None,
            "keep_session_ids": sorted(keep),
        },
        "summary": counts,
        "candidates": candidates,
        "next_actions": [
            "Review candidate_close rows and skipped_exception reasons before any apply.",
            "Confirm preservation coverage for Tier-B sessions before approving apply.",
            "Do not close live or exception-held sessions; re-run dry-run after idle ages.",
        ],
        "routine_registration": {
            "routine_id": "dad-agent-session-reaper",
            "enabled": False,
            "scheduled": False,
        },
    }


def render_agent_session_reaper_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Agent session reaper dry-run report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- dry_run: `{report['dry_run']}`",
        f"- apply_authorized: `{report['apply_authorized']}`",
        f"- execution_authorized: `{report['execution_authorized']}`",
        f"- idle_live_hours: `{report['liveness_rule']['idle_live_hours']}`",
        "",
        "## Summary",
        "",
        f"- open_considered: `{summary['open_considered']}`",
        f"- candidate_close: `{summary['candidate_close']}`",
        f"- skipped_live: `{summary['skipped_live']}`",
        f"- skipped_exception: `{summary['skipped_exception']}`",
        f"- skipped_keep: `{summary['skipped_keep']}`",
        f"- parse_error: `{summary['parse_error']}`",
        f"- repo_mismatch: `{summary['repo_mismatch']}`",
        "",
        "## Preservation pointer",
        "",
        report["preservation_pointer"],
        "",
        "## Authority boundary",
        "",
        report["authority_boundary"],
        "",
    ]
    closes = [row for row in report["candidates"] if row["classification"] == "candidate_close"]
    if closes:
        lines.extend(["## Candidate closes (dry-run only)", ""])
        for row in closes[:50]:
            lines.append(
                f"- `{row['session_id']}` tier={row['tier']} idle={row['idle_hours']}h "
                f"file=`{row['session_file']}`"
            )
        lines.append("")
    return "\n".join(lines)


def write_agent_session_reaper_report(
    hub_root: Path,
    *,
    repository: Path | None = None,
    idle_live_hours: float = DEFAULT_IDLE_LIVE_HOURS,
    keep_session_ids: frozenset[str] | set[str] | None = None,
    preservation_pointer: str = DEFAULT_PRESERVATION_POINTER,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write dry-run report artifacts and a receipt JSONL row (no session mutation)."""

    report = build_agent_session_reaper_report(
        hub_root,
        repository=repository,
        idle_live_hours=idle_live_hours,
        keep_session_ids=keep_session_ids,
        preservation_pointer=preservation_pointer,
        now=now,
    )
    reports_dir = data_path(hub_root, "central_reports")
    cadence_dir = data_path(hub_root, "cadence")
    reports_dir.mkdir(parents=True, exist_ok=True)
    cadence_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    receipt_path = cadence_dir / RECEIPT_JSONL
    history_path = cadence_dir / HISTORY_JSONL
    atomic_write_text(json_path, json_dumps(report) + "\n")
    atomic_write_text(md_path, render_agent_session_reaper_markdown(report))
    receipt = {
        "recorded_at": report["generated_at"],
        "report_id": report["report_id"],
        "dry_run": True,
        "apply_authorized": False,
        "summary": report["summary"],
        "candidate_session_ids": [
            row["session_id"]
            for row in report["candidates"]
            if row["classification"] == "candidate_close" and row.get("session_id")
        ],
    }
    append_jsonl(receipt_path, receipt)
    append_jsonl(
        history_path,
        {
            "recorded_at": report["generated_at"],
            "report_id": report["report_id"],
            "summary": report["summary"],
        },
    )
    return {
        "report": report,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "receipt_path": str(receipt_path),
        "history_path": str(history_path),
    }
