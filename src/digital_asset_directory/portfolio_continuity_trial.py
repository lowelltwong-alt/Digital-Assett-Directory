"""Supervised shadow-trial receipts and the non-activating continuity gate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .portfolio_continuity_events import (
    ContinuityIntegrityError,
    ContinuityValidationError,
    _append_record_exact,
)
from .transport import data_path, resolve_data_root


TRIAL_AUTHORITY_BOUNDARY = (
    "Trial reviews are immutable candidate evidence. Eligibility never activates a hook, "
    "notification, scheduler, model, Git action, task mutation, or archive operation; "
    "separate human approval remains mandatory."
)
MINIMUM_HOOK_SAMPLE_COUNT = 5
MINIMUM_REVIEWS = 5
MINIMUM_SPAN_DAYS = 7

OPERATOR_PACKET_AUTHORITY_BOUNDARY = (
    "The supervised-trial operator packet is read-only candidate guidance. It cannot "
    "trust a host, record or fabricate a review, advance time, activate a stage, notify, "
    "schedule, mutate Git or tasks, archive work, or authorize cleanup or execution."
)

_FAILURE_KEYS = (
    "missed_captures",
    "missed_recoveries",
    "unnecessary_captures",
    "harmful_captures",
    "false_duplicate_suggestions",
    "false_merges",
    "accidental_mutations",
    "unauthorized_mutations",
    "repeated_unchanged_asks",
    "privacy_escapes",
    "blind_delivery_retries",
    "model_calls_on_unchanged_cycles",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


@lru_cache(maxsize=2)
def _validator(name: str) -> Any:
    schema = json.loads(_schema_path(name).read_text(encoding="utf-8"))
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema, format_checker=FormatChecker())


def _validate(value: Any, schema_name: str) -> None:
    problems: list[str] = []
    for error in sorted(
        _validator(schema_name).iter_errors(value), key=lambda item: list(item.path)
    ):
        path = "$" + "".join(f"[{part!r}]" for part in error.path)
        problems.append(f"{path}: {error.message}")
    if problems:
        raise ContinuityValidationError("; ".join(problems))


def validate_trial_review(review: Any) -> None:
    _validate(review, "portfolio-continuity-trial-review.schema.json")
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
    expected = (
        "dad:continuity-review:" + hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()
    )
    if review["review_id"] != expected:
        raise ContinuityValidationError("review_id does not match review material")
    expected_origin = "fixture_builder" if review["fixture_only"] else "production_clock"
    if review["recording_origin"] != expected_origin:
        raise ContinuityValidationError("recording_origin does not match fixture_only")


def validate_activation_state(state: Any) -> None:
    _validate(state, "portfolio-continuity-activation-state.schema.json")


def validate_trial_operator_packet(packet: Any) -> None:
    _validate(packet, "portfolio-continuity-trial-operator-packet.schema.json")
    material = {key: value for key, value in packet.items() if key != "packet_digest"}
    if packet["packet_digest"] != "sha256:" + hashlib.sha256(
        _canonical(material).encode("utf-8")
    ).hexdigest():
        raise ContinuityValidationError("operator packet digest does not match packet material")


def _trial_review_set_digest(
    reviews: Sequence[Mapping[str, Any]], trial_id: str
) -> str:
    """Bind an activation decision to the exact matching immutable review set."""

    rows: list[dict[str, Any]] = []
    for review in reviews:
        validate_trial_review(review)
        if str(review["trial_id"]) == trial_id:
            rows.append(
                {
                    "review_id": str(review["review_id"]),
                    "fixture_only": bool(review["fixture_only"]),
                }
            )
    rows.sort(key=lambda row: (row["review_id"], row["fixture_only"]))
    return "sha256:" + hashlib.sha256(_canonical(rows).encode("utf-8")).hexdigest()


def trial_review_ledger_path(hub_root: Path) -> Path:
    return data_path(hub_root, "raw_portfolio_intents") / "continuity-trial-reviews.jsonl"


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ContinuityValidationError("Trial review recorded_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _review_record(
    *,
    trial_id: str,
    reviewer_id: str,
    snapshot_digest: str,
    failure_metrics: Mapping[str, int],
    hook_sample_count: int,
    hook_latency_ms_p95: float,
    hook_latency_budget_ms: float = 1500.0,
    performance_evidence_digest: str = "",
    adapter_interface_digest: str = "",
    performance_measurement_origin: str = "unbound",
    supervisor_attestation_id: str = "",
    useful_capture_count: int,
    eligible_plan_count: int,
    max_asks_in_digest: int,
    notification_content_safe: bool,
    recorded_at: str,
    fixture_only: bool,
) -> dict[str, Any]:
    missing_metrics = [key for key in _FAILURE_KEYS if key not in failure_metrics]
    if missing_metrics:
        raise ContinuityValidationError(
            "Trial review lacks required current failure metrics: "
            + ", ".join(missing_metrics)
        )
    performance = {
        "hook_sample_count": hook_sample_count,
        "hook_latency_ms_p95": hook_latency_ms_p95,
        "hook_latency_budget_ms": hook_latency_budget_ms,
        "hook_latency_within_budget": (
            hook_sample_count > 0 and hook_latency_ms_p95 <= hook_latency_budget_ms
        ),
        "measurement_origin": "fixture" if fixture_only else performance_measurement_origin,
        "performance_evidence_digest": performance_evidence_digest,
        "adapter_interface_digest": adapter_interface_digest,
        "supervisor_attestation_id": supervisor_attestation_id,
    }
    material = {
        "trial_id": trial_id,
        "reviewer_id": reviewer_id,
        "snapshot_digest": snapshot_digest,
        "failure_metrics": dict(failure_metrics),
        "performance": performance,
        "useful_capture_count": useful_capture_count,
        "eligible_plan_count": eligible_plan_count,
        "max_asks_in_digest": max_asks_in_digest,
        "notification_content_safe": notification_content_safe,
        "recorded_at": recorded_at,
        "fixture_only": fixture_only,
        "recording_origin": "fixture_builder" if fixture_only else "production_clock",
    }
    review = {
        "schema_version": "dad.portfolio_continuity_trial_review.v1",
        "review_id": "dad:continuity-review:"
        + hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest(),
        **material,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": TRIAL_AUTHORITY_BOUNDARY,
    }
    validate_trial_review(review)
    return review


def build_fixture_trial_review(
    *,
    trial_id: str,
    reviewer_id: str,
    snapshot_digest: str,
    failure_metrics: Mapping[str, int],
    hook_sample_count: int = 1,
    hook_latency_ms_p95: float = 0.0,
    hook_latency_budget_ms: float = 1500.0,
    performance_evidence_digest: str = "",
    adapter_interface_digest: str = "",
    performance_measurement_origin: str = "unbound",
    supervisor_attestation_id: str = "",
    useful_capture_count: int = 0,
    eligible_plan_count: int = 0,
    max_asks_in_digest: int = 0,
    notification_content_safe: bool = True,
    recorded_at: str,
) -> dict[str, Any]:
    """Build synthetic evaluator evidence that can never count for activation."""

    return _review_record(
        trial_id=trial_id,
        reviewer_id=reviewer_id,
        snapshot_digest=snapshot_digest,
        failure_metrics=failure_metrics,
        hook_sample_count=hook_sample_count,
        hook_latency_ms_p95=hook_latency_ms_p95,
        hook_latency_budget_ms=hook_latency_budget_ms,
        performance_evidence_digest=performance_evidence_digest,
        adapter_interface_digest=adapter_interface_digest,
        performance_measurement_origin=performance_measurement_origin,
        supervisor_attestation_id=supervisor_attestation_id,
        useful_capture_count=useful_capture_count,
        eligible_plan_count=eligible_plan_count,
        max_asks_in_digest=max_asks_in_digest,
        notification_content_safe=notification_content_safe,
        recorded_at=recorded_at,
        fixture_only=True,
    )


def record_production_trial_review(
    hub_root: Path,
    *,
    trial_id: str,
    reviewer_id: str,
    snapshot_digest: str,
    failure_metrics: Mapping[str, int],
    hook_sample_count: int,
    hook_latency_ms_p95: float,
    hook_latency_budget_ms: float = 1500.0,
    performance_evidence_digest: str = "",
    adapter_interface_digest: str = "",
    performance_measurement_origin: str = "unbound",
    supervisor_attestation_id: str = "",
    useful_capture_count: int = 0,
    eligible_plan_count: int = 0,
    max_asks_in_digest: int = 0,
    notification_content_safe: bool = True,
) -> dict[str, Any]:
    """Record a non-fixture review using only the production process clock.

    No timestamp parameter is exposed.  Tests should use fixture reviews to
    exercise recording, or pass constructed immutable records to the pure gate.
    """

    if not supervisor_attestation_id.strip():
        raise ContinuityValidationError(
            "Production trial review requires explicit supervisor attestation"
        )
    review = _review_record(
        trial_id=trial_id,
        reviewer_id=reviewer_id,
        snapshot_digest=snapshot_digest,
        failure_metrics=failure_metrics,
        hook_sample_count=hook_sample_count,
        hook_latency_ms_p95=hook_latency_ms_p95,
        hook_latency_budget_ms=hook_latency_budget_ms,
        performance_evidence_digest=performance_evidence_digest,
        adapter_interface_digest=adapter_interface_digest,
        performance_measurement_origin=performance_measurement_origin,
        supervisor_attestation_id=supervisor_attestation_id,
        useful_capture_count=useful_capture_count,
        eligible_plan_count=eligible_plan_count,
        max_asks_in_digest=max_asks_in_digest,
        notification_content_safe=notification_content_safe,
        recorded_at=_utc_now().isoformat(),
        fixture_only=False,
    )
    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Production trial writes require an initialized DAD_DATA_ROOT for this hub"
        )
    status = _append_record_exact(
        trial_review_ledger_path(hub_root), review, identity_field="review_id"
    )
    return {"status": status, "review": review}


def _append_fixture_trial_review(ledger: Path, review: Mapping[str, Any]) -> str:
    """Test-only exact append path; non-fixture reviews are rejected."""

    validate_trial_review(review)
    if review["fixture_only"] is not True:
        raise ContinuityValidationError(
            "Only fixture reviews may use the test ledger append helper"
        )
    return _append_record_exact(ledger, review, identity_field="review_id")


def _read_trial_reviews_from_ledger(ledger: Path) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    reviews: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            review = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContinuityIntegrityError(
                f"invalid JSON at trial review line {line_number}"
            ) from exc
        try:
            validate_trial_review(review)
        except ContinuityValidationError as exc:
            raise ContinuityIntegrityError(
                f"invalid trial review at line {line_number}: {exc}"
            ) from exc
        review_id = str(review["review_id"])
        prior = seen.get(review_id)
        if prior is not None:
            if prior != review:
                raise ContinuityIntegrityError(f"conflicting trial review: {review_id}")
            raise ContinuityIntegrityError(f"duplicate trial review: {review_id}")
        seen[review_id] = review
        reviews.append(review)
    return reviews


def read_trial_reviews(hub_root: Path) -> list[dict[str, Any]]:
    """Read production reviews only from this hub's initialized private root."""

    _root, mode = resolve_data_root(hub_root)
    if mode != "data_root":
        raise ContinuityIntegrityError(
            "Production trial reads require an initialized DAD_DATA_ROOT for this hub"
        )
    return _read_trial_reviews_from_ledger(trial_review_ledger_path(hub_root))


def evaluate_trial(
    reviews: Sequence[Mapping[str, Any]],
    *,
    trial_id: str,
    evaluated_at: str | None = None,
    host_readiness: Mapping[str, Any] | None = None,
    host_binding_failures: Sequence[str] = (),
) -> dict[str, Any]:
    """Evaluate eligibility without recording approval or activating anything."""

    evaluated = _parse_time(evaluated_at) if evaluated_at else _utc_now()
    selected: list[dict[str, Any]] = []
    fixtures = 0
    for review in reviews:
        validate_trial_review(review)
        if str(review["trial_id"]) != trial_id:
            continue
        if review["fixture_only"]:
            fixtures += 1
        else:
            selected.append(dict(review))

    failures: list[str] = []
    host_status = "missing"
    host_digest = ""
    host_assessed_at = ""
    host_adapter_interface_digest = ""
    host_failures = sorted(set(str(value) for value in host_binding_failures))
    host_evidence_failures = list(host_failures)
    host_binding_current = False
    host_time: datetime | None = None
    if host_readiness is None:
        failures.append("host_readiness_missing")
    else:
        host_status = str(host_readiness.get("status", "not_ready"))
        host_digest = str(host_readiness.get("assessment_digest", ""))
        host_assessed_at = str(host_readiness.get("assessed_at", ""))
        adapter_binding = host_readiness.get("adapter_binding", {})
        if isinstance(adapter_binding, Mapping):
            host_adapter_interface_digest = str(
                adapter_binding.get("computed_interface_digest", "")
            )
        host_gate_failures = host_readiness.get("gate_failures", [])
        if not isinstance(host_gate_failures, list):
            host_gate_failures = ["invalid_host_readiness_gate_failures"]
        else:
            host_gate_failures = [str(value) for value in host_gate_failures]
        host_evidence_failures = sorted(set([*host_failures, *host_gate_failures]))
        if host_status != "ready_for_supervised_trial" or host_gate_failures:
            failures.append("host_readiness_not_ready")
        if (
            host_status == "ready_for_supervised_trial"
            and not host_gate_failures
            and not host_adapter_interface_digest
        ):
            failures.append("host_readiness_adapter_digest_missing")
        try:
            host_time = _parse_time(host_assessed_at)
        except (ContinuityValidationError, ValueError):
            failures.append("host_readiness_time_invalid")
        if host_time is not None and host_time > evaluated:
            failures.append("host_readiness_after_evaluation_time")
        failures.extend(host_failures)
        host_binding_current = (
            not host_failures
            and not host_gate_failures
            and host_status == "ready_for_supervised_trial"
            and bool(host_adapter_interface_digest)
        )
    if any(_parse_time(str(review["recorded_at"])) > evaluated for review in selected):
        failures.append("review_recorded_after_evaluation_time")
    if host_time is not None and any(
        _parse_time(str(review["recorded_at"])) < host_time for review in selected
    ):
        failures.append("trial_review_precedes_host_readiness")
    distinct_ids = {str(review["review_id"]) for review in selected}
    distinct_times = {str(review["recorded_at"]) for review in selected}
    if len(selected) < MINIMUM_REVIEWS:
        failures.append("fewer_than_five_non_fixture_reviews")
    if len(distinct_ids) < MINIMUM_REVIEWS or len(distinct_times) < MINIMUM_REVIEWS:
        failures.append("fewer_than_five_distinct_reviews")

    times = sorted(_parse_time(str(review["recorded_at"])) for review in selected)
    span_days = (times[-1] - times[0]).total_seconds() / 86400 if len(times) >= 2 else 0.0
    if span_days < MINIMUM_SPAN_DAYS:
        failures.append("trial_span_less_than_seven_days")

    for key in _FAILURE_KEYS:
        if any(key not in review["failure_metrics"] for review in selected):
            failures.append(f"failure_metric_missing:{key}")
    aggregate_failures = {
        key: sum(int(review["failure_metrics"].get(key, 0)) for review in selected)
        for key in _FAILURE_KEYS
    }
    for key, value in aggregate_failures.items():
        if value:
            failures.append(f"nonzero_failure_metric:{key}")
    if any(int(review["max_asks_in_digest"]) > 3 for review in selected):
        failures.append("digest_exceeded_three_asks")
    if any(review["notification_content_safe"] is not True for review in selected):
        failures.append("notification_content_not_safe")
    if any(int(review["performance"]["hook_sample_count"]) == 0 for review in selected):
        failures.append("hook_latency_sample_missing")
    if any(
        0 < int(review["performance"]["hook_sample_count"]) < MINIMUM_HOOK_SAMPLE_COUNT
        for review in selected
    ):
        failures.append("hook_latency_sample_insufficient")
    if any(
        review["performance"].get("measurement_origin") != "instrumented_harness"
        or not review["performance"].get("performance_evidence_digest")
        or not review["performance"].get("adapter_interface_digest")
        for review in selected
    ):
        failures.append("hook_performance_evidence_unbound")
    if host_adapter_interface_digest and any(
        str(review["performance"].get("adapter_interface_digest", ""))
        != host_adapter_interface_digest
        for review in selected
    ):
        failures.append("review_adapter_interface_digest_mismatch")
    if any(
        not str(review["performance"].get("supervisor_attestation_id", "")).strip()
        for review in selected
    ):
        failures.append("supervisor_attestation_missing")
    if any(
        int(review["performance"]["hook_sample_count"]) > 0
        and review["performance"]["hook_latency_within_budget"] is not True
        for review in selected
    ):
        failures.append("hook_latency_budget_exceeded")
    latency_budgets = {
        float(review["performance"]["hook_latency_budget_ms"]) for review in selected
    }
    if len(latency_budgets) > 1:
        failures.append("inconsistent_hook_latency_budgets")
    sample_counts = [
        int(review["performance"]["hook_sample_count"]) for review in selected
    ]
    latencies = [
        float(review["performance"]["hook_latency_ms_p95"]) for review in selected
    ]

    failures = sorted(set(failures))
    if not selected:
        status = "inactive_shadow"
    elif failures:
        status = "trial_incomplete"
    else:
        status = "eligible_for_human_activation"
    state = {
        "schema_version": "dad.portfolio_continuity_activation_state.v1",
        "trial_id": trial_id,
        "review_set_digest": _trial_review_set_digest(reviews, trial_id),
        "status": status,
        "evaluated_at": evaluated.isoformat(),
        "review_count": len(selected),
        "distinct_review_count": min(len(distinct_ids), len(distinct_times)),
        "trial_span_days": span_days,
        "fixture_review_count": fixtures,
        "minimum_hook_sample_count": min(sample_counts) if sample_counts else 0,
        "maximum_hook_latency_ms_p95": max(latencies) if latencies else 0.0,
        "hook_latency_budget_ms": min(latency_budgets) if latency_budgets else 0.0,
        "host_readiness_status": host_status,
        "host_readiness_assessment_digest": host_digest,
        "host_readiness_assessed_at": host_assessed_at,
        "host_adapter_interface_digest": host_adapter_interface_digest,
        "host_binding_current": host_binding_current,
        "host_readiness_gate_failures": host_evidence_failures,
        "gate_failures": failures,
        "human_approval_required": True,
        "human_approval_status": "separate_approval_required",
        "activation_authorized": False,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": TRIAL_AUTHORITY_BOUNDARY,
    }
    validate_activation_state(state)
    return state


def build_trial_operator_packet(
    reviews: Sequence[Mapping[str, Any]],
    *,
    trial_id: str,
    activation_state: Mapping[str, Any],
    host_readiness: Mapping[str, Any] | None = None,
    host_binding_failures: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Explain the next honest supervised-trial action without performing it."""

    validate_activation_state(activation_state)
    if str(activation_state["trial_id"]) != trial_id:
        raise ContinuityValidationError("activation state trial_id does not match packet trial_id")
    recomputed_state = evaluate_trial(
        reviews,
        trial_id=trial_id,
        evaluated_at=str(activation_state["evaluated_at"]),
        host_readiness=host_readiness,
        host_binding_failures=host_binding_failures,
    )
    if _canonical(activation_state) != _canonical(recomputed_state):
        raise ContinuityValidationError(
            "activation state does not match recomputed review and host evidence"
        )
    review_set_digest = _trial_review_set_digest(reviews, trial_id)
    if str(activation_state["review_set_digest"]) != review_set_digest:
        raise ContinuityValidationError(
            "activation state review_set_digest does not match supplied reviews"
        )
    generated = _parse_time(generated_at) if generated_at else _utc_now()
    evaluated = _parse_time(str(activation_state["evaluated_at"]))
    if generated < evaluated:
        raise ContinuityValidationError(
            "operator packet generated_at precedes activation-state evaluation"
        )
    selected: list[dict[str, Any]] = []
    for review in reviews:
        validate_trial_review(review)
        if str(review["trial_id"]) == trial_id and review["fixture_only"] is False:
            selected.append(dict(review))

    selected.sort(key=lambda row: _parse_time(str(row["recorded_at"])))
    first_review_at = str(selected[0]["recorded_at"]) if selected else ""

    failures = [str(value) for value in activation_state["gate_failures"]]
    permanent_review_prefixes = (
        "failure_metric_missing:",
        "nonzero_failure_metric:",
    )
    permanent_review_failures = {
        "review_recorded_after_evaluation_time",
        "trial_review_precedes_host_readiness",
        "digest_exceeded_three_asks",
        "notification_content_not_safe",
        "hook_latency_sample_missing",
        "hook_latency_sample_insufficient",
        "hook_performance_evidence_unbound",
        "supervisor_attestation_missing",
        "hook_latency_budget_exceeded",
        "inconsistent_hook_latency_budgets",
        "host_readiness_adapter_digest_missing",
        "review_adapter_interface_digest_mismatch",
    }
    restart_reasons = sorted(
        failure
        for failure in failures
        if failure in permanent_review_failures
        or failure.startswith(permanent_review_prefixes)
    )
    if selected and activation_state["host_binding_current"] is not True:
        restart_reasons.append("recorded_reviews_lack_current_host_binding")
    restart_reasons = sorted(set(restart_reasons))

    host_ready = (
        activation_state["host_readiness_status"] == "ready_for_supervised_trial"
        and activation_state["host_binding_current"] is True
    )
    observed = int(activation_state["distinct_review_count"])
    reviews_remaining = (
        MINIMUM_REVIEWS
        if restart_reasons
        else max(0, MINIMUM_REVIEWS - observed)
    )
    earliest_eligibility_at = ""
    span_remaining = float(MINIMUM_SPAN_DAYS)
    if host_ready and not restart_reasons and first_review_at:
        first_review_time = _parse_time(first_review_at)
        if generated < first_review_time:
            raise ContinuityValidationError(
                "operator packet generated_at precedes first production review"
            )
        earliest_time = first_review_time + timedelta(days=MINIMUM_SPAN_DAYS)
        earliest_eligibility_at = earliest_time.isoformat()
        span_remaining = max(
            0.0, (earliest_time - generated).total_seconds() / 86400
        )

    if activation_state["status"] == "eligible_for_human_activation":
        phase = "eligible_for_separate_human_approval"
        next_action = "request_separate_activation_approval"
    elif not host_ready:
        phase = "awaiting_host_readiness"
        next_action = "complete_host_readiness"
    elif restart_reasons:
        phase = "restart_required_after_correction"
        next_action = "correct_and_start_new_trial_revision"
    elif reviews_remaining:
        phase = "collecting_supervised_reviews"
        next_action = "record_next_supervised_review"
    elif "trial_span_less_than_seven_days" in failures:
        if span_remaining:
            phase = "waiting_for_real_clock_span"
            next_action = "wait_then_record_span_extending_supervised_review"
        else:
            phase = "collecting_supervised_reviews"
            next_action = "record_span_extending_supervised_review"
    else:
        phase = "resolving_remaining_gates"
        next_action = "resolve_remaining_gate_failures"

    actions: list[str] = []
    if not host_ready:
        actions.append(
            "Review project trust and the exact current hook definition, then attest one real current-revision event from this linked worktree."
        )
    if restart_reasons:
        actions.append(
            "Correct the revision-bound failure and start a new trial ID; append-only failing reviews cannot be rewritten into passing evidence."
        )
    if host_ready and not restart_reasons and reviews_remaining:
        actions.append(
            f"Record {reviews_remaining} more distinct production-clock supervised review(s) with the complete metrics and performance contract."
        )
    if (
        host_ready
        and not restart_reasons
        and not reviews_remaining
        and "trial_span_less_than_seven_days" in failures
        and not span_remaining
    ):
        actions.append(
            "Record one additional production-clock review now to extend the observed review span to at least seven days."
        )
    if host_ready and not restart_reasons and selected and span_remaining:
        actions.append(
            f"Do not claim eligibility before {earliest_eligibility_at}; wait {span_remaining:.6f} day(s), then record a production-clock review that extends the observed span to at least seven days."
        )
    if activation_state["status"] == "eligible_for_human_activation":
        actions.append(
            "Request a separate exact human approval for the session-start summary stage; eligibility activates nothing by itself."
        )

    packet: dict[str, Any] = {
        "schema_version": "dad.portfolio_continuity_trial_operator_packet.v1",
        "trial_id": trial_id,
        "review_set_digest": review_set_digest,
        "generated_at": generated.isoformat(),
        "phase": phase,
        "next_action": next_action,
        "host_readiness_status": str(activation_state["host_readiness_status"]),
        "host_binding_current": bool(activation_state["host_binding_current"]),
        "observed_review_count": int(activation_state["review_count"]),
        "distinct_review_count": observed,
        "minimum_review_count": MINIMUM_REVIEWS,
        "reviews_remaining": reviews_remaining,
        "trial_span_days": float(activation_state["trial_span_days"]),
        "minimum_span_days": MINIMUM_SPAN_DAYS,
        "span_days_remaining": span_remaining,
        "first_review_at": first_review_at,
        "earliest_eligibility_at": earliest_eligibility_at,
        "restart_required": bool(restart_reasons),
        "restart_reasons": restart_reasons,
        "gate_failures": failures,
        "review_contract": {
            "failure_metric_keys": list(_FAILURE_KEYS),
            "minimum_hook_sample_count": MINIMUM_HOOK_SAMPLE_COUNT,
            "maximum_asks_per_digest": 3,
            "performance_measurement_origin": "instrumented_harness",
            "hook_latency_within_budget_required": True,
            "latency_budget_source": "validated_performance_evidence",
            "performance_evidence_digest_required": True,
            "adapter_interface_digest_match_required": True,
            "supervisor_attestation_required": True,
            "notification_content_safe_required": True,
            "production_clock_required": True,
            "zero_failure_metrics_required_for_activation": True,
        },
        "human_actions_required": actions,
        "delivery_authorized": False,
        "activation_authorized": False,
        "cleanup_authorized": False,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": OPERATOR_PACKET_AUTHORITY_BOUNDARY,
    }
    packet["packet_digest"] = "sha256:" + hashlib.sha256(
        _canonical(packet).encode("utf-8")
    ).hexdigest()
    validate_trial_operator_packet(packet)
    return packet


__all__ = [
    "MINIMUM_REVIEWS",
    "MINIMUM_SPAN_DAYS",
    "TRIAL_AUTHORITY_BOUNDARY",
    "build_fixture_trial_review",
    "build_trial_operator_packet",
    "evaluate_trial",
    "read_trial_reviews",
    "record_production_trial_review",
    "trial_review_ledger_path",
    "validate_activation_state",
    "validate_trial_review",
]
