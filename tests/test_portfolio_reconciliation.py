"""Adversarial tests for proposal-only Portfolio OS reconciliation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import unescape
import json
from pathlib import Path
import random
import shutil

import pytest
from jsonschema import FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from digital_asset_directory import portfolio_cockpit as pc
from digital_asset_directory import portfolio_reconciliation as pr


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
    *,
    project_id: str = "dad:portfolio-project:test",
    name: str = "DAD Portfolio OS",
    branch: str = "feature/portfolio-organizer",
    path: str = "C:/private/never-render-this-path",
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "name": name,
        "common_git_dir": f"{path}/.git",
        "remote_url": "",
        "default_branch": "main",
        "active_within_threshold": True,
        "branches": [
            {
                "name": branch,
                "head": "a" * 40,
                "committed_at": NOW.isoformat(),
                "subject": "organize portfolio workstreams",
                "upstream": "",
                "upstream_gone": False,
                "ahead": 0,
                "behind": 0,
                "project_id": project_id,
                "project_name": name,
                "worktree_path": path,
                "dirty": True,
                "status_unknown": False,
                "status_error": "",
                "worktree_locked": False,
                "conflicted": False,
                "changed_path_count": 2,
                "last_activity_at": NOW.isoformat(),
                "inactive_days": 5,
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
                "dirty": True,
                "change_counts": {
                    "staged": 0,
                    "unstaged": 2,
                    "untracked": 0,
                    "conflicted": 0,
                },
                "changed_path_count": 2,
                "latest_dirty_activity_at": NOW.isoformat(),
                "status_error": "",
            }
        ],
        "related_projects": [],
    }


def _attention(project: dict[str, object]) -> dict[str, object]:
    branch = project["branches"][0]
    return {
        "priority": 90,
        "project_id": project["project_id"],
        "project_name": project["name"],
        "branch": branch["name"],
        "worktree_path": branch["worktree_path"],
        "last_activity_at": NOW.isoformat(),
        "inactive_days": 5,
        "reasons": ["dirty_worktree_idle"],
        "next_action": "Review the diff.",
        "evidence": {
            "dirty": True,
            "changed_path_count": 2,
            "ahead": 0,
            "behind": 0,
            "merged_by_ancestry": False,
            "upstream": "",
            "worktree_locked": False,
        },
    }


def _git(project: dict[str, object] | None = None) -> dict[str, object]:
    projects = [project] if project else []
    attention = [_attention(project)] if project else []
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
            "dirty_worktree_count": len(projects),
            "attention_item_count": len(attention),
            "today_item_count": len(attention),
        },
        "today": attention,
        "projects": projects,
        "attention_queue": attention,
        "authority_boundary": "Read-only candidate evidence.",
    }


def _workstream(
    workstream_id: str = "ws-organizer",
    *,
    label: str = "portfolio organizer worktree",
    lifecycle: str = "active",
    bindings: list[dict[str, str]] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    normalized = [
        {
            "binding_id": row["binding_id"],
            "binding_kind": row["binding_kind"],
            "ref": row["ref"],
            "label": "",
            "assertion_status": row["assertion_status"],
            "asserted_by": "test",
            "approval_ref": "",
            "recorded_at": NOW.isoformat(),
        }
        for row in (bindings or [])
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
        "inactive_days": 5,
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
        "inactive_days": 5,
        "reasons": ["weekly_review"],
        "suppressed_reasons": [],
        "next_action": "Review.",
        "last_activity_at": NOW.isoformat(),
    }
    return row, focus


def _state(
    pairs: list[tuple[dict[str, object], dict[str, object]]] | None = None,
) -> dict[str, object]:
    pairs = pairs or []
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


def _cockpit(
    *,
    project: dict[str, object] | None = None,
    pairs: list[tuple[dict[str, object], dict[str, object]]] | None = None,
) -> dict[str, object]:
    return pc.build_portfolio_cockpit(
        _git(project), _state(pairs), now=NOW, schema_root=ROOT
    )


def _validate(value: dict[str, object]) -> None:
    schema = json.loads(
        (ROOT / "schemas" / "portfolio-reconciliation.schema.json").read_text(
            encoding="utf-8"
        )
    )
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema, format_checker=FormatChecker()).validate(value)
    assert pr.portfolio_reconciliation_semantic_problems(value) == []


def _validate_schema_only(value: dict[str, object]) -> None:
    schema = json.loads(
        (ROOT / "schemas" / "portfolio-reconciliation.schema.json").read_text(
            encoding="utf-8"
        )
    )
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema, format_checker=FormatChecker()).validate(value)


def test_missing_or_invalid_source_blocks_and_never_false_greens() -> None:
    result = pr.build_portfolio_reconciliation(None, now=NOW, schema_root=ROOT)

    _validate(result)
    assert result["status"] == "blocked_candidate"
    assert result["summary"]["fully_reconciled"] is False
    assert result["summary"]["no_candidates_generated"] is True
    assert result["blockers"][0]["kind"] == "source_not_ready"


def test_ready_structural_proposal_prevents_full_reconciliation_without_attention() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted-worktree",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    cockpit["attention_queue"] = []
    cockpit["today"] = []

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["summary"]["proposal_ready_count"] == 0
    assert any(
        row["disposition"] == "proposal_available"
        for row in result["binding_candidates"]
    )
    assert all(row["proposal_command"] is None for row in result["binding_candidates"])
    assert result["summary"]["fully_reconciled"] is False
    _validate(result)


def test_hidden_ready_proposal_prevents_full_reconciliation() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    bindings = [
        {
            "binding_id": "binding-accepted-worktree",
            "binding_kind": "worktree",
            "ref": worktree_id,
            "assertion_status": "accepted",
        },
        {
            "binding_id": "binding-proposed-repo",
            "binding_kind": "repo",
            "ref": str(project["project_id"]),
            "assertion_status": "proposed",
        },
    ]
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=bindings)])
    cockpit["attention_queue"] = []
    cockpit["today"] = []

    result = pr.build_portfolio_reconciliation(
        cockpit,
        now=NOW,
        settings=pr.ReconciliationSettings(candidate_limit=1),
        schema_root=ROOT,
    )

    assert result["summary"]["proposal_ready_count"] == 0
    assert result["summary"]["hidden_exact_proposal_count"] == 1
    assert result["workstream_cards"][0]["hidden_exact_proposal_count"] == 1
    assert result["summary"]["fully_reconciled"] is False
    _validate(result)
    html = pr.portfolio_reconciliation_html(result)
    assert "hidden exact proposals" in html
    assert "<strong>1</strong><span>hidden exact proposals</span>" in html
    assert "Visible and hidden exact evidence by eligible workstream." in html
    assert "portfolio organizer" in html


def test_persisted_proposal_commands_are_bounded_to_review_queue() -> None:
    projects = []
    pairs = []
    for index in range(12):
        project = _project(
            project_id=f"dad:portfolio-project:{index}",
            name=f"Portfolio {index}",
            branch=f"feature/portfolio-{index}",
            path=f"C:/private/worktree-{index}",
        )
        projects.append(project)
        worktree_id = pc.worktree_resource_id(
            str(project["project_id"]), str(project["worktrees"][0]["path"])
        )
        pairs.append(
            _workstream(
                f"ws-{index}",
                label=f"portfolio {index}",
                bindings=[
                    {
                        "binding_id": f"binding-{index}",
                        "binding_kind": "worktree",
                        "ref": worktree_id,
                        "assertion_status": "accepted",
                    }
                ],
            )
        )
    git = _git()
    git["projects"] = projects
    git["attention_queue"] = [_attention(project) for project in projects]
    git["today"] = git["attention_queue"][:3]
    git["summary"].update(
        {
            "project_count": len(projects),
            "branch_count": len(projects),
            "worktree_count": len(projects),
            "dirty_worktree_count": len(projects),
            "attention_item_count": len(projects),
            "today_item_count": 3,
        }
    )
    cockpit = pc.build_portfolio_cockpit(git, _state(pairs), now=NOW, schema_root=ROOT)

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    commands = [
        row for row in result["binding_candidates"] if row["proposal_command"] is not None
    ]

    assert len(result["review_queue"]) <= 3
    assert len(commands) <= len(result["review_queue"])
    assert {row["proposal_id"] for row in commands} <= {
        row["proposal_id"] for row in result["review_queue"]
    }
    assert any(
        row["disposition"] == "proposal_available"
        for row in result["binding_candidates"]
    )
    _validate(result)


def test_schema_rejects_fully_reconciled_with_stale_source() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    bindings = [
        {
            "binding_id": "binding-accepted-branch",
            "binding_kind": "branch",
            "ref": branch_id,
            "assertion_status": "accepted",
        },
        {
            "binding_id": "binding-accepted-worktree",
            "binding_kind": "worktree",
            "ref": worktree_id,
            "assertion_status": "accepted",
        },
    ]
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=bindings)])
    cockpit["attention_queue"] = []
    cockpit["today"] = []
    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    assert result["summary"]["fully_reconciled"] is True
    result["source"]["freshness"] = "stale"
    result["source"]["problems"] = ["source_stale"]

    with pytest.raises(ValidationError):
        _validate(result)


def test_zero_workstreams_requires_intake_and_is_not_all_clear() -> None:
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=_project()), now=NOW, schema_root=ROOT
    )

    _validate(result)
    assert result["summary"]["intake_needed"] is True
    assert result["summary"]["fully_reconciled"] is False
    assert result["summary"]["candidate_count"] == 0
    assert len(result["unassigned_bundles"]) == 1
    bundle = result["unassigned_bundles"][0]
    assert set(bundle["resource_kinds"]) == {"branch", "worktree"}
    assert len(bundle["resource_ids"]) == 2
    assert bundle["context_workstream_id"] == ""


def test_repo_binding_is_context_not_branch_worktree_completion() -> None:
    project = _project()
    binding = {
        "binding_id": "binding-accepted-repo",
        "binding_kind": "repo",
        "ref": str(project["project_id"]),
        "assertion_status": "accepted",
    }
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=project, pairs=[_workstream(bindings=[binding])]),
        now=NOW,
        schema_root=ROOT,
    )

    assert result["summary"]["fully_reconciled"] is False
    assert len(result["unassigned_bundles"]) == 1
    bundle = result["unassigned_bundles"][0]
    assert set(bundle["resource_kinds"]) == {"branch", "worktree"}
    assert bundle["context_workstream_id"] == "ws-organizer"
    _validate(result)


def test_accepted_worktree_still_requires_exact_branch_counterpart() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted-worktree",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=project, pairs=[_workstream(bindings=[binding])]),
        now=NOW,
        schema_root=ROOT,
    )

    assert result["summary"]["proposal_ready_count"] == 1
    assert result["summary"]["fully_reconciled"] is False
    assert len(result["unassigned_bundles"]) == 1
    assert result["unassigned_bundles"][0]["resource_kinds"] == ["branch"]
    _validate(result)


def test_repo_candidate_is_not_propagated_into_specific_recovery_bundles() -> None:
    project = _project()
    binding = {
        "binding_id": "binding-proposed-repo",
        "binding_kind": "repo",
        "ref": str(project["project_id"]),
        "assertion_status": "proposed",
    }
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=project, pairs=[_workstream(bindings=[binding])]),
        now=NOW,
        schema_root=ROOT,
    )
    repo_candidate = next(
        row
        for row in result["binding_candidates"]
        if row["resource_kind"] == "repo"
        and row["evidence_tier"] == "E0_existing_exact"
    )

    assert all(
        repo_candidate["proposal_id"] not in bundle["candidate_proposal_ids"]
        for bundle in result["unassigned_bundles"]
    )
    _validate(result)


def test_existing_exact_proposal_is_review_only_and_never_execution() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(str(project["project_id"]), "feature/portfolio-organizer")
    binding = {
        "binding_id": "binding-proposed",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "proposed",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    candidate = next(
        row for row in result["binding_candidates"] if row["evidence_tier"] == "E0_existing_exact"
    )
    assert candidate["disposition"] == "review_existing"
    assert candidate["proposal_command"] is None
    assert result["execution_authorized"] is False
    assert result["mutations_performed"] is False
    _validate(result)


def test_existing_exact_proposal_outranks_structural_evidence_for_same_resource() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    bindings = [
        {
            "binding_id": "binding-accepted-worktree",
            "binding_kind": "worktree",
            "ref": worktree_id,
            "assertion_status": "accepted",
        },
        {
            "binding_id": "binding-proposed-branch",
            "binding_kind": "branch",
            "ref": branch_id,
            "assertion_status": "proposed",
        },
    ]

    result = pr.build_portfolio_reconciliation(
        _cockpit(project=project, pairs=[_workstream(bindings=bindings)]),
        now=NOW,
        schema_root=ROOT,
    )
    branch_candidates = [
        row for row in result["binding_candidates"] if row["resource_id"] == branch_id
    ]

    assert len(branch_candidates) == 1
    assert branch_candidates[0]["evidence_tier"] == "E0_existing_exact"
    assert branch_candidates[0]["disposition"] == "review_existing"
    assert branch_candidates[0]["proposal_command"] is None
    _validate(result)


def test_duplicate_existing_exact_proposals_aggregate_deterministically() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    bindings = [
        {
            "binding_id": "binding-z",
            "binding_kind": "branch",
            "ref": branch_id,
            "assertion_status": "proposed",
        },
        {
            "binding_id": "binding-a",
            "binding_kind": "branch",
            "ref": branch_id,
            "assertion_status": "proposed",
        },
    ]
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=bindings)])
    reversed_cockpit = deepcopy(cockpit)
    reversed_cockpit["bindings"].reverse()

    first = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    second = pr.build_portfolio_reconciliation(
        reversed_cockpit, now=NOW, schema_root=ROOT
    )
    candidate = next(
        row
        for row in first["binding_candidates"]
        if row["evidence_tier"] == "E0_existing_exact"
    )

    assert first == second
    assert candidate["evidence_details"]["binding_id"] == "binding-a"
    assert candidate["evidence_details"]["binding_ids"] == ["binding-a", "binding-z"]
    assert "multiple_existing_exact_proposals" in candidate["signals"]
    assert candidate["proposal_command"] is None
    _validate(first)


def test_unique_branch_worktree_link_can_only_prepare_a_proposal_command() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    candidate = next(
        row for row in result["binding_candidates"] if row["evidence_tier"] == "E1_unique_structural"
    )
    args = candidate["proposal_command"]["args"]
    assert candidate["disposition"] == "proposal_ready"
    assert args[:2] == ["os", "bind"]
    assert "--accept" not in args
    assert "--approved-by" not in args
    _validate(result)


def test_structural_candidate_requires_reciprocal_same_project_counterpart() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    worktree = next(
        row for row in cockpit["resources"] if row["resource_id"] == worktree_id
    )
    worktree["linked_resource_ids"] = [str(project["project_id"])]

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert all(
        row["evidence_tier"] != "E1_unique_structural"
        for row in result["binding_candidates"]
    )
    assert all(row["proposal_command"] is None for row in result["binding_candidates"])
    _validate(result)


def test_structural_candidate_requires_unique_raw_link_lists() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    worktree = next(
        row for row in cockpit["resources"] if row["resource_id"] == worktree_id
    )
    branch = next(row for row in cockpit["resources"] if row["resource_id"] == branch_id)
    worktree["linked_resource_ids"].append("ghost")
    branch["linked_resource_ids"].append("ghost-reciprocal")

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert all(
        row["evidence_tier"] != "E1_unique_structural"
        for row in result["binding_candidates"]
    )
    assert all(row["proposal_command"] is None for row in result["binding_candidates"])
    _validate(result)


def test_similarity_is_inspect_only_and_never_emits_a_command() -> None:
    cockpit = _cockpit(
        project=_project(),
        pairs=[_workstream(label="portfolio organizer operating system")],
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    inspect = [
        row for row in result["binding_candidates"] if row["evidence_tier"] == "I0_inspect_only"
    ]
    assert inspect
    assert all(row["disposition"] == "inspect_only" for row in inspect)
    assert all(row["proposal_command"] is None for row in inspect)
    assert all("similarity_is_not_identity" in row["counterevidence"] for row in inspect)


def test_equal_best_exact_proposals_are_ambiguous_and_choose_no_winner() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    binding = {
        "binding_id": "binding-proposed",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "proposed",
    }
    cockpit = _cockpit(
        project=project,
        pairs=[
            _workstream("ws-a", bindings=[binding]),
            _workstream(
                "ws-b",
                bindings=[{**binding, "binding_id": "binding-proposed-b"}],
            ),
        ],
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    exact = [
        row
        for row in result["binding_candidates"]
        if row["evidence_tier"] == "E0_existing_exact"
    ]
    assert len(exact) == 2
    assert all(row["disposition"] == "ambiguous" for row in exact)
    assert all(row["proposal_command"] is None for row in exact)
    assert all(
        "multiple_exact_workstreams_for_resource" in row["counterevidence"] for row in exact
    )


def test_cross_tier_exact_workstream_competition_fails_closed() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    cockpit = _cockpit(
        project=project,
        pairs=[
            _workstream(
                "ws-existing",
                bindings=[
                    {
                        "binding_id": "binding-proposed-branch",
                        "binding_kind": "branch",
                        "ref": branch_id,
                        "assertion_status": "proposed",
                    }
                ],
            ),
            _workstream(
                "ws-structural",
                bindings=[
                    {
                        "binding_id": "binding-accepted-worktree",
                        "binding_kind": "worktree",
                        "ref": worktree_id,
                        "assertion_status": "accepted",
                    }
                ],
            ),
        ],
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    competing = [
        row for row in result["binding_candidates"] if row["resource_id"] == branch_id
    ]

    assert {row["evidence_tier"] for row in competing} == {
        "E0_existing_exact",
        "E1_unique_structural",
    }
    assert all(row["disposition"] == "ambiguous" for row in competing)
    assert all(row["proposal_command"] is None for row in competing)
    assert all(
        "multiple_exact_workstreams_for_resource" in row["counterevidence"]
        for row in competing
    )
    _validate(result)


def test_blocker_refs_do_not_copy_path_shaped_source_ids() -> None:
    path_id = r"C:\private\client\matter"
    cockpit = _cockpit(project=_project(), pairs=[_workstream()])
    duplicate_resource = deepcopy(cockpit["resources"][0])
    duplicate_resource.update(
        {
            "resource_id": path_id,
            "accepted_workstream_ids": [],
            "linked_resource_ids": [],
        }
    )
    cockpit["resources"].extend([duplicate_resource, deepcopy(duplicate_resource)])
    duplicate_workstream = deepcopy(cockpit["workstreams"][0])
    duplicate_workstream["workstream_id"] = path_id
    duplicate_workstream["accepted_resource_ids"] = []
    cockpit["workstreams"].extend(
        [duplicate_workstream, deepcopy(duplicate_workstream)]
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    encoded_blockers = json.dumps(result["blockers"])

    assert path_id not in encoded_blockers
    assert {row["kind"] for row in result["blockers"]} >= {
        "duplicate_resource_id",
        "duplicate_workstream_id",
    }
    _validate(result)


def test_duplicate_resource_identity_is_quarantined() -> None:
    cockpit = _cockpit(project=_project(), pairs=[_workstream()])
    cockpit["resources"].append(deepcopy(cockpit["resources"][0]))

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["summary"]["fully_reconciled"] is False
    assert any(row["kind"] == "duplicate_resource_id" for row in result["blockers"])
    duplicate_id = cockpit["resources"][0]["resource_id"]
    assert all(
        row["resource_id"] != duplicate_id for row in result["binding_candidates"]
    )
    _validate(result)


def test_permutation_is_deterministic_and_proposed_candidates_do_not_change_dependencies() -> None:
    project = _project()
    first_pair = _workstream("ws-a", label="portfolio organizer operating system")
    second_pair = _workstream("ws-b", label="portfolio worktree organizer")
    cockpit = _cockpit(project=project, pairs=[first_pair, second_pair])
    shuffled = deepcopy(cockpit)
    random.Random(23).shuffle(shuffled["resources"])
    random.Random(29).shuffle(shuffled["workstreams"])
    random.Random(31).shuffle(shuffled["bindings"])

    first = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    second = pr.build_portfolio_reconciliation(shuffled, now=NOW, schema_root=ROOT)

    assert first == second
    assert first["dependency_context"]["accepted_only"] is True
    assert first["dependency_context"]["critical_path_claimed"] is False
    assert first["dependency_context"]["unlock_frontier"] == cockpit["lanes"]["unlock_frontier"]


def test_stale_and_future_cockpit_snapshots_block_candidate_generation() -> None:
    cockpit = _cockpit(project=_project(), pairs=[_workstream()])

    stale = pr.build_portfolio_reconciliation(
        cockpit,
        now=NOW + timedelta(hours=27),
        schema_root=ROOT,
    )
    future_cockpit = _cockpit(project=_project(), pairs=[_workstream()])
    future_cockpit["generated_at"] = (NOW + timedelta(hours=2)).isoformat()
    future = pr.build_portfolio_reconciliation(
        future_cockpit,
        now=NOW,
        schema_root=ROOT,
    )

    assert stale["source"]["freshness"] == "stale"
    assert future["source"]["freshness"] == "future"
    for result in (stale, future):
        assert result["status"] == "blocked_candidate"
        assert result["summary"]["fully_reconciled"] is False
        assert result["binding_candidates"] == []
        assert any(row["kind"] == "source_not_ready" for row in result["blockers"])
        _validate(result)


def test_cockpit_unknowns_are_sanitized_counted_and_visible() -> None:
    cockpit = _cockpit(project=_project(), pairs=[_workstream()])
    private_path = r"C:\private\client\secret-repo"
    cockpit["unknowns"].append(
        {
            "source": "git",
            "kind": "scan_error",
            "ref": private_path,
            "note": f"Cannot inspect {private_path}",
            "severity": "danger",
        }
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    html = pr.portfolio_reconciliation_html(result)
    serialized = json.dumps(result)

    assert result["summary"]["unknown_count"] == 1
    assert result["summary"]["blocking_evidence_count"] >= 1
    assert result["summary"]["fully_reconciled"] is False
    assert private_path not in serialized
    assert private_path not in unescape(html)
    assert "scan_error" in html
    assert "Fully reconciled: no" in html
    assert "Cockpit evidence gaps" in html
    _validate(result)


def test_quiet_workstream_cannot_reenter_review_queue() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    binding = {
        "binding_id": "binding-proposed",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "proposed",
    }
    cockpit = _cockpit(
        project=project,
        pairs=[_workstream(lifecycle="paused", bindings=[binding])],
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["quiet_workstream_ids"] == ["ws-organizer"]
    assert result["binding_candidates"] == []
    assert result["review_queue"] == []
    assert result["summary"]["intake_needed"] is False


def test_material_structural_evidence_changes_revision_not_proposal_identity() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    first = pr.build_portfolio_reconciliation(
        _cockpit(
            project=project,
            pairs=[_workstream(label="portfolio worktree", bindings=[binding])],
        ),
        now=NOW,
        schema_root=ROOT,
    )
    second = pr.build_portfolio_reconciliation(
        _cockpit(
            project=project,
            pairs=[_workstream(label="organizer worktree", bindings=[binding])],
        ),
        now=NOW,
        schema_root=ROOT,
    )
    first_e1 = next(
        row for row in first["binding_candidates"] if row["evidence_tier"] == "E1_unique_structural"
    )
    second_e1 = next(
        row for row in second["binding_candidates"] if row["evidence_tier"] == "E1_unique_structural"
    )

    assert first_e1["proposal_id"] == second_e1["proposal_id"]
    assert first_e1["revision_id"] != second_e1["revision_id"]
    assert (
        first_e1["evidence_details"]["structural_anchor_resource_id"]
        == worktree_id
    )
    assert first_e1["evidence_details"]["shared_tokens"] != second_e1["evidence_details"]["shared_tokens"]


def test_schema_rejects_promotion_flags_in_structured_command() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=project, pairs=[_workstream(bindings=[binding])]),
        now=NOW,
        schema_root=ROOT,
    )
    candidate = next(
        row for row in result["binding_candidates"] if row["proposal_command"]
    )
    candidate["proposal_command"]["args"].append("--accept")

    with pytest.raises(ValidationError):
        _validate(result)


def test_unknown_categories_cannot_smuggle_local_paths() -> None:
    cockpit = _cockpit(project=_project(), pairs=[_workstream()])
    cockpit["unknowns"] = [
        {
            "source": "C:/Users/private/source",
            "kind": r"C:\Users\private\kind",
            "ref": "C:/Users/private/ref",
            "note": "C:/Users/private/note",
            "severity": "warning",
        }
    ]

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    encoded = json.dumps(result)

    assert "C:/Users/private" not in encoded
    assert r"C:\\Users\\private" not in encoded
    assert result["unknowns"][0]["source"] == "cockpit"
    assert result["unknowns"][0]["kind"] == "unknown_evidence"


def test_missing_accepted_resource_cannot_make_fully_reconciled_true() -> None:
    project = _project()
    cockpit = _cockpit(project=project, pairs=[_workstream()])
    cockpit["workstreams"][0]["accepted_resource_ids"] = ["missing-resource"]
    cockpit["bindings"] = []
    cockpit["attention_queue"] = []
    cockpit["today"] = []
    cockpit["unknowns"] = []

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["summary"]["fully_reconciled"] is False
    assert any(row["kind"] == "accepted_resource_missing" for row in result["blockers"])
    _validate(result)


def test_accepted_ownership_must_be_bidirectional_and_exact() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    resource = next(
        row for row in cockpit["resources"] if row["resource_id"] == branch_id
    )
    resource["accepted_workstream_ids"] = []
    cockpit["attention_queue"] = []
    cockpit["today"] = []
    cockpit["unknowns"] = []

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["summary"]["fully_reconciled"] is False
    assert any(
        row["kind"] == "accepted_ownership_not_bidirectional"
        for row in result["blockers"]
    )
    _validate(result)


def test_schema_rejects_commands_on_non_structural_candidates() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=project, pairs=[_workstream(bindings=[binding])]),
        now=NOW,
        schema_root=ROOT,
    )
    e1 = next(row for row in result["binding_candidates"] if row["proposal_command"])
    inspect_result = pr.build_portfolio_reconciliation(
        _cockpit(
            project=project,
            pairs=[_workstream(label="portfolio organizer operating system")],
        ),
        now=NOW,
        schema_root=ROOT,
    )
    inspect = next(
        row
        for row in inspect_result["binding_candidates"]
        if row["evidence_tier"] == "I0_inspect_only"
    )
    inspect["proposal_command"] = e1["proposal_command"]

    with pytest.raises(ValidationError):
        _validate(inspect_result)


def test_schema_rejects_false_green_intake_projection() -> None:
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=_project()), now=NOW, schema_root=ROOT
    )
    result["summary"]["fully_reconciled"] = True

    with pytest.raises(ValidationError):
        _validate(result)


def test_binding_semantic_mismatch_is_quarantined_and_suppresses_commands() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    cockpit["bindings"][0]["binding_kind"] = "repo"

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert any(row["kind"] == "binding_semantic_mismatch" for row in result["blockers"])
    assert result["summary"]["proposal_ready_count"] == 0
    assert all(row["proposal_command"] is None for row in result["binding_candidates"])
    _validate(result)


def test_integrity_blocker_downgrades_otherwise_ready_structural_candidate() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    branch = next(row for row in cockpit["resources"] if row["resource_id"] == branch_id)
    branch["accepted_workstream_ids"] = []

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert any(
        row["kind"] == "accepted_ownership_not_bidirectional"
        for row in result["blockers"]
    )
    assert result["summary"]["proposal_ready_count"] == 0
    e1 = next(
        row
        for row in result["binding_candidates"]
        if row["evidence_tier"] == "E1_unique_structural"
    )
    assert e1["disposition"] == "conflict"
    assert e1["proposal_command"] is None
    assert "reconciliation_blocking_evidence" in e1["counterevidence"]
    _validate(result)


def test_attention_without_exact_resource_scope_cannot_false_green() -> None:
    project = _project()
    binding = {
        "binding_id": "binding-accepted-repo",
        "binding_kind": "repo",
        "ref": str(project["project_id"]),
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    cockpit["unknowns"] = []
    for item in [*cockpit["attention_queue"], *cockpit["today"]]:
        item["resource_ids"] = []

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["summary"]["fully_reconciled"] is False
    assert any(row["kind"] == "attention_scope_missing" for row in result["blockers"])
    assert result["summary"]["proposal_ready_count"] == 0
    _validate(result)


def test_ghost_attention_assignment_cannot_make_fully_reconciled_true() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    cockpit["unknowns"] = []
    for item in [*cockpit["attention_queue"], *cockpit["today"]]:
        item["workstream_id"] = "ghost"

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["summary"]["fully_reconciled"] is False
    assert any(row["kind"] == "attention_workstream_missing" for row in result["blockers"])
    assert result["summary"]["proposal_ready_count"] == 0
    assert all(row["proposal_command"] is None for row in result["binding_candidates"])
    _validate(result)


def test_unknown_evidence_suppresses_structural_proposal_commands() -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=[binding])])
    cockpit["unknowns"].append(
        {
            "source": "git",
            "kind": "scan_error",
            "ref": "opaque-local-ref",
            "note": "Local scan coverage is incomplete.",
            "severity": "danger",
        }
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert result["summary"]["blocking_evidence_count"] >= 1
    assert result["summary"]["proposal_ready_count"] == 0
    e1 = next(
        row
        for row in result["binding_candidates"]
        if row["evidence_tier"] == "E1_unique_structural"
    )
    assert e1["disposition"] == "conflict"
    assert e1["proposal_command"] is None
    assert "reconciliation_blocking_evidence" in e1["counterevidence"]
    _validate(result)


def test_multiple_accepted_owners_are_a_reconciliation_blocker() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    binding = {
        "binding_id": "binding-accepted-a",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "accepted",
    }
    cockpit = _cockpit(
        project=project,
        pairs=[
            _workstream("ws-a", bindings=[binding]),
            _workstream(
                "ws-b",
                bindings=[{**binding, "binding_id": "binding-accepted-b"}],
            ),
        ],
    )

    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    assert any(
        row["kind"] == "multiple_accepted_workstream_owners"
        for row in result["blockers"]
    )
    assert result["summary"]["fully_reconciled"] is False


def test_ambiguity_is_detected_before_display_truncation() -> None:
    project = _project(branch="feature/portfolio-one")
    second_branch = deepcopy(project["branches"][0])
    second_branch.update(
        {
            "name": "feature/portfolio-two",
            "worktree_path": "C:/private/second-worktree",
        }
    )
    second_worktree = deepcopy(project["worktrees"][0])
    second_worktree.update(
        {
            "path": "C:/private/second-worktree",
            "branch": "feature/portfolio-two",
        }
    )
    project["branches"].append(second_branch)
    project["worktrees"].append(second_worktree)
    bindings = []
    for index, worktree in enumerate(project["worktrees"]):
        bindings.append(
            {
                "binding_id": f"accepted-worktree-{index}",
                "binding_kind": "worktree",
                "ref": pc.worktree_resource_id(
                    str(project["project_id"]), str(worktree["path"])
                ),
                "assertion_status": "accepted",
            }
        )
    cockpit = _cockpit(
        project=project,
        pairs=[_workstream(label="portfolio one two", bindings=bindings)],
    )

    result = pr.build_portfolio_reconciliation(
        cockpit,
        now=NOW,
        settings=pr.ReconciliationSettings(candidate_limit=1),
        schema_root=ROOT,
    )

    assert result["workstream_cards"][0]["truncated_candidate_count"] >= 1
    assert len(result["binding_candidates"]) == 1
    assert result["binding_candidates"][0]["disposition"] == "ambiguous"
    assert result["binding_candidates"][0]["proposal_command"] is None


def test_nested_set_like_resource_links_do_not_churn_source_hash() -> None:
    project = _project()
    cockpit = _cockpit(project=project, pairs=[_workstream()])
    repo = next(
        row for row in cockpit["resources"] if row["resource_kind"] == "repo"
    )
    assert len(repo["linked_resource_ids"]) >= 2
    reversed_cockpit = deepcopy(cockpit)
    reversed_repo = next(
        row
        for row in reversed_cockpit["resources"]
        if row["resource_kind"] == "repo"
    )
    reversed_repo["linked_resource_ids"].reverse()

    first = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    second = pr.build_portfolio_reconciliation(
        reversed_cockpit, now=NOW, schema_root=ROOT
    )

    assert first["source_refs"] == second["source_refs"]
    assert first["source"]["source_hash"] == second["source"]["source_hash"]


def test_nested_unique_metadata_and_source_problems_do_not_churn_source_hash() -> None:
    cockpit = _cockpit(project=_project(), pairs=[_workstream()])
    cockpit["projects"][0]["related_projects"] = [
        {
            "project_id": "related-project",
            "name": "Related",
            "relationship_type": "related",
            "score": 0.5,
            "shared_metadata_tokens": ["beta", "alpha"],
            "status": "candidate",
        }
    ]
    cockpit["sources"]["git"]["problems"] = ["zeta", "alpha"]
    reversed_cockpit = deepcopy(cockpit)
    reversed_cockpit["projects"][0]["related_projects"][0][
        "shared_metadata_tokens"
    ].reverse()
    reversed_cockpit["sources"]["git"]["problems"].reverse()

    first = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    second = pr.build_portfolio_reconciliation(
        reversed_cockpit, now=NOW, schema_root=ROOT
    )

    assert first["source_refs"] == second["source_refs"]
    assert first["source"]["source_hash"] == second["source"]["source_hash"]


def test_set_like_source_collections_do_not_churn_source_hash() -> None:
    cockpit = _cockpit(project=_project(), pairs=[_workstream()])
    cockpit["unknowns"].extend(
        [
            {
                "source": "git",
                "kind": "zeta",
                "ref": "z",
                "note": "z",
                "severity": "warning",
            },
            {
                "source": "git",
                "kind": "alpha",
                "ref": "a",
                "note": "a",
                "severity": "warning",
            },
        ]
    )
    shuffled = deepcopy(cockpit)
    shuffled["projects"].reverse()
    shuffled["coverage"].reverse()
    shuffled["unknowns"].reverse()

    first = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    second = pr.build_portfolio_reconciliation(shuffled, now=NOW, schema_root=ROOT)

    assert first["source_refs"] == second["source_refs"]
    assert first["unknowns"] == second["unknowns"]


def test_html_escapes_labels_hides_paths_and_has_no_active_controls() -> None:
    project = _project(name="<script>alert(1)</script>")
    cockpit = _cockpit(
        project=project,
        pairs=[_workstream(label="<img src=x onerror=alert(2)> portfolio organizer")],
    )
    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)

    html = pr.portfolio_reconciliation_html(result)
    decoded = unescape(html)

    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror=alert(2)>" not in html
    assert "C:/private/never-render-this-path" not in decoded
    assert "<form" not in html.casefold()
    assert "<script" not in html.casefold()
    assert "<iframe" not in html.casefold()
    assert "<object" not in html.casefold()
    assert "http://" not in html.casefold()
    assert "https://" not in html.casefold()
    assert "script-src 'none'" in decoded
    assert "form-action 'none'" in decoded
    assert 'href="#main"' in html
    assert "<caption>" in html
    assert 'scope="col"' in html


@pytest.mark.parametrize(
    "mutation",
    [
        lambda card: card.update({"accepted_resource_ids": []}),
        lambda card: card.update({"accepted_resource_ids": ["dad:ghost"]}),
        lambda card: card.update({"workstream_id": "ws-redirected"}),
    ],
)
def test_semantic_validator_rejects_workstream_card_tampering(mutation) -> None:
    project = _project()
    branch_id = pc.branch_resource_id(
        str(project["project_id"]), "feature/portfolio-organizer"
    )
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    bindings = [
        {
            "binding_id": "accepted-branch",
            "binding_kind": "branch",
            "ref": branch_id,
            "assertion_status": "accepted",
        },
        {
            "binding_id": "accepted-worktree",
            "binding_kind": "worktree",
            "ref": worktree_id,
            "assertion_status": "accepted",
        },
    ]
    cockpit = _cockpit(project=project, pairs=[_workstream(bindings=bindings)])
    cockpit["attention_queue"] = []
    cockpit["today"] = []
    result = pr.build_portfolio_reconciliation(cockpit, now=NOW, schema_root=ROOT)
    assert result["summary"]["fully_reconciled"] is True
    mutation(result["workstream_cards"][0])

    _validate_schema_only(result)
    problems = pr.portfolio_reconciliation_semantic_problems(result)
    assert {
        "workstream_card_identity_mismatch",
        "workstream_card_revision_mismatch",
        "summary_fully_reconciled_mismatch",
    } & set(problems)


@pytest.mark.parametrize("arg_index", [2, 4, 8])
def test_semantic_validator_rejects_redirected_candidate_command(arg_index: int) -> None:
    project = _project()
    worktree_id = pc.worktree_resource_id(
        str(project["project_id"]), str(project["worktrees"][0]["path"])
    )
    binding = {
        "binding_id": "binding-accepted-worktree",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=project, pairs=[_workstream(bindings=[binding])]),
        now=NOW,
        schema_root=ROOT,
    )
    candidate = next(row for row in result["binding_candidates"] if row["proposal_command"])
    candidate["proposal_command"]["args"][arg_index] = "redirected-but-shape-valid"

    _validate_schema_only(result)
    assert "candidate_command_target_mismatch" in (
        pr.portfolio_reconciliation_semantic_problems(result)
    )


@pytest.mark.parametrize(
    ("mutation", "expected_problem"),
    [
        (
            lambda value: value["source_refs"].update({"cockpit": "sha256:" + "0" * 64}),
            "source_hash_reference_mismatch",
        ),
        (
            lambda value: value["summary"].update(
                {"candidate_count": value["summary"]["candidate_count"] + 1}
            ),
            "summary_candidate_count_mismatch",
        ),
        (
            lambda value: value["binding_candidates"][0].update(
                {"revision_id": "tampered-revision"}
            ),
            "candidate_revision_identity_mismatch",
        ),
    ],
)
def test_semantic_validator_rejects_shape_valid_cross_field_tampering(
    mutation, expected_problem: str
) -> None:
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=_project(), pairs=[_workstream()]),
        now=NOW,
        schema_root=ROOT,
    )
    mutation(result)

    _validate_schema_only(result)
    assert expected_problem in pr.portfolio_reconciliation_semantic_problems(result)


def test_output_is_validated_and_publishes_html_before_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "registry").mkdir()
    (tmp_path / "schemas").mkdir()
    shutil.copy2(
        ROOT / "registry" / "schema-registry.json",
        tmp_path / "registry" / "schema-registry.json",
    )
    shutil.copy2(
        ROOT / "schemas" / "portfolio-reconciliation.schema.json",
        tmp_path / "schemas" / "portfolio-reconciliation.schema.json",
    )
    result = pr.build_portfolio_reconciliation(
        _cockpit(project=_project(), pairs=[_workstream()]),
        now=NOW,
        schema_root=ROOT,
    )
    writes: list[str] = []

    def record(path: Path, _text: str) -> None:
        writes.append(path.name)

    monkeypatch.setattr(pr, "atomic_write_text", record)
    packet = pr.write_portfolio_reconciliation_outputs(tmp_path, result)

    assert writes == ["reconciliation.html", "reconciliation.json"]
    assert packet["summary"] == result["summary"]

    invalid = deepcopy(result)
    invalid["execution_authorized"] = True
    with pytest.raises(ValueError, match="Invalid portfolio reconciliation"):
        pr.write_portfolio_reconciliation_outputs(tmp_path, invalid)
