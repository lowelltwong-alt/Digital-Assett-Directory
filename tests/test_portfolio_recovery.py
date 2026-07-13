from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from digital_asset_directory.ids import stable_id
from digital_asset_directory.portfolio_events import (
    EventConflictError,
    LedgerValidationError,
    RECOVERY_EVENT_SCHEMA_VERSION,
    build_event,
    envelope_problems,
    ledger_path,
    quarantine_path,
    read_events,
)
from digital_asset_directory.portfolio_recovery import (
    RecoveryStateError,
    RecoveryValidationError,
    build_recovery_packet,
    case_preconditions_digest,
    fold_recovery_events,
    load_recovery_projection,
    record_recovery_result,
    record_shaping_decision,
    recovery_packet_problems,
    retract_shaping_decision,
    shaping_source_snapshot_digest,
)

pytestmark = pytest.mark.unit

T0 = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _shaping() -> tuple[dict[str, object], str, str, list[dict[str, object]]]:
    case_id = stable_id("dad.portfolio-workstream-shaping.v1", "recovery", "case-1")
    revision_id = stable_id(case_id, "revision-1")
    choices = [
        {
            "choice_id": stable_id(case_id, "review"),
            "choice_kind": "review",
            "label": "Review",
            "effect_preview": "Inspect exact local evidence without changing state.",
            "execution_available": False,
            "requires_human_decision": True,
        },
        {
            "choice_id": stable_id(case_id, "defer"),
            "choice_kind": "defer",
            "label": "Defer",
            "effect_preview": "Make no state change and revisit with better evidence.",
            "execution_available": False,
            "requires_human_decision": True,
        },
    ]
    case = {
        "case_id": case_id,
        "revision_id": revision_id,
        "case_kind": "recovery",
        "evidence_tier": "RC1_dirty_or_unattended_observed_resource",
        "disposition": "review",
        "label": "Observed recovery evidence",
        "subject_workstream_ids": ["dad:portfolio-workstream:00000000-0000-0000-0000-000000000001"],
        "subject_resource_ids": ["dad:portfolio-resource:00000000-0000-0000-0000-000000000001"],
        "source_attention_ids": [],
        "source_bundle_ids": [],
        "signals": ["observed_dirty"],
        "counterevidence": [],
        "evidence_summary": {
            "exact_component_count": 0,
            "project_count": 1,
            "shared_specific_resource_count": 0,
            "shared_token_count": 0,
            "shared_token_hashes": [],
            "attention_bands": ["review"],
            "trigger_kinds": ["dirty_worktree"],
            "context_basis": "observed_attention",
        },
        "choices": choices,
    }
    source_refs = {
        "workstreams": "sha256:" + "1" * 64,
        "cockpit": "sha256:" + "2" * 64,
        "reconciliation": "sha256:" + "3" * 64,
    }
    shaping: dict[str, object] = {
        "schema_version": "dad.portfolio_workstream_shaping.v1",
        "generated_at": T0.isoformat(),
        "status": "generated_candidate",
        "execution_authorized": False,
        "source_authority_mutated": False,
        "sources": {
            name: {
                "name": name,
                "status": "observed",
                "freshness": "current",
                "schema_version": f"test.{name}.v1",
                "generated_at": T0.isoformat(),
                "source_hash": digest,
                "problems": [],
            }
            for name, digest in source_refs.items()
        },
        "source_refs": source_refs,
        "source_coupling": {
            "workstreams_to_cockpit": {"matches": True},
            "cockpit_to_reconciliation": {"matches": True},
            "reconciliation_fully_reconciled": True,
        },
        "cases": [case],
    }
    return shaping, case_id, revision_id, choices


def _record(
    hub: Path,
    shaping: dict[str, object],
    case_id: str,
    revision_id: str,
    choice: dict[str, object],
    *,
    command_id: str,
    supersedes: str = "",
    now: datetime = T0,
) -> dict[str, object]:
    return record_shaping_decision(
        hub,
        shaping,
        case_id=case_id,
        case_revision_id=revision_id,
        choice_id=str(choice["choice_id"]),
        approver="human:lowell",
        approval_ref="approval:recovery:1",
        command_id=command_id,
        supersedes_decision_id=supersedes,
        now=now,
    )


def test_recovery_event_uses_third_strict_schema_and_case_stream() -> None:
    shaping, case_id, revision_id, choices = _shaping()
    case = shaping["cases"][0]
    payload = {
        "decision_id": stable_id("portfolio-decision", case_id, "one"),
        "case_id": case_id,
        "case_revision_id": revision_id,
        "source_snapshot_digest": shaping_source_snapshot_digest(shaping, now=T0),
        "expected_preconditions_digest": case_preconditions_digest(case),
        "choice_id": choices[0]["choice_id"],
        "choice_kind": choices[0]["choice_kind"],
        "disposition": "approved",
        "review_after": "",
        "approver": "human:lowell",
        "approval_ref": "approval:recovery:1",
        "supersedes_decision_id": "",
    }

    event, _ = build_event(
        event_kind="shaping_decision_recorded",
        stream_id=case_id,
        payload=payload,
        prev_event_id="",
        recorded_at=T0.isoformat(),
        command_id="decision-1",
    )

    assert event["schema_version"] == RECOVERY_EVENT_SCHEMA_VERSION
    assert envelope_problems(event) == []
    wrong_stream = dict(event, stream_id=stable_id("other-case", "one"))
    assert any(
        "stream_id must equal payload.case_id" in row for row in envelope_problems(wrong_stream)
    )
    with pytest.raises(LedgerValidationError, match="Additional properties"):
        build_event(
            event_kind="shaping_decision_recorded",
            stream_id=case_id,
            payload=payload | {"unexpected": True},
            prev_event_id="",
            recorded_at=T0.isoformat(),
            command_id="decision-2",
        )
    with pytest.raises(LedgerValidationError, match="does not match"):
        build_event(
            event_kind="shaping_decision_recorded",
            stream_id=case_id,
            payload=payload | {"approver": "C:\\private\\name.txt"},
            prev_event_id="",
            recorded_at=T0.isoformat(),
            command_id="decision-3",
        )


def test_decision_retry_deduplicates_and_conflicting_retry_fails(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    first = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="same-request",
    )
    retry = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="same-request",
    )

    assert first["events_appended"] == 1
    assert retry["events_appended"] == 0
    assert retry["events_deduplicated"] == 1
    with pytest.raises(EventConflictError, match="command_id conflicts"):
        _record(
            tmp_path,
            shaping,
            case_id,
            revision_id,
            choices[1],
            command_id="same-request",
        )


def test_decision_retry_precedes_current_source_validation(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    first = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="retry-after-source-change",
    )
    changed = deepcopy(shaping)
    changed["cases"][0]["revision_id"] = stable_id(case_id, "later-revision")
    changed["sources"]["workstreams"]["generated_at"] = datetime(
        2020, 1, 1, tzinfo=timezone.utc
    ).isoformat()

    retry = _record(
        tmp_path,
        changed,
        case_id,
        revision_id,
        choices[0],
        command_id="retry-after-source-change",
        now=T0 + timedelta(days=2),
    )

    assert first["events_appended"] == 1
    assert retry["status"] == "deduplicated"
    assert retry["events_deduplicated"] == 1
    with pytest.raises(EventConflictError, match="command_id conflicts"):
        _record(
            tmp_path,
            changed,
            case_id,
            revision_id,
            choices[1],
            command_id="retry-after-source-change",
            now=T0 + timedelta(days=2),
        )


@pytest.mark.parametrize("stale_part", ["revision", "snapshot", "preconditions"])
def test_decision_rejects_stale_case_bindings(tmp_path: Path, stale_part: str) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    kwargs: dict[str, object] = {}
    requested_revision = revision_id
    if stale_part == "revision":
        requested_revision = stable_id(case_id, "old-revision")
    elif stale_part == "snapshot":
        kwargs["expected_source_snapshot_digest"] = "sha256:" + "9" * 64
    else:
        kwargs["expected_preconditions_digest"] = "sha256:" + "8" * 64

    with pytest.raises(RecoveryStateError, match="stale"):
        record_shaping_decision(
            tmp_path,
            shaping,
            case_id=case_id,
            case_revision_id=requested_revision,
            choice_id=str(choices[0]["choice_id"]),
            approver="human:lowell",
            approval_ref="approval:recovery:1",
            command_id=f"stale-{stale_part}",
            now=T0,
            **kwargs,
        )
    assert not ledger_path(tmp_path).exists()


def test_decision_allows_current_sources_with_partial_reconciliation(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    shaping["status"] = "partial_candidate"
    shaping["source_coupling"]["reconciliation_fully_reconciled"] = False

    result = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="partial-reconciliation",
    )

    assert result["events_appended"] == 1
    assert load_recovery_projection(tmp_path, shaping, now=T0)["decisions"][0]["status"] == "active"


def test_v2_shaping_source_snapshot_field_matches_core_digest_contract() -> None:
    shaping, _case_id, _revision_id, _choices = _shaping()
    shaping["schema_version"] = "dad.portfolio_workstream_shaping.v2"
    shaping["source_snapshot_digest"] = shaping_source_snapshot_digest(shaping, now=T0)

    assert shaping_source_snapshot_digest(shaping, now=T0) == shaping["source_snapshot_digest"]


def test_decision_rejects_noncurrent_source_descriptor(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    shaping["sources"]["reconciliation"]["freshness"] = "stale"

    with pytest.raises(RecoveryValidationError, match="source is not current"):
        _record(
            tmp_path,
            shaping,
            case_id,
            revision_id,
            choices[0],
            command_id="stale-source-descriptor",
        )

    assert not ledger_path(tmp_path).exists()


def test_decision_rejects_old_descriptor_even_when_label_claims_current(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    shaping["sources"]["workstreams"]["generated_at"] = datetime(
        2020, 1, 1, tzinfo=timezone.utc
    ).isoformat()

    with pytest.raises(RecoveryValidationError, match="stale by observed time"):
        _record(
            tmp_path,
            shaping,
            case_id,
            revision_id,
            choices[0],
            command_id="stale-generated-at",
            now=T0,
        )

    assert not ledger_path(tmp_path).exists()


def test_supersession_and_retraction_are_explicit_inverse_events(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    first = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-one",
    )
    second = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[1],
        command_id="decision-two",
        supersedes=str(first["decision_id"]),
        now=T0 + timedelta(minutes=1),
    )

    projection = load_recovery_projection(tmp_path, shaping, now=T0 + timedelta(minutes=1))
    by_id = {row["decision_id"]: row for row in projection["decisions"]}
    assert by_id[first["decision_id"]]["status"] == "retracted"
    assert by_id[first["decision_id"]]["superseded_by_decision_id"] == second["decision_id"]
    assert by_id[second["decision_id"]]["status"] == "active"

    retracted = retract_shaping_decision(
        tmp_path,
        str(second["decision_id"]),
        retracted_by="human:lowell",
        approval_ref="approval:retract:1",
        reason_code="decision_changed",
        command_id="retract-two",
        now=T0 + timedelta(minutes=2),
    )
    assert retracted["events_appended"] == 1
    final = load_recovery_projection(tmp_path, shaping, now=T0 + timedelta(minutes=2))
    assert {row["status"] for row in final["decisions"]} == {"retracted"}


def test_fold_marks_active_decision_stale_without_mutating_ledger(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-one",
    )
    events, diagnostics = read_events(ledger_path(tmp_path))
    changed = deepcopy(shaping)
    changed["cases"][0]["revision_id"] = stable_id(case_id, "revision-2")

    projection = fold_recovery_events(
        events, changed, ledger_diagnostics=diagnostics, now=T0
    )

    assert projection["decisions"][0]["status"] == "stale"
    assert projection["execution_authorized"] is False
    assert read_events(ledger_path(tmp_path))[0] == events


def test_packet_is_transient_private_minimized_and_never_authorizes(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    recorded = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-one",
    )

    packet = build_recovery_packet(
        tmp_path,
        shaping,
        str(recorded["decision_id"]),
        now=T0 + timedelta(minutes=1),
    )
    serialized = json.dumps(packet, sort_keys=True)

    assert recovery_packet_problems(packet) == []
    assert packet["execution_authorized"] is False
    assert packet["mutations_performed"] is False
    assert packet["source_authority_mutated"] is False
    assert "path" not in {key.casefold() for key in packet}
    assert "command" not in {key.casefold() for key in packet}
    assert "C:\\" not in serialized and "/Users/" not in serialized
    tainted = dict(packet, path="C:\\private\\secret.txt")
    assert "packet_fields_mismatch" in recovery_packet_problems(tainted)
    assert "packet_forbidden_field" in recovery_packet_problems(tainted)
    assert "packet_path_or_prose_exposed" in recovery_packet_problems(tainted)


def test_packet_id_binds_every_exact_approval_field(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    recorded = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-packet-binding",
    )
    packet = build_recovery_packet(
        tmp_path,
        shaping,
        str(recorded["decision_id"]),
        now=T0 + timedelta(minutes=1),
    )
    before = "sha256:" + "4" * 64
    after = "sha256:" + "5" * 64

    fabricated = dict(packet)
    fabricated["packet_id"] = stable_id("portfolio-recovery-packet", "fabricated")
    assert "packet_id_does_not_bind_exact_receipt" in recovery_packet_problems(fabricated)
    with pytest.raises(RecoveryValidationError, match="does_not_bind_exact_receipt"):
        record_recovery_result(
            tmp_path,
            shaping,
            fabricated,
            result_status="verified",
            before_snapshot_digest=before,
            after_snapshot_digest=after,
            worker_id="role:worker:v1",
            checker_id="role:checker:v2",
            evidence_refs=["test:packet-binding:1"],
            command_id="fabricated-packet-result",
            now=T0 + timedelta(minutes=2),
        )

    changed_approval = dict(packet, approval_ref="approval:other")
    assert "packet_id_does_not_bind_exact_receipt" in recovery_packet_problems(
        changed_approval
    )


def test_manual_result_requires_distinct_checker_and_folds_compatibly(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    recorded = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-one",
    )
    packet = build_recovery_packet(
        tmp_path,
        shaping,
        str(recorded["decision_id"]),
        now=T0 + timedelta(minutes=1),
    )
    before = "sha256:" + "4" * 64
    after = "sha256:" + "5" * 64

    with pytest.raises(RecoveryValidationError, match="must be distinct"):
        record_recovery_result(
            tmp_path,
            shaping,
            packet,
            result_status="verified",
            before_snapshot_digest=before,
            after_snapshot_digest=after,
            worker_id="role:worker:v1",
            checker_id="role:worker:v1",
            evidence_refs=["test:recovery:1"],
            command_id="result-one",
            now=T0 + timedelta(minutes=2),
        )

    result = record_recovery_result(
        tmp_path,
        shaping,
        packet,
        result_status="verified",
        before_snapshot_digest=before,
        after_snapshot_digest=after,
        worker_id="role:worker:v1",
        checker_id="role:checker:v2",
        evidence_refs=["test:recovery:1"],
        command_id="result-one",
        now=T0 + timedelta(minutes=2),
    )
    retry = record_recovery_result(
        tmp_path,
        shaping,
        packet,
        result_status="verified",
        before_snapshot_digest=before,
        after_snapshot_digest=after,
        worker_id="role:worker:v1",
        checker_id="role:checker:v2",
        evidence_refs=["test:recovery:1"],
        command_id="result-one",
        now=T0 + timedelta(minutes=2),
    )

    assert result["events_appended"] == 1
    assert result["execution_authorized"] is False
    assert retry["events_deduplicated"] == 1
    projection = load_recovery_projection(tmp_path, shaping, now=T0 + timedelta(minutes=2))
    assert projection["results"] == [
        projection["results"][0] | {"status": "verified", "result_status": "verified"}
    ]
    assert projection["results"][0]["decision_id"] == recorded["decision_id"]
    assert projection["results"][0]["packet_id"] == packet["packet_id"]


def test_result_retry_precedes_expiry_but_conflict_still_fails(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    recorded = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-expiring-packet",
    )
    packet = build_recovery_packet(
        tmp_path,
        shaping,
        str(recorded["decision_id"]),
        now=T0 + timedelta(minutes=1),
        expires_at=T0 + timedelta(minutes=2),
    )
    kwargs = {
        "result_status": "verified",
        "before_snapshot_digest": "sha256:" + "4" * 64,
        "after_snapshot_digest": "sha256:" + "5" * 64,
        "worker_id": "role:worker:v1",
        "checker_id": "role:checker:v2",
        "evidence_refs": ["test:expired-retry:1"],
        "command_id": "result-expiring-packet",
    }
    first = record_recovery_result(
        tmp_path,
        shaping,
        packet,
        now=T0 + timedelta(minutes=1, seconds=30),
        **kwargs,
    )
    retry = record_recovery_result(
        tmp_path,
        shaping,
        packet,
        now=T0 + timedelta(days=1),
        **kwargs,
    )

    assert first["events_appended"] == 1
    assert retry["status"] == "deduplicated"
    with pytest.raises(EventConflictError, match="command_id conflicts"):
        record_recovery_result(
            tmp_path,
            shaping,
            packet,
            now=T0 + timedelta(days=1),
            **(kwargs | {"after_snapshot_digest": "sha256:" + "6" * 64}),
        )


def test_torn_tail_blocks_recovery_without_repair_or_append(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    first = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-one",
    )
    ledger = ledger_path(tmp_path)
    with ledger.open("ab") as handle:
        handle.write(b'{"torn":')
    frozen = ledger.read_bytes()

    with pytest.raises(RecoveryStateError, match="torn_tail_pending"):
        _record(
            tmp_path,
            shaping,
            case_id,
            revision_id,
            choices[1],
            command_id="decision-two",
            supersedes=str(first["decision_id"]),
            now=T0 + timedelta(minutes=1),
        )

    assert ledger.read_bytes() == frozen
    assert not quarantine_path(ledger).exists()


def test_corrupt_interior_blocks_recovery_append(tmp_path: Path) -> None:
    shaping, case_id, revision_id, choices = _shaping()
    first = _record(
        tmp_path,
        shaping,
        case_id,
        revision_id,
        choices[0],
        command_id="decision-one",
    )
    ledger = ledger_path(tmp_path)
    original = ledger.read_bytes()
    ledger.write_bytes(original + b"not-json\n")
    frozen = ledger.read_bytes()

    with pytest.raises(RecoveryStateError, match="unsafe"):
        retract_shaping_decision(
            tmp_path,
            str(first["decision_id"]),
            retracted_by="human:lowell",
            approval_ref="approval:retract:1",
            reason_code="test_corruption",
            command_id="retract-corrupt",
            now=T0 + timedelta(minutes=2),
        )
    assert ledger.read_bytes() == frozen
