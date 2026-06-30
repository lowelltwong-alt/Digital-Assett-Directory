from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.config import LocalSource
from digital_asset_directory.lesson_automation_coverage import build_lesson_automation_coverage
from digital_asset_directory.models import AssetRecord, CounterfactualLessonRecord
from digital_asset_directory.priority_content_lessons import (
    build_priority_content_lesson_candidates,
    load_priority_content_observations,
    write_priority_content_lesson_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(asset_id: str, path: str, *, asset_type: str = "document") -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=None,
        source_kind="local",
        asset_type=asset_type,
        title=Path(path).stem,
        description="synthetic priority content lesson asset",
        logical_path=path,
        content_hash=f"hash-{asset_id}",
        metadata_fingerprint=f"metadata-{asset_id}",
        content_sha256=f"sha-{asset_id}",
        size_bytes=100,
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=60,
        metadata={"repository_root": "git-projects/repo-a", "instance_class": "source"},
    )


def local_source() -> LocalSource:
    return LocalSource(
        id="git-projects",
        path=Path("C:/Git Projects"),
        path_alias="git-projects",
        enabled=True,
        max_file_bytes=0,
    )


def observation(
    observation_id: str,
    *,
    repo_key: str = "git-projects/repo-a",
    asset_id: str = "dad:asset:agents",
    relative_path: str = "AGENTS.md",
    signal_tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "observation_id": observation_id,
        "approval_id": "approval:test",
        "methodology_version": "priority-content-extract-v0.1",
        "repo_key": repo_key,
        "asset_id": asset_id,
        "logical_path": f"{repo_key}/{relative_path}",
        "relative_path": relative_path,
        "category_id": "ai_navigation",
        "asset_type": "document",
        "content_read_bytes": 100,
        "content_truncated": False,
        "redaction_count": 0,
        "content_excerpt": "Read first. Run preflight and postflight.",
        "content_token_sample": ["preflight", "postflight"],
        "signal_counts": {"ai_navigation": 2},
        "signal_tags": signal_tags or ["ai_navigation"],
        "evidence": {"candidate_only": True},
        "authority_boundary": "Generated bounded content observations only.",
        "generated_at": TIMESTAMP,
        "scan_id": SCAN_ID,
        "review_status": "generated_candidate",
    }


def write_observations(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))


def test_priority_content_lesson_synthesis_fails_closed_without_observations(tmp_path: Path):
    with pytest.raises(ValueError, match="does not exist"):
        load_priority_content_observations(tmp_path / "missing.jsonl")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_priority_content_observations(empty)


def test_priority_content_lesson_candidates_are_context_bound():
    records = build_priority_content_lesson_candidates(
        [
            observation("obs:1"),
            observation("obs:2", relative_path="AI_FRONT_DOOR.md"),
            observation(
                "obs:3",
                asset_id="dad:asset:schema",
                relative_path="schemas/item.schema.json",
                signal_tags=["schema_contract"],
            ),
        ],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert len(records) == 2
    for record in records:
        CounterfactualLessonRecord.model_validate(record.model_dump(mode="json"))
        assert record.review_status == "generated_candidate"
        assert record.applies_when
        assert record.does_not_apply_when
        assert record.danger_if_misapplied
        assert record.counterfactual_better_order
        assert "counterfactual_sequence" in record.context_tags
        assert record.source_events
    by_tag = {record.context_tags[0]: record for record in records}
    assert "ai_navigation" in by_tag
    assert "schema_contract" in by_tag


def test_priority_content_lesson_outputs_and_coverage_status(tmp_path: Path):
    observations_path = tmp_path / "processed" / "learning" / "priority_content_observations.jsonl"
    write_observations(
        observations_path,
        [
            observation("obs:1"),
            observation("obs:2", relative_path="AI_FRONT_DOOR.md"),
        ],
    )

    result = write_priority_content_lesson_outputs(
        tmp_path,
        observations_file=observations_path,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert result["summary"]["lesson_candidate_count"] == 1
    lesson_path = Path(result["outputs"]["lesson_candidates"])
    assert lesson_path.exists()
    lesson_payload = json.loads(lesson_path.read_text(encoding="utf-8").splitlines()[0])
    assert lesson_payload["review_status"] == "generated_candidate"
    assert lesson_payload["does_not_apply_when"]
    assert lesson_payload["danger_if_misapplied"]

    assets = [
        make_asset("dad:asset:repo", "git-projects/repo-a", asset_type="repository"),
        make_asset("dad:asset:agents", "git-projects/repo-a/AGENTS.md"),
    ]
    coverage = build_lesson_automation_coverage(
        tmp_path,
        assets,
        [local_source()],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    by_family = {item["signal_family_id"]: item for item in coverage["signal_families"]}

    assert by_family["priority_content_extracts"]["current_status"] == "lesson_candidates_synthesized"
    assert (
        by_family["priority_content_extracts"]["evidence"][
            "priority_content_lesson_candidates_present"
        ]
        is True
    )
