import json
from pathlib import Path

from digital_asset_directory.database import CatalogDB
from digital_asset_directory.learning import (
    load_learning_rules,
    match_learning_rules,
    midflight,
    postflight,
    preflight,
)

import pytest

pytestmark = pytest.mark.integration


def test_preflight_postflight_closes_session_and_persists(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = hub / "state" / "catalog.sqlite3"
    session = preflight(hub, repo, db_path, "codex", "test work")
    lanes = {lane["lane_id"]: lane for lane in session["recommended_review_lanes"]}
    assert "review-lane:red-team-and-premortem" in lanes
    assert "review-lane:lesson-asset-harness-scout" in lanes
    assert lanes["review-lane:red-team-and-premortem"]["mode"] in {
        "subagent_when_available_else_checklist",
        "checklist_if_useful",
    }
    handoff, lesson = postflight(
        hub,
        db_path,
        session["session_id"],
        "completed",
        tests_run=["pytest"],
        lessons=["capture state transitions"],
        review_lanes=[
            "review-lane:red-team-and-premortem:checklist:checked failure modes",
            "review-lane:lesson-asset-harness-scout:checklist:captured reusable lesson",
        ],
    )
    assert handoff.session_id == session["session_id"]
    assert {lane.status for lane in handoff.review_lanes} == {"checklist"}
    assert {
        lane.lane_id for lane in handoff.review_lanes
    } == {
        "review-lane:red-team-and-premortem",
        "review-lane:lesson-asset-harness-scout",
    }
    assert lesson.lessons == ["capture state transitions"]
    with CatalogDB(db_path) as db:
        assert db.connection.execute("select count(*) from handoffs").fetchone()[0] == 1
        assert db.connection.execute("select count(*) from lessons").fetchone()[0] == 1


def test_postflight_defaults_unrecorded_review_lanes_to_not_run(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = hub / "state" / "catalog.sqlite3"
    session = preflight(hub, repo, db_path, "codex", "schema registry work")

    handoff, _lesson = postflight(hub, db_path, session["session_id"], "completed")

    assert {lane.status for lane in handoff.review_lanes} == {"not_run"}
    assert all("recommended but not recorded" in lane.summary for lane in handoff.review_lanes)


def test_postflight_accepts_json_review_lane_records(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = hub / "state" / "catalog.sqlite3"
    session = preflight(hub, repo, db_path, "codex", "harness asset scout work")
    lane = {
        "lane_id": "review-lane:lesson-asset-harness-scout",
        "status": "subagent",
        "reviewer": "asset-scout-agent",
        "summary": "Found one reusable harness idea.",
        "findings": ["Candidate harness discovery loop is reusable."],
        "candidate_outputs": ["dad:need:subagent-review-and-asset-scout-findings"],
        "follow_up": ["Review for promotion."],
    }

    handoff, _lesson = postflight(
        hub,
        db_path,
        session["session_id"],
        "completed",
        review_lanes=[json.dumps(lane)],
    )

    scout = next(
        item
        for item in handoff.review_lanes
        if item.lane_id == "review-lane:lesson-asset-harness-scout"
    )
    assert scout.status == "subagent"
    assert scout.candidate_outputs == ["dad:need:subagent-review-and-asset-scout-findings"]


def _write_learning_rule_registry(hub: Path) -> None:
    registry = hub / "registry"
    registry.mkdir(parents=True)
    (registry / "learning-rule-registry.json").write_text(
        """{
  "registry_version": "0.1.0",
  "rules": [
    {
      "schema_version": "0.1.0",
      "rule_id": "learning-rule:test-temp-fixture",
      "title": "Temp fixture copies are lineage evidence",
      "summary": "Score temp fixture copies conservatively while preserving family signal.",
      "trigger_terms": ["calibration", "temp copy"],
      "trigger_path_patterns": [".pytest-tmp-root", "processed/calibration/"],
      "context_tags": ["temp_fixture_noise"],
      "applies_when": ["A temp fixture copy is being reviewed."],
      "does_not_apply_when": ["The fixture is the canonical source."],
      "required_actions": ["Check canonical candidates before scoring current value."],
      "danger_if_ignored": "Copied fixtures can inflate the graph.",
      "evidence": ["test"],
      "enforcement_level": "require_ack",
      "review_status": "reviewed"
    }
  ]
}
""",
        encoding="utf-8",
    )


def test_preflight_surfaces_matching_learning_rules(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_learning_rule_registry(hub)
    repo = tmp_path / "repo"
    repo.mkdir()

    session = preflight(
        hub,
        repo,
        hub / "state" / "catalog.sqlite3",
        "codex",
        "asset calibration of temp copy schemas",
    )

    assert session["required_learning_rule_acknowledgements"] == [
        "learning-rule:test-temp-fixture"
    ]
    assert session["learning_rule_matches"][0]["matched_terms"] == ["calibration", "temp copy"]


def test_midflight_blocks_until_learning_rule_acknowledged(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    _write_learning_rule_registry(hub)
    repo = tmp_path / "repo"
    repo.mkdir()
    session = preflight(
        hub,
        repo,
        hub / "state" / "catalog.sqlite3",
        "codex",
        "review schema calibration",
    )

    blocked = midflight(
        hub,
        session["session_id"],
        context=["checking a .pytest-tmp-root schema copy"],
        paths=["processed/calibration/asset_rating_template.jsonl"],
    )
    ok = midflight(
        hub,
        session["session_id"],
        context=["checking a .pytest-tmp-root schema copy"],
        ack_rules=["learning-rule:test-temp-fixture"],
    )

    assert blocked["status"] == "blocked_missing_learning_rule_ack"
    assert {
        lane["lane_id"] for lane in blocked["recommended_review_lanes"]
    } == {
        "review-lane:red-team-and-premortem",
        "review-lane:lesson-asset-harness-scout",
    }
    assert blocked["missing_learning_rule_acknowledgements"] == [
        "learning-rule:test-temp-fixture"
    ]
    assert ok["status"] == "ok"
    assert ok["missing_learning_rule_acknowledgements"] == []


def test_learning_rule_registry_loads_and_matches_real_seed_rules():
    root = Path(__file__).resolve().parents[1]
    rules = load_learning_rules(root)
    matches = match_learning_rules(
        root,
        task="Phase 2 asset calibration",
        context=["temp fixture copy in .pytest-tmp-root has canonical schema variants"],
        paths=["processed/calibration/asset_rating_template.jsonl"],
    )

    assert "learning-rule:temp-fixture-copy-is-lineage-evidence" in {
        rule.rule_id for rule in rules
    }
    assert {
        "learning-rule:current-score-before-upside",
        "learning-rule:temp-fixture-copy-is-lineage-evidence",
    }.issubset({match["rule_id"] for match in matches})


def test_load_bearing_decision_rule_matches_roadmap_and_schema_defaults():
    root = Path(__file__).resolve().parents[1]
    matches = match_learning_rules(
        root,
        task=(
            "Plan a roadmap phase with a schema change, default behavior change, "
            "red team premortem, and A/B test before downstream agents inherit it"
        ),
        paths=["roadmap/roadmap.yaml", "schemas/proposal.schema.json"],
    )

    assert "learning-rule:load-bearing-decisions-need-risk-tier-review" in {
        match["rule_id"] for match in matches
    }
    matched = next(
        match
        for match in matches
        if match["rule_id"] == "learning-rule:load-bearing-decisions-need-risk-tier-review"
    )
    assert matched["enforcement_level"] == "human_gate"


def test_asset_use_pay_forward_rule_matches_non_trivial_software_work():
    root = Path(__file__).resolve().parents[1]
    matches = match_learning_rules(
        root,
        task=(
            "Plan software implementation before implementation and check whether "
            "asset-use feedback can help avoid issues"
        ),
        context=["A non-trivial issue appears while debugging failing tests."],
        paths=["src/digital_asset_directory/learning.py"],
    )

    assert "learning-rule:software-work-should-search-asset-use-pay-forward" in {
        match["rule_id"] for match in matches
    }
    matched = next(
        match
        for match in matches
        if match["rule_id"] == "learning-rule:software-work-should-search-asset-use-pay-forward"
    )
    assert matched["enforcement_level"] == "require_ack"


def test_asset_use_pay_forward_rule_does_not_match_trivial_non_software_task():
    root = Path(__file__).resolve().parents[1]
    matches = match_learning_rules(
        root,
        task="show the current date",
        context=["simple one-command request"],
        paths=[],
    )

    assert "learning-rule:software-work-should-search-asset-use-pay-forward" not in {
        match["rule_id"] for match in matches
    }
