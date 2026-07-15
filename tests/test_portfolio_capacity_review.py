"""Adversarial tests for the JSON-only portfolio capacity shadow review."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from digital_asset_directory import portfolio_capacity_review as capacity
from digital_asset_directory.portfolio_cockpit import schema_validation_problems


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _mission_payload(
    *,
    status: str = "reviewed",
    track_status: str = "reviewed",
    reviewed_at: datetime = NOW,
) -> dict:
    return {
        "schema_version": "dad.repo-missions.v1",
        "repo_ref": "dad://repo/synthetic-capacity",
        "status": status,
        "reviewed_at": reviewed_at.isoformat(),
        "data_classification": "C1_internal_metadata",
        "c3_payload_included": False,
        "human_review_required": True,
        "authority_boundary": "Synthetic source owner retains mission authority.",
        "mission": "Exercise the capacity-review contract with synthetic metadata.",
        "source_evidence": ["AI_FRONT_DOOR.md", "MACHINE_NAVIGATION_MANIFEST.json"],
        "tracks": [
            {
                "track_id": "capacity-shadow",
                "goal": "Prove fail-closed weekly capacity reporting.",
                "review_status": track_status,
                "map_rules": {
                    "branch_patterns": ["capacity/*"],
                    "path_globs": ["src/**"],
                },
            }
        ],
    }


def _write_mission(
    repo: Path,
    *,
    status: str = "reviewed",
    track_status: str = "reviewed",
    reviewed_at: datetime = NOW,
) -> Path:
    path = repo / ".digital-asset" / "portfolio" / "missions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _mission_payload(
                status=status,
                track_status=track_status,
                reviewed_at=reviewed_at,
            )
        ),
        encoding="utf-8",
    )
    return path


def _missions(repo: Path, **kwargs) -> list[dict]:
    _write_mission(repo, **kwargs)
    return capacity.load_repo_mission_coverage([repo], schema_root=ROOT, now=NOW)


def _review(
    *,
    human_count: int = 0,
    health: list[dict] | None = None,
    now: datetime = NOW,
) -> dict:
    return {
        "schema_version": "dad.portfolio_review_packet.v2",
        "generated_at": now.isoformat(),
        "status": "generated_candidate",
        "dashboard": {
            "now": [
                {
                    "subject_ref": f"workstream:human-{index}",
                    "kind": "human_decision",
                }
                for index in range(human_count)
            ]
        },
        "blockers": [],
        "unknowns": [],
        "health": health or [],
    }


def _sources(
    *, human_count: int = 0, roles: list[dict] | None = None, now: datetime = NOW
) -> dict:
    return {
        "portfolio_review": _review(human_count=human_count, now=now),
        "portfolio_attention": {
            "schema_version": "dad.portfolio_attention.v1",
            "generated_at": now.isoformat(),
            "status": "generated_candidate",
            "attention_queue": [],
            "projects": [],
        },
        "subagent_role_directory": {
            "schema_version": "dad.subagent_role_directory.v1",
            "generated_at": now.isoformat(),
            "status": "candidate",
            "roles": roles or [],
        },
        "daemon": {
            "schema_version": "dad.daemon.status.v1",
            "generated_at": now.isoformat(),
            "status": "fresh",
            "stale": False,
        },
        "roadmap": {
            "schema_version": "dad.roadmap.status.adapter.v1",
            "last_checked_at": now.isoformat(),
            "status": "observed",
            "phases": {},
        },
        "agent_skill_registry": {
            "schema_version": "0.1.0",
            "status": "candidate_seed",
            "skills": [],
        },
        "asset_registry": {
            "registry_version": "0.1.0",
            "status": "installed_candidate",
            "assets": [],
        },
        "coding_asset_registry": {
            "registry_version": "0.1.0",
            "status": "installed_candidate",
            "assets": [],
        },
        "subagent_evaluation_profiles": {
            "registry_version": "0.1.0",
            "status": "candidate",
            "profiles": [],
        },
        "learning_loop_status": {
            "schema_version": "dad.learning_loop.status.v1",
            "generated_at": now.isoformat(),
            "status": "current",
            "open_without_outcome_count": 0,
        },
        "iteration_measurements": {
            "schema_version": "dad.iteration_measurements.v1",
            "generated_at": now.isoformat(),
            "status": "current",
            "observations": [],
        },
        "scheduled_tasks": {
            "schema_version": "dad.daemon.scheduled_tasks.v1",
            "generated_at": now.isoformat(),
            "status": "current",
            "inspect_scheduler": True,
            "tasks": [{"scheduler": {"installed": True}}],
        },
        "research_freshness": {
            "schema_version": "dad.research_freshness.v1",
            "generated_at": now.isoformat(),
            "status": "current",
            "sources": [],
        },
    }


def _packet(repo: Path, *, human_count: int = 0, worker_packets=(), prior=None) -> dict:
    return capacity.build_portfolio_capacity_review(
        source_payloads=_sources(human_count=human_count),
        mission_coverage=_missions(repo),
        worker_packets=worker_packets,
        prior_packet=prior,
        now=NOW,
    )


def _validate(packet: dict) -> None:
    assert schema_validation_problems(packet, ROOT, "portfolio_capacity_review") == []
    assert capacity.portfolio_capacity_review_semantic_problems(packet) == []


def test_missing_and_candidate_missions_fail_closed_without_alignment_claim(tmp_path: Path):
    missing = capacity.load_repo_mission_coverage([tmp_path], schema_root=ROOT, now=NOW)
    assert missing[0]["status"] == "missing"

    candidate_repo = tmp_path / "candidate"
    candidate_repo.mkdir()
    candidate = _missions(candidate_repo, status="candidate", track_status="candidate")
    assert candidate[0]["status"] == "unknown"

    packet = capacity.build_portfolio_capacity_review(
        source_payloads=_sources(), mission_coverage=candidate, now=NOW
    )
    _validate(packet)
    assert packet["status"] == "partial_candidate"
    assert packet["mission_coverage"][0]["status"] == "unknown"
    serialized = json.dumps(packet).casefold()
    assert "mission_fit" not in serialized
    assert "leverage_score" not in serialized


def test_reviewed_source_owned_mission_is_current(tmp_path: Path):
    missions = _missions(tmp_path)
    assert missions[0]["status"] == "current"
    assert missions[0]["verified_at"] == NOW.isoformat()


def test_unknown_future_mission_status_is_invalid_not_guessed(tmp_path: Path):
    path = _write_mission(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "future_active"
    path.write_text(json.dumps(payload), encoding="utf-8")

    missions = capacity.load_repo_mission_coverage([tmp_path], schema_root=ROOT, now=NOW)
    assert missions[0]["status"] == "invalid"
    assert missions[0]["problems"] == ["mission_contract_schema_invalid"]


def test_human_frontier_is_three_and_overflow_is_complete(tmp_path: Path):
    packet = _packet(tmp_path, human_count=4)
    _validate(packet)
    assert len(packet["human_asks"]) == 3
    assert packet["overflow"]["complete"] is True
    assert packet["overflow"]["unrepresented_candidate_count"] == 0
    assert len(packet["overflow"]["items"]) == 1

    tampered = deepcopy(packet)
    tampered["human_asks"].append(deepcopy(tampered["human_asks"][0]))
    assert "human_ask_limit_exceeded" in capacity.portfolio_capacity_review_semantic_problems(
        tampered
    )
    assert schema_validation_problems(tampered, ROOT, "portfolio_capacity_review")


def test_unchanged_fingerprint_suppresses_fanout_and_duplicate_asks(tmp_path: Path):
    first = _packet(tmp_path, human_count=2)
    second = capacity.build_portfolio_capacity_review(
        source_payloads=_sources(human_count=2, now=NOW + timedelta(days=7)),
        mission_coverage=capacity.load_repo_mission_coverage(
            [tmp_path], schema_root=ROOT, now=NOW + timedelta(days=7)
        ),
        prior_packet=first,
        now=NOW + timedelta(days=7),
    )
    _validate(second)
    assert second["routing"]["semantic_agent_fanout"] == 0
    assert second["routing"]["fanout_status"] == "deterministic_v0_not_dispatched"
    assert second["human_asks"] == []
    assert second["bottlenecks"] == []
    assert second["overflow"]["items"] == []
    assert {row["reason"] for row in second["suppressed"]} == {"unchanged_fingerprint"}


def test_builder_contract_revision_wakes_semantic_suppression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    first = _packet(tmp_path, human_count=1)
    monkeypatch.setattr(
        capacity,
        "BUILDER_CONTRACT_REVISION",
        "dad.portfolio-capacity-review.builder.synthetic-next",
    )
    changed = capacity.build_portfolio_capacity_review(
        source_payloads=_sources(human_count=1),
        mission_coverage=_missions(tmp_path),
        prior_packet=first,
        now=NOW,
    )
    assert changed["material_fingerprint"] != first["material_fingerprint"]
    assert changed["human_asks"]
    assert changed["suppressed"] == []


@pytest.mark.parametrize(
    "candidate",
    [
        {
            "category": "worktree_or_handoff",
            "subject_ref": "worktree:old-only",
            "age_only": True,
            "evidence_refs": ["age:90d"],
        },
        {
            "category": "dependency_frontier",
            "subject_ref": "dependency:proposed-only",
            "accepted_dependency": False,
            "evidence_refs": ["dependency:proposed"],
        },
    ],
)
def test_age_only_and_proposed_dependencies_are_suppressed(tmp_path: Path, candidate: dict):
    worker = {
        "role_id": "delivery-closeout-resumption-steward",
        "role_revision_id": "role-revision:worker-v1",
        "privacy_class": "C1",
        "candidates": [candidate],
    }
    packet = _packet(tmp_path, worker_packets=[worker])
    _validate(packet)
    assert all(row["category"] != candidate["category"] for row in packet["bottlenecks"])
    assert any(row["reason"] == "insufficient_evidence" for row in packet["suppressed"])


def test_snoozed_work_stays_visible_as_suppressed_until_its_wake_condition(tmp_path: Path):
    worker = {
        "role_id": "neglected-worktree-triage-manager",
        "privacy_class": "C1",
        "candidates": [
            {
                "category": "worktree_or_handoff",
                "subject_ref": "worktree:snoozed",
                "state": "snoozed",
                "evidence_refs": ["state:snoozed"],
                "wake_conditions": ["snooze_expiry", "new_commit"],
            }
        ],
    }
    packet = _packet(tmp_path, worker_packets=[worker])
    _validate(packet)
    row = next(item for item in packet["suppressed"] if item["reason"] == "snoozed")
    assert row["wake_conditions"] == ["new_commit", "snooze_expiry"]
    assert packet["human_asks"] == []


def test_healthy_daemon_cannot_hide_a_stale_independent_source(tmp_path: Path):
    sources = _sources()
    sources["daemon"] = {
        "schema_version": "dad.daemon.status.v1",
        "generated_at": NOW.isoformat(),
        "status": "fresh",
        "stale": False,
    }
    sources["roadmap"] = {
        "schema_version": "dad.roadmap.status.adapter.v1",
        "last_checked_at": NOW.isoformat(),
        "status": "stale",
        "phases": {},
    }
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=sources,
        mission_coverage=_missions(tmp_path),
        now=NOW,
    )
    _validate(packet)
    assert packet["status"] == "partial_candidate"
    source_status = {
        row["source_id"]: row["status"] for row in packet["source_coverage"]["sources"]
    }
    assert source_status["daemon"] == "current"
    assert source_status["roadmap"] == "stale"
    assert packet["source_coverage"]["coverage_complete"] is False


def test_learning_loop_without_outcome_receipt_remains_unknown(tmp_path: Path):
    worker = {
        "role_id": "improvement-layer-router",
        "privacy_class": "C1",
        "candidates": [
            {
                "category": "learning_loop",
                "subject_ref": "learning-loop:open",
                "evidence_refs": ["attempt:present"],
                "outcome_receipt_present": False,
            }
        ],
    }
    packet = _packet(tmp_path, worker_packets=[worker])
    _validate(packet)
    row = next(item for item in packet["bottlenecks"] if item["category"] == "learning_loop")
    assert row["evidence_status"] == "unknown"


def test_iteration_claim_needs_baseline_same_workload_parity_and_failure_path(tmp_path: Path):
    incomplete_worker = {
        "role_id": "capability-maturity-and-cycle-auditor",
        "role_revision_id": "role-revision:cycle-v1",
        "privacy_class": "C1",
        "candidates": [
            {
                "category": "iteration_cycle",
                "subject_ref": "command:test-suite",
                "evidence_refs": ["wall_time:61s"],
            }
        ],
    }
    incomplete = _packet(tmp_path, worker_packets=[incomplete_worker])
    _validate(incomplete)
    assert incomplete["iteration_evidence"][0]["status"] == "unknown"
    assert incomplete["iteration_evidence"][0]["measurement_ref"] == "missing_measured_baseline"

    complete_worker = deepcopy(incomplete_worker)
    complete_worker["candidates"][0]["iteration_measurement"] = {
        "metric_kind": "wall_time",
        "better_is": "lower",
        "baseline": {
            "value": 61,
            "unit": "seconds",
            "workload_ref": "workload:exact-node-ids",
            "receipt_ref": "receipt:baseline-61s",
        },
        "comparison": {
            "value": 80,
            "unit": "seconds",
            "workload_ref": "workload:exact-node-ids",
            "receipt_ref": "receipt:comparison-42s",
        },
        "correctness_or_parity": {
            "oracle_ref": "test:pass-skip-fail",
            "status": "passed",
        },
        "failure_path": {
            "failure_path_ref": "test:failure-path-preserved",
            "status": "preserved",
        },
    }
    complete = _packet(tmp_path / "complete", worker_packets=[complete_worker])
    _validate(complete)
    assert complete["iteration_evidence"][0]["status"] == "confirmed"


@pytest.mark.parametrize(
    "worker, match",
    [
        (
            {
                "role_id": "delivery-closeout-resumption-steward",
                "privacy_class": "C3",
                "candidates": [],
            },
            "C3/C4 input",
        ),
        (
            {
                "role_id": "delivery-closeout-resumption-steward",
                "privacy_class": "C1",
                "candidates": [
                    {
                        "category": "attention_or_compute",
                        "subject_ref": "candidate:scored",
                        "evidence_refs": ["source:synthetic"],
                        "score": 99,
                    }
                ],
            },
            "scores are prohibited",
        ),
    ],
)
def test_c3_and_composite_scores_fail_before_digest(tmp_path: Path, worker: dict, match: str):
    with pytest.raises(ValueError, match=match):
        _packet(tmp_path, worker_packets=[worker])


def test_worker_checker_revision_collision_blocks_candidate(tmp_path: Path):
    worker = {
        "role_id": "delivery-closeout-resumption-steward",
        "role_revision_id": "role-revision:same",
        "privacy_class": "C1",
        "candidates": [],
    }
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=_sources(),
        mission_coverage=_missions(tmp_path),
        worker_packets=[worker],
        checker_revision_id="role-revision:same",
        now=NOW,
    )
    _validate(packet)
    assert packet["status"] == "blocked_candidate"
    assert packet["routing"]["checker_lineage"]["verdict"] == "not_run"


def test_every_required_source_is_declared_and_omission_is_partial(tmp_path: Path):
    for source_id in capacity.REQUIRED_SOURCE_IDS:
        sources = _sources()
        sources.pop(source_id)
        packet = capacity.build_portfolio_capacity_review(
            source_payloads=sources,
            mission_coverage=_missions(tmp_path / source_id),
            now=NOW,
        )
        _validate(packet)
        assert packet["status"] == "partial_candidate"
        assert packet["source_coverage"]["coverage_complete"] is False
        assert source_id in packet["source_coverage"]["unavailable_source_ids"]


def test_unknown_source_id_status_schema_and_empty_projection_fail_closed(tmp_path: Path):
    sources = _sources()
    sources["future_lane"] = {"schema_version": "dad.future.v1", "status": "current"}
    with pytest.raises(ValueError, match="unknown capacity source ids"):
        capacity.build_portfolio_capacity_review(
            source_payloads=sources,
            mission_coverage=_missions(tmp_path / "unknown-id"),
            now=NOW,
        )

    for label, replacement, expected_problem in (
        (
            "future-status",
            {"schema_version": "dad.portfolio_attention.v1", "status": "future"},
            "unknown_source_status",
        ),
        (
            "future-schema",
            {"schema_version": "dad.portfolio_attention.v99", "status": "current"},
            "unsupported_source_schema_version",
        ),
        ("empty", {}, "unsupported_source_schema_version"),
    ):
        sources = _sources()
        sources["portfolio_attention"] = replacement
        packet = capacity.build_portfolio_capacity_review(
            source_payloads=sources,
            mission_coverage=_missions(tmp_path / label),
            now=NOW,
        )
        _validate(packet)
        assert packet["status"] == "blocked_candidate"
        row = next(
            item
            for item in packet["source_coverage"]["sources"]
            if item["source_id"] == "portfolio_attention"
        )
        assert row["status"] == "invalid"
        assert expected_problem in row["problems"]


def test_c3_source_and_nested_worker_controls_are_rejected_before_hashing(tmp_path: Path):
    sources = _sources()
    sources["portfolio_attention"]["c3_payload_included"] = True
    with pytest.raises(ValueError, match="C3 payload flag"):
        capacity.build_portfolio_capacity_review(
            source_payloads=sources,
            mission_coverage=_missions(tmp_path / "c3-source"),
            now=NOW,
        )

    worker = {
        "role_id": "delivery-closeout-resumption-steward",
        "privacy_class": "C1",
        "candidates": [
            {
                "category": "attention_or_compute",
                "subject_ref": "candidate:nested-action",
                "evidence_refs": ["source:synthetic"],
                "details": {"execute": False},
            }
        ],
    }
    with pytest.raises(ValueError, match="forbidden action field"):
        _packet(tmp_path / "nested-action", worker_packets=[worker])


def test_portfolio_attention_projects_only_consumed_safe_fields(tmp_path: Path):
    sources = _sources()
    sources["portfolio_attention"]["attention_queue"] = [
        {
            "project_id": "synthetic-project",
            "branch": "feature/capacity",
            "reasons": ["dirty_worktree", "unpushed_or_unmerged_commits"],
            "priority": 100,
            "worktree_path": "C:\\private-root\\synthetic-project",
            "evidence": {"score": 0.9876},
        }
    ]
    sources["portfolio_attention"]["projects"] = [
        {"project_id": "synthetic-project", "similarity": {"score": 0.9876}}
    ]

    packet = capacity.build_portfolio_capacity_review(
        source_payloads=sources,
        mission_coverage=_missions(tmp_path),
        now=NOW,
    )
    _validate(packet)
    serialized = json.dumps(packet)
    assert "private-root" not in serialized
    assert '"priority": 100' not in serialized
    assert any(
        row["category"] == "worktree_or_handoff" for row in packet["bottlenecks"]
    )

    unsafe = deepcopy(sources)
    unsafe["portfolio_attention"]["projects"][0]["client_payload_included"] = True
    with pytest.raises(ValueError, match="C3 payload flag"):
        capacity.build_portfolio_capacity_review(
            source_payloads=unsafe,
            mission_coverage=_missions(tmp_path / "unsafe"),
            now=NOW,
        )


def test_scalar_source_is_invalid_without_hashing_excluded_content(tmp_path: Path):
    sources = _sources()
    sources["portfolio_attention"] = "synthetic-client-secret"
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=sources,
        mission_coverage=_missions(tmp_path),
        now=NOW,
    )
    _validate(packet)
    row = next(
        item
        for item in packet["source_coverage"]["sources"]
        if item["source_id"] == "portfolio_attention"
    )
    assert row["status"] == "invalid"
    assert row["evidence_refs"] == ["source:portfolio_attention:invalid_scalar"]
    assert "synthetic-client-secret" not in json.dumps(packet)


def test_required_lanes_affect_the_deterministic_shortlist(tmp_path: Path):
    sources = _sources()
    sources["portfolio_attention"]["attention_queue"] = [
        {
            "project_id": "synthetic-project",
            "branch": "feature/capacity",
            "reasons": ["dirty_worktree", "unpushed_or_unmerged_commits"],
        }
    ]
    sources["roadmap"]["phases"] = {
        "active-phase": {
            "declared_status": "active",
            "computed_status": "awaiting_human_gate",
            "blocked_dependencies": ["accepted-foundation"],
        },
        "partial-phase": {
            "declared_status": "complete",
            "computed_status": "blocked",
            "blocked_dependencies": [],
        },
    }
    sources["agent_skill_registry"]["skills"] = [
        {"skill_id": "candidate-skill", "status": "candidate"}
    ]
    sources["learning_loop_status"]["open_without_outcome_count"] = 2
    sources["iteration_measurements"]["observations"] = [
        {
            "subject_ref": "command:measured",
            "measurement": {
                "metric_kind": "wall_time",
                "better_is": "lower",
                "baseline": {
                    "value": 90,
                    "unit": "seconds",
                    "workload_ref": "workload:same",
                    "receipt_ref": "receipt:baseline",
                },
                "comparison": {
                    "value": 120,
                    "unit": "seconds",
                    "workload_ref": "workload:same",
                    "receipt_ref": "receipt:comparison",
                },
                "correctness_or_parity": {
                    "oracle_ref": "test:parity",
                    "status": "passed",
                },
                "failure_path": {
                    "failure_path_ref": "test:failure-path",
                    "status": "preserved",
                },
            },
        }
    ]
    sources["research_freshness"]["sources"] = [
        {"source_id": "research:architecture", "status": "stale"}
    ]
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=sources,
        mission_coverage=_missions(tmp_path),
        now=NOW,
    )
    _validate(packet)
    categories = {row["category"] for row in packet["bottlenecks"]}
    assert {
        "worktree_or_handoff",
        "human_decision",
        "dependency_frontier",
        "planned_or_partial_buildout",
        "skill_or_subagent_maturity",
        "learning_loop",
        "iteration_cycle",
        "mission_or_architecture_drift",
    } <= categories
    assert packet["iteration_evidence"][0]["status"] == "confirmed"


def test_dynamic_source_freshness_expires_and_cannot_claim_complete(tmp_path: Path):
    sources = _sources()
    sources["portfolio_attention"]["generated_at"] = (
        NOW - timedelta(hours=169)
    ).isoformat()
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=sources,
        mission_coverage=_missions(tmp_path),
        now=NOW,
    )
    _validate(packet)
    row = next(
        item
        for item in packet["source_coverage"]["sources"]
        if item["source_id"] == "portfolio_attention"
    )
    assert row["status"] == "stale"
    assert row["freshness_status"] == "stale"
    assert "source_freshness_expired" in row["problems"]
    assert packet["source_coverage"]["coverage_complete"] is False


@pytest.mark.parametrize(
    "source_id,mutate,problem",
    [
        (
            "roadmap",
            lambda source: source["phases"].update(
                {
                    "future-phase": {
                        "declared_status": "future",
                        "computed_status": "future",
                        "blocked_dependencies": [],
                    }
                }
            ),
            "roadmap_declared_status_unknown",
        ),
        (
            "agent_skill_registry",
            lambda source: source["skills"].append(
                {"skill_id": "future-skill", "status": "future"}
            ),
            "registry_status_unknown",
        ),
        (
            "research_freshness",
            lambda source: source["sources"].append(
                {"source_id": "research:future", "status": "future"}
            ),
            "research_source_status_unknown",
        ),
        (
            "roadmap",
            lambda source: source["phases"].update(
                {
                    "invalid-dependency": {
                        "declared_status": "active",
                        "computed_status": "blocked",
                        "blocked_dependencies": [7],
                    }
                }
            ),
            "roadmap_blocked_dependencies_invalid",
        ),
    ],
)
def test_nested_future_or_malformed_lane_values_block_before_routing(
    tmp_path: Path, source_id: str, mutate, problem: str
):
    sources = _sources()
    mutate(sources[source_id])
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=sources,
        mission_coverage=_missions(tmp_path / problem),
        now=NOW,
    )
    _validate(packet)
    assert packet["status"] == "blocked_candidate"
    row = next(
        item
        for item in packet["source_coverage"]["sources"]
        if item["source_id"] == source_id
    )
    assert row["status"] == "invalid"
    assert problem in row["problems"]


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("accepted_dependency", "false", "must be a boolean"),
        ("human_decision_required", 1, "must be a boolean"),
        ("age_only", None, "must be a boolean"),
    ],
)
def test_worker_booleans_are_strict(
    tmp_path: Path, field: str, value: object, match: str
):
    candidate = {
        "category": "attention_or_compute",
        "subject_ref": f"candidate:boolean-{field}",
        "evidence_refs": ["source:synthetic"],
        field: value,
    }
    worker = {
        "role_id": "delivery-closeout-resumption-steward",
        "privacy_class": "C1",
        "candidates": [candidate],
    }
    if match:
        with pytest.raises(ValueError, match=match):
            _packet(tmp_path / field, worker_packets=[worker])
    else:
        packet = _packet(tmp_path / field, worker_packets=[worker])
        _validate(packet)


def test_worker_cannot_self_elevate_precedence_or_use_unregistered_role(tmp_path: Path):
    candidate = {
        "category": "attention_or_compute",
        "subject_ref": "candidate:self-elevated",
        "evidence_refs": ["source:synthetic"],
        "precedence_class": "authority_privacy_security_integrity_gate",
    }
    worker = {
        "role_id": "delivery-closeout-resumption-steward",
        "privacy_class": "C1",
        "candidates": [candidate],
    }
    with pytest.raises(ValueError, match="precedence override"):
        _packet(tmp_path / "precedence", worker_packets=[worker])

    worker["role_id"] = "unregistered-capacity-worker"
    worker["candidates"] = []
    with pytest.raises(ValueError, match="not repo-authoritative"):
        _packet(tmp_path / "role", worker_packets=[worker])


def test_deceptive_iteration_refs_do_not_confirm_or_reach_human_frontier(tmp_path: Path):
    worker = {
        "role_id": "capability-maturity-and-cycle-auditor",
        "privacy_class": "C1",
        "candidates": [
            {
                "category": "iteration_cycle",
                "subject_ref": "command:deceptive",
                "human_decision_required": True,
                "evidence_refs": [
                    "baseline:missing",
                    "same_workload:not-proven",
                    "parity:not-run",
                    "failure:unknown",
                ],
            }
        ],
    }
    packet = _packet(tmp_path, worker_packets=[worker])
    _validate(packet)
    assert packet["iteration_evidence"][0]["status"] == "unknown"
    assert packet["human_asks"] == []
    assert any(row["reason"] == "insufficient_evidence" for row in packet["suppressed"])


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_iteration_measurements_are_rejected(tmp_path: Path, value: float):
    worker = {
        "role_id": "capability-maturity-and-cycle-auditor",
        "privacy_class": "C1",
        "candidates": [
            {
                "category": "iteration_cycle",
                "subject_ref": "command:non-finite",
                "iteration_measurement": {
                    "metric_kind": "wall_time",
                    "better_is": "lower",
                    "baseline": {
                        "value": value,
                        "unit": "seconds",
                        "workload_ref": "workload:same",
                        "receipt_ref": "receipt:baseline",
                    },
                    "comparison": {
                        "value": 1,
                        "unit": "seconds",
                        "workload_ref": "workload:same",
                        "receipt_ref": "receipt:comparison",
                    },
                    "correctness_or_parity": {
                        "oracle_ref": "test:parity",
                        "status": "passed",
                    },
                    "failure_path": {
                        "failure_path_ref": "test:failure",
                        "status": "preserved",
                    },
                },
            }
        ],
    }
    with pytest.raises(ValueError, match="non-negative measurement number"):
        _packet(tmp_path, worker_packets=[worker])


@pytest.mark.parametrize("comparison", [42, 61])
def test_neutral_or_improved_iteration_receipt_is_not_a_bottleneck(
    tmp_path: Path, comparison: int
):
    worker = {
        "role_id": "capability-maturity-and-cycle-auditor",
        "privacy_class": "C1",
        "candidates": [
            {
                "category": "iteration_cycle",
                "subject_ref": f"command:no-drag-{comparison}",
                "human_decision_required": True,
                "iteration_measurement": {
                    "metric_kind": "wall_time",
                    "better_is": "lower",
                    "baseline": {
                        "value": 61,
                        "unit": "seconds",
                        "workload_ref": "workload:same",
                        "receipt_ref": "receipt:baseline",
                    },
                    "comparison": {
                        "value": comparison,
                        "unit": "seconds",
                        "workload_ref": "workload:same",
                        "receipt_ref": "receipt:comparison",
                    },
                    "correctness_or_parity": {
                        "oracle_ref": "test:parity",
                        "status": "passed",
                    },
                    "failure_path": {
                        "failure_path_ref": "test:failure",
                        "status": "preserved",
                    },
                },
            }
        ],
    }
    packet = _packet(tmp_path, worker_packets=[worker])
    _validate(packet)
    assert not any(row["category"] == "iteration_cycle" for row in packet["bottlenecks"])
    assert packet["iteration_evidence"][0]["status"] == "confirmed"
    assert packet["iteration_evidence"][0]["drag_observed"] is False
    assert packet["human_asks"] == []
    assert any(row["reason"] == "no_material_drag" for row in packet["suppressed"])


def test_within_class_order_uses_evidence_and_exposes_frontier_ties(tmp_path: Path):
    candidates = [
        {
            "category": "human_decision",
            "subject_ref": f"decision:{name}",
            "human_decision_required": True,
            "evidence_status": status,
            "evidence_refs": [f"receipt:{name}"],
        }
        for name, status in (
            ("z-confirmed", "confirmed"),
            ("a-inferred", "inferred"),
            ("b-inferred", "inferred"),
            ("c-inferred", "inferred"),
            ("d-inferred", "inferred"),
        )
    ]
    worker = {
        "role_id": "delivery-closeout-resumption-steward",
        "privacy_class": "C1",
        "candidates": candidates,
    }
    packet = _packet(tmp_path, worker_packets=[worker])
    _validate(packet)
    by_id = {row["bottleneck_id"]: row for row in packet["bottlenecks"]}
    assert by_id[packet["human_asks"][0]["bottleneck_ref"]]["evidence_status"] == "confirmed"
    assert any(row["material"] is True for row in packet["disagreements"])


def test_mission_freshness_and_routine_schedule_are_observed_not_fabricated(tmp_path: Path):
    old_repo = tmp_path / "old-mission"
    old = _missions(old_repo, reviewed_at=NOW - timedelta(days=121))
    assert old[0]["status"] == "stale"
    assert old[0]["problems"] == ["mission_review_expired"]

    sources = _sources()
    sources["scheduled_tasks"]["inspect_scheduler"] = False
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=sources,
        mission_coverage=_missions(tmp_path / "schedule"),
        now=NOW,
    )
    _validate(packet)
    schedule = next(
        row for row in packet["routine_health"] if row["routine_id"] == "scheduled_tasks"
    )
    assert schedule["scheduled"] == "unknown"

    observed = _packet(tmp_path / "observed-schedule")
    schedule = next(
        row for row in observed["routine_health"] if row["routine_id"] == "scheduled_tasks"
    )
    assert schedule["scheduled"] == "scheduled"


def test_mission_schema_rejects_absolute_and_traversal_source_refs():
    for field, value in (
        ("source_evidence", ["C:/private/file.md", "AI_FRONT_DOOR.md"]),
        ("source_evidence", ["../private/file.md", "AI_FRONT_DOOR.md"]),
    ):
        payload = _mission_payload()
        payload[field] = value
        assert schema_validation_problems(payload, ROOT, "repo_missions")


def test_schema_and_semantics_reject_execution_fable_and_score_fields(tmp_path: Path):
    packet = _packet(tmp_path)
    for field, value in (
        ("execution_authorized", True),
        ("approval_granted", True),
        ("score", 100),
    ):
        tampered = deepcopy(packet)
        tampered[field] = value
        assert schema_validation_problems(tampered, ROOT, "portfolio_capacity_review")
        assert capacity.portfolio_capacity_review_semantic_problems(tampered)


def test_semantics_reject_duplicate_human_and_overflow_references(tmp_path: Path):
    packet = _packet(tmp_path / "asks", human_count=2)
    duplicate_ask = deepcopy(packet)
    duplicate_ask["human_asks"][1] = deepcopy(duplicate_ask["human_asks"][0])
    assert "duplicate_human_ask" in capacity.portfolio_capacity_review_semantic_problems(
        duplicate_ask
    )

    overflow_packet = _packet(tmp_path / "overflow", human_count=4)
    overflow_packet["overflow"]["items"].append(
        deepcopy(overflow_packet["overflow"]["items"][0])
    )
    assert "duplicate_overflow_reference" in (
        capacity.portfolio_capacity_review_semantic_problems(overflow_packet)
    )


def test_writer_emits_json_sidecar_only_and_does_not_touch_source_repo(tmp_path: Path):
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    mission_path = _write_mission(source_repo)
    before = mission_path.read_bytes()
    packet = capacity.build_portfolio_capacity_review(
        source_payloads=_sources(),
        mission_coverage=capacity.load_repo_mission_coverage(
            [source_repo], schema_root=ROOT, now=NOW
        ),
        now=NOW,
    )

    outputs = capacity.write_portfolio_capacity_review_output(
        tmp_path / "hub", packet, schema_root=ROOT
    )

    assert mission_path.read_bytes() == before
    assert outputs["output_ref"] == (
        "DAD_DATA_ROOT/processed/reports/portfolio_os/capacity_review.json"
    )
    assert str(tmp_path) not in json.dumps(outputs)
    output_path = (
        capacity.data_path(tmp_path / "hub", "central_reports")
        / "portfolio_os"
        / "capacity_review.json"
    )
    assert output_path.name == "capacity_review.json"
    assert output_path.exists()
    assert not output_path.with_suffix(".html").exists()
