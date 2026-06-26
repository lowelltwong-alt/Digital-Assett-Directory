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
    handoff, lesson = postflight(
        hub,
        db_path,
        session["session_id"],
        "completed",
        tests_run=["pytest"],
        lessons=["capture state transitions"],
    )
    assert handoff.session_id == session["session_id"]
    assert lesson.lessons == ["capture state transitions"]
    with CatalogDB(db_path) as db:
        assert db.connection.execute("select count(*) from handoffs").fetchone()[0] == 1
        assert db.connection.execute("select count(*) from lessons").fetchone()[0] == 1


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
