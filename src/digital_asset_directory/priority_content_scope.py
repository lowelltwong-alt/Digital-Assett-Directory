from __future__ import annotations

import json
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .config import LocalSource
from .ids import stable_id
from .models import AssetRecord
from .utils import atomic_write_text, json_dumps, redact_sensitive_text, tokens, utc_now, write_jsonl

METHODOLOGY_VERSION = "priority-content-extract-scope-v0.1"
EXTRACT_METHODOLOGY_VERSION = "priority-content-extract-v0.2"
AUTHORITY_BOUNDARY = (
    "Generated approval scope only. This command uses catalog metadata and logical paths to "
    "select candidate files for a future bounded content pass. It does not read source file "
    "contents, recurse through source filesystems, call GitHub, call models, mutate source "
    "repos, install hooks, or promote candidate findings to truth."
)
EXTRACT_AUTHORITY_BOUNDARY = (
    "Generated bounded content observations only. This command reads only human-approved "
    "candidate paths from a generated scope file, resolves them under configured local source "
    "roots, caps bytes per file, redacts secret-like text, writes generated outputs under "
    "`processed/`, and does not mutate source repos, call GitHub, call models, install hooks, "
    "or promote findings to truth."
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

CONTENT_SIGNAL_TERMS: dict[str, tuple[str, ...]] = {
    "ai_navigation": (
        "ai front door",
        "agents.md",
        "preflight",
        "postflight",
        "read first",
        "toc",
        "table of contents",
        "validation plan",
    ),
    "schema_contract": (
        "schema",
        "contract",
        "validator",
        "required",
        "json schema",
        "pydantic",
    ),
    "governance": (
        "authority",
        "gate",
        "human review",
        "source of truth",
        "boundary",
        "privacy",
        "security",
    ),
    "learning_loop": (
        "lesson",
        "learning",
        "handoff",
        "pay forward",
        "context tag",
        "review_status",
    ),
    "workflow_dataflow": (
        "workflow",
        "data flow",
        "normalization",
        "pipeline",
        "chunk",
        "migration",
    ),
}


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


def _load_scope(scope_file: Path) -> dict[str, Any]:
    try:
        return json.loads(scope_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Scope file does not exist: {scope_file}") from exc
    except ValueError as exc:
        raise ValueError(f"Scope file is not valid JSON: {scope_file}") from exc


def _case_insensitive_child(parent: Path, part: str) -> Path:
    candidate = parent / part
    if candidate.exists():
        return candidate
    try:
        for child in parent.iterdir():
            if child.name.lower() == part.lower():
                return child
    except OSError:
        return candidate
    return candidate


def _resolve_logical_path(
    logical_path: str, local_sources: list[LocalSource]
) -> tuple[Path | None, str]:
    logical = _normalized(logical_path)
    for source in sorted(local_sources, key=lambda item: len(item.path_alias), reverse=True):
        if not source.enabled:
            continue
        alias = _normalized(source.path_alias)
        if logical != alias and not logical.startswith(f"{alias}/"):
            continue
        rel = logical[len(alias) :].strip("/")
        source_root = source.path.resolve()
        candidate = source_root
        for part in PurePosixPath(rel).parts:
            candidate = _case_insensitive_child(candidate, part)
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(source_root)
        except ValueError:
            return None, "resolved path escapes configured source root"
        return resolved, ""
    return None, "no enabled local source matches logical path"


def _approved_candidates(
    scope: dict[str, Any],
    *,
    repo_keys: list[str],
    category_ids: list[str],
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    limit: int,
) -> list[dict[str, Any]]:
    repo_allow = {_normalized(repo_key) for repo_key in repo_keys}
    category_allow = {_normalized(category_id) for category_id in category_ids}
    include_allow = {_normalized(path) for path in include_paths or [] if str(path).strip()}
    exclude_block = {_normalized(path) for path in exclude_paths or [] if str(path).strip()}
    candidates: list[dict[str, Any]] = []
    for repo in scope.get("repo_scopes", []):
        repo_key = _normalized(str(repo.get("repo_key", "")))
        if repo_key not in repo_allow:
            continue
        for candidate in repo.get("candidates", []):
            category_id = _normalized(str(candidate.get("primary_category_id", "")))
            if category_id not in category_allow:
                continue
            path_keys = {
                _normalized(str(candidate.get("logical_path", ""))),
                _normalized(str(candidate.get("relative_path", ""))),
            }
            if include_allow and not (path_keys & include_allow):
                continue
            if exclude_block and path_keys & exclude_block:
                continue
            candidates.append({"repo_key": repo_key, **candidate})
            if len(candidates) >= limit:
                return candidates
    return candidates


def _signal_counts(text: str) -> dict[str, int]:
    lowered = text.lower()
    return {
        signal_id: sum(1 for term in terms if term in lowered)
        for signal_id, terms in CONTENT_SIGNAL_TERMS.items()
        if any(term in lowered for term in terms)
    }


def run_priority_content_extract(
    scope: dict[str, Any],
    local_sources: list[LocalSource],
    *,
    approval_id: str,
    repo_keys: list[str],
    category_ids: list[str],
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    scan_id: str,
    max_bytes_per_file: int = 20_000,
    max_excerpt_chars: int = 4_000,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not approval_id.strip():
        raise ValueError("--approval-id is required before reading scoped content.")
    if not repo_keys:
        raise ValueError("At least one --repo-key is required for bounded extraction.")
    if not category_ids:
        raise ValueError("At least one --category is required for bounded extraction.")
    if max_bytes_per_file <= 0:
        raise ValueError("--max-bytes-per-file must be positive.")
    generated = generated_at or utc_now()
    candidates = _approved_candidates(
        scope,
        repo_keys=repo_keys,
        category_ids=category_ids,
        include_paths=include_paths,
        exclude_paths=exclude_paths,
        limit=limit,
    )
    observations: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    redaction_count = 0
    bytes_read = 0

    for candidate in candidates:
        logical_path = str(candidate.get("logical_path", ""))
        resolved, reason = _resolve_logical_path(logical_path, local_sources)
        if resolved is None:
            skipped.append({"logical_path": logical_path, "reason": reason})
            continue
        if not resolved.exists():
            skipped.append({"logical_path": logical_path, "reason": "file does not exist"})
            continue
        if not resolved.is_file():
            skipped.append({"logical_path": logical_path, "reason": "path is not a file"})
            continue
        with resolved.open("rb") as handle:
            raw = handle.read(max_bytes_per_file + 1)
        truncated = len(raw) > max_bytes_per_file
        raw = raw[:max_bytes_per_file]
        bytes_read += len(raw)
        text = raw.decode("utf-8", errors="replace")
        redacted, count = redact_sensitive_text(text)
        redaction_count += count
        signal_counts = _signal_counts(redacted)
        category_id = str(candidate.get("primary_category_id", ""))
        category_counts[category_id] += 1
        observation_id = stable_id(
            "priority-content-observation",
            approval_id,
            str(candidate.get("asset_id", "")),
            logical_path,
        )
        observations.append(
            {
                "schema_version": "0.1.0",
                "observation_id": observation_id,
                "approval_id": approval_id,
                "methodology_version": EXTRACT_METHODOLOGY_VERSION,
                "repo_key": candidate["repo_key"],
                "asset_id": candidate.get("asset_id", ""),
                "logical_path": logical_path,
                "relative_path": candidate.get("relative_path", ""),
                "category_id": category_id,
                "asset_type": candidate.get("asset_type", ""),
                "content_read_bytes": len(raw),
                "content_truncated": truncated,
                "redaction_count": count,
                "content_excerpt": redacted[:max_excerpt_chars],
                "content_token_sample": sorted(tokens(redacted))[:80],
                "signal_counts": signal_counts,
                "signal_tags": sorted(signal_counts),
                "evidence": {
                    "match_reasons": candidate.get("match_reasons", []),
                    "max_bytes_per_file": max_bytes_per_file,
                    "max_excerpt_chars": max_excerpt_chars,
                    "resolved_under_configured_source": True,
                    "candidate_only": True,
                },
                "authority_boundary": EXTRACT_AUTHORITY_BOUNDARY,
                "generated_at": generated,
                "scan_id": scan_id,
                "review_status": "generated_candidate",
            }
        )

    return {
        "methodology_version": EXTRACT_METHODOLOGY_VERSION,
        "generated_at": generated,
        "scan_id": scan_id,
        "authority_boundary": EXTRACT_AUTHORITY_BOUNDARY,
        "approval_id": approval_id,
        "summary": {
            "candidate_count_considered": len(candidates),
            "observation_count": len(observations),
            "skipped_count": len(skipped),
            "bytes_read": bytes_read,
            "redaction_count": redaction_count,
            "source_repos_mutated": 0,
            "github_calls": 0,
            "model_calls": 0,
            "category_counts": dict(sorted(category_counts.items())),
            "repo_keys": sorted({_normalized(repo_key) for repo_key in repo_keys}),
            "category_ids": sorted({_normalized(category_id) for category_id in category_ids}),
            "include_path_count": len({_normalized(path) for path in include_paths or [] if str(path).strip()}),
            "exclude_path_count": len({_normalized(path) for path in exclude_paths or [] if str(path).strip()}),
        },
        "observations": observations,
        "skipped": skipped,
        "review_status": "generated_candidate",
    }


def priority_content_extract_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Priority Content Extract Observations",
        "",
        EXTRACT_AUTHORITY_BOUNDARY,
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Methodology: `{result['methodology_version']}`",
        f"- Approval id: `{result['approval_id']}`",
        f"- Candidate paths considered: **{summary['candidate_count_considered']}**",
        f"- Include path filters: **{summary['include_path_count']}**",
        f"- Exclude path filters: **{summary['exclude_path_count']}**",
        f"- Observations written: **{summary['observation_count']}**",
        f"- Skipped paths: **{summary['skipped_count']}**",
        f"- Bytes read: **{summary['bytes_read']}**",
        f"- Redactions: **{summary['redaction_count']}**",
        f"- Source repos mutated: **{summary['source_repos_mutated']}**",
        "",
        "## Category Counts",
        "",
    ]
    for category_id, count in summary["category_counts"].items():
        lines.append(f"- `{category_id}`: **{count}**")
    lines.extend(["", "## Observation Sample", ""])
    for observation in result["observations"][:25]:
        signals = ", ".join(observation["signal_tags"]) or "none"
        lines.extend(
            [
                f"### {observation['relative_path']}",
                "",
                f"- Repo: `{observation['repo_key']}`",
                f"- Category: `{observation['category_id']}`",
                f"- Bytes read: **{observation['content_read_bytes']}**",
                f"- Truncated: **{observation['content_truncated']}**",
                f"- Redactions: **{observation['redaction_count']}**",
                f"- Signal tags: `{signals}`",
                "",
            ]
        )
    if result["skipped"]:
        lines.extend(["## Skipped Paths", ""])
        for item in result["skipped"][:25]:
            lines.append(f"- `{item['logical_path']}`: {item['reason']}")
        lines.append("")
    lines.extend(
        [
            "## Red-Team",
            "",
            "- These are generated observations, not source truth.",
            "- Redaction is pattern-based and cannot prove all sensitive text was removed.",
            "- Excerpts are bounded, but still derived from source content and must stay ignored under `processed/`.",
            "- Human review is required before turning observations into deterministic learning rules.",
            "",
        ]
    )
    return "\n".join(lines)


def write_priority_content_extract_outputs(
    repo_root: Path,
    local_sources: list[LocalSource],
    *,
    scope_file: Path | None = None,
    approval_id: str,
    repo_keys: list[str],
    category_ids: list[str],
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    scan_id: str,
    max_bytes_per_file: int = 20_000,
    max_excerpt_chars: int = 4_000,
    limit: int = 50,
    generated_at: str | None = None,
) -> dict[str, Any]:
    scope_path = scope_file or repo_root / "processed" / "reports" / "priority_content_extract_scope.json"
    if not scope_path.is_absolute():
        scope_path = repo_root / scope_path
    result = run_priority_content_extract(
        _load_scope(scope_path),
        local_sources,
        approval_id=approval_id,
        repo_keys=repo_keys,
        category_ids=category_ids,
        include_paths=include_paths,
        exclude_paths=exclude_paths,
        scan_id=scan_id,
        max_bytes_per_file=max_bytes_per_file,
        max_excerpt_chars=max_excerpt_chars,
        limit=limit,
        generated_at=generated_at,
    )
    learning_dir = repo_root / "processed" / "learning"
    reports_dir = repo_root / "processed" / "reports"
    paths = {
        "observations": learning_dir / "priority_content_observations.jsonl",
        "report_markdown": reports_dir / "priority_content_extract_report.md",
        "report_json": reports_dir / "priority_content_extract_report.json",
    }
    write_jsonl(paths["observations"], result["observations"])
    atomic_write_text(paths["report_markdown"], priority_content_extract_markdown(result))
    atomic_write_text(paths["report_json"], json_dumps(result, pretty=True) + "\n")
    return {
        "output_type": "generated_candidate_observations",
        "review_status": "generated_candidate",
        "summary": result["summary"],
        "outputs": {key: str(path) for key, path in paths.items()},
    }
