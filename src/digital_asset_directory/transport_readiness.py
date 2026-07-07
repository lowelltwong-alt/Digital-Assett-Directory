"""Read-only readiness summary for the transport data-plane rollout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .daemon import daemon_status
from .journal import journal_status
from .transport import (
    AUTHORITY_BOUNDARY,
    DATA_PLANE_PATHS,
    TRANSPORT_SURFACE_VERSION,
    data_path,
    read_transport_upgrade_queue,
    resolve_data_root,
)
from .transport_upgrade import build_transport_upgrade_status
from .utils import utc_now


def _read_json_object(path: Path) -> tuple[str, dict[str, Any]]:
    if not path.exists():
        return "missing", {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "invalid", {"error": str(exc)}
    if not isinstance(payload, dict):
        return "invalid", {"error": "report is not a JSON object"}
    return "readable", payload


def _gate(*, complete: bool, status: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "complete": complete,
        "status": status,
        "evidence": evidence,
    }


def build_transport_readiness(
    hub_root: Path,
    *,
    transport_repos: Sequence[Mapping[str, Any]] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
    wave: str = "transport-surface-v1",
    stale_hours: int = 26,
    scheduler_status: Mapping[str, Any] | None = None,
    journal_repo_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize transport readiness without mutating repos or data files."""
    data_root, data_mode = resolve_data_root(hub_root)
    report_path = data_path(hub_root, "central_reports") / "transport_audit.json"
    report_status, report_payload = _read_json_object(report_path)
    queue = read_transport_upgrade_queue(hub_root)
    daemon = daemon_status(hub_root, stale_hours=stale_hours)
    journal = journal_status(hub_root)
    repos = list(transport_repos or [])
    upgrade_status = build_transport_upgrade_status(
        hub_root,
        transport_repos=repos,
        enrollment_policies=enrollment_policies or [],
        wave=wave,
    )
    scheduler = dict(scheduler_status or {})
    journal_repo = dict(journal_repo_status or {})

    data_root_active = data_mode == "data_root"
    last_checkpoint_at = str(journal.get("last_checkpoint_at") or "")
    daemon_fresh = daemon.get("status") == "fresh" and not bool(daemon.get("stale"))
    if scheduler.get("installed") and daemon_fresh:
        daemon_schedule_status = (
            "scheduler_installed_machine_condition_met_pending_human_gate_record"
        )
    elif scheduler:
        daemon_schedule_status = "scheduler_query_missing_or_not_installed"
    elif daemon_fresh:
        daemon_schedule_status = "fresh_heartbeat_but_task_scheduler_unverified"
    else:
        daemon_schedule_status = "pending_task_scheduler_apply"
    if journal_repo.get("machine_ready") and not bool(journal.get("checkpoint_due")):
        journal_gate_status = (
            "journal_repo_machine_condition_met_pending_human_gate_record"
        )
    elif journal_repo:
        journal_gate_status = str(
            journal_repo.get("status") or "journal_repo_not_ready"
        )
    else:
        journal_gate_status = "pending_private_journal_repo_or_checkpoint_apply"

    human_gates = {
        "data_root_migration": _gate(
            complete=data_root_active,
            status="active" if data_root_active else "pending_human_apply",
            evidence={
                "data_root": str(data_root),
                "mode": data_mode,
                "note": (
                    "legacy mode is the fail-safe fallback until an initialized "
                    "DAD_DATA_ROOT marker is present"
                ),
            },
        ),
        "journal_repo_checkpoint": _gate(
            complete=False,
            status=journal_gate_status,
            evidence={
                "last_checkpoint_at": last_checkpoint_at,
                "checkpoint_due": journal.get("checkpoint_due"),
                "new_record_count": journal.get("new_record_count"),
                "journal_repo_status": journal_repo or None,
            },
        ),
        "daemon_schedule": _gate(
            complete=False,
            status=daemon_schedule_status,
            evidence={
                "daemon_status": daemon.get("status"),
                "stale": daemon.get("stale"),
                "heartbeat_path": daemon.get("heartbeat_path"),
                "scheduler_status": scheduler or None,
                "note": (
                    "Task Scheduler evidence is read-only and machine-level; "
                    "the phase gate still needs a human approval/evidence record."
                ),
            },
        ),
        "repo_upgrade_wave": _gate(
            complete=False,
            status="pending_reviewed_enrollment_wave",
            evidence={
                "configured_policy_repo_count": len(repos),
                "transport_queue_row_count": queue.get("row_count"),
                "transport_report_repo_count": report_payload.get("repo_count"),
                "classification_counts": report_payload.get("classification_counts", {}),
                "upgrade_status": upgrade_status.get("status"),
                "selected_count": upgrade_status.get("selection", {}).get("selected_count"),
                "skipped_by_reason": upgrade_status.get("selection", {}).get(
                    "skipped_by_reason", {}
                ),
            },
        ),
        "cloudflare_relay": _gate(
            complete=False,
            status="deferred_until_phase_10a_cloud_boundary_reviewed",
            evidence={
                "implemented": False,
                "note": "M3 relay remains design-only until its human gate.",
            },
        ),
    }

    local_checks = {
        "data_root_resolver_available": True,
        "transport_audit_report_readable": report_status == "readable",
        "transport_upgrade_queue_readable": queue.get("invalid_row_count") == 0,
        "daemon_status_readable": daemon.get("schema_version") == "dad.daemon.status.v1",
        "journal_status_readable": journal.get("schema_version") == "dad.journal.status.v1",
        "configured_policy_repo_count": len(repos),
        "data_plane_surface_count": len(DATA_PLANE_PATHS),
    }
    local_ready = all(
        bool(local_checks[key])
        for key in (
            "data_root_resolver_available",
            "transport_audit_report_readable",
            "transport_upgrade_queue_readable",
            "daemon_status_readable",
            "journal_status_readable",
        )
    )
    completed_gates = [
        name for name, gate in human_gates.items() if bool(gate.get("complete"))
    ]
    pending_gates = [
        name for name, gate in human_gates.items() if not bool(gate.get("complete"))
    ]
    if not local_ready:
        overall_status = "needs_local_attention"
    elif pending_gates:
        overall_status = "local_ready_human_gates_pending"
    else:
        overall_status = "ready"

    return {
        "schema_version": "dad.transport.readiness.v1",
        "generated_at": utc_now(),
        "overall_status": overall_status,
        "local_ready": local_ready,
        "local_checks": local_checks,
        "data_root": {
            "path": str(data_root),
            "mode": data_mode,
            "active": data_root_active,
        },
        "audit": {
            "report_path": str(report_path),
            "report_status": report_status,
            "transport_surface_version": report_payload.get("transport_surface_version"),
            "hub_classification": report_payload.get("hub", {}).get("classification")
            if isinstance(report_payload.get("hub"), dict)
            else None,
            "classification_counts": report_payload.get("classification_counts", {}),
        },
        "upgrade_queue": {
            "queue_path": queue.get("queue_path"),
            "row_count": queue.get("row_count"),
            "invalid_row_count": queue.get("invalid_row_count"),
        },
        "upgrade_wave": upgrade_status,
        "daemon": {
            "status": daemon.get("status"),
            "stale": daemon.get("stale"),
            "heartbeat_path": daemon.get("heartbeat_path"),
            "transport_audit_ran": daemon.get("transport_audit_ran"),
            "daily_review_queue_path": daemon.get("daily_review_queue_path"),
            "scheduler_status": scheduler or None,
        },
        "journal": {
            "checkpoint_due": journal.get("checkpoint_due"),
            "new_record_count": journal.get("new_record_count"),
            "last_checkpoint_at": journal.get("last_checkpoint_at"),
            "data_root_mode": journal.get("data_root_mode"),
            "repo_status": journal_repo or None,
        },
        "human_gate_summary": {
            "complete_count": len(completed_gates),
            "pending_count": len(pending_gates),
            "completed": completed_gates,
            "pending": pending_gates,
        },
        "human_gates": human_gates,
        "operator_next_steps": [
            "asset-dir data migrate --plan-only",
            "asset-dir data migrate --apply",
            "asset-dir transport upgrade-status",
            "asset-dir daemon install --plan-only",
            "asset-dir daemon install --apply",
            "asset-dir journal repo-status",
            "asset-dir journal checkpoint --plan-only",
            "asset-dir enroll update-plan --from-transport-queue",
        ],
        "transport_surface_version": TRANSPORT_SURFACE_VERSION,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
