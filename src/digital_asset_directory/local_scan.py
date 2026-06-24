from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pathspec import PathSpec

from .config import LocalSource, Settings
from .extractors import classify_asset, extract_bytes, freshness_status
from .ids import asset_id, revision_id
from .models import AssetRecord
from .scoring import score_asset
from .utils import safe_relative, sha256_file, utc_now


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


def scan_local_source(
    source: LocalSource,
    settings: Settings,
    scoring: dict,
    max_files: int | None = None,
) -> tuple[list[AssetRecord], dict[str, str]]:
    files = discover_files(source, max_files=max_files)
    before = {str(path): sha256_file(path) for path in files}
    now = utc_now()
    assets: list[AssetRecord] = []
    base = source.path.resolve()
    repo_roots = _repo_roots(files, base)
    repo_asset_ids: dict[Path, str] = {}

    for repo in sorted(repo_roots):
        logical = f"{source.path_alias}/{safe_relative(repo, base)}".rstrip("/")
        identifier = asset_id(source.id, f"repository:{logical}")
        repo_asset_ids[repo] = identifier
        modified = datetime.fromtimestamp(repo.stat().st_mtime, tz=timezone.utc).isoformat()
        record = AssetRecord(
            asset_id=identifier,
            revision_id=revision_id(
                identifier, before.get(str(next(iter(repo.glob("*")), repo)), "directory")
            ),
            source_id=source.id,
            source_kind="local",
            asset_type="repository",
            title=repo.name,
            description="Local Git repository boundary discovered during read-only inventory.",
            logical_path=logical,
            uri=f"file://{logical}",
            content_hash="directory",
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
            metadata={"path_alias": source.path_alias, "repository_root": logical},
        )
        assets.append(score_asset(record, scoring))

    for path in files:
        stat = path.stat()
        size = stat.st_size
        rel = safe_relative(path, base)
        logical = f"{source.path_alias}/{rel}"
        file_hash = before[str(path)]
        identifier = asset_id(source.id, logical)
        parent_id = None
        repo_root = next((repo for repo in repo_roots if path.is_relative_to(repo)), None)
        if repo_root:
            parent_id = repo_asset_ids[repo_root]
        skipped_content = size > source.max_file_bytes
        if skipped_content:
            extracted = {
                "title": path.stem or path.name,
                "description": "Content not read because the file exceeded the configured size limit.",
                "excerpt": "",
                "text_tokens": [],
                "mime_type": "application/octet-stream",
                "decode_error": False,
                "redaction_count": 0,
                "tags": [],
                "capabilities": [],
                "needs": [],
                "outcomes": [],
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
            metadata={
                "path_alias": source.path_alias,
                "relative_path": rel,
                "repository_root": safe_relative(repo_root, base) if repo_root else None,
                "mime_type": extracted["mime_type"],
                "excerpt": extracted["excerpt"] if settings.store_excerpts else "",
                "text_tokens": extracted["text_tokens"],
                "redaction_count": extracted["redaction_count"],
                "decode_error": extracted["decode_error"],
                "content_skipped_for_size": skipped_content,
            },
        )
        assets.append(score_asset(record, scoring))

    after = {str(path): sha256_file(path) for path in files}
    mutated = {path: digest for path, digest in before.items() if after.get(path) != digest}
    if mutated:
        raise RuntimeError(f"Source mutation detected during scan: {sorted(mutated)[:5]}")
    return assets, before
