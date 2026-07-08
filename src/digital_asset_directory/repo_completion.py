from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import AssetRecord
from .repo_buildout import build_repo_groups
from .transport import data_relative_path
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "repo-completion-dashboard-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated repo-completion dashboard only. This command reads catalog metadata "
    "and generated scope/decision outputs; it does not rescan, read source file "
    "contents, mutate source repos, call GitHub, call models, approve decisions, "
    "install hooks, or mark roadmap phases complete."
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _normalized(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/").lower()


def _relative_path(logical_path: str, repo_key: str) -> str:
    logical = _normalized(logical_path)
    key = _normalized(repo_key)
    if logical == key:
        return ""
    prefix = f"{key}/"
    if logical.startswith(prefix):
        return logical[len(prefix) :]
    return logical


def _basename(path: str) -> str:
    return Path(path.replace("\\", "/")).name.lower()


def _repo_label(repo_key: str, repo_asset: AssetRecord | None) -> str:
    if repo_asset and repo_asset.title:
        return repo_asset.title
    parts = [part for part in repo_key.split("/") if part]
    return parts[-1] if parts else repo_key


def _repo_paths(repo_key: str, assets: list[AssetRecord]) -> set[str]:
    return {
        _relative_path(asset.logical_path, repo_key)
        for asset in assets
        if _relative_path(asset.logical_path, repo_key)
    }


def _surface_flags(repo_key: str, assets: list[AssetRecord]) -> dict[str, bool]:
    paths = _repo_paths(repo_key, assets)
    basenames = {_basename(path) for path in paths}
    normalized_paths = {_normalized(path) for path in paths}
    entrypoints = {
        _normalized(entrypoint)
        for asset in assets
        for entrypoint in (asset.entrypoints or [])
        if entrypoint
    }
    all_paths = normalized_paths | entrypoints
    return {
        "has_repo_contract": bool({"agents.md", "claude.md"} & basenames),
        "has_ai_front_door": "ai_front_door.md" in basenames,
        "has_ai_toc": bool({"ai_table_of_contents.md", "ai_toc.md"} & basenames),
        "has_learning_readme": ".digital-asset-directory/learning/readme.md" in all_paths,
        "has_learning_context_tags": ".digital-asset-directory/learning/context-tags.yaml"
        in all_paths,
        "has_learning_events": ".digital-asset-directory/learning/events.jsonl" in all_paths,
        "has_governance_map": any("governance_dependency_map" in path for path in all_paths),
        "has_governance_mirror": any("governance_dependency_map_mirror" in path for path in all_paths),
        "has_validation_surface": any(
            path.startswith("tests/")
            or path.startswith("scripts/validate")
            or _basename(path).startswith("test_")
            for path in all_paths
        ),
    }


def _scope_by_repo(scope: dict[str, Any] | None, key: str) -> dict[str, dict[str, Any]]:
    if not scope:
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for entry in scope.get(key, []):
        repo_key = _normalized(str(entry.get("repo_key", "")))
        if repo_key:
            indexed[repo_key] = entry
    return indexed


def _scope_category_ids(scope_entry: dict[str, Any] | None) -> set[str]:
    if not scope_entry:
        return set()
    return {
        str(candidate.get("primary_category_id", "")).strip()
        for candidate in scope_entry.get("candidates", [])
        if str(candidate.get("primary_category_id", "")).strip()
    }


def _is_noise_repo(repo_key: str, assets: list[AssetRecord]) -> bool:
    lowered = _normalized(repo_key)
    if lowered.endswith("/.") or lowered in {"", ".", "git-projects/."}:
        return True
    noise_markers = {
        ".pytest-tmp-root",
        ".pytest-tmp-local",
        "pytest-of-",
        "_codex_worktrees",
        ".claude/worktrees",
        "/tmp/",
        "/temp/",
        "/node_modules/",
        "/.venv/",
        "/__pycache__/",
    }
    if any(marker in lowered for marker in noise_markers):
        return True
    return any(asset.metadata.get("instance_class") in {"temp", "worktree"} for asset in assets)


def _decision_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decision_count": len(decisions),
        "pending_count": sum(1 for item in decisions if item.get("decision") == "pending"),
        "approved_count": sum(1 for item in decisions if item.get("decision") == "approve"),
        "deferred_count": sum(1 for item in decisions if item.get("decision") == "defer"),
        "rejected_count": sum(1 for item in decisions if item.get("decision") == "reject"),
        "content_read_approval_count": sum(1 for item in decisions if item.get("allow_content_read")),
        "source_mutation_approval_count": sum(1 for item in decisions if item.get("allow_source_mutation")),
        "external_api_approval_count": sum(1 for item in decisions if item.get("allow_external_api")),
    }


def _completion_state(
    flags: dict[str, bool],
    *,
    priority_candidate: bool,
    priority_categories: set[str],
    learning_candidate: bool,
    governance_candidate: bool,
    decisions: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    next_actions: list[str] = []
    ai_navigation_candidate = "ai_navigation" in priority_categories
    validation_candidate = "validators_tests" in priority_categories
    if (
        not (flags["has_ai_front_door"] and flags["has_ai_toc"] and flags["has_repo_contract"])
        and not ai_navigation_candidate
    ):
        blockers.append("ai_navigation_incomplete")
        next_actions.append("Review or add repo AI front door, TOC, and operating contract.")
    if priority_candidate and not decisions["content_read_approval_count"]:
        blockers.append("content_extract_human_gate")
        next_actions.append("Approve bounded priority content extraction before lesson synthesis.")
    if not (
        flags["has_learning_readme"]
        and flags["has_learning_context_tags"]
        and flags["has_learning_events"]
    ):
        blockers.append("repo_learning_loop_missing")
        next_actions.append("Select repo for files-only learning-loop installation before writing files.")
    if not (flags["has_governance_map"] or flags["has_governance_mirror"]):
        blockers.append("governance_dependency_surface_missing")
        next_actions.append("Review whether the repo needs a governance map or child mirror.")
    if not flags["has_validation_surface"] and not validation_candidate:
        blockers.append("validation_surface_not_observed")
        next_actions.append("Review repo-local tests or validators before relying on automation.")
    if learning_candidate and "repo_learning_loop_missing" not in blockers:
        next_actions.append("Learning-loop install scope exists; confirm existing surface is reviewed.")
    if governance_candidate and "governance_dependency_surface_missing" not in blockers:
        next_actions.append("Governance adoption scope exists; confirm existing surface is reviewed.")
    if not blockers:
        return "metadata_completion_ready_for_human_review", blockers, next_actions
    if "content_extract_human_gate" in blockers:
        return "blocked_by_content_read_gate", blockers, next_actions
    if "repo_learning_loop_missing" in blockers or "governance_dependency_surface_missing" in blockers:
        return "blocked_by_source_repo_governance_gate", blockers, next_actions
    return "metadata_incomplete", blockers, next_actions


def build_repo_completion_dashboard(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    generated_at: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    priority_scope = _load_json(reports_dir / "priority_content_extract_scope.json")
    learning_scope = _load_json(reports_dir / "repo_learning_loop_install_scope.json")
    governance_scope = _load_json(reports_dir / "governance_map_adoption_scope.json")
    ci_scope = _load_json(reports_dir / "ci_release_artifact_scope.json")
    approval_packet = _load_json(reports_dir / "lesson_automation_approval_packet.json")
    execution_plan = _load_json(reports_dir / "lesson_automation_execution_plan.json")
    decisions = _load_jsonl(learning_dir / "lesson_automation_action_decisions.jsonl")
    decision_summary = _decision_summary(decisions)

    priority_by_repo = _scope_by_repo(priority_scope, "repo_scopes")
    learning_by_repo = _scope_by_repo(learning_scope, "repo_candidates")
    governance_by_repo = _scope_by_repo(governance_scope, "repo_candidates")
    ci_by_repo = _scope_by_repo(ci_scope, "repo_scopes")

    records: list[dict[str, Any]] = []
    skipped_without_repo_asset = 0
    skipped_noise_repo = 0
    for repo_key, group_assets in sorted(build_repo_groups(assets).items()):
        repo_asset = next((asset for asset in group_assets if asset.asset_type == "repository"), None)
        if not repo_asset:
            skipped_without_repo_asset += 1
            continue
        if _is_noise_repo(repo_key, group_assets):
            skipped_noise_repo += 1
            continue
        normalized_key = _normalized(repo_key)
        flags = _surface_flags(repo_key, group_assets)
        priority_entry = priority_by_repo.get(normalized_key)
        priority_categories = _scope_category_ids(priority_entry)
        priority_candidate = normalized_key in priority_by_repo
        learning_candidate = normalized_key in learning_by_repo
        governance_candidate = normalized_key in governance_by_repo
        state, blockers, next_actions = _completion_state(
            flags,
            priority_candidate=priority_candidate,
            priority_categories=priority_categories,
            learning_candidate=learning_candidate,
            governance_candidate=governance_candidate,
            decisions=decision_summary,
        )
        records.append(
            {
                "repo_key": repo_key,
                "repo_label": _repo_label(repo_key, repo_asset),
                "repo_asset_id": repo_asset.asset_id,
                "asset_count": len(group_assets),
                "completion_state": state,
                "blockers": blockers,
                "next_actions": next_actions[:5],
                "surface_flags": flags,
                "scope_flags": {
                    "priority_content_scope_candidate": priority_candidate,
                    "priority_content_scope_categories": sorted(priority_categories),
                    "repo_learning_loop_install_candidate": learning_candidate,
                    "governance_map_adoption_candidate": governance_candidate,
                    "ci_release_artifact_scope_candidate": normalized_key in ci_by_repo,
                },
                "candidate_evidence": {
                    "priority_content": priority_entry or {},
                    "repo_learning_loop": learning_by_repo.get(normalized_key, {}),
                    "governance_map_adoption": governance_by_repo.get(normalized_key, {}),
                    "ci_release_artifact": ci_by_repo.get(normalized_key, {}),
                },
                "authority_boundary": AUTHORITY_BOUNDARY,
                "applies_when": [
                    "A future agent needs to see per-repo completion blockers before scanning or installing anything.",
                    "The work should start from generated DAD status surfaces rather than chat memory.",
                ],
                "does_not_apply_when": [
                    "The user has approved a direct source-repo mutation or content read for one named repo.",
                    "The catalog is stale and must be refreshed through an approved scan first.",
                ],
                "danger_if_misapplied": (
                    "A generated completion state can be mistaken for proof that a repo is complete. "
                    "It only reports observed surfaces and pending gates."
                ),
                "review_status": "generated_candidate",
            }
        )
    all_records = sorted(records, key=lambda item: (item["completion_state"], item["repo_key"]))
    reported_records = all_records[:limit]
    state_counts = Counter(record["completion_state"] for record in all_records)
    blocker_counts = Counter(blocker for record in all_records for blocker in record["blockers"])
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "status_methodology": {
            "type": "deterministic_status_labels",
            "inputs": [
                "catalog repository assets and logical paths",
                "priority content scope report",
                "repo learning-loop install scope report",
                "governance map adoption scope report",
                "CI/release artifact scope report",
                "lesson automation decision ledger",
                "lesson automation approval packet and execution plan presence",
            ],
            "output_range": [
                "metadata_completion_ready_for_human_review",
                "blocked_by_content_read_gate",
                "blocked_by_source_repo_governance_gate",
                "metadata_incomplete",
            ],
            "score_used": False,
        },
        "summary": {
            "repo_count": len(all_records),
            "reported_repo_count": len(reported_records),
            "skipped_groups_without_repo_asset": skipped_without_repo_asset,
            "skipped_noise_repo_count": skipped_noise_repo,
            "state_counts": dict(sorted(state_counts.items())),
            "blocker_counts": dict(sorted(blocker_counts.items())),
            "decision_summary": decision_summary,
            "approval_packet_present": bool(approval_packet),
            "execution_plan_present": bool(execution_plan),
            "source_repos_mutated": 0,
            "content_files_read": 0,
            "github_calls": 0,
            "model_calls": 0,
            "roadmap_phases_marked_complete": 0,
        },
        "checked_inputs": [
            "state/catalog.sqlite3 assets table",
            "processed/reports/priority_content_extract_scope.json",
            "processed/reports/repo_learning_loop_install_scope.json",
            "processed/reports/governance_map_adoption_scope.json",
            "processed/reports/ci_release_artifact_scope.json",
            "processed/learning/lesson_automation_action_decisions.jsonl",
            "processed/reports/lesson_automation_approval_packet.json",
            "processed/reports/lesson_automation_execution_plan.json",
        ],
        "intentionally_not_done": [
            "fresh source scan",
            "source file content reads",
            "decision approval",
            "source repo mutation",
            "learning-loop installation",
            "GitHub/API/model calls",
            "roadmap phase completion",
        ],
        "repo_records": reported_records,
        "review_status": "generated_candidate",
    }


def repo_completion_dashboard_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Repo Completion Dashboard",
        "",
        result["authority_boundary"],
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Repo count: **{summary['repo_count']}**",
        f"- Repos reported: **{summary['reported_repo_count']}**",
        f"- Noise/temp repos skipped: **{summary['skipped_noise_repo_count']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- GitHub/model calls: **{summary['github_calls']}** / **{summary['model_calls']}**",
        "",
        "## Status Methodology",
        "",
        "This dashboard uses deterministic status labels, not calculated scores.",
        "",
        "Inputs:",
        "",
    ]
    for item in result["status_methodology"]["inputs"]:
        lines.append(f"- {item}")
    lines.extend(["", "Output labels:", ""])
    for item in result["status_methodology"]["output_range"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## State Counts", ""])
    for state, count in summary["state_counts"].items():
        lines.append(f"- `{state}`: **{count}**")
    lines.extend(["", "## Blocker Counts", ""])
    for blocker, count in summary["blocker_counts"].items():
        lines.append(f"- `{blocker}`: **{count}**")
    lines.extend(["", "## Repo Queue", ""])
    lines.append("| Repo | State | Blockers | Next actions |")
    lines.append("|---|---|---|---|")
    for record in result["repo_records"]:
        lines.append(
            "| `{repo}` | `{state}` | `{blockers}` | {actions} |".format(
                repo=record["repo_key"],
                state=record["completion_state"],
                blockers=", ".join(record["blockers"]),
                actions="<br>".join(record["next_actions"]).replace("|", "/"),
            )
        )
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_repo_completion_dashboard_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    limit: int = 100,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_repo_completion_dashboard(
        repo_root,
        assets,
        generated_at=generated_at,
        limit=limit,
    )
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "dashboard_markdown": reports_dir / "repo_completion_dashboard.md",
        "dashboard_json": reports_dir / "repo_completion_dashboard.json",
    }
    atomic_write_text(paths["dashboard_markdown"], repo_completion_dashboard_markdown(result))
    atomic_write_text(paths["dashboard_json"], json_dumps(result, pretty=True) + "\n")
    return {
        "output_type": "generated_repo_completion_dashboard",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def _records_with_blocker(dashboard: dict[str, Any], blocker: str) -> list[dict[str, Any]]:
    return [record for record in dashboard["repo_records"] if blocker in record["blockers"]]


def _wave(
    *,
    sequence_order: int,
    wave_id: str,
    label: str,
    repo_records: list[dict[str, Any]],
    readiness_state: str,
    human_gate: str,
    generated_next_step: str,
    proof_to_advance: list[str],
    danger_if_misapplied: str,
    per_wave_repo_limit: int,
) -> dict[str, Any]:
    repo_keys = [record["repo_key"] for record in repo_records[:per_wave_repo_limit]]
    return {
        "sequence_order": sequence_order,
        "wave_id": wave_id,
        "label": label,
        "readiness_state": readiness_state,
        "repo_count": len(repo_records),
        "reported_repo_keys": repo_keys,
        "truncated_repo_count": max(0, len(repo_records) - len(repo_keys)),
        "human_gate": human_gate,
        "generated_next_step": generated_next_step,
        "proof_to_advance": proof_to_advance,
        "danger_if_misapplied": danger_if_misapplied,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "review_status": "generated_candidate",
    }


def build_repo_completion_wave_plan(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    generated_at: str | None = None,
    dashboard_limit: int = 500,
    per_wave_repo_limit: int = 25,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    dashboard = build_repo_completion_dashboard(
        repo_root,
        assets,
        generated_at=generated,
        limit=dashboard_limit,
    )
    records = list(dashboard["repo_records"])
    decision_summary = dashboard["summary"]["decision_summary"]
    content_records = _records_with_blocker(dashboard, "content_extract_human_gate")
    learning_records = _records_with_blocker(dashboard, "repo_learning_loop_missing")
    governance_records = _records_with_blocker(dashboard, "governance_dependency_surface_missing")
    ai_records = _records_with_blocker(dashboard, "ai_navigation_incomplete")
    validation_records = _records_with_blocker(dashboard, "validation_surface_not_observed")
    ready_records = [
        record
        for record in records
        if record["completion_state"] == "metadata_completion_ready_for_human_review"
    ]
    content_ready = (
        "ready_for_human_decision"
        if dashboard["summary"]["approval_packet_present"]
        and not decision_summary["content_read_approval_count"]
        else "already_approved_or_missing_packet"
    )
    waves = [
        _wave(
            sequence_order=1,
            wave_id="content_read_approval_wave",
            label="Approve bounded priority content extraction",
            repo_records=content_records,
            readiness_state=content_ready,
            human_gate="Lowell approves lesson-automation-decision-001 or regenerates the approval packet.",
            generated_next_step=(
                "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
                "lesson-automation-approval-packet"
            ),
            proof_to_advance=[
                "decision ledger has at least one reviewed content-read approval",
                "execution plan contains a ready_for_manual_run priority-content-extract entry",
                "content extraction writes generated observations only under processed/",
            ],
            danger_if_misapplied=(
                "Approving broad content reads without repo keys, categories, caps, and redaction can "
                "pull sensitive source content into generated outputs."
            ),
            per_wave_repo_limit=per_wave_repo_limit,
        ),
        _wave(
            sequence_order=2,
            wave_id="lesson_candidate_synthesis_wave",
            label="Synthesize lessons from approved priority observations",
            repo_records=content_records,
            readiness_state=(
                "waiting_for_priority_observations"
                if not (repo_root / "processed" / "learning" / "priority_content_observations.jsonl").exists()
                else "ready_for_generated_synthesis"
            ),
            human_gate="No new gate if observations already exist; otherwise depends on wave 1.",
            generated_next_step=(
                "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
                "priority-content-lessons --min-observations 1 --limit 100"
            ),
            proof_to_advance=[
                "priority_content_lesson_candidates.jsonl exists",
                "lesson candidates include applies_when, does_not_apply_when, and danger_if_misapplied",
                "no learning rule registry mutation occurred",
            ],
            danger_if_misapplied="Generated lesson candidates can be mistaken for reviewed learning rules.",
            per_wave_repo_limit=per_wave_repo_limit,
        ),
        _wave(
            sequence_order=3,
            wave_id="repo_learning_loop_selection_wave",
            label="Select repos for files-only learning-loop installation",
            repo_records=learning_records,
            readiness_state="awaiting_exact_repo_selection_and_source_write_permission",
            human_gate="Lowell selects exact repo paths and allows source mutation for files-only install.",
            generated_next_step=(
                "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
                "repo-learning-loop-scope --limit 50"
            ),
            proof_to_advance=[
                "decision ledger has reviewed source-mutation approval for exact repo paths",
                "learning-loop files exist in selected repos",
                "repo-local events remain data-only and append-only",
            ],
            danger_if_misapplied="Installing learning-loop files across active repos can create noisy source churn.",
            per_wave_repo_limit=per_wave_repo_limit,
        ),
        _wave(
            sequence_order=4,
            wave_id="governance_map_selection_wave",
            label="Select repo families for governance maps or child mirrors",
            repo_records=governance_records,
            readiness_state="awaiting_exact_family_selection_and_source_write_permission",
            human_gate="Lowell selects repo family, upstream authority, child mirrors, validators, and tests.",
            generated_next_step=(
                "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
                "governance-map-scope --limit 50"
            ),
            proof_to_advance=[
                "selected source repos include reviewed governance dependency map or mirror",
                "validators/tests exist for the map or mirror",
                "PR or change notes disclose governance dependency",
            ],
            danger_if_misapplied="Governance maps can imply authority if installed without source-owner review.",
            per_wave_repo_limit=per_wave_repo_limit,
        ),
        _wave(
            sequence_order=5,
            wave_id="ai_navigation_and_validation_review_wave",
            label="Review remaining AI navigation and validation gaps",
            repo_records=sorted(
                {record["repo_key"]: record for record in ai_records + validation_records}.values(),
                key=lambda item: item["repo_key"],
            ),
            readiness_state="metadata_review_needed",
            human_gate="Lowell decides whether gaps are real, intentionally absent, or scan-exclusion artifacts.",
            generated_next_step=(
                "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
                "repo-completion-dashboard --limit 100"
            ),
            proof_to_advance=[
                "AI navigation surfaces are observed or intentionally waived",
                "validation surfaces are observed or intentionally waived",
                "waivers are recorded as reviewed evidence, not inferred from absence",
            ],
            danger_if_misapplied="Metadata-only absence can be mistaken for proof that a repo lacks a surface.",
            per_wave_repo_limit=per_wave_repo_limit,
        ),
        _wave(
            sequence_order=6,
            wave_id="metadata_ready_review_wave",
            label="Human-review repos with no observed dashboard blockers",
            repo_records=ready_records,
            readiness_state="ready_for_human_review" if ready_records else "no_repos_ready",
            human_gate="Lowell verifies that generated metadata is sufficient for the repo's role.",
            generated_next_step=(
                "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend "
                "repo-buildout --repo <repo-key> --limit 10"
            ),
            proof_to_advance=[
                "human review confirms repo is covered for current scope",
                "any repo-specific buildout recommendations are accepted, deferred, or rejected",
                "no generated status is promoted to source truth",
            ],
            danger_if_misapplied="No dashboard blockers does not prove source completeness or repo quality.",
            per_wave_repo_limit=per_wave_repo_limit,
        ),
    ]
    return {
        "methodology_version": "repo-completion-wave-plan-v0.1",
        "generated_at": generated,
        "authority_boundary": (
            "Generated repo-completion wave plan only. This command orders dashboard blockers; "
            "it does not approve decisions, execute commands, read source contents, mutate source repos, "
            "call GitHub, call models, install hooks, or mark roadmap phases complete."
        ),
        "summary": {
            "repo_count": dashboard["summary"]["repo_count"],
            "wave_count": len(waves),
            "content_read_wave_repo_count": len(content_records),
            "learning_loop_wave_repo_count": len(learning_records),
            "governance_wave_repo_count": len(governance_records),
            "ai_navigation_or_validation_wave_repo_count": len(
                {record["repo_key"] for record in ai_records + validation_records}
            ),
            "metadata_ready_repo_count": len(ready_records),
            "source_repos_mutated": 0,
            "content_files_read": 0,
            "github_calls": 0,
            "model_calls": 0,
            "roadmap_phases_marked_complete": 0,
        },
        "dashboard_summary": dashboard["summary"],
        "status_methodology": {
            "type": "deterministic_wave_order",
            "inputs": [
                "repo completion dashboard blocker labels",
                "lesson automation decision summary",
                "presence of priority content observations",
            ],
            "order": [
                "content_read_approval_wave",
                "lesson_candidate_synthesis_wave",
                "repo_learning_loop_selection_wave",
                "governance_map_selection_wave",
                "ai_navigation_and_validation_review_wave",
                "metadata_ready_review_wave",
            ],
            "score_used": False,
        },
        "intentionally_not_done": [
            "decision approval",
            "command execution",
            "source file content reads",
            "source repo mutation",
            "learning-loop installation",
            "GitHub/API/model calls",
            "roadmap phase completion",
        ],
        "waves": waves,
        "review_status": "generated_candidate",
    }


def repo_completion_wave_plan_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Repo Completion Wave Plan",
        "",
        result["authority_boundary"],
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Repo count: **{summary['repo_count']}**",
        f"- Wave count: **{summary['wave_count']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- GitHub/model calls: **{summary['github_calls']}** / **{summary['model_calls']}**",
        "",
        "## Methodology",
        "",
        "This wave plan uses deterministic blocker labels from the repo completion dashboard, not calculated scores.",
        "",
        "Wave order:",
        "",
    ]
    for wave_id in result["status_methodology"]["order"]:
        lines.append(f"- `{wave_id}`")
    lines.extend(["", "## Waves", ""])
    for wave in result["waves"]:
        lines.extend(
            [
                f"### {wave['sequence_order']}. {wave['label']}",
                "",
                f"- Wave id: `{wave['wave_id']}`",
                f"- Readiness: `{wave['readiness_state']}`",
                f"- Repo count: **{wave['repo_count']}**",
                f"- Human gate: {wave['human_gate']}",
                f"- Danger if misapplied: {wave['danger_if_misapplied']}",
                "",
                "Next step:",
                "",
                "```powershell",
                wave["generated_next_step"],
                "```",
                "",
                "Proof to advance:",
            ]
        )
        for proof in wave["proof_to_advance"]:
            lines.append(f"- {proof}")
        if wave["reported_repo_keys"]:
            lines.extend(["", "Repos in this wave:"])
            for repo_key in wave["reported_repo_keys"]:
                lines.append(f"- `{repo_key}`")
        lines.append("")
    lines.extend(["## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_repo_completion_wave_plan_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    dashboard_limit: int = 500,
    per_wave_repo_limit: int = 25,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_repo_completion_wave_plan(
        repo_root,
        assets,
        generated_at=generated_at,
        dashboard_limit=dashboard_limit,
        per_wave_repo_limit=per_wave_repo_limit,
    )
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "wave_markdown": reports_dir / "repo_completion_wave_plan.md",
        "wave_json": reports_dir / "repo_completion_wave_plan.json",
    }
    atomic_write_text(paths["wave_markdown"], repo_completion_wave_plan_markdown(result))
    atomic_write_text(paths["wave_json"], json_dumps(result, pretty=True) + "\n")
    return {
        "output_type": "generated_repo_completion_wave_plan",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }


PROOF_CHECK_METHODOLOGY_VERSION = "repo-completion-proof-check-v0.1"
PROOF_CHECK_AUTHORITY_BOUNDARY = (
    "Generated repo-completion proof check only. This command reads the wave plan "
    "and generated decision/proof outputs; it does not approve decisions, execute "
    "commands, read source contents, mutate source repos, call GitHub, call models, "
    "install hooks, or mark roadmap phases complete."
)


def _approved_decision_count(decisions: list[dict[str, Any]], action_kind: str) -> int:
    return sum(
        1
        for item in decisions
        if item.get("decision") == "approve" and item.get("action_kind") == action_kind
    )


def _truthy_count(path: Path) -> int:
    return len(_load_jsonl(path))


def _lesson_candidate_context_bound(rows: list[dict[str, Any]]) -> bool:
    required = {
        "applies_when",
        "does_not_apply_when",
        "danger_if_misapplied",
        "counterfactual_better_order",
        "source_events",
        "context_tags",
    }
    return bool(rows) and all(
        all(row.get(field) for field in required)
        and row.get("review_status") == "generated_candidate"
        for row in rows
    )


def _proof_item(
    proof_id: str,
    label: str,
    *,
    satisfied: bool,
    evidence: dict[str, Any],
    missing_when_false: str,
) -> dict[str, Any]:
    return {
        "proof_id": proof_id,
        "label": label,
        "satisfied": satisfied,
        "evidence": evidence,
        "missing_when_false": "" if satisfied else missing_when_false,
    }


def _proof_status(
    wave: dict[str, Any],
    proof_items: list[dict[str, Any]],
    *,
    prior_waves_complete: bool,
) -> dict[str, Any]:
    satisfied = [item for item in proof_items if item["satisfied"]]
    missing = [item for item in proof_items if not item["satisfied"]]
    if not prior_waves_complete:
        status = "blocked_by_prior_wave"
    elif not missing:
        status = "complete"
    else:
        status = "blocked"
    return {
        "sequence_order": wave["sequence_order"],
        "wave_id": wave["wave_id"],
        "label": wave["label"],
        "proof_status": status,
        "satisfied_proof_ids": [item["proof_id"] for item in satisfied],
        "missing_proof_ids": [item["proof_id"] for item in missing],
        "missing_proof": [item["missing_when_false"] for item in missing],
        "proof_items": proof_items,
        "human_gate": wave["human_gate"],
        "generated_next_step": wave["generated_next_step"],
        "danger_if_misapplied": wave["danger_if_misapplied"],
        "repo_count": wave["repo_count"],
        "reported_repo_keys": wave["reported_repo_keys"],
        "review_status": "generated_candidate",
    }


def build_repo_completion_proof_check(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    generated_at: str | None = None,
    dashboard_limit: int = 500,
    per_wave_repo_limit: int = 25,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    wave_plan = build_repo_completion_wave_plan(
        repo_root,
        assets,
        generated_at=generated,
        dashboard_limit=dashboard_limit,
        per_wave_repo_limit=per_wave_repo_limit,
    )
    learning_dir = data_relative_path(repo_root, Path("processed") / "learning")
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    decisions = _load_jsonl(learning_dir / "lesson_automation_action_decisions.jsonl")
    execution_plan = _load_json(reports_dir / "lesson_automation_execution_plan.json") or {}
    observations = _load_jsonl(learning_dir / "priority_content_observations.jsonl")
    lesson_candidates = _load_jsonl(learning_dir / "priority_content_lesson_candidates.jsonl")
    promotion_candidates = _load_jsonl(learning_dir / "learning_rule_promotion_candidates.jsonl")
    decision_summary = _decision_summary(decisions)
    execution_summary = execution_plan.get("summary") or {}
    blocker_counts = wave_plan["dashboard_summary"].get("blocker_counts") or {}

    proof_by_wave = {
        "content_read_approval_wave": [
            _proof_item(
                "content_read_approval_recorded",
                "Decision ledger has at least one reviewed content-read approval.",
                satisfied=decision_summary["content_read_approval_count"] > 0,
                evidence={
                    "content_read_approval_count": decision_summary[
                        "content_read_approval_count"
                    ],
                    "approved_count": decision_summary["approved_count"],
                },
                missing_when_false=(
                    "Approve one bounded content-read decision row with exact repo keys, "
                    "categories, byte/file caps, approval id, and redaction."
                ),
            ),
            _proof_item(
                "priority_extract_execution_plan_ready",
                "Execution plan has at least one ready priority-content extract entry.",
                satisfied=int(execution_summary.get("ready_for_manual_run_count") or 0) > 0,
                evidence={
                    "execution_plan_present": bool(execution_plan),
                    "ready_for_manual_run_count": int(
                        execution_summary.get("ready_for_manual_run_count") or 0
                    ),
                },
                missing_when_false=(
                    "Regenerate the execution plan after a reviewed content-read approval."
                ),
            ),
            _proof_item(
                "priority_observations_present",
                "Content extraction wrote generated observations under processed/.",
                satisfied=bool(observations),
                evidence={"priority_content_observation_count": len(observations)},
                missing_when_false=(
                    "Run the approved bounded priority-content-extract command; keep "
                    "observations generated-only under processed/."
                ),
            ),
        ],
        "lesson_candidate_synthesis_wave": [
            _proof_item(
                "priority_lesson_candidates_present",
                "Priority content lesson candidates exist.",
                satisfied=bool(lesson_candidates),
                evidence={"priority_content_lesson_candidate_count": len(lesson_candidates)},
                missing_when_false=(
                    "Run priority-content-lessons after approved observations exist."
                ),
            ),
            _proof_item(
                "lesson_candidates_context_bound",
                "Lesson candidates include context-bound safety fields and candidate status.",
                satisfied=_lesson_candidate_context_bound(lesson_candidates),
                evidence={
                    "checked_candidate_count": len(lesson_candidates),
                    "required_fields": [
                        "applies_when",
                        "does_not_apply_when",
                        "danger_if_misapplied",
                        "counterfactual_better_order",
                        "source_events",
                        "context_tags",
                    ],
                },
                missing_when_false=(
                    "Regenerate or fix lesson candidates so each has applies_when, "
                    "does_not_apply_when, danger_if_misapplied, counterfactual order, "
                    "source events, context tags, and generated_candidate status."
                ),
            ),
            _proof_item(
                "learning_rules_not_promoted_by_synthesis",
                "Lesson synthesis has not promoted learning rules automatically.",
                satisfied=not any(row.get("registry_mutated") for row in promotion_candidates),
                evidence={
                    "promotion_candidate_count": len(promotion_candidates),
                    "registry_mutated_flags_seen": [
                        row.get("registry_mutated")
                        for row in promotion_candidates
                        if row.get("registry_mutated")
                    ],
                },
                missing_when_false=(
                    "Stop and review promotion outputs; registry mutation must be a "
                    "separate human-approved change."
                ),
            ),
        ],
        "repo_learning_loop_selection_wave": [
            _proof_item(
                "source_mutation_approval_for_learning_loop_recorded",
                "A reviewed files-only learning-loop source-mutation approval exists.",
                satisfied=_approved_decision_count(decisions, "source_repo_files_only_install") > 0
                and decision_summary["source_mutation_approval_count"] > 0,
                evidence={
                    "approved_files_only_install_count": _approved_decision_count(
                        decisions, "source_repo_files_only_install"
                    ),
                    "source_mutation_approval_count": decision_summary[
                        "source_mutation_approval_count"
                    ],
                },
                missing_when_false=(
                    "Select exact repos and approve files-only learning-loop installation "
                    "before writing any source-repo files."
                ),
            ),
            _proof_item(
                "learning_loop_surfaces_observed_or_waived",
                "Learning-loop missing blockers are resolved or explicitly waived.",
                satisfied=int(blocker_counts.get("repo_learning_loop_missing") or 0) == 0,
                evidence={
                    "repo_learning_loop_missing_count": int(
                        blocker_counts.get("repo_learning_loop_missing") or 0
                    )
                },
                missing_when_false=(
                    "Install files-only learning-loop surfaces in selected repos or record "
                    "human waivers; then refresh the catalog/dashboard."
                ),
            ),
        ],
        "governance_map_selection_wave": [
            _proof_item(
                "source_mutation_approval_for_governance_recorded",
                "A reviewed governance-map source-mutation approval exists.",
                satisfied=_approved_decision_count(decisions, "source_repo_governance_adoption") > 0
                and decision_summary["source_mutation_approval_count"] > 0,
                evidence={
                    "approved_governance_adoption_count": _approved_decision_count(
                        decisions, "source_repo_governance_adoption"
                    ),
                    "source_mutation_approval_count": decision_summary[
                        "source_mutation_approval_count"
                    ],
                },
                missing_when_false=(
                    "Select exact repo families and approve governance-map/mirror writes "
                    "before changing source repos."
                ),
            ),
            _proof_item(
                "governance_surfaces_observed_or_waived",
                "Governance dependency blockers are resolved or explicitly waived.",
                satisfied=int(blocker_counts.get("governance_dependency_surface_missing") or 0)
                == 0,
                evidence={
                    "governance_dependency_surface_missing_count": int(
                        blocker_counts.get("governance_dependency_surface_missing") or 0
                    )
                },
                missing_when_false=(
                    "Install or review governance maps/mirrors for selected repo families, "
                    "or record human waivers; then refresh the catalog/dashboard."
                ),
            ),
        ],
        "ai_navigation_and_validation_review_wave": [
            _proof_item(
                "ai_navigation_gaps_resolved_or_waived",
                "AI navigation blockers are resolved or explicitly waived.",
                satisfied=int(blocker_counts.get("ai_navigation_incomplete") or 0) == 0,
                evidence={
                    "ai_navigation_incomplete_count": int(
                        blocker_counts.get("ai_navigation_incomplete") or 0
                    )
                },
                missing_when_false=(
                    "Review AI front doors, TOCs, and repo contracts; add surfaces or "
                    "record human waivers."
                ),
            ),
            _proof_item(
                "validation_gaps_resolved_or_waived",
                "Validation blockers are resolved or explicitly waived.",
                satisfied=int(blocker_counts.get("validation_surface_not_observed") or 0) == 0,
                evidence={
                    "validation_surface_not_observed_count": int(
                        blocker_counts.get("validation_surface_not_observed") or 0
                    )
                },
                missing_when_false=(
                    "Review tests/validators for remaining repos; add surfaces or record "
                    "human waivers."
                ),
            ),
        ],
        "metadata_ready_review_wave": [
            _proof_item(
                "metadata_ready_repos_present",
                "At least one repo is metadata-ready for human review.",
                satisfied=int(wave_plan["summary"]["metadata_ready_repo_count"]) > 0,
                evidence={
                    "metadata_ready_repo_count": int(
                        wave_plan["summary"]["metadata_ready_repo_count"]
                    )
                },
                missing_when_false=(
                    "Resolve earlier blockers before final metadata-ready review."
                ),
            ),
            _proof_item(
                "metadata_ready_human_review_recorded",
                "Human review has accepted, deferred, or rejected metadata-ready repo status.",
                satisfied=False,
                evidence={"human_review_record_path": ""},
                missing_when_false=(
                    "Record explicit human review evidence for metadata-ready repos before "
                    "treating this wave as complete."
                ),
            ),
        ],
    }

    wave_statuses: list[dict[str, Any]] = []
    prior_complete = True
    for wave in wave_plan["waves"]:
        status = _proof_status(
            wave,
            proof_by_wave.get(wave["wave_id"], []),
            prior_waves_complete=prior_complete,
        )
        wave_statuses.append(status)
        if status["proof_status"] != "complete":
            prior_complete = False

    current = next(
        (wave for wave in wave_statuses if wave["proof_status"] != "complete"),
        None,
    )
    complete_count = sum(1 for wave in wave_statuses if wave["proof_status"] == "complete")
    return {
        "methodology_version": PROOF_CHECK_METHODOLOGY_VERSION,
        "generated_at": generated,
        "authority_boundary": PROOF_CHECK_AUTHORITY_BOUNDARY,
        "summary": {
            "wave_count": len(wave_statuses),
            "complete_wave_count": complete_count,
            "blocked_wave_count": len(wave_statuses) - complete_count,
            "current_wave_id": current["wave_id"] if current else "",
            "current_wave_status": current["proof_status"] if current else "complete",
            "safe_to_advance": current is None,
            "source_repos_mutated": 0,
            "content_files_read": 0,
            "github_calls": 0,
            "model_calls": 0,
            "roadmap_phases_marked_complete": 0,
        },
        "checked_inputs": [
            "repo completion wave plan",
            "repo completion dashboard summary",
            "processed/learning/lesson_automation_action_decisions.jsonl",
            "processed/reports/lesson_automation_execution_plan.json",
            "processed/learning/priority_content_observations.jsonl",
            "processed/learning/priority_content_lesson_candidates.jsonl",
            "processed/learning/learning_rule_promotion_candidates.jsonl",
        ],
        "intentionally_not_done": [
            "decision approval",
            "command execution",
            "source file content reads",
            "source repo mutation",
            "learning-loop installation",
            "GitHub/API/model calls",
            "roadmap phase completion",
        ],
        "current_wave": current or {},
        "wave_statuses": wave_statuses,
        "decision_summary": decision_summary,
        "execution_summary": execution_summary,
        "artifact_counts": {
            "priority_content_observations": _truthy_count(
                learning_dir / "priority_content_observations.jsonl"
            ),
            "priority_content_lesson_candidates": _truthy_count(
                learning_dir / "priority_content_lesson_candidates.jsonl"
            ),
            "learning_rule_promotion_candidates": _truthy_count(
                learning_dir / "learning_rule_promotion_candidates.jsonl"
            ),
        },
        "applies_when": [
            "A future agent needs to know whether a repo-completion wave has proof to advance.",
            "The work must avoid confusing a generated plan with completed execution.",
        ],
        "does_not_apply_when": [
            "The user has explicitly selected and approved one gated action to execute now.",
            "The catalog or generated scope reports are stale and need approved refresh first.",
        ],
        "danger_if_misapplied": (
            "A proof check can be mistaken for authorization. It only reports missing or "
            "present evidence and never grants permission to read content or mutate repos."
        ),
        "review_status": "generated_candidate",
    }


def repo_completion_proof_check_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    current = result["current_wave"]
    lines = [
        "# Repo Completion Proof Check",
        "",
        result["authority_boundary"],
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Complete waves: **{summary['complete_wave_count']} / {summary['wave_count']}**",
        f"- Current wave: `{summary['current_wave_id'] or 'none'}`",
        f"- Current status: `{summary['current_wave_status']}`",
        f"- Safe to advance all waves: **{summary['safe_to_advance']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- GitHub/model calls: **{summary['github_calls']}** / **{summary['model_calls']}**",
        "",
        "## Current Blocker",
        "",
    ]
    if current:
        lines.extend(
            [
                f"- Wave: `{current['wave_id']}`",
                f"- Label: {current['label']}",
                f"- Human gate: {current['human_gate']}",
                f"- Danger if misapplied: {current['danger_if_misapplied']}",
                "",
                "Missing proof:",
            ]
        )
        for item in current["missing_proof"]:
            lines.append(f"- {item}")
        lines.extend(["", "Generated next step:", "", "```powershell"])
        lines.append(current["generated_next_step"])
        lines.extend(["```", ""])
    else:
        lines.append("No blocked wave found; all proof items are satisfied.")
        lines.append("")

    lines.extend(["## Wave Proof Status", ""])
    lines.append("| Order | Wave | Status | Satisfied | Missing |")
    lines.append("|---:|---|---|---|---|")
    for wave in result["wave_statuses"]:
        lines.append(
            "| {order} | `{wave_id}` | `{status}` | `{satisfied}` | `{missing}` |".format(
                order=wave["sequence_order"],
                wave_id=wave["wave_id"],
                status=wave["proof_status"],
                satisfied=", ".join(wave["satisfied_proof_ids"]),
                missing=", ".join(wave["missing_proof_ids"]),
            )
        )
    lines.extend(["", "## Checked Inputs", ""])
    for item in result["checked_inputs"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Context Boundaries", ""])
    lines.append("Applies when:")
    for item in result["applies_when"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Does not apply when:")
    for item in result["does_not_apply_when"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"Danger if misapplied: {result['danger_if_misapplied']}")
    lines.append("")
    return "\n".join(lines)


def write_repo_completion_proof_check_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    *,
    dashboard_limit: int = 500,
    per_wave_repo_limit: int = 25,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_repo_completion_proof_check(
        repo_root,
        assets,
        generated_at=generated_at,
        dashboard_limit=dashboard_limit,
        per_wave_repo_limit=per_wave_repo_limit,
    )
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "proof_markdown": reports_dir / "repo_completion_proof_check.md",
        "proof_json": reports_dir / "repo_completion_proof_check.json",
    }
    atomic_write_text(paths["proof_markdown"], repo_completion_proof_check_markdown(result))
    atomic_write_text(paths["proof_json"], json_dumps(result, pretty=True) + "\n")
    return {
        "output_type": "generated_repo_completion_proof_check",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }
