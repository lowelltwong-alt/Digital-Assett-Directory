"""GitHub Actions adapter validation for provider-neutral CI module boundaries."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .ci_module_boundaries import (
    _Yaml12SafeLoader,
    _apply_exceptions,
    _diagnostic,
    _normalize_path,
)


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_github_workflows(
    repo_root: Path, manifest: dict[str, Any], *, today: date | None = None
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    declared = {
        _normalize_path(str(item.get("provider_path", ""))): item
        for item in manifest.get("workflows", [])
        if item.get("provider_path")
    }
    workflow_dir = repo_root / ".github" / "workflows"
    actual_paths = (
        sorted(
            _normalize_path(str(path.relative_to(repo_root)))
            for path in workflow_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
        )
        if workflow_dir.exists()
        else []
    )
    for path in actual_paths:
        if path not in declared:
            diagnostics.append(
                _diagnostic("undeclared_module_workflow", f"Workflow {path} is undeclared.", path=path)
            )
            continue
        workflow = declared[path]
        payload = yaml.load((repo_root / path).read_text(encoding="utf-8"), Loader=_Yaml12SafeLoader)
        if _canonical_digest(payload) != workflow.get("workflow_contract_digest"):
            diagnostics.append(
                _diagnostic("workflow_contract_digest_drift", f"Workflow {path} differs from its reviewed adapter digest.", path=path)
            )
        on = payload.get("on", {}) if isinstance(payload, dict) else {}
        if isinstance(on, str):
            on = {on: None}
        if isinstance(on, list):
            on = {name: None for name in on}
        if not isinstance(on, dict):
            on = {}
        actual_events: set[str] = set()
        for event in ("pull_request", "schedule", "workflow_dispatch", "workflow_call", "release"):
            if event in on:
                actual_events.add(event)
        if "push" in on:
            push = on.get("push")
            branches = push.get("branches", []) if isinstance(push, dict) else []
            actual_events.add("push_default_branch" if branches else "push_all_branches")
            if branches and branches != [manifest.get("repository", {}).get("default_branch")]:
                diagnostics.append(
                    _diagnostic("push_default_branch_drift", f"Workflow {path} does not target the declared default branch.", path=path)
                )
        declared_events = set(workflow.get("events", []))
        if actual_events != declared_events:
            diagnostics.append(
                _diagnostic(
                    "workflow_event_drift",
                    f"Workflow {path} events {sorted(actual_events)} differ from declared {sorted(declared_events)}.",
                    path=path,
                )
            )
        if {"pull_request", "push_all_branches"}.issubset(actual_events):
            diagnostics.append(
                _diagnostic("duplicate_push_pull_request", f"Workflow {path} duplicates feature push and PR runs.", path=path)
            )
        ordinary_triggers = [on.get(name) for name in ("pull_request", "push") if name in on]
        has_path_filter = any(
            isinstance(value, dict) and ("paths" in value or "paths-ignore" in value)
            for value in ordinary_triggers
        )
        if workflow.get("required_check") and has_path_filter:
            diagnostics.append(
                _diagnostic("required_check_deadlock", f"Required workflow {path} can skip without reporting.", path=path)
            )
        if workflow.get("lane") == "module" and ordinary_triggers:
            diagnostics.append(
                _diagnostic(
                    "module_workflow_bypasses_selector",
                    f"Module workflow {path} must be called by the authoritative selector, not trigger directly.",
                    path=path,
                )
            )
        suite_job_map = workflow.get("suite_job_map", {})
        jobs = payload.get("jobs", {}) if isinstance(payload, dict) else {}
        for job_id, expected_digest in workflow.get("job_contract_digests", {}).items():
            if job_id not in jobs or _canonical_digest(jobs[job_id]) != expected_digest:
                diagnostics.append(
                    _diagnostic("job_contract_digest_drift", f"Workflow {path} job {job_id} differs from reviewed evidence.", path=path)
                )
        if suite_job_map:
            selector_job = str(workflow.get("selector_job", ""))
            aggregator_job = str(workflow.get("required_aggregator_job", ""))
            expected_jobs = set(map(str, suite_job_map.values()))
            if selector_job not in jobs or aggregator_job not in jobs or not expected_jobs.issubset(set(jobs)):
                diagnostics.append(
                    _diagnostic("selector_job_map_drift", f"Workflow {path} is missing declared selector, suite, or aggregator jobs.", path=path)
                )
            else:
                needs = jobs[aggregator_job].get("needs", [])
                if isinstance(needs, str):
                    needs = [needs]
                if set(needs) != ({selector_job} | expected_jobs):
                    diagnostics.append(
                        _diagnostic("required_aggregator_scope_drift", f"Workflow {path} aggregator dependencies differ from the exact reviewed suite set.", path=path)
                    )
    for path in sorted(set(declared) - set(actual_paths)):
        diagnostics.append(_diagnostic("declared_workflow_missing", f"Declared workflow {path} is missing.", path=path))
    return _apply_exceptions(
        diagnostics,
        manifest.get("exceptions", []),
        today=today or datetime.now(timezone.utc).date(),
        report_invalid=False,
    )
