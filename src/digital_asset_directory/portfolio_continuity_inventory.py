"""Privacy-minimized, local-only Git inventory for portfolio continuity.

The inventory is deliberately observation-only.  It reads refs, linked
worktrees, and aggregate porcelain-v2 status without fetching, contacting a
remote, or changing Git state.  Paths, ref names, commit subjects, and Codex
titles are used only transiently; the returned packet contains opaque IDs,
object IDs, counts, timestamps, and fingerprints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Iterable, Mapping, Sequence

from .ids import stable_id


SCHEMA_VERSION = "dad.portfolio_continuity_inventory.v1"
AUTHORITY_BOUNDARY = (
    "Continuity inventory is local read-only candidate evidence. It cannot fetch, "
    "create or update refs, mutate a worktree, merge identities, archive tasks, or "
    "authorize execution."
)

_ALLOWED_GIT_COMMANDS = frozenset(
    {"for-each-ref", "ls-tree", "rev-parse", "status", "worktree"}
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SAFE_STATE_RE = re.compile(r"^[a-z0-9_.:/-]{1,64}$")
_SAFE_TIME_RE = re.compile(r"^[0-9T:Z+.-]{1,64}$")


class ContinuityInventoryError(RuntimeError):
    """Raised when a repository cannot be observed safely."""


@dataclass(frozen=True, slots=True)
class GitResult:
    returncode: int
    stdout: bytes
    stderr: bytes


GitRunner = Callable[[Path, Sequence[str]], GitResult]


@dataclass(frozen=True, slots=True)
class RefObservation:
    ref_name: str
    object_id: str
    committed_at: str
    subject: str
    ref_kind: str


@dataclass(frozen=True, slots=True)
class StatusObservation:
    status_available: bool
    staged: int
    unstaged: int
    untracked: int
    conflicted: int
    path_term_sets: tuple[frozenset[str], ...]
    path_fingerprints: tuple[str, ...]
    fingerprint: str

    @property
    def dirty(self) -> bool | None:
        if not self.status_available:
            return None
        return bool(self.staged or self.unstaged or self.untracked or self.conflicted)


@dataclass(frozen=True, slots=True)
class WorktreeObservation:
    path: Path
    worktree_id: str
    head_id: str
    branch_name: str
    detached: bool
    locked: bool
    prunable: bool
    status: StatusObservation


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _tokenize(value: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(value.casefold()))


def _default_git_runner(cwd: Path, args: Sequence[str]) -> GitResult:
    if not args or args[0] not in _ALLOWED_GIT_COMMANDS:
        raise ContinuityInventoryError("Git command is outside the read-only continuity allowlist")
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContinuityInventoryError("Local Git observation failed") from exc
    return GitResult(completed.returncode, completed.stdout, completed.stderr)


def _run(runner: GitRunner | None, cwd: Path, args: Sequence[str]) -> GitResult:
    return (runner or _default_git_runner)(cwd, args)


def _repository_identity(repo_root: Path, runner: GitRunner | None = None) -> str:
    result = _run(runner, repo_root, ["rev-parse", "--git-common-dir"])
    if result.returncode != 0:
        raise ContinuityInventoryError("Repository identity is unavailable")
    raw = result.stdout.decode("utf-8", errors="replace").strip()
    if not raw:
        raise ContinuityInventoryError("Repository identity is unavailable")
    common = Path(raw)
    if not common.is_absolute():
        common = repo_root / common
    try:
        normalized = str(common.resolve()).replace("\\", "/").casefold()
    except OSError as exc:
        raise ContinuityInventoryError("Repository identity is unavailable") from exc
    return stable_id("continuity-repository", _digest(normalized))


def _ref_id(repository_id: str, ref_name: str) -> str:
    return stable_id("continuity-ref", repository_id, _digest(ref_name))


def _worktree_id(repository_id: str, path: Path) -> str:
    try:
        normalized = str(path.resolve()).replace("\\", "/").casefold()
    except OSError:
        normalized = str(path).replace("\\", "/").casefold()
    return stable_id("continuity-worktree", repository_id, _digest(normalized))


def _collect_ref_observations(
    repo_root: Path,
    *,
    max_refs: int,
    runner: GitRunner | None = None,
) -> tuple[list[RefObservation], bool]:
    if not 1 <= max_refs <= 5000:
        raise ValueError("max_refs must be between 1 and 5000")
    fmt = "%(refname)%00%(objectname)%00%(committerdate:iso-strict)%00%(subject)"
    result = _run(
        runner,
        repo_root,
        [
            "for-each-ref",
            f"--count={max_refs + 1}",
            f"--format={fmt}",
            "refs/heads",
            "refs/remotes",
            "refs/tags",
        ],
    )
    if result.returncode != 0:
        raise ContinuityInventoryError("Local ref inventory failed")
    rows: list[RefObservation] = []
    for raw_line in result.stdout.decode("utf-8", errors="replace").splitlines():
        fields = raw_line.split("\0")
        if len(fields) != 4:
            continue
        ref_name, object_id, committed_at, subject = fields
        if ref_name.startswith("refs/remotes/") and ref_name.endswith("/HEAD"):
            continue
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", object_id):
            continue
        rows.append(
            RefObservation(
                ref_name=ref_name,
                object_id=object_id.casefold(),
                committed_at=committed_at,
                subject=subject,
                ref_kind=(
                    "head"
                    if ref_name.startswith("refs/heads/")
                    else "remote"
                    if ref_name.startswith("refs/remotes/")
                    else "tag"
                ),
            )
        )
    truncated = len(rows) > max_refs
    return rows[:max_refs], truncated


def _parse_worktree_records(raw: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for block in raw.split(b"\0\0"):
        if not block:
            continue
        row: dict[str, Any] = {
            "path": "",
            "head": "",
            "branch": "",
            "detached": False,
            "locked": False,
            "prunable": False,
        }
        for field in block.split(b"\0"):
            text = field.decode("utf-8", errors="replace")
            key, _, value = text.partition(" ")
            if key == "worktree":
                row["path"] = value
            elif key == "HEAD":
                row["head"] = value.casefold()
            elif key == "branch":
                row["branch"] = value
            elif key in {"detached", "locked", "prunable"}:
                row[key] = True
        if row["path"]:
            row["detached"] = bool(row["detached"] or not row["branch"])
            records.append(row)
    return records


def _status_record_path(record: bytes, extra: bytes | None = None) -> str:
    if record.startswith(b"? ") or record.startswith(b"! "):
        return record[2:].decode("utf-8", errors="replace")
    max_split = 9 if record.startswith(b"2 ") else 10 if record.startswith(b"u ") else 8
    parts = record.split(b" ", max_split)
    current = parts[-1].decode("utf-8", errors="replace") if parts else ""
    if extra:
        current += " " + extra.decode("utf-8", errors="replace")
    return current


def _observe_status(
    worktree_path: Path, runner: GitRunner | None = None
) -> StatusObservation:
    result = _run(
        runner,
        worktree_path,
        ["status", "--porcelain=v2", "-z", "--untracked-files=all", "--ignore-submodules=none"],
    )
    if result.returncode != 0:
        return StatusObservation(False, 0, 0, 0, 0, (), (), _digest("status_unavailable"))
    staged = unstaged = untracked = conflicted = 0
    term_sets: list[frozenset[str]] = []
    path_fingerprints: list[str] = []
    records = result.stdout.split(b"\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        extra: bytes | None = None
        if record.startswith(b"2 ") and index < len(records):
            extra = records[index]
            index += 1
        if record.startswith((b"1 ", b"2 ")):
            parts = record.split(b" ", 2)
            xy = parts[1].decode("ascii", errors="ignore") if len(parts) > 1 else ".."
            staged += int(bool(xy and xy[0] != "."))
            unstaged += int(len(xy) > 1 and xy[1] != ".")
        elif record.startswith(b"u "):
            conflicted += 1
        elif record.startswith(b"? "):
            untracked += 1
        else:
            continue
        path = _status_record_path(record, extra)
        term_sets.append(_tokenize(path))
        path_fingerprints.append(_digest(path.replace("\\", "/").casefold()))
    material = {
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "conflicted": conflicted,
        "paths": sorted(path_fingerprints),
    }
    return StatusObservation(
        True,
        staged,
        unstaged,
        untracked,
        conflicted,
        tuple(term_sets),
        tuple(sorted(path_fingerprints)),
        _digest(material),
    )


def _unavailable_status(reason: str) -> StatusObservation:
    return StatusObservation(False, 0, 0, 0, 0, (), (), _digest(reason))


def _collect_worktree_observations(
    repo_root: Path,
    repository_id: str,
    *,
    max_worktrees: int,
    include_status: bool = True,
    runner: GitRunner | None = None,
) -> tuple[list[WorktreeObservation], bool, list[str]]:
    if not 1 <= max_worktrees <= 1000:
        raise ValueError("max_worktrees must be between 1 and 1000")
    result = _run(runner, repo_root, ["worktree", "list", "--porcelain", "-z"])
    if result.returncode != 0:
        return [], False, ["worktree_inventory_unavailable"]
    raw_rows = _parse_worktree_records(result.stdout)
    truncated = len(raw_rows) > max_worktrees
    observations: list[WorktreeObservation] = []
    gaps: list[str] = []
    for row in raw_rows[:max_worktrees]:
        path = Path(str(row["path"]))
        if include_status:
            try:
                status = _observe_status(path, runner)
            except ContinuityInventoryError:
                status = _unavailable_status("status_observation_failed")
        else:
            status = _unavailable_status("status_not_requested")
        if include_status and not status.status_available:
            gaps.append("worktree_status_unavailable")
        observations.append(
            WorktreeObservation(
                path=path,
                worktree_id=_worktree_id(repository_id, path),
                head_id=str(row["head"]),
                branch_name=str(row["branch"]),
                detached=bool(row["detached"]),
                locked=bool(row["locked"]),
                prunable=bool(row["prunable"]),
                status=status,
            )
        )
    return observations, truncated, sorted(set(gaps))


def _safe_codex_items(
    repository_id: str, rows: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        opaque_source = str(row.get("task_id") or row.get("id") or "").strip()
        title = str(row.get("title") or "")
        aliases = [str(value) for value in row.get("aliases", []) if isinstance(value, str)]
        if not opaque_source or not (title or aliases):
            continue
        state_raw = str(row.get("state") or "unknown").casefold().strip()
        state = state_raw if _SAFE_STATE_RE.fullmatch(state_raw) else "unknown"
        updated_raw = str(row.get("updated_at") or "").strip()
        updated_at = updated_raw if _SAFE_TIME_RE.fullmatch(updated_raw) else ""
        result.append(
            {
                "codex_item_id": stable_id(
                    "continuity-codex-item", repository_id, _digest(opaque_source)
                ),
                "state": state,
                "updated_at": updated_at,
                "metadata_fingerprint": _digest(
                    {
                        "source": _digest(opaque_source),
                        "title": _digest(title),
                        "aliases": [_digest(value) for value in aliases],
                        "state": state,
                        "updated_at": updated_at,
                    }
                ),
            }
        )
    return sorted(result, key=lambda row: row["codex_item_id"])


def build_continuity_inventory(
    repo_root: Path,
    *,
    codex_metadata: Iterable[Mapping[str, Any]] | None = None,
    max_refs: int = 512,
    max_worktrees: int = 128,
    runner: GitRunner | None = None,
) -> dict[str, Any]:
    """Build a ref-aware, path-free inventory for one local repository."""

    root = Path(repo_root)
    repository_id = _repository_identity(root, runner)
    refs, refs_truncated = _collect_ref_observations(
        root, max_refs=max_refs, runner=runner
    )
    worktrees, worktrees_truncated, gaps = _collect_worktree_observations(
        root,
        repository_id,
        max_worktrees=max_worktrees,
        runner=runner,
    )
    by_object: dict[str, dict[str, Any]] = {}
    for ref in refs:
        row = by_object.setdefault(
            ref.object_id,
            {
                "object_id": ref.object_id,
                "ref_ids": [],
                "ref_kinds": set(),
                "committed_at": ref.committed_at,
                "worktree_ids": [],
                "detached_worktree": False,
            },
        )
        row["ref_ids"].append(_ref_id(repository_id, ref.ref_name))
        row["ref_kinds"].add(ref.ref_kind)
        if ref.committed_at > row["committed_at"]:
            row["committed_at"] = ref.committed_at
    for worktree in worktrees:
        if not worktree.head_id:
            continue
        row = by_object.setdefault(
            worktree.head_id,
            {
                "object_id": worktree.head_id,
                "ref_ids": [],
                "ref_kinds": set(),
                "committed_at": "",
                "worktree_ids": [],
                "detached_worktree": False,
            },
        )
        row["worktree_ids"].append(worktree.worktree_id)
        row["detached_worktree"] = bool(row["detached_worktree"] or worktree.detached)
    object_rows = []
    for object_id, row in sorted(by_object.items()):
        ref_ids = sorted(set(row["ref_ids"]))
        worktree_ids = sorted(set(row["worktree_ids"]))
        object_rows.append(
            {
                "object_id": object_id,
                "ref_ids": ref_ids,
                "ref_count": len(ref_ids),
                "ref_kinds": sorted(row["ref_kinds"]),
                "committed_at": row["committed_at"],
                "worktree_ids": worktree_ids,
                "worktree_count": len(worktree_ids),
                "detached_worktree": bool(row["detached_worktree"]),
            }
        )
    worktree_rows = [
        {
            "worktree_id": row.worktree_id,
            "head_id": row.head_id,
            "branch_ref_id": (
                _ref_id(repository_id, row.branch_name) if row.branch_name else ""
            ),
            "detached": row.detached,
            "locked": row.locked,
            "prunable": row.prunable,
            "status_available": row.status.status_available,
            "dirty": row.status.dirty,
            "changes": {
                "staged": row.status.staged,
                "unstaged": row.status.unstaged,
                "untracked": row.status.untracked,
                "conflicted": row.status.conflicted,
            },
            "overlay_fingerprint": row.status.fingerprint,
        }
        for row in sorted(worktrees, key=lambda item: item.worktree_id)
    ]
    if refs_truncated:
        gaps.append("refs_truncated")
    if worktrees_truncated:
        gaps.append("worktrees_truncated")
    if codex_metadata is None:
        gaps.append("codex_metadata_not_supplied")
    generated_at = datetime.now(timezone.utc).isoformat()
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "repository_id": repository_id,
        "objects": object_rows,
        "worktrees": worktree_rows,
        "codex_items": _safe_codex_items(repository_id, codex_metadata or ()),
        "coverage": {
            "refs_observed": len(refs),
            "objects_observed": len(object_rows),
            "worktrees_observed": len(worktree_rows),
            "refs_include": ["refs/heads", "refs/remotes", "refs/tags"],
            "dirty_overlay_mode": "porcelain_v2_aggregate",
            "codex_source": (
                "explicit_supplied_metadata_only"
                if codex_metadata is not None
                else "not_supplied"
            ),
            "network_calls": 0,
            "git_writes": 0,
            "gaps": sorted(set(gaps)),
        },
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    packet["inventory_fingerprint"] = _digest(
        {key: value for key, value in packet.items() if key not in {"generated_at"}}
    )
    return packet


inventory_repository = build_continuity_inventory


__all__ = [
    "AUTHORITY_BOUNDARY",
    "ContinuityInventoryError",
    "GitResult",
    "GitRunner",
    "SCHEMA_VERSION",
    "build_continuity_inventory",
    "inventory_repository",
]
