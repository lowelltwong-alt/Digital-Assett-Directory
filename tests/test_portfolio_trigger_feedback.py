from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from digital_asset_directory.portfolio_workstreams import (
    build_trigger_feedback_projection,
    capture_ideas,
    load_state,
    record_feedback,
    write_trigger_feedback_projection,
)


ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    for relative in (
        "registry/schema-registry.json",
        "schemas/portfolio-workstream-event.schema.json",
        "schemas/portfolio-trigger-feedback.schema.json",
    ):
        target = hub / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return hub


def test_trigger_feedback_projection_is_categorical_private_and_exact(tmp_path: Path):
    hub = _hub(tmp_path)
    captured = capture_ideas(
        hub,
        ["Build a humane dependency-aware project portfolio"],
        conversation_id="trigger-feedback-test",
        now=T0,
    )
    workstream_id = captured["proposals"][0]["workstream_id"]
    state = load_state(hub, now=T0 + timedelta(days=8))
    trigger_signature = next(
        row["trigger_signature"]
        for row in state["today"]
        if row["workstream_id"] == workstream_id
    )

    record_feedback(
        hub,
        workstream_id,
        "dismiss",
        note="private reason must not appear",
        trigger_signature=trigger_signature,
        now=T0 + timedelta(days=8, hours=1),
    )
    record_feedback(
        hub,
        workstream_id,
        "keep",
        trigger_signature=trigger_signature,
        now=T0 + timedelta(days=8, hours=2),
    )
    record_feedback(
        hub,
        workstream_id,
        "pause",
        now=T0 + timedelta(days=8, hours=3),
    )
    record_feedback(
        hub,
        workstream_id,
        "dismiss",
        trigger_signature="not-a-generated-signature private marker",
        now=T0 + timedelta(days=8, hours=4),
    )

    projection = build_trigger_feedback_projection(hub, now=T0 + timedelta(days=9))

    assert projection["coverage"] == {
        "feedback_event_count": 4,
        "valid_signature_event_count": 2,
        "unsigned_event_count": 1,
        "invalid_signature_event_count": 1,
        "ledger_diagnostic_count": 0,
    }
    assert projection["signature_count"] == 1
    row = projection["signatures"][0]
    assert row["trigger_signature"] == trigger_signature
    assert row["action_counts"] == {"dismiss": 1, "keep": 1}
    assert row["feedback_class_counts"] == {
        "accepted": 1,
        "suppressed": 1,
        "rejected": 0,
    }
    rendered = json.dumps(projection)
    assert "private reason" not in rendered
    assert "private marker" not in rendered
    assert "score" not in row


def test_trigger_feedback_write_is_explicit_and_deterministic(tmp_path: Path):
    hub = _hub(tmp_path)
    projection = build_trigger_feedback_projection(hub, now=T0)
    assert not (hub / "processed/reports/portfolio_os/trigger_feedback.json").exists()

    path = write_trigger_feedback_projection(hub, projection)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == projection
