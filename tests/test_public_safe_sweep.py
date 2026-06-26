from __future__ import annotations

import json
from pathlib import Path

from digital_asset_directory.public_safe_sweep import (
    build_public_safe_source_sweep,
    classify_public_safe_path,
    write_public_safe_source_sweep,
)


def test_public_safe_path_classifier_quarantines_data_and_outputs():
    assert classify_public_safe_path("data/source_page_snapshots/person.html") == {
        "decision": "quarantine",
        "reason": "row_data_or_source_snapshot_lane",
    }
    assert classify_public_safe_path("output/recruiting_intelligence/leads.csv") == {
        "decision": "quarantine",
        "reason": "generated_output_or_export_lane",
    }
    assert classify_public_safe_path("scripts/scrape_firm_bios.py") == {
        "decision": "include",
        "reason": "workflow_code_schema_or_governance_metadata_only",
    }


def test_public_safe_sweep_is_metadata_only_and_quarantines_private_lanes(tmp_path: Path):
    source = tmp_path / "Nevada Bar Results"
    (source / "scripts").mkdir(parents=True)
    (source / "tests").mkdir(parents=True)
    (source / "data" / "source_page_snapshots").mkdir(parents=True)
    (source / "output" / "recruiting_intelligence").mkdir(parents=True)

    (source / "WORKFLOW.md").write_text(
        "Private workflow doc with Jane Secret embedded.", encoding="utf-8"
    )
    (source / "scripts" / "scrape_firm_bios.py").write_text(
        "SECRET_PERSON = 'Jane Secret'", encoding="utf-8"
    )
    (source / "tests" / "test_identity_gate.py").write_text(
        "def test_gate(): assert True", encoding="utf-8"
    )
    (source / "data" / "source_page_snapshots" / "person.html").write_text(
        "<html>Jane Secret profile</html>", encoding="utf-8"
    )
    (source / "output" / "recruiting_intelligence" / "leads.csv").write_text(
        "name,lead\nJane Secret,yes\n", encoding="utf-8"
    )
    (source / "output" / "nevada_bar_results.sqlite").write_bytes(b"not really sqlite")

    record = build_public_safe_source_sweep(
        source,
        source_id="nevada-bar-results",
        review_sample=20,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    serialized = json.dumps(record, sort_keys=True)
    assert "Jane Secret" not in serialized
    assert record["privacy_boundary"]["file_contents_read"] is False
    assert record["privacy_boundary"]["sqlite_opened"] is False
    assert record["privacy_boundary"]["row_level_data_imported"] is False
    assert record["observed"]["metadata_only_candidate_files"] == 3
    assert record["observed"]["quarantine_reason_counts"] == {
        "generated_output_or_export_lane": 2,
        "row_data_or_source_snapshot_lane": 1,
    }
    assert {item["relative_path"] for item in record["safe_candidate_sample"]} == {
        "WORKFLOW.md",
        "scripts/scrape_firm_bios.py",
        "tests/test_identity_gate.py",
    }


def test_public_safe_sweep_writes_ignored_generated_outputs(tmp_path: Path):
    repo = tmp_path / "dad"
    source = tmp_path / "source"
    source.mkdir()
    (source / "ROADMAP.md").write_text("roadmap", encoding="utf-8")
    (source / "data.csv").write_text("name\nJane Secret\n", encoding="utf-8")

    result = write_public_safe_source_sweep(
        repo,
        source,
        source_id="source",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    report = Path(result["report"])
    record = Path(result["record"])
    assert report.exists()
    assert record.exists()
    assert "Jane Secret" not in report.read_text(encoding="utf-8")
    assert "Jane Secret" not in record.read_text(encoding="utf-8")
    assert "processed/reports/external_sweeps/source_public_safe_sweep.md" in report.as_posix()
