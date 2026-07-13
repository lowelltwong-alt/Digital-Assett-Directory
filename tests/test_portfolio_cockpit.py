"""Adversarial tests for the unified DAD Portfolio Cockpit projection."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from html import unescape
import json
from pathlib import Path
import random
import shutil
from types import SimpleNamespace

import pytest
from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from typer.testing import CliRunner

from digital_asset_directory import portfolio_cockpit as pc
from digital_asset_directory import cli


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


def _board() -> dict[str, list[dict[str, str]]]:
    return {state: [] for state in STATES}


def _git(
    *,
    projects: list[dict[str, object]] | None = None,
    attention: list[dict[str, object]] | None = None,
    generated_at: datetime = NOW,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    project_rows = projects or []
    attention_rows = attention or []
    return {
        "schema_version": "dad.portfolio_attention.v1",
        "generated_at": generated_at.isoformat(),
        "status": "generated_candidate",
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "scan": {
            "roots": [],
            "stale_days": 3,
            "max_depth": 5,
            "related_limit": 3,
            "discovered_checkout_count": len(project_rows),
            "errors": errors or [],
        },
        "summary": {
            "project_count": len(project_rows),
            "branch_count": sum(len(row["branches"]) for row in project_rows),
            "worktree_count": sum(len(row["worktrees"]) for row in project_rows),
            "dirty_worktree_count": sum(
                int(worktree["dirty"] is True)
                for row in project_rows
                for worktree in row["worktrees"]
            ),
            "attention_item_count": len(attention_rows),
            "today_item_count": min(3, len(attention_rows)),
        },
        "today": attention_rows[:3],
        "projects": project_rows,
        "attention_queue": attention_rows,
        "authority_boundary": "Read-only candidate evidence with no execution authority.",
    }


def _workstream(
    workstream_id: str,
    *,
    label: str = "creative operating system",
    state: str = "active",
    priority: int = 70,
    trigger_kind: str = "weekly_decision",
    inactive_days: int = 9,
    bindings: list[dict[str, object]] | None = None,
    needs_decision: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    normalized_bindings = [
        {
            "binding_id": str(binding.get("binding_id", "")),
            "binding_kind": str(binding.get("binding_kind", "")),
            "ref": str(binding.get("ref", "")),
            "label": "",
            "assertion_status": str(binding.get("assertion_status", "proposed")),
            "asserted_by": "test",
            "approval_ref": "",
            "recorded_at": NOW.isoformat(),
        }
        for binding in (bindings or [])
    ]
    row = {
        "workstream_id": workstream_id,
        "idea_id": f"idea:{workstream_id}",
        "idea_text": label,
        "proposal_kind": "new_independent_workstream",
        "recommended_action": "review",
        "needs_human_decision": needs_decision,
        "divergence": False,
        "relations": [],
        "proposed_at": NOW.isoformat(),
        "lifecycle_state": state,
        "state_since": NOW.isoformat(),
        "snooze_until": "",
        "review_at": "",
        "capsule": None,
        "dismissal_epoch": 0,
        "decision_rejected_at": "",
        "conflict_resolved": False,
        "bindings": normalized_bindings,
        "dismiss_count": 0,
        "last_activity_at": NOW.isoformat(),
        "inactive_days": inactive_days,
    }
    focus = {
        "workstream_id": workstream_id,
        "idea_text": label,
        "proposal_kind": "new_independent_workstream",
        "lifecycle_state": state,
        "priority": priority,
        "trigger_kind": trigger_kind,
        "trigger_signature": f"signature:{workstream_id}",
        "tier": "weekly",
        "inactive_days": inactive_days,
        "reasons": [f"reason:{workstream_id}"] if priority else [],
        "suppressed_reasons": ["intentional"] if not priority else [],
        "next_action": "",
        "last_activity_at": NOW.isoformat(),
    }
    return row, focus


def _state(
    pairs: list[tuple[dict[str, object], dict[str, object]]] | None = None,
    *,
    dependencies: dict[str, object] | None = None,
    generated_at: datetime = NOW,
    coverage: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    pairs = pairs or []
    workstreams = [pair[0] for pair in pairs]
    focus = [pair[1] for pair in pairs]
    board = _board()
    for row in workstreams:
        board[str(row["lifecycle_state"])].append(
            {
                "workstream_id": str(row["workstream_id"]),
                "idea_text": str(row["idea_text"]),
            }
        )
    surfaced = [row for row in focus if int(row["priority"]) > 0]
    return {
        "schema_version": "dad.portfolio_workstreams.v1",
        "generated_at": generated_at.isoformat(),
        "status": "generated_candidate",
        "data_classification": "local_private_metadata",
        "public_safe": False,
        "authority_boundary": "Local candidate projection with no execution authority.",
        "summary": {
            "project_count": 0,
            "idea_count": len(workstreams),
            "conversation_count": 0,
            "workstream_count": len(workstreams),
            "open_workstream_count": len(workstreams),
            "relation_count": 0,
            "focus_item_count": len(surfaced),
            "today_item_count": min(3, len(surfaced)),
            "suppressed_workstream_count": len(focus) - len(surfaced),
            "bottleneck_count": len((dependencies or {}).get("bottlenecks", [])),
            "sprawl_cluster_count": 0,
        },
        "conversations": [],
        "projects": [],
        "ideas": [],
        "workstreams": workstreams,
        "today": surfaced[:3],
        "focus_queue": focus,
        "coverage": coverage or [],
        "ledger_diagnostics": {
            "corrupt_line_count": 0,
            "invalid_envelope_count": 0,
            "torn_tail_pending": False,
            "problems": [],
            "fold_problems": [],
        },
        "dependencies": dependencies
        or {
            "per_workstream": {},
            "bottlenecks": [],
            "invalid_assertions": [],
            "cycle_nodes": [],
        },
        "board": board,
        "sprawl_clusters": [],
        "relationship_class_stats": {},
        "portfolio_snapshot": {
            "status": "unavailable",
            "as_of": "",
            "source_hash": "",
        },
    }


def _project(
    *,
    project_id: str = "dad:portfolio-project:test",
    name: str = "DAD",
    branch: str = "feature/cockpit",
    path: str = "C:/work/dad-cockpit",
    dirty: bool | None = True,
    status_known: bool = True,
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
                "subject": "test",
                "upstream": "",
                "upstream_gone": False,
                "ahead": 0,
                "behind": 0,
                "project_id": project_id,
                "project_name": name,
                "worktree_path": path,
                "dirty": dirty,
                "status_unknown": not status_known,
                "status_error": "",
                "worktree_locked": False,
                "conflicted": False,
                "changed_path_count": int(dirty is True),
                "last_activity_at": NOW.isoformat(),
                "inactive_days": 0,
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
                "status_known": status_known,
                "dirty": dirty,
                "change_counts": {
                    "staged": 0,
                    "unstaged": int(dirty is True),
                    "untracked": 0,
                    "conflicted": 0,
                },
                "changed_path_count": int(dirty is True),
                "latest_dirty_activity_at": NOW.isoformat() if dirty else "",
                "status_error": "",
            }
        ],
        "related_projects": [],
    }


def _git_attention(
    *,
    project_id: str = "dad:portfolio-project:test",
    project_name: str = "DAD",
    branch: str = "feature/cockpit",
    path: str = "C:/work/dad-cockpit",
    priority: int = 95,
    reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "priority": priority,
        "project_id": project_id,
        "project_name": project_name,
        "branch": branch,
        "worktree_path": path,
        "last_activity_at": NOW.isoformat(),
        "inactive_days": 8,
        "reasons": reasons or ["dirty_worktree_idle"],
        "next_action": "Review the diff and choose a state.",
        "evidence": {
            "dirty": True,
            "changed_path_count": 3,
            "ahead": 0,
            "behind": 0,
            "merged_by_ancestry": False,
            "upstream": "",
            "worktree_locked": False,
        },
    }


def _validate(value: dict[str, object]) -> None:
    schema = json.loads(
        (ROOT / "schemas" / "portfolio-cockpit.schema.json").read_text(encoding="utf-8")
    )
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema, format_checker=FormatChecker()).validate(value)


def _install_cockpit_schemas(hub_root: Path) -> None:
    schema_dir = hub_root / "schemas"
    schema_dir.mkdir()
    registry_dir = hub_root / "registry"
    registry_dir.mkdir()
    shutil.copy2(
        ROOT / "registry" / "schema-registry.json",
        registry_dir / "schema-registry.json",
    )
    for name in (
        "portfolio-attention-report.schema.json",
        "portfolio-workstream-state.schema.json",
        "portfolio-cockpit.schema.json",
        "portfolio-reconciliation.schema.json",
        "portfolio-workstream-shaping.schema.json",
        "portfolio-review-packet.schema.json",
    ):
        shutil.copy2(ROOT / "schemas" / name, schema_dir / name)


def test_missing_source_never_becomes_false_green() -> None:
    result = pc.build_portfolio_cockpit(None, _state(), now=NOW)

    _validate(result)
    assert result["status"] == "partial_candidate"
    assert result["summary"]["all_clear"] is False
    assert any(row["kind"] == "source_unavailable" for row in result["unknowns"])
    assert result["today"][0]["band"] == "integrity_unknown"


def test_global_today_is_bounded_deterministic_and_inputs_are_immutable() -> None:
    pairs = [
        _workstream(
            "ws-human",
            label="human choice",
            priority=50,
            trigger_kind="conflict_decision",
            needs_decision=True,
        ),
        _workstream("ws-unlock", label="unlock", priority=90),
        _workstream("ws-weekly", label="weekly", priority=100),
        _workstream("ws-more", label="more", priority=99),
    ]
    dependencies = {
        "per_workstream": {
            "ws-unlock": {
                "blocking_count": 4,
                "blocks_directly": ["ws-weekly"],
                "blocked_by": [],
            }
        },
        "bottlenecks": [
            {
                "workstream_id": "ws-unlock",
                "blocking_count": 4,
                "blocks_directly": ["ws-weekly"],
            }
        ],
        "invalid_assertions": [],
        "cycle_nodes": [],
    }
    git_report = _git()
    state = _state(pairs, dependencies=dependencies)
    before_git, before_state = deepcopy(git_report), deepcopy(state)

    first = pc.build_portfolio_cockpit(git_report, state, now=NOW)
    shuffled = deepcopy(pairs)
    random.Random(19).shuffle(shuffled)
    second = pc.build_portfolio_cockpit(
        _git(), _state(shuffled, dependencies=deepcopy(dependencies)), now=NOW
    )

    assert len(first["today"]) == 3
    assert [item["attention_id"] for item in first["today"]] == [
        item["attention_id"] for item in second["today"]
    ]
    assert first["today"][0]["workstream_id"] == "ws-human"
    assert first["today"][1]["workstream_id"] == "ws-unlock"
    assert git_report == before_git
    assert state == before_state
    _validate(first)


def test_only_exact_accepted_resource_binding_joins_attention() -> None:
    project = _project()
    project_id = str(project["project_id"])
    branch_id = pc.branch_resource_id(project_id, "feature/cockpit")
    worktree_id = pc.worktree_resource_id(project_id, str(project["worktrees"][0]["path"]))
    accepted = {
        "binding_id": "binding-accepted",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "accepted",
    }
    accepted_worktree = {
        "binding_id": "binding-accepted-worktree",
        "binding_kind": "worktree",
        "ref": worktree_id,
        "assertion_status": "accepted",
    }
    proposed = {
        "binding_id": "binding-proposed",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "proposed",
    }
    unresolved = {
        "binding_id": "binding-legacy",
        "binding_kind": "branch",
        "ref": "feature/cockpit",
        "assertion_status": "accepted",
    }
    pairs = [
        _workstream("ws-accepted", bindings=[accepted, accepted_worktree]),
        _workstream("ws-proposed", priority=0, bindings=[proposed]),
        _workstream("ws-legacy", priority=0, bindings=[unresolved]),
    ]
    result = pc.build_portfolio_cockpit(
        _git(projects=[project], attention=[_git_attention()]),
        _state(pairs),
        now=NOW,
    )

    joined = [item for item in result["attention_queue"] if item["source"] == "joined"]
    assert len(joined) == 1
    assert joined[0]["workstream_id"] == "ws-accepted"
    assert {row["resolution"] for row in result["bindings"]} == {
        "accepted_exact",
        "proposed_exact",
        "accepted_unresolved",
    }
    assert any(row["kind"] == "accepted_binding_unresolved" for row in result["unknowns"])
    _validate(result)


def test_repo_binding_is_context_only_for_git_attention() -> None:
    project = _project()
    repo_binding = {
        "binding_id": "binding-repo",
        "binding_kind": "repo",
        "ref": str(project["project_id"]),
        "assertion_status": "accepted",
    }
    result = pc.build_portfolio_cockpit(
        _git(projects=[project], attention=[_git_attention()]),
        _state([_workstream("ws-repo", bindings=[repo_binding])]),
        now=NOW,
    )
    git_items = [
        item
        for item in result["attention_queue"]
        if item["source"] == "git" and item["project_id"] == project["project_id"]
    ]

    assert len(git_items) == 1
    assert git_items[0]["workstream_id"] == ""
    assert any(row["kind"] == "unassigned_observed_attention" for row in result["coverage"])
    _validate(result)


def test_paused_repo_binding_cannot_hide_branch_attention() -> None:
    project = _project()
    repo_binding = {
        "binding_id": "binding-repo-paused",
        "binding_kind": "repo",
        "ref": str(project["project_id"]),
        "assertion_status": "accepted",
    }
    paused = _workstream(
        "ws-repo-paused",
        state="paused",
        priority=0,
        bindings=[repo_binding],
    )
    result = pc.build_portfolio_cockpit(
        _git(projects=[project], attention=[_git_attention()]),
        _state([paused]),
        now=NOW,
    )

    assert any(
        item["source"] == "git" and item["workstream_id"] == ""
        for item in result["attention_queue"]
    )
    assert any(row["workstream_id"] == "ws-repo-paused" for row in result["lanes"]["quiet_work"])
    _validate(result)


def test_branch_without_worktree_is_not_unknown_dirty() -> None:
    project = _project()
    project["worktrees"] = []
    branch_row = dict(project["branches"][0])
    branch_row.update(
        {
            "name": "old-idea",
            "worktree_path": "",
            "dirty": None,
            "status_unknown": False,
            "changed_path_count": 0,
        }
    )
    project["branches"] = [branch_row]
    attention = _git_attention(
        branch="old-idea",
        path="",
        priority=55,
        reasons=["stale_branch"],
    )
    attention["evidence"]["dirty"] = None

    result = pc.build_portfolio_cockpit(
        _git(projects=[project], attention=[attention]), _state(), now=NOW
    )

    assert not any(row["kind"] == "worktree_status_unknown" for row in result["unknowns"])
    git_item = next(item for item in result["attention_queue"] if item["source"] == "git")
    assert git_item["band"] == "weekly_maintenance"


def test_unknown_worktree_and_dependency_cycle_are_explicit() -> None:
    cycle_pair = _workstream("ws-cycle", priority=90)
    valid_pair = _workstream("ws-valid", priority=80)
    dependencies = {
        "per_workstream": {},
        "bottlenecks": [
            {
                "workstream_id": "ws-cycle",
                "blocking_count": 5,
                "blocks_directly": ["ws-valid"],
            },
            {
                "workstream_id": "ws-valid",
                "blocking_count": 1,
                "blocks_directly": ["ws-cycle"],
            },
        ],
        "invalid_assertions": [
            {
                "kind": "dependency_cycle",
                "source": "ws-cycle",
                "target": "",
            }
        ],
        "cycle_nodes": ["ws-cycle"],
    }
    project = _project(dirty=None, status_known=False)
    result = pc.build_portfolio_cockpit(
        _git(projects=[project], attention=[]),
        _state([cycle_pair, valid_pair], dependencies=dependencies),
        now=NOW,
    )

    assert {row["workstream_id"] for row in result["lanes"]["unlock_frontier"]} == {"ws-valid"}
    assert {row["kind"] for row in result["unknowns"]} >= {
        "worktree_status_unknown",
        "dependency_cycle",
    }
    assert result["summary"]["all_clear"] is False
    _validate(result)


def test_stale_source_is_visible_and_blocks_all_clear() -> None:
    stale = NOW - timedelta(hours=30)
    result = pc.build_portfolio_cockpit(
        _git(generated_at=stale), _state(generated_at=stale), now=NOW
    )

    assert result["status"] == "partial_candidate"
    assert result["summary"]["all_clear"] is False
    assert all(source["freshness"] == "stale" for source in result["sources"].values())
    assert sum(row["kind"] == "source_stale" for row in result["unknowns"]) == 2


def test_html_is_script_free_escaped_accessible_and_hash_bound() -> None:
    malicious = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    project = _project(name=malicious)
    result = pc.build_portfolio_cockpit(
        _git(
            projects=[project],
            attention=[_git_attention(project_name=malicious)],
        ),
        _state(),
        now=NOW,
    )
    html = pc.portfolio_cockpit_html(result)
    digest = base64.b64encode(hashlib.sha256(pc._STYLE.encode("utf-8")).digest()).decode("ascii")

    assert malicious not in html
    assert "&lt;script&gt;" in html
    lowered = html.casefold()
    assert "<script" not in lowered
    assert "<form" not in lowered
    assert "<iframe" not in lowered
    assert "<object" not in lowered
    assert "http://" not in lowered and "https://" not in lowered
    assert f"sha256-{digest}" in unescape(html)
    assert 'href="#main"' in html
    assert "<caption>" in html
    assert 'scope="col"' in html
    _validate(result)


def test_cli_cockpit_and_refresh_write_unified_outputs(tmp_path, monkeypatch) -> None:
    _install_cockpit_schemas(tmp_path)
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    monkeypatch.setattr(
        cli,
        "_cfg",
        lambda *_args, **_kwargs: SimpleNamespace(
            repo_root=tmp_path,
            local_sources=[],
        ),
    )
    runner = CliRunner()

    cockpit_result = runner.invoke(cli.app, ["os", "cockpit", "--no-scan-portfolio"])
    assert cockpit_result.exit_code == 0, cockpit_result.output
    cockpit_path = tmp_path / "processed" / "reports" / "portfolio_os" / "cockpit.json"
    assert cockpit_path.exists()
    _validate(json.loads(cockpit_path.read_text(encoding="utf-8")))

    reconcile_result = runner.invoke(cli.app, ["os", "reconcile", "--no-scan-portfolio"])
    assert reconcile_result.exit_code == 0, reconcile_result.output
    reconciliation_path = (
        tmp_path / "processed" / "reports" / "portfolio_os" / "reconciliation.json"
    )
    assert reconciliation_path.exists()
    shaping_path = tmp_path / "processed" / "reports" / "portfolio_os" / "shaping.json"
    assert shaping_path.exists()
    shape_result = runner.invoke(cli.app, ["os", "shape", "--no-scan-portfolio"])
    assert shape_result.exit_code == 0, shape_result.output
    assert json.loads(shaping_path.read_text(encoding="utf-8"))["execution_authorized"] is False
    reconcile_help = runner.invoke(cli.app, ["os", "reconcile", "--help"])
    assert reconcile_help.exit_code == 0
    assert "--accept" not in reconcile_help.output
    assert "--apply" not in reconcile_help.output
    shape_help = runner.invoke(cli.app, ["os", "shape", "--help"])
    assert shape_help.exit_code == 0
    assert "--accept" not in shape_help.output and "--apply" not in shape_help.output

    monkeypatch.setattr(
        cli,
        "_v1_attention_report",
        lambda _root: _git(
            projects=[_project()],
            attention=[_git_attention()],
        ),
    )
    refresh_result = runner.invoke(cli.app, ["os", "refresh", "--no-scan-portfolio"])
    assert refresh_result.exit_code == 0, refresh_result.output
    assert '"cockpit"' in refresh_result.output
    assert '"reconciliation"' in refresh_result.output
    assert '"shaping"' in refresh_result.output
    assert '"workstream_today_changed": false' in refresh_result.output
    assert '"today_changed": true' in refresh_result.output


def test_refresh_reconciliation_failure_does_not_consume_cockpit_cursor(
    tmp_path, monkeypatch
) -> None:
    _install_cockpit_schemas(tmp_path)
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    monkeypatch.setattr(
        cli,
        "_cfg",
        lambda *_args, **_kwargs: SimpleNamespace(
            repo_root=tmp_path,
            local_sources=[],
        ),
    )
    previous = pc.build_portfolio_cockpit(_git(), _state(), now=NOW)
    packet = pc.write_portfolio_cockpit_outputs(tmp_path, previous)
    cockpit_path = Path(packet["json_path"])
    previous_json = cockpit_path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_v1_attention_report",
        lambda _root: _git(
            projects=[_project()],
            attention=[_git_attention()],
        ),
    )

    def fail_reconciliation(*_args, **_kwargs):
        raise PermissionError("simulated reconciliation publication failure")

    monkeypatch.setattr(
        cli,
        "write_portfolio_reconciliation_outputs",
        fail_reconciliation,
    )
    result = CliRunner().invoke(cli.app, ["os", "refresh", "--no-scan-portfolio"])

    assert result.exit_code == 2
    assert "simulated reconciliation" in " ".join(result.output.split())
    assert "publication failure" in result.output
    assert cockpit_path.read_text(encoding="utf-8") == previous_json


def test_refresh_late_runtime_failure_rolls_back_all_projection_cursors(
    tmp_path, monkeypatch
) -> None:
    _install_cockpit_schemas(tmp_path)
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    monkeypatch.setattr(
        cli,
        "_cfg",
        lambda *_args, **_kwargs: SimpleNamespace(repo_root=tmp_path, local_sources=[]),
    )
    initial = CliRunner().invoke(cli.app, ["os", "reconcile", "--no-scan-portfolio"])
    assert initial.exit_code == 0, initial.output
    base = tmp_path / "processed" / "reports" / "portfolio_os"
    paths = [
        base / "cockpit.json",
        base / "cockpit.html",
        base / "reconciliation.json",
        base / "reconciliation.html",
        base / "shaping.json",
        base / "shaping.html",
    ]
    previous = {path: path.read_text(encoding="utf-8") for path in paths}

    def fail_cockpit(*_args, **_kwargs):
        raise RuntimeError("simulated late cockpit publication failure")

    monkeypatch.setattr(cli, "write_portfolio_cockpit_outputs", fail_cockpit)
    result = CliRunner().invoke(cli.app, ["os", "refresh", "--no-scan-portfolio"])

    assert result.exit_code == 2
    assert "simulated late cockpit" in " ".join(result.output.split())
    for path in paths:
        assert path.read_text(encoding="utf-8") == previous[path]


def test_cockpit_publication_failure_rolls_back_reconciliation_cursor(
    tmp_path, monkeypatch
) -> None:
    _install_cockpit_schemas(tmp_path)
    monkeypatch.delenv("DAD_DATA_ROOT", raising=False)
    monkeypatch.setattr(
        cli,
        "_cfg",
        lambda *_args, **_kwargs: SimpleNamespace(
            repo_root=tmp_path,
            local_sources=[],
        ),
    )
    runner = CliRunner()
    initial = runner.invoke(cli.app, ["os", "reconcile", "--no-scan-portfolio"])
    assert initial.exit_code == 0, initial.output
    base = tmp_path / "processed" / "reports" / "portfolio_os"
    cockpit_path = base / "cockpit.json"
    reconciliation_path = base / "reconciliation.json"
    previous_cockpit = cockpit_path.read_text(encoding="utf-8")
    previous_reconciliation = reconciliation_path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_v1_attention_report",
        lambda _root: _git(
            projects=[_project()],
            attention=[_git_attention()],
        ),
    )

    def fail_cockpit(*_args, **_kwargs):
        raise PermissionError("simulated cockpit publication failure")

    monkeypatch.setattr(cli, "write_portfolio_cockpit_outputs", fail_cockpit)
    result = runner.invoke(cli.app, ["os", "refresh", "--no-scan-portfolio"])

    assert result.exit_code == 2
    assert "simulated cockpit" in " ".join(result.output.split())
    assert "publication failure" in result.output
    assert cockpit_path.read_text(encoding="utf-8") == previous_cockpit
    assert reconciliation_path.read_text(encoding="utf-8") == previous_reconciliation


def test_structurally_invalid_sources_are_quarantined_and_never_clear() -> None:
    malformed_git = {
        "schema_version": "dad.portfolio_attention.v1",
        "generated_at": NOW.isoformat(),
        "projects": [_project()],
    }
    malformed_state = {
        "schema_version": "dad.portfolio_workstreams.v1",
        "generated_at": NOW.isoformat(),
        "focus_queue": [
            {
                "workstream_id": "ws-injected",
                "priority": 100,
                "trigger_kind": "conflict_decision",
            }
        ],
    }

    result = pc.build_portfolio_cockpit(malformed_git, malformed_state, now=NOW)

    assert result["sources"]["git"]["status"] == "invalid"
    assert result["sources"]["workstreams"]["status"] == "invalid"
    assert result["projects"] == []
    assert result["workstreams"] == []
    assert result["summary"]["all_clear"] is False
    assert all(item["workstream_id"] != "ws-injected" for item in result["attention_queue"])
    assert any(row["kind"] == "schema_validation_failed" for row in result["unknowns"])


def test_non_object_sources_fail_closed() -> None:
    result = pc.build_portfolio_cockpit([], [], now=NOW)  # type: ignore[arg-type]

    assert result["sources"]["git"]["status"] == "invalid"
    assert result["sources"]["workstreams"]["status"] == "invalid"
    assert result["summary"]["all_clear"] is False
    assert {row["kind"] for row in result["unknowns"]} == {"source_not_object"}


def test_invalid_version_cannot_control_today() -> None:
    pair = _workstream(
        "ws-injected",
        priority=100,
        trigger_kind="conflict_decision",
        needs_decision=True,
    )
    state = _state([pair])
    state["schema_version"] = "evil.v9"

    result = pc.build_portfolio_cockpit(_git(), state, now=NOW)

    assert result["sources"]["workstreams"]["status"] == "invalid"
    assert all(item["workstream_id"] != "ws-injected" for item in result["attention_queue"])
    assert result["summary"]["all_clear"] is False


def test_real_ledger_diagnostics_block_all_clear() -> None:
    state = _state()
    state["ledger_diagnostics"] = {
        "corrupt_line_count": 1,
        "invalid_envelope_count": 2,
        "torn_tail_pending": True,
        "problems": ["hash_chain_gap"],
        "fold_problems": [],
    }

    result = pc.build_portfolio_cockpit(_git(), state, now=NOW)

    kinds = {row["kind"] for row in result["unknowns"]}
    assert {
        "ledger_corrupt_line_count",
        "ledger_invalid_envelope_count",
        "ledger_torn_tail_pending",
        "ledger_integrity_problem",
    } <= kinds
    assert result["summary"]["all_clear"] is False


def test_quiet_workstream_cannot_reenter_today_through_git_join() -> None:
    project = _project()
    branch_id = pc.branch_resource_id(str(project["project_id"]), "feature/cockpit")
    binding = {
        "binding_id": "binding-quiet",
        "binding_kind": "branch",
        "ref": branch_id,
        "assertion_status": "accepted",
    }
    quiet = _workstream("ws-quiet", state="snoozed", priority=80, bindings=[binding])

    result = pc.build_portfolio_cockpit(
        _git(projects=[project], attention=[_git_attention()]),
        _state([quiet]),
        now=NOW,
    )

    assert all(item["workstream_id"] != "ws-quiet" for item in result["attention_queue"])
    assert any(row["workstream_id"] == "ws-quiet" for row in result["lanes"]["quiet_work"])


def test_duplicate_resource_identity_is_quarantined() -> None:
    project = _project()
    result = pc.build_portfolio_cockpit(
        _git(projects=[project, deepcopy(project)]),
        _state(),
        now=NOW,
    )

    assert result["projects"] == []
    assert any(row["kind"] == "duplicate_resource_identity" for row in result["unknowns"])
    assert result["summary"]["all_clear"] is False


def test_duplicate_workstream_identity_is_quarantined_everywhere() -> None:
    first = _workstream(
        "ws-dup",
        label="ambiguous A",
        priority=100,
        trigger_kind="conflict_decision",
        needs_decision=True,
    )
    second = _workstream(
        "ws-dup",
        label="ambiguous B",
        priority=99,
        trigger_kind="conflict_decision",
        needs_decision=True,
    )

    result = pc.build_portfolio_cockpit(_git(), _state([first, second]), now=NOW)

    assert result["workstreams"] == []
    assert all(item["workstream_id"] != "ws-dup" for item in result["attention_queue"])
    assert all(
        row["workstream_id"] != "ws-dup" for column in result["board"].values() for row in column
    )
    assert any(row["kind"] == "duplicate_workstream_identity" for row in result["unknowns"])


def test_html_failure_does_not_consume_today_change_edge(tmp_path, monkeypatch) -> None:
    _install_cockpit_schemas(tmp_path)
    previous = pc.build_portfolio_cockpit(_git(), _state(), now=NOW)
    changed = pc.build_portfolio_cockpit(
        _git(projects=[_project()], attention=[_git_attention()]),
        _state(),
        now=NOW,
    )
    first = pc.write_portfolio_cockpit_outputs(tmp_path, previous)
    assert first["today_changed"] is False
    json_path = Path(first["json_path"])
    previous_json = json_path.read_text(encoding="utf-8")

    real_atomic_write = pc.atomic_write_text

    def fail_html(path: Path, text: str) -> None:
        if path.suffix == ".html":
            raise PermissionError("simulated OneDrive HTML lock")
        real_atomic_write(path, text)

    monkeypatch.setattr(pc, "atomic_write_text", fail_html)
    with pytest.raises(PermissionError, match="OneDrive"):
        pc.write_portfolio_cockpit_outputs(tmp_path, changed)
    assert json_path.read_text(encoding="utf-8") == previous_json

    monkeypatch.setattr(pc, "atomic_write_text", real_atomic_write)
    retry = pc.write_portfolio_cockpit_outputs(tmp_path, changed)
    assert retry["today_changed"] is True


def test_path_identity_normalization_is_lexical(monkeypatch) -> None:
    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("Path.resolve must not be used for source resource identity")

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    first = pc.worktree_resource_id(
        "dad:portfolio-project:test", r"\\server\share\repo\tree\..\tree"
    )
    second = pc.worktree_resource_id("dad:portfolio-project:test", r"\\server\share\repo\tree")

    assert first == second


def test_fold_coverage_blocks_all_clear() -> None:
    result = pc.build_portfolio_cockpit(
        _git(),
        _state(coverage=[{"workstream_id": "ws-orphan", "note": "workstream without idea"}]),
        now=NOW,
    )

    assert result["summary"]["all_clear"] is False
    assert any(row["kind"] == "fold_coverage" for row in result["unknowns"])
    assert any(item["band"] == "integrity_unknown" for item in result["today"])
    _validate(result)
