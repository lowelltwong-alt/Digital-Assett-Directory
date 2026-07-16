"""Durable semantic entity identities above names, files, plans, and builds."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import unicodedata
from typing import Any

from .ids import stable_id
from .portfolio_events import minimize_payload, minimize_text
from .transport import data_path, resolve_data_root
from .utils import atomic_write_text, json_dumps

SCHEMA_VERSION = "dad.durable_entity_event.v1"
ENTITY_KINDS = frozenset(
    {
        "concept",
        "capability_family",
        "domain_expertise_family",
        "agent_family",
        "knowledge_library",
        "workflow_family",
        "plan",
        "project",
        "workstream",
        "build",
        "asset_family",
    }
)
RELATION_TYPES = frozenset(
    {
        "contains",
        "part_of",
        "specializes",
        "peer_of",
        "plans_for",
        "advances",
        "implements",
        "supports",
        "continues",
        "variant_of",
        "possible_duplicate_of",
        "merged_into",
        "split_into",
        "supersedes",
        "conflicts_with",
        "depends_on",
        "validated_by",
        "governed_by",
        "applies_to",
        "derived_from",
    }
)
AUTHORITY_BOUNDARY = (
    "Entity observations, semantic matches, and generated relations are candidate "
    "evidence. Similarity cannot merge identities, transfer source authority, "
    "promote dependencies, retire consumers, or authorize execution."
)


class EntityIntegrityError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def normalize_label(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def semantic_card(
    *,
    label: str,
    entity_kind: str,
    aliases: list[str] | None = None,
    capabilities: list[str] | None = None,
    outcomes: list[str] | None = None,
    scope_included: list[str] | None = None,
    scope_excluded: list[str] | None = None,
    audience: list[str] | None = None,
    domain_facets: list[str] | None = None,
    methods: list[str] | None = None,
    interfaces: list[str] | None = None,
    privacy_partition: str = "private",
    authority_scope: str = "dad-local-candidate",
) -> dict[str, Any]:
    if entity_kind not in ENTITY_KINDS:
        raise ValueError(f"Unknown entity kind: {entity_kind}")
    if privacy_partition not in {"public", "internal", "private", "restricted"}:
        raise ValueError(f"Unsupported privacy partition: {privacy_partition}")
    if not authority_scope.strip():
        raise ValueError("Semantic cards require a non-empty authority scope")
    raw = {
        "label": label,
        "normalized_label": normalize_label(label),
        "entity_kind": entity_kind,
        "aliases": sorted({normalize_label(v) for v in aliases or [] if normalize_label(v)}),
        "capabilities": sorted({normalize_label(v) for v in capabilities or [] if normalize_label(v)}),
        "outcomes": sorted({normalize_label(v) for v in outcomes or [] if normalize_label(v)}),
        "scope_included": sorted({normalize_label(v) for v in scope_included or [] if normalize_label(v)}),
        "scope_excluded": sorted({normalize_label(v) for v in scope_excluded or [] if normalize_label(v)}),
        "audience": sorted({normalize_label(v) for v in audience or [] if normalize_label(v)}),
        "domain_facets": sorted({normalize_label(v) for v in domain_facets or [] if normalize_label(v)}),
        "methods": sorted({normalize_label(v) for v in methods or [] if normalize_label(v)}),
        "interfaces": sorted({normalize_label(v) for v in interfaces or [] if normalize_label(v)}),
        "privacy_partition": privacy_partition,
        "authority_scope": authority_scope,
    }
    minimized, _ = minimize_payload(raw)
    if not isinstance(minimized, dict):
        raise ValueError("Semantic card must be an object")
    minimized["semantic_fingerprint"] = _digest(minimized)
    return minimized


def event_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_identity") / "entity-events.jsonl"


def state_path(hub_root: Path) -> Path:
    return data_path(hub_root, "identity_reports") / "entity-state.json"


def _require_initialized_root(hub_root: Path) -> None:
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise EntityIntegrityError("Durable entity writes require an initialized DAD_DATA_ROOT")


def read_events(hub_root: Path) -> list[dict[str, Any]]:
    path = event_path(hub_root)
    if not path.exists():
        return []
    result: list[dict[str, Any]] = []
    latest_by_stream: dict[str, str] = {}
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EntityIntegrityError(f"Invalid entity event row {index}") from exc
        if event.get("schema_version") != SCHEMA_VERSION:
            raise EntityIntegrityError(f"Unsupported entity event row {index}")
        required = {
            "event_id", "prev_event_id", "event_kind", "stream_id", "request_id",
            "request_digest", "recorded_at", "payload", "authority_boundary",
        }
        if not required.issubset(event) or not isinstance(event.get("payload"), dict):
            raise EntityIntegrityError(f"Incomplete entity event row {index}")
        if event["payload"].get("execution_authorized") is not False:
            raise EntityIntegrityError(f"Entity event row {index} asserts execution authority")
        if event["request_digest"] != _digest(event["payload"]):
            raise EntityIntegrityError(f"Entity event row {index} payload digest mismatch")
        expected_prev = latest_by_stream.get(str(event["stream_id"]), "")
        if event["prev_event_id"] != expected_prev:
            raise EntityIntegrityError(f"Entity event row {index} chain predecessor mismatch")
        expected_id = stable_id(
            "durable-entity-event",
            event["stream_id"],
            event["event_kind"],
            event["request_digest"],
            event["prev_event_id"],
        )
        if event["event_id"] != expected_id:
            raise EntityIntegrityError(f"Entity event row {index} identity mismatch")
        latest_by_stream[str(event["stream_id"])] = str(event["event_id"])
        result.append(event)
    return result


def _append(hub_root: Path, event: dict[str, Any]) -> dict[str, Any]:
    path = event_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".jsonl.lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise EntityIntegrityError("Entity journal is locked") from exc
    os.close(fd)
    try:
        rows = read_events(hub_root)
        same = [row for row in rows if row["request_id"] == event["request_id"]]
        if same:
            if same[-1]["request_digest"] != event["request_digest"]:
                raise EntityIntegrityError("Entity request id was reused with different content")
            return same[-1]
        previous = next(
            (row for row in reversed(rows) if row.get("stream_id") == event["stream_id"]),
            None,
        )
        event["prev_event_id"] = previous["event_id"] if previous else ""
        event["event_id"] = stable_id(
            "durable-entity-event",
            event["stream_id"],
            event["event_kind"],
            event["request_digest"],
            event["prev_event_id"],
        )
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json_dumps(event, pretty=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        confirmed = read_events(hub_root)[-1]
        if confirmed.get("event_id") != event["event_id"]:
            raise EntityIntegrityError("Entity append outcome could not be reconciled")
        return confirmed
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def register_entity(
    hub_root: Path,
    card: dict[str, Any],
    *,
    observation_id: str,
    source_ref: str,
    entity_id: str = "",
    predecessor_revision_id: str = "",
    request_id: str = "",
) -> dict[str, Any]:
    _require_initialized_root(hub_root)
    if card.get("entity_kind") not in ENTITY_KINDS:
        raise ValueError("Semantic card has an unsupported entity kind")
    minimized_source, _ = minimize_text(source_ref)
    candidate_id = stable_id("entity-candidate", observation_id)
    effective_id = entity_id or stable_id("entity", candidate_id)
    revision_id = stable_id(
        "entity-revision", effective_id, predecessor_revision_id, str(card["semantic_fingerprint"])
    )
    payload = {
        "entity_id": effective_id,
        "entity_revision_id": revision_id,
        "observation_id": observation_id,
        "source_ref": minimized_source,
        "predecessor_revision_id": predecessor_revision_id,
        "semantic_card": card,
        "review_status": "candidate",
        "execution_authorized": False,
    }
    request_digest = _digest(payload)
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_kind": "entity_registered" if not predecessor_revision_id else "entity_revision_added",
        "stream_id": effective_id,
        "request_id": request_id or stable_id("entity-request", request_digest),
        "request_digest": request_digest,
        "recorded_at": _now(),
        "payload": payload,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    recorded = _append(hub_root, event)
    write_state(hub_root)
    return recorded


def propose_relation(
    hub_root: Path,
    *,
    source_entity_id: str,
    target_entity_id: str,
    relation_type: str,
    source_revision_id: str,
    target_revision_id: str,
    evidence_refs: list[str],
    counterevidence: list[str] | None = None,
    methodology_revision: str = "entity-matching-v1",
    request_id: str = "",
) -> dict[str, Any]:
    _require_initialized_root(hub_root)
    if relation_type not in RELATION_TYPES:
        raise ValueError(f"Unknown relation type: {relation_type}")
    if source_entity_id == target_entity_id:
        raise ValueError("Self-relations are not permitted")
    payload = {
        "relation_id": stable_id(
            "entity-relation", source_entity_id, target_entity_id, relation_type, source_revision_id, target_revision_id
        ),
        "source_entity_id": source_entity_id,
        "target_entity_id": target_entity_id,
        "source_revision_id": source_revision_id,
        "target_revision_id": target_revision_id,
        "relation_type": relation_type,
        "evidence_refs": sorted(set(evidence_refs)),
        "counterevidence": sorted(set(counterevidence or [])),
        "methodology_revision": methodology_revision,
        "epistemic_state": "derived",
        "review_status": "candidate",
        "execution_authorized": False,
    }
    minimized, _ = minimize_payload(payload)
    if not isinstance(minimized, dict):
        raise ValueError("Relation payload must be an object")
    request_digest = _digest(minimized)
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_kind": "relation_proposed",
        "stream_id": str(minimized["relation_id"]),
        "request_id": request_id or stable_id("entity-relation-request", request_digest),
        "request_digest": request_digest,
        "recorded_at": _now(),
        "payload": minimized,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    recorded = _append(hub_root, event)
    write_state(hub_root)
    return recorded


def record_identity_decision(
    hub_root: Path,
    *,
    decision_id: str,
    disposition: str,
    source_entity_ids: list[str],
    target_entity_ids: list[str],
    human_approval_ref: str,
    rationale: str,
    request_id: str = "",
) -> dict[str, Any]:
    """Record an explicit decision without applying redirects or lifecycle changes."""

    _require_initialized_root(hub_root)
    allowed = {"accept_relation", "reject_relation", "keep_distinct", "merge", "split"}
    if disposition not in allowed:
        raise ValueError(f"Unsupported identity disposition: {disposition}")
    if not human_approval_ref:
        raise ValueError("Identity decisions require an explicit human approval reference")
    sources = sorted(set(source_entity_ids))
    targets = sorted(set(target_entity_ids))
    if not sources or (disposition in {"accept_relation", "merge", "split"} and not targets):
        raise ValueError("Identity decision endpoints are incomplete")
    payload = {
        "decision_id": decision_id,
        "disposition": disposition,
        "source_entity_ids": sources,
        "target_entity_ids": targets,
        "human_approval_ref": human_approval_ref,
        "rationale": minimize_text(rationale)[0],
        "review_status": "human_confirmed",
        "applied": False,
        "requires_separate_apply": disposition in {"merge", "split"},
        "execution_authorized": False,
    }
    request_digest = _digest(payload)
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_kind": "identity_decision_recorded",
        "stream_id": decision_id,
        "request_id": request_id or stable_id("identity-decision-request", request_digest),
        "request_digest": request_digest,
        "recorded_at": _now(),
        "payload": payload,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    recorded = _append(hub_root, event)
    write_state(hub_root)
    return recorded


def fold_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event["payload"]
        if event["event_kind"] in {"entity_registered", "entity_revision_added"}:
            entity_id = str(payload["entity_id"])
            entities[entity_id] = {
                **payload,
                "event_id": event["event_id"],
                "recorded_at": event["recorded_at"],
            }
        elif event["event_kind"] == "relation_proposed":
            relations[str(payload["relation_id"])] = {
                **payload,
                "event_id": event["event_id"],
                "recorded_at": event["recorded_at"],
            }
        elif event["event_kind"] == "identity_decision_recorded":
            decisions[str(payload["decision_id"])] = {
                **payload,
                "event_id": event["event_id"],
                "recorded_at": event["recorded_at"],
            }
    return {
        "schema_version": "dad.durable_entity_state.v1",
        "generated_at": _now(),
        "entities": sorted(entities.values(), key=lambda row: row["entity_id"]),
        "relations": sorted(relations.values(), key=lambda row: row["relation_id"]),
        "decisions": sorted(decisions.values(), key=lambda row: row["decision_id"]),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def write_state(hub_root: Path) -> dict[str, Any]:
    state = fold_state(read_events(hub_root))
    path = state_path(hub_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json_dumps(state) + "\n")
    return state


__all__ = [
    "AUTHORITY_BOUNDARY",
    "ENTITY_KINDS",
    "EntityIntegrityError",
    "RELATION_TYPES",
    "fold_state",
    "normalize_label",
    "propose_relation",
    "record_identity_decision",
    "read_events",
    "register_entity",
    "semantic_card",
    "write_state",
]
