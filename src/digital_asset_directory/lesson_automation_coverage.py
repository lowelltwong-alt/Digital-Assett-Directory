from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from .config import GitHubSource, LocalSource
from .ids import stable_id
from .models import AssetRecord, ScanCycleEventRecord
from .repo_buildout import build_repo_groups
from .transport import data_relative_path
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "lesson-automation-coverage-v0.1"
WEEKLY_ASSET_COVERAGE_VERSION = "weekly-asset-coverage-v0.2"
AUTHORITY_BOUNDARY = (
    "Generated coverage and scan-cycle guidance only. This command reads the current catalog, "
    "configuration metadata, and generated-output presence; it does not rescan source repos, read "
    "source file contents, call GitHub, call models, mutate downstream repos, install hooks, or "
    "promote candidate findings to truth."
)
WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY = (
    "Weekly asset coverage reads reviewed repo paths, recent Git path metadata, "
    "and repo-local DAD envelope metadata only. It does not read source file "
    "contents, call models, approve dependencies, mutate downstream repos, or "
    "promote candidate findings to truth."
)
WEEKLY_ASSET_COVERAGE_REPORT_JSON = "weekly_asset_coverage.json"
WEEKLY_ASSET_COVERAGE_REPORT_MD = "weekly_asset_coverage.md"
WEEKLY_ASSET_COVERAGE_SNAPSHOT = "weekly_asset_coverage_snapshot.jsonl"
WEEKLY_ASSET_COVERAGE_HISTORY = "weekly_asset_coverage_history.jsonl"

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{1,80}")
_GENERIC_PATH_TOKENS = {
    "apps",
    "build",
    "cache",
    "case",
    "cases",
    "config",
    "data",
    "docs",
    "generated",
    "json",
    "jsonl",
    "output",
    "outputs",
    "processed",
    "reports",
    "schema",
    "schemas",
    "script",
    "scripts",
    "source",
    "src",
    "test",
    "tests",
    "tools",
    "validate",
    "validation",
}
_SKIP_RECENT_PATH_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".venv/",
    "__pycache__/",
    "build/",
    "dist/",
    "node_modules/",
    "outputs/",
    "source/raw/",
)
_REPO_ENVELOPE_SOURCES = (
    (Path(".digital-asset") / "mail" / "outbox.jsonl", "mail_outbox", 1.0),
    (Path(".digital-asset") / "exceptions" / "outbox.jsonl", "exceptions_outbox", 1.0),
    (Path(".digital-asset") / "assets" / "index.jsonl", "asset_index", 1.0),
    (Path(".digital-asset") / "learning" / "events.jsonl", "learning_events", 0.8),
)
_SAFE_ENVELOPE_IDENTIFIER_FIELDS = (
    "mail_id",
    "event_id",
    "asset_id",
    "dedupe_key",
    "lesson_id",
    "exception_id",
    "message_type",
)
_SAFE_ENVELOPE_REF_FIELDS = (
    "asset_refs",
    "evidence_refs",
    "validation_refs",
    "fix_refs",
    "path_ref",
    "file_ref",
    "artifact_ref",
    "source_ref",
    "categories",
    "candidate_exception_labels",
    "context_tags",
)
_ENVELOPE_TIMESTAMP_FIELDS = ("created_at", "generated_at", "timestamp", "observed_at")

SURFACE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "surface_id": "repo_contract",
        "label": "Repo AI contract",
        "paths": ["AGENTS.md", "CLAUDE.md"],
        "weight": 14,
        "why": "Future agents need a repo-local operating contract before planning or editing.",
        "next_action": "Add or review an AGENTS.md/CLAUDE.md contract before deeper automation.",
    },
    {
        "surface_id": "ai_front_door",
        "label": "AI front door",
        "paths": ["AI_FRONT_DOOR.md"],
        "weight": 14,
        "why": "A single AI entrypoint prevents random-doc routing and stale memory reuse.",
        "next_action": "Add an AI_FRONT_DOOR.md or equivalent deterministic entrypoint.",
    },
    {
        "surface_id": "ai_toc",
        "label": "AI table of contents",
        "paths": ["AI_TABLE_OF_CONTENTS.md", "AI_TOC.md"],
        "weight": 10,
        "why": "TOC rows with descriptions, tags, and use-when triggers route agents to the right branch.",
        "next_action": "Add or upgrade an AI TOC with deterministic row shape.",
    },
    {
        "surface_id": "repo_learning_readme",
        "label": "Repo learning-loop README",
        "paths": [".digital-asset-directory/learning/README.md"],
        "weight": 12,
        "why": "Repo-local learning instructions tell future agents how to capture before/after lessons.",
        "next_action": "Human-approve files-only learning-loop installation for this repo.",
    },
    {
        "surface_id": "repo_learning_context_tags",
        "label": "Repo learning context tags",
        "paths": [".digital-asset-directory/learning/context-tags.yaml"],
        "weight": 8,
        "why": "Context tags keep lessons from being reused outside the conditions that made them true.",
        "next_action": "Install or review context-tags.yaml for repo-local learning events.",
    },
    {
        "surface_id": "repo_learning_events",
        "label": "Repo learning event log",
        "paths": [".digital-asset-directory/learning/events.jsonl"],
        "weight": 12,
        "why": "Append-only repo events create a pay-forward loop for asset use, failures, and reviews.",
        "next_action": "Start recording before_work, during_failure, after_work, and review events.",
    },
    {
        "surface_id": "dad_repo_config",
        "label": "DAD repo-local config",
        "paths": [".digital-asset-directory.yml", ".digital-asset-directory.yaml"],
        "weight": 8,
        "why": "Repo-local config can declare ownership, scope, sensitivity, and automation posture.",
        "next_action": "Add a repo-local DAD config only after its authority boundary is clear.",
    },
    {
        "surface_id": "governance_dependency_map",
        "label": "Governance dependency map",
        "paths": [
            "governance/GOVERNANCE_DEPENDENCY_MAP.yaml",
            "governance/governance_dependency_map.yaml",
            "GOVERNANCE_DEPENDENCY_MAP.yaml",
        ],
        "weight": 12,
        "why": "Cross-repo governance maps expose upstream/downstream dependencies and review gates.",
        "next_action": "Use the cross-repo governance dependency-map template if this repo has child mirrors.",
    },
    {
        "surface_id": "governance_mirror",
        "label": "Child governance mirror",
        "paths": [
            ".ai/control/governance_dependency_map_mirror.yaml",
            ".ai/control/GOVERNANCE_DEPENDENCY_MAP_MIRROR.yaml",
        ],
        "weight": 10,
        "why": "Child mirrors let a downstream repo disclose which upstream governance bundle it follows.",
        "next_action": "Add a mirror only for explicitly approved downstream repos.",
    },
)

SIGNAL_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "signal_family_id": "catalog_metadata",
        "label": "Catalog metadata and repo boundaries",
        "cycle_order": 1,
        "requires_human_approval": False,
        "why_next": "Baseline inventory is needed before higher-cost scans.",
        "next_action": "Use existing catalog metadata first; refresh only when source changes matter.",
    },
    {
        "signal_family_id": "priority_content_extracts",
        "label": "Priority content extracts",
        "cycle_order": 2,
        "requires_human_approval": True,
        "why_next": "Metadata-only scans cannot see formulas, workflow content, code comments, or dataflow.",
        "next_action": "After approval, run a bounded content pass for front doors, schemas, docs, tests, and governance files.",
    },
    {
        "signal_family_id": "repo_learning_events",
        "label": "Repo-local learning events",
        "cycle_order": 3,
        "requires_human_approval": True,
        "why_next": "Before/after learning events give the strongest future-agent reuse signal.",
        "next_action": "Install files-only learning loops in selected repos, then record events with context tags.",
    },
    {
        "signal_family_id": "governance_map_adoption",
        "label": "Cross-repo governance maps and mirrors",
        "cycle_order": 4,
        "requires_human_approval": True,
        "why_next": "Repo families need explicit upstream/downstream governance dependencies.",
        "next_action": "Review candidate repo families, then add maps/mirrors through normal repo changes.",
    },
    {
        "signal_family_id": "bounded_git_history",
        "label": "Bounded local git history and worktree archaeology",
        "cycle_order": 5,
        "requires_human_approval": True,
        "why_next": "Commit order, late validators, reverts, and repeated attempts reveal process lessons.",
        "next_action": "Run archaeology with bounded max repos and commits only after selecting target families.",
    },
    {
        "signal_family_id": "ci_and_release_artifacts",
        "label": "CI logs, release notes, and changelogs",
        "cycle_order": 6,
        "requires_human_approval": True,
        "why_next": "CI/release artifacts expose hidden failures, migrations, and compatibility promises.",
        "next_action": "Add a local-only artifact ingestion plan before reading CI logs or release outputs.",
    },
    {
        "signal_family_id": "github_pr_issue_metadata",
        "label": "GitHub PR, issue, and review metadata",
        "cycle_order": 7,
        "requires_human_approval": True,
        "why_next": "PR discussions and review threads capture why decisions changed, but require token and privacy review.",
        "next_action": "Keep deferred until a read-only token scope and privacy boundary are approved.",
    },
    {
        "signal_family_id": "private_source_public_safe_workflows",
        "label": "Private source workflows without row import",
        "cycle_order": 8,
        "requires_human_approval": True,
        "why_next": "Sensitive projects can teach reusable workflows without importing private records.",
        "next_action": "Use public-safe metadata-only sweeps for selected sensitive sources.",
    },
)


def _normalized(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/").lower()


def _repo_label(key: str) -> str:
    parts = [part for part in PurePosixPath(key.replace("\\", "/")).parts if part not in {"."}]
    return parts[-1] if parts else key


def _relative_path(logical_path: str, repo_key: str) -> str:
    logical = _normalized(logical_path)
    key = _normalized(repo_key)
    if logical == key:
        return ""
    prefix = f"{key}/"
    if logical.startswith(prefix):
        return logical[len(prefix) :]
    return logical


def _is_noise_repo(key: str, assets: list[AssetRecord]) -> bool:
    lowered = _normalized(key)
    if lowered.endswith("/.") or lowered in {"", "."}:
        return True
    noise_parts = {
        ".pytest-tmp-root",
        "_codex_worktrees",
        ".claude/worktrees",
        "/tmp/",
        "/temp/",
        "/node_modules/",
        "/.venv/",
        "/__pycache__/",
    }
    if any(part in lowered for part in noise_parts):
        return True
    return any(asset.metadata.get("instance_class") in {"temp", "worktree"} for asset in assets)


def _configured_source_for_repo(repo_key: str, local_sources: list[LocalSource]) -> LocalSource | None:
    normalized = _normalized(repo_key)
    candidates = sorted(local_sources, key=lambda item: len(item.path_alias), reverse=True)
    for source in candidates:
        alias = _normalized(source.path_alias)
        if normalized == alias or normalized.startswith(f"{alias}/"):
            return source
    return None


def _repo_surface_status(repo_key: str, assets: list[AssetRecord]) -> dict[str, Any]:
    repo_asset = next((asset for asset in assets if asset.asset_type == "repository"), None)
    relative_paths = {
        _relative_path(asset.logical_path, repo_key)
        for asset in assets
        if _relative_path(asset.logical_path, repo_key)
    }
    entrypoints = {
        _normalized(entrypoint)
        for asset in assets
        for entrypoint in (asset.entrypoints or [])
        if entrypoint
    }
    observed = relative_paths | entrypoints

    surfaces: list[dict[str, Any]] = []
    total_weight = sum(int(surface["weight"]) for surface in SURFACE_DEFINITIONS)
    hit_weight = 0
    for surface in SURFACE_DEFINITIONS:
        candidate_paths = {_normalized(path) for path in surface["paths"]}
        detected_paths = sorted(path for path in candidate_paths if path in observed)
        detected = bool(detected_paths)
        if detected:
            hit_weight += int(surface["weight"])
        surfaces.append(
            {
                "surface_id": surface["surface_id"],
                "label": surface["label"],
                "detected": detected,
                "detected_paths": detected_paths,
                "candidate_paths": sorted(candidate_paths),
                "why": surface["why"],
                "next_action": "" if detected else surface["next_action"],
            }
        )
    missing = [surface["surface_id"] for surface in surfaces if not surface["detected"]]
    flags: list[str] = []
    if "repo_learning_events" in missing:
        flags.append("learning_loop_missing")
    if "ai_front_door" in missing or "ai_toc" in missing:
        flags.append("ai_navigation_incomplete")
    if "repo_contract" in missing:
        flags.append("repo_contract_missing")
    if "governance_dependency_map" in missing and "governance_mirror" in missing:
        flags.append("governance_dependency_surface_missing")
    readiness = round(100 * hit_weight / total_weight, 1) if total_weight else 0.0
    if readiness >= 80:
        level = "learning_ready_or_nearly_ready"
    elif readiness >= 50:
        level = "partial_foundation"
    else:
        level = "needs_front_door_and_learning_loop_review"
    return {
        "repo_key": repo_key,
        "repo_label": repo_asset.title if repo_asset else _repo_label(repo_key),
        "repo_asset_id": repo_asset.asset_id if repo_asset else "",
        "asset_count": len(assets),
        "readiness_score": readiness,
        "readiness_level": level,
        "surfaces": surfaces,
        "missing_surface_ids": missing,
        "flags": flags,
        "sample_paths": sorted(relative_paths)[:12],
    }


def _source_summaries(local_sources: list[LocalSource], github_sources: list[GitHubSource]) -> dict[str, Any]:
    return {
        "local": [
            {
                "id": source.id,
                "path": str(source.path),
                "path_alias": source.path_alias,
                "enabled": source.enabled,
                "max_file_bytes": source.max_file_bytes,
                "scan_depth": "metadata_only" if source.max_file_bytes == 0 else "content_excerpt",
                "exclude_count": len(source.exclude),
            }
            for source in local_sources
        ],
        "github": [
            {
                "id": source.id,
                "owner": source.owner,
                "enabled": source.enabled,
                "content_mode": source.content_mode,
                "max_file_bytes": source.max_file_bytes,
            }
            for source in github_sources
        ],
    }


def _existing_output_status(repo_root: Path) -> dict[str, bool]:
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    paths = {
        "workflow_sweeps": reports_dir / "workflow_sweeps",
        "workflow_parts": learning_dir / "workflow_parts.jsonl",
        "manual_task_queue": reports_dir / "manual_task_queue.json",
        "template_library": reports_dir / "template_library.json",
        "priority_content_scope": reports_dir / "priority_content_extract_scope.json",
        "priority_content_observations": learning_dir / "priority_content_observations.jsonl",
        "priority_content_lesson_candidates": learning_dir
        / "priority_content_lesson_candidates.jsonl",
        "learning_rule_promotion_candidates": learning_dir
        / "learning_rule_promotion_candidates.jsonl",
        "lesson_automation_next_actions": reports_dir / "lesson_automation_next_actions.json",
        "lesson_automation_decision_template": learning_dir
        / "lesson_automation_action_decisions.jsonl",
        "lesson_automation_approval_packet": reports_dir
        / "lesson_automation_approval_packet.json",
        "lesson_automation_approval_impact": reports_dir
        / "lesson_automation_approval_impact.json",
        "lesson_automation_execution_plan": reports_dir
        / "lesson_automation_execution_plan.json",
        "archaeology": reports_dir / "worktree_archaeology.md",
        "root_cause_lessons": learning_dir / "counterfactual_lessons.jsonl",
        "semantic_evolution": learning_dir / "semantic_evolution_candidates.jsonl",
        "ci_release_artifact_scope": reports_dir / "ci_release_artifact_scope.json",
        "repo_learning_loop_install_scope": reports_dir
        / "repo_learning_loop_install_scope.json",
        "governance_map_adoption_scope": reports_dir
        / "governance_map_adoption_scope.json",
        "background_connections": learning_dir / "background_connection_candidates.jsonl",
        "repo_buildout_index": reports_dir / "repo_buildout" / "index.md",
        "repo_completion_dashboard": reports_dir / "repo_completion_dashboard.json",
        "repo_completion_wave_plan": reports_dir / "repo_completion_wave_plan.json",
        "repo_completion_proof_check": reports_dir / "repo_completion_proof_check.json",
        "public_safe_sweeps": reports_dir / "external_sweeps",
    }
    return {name: path.exists() for name, path in paths.items()}


def _signal_family_status(
    repo_root: Path,
    repo_records: list[dict[str, Any]],
    local_sources: list[LocalSource],
    github_sources: list[GitHubSource],
    output_status: dict[str, bool],
) -> list[dict[str, Any]]:
    repo_count = len(repo_records)
    metadata_only_sources = [source for source in local_sources if source.enabled and source.max_file_bytes == 0]
    learning_ready = sum(
        1
        for record in repo_records
        if not record["missing_surface_ids"]
        or "repo_learning_events" not in record["missing_surface_ids"]
    )
    governance_ready = sum(
        1
        for record in repo_records
        if "governance_dependency_map" not in record["missing_surface_ids"]
        or "governance_mirror" not in record["missing_surface_ids"]
    )
    statuses: list[dict[str, Any]] = []
    for family in SIGNAL_FAMILIES:
        family_id = str(family["signal_family_id"])
        status = "not_checked"
        evidence: dict[str, Any] = {}
        if family_id == "catalog_metadata":
            status = "covered_by_current_catalog" if repo_count else "missing_catalog"
            evidence = {"cataloged_repo_count": repo_count}
        elif family_id == "priority_content_extracts":
            if output_status.get("learning_rule_promotion_candidates"):
                status = "promotion_candidates_packaged"
            elif output_status.get("priority_content_lesson_candidates"):
                status = "lesson_candidates_synthesized"
            elif output_status.get("priority_content_observations"):
                status = "extracted_candidate_observations_present"
            elif output_status.get("priority_content_scope"):
                status = "scoped_not_extracted"
            else:
                status = "not_scanned_metadata_only" if metadata_only_sources else "partially_available"
            evidence = {
                "metadata_only_source_ids": [source.id for source in metadata_only_sources],
                "content_scan_outputs_present": output_status.get("workflow_parts", False),
                "priority_content_scope_present": output_status.get("priority_content_scope", False),
                "priority_content_observations_present": output_status.get(
                    "priority_content_observations", False
                ),
                "priority_content_lesson_candidates_present": output_status.get(
                    "priority_content_lesson_candidates", False
                ),
                "learning_rule_promotion_candidates_present": output_status.get(
                    "learning_rule_promotion_candidates", False
                ),
            }
        elif family_id == "repo_learning_events":
            if learning_ready:
                status = "partial_coverage"
            elif output_status.get("repo_learning_loop_install_scope"):
                status = "installation_scope_ready"
            else:
                status = "not_instrumented"
            evidence = {
                "repos_with_learning_event_surface": learning_ready,
                "cataloged_repo_count": repo_count,
                "repo_learning_loop_install_scope_present": output_status.get(
                    "repo_learning_loop_install_scope", False
                ),
            }
        elif family_id == "governance_map_adoption":
            if governance_ready:
                status = "partial_coverage"
            elif output_status.get("governance_map_adoption_scope"):
                status = "adoption_scope_ready"
            else:
                status = "not_instrumented"
            evidence = {
                "repos_with_map_or_mirror_surface": governance_ready,
                "cataloged_repo_count": repo_count,
                "governance_map_adoption_scope_present": output_status.get(
                    "governance_map_adoption_scope", False
                ),
            }
        elif family_id == "bounded_git_history":
            status = "covered_by_existing_report" if output_status.get("archaeology") else "not_run_this_cycle"
            evidence = {"archaeology_report_present": output_status.get("archaeology", False)}
        elif family_id == "ci_and_release_artifacts":
            status = (
                "scoped_not_extracted"
                if output_status.get("ci_release_artifact_scope")
                else "not_scanned"
            )
            evidence = {
                "ci_release_artifact_scope_present": output_status.get(
                    "ci_release_artifact_scope", False
                ),
                "content_extraction_present": False,
                "reason": "No approved CI/release artifact content extraction path in v1.",
            }
        elif family_id == "github_pr_issue_metadata":
            enabled = [source for source in github_sources if source.enabled]
            status = "deferred_by_human_gate" if not enabled else "configured_but_not_checked_here"
            evidence = {"enabled_github_source_ids": [source.id for source in enabled]}
        elif family_id == "private_source_public_safe_workflows":
            status = (
                "covered_by_existing_report"
                if output_status.get("public_safe_sweeps")
                else "not_run_this_cycle"
            )
            evidence = {"public_safe_sweep_outputs_present": output_status.get("public_safe_sweeps", False)}
        statuses.append(
            {
                **family,
                "current_status": status,
                "evidence": evidence,
                "authority_boundary": AUTHORITY_BOUNDARY,
                "applies_when": [
                    "A future agent is choosing the next repo or signal family to inspect.",
                    "The goal is to avoid repeating broad scans and instead fill known coverage gaps.",
                ],
                "does_not_apply_when": [
                    "The user explicitly authorizes a fresh broad source scan.",
                    "The target source has not been approved for even metadata-level observation.",
                ],
                "danger_if_misapplied": (
                    "A generated coverage gap can be mistaken for a claim that the repo or signal "
                    "has no value. It only means DAD has not observed that surface yet."
                ),
            }
        )
    return sorted(statuses, key=lambda item: int(item["cycle_order"]))


def _needs_followup(status: str) -> bool:
    complete_statuses = {
        "covered_by_current_catalog",
        "covered_by_existing_report",
        "promotion_candidates_packaged",
    }
    return status not in complete_statuses


def build_scan_cycle_event(
    scan_cycle_log: dict[str, Any],
    *,
    generated_at: str,
    scan_id: str,
) -> ScanCycleEventRecord:
    signal_statuses = [
        {
            "signal_family_id": entry["signal_family_id"],
            "label": entry["label"],
            "cycle_order": entry["cycle_order"],
            "current_status": entry["current_status"],
            "requires_human_approval": entry["requires_human_approval"],
            "next_action": entry["next_action"],
        }
        for entry in scan_cycle_log["cycle_entries"]
    ]
    next_families = [
        entry["signal_family_id"]
        for entry in signal_statuses
        if _needs_followup(str(entry["current_status"]))
    ]
    gated = [
        entry["signal_family_id"]
        for entry in signal_statuses
        if entry["requires_human_approval"] and _needs_followup(str(entry["current_status"]))
    ]
    next_guidance = [
        f"{entry['signal_family_id']}: {entry['next_action']}"
        for entry in signal_statuses
        if entry["signal_family_id"] in set(next_families[:5])
    ]
    return ScanCycleEventRecord(
        event_id=stable_id("scan-cycle-event", scan_id, generated_at, scan_cycle_log["pass_type"]),
        pass_type=scan_cycle_log["pass_type"],
        methodology_version=scan_cycle_log["methodology_version"],
        scan_id=scan_id,
        generated_at=generated_at,
        checked_inputs=list(scan_cycle_log["checked_inputs"]),
        intentionally_not_checked=list(scan_cycle_log["intentionally_not_checked"]),
        signal_family_statuses=signal_statuses,
        recommended_next_signal_family_ids=next_families,
        blocked_or_gated_signal_family_ids=gated,
        next_scan_guidance=next_guidance,
        authority_boundary=AUTHORITY_BOUNDARY,
        applies_when=[
            "A future agent needs to know what lesson-automation signal families were checked in prior passes.",
            "A future agent is selecting the next scan family without repeating broad scans.",
        ],
        does_not_apply_when=[
            "The user has explicitly authorized a fresh broad scan.",
            "The target source is outside the approved local source scope.",
        ],
        danger_if_misapplied=(
            "A generated scan-cycle event can be mistaken for source truth or permission to scan. "
            "It is only a routing log and does not authorize reading content, calling APIs, or mutating repos."
        ),
    )


def _repo_next_actions(record: dict[str, Any], source: LocalSource | None) -> list[str]:
    actions: list[str] = []
    missing = set(record["missing_surface_ids"])
    if source and source.enabled and source.max_file_bytes == 0:
        actions.append("Treat current repo evidence as metadata-only until a bounded content pass is approved.")
    if "repo_contract" in missing:
        actions.append("Review whether the repo needs an AGENTS.md/CLAUDE.md operating contract.")
    if "ai_front_door" in missing or "ai_toc" in missing:
        actions.append("Review AI navigation before using the repo as a future-agent source.")
    if "repo_learning_events" in missing:
        actions.append("Consider files-only learning-loop installation after human repo selection.")
    if "governance_dependency_map" in missing and "governance_mirror" in missing:
        actions.append("If this repo participates in a repo family, review governance map/mirror adoption.")
    return actions[:5]


def build_lesson_automation_coverage(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    github_sources: list[GitHubSource],
    *,
    scan_id: str,
    scan_summary: dict[str, Any] | None = None,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    groups = build_repo_groups(assets)
    repo_records: list[dict[str, Any]] = []
    skipped_noise = 0
    for repo_key, group_assets in sorted(groups.items()):
        if not any(asset.asset_type == "repository" for asset in group_assets):
            continue
        if _is_noise_repo(repo_key, group_assets):
            skipped_noise += 1
            continue
        source = _configured_source_for_repo(repo_key, local_sources)
        record = _repo_surface_status(repo_key, group_assets)
        record["configured_source_id"] = source.id if source else ""
        record["configured_source_scan_depth"] = (
            "metadata_only" if source and source.max_file_bytes == 0 else "content_excerpt"
        )
        record["recommended_next_actions"] = _repo_next_actions(record, source)
        repo_records.append(record)
    repo_records = sorted(
        repo_records,
        key=lambda item: (item["readiness_score"], -item["asset_count"], item["repo_key"]),
    )
    limited_records = repo_records[:limit]
    output_status = _existing_output_status(repo_root)
    signal_families = _signal_family_status(
        repo_root, repo_records, local_sources, github_sources, output_status
    )
    missing_surface_counts = Counter(
        surface for record in repo_records for surface in record["missing_surface_ids"]
    )
    checked_inputs = [
        "state/catalog.sqlite3 assets table",
        "latest scan summary metadata",
        "config local/github source settings",
        "presence of existing processed reports",
    ]
    intentionally_not_checked = [
        "source file contents",
        "fresh filesystem recursion",
        "GitHub PR/issue APIs",
        "CI logs or remote artifacts",
        "model or embedding calls",
        "downstream repo writes",
    ]
    scan_cycle_log = {
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "pass_type": "no_rescan_catalog_coverage",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "checked_inputs": checked_inputs,
        "intentionally_not_checked": intentionally_not_checked,
        "cycle_entries": signal_families,
        "recommended_cycle": [
            {
                "order": item["cycle_order"],
                "signal_family_id": item["signal_family_id"],
                "current_status": item["current_status"],
                "next_action": item["next_action"],
                "requires_human_approval": item["requires_human_approval"],
            }
            for item in signal_families
        ],
        "stop_conditions": [
            "Stop before broad rescans unless the user approves a fresh scope.",
            "Stop before GitHub, CI, or external APIs unless the matching gate is approved.",
            "Stop before installing learning-loop files into a repo unless that repo is explicitly selected.",
            "Stop if private row-level data would be imported into DAD.",
        ],
    }
    scan_cycle_event = build_scan_cycle_event(
        scan_cycle_log,
        generated_at=generated,
        scan_id=scan_id,
    )
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "catalog_asset_count": len(assets),
            "cataloged_repo_count": len(repo_records),
            "noise_repo_count_skipped": skipped_noise,
            "reported_repo_count": len(limited_records),
            "metadata_only_local_sources": [
                source.id for source in local_sources if source.enabled and source.max_file_bytes == 0
            ],
            "github_enabled_source_count": sum(1 for source in github_sources if source.enabled),
            "latest_scan_status": (scan_summary or {}).get("status", ""),
        },
        "source_summaries": _source_summaries(local_sources, github_sources),
        "existing_output_status": output_status,
        "missing_surface_counts": dict(sorted(missing_surface_counts.items())),
        "signal_families": signal_families,
        "repo_records": limited_records,
        "scan_cycle_log": scan_cycle_log,
        "scan_cycle_event": scan_cycle_event.model_dump(mode="json"),
        "review_status": "generated_candidate",
    }


def coverage_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Lesson Automation Coverage",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Scan id: `{result['scan_id']}`",
        f"- Cataloged repos considered: **{summary['cataloged_repo_count']}**",
        f"- Repos reported: **{summary['reported_repo_count']}**",
        f"- Noise/temp/worktree repos skipped: **{summary['noise_repo_count_skipped']}**",
        f"- Metadata-only local sources: `{summary['metadata_only_local_sources']}`",
        "",
        "## What This Pass Checked",
        "",
    ]
    for item in result["scan_cycle_log"]["checked_inputs"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Intentionally Not Checked", ""])
    for item in result["scan_cycle_log"]["intentionally_not_checked"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Signal Family Coverage", ""])
    lines.append("| Order | Signal family | Current status | Next action | Gate |")
    lines.append("|---:|---|---|---|---|")
    for family in result["signal_families"]:
        gate = "human" if family["requires_human_approval"] else "none"
        lines.append(
            "| {order} | `{family_id}` | `{status}` | {action} | {gate} |".format(
                order=family["cycle_order"],
                family_id=family["signal_family_id"],
                status=family["current_status"],
                action=str(family["next_action"]).replace("|", "/"),
                gate=gate,
            )
        )
    lines.extend(["", "## Most Common Missing Surfaces", ""])
    for surface_id, count in sorted(
        result["missing_surface_counts"].items(), key=lambda item: (-item[1], item[0])
    )[:12]:
        lines.append(f"- `{surface_id}`: **{count}** repos")
    lines.extend(["", "## Repo Coverage Queue", ""])
    lines.append(
        "| Repo | Readiness | Scan depth | Flags | Missing surfaces | Suggested next actions |"
    )
    lines.append("|---|---:|---|---|---|---|")
    for record in result["repo_records"]:
        actions = "<br>".join(record["recommended_next_actions"]) or "No immediate gap from metadata."
        lines.append(
            "| `{repo}` | {score:.1f} | `{depth}` | `{flags}` | `{missing}` | {actions} |".format(
                repo=record["repo_key"],
                score=record["readiness_score"],
                depth=record["configured_source_scan_depth"],
                flags=", ".join(record["flags"]),
                missing=", ".join(record["missing_surface_ids"]),
                actions=actions.replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Red-Team And Premortem",
            "",
            "- False positive risk: metadata can miss existing files if the last scan excluded or did not observe them.",
            "- False negative risk: a repo can be valuable even when it lacks AI navigation or learning files.",
            "- Misuse risk: do not treat missing surfaces as permission to edit downstream repos.",
            "- Repetition risk: future agents should start from the scan-cycle log instead of rerunning broad scans.",
            "- Rollback: delete generated `processed/reports/lesson_automation_coverage.*` and `processed/reports/scan_coverage_cycle.*`; no source repos are touched.",
            "",
            "## Stop Conditions",
            "",
        ]
    )
    for condition in result["scan_cycle_log"]["stop_conditions"]:
        lines.append(f"- {condition}")
    lines.append("")
    return "\n".join(lines)


def scan_cycle_markdown(result: dict[str, Any]) -> str:
    log = result["scan_cycle_log"]
    lines = [
        "# Scan Coverage Cycle Log",
        "",
        "Generated log of what this pass checked and what future agents should scan next.",
        "",
        f"- Generated at: `{log['generated_at']}`",
        f"- Pass type: `{log['pass_type']}`",
        f"- Scan id: `{log['scan_id']}`",
        "",
        "## Cycle",
        "",
        "| Order | Family | Status | Next action | Human gate |",
        "|---:|---|---|---|---|",
    ]
    for entry in log["recommended_cycle"]:
        lines.append(
            "| {order} | `{family}` | `{status}` | {action} | {gate} |".format(
                order=entry["order"],
                family=entry["signal_family_id"],
                status=entry["current_status"],
                action=str(entry["next_action"]).replace("|", "/"),
                gate="yes" if entry["requires_human_approval"] else "no",
            )
        )
    lines.extend(["", "## Checked This Pass", ""])
    for item in log["checked_inputs"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Skipped This Pass", ""])
    for item in log["intentionally_not_checked"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Safety Notes", ""])
    lines.append(log["authority_boundary"])
    lines.append("")
    return "\n".join(lines)


def write_lesson_automation_coverage_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    github_sources: list[GitHubSource],
    *,
    scan_id: str,
    scan_summary: dict[str, Any] | None = None,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_lesson_automation_coverage(
        repo_root,
        assets,
        local_sources,
        github_sources,
        scan_id=scan_id,
        scan_summary=scan_summary,
        limit=limit,
        generated_at=generated_at,
    )
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "coverage_markdown": reports_dir / "lesson_automation_coverage.md",
        "coverage_json": reports_dir / "lesson_automation_coverage.json",
        "scan_cycle_markdown": reports_dir / "scan_coverage_cycle.md",
        "scan_cycle_json": reports_dir / "scan_coverage_cycle.json",
        "scan_cycle_events": data_relative_path(
            repo_root, Path("processed") / "learning" / "scan_cycle_events.jsonl"
        ),
    }
    atomic_write_text(paths["coverage_markdown"], coverage_markdown(result))
    atomic_write_text(paths["coverage_json"], json_dumps(result, pretty=True) + "\n")
    atomic_write_text(paths["scan_cycle_markdown"], scan_cycle_markdown(result))
    atomic_write_text(paths["scan_cycle_json"], json_dumps(result["scan_cycle_log"], pretty=True) + "\n")
    append_jsonl(paths["scan_cycle_events"], result["scan_cycle_event"])
    return {
        "output_type": "generated_candidate_report",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def _weekly_reports_dir(repo_root: Path) -> Path:
    return data_relative_path(repo_root, Path("processed") / "reports")


def _weekly_cadence_dir(repo_root: Path) -> Path:
    return data_relative_path(repo_root, Path("processed") / "cadence")


def weekly_asset_coverage_paths(repo_root: Path) -> dict[str, Path]:
    reports_dir = _weekly_reports_dir(repo_root)
    cadence_dir = _weekly_cadence_dir(repo_root)
    return {
        "report_json": reports_dir / WEEKLY_ASSET_COVERAGE_REPORT_JSON,
        "report_markdown": reports_dir / WEEKLY_ASSET_COVERAGE_REPORT_MD,
        "snapshot": cadence_dir / WEEKLY_ASSET_COVERAGE_SNAPSHOT,
        "history": cadence_dir / WEEKLY_ASSET_COVERAGE_HISTORY,
        "scan_cycle_events": data_relative_path(
            repo_root, Path("processed") / "learning" / "scan_cycle_events.jsonl"
        ),
    }


def _parse_iso_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _last_jsonl_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def weekly_asset_coverage_due(
    repo_root: Path,
    *,
    generated_at: str | None = None,
    due_days: int = 7,
) -> dict[str, Any]:
    paths = weekly_asset_coverage_paths(repo_root)
    latest = _last_jsonl_record(paths["snapshot"])
    now = _parse_iso_time(generated_at or utc_now()) or datetime.now(timezone.utc)
    last_generated = _parse_iso_time(str((latest or {}).get("generated_at") or ""))
    if last_generated is None:
        return {
            "due": True,
            "reason": "no_prior_weekly_asset_coverage_snapshot",
            "last_generated_at": "",
            "due_days": due_days,
        }
    age_days = max(0.0, (now - last_generated).total_seconds() / 86400.0)
    return {
        "due": age_days >= due_days,
        "reason": "due" if age_days >= due_days else "weekly_not_due",
        "last_generated_at": last_generated.isoformat(),
        "age_days": round(age_days, 3),
        "due_days": due_days,
    }


def _repo_policy_path(policy: Any) -> Path | None:
    raw = getattr(policy, "path", None)
    if raw is None:
        return None
    return Path(raw)


def _repo_key_for_path(path: Path | None, fallback: str = "") -> str:
    if fallback.strip():
        return fallback.strip()
    if path is None:
        return "unknown-repo"
    return path.name or str(path)


def _repo_targets(
    repo_policies: Sequence[Any] | None,
    changed_paths_by_repo: dict[str, list[str] | list[dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for policy in repo_policies or []:
        if not bool(getattr(policy, "mail_enabled", True)):
            continue
        repo_path = _repo_policy_path(policy)
        repo_key = str(getattr(policy, "id", "") or getattr(policy, "alias", "") or "").strip()
        if not repo_key:
            repo_key = _repo_key_for_path(repo_path)
        targets[repo_key] = {
            "repo_key": repo_key,
            "repo_path": repo_path,
            "policy_id": str(getattr(policy, "id", "") or ""),
            "policy_alias": str(getattr(policy, "alias", "") or ""),
            "mail_enabled": bool(getattr(policy, "mail_enabled", True)),
            "changed_paths_override": None,
        }
    for key, paths in (changed_paths_by_repo or {}).items():
        repo_path = Path(key) if key and Path(key).exists() else None
        repo_key = _repo_key_for_path(repo_path, key if repo_path is None else "")
        target = targets.setdefault(
            repo_key,
            {
                "repo_key": repo_key,
                "repo_path": repo_path,
                "policy_id": "",
                "policy_alias": "",
                "mail_enabled": True,
                "changed_paths_override": None,
            },
        )
        target["changed_paths_override"] = paths
        if target.get("repo_path") is None and repo_path is not None:
            target["repo_path"] = repo_path
    return [targets[key] for key in sorted(targets)]


def _normalize_changed_path_row(row: str | dict[str, Any]) -> str:
    if isinstance(row, dict):
        raw = row.get("path") or row.get("file") or row.get("logical_path") or ""
        return str(raw).replace("\\", "/").strip()
    return str(row).replace("\\", "/").strip()


def _git_recent_changed_paths(
    repo_path: Path,
    *,
    generated_at: str,
    lookback_days: int,
) -> tuple[list[str], dict[str, Any]]:
    if not repo_path.exists():
        return [], {"status": "missing_repo_path", "repo_path": str(repo_path)}
    if not (repo_path / ".git").exists():
        return [], {"status": "not_a_git_repo", "repo_path": str(repo_path)}
    generated = _parse_iso_time(generated_at) or datetime.now(timezone.utc)
    since = (generated - timedelta(days=lookback_days)).date().isoformat()
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "log",
                f"--since={since}",
                "--name-only",
                "--pretty=format:",
                "--diff-filter=ACMR",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], {
            "status": "error",
            "repo_path": str(repo_path),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    paths = sorted(
        {
            line.strip().replace("\\", "/")
            for line in completed.stdout.splitlines()
            if line.strip()
        }
    )
    return paths, {
        "status": "ok" if completed.returncode == 0 else "git_log_failed",
        "repo_path": str(repo_path),
        "returncode": completed.returncode,
        "lookback_since": since,
        "stderr_present": bool(completed.stderr.strip()),
    }


def _path_tokens(path: str) -> set[str]:
    raw_tokens = {token.casefold() for token in _TOKEN_RE.findall(path.replace("/", " "))}
    split_tokens: set[str] = set()
    for token in raw_tokens:
        split_tokens.update(part for part in re.split(r"[_+.-]+", token) if part)
    return {
        token
        for token in raw_tokens | split_tokens
        if len(token) >= 3 and token not in _GENERIC_PATH_TOKENS
    }


def _skip_recent_path(path: str) -> bool:
    lowered = path.casefold().lstrip("./")
    return any(lowered.startswith(prefix) for prefix in _SKIP_RECENT_PATH_PREFIXES)


def classify_weekly_asset_path(path: str) -> dict[str, Any] | None:
    normalized = path.replace("\\", "/").lstrip("./")
    if not normalized or _skip_recent_path(normalized):
        return None
    lowered = normalized.casefold()
    categories: list[str] = []
    reasons: list[str] = []
    weight = 0

    def add(category: str, value: int, reason: str) -> None:
        nonlocal weight
        if category not in categories:
            categories.append(category)
            reasons.append(reason)
            weight = max(weight, value)

    if (
        lowered.startswith("tests/")
        or "/tests/" in lowered
        or Path(lowered).name.startswith("test_")
        or "_test." in lowered
        or "validate_" in lowered
        or "benchmark" in lowered
        or "smoke" in lowered
        or "red_team" in lowered
        or "guardrail" in lowered
        or "fixture" in lowered
    ):
        add("test_or_harness", 4, "path looks like a test, validator, fixture, smoke, benchmark, or guardrail")
    path_name = PurePosixPath(lowered).name
    if (
        lowered.startswith("scripts/")
        and path_name.startswith(("build_", "run_", "process_", "confirm_", "audit_"))
    ) or "engine" in lowered or "workflow" in lowered or "intake" in lowered or "pipeline" in lowered:
        add("engine_or_workflow", 5, "path looks like an executable workflow, intake engine, or pipeline")
    if (
        lowered.startswith("simulation/")
        or "simulation" in lowered
        or "simulator" in lowered
        or "monte_carlo" in lowered
        or "monte-carlo" in lowered
        or "scenario" in lowered
        or "jury" in lowered
        or "mock_jury" in lowered
    ):
        add("simulation_engine", 5, "path belongs to simulation, Monte Carlo, scenario, or jury/persona surfaces")
    if (
        "license" in lowered
        or "oss" in lowered
        or "external" in lowered
        or "public_fixture" in lowered
        or "due_diligence" in lowered
        or "research_registry" in lowered
        or "benchmark_registry" in lowered
    ):
        add("external_resource", 4, "path looks like external-resource, license, benchmark, or OSS intake governance")
    if lowered.startswith("schemas/") or "schema" in lowered or "contract" in lowered or "registry" in lowered:
        add("schema_or_contract", 3, "path looks like schema, contract, or registry-backed asset metadata")
    if "graphlite" in lowered or "graph" in lowered or "kg" in lowered or "lineage" in lowered:
        add("graph_or_kg", 3, "path looks like graph, GraphLite, KG, or lineage infrastructure")
    if not categories:
        return None
    return {
        "path": normalized,
        "categories": categories,
        "weight": weight or 1,
        "reason": "; ".join(reasons),
        "path_terms": sorted(_path_tokens(normalized)),
    }


def _safe_jsonl_records(path: Path, *, max_bytes: int = 5_000_000) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        if path.stat().st_size > max_bytes:
            return []
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _safe_repo_relative_ref(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized or len(normalized) > 512:
        return ""
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", normalized):
        return ""
    return normalized


def _safe_envelope_token_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in _SAFE_ENVELOPE_IDENTIFIER_FIELDS:
        value = record.get(field)
        if isinstance(value, (str, int, float, bool)):
            text = str(value).strip()
            if text and len(text) <= 256:
                parts.append(text)
    for field in _SAFE_ENVELOPE_REF_FIELDS:
        value = record.get(field)
        values = value if isinstance(value, list) else [value]
        for item in values[:50]:
            if not isinstance(item, str):
                continue
            safe_ref = _safe_repo_relative_ref(item)
            if safe_ref:
                parts.append(safe_ref)
    return " ".join(parts)


def _envelope_temporal_status(
    record: dict[str, Any],
    *,
    generated_at: str,
    lookback_days: int,
) -> str:
    generated = _parse_iso_time(generated_at) or datetime.now(timezone.utc)
    cutoff = generated - timedelta(days=lookback_days)
    for field in _ENVELOPE_TIMESTAMP_FIELDS:
        parsed = _parse_iso_time(str(record.get(field) or ""))
        if parsed is not None:
            return "current" if parsed >= cutoff else "stale"
    return "undated"


def _evidence_ref(source: str, index: int, record: dict[str, Any]) -> str:
    for field in ("mail_id", "event_id", "asset_id", "dedupe_key", "lesson_id", "exception_id"):
        value = str(record.get(field) or "").strip()
        if value:
            return f"{source}:{value}"
    return f"{source}:row-{index}"


def _repo_envelope_evidence(
    repo_path: Path | None,
    *,
    generated_at: str,
    lookback_days: int,
) -> list[dict[str, Any]]:
    if repo_path is None or not repo_path.exists():
        return []
    evidence: list[dict[str, Any]] = []
    for rel_path, source, confidence in _REPO_ENVELOPE_SOURCES:
        path = repo_path / rel_path
        for index, record in enumerate(_safe_jsonl_records(path), start=1):
            temporal_status = _envelope_temporal_status(
                record,
                generated_at=generated_at,
                lookback_days=lookback_days,
            )
            if temporal_status == "stale":
                continue
            text = _safe_envelope_token_text(record).casefold().replace("\\", "/")
            if not text:
                continue
            evidence.append(
                {
                    "source": source,
                    "confidence": confidence if temporal_status == "current" else min(confidence, 0.4),
                    "temporal_status": temporal_status,
                    "ref": _evidence_ref(source, index, record),
                    "tokens": _path_tokens(text),
                    "text": text,
                }
            )
    return evidence


def _coverage_for_candidate(
    candidate: dict[str, Any], evidence_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    path = str(candidate["path"]).casefold()
    terms = set(candidate.get("path_terms") or [])
    category_terms = set(candidate.get("categories") or [])
    best_status = "missing"
    best_score = 0.0
    refs: list[str] = []
    matched_terms: set[str] = set()
    for evidence in evidence_rows:
        text = str(evidence.get("text") or "")
        tokens = set(evidence.get("tokens") or [])
        exact = path in text
        overlap = terms & tokens
        category_overlap = category_terms & tokens
        score = 0.0
        status = "missing"
        temporally_current = evidence.get("temporal_status") == "current"
        if temporally_current and (
            exact or (len(overlap) >= 2 and (category_overlap or len(terms) <= 3))
        ):
            status = "covered"
            score = 1.0 * float(evidence.get("confidence") or 1.0)
        elif exact or overlap or category_overlap:
            status = "weak"
            score = 0.5 * float(evidence.get("confidence") or 1.0)
        if score > best_score:
            best_score = score
            best_status = status
        if score > 0:
            refs.append(str(evidence.get("ref") or "evidence"))
            matched_terms.update(overlap)
    return {
        "coverage_status": best_status,
        "coverage_score": round(min(best_score, 1.0), 3),
        "evidence_refs": sorted(set(refs))[:8],
        "matched_terms": sorted(matched_terms)[:12],
    }


def _grade(score: float | None) -> str:
    if score is None:
        return "N/A"
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _weekly_scan_cycle_event(result: dict[str, Any]) -> dict[str, Any]:
    generated_at = result["generated_at"]
    scan_id = result["scan_id"]
    signal_families = [
        {
            "signal_family_id": "recent_repo_path_metadata",
            "label": "Recent repo path metadata",
            "cycle_order": 1,
            "current_status": "checked",
            "next_action": "Keep weekly read-only Git path crawl on the daemon cadence.",
            "requires_human_approval": False,
        },
        {
            "signal_family_id": "repo_dad_envelope_response",
            "label": "Repo DAD envelope response",
            "cycle_order": 2,
            "current_status": "checked",
            "next_action": "Improve repo-local mail/asset/exception envelopes for uncovered high-value assets.",
            "requires_human_approval": False,
        },
        {
            "signal_family_id": "coverage_gap_exception_review",
            "label": "Coverage gap exception review",
            "cycle_order": 3,
            "current_status": "candidate" if result["summary"]["missing_candidate_count"] else "not_needed",
            "next_action": "Review missing candidates before promoting any exception class or downstream instruction.",
            "requires_human_approval": True,
        },
    ]
    scan_cycle_log = {
        "methodology_version": WEEKLY_ASSET_COVERAGE_VERSION,
        "generated_at": generated_at,
        "scan_id": scan_id,
        "pass_type": "weekly_asset_coverage",
        "authority_boundary": WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY,
        "checked_inputs": [
            "reviewed repo policy paths supplied by DAD configuration",
            "recent Git changed-path metadata only",
            "allowlisted identifiers and repo-relative refs from repo-local DAD envelopes within the lookback window",
        ],
        "intentionally_not_checked": [
            "source file contents",
            "raw case facts, witness packets, and private payloads",
            "GitHub PR bodies or CI logs unless a separate human-approved review asks for them",
            "downstream repo writes",
        ],
        "cycle_entries": signal_families,
        "recommended_cycle": signal_families,
        "stop_conditions": [
            "Stop before reading source file contents or raw private outputs.",
            "Stop before mutating a downstream repo.",
            "Stop before promoting a coverage gap to source truth or roadmap evidence.",
        ],
    }
    return build_scan_cycle_event(
        scan_cycle_log,
        generated_at=generated_at,
        scan_id=scan_id,
    ).model_dump(mode="json")


def build_weekly_asset_coverage(
    repo_root: Path,
    *,
    repo_policies: Sequence[Any] | None = None,
    changed_paths_by_repo: dict[str, list[str] | list[dict[str, Any]]] | None = None,
    lookback_days: int = 21,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    scan_id = stable_id("weekly-asset-coverage", generated, str(repo_root.resolve()))
    targets = _repo_targets(repo_policies, changed_paths_by_repo)
    repo_reports: list[dict[str, Any]] = []
    exception_candidates: list[dict[str, Any]] = []
    for target in targets:
        repo_path = target.get("repo_path")
        override = target.get("changed_paths_override")
        if override is None and isinstance(repo_path, Path):
            changed_paths, git_status = _git_recent_changed_paths(
                repo_path,
                generated_at=generated,
                lookback_days=lookback_days,
            )
        else:
            changed_paths = sorted(
                {
                    _normalize_changed_path_row(row)
                    for row in (override or [])
                    if _normalize_changed_path_row(row)
                }
            )
            git_status = {
                "status": "injected_changed_paths",
                "repo_path": str(repo_path) if repo_path is not None else "",
                "lookback_days": lookback_days,
            }
        evidence_rows = _repo_envelope_evidence(
            repo_path if isinstance(repo_path, Path) else None,
            generated_at=generated,
            lookback_days=lookback_days,
        )
        candidates: list[dict[str, Any]] = []
        for changed_path in changed_paths:
            classified = classify_weekly_asset_path(changed_path)
            if classified is None:
                continue
            coverage = _coverage_for_candidate(classified, evidence_rows)
            candidate = {
                "candidate_id": stable_id(
                    "weekly-asset-candidate",
                    str(target["repo_key"]),
                    classified["path"],
                    WEEKLY_ASSET_COVERAGE_VERSION,
                ),
                **classified,
                **coverage,
            }
            candidates.append(candidate)
        total_weight = sum(float(item["weight"]) for item in candidates)
        covered_weight = sum(
            float(item["weight"]) * float(item["coverage_score"]) for item in candidates
        )
        score = round(100.0 * covered_weight / total_weight, 1) if total_weight else None
        missing = [
            item
            for item in candidates
            if item["coverage_status"] == "missing" and float(item["weight"]) >= 4
        ]
        scan_failed = git_status.get("status") not in {"ok", "injected_changed_paths"}
        repo_report = {
            "repo_key": target["repo_key"],
            "repo_path": str(repo_path) if repo_path is not None else "",
            "mail_enabled": target["mail_enabled"],
            "git_status": git_status,
            "recent_changed_path_count": len(changed_paths),
            "candidate_count": len(candidates),
            "covered_candidate_count": sum(1 for item in candidates if item["coverage_status"] == "covered"),
            "weak_candidate_count": sum(1 for item in candidates if item["coverage_status"] == "weak"),
            "missing_candidate_count": sum(1 for item in candidates if item["coverage_status"] == "missing"),
            "missing_high_signal_count": len(missing),
            "coverage_score": score,
            "grade": "BLOCKED" if scan_failed else _grade(score),
            "scan_failed": scan_failed,
            "evidence_surface_counts": dict(
                Counter(str(item["source"]) for item in evidence_rows)
            ),
            "candidates": candidates,
        }
        repo_reports.append(repo_report)
        if scan_failed:
            exception_candidates.append(
                {
                    "candidate_exception_id": stable_id(
                        "weekly-asset-coverage-scan-failure",
                        str(target["repo_key"]),
                        WEEKLY_ASSET_COVERAGE_VERSION,
                    ),
                    "event_type": "review_finding",
                    "candidate_exception_labels": ["asset_coverage_scan_unavailable"],
                    "source_repo": target["repo_key"],
                    "path_ref": "",
                    "categories": [],
                    "safe_summary": "Reviewed repo path could not be scanned for weekly asset coverage.",
                    "review_status": "generated_candidate",
                    "authority_boundary": WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY,
                }
            )
        for item in missing:
            exception_candidates.append(
                {
                    "candidate_exception_id": stable_id(
                        "weekly-asset-coverage-gap",
                        str(target["repo_key"]),
                        str(item["path"]),
                        WEEKLY_ASSET_COVERAGE_VERSION,
                    ),
                    "event_type": "review_finding",
                    "candidate_exception_labels": ["asset_coverage_reporting_gap"],
                    "source_repo": target["repo_key"],
                    "path_ref": item["path"],
                    "categories": item["categories"],
                    "safe_summary": (
                        "Recent high-signal asset/test/resource path changed without a "
                        "strong matching repo-local DAD mail, asset, exception, or learning envelope."
                    ),
                    "review_status": "generated_candidate",
                    "authority_boundary": WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY,
                }
            )
    scored = [item["coverage_score"] for item in repo_reports if item["coverage_score"] is not None]
    result = {
        "schema_version": "dad.weekly_asset_coverage.v1",
        "methodology_version": WEEKLY_ASSET_COVERAGE_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "lookback_days": lookback_days,
        "repo_count": len(repo_reports),
        "summary": {
            "repo_count": len(repo_reports),
            "candidate_count": sum(item["candidate_count"] for item in repo_reports),
            "covered_candidate_count": sum(item["covered_candidate_count"] for item in repo_reports),
            "weak_candidate_count": sum(item["weak_candidate_count"] for item in repo_reports),
            "missing_candidate_count": sum(item["missing_candidate_count"] for item in repo_reports),
            "missing_high_signal_count": sum(item["missing_high_signal_count"] for item in repo_reports),
            "scan_failure_count": sum(1 for item in repo_reports if item["scan_failed"]),
            "average_coverage_score": round(sum(scored) / len(scored), 1) if scored else None,
            "grade_counts": dict(Counter(item["grade"] for item in repo_reports)),
        },
        "repos": repo_reports,
        "exception_candidates": exception_candidates,
        "scan_cycle_event": {},
        "review_status": "generated_candidate",
        "authority_boundary": WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY,
        "score_method": (
            "Weighted coverage of recent high-signal changed paths. Strong matching "
            "repo-local DAD evidence gets full credit; weak term/category evidence gets "
            "half credit; missing high-signal paths become review candidates."
        ),
    }
    result["scan_cycle_event"] = _weekly_scan_cycle_event(result)
    return result


def weekly_asset_coverage_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    avg = summary["average_coverage_score"]
    avg_text = "N/A" if avg is None else f"{avg:.1f}"
    lines = [
        "# Weekly Asset Coverage",
        "",
        WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Lookback days: **{result['lookback_days']}**",
        f"- Repos checked: **{summary['repo_count']}**",
        f"- Candidate paths: **{summary['candidate_count']}**",
        f"- Covered: **{summary['covered_candidate_count']}**",
        f"- Weak: **{summary['weak_candidate_count']}**",
        f"- Missing: **{summary['missing_candidate_count']}**",
        f"- Missing high-signal: **{summary['missing_high_signal_count']}**",
        f"- Average score: **{avg_text}**",
        "",
        "## Repo Grades",
        "",
        "| Repo | Grade | Score | Candidates | Missing high-signal | Evidence surfaces |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for repo in result["repos"]:
        score = repo["coverage_score"]
        score_text = "N/A" if score is None else f"{score:.1f}"
        surfaces = ", ".join(
            f"{key}:{value}" for key, value in sorted(repo["evidence_surface_counts"].items())
        )
        lines.append(
            "| `{repo}` | {grade} | {score} | {candidates} | {missing} | {surfaces} |".format(
                repo=repo["repo_key"],
                grade=repo["grade"],
                score=score_text,
                candidates=repo["candidate_count"],
                missing=repo["missing_high_signal_count"],
                surfaces=surfaces or "none",
            )
        )
    lines.extend(["", "## Missing High-Signal Candidates", ""])
    if not result["exception_candidates"]:
        lines.append("- None in this run.")
    else:
        for item in result["exception_candidates"][:50]:
            lines.append(
                "- `{repo}` `{path}` -> {labels}".format(
                    repo=item["source_repo"],
                    path=item["path_ref"],
                    labels=", ".join(item["candidate_exception_labels"]),
                )
            )
    lines.extend(
        [
            "",
            "## Red-Team And Premortem",
            "",
            "- False positive risk: path names can look reusable while a repo intentionally keeps them local.",
            "- False negative risk: broad mail can mention a theme without asset-specific adoption evidence.",
            "- Privacy boundary: generated case outputs and raw source paths are skipped by default.",
            "- Rollback: delete generated weekly asset coverage reports and cadence rows; no source repos are touched.",
            "",
        ]
    )
    return "\n".join(lines)


def write_weekly_asset_coverage_outputs(
    repo_root: Path,
    *,
    repo_policies: Sequence[Any] | None = None,
    changed_paths_by_repo: dict[str, list[str] | list[dict[str, Any]]] | None = None,
    lookback_days: int = 21,
    due_days: int = 7,
    force: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    paths = weekly_asset_coverage_paths(repo_root)
    due = weekly_asset_coverage_due(repo_root, generated_at=generated, due_days=due_days)
    if not force and not due["due"]:
        previous_summary: dict[str, Any] = {}
        try:
            previous = json.loads(paths["report_json"].read_text(encoding="utf-8"))
            if isinstance(previous, dict) and isinstance(previous.get("summary"), dict):
                previous_summary = dict(previous["summary"])
        except (OSError, json.JSONDecodeError):
            previous_summary = {}
        return {
            "schema_version": "dad.weekly_asset_coverage.outputs.v1",
            "output_type": "generated_candidate_report",
            "status": "skipped",
            "reason": due["reason"],
            "due": due,
            "summary": previous_summary,
            "prior_findings_carried_forward": bool(previous_summary),
            "outputs": {key: str(path) for key, path in paths.items()},
            "authority_boundary": WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY,
        }
    result = build_weekly_asset_coverage(
        repo_root,
        repo_policies=repo_policies,
        changed_paths_by_repo=changed_paths_by_repo,
        lookback_days=lookback_days,
        generated_at=generated,
    )
    snapshot = {
        "schema_version": "dad.weekly_asset_coverage.snapshot.v1",
        "generated_at": generated,
        "scan_id": result["scan_id"],
        "summary": result["summary"],
        "candidate_fingerprints": [
            stable_id("weekly-asset-candidate-fingerprint", repo["repo_key"], candidate["path"])
            for repo in result["repos"]
            for candidate in repo["candidates"]
        ],
    }
    history = {
        "schema_version": "dad.weekly_asset_coverage.history.v1",
        "generated_at": generated,
        "scan_id": result["scan_id"],
        "summary": result["summary"],
        "exception_candidate_count": len(result["exception_candidates"]),
        "exception_candidates": result["exception_candidates"],
    }
    atomic_write_text(paths["report_json"], json_dumps(result, pretty=True) + "\n")
    atomic_write_text(paths["report_markdown"], weekly_asset_coverage_markdown(result))
    append_jsonl(paths["snapshot"], snapshot)
    append_jsonl(paths["history"], history)
    append_jsonl(paths["scan_cycle_events"], result["scan_cycle_event"])
    return {
        "schema_version": "dad.weekly_asset_coverage.outputs.v1",
        "output_type": "generated_candidate_report",
        "status": "ok",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
        "authority_boundary": WEEKLY_ASSET_COVERAGE_AUTHORITY_BOUNDARY,
    }
