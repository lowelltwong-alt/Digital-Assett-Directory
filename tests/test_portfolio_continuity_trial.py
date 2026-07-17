from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import pytest

from digital_asset_directory import portfolio_continuity_trial as trial
from digital_asset_directory.transport import init_data_root


ZERO_FAILURES = {
    "missed_captures": 0,
    "unnecessary_captures": 0,
    "harmful_captures": 0,
    "false_merges": 0,
    "accidental_mutations": 0,
    "repeated_unchanged_asks": 0,
    "privacy_escapes": 0,
    "blind_delivery_retries": 0,
    "model_calls_on_unchanged_cycles": 0,
}


def _ready_host(assessed_at: str = "2026-06-30T00:00:00+00:00") -> dict:
    return {
        "status": "ready_for_supervised_trial",
        "assessment_digest": "sha256:" + "e" * 64,
        "assessed_at": assessed_at,
        "gate_failures": [],
    }


def _record_reviews(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    times: list[datetime],
    *,
    failure_overrides: dict[str, int] | None = None,
    unsafe_index: int | None = None,
    max_asks: int = 3,
) -> list[dict]:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    iterator = iter(times)
    monkeypatch.setattr(trial, "_utc_now", lambda: next(iterator))
    metrics = {**ZERO_FAILURES, **(failure_overrides or {})}
    for index in range(len(times)):
        trial.record_production_trial_review(
            hub,
            trial_id="trial:v1",
            reviewer_id="reviewer:human",
            snapshot_digest="sha256:" + f"{index + 1:064x}",
            failure_metrics=metrics,
            hook_sample_count=5,
            hook_latency_ms_p95=25.0,
            performance_evidence_digest="sha256:" + "d" * 64,
            adapter_interface_digest="sha256:" + "a" * 64,
            performance_measurement_origin="instrumented_harness",
            supervisor_attestation_id=f"attestation:{index + 1}",
            useful_capture_count=1,
            eligible_plan_count=1,
            max_asks_in_digest=max_asks,
            notification_content_safe=index != unsafe_index,
        )
    return trial.read_trial_reviews(hub)


def test_five_reviews_inside_seven_days_do_not_qualify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    reviews = _record_reviews(
        tmp_path, monkeypatch, [start + timedelta(days=index) for index in range(5)]
    )
    state = trial.evaluate_trial(
        reviews, trial_id="trial:v1", evaluated_at="2026-07-08T00:00:00+00:00"
    )
    assert state["status"] == "trial_incomplete"
    assert "trial_span_less_than_seven_days" in state["gate_failures"]
    assert state["activation_authorized"] is False


def test_five_distinct_zero_failure_reviews_over_seven_days_only_become_eligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    times = [start, start + timedelta(days=2), start + timedelta(days=4)]
    times.extend([start + timedelta(days=6), start + timedelta(days=7)])
    reviews = _record_reviews(tmp_path, monkeypatch, times)

    state = trial.evaluate_trial(
        reviews,
        trial_id="trial:v1",
        evaluated_at="2026-07-08T00:01:00+00:00",
        host_readiness=_ready_host(),
    )
    assert state["status"] == "eligible_for_human_activation"
    assert state["gate_failures"] == []
    assert state["human_approval_status"] == "separate_approval_required"
    assert state["activation_authorized"] is False
    assert state["execution_authorized"] is False


def test_reviews_cannot_qualify_without_recorded_host_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    reviews = _record_reviews(
        tmp_path,
        monkeypatch,
        [start + timedelta(days=index * 2) for index in range(5)],
    )

    state = trial.evaluate_trial(
        reviews, trial_id="trial:v1", evaluated_at="2026-07-10T00:00:00+00:00"
    )

    assert state["status"] == "trial_incomplete"
    assert state["host_readiness_status"] == "missing"
    assert "host_readiness_missing" in state["gate_failures"]


def test_reviews_before_host_readiness_cannot_qualify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    reviews = _record_reviews(
        tmp_path,
        monkeypatch,
        [start + timedelta(days=index * 2) for index in range(5)],
    )

    state = trial.evaluate_trial(
        reviews,
        trial_id="trial:v1",
        evaluated_at="2026-07-12T00:00:00+00:00",
        host_readiness=_ready_host("2026-07-02T00:00:00+00:00"),
    )

    assert state["status"] == "trial_incomplete"
    assert "trial_review_precedes_host_readiness" in state["gate_failures"]


def test_stale_host_binding_cannot_qualify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    reviews = _record_reviews(
        tmp_path,
        monkeypatch,
        [start + timedelta(days=index * 2) for index in range(5)],
    )

    state = trial.evaluate_trial(
        reviews,
        trial_id="trial:v1",
        evaluated_at="2026-07-10T00:00:00+00:00",
        host_readiness=_ready_host(),
        host_binding_failures=["host_readiness_hook_definition_stale"],
    )

    assert state["status"] == "trial_incomplete"
    assert state["host_binding_current"] is False
    assert "host_readiness_hook_definition_stale" in state["gate_failures"]


@pytest.mark.parametrize(
    ("failure_overrides", "unsafe_index", "max_asks", "expected"),
    [
        ({"false_merges": 1}, None, 3, "nonzero_failure_metric:false_merges"),
        ({"accidental_mutations": 1}, None, 3, "nonzero_failure_metric:accidental_mutations"),
        ({}, 2, 3, "notification_content_not_safe"),
        ({}, None, 4, "digest_exceeded_three_asks"),
    ],
)
def test_any_failed_safety_gate_blocks_eligibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_overrides: dict[str, int],
    unsafe_index: int | None,
    max_asks: int,
    expected: str,
) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    reviews = _record_reviews(
        tmp_path,
        monkeypatch,
        [start + timedelta(days=index * 2) for index in range(5)],
        failure_overrides=failure_overrides,
        unsafe_index=unsafe_index,
        max_asks=max_asks,
    )
    state = trial.evaluate_trial(
        reviews, trial_id="trial:v1", evaluated_at="2026-07-10T00:00:00+00:00"
    )
    assert state["status"] == "trial_incomplete"
    assert expected in state["gate_failures"]


def test_fixture_reviews_never_count_for_activation() -> None:
    reviews = [
        trial.build_fixture_trial_review(
            trial_id="trial:v1",
            reviewer_id="fixture",
            snapshot_digest="sha256:" + f"{index + 1:064x}",
            failure_metrics=ZERO_FAILURES,
            recorded_at=(
                datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(days=index * 2)
            ).isoformat(),
        )
        for index in range(5)
    ]
    state = trial.evaluate_trial(reviews, trial_id="trial:v1")
    assert state["status"] == "inactive_shadow"
    assert state["review_count"] == 0
    assert state["fixture_review_count"] == 5


def test_historical_review_without_supervisor_attestation_remains_readable_but_fails_gate(
    tmp_path: Path,
) -> None:
    review = trial._review_record(
        trial_id="trial:historical-preflight",
        reviewer_id="reviewer:historical",
        snapshot_digest="sha256:" + "a" * 64,
        failure_metrics={**ZERO_FAILURES, "missed_captures": 1},
        hook_sample_count=0,
        hook_latency_ms_p95=0.0,
        useful_capture_count=0,
        eligible_plan_count=0,
        max_asks_in_digest=0,
        notification_content_safe=True,
        recorded_at="2026-07-17T00:00:00+00:00",
        fixture_only=False,
    )
    del review["performance"]["supervisor_attestation_id"]
    material = {
        key: review[key]
        for key in (
            "trial_id",
            "reviewer_id",
            "snapshot_digest",
            "failure_metrics",
            "performance",
            "useful_capture_count",
            "eligible_plan_count",
            "max_asks_in_digest",
            "notification_content_safe",
            "recorded_at",
            "fixture_only",
            "recording_origin",
        )
    }
    review["review_id"] = "dad:continuity-review:" + hashlib.sha256(
        trial._canonical(material).encode("utf-8")
    ).hexdigest()
    ledger = tmp_path / "historical-trial.jsonl"
    ledger.write_text(trial._canonical(review) + "\n", encoding="utf-8")

    persisted = trial._read_trial_reviews_from_ledger(ledger)
    state = trial.evaluate_trial(
        persisted,
        trial_id="trial:historical-preflight",
        evaluated_at="2026-07-17T01:00:00+00:00",
    )

    assert state["status"] == "trial_incomplete"
    assert state["review_count"] == 1
    assert "supervisor_attestation_missing" in state["gate_failures"]
    assert state["activation_authorized"] is False


def test_production_review_requires_explicit_supervisor_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))

    with pytest.raises(
        trial.ContinuityValidationError,
        match="requires explicit supervisor attestation",
    ):
        trial.record_production_trial_review(
            hub,
            trial_id="trial:v1",
            reviewer_id="reviewer:human",
            snapshot_digest="sha256:" + "b" * 64,
            failure_metrics=ZERO_FAILURES,
            hook_sample_count=5,
            hook_latency_ms_p95=25.0,
            performance_evidence_digest="sha256:" + "d" * 64,
            adapter_interface_digest="sha256:" + "a" * 64,
            performance_measurement_origin="instrumented_harness",
        )


def test_latency_over_budget_blocks_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    iterator = iter(start + timedelta(days=index * 2) for index in range(5))
    monkeypatch.setattr(trial, "_utc_now", lambda: next(iterator))
    for index in range(5):
        trial.record_production_trial_review(
            hub,
            trial_id="trial:v1",
            reviewer_id="reviewer:human",
            snapshot_digest="sha256:" + f"{index + 1:064x}",
            failure_metrics=ZERO_FAILURES,
            hook_sample_count=5,
            hook_latency_ms_p95=300.0 if index == 2 else 20.0,
            hook_latency_budget_ms=250.0,
            performance_evidence_digest="sha256:" + "d" * 64,
            adapter_interface_digest="sha256:" + "a" * 64,
            performance_measurement_origin="instrumented_harness",
            supervisor_attestation_id=f"attestation:{index + 1}",
        )
    state = trial.evaluate_trial(
        trial.read_trial_reviews(hub),
        trial_id="trial:v1",
        evaluated_at="2026-07-10T00:00:00+00:00",
    )
    assert "hook_latency_budget_exceeded" in state["gate_failures"]
    assert state["maximum_hook_latency_ms_p95"] == 300.0


def test_missing_latency_sample_is_preserved_as_failing_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data"
    init_data_root(data_root, hub_root=hub)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    result = trial.record_production_trial_review(
        hub,
        trial_id="trial:preflight",
        reviewer_id="reviewer:codex",
        snapshot_digest="sha256:" + "a" * 64,
        failure_metrics={**ZERO_FAILURES, "missed_captures": 1},
        hook_sample_count=0,
        hook_latency_ms_p95=0.0,
        supervisor_attestation_id="attestation:preflight",
    )
    state = trial.evaluate_trial([result["review"]], trial_id="trial:preflight")
    assert "hook_latency_sample_missing" in state["gate_failures"]
    assert "nonzero_failure_metric:missed_captures" in state["gate_failures"]


def test_production_recording_has_no_timestamp_parameter() -> None:
    import inspect

    parameters = inspect.signature(trial.record_production_trial_review).parameters
    assert "recorded_at" not in parameters
    assert "clock" not in parameters


def test_trial_review_exact_replay_and_conflict(tmp_path: Path) -> None:
    review = trial.build_fixture_trial_review(
        trial_id="trial:v1",
        reviewer_id="fixture",
        snapshot_digest="sha256:" + "f" * 64,
        failure_metrics=ZERO_FAILURES,
        recorded_at="2026-07-01T00:00:00+00:00",
    )
    ledger = tmp_path / "trial.jsonl"
    assert trial._append_fixture_trial_review(ledger, review) == "appended"
    assert trial._append_fixture_trial_review(ledger, review) == "deduplicated"

    tampered = {**review, "useful_capture_count": 1}
    with pytest.raises(trial.ContinuityValidationError, match="review_id"):
        trial._append_fixture_trial_review(ledger, tampered)


def test_future_dated_nonfixture_reviews_cannot_qualify() -> None:
    reviews = [
        trial._review_record(
            trial_id="trial:v1",
            reviewer_id="reviewer:human",
            snapshot_digest="sha256:" + f"{index + 1:064x}",
            failure_metrics=ZERO_FAILURES,
            hook_sample_count=5,
            hook_latency_ms_p95=20.0,
            useful_capture_count=1,
            eligible_plan_count=1,
            max_asks_in_digest=1,
            notification_content_safe=True,
            recorded_at=(
                datetime(2035, 1, 1, tzinfo=timezone.utc) + timedelta(days=index * 2)
            ).isoformat(),
            fixture_only=False,
        )
        for index in range(5)
    ]
    state = trial.evaluate_trial(
        reviews,
        trial_id="trial:v1",
        evaluated_at="2026-07-16T00:00:00+00:00",
    )
    assert state["status"] == "trial_incomplete"
    assert "review_recorded_after_evaluation_time" in state["gate_failures"]
    with pytest.raises(trial.ContinuityValidationError, match="Only fixture reviews"):
        trial._append_fixture_trial_review(Path("unused.jsonl"), reviews[0])
