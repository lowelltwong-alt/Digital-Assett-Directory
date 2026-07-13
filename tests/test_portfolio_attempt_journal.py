from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digital_asset_directory.portfolio_attempts import (
    annotate_execution_projection,
    attempt_journal_path,
    claim_dry_run_attempt,
    load_attempt_projection,
    read_attempt_events,
    record_dry_run_result,
    simulate_claim_race,
)
from digital_asset_directory.portfolio_events import LedgerIntegrityError


T0 = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
DISPATCH = "dad:portfolio-dispatch:00000000-0000-0000-0000-000000000001"
SCOPE = "dad:portfolio-dispatch-scope:" + "a" * 64


def _projection() -> dict:
    return {
        "dispatches": [
            {
                "dispatch_revision_id": DISPATCH,
                "scope_digest": SCOPE,
                "status": "approval_unverified",
                "authorization_valid": False,
                "manual_packet_ready": False,
                "dispatch_allowed": False,
            }
        ]
    }


def _attempt(index: int) -> str:
    return f"dad:portfolio-attempt:00000000-0000-0000-0000-{index:012d}"


def _command(index: int) -> str:
    return f"dad:portfolio-attempt-command:00000000-0000-0000-0000-{index:012d}"


def test_first_committed_claim_is_only_selected_claim(tmp_path: Path) -> None:
    first = claim_dry_run_attempt(
        tmp_path,
        _projection(),
        DISPATCH,
        worker_revision_id="worker:first",
        attempt_id=_attempt(1),
        command_id=_command(1),
        now=T0,
    )
    second = claim_dry_run_attempt(
        tmp_path,
        _projection(),
        DISPATCH,
        worker_revision_id="worker:second",
        attempt_id=_attempt(2),
        command_id=_command(2),
        now=T0 + timedelta(seconds=1),
    )
    projection = load_attempt_projection(tmp_path)

    assert first["status"] == "claim_selected"
    assert second["status"] == "claim_not_selected"
    assert first["selected_attempt_id"] == second["selected_attempt_id"] == _attempt(1)
    assert projection["summary"]["selected_claim_count"] == 1
    assert projection["summary"]["real_execution_count"] == 0
    assert projection["summary"]["source_write_count"] == 0
    assert projection["executor"] == {"available": False, "dispatch_allowed": False}


def test_claim_retry_is_idempotent_and_conflict_fails(tmp_path: Path) -> None:
    kwargs = {
        "worker_revision_id": "worker:first",
        "attempt_id": _attempt(1),
        "command_id": _command(1),
        "now": T0,
    }
    first = claim_dry_run_attempt(tmp_path, _projection(), DISPATCH, **kwargs)
    retry = claim_dry_run_attempt(tmp_path, _projection(), DISPATCH, **kwargs)
    assert first["claim_selected"] is True
    assert retry["events_appended"] == 0
    assert retry["events_deduplicated"] == 1

    with pytest.raises(LedgerIntegrityError, match="command_id conflict"):
        claim_dry_run_attempt(
            tmp_path,
            _projection(),
            DISPATCH,
            worker_revision_id="worker:other",
            attempt_id=_attempt(2),
            command_id=_command(1),
            now=T0,
        )


def test_result_is_simulated_and_only_selected_attempt_can_record(tmp_path: Path) -> None:
    claim_dry_run_attempt(
        tmp_path,
        _projection(),
        DISPATCH,
        worker_revision_id="worker:first",
        attempt_id=_attempt(1),
        command_id=_command(1),
        now=T0,
    )
    claim_dry_run_attempt(
        tmp_path,
        _projection(),
        DISPATCH,
        worker_revision_id="worker:second",
        attempt_id=_attempt(2),
        command_id=_command(2),
        now=T0,
    )
    with pytest.raises(ValueError, match="only the selected"):
        record_dry_run_result(
            tmp_path,
            _attempt(2),
            result_disposition="simulated_succeeded",
            command_id=_command(3),
            now=T0,
        )

    result = record_dry_run_result(
        tmp_path,
        _attempt(1),
        result_disposition="simulated_succeeded",
        evidence_refs=["test:dry-run"],
        command_id=_command(4),
        now=T0,
    )
    assert result["execution_performed"] is False
    assert result["source_write_count"] == 0
    assert result["non_authoritative"] is True


def test_complete_unsealed_tail_is_committed_but_partial_tail_blocks(tmp_path: Path) -> None:
    claim_dry_run_attempt(
        tmp_path,
        _projection(),
        DISPATCH,
        worker_revision_id="worker:first",
        attempt_id=_attempt(1),
        command_id=_command(1),
        now=T0,
    )
    path = attempt_journal_path(tmp_path)
    path.write_bytes(path.read_bytes().rstrip(b"\n"))
    events, diagnostics = read_attempt_events(path)
    assert len(events) == 1
    assert diagnostics["complete_unsealed_tail"] is True

    second = claim_dry_run_attempt(
        tmp_path,
        _projection(),
        DISPATCH,
        worker_revision_id="worker:second",
        attempt_id=_attempt(2),
        command_id=_command(2),
        now=T0,
    )
    assert second["claim_selected"] is False
    assert path.read_bytes().endswith(b"\n")

    with path.open("ab") as handle:
        handle.write(b'{"partial"')
    before = path.read_bytes()
    with pytest.raises(LedgerIntegrityError, match="ambiguous or corrupt"):
        claim_dry_run_attempt(
            tmp_path,
            _projection(),
            DISPATCH,
            worker_revision_id="worker:third",
            attempt_id=_attempt(3),
            command_id=_command(3),
            now=T0,
        )
    assert path.read_bytes() == before


def test_concurrent_claims_have_exactly_one_selected_winner(tmp_path: Path) -> None:
    def claim(index: int) -> dict:
        return claim_dry_run_attempt(
            tmp_path,
            _projection(),
            DISPATCH,
            worker_revision_id=f"worker:{index}",
            attempt_id=_attempt(index),
            command_id=_command(index),
            now=T0,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(1, 21)))
    assert sum(item["claim_selected"] for item in results) == 1
    projection = load_attempt_projection(tmp_path)
    assert projection["summary"]["selected_claim_count"] == 1
    assert projection["summary"]["event_count"] == 20


def test_race_simulation_uses_explicit_sequence_and_never_executes() -> None:
    result = simulate_claim_race(
        [
            {"attempt_id": _attempt(2), "worker_revision_id": "worker:two", "sequence": 2},
            {"attempt_id": _attempt(1), "worker_revision_id": "worker:one", "sequence": 1},
        ]
    )
    assert result["selected_attempt_id"] == _attempt(1)
    assert result["execution_performed"] is False
    assert result["source_write_count"] == 0
    assert sum(row["claim_selected"] for row in result["ordered_claims"]) == 1


def test_dry_run_attempt_can_only_mark_reconciliation_dry_run(tmp_path: Path) -> None:
    claim_dry_run_attempt(
        tmp_path,
        _projection(),
        DISPATCH,
        worker_revision_id="worker:first",
        attempt_id=_attempt(1),
        command_id=_command(1),
        now=T0,
    )
    execution = {
        "executor": {"available": False, "dispatch_allowed": False},
        "dispatches": [
            {
                "dispatch_revision_id": DISPATCH,
                "status": "reconciliation_pending_attempt_journal",
                "reconciliation": {"attempt_id": _attempt(1)},
                "authorization_valid": True,
                "manual_packet_ready": True,
                "dispatch_allowed": False,
            }
        ],
    }
    annotated = annotate_execution_projection(execution, load_attempt_projection(tmp_path))
    row = annotated["dispatches"][0]
    assert row["status"] == "reconciliation_dry_run_only"
    assert row["authorization_valid"] is False
    assert row["manual_packet_ready"] is False
    assert row["dispatch_allowed"] is False
