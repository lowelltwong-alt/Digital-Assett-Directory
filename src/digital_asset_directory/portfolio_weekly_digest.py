"""Zero-model weekly forgotten-plan digest over the existing Today decision queue."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .portfolio_events import minimize_text
from .transport import data_path
from .utils import atomic_write_text, json_dumps


MAX_ASKS = 3
_SAFE_ACTIONS = frozenset({"inspect", "resume_request", "hold", "snooze", "acknowledge"})
_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:Users|home|tmp)/)[^\s\"'<>|?*]*")
AUTHORITY_BOUNDARY = (
    "The digest is a read-only cockpit projection. Delivery, scheduling, reminders, "
    "resume, closure, and execution require separately reviewed authority."
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_label(value: Any, fallback: str) -> str:
    minimized, _ = minimize_text(str(value or fallback))
    return _LOCAL_PATH.sub("[LOCAL_PATH]", minimized)[:160]


def build_weekly_digest(
    plan_index: dict[str, Any],
    *,
    today_items: list[dict[str, Any]] | None = None,
    previous_fingerprints: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    previous = set(previous_fingerprints or [])
    plans = list(plan_index.get("plans", []))
    unfinished = [
        row
        for row in plans
        if row.get("lifecycle") not in {"withdrawn", "superseded"}
        and row.get("implementation_state") not in {"verified_complete", "superseded"}
    ]
    candidates: list[dict[str, Any]] = []
    for item in today_items or []:
        if item.get("quiet") or item.get("snoozed") or item.get("dismissed"):
            continue
        material = {
            "decision_key": item.get("decision_key") or item.get("item_id") or item.get("plan_id"),
            "source_fingerprint": item.get("source_fingerprint", ""),
            "status": item.get("status", ""),
        }
        fingerprint = _digest(material)
        if fingerprint in previous:
            continue
        candidates.append(
            {
                "decision_key": "decision:" + _digest(material["decision_key"]).split(":", 1)[1],
                "fingerprint": fingerprint,
                "title": _safe_label(item.get("title"), "Unfinished work needs a decision"),
                "recommended_action": (
                    item.get("recommended_action")
                    if item.get("recommended_action") in _SAFE_ACTIONS
                    else "inspect"
                ),
                "source": "existing_today_queue",
                "execution_authorized": False,
            }
        )
    candidates.sort(key=lambda row: (str(row["title"]).casefold(), str(row["decision_key"])))
    asks = candidates[:MAX_ASKS]
    generated = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    packet = {
        "schema_version": "dad.portfolio_weekly_digest.v1",
        "digest_id": "dad:unfinished-digest:" + _digest(
            {"unfinished": sorted(str(row.get("plan_id")) for row in unfinished), "asks": asks}
        ).split(":", 1)[1],
        "generated_at": generated,
        "schedule_candidate": {"weekday": "monday", "local_time": "07:00", "timezone": "America/New_York"},
        "inventory": {
            "plan_count": len(plans),
            "unfinished_plan_count": len(unfinished),
            "new_decision_count": len(asks),
        },
        "asks": asks,
        "model_calls": 0,
        "model_tokens": 0,
        "delivery": {
            "cockpit_packet_ready": True,
            "windows_toast_status": "not_activated",
            "attempted": False,
            "confirmed": False,
            "blind_retry_allowed": False,
        },
        "activation_status": "supervised_trial_required",
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return packet


def metadata_safe_toast(digest: dict[str, Any]) -> dict[str, Any]:
    inventory = digest["inventory"]
    return {
        "title": "DAD weekly review",
        "body": f"{inventory['unfinished_plan_count']} unfinished plans; {inventory['new_decision_count']} new decisions.",
        "open_target": "local-capability-os-cockpit",
        "contains_names": False,
        "contains_paths": False,
        "contains_content": False,
        "delivery_authorized": False,
    }


def write_weekly_digest(hub_root: Path, digest: dict[str, Any]) -> dict[str, Any]:
    path = data_path(hub_root, "portfolio_reports") / "unfinished-intent-digest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json_dumps(digest) + "\n")
    return {"path": str(path), "delivery_attempted": False, "execution_authorized": False}


__all__ = ["AUTHORITY_BOUNDARY", "MAX_ASKS", "build_weekly_digest", "metadata_safe_toast", "write_weekly_digest"]
