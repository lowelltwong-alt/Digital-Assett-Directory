from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from digital_asset_directory.portfolio_attempts import (
    _build_event,
    attempt_journal_path,
    claim_dry_run_attempt,
    read_attempt_events,
    record_dry_run_result,
)
from digital_asset_directory.portfolio_events import LedgerIntegrityError


T0 = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
DISPATCH = "dad:portfolio-dispatch:00000000-0000-0000-0000-000000000001"
SCOPE = "dad:portfolio-dispatch-scope:" + "a" * 64


def _attempt(index: int) -> str:
    return f"dad:portfolio-attempt:00000000-0000-0000-0000-{index:012d}"


def _claim_payload(index: int, *, selected: bool, selected_id: str) -> dict:
    return {
        "attempt_id": _attempt(index),
        "dispatch_revision_id": DISPATCH,
        "dispatch_scope_digest": SCOPE,
        "worker_revision_id": f"worker:{index}",
        "execution_mode": "dry_run",
        "source_write_policy": "source_zero_write",
        "execution_performed": False,
        "source_write_count": 0,
        "non_authoritative": True,
        "claim_selected": selected,
        "selected_attempt_id": selected_id,
    }


def _write(path: Path, *events: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events
        ),
        encoding="utf-8",
    )


def test_reader_rejects_duplicate_json_object_keys(tmp_path: Path) -> None:
    event = _build_event(
        event_kind="dry_run_claim_recorded",
        prev_event_id="",
        command_id="dad:portfolio-attempt-command:00000000-0000-0000-0000-000000000001",
        recorded_at=T0.isoformat(),
        payload=_claim_payload(1, selected=True, selected_id=_attempt(1)),
    )
    raw = json.dumps(event, sort_keys=True, separators=(",", ":"))
    needle = '"authority_boundary":"source_zero_write_candidate_only"'
    duplicate = needle + "," + needle
    path = attempt_journal_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw.replace(needle, duplicate, 1) + "\n", encoding="utf-8")

    events, diagnostics = read_attempt_events(path)
    assert events == []
    assert diagnostics["corrupt_line_count"] == 1
    assert "invalid_json" in diagnostics["problems"][0]


def test_reader_blocks_two_rehashed_selected_claims(tmp_path: Path) -> None:
    first = _build_event(
        event_kind="dry_run_claim_recorded",
        prev_event_id="",
        command_id="dad:portfolio-attempt-command:00000000-0000-0000-0000-000000000001",
        recorded_at=T0.isoformat(),
        payload=_claim_payload(1, selected=True, selected_id=_attempt(1)),
    )
    second = _build_event(
        event_kind="dry_run_claim_recorded",
        prev_event_id=first["event_id"],
        command_id="dad:portfolio-attempt-command:00000000-0000-0000-0000-000000000002",
        recorded_at=T0.isoformat(),
        payload=_claim_payload(2, selected=True, selected_id=_attempt(2)),
    )
    path = attempt_journal_path(tmp_path)
    _write(path, first, second)

    events, diagnostics = read_attempt_events(path)
    assert events == [first]
    assert diagnostics["invalid_event_count"] == 1
    assert "multiple_selected_claims" in diagnostics["problems"][0]
    with pytest.raises(LedgerIntegrityError, match="ambiguous or corrupt"):
        claim_dry_run_attempt(
            tmp_path,
            {"dispatches": [{"dispatch_revision_id": DISPATCH, "scope_digest": SCOPE}]},
            DISPATCH,
            worker_revision_id="worker:3",
        )


def test_reader_blocks_result_that_does_not_match_selected_claim(tmp_path: Path) -> None:
    claim = _build_event(
        event_kind="dry_run_claim_recorded",
        prev_event_id="",
        command_id="dad:portfolio-attempt-command:00000000-0000-0000-0000-000000000001",
        recorded_at=T0.isoformat(),
        payload=_claim_payload(1, selected=True, selected_id=_attempt(1)),
    )
    result_payload = {
        key: claim["payload"][key]
        for key in (
            "attempt_id",
            "dispatch_revision_id",
            "dispatch_scope_digest",
            "worker_revision_id",
            "execution_mode",
            "source_write_policy",
            "execution_performed",
            "source_write_count",
            "non_authoritative",
        )
    }
    result_payload["worker_revision_id"] = "worker:tampered"
    result_payload["result_disposition"] = "simulated_succeeded"
    result_payload["evidence_refs"] = []
    result = _build_event(
        event_kind="dry_run_result_recorded",
        prev_event_id=claim["event_id"],
        command_id="dad:portfolio-attempt-command:00000000-0000-0000-0000-000000000002",
        recorded_at=T0.isoformat(),
        payload=result_payload,
    )
    path = attempt_journal_path(tmp_path)
    _write(path, claim, result)

    events, diagnostics = read_attempt_events(path)
    assert events == [claim]
    assert diagnostics["invalid_event_count"] == 1
    assert "result_claim_mismatch" in diagnostics["problems"][0]
    with pytest.raises(LedgerIntegrityError, match="ambiguous or corrupt"):
        record_dry_run_result(
            tmp_path,
            _attempt(1),
            result_disposition="simulated_succeeded",
        )


def test_redacted_retries_are_idempotent(tmp_path: Path) -> None:
    projection = {"dispatches": [{"dispatch_revision_id": DISPATCH, "scope_digest": SCOPE}]}
    claim_command = "dad:portfolio-attempt-command:00000000-0000-0000-0000-000000000010"
    worker = r"C:\Users\example\private\worker.py"
    first = claim_dry_run_attempt(
        tmp_path,
        projection,
        DISPATCH,
        worker_revision_id=worker,
        attempt_id=_attempt(10),
        command_id=claim_command,
        now=T0,
    )
    retried = claim_dry_run_attempt(
        tmp_path,
        projection,
        DISPATCH,
        worker_revision_id=worker,
        attempt_id=_attempt(10),
        command_id=claim_command,
        now=T0,
    )
    assert first["worker_revision_id"] == "[LOCAL_PATH]/worker.py"
    assert retried["events_appended"] == 0
    assert retried["events_deduplicated"] == 1
    assert retried["worker_revision_id"] == first["worker_revision_id"]

    result_command = "dad:portfolio-attempt-command:00000000-0000-0000-0000-000000000011"
    evidence = [r"C:\Users\example\private\result.json"]
    result = record_dry_run_result(
        tmp_path,
        _attempt(10),
        result_disposition="simulated_succeeded",
        evidence_refs=evidence,
        command_id=result_command,
        now=T0,
    )
    result_retry = record_dry_run_result(
        tmp_path,
        _attempt(10),
        result_disposition="simulated_succeeded",
        evidence_refs=evidence,
        command_id=result_command,
        now=T0,
    )
    assert result["evidence_refs"] == ["[LOCAL_PATH]/result.json"]
    assert result_retry["events_appended"] == 0
    assert result_retry["events_deduplicated"] == 1
    assert result_retry["evidence_refs"] == result["evidence_refs"]
