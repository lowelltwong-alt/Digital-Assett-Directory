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


def test_core_fails_closed_when_minimization_expands_past_line_budget() -> None:
    """A max-length /tmp/... line can grow after path redaction; fail closed."""
    # /tmp/a... (5 chars prefix) -> [LOCAL_PATH]/a... (13 chars), net +8.
    max_chars = 20_000
    raw = "/tmp/" + ("a" * (max_chars - len("/tmp/")))
    assert len(raw) == max_chars
    result = structure_capture_lines(
        ["safe prior line", raw],
        source_fingerprint="sha256:" + "c" * 64,
        captured_at=NOW.isoformat(),
        limits=CaptureCoreLimits(max_lines=10, max_line_chars=max_chars),
    )
    assert result["status"] == "partial_candidate"
    assert result["candidates"] == []
    assert result["coverage"]["problems"] == ["line_length_budget_exhausted"]
