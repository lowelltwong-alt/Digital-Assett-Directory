"""Rebuildable global and per-repository Intent Continuity projections."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .ids import stable_id
from .portfolio_continuity_attention import build_progressive_attention_readiness
from .portfolio_continuity_workflow import project_continuity_state
from .transport import data_path, resolve_data_root
from .utils import atomic_write_text, json_dumps


SCHEMA_VERSION = "dad.portfolio_continuity_projection.v1"
AUTHORITY_BOUNDARY = (
    "Intent continuity graphs and queues are rebuildable candidate projections. "
    "They do not merge identities, transition lifecycle, establish completion, "
    "create or remove worktrees, archive tasks, delete branches, notify, schedule, "
    "or authorize execution."
)
QUIET_LIFECYCLES = frozenset({"snoozed", "incubating", "superseded", "archived", "merged"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _latest(*values: str) -> str:
    valid = [(parsed, value) for value in values if (parsed := _parse(value)) is not None]
    return max(valid)[1] if valid else ""


def _activity_key(event: dict[str, Any]) -> str:
    payload = event.get("payload", {})
    for field in ("entity_id", "workstream_id", "plan_id", "task_id", "repository_id"):
        value = str(payload.get(field, ""))
        if value:
            return value
    return str(event.get("stream_id", ""))


def fold_continuity_activity(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Fold explicit activity facts; duration exists only for paired sessions."""

    groups: dict[str, dict[str, Any]] = {}
    starts: dict[tuple[str, str], datetime] = {}
    for event in sorted(events, key=lambda row: (str(row.get("observed_at", "")), str(row.get("event_id", "")))):
        key = _activity_key(event)
        if not key:
            continue
        observed_at = str(event.get("observed_at", ""))
        payload = event.get("payload", {})
        row = groups.setdefault(
            key,
            {
                "subject_id": key,
                "first_observed_at": observed_at,
                "last_observed_at": observed_at,
                "last_material_activity_at": "",
                "session_count": 0,
                "completed_session_count": 0,
                "interruption_count": 0,
                "resumption_count": 0,
                "engaged_duration_seconds": 0,
                "duration_coverage": "no_paired_sessions",
            },
        )
        row["first_observed_at"] = min(
            value for value in [row["first_observed_at"], observed_at] if value
        )
        row["last_observed_at"] = _latest(row["last_observed_at"], observed_at)
        material_at = str(payload.get("last_material_activity_at", ""))
        if event.get("event_kind") in {
            "session_started",
            "session_stopped",
            "turn_stopped",
            "interruption_observed",
            "resumption_observed",
        }:
            material_at = material_at or observed_at
        row["last_material_activity_at"] = _latest(row["last_material_activity_at"], material_at)
        event_kind = str(event.get("event_kind", ""))
        session_id = str(payload.get("session_id", ""))
        if event_kind == "session_started":
            row["session_count"] += 1
            if session_id and (parsed := _parse(observed_at)) is not None:
                starts[(key, session_id)] = parsed
        elif event_kind == "session_stopped" and session_id:
            stopped = _parse(observed_at)
            started = starts.get((key, session_id))
            if started is not None and stopped is not None and stopped >= started:
                row["completed_session_count"] += 1
                row["engaged_duration_seconds"] += int((stopped - started).total_seconds())
                row["duration_coverage"] = "explicit_paired_sessions_only"
        elif event_kind == "interruption_observed":
            row["interruption_count"] += 1
        elif event_kind == "resumption_observed":
            row["resumption_count"] += 1
    return groups


def _node(node_id: str, node_kind: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "node_kind": node_kind,
        "evidence": evidence,
        "candidate_only": True,
    }


def _edge(source: str, relation: str, target: str, evidence_ref: str) -> dict[str, Any]:
    material = {"source": source, "relation": relation, "target": target, "evidence_ref": evidence_ref}
    return {
        "edge_id": stable_id("portfolio-continuity-edge", _digest(material)),
        **material,
        "review_status": "candidate",
        "candidate_only": True,
    }


def build_continuity_projection(
    *,
    inventories: Iterable[dict[str, Any]] = (),
    plan_index: dict[str, Any] | None = None,
    roadmap: dict[str, Any] | None = None,
    workstream_state: dict[str, Any] | None = None,
    entity_state: dict[str, Any] | None = None,
    continuity_events: Iterable[dict[str, Any]] = (),
    execution_control: dict[str, Any] | None = None,
    search_results: Iterable[dict[str, Any]] = (),
    closeout_assessments: Iterable[dict[str, Any]] = (),
    external_coverage_gaps: Iterable[str] = (),
    activation_state: dict[str, Any] | None = None,
    stage_approvals: Iterable[dict[str, Any]] | None = None,
    adapter_interface_digest: str = "",
    previous_weekly_fingerprints: Iterable[str] = (),
) -> dict[str, Any]:
    """Build deterministic graphs and humane queues from immutable evidence."""

    inventory_rows = sorted(inventories, key=lambda row: str(row.get("repository_id", "")))
    plans = sorted((plan_index or {}).get("plans", []), key=lambda row: str(row.get("plan_id", "")))
    roadmap_rows = sorted((roadmap or {}).get("items", []), key=lambda row: str(row.get("item_id", "")))
    workstreams = sorted((workstream_state or {}).get("workstreams", []), key=lambda row: str(row.get("workstream_id", "")))
    entities = sorted((entity_state or {}).get("entities", []), key=lambda row: str(row.get("entity_id", "")))
    events = list(continuity_events)
    activity = fold_continuity_activity(events)
    workstream_by_id = {str(row.get("workstream_id", "")): row for row in workstreams}

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    repo_views: list[dict[str, Any]] = []
    repo_local_nodes: dict[str, set[str]] = {}
    coverage_gaps: list[str] = [str(value) for value in external_coverage_gaps]

    for inventory in inventory_rows:
        repository_id = str(inventory.get("repository_id", ""))
        nodes[repository_id] = _node(
            repository_id,
            "repository",
            {
                "inventory_fingerprint": str(inventory.get("inventory_fingerprint", "")),
            },
        )
        local_node_ids: list[str] = [repository_id]
        for obj in inventory.get("objects", []):
            commit_id = "commit:" + str(obj.get("object_id", ""))
            nodes[commit_id] = _node(
                commit_id,
                "commit",
                {
                    "object_id": str(obj.get("object_id", "")),
                    "committed_at": str(obj.get("committed_at", "")),
                },
            )
            local_node_ids.append(commit_id)
            for ref_id in obj.get("ref_ids", []):
                ref_id = str(ref_id)
                nodes.setdefault(ref_id, _node(ref_id, "ref", {}))
                edge = _edge(repository_id, "contains", ref_id, str(inventory.get("inventory_fingerprint", "")))
                edges[edge["edge_id"]] = edge
                edge = _edge(ref_id, "observed_as", commit_id, str(inventory.get("inventory_fingerprint", "")))
                edges[edge["edge_id"]] = edge
                local_node_ids.append(ref_id)
        for worktree in inventory.get("worktrees", []):
            worktree_id = str(worktree.get("worktree_id", ""))
            nodes[worktree_id] = _node(
                worktree_id,
                "worktree",
                {
                    "head_id": str(worktree.get("head_id", "")),
                    "dirty": worktree.get("dirty"),
                    "changes": dict(worktree.get("changes", {})),
                    "overlay_fingerprint": str(worktree.get("overlay_fingerprint", "")),
                },
            )
            edge = _edge(repository_id, "contains", worktree_id, str(inventory.get("inventory_fingerprint", "")))
            edges[edge["edge_id"]] = edge
            local_node_ids.append(worktree_id)
        for task in inventory.get("codex_items", []):
            task_id = str(task.get("codex_item_id", ""))
            nodes[task_id] = _node(task_id, "codex_task", dict(task))
            edge = _edge(repository_id, "contains", task_id, str(task.get("metadata_fingerprint", "")))
            edges[edge["edge_id"]] = edge
            local_node_ids.append(task_id)
        gaps = list(inventory.get("coverage", {}).get("gaps", []))
        coverage_gaps.extend(f"{repository_id}:{gap}" for gap in gaps)
        repo_views.append(
            {
                "repository_id": repository_id,
                "node_ids": sorted(set(local_node_ids)),
                "coverage_gaps": sorted(set(gaps)),
                "source_fingerprint": str(inventory.get("inventory_fingerprint", "")),
            }
        )
        repo_local_nodes[repository_id] = set(local_node_ids)

    for entity in entities:
        entity_id = str(entity.get("entity_id", ""))
        if entity_id:
            nodes[entity_id] = _node(
                entity_id,
                "entity",
                {"entity_kind": str(entity.get("entity_kind", "")), "revision_id": str(entity.get("revision_id", ""))},
            )

    for plan in plans:
        plan_id = str(plan.get("plan_id", ""))
        workstream = next(
            (
                workstream_by_id[ref]
                for ref in plan.get("workstream_refs", [])
                if ref in workstream_by_id
            ),
            None,
        )
        state = project_continuity_state(
            plan=plan,
            workstream=workstream,
            execution_control=execution_control,
        )
        nodes[plan_id] = _node(
            plan_id,
            "plan_revision",
            {
                "revision_id": str(plan.get("revision_id", "")),
                "implementation_state": str(plan.get("implementation_state", "")),
                "lifecycle": str(plan.get("lifecycle", "")),
                "recorded_at": str(plan.get("recorded_at", "")),
                "state_fingerprint": state["state_fingerprint"],
            },
        )
        for entity_id in plan.get("entity_refs", []):
            if str(entity_id) in nodes:
                edge = _edge(plan_id, "plans_for", str(entity_id), str(plan.get("revision_id", "")))
                edges[edge["edge_id"]] = edge
        for binding in plan.get("source_bindings", []):
            target = str(binding)
            if target not in nodes:
                continue
            edge = _edge(plan_id, "bound_to", target, str(plan.get("revision_id", "")))
            edges[edge["edge_id"]] = edge
            for repository_id, local_nodes in repo_local_nodes.items():
                if target == repository_id or target in local_nodes:
                    local_nodes.add(plan_id)

    for item in roadmap_rows:
        item_id = str(item.get("item_id", ""))
        nodes[item_id] = _node(
            item_id,
            "roadmap_item",
            {
                "status": str(item.get("status", "")),
                "recorded_at": str(item.get("recorded_at", "")),
                "last_event_id": str(item.get("last_event_id", "")),
            },
        )

    for item in roadmap_rows:
        item_id = str(item.get("item_id", ""))
        plan_id = str(item.get("plan_id", ""))
        if plan_id and plan_id in nodes:
            edge = _edge(plan_id, "contains", item_id, str(item.get("last_event_id", "")))
            edges[edge["edge_id"]] = edge
        elif plan_id:
            coverage_gaps.append("roadmap_plan_reference_unresolved")
        for dependency in item.get("dependency_item_ids", []):
            target = str(dependency)
            if target in nodes:
                edge = _edge(item_id, "depends_on", target, str(item.get("last_event_id", "")))
                edges[edge["edge_id"]] = edge
            else:
                coverage_gaps.append("roadmap_dependency_reference_unresolved")

    for workstream in workstreams:
        workstream_id = str(workstream.get("workstream_id", ""))
        nodes[workstream_id] = _node(
            workstream_id,
            "workstream",
            {
                "lifecycle_state": str(workstream.get("lifecycle_state", "")),
                "state_since": str(workstream.get("state_since", "")),
                "last_activity_at": str(workstream.get("last_activity_at", "")),
            },
        )

    for workstream in workstreams:
        workstream_id = str(workstream.get("workstream_id", ""))
        for binding in workstream.get("bindings", []):
            if str(binding.get("assertion_status", "")) != "accepted":
                continue
            target = str(binding.get("ref", ""))
            if not target:
                continue
            if target not in nodes:
                coverage_gaps.append("accepted_binding_target_unresolved")
                continue
            edge = _edge(workstream_id, "bound_to", target, str(binding.get("binding_id", "")))
            edges[edge["edge_id"]] = edge
            for repository_id, local_nodes in repo_local_nodes.items():
                if target != repository_id and target not in local_nodes:
                    continue
                local_nodes.add(workstream_id)
                local_nodes.update(
                    str(plan.get("plan_id", ""))
                    for plan in plans
                    if workstream_id in plan.get("workstream_refs", [])
                )

    for repository in repo_views:
        repository["node_ids"] = sorted(
            repo_local_nodes.get(str(repository["repository_id"]), set())
        )

    duplicate_queue_by_candidates: dict[tuple[str, ...], dict[str, Any]] = {}
    for result in search_results:
        candidates = list(result.get("candidates", []))
        if len(candidates) < 2:
            continue
        row = {
            "queue_id": stable_id("portfolio-possible-duplicate", str(result.get("query_digest", ""))),
            "query_digest": str(result.get("query_digest", "")),
            "candidate_ids": sorted(str(item.get("candidate_id", "")) for item in candidates),
            "classification": str(result.get("classification", "")),
            "primary_candidate_id": "",
            "requires_human_decision": True,
            "candidate_only": True,
        }
        candidate_key = tuple(row["candidate_ids"])
        duplicate_queue_by_candidates.setdefault(candidate_key, row)
    duplicate_queue = list(duplicate_queue_by_candidates.values())

    current_state: list[dict[str, Any]] = []
    interrupted: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []
    for plan in plans:
        plan_id = str(plan.get("plan_id", ""))
        related_workstream = next(
            (
                workstream_by_id[ref]
                for ref in plan.get("workstream_refs", [])
                if ref in workstream_by_id
            ),
            {},
        )
        subject_activity = activity.get(plan_id, {})
        state = project_continuity_state(
            plan=plan,
            workstream=related_workstream,
            execution_control=execution_control,
        )
        current_state.append(
            {
                "plan_id": plan_id,
                "plan_revision_id": str(plan.get("revision_id", "")),
                "workstream_id": str(related_workstream.get("workstream_id", "")),
                "durable_lifecycle": state["durable_lifecycle"],
                "overlays": state["overlays"],
                "next_action": state["next_action"],
                "last_material_activity_at": str(subject_activity.get("last_material_activity_at", "")),
                "session_count": int(subject_activity.get("session_count", 0)),
                "interruption_count": int(subject_activity.get("interruption_count", 0)),
                "state_fingerprint": state["state_fingerprint"],
            }
        )
        lifecycle = str(related_workstream.get("lifecycle_state", ""))
        is_interrupted = (
            int(subject_activity.get("interruption_count", 0))
            > int(subject_activity.get("resumption_count", 0))
            or lifecycle == "paused"
            or (
                str(plan.get("implementation_state", ""))
                in {"partial", "blocked", "drifted"}
                and not state["next_action"]
            )
        )
        if is_interrupted and lifecycle not in QUIET_LIFECYCLES:
            interrupted.append(
                {
                    "plan_id": plan_id,
                    "workstream_id": str(related_workstream.get("workstream_id", "")),
                    "next_action": state["next_action"],
                    "last_material_activity_at": str(subject_activity.get("last_material_activity_at", "")),
                    "reason_codes": sorted(
                        {
                            *(["unresumed_interruption"] if int(subject_activity.get("interruption_count", 0)) > int(subject_activity.get("resumption_count", 0)) else []),
                            *(["paused"] if lifecycle == "paused" else []),
                            *(["missing_next_action"] if not state["next_action"] else []),
                        }
                    ),
                    "candidate_only": True,
                }
            )
        if (
            state["next_action"]
            and lifecycle not in QUIET_LIFECYCLES
            and state["overlays"]["delivery"] != "delivered"
        ):
            next_actions.append(
                {
                    "plan_id": plan_id,
                    "workstream_id": str(related_workstream.get("workstream_id", "")),
                    "next_action": state["next_action"],
                    "blocking": state["overlays"]["blocking"],
                    "fingerprint": _digest([plan_id, state["next_action"], state["overlays"]["blocking"]]),
                }
            )

    next_actions.sort(key=lambda row: (row["blocking"] == "blocked", row["plan_id"]))
    visible_next_actions = next_actions[:3]
    task_archive: list[dict[str, Any]] = []
    worktree_close: list[dict[str, Any]] = []
    for assessment in closeout_assessments:
        common = {
            "assessment_id": str(assessment.get("assessment_id", "")),
            "plan_id": str(assessment.get("plan_id", "")),
            "plan_revision_id": str(assessment.get("plan_revision_id", "")),
            "candidate_only": True,
        }
        task_archive.append({**common, **dict(assessment.get("task_archive", {}))})
        worktree_close.append({**common, **dict(assessment.get("worktree_remove", {}))})

    for event in events:
        if event.get("event_kind") == "coverage_gap_observed":
            coverage_gaps.extend(str(value) for value in event.get("payload", {}).get("coverage_gaps", []))

    graph = {
        "nodes": sorted(nodes.values(), key=lambda row: row["node_id"]),
        "edges": sorted(edges.values(), key=lambda row: row["edge_id"]),
    }
    queues = {
        "current_state": current_state,
        "interrupted_resume": sorted(interrupted, key=lambda row: (row["plan_id"], row["workstream_id"])),
        "possible_duplicates": sorted(duplicate_queue, key=lambda row: row["queue_id"]),
        "next_actions": visible_next_actions,
        "next_actions_overflow": next_actions[3:],
        "task_archive": sorted(task_archive, key=lambda row: row["assessment_id"]),
        "worktree_close": sorted(worktree_close, key=lambda row: row["assessment_id"]),
    }
    repository_prefixes = [
        str(repository["repository_id"]) + ":" for repository in repo_views
    ]
    for repository in repo_views:
        local_ids = set(repository["node_ids"])

        def local_queue(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                row
                for row in rows
                if (
                    str(row.get("plan_id", "")) in local_ids
                    or str(row.get("workstream_id", "")) in local_ids
                    or bool(local_ids & set(row.get("candidate_ids", [])))
                )
            ]

        local_queues = {
            key: local_queue(value)
            for key, value in queues.items()
        }
        local_activity = [
            row for row in activity.values() if row["subject_id"] in local_ids
        ]
        repository_id = str(repository["repository_id"])
        cockpit_gaps = sorted(
            {
                gap
                for gap in coverage_gaps
                if not any(gap.startswith(prefix) for prefix in repository_prefixes)
                or gap.startswith(repository_id + ":")
            }
        )
        repository["cockpit"] = {
            "current_state": local_queues["current_state"],
            "activity": sorted(local_activity, key=lambda row: row["subject_id"]),
            "queues": local_queues,
            "queue_counts": {
                key: len(value) for key, value in local_queues.items()
            },
            "closeout_summary": {
                "task_ready": sum(
                    row.get("ready_for_human_decision") is True
                    for row in local_queues["task_archive"]
                ),
                "task_blocked": sum(
                    row.get("ready_for_human_decision") is not True
                    for row in local_queues["task_archive"]
                ),
                "worktree_ready": sum(
                    row.get("ready_for_human_decision") is True
                    for row in local_queues["worktree_close"]
                ),
                "worktree_blocked": sum(
                    row.get("ready_for_human_decision") is not True
                    for row in local_queues["worktree_close"]
                ),
            },
            "coverage": {
                "status": "partial" if cockpit_gaps else "complete",
                "gaps": cockpit_gaps,
            },
            "candidate_only": True,
            "execution_authorized": False,
        }
    material = {
        "repositories": repo_views,
        "graph": graph,
        "queues": queues,
        "activity": sorted(activity.values(), key=lambda row: row["subject_id"]),
        "coverage": {
            "status": "partial" if coverage_gaps else "complete",
            "gaps": sorted(set(coverage_gaps)),
            "repository_count": len(repo_views),
        },
    }
    projection = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        **material,
        "projection_fingerprint": _digest(material),
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    projection["attention_readiness"] = build_progressive_attention_readiness(
        projection,
        activation_state=activation_state,
        stage_approvals=stage_approvals,
        adapter_interface_digest=adapter_interface_digest,
        previous_weekly_fingerprints=previous_weekly_fingerprints,
    )
    return projection


def write_continuity_projection(hub_root: Path, projection: dict[str, Any]) -> dict[str, Any]:
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise RuntimeError(
            "Continuity projection writes require an initialized DAD_DATA_ROOT for this hub"
        )
    base = data_path(hub_root, "portfolio_reports") / "continuity"
    global_path = base / "global-graph.json"
    queue_path = base / "queues.json"
    atomic_write_text(global_path, json_dumps(projection, pretty=True) + "\n")
    atomic_write_text(queue_path, json_dumps(projection["queues"], pretty=True) + "\n")
    repo_outputs: list[dict[str, str]] = []
    for repository in projection["repositories"]:
        repository_id = str(repository["repository_id"])
        path = base / "repos" / f"{repository_id.replace(':', '_')}.json"
        atomic_write_text(path, json_dumps(repository, pretty=True) + "\n")
        repo_outputs.append({"repository_id": repository_id, "path": str(path)})
    return {
        "global_graph": str(global_path),
        "queues": str(queue_path),
        "repositories": repo_outputs,
        "projection_fingerprint": projection["projection_fingerprint"],
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "SCHEMA_VERSION",
    "build_continuity_projection",
    "fold_continuity_activity",
    "write_continuity_projection",
]
