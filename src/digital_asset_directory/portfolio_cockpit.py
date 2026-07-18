"""Pure unified projection for the DAD Portfolio OS cockpit.

This module joins two independently authoritative projections: observed Git
metadata and the folded workstream ledger. It never scans, appends events, or
mutates a source repository. Only exact, accepted resource bindings may join
the two sources.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import base64
import hashlib
import json
import ntpath
from pathlib import Path
import posixpath
from typing import Any

from jsonschema import FormatChecker
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for

from .ids import stable_id
from .portfolio_attention import LIFECYCLE_STATES, MAX_TODAY, TERMINAL_STATES
from .transport import data_path
from .utils import atomic_write_text, json_dumps


SCHEMA_VERSION = "dad.portfolio_cockpit.v1"
GIT_SCHEMA_VERSION = "dad.portfolio_attention.v1"
WORKSTREAM_SCHEMA_VERSION = "dad.portfolio_workstreams.v1"
SELECTION_POLICY_ID = "dad.portfolio-cockpit-selection.v1"
METHODOLOGY_REF = "docs/frontier/collaboration/11_PORTFOLIO_COCKPIT_PROJECTION.md"

ATTENTION_BANDS = (
    "human_decision",
    "integrity_unknown",
    "dirty_recovery",
    "dependency_unlock",
    "related_active_neglect",
    "weekly_maintenance",
)
_BAND_ORDER = {band: index for index, band in enumerate(ATTENTION_BANDS)}
_RESOURCE_BINDING_KINDS = frozenset({"repo", "branch", "worktree"})
_QUIET_STATES = frozenset({"paused", "snoozed", "incubating"})

AUTHORITY_BOUNDARY = (
    "The cockpit is a local, read-only candidate projection. It does not authorize "
    "commits, branch or worktree changes, lifecycle changes, accepted bindings, "
    "notifications, agent dispatch, cross-repo writes, or source-canon changes."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CockpitSettings:
    """Display-only policy for the unified projection."""

    fresh_after_hours: int = 26
    today_limit: int = MAX_TODAY

    def __post_init__(self) -> None:
        if self.fresh_after_hours < 1:
            raise ValueError("fresh_after_hours must be at least 1")
        if not 1 <= self.today_limit <= MAX_TODAY:
            raise ValueError(f"today_limit must be between 1 and {MAX_TODAY}")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


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


def _default_schema_root() -> Path:
    return Path(__file__).parents[2]


def _schema_validation_problems(
    value: dict[str, Any], schema_root: Path, schema_name: str
) -> list[str]:
    try:
        registry = json.loads(
            (schema_root / "registry" / "schema-registry.json").read_text(encoding="utf-8")
        )
        schema_ref = registry.get("schemas", {}).get(schema_name)
        if not schema_ref:
            raise ValueError(f"schema registry missing {schema_name}")
        schema = json.loads((schema_root / str(schema_ref)).read_text(encoding="utf-8"))
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
        errors = sorted(
            validator_cls(schema, format_checker=FormatChecker()).iter_errors(value),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except (OSError, ValueError, json.JSONDecodeError, SchemaError) as exc:
        return [f"source_schema_unavailable:{schema_name}:{type(exc).__name__}"]
    problems = []
    for error in errors[:8]:
        path = "/".join(str(part) for part in error.absolute_path) or "$"
        problems.append(f"schema_validation_failed:{path}:{error.validator}")
    if len(errors) > 8:
        problems.append(f"schema_validation_failed:truncated:{len(errors) - 8}")
    return problems


def projection_hash(value: Any) -> str:
    """Return the canonical hash used for cockpit source coupling."""

    return _canonical_hash(value)


def schema_validation_problems(
    value: dict[str, Any], schema_root: Path, schema_name: str
) -> list[str]:
    """Validate a registered strict projection without exposing validator internals."""

    return _schema_validation_problems(value, schema_root, schema_name)


def _source_descriptor(
    name: str,
    value: Any,
    *,
    expected_schema: str,
    now: datetime,
    fresh_after_hours: int,
    schema_root: Path,
    schema_name: str,
) -> dict[str, Any]:
    problems: list[str] = []
    if value is None:
        return {
            "name": name,
            "status": "unavailable",
            "freshness": "unknown",
            "schema_version": "",
            "generated_at": "",
            "source_hash": "",
            "problems": ["source_unavailable"],
        }
    if not isinstance(value, dict):
        return {
            "name": name,
            "status": "invalid",
            "freshness": "unknown",
            "schema_version": "",
            "generated_at": "",
            "source_hash": _canonical_hash(value),
            "problems": ["source_not_object"],
        }
    schema_version = str(value.get("schema_version", ""))
    if schema_version != expected_schema:
        problems.append(f"unexpected_schema:{schema_version or 'missing'}")
    schema_problems = _schema_validation_problems(value, schema_root, schema_name)
    problems.extend(schema_problems)
    structure_valid = schema_version == expected_schema and not schema_problems
    generated_at = str(value.get("generated_at", ""))
    generated = _parse_datetime(generated_at)
    if generated is None:
        freshness = "unknown"
        problems.append("generated_at_invalid_or_missing")
    else:
        age_hours = (now - generated).total_seconds() / 3600
        if age_hours < -1:
            freshness = "unknown"
            problems.append("generated_at_in_future")
        elif age_hours > fresh_after_hours:
            freshness = "stale"
            problems.append("source_stale")
        else:
            freshness = "current"
    return {
        "name": name,
        "status": "observed" if structure_valid else "invalid",
        "freshness": freshness,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "source_hash": _canonical_hash(value),
        "problems": problems,
    }


def _normalized_path(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if "\\" in text or (len(text) >= 2 and text[1] == ":"):
        return ntpath.normcase(ntpath.normpath(text)).replace("\\", "/")
    return posixpath.normpath(text)


def branch_resource_id(project_id: str, branch_name: str) -> str:
    return stable_id("portfolio-branch", project_id, branch_name)


def worktree_resource_id(project_id: str, path: str) -> str:
    return stable_id("portfolio-worktree", project_id, _normalized_path(path))


def _resource_projection(
    git_report: dict[str, Any] | None,
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, str]],
]:
    projects: list[dict[str, Any]] = []
    resources: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, str]] = []
    if not git_report or git_report.get("schema_version") != GIT_SCHEMA_VERSION:
        return projects, resources, duplicates

    source_projects = list(git_report.get("projects", []))
    project_counts = Counter(str(row.get("project_id", "")) for row in source_projects)
    for project_id, count in sorted(project_counts.items()):
        if project_id and count > 1:
            duplicates.append({"kind": "repo", "ref": project_id})

    for source_project in sorted(source_projects, key=lambda row: str(row.get("project_id", ""))):
        project_id = str(source_project.get("project_id", ""))
        if not project_id or project_counts[project_id] != 1:
            continue
        branch_ids: list[str] = []
        worktree_ids: list[str] = []
        source_branches = list(source_project.get("branches", []))
        branch_counts = Counter(str(row.get("name", "")) for row in source_branches)
        for branch in sorted(source_branches, key=lambda row: str(row.get("name", ""))):
            name = str(branch.get("name", ""))
            resource_id = branch_resource_id(project_id, name)
            if branch_counts[name] != 1:
                duplicates.append({"kind": "branch", "ref": resource_id})
                continue
            linked: list[str] = []
            if branch.get("worktree_path"):
                linked.append(worktree_resource_id(project_id, str(branch["worktree_path"])))
            resources[resource_id] = {
                "resource_id": resource_id,
                "resource_kind": "branch",
                "project_id": project_id,
                "project_name": str(source_project.get("name", "")),
                "label": name,
                "path": "",
                "accepted_workstream_ids": [],
                "linked_resource_ids": linked,
            }
            branch_ids.append(resource_id)

        source_worktrees = list(source_project.get("worktrees", []))
        worktree_counts = Counter(
            _normalized_path(str(row.get("path", ""))) for row in source_worktrees
        )
        for worktree in sorted(source_worktrees, key=lambda row: str(row.get("path", ""))):
            path = str(worktree.get("path", ""))
            resource_id = worktree_resource_id(project_id, path)
            if worktree_counts[_normalized_path(path)] != 1:
                duplicates.append({"kind": "worktree", "ref": resource_id})
                continue
            branch_name = str(worktree.get("branch", ""))
            linked = [branch_resource_id(project_id, branch_name)] if branch_name else []
            resources[resource_id] = {
                "resource_id": resource_id,
                "resource_kind": "worktree",
                "project_id": project_id,
                "project_name": str(source_project.get("name", "")),
                "label": branch_name or "(detached HEAD)",
                "path": path,
                "accepted_workstream_ids": [],
                "linked_resource_ids": linked,
            }
            worktree_ids.append(resource_id)

        resources[project_id] = {
            "resource_id": project_id,
            "resource_kind": "repo",
            "project_id": project_id,
            "project_name": str(source_project.get("name", "")),
            "label": str(source_project.get("name", "")),
            "path": "",
            "accepted_workstream_ids": [],
            "linked_resource_ids": sorted([*branch_ids, *worktree_ids]),
        }
        projects.append(
            {
                "project_id": project_id,
                "name": str(source_project.get("name", "")),
                "default_branch": str(source_project.get("default_branch", "")),
                "active_within_threshold": bool(source_project.get("active_within_threshold")),
                "branch_resource_ids": sorted(branch_ids),
                "worktree_resource_ids": sorted(worktree_ids),
                "accepted_workstream_ids": [],
                "related_projects": deepcopy(source_project.get("related_projects", [])),
            }
        )
    return projects, resources, duplicates


def _binding_projection(
    state: dict[str, Any] | None,
    resources: dict[str, dict[str, Any]],
    *,
    ambiguous_workstream_ids: frozenset[str] = frozenset(),
) -> tuple[list[dict[str, Any]], dict[str, list[str]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    accepted_by_resource: dict[str, list[str]] = {}
    unresolved: list[dict[str, Any]] = []
    if not state or state.get("schema_version") != WORKSTREAM_SCHEMA_VERSION:
        return rows, accepted_by_resource, unresolved
    for workstream in sorted(
        state.get("workstreams", []), key=lambda row: str(row.get("workstream_id", ""))
    ):
        workstream_id = str(workstream.get("workstream_id", ""))
        if workstream_id in ambiguous_workstream_ids:
            continue
        for binding in sorted(
            workstream.get("bindings", []), key=lambda row: str(row.get("binding_id", ""))
        ):
            kind = str(binding.get("binding_kind", ""))
            if kind not in _RESOURCE_BINDING_KINDS:
                continue
            ref = str(binding.get("ref", ""))
            assertion_status = str(binding.get("assertion_status", "proposed"))
            exact = ref in resources and resources[ref]["resource_kind"] == kind
            resolution = (
                "accepted_exact"
                if assertion_status == "accepted" and exact
                else "accepted_unresolved"
                if assertion_status == "accepted"
                else "proposed_exact"
                if exact
                else "proposed_unresolved"
            )
            row = {
                "binding_id": str(binding.get("binding_id", "")),
                "workstream_id": workstream_id,
                "binding_kind": kind,
                "ref": ref,
                "assertion_status": assertion_status,
                "resolution": resolution,
                "resource_id": ref if exact else "",
            }
            rows.append(row)
            if resolution == "accepted_exact":
                accepted_by_resource.setdefault(ref, []).append(workstream_id)
            elif resolution == "accepted_unresolved":
                unresolved.append(row)
    for resource_id, workstream_ids in accepted_by_resource.items():
        resources[resource_id]["accepted_workstream_ids"] = sorted(set(workstream_ids))
    return rows, accepted_by_resource, unresolved


def _coverage(
    source: str, kind: str, ref: str, note: str, *, severity: str = "warning"
) -> dict[str, str]:
    return {
        "source": source,
        "kind": kind,
        "ref": ref,
        "note": note,
        "severity": severity,
    }


def _item_fingerprint(item: dict[str, Any]) -> str:
    material = {
        key: value for key, value in item.items() if key not in {"fingerprint", "selected_today"}
    }
    return _canonical_hash(material)


def _finish_item(item: dict[str, Any]) -> dict[str, Any]:
    item["reasons"] = sorted(set(str(reason) for reason in item.get("reasons", []) if reason))
    item["resource_ids"] = sorted(set(str(ref) for ref in item.get("resource_ids", []) if ref))
    item["selected_today"] = False
    item["fingerprint"] = _item_fingerprint(item)
    return item


def _git_band(item: dict[str, Any]) -> str:
    reasons = set(item.get("reasons", []))
    # A branch with no checked-out worktree legitimately has dirty=None. Only
    # explicit status failure is an integrity unknown.
    if reasons & {"worktree_status_unknown", "conflicted_worktree", "upstream_gone"}:
        return "integrity_unknown"
    if reasons & {"dirty_worktree_idle", "dirty_worktree", "dirty_detached_worktree"}:
        return "dirty_recovery"
    if "stale_branch_in_active_project" in reasons:
        return "related_active_neglect"
    return "weekly_maintenance"


def _resource_ids_for_git_item(
    item: dict[str, Any], resources: dict[str, dict[str, Any]]
) -> list[str]:
    project_id = str(item.get("project_id", ""))
    result = [project_id] if project_id in resources else []
    branch = str(item.get("branch", ""))
    if branch and branch != "(detached HEAD)":
        candidate = branch_resource_id(project_id, branch)
        if candidate in resources:
            result.append(candidate)
    path = str(item.get("worktree_path", ""))
    if path:
        candidate = worktree_resource_id(project_id, path)
        if candidate in resources:
            result.append(candidate)
    return sorted(set(result))


def _workstream_band(item: dict[str, Any], needs_decision: bool, blocking_count: int) -> str:
    trigger_kind = str(item.get("trigger_kind", ""))
    if needs_decision or trigger_kind in {
        "blocker",
        "conflict_decision",
        "decision_proposed",
    }:
        return "human_decision"
    if blocking_count > 0:
        return "dependency_unlock"
    if trigger_kind == "related_active_idle":
        return "related_active_neglect"
    return "weekly_maintenance"


def _attention_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    priorities = item["source_local_priorities"]
    source_priority = max(int(priorities["git"]), int(priorities["workstreams"]))
    inactive = item.get("inactive_days")
    return (
        _BAND_ORDER[item["band"]],
        -source_priority,
        -int(item.get("blocking_count", 0)),
        -int(inactive if isinstance(inactive, int) else -1),
        item["attention_id"],
    )


def _merge_item(target: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    target["source"] = "joined"
    target["band"] = min((target["band"], incoming["band"]), key=_BAND_ORDER.__getitem__)
    target["source_local_priorities"]["git"] = max(
        target["source_local_priorities"]["git"],
        incoming["source_local_priorities"]["git"],
    )
    target["source_local_priorities"]["workstreams"] = max(
        target["source_local_priorities"]["workstreams"],
        incoming["source_local_priorities"]["workstreams"],
    )
    target["blocking_count"] = max(target["blocking_count"], incoming["blocking_count"])
    target["inactive_days"] = max(
        (
            value
            for value in (target.get("inactive_days"), incoming.get("inactive_days"))
            if isinstance(value, int)
        ),
        default=None,
    )
    target["reasons"].extend(incoming["reasons"])
    target["resource_ids"].extend(incoming["resource_ids"])
    if not target.get("project_id"):
        target["project_id"] = incoming.get("project_id", "")
        target["project_name"] = incoming.get("project_name", "")
    if not target.get("next_action"):
        target["next_action"] = incoming.get("next_action", "")
    target["evidence"]["git"] = incoming["evidence"].get("git", {})
    return _finish_item(target)


def _system_attention(row: dict[str, str]) -> dict[str, Any]:
    return _finish_item(
        {
            "attention_id": stable_id(
                "portfolio-cockpit-attention",
                row["source"],
                row["kind"],
                row["ref"],
                row["note"],
            ),
            "source": "system",
            "band": "integrity_unknown",
            "source_local_priorities": {"git": 0, "workstreams": 0},
            "blocking_count": 0,
            "inactive_days": None,
            "project_id": "",
            "project_name": "",
            "workstream_id": "",
            "label": row["note"],
            "lifecycle_state": "",
            "reasons": [row["kind"]],
            "next_action": (
                "Inspect the source evidence before treating this portfolio state as clear."
            ),
            "resource_ids": [],
            "evidence": {**_empty_evidence(), "coverage_ref": row["ref"]},
        }
    )


def _empty_evidence() -> dict[str, Any]:
    return {
        "git": {
            "dirty": None,
            "changed_path_count": 0,
            "ahead": 0,
            "behind": 0,
        },
        "workstream": {
            "trigger_kind": "",
            "trigger_signature": "",
            "tier": "",
            "needs_human_decision": False,
        },
        "coverage_ref": "",
    }


def build_portfolio_cockpit(
    git_report: dict[str, Any] | None,
    workstream_state: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    settings: CockpitSettings | None = None,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    """Join source projections without mutating either input."""

    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    policy = settings or CockpitSettings()
    schemas = schema_root or _default_schema_root()
    sources = {
        "git": _source_descriptor(
            "git",
            git_report,
            expected_schema=GIT_SCHEMA_VERSION,
            now=observed,
            fresh_after_hours=policy.fresh_after_hours,
            schema_root=schemas,
            schema_name="portfolio_attention_report",
        ),
        "workstreams": _source_descriptor(
            "workstreams",
            workstream_state,
            expected_schema=WORKSTREAM_SCHEMA_VERSION,
            now=observed,
            fresh_after_hours=policy.fresh_after_hours,
            schema_root=schemas,
            schema_name="portfolio_workstream_state",
        ),
    }
    git_source = (
        git_report
        if sources["git"]["status"] == "observed" and sources["git"]["freshness"] != "unknown"
        else None
    )
    workstream_source = (
        workstream_state
        if sources["workstreams"]["status"] == "observed"
        and sources["workstreams"]["freshness"] != "unknown"
        else None
    )
    workstream_rows = list((workstream_source or {}).get("workstreams", []))
    workstream_counts = Counter(str(row.get("workstream_id", "")) for row in workstream_rows)
    ambiguous_workstream_ids = frozenset(
        workstream_id
        for workstream_id, count in workstream_counts.items()
        if workstream_id and count > 1
    )
    projects, resource_map, duplicate_resources = _resource_projection(git_source)
    bindings, accepted_by_resource, unresolved = _binding_projection(
        workstream_source,
        resource_map,
        ambiguous_workstream_ids=ambiguous_workstream_ids,
    )
    coverage: list[dict[str, str]] = []

    for descriptor in sources.values():
        for problem in descriptor["problems"]:
            coverage.append(
                _coverage(
                    descriptor["name"],
                    problem.split(":", 1)[0],
                    descriptor["source_hash"],
                    problem,
                    severity="danger" if descriptor["status"] != "observed" else "warning",
                )
            )

    for duplicate in sorted({(row["kind"], row["ref"]) for row in duplicate_resources}):
        kind, ref = duplicate
        coverage.append(
            _coverage(
                "git",
                "duplicate_resource_identity",
                ref,
                f"Duplicate {kind} identity was quarantined and cannot join attention.",
                severity="danger",
            )
        )
    for workstream_id in sorted(ambiguous_workstream_ids):
        coverage.append(
            _coverage(
                "workstreams",
                "duplicate_workstream_identity",
                workstream_id,
                "Duplicate workstream identity was quarantined and cannot join attention.",
                severity="danger",
            )
        )

    if git_source:
        for error in git_source.get("scan", {}).get("errors", []):
            detail = str(error.get("error", "scan_error"))
            ref = stable_id(
                "portfolio-cockpit-source-error",
                str(error.get("path", "")),
                detail,
            )
            coverage.append(_coverage("git", "scan_error", ref, detail, severity="danger"))
        for project in git_source.get("projects", []):
            project_id = str(project.get("project_id", ""))
            for worktree in project.get("worktrees", []):
                if worktree.get("status_known") is False or worktree.get("dirty") is None:
                    ref = worktree_resource_id(project_id, str(worktree.get("path", "")))
                    coverage.append(
                        _coverage(
                            "git",
                            "worktree_status_unknown",
                            ref,
                            "A checked-out worktree could not be classified clean or dirty.",
                            severity="danger",
                        )
                    )

    if workstream_source:
        for row in workstream_source.get("coverage", []):
            coverage.append(
                _coverage(
                    "workstreams",
                    "fold_coverage",
                    str(row.get("workstream_id", "")),
                    str(row.get("note", "coverage note")),
                )
            )
        diagnostics = workstream_source.get("ledger_diagnostics", {})
        for problem in diagnostics.get("fold_problems", []):
            coverage.append(
                _coverage(
                    "workstreams",
                    "ledger_fold_problem",
                    stable_id("portfolio-cockpit-ledger-problem", str(problem)),
                    str(problem),
                    severity="danger",
                )
            )
        for key in ("corrupt_line_count", "invalid_envelope_count"):
            count = int(diagnostics.get(key, 0))
            if count:
                coverage.append(
                    _coverage(
                        "workstreams",
                        f"ledger_{key}",
                        stable_id("portfolio-cockpit-ledger-problem", key, str(count)),
                        f"{key}:{count}",
                        severity="danger",
                    )
                )
        if bool(diagnostics.get("torn_tail_pending")):
            coverage.append(
                _coverage(
                    "workstreams",
                    "ledger_torn_tail_pending",
                    stable_id("portfolio-cockpit-ledger-problem", "torn_tail_pending"),
                    "The ledger has an unacknowledged torn tail.",
                    severity="danger",
                )
            )
        for problem in diagnostics.get("problems", []):
            coverage.append(
                _coverage(
                    "workstreams",
                    "ledger_integrity_problem",
                    stable_id("portfolio-cockpit-ledger-problem", str(problem)),
                    str(problem),
                    severity="danger",
                )
            )

    for row in unresolved:
        coverage.append(
            _coverage(
                "bindings",
                "accepted_binding_unresolved",
                row["binding_id"] or row["ref"],
                (
                    f"Accepted {row['binding_kind']} binding for {row['workstream_id']} "
                    "does not match an exact observed resource ID."
                ),
                severity="danger",
            )
        )

    workstream_by_id = {
        str(row.get("workstream_id", "")): row
        for row in workstream_rows
        if workstream_counts[str(row.get("workstream_id", ""))] == 1
    }
    accepted_resources_by_workstream: dict[str, list[str]] = {}
    for resource_id, workstream_ids in accepted_by_resource.items():
        for workstream_id in workstream_ids:
            accepted_resources_by_workstream.setdefault(workstream_id, []).append(resource_id)

    projected_workstreams: list[dict[str, Any]] = []
    for workstream_id, row in sorted(workstream_by_id.items()):
        proposed_refs = sorted(
            binding["ref"]
            for binding in bindings
            if binding["workstream_id"] == workstream_id
            and binding["assertion_status"] != "accepted"
        )
        projected_workstreams.append(
            {
                "workstream_id": workstream_id,
                "label": str(row.get("idea_text", "")),
                "lifecycle_state": str(row.get("lifecycle_state", "")),
                "needs_human_decision": bool(row.get("needs_human_decision"))
                and not bool(row.get("conflict_resolved")),
                "inactive_days": row.get("inactive_days")
                if isinstance(row.get("inactive_days"), int)
                else None,
                "accepted_resource_ids": sorted(
                    set(accepted_resources_by_workstream.get(workstream_id, []))
                ),
                "proposed_resource_refs": proposed_refs,
            }
        )

    for project in projects:
        project_resources = {
            project["project_id"],
            *project["branch_resource_ids"],
            *project["worktree_resource_ids"],
        }
        project["accepted_workstream_ids"] = sorted(
            {
                workstream_id
                for resource_id in project_resources
                for workstream_id in accepted_by_resource.get(resource_id, [])
            }
        )

    dependency = (workstream_source or {}).get("dependencies", {})
    per_workstream = dependency.get("per_workstream", {})
    cycle_nodes = set(str(node) for node in dependency.get("cycle_nodes", []))
    for node in sorted(cycle_nodes):
        coverage.append(
            _coverage(
                "dependencies",
                "dependency_cycle_node",
                node,
                f"Dependency cycle membership prevents unlock scoring for {node}.",
                severity="danger",
            )
        )
    for invalid in dependency.get("invalid_assertions", []):
        coverage.append(
            _coverage(
                "dependencies",
                str(invalid.get("kind", "invalid_dependency")),
                str(invalid.get("source", "")),
                (
                    f"{invalid.get('kind', 'invalid_dependency')}:"
                    f"{invalid.get('source', '')}->{invalid.get('target', '')}"
                ),
                severity="danger",
            )
        )

    workstream_items: dict[str, dict[str, Any]] = {}
    quiet_work: list[dict[str, Any]] = []
    quiet_workstream_ids = {
        workstream_id
        for workstream_id, row in workstream_by_id.items()
        if str(row.get("lifecycle_state", "")) in _QUIET_STATES | TERMINAL_STATES
    }
    for focus in (workstream_source or {}).get("focus_queue", []):
        workstream_id = str(focus.get("workstream_id", ""))
        if workstream_id in ambiguous_workstream_ids:
            continue
        source_row = workstream_by_id.get(workstream_id, {})
        lifecycle = str(focus.get("lifecycle_state", source_row.get("lifecycle_state", "")))
        priority = int(focus.get("priority", 0))
        if lifecycle in _QUIET_STATES | TERMINAL_STATES or priority <= 0:
            quiet_workstream_ids.add(workstream_id)
            if lifecycle not in TERMINAL_STATES:
                quiet_work.append(
                    {
                        "workstream_id": workstream_id,
                        "label": str(focus.get("idea_text", "")),
                        "lifecycle_state": lifecycle,
                        "reason": "; ".join(
                            str(reason) for reason in focus.get("suppressed_reasons", [])
                        )
                        or "No current attention trigger.",
                    }
                )
            continue
        dep = per_workstream.get(workstream_id, {})
        blocking_count = 0 if workstream_id in cycle_nodes else int(dep.get("blocking_count", 0))
        evidence = _empty_evidence()
        evidence["workstream"] = {
            "trigger_kind": str(focus.get("trigger_kind", "")),
            "trigger_signature": str(focus.get("trigger_signature", "")),
            "tier": str(focus.get("tier", "")),
            "needs_human_decision": bool(source_row.get("needs_human_decision"))
            and not bool(source_row.get("conflict_resolved")),
        }
        item = _finish_item(
            {
                "attention_id": stable_id(
                    "portfolio-cockpit-attention", "workstream", workstream_id
                ),
                "source": "workstreams",
                "band": _workstream_band(
                    focus,
                    evidence["workstream"]["needs_human_decision"],
                    blocking_count,
                ),
                "source_local_priorities": {"git": 0, "workstreams": priority},
                "blocking_count": blocking_count,
                "inactive_days": focus.get("inactive_days")
                if isinstance(focus.get("inactive_days"), int)
                else None,
                "project_id": "",
                "project_name": "",
                "workstream_id": workstream_id,
                "label": str(focus.get("idea_text", "")),
                "lifecycle_state": lifecycle,
                "reasons": list(focus.get("reasons", [])),
                "next_action": str(focus.get("next_action", ""))
                or "Review this workstream and record one intentional next state.",
                "resource_ids": accepted_resources_by_workstream.get(workstream_id, []),
                "evidence": evidence,
            }
        )
        workstream_items[workstream_id] = item

    git_items: list[dict[str, Any]] = []
    if git_source:
        for source_item in git_source.get("attention_queue", []):
            resource_ids = _resource_ids_for_git_item(source_item, resource_map)
            evidence = _empty_evidence()
            source_evidence = source_item.get("evidence", {})
            evidence["git"] = {
                "dirty": source_evidence.get("dirty"),
                "changed_path_count": int(source_evidence.get("changed_path_count", 0)),
                "ahead": int(source_evidence.get("ahead", 0)),
                "behind": int(source_evidence.get("behind", 0)),
            }
            item = _finish_item(
                {
                    "attention_id": stable_id(
                        "portfolio-cockpit-attention",
                        "git",
                        str(source_item.get("project_id", "")),
                        str(source_item.get("branch", "")),
                        str(source_item.get("worktree_path", "")),
                    ),
                    "source": "git",
                    "band": _git_band(source_item),
                    "source_local_priorities": {
                        "git": int(source_item.get("priority", 0)),
                        "workstreams": 0,
                    },
                    "blocking_count": 0,
                    "inactive_days": source_item.get("inactive_days")
                    if isinstance(source_item.get("inactive_days"), int)
                    else None,
                    "project_id": str(source_item.get("project_id", "")),
                    "project_name": str(source_item.get("project_name", "")),
                    "workstream_id": "",
                    "label": (
                        f"{source_item.get('project_name', '')} / {source_item.get('branch', '')}"
                    ),
                    "lifecycle_state": "",
                    "reasons": list(source_item.get("reasons", [])),
                    "next_action": str(source_item.get("next_action", "")),
                    "resource_ids": resource_ids,
                    "evidence": evidence,
                }
            )
            specific_resource_ids = [
                resource_id
                for resource_id in resource_ids
                if resource_map.get(resource_id, {}).get("resource_kind") in {"branch", "worktree"}
            ]
            identity_resource_ids = specific_resource_ids or resource_ids
            owner_sets = [
                set(accepted_by_resource.get(resource_id, []))
                for resource_id in identity_resource_ids
            ]
            owner_union = set().union(*owner_sets) if owner_sets else set()
            common_owners = set.intersection(*owner_sets) if owner_sets else set()
            matched_workstreams = sorted(common_owners)
            if len(owner_union) > 1:
                coverage.append(
                    _coverage(
                        "bindings",
                        "multiple_workstreams_for_observed_attention",
                        item["attention_id"],
                        "More than one exact accepted workstream binding covers one Git attention item.",
                        severity="danger",
                    )
                )
            elif len(matched_workstreams) == 1:
                workstream_id = matched_workstreams[0]
                source_row = workstream_by_id.get(workstream_id, {})
                item["workstream_id"] = workstream_id
                item["lifecycle_state"] = str(source_row.get("lifecycle_state", ""))
                item["evidence"]["workstream"]["needs_human_decision"] = bool(
                    source_row.get("needs_human_decision")
                ) and not bool(source_row.get("conflict_resolved"))
                if workstream_id in quiet_workstream_ids and item["band"] != "integrity_unknown":
                    continue
                if workstream_id in workstream_items:
                    workstream_items[workstream_id] = _merge_item(
                        workstream_items[workstream_id], item
                    )
                    continue
                item["source"] = "joined"
                item["label"] = str(source_row.get("idea_text", item["label"]))
                item["fingerprint"] = _item_fingerprint(item)
            else:
                coverage.append(
                    _coverage(
                        "bindings",
                        "unassigned_observed_attention",
                        item["attention_id"],
                        "Observed Git work needs attention but has no exact accepted workstream binding.",
                        severity="info",
                    )
                )
            git_items.append(item)

    unknowns = [row for row in coverage if row["severity"] in {"warning", "danger"}]
    candidates = [*workstream_items.values(), *git_items]
    candidates.extend(_system_attention(row) for row in unknowns)
    # A duplicated coverage diagnosis is noise, so collapse exact candidate identity.
    candidates_by_id = {item["attention_id"]: item for item in candidates}
    attention_queue = sorted(candidates_by_id.values(), key=_attention_sort_key)
    today = attention_queue[: policy.today_limit]
    selected_ids = {item["attention_id"] for item in today}
    for item in attention_queue:
        item["selected_today"] = item["attention_id"] in selected_ids
        item["fingerprint"] = _item_fingerprint(item)

    unlock_frontier = []
    for row in dependency.get("bottlenecks", []):
        workstream_id = str(row.get("workstream_id", ""))
        if workstream_id in cycle_nodes or workstream_id in ambiguous_workstream_ids:
            continue
        source_row = workstream_by_id.get(workstream_id, {})
        unlock_frontier.append(
            {
                "workstream_id": workstream_id,
                "label": str(source_row.get("idea_text", "")),
                "blocking_count": int(row.get("blocking_count", 0)),
                "blocks_directly": sorted(str(value) for value in row.get("blocks_directly", [])),
            }
        )

    related_work: list[dict[str, Any]] = []
    for project in projects:
        for related in project["related_projects"]:
            related_work.append(
                {
                    "source_project_id": project["project_id"],
                    "target_project_id": str(related.get("project_id", "")),
                    "target_project_name": str(related.get("project_name", "")),
                    "score": float(related.get("score", 0.0)),
                    "status": str(related.get("status", "generated_candidate")),
                }
            )
    related_work.sort(
        key=lambda row: (
            row["source_project_id"],
            -row["score"],
            row["target_project_id"],
        )
    )

    board = {
        state_name: [
            deepcopy(row)
            for row in (workstream_source or {}).get("board", {}).get(state_name, [])
            if str(row.get("workstream_id", "")) not in ambiguous_workstream_ids
        ]
        for state_name in LIFECYCLE_STATES
    }
    sources_ready = all(
        descriptor["status"] == "observed" and descriptor["freshness"] == "current"
        for descriptor in sources.values()
    )
    all_clear = sources_ready and not attention_queue and not unknowns
    status = "generated_candidate" if sources_ready else "partial_candidate"
    lanes = {
        "human_gates": [item for item in attention_queue if item["band"] == "human_decision"],
        "dirty_worktrees": [item for item in attention_queue if item["band"] == "dirty_recovery"],
        "neglected_work": [
            item
            for item in attention_queue
            if item["band"] in {"related_active_neglect", "weekly_maintenance"}
        ],
        "unlock_frontier": unlock_frontier,
        "related_work": related_work,
        "quiet_work": sorted(
            quiet_work, key=lambda row: (row["lifecycle_state"], row["workstream_id"])
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed.isoformat(),
        "status": status,
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "selection_policy": {
            "policy_id": SELECTION_POLICY_ID,
            "methodology_ref": METHODOLOGY_REF,
            "today_limit": policy.today_limit,
            "fresh_after_hours": policy.fresh_after_hours,
            "bands": list(ATTENTION_BANDS),
            "tie_breakers": [
                "source_local_priority_desc",
                "accepted_blocking_count_desc",
                "inactive_days_desc",
                "attention_id_asc",
            ],
        },
        "sources": sources,
        "summary": {
            "project_count": len(projects),
            "branch_count": sum(
                1 for row in resource_map.values() if row["resource_kind"] == "branch"
            ),
            "worktree_count": sum(
                1 for row in resource_map.values() if row["resource_kind"] == "worktree"
            ),
            "workstream_count": len(projected_workstreams),
            "attention_item_count": len(attention_queue),
            "today_item_count": len(today),
            "unknown_count": len(unknowns),
            "unassigned_attention_count": sum(
                1 for row in coverage if row["kind"] == "unassigned_observed_attention"
            ),
            "all_clear": all_clear,
        },
        "today": today,
        "attention_queue": attention_queue,
        "lanes": lanes,
        "board": board,
        "projects": projects,
        "workstreams": projected_workstreams,
        "resources": sorted(resource_map.values(), key=lambda row: row["resource_id"]),
        "bindings": sorted(
            bindings, key=lambda row: (row["workstream_id"], row["binding_id"], row["ref"])
        ),
        "coverage": coverage,
        "unknowns": unknowns,
        "source_refs": {name: descriptor["source_hash"] for name, descriptor in sources.items()},
    }


_STYLE = """
:root{color-scheme:dark;--bg:#071016;--panel:#0d1d25;--line:#24404b;--text:#f4f7f7;--muted:#9fb3ba;--mint:#78e0bd;--amber:#ffc96f;--danger:#ff8d83}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 80% 0,#143743 0,transparent 38%),var(--bg);color:var(--text);font:15px/1.55 ui-sans-serif,system-ui,sans-serif}
a.skip{position:absolute;left:-999px;top:8px;background:#fff;color:#000;padding:10px;z-index:2}a.skip:focus{left:8px}.shell{width:min(1400px,94vw);margin:auto;padding:46px 0 80px}
.section-nav{position:sticky;top:0;z-index:1;display:flex;flex-wrap:wrap;gap:8px;padding:10px 0;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(10px)}.section-nav a{color:var(--mint);border:1px solid var(--line);border-radius:999px;padding:.35rem .7rem;text-decoration:none;font-size:.82rem}.section-nav a:hover{background:var(--panel)}
.eyebrow{text-transform:uppercase;letter-spacing:.13em;color:var(--mint);font-size:.72rem;font-weight:800}h1{font-size:clamp(2.4rem,6vw,5.7rem);line-height:.9;max-width:950px;margin:.3rem 0 1rem}h2{margin-top:3rem}h3{margin:.25rem 0}.muted{color:var(--muted);max-width:900px}
.stats,.today,.sources{display:grid;gap:14px}.stats{grid-template-columns:repeat(6,minmax(120px,1fr));margin:28px 0}.today{grid-template-columns:repeat(3,1fr)}.sources{grid-template-columns:repeat(2,1fr)}
.card,.stat,.table-wrap{background:color-mix(in srgb,var(--panel) 94%,transparent);border:1px solid var(--line);border-radius:17px;box-shadow:0 20px 55px #0004}.card,.stat{padding:18px}.stat strong{display:block;font-size:1.9rem}.stat span,.meta{color:var(--muted)}
.badge{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:.2rem .6rem;font-size:.74rem}.danger{color:var(--danger)}.warning{color:var(--amber)}code{color:#b5e4d4;overflow-wrap:anywhere}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}caption{text-align:left;font-weight:700;padding:14px}th,td{padding:12px 14px;border-top:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted);font-size:.74rem;text-transform:uppercase;letter-spacing:.08em}
footer{margin-top:48px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted)}:focus-visible{outline:3px solid var(--amber);outline-offset:3px}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media(max-width:950px){.stats{grid-template-columns:repeat(3,1fr)}.today{grid-template-columns:1fr}.sources{grid-template-columns:1fr}}@media(max-width:560px){.stats{grid-template-columns:repeat(2,1fr)}.shell{padding-top:28px}}
""".strip()


def _csp() -> str:
    digest = base64.b64encode(hashlib.sha256(_STYLE.encode("utf-8")).digest()).decode("ascii")
    return (
        "default-src 'none'; "
        f"style-src 'sha256-{digest}'; "
        "img-src 'none'; connect-src 'none'; script-src 'none'; "
        "object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
    )


def _attention_cards(items: list[dict[str, Any]], *, all_clear: bool) -> str:
    if not items:
        message = (
            "Both sources are current and no attention trigger fired."
            if all_clear
            else "No ranked item is available, but source coverage is incomplete or unknown."
        )
        return (
            '<article class="card"><div class="eyebrow">Current state</div>'
            f"<h3>{'All clear' if all_clear else 'Evidence incomplete'}</h3>"
            f"<p>{escape(message)}</p></article>"
        )
    cards: list[str] = []
    for item in items:
        reasons = " &middot; ".join(escape(reason.replace("_", " ")) for reason in item["reasons"])
        cards.append(
            '<article class="card">'
            f'<div class="eyebrow">{escape(item["band"].replace("_", " "))} &middot; '
            f"{escape(item['source'])}</div>"
            f"<h3>{escape(item['label'])}</h3>"
            f"<p>{reasons}</p><p>{escape(item['next_action'])}</p>"
            f'<span class="badge">Git {item["source_local_priorities"]["git"]}</span> '
            f'<span class="badge">Workstream {item["source_local_priorities"]["workstreams"]}</span>'
            "</article>"
        )
    return "".join(cards)


def portfolio_cockpit_html(cockpit: dict[str, Any]) -> str:
    """Render a script-free local cockpit with escaped candidate metadata."""

    summary = cockpit["summary"]
    source_cards = "".join(
        (
            '<article class="card">'
            f'<div class="eyebrow">{escape(name)}</div>'
            f"<h3>{escape(source['status'])} / {escape(source['freshness'])}</h3>"
            f'<p class="meta">As of {escape(source["generated_at"] or "unknown")}</p>'
            f"<p>{escape('; '.join(source['problems']) or 'No source problems reported.')}</p>"
            "</article>"
        )
        for name, source in cockpit["sources"].items()
    )
    queue_rows = "".join(
        (
            "<tr>"
            f'<td><span class="badge">{escape(item["band"].replace("_", " "))}</span></td>'
            f"<td>{escape(item['label'])}</td>"
            f"<td>{escape(item['source'])}</td>"
            f"<td>{escape(', '.join(item['reasons']))}</td>"
            f"<td>{escape(str(item['inactive_days']) if item['inactive_days'] is not None else 'unknown')}</td>"
            f"<td>{escape(item['next_action'])}</td>"
            "</tr>"
        )
        for item in cockpit["attention_queue"]
    )
    unknown_rows = "".join(
        (
            "<tr>"
            f'<td class="{escape(row["severity"])}">{escape(row["severity"])}</td>'
            f"<td>{escape(row['source'])}</td>"
            f"<td>{escape(row['kind'].replace('_', ' '))}</td>"
            f"<td>{escape(row['note'])}</td>"
            "</tr>"
        )
        for row in cockpit["unknowns"]
    )
    if not queue_rows:
        queue_rows = '<tr><td colspan="6">No ranked attention items.</td></tr>'
    if not unknown_rows:
        unknown_rows = '<tr><td colspan="4">No unresolved evidence gaps.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="{escape(_csp(), quote=True)}">
  <title>DAD Portfolio Cockpit</title>
  <style>{_STYLE}</style>
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<main id="main" class="shell">
  <div class="eyebrow">DAD &middot; Personal project operating system</div>
  <h1>See the whole field. Choose only three.</h1>
  <p class="muted">One deterministic view of observed Git work, creative workstreams, human decisions, and accepted dependency evidence. No control on this page can execute an action.</p>
  <nav class="section-nav" aria-label="Cockpit sections">
    <a href="#today">Today</a><a href="#sources">Source health</a><a href="#queue">Full queue</a><a href="#evidence">Evidence gaps</a>
  </nav>
  <section class="stats" aria-label="Portfolio totals">
    <div class="stat"><strong>{summary["project_count"]}</strong><span>projects</span></div>
    <div class="stat"><strong>{summary["branch_count"]}</strong><span>branches</span></div>
    <div class="stat"><strong>{summary["worktree_count"]}</strong><span>worktrees</span></div>
    <div class="stat"><strong>{summary["workstream_count"]}</strong><span>workstreams</span></div>
    <div class="stat"><strong>{summary["today_item_count"]}</strong><span>Today</span></div>
    <div class="stat"><strong>{summary["unknown_count"]}</strong><span>unknowns</span></div>
  </section>
  <h2 id="today">Today</h2>
  <section class="today" aria-label="Today attention items">{_attention_cards(cockpit["today"], all_clear=summary["all_clear"])}</section>
  <h2 id="sources">Source health</h2>
  <section class="sources" aria-label="Source health">{source_cards}</section>
  <h2 id="queue">Full attention queue</h2>
  <div class="table-wrap"><table>
    <caption>Deterministic display order; source priorities are not a composite value score.</caption>
    <thead><tr><th scope="col">Band</th><th scope="col">Work</th><th scope="col">Source</th><th scope="col">Why</th><th scope="col">Idle days</th><th scope="col">Suggested next action</th></tr></thead>
    <tbody>{queue_rows}</tbody>
  </table></div>
  <h2 id="evidence">Evidence gaps</h2>
  <div class="table-wrap"><table>
    <caption>Unknown, stale, invalid, or unresolved evidence that prevents false confidence.</caption>
    <thead><tr><th scope="col">Severity</th><th scope="col">Source</th><th scope="col">Kind</th><th scope="col">Explanation</th></tr></thead>
    <tbody>{unknown_rows}</tbody>
  </table></div>
  <footer>Generated {escape(cockpit["generated_at"])}. {escape(cockpit["authority_boundary"])}</footer>
</main>
</body>
</html>
"""


def _cockpit_today_fingerprints(cockpit: dict[str, Any]) -> list[str]:
    return [
        str(item.get("fingerprint", ""))
        for item in cockpit.get("today", [])
        if isinstance(item, dict)
    ]


def write_portfolio_cockpit_outputs(hub_root: Path, cockpit: dict[str, Any]) -> dict[str, Any]:
    validation_problems = _schema_validation_problems(cockpit, hub_root, "portfolio_cockpit")
    if validation_problems:
        raise ValueError("Invalid portfolio cockpit projection: " + "; ".join(validation_problems))

    base = data_path(hub_root, "central_reports") / "portfolio_os"
    json_path = base / "cockpit.json"
    html_path = base / "cockpit.html"
    previous_fingerprints: list[str] = []
    if json_path.exists():
        try:
            previous = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(previous, dict):
                previous_fingerprints = _cockpit_today_fingerprints(previous)
        except (OSError, json.JSONDecodeError):
            previous_fingerprints = []

    current_fingerprints = _cockpit_today_fingerprints(cockpit)
    # JSON is the authoritative change checkpoint. Publish HTML first so an
    # HTML/OneDrive failure cannot consume the Today change edge before retry.
    atomic_write_text(html_path, portfolio_cockpit_html(cockpit))
    atomic_write_text(json_path, json_dumps(cockpit, pretty=True) + "\n")
    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "status": cockpit["status"],
        "summary": cockpit["summary"],
        "today": cockpit["today"],
        "today_changed": current_fingerprints != previous_fingerprints,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "generated_at": cockpit["generated_at"],
    }


__all__ = [
    "ATTENTION_BANDS",
    "AUTHORITY_BOUNDARY",
    "CockpitSettings",
    "SCHEMA_VERSION",
    "SELECTION_POLICY_ID",
    "branch_resource_id",
    "build_portfolio_cockpit",
    "portfolio_cockpit_html",
    "worktree_resource_id",
    "write_portfolio_cockpit_outputs",
]
