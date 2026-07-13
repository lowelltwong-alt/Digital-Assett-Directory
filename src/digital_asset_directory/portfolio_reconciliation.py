"""Proposal-only reconciliation for Portfolio OS identities.

This pure projection consumes the strict Portfolio Cockpit snapshot. It never
scans Git, appends ledger events, mutates repositories, or promotes a binding.
Similarity is inspect-only evidence; exact proposals require an existing exact
assertion or unique structural branch/worktree evidence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import base64
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .ids import stable_id
from .portfolio_cockpit import SCHEMA_VERSION as COCKPIT_SCHEMA_VERSION
from .portfolio_cockpit import _schema_validation_problems
from .portfolio_relations import RelationTarget, classify_relations, idea_tokens
from .transport import data_path
from .utils import atomic_write_text, json_dumps


SCHEMA_VERSION = "dad.portfolio_reconciliation.v1"
METHOD_ID = "dad.portfolio-reconciliation-selection.v1"
METHODOLOGY_REF = "docs/frontier/collaboration/12_PORTFOLIO_BINDING_ASSISTANCE.md"
TERMINAL_STATES = frozenset({"merged", "superseded", "archived"})
QUIET_STATES = frozenset({"paused", "snoozed", "incubating"})
DEFAULT_BRANCHES = frozenset({"main", "master", "trunk", "develop", "development"})

AUTHORITY_BOUNDARY = (
    "This is a local, snapshot-bound candidate projection. It cannot append ledger "
    "events, accept bindings, create workstreams, branches, or worktrees, dispatch "
    "agents, notify people, or mutate any source repository."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconciliationSettings:
    """Bounded display policy for candidate reconciliation."""

    candidate_limit: int = 3
    review_limit: int = 3
    fresh_after_hours: int = 26
    future_tolerance_hours: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.candidate_limit <= 10:
            raise ValueError("candidate_limit must be between 1 and 10")
        if not 1 <= self.review_limit <= 3:
            raise ValueError("review_limit must be between 1 and 3")
        if self.fresh_after_hours < 1:
            raise ValueError("fresh_after_hours must be at least 1")
        if self.future_tolerance_hours < 0:
            raise ValueError("future_tolerance_hours cannot be negative")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


_TOP_LEVEL_SET_COLLECTIONS = frozenset(
    {"resources", "workstreams", "bindings", "projects", "coverage", "unknowns"}
)
_NESTED_SET_COLLECTIONS = frozenset(
    {
        "accepted_resource_ids",
        "accepted_workstream_ids",
        "attention_ids",
        "blocks_directly",
        "branch_resource_ids",
        "candidate_proposal_ids",
        "linked_resource_ids",
        "proposed_resource_refs",
        "problems",
        "reasons",
        "related_projects",
        "shared_metadata_tokens",
        "resource_ids",
        "suppressed_reasons",
        "worktree_resource_ids",
    }
)


def _canonicalize_cockpit_value(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize_cockpit_value(child, (*path, str(key)))
            for key, child in value.items()
        }
    if not isinstance(value, list):
        return value
    rows = [_canonicalize_cockpit_value(child, path) for child in value]
    top_level_set = len(path) == 1 and path[0] in _TOP_LEVEL_SET_COLLECTIONS
    nested_set = bool(path) and path[-1] in _NESTED_SET_COLLECTIONS
    if top_level_set or nested_set:
        rows.sort(
            key=lambda child: json.dumps(
                child,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            )
        )
    return rows


def _cockpit_hash(cockpit: dict[str, Any]) -> str:
    """Fingerprint set-like cockpit evidence without erasing queue order."""

    return _canonical_hash(_canonicalize_cockpit_value(cockpit))


def cockpit_projection_hash(cockpit: dict[str, Any]) -> str:
    """Return the queue-aware canonical hash used by dependent projections."""

    return _cockpit_hash(cockpit)


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_descriptor(
    cockpit: Any,
    schema_root: Path,
    *,
    now: datetime,
    fresh_after_hours: int,
    future_tolerance_hours: int,
) -> dict[str, Any]:
    if not isinstance(cockpit, dict):
        return {
            "status": "invalid",
            "freshness": "unknown",
            "schema_version": "",
            "generated_at": "",
            "source_hash": _canonical_hash(cockpit),
            "problems": ["cockpit_not_object"],
        }
    structural_problems: list[str] = []
    freshness_problems: list[str] = []
    schema_version = str(cockpit.get("schema_version", ""))
    if schema_version != COCKPIT_SCHEMA_VERSION:
        structural_problems.append(f"unexpected_schema:{schema_version or 'missing'}")
    structural_problems.extend(
        _schema_validation_problems(cockpit, schema_root, "portfolio_cockpit")
    )
    nested_sources = cockpit.get("sources", {})
    if not isinstance(nested_sources, dict) or not nested_sources:
        structural_problems.append("nested_sources_missing")
    else:
        for name, source in sorted(nested_sources.items()):
            if not isinstance(source, dict) or source.get("status") != "observed":
                structural_problems.append(f"nested_source_invalid:{name}")
            elif source.get("freshness") != "current":
                freshness_problems.append(f"nested_source_not_current:{name}")
    generated_at = str(cockpit.get("generated_at", ""))
    generated = _parse_datetime(generated_at)
    if generated is None:
        freshness = "unknown"
        freshness_problems.append("generated_at_invalid_or_missing")
    else:
        age_hours = (now - generated).total_seconds() / 3600
        if age_hours < -future_tolerance_hours:
            freshness = "future"
            freshness_problems.append("generated_at_in_future")
        elif age_hours > fresh_after_hours:
            freshness = "stale"
            freshness_problems.append("source_stale")
        elif freshness_problems:
            freshness = "unknown"
        else:
            freshness = "current"
    return {
        "status": "invalid" if structural_problems else "observed",
        "freshness": freshness,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "source_hash": _cockpit_hash(cockpit),
        "problems": sorted(set([*structural_problems, *freshness_problems])),
    }


def _duplicate_ids(rows: list[dict[str, Any]], key: str) -> set[str]:
    counts = Counter(str(row.get(key, "")) for row in rows)
    return {value for value, count in counts.items() if value and count > 1}


def _attention_identity_resource_ids(
    item: dict[str, Any], resources: dict[str, dict[str, Any]]
) -> tuple[str, ...]:
    """Return the most-specific exact identity scope for one attention item."""

    known = sorted(
        {
            str(resource_id)
            for resource_id in item.get("resource_ids", [])
            if str(resource_id) in resources
        }
    )
    specific = [
        resource_id
        for resource_id in known
        if resources[resource_id]["resource_kind"] in {"branch", "worktree"}
    ]
    return tuple(specific or known)


def _sanitized_unknown(row: dict[str, Any]) -> dict[str, str]:
    """Preserve categorical cockpit evidence without copying local paths or notes."""

    def safe_category(value: Any, fallback: str) -> str:
        candidate = str(value or "").strip().lower()
        if not candidate or len(candidate) > 64:
            return fallback
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", candidate):
            return fallback
        return candidate

    raw_source = str(row.get("source", "cockpit"))
    raw_kind = str(row.get("kind", "unknown_evidence"))
    source = safe_category(raw_source, "cockpit")
    kind = safe_category(raw_kind, "unknown_evidence")
    severity = str(row.get("severity", "warning"))
    if severity not in {"info", "warning", "danger"}:
        severity = "warning"
    opaque_ref = stable_id(
        "portfolio-reconciliation-unknown",
        raw_source,
        raw_kind,
        str(row.get("ref", "")),
    )
    return {
        "source": source,
        "kind": kind,
        "ref": opaque_ref,
        "note": (
            f"Cockpit reported categorical evidence gap '{kind}'. "
            "Inspect the local cockpit for source-specific detail."
        ),
        "severity": severity,
    }


def _relation(workstream: dict[str, Any], resource: dict[str, Any]) -> dict[str, Any] | None:
    target = RelationTarget(
        target_kind=(
            "portfolio_project" if resource["resource_kind"] == "repo" else "portfolio_branch"
        ),
        target_id=str(resource["resource_id"]),
        target_label=str(resource["label"]),
        text=f"{resource['project_name']} {resource['label']}",
        mature=True,
    )
    rows, _coverage = classify_relations(
        str(workstream["workstream_id"]), str(workstream["label"]), [target], limit=1
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "relationship_type": str(row["relationship_type"]),
        "score": float(row["score"]),
        "shared_tokens": sorted(str(value) for value in row["shared_tokens"]),
        "reason": str(row["reason"]),
    }


def _candidate(
    workstream: dict[str, Any],
    resource: dict[str, Any],
    *,
    evidence_tier: str,
    disposition: str,
    signals: list[str],
    counterevidence: list[str],
    relation: dict[str, Any] | None = None,
    evidence_details: dict[str, Any] | None = None,
    command_ready: bool = False,
) -> dict[str, Any]:
    proposal_id = stable_id(
        METHOD_ID, str(workstream["workstream_id"]), str(resource["resource_id"])
    )
    details = {
        "binding_id": "",
        "binding_ids": [],
        "binding_resolution": "",
        "structural_anchor_resource_id": "",
        "structural_anchor_resource_ids": [],
        "shared_tokens": [],
        "target_label_hash": _canonical_hash(str(resource["label"])),
        **(evidence_details or {}),
    }
    details["shared_tokens"] = sorted(set(str(value) for value in details.get("shared_tokens", [])))
    normalized_relation = relation or {
        "relationship_type": "",
        "score": None,
        "shared_tokens": [],
        "reason": "",
    }
    material = {
        "evidence_tier": evidence_tier,
        "disposition": disposition,
        "signals": sorted(set(signals)),
        "counterevidence": sorted(set(counterevidence)),
        "relation": normalized_relation,
        "evidence_details": details,
    }
    command = None
    if command_ready:
        command = {
            "command": "asset-dir",
            "args": [
                "os",
                "bind",
                str(workstream["workstream_id"]),
                str(resource["resource_kind"]),
                str(resource["resource_id"]),
                "--label",
                str(resource["label"]),
                "--request-id",
                proposal_id,
            ],
        }
    return {
        "proposal_id": proposal_id,
        "revision_id": stable_id(proposal_id, _canonical_hash(material)),
        "workstream_id": str(workstream["workstream_id"]),
        "workstream_label": str(workstream["label"]),
        "resource_id": str(resource["resource_id"]),
        "resource_kind": str(resource["resource_kind"]),
        "resource_label": str(resource["label"]),
        "project_id": str(resource["project_id"]),
        "project_name": str(resource["project_name"]),
        "evidence_tier": evidence_tier,
        "disposition": disposition,
        "signals": material["signals"],
        "counterevidence": material["counterevidence"],
        "evidence_details": details,
        "relation": normalized_relation,
        "proposal_command": command,
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    tier = {"E0_existing_exact": 0, "E1_unique_structural": 1, "I0_inspect_only": 2}
    disposition = {
        "review_existing": 0,
        "proposal_ready": 1,
        "proposal_available": 2,
        "ambiguous": 3,
        "inspect_only": 4,
        "conflict": 5,
    }
    score = row["relation"].get("score")
    return (
        tier.get(row["evidence_tier"], 99),
        disposition.get(row["disposition"], 99),
        -(float(score) if isinstance(score, (int, float)) else -1.0),
        row["proposal_id"],
    )


def _workstream_candidates(
    workstream: dict[str, Any],
    *,
    resources: dict[str, dict[str, Any]],
    bindings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    workstream_id = str(workstream["workstream_id"])
    accepted = set(str(value) for value in workstream.get("accepted_resource_ids", []))
    rows: list[dict[str, Any]] = []

    proposed_by_resource: dict[str, list[str]] = {}
    for binding in bindings:
        resource_id = str(binding.get("resource_id", ""))
        if (
            binding.get("workstream_id") != workstream_id
            or binding.get("resolution") != "proposed_exact"
            or resource_id not in resources
        ):
            continue
        proposed_by_resource.setdefault(resource_id, []).append(str(binding.get("binding_id", "")))
    for resource_id, raw_binding_ids in sorted(proposed_by_resource.items()):
        resource = resources[resource_id]
        binding_ids = sorted(set(raw_binding_ids))
        owners = set(str(value) for value in resource.get("accepted_workstream_ids", []))
        conflict = bool(owners - {workstream_id})
        rows.append(
            _candidate(
                workstream,
                resource,
                evidence_tier="E0_existing_exact",
                disposition="conflict" if conflict else "review_existing",
                signals=[
                    "existing_exact_proposed_binding",
                    *(["multiple_existing_exact_proposals"] if len(binding_ids) > 1 else []),
                ],
                counterevidence=(["resource_accepted_by_another_workstream"] if conflict else []),
                evidence_details={
                    "binding_id": binding_ids[0],
                    "binding_ids": binding_ids,
                    "binding_resolution": "proposed_exact",
                },
            )
        )

    e0_resource_ids = set(proposed_by_resource)
    structural_anchors: dict[str, set[str]] = {}
    structural_shared: dict[str, set[str]] = {}
    for accepted_id in sorted(accepted):
        source = resources.get(accepted_id)
        if not source or source["resource_kind"] not in {"branch", "worktree"}:
            continue
        expected_kind = "worktree" if source["resource_kind"] == "branch" else "branch"
        raw_link_ids = [str(resource_id) for resource_id in source.get("linked_resource_ids", [])]
        if len(raw_link_ids) != 1:
            continue
        target_id = raw_link_ids[0]
        target = resources.get(target_id)
        if (
            target is None
            or target_id in accepted
            or target["resource_kind"] != expected_kind
            or target["project_id"] != source["project_id"]
            or [str(resource_id) for resource_id in target.get("linked_resource_ids", [])]
            != [accepted_id]
        ):
            continue
        target_id = str(target["resource_id"])
        if target_id in e0_resource_ids:
            continue
        shared = idea_tokens(str(workstream["label"])) & idea_tokens(str(target["label"]))
        if not shared or str(target["label"]).casefold() in DEFAULT_BRANCHES:
            continue
        structural_anchors.setdefault(target_id, set()).add(accepted_id)
        structural_shared.setdefault(target_id, set()).update(shared)
    for target_id, anchor_ids in sorted(structural_anchors.items()):
        target = resources[target_id]
        anchors = sorted(anchor_ids)
        owners = set(str(value) for value in target.get("accepted_workstream_ids", []))
        conflict = bool(owners - {workstream_id})
        rows.append(
            _candidate(
                workstream,
                target,
                evidence_tier="E1_unique_structural",
                disposition="conflict" if conflict else "proposal_ready",
                signals=["unique_exact_branch_worktree_link", "discriminating_token_overlap"],
                counterevidence=(["resource_accepted_by_another_workstream"] if conflict else []),
                evidence_details={
                    "structural_anchor_resource_id": anchors[0],
                    "structural_anchor_resource_ids": anchors,
                    "shared_tokens": sorted(structural_shared[target_id]),
                },
                command_ready=not conflict,
            )
        )
    existing_ids = {row["resource_id"] for row in rows}
    for resource in resources.values():
        resource_id = str(resource["resource_id"])
        if resource_id in accepted or resource_id in existing_ids:
            continue
        relation = _relation(workstream, resource)
        if relation is None:
            continue
        owners = set(str(value) for value in resource.get("accepted_workstream_ids", []))
        conflict = bool(owners - {workstream_id})
        rows.append(
            _candidate(
                workstream,
                resource,
                evidence_tier="I0_inspect_only",
                disposition="conflict" if conflict else "inspect_only",
                signals=["lexical_relation_candidate"],
                counterevidence=[
                    "similarity_is_not_identity",
                    *(["resource_accepted_by_another_workstream"] if conflict else []),
                ],
                relation=relation,
                evidence_details={"shared_tokens": relation["shared_tokens"]},
            )
        )
    unique: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=_candidate_sort_key):
        unique.setdefault(str(row["proposal_id"]), row)
    return list(unique.values())


def _mark_ambiguities(rows: list[dict[str, Any]]) -> None:
    """Fail closed when equally strong exact proposals compete."""

    exact = [
        row
        for row in rows
        if row["evidence_tier"] in {"E0_existing_exact", "E1_unique_structural"}
        and row["disposition"] != "conflict"
    ]
    tier_rank = {"E0_existing_exact": 0, "E1_unique_structural": 1}
    ambiguous: dict[str, set[str]] = {}
    by_workstream: dict[str, list[dict[str, Any]]] = {}
    for row in exact:
        by_workstream.setdefault(str(row["workstream_id"]), []).append(row)
    for group in by_workstream.values():
        best = min(tier_rank[row["evidence_tier"]] for row in group)
        winners = [row for row in group if tier_rank[row["evidence_tier"]] == best]
        if len(winners) > 1:
            for row in winners:
                ambiguous.setdefault(row["proposal_id"], set()).add("multiple_equal_best_resources")

    by_resource: dict[str, list[dict[str, Any]]] = {}
    for row in exact:
        by_resource.setdefault(str(row["resource_id"]), []).append(row)
    for group in by_resource.values():
        if len({str(row["workstream_id"]) for row in group}) <= 1:
            continue
        for row in group:
            ambiguous.setdefault(row["proposal_id"], set()).add(
                "multiple_exact_workstreams_for_resource"
            )
    for row in rows:
        reasons = ambiguous.get(row["proposal_id"])
        if not reasons:
            continue
        row["disposition"] = "ambiguous"
        row["proposal_command"] = None
        row["counterevidence"] = sorted(
            set(row["counterevidence"]) | reasons | {"human_identity_decision_required"}
        )
        material = {
            "evidence_tier": row["evidence_tier"],
            "disposition": row["disposition"],
            "signals": row["signals"],
            "counterevidence": row["counterevidence"],
            "relation": row["relation"],
            "evidence_details": row["evidence_details"],
        }
        row["revision_id"] = stable_id(row["proposal_id"], _canonical_hash(material))


def build_portfolio_reconciliation(
    cockpit: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    settings: ReconciliationSettings | None = None,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic, non-mutating reconciliation projection."""

    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    policy = settings or ReconciliationSettings()
    source = _source_descriptor(
        cockpit,
        schema_root or Path(__file__).parents[2],
        now=observed,
        fresh_after_hours=policy.fresh_after_hours,
        future_tolerance_hours=policy.future_tolerance_hours,
    )
    source_ready = source["status"] == "observed" and source["freshness"] == "current"
    value = cockpit if isinstance(cockpit, dict) else {}
    source_resources = [row for row in value.get("resources", []) if isinstance(row, dict)]
    source_workstreams = [row for row in value.get("workstreams", []) if isinstance(row, dict)]
    duplicate_resources = _duplicate_ids(source_resources, "resource_id")
    duplicate_workstreams = _duplicate_ids(source_workstreams, "workstream_id")
    resource_rows = [
        row
        for row in source_resources
        if str(row.get("resource_id", "")) not in duplicate_resources
    ]
    workstreams = [
        row
        for row in source_workstreams
        if str(row.get("workstream_id", "")) not in duplicate_workstreams
    ]
    resources = {str(row["resource_id"]): row for row in resource_rows}
    bindings = [row for row in value.get("bindings", []) if isinstance(row, dict)]
    workstream_by_id = {str(workstream["workstream_id"]): workstream for workstream in workstreams}
    unknowns = sorted(
        (_sanitized_unknown(row) for row in value.get("unknowns", []) if isinstance(row, dict)),
        key=lambda row: (
            row["source"],
            row["kind"],
            row["ref"],
            row["severity"],
        ),
    )
    blockers: list[dict[str, str]] = []
    if not source_ready:
        blockers.append(
            {
                "kind": "source_not_ready",
                "ref": "cockpit",
                "note": "The cockpit or a nested source is invalid, stale, or unknown.",
            }
        )
    blockers.extend(
        {
            "kind": "duplicate_resource_id",
            "ref": stable_id(
                "portfolio-reconciliation-problem", "duplicate_resource_id", resource_id
            ),
            "note": "Duplicate exact resource identity was quarantined.",
        }
        for resource_id in sorted(duplicate_resources)
    )
    blockers.extend(
        {
            "kind": "duplicate_workstream_id",
            "ref": stable_id(
                "portfolio-reconciliation-problem",
                "duplicate_workstream_id",
                workstream_id,
            ),
            "note": "Duplicate workstream identity was quarantined.",
        }
        for workstream_id in sorted(duplicate_workstreams)
    )
    valid_bindings: list[dict[str, Any]] = []
    for binding in bindings:
        resolution = str(binding.get("resolution", ""))
        assertion_status = str(binding.get("assertion_status", ""))
        workstream_id = str(binding.get("workstream_id", ""))
        resource_id = str(binding.get("resource_id", ""))
        ref = str(binding.get("ref", ""))
        binding_kind = str(binding.get("binding_kind", ""))
        exact = resolution.endswith("_exact")
        expected_status = resolution.removesuffix("_exact").removesuffix("_unresolved")
        resource = resources.get(resource_id) if resource_id else None
        semantic_valid = (
            workstream_id in workstream_by_id
            and assertion_status == expected_status
            and (
                exact
                and bool(resource_id)
                and ref == resource_id
                and resource is not None
                and binding_kind == resource.get("resource_kind")
                or not exact
                and not resource_id
            )
        )
        if not semantic_valid:
            blockers.append(
                {
                    "kind": "binding_semantic_mismatch",
                    "ref": stable_id(
                        "portfolio-reconciliation-binding-problem",
                        str(binding.get("binding_id", "")),
                    ),
                    "note": (
                        "A cockpit binding contradicts its status, resolution, exact "
                        "resource identity, resource kind, or workstream identity."
                    ),
                }
            )
            continue
        valid_bindings.append(binding)
        if resolution == "accepted_unresolved":
            blockers.append(
                {
                    "kind": "accepted_binding_unresolved",
                    "ref": stable_id(
                        "portfolio-reconciliation-binding-problem",
                        str(binding.get("binding_id", "")),
                    ),
                    "note": "An accepted binding does not resolve to one exact resource.",
                }
            )

    accepted_pairs = {
        (str(binding.get("workstream_id", "")), str(binding.get("resource_id", "")))
        for binding in valid_bindings
        if binding.get("resolution") == "accepted_exact"
    }

    ownership_problem_keys: set[tuple[str, str, str]] = set()

    def add_ownership_blocker(kind: str, workstream_id: str, resource_id: str) -> None:
        key = (kind, workstream_id, resource_id)
        if key in ownership_problem_keys:
            return
        ownership_problem_keys.add(key)
        blockers.append(
            {
                "kind": kind,
                "ref": stable_id(
                    "portfolio-reconciliation-ownership-gap",
                    workstream_id,
                    resource_id,
                ),
                "note": (
                    "Accepted ownership is missing an exact, bidirectional cockpit "
                    "resource/workstream assertion."
                ),
            }
        )

    for workstream_id, workstream in sorted(workstream_by_id.items()):
        for resource_id in sorted(
            set(str(value) for value in workstream.get("accepted_resource_ids", []))
        ):
            resource = resources.get(resource_id)
            if resource is None:
                add_ownership_blocker("accepted_resource_missing", workstream_id, resource_id)
                continue
            owners = set(str(value) for value in resource.get("accepted_workstream_ids", []))
            if workstream_id not in owners or (workstream_id, resource_id) not in accepted_pairs:
                add_ownership_blocker(
                    "accepted_ownership_not_bidirectional", workstream_id, resource_id
                )

    for resource_id, resource in sorted(resources.items()):
        owners = sorted(set(str(value) for value in resource.get("accepted_workstream_ids", [])))
        if len(owners) > 1:
            blockers.append(
                {
                    "kind": "multiple_accepted_workstream_owners",
                    "ref": stable_id(
                        "portfolio-reconciliation-problem",
                        "multiple_accepted_workstream_owners",
                        resource_id,
                    ),
                    "note": (
                        "One exact resource has more than one accepted workstream owner; "
                        "identity reconciliation is blocked."
                    ),
                }
            )
        for workstream_id in owners:
            workstream = workstream_by_id.get(workstream_id)
            if workstream is None:
                add_ownership_blocker(
                    "accepted_owner_workstream_missing", workstream_id, resource_id
                )
                continue
            workstream_resources = set(
                str(value) for value in workstream.get("accepted_resource_ids", [])
            )
            if (
                resource_id not in workstream_resources
                or (
                    workstream_id,
                    resource_id,
                )
                not in accepted_pairs
            ):
                add_ownership_blocker(
                    "accepted_ownership_not_bidirectional", workstream_id, resource_id
                )

    attention_items = [item for item in value.get("attention_queue", []) if isinstance(item, dict)]
    today = [row for row in value.get("today", []) if isinstance(row, dict)]
    attention_problem_keys: set[tuple[str, str]] = set()

    def add_attention_blocker(kind: str, item: dict[str, Any]) -> None:
        attention_id = str(item.get("attention_id", ""))
        key = (kind, attention_id)
        if key in attention_problem_keys:
            return
        attention_problem_keys.add(key)
        blockers.append(
            {
                "kind": kind,
                "ref": stable_id("portfolio-reconciliation-attention-problem", kind, attention_id),
                "note": (
                    "An attention assignment does not resolve to the exact cockpit "
                    "workstream/resource ownership projection."
                ),
            }
        )

    queue_ids = {str(item.get("attention_id", "")) for item in attention_items}
    for collection_name, items in (
        ("attention_queue", attention_items),
        ("today", today),
    ):
        for item in items:
            attention_id = str(item.get("attention_id", ""))
            if collection_name == "today" and attention_id not in queue_ids:
                add_attention_blocker("today_item_not_in_attention_queue", item)
            workstream_id = str(item.get("workstream_id", ""))
            resource_ids = {str(resource_id) for resource_id in item.get("resource_ids", [])}
            known_resource_ids = {
                resource_id for resource_id in resource_ids if resource_id in resources
            }
            if any(resource_id not in resources for resource_id in resource_ids):
                add_attention_blocker("attention_resource_missing", item)
            if not known_resource_ids and item.get("source") != "system":
                add_attention_blocker("attention_scope_missing", item)
            if not workstream_id:
                continue
            if workstream_id not in workstream_by_id:
                add_attention_blocker("attention_workstream_missing", item)
                continue
    quiet_workstreams = [
        row for row in workstreams if str(row.get("lifecycle_state", "")) in QUIET_STATES
    ]
    eligible = [
        row
        for row in workstreams
        if str(row.get("lifecycle_state", "")) not in TERMINAL_STATES | QUIET_STATES
    ]
    candidates: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    complete_candidates: list[dict[str, Any]] = []
    bounded_review_ids: list[str] = []
    if source_ready:
        available_by_workstream: dict[str, list[dict[str, Any]]] = {}
        for workstream in sorted(eligible, key=lambda row: str(row["workstream_id"])):
            workstream_id = str(workstream["workstream_id"])
            available_by_workstream[workstream_id] = _workstream_candidates(
                workstream, resources=resources, bindings=valid_bindings
            )
        complete_candidates = [
            candidate for rows in available_by_workstream.values() for candidate in rows
        ]
        _mark_ambiguities(complete_candidates)
        if blockers or unknowns:
            for candidate in complete_candidates:
                if candidate["proposal_command"] is None:
                    continue
                candidate["disposition"] = "conflict"
                candidate["proposal_command"] = None
                candidate["counterevidence"] = sorted(
                    set(candidate["counterevidence"])
                    | {
                        "reconciliation_blocking_evidence",
                        "human_identity_decision_required",
                    }
                )
                material = {
                    "evidence_tier": candidate["evidence_tier"],
                    "disposition": candidate["disposition"],
                    "signals": candidate["signals"],
                    "counterevidence": candidate["counterevidence"],
                    "relation": candidate["relation"],
                    "evidence_details": candidate["evidence_details"],
                }
                candidate["revision_id"] = stable_id(
                    candidate["proposal_id"], _canonical_hash(material)
                )
        for workstream in sorted(eligible, key=lambda row: str(row["workstream_id"])):
            workstream_id = str(workstream["workstream_id"])
            available = sorted(available_by_workstream[workstream_id], key=_candidate_sort_key)
            shown = available[: policy.candidate_limit]
            candidates.extend(shown)
            cards.append(
                {
                    "card_id": stable_id("portfolio-reconciliation-workstream-card", workstream_id),
                    "workstream_id": workstream_id,
                    "label": str(workstream["label"]),
                    "lifecycle_state": str(workstream["lifecycle_state"]),
                    "accepted_resource_ids": sorted(
                        str(value) for value in workstream.get("accepted_resource_ids", [])
                    ),
                    "candidate_proposal_ids": [row["proposal_id"] for row in shown],
                    "truncated_candidate_count": len(available) - len(shown),
                }
            )
        candidates.sort(key=_candidate_sort_key)
        today_workstreams = {str(row.get("workstream_id", "")) for row in today}
        today_resources = {
            str(resource_id) for row in today for resource_id in row.get("resource_ids", [])
        }
        review_rows = [
            row
            for row in candidates
            if row["workstream_id"] in today_workstreams or row["resource_id"] in today_resources
        ]
        bounded_review_ids = [
            str(row["proposal_id"])
            for row in sorted(review_rows, key=_candidate_sort_key)[: policy.review_limit]
        ]
        allowed_commands = set(bounded_review_ids)
        for candidate in complete_candidates:
            if (
                candidate["disposition"] != "proposal_ready"
                or candidate["proposal_id"] in allowed_commands
            ):
                continue
            candidate["disposition"] = "proposal_available"
            candidate["proposal_command"] = None
            candidate["counterevidence"] = sorted(
                set(candidate["counterevidence"]) | {"outside_bounded_review_queue"}
            )
            material = {
                "evidence_tier": candidate["evidence_tier"],
                "disposition": candidate["disposition"],
                "signals": candidate["signals"],
                "counterevidence": candidate["counterevidence"],
                "relation": candidate["relation"],
                "evidence_details": candidate["evidence_details"],
            }
            candidate["revision_id"] = stable_id(
                candidate["proposal_id"], _canonical_hash(material)
            )
        for card in cards:
            shown_ids = set(str(value) for value in card["candidate_proposal_ids"])
            card["hidden_exact_proposal_count"] = sum(
                row["workstream_id"] == card["workstream_id"]
                and row["proposal_id"] not in shown_ids
                and row["disposition"] in {"proposal_ready", "proposal_available"}
                for row in complete_candidates
            )
            card_material = {
                key: card[key]
                for key in (
                    "workstream_id",
                    "label",
                    "lifecycle_state",
                    "accepted_resource_ids",
                    "candidate_proposal_ids",
                    "truncated_candidate_count",
                    "hidden_exact_proposal_count",
                )
            }
            card["card_revision_id"] = stable_id(card["card_id"], _canonical_hash(card_material))
        candidates.sort(key=_candidate_sort_key)

    by_resource: dict[str, list[str]] = {}
    for row in candidates:
        by_resource.setdefault(row["resource_id"], []).append(row["proposal_id"])
    bundle_rows: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in attention_items:
        projected_workstream_id = str(item.get("workstream_id", ""))
        identity_scope = _attention_identity_resource_ids(item, resources)
        if not identity_scope:
            continue
        context_workstream_id = projected_workstream_id
        if not context_workstream_id:
            specific_owners = {
                owner
                for resource_id in identity_scope
                for owner in resources[resource_id].get("accepted_workstream_ids", [])
            }
            context_owners = specific_owners
            if not context_owners:
                context_owners = {
                    owner
                    for resource_id in item.get("resource_ids", [])
                    if str(resource_id) in resources
                    for owner in resources[str(resource_id)].get("accepted_workstream_ids", [])
                }
            if len(context_owners) == 1:
                context_workstream_id = str(next(iter(context_owners)))
        if context_workstream_id in workstream_by_id:
            resource_ids = tuple(
                resource_id
                for resource_id in identity_scope
                if (context_workstream_id, resource_id) not in accepted_pairs
            )
        else:
            resource_ids = identity_scope
        if not resource_ids:
            continue
        bundle_key = (context_workstream_id, *resource_ids)
        scoped_project_ids = sorted(
            {str(resources[resource_id]["project_id"]) for resource_id in resource_ids}
        )
        scoped_project_names = sorted(
            {str(resources[resource_id]["project_name"]) for resource_id in resource_ids}
        )
        project_id = str(item.get("project_id", ""))
        project_name = str(item.get("project_name", ""))
        if not project_id and len(scoped_project_ids) == 1:
            project_id = scoped_project_ids[0]
        if not project_name and len(scoped_project_names) == 1:
            project_name = scoped_project_names[0]
        row = bundle_rows.setdefault(
            bundle_key,
            {
                "bundle_id": stable_id(
                    "portfolio-reconciliation-resource-bundle",
                    context_workstream_id,
                    *resource_ids,
                ),
                "attention_ids": [],
                "context_workstream_id": context_workstream_id,
                "project_id": project_id,
                "project_name": project_name,
                "label": str(item.get("label", "")),
                "resource_ids": list(resource_ids),
                "resource_kinds": sorted(
                    {str(resources[resource_id]["resource_kind"]) for resource_id in resource_ids}
                ),
                "resource_labels": sorted(
                    {str(resources[resource_id]["label"]) for resource_id in resource_ids}
                ),
                "candidate_proposal_ids": [],
                "next_action": "",
            },
        )
        row["attention_ids"].append(str(item.get("attention_id", "")))
        row["candidate_proposal_ids"].extend(
            proposal_id
            for resource_id in resource_ids
            for proposal_id in by_resource.get(resource_id, [])
        )

    unassigned_bundles = []
    for row in bundle_rows.values():
        row["attention_ids"] = sorted(set(row["attention_ids"]))
        row["candidate_proposal_ids"] = sorted(set(row["candidate_proposal_ids"]))[
            : policy.candidate_limit
        ]
        row["next_action"] = (
            "Review candidate evidence; leave this work bundle unassigned if identity is uncertain."
            if row["candidate_proposal_ids"]
            else "Capture an idea as a workstream, or intentionally leave this work bundle unassigned."
        )
        unassigned_bundles.append(row)
    unassigned_bundles.sort(key=lambda row: (row["project_id"], row["bundle_id"]))

    today_ids = {str(row.get("attention_id", "")) for row in today}
    candidate_by_proposal_id = {str(row["proposal_id"]): row for row in candidates}
    review_queue = []
    for proposal_id in bounded_review_ids:
        row = candidate_by_proposal_id[proposal_id]
        attention_ids = sorted(
            str(item["attention_id"])
            for item in today
            if item.get("workstream_id") == row["workstream_id"]
            or row["resource_id"] in item.get("resource_ids", [])
        )
        if attention_ids and set(attention_ids) <= today_ids:
            review_queue.append(
                {
                    "review_id": stable_id("portfolio-reconciliation-review", row["proposal_id"]),
                    "kind": "binding_candidate",
                    "attention_ids": attention_ids,
                    "proposal_id": row["proposal_id"],
                    "label": row["workstream_label"],
                    "next_action": (
                        "Review the existing exact proposal."
                        if row["disposition"] == "review_existing"
                        else "Inspect the evidence; no identity decision has been made."
                    ),
                }
            )

    all_workstreams_bound = all(
        any(
            resource_id in resources
            and workstream_id
            in set(
                str(value) for value in resources[resource_id].get("accepted_workstream_ids", [])
            )
            and (workstream_id, resource_id) in accepted_pairs
            for resource_id in set(str(value) for value in row.get("accepted_resource_ids", []))
        )
        for row in eligible
        for workstream_id in [str(row["workstream_id"])]
    )
    all_attention_assigned = not unassigned_bundles
    no_exact_proposals = not any(
        row["disposition"] in {"proposal_ready", "proposal_available"}
        for row in complete_candidates
    )
    fully_reconciled = bool(
        source_ready
        and not blockers
        and not unknowns
        and eligible
        and all_workstreams_bound
        and all_attention_assigned
        and no_exact_proposals
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "status": "generated_candidate" if source_ready else "blocked_candidate",
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "execution_authorized": False,
        "mutations_performed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "methodology": {
            "method_id": METHOD_ID,
            "methodology_ref": METHODOLOGY_REF,
            "candidate_limit": policy.candidate_limit,
            "review_limit": policy.review_limit,
            "fresh_after_hours": policy.fresh_after_hours,
            "future_tolerance_hours": policy.future_tolerance_hours,
            "evidence_precedence": [
                "E0_existing_exact",
                "E1_unique_structural",
                "I0_inspect_only",
            ],
            "critical_path_claimed": False,
        },
        "source": source,
        "summary": {
            "workstream_count": len(workstreams),
            "eligible_workstream_count": len(eligible),
            "candidate_count": len(candidates),
            "hidden_candidate_count": sum(int(row["truncated_candidate_count"]) for row in cards),
            "proposal_ready_count": sum(
                row["disposition"] == "proposal_ready" for row in candidates
            ),
            "hidden_exact_proposal_count": sum(
                int(row["hidden_exact_proposal_count"]) for row in cards
            ),
            "inspect_only_count": sum(row["disposition"] == "inspect_only" for row in candidates),
            "unassigned_attention_bundle_count": len(unassigned_bundles),
            "blocker_count": len(blockers),
            "unknown_count": len(unknowns),
            "blocking_evidence_count": len(blockers) + len(unknowns),
            "fully_reconciled": fully_reconciled,
            "intake_needed": source_ready and not workstreams,
            "no_candidates_generated": not candidates,
        },
        "review_queue": review_queue,
        "workstream_cards": cards,
        "binding_candidates": sorted(candidates, key=_candidate_sort_key),
        "unassigned_bundles": unassigned_bundles,
        "quiet_workstream_ids": sorted(str(row["workstream_id"]) for row in quiet_workstreams),
        "dependency_context": {
            "accepted_only": True,
            "critical_path_claimed": False,
            "unlock_frontier": value.get("lanes", {}).get("unlock_frontier", []),
        },
        "blockers": blockers,
        "unknowns": unknowns,
        "source_refs": {"cockpit": source["source_hash"]},
    }


_STYLE = """
:root{color-scheme:dark;--bg:#081014;--panel:#102027;--line:#28434c;--text:#f5f7f6;--muted:#a2b5ba;--mint:#70e0b8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,sans-serif}.skip{position:absolute;left:-999px;top:8px;background:#fff;color:#000;padding:10px;z-index:2}.skip:focus{left:8px}.shell{width:min(1320px,94vw);margin:auto;padding:44px 0 80px}.eyebrow{text-transform:uppercase;letter-spacing:.13em;color:var(--mint);font-size:.72rem;font-weight:800}h1{font-size:clamp(2.5rem,6vw,5.5rem);line-height:.93;margin:.3rem 0 1rem}h2{margin-top:3rem}.muted{color:var(--muted);max-width:920px}.stats,.cards{display:grid;gap:14px}.stats{grid-template-columns:repeat(6,1fr);margin:28px 0}.cards{grid-template-columns:repeat(3,1fr)}.card,.stat,.table-wrap,details{background:var(--panel);border:1px solid var(--line);border-radius:17px}.card,.stat{padding:18px}.stat strong{display:block;font-size:1.8rem}.stat span{color:var(--muted)}details{padding:14px}summary{cursor:pointer;font-weight:700}code{color:#b5ead7;overflow-wrap:anywhere}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}caption{text-align:left;padding:12px 14px;font-weight:700}th,td{padding:12px 14px;border-top:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted);font-size:.74rem;text-transform:uppercase}footer{margin-top:48px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted)}@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.cards{grid-template-columns:1fr}}
""".strip()


def _csp() -> str:
    digest = base64.b64encode(hashlib.sha256(_STYLE.encode("utf-8")).digest()).decode("ascii")
    return (
        "default-src 'none'; "
        f"style-src 'sha256-{digest}'; "
        "img-src 'none'; connect-src 'none'; script-src 'none'; object-src 'none'; "
        "frame-src 'none'; base-uri 'none'; form-action 'none'"
    )


def portfolio_reconciliation_html(projection: dict[str, Any]) -> str:
    """Render an inert, script-free human review surface."""

    summary = projection["summary"]
    review_cards = "".join(
        '<article class="card">'
        f'<div class="eyebrow">{escape(row["kind"].replace("_", " "))}</div>'
        f"<h3>{escape(row['label'])}</h3><p>{escape(row['next_action'])}</p>"
        f"<code>{escape(row['proposal_id'])}</code></article>"
        for row in projection["review_queue"]
    ) or (
        '<article class="card"><h3>No extra review item</h3>'
        "<p>This layer adds nothing beyond the current Today list.</p></article>"
    )
    workstream_rows = (
        "".join(
            "<tr>"
            f"<td>{escape(row['label'])}</td>"
            f"<td>{escape(row['lifecycle_state'])}</td>"
            f"<td>{len(row['accepted_resource_ids'])}</td>"
            f"<td>{len(row['candidate_proposal_ids'])}</td>"
            f"<td>{row['hidden_exact_proposal_count']}</td>"
            f"<td>{row['truncated_candidate_count']}</td></tr>"
            for row in projection["workstream_cards"]
        )
        or '<tr><td colspan="6">No eligible workstream card is visible.</td></tr>'
    )
    candidate_rows = "".join(
        "<tr>"
        f"<td>{escape(row['evidence_tier'])}</td>"
        f"<td>{escape(row['workstream_label'])}</td>"
        f"<td>{escape(row['resource_label'])}</td>"
        f"<td>{escape(row['disposition'])}</td>"
        f"<td>{escape('; '.join(row['signals']))}</td>"
        f"<td><code>{escape(row['proposal_id'])}</code></td></tr>"
        for row in projection["binding_candidates"]
    ) or (
        '<tr><td colspan="6">No candidate was generated. This is not an all-clear result.</td></tr>'
    )
    unassigned_rows = (
        "".join(
            "<tr>"
            f"<td>{escape(row['project_name'])}</td>"
            f"<td>{escape(', '.join(row['resource_kinds']))}</td>"
            f"<td>{escape(row['label'])}</td>"
            f"<td><code>{escape(', '.join(row['resource_ids']))}</code></td>"
            f"<td>{escape(row['next_action'])}</td></tr>"
            for row in projection["unassigned_bundles"]
        )
        or '<tr><td colspan="5">No unassigned attention bundle is visible.</td></tr>'
    )
    blocker_rows = (
        "".join(
            f"<tr><td>{escape(row['kind'])}</td>"
            f"<td><code>{escape(row['ref'])}</code></td>"
            f"<td>{escape(row['note'])}</td></tr>"
            for row in projection["blockers"]
        )
        or '<tr><td colspan="3">No reconciliation-specific blocker reported.</td></tr>'
    )
    unknown_rows = (
        "".join(
            f"<tr><td>{escape(row['severity'])}</td><td>{escape(row['source'])}</td>"
            f"<td>{escape(row['kind'])}</td><td><code>{escape(row['ref'])}</code></td>"
            f"<td>{escape(row['note'])}</td></tr>"
            for row in projection["unknowns"]
        )
        or '<tr><td colspan="5">No cockpit evidence gap reported.</td></tr>'
    )
    source_problems = "; ".join(projection["source"]["problems"]) or "None"
    reconciled = "yes" if summary["fully_reconciled"] else "no"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(_csp(), quote=True)}"><title>DAD Portfolio Reconciliation</title><style>{_STYLE}</style></head>
<body><a class="skip" href="#main">Skip to main content</a><main id="main" class="shell"><div class="eyebrow">DAD &middot; Portfolio identity steward</div>
<h1>Reconnect the work. Keep authority human.</h1><p class="muted">Exact resource proposals and inspect-only similarity evidence over one frozen cockpit snapshot. No control on this page can perform an action.</p>
<p class="muted"><strong>Fully reconciled: {reconciled}.</strong> Source: {escape(projection["source"]["status"])} / {escape(projection["source"]["freshness"])}. Source problems: {escape(source_problems)}.</p>
<section class="stats"><div class="stat"><strong>{summary["workstream_count"]}</strong><span>workstreams</span></div><div class="stat"><strong>{summary["candidate_count"]}</strong><span>visible candidates</span></div><div class="stat"><strong>{summary["hidden_candidate_count"]}</strong><span>hidden candidates</span></div><div class="stat"><strong>{summary["proposal_ready_count"]}</strong><span>proposal ready</span></div><div class="stat"><strong>{summary["hidden_exact_proposal_count"]}</strong><span>hidden exact proposals</span></div><div class="stat"><strong>{summary["unassigned_attention_bundle_count"]}</strong><span>unassigned bundles</span></div><div class="stat"><strong>{summary["blocker_count"]}</strong><span>blockers</span></div><div class="stat"><strong>{summary["unknown_count"]}</strong><span>unknowns</span></div></section>
<h2>Today organization</h2><section class="cards">{review_cards}</section>
<h2>Workstream coverage</h2><div class="table-wrap"><table><caption>Visible and hidden exact evidence by eligible workstream.</caption><thead><tr><th scope="col">Workstream</th><th scope="col">State</th><th scope="col">Accepted exact</th><th scope="col">Visible candidates</th><th scope="col">Hidden exact</th><th scope="col">Truncated candidates</th></tr></thead><tbody>{workstream_rows}</tbody></table></div>
<h2>Binding evidence</h2><div class="table-wrap"><table><caption>Candidate identity evidence; similarity is inspect-only.</caption><thead><tr><th scope="col">Tier</th><th scope="col">Workstream</th><th scope="col">Resource</th><th scope="col">Disposition</th><th scope="col">Signals</th><th scope="col">Proposal ID</th></tr></thead><tbody>{candidate_rows}</tbody></table></div>
<h2>Unassigned observed work</h2><details><summary>Full evidence inventory ({summary["unassigned_attention_bundle_count"]} bundles; not a Today queue)</summary><div class="table-wrap"><table><caption>Exact resource bundles grouped from observed attention.</caption><thead><tr><th scope="col">Project</th><th scope="col">Kinds</th><th scope="col">Label</th><th scope="col">Exact IDs</th><th scope="col">Next action</th></tr></thead><tbody>{unassigned_rows}</tbody></table></div></details>
<h2>Reconciliation blockers</h2><div class="table-wrap"><table><caption>Reconciliation-specific identity and source blockers.</caption><thead><tr><th scope="col">Kind</th><th scope="col">Ref</th><th scope="col">Explanation</th></tr></thead><tbody>{blocker_rows}</tbody></table></div>
<h2>Cockpit evidence gaps</h2><div class="table-wrap"><table><caption>Sanitized categorical evidence; inspect the local cockpit for source detail.</caption><thead><tr><th scope="col">Severity</th><th scope="col">Source</th><th scope="col">Kind</th><th scope="col">Opaque ref</th><th scope="col">Explanation</th></tr></thead><tbody>{unknown_rows}</tbody></table></div>
<footer>Generated {escape(projection["generated_at"])}. {escape(projection["authority_boundary"])}</footer></main></body></html>"""


def portfolio_reconciliation_semantic_problems(
    projection: dict[str, Any],
) -> list[str]:
    """Validate cross-field integrity that JSON Schema cannot express."""

    problems: set[str] = set()
    source = projection.get("source", {})
    source_refs = projection.get("source_refs", {})
    if source_refs.get("cockpit") != source.get("source_hash"):
        problems.add("source_hash_reference_mismatch")

    candidates = [row for row in projection.get("binding_candidates", []) if isinstance(row, dict)]
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for row in candidates:
        proposal_id = str(row.get("proposal_id", ""))
        if proposal_id in candidate_by_id:
            problems.add("duplicate_candidate_proposal_id")
        candidate_by_id[proposal_id] = row
        expected_proposal_id = stable_id(
            METHOD_ID,
            str(row.get("workstream_id", "")),
            str(row.get("resource_id", "")),
        )
        if proposal_id != expected_proposal_id:
            problems.add("candidate_proposal_identity_mismatch")
        details = row.get("evidence_details", {})
        if details.get("target_label_hash") != _canonical_hash(str(row.get("resource_label", ""))):
            problems.add("candidate_target_label_hash_mismatch")
        binding_ids = details.get("binding_ids", [])
        if binding_ids != sorted(set(str(value) for value in binding_ids)):
            problems.add("candidate_binding_ids_not_canonical")
        if details.get("binding_id") and details.get("binding_id") not in binding_ids:
            problems.add("candidate_binding_id_not_in_evidence_set")
        anchor_ids = details.get("structural_anchor_resource_ids", [])
        if anchor_ids != sorted(set(str(value) for value in anchor_ids)):
            problems.add("candidate_structural_anchors_not_canonical")
        if (
            details.get("structural_anchor_resource_id")
            and details.get("structural_anchor_resource_id") not in anchor_ids
        ):
            problems.add("candidate_structural_anchor_not_in_evidence_set")
        material = {
            "evidence_tier": row.get("evidence_tier"),
            "disposition": row.get("disposition"),
            "signals": row.get("signals"),
            "counterevidence": row.get("counterevidence"),
            "relation": row.get("relation"),
            "evidence_details": details,
        }
        expected_revision_id = stable_id(proposal_id, _canonical_hash(material))
        if row.get("revision_id") != expected_revision_id:
            problems.add("candidate_revision_identity_mismatch")
        command = row.get("proposal_command")
        if isinstance(command, dict):
            expected_args = [
                "os",
                "bind",
                str(row.get("workstream_id", "")),
                str(row.get("resource_kind", "")),
                str(row.get("resource_id", "")),
                "--label",
                str(row.get("resource_label", "")),
                "--request-id",
                proposal_id,
            ]
            if command.get("command") != "asset-dir" or command.get("args") != expected_args:
                problems.add("candidate_command_target_mismatch")

    cards = [row for row in projection.get("workstream_cards", []) if isinstance(row, dict)]
    seen_workstream_ids: set[str] = set()
    for card in cards:
        workstream_id = str(card.get("workstream_id", ""))
        if workstream_id in seen_workstream_ids:
            problems.add("duplicate_workstream_card_identity")
        seen_workstream_ids.add(workstream_id)
        card_id = stable_id("portfolio-reconciliation-workstream-card", workstream_id)
        if card.get("card_id") != card_id:
            problems.add("workstream_card_identity_mismatch")
        card_material = {
            key: card.get(key)
            for key in (
                "workstream_id",
                "label",
                "lifecycle_state",
                "accepted_resource_ids",
                "candidate_proposal_ids",
                "truncated_candidate_count",
                "hidden_exact_proposal_count",
            )
        }
        if card.get("card_revision_id") != stable_id(card_id, _canonical_hash(card_material)):
            problems.add("workstream_card_revision_mismatch")
        for proposal_id in card.get("candidate_proposal_ids", []):
            candidate = candidate_by_id.get(str(proposal_id))
            if not candidate or candidate.get("workstream_id") != workstream_id:
                problems.add("workstream_card_candidate_reference_mismatch")

    bundles = [row for row in projection.get("unassigned_bundles", []) if isinstance(row, dict)]
    for bundle in bundles:
        resource_ids = set(str(value) for value in bundle.get("resource_ids", []))
        expected_bundle_id = stable_id(
            "portfolio-reconciliation-resource-bundle",
            str(bundle.get("context_workstream_id", "")),
            *sorted(resource_ids),
        )
        if bundle.get("bundle_id") != expected_bundle_id:
            problems.add("unassigned_bundle_identity_mismatch")
        for proposal_id in bundle.get("candidate_proposal_ids", []):
            candidate = candidate_by_id.get(str(proposal_id))
            if not candidate or candidate.get("resource_id") not in resource_ids:
                problems.add("unassigned_bundle_candidate_reference_mismatch")

    review_proposal_ids: set[str] = set()
    for review in projection.get("review_queue", []):
        if not isinstance(review, dict):
            continue
        proposal_id = str(review.get("proposal_id", ""))
        review_proposal_ids.add(proposal_id)
        if proposal_id not in candidate_by_id:
            problems.add("review_candidate_reference_missing")
        if review.get("review_id") != stable_id("portfolio-reconciliation-review", proposal_id):
            problems.add("review_identity_mismatch")
    for candidate in candidates:
        if (
            candidate.get("disposition") == "proposal_ready"
            and str(candidate.get("proposal_id", "")) not in review_proposal_ids
        ):
            problems.add("ready_proposal_outside_bounded_review_queue")

    summary = projection.get("summary", {})
    expected_counts = {
        "candidate_count": len(candidates),
        "hidden_candidate_count": sum(
            int(row.get("truncated_candidate_count", 0)) for row in cards
        ),
        "proposal_ready_count": sum(
            row.get("disposition") == "proposal_ready" for row in candidates
        ),
        "hidden_exact_proposal_count": sum(
            int(row.get("hidden_exact_proposal_count", 0)) for row in cards
        ),
        "inspect_only_count": sum(row.get("disposition") == "inspect_only" for row in candidates),
        "unassigned_attention_bundle_count": len(bundles),
        "blocker_count": len(projection.get("blockers", [])),
        "unknown_count": len(projection.get("unknowns", [])),
        "blocking_evidence_count": len(projection.get("blockers", []))
        + len(projection.get("unknowns", [])),
    }
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            problems.add(f"summary_{key}_mismatch")
    if summary.get("no_candidates_generated") != (not candidates):
        problems.add("summary_no_candidates_generated_mismatch")
    source_ready = (
        source.get("status") == "observed"
        and source.get("freshness") == "current"
        and not source.get("problems")
    )
    if source_ready and summary.get("eligible_workstream_count") != len(cards):
        problems.add("summary_eligible_workstream_count_mismatch")
    if summary.get("intake_needed") != (source_ready and summary.get("workstream_count") == 0):
        problems.add("summary_intake_needed_mismatch")
    expected_fully_reconciled = bool(
        source_ready
        and not projection.get("blockers")
        and not projection.get("unknowns")
        and cards
        and all(card.get("accepted_resource_ids") for card in cards)
        and not bundles
        and not any(
            row.get("disposition") in {"proposal_ready", "proposal_available"} for row in candidates
        )
        and not any(int(card.get("hidden_exact_proposal_count", 0)) for card in cards)
    )
    if summary.get("fully_reconciled") != expected_fully_reconciled:
        problems.add("summary_fully_reconciled_mismatch")
    if (projection.get("blockers") or projection.get("unknowns")) and any(
        row.get("proposal_command") is not None for row in candidates
    ):
        problems.add("command_present_with_blocking_evidence")
    return sorted(problems)


def write_portfolio_reconciliation_outputs(
    hub_root: Path, projection: dict[str, Any]
) -> dict[str, Any]:
    """Validate and publish HTML first, then JSON as the durable cursor."""

    problems = _schema_validation_problems(projection, hub_root, "portfolio_reconciliation")
    if problems:
        raise ValueError("Invalid portfolio reconciliation projection: " + "; ".join(problems))
    semantic_problems = portfolio_reconciliation_semantic_problems(projection)
    if semantic_problems:
        raise ValueError(
            "Invalid portfolio reconciliation semantics: " + "; ".join(semantic_problems)
        )
    base = data_path(hub_root, "central_reports") / "portfolio_os"
    json_path = base / "reconciliation.json"
    html_path = base / "reconciliation.html"
    atomic_write_text(html_path, portfolio_reconciliation_html(projection))
    atomic_write_text(json_path, json_dumps(projection, pretty=True) + "\n")
    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "status": projection["status"],
        "summary": projection["summary"],
        "review_queue": projection["review_queue"],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "generated_at": projection["generated_at"],
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "METHOD_ID",
    "ReconciliationSettings",
    "SCHEMA_VERSION",
    "build_portfolio_reconciliation",
    "cockpit_projection_hash",
    "portfolio_reconciliation_html",
    "portfolio_reconciliation_semantic_problems",
    "write_portfolio_reconciliation_outputs",
]
