"""Load-bearing invariants for the portfolio event persistence boundary."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digital_asset_directory import portfolio_events as pe
from digital_asset_directory.utils import json_dumps

pytestmark = pytest.mark.unit

T0 = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
STREAM = "dad:portfolio-workstream:00000000-0000-0000-0000-000000000001"


def _feedback(note: str) -> dict[str, object]:
    return {
        "workstream_id": STREAM,
        "action": "dismiss",
        "note": note,
        "snooze_until": "",
        "review_at": "",
        "trigger_signature": "trigger-1",
    }


def _event(
    note: str,
    *,
    previous: str = "",
    command_id: str | None = None,
    when: datetime = T0,
) -> dict[str, object]:
    event, _ = pe.build_event(
        event_kind="focus_feedback",
        stream_id=STREAM,
        payload=_feedback(note),
        prev_event_id=previous,
        recorded_at=when.isoformat(),
        command_id=command_id,
    )
    return event


def test_explicit_command_id_dedupes_retry_without_time_heuristic(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    first = _event("same", command_id="request-42", when=T0)
    replay = _event("same", command_id="request-42", when=T0 + timedelta(days=1))

    assert pe.append_events(ledger, [first], recorded_at=T0.isoformat())["events_appended"] == 1
    result = pe.append_events(ledger, [replay], recorded_at=(T0 + timedelta(days=1)).isoformat())

    assert result["events_appended"] == 0
    assert result["events_deduplicated"] == 1


def test_missing_command_id_means_new_intent_and_rebases_linearly(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    first = _event("same", when=T0)
    second = _event("same", when=T0 + timedelta(hours=1))
    pe.append_events(ledger, [first], recorded_at=T0.isoformat())
    pe.append_events(ledger, [second], recorded_at=(T0 + timedelta(hours=1)).isoformat())

    events, diagnostics = pe.read_events(ledger)

    assert diagnostics["problems"] == []
    assert len(events) == 2
    assert events[1]["prev_event_id"] == events[0]["event_id"]
    assert events[1]["command_id"] != events[0]["command_id"]


def test_concurrent_stale_heads_are_rebased_under_the_lock(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    root = _event("root")
    pe.append_events(ledger, [root], recorded_at=T0.isoformat())
    stale_head = pe.read_events(ledger)[0][0]["event_id"]

    def worker(index: int) -> int:
        event = _event(
            f"worker-{index}",
            previous=stale_head,
            when=T0 + timedelta(minutes=index + 1),
        )
        return int(
            pe.append_events(
                ledger,
                [event],
                recorded_at=(T0 + timedelta(minutes=index + 1)).isoformat(),
            )["events_appended"]
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        appended = list(pool.map(worker, range(8)))

    events, diagnostics = pe.read_events(ledger)

    assert sum(appended) == 8
    assert diagnostics["problems"] == []
    stream_events = [event for event in events if event["stream_id"] == STREAM]
    for previous, current in zip(stream_events, stream_events[1:]):
        assert current["prev_event_id"] == previous["event_id"]


def test_write_all_handles_repeated_short_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "events.jsonl"
    original_write = pe.os.write

    def short_write(fd: int, data: bytes | memoryview) -> int:
        chunk = bytes(data[:7])
        return original_write(fd, chunk)

    monkeypatch.setattr(pe.os, "write", short_write)
    result = pe.append_events(ledger, [_event("one"), _event("two")], recorded_at=T0.isoformat())
    events, diagnostics = pe.read_events(ledger)

    assert result["events_appended"] == 2
    assert len(events) == 2
    assert diagnostics["problems"] == []


def test_partial_write_failure_is_never_acknowledged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "events.jsonl"
    original_write = pe.os.write
    ledger_calls = 0

    def fail_after_partial(fd: int, data: bytes | memoryview) -> int:
        nonlocal ledger_calls
        blob = bytes(data)
        if b'"nonce"' in blob:
            return original_write(fd, blob)
        ledger_calls += 1
        if ledger_calls == 1:
            count = max(1, len(blob) // 2)
            original_write(fd, blob[:count])
            return count
        return 0

    monkeypatch.setattr(pe.os, "write", fail_after_partial)

    with pytest.raises(OSError, match="no forward progress"):
        pe.append_events(ledger, [_event("one"), _event("two")], recorded_at=T0.isoformat())

    assert ledger.exists()
    assert pe.read_events(ledger)[1]["torn_tail_pending"] is True


def test_persistence_boundary_rejects_schema_drift_and_never_writes_secret(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "events.jsonl"
    secret = "sk-" + "z" * 24
    event = _event(secret)
    event["unexpected"] = secret

    with pytest.raises(pe.LedgerValidationError, match="Additional properties"):
        pe.append_events(ledger, [event], recorded_at=T0.isoformat())

    assert not ledger.exists() or secret not in ledger.read_text(encoding="utf-8")


def test_build_minimizes_before_identity_and_persistence(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    secret = "sk-" + "a" * 24
    event = _event(f"rotate {secret}")
    pe.append_events(ledger, [event], recorded_at=T0.isoformat())

    raw = ledger.read_text(encoding="utf-8")
    persisted = json.loads(raw)

    assert secret not in raw
    assert persisted["payload"]["note"] == "rotate [REDACTED_SECRET]"
    assert persisted["redaction_count"] >= 1


def test_read_rejects_payload_tampering_and_chain_successors(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    first = _event("first")
    pe.append_events(ledger, [first], recorded_at=T0.isoformat())
    second = _event("second", previous=pe.read_events(ledger)[0][0]["event_id"])
    pe.append_events(ledger, [second], recorded_at=T0.isoformat())
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    rows[0]["payload"]["note"] = "tampered"
    ledger.write_text("".join(json_dumps(row) + "\n" for row in rows), encoding="utf-8")

    events, diagnostics = pe.read_events(ledger)

    assert events == []
    assert diagnostics["invalid_envelope_count"] == 2
    assert any("event_id_mismatch" in problem for problem in diagnostics["problems"])
    assert any("chain_predecessor_mismatch" in problem for problem in diagnostics["problems"])


def test_duplicate_event_id_conflict_is_diagnostic(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    event = _event("one")
    pe.append_events(ledger, [event], recorded_at=T0.isoformat())
    conflict = dict(json.loads(ledger.read_text(encoding="utf-8")))
    conflict["recorded_at"] = (T0 + timedelta(hours=1)).isoformat()
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json_dumps(conflict) + "\n")

    events, diagnostics = pe.read_events(ledger)

    assert len(events) == 1
    assert diagnostics["invalid_envelope_count"] == 1
    assert any("duplicate_event_id_conflict" in problem for problem in diagnostics["problems"])


def test_read_rejects_duplicate_json_object_keys_and_blocks_append(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    event = _event("one")
    serialized = json_dumps(event)
    duplicate_key_row = serialized.replace(
        "{", '{"event_kind":"focus_feedback","event_kind":"capsule_recorded",', 1
    )
    ledger.write_text(duplicate_key_row + "\n", encoding="utf-8")

    events, diagnostics = pe.read_events(ledger)

    assert events == []
    assert diagnostics["corrupt_line_count"] == 1
    assert diagnostics["invalid_envelope_count"] == 0
    assert diagnostics["problems"] == ["line:1:duplicate_json_object_key"]
    assert not pe.quarantine_path(ledger).exists()
    with pytest.raises(pe.LedgerIntegrityError, match="duplicate_json_object_key"):
        pe.append_events(ledger, [_event("two")], recorded_at=T0.isoformat())
    assert ledger.read_text(encoding="utf-8") == duplicate_key_row + "\n"


def test_read_rejects_conflicting_per_stream_command_id_reuse(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    first = _event("one", command_id="request-42")
    conflict = _event(
        "different command content",
        previous=str(first["event_id"]),
        command_id="request-42",
        when=T0 + timedelta(hours=1),
    )
    ledger.write_text(
        json_dumps(first) + "\n" + json_dumps(conflict) + "\n",
        encoding="utf-8",
    )

    events, diagnostics = pe.read_events(ledger)

    assert events == [first]
    assert diagnostics["corrupt_line_count"] == 0
    assert diagnostics["invalid_envelope_count"] == 1
    assert diagnostics["problems"] == [
        f"line:2:command_id_conflict:{STREAM}:{first['command_id']}"
    ]
    with pytest.raises(pe.LedgerIntegrityError, match="command_id_conflict"):
        pe.append_events(ledger, [_event("two")], recorded_at=T0.isoformat())


def test_unlock_never_deletes_a_replacement_lock_generation(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    lock = pe.LedgerLock(ledger)
    lock.__enter__()
    path = pe.lock_path(ledger)
    replacement = {"pid": 987654321, "nonce": "replacement", "created_at_epoch": 0}
    path.write_text(json_dumps(replacement), encoding="utf-8")

    lock.__exit__(None, None, None)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["nonce"] == "replacement"
    path.unlink()


def test_lock_retries_transient_windows_creation_denial(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "events.jsonl"
    real_open = pe.os.open
    denied = False

    def flaky_open(path: object, flags: int, *args: object) -> int:
        nonlocal denied
        if str(path).endswith(".lock") and not denied:
            denied = True
            raise PermissionError("synthetic OneDrive release race")
        return real_open(path, flags, *args)

    monkeypatch.setattr(pe.os, "open", flaky_open)
    with pe.LedgerLock(ledger):
        assert pe.lock_path(ledger).exists()
    assert denied is True
    assert not pe.lock_path(ledger).exists()


def test_new_project_and_sovereignty_payload_contracts() -> None:
    project, _ = pe.build_event(
        event_kind="project_registered",
        stream_id="dad:project:dad",
        prev_event_id="",
        recorded_at=T0.isoformat(),
        payload={
            "project_id": "dad:project:dad",
            "name": "DAD",
            "parent_project_id": "",
            "note": "root",
        },
    )
    sovereignty, _ = pe.build_event(
        event_kind="sovereignty_recorded",
        stream_id="dad:project:child",
        prev_event_id="",
        recorded_at=T0.isoformat(),
        payload={
            "project_id": "dad:project:child",
            "sovereignty_state": "dad_governed_child",
            "decided_by": "human",
            "approval_ref": "approval-1",
            "note": "accepted",
        },
    )

    assert pe.envelope_problems(project) == []
    assert pe.envelope_problems(sovereignty) == []


def test_accepted_binding_requires_persistence_boundary_approval() -> None:
    payload = {
        "workstream_id": STREAM,
        "binding_id": "dad:portfolio-binding:00000000-0000-0000-0000-000000000002",
        "binding_kind": "blocks",
        "ref": "dad:portfolio-workstream:00000000-0000-0000-0000-000000000003",
        "label": "",
        "assertion_status": "accepted",
        "asserted_by": "",
        "approval_ref": "",
    }

    with pytest.raises(pe.LedgerValidationError, match="asserted_by|approval_ref"):
        pe.build_event(
            event_kind="binding_asserted",
            stream_id=STREAM,
            prev_event_id="",
            recorded_at=T0.isoformat(),
            payload=payload,
        )


def test_stream_identity_must_match_payload_identity() -> None:
    with pytest.raises(pe.LedgerValidationError, match="stream_id must equal"):
        pe.build_event(
            event_kind="focus_feedback",
            stream_id=STREAM,
            prev_event_id="",
            recorded_at=T0.isoformat(),
            payload={**_feedback("mismatch"), "workstream_id": "dad:other"},
        )
