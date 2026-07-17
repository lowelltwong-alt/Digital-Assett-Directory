from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from copy import deepcopy
import os
from pathlib import Path
import time

import pytest

from digital_asset_directory.portfolio_continuity_events import (
    ContinuityConflictError,
    ContinuityIntegrityError,
    ContinuityValidationError,
    _expected_event_id,
    _exclusive_lock,
    _validate_event_for_replay,
    _append_observation_to_ledger as append_observation,
    append_observation as append_production_observation,
    canonical_digest,
    read_observation_events,
    validate_adapter_receipt,
    validate_event,
)


def _receipt(**overrides):
    receipt = {
        "schema_version": "dad.portfolio_continuity_adapter_receipt.v1",
        "request_id": "receipt-001",
        "adapter_id": "adapter:codex-shadow",
        "adapter_revision_id": "adapter-revision:codex-shadow:0.1.0",
        "source_kind": "codex_task",
        "source_id": "task:123",
        "source_revision": "revision:7",
        "event_kind": "codex_task_observed",
        "observed_at": "2026-07-16T12:00:00+00:00",
        "privacy_partition": "private:personal",
        "payload": {
            "task_id": "task:123",
            "status": "active",
            "repository_id": "repo:dad",
            "title_fingerprint": "sha256:" + "a" * 64,
        },
    }
    receipt.update(overrides)
    return receipt


def test_exact_replay_deduplicates_and_conflicting_reuse_fails(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    first = append_observation(ledger, _receipt(), recorded_at="2026-07-16T12:01:00+00:00")
    retry = append_observation(ledger, _receipt(), recorded_at="2026-07-16T13:01:00+00:00")

    assert first["status"] == "appended"
    assert retry["status"] == "deduplicated"
    assert retry["event"]["event_id"] == first["event"]["event_id"]
    assert len(read_observation_events(ledger)) == 1

    conflicting = _receipt(payload={**_receipt()["payload"], "status": "paused"})
    with pytest.raises(ContinuityConflictError, match="request_id was reused"):
        append_observation(ledger, conflicting)
    assert len(read_observation_events(ledger)) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prompt", "do the private thing"),
        ("transcript", "raw conversation"),
        ("api_token", "credential material"),
        ("source_content", "source blob"),
    ],
)
def test_raw_or_sensitive_fields_are_rejected_before_persistence(
    tmp_path: Path, field: str, value: str
) -> None:
    ledger = tmp_path / "events.jsonl"
    receipt = _receipt(payload={**_receipt()["payload"], field: value})
    with pytest.raises(ContinuityValidationError, match="forbidden raw or sensitive field"):
        append_observation(ledger, receipt)
    assert not ledger.exists()


@pytest.mark.parametrize(
    "path_value",
    [
        r"C:\\Users\\person\\repo",
        "/home/person/repo",
        r"\\\\server\\private",
    ],
)
def test_path_shaped_values_are_rejected(tmp_path: Path, path_value: str) -> None:
    ledger = tmp_path / "events.jsonl"
    receipt = _receipt(payload={**_receipt()["payload"], "display_label": path_value})
    with pytest.raises(ContinuityValidationError, match="path-shaped"):
        append_observation(ledger, receipt)
    assert not ledger.exists()


def test_event_chain_and_payload_tampering_are_detected(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    result = append_observation(ledger, _receipt())
    event = result["event"]
    validate_event(event)

    event["payload"]["status"] = "tampered"
    ledger.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(ContinuityIntegrityError, match="invalid event"):
        read_observation_events(ledger)


def test_malformed_tail_blocks_read_and_append(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    append_observation(ledger, _receipt())
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write('{"partial":')

    with pytest.raises(ContinuityIntegrityError, match="invalid JSON"):
        read_observation_events(ledger)
    with pytest.raises(ContinuityIntegrityError, match="invalid JSON"):
        append_observation(ledger, _receipt(request_id="receipt-002"))


def test_schema_rejects_unknown_receipt_fields() -> None:
    receipt = _receipt()
    receipt["provider_private_extension"] = "not allowed"
    with pytest.raises(ContinuityValidationError, match="Additional properties"):
        validate_adapter_receipt(receipt)


def test_production_observation_fails_closed_without_private_root(tmp_path: Path) -> None:
    with pytest.raises(ContinuityIntegrityError, match="initialized DAD_DATA_ROOT"):
        append_production_observation(tmp_path, _receipt())


def test_persisted_event_contains_only_minimized_candidate_metadata(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    result = append_observation(
        ledger,
        _receipt(payload={**_receipt()["payload"], "display_label": "  paused   build  "}),
    )
    event = result["event"]

    assert event["payload"]["display_label"] == "paused build"
    assert event["redaction_count"] == 1
    assert event["candidate_only"] is True
    assert event["execution_authorized"] is False
    assert "request_id" not in event


def test_stale_dead_owner_lock_is_recovered_without_stealing_live_lock(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "events.jsonl"
    lock_path = ledger.with_suffix(ledger.suffix + ".lock")
    lock_path.write_text(json.dumps({"pid": 2_147_483_647}), encoding="ascii")
    old = time.time() - 120
    os.utime(lock_path, (old, old))

    with _exclusive_lock(ledger, timeout_seconds=0.2):
        assert lock_path.exists()
    assert not lock_path.exists()

    lock_path.write_text(json.dumps({"pid": os.getpid()}), encoding="ascii")
    os.utime(lock_path, (old, old))
    with pytest.raises(ContinuityIntegrityError, match="timed out"):
        with _exclusive_lock(ledger, timeout_seconds=0.05):
            pass
    assert lock_path.exists()


def test_concurrent_stale_lock_recovery_is_serialized(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    lock_path = ledger.with_suffix(ledger.suffix + ".lock")
    lock_path.write_text(
        json.dumps({"pid": 2_147_483_647, "created_at_epoch": 0}),
        encoding="ascii",
    )
    old = time.time() - 120
    os.utime(lock_path, (old, old))
    visits: list[int] = []

    def recover(worker: int) -> None:
        with _exclusive_lock(ledger, timeout_seconds=2.0):
            visits.append(worker)
            time.sleep(0.02)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(recover, (1, 2)))

    assert sorted(visits) == [1, 2]
    assert not lock_path.exists()


def test_exact_content_index_invalidates_on_ledger_change(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    append_observation(ledger, _receipt())
    index = ledger.with_suffix(ledger.suffix + ".index.json")
    assert index.exists()

    with ledger.open("a", encoding="utf-8") as handle:
        handle.write('{"partial":')

    with pytest.raises(ContinuityIntegrityError, match="invalid JSON"):
        append_observation(ledger, _receipt(request_id="receipt-002"))


def test_tampered_index_is_ignored_and_rebuilt_from_authoritative_ledger(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "events.jsonl"
    append_observation(ledger, _receipt())
    index_path = ledger.with_suffix(ledger.suffix + ".index.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["last_event_id"] = "dad:continuity-event:" + "0" * 64
    index_path.write_text(json.dumps(index), encoding="utf-8")

    result = append_observation(ledger, _receipt(request_id="receipt-002"))

    assert result["status"] == "appended"
    assert len(read_observation_events(ledger)) == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_kind", "not-a-real-event"),
        ("recorded_at", "2026-07-17T00:00:00"),
        ("redaction_count", -1),
        ("source_id", "x" * 241),
        ("candidate_only", False),
    ],
)
def test_fast_replay_validator_matches_full_schema_for_contract_failures(
    tmp_path: Path, field: str, value: object
) -> None:
    ledger = tmp_path / "events.jsonl"
    event = append_observation(ledger, _receipt())["event"]
    tampered = deepcopy(event)
    tampered[field] = value

    with pytest.raises(ContinuityValidationError):
        validate_event(tampered)
    with pytest.raises(ContinuityValidationError):
        _validate_event_for_replay(tampered)


def test_fast_replay_rejects_coherently_rehashed_extra_payload_property(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "events.jsonl"
    event = append_observation(ledger, _receipt())["event"]
    tampered = deepcopy(event)
    tampered["payload"]["unexpected_private_field"] = "must-not-survive-replay"
    tampered["payload_digest"] = canonical_digest(tampered["payload"])
    tampered["event_id"] = _expected_event_id(tampered)

    with pytest.raises(ContinuityValidationError):
        validate_event(tampered)
    with pytest.raises(ContinuityValidationError):
        _validate_event_for_replay(tampered)
