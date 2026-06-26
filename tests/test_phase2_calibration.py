from pathlib import Path
import csv
import json

import pytest
from jsonschema import Draft202012Validator

from digital_asset_directory.calibration import (
    build_asset_calibration_review_lens,
    build_asset_calibration_review_queue,
    build_asset_calibration_review_template,
    import_asset_calibration_review_csv,
    load_asset_calibration_reviews,
    summarize_asset_calibration_reviews,
    update_asset_calibration_review_file,
    update_asset_calibration_review_record,
    write_asset_calibration_evidence,
    write_asset_calibration_review_csv,
    write_phase2_calibration_reports,
    write_phase25_score_delta_validation,
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
    logical_path: str | None = None,
    content_sha256: str | None = None,
    metadata: dict | None = None,
) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"rev-{asset_id}",
        source_id="local-test",
        source_kind="local",
        asset_type=asset_type,
        title=title,
        description="phase 2 calibration test asset",
        logical_path=logical_path or f"src/{title.lower().replace(' ', '_')}.py",
        content_hash=asset_id,
        content_sha256=content_sha256,
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
        metadata=metadata or {},
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
        lens = record.evidence["review_lens"]
        assert lens["authority"].startswith("Generated review guidance only")
        assert len(lens["layers"]) <= 3
        assert {layer["evidence_level"] for layer in lens["layers"]} == {
            "direct",
            "derived",
            "projected",
        }
        assert lens["calibration_caution"].startswith("Projected lift")
        assert "near_duplicate" in lens["duplicate_review_prompt"]
        assert "cluster delta" in lens["cluster_delta_prompt"]
        assert lens["current_floor_basis"].startswith("Generated pre-review")
        assert lens["current_score_range"]["midpoint"] == record.generated_value_score
        assert lens["current_score_midpoint"] == record.generated_value_score
        assert lens["current_score_uncertainty"] in {"narrow", "medium", "wide"}
        assert "not a statistical confidence interval" in lens["current_score_range_basis"]
        assert lens["review_order"][0].startswith("Judge current generated score")
        assert lens["current_score_first_prompt"].startswith("Review the current value score first")
        assert lens["potential_ceiling_basis"].startswith("Conditional upside")
        assert set(lens["potential_ceiling_range"]) == {"low", "high"}
        assert lens["score_warning"].startswith("High ceiling")
        assert lens["score_justification"].startswith("Generated score")
        assert lens["ceiling_justification"].startswith("Potential ceiling")
        assert lens["ceiling_activation_conditions"] == lens["activation_requirements"]
        assert "6 months" in lens["projection_review_cadence"]
        assert "lesson asset-use" in lens["usage_feedback_command"]
        assert "feedback_code" in lens["usage_feedback_fields"]
        assert "interaction_stage" in lens["usage_feedback_fields"]
        assert "expected_usefulness" in lens["usage_feedback_fields"]
        assert lens["usage_feedback_instructions"][0].startswith("Complete a before_use")
        assert "Do not change source repo code" in lens["usage_feedback_instructions"][-1]
        assert "observed_usefulness" in lens["usage_feedback_scoring_methodology"]
        assert lens["development_posture"] in {
            "validate_first",
            "actively_develop",
            "prototype_bounded_experiment",
            "monitor",
        }


def test_asset_calibration_template_dedupes_and_excludes_quarantined_instances():
    source = make_asset(
        "source-schema",
        title="Claim Schema",
        score=70,
        asset_type="schema",
        logical_path="repo/schemas/claim.schema.json",
        content_sha256="same-content",
        metadata={
            "instance_class": "source",
            "information_content_class": "content_extracted",
            "text_tokens": ["schema", "claim"],
        },
    )
    temp = make_asset(
        "temp-schema",
        title="Claim Schema Copy",
        score=95,
        asset_type="schema",
        logical_path="repo/.pytest-tmp-root/pytest-of-Lowell/pytest-1/test_x/contract-repo/schemas/claim.schema.json",
        content_sha256="same-content",
        metadata={
            "instance_class": "temp_fixture",
            "information_content_class": "content_extracted",
            "text_tokens": ["schema", "claim"],
        },
    )
    junk = make_asset(
        "junk",
        title=".DS_Store",
        score=35,
        asset_type="unknown",
        logical_path="repo/.DS_Store",
        content_sha256="junk",
        metadata={"instance_class": "os_junk", "information_content_class": "os_junk"},
    )

    records = build_asset_calibration_review_template([temp, junk, source], per_band_sample=5)

    assert [record.asset_id for record in records] == ["source-schema"]
    assert records[0].evidence["instance_class"] == "source"
    assert records[0].evidence["sampling_bucket"] == "portfolio_candidate"
    assert (
        records[0]
        .evidence["sample_methodology_version"]
        .startswith("asset-calibration-sampling-v0.2")
    )


def test_asset_calibration_review_lens_preserves_duplicate_and_projection_boundaries():
    record = build_asset_calibration_review_template(
        [make_asset("asset-a", title="asset.schema", score=76, asset_type="schema")],
        per_band_sample=1,
    )[0]

    lens = build_asset_calibration_review_lens(record)

    assert lens["current_graph_role"] == "Contract node for structured asset interoperability."
    assert lens["current_score_range"] == {"low": 66.0, "midpoint": 76.0, "high": 86.0}
    assert lens["current_score_uncertainty"] == "medium"
    assert lens["projected_value_lift"] == "very_high"
    assert lens["potential_ceiling"] == "very_high"
    assert lens["potential_ceiling_range"] == {"low": "high", "high": "very_high"}
    assert lens["ceiling_confidence"] == "low"
    assert lens["upside_delta"] == 1
    assert lens["upside_delta_range"] == {"low": 0, "high": 1}
    assert lens["upside_delta_meaning"].startswith("One-band upside")
    assert lens["development_posture"] == "validate_first"
    assert lens["layers"][2]["evidence_level"] == "projected"
    assert lens["layers"][2]["score_use"] == "review_note_only"
    assert any(edge["edge"] == "constrains:catalog_contracts" for edge in lens["high_signal_edges"])
    assert "variant_of" in lens["duplicate_review_prompt"]
    assert "neutral differences" in lens["cluster_delta_prompt"]


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


def test_phase25_score_delta_validation_writes_directional_report(tmp_path: Path):
    records = [
        AssetCalibrationReviewRecord(
            review_id="review-high",
            sample_id="asset-review-001",
            asset_id="asset-too-high",
            asset_title="Template",
            logical_path="repo/.github/ISSUE_TEMPLATE/bug_report.md",
            asset_type="workflow",
            generated_value_score=58.5,
            generated_value_band="medium",
            reviewer="Lowell",
            score_rating="too_high",
            evidence={"information_content_class": "metadata_only"},
        ),
        AssetCalibrationReviewRecord(
            review_id="review-low",
            sample_id="asset-review-002",
            asset_id="asset-too-low",
            asset_title="Runtime",
            logical_path="repo/src/runtime.py",
            asset_type="code",
            generated_value_score=27.98,
            generated_value_band="low",
            reviewer="Lowell",
            score_rating="too_low",
            evidence={"information_content_class": "metadata_only"},
        ),
        AssetCalibrationReviewRecord(
            review_id="review-right",
            sample_id="asset-review-003",
            asset_id="asset-about-right",
            asset_title="Thin helper",
            logical_path="repo/src/helper.py",
            asset_type="code",
            generated_value_score=27.98,
            generated_value_band="low",
            reviewer="Lowell",
            score_rating="about_right",
            evidence={"information_content_class": "metadata_only"},
        ),
    ]
    assets = [
        make_asset(
            "asset-too-high",
            title="Template",
            score=24,
            asset_type="workflow",
            logical_path="repo/.github/ISSUE_TEMPLATE/bug_report.md",
            metadata={
                "information_content_class": "content_profiled",
                "score_methodology_version": "asset-value-v0.3-content-aware",
                "content_profile": {
                    "non_empty_line_count": 10,
                    "workflow_subtype": "issue_or_pr_template",
                },
            },
        ),
        make_asset(
            "asset-too-low",
            title="Runtime",
            score=61,
            asset_type="code",
            logical_path="repo/src/runtime.py",
            metadata={
                "information_content_class": "content_profiled",
                "score_methodology_version": "asset-value-v0.3-content-aware",
                "content_profile": {"non_empty_line_count": 150, "code_role": "runtime_core"},
            },
        ),
        make_asset(
            "asset-about-right",
            title="Thin helper",
            score=31,
            asset_type="code",
            logical_path="repo/src/helper.py",
            metadata={
                "information_content_class": "content_profiled",
                "score_methodology_version": "asset-value-v0.3-content-aware",
                "content_profile": {"non_empty_line_count": 20, "code_role": "support_module"},
            },
        ),
    ]

    result = write_phase25_score_delta_validation(
        tmp_path,
        records,
        assets,
        scan_summary={
            "scan_id": "scan-v03",
            "status": "complete",
            "source_files_mutated": False,
            "changed_during_scan_count": 0,
            "quarantine": {"count": 0},
        },
    )

    report = Path(result["report"]).read_text(encoding="utf-8")
    payload = json.loads(Path(result["json"]).read_text(encoding="utf-8"))

    assert result["status"] == "passed"
    assert payload["desired_band_movement_counts"] == {
        "about_right": 1,
        "too_high": 1,
        "too_low": 1,
    }
    assert payload["movement_by_rating"]["too_high"] == {"medium->low": 1}
    assert payload["movement_by_rating"]["too_low"] == {"low->medium": 1}
    assert payload["about_right_churn_count"] == 0
    assert "Phase 2.5 Fresh Scan Score-Delta Validation" in report
    assert "source repositories remain authoritative" in report.lower()


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
    assert "review_lens" in pending["items"][0]["evidence"]
    assert pending["items"][0]["pattern_key"].startswith("code/medium/")
    assert pending["items"][0]["evidence"]["review_lens"]["layers"][0]["evidence_level"] == "direct"


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
    assert "pattern_key" in rows[0]
    assert "current_graph_role" in rows[0]
    assert "duplicate_review_prompt" in rows[0]
    assert "near_duplicate" in rows[0]["duplicate_review_prompt"]
    assert "cluster_delta_prompt" in rows[0]
    assert "shared core" in rows[0]["cluster_delta_prompt"]
    assert "score_justification" in rows[0]
    assert "current_score_range" in rows[0]
    assert "current_score_midpoint" in rows[0]
    assert "ceiling_justification" in rows[0]
    assert "ceiling_activation_conditions" in rows[0]
    assert "current_score_first_prompt" in rows[0]
    assert "potential_ceiling_range" in rows[0]
    assert "upside_delta_range" in rows[0]
    assert "upside_delta_meaning" in rows[0]
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


def _complete_asset_calibration_records() -> list[AssetCalibrationReviewRecord]:
    assets = [
        make_asset(
            f"asset-{index:02d}",
            title=f"Calibration Asset {index:02d}",
            score=90 if index < 25 else 20,
        )
        for index in range(50)
    ]
    records = build_asset_calibration_review_template(assets, per_band_sample=25)
    for index, record in enumerate(list(records), start=1):
        kwargs = {
            "sample_id": record.sample_id,
            "reviewer": "Human",
            "score_rating": "about_right",
        }
        if index == 1:
            kwargs["false_positive_reason"] = "Representative false positive."
        if index == 2:
            kwargs["false_negative_note"] = "Representative false negative."
        if index == 3:
            kwargs["weight_change_note"] = "Adjust review weight after calibration."
        records, _ = update_asset_calibration_review_record(records, **kwargs)
    return records


def test_asset_calibration_evidence_refuses_incomplete_reviews(tmp_path: Path):
    records = build_asset_calibration_review_template(
        [make_asset("asset-a", title="Evaluator", score=88)], per_band_sample=1
    )
    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )

    try:
        write_asset_calibration_evidence(tmp_path, records, review_file)
    except ValueError as exc:
        assert "at least 50 reviewed asset ratings" in str(exc)
    else:
        raise AssertionError("incomplete asset calibration evidence should fail closed")


def test_asset_calibration_evidence_requires_structured_notes(tmp_path: Path):
    records = _complete_asset_calibration_records()
    for record in records:
        record.false_positive_reason = ""
        record.false_negative_note = ""
        record.weight_change_note = ""
    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )

    try:
        write_asset_calibration_evidence(tmp_path, records, review_file)
    except ValueError as exc:
        assert "requires false-positive" in str(exc)
    else:
        raise AssertionError("asset calibration evidence without notes should fail closed")


def test_asset_calibration_evidence_refuses_legacy_sample_methodology(tmp_path: Path):
    records = _complete_asset_calibration_records()
    for record in records:
        record.evidence.pop("sample_methodology_version", None)
    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )

    try:
        write_asset_calibration_evidence(tmp_path, records, review_file)
    except ValueError as exc:
        assert "current deduped calibration sample" in str(exc)
    else:
        raise AssertionError("legacy calibration samples should fail closed")


def test_asset_calibration_evidence_writes_tracked_gate_evidence(tmp_path: Path):
    records = _complete_asset_calibration_records()
    review_file = tmp_path / "asset_reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records),
        encoding="utf-8",
    )

    summary, evidence_path = write_asset_calibration_evidence(tmp_path, records, review_file)

    assert summary["calibration_gate_complete"] is True
    assert Path(evidence_path).exists()
    markdown = Path(evidence_path).read_text(encoding="utf-8")
    assert "Phase 2 Asset Calibration Evidence" in markdown
    gate_evidence = json.loads((tmp_path / "roadmap" / "gate-evidence.json").read_text())
    assert gate_evidence["human_gates"]["phase-2-asset-ratings-reviewed"]["status"] == ("verified")
    assert gate_evidence["human_gates"]["phase-2-weight-changes-documented"]["phase_id"] == (
        "phase-2-calibration"
    )


def test_catalog_db_reads_synergies_for_calibration_reports(tmp_path: Path):
    db_path = tmp_path / "state" / "catalog.sqlite3"
    synergy = make_synergy()

    with CatalogDB(db_path) as db:
        db.upsert_synergies([synergy])
        loaded = db.synergies()

    assert loaded == [synergy]
