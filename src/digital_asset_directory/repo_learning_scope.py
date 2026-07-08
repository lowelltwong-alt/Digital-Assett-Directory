from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .config import LocalSource
from .models import AssetRecord
from .transport import data_relative_path
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "repo-learning-loop-install-scope-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated repo learning-loop installation scope only. This command uses catalog metadata "
    "and logical paths to recommend candidate repos for a later files-only learning-loop install. "
    "It does not write to downstream repos, install hooks, read source file contents, recurse "
    "through source filesystems, call GitHub, call models, or promote generated findings to truth."
)
PRIORITY_FORMULA = (
    "priority_score = 100 * (0.35*learning_gap + 0.20*ai_navigation_readiness + "
    "0.15*validation_readiness + 0.15*governance_readiness + "
    "0.10*configured_source_path + 0.05*low_noise_bonus)"
)

LEARNING_PATHS = {
    ".digital-asset-directory/learning/readme.md",
    ".digital-asset-directory/learning/context-tags.yaml",
    ".digital-asset-directory/learning/events.jsonl",
}
TARGET_WRITE_PATHS = [
    ".digital-asset-directory/learning/README.md",
    ".digital-asset-directory/learning/context-tags.yaml",
    ".digital-asset-directory/learning/events.jsonl",
]


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


def _repo_label(key: str) -> str:
    parts = [part for part in PurePosixPath(key.replace("\\", "/")).parts if part not in {"."}]
    return parts[-1] if parts else key


def _is_noise_path(path: str) -> bool:
    lowered = _normalized(path)
    return any(
        term in lowered
        for term in (
            ".git/",
            "node_modules/",
            ".venv/",
            "__pycache__/",
            ".pytest-tmp-root/",
            "_codex_worktrees/",
            ".claude/worktrees/",
            "/tmp/",
            "/temp/",
            "processed/",
            "raw/",
            "state/",
            "audit/events/",
        )
    )


def _is_noise_repo(repo_key: str, assets: list[AssetRecord]) -> bool:
    lowered = _normalized(repo_key)
    if lowered.endswith("/.") or lowered in {"", "."}:
        return True
    if _is_noise_path(lowered):
        return True
    return any(asset.metadata.get("instance_class") in {"temp", "worktree"} for asset in assets)


def _build_repo_groups_by_prefix(assets: list[AssetRecord]) -> dict[str, list[AssetRecord]]:
    repo_assets = [asset for asset in assets if asset.asset_type == "repository"]
    repo_keys = sorted(
        {_normalized(asset.logical_path) for asset in repo_assets},
        key=lambda key: (-len(key), key),
    )
    groups: dict[str, list[AssetRecord]] = {key: [] for key in repo_keys}
    for asset in assets:
        logical = _normalized(asset.logical_path)
        if asset.asset_type == "repository" and logical in groups:
            groups[logical].append(asset)
            continue
        for key in repo_keys:
            if logical == key or logical.startswith(f"{key}/"):
                groups[key].append(asset)
                break
    return {key: group for key, group in groups.items() if group}


def _configured_source_for_repo(repo_key: str, local_sources: list[LocalSource]) -> LocalSource | None:
    normalized = _normalized(repo_key)
    for source in sorted(local_sources, key=lambda item: len(item.path_alias), reverse=True):
        alias = _normalized(source.path_alias)
        if normalized == alias or normalized.startswith(f"{alias}/"):
            return source
    return None


def _resolved_repo_path(repo_key: str, source: LocalSource | None) -> str:
    if source is None:
        return ""
    normalized = _normalized(repo_key)
    alias = _normalized(source.path_alias)
    if normalized == alias:
        rel = ""
    elif normalized.startswith(f"{alias}/"):
        rel = normalized[len(alias) + 1 :]
    else:
        return ""
    return str(source.path.joinpath(*PurePosixPath(rel).parts))


def _surface_flags(repo_key: str, assets: list[AssetRecord]) -> dict[str, Any]:
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
    flags = {
        "has_repo_contract": bool({"agents.md", "claude.md"} & observed),
        "has_ai_front_door": "ai_front_door.md" in observed,
        "has_ai_toc": bool({"ai_table_of_contents.md", "ai_toc.md"} & observed),
        "has_learning_readme": ".digital-asset-directory/learning/readme.md" in observed,
        "has_learning_context_tags": ".digital-asset-directory/learning/context-tags.yaml" in observed,
        "has_learning_events": ".digital-asset-directory/learning/events.jsonl" in observed,
        "has_governance_surface": any(
            term in path
            for path in observed
            for term in ("governance", "roadmap", "gate", "security", "privacy")
        ),
        "has_validation_surface": any(
            term in path
            for path in observed
            for term in ("tests/", "test_", "validate", ".github/workflows", "noxfile.py", "pytest.ini")
        ),
    }
    flags["learning_surface_count"] = sum(
        1
        for path in LEARNING_PATHS
        if path in observed
    )
    return flags


def _priority_components(flags: dict[str, Any], resolved_path: str) -> dict[str, float]:
    learning_count = int(flags["learning_surface_count"])
    if flags["has_learning_events"]:
        learning_gap = 0.0
    elif learning_count:
        learning_gap = 0.6
    else:
        learning_gap = 1.0
    ai_navigation_readiness = (
        sum(
            1
            for key in ("has_repo_contract", "has_ai_front_door", "has_ai_toc")
            if flags[key]
        )
        / 3
    )
    validation_readiness = 1.0 if flags["has_validation_surface"] else 0.25
    governance_readiness = 1.0 if flags["has_governance_surface"] else 0.25
    configured_source_path = 1.0 if resolved_path else 0.0
    low_noise_bonus = 1.0
    return {
        "learning_gap": learning_gap,
        "ai_navigation_readiness": round(ai_navigation_readiness, 3),
        "validation_readiness": validation_readiness,
        "governance_readiness": governance_readiness,
        "configured_source_path": configured_source_path,
        "low_noise_bonus": low_noise_bonus,
    }


def _priority_score(components: dict[str, float]) -> float:
    score = 100 * (
        0.35 * components["learning_gap"]
        + 0.20 * components["ai_navigation_readiness"]
        + 0.15 * components["validation_readiness"]
        + 0.15 * components["governance_readiness"]
        + 0.10 * components["configured_source_path"]
        + 0.05 * components["low_noise_bonus"]
    )
    return round(score, 2)


def build_repo_learning_loop_install_scope(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    groups = _build_repo_groups_by_prefix(assets)
    skipped_noise_repos = 0
    candidates: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for repo_key, group_assets in sorted(groups.items()):
        if not any(asset.asset_type == "repository" for asset in group_assets):
            continue
        if _is_noise_repo(repo_key, group_assets):
            skipped_noise_repos += 1
            continue
        repo_asset = next((asset for asset in group_assets if asset.asset_type == "repository"), None)
        source = _configured_source_for_repo(repo_key, local_sources)
        resolved_path = _resolved_repo_path(repo_key, source)
        flags = _surface_flags(repo_key, group_assets)
        if flags["has_learning_events"]:
            status = "already_has_event_log"
        elif flags["learning_surface_count"]:
            status = "partial_learning_loop_surface"
        else:
            status = "missing_learning_loop_surface"
        status_counts[status] += 1
        components = _priority_components(flags, resolved_path)
        proposed_command = (
            f'$env:PYTHONPATH="src"; python -m digital_asset_directory.cli '
            f'agent install-learning-loop --repo "{resolved_path}" --mode files-only'
            if resolved_path
            else ""
        )
        candidates.append(
            {
                "repo_key": repo_key,
                "repo_label": repo_asset.title if repo_asset else _repo_label(repo_key),
                "repo_asset_id": repo_asset.asset_id if repo_asset else "",
                "asset_count": len(group_assets),
                "configured_source_id": source.id if source else "",
                "resolved_repo_path": resolved_path,
                "install_status": status,
                "surface_flags": flags,
                "priority_score": _priority_score(components),
                "priority_components": components,
                "priority_formula": PRIORITY_FORMULA,
                "target_write_paths": list(TARGET_WRITE_PATHS),
                "proposed_install_command": proposed_command,
                "human_gate_required": True,
                "review_status": "generated_candidate",
                "authority_boundary": AUTHORITY_BOUNDARY,
                "applies_when": [
                    "A human is selecting repos for files-only DAD learning-loop installation.",
                    "The repo is in the approved local catalog and should preserve lessons as data.",
                ],
                "does_not_apply_when": [
                    "The repo is active and the user has not approved writing files into it.",
                    "The repo already has a reviewed equivalent learning-loop mechanism.",
                ],
                "danger_if_misapplied": (
                    "Installing learning-loop files without per-repo approval can mutate active repos "
                    "and create process noise. This candidate is only an approval scope."
                ),
            }
        )
    candidates = sorted(
        candidates,
        key=lambda item: (
            item["install_status"] == "already_has_event_log",
            -float(item["priority_score"]),
            item["repo_key"],
        ),
    )
    selected = candidates[:limit]
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "priority_formula": PRIORITY_FORMULA,
        "summary": {
            "catalog_asset_count": len(assets),
            "candidate_repo_count_before_limit": len(candidates),
            "reported_repo_count": len(selected),
            "skipped_noise_repo_count": skipped_noise_repos,
            "status_counts": dict(sorted(status_counts.items())),
            "source_repos_mutated": 0,
            "hooks_installed": 0,
            "content_files_read": 0,
        },
        "target_write_paths": list(TARGET_WRITE_PATHS),
        "intentionally_not_done": [
            "downstream repo writes",
            "hook installation",
            "source file content reads",
            "fresh filesystem recursion",
            "GitHub or model calls",
            "automatic event creation",
        ],
        "approval_question": (
            "Which repo keys should receive files-only DAD learning-loop installation?"
        ),
        "install_command_template": (
            "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli "
            "agent install-learning-loop --repo <resolved-repo-path> --mode files-only"
        ),
        "repo_candidates": selected,
        "review_status": "generated_candidate",
    }


def repo_learning_loop_install_scope_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Repo Learning Loop Install Scope",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Scan id: `{result['scan_id']}`",
        f"- Reported repos: **{summary['reported_repo_count']}**",
        f"- Candidate repos before limit: **{summary['candidate_repo_count_before_limit']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Hooks installed: **{summary['hooks_installed']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        "",
        "## Priority Formula",
        "",
        f"`{result['priority_formula']}`",
        "",
        "This is a review priority only. It does not prove repo value or authorize installation.",
        "",
        "## Target Files If Later Approved",
        "",
    ]
    for path in result["target_write_paths"]:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Status Counts", ""])
    for status, count in summary["status_counts"].items():
        lines.append(f"- `{status}`: **{count}**")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Repo Candidates", ""])
    lines.append(
        "| Priority | Status | Repo | Existing surfaces | Proposed command |"
    )
    lines.append("|---:|---|---|---|---|")
    for candidate in result["repo_candidates"]:
        flags = candidate["surface_flags"]
        surfaces = ", ".join(
            key.replace("has_", "")
            for key in (
                "has_repo_contract",
                "has_ai_front_door",
                "has_ai_toc",
                "has_learning_readme",
                "has_learning_context_tags",
                "has_learning_events",
                "has_validation_surface",
                "has_governance_surface",
            )
            if flags[key]
        ) or "none"
        command = candidate["proposed_install_command"] or "manual path resolution required"
        lines.append(
            "| {score:.2f} | `{status}` | `{repo}` | {surfaces} | `{command}` |".format(
                score=float(candidate["priority_score"]),
                status=candidate["install_status"],
                repo=candidate["repo_key"],
                surfaces=surfaces.replace("|", "/"),
                command=command.replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Red-Team",
            "",
            "- This report is an approval scope, not an installation.",
            "- Do not install into active repos unless Lowell explicitly selects the repo.",
            "- Files-only mode writes learning templates and an append-only event log path; hooks remain out of scope.",
            "- Repo-local events are untrusted data and must not be executed.",
            "",
        ]
    )
    return "\n".join(lines)


def repo_learning_loop_approval_prompt_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Fresh-Eyes Prompt: Repo Learning Loop Install Scope",
        "",
        "Review this DAD-generated scope before any repo-local learning-loop files are installed.",
        "",
        "Constraints:",
        "",
        "- Do not mutate any target repo during review.",
        "- Do not install hooks.",
        "- Do not read source file contents.",
        "- Treat priority scores as review routing only.",
        "",
        "Questions:",
        "",
        "1. Which repos should receive files-only learning-loop installation first?",
        "2. Which active repos should be deferred because they are changing?",
        "3. Which repos already have equivalent learning capture that should not be duplicated?",
        "4. What post-install event should be recorded first in each approved repo?",
        "5. What would prove that repo-local learning events improved future DAD lesson automation?",
        "",
        "Summary:",
        "",
        f"- Reported repos: {result['summary']['reported_repo_count']}",
        f"- Candidate repos before limit: {result['summary']['candidate_repo_count_before_limit']}",
        f"- Source repos mutated by this scope: {result['summary']['source_repos_mutated']}",
        "",
        "Top candidates:",
        "",
    ]
    for candidate in result["repo_candidates"][:10]:
        lines.append(
            f"- `{candidate['repo_key']}`: priority {candidate['priority_score']}, "
            f"status `{candidate['install_status']}`"
        )
    lines.append("")
    return "\n".join(lines)


def write_repo_learning_loop_install_scope_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_repo_learning_loop_install_scope(
        repo_root,
        assets,
        local_sources,
        scan_id=scan_id,
        limit=limit,
        generated_at=generated_at,
    )
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "scope_markdown": reports_dir / "repo_learning_loop_install_scope.md",
        "scope_json": reports_dir / "repo_learning_loop_install_scope.json",
        "approval_prompt": reports_dir / "repo_learning_loop_install_approval_prompt.md",
    }
    atomic_write_text(paths["scope_markdown"], repo_learning_loop_install_scope_markdown(result))
    atomic_write_text(paths["scope_json"], json_dumps(result, pretty=True) + "\n")
    atomic_write_text(paths["approval_prompt"], repo_learning_loop_approval_prompt_markdown(result))
    return {
        "output_type": "generated_candidate_scope",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }
