"""Inert, content-addressed archives for allowlisted global personal skills."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from jsonschema.validators import validator_for

from .ids import stable_id
from .logos_write_guard import assert_dad_write_allowed
from .transport import data_path, resolve_data_root
from .utils import json_dumps, sha256_bytes, utc_now

SOURCE_MANIFEST_PATH = Path("config/global-personal-skills.json")
ARCHIVE_SURFACE = "personal_skill_archives"
SCHEMA_VERSION = "dad.personal-skills.v1"
AUTHORITY_BOUNDARY = (
    "The live global personal skill root remains source authority. Archive records are inert "
    "candidate evidence, never installed, approved, executable, or a second active source."
)
RUNTIME_PREFIXES = ("agents/", ".codex/", "hooks/", "runtime/")
CACHE_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "target",
    "dist",
    "build",
}
SENSITIVE_PARTS = {
    ".env",
    "credential",
    "credentials",
    "secret",
    "secrets",
    "private",
    "client",
    "matter",
    "conversation",
    "conversations",
    "transcript",
    "transcripts",
    "chain-of-thought",
    "chain_of_thought",
    "hidden-reasoning",
    "hidden_reasoning",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"(?i)(?:api[_-]?key|password|client[_-]?secret|access[_-]?token|refresh[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{8,})"
    ),
)
WINDOWS_ABS = re.compile(r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/][^\r\n\"']+")
UNC_ABS = re.compile(r"(?<!\\)\\\\[^\\/\s]+[\\/][^\r\n\"']+")
POSIX_HOME = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/[^/\s]+(?:/[^\s\"']*)?")
POSIX_ABS = re.compile(r"(?<![A-Za-z0-9_.:/-])/(?!/)[^\s\"'`]+")
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REVISION_ID = re.compile(
    r"^dad:personal-skill-revision:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
PERSONAL_SKILL_ID = re.compile(r"^personal-skill:[a-z0-9][a-z0-9-]*$")
SAFE_METADATA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
SAFE_REVIEWER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,127}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class FileObservation:
    relative_path: str
    content_sha256: str
    size: int
    role: str
    data: bytes = field(repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillObservation:
    skill_id: str
    name: str
    source_relative_path: str
    source_absolute_path_hint: str
    source_runtime: str
    status: str
    tree_sha256: str = ""
    revision_id: str = ""
    files: tuple[FileObservation, ...] = ()
    issues: tuple[dict[str, str], ...] = ()
    excluded: tuple[dict[str, str], ...] = ()

    def public(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "source_relative_path": self.source_relative_path,
            "source_runtime": self.source_runtime,
            "status": self.status,
            "tree_sha256": self.tree_sha256,
            "revision_id": self.revision_id,
            "file_count": len(self.files),
            "total_bytes": sum(row.size for row in self.files),
            "issues": list(self.issues),
            "excluded": list(self.excluded),
            "authority": "active_personal_source",
            "review_status": "source_observation",
        }


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _validate(hub: Path, schema_name: str, payload: dict[str, Any]) -> None:
    registry = _json(hub / "registry/schema-registry.json")
    schema = _json(hub / str(registry["schemas"][schema_name]))
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema).validate(payload)


def load_source_manifest(hub: Path, path: Path | None = None) -> dict[str, Any]:
    payload = _json(path or hub / SOURCE_MANIFEST_PATH)
    _validate(hub, "personal_skill_source_manifest", payload)
    skill_ids = [str(row["skill_id"]) for row in payload["skills"]]
    source_paths = [str(row["source_path"]).casefold() for row in payload["skills"]]
    if len(skill_ids) != len(set(skill_ids)):
        raise ValueError("Personal skill manifest contains duplicate skill_id values")
    if len(source_paths) != len(set(source_paths)):
        raise ValueError(
            "Personal skill manifest contains duplicate case-insensitive source_path values"
        )
    if not SAFE_SEGMENT.fullmatch(str(payload["source_runtime"])):
        raise ValueError("source_runtime must be one portable path segment")
    return payload


def resolve_source_root(
    manifest: dict[str, Any], *, source_root: Path | None = None, env: dict[str, str] | None = None
) -> Path:
    if source_root is not None:
        return source_root.resolve()
    variables = os.environ if env is None else env
    home = (
        Path(str(variables.get("CODEX_HOME", "")).strip())
        if str(variables.get("CODEX_HOME", "")).strip()
        else Path.home() / ".codex"
    )
    return (home / str(manifest.get("source_root_relative", "skills"))).resolve()


def archive_root(hub: Path, *, env: dict[str, str] | None = None) -> Path:
    return data_path(hub, ARCHIVE_SURFACE, env=env)


def _assert_archive_disjoint(source: Path, archive: Path) -> None:
    source_resolved = source.resolve()
    archive_resolved = archive.resolve(strict=False)
    if (
        source_resolved == archive_resolved
        or archive_resolved.is_relative_to(source_resolved)
        or source_resolved.is_relative_to(archive_resolved)
    ):
        raise RuntimeError(
            "Personal skill archive must be disjoint from the active global skill source root"
        )


def _link_like(path: Path) -> bool:
    try:
        junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(junction and junction())
    except OSError:
        return True


def _source_name(value: str) -> str:
    path = Path(value)
    if (
        path.is_absolute()
        or len(path.parts) != 1
        or value in {"", ".", ".."}
        or "/" in value
        or "\\" in value
    ):
        raise ValueError(f"source_path must be one direct-child name: {value!r}")
    return value


def _path_reason(relative: Path, manifest: dict[str, Any]) -> tuple[str, bool] | None:
    parts = tuple(part.casefold() for part in relative.parts)
    cache = CACHE_PARTS | {str(value).casefold() for value in manifest.get("deny_path_parts", [])}
    if any(part in cache or part.startswith(".tmp") for part in parts):
        return "generated_or_cache_path", False
    normalized_parts = tuple(re.sub(r"[^a-z0-9]+", "-", part).strip("-") for part in parts)
    sensitive_markers = {
        re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        for value in SENSITIVE_PARTS
    }
    if any(
        any(f"-{marker}-" in f"-{part}-" for marker in sensitive_markers)
        for part in normalized_parts
    ):
        return "private_or_sensitive_path", True
    if any(part.startswith(".") for part in parts):
        return "hidden_path", False
    return None


def _file_identity(value: os.stat_result) -> tuple[int, int, int]:
    return value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode)


def _read_regular_file(path: Path, source_directory: Path, max_file: int) -> tuple[bytes, str]:
    try:
        path.resolve(strict=True).relative_to(source_directory.resolve())
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            return b"", "link_or_not_regular"
        if before.st_size > max_file:
            return b"", "file_too_large"
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(path), flags)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(before):
                return b"", "path_identity_changed_before_read"
            with os.fdopen(fd, "rb", closefd=False) as handle:
                data = handle.read(max_file + 1)
            after_open = os.fstat(fd)
        finally:
            os.close(fd)
        after_path = path.lstat()
    except (OSError, ValueError):
        return b"", "unreadable_or_escaped"
    if len(data) > max_file:
        return b"", "file_too_large"
    if (
        _file_identity(before) != _file_identity(after_open)
        or _file_identity(before) != _file_identity(after_path)
        or (before.st_size, before.st_mtime_ns) != (after_open.st_size, after_open.st_mtime_ns)
        or (before.st_size, before.st_mtime_ns)
        != (after_path.st_size, after_path.st_mtime_ns)
    ):
        return b"", "changed_during_read"
    return data, ""


def _content_issue(data: bytes, relative: str, text_extensions: set[str]) -> str:
    if (
        Path(relative).suffix.casefold() not in text_extensions
        and Path(relative).name != "SKILL.md"
    ):
        return "unsupported_or_binary_file"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "non_utf8_content"
    return "secret_like_content" if any(pattern.search(text) for pattern in SECRET_PATTERNS) else ""


def _tree_hash(files: list[FileObservation]) -> str:
    digest = hashlib.sha256()
    for row in sorted(files, key=lambda value: value.relative_path):
        digest.update(f"{row.relative_path}\0{row.content_sha256}\0{row.size}\n".encode("utf-8"))
    return digest.hexdigest()


def _observe(root: Path, skill: dict[str, Any], manifest: dict[str, Any]) -> SkillObservation:
    name = _source_name(str(skill["source_path"]))
    directory = root / name
    common = {
        "skill_id": str(skill["skill_id"]),
        "name": str(skill["name"]),
        "source_relative_path": name,
        "source_absolute_path_hint": str(directory),
        "source_runtime": str(skill.get("source_runtime", manifest["source_runtime"])),
    }
    if not directory.exists():
        return SkillObservation(**common, status="missing")
    if not directory.is_dir() or _link_like(directory):
        return SkillObservation(
            **common,
            status="unsafe",
            issues=({"path": name, "reason": "source_link_or_not_directory"},),
        )
    try:
        directory.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return SkillObservation(
            **common, status="unsafe", issues=({"path": name, "reason": "source_escape"},)
        )
    max_file, max_total = int(manifest["max_file_bytes"]), int(manifest["max_skill_bytes"])
    text_ext = {str(value).casefold() for value in manifest["text_extensions"]}
    files: list[FileObservation] = []
    issues: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    total = 0
    for current, dirs, names in os.walk(directory, topdown=True, followlinks=False):
        base = Path(current)
        keep: list[str] = []
        for child in sorted(dirs):
            path = base / child
            rel = path.relative_to(directory)
            reason = _path_reason(rel, manifest)
            if _link_like(path):
                issues.append({"path": rel.as_posix(), "reason": "link_or_junction"})
            elif reason:
                excluded.append({"path": rel.as_posix(), "reason": reason[0]})
                if reason[1]:
                    issues.append({"path": rel.as_posix(), "reason": reason[0]})
            else:
                keep.append(child)
        dirs[:] = keep
        for child in sorted(names):
            path = base / child
            rel = path.relative_to(directory)
            rel_text = rel.as_posix()
            reason = _path_reason(rel, manifest)
            if reason:
                excluded.append({"path": rel_text, "reason": reason[0]})
                if reason[1]:
                    issues.append({"path": rel_text, "reason": reason[0]})
                continue
            if _link_like(path):
                issues.append({"path": rel_text, "reason": "link_or_junction"})
                continue
            if rel_text.casefold() in seen:
                issues.append({"path": rel_text, "reason": "duplicate_normalized_path"})
                continue
            seen.add(rel_text.casefold())
            data, read_issue = _read_regular_file(path, directory, max_file)
            if read_issue:
                issues.append({"path": rel_text, "reason": read_issue})
                continue
            total += len(data)
            if total > max_total:
                issues.append({"path": name, "reason": "skill_too_large"})
                continue
            content_issue = _content_issue(data, rel_text, text_ext)
            if content_issue:
                issues.append({"path": rel_text, "reason": content_issue})
                continue
            role = (
                "runtime_adapter"
                if rel_text.casefold().startswith(RUNTIME_PREFIXES)
                or Path(rel_text).name.casefold() == "openai.yaml"
                else "portable_procedure"
            )
            files.append(
                FileObservation(
                    relative_path=rel_text,
                    content_sha256=sha256_bytes(data),
                    size=len(data),
                    role=role,
                    data=data,
                )
            )
    if not any(row.relative_path == "SKILL.md" for row in files):
        issues.append({"path": "SKILL.md", "reason": "missing_required_entrypoint"})
    if issues:
        return SkillObservation(
            **common,
            status="unsafe",
            issues=tuple(sorted(issues, key=lambda row: (row["path"], row["reason"]))),
            excluded=tuple(excluded),
        )
    tree = _tree_hash(files)
    return SkillObservation(
        **common,
        status="active",
        tree_sha256=tree,
        revision_id=stable_id("personal-skill-revision", str(skill["skill_id"]), tree),
        files=tuple(sorted(files, key=lambda row: row.relative_path)),
        excluded=tuple(excluded),
    )


def _observations(
    hub: Path,
    *,
    source_root: Path | None = None,
    manifest_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[dict[str, Any], Path, list[SkillObservation], list[dict[str, str]]]:
    manifest = load_source_manifest(hub, manifest_path)
    root = resolve_source_root(manifest, source_root=source_root, env=env)
    if not root.is_dir() or _link_like(root):
        raise ValueError("Global skill source root is missing, not a directory, or link-like")
    denied = {str(value).casefold() for value in manifest["deny_skill_names"]}
    rows: list[SkillObservation] = []
    for skill in manifest["skills"]:
        name = _source_name(str(skill["source_path"]))
        deny_wins = name.casefold() in denied
        paused = str(skill["status"]) == "paused"
        if deny_wins or paused:
            rows.append(
                SkillObservation(
                    skill_id=str(skill["skill_id"]),
                    name=str(skill["name"]),
                    source_relative_path=name,
                    source_absolute_path_hint=str(root / name),
                    source_runtime=str(skill.get("source_runtime", manifest["source_runtime"])),
                    status="unsafe" if deny_wins else "paused",
                    issues=({"path": name, "reason": "explicit_deny_wins"},) if deny_wins else (),
                )
            )
            continue
        rows.append(_observe(root, skill, manifest))
    allowed = {row.source_relative_path.casefold() for row in rows}
    unknown = [
        {
            "source_relative_path": child.name,
            "status": "unknown_origin",
            "reason": "not_in_explicit_personal_skill_allowlist",
        }
        for child in sorted(root.iterdir(), key=lambda item: item.name.casefold())
        if child.is_dir() and child.name.casefold() not in allowed | denied
    ]
    return manifest, root, rows, unknown


def inventory(
    hub: Path,
    *,
    source_root: Path | None = None,
    manifest_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    manifest, root, rows, unknown = _observations(
        hub, source_root=source_root, manifest_path=manifest_path, env=env
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "source_runtime": manifest["source_runtime"],
        "source_root_kind": manifest["source_root_kind"],
        "source_root_private_hint": str(root),
        "active_skill_count": sum(row.status == "active" for row in rows),
        "unsafe_skill_count": sum(row.status == "unsafe" for row in rows),
        "missing_skill_count": sum(row.status == "missing" for row in rows),
        "unknown_origin_count": len(unknown),
        "skills": [row.public() for row in rows],
        "unknown_origins": unknown,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "local_paths_private": True,
    }


def _read_jsonl(path: Path, *, root: Path | None = None) -> list[dict[str, Any]]:
    if root is not None:
        path = _safe_archive_output(root, path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupt JSONL record at {path.name}:{line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Non-object JSONL record at {path.name}:{line_number}")
        rows.append(value)
    return rows


def _key(value: str) -> str:
    return value.split(":")[-1]


def _pointer(root: Path, skill_id: str) -> Path:
    path = root / "skills" / _key(stable_id("personal-skill-key", skill_id)) / "current.json"
    return _safe_archive_output(root, path)


def _contained(root: Path, path: Path) -> Path:
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError("Archive identifier escaped its namespace")
    return path



def _reparse_like(path: Path) -> bool:
    if _link_like(path):
        return True
    try:
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return True
    return bool(attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def _safe_archive_output(root: Path, path: Path) -> Path:
    """Reject archive writes through links, junctions, reparse points, or escapes."""
    root_absolute = Path(os.path.abspath(root))
    path_absolute = Path(os.path.abspath(path))
    if not path_absolute.is_relative_to(root_absolute):
        raise RuntimeError("Archive output escaped its namespace")

    # The reviewed surface is <data-root>/private/personal-skills. Include the
    # data root itself so a first run cannot create through a redirected
    # `private` ancestor.
    boundary = root_absolute.parents[1] if len(root_absolute.parents) >= 2 else root_absolute
    candidates: list[Path] = []
    current = path_absolute
    while True:
        candidates.append(current)
        if current == boundary:
            break
        if current.parent == current or not current.is_relative_to(boundary):
            raise RuntimeError("Archive output boundary is invalid")
        current = current.parent

    for candidate in reversed(candidates):
        if os.path.lexists(candidate) and _reparse_like(candidate):
            raise RuntimeError(f"Archive output contains a link or reparse point: {candidate.name}")

    resolved_root = root_absolute.resolve(strict=False)
    resolved_path = path_absolute.resolve(strict=False)
    if not resolved_path.is_relative_to(resolved_root):
        raise RuntimeError("Archive output resolved outside its namespace")
    return path_absolute


def _prepare_archive_parent(root: Path, path: Path) -> Path:
    safe = _safe_archive_output(root, path)
    safe.parent.mkdir(parents=True, exist_ok=True)
    _safe_archive_output(root, safe.parent)
    return _safe_archive_output(root, safe)



def _prepare_archive_directory(root: Path, path: Path) -> Path:
    safe = _safe_archive_output(root, path)
    safe.mkdir(parents=True, exist_ok=True)
    return _safe_archive_output(root, safe)


def _write_archive_json(root: Path, path: Path, value: dict[str, Any]) -> None:
    _write_bytes(root, path, (json_dumps(value, pretty=True) + "\n").encode("utf-8"))


def _append_archive_jsonl(root: Path, path: Path, value: dict[str, Any]) -> None:
    safe = _safe_archive_output(root, path)
    existing = b""
    if os.path.lexists(safe):
        if not safe.is_file() or _reparse_like(safe):
            raise RuntimeError(f"Archive append target is not a regular file: {safe.name}")
        existing = safe.read_bytes()
        if existing and not existing.endswith(b"\n"):
            raise ValueError(f"Corrupt append-only archive log: {safe.name}")
    payload = existing + (json_dumps(value) + "\n").encode("utf-8")
    _write_bytes(root, safe, payload)

def _revision(root: Path, revision_id: str) -> Path:
    if not REVISION_ID.fullmatch(revision_id):
        raise ValueError("Invalid personal skill revision ID")
    key = _key(revision_id)
    return _safe_archive_output(root, root / "revisions" / key[:2] / key / "revision.json")


def _blob(root: Path, digest: str) -> Path:
    if not SHA256_HEX.fullmatch(digest):
        raise ValueError("Invalid personal skill blob digest")
    return _safe_archive_output(root, root / "blobs/sha256" / digest[:2] / digest)


def _safe_member(name: str) -> str:
    member = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or member.is_absolute()
        or any(part in {"", ".", ".."} for part in member.parts)
        or WINDOWS_ABS.search(name)
    ):
        raise ValueError(f"Unsafe portable bundle member: {name!r}")
    return member.as_posix()


def _write_bytes(root: Path, path: Path, data: bytes) -> None:
    path = _prepare_archive_parent(root, path)
    assert_dad_write_allowed(path)
    if os.path.lexists(path) and not path.is_file():
        raise RuntimeError(f"Archive output target is not a regular file: {path.name}")
    _safe_archive_output(root, path.parent)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _safe_archive_output(root, path)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


@contextmanager
def _lock(root: Path) -> Iterator[None]:
    path = _prepare_archive_parent(root, root / ".snapshot.lock")
    assert_dad_write_allowed(path)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags)
    except FileExistsError as exc:
        raise RuntimeError("Personal skill snapshot already running") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise RuntimeError("Personal skill snapshot lock is not a regular file")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json_dumps({"pid": os.getpid(), "created_at": utc_now()}))
        yield
    finally:
        _safe_archive_output(root, path)
        path.unlink(missing_ok=True)


def _current(root: Path, skill_id: str) -> dict[str, Any]:
    path = _pointer(root, skill_id)
    return _json(path) if path.exists() else {}


def _revision_invariant(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "schema_version",
            "revision_id",
            "skill_id",
            "artifact_role",
            "tree_sha256",
            "files",
            "status",
            "validation_status",
            "review_status",
            "authority_boundary",
        )
    }


def _load_revision(hub: Path, root: Path, revision_id: str) -> dict[str, Any]:
    record = _json(_revision(root, revision_id))
    _validate(hub, "personal_skill_revision", record)
    if record["revision_id"] != revision_id:
        raise ValueError("Stored revision ID does not match its requested identity")
    if not SAFE_SEGMENT.fullmatch(str(record["source_runtime"])):
        raise ValueError("Stored source runtime is not a portable path segment")
    digest = hashlib.sha256()
    seen: set[str] = set()
    for file in sorted(record["files"], key=lambda item: str(item["relative_path"])):
        relative = _safe_member(str(file["relative_path"]))
        if relative.casefold() in seen:
            raise ValueError("Stored revision has duplicate normalized file paths")
        seen.add(relative.casefold())
        blob_digest = str(file["blob_sha256"])
        blob = _blob(root, blob_digest).read_bytes()
        if len(blob) != int(file["size"]) or sha256_bytes(blob) != blob_digest:
            raise ValueError(f"Stored blob failed integrity validation: {blob_digest}")
        digest.update(f"{relative}\0{blob_digest}\0{int(file['size'])}\n".encode("utf-8"))
    tree_hash = digest.hexdigest()
    if tree_hash != record["tree_sha256"]:
        raise ValueError("Stored revision tree hash is invalid")
    expected_id = stable_id("personal-skill-revision", str(record["skill_id"]), tree_hash)
    if expected_id != revision_id:
        raise ValueError("Stored revision identity does not match skill and tree content")
    return record


def status(
    hub: Path,
    *,
    source_root: Path | None = None,
    manifest_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    manifest, _source, rows, unknown = _observations(
        hub, source_root=source_root, manifest_path=manifest_path, env=env
    )
    root = archive_root(hub, env=env)
    changes: list[dict[str, Any]] = []
    for row in rows:
        pointer = _current(root, row.skill_id)
        prior = str(pointer.get("current_revision_id", ""))
        change = (
            row.status
            if row.status != "active"
            else "new"
            if not prior
            else "changed"
            if prior != row.revision_id
            else "unchanged"
        )
        changes.append(
            {
                **row.public(),
                "change": change,
                "previous_revision_id": prior,
                "last_observed_at": str(pointer.get("last_observed_at", "")),
            }
        )
    observed_ids = {row.skill_id for row in rows}
    _safe_archive_output(root, root / "skills")
    for pointer_path in sorted(root.glob("skills/*/current.json")):
        pointer = _json(_safe_archive_output(root, pointer_path))
        pointer_skill_id = str(pointer.get("skill_id", ""))
        if pointer_skill_id in observed_ids:
            continue
        pointer_status = str(pointer.get("status", "unknown"))
        changes.append(
            {
                "skill_id": pointer_skill_id,
                "name": pointer_skill_id,
                "source_relative_path": str(pointer.get("source_relative_path", "unknown")),
                "source_runtime": str(pointer.get("source_runtime", "unknown")),
                "status": "not_allowlisted",
                "tree_sha256": str(pointer.get("tree_sha256", "")),
                "revision_id": str(pointer.get("current_revision_id", "")),
                "file_count": 0,
                "total_bytes": 0,
                "issues": [{"reason": "not_in_current_allowlist"}],
                "excluded": [],
                "authority": "historical_personal_source_pointer",
                "review_status": "source_observation",
                "change": "unchanged" if pointer_status == "not_allowlisted" else "not_allowlisted",
                "previous_revision_id": str(pointer.get("current_revision_id", "")),
                "last_observed_at": str(pointer.get("last_observed_at", "")),
            }
        )
    delta = [row for row in changes if row["change"] != "unchanged"]
    runs = _read_jsonl(root / "runs.jsonl", root=root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "data_root_mode": resolve_data_root(hub, env=env)[1],
        "changes": changes,
        "unknown_origins": unknown,
        "last_run": runs[-1] if runs else None,
        "delta_count": len(delta),
        "needs_steward_review": bool(delta or unknown),
        "recommended_steward_tier": "luna_low" if delta or unknown else "none",
        "terra_escalation": "integration_or_portability_ambiguity_only",
        "sol_escalation": "unresolved_load_bearing_architecture_only",
        "ultra_effort": "explicit_human_permission_per_attempt_required",
        "source_manifest_id": manifest["manifest_id"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def snapshot(
    hub: Path,
    *,
    source_root: Path | None = None,
    manifest_path: Path | None = None,
    env: dict[str, str] | None = None,
    allow_legacy_write: bool = False,
    observed_at: str | None = None,
) -> dict[str, Any]:
    manifest, source, rows, unknown = _observations(
        hub, source_root=source_root, manifest_path=manifest_path, env=env
    )
    _data_root, mode = resolve_data_root(hub, env=env)
    if mode != "data_root" and not allow_legacy_write:
        raise RuntimeError(
            "Snapshot write requires initialized DAD_DATA_ROOT; status/query retain legacy fallback"
        )
    root = archive_root(hub, env=env)
    _assert_archive_disjoint(source, root)
    timestamp = observed_at or utc_now()
    manifest_hash = sha256_bytes(json_dumps(manifest).encode("utf-8"))
    observation_hash = sha256_bytes(
        json_dumps([row.public() for row in rows] + unknown).encode("utf-8")
    )
    with _lock(root):
        prior_runs = _read_jsonl(root / "runs.jsonl", root=root)
        pointers = {row.skill_id: _current(root, row.skill_id) for row in rows}
        observed_ids = set(pointers)
        orphan_pointers = [
            _json(_safe_archive_output(root, path))
            for path in sorted(root.glob("skills/*/current.json"))
            if str(_json(_safe_archive_output(root, path)).get("skill_id", "")) not in observed_ids
        ]
        prior_state = [
            {
                "skill_id": skill_id,
                "status": pointer.get("status", "unknown"),
                "current_revision_id": pointer.get("current_revision_id", ""),
            }
            for skill_id, pointer in sorted(pointers.items())
        ] + [
            {
                "skill_id": str(pointer.get("skill_id", "")),
                "status": pointer.get("status", "unknown"),
                "current_revision_id": pointer.get("current_revision_id", ""),
            }
            for pointer in sorted(orphan_pointers, key=lambda item: str(item.get("skill_id", "")))
        ]
        state_hash = sha256_bytes(json_dumps(prior_state).encode("utf-8"))
        run_id = stable_id(
            "personal-skill-run",
            timestamp,
            manifest_hash,
            observation_hash,
            state_hash,
            str(len(prior_runs) + 1),
        )
        entries: list[dict[str, Any]] = []
        revision_records: dict[str, dict[str, Any]] = {}
        pointer_records: dict[str, dict[str, Any]] = {}

        for row in rows:
            pointer = pointers[row.skill_id]
            prior = str(pointer.get("current_revision_id", ""))
            if row.status != "active":
                entries.append(
                    {
                        "skill_id": row.skill_id,
                        "event_type": row.status,
                        "observed_at": timestamp,
                        "run_id": run_id,
                        "previous_revision_id": prior,
                        "revision_id": "",
                        "source_relative_path": row.source_relative_path,
                        "source_runtime": row.source_runtime,
                        "validation_status": "blocked_unsafe"
                        if row.status == "unsafe"
                        else "not_observed",
                        "issues": list(row.issues),
                    }
                )
                pointer_records[row.skill_id] = {
                    "schema_version": SCHEMA_VERSION,
                    "skill_id": row.skill_id,
                    "status": row.status,
                    "current_revision_id": prior,
                    "last_observed_at": timestamp,
                    "source_relative_path": row.source_relative_path,
                    "source_absolute_path_hint": row.source_absolute_path_hint,
                    "source_runtime": row.source_runtime,
                    "local_paths_private": True,
                    "authority_boundary": AUTHORITY_BOUNDARY,
                }
                continue

            record = {
                "schema_version": SCHEMA_VERSION,
                "revision_id": row.revision_id,
                "skill_id": row.skill_id,
                "artifact_role": "source_snapshot",
                "tree_sha256": row.tree_sha256,
                "archived_at": timestamp,
                "source_runtime": row.source_runtime,
                "source_relative_path": row.source_relative_path,
                "source_absolute_path_hint": row.source_absolute_path_hint,
                "source_manifest_id": manifest["manifest_id"],
                "source_manifest_sha256": manifest_hash,
                "run_id": run_id,
                "local_paths_private": True,
                "files": [
                    {
                        "relative_path": file.relative_path,
                        "blob_sha256": file.content_sha256,
                        "size": file.size,
                        "role": file.role,
                    }
                    for file in row.files
                ],
                "status": "archived",
                "validation_status": "safe_snapshot",
                "review_status": "source_observation",
                "authority_boundary": AUTHORITY_BOUNDARY,
            }
            _validate(hub, "personal_skill_revision", record)
            revision_records[row.revision_id] = record
            event_type = (
                "unchanged" if prior == row.revision_id else "created" if not prior else "revised"
            )
            entries.append(
                {
                    "skill_id": row.skill_id,
                    "event_type": event_type,
                    "observed_at": timestamp,
                    "run_id": run_id,
                    "previous_revision_id": prior,
                    "revision_id": row.revision_id,
                    "source_relative_path": row.source_relative_path,
                    "source_runtime": row.source_runtime,
                    "validation_status": "safe_snapshot",
                    "issues": [],
                }
            )
            pointer_records[row.skill_id] = {
                "schema_version": SCHEMA_VERSION,
                "skill_id": row.skill_id,
                "status": "active",
                "current_revision_id": row.revision_id,
                "tree_sha256": row.tree_sha256,
                "last_observed_at": timestamp,
                "source_relative_path": row.source_relative_path,
                "source_absolute_path_hint": row.source_absolute_path_hint,
                "source_runtime": row.source_runtime,
                "local_paths_private": True,
                "authority_boundary": AUTHORITY_BOUNDARY,
            }

        for pointer in orphan_pointers:
            skill_id = str(pointer.get("skill_id", ""))
            prior = str(pointer.get("current_revision_id", ""))
            entries.append(
                {
                    "skill_id": skill_id,
                    "event_type": "not_allowlisted",
                    "observed_at": timestamp,
                    "run_id": run_id,
                    "previous_revision_id": prior,
                    "revision_id": "",
                    "source_relative_path": str(pointer.get("source_relative_path", "unknown")),
                    "source_runtime": str(pointer.get("source_runtime", "unknown")),
                    "validation_status": "not_observed",
                    "issues": [{"reason": "not_in_current_allowlist"}],
                }
            )
            pointer_records[skill_id] = {
                **pointer,
                "status": "not_allowlisted",
                "last_observed_at": timestamp,
            }

        run = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "run_kind": "snapshot",
            "observed_at": timestamp,
            "data_root_mode": mode,
            "source_manifest_id": manifest["manifest_id"],
            "source_manifest_sha256": manifest_hash,
            "entries": entries,
            "unknown_origins": unknown,
            "status": "needs_review"
            if unknown or any(row["event_type"] in {"unsafe", "not_allowlisted"} for row in entries)
            else "complete",
            "review_status": "candidate_observation",
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        _validate(hub, "personal_skill_run", run)
        run_path = _safe_archive_output(root, root / "runs" / f"{_key(run_id)}.json")
        # Validate every mutable output namespace before the first immutable
        # write so a redirected log, pointer, or graph cannot leave a partial
        # snapshot transaction.
        _safe_archive_output(root, root / "runs.jsonl")
        _safe_archive_output(root, root / "events.jsonl")
        _safe_archive_output(root, root / "graph.json")
        if run_path.exists():
            raise RuntimeError(f"Run collision: {run_id}")

        for skill_id in pointer_records:
            _pointer(root, skill_id)

        for row in rows:
            if row.status != "active":
                continue
            for file in row.files:
                path = _blob(root, file.content_sha256)
                if path.exists():
                    existing = path.read_bytes()
                    if len(existing) != file.size or sha256_bytes(existing) != file.content_sha256:
                        raise RuntimeError(f"Blob collision or corruption: {file.content_sha256}")
            record = revision_records[row.revision_id]
            path = _revision(root, row.revision_id)
            if path.exists():
                existing = _load_revision(hub, root, row.revision_id)
                if _revision_invariant(existing) != _revision_invariant(record):
                    raise RuntimeError(f"Revision collision: {row.revision_id}")

        for row in rows:
            if row.status != "active":
                continue
            for file in row.files:
                path = _blob(root, file.content_sha256)
                if not path.exists():
                    _write_bytes(root, path, file.data)
            path = _revision(root, row.revision_id)
            if not path.exists():
                _write_archive_json(root, path, revision_records[row.revision_id])

        _write_archive_json(root, run_path, run)
        _append_archive_jsonl(root, root / "runs.jsonl", run)
        for event in entries:
            _append_archive_jsonl(root, root / "events.jsonl", event)
        for skill_id, pointer in pointer_records.items():
            _write_archive_json(root, _pointer(root, skill_id), pointer)

    build_graph(hub, env=env, manifest=manifest, observations=rows)
    return run


def list_archive(hub: Path, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    root = archive_root(hub, env=env)
    revisions = []
    for path in sorted(root.glob("revisions/*/*/revision.json")):
        raw = _json(_safe_archive_output(root, path))
        revisions.append(_load_revision(hub, root, str(raw.get("revision_id", ""))))
    revisions.sort(
        key=lambda row: (str(row["skill_id"]), str(row["archived_at"]), str(row["revision_id"]))
    )
    pointers = sorted(
        (_json(_safe_archive_output(root, path)) for path in root.glob("skills/*/current.json")),
        key=lambda row: str(row["skill_id"]),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "active_sources": pointers,
        "archived_revisions": revisions,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "local_paths_private": True,
    }


def query_archive(
    hub: Path,
    *,
    health: str = "",
    artifact_role: str = "",
    skill_id: str = "",
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = list_archive(hub, env=env)
    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    pointers_by_skill = {str(row["skill_id"]): row for row in payload["active_sources"]}
    revision_skills: set[str] = set()
    revisions_by_hash: dict[str, list[dict[str, Any]]] = {}
    source_path_to_skill: dict[str, str] = {}

    def selected(row: dict[str, Any]) -> bool:
        flags = set(row.get("health_flags", [row.get("health", "")]))
        return not (
            (health and health not in flags)
            or (artifact_role and row.get("artifact_role") != artifact_role)
            or (skill_id and row.get("skill_id") != skill_id)
        )

    for revision in payload["archived_revisions"]:
        revision_skill = str(revision["skill_id"])
        revision_skills.add(revision_skill)
        revisions_by_hash.setdefault(str(revision["tree_sha256"]), []).append(revision)
        source_path_to_skill.setdefault(
            str(revision["source_relative_path"]).casefold(), revision_skill
        )
        pointer = pointers_by_skill.get(revision_skill, {})
        try:
            age = (
                now - datetime.fromisoformat(str(pointer.get("last_observed_at", "")))
            ).total_seconds() / 86400
        except ValueError:
            age = 10**9
        is_current = pointer.get("current_revision_id") == revision["revision_id"]
        flags: list[str] = []
        if is_current and pointer.get("status") == "unsafe":
            flags.append("unsafe")
        if not is_current:
            flags.append("historical")
        if is_current and age > 30:
            flags.append("stale")
        if revision.get("review_status") != "reviewed":
            flags.append("unvalidated")
        if not flags:
            flags.append("current")
        row = {
            **revision,
            "health": flags[0],
            "health_flags": flags,
            "pointer_status": pointer.get("status", "unknown"),
        }
        if selected(row):
            results.append(row)

    for pointer in payload["active_sources"]:
        pointer_skill_id = str(pointer["skill_id"])
        if pointer_skill_id in revision_skills:
            continue
        pointer_status = str(pointer.get("status", "unknown"))
        pointer_health = (
            "unsafe"
            if pointer_status == "unsafe"
            else "stale"
            if pointer_status in {"missing", "not_allowlisted"}
            else "paused"
            if pointer_status == "paused"
            else "unvalidated"
        )
        row = {
            **pointer,
            "artifact_role": "active_personal_source",
            "health": pointer_health,
            "health_flags": [pointer_health],
            "pointer_status": pointer_status,
            "revision_id": "",
        }
        if selected(row):
            results.append(row)

    registry = _json(hub / "registry/agent-skill-library.json")
    manifest = load_source_manifest(hub)
    for source in manifest["skills"]:
        source_path_to_skill[str(source["source_path"]).casefold()] = str(source["skill_id"])
    for registered in registry.get("skills", []):
        for evidence in registered.get("source_evidence", []):
            prefix = "personal-skill-source:"
            if not str(evidence).startswith(prefix):
                continue
            source_skill = source_path_to_skill.get(str(evidence)[len(prefix) :].casefold(), "")
            if not source_skill:
                continue
            row = {
                "skill_id": source_skill,
                "revision_id": "",
                "artifact_role": "dad_adaptation",
                "adaptation_skill_id": registered["skill_id"],
                "relation": "adapted_as",
                "health": "unvalidated",
                "health_flags": ["unvalidated"],
                "review_status": registered.get("review_status", "candidate"),
                "authority_boundary": "A registered adaptation is not an archived source revision or active installation.",
            }
            if selected(row):
                results.append(row)

    for group in revisions_by_hash.values():
        ordered = sorted(group, key=lambda row: str(row["revision_id"]))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                for source, other in ((left, right), (right, left)):
                    row = {
                        "skill_id": source["skill_id"],
                        "revision_id": source["revision_id"],
                        "artifact_role": "duplicate_content_relation",
                        "other_skill_id": other["skill_id"],
                        "other_revision_id": other["revision_id"],
                        "tree_sha256": source["tree_sha256"],
                        "relation": "duplicate_content_of",
                        "health": "unvalidated",
                        "health_flags": ["unvalidated"],
                        "review_status": "candidate",
                        "authority_boundary": "Exact content equality does not transfer authority or approval.",
                    }
                    if selected(row):
                        results.append(row)

    root = archive_root(hub, env=env)
    runs = _read_jsonl(root / "runs.jsonl", root=root)
    for unknown in runs[-1].get("unknown_origins", []) if runs else []:
        row = {
            **unknown,
            "skill_id": "",
            "revision_id": "",
            "artifact_role": "unknown_source_observation",
            "health": "unknown_origin",
            "health_flags": ["unknown_origin"],
            "pointer_status": "unknown_origin",
        }
        if selected(row):
            results.append(row)
    results.sort(
        key=lambda row: (
            str(row.get("skill_id", "")),
            str(row.get("revision_id", "")),
            str(row.get("artifact_role", "")),
            str(row.get("source_relative_path", "")),
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "filters": {"health": health, "artifact_role": artifact_role, "skill_id": skill_id},
        "results": results,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _portable(data: bytes, roots: list[str]) -> tuple[bytes, list[str]]:
    text = data.decode("utf-8")
    redactions: list[str] = []
    for root in sorted({value for value in roots if value}, key=len, reverse=True):
        for variant in {root, root.replace("\\", "/")}:
            if variant in text:
                text = text.replace(variant, "${LOCAL_SOURCE_ROOT}")
                redactions.append("local_source_root")
    if WINDOWS_ABS.search(text) or UNC_ABS.search(text) or POSIX_ABS.search(text):
        raise ValueError("Portable export contains an absolute local path")
    return text.encode("utf-8"), sorted(set(redactions))


def export_portable(
    hub: Path,
    *,
    skill_id: str,
    target_runtime: str,
    reviewed_by: str,
    approval_id: str,
    revision_id: str = "",
    include_source_runtime_adapter: bool = False,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not PERSONAL_SKILL_ID.fullmatch(skill_id):
        raise ValueError("Invalid personal skill ID")
    if not SAFE_SEGMENT.fullmatch(target_runtime):
        raise ValueError("target_runtime must be one portable path segment")
    if not SAFE_REVIEWER.fullmatch(reviewed_by):
        raise ValueError("reviewed_by contains unsupported or path-like characters")
    if not SAFE_METADATA.fullmatch(approval_id):
        raise ValueError("approval_id contains unsupported or path-like characters")
    root = archive_root(hub, env=env)
    selected = revision_id or str(_current(root, skill_id).get("current_revision_id", ""))
    if not selected:
        raise ValueError(f"No archived revision for {skill_id}")
    revision = _load_revision(hub, root, selected)
    if revision["skill_id"] != skill_id:
        raise ValueError("Requested skill ID does not own the selected revision")
    source_manifest = load_source_manifest(hub)
    source_hint = Path(str(revision["source_absolute_path_hint"]))
    _assert_archive_disjoint(source_hint.parent, root)
    _assert_archive_disjoint(resolve_source_root(source_manifest), root)
    roots = [
        str(Path.home()),
        str(resolve_source_root(source_manifest)),
        str(source_hint),
        str(source_hint.parent),
    ]
    files: list[tuple[str, bytes]] = []
    file_rows: list[dict[str, Any]] = []
    omitted: list[str] = []
    redactions: list[dict[str, Any]] = []
    for row in revision["files"]:
        if row["role"] == "runtime_adapter" and not include_source_runtime_adapter:
            omitted.append(row["relative_path"])
            continue
        blob = _blob(root, str(row["blob_sha256"])).read_bytes()
        data, applied = _portable(blob, roots)
        destination = (
            f"adapters/{revision['source_runtime']}/{row['relative_path']}"
            if row["role"] == "runtime_adapter"
            else f"procedure/{row['relative_path']}"
        )
        destination = _safe_member(destination)
        files.append((destination, data))
        file_rows.append(
            {
                "path": destination,
                "source_role": row["role"],
                "sha256": sha256_bytes(data),
                "size": len(data),
            }
        )
        if applied:
            redactions.append({"path": destination, "kinds": applied})
    export_id = stable_id(
        "personal-skill-export",
        selected,
        target_runtime,
        approval_id,
        str(include_source_runtime_adapter),
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "export_id": export_id,
        "artifact_role": "portable_export",
        "skill_id": skill_id,
        "source_revision_id": selected,
        "target_runtime": target_runtime,
        "reviewed_by": reviewed_by,
        "approval_id": approval_id,
        "files": sorted(file_rows, key=lambda row: row["path"]),
        "omitted_runtime_adapters": sorted(omitted),
        "redactions": redactions,
        "local_paths_included": False,
        "compatibility_status": "candidate_reviewed_bundle",
        "authority_boundary": "Reviewed inert export; compatibility and installation are not implied.",
    }
    _validate(hub, "personal_skill_portable_export", manifest)
    manifest_bytes = (json_dumps(manifest, pretty=True) + "\n").encode("utf-8")
    checked_manifest, final_redactions = _portable(manifest_bytes, roots)
    if final_redactions or checked_manifest != manifest_bytes:
        raise ValueError("Portable export manifest required an unexpected final redaction")
    files.append((_safe_member("portable-export-manifest.json"), manifest_bytes))
    for name, data in files:
        _safe_member(name)
        checked, applied = _portable(data, roots)
        if applied or checked != data:
            raise ValueError(f"Portable member failed final path-leak validation: {name}")

    destination = root / "exports" / _key(export_id)
    _safe_archive_output(root, root / "graph.json")
    _safe_archive_output(root, destination / "export-record.json")
    assert_dad_write_allowed(destination)
    destination = _prepare_archive_directory(root, destination)
    bundle_path = _safe_archive_output(root, destination / "bundle.zip")
    fd, temp = tempfile.mkstemp(prefix=".bundle.", suffix=".zip", dir=str(destination))
    os.close(fd)
    try:
        with zipfile.ZipFile(
            temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as bundle:
            for name, data in sorted(files, key=lambda row: row[0]):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, data)
        data = Path(temp).read_bytes()
        if bundle_path.exists() and bundle_path.read_bytes() != data:
            raise RuntimeError(f"Export collision: {export_id}")
        if not bundle_path.exists():
            _write_bytes(root, bundle_path, data)
    finally:
        Path(temp).unlink(missing_ok=True)
    record = {
        **manifest,
        "exported_at": utc_now(),
        "bundle_sha256": sha256_bytes(bundle_path.read_bytes()),
        "bundle_path_private_hint": str(bundle_path),
        "local_paths_private": True,
    }
    record_path = _safe_archive_output(root, destination / "export-record.json")
    if record_path.exists():
        existing = _json(record_path)
        comparable = {key: value for key, value in existing.items() if key != "exported_at"}
        candidate = {key: value for key, value in record.items() if key != "exported_at"}
        if comparable != candidate:
            raise RuntimeError(f"Export record collision: {export_id}")
        record = existing
    else:
        _write_archive_json(root, record_path, record)
    build_graph(hub, env=env)
    return record


def _edge(
    source: str,
    target: str,
    kind: str,
    evidence: list[str],
    *,
    run_id: str = "",
) -> dict[str, Any]:
    return {
        "edge_id": stable_id("personal-skill-edge", source, target, kind),
        "source": source,
        "target": target,
        "edge_type": kind,
        "method": "declared-personal-skill-archive-v1",
        "evidence": sorted(evidence),
        "confidence": "direct_deterministic_evidence",
        "scan_provenance": {
            "run_id": run_id or "not_applicable",
            "source": "global-personal-skills-gpt",
        },
        "review_status": "candidate",
        "authority_boundary": "Graph presence does not imply approval, installation, or authority.",
    }


def build_graph(
    hub: Path,
    *,
    env: dict[str, str] | None = None,
    manifest: dict[str, Any] | None = None,
    observations: list[SkillObservation] | None = None,
) -> dict[str, Any]:
    root = archive_root(hub, env=env)
    source_manifest = manifest or load_source_manifest(hub)
    default_source = resolve_source_root(source_manifest)
    _assert_archive_disjoint(default_source, root)
    current_rows = observations
    if current_rows is None:
        try:
            _loaded_manifest, observed_source, current_rows, _unknown = _observations(hub, env=env)
            _assert_archive_disjoint(observed_source, root)
        except ValueError:
            current_rows = []
    elif current_rows:
        _assert_archive_disjoint(
            Path(current_rows[0].source_absolute_path_hint).parent,
            root,
        )

    agent_registry = _json(hub / "registry/agent-skill-library.json")
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    revisions: list[dict[str, Any]] = []
    runtime_id = f"runtime:{source_manifest['source_runtime']}"
    nodes[runtime_id] = {
        "node_id": runtime_id,
        "node_type": "runtime",
        "review_status": "declared",
    }
    source_path_to_skill: dict[str, str] = {}

    for row in current_rows:
        source_path_to_skill[row.source_relative_path.casefold()] = row.skill_id
        if row.status != "active":
            continue
        logical = row.skill_id
        active_source = f"active-source:{row.skill_id}"
        nodes[logical] = {
            "node_id": logical,
            "node_type": "personal_skill",
            "label": row.name,
            "authority": "live_global_personal_skill_root",
            "review_status": "declared_allowlist",
        }
        nodes[active_source] = {
            "node_id": active_source,
            "node_type": "active_personal_source",
            "label": row.name,
            "authority": "source_authority",
            "review_status": "source_observation",
        }
        relation = _edge(
            active_source,
            runtime_id,
            "loaded_by",
            ["config/global-personal-skills.json"],
        )
        edges[relation["edge_id"]] = relation

    _safe_archive_output(root, root / "skills")
    for pointer_path in sorted(root.glob("skills/*/current.json")):
        pointer = _json(_safe_archive_output(root, pointer_path))
        if pointer.get("status") != "active":
            continue
        skill_id = str(pointer.get("skill_id", ""))
        active_source = f"active-source:{skill_id}"
        if active_source in nodes:
            continue
        logical = skill_id
        source_runtime = str(pointer.get("source_runtime", source_manifest["source_runtime"]))
        pointer_runtime = f"runtime:{source_runtime}"
        nodes.setdefault(
            pointer_runtime,
            {"node_id": pointer_runtime, "node_type": "runtime", "review_status": "declared"},
        )
        nodes[logical] = {
            "node_id": logical,
            "node_type": "personal_skill",
            "label": skill_id,
            "authority": "last_observed_live_global_personal_skill_root",
            "review_status": "source_observation",
        }
        nodes[active_source] = {
            "node_id": active_source,
            "node_type": "active_personal_source",
            "label": skill_id,
            "authority": "last_observed_source_authority",
            "review_status": "source_observation",
        }
        relation = _edge(
            active_source,
            pointer_runtime,
            "loaded_by",
            ["personal-skill current pointer"],
        )
        edges[relation["edge_id"]] = relation
    for path in sorted(root.glob("revisions/*/*/revision.json")):
        raw = _json(_safe_archive_output(root, path))
        revision = _load_revision(hub, root, str(raw.get("revision_id", "")))
        revisions.append(revision)
        skill_id = str(revision["skill_id"])
        source_path_to_skill.setdefault(str(revision["source_relative_path"]).casefold(), skill_id)
        logical = skill_id
        revision_node = f"archived-revision:{revision['revision_id']}"
        observation_node = f"source-observation:{revision['revision_id']}"
        nodes.setdefault(
            logical,
            {
                "node_id": logical,
                "node_type": "personal_skill",
                "label": skill_id,
                "authority": "stable_archived_identity_only",
                "review_status": "source_observation",
            },
        )
        nodes[observation_node] = {
            "node_id": observation_node,
            "node_type": "personal_source_observation",
            "source_relative_path": revision["source_relative_path"],
            "source_runtime": revision["source_runtime"],
            "review_status": "source_observation",
            "active": False,
        }
        nodes[revision_node] = {
            "node_id": revision_node,
            "node_type": "archived_revision",
            "artifact_role": "source_snapshot",
            "tree_sha256": revision["tree_sha256"],
            "validation_status": revision["validation_status"],
            "review_status": revision["review_status"],
            "inert": True,
        }
        for edge in (
            _edge(
                revision_node,
                observation_node,
                "snapshot_of",
                [revision["revision_id"], revision["source_manifest_sha256"]],
                run_id=revision["run_id"],
            ),
            _edge(
                revision_node,
                logical,
                "revision_of",
                [revision["revision_id"]],
                run_id=revision["run_id"],
            ),
        ):
            edges[edge["edge_id"]] = edge

    for registered in agent_registry.get("skills", []):
        for evidence in registered.get("source_evidence", []):
            marker = str(evidence)
            prefix = "personal-skill-source:"
            if not marker.startswith(prefix):
                continue
            skill_id = source_path_to_skill.get(marker[len(prefix) :].casefold(), "")
            if not skill_id:
                continue
            adaptation = f"dad-adaptation:{registered['skill_id']}"
            nodes[adaptation] = {
                "node_id": adaptation,
                "node_type": "dad_adaptation",
                "label": registered["name"],
                "review_status": registered["review_status"],
            }
            edge = _edge(
                skill_id,
                adaptation,
                "adapted_as",
                [marker, "registry/agent-skill-library.json"],
            )
            edges[edge["edge_id"]] = edge

    checkout_log = hub / "processed/skills/checkouts.jsonl"
    for checkout in _read_jsonl(checkout_log):
        adaptation = f"dad-adaptation:{checkout.get('skill_id', '')}"
        if adaptation not in nodes:
            continue
        checkout_node = f"checkout-pointer:{checkout.get('checkout_id', '')}"
        nodes[checkout_node] = {
            "node_id": checkout_node,
            "node_type": "checkout_pointer",
            "label": checkout.get("checkout_id", ""),
            "review_status": checkout.get("review_status", "candidate"),
        }

    by_hash: dict[str, list[dict[str, Any]]] = {}
    for revision in revisions:
        by_hash.setdefault(str(revision["tree_sha256"]), []).append(revision)
    for digest, group in by_hash.items():
        ordered = sorted(group, key=lambda row: str(row["revision_id"]))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                edge = _edge(
                    f"archived-revision:{left['revision_id']}",
                    f"archived-revision:{right['revision_id']}",
                    "duplicate_content_of",
                    [f"sha256:{digest}"],
                )
                edges[edge["edge_id"]] = edge

    for path in sorted(root.glob("exports/*/export-record.json")):
        record = _json(_safe_archive_output(root, path))
        manifest_record = {
            key: record[key]
            for key in (
                "schema_version",
                "export_id",
                "artifact_role",
                "skill_id",
                "source_revision_id",
                "target_runtime",
                "reviewed_by",
                "approval_id",
                "files",
                "omitted_runtime_adapters",
                "redactions",
                "local_paths_included",
                "compatibility_status",
                "authority_boundary",
            )
        }
        _validate(hub, "personal_skill_portable_export", manifest_record)
        source_revision = _load_revision(hub, root, str(record["source_revision_id"]))
        if source_revision["skill_id"] != record["skill_id"]:
            raise ValueError("Portable export provenance does not match its revision owner")
        bundle_path = _safe_archive_output(root, path.parent / "bundle.zip")
        if sha256_bytes(bundle_path.read_bytes()) != record.get("bundle_sha256"):
            raise ValueError("Portable export bundle integrity check failed")
        export_node = f"portable-export:{record['export_id']}"
        target = f"runtime:{record['target_runtime']}"
        nodes[export_node] = {
            "node_id": export_node,
            "node_type": "portable_export",
            "artifact_role": "portable_export",
            "review_status": record["compatibility_status"],
            "local_paths_included": False,
        }
        nodes.setdefault(
            target,
            {"node_id": target, "node_type": "runtime", "review_status": "declared"},
        )
        for edge in (
            _edge(
                export_node,
                f"archived-revision:{record['source_revision_id']}",
                "derived_from",
                [record["approval_id"]],
            ),
            _edge(export_node, target, "portable_to", [record["approval_id"]]),
        ):
            edges[edge["edge_id"]] = edge

    graph = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "nodes": sorted(nodes.values(), key=lambda row: row["node_id"]),
        "edges": sorted(edges.values(), key=lambda row: row["edge_id"]),
        "authority_boundary": "Candidate graph only; no approval, installation, compatibility, or authority transfer is implied.",
        "local_paths_included": False,
    }
    _resolved_root, mode = resolve_data_root(hub, env=env)
    if mode == "data_root":
        _write_archive_json(root, _safe_archive_output(root, root / "graph.json"), graph)
    return graph


def daily(
    hub: Path,
    *,
    source_root: Path | None = None,
    manifest_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    review = status(hub, source_root=source_root, manifest_path=manifest_path, env=env)
    if not review["needs_steward_review"]:
        return {"status": "no_delta", "snapshot_created": False, "review": review}
    if review["data_root_mode"] != "data_root":
        return {
            "status": "blocked_uninitialized_data_root",
            "snapshot_created": False,
            "review": review,
            "next_action": "Initialize/migrate DAD_DATA_ROOT for the stable hub.",
        }
    run = snapshot(hub, source_root=source_root, manifest_path=manifest_path, env=env)
    return {"status": run["status"], "snapshot_created": True, "review": review, "run": run}
