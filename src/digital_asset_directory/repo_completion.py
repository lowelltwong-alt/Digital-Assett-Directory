from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import AssetRecord
from .repo_buildout import build_repo_groups
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
    reports_dir = repo_root / "processed" / "reports"
    priority_scope = _load_json(reports_dir / "priority_content_extract_scope.json")
    learning_scope = _load_json(reports_dir / "repo_learning_loop_install_scope.json")
    governance_scope = _load_json(reports_dir / "governance_map_adoption_scope.json")
    ci_scope = _load_json(reports_dir / "ci_release_artifact_scope.json")
    approval_packet = _load_json(reports_dir / "lesson_automation_approval_packet.json")
    execution_plan = _load_json(reports_dir / "lesson_automation_execution_plan.json")
    decisions = _load_jsonl(repo_root / "processed" / "learning" / "lesson_automation_action_decisions.jsonl")
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
    reports_dir = repo_root / "processed" / "reports"
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
    reports_dir = repo_root / "processed" / "reports"
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
