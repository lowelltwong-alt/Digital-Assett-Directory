from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .config import GitHubSource, LocalSource
from .ids import stable_id
from .models import AssetRecord, ScanCycleEventRecord
from .repo_buildout import build_repo_groups
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "lesson-automation-coverage-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated coverage and scan-cycle guidance only. This command reads the current catalog, "
    "configuration metadata, and generated-output presence; it does not rescan source repos, read "
    "source file contents, call GitHub, call models, mutate downstream repos, install hooks, or "
    "promote candidate findings to truth."
)

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
    paths = {
        "workflow_sweeps": repo_root / "processed" / "reports" / "workflow_sweeps",
        "workflow_parts": repo_root / "processed" / "learning" / "workflow_parts.jsonl",
        "manual_task_queue": repo_root / "processed" / "reports" / "manual_task_queue.json",
        "template_library": repo_root / "processed" / "reports" / "template_library.json",
        "priority_content_scope": repo_root
        / "processed"
        / "reports"
        / "priority_content_extract_scope.json",
        "priority_content_observations": repo_root
        / "processed"
        / "learning"
        / "priority_content_observations.jsonl",
        "priority_content_lesson_candidates": repo_root
        / "processed"
        / "learning"
        / "priority_content_lesson_candidates.jsonl",
        "learning_rule_promotion_candidates": repo_root
        / "processed"
        / "learning"
        / "learning_rule_promotion_candidates.jsonl",
        "lesson_automation_next_actions": repo_root
        / "processed"
        / "reports"
        / "lesson_automation_next_actions.json",
        "archaeology": repo_root / "processed" / "reports" / "worktree_archaeology.md",
        "root_cause_lessons": repo_root / "processed" / "learning" / "counterfactual_lessons.jsonl",
        "semantic_evolution": repo_root / "processed" / "learning" / "semantic_evolution_candidates.jsonl",
        "ci_release_artifact_scope": repo_root
        / "processed"
        / "reports"
        / "ci_release_artifact_scope.json",
        "repo_learning_loop_install_scope": repo_root
        / "processed"
        / "reports"
        / "repo_learning_loop_install_scope.json",
        "governance_map_adoption_scope": repo_root
        / "processed"
        / "reports"
        / "governance_map_adoption_scope.json",
        "background_connections": (
            repo_root / "processed" / "learning" / "background_connection_candidates.jsonl"
        ),
        "repo_buildout_index": repo_root / "processed" / "reports" / "repo_buildout" / "index.md",
        "public_safe_sweeps": repo_root / "processed" / "reports" / "external_sweeps",
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
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "coverage_markdown": reports_dir / "lesson_automation_coverage.md",
        "coverage_json": reports_dir / "lesson_automation_coverage.json",
        "scan_cycle_markdown": reports_dir / "scan_coverage_cycle.md",
        "scan_cycle_json": reports_dir / "scan_coverage_cycle.json",
        "scan_cycle_events": repo_root / "processed" / "learning" / "scan_cycle_events.jsonl",
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
