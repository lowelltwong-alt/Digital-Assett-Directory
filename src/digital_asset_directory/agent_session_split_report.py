"""Report-only reconciliation of legacy vs data-root agent sessions (N1)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ids import stable_id
from .transport import data_path, legacy_data_path, resolve_data_root
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

SCHEMA_VERSION = "dad.agent_session_split_report.v1"
METHOD_ID = "dad.agent-session-split.v1"
REPORT_JSON = "agent_session_split.json"
REPORT_MD = "agent_session_split.md"
HISTORY_JSONL = "agent_session_split_history.jsonl"
AUTHORITY_BOUNDARY = (
    "Agent session split reporting is dry-run evidence only. It compares "
    "legacy hub state/agent_sessions with the initialized data-root copy, "
    "proposes a preferred side, and never migrates, deletes, merges, or "
    "rewrites session files. Apply/migrate requires a separate named human "
    "approval because it mutates lifecycle evidence."
)

_COMPARE_FIELDS = (
    "status",
    "closed_at",
    "handoff_id",
    "task",
    "agent",
    "repository",
    "required_postflight",
)


def canonical_agent_session_path(hub_root: Path, session_uuid: str) -> Path:
    """Return the canonical write path for a new or data-root session file."""
    return data_path(hub_root, "agent_sessions") / f"{session_uuid}.json"


def read_agent_session_path(hub_root: Path, session_uuid: str) -> Path:
    """Resolve an existing session with data-root preference and legacy fallback."""
    from .transport import existing_data_file

    return existing_data_file(hub_root, "agent_sessions", f"{session_uuid}.json")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _load_session_dir(directory: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not directory.is_dir():
        return rows
    for path in directory.glob("*.json"):
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            try:
                digest = _sha256_bytes(path.read_bytes())
            except OSError:
                digest = _sha256_bytes(b"")
            rows[path.stem] = {
                "path": str(path),
                "parse_error": True,
                "content_digest": digest,
            }
            continue
        if not isinstance(payload, dict):
            rows[path.stem] = {
                "path": str(path),
                "parse_error": True,
                "content_digest": _sha256_bytes(raw),
            }
            continue
        rows[path.stem] = {
            "path": str(path),
            "parse_error": False,
            "content_digest": _sha256_bytes(raw.replace(b"\r\n", b"\n")),
            "session_id": payload.get("session_id"),
            "status": payload.get("status"),
            "closed_at": payload.get("closed_at"),
            "handoff_id": payload.get("handoff_id"),
            "task": payload.get("task"),
            "agent": payload.get("agent"),
            "repository": payload.get("repository"),
            "required_postflight": payload.get("required_postflight"),
            "created_at": payload.get("created_at"),
        }
    return rows


def _field_diffs(legacy: dict[str, Any], data_root: dict[str, Any]) -> list[str]:
    diffs: list[str] = []
    for field in _COMPARE_FIELDS:
        if legacy.get(field) != data_root.get(field):
            diffs.append(field)
    return diffs


def _prefer_side(legacy: dict[str, Any], data_root: dict[str, Any]) -> str:
    """Propose a preferred copy without mutating anything."""

    legacy_status = str(legacy.get("status") or "")
    data_status = str(data_root.get("status") or "")
    if legacy_status == "closed" and data_status != "closed":
        return "legacy"
    if data_status == "closed" and legacy_status != "closed":
        return "data_root"
    legacy_ts = str(legacy.get("closed_at") or legacy.get("created_at") or "")
    data_ts = str(data_root.get("closed_at") or data_root.get("created_at") or "")
    if legacy_ts and data_ts and legacy_ts != data_ts:
        return "legacy" if legacy_ts > data_ts else "data_root"
    if legacy.get("content_digest") == data_root.get("content_digest"):
        return "either_identical"
    return "human_review_required"


def build_agent_session_split_report(
    hub_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compare legacy and data-root agent session directories (report-only)."""

    observed = now or utc_now()
    if isinstance(observed, datetime):
        observed_at = observed.astimezone(timezone.utc).isoformat()
    else:
        observed_at = str(observed)

    root, mode = resolve_data_root(hub_root)
    legacy_dir = legacy_data_path(hub_root, "agent_sessions")
    data_dir = data_path(hub_root, "agent_sessions")
    same_location = legacy_dir.resolve() == data_dir.resolve()

    legacy_rows = _load_session_dir(legacy_dir)
    data_rows = _load_session_dir(data_dir)
    names = sorted(set(legacy_rows) | set(data_rows))

    pairs: list[dict[str, Any]] = []
    counts = {
        "agree": 0,
        "disagree": 0,
        "legacy_only": 0,
        "data_root_only": 0,
        "open_closed_split": 0,
        "parse_error": 0,
        "same_location_no_split_possible": 0,
    }

    for name in names:
        legacy = legacy_rows.get(name)
        data = data_rows.get(name)
        if same_location:
            counts["same_location_no_split_possible"] += 1
            pairs.append(
                {
                    "session_file": f"{name}.json",
                    "classification": "same_location",
                    "proposed_resolution": "not_applicable_same_location",
                    "differing_fields": [],
                }
            )
            continue
        if legacy and data:
            if legacy.get("parse_error") or data.get("parse_error"):
                classification = "parse_error"
                counts["parse_error"] += 1
                proposed = "human_review_required"
                diffs = ["parse_error"]
            elif legacy.get("content_digest") == data.get("content_digest"):
                classification = "agree"
                counts["agree"] += 1
                proposed = "either_identical"
                diffs = []
            else:
                classification = "disagree"
                counts["disagree"] += 1
                diffs = _field_diffs(legacy, data)
                proposed = _prefer_side(legacy, data)
                if (
                    legacy.get("status") == "open"
                    and data.get("status") == "closed"
                ) or (
                    legacy.get("status") == "closed"
                    and data.get("status") == "open"
                ):
                    counts["open_closed_split"] += 1
                    classification = "open_closed_split"
            pairs.append(
                {
                    "session_file": f"{name}.json",
                    "classification": classification,
                    "proposed_resolution": proposed,
                    "differing_fields": diffs,
                    "legacy": {
                        "path": legacy.get("path"),
                        "status": legacy.get("status"),
                        "content_digest": legacy.get("content_digest"),
                    },
                    "data_root": {
                        "path": data.get("path"),
                        "status": data.get("status"),
                        "content_digest": data.get("content_digest"),
                    },
                }
            )
        elif legacy:
            counts["legacy_only"] += 1
            pairs.append(
                {
                    "session_file": f"{name}.json",
                    "classification": "legacy_only",
                    "proposed_resolution": "keep_readable_via_legacy_fallback",
                    "differing_fields": [],
                    "legacy": {
                        "path": legacy.get("path"),
                        "status": legacy.get("status"),
                        "content_digest": legacy.get("content_digest"),
                    },
                }
            )
        else:
            counts["data_root_only"] += 1
            assert data is not None
            pairs.append(
                {
                    "session_file": f"{name}.json",
                    "classification": "data_root_only",
                    "proposed_resolution": "already_canonical",
                    "differing_fields": [],
                    "data_root": {
                        "path": data.get("path"),
                        "status": data.get("status"),
                        "content_digest": data.get("content_digest"),
                    },
                }
            )

    report_id = stable_id(
        "agent-session-split",
        mode,
        str(len(names)),
        json_dumps(counts),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed_at,
        "report_id": report_id,
        "status": "generated_candidate",
        "method_id": METHOD_ID,
        "model_call_count": 0,
        "model_token_count": 0,
        "candidate_only": True,
        "execution_authorized": False,
        "apply_authorized": False,
        "data_classification": "local_private_metadata",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "data_plane": {
            "mode": mode,
            "data_root": str(root),
            "legacy_sessions_dir": str(legacy_dir),
            "canonical_sessions_dir": str(data_dir),
            "same_location": same_location,
        },
        "canonical_write_path": "data_path(hub, 'agent_sessions')",
        "legacy_read_fallback": "existing_data_file(hub, 'agent_sessions', uuid.json)",
        "summary": {
            "session_file_count": len(names),
            **counts,
            "split_evidence": (
                "absent"
                if same_location
                else (
                    "present"
                    if counts["disagree"]
                    or counts["open_closed_split"]
                    or counts["legacy_only"]
                    or counts["data_root_only"]
                    or counts["parse_error"]
                    else "none_observed"
                )
            ),
        },
        "pairs": pairs,
        "next_actions": [
            "Review disagree and open_closed_split rows before any apply.",
            "Keep new session creates on the canonical data_path write surface.",
            "Do not delete legacy copies without a separate named human approval.",
        ],
        "routine_registration": {
            "routine_id": "dad-agent-session-split-report",
            "enabled": False,
            "scheduled": False,
        },
    }


def render_agent_session_split_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Agent session split-state report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- data_plane.mode: `{report['data_plane']['mode']}`",
        f"- same_location: `{report['data_plane']['same_location']}`",
        f"- execution_authorized: `{report['execution_authorized']}`",
        f"- apply_authorized: `{report['apply_authorized']}`",
        "",
        "## Summary",
        "",
        f"- session_file_count: `{summary['session_file_count']}`",
        f"- agree: `{summary['agree']}`",
        f"- disagree: `{summary['disagree']}`",
        f"- open_closed_split: `{summary['open_closed_split']}`",
        f"- legacy_only: `{summary['legacy_only']}`",
        f"- data_root_only: `{summary['data_root_only']}`",
        f"- split_evidence: `{summary['split_evidence']}`",
        "",
        "## Canonical policy (advice only)",
        "",
        f"- write: `{report['canonical_write_path']}`",
        f"- read fallback: `{report['legacy_read_fallback']}`",
        "",
        "## Authority boundary",
        "",
        report["authority_boundary"],
        "",
    ]
    actionable = [
        pair
        for pair in report["pairs"]
        if pair["classification"] in {"disagree", "open_closed_split", "parse_error"}
    ]
    if actionable:
        lines.extend(["## Actionable pairs", ""])
        for pair in actionable[:50]:
            lines.append(
                f"- `{pair['session_file']}`: {pair['classification']} → "
                f"{pair['proposed_resolution']} (fields: {', '.join(pair['differing_fields']) or 'n/a'})"
            )
        lines.append("")
    return "\n".join(lines)


def write_agent_session_split_report(
    hub_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write report artifacts only (no session mutation).

    Writes JSON/Markdown under processed/reports and appends a metadata-only
    cadence history row under processed/cadence. Never migrates, deletes, or
    rewrites agent session files.
    """

    report = build_agent_session_split_report(hub_root, now=now)
    reports_dir = data_path(hub_root, "central_reports")
    cadence_dir = data_path(hub_root, "cadence")
    reports_dir.mkdir(parents=True, exist_ok=True)
    cadence_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    history_path = cadence_dir / HISTORY_JSONL
    atomic_write_text(json_path, json_dumps(report) + "\n")
    atomic_write_text(md_path, render_agent_session_split_markdown(report))
    append_jsonl(
        history_path,
        {
            "recorded_at": report["generated_at"],
            "report_id": report["report_id"],
            "summary": report["summary"],
        },
    )
    return {
        "report": report,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "history_path": str(history_path),
    }
