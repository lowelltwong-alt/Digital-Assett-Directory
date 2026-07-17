from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path

import pytest

from digital_asset_directory.cli import portfolio_continuity_trial_review
from digital_asset_directory.portfolio_continuity_hook_benchmark import (
    HookPerformanceEvidenceError,
    nearest_rank_p95,
    run_hook_performance_benchmark,
    run_hook_scale_harness,
    validate_hook_performance_evidence,
    validate_hook_scale_evidence,
)
from digital_asset_directory.portability_control import (
    canonical_digest,
    runtime_adapter_interface_digest,
)


ROOT = Path(__file__).resolve().parents[1]


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


def test_hook_scale_harness_covers_cold_and_warm_0_1k_10k() -> None:
    result = run_hook_scale_harness(ROOT)

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
        tampered["results"][0][field] = value
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
