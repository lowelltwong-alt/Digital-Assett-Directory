from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from digital_asset_directory import portfolio_continuity_host_readiness as readiness
from digital_asset_directory.portfolio_continuity_codex_hook import ingest_codex_hook
from digital_asset_directory.portfolio_continuity_events import (
    continuity_ledger_path,
    read_observation_events,
)
from digital_asset_directory.portability_control import canonical_digest
from digital_asset_directory.transport import init_data_root


INTERFACE_DIGEST = "sha256:" + "a" * 64
ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    repo = tmp_path / "repo"
    for relative in (
        ".codex/hooks.json",
        "config/intent-continuity-shadow-hooks.json",
        ".digital-asset/dad-integration.json",
        "schemas/intent-continuity-host-readiness.schema.json",
    ):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    (repo / ".git").write_text("gitdir: synthetic-linked-worktree\n", encoding="utf-8")
    return repo


def _hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    return hub


def _bind_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        readiness,
        "_load_adapter_card",
        lambda _root: {
            "revision_id": "portability-card-revision:adapter-intent-continuity-codex-host:0.3.9",
            "adapter_interface_digest": INTERFACE_DIGEST,
        },
    )
    monkeypatch.setattr(
        readiness,
        "runtime_adapter_interface_digest",
        lambda _root, _artifact: INTERFACE_DIGEST,
    )


def _hook_digest(repo: Path) -> str:
    return "sha256:" + hashlib.sha256((repo / ".codex/hooks.json").read_bytes()).hexdigest()


def _stop_input() -> dict:
    return {
        "session_id": "private-session",
        "turn_id": "private-turn",
        "hook_event_name": "Stop",
        "cwd": r"C:\private\repo",
        "transcript_path": r"C:\private\transcript.jsonl",
        "model": "private-model",
    }


def _ingest_stop(hub: Path) -> dict:
    result = ingest_codex_hook(hub, _stop_input(), repository_id="dad")
    event = read_observation_events(continuity_ledger_path(hub))[-1]
    assert event["event_id"] == result["event_id"]
    return event


def test_linked_worktree_without_trust_or_dispatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)

    result = readiness.build_codex_host_readiness(
        repo,
        hub,
        assessed_at="2026-07-17T06:00:00+00:00",
        codex_version="codex-cli 0.130.0",
    )

    assert result["status"] == "not_ready"
    assert result["repository_layout"] == "linked_worktree"
    assert result["dispatch_evidence"]["status"] == "unverified"
    assert result["dispatch_evidence"]["linked_worktree_discovery_risk"] is True
    assert "project_trust_not_attested" in result["gate_failures"]
    assert "exact_hook_trust_not_attested" in result["gate_failures"]
    assert "linked_worktree_dispatch_unverified" in result["gate_failures"]
    assert result["candidate_only"] is True
    assert result["execution_authorized"] is False


def test_exact_attestation_and_current_real_event_are_required_for_trial_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    event = _ingest_stop(hub)

    result = readiness.build_codex_host_readiness(
        repo,
        hub,
        project_trust_status="trusted",
        hook_trust_status="trusted",
        hook_discovery_status="discovered",
        reviewed_hook_definition_digest=_hook_digest(repo),
        reviewer_id="reviewer:human",
        reviewed_at="2026-07-17T00:00:00+00:00",
        dispatch_observer_id="reviewer:human",
        dispatch_attested_at=event["observed_at"],
        attested_event_id=event["event_id"],
        codex_version="codex-cli 0.130.0",
        assessed_at="2026-07-18T00:00:00+00:00",
    )

    assert result["status"] == "ready_for_supervised_trial"
    assert result["gate_failures"] == []
    assert result["dispatch_evidence"]["status"] == "operator_attested"
    assert result["dispatch_evidence"]["current_revision_event_count"] == 1
    assert result["dispatch_evidence"]["attested_event_found"] is True
    assert result["dispatch_evidence"]["temporal_binding_valid"] is True
    assert result["dispatch_evidence"]["origin_authenticated"] is False
    assert result["dispatch_evidence"]["attestable_events"] == [
        {
            "event_id": event["event_id"],
            "observed_at": event["observed_at"],
            "event_kind": event["event_kind"],
        }
    ]
    assert result["host_observation"]["reviewed_digest_matches"] is True
    assert result["human_actions_required"] == []


def test_explicit_host_readiness_recording_is_private_exact_and_replay_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    assessment = readiness.build_codex_host_readiness(
        repo,
        hub,
        assessed_at="2026-07-17T06:00:00+00:00",
        codex_version="codex-cli 0.130.0",
    )

    assert readiness.record_host_readiness_assessment(repo, hub, assessment) == "appended"
    assert (
        readiness.record_host_readiness_assessment(repo, hub, assessment)
        == "deduplicated"
    )
    assert readiness.read_host_readiness_assessments(repo, hub) == [assessment]
    assert readiness.latest_host_readiness_assessment(repo, hub) == assessment
    assert readiness.host_readiness_recording_failures(repo, hub, assessment) == []

    unrecorded = readiness.build_codex_host_readiness(
        repo,
        hub,
        assessed_at="2026-07-17T06:01:00+00:00",
        codex_version="codex-cli 0.130.0",
    )
    assert readiness.host_readiness_recording_failures(repo, hub, unrecorded) == [
        "host_readiness_not_recorded"
    ]
    assert readiness.record_host_readiness_assessment(repo, hub, unrecorded) == "appended"
    assert readiness.host_readiness_recording_failures(repo, hub, assessment) == [
        "host_readiness_not_latest_recorded"
    ]

    other_repo = _repo(tmp_path / "other")
    integration_path = other_repo / ".digital-asset/dad-integration.json"
    integration = json.loads(integration_path.read_text(encoding="utf-8"))
    integration["repo_id"] = "repo:other"
    integration_path.write_text(json.dumps(integration), encoding="utf-8")
    other = readiness.build_codex_host_readiness(
        other_repo,
        hub,
        assessed_at="2026-07-17T07:00:00+00:00",
        codex_version="codex-cli 0.130.0",
    )
    assert readiness.record_host_readiness_assessment(other_repo, hub, other) == "appended"
    assert readiness.latest_host_readiness_assessment(repo, hub) == unrecorded
    assert readiness.latest_host_readiness_assessment(other_repo, hub) == other

    path = readiness.host_readiness_ledger_path(hub)
    tampered = {**assessment, "status": "ready_for_supervised_trial"}
    path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    with pytest.raises(readiness.ContinuityIntegrityError, match="invalid host-readiness"):
        readiness.read_host_readiness_assessments(repo, hub)


def test_current_host_binding_is_rechecked_at_activation_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    event = _ingest_stop(hub)
    assessment = readiness.build_codex_host_readiness(
        repo,
        hub,
        project_trust_status="trusted",
        hook_trust_status="trusted",
        hook_discovery_status="discovered",
        reviewed_hook_definition_digest=_hook_digest(repo),
        reviewer_id="reviewer:human",
        reviewed_at="2026-07-17T00:00:00+00:00",
        dispatch_observer_id="reviewer:human",
        dispatch_attested_at=event["observed_at"],
        attested_event_id=event["event_id"],
        codex_version="codex-cli 0.130.0",
        assessed_at="2026-07-18T00:00:00+00:00",
    )

    assert readiness.host_readiness_binding_failures(repo, assessment) == []
    monkeypatch.setattr(
        readiness,
        "_load_adapter_card",
        lambda _root: {
            "revision_id": "portability-card-revision:adapter-intent-continuity-codex-host:0.3.4",
            "adapter_interface_digest": INTERFACE_DIGEST,
        },
    )
    assert readiness.host_readiness_binding_failures(repo, assessment) == [
        "host_readiness_portability_card_revision_stale"
    ]
    _bind_adapter(monkeypatch)
    (repo / ".codex/hooks.json").write_bytes(
        (repo / ".codex/hooks.json").read_bytes() + b"\n"
    )
    assert readiness.host_readiness_binding_failures(repo, assessment) == [
        "host_readiness_hook_definition_stale"
    ]


def test_stale_review_digest_cannot_be_reused_after_hook_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    previous_digest = _hook_digest(repo)
    hook_path = repo / ".codex/hooks.json"
    hook_path.write_bytes(hook_path.read_bytes() + b"\n")

    result = readiness.build_codex_host_readiness(
        repo,
        hub,
        project_trust_status="trusted",
        hook_trust_status="trusted",
        hook_discovery_status="discovered",
        reviewed_hook_definition_digest=previous_digest,
        reviewer_id="reviewer:human",
        reviewed_at="2026-07-17T06:00:00+00:00",
        assessed_at="2026-07-17T06:01:00+00:00",
    )

    assert result["status"] == "not_ready"
    assert "reviewed_hook_definition_digest_mismatch" in result["gate_failures"]


def test_unattested_runtime_event_cannot_satisfy_dispatch_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    _ingest_stop(hub)

    result = readiness.build_codex_host_readiness(
        repo,
        hub,
        project_trust_status="trusted",
        hook_trust_status="trusted",
        hook_discovery_status="discovered",
        reviewed_hook_definition_digest=_hook_digest(repo),
        reviewer_id="reviewer:human",
        reviewed_at="2026-07-17T00:00:00+00:00",
        assessed_at="2026-07-18T00:00:00+00:00",
    )

    assert result["status"] == "not_ready"
    assert result["dispatch_evidence"]["status"] == "observed_unattested"
    assert result["dispatch_evidence"]["linked_worktree_discovery_risk"] is True
    assert "supervised_dispatch_attestation_missing" in result["gate_failures"]


def test_dispatch_attestation_requires_exact_current_event_and_time_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    event = _ingest_stop(hub)

    wrong_event = readiness.build_codex_host_readiness(
        repo,
        hub,
        project_trust_status="trusted",
        hook_trust_status="trusted",
        hook_discovery_status="discovered",
        reviewed_hook_definition_digest=_hook_digest(repo),
        reviewer_id="reviewer:human",
        reviewed_at="2026-07-17T00:00:00+00:00",
        dispatch_observer_id="reviewer:human",
        dispatch_attested_at=event["observed_at"],
        attested_event_id="dad:continuity-event:" + "0" * 64,
        assessed_at="2026-07-18T00:00:00+00:00",
    )
    bad_time = readiness.build_codex_host_readiness(
        repo,
        hub,
        project_trust_status="trusted",
        hook_trust_status="trusted",
        hook_discovery_status="discovered",
        reviewed_hook_definition_digest=_hook_digest(repo),
        reviewer_id="reviewer:human",
        reviewed_at="2026-07-18T00:00:00+00:00",
        dispatch_observer_id="reviewer:human",
        dispatch_attested_at="2026-07-18T00:00:00+00:00",
        attested_event_id=event["event_id"],
        assessed_at="2026-07-19T00:00:00+00:00",
    )

    assert "attested_dispatch_event_not_found" in wrong_event["gate_failures"]
    assert "dispatch_attestation_temporal_mismatch" in bad_time["gate_failures"]
    assert wrong_event["status"] == bad_time["status"] == "not_ready"


def test_shadow_config_must_require_host_readiness_before_trial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    config_path = repo / "config/intent-continuity-shadow-hooks.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    del config["activation_gate"]["real_codex_dispatch_required"]
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = readiness.build_codex_host_readiness(
        repo,
        hub,
        assessed_at="2026-07-17T06:00:00+00:00",
    )

    assert result["status"] == "not_ready"
    assert "host_readiness_gate_not_configured" in result["gate_failures"]


def test_readiness_packet_contains_no_paths_or_hook_input_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    hub = _hub(tmp_path, monkeypatch)
    _bind_adapter(monkeypatch)
    _ingest_stop(hub)

    result = readiness.build_codex_host_readiness(
        repo,
        hub,
        assessed_at="2026-07-17T06:00:00+00:00",
    )
    rendered = json.dumps(result)

    for forbidden in (
        str(tmp_path),
        "private-session",
        "private-turn",
        "private-model",
        "transcript",
        "C:\\private",
    ):
        assert forbidden not in rendered


def test_tracked_pretrust_readiness_evidence_is_schema_and_digest_valid() -> None:
    evidence = json.loads(
        (
            ROOT
            / "roadmap/evidence/intent-continuity-host-readiness-2026-07-17.json"
        ).read_text(encoding="utf-8")
    )
    readiness._validate_assessment(ROOT, evidence)
    material = {key: value for key, value in evidence.items() if key != "assessment_digest"}

    assert evidence["assessment_digest"] == canonical_digest(material)
    assert evidence["status"] == "not_ready"
    assert evidence["dispatch_evidence"]["current_revision_event_count"] == 0
    assert evidence["candidate_only"] is True
    assert evidence["execution_authorized"] is False
