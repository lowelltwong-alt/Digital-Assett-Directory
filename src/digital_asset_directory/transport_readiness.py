"""Read-only readiness summary for the transport data-plane rollout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .daemon import daemon_status
from .graph_surfaces import graph_surface_status
from .journal import journal_status
from .roadmap import check_roadmap
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


def _phase13_verified_gate_ids(hub_root: Path) -> set[str]:
    try:
        phase = check_roadmap(hub_root, update=False).get("phases", {}).get(
            "phase-13-transport-data-plane", {}
        )
    except (OSError, ValueError, KeyError, TypeError):
        return set()
    return {
        str(gate_id)
        for gate_id in phase.get("human_gate_ids_verified", [])
        if str(gate_id)
    }


def _is_nonnegative_plain_int(value: Any) -> bool:
    return type(value) is int and value >= 0


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
    scheduler = dict(scheduler_status or {})
    journal_repo = dict(journal_repo_status or {})
    embedded_journal = journal_repo.get("journal_status")
    journal = (
        dict(embedded_journal)
        if isinstance(embedded_journal, Mapping)
        else journal_status(hub_root)
    )
    graph_surfaces = graph_surface_status(hub_root)
    repos = list(transport_repos or [])
    upgrade_status = build_transport_upgrade_status(
        hub_root,
        transport_repos=repos,
        enrollment_policies=enrollment_policies or [],
        wave=wave,
    )
    verified_gate_ids = _phase13_verified_gate_ids(hub_root)

    data_root_active = data_mode == "data_root"
    last_checkpoint_at = str(journal.get("last_checkpoint_at") or "")
    daemon_fresh = daemon.get("status") == "fresh" and not bool(daemon.get("stale"))
    daemon_machine_ready = bool(
        scheduler.get("installed")
        and scheduler.get("command_mentions_run_cycle")
        and scheduler.get("expected_hub_found")
        and daemon_fresh
    )
    daemon_gate_verified = "phase-13-daemon-schedule-approved" in verified_gate_ids
    if daemon_machine_ready and daemon_gate_verified:
        daemon_schedule_status = "verified_and_operational"
    elif daemon_machine_ready:
        daemon_schedule_status = "scheduler_installed_pending_human_gate_record"
    elif scheduler:
        daemon_schedule_status = "scheduler_query_missing_or_not_installed"
    elif daemon_fresh:
        daemon_schedule_status = "fresh_heartbeat_but_task_scheduler_unverified"
    else:
        daemon_schedule_status = "pending_task_scheduler_apply"
    journal_machine_ready = bool(
        journal_repo.get("machine_ready")
        and journal_repo.get("working_tree_clean")
        and journal_repo.get("checkpoint_current_for_threshold")
        and not bool(journal.get("checkpoint_due"))
    )
    journal_gate_verified = "phase-13-journal-repo-approved" in verified_gate_ids
    if journal_machine_ready and journal_gate_verified:
        journal_gate_status = "verified_and_operational"
    elif journal_machine_ready:
        journal_gate_status = "journal_repo_ready_pending_human_gate_record"
    elif journal_repo:
        journal_gate_status = str(
            journal_repo.get("status") or "journal_repo_not_ready"
        )
    else:
        journal_gate_status = "pending_private_journal_repo_or_checkpoint_apply"

    data_root_gate_verified = "phase-13-data-root-migration-approved" in verified_gate_ids
    data_root_complete = data_root_active and data_root_gate_verified
    repo_gate_verified = (
        "phase-13-repo-transport-upgrade-wave-approved" in verified_gate_ids
    )
    raw_classification_counts = report_payload.get("classification_counts")
    classification_counts = (
        raw_classification_counts if isinstance(raw_classification_counts, dict) else {}
    )
    reported_repo_count = report_payload.get("repo_count")
    classification_keys = (
        "current",
        "no_dad_surface",
        "upgrade_recommended",
        "upgrade_required",
    )
    classification_counts_are_strict = all(
        _is_nonnegative_plain_int(classification_counts.get(key, 0))
        for key in classification_keys
    )
    explicit_classification_total = (
        sum(classification_counts.get(key, 0) for key in classification_keys)
        if classification_counts_are_strict
        else -1
    )
    repo_machine_ready = bool(
        report_status == "readable"
        and report_payload.get("schema_version") == "0.1.0"
        and report_payload.get("transport_surface_version") == TRANSPORT_SURFACE_VERSION
        and _is_nonnegative_plain_int(reported_repo_count)
        and reported_repo_count > 0
        and reported_repo_count == len(repos)
        and explicit_classification_total == reported_repo_count
        and "upgrade_required" in classification_counts
        and classification_counts.get("upgrade_required") == 0
    )
    repo_gate_complete = repo_gate_verified and repo_machine_ready
    cloudflare_gate_verified = (
        "phase-13-cloudflare-relay-deferred" in verified_gate_ids
    )

    human_gates = {
        "data_root_migration": _gate(
            complete=data_root_complete,
            status=(
                "verified_and_operational"
                if data_root_complete
                else "active_pending_human_gate_record"
                if data_root_active
                else "pending_human_apply"
            ),
            evidence={
                "data_root": str(data_root),
                "mode": data_mode,
                "human_gate_verified": data_root_gate_verified,
                "note": (
                    "legacy mode is the fail-safe fallback until an initialized "
                    "DAD_DATA_ROOT marker is present"
                ),
            },
        ),
        "journal_repo_checkpoint": _gate(
            complete=journal_machine_ready and journal_gate_verified,
            status=journal_gate_status,
            evidence={
                "last_checkpoint_at": last_checkpoint_at,
                "checkpoint_due": journal.get("checkpoint_due"),
                "new_record_count": journal.get("new_record_count"),
                "journal_repo_status": journal_repo or None,
                "human_gate_verified": journal_gate_verified,
            },
        ),
        "daemon_schedule": _gate(
            complete=daemon_machine_ready and daemon_gate_verified,
            status=daemon_schedule_status,
            evidence={
                "daemon_status": daemon.get("status"),
                "stale": daemon.get("stale"),
                "heartbeat_path": daemon.get("heartbeat_path"),
                "scheduler_status": scheduler or None,
                "human_gate_verified": daemon_gate_verified,
                "note": (
                    "Task Scheduler evidence is read-only and machine-level; "
                    "the phase gate still needs a human approval/evidence record."
                ),
            },
        ),
        "repo_upgrade_wave": _gate(
            complete=repo_gate_complete,
            status=(
                "verified_and_operational"
                if repo_gate_complete
                else "machine_ready_pending_human_gate_record"
                if repo_machine_ready
                else "pending_reviewed_enrollment_wave"
            ),
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
                "human_gate_verified": repo_gate_verified,
            },
        ),
        "cloudflare_relay": _gate(
            complete=cloudflare_gate_verified,
            status=(
                "verified_deferred"
                if cloudflare_gate_verified
                else "deferred_until_phase_10a_cloud_boundary_reviewed"
            ),
            evidence={
                "implemented": False,
                "human_gate_verified": cloudflare_gate_verified,
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
        "graph_surface_status_readable": graph_surfaces.get("schema_version")
        == "dad.graph_surface.status.v1",
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
            "graph_surface_status_readable",
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
        "graph_surfaces": graph_surfaces,
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


def compact_transport_readiness(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stable operator/UI summary without embedding large evidence bodies."""
    gates = payload.get("human_gates")
    compact_gates: dict[str, dict[str, Any]] = {}
    if isinstance(gates, Mapping):
        for name, raw_gate in gates.items():
            gate = raw_gate if isinstance(raw_gate, Mapping) else {}
            compact_gates[str(name)] = {
                "complete": bool(gate.get("complete")),
                "status": str(gate.get("status") or "unknown"),
            }
    journal = payload.get("journal")
    journal = journal if isinstance(journal, Mapping) else {}
    repo_status = journal.get("repo_status")
    repo_status = repo_status if isinstance(repo_status, Mapping) else {}
    daemon = payload.get("daemon")
    daemon = daemon if isinstance(daemon, Mapping) else {}
    audit = payload.get("audit")
    audit = audit if isinstance(audit, Mapping) else {}
    return {
        "schema_version": "dad.transport.readiness.summary.v1",
        "generated_at": payload.get("generated_at"),
        "overall_status": payload.get("overall_status"),
        "local_ready": bool(payload.get("local_ready")),
        "human_gate_summary": payload.get("human_gate_summary", {}),
        "human_gates": compact_gates,
        "classification_counts": audit.get("classification_counts", {}),
        "daemon": {
            "status": daemon.get("status"),
            "stale": daemon.get("stale"),
        },
        "journal": {
            "checkpoint_due": journal.get("checkpoint_due"),
            "new_record_count": journal.get("new_record_count"),
            "last_checkpoint_at": journal.get("last_checkpoint_at"),
            "status": repo_status.get("status"),
            "machine_ready": bool(repo_status.get("machine_ready")),
            "journal_engine_version_seen": repo_status.get(
                "journal_engine_version_seen"
            ),
            "journal_engine_version_expected": repo_status.get(
                "journal_engine_version_expected"
            ),
            "journal_engine_version_current": repo_status.get(
                "journal_engine_version_current"
            ),
            "integrity_valid": bool(
                (repo_status.get("file_index_integrity") or {}).get("valid")
                if isinstance(repo_status.get("file_index_integrity"), Mapping)
                else False
            ),
            "verification_backend": (
                repo_status.get("file_index_integrity") or {}
            ).get("verification_backend")
            if isinstance(repo_status.get("file_index_integrity"), Mapping)
            else None,
        },
        "operator_next_steps": payload.get("operator_next_steps", []),
        "transport_surface_version": payload.get("transport_surface_version"),
        "authority_boundary": payload.get("authority_boundary"),
    }
