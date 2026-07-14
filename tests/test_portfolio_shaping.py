"""Adversarial tests for candidate-only Portfolio OS workstream shaping."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import unescape
import base64
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from digital_asset_directory import portfolio_cockpit as pc
from digital_asset_directory import portfolio_reconciliation as pr
from digital_asset_directory import portfolio_shaping as ps

NOW = datetime(2026, 7, 13, 12, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
STATES = (
    "proposed",
    "active",
    "paused",
    "snoozed",
    "incubating",
    "merged",
    "superseded",
    "archived",
)


def _project(
    suffix: str = "one",
    *,
    dirty: bool = True,
    conflicted: bool = False,
    reason: str = "dirty_worktree_idle",
) -> tuple[dict[str, object], dict[str, object]]:
    project_id = f"dad:portfolio-project:{suffix}"
    branch = f"feature/{suffix}"
    path = f"C:/private/{suffix}"
    project = {
        "project_id": project_id,
        "name": f"Project {suffix}",
        "common_git_dir": f"{path}/.git",
        "remote_url": "",
        "default_branch": "main",
        "active_within_threshold": True,
        "branches": [
            {
                "name": branch,
                "head": "a" * 40,
                "committed_at": NOW.isoformat(),
                "subject": f"work {suffix}",
                "upstream": "",
                "upstream_gone": False,
                "ahead": 0,
                "behind": 0,
                "project_id": project_id,
                "project_name": f"Project {suffix}",
                "worktree_path": path,
                "dirty": dirty,
                "status_unknown": False,
                "status_error": "",
                "worktree_locked": False,
                "conflicted": conflicted,
                "changed_path_count": 2 if dirty else 0,
                "last_activity_at": NOW.isoformat(),
                "inactive_days": 7,
                "merged": False,
                "prunable_worktree": False,
            }
        ],
        "worktrees": [
            {
                "path": path,
                "branch": branch,
                "head": "a" * 40,
                "detached": False,
                "locked": False,
                "prunable": False,
                "status_known": True,
                "dirty": dirty,
                "change_counts": {
                    "staged": 0,
                    "unstaged": 2 if dirty else 0,
                    "untracked": 0,
                    "conflicted": 1 if conflicted else 0,
                },
                "changed_path_count": 2 if dirty else 0,
                "latest_dirty_activity_at": NOW.isoformat() if dirty else "",
                "status_error": "",
            }
        ],
        "related_projects": [],
    }
    attention = {
        "priority": 100 if conflicted else 90,
        "project_id": project_id,
        "project_name": f"Project {suffix}",
        "branch": branch,
        "worktree_path": path,
        "last_activity_at": NOW.isoformat(),
        "inactive_days": 7,
        "reasons": [reason],
        "next_action": "Review exact evidence.",
        "evidence": {
            "dirty": dirty,
            "changed_path_count": 2 if dirty else 0,
            "ahead": 0,
            "behind": 0,
            "merged_by_ancestry": False,
            "upstream": "",
            "worktree_locked": False,
        },
    }
    return project, attention


def _git(items: list[tuple[dict[str, object], dict[str, object]]]) -> dict[str, object]:
    projects = [row[0] for row in items]
    attention = [row[1] for row in items]
    return {
        "schema_version": "dad.portfolio_attention.v1",
        "generated_at": NOW.isoformat(),
        "status": "generated_candidate",
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "scan": {
            "roots": [],
            "stale_days": 3,
            "max_depth": 5,
            "related_limit": 3,
            "discovered_checkout_count": len(projects),
            "errors": [],
        },
        "summary": {
            "project_count": len(projects),
            "branch_count": len(projects),
            "worktree_count": len(projects),
            "dirty_worktree_count": sum(bool(row[0]["worktrees"][0]["dirty"]) for row in items),
            "attention_item_count": len(attention),
            "today_item_count": min(3, len(attention)),
        },
        "today": attention[:3],
        "projects": projects,
        "attention_queue": attention,
        "authority_boundary": "Read-only candidate evidence.",
    }


def _workstream(
    workstream_id: str,
    label: str,
    *,
    bindings: list[tuple[str, str, str]] = (),
    lifecycle: str = "active",
) -> tuple[dict[str, object], dict[str, object]]:
    normalized = [
        {
            "binding_id": f"binding:{workstream_id}:{index}",
            "binding_kind": kind,
            "ref": ref,
            "label": "",
            "assertion_status": status,
            "asserted_by": "test",
            "approval_ref": "",
            "recorded_at": NOW.isoformat(),
        }
        for index, (kind, ref, status) in enumerate(bindings)
    ]
    row = {
        "workstream_id": workstream_id,
        "idea_id": f"idea:{workstream_id}",
        "idea_text": label,
        "proposal_kind": "new_independent_workstream",
        "recommended_action": "review",
        "needs_human_decision": False,
        "divergence": False,
        "relations": [],
        "proposed_at": NOW.isoformat(),
        "lifecycle_state": lifecycle,
        "state_since": NOW.isoformat(),
        "snooze_until": "",
        "review_at": "",
        "capsule": None,
        "dismissal_epoch": 0,
        "decision_rejected_at": "",
        "conflict_resolved": False,
        "bindings": normalized,
        "dismiss_count": 0,
        "last_activity_at": NOW.isoformat(),
        "inactive_days": 7,
    }
    focus = {
        "workstream_id": workstream_id,
        "idea_text": label,
        "proposal_kind": "new_independent_workstream",
        "lifecycle_state": lifecycle,
        "priority": 80,
        "trigger_kind": "weekly_decision",
        "trigger_signature": f"sig:{workstream_id}",
        "tier": "weekly",
        "inactive_days": 7,
        "reasons": ["weekly_review"],
        "suppressed_reasons": [],
        "next_action": "Review.",
        "last_activity_at": NOW.isoformat(),
    }
    return row, focus


def _state(pairs: list[tuple[dict[str, object], dict[str, object]]]) -> dict[str, object]:
    workstreams = [pair[0] for pair in pairs]
    focus = [pair[1] for pair in pairs]
    board = {state: [] for state in STATES}
    for row in workstreams:
        board[str(row["lifecycle_state"])].append(
            {"workstream_id": row["workstream_id"], "idea_text": row["idea_text"]}
        )
    return {
        "schema_version": "dad.portfolio_workstreams.v1",
        "generated_at": NOW.isoformat(),
        "status": "generated_candidate",
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "authority_boundary": "Local candidate projection.",
        "summary": {
            "project_count": 0,
            "idea_count": len(workstreams),
            "conversation_count": 0,
            "workstream_count": len(workstreams),
            "open_workstream_count": len(workstreams),
            "relation_count": 0,
            "focus_item_count": len(focus),
            "today_item_count": min(3, len(focus)),
            "suppressed_workstream_count": 0,
            "bottleneck_count": 0,
            "sprawl_cluster_count": 0,
        },
        "conversations": [],
        "projects": [],
        "ideas": [],
        "workstreams": workstreams,
        "today": focus[:3],
        "focus_queue": focus,
        "coverage": [],
        "ledger_diagnostics": {
            "corrupt_line_count": 0,
            "invalid_envelope_count": 0,
            "torn_tail_pending": False,
            "problems": [],
            "fold_problems": [],
        },
        "dependencies": {
            "per_workstream": {},
            "bottlenecks": [],
            "invalid_assertions": [],
            "cycle_nodes": [],
        },
        "board": board,
        "sprawl_clusters": [],
        "relationship_class_stats": {},
        "portfolio_snapshot": {"status": "unavailable", "as_of": "", "source_hash": ""},
    }


def _triple(
    projects: list[tuple[dict[str, object], dict[str, object]]],
    pairs: list[tuple[dict[str, object], dict[str, object]]],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    state = _state(pairs)
    cockpit = pc.build_portfolio_cockpit(_git(projects), state, now=NOW, schema_root=ROOT)
    reconciliation = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    return state, cockpit, reconciliation


def _shape(triple, *, now: datetime = NOW, limit: int = 250):
    return ps.build_portfolio_shaping(
        *triple, now=now, settings=ps.ShapingSettings(case_limit=limit), schema_root=ROOT
    )


def _decisions_for(
    shaping: dict[str, object],
    *,
    choice_kind: str | None = None,
    status: str = "active",
    review_after: str = "",
    result_status: str = "",
    revision_id: str | None = None,
    snapshot_digest: str | None = None,
) -> dict[str, object]:
    case = shaping["cases"][0]
    choice = next(
        (
            row
            for row in case["choices"]
            if choice_kind is None or row["choice_kind"] == choice_kind
        ),
        case["choices"][0],
    )
    decision_id = "dad:decision:test"
    projection: dict[str, object] = {
        "schema_version": "dad.portfolio_recovery_projection.v1",
        "status": "ready",
        "execution_authorized": False,
        "mutations_performed": False,
        "source_authority_mutated": False,
        "decisions": [
            {
                "decision_id": decision_id,
                "case_id": case["case_id"],
                "case_revision_id": revision_id or case["revision_id"],
                "source_snapshot_digest": snapshot_digest
                or shaping["source_snapshot_digest"],
                "expected_preconditions_digest": ps._case_preconditions_digest(case),
                "choice_id": choice["choice_id"],
                "choice_kind": choice["choice_kind"],
                "status": status,
                "disposition": "defer" if choice["choice_kind"] == "defer" else "review",
                "review_after": review_after,
            }
        ],
        "results": [],
    }
    if result_status:
        projection["results"] = [
            {
                "result_id": "dad:recovery-result:test",
                "decision_id": decision_id,
                "packet_id": "dad:recovery-packet:test",
                "status": result_status,
                "result_status": result_status,
            }
        ]
    return projection


def _validate(value: dict[str, object]) -> None:
    schema = json.loads(
        (ROOT / "schemas" / "portfolio-workstream-shaping.schema.json").read_text(encoding="utf-8")
    )
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema, format_checker=FormatChecker()).validate(value)
    assert ps.portfolio_shaping_semantic_problems(value) == []


def _resource_ids(project: dict[str, object]) -> tuple[str, str]:
    return (
        pc.branch_resource_id(str(project["project_id"]), str(project["branches"][0]["name"])),
        pc.worktree_resource_id(str(project["project_id"]), str(project["worktrees"][0]["path"])),
    )


def test_missing_or_hash_mismatched_sources_block_without_cases() -> None:
    missing = ps.build_portfolio_shaping(None, None, None, now=NOW, schema_root=ROOT)
    _validate(missing)
    assert missing["status"] == "blocked_candidate"
    assert missing["cases"] == []
    assert missing["summary"]["shaping_complete"] is False

    triple = list(_triple([], []))
    triple[1] = deepcopy(triple[1])
    triple[1]["source_refs"]["workstreams"] = "sha256:" + "0" * 64
    mismatch = _shape(tuple(triple))
    _validate(mismatch)
    assert mismatch["status"] == "blocked_candidate"
    assert mismatch["cases"] == []
    assert any(row["kind"] == "workstream_cockpit_hash_mismatch" for row in mismatch["blockers"])


def test_empty_portfolio_never_claims_organization() -> None:
    result = _shape(_triple([], []))
    _validate(result)
    assert result["summary"]["no_cases_generated"] is True
    assert result["summary"]["intake_needed"] is True
    assert result["summary"]["shaping_complete"] is False


def test_v2_decision_projection_is_snapshot_bound_pending_and_retractable() -> None:
    triple = _triple([_project("decision-pending")], [])
    base = _shape(triple)
    decisions = _decisions_for(base)
    pending = ps.build_portfolio_shaping(
        *triple, decisions=decisions, now=NOW, schema_root=ROOT
    )
    _validate(pending)
    annotation = pending["cases"][0]["decision"]
    assert pending["schema_version"] == "dad.portfolio_workstream_shaping.v2"
    assert annotation["state"] == "active"
    assert annotation["manual_action_state"] == "pending"
    assert pending["decision_projection"]["pending_manual_action_count"] == 1
    assert pending["review_queue"] == []
    assert pending["execution_authorized"] is False

    retracted_input = deepcopy(decisions)
    retracted_input["decisions"][0]["status"] = "retracted"
    retracted = ps.build_portfolio_shaping(
        *triple, decisions=retracted_input, now=NOW, schema_root=ROOT
    )
    _validate(retracted)
    assert retracted["cases"][0]["decision"]["state"] == "retracted"
    assert retracted["cases"][0]["decision"]["manual_action_state"] == "none"
    assert len(retracted["review_queue"]) == 1


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"revision_id": "dad:revision:stale"}, "stale"),
        ({"snapshot_digest": "sha256:" + "0" * 64}, "stale"),
    ],
)
def test_decision_binding_mismatch_is_stale(override: dict[str, str], expected: str) -> None:
    triple = _triple([_project("decision-stale")], [])
    base = _shape(triple)
    decisions = _decisions_for(base, **override)
    result = ps.build_portfolio_shaping(
        *triple, decisions=decisions, now=NOW, schema_root=ROOT
    )
    _validate(result)
    assert result["cases"][0]["decision"]["state"] == expected
    assert result["decision_projection"]["stale_count"] == 1
    assert result["review_queue"] == []


def test_decision_projection_minimizes_private_extra_fields() -> None:
    triple = _triple([_project("decision-private")], [])
    base = _shape(triple)
    decisions = _decisions_for(base)
    decisions["decisions"][0]["private_note"] = "PRIVATE CLIENT ALPHA C:/private/matter"
    decisions["results"] = []
    result = ps.build_portfolio_shaping(
        *triple, decisions=decisions, now=NOW, schema_root=ROOT
    )
    _validate(result)
    serialized = json.dumps(result)
    html = ps.portfolio_shaping_html(result)
    assert "PRIVATE CLIENT ALPHA" not in serialized + html
    assert "C:/private/matter" not in serialized + html
    assert "private_note" not in serialized


def test_blocked_recovery_projection_is_not_applied() -> None:
    triple = _triple([_project("decision-blocked")], [])
    base = _shape(triple)
    decisions = _decisions_for(base)
    decisions["status"] = "blocked"
    decisions["diagnostics"] = ["PRIVATE CLIENT C:/private/evidence"]
    result = ps.build_portfolio_shaping(
        *triple, decisions=decisions, now=NOW, schema_root=ROOT
    )
    _validate(result)
    assert result["decision_projection"]["source_status"] == "invalid"
    assert result["cases"][0]["decision"] == ps._empty_decision_annotation()
    assert any(row["kind"] == "decision_projection_invalid" for row in result["blockers"])
    assert "PRIVATE CLIENT" not in json.dumps(result)


def test_retracted_history_does_not_hide_current_case_decision() -> None:
    triple = _triple([_project("decision-history")], [])
    base = _shape(triple)
    decisions = _decisions_for(base)
    current = deepcopy(decisions["decisions"][0])
    current["decision_id"] = "dad:decision:current"
    historical = deepcopy(decisions["decisions"][0])
    historical["decision_id"] = "dad:decision:historical"
    historical["status"] = "retracted"
    decisions["decisions"] = [historical, current]
    result = ps.build_portfolio_shaping(
        *triple, decisions=decisions, now=NOW, schema_root=ROOT
    )
    _validate(result)
    assert result["cases"][0]["decision"]["decision_id"] == "dad:decision:current"
    assert result["decision_projection"]["active_count"] == 1
    assert result["decision_projection"]["historical_decision_count"] == 1


def test_shared_exact_resource_is_one_symmetric_pd0_without_winner() -> None:
    project_item = _project()
    branch_id, _ = _resource_ids(project_item[0])
    pairs = [
        _workstream("ws-a", "alpha portfolio scope", bindings=[("branch", branch_id, "accepted")]),
        _workstream("ws-b", "beta portfolio scope", bindings=[("branch", branch_id, "accepted")]),
    ]
    result = _shape(_triple([project_item], pairs))
    rows = [
        row
        for row in result["cases"]
        if row["evidence_tier"] == "PD0_shared_exact_specific_resource"
    ]
    _validate(result)
    assert len(rows) == 1
    assert rows[0]["subject_workstream_ids"] == ["ws-a", "ws-b"]
    assert "recommended_choice_id" not in json.dumps(rows[0])
    assert all(choice["execution_available"] is False for choice in rows[0]["choices"])


def test_reciprocal_pair_split_between_workstreams_is_pd1() -> None:
    project_item = _project()
    branch_id, worktree_id = _resource_ids(project_item[0])
    pairs = [
        _workstream("ws-a", "alpha scope", bindings=[("branch", branch_id, "accepted")]),
        _workstream("ws-b", "beta scope", bindings=[("worktree", worktree_id, "accepted")]),
    ]
    result = _shape(_triple([project_item], pairs))
    _validate(result)
    rows = [
        row
        for row in result["cases"]
        if row["evidence_tier"] == "PD1_reciprocal_exact_pair_split_between_workstreams"
    ]
    assert len(rows) == 1
    assert rows[0]["subject_resource_ids"] == sorted([branch_id, worktree_id])


def test_similarity_only_is_inspect_only_and_same_age_alone_is_silent() -> None:
    labels = [
        _workstream("ws-a", "portfolio workstream shaping recovery duplicate boundary"),
        _workstream("ws-b", "portfolio workstream shaping recovery duplicate boundary"),
    ]
    result = _shape(_triple([], labels))
    _validate(result)
    rows = [row for row in result["cases"] if row["evidence_tier"] == "PD2_similarity_only"]
    assert len(rows) == 1
    assert rows[0]["disposition"] == "inspect_only"
    assert rows[0]["subject_resource_ids"] == []
    assert all(
        value.startswith("sha256:") for value in rows[0]["evidence_summary"]["shared_token_hashes"]
    )

    different = _shape(
        _triple(
            [],
            [
                _workstream("ws-a", "database migration"),
                _workstream("ws-b", "illustration color study"),
            ],
        )
    )
    _validate(different)
    assert not any(row["case_kind"] == "possible_duplicate" for row in different["cases"])


def test_two_disconnected_exact_projects_produce_split_but_one_pair_does_not() -> None:
    first, second = _project("one"), _project("two")
    first_branch, _ = _resource_ids(first[0])
    second_branch, _ = _resource_ids(second[0])
    split = _shape(
        _triple(
            [first, second],
            [
                _workstream(
                    "ws",
                    "cross project program",
                    bindings=[
                        ("branch", first_branch, "accepted"),
                        ("branch", second_branch, "accepted"),
                    ],
                )
            ],
        )
    )
    _validate(split)
    rows = [
        row
        for row in split["cases"]
        if row["evidence_tier"] == "SP0_disconnected_exact_owned_components"
    ]
    assert len(rows) == 1
    assert rows[0]["evidence_summary"]["exact_component_count"] == 2

    branch_id, worktree_id = _resource_ids(first[0])
    one_pair = _shape(
        _triple(
            [first],
            [
                _workstream(
                    "ws",
                    "single exact pair",
                    bindings=[
                        ("branch", branch_id, "accepted"),
                        ("worktree", worktree_id, "accepted"),
                    ],
                )
            ],
        )
    )
    _validate(one_pair)
    assert not any(row["case_kind"] == "split" for row in one_pair["cases"])


def test_repo_context_is_inspect_only_rescope_and_exact_context_is_review() -> None:
    project_item = _project("context")
    repo_id = str(project_item[0]["project_id"])
    repo_context = _triple(
        [project_item],
        [_workstream("ws", "context owner", bindings=[("repo", repo_id, "accepted")])],
    )
    repo_result = _shape(repo_context)
    _validate(repo_result)
    rows = [row for row in repo_result["cases"] if row["evidence_tier"] == "RS1_repo_context_only"]
    assert len(rows) == 1 and rows[0]["disposition"] == "inspect_only"

    state, cockpit, _ = _triple([project_item], [_workstream("ws", "exact context")])
    cockpit = deepcopy(cockpit)
    cockpit["attention_queue"][0]["workstream_id"] = "ws"
    cockpit["today"][0]["workstream_id"] = "ws"
    reconciliation = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    exact_result = _shape((state, cockpit, reconciliation))
    _validate(exact_result)
    rows = [
        row
        for row in exact_result["cases"]
        if row["evidence_tier"] == "RS0_exact_contextual_unassigned_bundle"
    ]
    assert len(rows) == 1 and rows[0]["disposition"] == "review"


def test_recovery_tiers_are_observed_and_age_never_creates_one() -> None:
    conflicted = _shape(
        _triple([_project("conflict", conflicted=True, reason="conflicted_worktree")], [])
    )
    _validate(conflicted)
    rc0 = next(
        row
        for row in conflicted["cases"]
        if row["evidence_tier"] == "RC0_integrity_unknown_attention"
    )
    assert [choice["choice_kind"] for choice in rc0["choices"]] == ["inspect_evidence", "defer"]

    dirty = _shape(_triple([_project("dirty")], []))
    _validate(dirty)
    assert any(row["evidence_tier"] == "RC1_dirty_exact_attention" for row in dirty["cases"])

    clean = _shape(
        _triple([_project("clean", dirty=False, reason="stale_branch_in_active_project")], [])
    )
    _validate(clean)
    assert clean["cases"] == []

    mixed_item = _project("mixed", dirty=False, reason="stale_branch_in_active_project")
    mixed_item[1]["reasons"].append("no_upstream_tracking")
    mixed = _shape(_triple([mixed_item], []))
    _validate(mixed)
    assert any(row["evidence_tier"] == "RC3_unassigned_observed_bundle" for row in mixed["cases"])


def test_existing_workstream_trigger_produces_rc2_but_quiet_work_does_not() -> None:
    project_item = _project("trigger", dirty=False, reason="stale_branch_in_active_project")
    branch_id, _ = _resource_ids(project_item[0])
    active = _shape(
        _triple(
            [project_item],
            [_workstream("ws", "triggered work", bindings=[("branch", branch_id, "accepted")])],
        )
    )
    _validate(active)
    assert any(row["evidence_tier"] == "RC2_existing_workstream_trigger" for row in active["cases"])

    quiet = _shape(
        _triple(
            [project_item],
            [
                _workstream(
                    "ws",
                    "quiet work",
                    lifecycle="paused",
                    bindings=[("branch", branch_id, "accepted")],
                )
            ],
        )
    )
    _validate(quiet)
    assert not any(
        row["evidence_tier"] == "RC2_existing_workstream_trigger" for row in quiet["cases"]
    )
    assert quiet["coverage"]["quiet_workstream_ids"] == ["ws"]


def test_today_review_is_capped_and_hidden_inventory_is_explicit() -> None:
    items = [
        _project(str(index), conflicted=True, reason="conflicted_worktree") for index in range(6)
    ]
    result = _shape(_triple(items, []), limit=2)
    _validate(result)
    assert len(result["review_queue"]) <= 2
    assert set(
        attention_id for row in result["review_queue"] for attention_id in row["attention_ids"]
    ) <= set(result["coverage"]["today_attention_ids"])
    assert result["summary"]["hidden_case_count"] == result["coverage"]["cases_truncated_count"]
    assert result["coverage"]["source_case_count"] > result["summary"]["case_count"]


def test_case_identity_ignores_time_but_revision_changes_with_material_evidence() -> None:
    triple = _triple([_project("stable", dirty=False, reason="no_upstream_tracking")], [])
    first = _shape(triple, now=NOW)
    second = _shape(triple, now=NOW + timedelta(minutes=5))
    _validate(first)
    _validate(second)
    assert [(row["case_id"], row["revision_id"]) for row in first["cases"]] == [
        (row["case_id"], row["revision_id"]) for row in second["cases"]
    ]

    state, cockpit, _ = triple
    changed_cockpit = deepcopy(cockpit)
    changed_cockpit["attention_queue"][0]["band"] = "integrity_unknown"
    changed_cockpit["today"][0]["band"] = "integrity_unknown"
    reconciliation = pr.build_portfolio_reconciliation(changed_cockpit, now=NOW, schema_root=ROOT)
    changed = _shape((state, changed_cockpit, reconciliation))
    _validate(changed)
    assert first["cases"][0]["case_id"] == changed["cases"][0]["case_id"]
    assert first["cases"][0]["revision_id"] != changed["cases"][0]["revision_id"]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda value: value["cases"][0].__setitem__("case_id", "tampered"),
            "case_identity_mismatch",
        ),
        (
            lambda value: value["cases"][0]["choices"][0].__setitem__("execution_available", True),
            "choice_authority_mismatch",
        ),
        (
            lambda value: value["summary"].__setitem__("shaping_complete", True),
            "shaping_complete_mismatch",
        ),
        (
            lambda value: value["review_queue"].append(deepcopy(value["review_queue"][0])),
            "duplicate_review_id",
        ),
    ],
)
def test_semantic_tampering_fails_closed(mutation, expected: str) -> None:
    result = _shape(
        _triple([_project("tamper", conflicted=True, reason="conflicted_worktree")], [])
    )
    mutation(result)
    assert any(expected in problem for problem in ps.portfolio_shaping_semantic_problems(result))


def test_html_is_inert_escaped_and_contains_no_raw_paths_or_conversations() -> None:
    malicious = '<script>alert("x")</script>'
    project_item = _project("html")
    triple = _triple([project_item], [_workstream("ws", malicious)])
    result = _shape(triple)
    _validate(result)
    html = ps.portfolio_shaping_html(result)
    digest = base64.b64encode(hashlib.sha256(ps._STYLE.encode("utf-8")).digest()).decode("ascii")
    lowered = html.casefold()
    assert malicious not in html
    assert "<script" not in lowered and "<form" not in lowered and "<button" not in lowered
    assert "http://" not in lowered and "https://" not in lowered
    assert "c:/private" not in lowered
    assert f"sha256-{digest}" in unescape(html)
    assert '<a class="skip" href="#main">' in html
    assert "<caption>" in html and 'scope="col"' in html
    payload = json.dumps(result)
    assert "C:/private" not in payload
    assert "idea_text" not in payload and "conversations" not in payload


def test_coupling_and_status_tampering_cannot_create_false_green() -> None:
    state, cockpit, reconciliation = _triple([_project("coupling")], [])
    mismatched = deepcopy(cockpit)
    mismatched["source_refs"]["workstreams"] = "sha256:" + "0" * 64
    result = ps.build_portfolio_shaping(
        state,
        mismatched,
        reconciliation,
        now=NOW,
        schema_root=ROOT,
    )
    result["blockers"] = [
        row
        for row in result["blockers"]
        if row["kind"]
        not in {
            "workstream_cockpit_hash_mismatch",
            "cockpit_reconciliation_hash_mismatch",
        }
    ]
    result["summary"]["blocker_count"] = len(result["blockers"])
    result["summary"]["shaping_complete"] = True
    result["status"] = "generated_candidate"
    problems = ps.portfolio_shaping_semantic_problems(result)
    assert "source_coupling_blocker_mismatch:workstreams_to_cockpit" in problems
    assert "projection_status_mismatch" in problems
    assert "shaping_complete_mismatch" in problems


def test_tiers_subjects_choices_and_status_are_semantically_bound() -> None:
    result = _shape(_triple([_project("bound")], []))

    wrong_kind = deepcopy(result)
    wrong_kind["cases"][0]["case_kind"] = "rescope"
    assert "tier_case_kind_mismatch" in ps.portfolio_shaping_semantic_problems(wrong_kind)

    missing_subject = deepcopy(result)
    missing_subject["cases"][0]["subject_resource_ids"] = ["resource-does-not-exist"]
    assert "case_resource_subject_missing" in ps.portfolio_shaping_semantic_problems(
        missing_subject
    )

    social_action = deepcopy(result)
    social_action["cases"][0]["choices"][0]["label"] = "Apply now"
    assert "case_choice_vocabulary_mismatch" in ps.portfolio_shaping_semantic_problems(
        social_action
    )

    false_status = deepcopy(result)
    false_status["unknowns"] = [
        {
            "source": "reconciliation",
            "kind": "test_unknown",
            "ref": "dad:test:opaque",
            "note": "Evidence remains incomplete; inspect the source projection locally.",
            "severity": "warning",
        }
    ]
    false_status["summary"]["unknown_count"] = 1
    assert "projection_status_mismatch" in ps.portfolio_shaping_semantic_problems(false_status)


@pytest.mark.parametrize("target", ["cockpit", "reconciliation"])
def test_malformed_nested_source_refs_fail_closed_without_crashing(target: str) -> None:
    state, cockpit, reconciliation = _triple([_project(f"malformed-{target}")], [])
    if target == "cockpit":
        cockpit = deepcopy(cockpit)
        cockpit["source_refs"] = []
    else:
        reconciliation = deepcopy(reconciliation)
        reconciliation["source_refs"] = []
    result = ps.build_portfolio_shaping(
        state,
        cockpit,
        reconciliation,
        now=NOW,
        schema_root=ROOT,
    )
    assert result["status"] == "blocked_candidate"
    assert result["cases"] == []
    _validate(result)


@pytest.mark.parametrize(
    "private_value",
    [
        "PRIVATE CLIENT MATTER 8472 settlement strategy",
        "/srv/private/client-repo",
        "/tmp/private-client-record",
        "/var/lib/private",
        "/mnt/client",
        "/workspace/private",
        r"\\server\share\client",
        r"\\?\C:\client\private",
        "~/private-client",
    ],
)
def test_inherited_private_labels_are_minimized_by_provenance(private_value: str) -> None:
    triple = _triple([_project("private-label")], [_workstream("ws", private_value)])
    result = _shape(triple)
    _validate(result)
    payload = json.dumps(result)
    html = ps.portfolio_shaping_html(result)
    assert private_value not in payload
    assert private_value not in html
    assert all(card["label"] == "Workstream" for card in result["workstream_cards"])


@pytest.mark.parametrize(
    "private_trigger",
    [
        "PRIVATE CLIENT MATTER 8472 settlement strategy",
        "/srv/private/client-trigger",
    ],
)
def test_inherited_trigger_kind_is_categorical(private_trigger: str) -> None:
    project_item = _project("private-trigger", dirty=False, reason="no_upstream_tracking")
    branch_id, _ = _resource_ids(project_item[0])
    pair = _workstream(
        "ws-trigger-private",
        "ordinary idea",
        bindings=[("branch", branch_id, "accepted")],
    )
    pair[1]["trigger_kind"] = private_trigger
    result = _shape(_triple([project_item], [pair]))
    _validate(result)
    rc2 = next(
        row for row in result["cases"] if row["evidence_tier"] == "RC2_existing_workstream_trigger"
    )
    assert rc2["evidence_summary"]["trigger_kinds"] == ["other_trigger"]
    assert private_trigger not in json.dumps(result)


def test_html_makes_partial_sources_and_unknowns_prominent() -> None:
    result = _shape(_triple([_project("html-unknown")], []))
    result["unknowns"] = [
        {
            "source": "reconciliation",
            "kind": "discovery_incomplete",
            "ref": "dad:opaque:unknown",
            "note": "Evidence remains incomplete; inspect the source projection locally.",
            "severity": "warning",
        }
    ]
    result["summary"]["unknown_count"] = 1
    result["status"] = "partial_candidate"
    html = ps.portfolio_shaping_html(result)
    assert "Status: partial_candidate" in html
    assert "There are 1 source unknowns" in html
    assert "<h2>Source readiness</h2>" in html
    assert "<h2>Unknowns</h2>" in html
    assert "discovery_incomplete" in html


def test_writer_rejects_semantic_tampering_and_publishes_strict_outputs(tmp_path: Path) -> None:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "registry").mkdir()
    for name in (
        "portfolio-attention-report.schema.json",
        "portfolio-workstream-state.schema.json",
        "portfolio-cockpit.schema.json",
        "portfolio-reconciliation.schema.json",
        "portfolio-workstream-shaping.schema.json",
    ):
        (tmp_path / "schemas" / name).write_bytes((ROOT / "schemas" / name).read_bytes())
    (tmp_path / "registry" / "schema-registry.json").write_bytes(
        (ROOT / "registry" / "schema-registry.json").read_bytes()
    )
    triple = _triple([_project("write")], [])
    result = _shape(triple)
    state, cockpit, reconciliation = triple
    packet = ps.write_portfolio_shaping_outputs(
        tmp_path,
        result,
        workstream_state=state,
        cockpit=cockpit,
        reconciliation=reconciliation,
    )
    assert Path(packet["json_path"]).exists() and Path(packet["html_path"]).exists()
    decisions = _decisions_for(result)
    decided = ps.build_portfolio_shaping(
        *triple,
        decisions=decisions,
        now=NOW,
        schema_root=ROOT,
    )
    decided_packet = ps.write_portfolio_shaping_outputs(
        tmp_path,
        decided,
        workstream_state=state,
        cockpit=cockpit,
        reconciliation=reconciliation,
        decisions=decisions,
    )
    assert decided_packet["summary"]["case_count"] == decided["summary"]["case_count"]
    tampered = deepcopy(result)
    tampered["cases"][0]["choices"][0]["execution_available"] = True
    with pytest.raises(ValueError, match="Invalid portfolio shaping"):
        ps.write_portfolio_shaping_outputs(
            tmp_path,
            tampered,
            workstream_state=state,
            cockpit=cockpit,
            reconciliation=reconciliation,
        )
