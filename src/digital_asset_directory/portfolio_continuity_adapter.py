"""Silent, provider-neutral adapter for continuity metadata receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .portfolio_continuity_events import append_observation


ADAPTER_AUTHORITY_BOUNDARY = (
    "The shadow adapter records minimized local metadata only. It cannot call models, "
    "networks, notifications, schedulers, Git, task mutation, or archival actions."
)


def ingest_receipt(
    hub_root: Path,
    receipt: Mapping[str, Any],
    *,
    lock_timeout_seconds: float = 5.0,
    retry_clock_tolerant: bool = False,
) -> dict[str, Any]:
    """Durably ingest one receipt and return content-free status metadata.

    The function intentionally has no callback, dispatch, notification, or
    execution extension point.  Callers may print the returned status, but no
    receipt payload or label is returned.
    """

    result = append_observation(
        hub_root,
        receipt,
        lock_timeout_seconds=lock_timeout_seconds,
        retry_clock_tolerant=retry_clock_tolerant,
    )
    event = result["event"]
    return {
        "schema_version": "dad.portfolio_continuity_adapter_result.v1",
        "status": result["status"],
        "event_id": event["event_id"],
        "command_id": event["command_id"],
        "redaction_count": event["redaction_count"],
        "silent": True,
        "model_calls": 0,
        "network_calls": 0,
        "notifications_attempted": 0,
        "scheduler_actions": 0,
        "git_actions": 0,
        "task_mutations": 0,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": ADAPTER_AUTHORITY_BOUNDARY,
    }


def ingest_receipt_file(hub_root: Path, receipt_file: Path) -> dict[str, Any]:
    """Load a strict local JSON receipt and pass it through the silent adapter."""

    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("Continuity receipt file must contain one JSON object")
    return ingest_receipt(hub_root, receipt)


__all__ = ["ADAPTER_AUTHORITY_BOUNDARY", "ingest_receipt", "ingest_receipt_file"]
