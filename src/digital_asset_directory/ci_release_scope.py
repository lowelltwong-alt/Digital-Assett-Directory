from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .config import LocalSource
from .models import AssetRecord
from .transport import data_relative_path
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "ci-release-artifact-scope-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated CI/release artifact approval scope only. This command uses catalog metadata "
    "and logical paths to select candidate CI, release, changelog, QA, and build artifact "
    "files for a future bounded content pass. It does not read source file contents, recurse "
    "through source filesystems, call GitHub, call CI services, call models, mutate source "
    "repos, install hooks, or promote candidate findings to truth."
)

ARTIFACT_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "category_id": "ci_workflow_config",
        "label": "CI workflow configuration",
        "priority": 1,
        "exact_names": {
            ".gitlab-ci.yml",
            "azure-pipelines.yml",
            "bitbucket-pipelines.yml",
            "jenkinsfile",
            "noxfile.py",
            "tox.ini",
        },
        "path_terms": (
            ".github/workflows/",
            ".circleci/config.yml",
            "workflows/ci",
            "workflow/ci",
            "ci.yml",
            "ci.yaml",
            "validate.yml",
            "validate.yaml",
        ),
        "why": "CI workflow files reveal validation order, release gates, and late stabilizers.",
    },
    {
        "category_id": "release_notes_changelog",
        "label": "Release notes and changelogs",
        "priority": 2,
        "exact_names": {
            "changelog.md",
            "changes.md",
            "release_notes.md",
            "release-notes.md",
            "releases.md",
        },
        "path_terms": ("changelog", "release_notes", "release-notes", "releases/"),
        "why": "Release history captures migrations, fixes, compatibility promises, and repeated issues.",
    },
    {
        "category_id": "qa_validation_report",
        "label": "QA, validation, and verification reports",
        "priority": 3,
        "exact_names": {
            "verification_report.md",
            "validation_report.md",
            "qa_report.md",
            "test_report.md",
        },
        "path_terms": (
            "verification",
            "validation_report",
            "qa/",
            "quality/",
            "test-report",
            "test_results",
            "test-results",
        ),
        "why": "QA reports expose actual failure modes, acceptance evidence, and review boundaries.",
    },
    {
        "category_id": "build_test_log_artifact",
        "label": "Build and test log artifacts",
        "priority": 4,
        "exact_names": {
            "build.log",
            "test.log",
            "pytest.log",
            "junit.xml",
            "coverage.xml",
        },
        "path_terms": (
            "logs/",
            "artifacts/",
            "coverage/",
            "junit",
            "test-results",
            "build-output",
            "ci-output",
        ),
        "why": "Logs and generated reports can reveal repeated failures and fixes, but are noisy and often sensitive.",
    },
    {
        "category_id": "dependency_lock_manifest",
        "label": "Dependency lock and version manifests",
        "priority": 5,
        "exact_names": {
            "poetry.lock",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "pipfile.lock",
            "requirements.txt",
            "pyproject.toml",
            "package.json",
        },
        "path_terms": ("requirements-", "lockfile", "version", "manifest"),
        "why": "Dependency and version manifests help explain reproducibility, compatibility, and upgrade lessons.",
    },
)


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


def _category_matches(asset: AssetRecord, relative_path: str) -> list[dict[str, Any]]:
    lowered_path = _normalized(relative_path)
    name = PurePosixPath(lowered_path).name
    text = " ".join(
        [
            lowered_path,
            asset.asset_type.lower(),
            " ".join(asset.tags).lower(),
            " ".join(asset.capabilities).lower(),
            " ".join(asset.needs).lower(),
        ]
    )
    matches: list[dict[str, Any]] = []
    for category in ARTIFACT_CATEGORIES:
        reasons: list[str] = []
        if name in set(category["exact_names"]):
            reasons.append(f"filename:{name}")
        reasons.extend(f"path_term:{term}" for term in category["path_terms"] if term in text)
        if reasons:
            matches.append(
                {
                    "category_id": category["category_id"],
                    "label": category["label"],
                    "priority": category["priority"],
                    "why": category["why"],
                    "match_reasons": sorted(set(reasons))[:8],
                }
            )
    return sorted(matches, key=lambda item: (int(item["priority"]), item["category_id"]))


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, float, int, str]:
    return (
        int(candidate["categories"][0]["priority"]),
        -float(candidate["value_score"]),
        len(str(candidate["logical_path"])),
        _normalized(str(candidate["logical_path"])),
    )


def build_ci_release_artifact_scope(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    limit: int = 200,
    per_repo_limit: int = 12,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    repo_scopes: list[dict[str, Any]] = []
    skipped_noise_repos = 0
    skipped_noise_assets = 0
    category_counts: Counter[str] = Counter()
    groups = _build_repo_groups_by_prefix(assets)

    for repo_key, group_assets in sorted(groups.items()):
        if not any(asset.asset_type == "repository" for asset in group_assets):
            continue
        if _is_noise_repo(repo_key, group_assets):
            skipped_noise_repos += 1
            continue
        source = _configured_source_for_repo(repo_key, local_sources)
        candidates: list[dict[str, Any]] = []
        for asset in group_assets:
            if asset.asset_type == "repository":
                continue
            relative_path = _relative_path(asset.logical_path, repo_key)
            if not relative_path or _is_noise_path(relative_path):
                skipped_noise_assets += 1
                continue
            categories = _category_matches(asset, relative_path)
            if not categories:
                continue
            candidate = {
                "asset_id": asset.asset_id,
                "logical_path": asset.logical_path,
                "relative_path": relative_path,
                "asset_type": asset.asset_type,
                "value_score": asset.value_score,
                "categories": categories,
                "primary_category_id": categories[0]["category_id"],
                "match_reasons": categories[0]["match_reasons"],
                "content_read_status": "not_read_by_scope_pack",
                "review_status": "generated_candidate",
            }
            candidates.append(candidate)
        candidates = sorted(candidates, key=_candidate_sort_key)[:per_repo_limit]
        if not candidates:
            continue
        repo_asset = next((asset for asset in group_assets if asset.asset_type == "repository"), None)
        for candidate in candidates:
            category_counts[candidate["primary_category_id"]] += 1
        repo_scopes.append(
            {
                "repo_key": repo_key,
                "repo_label": repo_asset.title if repo_asset else _repo_label(repo_key),
                "repo_asset_id": repo_asset.asset_id if repo_asset else "",
                "configured_source_id": source.id if source else "",
                "configured_source_scan_depth": (
                    "metadata_only" if source and source.max_file_bytes == 0 else "content_excerpt"
                ),
                "candidate_count": len(candidates),
                "candidates": candidates,
                "human_gate_required": True,
                "recommended_next_action": (
                    "Review candidate artifacts before authorizing any content reads from CI, release, or log files."
                ),
            }
        )

    repo_scopes = sorted(repo_scopes, key=lambda item: (-item["candidate_count"], item["repo_key"]))
    limited_scopes: list[dict[str, Any]] = []
    emitted = 0
    for scope in repo_scopes:
        if emitted >= limit:
            break
        remaining = limit - emitted
        scoped = {**scope, "candidates": scope["candidates"][:remaining]}
        scoped["candidate_count"] = len(scoped["candidates"])
        limited_scopes.append(scoped)
        emitted += scoped["candidate_count"]
    reported_counts: Counter[str] = Counter(
        candidate["primary_category_id"]
        for scope in limited_scopes
        for candidate in scope["candidates"]
    )

    return {
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "catalog_asset_count": len(assets),
            "repo_count_with_candidates": len(repo_scopes),
            "reported_repo_count": len(limited_scopes),
            "total_candidate_count_before_limit": sum(scope["candidate_count"] for scope in repo_scopes),
            "candidate_count": sum(scope["candidate_count"] for scope in limited_scopes),
            "skipped_noise_repo_count": skipped_noise_repos,
            "skipped_noise_asset_count": skipped_noise_assets,
            "category_counts": dict(sorted(reported_counts.items())),
            "total_category_counts_before_limit": dict(sorted(category_counts.items())),
            "content_files_read": 0,
            "source_repos_mutated": 0,
            "github_calls": 0,
            "ci_service_calls": 0,
        },
        "categories": [
            {
                "category_id": category["category_id"],
                "label": category["label"],
                "priority": category["priority"],
                "why": category["why"],
            }
            for category in ARTIFACT_CATEGORIES
        ],
        "intentionally_not_done": [
            "source file content reads",
            "fresh filesystem recursion",
            "GitHub, CI, or package registry calls",
            "model or embedding calls",
            "downstream repo mutation",
            "automatic lesson synthesis from logs",
        ],
        "applies_when": [
            "A future agent needs to decide which CI, release, changelog, QA, or log artifacts might contain reusable lessons.",
            "The goal is to avoid repeated broad scans and choose a bounded artifact review scope.",
        ],
        "does_not_apply_when": [
            "The user has not approved even metadata-level observation for the source.",
            "The task is to run CI or fetch remote CI logs; this scope does not authorize either.",
        ],
        "danger_if_misapplied": (
            "CI logs and release artifacts can contain secrets, private filenames, and noisy generated output. "
            "This metadata-only scope must not be treated as approval to read or import their contents."
        ),
        "approval_question": (
            "Which repo keys and CI/release artifact categories should be authorized for a bounded, redacted content pass?"
        ),
        "repo_scopes": limited_scopes,
        "review_status": "generated_candidate",
    }


def ci_release_artifact_scope_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# CI And Release Artifact Scope",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Scan id: `{result['scan_id']}`",
        f"- Candidate artifacts listed: **{summary['candidate_count']}**",
        f"- Repos with candidates reported: **{summary['reported_repo_count']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        "",
        "## Categories",
        "",
    ]
    for category in result["categories"]:
        lines.append(f"- `{category['category_id']}`: {category['why']}")
    lines.extend(["", "## Category Counts", ""])
    for category_id, count in summary["category_counts"].items():
        lines.append(f"- `{category_id}`: **{count}**")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Repo Scopes", ""])
    for scope in result["repo_scopes"]:
        lines.extend(
            [
                f"### {scope['repo_key']}",
                "",
                f"- Scan depth from config: `{scope['configured_source_scan_depth']}`",
                f"- Candidate count: **{scope['candidate_count']}**",
                f"- Human gate required: **{scope['human_gate_required']}**",
                "",
                "| Category | Path | Type | Score | Match reasons |",
                "|---|---|---|---:|---|",
            ]
        )
        for candidate in scope["candidates"]:
            lines.append(
                "| `{category}` | `{path}` | `{asset_type}` | {score:.1f} | `{reasons}` |".format(
                    category=candidate["primary_category_id"],
                    path=candidate["relative_path"],
                    asset_type=candidate["asset_type"],
                    score=float(candidate["value_score"]),
                    reasons=", ".join(candidate["match_reasons"]),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Context Boundary",
            "",
            "Applies when:",
            "",
        ]
    )
    for item in result["applies_when"]:
        lines.append(f"- {item}")
    lines.extend(["", "Does not apply when:", ""])
    for item in result["does_not_apply_when"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            f"Danger if misapplied: {result['danger_if_misapplied']}",
            "",
            "## Red-Team",
            "",
            "- This is metadata-only routing evidence, not content analysis.",
            "- CI logs and generated artifacts are especially likely to contain secrets or noisy paths.",
            "- Release notes can be aspirational or incomplete; later extraction must preserve candidate-only status.",
            "- Human approval is required before content extraction or downstream repo changes.",
            "",
        ]
    )
    return "\n".join(lines)


def ci_release_approval_prompt_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Fresh-Eyes Prompt: CI And Release Artifact Scope",
        "",
        "Review this DAD-generated scope pack before any CI/release artifact content is read.",
        "",
        "Constraints:",
        "",
        "- Do not read source file contents unless separately authorized.",
        "- Do not call GitHub, CI services, package registries, or models.",
        "- Do not mutate downstream repositories.",
        "- Treat the candidate list as metadata-only routing evidence.",
        "",
        "Questions:",
        "",
        "1. Which repo families should be included first?",
        "2. Which artifact categories are most likely to expose reusable lessons?",
        "3. Which candidates are likely generated noise, secret-bearing, or too stale?",
        "4. What byte caps, redaction checks, and stop conditions should be required?",
        "5. What would prove that reading these artifacts improved lesson automation?",
        "",
        "Summary:",
        "",
        f"- Candidate artifacts: {result['summary']['candidate_count']}",
        f"- Reported repos: {result['summary']['reported_repo_count']}",
        f"- Content files read by this scope pack: {result['summary']['content_files_read']}",
        "",
        "Category counts:",
        "",
    ]
    for category_id, count in result["summary"]["category_counts"].items():
        lines.append(f"- `{category_id}`: {count}")
    lines.append("")
    return "\n".join(lines)


def write_ci_release_artifact_scope_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    limit: int = 200,
    per_repo_limit: int = 12,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_ci_release_artifact_scope(
        repo_root,
        assets,
        local_sources,
        scan_id=scan_id,
        limit=limit,
        per_repo_limit=per_repo_limit,
        generated_at=generated_at,
    )
    reports_dir = data_relative_path(repo_root, Path("processed") / "reports")
    paths = {
        "scope_markdown": reports_dir / "ci_release_artifact_scope.md",
        "scope_json": reports_dir / "ci_release_artifact_scope.json",
        "approval_prompt": reports_dir / "ci_release_artifact_approval_prompt.md",
    }
    atomic_write_text(paths["scope_markdown"], ci_release_artifact_scope_markdown(result))
    atomic_write_text(paths["scope_json"], json_dumps(result, pretty=True) + "\n")
    atomic_write_text(paths["approval_prompt"], ci_release_approval_prompt_markdown(result))
    return {
        "output_type": "generated_candidate_scope",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }
