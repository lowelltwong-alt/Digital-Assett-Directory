"""Branch disposition check: force a decision on stranded preserve/checkpoint branches.

Why this exists (incident 2026-07-10, lesson dad:lesson:0cf6def7-acf4-5824-b465-c2f9bfe5d305):
``codex/preserve-parallel-orchestration-20260710`` held the entire orchestration
layer for 16 days with no forcing function - four decision records cited as open
gates were unreachable from the default branch. This check makes an
undispositioned stranded branch an ERROR until a named human records what
happens to it in ``registry/branch-disposition-registry.json``. It never merges,
deletes, pushes, or rewrites anything; its job is to force a DECISION, never to
make one (a checkpoint may be a deliberate quarantine of rejected work).

SCOPING RATIONALE - measured on the live repo 2026-07-27 so the next person
knows why 118 branches produce 1 finding and not 118:

- 118 branches under refs/heads; 67 merged into main; 51 unmerged.
- 22 of the unmerged have tips older than the 14-day window.
- Launch scope = stale unmerged branches whose NAME matches the
  preserve/checkpoint/wip/backup/snapshot patterns: exactly 1 finding - the
  incident branch. Zero false positives.
- Widening candidates: 19 more stale unmerged branches touch ``registry/``,
  ``decisions/``, or ``docs/`` in their diff from main. Erroring on all of them
  on day one is the "100+ findings, muted immediately" trap, so they surface as
  a single non-blocking watchlist WARNING; pass
  ``include_sensitive_diff_scope=True`` (CLI ``--include-sensitive-diff``) to
  promote them to errors once the initial backlog is dispositioned.
- DELIBERATE DEVIATION from the originating handoff: a registered worktree does
  NOT exempt a branch. Evidence: 90 of 118 branches have worktrees because
  agent tooling auto-creates one per session and never cleans up - including
  ``C:/tmp/dad-preserved-orchestration`` parked on the incident branch itself
  for its whole 16 stranded days. In this repo worktree presence signals
  parking, not activity; tip freshness is the activity signal. The only
  worktree exemption is the branch currently checked out at ``repo_root``.

Staleness follows the mcp_dependency_map day-granularity convention:
``window_days`` (default 14; the incident ran 16) plus a
``future_skew_seconds`` clock-skew guard - a future-dated commit cannot prove
freshness and is flagged instead.

Dispositions (schema: schemas/branch-disposition-registry.schema.json):

- ``integrate``: should land on the default branch; remains an ERROR until its
  tip is actually reachable from the default branch.
- ``tombstone``: deliberately not integrating; clears the error. Requires a
  non-empty reason - an unexplained tombstone is how the next incident starts.
- ``active``: work in progress; clears until ``review_after``, then errors
  again. An ``active`` row without ``review_after`` is an error (a forever-pass
  hole, not a decision).

All git access goes through the budgeted read-only wrapper in
portfolio_convergence_git with an explicit subcommand allowlist; read-only
behavior is enforced by test.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .portfolio_convergence_git import (
    GitConvergenceSettings,
    _GitCounter,
    _GitObservationError,
    _git_worktree,
)
from .pointer_liveness import resolve_default_branch

REGISTRY_PATH = Path("registry/branch-disposition-registry.json")

DEFAULT_WINDOW_DAYS = 14
DEFAULT_FUTURE_SKEW_SECONDS = 86_400

ISSUE_STRANDED = "branch_stranded_undispositioned"
ISSUE_INTEGRATE_PENDING = "branch_integrate_pending"
ISSUE_ACTIVE_OVERDUE = "branch_active_review_overdue"
ISSUE_ACTIVE_UNDATED = "branch_disposition_review_after_missing"
ISSUE_REASON_MISSING = "branch_disposition_reason_missing"
ISSUE_REGISTRY_UNPARSEABLE = "branch_disposition_registry_unparseable"
ISSUE_ORPHANED = "branch_disposition_orphaned"
ISSUE_FUTURE_TIP = "branch_tip_timestamp_from_future"

_DISPOSITIONS = frozenset({"integrate", "tombstone", "active"})

_NAME_PATTERN = re.compile(
    r"(^|/)(preserve|checkpoint|wip|backup|snapshot)([-/_]|$)"
    r"|[-_](preserve|checkpoint|wip|backup|snapshot)([-_]|$)",
    re.IGNORECASE,
)
_SENSITIVE_PREFIXES = ("registry/", "decisions/", "docs/")

_READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {"for-each-ref", "rev-parse", "diff", "rev-list", "show-ref", "symbolic-ref"}
)


def _read_only_git(
    repo_root: Path,
    args: tuple[str, ...],
    *,
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> tuple[int, str]:
    """Run one allowlisted read-only git command. Blocks anything mutating."""
    if args[0] not in _READ_ONLY_GIT_SUBCOMMANDS:
        raise ValueError(f"Blocked non-read-only git subcommand: {args[0]}")
    result = _git_worktree(
        worktree=repo_root, args=args, settings=settings, counter=counter
    )
    return result.returncode, result.stdout.decode("utf-8", errors="replace")


def _parse_day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def load_branch_disposition_registry(
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return (dispositions by branch, registry errors). Missing file is empty."""
    errors: list[str] = []
    path = repo_root / REGISTRY_PATH
    if not path.exists():
        return {}, errors
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"{ISSUE_REGISTRY_UNPARSEABLE}: {REGISTRY_PATH.as_posix()}: {exc}"]
    by_branch: dict[str, dict[str, Any]] = {}
    for row in payload.get("dispositions", []):
        if not isinstance(row, dict):
            continue
        branch = str(row.get("branch", "")).strip()
        if not branch:
            errors.append(
                f"{ISSUE_REGISTRY_UNPARSEABLE}: disposition row without a branch name"
            )
            continue
        if branch in by_branch:
            errors.append(
                f"{ISSUE_REGISTRY_UNPARSEABLE}: duplicate disposition for branch {branch}"
            )
            continue
        disposition = str(row.get("disposition", "")).strip()
        if disposition not in _DISPOSITIONS:
            errors.append(
                f"{ISSUE_REGISTRY_UNPARSEABLE}: {branch} has unknown disposition "
                f"{disposition!r} (expected one of {sorted(_DISPOSITIONS)})"
            )
            continue
        if not str(row.get("reason", "")).strip():
            errors.append(
                f"{ISSUE_REASON_MISSING}: {branch} disposition {disposition} has an "
                "empty reason; an unexplained disposition is not a decision"
            )
            continue
        by_branch[branch] = row
    return by_branch, errors


def check_branch_dispositions(
    repo_root: Path,
    *,
    now: datetime | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    future_skew_seconds: int = DEFAULT_FUTURE_SKEW_SECONDS,
    include_sensitive_diff_scope: bool = False,
    settings: GitConvergenceSettings | None = None,
) -> dict[str, Any]:
    """Read-only stranded-branch check. Never mutates git state."""
    settings = settings or GitConvergenceSettings()
    counter = _GitCounter()
    clock = now or datetime.now(timezone.utc)
    errors: list[str] = []
    warnings: list[str] = []
    issue_codes: set[str] = set()
    findings: list[dict[str, Any]] = []
    watchlist: list[str] = []

    dispositions, registry_errors = load_branch_disposition_registry(repo_root)
    for message in registry_errors:
        errors.append(message)
        issue_codes.add(message.split(":", 1)[0])

    result: dict[str, Any] = {
        "valid": not errors,
        "default_branch": None,
        "window_days": window_days,
        "branch_count": 0,
        "scoped_branch_count": 0,
        "errors": errors,
        "warnings": warnings,
        "issue_codes": sorted(issue_codes),
        "findings": findings,
        "sensitive_diff_watchlist": watchlist,
        "include_sensitive_diff_scope": include_sensitive_diff_scope,
        "authority_boundary": (
            "Stranded-branch findings force a recorded human decision. This check "
            "never merges, deletes, pushes, or rewrites branches, and a "
            "disposition row never authorizes those actions either."
        ),
    }

    if not (repo_root / ".git").exists():
        # Not a git repository (fixtures, exports): skip silently rather than
        # warn on every synthetic hub.
        result["issue_codes"] = sorted(issue_codes)
        result["valid"] = not errors
        return result
    default_branch = resolve_default_branch(repo_root, settings=settings, counter=counter)
    result["default_branch"] = default_branch
    if default_branch is None:
        warnings.append(
            "branch_disposition_git_unavailable: no resolvable default branch "
            "here; branch disposition check skipped"
        )
        result["issue_codes"] = sorted(issue_codes)
        result["valid"] = not errors
        return result

    try:
        code, out = _read_only_git(
            repo_root,
            (
                "for-each-ref",
                "--format=%(refname:short)%00%(objectname)%00%(committerdate:iso8601-strict)",
                "refs/heads",
            ),
            settings=settings,
            counter=counter,
        )
        merged_code, merged_out = _read_only_git(
            repo_root,
            (
                "for-each-ref",
                f"--merged=refs/heads/{default_branch}",
                "--format=%(refname:short)",
                "refs/heads",
            ),
            settings=settings,
            counter=counter,
        )
        head_code, head_out = _read_only_git(
            repo_root,
            ("rev-parse", "--abbrev-ref", "HEAD"),
            settings=settings,
            counter=counter,
        )
    except (OSError, _GitObservationError) as exc:
        warnings.append(
            f"branch_disposition_git_unavailable: git observation failed ({exc}); "
            "branch disposition check skipped"
        )
        result["issue_codes"] = sorted(issue_codes)
        result["valid"] = not errors
        return result
    if code != 0 or merged_code != 0:
        warnings.append(
            "branch_disposition_git_unavailable: branch enumeration failed; "
            "branch disposition check skipped"
        )
        result["issue_codes"] = sorted(issue_codes)
        result["valid"] = not errors
        return result

    merged = {line.strip() for line in merged_out.splitlines() if line.strip()}
    head_branch = head_out.strip() if head_code == 0 else ""

    branches: list[tuple[str, str, datetime | None]] = []
    for line in out.splitlines():
        parts = line.split("\0")
        if len(parts) != 3:
            continue
        name, sha, raw_date = parts
        try:
            tip_date: datetime | None = datetime.fromisoformat(raw_date)
        except ValueError:
            tip_date = None
        branches.append((name, sha, tip_date))
    result["branch_count"] = len(branches)
    known_branches = {name for name, _sha, _date in branches}

    def _diff_touches_sensitive(sha: str) -> bool:
        try:
            diff_code, diff_out = _read_only_git(
                repo_root,
                ("diff", "--name-only", f"refs/heads/{default_branch}...{sha}"),
                settings=settings,
                counter=counter,
            )
        except (OSError, _GitObservationError):
            return False
        if diff_code != 0:
            return False
        return any(
            line.startswith(_SENSITIVE_PREFIXES) for line in diff_out.splitlines()
        )

    def _ahead_count(sha: str) -> int | None:
        try:
            count_code, count_out = _read_only_git(
                repo_root,
                ("rev-list", "--count", f"refs/heads/{default_branch}..{sha}"),
                settings=settings,
                counter=counter,
            )
        except (OSError, _GitObservationError):
            return None
        if count_code != 0:
            return None
        try:
            return int(count_out.strip())
        except ValueError:
            return None

    scoped: list[dict[str, Any]] = []
    for name, sha, tip_date in branches:
        if name == default_branch or (head_branch and name == head_branch):
            continue
        if name in merged:
            continue
        if tip_date is None:
            continue
        age_seconds = (clock - tip_date).total_seconds()
        if age_seconds < -future_skew_seconds:
            warnings.append(
                f"{ISSUE_FUTURE_TIP}: {name} tip is dated in the future "
                f"({tip_date.isoformat()}); treating it as a stale candidate"
            )
            issue_codes.add(ISSUE_FUTURE_TIP)
        elif age_seconds <= window_days * 86_400:
            continue
        age_days = int(age_seconds // 86_400)
        name_scoped = bool(_NAME_PATTERN.search(name))
        if name_scoped:
            scoped.append({"branch": name, "commit": sha, "age_days": age_days})
            continue
        if _diff_touches_sensitive(sha):
            if include_sensitive_diff_scope:
                scoped.append({"branch": name, "commit": sha, "age_days": age_days})
            else:
                watchlist.append(name)

    if watchlist:
        warnings.append(
            "branch_disposition_sensitive_diff_watchlist: "
            f"{len(watchlist)} stale unmerged branches touch "
            "registry/, decisions/, or docs/ and are widening candidates: "
            + ", ".join(sorted(watchlist))
        )

    result["scoped_branch_count"] = len(scoped)
    for candidate in scoped:
        branch = candidate["branch"]
        row = dispositions.get(branch)
        ahead = _ahead_count(candidate["commit"])
        detail = (
            f"{branch} (tip {candidate['age_days']}d old"
            + (f", {ahead} commits ahead of {default_branch}" if ahead is not None else "")
            + ")"
        )
        finding = {**candidate, "ahead_count": ahead, "disposition": None, "status": "ok"}
        if row is None:
            finding["status"] = ISSUE_STRANDED
            errors.append(
                f"{ISSUE_STRANDED}: {detail} - record integrate/tombstone/active "
                f"in {REGISTRY_PATH.as_posix()}"
            )
            issue_codes.add(ISSUE_STRANDED)
        else:
            disposition = str(row.get("disposition"))
            finding["disposition"] = disposition
            if disposition == "integrate":
                finding["status"] = ISSUE_INTEGRATE_PENDING
                errors.append(
                    f"{ISSUE_INTEGRATE_PENDING}: {detail} - disposition is "
                    f"integrate but the tip is not reachable from {default_branch}"
                )
                issue_codes.add(ISSUE_INTEGRATE_PENDING)
            elif disposition == "active":
                review_after = _parse_day(row.get("review_after"))
                if review_after is None:
                    finding["status"] = ISSUE_ACTIVE_UNDATED
                    errors.append(
                        f"{ISSUE_ACTIVE_UNDATED}: {detail} - active disposition "
                        "requires review_after; an undated active row never re-raises"
                    )
                    issue_codes.add(ISSUE_ACTIVE_UNDATED)
                elif clock.date() > review_after:
                    finding["status"] = ISSUE_ACTIVE_OVERDUE
                    errors.append(
                        f"{ISSUE_ACTIVE_OVERDUE}: {detail} - active review window "
                        f"expired {review_after.isoformat()}; re-decide its disposition"
                    )
                    issue_codes.add(ISSUE_ACTIVE_OVERDUE)
            # tombstone: cleared; reason was enforced at registry load.
        findings.append(finding)

    for branch in sorted(dispositions):
        if branch not in known_branches:
            warnings.append(
                f"{ISSUE_ORPHANED}: disposition recorded for {branch} but no such "
                "local branch exists (deleted or renamed); row can be retired"
            )
            issue_codes.add(ISSUE_ORPHANED)

    result["issue_codes"] = sorted(issue_codes)
    result["valid"] = not errors
    return result
