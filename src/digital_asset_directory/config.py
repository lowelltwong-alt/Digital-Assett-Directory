from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import yaml

from .utils import find_repo_root


@dataclass
class LocalSource:
    id: str
    path: Path
    path_alias: str
    enabled: bool = True
    follow_symlinks: bool = False
    max_file_bytes: int = 2_000_000
    excerpt_chars: int = 5_000
    include_binary_metadata: bool = True
    exclude: list[str] = field(default_factory=list)


@dataclass
class GitHubSource:
    id: str
    owner: str
    enabled: bool = True
    token_env: str = "GITHUB_TOKEN"
    include_private: bool = True
    include_archived: bool = True
    content_mode: str = "priority"
    max_file_bytes: int = 1_000_000
    priority_patterns: list[str] = field(default_factory=list)


@dataclass
class MailRepoPolicy:
    id: str
    path: Path
    alias: str
    visibility: str = "unknown"
    public_facing: bool = False
    mail_enabled: bool = True
    delivery_allowed: bool = True


@dataclass
class Settings:
    read_only: bool = True
    store_excerpts: bool = True
    redact_sensitive_excerpts: bool = True
    stale_days_default: int = 365
    stale_days_by_type: dict[str, int] = field(default_factory=dict)
    related_similarity_threshold: float = 0.34
    synergy_alert_threshold: float = 0.64
    high_value_threshold: float = 70.0
    orphan_degree_threshold: int = 1
    max_related_edges_per_asset: int = 20
    max_context_assets: int = 20
    skill_candidate_repeat_threshold: int = 3


@dataclass
class AppConfig:
    repo_root: Path
    raw: dict[str, Any]
    database_path: Path
    local_sources: list[LocalSource]
    github_sources: list[GitHubSource]
    settings: Settings
    mail_repos: list[MailRepoPolicy] = field(default_factory=list)


def resolve_config_path(repo_root: Path, requested: Path | None = None) -> Path:
    if requested:
        return requested if requested.is_absolute() else repo_root / requested
    local = repo_root / "config" / "sources.local.yaml"
    return local if local.exists() else repo_root / "config" / "sources.example.yaml"


def load_config(path: Path | None = None, repo_root: Path | None = None) -> AppConfig:
    root = (repo_root or find_repo_root(Path.cwd())).resolve()
    cfg_path = resolve_config_path(root, path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    project = raw.get("project", {})
    db = Path(project.get("database", "state/catalog.sqlite3"))
    db_path = db if db.is_absolute() else root / db

    local_sources: list[LocalSource] = []
    for item in raw.get("sources", {}).get("local", []) or []:
        raw_path = os.path.expandvars(os.path.expanduser(str(item.get("path", ""))))
        local_sources.append(
            LocalSource(
                id=str(item["id"]),
                path=Path(raw_path),
                path_alias=str(item.get("path_alias") or item["id"]),
                enabled=bool(item.get("enabled", True)),
                follow_symlinks=bool(item.get("follow_symlinks", False)),
                max_file_bytes=int(item.get("max_file_bytes", 2_000_000)),
                excerpt_chars=int(item.get("excerpt_chars", 5_000)),
                include_binary_metadata=bool(item.get("include_binary_metadata", True)),
                exclude=list(item.get("exclude", [])),
            )
        )

    github_sources = [
        GitHubSource(
            id=str(item["id"]),
            owner=str(item["owner"]),
            enabled=bool(item.get("enabled", True)),
            token_env=str(item.get("token_env", "GITHUB_TOKEN")),
            include_private=bool(item.get("include_private", True)),
            include_archived=bool(item.get("include_archived", True)),
            content_mode=str(item.get("content_mode", "priority")),
            max_file_bytes=int(item.get("max_file_bytes", 1_000_000)),
            priority_patterns=list(item.get("priority_patterns", [])),
        )
        for item in raw.get("sources", {}).get("github", []) or []
    ]

    mail_repos: list[MailRepoPolicy] = []
    for item in raw.get("mail", {}).get("repos", []) or []:
        raw_path = os.path.expandvars(os.path.expanduser(str(item.get("path", ""))))
        path = Path(raw_path)
        resolved_path = path if path.is_absolute() else root / path
        repo_id = str(item["id"])
        mail_repos.append(
            MailRepoPolicy(
                id=repo_id,
                path=resolved_path,
                alias=str(item.get("alias") or repo_id),
                visibility=str(item.get("visibility", "unknown")),
                public_facing=bool(item.get("public_facing", False)),
                mail_enabled=bool(item.get("mail_enabled", True)),
                delivery_allowed=bool(item.get("delivery_allowed", True)),
            )
        )

    settings_raw = raw.get("settings", {})
    settings = Settings(
        **{k: v for k, v in settings_raw.items() if k in Settings.__dataclass_fields__}
    )
    return AppConfig(root, raw, db_path, local_sources, github_sources, settings, mail_repos)
