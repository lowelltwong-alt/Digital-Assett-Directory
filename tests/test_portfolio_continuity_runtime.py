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
    activation_sentinel = {"status": "trial_incomplete"}
    approvals_sentinel = [{"approval_event_id": "approval:sentinel"}]
    adapter_digest = "sha256:" + "a" * 64
    captured_attention: dict = {}
    original_build_projection = runtime.build_continuity_projection

    def _capture_attention(**kwargs):
        captured_attention.update(
            {
                "activation_state": kwargs["activation_state"],
                "stage_approvals": kwargs["stage_approvals"],
                "adapter_interface_digest": kwargs["adapter_interface_digest"],
            }
        )
        kwargs["activation_state"] = None
        kwargs["stage_approvals"] = None
        kwargs["adapter_interface_digest"] = ""
        return original_build_projection(**kwargs)

    monkeypatch.setattr(runtime, "build_continuity_projection", _capture_attention)
    monkeypatch.setattr(
        runtime,
        "derive_attention_stage_context",
        lambda *_a, **_k: (
            activation_sentinel,
            approvals_sentinel,
            adapter_digest,
            [],
        ),
    )
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
    assert captured_attention == {
        "activation_state": activation_sentinel,
        "stage_approvals": approvals_sentinel,
        "adapter_interface_digest": adapter_digest,
    }


def test_live_runtime_populates_duplicate_and_terminal_closeout_queues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plans = [
        {
            "plan_id": "plan:hybrid-a",
            "revision_id": "revision:a",
            "title": "Hybrid Azure local model architecture",
            "aliases": [],
            "outcome": "Provider agnostic hybrid Azure local model architecture",
            "privacy_class": "private",
            "lifecycle": "decision_complete",
            "implementation_state": "partial",
            "recorded_at": "2026-07-16T00:00:00Z",
            "smallest_next_action": "compare adapters",
            "acceptance_evidence": ["architecture harness"],
            "workstream_refs": [],
            "entity_refs": [],
        },
        {
            "plan_id": "plan:hybrid-b",
            "revision_id": "revision:b",
            "title": "Hybrid Azure local model architecture",
            "aliases": [],
            "outcome": "Provider agnostic hybrid Azure local model architecture",
            "privacy_class": "private",
            "lifecycle": "withdrawn",
            "implementation_state": "superseded",
            "recorded_at": "2026-07-16T00:00:00Z",
            "smallest_next_action": "",
            "acceptance_evidence": [],
            "workstream_refs": [],
            "entity_refs": [],
        },
    ]
    monkeypatch.setattr(runtime, "build_continuity_inventory", lambda *_a, **_k: _inventory())
    monkeypatch.setattr(runtime, "fold_plan_index", lambda _events: {"plans": plans})
    monkeypatch.setattr(runtime, "read_plan_events", lambda _hub: [])
    monkeypatch.setattr(runtime, "read_roadmap_events", lambda _hub: [])
    monkeypatch.setattr(runtime, "fold_roadmap", lambda _events: {"items": []})
    monkeypatch.setattr(runtime, "load_workstream_state", lambda _hub: {"workstreams": []})
    monkeypatch.setattr(runtime, "read_entity_events", lambda _hub: [])
    monkeypatch.setattr(runtime, "fold_entity_state", lambda _events: {"entities": []})
    monkeypatch.setattr(runtime, "continuity_ledger_path", lambda _hub: tmp_path / "missing.jsonl")
    monkeypatch.setattr(runtime, "read_observation_events", lambda _ledger: [])
    monkeypatch.setattr(runtime, "read_codex_hook_failures", lambda _hub: [])
    monkeypatch.setattr(runtime, "resolve_data_root", lambda _hub: (tmp_path, "legacy"))

    projection = runtime.build_current_projection(tmp_path, repo_roots=[tmp_path])

    duplicate = projection["queues"]["possible_duplicates"][0]
    assert duplicate["candidate_ids"] == ["plan:hybrid-a", "plan:hybrid-b"]
    assert duplicate["primary_candidate_id"] == ""
    assert projection["queues"]["task_archive"][0]["plan_id"] == "plan:hybrid-b"
    assert projection["queues"]["task_archive"][0]["action_executed"] is False
    assert projection["queues"]["worktree_close"][0]["action_executed"] is False


def test_automatic_duplicate_scan_is_bounded_and_reports_partial_coverage() -> None:
    plans = [
        {
            "plan_id": f"plan:{index:03d}",
            "title": f"Distinct capability {index}",
            "aliases": [],
            "outcome": f"Outcome {index}",
        }
        for index in range(runtime.MAX_AUTOMATIC_DUPLICATE_PLANS + 1)
    ]
    results, gaps = runtime.derive_plan_duplicate_search_results(plans)

    assert results == []
    assert gaps == ["automatic_plan_duplicate_scan_truncated"]


def test_previous_weekly_fingerprint_history_is_read_from_derived_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "resolve_data_root", lambda _hub: (tmp_path, "data_root"))
    report = tmp_path / "portfolio_reports" / "continuity" / "global-graph.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "attention_readiness": {
                    "weekly_digest_preview": {
                        "asks": [{"fingerprint": "sha256:" + "a" * 64}]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime, "data_path", lambda _hub, name: tmp_path / name)

    fingerprints, gaps = runtime.read_previous_weekly_fingerprints(tmp_path)

    assert fingerprints == ["sha256:" + "a" * 64]
    assert gaps == []


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
        "trial-readiness",
        "stage-status",
        "stage-approval",
        "activation-check",
    ):
        assert command in result.stdout


def test_trial_review_cli_blocks_before_files_or_append_without_ready_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "require_initialized_private_data_root", lambda _hub: None)
    monkeypatch.setattr(cli, "latest_host_readiness_assessment", lambda *_a: None)
    append_attempted = False

    def _unexpected_append(*_args, **_kwargs):
        nonlocal append_attempted
        append_attempted = True
        raise AssertionError("trial review append must not run")

    monkeypatch.setattr(cli, "record_production_trial_review", _unexpected_append)
    result = CliRunner().invoke(
        cli.app,
        [
            "os",
            "continuity",
            "trial-review",
            "--trial-id",
            "trial:future",
            "--reviewer-id",
            "human:fixture",
            "--snapshot-digest",
            "sha256:" + "a" * 64,
            "--metrics-file",
            "missing-metrics.json",
            "--performance-evidence",
            "missing-performance.json",
            "--supervisor-attestation-id",
            "attestation:fixture",
        ],
    )

    assert result.exit_code != 0
    assert "requires a current recorded" in result.output
    assert "host-readiness assessment" in result.output
    assert append_attempted is False


def test_stage_approval_cli_blocks_write_until_predecessor_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli,
        "_continuity_stage_context",
        lambda *_a, **_k: ({}, "sha256:" + "a" * 64, []),
    )
    monkeypatch.setattr(
        cli,
        "fold_stage_activation",
        lambda *_a, **_k: {
            "eligibility_state_digest": "sha256:" + "b" * 64,
            "stages": [
                {
                    "stage_id": "supervised_silent_shadow",
                    "activation_authorized": False,
                    "approval_event_id": "",
                }
            ],
        },
    )
    append_attempted = False

    def _unexpected_append(*_args, **_kwargs):
        nonlocal append_attempted
        append_attempted = True
        raise AssertionError("stage approval append must not run")

    monkeypatch.setattr(cli, "record_stage_approval", _unexpected_append)
    result = CliRunner().invoke(
        cli.app,
        [
            "os",
            "continuity",
            "stage-approval",
            "--trial-id",
            "trial:future",
            "--stage-id",
            "session_start_summary",
            "--decision",
            "approve",
            "--approved-by",
            "human:fixture",
            "--approval-ref",
            "approval:fixture",
            "--valid-until",
            "2026-08-01T00:00:00+00:00",
            "--rollback-criterion",
            "latency_budget_exceeded",
            "--kill-criterion",
            "unauthorized_mutation_observed",
        ],
    )

    assert result.exit_code != 0
    assert "stage approval blocked because the predecessor stage" in result.output
    assert "active" in result.output
    assert append_attempted is False
