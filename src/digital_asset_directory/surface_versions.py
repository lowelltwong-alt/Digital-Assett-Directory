"""Enrollment contract surface-version tracking.

Surface versions are repo-contract compatibility markers. They are not runtime
authority, and missing blocks mean a repo is legacy until a reviewed enrollment
update wave installs the current contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ids import stable_id
from .transport import TRANSPORT_SURFACE_VERSION, data_path
from .utils import atomic_write_text, json_dumps, utc_now

GRAPH_SURFACE_VERSION = "1.0.0"
MCP_SURFACE_VERSION = "1.0.0"
JOURNAL_SURFACE_VERSION = "1.0.0"
EVENTS_SURFACE_VERSION = "1.0.0"

SURFACE_VERSION_ORDER = ("transport", "graph", "mcp", "journal", "events")
EXPECTED_SURFACE_VERSIONS = {
    "transport": TRANSPORT_SURFACE_VERSION,
    "graph": GRAPH_SURFACE_VERSION,
    "mcp": MCP_SURFACE_VERSION,
    "journal": JOURNAL_SURFACE_VERSION,
    "events": EVENTS_SURFACE_VERSION,
}

SURFACE_VERSION_AUTHORITY_BOUNDARY = (
    "Surface-version reports and queue rows are central candidate metadata. "
    "They identify enrollment-contract drift only; they never authorize writes "
    "to target repos or make generated graph/MCP/journal/event data authoritative."
)


def graph_surface_contract_block() -> dict[str, Any]:
    return {
        "surface_version": GRAPH_SURFACE_VERSION,
        "mode": "central_read_only_generated_surfaces",
        "registry_ref": "dad://hub/Digital-Assett-Directory/registry/graph-surface-registry.json",
        "freshness_policy": {
            "fresh": "hashes_match",
            "stale": "warn_only",
            "inconsistent": "block",
        },
        "authority_boundary": (
            "Graph surfaces are generated candidate projections. They cannot override "
            "AGENTS.md, reviewed registries, schemas, audit records, Git/CI gates, or "
            "human approval gates."
        ),
    }


def mcp_surface_contract_block() -> dict[str, Any]:
    return {
        "surface_version": MCP_SURFACE_VERSION,
        "mode": "local_stdio_read_only",
        "remote_mcp_enabled": False,
        "vendor_sdk_required": False,
        "write_tools_enabled": False,
        "adapter_authority": "optional_wrapper_only",
        "authority_boundary": (
            "MCP is a read-only adapter over DAD registries and generated surfaces. "
            "It is not source authority and cannot perform writes."
        ),
    }


def journal_surface_contract_block() -> dict[str, Any]:
    return {
        "surface_version": JOURNAL_SURFACE_VERSION,
        "mode": "plan_only_until_human_gate",
        "checkpoint_scope": "DAD_DATA_ROOT data plane only",
        "checkpoint_threshold": ">=200 new records or >=24h",
        "source_repo_writes": False,
        "authority_boundary": (
            "Journal checkpoint rows are data-plane evidence only. They do not authorize "
            "a push or make generated graph content authoritative."
        ),
    }


def events_surface_contract_block() -> dict[str, Any]:
    return {
        "surface_version": EVENTS_SURFACE_VERSION,
        "mode": "append_only_candidate_metadata",
        "local_outbox": ".digital-asset/events/outbox.jsonl",
        "central_log": "processed/events/event_log.jsonl",
        "write_boundary": (
            "Events are explicit candidate metadata emissions. Normal recurring DAD "
            "operation remains limited to .digital-asset/mail/**."
        ),
        "authority_boundary": (
            "Event records are operational evidence only; they do not approve, verify, "
            "recommend, or authorize source repo changes."
        ),
    }


def expected_contract_surface_blocks() -> dict[str, dict[str, Any]]:
    return {
        "graph": graph_surface_contract_block(),
        "mcp": mcp_surface_contract_block(),
        "journal": journal_surface_contract_block(),
        "events": events_surface_contract_block(),
    }


def contract_surface_statuses(contract: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    contract_obj = contract if isinstance(contract, Mapping) else {}
    for surface_id in SURFACE_VERSION_ORDER:
        expected = EXPECTED_SURFACE_VERSIONS[surface_id]
        block = contract_obj.get(surface_id)
        seen = ""
        issue = ""
        if block is None:
            status = "legacy"
            issue = "surface_block_missing"
        elif not isinstance(block, Mapping):
            status = "invalid"
            issue = "surface_block_invalid"
        else:
            seen = str(block.get("surface_version") or "")
            if not seen:
                status = "legacy"
                issue = "surface_version_missing"
            elif seen == expected:
                status = "current"
            else:
                status = "stale"
                issue = "surface_version_mismatch"
        rows.append(
            {
                "surface": surface_id,
                "status": status,
                "surface_version": seen,
                "expected_surface_version": expected,
                "issue": issue,
                "update_needed": status != "current",
            }
        )
    return rows


def surface_version_status_report_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports") / "surface_version_status.json"


def surface_version_upgrade_queue_path(hub_root: Path) -> Path:
    return data_path(hub_root, "central_mail") / "staged" / "surface-version-upgrade-queue.jsonl"


def _read_contract(repo_root: Path) -> tuple[str, dict[str, Any]]:
    contract_path = repo_root / ".digital-asset" / "dad-integration.json"
    if not contract_path.exists():
        return "missing", {}
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "invalid", {}
    return ("readable", payload) if isinstance(payload, dict) else ("invalid", {})


def _write_protection_by_repo(
    transport_repos: Sequence[Mapping[str, Any]] | None,
) -> dict[str, bool]:
    rows: dict[str, bool] = {}
    for row in transport_repos or []:
        repo_id = str(row.get("id", "")).strip()
        if repo_id:
            rows[repo_id] = bool(row.get("write_protected", False))
    return rows


def _contract_record(
    policy: Any,
    *,
    write_protected: bool,
) -> dict[str, Any]:
    repo_id = str(getattr(policy, "id", "") or getattr(policy, "alias", ""))
    repo_root = Path(getattr(policy, "path"))
    contract_status, contract = _read_contract(repo_root)
    surface_rows = contract_surface_statuses(contract if contract_status == "readable" else {})
    update_rows = [row for row in surface_rows if row["update_needed"]]
    if contract_status == "missing":
        classification = "contract_missing"
    elif contract_status == "invalid":
        classification = "contract_invalid"
    elif update_rows:
        classification = "update_available"
    else:
        classification = "current"
    return {
        "repo_id": repo_id,
        "repo_alias": str(getattr(policy, "alias", repo_id)),
        "repo_path": str(repo_root),
        "policy_wave": str(getattr(policy, "wave", "")),
        "contract_status": contract_status,
        "classification": classification,
        "write_protected": write_protected,
        "surfaces": surface_rows,
        "update_needed_surfaces": [row["surface"] for row in update_rows],
    }


def build_surface_version_status(
    hub_root: Path,
    *,
    enrollment_policies: Sequence[Any],
    transport_repos: Sequence[Mapping[str, Any]] | None = None,
    wave: str = "",
) -> dict[str, Any]:
    """Write a central read-only report and deduped update queue rows."""
    hub_root = hub_root.resolve()
    generated_at = utc_now()
    protection = _write_protection_by_repo(transport_repos)
    records = [
        _contract_record(
            policy,
            write_protected=protection.get(str(getattr(policy, "id", "")), False),
        )
        for policy in enrollment_policies
        if bool(getattr(policy, "enrollment_enabled", True))
        and (not wave or str(getattr(policy, "wave", "")) == wave)
    ]
    report = {
        "schema_version": "dad.surface_versions.status.v1",
        "generated_at": generated_at,
        "wave": wave,
        "expected_surface_versions": dict(EXPECTED_SURFACE_VERSIONS),
        "repo_count": len(records),
        "classification_counts": _count(records, "classification"),
        "surface_update_counts": _surface_update_counts(records),
        "records": records,
        "authority_boundary": SURFACE_VERSION_AUTHORITY_BOUNDARY,
    }
    report_path = surface_version_status_report_path(hub_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(report_path, json_dumps(report, pretty=True) + "\n")

    queue_path = surface_version_upgrade_queue_path(hub_root)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_queue_keys(queue_path)
    appended = 0
    with queue_path.open("a", encoding="utf-8") as handle:
        for record in records:
            if record["contract_status"] != "readable":
                continue
            for surface in record["surfaces"]:
                if not surface["update_needed"]:
                    continue
                queue_key = stable_id(
                    "surface-version-upgrade",
                    record["repo_id"],
                    surface["surface"],
                    surface["expected_surface_version"],
                )
                if queue_key in existing:
                    continue
                delivery_rule = (
                    "central_only for write-protected repos; do not mutate target repo"
                    if record["write_protected"]
                    else "candidate mail/update-plan only after reviewed enrollment gate"
                )
                handle.write(
                    json.dumps(
                        {
                            "queue_key": queue_key,
                            "repo_id": record["repo_id"],
                            "surface": surface["surface"],
                            "classification": surface["status"],
                            "current_surface_version": surface["surface_version"] or "legacy",
                            "expected_surface_version": surface["expected_surface_version"],
                            "issue": surface["issue"],
                            "staged_at": generated_at,
                            "wave": wave,
                            "delivery_rule": delivery_rule,
                            "write_protected": record["write_protected"],
                            "review_status": "candidate",
                            "authority_boundary": SURFACE_VERSION_AUTHORITY_BOUNDARY,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                existing.add(queue_key)
                appended += 1
    return {
        **report,
        "report_path": str(report_path),
        "queue_path": str(queue_path),
        "queue_appended": appended,
    }


def _existing_queue_keys(queue_path: Path) -> set[str]:
    keys: set[str] = set()
    if not queue_path.exists():
        return keys
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            key = str(payload.get("queue_key", ""))
            if key:
                keys.add(key)
    return keys


def _count(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _surface_update_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {surface: 0 for surface in SURFACE_VERSION_ORDER}
    for record in records:
        for surface in record.get("surfaces", []):
            if isinstance(surface, Mapping) and surface.get("update_needed"):
                surface_id = str(surface.get("surface", ""))
                counts[surface_id] = counts.get(surface_id, 0) + 1
    return counts
