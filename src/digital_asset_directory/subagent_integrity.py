from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .subagent_evaluations import (
    RAW_BASE,
    RAW_FILES,
    _ingest_lock,
    _is_verified_independent,
    _read_jsonl,
    _routing_audit,
    _schema_validator,
    _validate_candidate_authority_boundary,
    _validate_no_private_payload,
    content_hash,
    validate_records,
)
from .transport import data_relative_path
from .utils import append_jsonl, utc_now


PROFILE_REGISTRY_PATH = Path("registry/subagent-evaluation-profile-registry.json")
SELF_ASSESSMENTS_PATH = RAW_BASE / "self-assessments.jsonl"
METHODOLOGY_ID = "dad:methodology:subagent-evaluation-integrity"
METHODOLOGY_VERSION = "0.1.0"
AUTHORITY_BOUNDARY = (
    "This candidate integrity report diagnoses evidence and evaluator weaknesses only. "
    "It cannot treat a self-grade or hash as proof, rank agents or domains, rewrite an "
    "agent or workflow, change model routing, promote a revision, or authorize deployment."
)
SELF_ASSESSMENT_AUTHORITY_BOUNDARY = (
    "This candidate actor-claimed prediction has DAD receipt chronology only. It does not establish "
    "outcome blindness or verified actor identity, prove correctness, award a grade, "
    "authorize promotion, or change routing."
)
DISPOSITIONS = {
    "no_change_freeze_candidate",
    "collect_more_evidence",
    "repair_task_or_rubric",
    "repair_evaluator",
    "revise_agent_instruction",
    "change_model_or_effort_route",
    "change_context_or_data",
    "change_tool_or_environment",
    "redesign_workflow_or_handoff",
    "compose_downstream_specialist",
    "require_domain_expert",
    "retire_or_supersede",
    "human_attribution_required",
}
TARGET_LAYERS = {
    "agent_instruction",
    "model_route",
    "tool",
    "input_contract",
    "context_or_data",
    "workflow",
    "handoff",
    "evaluation_harness",
    "reviewer",
    "domain_overlay",
    "downstream_specialist",
    "preserve_simple",
    "observe_more",
}
_RUNTIME_ASSESSMENT_FIELDS = {"received_at", "receipt_source", "assessment_sha256"}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _profile_index(
    hub_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    path = hub_root / PROFILE_REGISTRY_PATH
    registry = _load_json(path)
    _schema_validator(hub_root, "subagent_evaluation_profile_registry").validate(registry)
    profiles: dict[str, dict[str, Any]] = {}
    for profile in registry["profiles"]:
        profile_id = str(profile["profile_id"])
        if profile_id in profiles:
            raise ValueError(f"Duplicate evaluation profile {profile_id}")
        criterion_ids = [str(row["criterion_id"]) for row in profile["required_criteria"]]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError(f"Evaluation profile {profile_id} has duplicate criteria")
        _validate_candidate_authority_boundary(
            profile["authority_boundary"],
            f"Evaluation profile {profile_id} authority boundary",
        )
        profiles[profile_id] = profile
    if set(registry["dispositions"]) != DISPOSITIONS:
        raise ValueError("Evaluation profile disposition vocabulary is incomplete")
    if set(registry["improvement_target_layers"]) != TARGET_LAYERS:
        raise ValueError("Evaluation profile target-layer vocabulary is incomplete")
    _validate_candidate_authority_boundary(
        registry["authority_boundary"],
        "Evaluation profile registry authority boundary",
    )
    return registry, profiles, content_hash(registry)


def _assessment_without_runtime(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in _RUNTIME_ASSESSMENT_FIELDS}


def _validate_assessment(
    hub_root: Path,
    assessment: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> None:
    _schema_validator(hub_root, "subagent_self_assessment").validate(assessment)
    _validate_no_private_payload(assessment, location=str(assessment["assessment_id"]))
    _validate_candidate_authority_boundary(
        assessment["authority_boundary"],
        f"Self-assessment {assessment['assessment_id']} authority boundary",
    )
    expected_hash = content_hash(
        {key: value for key, value in assessment.items() if key != "assessment_sha256"}
    )
    if assessment["assessment_sha256"] != expected_hash:
        raise ValueError(f"Self-assessment {assessment['assessment_id']} content hash mismatch")
    profile = profiles.get(str(assessment["profile_id"]))
    if profile is None:
        raise ValueError(
            f"Self-assessment {assessment['assessment_id']} references an unknown profile"
        )
    if assessment["profile_version"] != profile["profile_version"]:
        raise ValueError(f"Self-assessment {assessment['assessment_id']} profile version mismatch")
    if assessment["profile_sha256"] != content_hash(profile):
        raise ValueError(f"Self-assessment {assessment['assessment_id']} profile hash mismatch")
    criteria = [str(row["criterion_id"]) for row in assessment["criterion_predictions"]]
    expected = [str(row["criterion_id"]) for row in profile["required_criteria"]]
    if len(criteria) != len(set(criteria)):
        raise ValueError(f"Self-assessment {assessment['assessment_id']} has duplicate predictions")
    if set(criteria) != set(expected):
        raise ValueError(
            f"Self-assessment {assessment['assessment_id']} must predict every profile criterion"
        )
    recorded_at = _parse_time(assessment["recorded_at"])
    received_at = _parse_time(assessment["received_at"])
    if recorded_at is None or received_at is None:
        raise ValueError(
            f"Self-assessment {assessment['assessment_id']} timestamps require time zones"
        )
    if recorded_at > received_at:
        raise ValueError(
            f"Self-assessment {assessment['assessment_id']} claims a future recorded time"
        )


def record_self_assessment(
    hub_root: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Append an actor-claimed prediction with non-caller-controlled receipt chronology."""
    if not isinstance(payload, dict):
        raise ValueError("Self-assessment input must be a JSON object")
    forbidden = _RUNTIME_ASSESSMENT_FIELDS.intersection(payload)
    if forbidden:
        raise ValueError(
            "Self-assessment input cannot supply runtime receipt fields: "
            + ", ".join(sorted(forbidden))
        )
    _, profiles, _ = _profile_index(hub_root)
    assessment = dict(payload)
    assessment.setdefault("schema_version", "dad.subagent.self_assessment.v1")
    assessment.setdefault("phase", "pre_outcome_prediction")
    assessment.setdefault("outcome_visibility", "not_available")
    assessment.setdefault("review_status", "generated_candidate")
    assessment.setdefault("authority_boundary", SELF_ASSESSMENT_AUTHORITY_BOUNDARY)
    assessment["received_at"] = utc_now()
    assessment["receipt_source"] = "dad_cli_runtime"
    assessment["assessment_sha256"] = content_hash(assessment)
    _validate_assessment(hub_root, assessment, profiles)

    path = data_relative_path(hub_root, SELF_ASSESSMENTS_PATH)
    with _ingest_lock(data_relative_path(hub_root, RAW_BASE)):
        existing = {
            str(row.get("assessment_id")): row
            for row in _read_jsonl(path)
            if row.get("assessment_id")
        }
        assessment_id = str(assessment["assessment_id"])
        prior = existing.get(assessment_id)
        if prior is not None:
            if _assessment_without_runtime(prior) != _assessment_without_runtime(assessment):
                raise ValueError(f"Conflicting immutable self-assessment {assessment_id}")
            _validate_assessment(hub_root, prior, profiles)
            return {
                "assessment_id": assessment_id,
                "status": "unchanged",
                "received_at": prior["received_at"],
                "authority_boundary": SELF_ASSESSMENT_AUTHORITY_BOUNDARY,
            }
        append_jsonl(path, assessment)
    return {
        "assessment_id": assessment["assessment_id"],
        "status": "appended",
        "received_at": assessment["received_at"],
        "authority_boundary": SELF_ASSESSMENT_AUTHORITY_BOUNDARY,
    }


def _self_assessment_review(
    attempt: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    if not rows:
        return {
            "status": "missing",
            "count": 0,
            "received_before_recorded_attempt_end": None,
            "actor_binding": "missing",
            "calibration_status": "missing",
            "profile_match": "missing",
            "criterion_coverage": "missing",
            "signals": ["self_assessment_missing"],
        }
    signals: set[str] = set()
    hashes = {str(row["assessment_sha256"]) for row in rows}
    if len(rows) > 1 or len(hashes) > 1:
        signals.add("multiple_self_assessments")
    ended_at = _parse_time(attempt.get("ended_at"))
    receipt_times = [_parse_time(row.get("received_at")) for row in rows]
    before = ended_at is not None and all(
        value is not None and value < ended_at for value in receipt_times
    )
    if ended_at is None:
        status = "attempt_end_missing"
        received_before: bool | None = None
        signals.add("attempt_end_time_unavailable")
    elif before:
        status = "receipt_before_recorded_attempt_end"
        received_before = True
        signals.add("outcome_blindness_not_attested")
    else:
        status = "receipt_after_recorded_attempt_end"
        received_before = False
        signals.add("self_assessment_received_after_recorded_attempt_end")
    if len(rows) > 1:
        status = "conflicting_records"

    if all(str(row.get("actor_id")) == str(attempt["attempt_id"]) for row in rows):
        actor_binding = "claimed_match_unverified"
        signals.add("self_actor_not_runtime_verified")
    else:
        actor_binding = "mismatch"
        signals.add("self_actor_attempt_mismatch")

    calibration_status = "not_available_missing_criterion_outcomes"
    signals.add("criterion_outcome_record_missing")

    if profile is None:
        profile_match = "not_selected"
        criterion_coverage = "not_selected"
        signals.add("domain_profile_not_selected")
    else:
        profile_id = str(profile["profile_id"])
        profile_version = str(profile["profile_version"])
        expected = {str(row["criterion_id"]) for row in profile["required_criteria"]}
        matches = all(
            row["profile_id"] == profile_id
            and row["profile_version"] == profile_version
            and row["profile_sha256"] == content_hash(profile)
            for row in rows
        )
        profile_match = "match" if matches else "mismatch"
        if not matches:
            signals.add("self_assessment_profile_mismatch")
        covered = {
            str(item["criterion_id"])
            for row in rows
            if row["profile_id"] == profile_id
            for item in row["criterion_predictions"]
        }
        criterion_coverage = "complete" if covered == expected else "partial"
        if criterion_coverage == "partial":
            signals.add("self_assessment_criterion_gap")
    return {
        "status": status,
        "count": len(rows),
        "received_before_recorded_attempt_end": received_before,
        "actor_binding": actor_binding,
        "calibration_status": calibration_status,
        "profile_match": profile_match,
        "criterion_coverage": criterion_coverage,
        "signals": sorted(signals),
    }


def _review_cycle_edges(evaluations: list[dict[str, Any]]) -> set[tuple[str, str]]:
    edges = {
        (str(row["attempt_id"]), str(row["evaluator_attempt_id"]))
        for row in evaluations
        if row.get("evaluator_attempt_id") and row.get("evaluator_independence") == "independent"
    }
    adjacency: dict[str, set[str]] = {}
    for source, target in edges:
        adjacency.setdefault(source, set()).add(target)

    def reaches(source: str, target: str, seen: set[str]) -> bool:
        if source == target:
            return True
        if source in seen:
            return False
        seen.add(source)
        return any(reaches(item, target, seen) for item in adjacency.get(source, set()))

    return {edge for edge in edges if reaches(edge[1], edge[0], set())}


def _lineage_ids(
    attempt: dict[str, Any],
    attempts_by_id: dict[str, dict[str, Any]],
) -> set[str]:
    identifiers = {
        f"session:{attempt['parent_session_id']}" for _ in [0] if attempt.get("parent_session_id")
    }
    if attempt.get("runtime_attempt_id"):
        identifiers.add(f"runtime:{attempt['runtime_attempt_id']}")
    parent_id = attempt.get("parent_attempt_id")
    seen: set[str] = set()
    while parent_id and str(parent_id) not in seen:
        parent_text = str(parent_id)
        seen.add(parent_text)
        identifiers.add(f"attempt:{parent_text}")
        parent = attempts_by_id.get(parent_text)
        if parent is None:
            break
        if parent.get("runtime_attempt_id"):
            identifiers.add(f"runtime:{parent['runtime_attempt_id']}")
        if parent.get("parent_session_id"):
            identifiers.add(f"session:{parent['parent_session_id']}")
        parent_id = parent.get("parent_attempt_id")
    return identifiers


def _independent_review(
    attempt: dict[str, Any],
    rows: list[dict[str, Any]],
    attempts_by_id: dict[str, dict[str, Any]],
    cycle_edges: set[tuple[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    claimed = [row for row in rows if row.get("evaluator_independence") == "independent"]
    verified = [row for row in claimed if _is_verified_independent(row, attempts_by_id)]
    signals: set[str] = set()
    if not claimed:
        signals.add("independent_review_missing")
    elif not verified:
        signals.add("independent_identity_unverified")

    subject_family = str(attempt["runtime_claims"]["model_family"]).casefold()
    different_model = 0
    common_lineage = False
    distinct_parent = bool(verified)
    review_cycle_detected = False
    subject_lineage = _lineage_ids(attempt, attempts_by_id)
    for row in verified:
        evaluator_attempt = attempts_by_id[str(row["evaluator_attempt_id"])]
        if str(evaluator_attempt["runtime_claims"]["model_family"]).casefold() != subject_family:
            different_model += 1
        evaluator_lineage = _lineage_ids(evaluator_attempt, attempts_by_id)
        if subject_lineage.intersection(evaluator_lineage):
            common_lineage = True
            distinct_parent = False
        if not subject_lineage or not evaluator_lineage:
            distinct_parent = False
        edge = (str(row["attempt_id"]), str(row["evaluator_attempt_id"]))
        if edge in cycle_edges:
            review_cycle_detected = True
    if verified and different_model == 0:
        signals.add("different_model_family_review_missing")
    if common_lineage:
        signals.add("common_parent_session_lineage")
    if review_cycle_detected:
        signals.add("review_cycle_detected")
    if verified:
        signals.add("blind_review_not_recorded")
        signals.add("prompt_lineage_not_recorded")
        signals.add("evidence_truth_not_verified_by_hash")
    lineage_status = (
        "common_lineage_detected"
        if common_lineage
        else "distinct_parent_candidate"
        if distinct_parent
        else "not_available"
    )
    if not claimed:
        status = "missing"
    elif not verified:
        status = "claim_unverified"
    else:
        status = "identity_verified_integrity_incomplete"
    return (
        {
            "status": status,
            "claimed_count": len(claimed),
            "identity_verified_count": len(verified),
            "different_model_family_count": different_model,
            "domain_expert_review_count": 0,
            "blind_review_status": "not_recorded",
            "lineage_status": lineage_status,
            "reciprocal_cycle_detected": review_cycle_detected,
            "signals": sorted(signals),
        },
        verified,
    )


def _base_attribution(
    self_review: dict[str, Any],
    independent: dict[str, Any],
    evaluations: list[dict[str, Any]],
    routing: dict[str, Any],
    profile: dict[str, Any] | None,
) -> tuple[set[str], set[str], str]:
    layers: set[str] = set()
    signals: set[str] = set()
    disposition = "collect_more_evidence"

    if (
        self_review["status"] != "receipt_before_recorded_attempt_end"
        or self_review["actor_binding"] != "runtime_verified"
        or self_review["calibration_status"] != "calibrated_candidate"
    ):
        layers.update({"observe_more", "evaluation_harness"})
        signals.add("self_prediction_not_calibratable")
    if independent["identity_verified_count"] == 0:
        layers.update({"observe_more", "evaluation_harness", "reviewer"})
        signals.add("independent_outcome_not_reviewable")
    elif independent["status"] != "reviewable_candidate":
        layers.update({"evaluation_harness", "reviewer"})
        signals.add("evaluator_integrity_incomplete")
        disposition = "repair_evaluator"
    if routing["signals"]:
        layers.update({"model_route", "workflow"})
        signals.update(str(value) for value in routing["signals"])
        disposition = "change_model_or_effort_route"
    if self_review["profile_match"] == "mismatch" or self_review["criterion_coverage"] == "partial":
        layers.update({"domain_overlay", "input_contract", "evaluation_harness"})
        signals.add("evaluation_contract_mismatch")
        disposition = "repair_task_or_rubric"
    if profile is None:
        layers.update({"domain_overlay", "observe_more"})
    elif profile["domain_expert_required"] and independent["domain_expert_review_count"] == 0:
        layers.update({"domain_overlay", "downstream_specialist"})
        signals.add("domain_expert_attestation_missing")
        disposition = "require_domain_expert"
    if any(row["aggregate_result"]["gate_failed"] for row in evaluations):
        layers.update(
            {
                "agent_instruction",
                "input_contract",
                "tool",
                "workflow",
                "evaluation_harness",
            }
        )
        signals.add("gate_failure_layer_unresolved")
        disposition = "human_attribution_required"
    if not layers:
        layers.add("observe_more")
    return layers, signals, disposition


def _count_rows(values: list[str]) -> list[dict[str, Any]]:
    counts = Counter(values)
    return [{"id": key, "count": counts[key]} for key in sorted(counts)]


def build_integrity_review(
    hub_root: Path,
    *,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Build a strict read-only meta-evaluation without copying source grades."""
    registry, profiles, registry_hash = _profile_index(hub_root)
    if profile_id is None:
        profile = None
    else:
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"Unknown evaluation profile {profile_id}")

    role_profiles = _read_jsonl(data_relative_path(hub_root, RAW_FILES["role_profiles"]))
    attempts = _read_jsonl(data_relative_path(hub_root, RAW_FILES["attempts"]))
    evaluations = _read_jsonl(data_relative_path(hub_root, RAW_FILES["evaluations"]))
    unrated = _read_jsonl(data_relative_path(hub_root, RAW_FILES["unrated_inventory"]))
    present = [bool(role_profiles), bool(attempts), bool(evaluations)]
    if any(present) and not all(present):
        raise ValueError("Subagent integrity inputs are partial, not reviewable")
    if all(present):
        validate_records(hub_root, role_profiles, attempts, evaluations, unrated)

    self_assessments = _read_jsonl(data_relative_path(hub_root, SELF_ASSESSMENTS_PATH))
    for assessment in self_assessments:
        _validate_assessment(hub_root, assessment, profiles)

    attempts_by_id = {str(row["attempt_id"]): row for row in attempts}
    evaluations_by_attempt: dict[str, list[dict[str, Any]]] = {}
    for evaluation in evaluations:
        evaluations_by_attempt.setdefault(str(evaluation["attempt_id"]), []).append(evaluation)
    assessments_by_attempt: dict[str, list[dict[str, Any]]] = {}
    for assessment in self_assessments:
        assessments_by_attempt.setdefault(str(assessment["attempt_id"]), []).append(assessment)
    cycle_edges = _review_cycle_edges(evaluations)

    contexts: list[dict[str, Any]] = []
    simple_eligible_by_revision: Counter[str] = Counter()
    for attempt in sorted(attempts, key=lambda row: str(row["attempt_id"])):
        attempt_id = str(attempt["attempt_id"])
        attempt_evaluations = evaluations_by_attempt.get(attempt_id, [])
        self_review = _self_assessment_review(
            attempt,
            assessments_by_attempt.get(attempt_id, []),
            profile,
        )
        independent, _ = _independent_review(
            attempt,
            attempt_evaluations,
            attempts_by_id,
            cycle_edges,
        )
        routing = _routing_audit(attempt)
        layers, attribution_signals, disposition = _base_attribution(
            self_review,
            independent,
            attempt_evaluations,
            routing,
            profile,
        )
        eligible_simple = bool(
            profile
            and profile["profile_id"] == "dad:evaluation-profile:simple-deterministic"
            and attempt["terminal_status"] == "completed"
            and self_review["status"] == "receipt_before_recorded_attempt_end"
            and self_review["actor_binding"] == "runtime_verified"
            and self_review["calibration_status"] == "calibrated_candidate"
            and self_review["profile_match"] == "match"
            and self_review["criterion_coverage"] == "complete"
            and independent["identity_verified_count"] >= 1
            and independent["different_model_family_count"] >= 1
            and independent["lineage_status"] == "distinct_parent_candidate"
            and not independent["reciprocal_cycle_detected"]
            and not routing["signals"]
            and not any(row["aggregate_result"]["gate_failed"] for row in attempt_evaluations)
        )
        if eligible_simple:
            simple_eligible_by_revision[str(attempt["role_revision_id"])] += 1
        contexts.append(
            {
                "attempt": attempt,
                "self_review": self_review,
                "independent": independent,
                "evaluations": attempt_evaluations,
                "routing": routing,
                "layers": layers,
                "attribution_signals": attribution_signals,
                "disposition": disposition,
                "eligible_simple": eligible_simple,
            }
        )

    attempt_reviews: list[dict[str, Any]] = []
    for context in contexts:
        attempt = context["attempt"]
        role_revision_id = str(attempt["role_revision_id"])
        layers = set(context["layers"])
        attribution_signals = set(context["attribution_signals"])
        disposition = str(context["disposition"])
        if context["eligible_simple"] and profile is not None:
            required = int(profile["minimum_comparable_attempts_for_no_change"])
            if simple_eligible_by_revision[role_revision_id] >= required:
                layers = {"preserve_simple"}
                attribution_signals = {
                    "bounded_simple_cohort_supports_no_change_candidate",
                    "held_out_shadow_and_human_gate_still_required",
                }
                disposition = "no_change_freeze_candidate"
        evaluator_signals = set(context["independent"]["signals"])
        if not context["evaluations"]:
            evaluator_status = "not_reviewable"
            evaluator_signals.add("evaluation_missing")
        elif context["independent"]["status"] == "reviewable_candidate":
            evaluator_status = "reviewable_candidate"
        else:
            evaluator_status = "integrity_incomplete"
        all_signals = set(context["self_review"]["signals"])
        all_signals.update(context["independent"]["signals"])
        all_signals.update(context["routing"]["signals"])
        all_signals.update(attribution_signals)
        review_id = content_hash(
            {
                "attempt_id": attempt["attempt_id"],
                "profile_id": profile["profile_id"] if profile else None,
                "signals": sorted(all_signals),
                "disposition": disposition,
            }
        ).removeprefix("sha256:")[:20]
        attempt_reviews.append(
            {
                "review_id": f"dad:subagent-integrity-review:{review_id}",
                "attempt_id": attempt["attempt_id"],
                "role_revision_id": role_revision_id,
                "terminal_status": attempt["terminal_status"],
                "self_assessment": context["self_review"],
                "independent_review": context["independent"],
                "evaluator_integrity": {
                    "status": evaluator_status,
                    "signals": sorted(evaluator_signals),
                },
                "attribution": {
                    "status": (
                        "candidate"
                        if disposition
                        in {
                            "no_change_freeze_candidate",
                            "change_model_or_effort_route",
                            "require_domain_expert",
                            "repair_evaluator",
                            "repair_task_or_rubric",
                        }
                        else "unresolved"
                    ),
                    "target_layers": sorted(layers),
                    "signals": sorted(attribution_signals),
                },
                "recommended_disposition": disposition,
                "human_gate_required": True,
                "auto_apply": False,
                "signals": sorted(all_signals),
            }
        )

    disposition_values = [str(row["recommended_disposition"]) for row in attempt_reviews]
    target_values = [
        str(layer) for row in attempt_reviews for layer in row["attribution"]["target_layers"]
    ]
    portfolio_signals = {"cross_domain_comparison_forbidden"}
    if any(row["self_assessment"]["status"] == "missing" for row in attempt_reviews):
        portfolio_signals.add("self_assessment_missing")
    if any(
        row["evaluator_integrity"]["status"] != "reviewable_candidate" for row in attempt_reviews
    ):
        portfolio_signals.add("evaluator_integrity_incomplete")
    if any(
        row["self_assessment"]["actor_binding"] != "runtime_verified" for row in attempt_reviews
    ):
        portfolio_signals.add("self_actor_binding_unverified")
    if any(
        row["self_assessment"]["calibration_status"] != "calibrated_candidate"
        for row in attempt_reviews
    ):
        portfolio_signals.add("self_calibration_unavailable")
    if profile is None:
        portfolio_signals.add("domain_profile_not_selected")
    else:
        portfolio_signals.add("explicit_domain_profile_selection_unverified")
    orphan_assessments = [
        row for row in self_assessments if str(row["attempt_id"]) not in attempts_by_id
    ]
    if orphan_assessments:
        portfolio_signals.add("orphan_self_assessments_present")

    anti_gaming = [
        {
            "check_id": "review_cycles",
            "status": "run",
            "signals": (["review_cycle_detected"] if cycle_edges else ["no_review_cycle_detected"]),
        },
        {
            "check_id": "self_persuasion_blind_verdict",
            "status": "not_supported_by_current_records",
            "signals": ["blind_review_attestation_missing"],
        },
        {
            "check_id": "prediction_actor_and_outcome_sealing",
            "status": "not_supported_by_current_records",
            "signals": [
                "runtime_actor_attestation_missing",
                "orchestrator_outcome_seal_missing",
                "criterion_outcome_record_missing",
            ],
        },
        {
            "check_id": "evaluator_identity_and_lineage_bias",
            "status": "partial",
            "signals": [
                "model_family_and_parent_session_checked",
                "prompt_and_training_lineage_unavailable",
            ],
        },
        {
            "check_id": "evidence_truth_and_environment_replay",
            "status": "not_supported_by_current_records",
            "signals": ["hash_integrity_does_not_prove_evidence_truth"],
        },
        {
            "check_id": "heldout_canary_and_mutation_resistance",
            "status": "not_supported_by_current_records",
            "signals": ["heldout_meta_evaluation_not_recorded"],
        },
        {
            "check_id": "domain_expert_qualification",
            "status": "not_supported_by_current_records",
            "signals": ["reviewer_domain_qualification_not_attested"],
        },
    ]
    profile_selection = {
        "profile_id": profile["profile_id"] if profile else None,
        "status": "explicit_candidate_unverified" if profile else "universal_only",
        "profile_version": profile["profile_version"] if profile else None,
        "profile_sha256": content_hash(profile) if profile else None,
        "cross_domain_comparison_forbidden": True,
    }
    source_snapshot = {
        "attempt_count": len(attempts),
        "evaluation_count": len(evaluations),
        "self_assessment_count": len(self_assessments),
        "source_sha256": {
            "attempts": content_hash(attempts),
            "evaluations": content_hash(evaluations),
            "self_assessments": content_hash(self_assessments),
            "profiles": registry_hash,
        },
    }
    report_status = (
        "no_evidence"
        if not attempts
        else "reviewable_candidate"
        if all(
            row["evaluator_integrity"]["status"] == "reviewable_candidate"
            and row["self_assessment"]["actor_binding"] == "runtime_verified"
            and row["self_assessment"]["calibration_status"] == "calibrated_candidate"
            for row in attempt_reviews
        )
        else "insufficient_integrity"
    )
    methodology = {
        "methodology_id": METHODOLOGY_ID,
        "methodology_version": METHODOLOGY_VERSION,
        "source_sha256": content_hash(
            {
                "registry_hash": registry_hash,
                "algorithm": METHODOLOGY_VERSION,
                "dispositions": registry["dispositions"],
                "target_layers": registry["improvement_target_layers"],
            }
        ),
        "formula": "categorical_rule_projection_no_composite_score",
        "uncertainty_handling": (
            "missing_or_unverifiable_evidence_blocks_clearance_and_routes_to_collect_more_evidence"
        ),
    }
    report: dict[str, Any] = {
        "schema_version": "dad.subagent.evaluation_integrity_report.v1",
        "generated_at": utc_now(),
        "methodology": methodology,
        "profile_selection": profile_selection,
        "source_snapshot": source_snapshot,
        "report_status": report_status,
        "score_authority": (
            "self_assessment_is_prediction_telemetry_not_proof_or_promotion_authority"
        ),
        "attempt_reviews": attempt_reviews,
        "summary": {
            "disposition_counts": _count_rows(disposition_values),
            "target_layer_counts": _count_rows(target_values),
            "portfolio_signals": sorted(portfolio_signals),
        },
        "anti_gaming_checks": anti_gaming,
        "methodology_limitations": [
            "A DAD receipt before recorded attempt end establishes chronology, not actor identity or outcome blindness.",
            "Criterion-level outcome records do not yet exist, so prediction calibration is unavailable.",
            "Existing evaluation hashes establish record integrity, not evidence truth.",
            "Current evaluation records do not attest blind review, prompt lineage, holdout exposure, or reviewer domain qualification.",
            "The selected domain profile is an explicit candidate supplied by the caller and is not inferred or approved by this report.",
            "No cross-domain aggregate score or leaderboard is calculated.",
        ],
        "material_fingerprint": "",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    report["material_fingerprint"] = content_hash(
        {
            key: value
            for key, value in report.items()
            if key not in {"generated_at", "material_fingerprint"}
        }
    )
    validate_integrity_report(hub_root, report)
    return report


def validate_integrity_report(hub_root: Path, report: dict[str, Any]) -> None:
    _schema_validator(hub_root, "subagent_evaluation_integrity_report").validate(report)
    _validate_no_private_payload(report, location="subagent integrity report")
    _validate_candidate_authority_boundary(
        report["authority_boundary"],
        "Subagent integrity report authority boundary",
    )
    expected = content_hash(
        {
            key: value
            for key, value in report.items()
            if key not in {"generated_at", "material_fingerprint"}
        }
    )
    if report["material_fingerprint"] != expected:
        raise ValueError("Subagent integrity report material fingerprint mismatch")
    reviews = report["attempt_reviews"]
    review_ids = [str(row["review_id"]) for row in reviews]
    attempt_ids = [str(row["attempt_id"]) for row in reviews]
    if len(review_ids) != len(set(review_ids)):
        raise ValueError("Subagent integrity report has duplicate review ids")
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ValueError("Subagent integrity report has duplicate attempt ids")
    if report["source_snapshot"]["attempt_count"] != len(reviews):
        raise ValueError("Subagent integrity report attempt count mismatch")
    if any(row["auto_apply"] for row in reviews):
        raise ValueError("Subagent integrity report cannot auto-apply an intervention")
    if any(
        row["recommended_disposition"] == "no_change_freeze_candidate"
        and report["profile_selection"]["profile_id"]
        != "dad:evaluation-profile:simple-deterministic"
        for row in reviews
    ):
        raise ValueError("Preserve-simple disposition requires the simple profile")
    if report["report_status"] == "reviewable_candidate" and any(
        row["evaluator_integrity"]["status"] != "reviewable_candidate"
        or row["self_assessment"]["actor_binding"] != "runtime_verified"
        or row["self_assessment"]["calibration_status"] != "calibrated_candidate"
        for row in reviews
    ):
        raise ValueError(
            "Reviewable report status requires evaluator integrity, actor binding, and calibration"
        )


def list_evaluation_profiles(hub_root: Path) -> dict[str, Any]:
    """Return safe, source-authoritative profile contracts without selecting one."""
    registry, profiles, registry_hash = _profile_index(hub_root)
    return {
        "registry_version": registry["registry_version"],
        "registry_sha256": registry_hash,
        "profiles": [
            {
                "profile_id": profile_id,
                "profile_version": profile["profile_version"],
                "status": profile["status"],
                "criterion_ids": [row["criterion_id"] for row in profile["required_criteria"]],
                "domain_expert_required": profile["domain_expert_required"],
                "minimum_comparable_attempts_for_no_change": profile[
                    "minimum_comparable_attempts_for_no_change"
                ],
                "cross_domain_comparison_forbidden": True,
            }
            for profile_id, profile in sorted(profiles.items())
        ],
        "score_authority": (
            "profiles_define_context_contracts_and_do_not_create_cross_domain_scores"
        ),
        "authority_boundary": registry["authority_boundary"],
    }
