from __future__ import annotations

import json
import fnmatch
import os
import re
import subprocess
import time
import zipfile
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .ids import stable_id
from .intelligence_routing import recommend_start_tiers
from .rust_bridge.dad_scan_core import validate_repo_inventory_probe_summary
from .transport import data_path
from .utils import append_jsonl, atomic_write_text, json_dumps, sha256_bytes, sha256_file, sha256_text_file_lf, utc_now

NEEDS_REGISTRY = Path("registry") / "dad-needs-registry.json"
OFFERINGS_REGISTRY = Path("registry") / "dad-offerings-registry.json"
USEFULNESS_METHODOLOGY = Path("registry") / "dad-usefulness-methodology.json"
ASSET_RECOGNITION_METHODOLOGY = Path("registry") / "asset-recognition-methodology.json"
HARNESS_DISCOVERY_METHODOLOGY = Path("registry") / "harness-discovery-methodology.json"
HARNESS_REGISTRY = Path("registry") / "coding-harness-registry.json"
NON_NEGOTIABLES_REGISTRY = Path("registry") / "non-negotiables.json"
ASSET_PATTERN_REGISTRY = Path("registry") / "asset-pattern-registry.json"
ADDRESS_MODEL_REGISTRY = Path("registry") / "dad-address-model-registry.json"
CENTRAL_USAGE_LEDGER = Path("processed") / "usage" / "repo-asset-usage.jsonl"
DECISION_TRACE_LEDGER = Path("processed") / "usage" / "decision-traces.jsonl"
HARNESS_OUTCOME_LEDGER = Path("processed") / "usage" / "harness-outcomes.jsonl"
HARNESS_REPORT_DIR = Path("processed") / "harnesses"
REPO_INVENTORY_DIR = Path("processed") / "repo_inventory"
CADENCE_REPORT_DIR = Path("processed") / "cadence"
LOCAL_USAGE_LEDGER = Path(".digital-asset") / "dad-usage.jsonl"
LOCAL_ASSET_INDEX = Path(".digital-asset") / "assets" / "index.jsonl"
LOCAL_ASSET_ADOPTION = Path(".digital-asset") / "assets" / "adoption.jsonl"
LOCAL_ASSET_README = Path(".digital-asset") / "assets" / "README.md"
LOCAL_LEARNING_LEDGER = Path(".digital-asset") / "learning" / "events.jsonl"
LEGACY_LEARNING_LEDGER = Path(".digital-asset-directory") / "learning" / "events.jsonl"
LEGACY_DAD_INGEST_MANIFEST = Path(".digital-asset") / "dad-ingest" / "asset_manifest.json"
REPO_ASSET_REPORT_DIR = Path("processed") / "reports" / "repo_local_assets"
REPO_INVENTORY_METHODOLOGY = Path("src") / "digital_asset_directory" / "dad_library.py"
REPO_INVENTORY_INPUT_REFS = (
    REPO_INVENTORY_METHODOLOGY,
    Path("src") / "digital_asset_directory" / "config.py",
)
REPO_INVENTORY_RUST_PARITY_INPUT_REFS = (
    REPO_INVENTORY_METHODOLOGY,
    Path("src") / "digital_asset_directory" / "rust_bridge" / "dad_scan_core.py",
    Path("tools") / "dad_scan_core" / "src" / "repo_probe.rs",
    Path("tools") / "dad_scan_core" / "src" / "models.rs",
)
REPO_INVENTORY_HASH_POLICY = "text-lf-normalized-v1"
REPO_INVENTORY_UNBORN_HEAD = "UNBORN"


def central_usage_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "usage")


def central_usage_path(hub_root: Path, relative_path: Path) -> Path:
    return central_usage_dir(hub_root) / relative_path.relative_to(Path("processed") / "usage")


def harness_report_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "harness_reports")


def repo_inventory_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "repo_inventory")


def cadence_report_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "cadence")


def central_reports_dir(hub_root: Path) -> Path:
    return data_path(hub_root, "central_reports")


USAGE_STATUSES = {"using", "watching", "depends_on", "dependency_candidate", "rejected", "retired"}
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
REPO_ASSET_SURFACE_BOUNDARY = (
    "Repo-local digital asset directories are source-repo owned candidate memory. "
    "DAD collection reads metadata pointers only; it does not copy private rows, "
    "raw source blobs, secrets, generated databases, or source authority."
)
LOCAL_ASSET_STANDARD_VERSION = "0.1.0"
LOCAL_ASSET_ALLOWED_FIELDS = {
    "asset_id",
    "title",
    "name",
    "asset_type",
    "local_path",
    "path",
    "source_paths",
    "summary",
    "problem_solved",
    "tags",
    "context_tags",
    "pattern_id",
    "pattern_ids",
    "validation_commands",
    "source_refs",
    "sensitivity",
    "review_status",
    "lifecycle_status",
    "leverage",
    "fractal_address",
    "upgrade_channel",
    "applies_when",
    "does_not_apply_when",
    "graph_tags",
    "novelty_claim",
    "usefulness_context",
    "parent_asset_id",
    "derived_from",
    "workflow_ref",
    "learning_ref",
    "updated_at",
    "created_at",
}
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
    ".tmp",
    "_codex_worktrees",
    ".worktrees",
    "target",
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


def _is_repo_skip_dir_name(name: str) -> bool:
    return _repo_inventory_skip_reason(name) is not None


def _repo_inventory_skip_reason(name: str) -> str | None:
    lowered = name.lower()
    if lowered.startswith(("pytest-of-", "pytest_tmp", "pytest-tmp")):
        return "pytest temp workspace"
    if lowered in REPO_SKIP_DIRS:
        return "repo discovery skip directory"
    return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _methodology_hash(path: Path) -> str:
    return f"sha256:{sha256_file(path)}"


def _repo_inventory_hash(path: Path) -> str:
    return f"sha256:{sha256_text_file_lf(path)}"


def _existing_input_hashes(
    hub_root: Path,
    refs: Sequence[Path],
    *,
    repo_inventory_policy: bool = False,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for ref in refs:
        path = hub_root / ref
        if path.exists():
            hashes[ref.as_posix()] = (
                _repo_inventory_hash(path) if repo_inventory_policy else _methodology_hash(path)
            )
    return hashes


def _methodology_metadata(
    hub_root: Path,
    ref: Path,
    *,
    repo_inventory_policy: bool = False,
) -> dict[str, str]:
    path = hub_root / ref
    if not path.exists():
        return {}
    return {
        "methodology_ref": ref.as_posix(),
        "methodology_hash": (
            _repo_inventory_hash(path) if repo_inventory_policy else _methodology_hash(path)
        ),
    }


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


def _read_jsonl_tolerant(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            malformed.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "error": exc.msg,
                }
            )
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
        else:
            malformed.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "error": "row is not a JSON object",
                }
            )
    return records, malformed


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _append_unique(path: Path, record: dict[str, Any], key: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {str(item.get(key, "")) for item in _read_jsonl(path)}
    if str(record.get(key, "")) in existing:
        return False
    append_jsonl(path, record)
    return True


def _normalized_path(value: str | Path) -> str:
    return str(Path(value).resolve()).replace("\\", "/")


def _inventory_file_ref(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        normalized = str(path.resolve()).replace("\\", "/")
        return f"path-sha256:{sha256_bytes(normalized.encode('utf-8'))}"


def _policy_path(policy: Any) -> str:
    try:
        return _normalized_path(getattr(policy, "path"))
    except (AttributeError, TypeError):
        return ""


def _policy_matches(repo: Path, policy: Any) -> bool:
    normalized = _normalized_path(repo)
    return normalized == _policy_path(policy)


def _repo_policy(
    repo: Path,
    *,
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
    prefer_enrollment: bool = False,
) -> Any | None:
    ordered = (
        [*(enrollment_policies or []), *(mail_policies or [])]
        if prefer_enrollment
        else [*(mail_policies or []), *(enrollment_policies or [])]
    )
    matches = [
        policy
        for policy in ordered
        if _policy_matches(repo, policy)
    ]
    return matches[0] if matches else None


def _repo_ref(repo: Path, policy: Any | None = None) -> str:
    if policy and bool(getattr(policy, "public_facing", False)):
        return f"dad://repo/{getattr(policy, 'id', repo.name)}"
    return _normalized_path(repo)


def _inventory_repo_ref(
    repo: Path,
    *,
    repo_id: str,
    policy: Any | None,
    public_facing: bool,
    local_paths_allowed: bool,
) -> str:
    if public_facing and not local_paths_allowed:
        return f"dad://repo/{repo_id or _slug(repo.name)}"
    return _repo_ref(repo, policy)


def _force_public_safe_inventory_record(
    record: dict[str, Any],
    *,
    public_ref: str,
    public_name: str = "",
) -> None:
    """Redact local-path fields after late evidence proves the repo is public-facing."""

    local_paths_allowed = bool(record.get("local_paths_allowed", False))
    if public_name and not local_paths_allowed:
        record["repo_name"] = public_name
    record["public_facing"] = True
    record["visibility"] = "public"
    if not local_paths_allowed:
        record["path_ref"] = public_ref
    record["path_public_safe"] = public_ref
    record["git_state"] = _inventory_report_git_state(
        record.get("git_state", {}),
        public_facing=True,
        local_paths_allowed=local_paths_allowed,
    )


def _policy_local_paths_allowed(policy: Any | None) -> bool:
    return bool(getattr(policy, "local_paths_allowed", False)) if policy else False


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


def _coverage(query_values: Any, target_values: Any) -> float:
    query_tokens = _tokenize(query_values)
    target_tokens = _tokenize(target_values)
    if not query_tokens or not target_tokens:
        return 0.0
    return len(query_tokens & target_tokens) / len(target_tokens)


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


def load_non_negotiables(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / NON_NEGOTIABLES_REGISTRY)


def load_asset_patterns(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / ASSET_PATTERN_REGISTRY)


def load_address_model_registry(hub_root: Path) -> dict[str, Any]:
    return _load_json(hub_root / ADDRESS_MODEL_REGISTRY)


PATTERN_MATCH_STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "without",
}
PATTERN_MATCH_BASIS = (
    "deterministic keyword overlap between task/context tokens and pattern "
    "id/label/description/positive-signal tokens after stopword removal; "
    "count-ranked routing aid, not a value score"
)


def match_asset_patterns(
    hub_root: Path,
    *,
    task: str = "",
    repo: Path | None = None,
    repo_context: dict[str, Any] | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Match task/context tokens to asset-pattern cards so builds know what to watch for.

    Matched terms are raw overlap observations used only for routing which pattern
    cards to surface; they carry no value claim and no promotion authority.
    """
    registry = load_asset_patterns(hub_root)
    context = repo_context or (_repo_context(repo) if repo else {})
    context_tokens = _tokenize(
        [
            task,
            context.get("languages", []),
            context.get("repo_type", ""),
            context.get("domains", []),
            context.get("context_tags", []),
        ]
    ) - PATTERN_MATCH_STOPWORDS
    matches: list[dict[str, Any]] = []
    for pattern in registry.get("patterns", []):
        pattern_tokens = _tokenize(
            [
                pattern.get("id", ""),
                pattern.get("label", ""),
                pattern.get("description", ""),
                pattern.get("positive_signals", []),
            ]
        ) - PATTERN_MATCH_STOPWORDS
        overlap = sorted(context_tokens & pattern_tokens)
        if not overlap:
            continue
        matches.append(
            {
                "pattern_id": str(pattern.get("id", "")),
                "label": str(pattern.get("label", "")),
                "leverage": str(pattern.get("leverage", "")),
                "matched_terms": overlap,
                "watch_for": list(pattern.get("positive_signals", []))[:4],
                "report_via": "dad:need:asset-pattern-sightings",
            }
        )
    matches.sort(key=lambda item: (-len(item["matched_terms"]), item["pattern_id"]))
    return {
        "registry_version": str(registry.get("registry_version", "")),
        "pattern_count": len(registry.get("patterns", [])),
        "match_basis": PATTERN_MATCH_BASIS,
        "matches": matches[:limit],
        "authority_boundary": str(registry.get("rule", "")) or AUTHORITY_BOUNDARY,
    }


def _decision_for_score(score: float, needs_human_review: bool, methodology: dict[str, Any]) -> str:
    if needs_human_review:
        return "needs_human_review"
    thresholds = methodology.get("thresholds", {})
    required = {"use_now", "save_for_future", "defer"}
    missing = sorted(required - set(thresholds))
    if missing:
        raise ValueError("DAD usefulness methodology missing thresholds: " + ", ".join(missing))
    if score >= float(thresholds["use_now"]):
        return "use_now"
    if score >= float(thresholds["save_for_future"]):
        return "save_for_future"
    if score >= float(thresholds["defer"]):
        return "defer"
    return "reject"


def _human_review_needed(repo_context: dict[str, Any], offering: dict[str, Any]) -> bool:
    if repo_context.get("public_facing") and not bool(offering.get("public_safe", False)):
        return True
    if str(offering.get("review_status", "")) not in {"reviewed", "installed_for_local_reuse"}:
        return True
    return False


def _task_routing_intents(task: str) -> set[str]:
    """Return small, declared task families used only to order candidate cards."""
    tokens = _tokenize(task)
    intents: set[str] = set()
    if tokens & {"enroll", "enrollment", "onboard", "onboarding"}:
        intents.add("enrollment")
    if tokens & {"mail", "mailbox", "spool", "delivery", "deliver"}:
        intents.add("mail")
    if tokens & {"governance", "authority", "policy", "enforcement", "control", "controls"}:
        intents.add("governance")
    if "rust" in tokens:
        intents.add("rust")
    if tokens & {"code", "coding", "feature", "implement", "implementation", "refactor", "test", "tests", "python", "write"}:
        intents.add("coding")
    return intents


def score_offering(
    repo_context: dict[str, Any],
    offering: dict[str, Any],
    methodology: dict[str, Any],
    *,
    task: str = "",
) -> dict[str, Any]:
    weights = methodology.get("weights", {})
    language = _coverage(offering.get("languages", []), repo_context.get("languages", []))
    repo_type = _coverage(offering.get("repo_types", []), repo_context.get("repo_type", ""))
    domain = _coverage(offering.get("domains", []), repo_context.get("domains", []))
    context_tags = _coverage(offering.get("context_tags", []), repo_context.get("context_tags", []))
    task_match = _coverage(task, offering.get("task_types", []))
    capability = _coverage(task, offering.get("capabilities", []))
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
    task_tokens = _tokenize(task)
    route_tokens = _tokenize(
        [
            *offering.get("task_types", []),
            *offering.get("capabilities", []),
            *offering.get("domains", []),
            *offering.get("languages", []),
        ]
    )
    route_match_terms = sorted(task_tokens & route_tokens)
    task_intents = _task_routing_intents(task)
    route_intent_matches = sorted(task_intents & set(offering.get("routing_intents", [])))
    declared_priority = list(methodology.get("intent_priority", []))
    intent_priority = {
        intent: len(declared_priority) - index
        for index, intent in enumerate(declared_priority)
    }
    route_intent_priority = max(
        (intent_priority[intent] for intent in route_intent_matches),
        default=1 if route_intent_matches else 0,
    )
    return {
        "offering_id": offering["offering_id"],
        "name": offering["name"],
        "offering_type": offering["offering_type"],
        "path": offering["path"],
        "decision": decision,
        "usefulness_score": round(weighted, 2),
        "component_scores": component_scores,
        "route_specificity": len(route_match_terms),
        "route_match_terms": route_match_terms,
        "route_intent_matches": route_intent_matches,
        "route_intent_priority": route_intent_priority,
        "methodology_id": methodology["methodology_id"],
        "methodology_version": methodology.get("methodology_version", ""),
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
    matches.sort(
        key=lambda item: (
            -int(item["route_intent_priority"]),
            -len(item["route_intent_matches"]),
            -int(item["route_specificity"]),
            -float(item["usefulness_score"]),
            str(item["offering_id"]),
        )
    )
    return {
        "repo": _normalized_path(repo),
        "task": task,
        "context": context,
        "match_count": len(matches),
        "returned_match_count": len(matches[:limit]),
        "limit": limit,
        "matches": matches[:limit],
        "routing_basis": (
            "Declared task-family priority "
            f"{methodology.get('intent_priority', [])}, then intent-match count, exact "
            "task-token specificity, candidate usefulness score, and offering id; routing "
            "order is not proof of quality or adoption authority."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


OFFER_CHECK_BASIS = (
    "deterministic metadata comparison at thresholds 0.5: name token Jaccard "
    "(|intersection|/|union|), capability token coverage in both directions "
    "(|intersection|/|side|), and normalized path equality/prefix. Metadata-level "
    "routing only; content-level deltas still require semantic-evolution grading "
    "(registry/semantic-evolution-grade-registry.json) before merge or replacement."
)
OFFER_CHECK_VERDICT_ORDER = [
    "duplicate",
    "upgrade_candidate",
    "possible_duplicate",
    "possible_upgrade",
    "new",
]


def check_offering_novelty(
    hub_root: Path,
    *,
    name: str,
    path: str = "",
    version: str = "",
    capabilities: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Classify a proposed offering as new, duplicate, or upgrade against the registry.

    All relations are candidate routing evidence for human review; a duplicate or
    upgrade verdict never auto-merges, auto-replaces, or blocks registration by itself.
    """
    candidate_name_tokens = _tokenize(name)
    candidate_caps = _tokenize(list(capabilities or []))
    candidate_path = path.replace("\\", "/").strip().strip("/").lower()
    matches: list[dict[str, Any]] = []
    for offering in load_offerings(hub_root).get("offerings", []):
        existing_name_tokens = _tokenize(offering.get("name", ""))
        existing_caps = _tokenize(offering.get("capabilities", []))
        existing_path = str(offering.get("path", "")).replace("\\", "/").strip().strip("/").lower()
        union = candidate_name_tokens | existing_name_tokens
        name_jaccard = len(candidate_name_tokens & existing_name_tokens) / len(union) if union else 0.0
        cap_overlap = candidate_caps & existing_caps
        existing_covered = len(cap_overlap) / len(existing_caps) if existing_caps else 0.0
        candidate_covered = len(cap_overlap) / len(candidate_caps) if candidate_caps else 0.0
        path_equal = bool(candidate_path) and candidate_path == existing_path
        path_prefix = bool(candidate_path) and not path_equal and (
            candidate_path.startswith(existing_path + "/")
            or existing_path.startswith(candidate_path + "/")
        )
        relation = ""
        if path_equal:
            relation = (
                "duplicate"
                if version and version == str(offering.get("version", ""))
                else "upgrade_candidate"
            )
        elif name_jaccard >= 0.5 or max(existing_covered, candidate_covered) >= 0.5:
            new_capabilities = sorted(candidate_caps - existing_caps)
            relation = "possible_upgrade" if new_capabilities else "possible_duplicate"
        elif path_prefix:
            relation = "possible_duplicate"
        if not relation:
            continue
        matches.append(
            {
                "offering_id": offering["offering_id"],
                "existing_name": offering.get("name", ""),
                "existing_version": str(offering.get("version", "")),
                "existing_path": offering.get("path", ""),
                "relation": relation,
                "name_token_jaccard": round(name_jaccard, 3),
                "existing_capability_coverage": round(existing_covered, 3),
                "candidate_capability_coverage": round(candidate_covered, 3),
                "new_capabilities": sorted(candidate_caps - existing_caps),
                "path_equal": path_equal,
                "path_prefix_overlap": path_prefix,
            }
        )
    matches.sort(key=lambda item: OFFER_CHECK_VERDICT_ORDER.index(item["relation"]))
    verdict = matches[0]["relation"] if matches else "new"
    return {
        "schema_version": "0.1.0",
        "candidate_name": name,
        "candidate_path": path,
        "candidate_version": version,
        "verdict": verdict,
        "check_basis": OFFER_CHECK_BASIS,
        "matches": matches,
        "next_steps": [
            "Human review decides register, merge, upgrade, or reject; this check only routes.",
            "For duplicate/upgrade verdicts, run semantic-evolution grading on content-level deltas before replacing or merging.",
            "For upgrades, append a known_upgrades entry to the existing offering instead of registering a parallel one.",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def compile_context_pack(
    hub_root: Path,
    target_repo: Path,
    *,
    session_id: str,
    task: str,
    mail_digest_status: dict[str, Any] | None = None,
    deferred_mail: dict[str, Any] | None = None,
    asset_limit: int = 5,
) -> dict[str, Any]:
    created = utc_now()
    trace_id = stable_id("trace", session_id, created, _normalized_path(target_repo), task)
    warnings: list[str] = []
    try:
        non_negotiables = load_non_negotiables(hub_root)
        entries = non_negotiables.get("non_negotiables", [])[:10]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        entries = []
        warnings.append(f"non-negotiables unavailable: {exc}")
    try:
        match_payload = match_repo_offerings(hub_root, target_repo, task=task, limit=asset_limit)
        raw_assets = match_payload["matches"][:asset_limit]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raw_assets = []
        warnings.append(f"DAD offerings unavailable: {exc}")
    assets = [
        {
            "asset_id": item["offering_id"],
            "decision": item["decision"],
            "score": item["usefulness_score"],
            "path": item["path"],
            "use_when": item.get("reason", ""),
            "needs_human_review": item.get("needs_human_review", False),
        }
        for item in raw_assets
    ]
    try:
        pattern_payload = match_asset_patterns(
            hub_root, task=task, repo_context=_repo_context(target_repo), limit=3
        )
        asset_patterns = pattern_payload["matches"]
        pattern_library_version = pattern_payload["registry_version"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        asset_patterns = []
        pattern_library_version = ""
        warnings.append(f"asset pattern registry unavailable: {exc}")
    registry_hashes = {}
    for key, rel in {
        "non_negotiables": NON_NEGOTIABLES_REGISTRY,
        "dad_offerings": OFFERINGS_REGISTRY,
        "dad_usefulness_methodology": USEFULNESS_METHODOLOGY,
        "asset_pattern_registry": ASSET_PATTERN_REGISTRY,
    }.items():
        path = hub_root / rel
        if path.exists():
            registry_hashes[key] = _methodology_hash(path)
    if mail_digest_status and mail_digest_status.get("stale"):
        warnings.append("mail digest is stale or unavailable")
    deferred_payload = deferred_mail or {}
    deferred_items = list(deferred_payload.get("items") or [])[:3]
    if deferred_items:
        warnings.append(
            f"{len(deferred_items)} previously deferred mail item(s) match this task; "
            "re-triage before finishing"
        )
    intelligence_routing_advice: dict[str, Any] | None = None
    try:
        intelligence_routing_advice = recommend_start_tiers(task, hub_root)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as exc:
        warnings.append(f"intelligence routing advice unavailable: {exc}")
    pack = {
        "schema_version": "0.1.0",
        "trace_id": trace_id,
        "session_id": session_id,
        "generated_at": created,
        "task": task,
        "non_negotiables": entries,
        "assets": assets,
        "asset_patterns": asset_patterns,
        "pattern_library_version": pattern_library_version,
        "pattern_match_basis": PATTERN_MATCH_BASIS,
        "deferred_mail": deferred_items,
        "deferred_mail_basis": str(deferred_payload.get("match_basis", "")),
        "deferred_backlog_count": int(deferred_payload.get("deferred_total", 0) or 0),
        "intelligence_routing_advice": intelligence_routing_advice,
        "stop_conditions": [
            "Stop for a human when DAD recommendations conflict with local source authority.",
            "Stop before cross-repo writes, public releases, enrollment writes, or protected repo writes when DAD is unavailable.",
            "Stop when a recommendation requires human review and no reviewed local adoption decision exists.",
        ],
        "validation_commands": [
            "python -m pytest",
            "python -m digital_asset_directory.cli validate",
            "python -m digital_asset_directory.cli roadmap check --no-update",
        ],
        "registry_hashes": registry_hashes,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    trace = {
        "trace_id": trace_id,
        "session_id": session_id,
        "repo": _normalized_path(target_repo),
        "task_hash": stable_id("task", task),
        "created_at": created,
        "recommended": assets,
        "recommended_patterns": [item["pattern_id"] for item in asset_patterns],
        "resurfaced_mail": [item["mail_id"] for item in deferred_items],
        "registry_hashes": registry_hashes,
        "outcomes": [],
    }
    append_jsonl(central_usage_path(hub_root, DECISION_TRACE_LEDGER), trace)
    return pack


def record_trace_outcomes(
    hub_root: Path,
    *,
    trace_id: str,
    session_id: str,
    outcomes: dict[str, list[str]],
    summary: str,
) -> dict[str, Any]:
    if not trace_id:
        return {"trace_id": "", "recorded_count": 0}
    created = utc_now()
    rows = _read_jsonl(central_usage_path(hub_root, DECISION_TRACE_LEDGER))
    trace_seen = any(row.get("trace_id") == trace_id for row in rows)
    records: list[dict[str, Any]] = []
    for outcome, asset_ids in outcomes.items():
        for asset_id in asset_ids:
            records.append(
                {
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "asset_id": asset_id,
                    "outcome": outcome,
                    "summary": summary,
                    "created_at": created,
                    "trace_seen": trace_seen,
                }
            )
    for record in records:
        append_jsonl(
            central_usage_path(hub_root, DECISION_TRACE_LEDGER),
            {"event_type": "trace_outcome", **record},
        )
    return {"trace_id": trace_id, "recorded_count": len(records), "trace_seen": trace_seen}


def calibration_report(hub_root: Path, *, minimum_n: int = 10) -> dict[str, Any]:
    recommendations: dict[str, dict[str, Any]] = {}
    outcomes: list[dict[str, Any]] = []
    for row in _read_jsonl(central_usage_path(hub_root, DECISION_TRACE_LEDGER)):
        if row.get("event_type") == "trace_outcome":
            outcomes.append(row)
            continue
        for item in row.get("recommended", []) or []:
            key = f"{row.get('trace_id')}::{item.get('asset_id')}"
            recommendations[key] = {
                "decision": item.get("decision", "unknown"),
                "asset_id": item.get("asset_id", ""),
            }
    grouped: dict[str, dict[str, int]] = {}
    for outcome in outcomes:
        key = f"{outcome.get('trace_id')}::{outcome.get('asset_id')}"
        decision = recommendations.get(key, {}).get("decision", "unknown")
        grouped.setdefault(decision, {})
        grouped[decision][str(outcome.get("outcome", "unknown"))] = (
            grouped[decision].get(str(outcome.get("outcome", "unknown")), 0) + 1
        )
    rows = []
    for decision, counts in sorted(grouped.items()):
        total = sum(counts.values())
        rows.append(
            {
                "decision": decision,
                "count": total,
                "outcomes": counts,
                "percentages_available": total >= minimum_n,
            }
        )
    return {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "minimum_n_for_percentages": minimum_n,
        "decision_rows": rows,
        "trace_count": len(
            [
                row
                for row in _read_jsonl(central_usage_path(hub_root, DECISION_TRACE_LEDGER))
                if row.get("trace_id")
            ]
        ),
        "outcome_count": len(outcomes),
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
    workspace_container_paths: set[Path] = set()
    for source in local_sources or []:
        if not bool(getattr(source, "enabled", True)):
            continue
        base = Path(getattr(source, "path", ""))
        if not base.exists():
            source_warnings.append(f"local source missing: {getattr(source, 'id', base)}")
            continue
        resolved_base = base.resolve()
        if _normalize_name(resolved_base.name) in WORKSPACE_ROOT_NAMES:
            workspace_container_paths.add(resolved_base)
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
    contract_summaries_by_path: dict[str, dict[str, Any]] = {}
    stable_id_counts: dict[str, int] = {}
    for record in records_by_path.values():
        basename = _normalize_name(record["repo_name"])
        basename_counts[basename] = basename_counts.get(basename, 0) + 1
        repo = Path(record["local_path"])
        contract = _read_repo_contract_summary(repo)
        contract_summaries_by_path[record["local_path"]] = contract
        stable_repo_id = str(contract.get("repo_id", "") or "")
        if stable_repo_id:
            stable_id_counts[stable_repo_id] = stable_id_counts.get(stable_repo_id, 0) + 1

    records: list[dict[str, Any]] = []
    local_records_by_basename: dict[str, list[dict[str, Any]]] = {}
    local_records_by_github_full_name: dict[str, list[dict[str, Any]]] = {}
    local_repo_paths = [Path(record["local_path"]).resolve() for record in records_by_path.values()]
    nesting_parent_paths = [
        path for path in local_repo_paths if path not in workspace_container_paths
    ]
    for record in records_by_path.values():
        repo = Path(record["local_path"])
        policy = _repo_policy(
            repo,
            mail_policies=mail_policies,
            enrollment_policies=enrollment_policies,
            prefer_enrollment=True,
        )
        mail_policy_present = _policy_matches_any(repo, mail_policies)
        enrollment_policy_present = _policy_matches_any(repo, enrollment_policies)
        duplicate_basename = basename_counts.get(_normalize_name(record["repo_name"]), 0) > 1
        contract = contract_summaries_by_path.get(record["local_path"], {})
        policy_repo_id = str(getattr(policy, "id", "") or "") if policy else ""
        contract_repo_id = str(contract.get("repo_id", "") or "")
        stable_repo_id = policy_repo_id or contract_repo_id
        duplicate_lineage = bool(
            contract_repo_id and stable_id_counts.get(contract_repo_id, 0) > 1
        )
        git_state = _inventory_git_state(repo)
        repo_resolved = repo.resolve()
        nested_repo = any(
            parent != repo_resolved and repo_resolved.is_relative_to(parent)
            for parent in nesting_parent_paths
        )
        classification, reasons, next_action = _classify_inventory_repo(
            repo,
            policy=policy,
            enrollment_policy_present=enrollment_policy_present,
            duplicate_basename=duplicate_basename,
            duplicate_lineage=duplicate_lineage,
            nested_repo=nested_repo,
            git_state=git_state,
        )
        public_facing = (
            bool(getattr(policy, "public_facing", False))
            if policy
            else bool(contract.get("public_facing", False))
        )
        local_paths_allowed = _policy_local_paths_allowed(policy)
        visibility = (
            str(getattr(policy, "visibility", "unknown"))
            if policy
            else str(contract.get("visibility", "") or "unknown")
        )
        alias = str(getattr(policy, "alias", "") if policy else contract.get("repo_alias", "") or "")
        path_ref = _inventory_repo_ref(
            repo,
            repo_id=stable_repo_id,
            policy=policy,
            public_facing=public_facing,
            local_paths_allowed=local_paths_allowed,
        )
        path_public_safe = (
            f"dad://repo/{stable_repo_id or _slug(repo.name)}"
            if public_facing
            else _normalized_path(repo)
        )
        record.update(
            {
                "repo_id": stable_repo_id,
                "repo_id_source": (
                    "policy"
                    if policy_repo_id
                    else "contract"
                    if contract_repo_id
                    else ""
                ),
                "alias": alias,
                "visibility": visibility,
                "public_facing": public_facing,
                "local_paths_allowed": local_paths_allowed,
                "path_ref": path_ref,
                "path_public_safe": path_public_safe,
                "classification": classification,
                "classification_reasons": reasons,
                "next_action": next_action,
                "write_boundary": (
                    "central_only"
                    if classification
                    in {"protected-central-only", "active-no-write", "archive-ignore", "duplicate-ignore"}
                    else "reviewed_policy_required"
                ),
                "mail_policy_present": mail_policy_present,
                "enrollment_policy_present": enrollment_policy_present,
                "contract_present": bool(contract.get("present", False)),
                "contract_error": str(contract.get("error", "")),
                "duplicate_basename": duplicate_basename,
                "duplicate_lineage": duplicate_lineage,
                "nested_repo": nested_repo,
                "same_basename_count": basename_counts.get(_normalize_name(record["repo_name"]), 0),
                "addressing_status": (
                    "ambiguous_bare_name"
                    if duplicate_basename
                    else "nested_repo"
                    if nested_repo
                    else "bare_name_unambiguous"
                ),
                "git_state": _inventory_report_git_state(
                    git_state,
                    public_facing=public_facing,
                    local_paths_allowed=local_paths_allowed,
                ),
                "authority_boundary": CENTRAL_ONLY_BOUNDARY,
            }
        )
        record.pop("local_path")
        records.append(record)
        local_records_by_basename.setdefault(_normalize_name(record["repo_name"]), []).append(record)
        remote_full_name = _github_full_name_from_remote(str(git_state.get("remote_origin", "")))
        if remote_full_name:
            local_records_by_github_full_name.setdefault(remote_full_name, []).append(record)

    github_summary: list[dict[str, Any]] = []
    dynamic_input_hashes: dict[str, str] = {}
    for source in github_sources or []:
        repo_items = _github_repo_items(source)
        repositories_file = _field(source, "repositories_file", None)
        repositories_file_ref = ""
        repositories_file_hash = ""
        if repositories_file:
            repositories_file_path = Path(repositories_file)
            repositories_file_ref = _inventory_file_ref(repositories_file_path, hub_root)
            if repositories_file_path.exists() and repositories_file_path.is_file():
                repositories_file_hash = f"sha256:{sha256_file(repositories_file_path)}"
                dynamic_input_hashes[repositories_file_ref] = repositories_file_hash
        github_summary.append(
            {
                "source_id": str(_field(source, "id", "")),
                "owner": str(_field(source, "owner", "")),
                "enabled": bool(_field(source, "enabled", True)),
                "include_private": bool(_field(source, "include_private", True)),
                "inventory_status": (
                    "imported_repo_list" if repo_items else "configured_source_only"
                ),
                "repo_count": len(repo_items),
                "metadata_source": (
                    "repositories_file"
                    if repositories_file_ref
                    else "inline_rows"
                    if repo_items
                    else "configured_source_only"
                ),
                "repositories_file_ref": repositories_file_ref,
                "repositories_file_sha256": repositories_file_hash,
                "next_action": (
                    "Review imported GitHub repository rows against local inventory before delivery."
                    if repo_items
                    else "Import reviewed GitHub repository list or connector output before delivery. "
                    "Discovery does not authorize local writes."
                ),
            }
        )
        for item in repo_items:
            github_record = _github_inventory_record(source, item)
            github_full_name = str(github_record.get("github_full_name", "")).lower()
            basename = _normalize_name(github_record["repo_name"])
            local_matches = local_records_by_basename.get(basename, [])
            remote_matches = local_records_by_github_full_name.get(github_full_name, [])
            if len(remote_matches) == 1:
                matched = remote_matches[0]
                signals = matched.setdefault("source_signals", [])
                signal = f"github_source:{github_record['github_source_id']}"
                if signal not in signals:
                    signals.append(signal)
                matched["github_ref"] = github_record["github_ref"]
                matched["github_full_name"] = github_record["github_full_name"]
                matched["github_source_id"] = github_record["github_source_id"]
                matched["github_visibility"] = github_record["visibility"]
                matched["github_archived"] = bool(github_record.get("github_archived", False))
                matched["github_inventory_status"] = "matched_by_remote_origin"
                _tighten_remote_matched_github_classification(matched, github_record)
                if github_record["visibility"] == "public":
                    _force_public_safe_inventory_record(
                        matched,
                        public_ref=str(github_record["github_ref"]),
                        public_name=str(github_record.get("repo_name", "")),
                    )
                continue
            if len(local_matches) >= 1:
                github_record["classification"] = "needs-human-classification"
                github_record["classification_reasons"].append(
                    "GitHub repo name has local basename matches but no verified remote-origin match."
                )
                github_record["addressing_status"] = (
                    "ambiguous_bare_name"
                    if len(local_matches) > 1
                    else "unverified_basename_match"
                )
            records.append(github_record)

    enabled_github_sources = [source for source in github_summary if source["enabled"]]
    if not github_summary:
        github_coverage_status = "not_configured"
    elif not enabled_github_sources:
        github_coverage_status = "configured_disabled"
    elif all(int(source.get("repo_count", 0)) > 0 for source in enabled_github_sources):
        github_coverage_status = "imported_repo_list"
    else:
        github_coverage_status = "incomplete_import_required"
        source_warnings.append(
            "enabled GitHub source lacks imported repo rows; all-GitHub coverage is incomplete"
        )

    records.sort(key=lambda item: (item["classification"], item["repo_name"].lower()))
    counts: dict[str, int] = {}
    for record in records:
        counts[record["classification"]] = counts.get(record["classification"], 0) + 1

    methodology_metadata = _methodology_metadata(
        hub_root,
        REPO_INVENTORY_METHODOLOGY,
        repo_inventory_policy=True,
    )
    input_hashes = _existing_input_hashes(
        hub_root,
        REPO_INVENTORY_INPUT_REFS,
        repo_inventory_policy=True,
    )
    input_hashes.update(dynamic_input_hashes)
    report_identity_basis = {
        "schema_version": "0.1.0",
        "hash_policy": REPO_INVENTORY_HASH_POLICY,
        "methodology": methodology_metadata,
        "input_hashes": input_hashes,
        "repo_count": len(records),
        "classification_counts": counts,
        "records": records,
        "github_sources": github_summary,
        "github_coverage_status": github_coverage_status,
        "github_coverage_complete": github_coverage_status == "imported_repo_list",
        "source_warnings": source_warnings,
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    content_fingerprint = "sha256:" + sha256_bytes(
        json_dumps(report_identity_basis).encode("utf-8")
    )

    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "report_id": stable_id("dad-repo-inventory", content_fingerprint),
        "content_fingerprint": content_fingerprint,
        "hash_policy": REPO_INVENTORY_HASH_POLICY,
        **methodology_metadata,
        "input_hashes": input_hashes,
        "repo_count": len(records),
        "classification_counts": counts,
        "records": records,
        "github_sources": github_summary,
        "github_coverage_status": github_coverage_status,
        "github_coverage_complete": github_coverage_status == "imported_repo_list",
        "source_warnings": source_warnings,
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    out_dir = repo_inventory_dir(hub_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "reconciled_inventory.json"
    md_path = out_dir / "reconciled_inventory.md"
    _write_json(json_path, payload)
    atomic_write_text(md_path, _inventory_markdown(payload))
    return {"inventory": payload, "json_path": str(json_path), "markdown_path": str(md_path)}


def write_repo_inventory_rust_probe_parity(
    hub_root: Path,
    *,
    roots: Sequence[Path],
    root_aliases: Sequence[str],
    rust_summary: dict[str, Any],
    max_depth: int = 5,
    follow_symlinks: bool = False,
) -> dict[str, Any]:
    if len(roots) != len(root_aliases):
        raise ValueError("roots and root_aliases must have the same length")
    alias_counts = Counter(root_aliases)
    duplicate_aliases = sorted(alias for alias, count in alias_counts.items() if count > 1)
    if duplicate_aliases:
        raise ValueError(
            "root_alias values must be unique: " + ", ".join(duplicate_aliases)
        )
    rust_summary_validation_errors = validate_repo_inventory_probe_summary(
        rust_summary,
        root_aliases=root_aliases,
    )
    python_records: list[dict[str, Any]] = []
    python_skipped_dirs: list[dict[str, Any]] = []
    for root, alias in zip(roots, root_aliases):
        base = Path(root).resolve()
        if not base.exists() or not base.is_dir():
            continue
        discovered_roots, discovered_skips = _discover_git_roots_with_skips(
            base,
            max_depth=max_depth,
            follow_symlinks=follow_symlinks,
            root_alias=alias,
        )
        python_skipped_dirs.extend(discovered_skips)
        for repo in discovered_roots:
            python_records.append(
                {
                    "root_alias": alias,
                    "logical_path": _repo_probe_logical_path(base, alias, repo),
                    "contract_present": (
                        repo / ".digital-asset" / "dad-integration.json"
                    ).is_file(),
                    "source": "python_inventory_discovery",
                }
            )
    python_records.sort(key=lambda item: str(item["logical_path"]))
    python_skipped_dirs.sort(
        key=lambda item: (str(item["logical_path"]), str(item["reason"]))
    )
    rust_records: list[dict[str, Any]] = []
    rust_unknown_contract_fields: list[dict[str, Any]] = []
    for item in rust_summary.get("repos", []):
        logical_path = str(item.get("logical_path", ""))
        if not logical_path:
            continue
        contract_value = item.get("contract_present")
        if "contract_present" not in item:
            contract_present_field_status = "missing"
        elif not isinstance(contract_value, bool):
            contract_present_field_status = "non_boolean"
        else:
            contract_present_field_status = "ok"
        structural_value = item.get("contract_structural_pass")
        if "contract_structural_pass" not in item:
            contract_structural_field_status = "missing"
        elif not isinstance(structural_value, bool):
            contract_structural_field_status = "non_boolean"
        else:
            contract_structural_field_status = "ok"
        issue_codes = item.get("contract_issue_codes")
        safe_issue_codes = (
            sorted(str(code) for code in issue_codes)
            if isinstance(issue_codes, list)
            and all(isinstance(code, str) for code in issue_codes)
            else []
        )
        record = {
            "root_alias": str(item.get("root_alias", "")),
            "logical_path": logical_path,
            "contract_present": (
                bool(contract_value) if contract_present_field_status == "ok" else None
            ),
            "contract_present_field_status": contract_present_field_status,
            "contract_parse_status": str(item.get("contract_parse_status", "unknown")),
            "contract_structural_pass": (
                bool(structural_value)
                if contract_structural_field_status == "ok"
                else None
            ),
            "contract_structural_field_status": contract_structural_field_status,
            "contract_issue_codes": safe_issue_codes,
            "source": "rust_repo_inventory_probe",
        }
        rust_records.append(record)
        if contract_present_field_status != "ok":
            rust_unknown_contract_fields.append(
                {
                    "logical_path": logical_path,
                    "root_alias": record["root_alias"],
                    "field_status": contract_present_field_status,
                }
            )
    rust_records.sort(key=lambda item: str(item["logical_path"]))
    rust_skipped_dirs = [
        {
            "root_alias": str(item.get("root_alias", "")),
            "logical_path": str(item.get("logical_path", "")),
            "reason": str(item.get("reason", "")),
            "source": "rust_repo_inventory_probe",
        }
        for item in rust_summary.get("skipped_dirs", [])
        if isinstance(item, dict) and str(item.get("logical_path", ""))
    ]
    rust_skipped_dirs.sort(
        key=lambda item: (str(item["logical_path"]), str(item["reason"]))
    )
    python_paths = {str(item["logical_path"]) for item in python_records}
    rust_paths = {str(item["logical_path"]) for item in rust_records}
    only_python = sorted(python_paths - rust_paths)
    only_rust = sorted(rust_paths - python_paths)
    python_skipped_keys = {
        (str(item["logical_path"]), str(item["reason"])) for item in python_skipped_dirs
    }
    rust_skipped_keys = {
        (str(item["logical_path"]), str(item["reason"])) for item in rust_skipped_dirs
    }
    only_python_skipped_dirs = [
        {
            "logical_path": logical_path,
            "reason": reason,
            "source": "python_inventory_discovery",
        }
        for logical_path, reason in sorted(python_skipped_keys - rust_skipped_keys)
    ]
    only_rust_skipped_dirs = [
        {
            "logical_path": logical_path,
            "reason": reason,
            "source": "rust_repo_inventory_probe",
        }
        for logical_path, reason in sorted(rust_skipped_keys - python_skipped_keys)
    ]
    duplicate_logical_paths: list[dict[str, Any]] = []
    for source, records in (
        ("python_inventory_discovery", python_records),
        ("rust_repo_inventory_probe", rust_records),
    ):
        path_counts = Counter(str(item["logical_path"]) for item in records)
        duplicate_logical_paths.extend(
            {
                "source": source,
                "logical_path": logical_path,
                "count": count,
            }
            for logical_path, count in sorted(path_counts.items())
            if count > 1
        )
    python_by_path = {str(item["logical_path"]): item for item in python_records}
    rust_by_path = {str(item["logical_path"]): item for item in rust_records}
    contract_present_mismatches = []
    for logical_path in sorted(python_paths & rust_paths):
        if rust_by_path[logical_path]["contract_present_field_status"] != "ok":
            continue
        python_contract_present = bool(python_by_path[logical_path]["contract_present"])
        rust_contract_present = bool(rust_by_path[logical_path]["contract_present"])
        if python_contract_present != rust_contract_present:
            contract_present_mismatches.append(
                {
                    "logical_path": logical_path,
                    "python_contract_present": python_contract_present,
                    "rust_contract_present": rust_contract_present,
                }
            )
    parity_status = (
        "matched"
        if not only_python
        and not only_rust
        and not duplicate_logical_paths
        and not contract_present_mismatches
        and not rust_unknown_contract_fields
        and not rust_summary_validation_errors
        and not only_python_skipped_dirs
        and not only_rust_skipped_dirs
        else "mismatch_candidate"
    )
    rust_contract_parse_status_counts = dict(
        sorted(Counter(str(item["contract_parse_status"]) for item in rust_records).items())
    )
    rust_contract_structural_pass_count = sum(
        1 for item in rust_records if item["contract_structural_pass"] is True
    )
    rust_contract_structural_fail_count = sum(
        1 for item in rust_records if item["contract_structural_pass"] is False
    )
    rust_unknown_contract_structural_field_count = sum(
        1
        for item in rust_records
        if item["contract_structural_field_status"] != "ok"
    )
    rust_contract_issue_code_count = sum(
        len(item["contract_issue_codes"]) for item in rust_records
    )
    payload = {
        "schema_version": "dad_repo_inventory_rust_probe_parity.v0_1",
        "generated_at": utc_now(),
        "hash_policy": REPO_INVENTORY_HASH_POLICY,
        **_methodology_metadata(
            hub_root,
            REPO_INVENTORY_METHODOLOGY,
            repo_inventory_policy=True,
        ),
        "input_hashes": _existing_input_hashes(
            hub_root,
            REPO_INVENTORY_RUST_PARITY_INPUT_REFS,
            repo_inventory_policy=True,
        ),
        "max_depth": max_depth,
        "follow_symlinks": follow_symlinks,
        "rust_summary_valid": not rust_summary_validation_errors,
        "rust_summary_validation_errors": rust_summary_validation_errors,
        "python_repo_count": len(python_records),
        "rust_repo_count": len(rust_records),
        "matched_repo_count": len(python_paths & rust_paths),
        "python_skipped_dir_count": len(python_skipped_dirs),
        "rust_skipped_dir_count": len(rust_skipped_dirs),
        "skip_policy_mismatch_count": len(only_python_skipped_dirs)
        + len(only_rust_skipped_dirs),
        "duplicate_logical_path_count": len(duplicate_logical_paths),
        "contract_present_mismatch_count": len(contract_present_mismatches),
        "rust_unknown_contract_field_count": len(rust_unknown_contract_fields),
        "rust_contract_structural_pass_count": rust_contract_structural_pass_count,
        "rust_contract_structural_fail_count": rust_contract_structural_fail_count,
        "rust_unknown_contract_structural_field_count": (
            rust_unknown_contract_structural_field_count
        ),
        "rust_contract_issue_code_count": rust_contract_issue_code_count,
        "rust_contract_parse_status_counts": rust_contract_parse_status_counts,
        "contract_structural_scope": (
            "Rust contract structural fields are deployment-doctor inputs only; "
            "inventory parity status is not enrollment readiness."
        ),
        "parity_status": parity_status,
        "only_python_logical_paths": only_python,
        "only_rust_logical_paths": only_rust,
        "only_python_skipped_dirs": only_python_skipped_dirs,
        "only_rust_skipped_dirs": only_rust_skipped_dirs,
        "duplicate_logical_paths": duplicate_logical_paths,
        "contract_present_mismatches": contract_present_mismatches,
        "rust_unknown_contract_fields": rust_unknown_contract_fields,
        "python_records": python_records,
        "rust_records": rust_records,
        "python_skipped_dirs": python_skipped_dirs,
        "rust_skipped_dirs": rust_skipped_dirs,
        "rust_summary_schema_version": str(rust_summary.get("schema_version", "")),
        "authority_boundary": (
            "This report compares Python and Rust local Git-root discovery as "
            "candidate machine evidence only. It does not classify repos, satisfy "
            "Phase 8/9 human gates, authorize enrollment, or write to target repos."
        ),
    }
    out_dir = repo_inventory_dir(hub_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rust_probe_shadow_parity.json"
    md_path = out_dir / "rust_probe_shadow_parity.md"
    _write_json(json_path, payload)
    atomic_write_text(md_path, _repo_inventory_probe_parity_markdown(payload))
    return {"parity": payload, "json_path": str(json_path), "markdown_path": str(md_path)}


def _repo_probe_logical_path(base: Path, alias: str, repo: Path) -> str:
    base_path = Path(base).absolute()
    repo_path = Path(repo).absolute()
    try:
        rel = repo_path.relative_to(base_path).as_posix()
    except ValueError:
        rel = repo.name
    if not rel or rel == ".":
        return alias
    segments = [
        _repo_probe_public_safe_segment(segment)
        for segment in rel.replace("\\", "/").split("/")
        if segment and segment not in {".", ".."}
    ]
    if not segments:
        return alias
    return f"{alias.rstrip('/')}/{'/'.join(segments)}"


def _repo_probe_public_safe_segment(value: str) -> str:
    text = "".join(
        character.lower()
        if character.isascii() and (character.isalnum() or character in {"-", "_", "."})
        else "-"
        for character in value
    )
    cleaned = re.sub("-+", "-", text).strip("-")
    if cleaned in {"", ".", ".."}:
        return "unnamed"
    return cleaned


def _repo_inventory_probe_parity_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Rust Repo Inventory Probe Shadow Parity",
        "",
        f"Generated: {payload['generated_at']}",
        f"Status: `{payload['parity_status']}`",
        "",
        "This is candidate machine evidence only. Python remains the authority for Phase 9 classification.",
        "",
        "## Counts",
        "",
        f"- Python repo roots: `{payload['python_repo_count']}`",
        f"- Rust repo roots: `{payload['rust_repo_count']}`",
        f"- Matched repo roots: `{payload['matched_repo_count']}`",
        f"- Python skipped dirs: `{payload['python_skipped_dir_count']}`",
        f"- Rust skipped dirs: `{payload['rust_skipped_dir_count']}`",
        f"- Skip-policy mismatches: `{payload['skip_policy_mismatch_count']}`",
        f"- Duplicate logical paths: `{payload['duplicate_logical_path_count']}`",
        f"- Contract-present mismatches: `{payload['contract_present_mismatch_count']}`",
        f"- Rust unknown contract-present fields: `{payload['rust_unknown_contract_field_count']}`",
        f"- Rust contract structural pass: `{payload['rust_contract_structural_pass_count']}`",
        f"- Rust contract structural fail: `{payload['rust_contract_structural_fail_count']}`",
        "- Rust unknown contract-structural fields: "
        f"`{payload['rust_unknown_contract_structural_field_count']}`",
        f"- Rust contract issue codes: `{payload['rust_contract_issue_code_count']}`",
        "",
        payload["contract_structural_scope"],
        "",
    ]
    if (
        payload["only_python_logical_paths"]
        or payload["only_rust_logical_paths"]
        or payload["only_python_skipped_dirs"]
        or payload["only_rust_skipped_dirs"]
        or payload["duplicate_logical_paths"]
        or payload["contract_present_mismatches"]
        or payload["rust_unknown_contract_fields"]
    ):
        lines.extend(["## Mismatches", ""])
        for path in payload["only_python_logical_paths"]:
            lines.append(f"- Python only: `{path}`")
        for path in payload["only_rust_logical_paths"]:
            lines.append(f"- Rust only: `{path}`")
        for item in payload["only_python_skipped_dirs"]:
            lines.append(
                "- Python-only skipped dir: "
                f"`{item['logical_path']}` "
                f"({item['reason']})"
            )
        for item in payload["only_rust_skipped_dirs"]:
            lines.append(
                "- Rust-only skipped dir: "
                f"`{item['logical_path']}` "
                f"({item['reason']})"
            )
        for duplicate in payload["duplicate_logical_paths"]:
            lines.append(
                "- Duplicate logical path: "
                f"`{duplicate['logical_path']}` "
                f"from `{duplicate['source']}` "
                f"(count `{duplicate['count']}`)"
            )
        for mismatch in payload["contract_present_mismatches"]:
            lines.append(
                "- Contract-present mismatch: "
                f"`{mismatch['logical_path']}` "
                f"(Python `{mismatch['python_contract_present']}`, "
                f"Rust `{mismatch['rust_contract_present']}`)"
            )
        for unknown in payload["rust_unknown_contract_fields"]:
            lines.append(
                "- Rust unknown contract-present field: "
                f"`{unknown['logical_path']}` "
                f"({unknown['field_status']})"
            )
    else:
        lines.append("- No Python/Rust logical-path or contract-present mismatches.")
    lines.extend(["", payload["authority_boundary"], ""])
    return "\n".join(lines)


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
                "transport audit and transport-upgrade queue review",
                "enrollment contract update-plan generation",
            ],
            "preflight_behavior": (
                "Surface stale weekly checks as warnings; do not run heavy scans on every preflight."
            ),
            "write_boundary": "central reports plus candidate mail; enrollment apply still needs approval",
            "transport_upgrade": {
                "audit_command": "asset-dir transport audit",
                "queue_path": "processed/mail/staged/transport-upgrade-queue.jsonl",
                "target_repo_write_boundary": (
                    "No downstream repo writes occur during weekly checks. Upgrade "
                    "delivery still requires reviewed enrollment update waves and "
                    "approved apply commands."
                ),
            },
        },
        "blocked_operations": [
            "no normal recurring source edits",
            "no hook installation outside approved enrollment apply/update-apply",
            "no private/internal/restricted/unknown origin delivery to public-facing repos without release",
            "no broad discovered-repo delivery without reviewed policy",
        ],
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    out_dir = cadence_report_dir(hub_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "dad_cadence_plan.json"
    md_path = out_dir / "dad_cadence_plan.md"
    _write_json(json_path, payload)
    atomic_write_text(md_path, _cadence_markdown(payload))
    return {"cadence": payload, "json_path": str(json_path), "markdown_path": str(md_path)}


def repo_local_asset_surface_standard() -> dict[str, Any]:
    """Return the canonical repo-local DAD asset-memory surface."""
    layers = [
        {
            "layer": 1,
            "name": "identity",
            "purpose": "Stable asset IDs, repo IDs, source refs, and return addresses.",
        },
        {
            "layer": 2,
            "name": "object",
            "purpose": "The asset card itself: type, title, local path, summary, tags.",
        },
        {
            "layer": 3,
            "name": "claim",
            "purpose": "Candidate claims about usefulness, leverage, and applicability limits.",
        },
        {
            "layer": 4,
            "name": "relationship",
            "purpose": "Pattern IDs, parent/derived links, upgrade channels, and related assets.",
        },
        {
            "layer": 5,
            "name": "validation",
            "purpose": "Validation commands, evidence pointers, review status, and false-confidence notes.",
        },
        {
            "layer": 6,
            "name": "retrieval",
            "purpose": "Context tags, use-when routes, and how future agents should find it.",
        },
        {
            "layer": 7,
            "name": "fractal_address",
            "purpose": "Repo-local placement discipline compatible with source-owned address systems.",
        },
        {
            "layer": 8,
            "name": "artifact_evidence",
            "purpose": "Source paths, hashes, provenance, and privacy/sensitivity boundaries.",
        },
        {
            "layer": 9,
            "name": "learning_adaptation",
            "adoption_status": "dad_adopted",
            "purpose": (
                "Recursive improvement loop: postflight outcomes, hard-issue fixes, "
                "variant/delta learning, calibration, upgrade notices, and asset "
                "promotion or retirement signals."
            ),
            "dad_rule": (
                "DAD treats layer 9 as a real layer for learning and adaptation, "
                "not as an optional afterthought. Source repos may still label "
                "orchestration/workflow as a ninth-layer variant when their local "
                "address model uses that meaning."
            ),
            "observed_variants": [
                "learning_adaptation",
                "orchestration_workflow",
            ],
        },
    ]
    return {
        "schema_version": "0.1.0",
        "standard_id": "dad:standard:repo-local-digital-asset-directory",
        "standard_version": LOCAL_ASSET_STANDARD_VERSION,
        "canonical_root": ".digital-asset/",
        "required_paths": [
            str(LOCAL_ASSET_README.as_posix()),
            str(LOCAL_ASSET_INDEX.as_posix()),
            ".digital-asset/mail/outbox.jsonl",
            ".digital-asset/mail/inbox.jsonl",
            ".digital-asset/dad-usage.jsonl",
        ],
        "recommended_paths": [
            str(LOCAL_ASSET_ADOPTION.as_posix()),
            str(LOCAL_LEARNING_LEDGER.as_posix()),
            ".digital-asset/context-map.json",
            ".digital-asset/governance-map.yaml",
            ".digital-asset/data-map.yaml",
            ".digital-asset/exceptions/outbox.jsonl",
        ],
        "legacy_or_compatibility_inputs": [
            str(LEGACY_DAD_INGEST_MANIFEST.as_posix()),
            str(LEGACY_LEARNING_LEDGER.as_posix()),
        ],
        "record_schema": "schemas/repo-local-digital-asset-record.schema.json",
        "address_model_ref": "registry/dad-address-model-registry.json",
        "fractal_layers": layers,
        "adopted_layer_count": 9,
        "dad_layer_9": {
            "name": "learning_adaptation",
            "required_for_dad_assets": True,
            "records": [
                "what was learned",
                "what changed after validation",
                "which prior asset or fix this derived from",
                "what context delta made the variant useful",
                "when to upgrade, retire, or re-check the asset",
            ],
        },
        "compact_fill_policy": {
            "default": "Use IDs, paths, hashes, refs, and short labels instead of copied prose.",
            "workflow_depth": (
                "Represent workflows as workflow cards with step IDs and refs; "
                "do not inline full workflow text in asset cards."
            ),
            "evolution": (
                "The address model is versioned and expected to evolve; breaking "
                "changes need migration notes and tests."
            ),
        },
        "source_inspiration": [
            {
                "source_repo": "LawFirm-os-semantic-substrate",
                "source_ref": "docs/architecture/8_LAYER_DNA_ADDRESS_MODEL.md",
                "role": "pointer-only inspiration for address discipline; not DAD canon",
            },
            {
                "source_repo": "LawFirm-os-semantic-substrate",
                "source_ref": "governance/TALENT_INTELLIGENCE_LAYER_PLACEMENT.md",
                "role": "pointer-only example of layers 1-8 plus optional orchestration/workflow layer 9",
            },
            {
                "source_repo": "LawFirm-os-semantic-substrate",
                "source_ref": "docs/learning-loop-layer.md",
                "role": "pointer-only example of learning/adaptation as optional layer 9",
            },
            {
                "source_repo": "LawFirm-os-semantic-substrate",
                "source_ref": "schemas/address_struct.schema.json",
                "role": "pointer-only structured address pattern",
            },
            {
                "source_repo": "LawFirm-os-semantic-substrate",
                "source_ref": "schemas/skill-agent-metadata.schema.json",
                "role": "pointer-only schema using the phrase nine-layer LawFirm OS address without defining the segments there",
            },
        ],
        "collection_policy": {
            "default": "metadata_pointer_only",
            "copy_file_contents": False,
            "copy_private_rows": False,
            "copy_secrets_or_credentials": False,
            "cross_repo_writes": "blocked unless enrollment/update approval explicitly allows them",
        },
        "authority_boundary": REPO_ASSET_SURFACE_BOUNDARY,
    }


def _truncate_metadata_value(value: Any, *, max_string: int = 500) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_string else value[: max_string - 15] + "...[truncated]"
    if isinstance(value, list):
        safe: list[Any] = []
        for item in value[:50]:
            safe.append(_truncate_metadata_value(item, max_string=200))
        return safe
    if isinstance(value, dict):
        return {
            str(key): _truncate_metadata_value(item, max_string=200)
            for key, item in list(value.items())[:30]
            if isinstance(key, str)
        }
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:max_string]


def _safe_repo_asset_record(record: dict[str, Any], *, source_surface: str) -> dict[str, Any]:
    safe = {
        key: _truncate_metadata_value(record.get(key))
        for key in sorted(LOCAL_ASSET_ALLOWED_FIELDS)
        if key in record and record.get(key) not in (None, "")
    }
    source_paths = safe.get("source_paths")
    path = safe.get("path") or safe.get("local_path")
    if not source_paths and path:
        safe["source_paths"] = [str(path)]
    safe.setdefault("asset_id", stable_id("repo-local-asset", source_surface, json.dumps(safe, sort_keys=True)))
    safe.setdefault("review_status", "candidate")
    safe["source_surface"] = source_surface
    safe["payload_policy"] = "metadata_pointer_only"
    dropped = sorted(set(record) - LOCAL_ASSET_ALLOWED_FIELDS)
    if dropped:
        safe["dropped_fields"] = dropped[:25]
    return safe


def _load_repo_asset_index(repo: Path) -> dict[str, Any]:
    path = repo / LOCAL_ASSET_INDEX
    records, malformed = _read_jsonl_tolerant(path)
    return {
        "path": str(LOCAL_ASSET_INDEX.as_posix()),
        "exists": path.exists(),
        "record_count": len(records),
        "malformed_count": len(malformed),
        "malformed_rows": malformed[:10],
        "records": [
            _safe_repo_asset_record(record, source_surface=str(LOCAL_ASSET_INDEX.as_posix()))
            for record in records
        ],
    }


def _load_legacy_dad_ingest(repo: Path) -> dict[str, Any]:
    path = repo / LEGACY_DAD_INGEST_MANIFEST
    if not path.exists():
        return {
            "path": str(LEGACY_DAD_INGEST_MANIFEST.as_posix()),
            "exists": False,
            "record_count": 0,
            "records": [],
        }
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(LEGACY_DAD_INGEST_MANIFEST.as_posix()),
            "exists": True,
            "record_count": 0,
            "records": [],
            "error": str(exc),
        }
    assets = payload.get("assets", [])
    if not isinstance(assets, list):
        assets = []
    records = [
        _safe_repo_asset_record(record, source_surface=str(LEGACY_DAD_INGEST_MANIFEST.as_posix()))
        for record in assets
        if isinstance(record, dict)
    ]
    return {
        "path": str(LEGACY_DAD_INGEST_MANIFEST.as_posix()),
        "exists": True,
        "manifest_id": str(payload.get("manifest_id", "")),
        "record_count": len(records),
        "primary_pattern_id": str(payload.get("primary_pattern_id", "")),
        "dad_needs_addressed": list(payload.get("dad_needs_addressed", []) or []),
        "authority_boundary": str(payload.get("authority_boundary", "")),
        "records": records,
    }


def _load_legacy_learning_summary(repo: Path) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for rel in (LOCAL_LEARNING_LEDGER, LEGACY_LEARNING_LEDGER):
        path = repo / rel
        records, malformed = _read_jsonl_tolerant(path)
        summaries.append(
            {
                "path": rel.as_posix(),
                "exists": path.exists(),
                "record_count": len(records),
                "malformed_count": len(malformed),
            }
        )
    return {"learning_surfaces": summaries}


def collect_repo_local_assets(
    hub_root: Path,
    repo: Path,
    *,
    task: str = "",
    limit: int = 25,
    include_legacy: bool = True,
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    if not repo.exists() or not repo.is_dir():
        raise ValueError(f"Repo path does not exist: {repo}")
    policy = _repo_policy(repo, mail_policies=mail_policies, enrollment_policies=enrollment_policies)
    repo_ref = _repo_ref(repo, policy)
    repo_id = str(getattr(policy, "id", "") if policy else "")
    standard = repo_local_asset_surface_standard()
    present_paths = [
        rel
        for rel in [*standard["required_paths"], *standard["recommended_paths"]]
        if (repo / rel).exists()
    ]
    missing_required = [
        rel for rel in standard["required_paths"] if not (repo / rel).exists()
    ]
    index_payload = _load_repo_asset_index(repo)
    legacy_ingest = _load_legacy_dad_ingest(repo) if include_legacy else {
        "path": str(LEGACY_DAD_INGEST_MANIFEST.as_posix()),
        "exists": False,
        "record_count": 0,
        "records": [],
        "skipped": True,
    }
    learning_summary = _load_legacy_learning_summary(repo)
    declared_records = [
        *index_payload.get("records", []),
        *legacy_ingest.get("records", []),
    ]
    scout = scout_asset_candidates(hub_root, repo, task=task, limit=limit)
    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "report_id": stable_id("repo-local-assets", _normalized_path(repo), task),
        "repo": repo_ref,
        "repo_id": repo_id,
        "repo_name": repo.name,
        "task": task,
        "standard": standard,
        "surface_status": {
            "canonical_root_exists": (repo / ".digital-asset").exists(),
            "present_paths": present_paths,
            "missing_required_paths": missing_required,
            "legacy_inputs_detected": [
                item
                for item in standard["legacy_or_compatibility_inputs"]
                if (repo / item).exists()
            ],
        },
        "declared_assets": {
            "canonical_index": {
                key: value for key, value in index_payload.items() if key != "records"
            },
            "legacy_dad_ingest": {
                key: value for key, value in legacy_ingest.items() if key != "records"
            },
            "record_count": len(declared_records),
            "records": declared_records[:limit],
        },
        "learning_surfaces": learning_summary["learning_surfaces"],
        "asset_scout_report": scout["path"],
        "asset_scout_returned_count": scout["asset_candidates"]["returned_candidate_count"],
        "asset_scout_top_candidates": scout["asset_candidates"]["candidates"][: min(10, limit)],
        "next_actions": [
            "If missing required paths, plan a reviewed enrollment/update wave before writing them.",
            "If legacy dad-ingest exists, migrate future records to .digital-asset/assets/index.jsonl while keeping the legacy packet as evidence.",
            "Route useful records to DAD mail with metadata pointers only; do not copy private rows or source blobs.",
        ],
        "authority_boundary": REPO_ASSET_SURFACE_BOUNDARY,
    }
    out_dir = central_reports_dir(hub_root) / REPO_ASSET_REPORT_DIR.relative_to(
        Path("processed") / "reports"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_repo_report_slug(repo)}.json"
    _write_json(path, payload)
    return {"repo_assets": payload, "path": str(path)}


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
        importance, relevance, signals = _score_asset_path(rel, methodology, task=task)
        if importance < float(methodology.get("min_candidate_score", 30)):
            continue
        candidates.append(
            {
                "candidate_id": stable_id("dad-asset-candidate", _normalized_path(repo), rel),
                "path": rel,
                "score": round(importance, 2),
                "file_importance": round(importance, 2),
                "task_relevance": round(relevance, 2),
                "importance_tier": _importance_tier(importance, methodology),
                "signals": signals,
                "evidence": _asset_candidate_evidence(repo, rel),
                "human_label": "plausible",
                "source_policy": "path-and-metadata-only; file contents were not copied",
                "score_interpretation": (
                    "File importance is deterministic path/metadata routing only; task relevance "
                    "is separate and does not change importance tiers."
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
        "methodology_hash": _methodology_hash(hub_root / ASSET_RECOGNITION_METHODOLOGY),
        "score_scale": "0-100+ candidate routing score; higher means inspect earlier, not promote automatically",
        "score_formula_summary": (
            "File importance sums path/location/extension weights, subtracts downgrade signals, "
            "and clamps at zero. Task relevance is reported separately."
        ),
        "limit": limit,
        "files_scanned": scanned,
        "candidate_count": len(candidates),
        "returned_candidate_count": len(candidates[:limit]),
        "candidates": candidates[:limit],
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }
    path = central_reports_dir(hub_root) / f"asset-recognition-{_repo_report_slug(repo)}.json"
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
        "methodology_hash": _methodology_hash(hub_root / HARNESS_DISCOVERY_METHODOLOGY),
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
    path = harness_report_dir(hub_root) / f"discovery-{_repo_report_slug(repo)}.json"
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
    dependency_basis: str = "",
    mail_policies: Sequence[Any] | None = None,
    enrollment_policies: Sequence[Any] | None = None,
) -> dict[str, Any]:
    if not repo.exists() or not repo.is_dir():
        raise ValueError(f"Usage target repo does not exist: {repo}")
    normalized_status = status.lower().replace("-", "_")
    if normalized_status not in USAGE_STATUSES:
        raise ValueError(
            "status must be using, watching, depends_on, dependency_candidate, rejected, or retired"
        )
    confirmed_dependency_bases = {"explicit_repo_record", "human_reviewed"}
    if normalized_status == "depends_on" and dependency_basis not in confirmed_dependency_bases:
        raise ValueError(
            "depends_on status requires dependency_basis: explicit_repo_record, "
            "or human_reviewed"
        )
    if normalized_status == "depends_on" and dependency_basis == "explicit_repo_record":
        if not source_ref.strip():
            raise ValueError("explicit_repo_record dependency requires a nonempty source_ref")
    if normalized_status == "depends_on" and dependency_basis == "human_reviewed":
        generic_reviewers = {
            "",
            "unknown",
            "agent",
            "ai",
            "automation",
            "ci",
            "codex",
            "claude",
            "copilot",
            "cursor",
            "fable",
            "human",
            "human reviewer",
            "luna",
            "other",
            "reviewer",
            "sol",
            "terra",
            "user",
            "boss_architect",
        }
        if recorded_by.strip().lower() in generic_reviewers:
            raise ValueError("human_reviewed dependency requires a named non-generic reviewer")
        if not (adoption_id.strip() or source_ref.strip()):
            raise ValueError(
                "human_reviewed dependency requires an adoption_id or source_ref review pointer"
            )
    if normalized_status == "dependency_candidate" and dependency_basis != "imported_candidate":
        raise ValueError("dependency_candidate requires dependency_basis: imported_candidate")
    if normalized_status not in {"depends_on", "dependency_candidate"} and dependency_basis:
        raise ValueError(
            "dependency_basis is only valid for depends_on or dependency_candidate status"
        )
    policy = _repo_policy(repo, mail_policies=mail_policies, enrollment_policies=enrollment_policies)
    protected, protection_reason = _repo_write_protection(policy)
    repo_ref = _repo_ref(repo, policy)
    repo_id = str(getattr(policy, "id", "") if policy else "")
    usage_repo_key = repo_id or repo_ref
    timestamp = utc_now()
    usage_id = stable_id(
        "dad-usage",
        usage_repo_key,
        asset_id,
        normalized_status,
        dependency_basis,
        source_ref,
        adoption_id,
    )
    record = {
        "schema_version": "0.1.0",
        "usage_id": usage_id,
        "repo": repo_ref,
        "repo_id": repo_id,
        "asset_id": asset_id,
        "status": normalized_status,
        **({"dependency_basis": dependency_basis} if dependency_basis else {}),
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
    central_appended = _append_unique(
        central_usage_path(hub_root, CENTRAL_USAGE_LEDGER),
        record,
        "usage_id",
    )
    local_appended = False
    local_path = repo / LOCAL_USAGE_LEDGER
    if not protected:
        local_appended = _append_unique(local_path, record, "usage_id")
    return {
        "usage": record,
        "central_appended": central_appended,
        "local_appended": local_appended,
        "central_ledger": str(central_usage_path(hub_root, CENTRAL_USAGE_LEDGER)),
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
    repo_id = str(getattr(policy, "id", "") if policy else "")
    accepted_repo_keys = {repo_ref, _normalized_path(repo)}
    if repo_id:
        accepted_repo_keys.add(repo_id)
    rows = [
        item
        for item in [
            *_read_jsonl(central_usage_path(hub_root, CENTRAL_USAGE_LEDGER)),
            *_read_jsonl(repo / LOCAL_USAGE_LEDGER),
        ]
        if (str(item.get("repo_id") or "") in accepted_repo_keys or str(item.get("repo")) in accepted_repo_keys)
        and str(item.get("status")) in {"using", "watching", "depends_on"}
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
    notice_budget = 5
    return {
        "repo": repo_ref,
        "tracked_usage_count": len(rows),
        "upgrade_count": len(upgrades),
        "notice_budget_period": "weekly",
        "notice_budget": notice_budget,
        "overflow_count": max(0, len(upgrades) - notice_budget),
        "upgrades": upgrades[:notice_budget],
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
    path = harness_report_dir(hub_root) / f"research-{_slug(harness_id)}.json"
    _write_json(path, payload)
    return {"research": payload, "path": str(path)}


def harness_evaluate(hub_root: Path, harness_id: str, repo: Path) -> dict[str, Any]:
    harness = _harness_by_id(hub_root, harness_id)
    recommendation = recommend_harnesses(hub_root, repo, task=" ".join(harness.get("task_types", [])), limit=10)
    match = next(
        (item for item in recommendation["recommendations"] if item["harness_id"] == harness_id),
        None,
    )
    command_results: list[dict[str, Any]] = []
    for command in harness.get("validation_commands", []):
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                str(command),
                cwd=str(repo),
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            exit_code = completed.returncode
            status = "passed" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            exit_code = 124
            status = "timeout"
        duration_ms = int((time.perf_counter() - started) * 1000)
        command_results.append(
            {
                "command": str(command),
                "exit_code": exit_code,
                "status": status,
                "duration_ms": duration_ms,
            }
        )
    evaluation_status = (
        "passed"
        if command_results and all(item["status"] == "passed" for item in command_results)
        else "failed"
        if command_results
        else "not_executed"
    )
    outcome = {
        "schema_version": "0.1.0",
        "outcome_id": stable_id("harness-outcome", harness_id, _normalized_path(repo), utc_now()),
        "harness_id": harness_id,
        "repo": _normalized_path(repo),
        "created_at": utc_now(),
        "evaluation_status": evaluation_status,
        "command_results": command_results,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    append_jsonl(central_usage_path(hub_root, HARNESS_OUTCOME_LEDGER), outcome)
    payload = {
        "schema_version": "0.1.0",
        "generated_at": utc_now(),
        "harness_id": harness_id,
        "repo": _normalized_path(repo),
        "evaluation_status": evaluation_status,
        "match": match,
        "validation_commands": harness.get("validation_commands", []),
        "command_results": command_results,
        "outcome_ledger": str(central_usage_path(hub_root, HARNESS_OUTCOME_LEDGER)),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    path = harness_report_dir(hub_root) / (
        f"evaluate-{_slug(harness_id)}-{_repo_report_slug(repo)}.json"
    )
    _write_json(path, payload)
    return {"evaluation": payload, "path": str(path)}


def harness_package(hub_root: Path, harness_id: str) -> dict[str, Any]:
    harness = _harness_by_id(hub_root, harness_id)
    root = hub_root / harness["path"]
    if not root.exists():
        raise FileNotFoundError(root)
    package_path = harness_report_dir(hub_root) / f"{_slug(harness_id)}.zip"
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
    _write_json(harness_report_dir(hub_root) / f"{_slug(harness_id)}.package.json", manifest)
    return manifest


def _discover_git_roots(base: Path, *, max_depth: int, follow_symlinks: bool) -> list[Path]:
    roots, _skipped_dirs = _discover_git_roots_with_skips(
        base,
        max_depth=max_depth,
        follow_symlinks=follow_symlinks,
    )
    return roots


def _discover_git_roots_with_skips(
    base: Path,
    *,
    max_depth: int,
    follow_symlinks: bool,
    root_alias: str | None = None,
) -> tuple[list[Path], list[dict[str, Any]]]:
    roots: list[Path] = []
    skipped_dirs: list[dict[str, Any]] = []
    base = base.resolve()
    for current_raw, dirs, files in os.walk(base, topdown=True, followlinks=follow_symlinks):
        current = Path(current_raw)
        try:
            depth = len(current.relative_to(base).parts)
        except ValueError:
            depth = 0
        if depth > max_depth:
            dirs[:] = []
            continue
        retained_dirs: list[str] = []
        for item in sorted(dirs, key=str.lower):
            child = current / item
            if not _should_descend_repo_inventory_dir(
                child, follow_symlinks=follow_symlinks
            ):
                continue
            reason = _repo_inventory_skip_reason(item)
            if reason:
                if root_alias:
                    skipped_dirs.append(
                        {
                            "root_alias": root_alias,
                            "logical_path": _repo_probe_logical_path(
                                base, root_alias, child
                            ),
                            "reason": reason,
                            "source": "python_inventory_discovery",
                        }
                    )
                continue
            retained_dirs.append(item)
        dirs[:] = retained_dirs
        if ".git" in dirs or ".git" in files or (current / ".git").exists():
            roots.append(current)
    return (
        sorted(set(roots), key=lambda item: str(item).lower()),
        sorted(
            skipped_dirs,
            key=lambda item: (str(item["logical_path"]), str(item["reason"])),
        ),
    )


def _should_descend_repo_inventory_dir(path: Path, *, follow_symlinks: bool) -> bool:
    if follow_symlinks:
        return True
    try:
        if path.is_symlink():
            return False
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return False
    except OSError:
        return False
    return True


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


def _direct_path_marker_match(repo: Path, markers: set[str]) -> bool:
    """Match path-role markers only on the repo name or immediate parent."""
    normalized = [_normalize_name(part) for part in repo.parts[-2:]]
    return any(marker in normalized for marker in markers)


def _name_marker_match(value: str, markers: set[str], *, contains: bool = False) -> bool:
    normalized = _normalize_name(value)
    return any(marker == normalized or (contains and marker in normalized) for marker in markers)


def _policy_matches_any(repo: Path, policies: Sequence[Any] | None) -> bool:
    return any(_policy_matches(repo, policy) for policy in policies or [])


def _inventory_git_stdout(repo: Path, args: Sequence[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _inventory_git_state(repo: Path) -> dict[str, Any]:
    state: dict[str, Any] = {
        "git_detected": False,
        "branch": "",
        "branch_status": "unknown",
        "head": "",
        "remote_origin": "",
        "dirty_count": 0,
        "is_dirty": False,
    }
    if not repo.exists() or not repo.is_dir():
        return state
    inside = _inventory_git_stdout(repo, ["rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        return state
    status_result = _inventory_git_stdout(repo, ["status", "--porcelain=v1"])
    status = status_result or ""
    dirty_lines = [line for line in status.splitlines() if line.strip()]
    branch = _inventory_git_stdout(repo, ["branch", "--show-current"]) or ""
    head = _inventory_git_stdout(repo, ["rev-parse", "--short", "HEAD"])
    symbolic_head = _inventory_git_stdout(repo, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if head is None and status_result is not None and symbolic_head is not None:
        head = REPO_INVENTORY_UNBORN_HEAD
    state.update(
        {
            "git_detected": True,
            "branch": branch,
            "branch_status": (
                "mainline"
                if branch in {"main", "master"}
                else "non_main"
                if branch
                else "detached_or_unknown"
            ),
            "head": head or "",
            "remote_origin": _inventory_git_stdout(repo, ["remote", "get-url", "origin"]) or "",
            "dirty_count": len(dirty_lines),
            "is_dirty": bool(dirty_lines),
        }
    )
    return state


def _inventory_report_git_state(
    git_state: dict[str, Any],
    *,
    public_facing: bool,
    local_paths_allowed: bool,
) -> dict[str, Any]:
    if public_facing and not local_paths_allowed:
        return {
            "git_detected": bool(git_state.get("git_detected", False)),
            "branch_status": str(git_state.get("branch_status", "unknown")),
            "dirty_count": int(git_state.get("dirty_count", 0) or 0),
            "is_dirty": bool(git_state.get("is_dirty", False)),
            "branch": "redacted-public-facing" if git_state.get("branch") else "",
            "head": "redacted-public-facing" if git_state.get("head") else "",
            "remote_origin": "redacted-public-facing" if git_state.get("remote_origin") else "",
            "public_safe_redaction": True,
        }
    return dict(git_state)


def _github_full_name_from_remote(remote_origin: str) -> str:
    value = remote_origin.strip()
    if not value:
        return ""
    patterns = [
        r"github\.com[:/](?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?$",
        r"^git@github\.com:(?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            owner = match.group("owner")
            name = match.group("name")
            return f"{owner}/{name}".lower()
    return ""


def _tighten_remote_matched_github_classification(
    matched: dict[str, Any],
    github_record: dict[str, Any],
) -> None:
    github_classification = str(github_record.get("classification", ""))
    if github_classification == "protected-central-only":
        _apply_inventory_classification_tightening(
            matched,
            classification="protected-central-only",
            reasons=[
                "Verified GitHub remote-origin match is protected-central-only: "
                + str(reason)
                for reason in github_record.get("classification_reasons", [])
            ],
            next_action=str(github_record.get("next_action", "")),
        )
        return
    if (
        github_classification == "archive-ignore"
        and not bool(matched.get("enrollment_policy_present", False))
        and str(matched.get("classification", "")) != "protected-central-only"
    ):
        _apply_inventory_classification_tightening(
            matched,
            classification="archive-ignore",
            reasons=[
                "Verified GitHub remote-origin match is archive-ignore: "
                + str(reason)
                for reason in github_record.get("classification_reasons", [])
            ],
            next_action=str(github_record.get("next_action", "")),
        )


def _apply_inventory_classification_tightening(
    record: dict[str, Any],
    *,
    classification: str,
    reasons: list[str],
    next_action: str,
) -> None:
    if str(record.get("classification", "")) == classification:
        existing_reasons = record.setdefault("classification_reasons", [])
        for reason in reasons:
            if reason and reason not in existing_reasons:
                existing_reasons.append(reason)
    else:
        record["classification"] = classification
        existing_reasons = list(record.get("classification_reasons", []))
        for reason in reasons:
            if reason and reason not in existing_reasons:
                existing_reasons.append(reason)
        record["classification_reasons"] = existing_reasons
    if next_action:
        record["next_action"] = next_action
    if classification in {
        "protected-central-only",
        "active-no-write",
        "archive-ignore",
        "duplicate-ignore",
    }:
        record["write_boundary"] = "central_only"


def _inventory_hold_reasons(policy: Any | None, git_state: dict[str, Any]) -> list[str]:
    if not policy:
        return []
    reasons: list[str] = []
    if bool(getattr(policy, "active_hold", False)):
        reason = str(getattr(policy, "active_hold_reason", "") or "policy active_hold")
        reasons.append(f"active_hold: {reason}")
    if (
        bool(git_state.get("git_detected", False))
        and bool(git_state.get("is_dirty", False))
        and not bool(getattr(policy, "allow_dirty_worktree", False))
    ):
        reasons.append("dirty_worktree: reviewed policy does not allow dirty enrollment.")
    if (
        bool(git_state.get("git_detected", False))
        and str(git_state.get("branch_status", "")) == "non_main"
        and not bool(getattr(policy, "allow_non_main_branch", False))
    ):
        reasons.append("non_main_branch: reviewed policy does not allow non-main enrollment.")
    return reasons


def _read_repo_contract_summary(repo: Path) -> dict[str, Any]:
    path = repo / ".digital-asset" / "dad-integration.json"
    if not path.exists():
        return {"present": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"present": True, "error": str(exc)}
    return {
        "present": True,
        "repo_id": str(payload.get("repo_id", "") or ""),
        "repo_alias": str(payload.get("repo_alias", "") or ""),
        "repo_ref": str(payload.get("repo_ref", "") or ""),
        "visibility": str(payload.get("visibility", "") or ""),
        "public_facing": bool(payload.get("public_facing", False)),
    }


def _github_repo_items(source: Any) -> list[Any]:
    items = _field(source, "repositories", None)
    if items is None:
        items = _field(source, "repos", None)
    if items is None:
        return []
    if isinstance(items, Sequence) and not isinstance(items, (str, bytes, bytearray)):
        return list(items)
    return []


def _github_inventory_record(source: Any, item: Any) -> dict[str, Any]:
    owner = str(_field(item, "owner", "") or _field(source, "owner", "") or "")
    full_name = str(
        _field(item, "full_name", "")
        or _field(item, "nameWithOwner", "")
        or ""
    )
    name = str(_field(item, "name", "") or "")
    if not name and "/" in full_name:
        name = full_name.rsplit("/", 1)[-1]
    if not full_name:
        full_name = f"{owner}/{name}".strip("/")
    visibility = str(_field(item, "visibility", "") or "").lower()
    private = bool(_field(item, "private", _field(item, "isPrivate", False)))
    if not visibility:
        visibility = "private" if private else "public"
    archived = bool(_field(item, "archived", _field(item, "isArchived", False)))
    public_facing = visibility == "public" and not private
    repo_id = _slug(full_name.replace("/", "-")) or _slug(name)
    if _name_marker_match(f"{full_name} {name}", PROTECTED_REPO_MARKERS, contains=True):
        classification = "protected-central-only"
        reasons = ["GitHub repo name matches protected Logos marker; keep central-only."]
        next_action = "Require explicit Logos local-write approval before any repair or enrollment write."
    elif archived:
        classification = "archive-ignore"
        reasons = ["GitHub source reports archived repo; keep central-only unless policy promotes it."]
        next_action = "Reconcile with local inventory and reviewed policy before delivery or enrollment."
    else:
        classification = "needs-human-classification"
        reasons = ["GitHub source row has no reviewed local enrollment policy match."]
        next_action = "Reconcile with local inventory and reviewed policy before delivery or enrollment."
    return {
        "repo_record_id": stable_id("dad-github-repo-record", full_name),
        "repo_name": name or full_name,
        "repo_id": repo_id,
        "repo_id_source": "github",
        "alias": full_name,
        "visibility": visibility if visibility in {"public", "internal", "private", "restricted", "unknown"} else "unknown",
        "public_facing": public_facing,
        "local_paths_allowed": False,
        "path_ref": f"dad://github/{full_name}",
        "path_public_safe": f"dad://github/{full_name}",
        "classification": classification,
        "classification_reasons": reasons,
        "next_action": next_action,
        "write_boundary": "central_only",
        "source_signals": [f"github_source:{_field(source, 'id', '')}"],
        "mail_policy_present": False,
        "enrollment_policy_present": False,
        "contract_present": False,
        "contract_error": "",
        "duplicate_basename": False,
        "duplicate_lineage": False,
        "same_basename_count": 1,
        "addressing_status": "bare_name_unambiguous",
        "local_presence": False,
        "github_ref": f"dad://github/{full_name}",
        "github_full_name": full_name,
        "github_source_id": str(_field(source, "id", "")),
        "github_visibility": visibility,
        "github_archived": archived,
        "git_state": {
            "git_detected": False,
            "branch_status": "unknown",
            "dirty_count": 0,
            "is_dirty": False,
            "branch": "",
            "head": "",
            "public_safe_redaction": True,
        },
        "authority_boundary": CENTRAL_ONLY_BOUNDARY,
    }


def _classify_inventory_repo(
    repo: Path,
    *,
    policy: Any | None,
    enrollment_policy_present: bool,
    duplicate_basename: bool,
    duplicate_lineage: bool,
    nested_repo: bool,
    git_state: dict[str, Any],
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
    hold_reasons = _inventory_hold_reasons(policy, git_state)
    if hold_reasons:
        reasons.extend(hold_reasons)
        return "active-no-write", reasons, "Keep central-only until the active/dirty/non-main hold is reviewed."
    if _path_marker_match(repo, ARCHIVE_MARKERS) and not enrollment_policy_present:
        reasons.append("Archive/snapshot path marker and no reviewed policy.")
        return "archive-ignore", reasons, "Leave out of enrollment unless policy promotes it."
    if duplicate_lineage and not enrollment_policy_present:
        reasons.append("Duplicate DAD contract repo_id appears in more than one local repo path.")
        return "duplicate-ignore", reasons, "Review lineage before choosing one canonical enrolled repo."
    if nested_repo and not enrollment_policy_present:
        reasons.append("Nested Git repo discovered inside another local Git root.")
        return "duplicate-ignore", reasons, "Review nested repo lineage before enrollment or delivery."
    if (
        duplicate_basename
        or _direct_path_marker_match(repo, DUPLICATE_MARKERS)
    ) and not enrollment_policy_present:
        reasons.append("Duplicate/reference/temp path marker or duplicate basename without policy.")
        return "duplicate-ignore", reasons, "Keep central record only; avoid mailbox delivery."
    if _normalize_name(repo.name) in WORKSPACE_ROOT_NAMES and not enrollment_policy_present:
        reasons.append("Workspace/container root marker and no reviewed repo policy.")
        return (
            "duplicate-ignore",
            reasons,
            "Track child repos through inventory; do not enroll the workspace container.",
        )
    if policy and enrollment_policy_present and bool(getattr(policy, "enrollment_enabled", False)):
        reasons.append("Reviewed enrollment policy is present.")
        return "enroll", reasons, "Use reviewed waves and approval IDs for any broad writes."
    if policy and not enrollment_policy_present:
        reasons.append("Reviewed mail policy is present, but no reviewed enrollment policy is present.")
        return (
            "needs-human-classification",
            reasons,
            "Mail delivery may be reviewed separately; enrollment still requires reviewed enrollment policy.",
        )
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
        f"Report ID: `{payload.get('report_id', '')}`",
        f"Content fingerprint: `{payload.get('content_fingerprint', '')}`",
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
        lines.extend(
            [
                "",
                "## GitHub Sources",
                "",
                f"Coverage status: `{payload.get('github_coverage_status', 'unknown')}`",
                "",
            ]
        )
        for source in payload["github_sources"]:
            lines.append(
                f"- {source['source_id']} ({source['owner']}): "
                f"{source['inventory_status']} ({source.get('repo_count', 0)} rows)"
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
    transport_upgrade = payload["weekly"].get("transport_upgrade", {})
    lines.extend(
        [
            "",
            f"Preflight behavior: {payload['weekly']['preflight_behavior']}",
            f"Write boundary: {payload['weekly']['write_boundary']}",
            f"Transport audit command: `{transport_upgrade.get('audit_command', '')}`",
            f"Transport queue: `{transport_upgrade.get('queue_path', '')}`",
            transport_upgrade.get("target_repo_write_boundary", ""),
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
            if not _is_repo_skip_dir_name(item)
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


def _score_asset_path(
    rel_path: str,
    methodology: dict[str, Any],
    *,
    task: str,
) -> tuple[float, float, list[str]]:
    lowered = rel_path.lower().replace("\\", "/")
    importance = 0.0
    relevance = 0.0
    signals: list[str] = []
    for location in methodology.get("candidate_locations", []):
        patterns = [str(pattern).lower() for pattern in location.get("patterns", [])]
        if any(_glob_match(lowered, pattern) for pattern in patterns):
            weight = float(location.get("weight", 0))
            importance += weight
            signals.append(f"location:{location['location_id']}:+{weight:g}")
    path_tokens = _tokenize(lowered)
    task_tokens = _tokenize(task)
    suffix = Path(lowered).suffix
    for signal in methodology.get("recognition_signals", []):
        matched_importance = False
        keywords = _tokenize(signal.get("path_keywords", []))
        if keywords and path_tokens & keywords:
            matched_importance = True
        extensions = set(signal.get("extensions", []))
        if extensions and suffix in extensions:
            matched_importance = True
        if matched_importance:
            weight = float(signal.get("weight", 0))
            importance += weight
            signals.append(f"signal:{signal['signal_id']}:+{weight:g}")
        task_keywords = _tokenize(signal.get("task_keywords", []))
        if task_keywords and task_tokens & task_keywords:
            weight = float(signal.get("weight", 0))
            relevance += weight
            signals.append(f"task_relevance:{signal['signal_id']}:+{weight:g}")
    for downgrade in methodology.get("downgrade_signals", []):
        patterns = [str(pattern).lower() for pattern in downgrade.get("patterns", [])]
        if any(_glob_match(lowered, pattern) for pattern in patterns):
            weight = float(downgrade.get("weight", 0))
            importance -= weight
            signals.append(f"downgrade:{downgrade['signal_id']}:-{weight:g}")
    return max(0.0, importance), max(0.0, relevance), signals


def _asset_candidate_evidence(repo: Path, rel_path: str) -> dict[str, Any]:
    inbound_refs = 0
    front_door_refs = 0
    paired = False
    path = repo / rel_path
    stem = Path(rel_path).stem.lower()
    if stem:
        front_doors = [
            repo / "AGENTS.md",
            repo / "CLAUDE.md",
            repo / "AI_FRONT_DOOR.md",
            repo / "AI_TABLE_OF_CONTENTS.md",
            repo / "MACHINE_NAVIGATION_MANIFEST.json",
        ]
        for file_path in _iter_repo_files(repo, max_files=500):
            if file_path == path or file_path.stat().st_size > 200_000:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            if rel_path.lower().replace("\\", "/") in text or stem in text:
                inbound_refs += 1
                if file_path in front_doors:
                    front_door_refs += 1
    if path.exists():
        siblings = list(path.parent.glob(f"{path.stem}.*"))
        paired = any(item != path and item.suffix.lower() in {".json", ".md", ".py", ".yaml", ".yml"} for item in siblings)
    churn_commits = 0
    git_age_days: int | None = None
    try:
        count = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD", "--", rel_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if count.returncode == 0 and count.stdout.strip().isdigit():
            churn_commits = int(count.stdout.strip())
        first = subprocess.run(
            ["git", "-C", str(repo), "log", "--follow", "--format=%ct", "--reverse", "--", rel_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = next((line for line in first.stdout.splitlines() if line.strip().isdigit()), "")
        if first.returncode == 0 and first_line:
            git_age_days = max(0, int((time.time() - int(first_line)) // 86400))
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return {
        "inbound_refs": inbound_refs,
        "git_age_days": git_age_days,
        "churn_commits": churn_commits,
        "has_paired_test_or_example": paired,
        "front_door_refs": front_door_refs,
    }


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
