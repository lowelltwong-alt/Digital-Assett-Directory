from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.asset_families import (
    build_asset_family_candidates,
    build_learning_loop_candidates,
    build_workflow_usefulness_review,
    build_learning_loop_edges,
    build_workflow_sweep_candidates,
    detect_asset_family_matches,
    write_asset_family_reports,
    write_learning_loop_outputs,
    write_workflow_sweep_reports,
)
from digital_asset_directory.models import AssetRecord

pytestmark = pytest.mark.integration


def make_asset(
    asset_id: str,
    *,
    title: str,
    logical_path: str,
    asset_type: str = "document",
    parent_asset_id: str | None = "dad:asset:repo",
    text: str = "",
    tags: list[str] | None = None,
    capabilities: list[str] | None = None,
    value_score: float = 50.0,
) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=parent_asset_id,
        source_kind="local",
        asset_type=asset_type,
        title=title,
        description=text[:200],
        logical_path=logical_path,
        content_hash=asset_id,
        metadata_fingerprint=f"metadata:{asset_id}",
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        tags=tags or [],
        capabilities=capabilities or [],
        outcomes=["repeatable_quality"],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=value_score,
        value_components={},
        metadata={
            "excerpt": text,
            "chunk_text": text,
            "text_tokens": sorted(text.lower().split()),
            "asset_patterns": [],
            "pattern_evidence": {},
        },
    )


def repo_asset() -> AssetRecord:
    return make_asset(
        "dad:asset:repo",
        title="Legal Workflow Repo",
        logical_path="legal-workflow",
        asset_type="repository",
        parent_asset_id=None,
        text="Repository boundary",
        tags=["repository"],
        capabilities=["catalog_assets"],
        value_score=72,
    )


def test_asset_family_recognizer_is_domain_general_not_bible_specific():
    asset = make_asset(
        "dad:asset:legal-route-eval",
        title="Contract Route Evaluation Harness",
        logical_path="legal/evals/contract_route_scorecard.md",
        asset_type="evaluation",
        text=(
            "Route classification sends contract clauses to a chunking context packet. "
            "The scorecard compares expected outputs against a gold case review packet."
        ),
        tags=["evaluation", "retrieval"],
        capabilities=["validate_contracts", "retrieve_context"],
        value_score=61,
    )

    pattern_ids = {match["pattern_id"] for match in detect_asset_family_matches(asset)}

    assert "route_isolated_evaluation_harness" in pattern_ids
    assert "gold_review_packet_system" in pattern_ids


def test_cross_repo_governance_dependency_map_family_is_detected():
    asset = make_asset(
        "dad:asset:governance-map",
        title="Governance Dependency Map",
        logical_path="repo/governance/GOVERNANCE_DEPENDENCY_MAP.yaml",
        asset_type="configuration",
        text=(
            "Governance dependency map with changed path gate, required companion "
            "surfaces, child repo mirror controls, PR description requirements, and "
            "validator-backed upstream governance non-override rules."
        ),
        tags=["governance", "governance-map"],
        capabilities=["govern_agents", "validate_contracts"],
        value_score=68,
    )

    pattern_ids = {match["pattern_id"] for match in detect_asset_family_matches(asset)}

    assert "cross_repo_governance_dependency_map_pattern" in pattern_ids


def test_asset_family_candidates_report_current_score_before_upside():
    assets = [
        repo_asset(),
        make_asset(
            "dad:asset:agent-graph",
            title="Agent Skill Graph",
            logical_path="agents/capability_registry.md",
            asset_type="skill",
            text="Agent skill capability registry and orchestration handoff graph.",
            tags=["agent", "skill", "knowledge-graph"],
            capabilities=["govern_agents", "build_knowledge_graph"],
            value_score=58,
        ),
    ]

    candidates, summary = build_asset_family_candidates(assets)
    agent_graph = next(
        item for item in candidates if item["pattern_id"] == "agent_skill_graph_system"
    )

    assert summary["assets_considered"] == 2
    assert agent_graph["current_score_midpoint"] == 58
    assert agent_graph["upside_score_range"][1] > agent_graph["current_score_midpoint"]
    assert agent_graph["delta_to_upside_midpoint"] > 0


def test_workflow_sweeps_are_governance_first_and_candidate_only():
    assets = [
        repo_asset(),
        make_asset(
            "dad:asset:governance-workflow",
            title="Governance Gate Workflow",
            logical_path="git-projects/00_LawFirm_OS/repo-a/docs/governance-workflow.md",
            asset_type="workflow",
            parent_asset_id=None,
            text=(
                "Preflight postflight human review gate source authority candidate-only "
                "approval and rollback."
            ),
            tags=["governance", "provenance"],
            capabilities=["govern_agents"],
            value_score=74,
        ),
        make_asset(
            "dad:asset:temp-governance-copy",
            title="Temp Governance Copy",
            logical_path="repo/.pytest-tmp-root/pytest-of-Lowell/copy/governance.md",
            asset_type="workflow",
            parent_asset_id=None,
            text="Preflight postflight human review gate source authority approval.",
            tags=["governance"],
            capabilities=["govern_agents"],
            value_score=99,
        ),
        make_asset(
            "dad:asset:second-repo-governance",
            title="Second Repo Governance",
            logical_path="git-projects/03_World_View/repo-b/docs/governance.md",
            asset_type="workflow",
            parent_asset_id=None,
            text="Preflight postflight governance approval source authority.",
            tags=["governance"],
            capabilities=["govern_agents"],
            value_score=60,
        ),
        make_asset(
            "dad:asset:evaluation-workflow",
            title="Evaluation Calibration Workflow",
            logical_path="docs/evaluation-calibration.md",
            asset_type="evaluation",
            text="Gold review packet scorecard calibration precision recall validator.",
            tags=["evaluation"],
            capabilities=["validate_contracts"],
            value_score=63,
        ),
        make_asset(
            "dad:asset:agent-workflow",
            title="Agent Skill Workflow",
            logical_path="agents/skill-orchestration.md",
            asset_type="workflow",
            text="Agent skill capability registry orchestration handoff tool route.",
            tags=["agent", "skill", "workflow"],
            capabilities=["govern_agents"],
            value_score=58,
        ),
    ]

    sweeps, summary = build_workflow_sweep_candidates(assets, review_sample=10)

    assert summary["first_sweep"] == "governance_workflows"
    assert sweeps[0]["sweep_id"] == "governance_workflows"
    assert sweeps[0]["matched_asset_count"] >= 1
    assert sweeps[0]["sample_matches"][0]["review_status"] == "generated_candidate"
    assert any(
        match["asset_id"] == "dad:asset:governance-workflow"
        for match in sweeps[0]["sample_matches"]
    )
    assert sweeps[0]["matched_repository_count"] >= 2
    assert all(
        match["asset_id"] != "dad:asset:temp-governance-copy"
        for match in sweeps[0]["sample_matches"]
    )
    assert summary["noise_assets_excluded"] == 1


def test_workflow_usefulness_review_separates_reuse_from_variant_review():
    assets = [
        repo_asset(),
        make_asset(
            "dad:asset:canonical-governance",
            title="Canonical Governance Workflow",
            logical_path="git-projects/00_LawFirm_OS/governance/docs/review.md",
            asset_type="workflow",
            parent_asset_id=None,
            text="Governance preflight postflight human review source authority approval.",
            tags=["governance"],
            capabilities=["govern_agents"],
            value_score=65,
        ),
        make_asset(
            "dad:asset:archive-governance",
            title="Archived Governance Workflow",
            logical_path="git-projects/99_Archive/zips/governance/docs/review.md",
            asset_type="workflow",
            parent_asset_id=None,
            text="Governance preflight postflight human review source authority approval.",
            tags=["governance"],
            capabilities=["govern_agents"],
            value_score=65,
        ),
    ]

    sweeps, _summary = build_workflow_sweep_candidates(assets, review_sample=10)
    review = build_workflow_usefulness_review(sweeps, per_sweep_limit=10, global_limit=10)
    by_id = {record["asset_id"]: record for record in review["records"]}

    assert by_id["dad:asset:canonical-governance"]["path_class"] == "canonical_or_active_source"
    assert by_id["dad:asset:canonical-governance"]["usefulness_category"] in {
        "review_first_for_reuse",
        "review_after_first_batch",
    }
    assert by_id["dad:asset:archive-governance"]["path_class"] == "archive_variant"
    assert (
        by_id["dad:asset:archive-governance"]["usefulness_category"]
        == "variant_or_delta_review"
    )
    assert by_id["dad:asset:canonical-governance"]["utility_score"] > by_id[
        "dad:asset:archive-governance"
    ]["utility_score"]


def test_learning_loop_candidates_and_edges_are_candidate_only():
    assets = [
        repo_asset(),
        make_asset(
            "dad:asset:expectation",
            title="Workflow Acceptance Test",
            logical_path="tests/test_acceptance.py",
            asset_type="test",
            text="Expectation source with evaluation scorecard and validator contract.",
            capabilities=["validate_contracts"],
        ),
        make_asset(
            "dad:asset:exception",
            title="Failure Case Notes",
            logical_path="docs/failure-case.md",
            asset_type="lesson",
            text="Exception and regression gap with false positive risk.",
            tags=["learning-loop"],
        ),
        make_asset(
            "dad:asset:adaptation",
            title="Candidate Rule Update",
            logical_path="docs/adaptation-proposal.md",
            asset_type="decision",
            text="Adaptation proposal and candidate patch for a rule update.",
        ),
        make_asset(
            "dad:asset:gate",
            title="Human Review Gate",
            logical_path="docs/review-gate.md",
            asset_type="workflow",
            text="Human review gate with preflight postflight governance approval.",
            tags=["governance"],
            capabilities=["govern_agents"],
        ),
        make_asset(
            "dad:asset:promotion",
            title="Validator Promotion Target",
            logical_path="schemas/validator.schema.json",
            asset_type="schema",
            text="Promotion target for validator schema and workflow contract.",
        ),
    ]

    records = build_learning_loop_candidates(
        assets,
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    edges = build_learning_loop_edges(
        records,
        scan_id="dad:scan:test",
        created_at="2026-01-01T00:00:00+00:00",
    )

    assert len(records) == 1
    assert records[0].review_status == "generated_candidate"
    assert records[0].learning_loop_type == "exception_to_adaptation_loop"
    assert "source repositories retain authority" in records[0].authority_boundary
    assert {edge.edge_type for edge in edges} == {
        "produces_learning_signal",
        "requires_human_gate",
        "supports_but_cannot_override",
    }
    assert all(edge.review_status == "generated_candidate" for edge in edges)
    assert all(edge.source_asset_id != edge.target_asset_id for edge in edges)


def test_asset_family_writers_create_generated_outputs(tmp_path: Path):
    assets = [
        repo_asset(),
        make_asset(
            "dad:asset:expectation",
            title="Workflow Acceptance Test",
            logical_path="tests/test_acceptance.py",
            asset_type="test",
            text="Expectation evaluation scorecard gold case validator contract.",
            capabilities=["validate_contracts"],
        ),
        make_asset(
            "dad:asset:exception",
            title="Failure Case Notes",
            logical_path="docs/failure-case.md",
            asset_type="lesson",
            text="Exception failure regression gap false positive risk.",
            tags=["learning-loop"],
        ),
        make_asset(
            "dad:asset:adaptation",
            title="Candidate Rule Update",
            logical_path="docs/adaptation-proposal.md",
            asset_type="decision",
            text="Adaptation proposal candidate patch rule update.",
        ),
        make_asset(
            "dad:asset:gate",
            title="Human Review Gate",
            logical_path="docs/review-gate.md",
            asset_type="workflow",
            text="Human review gate preflight postflight governance approval.",
            tags=["governance"],
            capabilities=["govern_agents"],
        ),
        make_asset(
            "dad:asset:promotion",
            title="Validator Promotion Target",
            logical_path="schemas/validator.schema.json",
            asset_type="schema",
            text="Promotion target validator schema workflow contract.",
        ),
    ]

    family_result = write_asset_family_reports(
        tmp_path,
        assets,
        generated_at="2026-01-01T00:00:00+00:00",
    )
    loop_result = write_learning_loop_outputs(
        tmp_path,
        assets,
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    sweep_result = write_workflow_sweep_reports(
        tmp_path,
        assets,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert Path(family_result["asset_family_report"]).exists()
    assert Path(family_result["logos_report"]).exists()
    assert Path(loop_result["learning_loop_candidates"]).exists()
    assert Path(loop_result["candidate_edges"]).exists()
    assert Path(sweep_result["workflow_sweeps_index"]).exists()
    assert Path(sweep_result["workflow_sweep_reports"]["governance_workflows"]).exists()
    assert Path(sweep_result["workflow_usefulness_report"]).exists()
    assert Path(sweep_result["workflow_usefulness_candidates"]).exists()
    records = [
        json.loads(line)
        for line in Path(loop_result["learning_loop_candidates"]).read_text().splitlines()
    ]
    assert records[0]["review_status"] == "generated_candidate"


def test_new_asset_family_edge_types_are_registered():
    registry = json.loads(Path("registry/edge-type-registry.json").read_text(encoding="utf-8"))
    edge_types = {item["id"] for item in registry["edge_types"]}

    assert {
        "routes_to",
        "handles_form",
        "has_gold_set",
        "has_review_packet",
        "produces_learning_signal",
        "requires_human_gate",
        "archived_variant_of",
        "duplicate_candidate",
        "delta_better_at",
        "composes_with",
        "unsafe_composition_with",
        "contaminates_if_default",
        "supports_but_cannot_override",
    }.issubset(edge_types)
