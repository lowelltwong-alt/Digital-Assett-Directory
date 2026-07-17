from __future__ import annotations

from pathlib import Path

import pytest

from digital_asset_directory.portfolio_roadmap import (
    RoadmapIntegrityError,
    fold_roadmap,
    read_roadmap_events,
    record_roadmap_item,
    transition_roadmap_item,
)
from digital_asset_directory.transport import init_data_root


def _private_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hub = tmp_path / "hub"
    data = tmp_path / "data"
    hub.mkdir()
    init_data_root(data, hub_root=hub, force_onedrive=True)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data))
    return hub


def test_roadmap_requires_private_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DAD_DATA_ROOT", str(tmp_path / "missing"))
    with pytest.raises(RoadmapIntegrityError, match="initialized DAD_DATA_ROOT"):
        record_roadmap_item(
            hub,
            plan_id="plan:one",
            title="Build recovery",
            outcome="Recover ref-only work",
            acceptance_criteria=["Ref-only fixture is found"],
        )


def test_roadmap_capture_is_idempotent_private_and_non_authorizing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)
    first = record_roadmap_item(
        hub,
        plan_id="plan:one",
        title="Build from C:\\Users\\lowel\\private\\repo",
        outcome="Never keep token sk-12345678901234567890",
        acceptance_criteria=["Ref-only fixture is found"],
        request_id="roadmap-request:one",
    )
    retry = record_roadmap_item(
        hub,
        plan_id="plan:one",
        title="Build from C:\\Users\\lowel\\private\\repo",
        outcome="Never keep token sk-12345678901234567890",
        acceptance_criteria=["Ref-only fixture is found"],
        request_id="roadmap-request:one",
    )
    assert retry["event_id"] == first["event_id"]
    assert first["candidate_only"] is True
    assert first["execution_authorized"] is False
    persisted = str(read_roadmap_events(hub))
    assert "C:\\Users" not in persisted
    assert "sk-12345678901234567890" not in persisted


def test_roadmap_transition_requires_human_gate_and_acceptance_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)
    item = record_roadmap_item(
        hub,
        plan_id="plan:one",
        title="Manual workflow",
        outcome="Capture through archive assessment",
        acceptance_criteria=["Workflow integration test passes"],
    )
    with pytest.raises(ValueError, match="human approval"):
        transition_roadmap_item(hub, item_id=item["item_id"], status="ready", human_approval_ref="")
    with pytest.raises(ValueError, match="Accepted roadmap items"):
        transition_roadmap_item(
            hub,
            item_id=item["item_id"],
            status="accepted",
            human_approval_ref="human:lowell",
        )

    accepted = transition_roadmap_item(
        hub,
        item_id=item["item_id"],
        status="accepted",
        human_approval_ref="human:lowell",
        acceptance_evidence=["pytest:test_manual_workflow"],
        independent_check_ref="check:independent",
        producer_ref="agent:builder",
        independent_checker_ref="agent:checker",
    )
    assert accepted["payload"]["status"] == "accepted"
    projection = fold_roadmap(read_roadmap_events(hub), plan_id="plan:one")
    assert projection["accepted_count"] == 1
    assert projection["remaining_count"] == 0


def test_closed_task_or_clean_git_cannot_accept_roadmap_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)
    item = record_roadmap_item(
        hub,
        plan_id="plan:one",
        title="Close worktree",
        outcome="Preserve unique value before cleanup",
        acceptance_criteria=["Independent preservation check passes"],
    )
    with pytest.raises(ValueError, match="Accepted roadmap items"):
        transition_roadmap_item(
            hub,
            item_id=item["item_id"],
            status="accepted",
            human_approval_ref="human:lowell",
            acceptance_evidence=["task:closed", "git:clean"],
            independent_check_ref="",
            producer_ref="agent:builder",
            independent_checker_ref="agent:checker",
        )


def test_accepted_and_superseded_roadmap_items_cannot_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)
    item = record_roadmap_item(
        hub,
        plan_id="plan:one",
        title="Terminal item",
        outcome="Stay terminal",
        acceptance_criteria=["Independent evidence"],
    )
    transition_roadmap_item(
        hub,
        item_id=item["item_id"],
        status="accepted",
        human_approval_ref="human:lowell",
        acceptance_evidence=["test:passed"],
        independent_check_ref="check:one",
        producer_ref="agent:builder",
        independent_checker_ref="agent:checker",
    )
    with pytest.raises(ValueError, match="Illegal roadmap status transition"):
        transition_roadmap_item(
            hub,
            item_id=item["item_id"],
            status="active",
            human_approval_ref="human:lowell",
        )
    transition_roadmap_item(
        hub,
        item_id=item["item_id"],
        status="superseded",
        human_approval_ref="human:lowell",
    )
    with pytest.raises(ValueError, match="Illegal roadmap status transition"):
        transition_roadmap_item(
            hub,
            item_id=item["item_id"],
            status="ready",
            human_approval_ref="human:lowell",
        )


def test_conflicting_request_id_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _private_hub(tmp_path, monkeypatch)
    record_roadmap_item(
        hub,
        plan_id="plan:one",
        title="One",
        outcome="One",
        acceptance_criteria=["One"],
        request_id="same",
    )
    with pytest.raises(RoadmapIntegrityError, match="different roadmap content"):
        record_roadmap_item(
            hub,
            plan_id="plan:one",
            title="Two",
            outcome="Two",
            acceptance_criteria=["Two"],
            request_id="same",
        )
