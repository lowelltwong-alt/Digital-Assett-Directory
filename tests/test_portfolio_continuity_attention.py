from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for

from digital_asset_directory.portfolio_continuity_attention import (
    STAGE_IDS,
    build_progressive_attention_readiness,
)


def _projection() -> dict:
    return {
        "projection_fingerprint": "sha256:" + "a" * 64,
        "queues": {
            "current_state": [{"plan_id": "plan:one"}],
            "interrupted_resume": [
                {
                    "plan_id": "plan:one",
                    "workstream_id": "ws:one",
                    "next_action": "resume bounded architecture test",
                    "reason_codes": ["unresumed_interruption"],
                }
            ],
            "next_actions": [
                {
                    "plan_id": "plan:two",
                    "workstream_id": "ws:two",
                    "next_action": "review provider boundary",
                }
            ],
        },
    }


def test_inactive_attention_contract_builds_bounded_non_deliverable_previews() -> None:
    packet = build_progressive_attention_readiness(_projection())

    assert tuple(row["stage_id"] for row in packet["stages"]) == STAGE_IDS
    assert packet["stages"][0]["status"] == "available"
    assert packet["stages"][2]["status"] == "blocked_by_supervised_trial"
    assert packet["session_start_summary_preview"]["item_count"] == 2
    assert packet["session_start_summary_preview"]["delivery_authorized"] is False
    assert len(packet["weekly_digest_preview"]["asks"]) <= 3
    assert packet["weekly_digest_preview"]["execution_authorized"] is False
    assert packet["breakpoint_prompt_preview"]["delivery_authorized"] is False
    assert packet["automatic_cleanup_allowed"] is False
    assert packet["execution_authorized"] is False

    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "portfolio-continuity-attention-readiness.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator_class(schema).validate(packet)


def test_trial_eligibility_only_opens_separate_session_summary_approval_gate() -> None:
    packet = build_progressive_attention_readiness(
        _projection(),
        activation_state={
            "status": "eligible_for_human_activation",
            "gate_failures": [],
        },
    )

    stages = {row["stage_id"]: row for row in packet["stages"]}
    assert stages["session_start_summary"]["status"] == "separate_human_approval_required"
    assert stages["weekly_changed_only_digest"]["status"] == "blocked_by_session_summary_activation"
    assert stages["breakpoint_prompts"]["status"] == "blocked_by_weekly_digest_activation"
    assert packet["execution_authorized"] is False


def test_weekly_preview_suppresses_unchanged_fingerprints() -> None:
    first = build_progressive_attention_readiness(_projection())
    fingerprints = [row["fingerprint"] for row in first["weekly_digest_preview"]["asks"]]

    second = build_progressive_attention_readiness(
        _projection(), previous_weekly_fingerprints=fingerprints
    )
    third = build_progressive_attention_readiness(
        _projection(),
        previous_weekly_fingerprints=second["weekly_seen_fingerprints"],
    )

    assert first["weekly_digest_preview"]["asks"]
    assert second["weekly_digest_preview"]["asks"] == []
    assert third["weekly_digest_preview"]["asks"] == []
    assert second["weekly_seen_fingerprints"] == fingerprints
