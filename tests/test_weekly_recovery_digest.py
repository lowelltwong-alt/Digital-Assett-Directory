from pathlib import Path

import pytest

from digital_asset_directory.portfolio_weekly_digest import build_weekly_digest, metadata_safe_toast, write_weekly_digest
from digital_asset_directory.transport import init_data_root


def test_digest_reuses_today_queue_caps_asks_and_uses_zero_tokens() -> None:
    index = {
        "plans": [
            {"plan_id": f"p{i}", "lifecycle": "decision_complete", "implementation_state": "partial"}
            for i in range(7)
        ]
    }
    today = [
        {"decision_key": f"d{i}", "title": f"Decision {i}", "source_fingerprint": f"f{i}"}
        for i in range(7)
    ]
    digest = build_weekly_digest(index, today_items=today)
    assert digest["inventory"]["unfinished_plan_count"] == 7
    assert len(digest["asks"]) == 3
    assert {row["source"] for row in digest["asks"]} == {"existing_today_queue"}
    assert digest["model_calls"] == digest["model_tokens"] == 0
    assert digest["delivery"]["windows_toast_status"] == "not_activated"


def test_unchanged_snoozed_and_quiet_items_do_not_repeat() -> None:
    index = {"plans": []}
    first = build_weekly_digest(index, today_items=[{"decision_key": "x", "title": "X", "source_fingerprint": "1"}])
    fingerprint = first["asks"][0]["fingerprint"]
    second = build_weekly_digest(
        index,
        today_items=[
            {"decision_key": "x", "title": "X", "source_fingerprint": "1"},
            {"decision_key": "y", "title": "Y", "source_fingerprint": "2", "snoozed": True},
            {"decision_key": "z", "title": "Z", "source_fingerprint": "3", "quiet": True},
        ],
        previous_fingerprints=[fingerprint],
    )
    assert second["asks"] == []


def test_toast_is_metadata_safe_and_not_authorized() -> None:
    packet = metadata_safe_toast(build_weekly_digest({"plans": []}))
    assert packet["contains_names"] is False
    assert packet["contains_paths"] is False
    assert packet["contains_content"] is False
    assert packet["delivery_authorized"] is False


def test_today_queue_content_is_minimized_and_actions_are_allowlisted() -> None:
    digest = build_weekly_digest(
        {"plans": []},
        today_items=[{
            "decision_key": "C:\\Users\\lowel\\private-plan",
            "title": "Inspect C:\\Users\\lowel\\secret\\plan.md token sk-12345678901234567890",
            "source_fingerprint": "raw-source",
            "recommended_action": "execute_everything",
        }],
    )
    serialized = repr(digest)
    assert "C:\\Users" not in serialized
    assert "sk-12345678901234567890" not in serialized
    assert digest["asks"][0]["recommended_action"] == "inspect"
    assert digest["asks"][0]["decision_key"].startswith("decision:")


def test_digest_write_is_local_and_does_not_attempt_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = tmp_path / "hub"
    data = tmp_path / "data"
    hub.mkdir()
    init_data_root(data, hub_root=hub, force_onedrive=True)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data))
    result = write_weekly_digest(hub, build_weekly_digest({"plans": []}))
    assert Path(result["path"]).name == "unfinished-intent-digest.json"
    assert result["delivery_attempted"] is False
