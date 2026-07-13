"""Adversarial invariants for the Portfolio OS attention projections."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random

from digital_asset_directory import portfolio_attention as pa
from digital_asset_directory import portfolio_relations as pr


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _event(kind: str, action: str = "", *, day: int, **payload: object) -> dict[str, object]:
    body = dict(payload)
    if action:
        body["action"] = action
    return {
        "event_id": f"event-{kind}-{action}-{day}",
        "event_kind": kind,
        "recorded_at": (T0 + timedelta(days=day)).isoformat(),
        "payload": body,
    }


def _workstream(
    ws_id: str = "ws-a",
    *,
    state: str = "proposed",
    inactive_days: int = 10,
    dismissals: list[dict[str, str]] | None = None,
    dismissal_epoch: int = 0,
    snooze_until: str = "",
) -> dict[str, object]:
    return {
        "workstream_id": ws_id,
        "idea_text": ws_id,
        "proposal_kind": "new_independent_workstream",
        "lifecycle_state": state,
        "snooze_until": snooze_until,
        "review_at": "",
        "capsule": None,
        "dismissals": dismissals or [],
        "dismissal_epoch": dismissal_epoch,
        "inactive_days": inactive_days,
        "needs_human_decision": False,
        "conflict_resolved": False,
        "relations": [],
        "last_activity_at": T0.isoformat(),
    }


def _focus(ws: dict[str, object], *, now: datetime) -> dict[str, object]:
    return pa.evaluate_triggers(
        ws,
        policy=pa.AttentionPolicy(),
        now=now,
        related_active_labels=[],
        dependency_info=None,
        class_stats={},
        coverage=[],
    )


def test_expired_snooze_resurfaces_immediately() -> None:
    until = (T0 + timedelta(days=3)).isoformat()
    ws = _workstream(state="snoozed", inactive_days=2, snooze_until=until)

    before = _focus(ws, now=T0 + timedelta(days=2))
    after = _focus(ws, now=T0 + timedelta(days=4))

    assert before["priority"] == 0
    assert after["trigger_kind"] == "weekly_decision"
    assert "Snooze expired" in after["reasons"][0]


def test_terminal_capsules_are_projection_noninterfering_for_every_terminal_state() -> None:
    for action, expected in (("merge", "merged"), ("supersede", "superseded"), ("archive", "archived")):
        terminal = _event("focus_feedback", action, day=1)
        capsule = _event(
            "capsule_recorded",
            day=20,
            capsule_id="ghost",
            next_action="ghost action",
            pause_reason="",
            blocker="",
            last_check="",
            snooze_until="",
            incubating=False,
            review_at="",
        )
        diagnostics: list[str] = []
        baseline = pa.fold_lifecycle(T0.isoformat(), [terminal], [])
        folded = pa.fold_lifecycle(T0.isoformat(), [terminal, capsule], diagnostics)

        assert folded["lifecycle_state"] == expected
        assert folded["capsule"] is baseline["capsule"] is None
        assert folded["last_activity_event_at"] == baseline["last_activity_event_at"]
        assert diagnostics == [f"capsule_on_terminal:{capsule['event_id']}"]


def test_keep_resolves_to_active_and_reject_starts_new_dismissal_epoch() -> None:
    events = [
        _event("focus_feedback", "dismiss", day=8, trigger_signature="old"),
        _event("focus_feedback", "dismiss", day=12, trigger_signature="old"),
        _event("focus_feedback", "dismiss", day=16, trigger_signature="old"),
        _event("focus_feedback", "reject_decision", day=17, trigger_signature="decision"),
        _event("focus_feedback", "keep", day=18),
    ]
    folded = pa.fold_lifecycle(T0.isoformat(), events, [])

    assert folded["lifecycle_state"] == "active"
    assert folded["dismissals"] == []
    assert folded["dismissal_epoch"] == 1
    assert folded["decision_rejected_at"] == (T0 + timedelta(days=17)).isoformat()
    assert folded["accept_actions"] == ["keep"]

    ws = _workstream(
        state="active",
        inactive_days=20,
        dismissals=folded["dismissals"],
        dismissal_epoch=folded["dismissal_epoch"],
    )
    assert _focus(ws, now=T0 + timedelta(days=20))["trigger_kind"] == "weekly_decision"


def test_trigger_signatures_are_stable_within_bands_and_change_on_material_input() -> None:
    policy = pa.AttentionPolicy()
    assert pa._idle_band(8, policy) == pa._idle_band(20, policy) == "weekly"

    base = {"dismissal_epoch": 0, "state": "active", "idle_band": "weekly"}
    same = {"state": "active", "idle_band": "weekly", "dismissal_epoch": 0}
    changed_age = {**base, "idle_band": "monthly"}
    changed_epoch = {**base, "dismissal_epoch": 1}

    signature = pa.trigger_signature("ws-a", "weekly_decision", base)
    assert signature == pa.trigger_signature("ws-a", "weekly_decision", same)
    assert signature != pa.trigger_signature("ws-a", "weekly_decision", changed_age)
    assert signature != pa.trigger_signature("ws-a", "weekly_decision", changed_epoch)


def _graph_workstreams(node_count: int, edges: set[tuple[int, int]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for node in range(node_count):
        ws_id = f"ws-{node}"
        result[ws_id] = {
            "lifecycle_state": "active",
            "bindings": [
                {"binding_kind": "blocks", "ref": f"ws-{target}"}
                for source, target in sorted(edges)
                if source == node
            ],
        }
    return result


def _oracle_descendants(node_count: int, edges: set[tuple[int, int]], start: int) -> set[int]:
    adjacency = {node: set() for node in range(node_count)}
    for source, target in edges:
        adjacency[source].add(target)
    seen: set[int] = set()
    stack = list(adjacency[start])
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node])
    return seen


def test_dependency_rollup_matches_reachability_oracle_for_generated_dags() -> None:
    rng = random.Random(71423)
    for _case in range(75):
        node_count = rng.randint(2, 7)
        edges = {
            (source, target)
            for source in range(node_count)
            for target in range(source + 1, node_count)
            if rng.random() < 0.35
        }
        rollup = pa.dependency_rollup(_graph_workstreams(node_count, edges))

        assert rollup["invalid_assertions"] == []
        for node in range(node_count):
            actual = rollup["per_workstream"][f"ws-{node}"]["blocking_count"]
            assert actual == len(_oracle_descendants(node_count, edges, node))


def test_dependency_rollup_surfaces_and_excludes_self_cycles_and_retractions() -> None:
    workstreams = _graph_workstreams(3, {(0, 1), (1, 0), (1, 2)})
    workstreams["ws-2"]["bindings"] = [
        {"binding_kind": "depends_on", "ref": "ws-2"},
        {"binding_kind": "blocks", "ref": "ws-0", "assertion_state": "retracted"},
        {"binding_kind": "blocks", "ref": "ws-0", "assertion_status": "proposed"},
        {"binding_kind": "blocks", "ref": "ws-0", "assertion_status": "rejected"},
    ]

    rollup = pa.dependency_rollup(workstreams)

    assert rollup["cycle_nodes"] == ["ws-0", "ws-1"]
    assert {row["kind"] for row in rollup["invalid_assertions"]} == {
        "self_dependency",
        "dependency_cycle",
    }
    assert rollup["per_workstream"]["ws-0"]["blocked_by"] == []
    assert rollup["per_workstream"]["ws-1"]["blocks_directly"] == ["ws-2"]
    assert rollup["per_workstream"]["ws-2"]["blocked_by"] == ["ws-1"]


def test_intentional_lifecycle_states_and_any_capsule_are_not_sprawl() -> None:
    relation = {
        "relationship_type": "sibling",
        "target_id": "ws-proposed",
    }
    workstreams = {
        "ws-proposed": {
            **_workstream("ws-proposed"),
            "bindings": [],
            "relations": [{**relation, "target_id": "ws-active"}],
        },
        "ws-active": {
            **_workstream("ws-active", state="active"),
            "bindings": [],
            "relations": [relation],
        },
        "ws-incubating": {
            **_workstream("ws-incubating", state="incubating"),
            "bindings": [],
            "relations": [relation],
        },
        "ws-snoozed": {
            **_workstream("ws-snoozed", state="snoozed"),
            "bindings": [],
            "relations": [relation],
        },
        "ws-capsule": {
            **_workstream("ws-capsule"),
            "capsule": {"blocker": "waiting"},
            "bindings": [],
            "relations": [relation],
        },
    }

    clusters = pa.sprawl_clusters(workstreams, policy=pa.AttentionPolicy())
    clustered = {ws_id for cluster in clusters for ws_id in cluster["workstream_ids"]}

    assert clustered == {"ws-proposed", "ws-active"}


def test_exact_two_token_match_is_not_a_duplicate() -> None:
    relations, coverage = pr.classify_relations(
        "source",
        "api auth",
        [
            pr.RelationTarget(
                target_kind="workstream",
                target_id="target",
                target_label="prior",
                text="api auth",
            )
        ],
    )

    assert coverage == []
    assert relations[0]["relationship_type"] == "continuation"
    assert relations[0]["confidence"] == "medium"
