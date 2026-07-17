"""Read-only reconciliation and private write gates for Intent Continuity."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from .entity_identity import fold_state as fold_entity_state
from .entity_identity import read_events as read_entity_events
from .portfolio_continuity_events import (
    continuity_ledger_path,
    read_observation_events,
)
from .portfolio_continuity_codex_hook import read_codex_hook_failures
from .portfolio_continuity_inventory import build_continuity_inventory
from .portfolio_continuity_projection import (
    build_continuity_projection,
    write_continuity_projection,
)
from .portfolio_intents import fold_plan_index, load_plan_revision
from .portfolio_intents import read_events as read_plan_events
from .portfolio_roadmap import fold_roadmap, read_roadmap_events
from .portfolio_workstreams import load_state as load_workstream_state
from .transport import resolve_data_root


AUTHORITY_BOUNDARY = (
    "Reconciliation rebuilds candidate projections from local evidence. It cannot "
    "fetch, merge identities, activate hooks, schedule, notify, mutate tasks or Git, "
    "archive work, or authorize execution."
)


class ContinuityRuntimeError(RuntimeError):
    """The continuity runtime cannot safely perform the requested operation."""


def require_initialized_private_data_root(hub_root: Path) -> Path:
    """Fail closed for new private continuity writes outside DAD_DATA_ROOT."""

    root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityRuntimeError(
            "Intent Continuity private writes require an initialized DAD_DATA_ROOT "
            "whose marker belongs to this hub"
        )
    return root


def build_current_projection(
    hub_root: Path,
    *,
    repo_roots: Iterable[Path],
    codex_metadata_by_root: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
    search_results: Iterable[dict[str, Any]] = (),
    closeout_assessments: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Rebuild one global projection without changing any source system."""

    metadata = codex_metadata_by_root or {}
    inventories = []
    for root in repo_roots:
        resolved = Path(root).resolve()
        supplied_metadata = (
            metadata[str(resolved)] if str(resolved) in metadata else None
        )
        inventories.append(
            build_continuity_inventory(
                resolved,
                codex_metadata=supplied_metadata,
            )
        )
    _private_root, private_root_mode = resolve_data_root(hub_root)
    plan_index = fold_plan_index(read_plan_events(hub_root))
    artifact_gap = False
    if private_root_mode == "data_root":
        enriched_plans: list[dict[str, Any]] = []
        for plan in plan_index["plans"]:
            try:
                artifact = load_plan_revision(
                    hub_root,
                    str(plan["plan_id"]),
                    str(plan["revision_id"]),
                )
            except (KeyError, OSError, ValueError, RuntimeError):
                artifact_gap = True
                enriched_plans.append(plan)
                continue
            card = artifact.get("semantic_card", {})
            enriched_plans.append(
                {
                    **plan,
                    "project_refs": list(card.get("project_refs", [])),
                    "workstream_refs": list(card.get("workstream_refs", [])),
                    "entity_refs": list(card.get("entity_refs", [])),
                    "source_bindings": list(card.get("source_bindings", [])),
                }
            )
        plan_index = {**plan_index, "plans": enriched_plans}
    external_gaps: list[str] = []
    if private_root_mode != "data_root":
        external_gaps.append("private_data_root_unavailable_for_current_hub")
    if artifact_gap:
        external_gaps.append("one_or_more_private_plan_artifacts_unavailable")
    continuity_events = read_observation_events(continuity_ledger_path(hub_root))
    hook_failures = read_codex_hook_failures(hub_root)
    if hook_failures:
        external_gaps.append(f"hook_failure_markers_observed:{len(hook_failures)}")
    activity_kinds = {
        str(event.get("event_kind", "")) for event in continuity_events
    }
    if not {"session_started", "session_stopped"}.issubset(activity_kinds):
        external_gaps.append("activity_duration_coverage_unknown")
    return build_continuity_projection(
        inventories=inventories,
        plan_index=plan_index,
        roadmap=fold_roadmap(read_roadmap_events(hub_root)),
        workstream_state=load_workstream_state(hub_root),
        entity_state=fold_entity_state(read_entity_events(hub_root)),
        continuity_events=continuity_events,
        search_results=search_results,
        closeout_assessments=closeout_assessments,
        external_coverage_gaps=external_gaps,
    )


def reconcile_current_projection(
    hub_root: Path,
    *,
    repo_roots: Iterable[Path],
    codex_metadata_by_root: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
    search_results: Iterable[dict[str, Any]] = (),
    closeout_assessments: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Rebuild and write derived projections only after the private-root gate."""

    require_initialized_private_data_root(hub_root)
    projection = build_current_projection(
        hub_root,
        repo_roots=repo_roots,
        codex_metadata_by_root=codex_metadata_by_root,
        search_results=search_results,
        closeout_assessments=closeout_assessments,
    )
    return {
        "schema_version": "dad.portfolio_continuity_reconciliation.v1",
        "status": "projection_rebuilt",
        "outputs": write_continuity_projection(hub_root, projection),
        "coverage": projection["coverage"],
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "ContinuityRuntimeError",
    "build_current_projection",
    "reconcile_current_projection",
    "require_initialized_private_data_root",
]
