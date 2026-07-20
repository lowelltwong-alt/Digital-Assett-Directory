"""Bounded read-only Git adapter for the portfolio convergence core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Iterable

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .portfolio_cockpit import projection_hash, schema_validation_problems
from .portfolio_convergence import (
    BranchEvidence,
    MAX_PROPOSALS,
    PairDistance,
    branch_pair_key,
    candidate_precedence,
    finalize_report,
    validate_convergence_report as validate_core_convergence_report,
)
from .portfolio_relations import idea_tokens
from .transport import data_path
from .utils import atomic_write_text, json_dumps


ADAPTER_ID = "runtime-adapter:git-convergence-readonly"
ADAPTER_REVISION_ID = "runtime-adapter-revision:git-convergence-readonly:0.2.0"
EXPECTED_SOURCE_SCHEMA = "dad.portfolio_attention.v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class GitConvergenceSettings:
    proposal_limit: int = MAX_PROPOSALS
    max_projects: int = 64
    max_branches_per_project: int = 64
    max_candidate_distances: int = 64
    max_paths_per_branch: int = 500
    max_git_commands: int = 512
    max_output_bytes_per_command: int = 1_048_576
    max_total_output_bytes: int = 8_388_608
    max_total_seconds: float = 60.0
    git_timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        if not 1 <= self.proposal_limit <= MAX_PROPOSALS:
            raise ValueError(f"proposal_limit must be between 1 and {MAX_PROPOSALS}")
        if not 1 <= self.max_projects <= 256:
            raise ValueError("max_projects must be between 1 and 256")
        if not 2 <= self.max_branches_per_project <= 256:
            raise ValueError("max_branches_per_project must be between 2 and 256")
        if not 1 <= self.max_candidate_distances <= 2_000:
            raise ValueError("max_candidate_distances must be between 1 and 2000")
        if not 1 <= self.max_paths_per_branch <= 10_000:
            raise ValueError("max_paths_per_branch must be between 1 and 10000")
        if not 1 <= self.max_git_commands <= 10_000:
            raise ValueError("max_git_commands must be between 1 and 10000")
        if not 1_024 <= self.max_output_bytes_per_command <= 8_388_608:
            raise ValueError("max_output_bytes_per_command must be between 1024 and 8388608")
        if not (self.max_output_bytes_per_command <= self.max_total_output_bytes <= 268_435_456):
            raise ValueError(
                "max_total_output_bytes must cover one command and be at most 268435456"
            )
        if not 1 <= self.max_total_seconds <= 600:
            raise ValueError("max_total_seconds must be between 1 and 600")
        if not 1 <= self.git_timeout_seconds <= 120:
            raise ValueError("git_timeout_seconds must be between 1 and 120")


@dataclass(slots=True)
class _GitCounter:
    command_count: int = 0
    output_bytes: int = 0
    truncated_command_count: int = 0
    started_at: float = field(default_factory=time.monotonic)
    exhausted: bool = False


class _GitObservationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _run_git(
    command: list[str],
    *,
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> subprocess.CompletedProcess[bytes]:
    elapsed = time.monotonic() - counter.started_at
    remaining_seconds = settings.max_total_seconds - elapsed
    remaining_bytes = settings.max_total_output_bytes - counter.output_bytes
    if counter.command_count >= settings.max_git_commands or remaining_seconds <= 0:
        counter.exhausted = True
        raise _GitObservationError("observation_budget_exhausted")
    if remaining_bytes <= 0:
        counter.exhausted = True
        raise _GitObservationError("observation_output_budget_exhausted")
    output_limit = min(settings.max_output_bytes_per_command, remaining_bytes)
    timeout = min(settings.git_timeout_seconds, remaining_seconds)
    counter.command_count += 1
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    assert process.stdout is not None
    chunks: list[bytes] = []
    size = 0
    truncated = False

    def _read_stdout() -> None:
        nonlocal size, truncated
        while True:
            chunk = process.stdout.read(65_536)
            if not chunk:
                return
            room = output_limit - size
            if len(chunk) > room:
                if room > 0:
                    chunks.append(chunk[:room])
                    size += room
                truncated = True
                process.kill()
                return
            chunks.append(chunk)
            size += len(chunk)

    reader = threading.Thread(target=_read_stdout, daemon=True)
    reader.start()
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait()
    reader.join(timeout=2)
    if reader.is_alive():
        process.kill()
        reader.join(timeout=2)
        timed_out = True
    counter.output_bytes += size
    if truncated:
        counter.truncated_command_count += 1
        if counter.output_bytes >= settings.max_total_output_bytes:
            counter.exhausted = True
        raise _GitObservationError("git_output_truncated")
    if timed_out:
        if time.monotonic() - counter.started_at >= settings.max_total_seconds:
            counter.exhausted = True
        raise _GitObservationError("git_command_timeout")
    return subprocess.CompletedProcess(
        command,
        returncode,
        stdout=b"".join(chunks),
        stderr=b"",
    )


def _git(
    *,
    common_git_dir: Path,
    args: Iterable[str],
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> subprocess.CompletedProcess[bytes]:
    return _run_git(
        [
            "git",
            f"--git-dir={common_git_dir}",
            "-c",
            "core.quotepath=false",
            *args,
        ],
        settings=settings,
        counter=counter,
    )


def _git_worktree(
    *,
    worktree: Path,
    args: Iterable[str],
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> subprocess.CompletedProcess[bytes]:
    return _run_git(
        ["git", "-C", str(worktree), "-c", "core.quotepath=false", *args],
        settings=settings,
        counter=counter,
    )


def _decoded(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stdout.decode("utf-8", errors="replace").strip()


def _nul_paths(data: bytes) -> list[str]:
    return sorted(
        {
            value.decode("utf-8", errors="replace").replace("\\", "/")
            for value in data.split(b"\0")
            if value
        }
    )


def _status_paths(data: bytes) -> list[str]:
    parts = data.split(b"\0")
    paths: set[str] = set()
    index = 0
    while index < len(parts):
        raw = parts[index]
        index += 1
        if not raw or len(raw) < 4:
            continue
        status = raw[:2].decode("ascii", errors="replace")
        path = raw[3:].decode("utf-8", errors="replace").replace("\\", "/")
        if path:
            paths.add(path)
        if "R" in status or "C" in status:
            if index < len(parts) and parts[index]:
                paths.add(parts[index].decode("utf-8", errors="replace").replace("\\", "/"))
            index += 1
    return sorted(paths)


def _problem(
    code: str,
    *,
    project_id: str,
    branch: str = "",
) -> dict[str, str]:
    return {"project_id": project_id, "branch": branch, "code": code}


def _branch_order(row: dict[str, Any]) -> tuple[bool, int, str, str]:
    idle = row.get("inactive_days")
    return (
        bool(row.get("merged")),
        idle if isinstance(idle, int) else 10**9,
        str(row.get("name", "")).casefold(),
        str(row.get("head", "")),
    )


def _collect_branch(
    project: dict[str, Any],
    branch: dict[str, Any],
    *,
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> tuple[BranchEvidence, list[dict[str, str]]]:
    project_id = str(project["project_id"])
    branch_name = str(branch["name"])
    common_git_dir = Path(str(project["common_git_dir"])).resolve()
    head = str(branch["head"])
    default_branch = str(project["default_branch"])
    problems: list[dict[str, str]] = []
    problem_codes: list[str] = []

    try:
        merge_base = _git(
            common_git_dir=common_git_dir,
            args=("merge-base", f"refs/heads/{default_branch}", head),
            settings=settings,
            counter=counter,
        )
    except (OSError, subprocess.SubprocessError, _GitObservationError):
        merge_base = None
    if merge_base is None or merge_base.returncode != 0 or not _decoded(merge_base):
        problem_codes.append("default_merge_base_unknown")
        problems.append(
            _problem(
                "default_merge_base_unknown",
                project_id=project_id,
                branch=branch_name,
            )
        )
        committed_paths: list[str] = []
    else:
        base = _decoded(merge_base)
        try:
            diff = _git(
                common_git_dir=common_git_dir,
                args=(
                    "diff",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACDMRTUXB",
                    f"{base}..{head}",
                    "--",
                ),
                settings=settings,
                counter=counter,
            )
        except (OSError, subprocess.SubprocessError, _GitObservationError):
            diff = None
        if diff is None or diff.returncode != 0:
            problem_codes.append("branch_diff_unknown")
            problems.append(
                _problem("branch_diff_unknown", project_id=project_id, branch=branch_name)
            )
            committed_paths = []
        else:
            committed_paths = _nul_paths(diff.stdout)

    dirty_paths: list[str] = []
    worktree_path = str(branch.get("worktree_path", "")).strip()
    if branch.get("dirty") is True and worktree_path:
        try:
            status = _git_worktree(
                worktree=Path(worktree_path),
                args=("status", "--porcelain=v1", "-z", "--untracked-files=normal"),
                settings=settings,
                counter=counter,
            )
        except (OSError, subprocess.SubprocessError, _GitObservationError):
            status = None
        if status is None or status.returncode != 0:
            problem_codes.append("dirty_worktree_paths_unknown")
            problems.append(
                _problem(
                    "dirty_worktree_paths_unknown",
                    project_id=project_id,
                    branch=branch_name,
                )
            )
        else:
            dirty_paths = _status_paths(status.stdout)

    all_paths = sorted(set(committed_paths) | set(dirty_paths))
    paths_truncated = len(all_paths) > settings.max_paths_per_branch
    if paths_truncated:
        problem_codes.append("touched_paths_truncated")
        problems.append(
            _problem("touched_paths_truncated", project_id=project_id, branch=branch_name)
        )
        all_paths = all_paths[: settings.max_paths_per_branch]
    evidence = BranchEvidence(
        project_id=project_id,
        project_name=str(project["name"]),
        branch_name=branch_name,
        head=head,
        default_branch=default_branch,
        name_tokens=tuple(sorted(idea_tokens(branch_name))),
        touched_paths=tuple(all_paths),
        worktree_present=bool(worktree_path),
        dirty_worktree=branch.get("dirty") if worktree_path else None,
        paths_truncated=paths_truncated,
        problems=tuple(sorted(set(problem_codes))),
    )
    return evidence, problems


def _distance(
    left: BranchEvidence,
    right: BranchEvidence,
    *,
    common_git_dir: Path,
    settings: GitConvergenceSettings,
    counter: _GitCounter,
) -> PairDistance:
    try:
        merge_base = _git(
            common_git_dir=common_git_dir,
            args=("merge-base", left.head, right.head),
            settings=settings,
            counter=counter,
        )
        counts = _git(
            common_git_dir=common_git_dir,
            args=("rev-list", "--left-right", "--count", f"{left.head}...{right.head}"),
            settings=settings,
            counter=counter,
        )
    except (OSError, subprocess.SubprocessError, _GitObservationError):
        return PairDistance(status="unknown", problems=("pair_git_command_failed",))
    base = _decoded(merge_base)
    fields = _decoded(counts).split()
    if merge_base.returncode != 0 or counts.returncode != 0 or not base or len(fields) != 2:
        return PairDistance(status="unknown", problems=("merge_base_distance_unknown",))
    try:
        left_count, right_count = (int(value) for value in fields)
    except ValueError:
        return PairDistance(status="unknown", problems=("merge_base_distance_invalid",))
    return PairDistance(
        status="observed",
        merge_base=base,
        left_commits=left_count,
        right_commits=right_count,
    )


def build_git_convergence_report(
    attention_report: dict[str, Any],
    *,
    schema_root: Path,
    settings: GitConvergenceSettings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect bounded Git evidence and project a top-five candidate report."""

    effective = settings or GitConvergenceSettings()
    schema_problems = schema_validation_problems(
        attention_report,
        schema_root,
        "portfolio_attention_report",
    )
    if attention_report.get("schema_version") != EXPECTED_SOURCE_SCHEMA or schema_problems:
        raise ValueError(
            "portfolio attention source is not schema-valid: "
            + ", ".join(schema_problems or ["unexpected_schema"])
        )
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    counter = _GitCounter()
    branches: list[BranchEvidence] = []
    problems: list[dict[str, str]] = []
    common_dirs: dict[str, Path] = {}

    project_rows = sorted(
        attention_report.get("projects", []),
        key=lambda row: str(row.get("project_id", "")),
    )
    if len(project_rows) > effective.max_projects:
        problems.append(_problem("project_budget_truncated", project_id="portfolio"))
        project_rows = project_rows[: effective.max_projects]

    for project in project_rows:
        if counter.exhausted:
            break
        project_id = str(project.get("project_id", ""))
        default_branch = str(project.get("default_branch", ""))
        common_dir = Path(str(project.get("common_git_dir", ""))).resolve()
        if not project_id or not default_branch or not common_dir.is_dir():
            problems.append(
                _problem("project_git_metadata_invalid", project_id=project_id or "unknown")
            )
            continue
        common_dirs[project_id] = common_dir
        eligible = [
            row
            for row in project.get("branches", [])
            if str(row.get("name", ""))
            and str(row.get("head", ""))
            and str(row.get("name", "")) != default_branch
            and not bool(row.get("merged"))
        ]
        eligible.sort(key=_branch_order)
        if len(eligible) > effective.max_branches_per_project:
            problems.append(_problem("branch_budget_truncated", project_id=project_id))
            eligible = eligible[: effective.max_branches_per_project]
        for branch in eligible:
            if counter.exhausted:
                break
            evidence, branch_problems = _collect_branch(
                project,
                branch,
                settings=effective,
                counter=counter,
            )
            branches.append(evidence)
            problems.extend(branch_problems)

    qualified: list[tuple[tuple[float, int, int, str, str], BranchEvidence, BranchEvidence]] = []
    by_project: dict[str, list[BranchEvidence]] = {}
    for branch in branches:
        by_project.setdefault(branch.project_id, []).append(branch)
    for project_id in sorted(by_project):
        rows = sorted(by_project[project_id], key=lambda row: row.branch_name.casefold())
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                precedence = candidate_precedence(left, right)
                if precedence is not None:
                    qualified.append((precedence, left, right))
    qualified.sort(
        key=lambda row: (
            -row[0][0],
            -row[0][1],
            -row[0][2],
            row[0][3],
            row[0][4],
        )
    )
    if len(qualified) > effective.max_candidate_distances:
        problems.append(_problem("distance_budget_truncated", project_id="portfolio"))
        qualified = qualified[: effective.max_candidate_distances]
    distances: dict[str, PairDistance] = {}
    for _precedence, left, right in qualified:
        if counter.exhausted:
            break
        distances[branch_pair_key(left, right)] = _distance(
            left,
            right,
            common_git_dir=common_dirs[left.project_id],
            settings=effective,
            counter=counter,
        )
    if counter.exhausted:
        problems.append(_problem("observation_budget_exhausted", project_id="portfolio"))
    if counter.truncated_command_count:
        problems.append(_problem("git_output_truncated", project_id="portfolio"))

    source = {
        "schema_version": EXPECTED_SOURCE_SCHEMA,
        "generated_at": str(attention_report.get("generated_at", "")),
        "fingerprint": projection_hash(attention_report),
        "project_count": len(attention_report.get("projects", [])),
    }
    producer = {
        "producer_id": ADAPTER_ID,
        "producer_revision_id": ADAPTER_REVISION_ID,
        "observation_count": counter.command_count,
        "source_write_count": 0,
        "bounded": True,
        "problems_recorded": True,
        "details": {
            "git_command_count": counter.command_count,
            "git_output_bytes": counter.output_bytes,
            "truncated_command_count": counter.truncated_command_count,
            "git_timeout_seconds": effective.git_timeout_seconds,
            "max_projects": effective.max_projects,
            "max_branches_per_project": effective.max_branches_per_project,
            "max_candidate_distances": effective.max_candidate_distances,
            "max_paths_per_branch": effective.max_paths_per_branch,
            "max_git_commands": effective.max_git_commands,
            "max_output_bytes_per_command": effective.max_output_bytes_per_command,
            "max_total_output_bytes": effective.max_total_output_bytes,
            "max_total_seconds": effective.max_total_seconds,
            "git_optional_locks": False,
        },
    }
    return finalize_report(
        generated_at=observed.isoformat(),
        source=source,
        branches=branches,
        distances=distances,
        producer=producer,
        problems=problems,
        proposal_limit=effective.proposal_limit,
    )


def validate_convergence_report(schema_root: Path, report: dict[str, Any]) -> None:
    validate_core_convergence_report(schema_root, report)
    schema = json.loads(
        (schema_root / "schemas/portfolio-convergence-git-producer-receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=FormatChecker()).validate(report["producer"])


def write_convergence_report(hub_root: Path, report: dict[str, Any]) -> dict[str, Any]:
    validate_convergence_report(hub_root, report)
    path = data_path(hub_root, "central_reports") / "portfolio_os/convergence-radar.json"
    atomic_write_text(path, json_dumps(report, pretty=True) + "\n")
    return {
        "path": str(path),
        "status": report["status"],
        "summary": report["summary"],
        "candidate_only": True,
        "execution_authorized": False,
    }
