import json
from pathlib import Path

from jsonschema import Draft202012Validator

from digital_asset_directory.models import (
    AlertRecord,
    AssetRecord,
    EdgeRecord,
    ProposalRecord,
    ProposalReviewRecord,
)
from digital_asset_directory.proposals import (
    build_proposal_review_template,
    generate_bottom_up_proposals,
    generate_top_down_proposals,
    load_proposal_reviews,
    run_proposal_engines,
    summarize_proposal_reviews,
    write_proposal_review_results_summary,
    write_proposal_outputs,
)


def make_asset(
    aid: str,
    *,
    asset_type: str = "workflow",
    capability: str | None = None,
    need: str | None = None,
    outcome: str = "faster_builds",
    freshness: str = "current",
) -> AssetRecord:
    return AssetRecord(
        asset_id=aid,
        revision_id=f"rev-{aid}",
        source_id="local-test",
        source_kind="local",
        asset_type=asset_type,
        title=f"Asset {aid}",
        description="proposal engine test asset",
        logical_path=f"{aid}.md",
        content_hash=aid,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        capabilities=[capability] if capability else [],
        needs=[need] if need else [],
        outcomes=[outcome],
        lifecycle_state="active",
        freshness_status=freshness,  # type: ignore[arg-type]
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=70,
        value_components={},
        confidence="medium",
    )


def make_edge(source: str, target: str) -> EdgeRecord:
    return EdgeRecord(
        edge_id=f"edge-{source}-{target}",
        edge_type="satisfies_need",
        source_asset_id=source,
        target_asset_id=target,
        method="test",
        confidence=0.9,
        evidence={"matched": ["evaluation_harness"]},
        created_at="2026-01-01T00:00:00+00:00",
        scan_id="scan-test",
    )


def make_alert(asset_id: str) -> AlertRecord:
    return AlertRecord(
        alert_id=f"alert-{asset_id}",
        created_at="2026-01-01T00:00:00+00:00",
        alert_type="orphan_asset",
        severity="medium",
        title=f"Orphan {asset_id}",
        description="test alert",
        asset_ids=[asset_id],
        evidence={"degree": 0},
        recommended_action="review",
        scan_id="scan-test",
    )


def test_proposal_record_schema_requires_evidence_and_candidate_status():
    proposal = ProposalRecord(
        proposal_id="proposal-1",
        proposal_engine="bottom_up_self_proposal",
        proposal_type="satisfies_need",
        source_asset_ids=["provider"],
        target_asset_ids=["target"],
        need_ids=["evaluation_harness"],
        capability_ids=["evaluation_harness"],
        rationale="Provider may satisfy target need.",
        evidence={"matched_need": "evaluation_harness"},
        smallest_bounded_experiment="Review both assets without changing sources.",
        authority_boundary="Generated candidate only; source repositories retain authority.",
        confidence="medium",
        risk="low",
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="scan-test",
    )
    assert proposal.review_status == "generated_candidate"

    schema = json.loads(Path("schemas/proposal.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(proposal.model_dump(mode="json"))
    invalid = proposal.model_dump(mode="json")
    invalid["evidence"] = {}
    assert list(Draft202012Validator(schema).iter_errors(invalid))


def test_proposal_review_record_schema_supports_unreviewed_template():
    review = ProposalReviewRecord(
        review_id="review-1",
        sample_id="review-001",
        proposal_id="proposal-1",
        proposal_engine="top_down_orchestration",
        evidence={"proposal_type": "research_missing_part"},
    )
    assert review.usefulness == "unreviewed"
    assert review.decision == "pending"

    schema = json.loads(Path("schemas/proposal-review.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(review.model_dump(mode="json"))
    invalid = review.model_dump(mode="json")
    invalid["usefulness"] = "great"
    assert list(Draft202012Validator(schema).iter_errors(invalid))


def test_bottom_up_proposals_are_stable_capped_candidate_and_not_self_matches():
    assets = [
        make_asset("target", need="evaluation_harness"),
        make_asset("provider-a", capability="evaluation_harness"),
        make_asset("provider-b", capability="evaluation_harness"),
    ]
    first = generate_bottom_up_proposals(
        assets, [make_edge("provider-a", "target")], [make_alert("target")], "scan-test", 1
    )
    second = generate_bottom_up_proposals(
        assets, [make_edge("provider-a", "target")], [make_alert("target")], "scan-test", 1
    )

    assert [proposal.proposal_id for proposal in first] == [
        proposal.proposal_id for proposal in second
    ]
    assert all(proposal.review_status == "generated_candidate" for proposal in first)
    assert all(
        not (set(proposal.source_asset_ids) & set(proposal.target_asset_ids))
        for proposal in first
    )
    assert sum("target" in proposal.target_asset_ids for proposal in first) <= 1
    assert any(proposal.proposal_type == "activates_orphan" for proposal in first)


def test_top_down_proposals_respect_portfolio_cap_and_cover_missing_parts():
    assets = [
        make_asset("need-1", need="missing_capability"),
        make_asset("need-2", need="missing_capability"),
        make_asset("provider", capability="evaluation_harness"),
        make_asset("need-3", need="evaluation_harness"),
    ]
    proposals = generate_top_down_proposals(assets, [], [], "scan-test", portfolio_limit=1)

    assert len(proposals) == 1
    assert proposals[0].proposal_engine == "top_down_orchestration"
    assert proposals[0].review_status == "generated_candidate"
    assert not (set(proposals[0].source_asset_ids) & set(proposals[0].target_asset_ids))


def test_run_and_write_proposal_outputs(tmp_path: Path):
    assets = [
        make_asset("target", need="evaluation_harness"),
        make_asset("provider", capability="evaluation_harness"),
    ]
    bottom_up, top_down, comparison = run_proposal_engines(
        assets=assets,
        edges=[make_edge("provider", "target")],
        alerts=[make_alert("target")],
        scan_id="scan-test",
        engine="both",
        per_asset_limit=2,
        portfolio_limit=2,
        review_sample=2,
    )
    paths = write_proposal_outputs(tmp_path, bottom_up, top_down, comparison)

    assert bottom_up
    assert top_down
    assert comparison["combined"]["self_match_violations"] == 0
    assert comparison["combined"]["safety_pass_rate"] == 1.0
    assert comparison["review_sample_engine_counts"]["bottom_up_self_proposal"] == min(
        len(bottom_up), 2
    )
    assert comparison["review_sample_engine_counts"]["top_down_orchestration"] == min(
        len(top_down), 2
    )
    for output in paths.values():
        assert Path(output).exists()
    assert "Proposal Engine Comparison" in Path(paths["comparison"]).read_text(encoding="utf-8")
    assert "Engine labels are hidden" in Path(paths["review_sample"]).read_text(encoding="utf-8")
    assert "Proposal Calibration Summary" in Path(paths["calibration_summary"]).read_text(
        encoding="utf-8"
    )
    review_template = [
        json.loads(line)
        for line in Path(paths["review_template"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {record["proposal_engine"] for record in review_template} == {
        "bottom_up_self_proposal",
        "top_down_orchestration",
    }


def test_review_template_tracks_per_engine_and_human_completion_counts():
    assets = [
        make_asset("target", need="evaluation_harness"),
        make_asset("provider", capability="evaluation_harness"),
    ]
    bottom_up, top_down, _ = run_proposal_engines(
        assets=assets,
        edges=[make_edge("provider", "target")],
        alerts=[make_alert("target")],
        scan_id="scan-test",
        engine="both",
        per_asset_limit=2,
        portfolio_limit=2,
        review_sample=1,
    )
    template = build_proposal_review_template(bottom_up, top_down, per_engine_sample=1)
    assert len(template) == 2
    assert summarize_proposal_reviews(template)["calibration_gate_complete"] is False
    template[0].usefulness = "useful"
    template[0].safety = "safe"
    template[0].actionability = "actionable"
    assert summarize_proposal_reviews(template)["reviewed_count"] == 1


def test_review_summary_loads_filled_jsonl_and_writes_report(tmp_path: Path):
    reviews = [
        ProposalReviewRecord(
            review_id="review-a",
            sample_id="review-001",
            proposal_id="proposal-a",
            proposal_engine="bottom_up_self_proposal",
            usefulness="useful",
            safety="safe",
            novelty="novel",
            actionability="actionable",
            decision="accept_candidate",
            evidence={"proposal_type": "strengthens_capability"},
        ),
        ProposalReviewRecord(
            review_id="review-b",
            sample_id="review-002",
            proposal_id="proposal-b",
            proposal_engine="top_down_orchestration",
            usefulness="not_useful",
            safety="needs_more_review",
            novelty="already_known",
            actionability="not_actionable",
            decision="reject_candidate",
            evidence={"proposal_type": "research_missing_part"},
        ),
    ]
    review_file = tmp_path / "reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(review.model_dump(mode="json")) + "\n" for review in reviews),
        encoding="utf-8",
    )

    loaded = load_proposal_reviews(review_file)
    summary, output = write_proposal_review_results_summary(tmp_path, loaded, review_file)

    assert summary["reviewed_count"] == 2
    assert summary["usefulness_counts"]["useful"] == 1
    assert summary["decision_counts"]["reject_candidate"] == 1
    assert Path(output).exists()
    assert "Proposal Review Results Summary" in Path(output).read_text(encoding="utf-8")
