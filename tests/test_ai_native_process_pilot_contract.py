from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PM_ROOT = ROOT / "assets/agent-skills/personal-project-management-ops"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _yaml(relative: str) -> dict:
    return yaml.safe_load(_text(relative))


def test_pm_skill_routes_artifact_diagnosis_to_one_bounded_specialist():
    skill = _text("assets/agent-skills/personal-project-management-ops/SKILL.md")
    frontmatter = yaml.safe_load(skill.split("---", 2)[1])
    pack = _yaml("assets/agent-skills/personal-project-management-ops/subagents.yaml")
    library = json.loads(_text("registry/agent-skill-library.json"))
    registered = next(
        row
        for row in library["skills"]
        if row["skill_id"] == "skill:personal-project-management-ops"
    )
    role = next(
        row
        for row in pack["roles"]
        if row["role_id"] == "artifact-proximate-product-catalyst"
    )

    assert "`diagnose-artifact`" in skill
    assert "first runnable artifact" in skill
    assert "first-runnable-artifact product diagnosis" in frontmatter["description"]
    assert any(
        "Diagnose a first runnable artifact" in example
        for example in registered["trigger_examples"]
    )
    assert pack["version"] == "0.3.0"
    assert set(role["required_output"]) >= {
        "current_project_position",
        "intended_user_and_outcome",
        "artifact_evidence_inspected",
        "experience_surface_assessment",
        "routine_purpose_and_expiry_assessment",
        "build_refusal_assessment",
        "smallest_evidence_producing_experiment",
        "learning_velocity_measures",
        "stop_signal",
        "human_decision_needed",
    }
    stops = set(role["stop_conditions"])
    assert {
        "work_allocation_or_artifact_edit_requested",
        "release_or_self_approval_requested",
        "system_mutation_requested",
        "more_than_three_immediate_human_action_asks",
    } <= stops


def test_project_management_contract_keeps_unknowns_and_applicability_explicit():
    contract = _text(
        "assets/agent-skills/personal-project-management-ops/references/"
        "PROJECT_MANAGEMENT_CONTRACT.md"
    )

    for field in (
        "consumer",
        "decision_or_behavior_changed",
        "why_now",
        "risk_caught",
        "retained_human_judgment",
        "evidence_of_value",
        "cost_ceiling",
        "quiet_condition",
        "review_expiry_or_retirement_condition",
        "can_build",
        "should_exist",
        "target_user_and_outcome",
        "what_it_replaces",
        "maintenance_and_attention_cost",
        "smallest_evidence_version",
        "stop_condition",
    ):
        assert field in contract

    for surface in (
        "UI",
        "cockpit",
        "CLI",
        "MCP",
        "API/SDK",
        "error recovery",
        "permissions",
        "rollback",
        "human handoff",
        "agent handoff",
        "next-action guidance",
    ):
        assert f"- {surface}" in contract
    assert "applicable | not_applicable | unknown" in contract
    assert "`unknown`, `not_measured`, or `not_applicable`" in contract
    assert "not proof of product\nvalue" in contract
    assert "no more than three immediate\naction asks" in contract


def test_manual_pilot_has_bounded_entry_exit_and_kill_contract():
    pilot = _text(
        "assets/agent-skills/personal-project-management-ops/references/"
        "AI_NATIVE_PROCESS_PILOT.md"
    )

    assert "Status: candidate manual pilot; not enabled automation." in pilot
    assert "Duration: four weeks" in pilot
    assert "exactly two bounded workstreams" in pilot
    assert "15 minutes per\nworkstream per review" in pilot
    assert "no more than three immediate action asks" in pilot
    assert "no cross-repo writes" in pilot
    assert "transcript ingestion" in pilot
    assert "after six completed workstreams" in pilot
    assert "grows documents without producing clearer decisions" in pilot
    assert "weakens security, privacy, source authority" in pilot
    assert "Telemetry is candidate evidence, not proof of\nbenefit" in pilot
    assert "initial_decision: pilot | watch | reject | unknown" in pilot
    assert (
        "final_disposition: adopt | revise | watch | reject | stop | unknown"
        in pilot
    )
    assert "\ndecision: pilot | watch | reject | unknown\n" not in pilot


def test_ai_native_trigger_specs_satisfy_canonical_contract():
    routines = _yaml("assets/agent-skills/dad-trigger-pattern-radar/routines.yaml")
    assert routines["status"] == "candidate_specs_not_scheduled"
    assert "not enabled automations" in routines["authority_boundary"]
    by_id = {row["routine_id"]: row for row in routines["routines"]}

    expected = {
        "routine-purpose-expiry-review",
        "first-runnable-artifact-review",
        "learning-velocity-followup",
    }
    assert expected <= set(by_id)
    canonical_fields = {
        "pattern_id",
        "pattern_revision_id",
        "revision",
        "status",
        "epistemic_state",
        "problem_or_opportunity",
        "applies_when",
        "does_not_apply_when",
        "required_signals",
        "any_signals",
        "forbidden_signals",
        "counter_signals",
        "suppress_when",
        "transitions",
        "ordered_sequence",
        "grouping_key",
        "temporal_window",
        "minimum_lineage_distinct_occurrences",
        "source_diversity",
        "coverage",
        "deterministic_fields",
        "model_proposed_fields",
        "candidate_action_class",
        "human_gate",
        "prohibited_side_effects",
        "cooldown",
        "expiry",
        "wake_condition",
        "idempotency_key",
        "privacy_class",
        "redaction_rule",
        "expected_benefit",
        "execution_cost",
        "interruption_cost",
        "false_positive_harm",
        "validator",
        "positive_cases",
        "negative_cases",
        "rollback",
        "kill_criteria",
        "feedback_events",
        "historical_replay",
        "lineage_grouped_holdout",
        "drift_state",
    }
    for routine_id in expected:
        routine = by_id[routine_id]
        assert canonical_fields <= set(routine)
        assert routine["pattern_id"] != routine["pattern_revision_id"]
        assert routine["revision"] == 1
        assert routine["status"] == "candidate"
        assert routine["epistemic_state"] in {
            "observed",
            "derived",
            "model-proposed",
            "confirmed",
        }
        assert routine["input_fingerprint"].startswith("sha256_")
        assert "input_fingerprint_unchanged" in routine["suppress_when"]
        assert routine["quiet_when"]
        assert routine["human_gate"].startswith("required_before_")
        assert routine["side_effect_authority"] == "none_candidate_packet_only"
        assert routine["candidate_action"].startswith("suggest_")
        assert routine["candidate_action_class"] == "suggest"
        assert routine["positive_cases"] and routine["negative_cases"]
        assert routine["rollback"] and routine["kill_criteria"]
        assert set(routine["feedback_events"]) == {
            "accept",
            "reject",
            "dismiss",
            "snooze",
            "usefulness",
            "harm",
            "miss",
        }
        assert routine["historical_replay"] == "not_run_candidate_only"
        assert routine["lineage_grouped_holdout"] == "not_run_candidate_only"
        assert routine["drift_state"] == "not_calibrated"

    purpose = by_id["routine-purpose-expiry-review"]
    for material_field in (
        "consumer",
        "decision_or_behavior_changed",
        "why_now",
        "risk_caught",
        "retained_human_judgment",
        "evidence_of_value",
        "cost_ceiling",
        "quiet_condition",
        "quiet_state_evidence",
        "review_expiry_or_retirement_condition",
    ):
        assert material_field in purpose["input_fingerprint"]

    artifact = by_id["first-runnable-artifact-review"]
    assert "planning_only_without_observable_artifact" in artifact["does_not_apply_when"]
    assert "checklist_requires_nonapplicable_surfaces" in artifact["kill_criteria"]
    assert {
        "allocate_work",
        "edit_artifact",
        "release",
        "schedule",
        "notify",
        "mutate_system",
        "cross_repo_write",
        "self_approve",
    } <= set(artifact["prohibited_side_effects"])


def test_pay_forward_surfaces_workflow_telemetry_without_value_claims():
    template = _text("templates/asset-use-feedback.template.md")
    guidance = _text("docs/ASSET_USE_PAY_FORWARD_LOOP.md")
    combined = template + guidance

    for term in (
        "Repeated explanations",
        "Human attention",
        "Unused output",
        "Evidence-to-candidate",
        "Test-to-decision",
        "Use after 30 days",
    ):
        assert term.casefold() in combined.casefold()
    assert "Telemetry is candidate evidence" in template
    assert "not proof of benefit or causation" in guidance
    assert "`observed`, `unknown`, `not_measured`, or `not_applicable`" in guidance
    assert "Every measure has a separate `status`" in template
    telemetry_lines = [
        line
        for line in template.splitlines()
        if line.startswith("- ") and "status/" in line
    ]
    assert len(telemetry_lines) == 9
