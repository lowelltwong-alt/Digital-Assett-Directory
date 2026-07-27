"""Session boot verb: bring DAD to a fresh, verified state in one command.

The boot report is candidate status evidence only. It surfaces freshness of the
data root, backup journal, daemon heartbeat, cockpit, and restore drill, runs
the backup checkpoint when it is due, and translates Today attention items into
plain language. It proposes next actions; it never mutates scheduled tasks,
enrollment surfaces, or other repositories.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .daemon import daemon_status
from .journal import (
    checkpoint_journal,
    default_journal_repo,
    journal_status,
    restore_drill_status,
)
from .transport import (
    AUTHORITY_BOUNDARY,
    _looks_like_onedrive,
    data_path,
    resolve_data_root,
)
from .utils import atomic_write_text, json_dumps, utc_now

BOOT_HEALTH_SCHEMA_VERSION = "dad.boot_health.v1"
BOOT_HEALTH_NAME = "boot_health.json"
# Fixed freshness thresholds, ages are raw hour/day deltas with no scoring.
DAEMON_STALE_HOURS = 26
RESTORE_DRILL_DUE_DAYS = 90
COCKPIT_STALE_HOURS = 26
TODAY_LIMIT = 3

_REASON_TRANSLATIONS = {
    "conflicted_worktree": "has a merge conflict",
    "dirty_worktree_idle": "has unsaved work sitting idle",
    "diverged_from_upstream": "local and GitHub copies have drifted apart",
    "stale_branch": "has not moved in a while",
    "stale_branch_in_active_project": "is an old branch in an active project",
    "unpushed_or_unmerged_commits": "has work that is not on GitHub yet",
    "merged_branch_cleanup_candidate": "was merged and can be tidied away",
    "upstream_gone": "lost its matching GitHub branch",
}


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_hours(value: str, *, now: datetime) -> float | None:
    parsed = _parse_utc(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600.0)


def plain_reasons(reasons: list[str], *, limit: int = 2) -> str:
    """Translate cockpit reason codes into plain language."""

    translated = [
        _REASON_TRANSLATIONS.get(reason, reason.replace("_", " "))
        for reason in reasons[:limit]
        if isinstance(reason, str) and reason
    ]
    return " and ".join(translated)


def data_root_guard(hub_root: Path, *, allow_onedrive: bool = False) -> dict[str, Any]:
    """Refuse to boot on a OneDrive-synced data root unless explicitly allowed."""

    root, mode = resolve_data_root(hub_root)
    onedrive = _looks_like_onedrive(root)
    blocked = onedrive and not allow_onedrive
    guard: dict[str, Any] = {
        "data_root": str(root),
        "mode": mode,
        "onedrive": onedrive,
        "status": "blocked" if blocked else "ok",
    }
    if blocked:
        guard["plain_language"] = (
            "Your DAD data lives inside a OneDrive-synced folder. OneDrive sync "
            "locks corrupt live databases. Move it out with: asset-dir data init "
            "then asset-dir data migrate (or re-run with --allow-onedrive-data-root "
            "to accept the risk this once)."
        )
    return guard


def today_items(hub_root: Path, *, now: datetime, limit: int = TODAY_LIMIT) -> dict[str, Any]:
    """Read the portfolio cockpit Today list without mutating anything."""

    cockpit_path = data_path(hub_root, "central_reports") / "portfolio_os" / "cockpit.json"
    summary: dict[str, Any] = {"path": str(cockpit_path), "items": []}
    if not cockpit_path.is_file():
        summary["status"] = "missing"
        return summary
    try:
        payload = json.loads(cockpit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        summary["status"] = "invalid"
        return summary
    if not isinstance(payload, dict) or not isinstance(payload.get("today"), list):
        summary["status"] = "invalid"
        return summary
    generated_at = str(payload.get("generated_at") or "")
    summary["generated_at"] = generated_at
    summary["age_hours"] = _age_hours(generated_at, now=now)
    summary["status"] = "ok"
    for row in payload["today"][:limit]:
        if not isinstance(row, dict):
            continue
        reasons = row.get("reasons") if isinstance(row.get("reasons"), list) else []
        summary["items"].append(
            {
                "project_name": str(row.get("project_name") or ""),
                "label": str(row.get("label") or ""),
                "inactive_days": row.get("inactive_days"),
                "plain_reason": plain_reasons(reasons),
                "next_action": str(row.get("next_action") or ""),
            }
        )
    return summary


def _journal_section(
    hub_root: Path,
    *,
    journal_repo: Path | None,
    apply_checkpoint: bool,
) -> dict[str, Any]:
    resolved_repo = journal_repo or default_journal_repo()
    section: dict[str, Any] = {
        "journal_repo": str(resolved_repo) if resolved_repo else "",
        "journal_repo_source": (
            "explicit"
            if journal_repo
            else ("autodiscovered" if resolved_repo else "not_found")
        ),
    }
    try:
        if apply_checkpoint:
            result = checkpoint_journal(hub_root, resolved_repo, apply=True)
        else:
            result = journal_status(hub_root)
    except (OSError, RuntimeError, ValueError) as exc:
        section["status"] = "error"
        section["error"] = str(exc)
        return section
    for key in (
        "status",
        "last_checkpoint_at",
        "hours_since_checkpoint",
        "checkpoint_due",
        "checkpoint_applied",
        "checkpoint_skipped_reason",
        "git_transaction_error",
        "new_record_count",
    ):
        if key in result:
            section[key] = result[key]
    return section


def run_boot(
    hub_root: Path,
    *,
    journal_repo: Path | None = None,
    apply_checkpoint: bool = True,
    allow_onedrive: bool = False,
    cockpit_refresher: Callable[[], dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assemble and persist the boot health report; return it."""

    started = time.perf_counter()
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    report: dict[str, Any] = {
        "schema_version": BOOT_HEALTH_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "candidate_only": True,
        "thresholds": {
            "daemon_stale_hours": DAEMON_STALE_HOURS,
            "restore_drill_due_days": RESTORE_DRILL_DUE_DAYS,
            "cockpit_stale_hours": COCKPIT_STALE_HOURS,
            "today_limit": TODAY_LIMIT,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    attention: list[str] = []

    guard = data_root_guard(hub_root, allow_onedrive=allow_onedrive)
    report["data_root"] = guard
    if guard["status"] == "blocked":
        report["status"] = "blocked"
        report["attention"] = [guard["plain_language"]]
        report["boot_duration_seconds"] = round(time.perf_counter() - started, 3)
        return report
    if guard["onedrive"]:
        attention.append(
            "Data root is inside OneDrive and boot was forced with "
            "--allow-onedrive-data-root; plan the migration out soon."
        )

    journal = _journal_section(
        hub_root, journal_repo=journal_repo, apply_checkpoint=apply_checkpoint
    )
    report["journal"] = journal
    if not journal["journal_repo"]:
        attention.append(
            "No backup journal repo found at ~/.dad/dad-journal, so your DAD data "
            "has no versioned backup. Decide where the journal repo should live."
        )
    elif journal.get("status") == "error":
        attention.append(
            "The backup checkpoint hit an error and did not complete: "
            f"{journal.get('error', 'unknown')}. Your data is unchanged; re-run "
            "asset-dir journal checkpoint --apply once the cause is fixed."
        )
    elif journal.get("checkpoint_applied"):
        pass  # backed up during this boot; nothing to flag
    elif journal.get("status") == "blocked":
        attention.append(
            "The backup checkpoint was blocked "
            f"({journal.get('checkpoint_skipped_reason', 'unknown reason')}). "
            "Your previous backups are intact, but no new one was taken."
        )
    else:
        hours = journal.get("hours_since_checkpoint")
        if isinstance(hours, (int, float)) and hours > 48:
            attention.append(
                f"The last data backup is {hours:.0f} hours old. Boot normally "
                "takes one automatically; run asset-dir journal checkpoint --apply "
                "if this persists."
            )

    daemon = daemon_status(hub_root, stale_hours=DAEMON_STALE_HOURS)
    report["daemon"] = {
        "status": daemon.get("status", ""),
        "stale": bool(daemon.get("stale", True)),
        "age_hours": daemon.get("age_hours"),
    }
    if report["daemon"]["stale"]:
        attention.append(
            "The background helper has not completed a cycle recently. "
            "Run: asset-dir daemon run-cycle --quiet"
        )

    cockpit_refresh: dict[str, Any] = {"status": "skipped"}
    if cockpit_refresher is not None:
        try:
            cockpit_refresh = cockpit_refresher()
        except Exception as exc:  # surface, never crash boot on cockpit refresh
            cockpit_refresh = {"status": "error", "error": str(exc)}
    report["cockpit_refresh"] = {
        "status": str(cockpit_refresh.get("status", "unknown")),
    }
    if report["cockpit_refresh"]["status"] not in {"refreshed", "skipped"}:
        attention.append(
            "The cockpit refresh did not complete; the Today list below may be "
            "stale. Run: asset-dir os cockpit-refresh-now"
        )

    today = today_items(hub_root, now=observed)
    report["today"] = today
    if today["status"] != "ok":
        attention.append(
            "No readable Today list yet. Run: asset-dir os cockpit-refresh-now"
        )
    else:
        age = today.get("age_hours")
        if isinstance(age, (int, float)) and age > COCKPIT_STALE_HOURS:
            attention.append(
                f"The Today list is {age:.0f} hours old; treat it as a sketch, "
                "not the current state."
            )

    drill = restore_drill_status(hub_root)
    drill_section: dict[str, Any] = {"status": str(drill.get("status", "never_run"))}
    drill_age_days = None
    generated = str(drill.get("generated_at") or "")
    age_hours = _age_hours(generated, now=observed)
    if age_hours is not None:
        drill_age_days = age_hours / 24.0
        drill_section["age_days"] = round(drill_age_days, 1)
    drill_section["due"] = (
        drill_section["status"] != "verified"
        or drill_age_days is None
        or drill_age_days > RESTORE_DRILL_DUE_DAYS
    )
    report["restore_drill"] = drill_section
    if drill_section["status"] == "never_run":
        attention.append(
            "Backups exist but a restore has never been proven. "
            "Run: asset-dir journal restore-drill"
        )
    elif drill_section["status"] != "verified":
        attention.append(
            "The last restore drill did not pass; the backup may not restore "
            "cleanly. Run: asset-dir journal restore-drill"
        )
    elif drill_section["due"]:
        attention.append(
            "The last proven restore is over "
            f"{RESTORE_DRILL_DUE_DAYS} days old. Run: asset-dir journal restore-drill"
        )

    report["status"] = "ok" if not attention else "attention"
    report["attention"] = attention
    report["boot_duration_seconds"] = round(time.perf_counter() - started, 3)
    health_path = data_path(hub_root, "central_reports") / BOOT_HEALTH_NAME
    report["report_path"] = str(health_path)
    atomic_write_text(health_path, json_dumps(report, pretty=True) + "\n")
    return report


def render_boot_text(report: dict[str, Any]) -> list[str]:
    """Render the boot report as plain-language ASCII terminal lines."""

    lines: list[str] = []
    status = report.get("status", "unknown")
    if status == "blocked":
        lines.append("DAD did not start.")
        lines.extend(f"  [!!] {line}" for line in report.get("attention", []))
        return lines

    duration = report.get("boot_duration_seconds")
    duration_text = f" in {duration:.1f}s" if isinstance(duration, (int, float)) else ""
    lines.append(f"DAD is up{duration_text}.")

    journal = report.get("journal", {})
    if journal.get("checkpoint_applied"):
        lines.append("  [OK] Data backed up just now (checkpoint applied).")
    else:
        hours = journal.get("hours_since_checkpoint")
        if isinstance(hours, (int, float)):
            marker = "[OK]" if hours <= 48 else "[!!]"
            lines.append(f"  {marker} Last data backup: {hours:.0f} hours ago.")
        else:
            lines.append("  [!!] Backup state unknown.")

    daemon = report.get("daemon", {})
    lines.append(
        "  [OK] Background helper is fresh."
        if not daemon.get("stale", True)
        else "  [!!] Background helper is stale."
    )

    drill = report.get("restore_drill", {})
    if drill.get("status") == "verified" and not drill.get("due"):
        lines.append("  [OK] Backup restore was proven recently.")
    else:
        lines.append("  [!!] Backup restore not proven recently.")

    today = report.get("today", {})
    items = today.get("items", []) if isinstance(today, dict) else []
    if items:
        lines.append("Today (top 3, nothing else needs you):")
        for index, item in enumerate(items, start=1):
            name = item.get("project_name") or item.get("label") or "(unnamed)"
            reason = item.get("plain_reason") or "needs a look"
            lines.append(f"  {index}. {name} - {reason}.")
            action = item.get("next_action")
            if action:
                lines.append(f"     Next: {action}")
    else:
        lines.append("Today: nothing is waiting on you.")

    remaining = report.get("attention", [])
    if remaining:
        lines.append("Needs a decision or a quick command:")
        lines.extend(f"  [!!] {line}" for line in remaining)
    return lines
