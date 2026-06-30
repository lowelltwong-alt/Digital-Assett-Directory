from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .config import LocalSource
from .models import AssetRecord
from .utils import atomic_write_text, json_dumps, utc_now

METHODOLOGY_VERSION = "priority-content-extract-scope-v0.1"
AUTHORITY_BOUNDARY = (
    "Generated approval scope only. This command uses catalog metadata and logical paths to "
    "select candidate files for a future bounded content pass. It does not read source file "
    "contents, recurse through source filesystems, call GitHub, call models, mutate source "
    "repos, install hooks, or promote candidate findings to truth."
)

CATEGORY_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "category_id": "ai_navigation",
        "label": "AI navigation and repo contracts",
        "priority": 1,
        "exact_names": {
            "agents.md",
            "claude.md",
            "ai_front_door.md",
            "ai_table_of_contents.md",
            "ai_toc.md",
            "readme.md",
        },
        "path_terms": ("start_here", "start-here", "front_door", "front-door"),
        "why": "These files determine how future agents enter, route, and obey authority.",
    },
    {
        "category_id": "schemas_contracts",
        "label": "Schemas, contracts, and registries",
        "priority": 2,
        "exact_names": {"pyproject.toml", "package.json", "tsconfig.json"},
        "path_terms": ("schema", "schemas/", "registry", "registries", "contract", "contracts"),
        "why": "Contracts and registries define deterministic records, fields, and controlled vocabularies.",
    },
    {
        "category_id": "validators_tests",
        "label": "Validators, tests, and quality gates",
        "priority": 3,
        "exact_names": {"noxfile.py", "pytest.ini"},
        "path_terms": ("tests/", "test_", "_test.", "validate", "validator", "quality", ".github/workflows"),
        "why": "Tests and validators show how the repo proves behavior and where gates should run.",
    },
    {
        "category_id": "governance_security",
        "label": "Governance, security, and privacy boundaries",
        "priority": 4,
        "exact_names": {"roadmap.yaml", "gate-evidence.json"},
        "path_terms": (
            "governance",
            ".ai/control",
            "security",
            "privacy",
            "authority",
            "source-of-truth",
            "design-authority",
            "gate",
            "roadmap",
        ),
        "why": "Governance files carry authority boundaries, human gates, and public-safety rules.",
    },
    {
        "category_id": "learning_loops",
        "label": "Learning loops and pay-forward surfaces",
        "priority": 5,
        "exact_names": {"events.jsonl", "context-tags.yaml"},
        "path_terms": ("learning", "lesson", "handoff", "postflight", "preflight", "pay_forward", "pay-forward"),
        "why": "Learning-loop files show how lessons, asset-use feedback, and context tags are captured.",
    },
    {
        "category_id": "workflow_dataflow",
        "label": "Workflows, dataflow, and normalization",
        "priority": 6,
        "exact_names": {"data_flow.md", "data_dictionary.md", "changelog.md"},
        "path_terms": (
            "workflow",
            "data_flow",
            "data-flow",
            "data_dictionary",
            "normalization",
            "pipeline",
            "migration",
            "etl",
            "chunk",
        ),
        "why": "Workflow and dataflow files are the best candidates for reusable process assets.",
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


def _is_noise_path(path: str) -> bool:
    lowered = _normalized(path)
    noise_terms = (
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
    return any(term in lowered for term in noise_terms)


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
    for category in CATEGORY_DEFINITIONS:
        exact_names = set(category["exact_names"])
        path_terms = tuple(category["path_terms"])
        reasons: list[str] = []
        if name in exact_names:
            reasons.append(f"filename:{name}")
        reasons.extend(f"path_term:{term}" for term in path_terms if term in text)
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


def _candidate_priority(asset: AssetRecord, categories: list[dict[str, Any]]) -> tuple[int, float, int, str]:
    category_priority = min(int(category["priority"]) for category in categories)
    return (
        category_priority,
        -float(asset.value_score),
        len(asset.logical_path),
        _normalized(asset.logical_path),
    )


def build_priority_content_extract_scope(
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
    groups = _build_repo_groups_by_prefix(assets)
    repo_candidates: list[dict[str, Any]] = []
    full_category_counts: Counter[str] = Counter()
    skipped_noise_repos = 0
    skipped_noise_assets = 0

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
        candidates = sorted(
            candidates,
            key=lambda item: _candidate_priority(
                next(asset for asset in group_assets if asset.asset_id == item["asset_id"]),
                item["categories"],
            ),
        )[:per_repo_limit]
        if not candidates:
            continue
        for candidate in candidates:
            full_category_counts[candidate["primary_category_id"]] += 1
        repo_asset = next((asset for asset in group_assets if asset.asset_type == "repository"), None)
        repo_candidates.append(
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
                    "Review this repo's candidate file list before authorizing a bounded content pass."
                ),
            }
        )
    repo_candidates = sorted(
        repo_candidates,
        key=lambda item: (
            item["configured_source_scan_depth"] != "metadata_only",
            -item["candidate_count"],
            item["repo_key"],
        ),
    )
    limited_repos: list[dict[str, Any]] = []
    emitted_candidates = 0
    for record in repo_candidates:
        if emitted_candidates >= limit:
            break
        remaining = limit - emitted_candidates
        scoped = {**record, "candidates": record["candidates"][:remaining]}
        scoped["candidate_count"] = len(scoped["candidates"])
        limited_repos.append(scoped)
        emitted_candidates += scoped["candidate_count"]
    reported_category_counts: Counter[str] = Counter(
        candidate["primary_category_id"]
        for repo in limited_repos
        for candidate in repo["candidates"]
    )

    return {
        "methodology_version": METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "catalog_asset_count": len(assets),
            "repo_count_with_candidates": len(repo_candidates),
            "reported_repo_count": len(limited_repos),
            "total_candidate_count_before_limit": sum(
                len(repo["candidates"]) for repo in repo_candidates
            ),
            "candidate_count": sum(len(repo["candidates"]) for repo in limited_repos),
            "skipped_noise_repo_count": skipped_noise_repos,
            "skipped_noise_asset_count": skipped_noise_assets,
            "category_counts": dict(sorted(reported_category_counts.items())),
            "total_category_counts_before_limit": dict(sorted(full_category_counts.items())),
            "content_files_read": 0,
            "source_repos_mutated": 0,
        },
        "categories": [
            {
                "category_id": category["category_id"],
                "label": category["label"],
                "priority": category["priority"],
                "why": category["why"],
            }
            for category in CATEGORY_DEFINITIONS
        ],
        "intentionally_not_done": [
            "source file content reads",
            "fresh filesystem recursion",
            "GitHub or CI access",
            "model or embedding calls",
            "downstream repo mutation",
            "automatic learning-loop installation",
        ],
        "approval_question": (
            "Which repo families and categories should be authorized for a bounded content extract pass?"
        ),
        "approved_next_step_template": (
            "After human approval, run or implement a bounded content extractor that reads only approved "
            "candidate paths, caps bytes per file, redacts secrets, and writes generated observations."
        ),
        "repo_scopes": limited_repos,
        "review_status": "generated_candidate",
    }


def priority_content_scope_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Priority Content Extract Scope",
        "",
        AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Scan id: `{result['scan_id']}`",
        f"- Candidate files listed: **{summary['candidate_count']}**",
        f"- Repos with candidates reported: **{summary['reported_repo_count']}**",
        f"- Content files read: **{summary['content_files_read']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        "",
        "## Categories",
        "",
    ]
    for category in result["categories"]:
        lines.append(f"- `{category['category_id']}`: {category['why']}")
    lines.extend(["", "## Intentionally Not Done", ""])
    for item in result["intentionally_not_done"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Category Counts", ""])
    for category_id, count in summary["category_counts"].items():
        lines.append(f"- `{category_id}`: **{count}**")
    lines.extend(["", "## Approval Question", "", result["approval_question"], "", "## Repo Scopes", ""])
    for repo in result["repo_scopes"]:
        lines.extend(
            [
                f"### {repo['repo_key']}",
                "",
                f"- Scan depth from config: `{repo['configured_source_scan_depth']}`",
                f"- Candidate count: **{repo['candidate_count']}**",
                f"- Human gate required: **{repo['human_gate_required']}**",
                "",
                "| Category | Path | Type | Score | Match reasons |",
                "|---|---|---|---:|---|",
            ]
        )
        for candidate in repo["candidates"]:
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
            "## Red-Team",
            "",
            "- This is a scope list, not evidence from file content.",
            "- Metadata-only paths can be stale or incomplete.",
            "- High-value scores do not prove content should be read.",
            "- A future extractor must cap bytes, redact secrets, and write generated observations only.",
            "- Human approval is required before content extraction or downstream repo changes.",
            "",
        ]
    )
    return "\n".join(lines)


def approval_prompt_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Fresh-Eyes Prompt: Priority Content Extract Scope",
        "",
        "Review this DAD-generated scope pack before any content extraction is authorized.",
        "",
        "Constraints:",
        "",
        "- Do not read source file contents for this review unless separately authorized.",
        "- Do not mutate downstream repositories.",
        "- Treat the candidate list as metadata-only routing evidence.",
        "- Recommend a bounded content pass only for categories/repos where the likely value exceeds privacy and noise risk.",
        "",
        "Questions:",
        "",
        "1. Which repo families should be included first?",
        "2. Which categories should be excluded or capped more tightly?",
        "3. Are any candidate paths likely sensitive, noisy, or stale?",
        "4. What byte caps, redaction checks, and stop conditions should be required?",
        "5. What would prove that the content pass improved lesson automation?",
        "",
        "Summary:",
        "",
        f"- Candidate files: {result['summary']['candidate_count']}",
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


def write_priority_content_extract_scope_outputs(
    repo_root: Path,
    assets: list[AssetRecord],
    local_sources: list[LocalSource],
    *,
    scan_id: str,
    limit: int = 200,
    per_repo_limit: int = 12,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result = build_priority_content_extract_scope(
        repo_root,
        assets,
        local_sources,
        scan_id=scan_id,
        limit=limit,
        per_repo_limit=per_repo_limit,
        generated_at=generated_at,
    )
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "scope_markdown": reports_dir / "priority_content_extract_scope.md",
        "scope_json": reports_dir / "priority_content_extract_scope.json",
        "approval_prompt": reports_dir / "priority_content_extract_approval_prompt.md",
    }
    atomic_write_text(paths["scope_markdown"], priority_content_scope_markdown(result))
    atomic_write_text(paths["scope_json"], json_dumps(result, pretty=True) + "\n")
    atomic_write_text(paths["approval_prompt"], approval_prompt_markdown(result))
    return {
        "output_type": "generated_candidate_scope",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }
