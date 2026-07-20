from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from digital_asset_directory.portfolio_convergence import (
    BranchEvidence,
    PairDistance,
    branch_pair_key,
    finalize_report,
    rank_candidates,
    validate_convergence_report,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)


def _branch(
    name: str,
    head: str,
    *,
    paths: tuple[str, ...],
    tokens: tuple[str, ...],
) -> BranchEvidence:
    return BranchEvidence(
        project_id="dad:project:test",
        project_name="DAD",
        branch_name=name,
        head=head,
        default_branch="main",
        name_tokens=tokens,
        touched_paths=paths,
    )


def test_core_is_deterministic_bounded_and_provider_neutral() -> None:
    left = _branch(
        "work/cockpit-refresh-a",
        "a" * 40,
        paths=("src/cockpit.py", "tests/test_cockpit.py"),
        tokens=("cockpit", "refresh"),
    )
    right = _branch(
        "work/cockpit-refresh-b",
        "b" * 40,
        paths=("src/cockpit.py",),
        tokens=("cockpit", "refresh"),
    )
    distance = PairDistance(
        status="observed",
        merge_base="d" * 40,
        left_commits=2,
        right_commits=3,
    )
    distances = {branch_pair_key(left, right): distance}

    first, coverage = rank_candidates([left, right], distances)
    second, _ = rank_candidates([right, left], distances)

    assert first == second
    assert coverage["qualified_pair_count"] == 1
    assert first[0]["score_kind"] == "ordinal_review_priority_not_probability"
    assert first[0]["execution_authorized"] is False


def test_core_report_accepts_a_non_git_producer_receipt() -> None:
    report = finalize_report(
        generated_at=NOW.isoformat(),
        source={
            "schema_version": "dad.portfolio_attention.v1",
            "generated_at": NOW.isoformat(),
            "fingerprint": "sha256:" + "a" * 64,
            "project_count": 0,
        },
        branches=[],
        distances={},
        producer={
            "producer_id": "fixture-observer",
            "producer_revision_id": "fixture-observer:0.1.0",
            "observation_count": 0,
            "source_write_count": 0,
            "bounded": True,
            "problems_recorded": True,
            "details": {"runtime": "fixture"},
        },
    )

    validate_convergence_report(ROOT, report)

    assert report["producer"]["producer_id"] == "fixture-observer"
    assert report["summary"]["proposal_count"] == 0
    assert report["model_call_count"] == 0
    assert report["execution_authorized"] is False
