from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import json
import yaml

from .transport import resolve_data_root
from .utils import atomic_write_text, find_repo_root


HUB_ENV_NAMES = ("DAD_HUB", "DAD_HUB_PATH")
HUB_LOCATOR_RELATIVE_PATH = Path(".dad") / "hub.json"
CONFIG_ENV_NAME = "DAD_CONFIG"


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
    repositories: list[dict[str, Any]] = field(default_factory=list)
    repositories_file: Path | None = None


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
    llos_control_path: Path | None = None
    transport_audit_path: Path | None = None


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
    approved_approval_ids: list[str] = field(default_factory=list)
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


def read_config_pointer(
    *,
    environ: dict[str, str] | None = None,
    locator: Path | None = None,
) -> dict[str, Any]:
    """Resolve the governed user-level local-config pointer.

    Precedence: the ``DAD_CONFIG`` env var, then the ``config_path`` field in
    ``~/.dad/hub.json``. The pointer only "wins" when it names an existing
    readable file; a set-but-missing/unreadable pointer is reported with an
    ``error`` so callers can warn instead of silently splitting authority.
    Returns ``{source, value, path, exists, usable, error}``.
    """
    env = environ if environ is not None else os.environ
    raw = str(env.get(CONFIG_ENV_NAME, "") or "").strip()
    source = CONFIG_ENV_NAME
    if not raw:
        locator_path = locator or hub_locator_path()
        source = "user_locator"
        if locator_path.exists():
            try:
                payload = json.loads(locator_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                return {
                    "source": "user_locator",
                    "value": "",
                    "path": "",
                    "exists": False,
                    "usable": False,
                    "error": f"invalid hub locator JSON: {exc}",
                }
            if isinstance(payload, dict):
                raw = str(payload.get("config_path") or "").strip()
    if not raw:
        return {"source": "", "value": "", "path": "", "exists": False, "usable": False, "error": ""}
    resolved = _expand_path(raw)
    exists = resolved.exists() and resolved.is_file()
    return {
        "source": source,
        "value": raw,
        "path": str(resolved),
        "exists": exists,
        "usable": exists,
        "error": "" if exists else f"configured local-config pointer does not name a readable file: {resolved}",
    }


def resolve_config_path(
    repo_root: Path,
    requested: Path | None = None,
    *,
    environ: dict[str, str] | None = None,
    locator: Path | None = None,
) -> Path:
    if requested:
        return requested if requested.is_absolute() else repo_root / requested
    local = repo_root / "config" / "sources.local.yaml"
    if local.exists():
        return local
    pointer = read_config_pointer(environ=environ, locator=locator)
    if pointer["usable"]:
        return Path(pointer["path"])
    return repo_root / "config" / "sources.example.yaml"


def write_config_pointer(config_path: Path, locator: Path | None = None) -> dict[str, Any]:
    """Record a canonical local-config pointer in ``~/.dad/hub.json``.

    This only writes the user-level locator (never a repo file) and refuses a
    pointer that does not name an existing readable file, so isolated worktrees
    can resolve the canonical config without copying private config in.
    """
    resolved = config_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"Refusing to record a local-config pointer to a missing file: {resolved}")
    locator_path = locator or hub_locator_path()
    payload: dict[str, Any] = {}
    if locator_path.exists():
        try:
            existing = json.loads(locator_path.read_text(encoding="utf-8-sig"))
            if isinstance(existing, dict):
                payload = existing
        except json.JSONDecodeError:
            payload = {}
    payload.setdefault("schema_version", "dad.hub-locator.v1")
    payload["config_path"] = str(resolved)
    locator_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(locator_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {"path": str(locator_path), "config_path": str(resolved), "written": True}


def describe_config_resolution(
    repo_root: Path,
    requested: Path | None = None,
    *,
    environ: dict[str, str] | None = None,
    locator: Path | None = None,
) -> dict[str, Any]:
    """Explain which config file wins and why (for ``asset-dir config show``)."""
    root = repo_root.resolve()
    local = root / "config" / "sources.local.yaml"
    example = root / "config" / "sources.example.yaml"
    pointer = read_config_pointer(environ=environ, locator=locator)
    resolved = resolve_config_path(root, requested, environ=environ, locator=locator)
    if requested is not None:
        source = "explicit_--config"
    elif local.exists():
        source = "repo_sources_local"
    elif pointer["usable"]:
        source = f"user_pointer:{pointer['source']}"
    else:
        source = "repo_sources_example"
    warnings: list[str] = []
    if pointer["value"] and not pointer["usable"] and not local.exists():
        warnings.append(pointer["error"])
    return {
        "resolved_path": str(resolved),
        "resolved_exists": resolved.exists(),
        "source": source,
        "precedence": [
            {"source": "explicit_--config", "path": str(requested) if requested else "", "active": requested is not None},
            {"source": "repo_sources_local", "path": str(local), "active": requested is None and local.exists()},
            {
                "source": f"user_pointer:{pointer['source'] or 'unset'}",
                "path": pointer["path"],
                "active": requested is None and not local.exists() and pointer["usable"],
            },
            {"source": "repo_sources_example", "path": str(example), "active": source == "repo_sources_example"},
        ],
        "pointer": pointer,
        "warnings": warnings,
    }


def is_dad_hub_root(path: Path) -> bool:
    root = path.resolve()
    required_files = [
        root / "AI_FRONT_DOOR.md",
        root / "MACHINE_NAVIGATION_MANIFEST.json",
        root / "registry" / "source-of-truth.json",
        root / "pyproject.toml",
        root / "src" / "digital_asset_directory" / "cli.py",
    ]
    if not all(path.exists() and path.is_file() for path in required_files):
        return False
    try:
        pyproject_text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        'name = "digital-asset-directory"' in pyproject_text
        and 'asset-dir = "digital_asset_directory.cli:app"' in pyproject_text
    )


def hub_locator_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / HUB_LOCATOR_RELATIVE_PATH


def _expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def _resolve_config_path_value(root: Path, value: Any) -> Path:
    raw_path = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def _github_repository_rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    rows = payload
    if isinstance(payload, dict):
        rows = payload.get("repositories", payload.get("repos", []))
    if not isinstance(rows, list):
        return []
    return [dict(value) for value in rows if isinstance(value, dict)]


def load_github_repositories_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"GitHub repository metadata file not found: {path}")
    text = path.read_text(encoding="utf-8-sig")
    payload = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    return _github_repository_rows_from_payload(payload)


def read_hub_locator(locator: Path | None = None) -> dict[str, Any]:
    locator_path = locator or hub_locator_path()
    if not locator_path.exists():
        return {
            "exists": False,
            "path": str(locator_path),
            "hub_path": "",
            "error": "",
        }
    try:
        payload = json.loads(locator_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {
            "exists": True,
            "path": str(locator_path),
            "hub_path": "",
            "error": f"invalid JSON: {exc}",
        }
    if not isinstance(payload, dict):
        return {
            "exists": True,
            "path": str(locator_path),
            "hub_path": "",
            "error": "invalid locator payload: expected JSON object",
        }
    value = str(payload.get("hub_path") or payload.get("path") or "").strip()
    if not value:
        return {
            "exists": True,
            "path": str(locator_path),
            "hub_path": "",
            "error": "missing hub_path",
        }
    resolved = _expand_path(value)
    return {
        "exists": True,
        "path": str(locator_path),
        "hub_path": str(resolved),
        "is_dad_hub": is_dad_hub_root(resolved),
        "error": "",
    }


def write_hub_locator(hub_root: Path, locator: Path | None = None) -> dict[str, Any]:
    root = hub_root.resolve()
    if not is_dad_hub_root(root):
        raise ValueError(f"Refusing to write DAD hub locator for non-DAD path: {root}")
    locator_path = locator or hub_locator_path()
    locator_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "dad.hub-locator.v1",
        "hub_path": str(root),
        "hub_ref": "dad://hub/Digital-Assett-Directory",
    }
    atomic_write_text(locator_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {
        "path": str(locator_path),
        "hub_path": str(root),
        "schema_version": payload["schema_version"],
        "written": True,
    }


def describe_hub_resolution(
    explicit_hub: Path | None = None,
    *,
    cwd: Path | None = None,
    environ: dict[str, str] | None = None,
    locator: Path | None = None,
    allow_current_fallback: bool = True,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    attempts: list[dict[str, Any]] = []

    def candidate(source: str, raw_value: str, *, detail: str = "") -> dict[str, Any]:
        try:
            resolved = _expand_path(raw_value)
            error = ""
        except RuntimeError as exc:
            resolved = Path(raw_value)
            error = str(exc)
        record = {
            "source": source,
            "value": raw_value,
            "path": str(resolved),
            "exists": resolved.exists(),
            "is_dad_hub": error == "" and resolved.exists() and is_dad_hub_root(resolved),
            "error": error,
        }
        if detail:
            record["detail"] = detail
        attempts.append(record)
        return record

    if explicit_hub is not None:
        record = candidate("explicit_hub", str(explicit_hub))
        if record["is_dad_hub"]:
            return {"resolved": True, "source": "explicit_hub", "hub_path": record["path"], "attempts": attempts}
        return {
            "resolved": False,
            "source": "",
            "hub_path": "",
            "attempts": attempts,
            "error": f"Explicit DAD hub is not a valid DAD hub: {record['path']}",
        }

    for env_name in HUB_ENV_NAMES:
        value = env.get(env_name, "").strip()
        if value:
            record = candidate(env_name, value)
            if record["is_dad_hub"]:
                return {"resolved": True, "source": env_name, "hub_path": record["path"], "attempts": attempts}
            return {
                "resolved": False,
                "source": "",
                "hub_path": "",
                "attempts": attempts,
                "error": f"{env_name} is set but is not a valid DAD hub: {record['path']}",
            }

    locator_info = read_hub_locator(locator)
    locator_attempt = {
        "source": "user_locator",
        "path": locator_info["path"],
        "exists": locator_info["exists"],
        "hub_path": locator_info.get("hub_path", ""),
        "is_dad_hub": bool(locator_info.get("is_dad_hub")),
        "error": locator_info.get("error", ""),
    }
    attempts.append(locator_attempt)
    if locator_attempt["is_dad_hub"]:
        return {
            "resolved": True,
            "source": "user_locator",
            "hub_path": str(locator_info["hub_path"]),
            "locator_path": locator_info["path"],
            "attempts": attempts,
        }

    if allow_current_fallback:
        current = find_repo_root((cwd or Path.cwd()).resolve()).resolve()
        record = candidate("current_dad_repo", str(current))
        if record["is_dad_hub"]:
            return {"resolved": True, "source": "current_dad_repo", "hub_path": record["path"], "attempts": attempts}

    return {
        "resolved": False,
        "source": "",
        "hub_path": "",
        "attempts": attempts,
        "error": (
            "DAD hub unavailable. Set --hub, DAD_HUB, or ~/.dad/hub.json before "
            "running DAD commands outside the hub repo."
        ),
    }


def resolve_hub_root(repo_root: Path | None = None) -> Path:
    resolution = describe_hub_resolution(explicit_hub=repo_root)
    if resolution["resolved"]:
        return Path(str(resolution["hub_path"]))
    raise FileNotFoundError(str(resolution["error"]))


def load_config(path: Path | None = None, repo_root: Path | None = None) -> AppConfig:
    root = resolve_hub_root(repo_root)
    cfg_path = resolve_config_path(root, path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    project = raw.get("project", {})
    db = Path(project.get("database", "state/catalog.sqlite3"))
    data_root, _data_root_mode = resolve_data_root(root)
    db_path = db if db.is_absolute() else data_root / db

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

    github_sources: list[GitHubSource] = []
    for item in raw.get("sources", {}).get("github", []) or []:
        enabled = bool(item.get("enabled", True))
        repositories = _github_repository_rows_from_payload(
            item.get("repositories", item.get("repos", [])) or []
        )
        repositories_file: Path | None = None
        repositories_file_raw = item.get("repositories_file", item.get("repos_file"))
        if repositories_file_raw and enabled:
            repositories_file = _resolve_config_path_value(root, repositories_file_raw)
            repositories.extend(load_github_repositories_file(repositories_file))
        github_sources.append(
            GitHubSource(
                id=str(item["id"]),
                owner=str(item["owner"]),
                enabled=enabled,
                token_env=str(item.get("token_env", "GITHUB_TOKEN")),
                include_private=bool(item.get("include_private", True)),
                include_archived=bool(item.get("include_archived", True)),
                content_mode=str(item.get("content_mode", "priority")),
                max_file_bytes=int(item.get("max_file_bytes", 1_000_000)),
                priority_patterns=list(item.get("priority_patterns", [])),
                repositories=repositories,
                repositories_file=repositories_file,
            )
        )

    mail_repos: list[MailRepoPolicy] = []
    for item in raw.get("mail", {}).get("repos", []) or []:
        raw_path = os.path.expandvars(os.path.expanduser(str(item.get("path", ""))))
        path = Path(raw_path)
        resolved_path = path if path.is_absolute() else root / path
        raw_llos_control_path = str(item.get("llos_control_path", "")).strip()
        llos_control_path = None
        if raw_llos_control_path:
            expanded_control_path = os.path.expandvars(os.path.expanduser(raw_llos_control_path))
            candidate_control_path = Path(expanded_control_path)
            llos_control_path = (
                candidate_control_path
                if candidate_control_path.is_absolute()
                else root / candidate_control_path
            )
        raw_transport_audit_path = str(item.get("transport_audit_path", "")).strip()
        transport_audit_path = None
        if raw_transport_audit_path:
            expanded_audit_path = os.path.expandvars(os.path.expanduser(raw_transport_audit_path))
            candidate_audit_path = Path(expanded_audit_path)
            transport_audit_path = (
                candidate_audit_path
                if candidate_audit_path.is_absolute()
                else root / candidate_audit_path
            )
        repo_id = str(item["id"])
        mail_repos.append(
            MailRepoPolicy(
                id=repo_id,
                path=resolved_path,
                alias=str(item.get("alias") or repo_id),
                llos_control_path=llos_control_path,
                transport_audit_path=transport_audit_path,
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
                approved_approval_ids=[
                    str(value) for value in item.get("approved_approval_ids", []) or []
                ],
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
