from pathlib import Path

from digital_asset_directory.calibration import write_phase2_calibration_reports
from digital_asset_directory.database import CatalogDB
from digital_asset_directory.models import AlertRecord, AssetRecord, SynergyRecord


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
    }

    scoring = Path(result["outputs"]["scoring_calibration"]).read_text(encoding="utf-8")
    orphan = Path(result["outputs"]["orphan_review_sample"]).read_text(encoding="utf-8")
    synergy = Path(result["outputs"]["synergy_review_sample"]).read_text(encoding="utf-8")

    assert "Generated candidate review artifact" in scoring
    assert "Human rating" in scoring
    assert "Orphan Review Sample" in orphan
    assert "Human decision" in orphan
    assert "Synergy Review Sample" in synergy
    assert "Smallest bounded experiment" in synergy
    assert not (tmp_path / "roadmap" / "state.json").exists()


def test_catalog_db_reads_synergies_for_calibration_reports(tmp_path: Path):
    db_path = tmp_path / "state" / "catalog.sqlite3"
    synergy = make_synergy()

    with CatalogDB(db_path) as db:
        db.upsert_synergies([synergy])
        loaded = db.synergies()

    assert loaded == [synergy]
