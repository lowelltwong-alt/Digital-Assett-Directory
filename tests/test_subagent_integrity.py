from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from digital_asset_directory.subagent_evaluations import (
    _evaluation_bundle_hash,
    _is_verified_independent,
    content_hash,
    ingest_packet,
)
from digital_asset_directory.subagent_integrity import (
    SELF_ASSESSMENTS_PATH,
    _review_cycle_edges,
    build_integrity_review,
    list_evaluation_profiles,
    record_self_assessment,
    validate_integrity_report,
)


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "examples/subagent-evaluations/logos-t475-and-dad-graph-v1"


def _hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    for rel in (
        "registry/schema-registry.json",
        "registry/subagent-evaluation-methodology.json",
        "registry/subagent-evaluation-methodologies/0.1.0.json",
        "registry/subagent-capability-registry.json",
        "registry/subagent-evaluation-profile-registry.json",
        "registry/graph-edge-registry.json",
        "registry/edge-type-registry.json",
        "schemas/subagent-role-profile-revision.schema.json",
        "schemas/subagent-execution-attempt.schema.json",
        "schemas/subagent-attempt-evaluation.schema.json",
        "schemas/subagent-capability-graph.schema.json",
        "schemas/subagent-evaluation-methodology.schema.json",
        "schemas/subagent-unrated-inventory.schema.json",
        "schemas/subagent-evaluation-profile-registry.schema.json",
        "schemas/subagent-self-assessment.schema.json",
        "schemas/subagent-evaluation-integrity-report.schema.json",
    ):
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    evidence_source = PACKET / "evidence"
    evidence_target = hub / PACKET.relative_to(ROOT) / "evidence"
    evidence_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(evidence_source, evidence_target)
    return hub


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _profile(hub: Path, profile_id: str) -> dict[str, Any]:
    registry = json.loads(
        (hub / "registry/subagent-evaluation-profile-registry.json").read_text(encoding="utf-8")
    )
    return next(row for row in registry["profiles"] if row["profile_id"] == profile_id)


def _assessment_payload(
    profile: dict[str, Any],
    attempt_id: str,
    *,
    assessment_id: str = "dad:subagent-self-assessment:test",
    recorded_at: str = "2026-01-01T00:00:01+00:00",
) -> dict[str, Any]:
    return {
        "assessment_id": assessment_id,
        "attempt_id": attempt_id,
        "actor_id": attempt_id,
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "profile_sha256": content_hash(profile),
        "criterion_predictions": [
            {
                "criterion_id": criterion["criterion_id"],
                "predicted_status": "pass",
                "probability_pass": 0.8,
                "confidence": 0.7,
                "evidence_refs": ["input://locked-contract"],
            }
            for criterion in profile["required_criteria"]
        ],
        "anticipated_failure_modes": ["A boundary case may invalidate the prediction."],
        "falsifiers": ["A locked validator or independent reviewer finds a contract failure."],
        "limitations": ["Outcome evidence was not visible when this prediction was recorded."],
        "recorded_at": recorded_at,
    }


def _contains_exact_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return bool(forbidden.intersection(value)) or any(
            _contains_exact_key(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_exact_key(item, forbidden) for item in value)
    return False


def _refresh_attempt_snapshot_hashes(hub: Path) -> None:
    attempts_path = hub / "raw/agent-evaluations/execution-attempts.jsonl"
    evaluations_path = hub / "raw/agent-evaluations/attempt-evaluations.jsonl"
    attempts = _read_jsonl(attempts_path)
    by_id = {row["attempt_id"]: row for row in attempts}
    evaluations = _read_jsonl(evaluations_path)
    for evaluation in evaluations:
        evaluation["attempt_snapshot_sha256"] = content_hash(by_id[evaluation["attempt_id"]])
    _write_jsonl(evaluations_path, evaluations)


def test_profile_registry_and_empty_integrity_report_are_strict(tmp_path: Path):
    hub = _hub(tmp_path)

    profiles = list_evaluation_profiles(hub)
    assert {row["profile_id"] for row in profiles["profiles"]} >= {
        "dad:evaluation-profile:simple-deterministic",
        "dad:evaluation-profile:financial-algorithm-research",
        "dad:evaluation-profile:evidence-heavy-historical-claims",
    }
    assert all(row["cross_domain_comparison_forbidden"] for row in profiles["profiles"])

    report = build_integrity_review(hub)
    assert report["report_status"] == "no_evidence"
    assert report["score_authority"].endswith("not_proof_or_promotion_authority")
    assert report["attempt_reviews"] == []
    validate_integrity_report(hub, report)


def test_runtime_receipt_cannot_be_forged_and_orphans_remain_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = _hub(tmp_path)
    profile = _profile(hub, "dad:evaluation-profile:general-agentic-work")
    payload = _assessment_payload(
        profile,
        "dad:subagent-attempt:future",
        assessment_id="dad:subagent-self-assessment:future",
    )

    with pytest.raises(ValueError, match="cannot supply runtime receipt"):
        record_self_assessment(
            hub,
            {**payload, "received_at": "2025-01-01T00:00:00+00:00"},
        )

    with pytest.raises(TypeError, match="received_at"):
        record_self_assessment(
            hub,
            payload,
            received_at="2025-01-01T00:00:00+00:00",  # type: ignore[call-arg]
        )

    receipt_times = iter(
        [
            "2026-01-01T00:00:02+00:00",
            "2026-01-01T00:00:03+00:00",
            "2026-01-01T00:00:04+00:00",
        ]
    )
    monkeypatch.setattr(
        "digital_asset_directory.subagent_integrity.utc_now", lambda: next(receipt_times)
    )
    first = record_self_assessment(hub, payload)
    second = record_self_assessment(hub, payload)
    assert first["status"] == "appended"
    assert second["status"] == "unchanged"
    stored = _read_jsonl(hub / SELF_ASSESSMENTS_PATH)
    assert stored[0]["receipt_source"] == "dad_cli_runtime"
    assert stored[0]["received_at"] == "2026-01-01T00:00:02+00:00"

    report = build_integrity_review(hub)
    assert "orphan_self_assessments_present" in report["summary"]["portfolio_signals"]


def test_seed_report_exposes_missing_integrity_without_copying_scores(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)

    first = build_integrity_review(hub)
    second = build_integrity_review(hub)

    assert first["report_status"] == "insufficient_integrity"
    assert first["source_snapshot"]["attempt_count"] == 16
    assert all(row["self_assessment"]["status"] == "missing" for row in first["attempt_reviews"])
    assert all(row["independent_review"]["status"] == "missing" for row in first["attempt_reviews"])
    assert not _contains_exact_key(
        first,
        {
            "score",
            "self_score",
            "independent_score",
            "aggregate_result",
            "ranking",
        },
    )
    assert first["material_fingerprint"] == second["material_fingerprint"]

    finance = build_integrity_review(
        hub,
        profile_id="dad:evaluation-profile:financial-algorithm-research",
    )
    assert all(
        "domain_expert_attestation_missing" in row["signals"] for row in finance["attempt_reviews"]
    )
    assert all(
        "downstream_specialist" in row["attribution"]["target_layers"]
        for row in finance["attempt_reviews"]
    )


def test_after_outcome_self_grade_is_recorded_but_unusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    attempts_path = hub / "raw/agent-evaluations/execution-attempts.jsonl"
    attempts = _read_jsonl(attempts_path)
    target = attempts[0]
    target["ended_at"] = "2026-01-01T00:00:10+00:00"
    _write_jsonl(attempts_path, attempts)
    _refresh_attempt_snapshot_hashes(hub)

    profile = _profile(hub, "dad:evaluation-profile:general-agentic-work")
    monkeypatch.setattr(
        "digital_asset_directory.subagent_integrity.utc_now",
        lambda: "2026-01-01T00:00:11+00:00",
    )
    record_self_assessment(
        hub,
        _assessment_payload(
            profile,
            target["attempt_id"],
            assessment_id="dad:subagent-self-assessment:after-outcome",
        ),
    )

    report = build_integrity_review(hub, profile_id=profile["profile_id"])
    row = next(
        item for item in report["attempt_reviews"] if item["attempt_id"] == target["attempt_id"]
    )
    assert row["self_assessment"]["status"] == "receipt_after_recorded_attempt_end"
    assert row["self_assessment"]["received_before_recorded_attempt_end"] is False
    assert "self_assessment_received_after_recorded_attempt_end" in row["signals"]


def test_integrity_review_detects_common_reviewer_lineage(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    attempts_path = hub / "raw/agent-evaluations/execution-attempts.jsonl"
    evaluations_path = hub / "raw/agent-evaluations/attempt-evaluations.jsonl"
    attempts = _read_jsonl(attempts_path)
    evaluations = _read_jsonl(evaluations_path)
    subject = attempts[1]
    reviewer = attempts[0]
    subject["parent_session_id"] = "dad:session:shared-parent"
    reviewer["parent_session_id"] = "dad:session:shared-parent"
    reviewer["runtime_claims"]["verification_status"] = "runtime_verified"
    _write_jsonl(attempts_path, attempts)
    _refresh_attempt_snapshot_hashes(hub)
    evaluations = _read_jsonl(evaluations_path)

    seed = next(row for row in evaluations if row["attempt_id"] == subject["attempt_id"])
    independent = copy.deepcopy(seed)
    independent["evaluation_id"] = "dad:subagent-evaluation:common-lineage-test"
    independent["evaluator"] = "common-lineage-reviewer"
    independent["evaluator_attempt_id"] = reviewer["attempt_id"]
    independent["evaluator_independence"] = "independent"
    independent["evaluator_identity"] = {
        "actor_id": reviewer["attempt_id"],
        "actor_type": "subagent",
        "verification_status": "runtime_verified",
        "relationship_to_attempt": "independent",
        "evidence_ref": reviewer["artifact_refs"][0]["ref"],
    }
    independent["aggregate_result"]["status"] = "rated_attempt"
    independent["evidence_grade"] = "independent_hashed_review"
    independent["evidence_bundle_sha256"] = _evaluation_bundle_hash(independent)
    _write_jsonl(evaluations_path, [*evaluations, independent])

    report = build_integrity_review(hub)
    row = next(
        item for item in report["attempt_reviews"] if item["attempt_id"] == subject["attempt_id"]
    )
    assert row["independent_review"]["identity_verified_count"] == 1
    assert row["independent_review"]["lineage_status"] == "common_lineage_detected"
    assert "common_parent_session_lineage" in row["signals"]
    assert "evidence_truth_not_verified_by_hash" in row["signals"]
    assert row["evaluator_integrity"]["status"] == "integrity_incomplete"


def test_simple_cohort_cannot_freeze_without_verified_criterion_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    attempts_path = hub / "raw/agent-evaluations/execution-attempts.jsonl"
    evaluations_path = hub / "raw/agent-evaluations/attempt-evaluations.jsonl"
    attempts = _read_jsonl(attempts_path)
    subjects = [
        row
        for row in attempts
        if row["role_revision_id"] == "dad:role-profile-revision:terra-integration-specialist:v1"
    ]
    reviewers = [
        row
        for row in attempts
        if row["runtime_claims"]["model_family"] == "gpt-5.6-sol"
        and row["terminal_status"] == "completed"
    ][:3]
    assert len(subjects) == len(reviewers) == 3

    for index, (subject, reviewer) in enumerate(zip(subjects, reviewers, strict=True)):
        subject["started_at"] = f"2026-01-01T00:00:0{index}+00:00"
        subject["ended_at"] = "2026-01-01T00:00:10+00:00"
        subject["parent_session_id"] = f"dad:session:simple-subject-{index}"
        reviewer["parent_session_id"] = f"dad:session:simple-reviewer-{index}"
        reviewer["runtime_claims"]["verification_status"] = "runtime_verified"
        subject["routing_decision"] = {
            "task_complexity": "low",
            "material_complexity": "low",
            "material_scale": "small",
            "material_ambiguity": "low",
            "material_sensitivity": "public",
            "consequence": "low",
            "selected_model_family": "terra",
            "selected_reasoning_effort": "medium",
            "selection_reason": "Bounded synthetic simple-role cohort.",
            "alternatives_considered": ["luna/low"],
        }
    _write_jsonl(attempts_path, attempts)
    _refresh_attempt_snapshot_hashes(hub)
    evaluations = _read_jsonl(evaluations_path)

    independent_rows: list[dict[str, Any]] = []
    for index, (subject, reviewer) in enumerate(zip(subjects, reviewers, strict=True)):
        seed = next(row for row in evaluations if row["attempt_id"] == subject["attempt_id"])
        seed["aggregate_result"]["gate_failed"] = False
        independent = copy.deepcopy(seed)
        independent["evaluation_id"] = f"dad:subagent-evaluation:simple-preserve-{index}"
        independent["evaluator"] = f"simple-preserve-reviewer-{index}"
        independent["evaluator_attempt_id"] = reviewer["attempt_id"]
        independent["evaluator_independence"] = "independent"
        independent["evaluator_identity"] = {
            "actor_id": reviewer["attempt_id"],
            "actor_type": "subagent",
            "verification_status": "runtime_verified",
            "relationship_to_attempt": "independent",
            "evidence_ref": reviewer["artifact_refs"][0]["ref"],
        }
        independent["aggregate_result"]["status"] = "rated_attempt"
        independent["aggregate_result"]["gate_failed"] = False
        independent["evidence_grade"] = "independent_hashed_review"
        independent["evidence_bundle_sha256"] = _evaluation_bundle_hash(independent)
        independent_rows.append(independent)
    _write_jsonl(evaluations_path, [*evaluations, *independent_rows])

    profile = _profile(hub, "dad:evaluation-profile:simple-deterministic")
    monkeypatch.setattr(
        "digital_asset_directory.subagent_integrity.utc_now",
        lambda: "2026-01-01T00:00:05+00:00",
    )
    for index, subject in enumerate(subjects):
        record_self_assessment(
            hub,
            _assessment_payload(
                profile,
                subject["attempt_id"],
                assessment_id=f"dad:subagent-self-assessment:simple-{index}",
            ),
        )

    report = build_integrity_review(hub, profile_id=profile["profile_id"])
    subject_reviews = [
        row
        for row in report["attempt_reviews"]
        if row["attempt_id"] in {subject["attempt_id"] for subject in subjects}
    ]
    assert len(subject_reviews) == 3
    assert not any(
        row["recommended_disposition"] == "no_change_freeze_candidate" for row in subject_reviews
    )
    assert not any(
        "preserve_simple" in row["attribution"]["target_layers"] for row in subject_reviews
    )
    assert all(
        row["self_assessment"]["calibration_status"] == "not_available_missing_criterion_outcomes"
        for row in subject_reviews
    )
    assert all(
        row["self_assessment"]["actor_binding"] == "claimed_match_unverified"
        for row in subject_reviews
    )
    assert all("self_prediction_not_calibratable" in row["signals"] for row in subject_reviews)
    assert all(row["human_gate_required"] for row in subject_reviews)
    assert not any(row["auto_apply"] for row in subject_reviews)


def test_reported_reviewer_attempt_cannot_self_assert_runtime_verification():
    attempts = _read_jsonl(PACKET / "execution-attempts.jsonl")
    subject = attempts[0]
    reviewer = attempts[1]
    evaluation = {
        "attempt_id": subject["attempt_id"],
        "evaluator_attempt_id": reviewer["attempt_id"],
        "evaluator_independence": "independent",
        "evaluator_identity": {
            "actor_id": reviewer["attempt_id"],
            "verification_status": "runtime_verified",
            "relationship_to_attempt": "independent",
            "evidence_ref": reviewer["artifact_refs"][0]["ref"],
        },
    }

    assert reviewer["runtime_claims"]["verification_status"] == "reported"
    assert not _is_verified_independent(evaluation, {row["attempt_id"]: row for row in attempts})


def test_review_cycle_detection_handles_cycles_longer_than_two_nodes():
    rows = [
        {
            "attempt_id": source,
            "evaluator_attempt_id": target,
            "evaluator_independence": "independent",
        }
        for source, target in (("a", "b"), ("b", "c"), ("c", "a"))
    ]

    assert _review_cycle_edges(rows) == {("a", "b"), ("b", "c"), ("c", "a")}
