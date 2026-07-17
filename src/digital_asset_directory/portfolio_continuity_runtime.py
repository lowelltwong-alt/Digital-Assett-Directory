"""Read-only reconciliation and private write gates for Intent Continuity."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .entity_identity import fold_state as fold_entity_state
from .entity_identity import read_events as read_entity_events
from .portfolio_continuity_events import (
    continuity_ledger_path,
    read_observation_events,
)
from .portfolio_continuity_codex_hook import read_codex_hook_failures
from .portfolio_continuity_inventory import build_continuity_inventory
from .portfolio_continuity_host_readiness import (
    host_readiness_binding_failures,
    host_readiness_recording_failures,
    latest_host_readiness_assessment,
)
from .portfolio_continuity_projection import (
    build_continuity_projection,
    write_continuity_projection,
)
from .portfolio_continuity_workflow import assess_closeout, project_continuity_state
from .portfolio_continuity_stage_activation import read_stage_approvals
from .portfolio_continuity_trial import evaluate_trial, read_trial_reviews
from .portfolio_intents import fold_plan_index, load_plan_revision
from .portfolio_intents import read_events as read_plan_events
from .portfolio_relations import RelationTarget, classify_relations
from .portfolio_roadmap import fold_roadmap, read_roadmap_events
from .portfolio_workstreams import load_state as load_workstream_state
from .transport import data_path, resolve_data_root


AUTHORITY_BOUNDARY = (
    "Reconciliation rebuilds candidate projections from local evidence. It cannot "
    "fetch, merge identities, activate hooks, schedule, notify, mutate tasks or Git, "
    "archive work, or authorize execution."
)
MAX_AUTOMATIC_DUPLICATE_PLANS = 250
ADAPTER_ARTIFACT_ID = "adapter:intent-continuity-codex-host"


class ContinuityRuntimeError(RuntimeError):
    """The continuity runtime cannot safely perform the requested operation."""


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _plan_text(plan: Mapping[str, Any]) -> str:
    return " ".join(
        [
            str(plan.get("title", "")),
            *[str(value) for value in plan.get("aliases", [])],
            str(plan.get("outcome", "")),
        ]
    )


def _plan_identity_tokens(plan: Mapping[str, Any]) -> frozenset[str]:
    """Keep numbers and generic words for conservative automatic identity checks."""

    return frozenset(re.findall(r"[a-z0-9]+", _plan_text(plan).casefold()))


def derive_plan_duplicate_search_results(
    plans: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build conservative duplicate pairs from current private plan revisions.

    The existing deterministic relation classifier owns the duplicate threshold.
    This helper supplies the previously missing live queue input; it never merges
    plans or selects a primary identity.
    """

    rows = sorted(plans, key=lambda row: str(row.get("plan_id", "")))
    gaps: list[str] = []
    if len(rows) > MAX_AUTOMATIC_DUPLICATE_PLANS:
        rows = rows[:MAX_AUTOMATIC_DUPLICATE_PLANS]
        gaps.append("automatic_plan_duplicate_scan_truncated")
    results: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        source_id = str(source.get("plan_id", ""))
        if not source_id:
            continue
        source_identity = _plan_identity_tokens(source)
        for target in rows[index + 1 :]:
            target_id = str(target.get("plan_id", ""))
            if not target_id:
                continue
            if (
                len(source_identity) < 4
                or source_identity != _plan_identity_tokens(target)
            ):
                continue
            relations, _coverage = classify_relations(
                source_id,
                _plan_text(source),
                [
                    RelationTarget(
                        target_kind="plan",
                        target_id=target_id,
                        target_label=str(target.get("title", "")) or target_id,
                        text=_plan_text(target),
                        mature=str(target.get("implementation_state", ""))
                        not in {"", "unstarted"},
                    )
                ],
                limit=1,
            )
            if not relations or relations[0]["relationship_type"] != "duplicate":
                continue
            relation = relations[0]
            material = {
                "source_plan_id": source_id,
                "target_plan_id": target_id,
                "relation_id": relation["relation_id"],
            }
            results.append(
                {
                    "query_digest": _digest(material),
                    "classification": "possible_duplicate_pair",
                    "primary_candidate_id": "",
                    "candidates": [
                        {"candidate_id": source_id},
                        {"candidate_id": target_id},
                    ],
                    "relation_evidence": {
                        "relation_id": relation["relation_id"],
                        "confidence": relation["confidence"],
                        "score": relation["score"],
                    },
                    "candidate_only": True,
                    "execution_authorized": False,
                }
            )
    return results, gaps


def derive_closeout_assessments(
    plans: Iterable[dict[str, Any]],
    workstream_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Assess terminal plans from current evidence without performing cleanup."""

    workstreams = {
        str(row.get("workstream_id", "")): row
        for row in workstream_state.get("workstreams", [])
    }
    assessments: list[dict[str, Any]] = []
    for plan in plans:
        workstream = next(
            (
                workstreams[ref]
                for ref in plan.get("workstream_refs", [])
                if ref in workstreams
            ),
            None,
        )
        state = project_continuity_state(plan=plan, workstream=workstream)
        terminal = (
            state["overlays"]["delivery"] == "delivered"
            or str(plan.get("lifecycle", "")) in {"superseded", "withdrawn"}
        )
        if not terminal:
            continue
        try:
            assessed_at = datetime.fromisoformat(
                str(plan.get("recorded_at", "")).replace("Z", "+00:00")
            )
            if assessed_at.tzinfo is None:
                raise ValueError("naive plan observation time")
            assessed_at = assessed_at.astimezone(timezone.utc)
        except ValueError:
            assessed_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
        assessment = assess_closeout(
            plan=plan,
            workstream=workstream,
            now=assessed_at,
        )
        assessment["assessment_mode"] = "automatic_current_evidence_candidate"
        assessments.append(assessment)
    return assessments


def read_previous_weekly_fingerprints(
    hub_root: Path,
) -> tuple[list[str], list[str]]:
    """Read only prior derived asks; missing/corrupt history disables suppression."""

    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        return [], ["weekly_changed_only_history_unavailable"]
    path = data_path(hub_root, "portfolio_reports") / "continuity" / "global-graph.json"
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
        attention = prior["attention_readiness"]
        fingerprints = attention.get("weekly_seen_fingerprints")
        if fingerprints is None:
            asks = attention["weekly_digest_preview"]["asks"]
            fingerprints = [
                str(row["fingerprint"])
                for row in asks
                if isinstance(row, dict) and str(row.get("fingerprint", ""))
            ]
        if not isinstance(fingerprints, list):
            raise TypeError("weekly fingerprint history is not a list")
        if any(
            not isinstance(value, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
            for value in fingerprints
        ):
            raise ValueError("weekly fingerprint history contains an invalid digest")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return [], ["weekly_changed_only_history_unavailable"]
    return sorted(set(fingerprints)), []


def require_initialized_private_data_root(hub_root: Path) -> Path:
    """Fail closed for new private continuity writes outside DAD_DATA_ROOT."""

    root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityRuntimeError(
            "Intent Continuity private writes require an initialized DAD_DATA_ROOT "
            "whose marker belongs to this hub"
        )
    return root


def derive_attention_stage_context(
    hub_root: Path, repository_roots: Iterable[Path]
) -> tuple[
    dict[str, Any] | None,
    list[dict[str, Any]] | None,
    str,
    list[str],
]:
    """Resolve the active trial and raw approval ledger for the live projection."""

    reviews = read_trial_reviews(hub_root)
    approvals = read_stage_approvals(hub_root)
    non_fixture_approvals = [row for row in approvals if row["fixture_only"] is False]
    non_fixture_reviews = [row for row in reviews if row["fixture_only"] is False]
    if non_fixture_approvals:
        trial_id = str(non_fixture_approvals[-1]["trial_id"])
    elif non_fixture_reviews:
        trial_id = str(non_fixture_reviews[-1]["trial_id"])
    else:
        return None, None, "", []

    host_root = next(
        (
            Path(root).resolve()
            for root in repository_roots
            if (Path(root).resolve() / ".codex/hooks.json").is_file()
            and (
                Path(root).resolve()
                / "registry/portable-capability-registry.json"
            ).is_file()
        ),
        None,
    )
    if host_root is None:
        return None, None, "", ["attention_host_adapter_repository_unavailable"]

    host_assessment = latest_host_readiness_assessment(host_root, hub_root)
    binding_failures = (
        [
            *host_readiness_binding_failures(host_root, host_assessment),
            *host_readiness_recording_failures(
                host_root, hub_root, host_assessment
            ),
        ]
        if host_assessment is not None
        else []
    )
    activation = evaluate_trial(
        reviews,
        trial_id=trial_id,
        host_readiness=host_assessment,
        host_binding_failures=binding_failures,
    )
    from .portability_control import runtime_adapter_interface_digest

    adapter_digest = runtime_adapter_interface_digest(host_root, ADAPTER_ARTIFACT_ID)
    return activation, approvals, adapter_digest, []


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
    resolved_roots = [Path(root).resolve() for root in repo_roots]
    inventories = []
    for resolved in resolved_roots:
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
    previous_weekly_fingerprints, weekly_history_gaps = read_previous_weekly_fingerprints(
        hub_root
    )
    external_gaps.extend(weekly_history_gaps)
    activation_state: dict[str, Any] | None = None
    stage_approvals: list[dict[str, Any]] | None = None
    adapter_interface_digest = ""
    if private_root_mode == "data_root":
        (
            activation_state,
            stage_approvals,
            adapter_interface_digest,
            attention_gaps,
        ) = derive_attention_stage_context(hub_root, resolved_roots)
        external_gaps.extend(attention_gaps)
    supplied_search_results = list(search_results)
    supplied_closeout_assessments = list(closeout_assessments)
    workstream_state = load_workstream_state(hub_root)
    automatic_search_results, duplicate_gaps = derive_plan_duplicate_search_results(
        plan_index["plans"]
    )
    automatic_closeout_assessments = derive_closeout_assessments(
        plan_index["plans"], workstream_state
    )
    supplied_closeout_plan_ids = {
        str(row.get("plan_id", "")) for row in supplied_closeout_assessments
    }
    automatic_closeout_assessments = [
        row
        for row in automatic_closeout_assessments
        if str(row.get("plan_id", "")) not in supplied_closeout_plan_ids
    ]
    external_gaps.extend(duplicate_gaps)
    return build_continuity_projection(
        inventories=inventories,
        plan_index=plan_index,
        roadmap=fold_roadmap(read_roadmap_events(hub_root)),
        workstream_state=workstream_state,
        entity_state=fold_entity_state(read_entity_events(hub_root)),
        continuity_events=continuity_events,
        search_results=[*automatic_search_results, *supplied_search_results],
        closeout_assessments=[
            *automatic_closeout_assessments,
            *supplied_closeout_assessments,
        ],
        external_coverage_gaps=external_gaps,
        activation_state=activation_state,
        stage_approvals=stage_approvals,
        adapter_interface_digest=adapter_interface_digest,
        previous_weekly_fingerprints=previous_weekly_fingerprints,
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
    "derive_closeout_assessments",
    "derive_attention_stage_context",
    "derive_plan_duplicate_search_results",
    "read_previous_weekly_fingerprints",
    "build_current_projection",
    "reconcile_current_projection",
    "require_initialized_private_data_root",
]
