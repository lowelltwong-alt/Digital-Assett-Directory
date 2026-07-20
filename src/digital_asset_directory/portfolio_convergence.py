"""Provider-neutral branch/worktree convergence candidate projection.

The core consumes bounded, already-observed branch evidence.  It does not run
Git, read a repository, call a model, write a file, or authorize an action.
Scores are ordinal review priority, never a probability or same-intent claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
from jsonschema import FormatChecker
from jsonschema.validators import validator_for


from .ids import stable_id


SCHEMA_VERSION = "dad.portfolio_convergence_report.v1"
METHOD_ID = "dad.branch-worktree-convergence.v1"
MAX_PROPOSALS = 5
MAX_SHARED_PATH_REFS = 12
MAX_SHARED_TOKEN_REFS = 8

AUTHORITY_BOUNDARY = (
    "This report contains deterministic review candidates only. Similar names, "
    "touched paths, or commit proximity do not prove shared intent. The report "
    "cannot merge or close a branch, remove a worktree, dispatch an agent, grant "
    "authority, or mutate any scanned repository."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BranchEvidence:
    """Bounded branch evidence supplied by a runtime adapter."""

    project_id: str
    project_name: str
    branch_name: str
    head: str
    default_branch: str
    name_tokens: tuple[str, ...]
    touched_paths: tuple[str, ...]
    worktree_present: bool = False
    dirty_worktree: bool | None = None
    paths_truncated: bool = False
    problems: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "project_id",
            "project_name",
            "branch_name",
            "head",
            "default_branch",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must be non-empty")
        if len(self.head) < 7:
            raise ValueError("head must contain a Git object identity")
        if tuple(sorted(set(self.name_tokens))) != self.name_tokens:
            raise ValueError("name_tokens must be sorted and unique")
        if tuple(sorted(set(self.touched_paths))) != self.touched_paths:
            raise ValueError("touched_paths must be sorted and unique")


@dataclass(frozen=True, slots=True, kw_only=True)
class PairDistance:
    """Observed distance from the merge base to each branch tip."""

    status: str
    merge_base: str = ""
    left_commits: int | None = None
    right_commits: int | None = None
    problems: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"observed", "unknown"}:
            raise ValueError("distance status must be observed or unknown")
        counts = (self.left_commits, self.right_commits)
        if self.status == "observed":
            if not self.merge_base or any(value is None or value < 0 for value in counts):
                raise ValueError("observed distance requires a merge base and nonnegative counts")
        elif self.merge_base or any(value is not None for value in counts):
            raise ValueError("unknown distance cannot expose partial numeric evidence")

    @property
    def total_commits(self) -> int | None:
        if self.left_commits is None or self.right_commits is None:
            return None
        return self.left_commits + self.right_commits


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return "sha256:" + sha256(payload).hexdigest()


def branch_pair_key(left: BranchEvidence, right: BranchEvidence) -> str:
    """Stable logical pair identity; evidence revisions remain separate."""

    if left.project_id != right.project_id:
        raise ValueError("a convergence pair cannot cross project identity")
    names = sorted((left.branch_name, right.branch_name), key=str.casefold)
    return stable_id("portfolio-convergence-pair", left.project_id, *names)


def pair_revision_id(left: BranchEvidence, right: BranchEvidence) -> str:
    heads = sorted((left.head, right.head))
    evidence_digest = _canonical_digest(
        {
            "heads": heads,
            "left_paths": left.touched_paths,
            "right_paths": right.touched_paths,
            "method_id": METHOD_ID,
        }
    )
    return stable_id(
        "portfolio-convergence-pair-revision",
        branch_pair_key(left, right),
        evidence_digest,
    )


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _pair_sort_key(left: BranchEvidence, right: BranchEvidence) -> tuple[str, str]:
    return tuple(sorted((left.branch_name, right.branch_name), key=str.casefold))  # type: ignore[return-value]


def candidate_precedence(
    left: BranchEvidence, right: BranchEvidence
) -> tuple[float, int, int, str, str] | None:
    """Return a cheap deterministic candidate key or suppress weak evidence."""

    left_names = set(left.name_tokens)
    right_names = set(right.name_tokens)
    left_paths = set(left.touched_paths)
    right_paths = set(right.touched_paths)
    shared_names = left_names & right_names
    shared_paths = left_paths & right_paths
    name_similarity = _jaccard(left_names, right_names)
    path_similarity = _jaccard(left_paths, right_paths)

    qualifies = (
        bool(shared_names and shared_paths)
        or (len(shared_names) >= 2 and name_similarity >= 0.5)
        or (len(shared_paths) >= 2 and path_similarity >= 0.5)
        or left.head == right.head
    )
    if not qualifies:
        return None
    cheap_score = 0.5 * name_similarity + 0.5 * path_similarity
    first, second = _pair_sort_key(left, right)
    return (
        cheap_score,
        len(shared_paths),
        len(shared_names),
        first.casefold(),
        second.casefold(),
    )


def _ordered_pair(
    left: BranchEvidence, right: BranchEvidence
) -> tuple[BranchEvidence, BranchEvidence]:
    return (
        (left, right)
        if (left.branch_name.casefold(), left.branch_name)
        <= (right.branch_name.casefold(), right.branch_name)
        else (right, left)
    )


def build_candidate(
    left: BranchEvidence,
    right: BranchEvidence,
    distance: PairDistance,
) -> dict[str, Any]:
    left, right = _ordered_pair(left, right)
    shared_names = sorted(set(left.name_tokens) & set(right.name_tokens))
    shared_paths = sorted(set(left.touched_paths) & set(right.touched_paths))
    name_similarity = _jaccard(set(left.name_tokens), set(right.name_tokens))
    path_similarity = _jaccard(set(left.touched_paths), set(right.touched_paths))
    total_distance = distance.total_commits
    proximity = 0.0 if total_distance is None else 1.0 / (1.0 + total_distance)
    priority_score = round(
        100.0 * (0.45 * name_similarity + 0.45 * path_similarity + 0.10 * proximity),
        1,
    )
    if priority_score >= 65 and shared_names and shared_paths:
        evidence_band = "strong_review"
    elif priority_score >= 40 or left.head == right.head:
        evidence_band = "review"
    else:
        evidence_band = "weak_review"
    problems = sorted(
        set(
            [
                *left.problems,
                *right.problems,
                *distance.problems,
                *(["left_paths_truncated"] if left.paths_truncated else []),
                *(["right_paths_truncated"] if right.paths_truncated else []),
            ]
        )
    )
    pair_id = branch_pair_key(left, right)
    revision_id = pair_revision_id(left, right)
    return {
        "proposal_id": stable_id("portfolio-convergence-proposal", revision_id, METHOD_ID),
        "pair_id": pair_id,
        "revision_id": revision_id,
        "project_id": left.project_id,
        "project_name": left.project_name,
        "left": {
            "branch": left.branch_name,
            "head": left.head,
            "worktree_present": left.worktree_present,
            "dirty_worktree": left.dirty_worktree,
            "touched_path_count": len(left.touched_paths),
        },
        "right": {
            "branch": right.branch_name,
            "head": right.head,
            "worktree_present": right.worktree_present,
            "dirty_worktree": right.dirty_worktree,
            "touched_path_count": len(right.touched_paths),
        },
        "priority_score": priority_score,
        "score_kind": "ordinal_review_priority_not_probability",
        "evidence_band": evidence_band,
        "evidence": {
            "name_similarity": round(name_similarity, 4),
            "path_similarity": round(path_similarity, 4),
            "shared_name_token_count": len(shared_names),
            "shared_name_tokens": shared_names[:MAX_SHARED_TOKEN_REFS],
            "shared_touched_path_count": len(shared_paths),
            "shared_touched_paths": shared_paths[:MAX_SHARED_PATH_REFS],
            "shared_paths_truncated": len(shared_paths) > MAX_SHARED_PATH_REFS,
            "merge_base_status": distance.status,
            "merge_base": distance.merge_base,
            "left_commits_from_merge_base": distance.left_commits,
            "right_commits_from_merge_base": distance.right_commits,
            "merge_base_distance": total_distance,
        },
        "problems": problems,
        "next_action": (
            "Compare the exact diffs, intent, ownership, and validation evidence; then "
            "choose combine, supersede, resume, or keep separate. Any merge, close, "
            "branch deletion, or worktree removal requires explicit human approval."
        ),
        "human_decision_required": True,
        "candidate_only": True,
        "execution_authorized": False,
    }


def rank_candidates(
    branches: Iterable[BranchEvidence],
    distances: Mapping[str, PairDistance],
    *,
    proposal_limit: int = MAX_PROPOSALS,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Rank bounded candidates while exposing coverage and suppression counts."""

    if not 1 <= proposal_limit <= MAX_PROPOSALS:
        raise ValueError(f"proposal_limit must be between 1 and {MAX_PROPOSALS}")
    grouped: dict[str, list[BranchEvidence]] = {}
    for branch in branches:
        grouped.setdefault(branch.project_id, []).append(branch)

    evaluated_pairs = 0
    qualified: list[tuple[tuple[float, int, int, str, str], BranchEvidence, BranchEvidence]] = []
    for project_id in sorted(grouped):
        rows = sorted(
            grouped[project_id],
            key=lambda row: (row.branch_name.casefold(), row.branch_name),
        )
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                evaluated_pairs += 1
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
    candidates = [
        build_candidate(
            left,
            right,
            distances.get(
                branch_pair_key(left, right),
                PairDistance(status="unknown", problems=("merge_base_distance_not_evaluated",)),
            ),
        )
        for _precedence, left, right in qualified
    ]
    candidates.sort(
        key=lambda row: (
            -row["priority_score"],
            row["project_name"].casefold(),
            row["left"]["branch"].casefold(),
            row["right"]["branch"].casefold(),
            row["proposal_id"],
        )
    )
    return candidates[:proposal_limit], {
        "evaluated_pair_count": evaluated_pairs,
        "qualified_pair_count": len(qualified),
        "suppressed_pair_count": evaluated_pairs - len(qualified),
    }


def finalize_report(
    *,
    generated_at: str,
    source: dict[str, Any],
    branches: Iterable[BranchEvidence],
    distances: Mapping[str, PairDistance],
    producer: dict[str, Any],
    problems: Iterable[dict[str, str]] = (),
    proposal_limit: int = MAX_PROPOSALS,
) -> dict[str, Any]:
    branch_rows = list(branches)
    proposals, pair_counts = rank_candidates(branch_rows, distances, proposal_limit=proposal_limit)
    problem_rows = sorted(
        [dict(row) for row in problems],
        key=lambda row: (
            row.get("project_id", ""),
            row.get("branch", ""),
            row.get("code", ""),
        ),
    )
    body = {
        "source": source,
        "producer": producer,
        "summary": {
            "project_count": len({row.project_id for row in branch_rows}),
            "branch_count": len(branch_rows),
            "proposal_count": len(proposals),
            "problem_count": len(problem_rows),
            **pair_counts,
        },
        "proposals": proposals,
        "problems": problem_rows,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "report_id": "dad:portfolio-convergence:" + _canonical_digest(body).split(":", 1)[1],
        "status": "generated_candidate",
        "method_id": METHOD_ID,
        "model_call_count": 0,
        "model_token_count": 0,
        "candidate_only": True,
        "execution_authorized": False,
        "data_classification": "local_private_metadata",
        "authority_boundary": AUTHORITY_BOUNDARY,
        **body,
    }


def validate_convergence_report(schema_root: Path, report: dict[str, Any]) -> None:
    """Validate the provider-neutral convergence report contract."""

    schema = json.loads(
        (schema_root / "schemas/portfolio-convergence-report.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema, format_checker=FormatChecker()).validate(report)
