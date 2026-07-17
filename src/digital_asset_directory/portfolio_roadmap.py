"""Structured, evidence-gated roadmap items for private Portfolio OS plans.

Roadmap item status is an implementation overlay, not the durable workstream
lifecycle and not an execution authority.  Accepted items require explicit
acceptance evidence and an independent checker; closed tasks or clean Git state
are never sufficient.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator

from .ids import stable_id
from .portfolio_events import minimize_payload
from .transport import data_path, resolve_data_root
from .utils import json_dumps


SCHEMA_VERSION = "dad.portfolio_roadmap_event.v1"
PROJECTION_SCHEMA_VERSION = "dad.portfolio_roadmap_projection.v1"
ITEM_STATUSES = frozenset(
    {"proposed", "ready", "active", "blocked", "validation_pending", "accepted", "superseded"}
)
EVENT_KINDS = frozenset({"roadmap_item_recorded", "roadmap_item_transitioned"})
LEGAL_STATUS_TRANSITIONS = {
    "proposed": frozenset(
        {"ready", "active", "blocked", "validation_pending", "accepted", "superseded"}
    ),
    "ready": frozenset(
        {"active", "blocked", "validation_pending", "accepted", "superseded"}
    ),
    "active": frozenset({"blocked", "validation_pending", "accepted", "superseded"}),
    "blocked": frozenset(
        {"ready", "active", "validation_pending", "accepted", "superseded"}
    ),
    "validation_pending": frozenset({"active", "blocked", "accepted", "superseded"}),
    "accepted": frozenset({"superseded"}),
    "superseded": frozenset(),
}
AUTHORITY_BOUNDARY = (
    "Roadmap rows are private implementation overlays and candidate evidence. "
    "They create no workstream lifecycle transition, execution lease, task, Git "
    "mutation, delivery authority, archive action, or source authority."
)


class RoadmapIntegrityError(RuntimeError):
    """Roadmap evidence is corrupt, conflicting, or unsafe to append."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_private_root(hub_root: Path) -> None:
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise RoadmapIntegrityError("Roadmap persistence requires an initialized DAD_DATA_ROOT")


def journal_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_portfolio_intents") / "roadmap-events.jsonl"


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    lock = path.with_suffix(path.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RoadmapIntegrityError("Roadmap journal is locked") from exc
    try:
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        os.close(fd)
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def read_roadmap_events(hub_root: Path) -> list[dict[str, Any]]:
    path = journal_path(hub_root)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    heads: dict[str, str] = {}
    request_digests: dict[str, str] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RoadmapIntegrityError(f"Invalid roadmap journal row {line_no}") from exc
        if not isinstance(row, dict) or row.get("schema_version") != SCHEMA_VERSION:
            raise RoadmapIntegrityError(f"Unsupported roadmap journal row {line_no}")
        required = {
            "event_id", "prev_event_id", "event_kind", "plan_id", "item_id",
            "request_id", "request_digest", "recorded_at", "payload",
            "candidate_only", "execution_authorized", "authority_boundary",
        }
        if not required.issubset(row) or not isinstance(row.get("payload"), dict):
            raise RoadmapIntegrityError(f"Incomplete roadmap journal row {line_no}")
        if row["event_kind"] not in EVENT_KINDS:
            raise RoadmapIntegrityError(f"Unknown roadmap event kind at row {line_no}")
        if row["candidate_only"] is not True or row["execution_authorized"] is not False:
            raise RoadmapIntegrityError(f"Roadmap row {line_no} asserts authority")
        if row["request_digest"] != _digest(row["payload"]):
            raise RoadmapIntegrityError(f"Roadmap row {line_no} payload digest mismatch")
        request_id = str(row["request_id"])
        if request_id in request_digests and request_digests[request_id] != row["request_digest"]:
            raise RoadmapIntegrityError(f"Roadmap request conflict at row {line_no}")
        request_digests[request_id] = str(row["request_digest"])
        item_id = str(row["item_id"])
        expected_prev = heads.get(item_id, "")
        if row["prev_event_id"] != expected_prev:
            raise RoadmapIntegrityError(f"Roadmap chain mismatch at row {line_no}")
        expected_id = stable_id(
            "portfolio-roadmap-event",
            item_id,
            str(row["event_kind"]),
            str(row["request_digest"]),
            expected_prev,
        )
        if row["event_id"] != expected_id:
            raise RoadmapIntegrityError(f"Roadmap identity mismatch at row {line_no}")
        heads[item_id] = expected_id
        rows.append(row)
    return rows


def _append(hub_root: Path, row: dict[str, Any]) -> dict[str, Any]:
    path = journal_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(path):
        rows = read_roadmap_events(hub_root)
        same = [item for item in rows if item["request_id"] == row["request_id"]]
        if same:
            if same[-1]["request_digest"] != row["request_digest"]:
                raise RoadmapIntegrityError("request_id was reused for different roadmap content")
            return same[-1]
        previous = next(
            (item for item in reversed(rows) if item["item_id"] == row["item_id"]), None
        )
        row["prev_event_id"] = str(previous["event_id"]) if previous else ""
        row["event_id"] = stable_id(
            "portfolio-roadmap-event",
            row["item_id"],
            row["event_kind"],
            row["request_digest"],
            row["prev_event_id"],
        )
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json_dumps(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        confirmed = read_roadmap_events(hub_root)[-1]
        if confirmed["event_id"] != row["event_id"]:
            raise RoadmapIntegrityError("Roadmap append outcome could not be reconciled")
        return confirmed


def record_roadmap_item(
    hub_root: Path,
    *,
    plan_id: str,
    title: str,
    outcome: str,
    acceptance_criteria: list[str],
    dependency_item_ids: list[str] | None = None,
    item_id: str = "",
    request_id: str = "",
) -> dict[str, Any]:
    _require_private_root(hub_root)
    raw = {
        "title": title,
        "outcome": outcome,
        "acceptance_criteria": acceptance_criteria,
        "dependency_item_ids": sorted(set(dependency_item_ids or [])),
        "status": "proposed",
        "acceptance_evidence": [],
        "independent_check_ref": "",
        "producer_ref": "",
        "independent_checker_ref": "",
        "human_approval_ref": "",
    }
    payload, redactions = minimize_payload(raw)
    if not str(payload["title"]) or not str(payload["outcome"]):
        raise ValueError("Roadmap title and outcome are required")
    if not payload["acceptance_criteria"]:
        raise ValueError("Roadmap acceptance criteria are required")
    effective_item_id = item_id or stable_id("portfolio-roadmap-item", plan_id, payload["title"])
    payload.update({"plan_id": plan_id, "item_id": effective_item_id, "redaction_count": redactions})
    digest = _digest(payload)
    effective_request = request_id or stable_id("portfolio-roadmap-request", "record", digest)
    row = {
        "schema_version": SCHEMA_VERSION,
        "event_id": "",
        "prev_event_id": "",
        "event_kind": "roadmap_item_recorded",
        "plan_id": plan_id,
        "item_id": effective_item_id,
        "request_id": effective_request,
        "request_digest": digest,
        "recorded_at": _now(),
        "payload": payload,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return _append(hub_root, row)


def transition_roadmap_item(
    hub_root: Path,
    *,
    item_id: str,
    status: str,
    human_approval_ref: str,
    acceptance_evidence: list[str] | None = None,
    independent_check_ref: str = "",
    producer_ref: str = "",
    independent_checker_ref: str = "",
    request_id: str = "",
) -> dict[str, Any]:
    _require_private_root(hub_root)
    if status not in ITEM_STATUSES - {"proposed"}:
        raise ValueError(f"Unsupported roadmap status: {status}")
    if not human_approval_ref:
        raise ValueError("Roadmap status transitions require human approval evidence")
    current = fold_roadmap(read_roadmap_events(hub_root))
    item = next((row for row in current["items"] if row["item_id"] == item_id), None)
    if item is None:
        raise KeyError(f"Unknown roadmap item: {item_id}")
    current_status = str(item.get("status", "proposed"))
    if status not in LEGAL_STATUS_TRANSITIONS.get(current_status, frozenset()):
        raise ValueError(
            f"Illegal roadmap status transition: {current_status} -> {status}"
        )
    evidence = sorted(set(acceptance_evidence or []))
    if status == "accepted" and (
        not evidence
        or not independent_check_ref
        or not producer_ref
        or not independent_checker_ref
        or producer_ref == independent_checker_ref
    ):
        raise ValueError(
            "Accepted roadmap items require evidence and distinct producer/checker identities"
        )
    raw = {
        **item,
        "status": status,
        "acceptance_evidence": evidence,
        "independent_check_ref": independent_check_ref,
        "producer_ref": producer_ref,
        "independent_checker_ref": independent_checker_ref,
        "human_approval_ref": human_approval_ref,
    }
    raw.pop("last_event_id", None)
    raw.pop("recorded_at", None)
    payload, redactions = minimize_payload(raw)
    payload["redaction_count"] = int(payload.get("redaction_count", 0)) + redactions
    digest = _digest(payload)
    effective_request = request_id or stable_id(
        "portfolio-roadmap-request", "transition", item_id, status, digest
    )
    row = {
        "schema_version": SCHEMA_VERSION,
        "event_id": "",
        "prev_event_id": "",
        "event_kind": "roadmap_item_transitioned",
        "plan_id": item["plan_id"],
        "item_id": item_id,
        "request_id": effective_request,
        "request_digest": digest,
        "recorded_at": _now(),
        "payload": payload,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    return _append(hub_root, row)


def fold_roadmap(events: list[dict[str, Any]], *, plan_id: str = "") -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = dict(event["payload"])
        payload["last_event_id"] = event["event_id"]
        payload["recorded_at"] = event["recorded_at"]
        items[str(event["item_id"])] = payload
    rows = sorted(
        (row for row in items.values() if not plan_id or row["plan_id"] == plan_id),
        key=lambda row: (str(row["plan_id"]), str(row["title"]).casefold(), str(row["item_id"])),
    )
    accepted = sum(row["status"] == "accepted" for row in rows)
    return {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "plan_id": plan_id,
        "item_count": len(rows),
        "accepted_count": accepted,
        "remaining_count": len(rows) - accepted,
        "items": rows,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "EVENT_KINDS",
    "ITEM_STATUSES",
    "PROJECTION_SCHEMA_VERSION",
    "RoadmapIntegrityError",
    "SCHEMA_VERSION",
    "fold_roadmap",
    "journal_path",
    "read_roadmap_events",
    "record_roadmap_item",
    "transition_roadmap_item",
]
