from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .config import LocalSource
from .models import AssetRecord
from .repo_buildout import build_repo_groups
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "governance-map-adoption-scope-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated governance-map adoption scope only. This command uses catalog metadata "
    "and logical paths to recommend candidate repos or repo families for later human-approved "
    "governance dependency maps, child mirrors, validators, tests, and discovery surfaces. "
    "It does not write to downstream repos, read source file contents, recurse through source "
    "filesystems, call GitHub, call models, install hooks, or promote generated findings to truth."
)
PRIORITY_FORMULA = (
    "priority_score = 100 * (0.25*family_size_signal + 0.25*governance_gap + "
    "0.20*downstream_likelihood + 0.15*ai_navigation_readiness + "
    "0.10*validation_readiness + 0.05*configured_source_path)"
)

UPSTREAM_MAP_PATHS = {
    "governance/governance_dependency_map.yaml",
    "governance/governance_dependency_map.yml",
    "governance/GOVERNANCE_DEPENDENCY_MAP.yaml".lower(),
    "governance/GOVERNANCE_DEPENDENCY_MAP.yml".lower(),
    "governance_dependency_map.yaml",
    "governance_dependency_map.yml",
    "GOVERNANCE_DEPENDENCY_MAP.yaml".lower(),
}
CHILD_MIRROR_PATHS = {
    ".ai/control/governance_dependency_map_mirror.yaml",
    ".ai/control/governance_dependency_map_mirror.yml",
    ".ai/control/GOVERNANCE_DEPENDENCY_MAP_MIRROR.yaml".lower(),
    ".ai/control/GOVERNANCE_DEPENDENCY_MAP_MIRROR.yml".lower(),
    "governance/governance_dependency_map_mirror.yaml",
    "governance/governance_dependency_map_mirror.yml",
}
VALIDATOR_PATH_TERMS = (
    "validate_governance_dependency_map",
    "validate_governance_map",
    "governance_dependency_map_validator",
)
TEST_PATH_TERMS = (
    "test_governance_dependency_map",
    "test_governance_map",
    "governance_dependency_map.test",
)
PR_DISCLOSURE_PATHS = {
    ".github/pull_request_template.md",
    ".github/pull_request_template/pull_request_template.md",
    "pull_request_template.md",
    "pr_description_required_sections.md",
    "docs/pr_description_required_sections.md",
}
ADOPTION_CHECKLIST_PATHS = {
    "governance/adoption_checklist.md",
    "governance/handoff_checklist.md",
    "adoption_checklist.md",
    "handoff_checklist.md",
}
TARGET_TEMPLATE_PATHS = [
    "governance/GOVERNANCE_DEPENDENCY_MAP.yaml",
    ".ai/control/governance_dependency_map_mirror.yaml",
    "AI_FRONT_DOOR.md governance row",
    "AI_TABLE_OF_CONTENTS.md governance row",
    "AGENTS.md/CLAUDE.md governance block",
    ".github/PULL_REQUEST_TEMPLATE.md governance disclosure section",
    "scripts/validate_governance_dependency_map.py",
    "tests/test_governance_dependency_map.py",
]


def _normalized(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/").lower()


def _path_parts(value: str) -> tuple[str, ...]:
    return tuple(part for part in PurePosixPath(_normalized(value)).parts if part)


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
    parts = _path_parts(key)
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


def _family_key(repo_key: str) -> str:
    parts = _path_parts(repo_key)
    if len(parts) >= 2 and parts[0] in {"git-projects", "github", "repos"}:
        return "/".join(parts[:2])
    if len(parts) >= 2:
        return "/".join(parts[:-1])
    return parts[0] if parts else "."


def _family_counts(groups: dict[str, list[AssetRecord]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for repo_key, assets in groups.items():
        if any(asset.asset_type == "repository" for asset in assets) and not _is_noise_repo(
            repo_key, assets
        ):
            counts[_family_key(repo_key)] += 1
    return counts


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
    joined = " ".join(sorted(observed))
    flags = {
        "has_repo_contract": bool({"agents.md", "claude.md"} & observed),
        "has_ai_front_door": "ai_front_door.md" in observed,
        "has_ai_toc": bool({"ai_table_of_contents.md", "ai_toc.md"} & observed),
        "has_upstream_map": bool(UPSTREAM_MAP_PATHS & observed),
        "has_child_mirror": bool(CHILD_MIRROR_PATHS & observed),
        "has_governance_validator": any(term in joined for term in VALIDATOR_PATH_TERMS),
        "has_governance_test": any(term in joined for term in TEST_PATH_TERMS),
        "has_pr_disclosure": bool(PR_DISCLOSURE_PATHS & observed),
        "has_adoption_checklist": bool(ADOPTION_CHECKLIST_PATHS & observed),
        "has_general_governance_surface": any(
            term in joined
            for term in (
                "governance",
                "authority",
                "boundary",
                "gate",
                "policy",
                "control",
            )
        ),
        "sample_paths": sorted(relative_paths)[:12],
    }
    flags["governance_surface_count"] = sum(
        1
        for key in (
            "has_upstream_map",
            "has_child_mirror",
            "has_governance_validator",
            "has_governance_test",
            "has_pr_disclosure",
            "has_adoption_checklist",
        )
        if flags[key]
    )
    return flags


def _adoption_status(flags: dict[str, Any]) -> str:
    has_map = bool(flags["has_upstream_map"])
    has_mirror = bool(flags["has_child_mirror"])
    has_validator = bool(flags["has_governance_validator"] or flags["has_governance_test"])
    if has_map and has_mirror and has_validator:
        return "map_and_mirror_with_validation_observed"
    if has_map and has_validator:
        return "upstream_map_with_validation_observed"
    if has_mirror and has_validator:
        return "child_mirror_with_validation_observed"
    if has_map or has_mirror:
        return "partial_map_or_mirror_observed"
    if flags["has_general_governance_surface"]:
        return "governance_surface_without_dependency_map"
    return "missing_governance_dependency_surface"


def _proposed_role(status: str, family_repo_count: int, flags: dict[str, Any]) -> str:
    if flags["has_upstream_map"]:
        return "upstream_map_maintenance_candidate"
    if flags["has_child_mirror"]:
        return "child_mirror_maintenance_candidate"
    if family_repo_count > 1 and flags["has_general_governance_surface"]:
        return "repo_family_map_candidate"
    if family_repo_count > 1:
        return "repo_family_review_candidate"
    return "single_repo_governance_review_candidate"


def _missing_surface_ids(flags: dict[str, Any]) -> list[str]:
    mapping = {
        "upstream_map": "has_upstream_map",
        "child_mirror": "has_child_mirror",
        "governance_validator": "has_governance_validator",
        "governance_test": "has_governance_test",
        "pr_disclosure": "has_pr_disclosure",
        "adoption_checklist": "has_adoption_checklist",
        "ai_front_door": "has_ai_front_door",
        "ai_toc": "has_ai_toc",
        "repo_contract": "has_repo_contract",
    }
    return [surface_id for surface_id, flag in mapping.items() if not flags[flag]]


def _priority_components(
    *,
    flags: dict[str, Any],
    family_repo_count: int,
    adoption_status: str,
    resolved_path: str,
) -> dict[str, float]:
    family_size_signal = min(family_repo_count / 5, 1.0)
    if adoption_status == "missing_governance_dependency_surface":
        governance_gap = 1.0
    elif adoption_status == "governance_surface_without_dependency_map":
        governance_gap = 0.9
    elif adoption_status == "partial_map_or_mirror_observed":
        governance_gap = 0.6
    else:
        governance_gap = 0.25
    downstream_likelihood = 1.0 if family_repo_count > 1 else 0.35
    if flags["has_upstream_map"] or flags["has_child_mirror"]:
        downstream_likelihood = max(downstream_likelihood, 0.8)
    ai_navigation_readiness = (
        sum(
            1
            for key in ("has_repo_contract", "has_ai_front_door", "has_ai_toc")
            if flags[key]
        )
        / 3
    )
    validation_readiness = (
        sum(
            1
            for key in ("has_governance_validator", "has_governance_test", "has_pr_disclosure")
            if flags[key]
        )
        / 3
    )
    return {
        "family_size_signal": round(family_size_signal, 3),
        "governance_gap": round(governance_gap, 3),
        "downstream_likelihood": round(downstream_likelihood, 3),
        "ai_navigation_readiness": round(ai_navigation_readiness, 3),
        "validation_readiness": round(validation_readiness, 3),
        "configured_source_path": 1.0 if resolved_path else 0.0,
    }


def _priority_score(components: dict[str, float]) -> float:
    score = 100 * (
        0.25 * components["family_size_signal"]
        + 0.25 * components["governance_gap"]
        + 0.20 * components["downstream_likelihood"]
        + 0.15 * components["ai_navigation_readiness"]
        + 0.10 * components["validation_readiness"]
        + 0.05 * components["configured_source_path"]
    )
    return round(score, 2)


def _proposed_next_steps(candidate: dict[str, Any]) -> list[str]:
    status = candidate["adoption_status"]
    role = candidate["proposed_role"]
    steps: list[str] = []
    if role == "repo_family_map_candidate":
        steps.append("Review whether this repo should own the upstream governance dependency map.")
    elif role == "repo_family_review_candidate":
        steps.append("Review the repo family relationship before selecting a map owner or child mirror.")
    elif role == "child_mirror_maintenance_candidate":
        steps.append("Review whether the child mirror still points to the correct upstream map.")
    elif role == "upstream_map_maintenance_candidate":
        steps.append("Review whether child repos need mirrors and validators.")
    else:
        steps.append("Review whether this single repo has enough downstream impact to need a map.")
    if status in {
        "missing_governance_dependency_surface",
        "governance_surface_without_dependency_map",
    }:
        steps.append("If approved, adapt the cross-repo governance dependency-map template.")
    if "governance_validator" in candidate["missing_surface_ids"]:
        steps.append("Add fail-closed validation only after the map or mirror content is human-reviewed.")
    if "pr_disclosure" in candidate["missing_surface_ids"]:
        steps.append("Add PR disclosure requirements only inside an approved source-repo change.")
    return steps[:5]


def build_governance_map_adoption_scope(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    groups = build_repo_groups(assets)
    family_counts = _family_counts(groups)
    candidates: list[dict[str, Any]] = []
    skipped_noise_repos = 0
    status_counts: Counter[str] = Counter()
    family_status_counts: Counter[str] = Counter()

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
        status = _adoption_status(flags)
        family_key = _family_key(repo_key)
        family_repo_count = int(family_counts[family_key])
        role = _proposed_role(status, family_repo_count, flags)
        missing = _missing_surface_ids(flags)
        components = _priority_components(
            flags=flags,
            family_repo_count=family_repo_count,
            adoption_status=status,
            resolved_path=resolved_path,
        )
        candidate: dict[str, Any] = {
            "repo_key": repo_key,
            "repo_label": repo_asset.title if repo_asset else _repo_label(repo_key),
            "repo_asset_id": repo_asset.asset_id if repo_asset else "",
            "asset_count": len(group_assets),
            "family_key": family_key,
            "family_repo_count": family_repo_count,
            "configured_source_id": source.id if source else "",
            "resolved_repo_path": resolved_path,
            "adoption_status": status,
            "proposed_role": role,
            "surface_flags": flags,
            "missing_surface_ids": missing,
            "priority_score": _priority_score(components),
            "priority_components": components,
            "priority_formula": PRIORITY_FORMULA,
            "target_template_paths": list(TARGET_TEMPLATE_PATHS),
            "human_gate_required": True,
            "review_status": "generated_candidate",
            "authority_boundary": AUTHORITY_BOUNDARY,
            "applies_when": [
                "A human is selecting repo families for governance map or child mirror adoption.",
                "The repo is in the approved local catalog and source authority must remain local.",
            ],
            "does_not_apply_when": [
                "The repo is a scratch, temp, or fixture repo with no downstream consumers.",
                "The user has not approved any source-repo changes.",
                "The repo already has a reviewed equivalent governance dependency-map mechanism.",
            ],
            "danger_if_misapplied": (
                "A generated adoption candidate can be mistaken for permission to write governance "
                "files into source repos. It is only a review scope and must not override source authority."
            ),
        }
        candidate["proposed_next_steps"] = _proposed_next_steps(candidate)
        candidates.append(candidate)
        status_counts[status] += 1
        family_status_counts[family_key] += 1

    candidates = sorted(
        candidates,
        key=lambda item: (
            item["adoption_status"].startswith("map_and_mirror"),
            -float(item["priority_score"]),
            item["family_key"],
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
            "candidate_family_count": len(family_counts),
            "skipped_noise_repo_count": skipped_noise_repos,
            "status_counts": dict(sorted(status_counts.items())),
            "families_seen": dict(sorted(family_status_counts.items())),
            "source_repos_mutated": 0,
            "hooks_installed": 0,
            "content_files_read": 0,
            "filesystem_recursions": 0,
            "github_calls": 0,
            "model_calls": 0,
        },
        "target_template_paths": list(TARGET_TEMPLATE_PATHS),
        "intentionally_not_done": [
            "downstream repo writes",
            "governance map or mirror installation",
            "validator or test installation",
            "source file content reads",
            "fresh filesystem recursion",
            "GitHub or model calls",
            "roadmap phase completion",
        ],
        "approval_question": (
            "Which repo family should receive a human-reviewed governance dependency map or child mirror first?"
        ),
        "template_source": "templates/cross-repo-governance-dependency-map/",
        "repo_candidates": selected,
        "review_status": "generated_candidate",
    }


def governance_map_adoption_scope_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Governance Map Adoption Scope",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Scan id: `{result['scan_id']}`",
        f"- Reported repos: **{summary['reported_repo_count']}**",
        f"- Candidate repos before limit: **{summary['candidate_repo_count_before_limit']}**",
        f"- Candidate families: **{summary['candidate_family_count']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- GitHub/model calls: **{summary['github_calls']}** / **{summary['model_calls']}**",
        "",
        "## Priority Formula",
        "",
        f"`{result['priority_formula']}`",
        "",
        "This score is review routing only. It does not prove repo value, authority, or adoption approval.",
        "",
        "## Target Surfaces If Later Approved",
        "",
    ]
    for path in result["target_template_paths"]:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Status Counts", ""])
    for status, count in summary["status_counts"].items():
        lines.append(f"- `{status}`: **{count}**")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Repo Candidates", ""])
    lines.append(
        "| Priority | Status | Role | Family | Repo | Observed surfaces | Missing surfaces |"
    )
    lines.append("|---:|---|---|---|---|---|---|")
    for candidate in result["repo_candidates"]:
        flags = candidate["surface_flags"]
        observed = ", ".join(
            key.replace("has_", "")
            for key in (
                "has_upstream_map",
                "has_child_mirror",
                "has_governance_validator",
                "has_governance_test",
                "has_pr_disclosure",
                "has_ai_front_door",
                "has_ai_toc",
                "has_repo_contract",
            )
            if flags[key]
        ) or "none"
        lines.append(
            "| {score:.2f} | `{status}` | `{role}` | `{family}` | `{repo}` | {observed} | {missing} |".format(
                score=float(candidate["priority_score"]),
                status=candidate["adoption_status"],
                role=candidate["proposed_role"],
                family=candidate["family_key"],
                repo=candidate["repo_key"],
                observed=observed.replace("|", "/"),
                missing=", ".join(candidate["missing_surface_ids"]).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Review Questions",
            "",
            "1. Which repo actually owns upstream governance for each family?",
            "2. Which child repos should mirror that upstream map?",
            "3. Which active repos should be deferred because a governance edit would disrupt current work?",
            "4. Which validators and tests prove the map or mirror is not stale boilerplate?",
            "5. What PR disclosure should be required before governance-facing files change?",
            "",
            "## Red-Team",
            "",
            "- Metadata can miss existing maps if the last scan did not observe the file.",
            "- Repo family grouping by path prefix can be wrong for unusual layouts.",
            "- A child mirror must not claim authority over the upstream map.",
            "- Template adoption without validation creates false confidence.",
            "- This report is not permission to edit source repos.",
            "",
        ]
    )
    return "\n".join(lines)


def governance_map_adoption_approval_prompt_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Fresh-Eyes Prompt: Governance Map Adoption Scope",
        "",
        "Review this DAD-generated scope before any governance dependency maps, child mirrors, "
        "validators, tests, or PR disclosure sections are installed in source repos.",
        "",
        "Constraints:",
        "",
        "- Do not mutate any target repo during review.",
        "- Do not read source file contents unless a separate bounded content pass is approved.",
        "- Treat priority scores as review routing only.",
        "- Preserve each source repo's authority over its own governance meaning.",
        "",
        "Questions:",
        "",
        "1. Which repo family should be reviewed first?",
        "2. Which repo in that family should own the upstream map?",
        "3. Which repos should receive child mirrors?",
        "4. Which repos should be excluded because they are scratch, temp, or actively changing?",
        "5. What validator and test should prove adoption before any human gate is marked verified?",
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
            f"status `{candidate['adoption_status']}`, role `{candidate['proposed_role']}`"
        )
    lines.append("")
    return "\n".join(lines)


def write_governance_map_adoption_scope_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_governance_map_adoption_scope(
        repo_root,
        assets,
        local_sources,
        scan_id=scan_id,
        limit=limit,
        generated_at=generated_at,
    )
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "scope_markdown": reports_dir / "governance_map_adoption_scope.md",
        "scope_json": reports_dir / "governance_map_adoption_scope.json",
        "approval_prompt": reports_dir / "governance_map_adoption_approval_prompt.md",
    }
    atomic_write_text(paths["scope_markdown"], governance_map_adoption_scope_markdown(result))
    atomic_write_text(paths["scope_json"], json_dumps(result, pretty=True) + "\n")
    atomic_write_text(paths["approval_prompt"], governance_map_adoption_approval_prompt_markdown(result))
    return {
        "output_type": "generated_candidate_scope",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }
