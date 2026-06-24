from pathlib import Path
import csv
import json

import pytest
from jsonschema import Draft202012Validator

from digital_asset_directory.calibration import (
    build_asset_calibration_review_queue,
    build_asset_calibration_review_template,
    import_asset_calibration_review_csv,
    load_asset_calibration_reviews,
    summarize_asset_calibration_reviews,
    update_asset_calibration_review_file,
    update_asset_calibration_review_record,
    write_asset_calibration_review_csv,
    write_phase2_calibration_reports,
)
from digital_asset_directory.database import CatalogDB
from digital_asset_directory.models import (
    AlertRecord,
    AssetCalibrationReviewRecord,
    AssetRecord,
    SynergyRecord,
)

pytestmark = pytest.mark.calibration


def make_asset(
    asset_id: str,
    *,
    title: str,
    score: float,
    asset_type: str = "code",
    freshness: str = "current",
) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"rev-{asset_id}",
        source_id="local-test",
        source_kind="local",
        asset_type=asset_type,
        title=title,
        description="phase 2 calibration test asset",
        logical_path=f"src/{title.lower().replace(' ', '_')}.py",
        content_hash=asset_id,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        capabilities=["evaluate_assets"] if asset_id == "asset-a" else [],
        needs=["human_review"] if asset_id == "asset-b" else [],
        outcomes=["better_calibration"],
        lifecycle_state="active",
        freshness_status=freshness,  # type: ignore[arg-type]
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=score,
        value_components={
            "reuse_potential": score,
            "verification": 80 if asset_type == "test" else 40,
        },
        confidence="medium",
    )


def make_orphan_alert(asset_id: str) -> AlertRecord:
    return AlertRecord(
        alert_id=f"alert-{asset_id}",
        created_at="2026-01-01T00:00:00+00:00",
        alert_type="orphan_asset",
        severity="high",
        title=f"Orphan {asset_id}",
        description="orphan test alert",
        asset_ids=[asset_id],
        evidence={"degree": 0},
        recommended_action="review orphan candidate",
        scan_id="scan-test",
    )


def make_synergy() -> SynergyRecord:
    return SynergyRecord(
        synergy_id="synergy-1",
        asset_ids=["asset-a", "asset-b"],
        score=0.82,
        confidence="high",
        shared_outcomes=["better_calibration"],
        complementary_capabilities=["evaluate_assets"],
        needs_covered=["human_review"],
        missing_parts=[],
        integration_hypothesis="Use the evaluator asset to review the human review need.",
        evidence={"candidate_generation": "test"},
    )


def test_write_phase2_calibration_reports_creates_review_artifacts(tmp_path: Path):
    assets = [
        make_asset("asset-a", title="Evaluator", score=88, asset_type="test"),
        make_asset("asset-b", title="Review Workflow", score=42, freshness="watch"),
    ]
    result = write_phase2_calibration_reports(
        tmp_path, assets, [make_orphan_alert("asset-b")], [make_synergy()], sample_size=1
    )

    assert result["asset_count"] == 2
    assert result["open_orphan_alert_count"] == 1
    assert result["synergy_count"] == 1
    assert set(result["outputs"]) == {
        "scoring_calibration",
        "orphan_review_sample",
        "synergy_review_sample",
        "asset_rating_template",
        "asset_rating_summary",
    }
    assert result["asset_review_template_count"] == 2
    assert result["asset_review_summary"]["reviewed_count"] == 0

    scoring = Path(result["outputs"]["scoring_calibration"]).read_text(encoding="utf-8")
    orphan = Path(result["outputs"]["orphan_review_sample"]).read_text(encoding="utf-8")
    synergy = Path(result["outputs"]["synergy_review_sample"]).read_text(encoding="utf-8")
    reviews = load_asset_calibration_reviews(Path(result["outputs"]["asset_rating_template"]))

    assert "Generated candidate review artifact" in scoring
    assert "Human rating" in scoring
    assert "Orphan Review Sample" in orphan
    assert "Human decision" in orphan
    assert "Synergy Review Sample" in synergy
    assert "Smallest bounded experiment" in synergy
    assert {record.review_status for record in reviews} == {"generated_candidate"}
    assert not (tmp_path / "roadmap" / "state.json").exists()


def test_asset_calibration_review_schema_and_template_are_candidate_only():
    assets = [
        make_asset("asset-a", title="Evaluator", score=88, asset_type="test"),
        make_asset("asset-b", title="Review Workflow", score=42),
    ]
    records = build_asset_calibration_review_template(assets, per_band_sample=1)
    schema = json.loads(
        Path("schemas/asset-calibration-review.schema.json").read_text(encoding="utf-8")
    )

    assert len(records) == 2
    for record in records:
        AssetCalibrationReviewRecord.model_validate(record.model_dump(mode="json"))
        Draft202012Validator(schema).validate(record.model_dump(mode="json"))
        assert record.review_status == "generated_candidate"
        assert record.score_rating == "unreviewed"
        assert record.evidence["authority"].startswith("Generated calibration candidate")


def test_asset_calibration_review_update_and_summary(tmp_path: Path):
    records = build_asset_calibration_review_template(
        [
            make_asset("asset-a", title="Evaluator", score=88, asset_type="test"),
            make_asset("asset-b", title="Review Workflow", score=42),
        ],
        per_band_sample=1,
    )
    updated_records, updated = update_asset_calibration_review_record(
        records,
        sample_id="asset-review-001",
        reviewer="Human",
        score_rating="too_high",
        false_positive_reason="Score overweights reusable test assets.",
        weight_change_note="Lower verification weight for generated tests.",
    )

    assert updated.review_status == "reviewed"
    assert updated.reviewer == "Human"
    summary = summarize_asset_calibration_reviews(updated_records)
    assert summary["reviewed_count"] == 1
    assert summary["false_positive_note_count"] == 1
    assert summary["weight_change_note_count"] == 1
    assert summary["calibration_gate_complete"] is False

    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )
    file_updated, file_summary = update_asset_calibration_review_file(
        review_file,
        asset_id="asset-b",
        score_rating="too_low",
        false_negative_note="Human expected this workflow to rank higher.",
    )

    assert file_updated.asset_id == "asset-b"
    assert file_summary["reviewed_count"] == 1
    assert load_asset_calibration_reviews(review_file)[1].review_status == "reviewed"


def test_asset_calibration_notes_only_do_not_count_as_reviewed():
    records = build_asset_calibration_review_template(
        [make_asset("asset-a", title="Evaluator", score=88)], per_band_sample=1
    )
    updated_records, updated = update_asset_calibration_review_record(
        records, sample_id="asset-review-001", notes="Metadata-only note."
    )

    assert updated.review_status == "generated_candidate"
    assert updated.reviewed_at is None
    assert summarize_asset_calibration_reviews(updated_records)["reviewed_count"] == 0


def test_asset_calibration_review_queue_filters_pending_reviewed_and_band():
    records = build_asset_calibration_review_template(
        [
            make_asset("asset-a", title="Evaluator", score=88, asset_type="test"),
            make_asset("asset-b", title="Review Workflow", score=42),
            make_asset("asset-c", title="Middle Asset", score=55),
        ],
        per_band_sample=2,
    )
    records, _ = update_asset_calibration_review_record(
        records,
        sample_id="asset-review-001",
        reviewer="Human",
        score_rating="about_right",
    )
    records, _ = update_asset_calibration_review_record(
        records,
        sample_id="asset-review-003",
        notes="Metadata-only note.",
    )

    pending = build_asset_calibration_review_queue(records, status="pending", limit=10)
    reviewed = build_asset_calibration_review_queue(records, status="reviewed", limit=10)
    low_pending = build_asset_calibration_review_queue(
        records, status="pending", band="low", limit=10
    )

    assert pending["returned_count"] == 2
    assert [item["sample_id"] for item in pending["items"]] == [
        "asset-review-002",
        "asset-review-003",
    ]
    assert pending["items"][1]["labels"]["notes"] == "Metadata-only note."
    assert pending["items"][1]["review_status"] == "generated_candidate"
    assert reviewed["returned_count"] == 1
    assert reviewed["items"][0]["labels"]["score_rating"] == "about_right"
    assert low_pending["returned_count"] == 1
    assert low_pending["items"][0]["generated_value_band"] == "low"
    assert "value_components" in pending["items"][0]["evidence"]


def test_asset_calibration_review_queue_rejects_bad_filters():
    records = build_asset_calibration_review_template(
        [make_asset("asset-a", title="Evaluator", score=88)], per_band_sample=1
    )

    try:
        build_asset_calibration_review_queue(records, status="done")  # type: ignore[arg-type]
    except ValueError as exc:
        assert "Status must be one of" in str(exc)
    else:
        raise AssertionError("bad queue status should fail closed")

    try:
        build_asset_calibration_review_queue(records, band="urgent")  # type: ignore[arg-type]
    except ValueError as exc:
        assert "Band must be one of" in str(exc)
    else:
        raise AssertionError("bad queue band should fail closed")


def test_asset_calibration_review_update_rejects_bad_rating():
    records = build_asset_calibration_review_template(
        [make_asset("asset-a", title="Evaluator", score=88)], per_band_sample=1
    )

    try:
        update_asset_calibration_review_record(
            records, sample_id="asset-review-001", score_rating="great"
        )
    except ValueError as exc:
        assert "Invalid score_rating" in str(exc)
    else:
        raise AssertionError("bad score rating should fail closed")


def test_asset_calibration_review_csv_round_trip_labels(tmp_path: Path):
    records = build_asset_calibration_review_template(
        [
            make_asset("asset-a", title="Evaluator", score=88, asset_type="test"),
            make_asset("asset-b", title="Review Workflow", score=42),
        ],
        per_band_sample=1,
    )
    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )
    csv_file = tmp_path / "asset_reviews.csv"
    write_asset_calibration_review_csv(csv_file, records)

    rows = list(csv.DictReader(csv_file.open("r", encoding="utf-8", newline="")))
    assert "value_components" in rows[0]
    assert "capabilities" in rows[0]
    rows[0]["reviewer"] = "Human"
    rows[0]["score_rating"] = "too_high"
    rows[0]["notes"] = "CSV score review."
    rows[0]["false_positive_reason"] = "Score is too high for this asset."
    rows[0]["weight_change_note"] = "Reduce reusable test boost."
    with csv_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    result = import_asset_calibration_review_csv(review_file, csv_file)
    loaded = load_asset_calibration_reviews(review_file)

    assert result["updated_count"] == 1
    assert result["summary"]["reviewed_count"] == 1
    assert loaded[0].review_status == "reviewed"
    assert loaded[0].false_positive_reason == "Score is too high for this asset."
    assert loaded[1].review_status == "generated_candidate"


def test_asset_calibration_review_csv_notes_only_does_not_count_as_reviewed(tmp_path: Path):
    records = build_asset_calibration_review_template(
        [make_asset("asset-a", title="Evaluator", score=88)], per_band_sample=1
    )
    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )
    csv_file = tmp_path / "asset_reviews.csv"
    write_asset_calibration_review_csv(csv_file, records)

    rows = list(csv.DictReader(csv_file.open("r", encoding="utf-8", newline="")))
    rows[0]["notes"] = "Metadata-only note."
    with csv_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    result = import_asset_calibration_review_csv(review_file, csv_file)
    loaded = load_asset_calibration_reviews(review_file)

    assert result["updated_count"] == 1
    assert result["summary"]["reviewed_count"] == 0
    assert loaded[0].notes == "Metadata-only note."
    assert loaded[0].review_status == "generated_candidate"


def test_asset_calibration_review_csv_import_fails_before_writing_bad_rating(tmp_path: Path):
    records = build_asset_calibration_review_template(
        [make_asset("asset-a", title="Evaluator", score=88)], per_band_sample=1
    )
    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )
    csv_file = tmp_path / "asset_reviews.csv"
    csv_file.write_text(
        "sample_id,asset_id,score_rating\nasset-review-001,asset-a,great\n",
        encoding="utf-8",
    )
    original = review_file.read_text(encoding="utf-8")

    try:
        import_asset_calibration_review_csv(review_file, csv_file)
    except ValueError as exc:
        assert "Invalid score_rating" in str(exc)
    else:
        raise AssertionError("bad CSV score rating should fail closed")
    assert review_file.read_text(encoding="utf-8") == original


def test_catalog_db_reads_synergies_for_calibration_reports(tmp_path: Path):
    db_path = tmp_path / "state" / "catalog.sqlite3"
    synergy = make_synergy()

    with CatalogDB(db_path) as db:
        db.upsert_synergies([synergy])
        loaded = db.synergies()

    assert loaded == [synergy]
