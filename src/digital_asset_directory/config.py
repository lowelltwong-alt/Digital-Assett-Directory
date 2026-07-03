from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import json
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
    write_protected: bool = False
    write_protection_reason: str = ""


@dataclass
class ExceptionRepoPolicy:
    id: str
    path: Path
    alias: str
    visibility: str = "unknown"
    public_facing: bool = False
    exceptions_enabled: bool = True
    collect_allowed: bool = True
    capture_audit_allowed: bool = True
    backfill_allowed: bool = False
    write_protected: bool = False
    write_protection_reason: str = ""


@dataclass
class EnrollmentRepoPolicy:
    id: str
    path: Path
    alias: str
    visibility: str = "unknown"
    public_facing: bool = False
    enrollment_enabled: bool = True
    apply_allowed: bool = False
    update_allowed: bool = False
    active_hold: bool = False
    active_hold_reason: str = ""
    allow_dirty_worktree: bool = False
    allow_non_main_branch: bool = False
    wave: str = ""
    approved_approval_ids: list[str] = field(default_factory=list)
    local_paths_allowed: bool = False
    repo_type: str = "unknown"
    languages: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    context_tags: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    enabled_control_planes: list[str] = field(default_factory=list)


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
    exception_repos: list[ExceptionRepoPolicy] = field(default_factory=list)
    enrollment_repos: list[EnrollmentRepoPolicy] = field(default_factory=list)


def resolve_config_path(repo_root: Path, requested: Path | None = None) -> Path:
    if requested:
        return requested if requested.is_absolute() else repo_root / requested
    local = repo_root / "config" / "sources.local.yaml"
    return local if local.exists() else repo_root / "config" / "sources.example.yaml"


def resolve_hub_root(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root.resolve()
    for env_name in ("DAD_HUB", "DAD_HUB_PATH"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(os.path.expandvars(os.path.expanduser(value))).resolve()
    locator = Path.home() / ".dad" / "hub.json"
    if locator.exists():
        payload = json.loads(locator.read_text(encoding="utf-8"))
        value = str(payload.get("hub_path") or payload.get("path") or "").strip()
        if value:
            return Path(os.path.expandvars(os.path.expanduser(value))).resolve()
    current = find_repo_root(Path.cwd()).resolve()
    if (current / "registry" / "source-of-truth.json").exists() and (
        current / "src" / "digital_asset_directory"
    ).exists():
        return current
    raise FileNotFoundError(
        "DAD hub unavailable. Set --hub, DAD_HUB, or ~/.dad/hub.json before "
        "running DAD commands outside the hub repo."
    )


def load_config(path: Path | None = None, repo_root: Path | None = None) -> AppConfig:
    root = resolve_hub_root(repo_root)
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
                write_protected=bool(item.get("write_protected", False)),
                write_protection_reason=str(item.get("write_protection_reason", "")),
            )
        )

    exception_repos: list[ExceptionRepoPolicy] = []
    for item in raw.get("exceptions", {}).get("repos", []) or []:
        raw_path = os.path.expandvars(os.path.expanduser(str(item.get("path", ""))))
        path = Path(raw_path)
        resolved_path = path if path.is_absolute() else root / path
        repo_id = str(item["id"])
        exception_repos.append(
            ExceptionRepoPolicy(
                id=repo_id,
                path=resolved_path,
                alias=str(item.get("alias") or repo_id),
                visibility=str(item.get("visibility", "unknown")),
                public_facing=bool(item.get("public_facing", False)),
                exceptions_enabled=bool(item.get("exceptions_enabled", True)),
                collect_allowed=bool(item.get("collect_allowed", True)),
                capture_audit_allowed=bool(item.get("capture_audit_allowed", True)),
                backfill_allowed=bool(item.get("backfill_allowed", False)),
                write_protected=bool(item.get("write_protected", False)),
                write_protection_reason=str(item.get("write_protection_reason", "")),
            )
        )

    enrollment_repos: list[EnrollmentRepoPolicy] = []
    for item in raw.get("enrollment", {}).get("repos", []) or []:
        raw_path = os.path.expandvars(os.path.expanduser(str(item.get("path", ""))))
        path = Path(raw_path)
        resolved_path = path if path.is_absolute() else root / path
        repo_id = str(item["id"])
        enrollment_repos.append(
            EnrollmentRepoPolicy(
                id=repo_id,
                path=resolved_path,
                alias=str(item.get("alias") or repo_id),
                visibility=str(item.get("visibility", "unknown")),
                public_facing=bool(item.get("public_facing", False)),
                enrollment_enabled=bool(item.get("enrollment_enabled", True)),
                apply_allowed=bool(item.get("apply_allowed", False)),
                update_allowed=bool(item.get("update_allowed", False)),
                active_hold=bool(item.get("active_hold", False)),
                active_hold_reason=str(item.get("active_hold_reason", "")),
                allow_dirty_worktree=bool(item.get("allow_dirty_worktree", False)),
                allow_non_main_branch=bool(item.get("allow_non_main_branch", False)),
                wave=str(item.get("wave", "")),
                approved_approval_ids=[
                    str(value) for value in item.get("approved_approval_ids", []) or []
                ],
                local_paths_allowed=bool(item.get("local_paths_allowed", False)),
                repo_type=str(item.get("repo_type", "unknown")),
                languages=[str(value) for value in item.get("languages", []) or []],
                domains=[str(value) for value in item.get("domains", []) or []],
                context_tags=[str(value) for value in item.get("context_tags", []) or []],
                validation_commands=[
                    str(value) for value in item.get("validation_commands", []) or []
                ],
                enabled_control_planes=[
                    str(value) for value in item.get("enabled_control_planes", []) or []
                ],
            )
        )

    settings_raw = raw.get("settings", {})
    settings = Settings(
        **{k: v for k, v in settings_raw.items() if k in Settings.__dataclass_fields__}
    )
    return AppConfig(
        root,
        raw,
        db_path,
        local_sources,
        github_sources,
        settings,
        mail_repos,
        exception_repos,
        enrollment_repos,
    )
