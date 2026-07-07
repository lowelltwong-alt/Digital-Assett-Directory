from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional, cast

import typer
from rich.console import Console

from .archaeology import (
    append_repo_learning_event,
    install_repo_learning_loop,
    write_archaeology_outputs,
    write_root_cause_lesson_outputs,
)
from .architecture_consult import write_architecture_consult_outputs
from .asset_families import (
    write_asset_family_reports,
    write_learning_loop_outputs,
    write_workflow_sweep_reports,
)
from .background_connections import write_background_connection_outputs
from .calibration import (
    build_asset_calibration_review_queue,
    import_asset_calibration_review_csv,
    load_asset_calibration_reviews,
    load_catalog_assets,
    update_asset_calibration_review_file,
    write_asset_calibration_evidence,
    write_asset_calibration_summary,
    write_asset_calibration_review_csv,
    write_phase2_calibration_reports,
    write_phase25_score_delta_validation,
)
from .catalog import catalog_status, run_scan
from .ci_release_scope import write_ci_release_artifact_scope_outputs
from .config import (
    GitHubSource,
    describe_hub_resolution,
    hub_locator_path,
    load_config,
    load_github_repositories_file,
    write_hub_locator,
)
from .context_pack import build_context_pack, write_context_pack
from .dad_library import (
    build_dad_cadence_plan,
    calibration_report,
    check_offering_novelty,
    discover_harness_opportunities,
    harness_evaluate,
    harness_package,
    harness_research,
    list_harnesses,
    load_address_model_registry,
    load_asset_patterns,
    load_asset_recognition_methodology,
    load_harness_discovery_methodology,
    load_needs,
    load_offerings,
    match_asset_patterns,
    match_repo_offerings,
    collect_repo_local_assets,
    reconcile_repo_inventory,
    recommend_harnesses,
    record_usage,
    repo_local_asset_surface_standard,
    scout_asset_candidates,
    usage_upgrades,
    write_repo_inventory_rust_probe_parity,
)
from .database import CatalogDB
from .daemon import (
    daemon_status,
    install_task_scheduler,
    run_daemon_cycle,
    task_scheduler_plan,
    task_scheduler_status,
)
from .enrollment import (
    apply_enrollment,
    build_enrollment_plan,
    discover_enrollment_candidates,
    enrollment_status_all,
    select_enrollment_policies,
)
from .event_pipeline import (
    build_event_record,
    collect_events,
    record_repo_event,
    write_event_pipeline_report,
)
from .exceptions_lake import (
    BackfillAuthorization,
    backfill_exception_candidates,
    collect_exception_fix_outcomes,
    collect_exception_events,
    evaluate_exception_learning_readiness_scenarios,
    exception_lake_paths,
    hard_issue_lookup,
    load_event_type_registry,
    record_exception_backfill_review_decision,
    record_exception_fix_outcome,
    record_exception_event,
    summarize_exception_backfill_review_decisions,
    write_exception_backfill_refresh_plan,
    write_exception_backfill_review_queue,
    write_exception_fix_outcome_requests,
    write_exception_learning_queue,
    write_exception_report,
    write_exception_source_packet_opportunities,
    write_exception_source_packet_requests,
)
from .exception_capture import (
    discover_capture_audit_repos,
    evaluate_exception_taxonomy_coverage,
    evaluate_capture_scenarios,
    load_capture_pattern_registry,
    observed_capture_audit_gap_count,
    suggest_exception_capture,
    write_exception_backfill_readiness,
    write_exception_backfill_wave_plan,
    write_exception_capture_emission_simulation,
    write_exception_capture_gap_review_queue,
    write_phase6_machine_evidence_summary,
    write_exception_capture_remediation_plan,
    write_exception_capture_surface_refresh_notices,
    write_observed_capture_audit,
)
from .governance import enforce_postflight, install_governance, scaffold_new_repo
from .governance_map_scope import write_governance_map_adoption_scope_outputs
from .learning import (
    add_asset_use_feedback,
    add_lesson,
    add_review_feedback,
    build_lesson_graph,
    midflight,
    postflight,
    preflight,
    rebuild_lesson_routes,
)
from .lesson_automation_coverage import write_lesson_automation_coverage_outputs
from .lesson_action_queue import (
    DECISION_TEMPLATE_PATH,
    load_lesson_automation_path_filter_file,
    load_lesson_automation_decisions,
    summarize_lesson_automation_decisions,
    update_lesson_automation_decision_record,
    write_lesson_automation_approval_impact_outputs,
    write_lesson_automation_approval_packet_outputs,
    write_lesson_automation_decision_template_outputs,
    write_lesson_automation_decisions,
    write_lesson_automation_execution_plan_outputs,
    write_lesson_automation_next_action_outputs,
)
from .manual_tasks import write_manual_task_queue
from .mail_center import (
    MAIL_MIRROR_DIR,
    MAX_MAIL_RECORD_BYTES,
    check_outbox_novelty,
    append_jsonl_locked,
    collect_mail,
    compose_asset_suggestion,
    compose_mail,
    deliver_mail,
    diagnose_mail_dirty_state,
    digest_mail,
    invalid_mail_quarantine_path,
    legacy_delivery_allowlist_path,
    repair_route_audit_gaps,
    release_mail,
    resurface_deferred_mail,
    review_central_mail,
    route_mail,
    review_mail,
    triage_mail,
)
from .orphan_adapter import run_orphan_radar
from .operational import (
    DOCTOR_CHILD_PROBE_ENV,
    UNAVAILABLE_HUB_POLICY,
    build_deployment_status,
    write_operational_readiness_report,
)
from .priority_content_lessons import (
    build_priority_content_lesson_review_queue,
    load_priority_content_lesson_candidates,
    load_priority_content_lesson_reviews,
    summarize_priority_content_lesson_reviews,
    update_priority_content_lesson_review_file,
    write_learning_rule_promotion_candidate_outputs,
    write_priority_content_lesson_outputs,
    write_priority_content_lesson_review_template_outputs,
)
from .priority_content_scope import (
    write_priority_content_extract_outputs,
    write_priority_content_extract_scope_outputs,
)
from .proposals import (
    ProposalEngineOption,
    build_proposal_review_queue,
    import_proposal_review_csv,
    load_roadmap_relevance_context,
    load_generated_proposals,
    load_proposal_reviews,
    run_proposal_engines,
    update_proposal_review_file,
    write_proposal_review_csv,
    write_proposal_review_unblind_map,
    write_proposal_calibration_evidence,
    write_proposal_outputs,
    write_proposal_review_results_summary,
)
from .public_safe_sweep import write_public_safe_source_sweep
from .recommendations import recommend_skills_and_agents, recommend_swarm
from .readiness import write_downstream_pilot_candidates, write_phase45_readiness_reports
from .reference_architectures import write_reference_architecture_outputs
from .research import research_missing_parts
from .research_intake import (
    build_language_playbook_report,
    build_language_frontier_watchlist,
    build_research_intake_graph,
    intake_external_candidate,
    list_intake,
    promote_intake,
    record_screening,
)
from .repo_buildout import load_default_repo_buildout_artifacts, write_repo_buildout_outputs
from .repo_completion import (
    write_repo_completion_dashboard_outputs,
    write_repo_completion_proof_check_outputs,
    write_repo_completion_wave_plan_outputs,
)
from .repo_learning_scope import write_repo_learning_loop_install_scope_outputs
from .roadmap import check_roadmap, write_human_gate_review_packet
from .rust_bridge import (
    run_dad_event_log_check,
    run_dad_mail_spool_check,
    run_dad_phase8_evidence_check,
    run_dad_repo_inventory_probe,
    run_dad_scan_core,
)
from .rust_rollout import (
    apply_rust_rollout_scaffold,
    build_rust_rollout_mail_packets,
    load_rust_repo_records,
    summarize_rust_rollout_lessons,
    write_rust_rollout_plan,
)
from .semantic_evolution import write_semantic_evolution_outputs
from .template_library import validate_template_registry, write_template_library_report
from .test_parity import run_test_parity
from .transport import (
    DATA_PLANE_PATHS,
    apply_data_migration,
    audit_all_repo_transport,
    data_path,
    data_relative_path,
    init_data_root,
    plan_data_migration,
    resolve_data_root,
)
from .transport_readiness import build_transport_readiness
from .validation import validate_repo
from .workflow_parts import (
    build_workflow_part_review_queue,
    load_workflow_part_reviews,
    load_workflow_parts,
    update_workflow_part_review_file,
    write_workflow_part_calibration_evidence,
    write_workflow_part_outputs,
    write_workflow_part_review_results_summary,
    write_workflow_part_review_template_outputs,
    write_workflow_part_usage_guidance,
)
from .utils import append_jsonl, find_repo_root, json_dumps, safe_relative, sha256_bytes, utc_now

app = typer.Typer(no_args_is_help=True, help="Digital Asset Directory portfolio intelligence CLI.")
lesson_app = typer.Typer(no_args_is_help=True)
app.add_typer(lesson_app, name="lesson")
agent_app = typer.Typer(no_args_is_help=True)
app.add_typer(agent_app, name="agent")
roadmap_app = typer.Typer(no_args_is_help=True)
app.add_typer(roadmap_app, name="roadmap")
research_app = typer.Typer(no_args_is_help=True)
app.add_typer(research_app, name="research")
template_app = typer.Typer(no_args_is_help=True)
app.add_typer(template_app, name="templates")
orphan_app = typer.Typer(no_args_is_help=True)
app.add_typer(orphan_app, name="orphan-radar")
test_app = typer.Typer(no_args_is_help=True)
app.add_typer(test_app, name="test")
recommend_app = typer.Typer(no_args_is_help=True)
app.add_typer(recommend_app, name="recommend")
mail_app = typer.Typer(no_args_is_help=True)
app.add_typer(mail_app, name="mail")
event_app = typer.Typer(no_args_is_help=True)
app.add_typer(event_app, name="events")
enroll_app = typer.Typer(no_args_is_help=True)
app.add_typer(enroll_app, name="enroll")
dad_app = typer.Typer(no_args_is_help=True)
app.add_typer(dad_app, name="dad")
usage_app = typer.Typer(no_args_is_help=True)
app.add_typer(usage_app, name="usage")
harness_app = typer.Typer(no_args_is_help=True)
app.add_typer(harness_app, name="harness")
exceptions_app = typer.Typer(no_args_is_help=True)
app.add_typer(exceptions_app, name="exceptions")
rust_app = typer.Typer(no_args_is_help=True)
app.add_typer(rust_app, name="rust")
rust_rollout_app = typer.Typer(no_args_is_help=True)
app.add_typer(rust_rollout_app, name="rust-rollout")
data_app = typer.Typer(no_args_is_help=True)
app.add_typer(data_app, name="data")
transport_app = typer.Typer(no_args_is_help=True)
app.add_typer(transport_app, name="transport")
daemon_app = typer.Typer(no_args_is_help=True)
app.add_typer(daemon_app, name="daemon")
console = Console()


def _cfg(config: Optional[Path] = None, hub: Optional[Path] = None):
    try:
        return load_config(config, repo_root=hub)
    except FileNotFoundError as exc:
        detail_hash = f"sha256:{sha256_bytes(str(exc).encode('utf-8'))}"
        console.print_json(
            data={
                "schema": "dad_command_error.v1",
                "status": "blocked_dad_hub_unavailable",
                "error": "DAD hub unavailable. Set --hub, DAD_HUB, or ~/.dad/hub.json.",
                "detail": "DAD hub could not be resolved or validated.",
                "detail_hash": detail_hash,
                "authority_boundary": (
                    "This controlled failure does not authorize cross-repo writes, "
                    "public release, enrollment apply/update, protected repo work, "
                    "or mail containing sensitive payloads."
                ),
            }
        )
        raise typer.Exit(2) from None


def _repo_path(repo_root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else repo_root / path


def _transport_repo_rows(cfg) -> list[dict[str, Any]]:
    rows_by_path: dict[str, dict[str, Any]] = {}

    def add_policy(policy: object, enabled_attr: str) -> None:
        if not bool(getattr(policy, enabled_attr, True)):
            return
        path = Path(getattr(policy, "path"))
        key = str(path.resolve())
        row = rows_by_path.setdefault(
            key,
            {
                "id": str(getattr(policy, "id", path.name)),
                "path": str(path),
                "write_protected": False,
            },
        )
        if bool(getattr(policy, "write_protected", False)):
            row["write_protected"] = True

    for policy in getattr(cfg, "mail_repos", []) or []:
        add_policy(policy, "mail_enabled")
    for policy in getattr(cfg, "exception_repos", []) or []:
        add_policy(policy, "exceptions_enabled")
    for policy in getattr(cfg, "enrollment_repos", []) or []:
        add_policy(policy, "enrollment_enabled")
    return sorted(rows_by_path.values(), key=lambda row: str(row["id"]))


@data_app.command("status")
def data_status(hub: Optional[Path] = typer.Option(None)) -> None:
    cfg = _cfg(hub=hub)
    root, mode = resolve_data_root(cfg.repo_root)
    console.print_json(
        data={
            "schema_version": "dad.data.status.v1",
            "hub_root": str(cfg.repo_root),
            "data_root": str(root),
            "mode": mode,
            "surfaces": {
                logical: str(data_path(cfg.repo_root, logical))
                for logical in sorted(DATA_PLANE_PATHS)
            },
        }
    )


@data_app.command("init")
def data_init(
    target: Path = typer.Option(Path.home() / ".dad" / "data"),
    hub: Optional[Path] = typer.Option(None),
    force_onedrive: bool = typer.Option(False, "--force-onedrive"),
) -> None:
    cfg = _cfg(hub=hub)
    console.print_json(
        data=init_data_root(
            target,
            hub_root=cfg.repo_root,
            force_onedrive=force_onedrive,
        )
    )


@data_app.command("migrate")
def data_migrate(
    target: Path = typer.Option(Path.home() / ".dad" / "data"),
    hub: Optional[Path] = typer.Option(None),
    apply: bool = typer.Option(False, "--apply/--plan-only"),
    force_onedrive: bool = typer.Option(False, "--force-onedrive"),
) -> None:
    cfg = _cfg(hub=hub)
    result = (
        apply_data_migration(cfg.repo_root, target, force_onedrive=force_onedrive)
        if apply
        else plan_data_migration(cfg.repo_root, target)
    )
    console.print_json(data=result)


@transport_app.command("audit")
def transport_audit(hub: Optional[Path] = typer.Option(None)) -> None:
    cfg = _cfg(hub=hub)
    console.print_json(data=audit_all_repo_transport(cfg.repo_root, _transport_repo_rows(cfg)))


@transport_app.command("readiness")
def transport_readiness(
    hub: Optional[Path] = typer.Option(None),
    stale_hours: int = typer.Option(26),
    inspect_scheduler: bool = typer.Option(False, "--inspect-scheduler"),
    task_name: str = typer.Option("DAD Daemon Run Cycle"),
    shim: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    scheduler = (
        task_scheduler_status(cfg.repo_root, task_name=task_name, shim=shim)
        if inspect_scheduler
        else None
    )
    console.print_json(
        data=build_transport_readiness(
            cfg.repo_root,
            transport_repos=_transport_repo_rows(cfg),
            stale_hours=stale_hours,
            scheduler_status=scheduler,
        )
    )


@daemon_app.command("run-cycle")
def daemon_run_cycle(
    hub: Optional[Path] = typer.Option(None),
    skip_transport_audit: bool = typer.Option(False, "--skip-transport-audit"),
    skip_graphs: bool = typer.Option(False, "--skip-graphs"),
    deliver_local_caches: bool = typer.Option(
        False,
        "--deliver-local-caches",
        help="Also write routed mail to reviewed repo-local inbox caches.",
    ),
) -> None:
    cfg = _cfg(hub=hub)
    console.print_json(
        data=run_daemon_cycle(
            cfg.repo_root,
            mail_repos=cfg.mail_repos,
            exception_repos=cfg.exception_repos,
            deliver_local_caches=deliver_local_caches,
            rebuild_graphs=not skip_graphs,
            transport_repos=None if skip_transport_audit else _transport_repo_rows(cfg),
        )
    )


@daemon_app.command("status")
def daemon_status_command(
    hub: Optional[Path] = typer.Option(None),
    stale_hours: int = typer.Option(26),
) -> None:
    cfg = _cfg(hub=hub)
    console.print_json(data=daemon_status(cfg.repo_root, stale_hours=stale_hours))


@daemon_app.command("install")
def daemon_install(
    hub: Optional[Path] = typer.Option(None),
    task_name: str = typer.Option("DAD Daemon Run Cycle"),
    schedule_time: str = typer.Option("09:00"),
    twice_daily: bool = typer.Option(False, "--twice-daily"),
    shim: Optional[Path] = typer.Option(None),
    apply: bool = typer.Option(False, "--apply/--plan-only"),
) -> None:
    cfg = _cfg(hub=hub)
    plan = task_scheduler_plan(
        cfg.repo_root,
        task_name=task_name,
        schedule_time=schedule_time,
        twice_daily=twice_daily,
        shim=shim,
    )
    console.print_json(data=install_task_scheduler(plan) if apply else plan)


@daemon_app.command("task-status")
def daemon_task_status(
    hub: Optional[Path] = typer.Option(None),
    task_name: str = typer.Option("DAD Daemon Run Cycle"),
    shim: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    console.print_json(
        data=task_scheduler_status(
            cfg.repo_root,
            task_name=task_name,
            shim=shim,
        )
    )


def _rust_rollout_snapshot_promotion_log(repo_root: Path) -> Path:
    return data_relative_path(
        repo_root,
        Path("processed") / "mail" / "archive" / "rust_rollout_snapshot_promotion.jsonl",
    )


def _rust_rollout_snapshot_promotion_record(
    *,
    repo_root: Path,
    out_dir: Path,
    ack: str,
    packet_count: int,
) -> dict[str, object]:
    packet_manifest = []
    for path in sorted(out_dir.rglob("*.json")):
        if not path.is_file():
            continue
        packet_manifest.append(
            {
                "path": safe_relative(path, repo_root),
                "sha256": f"sha256:{sha256_bytes(path.read_bytes())}",
            }
        )
    return {
        "schema_version": "dad_rust_rollout_snapshot_promotion.v1",
        "event_type": "rust_rollout_reference_snapshot_promoted",
        "created_at": utc_now(),
        "operation": "rust-rollout build-mail",
        "out_dir": safe_relative(out_dir, repo_root),
        "acknowledgement": ack,
        "packet_count": packet_count,
        "snapshot_json_file_count": len(packet_manifest),
        "packet_manifest": packet_manifest,
        "authority_boundary": (
            "This audit row records intentional promotion of tracked "
            "mail/outbox/rust_rollout reference snapshots. It is not delivery, "
            "release approval, target repo adoption, or live mail routing evidence."
        ),
    }


def _is_under_or_equal(path: Path, root: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    return resolved_path == resolved_root or resolved_path.is_relative_to(resolved_root)


def _system_temp_root() -> Path:
    return Path(tempfile.gettempdir()).resolve(strict=False)


def _local_path_ref(path: Path, root: Path) -> str:
    try:
        resolved_path = path.resolve(strict=False)
        resolved_root = root.resolve(strict=False)
        if resolved_path == resolved_root or resolved_path.is_relative_to(resolved_root):
            return safe_relative(resolved_path, resolved_root)
    except OSError:
        pass
    normalized = str(path).replace("\\", "/")
    return f"path-sha256:{sha256_bytes(normalized.encode('utf-8'))}"


def _annotate_mail_storm_scope(result: dict, *, requested_all: bool) -> None:
    coverage = result.get("mailbox_coverage")
    if not isinstance(coverage, dict):
        coverage = {}
    repo_scope = result.setdefault("repo_scope", {})
    if not isinstance(repo_scope, dict):
        repo_scope = {}
        result["repo_scope"] = repo_scope
    action_summary = result.setdefault("action_summary", {})
    if not isinstance(action_summary, dict):
        action_summary = {}
        result["action_summary"] = action_summary
    storm_scope_verified = (
        requested_all
        and bool(repo_scope.get("external_repo_mailboxes_checked"))
        and int(coverage.get("unreviewed_mailbox_candidate_count", 0) or 0) == 0
        and int(coverage.get("reviewed_enabled_not_checked_count", 0) or 0) == 0
        and not str(coverage.get("warning", "")).strip()
    )
    repo_scope["storm_scope_verified"] = storm_scope_verified
    repo_scope["storm_scope_basis"] = (
        "--repo all checked reviewed mail.repos and mailbox coverage"
        if storm_scope_verified
        else "not storm-verified; use --repo all with reviewed mail.repos coverage"
    )
    action_summary["safe_for_mail_storm_operations"] = (
        storm_scope_verified
        and bool(action_summary.get("safe_to_collect"))
        and bool(action_summary.get("safe_to_route"))
        and bool(action_summary.get("safe_to_deliver"))
    )
    action_summary["safe_for_ingest_operations"] = (
        storm_scope_verified
        and bool(action_summary.get("safe_to_collect"))
        and bool(action_summary.get("safe_to_route"))
    )
    action_summary["safe_for_delivery_operations"] = bool(
        action_summary.get("safe_for_mail_storm_operations")
    )


_MAIL_STORM_OPERATION_GATES = {
    "all": "safe_for_mail_storm_operations",
    "ingest": "safe_for_ingest_operations",
    "delivery": "safe_for_delivery_operations",
}


def _mail_storm_operation_key(operation: str) -> str:
    normalized = operation.strip().lower()
    if normalized not in _MAIL_STORM_OPERATION_GATES:
        allowed = ", ".join(sorted(_MAIL_STORM_OPERATION_GATES))
        raise typer.BadParameter(f"--operation must be one of: {allowed}")
    return normalized


def _mail_storm_operation_safe(gate: dict[str, Any], operation: str) -> bool:
    key = _MAIL_STORM_OPERATION_GATES[_mail_storm_operation_key(operation)]
    return bool(gate.get(key))


def _mail_delivery_policy_summary(
    selected: list[Path],
    policies: list[Any],
) -> dict[str, Any]:
    policies_by_path = {str(policy.path.resolve()): policy for policy in policies}
    blocked: list[dict[str, Any]] = []
    for repo in selected:
        policy = policies_by_path.get(str(repo.resolve()))
        if policy is None:
            continue
        reasons: list[str] = []
        if not getattr(policy, "delivery_allowed", True):
            reasons.append("delivery_allowed=false")
        if getattr(policy, "write_protected", False):
            reasons.append("write_protected=true")
        if reasons:
            blocked.append(
                {
                    "repo_id": str(getattr(policy, "id", "unknown")),
                    "repo_ref": f"repo:{getattr(policy, 'id', 'unknown')}",
                    "reasons": reasons,
                    "write_protection_reason": _mail_repair_plan_safe_value(
                        str(getattr(policy, "write_protection_reason", ""))
                    ),
                }
            )
    return {
        "schema_version": "dad_mail_delivery_policy_summary.v1",
        "evaluated_repo_count": len(selected),
        "blocked_delivery_repo_count": len(blocked),
        "all_selected_delivery_allowed": not blocked,
        "blocked_delivery_repos": blocked,
        "authority_boundary": (
            "Delivery policy is separate from mailbox cleanliness. A clean storm "
            "gate does not authorize delivery to repos whose reviewed policy blocks "
            "delivery or marks the mailbox write-protected."
        ),
    }


def _mail_storm_gate_report(
    result: dict,
    *,
    repo_args: list[str],
    requested_operation: str = "all",
) -> dict:
    operation = _mail_storm_operation_key(requested_operation)
    action_summary = result.get("action_summary", {})
    if not isinstance(action_summary, dict):
        action_summary = {}
    summary = result.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    repo_scope = result.get("repo_scope", {})
    if not isinstance(repo_scope, dict):
        repo_scope = {}
    mailbox_coverage = result.get("mailbox_coverage", {})
    if not isinstance(mailbox_coverage, dict):
        mailbox_coverage = {}
    delivery_policy = result.get("delivery_policy", {})
    if not isinstance(delivery_policy, dict):
        delivery_policy = {}
    worktree_state = result.get("worktree_state", {})
    if not isinstance(worktree_state, dict):
        worktree_state = {}

    coverage_blocked = bool(
        int(mailbox_coverage.get("unreviewed_mailbox_candidate_count", 0) or 0)
        or int(mailbox_coverage.get("reviewed_enabled_not_checked_count", 0) or 0)
        or str(mailbox_coverage.get("warning", "")).strip()
    )
    mail_blocked = bool(result.get("dirty")) or not (
        bool(action_summary.get("safe_to_collect"))
        and bool(action_summary.get("safe_to_route"))
        and bool(action_summary.get("safe_to_deliver"))
    )
    delivery_policy_blocked = not bool(delivery_policy.get("all_selected_delivery_allowed", True))
    storm_scope_verified = bool(repo_scope.get("storm_scope_verified"))
    worktree_dirty = bool(result.get("worktree_dirty"))

    if mail_blocked and coverage_blocked:
        gate_status = "blocked_mail_dirty_and_coverage_gap"
    elif mail_blocked:
        gate_status = "blocked_mail_dirty"
    elif coverage_blocked:
        gate_status = "blocked_coverage_gap"
    elif not storm_scope_verified:
        gate_status = "hub_or_partial_scope_only"
    elif delivery_policy_blocked:
        gate_status = "mail_safe_delivery_policy_hold"
    elif worktree_dirty:
        gate_status = "mail_safe_worktree_dirty"
    elif str(result.get("status", "")) != "clean":
        gate_status = "mail_safe_with_observations"
    else:
        gate_status = "mail_safe"

    safe_for_selected_scope = not mail_blocked and not coverage_blocked
    collect_route_safe = safe_for_selected_scope and storm_scope_verified
    deliver_safe = collect_route_safe and not delivery_policy_blocked
    safe_for_ingest_operations = collect_route_safe
    safe_for_delivery_operations = deliver_safe
    safe_for_mail_storm_operations = collect_route_safe and deliver_safe
    blocked_operation_classes = [
        operation
        for operation, allowed in (
            ("collect", collect_route_safe),
            ("route", collect_route_safe),
            ("deliver", deliver_safe),
        )
        if not allowed
    ]
    blocking_reasons: list[str] = []
    if mail_blocked:
        blocking_reasons.append("mail_dirty")
    if coverage_blocked:
        blocking_reasons.append("coverage_gap")
    if not storm_scope_verified and not coverage_blocked:
        blocking_reasons.append("partial_or_hub_local_scope")
    if delivery_policy_blocked:
        blocking_reasons.append("delivery_policy_hold")

    next_actions = list(action_summary.get("next_actions", []))
    if gate_status == "hub_or_partial_scope_only":
        next_actions.append(
            "Rerun `mail storm-gate --repo all` before multi-repo collection, routing, or delivery."
        )
    if coverage_blocked:
        next_actions.append(
            "Run `mail discover-repos`; classify unreviewed mailboxes before moving mail."
        )
    if delivery_policy_blocked:
        next_actions.append(
            "Do not deliver to selected repos blocked by reviewed mail policy; narrow scope "
            "or change policy with human review."
        )
    if mail_blocked:
        next_actions.append(
            "Run full `mail doctor --repo all` and repair or quarantine mailbox issues before collect/route/deliver."
        )
    if worktree_dirty and safe_for_selected_scope:
        next_actions.append(
            "Review git status before push/merge; worktree dirt is not mailbox corruption by itself."
        )

    return {
        "schema_version": "dad_mail_storm_gate.v1",
        "generated_at": result.get("generated_at", utc_now()),
        "gate_status": gate_status,
        "dirty_state_fingerprint": str(
            result.get("dirty_state_fingerprint") or _mail_dirty_state_fingerprint(result)
        ),
        "requested_repos": repo_args,
        "requested_operation": operation,
        "safe_for_selected_scope": safe_for_selected_scope,
        "safe_for_mail_storm_operations": safe_for_mail_storm_operations,
        "safe_for_ingest_operations": safe_for_ingest_operations,
        "safe_for_delivery_operations": safe_for_delivery_operations,
        "selected_operation_safe": _mail_storm_operation_safe(
            {
                "safe_for_mail_storm_operations": safe_for_mail_storm_operations,
                "safe_for_ingest_operations": safe_for_ingest_operations,
                "safe_for_delivery_operations": safe_for_delivery_operations,
            },
            operation,
        ),
        "safe_to_collect": collect_route_safe,
        "safe_to_route": collect_route_safe,
        "safe_to_deliver": deliver_safe,
        "blocked_operation_classes": blocked_operation_classes,
        "blocking_reasons": blocking_reasons,
        "operation_safety_contract": (
            "Use safe_for_ingest_operations for collect/route decisions and "
            "safe_for_delivery_operations for repo inbox writes. "
            "safe_for_mail_storm_operations remains the all-operations gate."
        ),
        "requires_human_review": bool(coverage_blocked or mail_blocked or delivery_policy_blocked),
        "spool_dirty": bool(result.get("spool_dirty", result.get("dirty", False))),
        "worktree_dirty": worktree_dirty,
        "worktree_dirty_does_not_change_mail_dirty": bool(
            result.get("worktree_dirty_does_not_change_mail_dirty", True)
        ),
        "doctor_status": result.get("status"),
        "mail_summary": {
            "issue_count": int(summary.get("issue_count", 0) or 0),
            "blocking_issue_count": int(action_summary.get("blocking_issue_count", 0) or 0),
            "repairable_issue_count": int(action_summary.get("repairable_issue_count", 0) or 0),
            "legacy_observation_count": int(action_summary.get("legacy_observation_count", 0) or 0),
            "lifecycle_observation_count": int(
                action_summary.get("lifecycle_observation_count", 0) or 0
            ),
            "rust_packet_count": int(summary.get("rust_packet_count", 0) or 0),
            "source_outbox_duplicate_identity_count": int(
                summary.get("source_outbox_duplicate_identity_count", 0) or 0
            ),
            "cross_source_outbox_duplicate_identity_count": int(
                summary.get("cross_source_outbox_duplicate_identity_count", 0) or 0
            ),
            "unknown_source_outbox_duplicate_identity_count": int(
                summary.get("unknown_source_outbox_duplicate_identity_count", 0) or 0
            ),
            "invalid_mail_packet_count": int(summary.get("invalid_mail_packet_count", 0) or 0),
            "invalid_mail_packet_quarantine_count": int(
                summary.get("invalid_mail_packet_quarantine_count", 0) or 0
            ),
        },
        "repo_scope": repo_scope,
        "mailbox_coverage": mailbox_coverage,
        "delivery_policy": delivery_policy,
        "worktree_state": {
            "evaluated": worktree_state.get("evaluated", False),
            "is_git_worktree": worktree_state.get("is_git_worktree", False),
            "status": worktree_state.get("status", "unknown"),
            "changed_count": int(worktree_state.get("changed_count", 0) or 0),
            "counts_by_category": worktree_state.get("counts_by_category", {}),
            "guidance": worktree_state.get("guidance", []),
        },
        "write_target_guidance": result.get("write_target_guidance", {}),
        "operator_commands": {
            "authoritative_doctor": (
                "python -m digital_asset_directory.cli mail doctor --repo all "
                "--summary-only --fail-on-dirty --fail-on-coverage-gap"
            ),
            "coverage_discovery": "python -m digital_asset_directory.cli mail discover-repos",
            "rust_leaf_probe": "python -m digital_asset_directory.cli rust mail-spool-check",
        },
        "next_actions": next_actions,
        "authority_boundary": (
            "This storm gate is read-only. It does not collect, route, deliver, repair, "
            "promote Rust rollout snapshots, approve public release, or authorize repo writes."
        ),
    }


_REPAIR_PLAN_LOCAL_PATH_RE = re.compile(
    r"(?i)(^[a-z]:[\\/]|^\\\\|^/tmp[\\/]|/tmp[\\/]|^/home/runner[\\/]|"
    r"^/users[\\/]|[\\/]users[\\/]|[\\/]pytest-of-|onedrive|git projects)"
)


def _mail_repair_issue_severity(issue_type: str) -> str:
    if issue_type in {
        "central_inbox_uncollected_row",
        "central_inbox_missing_collection_audit",
        "central_inbox_missing_collection_provenance",
        "central_outbox_missing_route_audit",
        "central_outbox_unrouted_row",
        "repo_inbox_without_delivery_log",
        "rust_rollout_packet_write_claim",
    }:
        return "critical"
    if issue_type in {
        "central_inbox_duplicate_logical_identity",
        "central_outbox_route_hash_mismatch",
        "central_outbox_missing_source_inbox",
        "unknown_source_outbox_duplicate_identity",
        "source_outbox_unstable",
        "invalid_mail_packet",
        "malformed_jsonl",
        "oversized_jsonl_record",
        "duplicate_jsonl_identity",
        "cross_file_same_stage_duplicate_identity",
        "cross_source_outbox_duplicate_identity",
        "repo_inbox_delivery_hash_mismatch",
        "rust_rollout_packet_invalid",
        "rust_rollout_packet_delivery_status",
        "rust_rollout_duplicate_packet_identity",
        "rust_rollout_semantic_identity_conflict",
    }:
        return "high"
    if issue_type in {"jsonl_lock", "atomic_temp_fragment"}:
        return "medium"
    return "low"


def _mail_repair_plan_safe_value(value: Any) -> Any:
    if isinstance(value, str):
        if "|" in value:
            parts = [_mail_repair_plan_safe_value(part) for part in value.split("|")]
            return "|".join(str(part) for part in parts)
        if _REPAIR_PLAN_LOCAL_PATH_RE.search(value):
            normalized = value.replace("\\", "/")
            return f"path-sha256:{sha256_bytes(normalized.encode('utf-8'))}"
        return value
    if isinstance(value, list):
        return [_mail_repair_plan_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _mail_repair_plan_safe_value(item)
            for key, item in value.items()
            if str(key) not in {"payload", "raw", "raw_value", "raw_text", "stdout", "stderr"}
        }
    return value


def _mail_repair_issue_sample(issue: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "issue_type",
        "path",
        "mail_id",
        "dedupe_key",
        "record_hash",
        "message_type",
        "expected_target_repo",
        "legacy_delivery_log_present",
        "legacy_allowlist",
        "identity",
        "semantic_identity",
        "path_classes",
        "revision_ids",
        "path_count",
        "status",
        "age_seconds",
        "line",
        "bytes",
        "max_bytes",
        "delivery_status",
        "review_status",
        "source_policy_keys",
    }
    sample = {
        key: _mail_repair_plan_safe_value(issue[key])
        for key in sorted(allowed_keys)
        if key in issue
    }
    if isinstance(issue.get("paths"), list):
        sample["paths"] = _mail_repair_plan_safe_value(issue["paths"][:5])
    if isinstance(issue.get("rows"), list):
        rows = []
        for row in issue["rows"][:5]:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    key: _mail_repair_plan_safe_value(row[key])
                    for key in ("path", "mail_id", "dedupe_key", "record_hash")
                    if key in row
                }
            )
        if rows:
            sample["rows"] = rows
    return sample


def _mail_repair_review_queue(issues: list[dict[str, Any]], *, limit: int = 200) -> dict[str, Any]:
    rows = []
    for issue in issues[:limit]:
        if not isinstance(issue, dict):
            continue
        item = _mail_repair_issue_sample(issue)
        item["raw_payload_copied"] = False
        item["review_required"] = _mail_repair_issue_severity(str(issue.get("issue_type", ""))) in {
            "critical",
            "high",
        }
        item["authority_boundary"] = (
            "Sanitized operator review evidence only; use the authoritative DAD "
            "mail lifecycle for repair, replay, delivery, or quarantine."
        )
        rows.append(item)
    return {
        "schema_version": "dad_mail_storm_repair_review_queue.v1",
        "item_count": len(issues),
        "items_emitted": len(rows),
        "truncated": len(issues) > limit,
        "raw_payload_copied": False,
        "items": rows,
    }


def _mail_repair_lane_priority(issue_type: str) -> int:
    if issue_type == "mailbox_coverage_gap":
        return 0
    if issue_type == "delivery_policy_hold":
        return 5
    if issue_type in {
        "central_inbox_uncollected_row",
        "central_inbox_missing_collection_audit",
        "central_inbox_missing_collection_provenance",
    }:
        return 10
    if issue_type == "repo_inbox_without_delivery_log":
        return 20
    if issue_type in {
        "central_outbox_missing_route_audit",
        "central_outbox_unrouted_row",
        "central_outbox_route_hash_mismatch",
        "central_outbox_missing_source_inbox",
    }:
        return 30
    if issue_type in {
        "malformed_jsonl",
        "oversized_jsonl_record",
        "duplicate_jsonl_identity",
        "cross_file_same_stage_duplicate_identity",
        "central_inbox_duplicate_logical_identity",
        "repo_inbox_delivery_hash_mismatch",
        "cross_source_outbox_duplicate_identity",
        "unknown_source_outbox_duplicate_identity",
        "source_outbox_unstable",
        "invalid_mail_packet",
    }:
        return 40
    if issue_type.startswith("rust_rollout_"):
        return 70
    if issue_type in {"jsonl_lock", "atomic_temp_fragment"}:
        return 80
    return 90


def _mail_repair_lane(issue_type: str, issues: list[dict[str, Any]]) -> dict[str, Any]:
    severity = _mail_repair_issue_severity(issue_type)
    lane = {
        "lane_id": issue_type.replace("_", "-"),
        "issue_type": issue_type,
        "issue_count": len(issues),
        "severity": severity,
        "automated_default": "blocked",
        "allowed_now": "read_only_review",
        "requires_human_review": severity in {"critical", "high"},
        "samples": [_mail_repair_issue_sample(issue) for issue in issues[:5]],
        "forbidden_actions": [
            "do_not_collect_route_or_deliver_while_lane_is_open",
            "do_not_edit_target_repo_inbox_as_cleanup",
            "do_not_treat_this_plan_as_delivery_or_release_approval",
        ],
    }
    if issue_type == "repo_inbox_without_delivery_log":
        lane.update(
            {
                "lane_id": "repo-inbox-delivery-audit-repair",
                "title": "Repo inbox rows without DAD delivery-log evidence",
                "allowed_now": "review_only_then_replay_through_dad_delivery",
                "repair_strategy": (
                    "Verify whether each inbox row was delivered by DAD. If not, treat it "
                    "as a wrong-box candidate: move the source decision back through the "
                    "source repo outbox, DAD collect, route, and deliver after review. "
                    "For pre-enforcement rows that have only legacy unhashed delivery-log "
                    "evidence, use --allowlist-legacy-repo-inbox with a reviewer note; "
                    "the allowlist is keyed by mail_id, dedupe_key, current row hash, and "
                    "target repo."
                ),
                "danger_if_rushed": (
                    "A direct inbox write can look like delivered mail and make agents act "
                    "on unreviewed or spoofed recommendations."
                ),
            }
        )
    elif issue_type in {
        "central_inbox_uncollected_row",
        "central_inbox_missing_collection_audit",
        "central_inbox_missing_collection_provenance",
    }:
        lane.update(
            {
                "lane_id": "central-inbox-collection-audit-repair",
                "title": "Central inbox rows without collection authority",
                "allowed_now": "review_only_then_recollect_or_quarantine",
                "repair_strategy": (
                    "Re-collect from the source repo outbox when available, or quarantine "
                    "the central row by metadata/hash after human review. Do not trust packet "
                    "contents alone as collection evidence."
                ),
            }
        )
    elif issue_type in {
        "central_outbox_missing_route_audit",
        "central_outbox_unrouted_row",
        "central_outbox_route_hash_mismatch",
        "central_outbox_missing_source_inbox",
    }:
        lane.update(
            {
                "lane_id": "central-outbox-route-audit-repair",
                "title": "Central outbox rows without route authority",
                "allowed_now": "review_only_then_reroute_from_collected_inbox",
                "repair_strategy": (
                    "Reroute only from current collected central inbox rows with matching "
                    "collection evidence, or quarantine stale/mutated routed rows."
                ),
            }
        )
    elif issue_type in {
        "malformed_jsonl",
        "oversized_jsonl_record",
        "duplicate_jsonl_identity",
        "cross_file_same_stage_duplicate_identity",
        "central_inbox_duplicate_logical_identity",
        "repo_inbox_delivery_hash_mismatch",
        "cross_source_outbox_duplicate_identity",
        "unknown_source_outbox_duplicate_identity",
        "source_outbox_unstable",
        "invalid_mail_packet",
    }:
        lane.update(
            {
                "lane_id": "mailbox-integrity-and-provenance-repair",
                "title": "Mailbox integrity or provenance blocker",
                "allowed_now": "review_only_then_metadata_quarantine_or_source_retry",
                "repair_strategy": (
                    "Quarantine malformed/oversized rows by metadata, retry unstable "
                    "source outboxes after writers finish, and resolve provenance conflicts "
                    "before collection."
                ),
            }
        )
    elif issue_type.startswith("rust_rollout_"):
        lane.update(
            {
                "lane_id": "rust-rollout-packet-resync",
                "title": "Rust rollout staged/tracked packet drift",
                "allowed_now": "review_only_then_staged_regeneration",
                "repair_strategy": (
                    "Resolve higher-priority live mailbox blockers first. Then regenerate "
                    "Rust rollout packets into ignored staging; promote tracked reference "
                    "snapshots only with a reviewed promotion acknowledgement."
                ),
                "review_required_before_running_examples": True,
                "post_review_execution_examples": [
                    (
                        "python -m digital_asset_directory.cli rust-rollout build-mail "
                        "--out-dir processed/mail/staged/rust_rollout "
                        '--dirty-state-ack "reviewed Rust rollout packet resync" '
                        "--dirty-state-fingerprint <fingerprint-from-storm-gate-or-doctor>"
                    ),
                    (
                        "python -m digital_asset_directory.cli rust-rollout build-mail "
                        "--out-dir mail/outbox/rust_rollout "
                        '--dirty-state-ack "reviewed Rust rollout packet resync" '
                        "--dirty-state-fingerprint <fingerprint-from-storm-gate-or-doctor> "
                        '--promote-reference-snapshot-ack "reviewed tracked snapshot promotion"'
                    ),
                ],
                "example_command_authority": (
                    "Examples are not approval. Run only after the lane is selected by "
                    "a human/operator review and higher-priority live mailbox blockers "
                    "are cleared or explicitly accounted for."
                ),
                "danger_if_rushed": (
                    "Rust rollout reference packets are not delivered mail. Promoting them "
                    "while inbox or route authority is dirty can make stale rollout advice "
                    "look current."
                ),
            }
        )
    elif issue_type in {"jsonl_lock", "atomic_temp_fragment"}:
        lane.update(
            {
                "lane_id": "stale-lock-and-temp-fragment-repair",
                "title": "Mailbox lock or atomic temp debris",
                "allowed_now": "repair_only_when_stale_or_dead",
                "repair_strategy": (
                    "Use mail doctor repair flags only for stale/dead locks or stale temp "
                    "fragments. Active locks mean another writer may still be appending."
                ),
            }
        )
    else:
        lane.update(
            {
                "title": "Generic mail doctor issue",
                "repair_strategy": (
                    "Review the authoritative mail doctor issue and repair through the "
                    "documented DAD lifecycle before moving mail."
                ),
            }
        )
    return lane


def _mail_storm_repair_plan_report(
    result: dict[str, Any],
    *,
    gate: dict[str, Any],
    repo_args: list[str],
    requested_operation: str = "all",
) -> dict[str, Any]:
    operation = _mail_storm_operation_key(requested_operation)
    issues = [issue for issue in result.get("issues", []) if isinstance(issue, dict)]
    issue_groups: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        issue_type = str(issue.get("issue_type", "") or "unknown_issue")
        issue_groups.setdefault(issue_type, []).append(issue)
    issue_counts = {issue_type: len(group) for issue_type, group in sorted(issue_groups.items())}
    lanes: list[dict[str, Any]] = []
    mailbox_coverage = result.get("mailbox_coverage", {})
    if not isinstance(mailbox_coverage, dict):
        mailbox_coverage = {}
    delivery_policy = result.get("delivery_policy", {})
    if not isinstance(delivery_policy, dict):
        delivery_policy = {}
    coverage_gap_count = int(mailbox_coverage.get("unreviewed_mailbox_candidate_count", 0) or 0)
    coverage_gap_count += int(mailbox_coverage.get("reviewed_enabled_not_checked_count", 0) or 0)
    if coverage_gap_count or str(mailbox_coverage.get("warning", "")).strip():
        lanes.append(
            {
                "lane_id": "mailbox-coverage-review",
                "issue_type": "mailbox_coverage_gap",
                "issue_count": coverage_gap_count,
                "severity": "critical",
                "title": "Mailbox coverage is not reviewed complete",
                "automated_default": "blocked",
                "allowed_now": "read_only_discovery_and_policy_review",
                "requires_human_review": True,
                "samples": {
                    "unreviewed_mailbox_candidate_samples": mailbox_coverage.get(
                        "unreviewed_mailbox_candidate_samples", []
                    ),
                    "reviewed_enabled_not_checked_samples": mailbox_coverage.get(
                        "reviewed_enabled_not_checked_samples", []
                    ),
                },
                "repair_strategy": (
                    "Classify discovered mailbox candidates into reviewed mail.repos policy "
                    "or explicitly ignore/archive them before treating --repo all as complete."
                ),
                "forbidden_actions": [
                    "do_not_collect_from_unreviewed_mailboxes",
                    "do_not_deliver_to_unchecked_reviewed_repos",
                ],
            }
        )
    delivery_policy_blocked = int(delivery_policy.get("blocked_delivery_repo_count", 0) or 0)
    if delivery_policy_blocked:
        lanes.append(
            {
                "lane_id": "delivery-policy-hold-review",
                "issue_type": "delivery_policy_hold",
                "issue_count": delivery_policy_blocked,
                "severity": "critical",
                "title": "Reviewed repo policy blocks delivery",
                "automated_default": "blocked",
                "allowed_now": "narrow_scope_or_human_policy_review",
                "requires_human_review": True,
                "samples": delivery_policy.get("blocked_delivery_repos", [])[:10],
                "repair_strategy": (
                    "Do not deliver to write-protected or delivery-disallowed repos. "
                    "Narrow the command scope or change reviewed mail policy only after "
                    "repo-specific human review."
                ),
                "forbidden_actions": [
                    "do_not_deliver_to_write_protected_repos",
                    "do_not_use_clean_mail_spool_as_delivery_approval",
                ],
            }
        )
    for issue_type, group in issue_groups.items():
        lanes.append(_mail_repair_lane(issue_type, group))
    lanes.sort(
        key=lambda lane: (
            _mail_repair_lane_priority(str(lane.get("issue_type", ""))),
            str(lane.get("lane_id", "")),
        )
    )
    status = "repair_plan_required" if lanes else "no_repair_needed"
    if not lanes and not gate.get("safe_for_mail_storm_operations"):
        status = "scope_review_required"
    review_queue = _mail_repair_review_queue(issues)
    return {
        "schema_version": "dad_mail_storm_repair_plan.v1",
        "generated_at": result.get("generated_at", utc_now()),
        "status": status,
        "requested_repos": repo_args,
        "gate_status": gate.get("gate_status"),
        "dirty_state_fingerprint": gate.get("dirty_state_fingerprint", ""),
        "doctor_status": result.get("status"),
        "writes_performed": False,
        "repair_execution_performed": False,
        "repair_automation_allowed": False,
        "requested_operation": operation,
        "operator_review_required": bool(lanes or gate.get("requires_human_review")),
        "safe_for_selected_scope": bool(gate.get("safe_for_selected_scope")),
        "safe_for_mail_storm_operations": bool(gate.get("safe_for_mail_storm_operations")),
        "safe_for_ingest_operations": bool(gate.get("safe_for_ingest_operations")),
        "safe_for_delivery_operations": bool(gate.get("safe_for_delivery_operations")),
        "selected_operation_safe": _mail_storm_operation_safe(gate, operation),
        "safe_to_collect": bool(gate.get("safe_to_collect")),
        "safe_to_route": bool(gate.get("safe_to_route")),
        "safe_to_deliver": bool(gate.get("safe_to_deliver")),
        "blocked_operation_classes": gate.get("blocked_operation_classes", []),
        "blocking_reasons": gate.get("blocking_reasons", []),
        "operation_safety_contract": gate.get("operation_safety_contract", ""),
        "issue_counts_by_type": issue_counts,
        "mail_summary": gate.get("mail_summary", {}),
        "repo_scope": gate.get("repo_scope", {}),
        "mailbox_coverage": mailbox_coverage,
        "delivery_policy": delivery_policy,
        "worktree_state": gate.get("worktree_state", {}),
        "repair_lanes": lanes,
        "review_queue": review_queue,
        "recommended_order": [str(lane.get("lane_id", "")) for lane in lanes],
        "operator_commands": {
            **dict(gate.get("operator_commands", {})),
            "repair_plan": "python -m digital_asset_directory.cli mail repair-plan --repo all",
            "diagnostic_doctor_summary_only_not_an_exit_gate": (
                "python -m digital_asset_directory.cli mail doctor --repo all --summary-only"
            ),
            "fail_closed_doctor": (
                "python -m digital_asset_directory.cli mail doctor --repo all "
                "--summary-only --fail-on-dirty --fail-on-coverage-gap"
            ),
        },
        "next_actions": gate.get("next_actions", []),
        "safety_rules": [
            "This report is read-only and cannot approve repair, delivery, public release, or repo writes.",
            "Repo inbox rows are trusted only when backed by matching DAD delivery-log evidence.",
            "Rust rollout packets are reference/staging instructions, not delivered inbox mail.",
            (
                "Use the operation-specific storm gate before moving mail: ingest for "
                "collect/route, delivery or all before target repo inbox writes."
            ),
        ],
        "authority_boundary": (
            "The repair plan classifies dirty-state blockers and proposes review lanes. It does "
            "not collect, route, deliver, quarantine, allowlist, repair, promote Rust snapshots, "
            "approve public release, or authorize writes to target repos."
        ),
    }


def _mail_repair_report_slug(plan: dict[str, Any]) -> str:
    generated_at = str(plan.get("generated_at", utc_now()))
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", generated_at).strip("-").lower()
    return slug[:80] or "latest"


def _mail_repair_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# DAD Mail Storm Repair Packet",
        "",
        f"Generated: `{plan.get('generated_at', '')}`",
        f"Status: `{plan.get('status', '')}`",
        f"Gate: `{plan.get('gate_status', '')}`",
        f"Doctor status: `{plan.get('doctor_status', '')}`",
        "",
        "## Authority Boundary",
        "",
        str(plan.get("authority_boundary", "")),
        "",
        "This packet is operator evidence only. It does not collect, route, deliver, "
        "quarantine, repair, promote Rust snapshots, approve public release, or authorize "
        "writes to target repositories.",
        "",
        "## Safety Summary",
        "",
        f"- Requested operation: `{plan.get('requested_operation', 'all')}`",
        f"- Selected operation safe: `{bool(plan.get('selected_operation_safe'))}`",
        f"- Safe for selected scope: `{bool(plan.get('safe_for_selected_scope'))}`",
        f"- Safe for mail-storm operations: `{bool(plan.get('safe_for_mail_storm_operations'))}`",
        f"- Safe for ingest operations: `{bool(plan.get('safe_for_ingest_operations'))}`",
        f"- Safe for delivery operations: `{bool(plan.get('safe_for_delivery_operations'))}`",
        f"- Safe to collect: `{bool(plan.get('safe_to_collect'))}`",
        f"- Safe to route: `{bool(plan.get('safe_to_route'))}`",
        f"- Safe to deliver: `{bool(plan.get('safe_to_deliver'))}`",
        f"- Blocked operation classes: `{', '.join(plan.get('blocked_operation_classes', []))}`",
        f"- Blocking reasons: `{', '.join(plan.get('blocking_reasons', []))}`",
        f"- Operator review required: `{bool(plan.get('operator_review_required'))}`",
        "",
        "## Recommended Order",
        "",
    ]
    recommended = plan.get("recommended_order", [])
    if isinstance(recommended, list) and recommended:
        lines.extend(f"- `{item}`" for item in recommended)
    else:
        lines.append("- No repair lanes were generated.")
    lines.extend(["", "## Repair Lanes", ""])
    lanes = plan.get("repair_lanes", [])
    if isinstance(lanes, list) and lanes:
        for lane in lanes:
            if not isinstance(lane, dict):
                continue
            lines.extend(
                [
                    f"### {lane.get('title', lane.get('lane_id', 'Untitled lane'))}",
                    "",
                    f"- Lane ID: `{lane.get('lane_id', '')}`",
                    f"- Issue type: `{lane.get('issue_type', '')}`",
                    f"- Severity: `{lane.get('severity', '')}`",
                    f"- Count: `{lane.get('issue_count', 0)}`",
                    f"- Allowed now: `{lane.get('allowed_now', '')}`",
                    f"- Requires human review: `{bool(lane.get('requires_human_review'))}`",
                    "",
                    str(lane.get("repair_strategy", "")),
                    "",
                ]
            )
    else:
        lines.append("No repair lanes were generated.")
        lines.append("")
    commands = plan.get("operator_commands", {})
    if isinstance(commands, dict):
        lines.extend(["## Operator Commands", ""])
        for key, value in sorted(commands.items()):
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    lines.extend(["## Safety Rules", ""])
    for rule in plan.get("safety_rules", []):
        lines.append(f"- {rule}")
    lines.append("")
    return "\n".join(lines)


def _write_mail_repair_plan_packet(repo_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    output_dir = data_relative_path(repo_root, Path("processed") / "reports" / "mail_storm_repair")
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _mail_repair_report_slug(plan)
    json_path = output_dir / f"{slug}.json"
    md_path = output_dir / f"{slug}.md"
    latest_json_path = output_dir / "latest.json"
    latest_md_path = output_dir / "latest.md"
    packet = {
        **plan,
        "report_packet": {
            "schema_version": "dad_mail_storm_repair_packet.v1",
            "created_at": utc_now(),
            "report_writes_performed": True,
            "report_write_scope": "DAD-local processed/reports/mail_storm_repair only",
            "authority_boundary": (
                "This report packet is durable operator evidence only. It does not "
                "repair mail, collect, route, deliver, approve public release, or "
                "authorize target repo writes."
            ),
        },
    }
    json_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = _mail_repair_plan_markdown(packet)
    md_path.write_text(markdown, encoding="utf-8")
    latest_json_path.write_text(
        json.dumps(
            {
                **packet,
                "latest_pointer": {
                    "schema_version": "dad_mail_storm_repair_latest_pointer.v1",
                    "source_report": safe_relative(json_path, repo_root),
                    "source_markdown": safe_relative(md_path, repo_root),
                    "updated_at": utc_now(),
                    "authority_boundary": (
                        "This stable pointer only mirrors the latest DAD-local "
                        "operator repair plan. It does not approve repair, mail "
                        "delivery, public release, or target-repo writes."
                    ),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    latest_md_path.write_text(markdown, encoding="utf-8")
    return {
        "schema_version": "dad_mail_storm_repair_packet_write.v1",
        "json": safe_relative(json_path, repo_root),
        "markdown": safe_relative(md_path, repo_root),
        "latest_json": safe_relative(latest_json_path, repo_root),
        "latest_markdown": safe_relative(latest_md_path, repo_root),
        "report_writes_performed": True,
        "repair_execution_performed": False,
        "authority_boundary": (
            "Only DAD-local report files were written; no mail lifecycle or target repo "
            "state was changed."
        ),
    }


def _json_command(value: Optional[str], option_name: str) -> list[str] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{option_name} must be a JSON array of arguments.") from exc
    if not isinstance(parsed, list) or not parsed:
        raise typer.BadParameter(f"{option_name} must be a non-empty JSON array of arguments.")
    if not all(isinstance(item, str | int | float | bool) for item in parsed):
        raise typer.BadParameter(f"{option_name} arguments must be strings, numbers, or booleans.")
    return [str(item) for item in parsed]


RAW_JSON_PAYLOAD_MESSAGE = (
    "--payload is key=value convenience mode only; use --payload-json or "
    "--payload-file for structured JSON payloads."
)


def _payload_key_looks_like_raw_json(key: str) -> bool:
    return "{" in key or "}" in key or "\n" in key or "\r" in key or len(key) > 128


def _parse_payload_json(value: str, *, option_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{option_name} must be a JSON object.") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter(f"{option_name} must be a JSON object.")
    return parsed


def _payload_file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise typer.BadParameter(f"--payload-file could not be read: {exc}") from exc


def _payload_json_text(value: str) -> str:
    source = value.strip()
    if not source:
        raise typer.BadParameter("--payload-json requires a JSON object, file path, or '-' for stdin.")
    if source == "-":
        return sys.stdin.read()
    if source.startswith(("{", "[")):
        return source
    candidate = Path(source)
    try:
        if candidate.exists():
            return _payload_file_text(candidate)
    except OSError:
        pass
    return source


def _key_value_payload(values: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for value in values:
        stripped = value.lstrip()
        bracketed_key = bool(re.match(r"^\[[^\]]+\]\s*=", stripped))
        if stripped.startswith("{") or (stripped.startswith("[") and not bracketed_key):
            raise typer.BadParameter(
                "--payload is key=value convenience mode only; use --payload-json "
                "or --payload-file for structured JSON payloads."
            )
        if "=" not in value:
            raise typer.BadParameter(
                "Mail payload values must use key=value form, or use --payload-json/"
                "--payload-file for structured JSON payloads."
            )
        key, item = value.split("=", 1)
        key = key.strip()
        if _payload_key_looks_like_raw_json(key):
            raise typer.BadParameter(RAW_JSON_PAYLOAD_MESSAGE)
        if not key:
            raise typer.BadParameter("Mail payload keys cannot be empty.")
        payload[key] = item.strip()
    return payload


def _mail_payload_options(
    payload: list[str],
    *,
    payload_json: str | None = None,
    payload_file: Path | None = None,
) -> dict[str, Any]:
    source_count = int(bool(payload)) + int(bool(payload_json)) + int(payload_file is not None)
    if source_count > 1:
        raise typer.BadParameter(
            "Use only one payload source: --payload key=value, --payload-json, or --payload-file."
        )
    if payload_file is not None:
        return _parse_payload_json(_payload_file_text(payload_file), option_name="--payload-file")
    if payload_json is not None:
        return _parse_payload_json(_payload_json_text(payload_json), option_name="--payload-json")
    return _key_value_payload(payload)


def _event_payload_options(
    payload: list[str],
    *,
    payload_json: str | None = None,
    payload_file: Path | None = None,
) -> dict[str, Any]:
    try:
        return _mail_payload_options(
            payload,
            payload_json=payload_json,
            payload_file=payload_file,
        )
    except typer.BadParameter as exc:
        detail = str(exc).replace("Mail payload", "Event payload")
        raise typer.BadParameter(detail) from exc


def _mail_repo_aliases(policy) -> set[str]:
    aliases: set[str] = set()
    for attr in ("id", "alias"):
        value = str(getattr(policy, attr, "") or "").strip()
        if value:
            aliases.add(value)
    path = getattr(policy, "path", None)
    if path is not None:
        aliases.add(Path(path).name)
        aliases.add(str(Path(path).resolve()))
    return aliases


def _exception_repo_policies(cfg) -> list[object]:
    return list(getattr(cfg, "exception_repos", []) or [])


def _looks_like_repo_path(value: str) -> bool:
    if value in {".", ".."}:
        return True
    return any(part in value for part in ("/", "\\")) or Path(value).is_absolute()


def _resolve_mail_repo(raw_repo: str, cfg) -> Path:
    value = raw_repo.strip()
    if not value:
        raise typer.BadParameter("Repo values cannot be empty.")
    if _looks_like_repo_path(value):
        return Path(value).resolve()
    matches = [
        policy
        for policy in cfg.mail_repos
        if getattr(policy, "mail_enabled", True) and value in _mail_repo_aliases(policy)
    ]
    if len(matches) == 1:
        return Path(matches[0].path).resolve()
    if len(matches) > 1:
        matched = ", ".join(sorted(str(Path(policy.path).resolve()) for policy in matches))
        raise typer.BadParameter(
            f"Repo value {value!r} is ambiguous in reviewed mail.repos policy: {matched}"
        )
    return Path(value).resolve()


def _discover_mail_repos(
    raw_repos: list[str],
    cfg,
    *,
    delivery: bool = False,
    reviewed: bool = False,
) -> list[Path]:
    if not raw_repos:
        raise typer.BadParameter("Provide at least one --repo value, or --repo all.")
    if raw_repos != ["all"]:
        repos = [_resolve_mail_repo(repo, cfg) for repo in raw_repos]
        if delivery or reviewed:
            protected: list[str] = []
            unreviewed: list[str] = []
            for repo in repos:
                matched_policy = None
                for policy in cfg.mail_repos:
                    if repo == policy.path.resolve():
                        matched_policy = policy
                        if not policy.mail_enabled:
                            protected.append(policy.id)
                        elif delivery and (
                            not policy.delivery_allowed or getattr(policy, "write_protected", False)
                        ):
                            protected.append(policy.id)
                        break
                if matched_policy is None:
                    unreviewed.append(str(repo))
            if unreviewed:
                raise typer.BadParameter(
                    "This operation can target only reviewed mail.repos entries: "
                    + ", ".join(unreviewed)
                )
            if protected:
                raise typer.BadParameter(
                    "This operation is blocked by reviewed policy for: " + ", ".join(protected)
                )
        return repos

    repos: dict[str, Path] = {}
    if delivery:
        blocked_delivery = [
            policy.id
            for policy in cfg.mail_repos
            if policy.mail_enabled
            and (not policy.delivery_allowed or getattr(policy, "write_protected", False))
        ]
        if blocked_delivery:
            raise typer.BadParameter(
                "--repo all delivery is blocked by reviewed mail.repos policy for: "
                + ", ".join(sorted(blocked_delivery))
                + ". Narrow --repo to explicitly reviewed deliverable repos, or run "
                "mail storm-gate --operation delivery for the full hold report."
            )
    for policy in cfg.mail_repos:
        if not policy.mail_enabled:
            continue
        if delivery and (not policy.delivery_allowed or getattr(policy, "write_protected", False)):
            continue
        repos[str(policy.path.resolve())] = policy.path.resolve()
    if not repos:
        raise typer.BadParameter(
            "--repo all uses reviewed mail.repos config only; provide explicit --repo "
            "or add enabled mail.repos entries."
        )
    return list(repos.values())


def _mail_dirty_gate_payload(
    *,
    operation: str,
    result: dict,
    dirty_state_ack: str | None = None,
) -> dict:
    payload = {
        "schema_version": "dad_mail_dirty_gate.v1",
        "operation": operation,
        "dirty": bool(result.get("dirty")),
        "status": result.get("status"),
        "action_summary": result.get("action_summary", {}),
        "summary": result.get("summary", {}),
        "worktree_state": result.get("worktree_state", {}),
        "write_target_guidance": result.get("write_target_guidance", {}),
        "authority_boundary": result.get("authority_boundary", ""),
    }
    if dirty_state_ack:
        payload["dirty_state_ack"] = dirty_state_ack
    payload["dirty_state_fingerprint"] = _mail_dirty_state_fingerprint(result)
    return payload


_MAIL_DIRTY_FINGERPRINT_FIELDS = (
    "issue_type",
    "path",
    "stage",
    "mail_id",
    "dedupe_key",
    "record_hash",
    "identity",
    "line",
    "filename",
    "root_class",
    "packet_path",
    "expected_target_repo",
)


def _mail_dirty_state_fingerprint(result: dict[str, Any]) -> str:
    """Return a stable fingerprint for the currently observed mail-storm blockers.

    The fingerprint intentionally ignores volatile timestamps and lock ages, but it
    includes issue identity, paths, hashes, and summary counts so a reviewed bypass
    cannot silently apply after a different repo appends new mail.
    """

    issues: list[dict[str, Any]] = []
    for issue in result.get("issues", []):
        if not isinstance(issue, dict):
            continue
        issues.append(
            {
                key: str(issue.get(key, ""))
                for key in _MAIL_DIRTY_FINGERPRINT_FIELDS
                if str(issue.get(key, "")) != ""
            }
        )
    issues.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    summary = result.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    basis = {
        "schema_version": "dad_mail_dirty_state_fingerprint.v1",
        "dirty": bool(result.get("dirty")),
        "spool_dirty": bool(result.get("spool_dirty", result.get("dirty"))),
        "status": str(result.get("status", "")),
        "issue_count": len(issues),
        "summary_counts": {
            key: int(value)
            for key, value in sorted(summary.items())
            if key.endswith("_count") and type(value) is int
        },
        "issues": issues,
    }
    encoded = json.dumps(basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256_bytes(encoded)}"


def _ensure_mail_clean_for_operation(
    cfg,
    repos: list[Path],
    *,
    operation: str,
    dirty_state_ack: str | None = None,
    dirty_state_fingerprint: str | None = None,
    allow_dirty_ack: bool = False,
    dirty_ack_issue_types: set[str] | None = None,
) -> dict:
    result = diagnose_mail_dirty_state(cfg.repo_root, repos, repo_policies=cfg.mail_repos)
    if not result.get("dirty"):
        return _mail_dirty_gate_payload(operation=operation, result=result)
    payload = _mail_dirty_gate_payload(
        operation=operation,
        result=result,
        dirty_state_ack=dirty_state_ack,
    )
    if allow_dirty_ack and dirty_state_ack and dirty_state_ack.strip():
        allowed_issue_types = dirty_ack_issue_types or set()
        issue_types = {
            str(issue.get("issue_type", ""))
            for issue in result.get("issues", [])
            if isinstance(issue, dict)
        }
        disallowed_issue_types = sorted(issue_types - allowed_issue_types)
        if disallowed_issue_types:
            payload["blocked"] = True
            payload["dirty_ack_rejected"] = True
            payload["disallowed_issue_types"] = disallowed_issue_types
            payload["allowed_dirty_ack_issue_types"] = sorted(allowed_issue_types)
            console.print_json(data=payload)
            raise typer.Exit(2)
        expected_fingerprint = str(payload.get("dirty_state_fingerprint", ""))
        provided_fingerprint = (dirty_state_fingerprint or "").strip()
        if not provided_fingerprint or provided_fingerprint != expected_fingerprint:
            payload["blocked"] = True
            payload["dirty_ack_rejected"] = True
            payload["dirty_state_fingerprint_required"] = True
            payload["provided_dirty_state_fingerprint"] = provided_fingerprint
            payload["expected_dirty_state_fingerprint"] = expected_fingerprint
            payload["allowed_dirty_ack_issue_types"] = sorted(allowed_issue_types)
            payload["recommendation"] = (
                "Run mail storm-gate or mail doctor, review the current dirty-state "
                "fingerprint, then retry with --dirty-state-fingerprint only if the "
                "same allowed Rust packet dirt is still present."
            )
            console.print_json(data=payload)
            raise typer.Exit(2)
        payload["bypassed"] = True
        payload["allowed_dirty_ack_issue_types"] = sorted(allowed_issue_types)
        append_jsonl_locked(
            cfg.repo_root / "processed" / "mail" / "archive" / "dirty_gate_bypass.jsonl",
            {"event_type": "mail_dirty_gate_bypass", "created_at": utc_now(), **payload},
        )
        return payload
    payload["blocked"] = True
    console.print_json(data=payload)
    raise typer.Exit(2)


def _mailbox_coverage_gate_payload(*, operation: str, coverage: dict) -> dict:
    return {
        "schema_version": "dad_mailbox_coverage_gate.v1",
        "operation": operation,
        "blocked": True,
        "mailbox_coverage": coverage,
        "authority_boundary": (
            "Mailbox coverage is read-only discovery evidence. It does not authorize "
            "collection, delivery, enrollment, or repo writes. Add reviewed mail.repos "
            "policy before using --repo all for newly discovered mailboxes."
        ),
    }


def _mailbox_coverage_for_repo_all(
    repo_args: list[str],
    cfg,
    selected: list[Path],
    *,
    include_local_paths: bool = False,
) -> dict | None:
    return (
        _mailbox_coverage_summary(
            cfg,
            selected,
            include_local_paths=include_local_paths,
        )
        if repo_args == ["all"]
        else None
    )


def _record_mailbox_coverage_gap_ack(
    cfg,
    *,
    operation: str,
    coverage: dict,
    ack: str,
) -> None:
    append_jsonl_locked(
        cfg.repo_root / "processed" / "mail" / "archive" / "coverage_gap_ack.jsonl",
        {
            "event_type": "mailbox_coverage_gap_ack",
            "created_at": utc_now(),
            "operation": operation,
            "ack": ack,
            "mailbox_coverage": coverage,
            "authority_boundary": (
                "Coverage-gap acknowledgement permits this operator run to continue "
                "with reviewed mail.repos only. It does not enroll, collect from, or "
                "deliver to unreviewed mailbox candidates."
            ),
        },
    )


def _block_on_mailbox_coverage_gap(
    cfg,
    coverage: dict | None,
    *,
    operation: str,
    allow_coverage_gap_ack: str | None = None,
) -> None:
    if coverage is None:
        return
    coverage_blocked = bool(
        int(coverage.get("unreviewed_mailbox_candidate_count", 0) or 0)
        or int(coverage.get("reviewed_enabled_not_checked_count", 0) or 0)
        or str(coverage.get("warning", "")).strip()
    )
    if coverage_blocked:
        ack = (allow_coverage_gap_ack or "").strip()
        if ack:
            _record_mailbox_coverage_gap_ack(
                cfg,
                operation=operation,
                coverage=coverage,
                ack=ack,
            )
            return
        console.print_json(
            data=_mailbox_coverage_gate_payload(operation=operation, coverage=coverage)
        )
        raise typer.Exit(1)


def _resolve_exception_repo(raw_repo: str, cfg) -> Path:
    value = raw_repo.strip()
    if not value:
        raise typer.BadParameter("Repo values cannot be empty.")
    if _looks_like_repo_path(value):
        return Path(value).resolve()
    matches = [
        policy
        for policy in _exception_repo_policies(cfg)
        if getattr(policy, "exceptions_enabled", True) and value in _mail_repo_aliases(policy)
    ]
    if len(matches) == 1:
        return Path(getattr(matches[0], "path")).resolve()
    if len(matches) > 1:
        matched = ", ".join(sorted(str(Path(policy.path).resolve()) for policy in matches))
        raise typer.BadParameter(
            f"Repo value {value!r} is ambiguous in reviewed exceptions.repos policy: " + matched
        )
    return Path(value).resolve()


def _discover_exception_repos(
    raw_repos: list[str],
    cfg,
    *,
    collect: bool = False,
    capture_audit: bool = False,
    reviewed: bool = False,
) -> list[Path]:
    if not raw_repos:
        raise typer.BadParameter("Provide at least one --repo value, or --repo all.")
    policies = _exception_repo_policies(cfg)
    if raw_repos != ["all"]:
        repos = [_resolve_exception_repo(repo, cfg) for repo in raw_repos]
        if collect or capture_audit or reviewed:
            blocked: list[str] = []
            unreviewed: list[str] = []
            for repo in repos:
                matched_policy = None
                for policy in policies:
                    if repo == Path(getattr(policy, "path")).resolve():
                        matched_policy = policy
                        if not getattr(policy, "exceptions_enabled", True):
                            blocked.append(str(getattr(policy, "id", repo)))
                        elif collect and (
                            not getattr(policy, "collect_allowed", True)
                            or getattr(policy, "write_protected", False)
                        ):
                            blocked.append(str(getattr(policy, "id", repo)))
                        elif capture_audit and not getattr(
                            policy,
                            "capture_audit_allowed",
                            True,
                        ):
                            blocked.append(str(getattr(policy, "id", repo)))
                        break
                if matched_policy is None:
                    unreviewed.append(str(repo))
            if unreviewed:
                raise typer.BadParameter(
                    "This operation can target only reviewed exceptions.repos entries: "
                    + ", ".join(unreviewed)
                )
            if blocked:
                raise typer.BadParameter(
                    "This operation is blocked by reviewed exceptions policy for: "
                    + ", ".join(blocked)
                )
        return repos

    repos: dict[str, Path] = {}
    for policy in policies:
        if not getattr(policy, "exceptions_enabled", True):
            continue
        if collect and (
            not getattr(policy, "collect_allowed", True)
            or getattr(policy, "write_protected", False)
        ):
            continue
        if capture_audit and not getattr(policy, "capture_audit_allowed", True):
            continue
        path = Path(getattr(policy, "path")).resolve()
        repos[str(path)] = path
    if not repos:
        raise typer.BadParameter(
            "--repo all uses reviewed exceptions.repos config only; add enabled "
            "exceptions.repos entries before collecting or auditing exception mail."
        )
    return list(repos.values())


def _path_is_relative_to(path: Path, base: Path) -> bool:
    try:
        return path.is_relative_to(base)
    except AttributeError:
        return str(path).startswith(str(base))


def _exception_policy_for_path(cfg, path: Path):
    resolved = path.resolve()
    for policy in _exception_repo_policies(cfg):
        policy_path = Path(getattr(policy, "path")).resolve()
        if resolved == policy_path or _path_is_relative_to(resolved, policy_path):
            return policy
    return None


def _exception_backfill_policy_block_reason(cfg, root: Path) -> str:
    policy = _exception_policy_for_path(cfg, root)
    if policy is None:
        return ""
    policy_id = str(getattr(policy, "id", root))
    if not getattr(policy, "exceptions_enabled", True):
        return f"{policy_id} has exceptions_enabled=false"
    if getattr(policy, "write_protected", False):
        return f"{policy_id} is write_protected for exception backfill"
    if not getattr(policy, "backfill_allowed", False):
        return f"{policy_id} has backfill_allowed=false"
    return ""


def _exception_backfill_approval_block_reason(cfg, root: Path, approval_id: str) -> str:
    approval = approval_id.strip()
    if not approval:
        return "missing reviewed exception backfill approval id"
    policy = _exception_policy_for_path(cfg, root)
    if policy is None:
        return "root is not covered by reviewed exceptions.repos policy"
    approved_ids = [str(value) for value in getattr(policy, "approved_approval_ids", []) or []]
    if approval not in approved_ids:
        policy_id = str(getattr(policy, "id", root))
        return f"{approval!r} is not approved for exceptions repo policy {policy_id}"
    return ""


def _exception_backfill_review_queue_approval_block_reason(cfg, approval_id: str) -> str:
    approval = approval_id.strip()
    if not approval:
        return "missing reviewed exception backfill review-queue approval id"
    matching_policies = [
        str(getattr(policy, "id", "unknown"))
        for policy in _exception_repo_policies(cfg)
        if approval in [str(value) for value in getattr(policy, "approved_approval_ids", []) or []]
    ]
    if not matching_policies:
        return f"{approval!r} is not approved by any reviewed exceptions.repos policy"
    return ""


def _exception_record_policy_block_reason(cfg, repo: Path) -> str:
    policy = _exception_policy_for_path(cfg, repo)
    if policy is None:
        return ""
    policy_id = str(getattr(policy, "id", repo))
    if not getattr(policy, "exceptions_enabled", True):
        return f"{policy_id} has exceptions_enabled=false"
    if getattr(policy, "write_protected", False):
        return f"{policy_id} is write_protected for exception recording"
    return ""


def _capture_audit_gap_count(result: dict[str, object], *, strict: bool = False) -> int:
    return observed_capture_audit_gap_count(result, strict=strict)


MAIL_CANDIDATE_SCAN_MAX_DEPTH = 6
MAIL_CANDIDATE_PRUNE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".nox",
    ".tox",
    ".tmp",
    ".tmp-codex",
    ".tmp_pytest",
    ".cache",
    "_codex_worktrees",
    ".worktrees",
    ".pytest-tmp-root",
    "processed",
    "raw",
    "state",
    "audit",
}


def _iter_mailbox_candidate_roots(base: Path, *, max_depth: int = MAIL_CANDIDATE_SCAN_MAX_DEPTH):
    if not base.exists() or not base.is_dir():
        return
    try:
        root = base.resolve()
    except OSError:
        return
    stack: list[tuple[Path, int]] = [(root, 0)]
    seen: set[Path] = set()
    while stack:
        current, depth = stack.pop()
        try:
            resolved = current.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        mail_dir = current / ".digital-asset" / "mail"
        if (mail_dir / "outbox.jsonl").exists() or (mail_dir / "inbox.jsonl").exists():
            yield current
        if depth >= max_depth:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for child in reversed(children):
            name = child.name
            lowered = name.casefold()
            if (
                name in MAIL_CANDIDATE_PRUNE_DIRS
                or lowered.startswith("pytest-of-")
                or lowered.startswith(".pytest_tmp")
                or lowered.startswith("pytest_tmp")
                or lowered.startswith("pytest-tmp")
                or lowered.startswith("tmp_pytest")
                or lowered.startswith("tmp-pytest")
                or lowered.startswith("dad-capture-emission-")
                or lowered.startswith("dad-exception-learning-check-")
            ):
                continue
            try:
                if child.is_symlink() or not child.is_dir():
                    continue
            except OSError:
                continue
            stack.append((child, depth + 1))


def _mail_repo_candidates(cfg) -> list[dict[str, object]]:
    configured = {str(policy.path.resolve()): policy for policy in cfg.mail_repos}
    discovered: dict[str, Path] = {str(cfg.repo_root.resolve()): cfg.repo_root.resolve()}
    for policy in cfg.mail_repos:
        discovered[str(policy.path.resolve())] = policy.path.resolve()
    for source in cfg.local_sources:
        if not source.enabled:
            continue
        base = source.path.resolve()
        for candidate in _iter_mailbox_candidate_roots(base):
            discovered[str(candidate.resolve())] = candidate.resolve()
    rows: list[dict[str, object]] = []
    for path in sorted(discovered.values(), key=lambda item: str(item).lower()):
        mail_dir = path / ".digital-asset" / "mail"
        policy = configured.get(str(path.resolve()))
        rows.append(
            {
                "path": str(path.resolve()),
                "has_inbox": (mail_dir / "inbox.jsonl").exists(),
                "has_outbox": (mail_dir / "outbox.jsonl").exists(),
                "configured": policy is not None,
                "mail_enabled": bool(policy.mail_enabled) if policy else False,
                "delivery_allowed": bool(policy.delivery_allowed) if policy else False,
                "write_protected": bool(getattr(policy, "write_protected", False))
                if policy
                else False,
                "write_protection_reason": _mail_repair_plan_safe_value(
                    str(getattr(policy, "write_protection_reason", ""))
                )
                if policy
                else "",
                "visibility": policy.visibility if policy else "unreviewed_candidate",
                "public_facing": bool(policy.public_facing) if policy else False,
            }
        )
    return rows


def _safe_coverage_path_ref(path: Path) -> str:
    normalized = str(path.resolve()).replace("\\", "/")
    return f"repo-path-sha256:{sha256_bytes(normalized.encode('utf-8'))}"


def _mailbox_coverage_row_for_output(
    row: dict[str, object],
    *,
    include_local_paths: bool = False,
) -> dict[str, object]:
    output = dict(row)
    raw_path = str(output.pop("path", "") or "")
    output["path_ref"] = (
        raw_path
        if include_local_paths and raw_path
        else (_safe_coverage_path_ref(Path(raw_path)) if raw_path else "")
    )
    if include_local_paths and raw_path:
        output["path"] = raw_path
    return output


def _mailbox_coverage_summary(
    cfg,
    selected: list[Path],
    *,
    include_local_paths: bool = False,
) -> dict[str, object]:
    candidate_rows = _mail_repo_candidates(cfg)
    selected_paths = {str(path.resolve()) for path in selected}
    unreviewed = [
        row
        for row in candidate_rows
        if not row["configured"] and (row["has_inbox"] or row["has_outbox"])
    ]
    reviewed_unchecked = [
        row
        for row in candidate_rows
        if row["configured"]
        and row["mail_enabled"]
        and str(Path(str(row["path"])).resolve()) not in selected_paths
    ]
    warning = ""
    if unreviewed:
        warning = (
            "Read-only discovery found mailbox candidates outside reviewed mail.repos. "
            "DAD will not collect or deliver for them until they are reviewed, but they "
            "may explain a visible Rust/mail learning storm."
        )
    elif reviewed_unchecked:
        warning = (
            "Reviewed enabled mail.repos were not included in the selected mailbox "
            "coverage set. Treat the run as partial until those repos are checked or "
            "explicitly scoped out by operator review."
        )
    return {
        "schema_version": "dad_mailbox_coverage.v1",
        "candidate_count": len(candidate_rows),
        "reviewed_checked_count": len(selected_paths),
        "unreviewed_mailbox_candidate_count": len(unreviewed),
        "reviewed_enabled_not_checked_count": len(reviewed_unchecked),
        "unreviewed_mailbox_candidate_samples": [
            _mailbox_coverage_row_for_output(row, include_local_paths=include_local_paths)
            for row in unreviewed[:10]
        ],
        "reviewed_enabled_not_checked_samples": [
            _mailbox_coverage_row_for_output(row, include_local_paths=include_local_paths)
            for row in reviewed_unchecked[:10]
        ],
        "local_paths_included": include_local_paths,
        "warning": warning,
        "authority_boundary": (
            "Mailbox discovery is read-only coverage evidence. It does not authorize "
            "collection, delivery, enrollment, or repo writes."
        ),
    }


def _select_enrollment(repo: list[str], cfg, *, wave: str | None = None):
    try:
        return select_enrollment_policies(repo, cfg, wave=wave or None)
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc


@app.command()
def scan(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    local_only: bool = False,
    github_only: bool = False,
    max_files: Optional[int] = typer.Option(None, min=1),
) -> None:
    """Run a read-only inventory and regenerate catalog, graph, radar, and alert outputs."""
    cfg = _cfg(config, hub)
    summary = run_scan(cfg, local=not github_only, github=not local_only, max_files=max_files)
    console.print_json(data=summary)


@app.command()
def status(
    config: Optional[Path] = typer.Option(None), hub: Optional[Path] = typer.Option(None)
) -> None:
    console.print_json(data=catalog_status(_cfg(config, hub)))


def _path_contains_path(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _validate_hub_locator_write_target(
    locator: Path | None,
    *,
    repo_root: Path,
    cwd: Path,
) -> None:
    """Keep doctor locator repair out of caller repos and arbitrary paths."""
    if locator is None:
        return
    resolved = locator.expanduser().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    is_probe_locator = (
        os.environ.get(DOCTOR_CHILD_PROBE_ENV) == "1"
        and _path_contains_path(temp_root, resolved)
        and any(part.startswith("dad-doctor-probe-") for part in resolved.parts)
    )
    if is_probe_locator:
        return
    caller_repo = find_repo_root(cwd).resolve()
    if _path_contains_path(caller_repo, resolved):
        raise ValueError(
            "Refusing to write a DAD hub locator inside the caller repository. "
            "Use the user-level ~/.dad/hub.json locator or run bootstrap from the DAD hub."
        )
    is_user_style_locator = resolved.name == "hub.json" and resolved.parent.name == ".dad"
    if is_user_style_locator:
        return
    default_locator = hub_locator_path().expanduser().resolve()
    if resolved == default_locator:
        return
    raise ValueError(
        "Refusing to write DAD hub locator to an arbitrary path. "
        "Locator writes are limited to ~/.dad/hub.json or DAD child-probe temp locators."
    )


@app.command()
def doctor(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    scope: str = typer.Option(
        "operational",
        "--scope",
        help="Readiness scope to enforce: operational or deployment.",
    ),
    write_locator: bool = typer.Option(
        False,
        "--write-hub-locator",
        help="Write ~/.dad/hub.json for this DAD hub before running the check.",
    ),
    locator: Optional[Path] = typer.Option(
        None,
        "--locator",
        help="Alternate hub locator path for tests or custom local installs.",
    ),
    skip_invocation_probes: bool = typer.Option(
        False,
        "--skip-invocation-probes",
        help="Internal deployment doctor probe mode; avoids recursive wrapper verification.",
    ),
) -> None:
    """Check whether the local DAD hub is operational without rescanning or mutating sources."""
    if scope not in {"operational", "deployment"}:
        raise typer.BadParameter("scope must be operational or deployment")
    hub_resolution = describe_hub_resolution(explicit_hub=hub, locator=locator)
    if not hub_resolution["resolved"]:
        console.print_json(
            data={
                "schema": (
                    "deployment_readiness.v1"
                    if scope == "deployment"
                    else "operational_readiness.v1"
                ),
                "generated_at": utc_now(),
                "ready": False,
                "deployment_ready": False,
                "candidate_only": True,
                "authority_boundary": (
                    "Deployment readiness reports local DAD callability only. It does not scan, "
                    "mutate target repositories, approve public release, or satisfy enrollment gates."
                ),
                "deployment": {
                    "hub_resolution": hub_resolution,
                    "unavailable_hub_policy": UNAVAILABLE_HUB_POLICY,
                },
                "warnings": [hub_resolution.get("error", "DAD hub unavailable.")],
            }
        )
        raise typer.Exit(2)
    resolved_hub = Path(str(hub_resolution["hub_path"]))
    cfg = _cfg(config, resolved_hub)
    if write_locator:
        try:
            _validate_hub_locator_write_target(
                locator,
                repo_root=cfg.repo_root,
                cwd=Path.cwd(),
            )
        except ValueError as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    locator_write = None
    if write_locator:
        try:
            locator_write = write_hub_locator(cfg.repo_root, locator)
        except OSError as exc:
            error = f"hub locator write failed: {type(exc).__name__}"
            result = {
                "schema": (
                    "deployment_readiness.v1"
                    if scope == "deployment"
                    else "operational_readiness.v1"
                ),
                "generated_at": utc_now(),
                "ready": False,
                "deployment_ready": False,
                "candidate_only": True,
                "authority_boundary": (
                    "Deployment readiness reports local DAD callability only. It does not scan, "
                    "mutate target repositories, approve public release, or satisfy enrollment gates."
                ),
                "deployment": {
                    "hub_resolution": hub_resolution,
                    "unavailable_hub_policy": UNAVAILABLE_HUB_POLICY,
                    "locator_write": {
                        "written": False,
                        "error": error,
                        "error_type": type(exc).__name__,
                    },
                },
                "warnings": [error],
            }
            console.print_json(data=result)
            raise typer.Exit(2) from exc
    if scope == "deployment":
        deployment = build_deployment_status(
            cfg,
            hub_resolution=hub_resolution,
            locator_write=locator_write,
            locator_path=locator,
            cwd=Path.cwd(),
            skip_invocation_probes=skip_invocation_probes,
        )
        result = {
            "schema": "deployment_readiness.v1",
            "generated_at": utc_now(),
            "ready": deployment["ready"],
            "deployment_ready": deployment["ready"],
            "candidate_only": True,
            "authority_boundary": (
                "Deployment readiness reports local DAD callability only. It does not scan, "
                "mutate target repositories, approve public release, or satisfy enrollment gates."
            ),
            "deployment": deployment,
            "warnings": deployment["warnings"],
        }
        console.print_json(data=result)
        if not result["deployment_ready"]:
            raise typer.Exit(2)
        return
    result = write_operational_readiness_report(
        cfg,
        hub_resolution=hub_resolution,
        locator_write=locator_write,
        locator_path=locator,
        cwd=Path.cwd(),
    )
    console.print_json(data=result)
    ready_key = "deployment_ready" if scope == "deployment" else "ready"
    if not result[ready_key]:
        raise typer.Exit(2)


@rust_app.command("scan-local")
def rust_scan_local(
    source: Path = typer.Option(..., "--source", help="Local source tree to scan."),
    source_id: str = typer.Option(..., "--source-id", help="Stable DAD source identifier."),
    path_alias: str = typer.Option(..., "--path-alias", help="Alias used instead of raw paths."),
    out: Path = typer.Option(..., "--out", help="JSONL observation output path."),
    summary_out: Path = typer.Option(..., "--summary-out", help="Scan summary JSON output path."),
    quarantine_out: Path = typer.Option(
        ..., "--quarantine-out", help="Quarantine/skip report JSON output path."
    ),
    max_files: Optional[int] = typer.Option(None, "--max-files", min=1),
    max_content_hash_bytes: int = typer.Option(10_485_760, "--max-content-hash-bytes", min=1),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks"),
    exclude: list[str] = typer.Option([], "--exclude", help="Additional glob exclude pattern."),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest-path"),
    cargo_bin: str = typer.Option("cargo", "--cargo-bin"),
    timeout_seconds: int = typer.Option(300, "--timeout-seconds", min=1),
    include_output: bool = typer.Option(
        False, "--include-output", help="Include raw Rust subprocess stdout/stderr."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run DAD's Rust leaf scanner through the Python orchestration boundary."""
    cfg = _cfg(hub=hub)
    result = run_dad_scan_core(
        repo_root=cfg.repo_root,
        source=source,
        source_id=source_id,
        path_alias=path_alias,
        out=out,
        summary_out=summary_out,
        quarantine_out=quarantine_out,
        max_files=max_files,
        max_content_hash_bytes=max_content_hash_bytes,
        follow_symlinks=follow_symlinks,
        excludes=exclude,
        cargo_bin=cargo_bin,
        manifest_path=manifest_path,
        timeout_seconds=timeout_seconds,
    )
    console.print_json(data=result.to_dict(include_output=include_output))
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def _default_rust_mail_spool_roots(repo_root: Path) -> tuple[list[Path], list[str]]:
    return (
        [
            repo_root / ".digital-asset" / "mail",
            repo_root / "processed" / "mail",
            repo_root / "mail" / "outbox" / "rust_rollout",
            repo_root / "processed" / "mail" / "staged" / "rust_rollout",
        ],
        [
            "dad/repo-mail-mirror",
            "dad/central-mail",
            "dad/rust-rollout-reference",
            "dad/rust-rollout-staging",
        ],
    )


def _default_rust_event_log_roots(repo_root: Path) -> tuple[list[Path], list[str]]:
    return (
        [
            repo_root / ".digital-asset" / "events",
            repo_root / "processed" / "events",
        ],
        [
            "dad/repo-event-mirror",
            "dad/central-events",
        ],
    )


def _rust_safe_alias_fragment(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or fallback


def _default_rust_repo_inventory_roots(cfg) -> tuple[list[Path], list[str]]:
    roots: list[Path] = []
    aliases: list[str] = []
    for index, source in enumerate(getattr(cfg, "local_sources", []) or [], start=1):
        if not bool(getattr(source, "enabled", True)):
            continue
        roots.append(Path(getattr(source, "path")))
        source_id = _rust_safe_alias_fragment(
            str(getattr(source, "id", "") or ""), f"source-{index}"
        )
        aliases.append(f"dad-local-source/{source_id}")
    if not roots:
        roots.append(cfg.repo_root)
        aliases.append("dad-local-source/dad")
    return roots, aliases


def _infer_github_owner(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        full_name = str(row.get("full_name") or row.get("nameWithOwner") or "")
        if "/" in full_name:
            return full_name.split("/", 1)[0]
    return "unknown"


def _github_sources_with_reviewed_file(
    cfg,
    *,
    repositories_file: Path,
    source_id: str,
    owner: str,
) -> list[GitHubSource]:
    resolved_file = (
        repositories_file if repositories_file.is_absolute() else cfg.repo_root / repositories_file
    )
    rows = load_github_repositories_file(resolved_file)
    inferred_owner = owner or _infer_github_owner(rows)
    existing_sources = list(cfg.github_sources)
    template = next((source for source in existing_sources if source.id == source_id), None)
    reviewed_source = GitHubSource(
        id=source_id,
        owner=inferred_owner
        if inferred_owner != "unknown"
        else (template.owner if template else inferred_owner),
        enabled=True,
        token_env=template.token_env if template else "GITHUB_TOKEN",
        include_private=template.include_private if template else True,
        include_archived=template.include_archived if template else True,
        content_mode=template.content_mode if template else "priority",
        max_file_bytes=template.max_file_bytes if template else 1_000_000,
        priority_patterns=list(template.priority_patterns) if template else [],
        repositories=rows,
        repositories_file=resolved_file,
    )
    replaced = False
    updated: list[GitHubSource] = []
    for source in existing_sources:
        if source.id == source_id:
            updated.append(reviewed_source)
            replaced = True
        else:
            updated.append(source)
    if not replaced:
        updated.append(reviewed_source)
    return updated


@rust_app.command("mail-spool-check")
def rust_mail_spool_check(
    root: list[Path] = typer.Option([], "--root", help="Mail root to inspect."),
    root_alias: list[str] = typer.Option(
        [],
        "--root-alias",
        help="Public-safe alias for the matching --root. Required when --root is provided.",
    ),
    max_jsonl_row_bytes: int = typer.Option(MAX_MAIL_RECORD_BYTES, "--max-jsonl-row-bytes", min=1),
    max_samples: int = typer.Option(25, "--max-samples", min=0),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest-path"),
    cargo_bin: str = typer.Option("cargo", "--cargo-bin"),
    timeout_seconds: int = typer.Option(120, "--timeout-seconds", min=1),
    include_output: bool = typer.Option(
        False, "--include-output", help="Include raw Rust subprocess stdout/stderr."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run the Rust read-only mail-spool probe through the Python boundary."""
    cfg = _cfg(hub=hub)
    roots, aliases = (list(root), list(root_alias))
    default_roots_used = not roots and not aliases
    if roots or aliases:
        if len(roots) != len(aliases):
            raise typer.BadParameter("Provide exactly one --root-alias for each --root.")
    else:
        roots, aliases = _default_rust_mail_spool_roots(cfg.repo_root)
    result = run_dad_mail_spool_check(
        repo_root=cfg.repo_root,
        roots=roots,
        root_aliases=aliases,
        max_jsonl_row_bytes=max_jsonl_row_bytes,
        max_samples=max_samples,
        cargo_bin=cargo_bin,
        manifest_path=manifest_path,
        timeout_seconds=timeout_seconds,
    )
    payload = result.to_dict(include_output=include_output)
    payload["scope"] = {
        "schema_version": "dad_rust_mail_spool_probe_scope.v1",
        "hub_local_default_roots": default_roots_used,
        "structural_spool_check_only": True,
        "mail_storm_gate_satisfied": False,
        "authoritative_gate": (
            "python -m digital_asset_directory.cli mail doctor --repo all "
            "--summary-only --fail-on-dirty --fail-on-coverage-gap"
        ),
        "authority_boundary": (
            "Rust mail-spool-check is structural evidence only. It does not prove "
            "reviewed repo coverage and cannot authorize collect, route, deliver, "
            "public release, or adoption."
        ),
    }
    if isinstance(payload.get("summary"), dict):
        payload["summary"]["mail_spool_structural_clean"] = (
            int(payload["summary"].get("issue_count", 0) or 0) == 0
        )
        payload["summary"]["structural_spool_check_only"] = True
        payload["summary"]["mail_storm_gate_satisfied"] = False
    console.print_json(data=payload)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@rust_app.command("event-log-check")
def rust_event_log_check(
    root: list[Path] = typer.Option([], "--root", help="Event JSONL root to inspect."),
    root_alias: list[str] = typer.Option(
        [],
        "--root-alias",
        help="Public-safe alias for the matching --root. Required when --root is provided.",
    ),
    max_jsonl_row_bytes: int = typer.Option(MAX_MAIL_RECORD_BYTES, "--max-jsonl-row-bytes", min=1),
    max_samples: int = typer.Option(25, "--max-samples", min=0),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest-path"),
    cargo_bin: str = typer.Option("cargo", "--cargo-bin"),
    timeout_seconds: int = typer.Option(120, "--timeout-seconds", min=1),
    include_output: bool = typer.Option(
        False, "--include-output", help="Include raw Rust subprocess stdout/stderr."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run the Rust read-only event-log probe through the Python boundary."""
    cfg = _cfg(hub=hub)
    roots, aliases = (list(root), list(root_alias))
    default_roots_used = not roots and not aliases
    if roots or aliases:
        if len(roots) != len(aliases):
            raise typer.BadParameter("Provide exactly one --root-alias for each --root.")
    else:
        roots, aliases = _default_rust_event_log_roots(cfg.repo_root)
    result = run_dad_event_log_check(
        repo_root=cfg.repo_root,
        roots=roots,
        root_aliases=aliases,
        max_jsonl_row_bytes=max_jsonl_row_bytes,
        max_samples=max_samples,
        cargo_bin=cargo_bin,
        manifest_path=manifest_path,
        timeout_seconds=timeout_seconds,
    )
    payload = result.to_dict(include_output=include_output)
    payload["scope"] = {
        "schema_version": "dad_rust_event_log_probe_scope.v1",
        "hub_local_default_roots": default_roots_used,
        "structural_event_check_only": True,
        "event_pipeline_gate_satisfied": False,
        "authoritative_gate": (
            "python -m digital_asset_directory.cli events collect/report "
            "plus python -m digital_asset_directory.cli validate"
        ),
        "authority_boundary": (
            "Rust event-log-check is structural evidence only. It does not collect, "
            "route, release, infer adoption, update response state, or satisfy "
            "Phase 10A human gates."
        ),
    }
    if isinstance(payload.get("summary"), dict):
        roots_summary = payload["summary"].get("roots", [])
        all_roots_checked = isinstance(roots_summary, list) and all(
            isinstance(row, dict) and row.get("status") == "checked" for row in roots_summary
        )
        payload["summary"]["event_log_structural_clean"] = (
            all_roots_checked and int(payload["summary"].get("issue_count", 0) or 0) == 0
        )
        payload["summary"]["event_log_all_roots_checked"] = all_roots_checked
        payload["summary"]["structural_event_check_only"] = True
        payload["summary"]["event_pipeline_gate_satisfied"] = False
    console.print_json(data=payload)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@rust_app.command("phase8-evidence-check")
def rust_phase8_evidence_check(
    commands: Optional[Path] = typer.Option(
        None,
        "--commands",
        help="Phase 8 command-evidence JSON file to inspect.",
    ),
    commands_alias: str = typer.Option(
        "dad/phase8/command-evidence",
        "--commands-alias",
        help="Public-safe alias for the command evidence file.",
    ),
    max_samples: int = typer.Option(25, "--max-samples", min=0),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest-path"),
    cargo_bin: str = typer.Option("cargo", "--cargo-bin"),
    timeout_seconds: int = typer.Option(120, "--timeout-seconds", min=1),
    include_output: bool = typer.Option(
        False, "--include-output", help="Include raw Rust subprocess stdout/stderr."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run the Rust read-only Phase 8 command-evidence structural checker."""
    cfg = _cfg(hub=hub)
    default_commands_used = commands is None
    commands_path = commands or (
        cfg.repo_root / "roadmap" / "evidence" / "phase-8-dad-local-deployment.commands.json"
    )
    result = run_dad_phase8_evidence_check(
        repo_root=cfg.repo_root,
        commands=commands_path,
        commands_alias=commands_alias,
        max_samples=max_samples,
        cargo_bin=cargo_bin,
        manifest_path=manifest_path,
        timeout_seconds=timeout_seconds,
    )
    payload = result.to_dict(include_output=include_output)
    payload["scope"] = {
        "schema_version": "dad_rust_phase8_evidence_probe_scope.v1",
        "hub_local_default_commands": default_commands_used,
        "structural_phase8_evidence_check_only": True,
        "phase8_human_gate_satisfied": False,
        "authoritative_gate": (
            "python -m digital_asset_directory.cli roadmap check --no-update "
            "plus recorded human gate review"
        ),
        "authority_boundary": (
            "Rust phase8-evidence-check validates command evidence structure only. "
            "It does not run deployment smoke tests, approve human gates, authorize "
            "enrollment, deliver mail, or promote Rust to deployment policy authority."
        ),
    }
    if isinstance(payload.get("summary"), dict):
        payload["summary"]["structural_phase8_evidence_check_only"] = True
        payload["summary"]["phase8_human_gate_satisfied"] = False
    console.print_json(data=payload)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@rust_app.command("repo-inventory-probe")
def rust_repo_inventory_probe(
    root: list[Path] = typer.Option([], "--root", help="Local root to inspect for Git repos."),
    root_alias: list[str] = typer.Option(
        [],
        "--root-alias",
        help="Public-safe alias for the matching --root. Required when --root is provided.",
    ),
    max_depth: int = typer.Option(5, "--max-depth", min=1, max=12),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks"),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest-path"),
    cargo_bin: str = typer.Option("cargo", "--cargo-bin"),
    timeout_seconds: int = typer.Option(120, "--timeout-seconds", min=1),
    include_output: bool = typer.Option(
        False, "--include-output", help="Include raw Rust subprocess stdout/stderr."
    ),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run the Rust read-only repo-root probe through the Python boundary."""
    cfg = _cfg(config, hub)
    roots, aliases = (list(root), list(root_alias))
    if roots or aliases:
        if len(roots) != len(aliases):
            raise typer.BadParameter("Provide exactly one --root-alias for each --root.")
    else:
        roots, aliases = _default_rust_repo_inventory_roots(cfg)
    result = run_dad_repo_inventory_probe(
        repo_root=cfg.repo_root,
        roots=roots,
        root_aliases=aliases,
        max_depth=max_depth,
        follow_symlinks=follow_symlinks,
        cargo_bin=cargo_bin,
        manifest_path=manifest_path,
        timeout_seconds=timeout_seconds,
    )
    console.print_json(data=result.to_dict(include_output=include_output))
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@rust_app.command("repo-inventory-parity")
def rust_repo_inventory_parity(
    root: list[Path] = typer.Option([], "--root", help="Local root to inspect for Git repos."),
    root_alias: list[str] = typer.Option(
        [],
        "--root-alias",
        help="Public-safe alias for the matching --root. Required when --root is provided.",
    ),
    max_depth: int = typer.Option(5, "--max-depth", min=1, max=12),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest-path"),
    cargo_bin: str = typer.Option("cargo", "--cargo-bin"),
    timeout_seconds: int = typer.Option(120, "--timeout-seconds", min=1),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Compare Rust and Python read-only local Git-root discovery."""
    cfg = _cfg(config, hub)
    roots, aliases = (list(root), list(root_alias))
    if roots or aliases:
        if len(roots) != len(aliases):
            raise typer.BadParameter("Provide exactly one --root-alias for each --root.")
    else:
        roots, aliases = _default_rust_repo_inventory_roots(cfg)
    rust_result = run_dad_repo_inventory_probe(
        repo_root=cfg.repo_root,
        roots=roots,
        root_aliases=aliases,
        max_depth=max_depth,
        follow_symlinks=False,
        cargo_bin=cargo_bin,
        manifest_path=manifest_path,
        timeout_seconds=timeout_seconds,
    )
    if rust_result.returncode != 0 or not rust_result.summary or not rust_result.summary_valid:
        console.print_json(data=rust_result.to_dict())
        raise typer.Exit(rust_result.returncode or 2)
    parity = write_repo_inventory_rust_probe_parity(
        cfg.repo_root,
        roots=roots,
        root_aliases=aliases,
        rust_summary=rust_result.summary,
        max_depth=max_depth,
        follow_symlinks=False,
    )
    console.print_json(
        data={
            "schema_version": "dad_repo_inventory_rust_probe_parity_command.v0_1",
            "rust_probe": rust_result.to_dict(),
            **parity,
        }
    )


@rust_rollout_app.command("plan")
def rust_rollout_plan(
    config_path: Path = typer.Option(
        Path("config/repo_rust_status.yaml"), "--config", help="Rust repo status matrix."
    ),
    out_dir: Path = typer.Option(
        Path("processed/reports/rust_rollout"), "--out-dir", help="DAD-local report output dir."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write DAD's Rust rollout plan without mutating target repos."""
    cfg = _cfg(hub=hub)
    result = write_rust_rollout_plan(
        _repo_path(cfg.repo_root, config_path) or config_path,
        data_relative_path(cfg.repo_root, out_dir),
    )
    console.print_json(data=result)


@rust_rollout_app.command("build-mail")
def rust_rollout_build_mail(
    config_path: Path = typer.Option(Path("config/repo_rust_status.yaml"), "--config"),
    out_dir: Path = typer.Option(Path("processed/mail/staged/rust_rollout"), "--out-dir"),
    dirty_state_ack: Optional[str] = typer.Option(
        None,
        "--dirty-state-ack",
        help=(
            "Allow staged Rust packet regeneration after reviewing a dirty mail doctor "
            "report; normal mail collect/route/deliver still fail closed."
        ),
    ),
    dirty_state_fingerprint: Optional[str] = typer.Option(
        None,
        "--dirty-state-fingerprint",
        help=(
            "Required with --dirty-state-ack. Copy the fingerprint from the current "
            "blocked dirty gate so the bypass is tied to the exact reviewed storm state."
        ),
    ),
    promote_reference_snapshot_ack: Optional[str] = typer.Option(
        None,
        "--promote-reference-snapshot-ack",
        help=(
            "Required when --out-dir targets tracked mail/outbox/rust_rollout. "
            "Use only after reviewing staged packet diffs and promotion evidence."
        ),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Build deterministic local Rust rollout instruction packets."""
    cfg = _cfg(hub=hub)
    resolved_out_dir = data_relative_path(cfg.repo_root, out_dir)
    active_data_root, _data_root_mode = resolve_data_root(cfg.repo_root)
    central_mail_root = data_path(cfg.repo_root, "central_mail")
    live_mail_roots = [
        cfg.repo_root / MAIL_MIRROR_DIR,
        central_mail_root / "inbox",
        central_mail_root / "outbox",
        central_mail_root / "archive",
        central_mail_root / "quarantine",
        central_mail_root / "releases",
    ]
    live_mail_root = next(
        (root for root in live_mail_roots if _is_under_or_equal(resolved_out_dir, root)),
        None,
    )
    if live_mail_root is not None:
        console.print_json(
            data={
                "schema_version": "dad_rust_rollout_live_mail_target_gate.v1",
                "blocked": True,
                "operation": "rust-rollout build-mail",
                "out_dir": _local_path_ref(resolved_out_dir, cfg.repo_root),
                "live_mail_root": safe_relative(live_mail_root, cfg.repo_root),
                "required_out_dir": "processed/mail/staged/rust_rollout",
                "authority_boundary": (
                    "Rust rollout packet generation may write only to ignored staging "
                    "or to the tracked reference snapshot with explicit promotion ack. "
                    "It must not write generated packets directly into live mailboxes, "
                    "audit logs, quarantine, or release records."
                ),
            }
        )
        raise typer.Exit(2)
    tracked_snapshot_dir = (cfg.repo_root / "mail" / "outbox" / "rust_rollout").resolve(
        strict=False
    )
    default_staging_dir = (central_mail_root / "staged" / "rust_rollout").resolve(strict=False)
    temp_root = _system_temp_root()
    if (
        _is_under_or_equal(resolved_out_dir, tracked_snapshot_dir)
        and not (promote_reference_snapshot_ack or "").strip()
    ):
        console.print_json(
            data={
                "schema_version": "dad_rust_rollout_snapshot_promotion_gate.v1",
                "blocked": True,
                "operation": "rust-rollout build-mail",
                "out_dir": _local_path_ref(resolved_out_dir, cfg.repo_root),
                "tracked_reference_snapshot": safe_relative(tracked_snapshot_dir, cfg.repo_root),
                "required_ack": "--promote-reference-snapshot-ack",
                "authority_boundary": (
                    "Routine Rust rollout packet generation writes to ignored staging. "
                    "Tracked mail/outbox/rust_rollout snapshots are promoted deliberately "
                    "after review and are not delivered inbox mail."
                ),
            }
        )
        raise typer.Exit(2)
    if promote_reference_snapshot_ack and not _is_under_or_equal(
        resolved_out_dir, tracked_snapshot_dir
    ):
        console.print_json(
            data={
                "schema_version": "dad_rust_rollout_snapshot_promotion_scope_gate.v1",
                "blocked": True,
                "operation": "rust-rollout build-mail",
                "out_dir": _local_path_ref(resolved_out_dir, cfg.repo_root),
                "tracked_reference_snapshot": safe_relative(
                    tracked_snapshot_dir,
                    cfg.repo_root,
                ),
                "authority_boundary": (
                    "The promotion acknowledgement is valid only when --out-dir targets "
                    "mail/outbox/rust_rollout. Staging or ad hoc output must not create "
                    "tracked reference snapshot promotion evidence."
                ),
            }
        )
        raise typer.Exit(2)
    if (
        not _is_under_or_equal(resolved_out_dir, cfg.repo_root)
        and not _is_under_or_equal(resolved_out_dir, active_data_root)
        and not _is_under_or_equal(resolved_out_dir, temp_root)
    ):
        console.print_json(
            data={
                "schema_version": "dad_rust_rollout_external_output_gate.v1",
                "blocked": True,
                "operation": "rust-rollout build-mail",
                "out_dir": _local_path_ref(resolved_out_dir, cfg.repo_root),
                "allowed_output_roots": [
                    safe_relative(default_staging_dir, cfg.repo_root),
                    safe_relative(tracked_snapshot_dir, cfg.repo_root),
                    "system-temp",
                ],
                "authority_boundary": (
                    "Rust rollout packet generation may not write to arbitrary "
                    "absolute paths because those paths may be another repo's "
                    "mailbox or source tree. Use DAD ignored staging, the tracked "
                    "reference snapshot with promotion ack, or a system temp "
                    "directory for ad hoc review."
                ),
            }
        )
        raise typer.Exit(2)
    if (
        _is_under_or_equal(resolved_out_dir, cfg.repo_root)
        and not _is_under_or_equal(resolved_out_dir, default_staging_dir)
        and not _is_under_or_equal(resolved_out_dir, tracked_snapshot_dir)
    ):
        console.print_json(
            data={
                "schema_version": "dad_rust_rollout_output_root_gate.v1",
                "blocked": True,
                "operation": "rust-rollout build-mail",
                "out_dir": _local_path_ref(resolved_out_dir, cfg.repo_root),
                "allowed_in_repo_output_roots": [
                    safe_relative(default_staging_dir, cfg.repo_root),
                    safe_relative(tracked_snapshot_dir, cfg.repo_root),
                ],
                "authority_boundary": (
                    "In-repo Rust rollout packet output is restricted to ignored staging "
                    "or the tracked reference snapshot with explicit promotion ack. Use an "
                    "out-of-repo temporary directory for ad hoc packet review."
                ),
            }
        )
        raise typer.Exit(2)
    dirty_check = _ensure_mail_clean_for_operation(
        cfg,
        [],
        operation="rust-rollout build-mail",
        dirty_state_ack=dirty_state_ack,
        dirty_state_fingerprint=dirty_state_fingerprint,
        allow_dirty_ack=True,
        dirty_ack_issue_types={
            "rust_rollout_packet_invalid",
            "rust_rollout_packet_delivery_status",
            "rust_rollout_duplicate_packet_identity",
            "rust_rollout_semantic_identity_conflict",
        },
    )
    try:
        result = build_rust_rollout_mail_packets(
            _repo_path(cfg.repo_root, config_path) or config_path,
            resolved_out_dir,
        )
    except ValueError as exc:
        console.print_json(
            data={
                "schema_version": "dad_rust_rollout_stale_output_gate.v1",
                "blocked": True,
                "operation": "rust-rollout build-mail",
                "out_dir": _local_path_ref(resolved_out_dir, cfg.repo_root),
                "error": str(exc),
                "authority_boundary": (
                    "Rust rollout packet directories must not keep stale packet files. "
                    "Remove or quarantine obsolete generated packets before rebuilding."
                ),
            }
        )
        raise typer.Exit(2) from exc
    if promote_reference_snapshot_ack:
        promotion_record = _rust_rollout_snapshot_promotion_record(
            repo_root=cfg.repo_root,
            out_dir=resolved_out_dir,
            ack=promote_reference_snapshot_ack,
            packet_count=int(result.get("packet_count", 0)),
        )
        append_jsonl_locked(_rust_rollout_snapshot_promotion_log(cfg.repo_root), promotion_record)
        result["tracked_reference_snapshot_promotion"] = {
            "acknowledged": True,
            "ack": promote_reference_snapshot_ack,
            "tracked_reference_snapshot": safe_relative(tracked_snapshot_dir, cfg.repo_root),
            "audit_log": safe_relative(
                _rust_rollout_snapshot_promotion_log(cfg.repo_root),
                cfg.repo_root,
            ),
            "snapshot_json_file_count": promotion_record["snapshot_json_file_count"],
        }
    if dirty_check.get("bypassed"):
        result["mail_dirty_check"] = dirty_check
    console.print_json(data=result)


@rust_rollout_app.command("apply")
def rust_rollout_apply(
    repo: str = typer.Option(..., "--repo"),
    approval_id: str = typer.Option(..., "--approval-id"),
    force: bool = typer.Option(False, "--force"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    config_path: Path = typer.Option(Path("config/repo_rust_status.yaml"), "--config"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Apply a conservative target-repo Rust scaffold when policy allows it."""
    cfg = _cfg(hub=hub)
    records = load_rust_repo_records(_repo_path(cfg.repo_root, config_path) or config_path)
    matches = [record for record in records if record.repo == repo or record.repo_name == repo]
    if not matches:
        console.print(f"Unknown Rust rollout repo: {repo}")
        raise typer.Exit(2)
    result = apply_rust_rollout_scaffold(
        repo_root=cfg.repo_root,
        record=matches[0],
        approval_id=approval_id,
        force=force,
        dry_run=dry_run,
    )
    console.print_json(data=result.to_dict())
    if result.status == "blocked":
        raise typer.Exit(2)


@rust_rollout_app.command("lessons-summarize")
def rust_rollout_lessons_summarize(
    ledger: Path = typer.Option(Path("lessons/rust_rollout/lesson_ledger.jsonl"), "--ledger"),
    out_dir: Path = typer.Option(Path("processed/reports/rust_rollout"), "--out-dir"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Rebuild Rust rollout lesson summaries from the append-only ledger."""
    cfg = _cfg(hub=hub)
    result = summarize_rust_rollout_lessons(
        _repo_path(cfg.repo_root, ledger) or ledger,
        data_relative_path(cfg.repo_root, out_dir),
    )
    console.print_json(data=result)


@template_app.command("check")
def templates_check(hub: Optional[Path] = typer.Option(None)) -> None:
    """Validate the tracked template registry and write the generated dependency report."""
    cfg = _cfg(hub=hub)
    result = write_template_library_report(cfg.repo_root)
    console.print_json(data=result)
    if not result["valid"]:
        raise typer.Exit(2)


@template_app.command("validate")
def templates_validate(hub: Optional[Path] = typer.Option(None)) -> None:
    """Validate template records without writing reports."""
    cfg = _cfg(hub=hub)
    result = validate_template_registry(cfg.repo_root)
    console.print_json(data=result)
    if not result["valid"]:
        raise typer.Exit(2)


@app.command()
def context(
    query: str,
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(20, min=1, max=100),
) -> None:
    cfg = _cfg(config, hub)
    with CatalogDB(cfg.database_path) as db:
        pack = build_context_pack(query, db.assets(), db.edges(), db.alerts(open_only=True), limit)
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:80] or "context"
    paths = write_context_pack(cfg.repo_root, pack, slug)
    console.print(f"Wrote {paths[0]} and {paths[1]}")


@app.command()
def idea(
    query: str,
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(20, min=1, max=100),
) -> None:
    """Create an AI-ready context pack for an idea or build problem."""
    context(query, config, hub, limit)


@app.command(name="validate")
def validate_command(hub: Optional[Path] = typer.Option(None)) -> None:
    cfg = _cfg(hub=hub)
    result = validate_repo(cfg.repo_root)
    console.print_json(data=result)
    if not result["valid"]:
        raise typer.Exit(1)


@test_app.command("parity")
def test_parity_command(
    native_command: str = typer.Option(
        "python -m pytest -q",
        "--native-command",
        help="Native command string. Prefer --native-command-json for paths with spaces.",
    ),
    native_command_json: Optional[str] = typer.Option(
        None,
        "--native-command-json",
        help='Native command argv as JSON, for example ["python","-m","pytest","-q"].',
    ),
    shadow_command: Optional[str] = typer.Option(
        None,
        "--shadow-command",
        help="Candidate shadow command string. Prefer --shadow-command-json for paths with spaces.",
    ),
    shadow_command_json: Optional[str] = typer.Option(
        None,
        "--shadow-command-json",
        help='Candidate shadow command argv as JSON, for example ["cargo","test"].',
    ),
    timeout_seconds: int = typer.Option(120, min=1, max=7200),
    native_report: Optional[Path] = typer.Option(None, "--native-report"),
    shadow_report: Optional[Path] = typer.Option(None, "--shadow-report"),
    audit: bool = typer.Option(True, "--audit/--no-audit"),
    audit_path: Optional[Path] = typer.Option(None, "--audit-path"),
    session: Optional[str] = typer.Option(None, "--session"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run native pytest and a candidate Rust shadow path, then compare and audit."""
    cfg = _cfg(hub=hub)
    native_spec = _json_command(native_command_json, "--native-command-json") or native_command
    shadow_spec = _json_command(shadow_command_json, "--shadow-command-json") or shadow_command
    if shadow_spec is None:
        raise typer.BadParameter("Provide --shadow-command or --shadow-command-json.")
    result = run_test_parity(
        cfg.repo_root,
        native_command=native_spec,
        shadow_command=shadow_spec,
        timeout_seconds=timeout_seconds,
        native_report=native_report,
        shadow_report=shadow_report,
        audit=audit,
        audit_path=audit_path,
        session_id=session,
    )
    console.print_json(data=result)
    if result["exit_code"] != 0:
        raise typer.Exit(result["exit_code"])


@roadmap_app.command("check")
def roadmap_check(hub: Optional[Path] = typer.Option(None), no_update: bool = False) -> None:
    cfg = _cfg(hub=hub)
    result = check_roadmap(cfg.repo_root, update=not no_update)
    console.print_json(data=result)


@roadmap_app.command("human-gate-review-packet")
def roadmap_human_gate_review_packet(
    phase_id: str = typer.Argument(..., help="Roadmap phase id to compile for human review."),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional output path. Defaults to roadmap/evidence/<phase-id>.human-review-packet.json.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a review-only packet for roadmap human gates."""
    cfg = _cfg(hub=hub)
    result = write_human_gate_review_packet(cfg.repo_root, phase_id, output=output)
    console.print_json(data=result)


@mail_app.command("compose")
def mail_compose(
    repo: Path = typer.Option(Path("."), "--repo"),
    message_type: str = typer.Option(..., "--type"),
    target_repo: str = typer.Option("central_only", "--target-repo"),
    summary: str = typer.Option(..., "--summary"),
    payload: list[str] = typer.Option(
        [],
        "--payload",
        help="Simple payload field in key=value form. Use --payload-file for structured JSON.",
    ),
    payload_json: Optional[str] = typer.Option(
        None,
        "--payload-json",
        help="Structured payload JSON object. Prefer --payload-file for large lesson packs.",
    ),
    payload_file: Optional[Path] = typer.Option(
        None,
        "--payload-file",
        help="Path to a structured payload JSON object; UTF-8 BOM is tolerated.",
    ),
    evidence: list[str] = typer.Option([], "--evidence"),
    suggested_action: list[str] = typer.Option([], "--suggested-action"),
    sensitivity: str = typer.Option("internal", "--sensitivity"),
    thread_id: Optional[str] = typer.Option(None, "--thread-id"),
    dedupe_key: Optional[str] = typer.Option(None, "--dedupe-key"),
    composed_by: str = typer.Option("unknown", "--composed-by"),
    supersedes: str = typer.Option(
        "",
        "--supersedes",
        help="Mail ID of a previously sent message this one upgrades; reuses its thread.",
    ),
    allow_similar: bool = typer.Option(
        False, "--allow-similar", help="Send even when a near-duplicate was already sent."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Append a candidate mail packet to a repo-local outbox."""
    cfg = _cfg(hub=hub)
    try:
        result = compose_mail(
            repo.resolve(),
            message_type=message_type,
            target_repo=target_repo,
            summary=summary,
            payload=_mail_payload_options(
                payload,
                payload_json=payload_json,
                payload_file=payload_file,
            ),
            evidence=evidence,
            suggested_actions=suggested_action,
            sensitivity=sensitivity,
            thread_id=thread_id,
            dedupe_key=dedupe_key,
            repo_policies=cfg.mail_repos,
            composed_by=composed_by,
            supersedes=supersedes,
            allow_similar=allow_similar,
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("discover-repos")
def mail_discover_repos(
    include_local_paths: bool = typer.Option(
        False,
        "--include-local-paths",
        help="Include exact local paths for local operator debugging.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Report candidate repo mailboxes without delivering to them."""
    cfg = _cfg(hub=hub)
    candidates = [
        _mailbox_coverage_row_for_output(row, include_local_paths=include_local_paths)
        for row in _mail_repo_candidates(cfg)
    ]
    unreviewed_count = sum(
        1 for row in candidates if not row["configured"] and (row["has_inbox"] or row["has_outbox"])
    )
    console.print_json(
        data={
            "schema_version": "dad_mail_repo_discovery.v1",
            "candidate_count": len(candidates),
            "unreviewed_mailbox_candidate_count": unreviewed_count,
            "candidates": candidates,
            "authority_boundary": (
                "Discovery is read-only. Add reviewed mail.repos policy before using --repo all."
            ),
        }
    )


@mail_app.command("collect")
def mail_collect(
    repo: list[str] = typer.Option([], "--repo"),
    allow_coverage_gap_ack: Optional[str] = typer.Option(
        None,
        "--allow-coverage-gap-ack",
        help=(
            "Permit --repo all collection to continue with reviewed mail.repos only "
            "when read-only discovery found unreviewed mailbox candidates."
        ),
    ),
    include_local_paths: bool = typer.Option(
        False,
        "--include-local-paths",
        help="Include exact local paths in mailbox coverage output for local operator debugging.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Collect repo outboxes into DAD's central mail inbox."""
    cfg = _cfg(hub=hub)
    selected = _discover_mail_repos(repo, cfg, reviewed=True)
    coverage = _mailbox_coverage_for_repo_all(
        repo,
        cfg,
        selected,
        include_local_paths=include_local_paths,
    )
    _block_on_mailbox_coverage_gap(
        cfg,
        coverage,
        operation="mail collect",
        allow_coverage_gap_ack=allow_coverage_gap_ack,
    )
    _ensure_mail_clean_for_operation(cfg, selected, operation="mail collect")
    result = collect_mail(
        cfg.repo_root,
        selected,
        repo_policies=cfg.mail_repos,
    )
    if coverage is not None:
        result["mailbox_coverage"] = coverage
    console.print_json(data=result)
    if bool(result.get("blocked")) or int(result.get("error_count", 0) or 0):
        raise typer.Exit(2)


@mail_app.command("route")
def mail_route(
    default_target_repo: str = typer.Option("central_only", "--default-target-repo"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Categorize central inbox mail and stage delivery candidates."""
    cfg = _cfg(hub=hub)
    _ensure_mail_clean_for_operation(cfg, [], operation="mail route")
    result = route_mail(
        cfg.repo_root,
        default_target_repo=default_target_repo,
        repo_policies=cfg.mail_repos,
    )
    console.print_json(data=result)
    if bool(result.get("blocked")) or int(result.get("error_count", 0) or 0):
        raise typer.Exit(2)


@mail_app.command("ingest")
def mail_ingest(
    repo: list[str] = typer.Option(
        [],
        "--repo",
        help="Repos to collect from. Defaults to all reviewed mail.repos.",
    ),
    default_target_repo: str = typer.Option("central_only", "--default-target-repo"),
    allow_coverage_gap_ack: Optional[str] = typer.Option(
        None,
        "--allow-coverage-gap-ack",
        help=(
            "Permit --repo all ingest to continue with reviewed mail.repos only "
            "when read-only discovery found unreviewed mailbox candidates."
        ),
    ),
    include_local_paths: bool = typer.Option(
        False,
        "--include-local-paths",
        help="Include exact local paths in mailbox coverage output for local operator debugging.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Collect reviewed repo outboxes and route centrally without delivering inbox mail."""
    cfg = _cfg(hub=hub)
    repo_args = repo or ["all"]
    selected = _discover_mail_repos(repo_args, cfg, reviewed=True)
    coverage = _mailbox_coverage_for_repo_all(
        repo_args,
        cfg,
        selected,
        include_local_paths=include_local_paths,
    )
    _block_on_mailbox_coverage_gap(
        cfg,
        coverage,
        operation="mail ingest",
        allow_coverage_gap_ack=allow_coverage_gap_ack,
    )
    ingest_gate = _ensure_mail_clean_for_operation(cfg, selected, operation="mail ingest")
    collect_result = collect_mail(
        cfg.repo_root,
        selected,
        repo_policies=cfg.mail_repos,
    )
    if coverage is not None:
        collect_result["mailbox_coverage"] = coverage
    if bool(collect_result.get("blocked")) or int(collect_result.get("error_count", 0) or 0):
        console.print_json(
            data={
                "schema_version": "dad_mail_ingest_result.v1",
                "requested_repos": repo_args,
                "selected_repo_count": len(selected),
                "ingest_gate": ingest_gate,
                "collect": collect_result,
                "route": None,
                "delivery_performed": False,
                "authority_boundary": (
                    "mail ingest collects source repo outboxes into DAD and routes "
                    "central candidates only. It never writes target repo inboxes."
                ),
            }
        )
        raise typer.Exit(2)

    route_gate = _ensure_mail_clean_for_operation(cfg, [], operation="mail ingest route")
    route_result = route_mail(
        cfg.repo_root,
        default_target_repo=default_target_repo,
        repo_policies=cfg.mail_repos,
    )
    route_result_for_output = dict(route_result)
    if route_result_for_output.get("outbox"):
        route_result_for_output["outbox"] = _local_path_ref(
            Path(str(route_result_for_output["outbox"])),
            cfg.repo_root,
        )
    result = {
        "schema_version": "dad_mail_ingest_result.v1",
        "requested_repos": repo_args,
        "selected_repo_count": len(selected),
        "ingest_gate": ingest_gate,
        "route_gate": route_gate,
        "collect": collect_result,
        "route": route_result_for_output,
        "delivery_policy": _mail_delivery_policy_summary(selected, cfg.mail_repos),
        "delivery_performed": False,
        "next_command_for_delivery": (
            "python -m digital_asset_directory.cli mail storm-gate --operation delivery"
        ),
        "authority_boundary": (
            "mail ingest is the safe receive path for concurrent repo mail storms: "
            "repos write their own outboxes, DAD collects and routes centrally, and "
            "target repo inbox delivery remains a separate policy-gated operation."
        ),
    }
    console.print_json(data=result)
    if bool(route_result.get("blocked")) or int(route_result.get("error_count", 0) or 0):
        raise typer.Exit(2)


@mail_app.command("deliver")
def mail_deliver(
    repo: list[str] = typer.Option([], "--repo"),
    allow_coverage_gap_ack: Optional[str] = typer.Option(
        None,
        "--allow-coverage-gap-ack",
        help=(
            "Permit --repo all delivery to continue to reviewed mail.repos only "
            "when read-only discovery found unreviewed mailbox candidates."
        ),
    ),
    include_local_paths: bool = typer.Option(
        False,
        "--include-local-paths",
        help="Include exact local paths in mailbox coverage output for local operator debugging.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Deliver staged central outbox mail only into target repo mailboxes."""
    cfg = _cfg(hub=hub)
    selected = _discover_mail_repos(repo, cfg, delivery=True)
    coverage = _mailbox_coverage_for_repo_all(
        repo,
        cfg,
        selected,
        include_local_paths=include_local_paths,
    )
    _block_on_mailbox_coverage_gap(
        cfg,
        coverage,
        operation="mail deliver",
        allow_coverage_gap_ack=allow_coverage_gap_ack,
    )
    _ensure_mail_clean_for_operation(cfg, selected, operation="mail deliver")
    result = deliver_mail(
        cfg.repo_root,
        selected,
        repo_policies=cfg.mail_repos,
        require_target_policy=True,
    )
    if coverage is not None:
        result["mailbox_coverage"] = coverage
    console.print_json(data=result)
    if bool(result.get("blocked")) or int(result.get("error_count", 0) or 0):
        raise typer.Exit(2)


@mail_app.command("review")
def mail_review(
    repo: Path = typer.Option(Path("."), "--repo"),
    mail_id: str = typer.Option(..., "--mail-id"),
    decision: str = typer.Option(..., "--decision"),
    decided_by: str = typer.Option("unknown", "--decided-by"),
    human_verified: bool = typer.Option(False, "--human-reviewed"),
    notes: str = typer.Option("", "--notes"),
) -> None:
    """Append a local triage or human review decision for an inbox mail packet."""
    cfg = _cfg()
    try:
        result = review_mail(
            repo.resolve(),
            mail_id=mail_id,
            decision=decision,
            decided_by=decided_by,
            human_verified=human_verified,
            notes=notes,
            repo_policies=cfg.mail_repos,
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("central-review")
def mail_central_review(
    mail_id: str = typer.Option(..., "--mail-id"),
    decision: str = typer.Option(..., "--decision"),
    decided_by: str = typer.Option("unknown", "--decided-by"),
    human_verified: bool = typer.Option(False, "--human-reviewed"),
    notes: str = typer.Option("", "--notes"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Append a DAD-central triage decision for collected or routed central mail."""
    cfg = _cfg(hub=hub)
    try:
        result = review_central_mail(
            cfg.repo_root,
            mail_id=mail_id,
            decision=decision,
            decided_by=decided_by,
            human_verified=human_verified,
            notes=notes,
            repo_policies=cfg.mail_repos,
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("triage")
def mail_triage(
    repo: Path = typer.Option(Path("."), "--repo"),
    mail_id: str = typer.Option(..., "--mail-id"),
    decision: str = typer.Option(..., "--decision"),
    importance: str = typer.Option("unknown", "--importance"),
    planned_use: str = typer.Option("", "--planned-use"),
    implementation_plan: list[str] = typer.Option([], "--implementation-plan"),
    recorded_by: str = typer.Option("unknown", "--recorded-by"),
    human_verified: bool = typer.Option(False, "--human-reviewed"),
    notes: str = typer.Option("", "--notes"),
) -> None:
    """Evaluate inbox mail and record now/future adoption tracking."""
    cfg = _cfg()
    try:
        result = triage_mail(
            repo.resolve(),
            mail_id=mail_id,
            intake_decision=decision,
            importance=importance,
            planned_use=planned_use,
            implementation_plan=implementation_plan,
            recorded_by=recorded_by,
            human_verified=human_verified,
            notes=notes,
            repo_policies=cfg.mail_repos,
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("release")
def mail_release(
    mail_id: str = typer.Option(..., "--mail-id"),
    decision: str = typer.Option(..., "--decision"),
    human_reviewed_by: str = typer.Option(..., "--human-reviewed-by"),
    notes: str = typer.Option("", "--notes"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Human-approve or reject a public-facing release hold."""
    cfg = _cfg(hub=hub)
    try:
        result = release_mail(
            cfg.repo_root,
            mail_id=mail_id,
            decision=decision,
            human_reviewed_by=human_reviewed_by,
            notes=notes,
            repo_policies=cfg.mail_repos,
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("compose-asset")
def mail_compose_asset(
    asset: str = typer.Option(
        ..., "--asset", help="DAD offering ID, e.g. dad:offering:python-underused-idioms"
    ),
    target_repo: str = typer.Option(..., "--target-repo"),
    note: str = typer.Option("", "--note"),
    supersedes: str = typer.Option("", "--supersedes"),
    allow_similar: bool = typer.Option(False, "--allow-similar"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Compose the standard asset-suggestion mail: pointer, context, version, and graph edges - never a copy."""
    cfg = _cfg(hub=hub)
    try:
        result = compose_asset_suggestion(
            cfg.repo_root,
            asset_id=asset,
            target_repo=target_repo,
            note=note,
            repo_policies=cfg.mail_repos,
            supersedes=supersedes,
            allow_similar=allow_similar,
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("outbox-check")
def mail_outbox_check(
    repo: Path = typer.Option(Path("."), "--repo"),
    message_type: str = typer.Option("", "--type"),
    summary: str = typer.Option(..., "--summary"),
    payload: list[str] = typer.Option(
        [],
        "--payload",
        help="Simple payload field in key=value form. Use --payload-file for structured JSON.",
    ),
    payload_json: Optional[str] = typer.Option(
        None,
        "--payload-json",
        help="Structured payload JSON object. Prefer --payload-file for large lesson packs.",
    ),
    payload_file: Optional[Path] = typer.Option(
        None,
        "--payload-file",
        help="Path to a structured payload JSON object; UTF-8 BOM is tolerated.",
    ),
    evidence: list[str] = typer.Option([], "--evidence"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Check a proposed message against previously sent outbox mail before composing."""
    _cfg(hub=hub)
    try:
        result = check_outbox_novelty(
            repo.resolve(),
            message_type=message_type,
            summary=summary,
            payload=_mail_payload_options(
                payload,
                payload_json=payload_json,
                payload_file=payload_file,
            ),
            evidence=evidence,
        )
    except (OSError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("resurface")
def mail_resurface(
    repo: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option(..., "--task"),
    limit: int = typer.Option(3, min=1, max=10),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Bring back previously deferred/saved mail that matches the current task or watched assets."""
    cfg = _cfg(hub=hub)
    try:
        result = resurface_deferred_mail(
            repo.resolve(), task=task, hub_root=cfg.repo_root, limit=limit
        )
    except (OSError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@mail_app.command("digest")
def mail_digest(
    repo: str = typer.Option(".", "--repo"), hub: Optional[Path] = typer.Option(None)
) -> None:
    """Show unread mail and mark the repo mailbox as checked."""
    cfg = _cfg(hub=hub)
    result = digest_mail(_resolve_mail_repo(repo, cfg), repo_policies=cfg.mail_repos)
    console.print_json(data=result)


@mail_app.command("storm-gate")
def mail_storm_gate(
    repo: list[str] = typer.Option(
        [],
        "--repo",
        help="Repos to include. Defaults to all reviewed mail.repos for storm-safe checks.",
    ),
    include_local_paths: bool = typer.Option(
        False,
        "--include-local-paths",
        help="Include exact local paths in mailbox coverage output for local operator debugging.",
    ),
    fail_on_blocked: bool = typer.Option(
        True,
        "--fail-on-blocked/--no-fail-on-blocked",
        help="Exit non-zero when the selected mail-storm operation is not safe.",
    ),
    operation: str = typer.Option(
        "all",
        "--operation",
        help="Gate to use for exit status: all, ingest, or delivery.",
    ),
    fail_on_worktree_dirty: bool = typer.Option(
        False,
        "--fail-on-worktree-dirty",
        help="Also exit non-zero when the DAD git worktree is dirty.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Read-only go/no-go gate for concurrent repo mail and Rust rollout storms."""
    cfg = _cfg(hub=hub)
    repo_args = repo or ["all"]
    selected = _discover_mail_repos(repo_args, cfg)
    result = diagnose_mail_dirty_state(
        cfg.repo_root,
        selected,
        repo_policies=cfg.mail_repos,
    )
    result["delivery_policy"] = _mail_delivery_policy_summary(selected, cfg.mail_repos)
    if repo_args == ["all"]:
        coverage = _mailbox_coverage_summary(
            cfg,
            selected,
            include_local_paths=include_local_paths,
        )
        result["mailbox_coverage"] = coverage
        if isinstance(result.get("repo_scope"), dict):
            result["repo_scope"]["mailbox_coverage_warning"] = coverage["warning"]
            result["repo_scope"]["unreviewed_mailbox_candidate_count"] = coverage[
                "unreviewed_mailbox_candidate_count"
            ]
            result["repo_scope"]["reviewed_enabled_not_checked_count"] = coverage[
                "reviewed_enabled_not_checked_count"
            ]
        if coverage["warning"]:
            result["action_summary"]["next_actions"].append(
                "Classify unreviewed mailbox candidates before treating --repo all as complete."
            )
    _annotate_mail_storm_scope(result, requested_all=repo_args == ["all"])
    result["dirty_state_fingerprint"] = _mail_dirty_state_fingerprint(result)
    operation_key = _mail_storm_operation_key(operation)
    gate = _mail_storm_gate_report(
        result,
        repo_args=repo_args,
        requested_operation=operation_key,
    )
    console.print_json(data=gate)
    if fail_on_blocked and not gate["selected_operation_safe"]:
        raise typer.Exit(1)
    if fail_on_worktree_dirty and gate["worktree_dirty"]:
        raise typer.Exit(1)


@mail_app.command("repair-plan")
def mail_repair_plan(
    repo: list[str] = typer.Option(
        [],
        "--repo",
        help="Repos to include. Defaults to all reviewed mail.repos for storm-safe planning.",
    ),
    include_local_paths: bool = typer.Option(
        False,
        "--include-local-paths",
        help="Include exact local paths in mailbox coverage output for local operator debugging.",
    ),
    fail_on_blocked: bool = typer.Option(
        False,
        "--fail-on-blocked/--no-fail-on-blocked",
        help="Exit non-zero when the selected mail-storm operation is not safe.",
    ),
    operation: str = typer.Option(
        "all",
        "--operation",
        help="Gate to use for exit status: all, ingest, or delivery.",
    ),
    write_report: bool = typer.Option(
        False,
        "--write-report",
        help=(
            "Persist a DAD-local JSON and Markdown operator packet under "
            "processed/reports/mail_storm_repair without executing repairs."
        ),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Read-only ordered repair plan for blocked mail/Rust rollout storm states."""
    cfg = _cfg(hub=hub)
    repo_args = repo or ["all"]
    selected = _discover_mail_repos(repo_args, cfg)
    result = diagnose_mail_dirty_state(
        cfg.repo_root,
        selected,
        repo_policies=cfg.mail_repos,
    )
    result["delivery_policy"] = _mail_delivery_policy_summary(selected, cfg.mail_repos)
    if repo_args == ["all"]:
        coverage = _mailbox_coverage_summary(
            cfg,
            selected,
            include_local_paths=include_local_paths,
        )
        result["mailbox_coverage"] = coverage
        if isinstance(result.get("repo_scope"), dict):
            result["repo_scope"]["mailbox_coverage_warning"] = coverage["warning"]
            result["repo_scope"]["unreviewed_mailbox_candidate_count"] = coverage[
                "unreviewed_mailbox_candidate_count"
            ]
            result["repo_scope"]["reviewed_enabled_not_checked_count"] = coverage[
                "reviewed_enabled_not_checked_count"
            ]
        if coverage["warning"]:
            result["action_summary"]["next_actions"].append(
                "Classify unreviewed mailbox candidates before treating --repo all as complete."
            )
    _annotate_mail_storm_scope(result, requested_all=repo_args == ["all"])
    result["dirty_state_fingerprint"] = _mail_dirty_state_fingerprint(result)
    operation_key = _mail_storm_operation_key(operation)
    gate = _mail_storm_gate_report(
        result,
        repo_args=repo_args,
        requested_operation=operation_key,
    )
    plan = _mail_storm_repair_plan_report(
        result,
        gate=gate,
        repo_args=repo_args,
        requested_operation=operation_key,
    )
    if write_report:
        plan["report_write"] = _write_mail_repair_plan_packet(cfg.repo_root, plan)
    console.print_json(data=plan)
    if fail_on_blocked and not plan["selected_operation_safe"]:
        raise typer.Exit(1)


@mail_app.command("doctor")
def mail_doctor(
    repo: list[str] = typer.Option([], "--repo"),
    repair_stale_locks: bool = typer.Option(
        False,
        "--repair-stale-locks",
        help="Remove only stale, dead-owner, or same-process leftover JSONL locks.",
    ),
    repair_temp_fragments: bool = typer.Option(
        False,
        "--repair-temp-fragments",
        help="Remove stale atomic JSON temp fragments from mail spools.",
    ),
    stale_lock_seconds: float = typer.Option(300.0, "--stale-lock-seconds", min=1.0),
    fail_on_dirty: bool = typer.Option(False, "--fail-on-dirty"),
    fail_on_worktree_dirty: bool = typer.Option(
        False,
        "--fail-on-worktree-dirty",
        help=(
            "Exit non-zero when the DAD git worktree has changes. This is separate from "
            "--fail-on-dirty, which only covers mail spool and staged-packet hazards."
        ),
    ),
    fail_on_coverage_gap: bool = typer.Option(
        False,
        "--fail-on-coverage-gap",
        help=(
            "Exit non-zero when --repo all finds unreviewed mailbox candidates outside "
            "reviewed mail.repos coverage. This is stricter than --fail-on-dirty."
        ),
    ),
    summary_only: bool = typer.Option(
        False,
        "--summary-only",
        help="Print compact operator status without long issue/observation arrays.",
    ),
    include_local_paths: bool = typer.Option(
        False,
        "--include-local-paths",
        help="Include exact local paths in mailbox coverage output for local operator debugging.",
    ),
    allowlist_legacy_central_inbox: bool = typer.Option(
        False,
        "--allowlist-legacy-central-inbox",
        help=(
            "Write reviewed legacy allowlist rows for pre-enforcement central inbox "
            "records that lack collection-audit hashes."
        ),
    ),
    allowlist_legacy_repo_inbox: bool = typer.Option(
        False,
        "--allowlist-legacy-repo-inbox",
        help=(
            "Write reviewed legacy allowlist rows for repo inbox records that have only "
            "pre-hash delivery-log evidence. Rows are keyed by mail_id, dedupe_key, "
            "current record hash, and target repo."
        ),
    ),
    quarantine_invalid_packets: bool = typer.Option(
        False,
        "--quarantine-invalid-packets",
        help=(
            "Write hash-bound quarantine acknowledgements for invalid source outbox rows "
            "reported by the doctor. Does not validate, deliver, or delete the rows."
        ),
    ),
    legacy_allowlist_ack: Optional[str] = typer.Option(
        None,
        "--legacy-allowlist-ack",
        help=(
            "Required reason/reviewer note when --allowlist-legacy-central-inbox or "
            "--allowlist-legacy-repo-inbox is used."
        ),
    ),
    invalid_quarantine_ack: Optional[str] = typer.Option(
        None,
        "--invalid-quarantine-ack",
        help="Required reason/reviewer note when --quarantine-invalid-packets is used.",
    ),
    repair_route_audit: bool = typer.Option(
        False,
        "--repair-route-audit",
        help=(
            "Write route audit repair rows only when an existing routed row exactly "
            "matches a derived route from a collected central inbox row."
        ),
    ),
    route_audit_repair_ack: Optional[str] = typer.Option(
        None,
        "--route-audit-repair-ack",
        help="Required reason/reviewer note when --repair-route-audit is used.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Diagnose dirty DAD mail spools and staged Rust rollout packets."""
    cfg = _cfg(hub=hub)
    selected = _discover_mail_repos(repo, cfg) if repo else []
    result = diagnose_mail_dirty_state(
        cfg.repo_root,
        selected,
        repo_policies=cfg.mail_repos,
        repair_stale_locks=repair_stale_locks,
        repair_temp_fragments=repair_temp_fragments,
        stale_lock_seconds=stale_lock_seconds,
    )
    if repo == ["all"]:
        coverage = _mailbox_coverage_summary(
            cfg,
            selected,
            include_local_paths=include_local_paths,
        )
        result["mailbox_coverage"] = coverage
        if isinstance(result.get("repo_scope"), dict):
            result["repo_scope"]["mailbox_coverage_warning"] = coverage["warning"]
            result["repo_scope"]["unreviewed_mailbox_candidate_count"] = coverage[
                "unreviewed_mailbox_candidate_count"
            ]
            result["repo_scope"]["reviewed_enabled_not_checked_count"] = coverage[
                "reviewed_enabled_not_checked_count"
            ]
        if coverage["warning"]:
            result["action_summary"]["next_actions"].append(
                "Run mail discover-repos and add reviewed mail.repos entries for any "
                "persistent repos whose outboxes DAD should collect."
            )
    legacy_allowlist_result: dict[str, object] | None = None
    if allowlist_legacy_central_inbox:
        ack = (legacy_allowlist_ack or "").strip()
        if not ack:
            console.print_json(
                data={
                    "schema_version": "dad_mail_legacy_allowlist_gate.v1",
                    "blocked": True,
                    "required_ack": "--legacy-allowlist-ack",
                    "authority_boundary": (
                        "Legacy central inbox allowlisting is an operator migration action. "
                        "It does not approve delivery, adoption, or public release."
                    ),
                }
            )
            raise typer.Exit(2)
        allowlist_path = (
            cfg.repo_root / "processed" / "mail" / "archive" / "legacy_collection_allowlist.jsonl"
        )
        allowlisted = 0
        for issue in result.get("issues", []):
            if issue.get("issue_type") != "central_inbox_missing_collection_audit":
                continue
            if not issue.get("collected_at"):
                continue
            append_jsonl_locked(
                allowlist_path,
                {
                    "schema_version": "dad_mail_legacy_collection_allowlist.v1",
                    "event_type": "legacy_collection_allowlisted",
                    "created_at": utc_now(),
                    "mail_id": str(issue.get("mail_id", "")),
                    "dedupe_key": str(issue.get("dedupe_key", "")),
                    "record_hash": str(issue.get("record_hash", "")),
                    "review_status": "reviewed_legacy",
                    "reviewed_by": "operator",
                    "reason": ack,
                    "source_issue_path": str(issue.get("path", "")),
                    "authority_boundary": (
                        "Allowlist only preserves pre-enforcement central inbox evidence. "
                        "It does not approve delivery, adoption, or public release."
                    ),
                },
            )
            allowlisted += 1
        legacy_allowlist_result = {
            "schema_version": "dad_mail_legacy_allowlist_result.v1",
            "allowlisted_count": allowlisted,
            "allowlist_path": str(allowlist_path),
            "ack": ack,
        }
        result = diagnose_mail_dirty_state(
            cfg.repo_root,
            selected,
            repo_policies=cfg.mail_repos,
            repair_stale_locks=False,
            repair_temp_fragments=False,
            stale_lock_seconds=stale_lock_seconds,
        )
        if repo == ["all"]:
            coverage = _mailbox_coverage_summary(
                cfg,
                selected,
                include_local_paths=include_local_paths,
            )
            result["mailbox_coverage"] = coverage
            if isinstance(result.get("repo_scope"), dict):
                result["repo_scope"]["mailbox_coverage_warning"] = coverage["warning"]
                result["repo_scope"]["unreviewed_mailbox_candidate_count"] = coverage[
                    "unreviewed_mailbox_candidate_count"
                ]
                result["repo_scope"]["reviewed_enabled_not_checked_count"] = coverage[
                    "reviewed_enabled_not_checked_count"
                ]
        result["legacy_allowlist_result"] = legacy_allowlist_result
    legacy_delivery_allowlist_result: dict[str, object] | None = None
    if allowlist_legacy_repo_inbox:
        ack = (legacy_allowlist_ack or "").strip()
        if not ack:
            console.print_json(
                data={
                    "schema_version": "dad_mail_legacy_delivery_allowlist_gate.v1",
                    "blocked": True,
                    "required_ack": "--legacy-allowlist-ack",
                    "authority_boundary": (
                        "Legacy repo inbox delivery allowlisting is an operator migration "
                        "action. It does not approve delivery, adoption, public release, or "
                        "future direct inbox writes."
                    ),
                }
            )
            raise typer.Exit(2)
        allowlist_path = legacy_delivery_allowlist_path(cfg.repo_root)
        allowlisted = 0
        skipped = 0
        for issue in result.get("issues", []):
            if issue.get("issue_type") != "repo_inbox_without_delivery_log":
                continue
            if not issue.get("legacy_delivery_log_present"):
                skipped += 1
                continue
            append_jsonl_locked(
                allowlist_path,
                {
                    "schema_version": "dad_mail_legacy_delivery_allowlist.v1",
                    "event_type": "legacy_delivery_allowlisted",
                    "created_at": utc_now(),
                    "mail_id": str(issue.get("mail_id", "")),
                    "dedupe_key": str(issue.get("dedupe_key", "")),
                    "record_hash": str(issue.get("record_hash", "")),
                    "target_repo": str(issue.get("expected_target_repo", "")),
                    "review_status": "reviewed_legacy",
                    "reviewed_by": "operator",
                    "reason": ack,
                    "source_issue_path": str(issue.get("path", "")),
                    "authority_boundary": (
                        "Allowlist only preserves reviewed pre-hash repo inbox delivery "
                        "evidence for this exact row hash and target repo. It does not "
                        "approve adoption, public release, or future direct inbox writes."
                    ),
                },
            )
            allowlisted += 1
        legacy_delivery_allowlist_result = {
            "schema_version": "dad_mail_legacy_delivery_allowlist_result.v1",
            "allowlisted_count": allowlisted,
            "skipped_non_legacy_count": skipped,
            "allowlist_path": str(allowlist_path),
            "ack": ack,
        }
        result = diagnose_mail_dirty_state(
            cfg.repo_root,
            selected,
            repo_policies=cfg.mail_repos,
            repair_stale_locks=False,
            repair_temp_fragments=False,
            stale_lock_seconds=stale_lock_seconds,
        )
        if repo == ["all"]:
            coverage = _mailbox_coverage_summary(
                cfg,
                selected,
                include_local_paths=include_local_paths,
            )
            result["mailbox_coverage"] = coverage
            if isinstance(result.get("repo_scope"), dict):
                result["repo_scope"]["mailbox_coverage_warning"] = coverage["warning"]
                result["repo_scope"]["unreviewed_mailbox_candidate_count"] = coverage[
                    "unreviewed_mailbox_candidate_count"
                ]
                result["repo_scope"]["reviewed_enabled_not_checked_count"] = coverage[
                    "reviewed_enabled_not_checked_count"
                ]
        if legacy_allowlist_result:
            result["legacy_allowlist_result"] = legacy_allowlist_result
        result["legacy_delivery_allowlist_result"] = legacy_delivery_allowlist_result
    invalid_quarantine_result: dict[str, object] | None = None
    if quarantine_invalid_packets:
        ack = (invalid_quarantine_ack or "").strip()
        if not ack:
            console.print_json(
                data={
                    "schema_version": "dad_mail_invalid_packet_quarantine_gate.v1",
                    "blocked": True,
                    "required_ack": "--invalid-quarantine-ack",
                    "authority_boundary": (
                        "Invalid source-outbox quarantine is an operator triage action. "
                        "It does not validate the row, deliver it, adopt it, or delete it "
                        "from the source repo outbox."
                    ),
                }
            )
            raise typer.Exit(2)
        quarantine_path = invalid_mail_quarantine_path(cfg.repo_root)
        quarantined = 0
        skipped = 0
        for issue in result.get("issues", []):
            if issue.get("issue_type") != "invalid_mail_packet":
                continue
            if issue.get("stage") != "repo_mirror_outbox":
                skipped += 1
                continue
            append_jsonl_locked(
                quarantine_path,
                {
                    "schema_version": "dad_mail_invalid_packet_quarantine.v1",
                    "event_type": "invalid_mail_packet",
                    "created_at": utc_now(),
                    "path": str(issue.get("path", "")),
                    "stage": str(issue.get("stage", "")),
                    "mail_id": str(issue.get("mail_id", "")),
                    "dedupe_key": str(issue.get("dedupe_key", "")),
                    "record_hash": str(issue.get("record_hash", "")),
                    "review_status": "reviewed_quarantine",
                    "reviewed_by": "operator",
                    "reason": ack,
                    "raw_payload_copied": False,
                    "authority_boundary": (
                        "This hash-bound quarantine isolates an invalid source-outbox row "
                        "without copying raw payload content. It does not make the row valid "
                        "mail and does not authorize delivery, adoption, or public release."
                    ),
                },
            )
            quarantined += 1
        invalid_quarantine_result = {
            "schema_version": "dad_mail_invalid_packet_quarantine_result.v1",
            "quarantined_count": quarantined,
            "skipped_non_source_outbox_count": skipped,
            "quarantine_path": str(quarantine_path),
            "ack": ack,
        }
        result = diagnose_mail_dirty_state(
            cfg.repo_root,
            selected,
            repo_policies=cfg.mail_repos,
            repair_stale_locks=False,
            repair_temp_fragments=False,
            stale_lock_seconds=stale_lock_seconds,
        )
        if repo == ["all"]:
            coverage = _mailbox_coverage_summary(
                cfg,
                selected,
                include_local_paths=include_local_paths,
            )
            result["mailbox_coverage"] = coverage
            if isinstance(result.get("repo_scope"), dict):
                result["repo_scope"]["mailbox_coverage_warning"] = coverage["warning"]
                result["repo_scope"]["unreviewed_mailbox_candidate_count"] = coverage[
                    "unreviewed_mailbox_candidate_count"
                ]
                result["repo_scope"]["reviewed_enabled_not_checked_count"] = coverage[
                    "reviewed_enabled_not_checked_count"
                ]
        if legacy_allowlist_result:
            result["legacy_allowlist_result"] = legacy_allowlist_result
        if legacy_delivery_allowlist_result:
            result["legacy_delivery_allowlist_result"] = legacy_delivery_allowlist_result
        result["invalid_quarantine_result"] = invalid_quarantine_result
    route_audit_repair_result: dict[str, object] | None = None
    if repair_route_audit:
        ack = (route_audit_repair_ack or "").strip()
        if not ack:
            console.print_json(
                data={
                    "schema_version": "dad_mail_route_audit_repair_gate.v1",
                    "blocked": True,
                    "required_ack": "--route-audit-repair-ack",
                    "authority_boundary": (
                        "Route audit repair is an operator migration action. It does not "
                        "approve delivery, adoption, or public release."
                    ),
                }
            )
            raise typer.Exit(2)
        route_audit_repair_result = repair_route_audit_gaps(
            cfg.repo_root,
            repo_policies=cfg.mail_repos,
            operator_ack=ack,
        )
        result = diagnose_mail_dirty_state(
            cfg.repo_root,
            selected,
            repo_policies=cfg.mail_repos,
            repair_stale_locks=False,
            repair_temp_fragments=False,
            stale_lock_seconds=stale_lock_seconds,
        )
        if repo == ["all"]:
            coverage = _mailbox_coverage_summary(
                cfg,
                selected,
                include_local_paths=include_local_paths,
            )
            result["mailbox_coverage"] = coverage
            if isinstance(result.get("repo_scope"), dict):
                result["repo_scope"]["mailbox_coverage_warning"] = coverage["warning"]
                result["repo_scope"]["unreviewed_mailbox_candidate_count"] = coverage[
                    "unreviewed_mailbox_candidate_count"
                ]
                result["repo_scope"]["reviewed_enabled_not_checked_count"] = coverage[
                    "reviewed_enabled_not_checked_count"
                ]
        if legacy_allowlist_result:
            result["legacy_allowlist_result"] = legacy_allowlist_result
        if legacy_delivery_allowlist_result:
            result["legacy_delivery_allowlist_result"] = legacy_delivery_allowlist_result
        if invalid_quarantine_result:
            result["invalid_quarantine_result"] = invalid_quarantine_result
        result["route_audit_repair_result"] = route_audit_repair_result
    _annotate_mail_storm_scope(result, requested_all=repo == ["all"])
    result["dirty_state_fingerprint"] = _mail_dirty_state_fingerprint(result)
    if summary_only:
        result = {
            "schema_version": "dad_mail_dirty_state_summary.v1",
            "generated_at": result["generated_at"],
            "status": result["status"],
            "dirty": result["dirty"],
            "dirty_state_fingerprint": result["dirty_state_fingerprint"],
            "spool_dirty": result.get("spool_dirty", result["dirty"]),
            "worktree_dirty": result.get("worktree_dirty", False),
            "action_summary": result["action_summary"],
            "summary": result["summary"],
            "repo_scope": result.get("repo_scope", {}),
            "mailbox_coverage": result.get("mailbox_coverage", {}),
            "worktree_state": result.get("worktree_state", {}),
            "write_target_guidance": result["write_target_guidance"],
            "authority_boundary": result["authority_boundary"],
        }
        if legacy_allowlist_result:
            result["legacy_allowlist_result"] = legacy_allowlist_result
        if legacy_delivery_allowlist_result:
            result["legacy_delivery_allowlist_result"] = legacy_delivery_allowlist_result
        if invalid_quarantine_result:
            result["invalid_quarantine_result"] = invalid_quarantine_result
        if route_audit_repair_result:
            result["route_audit_repair_result"] = route_audit_repair_result
    console.print_json(data=result)
    if fail_on_dirty and result["dirty"]:
        raise typer.Exit(1)
    if fail_on_coverage_gap:
        coverage = result.get("mailbox_coverage", {})
        coverage_blocked = bool(
            int(coverage.get("unreviewed_mailbox_candidate_count", 0) or 0)
            or int(coverage.get("reviewed_enabled_not_checked_count", 0) or 0)
            or str(coverage.get("warning", "")).strip()
        )
        if coverage_blocked:
            raise typer.Exit(1)
    if fail_on_worktree_dirty:
        worktree = result.get("worktree_state", {})
        clean_verified = (
            bool(worktree.get("evaluated"))
            and bool(worktree.get("is_git_worktree"))
            and str(worktree.get("status", "")) == "clean"
        )
        if not clean_verified:
            raise typer.Exit(1)


@event_app.command("record")
def events_record(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    repo: Path = typer.Option(Path("."), "--repo"),
    event_type: str = typer.Option(..., "--type"),
    summary: Optional[str] = typer.Option(None, "--summary"),
    dedupe_key: Optional[str] = typer.Option(None, "--dedupe-key"),
    source_repo: Optional[str] = typer.Option(None, "--source-repo"),
    source_repo_id: str = typer.Option("", "--source-repo-id"),
    source_visibility: str = typer.Option("unknown", "--source-visibility"),
    target_repo: str = typer.Option("", "--target-repo"),
    target_repo_id: str = typer.Option("", "--target-repo-id"),
    target_visibility: str = typer.Option("unknown", "--target-visibility"),
    notice_id: str = typer.Option("", "--notice-id"),
    actionable: bool = typer.Option(False, "--actionable/--not-actionable"),
    response_state: str = typer.Option("not_applicable", "--response-state"),
    sensitivity: str = typer.Option("internal_metadata", "--sensitivity"),
    payload: list[str] = typer.Option([], "--payload"),
    payload_json: Optional[str] = typer.Option(None, "--payload-json"),
    payload_file: Optional[Path] = typer.Option(None, "--payload-file"),
    evidence: list[str] = typer.Option([], "--evidence"),
) -> None:
    """Append a repo-owned candidate event to .digital-asset/events/outbox.jsonl."""
    _cfg(config, hub)
    repo_path = repo.resolve()
    event_payload = _event_payload_options(
        payload,
        payload_json=payload_json,
        payload_file=payload_file,
    )
    if summary:
        event_payload.setdefault("summary", summary)
    source_label = source_repo or repo_path.name
    dedupe = dedupe_key or "|".join(
        [
            source_label,
            event_type,
            notice_id,
            summary or json_dumps(event_payload),
        ]
    )
    record = build_event_record(
        event_type=event_type,
        source_repo=source_label,
        source_repo_id=source_repo_id,
        source_visibility=source_visibility,
        target_repo=target_repo,
        target_repo_id=target_repo_id,
        target_visibility=target_visibility,
        notice_id=notice_id,
        actionable=actionable,
        response_state=response_state,
        sensitivity=sensitivity,
        dedupe_key=dedupe,
        payload=event_payload,
        evidence=evidence,
    )
    console.print_json(data=record_repo_event(repo_path, record))


@event_app.command("collect")
def events_collect(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    repo: list[str] = typer.Option(..., "--repo"),
) -> None:
    """Collect repo-local event outboxes into DAD central candidate state."""
    cfg = _cfg(config, hub)
    if repo == ["all"]:
        selected = _discover_mail_repos(repo, cfg, reviewed=True)
    else:
        selected = [_resolve_mail_repo(raw_repo, cfg) for raw_repo in repo]
    console.print_json(data=collect_events(cfg.repo_root, selected, repo_policies=cfg.mail_repos))


@event_app.command("report")
def events_report(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Refresh and print the central event pipeline report."""
    cfg = _cfg(config, hub)
    console.print_json(data=write_event_pipeline_report(cfg.repo_root))


@enroll_app.command("discover")
def enroll_discover(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Report configured and candidate repos without mutating targets."""
    cfg = _cfg(config, hub)
    console.print_json(data=discover_enrollment_candidates(cfg))


@enroll_app.command("plan")
def enroll_plan(
    repo: list[str] = typer.Option([], "--repo"),
    wave: str = typer.Option(..., "--wave"),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a reviewed-wave enrollment plan under processed/enrollment."""
    cfg = _cfg(config, hub)
    policies = _select_enrollment(repo, cfg, wave=wave)
    result = build_enrollment_plan(cfg.repo_root, policies, wave=wave, update=False)
    console.print_json(data=result)


@enroll_app.command("apply")
def enroll_apply(
    repo: str = typer.Option(..., "--repo"),
    approval_id: str = typer.Option(..., "--approval-id"),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Apply full DAD governance enrollment to one reviewed repo."""
    cfg = _cfg(config, hub)
    policy = _select_enrollment([repo], cfg)[0]
    try:
        result = apply_enrollment(
            cfg.repo_root,
            policy,
            approval_id=approval_id,
            update=False,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@enroll_app.command("update-plan")
def enroll_update_plan(
    repo: list[str] = typer.Option([], "--repo"),
    wave: str = typer.Option(..., "--wave"),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a reviewed-wave enrollment update plan under processed/enrollment."""
    cfg = _cfg(config, hub)
    policies = _select_enrollment(repo, cfg, wave=wave)
    result = build_enrollment_plan(cfg.repo_root, policies, wave=wave, update=True)
    console.print_json(data=result)


@enroll_app.command("update-apply")
def enroll_update_apply(
    repo: str = typer.Option(..., "--repo"),
    approval_id: str = typer.Option(..., "--approval-id"),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Apply a reviewed DAD enrollment update to one repo."""
    cfg = _cfg(config, hub)
    policy = _select_enrollment([repo], cfg)[0]
    try:
        result = apply_enrollment(
            cfg.repo_root,
            policy,
            approval_id=approval_id,
            update=True,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@enroll_app.command("status")
def enroll_status(
    repo: list[str] = typer.Option(["all"], "--repo"),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Show enrollment contract and daily/weekly freshness status."""
    cfg = _cfg(config, hub)
    policies = cfg.enrollment_repos if repo == ["all"] else _select_enrollment(repo, cfg)
    console.print_json(data=enrollment_status_all(policies))


@dad_app.command("needs")
def dad_needs(hub: Optional[Path] = typer.Option(None)) -> None:
    """Show what DAD wants repos to send back through candidate mail."""
    cfg = _cfg(hub=hub)
    console.print_json(data=load_needs(cfg.repo_root))


@dad_app.command("offerings")
def dad_offerings(hub: Optional[Path] = typer.Option(None)) -> None:
    """Show DAD's richer asset, skill, template, harness, and map catalog."""
    cfg = _cfg(hub=hub)
    console.print_json(data=load_offerings(cfg.repo_root))


@dad_app.command("match")
def dad_match(
    repo: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option("", "--task"),
    limit: int = typer.Option(10, min=1, max=50),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Match a repo context to DAD offerings with deterministic candidate scoring."""
    cfg = _cfg(hub=hub)
    try:
        result = match_repo_offerings(cfg.repo_root, repo.resolve(), task=task, limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@dad_app.command("inventory")
def dad_inventory(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    max_depth: int = typer.Option(5, "--max-depth", min=1, max=12),
    github_repositories_file: Optional[Path] = typer.Option(
        None,
        "--github-repositories-file",
        help=(
            "Reviewed GitHub metadata JSON/YAML file to use for this inventory run. "
            "Rows are central candidate records only."
        ),
    ),
    github_source_id: str = typer.Option(
        "",
        "--github-source-id",
        help=(
            "Source id to attach to --github-repositories-file; defaults to the "
            "only configured GitHub source or github-reviewed-export."
        ),
    ),
    github_owner: str = typer.Option(
        "",
        "--github-owner",
        help="Owner for --github-repositories-file when it cannot be inferred from rows.",
    ),
) -> None:
    """Write central-only repo inventory reconciliation reports."""
    cfg = _cfg(config, hub)
    github_sources = cfg.github_sources
    if github_repositories_file is not None:
        source_id = github_source_id.strip()
        if not source_id:
            source_id = (
                cfg.github_sources[0].id
                if len(cfg.github_sources) == 1
                else "github-reviewed-export"
            )
        try:
            github_sources = _github_sources_with_reviewed_file(
                cfg,
                repositories_file=github_repositories_file,
                source_id=source_id,
                owner=github_owner.strip(),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    try:
        result = reconcile_repo_inventory(
            cfg.repo_root,
            local_sources=cfg.local_sources,
            github_sources=github_sources,
            mail_policies=cfg.mail_repos,
            enrollment_policies=cfg.enrollment_repos,
            max_depth=max_depth,
        )
    except (OSError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@dad_app.command("cadence-plan")
def dad_cadence_plan(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write the daily mail and weekly library/check cadence plan."""
    cfg = _cfg(config, hub)
    try:
        result = build_dad_cadence_plan(
            cfg.repo_root,
            mail_policies=cfg.mail_repos,
            enrollment_policies=cfg.enrollment_repos,
        )
    except (OSError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@dad_app.command("asset-recognition")
def dad_asset_recognition(hub: Optional[Path] = typer.Option(None)) -> None:
    """Show the methodology DAD uses to recognize useful digital assets."""
    cfg = _cfg(hub=hub)
    console.print_json(data=load_asset_recognition_methodology(cfg.repo_root))


@dad_app.command("address-model")
def dad_address_model(hub: Optional[Path] = typer.Option(None)) -> None:
    """Show DAD's adopted 9-layer address model and source inspirations."""
    cfg = _cfg(hub=hub)
    console.print_json(data=load_address_model_registry(cfg.repo_root))


@dad_app.command("repo-asset-standard")
def dad_repo_asset_standard(hub: Optional[Path] = typer.Option(None)) -> None:
    """Show the canonical repo-local digital asset directory/log standard."""
    _cfg(hub=hub)
    console.print_json(data=repo_local_asset_surface_standard())


@dad_app.command("repo-assets")
def dad_repo_assets(
    repo: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option("", "--task"),
    limit: int = typer.Option(25, min=1, max=100),
    include_legacy: bool = typer.Option(True, "--include-legacy/--no-legacy"),
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Collect repo-local digital asset memory as metadata-only candidate evidence."""
    cfg = _cfg(config, hub)
    try:
        result = collect_repo_local_assets(
            cfg.repo_root,
            repo.resolve(),
            task=task,
            limit=limit,
            include_legacy=include_legacy,
            mail_policies=cfg.mail_repos,
            enrollment_policies=cfg.enrollment_repos,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@dad_app.command("offer-check")
def dad_offer_check(
    name: str = typer.Option(..., "--name"),
    path: str = typer.Option("", "--path"),
    version: str = typer.Option("", "--version"),
    capability: list[str] = typer.Option([], "--capability"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Check a proposed offering against the registry for duplicate vs upgrade before registering."""
    cfg = _cfg(hub=hub)
    try:
        result = check_offering_novelty(
            cfg.repo_root,
            name=name,
            path=path,
            version=version,
            capabilities=capability,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@dad_app.command("patterns")
def dad_patterns(
    repo: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option("", "--task"),
    limit: int = typer.Option(3, min=1, max=10),
    full: bool = typer.Option(
        False, "--full", help="Print the full pattern registry instead of matches."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Show high-value asset-pattern cards matched to a repo/task, or the full registry."""
    cfg = _cfg(hub=hub)
    try:
        if full:
            console.print_json(data=load_asset_patterns(cfg.repo_root))
            return
        result = match_asset_patterns(
            cfg.repo_root,
            task=task,
            repo=repo.resolve(),
            limit=limit,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@dad_app.command("calibration")
def dad_calibration(
    minimum_n: int = typer.Option(10, "--minimum-n", min=1),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Join preflight decision traces to postflight outcomes without overclaiming small samples."""
    cfg = _cfg(hub=hub)
    console.print_json(data=calibration_report(cfg.repo_root, minimum_n=minimum_n))


@dad_app.command("unavailable-ack")
def dad_unavailable_ack(
    operation: str = typer.Option(..., "--operation"),
    reason: str = typer.Option(..., "--reason"),
    reviewed_by: str = typer.Option("human", "--reviewed-by"),
    audit_output: Optional[Path] = typer.Option(
        None,
        "--audit-output",
        help=(
            "Optional local JSONL audit output. Used directly when the DAD hub cannot be resolved."
        ),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Record a named DAD-unavailable bypass for a hard-gated operation."""
    reviewer = reviewed_by.strip()
    if reviewer.casefold() in {"", "human", "unknown", "agent", "codex", "claude", "ai"}:
        console.print("--reviewed-by must name the human who approved this bypass.")
        raise typer.Exit(2)
    hub_resolution = describe_hub_resolution(explicit_hub=hub)
    record = {
        "event_type": "dad_unavailable_ack",
        "created_at": utc_now(),
        "operation": operation,
        "reason": reason,
        "reviewed_by": reviewer,
        "hub_available": bool(hub_resolution.get("resolved")),
        "audit_scope": "hub" if hub_resolution.get("resolved") else "user_local",
        "authority_boundary": "Bypass acknowledgement is an audit record, not blanket approval.",
    }
    if hub_resolution.get("resolved"):
        cfg = _cfg(hub=Path(str(hub_resolution["hub_path"])))
        audit_path = cfg.repo_root / "audit" / "events" / f"{record['created_at'][:10]}.jsonl"
    else:
        audit_path = audit_output or Path.home() / ".dad" / "audit" / "unavailable-acks.jsonl"
        record["hub_error"] = hub_resolution.get("error", "DAD hub unavailable.")
    append_jsonl(audit_path, record)
    console.print_json(data=record)


@dad_app.command("asset-scout")
def dad_asset_scout(
    repo: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option("", "--task"),
    limit: int = typer.Option(25, min=1, max=100),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a path/metadata-only candidate asset recognition report for a repo."""
    cfg = _cfg(hub=hub)
    try:
        result = scout_asset_candidates(cfg.repo_root, repo.resolve(), task=task, limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@usage_app.command("record")
def usage_record(
    repo: Path = typer.Option(Path("."), "--repo"),
    asset: str = typer.Option(..., "--asset"),
    status: str = typer.Option(..., "--status"),
    recorded_by: str = typer.Option("unknown", "--recorded-by"),
    source_ref: str = typer.Option("", "--source-ref"),
    reason: str = typer.Option("", "--reason"),
    mail_id: str = typer.Option("", "--mail-id"),
    adoption_id: str = typer.Option("", "--adoption-id"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Record that a repo uses, watches, rejects, or retired a DAD asset."""
    cfg = _cfg(hub=hub)
    try:
        result = record_usage(
            cfg.repo_root,
            repo.resolve(),
            asset_id=asset,
            status=status,
            recorded_by=recorded_by,
            source_ref=source_ref,
            reason=reason,
            mail_id=mail_id,
            adoption_id=adoption_id,
            mail_policies=cfg.mail_repos,
            enrollment_policies=cfg.enrollment_repos,
        )
    except (OSError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@usage_app.command("upgrades")
def usage_upgrades_command(
    repo: Path = typer.Option(Path("."), "--repo"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Show candidate upgrade notices for assets a repo uses or watches."""
    cfg = _cfg(hub=hub)
    try:
        result = usage_upgrades(
            cfg.repo_root,
            repo.resolve(),
            mail_policies=cfg.mail_repos,
            enrollment_policies=cfg.enrollment_repos,
        )
    except (OSError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@harness_app.command("list")
def harness_list(hub: Optional[Path] = typer.Option(None)) -> None:
    """List DAD coding-improvement harnesses."""
    cfg = _cfg(hub=hub)
    console.print_json(data=list_harnesses(cfg.repo_root))


@harness_app.command("recommend")
def harness_recommend(
    repo: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option("", "--task"),
    limit: int = typer.Option(5, min=1, max=25),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Recommend coding harnesses for a repo and task."""
    cfg = _cfg(hub=hub)
    try:
        result = recommend_harnesses(cfg.repo_root, repo.resolve(), task=task, limit=limit)
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@harness_app.command("discovery-methodology")
def harness_discovery_methodology(hub: Optional[Path] = typer.Option(None)) -> None:
    """Show the radar methodology for finding new coding harness opportunities."""
    cfg = _cfg(hub=hub)
    console.print_json(data=load_harness_discovery_methodology(cfg.repo_root))


@harness_app.command("discover")
def harness_discover_command(
    repo: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option("", "--task"),
    limit: int = typer.Option(10, min=1, max=50),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a candidate harness-opportunity discovery report for a repo."""
    cfg = _cfg(hub=hub)
    try:
        result = discover_harness_opportunities(
            cfg.repo_root,
            repo.resolve(),
            task=task,
            limit=limit,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@harness_app.command("research")
def harness_research_command(
    harness: str = typer.Option(..., "--harness"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a candidate research packet for a harness."""
    cfg = _cfg(hub=hub)
    try:
        result = harness_research(cfg.repo_root, harness)
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@harness_app.command("evaluate")
def harness_evaluate_command(
    harness: str = typer.Option(..., "--harness"),
    repo: Path = typer.Option(Path("."), "--repo"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a candidate harness fit report for a repo."""
    cfg = _cfg(hub=hub)
    try:
        result = harness_evaluate(cfg.repo_root, harness, repo.resolve())
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@harness_app.command("package")
def harness_package_command(
    harness: str = typer.Option(..., "--harness"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Package a DAD coding harness under processed/harnesses."""
    cfg = _cfg(hub=hub)
    try:
        result = harness_package(cfg.repo_root, harness)
    except (OSError, ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("paths")
def exceptions_paths() -> None:
    """Show repo-local and DAD-central exception lake paths."""
    console.print_json(data=exception_lake_paths())


@exceptions_app.command("taxonomy")
def exceptions_taxonomy(hub: Optional[Path] = typer.Option(None)) -> None:
    """Print the reviewed exception event type registry."""
    cfg = _cfg(hub=hub)
    console.print_json(data=load_event_type_registry(cfg.repo_root))


@exceptions_app.command("capture-patterns")
def exceptions_capture_patterns(hub: Optional[Path] = typer.Option(None)) -> None:
    """Print DAD's deterministic exception/mail capture-pattern registry."""
    cfg = _cfg(hub=hub)
    console.print_json(data=load_capture_pattern_registry(cfg.repo_root))


@exceptions_app.command("capture-suggest")
def exceptions_capture_suggest(
    signal: list[str] = typer.Option(
        [],
        "--signal",
        help="Observable metadata signal, repeat for multiple signals.",
    ),
    repo_capture_surface_version: str = typer.Option(
        "",
        "--repo-capture-surface-version",
        help="Capture surface version recorded in the source repo contract.",
    ),
    payload_sample: list[str] = typer.Option(
        [],
        "--payload-sample",
        help=(
            "Short metadata-only local sample to screen. Do not pass secrets, "
            "raw logs, private rows, copied conversations, or source blobs."
        ),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Suggest candidate exception/mail/fix packets for observable signals."""
    cfg = _cfg(hub=hub)
    samples = [
        {"field": f"cli_payload_sample_{index}", "text": text}
        for index, text in enumerate(payload_sample, start=1)
    ]
    try:
        result = suggest_exception_capture(
            cfg.repo_root,
            signals=signal,
            repo_capture_surface_version=repo_capture_surface_version,
            payload_samples=samples,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("taxonomy-coverage")
def exceptions_taxonomy_coverage(
    scenarios: Path = typer.Option(
        Path(
            "assets/coding-harnesses/exception-capture-completeness/examples/"
            "synthetic-capture-scenarios.json"
        ),
        "--scenarios",
    ),
    output: Optional[Path] = typer.Option(None, "--output"),
    fail_on_unrouted: bool = typer.Option(False, "--fail-on-unrouted"),
    fail_on_missing_scenarios: bool = typer.Option(False, "--fail-on-missing-scenarios"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Report event taxonomy coverage by direct, capture-rule, and backfill routes."""
    cfg = _cfg(hub=hub)
    scenario_path = scenarios if scenarios.is_absolute() else cfg.repo_root / scenarios
    try:
        result = evaluate_exception_taxonomy_coverage(
            cfg.repo_root,
            scenario_path,
            output=output,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    if fail_on_unrouted and (
        result.get("reviewed_unrouted_event_types") or result.get("learnable_unrouted_event_types")
    ):
        raise typer.Exit(1)
    missing_scenarios = result.get("routed_events_missing_synthetic_cases") or result.get(
        "capture_rule_events_missing_synthetic_cases"
    )
    if fail_on_missing_scenarios and missing_scenarios:
        raise typer.Exit(1)


@exceptions_app.command("capture-check")
def exceptions_capture_check(
    scenarios: Path = typer.Option(..., "--scenarios"),
    output: Optional[Path] = typer.Option(None, "--output"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run synthetic capture-completeness scenarios against DAD capture rules."""
    cfg = _cfg(hub=hub)
    scenario_path = scenarios if scenarios.is_absolute() else cfg.repo_root / scenarios
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = evaluate_capture_scenarios(
            cfg.repo_root,
            scenario_path,
            output=output_path,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    if (
        result["failed_count"]
        or result["missing_required_pattern_families"]
        or result.get("missing_reviewed_rule_ids")
        or result.get("undeclared_matched_rule_ids")
        or result.get("unknown_declared_rule_ids")
    ):
        raise typer.Exit(1)


@exceptions_app.command("capture-simulate-emission")
def exceptions_capture_simulate_emission(
    scenarios: Path = typer.Option(
        Path(
            "assets/coding-harnesses/exception-capture-completeness/examples/"
            "synthetic-capture-scenarios.json"
        ),
        "--scenarios",
    ),
    output: Optional[Path] = typer.Option(None, "--output"),
    limit: Optional[int] = typer.Option(None, "--limit", min=1),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Prove capture-suggest can emit real temp-repo packets observed-check accepts."""
    cfg = _cfg(hub=hub)
    scenario_path = scenarios if scenarios.is_absolute() else cfg.repo_root / scenarios
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_exception_capture_emission_simulation(
            cfg.repo_root,
            scenario_path,
            output=output_path,
            limit=limit,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    if result["failed_count"] or result["case_count"] == 0:
        raise typer.Exit(1)


@exceptions_app.command("phase6-summary")
def exceptions_phase6_summary(
    output: Optional[Path] = typer.Option(None, "--output"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Compile Phase 6 machine evidence into one human-review summary."""
    cfg = _cfg(hub=hub)
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_phase6_machine_evidence_summary(
            cfg.repo_root,
            output=output_path,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("capture-audit")
def exceptions_capture_audit(
    repo: list[str] = typer.Option([], "--repo"),
    root: list[Path] = typer.Option([], "--root"),
    limit: int = typer.Option(200, "--limit", min=1, max=1000),
    candidate_limit: int = typer.Option(
        50,
        "--candidate-limit",
        min=0,
        max=500,
        help="Maximum candidate path signals per repo; 0 means exhaustive metadata-only scan.",
    ),
    max_scanned_files: int = typer.Option(
        50000,
        "--max-scanned-files",
        min=1,
        max=1000000,
        help="Maximum repo files to inspect by path name for capture candidates.",
    ),
    output: Optional[Path] = typer.Option(None, "--output"),
    fail_on_gaps: bool = typer.Option(False, "--fail-on-gaps"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help=(
            "Also fail on type-present-but-uncorrelated and unverified emissions. "
            "Stale or unknown capture surfaces already fail with --fail-on-gaps."
        ),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Read repo outboxes and report missed exception/mail capture candidates."""
    cfg = _cfg(hub=hub)
    repos: dict[str, Path] = {}
    reviewed_policy_scope = bool(repo == ["all"] and not root)
    if repo:
        selected = _discover_exception_repos(repo, cfg, capture_audit=True)
        for item in selected:
            repos[str(item.resolve())] = item.resolve()
    for item in root:
        for discovered in discover_capture_audit_repos([item], limit=limit):
            repos[str(discovered.resolve())] = discovered.resolve()
            if len(repos) >= limit:
                break
    if not repos:
        current = Path(".").resolve()
        repos[str(current)] = current
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_observed_capture_audit(
            cfg.repo_root,
            list(repos.values())[:limit],
            repo_policies=_exception_repo_policies(cfg),
            output=output_path,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
            scope={
                "scope_id": "exceptions.repos:all" if reviewed_policy_scope else "ad_hoc",
                "scope_kind": "reviewed_exception_policy" if reviewed_policy_scope else "ad_hoc",
                "reviewed_policy_scope": reviewed_policy_scope,
                "expected_repo_count": len(repos),
                "audited_repo_count": min(len(repos), limit),
            },
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    gap_count = _capture_audit_gap_count(result, strict=strict)
    if fail_on_gaps and gap_count:
        raise typer.Exit(1)
    if strict and gap_count:
        raise typer.Exit(1)


@exceptions_app.command("backfill-readiness")
def exceptions_backfill_readiness(
    repo: list[str] = typer.Option([], "--repo"),
    candidate_limit: int = typer.Option(
        50,
        "--candidate-limit",
        min=0,
        max=500,
        help="Maximum candidate path signals per repo; 0 means exhaustive metadata-only scan.",
    ),
    max_scanned_files: int = typer.Option(
        50000,
        "--max-scanned-files",
        min=1,
        max=1000000,
        help="Maximum repo files to inspect by path name for capture candidates.",
    ),
    output: Optional[Path] = typer.Option(None, "--output"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a central readiness matrix for safe historical exception backfill."""
    cfg = _cfg(hub=hub)
    selected = _discover_exception_repos(
        repo or ["all"],
        cfg,
        capture_audit=True,
        reviewed=True,
    )
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_exception_backfill_readiness(
            cfg.repo_root,
            selected,
            repo_policies=_exception_repo_policies(cfg),
            output=output_path,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("backfill-plan")
def exceptions_backfill_plan(
    repo: list[str] = typer.Option([], "--repo"),
    candidate_limit: int = typer.Option(
        50,
        "--candidate-limit",
        min=0,
        max=500,
        help="Maximum candidate path signals per repo; 0 means exhaustive metadata-only scan.",
    ),
    max_scanned_files: int = typer.Option(
        50000,
        "--max-scanned-files",
        min=1,
        max=1000000,
        help="Maximum repo files to inspect by path name for capture candidates.",
    ),
    per_wave_repo_limit: int = typer.Option(25, "--per-wave-repo-limit", min=1, max=500),
    output: Optional[Path] = typer.Option(None, "--output"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a planning-only review wave plan before historical backfill."""
    cfg = _cfg(hub=hub)
    selected = _discover_exception_repos(
        repo or ["all"],
        cfg,
        capture_audit=True,
        reviewed=True,
    )
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_exception_backfill_wave_plan(
            cfg.repo_root,
            selected,
            repo_policies=_exception_repo_policies(cfg),
            output=output_path,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
            per_wave_repo_limit=per_wave_repo_limit,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("capture-remediation-plan")
def exceptions_capture_remediation_plan(
    repo: list[str] = typer.Option([], "--repo"),
    candidate_limit: int = typer.Option(
        50,
        "--candidate-limit",
        min=0,
        max=500,
        help="Maximum candidate path signals per repo; 0 means exhaustive metadata-only scan.",
    ),
    max_scanned_files: int = typer.Option(
        50000,
        "--max-scanned-files",
        min=1,
        max=1000000,
        help="Maximum repo files to inspect by path name for capture candidates.",
    ),
    per_lane_repo_limit: int = typer.Option(25, "--per-lane-repo-limit", min=1, max=500),
    output: Optional[Path] = typer.Option(None, "--output"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a central-only remediation plan for exception capture gaps."""
    cfg = _cfg(hub=hub)
    selected = _discover_exception_repos(
        repo or ["all"],
        cfg,
        capture_audit=True,
        reviewed=True,
    )
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_exception_capture_remediation_plan(
            cfg.repo_root,
            selected,
            repo_policies=_exception_repo_policies(cfg),
            output=output_path,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
            per_lane_repo_limit=per_lane_repo_limit,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("capture-surface-refresh-notices")
def exceptions_capture_surface_refresh_notices(
    repo: list[str] = typer.Option([], "--repo"),
    candidate_limit: int = typer.Option(
        50,
        "--candidate-limit",
        min=0,
        max=500,
        help="Maximum candidate path signals per repo; 0 means exhaustive metadata-only scan.",
    ),
    max_scanned_files: int = typer.Option(
        50000,
        "--max-scanned-files",
        min=1,
        max=1000000,
        help="Maximum repo files to inspect by path name for capture candidates.",
    ),
    per_lane_repo_limit: int = typer.Option(500, "--per-lane-repo-limit", min=1, max=500),
    output: Optional[Path] = typer.Option(None, "--output"),
    write_mail: bool = typer.Option(
        True,
        "--write-mail/--no-write-mail",
        help=(
            "Write staged candidate mail to "
            "processed/mail/staged/capture_surface_refresh_notices.jsonl."
        ),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Stage central candidate notices for repos with stale exception capture surfaces."""
    cfg = _cfg(hub=hub)
    selected = _discover_exception_repos(
        repo or ["all"],
        cfg,
        capture_audit=True,
        reviewed=True,
    )
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_exception_capture_surface_refresh_notices(
            cfg.repo_root,
            selected,
            repo_policies=_exception_repo_policies(cfg),
            output=output_path,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
            per_lane_repo_limit=per_lane_repo_limit,
            write_mail=write_mail,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("capture-gap-review-queue")
def exceptions_capture_gap_review_queue(
    repo: list[str] = typer.Option([], "--repo"),
    candidate_limit: int = typer.Option(
        50,
        "--candidate-limit",
        min=0,
        max=500,
        help="Maximum candidate path signals per repo; 0 means exhaustive metadata-only scan.",
    ),
    max_scanned_files: int = typer.Option(
        50000,
        "--max-scanned-files",
        min=1,
        max=1000000,
        help="Maximum repo files to inspect by path name for capture candidates.",
    ),
    per_group_example_limit: int = typer.Option(5, "--per-group-example-limit", min=1, max=50),
    output: Optional[Path] = typer.Option(None, "--output"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Write a central-only review queue for observed capture gaps."""
    cfg = _cfg(hub=hub)
    selected = _discover_exception_repos(
        repo or ["all"],
        cfg,
        capture_audit=True,
        reviewed=True,
    )
    output_path = output if output is None or output.is_absolute() else output
    try:
        result = write_exception_capture_gap_review_queue(
            cfg.repo_root,
            selected,
            repo_policies=_exception_repo_policies(cfg),
            output=output_path,
            candidate_limit=candidate_limit,
            max_scanned_files=max_scanned_files,
            per_group_example_limit=per_group_example_limit,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("record")
def exceptions_record(
    repo: Path = typer.Option(Path("."), "--repo"),
    event_type: str = typer.Option(..., "--type"),
    summary: str = typer.Option(..., "--summary"),
    stage: str = typer.Option("midflight", "--stage"),
    severity: str = typer.Option("medium", "--severity"),
    capture_contract: str = typer.Option("failed_command", "--capture-contract"),
    agent: str = typer.Option("codex", "--agent"),
    source_visibility: Optional[str] = typer.Option(None, "--source-visibility"),
    command_arg: list[str] = typer.Option([], "--command-arg"),
    exit_code: Optional[int] = typer.Option(None, "--exit-code"),
    duration_ms: Optional[int] = typer.Option(None, "--duration-ms"),
    context_ref: list[str] = typer.Option([], "--context-ref"),
    validation_ref: list[str] = typer.Option([], "--validation-ref"),
    asset_ref: list[str] = typer.Option([], "--asset-ref"),
    harness_ref: list[str] = typer.Option([], "--harness-ref"),
    trace_ref: list[str] = typer.Option([], "--trace-ref"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Append a safe candidate exception packet to a repo-local exceptions outbox."""
    cfg = _cfg(hub=hub)
    policy_block_reason = _exception_record_policy_block_reason(cfg, repo.resolve())
    if policy_block_reason:
        raise typer.BadParameter(
            "exceptions record is blocked by reviewed exceptions.repos policy: "
            + policy_block_reason
        )
    try:
        result = record_exception_event(
            cfg.repo_root,
            repo.resolve(),
            event_type=event_type,
            summary=summary,
            stage=stage,
            severity=severity,
            capture_contract=capture_contract,
            agent=agent,
            source_visibility=source_visibility,
            command=command_arg,
            exit_code=exit_code,
            duration_ms=duration_ms,
            context_refs=context_ref,
            validation_refs=validation_ref,
            asset_refs=asset_ref,
            harness_refs=harness_ref,
            trace_refs=trace_ref,
            repo_policies=_exception_repo_policies(cfg),
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("fix")
def exceptions_fix(
    repo: Path = typer.Option(Path("."), "--repo"),
    event_id: str = typer.Option(..., "--event-id"),
    decision: str = typer.Option(..., "--decision"),
    summary: str = typer.Option(..., "--summary"),
    recorded_by: str = typer.Option("codex", "--recorded-by"),
    validation_ref: list[str] = typer.Option([], "--validation-ref"),
    regression_test_ref: list[str] = typer.Option([], "--regression-test-ref"),
    fix_ref: list[str] = typer.Option([], "--fix-ref"),
    asset_ref: list[str] = typer.Option([], "--asset-ref"),
    lesson_ref: list[str] = typer.Option([], "--lesson-ref"),
    owner_authority: str = typer.Option("", "--owner-authority"),
    canonical_event_id: str = typer.Option("", "--canonical-event-id"),
    expiry: str = typer.Option("", "--expiry"),
    remaining_risk: list[str] = typer.Option([], "--remaining-risk"),
    review_status: str = typer.Option("candidate", "--review-status"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Append a safe candidate fix outcome to a repo-local fix-outcome ledger."""
    cfg = _cfg(hub=hub)
    policy_block_reason = _exception_record_policy_block_reason(cfg, repo.resolve())
    if policy_block_reason:
        raise typer.BadParameter(
            "exceptions fix is blocked by reviewed exceptions.repos policy: " + policy_block_reason
        )
    try:
        result = record_exception_fix_outcome(
            cfg.repo_root,
            repo.resolve(),
            event_id=event_id,
            decision=decision,
            summary=summary,
            recorded_by=recorded_by,
            validation_refs=validation_ref,
            regression_test_refs=regression_test_ref,
            fix_refs=fix_ref,
            asset_refs=asset_ref,
            lesson_refs=lesson_ref,
            owner_authority=owner_authority,
            canonical_event_id=canonical_event_id,
            expiry=expiry,
            remaining_risks=remaining_risk,
            review_status=review_status,
            repo_policies=_exception_repo_policies(cfg),
        )
    except (ValueError, TypeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("collect")
def exceptions_collect(
    repo: list[str] = typer.Option([], "--repo"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Collect repo exception outboxes into DAD's central exception lake."""
    cfg = _cfg(hub=hub)
    repos = _discover_exception_repos(repo, cfg, collect=True, reviewed=True)
    event_results = []
    fix_outcome_results = []
    for item in repos:
        event_results.append(
            collect_exception_events(
                cfg.repo_root,
                item,
                repo_policies=_exception_repo_policies(cfg),
            )
        )
        fix_outcome_results.append(
            collect_exception_fix_outcomes(
                cfg.repo_root,
                item,
                repo_policies=_exception_repo_policies(cfg),
            )
        )
    report = write_exception_report(cfg.repo_root)
    console.print_json(
        data={
            "results": event_results,
            "fix_outcome_results": fix_outcome_results,
            "report": report,
            "authority_boundary": (
                "Exception records are candidate evidence. Collection never proves a fix, "
                "promotes a rule, or authorizes downstream repo mutation."
            ),
        }
    )


@exceptions_app.command("backfill")
def exceptions_backfill(
    root: Path = typer.Option(Path("."), "--root"),
    limit: int = typer.Option(200, "--limit", min=1, max=1000),
    per_repo_limit: int = typer.Option(50, "--per-repo-limit", min=1, max=1000),
    max_scanned_files: int = typer.Option(
        25_000,
        "--max-scanned-files",
        min=0,
        help="Stop after scanning this many eligible files. Use 0 for an unbounded walk.",
    ),
    include_path_refs: bool = typer.Option(
        False,
        "--include-path-refs",
        help=(
            "Include readable repo-relative path refs in central backfill events. "
            "Default is hash-only."
        ),
    ),
    approval_id: str = typer.Option(
        "",
        "--approval-id",
        help=("Reviewed approval id required for non-DAD backfill roots or readable path refs."),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Seed metadata-only historical exception candidates from path/name signals."""
    cfg = _cfg(hub=hub)
    root_resolved = root.resolve()
    dad_root = cfg.repo_root.resolve()
    try:
        root_inside_dad = root_resolved == dad_root or root_resolved.is_relative_to(dad_root)
    except AttributeError:
        root_inside_dad = root_resolved == dad_root or str(root_resolved).startswith(str(dad_root))
    approval_required = include_path_refs or not root_inside_dad
    if approval_required:
        approval_block_reason = _exception_backfill_approval_block_reason(
            cfg,
            root_resolved,
            approval_id,
        )
        if approval_block_reason:
            raise typer.BadParameter(
                "exceptions backfill needs a reviewed --approval-id: " + approval_block_reason
            )
    policy_block_reason = _exception_backfill_policy_block_reason(cfg, root_resolved)
    if policy_block_reason:
        approval_block_reason = _exception_backfill_approval_block_reason(
            cfg,
            root_resolved,
            approval_id,
        )
        if approval_block_reason:
            raise typer.BadParameter(
                "exceptions backfill is blocked by reviewed exceptions.repos policy: "
                + policy_block_reason
                + "; "
                + approval_block_reason
            )
    repo_policies = _exception_repo_policies(cfg)
    authorization = BackfillAuthorization(
        root=root_resolved,
        approval_id=approval_id.strip() if approval_required else "dad-self-backfill",
        include_path_refs=include_path_refs,
        repo_policies=repo_policies,
        approved_by="reviewed_policy" if approval_required else "dad_self",
        reason="exceptions backfill CLI request",
    )
    result = backfill_exception_candidates(
        cfg.repo_root,
        root_resolved,
        limit=limit,
        per_repo_limit=per_repo_limit,
        include_path_refs=include_path_refs,
        repo_policies=repo_policies,
        max_scanned_files=max_scanned_files,
        authorization=authorization,
    )
    console.print_json(data=result)


@exceptions_app.command("report")
def exceptions_report(hub: Optional[Path] = typer.Option(None)) -> None:
    """Regenerate and print the DAD exceptions lake report."""
    cfg = _cfg(hub=hub)
    console.print_json(data=write_exception_report(cfg.repo_root))


@exceptions_app.command("backfill-review-queue")
def exceptions_backfill_review_queue(
    output: Optional[Path] = typer.Option(None, "--output"),
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
    example_limit: int = typer.Option(5, "--example-limit", min=1, max=25),
    include_readable_path_refs: bool = typer.Option(
        False,
        "--include-readable-path-refs",
        help=(
            "Include readable repo-relative path refs that already exist in central "
            "backfill events. Default output remains hash-only."
        ),
    ),
    approval_id: str = typer.Option(
        "",
        "--approval-id",
        help=(
            "Reviewed exceptions.repos approval id required when emitting readable "
            "repo-relative path refs."
        ),
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Regenerate and print the source-review queue for backfill candidates."""
    cfg = _cfg(hub=hub)
    if include_readable_path_refs:
        approval_block_reason = _exception_backfill_review_queue_approval_block_reason(
            cfg,
            approval_id,
        )
        if approval_block_reason:
            raise typer.BadParameter(
                "exceptions backfill-review-queue needs a reviewed --approval-id: "
                + approval_block_reason
            )
    try:
        result = write_exception_backfill_review_queue(
            cfg.repo_root,
            output=output,
            limit=limit,
            example_limit=example_limit,
            include_readable_path_refs=include_readable_path_refs,
            readable_path_refs_authorized=include_readable_path_refs,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("backfill-refresh-plan")
def exceptions_backfill_refresh_plan(
    output: Optional[Path] = typer.Option(None, "--output"),
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
    example_limit: int = typer.Option(5, "--example-limit", min=1, max=25),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Regenerate and print the classifier refresh plan for backfill groups."""
    cfg = _cfg(hub=hub)
    try:
        result = write_exception_backfill_refresh_plan(
            cfg.repo_root,
            output=output,
            limit=limit,
            example_limit=example_limit,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("backfill-review-decision")
def exceptions_backfill_review_decision(
    review_group_id: str = typer.Option(..., "--review-group-id"),
    decision: str = typer.Option(
        ...,
        "--decision",
        help="confirm | reject | needs_source_packet | needs_classifier_refresh | defer | archive",
    ),
    reviewer: str = typer.Option("unknown", "--reviewer"),
    reviewer_type: str = typer.Option(
        "agent",
        "--reviewer-type",
        help="human | agent | source_repo | unknown",
    ),
    approval_id: str = typer.Option(
        "",
        "--approval-id",
        help="Required when --reviewer-type human.",
    ),
    source_packet_id: str = typer.Option(
        "",
        "--source-packet-id",
        help="Required when --reviewer-type source_repo.",
    ),
    notes: str = typer.Option("", "--notes"),
    evidence_ref: list[str] = typer.Option([], "--evidence-ref"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Append an audited source-review decision for a backfill review group."""
    cfg = _cfg(hub=hub)
    try:
        result = record_exception_backfill_review_decision(
            cfg.repo_root,
            review_group_id=review_group_id,
            decision=decision,
            reviewer=reviewer,
            reviewer_type=reviewer_type,
            approval_id=approval_id,
            source_packet_id=source_packet_id,
            notes=notes,
            evidence_refs=evidence_ref,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("backfill-review-decisions")
def exceptions_backfill_review_decisions(
    review_group_id: str = typer.Option("", "--review-group-id"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Summarize appended backfill review decisions."""
    cfg = _cfg(hub=hub)
    try:
        result = summarize_exception_backfill_review_decisions(
            cfg.repo_root,
            review_group_id=review_group_id,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("source-packet-opportunities")
def exceptions_source_packet_opportunities(
    output: Optional[Path] = typer.Option(None, "--output"),
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
    example_limit: int = typer.Option(5, "--example-limit", min=1, max=25),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Report backfill groups that are eligible or blocked for source packets."""
    cfg = _cfg(hub=hub)
    try:
        result = write_exception_source_packet_opportunities(
            cfg.repo_root,
            output=output,
            limit=limit,
            example_limit=example_limit,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("source-packet-requests")
def exceptions_source_packet_requests(
    output: Optional[Path] = typer.Option(None, "--output"),
    write_mail: bool = typer.Option(
        True,
        "--write-mail/--no-write-mail",
        help="Write staged candidate mail to processed/mail/staged/source_packet_requests.jsonl.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Compile needs_source_packet decisions into central candidate mail."""
    cfg = _cfg(hub=hub)
    try:
        result = write_exception_source_packet_requests(
            cfg.repo_root,
            output=output,
            write_mail=write_mail,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("fix-outcome-requests")
def exceptions_fix_outcome_requests(
    output: Optional[Path] = typer.Option(None, "--output"),
    write_mail: bool = typer.Option(
        True,
        "--write-mail/--no-write-mail",
        help="Write staged candidate mail to processed/mail/staged/fix_outcome_requests.jsonl.",
    ),
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Compile unresolved observed exceptions into staged fix-outcome request mail."""
    cfg = _cfg(hub=hub)
    try:
        result = write_exception_fix_outcome_requests(
            cfg.repo_root,
            output=output,
            write_mail=write_mail,
            limit=limit,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("hard-issue-lookup")
def exceptions_hard_issue_lookup(
    query: str = typer.Option(
        "", "--query", help="Short safe issue summary. Do not paste raw logs."
    ),
    signal: list[str] = typer.Option([], "--signal"),
    event_type: list[str] = typer.Option([], "--event-type"),
    command_arg: list[str] = typer.Option(
        [], "--command-arg", help="Command argv only; no stdout/stderr."
    ),
    path_ref: list[str] = typer.Option(
        [], "--path-ref", help="Repo-relative path refs or safe hashes."
    ),
    limit: int = typer.Option(5, "--limit", min=1, max=20),
    include_backfill: bool = typer.Option(False, "--include-backfill"),
    target_public_facing: bool = typer.Option(False, "--target-public-facing"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Look up prior exception/fix evidence before a non-obvious fix."""
    cfg = _cfg(hub=hub)
    try:
        result = hard_issue_lookup(
            cfg.repo_root,
            query=query,
            signals=signal,
            event_types=event_type,
            command=command_arg,
            path_refs=path_ref,
            limit=limit,
            include_backfill=include_backfill,
            target_public_facing=target_public_facing,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("learning-queue")
def exceptions_learning_queue(
    output: Optional[Path] = typer.Option(None, "--output"),
    sample_size_threshold: int = typer.Option(10, "--sample-size-threshold", min=2),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Regenerate and print the candidate exception learning queue."""
    cfg = _cfg(hub=hub)
    try:
        result = write_exception_learning_queue(
            cfg.repo_root,
            output=output,
            sample_size_threshold=sample_size_threshold,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@exceptions_app.command("learning-check")
def exceptions_learning_check(
    scenarios: Path = typer.Option(
        Path(
            "assets/coding-harnesses/exception-learning-readiness/examples/"
            "synthetic-learning-readiness-scenarios.json"
        ),
        "--scenarios",
    ),
    output: Optional[Path] = typer.Option(None, "--output"),
    sample_size_threshold: Optional[int] = typer.Option(None, "--sample-size-threshold"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Run synthetic learning-readiness scenarios against the exception queue."""
    cfg = _cfg(hub=hub)
    scenario_path = scenarios if scenarios.is_absolute() else cfg.repo_root / scenarios
    try:
        result = evaluate_exception_learning_readiness_scenarios(
            cfg.repo_root,
            scenario_path,
            output=output,
            sample_size_threshold=sample_size_threshold,
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    if result.get("failed_count"):
        raise typer.Exit(1)


@lesson_app.command("add")
def lesson_add(
    repository: Path = typer.Option(Path("."), "--repo"),
    summary: str = typer.Option(...),
    task: str = "",
    agent: str = "human",
    model: Optional[str] = None,
    lesson: list[str] = typer.Option([], "--lesson"),
    files_changed: list[str] = typer.Option([], "--file"),
    tests_run: list[str] = typer.Option([], "--test"),
    tests_not_run: list[str] = typer.Option([], "--test-not-run"),
    discovery: list[str] = typer.Option([], "--discovery"),
    failure: list[str] = typer.Option([], "--failure"),
    reusable_pattern: list[str] = typer.Option([], "--reusable-pattern"),
    missing_capability: list[str] = typer.Option([], "--missing-capability"),
    evidence: list[str] = typer.Option([], "--evidence"),
    confidence: str = "medium",
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    record = add_lesson(
        cfg.repo_root,
        cfg.database_path,
        repository=str(repository.resolve()),
        task=task,
        agent=agent,
        model=model,
        summary=summary,
        lessons=lesson,
        files_changed=files_changed,
        tests_run=tests_run,
        tests_not_run=tests_not_run,
        discoveries=discovery,
        failures=failure,
        reusable_patterns=reusable_pattern,
        missing_capabilities=missing_capability,
        evidence=evidence,
        confidence=confidence,
    )
    console.print(record.lesson_id)


@lesson_app.command("reindex")
def lesson_reindex(hub: Optional[Path] = typer.Option(None)) -> None:
    """Rebuild by-repo and by-capability lesson indexes from canonical lesson files."""
    cfg = _cfg(hub=hub)
    result = rebuild_lesson_routes(cfg.repo_root)
    console.print_json(data=result)


@lesson_app.command("review-feedback")
def lesson_review_feedback(
    repository: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option("", "--task"),
    agent: str = typer.Option(
        ..., "--agent", help="Reviewing agent, e.g. fable, opus, codex, claude-code, cursor, human."
    ),
    model: Optional[str] = typer.Option(None, "--model"),
    review_type: str = typer.Option(
        ...,
        "--review-type",
        help="red_team | premortem | audit | code_review | security_review | swe_feedback",
    ),
    severity: str = typer.Option("mixed", "--severity"),
    finding: list[str] = typer.Option(
        ...,
        "--finding",
        help="One finding summary per flag; pointers and paths, never source blobs.",
    ),
    confirmed: list[str] = typer.Option([], "--confirmed"),
    recommendation: list[str] = typer.Option([], "--recommendation"),
    path: list[str] = typer.Option([], "--path"),
    evidence: list[str] = typer.Option([], "--evidence"),
    confidence: str = typer.Option("medium", "--confidence"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Record red-team/premortem/audit/code-review findings from any agent for DAD pattern mining."""
    cfg = _cfg(hub=hub)
    try:
        record = add_review_feedback(
            cfg.repo_root,
            cfg.database_path,
            repository=str(repository.resolve()),
            task=task,
            agent=agent,
            model=model,
            review_type=review_type,
            severity=severity,
            findings=finding,
            confirmed=confirmed,
            recommendations=recommendation,
            paths=path,
            evidence=evidence,
            confidence=confidence,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"lesson_id": record.lesson_id, "summary": record.summary})


@lesson_app.command("graph")
def lesson_graph(hub: Optional[Path] = typer.Option(None)) -> None:
    """Compile lessons, patterns, offerings, repos, and usage into a candidate node/edge graph."""
    cfg = _cfg(hub=hub)
    try:
        result = build_lesson_graph(cfg.repo_root)
    except (OSError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    graph = result["graph"]
    summary = {
        "path": result["path"],
        "pattern_library_version": graph["pattern_library_version"],
        "lesson_count": graph["lesson_count"],
        "node_count": graph["node_count"],
        "edge_count": graph["edge_count"],
        "nodes_by_type": graph["nodes_by_type"],
        "edges_by_type": graph["edges_by_type"],
        "pattern_gap_candidates": graph["pattern_gap_candidates"][:10],
        "unmatched_asset_refs": graph["unmatched_asset_refs"][:10],
        "authority_boundary": graph["authority_boundary"],
    }
    console.print_json(data=summary)


@lesson_app.command("asset-use")
def lesson_asset_use(
    asset_id: str = typer.Option(..., "--asset-id"),
    repository: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option(..., "--task"),
    agent: str = typer.Option(..., "--agent"),
    used_for: str = typer.Option(..., "--used-for"),
    interaction_stage: str = typer.Option("after_use", "--stage"),
    expected_usefulness: str = typer.Option("unknown", "--expected-usefulness"),
    expected_futurefulness: str = typer.Option("unknown", "--expected-futurefulness"),
    expected_value_reason: str = typer.Option("", "--expected-value-reason"),
    planned_use: str = typer.Option("", "--planned-use"),
    found_by: str = typer.Option("", "--found-by"),
    found_query: str = typer.Option("", "--found-query"),
    issue_addressed: str = typer.Option("", "--issue-addressed"),
    part_used: list[str] = typer.Option([], "--part-used"),
    part_not_used: list[str] = typer.Option([], "--part-not-used"),
    not_used_reason: str = typer.Option("", "--not-used-reason"),
    upgrade_made: list[str] = typer.Option([], "--upgrade-made"),
    difficulty: list[str] = typer.Option([], "--difficulty"),
    thing_learned: list[str] = typer.Option([], "--thing-learned"),
    reuse_when: list[str] = typer.Option([], "--reuse-when"),
    avoid_when: list[str] = typer.Option([], "--avoid-when"),
    pay_forward: str = typer.Option("", "--pay-forward"),
    next_agent_action: list[str] = typer.Option([], "--next-agent-action"),
    use_outcome: str = typer.Option(..., "--use-outcome"),
    observed_usefulness: str = typer.Option(..., "--observed-usefulness"),
    observed_futurefulness: str = typer.Option(..., "--observed-futurefulness"),
    missing_part: list[str] = typer.Option([], "--missing-part"),
    score_feedback: str = typer.Option("", "--score-feedback"),
    ceiling_feedback: str = typer.Option("", "--ceiling-feedback"),
    evidence: list[str] = typer.Option([], "--evidence"),
    model: Optional[str] = None,
    confidence: str = "medium",
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Record deterministic candidate feedback after materially using an asset."""
    cfg = _cfg(hub=hub)
    try:
        record = add_asset_use_feedback(
            cfg.repo_root,
            cfg.database_path,
            asset_id=asset_id,
            repository=str(repository.resolve()),
            task=task,
            agent=agent,
            used_for=used_for,
            interaction_stage=interaction_stage,
            expected_usefulness=expected_usefulness,
            expected_futurefulness=expected_futurefulness,
            expected_value_reason=expected_value_reason,
            planned_use=planned_use,
            found_by=found_by,
            found_query=found_query,
            issue_addressed=issue_addressed,
            parts_used=part_used,
            parts_not_used=part_not_used,
            not_used_reason=not_used_reason,
            upgrades_made=upgrade_made,
            difficulties=difficulty,
            things_learned=thing_learned,
            reuse_when=reuse_when,
            avoid_when=avoid_when,
            pay_forward_guidance=pay_forward,
            next_agent_actions=next_agent_action,
            use_outcome=use_outcome,
            observed_usefulness=observed_usefulness,
            observed_futurefulness=observed_futurefulness,
            missing_parts_seen=missing_part,
            score_feedback=score_feedback,
            ceiling_feedback=ceiling_feedback,
            evidence=evidence,
            model=model,
            confidence=confidence,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print(record.lesson_id)


@lesson_app.command("repo-event")
def lesson_repo_event(
    repository: Path = typer.Option(Path("."), "--repo"),
    stage: str = typer.Option(..., "--stage"),
    task: str = typer.Option(..., "--task"),
    agent: str = typer.Option("human", "--agent"),
    context_tag: list[str] = typer.Option([], "--context-tag"),
    asset_used: list[str] = typer.Option([], "--asset-used"),
    expected_value: str = typer.Option("", "--expected-value"),
    actual_value: str = typer.Option("", "--actual-value"),
    failure_class: str = typer.Option("", "--failure-class"),
    dependency_order_notes: str = typer.Option("", "--dependency-order-notes"),
    evidence: list[str] = typer.Option([], "--evidence"),
) -> None:
    """Append a repo-local candidate learning event as data, never executable instructions."""
    stage_value = stage.lower()
    if stage_value not in {"before_work", "during_failure", "after_work", "review"}:
        console.print("Stage must be one of: before_work, during_failure, after_work, review")
        raise typer.Exit(2)
    try:
        record = append_repo_learning_event(
            repository,
            stage=stage_value,
            task=task,
            agent=agent,
            context_tags=context_tag,
            assets_used=asset_used,
            expected_value=expected_value,
            actual_value=actual_value,
            failure_class=failure_class,
            dependency_order_notes=dependency_order_notes,
            evidence=evidence,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=record.model_dump(mode="json"))


@agent_app.command("preflight")
def agent_preflight(
    repository: Path = typer.Option(Path("."), "--repo"),
    agent: str = typer.Option(...),
    task: str = typer.Option(...),
    model: Optional[str] = None,
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    payload = preflight(cfg.repo_root, repository, cfg.database_path, agent, task, model)
    console.print_json(data=payload)


@agent_app.command("postflight")
def agent_postflight(
    session: str = typer.Option(...),
    repository: Path = typer.Option(Path("."), "--repo"),
    summary: str = typer.Option(...),
    hub: Optional[Path] = typer.Option(None),
    file: list[str] = typer.Option([], "--file"),
    command: list[str] = typer.Option([], "--command"),
    test: list[str] = typer.Option([], "--test", "--tests"),
    test_not_run: list[str] = typer.Option([], "--test-not-run"),
    confirmed: list[str] = typer.Option([], "--confirmed"),
    inferred: list[str] = typer.Option([], "--inferred"),
    assumption: list[str] = typer.Option([], "--assumption"),
    unknown: list[str] = typer.Option([], "--unknown"),
    lesson: list[str] = typer.Option([], "--lesson"),
    risk: list[str] = typer.Option([], "--risk"),
    next_action: list[str] = typer.Option([], "--next-action"),
    review_lane: list[str] = typer.Option([], "--review-lane"),
    discovery: list[str] = typer.Option([], "--discovery"),
    failure: list[str] = typer.Option([], "--failure"),
    reusable_pattern: list[str] = typer.Option([], "--reusable-pattern"),
    missing_capability: list[str] = typer.Option([], "--missing-capability"),
    evidence: list[str] = typer.Option([], "--evidence"),
    trace: str = typer.Option("", "--trace"),
    used: list[str] = typer.Option([], "--used"),
    ignored: list[str] = typer.Option([], "--ignored"),
    attempted_failed: list[str] = typer.Option([], "--attempted-failed"),
    harmful: list[str] = typer.Option([], "--harmful"),
) -> None:
    cfg = _cfg(hub=hub)
    handoff, lesson_record = postflight(
        cfg.repo_root,
        cfg.database_path,
        session,
        summary,
        files_changed=file,
        commands_run=command,
        tests_run=test,
        tests_not_run=test_not_run,
        confirmed=confirmed,
        inferred=inferred,
        assumptions=assumption,
        unknowns=unknown,
        lessons=lesson,
        risks=risk,
        next_actions=next_action,
        review_lanes=review_lane,
        discoveries=discovery,
        failures=failure,
        reusable_patterns=reusable_pattern,
        missing_capabilities=missing_capability,
        evidence=evidence,
        trace=trace,
        used=used,
        ignored=ignored,
        attempted_failed=attempted_failed,
        harmful=harmful,
    )
    console.print_json(
        data={"handoff_id": handoff.handoff_id, "lesson_id": lesson_record.lesson_id}
    )


@agent_app.command("midflight")
def agent_midflight(
    session: str = typer.Option(...),
    hub: Optional[Path] = typer.Option(None),
    context: list[str] = typer.Option([], "--context"),
    path: list[str] = typer.Option([], "--path"),
    ack_rule: list[str] = typer.Option([], "--ack-rule"),
) -> None:
    """Check and acknowledge deterministic learning rules during material work."""
    cfg = _cfg(hub=hub)
    try:
        result = midflight(
            cfg.repo_root,
            session,
            context=context,
            paths=path,
            ack_rules=ack_rule,
        )
    except FileNotFoundError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    if result["missing_learning_rule_acknowledgements"]:
        raise typer.Exit(2)


@agent_app.command("install")
def agent_install(
    repository: Path = typer.Option(..., "--repo"),
    hub: Optional[Path] = typer.Option(None),
    force: bool = False,
) -> None:
    cfg = _cfg(hub=hub)
    changed = install_governance(repository, cfg.repo_root, force)
    console.print("\n".join(str(path) for path in changed))


@agent_app.command("install-learning-loop")
def agent_install_learning_loop(
    repository: Path = typer.Option(..., "--repo"),
    mode: str = typer.Option("files-only", "--mode"),
    force: bool = False,
) -> None:
    """Install files-only repo learning-loop templates; no hooks are created."""
    try:
        changed = install_repo_learning_loop(repository, mode=mode, force=force)
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={"repo": str(repository.resolve()), "changed": [str(path) for path in changed]}
    )


@agent_app.command("new")
def agent_new(
    repository: Path = typer.Option(..., "--repo"),
    name: Optional[str] = typer.Option(None, "--name"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Scaffold a new repository already wired to this hub (starter files + governance)."""
    cfg = _cfg(hub=hub)
    changed = scaffold_new_repo(repository, cfg.repo_root, name)
    console.print("\n".join(str(path) for path in changed))


@agent_app.command("enforce")
def agent_enforce(
    repository: Path = typer.Option(Path("."), "--repo"), hub: Optional[Path] = typer.Option(None)
) -> None:
    cfg = _cfg(hub=hub)
    ok, message = enforce_postflight(cfg.repo_root, repository)
    console.print(message)
    if not ok:
        raise typer.Exit(2)


@research_app.command("intake")
def research_intake(
    name: str = typer.Option(..., "--name"),
    kind: str = typer.Option(..., "--kind", help="skill | harness | asset | lesson | doc"),
    source_url: str = typer.Option(..., "--source-url"),
    research_ref: str = typer.Option(
        "", "--research-ref", help="Pointer into a processed/research report entry."
    ),
    license_name: str = typer.Option("", "--license"),
    notes: str = typer.Option("", "--notes"),
    justification: str = typer.Option(
        "",
        "--justification",
        help="Required when the source is not in the trusted-source registry.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Quarantine an external research finding as a candidate skill/asset intake record."""
    cfg = _cfg(hub=hub)
    try:
        result = intake_external_candidate(
            cfg.repo_root,
            name=name,
            kind=kind,
            source_url=source_url,
            research_ref=research_ref,
            license_name=license_name,
            notes=notes,
            justification=justification,
        )
    except (ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@research_app.command("screen")
def research_screen(
    intake_id: str = typer.Option(..., "--intake-id"),
    check: str = typer.Option(
        ..., "--check", help="prompt_injection | license | provenance | compatibility"
    ),
    result: str = typer.Option(..., "--result", help="pass | fail | not_applicable"),
    notes: str = typer.Option("", "--notes"),
    screened_by: str = typer.Option("agent", "--screened-by"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Record one screening check on a quarantined intake record."""
    cfg = _cfg(hub=hub)
    try:
        outcome = record_screening(
            cfg.repo_root,
            intake_id,
            check=check,
            result=result,
            notes=notes,
            screened_by=screened_by,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=outcome)


@research_app.command("promote")
def research_promote(
    intake_id: str = typer.Option(..., "--intake-id"),
    approved_by: str = typer.Option(
        ..., "--approved-by", help="Named human approver; agent/unknown are rejected."
    ),
    approval_id: str = typer.Option(..., "--approval-id"),
    target: str = typer.Option(..., "--target", help="offering | skill_pointer"),
    capability: list[str] = typer.Option([], "--capability"),
    task_type: list[str] = typer.Option([], "--task-type"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Promote a fully screened intake record into the library as a pointer (human-approved)."""
    cfg = _cfg(hub=hub)
    try:
        outcome = promote_intake(
            cfg.repo_root,
            intake_id,
            approved_by=approved_by,
            approval_id=approval_id,
            target=target,
            capabilities=capability or None,
            task_types=task_type or None,
        )
    except (ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=outcome)


@research_app.command("intake-list")
def research_intake_list(
    status: str = typer.Option(
        "", "--status", help="Filter: quarantined | screened | promoted | rejected"
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """List external intake records and their screening status."""
    cfg = _cfg(hub=hub)
    console.print_json(data=list_intake(cfg.repo_root, status=status))


@research_app.command("intake-graph")
def research_intake_graph(
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Build a pointer-only candidate graph over external research intake records."""
    cfg = _cfg(hub=hub)
    try:
        report = build_research_intake_graph(cfg.repo_root)
    except (ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=report)


@research_app.command("frontier-watch")
def research_frontier_watch(
    language: str = typer.Option(
        "", "--language", help="Filter to python, rust, or another language id."
    ),
    cadence: str = typer.Option(
        "", "--cadence", help="Filter to weekly | monthly | quarterly | manual."
    ),
    include_manual: bool = typer.Option(
        False, "--include-manual", help="Include manual-only source rows."
    ),
    limit: int = typer.Option(0, "--limit", min=0, max=100),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """List pointer-only language-frontier sources that agents should check."""
    cfg = _cfg(hub=hub)
    try:
        report = build_language_frontier_watchlist(
            cfg.repo_root,
            language=language,
            cadence=cadence,
            include_manual=include_manual,
            limit=limit,
        )
    except (ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=report)


@research_app.command("language-playbook")
def research_language_playbook(
    language: str = typer.Option(
        ..., "--language", help="Language id, e.g. python, rust, future-language-template."
    ),
    include_text: bool = typer.Option(
        False, "--include-text", help="Include the markdown playbook body in the JSON output."
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Show the operational DAD coding playbook for one language."""
    cfg = _cfg(hub=hub)
    try:
        report = build_language_playbook_report(
            cfg.repo_root,
            language=language,
            include_text=include_text,
        )
    except (ValueError, FileNotFoundError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=report)


@research_app.command("missing")
def research_missing(
    limit: int = typer.Option(20, min=1, max=30),
    enable_external: bool = typer.Option(
        False,
        "--enable-external",
        help="Allow live external GitHub API calls for missing-part research.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    report = research_missing_parts(
        cfg.repo_root, cfg.database_path, limit, enable_external=enable_external
    )
    console.print_json(data=report)
    if report["status"] == "blocked_external_research_not_enabled":
        raise typer.Exit(2)


@recommend_app.command("skills")
def recommend_skills(
    hub: Optional[Path] = typer.Option(None),
    threshold: int = typer.Option(3, min=2, max=100),
) -> None:
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        records = recommend_skills_and_agents(db.assets(), threshold)
    console.print_json(data=[record.model_dump(mode="json") for record in records])


@recommend_app.command("swarm")
def recommend_swarm_command(
    goal: str,
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(12, min=1, max=50),
) -> None:
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        record = recommend_swarm(goal, db.assets(), limit)
    console.print_json(data=record.model_dump(mode="json"))


@recommend_app.command("asset-families")
def recommend_asset_families(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated candidate reports for high-leverage asset-family patterns."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_asset_family_reports(
            cfg.repo_root,
            db.assets(),
            source_id=source_id,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("learning-loops")
def recommend_learning_loops(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(25, "--review-sample", min=1, max=200),
) -> None:
    """Write generated candidate learning-loop records from the current catalog."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_learning_loop_outputs(
            cfg.repo_root,
            db.assets(),
            scan_id=scan_id,
            source_id=source_id,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("workflow-sweeps")
def recommend_workflow_sweeps(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
    include_noise: bool = typer.Option(False, "--include-noise/--exclude-noise"),
    usefulness_per_sweep_limit: int = typer.Option(
        25, "--usefulness-per-sweep-limit", min=1, max=100
    ),
    usefulness_global_limit: int = typer.Option(75, "--usefulness-global-limit", min=1, max=300),
) -> None:
    """Write generated candidate workflow-family sweeps, governance first."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_workflow_sweep_reports(
            cfg.repo_root,
            db.assets(),
            source_id=source_id,
            review_sample=review_sample,
            include_noise=include_noise,
            usefulness_per_sweep_limit=usefulness_per_sweep_limit,
            usefulness_global_limit=usefulness_global_limit,
        )
    console.print_json(data=result)


@recommend_app.command("workflow-parts")
def recommend_workflow_parts(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated candidate workflow-part records from the current catalog."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_workflow_part_outputs(
            cfg.repo_root,
            db.assets(),
            db.edges(),
            scan_id=scan_id,
            source_id=source_id,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("workflow-part-review-template")
def recommend_workflow_part_review_template(
    hub: Optional[Path] = typer.Option(None),
    workflow_parts_file: Optional[Path] = typer.Option(None, "--workflow-parts-file"),
    sample_size: int = typer.Option(50, "--sample-size", min=1, max=200),
) -> None:
    """Write a stratified generated review template for workflow-part calibration."""
    cfg = _cfg(hub=hub)
    path = workflow_parts_file or cfg.repo_root / "processed" / "learning" / "workflow_parts.jsonl"
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        result = write_workflow_part_review_template_outputs(
            cfg.repo_root, load_workflow_parts(path), sample_size=sample_size
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"workflow_parts_file": str(path), **result})


@recommend_app.command("workflow-part-review-summary")
def recommend_workflow_part_review_summary(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
) -> None:
    """Summarize filled workflow-part review JSONL labels without changing roadmap state."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        reviews = load_workflow_part_reviews(path)
        summary, output = write_workflow_part_review_results_summary(cfg.repo_root, reviews, path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": output, "summary": summary})


@recommend_app.command("workflow-part-review-queue")
def recommend_workflow_part_review_queue(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    workflow_parts_file: Optional[Path] = typer.Option(None, "--workflow-parts-file"),
    status: str = typer.Option("pending", "--status"),
    part_type: str = typer.Option("all", "--part-type"),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    """List workflow-part review queue items joined with candidate context."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    parts_path = (
        workflow_parts_file or cfg.repo_root / "processed" / "learning" / "workflow_parts.jsonl"
    )
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not parts_path.is_absolute():
        parts_path = cfg.repo_root / parts_path
    status_value = status.lower()
    if status_value not in {"pending", "reviewed", "all"}:
        console.print("Status must be one of: pending, reviewed, all")
        raise typer.Exit(2)
    try:
        queue = build_workflow_part_review_queue(
            load_workflow_part_reviews(review_path),
            load_workflow_parts(parts_path),
            status=status_value,  # type: ignore[arg-type]
            part_type=part_type,
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(review_path),
            "workflow_parts_file": str(parts_path),
            **queue,
        }
    )


@recommend_app.command("workflow-part-review-label")
def recommend_workflow_part_review_label(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    part_id: Optional[str] = typer.Option(None, "--part-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    usefulness: Optional[str] = typer.Option(None, "--usefulness"),
    safety: Optional[str] = typer.Option(None, "--safety"),
    specificity: Optional[str] = typer.Option(None, "--specificity"),
    dataflow_completeness: Optional[str] = typer.Option(None, "--dataflow-completeness"),
    decision: Optional[str] = typer.Option(None, "--decision"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    false_negative_note: Optional[str] = typer.Option(None, "--false-negative-note"),
    useful_example_note: Optional[str] = typer.Option(None, "--useful-example-note"),
    missing_dataflow_note: Optional[str] = typer.Option(None, "--missing-dataflow-note"),
) -> None:
    """Update one workflow-part review JSONL record with human calibration labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_workflow_part_review_file(
            path,
            sample_id=sample_id,
            part_id=part_id,
            reviewer=reviewer,
            usefulness=usefulness,
            safety=safety,
            specificity=specificity,
            dataflow_completeness=dataflow_completeness,
            decision=decision,
            notes=notes,
            false_positive_reason=false_positive_reason,
            false_negative_note=false_negative_note,
            useful_example_note=useful_example_note,
            missing_dataflow_note=missing_dataflow_note,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "updated": updated.model_dump(mode="json"),
            "summary": summary,
        }
    )


@recommend_app.command("workflow-part-calibration-evidence")
def recommend_workflow_part_calibration_evidence(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Write tracked-ready evidence only after workflow-part calibration review is complete."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        summary, evidence_path = write_workflow_part_calibration_evidence(
            cfg.repo_root, load_workflow_part_reviews(path), path, output
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": evidence_path, "summary": summary})


@recommend_app.command("workflow-part-guidance")
def recommend_workflow_part_guidance(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    limit: int = typer.Option(30, "--limit", min=1, max=100),
) -> None:
    """Write manual workflow-part usage guidance from completed human review labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        guidance, report, payload = write_workflow_part_usage_guidance(
            cfg.repo_root, load_workflow_part_reviews(path), path, limit=limit
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "report": report,
            "payload": payload,
            "summary": guidance["summary"],
            "authority_boundary": guidance["authority_boundary"],
        }
    )


@recommend_app.command("manual-tasks")
def recommend_manual_tasks(
    hub: Optional[Path] = typer.Option(None),
    workflow_guidance_file: Optional[Path] = typer.Option(None, "--workflow-guidance-file"),
    limit: int = typer.Option(25, "--limit", min=1, max=100),
    family_limit: int = typer.Option(12, "--family-limit", min=1, max=50),
) -> None:
    """Write a generated manual task queue from current alerts and workflow-part guidance."""
    cfg = _cfg(hub=hub)
    guidance_path = (
        workflow_guidance_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_usage_guidance.json"
    )
    if not guidance_path.is_absolute():
        guidance_path = cfg.repo_root / guidance_path
    try:
        workflow_guidance = json.loads(guidance_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else None
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        result = write_manual_task_queue(
            cfg.repo_root,
            db.alerts(open_only=True),
            db.assets(),
            workflow_guidance,
            latest_scan_id=latest_scan_id,
            scan_changed_count=int(scan_summary.get("changed_during_scan_count") or 0),
            limit=limit,
            family_limit=family_limit,
        )
    console.print_json(data={"workflow_guidance_file": str(guidance_path), **result})


@recommend_app.command("repo-buildout")
def recommend_repo_buildout(
    repo: str = typer.Option(..., "--repo"),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(10, "--limit", min=1, max=50),
) -> None:
    """Write generated repo-specific buildout recommendations from current catalog data."""
    cfg = _cfg(hub=hub)
    artifacts = load_default_repo_buildout_artifacts(cfg.repo_root)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        try:
            result = write_repo_buildout_outputs(
                cfg.repo_root,
                repo,
                db.assets(),
                db.edges(),
                db.alerts(open_only=True),
                local_sources=cfg.local_sources,
                artifacts=artifacts,
                scan_id=latest_scan_id,
                scan_changed_count=int(scan_summary.get("changed_during_scan_count") or 0),
                limit=limit,
            )
        except ValueError as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("reference-architectures")
def recommend_reference_architectures(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
    component_limit: int = typer.Option(12, "--component-limit", min=3, max=50),
    include_edges: bool = typer.Option(
        False,
        "--include-edges",
        help="Load the full candidate edge table for composition scoring; off by default for large catalogs.",
    ),
) -> None:
    """Write generated reference architecture candidates from current catalog data."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_reference_architecture_outputs(
            cfg.repo_root,
            db.assets(),
            db.edges() if include_edges else [],
            scan_id=latest_scan_id,
            limit=limit,
            component_limit=component_limit,
        )
    console.print_json(data=result)


@recommend_app.command("architecture-consult")
def recommend_architecture_consult(
    intent_file: Path = typer.Option(..., "--intent-file"),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(10, "--limit", min=1, max=25),
) -> None:
    """Write a generated seed architecture consult for a new repo intent file."""
    cfg = _cfg(hub=hub)
    resolved_intent = intent_file if intent_file.is_absolute() else Path.cwd() / intent_file
    if not resolved_intent.exists():
        console.print(f"Intent file not found: {resolved_intent}")
        raise typer.Exit(2)
    result = write_architecture_consult_outputs(
        cfg.repo_root,
        resolved_intent.resolve(),
        limit=limit,
    )
    console.print_json(data=result)


@recommend_app.command("repo-completion-dashboard")
def recommend_repo_completion_dashboard(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(100, "--limit", min=1, max=500),
) -> None:
    """Write generated per-repo completion blockers for lesson automation."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_repo_completion_dashboard_outputs(
            cfg.repo_root,
            db.assets(),
            limit=limit,
        )
    console.print_json(data=result)


@recommend_app.command("repo-completion-waves")
def recommend_repo_completion_waves(
    hub: Optional[Path] = typer.Option(None),
    dashboard_limit: int = typer.Option(500, "--dashboard-limit", min=1, max=1000),
    per_wave_repo_limit: int = typer.Option(25, "--per-wave-repo-limit", min=1, max=100),
) -> None:
    """Write generated ordered waves for completing repo lesson automation."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_repo_completion_wave_plan_outputs(
            cfg.repo_root,
            db.assets(),
            dashboard_limit=dashboard_limit,
            per_wave_repo_limit=per_wave_repo_limit,
        )
    console.print_json(data=result)


@recommend_app.command("repo-completion-proof-check")
def recommend_repo_completion_proof_check(
    hub: Optional[Path] = typer.Option(None),
    dashboard_limit: int = typer.Option(500, "--dashboard-limit", min=1, max=1000),
    per_wave_repo_limit: int = typer.Option(25, "--per-wave-repo-limit", min=1, max=100),
) -> None:
    """Write generated proof status for repo-completion wave advancement."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_repo_completion_proof_check_outputs(
            cfg.repo_root,
            db.assets(),
            dashboard_limit=dashboard_limit,
            per_wave_repo_limit=per_wave_repo_limit,
        )
    console.print_json(data=result)


@recommend_app.command("lesson-automation-coverage")
def recommend_lesson_automation_coverage(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
) -> None:
    """Write a no-rescan coverage report and scan-cycle log for future learning automation."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        result = write_lesson_automation_coverage_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            cfg.github_sources,
            scan_id=latest_scan_id,
            scan_summary=scan_summary,
            limit=limit,
        )
    console.print_json(data=result)


@recommend_app.command("lesson-automation-next-actions")
def recommend_lesson_automation_next_actions(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(25, "--limit", min=1, max=100),
) -> None:
    """Write a generated queue of next human-gated lesson-automation actions."""
    cfg = _cfg(hub=hub)
    result = write_lesson_automation_next_action_outputs(
        cfg.repo_root,
        limit=limit,
    )
    console.print_json(data=result)


@recommend_app.command("lesson-automation-decision-template")
def recommend_lesson_automation_decision_template(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(25, "--limit", min=1, max=100),
) -> None:
    """Write a generated human-decision template for lesson-automation actions."""
    cfg = _cfg(hub=hub)
    result = write_lesson_automation_decision_template_outputs(
        cfg.repo_root,
        limit=limit,
    )
    console.print_json(data=result)


@recommend_app.command("lesson-automation-decision-queue")
def recommend_lesson_automation_decision_queue(
    hub: Optional[Path] = typer.Option(None),
    status: str = typer.Option("pending", "--status"),
    limit: int = typer.Option(25, "--limit", min=1, max=100),
) -> None:
    """List pending or reviewed lesson-automation decision rows."""
    cfg = _cfg(hub=hub)
    path = cfg.repo_root / DECISION_TEMPLATE_PATH
    records = load_lesson_automation_decisions(path)
    if status not in {"pending", "reviewed", "all"}:
        raise typer.BadParameter("--status must be pending, reviewed, or all.")
    if status == "pending":
        selected = [record for record in records if record.decision == "pending"]
    elif status == "reviewed":
        selected = [record for record in records if record.decision != "pending"]
    else:
        selected = records
    payload = {
        "decision_file": str(path),
        "summary": summarize_lesson_automation_decisions(records),
        "items": [record.model_dump(mode="json") for record in selected[:limit]],
    }
    console.print_json(data=payload)


@recommend_app.command("lesson-automation-decision-label")
def recommend_lesson_automation_decision_label(
    sample_id: str = typer.Option(..., "--sample-id"),
    reviewer: str = typer.Option(..., "--reviewer"),
    decision: str = typer.Option(..., "--decision"),
    approval_id: str = typer.Option("", "--approval-id"),
    repo_key: list[str] = typer.Option([], "--repo-key"),
    category: list[str] = typer.Option([], "--category"),
    repo_path: list[str] = typer.Option([], "--repo-path"),
    include_path: list[str] = typer.Option([], "--include-path"),
    exclude_path: list[str] = typer.Option([], "--exclude-path"),
    include_path_file: Optional[Path] = typer.Option(None, "--include-path-file"),
    exclude_path_file: Optional[Path] = typer.Option(None, "--exclude-path-file"),
    max_bytes_per_file: int = typer.Option(0, "--max-bytes-per-file", min=0),
    max_files: int = typer.Option(0, "--max-files", min=0),
    allow_content_read: bool = typer.Option(False, "--allow-content-read"),
    allow_source_mutation: bool = typer.Option(False, "--allow-source-mutation"),
    allow_external_api: bool = typer.Option(False, "--allow-external-api"),
    allow_model_call: bool = typer.Option(False, "--allow-model-call"),
    redaction_required: bool = typer.Option(
        True,
        "--redaction-required/--no-redaction-required",
    ),
    token_scope_note: str = typer.Option("", "--token-scope-note"),
    privacy_boundary_note: str = typer.Option("", "--privacy-boundary-note"),
    rationale: str = typer.Option("", "--rationale"),
    notes: str = typer.Option("", "--notes"),
    stop_condition: list[str] = typer.Option([], "--stop-condition"),
    validation_command: list[str] = typer.Option([], "--validation-command"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Apply one human-approved lesson-automation decision label."""
    cfg = _cfg(hub=hub)
    path = cfg.repo_root / DECISION_TEMPLATE_PATH
    records = load_lesson_automation_decisions(path)
    if not records:
        console.print(
            "No decision template exists. Run recommend lesson-automation-decision-template first."
        )
        raise typer.Exit(2)
    include_paths = list(include_path)
    exclude_paths = list(exclude_path)
    try:
        resolved_include_file = _repo_path(cfg.repo_root, include_path_file)
        if resolved_include_file:
            include_paths.extend(
                load_lesson_automation_path_filter_file(
                    resolved_include_file,
                    filter_kind="include",
                )
            )
        resolved_exclude_file = _repo_path(cfg.repo_root, exclude_path_file)
        if resolved_exclude_file:
            exclude_paths.extend(
                load_lesson_automation_path_filter_file(
                    resolved_exclude_file,
                    filter_kind="exclude",
                )
            )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    try:
        updated_records, updated = update_lesson_automation_decision_record(
            records,
            sample_id=sample_id,
            reviewer=reviewer,
            decision=decision,
            reviewed_at=utc_now(),
            approval_id=approval_id,
            approved_repo_keys=repo_key,
            approved_categories=category,
            approved_repo_paths=repo_path,
            approved_include_paths=include_paths,
            approved_exclude_paths=exclude_paths,
            max_bytes_per_file=max_bytes_per_file,
            max_files=max_files,
            allow_content_read=allow_content_read,
            allow_source_mutation=allow_source_mutation,
            allow_external_api=allow_external_api,
            allow_model_call=allow_model_call,
            redaction_required=redaction_required,
            token_scope_note=token_scope_note,
            privacy_boundary_note=privacy_boundary_note,
            rationale=rationale,
            notes=notes,
            stop_conditions=stop_condition,
            validation_commands=validation_command,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    write_lesson_automation_decisions(path, updated_records)
    console.print_json(
        data={
            "decision_file": str(path),
            "summary": summarize_lesson_automation_decisions(updated_records),
            "updated": updated.model_dump(mode="json"),
        }
    )


@recommend_app.command("lesson-automation-approval-packet")
def recommend_lesson_automation_approval_packet(
    hub: Optional[Path] = typer.Option(None),
    decisions_file: Optional[Path] = typer.Option(None, "--decisions-file"),
    repo_limit: int = typer.Option(5, "--repo-limit", min=1, max=25),
    max_bytes_per_file: int = typer.Option(20000, "--max-bytes-per-file", min=1),
    max_files: int = typer.Option(50, "--max-files", min=1, max=500),
) -> None:
    """Write generated decision-label commands for pending lesson-automation approvals."""
    cfg = _cfg(hub=hub)
    result = write_lesson_automation_approval_packet_outputs(
        cfg.repo_root,
        decisions_file=decisions_file,
        repo_limit=repo_limit,
        max_bytes_per_file=max_bytes_per_file,
        max_files=max_files,
    )
    console.print_json(data=result)


@recommend_app.command("lesson-automation-approval-impact")
def recommend_lesson_automation_approval_impact(
    hub: Optional[Path] = typer.Option(None),
    decisions_file: Optional[Path] = typer.Option(None, "--decisions-file"),
    sample_id: str = typer.Option("lesson-automation-decision-001", "--sample-id"),
    repo_limit: int = typer.Option(5, "--repo-limit", min=1, max=25),
    max_bytes_per_file: int = typer.Option(20000, "--max-bytes-per-file", min=1),
    max_files: int = typer.Option(50, "--max-files", min=1, max=500),
) -> None:
    """Write generated approval impact brief for one pending lesson-automation decision."""
    cfg = _cfg(hub=hub)
    try:
        result = write_lesson_automation_approval_impact_outputs(
            cfg.repo_root,
            decisions_file=decisions_file,
            sample_id=sample_id,
            repo_limit=repo_limit,
            max_bytes_per_file=max_bytes_per_file,
            max_files=max_files,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("lesson-automation-execution-plan")
def recommend_lesson_automation_execution_plan(
    hub: Optional[Path] = typer.Option(None),
    decisions_file: Optional[Path] = typer.Option(None, "--decisions-file"),
) -> None:
    """Write a generated execution plan from approved lesson-automation decisions."""
    cfg = _cfg(hub=hub)
    result = write_lesson_automation_execution_plan_outputs(
        cfg.repo_root,
        decisions_file=decisions_file,
    )
    console.print_json(data=result)


@recommend_app.command("priority-content-scope")
def recommend_priority_content_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(200, "--limit", min=1, max=1000),
    per_repo_limit: int = typer.Option(12, "--per-repo-limit", min=1, max=50),
) -> None:
    """Write a metadata-only approval scope for a future bounded content extract pass."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_priority_content_extract_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
            per_repo_limit=per_repo_limit,
        )
    console.print_json(data=result)


@recommend_app.command("ci-release-scope")
def recommend_ci_release_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(200, "--limit", min=1, max=1000),
    per_repo_limit: int = typer.Option(12, "--per-repo-limit", min=1, max=50),
) -> None:
    """Write a metadata-only approval scope for CI, release, changelog, QA, and log artifacts."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_ci_release_artifact_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
            per_repo_limit=per_repo_limit,
        )
    console.print_json(data=result)


@recommend_app.command("repo-learning-loop-scope")
def recommend_repo_learning_loop_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
) -> None:
    """Write a generated approval scope for files-only repo learning-loop installation."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_repo_learning_loop_install_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
        )
    console.print_json(data=result)


@recommend_app.command("governance-map-scope")
def recommend_governance_map_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
) -> None:
    """Write a generated approval scope for governance maps and child mirrors."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_governance_map_adoption_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
        )
    console.print_json(data=result)


@recommend_app.command("priority-content-extract")
def recommend_priority_content_extract(
    approval_id: str = typer.Option(..., "--approval-id"),
    repo_key: list[str] = typer.Option([], "--repo-key"),
    category: list[str] = typer.Option([], "--category"),
    include_path: list[str] = typer.Option([], "--include-path"),
    exclude_path: list[str] = typer.Option([], "--exclude-path"),
    include_path_file: Optional[Path] = typer.Option(None, "--include-path-file"),
    exclude_path_file: Optional[Path] = typer.Option(None, "--exclude-path-file"),
    scope_file: Optional[Path] = typer.Option(None, "--scope-file"),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    max_bytes_per_file: int = typer.Option(20_000, "--max-bytes-per-file", min=1, max=200_000),
    max_excerpt_chars: int = typer.Option(4_000, "--max-excerpt-chars", min=200, max=20_000),
) -> None:
    """Read only approved scoped paths with byte caps and write generated observations."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        try:
            include_paths = list(include_path)
            exclude_paths = list(exclude_path)
            resolved_include_file = _repo_path(cfg.repo_root, include_path_file)
            if resolved_include_file:
                include_paths.extend(
                    load_lesson_automation_path_filter_file(
                        resolved_include_file,
                        filter_kind="include",
                    )
                )
            resolved_exclude_file = _repo_path(cfg.repo_root, exclude_path_file)
            if resolved_exclude_file:
                exclude_paths.extend(
                    load_lesson_automation_path_filter_file(
                        resolved_exclude_file,
                        filter_kind="exclude",
                    )
                )
            result = write_priority_content_extract_outputs(
                cfg.repo_root,
                cfg.local_sources,
                scope_file=scope_file,
                approval_id=approval_id,
                repo_keys=repo_key,
                category_ids=category,
                include_paths=include_paths,
                exclude_paths=exclude_paths,
                scan_id=latest_scan_id,
                max_bytes_per_file=max_bytes_per_file,
                max_excerpt_chars=max_excerpt_chars,
                limit=limit,
            )
        except ValueError as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("priority-content-lessons")
def recommend_priority_content_lessons(
    observations_file: Optional[Path] = typer.Option(None, "--observations-file"),
    hub: Optional[Path] = typer.Option(None),
    min_observations: int = typer.Option(1, "--min-observations", min=1, max=20),
    limit: int = typer.Option(100, "--limit", min=1, max=500),
) -> None:
    """Synthesize generated lesson candidates from bounded priority-content observations."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        try:
            result = write_priority_content_lesson_outputs(
                cfg.repo_root,
                observations_file=observations_file,
                scan_id=latest_scan_id,
                min_observations=min_observations,
                limit=limit,
            )
        except ValueError as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("priority-content-lesson-review-template")
def recommend_priority_content_lesson_review_template(
    candidates_file: Optional[Path] = typer.Option(None, "--candidates-file"),
    hub: Optional[Path] = typer.Option(None),
    sample_size: int = typer.Option(100, "--sample-size", min=1, max=500),
) -> None:
    """Write a generated human-review template for priority-content lesson candidates."""
    cfg = _cfg(hub=hub)
    path = candidates_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_candidates.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        result = write_priority_content_lesson_review_template_outputs(
            cfg.repo_root,
            load_priority_content_lesson_candidates(path),
            sample_size=sample_size,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"candidates_file": str(path), **result})


@recommend_app.command("priority-content-lesson-review-summary")
def recommend_priority_content_lesson_review_summary(
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Summarize priority-content lesson review labels without promoting lessons."""
    cfg = _cfg(hub=hub)
    path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        summary = summarize_priority_content_lesson_reviews(
            load_priority_content_lesson_reviews(path)
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "summary": summary})


@recommend_app.command("priority-content-lesson-promotion-candidates")
def recommend_priority_content_lesson_promotion_candidates(
    candidates_file: Optional[Path] = typer.Option(None, "--candidates-file"),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(100, "--limit", min=1, max=500),
) -> None:
    """Package reviewed priority-content lessons as generated learning-rule promotion candidates."""
    cfg = _cfg(hub=hub)
    candidates_path = candidates_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_candidates.jsonl"
    )
    reviews_path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not candidates_path.is_absolute():
        candidates_path = cfg.repo_root / candidates_path
    if not reviews_path.is_absolute():
        reviews_path = cfg.repo_root / reviews_path
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
    try:
        result = write_learning_rule_promotion_candidate_outputs(
            cfg.repo_root,
            load_priority_content_lesson_candidates(candidates_path),
            load_priority_content_lesson_reviews(reviews_path),
            scan_id=latest_scan_id,
            limit=limit,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "candidates_file": str(candidates_path),
            "review_file": str(reviews_path),
            **result,
        }
    )


@recommend_app.command("priority-content-lesson-review-queue")
def recommend_priority_content_lesson_review_queue(
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    hub: Optional[Path] = typer.Option(None),
    status: str = typer.Option("pending", "--status"),
    limit: int = typer.Option(10, "--limit", min=1, max=100),
) -> None:
    """List priority-content lesson review queue items for human labeling."""
    cfg = _cfg(hub=hub)
    path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        result = build_priority_content_lesson_review_queue(
            load_priority_content_lesson_reviews(path),
            status=status,
            limit=limit,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), **result})


@recommend_app.command("priority-content-lesson-review-label")
def recommend_priority_content_lesson_review_label(
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    lesson_candidate_id: Optional[str] = typer.Option(None, "--lesson-candidate-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    applicability: Optional[str] = typer.Option(None, "--applicability"),
    usefulness: Optional[str] = typer.Option(None, "--usefulness"),
    safety: Optional[str] = typer.Option(None, "--safety"),
    actionability: Optional[str] = typer.Option(None, "--actionability"),
    decision: Optional[str] = typer.Option(None, "--decision"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    missing_context_note: Optional[str] = typer.Option(None, "--missing-context-note"),
    useful_example_note: Optional[str] = typer.Option(None, "--useful-example-note"),
    promotion_blocker_note: Optional[str] = typer.Option(None, "--promotion-blocker-note"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Apply one human-approved priority-content lesson review label."""
    cfg = _cfg(hub=hub)
    path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_priority_content_lesson_review_file(
            path,
            sample_id=sample_id,
            lesson_candidate_id=lesson_candidate_id,
            reviewer=reviewer,
            applicability=applicability,
            usefulness=usefulness,
            safety=safety,
            actionability=actionability,
            decision=decision,
            notes=notes,
            false_positive_reason=false_positive_reason,
            missing_context_note=missing_context_note,
            useful_example_note=useful_example_note,
            promotion_blocker_note=promotion_blocker_note,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "updated": updated.model_dump(mode="json"),
            "summary": summary,
        }
    )


@recommend_app.command("public-safe-source-sweep")
def recommend_public_safe_source_sweep(
    source_path: Path = typer.Option(..., "--source-path"),
    source_id: str = typer.Option(..., "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=300),
    max_files: Optional[int] = typer.Option(None, "--max-files", min=1),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Metadata-only sweep for private sources whose workflow is reusable but rows are not."""
    cfg = _cfg(hub=hub)
    result = write_public_safe_source_sweep(
        cfg.repo_root,
        source_path,
        source_id=source_id,
        review_sample=review_sample,
        max_files=max_files,
    )
    console.print_json(data=result)


@recommend_app.command("archaeology")
def recommend_archaeology(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    include_worktrees: bool = typer.Option(True, "--include-worktrees/--exclude-worktrees"),
    include_temp: bool = typer.Option(True, "--include-temp/--exclude-temp"),
    max_repos: int = typer.Option(25, "--max-repos", min=1, max=100),
    max_commits: int = typer.Option(200, "--max-commits", min=1, max=1000),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated worktree, git-history, failure, and change-pattern archaeology reports."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_archaeology_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=scan_id,
            source_id=source_id,
            include_worktrees=include_worktrees,
            include_temp=include_temp,
            max_repos=max_repos,
            max_commits=max_commits,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("root-cause-lessons")
def recommend_root_cause_lessons(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    include_worktrees: bool = typer.Option(True, "--include-worktrees/--exclude-worktrees"),
    include_temp: bool = typer.Option(True, "--include-temp/--exclude-temp"),
    max_repos: int = typer.Option(25, "--max-repos", min=1, max=100),
    max_commits: int = typer.Option(200, "--max-commits", min=1, max=1000),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated context-bound root-cause and counterfactual lesson candidates."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_root_cause_lesson_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=scan_id,
            source_id=source_id,
            include_worktrees=include_worktrees,
            include_temp=include_temp,
            max_repos=max_repos,
            max_commits=max_commits,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("semantic-evolution")
def recommend_semantic_evolution(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    basename: Optional[str] = typer.Option(None, "--basename"),
    asset_type: str = typer.Option("schema", "--asset-type"),
    max_families: int = typer.Option(100, "--max-families", min=1, max=500),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
    max_read_bytes: int = typer.Option(1_000_000, "--max-read-bytes", min=0),
) -> None:
    """Grade structured semantic evolution versus copy/fixture noise from the current catalog."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_semantic_evolution_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=scan_id,
            source_id=source_id,
            basename=basename,
            asset_type=asset_type,
            max_families=max_families,
            review_sample=review_sample,
            max_read_bytes=max_read_bytes,
        )
    console.print_json(data=result)


@recommend_app.command("background-connections")
def recommend_background_connections(
    hub: Optional[Path] = typer.Option(None),
    attention: str = typer.Option("recent", "--attention"),
    cold: str = typer.Option("older", "--cold"),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
    escalation_budget: int = typer.Option(5, "--escalation-budget", min=1, max=20),
    tau: float = typer.Option(0.70, "--tau", min=0.0, max=1.0),
    max_hops: int = typer.Option(2, "--max-hops", min=0, max=2),
    reserve_cold: int = typer.Option(2, "--reserve-cold", min=0, max=20),
) -> None:
    """Generate manual, local-only background connection candidates from existing catalog data."""
    normalized_attention = attention.lower()
    normalized_cold = cold.lower()
    if normalized_attention != "recent":
        console.print("Attention mode must be: recent")
        raise typer.Exit(2)
    if normalized_cold != "older":
        console.print("Cold mode must be: older")
        raise typer.Exit(2)
    if reserve_cold > escalation_budget:
        console.print("reserve-cold cannot exceed escalation-budget")
        raise typer.Exit(2)
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_background_connection_outputs(
            cfg.repo_root,
            db.assets(),
            db.edges(),
            scan_id=scan_id,
            attention=normalized_attention,
            cold=normalized_cold,
            limit=limit,
            escalation_budget=escalation_budget,
            tau=tau,
            max_hops=max_hops,
            reserve_cold=reserve_cold,
        )
    console.print_json(data=result)


@recommend_app.command("proposals")
def recommend_proposals(
    hub: Optional[Path] = typer.Option(None),
    engine: str = typer.Option("both", "--engine"),
    per_asset_limit: int = typer.Option(3, min=1, max=20),
    portfolio_limit: int = typer.Option(20, min=1, max=200),
    review_sample: int = typer.Option(25, min=1, max=200),
) -> None:
    """Generate bottom-up and/or top-down candidate proposals from the current catalog."""
    normalized_engine = engine.lower()
    if normalized_engine not in {"bottom-up", "top-down", "both"}:
        console.print("Engine must be one of: bottom-up, top-down, both")
        raise typer.Exit(2)
    selected_engine = cast(ProposalEngineOption, normalized_engine)
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        bottom_up, top_down, comparison = run_proposal_engines(
            assets=db.assets(),
            edges=db.edges(),
            alerts=db.alerts(open_only=True),
            scan_id=scan_id,
            engine=selected_engine,
            per_asset_limit=per_asset_limit,
            portfolio_limit=portfolio_limit,
            review_sample=review_sample,
            roadmap_context=load_roadmap_relevance_context(cfg.repo_root),
        )
    paths = write_proposal_outputs(cfg.repo_root, bottom_up, top_down, comparison)
    comparison_summary = {key: value for key, value in comparison.items() if key != "review_sample"}
    console.print_json(
        data={
            "scan_id": scan_id,
            "engine": normalized_engine,
            "bottom_up_count": len(bottom_up),
            "top_down_count": len(top_down),
            "comparison": comparison_summary,
            "outputs": paths,
        }
    )


@recommend_app.command("calibration-reports")
def recommend_calibration_reports(
    hub: Optional[Path] = typer.Option(None),
    sample_size: int = typer.Option(25, "--sample-size", min=1, max=100),
) -> None:
    """Write generated phase-2 scoring, orphan, and synergy calibration review reports."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_phase2_calibration_reports(
            cfg.repo_root,
            db.assets(),
            db.alerts(open_only=True),
            db.synergies(),
            sample_size=sample_size,
        )
    console.print_json(data=result)


@recommend_app.command("calibration-review-summary")
def recommend_calibration_review_summary(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
) -> None:
    """Summarize phase-2 asset scoring calibration review progress."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    records = load_asset_calibration_reviews(path)
    summary, output = write_asset_calibration_summary(cfg.repo_root, records, path)
    console.print_json(data={"review_file": str(path), "output": output, "summary": summary})


@recommend_app.command("calibration-review-label")
def recommend_calibration_review_label(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    asset_id: Optional[str] = typer.Option(None, "--asset-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    score_rating: Optional[str] = typer.Option(None, "--score-rating"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    false_negative_note: Optional[str] = typer.Option(None, "--false-negative-note"),
    weight_change_note: Optional[str] = typer.Option(None, "--weight-change-note"),
    notes: Optional[str] = typer.Option(None, "--notes"),
) -> None:
    """Update one phase-2 asset calibration review record with human labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_asset_calibration_review_file(
            path,
            sample_id=sample_id,
            asset_id=asset_id,
            reviewer=reviewer,
            score_rating=score_rating,
            false_positive_reason=false_positive_reason,
            false_negative_note=false_negative_note,
            weight_change_note=weight_change_note,
            notes=notes,
        )
        write_asset_calibration_summary(cfg.repo_root, load_asset_calibration_reviews(path), path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "updated": updated.model_dump(mode="json"),
            "summary": summary,
        }
    )


@recommend_app.command("calibration-review-queue")
def recommend_calibration_review_queue(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    status: str = typer.Option("pending", "--status"),
    band: str = typer.Option("all", "--band"),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    """List asset calibration review queue items with generated score context."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path

    status_value = status.lower()
    band_value = band.lower()
    if status_value not in {"pending", "reviewed", "all"}:
        console.print("Status must be one of: pending, reviewed, all")
        raise typer.Exit(2)
    if band_value not in {"low", "medium", "high", "all"}:
        console.print("Band must be one of: low, medium, high, all")
        raise typer.Exit(2)
    try:
        queue = build_asset_calibration_review_queue(
            load_asset_calibration_reviews(path),
            status=status_value,  # type: ignore[arg-type]
            band=band_value,  # type: ignore[arg-type]
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), **queue})


@recommend_app.command("calibration-review-export-csv")
def recommend_calibration_review_export_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Export phase-2 asset calibration reviews to a human-editable CSV."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    output_path = output or cfg.repo_root / "processed" / "calibration" / "asset_rating_batch.csv"
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not output_path.is_absolute():
        output_path = cfg.repo_root / output_path
    records = load_asset_calibration_reviews(review_path)
    written = write_asset_calibration_review_csv(output_path, records)
    console.print_json(
        data={"review_file": str(review_path), "output": written, "row_count": len(records)}
    )


@recommend_app.command("calibration-review-import-csv")
def recommend_calibration_review_import_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    csv_file: Optional[Path] = typer.Option(None, "--csv-file"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
) -> None:
    """Import human-edited phase-2 asset calibration review CSV labels."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    csv_path = csv_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_batch.csv"
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not csv_path.is_absolute():
        csv_path = cfg.repo_root / csv_path
    try:
        result = import_asset_calibration_review_csv(
            review_path, csv_path, default_reviewer=reviewer
        )
        write_asset_calibration_summary(
            cfg.repo_root, load_asset_calibration_reviews(review_path), review_path
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("calibration-evidence")
def recommend_calibration_evidence(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Write tracked roadmap evidence only after asset calibration review is complete."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    records = load_asset_calibration_reviews(path)
    try:
        summary, evidence_path = write_asset_calibration_evidence(
            cfg.repo_root, records, path, output
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": evidence_path, "summary": summary})


@recommend_app.command("phase25-score-delta")
def recommend_phase25_score_delta(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
    json_output: Optional[Path] = typer.Option(None, "--json-output"),
) -> None:
    """Compare reviewed Phase 2 labels against current Phase 2.5 v0.3 scores."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        result = write_phase25_score_delta_validation(
            cfg.repo_root,
            load_asset_calibration_reviews(path),
            load_catalog_assets(cfg.repo_root / "processed" / "catalog" / "assets.jsonl"),
            scan_summary=scan_summary,
            output=output,
            json_output=json_output,
        )
    console.print_json(data={"review_file": str(path), **result})


@recommend_app.command("downstream-pilots")
def recommend_downstream_pilots(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(10, min=1, max=50),
) -> None:
    """Write a generated candidate pack for selecting a downstream governance pilot."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_downstream_pilot_candidates(cfg.repo_root, db.assets(), limit=limit)
    console.print_json(data=result)


@recommend_app.command("roadmap-readiness")
def recommend_roadmap_readiness(hub: Optional[Path] = typer.Option(None)) -> None:
    """Write planning-only readiness templates for later roadmap phases."""
    cfg = _cfg(hub=hub)
    console.print_json(data=write_phase45_readiness_reports(cfg.repo_root))


@recommend_app.command("proposal-review-summary")
def recommend_proposal_review_summary(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
) -> None:
    """Summarize filled proposal review JSONL labels without changing roadmap state."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    reviews = load_proposal_reviews(path)
    summary, output = write_proposal_review_results_summary(cfg.repo_root, reviews, path)
    console.print_json(data={"review_file": str(path), "output": output, "summary": summary})


@recommend_app.command("proposal-review-label")
def recommend_proposal_review_label(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    proposal_id: Optional[str] = typer.Option(None, "--proposal-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    usefulness: Optional[str] = typer.Option(None, "--usefulness"),
    safety: Optional[str] = typer.Option(None, "--safety"),
    novelty: Optional[str] = typer.Option(None, "--novelty"),
    actionability: Optional[str] = typer.Option(None, "--actionability"),
    decision: Optional[str] = typer.Option(None, "--decision"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    false_negative_note: Optional[str] = typer.Option(None, "--false-negative-note"),
    useful_example_note: Optional[str] = typer.Option(None, "--useful-example-note"),
) -> None:
    """Update one proposal review JSONL record with human calibration labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_proposal_review_file(
            path,
            sample_id=sample_id,
            proposal_id=proposal_id,
            reviewer=reviewer,
            usefulness=usefulness,
            safety=safety,
            novelty=novelty,
            actionability=actionability,
            decision=decision,
            notes=notes,
            false_positive_reason=false_positive_reason,
            false_negative_note=false_negative_note,
            useful_example_note=useful_example_note,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "updated": updated.model_dump(mode="json"),
            "summary": summary,
        }
    )


@recommend_app.command("proposal-review-queue")
def recommend_proposal_review_queue(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    bottom_up_file: Optional[Path] = typer.Option(None, "--bottom-up-file"),
    top_down_file: Optional[Path] = typer.Option(None, "--top-down-file"),
    status: str = typer.Option("pending", "--status"),
    engine: str = typer.Option("all", "--engine"),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    """List proposal review queue items joined with proposal context."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    bottom_path = (
        bottom_up_file or cfg.repo_root / "processed" / "proposals" / "bottom_up_proposals.jsonl"
    )
    top_path = (
        top_down_file or cfg.repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
    )
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not bottom_path.is_absolute():
        bottom_path = cfg.repo_root / bottom_path
    if not top_path.is_absolute():
        top_path = cfg.repo_root / top_path

    status_value = status.lower()
    engine_value = engine.lower()
    engine_map = {
        "all": "all",
        "bottom-up": "bottom_up_self_proposal",
        "bottom_up_self_proposal": "bottom_up_self_proposal",
        "top-down": "top_down_orchestration",
        "top_down_orchestration": "top_down_orchestration",
    }
    if status_value not in {"pending", "reviewed", "all"}:
        console.print("Status must be one of: pending, reviewed, all")
        raise typer.Exit(2)
    if engine_value not in engine_map:
        console.print("Engine must be one of: all, bottom-up, top-down")
        raise typer.Exit(2)
    try:
        queue = build_proposal_review_queue(
            load_proposal_reviews(review_path),
            load_generated_proposals(bottom_path, top_path),
            status=status_value,  # type: ignore[arg-type]
            engine=engine_map[engine_value],  # type: ignore[arg-type]
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(review_path),
            "bottom_up_file": str(bottom_path),
            "top_down_file": str(top_path),
            **queue,
        }
    )


@recommend_app.command("proposal-review-export-csv")
def recommend_proposal_review_export_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    bottom_up_file: Optional[Path] = typer.Option(None, "--bottom-up-file"),
    top_down_file: Optional[Path] = typer.Option(None, "--top-down-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
    unblind_output: Optional[Path] = typer.Option(None, "--unblind-output"),
    blind: bool = typer.Option(True, "--blind/--include-engine"),
) -> None:
    """Export proposal review records and proposal context to a human-editable CSV."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    bottom_path = (
        bottom_up_file or cfg.repo_root / "processed" / "proposals" / "bottom_up_proposals.jsonl"
    )
    top_path = (
        top_down_file or cfg.repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
    )
    output_path = output or cfg.repo_root / "processed" / "proposals" / "proposal_review_batch.csv"
    unblind_path = (
        unblind_output
        or cfg.repo_root / "processed" / "proposals" / "proposal_review_unblind_map.csv"
    )
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not bottom_path.is_absolute():
        bottom_path = cfg.repo_root / bottom_path
    if not top_path.is_absolute():
        top_path = cfg.repo_root / top_path
    if not output_path.is_absolute():
        output_path = cfg.repo_root / output_path
    if not unblind_path.is_absolute():
        unblind_path = cfg.repo_root / unblind_path
    reviews = load_proposal_reviews(review_path)
    proposals = load_generated_proposals(bottom_path, top_path)
    written = write_proposal_review_csv(output_path, reviews, proposals, blind=blind)
    unblind_written = write_proposal_review_unblind_map(unblind_path, reviews) if blind else None
    console.print_json(
        data={
            "review_file": str(review_path),
            "bottom_up_file": str(bottom_path),
            "top_down_file": str(top_path),
            "output": written,
            "blind": blind,
            "unblind_output": unblind_written,
            "row_count": len(reviews),
        }
    )


@recommend_app.command("proposal-review-import-csv")
def recommend_proposal_review_import_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    csv_file: Optional[Path] = typer.Option(None, "--csv-file"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
) -> None:
    """Import validated human labels from proposal review CSV back into review JSONL."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    csv_path = csv_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_batch.csv"
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not csv_path.is_absolute():
        csv_path = cfg.repo_root / csv_path
    try:
        result = import_proposal_review_csv(review_path, csv_path, default_reviewer=reviewer)
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("proposal-calibration-evidence")
def recommend_proposal_calibration_evidence(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
    default_path: Optional[str] = typer.Option(None, "--default-path"),
    default_rationale: Optional[str] = typer.Option(None, "--default-rationale"),
) -> None:
    """Write tracked-ready roadmap evidence only after proposal calibration review is complete."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    reviews = load_proposal_reviews(path)
    try:
        summary, evidence_path = write_proposal_calibration_evidence(
            cfg.repo_root,
            reviews,
            path,
            output,
            default_path=default_path,
            default_rationale=default_rationale,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": evidence_path, "summary": summary})


@orphan_app.command("run")
def orphan_run(
    source: Path = typer.Option(..., "--src"),
    executable: str = "orphan-radar",
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    console.print_json(data=run_orphan_radar(cfg.repo_root, source, executable))


if __name__ == "__main__":
    app()
