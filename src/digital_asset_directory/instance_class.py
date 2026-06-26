from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

OS_JUNK_FILENAMES = {".ds_store", "thumbs.db", "desktop.ini"}
EMPTY_MARKER_FILENAMES = {"__init__.py", ".gitkeep", ".keep"}

ALWAYS_EXCLUDE_PATTERNS = [
    ".DS_Store",
    "**/.DS_Store",
    "._*",
    "**/._*",
    "Thumbs.db",
    "**/Thumbs.db",
    "desktop.ini",
    "**/desktop.ini",
]

INSTANCE_CLASS_PRIORITY = {
    "source": 0,
    "archive": 1,
    "worktree": 2,
    "generated": 3,
    "temp_fixture": 4,
    "os_junk": 5,
}

QUARANTINED_INSTANCE_CLASSES = {"temp_fixture", "worktree", "generated", "os_junk"}


def _normalized_path(path: str) -> str:
    return path.replace("\\", "/").strip().lower()


def _parts(path: str) -> list[str]:
    return [part for part in PurePosixPath(_normalized_path(path)).parts if part not in {"", "/"}]


def _is_os_junk_name(name: str) -> bool:
    return name in OS_JUNK_FILENAMES or name.startswith("._")


def classify_instance_class(logical_path: str) -> str:
    """Classify whether an observation is a source asset or a non-portfolio instance.

    The catalog may still observe temp fixtures, worktrees, and generated outputs as
    lineage evidence. This class prevents those observations from earning the same
    current value score as canonical/source assets.
    """
    normalized = _normalized_path(logical_path)
    parts = _parts(normalized)
    name = parts[-1] if parts else normalized
    path_with_slashes = f"/{normalized.strip('/')}/"

    if _is_os_junk_name(name):
        return "os_junk"
    if (
        "/.pytest-tmp-root/" in path_with_slashes
        or "/pytest-of-" in path_with_slashes
        or ("/pytest-" in path_with_slashes and "/contract-repo/" in path_with_slashes)
        or "/90_ai_tooling_and_temp/" in path_with_slashes
        or "/.ci-contracts/" in path_with_slashes
        or "/.scratch/" in path_with_slashes
    ):
        return "temp_fixture"
    if any(part in {"processed", "raw", "state"} for part in parts):
        return "generated"
    if any(
        part in {"worktree", "worktrees", "_codex_worktrees", ".worktrees"}
        or part.endswith("-worktree")
        or part.endswith("-workspace")
        or part.endswith("_worktrees")
        for part in parts
    ):
        return "worktree"
    if any(
        part in {"archive", "archives", "archived"}
        or part.startswith("main-clean-")
        or part.startswith("backup-")
        for part in parts
    ):
        return "archive"
    return "source"


def information_content_class(
    logical_path: str,
    *,
    asset_type: str,
    size_bytes: int,
    content_sha256: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    normalized = _normalized_path(logical_path)
    name = PurePosixPath(normalized).name
    if _is_os_junk_name(name):
        return "os_junk"
    if size_bytes == 0 and name in EMPTY_MARKER_FILENAMES:
        return "empty_marker"
    if size_bytes == 0:
        return "empty"
    if not content_sha256:
        return "metadata_only"
    text_tokens = metadata.get("text_tokens")
    chunk_text = metadata.get("chunk_text")
    if isinstance(text_tokens, list) and text_tokens:
        return "content_extracted"
    if isinstance(chunk_text, str) and chunk_text.strip():
        return "content_extracted"
    if asset_type == "media":
        return "binary_metadata"
    return "content_present"


def instance_priority(instance_class: str) -> int:
    return INSTANCE_CLASS_PRIORITY.get(instance_class, 9)


def is_independent_portfolio_asset(instance_class: str, info_class: str) -> bool:
    if instance_class in QUARANTINED_INSTANCE_CLASSES:
        return False
    if info_class == "os_junk":
        return False
    return True


def calibration_group_key(
    *,
    asset_id: str,
    logical_path: str,
    asset_type: str,
    content_sha256: str | None,
    metadata_fingerprint: str,
    instance_class: str,
) -> str:
    if content_sha256:
        return f"sha256:{content_sha256}"
    name = PurePosixPath(_normalized_path(logical_path)).name
    if instance_class in QUARANTINED_INSTANCE_CLASSES:
        return f"quarantined:{instance_class}:{asset_type}:{name}"
    if metadata_fingerprint:
        return f"metadata:{metadata_fingerprint}"
    return f"asset:{asset_id}"
