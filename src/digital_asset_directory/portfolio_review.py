"""Strict read-only review packet for the DAD Portfolio OS.

This composes frozen candidate projections and categorical operational health.
It never scans Git, appends events, records decisions, runs a checker, dispatches
an agent, or activates a task, notification, executor, or routine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from .ids import stable_id
from .portfolio_cockpit import SCHEMA_VERSION as COCKPIT_SCHEMA_VERSION
from .portfolio_cockpit import projection_hash, schema_validation_problems
from .portfolio_reconciliation import SCHEMA_VERSION as RECONCILIATION_SCHEMA_VERSION
from .portfolio_reconciliation import portfolio_reconciliation_semantic_problems
from .portfolio_shaping import SCHEMA_VERSION as SHAPING_SCHEMA_VERSION
from .portfolio_shaping import portfolio_shaping_semantic_problems
from .transport import data_path
from .utils import atomic_write_text, json_dumps

SCHEMA_VERSION = "dad.portfolio_review_packet.v2"
METHOD_ID = "dad.portfolio-review-packet.v2"
LEGACY_SHAPING_SCHEMA_VERSION = "dad.portfolio_workstream_shaping.v1"
METHODOLOGY_REF = "docs/frontier/collaboration/14_PORTFOLIO_REVIEW_PACKET.md"
HEALTH_SOURCE_IDS = (
    "daemon",
    "daily_review",
    "mail",
    "journal",
    "transport",
    "execution",
    "roadmap",
)
CORE_SOURCE_IDS = ("cockpit", "reconciliation", "shaping")
DASHBOARD_LANES = (
    "now",
    "next",
    "waiting",
    "blocked",
    "failed",
    "completed",
    "intentionally_quiet",
)
HEALTH_STATES = ("ready", "attention", "blocked", "unavailable", "not_applicable")
RESPONSE_LABELS = ("review_now", "useful", "noisy", "missing_context", "defer")
_PATH_RE = re.compile(
    r"(?:(?:[A-Za-z]:[\\/])|(?:\\\\(?:[?.]\\)?[^\\/\s]+[\\/])|"
    r"(?:^|(?<=[\s\"'=(]))/(?!/)[^\s\"'<>]+|(?:^|(?<=[\s\"'=(]))~[\\/])",
    re.IGNORECASE,
)
_SAFE_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
_FORBIDDEN_FIELDS = frozenset({"command", "apply", "accept", "dispatch", "execute"})
_BAND_LABELS = {
    "human_decision": "Human decision needed",
    "integrity_unknown": "Integrity evidence unknown",
    "dirty_recovery": "Dirty work recovery",
    "dependency_unlock": "Dependency unlock",
    "related_active_neglect": "Related active work review",
    "weekly_maintenance": "Weekly maintenance",
}
_BAND_STATUS = {
    "human_decision": "waiting",
    "integrity_unknown": "blocked",
    "dirty_recovery": "review_required",
    "dependency_unlock": "ready_next",
    "related_active_neglect": "review_required",
    "weekly_maintenance": "review_required",
}
AUTHORITY_BOUNDARY = (
    "This local review packet is a snapshot-bound candidate projection. It cannot "
    "scan or mutate Git, append ledger events, record decisions, run validators or "
    "checkers, dispatch agents, start tasks, schedules, routines, or notifications, "
    "or change source authority. Its HTML and JSON are derived read-only reports."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewSettings:
    today_limit: int = 3
    lane_limit: int = 20
    fresh_after_hours: int = 26
    future_tolerance_hours: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.today_limit <= 3:
            raise ValueError("today_limit must be between 1 and 3")
        if not 1 <= self.lane_limit <= 50:
            raise ValueError("lane_limit must be between 1 and 50")
        if self.fresh_after_hours < 1 or self.future_tolerance_hours < 0:
            raise ValueError("invalid freshness policy")


def _canonical_hash(value: Any) -> str:
    body = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_code(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text if _SAFE_CODE_RE.fullmatch(text) else fallback


def _codes(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({_safe_code(value, "source_detail_omitted") for value in values if str(value)})


def _source_time(source_id: str, value: Mapping[str, Any]) -> str:
    keys = {
        "daemon": ("cycle_completed_at", "generated_at"),
        "daily_review": ("generated_at",),
        "mail": ("last_checked_at",),
        "journal": ("generated_at",),
        "transport": ("generated_at",),
        "execution": ("as_of",),
        "roadmap": ("last_checked_at",),
    }.get(source_id, ("generated_at",))
    return next((str(value[key]) for key in keys if value.get(key)), "")


def _source_descriptor(
    name: str,
    value: Any,
    *,
    now: datetime,
    settings: ReviewSettings,
    expected_schema: str = "",
    schema_name: str = "",
    schema_root: Path | None = None,
    semantic_validator: Callable[[dict[str, Any]], list[str]] | None = None,
    legacy_schema: str = "",
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "name": name,
            "status": "unavailable" if value is None else "invalid",
            "freshness": "unknown",
            "schema_version": "",
            "generated_at": "",
            "source_hash": "" if value is None else _canonical_hash(value),
            "problems": ["source_unavailable" if value is None else "source_not_object"],
        }
    problems: list[str] = []
    schema_version = str(value.get("schema_version", ""))
    if legacy_schema and schema_version == legacy_schema:
        problems.append("upgrade_required")
    elif expected_schema and schema_version != expected_schema:
        problems.append("unexpected_schema")
    if schema_name and schema_root is not None:
        structural = schema_validation_problems(value, schema_root, schema_name)
        if structural:
            problems.append("schema_invalid")
        elif semantic_validator is not None and semantic_validator(value):
            problems.append("semantic_invalid")
    raw_status = str(value.get("status", "")).casefold()
    if name in HEALTH_SOURCE_IDS and raw_status in {"missing", "unavailable"}:
        problems.append("source_unavailable")
    elif name in HEALTH_SOURCE_IDS and raw_status in {"invalid", "error", "future"}:
        problems.append("source_invalid")
    generated = _parse_time(
        value.get("generated_at", "") if name in CORE_SOURCE_IDS else _source_time(name, value)
    )
    if generated is None:
        freshness = "unknown"
        problems.append("generated_at_invalid_or_missing")
    else:
        age = (now - generated).total_seconds() / 3600
        if age < -settings.future_tolerance_hours:
            freshness = "future"
            problems.append("generated_at_in_future")
        elif age > settings.fresh_after_hours:
            freshness = "stale"
            problems.append("source_stale")
        else:
            freshness = "current"
    unavailable = "source_unavailable" in problems
    invalid = any(
        item
        in {
            "source_invalid",
            "schema_invalid",
            "semantic_invalid",
            "unexpected_schema",
            "upgrade_required",
        }
        for item in problems
    )
    return {
        "name": name,
        "status": "unavailable" if unavailable else "invalid" if invalid else "observed",
        "freshness": freshness,
        "schema_version": schema_version,
        "generated_at": generated.isoformat() if generated else "",
        "source_hash": projection_hash(value),
        "problems": sorted(set(problems)),
    }


def _health_row(
    lane_id: str,
    source_id: str,
    status: str,
    reason_code: str,
    *,
    blocks_clearance: bool,
    source_hash: str,
    count: int = 0,
) -> dict[str, Any]:
    return {
        "health_id": stable_id(METHOD_ID, "health", lane_id),
        "lane_id": lane_id,
        "source_id": source_id,
        "status": status,
        "reason_code": reason_code,
        "blocks_clearance": blocks_clearance,
        "count": max(0, int(count)),
        "source_hash": source_hash,
    }


def _status_health(
    lane_id: str,
    source_id: str,
    descriptor: dict[str, Any],
    payload: Any,
    *,
    ready: set[str],
    attention: set[str] = frozenset(),
) -> dict[str, Any]:
    raw = str(payload.get("status", "")).casefold() if isinstance(payload, dict) else ""
    if descriptor["status"] == "unavailable":
        state, reason = "unavailable", f"{lane_id}_source_unavailable"
    elif descriptor["status"] == "invalid" or descriptor["freshness"] in {"future", "unknown"}:
        state, reason = "blocked", f"{lane_id}_source_invalid"
    elif descriptor["freshness"] == "stale":
        state, reason = "blocked", f"{lane_id}_source_stale"
    elif raw in ready:
        state, reason = "ready", f"{lane_id}_ready"
    elif raw in attention:
        state, reason = "attention", f"{lane_id}_{_safe_code(raw, 'attention')}"
    else:
        state, reason = "blocked", f"{lane_id}_{_safe_code(raw, 'unknown')}"
    return _health_row(
        lane_id,
        source_id,
        state,
        reason,
        blocks_clearance=state != "ready",
        source_hash=descriptor["source_hash"],
    )


def _build_health(
    cockpit: Any, health_inputs: Mapping[str, Any], sources: Mapping[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    daemon, daily, mail = (health_inputs.get(key) for key in ("daemon", "daily_review", "mail"))
    journal, transport = (health_inputs.get(key) for key in ("journal", "transport"))
    execution, roadmap = (health_inputs.get(key) for key in ("execution", "roadmap"))
    rows = [
        _status_health(
            "daemon", "daemon", sources["daemon"], daemon, ready={"fresh"}, attention={"degraded"}
        ),
        _status_health(
            "daily_review",
            "daily_review",
            sources["daily_review"],
            daily,
            ready={"ready", "fresh", "complete", "observed"},
            attention={"complete_with_errors", "attention"},
        ),
        _status_health("mail", "mail", sources["mail"], mail, ready={"fresh"}, attention={"stale"}),
    ]
    if sources["journal"]["status"] != "observed":
        state, reason = "unavailable", "journal_source_unavailable"
    elif sources["journal"]["freshness"] != "current":
        state, reason = "blocked", "journal_source_not_current"
    elif bool(journal.get("checkpoint_due")):
        state, reason = "attention", "journal_checkpoint_due"
    else:
        state, reason = "ready", "journal_ready"
    rows.append(
        _health_row(
            "journal",
            "journal",
            state,
            reason,
            blocks_clearance=state != "ready",
            source_hash=sources["journal"]["source_hash"],
            count=int(journal.get("new_record_count", 0)) if isinstance(journal, dict) else 0,
        )
    )
    rows.append(
        _status_health(
            "transport",
            "transport",
            sources["transport"],
            transport,
            ready={"ready", "fresh", "complete", "observed", "current"},
            attention={"attention", "upgrade_required", "partial"},
        )
    )
    cockpit_lanes = cockpit.get("lanes", {}) if isinstance(cockpit, dict) else {}
    dirty_count = len(cockpit_lanes.get("dirty_worktrees", []))
    human_attention_count = len(cockpit_lanes.get("human_gates", []))
    rows.append(
        _health_row(
            "target_repo",
            "cockpit",
            "attention" if dirty_count else "ready",
            "target_repo_dirty" if dirty_count else "target_repo_clean",
            blocks_clearance=bool(dirty_count),
            source_hash=sources["cockpit"]["source_hash"],
            count=dirty_count,
        )
    )
    dispatch_count = active_lease_count = attempt_count = 0
    executor_available = False
    if isinstance(execution, dict):
        summary = execution.get("summary", {})
        attempts = execution.get("attempt_journal", {}).get("summary", {})
        dispatch_count = int(summary.get("dispatch_count", 0) or 0)
        active_lease_count = int(summary.get("active_lease_count", 0) or 0)
        attempt_count = int(attempts.get("dispatch_count", 0) or 0)
        executor_available = bool(execution.get("executor", {}).get("available", False))
    checker_needed = bool(dispatch_count or active_lease_count or attempt_count)
    if not checker_needed and sources["execution"]["status"] == "observed":
        checker_state, checker_reason, checker_blocks = (
            "not_applicable",
            "checker_not_applicable_manual_mode",
            False,
        )
    elif sources["execution"]["status"] != "observed":
        checker_state, checker_reason, checker_blocks = (
            "unavailable",
            "checker_source_unavailable",
            True,
        )
    else:
        checker_state, checker_reason, checker_blocks = (
            "unavailable",
            "checker_evidence_unavailable",
            True,
        )
    rows.append(
        _health_row(
            "checker",
            "execution",
            checker_state,
            checker_reason,
            blocks_clearance=checker_blocks,
            source_hash=sources["execution"]["source_hash"],
            count=dispatch_count + attempt_count,
        )
    )
    execution_state = "attention" if checker_needed else "ready"
    execution_reason = (
        "execution_shadow_has_pending_state" if checker_needed else "execution_disabled_safe"
    )
    if executor_available:
        execution_state, execution_reason = "blocked", "executor_unexpectedly_available"
    rows.append(
        _health_row(
            "execution_shadow",
            "execution",
            execution_state,
            execution_reason,
            blocks_clearance=execution_state != "ready",
            source_hash=sources["execution"]["source_hash"],
            count=dispatch_count + active_lease_count,
        )
    )
    roadmap_pending = 0
    if isinstance(roadmap, dict) and isinstance(roadmap.get("phases"), dict):
        roadmap_pending = sum(
            isinstance(row, dict) and row.get("computed_status") == "awaiting_human_gate"
            for row in roadmap["phases"].values()
        )
    human_count = human_attention_count + roadmap_pending
    if sources["roadmap"]["status"] != "observed":
        human_state, human_reason = "unavailable", "human_decision_source_unavailable"
    elif human_count:
        human_state, human_reason = "attention", "human_decision_pending"
    else:
        human_state, human_reason = "ready", "human_decision_clear"
    rows.append(
        _health_row(
            "human_decision",
            "roadmap",
            human_state,
            human_reason,
            blocks_clearance=human_state != "ready",
            source_hash=sources["roadmap"]["source_hash"],
            count=human_count,
        )
    )
    return rows


def _attachments(reconciliation: Any, shaping: Any, today_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(reconciliation, dict):
        for source in reconciliation.get("review_queue", []):
            if not isinstance(source, dict):
                continue
            attention_ids = sorted(set(source.get("attention_ids", [])))
            if not attention_ids or not set(attention_ids) <= today_ids:
                continue
            subject = str(source.get("proposal_id", ""))
            rows.append(
                {
                    "attachment_id": stable_id(
                        METHOD_ID, "reconciliation", subject, *attention_ids
                    ),
                    "kind": "reconciliation",
                    "source_review_id": str(source.get("review_id", "")),
                    "subject_ref": subject,
                    "revision_ref": "",
                    "attention_ids": attention_ids,
                    "label": "Exact binding review",
                    "detail_code": "binding_candidate",
                }
            )
    if isinstance(shaping, dict):
        cases = {
            str(row.get("case_id", "")): row
            for row in shaping.get("cases", [])
            if isinstance(row, dict)
        }
        for source in shaping.get("review_queue", []):
            if not isinstance(source, dict):
                continue
            attention_ids = sorted(set(source.get("attention_ids", [])))
            if not attention_ids or not set(attention_ids) <= today_ids:
                continue
            subject = str(source.get("case_id", ""))
            kind = _safe_code(source.get("case_kind"), "shaping")
            rows.append(
                {
                    "attachment_id": stable_id(METHOD_ID, "shaping", subject, *attention_ids),
                    "kind": "shaping",
                    "source_review_id": str(source.get("review_id", "")),
                    "subject_ref": subject,
                    "revision_ref": str(cases.get(subject, {}).get("revision_id", "")),
                    "attention_ids": attention_ids,
                    "label": f"{kind.replace('_', ' ').title()} shaping review",
                    "detail_code": _safe_code(source.get("evidence_tier"), "evidence_unknown"),
                }
            )
    return sorted(rows, key=lambda row: (row["kind"], row["attachment_id"]))


def _card(
    lane: str,
    kind: str,
    subject: str,
    label: str,
    status: str,
    *,
    reasons: list[str] = (),
    attachments: list[str] = (),
    sources: list[str] = (),
) -> dict[str, Any]:
    return {
        "item_id": stable_id(METHOD_ID, "dashboard", lane, kind, subject),
        "lane": lane,
        "kind": kind,
        "subject_ref": subject,
        "label": label,
        "status": status,
        "reason_codes": sorted(set(reasons)),
        "attachment_refs": sorted(set(attachments)),
        "source_refs": sorted(set(sources)),
    }


def _dashboard(
    cockpit: Any,
    attachments: list[dict[str, Any]],
    health: list[dict[str, Any]],
    roadmap: Any,
    shaping: Any,
    *,
    now: datetime,
    settings: ReviewSettings,
) -> dict[str, list[dict[str, Any]]]:
    lanes: dict[str, list[dict[str, Any]]] = {name: [] for name in DASHBOARD_LANES}
    by_attention: dict[str, list[str]] = {}
    for attachment in attachments:
        for attention_id in attachment["attention_ids"]:
            by_attention.setdefault(attention_id, []).append(attachment["attachment_id"])
    if isinstance(cockpit, dict):
        for source in cockpit.get("today", [])[: settings.today_limit]:
            if not isinstance(source, dict):
                continue
            subject = str(source.get("attention_id", ""))
            band = _safe_code(source.get("band"), "integrity_unknown")
            lanes["now"].append(
                _card(
                    "now",
                    "attention",
                    subject,
                    _BAND_LABELS.get(band, "Portfolio evidence review"),
                    _BAND_STATUS.get(band, "review_required"),
                    reasons=_codes(source.get("reasons")),
                    attachments=by_attention.get(subject, []),
                    sources=["cockpit"],
                )
            )
        decided_cases = {
            str(row.get("case_id", ""))
            for row in (shaping.get("cases", []) if isinstance(shaping, dict) else [])
            if isinstance(row, dict)
            and isinstance(row.get("decision"), dict)
            and row["decision"].get("state") in {"active", "stale"}
        }
        for attachment in [
            row
            for row in attachments
            if not (row.get("kind") == "shaping" and row.get("subject_ref") in decided_cases)
        ][: settings.today_limit]:
            lanes["next"].append(
                _card(
                    "next",
                    attachment["kind"],
                    attachment["attachment_id"],
                    attachment["label"],
                    "review_available",
                    reasons=[attachment["detail_code"]],
                    attachments=[attachment["attachment_id"]],
                    sources=[attachment["kind"]],
                )
            )
        source_lanes = cockpit.get("lanes", {})
        for source in source_lanes.get("human_gates", [])[: settings.lane_limit]:
            if isinstance(source, dict):
                lanes["waiting"].append(
                    _card(
                        "waiting",
                        "attention",
                        str(source.get("attention_id", "")),
                        "Human decision needed",
                        "waiting",
                        reasons=["human_decision"],
                        sources=["cockpit"],
                    )
                )
        now_ids = {row["subject_ref"] for row in lanes["now"]}
        for source in cockpit.get("attention_queue", []):
            if not isinstance(source, dict) or source.get("band") not in {
                "integrity_unknown",
                "dirty_recovery",
            }:
                continue
            subject = str(source.get("attention_id", ""))
            if subject in now_ids:
                continue
            band = str(source.get("band"))
            lanes["blocked"].append(
                _card(
                    "blocked",
                    "attention",
                    subject,
                    _BAND_LABELS[band],
                    "blocked",
                    reasons=_codes(source.get("reasons")),
                    sources=["cockpit"],
                )
            )
            if len(lanes["blocked"]) >= settings.lane_limit:
                break
        board = cockpit.get("board", {})
        for state in ("merged", "superseded", "archived"):
            for source in board.get(state, []):
                if isinstance(source, dict) and len(lanes["completed"]) < settings.lane_limit:
                    lanes["completed"].append(
                        _card(
                            "completed",
                            "workstream",
                            str(source.get("workstream_id", "")),
                            "Completed workstream",
                            state,
                            reasons=[state],
                            sources=["cockpit"],
                        )
                    )
        for state in ("paused", "snoozed", "incubating"):
            for source in board.get(state, []):
                if (
                    isinstance(source, dict)
                    and len(lanes["intentionally_quiet"]) < settings.lane_limit
                ):
                    lanes["intentionally_quiet"].append(
                        _card(
                            "intentionally_quiet",
                            "workstream",
                            str(source.get("workstream_id", "")),
                            "Intentionally quiet workstream",
                            state,
                            reasons=[state],
                            sources=["cockpit"],
                        )
                    )
    if isinstance(roadmap, dict) and isinstance(roadmap.get("phases"), dict):
        for phase_id, source in roadmap["phases"].items():
            if (
                not isinstance(source, dict)
                or source.get("computed_status") != "awaiting_human_gate"
            ):
                continue
            subject = _safe_code(phase_id, stable_id(METHOD_ID, "roadmap-phase", str(phase_id)))
            lanes["waiting"].append(
                _card(
                    "waiting",
                    "roadmap_phase",
                    subject,
                    "Roadmap human gate pending",
                    "waiting",
                    reasons=["awaiting_human_gate"],
                    sources=["roadmap"],
                )
            )
            if len(lanes["waiting"]) >= settings.lane_limit:
                break
    for row in health:
        if row["status"] in {"blocked", "unavailable"}:
            lanes["failed"].append(
                _card(
                    "failed",
                    "health",
                    row["health_id"],
                    "Control-plane health requires review",
                    row["status"],
                    reasons=[row["reason_code"]],
                    sources=[row["source_id"]],
                )
            )
    decision_lanes: dict[str, list[dict[str, Any]]] = {
        lane: [] for lane in DASHBOARD_LANES
    }
    if isinstance(shaping, dict):
        for case in shaping.get("cases", []):
            if not isinstance(case, dict) or not isinstance(case.get("decision"), dict):
                continue
            decision = case["decision"]
            state = str(decision.get("state", "none"))
            if state in {"none", "retracted"}:
                continue
            subject = str(decision.get("decision_id") or case.get("case_id", ""))
            manual_state = str(decision.get("manual_action_state", "none"))
            review_after = _parse_time(decision.get("review_after"))
            if state == "stale":
                lane, label, status, reason = (
                    "blocked",
                    "Shaping decision needs review",
                    "blocked",
                    "stale_decision",
                )
            elif manual_state == "failed":
                lane, label, status, reason = (
                    "failed",
                    "Manual recovery verification failed",
                    "failed",
                    "manual_recovery_failed",
                )
            elif manual_state == "verified":
                lane, label, status, reason = (
                    "completed",
                    "Manual recovery verified",
                    "verified",
                    "manual_recovery_verified",
                )
            elif manual_state == "aborted":
                lane, label, status, reason = (
                    "blocked",
                    "Manual recovery needs review",
                    "aborted",
                    "manual_recovery_aborted",
                )
            elif decision.get("choice_kind") == "defer" and review_after is not None:
                if review_after > now:
                    lane, label, status, reason = (
                        "intentionally_quiet",
                        "Deferred shaping decision",
                        "deferred",
                        "defer_review_scheduled",
                    )
                else:
                    lane, label, status, reason = (
                        "blocked",
                        "Deferred shaping decision needs review",
                        "review_due",
                        "defer_review_due",
                    )
            else:
                lane, label, status, reason = (
                    "waiting",
                    "Manual recovery pending",
                    "waiting",
                    "manual_recovery_pending",
                )
            decision_lanes[lane].append(
                _card(
                    lane,
                    "shaping_decision",
                    subject,
                    label,
                    status,
                    reasons=[reason],
                    sources=["shaping"],
                )
            )
    for lane in DASHBOARD_LANES:
        if lane in {"now", "next"}:
            continue
        lanes[lane] = (decision_lanes[lane] + lanes[lane])[: settings.lane_limit]
    return lanes


def _issues(
    sources: Mapping[str, dict[str, Any]], health: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []
    for name, descriptor in sources.items():
        if name in CORE_SOURCE_IDS and (
            descriptor["status"] != "observed" or descriptor["freshness"] != "current"
        ):
            blockers.append(
                {
                    "issue_id": stable_id(METHOD_ID, "blocker", name),
                    "kind": "core_source_not_current",
                    "source": name,
                    "severity": "danger",
                    "ref": descriptor["source_hash"],
                }
            )
        for problem in descriptor["problems"]:
            if problem in {
                "source_stale",
                "generated_at_in_future",
                "generated_at_invalid_or_missing",
            }:
                unknowns.append(
                    {
                        "issue_id": stable_id(METHOD_ID, "unknown", name, problem),
                        "kind": problem,
                        "source": name,
                        "severity": "warning",
                        "ref": descriptor["source_hash"],
                    }
                )
    for row in health:
        if row["status"] in {"blocked", "unavailable"} and row["blocks_clearance"]:
            blockers.append(
                {
                    "issue_id": stable_id(METHOD_ID, "health-blocker", row["health_id"]),
                    "kind": row["reason_code"],
                    "source": row["source_id"],
                    "severity": "danger",
                    "ref": row["health_id"],
                }
            )
        elif row["status"] == "attention" and row["blocks_clearance"]:
            unknowns.append(
                {
                    "issue_id": stable_id(METHOD_ID, "health-unknown", row["health_id"]),
                    "kind": row["reason_code"],
                    "source": row["source_id"],
                    "severity": "warning",
                    "ref": row["health_id"],
                }
            )

    def canonical(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            {row["issue_id"]: row for row in rows}.values(),
            key=lambda row: row["issue_id"],
        )

    return canonical(blockers), canonical(unknowns)


def _response_template(now_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "template_id": stable_id(METHOD_ID, "review-response-template"),
        "response_syntax": "<response_id>=<allowed_label>",
        "records_decision": False,
        "rows": [
            {
                "response_id": stable_id(METHOD_ID, "response", row["subject_ref"]),
                "attention_id": row["subject_ref"],
                "attachment_ids": row["attachment_refs"],
                "allowed_labels": list(RESPONSE_LABELS),
            }
            for row in now_rows
        ],
    }


def _fingerprints(
    dashboard: Mapping[str, list[dict[str, Any]]],
    health: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
) -> list[str]:
    material: list[dict[str, Any]] = []
    for lane in ("now", "next", "waiting", "blocked", "failed"):
        for row in dashboard[lane]:
            material.append(
                {
                    "kind": "dashboard",
                    "lane": lane,
                    "subject_ref": row["subject_ref"],
                    "status": row["status"],
                    "reason_codes": row["reason_codes"],
                    "attachment_refs": row["attachment_refs"],
                }
            )
    for row in health:
        material.append(
            {
                "kind": "health",
                "lane_id": row["lane_id"],
                "status": row["status"],
                "reason_code": row["reason_code"],
                "count": row["count"],
            }
        )
    for row in attachments:
        material.append(
            {
                "kind": "attachment",
                "attachment_id": row["attachment_id"],
                "revision_ref": row["revision_ref"],
            }
        )
    return sorted({_canonical_hash(row) for row in material})


def build_portfolio_review(
    cockpit: Any,
    reconciliation: Any,
    shaping: Any,
    health_inputs: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
    settings: ReviewSettings | None = None,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    """Build one candidate-only packet from frozen snapshots."""

    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    policy = settings or ReviewSettings()
    root = schema_root or Path(__file__).parents[2]
    operational = dict(health_inputs or {})
    sources = {
        "cockpit": _source_descriptor(
            "cockpit",
            cockpit,
            now=observed,
            settings=policy,
            expected_schema=COCKPIT_SCHEMA_VERSION,
            schema_name="portfolio_cockpit",
            schema_root=root,
        ),
        "reconciliation": _source_descriptor(
            "reconciliation",
            reconciliation,
            now=observed,
            settings=policy,
            expected_schema=RECONCILIATION_SCHEMA_VERSION,
            schema_name="portfolio_reconciliation",
            schema_root=root,
            semantic_validator=portfolio_reconciliation_semantic_problems,
        ),
        "shaping": _source_descriptor(
            "shaping",
            shaping,
            now=observed,
            settings=policy,
            expected_schema=SHAPING_SCHEMA_VERSION,
            schema_name="portfolio_workstream_shaping",
            schema_root=root,
            semantic_validator=portfolio_shaping_semantic_problems,
            legacy_schema=LEGACY_SHAPING_SCHEMA_VERSION,
        ),
    }
    for source_id in HEALTH_SOURCE_IDS:
        sources[source_id] = _source_descriptor(
            source_id, operational.get(source_id), now=observed, settings=policy
        )
    source_refs = {name: row["source_hash"] for name, row in sources.items()}
    health = _build_health(cockpit, operational, sources)
    today_ids = {
        str(row.get("attention_id", ""))
        for row in (cockpit.get("today", []) if isinstance(cockpit, dict) else [])
        if isinstance(row, dict)
    }
    current_shaping = (
        shaping
        if isinstance(shaping, dict) and shaping.get("schema_version") == SHAPING_SCHEMA_VERSION
        else None
    )
    attachments = _attachments(reconciliation, current_shaping, today_ids)
    dashboard = _dashboard(
        cockpit,
        attachments,
        health,
        operational.get("roadmap"),
        current_shaping,
        now=observed,
        settings=policy,
    )
    blockers, unknowns = _issues(sources, health)
    cockpit_summary = cockpit.get("summary", {}) if isinstance(cockpit, dict) else {}
    cockpit_queue = cockpit.get("attention_queue", []) if isinstance(cockpit, dict) else []
    recon_summary = reconciliation.get("summary", {}) if isinstance(reconciliation, dict) else {}
    shaping_summary = current_shaping.get("summary", {}) if current_shaping else {}
    shaping_coverage = current_shaping.get("coverage", {}) if current_shaping else {}
    coverage = {
        "attention_item_count": len(cockpit_queue),
        "today_item_count": len(dashboard["now"]),
        "attention_overflow_count": max(0, len(cockpit_queue) - len(dashboard["now"])),
        "attachment_count": len(attachments),
        "hidden_attachment_count": max(0, len(attachments) - len(dashboard["next"])),
        "workstream_count": int(cockpit_summary.get("workstream_count", 0) or 0),
        "eligible_workstream_count": int(shaping_summary.get("eligible_workstream_count", 0) or 0),
        "workstreams_without_exact_scope_count": len(
            shaping_coverage.get("workstreams_without_exact_bindings", [])
        ),
        "reconciliation_fully_reconciled": bool(recon_summary.get("fully_reconciled", False)),
        "shaping_complete": bool(shaping_summary.get("shaping_complete", False)),
        "operational_source_count": len(HEALTH_SOURCE_IDS),
        "health_lane_count": len(health),
    }
    core_ready = all(
        sources[name]["status"] == "observed" and sources[name]["freshness"] == "current"
        for name in CORE_SOURCE_IDS
    )
    all_clear = bool(
        core_ready
        and not blockers
        and not unknowns
        and not any(dashboard[lane] for lane in ("now", "next", "waiting", "blocked", "failed"))
        and coverage["attention_overflow_count"] == 0
        and coverage["workstream_count"] > 0
        and coverage["eligible_workstream_count"] > 0
        and coverage["workstreams_without_exact_scope_count"] == 0
        and coverage["reconciliation_fully_reconciled"]
        and coverage["shaping_complete"]
        and all(row["status"] in {"ready", "not_applicable"} for row in health)
    )
    summary = {
        "now_count": len(dashboard["now"]),
        "next_count": len(dashboard["next"]),
        "waiting_count": len(dashboard["waiting"]),
        "blocked_count": len(dashboard["blocked"]),
        "failed_count": len(dashboard["failed"]),
        "completed_count": len(dashboard["completed"]),
        "intentionally_quiet_count": len(dashboard["intentionally_quiet"]),
        "health_attention_count": sum(
            row["status"] not in {"ready", "not_applicable"} for row in health
        ),
        "blocker_count": len(blockers),
        "unknown_count": len(unknowns),
        "all_clear": all_clear,
    }
    upgrade_required = bool(
        isinstance(shaping, dict)
        and shaping.get("schema_version") == LEGACY_SHAPING_SCHEMA_VERSION
    )
    status = (
        "upgrade_required"
        if upgrade_required
        else "blocked_candidate"
        if not core_ready
        else "partial_candidate"
        if blockers or unknowns
        else "generated_candidate"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "status": status,
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "execution_authorized": False,
        "mutations_performed": False,
        "decision_recorded": False,
        "source_authority_mutated": False,
        "publication_scope": "derived_reports_only",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "methodology": {
            "method_id": METHOD_ID,
            "methodology_ref": METHODOLOGY_REF,
            "today_limit": policy.today_limit,
            "lane_limit": policy.lane_limit,
            "fresh_after_hours": policy.fresh_after_hours,
            "future_tolerance_hours": policy.future_tolerance_hours,
            "dashboard_lanes": list(DASHBOARD_LANES),
            "numeric_score_used": False,
            "creates_second_today_queue": False,
        },
        "sources": sources,
        "source_refs": source_refs,
        "health": health,
        "dashboard": dashboard,
        "attachments": attachments,
        "review_response_template": _response_template(dashboard["now"]),
        "coverage": coverage,
        "summary": summary,
        "blockers": blockers,
        "unknowns": unknowns,
        "material_fingerprints": _fingerprints(dashboard, health, attachments),
    }


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    rows = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(_walk(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk(child, (*path, str(index))))
    return rows


def portfolio_review_semantic_problems(packet: dict[str, Any]) -> list[str]:
    """Validate identities, clearance, summaries, and privacy invariants."""

    problems: set[str] = set()
    sources, refs = packet.get("sources", {}), packet.get("source_refs", {})
    if set(sources) != set((*CORE_SOURCE_IDS, *HEALTH_SOURCE_IDS)):
        problems.add("source_inventory_mismatch")
    for name, row in sources.items():
        if refs.get(name) != row.get("source_hash"):
            problems.add(f"source_hash_reference_mismatch:{name}")
    dashboard = packet.get("dashboard", {})
    if list(dashboard) != list(DASHBOARD_LANES):
        problems.add("dashboard_lane_inventory_mismatch")
    if len(dashboard.get("now", [])) > 3:
        problems.add("today_limit_exceeded")
    item_ids: set[str] = set()
    decision_contracts = {
        "manual_recovery_pending": (
            "waiting",
            "waiting",
            "Manual recovery pending",
        ),
        "stale_decision": (
            "blocked",
            "blocked",
            "Shaping decision needs review",
        ),
        "manual_recovery_failed": (
            "failed",
            "failed",
            "Manual recovery verification failed",
        ),
        "manual_recovery_verified": (
            "completed",
            "verified",
            "Manual recovery verified",
        ),
        "manual_recovery_aborted": (
            "blocked",
            "aborted",
            "Manual recovery needs review",
        ),
        "defer_review_scheduled": (
            "intentionally_quiet",
            "deferred",
            "Deferred shaping decision",
        ),
        "defer_review_due": (
            "blocked",
            "review_due",
            "Deferred shaping decision needs review",
        ),
    }
    for lane in DASHBOARD_LANES:
        for row in dashboard.get(lane, []):
            item_id = str(row.get("item_id", ""))
            if item_id in item_ids:
                problems.add("duplicate_dashboard_item")
            item_ids.add(item_id)
            if row.get("lane") != lane:
                problems.add("dashboard_lane_mismatch")
            expected = stable_id(
                METHOD_ID,
                "dashboard",
                lane,
                str(row.get("kind", "")),
                str(row.get("subject_ref", "")),
            )
            if item_id != expected:
                problems.add("dashboard_item_identity_mismatch")
            for key in ("reason_codes", "attachment_refs", "source_refs"):
                if row.get(key, []) != sorted(set(row.get(key, []))):
                    problems.add(f"dashboard_collection_not_canonical:{key}")
            if row.get("kind") == "shaping_decision":
                reasons = row.get("reason_codes", [])
                contract = decision_contracts.get(reasons[0]) if len(reasons) == 1 else None
                if contract != (lane, row.get("status"), row.get("label")):
                    problems.add("decision_card_contract_mismatch")
                if row.get("source_refs") != ["shaping"] or row.get("attachment_refs"):
                    problems.add("decision_card_provenance_mismatch")
    attachments = packet.get("attachments", [])
    attachment_ids = {row.get("attachment_id") for row in attachments}
    if len(attachment_ids) != len(attachments):
        problems.add("duplicate_attachment")
    today_ids = {row.get("subject_ref") for row in dashboard.get("now", [])}
    for row in attachments:
        if not set(row.get("attention_ids", [])) <= today_ids:
            problems.add("attachment_not_bound_to_today")
        expected = stable_id(
            METHOD_ID,
            row.get("kind", ""),
            row.get("subject_ref", ""),
            *row.get("attention_ids", []),
        )
        if row.get("attachment_id") != expected:
            problems.add("attachment_identity_mismatch")
    for row in dashboard.get("now", []):
        if not set(row.get("attachment_refs", [])) <= attachment_ids:
            problems.add("today_attachment_missing")
    template = packet.get("review_response_template", {})
    if template.get("rows") != _response_template(dashboard.get("now", []))["rows"]:
        problems.add("review_response_rows_mismatch")
    if template.get("records_decision") is not False:
        problems.add("review_response_authority_mismatch")
    health = packet.get("health", [])
    health_ids: set[str] = set()
    for row in health:
        health_id = str(row.get("health_id", ""))
        if health_id in health_ids:
            problems.add("duplicate_health_lane")
        health_ids.add(health_id)
        if health_id != stable_id(METHOD_ID, "health", str(row.get("lane_id", ""))):
            problems.add("health_identity_mismatch")
        if row.get("status") not in HEALTH_STATES:
            problems.add("health_status_invalid")
        if row.get("source_hash") != sources.get(row.get("source_id"), {}).get("source_hash"):
            problems.add("health_source_hash_mismatch")
    expected_counts = {
        "now_count": len(dashboard.get("now", [])),
        "next_count": len(dashboard.get("next", [])),
        "waiting_count": len(dashboard.get("waiting", [])),
        "blocked_count": len(dashboard.get("blocked", [])),
        "failed_count": len(dashboard.get("failed", [])),
        "completed_count": len(dashboard.get("completed", [])),
        "intentionally_quiet_count": len(dashboard.get("intentionally_quiet", [])),
        "health_attention_count": sum(
            row.get("status") not in {"ready", "not_applicable"} for row in health
        ),
        "blocker_count": len(packet.get("blockers", [])),
        "unknown_count": len(packet.get("unknowns", [])),
    }
    summary, coverage = packet.get("summary", {}), packet.get("coverage", {})
    for key, value in expected_counts.items():
        if summary.get(key) != value:
            problems.add(f"summary_mismatch:{key}")
    core_ready = all(
        sources.get(name, {}).get("status") == "observed"
        and sources.get(name, {}).get("freshness") == "current"
        for name in CORE_SOURCE_IDS
    )
    expected_clear = bool(
        core_ready
        and not packet.get("blockers")
        and not packet.get("unknowns")
        and not any(dashboard.get(lane) for lane in ("now", "next", "waiting", "blocked", "failed"))
        and coverage.get("attention_overflow_count") == 0
        and coverage.get("workstream_count", 0) > 0
        and coverage.get("eligible_workstream_count", 0) > 0
        and coverage.get("workstreams_without_exact_scope_count") == 0
        and coverage.get("reconciliation_fully_reconciled") is True
        and coverage.get("shaping_complete") is True
        and all(row.get("status") in {"ready", "not_applicable"} for row in health)
    )
    if summary.get("all_clear") is not expected_clear:
        problems.add("all_clear_mismatch")
    upgrade_required = "upgrade_required" in sources.get("shaping", {}).get("problems", [])
    expected_status = (
        "upgrade_required"
        if upgrade_required
        else "blocked_candidate"
        if not core_ready
        else "partial_candidate"
        if packet.get("blockers") or packet.get("unknowns")
        else "generated_candidate"
    )
    if packet.get("status") != expected_status:
        problems.add("review_status_mismatch")
    if packet.get("material_fingerprints") != _fingerprints(dashboard, health, attachments):
        problems.add("material_fingerprint_mismatch")
    if (
        packet.get("execution_authorized") is not False
        or packet.get("mutations_performed") is not False
        or packet.get("decision_recorded") is not False
        or packet.get("source_authority_mutated") is not False
        or packet.get("publication_scope") != "derived_reports_only"
        or packet.get("authority_boundary") != AUTHORITY_BOUNDARY
    ):
        problems.add("authority_boundary_mismatch")
    for path, value in _walk(packet):
        if path and path[-1].casefold() in _FORBIDDEN_FIELDS:
            problems.add("forbidden_action_field")
        if isinstance(value, str) and _PATH_RE.search(value):
            problems.add("raw_path_exposed")
    return sorted(problems)


_STYLE = """
:root{color-scheme:dark;--bg:#091019;--ink:#edf4f7;--muted:#9fb0bf;--line:#2a3a49;--hot:#ffb86b;--ok:#7bdba1;--bad:#ff7b8d}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#142332,var(--bg) 48%);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,sans-serif}.shell{width:min(1180px,calc(100% - 32px));margin:auto;padding:40px 0 64px}.skip{position:absolute;left:-9999px}.skip:focus{left:16px;top:16px;background:#fff;color:#000;padding:8px}.eyebrow{color:var(--hot);letter-spacing:.14em;text-transform:uppercase;font-size:.78rem}h1{font-size:clamp(2rem,5vw,4.8rem);line-height:.98;margin:.3em 0}h2{margin-top:34px}.muted{color:var(--muted);max-width:78ch}.stats,.health,.grid{display:grid;gap:12px}.stats{grid-template-columns:repeat(auto-fit,minmax(130px,1fr))}.health,.grid{grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}.card,.stat{background:linear-gradient(145deg,#14222f,#0c1620);border:1px solid var(--line);border-radius:16px;padding:16px}.stat strong{display:block;font-size:1.8rem}.stat span,.meta{color:var(--muted)}.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;margin:0 4px 4px 0;font-size:.76rem}.ready{color:var(--ok)}.blocked,.unavailable{color:var(--bad)}.attention{color:var(--hot)}code{overflow-wrap:anywhere}footer{margin-top:42px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted)}
"""


def _csp() -> str:
    return (
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )


def _card_html(row: Mapping[str, Any]) -> str:
    reasons = "".join(
        f'<span class="pill">{escape(str(code))}</span>' for code in row.get("reason_codes", [])
    )
    return (
        '<article class="card">'
        f'<div class="eyebrow">{escape(str(row.get("lane", "")))}</div>'
        f"<h3>{escape(str(row.get('label', '')))}</h3>"
        f'<p class="meta">{escape(str(row.get("status", "")))} &middot; '
        f"<code>{escape(str(row.get('subject_ref', '')))}</code></p>{reasons}</article>"
    )


def portfolio_review_html(packet: dict[str, Any]) -> str:
    """Render an inert, script-free review surface."""

    summary = packet["summary"]
    stats = "".join(
        f'<div class="stat"><strong>{summary[key]}</strong><span>{escape(label)}</span></div>'
        for key, label in (
            ("now_count", "now"),
            ("next_count", "next"),
            ("waiting_count", "waiting"),
            ("blocked_count", "blocked"),
            ("failed_count", "failed"),
            ("completed_count", "completed"),
        )
    )
    health = "".join(
        '<article class="card">'
        f'<div class="eyebrow">{escape(row["lane_id"])}</div>'
        f'<h3 class="{escape(row["status"])}">'
        f"{escape(row['status'].replace('_', ' ').title())}</h3>"
        f'<p class="meta">{escape(row["reason_code"])} &middot; {row["count"]}</p>'
        "</article>"
        for row in packet["health"]
    )
    sections = []
    for lane in DASHBOARD_LANES:
        rendered = "".join(_card_html(row) for row in packet["dashboard"][lane])
        rendered = rendered or '<p class="card muted">No items in this lane.</p>'
        sections.append(
            f"<h2>{escape(lane.replace('_', ' ').title())}</h2>"
            f'<section class="grid" aria-label="{escape(lane)}">{rendered}</section>'
        )
    clearance = "Clear" if summary["all_clear"] else "Not clear"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(_csp(), quote=True)}">
<title>DAD Portfolio Review</title><style>{_STYLE}</style></head>
<body><a class="skip" href="#main">Skip to main content</a><main id="main" class="shell">
<div class="eyebrow">DAD &middot; Portfolio review packet</div>
<h1>One review. No hidden green.</h1>
<p class="muted">{escape(clearance)}. Status: {escape(packet["status"])}. One snapshot-bound, read-only view of current attention and control-plane health.</p>
<section class="stats" aria-label="Review totals">{stats}</section>
<h2>Operational health</h2><section class="health" aria-label="Operational health">{health}</section>
{"".join(sections)}
<footer>Generated {escape(packet["generated_at"])}. Derived local report with no active controls.</footer>
</main></body></html>"""


def write_portfolio_review_outputs(
    hub_root: Path,
    packet: dict[str, Any],
    *,
    cockpit: Any,
    reconciliation: Any,
    shaping: Any,
    health_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild frozen sources, then publish HTML and the authoritative JSON cursor."""

    schema_problems = schema_validation_problems(packet, hub_root, "portfolio_review_packet")
    if schema_problems:
        raise ValueError("Invalid portfolio review packet: " + "; ".join(schema_problems))
    semantic_problems = portfolio_review_semantic_problems(packet)
    if semantic_problems:
        raise ValueError("Invalid portfolio review semantics: " + "; ".join(semantic_problems))
    generated = _parse_time(packet.get("generated_at"))
    if generated is None:
        raise ValueError("Invalid portfolio review packet: generated_at")
    policy = packet["methodology"]
    expected = build_portfolio_review(
        cockpit,
        reconciliation,
        shaping,
        health_inputs,
        now=generated,
        settings=ReviewSettings(
            today_limit=int(policy["today_limit"]),
            lane_limit=int(policy["lane_limit"]),
            fresh_after_hours=int(policy["fresh_after_hours"]),
            future_tolerance_hours=int(policy["future_tolerance_hours"]),
        ),
        schema_root=hub_root,
    )
    if packet != expected:
        raise ValueError("Invalid portfolio review semantics: projection_source_rebuild_mismatch")
    base = data_path(hub_root, "central_reports") / "portfolio_os"
    json_path, html_path = base / "review.json", base / "review.html"
    prior_json = json_path.read_text(encoding="utf-8") if json_path.exists() else None
    prior_html = html_path.read_text(encoding="utf-8") if html_path.exists() else None
    previous: list[str] = []
    if prior_json is not None:
        try:
            previous_packet = json.loads(prior_json)
            if isinstance(previous_packet, dict):
                previous = list(previous_packet.get("material_fingerprints", []))
        except json.JSONDecodeError:
            pass
    try:
        atomic_write_text(html_path, portfolio_review_html(packet))
        atomic_write_text(json_path, json_dumps(packet, pretty=True) + "\n")
    except Exception:
        for path, prior in ((html_path, prior_html), (json_path, prior_json)):
            if prior is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write_text(path, prior)
        raise
    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "status": packet["status"],
        "summary": packet["summary"],
        "today_changed": packet["material_fingerprints"] != previous,
        "review_response_template": packet["review_response_template"],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "generated_at": packet["generated_at"],
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "DASHBOARD_LANES",
    "HEALTH_SOURCE_IDS",
    "METHOD_ID",
    "ReviewSettings",
    "SCHEMA_VERSION",
    "build_portfolio_review",
    "portfolio_review_html",
    "portfolio_review_semantic_problems",
    "write_portfolio_review_outputs",
]
