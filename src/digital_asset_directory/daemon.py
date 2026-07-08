"""Local DAD daemon cycle orchestration.

The daemon is intentionally boring: it writes central status artifacts, never
discovers repos by itself, and only acts on repo rows supplied by reviewed
configuration.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .event_pipeline import collect_events
from .exceptions_lake import (
    collect_exception_events,
    collect_exception_fix_outcomes,
    write_exception_report,
)
from .graph_inference import write_inference_outputs
from .graph_surfaces import graph_surface_status
from .journal import checkpoint_journal, ingest_remote_outbox, journal_status
from .learning import build_lesson_graph
from .mail_center import collect_mail, deliver_mail, diagnose_mail_dirty_state, route_mail
from .transport import AUTHORITY_BOUNDARY, audit_all_repo_transport, data_path
from .utils import atomic_write_text, json_dumps, utc_now

DAEMON_HEARTBEAT_NAME = "daemon-heartbeat.json"
DAILY_REVIEW_QUEUE_MD = "daily_review_queue.md"
DAILY_REVIEW_QUEUE_JSON = "daily_review_queue.json"


def _reports_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports")


def daemon_heartbeat_path(hub_root: Path) -> Path:
    return _reports_dir(hub_root) / DAEMON_HEARTBEAT_NAME


def daily_review_queue_path(hub_root: Path) -> Path:
    return _reports_dir(hub_root) / DAILY_REVIEW_QUEUE_MD


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def daemon_status(hub_root: Path, *, stale_hours: int = 26) -> dict[str, Any]:
    heartbeat = daemon_heartbeat_path(hub_root)
    if not heartbeat.exists():
        return {
            "schema_version": "dad.daemon.status.v1",
            "generated_at": utc_now(),
            "status": "missing",
            "stale": True,
            "heartbeat_path": str(heartbeat),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    try:
        payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema_version": "dad.daemon.status.v1",
            "generated_at": utc_now(),
            "status": "invalid",
            "stale": True,
            "heartbeat_path": str(heartbeat),
            "error": str(exc),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    cycle_at = _parse_time(str(payload.get("cycle_completed_at") or ""))
    age_hours = None
    stale = True
    if cycle_at is not None:
        age_hours = max(0.0, (datetime.now(timezone.utc) - cycle_at).total_seconds() / 3600.0)
        stale = age_hours > stale_hours
    return {
        "schema_version": "dad.daemon.status.v1",
        "generated_at": utc_now(),
        "status": "stale" if stale else "fresh",
        "stale": stale,
        "heartbeat_path": str(heartbeat),
        "cycle_completed_at": payload.get("cycle_completed_at", ""),
        "age_hours": age_hours,
        "stale_after_hours": stale_hours,
        "daily_review_queue_path": payload.get("daily_review_queue", ""),
        "follow_through_status": payload.get("follow_through_status"),
        "follow_through_issue_count": payload.get("follow_through_issue_count"),
        "transport_audit_ran": payload.get("transport_audit_ran"),
        "journal_checkpoint_due": payload.get("journal_checkpoint_due"),
        "journal_checkpoint_applied": payload.get("journal_checkpoint_applied"),
        "journal_checkpoint_status": payload.get("journal_checkpoint_status", {}),
        "last_cycle": payload,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _write_daily_review_queue(
    hub_root: Path,
    *,
    generated_at: str,
    remote_outbox_result: dict[str, Any],
    mail_result: dict[str, Any],
    follow_through_result: dict[str, Any],
    event_result: dict[str, Any],
    exception_result: dict[str, Any],
    graph_result: dict[str, Any],
    graph_surface_status_result: dict[str, Any],
    transport_result: dict[str, Any] | None,
    journal_result: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "schema_version": "dad.daily_review_queue.v1",
        "generated_at": generated_at,
        "remote_outbox_ingest": remote_outbox_result,
        "mail": mail_result,
        "follow_through": follow_through_result,
        "events": event_result,
        "exceptions": exception_result,
        "graphs": graph_result,
        "graph_surfaces": graph_surface_status_result,
        "transport": transport_result or {"status": "not_run"},
        "journal": journal_result,
        "authority_boundary": (
            "Daily review queue is an attention surface over candidate data. It "
            "does not approve repo writes, public release, source truth, or "
            "roadmap human gates."
        ),
    }
    json_path = _reports_dir(hub_root) / DAILY_REVIEW_QUEUE_JSON
    atomic_write_text(json_path, json_dumps(report, pretty=True) + "\n")
    lines = [
        "# DAD Daily Review Queue",
        "",
        f"- Generated: {generated_at}",
        f"- Remote outbox ingest: {remote_outbox_result.get('status', 'unknown')}",
        f"- Remote outbox accepted: {remote_outbox_result.get('accepted_count', 'not run')}",
        f"- Remote outbox quarantined: {remote_outbox_result.get('quarantined_count', 'not run')}",
        f"- Mail collect: {mail_result.get('collect', {}).get('status', 'unknown')}",
        f"- Mail route: {mail_result.get('route', {}).get('status', 'unknown')}",
        f"- Mail delivery: {mail_result.get('deliver', {}).get('status', 'unknown')}",
        f"- Follow-through audit: {follow_through_result.get('audit_status', follow_through_result.get('status', 'unknown'))}",
        f"- Follow-through issues: {follow_through_result.get('issue_count', 'unknown')}",
        f"- Events collect: {event_result.get('collect', {}).get('status', event_result.get('status', 'unknown'))}",
        f"- Exceptions collect: {exception_result.get('status', 'unknown')}",
        f"- Lesson graph: {graph_result.get('lesson_graph', {}).get('status', 'unknown')}",
        f"- Graph inference: {graph_result.get('inference', {}).get('status', 'unknown')}",
        f"- Graph surface freshness: {graph_surface_status_result.get('freshness_counts', {})}",
        f"- Transport audit: {transport_result.get('report_path', 'not run') if transport_result else 'not run'}",
        f"- Transport upgrade count: {transport_result.get('upgrade_required_count', 'not run') if transport_result else 'not run'}",
        f"- Journal checkpoint due: {journal_result.get('checkpoint_due')}",
        f"- Journal new records: {journal_result.get('new_record_count')}",
        f"- Journal status: {journal_result.get('checkpoint_skipped_reason', 'ready_or_applied')}",
        "",
        "Boundary: this is an attention queue over candidate data. It does not "
        "authorize downstream repo writes, public release, source truth, or "
        "human-gate completion.",
        "",
    ]
    md_path = daily_review_queue_path(hub_root)
    atomic_write_text(md_path, "\n".join(lines))
    return {"json_path": str(json_path), "markdown_path": str(md_path), "report": report}


def _step_result(name: str, func, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        result = func(*args, **kwargs)
    except Exception as exc:
        return {
            "status": "error",
            "step": name,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    if isinstance(result, dict):
        return {"status": "ok", "step": name, **result}
    return {"status": "ok", "step": name, "result": result}


def _run_mail_cycle(
    hub_root: Path,
    *,
    mail_repos: Sequence[Any] | None,
    deliver_local_caches: bool,
) -> dict[str, Any]:
    if mail_repos is None:
        return {
            "status": "skipped",
            "reason": "mail_repos_not_provided",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    collect_repos = [
        policy.path.resolve()
        for policy in mail_repos
        if bool(getattr(policy, "mail_enabled", True))
    ]
    delivery_repos = [
        policy.path.resolve()
        for policy in mail_repos
        if bool(getattr(policy, "mail_enabled", True))
        and bool(getattr(policy, "delivery_allowed", True))
    ]
    collect_result = _step_result(
        "mail_collect",
        collect_mail,
        hub_root,
        collect_repos,
        repo_policies=mail_repos,
    )
    route_result = _step_result(
        "mail_route",
        route_mail,
        hub_root,
        repo_policies=mail_repos,
    )
    if deliver_local_caches:
        deliver_result = _step_result(
            "mail_deliver",
            deliver_mail,
            hub_root,
            delivery_repos,
            repo_policies=mail_repos,
            require_target_policy=True,
        )
    else:
        deliver_result = {
            "status": "skipped",
            "step": "mail_deliver",
            "reason": "requires_deliver_local_caches_flag",
            "reviewed_delivery_repo_count": len(delivery_repos),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    return {
        "status": "ok",
        "collect_repo_count": len(collect_repos),
        "delivery_repo_count": len(delivery_repos),
        "collect": collect_result,
        "route": route_result,
        "deliver": deliver_result,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _run_follow_through_audit(
    hub_root: Path,
    *,
    mail_repos: Sequence[Any] | None,
) -> dict[str, Any]:
    if mail_repos is None:
        return {
            "status": "skipped",
            "step": "mail_follow_through_audit",
            "reason": "mail_repos_not_provided",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    repos = [
        policy.path.resolve()
        for policy in mail_repos
        if bool(getattr(policy, "mail_enabled", True))
    ]
    try:
        result = diagnose_mail_dirty_state(
            hub_root,
            repos,
            repo_policies=mail_repos,
        )
    except Exception as exc:
        return {
            "status": "error",
            "step": "mail_follow_through_audit",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    issues = [issue for issue in result.get("issues", []) if isinstance(issue, dict)]
    issue_types: dict[str, int] = {}
    for issue in issues:
        issue_type = str(issue.get("issue_type", "unknown") or "unknown")
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
    return {
        "status": "ok",
        "step": "mail_follow_through_audit",
        "audit_status": result.get("status", "unknown"),
        "dirty": bool(result.get("dirty")),
        "spool_dirty": bool(result.get("spool_dirty", result.get("dirty"))),
        "worktree_dirty": bool(result.get("worktree_dirty")),
        "issue_count": len(issues),
        "issue_types": dict(sorted(issue_types.items())),
        "summary": result.get("summary", {}),
        "repo_scope": result.get("repo_scope", {}),
        "action_summary": result.get("action_summary", {}),
        "authority_boundary": (
            "Follow-through audit is a read-only mailbox/route-audit diagnostic. "
            "It does not collect, route, deliver, repair, review, promote, or "
            "write target repos."
        ),
    }


def _run_remote_outbox_ingest(
    hub_root: Path,
    *,
    journal_repo: Path | None,
) -> dict[str, Any]:
    if journal_repo is None:
        return {
            "status": "skipped",
            "step": "journal_remote_outbox_ingest",
            "reason": "journal_repo_not_configured",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    return _step_result(
        "journal_remote_outbox_ingest",
        ingest_remote_outbox,
        hub_root,
        journal_repo,
    )


def _run_graph_cycle(hub_root: Path) -> dict[str, Any]:
    return {
        "status": "ok",
        "lesson_graph": _step_result("lesson_graph", build_lesson_graph, hub_root),
        "inference": _step_result("graph_inference", write_inference_outputs, hub_root),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _run_event_cycle(
    hub_root: Path, *, mail_repos: Sequence[Any] | None
) -> dict[str, Any]:
    if mail_repos is None:
        return {
            "status": "skipped",
            "reason": "mail_repos_not_provided",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    repos = [
        policy.path.resolve()
        for policy in mail_repos
        if bool(getattr(policy, "mail_enabled", True))
    ]
    return {
        "status": "ok",
        "repo_count": len(repos),
        "collect": _step_result(
            "events_collect",
            collect_events,
            hub_root,
            repos,
            repo_policies=mail_repos,
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _collect_exceptions_for_repos(
    hub_root: Path,
    repos: list[Path],
    repo_policies: Sequence[Any],
) -> dict[str, Any]:
    event_results = []
    fix_outcome_results = []
    for repo in repos:
        event_results.append(
            collect_exception_events(
                hub_root,
                repo,
                repo_policies=repo_policies,
            )
        )
        fix_outcome_results.append(
            collect_exception_fix_outcomes(
                hub_root,
                repo,
                repo_policies=repo_policies,
            )
        )
    report = write_exception_report(hub_root) if repos else None
    return {
        "repo_count": len(repos),
        "results": event_results,
        "fix_outcome_results": fix_outcome_results,
        "report": report,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _run_exception_cycle(
    hub_root: Path, *, exception_repos: Sequence[Any] | None
) -> dict[str, Any]:
    if exception_repos is None:
        return {
            "status": "skipped",
            "reason": "exception_repos_not_provided",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    repos = [
        policy.path.resolve()
        for policy in exception_repos
        if bool(getattr(policy, "exceptions_enabled", True))
        and bool(getattr(policy, "collect_allowed", True))
    ]
    return _step_result(
        "exceptions_collect",
        _collect_exceptions_for_repos,
        hub_root,
        repos,
        exception_repos,
    )


def run_daemon_cycle(
    hub_root: Path,
    *,
    mail_repos: Sequence[Any] | None = None,
    exception_repos: Sequence[Any] | None = None,
    deliver_local_caches: bool = False,
    rebuild_graphs: bool = True,
    transport_repos: list[dict[str, Any]] | None = None,
    journal_repo: Path | None = None,
    checkpoint_apply: bool = False,
) -> dict[str, Any]:
    generated_at = utc_now()
    cycle_order = [
        "journal_remote_outbox_ingest",
        "mail_collect",
        "mail_route",
        "mail_deliver",
        "mail_follow_through_audit",
        "events_collect",
        "exceptions_collect",
        "lesson_graph_rebuild",
        "graph_inference",
        "transport_audit",
        "daily_review_queue",
        "heartbeat",
        "journal_checkpoint",
    ]
    remote_outbox_result = _run_remote_outbox_ingest(
        hub_root,
        journal_repo=journal_repo,
    )
    mail_result = _run_mail_cycle(
        hub_root,
        mail_repos=mail_repos,
        deliver_local_caches=deliver_local_caches,
    )
    follow_through_result = _run_follow_through_audit(
        hub_root,
        mail_repos=mail_repos,
    )
    event_result = _run_event_cycle(hub_root, mail_repos=mail_repos)
    exception_result = _run_exception_cycle(hub_root, exception_repos=exception_repos)
    graph_result = (
        _run_graph_cycle(hub_root)
        if rebuild_graphs
        else {
            "status": "skipped",
            "reason": "rebuild_graphs_false",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    )
    transport_result = (
        audit_all_repo_transport(hub_root, transport_repos)
        if transport_repos is not None
        else None
    )
    journal_status_result = journal_status(hub_root)
    graph_surface_status_result = graph_surface_status(hub_root)
    review_queue = _write_daily_review_queue(
        hub_root,
        generated_at=generated_at,
        remote_outbox_result=remote_outbox_result,
        mail_result=mail_result,
        follow_through_result=follow_through_result,
        event_result=event_result,
        exception_result=exception_result,
        graph_result=graph_result,
        graph_surface_status_result=graph_surface_status_result,
        transport_result=transport_result,
        journal_result=journal_status_result,
    )
    heartbeat = {
        "schema_version": "dad.daemon.heartbeat.v1",
        "cycle_started_at": generated_at,
        "cycle_completed_at": utc_now(),
        "cycle_order": cycle_order,
        "remote_outbox_ingest_status": remote_outbox_result.get("status"),
        "mail_collect_status": mail_result.get("collect", {}).get("status", mail_result.get("status")),
        "mail_route_status": mail_result.get("route", {}).get("status", mail_result.get("status")),
        "mail_deliver_status": mail_result.get("deliver", {}).get("status", mail_result.get("status")),
        "follow_through_status": follow_through_result.get("audit_status", follow_through_result.get("status")),
        "follow_through_issue_count": follow_through_result.get("issue_count"),
        "events_collect_status": event_result.get("collect", {}).get("status", event_result.get("status")),
        "exceptions_collect_status": exception_result.get("status"),
        "lesson_graph_status": graph_result.get("lesson_graph", {}).get("status", graph_result.get("status")),
        "graph_inference_status": graph_result.get("inference", {}).get("status", graph_result.get("status")),
        "graph_surface_freshness_counts": graph_surface_status_result.get("freshness_counts", {}),
        "transport_audit_ran": transport_result is not None,
        "journal_checkpoint_due": journal_status_result.get("checkpoint_due"),
        "journal_checkpoint_applied": False,
        "journal_checkpoint_status": journal_status_result,
        "daily_review_queue": review_queue["markdown_path"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_text(daemon_heartbeat_path(hub_root), json_dumps(heartbeat, pretty=True) + "\n")
    journal_result = checkpoint_journal(
        hub_root,
        journal_repo,
        apply=checkpoint_apply,
    )
    return {
        "schema_version": "dad.daemon.cycle.v1",
        "generated_at": generated_at,
        "cycle_order": cycle_order,
        "heartbeat_path": str(daemon_heartbeat_path(hub_root)),
        "daily_review_queue": review_queue,
        "remote_outbox_ingest": remote_outbox_result,
        "mail": mail_result,
        "follow_through": follow_through_result,
        "events": event_result,
        "exceptions": exception_result,
        "graphs": graph_result,
        "graph_surface_status": graph_surface_status_result,
        "transport": transport_result,
        "journal_status": journal_status_result,
        "journal": journal_result,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def task_scheduler_plan(
    hub_root: Path,
    *,
    task_name: str = "DAD Daemon Run Cycle",
    schedule_time: str = "09:00",
    twice_daily: bool = False,
    shim: Path | None = None,
) -> dict[str, Any]:
    shim_path = shim or Path.home() / ".dad" / "bin" / "asset-dir.ps1"
    tr = "HOURLY" if twice_daily else "DAILY"
    mo = "12" if twice_daily else "1"
    command = (
        f'schtasks /Create /TN "{task_name}" /SC {tr} /MO {mo} /ST {schedule_time} '
        f'/TR "powershell -NoProfile -ExecutionPolicy Bypass -File '
        f"'{shim_path}' daemon run-cycle --hub '{hub_root.resolve()}'\" /F"
    )
    return {
        "schema_version": "dad.daemon.task_scheduler_plan.v1",
        "task_name": task_name,
        "schedule_time": schedule_time,
        "twice_daily": twice_daily,
        "shim": str(shim_path),
        "command": command,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def install_task_scheduler(plan: dict[str, Any]) -> dict[str, Any]:
    command = str(plan["command"])
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
    return {
        **plan,
        "installed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _parse_schtasks_list_output(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = key.strip().lower().replace(" ", "_")
        if normalized:
            parsed[normalized] = value.strip()
    return parsed


def task_scheduler_status(
    hub_root: Path,
    *,
    task_name: str = "DAD Daemon Run Cycle",
    shim: Path | None = None,
    runner: Any | None = None,
) -> dict[str, Any]:
    """Read-only Windows Task Scheduler verification for the daemon task."""
    query_args = ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"]
    runner = runner or subprocess.run
    try:
        result = runner(query_args, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        return {
            "schema_version": "dad.daemon.task_scheduler_status.v1",
            "task_name": task_name,
            "query_command": 'schtasks /Query /TN "{name}" /FO LIST /V'.format(
                name=task_name
            ),
            "installed": False,
            "status": "unavailable",
            "error": str(exc),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }

    stdout = str(getattr(result, "stdout", "") or "")
    stderr = str(getattr(result, "stderr", "") or "")
    returncode = int(getattr(result, "returncode", 1))
    parsed = _parse_schtasks_list_output(stdout)
    task_to_run = parsed.get("task_to_run", "")
    hub_text = str(hub_root.resolve())
    shim_text = str((shim or Path.home() / ".dad" / "bin" / "asset-dir.ps1"))
    installed = returncode == 0
    return {
        "schema_version": "dad.daemon.task_scheduler_status.v1",
        "task_name": task_name,
        "query_command": 'schtasks /Query /TN "{name}" /FO LIST /V'.format(
            name=task_name
        ),
        "installed": installed,
        "status": "installed" if installed else "missing",
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "task_status": parsed.get("status", ""),
        "next_run_time": parsed.get("next_run_time", ""),
        "task_to_run": task_to_run,
        "command_mentions_run_cycle": "daemon run-cycle" in task_to_run,
        "expected_hub_found": hub_text in task_to_run,
        "expected_shim_found": shim_text in task_to_run,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
