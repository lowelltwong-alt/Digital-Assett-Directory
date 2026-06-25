from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pathspec import PathSpec

from .config import LocalSource, Settings
from .extractors import ExtractedContent, classify_asset, extract_bytes, freshness_status
from .ids import asset_id, revision_id
from .models import AssetRecord
from .scoring import score_asset
from .utils import safe_relative, sha256_bytes, sha256_file, utc_now

FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
CLOUD_PLACEHOLDER_FLAGS = (
    FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)


def _compile_spec(patterns: list[str]) -> PathSpec:
    return PathSpec.from_lines("gitwildmatch", patterns)


def discover_files(source: LocalSource, max_files: int | None = None) -> list[Path]:
    base = source.path.resolve()
    if not base.exists():
        return []
    spec = _compile_spec(source.exclude)
    result: list[Path] = []
    for current, dirs, names in os.walk(base, followlinks=source.follow_symlinks):
        current_path = Path(current)
        rel_dir = safe_relative(current_path, base)
        dirs[:] = [
            d
            for d in dirs
            if not spec.match_file(f"{rel_dir}/{d}/")
            and (source.follow_symlinks or not (current_path / d).is_symlink())
        ]
        for name in names:
            path = current_path / name
            rel = safe_relative(path, base)
            if spec.match_file(rel) or path.is_symlink():
                continue
            result.append(path)
            if max_files and len(result) >= max_files:
                return result
    return result


def _is_cloud_placeholder(stat: os.stat_result) -> bool:
    if os.name != "nt":
        return False
    return bool(getattr(stat, "st_file_attributes", 0) & CLOUD_PLACEHOLDER_FLAGS)


def _cloud_placeholder_detection_mode() -> str:
    return "windows_file_attributes" if os.name == "nt" else "bounded_size_only_non_windows"


def _metadata_fingerprint(stat: os.stat_result) -> str:
    payload = (
        f"{stat.st_size}:{stat.st_mtime_ns}:"
        f"{getattr(stat, 'st_file_attributes', 0)}"
    ).encode("utf-8")
    return sha256_bytes(payload)


def _file_revision_identity(path: Path, max_file_bytes: int) -> tuple[str, str]:
    stat = path.stat()
    placeholder = _is_cloud_placeholder(stat)
    if stat.st_size > max_file_bytes or placeholder:
        mode = (
            "metadata_sha256_for_cloud_placeholder"
            if placeholder
            else "metadata_sha256_for_oversize_file"
        )
        return _metadata_fingerprint(stat), mode
    return sha256_file(path), "content_sha256"


def _repo_roots(files: Iterable[Path], base: Path) -> set[Path]:
    roots: set[Path] = set()
    visited: set[Path] = set()
    for file in files:
        parent = file.parent
        while parent != base.parent and parent not in visited:
            visited.add(parent)
            if (parent / ".git").exists():
                roots.add(parent)
                break
            if parent == base:
                break
            parent = parent.parent
    return roots


def _repo_composite_patterns(child_assets: list[AssetRecord]) -> list[dict[str, object]]:
    type_ids = {asset.asset_type for asset in child_assets}
    tags = {tag for asset in child_assets for tag in asset.tags}
    capabilities = {capability for asset in child_assets for capability in asset.capabilities}
    asset_patterns = {
        str(pattern_id)
        for asset in child_assets
        for pattern_id in asset.metadata.get("asset_patterns", [])
    }
    patterns: list[dict[str, object]] = []

    def add(pattern_id: str, label: str, evidence: list[str], leverage: str) -> None:
        if len(evidence) >= 2:
            patterns.append(
                {
                    "pattern_id": pattern_id,
                    "label": label,
                    "evidence": sorted(set(evidence)),
                    "leverage": leverage,
                    "review_status": "generated_candidate",
                    "authority": "Composite pattern hint only; human review required.",
                }
            )

    add(
        "ai_agent_workflow_system",
        "AI agent workflow system",
        [
            *(["asset_type:agent"] if "agent" in type_ids else []),
            *(["asset_type:skill"] if "skill" in type_ids else []),
            *(["asset_type:workflow"] if "workflow" in type_ids else []),
            *(["tag:agent"] if "agent" in tags else []),
            *(["capability:govern_agents"] if "govern_agents" in capabilities else []),
            *(["capability:capture_lessons"] if "capture_lessons" in capabilities else []),
        ],
        "very_high",
    )
    add(
        "evaluation_contract_system",
        "Evaluation and contract system",
        [
            *(["asset_type:test"] if "test" in type_ids else []),
            *(["asset_type:evaluation"] if "evaluation" in type_ids else []),
            *(["asset_type:schema"] if "schema" in type_ids else []),
            *(["asset_type:ontology"] if "ontology" in type_ids else []),
            *(["capability:validate_contracts"] if "validate_contracts" in capabilities else []),
        ],
        "very_high",
    )
    add(
        "knowledge_graph_retrieval_system",
        "Knowledge graph and retrieval system",
        [
            *(["asset_type:ontology"] if "ontology" in type_ids else []),
            *(["asset_type:taxonomy"] if "taxonomy" in type_ids else []),
            *(["tag:knowledge-graph"] if "knowledge-graph" in tags else []),
            *(["tag:retrieval"] if "retrieval" in tags else []),
            *(["capability:build_knowledge_graph"] if "build_knowledge_graph" in capabilities else []),
            *(["capability:retrieve_context"] if "retrieve_context" in capabilities else []),
        ],
        "very_high",
    )
    add(
        "governed_learning_loop_system",
        "Governed learning loop system",
        [
            *(["asset_type:lesson"] if "lesson" in type_ids else []),
            *(["asset_type:workflow"] if "workflow" in type_ids else []),
            *(["tag:learning-loop"] if "learning-loop" in tags else []),
            *(["tag:governance"] if "governance" in tags else []),
            *(["capability:capture_lessons"] if "capture_lessons" in capabilities else []),
            *(["capability:govern_agents"] if "govern_agents" in capabilities else []),
            *(
                ["asset_pattern:governed_learning_loop"]
                if "governed_learning_loop" in asset_patterns
                else []
            ),
        ],
        "very_high",
    )
    add(
        "route_isolated_evaluation_harness",
        "Route-isolated evaluation harness",
        [
            *(["asset_type:evaluation"] if "evaluation" in type_ids else []),
            *(["asset_type:test"] if "test" in type_ids else []),
            *(["tag:retrieval"] if "retrieval" in tags else []),
            *(["capability:validate_contracts"] if "validate_contracts" in capabilities else []),
            *(
                ["asset_pattern:route_isolated_evaluation_harness"]
                if "route_isolated_evaluation_harness" in asset_patterns
                else []
            ),
            *(
                ["asset_pattern:gold_review_packet_system"]
                if "gold_review_packet_system" in asset_patterns
                else []
            ),
        ],
        "very_high",
    )
    add(
        "agent_skill_graph_system",
        "Agent and skill graph system",
        [
            *(["asset_type:agent"] if "agent" in type_ids else []),
            *(["asset_type:skill"] if "skill" in type_ids else []),
            *(["tag:knowledge-graph"] if "knowledge-graph" in tags else []),
            *(["capability:build_knowledge_graph"] if "build_knowledge_graph" in capabilities else []),
            *(
                ["asset_pattern:agent_skill_graph_system"]
                if "agent_skill_graph_system" in asset_patterns
                else []
            ),
        ],
        "very_high",
    )
    add(
        "boundary_contamination_firewall",
        "Boundary and contamination firewall",
        [
            *(["tag:security"] if "security" in tags else []),
            *(["tag:governance"] if "governance" in tags else []),
            *(["capability:protect_sensitive_data"] if "protect_sensitive_data" in capabilities else []),
            *(
                ["asset_pattern:boundary_contamination_firewall"]
                if "boundary_contamination_firewall" in asset_patterns
                else []
            ),
            *(
                ["asset_pattern:security_governance_gate"]
                if "security_governance_gate" in asset_patterns
                else []
            ),
        ],
        "very_high",
    )
    add(
        "proposal_promotion_workflow",
        "Proposal-to-promotion workflow",
        [
            *(["asset_type:decision"] if "decision" in type_ids else []),
            *(["asset_type:workflow"] if "workflow" in type_ids else []),
            *(["tag:governance"] if "governance" in tags else []),
            *(
                ["asset_pattern:proposal_promotion_workflow"]
                if "proposal_promotion_workflow" in asset_patterns
                else []
            ),
        ],
        "very_high",
    )
    add(
        "frontier_signal_intake_loop",
        "Frontier signal intake loop",
        [
            *(["asset_type:research"] if "research" in type_ids else []),
            *(["tag:research-radar"] if "research-radar" in tags else []),
            *(["capability:research_missing_parts"] if "research_missing_parts" in capabilities else []),
            *(
                ["asset_pattern:frontier_signal_intake_loop"]
                if "frontier_signal_intake_loop" in asset_patterns
                else []
            ),
        ],
        "high",
    )
    add(
        "gold_review_packet_system",
        "Gold set and review packet system",
        [
            *(["asset_type:evaluation"] if "evaluation" in type_ids else []),
            *(["asset_type:dataset"] if "dataset" in type_ids else []),
            *(
                ["asset_pattern:gold_review_packet_system"]
                if "gold_review_packet_system" in asset_patterns
                else []
            ),
        ],
        "very_high",
    )
    add(
        "duplicate_variant_preservation_system",
        "Duplicate and variant preservation system",
        [
            *(["asset_type:archive"] if "archive" in type_ids else []),
            *(["tag:provenance"] if "provenance" in tags else []),
            *(
                ["asset_pattern:duplicate_variant_preservation_system"]
                if "duplicate_variant_preservation_system" in asset_patterns
                else []
            ),
        ],
        "high",
    )
    add(
        "security_governance_system",
        "Security and governance gate system",
        [
            *(["asset_type:configuration"] if "configuration" in type_ids else []),
            *(["asset_type:test"] if "test" in type_ids else []),
            *(["tag:security"] if "security" in tags else []),
            *(["tag:governance"] if "governance" in tags else []),
            *(["capability:protect_sensitive_data"] if "protect_sensitive_data" in capabilities else []),
            *(["capability:govern_agents"] if "govern_agents" in capabilities else []),
        ],
        "high",
    )
    add(
        "model_algorithm_system",
        "Model, algorithm, or forecasting system",
        [
            *(["asset_type:code"] if "code" in type_ids else []),
            *(["asset_type:dataset"] if "dataset" in type_ids else []),
            *(["asset_type:evaluation"] if "evaluation" in type_ids else []),
            *(["capability:score_assets"] if "score_assets" in capabilities else []),
            *(["tag:evaluation"] if "evaluation" in tags else []),
            *(["tag:research-radar"] if "research-radar" in tags else []),
        ],
        "high",
    )
    return sorted(patterns, key=lambda item: str(item["pattern_id"]))


def scan_local_source(
    source: LocalSource,
    settings: Settings,
    scoring: dict,
    max_files: int | None = None,
) -> tuple[list[AssetRecord], dict[str, str]]:
    files = discover_files(source, max_files=max_files)
    before_identities: dict[str, tuple[str, str]] = {}
    for path in files:
        try:
            before_identities[str(path)] = _file_revision_identity(path, source.max_file_bytes)
        except (FileNotFoundError, OSError):
            continue
    files = [path for path in files if str(path) in before_identities]
    before = {path: identity for path, (identity, _mode) in before_identities.items()}
    now = utc_now()
    assets: list[AssetRecord] = []
    assets_by_path: dict[str, AssetRecord] = {}
    base = source.path.resolve()
    repo_roots = _repo_roots(files, base)
    repo_asset_ids: dict[Path, str] = {}

    for repo in sorted(repo_roots):
        logical = f"{source.path_alias}/{safe_relative(repo, base)}".rstrip("/")
        identifier = asset_id(source.id, f"repository:{logical}")
        repo_asset_ids[repo] = identifier
        repo_stat = repo.stat()
        metadata_fingerprint = _metadata_fingerprint(repo_stat)
        modified = datetime.fromtimestamp(repo_stat.st_mtime, tz=timezone.utc).isoformat()
        record = AssetRecord(
            asset_id=identifier,
            revision_id=revision_id(identifier, metadata_fingerprint),
            source_id=source.id,
            source_kind="local",
            asset_type="repository",
            title=repo.name,
            description="Local Git repository boundary discovered during read-only inventory.",
            logical_path=logical,
            uri=f"file://{logical}",
            content_hash="directory",
            metadata_fingerprint=metadata_fingerprint,
            content_sha256=None,
            modified_at=modified,
            first_seen_at=now,
            last_seen_at=now,
            tags=["repository"],
            capabilities=["catalog_assets"],
            outcomes=["faster_builds", "higher_discovery"],
            entrypoints=[
                p.name
                for p in repo.iterdir()
                if p.name
                in {"README.md", "AI_FRONT_DOOR.md", "AGENTS.md", "CLAUDE.md", "pyproject.toml"}
            ],
            lifecycle_state="active",
            freshness_status=freshness_status(
                modified, settings.stale_days_by_type.get("repository", settings.stale_days_default)
            ),
            sensitivity="internal",
            trust_zone="source_owned",
            confidence="high",
            source_provenance={
                "source_id": source.id,
                "source_kind": "local",
                "path_alias": source.path_alias,
                "logical_path": logical,
                "observed_by": "local_scan",
                "authority": "Source repository remains authoritative.",
            },
            metadata={
                "path_alias": source.path_alias,
                "repository_root": logical,
                "revision_identity_mode": "directory_metadata",
            },
        )
        assets.append(score_asset(record, scoring))

    for path in files:
        try:
            stat = path.stat()
        except (FileNotFoundError, OSError):
            continue
        size = stat.st_size
        rel = safe_relative(path, base)
        logical = f"{source.path_alias}/{rel}"
        file_hash = before[str(path)]
        revision_identity_mode = before_identities[str(path)][1]
        metadata_fingerprint = _metadata_fingerprint(stat)
        identifier = asset_id(source.id, logical)
        parent_id = None
        repo_root = next((repo for repo in repo_roots if path.is_relative_to(repo)), None)
        if repo_root:
            parent_id = repo_asset_ids[repo_root]
        cloud_placeholder = _is_cloud_placeholder(stat)
        content_exceeds_size_limit = size > source.max_file_bytes
        skipped_content = content_exceeds_size_limit or cloud_placeholder
        extracted: ExtractedContent
        if skipped_content:
            skip_reason = (
                "cloud storage placeholder or offline file"
                if cloud_placeholder
                else "configured size limit"
            )
            extracted = {
                "title": path.stem or path.name,
                "description": f"Content not read because the file matched the {skip_reason}.",
                "excerpt": "",
                "chunk_text": "",
                "text_tokens": [],
                "mime_type": "application/octet-stream",
                "decode_error": False,
                "redaction_count": 0,
                "tags": [],
                "capabilities": [],
                "needs": [],
                "outcomes": [],
                "asset_patterns": [],
                "pattern_evidence": {},
            }
        else:
            data = path.read_bytes()
            extracted = extract_bytes(
                logical, data, source.excerpt_chars, settings.redact_sensitive_excerpts
            )
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        asset_type = classify_asset(logical)
        stale_days = settings.stale_days_by_type.get(asset_type, settings.stale_days_default)
        record = AssetRecord(
            asset_id=identifier,
            revision_id=revision_id(identifier, file_hash),
            source_id=source.id,
            parent_asset_id=parent_id,
            source_kind="local",
            asset_type=asset_type,
            title=extracted["title"],
            description=extracted["description"],
            logical_path=logical,
            uri=f"file://{logical}",
            content_hash=file_hash,
            metadata_fingerprint=metadata_fingerprint,
            content_sha256=file_hash if revision_identity_mode == "content_sha256" else None,
            size_bytes=size,
            modified_at=modified,
            first_seen_at=now,
            last_seen_at=now,
            tags=extracted["tags"],
            capabilities=extracted["capabilities"],
            needs=extracted["needs"],
            outcomes=extracted["outcomes"],
            entrypoints=[path.name]
            if path.name in {"README.md", "AI_FRONT_DOOR.md", "AGENTS.md", "CLAUDE.md"}
            else [],
            lifecycle_state="stale"
            if freshness_status(modified, stale_days) == "stale"
            else "discovered",
            freshness_status=freshness_status(modified, stale_days),
            sensitivity="internal",
            trust_zone="source_owned",
            confidence="high",
            source_provenance={
                "source_id": source.id,
                "source_kind": "local",
                "path_alias": source.path_alias,
                "logical_path": logical,
                "observed_by": "local_scan",
                "authority": "Source repository remains authoritative.",
            },
            metadata={
                "path_alias": source.path_alias,
                "relative_path": rel,
                "repository_root": safe_relative(repo_root, base) if repo_root else None,
                "mime_type": extracted["mime_type"],
                "excerpt": extracted["excerpt"] if settings.store_excerpts else "",
                "chunk_text": extracted["chunk_text"] if settings.store_excerpts else "",
                "text_tokens": extracted["text_tokens"],
                "asset_patterns": extracted["asset_patterns"],
                "pattern_evidence": extracted["pattern_evidence"],
                "redaction_count": extracted["redaction_count"],
                "decode_error": extracted["decode_error"],
                "content_skipped_for_size": content_exceeds_size_limit,
                "content_skipped_for_cloud_placeholder": cloud_placeholder,
                "cloud_placeholder_detection_mode": _cloud_placeholder_detection_mode(),
                "revision_identity_mode": revision_identity_mode,
            },
        )
        assets.append(score_asset(record, scoring))
        assets_by_path[str(path)] = record

    assets_by_id = {asset.asset_id: asset for asset in assets}
    for repo_path, repo_id in repo_asset_ids.items():
        child_assets = [
            asset
            for asset in assets
            if asset.parent_asset_id == repo_id
            and asset.logical_path.startswith(f"{source.path_alias}/{safe_relative(repo_path, base)}")
        ]
        repo_asset = assets_by_id[repo_id]
        repo_patterns = _repo_composite_patterns(child_assets)
        if repo_patterns:
            repo_asset.metadata["composite_patterns"] = repo_patterns
            repo_asset.metadata["composite_asset_hint"] = {
                "asset_type_candidates": ["repository", "asset_bundle"],
                "child_asset_count": len(child_assets),
                "member_asset_ids": [asset.asset_id for asset in child_assets[:50]],
                "authority": "Generated composite candidate; source repository remains authoritative.",
            }
            repo_asset.tags = sorted(
                set(repo_asset.tags)
                | {"composite-asset", *(str(item["pattern_id"]) for item in repo_patterns)}
            )
            repo_asset.outcomes = sorted(set(repo_asset.outcomes) | {"repeatable_quality"})
            score_asset(repo_asset, scoring)

    after_identities: dict[str, tuple[str, str]] = {}
    for path in files:
        try:
            after_identities[str(path)] = _file_revision_identity(path, source.max_file_bytes)
        except (FileNotFoundError, OSError):
            continue
    after = {path: identity for path, (identity, _mode) in after_identities.items()}
    mutated = {
        path: digest
        for path, digest in before.items()
        if path in after and after.get(path) != digest
    }
    for path in mutated:
        asset = assets_by_path.get(path)
        if asset:
            asset.confidence = "low"
            asset.metadata["scan_stability"] = "changed_during_scan"
            asset.metadata["changed_during_scan"] = True
            asset.metadata["post_scan_revision_identity"] = after.get(path)
    return assets, before
