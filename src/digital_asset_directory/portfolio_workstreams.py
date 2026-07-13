"""Portfolio OS workstream kernel (V0) — command surface and fold assembly.

Collaboration rework (see ``docs/frontier/collaboration/``): the durability,
privacy, relation, and attention organs live in ``portfolio_events``,
``portfolio_relations``, and ``portfolio_attention``; this module assembles
them into the capture / capsule / feedback / bind / state / refresh commands
and the local HTML board.

Loop proven here (all deterministic, no model calls, no Git mutation):

``capture idea -> retrieve related work -> explicit relationship assertions ->
propose separate workstreams -> preserve conversation context -> resume
capsule -> explainable focus queue capped at three``
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
import re
from typing import Any

from jsonschema.validators import validator_for

from .ids import stable_id
from .portfolio_attention import (
    AttentionPolicy,
    FEEDBACK_ACTIONS,
    LIFECYCLE_STATES,
    MAX_TODAY,
    TERMINAL_STATES,
    board_projection,
    days_since,
    dependency_rollup,
    evaluate_triggers,
    fold_lifecycle,
    latest_iso,
    relationship_class_stats,
    sprawl_clusters,
)
from .portfolio_events import (
    append_events,
    build_event,
    is_head_retry,
    ledger_path,
    minimize_text,
    read_events,
    stream_heads,
)
from .portfolio_relations import (
    DEFAULT_RELATION_LIMIT,
    RELATIONSHIP_TYPES,
    RelationTarget,
    classify_relations,
    normalize_text,
    proposal_for,
    short_label,
    targets_from_portfolio_report,
)
from .transport import data_path
from .utils import atomic_write_text, json_dumps

SCHEMA_VERSION = "dad.portfolio_workstreams.v1"

AUTHORITY_BOUNDARY = (
    "Portfolio workstream records are local, metadata-only candidate evidence. "
    "Relationship classes, workstream proposals, board columns, dependency "
    "rollups, and focus recommendations are explainable suggestions only. They "
    "never authorize commits, branch or worktree creation, checkout, merge, "
    "rebase, cleanup, deletion, cross-repo writes, or source-canon changes; a "
    "human decides every action."
)

PROPOSAL_KINDS = (
    "new_independent_workstream",
    "new_sibling_workstream",
    "new_experiment_workstream",
    "new_workstream_flagged_conflict",
    "resume_existing",
    "merge_or_dedupe",
)

BINDING_KINDS = (
    "repo",
    "branch",
    "worktree",
    "codex_task",
    "agent_run",
    "specification",
    "conversation",
    "depends_on",
    "blocks",
)

TRIGGER_FEEDBACK_METHOD_VERSION = "portfolio-trigger-feedback-projection.v0.1.0"
TRIGGER_FEEDBACK_CLASSES = {
    "resume": "accepted",
    "keep": "accepted",
    "merge": "accepted",
    "snooze": "suppressed",
    "incubate": "suppressed",
    "pause": "suppressed",
    "dismiss": "suppressed",
    "reject_decision": "rejected",
    "supersede": "rejected",
    "archive": "rejected",
}
TRIGGER_SIGNATURE_RE = re.compile(r"^dad:portfolio-trigger:[0-9a-f-]{36}$")

BINDING_STATUSES = ("proposed", "accepted")

# Sovereignty lifecycle for DAD-governed child projects (owner decision,
# 2026-07-12). Every transition is an explicit, human-approved ledger event.
SOVEREIGNTY_STATES = (
    "incubating",
    "dad_governed_child",
    "release_candidate",
    "delivery_approved",
    "client_sovereign",
    "maintained_upstream",
    "fully_detached",
)

SOVEREIGNTY_TRANSITIONS: dict[str, frozenset[str]] = {
    "incubating": frozenset({"dad_governed_child"}),
    "dad_governed_child": frozenset({"release_candidate"}),
    "release_candidate": frozenset({"delivery_approved", "dad_governed_child"}),
    "delivery_approved": frozenset({"client_sovereign", "dad_governed_child"}),
    "client_sovereign": frozenset(
        {"maintained_upstream", "fully_detached", "dad_governed_child"}
    ),
    "maintained_upstream": frozenset({"fully_detached", "dad_governed_child"}),
    "fully_detached": frozenset({"dad_governed_child"}),
}


class _SovereigntyTransitionRejected(RuntimeError):
    """An under-lock sovereignty precondition rejected a command."""

    def __init__(self, status: str, *, current_state: str = "") -> None:
        super().__init__(status)
        self.status = status
        self.current_state = current_state


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureSettings:
    """Immutable settings for one capture pass."""

    relation_limit: int = DEFAULT_RELATION_LIMIT
    captured_by: str = "human"
    source_kind: str = "chat_capture"

    def __post_init__(self) -> None:
        if not 0 <= self.relation_limit <= 25:
            raise ValueError("relation_limit must be between 0 and 25.")


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def idea_id_for(conversation_id: str, text: str) -> str:
    minimized_conversation, _ = minimize_text(normalize_text(conversation_id))
    minimized_text, _ = minimize_text(normalize_text(text))
    return stable_id("portfolio-idea", minimized_conversation, minimized_text.casefold())


def workstream_id_for(idea_id: str) -> str:
    return stable_id("portfolio-workstream", idea_id)


def project_id_for(name: str) -> str:
    minimized_name, _ = minimize_text(normalize_text(name))
    return stable_id("portfolio-project", minimized_name.casefold())


# ---------------------------------------------------------------------------
# Fold: events -> state
# ---------------------------------------------------------------------------


def fold_state(
    events: list[dict[str, Any]],
    *,
    diagnostics: dict[str, Any] | None = None,
    now: datetime | None = None,
    policy: AttentionPolicy | None = None,
    portfolio_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically fold the append-only ledger into current state."""

    observed = _now(now)
    policy = policy or AttentionPolicy()
    fold_diagnostics: list[str] = []
    coverage: list[dict[str, str]] = []

    ideas: dict[str, dict[str, Any]] = {}
    conversations: dict[str, dict[str, Any]] = {}
    proposals: dict[str, dict[str, Any]] = {}
    stream_events: dict[str, list[dict[str, Any]]] = {}
    bindings: dict[str, dict[str, dict[str, Any]]] = {}
    projects: dict[str, dict[str, Any]] = {}

    for event in events:  # ledger (append) order is fold order
        kind = event.get("event_kind")
        payload = event.get("payload", {})
        recorded_at = str(event.get("recorded_at", ""))
        if kind == "idea_captured":
            idea_id = str(payload.get("idea_id", ""))
            ideas[idea_id] = {
                "idea_id": idea_id,
                "text": str(payload.get("text", "")),
                "conversation_id": str(payload.get("conversation_id", "")),
                "conversation_title": str(payload.get("conversation_title", "")),
                "captured_at": recorded_at,
                "provenance": payload.get("provenance", {}),
            }
            conv_id = ideas[idea_id]["conversation_id"]
            if conv_id:
                conv = conversations.setdefault(
                    conv_id,
                    {"conversation_id": conv_id, "title": "", "idea_ids": []},
                )
                if idea_id not in conv["idea_ids"]:
                    conv["idea_ids"].append(idea_id)
                if ideas[idea_id]["conversation_title"]:
                    conv["title"] = ideas[idea_id]["conversation_title"]
        elif kind == "workstream_proposed":
            ws_id = str(payload.get("workstream_id", ""))
            proposals[ws_id] = {**payload, "proposed_at": recorded_at}
        elif kind in {"capsule_recorded", "focus_feedback"}:
            stream_events.setdefault(str(event.get("stream_id", "")), []).append(event)
        elif kind == "binding_asserted":
            ws_id = str(payload.get("workstream_id", ""))
            binding_id = str(payload.get("binding_id", ""))
            assertion_status = str(payload.get("assertion_status", "proposed"))
            existing_binding = bindings.setdefault(ws_id, {}).get(binding_id)
            if (
                existing_binding
                and existing_binding.get("assertion_status") == "accepted"
                and assertion_status == "proposed"
            ):
                fold_diagnostics.append(f"proposal_cannot_downgrade_accepted_binding:{binding_id}")
                continue
            bindings[ws_id][binding_id] = {
                "binding_id": binding_id,
                "binding_kind": str(payload.get("binding_kind", "")),
                "ref": str(payload.get("ref", "")),
                "label": str(payload.get("label", "")),
                "assertion_status": assertion_status,
                "asserted_by": str(payload.get("asserted_by", "")),
                "approval_ref": str(payload.get("approval_ref", "")),
                "recorded_at": recorded_at,
            }
        elif kind == "binding_retracted":
            ws_id = str(payload.get("workstream_id", ""))
            binding_id = str(payload.get("binding_id", ""))
            bindings.setdefault(ws_id, {}).pop(binding_id, None)
        elif kind == "project_registered":
            project_id = str(payload.get("project_id", ""))
            if not project_id:
                fold_diagnostics.append(f"project_without_id:{event.get('event_id', '')}")
                continue
            existing = projects.get(project_id)
            history = list(existing.get("sovereignty_history", [])) if existing else []
            projects[project_id] = {
                "project_id": project_id,
                "name": str(payload.get("name", "")),
                "parent_project_id": str(payload.get("parent_project_id", "")),
                "note": str(payload.get("note", "")),
                "sovereignty_state": existing.get("sovereignty_state", "incubating")
                if existing
                else "incubating",
                "state_since": existing.get("state_since", recorded_at) if existing else recorded_at,
                "registered_at": existing.get("registered_at", recorded_at)
                if existing
                else recorded_at,
                "sovereignty_history": history,
            }
        elif kind == "sovereignty_recorded":
            project_id = str(payload.get("project_id", ""))
            project = projects.get(project_id)
            target_state = str(payload.get("sovereignty_state", ""))
            if project is None:
                fold_diagnostics.append(f"sovereignty_without_project:{event.get('event_id', '')}")
                continue
            current_state = str(project["sovereignty_state"])
            if target_state not in SOVEREIGNTY_TRANSITIONS.get(current_state, frozenset()):
                fold_diagnostics.append(
                    f"illegal_sovereignty_transition:{current_state}->{target_state}"
                )
                continue
            project["sovereignty_state"] = target_state
            project["state_since"] = recorded_at
            project["sovereignty_history"].append(
                {
                    "from_state": current_state,
                    "to_state": target_state,
                    "decided_by": str(payload.get("decided_by", "")),
                    "approval_ref": str(payload.get("approval_ref", "")),
                    "note": str(payload.get("note", "")),
                    "recorded_at": recorded_at,
                }
            )

    workstreams: dict[str, dict[str, Any]] = {}
    for ws_id, proposal in proposals.items():
        idea = ideas.get(str(proposal.get("idea_id", "")))
        if idea is None:
            coverage.append({"workstream_id": ws_id, "note": "workstream without idea event"})
            continue
        lifecycle = fold_lifecycle(
            proposal["proposed_at"], stream_events.get(ws_id, []), fold_diagnostics
        )
        ws_bindings = sorted(bindings.get(ws_id, {}).values(), key=lambda b: b["binding_id"])
        feedback_events = [
            e for e in stream_events.get(ws_id, []) if e.get("event_kind") == "focus_feedback"
        ]
        conflict_resolved = any(
            e.get("payload", {}).get("action") in {"keep", "merge", "supersede", "archive"}
            for e in feedback_events
        )
        last_activity = latest_iso(
            idea["captured_at"],
            lifecycle["last_activity_event_at"],
            max((b["recorded_at"] for b in ws_bindings), default=""),
        )
        workstreams[ws_id] = {
            "workstream_id": ws_id,
            "idea_id": idea["idea_id"],
            "idea_text": short_label(idea["text"], limit=100),
            "proposal_kind": str(proposal.get("proposal_kind", "new_independent_workstream")),
            "recommended_action": str(proposal.get("recommended_action", "")),
            "needs_human_decision": bool(proposal.get("needs_human_decision", False)),
            "divergence": bool(proposal.get("divergence", False)),
            "relations": proposal.get("relations", []),
            "proposed_at": proposal["proposed_at"],
            "lifecycle_state": lifecycle["lifecycle_state"],
            "state_since": lifecycle["state_since"],
            "snooze_until": lifecycle["snooze_until"],
            "review_at": lifecycle["review_at"],
            "capsule": lifecycle["capsule"],
            "dismissals": lifecycle["dismissals"],
            "accept_actions": lifecycle["accept_actions"],
            "dismissal_epoch": lifecycle["dismissal_epoch"],
            "decision_rejected_at": lifecycle["decision_rejected_at"],
            "conflict_resolved": conflict_resolved,
            "bindings": ws_bindings,
            "dismiss_count": len(lifecycle["dismissals"]),
            "last_activity_at": last_activity,
            "inactive_days": days_since(last_activity, observed),
        }
        for note in proposal.get("coverage_notes", []):
            coverage.append({"workstream_id": ws_id, "note": str(note)})

    orphan_ideas = [
        idea_id for idea_id in ideas if workstream_id_for(idea_id) not in workstreams
    ]
    for idea_id in orphan_ideas:
        coverage.append({"workstream_id": "", "note": f"idea without workstream: {idea_id}"})

    adjacency: dict[str, set[str]] = {}
    for ws_id, ws in workstreams.items():
        for relation in ws.get("relations", []):
            target_id = str(relation.get("target_id", ""))
            if relation.get("target_kind") in {"workstream", "co_captured_idea"} and target_id in workstreams:
                adjacency.setdefault(ws_id, set()).add(target_id)
                adjacency.setdefault(target_id, set()).add(ws_id)

    snapshot_project_names: dict[str, str] = {}
    snapshot_attention_ids: set[str] = set()
    snapshot_ref: dict[str, Any] = {
        "status": "unavailable",
        "as_of": "",
        "source_hash": "",
    }
    if portfolio_snapshot is None:
        coverage.append({"workstream_id": "", "note": "portfolio_v1_snapshot_unavailable"})
    else:
        snapshot_project_names = {
            str(project.get("project_id", "")): str(project.get("name", "project"))
            for project in portfolio_snapshot.get("projects", [])
            if project.get("project_id")
        }
        snapshot_attention_ids = {
            str(item.get("project_id", ""))
            for item in portfolio_snapshot.get("attention_queue", [])
            if item.get("project_id")
        }
        canonical_snapshot = json.dumps(
            portfolio_snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        snapshot_ref = {
            "status": "provided",
            "as_of": str(portfolio_snapshot.get("generated_at", "")),
            "source_hash": stable_id("portfolio-v1-snapshot", canonical_snapshot),
        }

    class_stats = relationship_class_stats(
        workstreams, policy=policy, relationship_types=RELATIONSHIP_TYPES
    )
    dependencies = dependency_rollup(workstreams)
    for invalid in dependencies.get("invalid_assertions", []):
        coverage.append(
            {
                "workstream_id": str(invalid.get("source", "")),
                "note": (
                    f"dependency_{invalid.get('kind', 'invalid')}:"
                    f"{invalid.get('source', '')}->{invalid.get('target', '')}"
                ),
            }
        )
    active_ids = {ws_id for ws_id, ws in workstreams.items() if ws["lifecycle_state"] == "active"}

    focus_queue: list[dict[str, Any]] = []
    suppressed_count = 0
    for ws_id in sorted(workstreams):
        ws = workstreams[ws_id]
        item = evaluate_triggers(
            ws,
            policy=policy,
            now=observed,
            related_active_labels=[
                workstreams[n]["idea_text"] for n in sorted(adjacency.get(ws_id, set()) & active_ids)
            ]
            + sorted(
                {
                    snapshot_project_names.get(str(relation.get("target_id", "")), "project")
                    for relation in ws.get("relations", [])
                    if relation.get("target_kind") == "portfolio_project"
                    and str(relation.get("target_id", "")) in snapshot_attention_ids
                }
            ),
            dependency_info=dependencies["per_workstream"].get(ws_id),
            class_stats=class_stats,
            coverage=coverage,
        )
        if item["priority"] > 0:
            focus_queue.append(item)
        else:
            suppressed_count += 1
            if ws["lifecycle_state"] not in TERMINAL_STATES:
                focus_queue.append(item)  # kept visible with priority 0; sliced out of Today
    focus_queue.sort(
        key=lambda item: (-item["priority"], item["last_activity_at"], item["workstream_id"])
    )
    surfaced = [item for item in focus_queue if item["priority"] > 0]

    ws_public = [
        {key: value for key, value in ws.items() if key not in {"dismissals", "accept_actions"}}
        for ws in sorted(workstreams.values(), key=lambda w: (w["proposed_at"], w["workstream_id"]))
    ]
    open_count = sum(1 for ws in workstreams.values() if ws["lifecycle_state"] not in TERMINAL_STATES)
    ledger_diagnostics = dict(diagnostics or {})
    ledger_diagnostics["fold_problems"] = fold_diagnostics

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "status": "generated_candidate",
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "project_count": len(projects),
            "idea_count": len(ideas),
            "conversation_count": len(conversations),
            "workstream_count": len(workstreams),
            "open_workstream_count": open_count,
            "relation_count": sum(len(ws.get("relations", [])) for ws in workstreams.values()),
            "focus_item_count": len(surfaced),
            "today_item_count": min(MAX_TODAY, len(surfaced)),
            "suppressed_workstream_count": suppressed_count,
            "bottleneck_count": len(dependencies["bottlenecks"]),
            "sprawl_cluster_count": 0,  # replaced below; kept adjacent for readers
        },
        "conversations": sorted(conversations.values(), key=lambda conv: conv["conversation_id"]),
        "projects": sorted(projects.values(), key=lambda project: project["project_id"]),
        "ideas": sorted(ideas.values(), key=lambda idea: (idea["captured_at"], idea["idea_id"])),
        "workstreams": ws_public,
        "today": surfaced[:MAX_TODAY],
        "focus_queue": focus_queue,
        "board": board_projection(workstreams.values()),
        "dependencies": dependencies,
        "sprawl_clusters": sprawl_clusters(workstreams, policy=policy),
        "relationship_class_stats": class_stats,
        "coverage": coverage,
        "ledger_diagnostics": ledger_diagnostics,
        "portfolio_snapshot": snapshot_ref,
    }


def _finalize_summary(state: dict[str, Any]) -> dict[str, Any]:
    state["summary"]["sprawl_cluster_count"] = len(state["sprawl_clusters"])
    return state


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _targets_from_state(state: dict[str, Any]) -> list[RelationTarget]:
    idea_text_by_id = {idea["idea_id"]: idea["text"] for idea in state["ideas"]}
    targets: list[RelationTarget] = []
    for ws in state["workstreams"]:
        if ws["lifecycle_state"] in TERMINAL_STATES:
            continue
        text = idea_text_by_id.get(ws["idea_id"], "")
        if not text:
            continue
        mature = bool(ws.get("capsule")) or ws["lifecycle_state"] in {"active", "paused"}
        targets.append(
            RelationTarget(
                target_kind="workstream",
                target_id=ws["workstream_id"],
                target_label=short_label(text),
                text=text,
                mature=mature,
            )
        )
    return targets


def capture_ideas(
    hub_root: Path,
    idea_texts: list[str],
    *,
    conversation_id: str = "",
    conversation_title: str = "",
    portfolio_report: dict[str, Any] | None = None,
    settings: CaptureSettings | None = None,
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Capture one or more ideas from a single conversation.

    Idempotent including solo captures: a missing conversation id derives from
    the idea content, not the clock (audit C11). Ideas captured together become
    relation candidates for each other (C10) and share the conversation id so
    the connective context survives without storing raw chat.
    """

    settings = settings or CaptureSettings()
    observed = _now(now)
    recorded_at = observed.isoformat()

    minimized_texts: list[tuple[str, int]] = []
    for raw in idea_texts:
        minimized, count = minimize_text(raw)
        minimized = normalize_text(minimized)
        if minimized:
            minimized_texts.append((minimized, count))
    raw_conv_id = conversation_id or stable_id(
        "portfolio-conversation", *sorted(text.casefold() for text, _ in minimized_texts)
    )
    conv_id, _ = minimize_text(normalize_text(raw_conv_id))
    conv_title, _ = minimize_text(normalize_text(conversation_title))

    path = ledger_path(hub_root)
    events, diagnostics = read_events(path)
    state = fold_state(events, diagnostics=diagnostics, now=observed)
    ledger_targets = _targets_from_state(state)
    report_targets = targets_from_portfolio_report(portfolio_report) if portfolio_report else []

    new_events: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    batch_targets: list[RelationTarget] = []
    seen_idea_ids: set[str] = set()

    for text, redaction_count in minimized_texts:
        idea_id = idea_id_for(conv_id, text)
        if idea_id in seen_idea_ids:
            continue
        seen_idea_ids.add(idea_id)
        ws_id = workstream_id_for(idea_id)

        own_excluded = [t for t in ledger_targets if t.target_id != ws_id]
        relations, coverage_notes = classify_relations(
            ws_id,
            text,
            [*own_excluded, *batch_targets, *report_targets],
            limit=settings.relation_limit,
        )
        proposal = proposal_for(relations)

        idea_event, _ = build_event(
            event_kind="idea_captured",
            stream_id=idea_id,
            prev_event_id="",
            recorded_at=recorded_at,
            command_id=command_id,
            payload={
                "idea_id": idea_id,
                "text": text,
                "conversation_id": conv_id,
                "conversation_title": conv_title,
                "provenance": {
                    "captured_by": settings.captured_by,
                    "source_kind": settings.source_kind,
                },
            },
        )
        ws_event, _ = build_event(
            event_kind="workstream_proposed",
            stream_id=ws_id,
            prev_event_id="",
            recorded_at=recorded_at,
            command_id=command_id,
            payload={
                "workstream_id": ws_id,
                "idea_id": idea_id,
                "proposal_kind": proposal["proposal_kind"],
                "recommended_action": proposal["recommended_action"],
                "needs_human_decision": proposal["needs_human_decision"],
                "divergence": proposal["divergence"],
                "primary_relation_id": proposal["primary_relation_id"],
                "relations": relations,
                "coverage_notes": coverage_notes,
            },
        )
        new_events.extend([idea_event, ws_event])
        batch_targets.append(
            RelationTarget(
                target_kind="co_captured_idea",
                target_id=ws_id,
                target_label=short_label(text),
                text=text,
                mature=False,
            )
        )
        proposals.append(
            {
                "idea_id": idea_id,
                "workstream_id": ws_id,
                "idea_text": short_label(text, limit=100),
                "redaction_count": redaction_count,
                **proposal,
                "relations": relations,
                "coverage_notes": coverage_notes,
            }
        )

    append_result = append_events(path, new_events, recorded_at=recorded_at)
    return {
        "schema_version": "dad.portfolio_workstreams.capture.v1",
        "conversation_id": conv_id,
        "captured_count": len(proposals),
        **append_result,
        "ledger_path": str(path),
        "proposals": proposals,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _workstream_exists(events: list[dict[str, Any]], workstream_id: str) -> bool:
    return any(
        event.get("event_kind") == "workstream_proposed"
        and event.get("payload", {}).get("workstream_id") == workstream_id
        for event in events
    )


def record_capsule(
    hub_root: Path,
    workstream_id: str,
    *,
    pause_reason: str = "",
    blocker: str = "",
    last_check: str = "",
    next_action: str = "",
    snooze_days: int = 0,
    incubating: bool = False,
    review_days: int = 0,
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record a resume capsule. Chain identity: retries dedupe, updates land
    (fixes C5 — every field including ``last_check`` is payload)."""

    observed = _now(now)
    recorded_at = observed.isoformat()
    snooze_until = (observed + timedelta(days=snooze_days)).isoformat() if snooze_days > 0 else ""
    review_at = ""
    if incubating:
        days = review_days if review_days > 0 else AttentionPolicy().incubation_review_days
        review_at = (observed + timedelta(days=days)).isoformat()

    path = ledger_path(hub_root)
    events, _diagnostics = read_events(path)
    if not _workstream_exists(events, workstream_id):
        return {
            "schema_version": "dad.portfolio_workstreams.capsule.v1",
            "status": "unknown_workstream",
            "workstream_id": workstream_id,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    prev = stream_heads(events).get(workstream_id, "")
    minimized_pause_reason, _ = minimize_text(normalize_text(pause_reason))
    minimized_blocker, _ = minimize_text(normalize_text(blocker))
    minimized_last_check, _ = minimize_text(normalize_text(last_check))
    minimized_next_action, _ = minimize_text(normalize_text(next_action))
    payload = {
        "workstream_id": workstream_id,
        "pause_reason": minimized_pause_reason,
        "blocker": minimized_blocker,
        "last_check": minimized_last_check,
        "next_action": minimized_next_action,
        "snooze_until": snooze_until,
        "incubating": incubating,
        "review_at": review_at,
    }
    payload["capsule_id"] = stable_id(
        "portfolio-capsule", workstream_id, json.dumps(payload, sort_keys=True)
    )
    if is_head_retry(
        events,
        workstream_id,
        "capsule_recorded",
        payload,
        recorded_at=recorded_at,
        command_id=command_id,
    ):
        return {
            "schema_version": "dad.portfolio_workstreams.capsule.v1",
            "status": "deduplicated",
            "capsule_id": payload["capsule_id"],
            "workstream_id": workstream_id,
            "snooze_until": snooze_until,
            "review_at": review_at,
            "events_appended": 0,
            "ledger_path": str(path),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    event, _ = build_event(
        event_kind="capsule_recorded",
        stream_id=workstream_id,
        prev_event_id=prev,
        recorded_at=recorded_at,
        command_id=command_id,
        payload=payload,
    )
    append_result = append_events(path, [event], recorded_at=recorded_at)
    return {
        "schema_version": "dad.portfolio_workstreams.capsule.v1",
        "status": "recorded" if append_result["events_appended"] else "deduplicated",
        "capsule_id": payload["capsule_id"],
        "workstream_id": workstream_id,
        "snooze_until": snooze_until,
        "review_at": review_at,
        **append_result,
        "ledger_path": str(path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def record_feedback(
    hub_root: Path,
    workstream_id: str,
    action: str,
    *,
    note: str = "",
    snooze_days: int = 0,
    review_days: int = 0,
    trigger_signature: str = "",
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record feedback (resume/snooze/incubate/pause/dismiss/merge/supersede/
    archive). Chain identity: a crash retry dedupes; a genuine repeat after the
    stream advanced appends (fixes C4 both ways)."""

    if action not in FEEDBACK_ACTIONS:
        raise ValueError(f"Unknown feedback action '{action}'. Expected one of {FEEDBACK_ACTIONS}.")
    observed = _now(now)
    recorded_at = observed.isoformat()
    snooze_until = ""
    if action == "snooze":
        days = snooze_days if snooze_days > 0 else AttentionPolicy().stale_days
        snooze_until = (observed + timedelta(days=days)).isoformat()
    review_at = ""
    if action == "incubate":
        days = review_days if review_days > 0 else AttentionPolicy().incubation_review_days
        review_at = (observed + timedelta(days=days)).isoformat()

    path = ledger_path(hub_root)
    events, _diagnostics = read_events(path)
    if not _workstream_exists(events, workstream_id):
        return {
            "schema_version": "dad.portfolio_workstreams.feedback.v1",
            "status": "unknown_workstream",
            "workstream_id": workstream_id,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    prev = stream_heads(events).get(workstream_id, "")
    payload = {
        "workstream_id": workstream_id,
        "action": action,
        "note": normalize_text(note),
        "snooze_until": snooze_until,
        "review_at": review_at,
        "trigger_signature": trigger_signature,
    }
    if is_head_retry(
        events,
        workstream_id,
        "focus_feedback",
        payload,
        recorded_at=recorded_at,
        command_id=command_id,
    ):
        return {
            "schema_version": "dad.portfolio_workstreams.feedback.v1",
            "status": "deduplicated",
            "workstream_id": workstream_id,
            "action": action,
            "snooze_until": snooze_until,
            "review_at": review_at,
            "events_appended": 0,
            "ledger_path": str(path),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    event, _ = build_event(
        event_kind="focus_feedback",
        stream_id=workstream_id,
        prev_event_id=prev,
        recorded_at=recorded_at,
        command_id=command_id,
        payload=payload,
    )
    append_result = append_events(path, [event], recorded_at=recorded_at)
    return {
        "schema_version": "dad.portfolio_workstreams.feedback.v1",
        "status": "recorded" if append_result["events_appended"] else "deduplicated",
        "workstream_id": workstream_id,
        "action": action,
        "snooze_until": snooze_until,
        "review_at": review_at,
        **append_result,
        "ledger_path": str(path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def record_binding(
    hub_root: Path,
    workstream_id: str,
    binding_kind: str,
    ref: str,
    *,
    label: str = "",
    assertion_status: str = "proposed",
    asserted_by: str = "",
    approval_ref: str = "",
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assert a declarative binding (repo/branch/worktree/task/spec/dependency).

    Declarative only: nothing is created, verified against Git, or mutated.
    Agent-discovered bindings default to ``proposed`` and do not affect the
    board. Accepted assertions require a named approver and approval reference.
    Dependency refs must name another existing workstream."""

    if binding_kind not in BINDING_KINDS:
        raise ValueError(f"Unknown binding kind '{binding_kind}'. Expected one of {BINDING_KINDS}.")
    if assertion_status not in BINDING_STATUSES:
        raise ValueError(
            f"Unknown assertion status '{assertion_status}'. Expected one of {BINDING_STATUSES}."
        )
    if assertion_status == "accepted" and (not asserted_by.strip() or not approval_ref.strip()):
        raise ValueError("Accepted bindings require asserted_by and approval_ref.")
    observed = _now(now)
    recorded_at = observed.isoformat()
    path = ledger_path(hub_root)
    events, _diagnostics = read_events(path)
    if not _workstream_exists(events, workstream_id):
        return {
            "schema_version": "dad.portfolio_workstreams.binding.v1",
            "status": "unknown_workstream",
            "workstream_id": workstream_id,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    if binding_kind in {"depends_on", "blocks"} and not _workstream_exists(events, ref):
        return {
            "schema_version": "dad.portfolio_workstreams.binding.v1",
            "status": "unknown_dependency_target",
            "workstream_id": workstream_id,
            "ref": ref,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    if binding_kind in {"depends_on", "blocks"} and ref == workstream_id:
        return {
            "schema_version": "dad.portfolio_workstreams.binding.v1",
            "status": "self_dependency_rejected",
            "workstream_id": workstream_id,
            "ref": ref,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    minimized_ref, _ = minimize_text(normalize_text(ref))
    binding_id = stable_id(
        "portfolio-binding", workstream_id, binding_kind, minimized_ref.casefold()
    )
    prev = stream_heads(events).get(workstream_id, "")
    payload = {
        "workstream_id": workstream_id,
        "binding_id": binding_id,
        "binding_kind": binding_kind,
        "ref": minimized_ref,
        "label": normalize_text(label),
        "assertion_status": assertion_status,
        "asserted_by": normalize_text(asserted_by),
        "approval_ref": normalize_text(approval_ref),
    }
    if is_head_retry(
        events,
        workstream_id,
        "binding_asserted",
        payload,
        recorded_at=recorded_at,
        command_id=command_id,
    ):
        return {
            "schema_version": "dad.portfolio_workstreams.binding.v1",
            "status": "deduplicated",
            "binding_id": binding_id,
            "workstream_id": workstream_id,
            "binding_kind": binding_kind,
            "assertion_status": assertion_status,
            "events_appended": 0,
            "ledger_path": str(path),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    event, _ = build_event(
        event_kind="binding_asserted",
        stream_id=workstream_id,
        prev_event_id=prev,
        recorded_at=recorded_at,
        command_id=command_id,
        payload=payload,
    )
    append_result = append_events(path, [event], recorded_at=recorded_at)
    return {
        "schema_version": "dad.portfolio_workstreams.binding.v1",
        "status": "recorded" if append_result["events_appended"] else "deduplicated",
        "binding_id": binding_id,
        "workstream_id": workstream_id,
        "binding_kind": binding_kind,
        "assertion_status": assertion_status,
        **append_result,
        "ledger_path": str(path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def record_binding_retraction(
    hub_root: Path,
    workstream_id: str,
    binding_kind: str,
    ref: str,
    *,
    reason: str,
    retracted_by: str,
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Retract one binding through an append-only inverse event."""

    if binding_kind not in BINDING_KINDS:
        raise ValueError(f"Unknown binding kind '{binding_kind}'. Expected one of {BINDING_KINDS}.")
    if not reason.strip() or not retracted_by.strip():
        raise ValueError("Binding retraction requires reason and retracted_by.")
    observed = _now(now)
    recorded_at = observed.isoformat()
    path = ledger_path(hub_root)
    events, _diagnostics = read_events(path)
    if not _workstream_exists(events, workstream_id):
        return {
            "schema_version": "dad.portfolio_workstreams.binding_retraction.v1",
            "status": "unknown_workstream",
            "workstream_id": workstream_id,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    minimized_ref, _ = minimize_text(normalize_text(ref))
    binding_id = stable_id(
        "portfolio-binding", workstream_id, binding_kind, minimized_ref.casefold()
    )
    state = fold_state(events, now=observed)
    workstream = next(
        (row for row in state["workstreams"] if row["workstream_id"] == workstream_id), None
    )
    if workstream is None or not any(
        binding["binding_id"] == binding_id for binding in workstream.get("bindings", [])
    ):
        return {
            "schema_version": "dad.portfolio_workstreams.binding_retraction.v1",
            "status": "unknown_binding",
            "workstream_id": workstream_id,
            "binding_id": binding_id,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    prev = stream_heads(events).get(workstream_id, "")
    payload = {
        "workstream_id": workstream_id,
        "binding_id": binding_id,
        "reason": normalize_text(reason),
        "retracted_by": normalize_text(retracted_by),
    }
    event, _ = build_event(
        event_kind="binding_retracted",
        stream_id=workstream_id,
        prev_event_id=prev,
        recorded_at=recorded_at,
        command_id=command_id,
        payload=payload,
    )
    append_result = append_events(path, [event], recorded_at=recorded_at)
    return {
        "schema_version": "dad.portfolio_workstreams.binding_retraction.v1",
        "status": "retracted" if append_result["events_appended"] else "deduplicated",
        "workstream_id": workstream_id,
        "binding_id": binding_id,
        **append_result,
        "ledger_path": str(path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_trigger_feedback_projection(
    hub_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project privacy-minimized trigger feedback for the radar/grader.

    The projection reports categorical user actions only. It never copies note
    text, calculates a quality score, promotes a signature, or enables a routine.
    """

    events, diagnostics = read_events(ledger_path(hub_root))
    by_signature: dict[str, dict[str, Any]] = {}
    unsigned_count = 0
    invalid_signature_count = 0
    feedback_event_count = 0
    for event in events:
        if event.get("event_kind") != "focus_feedback":
            continue
        feedback_event_count += 1
        payload = event.get("payload", {})
        signature = str(payload.get("trigger_signature") or "")
        if not signature:
            unsigned_count += 1
            continue
        if not TRIGGER_SIGNATURE_RE.fullmatch(signature):
            invalid_signature_count += 1
            continue
        action = str(payload.get("action") or "")
        feedback_class = TRIGGER_FEEDBACK_CLASSES[action]
        row = by_signature.setdefault(
            signature,
            {
                "trigger_signature": signature,
                "workstream_ids": set(),
                "action_counts": {},
                "feedback_class_counts": {
                    "accepted": 0,
                    "suppressed": 0,
                    "rejected": 0,
                },
                "first_recorded_at": str(event.get("recorded_at") or ""),
                "last_recorded_at": str(event.get("recorded_at") or ""),
            },
        )
        row["workstream_ids"].add(str(payload.get("workstream_id") or ""))
        row["action_counts"][action] = int(row["action_counts"].get(action, 0)) + 1
        row["feedback_class_counts"][feedback_class] += 1
        row["first_recorded_at"] = min(
            str(row["first_recorded_at"]),
            str(event.get("recorded_at") or ""),
        )
        row["last_recorded_at"] = max(
            str(row["last_recorded_at"]),
            str(event.get("recorded_at") or ""),
        )
    signatures = []
    for signature, row in sorted(by_signature.items()):
        signatures.append(
            {
                "trigger_signature": signature,
                "workstream_ids": sorted(value for value in row["workstream_ids"] if value),
                "action_counts": dict(sorted(row["action_counts"].items())),
                "feedback_class_counts": row["feedback_class_counts"],
                "first_recorded_at": row["first_recorded_at"],
                "last_recorded_at": row["last_recorded_at"],
            }
        )
    projection = {
        "schema_version": "dad.portfolio.trigger_feedback.v1",
        "generated_at": _now(now).isoformat(),
        "methodology": {
            "method_version": TRIGGER_FEEDBACK_METHOD_VERSION,
            "accepted_actions": ["keep", "merge", "resume"],
            "suppressed_actions": ["dismiss", "incubate", "pause", "snooze"],
            "rejected_actions": ["archive", "reject_decision", "supersede"],
            "score_policy": "No score is calculated. Actions remain categorical evidence for shadow-trial review.",
            "privacy_policy": "Notes and invalid signature text are excluded; only valid generated signature IDs and workstream IDs are emitted.",
        },
        "coverage": {
            "feedback_event_count": feedback_event_count,
            "valid_signature_event_count": sum(
                sum(row["action_counts"].values()) for row in signatures
            ),
            "unsigned_event_count": unsigned_count,
            "invalid_signature_event_count": invalid_signature_count,
            "ledger_diagnostic_count": len(diagnostics.get("problems", []))
            + int(bool(diagnostics.get("torn_tail_pending", False))),
        },
        "signature_count": len(signatures),
        "signatures": signatures,
        "authority_boundary": (
            "Trigger feedback is local candidate calibration evidence. It cannot "
            "promote or rewrite a signature, change agent instructions, schedule a "
            "routine, notify a person, or mutate Git or an external system."
        ),
    }
    schema_path = hub_root / "schemas" / "portfolio-trigger-feedback.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    try:
        validator_cls(schema).validate(projection)
    except Exception as exc:
        raise ValueError(f"Invalid portfolio trigger feedback projection: {exc}") from exc
    return projection


def write_trigger_feedback_projection(hub_root: Path, projection: dict[str, Any]) -> Path:
    path = data_path(hub_root, "central_reports") / "portfolio_os" / "trigger_feedback.json"
    atomic_write_text(path, json_dumps(projection, pretty=True) + "\n")
    return path


def register_project(
    hub_root: Path,
    name: str,
    *,
    project_id: str = "",
    parent_project_id: str = "",
    note: str = "",
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Register a child project in the DAD sovereignty plane."""

    normalized_name = normalize_text(name)
    if not normalized_name:
        raise ValueError("Project name must not be empty.")
    observed = _now(now)
    recorded_at = observed.isoformat()
    path = ledger_path(hub_root)
    events, _diagnostics = read_events(path)
    minimized_project_id, _ = minimize_text(normalize_text(project_id))
    resolved_id = minimized_project_id or project_id_for(normalized_name)
    prev = stream_heads(events).get(resolved_id, "")
    payload = {
        "project_id": resolved_id,
        "name": normalized_name,
        "parent_project_id": normalize_text(parent_project_id),
        "note": normalize_text(note),
    }
    if is_head_retry(
        events,
        resolved_id,
        "project_registered",
        payload,
        recorded_at=recorded_at,
        command_id=command_id,
    ):
        return {
            "schema_version": "dad.portfolio_projects.registration.v1",
            "status": "deduplicated",
            "project_id": resolved_id,
            "events_appended": 0,
            "ledger_path": str(path),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    event, _ = build_event(
        event_kind="project_registered",
        stream_id=resolved_id,
        prev_event_id=prev,
        recorded_at=recorded_at,
        command_id=command_id,
        payload=payload,
    )
    append_result = append_events(path, [event], recorded_at=recorded_at)
    return {
        "schema_version": "dad.portfolio_projects.registration.v1",
        "status": "registered" if append_result["events_appended"] else "deduplicated",
        "project_id": resolved_id,
        "sovereignty_state": "incubating",
        **append_result,
        "ledger_path": str(path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def record_sovereignty(
    hub_root: Path,
    project_id: str,
    sovereignty_state: str,
    *,
    decided_by: str,
    approval_ref: str,
    note: str = "",
    command_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record one legal, human-approved child-project sovereignty transition."""

    minimized_project_id, _ = minimize_text(normalize_text(project_id))
    if not minimized_project_id:
        return {
            "schema_version": "dad.portfolio_projects.sovereignty.v1",
            "status": "unknown_project",
            "project_id": minimized_project_id,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    if sovereignty_state not in SOVEREIGNTY_STATES:
        raise ValueError(
            f"Unknown sovereignty state '{sovereignty_state}'. Expected one of {SOVEREIGNTY_STATES}."
        )
    if not decided_by.strip() or not approval_ref.strip():
        raise ValueError("Sovereignty transitions require decided_by and approval_ref.")
    observed = _now(now)
    recorded_at = observed.isoformat()
    path = ledger_path(hub_root)
    payload = {
        "project_id": minimized_project_id,
        "sovereignty_state": sovereignty_state,
        "decided_by": normalize_text(decided_by),
        "approval_ref": normalize_text(approval_ref),
        "note": normalize_text(note),
    }
    event, _ = build_event(
        event_kind="sovereignty_recorded",
        stream_id=minimized_project_id,
        # append_events rebases under the ledger lock after the precondition.
        prev_event_id="",
        recorded_at=recorded_at,
        command_id=command_id,
        payload=payload,
    )
    transition: dict[str, str] = {}

    def validate_transition(
        events: list[dict[str, Any]], diagnostics: dict[str, Any]
    ) -> None:
        # Let append_events adjudicate an explicit retry/conflict after deriving
        # the current state, but before applying the transition precondition to
        # new command intent.
        existing_command = any(
            existing.get("stream_id") == event["stream_id"]
            and existing.get("command_id") == event["command_id"]
            for existing in events
        )
        state = fold_state(events, diagnostics=diagnostics, now=observed)
        project = next(
            (
                row
                for row in state.get("projects", [])
                if row["project_id"] == minimized_project_id
            ),
            None,
        )
        if project is None:
            raise _SovereigntyTransitionRejected("unknown_project")
        current_state = str(project["sovereignty_state"])
        transition["from_state"] = current_state
        if existing_command:
            return
        if sovereignty_state not in SOVEREIGNTY_TRANSITIONS.get(
            current_state, frozenset()
        ):
            raise _SovereigntyTransitionRejected(
                "illegal_transition", current_state=current_state
            )

    try:
        append_result = append_events(
            path,
            [event],
            recorded_at=recorded_at,
            validate_existing=validate_transition,
        )
    except _SovereigntyTransitionRejected as exc:
        result = {
            "schema_version": "dad.portfolio_projects.sovereignty.v1",
            "status": exc.status,
            "project_id": minimized_project_id,
            "events_appended": 0,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        if exc.current_state:
            result.update(
                {
                    "from_state": exc.current_state,
                    "to_state": sovereignty_state,
                }
            )
        return result
    current_state = transition.get("from_state", "")
    return {
        "schema_version": "dad.portfolio_projects.sovereignty.v1",
        "status": "recorded" if append_result["events_appended"] else "deduplicated",
        "project_id": minimized_project_id,
        "from_state": current_state,
        "to_state": sovereignty_state,
        **append_result,
        "ledger_path": str(path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def load_state(
    hub_root: Path,
    *,
    now: datetime | None = None,
    policy: AttentionPolicy | None = None,
    portfolio_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events, diagnostics = read_events(ledger_path(hub_root))
    return _finalize_summary(
        fold_state(
            events,
            diagnostics=diagnostics,
            now=now,
            policy=policy,
            portfolio_snapshot=portfolio_snapshot,
        )
    )


def _load_portfolio_snapshot(hub_root: Path) -> dict[str, Any] | None:
    path = data_path(hub_root, "central_reports") / "portfolio_attention.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _today_fingerprints(items: list[dict[str, Any]]) -> list[str]:
    """Canonical user-visible Today fingerprints for change-gated activation."""

    material_keys = (
        "workstream_id",
        "trigger_signature",
        "trigger_kind",
        "tier",
        "priority",
        "reasons",
        "next_action",
        "lifecycle_state",
    )
    return [
        stable_id(
            "portfolio-today-item",
            json.dumps(
                {key: item.get(key) for key in material_keys},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ),
        )
        for item in items
    ]


def write_state_outputs(hub_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    base = data_path(hub_root, "central_reports") / "portfolio_os"
    json_path = base / "workstream_state.json"
    html_path = base / "workstream_state.html"
    atomic_write_text(json_path, json_dumps(state, pretty=True) + "\n")
    atomic_write_text(html_path, workstream_state_html(state))
    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "summary": state["summary"],
        "today": state["today"],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "generated_at": state["generated_at"],
    }


def refresh(
    hub_root: Path,
    *,
    now: datetime | None = None,
    policy: AttentionPolicy | None = None,
) -> dict[str, Any]:
    """M8 trigger target: fold, render, and report whether Today changed.

    Idempotent and read-only outside the kernel's own report files, so any
    activator (human, timer, routine, session hook) can call it safely.
    User-facing notification should gate on ``today_changed``."""

    json_path = data_path(hub_root, "central_reports") / "portfolio_os" / "workstream_state.json"
    previous_fingerprints: list[str] = []
    if json_path.exists():
        try:
            previous = json.loads(json_path.read_text(encoding="utf-8"))
            previous_fingerprints = _today_fingerprints(list(previous.get("today", [])))
        except (OSError, json.JSONDecodeError):
            previous_fingerprints = []
    snapshot = _load_portfolio_snapshot(hub_root)
    state = load_state(
        hub_root,
        now=now,
        policy=policy,
        portfolio_snapshot=snapshot,
    )
    outputs = write_state_outputs(hub_root, state)
    current_fingerprints = _today_fingerprints(state["today"])
    return {
        "schema_version": "dad.portfolio_workstreams.refresh.v1",
        "today_changed": current_fingerprints != previous_fingerprints,
        "today_count": len(current_fingerprints),
        "portfolio_snapshot": state["portfolio_snapshot"],
        **outputs,
    }


# ---------------------------------------------------------------------------
# Local HTML board (self-contained, escaped)
# ---------------------------------------------------------------------------


def workstream_state_html(state: dict[str, Any]) -> str:
    summary = state["summary"]
    project_rows = "".join(
        (
            f"<li><strong>{escape(project['name'])}</strong> "
            f"<code>{escape(project['sovereignty_state'])}</code></li>"
        )
        for project in state.get("projects", [])
    )
    today_cards: list[str] = []
    for item in state["today"]:
        reasons = " · ".join(escape(reason) for reason in item["reasons"])
        today_cards.append(
            f"""
            <article class="card tier-{escape(item['tier'])}">
              <div class="eyebrow">{escape(item['tier'])} · {escape(item['trigger_kind'])}</div>
              <h3>{escape(item['idea_text'])}</h3>
              <p>{reasons or 'No specific trigger.'}</p>
              <code>{escape(item['proposal_kind'])}</code>
            </article>
            """
        )
    if not today_cards:
        today_cards.append(
            '<article class="card"><h3>Nothing needs you today</h3>'
            "<p>Every open workstream is intentional, snoozed, incubating, or waiting upstream.</p></article>"
        )

    board_columns: list[str] = []
    for lifecycle_state in LIFECYCLE_STATES:
        cards = state["board"].get(lifecycle_state, [])
        entries = "".join(f"<li>{escape(card['idea_text'])}</li>" for card in cards)
        board_columns.append(
            f'<div class="col"><h4>{escape(lifecycle_state)} ({len(cards)})</h4><ul>{entries or "<li class=empty>—</li>"}</ul></div>'
        )

    bottleneck_rows = "".join(
        f"<li><code>{escape(b['workstream_id'])}</code> blocks {b['blocking_count']} workstream(s)</li>"
        for b in state["dependencies"]["bottlenecks"]
    )
    sprawl_rows = "".join(
        f"<li>{escape(cluster['reason'])}</li>" for cluster in state["sprawl_clusters"]
    )

    workstream_rows: list[str] = []
    for workstream in state["workstreams"]:
        relations = "; ".join(
            f"{escape(rel['relationship_type'])} → {escape(rel['target_label'])}"
            for rel in workstream["relations"]
        )
        workstream_rows.append(
            f"""
            <tr>
              <td>{escape(workstream['idea_text'])}</td>
              <td><code>{escape(workstream['lifecycle_state'])}</code></td>
              <td><code>{escape(workstream['proposal_kind'])}</code></td>
              <td>{relations or '<em>no prior work</em>'}</td>
            </tr>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DAD Portfolio OS — Workstreams</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0b1020; --panel:#141b2d; --line:#27314a; --text:#edf2ff; --muted:#9eabc7; --accent:#8bb8ff; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:linear-gradient(135deg,#080c18,#101a31 55%,#0b1020); color:var(--text); font:15px/1.5 ui-sans-serif,system-ui,sans-serif; }}
    main {{ width:min(1200px,94vw); margin:0 auto; padding:48px 0 80px; }}
    h1 {{ font-size:clamp(1.8rem,4vw,3.4rem); margin:.25rem 0 1rem; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.11em; color:var(--accent); font-size:.72rem; font-weight:800; }}
    .muted {{ color:var(--muted); max-width:820px; }}
    .stats {{ display:grid; grid-template-columns:repeat(5,minmax(120px,1fr)); gap:12px; margin:26px 0; }}
    .stat,.card,.table-wrap,.col {{ background:rgba(20,27,45,.9); border:1px solid var(--line); border-radius:16px; }}
    .stat {{ padding:16px; }} .stat strong {{ display:block; font-size:1.8rem; }} .stat span {{ color:var(--muted); }}
    .today {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }} .card {{ padding:18px; }} .card p {{ min-height:44px; }}
    code {{ color:#b9d4ff; overflow-wrap:anywhere; }}
    .tier-interrupt {{ border-color:#ff8f8f; }} .tier-nudge {{ border-color:#ffca70; }} .tier-weekly {{ border-color:#8bb8ff; }}
    .board {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }} .col {{ padding:12px 14px; }}
    .col h4 {{ margin:.2rem 0 .5rem; color:var(--muted); text-transform:uppercase; font-size:.72rem; letter-spacing:.08em; }}
    .col ul {{ margin:0; padding-left:18px; }} .col li.empty {{ list-style:none; color:var(--muted); }}
    .table-wrap {{ overflow:auto; margin-top:12px; }} table {{ width:100%; border-collapse:collapse; }}
    th,td {{ padding:12px 14px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ position:sticky; top:0; background:#151d30; color:var(--muted); font-size:.74rem; text-transform:uppercase; letter-spacing:.08em; }}
    footer {{ margin-top:42px; color:var(--muted); border-top:1px solid var(--line); padding-top:18px; }}
    @media (max-width:820px) {{ .stats,.today,.board {{ grid-template-columns:1fr 1fr; }} }}
  </style>
</head>
<body>
<main>
  <div class="eyebrow">DAD · Portfolio OS workstream kernel</div>
  <h1>What is worth your attention?</h1>
  <p class="muted">Local metadata only. Relationship classes, board columns, dependency rollups, and focus items are explainable candidates; DAD never creates, cleans, deletes, commits, merges, or changes a branch or repository from this view.</p>
  <section class="stats">
    <div class="stat"><strong>{summary['project_count']}</strong><span>governed projects</span></div>
    <div class="stat"><strong>{summary['idea_count']}</strong><span>ideas</span></div>
    <div class="stat"><strong>{summary['open_workstream_count']}</strong><span>open workstreams</span></div>
    <div class="stat"><strong>{summary['focus_item_count']}</strong><span>focus items</span></div>
    <div class="stat"><strong>{summary['bottleneck_count']}</strong><span>bottlenecks</span></div>
  </section>
  {f'<h2>Project sovereignty</h2><ul>{project_rows}</ul>' if project_rows else ''}
  <h2>Today (max {MAX_TODAY})</h2>
  <section class="today">{''.join(today_cards)}</section>
  <h2>Board</h2>
  <section class="board">{''.join(board_columns)}</section>
  {f'<h2>Bottlenecks</h2><ul>{bottleneck_rows}</ul>' if bottleneck_rows else ''}
  {f'<h2>Sprawl check</h2><ul>{sprawl_rows}</ul>' if sprawl_rows else ''}
  <h2>Workstreams</h2>
  <div class="table-wrap"><table><thead><tr><th>Idea</th><th>State</th><th>Proposal</th><th>Related prior work</th></tr></thead><tbody>{''.join(workstream_rows)}</tbody></table></div>
  <footer>Generated {escape(state['generated_at'])}. {escape(state['authority_boundary'])}</footer>
</main>
</body>
</html>
"""


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BINDING_KINDS",
    "BINDING_STATUSES",
    "CaptureSettings",
    "PROPOSAL_KINDS",
    "SCHEMA_VERSION",
    "SOVEREIGNTY_STATES",
    "SOVEREIGNTY_TRANSITIONS",
    "capture_ideas",
    "build_trigger_feedback_projection",
    "fold_state",
    "idea_id_for",
    "load_state",
    "record_binding",
    "record_binding_retraction",
    "record_capsule",
    "record_feedback",
    "record_sovereignty",
    "register_project",
    "refresh",
    "project_id_for",
    "workstream_id_for",
    "workstream_state_html",
    "write_state_outputs",
    "write_trigger_feedback_projection",
]
