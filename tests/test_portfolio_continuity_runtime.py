from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.validators import validator_for
from typer.testing import CliRunner

from digital_asset_directory import cli
from digital_asset_directory import portfolio_continuity_runtime as runtime


def _inventory() -> dict:
    return {
        "repository_id": "repo:one",
        "generated_at": "2026-07-16T00:00:00Z",
        "inventory_fingerprint": "sha256:" + "1" * 64,
        "objects": [],
        "worktrees": [],
        "codex_items": [],
        "coverage": {"gaps": [], "network_calls": 0, "git_writes": 0},
    }


def test_private_write_gate_fails_closed_on_legacy_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "resolve_data_root", lambda _hub: (tmp_path, "legacy"))
    with pytest.raises(runtime.ContinuityRuntimeError, match="initialized DAD_DATA_ROOT"):
        runtime.require_initialized_private_data_root(tmp_path)


def test_reconciliation_recovers_current_state_when_hook_events_were_missed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "build_continuity_inventory", lambda *_a, **_k: _inventory())
    monkeypatch.setattr(
        runtime,
        "fold_plan_index",
        lambda _events: {
            "plans": [
                {
                    "plan_id": "plan:one",
                    "revision_id": "revision:one",
                    "lifecycle": "decision_complete",
                    "implementation_state": "partial",
                    "recorded_at": "2026-07-16T00:00:00Z",
                    "smallest_next_action": "resume the bounded test",
                    "acceptance_evidence": ["test passes"],
                    "workstream_refs": [],
                    "entity_refs": [],
                }
            ]
        },
    )
    monkeypatch.setattr(runtime, "read_plan_events", lambda _hub: [])
    monkeypatch.setattr(runtime, "read_roadmap_events", lambda _hub: [])
    monkeypatch.setattr(runtime, "fold_roadmap", lambda _events: {"items": []})
    monkeypatch.setattr(runtime, "load_workstream_state", lambda _hub: {"workstreams": []})
    monkeypatch.setattr(runtime, "read_entity_events", lambda _hub: [])
    monkeypatch.setattr(runtime, "fold_entity_state", lambda _events: {"entities": []})
    monkeypatch.setattr(runtime, "continuity_ledger_path", lambda _hub: tmp_path / "missing.jsonl")
    monkeypatch.setattr(runtime, "read_observation_events", lambda _ledger: [])
    monkeypatch.setattr(runtime, "resolve_data_root", lambda _hub: (tmp_path, "data_root"))
    monkeypatch.setattr(
        runtime,
        "load_plan_revision",
        lambda *_a, **_k: {
            "semantic_card": {
                "project_refs": [],
                "workstream_refs": [],
                "entity_refs": [],
                "source_bindings": [],
            }
        },
    )

    projection = runtime.build_current_projection(tmp_path, repo_roots=[tmp_path])

    assert projection["queues"]["current_state"][0]["plan_id"] == "plan:one"
    assert projection["queues"]["next_actions"][0]["next_action"] == "resume the bounded test"
    assert projection["activity"] == []
    assert projection["coverage"]["status"] == "partial"
    assert "activity_duration_coverage_unknown" in projection["coverage"]["gaps"]


def test_supervised_shadow_config_enables_only_content_free_lifecycle_triggers() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "schemas" / "intent-continuity-shadow-hook-config.schema.json").read_text(
            encoding="utf-8"
        )
    )
    config = json.loads(
        (root / "config" / "intent-continuity-shadow-hooks.json").read_text(
            encoding="utf-8"
        )
    )
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator_class(schema).validate(config)
    assert config["status"] == "supervised_silent_shadow"
    enabled = {
        trigger["runtime_event"] for trigger in config["triggers"] if trigger["enabled"]
    }
    assert enabled == {"SessionStart", "PreCompact", "PostCompact", "Stop"}
    prompt = next(
        trigger for trigger in config["triggers"] if trigger["runtime_event"] == "UserPromptSubmit"
    )
    assert prompt["enabled"] is False
    assert config["activation_gate"]["recorded_host_readiness_required"] is True
    assert config["activation_gate"]["automatic_activation_allowed"] is False


def test_continuity_cli_surfaces_are_discoverable() -> None:
    result = CliRunner().invoke(cli.app, ["os", "continuity", "--help"])
    assert result.exit_code == 0
    for command in (
        "scan",
        "recover",
        "status",
        "reconcile",
        "observe",
        "host-readiness",
        "trial-review",
        "activation-check",
    ):
        assert command in result.stdout
