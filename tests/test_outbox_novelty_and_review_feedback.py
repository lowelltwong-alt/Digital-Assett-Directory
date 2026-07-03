from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.learning import add_review_feedback, build_lesson_graph
from digital_asset_directory.mail_center import check_outbox_novelty, compose_mail

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _compose_first(repo: Path) -> dict:
    return compose_mail(
        repo,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Adopt the rust shadow parity timing harness",
        payload={"asset_id": "dad:offering:rust-shadow-parity-harness"},
        evidence=["assets/coding-harnesses/rust-shadow-parity-harness"],
    )


def test_reworded_near_duplicate_is_blocked_and_supersede_links_thread(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    first = _compose_first(repo)
    assert first["appended"] is True
    assert first["novelty_check"]["verdict"] == "new"
    first_mail_id = first["record"]["mail_id"]

    check = check_outbox_novelty(
        repo,
        message_type="asset_suggestion",
        summary="Use the rust shadow parity harness for timing",
        payload={"asset_id": "dad:offering:rust-shadow-parity-harness"},
        evidence=["assets/coding-harnesses/rust-shadow-parity-harness"],
    )
    assert check["verdict"] == "already_sent_similar"
    assert check["matches"][0]["mail_id"] == first_mail_id

    with pytest.raises(ValueError, match="Near-duplicate"):
        compose_mail(
            repo,
            message_type="asset_suggestion",
            target_repo="central_only",
            summary="Use the rust shadow parity harness for timing",
            payload={"asset_id": "dad:offering:rust-shadow-parity-harness"},
            evidence=["assets/coding-harnesses/rust-shadow-parity-harness"],
        )

    upgrade = compose_mail(
        repo,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Parity harness upgrade: found three mismatch classes in chunker coverage",
        payload={"asset_id": "dad:offering:rust-shadow-parity-harness"},
        evidence=["assets/coding-harnesses/rust-shadow-parity-harness"],
        supersedes=first_mail_id,
    )
    assert upgrade["appended"] is True
    assert upgrade["record"]["thread_id"] == first["record"]["thread_id"]
    assert upgrade["record"]["payload"]["supersedes"] == first_mail_id
    assert upgrade["supersedes"] == first_mail_id


def test_allow_similar_overrides_block_and_unrelated_is_new(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _compose_first(repo)

    forced = compose_mail(
        repo,
        message_type="asset_suggestion",
        target_repo="central_only",
        summary="Adopt the rust shadow parity timing harness today",
        payload={"asset_id": "dad:offering:rust-shadow-parity-harness"},
        evidence=["assets/coding-harnesses/rust-shadow-parity-harness"],
        allow_similar=True,
    )
    assert forced["appended"] is True
    assert forced["novelty_check"]["verdict"] == "already_sent_similar"

    unrelated = check_outbox_novelty(
        repo,
        message_type="governance_notice",
        summary="Quarterly data map drift report for downstream repos",
    )
    assert unrelated["verdict"] == "new"
    assert unrelated["matches"] == []


def test_supersede_unknown_mail_raises(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="unknown outbox mail"):
        compose_mail(
            repo,
            message_type="asset_suggestion",
            target_repo="central_only",
            summary="anything",
            supersedes="dad:mail:does-not-exist",
        )


def test_review_feedback_intake_creates_minable_lesson(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    record = add_review_feedback(
        hub,
        hub / "catalog.db",
        repository=str(tmp_path / "repo-one"),
        task="review the mail center changes",
        agent="fable",
        model="claude-fable-5",
        review_type="red_team",
        severity="high",
        findings=[
            "compose path skips redaction when payload is empty",
            "novelty threshold untested at exactly 0.6",
        ],
        confirmed=["compose path skips redaction when payload is empty"],
        recommendations=["add boundary test at similarity 0.6"],
        paths=["src/digital_asset_directory/mail_center.py"],
    )
    assert "red_team feedback from fable" in record.summary
    assert "feedback_code=DAD_REVIEW_FEEDBACK_V1" in record.lessons
    assert "swe_review_feedback_loop" in record.reusable_patterns
    assert record.missing_capabilities == ["red_team"]
    assert any(line.startswith("finding=") for line in record.lessons)
    assert (hub / "raw" / "lessons" / "by-capability" / "red-team.jsonl").exists()

    with pytest.raises(ValueError, match="review_type"):
        add_review_feedback(
            hub,
            hub / "catalog.db",
            repository="r",
            task="t",
            agent="codex",
            review_type="vibes_check",
            findings=["x"],
        )
    with pytest.raises(ValueError, match="finding"):
        add_review_feedback(
            hub,
            hub / "catalog.db",
            repository="r",
            task="t",
            agent="codex",
            review_type="audit",
            findings=["   "],
        )


def test_review_feedback_lessons_link_to_pattern_card_in_graph(tmp_path: Path):
    hub = tmp_path / "hub"
    (hub / "registry").mkdir(parents=True)
    real_patterns = json.loads(
        (ROOT / "registry" / "asset-pattern-registry.json").read_text(encoding="utf-8")
    )
    assert "swe_review_feedback_loop" in {p["id"] for p in real_patterns["patterns"]}
    (hub / "registry" / "asset-pattern-registry.json").write_text(
        json.dumps(real_patterns), encoding="utf-8"
    )
    (hub / "registry" / "dad-offerings-registry.json").write_text(
        json.dumps({"offerings": []}), encoding="utf-8"
    )
    add_review_feedback(
        hub,
        hub / "catalog.db",
        repository=str(tmp_path / "repo-one"),
        task="premortem the enrollment wave",
        agent="opus",
        review_type="premortem",
        findings=["wave plan assumes hub path never moves"],
    )
    graph = build_lesson_graph(hub)["graph"]
    assert graph["edges_by_type"].get("matches_pattern") == 1
    pattern_edge = next(
        edge for edge in graph["edges"] if edge["edge_type"] == "matches_pattern"
    )
    assert pattern_edge["target"] == "pattern:swe_review_feedback_loop"
