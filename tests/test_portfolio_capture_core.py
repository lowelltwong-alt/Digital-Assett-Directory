from __future__ import annotations

from datetime import datetime, timezone

from digital_asset_directory.portfolio_capture_core import (
    CaptureCoreLimits,
    structure_capture_lines,
)

NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def test_core_is_bounded_provider_neutral_and_deduplicates() -> None:
    result = structure_capture_lines(
        ["First thought", "First thought", "", "Second thought"],
        source_fingerprint="sha256:" + "a" * 64,
        captured_at=NOW.isoformat(),
        limits=CaptureCoreLimits(max_lines=4, max_line_chars=100),
    )
    assert result["status"] == "complete_candidate"
    assert result["summary"] == {
        "observed_line_count": 4,
        "candidate_count": 2,
        "blank_line_count": 1,
        "duplicate_line_count": 1,
        "redaction_count": 0,
    }
    assert all(row["execution_authorized"] is False for row in result["candidates"])


def test_core_discards_partial_batch_when_a_budget_is_exhausted() -> None:
    result = structure_capture_lines(
        ["safe", "x" * 33],
        source_fingerprint="sha256:" + "b" * 64,
        captured_at=NOW.isoformat(),
        limits=CaptureCoreLimits(max_lines=2, max_line_chars=32),
    )
    assert result["status"] == "partial_candidate"
    assert result["candidates"] == []
    assert result["coverage"]["problems"] == ["line_length_budget_exhausted"]
