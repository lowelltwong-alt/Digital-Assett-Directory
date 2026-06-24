import json
from pathlib import Path

import pytest

from digital_asset_directory.learning import (
    add_asset_use_feedback,
    add_lesson,
    rebuild_lesson_routes,
)

pytestmark = pytest.mark.integration


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_add_lesson_routes_to_repo_and_capability_indexes(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    record = add_lesson(
        hub,
        hub / "state" / "catalog.sqlite3",
        repository=str(tmp_path / "my-cool-repo"),
        summary="Learned something about evaluation",
        missing_capabilities=["evaluation_harness"],
        reusable_patterns=["redact once at the boundary"],
    )
    repo_index = hub / "raw" / "lessons" / "by-repo" / "my-cool-repo.jsonl"
    cap_index = hub / "raw" / "lessons" / "by-capability" / "evaluation-harness.jsonl"
    assert repo_index.exists() and cap_index.exists()

    pointer = _read_jsonl(repo_index)[0]
    assert pointer["lesson_id"] == record.lesson_id
    assert pointer["missing_capabilities"] == ["evaluation_harness"]
    assert pointer["source_path"].startswith("raw/lessons/")
    assert _read_jsonl(cap_index)[0]["lesson_id"] == record.lesson_id


def test_reindex_rebuilds_indexes_without_duplicates(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    db = hub / "state" / "catalog.sqlite3"
    add_lesson(
        hub, db, repository=str(tmp_path / "repo-a"), summary="A", missing_capabilities=["provenance"]
    )
    # Rebuild twice; each rebuild clears and regenerates from the canonical lesson files.
    rebuild_lesson_routes(hub)
    result = rebuild_lesson_routes(hub)
    cap_index = hub / "raw" / "lessons" / "by-capability" / "provenance.jsonl"
    assert result["lessons_indexed"] == 1
    assert len(_read_jsonl(cap_index)) == 1


def test_add_asset_use_feedback_records_candidate_learning_loop(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    db = hub / "state" / "catalog.sqlite3"

    record = add_asset_use_feedback(
        hub,
        db,
        asset_id="dad:asset:test",
        repository=str(tmp_path / "repo-a"),
        task="Use schema during calibration",
        agent="codex",
        used_for="validated asset record shape",
        interaction_stage="after_use",
        expected_usefulness="medium",
        expected_futurefulness="high",
        expected_value_reason="schema should constrain asset shape",
        planned_use="validate asset record shape",
        found_by="queue",
        found_query="asset-review-010",
        parts_used=["required properties"],
        parts_not_used=["examples"],
        not_used_reason="examples are missing",
        upgrades_made=["added test expectation"],
        difficulties=["examples absent"],
        things_learned=["schema needs examples"],
        use_outcome="helped",
        observed_usefulness="high",
        observed_futurefulness="medium",
        missing_parts_seen=["schema examples"],
        score_feedback="current score should stay high",
        ceiling_feedback="ceiling needs examples before increasing confidence",
        evidence=["schemas/asset.schema.json"],
    )

    assert record.review_status == "candidate"
    assert record.reusable_patterns == ["asset_use_feedback_loop"]
    assert "feedback_code=DAD_ASSET_USE_FEEDBACK_V1" in record.lessons
    assert "interaction_stage=after_use" in record.lessons
    assert "asset_id=dad:asset:test" in record.lessons
    assert "planned_use=validate asset record shape" in record.lessons
    assert "expected_usefulness=medium" in record.lessons
    assert "expected_futurefulness=high" in record.lessons
    assert "expected_value_reason=schema should constrain asset shape" in record.lessons
    assert "found_by=queue" in record.lessons
    assert "found_query=asset-review-010" in record.lessons
    assert "parts_used=required properties" in record.lessons
    assert "parts_not_used=examples" in record.lessons
    assert "not_used_reason=examples are missing" in record.lessons
    assert "upgrades_made=added test expectation" in record.lessons
    assert "difficulties=examples absent" in record.lessons
    assert "things_learned=schema needs examples" in record.lessons
    assert "use_outcome=helped" in record.lessons
    assert "observed_usefulness=high" in record.lessons
    assert "observed_futurefulness=medium" in record.lessons
    assert record.missing_capabilities == ["schema examples"]
    assert "asset:dad:asset:test" in record.evidence


def test_add_asset_use_feedback_records_before_use_expectation(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()

    record = add_asset_use_feedback(
        hub,
        hub / "state" / "catalog.sqlite3",
        asset_id="dad:asset:test",
        repository=str(tmp_path / "repo-a"),
        task="Plan use",
        agent="codex",
        used_for="expected schema grounding",
        interaction_stage="before_use",
        expected_usefulness="medium",
        expected_futurefulness="high",
        expected_value_reason="schema might reduce ambiguity",
        planned_use="inspect required fields",
    )

    assert "interaction_stage=before_use" in record.lessons
    assert "expected_usefulness=medium" in record.lessons
    assert "observed_usefulness=unknown" in record.lessons


def test_add_asset_use_feedback_rejects_invalid_values(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()

    with pytest.raises(ValueError, match="use_outcome"):
        add_asset_use_feedback(
            hub,
            hub / "state" / "catalog.sqlite3",
            asset_id="dad:asset:test",
            repository=str(tmp_path / "repo-a"),
            task="Use asset",
            agent="codex",
            used_for="test",
            use_outcome="amazing",
            observed_usefulness="high",
            observed_futurefulness="medium",
        )
