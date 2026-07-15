"""Local DAD daemon cycle orchestration.

The daemon is intentionally boring: it writes central status artifacts, never
discovers repos by itself, and only acts on repo rows supplied by reviewed
configuration.
"""

from __future__ import annotations

import json
import hashlib
import re
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
from .logos_write_guard import assert_dad_write_allowed
from .graph_surfaces import graph_surface_status
from .journal import checkpoint_journal, ingest_remote_outbox, journal_status
from .learning import build_lesson_graph
from .logos_llos import LOGOS_LLOS_SURFACES, POLICY_PATH, audit_logos_llos
from .lesson_automation_coverage import (
    weekly_asset_coverage_due,
    write_weekly_asset_coverage_outputs,
)
from .mail_center import collect_mail, deliver_mail, diagnose_mail_dirty_state, route_mail
from .subagent_evaluations import build_improvement_review
from .transport import AUTHORITY_BOUNDARY, audit_all_repo_transport, data_path, data_relative_path
from .utils import atomic_write_text, json_dumps, sha256_file, utc_now

DAEMON_HEARTBEAT_NAME = "daemon-heartbeat.json"
DAILY_REVIEW_QUEUE_MD = "daily_review_queue.md"
DAILY_REVIEW_QUEUE_JSON = "daily_review_queue.json"
DAEMON_TASK_WRAPPER_NAME = "dad-daemon-run-cycle.ps1"
DAEMON_TASK_LAST_RUN_LOG = "daemon-task-last-run.log"
DAEMON_TASK_LAST_RUN_STATUS = "daemon-task-last-run.json"
SCHEDULED_TASKS_REPORT_NAME = "scheduled_tasks.json"

_DAEMON_REAL_FIRM_PRIVACY_GATES = (
    "approved_redaction_and_minimization",
    "role_based_access_control",
    "retention_and_secure_deletion",
    "tenant_and_matter_isolation",
    "privacy_leak_and_adversarial_tests",
    "approved_logging_and_incident_response",
)


def daemon_reporting_privacy() -> dict[str, Any]:
    """Return the deployment boundary carried by every daemon status surface."""
    return {
        "schema_version": "dad.daemon.reporting_privacy.v1",
        "approved_scope": "synthetic_or_mock_only",
        "data_classification": "synthetic_development_only",
        "real_client_data_approved": False,
        "real_client_data_gate": {
            "id": "daemon-real-client-data-approved",
            "status": "blocked",
        },
        "risk": (
            "Daemon reports and logs may expose repository paths, payload metadata, "
            "review context, or client data if deployed inside a real firm."
        ),
        "required_before_real_firm_use": list(_DAEMON_REAL_FIRM_PRIVACY_GATES),
    }


def _reports_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports")


_CYCLE_INPUT_RELATIVE_PATHS = (
    ".digital-asset/mail/outbox.jsonl",
    ".digital-asset/exceptions/outbox.jsonl",
    ".digital-asset/events/outbox.jsonl",
    "processed/exceptions/fix-outcomes/outcomes.jsonl",
    "governance/LOGOS_LEARNING_LOOP_OPERATING_STANDARD.yaml",
    "governance/registry/LLOS_ROUTE_REGISTRY.yaml",
    ".ai/control/llos_v1_adapter.yaml",
    ".ai/control/llos_v1_lesson_index.yaml",
    "governance/LLOS_STANDARD_MIRROR.yaml",
    "governance/LLOS_LESSON_INDEX.yaml",
    "governance/llos_v1_adapter.yaml",
    "governance/llos_v1_lesson_index.yaml",
    ".digital-asset/dad-write-policy.json",
)
_SUBAGENT_CYCLE_INPUT_PATHS = (
    "raw/agent-evaluations/role-profile-revisions.jsonl",
    "raw/agent-evaluations/execution-attempts.jsonl",
    "raw/agent-evaluations/attempt-evaluations.jsonl",
    "raw/agent-evaluations/unrated-inventory.jsonl",
)
_CONTROL_HASH_MAX_BYTES = 1024 * 1024
_MATERIAL_ERROR_STATUSES = {"blocked", "error", "failed", "invalid"}


def _fingerprint_row(owner: str, relative: str, path: Path) -> tuple[Any, ...] | None:
    """Hash small control files so same-size/same-mtime edits still wake the daemon."""
    try:
        stat = path.stat()
    except OSError:
        return None
    row: tuple[Any, ...] = (owner, relative, stat.st_size, stat.st_mtime_ns)
    if stat.st_size <= _CONTROL_HASH_MAX_BYTES and path.suffix.casefold() != ".jsonl":
        try:
            row = (*row, sha256_file(path))
        except OSError:
            return None
    return row


def _material_error_paths(value: Any, *, path: str = "cycle") -> list[str]:
    """Find nested material step errors without treating absent/skipped work as failure."""
    found: list[str] = []
    if isinstance(value, dict):
        if ".reporting_privacy" in path:
            return []
        status = value.get("status")
        expected_optional_absence = (
            value.get("error_type") == "FileNotFoundError"
            and "graph-inference-methodology.json" in str(value.get("error", ""))
        )
        if (
            isinstance(status, str)
            and status.casefold() in _MATERIAL_ERROR_STATUSES
            and not expected_optional_absence
        ):
            found.append(f"{path}.status:{status.casefold()}")
        for key, child in value.items():
            if key != "status":
                found.extend(_material_error_paths(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_material_error_paths(child, path=f"{path}[{index}]"))
    return sorted(set(found))


def _git_index_path(repo_root: Path) -> Path | None:
    dot_git = repo_root / ".git"
    if dot_git.is_dir():
        return dot_git / "index"
    if not dot_git.is_file():
        return None
    try:
        marker = dot_git.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir:"
    if not marker.lower().startswith(prefix):
        return None
    git_dir = Path(marker[len(prefix):].strip())
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()
    return git_dir / "index"


def _cycle_input_fingerprint(
    hub_root: Path,
    *,
    mail_repos: Sequence[Any] | None,
    exception_repos: Sequence[Any] | None,
    journal_repo: Path | None,
) -> tuple[str, int]:
    rows: list[tuple[Any, ...]] = []
    seen: set[tuple[str, str]] = set()
    enabled_policies = [
        policy for policy in (mail_repos or []) if bool(getattr(policy, "mail_enabled", True))
    ] + [
        policy
        for policy in (exception_repos or [])
        if bool(getattr(policy, "exceptions_enabled", True))
    ]
    for policy in enabled_policies:
        repo_id = str(getattr(policy, "id", "") or getattr(policy, "alias", "") or "repo")
        repo_root = Path(getattr(policy, "path"))
        for relative in _CYCLE_INPUT_RELATIVE_PATHS:
            key = (repo_id, relative)
            if key in seen:
                continue
            seen.add(key)
            path = repo_root / relative
            row = _fingerprint_row(repo_id, relative, path)
            if row is not None:
                rows.append(row)
    for policy in mail_repos or []:
        repo_id = str(getattr(policy, "id", "") or getattr(policy, "alias", "") or "repo")
        relatives = LOGOS_LLOS_SURFACES.get(repo_id)
        raw_control_root = getattr(policy, "llos_control_path", None)
        configured_control_root = str(raw_control_root).strip() if raw_control_root is not None else ""
        if relatives and configured_control_root:
            control_root = Path(configured_control_root)
            for relative in (*relatives, POLICY_PATH):
                path = control_root / relative
                row = _fingerprint_row(f"{repo_id}:llos-control", relative, path)
                if row is not None:
                    rows.append(row)
        raw_transport_root = getattr(policy, "transport_audit_path", None)
        configured_transport_root = (
            str(raw_transport_root).strip() if raw_transport_root is not None else ""
        )
        if configured_transport_root:
            transport_root = Path(configured_transport_root)
            for relative in (
                ".digital-asset/dad-integration.json",
                ".digital-asset/mail/.gitignore",
            ):
                path = transport_root / relative
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rows.append(
                    (
                        f"{repo_id}:transport-audit",
                        relative,
                        stat.st_size,
                        stat.st_mtime_ns,
                        sha256_file(path),
                    )
                )
            index_path = _git_index_path(transport_root)
            if index_path is not None:
                try:
                    stat = index_path.stat()
                except OSError:
                    pass
                else:
                    rows.append(
                        (
                            f"{repo_id}:transport-audit",
                            ".git/index",
                            stat.st_size,
                            stat.st_mtime_ns,
                            sha256_file(index_path),
                        )
                    )
    if journal_repo is not None:
        remote_root = journal_repo / "remote-outbox"
        if remote_root.exists():
            for path in sorted(remote_root.rglob("*.jsonl")):
                try:
                    stat = path.stat()
                    relative = path.relative_to(remote_root).as_posix()
                except OSError:
                    continue
                rows.append(("dad-journal", relative, stat.st_size, stat.st_mtime_ns))
    for relative in (
        "config/sources.local.yaml",
        "config/sources.yaml",
        "config/sources.example.yaml",
        ".digital-asset/dad-integration.json",
    ):
        path = hub_root / relative
        row = _fingerprint_row("dad", relative, path)
        if row is not None:
            rows.append(row)
    for relative in _SUBAGENT_CYCLE_INPUT_PATHS:
        path = data_relative_path(hub_root, Path(relative))
        row = _fingerprint_row("dad-data", relative, path)
        if row is not None:
            rows.append(row)
    material = json.dumps(sorted(rows), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest(), len(rows)


def _read_heartbeat_payload(hub_root: Path) -> dict[str, Any]:
    path = daemon_heartbeat_path(hub_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _idle_cycle_result(
    hub_root: Path,
    *,
    generated_at: str,
    previous: dict[str, Any],
    input_fingerprint: str,
    input_snapshot_count: int,
    journal_status_result: dict[str, Any],
) -> dict[str, Any]:
    completed_at = utc_now()
    heartbeat = {
        **previous,
        "schema_version": "dad.daemon.heartbeat.v1",
        "status": "complete",
        "idle": True,
        "idle_reason": "cycle_inputs_unchanged",
        "cycle_started_at": generated_at,
        "cycle_completed_at": completed_at,
        "cycle_order": ["heartbeat"],
        "input_fingerprint": input_fingerprint,
        "input_snapshot_count": input_snapshot_count,
        "journal_checkpoint_due": journal_status_result.get("checkpoint_due"),
        "journal_checkpoint_applied": False,
        "journal_checkpoint_status": journal_status_result,
        "heartbeat_finalized": True,
        "heartbeat_finalized_at": completed_at,
        "reporting_privacy": daemon_reporting_privacy(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_text(
        daemon_heartbeat_path(hub_root),
        json_dumps(heartbeat, pretty=True) + "\n",
    )
    return {
        "schema_version": "dad.daemon.cycle.v1",
        "generated_at": generated_at,
        "idle": True,
        "idle_reason": "cycle_inputs_unchanged",
        "cycle_order": ["heartbeat"],
        "heartbeat_path": str(daemon_heartbeat_path(hub_root)),
        "journal_status": journal_status_result,
        "reporting_privacy": daemon_reporting_privacy(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def daemon_heartbeat_path(hub_root: Path) -> Path:
    return _reports_dir(hub_root) / DAEMON_HEARTBEAT_NAME


def daily_review_queue_path(hub_root: Path) -> Path:
    return _reports_dir(hub_root) / DAILY_REVIEW_QUEUE_MD


def scheduled_tasks_report_path(hub_root: Path) -> Path:
    return _reports_dir(hub_root) / SCHEDULED_TASKS_REPORT_NAME


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
            "reporting_privacy": daemon_reporting_privacy(),
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
            "reporting_privacy": daemon_reporting_privacy(),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    cycle_at = _parse_time(str(payload.get("cycle_completed_at") or ""))
    age_hours = None
    stale = True
    if cycle_at is not None:
        age_hours = max(0.0, (datetime.now(timezone.utc) - cycle_at).total_seconds() / 3600.0)
        stale = age_hours > stale_hours
    cycle_status = str(payload.get("status") or "")
    heartbeat_status = "stale" if stale else "fresh"
    if not stale and cycle_status == "complete_with_errors":
        heartbeat_status = "degraded"
    elif not stale and cycle_status not in {"complete", "complete_with_errors"}:
        heartbeat_status = "invalid"
    return {
        "schema_version": "dad.daemon.status.v1",
        "generated_at": utc_now(),
        "status": heartbeat_status,
        "cycle_status": cycle_status,
        "stale": stale,
        "heartbeat_path": str(heartbeat),
        "cycle_completed_at": payload.get("cycle_completed_at", ""),
        "age_hours": age_hours,
        "stale_after_hours": stale_hours,
        "daily_review_queue_path": payload.get("daily_review_queue", ""),
        "follow_through_status": payload.get("follow_through_status"),
        "follow_through_issue_count": payload.get("follow_through_issue_count"),
        "transport_audit_ran": payload.get("transport_audit_ran"),
        "weekly_asset_coverage_status": payload.get("weekly_asset_coverage_status"),
        "weekly_asset_coverage_missing_high_signal_count": payload.get(
            "weekly_asset_coverage_missing_high_signal_count"
        ),
        "weekly_asset_coverage_average_score": payload.get("weekly_asset_coverage_average_score"),
        "weekly_asset_coverage_outputs": payload.get("weekly_asset_coverage_outputs", {}),
        "journal_checkpoint_due": payload.get("journal_checkpoint_due"),
        "journal_checkpoint_applied": payload.get("journal_checkpoint_applied"),
        "journal_checkpoint_status": payload.get("journal_checkpoint_status", {}),
        "scheduled_tasks_report_path": payload.get(
            "scheduled_tasks_report_path",
            str(scheduled_tasks_report_path(hub_root)),
        ),
        "reporting_privacy": daemon_reporting_privacy(),
        "scheduled_task_count": payload.get("scheduled_task_count"),
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
    logos_llos_result: dict[str, Any],
    subagent_improvement_result: dict[str, Any],
    graph_surface_status_result: dict[str, Any],
    transport_result: dict[str, Any] | None,
    weekly_asset_coverage_result: dict[str, Any],
    scheduled_tasks_result: dict[str, Any],
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
        "logos_llos": logos_llos_result,
        "subagent_improvement": subagent_improvement_result,
        "graph_surfaces": graph_surface_status_result,
        "transport": transport_result or {"status": "not_run"},
        "weekly_asset_coverage": weekly_asset_coverage_result,
        "scheduled_tasks": scheduled_tasks_result,
        "journal": journal_result,
        "reporting_privacy": daemon_reporting_privacy(),
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
        f"- Logos LLOS audit: {logos_llos_result.get('status', 'unknown')}",
        f"- Logos LLOS current repos: {logos_llos_result.get('current_count', 'unknown')}",
        f"- Subagent improvement review: {subagent_improvement_result.get('status', 'unknown')}",
        f"- Subagent exception candidates: {len(subagent_improvement_result.get('report', {}).get('exception_candidates', []))}",
        f"- Graph surface freshness: {graph_surface_status_result.get('freshness_counts', {})}",
        f"- Transport audit: {transport_result.get('report_path', 'not run') if transport_result else 'not run'}",
        f"- Transport upgrade count: {transport_result.get('upgrade_required_count', 'not run') if transport_result else 'not run'}",
        f"- Weekly asset coverage: {weekly_asset_coverage_result.get('status', 'unknown')}",
        f"- Weekly asset coverage missing high-signal: {weekly_asset_coverage_result.get('summary', {}).get('missing_high_signal_count', 'not run')}",
        f"- Scheduled tasks: {scheduled_tasks_result.get('task_count', 'unknown')}",
        f"- Scheduled task report: {scheduled_tasks_result.get('report_path', 'unknown')}",
        f"- Journal checkpoint due: {journal_result.get('checkpoint_due')}",
        f"- Journal new records: {journal_result.get('new_record_count')}",
        f"- Journal status: {journal_result.get('checkpoint_skipped_reason', 'ready_or_applied')}",
        "- Data classification: synthetic development only",
        "- Real client data gate: blocked",
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


def _run_subagent_improvement_review(hub_root: Path) -> dict[str, Any]:
    if not (hub_root / "registry" / "subagent-improvement-policy.json").exists():
        return {
            "status": "skipped",
            "reason": "subagent_improvement_policy_missing",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    return build_improvement_review(hub_root)


def _run_event_cycle(hub_root: Path, *, mail_repos: Sequence[Any] | None) -> dict[str, Any]:
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
    asset_coverage_repos: Sequence[Any] | None = None,
    journal_repo: Path | None = None,
    checkpoint_apply: bool = False,
) -> dict[str, Any]:
    generated_at = utc_now()
    input_fingerprint, input_snapshot_count = _cycle_input_fingerprint(
        hub_root,
        mail_repos=mail_repos,
        exception_repos=exception_repos,
        journal_repo=journal_repo,
    )
    previous_heartbeat = _read_heartbeat_payload(hub_root)
    journal_status_result = journal_status(hub_root)
    weekly_due = weekly_asset_coverage_due(hub_root, generated_at=generated_at)
    if (
        previous_heartbeat.get("status") == "complete"
        and previous_heartbeat.get("input_fingerprint") == input_fingerprint
        and not bool(journal_status_result.get("checkpoint_due"))
        and not bool(weekly_due.get("due"))
    ):
        return _idle_cycle_result(
            hub_root,
            generated_at=generated_at,
            previous=previous_heartbeat,
            input_fingerprint=input_fingerprint,
            input_snapshot_count=input_snapshot_count,
            journal_status_result=journal_status_result,
        )
    cycle_order = [
        "journal_remote_outbox_ingest",
        "mail_collect",
        "mail_route",
        "mail_deliver",
        "mail_follow_through_audit",
        "events_collect",
        "exceptions_collect",
        "lesson_graph_rebuild",
        "logos_llos_read_only_audit",
        "subagent_improvement_review",
        "graph_inference",
        "transport_audit",
        "weekly_asset_coverage",
        "scheduled_task_registry",
        "daily_review_queue",
        "heartbeat",
        "journal_checkpoint",
    ]
    heartbeat = {
        "schema_version": "dad.daemon.heartbeat.v1",
        "status": "in_progress",
        "cycle_started_at": generated_at,
        "cycle_completed_at": "",
        "cycle_order": cycle_order,
        "idle": False,
        "input_fingerprint": input_fingerprint,
        "input_snapshot_count": input_snapshot_count,
        "journal_checkpoint_due": journal_status_result.get("checkpoint_due"),
        "journal_checkpoint_applied": False,
        "journal_checkpoint_status": journal_status_result,
        "heartbeat_finalized": False,
        "reporting_privacy": daemon_reporting_privacy(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_text(daemon_heartbeat_path(hub_root), json_dumps(heartbeat, pretty=True) + "\n")
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
    logos_llos_result = _step_result(
        "logos_llos_read_only_audit",
        audit_logos_llos,
        hub_root,
        mail_repos or [],
    )
    subagent_improvement_result = _step_result(
        "subagent_improvement_review",
        _run_subagent_improvement_review,
        hub_root,
    )
    transport_result = (
        audit_all_repo_transport(hub_root, transport_repos) if transport_repos is not None else None
    )
    weekly_asset_coverage_result = _step_result(
        "weekly_asset_coverage",
        write_weekly_asset_coverage_outputs,
        hub_root,
        repo_policies=asset_coverage_repos if asset_coverage_repos is not None else mail_repos,
    )
    scheduled_tasks_result = scheduled_tasks_status(
        hub_root,
        inspect_scheduler=False,
    )
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
        logos_llos_result=logos_llos_result,
        subagent_improvement_result=subagent_improvement_result,
        graph_surface_status_result=graph_surface_status_result,
        transport_result=transport_result,
        weekly_asset_coverage_result=weekly_asset_coverage_result,
        scheduled_tasks_result=scheduled_tasks_result,
        journal_result=journal_status_result,
    )
    heartbeat.update(
        {
            "remote_outbox_ingest_status": remote_outbox_result.get("status"),
            "mail_collect_status": mail_result.get("collect", {}).get(
                "status", mail_result.get("status")
            ),
            "mail_route_status": mail_result.get("route", {}).get(
                "status", mail_result.get("status")
            ),
            "mail_deliver_status": mail_result.get("deliver", {}).get(
                "status", mail_result.get("status")
            ),
            "follow_through_status": follow_through_result.get(
                "audit_status", follow_through_result.get("status")
            ),
            "follow_through_issue_count": follow_through_result.get("issue_count"),
            "events_collect_status": event_result.get("collect", {}).get(
                "status", event_result.get("status")
            ),
            "exceptions_collect_status": exception_result.get("status"),
            "lesson_graph_status": graph_result.get("lesson_graph", {}).get(
                "status", graph_result.get("status")
            ),
            "logos_llos_status": logos_llos_result.get("status"),
            "logos_llos_current_count": logos_llos_result.get("current_count"),
            "graph_inference_status": graph_result.get("inference", {}).get(
                "status", graph_result.get("status")
            ),
            "subagent_improvement_status": subagent_improvement_result.get("status"),
            "subagent_exception_candidate_count": len(
                subagent_improvement_result.get("report", {}).get("exception_candidates", [])
            ),
            "graph_surface_freshness_counts": graph_surface_status_result.get(
                "freshness_counts", {}
            ),
            "transport_audit_ran": transport_result is not None,
            "weekly_asset_coverage_status": weekly_asset_coverage_result.get("status"),
            "weekly_asset_coverage_missing_high_signal_count": weekly_asset_coverage_result.get(
                "summary", {}
            ).get("missing_high_signal_count"),
            "weekly_asset_coverage_average_score": weekly_asset_coverage_result.get(
                "summary", {}
            ).get("average_coverage_score"),
            "weekly_asset_coverage_outputs": weekly_asset_coverage_result.get("outputs", {}),
            "daily_review_queue": review_queue["markdown_path"],
            "scheduled_tasks_report_path": scheduled_tasks_result["report_path"],
            "scheduled_task_count": scheduled_tasks_result["task_count"],
        }
    )
    atomic_write_text(daemon_heartbeat_path(hub_root), json_dumps(heartbeat, pretty=True) + "\n")
    journal_result = _step_result(
        "journal_checkpoint",
        checkpoint_journal,
        hub_root,
        journal_repo,
        apply=checkpoint_apply,
    )
    heartbeat["journal_checkpoint_due"] = journal_result.get("checkpoint_due")
    heartbeat["journal_checkpoint_applied"] = bool(journal_result.get("checkpoint_applied", False))
    heartbeat["journal_checkpoint_status"] = journal_result
    cycle_errors = _material_error_paths(
        {
            "remote_outbox_ingest": remote_outbox_result,
            "mail": mail_result,
            "follow_through": follow_through_result,
            "events": event_result,
            "exceptions": exception_result,
            "graphs": graph_result,
            "logos_llos": logos_llos_result,
            "subagent_improvement": subagent_improvement_result,
            "transport": transport_result,
            "weekly_asset_coverage": weekly_asset_coverage_result,
            "scheduled_tasks": scheduled_tasks_result,
            "daily_review_queue": review_queue,
            "journal": journal_result,
        }
    )
    heartbeat["material_error_count"] = len(cycle_errors)
    heartbeat["material_error_paths"] = cycle_errors
    heartbeat["status"] = (
        "complete_with_errors"
        if cycle_errors
        else "complete"
    )
    heartbeat["cycle_completed_at"] = utc_now()
    heartbeat["heartbeat_finalized"] = True
    heartbeat["heartbeat_finalized_at"] = utc_now()
    atomic_write_text(daemon_heartbeat_path(hub_root), json_dumps(heartbeat, pretty=True) + "\n")
    scheduled_tasks_result = write_scheduled_tasks_report(
        hub_root,
        inspect_scheduler=False,
    )
    return {
        "schema_version": "dad.daemon.cycle.v1",
        "generated_at": generated_at,
        "idle": False,
        "cycle_order": cycle_order,
        "heartbeat_path": str(daemon_heartbeat_path(hub_root)),
        "daily_review_queue": review_queue,
        "remote_outbox_ingest": remote_outbox_result,
        "mail": mail_result,
        "follow_through": follow_through_result,
        "events": event_result,
        "exceptions": exception_result,
        "graphs": graph_result,
        "logos_llos": logos_llos_result,
        "subagent_improvement": subagent_improvement_result,
        "graph_surface_status": graph_surface_status_result,
        "transport": transport_result,
        "weekly_asset_coverage": weekly_asset_coverage_result,
        "scheduled_tasks": scheduled_tasks_result,
        "journal_status": journal_status_result,
        "journal": journal_result,
        "reporting_privacy": daemon_reporting_privacy(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def task_scheduler_plan(
    hub_root: Path,
    *,
    task_name: str = "DAD Daemon Run Cycle",
    schedule_time: str = "09:00",
    twice_daily: bool = False,
    shim: Path | None = None,
    journal_repo: Path | None = None,
    checkpoint_apply: bool = False,
) -> dict[str, Any]:
    shim_path = shim or Path.home() / ".dad" / "bin" / "asset-dir.ps1"
    wrapper_path = shim_path.parent / DAEMON_TASK_WRAPPER_NAME
    task_report_dir = data_path(hub_root, "central_reports")
    task_log_path = task_report_dir / DAEMON_TASK_LAST_RUN_LOG
    task_status_path = task_report_dir / DAEMON_TASK_LAST_RUN_STATUS
    tr = "HOURLY" if twice_daily else "DAILY"
    mo = "12" if twice_daily else "1"
    run_cycle_args = ["--hub", str(hub_root.resolve()), "--quiet"]
    if journal_repo is not None:
        run_cycle_args.extend(["--journal-repo", str(journal_repo.resolve())])
    if checkpoint_apply:
        run_cycle_args.append("--checkpoint-apply")
    wrapper_args = " ".join(_ps_single_quote(arg) for arg in run_cycle_args)
    wrapper_script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$logPath = {_ps_single_quote(str(task_log_path))}",
            f"$statusPath = {_ps_single_quote(str(task_status_path))}",
            "New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logPath) | Out-Null",
            "$startedAt = [DateTimeOffset]::UtcNow.ToString('o')",
            (
                "& powershell -NoProfile -ExecutionPolicy Bypass -File "
                f"{_ps_single_quote(str(shim_path))} daemon run-cycle {wrapper_args} "
                "*> $logPath"
            ),
            "$exitCode = $LASTEXITCODE",
            "$status = [ordered]@{",
            "  schema_version = 'dad.daemon.task_run.v1'",
            "  started_at = $startedAt",
            "  completed_at = [DateTimeOffset]::UtcNow.ToString('o')",
            "  exit_code = $exitCode",
            "  log_path = $logPath",
            "  data_classification = 'synthetic_development_only'",
            "  real_client_data_approved = $false",
            "}",
            "$statusJson = $status | ConvertTo-Json",
            "$utf8NoBom = New-Object System.Text.UTF8Encoding($false)",
            (
                "[System.IO.File]::WriteAllText($statusPath, "
                "$statusJson + [Environment]::NewLine, $utf8NoBom)"
            ),
            "exit $exitCode",
            "",
        ]
    )
    task_to_run = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{wrapper_path}"'
    command = (
        f'schtasks /Create /TN "{task_name}" /SC {tr} /MO {mo} /ST {schedule_time} '
        f'/TR "{task_to_run}" /F'
    )
    settings_script = (
        "$settings = New-ScheduledTaskSettingsSet "
        "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-DontStopOnIdleEnd -StartWhenAvailable; "
        f"Set-ScheduledTask -TaskName {_ps_single_quote(task_name)} "
        "-Settings $settings | Out-Null"
    )
    return {
        "schema_version": "dad.daemon.task_scheduler_plan.v1",
        "task_name": task_name,
        "schedule_time": schedule_time,
        "twice_daily": twice_daily,
        "shim": str(shim_path),
        "wrapper_path": str(wrapper_path),
        "task_log_path": str(task_log_path),
        "task_status_path": str(task_status_path),
        "wrapper_script": wrapper_script,
        "task_to_run": task_to_run,
        "run_cycle_args": run_cycle_args,
        "journal_repo": str(journal_repo.resolve()) if journal_repo is not None else None,
        "checkpoint_apply": checkpoint_apply,
        "command": command,
        "settings_command": [
            "powershell",
            "-NoProfile",
            "-Command",
            settings_script,
        ],
        "reporting_privacy": daemon_reporting_privacy(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def install_task_scheduler(plan: dict[str, Any]) -> dict[str, Any]:
    wrapper_path = Path(str(plan["wrapper_path"]))
    assert_dad_write_allowed(wrapper_path)
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(wrapper_path, str(plan["wrapper_script"]))
    command = str(plan["command"])
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
    settings_result = None
    if result.returncode == 0:
        settings_result = subprocess.run(
            list(plan["settings_command"]),
            capture_output=True,
            text=True,
            check=False,
        )
    settings_returncode = int(settings_result.returncode) if settings_result is not None else None
    return {
        **plan,
        "installed": result.returncode == 0 and settings_returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "settings_returncode": settings_returncode,
        "settings_stdout": settings_result.stdout if settings_result is not None else "",
        "settings_stderr": settings_result.stderr if settings_result is not None else "",
    }


def _scheduler_status_summary(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": status.get("schema_version", "dad.daemon.task_scheduler_status.v1"),
        "installed": bool(status.get("installed", False)),
        "status": status.get("status", "unknown"),
        "task_status": status.get("task_status", ""),
        "next_run_time": status.get("next_run_time", ""),
        "last_run_time": status.get("last_run_time", ""),
        "last_result": status.get("last_result", ""),
        "last_result_status": status.get("last_result_status", "unknown"),
        "task_to_run": status.get("task_to_run", ""),
        "wrapper_path": status.get("wrapper_path", ""),
        "wrapper_found": bool(status.get("wrapper_found", False)),
        "wrapper_read_error": status.get("wrapper_read_error", ""),
        "command_mentions_run_cycle": bool(status.get("command_mentions_run_cycle", False)),
        "expected_hub_found": bool(status.get("expected_hub_found", False)),
        "expected_shim_found": bool(status.get("expected_shim_found", False)),
        "returncode": status.get("returncode"),
    }


def _scheduler_result_status(*, task_status: str, last_result: str) -> str:
    normalized_task_status = task_status.strip().casefold()
    if normalized_task_status == "running":
        return "running"
    value = last_result.strip()
    if not value:
        return "unknown"
    try:
        code = int(value, 0)
    except ValueError:
        return "unknown"
    if code == 267009:  # 0x41301: task is currently running.
        return "inconsistent" if normalized_task_status else "running"
    if code == 0:
        return "success"
    if code == 3221225786:  # 0xC000013A: interrupted by a control event.
        return "interrupted"
    return "failed"


def _scheduled_task_health(
    *,
    scheduler: dict[str, Any],
    heartbeat: dict[str, Any],
    inspect_scheduler: bool,
) -> str:
    if inspect_scheduler:
        if not scheduler.get("installed"):
            return "scheduler_missing_or_unavailable"
        if not scheduler.get("command_mentions_run_cycle"):
            return "installed_command_mismatch"
        if not scheduler.get("expected_hub_found"):
            return "installed_hub_mismatch"
        if not scheduler.get("expected_shim_found"):
            return "installed_shim_mismatch"
        result_status = str(scheduler.get("last_result_status") or "unknown")
        if result_status == "running":
            return "scheduler_running"
        if result_status == "inconsistent":
            return "scheduler_state_inconsistent"
        if result_status == "interrupted":
            return "scheduler_last_run_interrupted"
        if result_status == "failed":
            return "scheduler_last_run_failed"
    if heartbeat.get("status") == "fresh" and not bool(heartbeat.get("stale", True)):
        return "ready" if inspect_scheduler else "heartbeat_fresh_scheduler_not_inspected"
    if heartbeat.get("status") in {"missing", "invalid", "stale"}:
        return "heartbeat_stale_or_missing"
    if heartbeat.get("status") == "degraded":
        return "degraded"
    return "unknown"


def scheduled_tasks_status(
    hub_root: Path,
    *,
    task_name: str = "DAD Daemon Run Cycle",
    shim: Path | None = None,
    inspect_scheduler: bool = False,
    runner: Any | None = None,
    stale_hours: int = 26,
) -> dict[str, Any]:
    heartbeat = daemon_status(hub_root, stale_hours=stale_hours)
    if inspect_scheduler:
        scheduler = task_scheduler_status(
            hub_root,
            task_name=task_name,
            shim=shim,
            runner=runner,
        )
        scheduler_summary = _scheduler_status_summary(scheduler)
    else:
        scheduler_summary = {
            "schema_version": "dad.daemon.task_scheduler_status.v1",
            "installed": None,
            "status": "not_inspected",
            "task_status": "",
            "next_run_time": "",
            "last_run_time": "",
            "last_result": "",
            "last_result_status": "unknown",
            "task_to_run": "",
            "wrapper_path": str(
                (shim or Path.home() / ".dad" / "bin" / "asset-dir.ps1").parent
                / DAEMON_TASK_WRAPPER_NAME
            ),
            "wrapper_found": None,
            "wrapper_read_error": "",
            "command_mentions_run_cycle": None,
            "expected_hub_found": None,
            "expected_shim_found": None,
            "returncode": None,
        }
    report_path = scheduled_tasks_report_path(hub_root)
    health = _scheduled_task_health(
        scheduler=scheduler_summary,
        heartbeat=heartbeat,
        inspect_scheduler=inspect_scheduler,
    )
    task = {
        "task_id": "dad-daemon-run-cycle",
        "display_name": "DAD daemon run cycle",
        "task_name": task_name,
        "owner": "dad",
        "kind": "windows_task_scheduler",
        "schedule_source": "windows_task_scheduler",
        "primary_command": "asset-dir daemon run-cycle",
        "status_command": "asset-dir daemon task-status --hub .",
        "install_command": "asset-dir daemon install --apply",
        "category": "transport_daemon",
        "health": health,
        "heartbeat": {
            "status": heartbeat.get("status"),
            "stale": heartbeat.get("stale"),
            "cycle_completed_at": heartbeat.get("cycle_completed_at", ""),
            "heartbeat_path": heartbeat.get("heartbeat_path", ""),
            "daily_review_queue_path": heartbeat.get("daily_review_queue_path", ""),
            "scheduled_tasks_report_path": str(report_path),
        },
        "scheduler": scheduler_summary,
        "writes": [
            "DAD_DATA_ROOT/processed/reports/daemon-heartbeat.json",
            "DAD_DATA_ROOT/processed/reports/daily_review_queue.md",
            "DAD_DATA_ROOT/processed/reports/scheduled_tasks.json",
        ],
        "mutation_policy": (
            "This registry is read-only status evidence. It does not create, "
            "delete, enable, disable, or edit scheduled tasks."
        ),
        "human_gate_ids": ["phase-13-daemon-schedule-approved"],
        "reporting_privacy": daemon_reporting_privacy(),
        "ui_ready": True,
    }
    tasks = [task]
    healthy_count = sum(
        1
        for item in tasks
        if item["health"] in {"ready", "heartbeat_fresh_scheduler_not_inspected"}
    )
    installed_count = sum(1 for item in tasks if item.get("scheduler", {}).get("installed") is True)
    return {
        "schema_version": "dad.daemon.scheduled_tasks.v1",
        "generated_at": utc_now(),
        "report_path": str(report_path),
        "inspect_scheduler": inspect_scheduler,
        "task_count": len(tasks),
        "healthy_count": healthy_count,
        "installed_count": installed_count,
        "tasks": tasks,
        "reporting_privacy": daemon_reporting_privacy(),
        "ui_ready": True,
        "authority_boundary": (
            "Scheduled-task registry rows are local operational status evidence. "
            "They do not authorize scheduler mutation, downstream repo writes, "
            "protected repo changes, Cloudflare deployment, or roadmap gate approval."
        ),
    }


def write_scheduled_tasks_report(
    hub_root: Path,
    *,
    task_name: str = "DAD Daemon Run Cycle",
    shim: Path | None = None,
    inspect_scheduler: bool = False,
    runner: Any | None = None,
    stale_hours: int = 26,
) -> dict[str, Any]:
    report = scheduled_tasks_status(
        hub_root,
        task_name=task_name,
        shim=shim,
        inspect_scheduler=inspect_scheduler,
        runner=runner,
        stale_hours=stale_hours,
    )
    atomic_write_text(
        scheduled_tasks_report_path(hub_root),
        json_dumps(report, pretty=True) + "\n",
    )
    return report


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


def _generated_wrapper_options(wrapper_text: str) -> dict[str, Any]:
    quoted_tokens = [
        token.replace("''", "'")
        for token in re.findall(r"'((?:''|[^'])*)'", wrapper_text)
    ]
    options: dict[str, Any] = {
        "journal_repo": None,
        "checkpoint_apply": False,
    }
    for index, token in enumerate(quoted_tokens):
        if token == "--journal-repo" and index + 1 < len(quoted_tokens):
            options["journal_repo"] = quoted_tokens[index + 1]
        elif token == "--checkpoint-apply":
            options["checkpoint_apply"] = True
    return options


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
            "query_command": 'schtasks /Query /TN "{name}" /FO LIST /V'.format(name=task_name),
            "installed": False,
            "status": "unavailable",
            "error": str(exc),
            "reporting_privacy": daemon_reporting_privacy(),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }

    stdout = str(getattr(result, "stdout", "") or "")
    stderr = str(getattr(result, "stderr", "") or "")
    returncode = int(getattr(result, "returncode", 1))
    parsed = _parse_schtasks_list_output(stdout)
    task_status = parsed.get("status", "")
    last_result = parsed.get("last_result", "")
    task_to_run = parsed.get("task_to_run", "")
    hub_text = str(hub_root.resolve())
    shim_text = str((shim or Path.home() / ".dad" / "bin" / "asset-dir.ps1"))
    wrapper_path = Path(shim_text).parent / DAEMON_TASK_WRAPPER_NAME
    wrapper_text = ""
    wrapper_read_error = ""
    if str(wrapper_path) in task_to_run and wrapper_path.exists():
        try:
            wrapper_text = wrapper_path.read_text(encoding="utf-8")
        except OSError as exc:
            wrapper_read_error = str(exc)
    command_material = task_to_run + "\n" + wrapper_text
    wrapper_options = _generated_wrapper_options(wrapper_text)
    installed = returncode == 0
    return {
        "schema_version": "dad.daemon.task_scheduler_status.v1",
        "task_name": task_name,
        "query_command": 'schtasks /Query /TN "{name}" /FO LIST /V'.format(name=task_name),
        "installed": installed,
        "status": "installed" if installed else "missing",
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "task_status": task_status,
        "next_run_time": parsed.get("next_run_time", ""),
        "last_run_time": parsed.get("last_run_time", ""),
        "last_result": last_result,
        "last_result_status": _scheduler_result_status(
            task_status=task_status,
            last_result=last_result,
        ),
        "task_to_run": task_to_run,
        "wrapper_path": str(wrapper_path),
        "wrapper_found": bool(wrapper_text),
        "wrapper_read_error": wrapper_read_error,
        "wrapper_text": wrapper_text,
        "journal_repo": wrapper_options["journal_repo"],
        "checkpoint_apply": wrapper_options["checkpoint_apply"],
        "command_mentions_run_cycle": "daemon run-cycle" in command_material,
        "expected_hub_found": hub_text in command_material,
        "expected_shim_found": shim_text in command_material,
        "reporting_privacy": daemon_reporting_privacy(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
