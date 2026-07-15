from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digital_asset_directory.autonomy_control import evaluate_authority, global_kill_candidate
from digital_asset_directory.harness_engineering import prepare_typed_command, run_typed_command, validate_command_spec
from digital_asset_directory.runtime_resolver import build_capability_snapshot, resolve_fallback, resolve_runtime


REPO = Path(__file__).resolve().parents[1]


def _registration(runtime_id: str, *, cost: float) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "registration_id": f"registration:{runtime_id}", "runtime_id": runtime_id,
        "adapter_id": "adapter:codex-host", "provider_id": f"provider:{runtime_id}", "runtime_label": runtime_id,
        "health": "available", "verification_status": "runtime_verified", "capability_ids": ["reasoning"], "tool_ids": ["read"],
        "privacy_classes": ["confidential"], "effort_classes": ["high"], "max_context_tokens": 10000,
        "cost_status": "known", "estimated_cost_per_million_tokens": cost, "latency_class": "medium", "reliability_class": "verified",
        "qualified_role_ids": ["role:architect"], "observed_at": now.isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat(),
    }


def test_runtime_route_is_provider_neutral_and_fallback_is_single_use() -> None:
    snapshot = build_capability_snapshot(REPO, [_registration("runtime:a", cost=2), _registration("runtime:b", cost=3)])
    request = {"request_id": "req:1", "plan_revision_id": "plan-revision:1", "harness_revision_id": "harness-revision:1", "capability_ids": ["reasoning"], "tool_ids": ["read"], "privacy_class": "confidential", "effort_class": "high", "context_tokens": 1000, "role_id": "role:architect", "consequence": "medium"}
    decision = resolve_runtime(REPO, request, snapshot)
    assert decision["selected_runtime_id"] == "runtime:a"
    assert decision["fallback_runtime_id"] == "runtime:b"
    assert decision["execution_authorized"] is False
    assert resolve_fallback(decision, failed_runtime_id="runtime:a", attempts_used=1, side_effect_started=False)["runtime_id"] == "runtime:b"
    assert resolve_fallback(decision, failed_runtime_id="runtime:a", attempts_used=1, side_effect_started=True)["status"] == "blocked"


def test_typed_runner_rejects_shell_and_path_escape(tmp_path: Path) -> None:
    spec = {"command_id": "test", "argv": ["python", "-V"], "cwd_policy": "target_repo", "timeout_seconds": 10, "effect_class": "read_only", "required_tool_capabilities": ["python"], "allowed_environment_keys": []}
    packet = prepare_typed_command(spec, target_repo=tmp_path, harness_package=tmp_path, available_tool_capabilities=["python"])
    assert packet["shell"] is False
    assert packet["execution_authorized"] is False
    secret_spec = {**spec, "allowed_environment_keys": ["API_TOKEN"]}
    secret_packet = prepare_typed_command(
        secret_spec,
        target_repo=tmp_path,
        harness_package=tmp_path,
        available_tool_capabilities=["python"],
        environment={"API_TOKEN": "do-not-expose"},
    )
    assert secret_packet["environment_keys"] == ["API_TOKEN"]
    assert "do-not-expose" not in repr(secret_packet)
    with pytest.raises(ValueError, match="metacharacters"):
        validate_command_spec({**spec, "argv": ["python", "-c", "x; y"]})
    with pytest.raises(ValueError, match="Absolute"):
        validate_command_spec({**spec, "argv": ["python", str((tmp_path / "x.py").resolve())]})
    with pytest.raises(ValueError, match="denies execution"):
        run_typed_command(spec, target_repo=tmp_path, harness_package=tmp_path, available_tool_capabilities=["python"], execute=True)


def test_autonomy_blocks_a2_without_exact_lease_and_never_executes() -> None:
    action = {"action_id": "a", "authority_level": "A2", "scope_type": "attempt", "scope_id": "attempt:1", "operation": "fixture_write", "effect_class": "local_build_artifact", "consequence": "small", "target_ref": "fixture:one", "parameters_digest": "sha256:" + "0" * 64, "plan_revision_id": "plan-revision:1", "checkpoint_digest": "sha256:" + "1" * 64, "harness_revision_id": "harness-revision:1", "runtime_route_decision_id": "route:1"}
    result = evaluate_authority(REPO, action)
    assert result["status"] == "blocked"
    assert "exact_lease_missing" in result["reason_codes"]
    assert result["execution_authorized"] is False


def test_global_kill_is_deterministic_and_recovery_is_not_automatic() -> None:
    event = global_kill_candidate(REPO, observed_signals=["audit_corruption"], incident_id="incident:1")
    assert event["payload"]["automatic_recovery"] is False
    assert event["execution_authorized"] is False
