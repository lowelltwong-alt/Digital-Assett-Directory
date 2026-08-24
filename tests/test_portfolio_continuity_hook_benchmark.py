from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest
import typer

import digital_asset_directory.cli as cli_module
from digital_asset_directory.cli import portfolio_continuity_benchmark_hook_scale
from digital_asset_directory.cli import portfolio_continuity_trial_review
from digital_asset_directory.portfolio_continuity_codex_hook import (
    CODEX_HOOK_ADAPTER_REVISION_ID,
)
from digital_asset_directory.portfolio_continuity_hook_benchmark import (
    HookPerformanceEvidenceError,
    nearest_rank_p95,
    qualify_hook_scale_evidence,
    run_hook_performance_benchmark,
    validate_hook_performance_evidence,
    validate_hook_scale_collection,
    validate_hook_scale_evidence,
)
from digital_asset_directory.portability_control import (
    canonical_digest,
    runtime_adapter_interface_digest,
)


ROOT = Path(__file__).resolve().parents[1]


def _scale_evidence(*, failing_warm_latency: float | None = None) -> dict:
    results = []
    for count, index_state in (
        (0, "warm"),
        (1_000, "warm"),
        (10_000, "cold"),
        (10_000, "warm"),
    ):
        sample_count = 5 if index_state == "warm" else 1
        latency = (
            failing_warm_latency
            if failing_warm_latency is not None
            and count == 0
            and index_state == "warm"
            else 25.0
        )
        samples = [
            {
                "latency_ms": latency,
                "exit_code": 0,
                "silent": True,
                "ledger_event_count": count + 1,
                "index_event_count": count + 1,
                "index_valid": True,
                "index_size_matches": True,
                "index_digest_matches": True,
                "index_command_count": count + 1,
                "failure_marker_count": 0,
                "persistence_confirmed": True,
                "full_oracle_valid": True,
                "timed_out": False,
            }
            for _index in range(sample_count)
        ]
        latencies = [float(sample["latency_ms"]) for sample in samples]
        p95 = nearest_rank_p95(latencies)
        results.append(
            {
                "preexisting_event_count": count,
                "index_state": index_state,
                "sample_count": sample_count,
                "latency_ms_samples": latencies,
                "latency_ms_p95": p95,
                "samples": samples,
                "latency_ms": p95,
                "exit_code": 0,
                "silent": True,
                "ledger_event_count": count + 1,
                "index_event_count": count + 1,
                "index_valid": True,
                "index_size_matches": True,
                "index_digest_matches": True,
                "index_command_count": count + 1,
                "failure_marker_count": 0,
                "persistence_confirmed": True,
                "full_oracle_valid": True,
                "timed_out_count": 0,
            }
        )
    material = {
        "recorded_at": "2026-08-21T00:00:00+00:00",
        "methodology_id": "methodology:exact-content-index-scale-v1",
        "adapter_revision_id": CODEX_HOOK_ADAPTER_REVISION_ID,
        "adapter_interface_digest": runtime_adapter_interface_digest(
            ROOT, "adapter:intent-continuity-codex-host"
        ),
        "warm_latency_budget_ms": 1500.0,
        "cold_hard_timeout_ms": 5000,
        "results": results,
        "source_worktree_unchanged": True,
        "evidence_integrity": "self_consistent_not_origin_authenticated",
        "origin_authenticated": False,
        "supervisor_attestation_required": True,
        "synthetic_payload": True,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": (
            "Hook performance evidence is synthetic, revision-bound candidate "
            "evidence only and authorizes no effect."
        ),
    }
    return {
        "schema_version": "dad.intent_continuity_hook_scale_evidence.v1",
        "measurement_id": "dad:hook-scale:"
        + canonical_digest(material).split(":", 1)[1],
        **material,
    }


def test_nearest_rank_p95_methodology_is_explicit() -> None:
    assert nearest_rank_p95([1, 2, 3, 4, 5]) == 5.0
    assert nearest_rank_p95([5, 4, 3, 2, 1, 6, 7, 8, 9, 10]) == 10.0


def test_trial_review_cli_requires_instrumented_evidence_not_free_form_latency() -> None:
    parameters = inspect.signature(portfolio_continuity_trial_review).parameters

    assert "performance_evidence" in parameters
    assert "supervisor_attestation_id" in parameters
    assert "hook_latency_ms_p95" not in parameters
    assert "hook_sample_count" not in parameters


@pytest.mark.skipif(not (ROOT / ".codex/hooks.json").exists(), reason="repo hook required")
def test_instrumented_hook_evidence_is_current_silent_private_and_source_bound() -> None:
    evidence = run_hook_performance_benchmark(ROOT, sample_count=5)

    assert validate_hook_performance_evidence(ROOT, evidence) == evidence
    assert evidence["sample_count"] == 5
    assert evidence["silent_success_count"] == 5
    assert evidence["persistence_success_count"] == 5
    assert evidence["privacy_check_passed"] is True
    assert evidence["source_worktree_unchanged"] is True
    assert evidence["adapter_interface_digest"] == runtime_adapter_interface_digest(
        ROOT, "adapter:intent-continuity-codex-host"
    )


def test_performance_evidence_tampering_and_stale_bindings_fail_closed() -> None:
    evidence = run_hook_performance_benchmark(ROOT, sample_count=5)
    tampered = deepcopy(evidence)
    tampered["latency_ms_p95"] = 0.0
    material = {
        key: value
        for key, value in tampered.items()
        if key not in {"schema_version", "measurement_id"}
    }
    tampered["measurement_id"] = "dad:hook-performance:" + canonical_digest(material).split(
        ":", 1
    )[1]
    with pytest.raises(HookPerformanceEvidenceError, match="p95"):
        validate_hook_performance_evidence(ROOT, tampered)

    stale = deepcopy(evidence)
    stale["adapter_interface_digest"] = "sha256:" + "0" * 64
    material = {
        key: value
        for key, value in stale.items()
        if key not in {"schema_version", "measurement_id"}
    }
    stale["measurement_id"] = "dad:hook-performance:" + canonical_digest(material).split(
        ":", 1
    )[1]
    with pytest.raises(HookPerformanceEvidenceError, match="interface digest"):
        validate_hook_performance_evidence(ROOT, stale)


def test_hook_scale_contract_covers_repeated_warm_0_1k_10k_and_cold() -> None:
    result = _scale_evidence()

    assert validate_hook_scale_collection(ROOT, result) == result
    assert qualify_hook_scale_evidence(ROOT, result) == result
    assert result["source_worktree_unchanged"] is True
    assert [(row["preexisting_event_count"], row["index_state"]) for row in result["results"]] == [
        (0, "warm"),
        (1_000, "warm"),
        (10_000, "cold"),
        (10_000, "warm"),
    ]
    assert all(row["exit_code"] == 0 for row in result["results"])
    assert all(row["silent"] is True for row in result["results"])
    assert all(row["persistence_confirmed"] is True for row in result["results"])
    assert all(
        row["sample_count"] >= 5
        for row in result["results"]
        if row["index_state"] == "warm"
    )
    assert all(
        row["latency_ms"] <= result["warm_latency_budget_ms"]
        for row in result["results"]
        if row["index_state"] == "warm"
    )
    cold = next(row for row in result["results"] if row["index_state"] == "cold")
    assert cold["latency_ms"] <= result["cold_hard_timeout_ms"]

    for field, value in (
        ("index_size_matches", False),
        ("index_digest_matches", False),
        ("index_command_count", 0),
    ):
        tampered = deepcopy(result)
        tampered["results"][0]["samples"][0][field] = value
        material = {
            key: item
            for key, item in tampered.items()
            if key not in {"schema_version", "measurement_id"}
        }
        tampered["measurement_id"] = (
            "dad:hook-scale:" + canonical_digest(material).split(":", 1)[1]
        )
        with pytest.raises(HookPerformanceEvidenceError, match="safely"):
            validate_hook_scale_evidence(ROOT, tampered)


def test_failed_scale_evidence_is_written_before_cli_qualification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _scale_evidence(failing_warm_latency=1841.977)
    monkeypatch.setattr(
        cli_module,
        "collect_hook_scale_evidence",
        lambda _repo_root: evidence,
    )
    output = tmp_path / "failed-scale-evidence.json"

    with pytest.raises(typer.BadParameter, match="latency boundary"):
        portfolio_continuity_benchmark_hook_scale(output=output)

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["measurement_id"] == evidence["measurement_id"]
    assert persisted["results"][0]["latency_ms_p95"] == 1841.977
    with pytest.raises(HookPerformanceEvidenceError, match="latency boundary"):
        qualify_hook_scale_evidence(ROOT, persisted)
