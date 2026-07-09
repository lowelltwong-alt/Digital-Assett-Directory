"""Read-only transport upgrade-wave status helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .transport import (
    AUTHORITY_BOUNDARY,
    TRANSPORT_IMPLEMENTATION_VERSION,
    TRANSPORT_SURFACE_VERSION,
    data_path,
    read_transport_upgrade_queue,
)
from .utils import utc_now

ENROLLMENT_PLAN_DIR = Path("processed") / "enrollment" / "plans"


def enrollment_policy_keys(policy: Any) -> set[str]:
    """Return stable match keys for a reviewed enrollment policy."""
    values = {
        str(getattr(policy, "id", "")),
        str(getattr(policy, "alias", "")),
        str(getattr(policy, "path", "")),
        str(getattr(policy, "path", "")).replace("\\", "/"),
    }
    try:
        resolved = getattr(policy, "path").resolve()
        values.add(str(resolved))
        values.add(str(resolved).replace("\\", "/"))
    except Exception:
        pass
    return {value.strip().casefold() for value in values if value and value.strip()}


def select_transport_upgrade_policies_from_queue(
    hub_root: Path,
    enrollment_policies: Sequence[Any],
    *,
    wave: str,
    requested_repos: Sequence[str] | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Select reviewed enrollment policies from the central transport queue."""
    hub_root = hub_root.resolve()
    queue = read_transport_upgrade_queue(hub_root)
    effective_rows = _latest_queue_rows_by_repo(queue["rows"])
    audit_status, audit_payload = _read_json_object(
        data_path(hub_root, "central_reports") / "transport_audit.json"
    )
    audit_classifications = (
        _audit_classifications_by_repo(audit_payload)
        if audit_status == "readable"
        else {}
    )
    requested = {
        item.strip().casefold()
        for item in (requested_repos or [])
        if item.strip() and item.strip().casefold() != "all"
    }
    policies_by_key: dict[str, Any] = {}
    for policy in enrollment_policies:
        for key in enrollment_policy_keys(policy):
            policies_by_key[key] = policy

    selected: list[Any] = []
    seen_policy_ids: set[str] = set()
    skipped: list[dict[str, Any]] = []
    for row in effective_rows:
        repo_id = str(row.get("repo_id", "")).strip()
        if not repo_id:
            skipped.append({"repo_id": "", "reason": "missing_repo_id"})
            continue
        audit_classification = audit_classifications.get(repo_id.casefold())
        if audit_classification in {"current", "no_dad_surface"}:
            skipped.append(
                {
                    "repo_id": repo_id,
                    "reason": "superseded_by_current_audit",
                    "audit_classification": audit_classification,
                }
            )
            continue
        if audit_classifications and audit_classification is None:
            skipped.append({"repo_id": repo_id, "reason": "not_in_current_audit"})
            continue
        if row.get("expected_surface_version") != TRANSPORT_SURFACE_VERSION:
            skipped.append({"repo_id": repo_id, "reason": "stale_surface_version"})
            continue
        if row.get("expected_implementation_version") != TRANSPORT_IMPLEMENTATION_VERSION:
            skipped.append({"repo_id": repo_id, "reason": "stale_implementation_version"})
            continue
        row_keys = {repo_id.casefold()}
        policy = policies_by_key.get(repo_id.casefold())
        if policy is not None:
            row_keys.update(enrollment_policy_keys(policy))
        if requested and not (requested & row_keys):
            skipped.append({"repo_id": repo_id, "reason": "not_requested"})
            continue
        if bool(row.get("write_protected", False)):
            skipped.append({"repo_id": repo_id, "reason": "write_protected_central_only"})
            continue
        if str(row.get("review_status", "")) not in {"candidate", "queued", ""}:
            skipped.append(
                {
                    "repo_id": repo_id,
                    "reason": "queue_row_not_candidate",
                    "review_status": str(row.get("review_status", "")),
                }
            )
            continue
        if policy is None:
            skipped.append({"repo_id": repo_id, "reason": "no_reviewed_enrollment_policy"})
            continue
        if wave and getattr(policy, "wave", "") != wave:
            skipped.append(
                {
                    "repo_id": repo_id,
                    "reason": "wrong_wave",
                    "policy_wave": str(getattr(policy, "wave", "")),
                }
            )
            continue
        policy_id = str(getattr(policy, "id", ""))
        if policy_id in seen_policy_ids:
            skipped.append({"repo_id": repo_id, "reason": "duplicate_policy"})
            continue
        selected.append(policy)
        seen_policy_ids.add(policy_id)

    return selected, {
        "schema_version": "dad.transport.upgrade_queue_selection.v1",
        "queue_path": queue["queue_path"],
        "queue_row_count": queue["row_count"],
        "effective_row_count": len(effective_rows),
        "invalid_row_count": queue["invalid_row_count"],
        "selected_count": len(selected),
        "selected_repo_ids": [str(getattr(policy, "id", "")) for policy in selected],
        "skipped_count": len(skipped),
        "skipped": skipped,
        "skipped_by_reason": _count_reason(skipped),
        "audit_filter": {
            "report_status": audit_status,
            "filter_applied": bool(audit_classifications),
            "current_or_absent_rows_supersede_queue_history": True,
        },
        "authority_boundary": (
            "Transport queue selection is read-only. It can only select reviewed "
            "enrollment.repos policy rows for an update plan; it never applies "
            "updates, writes protected repos, or fixes tracked spool JSONL."
        ),
    }


def build_transport_upgrade_status(
    hub_root: Path,
    *,
    transport_repos: Sequence[Mapping[str, Any]] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
    wave: str = "transport-surface-v1",
    requested_repos: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Summarize the repo upgrade wave without discovering or mutating repos."""
    hub_root = hub_root.resolve()
    selected, selection = select_transport_upgrade_policies_from_queue(
        hub_root,
        enrollment_policies or [],
        wave=wave,
        requested_repos=requested_repos or [],
    )
    queue = read_transport_upgrade_queue(hub_root)
    report_path = data_path(hub_root, "central_reports") / "transport_audit.json"
    report_status, report_payload = _read_json_object(report_path)
    plan_id = f"update-{wave or 'selected'}"
    plan_json_path = hub_root / ENROLLMENT_PLAN_DIR / f"{plan_id}.json"
    plan_md_path = hub_root / ENROLLMENT_PLAN_DIR / f"{plan_id}.md"
    plan_status, plan_payload = _read_json_object(plan_json_path)
    transport_rows = list(transport_repos or [])
    policies = list(enrollment_policies or [])
    effective_rows = _latest_queue_rows_by_repo(queue["rows"])
    protected_repo_ids = [
        str(row.get("repo_id", "")).strip()
        for row in effective_rows
        if bool(row.get("write_protected", False)) and str(row.get("repo_id", "")).strip()
    ]
    unmatched_repo_ids = [
        str(item.get("repo_id", ""))
        for item in selection["skipped"]
        if item.get("reason") == "no_reviewed_enrollment_policy"
    ]

    status = _upgrade_status(
        report_status=report_status,
        queue_row_count=int(queue["row_count"]),
        invalid_row_count=int(queue["invalid_row_count"]),
        selected_count=len(selected),
        skipped_by_reason=selection["skipped_by_reason"],
    )
    plan_summary = {
        "plan_id": plan_id,
        "json_path": str(plan_json_path),
        "markdown_path": str(plan_md_path),
        "json_exists": plan_json_path.exists(),
        "markdown_exists": plan_md_path.exists(),
        "json_status": plan_status,
        "item_count": plan_payload.get("item_count") if plan_status == "readable" else None,
        "repo_ids": [
            str(item.get("repo_id", ""))
            for item in plan_payload.get("items", [])
            if isinstance(item, dict)
        ]
        if plan_status == "readable"
        else [],
    }
    return {
        "schema_version": "dad.transport.upgrade_status.v1",
        "generated_at": utc_now(),
        "status": status,
        "wave": wave,
        "requested_repos": list(requested_repos or []),
        "transport_surface_version": TRANSPORT_SURFACE_VERSION,
        "audit": {
            "report_path": str(report_path),
            "report_status": report_status,
            "repo_count": report_payload.get("repo_count") if report_status == "readable" else None,
            "classification_counts": report_payload.get("classification_counts", {})
            if report_status == "readable"
            else {},
            "hub_classification": report_payload.get("hub", {}).get("classification")
            if isinstance(report_payload.get("hub"), dict)
            else None,
        },
        "queue": {
            "queue_path": queue["queue_path"],
            "row_count": queue["row_count"],
            "effective_row_count": len(effective_rows),
            "invalid_row_count": queue["invalid_row_count"],
            "candidate_row_count": sum(
                1
                for row in effective_rows
                if str(row.get("review_status", "")) in {"candidate", "queued", ""}
            ),
            "write_protected_row_count": len(protected_repo_ids),
            "protected_repo_ids": protected_repo_ids,
            "unmatched_repo_ids": unmatched_repo_ids,
        },
        "reviewed_policy": {
            "transport_repo_count": len(transport_rows),
            "enrollment_policy_count": len(policies),
            "transport_repo_ids": [str(row.get("id", "")) for row in transport_rows],
            "enrollment_repo_ids": [str(getattr(policy, "id", "")) for policy in policies],
        },
        "selection": selection,
        "plan_artifacts": plan_summary,
        "operator_next_steps": _operator_next_steps(status, wave=wave),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _read_json_object(path: Path) -> tuple[str, dict[str, Any]]:
    if not path.exists():
        return "missing", {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "invalid", {"error": str(exc)}
    if not isinstance(payload, dict):
        return "invalid", {"error": "JSON document is not an object"}
    return "readable", payload


def _count_reason(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _latest_queue_rows_by_repo(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Collapse append-only queue history to the latest row for each repo."""
    missing_repo_rows: list[Mapping[str, Any]] = []
    latest_by_repo: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        repo_id = str(row.get("repo_id", "")).strip().casefold()
        if not repo_id:
            missing_repo_rows.append(row)
            continue
        if repo_id in latest_by_repo:
            del latest_by_repo[repo_id]
        latest_by_repo[repo_id] = row
    return [*missing_repo_rows, *latest_by_repo.values()]


def _audit_classifications_by_repo(payload: Mapping[str, Any]) -> dict[str, str]:
    rows = payload.get("records", [])
    if not isinstance(rows, list):
        return {}
    classifications: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        repo_id = str(row.get("repo_id", "")).strip().casefold()
        classification = str(row.get("classification", "")).strip()
        if repo_id and classification:
            classifications[repo_id] = classification
    return classifications


def _live_skipped_by_reason(skipped_by_reason: Mapping[str, int]) -> dict[str, int]:
    benign_history_reasons = {
        "superseded_by_current_audit",
        "not_in_current_audit",
    }
    return {
        reason: count
        for reason, count in skipped_by_reason.items()
        if reason not in benign_history_reasons
    }


def _upgrade_status(
    *,
    report_status: str,
    queue_row_count: int,
    invalid_row_count: int,
    selected_count: int,
    skipped_by_reason: Mapping[str, int],
) -> str:
    if invalid_row_count:
        return "queue_needs_repair"
    if report_status != "readable":
        return "audit_missing_or_invalid"
    if queue_row_count == 0:
        return "no_queue_rows_for_reviewed_policy"
    if selected_count:
        return "ready_for_update_plan"
    live_skipped_by_reason = _live_skipped_by_reason(skipped_by_reason)
    if live_skipped_by_reason and set(live_skipped_by_reason) <= {"write_protected_central_only"}:
        return "protected_repos_central_only"
    if skipped_by_reason and not live_skipped_by_reason:
        return "no_current_upgrade_rows"
    return "review_required"


def _operator_next_steps(status: str, *, wave: str) -> list[str]:
    if status == "ready_for_update_plan":
        return [f"asset-dir enroll update-plan --wave {wave} --from-transport-queue"]
    if status == "queue_needs_repair":
        return ["inspect processed/mail/staged/transport-upgrade-queue.jsonl"]
    if status == "audit_missing_or_invalid":
        return ["asset-dir transport audit"]
    if status == "protected_repos_central_only":
        return ["review protected repo rows centrally; do not write target repos"]
    if status == "no_current_upgrade_rows":
        return ["asset-dir transport audit", "no non-protected current upgrade rows selected"]
    if status == "no_queue_rows_for_reviewed_policy":
        return ["asset-dir transport audit", "review config/sources*.yaml transport policy rows"]
    return ["review skipped reasons before planning or applying any upgrade wave"]
