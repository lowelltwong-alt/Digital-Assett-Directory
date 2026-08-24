from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

import digital_asset_directory.portfolio_continuity_events as continuity_events
from digital_asset_directory.portfolio_continuity_codex_hook import (
    build_codex_hook_receipt,
)
from digital_asset_directory.portfolio_continuity_events import (
    ContinuityValidationError,
    _append_codex_hook_observation_to_ledger,
    _expected_event_id,
    _validate_codex_hook_event_fast,
    _validate_codex_hook_receipt_fast,
    canonical_digest,
    validate_adapter_receipt,
    validate_event,
)


ROOT = Path(__file__).resolve().parents[1]


def _hook_input(event_name: str = "Stop") -> dict[str, str]:
    value = {
        "session_id": "session-private",
        "turn_id": "turn-private",
        "hook_event_name": event_name,
    }
    if event_name == "SessionStart":
        value.pop("turn_id")
        value["source"] = "resume"
    elif event_name in {"PreCompact", "PostCompact"}:
        value["trigger"] = "auto"
    return value


def _full_payload() -> dict[str, Any]:
    return {
        "task_id": "task:1",
        "status": "active",
        "archive_state": "open",
        "created_at": "2026-08-21T00:00:00+00:00",
        "updated_at": "2026-08-21T00:00:01+00:00",
        "last_observed_at": "2026-08-21T00:00:02+00:00",
        "display_label": "bounded label",
        "title_fingerprint": "sha256:" + "1" * 64,
        "repository_id": "dad",
        "branch_id": "branch:1",
        "worktree_id": "worktree:1",
        "plan_id": "plan:1",
        "entity_id": "entity:1",
        "workstream_id": "workstream:1",
        "session_id": "codex-session:" + "2" * 64,
        "interrupted_entity_id": "entity:old",
        "new_entity_id": "entity:new",
        "reason_code": "codex_turn_stop",
        "source_digest": "sha256:" + "3" * 64,
        "last_material_activity_at": "2026-08-21T00:00:03+00:00",
        "coverage_status": "partial",
        "coverage_gaps": ["gap-a", "gap-b"],
        "recommended_action": "inspect",
    }


def _receipt() -> dict[str, Any]:
    value = build_codex_hook_receipt(
        _hook_input(),
        observed_at="2026-08-21T00:00:00+00:00",
        repository_id="dad",
    )
    value["payload"] = _full_payload()
    return value


def _accepted(validator: Callable[[Any], None], value: Any) -> bool:
    try:
        validator(value)
    except ContinuityValidationError:
        return False
    return True


def _assert_receipt_parity(value: Any, *, accepted: bool) -> None:
    assert _accepted(validate_adapter_receipt, value) is accepted
    assert _accepted(_validate_codex_hook_receipt_fast, value) is accepted


def _assert_event_parity(value: Any, *, accepted: bool) -> None:
    assert _accepted(validate_event, value) is accepted
    assert _accepted(_validate_codex_hook_event_fast, value) is accepted


def _invalid_type(rule: dict[str, Any]) -> Any:
    return {
        "string": 1,
        "integer": "1",
        "boolean": 1,
        "object": [],
        "array": {},
    }[rule["type"]]


def test_fast_receipt_validator_matches_full_oracle_for_every_schema_rule() -> None:
    receipt = _receipt()
    _assert_receipt_parity(receipt, accepted=True)
    schema = json.loads(
        (ROOT / "schemas/portfolio-continuity-adapter-receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )

    invalid: list[tuple[str, dict[str, Any]]] = []
    for field in schema["required"]:
        value = deepcopy(receipt)
        value.pop(field)
        invalid.append((f"missing:{field}", value))
    extra = deepcopy(receipt)
    extra["unexpected"] = True
    invalid.append(("additionalProperties", extra))

    for field, rule in schema["properties"].items():
        if "type" in rule:
            value = deepcopy(receipt)
            value[field] = _invalid_type(rule)
            invalid.append((f"type:{field}", value))
        if "const" in rule:
            value = deepcopy(receipt)
            value[field] = "not-the-const"
            invalid.append((f"const:{field}", value))
        if "enum" in rule:
            value = deepcopy(receipt)
            value[field] = "not-an-enum"
            invalid.append((f"enum:{field}", value))
        if rule.get("minLength"):
            value = deepcopy(receipt)
            value[field] = ""
            invalid.append((f"minLength:{field}", value))
        if "maxLength" in rule:
            value = deepcopy(receipt)
            value[field] = "x" * (int(rule["maxLength"]) + 1)
            invalid.append((f"maxLength:{field}", value))
        if "pattern" in rule:
            value = deepcopy(receipt)
            value[field] = "not-a-pattern"
            invalid.append((f"pattern:{field}", value))

    payload_schema = schema["properties"]["payload"]
    empty_payload = deepcopy(receipt)
    empty_payload["payload"] = {}
    invalid.append(("payload:minProperties", empty_payload))
    extra_payload = deepcopy(receipt)
    extra_payload["payload"]["unexpected"] = "x"
    invalid.append(("payload:additionalProperties", extra_payload))
    for field, rule in payload_schema["properties"].items():
        if "type" in rule:
            value = deepcopy(receipt)
            value["payload"][field] = _invalid_type(rule)
            invalid.append((f"payload:type:{field}", value))
        if "enum" in rule:
            value = deepcopy(receipt)
            value["payload"][field] = "not-an-enum"
            invalid.append((f"payload:enum:{field}", value))
        if "maxLength" in rule:
            value = deepcopy(receipt)
            value["payload"][field] = "x" * (int(rule["maxLength"]) + 1)
            invalid.append((f"payload:maxLength:{field}", value))
        if "pattern" in rule:
            value = deepcopy(receipt)
            value["payload"][field] = "not-a-pattern"
            invalid.append((f"payload:pattern:{field}", value))
        if rule.get("type") == "array":
            value = deepcopy(receipt)
            value["payload"][field] = ["x"] * (int(rule["maxItems"]) + 1)
            invalid.append((f"payload:maxItems:{field}", value))
            value = deepcopy(receipt)
            value["payload"][field] = ["duplicate", "duplicate"]
            invalid.append((f"payload:uniqueItems:{field}", value))
            value = deepcopy(receipt)
            value["payload"][field] = [1]
            invalid.append((f"payload:itemType:{field}", value))
            value = deepcopy(receipt)
            value["payload"][field] = [""]
            invalid.append((f"payload:itemMinLength:{field}", value))
            value = deepcopy(receipt)
            value["payload"][field] = [
                "x" * (int(rule["items"]["maxLength"]) + 1)
            ]
            invalid.append((f"payload:itemMaxLength:{field}", value))

    privacy_key = deepcopy(receipt)
    privacy_key["payload"]["prompt"] = "private"
    invalid.append(("privacy:key", privacy_key))
    privacy_path = deepcopy(receipt)
    privacy_path["payload"]["display_label"] = r"C:\Users\private"
    invalid.append(("privacy:path", privacy_path))

    for label, value in invalid:
        try:
            _assert_receipt_parity(value, accepted=False)
        except AssertionError as exc:
            raise AssertionError(f"receipt parity mismatch for {label}") from exc

    format_annotation = deepcopy(receipt)
    format_annotation["observed_at"] = "not-a-date-time"
    format_annotation["payload"]["created_at"] = "not-a-date-time"
    _assert_receipt_parity(format_annotation, accepted=True)


def test_fast_event_validator_matches_full_oracle_for_every_schema_rule(
    tmp_path: Path,
) -> None:
    event = _append_codex_hook_observation_to_ledger(
        tmp_path / "events.jsonl",
        _receipt(),
        recorded_at="2026-08-21T00:00:01+00:00",
    )["event"]
    _assert_event_parity(event, accepted=True)
    schema = json.loads(
        (ROOT / "schemas/portfolio-continuity-event.schema.json").read_text(
            encoding="utf-8"
        )
    )
    invalid: list[tuple[str, dict[str, Any]]] = []
    for field in schema["required"]:
        value = deepcopy(event)
        value.pop(field)
        invalid.append((f"missing:{field}", value))
    extra = deepcopy(event)
    extra["unexpected"] = True
    invalid.append(("additionalProperties", extra))
    for field, rule in schema["properties"].items():
        if "type" in rule:
            value = deepcopy(event)
            value[field] = _invalid_type(rule)
            invalid.append((f"type:{field}", value))
        if "const" in rule:
            value = deepcopy(event)
            value[field] = not bool(rule["const"])
            invalid.append((f"const:{field}", value))
        if "enum" in rule:
            value = deepcopy(event)
            value[field] = "not-an-enum"
            invalid.append((f"enum:{field}", value))
        if rule.get("minLength"):
            value = deepcopy(event)
            value[field] = ""
            invalid.append((f"minLength:{field}", value))
        if "maxLength" in rule:
            value = deepcopy(event)
            value[field] = "x" * (int(rule["maxLength"]) + 1)
            invalid.append((f"maxLength:{field}", value))
        if "pattern" in rule:
            value = deepcopy(event)
            value[field] = "not-a-pattern"
            invalid.append((f"pattern:{field}", value))
        if "minimum" in rule:
            value = deepcopy(event)
            value[field] = int(rule["minimum"]) - 1
            invalid.append((f"minimum:{field}", value))

    payload_extra = deepcopy(event)
    payload_extra["payload"]["unexpected"] = "x"
    payload_extra["payload_digest"] = canonical_digest(payload_extra["payload"])
    payload_extra["event_id"] = _expected_event_id(payload_extra)
    invalid.append(("payload:additionalProperties", payload_extra))
    bad_digest = deepcopy(event)
    bad_digest["payload_digest"] = "sha256:" + "0" * 64
    invalid.append(("payload:digest", bad_digest))
    bad_identity = deepcopy(event)
    bad_identity["event_id"] = "dad:continuity-event:" + "0" * 64
    invalid.append(("event:identity", bad_identity))
    privacy_path = deepcopy(event)
    privacy_path["payload"]["display_label"] = "/home/private"
    privacy_path["payload_digest"] = canonical_digest(privacy_path["payload"])
    privacy_path["event_id"] = _expected_event_id(privacy_path)
    invalid.append(("privacy:path", privacy_path))

    for label, value in invalid:
        try:
            _assert_event_parity(value, accepted=False)
        except AssertionError as exc:
            raise AssertionError(f"event parity mismatch for {label}") from exc

    format_annotation = deepcopy(event)
    format_annotation["observed_at"] = "not-a-date-time"
    format_annotation["payload"]["created_at"] = "not-a-date-time"
    format_annotation["payload_digest"] = canonical_digest(format_annotation["payload"])
    format_annotation["event_id"] = _expected_event_id(format_annotation)
    _assert_event_parity(format_annotation, accepted=True)


def test_fast_hook_schema_digest_guard_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _receipt()
    validate_adapter_receipt(receipt)

    monkeypatch.setattr(
        continuity_events,
        "RECEIPT_SCHEMA_SHA256",
        "sha256:" + "0" * 64,
    )
    with pytest.raises(ContinuityValidationError, match="fast validation is stale"):
        _validate_codex_hook_receipt_fast(receipt)


@pytest.mark.parametrize(
    "event_name",
    ["SessionStart", "PreCompact", "PostCompact", "Stop"],
)
def test_all_codex_event_receipts_pass_full_and_fast_oracles(event_name: str) -> None:
    receipt = build_codex_hook_receipt(
        _hook_input(event_name),
        observed_at="2026-08-21T00:00:00+00:00",
        repository_id="dad",
    )
    _assert_receipt_parity(receipt, accepted=True)
