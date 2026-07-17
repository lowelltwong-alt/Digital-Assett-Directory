from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pathspec
import yaml
import re


SCHEMA_VERSION = "dad.ci_module_boundaries.v1"
CAPABILITY_ID = "dad:capability:ci-module-boundary-governance"
CAPABILITY_REVISION = "0.1.0"
LANES = {"ci_contract", "module", "integration", "release", "scheduled_full_regression"}
PATH_EDGE_TYPES = {"code", "contract", "authoritative_input"}
EVENTS = {
    "pull_request",
    "push_default_branch",
    "push_all_branches",
    "workflow_dispatch",
    "workflow_call",
    "schedule",
    "release",
}
ORDINARY_EVENTS = {"pull_request", "push_default_branch", "push_all_branches"}


class _Yaml12SafeLoader(yaml.SafeLoader):
    pass


for first_char, resolvers in list(_Yaml12SafeLoader.yaml_implicit_resolvers.items()):
    _Yaml12SafeLoader.yaml_implicit_resolvers[first_char] = [
        item for item in resolvers if item[0] != "tag:yaml.org,2002:bool"
    ]
_Yaml12SafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


@dataclass(frozen=True)
class Change:
    status: str
    path: str
    old_path: str = ""

    @property
    def paths(self) -> tuple[str, ...]:
        values = [self.old_path, self.path] if self.old_path else [self.path]
        return tuple(_normalize_path(value) for value in values if value)


def _normalize_path(value: str) -> str:
    path = value.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    while "//" in path:
        path = path.replace("//", "/")
    return path.rstrip("/")


def _matches(path: str, patterns: Iterable[str]) -> bool:
    lines = [_normalize_path(pattern) for pattern in patterns if str(pattern).strip()]
    return bool(lines) and pathspec.PathSpec.from_lines("gitwildmatch", lines).match_file(path)


def load_manifest(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    payload = (
        json.loads(raw)
        if path.suffix.lower() == ".json"
        else yaml.load(raw, Loader=_Yaml12SafeLoader)
    )
    if not isinstance(payload, dict):
        raise ValueError("CI module-boundary manifest must be an object")
    return payload


def parse_changes(lines: Iterable[str]) -> list[Change]:
    changes: list[Change] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) == 1:
            changes.append(Change("M", _normalize_path(parts[0])))
        elif parts[0].startswith(("R", "C")) and len(parts) >= 3:
            changes.append(Change(parts[0], _normalize_path(parts[2]), _normalize_path(parts[1])))
        elif len(parts) >= 2:
            changes.append(Change(parts[0], _normalize_path(parts[1])))
        else:
            raise ValueError(f"Unsupported change line: {line}")
    return changes


def scope_digest(manifest: dict[str, Any]) -> str:
    scope = {
        "capability_revision": manifest.get("capability_revision"),
        "repository": manifest.get("repository", {}),
        "workflow_paths": manifest.get("workflow_paths", []),
        "modules": manifest.get("modules", []),
        "dependencies": manifest.get("dependencies", []),
        "suites": manifest.get("suites", []),
        "workflows": manifest.get("workflows", []),
        "generated_artifacts": manifest.get("generated_artifacts", []),
    }
    canonical = json.dumps(scope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _diagnostic(code: str, message: str, *, severity: str = "error", path: str = "") -> dict[str, str]:
    result = {"code": code, "severity": severity, "message": message}
    if path:
        result["path"] = path
    return result


def _valid_exception(exception: dict[str, Any], *, today: date) -> bool:
    required = (
        "owner",
        "reason",
        "expires_on",
        "reviewed_by",
        "reviewed_at",
        "review_ref",
        "diagnostic_scopes",
    )
    if not all(str(exception.get(field, "")).strip() for field in required):
        return False
    try:
        expiry = date.fromisoformat(str(exception["expires_on"]))
        reviewed_at = datetime.fromisoformat(str(exception["reviewed_at"]).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (
        expiry >= today
        and reviewed_at.tzinfo is not None
        and reviewed_at.date() <= today
        and isinstance(exception.get("diagnostic_scopes"), list)
        and bool(exception["diagnostic_scopes"])
    )


def _apply_exceptions(
    diagnostics: list[dict[str, str]],
    exceptions: list[dict[str, Any]],
    *,
    today: date,
    report_invalid: bool = True,
) -> list[dict[str, str]]:
    valid_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for exception in exceptions:
        codes = exception.get("codes", [])
        if _valid_exception(exception, today=today):
            for code in codes:
                for scope in exception.get("diagnostic_scopes", []):
                    valid_by_key[(str(code), str(scope))] = exception
        elif report_invalid:
            diagnostics.append(
                _diagnostic(
                    "invalid_exception",
                    f"Exception {exception.get('exception_id', '<unnamed>')} is incomplete, expired, or unreviewed.",
                )
            )
    output: list[dict[str, str]] = []
    for item in diagnostics:
        exception = valid_by_key.get((item["code"], item.get("path", "")))
        if exception and item["code"] not in {"invalid_exception", "schema_version"}:
            output.append(
                {
                    **item,
                    "severity": "warning",
                    "exception_id": str(exception.get("exception_id", "")),
                    "message": item["message"] + " Suppressed by a current human-reviewed exception.",
                }
            )
        else:
            output.append(item)
    return output


def _pattern_is_broad(pattern: str, roots: list[str]) -> bool:
    normalized = _normalize_path(pattern)
    if normalized in {"*", "**", "**/*", "*/**", "."} or normalized.startswith("!"):
        return True
    static_prefix = normalized.split("*", 1)[0].rstrip("/")
    return not any(
        static_prefix == _normalize_path(root)
        or static_prefix.startswith(_normalize_path(root) + "/")
        for root in roots
    )


def validate_manifest(
    manifest: dict[str, Any],
    *,
    base_manifest: dict[str, Any] | None = None,
    observed_dependencies: Iterable[tuple[str, str]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    now = today or datetime.now(timezone.utc).date()
    diagnostics: list[dict[str, str]] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        diagnostics.append(_diagnostic("schema_version", f"schema_version must be {SCHEMA_VERSION}"))
    if manifest.get("capability_id") != CAPABILITY_ID:
        diagnostics.append(_diagnostic("capability_id", f"capability_id must be {CAPABILITY_ID}"))
    if manifest.get("capability_revision") != CAPABILITY_REVISION:
        diagnostics.append(
            _diagnostic("capability_revision", f"capability_revision must be supported revision {CAPABILITY_REVISION}")
        )

    modules = manifest.get("modules", [])
    module_ids = [str(item.get("module_id", "")) for item in modules]
    if not module_ids or any(not item for item in module_ids) or len(module_ids) != len(set(module_ids)):
        diagnostics.append(_diagnostic("module_identity", "Module IDs must be non-empty and unique."))
    module_by_id = {str(item.get("module_id", "")): item for item in modules}
    for module in modules:
        module_id = str(module.get("module_id", ""))
        roots = [_normalize_path(item) for item in module.get("roots", [])]
        if not roots or any("*" in root or not root for root in roots):
            diagnostics.append(_diagnostic("invalid_module_root", f"Module {module_id} needs concrete roots."))
        if not module.get("owners"):
            diagnostics.append(_diagnostic("missing_module_owner", f"Module {module_id} needs an owner."))
        seen_types = set()
        for trigger in module.get("triggers", []):
            edge_type = trigger.get("edge_type")
            seen_types.add(edge_type)
            if edge_type not in PATH_EDGE_TYPES:
                diagnostics.append(_diagnostic("invalid_path_edge", f"Module {module_id} has invalid edge {edge_type}."))
            paths = trigger.get("paths", [])
            if not paths:
                diagnostics.append(_diagnostic("empty_trigger", f"Module {module_id} has an empty {edge_type} trigger."))
            for pattern in paths:
                if _pattern_is_broad(str(pattern), roots):
                    diagnostics.append(
                        _diagnostic(
                            "overly_broad_glob",
                            f"Module {module_id} pattern {pattern!r} escapes its roots.",
                            path=f"module:{module_id}:{pattern}",
                        )
                    )
        if not PATH_EDGE_TYPES.issubset(seen_types):
            missing = sorted(PATH_EDGE_TYPES - seen_types)
            diagnostics.append(_diagnostic("missing_path_edge_type", f"Module {module_id} lacks {missing}."))

    dependencies = manifest.get("dependencies", [])
    declared_edges: set[tuple[str, str]] = set()
    declared_edge_ids: dict[str, tuple[str, str]] = {}
    for edge in dependencies:
        edge_id = str(edge.get("edge_id", ""))
        upstream, downstream = str(edge.get("from", "")), str(edge.get("to", ""))
        if not edge_id or edge_id in declared_edge_ids:
            diagnostics.append(_diagnostic("dependency_edge_identity", "Dependency edge IDs must be non-empty and unique."))
        declared_edge_ids[edge_id] = (upstream, downstream)
        if edge.get("edge_type") != "direct_dependent":
            diagnostics.append(_diagnostic("invalid_dependency_edge", "Dependency edge_type must be direct_dependent."))
        if upstream not in module_by_id or downstream not in module_by_id or upstream == downstream:
            diagnostics.append(_diagnostic("invalid_dependency_endpoint", f"Invalid edge {upstream}->{downstream}."))
        if not edge.get("on") or not set(edge.get("on", [])).issubset(PATH_EDGE_TYPES):
            diagnostics.append(_diagnostic("invalid_dependency_trigger", f"Edge {upstream}->{downstream} needs valid on types."))
        declared_edges.add((upstream, downstream))

    graph: dict[str, set[str]] = {module_id: set() for module_id in module_ids}
    for upstream, downstream in declared_edges:
        if upstream in graph and downstream in graph:
            graph[upstream].add(downstream)
    visiting: set[str] = set()
    visited: set[str] = set()

    def has_cycle(module_id: str) -> bool:
        if module_id in visiting:
            return True
        if module_id in visited:
            return False
        visiting.add(module_id)
        cyclic = any(has_cycle(child) for child in graph.get(module_id, set()))
        visiting.remove(module_id)
        visited.add(module_id)
        return cyclic

    if any(has_cycle(module_id) for module_id in module_ids if module_id not in visited):
        diagnostics.append(_diagnostic("dependency_cycle", "Direct-dependent edges must form an acyclic trigger graph."))

    if observed_dependencies is None:
        dependency_coverage = "coverage_unavailable"
    else:
        dependency_coverage = "observed_edges_compared"
        for upstream, downstream in observed_dependencies:
            if (upstream, downstream) not in declared_edges:
                diagnostics.append(
                    _diagnostic("missing_dependency_edge", f"Observed dependency {upstream}->{downstream} is undeclared.")
                )

    suites = manifest.get("suites", [])
    suite_ids = [str(item.get("suite_id", "")) for item in suites]
    if not suite_ids or len(suite_ids) != len(set(suite_ids)):
        diagnostics.append(_diagnostic("suite_identity", "Suite IDs must be non-empty and unique."))
    contract_suites = [item for item in suites if item.get("lane") == "ci_contract"]
    if not contract_suites:
        diagnostics.append(_diagnostic("missing_contract_lane", "At least one ci_contract suite is required."))
    for suite in suites:
        lane = suite.get("lane")
        if lane not in LANES:
            diagnostics.append(_diagnostic("invalid_lane", f"Suite {suite.get('suite_id')} has invalid lane {lane}."))
            continue
        if suite.get("scope") is None:
            diagnostics.append(_diagnostic("missing_suite_scope", f"Suite {suite.get('suite_id')} needs explicit scope."))
        scope_modules = suite.get("scope_modules", [])
        if any(module not in module_by_id for module in scope_modules):
            diagnostics.append(_diagnostic("unknown_suite_module", f"Suite {suite.get('suite_id')} has unknown modules."))
        if lane == "module" and (suite.get("scope") == "repository" or len(scope_modules) != 1):
            diagnostics.append(_diagnostic("repository_wide_module_suite", f"Module suite {suite.get('suite_id')} must own one module."))
        if lane in {"integration", "release"}:
            if len(scope_modules) < 2 or not suite.get("dependency_edges"):
                diagnostics.append(
                    _diagnostic("unjustified_cross_module_suite", f"{lane} suite {suite.get('suite_id')} needs explicit scope and edges.")
                )
            for edge_id in suite.get("dependency_edges", []):
                endpoints = declared_edge_ids.get(str(edge_id))
                if endpoints is None:
                    diagnostics.append(
                        _diagnostic("unknown_suite_dependency_edge", f"Suite {suite.get('suite_id')} references unknown edge {edge_id}.")
                    )
                elif not set(endpoints).issubset(set(scope_modules)):
                    diagnostics.append(
                        _diagnostic("suite_dependency_outside_scope", f"Suite {suite.get('suite_id')} edge {edge_id} escapes its declared modules.")
                    )
        if lane == "scheduled_full_regression" and set(suite.get("events", [])) - {"schedule", "workflow_dispatch"}:
            diagnostics.append(
                _diagnostic("scheduled_lane_on_pr", f"Scheduled suite {suite.get('suite_id')} cannot run on ordinary PR/push.")
            )

    workflows = manifest.get("workflows", [])
    workflow_ids = [str(item.get("workflow_id", "")) for item in workflows]
    provider_paths = [_normalize_path(str(item.get("provider_path", ""))) for item in workflows]
    if any(not item for item in workflow_ids) or len(workflow_ids) != len(set(workflow_ids)):
        diagnostics.append(_diagnostic("workflow_identity", "Workflow IDs must be non-empty and unique."))
    if any(not item for item in provider_paths) or len(provider_paths) != len(set(provider_paths)):
        diagnostics.append(_diagnostic("workflow_provider_path_identity", "Workflow provider paths must be non-empty and unique."))
    for workflow in workflows:
        events = set(workflow.get("events", []))
        if not events or not events.issubset(EVENTS):
            diagnostics.append(_diagnostic("invalid_workflow_event", f"Workflow {workflow.get('workflow_id')} has invalid events."))
        if "pull_request" in events and "push_all_branches" in events:
            diagnostics.append(
                _diagnostic("duplicate_push_pull_request", f"Workflow {workflow.get('workflow_id')} duplicates feature PR and push runs.")
            )
        if workflow.get("required_check") and not workflow.get("always_reports"):
            diagnostics.append(
                _diagnostic("required_check_deadlock", f"Required workflow {workflow.get('workflow_id')} must always report.")
            )
        if workflow.get("scope") == "repository" and workflow.get("lane") == "module":
            diagnostics.append(
                _diagnostic("repository_wide_module_workflow", f"Workflow {workflow.get('workflow_id')} is repository-wide without justification.")
            )
        if not str(workflow.get("workflow_contract_digest", "")).startswith("sha256:"):
            diagnostics.append(
                _diagnostic("missing_workflow_contract_digest", f"Workflow {workflow.get('workflow_id')} needs revision-bound adapter evidence.")
            )
        suite_job_map = workflow.get("suite_job_map", {})
        if any(suite_id not in set(suite_ids) for suite_id in suite_job_map):
            diagnostics.append(
                _diagnostic("unknown_selector_suite", f"Workflow {workflow.get('workflow_id')} maps an unknown suite.")
            )
        if workflow.get("required_check") and workflow.get("lane") == "ci_contract" and (
            not suite_job_map
            or not workflow.get("selector_job")
            or not workflow.get("required_aggregator_job")
        ):
            diagnostics.append(
                _diagnostic("missing_selector_job_map", f"Required selector {workflow.get('workflow_id')} needs an exact suite-to-job map.")
            )
        if suite_job_map:
            expected_job_ids = {
                str(workflow.get("selector_job", "")),
                str(workflow.get("required_aggregator_job", "")),
                *map(str, suite_job_map.values()),
            }
            if set(workflow.get("job_contract_digests", {})) != expected_job_ids:
                diagnostics.append(
                    _diagnostic("incomplete_job_contract_digests", f"Workflow {workflow.get('workflow_id')} must bind every selector, suite, and aggregator job exactly.")
                )
    if not any(
        workflow.get("lane") == "ci_contract"
        and workflow.get("always_reports")
        and "pull_request" in workflow.get("events", [])
        for workflow in workflows
    ):
        diagnostics.append(
            _diagnostic("missing_always_starting_selector", "An always-reporting PR ci_contract selector is required.")
        )
    if not any(workflow.get("lane") == "scheduled_full_regression" for workflow in workflows):
        diagnostics.append(_diagnostic("missing_scheduled_regression", "A separate scheduled full-regression workflow is required."))

    workflow_paths = manifest.get("workflow_paths", [])
    if not workflow_paths:
        diagnostics.append(_diagnostic("missing_workflow_paths", "Workflow files need a declared contract trigger."))

    generated = manifest.get("generated_artifacts", [])
    for item in generated:
        module = module_by_id.get(item.get("module_id"))
        authoritative_paths = {
            str(path)
            for trigger in (module or {}).get("triggers", [])
            if trigger.get("edge_type") == "authoritative_input"
            for path in trigger.get("paths", [])
        }
        if (
            module is None
            or not item.get("paths")
            or not item.get("authoritative_inputs")
            or not set(map(str, item.get("authoritative_inputs", []))).issubset(authoritative_paths)
        ):
            diagnostics.append(
                _diagnostic("invalid_generated_lineage", "Generated artifacts need a module, paths, and authoritative inputs.")
            )

    if base_manifest is not None and scope_digest(base_manifest) != scope_digest(manifest):
        diagnostics.append(
            _diagnostic(
                "scope_broadening",
                "Scope changed relative to the base manifest and needs reviewed exception evidence.",
                path="manifest:scope",
            )
        )

    diagnostics = _apply_exceptions(diagnostics, manifest.get("exceptions", []), today=now)
    errors = [item for item in diagnostics if item["severity"] == "error"]
    return {
        "status": "valid" if not errors else "invalid",
        "capability_id": CAPABILITY_ID,
        "capability_revision": CAPABILITY_REVISION,
        "scope_digest": scope_digest(manifest),
        "dependency_coverage": dependency_coverage,
        "diagnostics": diagnostics,
        "summary": {
            "errors": len(errors),
            "warnings": sum(item["severity"] == "warning" for item in diagnostics),
            "modules": len(modules),
            "suites": len(suites),
            "workflows": len(workflows),
        },
    }


def _module_trigger_map(manifest: dict[str, Any], path: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for module in manifest.get("modules", []):
        for trigger in module.get("triggers", []):
            if _matches(path, trigger.get("paths", [])):
                matches.append((module["module_id"], trigger["edge_type"]))
    return matches


def evaluate_changes(
    manifest: dict[str, Any],
    changes: Iterable[Change | str],
    *,
    event: str = "pull_request",
) -> dict[str, Any]:
    parsed = [item if isinstance(item, Change) else Change("M", _normalize_path(item)) for item in changes]
    selected_modules: set[str] = set()
    reasons: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    generated_only: list[str] = []
    contract_triggered = event in ORDINARY_EVENTS

    if event in {"schedule", "workflow_dispatch"}:
        selected = sorted(
            suite["suite_id"]
            for suite in manifest.get("suites", [])
            if suite.get("lane") == "scheduled_full_regression"
        )
        return {
            "status": "ok",
            "event": event,
            "selected_modules": [],
            "selected_suites": selected,
            "reasons": [{"kind": "scheduled_full_regression", "path": ""}],
            "diagnostics": [],
            "generated_artifacts_ignored": [],
        }

    for change in parsed:
        for path in change.paths:
            path_matched = False
            if _matches(path, manifest.get("workflow_paths", [])):
                contract_triggered = True
                path_matched = True
                reasons.append({"kind": "workflow_contract", "path": path})
            generated_matches = [
                item for item in manifest.get("generated_artifacts", []) if _matches(path, item.get("paths", []))
            ]
            if generated_matches:
                generated_only.append(path)
                path_matched = True
                reasons.append({"kind": "generated_artifact_ignored", "path": path})
                continue
            matches = _module_trigger_map(manifest, path)
            for module_id, edge_type in matches:
                selected_modules.add(module_id)
                reasons.append({"kind": edge_type, "module_id": module_id, "path": path})
                path_matched = True
            if not path_matched:
                diagnostics.append(_diagnostic("unowned_changed_path", f"Changed path {path} is not owned.", path=path))
                contract_triggered = True

    changed_types: dict[str, set[str]] = {}
    for reason in reasons:
        if reason["kind"] in PATH_EDGE_TYPES:
            changed_types.setdefault(reason["module_id"], set()).add(reason["kind"])
    frontier = [
        (module_id, edge_type)
        for module_id in sorted(selected_modules)
        for edge_type in sorted(changed_types.get(module_id, set()))
    ]
    while frontier:
        upstream, propagated_type = frontier.pop(0)
        for edge in manifest.get("dependencies", []):
            if edge.get("from") != upstream or propagated_type not in set(edge.get("on", [])):
                continue
            downstream = edge.get("to")
            downstream_types = changed_types.setdefault(downstream, set())
            if propagated_type in downstream_types:
                continue
            downstream_types.add(propagated_type)
            selected_modules.add(downstream)
            frontier.append((downstream, propagated_type))
            reasons.append(
                {
                    "kind": "direct_dependent",
                    "module_id": downstream,
                    "from_module_id": upstream,
                    "edge_type": propagated_type,
                    "path": "",
                }
            )

    selected_suites: set[str] = set()
    for suite in manifest.get("suites", []):
        lane = suite.get("lane")
        scope = set(suite.get("scope_modules", []))
        if lane == "ci_contract" and contract_triggered and event in set(suite.get("events", [])):
            selected_suites.add(suite["suite_id"])
        elif lane == "module" and scope & selected_modules and event in set(suite.get("events", [])):
            selected_suites.add(suite["suite_id"])
        elif (
            lane == "integration"
            and len(scope & selected_modules) >= 2
            and event in set(suite.get("events", []))
        ):
            selected_suites.add(suite["suite_id"])
        elif lane == "release" and event in set(suite.get("events", [])):
            selected_suites.add(suite["suite_id"])

    return {
        "status": "ok" if not diagnostics else "contract_failed",
        "event": event,
        "selected_modules": sorted(selected_modules),
        "selected_suites": sorted(selected_suites),
        "reasons": reasons,
        "diagnostics": diagnostics,
        "generated_artifacts_ignored": sorted(set(generated_only)),
    }


def build_metadata_only_adoption_audit(repo_root: Path) -> dict[str, Any]:
    audit_path = repo_root / "processed" / "enrollment" / "audit.jsonl"
    rows: list[dict[str, Any]] = []
    if audit_path.exists():
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        repo_id = str(row.get("repo_id", ""))
        event_type = row.get("event_type") or row.get("status")
        if repo_id and event_type in {"applied", "updated"}:
            latest[repo_id] = row
    digest = "sha256:" + hashlib.sha256(audit_path.read_bytes()).hexdigest() if audit_path.exists() else ""
    findings = []
    law_firm_ids = {
        repo_id
        for repo_id in latest
        if repo_id.startswith("lawfirm-os-")
    }
    for repo_id in sorted(latest):
        local_candidate = repo_id == "dad" and (repo_root / ".ci" / "module-boundaries.yaml").exists()
        codes = [
            "local_ci_contract_candidate_validation_required"
            if local_candidate
            else "local_ci_contract_audit_required"
        ]
        if repo_id != "dad":
            codes.append("module_manifest_not_evidenced")
        if repo_id in law_firm_ids:
            codes.append("multi_repo_dependency_manifest_candidate")
        findings.append(
            {
                "repo_id": repo_id,
                "audit_depth": "metadata_only",
                "manifest_status": "candidate_present_local" if local_candidate else "not_evidenced",
                "workflow_contents_read": 0,
                "source_mutations": 0,
                "finding_codes": codes,
                "recommended_patch": (
                    "multi-repo-law-firm-os" if repo_id in law_firm_ids else "monorepo"
                ),
                "human_review_required": True,
            }
        )
    return {
        "status": "ok",
        "schema_version": "dad.ci_module_boundary_adoption_audit.v1",
        "capability_id": CAPABILITY_ID,
        "capability_revision": CAPABILITY_REVISION,
        "authority_boundary": (
            "Metadata-only candidate findings. No downstream contents were read and no source repository was mutated."
        ),
        "enrollment_audit_sha256": digest,
        "repo_count": len(findings),
        "workflow_contents_read": 0,
        "source_mutations": 0,
        "coverage_limit": (
            "Enrollment metadata cannot prove workflow triggers, dependency completeness, required checks, or current heads."
        ),
        "findings": findings,
    }
