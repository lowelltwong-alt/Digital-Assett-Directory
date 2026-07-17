from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for

from digital_asset_directory.portfolio_continuity_projection import (
    build_continuity_projection,
    fold_continuity_activity,
)
from digital_asset_directory.portfolio_continuity_workflow import assess_closeout


def _inventory() -> dict:
    return {
        "repository_id": "repo:one",
        "generated_at": "2026-07-17T00:00:00Z",
        "inventory_fingerprint": "sha256:" + "1" * 64,
        "objects": [
            {
                "object_id": "a" * 40,
                "ref_ids": ["ref:main"],
                "committed_at": "2026-07-16T00:00:00Z",
            }
        ],
        "worktrees": [
            {
                "worktree_id": "worktree:one",
                "head_id": "a" * 40,
                "dirty": False,
                "changes": {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0},
                "overlay_fingerprint": "sha256:" + "2" * 64,
            }
        ],
        "codex_items": [
            {
                "codex_item_id": "task:one",
                "state": "closed",
                "updated_at": "2026-07-17T00:00:00Z",
                "metadata_fingerprint": "sha256:" + "3" * 64,
            }
        ],
        "coverage": {"gaps": [], "network_calls": 0, "git_writes": 0},
    }


def _plan(index: int = 0, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "plan_id": f"plan:{index}",
        "revision_id": f"revision:{index}",
        "lifecycle": "decision_complete",
        "implementation_state": "partial",
        "recorded_at": "2026-07-17T00:00:00Z",
        "smallest_next_action": f"next {index}",
        "acceptance_evidence": ["expected test"],
        "workstream_refs": [f"ws:{index}"],
        "entity_refs": [],
    }
    row.update(updates)
    return row


def _workstream(index: int = 0, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "workstream_id": f"ws:{index}",
        "lifecycle_state": "active",
        "state_since": "2026-07-17T00:00:00Z",
        "last_activity_at": "2026-07-17T00:00:00Z",
        "next_action": f"next {index}",
        "bindings": [],
        "capsule": {},
    }
    row.update(updates)
    return row


def _event(kind: str, observed_at: str, *, session_id: str = "") -> dict:
    return {
        "event_id": f"event:{kind}:{observed_at}",
        "event_kind": kind,
        "stream_id": "plan:0",
        "observed_at": observed_at,
        "payload": {
            "plan_id": "plan:0",
            "session_id": session_id,
            "last_material_activity_at": observed_at,
        },
    }


def test_activity_duration_uses_only_explicit_paired_sessions() -> None:
    activity = fold_continuity_activity(
        [
            _event("session_started", "2026-07-17T00:00:00Z", session_id="session:one"),
            _event("interruption_observed", "2026-07-17T00:10:00Z"),
            _event("session_stopped", "2026-07-17T00:30:00Z", session_id="session:one"),
            _event("session_started", "2026-07-17T01:00:00Z", session_id="unpaired"),
        ]
    )["plan:0"]
    assert activity["session_count"] == 2
    assert activity["completed_session_count"] == 1
    assert activity["engaged_duration_seconds"] == 1800
    assert activity["duration_coverage"] == "explicit_paired_sessions_only"
    assert activity["interruption_count"] == 1


def test_projection_is_rebuildable_has_global_repo_graph_and_all_queues() -> None:
    plans = [_plan(index) for index in range(5)]
    plans[0]["source_bindings"] = ["ref:main"]
    workstreams = [_workstream(index) for index in range(5)]
    workstreams[0]["bindings"] = [
        {
            "binding_id": "binding:one",
            "binding_kind": "worktree",
            "assertion_status": "accepted",
            "ref": "ref:main",
        }
    ]
    plans[0]["smallest_next_action"] = ""
    workstreams[0]["next_action"] = ""
    workstreams[0]["lifecycle_state"] = "paused"
    search = {
        "query_digest": "sha256:" + "4" * 64,
        "classification": "ambiguous_no_winner",
        "primary_candidate_id": "",
        "candidates": [{"candidate_id": "candidate:a"}, {"candidate_id": "candidate:b"}],
    }
    closeout = assess_closeout(
        plan=dict(_plan(0)),
        workstream=dict(workstreams[0]),
        recovery_bundle={
            "snapshot_current": True,
            "classification": "contained_in_main",
            "completion_supported": False,
        },
        task_observation={"task_id": "task:one", "observed_at": "2026-07-17T00:00:00Z"},
        preserved_handoff_ref="handoff:one",
        branch_pr_disposition_ref="pr:one",
    )
    kwargs = {
        "inventories": [_inventory()],
        "plan_index": {"plans": plans},
        "roadmap": {"items": []},
        "workstream_state": {"workstreams": workstreams},
        "entity_state": {"entities": []},
        "continuity_events": [_event("interruption_observed", "2026-07-17T00:10:00Z")],
        "search_results": [search],
        "closeout_assessments": [closeout],
    }
    first = build_continuity_projection(**kwargs)
    second = build_continuity_projection(**kwargs)

    assert first["projection_fingerprint"] == second["projection_fingerprint"]
    assert len(first["repositories"]) == 1
    assert "plan:0" in first["repositories"][0]["node_ids"]
    assert any(
        edge["source"] == "plan:0"
        and edge["relation"] == "bound_to"
        and edge["target"] == "ref:main"
        for edge in first["graph"]["edges"]
    )
    assert any(
        edge["source"] == "ws:0"
        and edge["relation"] == "bound_to"
        and edge["target"] == "ref:main"
        for edge in first["graph"]["edges"]
    )
    assert {row["node_kind"] for row in first["graph"]["nodes"]} >= {
        "repository",
        "commit",
        "ref",
        "worktree",
        "codex_task",
        "plan_revision",
        "workstream",
    }
    assert set(first["queues"]) == {
        "current_state",
        "interrupted_resume",
        "possible_duplicates",
        "next_actions",
        "next_actions_overflow",
        "task_archive",
        "worktree_close",
    }
    assert len(first["queues"]["next_actions"]) == 3
    assert len(first["queues"]["next_actions_overflow"]) == 1
    assert first["queues"]["possible_duplicates"][0]["primary_candidate_id"] == ""
    assert first["queues"]["task_archive"][0]["ready_for_human_decision"] is False
    assert first["queues"]["worktree_close"][0]["ready_for_human_decision"] is False
    cockpit = first["repositories"][0]["cockpit"]
    assert cockpit["current_state"][0]["plan_id"] == "plan:0"
    assert cockpit["queue_counts"]["possible_duplicates"] == 0
    assert cockpit["queue_counts"]["task_archive"] == 1
    assert cockpit["closeout_summary"]["task_blocked"] == 1
    assert cockpit["candidate_only"] is True
    assert cockpit["execution_authorized"] is False

    schema = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "portfolio-continuity-projection.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator_class(schema).validate(first)


def test_projection_fingerprint_ignores_inventory_observation_time() -> None:
    first_inventory = _inventory()
    second_inventory = _inventory()
    second_inventory["generated_at"] = "2026-07-17T00:01:00Z"

    first = build_continuity_projection(inventories=[first_inventory])
    second = build_continuity_projection(inventories=[second_inventory])

    assert first["projection_fingerprint"] == second["projection_fingerprint"]


def test_missing_source_health_prevents_false_complete_coverage() -> None:
    inventory = _inventory()
    inventory["coverage"]["gaps"] = ["worktree_status_unavailable"]
    projection = build_continuity_projection(inventories=[inventory])
    assert projection["coverage"]["status"] == "partial"
    assert projection["coverage"]["gaps"] == ["repo:one:worktree_status_unavailable"]


def test_external_private_root_gap_prevents_false_complete_coverage() -> None:
    projection = build_continuity_projection(
        inventories=[_inventory()],
        external_coverage_gaps=["private_data_root_unavailable_for_current_hub"],
    )
    assert projection["coverage"]["status"] == "partial"
    assert projection["coverage"]["gaps"] == [
        "private_data_root_unavailable_for_current_hub"
    ]
    assert projection["repositories"][0]["cockpit"]["coverage"] == {
        "status": "partial",
        "gaps": ["private_data_root_unavailable_for_current_hub"],
    }


def test_quiet_work_is_not_added_to_resume_or_next_action_queues() -> None:
    projection = build_continuity_projection(
        plan_index={"plans": [_plan(0)]},
        workstream_state={"workstreams": [_workstream(0, lifecycle_state="snoozed")]},
        continuity_events=[_event("interruption_observed", "2026-07-17T00:10:00Z")],
    )
    assert projection["queues"]["interrupted_resume"] == []
    assert projection["queues"]["next_actions"] == []


def test_unresolved_roadmap_references_are_gaps_not_dangling_edges() -> None:
    projection = build_continuity_projection(
        roadmap={
            "items": [
                {
                    "item_id": "roadmap:one",
                    "plan_id": "plan:missing",
                    "status": "proposed",
                    "recorded_at": "2026-07-17T00:00:00Z",
                    "last_event_id": "event:one",
                    "dependency_item_ids": ["roadmap:missing"],
                }
            ]
        }
    )
    node_ids = {node["node_id"] for node in projection["graph"]["nodes"]}
    assert all(
        edge["source"] in node_ids and edge["target"] in node_ids
        for edge in projection["graph"]["edges"]
    )
    assert projection["coverage"]["status"] == "partial"
    assert projection["coverage"]["gaps"] == [
        "roadmap_dependency_reference_unresolved",
        "roadmap_plan_reference_unresolved",
    ]


def test_forward_workstream_binding_resolves_after_node_prepass() -> None:
    workstreams = [
        _workstream(
            0,
            workstream_id="ws:a",
            bindings=[
                {
                    "binding_id": "binding:a-b",
                    "assertion_status": "accepted",
                    "ref": "ws:b",
                }
            ],
        ),
        _workstream(1, workstream_id="ws:b"),
    ]
    projection = build_continuity_projection(
        workstream_state={"workstreams": workstreams}
    )
    assert any(
        edge["source"] == "ws:a"
        and edge["relation"] == "bound_to"
        and edge["target"] == "ws:b"
        for edge in projection["graph"]["edges"]
    )
    assert "accepted_binding_target_unresolved" not in projection["coverage"]["gaps"]
