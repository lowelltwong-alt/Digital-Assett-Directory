import csv
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
    build_proposal_indexes,
    build_proposal_review_queue,
    build_proposal_review_template,
    generate_bottom_up_proposals,
    generate_top_down_proposals,
    import_proposal_review_csv,
    load_generated_proposals,
    load_proposal_reviews,
    run_proposal_engines,
    summarize_proposal_reviews,
    update_proposal_review_file,
    update_proposal_review_record,
    write_proposal_calibration_evidence,
    write_proposal_review_csv,
    write_proposal_review_unblind_map,
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
    lifecycle: str = "active",
    source_kind: str = "local",
    logical_path: str | None = None,
) -> AssetRecord:
    return AssetRecord(
        asset_id=aid,
        revision_id=f"rev-{aid}",
        source_id="local-test",
        source_kind=source_kind,  # type: ignore[arg-type]
        asset_type=asset_type,
        title=f"Asset {aid}",
        description="proposal engine test asset",
        logical_path=logical_path or f"{aid}.md",
        content_hash=aid,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        capabilities=[capability] if capability else [],
        needs=[need] if need else [],
        outcomes=[outcome],
        lifecycle_state=lifecycle,
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


def test_proposal_examples_validate_against_schema_and_model():
    schema = json.loads(Path("schemas/proposal.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    examples = sorted(Path("examples/proposals").glob("*.example.json"))

    assert [path.name for path in examples] == [
        "bottom-up-proposal.example.json",
        "top-down-proposal.example.json",
    ]

    proposals = []
    for path in examples:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(payload)
        proposal = ProposalRecord.model_validate(payload)
        proposals.append(proposal)
        assert proposal.review_status == "generated_candidate"
        assert proposal.evidence
        assert "Generated candidate only" in proposal.authority_boundary
        assert "no source mutation" in proposal.authority_boundary

    assert {proposal.proposal_engine for proposal in proposals} == {
        "bottom_up_self_proposal",
        "top_down_orchestration",
    }


def test_proposal_indexes_include_asset_type_and_lifecycle_for_eligible_assets_only():
    assets = [
        make_asset("workflow-a", asset_type="workflow", lifecycle="active"),
        make_asset("doc-a", asset_type="document", lifecycle="discovered"),
        make_asset("generated-a", asset_type="workflow", source_kind="generated"),
        make_asset("sentinel", asset_type="document", logical_path=".gitkeep"),
    ]

    indexes = build_proposal_indexes(assets, [], [])

    assert [asset.asset_id for asset in indexes.assets_by_type["workflow"]] == ["workflow-a"]
    assert [asset.asset_id for asset in indexes.assets_by_type["document"]] == ["doc-a"]
    assert [asset.asset_id for asset in indexes.assets_by_lifecycle["active"]] == [
        "workflow-a"
    ]
    assert [asset.asset_id for asset in indexes.assets_by_lifecycle["discovered"]] == [
        "doc-a"
    ]
    assert "generated-a" not in indexes.eligible
    assert "sentinel" not in indexes.eligible


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
    assert review.false_positive_reason == ""
    assert review.false_negative_note == ""
    assert review.useful_example_note == ""

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


def test_top_down_proposals_use_lifecycle_index_for_risk_review():
    assets = [
        make_asset("active-workflow", asset_type="workflow", lifecycle="active"),
        make_asset("stale-code", asset_type="code", lifecycle="stale"),
        make_asset("stale-doc", asset_type="document", lifecycle="stale"),
    ]

    proposals = generate_top_down_proposals(assets, [], [], "scan-test", portfolio_limit=5)
    lifecycle_proposals = [
        proposal
        for proposal in proposals
        if proposal.proposal_type == "reduces_risk"
        and proposal.evidence.get("lifecycle_state") == "stale"
    ]

    assert len(lifecycle_proposals) == 1
    proposal = lifecycle_proposals[0]
    assert proposal.review_status == "generated_candidate"
    assert proposal.target_asset_ids == []
    assert set(proposal.source_asset_ids) == {"stale-code", "stale-doc"}
    assert proposal.evidence["asset_type_counts"] == {"code": 1, "document": 1}
    assert "source owner" in proposal.known_risks[0]


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
    assert comparison["combined"]["actionable_experiment_rate"] == 1.0
    assert comparison["combined"]["candidate_status_pass_rate"] == 1.0
    assert comparison["combined"]["authority_boundary_pass_rate"] == 1.0
    assert comparison["combined"]["estimated_review_cost_counts"]
    assert comparison["combined"]["estimated_integration_cost_counts"]
    assert comparison["combined"]["human_usefulness_metrics_available"] is False
    assert comparison["review_sample_engine_counts"]["bottom_up_self_proposal"] == min(
        len(bottom_up), 2
    )
    assert comparison["review_sample_engine_counts"]["top_down_orchestration"] == min(
        len(top_down), 2
    )
    for output in paths.values():
        assert Path(output).exists()
    comparison_text = Path(paths["comparison"]).read_text(encoding="utf-8")
    assert "Proposal Engine Comparison" in comparison_text
    assert "Actionable experiment rate" in comparison_text
    assert "Human usefulness metrics available: **False**" in comparison_text
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


def test_update_proposal_review_record_sets_labels_and_review_status():
    reviews = [
        ProposalReviewRecord(
            review_id="review-1",
            sample_id="review-001",
            proposal_id="proposal-1",
            proposal_engine="bottom_up_self_proposal",
            evidence={"proposal_type": "strengthens_capability"},
        )
    ]
    updated_reviews, updated = update_proposal_review_record(
        reviews,
        sample_id="review-001",
        reviewer="Lowell",
        usefulness="useful",
        safety="safe",
        novelty="novel",
        actionability="actionable",
        decision="accept_candidate",
        notes="Good candidate.",
        false_positive_reason="",
        false_negative_note="No better missing proposal was observed.",
        useful_example_note="Good representative positive example.",
        reviewed_at="2026-01-01T00:00:00+00:00",
    )

    assert updated.review_status == "reviewed"
    assert updated.reviewer == "Lowell"
    assert updated.usefulness == "useful"
    assert updated.safety == "safe"
    assert updated.novelty == "novel"
    assert updated.actionability == "actionable"
    assert updated.decision == "accept_candidate"
    assert updated.false_negative_note == "No better missing proposal was observed."
    assert updated.useful_example_note == "Good representative positive example."
    summary = summarize_proposal_reviews(updated_reviews)
    assert summary["reviewed_count"] == 1
    assert summary["false_negative_note_count"] == 1
    assert summary["useful_example_note_count"] == 1


def test_calibration_note_counts_as_review_signal():
    reviews = [
        ProposalReviewRecord(
            review_id="review-1",
            sample_id="review-001",
            proposal_id="proposal-1",
            proposal_engine="top_down_orchestration",
            evidence={"proposal_type": "research_missing_part"},
        )
    ]

    updated_reviews, updated = update_proposal_review_record(
        reviews,
        sample_id="review-001",
        false_positive_reason="Rejected because it duplicates an existing source-owned path.",
    )
    summary = summarize_proposal_reviews(updated_reviews)

    assert updated.review_status == "reviewed"
    assert updated.false_positive_reason.startswith("Rejected")
    assert summary["reviewed_count"] == 1
    assert summary["false_positive_note_count"] == 1


def test_update_proposal_review_record_rejects_bad_input():
    reviews = [
        ProposalReviewRecord(
            review_id="review-1",
            sample_id="review-001",
            proposal_id="proposal-1",
            proposal_engine="bottom_up_self_proposal",
            evidence={"proposal_type": "strengthens_capability"},
        )
    ]
    for kwargs, expected in [
        ({}, "Provide --sample-id or --proposal-id"),
        ({"sample_id": "missing", "usefulness": "useful"}, "No proposal review record"),
        ({"sample_id": "review-001", "usefulness": "great"}, "Invalid usefulness"),
    ]:
        try:
            update_proposal_review_record(reviews, **kwargs)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("invalid review update should fail")


def test_update_proposal_review_file_rewrites_jsonl(tmp_path: Path):
    review_file = tmp_path / "reviews.jsonl"
    review = ProposalReviewRecord(
        review_id="review-1",
        sample_id="review-001",
        proposal_id="proposal-1",
        proposal_engine="top_down_orchestration",
        evidence={"proposal_type": "research_missing_part"},
    )
    review_file.write_text(json.dumps(review.model_dump(mode="json")) + "\n", encoding="utf-8")

    updated, summary = update_proposal_review_file(
        review_file,
        proposal_id="proposal-1",
        reviewer="Human",
        usefulness="unsure",
        safety="needs_more_review",
        decision="defer",
    )
    loaded = load_proposal_reviews(review_file)

    assert updated.sample_id == "review-001"
    assert loaded[0].reviewer == "Human"
    assert loaded[0].review_status == "reviewed"
    assert summary["reviewed_count"] == 1


def test_review_queue_joins_reviews_to_proposal_context_and_filters():
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
    reviews = build_proposal_review_template(bottom_up, top_down, per_engine_sample=1)
    reviews, _ = update_proposal_review_record(
        reviews,
        sample_id="review-001",
        usefulness="useful",
        safety="safe",
        decision="accept_candidate",
    )

    pending = build_proposal_review_queue(reviews, [*bottom_up, *top_down], status="pending")
    reviewed = build_proposal_review_queue(
        reviews, [*bottom_up, *top_down], status="reviewed", engine="bottom_up_self_proposal"
    )

    assert pending["returned_count"] == 1
    assert pending["items"][0]["proposal_engine"] == "top_down_orchestration"
    assert "rationale" in pending["items"][0]
    assert reviewed["returned_count"] == 1
    assert reviewed["items"][0]["labels"]["usefulness"] == "useful"


def test_review_queue_reports_missing_proposal_records():
    review = ProposalReviewRecord(
        review_id="review-missing",
        sample_id="review-001",
        proposal_id="proposal-missing",
        proposal_engine="bottom_up_self_proposal",
        evidence={"proposal_type": "strengthens_capability"},
    )
    queue = build_proposal_review_queue([review], [], status="pending")

    assert queue["returned_count"] == 0
    assert queue["missing_proposal_count"] == 1
    assert queue["missing_proposal_ids"] == ["proposal-missing"]


def test_load_generated_proposals_reads_both_engine_files(tmp_path: Path):
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
        per_asset_limit=1,
        portfolio_limit=1,
        review_sample=1,
    )
    bottom_path = tmp_path / "bottom.jsonl"
    top_path = tmp_path / "top.jsonl"
    bottom_path.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in bottom_up),
        encoding="utf-8",
    )
    top_path.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in top_down),
        encoding="utf-8",
    )

    loaded = load_generated_proposals(bottom_path, top_path)

    assert len(loaded) == len(bottom_up) + len(top_down)


def test_review_csv_export_and_import_round_trip_labels(tmp_path: Path):
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
        per_asset_limit=1,
        portfolio_limit=1,
        review_sample=1,
    )
    reviews = build_proposal_review_template(bottom_up, top_down, per_engine_sample=1)
    review_file = tmp_path / "reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in reviews),
        encoding="utf-8",
    )
    csv_file = tmp_path / "reviews.csv"
    write_proposal_review_csv(csv_file, reviews, [*bottom_up, *top_down])

    rows = list(csv.DictReader(csv_file.open("r", encoding="utf-8", newline="")))
    rows[0]["reviewer"] = "Human"
    rows[0]["usefulness"] = "useful"
    rows[0]["safety"] = "safe"
    rows[0]["novelty"] = "novel"
    rows[0]["actionability"] = "actionable"
    rows[0]["decision"] = "accept_candidate"
    rows[0]["notes"] = "CSV reviewed."
    rows[0]["false_positive_reason"] = ""
    rows[0]["false_negative_note"] = "CSV reviewer saw a missed adjacent need."
    rows[0]["useful_example_note"] = "CSV reviewer liked this as a positive sample."
    with csv_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    result = import_proposal_review_csv(review_file, csv_file, default_reviewer="Fallback")
    loaded = load_proposal_reviews(review_file)

    assert result["updated_count"] == 1
    assert result["summary"]["reviewed_count"] == 1
    assert loaded[0].reviewer == "Human"
    assert loaded[0].usefulness == "useful"
    assert loaded[0].false_negative_note == "CSV reviewer saw a missed adjacent need."
    assert loaded[0].useful_example_note == "CSV reviewer liked this as a positive sample."
    assert loaded[0].review_status == "reviewed"
    assert loaded[1].review_status == "generated_candidate"


def test_review_csv_import_fails_before_writing_bad_labels(tmp_path: Path):
    review = ProposalReviewRecord(
        review_id="review-1",
        sample_id="review-001",
        proposal_id="proposal-1",
        proposal_engine="bottom_up_self_proposal",
        evidence={"proposal_type": "strengthens_capability"},
    )
    review_file = tmp_path / "reviews.jsonl"
    review_file.write_text(json.dumps(review.model_dump(mode="json")) + "\n", encoding="utf-8")
    csv_file = tmp_path / "reviews.csv"
    csv_file.write_text(
        "sample_id,proposal_id,usefulness,safety,novelty,actionability,decision\n"
        "review-001,proposal-1,great,safe,novel,actionable,accept_candidate\n",
        encoding="utf-8",
    )

    original = review_file.read_text(encoding="utf-8")
    try:
        import_proposal_review_csv(review_file, csv_file)
    except ValueError as exc:
        assert "Invalid usefulness" in str(exc)
    else:
        raise AssertionError("bad CSV labels should fail")
    assert review_file.read_text(encoding="utf-8") == original


def test_blinded_review_csv_hides_engine_and_imports_labels(tmp_path: Path):
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
        per_asset_limit=1,
        portfolio_limit=1,
        review_sample=1,
    )
    reviews = build_proposal_review_template(bottom_up, top_down, per_engine_sample=1)
    review_file = tmp_path / "reviews.jsonl"
    review_file.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in reviews),
        encoding="utf-8",
    )
    csv_file = tmp_path / "blinded.csv"
    unblind_file = tmp_path / "unblind.csv"

    write_proposal_review_csv(csv_file, reviews, [*bottom_up, *top_down], blind=True)
    write_proposal_review_unblind_map(unblind_file, reviews)

    rows = list(csv.DictReader(csv_file.open("r", encoding="utf-8", newline="")))
    assert rows
    assert "proposal_engine" not in rows[0]
    assert "false_positive_reason" in rows[0]
    assert "false_negative_note" in rows[0]
    assert "useful_example_note" in rows[0]
    unblind_rows = list(csv.DictReader(unblind_file.open("r", encoding="utf-8", newline="")))
    assert {row["proposal_engine"] for row in unblind_rows} == {
        "bottom_up_self_proposal",
        "top_down_orchestration",
    }

    rows[0]["reviewer"] = "Human"
    rows[0]["usefulness"] = "useful"
    rows[0]["safety"] = "safe"
    rows[0]["novelty"] = "novel"
    rows[0]["actionability"] = "actionable"
    rows[0]["decision"] = "accept_candidate"
    with csv_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    result = import_proposal_review_csv(review_file, csv_file)

    assert result["updated_count"] == 1
    assert result["summary"]["reviewed_count"] == 1


def make_review(index: int, engine: str, decision: str = "accept_candidate") -> ProposalReviewRecord:
    return ProposalReviewRecord(
        review_id=f"review-{engine}-{index}",
        sample_id=f"review-{index:03d}",
        proposal_id=f"proposal-{engine}-{index}",
        proposal_engine=engine,  # type: ignore[arg-type]
        reviewer="human",
        reviewed_at="2026-01-01T00:00:00+00:00",
        usefulness="useful",
        safety="safe",
        novelty="novel",
        actionability="actionable",
        decision=decision,  # type: ignore[arg-type]
        evidence={"proposal_type": "strengthens_capability"},
        review_status="reviewed",
    )


def test_calibration_evidence_refuses_incomplete_reviews(tmp_path: Path):
    reviews = [make_review(index, "bottom_up_self_proposal") for index in range(25)]
    output = tmp_path / "roadmap" / "evidence" / "proposal-engine-calibration.md"

    try:
        write_proposal_calibration_evidence(tmp_path, reviews, tmp_path / "reviews.jsonl", output)
    except ValueError as exc:
        assert "at least 25 reviewed records from each engine" in str(exc)
    else:
        raise AssertionError("incomplete proposal calibration evidence should fail closed")
    assert not output.exists()


def test_calibration_evidence_requires_structured_notes(tmp_path: Path):
    reviews = [
        *(make_review(index, "bottom_up_self_proposal") for index in range(25)),
        *(make_review(index, "top_down_orchestration", "reject_candidate") for index in range(25)),
    ]
    output = tmp_path / "roadmap" / "evidence" / "proposal-engine-calibration.md"

    try:
        write_proposal_calibration_evidence(
            tmp_path,
            reviews,
            tmp_path / "reviews.jsonl",
            output,
            default_path="hybrid",
            default_rationale="Human chose hybrid after review.",
        )
    except ValueError as exc:
        assert "false positive, false negative, and useful example notes" in str(exc)
    else:
        raise AssertionError("calibration evidence without structured notes should fail closed")
    assert not output.exists()


def test_calibration_evidence_requires_explicit_default_decision(tmp_path: Path):
    reviews = [
        *(make_review(index, "bottom_up_self_proposal") for index in range(25)),
        *(make_review(index, "top_down_orchestration", "reject_candidate") for index in range(25)),
    ]
    reviews[0].useful_example_note = "Human kept this as a strong bottom-up example."
    reviews[26].false_positive_reason = "Human rejected this as duplicative."
    reviews[27].false_negative_note = "Human expected a missing-part proposal for tests."
    output = tmp_path / "roadmap" / "evidence" / "proposal-engine-calibration.md"

    try:
        write_proposal_calibration_evidence(tmp_path, reviews, tmp_path / "reviews.jsonl", output)
    except ValueError as exc:
        assert "--default-path" in str(exc)
    else:
        raise AssertionError("calibration evidence without default path should fail closed")
    assert not output.exists()


def test_calibration_evidence_writes_after_complete_reviews(tmp_path: Path):
    reviews = [
        *(make_review(index, "bottom_up_self_proposal") for index in range(25)),
        *(make_review(index, "top_down_orchestration", "reject_candidate") for index in range(25)),
    ]
    reviews[0].useful_example_note = "Human kept this as a strong bottom-up example."
    reviews[26].false_positive_reason = "Human rejected this as duplicative."
    reviews[27].false_negative_note = "Human expected a missing-part proposal for tests."
    output = tmp_path / "roadmap" / "evidence" / "proposal-engine-calibration.md"
    summary, path = write_proposal_calibration_evidence(
        tmp_path,
        reviews,
        tmp_path / "reviews.jsonl",
        output,
        default_path="bottom-up",
        default_rationale="Human review preferred the accepted bottom-up candidates.",
    )

    assert summary["calibration_gate_complete"] is True
    assert summary["structured_calibration_notes_complete"] is True
    assert Path(path).exists()
    text = Path(path).read_text(encoding="utf-8")
    assert "Proposal Engine Calibration Evidence" in text
    assert "Candidate default path from accepted counts: **bottom_up_self_proposal**" in text
    assert "Human-selected default path: **bottom_up_self_proposal**" in text
    assert "Human review preferred the accepted bottom-up candidates." in text
    assert "False positive notes: **1**" in text
    assert "False negative notes: **1**" in text
    assert "Useful example notes: **1**" in text
    assert "Human rejected this as duplicative." in text
