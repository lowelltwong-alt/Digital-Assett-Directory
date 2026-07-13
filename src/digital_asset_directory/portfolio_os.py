from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from .ids import stable_id
from .transport import data_path
from .utils import atomic_write_text, idf_weighted_cosine, idf_weights, json_dumps, tokens, utc_now


SCHEMA_VERSION = "dad.portfolio_attention.v1"
DEFAULT_STALE_DAYS = 3
DEFAULT_MAX_DEPTH = 5
DEFAULT_RELATED_LIMIT = 3
GIT_TIMEOUT_SECONDS = 15
WORKTREE_STATUS_WORKERS = 4

AUTHORITY_BOUNDARY = (
    "Portfolio attention reports are local, metadata-only candidate evidence. They do not "
    "authorize commits, branch deletion, worktree removal, cross-repo writes, or source-canon "
    "changes."
)

_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".tmp",
    ".ruff_cache",
    ".mypy_cache",
}

_GENERIC_RELATION_TOKENS = {
    "add",
    "branch",
    "chore",
    "codex",
    "docs",
    "feature",
    "fix",
    "initial",
    "main",
    "master",
    "merge",
    "plan",
    "project",
    "pull",
    "request",
    "test",
    "update",
}

_TRACK_COUNT = re.compile(r"(ahead|behind) (\d+)")


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioScanSettings:
    """Stable settings for a read-only portfolio attention scan."""

    roots: tuple[Path, ...]
    stale_days: int = DEFAULT_STALE_DAYS
    max_depth: int = DEFAULT_MAX_DEPTH
    related_limit: int = DEFAULT_RELATED_LIMIT

    def __post_init__(self) -> None:
        if not self.roots:
            raise ValueError("At least one portfolio root is required.")
        if self.stale_days < 1:
            raise ValueError("stale_days must be at least 1.")
        if not 1 <= self.max_depth <= 12:
            raise ValueError("max_depth must be between 1 and 12.")
        if not 0 <= self.related_limit <= 10:
            raise ValueError("related_limit must be between 0 and 10.")


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _run_git_bytes(repo: Path, args: Iterable[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
        check=False,
        capture_output=True,
        timeout=GIT_TIMEOUT_SECONDS,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def _run_git_text(repo: Path, args: Iterable[str]) -> subprocess.CompletedProcess[str]:
    result = _run_git_bytes(repo, args)
    return subprocess.CompletedProcess(
        args=result.args,
        returncode=result.returncode,
        stdout=result.stdout.decode("utf-8", errors="replace"),
        stderr=result.stderr.decode("utf-8", errors="replace"),
    )


def discover_git_checkouts(
    roots: Iterable[Path], *, max_depth: int = DEFAULT_MAX_DEPTH
) -> tuple[list[Path], list[dict[str, str]]]:
    """Find checkout roots without reading repository file contents."""

    discovered: dict[str, Path] = {}
    errors: list[dict[str, str]] = []
    pending: list[tuple[Path, int]] = [(Path(root).expanduser(), 0) for root in roots]
    visited: set[str] = set()

    while pending:
        candidate, depth = pending.pop()
        try:
            resolved = candidate.resolve()
        except OSError as exc:
            errors.append({"path": str(candidate), "error": str(exc)})
            continue
        key = _path_key(resolved)
        if key in visited:
            continue
        visited.add(key)
        if not resolved.exists() or not resolved.is_dir():
            errors.append({"path": str(resolved), "error": "root_missing_or_not_directory"})
            continue
        is_checkout = (resolved / ".git").exists()
        if is_checkout:
            discovered[key] = resolved
            # A user-supplied portfolio root can itself be an aggregate Git
            # checkout containing the real project repos. Descend only from
            # that explicit root; once a nested checkout is found, stop there.
            if depth > 0:
                continue
        if depth >= max_depth:
            continue
        try:
            children = sorted(
                (
                    Path(entry.path)
                    for entry in os.scandir(resolved)
                    if entry.is_dir(follow_symlinks=False)
                    and entry.name not in _SKIP_DIR_NAMES
                    and not entry.name.startswith(".pytest-tmp")
                ),
                key=lambda path: path.name.casefold(),
                reverse=True,
            )
        except OSError as exc:
            errors.append({"path": str(resolved), "error": str(exc)})
            continue
        pending.extend((child, depth + 1) for child in children)

    return sorted(discovered.values(), key=lambda path: str(path).casefold()), errors


def _resolve_common_git_dir(checkout: Path) -> Path:
    result = _run_git_text(checkout, ["rev-parse", "--git-common-dir"])
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"Cannot resolve git common dir for {checkout}")
    raw = Path(result.stdout.strip())
    return raw.resolve() if raw.is_absolute() else (checkout / raw).resolve()


def _parse_worktree_list(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in [*text.splitlines(), ""]:
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key in {"detached", "bare"}:
            current[key] = True
        elif key in {"locked", "prunable"}:
            current[key] = value or True
        else:
            current[key] = value
    return records


def _worktrees_for_checkout(checkout: Path) -> list[dict[str, Any]]:
    result = _run_git_text(checkout, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return [{"worktree": str(checkout), "diagnostic": result.stderr.strip()}]
    return _parse_worktree_list(result.stdout)


def _parse_status_records(data: bytes) -> list[tuple[str, str]]:
    parts = data.split(b"\0")
    records: list[tuple[str, str]] = []
    index = 0
    while index < len(parts):
        raw = parts[index]
        index += 1
        if not raw:
            continue
        decoded = raw.decode("utf-8", errors="replace")
        if len(decoded) < 3:
            continue
        status = decoded[:2]
        path = decoded[3:]
        records.append((status, path))
        if "R" in status or "C" in status:
            index += 1
    return records


def _parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _latest_datetime(*values: str) -> str:
    parsed = [(value, _parse_datetime(value)) for value in values if value]
    available = [(value, date) for value, date in parsed if date is not None]
    if not available:
        return ""
    return max(available, key=lambda item: item[1])[0]


def _days_since(value: str, now: datetime) -> int | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds() // 86_400))


def _worktree_state(record: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(record.get("worktree", "")))
    branch_ref = str(record.get("branch", ""))
    branch = branch_ref.removeprefix("refs/heads/") if branch_ref else ""
    status_result = _run_git_bytes(
        path, ["status", "--porcelain=v1", "-z", "--untracked-files=normal"]
    )
    status_known = status_result.returncode == 0
    status_records = _parse_status_records(status_result.stdout) if status_known else []
    counts = {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0}
    latest_dirty_activity = ""
    for status, relative in status_records:
        if status == "??":
            counts["untracked"] += 1
        else:
            if status[0] not in {" ", "?"}:
                counts["staged"] += 1
            if status[1] not in {" ", "?"}:
                counts["unstaged"] += 1
            if status in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}:
                counts["conflicted"] += 1
        changed_path = path / relative
        try:
            if changed_path.exists():
                latest_dirty_activity = _latest_datetime(
                    latest_dirty_activity, _iso_from_timestamp(changed_path.stat().st_mtime)
                )
        except OSError:
            pass
    return {
        "path": str(path.resolve()),
        "branch": branch,
        "head": str(record.get("HEAD", "")),
        "detached": bool(record.get("detached")),
        "locked": record.get("locked", False),
        "prunable": record.get("prunable", False),
        "status_known": status_known,
        "dirty": bool(status_records) if status_known else None,
        "change_counts": counts,
        "changed_path_count": len(status_records),
        "latest_dirty_activity_at": latest_dirty_activity,
        "status_error": status_result.stderr.decode("utf-8", errors="replace").strip()
        if status_result.returncode != 0
        else "",
    }


def _default_branch(checkout: Path) -> str:
    symbolic = _run_git_text(
        checkout, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"]
    )
    if symbolic.returncode == 0 and symbolic.stdout.strip():
        return symbolic.stdout.strip().removeprefix("origin/")
    for candidate in ("main", "master"):
        exists = _run_git_text(
            checkout, ["show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"]
        )
        if exists.returncode == 0:
            return candidate
    current = _run_git_text(checkout, ["branch", "--show-current"])
    return current.stdout.strip()


def _local_branches(checkout: Path) -> list[dict[str, Any]]:
    fmt = (
        "%(refname:short)%00%(objectname)%00%(committerdate:iso-strict)%00"
        "%(subject)%00%(upstream:short)%00%(upstream:track)"
    )
    result = _run_git_text(checkout, ["for-each-ref", f"--format={fmt}", "refs/heads"])
    if result.returncode != 0:
        return []
    branches: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\0")
        if len(fields) != 6:
            continue
        name, head, committed_at, subject, upstream, track = fields
        counts = {"ahead": 0, "behind": 0}
        for direction, raw_count in _TRACK_COUNT.findall(track):
            counts[direction] = int(raw_count)
        branches.append(
            {
                "name": name,
                "head": head,
                "committed_at": committed_at,
                "subject": subject,
                "upstream": upstream,
                "upstream_gone": "gone" in track,
                **counts,
            }
        )
    return branches


def _merged_branches(checkout: Path, default_branch: str) -> set[str]:
    """Return all branches ancestry-merged into the default branch in one Git process."""

    if not default_branch:
        return set()
    result = _run_git_text(
        checkout,
        [
            "for-each-ref",
            f"--merged=refs/heads/{default_branch}",
            "--format=%(refname:short)",
            "refs/heads",
        ],
    )
    if result.returncode != 0:
        return set()
    return {name for name in result.stdout.splitlines() if name and name != default_branch}


def _remote_url(checkout: Path) -> str:
    result = _run_git_text(checkout, ["remote", "get-url", "origin"])
    return _sanitize_remote_url(result.stdout.strip()) if result.returncode == 0 else ""


def _sanitize_remote_url(value: str) -> str:
    """Remove userinfo, query, and fragment secrets from report remote identities."""

    if "://" not in value:
        _prefix, separator, suffix = value.partition("@")
        if separator and ":" in suffix:
            return suffix
        return value
    parsed = urlsplit(value)
    netloc_without_userinfo = parsed.netloc.rsplit("@", 1)[-1]
    if not netloc_without_userinfo:
        return ""
    return urlunsplit((parsed.scheme, netloc_without_userinfo, parsed.path, "", ""))


def _project_name(checkout: Path, remote_url: str) -> str:
    if remote_url:
        remote_name = remote_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        if remote_name:
            return remote_name
    return checkout.name


def _branch_attention(
    branch: dict[str, Any], *, default_branch: str, project_active: bool, stale_days: int
) -> dict[str, Any] | None:
    reasons: list[str] = []
    priority = 0
    days = branch.get("inactive_days")
    stale = isinstance(days, int) and days >= stale_days
    is_default = branch["name"] == default_branch

    if branch.get("conflicted"):
        reasons.append("conflicted_worktree")
        priority = max(priority, 100)
    if branch.get("status_unknown"):
        reasons.append("worktree_status_unknown")
        priority = max(priority, 85)
    if branch.get("dirty") and stale:
        reasons.append("dirty_worktree_idle")
        priority = max(priority, 95)
    elif branch.get("dirty"):
        reasons.append("dirty_worktree")
        priority = max(priority, 70)
    if branch.get("upstream_gone"):
        reasons.append("upstream_gone")
        priority = max(priority, 90)
    if branch.get("ahead", 0) > 0:
        reasons.append("unpushed_or_unmerged_commits")
        priority = max(priority, 80)
    if branch.get("behind", 0) > 0 and (branch.get("dirty") or branch.get("ahead", 0) > 0):
        reasons.append("diverged_from_upstream")
        priority = max(priority, 75)
    if not branch.get("upstream") and not is_default:
        reasons.append("no_upstream_tracking")
        priority = max(priority, 45)
    if stale and not is_default and not branch.get("merged"):
        reasons.append("stale_branch_in_active_project" if project_active else "stale_branch")
        priority = max(priority, 78 if project_active else 55)
    if stale and branch.get("merged"):
        reasons.append("merged_branch_cleanup_candidate")
        priority = max(priority, 25)
    if branch.get("prunable_worktree"):
        reasons.append("prunable_worktree_metadata")
        priority = max(priority, 65)
    if not reasons:
        return None

    if "worktree_status_unknown" in reasons:
        next_action = "Re-scan or inspect this worktree directly; DAD could not establish clean or dirty state."
    elif "conflicted_worktree" in reasons:
        next_action = "Resolve or checkpoint the conflict before starting overlapping work."
    elif "dirty_worktree_idle" in reasons:
        next_action = "Review the diff; resume, checkpoint and pause, or mark the work superseded."
    elif "stale_branch_in_active_project" in reasons:
        next_action = "Compare this branch with the active work; resume, supersede, or intentionally pause it."
    elif "upstream_gone" in reasons:
        next_action = (
            "Confirm whether the upstream work merged or was removed before changing tracking."
        )
    elif "merged_branch_cleanup_candidate" in reasons:
        next_action = (
            "Verify patch equivalence and worktree cleanliness before optional archival or cleanup."
        )
    elif "unpushed_or_unmerged_commits" in reasons:
        next_action = (
            "Review the commits and decide whether to open/update a PR or checkpoint the work."
        )
    else:
        next_action = (
            "Record a next action, pause reason, or owner so this workstream is intentional."
        )

    return {
        "priority": priority,
        "project_id": branch["project_id"],
        "project_name": branch["project_name"],
        "branch": branch["name"],
        "worktree_path": branch.get("worktree_path", ""),
        "last_activity_at": branch.get("last_activity_at", ""),
        "inactive_days": days,
        "reasons": reasons,
        "next_action": next_action,
        "evidence": {
            "dirty": branch.get("dirty"),
            "changed_path_count": int(branch.get("changed_path_count", 0)),
            "ahead": int(branch.get("ahead", 0)),
            "behind": int(branch.get("behind", 0)),
            "merged_by_ancestry": bool(branch.get("merged")),
            "upstream": branch.get("upstream", ""),
            "worktree_locked": branch.get("worktree_locked", False),
        },
    }


def _relation_tokens(project: dict[str, Any]) -> set[str]:
    values = [project["name"], project.get("remote_url", "")]
    for branch in project["branches"]:
        values.extend([branch["name"], branch.get("subject", "")])
    separated = re.sub(r"[-_./\\:+]+", " ", " ".join(values))
    meaningful_short_tokens = {
        part.casefold() for part in separated.split() if part.casefold() in {"ai", "os", "ui"}
    }
    return (tokens(separated) | meaningful_short_tokens) - _GENERIC_RELATION_TOKENS


def _attach_related_projects(projects: list[dict[str, Any]], *, limit: int) -> None:
    if limit == 0 or len(projects) < 2:
        return
    token_sets = [_relation_tokens(project) for project in projects]
    weights = idf_weights(token_sets)
    for index, project in enumerate(projects):
        candidates: list[dict[str, Any]] = []
        for other_index, other in enumerate(projects):
            if index == other_index:
                continue
            shared = sorted(token_sets[index] & token_sets[other_index])
            if len(shared) < 2:
                continue
            score = idf_weighted_cosine(token_sets[index], token_sets[other_index], weights)
            if score < 0.18:
                continue
            candidates.append(
                {
                    "project_id": other["project_id"],
                    "project_name": other["name"],
                    "score": round(score, 4),
                    "shared_metadata_tokens": shared[:8],
                    "status": "generated_candidate",
                }
            )
        project["related_projects"] = sorted(
            candidates, key=lambda item: (-item["score"], item["project_name"].casefold())
        )[:limit]


def build_portfolio_attention_report(
    settings: PortfolioScanSettings, *, now: datetime | None = None
) -> dict[str, Any]:
    """Build a read-only, metadata-only portfolio attention report."""

    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    checkouts, scan_errors = discover_git_checkouts(settings.roots, max_depth=settings.max_depth)
    seeds_by_common_dir: dict[str, tuple[Path, Path]] = {}
    for checkout in checkouts:
        try:
            common_dir = _resolve_common_git_dir(checkout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            scan_errors.append({"path": str(checkout), "error": str(exc)})
            continue
        seeds_by_common_dir.setdefault(_path_key(common_dir), (checkout, common_dir))

    projects: list[dict[str, Any]] = []
    attention_queue: list[dict[str, Any]] = []
    for common_key, (seed, common_dir) in sorted(
        seeds_by_common_dir.items(), key=lambda item: str(item[1][0]).casefold()
    ):
        raw_worktrees = _worktrees_for_checkout(seed)
        if len(raw_worktrees) > 1:
            with ThreadPoolExecutor(
                max_workers=min(WORKTREE_STATUS_WORKERS, len(raw_worktrees))
            ) as pool:
                worktrees = list(pool.map(_worktree_state, raw_worktrees))
        else:
            worktrees = [_worktree_state(item) for item in raw_worktrees]
        for worktree in worktrees:
            if not worktree["status_known"]:
                scan_errors.append(
                    {
                        "path": worktree["path"],
                        "error": f"git_status_failed: {worktree['status_error'] or 'unknown error'}",
                    }
                )
        default_branch = _default_branch(seed)
        merged_branches = _merged_branches(seed, default_branch)
        remote_url = _remote_url(seed)
        project_name = _project_name(seed, remote_url)
        project_id = stable_id("portfolio-project", common_key)
        worktrees_by_branch = {
            item["branch"]: item
            for item in worktrees
            if item.get("branch") and not item.get("detached")
        }
        branches: list[dict[str, Any]] = []
        for raw_branch in _local_branches(seed):
            worktree = worktrees_by_branch.get(raw_branch["name"], {})
            last_activity = _latest_datetime(
                raw_branch.get("committed_at", ""), worktree.get("latest_dirty_activity_at", "")
            )
            counts = worktree.get("change_counts", {})
            branches.append(
                {
                    **raw_branch,
                    "project_id": project_id,
                    "project_name": project_name,
                    "worktree_path": worktree.get("path", ""),
                    "dirty": worktree.get("dirty"),
                    "status_unknown": bool(worktree) and not bool(worktree.get("status_known")),
                    "status_error": worktree.get("status_error", ""),
                    "worktree_locked": worktree.get("locked", False),
                    "conflicted": int(counts.get("conflicted", 0)) > 0,
                    "changed_path_count": int(worktree.get("changed_path_count", 0)),
                    "last_activity_at": last_activity,
                    "inactive_days": _days_since(last_activity, observed_at),
                    "merged": raw_branch["name"] in merged_branches,
                    "prunable_worktree": bool(worktree.get("prunable")),
                }
            )
        project_active = any(
            isinstance(branch.get("inactive_days"), int)
            and branch["inactive_days"] < settings.stale_days
            for branch in branches
        )
        for branch in branches:
            item = _branch_attention(
                branch,
                default_branch=default_branch,
                project_active=project_active,
                stale_days=settings.stale_days,
            )
            if item:
                attention_queue.append(item)
        for worktree in worktrees:
            if not worktree.get("detached"):
                continue
            last_activity = worktree.get("latest_dirty_activity_at", "")
            if not (
                worktree.get("dirty")
                or worktree.get("prunable")
                or not worktree.get("status_known")
            ):
                continue
            if not worktree.get("status_known"):
                detached_reason = "worktree_status_unknown"
            elif worktree.get("dirty"):
                detached_reason = "dirty_detached_worktree"
            else:
                detached_reason = "prunable_worktree_metadata"
            attention_queue.append(
                {
                    "priority": 92
                    if worktree.get("dirty")
                    else 85
                    if detached_reason == "worktree_status_unknown"
                    else 65,
                    "project_id": project_id,
                    "project_name": project_name,
                    "branch": "(detached HEAD)",
                    "worktree_path": worktree["path"],
                    "last_activity_at": last_activity,
                    "inactive_days": _days_since(last_activity, observed_at),
                    "reasons": [detached_reason],
                    "next_action": (
                        "Re-scan or inspect this worktree directly; DAD could not establish clean or dirty state."
                        if detached_reason == "worktree_status_unknown"
                        else "Checkpoint or attach this work to a named branch before cleanup."
                    ),
                    "evidence": {
                        "dirty": worktree.get("dirty"),
                        "changed_path_count": int(worktree.get("changed_path_count", 0)),
                        "ahead": 0,
                        "behind": 0,
                        "merged_by_ancestry": False,
                        "upstream": "",
                        "worktree_locked": worktree.get("locked", False),
                    },
                }
            )
        projects.append(
            {
                "project_id": project_id,
                "name": project_name,
                "common_git_dir": str(common_dir),
                "remote_url": remote_url,
                "default_branch": default_branch,
                "active_within_threshold": project_active,
                "worktrees": sorted(worktrees, key=lambda item: item["path"].casefold()),
                "branches": sorted(branches, key=lambda item: item["name"].casefold()),
                "related_projects": [],
            }
        )

    _attach_related_projects(projects, limit=settings.related_limit)
    attention_queue.sort(
        key=lambda item: (
            -item["priority"],
            item["project_name"].casefold(),
            item["branch"].casefold(),
        )
    )
    dirty_worktree_count = sum(
        1 for project in projects for worktree in project["worktrees"] if worktree["dirty"] is True
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": observed_at.isoformat(),
        "status": "generated_candidate",
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "scan": {
            "roots": [str(root.resolve()) for root in settings.roots],
            "stale_days": settings.stale_days,
            "max_depth": settings.max_depth,
            "related_limit": settings.related_limit,
            "discovered_checkout_count": len(checkouts),
            "errors": scan_errors,
        },
        "summary": {
            "project_count": len(projects),
            "branch_count": sum(len(project["branches"]) for project in projects),
            "worktree_count": sum(len(project["worktrees"]) for project in projects),
            "dirty_worktree_count": dirty_worktree_count,
            "attention_item_count": len(attention_queue),
            "today_item_count": min(3, len(attention_queue)),
        },
        "today": attention_queue[:3],
        "attention_queue": attention_queue,
        "projects": projects,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def portfolio_attention_html(report: dict[str, Any]) -> str:
    """Render a self-contained local dashboard with escaped metadata."""

    summary = report["summary"]
    today_cards: list[str] = []
    for item in report["today"]:
        reasons = " · ".join(str(reason).replace("_", " ") for reason in item["reasons"])
        today_cards.append(
            f"""
            <article class="attention-card priority-{min(9, item["priority"] // 10)}">
              <div class="eyebrow">Priority {item["priority"]} · {escape(reasons)}</div>
              <h3>{escape(item["project_name"])} <span>{escape(item["branch"])}</span></h3>
              <p>{escape(item["next_action"])}</p>
              <code>{escape(item.get("worktree_path") or "No checked-out worktree")}</code>
            </article>
            """
        )
    if not today_cards:
        today_cards.append(
            '<article class="attention-card"><h3>No urgent items</h3><p>The scan found no branch or worktree requiring attention.</p></article>'
        )

    queue_rows: list[str] = []
    for item in report["attention_queue"]:
        reasons = ", ".join(str(reason).replace("_", " ") for reason in item["reasons"])
        search_text = " ".join(
            [item["project_name"], item["branch"], reasons, item.get("worktree_path", "")]
        ).casefold()
        queue_rows.append(
            f"""
            <tr data-search="{escape(search_text, quote=True)}">
              <td><strong>{item["priority"]}</strong></td>
              <td>{escape(item["project_name"])}</td>
              <td><code>{escape(item["branch"])}</code></td>
              <td>{escape(reasons)}</td>
              <td>{escape(str(item.get("inactive_days") if item.get("inactive_days") is not None else "unknown"))}</td>
              <td>{escape(item["next_action"])}</td>
            </tr>
            """
        )

    project_cards: list[str] = []
    for project in report["projects"]:
        related = ", ".join(item["project_name"] for item in project["related_projects"])
        project_cards.append(
            f"""
            <article class="project-card" data-search="{escape((project["name"] + " " + related).casefold(), quote=True)}">
              <div class="eyebrow">{len(project["branches"])} branches · {len(project["worktrees"])} worktrees</div>
              <h3>{escape(project["name"])}</h3>
              <p>Default: <code>{escape(project["default_branch"] or "unknown")}</code></p>
              <p>Related candidates: {escape(related or "none yet")}</p>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DAD Portfolio Attention</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0b1020; --panel:#141b2d; --line:#27314a; --text:#edf2ff; --muted:#9eabc7; --accent:#8bb8ff; --warn:#ffca70; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:linear-gradient(135deg,#080c18,#101a31 55%,#0b1020); color:var(--text); font:15px/1.5 Inter,ui-sans-serif,system-ui,sans-serif; }}
    main {{ width:min(1380px,94vw); margin:0 auto; padding:48px 0 80px; }} h1 {{ font-size:clamp(2rem,5vw,4.5rem); line-height:.95; margin:.25rem 0 1rem; max-width:900px; }} h2 {{ margin-top:3rem; }} h3 {{ margin:.35rem 0; }} h3 span {{ color:var(--muted); font-weight:500; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.11em; color:var(--accent); font-size:.72rem; font-weight:800; }} .muted {{ color:var(--muted); max-width:900px; }}
    .stats {{ display:grid; grid-template-columns:repeat(5,minmax(120px,1fr)); gap:12px; margin:28px 0; }} .stat,.attention-card,.project-card,.table-wrap {{ background:rgba(20,27,45,.9); border:1px solid var(--line); border-radius:18px; box-shadow:0 18px 50px rgba(0,0,0,.16); }}
    .stat {{ padding:18px; }} .stat strong {{ display:block; font-size:2rem; }} .stat span {{ color:var(--muted); }}
    .today {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }} .attention-card,.project-card {{ padding:20px; }} .attention-card p {{ min-height:48px; }} code {{ color:#b9d4ff; overflow-wrap:anywhere; }}
    .search {{ width:100%; margin:12px 0 18px; padding:13px 16px; border-radius:12px; border:1px solid var(--line); background:#0f1628; color:var(--text); }}
    .table-wrap {{ overflow:auto; }} table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:13px 15px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} th {{ position:sticky; top:0; background:#151d30; color:var(--muted); font-size:.76rem; text-transform:uppercase; letter-spacing:.08em; }}
    .projects {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; }} footer {{ margin-top:48px; color:var(--muted); border-top:1px solid var(--line); padding-top:20px; }}
    @media (max-width:900px) {{ .stats,.today {{ grid-template-columns:1fr 1fr; }} }} @media (max-width:620px) {{ .stats,.today {{ grid-template-columns:1fr; }} main {{ padding-top:28px; }} }}
  </style>
</head>
<body>
<main>
  <div class="eyebrow">DAD · Local portfolio control plane</div>
  <h1>What needs your attention?</h1>
  <p class="muted">Read-only Git metadata, grouped by project. Suggestions are candidates; DAD never cleans, deletes, commits, or changes another repository from this view.</p>
  <section class="stats">
    <div class="stat"><strong>{summary["project_count"]}</strong><span>projects</span></div>
    <div class="stat"><strong>{summary["branch_count"]}</strong><span>branches</span></div>
    <div class="stat"><strong>{summary["worktree_count"]}</strong><span>worktrees</span></div>
    <div class="stat"><strong>{summary["dirty_worktree_count"]}</strong><span>dirty worktrees</span></div>
    <div class="stat"><strong>{summary["attention_item_count"]}</strong><span>attention items</span></div>
  </section>
  <h2>Today</h2>
  <section class="today">{"".join(today_cards)}</section>
  <h2>Full attention queue</h2>
  <input class="search" id="queue-search" placeholder="Filter by project, branch, path, or reason" aria-label="Filter attention queue">
  <div class="table-wrap"><table><thead><tr><th>Priority</th><th>Project</th><th>Branch</th><th>Why</th><th>Idle days</th><th>Suggested next action</th></tr></thead><tbody id="queue-body">{"".join(queue_rows)}</tbody></table></div>
  <h2>Projects and related-work candidates</h2>
  <section class="projects">{"".join(project_cards)}</section>
  <footer>Generated {escape(report["generated_at"])}. {escape(report["authority_boundary"])}</footer>
</main>
<script>
  const input = document.getElementById('queue-search');
  input.addEventListener('input', () => {{
    const query = input.value.toLowerCase().trim();
    document.querySelectorAll('#queue-body [data-search]').forEach(row => {{ row.hidden = query && !row.dataset.search.includes(query); }});
  }});
</script>
</body>
</html>
"""


def write_portfolio_attention_outputs(hub_root: Path, report: dict[str, Any]) -> dict[str, Any]:
    report_dir = data_path(hub_root, "central_reports")
    json_path = report_dir / "portfolio_attention.json"
    html_path = report_dir / "portfolio_attention.html"
    atomic_write_text(json_path, json_dumps(report, pretty=True) + "\n")
    atomic_write_text(html_path, portfolio_attention_html(report))
    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
        "summary": report["summary"],
        "status": report["status"],
        "authority_boundary": report["authority_boundary"],
        "generated_at": report.get("generated_at", utc_now()),
    }


__all__ = [
    "AUTHORITY_BOUNDARY",
    "PortfolioScanSettings",
    "build_portfolio_attention_report",
    "discover_git_checkouts",
    "portfolio_attention_html",
    "write_portfolio_attention_outputs",
]
