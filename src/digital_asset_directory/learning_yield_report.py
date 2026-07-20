"""Monthly learning-loop yield projection (report-only, not scheduled)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .ids import stable_id
from .learning import agent_sessions_dir, raw_handoffs_dir, raw_lessons_dir
from .transport import data_path
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

SCHEMA_VERSION = "dad.learning_loop_yield_report.v1"
METHOD_ID = "dad.learning-loop-yield.v1"
REPORT_JSON = "learning_loop_yield.json"
REPORT_MD = "learning_loop_yield.md"
HISTORY_JSONL = "learning_loop_yield_history.jsonl"
AUTHORITY_BOUNDARY = (
    "Learning-loop yield is a report-only projection over source records "
    "(lessons, handoffs, sessions, usage ledgers). It does not score agents, "
    "trust self-ratings, schedule work, promote lessons, or mutate source "
    "records. Coverage may be coverage_unavailable when evidence is missing."
)

# Agent self-score / prediction fields that must never drive yield counts.
_FORBIDDEN_SCORE_FIELDS = frozenset(
    {
        "observed_usefulness",
        "self_score",
        "self_rating",
        "predicted_usefulness",
        "agent_confidence",
        "usefulness_self_report",
    }
)

LOOP_CATALOG: tuple[dict[str, str], ...] = (
    {
        "loop_id": "loop:lessons-and-handoffs",
        "label": "Lessons and handoffs",
        "written_source": "raw_lessons + raw_handoffs",
        "reuse_source": "later sessions citing lesson_id / handoff_id",
        "promotion_source": "review_status reviewed|promoted on lesson/handoff",
    },
    {
        "loop_id": "loop:lifecycle-rule-acks",
        "label": "Lifecycle and learning-rule acknowledgements",
        "written_source": "agent_sessions learning_rule_acknowledgements",
        "reuse_source": "midflight/postflight acknowledgements in window",
        "promotion_source": "not_applicable",
    },
    {
        "loop_id": "loop:usage-decision-traces",
        "label": "Usage decision traces",
        "written_source": "processed/usage/decision-traces.jsonl",
        "reuse_source": "trace_outcome reuse rows",
        "promotion_source": "promotion or adopt decisions",
    },
)


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _in_window(ts: datetime | None, start: datetime, end: datetime) -> bool:
    return ts is not None and start <= ts <= end


def _load_json_files(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in root.rglob("*.json"):
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    except OSError:
        return []
    return rows


def _strip_forbidden(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in _FORBIDDEN_SCORE_FIELDS}


def _coverage(exact: bool, partial: bool, evidence_present: bool) -> str:
    if not evidence_present:
        return "coverage_unavailable"
    if exact:
        return "exact"
    if partial:
        return "partial"
    return "coverage_unavailable"


def build_learning_yield_report(
    hub_root: Path,
    *,
    window_days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a candidate yield report from hub source records only."""

    if window_days < 1:
        raise ValueError("window_days must be >= 1")
    observed = (now or utc_now()).astimezone(timezone.utc)
    start = observed - timedelta(days=window_days)

    lessons = [_strip_forbidden(row) for row in _load_json_files(raw_lessons_dir(hub_root))]
    handoffs = [_strip_forbidden(row) for row in _load_json_files(raw_handoffs_dir(hub_root))]
    sessions = [_strip_forbidden(row) for row in _load_json_files(agent_sessions_dir(hub_root))]
    traces_path = data_path(hub_root, "usage") / "decision-traces.jsonl"
    traces = [_strip_forbidden(row) for row in _load_jsonl(traces_path)]
    traces_present = traces_path.is_file()

    lessons_written = [
        row
        for row in lessons
        if _in_window(_parse_ts(row.get("created_at") or row.get("recorded_at")), start, observed)
    ]
    handoffs_written = [
        row
        for row in handoffs
        if _in_window(_parse_ts(row.get("created_at") or row.get("recorded_at")), start, observed)
    ]
    lesson_ids = {
        str(row.get("lesson_id") or "")
        for row in lessons_written
        if row.get("lesson_id")
    }
    handoff_ids = {
        str(row.get("handoff_id") or "")
        for row in handoffs_written
        if row.get("handoff_id")
    }

    reused_lesson_ids: set[str] = set()
    reused_handoff_ids: set[str] = set()
    for session in sessions:
        created = _parse_ts(session.get("created_at") or session.get("closed_at"))
        if not _in_window(created, start, observed):
            continue
        blob = json.dumps(session, sort_keys=True)
        for lesson_id in lesson_ids:
            if lesson_id and lesson_id in blob:
                reused_lesson_ids.add(lesson_id)
        for handoff_id in handoff_ids:
            if handoff_id and handoff_id in blob:
                reused_handoff_ids.add(handoff_id)

    promoted = [
        row
        for row in [*lessons_written, *handoffs_written]
        if str(row.get("review_status") or "").lower()
        in {"reviewed", "promoted", "accepted"}
    ]

    ack_written = 0
    for session in sessions:
        created = _parse_ts(session.get("created_at") or session.get("closed_at"))
        if not _in_window(created, start, observed):
            continue
        acks = session.get("learning_rule_acknowledgements") or []
        if isinstance(acks, list):
            ack_written += len(acks)

    traces_written = [
        row
        for row in traces
        if _in_window(_parse_ts(row.get("observed_at") or row.get("created_at")), start, observed)
    ]
    traces_reused = [
        row
        for row in traces_written
        if str(row.get("trace_outcome") or row.get("outcome") or "").lower()
        in {"reused", "reuse", "applied", "adopted"}
    ]
    traces_promoted = [
        row
        for row in traces_written
        if str(row.get("decision") or row.get("trace_outcome") or "").lower()
        in {"promoted", "promote", "adopt", "accepted"}
    ]

    loops = [
        {
            **LOOP_CATALOG[0],
            "records_written": len(lessons_written) + len(handoffs_written),
            "records_reused": len(reused_lesson_ids) + len(reused_handoff_ids),
            "records_promoted": len(promoted),
            "reuse_coverage": _coverage(
                exact=bool(lesson_ids or handoff_ids),
                partial=bool(sessions),
                evidence_present=bool(lessons or handoffs or sessions),
            ),
        },
        {
            **LOOP_CATALOG[1],
            "records_written": ack_written,
            "records_reused": ack_written,
            "records_promoted": 0,
            "reuse_coverage": _coverage(
                exact=ack_written > 0,
                partial=bool(sessions),
                evidence_present=bool(sessions) or agent_sessions_dir(hub_root).is_dir(),
            ),
        },
        {
            **LOOP_CATALOG[2],
            "records_written": len(traces_written),
            "records_reused": len(traces_reused),
            "records_promoted": len(traces_promoted),
            "reuse_coverage": _coverage(
                exact=traces_present,
                partial=False,
                evidence_present=traces_present,
            ),
        },
    ]

    unknown = [
        loop["loop_id"]
        for loop in loops
        if loop["reuse_coverage"] == "coverage_unavailable"
    ]
    report_id = stable_id(
        "learning-loop-yield",
        str(window_days),
        observed.date().isoformat(),
        json_dumps(
            [
                {
                    "loop_id": loop["loop_id"],
                    "written": loop["records_written"],
                    "reused": loop["records_reused"],
                    "promoted": loop["records_promoted"],
                    "coverage": loop["reuse_coverage"],
                }
                for loop in loops
            ]
        ),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "report_id": report_id,
        "status": "generated_candidate",
        "method_id": METHOD_ID,
        "model_call_count": 0,
        "model_token_count": 0,
        "candidate_only": True,
        "execution_authorized": False,
        "data_classification": "local_private_metadata",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "window": {
            "days": window_days,
            "start_at": start.isoformat(),
            "end_at": observed.isoformat(),
        },
        "loops": loops,
        "summary": {
            "loop_count": len(loops),
            "records_written": sum(int(loop["records_written"]) for loop in loops),
            "records_reused": sum(int(loop["records_reused"]) for loop in loops),
            "records_promoted": sum(int(loop["records_promoted"]) for loop in loops),
            "unknown_coverage_loop_count": len(unknown),
        },
        "unknown_coverage": unknown,
        "anti_gaming_notes": [
            "Counts use source records only; agent self-score fields are ignored.",
            "Missing ledgers report coverage_unavailable instead of zero.",
            "Promotion requires explicit review_status or adoption decision labels.",
        ],
        "routine_registration": {
            "routine_id": "dad-learning-loop-yield-report",
            "enabled": False,
            "scheduled": False,
        },
    }


def render_learning_yield_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Learning-loop yield report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- window_days: `{report['window']['days']}`",
        f"- candidate_only: `{report['candidate_only']}`",
        f"- execution_authorized: `{report['execution_authorized']}`",
        "",
        "## Summary",
        "",
        f"- written: `{report['summary']['records_written']}`",
        f"- reused: `{report['summary']['records_reused']}`",
        f"- promoted: `{report['summary']['records_promoted']}`",
        f"- unknown_coverage_loops: `{report['summary']['unknown_coverage_loop_count']}`",
        "",
        "## Loops",
        "",
    ]
    for loop in report["loops"]:
        lines.extend(
            [
                f"### {loop['label']} (`{loop['loop_id']}`)",
                "",
                f"- written: `{loop['records_written']}`",
                f"- reused: `{loop['records_reused']}`",
                f"- promoted: `{loop['records_promoted']}`",
                f"- reuse_coverage: `{loop['reuse_coverage']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Authority boundary",
            "",
            report["authority_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def write_learning_yield_report(
    hub_root: Path,
    *,
    window_days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write JSON + Markdown yield report under processed/reports (report-only)."""

    report = build_learning_yield_report(hub_root, window_days=window_days, now=now)
    reports_dir = data_path(hub_root, "central_reports")
    cadence_dir = data_path(hub_root, "cadence")
    reports_dir.mkdir(parents=True, exist_ok=True)
    cadence_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    history_path = cadence_dir / HISTORY_JSONL
    atomic_write_text(json_path, json_dumps(report) + "\n")
    atomic_write_text(md_path, render_learning_yield_markdown(report))
    append_jsonl(
        history_path,
        {
            "recorded_at": report["generated_at"],
            "report_id": report["report_id"],
            "summary": report["summary"],
            "window_days": window_days,
        },
    )
    return {
        "report": report,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "history_path": str(history_path),
    }
