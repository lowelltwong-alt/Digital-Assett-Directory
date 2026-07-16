"""Unified local read-only cockpit companion for DAD Capability OS."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
from typing import Any

from .agent_families import agent_family_health
from .entity_identity import fold_state as fold_entity_state, read_events as read_entity_events
from .portfolio_intents import fold_plan_index, read_events as read_intent_events
from .portfolio_weekly_digest import build_weekly_digest
from .runtime_resolver import load_adapter_registry
from .harness_engineering import load_harness_registry
from .autonomy_control import load_autonomy_registry
from .portability_control import health_snapshot as portability_health_snapshot
from .transport import data_path
from .utils import atomic_write_text, json_dumps


AUTHORITY_BOUNDARY = (
    "The Capability OS cockpit is a local read-only projection. Controls prepare request "
    "packets only; they cannot execute, schedule, notify, mutate Git, change identity, "
    "activate a harness, lift quarantine, or grant authority."
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_capability_os_cockpit(
    repo_root: Path,
    hub_root: Path,
    *,
    today_items: list[dict[str, Any]] | None = None,
    previous_fingerprints: list[str] | None = None,
    usage_rows: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    plan_index = fold_plan_index(read_intent_events(hub_root))
    entity_state = fold_entity_state(read_entity_events(hub_root))
    digest = build_weekly_digest(
        plan_index,
        today_items=today_items,
        previous_fingerprints=previous_fingerprints,
    )
    family_health = agent_family_health(repo_root)
    runtime_registry = load_adapter_registry(repo_root)
    harness_registry = load_harness_registry(repo_root)
    autonomy_registry = load_autonomy_registry(repo_root)
    portability_health = portability_health_snapshot(repo_root, now=now)
    usage = list(usage_rows or [])
    usage_summary = {
        "row_count": len(usage),
        "token_status": "reported_or_estimated_or_unknown_per_row",
        "total_reported_tokens": sum(
            int(row.get("tokens", 0)) for row in usage if row.get("token_status") == "reported"
        ),
        "total_known_cost": round(
            sum(float(row.get("cost", 0.0)) for row in usage if row.get("cost_status") == "known"),
            6,
        ),
        "historical_views": ["daily", "weekly", "monthly", "all_time"],
    }
    views = {
        "plan_memory_and_forgotten_work": digest["inventory"],
        "related_plans_families_libraries_graph": {
            "entity_count": len(entity_state["entities"]),
            "candidate_relation_count": len(entity_state["relations"]),
        },
        "partial_build_recovery": {
            "candidate_count": digest["inventory"]["unfinished_plan_count"],
            "mutation_authorized": False,
        },
        "automation_pulse": {
            "weekly_recovery": digest["activation_status"],
            "schedule": digest["schedule_candidate"],
            "last_delivery": "unknown",
        },
        "runtime_and_harness_health": {
            "adapter_count": len(runtime_registry["adapters"]),
            "live_runtime_snapshot_status": "not_supplied",
            "harness_family_id": harness_registry["family_id"],
            "harness_status": harness_registry["status"],
        },
        "portable_capability_health": {
            "policy_revision_id": portability_health["policy_revision_id"],
            "baseline_id": portability_health["baseline_id"],
            "coverage": portability_health["coverage"],
            "finding_counts": portability_health["finding_counts"],
            "backlog_count": portability_health["backlog_count"],
            "model_calls": portability_health["model_calls"],
        },
        "incidents_and_quarantine": {
            "global_kill_status": "not_observed",
            "quarantine_status": "not_observed",
            "automatic_recovery_allowed": autonomy_registry["automatic_recovery_allowed"],
        },
        "tokens_and_cost": usage_summary,
        "portfolio": {
            "family_count": family_health["summary"]["family_count"],
            "family_issue_count": family_health["summary"]["issue_count"],
        },
    }
    controls = [
        {"control": name, "behavior": "create_request_packet", "execution_authorized": False}
        for name in ("pause", "kill", "acknowledge", "snooze", "resume_request")
    ]
    merged_decisions: list[dict[str, Any]] = []
    seen_decisions: set[str] = set()
    for row in [*portability_health["decisions"], *digest["asks"]]:
        fingerprint = _digest({
            "title": row.get("title", ""),
            "artifact_id": row.get("artifact_id", ""),
            "recommended_action": row.get("recommended_action", "inspect"),
        })
        if fingerprint not in seen_decisions:
            seen_decisions.add(fingerprint)
            merged_decisions.append(row)
    body = {"views": views, "decisions": merged_decisions[:3], "controls": controls}
    return {
        "schema_version": "dad.capability_os_cockpit.v1",
        "generated_at": observed,
        "cockpit_id": "dad:capability-os-cockpit:" + _digest(body).split(":", 1)[1],
        **body,
        "maximum_immediate_decisions": 3,
        "local_bind": "127.0.0.1",
        "external_javascript": False,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def capability_os_cockpit_html(cockpit: dict[str, Any]) -> str:
    cards = []
    for name, value in cockpit["views"].items():
        cards.append(
            f"<section><h2>{escape(name.replace('_', ' ').title())}</h2>"
            f"<pre>{escape(json_dumps(value, pretty=True))}</pre></section>"
        )
    decisions = "".join(
        f"<li>{escape(str(row.get('title', 'Decision')))} — {escape(str(row.get('recommended_action', 'inspect')))}</li>"
        for row in cockpit["decisions"]
    ) or "<li>No new immediate decisions.</li>"
    controls = ", ".join(escape(row["control"]) for row in cockpit["controls"])
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>DAD Capability OS</title>"
        "<style>body{font-family:system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}"
        "section{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap}</style>"
        "</head><body><h1>DAD Capability OS</h1><h2>Immediate decisions</h2><ol>"
        + decisions
        + f"</ol><p>Request-only controls: {controls}</p>{''.join(cards)}"
        + f"<footer>{escape(cockpit['authority_boundary'])}</footer></body></html>"
    )


def write_capability_os_cockpit(hub_root: Path, cockpit: dict[str, Any]) -> dict[str, Any]:
    root = data_path(hub_root, "portfolio_reports")
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "capability-os-cockpit.json"
    html_path = root / "capability-os-cockpit.html"
    # HTML is prepared first; the JSON projection is the publication commit
    # marker, so a failure cannot advertise a new JSON snapshot with stale HTML.
    atomic_write_text(html_path, capability_os_cockpit_html(cockpit))
    atomic_write_text(json_path, json_dumps(cockpit) + "\n")
    return {
        "json": str(json_path),
        "html": str(html_path),
        "publication_commit_marker": str(json_path),
        "execution_authorized": False,
    }


__all__ = ["AUTHORITY_BOUNDARY", "build_capability_os_cockpit", "capability_os_cockpit_html", "write_capability_os_cockpit"]
