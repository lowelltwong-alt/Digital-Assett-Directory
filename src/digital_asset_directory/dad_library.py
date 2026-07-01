from __future__ import annotations

import json
import fnmatch
import os
import re
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .ids import stable_id
from .utils import append_jsonl, atomic_write_text, json_dumps, utc_now

NEEDS_REGISTRY = Path("registry") / "dad-needs-registry.json"
OFFERINGS_REGISTRY = Path("registry") / "dad-offerings-registry.json"
USEFULNESS_METHODOLOGY = Path("registry") / "dad-usefulness-methodology.json"
ASSET_RECOGNITION_METHODOLOGY = Path("registry") / "asset-recognition-methodology.json"
HARNESS_DISCOVERY_METHODOLOGY = Path("registry") / "harness-discovery-methodology.json"
HARNESS_REGISTRY = Path("registry") / "coding-harness-registry.json"
CENTRAL_USAGE_LEDGER = Path("processed") / "usage" / "repo-asset-usage.jsonl"
HARNESS_REPORT_DIR = Path("processed") / "harnesses"
REPO_INVENTORY_DIR = Path("processed") / "repo_inventory"
CADENCE_REPORT_DIR = Path("processed") / "cadence"
LOCAL_USAGE_LEDGER = Path(".digital-asset") / "dad-usage.jsonl"

USAGE_STATUSES = {"using", "watching", "rejected", "retired"}
TRIAGE_DECISIONS = {"use_now", "save_for_future", "defer", "reject", "needs_human_review"}
AUTHORITY_BOUNDARY = (
    "DAD library, usage, and harness records are candidate control-plane metadata. "
    "Target repos retain local source authority and decide whether to adopt any "
    "asset, skill, harness, template, or workflow suggestion."
)
CENTRAL_ONLY_BOUNDARY = (
    "This DAD report is central candidate metadata only. It does not authorize "
    "enrollment, delivery, hooks, source edits, or writes to downstream repos."
)
REPO_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".nox",
    ".tox",
    ".pytest-tmp-root",
    "_codex_worktrees",
    ".worktrees",
}
ARCHIVE_MARKERS = {"99_archive", "archive", "archives", "snapshot", "snapshots"}
DUPLICATE_MARKERS = {"repos", "ss", "temp", "tmp", "reference", "references"}
WORKSPACE_ROOT_NAMES = {"git-projects", "github-repos", "repos-root", "workspace"}
PROTECTED_REPO_MARKERS = {
    "logos-scripture-graph",
    "logos_scripture_graph",
    "logos-governance",
    "logos_governance",
    "logos-governance-architecture",
    "logos_governance_architecture",
}
LAW_FIRM_KERNEL_MARKERS = {
    "semantic-substrate",
    "semantic_substrate",
    "orchestrator",
    "exceptions-lake-runtime",
    "exceptions_lake_runtime",
    "legal-knowledge-runtime",
    "legal_knowledge_runtime",
    "skills-registry",
    "skills_registry",
}
LAW_FIRM_SIDE_MARKERS = {"intake", "talent", "intelligence"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json_dumps(payload, pretty=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _append_unique(path: Path, record: dict[str, Any], key: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {str(item.get(key, "")) for item in _read_jsonl(path)}
    if str(record.get(key, "")) in existing:
        return False
    append_jsonl(path, record)
    return True


def _normalized_path(value: str | Path) -> str:
    return str(Path(value).resolve()).replace("\\", "/")


def _policy_path(policy: Any) -> str:
    try:
        return _normalized_path(getattr(policy, "path"))
    except (AttributeError, TypeError):
        return ""


def _policy_matches(repo: Path, policy: Any) -> bool:
    normalized = _normalized_path(repo)
    aliases = {
        str(getattr(policy, "id", "") or ""),
        str(getattr(policy, "alias", "") or ""),
        Path(_policy_path(policy)).name,
        _policy_path(policy),
    }
    return normalized in aliases or repo.name in aliases


def _repo_policy(
    repo: Path,
    *,
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
) -> Any | None:
    matches = [
        policy
        for policy in [*(mail_policies or []), *(enrollment_policies or [])]
        if _policy_matches(repo, policy)
    ]
    return matches[0] if matches else None


def _repo_ref(repo: Path, policy: Any | None = None) -> str:
    if policy and bool(getattr(policy, "public_facing", False)):
        return f"dad://repo/{getattr(policy, 'id', repo.name)}"
    return _normalized_path(repo)


def _repo_write_protection(policy: Any | None) -> tuple[bool, str]:
    if not policy:
        return True, "no reviewed DAD repo policy authorizes local writes"
    if bool(getattr(policy, "write_protected", False)):
        reason = str(getattr(policy, "write_protection_reason", "") or "").strip()
        return True, reason or "repo is write-protected by reviewed DAD policy"
    if bool(getattr(policy, "active_hold", False)):
        reason = str(getattr(policy, "active_hold_reason", "") or "").strip()
        return True, reason or "repo has an active enrollment hold"
    if hasattr(policy, "mail_enabled") and not bool(getattr(policy, "mail_enabled", True)):
        return True, "reviewed mail policy disables repo-local mail/usage writes"
    if hasattr(policy, "delivery_allowed") and not bool(getattr(policy, "delivery_allowed", True)):
        return True, "reviewed mail policy blocks DAD delivery/local writes"
    if hasattr(policy, "enrollment_enabled") and not bool(
        getattr(policy, "enrollment_enabled", True)
    ):
        return True, "reviewed enrollment policy disables repo-local writes"
    return False, ""


def _tokenize(value: Any) -> set[str]:
    if isinstance(value, str):
        parts = re.split(r"[^a-z0-9]+", value.lower())
        return {part for part in parts if part}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        tokens: set[str] = set()
        for item in value:
            tokens.update(_tokenize(item))
        return tokens
    return set()


def _repo_context(repo: Path) -> dict[str, Any]:
    context_path = repo / ".digital-asset" / "context-map.json"
    fallback = {
        "languages": [],
        "repo_type": "unknown",
        "domains": [],
        "context_tags": [],
        "visibility": "unknown",
        "public_facing": False,
    }
    if context_path.exists():
        try:
            payload = _load_json(context_path)
            dimensions = payload.get("context_dimensions", {})
            return {
                **fallback,
                "languages": list(dimensions.get("languages", []) or []),
                "repo_type": str(dimensions.get("repo_type", "unknown") or "unknown"),
                "domains": list(dimensions.get("domains", []) or []),
                "context_tags": list(dimensions.get("context_tags", []) or []),
                "visibility": str(dimensions.get("visibility", "unknown") or "unknown"),
                "public_facing": bool(dimensions.get("public_facing", False)),
            }
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    languages: list[str] = []
    if (repo / "pyproject.toml").exists() or any(repo.glob("*.py")):
        languages.append("python")
    if (repo / "Cargo.toml").exists():
        languages.append("rust")
    if (repo / "package.json").exists():
        languages.append("javascript")
    fallback["languages"] = sorted(set(languages))
    return fallback


def load_needs(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / NEEDS_REGISTRY)


def load_offerings(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / OFFERINGS_REGISTRY)


def load_usefulness_methodology(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / USEFULNESS_METHODOLOGY)


def load_asset_recognition_methodology(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / ASSET_RECOGNITION_METHODOLOGY)


def load_harness_discovery_methodology(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / HARNESS_DISCOVERY_METHODOLOGY)


def load_harnesses(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / HARNESS_REGISTRY)


def _score_overlap(repo_values: Any, offering_values: Any) -> float:
    repo_tokens = _tokenize(repo_values)
    offering_tokens = _tokenize(offering_values)
    if not repo_tokens or not offering_tokens:
        return 0.0
    return len(repo_tokens & offering_tokens) / len(repo_tokens | offering_tokens)


def _decision_for_score(score: float, needs_human_review: bool, methodology: dict[str, Any]) -> str:
    if needs_human_review:
        return "needs_human_review"
    thresholds = methodology.get("thresholds", {})
    if score >= float(thresholds.get("use_now", 75)):
        return "use_now"
    if score >= float(thresholds.get("save_for_future", 45)):
        return "save_for_future"
    if score >= float(thresholds.get("defer", 25)):
        return "defer"
    return "reject"


def _human_review_needed(repo_context: dict[str, Any], offering: dict[str, Any]) -> bool:
    if repo_context.get("public_facing") and not bool(offering.get("public_safe", False)):
        return True
    if str(offering.get("review_status", "")) not in {"reviewed", "installed_for_local_reuse"}:
        return True
    return False


def score_offering(
    repo_context: dict[str, Any],
    offering: dict[str, Any],
    methodology: dict[str, Any],
    *,
    task: str = "",
) -> dict[str, Any]:
    weights = methodology.get("weights", {})
    language = _score_overlap(repo_context.get("languages", []), offering.get("languages", []))
    repo_type = _score_overlap(repo_context.get("repo_type", ""), offering.get("repo_types", []))
    domain = _score_overlap(repo_context.get("domains", []), offering.get("domains", []))
    context_tags = _score_overlap(
        repo_context.get("context_tags", []), offering.get("context_tags", [])
    )
    task_match = _score_overlap(task, offering.get("task_types", []))
    capability = _score_overlap(task, offering.get("capabilities", []))
    component_scores = {
        "language_match": round(language * 100, 2),
        "repo_type_match": round(repo_type * 100, 2),
        "domain_match": round(domain * 100, 2),
        "context_tag_match": round(context_tags * 100, 2),
        "task_match": round(task_match * 100, 2),
        "capability_match": round(capability * 100, 2),
    }
    weighted = sum(
        component_scores[name] * float(weights.get(name, 0))
        for name in component_scores
    )
    needs_human_review = _human_review_needed(repo_context, offering)
    decision = _decision_for_score(weighted, needs_human_review, methodology)
    return {
        "offering_id": offering["offering_id"],
        "name": offering["name"],
        "offering_type": offering["offering_type"],
        "path": offering["path"],
        "decision": decision,
        "usefulness_score": round(weighted, 2),
        "component_scores": component_scores,
        "methodology_id": methodology["methodology_id"],
        "needs_human_review": needs_human_review,
        "reason": _decision_reason(decision, component_scores, offering),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _decision_reason(decision: str, components: dict[str, float], offering: dict[str, Any]) -> str:
    strongest = sorted(components.items(), key=lambda item: item[1], reverse=True)[:2]
    signals = ", ".join(f"{name}={score}" for name, score in strongest if score > 0)
    if decision == "needs_human_review":
        return "Human review required before local adoption or public-facing delivery."
    if not signals:
        return "No strong deterministic context overlap was found."
    return f"{decision} based on deterministic overlap: {signals}; review locally."


def match_repo_offerings(
    hub_root: Path,
    repo: Path,
    *,
    task: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    context = _repo_context(repo)
    methodology = load_usefulness_methodology(hub_root)
    offerings = load_offerings(hub_root).get("offerings", [])
    matches = [
        score_offering(context, offering, methodology, task=task)
        for offering in offerings
    ]
    matches.sort(key=lambda item: (item["decision"] == "needs_human_review", item["usefulness_score"]), reverse=True)
    return {
        "repo": _normalized_path(repo),
        "task": task,
        "context": context,
        "match_count": len(matches),
        "returned_match_count": len(matches[:limit]),
        "limit": limit,
        "matches": matches[:limit],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def reconcile_repo_inventory(
    hub_root: Path,
    *,
    local_sources: Sequence[Any] | None = None,
    github_sources: Sequence[Any] | None = None,
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
    max_depth: int = 5,
) -> dict[str, Any]:
    records_by_path: dict[str, dict[str, Any]] = {}
    source_warnings: list[str] = []
    for source in local_sources or []:
        if not bool(getattr(source, "enabled", True)):
            continue
        base = Path(getattr(source, "path", ""))
        if not base.exists():
            source_warnings.append(f"local source missing: {getattr(source, 'id', base)}")
            continue
        for repo in _discover_git_roots(
            base,
            max_depth=max_depth,
            follow_symlinks=bool(getattr(source, "follow_symlinks", False)),
        ):
            _add_inventory_signal(
                records_by_path,
                repo,
                f"local_source:{getattr(source, 'id', '')}",
            )
    for policy in enrollment_policies or []:
        repo = Path(getattr(policy, "path"))
        _add_inventory_signal(records_by_path, repo, "enrollment_policy")
    for policy in mail_policies or []:
        repo = Path(getattr(policy, "path"))
        _add_inventory_signal(records_by_path, repo, "mail_policy")

    basename_counts: dict[str, int] = {}
    for record in records_by_path.values():
        basename = _normalize_name(record["repo_name"])
        basename_counts[basename] = basename_counts.get(basename, 0) + 1

    records: list[dict[str, Any]] = []
    for record in records_by_path.values():
        repo = Path(record["local_path"])
        policy = _repo_policy(
            repo,
            mail_policies=mail_policies,
            enrollment_policies=enrollment_policies,
        )
        duplicate_basename = basename_counts.get(_normalize_name(record["repo_name"]), 0) > 1
        classification, reasons, next_action = _classify_inventory_repo(
            repo,
            policy=policy,
            duplicate_basename=duplicate_basename,
        )
        public_facing = bool(getattr(policy, "public_facing", False)) if policy else False
        record.update(
            {
                "repo_id": str(getattr(policy, "id", "")) if policy else "",
                "alias": str(getattr(policy, "alias", "")) if policy else "",
                "visibility": str(getattr(policy, "visibility", "unknown")) if policy else "unknown",
                "public_facing": public_facing,
                "path_ref": _repo_ref(repo, policy),
                "path_public_safe": _repo_ref(repo, policy) if public_facing else _normalized_path(repo),
                "classification": classification,
                "classification_reasons": reasons,
                "next_action": next_action,
                "write_boundary": (
                    "central_only"
                    if classification == "protected-central-only"
                    else "reviewed_policy_required"
                ),
                "mail_policy_present": _policy_matches_any(repo, mail_policies),
                "enrollment_policy_present": _policy_matches_any(repo, enrollment_policies),
                "contract_present": (repo / ".digital-asset" / "dad-integration.json").exists(),
                "authority_boundary": CENTRAL_ONLY_BOUNDARY,
            }
        )
        record.pop("local_path")
        records.append(record)

    github_summary = [
        {
            "source_id": str(getattr(source, "id", "")),
            "owner": str(getattr(source, "owner", "")),
            "enabled": bool(getattr(source, "enabled", True)),
            "include_private": bool(getattr(source, "include_private", True)),
            "inventory_status": "configured_source_only",
            "next_action": (
                "Import reviewed GitHub repository list or connector output before delivery. "
                "Discovery does not authorize local writes."
            ),
        }
        for source in github_sources or []
    ]
    records.sort(key=lambda item: (item["classification"], item["repo_name"].lower()))
    counts: dict[str, int] = {}
    for record in records:
        counts[record["classification"]] = counts.get(record["classification"], 0) + 1

    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "report_id": stable_id("dad-repo-inventory", str(hub_root), str(len(records))),
        "repo_count": len(records),
        "classification_counts": counts,
        "records": records,
        "github_sources": github_summary,
        "source_warnings": source_warnings,
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    out_dir = hub_root / REPO_INVENTORY_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "reconciled_inventory.json"
    md_path = out_dir / "reconciled_inventory.md"
    _write_json(json_path, payload)
    atomic_write_text(md_path, _inventory_markdown(payload))
    return {"inventory": payload, "json_path": str(json_path), "markdown_path": str(md_path)}


def build_dad_cadence_plan(
    hub_root: Path,
    *,
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    repo_ids = sorted(
        {
            str(getattr(policy, "id", "") or getattr(policy, "alias", ""))
            for policy in [*(mail_policies or []), *(enrollment_policies or [])]
            if str(getattr(policy, "id", "") or getattr(policy, "alias", ""))
        }
    )
    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "cadence_id": "dad-cadence:daily-mail-weekly-library-checks",
        "repo_count": len(repo_ids),
        "repos": repo_ids,
        "daily": {
            "owner": "dad_hub",
            "operations": [
                "mail collect from reviewed repo outboxes",
                "mail route with provenance and public-release gates",
                "mail deliver only to .digital-asset/mail/** for policy-approved repos",
                "mail digest freshness update",
            ],
            "preflight_behavior": "Warn only when mail digest is older than 24 hours.",
            "write_boundary": ".digital-asset/mail/**",
        },
        "weekly": {
            "owner": "dad_hub",
            "operations": [
                "asset offering freshness check",
                "agent skill update/retirement/replacement check",
                "coding harness update and research-opportunity check",
                "template/reference architecture update check",
                "governance-map and data-map drift check",
                "enrollment contract update-plan generation",
            ],
            "preflight_behavior": (
                "Surface stale weekly checks as warnings; do not run heavy scans on every preflight."
            ),
            "write_boundary": "central reports plus candidate mail; enrollment apply still needs approval",
        },
        "blocked_operations": [
            "no normal recurring source edits",
            "no hook installation outside approved enrollment apply/update-apply",
            "no private/internal/restricted/unknown origin delivery to public-facing repos without release",
            "no broad discovered-repo delivery without reviewed policy",
        ],
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    out_dir = hub_root / CADENCE_REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "dad_cadence_plan.json"
    md_path = out_dir / "dad_cadence_plan.md"
    _write_json(json_path, payload)
    atomic_write_text(md_path, _cadence_markdown(payload))
    return {"cadence": payload, "json_path": str(json_path), "markdown_path": str(md_path)}


def scout_asset_candidates(
    hub_root: Path,
    repo: Path,
    *,
    task: str = "",
    limit: int = 25,
    max_files: int = 2000,
) -> dict[str, Any]:
    methodology = load_asset_recognition_methodology(hub_root)
    candidates: list[dict[str, Any]] = []
    scanned = 0
    for path in _iter_repo_files(repo, max_files=max_files):
        scanned += 1
        rel = _safe_relative(path, repo)
        score, signals = _score_asset_path(rel, methodology, task=task)
        if score < float(methodology.get("min_candidate_score", 30)):
            continue
        candidates.append(
            {
                "candidate_id": stable_id("dad-asset-candidate", _normalized_path(repo), rel),
                "path": rel,
                "score": round(score, 2),
                "importance_tier": _importance_tier(score, methodology),
                "signals": signals,
                "source_policy": "path-and-metadata-only; file contents were not copied",
                "score_interpretation": (
                    "Deterministic candidate routing score from methodology weights; "
                    "not proof of asset value or readiness."
                ),
                "review_status": "candidate",
            }
        )
    candidates.sort(key=lambda item: (item["score"], item["path"]), reverse=True)
    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "repo": repo.name,
        "task": task,
        "methodology_id": methodology["methodology_id"],
        "methodology_version": methodology.get("methodology_version", ""),
        "methodology_ref": "registry/asset-recognition-methodology.json",
        "score_scale": "0-100+ candidate routing score; higher means inspect earlier, not promote automatically",
        "score_formula_summary": (
            "Sum matching candidate location weights and recognition signal weights, "
            "then subtract downgrade signal weights and clamp at zero."
        ),
        "limit": limit,
        "files_scanned": scanned,
        "candidate_count": len(candidates),
        "returned_candidate_count": len(candidates[:limit]),
        "candidates": candidates[:limit],
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    path = hub_root / "processed" / "reports" / f"asset-recognition-{_repo_report_slug(repo)}.json"
    _write_json(path, payload)
    return {"asset_candidates": payload, "path": str(path)}


def discover_harness_opportunities(
    hub_root: Path,
    repo: Path,
    *,
    task: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    methodology = load_harness_discovery_methodology(hub_root)
    context = _repo_context(repo)
    context_tokens = _tokenize(
        [
            task,
            context.get("languages", []),
            context.get("repo_type", ""),
            context.get("domains", []),
            context.get("context_tags", []),
            repo.name,
        ]
    )
    existing_families = {
        str(harness.get("family", ""))
        for harness in load_harnesses(hub_root).get("harnesses", [])
    }
    candidates: list[dict[str, Any]] = []
    for signal in methodology.get("opportunity_signals", []):
        keywords = _tokenize(signal.get("keywords", []))
        overlap = sorted(context_tokens & keywords)
        score = min(100.0, len(overlap) * float(signal.get("weight", 10)))
        family = str(signal.get("candidate_family", ""))
        if family and family not in existing_families:
            score += float(methodology.get("missing_family_bonus", 15))
        if score <= 0:
            continue
        recommended_action = (
            "evaluate_existing_harness"
            if family in existing_families
            else "research_candidate_harness"
        )
        candidates.append(
            {
                "opportunity_id": stable_id(
                    "dad-harness-opportunity", repo.name, str(signal.get("signal_id", "")), task
                ),
                "signal_id": signal["signal_id"],
                "candidate_family": family,
                "score": round(score, 2),
                "matched_keywords": overlap,
                "recommended_action": recommended_action,
                "external_research_gate": methodology.get("external_research_policy", {}),
                "score_interpretation": (
                    "Deterministic candidate routing score from matched context keywords; "
                    "not proof that a harness exists or is sufficient."
                ),
                "review_status": "candidate",
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "repo": repo.name,
        "task": task,
        "methodology_id": methodology["methodology_id"],
        "methodology_version": methodology.get("methodology_version", ""),
        "methodology_ref": "registry/harness-discovery-methodology.json",
        "score_scale": "0-100+ opportunity routing score; higher means inspect earlier, not promote automatically",
        "score_formula_summary": (
            "Matched keyword count times signal weight, plus missing-family bonus when no existing "
            "harness family covers the signal."
        ),
        "context": context,
        "limit": limit,
        "opportunity_count": len(candidates),
        "returned_opportunity_count": len(candidates[:limit]),
        "opportunities": candidates[:limit],
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    path = hub_root / HARNESS_REPORT_DIR / f"discovery-{_repo_report_slug(repo)}.json"
    _write_json(path, payload)
    return {"discovery": payload, "path": str(path)}


def record_usage(
    hub_root: Path,
    repo: Path,
    *,
    asset_id: str,
    status: str,
    recorded_by: str = "unknown",
    source_ref: str = "",
    reason: str = "",
    mail_id: str = "",
    adoption_id: str = "",
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    if not repo.exists() or not repo.is_dir():
        raise ValueError(f"Usage target repo does not exist: {repo}")
    normalized_status = status.lower().replace("-", "_")
    if normalized_status not in USAGE_STATUSES:
        raise ValueError("status must be using, watching, rejected, or retired")
    policy = _repo_policy(repo, mail_policies=mail_policies, enrollment_policies=enrollment_policies)
    protected, protection_reason = _repo_write_protection(policy)
    repo_ref = _repo_ref(repo, policy)
    timestamp = utc_now()
    usage_id = stable_id("dad-usage", repo_ref, asset_id, normalized_status, source_ref)
    record = {
        "schema_version": "0.1.0",
        "usage_id": usage_id,
        "repo": repo_ref,
        "repo_id": str(getattr(policy, "id", "") if policy else ""),
        "asset_id": asset_id,
        "status": normalized_status,
        "recorded_at": timestamp,
        "recorded_by": recorded_by,
        "source_ref": source_ref,
        "reason": reason,
        "mail_id": mail_id,
        "adoption_id": adoption_id,
        "upgrade_channel": "dad_mail",
        "local_write": not protected,
        "central_only_reason": protection_reason if protected else "",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    central_appended = _append_unique(hub_root / CENTRAL_USAGE_LEDGER, record, "usage_id")
    local_appended = False
    local_path = repo / LOCAL_USAGE_LEDGER
    if not protected:
        local_appended = _append_unique(local_path, record, "usage_id")
    return {
        "usage": record,
        "central_appended": central_appended,
        "local_appended": local_appended,
        "central_ledger": str(hub_root / CENTRAL_USAGE_LEDGER),
        "local_ledger": "" if protected else str(local_path),
        "central_only": protected,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def usage_upgrades(
    hub_root: Path,
    repo: Path,
    *,
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    policy = _repo_policy(repo, mail_policies=mail_policies, enrollment_policies=enrollment_policies)
    repo_ref = _repo_ref(repo, policy)
    rows = [
        item
        for item in [
            *_read_jsonl(hub_root / CENTRAL_USAGE_LEDGER),
            *_read_jsonl(repo / LOCAL_USAGE_LEDGER),
        ]
        if str(item.get("repo")) in {repo_ref, _normalized_path(repo)}
        and str(item.get("status")) in {"using", "watching"}
    ]
    by_asset = {item["offering_id"]: item for item in load_offerings(hub_root).get("offerings", [])}
    upgrades: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        asset_id = str(row.get("asset_id", ""))
        if asset_id in seen:
            continue
        seen.add(asset_id)
        offering = by_asset.get(asset_id)
        if not offering:
            continue
        known_upgrades = offering.get("known_upgrades", [])
        if known_upgrades:
            upgrades.append(
                {
                    "asset_id": asset_id,
                    "name": offering["name"],
                    "current_usage_status": row["status"],
                    "known_upgrades": known_upgrades,
                    "upgrade_channel": offering.get("upgrade_channel", "dad_mail"),
                    "authority_boundary": "Upgrade notice is candidate mail until reviewed locally.",
                }
            )
    return {
        "repo": repo_ref,
        "tracked_usage_count": len(rows),
        "upgrade_count": len(upgrades),
        "upgrades": upgrades,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def list_harnesses(hub_root: Path) -> dict[str, Any]:
    return load_harnesses(hub_root)


def recommend_harnesses(
    hub_root: Path,
    repo: Path,
    *,
    task: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    context = _repo_context(repo)
    harnesses = load_harnesses(hub_root).get("harnesses", [])
    methodology = load_usefulness_methodology(hub_root)
    offerings = [
        {
            "offering_id": harness["harness_id"],
            "name": harness["name"],
            "offering_type": "harness",
            "path": harness["path"],
            "languages": harness.get("languages", []),
            "repo_types": harness.get("repo_types", []),
            "domains": harness.get("domains", []),
            "context_tags": harness.get("context_tags", []),
            "task_types": harness.get("task_types", []),
            "capabilities": harness.get("capabilities", []),
            "public_safe": harness.get("public_safe", False),
            "review_status": harness.get("review_status", "candidate"),
        }
        for harness in harnesses
    ]
    matches = [
        {
            **score_offering(context, offering, methodology, task=task),
            "harness_id": offering["offering_id"],
        }
        for offering in offerings
    ]
    matches.sort(key=lambda item: item["usefulness_score"], reverse=True)
    return {
        "repo": _normalized_path(repo),
        "task": task,
        "recommendation_count": len(matches[:limit]),
        "recommendations": matches[:limit],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def harness_research(hub_root: Path, harness_id: str) -> dict[str, Any]:
    harness = _harness_by_id(hub_root, harness_id)
    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "harness_id": harness_id,
        "status": "candidate_research_packet",
        "research_questions": harness.get("research_questions", []),
        "source_evidence": harness.get("source_evidence", []),
        "next_review_gate": "Human review before promoting research output into reviewed guidance.",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    path = hub_root / HARNESS_REPORT_DIR / f"research-{_slug(harness_id)}.json"
    _write_json(path, payload)
    return {"research": payload, "path": str(path)}


def harness_evaluate(hub_root: Path, harness_id: str, repo: Path) -> dict[str, Any]:
    harness = _harness_by_id(hub_root, harness_id)
    recommendation = recommend_harnesses(hub_root, repo, task=" ".join(harness.get("task_types", [])), limit=10)
    match = next(
        (item for item in recommendation["recommendations"] if item["harness_id"] == harness_id),
        None,
    )
    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "harness_id": harness_id,
        "repo": _normalized_path(repo),
        "evaluation_status": "candidate_only",
        "match": match,
        "validation_commands": harness.get("validation_commands", []),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    path = hub_root / HARNESS_REPORT_DIR / (
        f"evaluate-{_slug(harness_id)}-{_repo_report_slug(repo)}.json"
    )
    _write_json(path, payload)
    return {"evaluation": payload, "path": str(path)}


def harness_package(hub_root: Path, harness_id: str) -> dict[str, Any]:
    harness = _harness_by_id(hub_root, harness_id)
    root = hub_root / harness["path"]
    if not root.exists():
        raise FileNotFoundError(root)
    package_path = hub_root / HARNESS_REPORT_DIR / f"{_slug(harness_id)}.zip"
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root.parent))
    manifest = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "harness_id": harness_id,
        "package_path": str(package_path),
        "source_path": harness["path"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _write_json(hub_root / HARNESS_REPORT_DIR / f"{_slug(harness_id)}.package.json", manifest)
    return manifest


def _discover_git_roots(base: Path, *, max_depth: int, follow_symlinks: bool) -> list[Path]:
    roots: list[Path] = []
    base = base.resolve()
    base_is_workspace_root = _normalize_name(base.name) in WORKSPACE_ROOT_NAMES
    for current_raw, dirs, files in os.walk(base, topdown=True, followlinks=follow_symlinks):
        current = Path(current_raw)
        dirs[:] = [
            item
            for item in dirs
            if item.lower() not in REPO_SKIP_DIRS
            and not item.lower().startswith("pytest-of-")
        ]
        try:
            depth = len(current.relative_to(base).parts)
        except ValueError:
            depth = 0
        if depth >= max_depth:
            dirs[:] = []
        if ".git" in dirs or ".git" in files or (current / ".git").exists():
            roots.append(current)
            if not (current == base and base_is_workspace_root):
                dirs[:] = []
    return sorted(set(roots), key=lambda item: str(item).lower())


def _inventory_seed(repo: Path, *, source_signal: str) -> dict[str, Any]:
    return {
        "repo_record_id": stable_id("dad-repo-record", _normalized_path(repo)),
        "repo_name": repo.name,
        "local_path": _normalized_path(repo),
        "source_signals": [source_signal],
    }


def _add_inventory_signal(
    records_by_path: dict[str, dict[str, Any]],
    repo: Path,
    source_signal: str,
) -> None:
    key = _normalized_path(repo)
    if key not in records_by_path:
        records_by_path[key] = _inventory_seed(repo, source_signal=source_signal)
        return
    signals = records_by_path[key].setdefault("source_signals", [])
    if source_signal not in signals:
        signals.append(source_signal)


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _path_marker_match(
    repo: Path,
    markers: set[str],
    *,
    repo_name_contains: bool = False,
) -> bool:
    normalized_parts = {_normalize_name(part) for part in repo.parts[-5:]}
    normalized_name = _normalize_name(repo.name)
    return any(
        marker in normalized_parts
        or marker == normalized_name
        or (repo_name_contains and marker in normalized_name)
        for marker in markers
    )


def _policy_matches_any(repo: Path, policies: Sequence[Any] | None) -> bool:
    return any(_policy_matches(repo, policy) for policy in policies or [])


def _classify_inventory_repo(
    repo: Path,
    *,
    policy: Any | None,
    duplicate_basename: bool,
) -> tuple[str, list[str], str]:
    reasons: list[str] = []
    if _path_marker_match(repo, PROTECTED_REPO_MARKERS, repo_name_contains=True):
        reasons.append("Logos repo marker requires protected central-only handling.")
        return (
            "protected-central-only",
            reasons,
            "Require explicit Logos local-write approval before any repair or enrollment write.",
        )
    if policy and bool(getattr(policy, "write_protected", False)):
        reasons.append(str(getattr(policy, "write_protection_reason", "")) or "policy write_protected")
        return (
            "protected-central-only",
            reasons,
            "Keep central-only unless a human-approved policy changes write protection.",
        )
    if policy and bool(getattr(policy, "active_hold", False)):
        reasons.append(str(getattr(policy, "active_hold_reason", "")) or "policy active_hold")
        return (
            "protected-central-only",
            reasons,
            "Do not apply enrollment updates while the active hold remains.",
        )
    if _path_marker_match(repo, ARCHIVE_MARKERS) and not policy:
        reasons.append("Archive/snapshot path marker and no reviewed policy.")
        return "archive-ignore", reasons, "Leave out of enrollment unless policy promotes it."
    if (duplicate_basename or _path_marker_match(repo, DUPLICATE_MARKERS)) and not policy:
        reasons.append("Duplicate/reference/temp path marker or duplicate basename without policy.")
        return "duplicate-ignore", reasons, "Keep central record only; avoid mailbox delivery."
    if _normalize_name(repo.name) in WORKSPACE_ROOT_NAMES and not policy:
        reasons.append("Workspace/container root marker and no reviewed repo policy.")
        return (
            "duplicate-ignore",
            reasons,
            "Track child repos through inventory; do not enroll the workspace container.",
        )
    if policy and bool(getattr(policy, "enrollment_enabled", True)):
        reasons.append("Reviewed enrollment/mail policy is present.")
        return "enroll", reasons, "Use reviewed waves and approval IDs for any broad writes."
    if _path_marker_match(repo, LAW_FIRM_SIDE_MARKERS, repo_name_contains=True):
        reasons.append("LawFirm side/candidate marker such as intake, talent, or intelligence.")
        return "side-project", reasons, "Track centrally; enroll only after explicit classification."
    if _path_marker_match(repo, LAW_FIRM_KERNEL_MARKERS, repo_name_contains=True):
        reasons.append("Potential LawFirm OS substrate/kernel marker.")
        return (
            "needs-human-classification",
            reasons,
            "Review as possible kernel repo before enrollment.",
        )
    if _path_marker_match(
        repo,
        {"mocktrial", "mock-trial", "albert", "trial-simulation"},
        repo_name_contains=True,
    ):
        reasons.append("Mock Trial/Albert marker; not Logos-protected by default.")
        return (
            "needs-human-classification",
            reasons,
            "Treat as an active normal repo unless policy says otherwise.",
        )
    if (repo / ".digital-asset" / "dad-integration.json").exists():
        reasons.append("Existing DAD contract found without reviewed policy match.")
        return (
            "needs-human-classification",
            reasons,
            "Reconcile the existing contract into reviewed policy before updates.",
        )
    reasons.append("No reviewed policy or special classification marker.")
    return (
        "needs-human-classification",
        reasons,
        "Add to reviewed policy or explicitly ignore before DAD delivery/enrollment.",
    )


def _inventory_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DAD Repo Inventory Reconciliation",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        CENTRAL_ONLY_BOUNDARY,
        "",
        "## Counts",
        "",
    ]
    for name, count in sorted(payload.get("classification_counts", {}).items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Repos", "", "| Repo | Classification | Reasons | Next action |", "| --- | --- | --- | --- |"])
    for record in payload.get("records", []):
        reasons = "; ".join(record.get("classification_reasons", []))
        lines.append(
            "| "
            f"{record['repo_name']} | {record['classification']} | "
            f"{reasons} | {record['next_action']} |"
        )
    if payload.get("github_sources"):
        lines.extend(["", "## GitHub Sources", ""])
        for source in payload["github_sources"]:
            lines.append(
                f"- {source['source_id']} ({source['owner']}): {source['inventory_status']}"
            )
    if payload.get("source_warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in payload["source_warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _cadence_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DAD Cadence Plan",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        CENTRAL_ONLY_BOUNDARY,
        "",
        "## Daily Mail",
        "",
    ]
    for operation in payload["daily"]["operations"]:
        lines.append(f"- {operation}")
    lines.extend(
        [
            "",
            f"Preflight behavior: {payload['daily']['preflight_behavior']}",
            f"Write boundary: `{payload['daily']['write_boundary']}`",
            "",
            "## Weekly Library Checks",
            "",
        ]
    )
    for operation in payload["weekly"]["operations"]:
        lines.append(f"- {operation}")
    lines.extend(
        [
            "",
            f"Preflight behavior: {payload['weekly']['preflight_behavior']}",
            f"Write boundary: {payload['weekly']['write_boundary']}",
            "",
            "## Blocked Operations",
            "",
        ]
    )
    for operation in payload["blocked_operations"]:
        lines.append(f"- {operation}")
    return "\n".join(lines) + "\n"


def _iter_repo_files(repo: Path, *, max_files: int) -> list[Path]:
    files: list[Path] = []
    if not repo.exists():
        raise FileNotFoundError(repo)
    if not repo.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo}")
    for current_raw, dirs, filenames in os.walk(repo, topdown=True):
        dirs[:] = [
            item
            for item in dirs
            if item.lower() not in REPO_SKIP_DIRS
            and not item.lower().startswith("pytest-of-")
        ]
        for filename in filenames:
            path = Path(current_raw) / filename
            if path.is_file():
                files.append(path)
                if len(files) >= max_files:
                    return files
    return files


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _score_asset_path(rel_path: str, methodology: dict[str, Any], *, task: str) -> tuple[float, list[str]]:
    lowered = rel_path.lower().replace("\\", "/")
    score = 0.0
    signals: list[str] = []
    for location in methodology.get("candidate_locations", []):
        patterns = [str(pattern).lower() for pattern in location.get("patterns", [])]
        if any(_glob_match(lowered, pattern) for pattern in patterns):
            weight = float(location.get("weight", 0))
            score += weight
            signals.append(f"location:{location['location_id']}:+{weight:g}")
    path_tokens = _tokenize(lowered)
    task_tokens = _tokenize(task)
    suffix = Path(lowered).suffix
    for signal in methodology.get("recognition_signals", []):
        matched = False
        keywords = _tokenize(signal.get("path_keywords", []))
        if keywords and path_tokens & keywords:
            matched = True
        extensions = set(signal.get("extensions", []))
        if extensions and suffix in extensions:
            matched = True
        task_keywords = _tokenize(signal.get("task_keywords", []))
        if task_keywords and task_tokens & task_keywords:
            matched = True
        if matched:
            weight = float(signal.get("weight", 0))
            score += weight
            signals.append(f"signal:{signal['signal_id']}:+{weight:g}")
    for downgrade in methodology.get("downgrade_signals", []):
        patterns = [str(pattern).lower() for pattern in downgrade.get("patterns", [])]
        if any(_glob_match(lowered, pattern) for pattern in patterns):
            weight = float(downgrade.get("weight", 0))
            score -= weight
            signals.append(f"downgrade:{downgrade['signal_id']}:-{weight:g}")
    return max(0.0, score), signals


def _glob_match(value: str, pattern: str) -> bool:
    if fnmatch.fnmatch(value, pattern):
        return True
    if pattern.startswith("**/") and fnmatch.fnmatch(value, pattern[3:]):
        return True
    if "/**/" in pattern:
        zero_depth = pattern.replace("/**/", "/")
        if fnmatch.fnmatch(value, zero_depth):
            return True
    return False


def _importance_tier(score: float, methodology: dict[str, Any]) -> str:
    tiers = sorted(
        methodology.get("importance_tiers", []),
        key=lambda item: float(item.get("min_score", 0)),
        reverse=True,
    )
    for tier in tiers:
        if score >= float(tier.get("min_score", 0)):
            return str(tier.get("tier", "candidate"))
    return "candidate"


def _harness_by_id(hub_root: Path, harness_id: str) -> dict[str, Any]:
    matches = [
        harness
        for harness in load_harnesses(hub_root).get("harnesses", [])
        if harness.get("harness_id") == harness_id
    ]
    if not matches:
        raise ValueError(f"Unknown harness: {harness_id}")
    return matches[0]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def _repo_report_slug(repo: Path) -> str:
    suffix = stable_id("dad-repo-report", _normalized_path(repo)).split(":")[-1][:8]
    return f"{_slug(repo.name)}-{suffix}"


def _repo_slug(repo: Path) -> str:
    short_id = stable_id("dad-repo-path", _normalized_path(repo)).rsplit(":", 1)[-1][:10]
    return f"{_slug(repo.name)}-{short_id}"
