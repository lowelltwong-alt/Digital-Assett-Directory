"""Durable, non-authorizing intent checkpoints and private plan revisions.

This module deliberately does not reuse ``portfolio_workstreams.capture_ideas``:
capturing a plan must not create a project, workstream, attention claim, lease,
or execution permission.  The append-only journal stores minimized metadata;
the full sanitized plan artifact stays under the initialized private data root.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterator

from .ids import stable_id
from .portfolio_events import minimize_payload, minimize_text
from .transport import data_path, resolve_data_root
from .utils import atomic_write_text, json_dumps

SCHEMA_VERSION = "dad.portfolio_intent_event.v1"
AUTHORITY_BOUNDARY = (
    "Intent checkpoints and plan revisions are recovery evidence only. They "
    "create no project, workstream, priority, dependency, reminder, lease, "
    "dispatch, execution permission, or source authority."
)
PLAN_LIFECYCLES = frozenset(
    {"draft", "decision_complete", "approved_for_execution", "superseded", "withdrawn"}
)
PRIVACY_CLASSES = frozenset({"public", "internal", "private", "restricted"})
CONSEQUENCE_CLASSES = frozenset({"C0", "C1", "C2", "C3", "C4"})
IMPLEMENTATION_STATES = frozenset(
    {
        "unstarted",
        "partial",
        "blocked",
        "drifted",
        "validation_pending",
        "implemented_candidate",
        "verified_complete",
        "superseded",
        "unknown",
    }
)
EVENT_KINDS = frozenset(
    {
        "intent_checkpoint_recorded",
        "intent_checkpoint_revised",
        "intent_checkpoint_closed",
        "intent_checkpoint_superseded",
        "intent_checkpoint_hold_recorded",
    }
)
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/]|/(?:Users|home|tmp|var|opt|srv)/)[^\s\"'<>|?*]*"
)


class IntentIntegrityError(RuntimeError):
    """The journal or an idempotency request is unsafe to extend."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized[:64] or "untitled-plan"


def _fs_segment(value: str) -> str:
    """Encode a stable ID as a portable single filesystem segment."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def plan_id_for(
    title: str, *, privacy_partition: str = "private", identity_fingerprint: str = ""
) -> str:
    minimized, _ = minimize_text(title)
    return stable_id(
        "portfolio-plan", privacy_partition, _slug(minimized), identity_fingerprint or "title-only"
    )


def _require_initialized_private_root(hub_root: Path) -> None:
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise IntentIntegrityError(
            "Private plan persistence requires an initialized DAD_DATA_ROOT; "
            "legacy repository fallback is not permitted."
        )


def journal_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_portfolio_intents") / "intent-events.jsonl"


def private_plan_root(hub_root: Path) -> Path:
    _require_initialized_private_root(hub_root)
    return data_path(hub_root, "private_portfolio_plans")


def plan_index_path(hub_root: Path) -> Path:
    return data_path(hub_root, "portfolio_reports") / "plan-index.json"


def plan_build_status_path(hub_root: Path) -> Path:
    return data_path(hub_root, "portfolio_reports") / "plan-build-status.json"


def load_plan_revision(
    hub_root: Path, plan_id: str, revision_id: str = ""
) -> dict[str, Any]:
    index = fold_plan_index(read_events(hub_root))
    row = next((item for item in index["plans"] if item["plan_id"] == plan_id), None)
    if row is None:
        raise KeyError(f"Unknown plan: {plan_id}")
    selected_revision = revision_id or str(row["revision_id"])
    artifact_dir = private_plan_root(hub_root) / _fs_segment(plan_id)
    json_path = artifact_dir / f"{_fs_segment(selected_revision)}.json"
    markdown_path = artifact_dir / f"{_fs_segment(selected_revision)}.md"
    if not json_path.exists() or not markdown_path.exists():
        raise IntentIntegrityError("Private plan artifact is incomplete")
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IntentIntegrityError("Private plan artifact is corrupt") from exc
    markdown = markdown_path.read_text(encoding="utf-8")
    expected_content = _sha256_text(_canonical(payload.get("semantic_card", {})) + "\n" + markdown)
    if payload.get("content_digest") != expected_content:
        raise IntentIntegrityError("Private plan artifact content digest mismatch")
    expected_revision = stable_id(
        "portfolio-plan-revision",
        payload.get("plan_id", ""),
        payload.get("predecessor_revision_id", ""),
        expected_content,
    )
    if payload.get("plan_id") != plan_id or payload.get("revision_id") != expected_revision:
        raise IntentIntegrityError("Private plan artifact identity mismatch")
    payload["plan_markdown"] = markdown
    return payload


def revise_plan(
    hub_root: Path,
    plan_id: str,
    *,
    plan_markdown: str | None = None,
    lifecycle: str | None = None,
    implementation_state: str | None = None,
    acceptance_evidence: list[str] | None = None,
    independent_check_ref: str | None = None,
    producer_ref: str | None = None,
    independent_checker_ref: str | None = None,
    validated_plan_revision_id: str | None = None,
    human_approval_ref: str | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    current = load_plan_revision(hub_root, plan_id)
    card = current["semantic_card"]
    return capture_plan(
        hub_root,
        title=str(card["title"]),
        aliases=list(card.get("aliases", [])),
        outcome=str(card["outcome"]),
        plan_markdown=current["plan_markdown"] if plan_markdown is None else plan_markdown,
        lifecycle=lifecycle or str(current["lifecycle"]),
        implementation_state=implementation_state or str(current["implementation_state"]),
        current_position=str(card.get("current_position", "unknown")),
        desired_end_state=str(card.get("desired_end_state", card["outcome"])),
        non_goals=list(card.get("non_goals", [])),
        capabilities=list(card.get("capabilities", [])),
        domain_facets=list(card.get("domain_facets", [])),
        acceptance_evidence=(
            list(card.get("acceptance_evidence", []))
            if acceptance_evidence is None
            else acceptance_evidence
        ),
        independent_check_ref=(
            str(card.get("independent_check_ref", ""))
            if independent_check_ref is None
            else independent_check_ref
        ),
        producer_ref=str(card.get("producer_ref", "")) if producer_ref is None else producer_ref,
        independent_checker_ref=(
            str(card.get("independent_checker_ref", ""))
            if independent_checker_ref is None
            else independent_checker_ref
        ),
        validated_plan_revision_id=(
            str(card.get("validated_plan_revision_id", ""))
            if validated_plan_revision_id is None
            else validated_plan_revision_id
        ),
        human_approval_ref=(
            str(card.get("human_approval_ref", ""))
            if human_approval_ref is None
            else human_approval_ref
        ),
        target_users=list(card.get("target_users", [])),
        deliverables=list(card.get("deliverables", [])),
        risks=list(card.get("risks", [])),
        human_decisions=list(card.get("human_decisions", [])),
        project_refs=list(card.get("project_refs", [])),
        workstream_refs=list(card.get("workstream_refs", [])),
        entity_refs=list(card.get("entity_refs", [])),
        source_bindings=list(card.get("source_bindings", [])),
        dependencies=list(card.get("dependencies", [])),
        smallest_next_action=str(card.get("smallest_next_action", "")),
        privacy_class=str(card.get("privacy_class", "private")),
        consequence_class=str(card.get("consequence_class", "C1")),
        source_ref=str(card.get("source_ref", "local-task")),
        runtime_ref=str(card.get("runtime_ref", "unknown")),
        plan_id=plan_id,
        predecessor_revision_id=str(current["revision_id"]),
        request_id=request_id,
        event_kind="intent_checkpoint_revised",
    )


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    lock = path.with_suffix(path.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise IntentIntegrityError(f"Intent journal is locked: {lock.name}") from exc
    try:
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        os.close(fd)
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def read_events(hub_root: Path) -> list[dict[str, Any]]:
    path = journal_path(hub_root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    latest_by_plan: dict[str, str] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IntentIntegrityError(f"Invalid intent journal row {line_no}") from exc
        if not isinstance(event, dict) or event.get("schema_version") != SCHEMA_VERSION:
            raise IntentIntegrityError(f"Unsupported intent journal row {line_no}")
        if event.get("execution_authorized") is not False:
            raise IntentIntegrityError(f"Intent row {line_no} asserts execution authority")
        required = {
            "event_id", "prev_event_id", "event_kind", "plan_id", "revision_id",
            "request_id", "request_digest", "recorded_at", "payload",
        }
        if not required.issubset(event) or not isinstance(event.get("payload"), dict):
            raise IntentIntegrityError(f"Incomplete intent journal row {line_no}")
        if event["payload"].get("execution_authorized") is not False:
            raise IntentIntegrityError(f"Intent payload {line_no} asserts execution authority")
        if (
            event["payload"].get("plan_id") != event["plan_id"]
            or event["payload"].get("revision_id") != event["revision_id"]
        ):
            raise IntentIntegrityError(f"Intent row {line_no} payload identity mismatch")
        if event["request_digest"] != _sha256_text(_canonical(event["payload"])):
            raise IntentIntegrityError(f"Intent row {line_no} payload digest mismatch")
        if event["payload"].get("lifecycle") == "approved_for_execution":
            raise IntentIntegrityError(
                "approved_for_execution may only be derived from signed execution control"
            )
        if event["payload"].get("implementation_state") == "verified_complete":
            try:
                _require_independent_validation_receipt(
                    hub_root,
                    receipt_ref=str(event["payload"].get("independent_check_ref", "")),
                    plan_revision_id=str(event["payload"].get("validated_plan_revision_id", "")),
                    producer_ref=str(event["payload"].get("producer_ref", "")),
                    checker_ref=str(event["payload"].get("independent_checker_ref", "")),
                    acceptance_evidence=list(event["payload"].get("acceptance_evidence", [])),
                )
            except ValueError as exc:
                raise IntentIntegrityError(
                    f"Intent row {line_no} lacks canonical independent validation"
                ) from exc
        expected_prev = latest_by_plan.get(str(event["plan_id"]), "")
        if event["prev_event_id"] != expected_prev:
            raise IntentIntegrityError(f"Intent row {line_no} chain predecessor mismatch")
        expected_id = stable_id(
            "portfolio-intent-event", event["plan_id"], event["event_kind"],
            event["request_digest"], event["prev_event_id"],
        )
        if event["event_id"] != expected_id:
            raise IntentIntegrityError(f"Intent row {line_no} identity mismatch")
        latest_by_plan[str(event["plan_id"])] = str(event["event_id"])
        events.append(event)
    return events


def _require_independent_validation_receipt(
    hub_root: Path,
    *,
    receipt_ref: str,
    plan_revision_id: str,
    producer_ref: str,
    checker_ref: str,
    acceptance_evidence: list[str],
) -> None:
    from .technical_product_os import resolve_independent_validation_receipt

    resolve_independent_validation_receipt(
        hub_root,
        receipt_id=receipt_ref,
        plan_revision_id=plan_revision_id,
        producer_ref=producer_ref,
        checker_ref=checker_ref,
        acceptance_evidence=acceptance_evidence,
    )


def _append_event(hub_root: Path, event: dict[str, Any]) -> dict[str, Any]:
    path = journal_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(path):
        rows = read_events(hub_root)
        same_request = [row for row in rows if row.get("request_id") == event["request_id"]]
        if same_request:
            existing = same_request[-1]
            if existing.get("request_digest") != event["request_digest"]:
                raise IntentIntegrityError("request_id was reused for different intent content")
            return existing
        previous = next(
            (row for row in reversed(rows) if row.get("plan_id") == event["plan_id"]),
            None,
        )
        event["prev_event_id"] = previous["event_id"] if previous else ""
        event["event_id"] = stable_id(
            "portfolio-intent-event",
            event["plan_id"],
            event["event_kind"],
            event["request_digest"],
            event["prev_event_id"],
        )
        serialized = json_dumps(event, pretty=False) + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        confirmed = read_events(hub_root)[-1]
        if confirmed.get("event_id") != event["event_id"]:
            raise IntentIntegrityError("Intent append outcome could not be reconciled")
        return confirmed


def _precheck_request(hub_root: Path, request_id: str, request_digest: str) -> dict[str, Any] | None:
    same = [row for row in read_events(hub_root) if row.get("request_id") == request_id]
    if not same:
        return None
    existing = same[-1]
    if existing.get("request_digest") != request_digest:
        raise IntentIntegrityError("request_id was reused for different intent content")
    return existing


def _precheck_revision(
    hub_root: Path, plan_id: str, revision_id: str, content_digest: str
) -> dict[str, Any] | None:
    for row in reversed(read_events(hub_root)):
        if (
            row.get("plan_id") == plan_id
            and row.get("revision_id") == revision_id
            and row.get("payload", {}).get("content_digest") == content_digest
        ):
            return row
    return None


def _safe_markdown(value: str) -> tuple[str, int]:
    minimized, redactions = minimize_text(value)
    minimized, path_count = _ABSOLUTE_PATH.subn("[LOCAL_PATH]", minimized)
    return minimized, redactions + path_count


def capture_plan(
    hub_root: Path,
    *,
    title: str,
    outcome: str,
    plan_markdown: str = "",
    lifecycle: str = "draft",
    implementation_state: str = "unstarted",
    aliases: list[str] | None = None,
    current_position: str = "unknown",
    desired_end_state: str = "",
    non_goals: list[str] | None = None,
    capabilities: list[str] | None = None,
    domain_facets: list[str] | None = None,
    acceptance_evidence: list[str] | None = None,
    independent_check_ref: str = "",
    producer_ref: str = "",
    independent_checker_ref: str = "",
    validated_plan_revision_id: str = "",
    human_approval_ref: str = "",
    target_users: list[str] | None = None,
    deliverables: list[str] | None = None,
    risks: list[str] | None = None,
    human_decisions: list[str] | None = None,
    project_refs: list[str] | None = None,
    workstream_refs: list[str] | None = None,
    entity_refs: list[str] | None = None,
    source_bindings: list[str] | None = None,
    dependencies: list[str] | None = None,
    smallest_next_action: str = "",
    privacy_class: str = "private",
    consequence_class: str = "C1",
    source_ref: str = "local-task",
    runtime_ref: str = "unknown",
    plan_id: str = "",
    predecessor_revision_id: str = "",
    request_id: str = "",
    event_kind: str = "intent_checkpoint_recorded",
) -> dict[str, Any]:
    """Capture one immutable plan revision and return its non-authorizing event."""

    if lifecycle not in PLAN_LIFECYCLES:
        raise ValueError(f"Unsupported plan lifecycle: {lifecycle}")
    if implementation_state not in IMPLEMENTATION_STATES:
        raise ValueError(f"Unsupported implementation state: {implementation_state}")
    if implementation_state == "verified_complete" and (
        not acceptance_evidence
        or not independent_check_ref
        or not producer_ref
        or not independent_checker_ref
        or producer_ref == independent_checker_ref
        or not predecessor_revision_id
        or validated_plan_revision_id != predecessor_revision_id
    ):
        raise ValueError(
            "verified_complete requires acceptance evidence, distinct producer/checker identities, "
            "and an independent check bound to the predecessor plan revision"
        )
    if lifecycle == "approved_for_execution":
        raise ValueError(
            "Plan Memory cannot grant approved_for_execution; that state must be derived "
            "from DAD's existing signed portfolio execution-control authority plane"
        )
    if privacy_class not in PRIVACY_CLASSES:
        raise ValueError(f"Unsupported privacy class: {privacy_class}")
    if consequence_class not in CONSEQUENCE_CLASSES:
        raise ValueError(f"Unsupported consequence class: {consequence_class}")
    if event_kind not in EVENT_KINDS:
        raise ValueError(f"Unsupported intent event kind: {event_kind}")
    _require_initialized_private_root(hub_root)
    if implementation_state == "verified_complete":
        _require_independent_validation_receipt(
            hub_root,
            receipt_ref=independent_check_ref,
            plan_revision_id=predecessor_revision_id,
            producer_ref=producer_ref,
            checker_ref=independent_checker_ref,
            acceptance_evidence=acceptance_evidence or [],
        )

    raw_card = {
        "title": title,
        "aliases": aliases or [],
        "outcome": outcome,
        "current_position": current_position,
        "desired_end_state": desired_end_state or outcome,
        "non_goals": non_goals or [],
        "capabilities": capabilities or [],
        "domain_facets": domain_facets or [],
        "acceptance_evidence": acceptance_evidence or [],
        "independent_check_ref": independent_check_ref,
        "producer_ref": producer_ref,
        "independent_checker_ref": independent_checker_ref,
        "validated_plan_revision_id": validated_plan_revision_id,
        "human_approval_ref": human_approval_ref,
        "target_users": target_users or [],
        "deliverables": deliverables or [],
        "risks": risks or [],
        "human_decisions": human_decisions or [],
        "project_refs": project_refs or [],
        "workstream_refs": workstream_refs or [],
        "entity_refs": entity_refs or [],
        "source_bindings": source_bindings or [],
        "dependencies": dependencies or [],
        "smallest_next_action": smallest_next_action,
        "privacy_class": privacy_class,
        "consequence_class": consequence_class,
        "source_ref": source_ref,
        "runtime_ref": runtime_ref,
    }
    card, redaction_count = minimize_payload(raw_card)
    if not isinstance(card, dict):
        raise ValueError("Plan card must be an object")
    markdown, markdown_redactions = _safe_markdown(plan_markdown)
    identity_material = {
        "title": card["title"],
        "outcome": card["outcome"],
        "capabilities": card["capabilities"],
        "domain_facets": card["domain_facets"],
        "target_users": card["target_users"],
        "source_bindings": card["source_bindings"],
    }
    effective_plan_id = plan_id or plan_id_for(
        str(card["title"]),
        privacy_partition=privacy_class,
        identity_fingerprint=_sha256_text(_canonical(identity_material)),
    )
    content_digest = _sha256_text(_canonical(card) + "\n" + markdown)
    revision_id = stable_id(
        "portfolio-plan-revision", effective_plan_id, predecessor_revision_id, content_digest
    )
    artifact_json = {
        "schema_version": "dad.private_plan_revision.v1",
        "plan_id": effective_plan_id,
        "revision_id": revision_id,
        "predecessor_revision_id": predecessor_revision_id,
        "content_digest": content_digest,
        "lifecycle": lifecycle,
        "implementation_state": implementation_state,
        "semantic_card": card,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload = {
        "plan_id": effective_plan_id,
        "revision_id": revision_id,
        "predecessor_revision_id": predecessor_revision_id,
        "content_digest": content_digest,
        "title": card["title"],
        "aliases": card["aliases"],
        "outcome": card["outcome"],
        "lifecycle": lifecycle,
        "implementation_state": implementation_state,
        "privacy_class": privacy_class,
        "consequence_class": consequence_class,
        "smallest_next_action": card["smallest_next_action"],
        "acceptance_evidence": card["acceptance_evidence"],
        "independent_check_ref": card["independent_check_ref"],
        "producer_ref": card["producer_ref"],
        "independent_checker_ref": card["independent_checker_ref"],
        "validated_plan_revision_id": card["validated_plan_revision_id"],
        "human_approval_ref": card["human_approval_ref"],
        "artifact_ref": f"private-plan:{effective_plan_id}:{revision_id}",
        "execution_authorized": False,
        "redaction_count": redaction_count + markdown_redactions,
    }
    request_digest = _sha256_text(_canonical(payload))
    effective_request_id = request_id or stable_id("portfolio-intent-request", request_digest)
    existing = _precheck_request(hub_root, effective_request_id, request_digest)
    if existing is not None:
        return existing
    existing_revision = _precheck_revision(
        hub_root, effective_plan_id, revision_id, content_digest
    )
    if existing_revision is not None:
        return existing_revision
    artifact_dir = private_plan_root(hub_root) / _fs_segment(effective_plan_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe_revision = _fs_segment(revision_id)
    atomic_write_text(artifact_dir / f"{safe_revision}.json", json_dumps(artifact_json) + "\n")
    atomic_write_text(artifact_dir / f"{safe_revision}.md", markdown)
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_kind": event_kind,
        "plan_id": effective_plan_id,
        "revision_id": revision_id,
        "request_id": effective_request_id,
        "request_digest": request_digest,
        "recorded_at": _utc_now(),
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "payload": payload,
    }
    recorded = _append_event(hub_root, event)
    write_plan_index(hub_root)
    return recorded


def fold_plan_index(events: list[dict[str, Any]]) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    revision_counts: dict[str, int] = {}
    for event in events:
        plan_id = str(event["plan_id"])
        revision_counts[plan_id] = revision_counts.get(plan_id, 0) + 1
        latest[plan_id] = {
            **event["payload"],
            "event_id": event["event_id"],
            "recorded_at": event["recorded_at"],
            "revision_count": revision_counts[plan_id],
            "execution_authorized": False,
        }
    plans = sorted(latest.values(), key=lambda row: (str(row["title"]).casefold(), row["plan_id"]))
    return {
        "schema_version": "dad.plan_index.v1",
        "generated_at": _utc_now(),
        "plan_count": len(plans),
        "plans": plans,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def write_plan_index(hub_root: Path) -> dict[str, Any]:
    index = fold_plan_index(read_events(hub_root))
    path = plan_index_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json_dumps(index) + "\n")
    status = {
        "schema_version": "dad.plan_build_status.v1",
        "generated_at": index["generated_at"],
        "plans": [
            {
                "plan_id": row["plan_id"],
                "plan_revision_id": row["revision_id"],
                "lifecycle": row["lifecycle"],
                "implementation_state": row["implementation_state"],
                "acceptance_evidence_required": row["implementation_state"] == "verified_complete",
                "execution_authorized": False,
            }
            for row in index["plans"]
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_text(plan_build_status_path(hub_root), json_dumps(status) + "\n")
    return index


def search_plans(
    hub_root: Path, query: str, *, privacy_partition: str = "private", limit: int = 5
) -> dict[str, Any]:
    from .portfolio_relations import idea_tokens

    index = fold_plan_index(read_events(hub_root))
    query_tokens = idea_tokens(query)
    matches: list[dict[str, Any]] = []
    for plan in index["plans"]:
        if plan.get("privacy_class") != privacy_partition:
            continue
        text = " ".join(
            [str(plan.get("title", "")), *[str(v) for v in plan.get("aliases", [])], str(plan.get("outcome", ""))]
        )
        shared = sorted(query_tokens & idea_tokens(text))
        if not shared:
            continue
        matches.append(
            {
                "plan_id": plan["plan_id"],
                "revision_id": plan["revision_id"],
                "title": plan["title"],
                "shared_tokens": shared[:8],
                "match_basis": "deterministic_lexical_candidate",
                "review_status": "candidate",
                "execution_authorized": False,
            }
        )
    matches.sort(key=lambda row: (-len(row["shared_tokens"]), str(row["title"]).casefold()))
    return {
        "query": query,
        "matches": matches[: max(0, min(limit, 25))],
        "privacy_partition": privacy_partition,
        "coverage": {
            "plan_count_in_partition": sum(
                1 for row in index["plans"] if row.get("privacy_class") == privacy_partition
            ),
            "returned_count": min(len(matches), limit),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "IMPLEMENTATION_STATES",
    "IntentIntegrityError",
    "PLAN_LIFECYCLES",
    "capture_plan",
    "fold_plan_index",
    "journal_path",
    "load_plan_revision",
    "plan_id_for",
    "plan_build_status_path",
    "read_events",
    "revise_plan",
    "search_plans",
    "write_plan_index",
]
