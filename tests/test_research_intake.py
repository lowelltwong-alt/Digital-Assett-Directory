from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

from jsonschema.validators import validator_for
import pytest

from digital_asset_directory.mail_center import compose_asset_suggestion
from digital_asset_directory.research_intake import (
    build_language_playbook_report,
    build_language_frontier_watchlist,
    intake_external_candidate,
    list_intake,
    match_trusted_source,
    promote_intake,
    record_screening,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text())
    return json.loads((ROOT / registry["schemas"][name]).read_text())


def _validate(schema_name: str, payload: dict) -> None:
    schema = _schema(schema_name)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def _intake_hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    (hub / "registry").mkdir(parents=True)
    for rel in (
        "registry/trusted-source-registry.json",
        "registry/dad-offerings-registry.json",
        "registry/agent-skill-library.json",
    ):
        (hub / rel).write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return hub


def _language_hub(tmp_path: Path) -> Path:
    hub = tmp_path / "language-hub"
    (hub / "registry").mkdir(parents=True)
    (hub / "registry" / "language-coding-advantage-registry.json").write_text(
        (ROOT / "registry" / "language-coding-advantage-registry.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    shutil.copytree(
        ROOT / "assets" / "language-coding-playbooks",
        hub / "assets" / "language-coding-playbooks",
    )
    return hub


def _screen_all(hub: Path, intake_id: str) -> None:
    for check in ("prompt_injection", "license", "provenance", "compatibility"):
        record_screening(hub, intake_id, check=check, result="pass", screened_by="human")


def test_trusted_source_registry_validates_and_matches():
    _validate(
        "trusted_source_registry",
        json.loads((ROOT / "registry" / "trusted-source-registry.json").read_text(encoding="utf-8")),
    )
    source, tier = match_trusted_source(ROOT, "https://github.com/trailofbits/skills")
    assert tier == "high_signal"
    assert source["source_id"] == "trailofbits"
    rust_source, rust_tier = match_trusted_source(
        ROOT, "https://blog.rust-lang.org/inside-rust/"
    )
    assert rust_tier == "high_signal"
    assert rust_source["source_id"] == "rust-lang"
    assert rust_source["check_cadence"] == "weekly"
    assert "rust" in rust_source["language_focus"]
    python_source, python_tier = match_trusted_source(ROOT, "https://peps.python.org/pep-0703/")
    assert python_tier == "high_signal"
    assert python_source["source_id"] == "python-core"
    assert python_source["check_cadence"] == "weekly"
    assert "python" in python_source["language_focus"]
    pytest_source, pytest_tier = match_trusted_source(ROOT, "https://docs.pytest.org/en/stable/")
    assert pytest_tier == "high_signal"
    assert pytest_source["source_id"] == "pytest-dev"
    hypothesis_source, hypothesis_tier = match_trusted_source(
        ROOT, "https://hypothesis.readthedocs.io/en/latest/"
    )
    assert hypothesis_tier == "known"
    assert hypothesis_source["source_id"] == "hypothesis"
    rust_fuzz_source, rust_fuzz_tier = match_trusted_source(
        ROOT, "https://rust-fuzz.github.io/book/"
    )
    assert rust_fuzz_tier == "known"
    assert rust_fuzz_source["source_id"] == "rust-fuzz"
    nextest_source, nextest_tier = match_trusted_source(ROOT, "https://nexte.st/")
    assert nextest_tier == "known"
    assert nextest_source["source_id"] == "rust-test-frontier"
    _, unknown_tier = match_trusted_source(ROOT, "https://random-blog.example.com/skill")
    assert unknown_tier == "unknown"
    insecure_source, insecure_tier = match_trusted_source(ROOT, "http://peps.python.org/pep-0703/")
    assert insecure_source is None
    assert insecure_tier == "unknown"


def test_language_frontier_watchlist_routes_python_and_rust_sources():
    rust = build_language_frontier_watchlist(ROOT, language="rust", cadence="weekly")
    rust_rows = {row["source_id"]: row for row in rust["rows"]}
    assert rust["report_id"] == "dad:language-frontier-watchlist"
    assert rust["filters"]["language"] == "rust"
    assert rust_rows["rust-lang"]["cadence_days"] == 7
    assert "blog.rust-lang.org" in rust_rows["rust-lang"]["url_patterns"]
    assert any(
        "rust-buildout-guide" in route["primary_assets"]
        for route in rust_rows["rust-lang"]["language_routes"]
    )
    assert any(
        "dad:harness:language-frontier-research" in route["harness_routes"]
        for route in rust_rows["rust-lang"]["language_routes"]
    )

    python = build_language_frontier_watchlist(ROOT, language="python", cadence="weekly")
    python_rows = {row["source_id"]: row for row in python["rows"]}
    assert python_rows["python-core"]["cadence_days"] == 7
    assert "peps.python.org" in python_rows["python-core"]["url_patterns"]
    assert any(
        "asset:python-ai-advantage-preflight" in route["primary_assets"]
        for route in python_rows["python-core"]["language_routes"]
    )
    assert any(
        "dad:harness:language-frontier-research" in route["harness_routes"]
        for route in python_rows["python-core"]["language_routes"]
    )


def test_language_frontier_watchlist_is_pointer_only_and_mail_safe():
    report = build_language_frontier_watchlist(ROOT, language="rust", limit=3)

    assert report["source_count"] == 3
    assert "pointer-only" in report["authority_boundary"]
    assert "not prove" in report["authority_boundary"]
    for row in report["rows"]:
        assert row["url_patterns"]
        contract = row["candidate_mail_contract"]
        assert contract["dad_need_id"] == "dad:need:language-frontier-signals"
        assert "proof_surface" in contract["required_fields"]
        assert "proof_surface_refs" in contract["required_fields"]
        assert "validation_or_eval_idea" in contract["required_fields"]
        assert "target_dad_surface" in contract["required_fields"]
        assert "copied_third_party_docs" in contract["forbidden_fields"]
        assert "raw_private_rows" in contract["forbidden_fields"]
        assert "benchmark_claim_without_same_workload_evidence" in contract["forbidden_fields"]


def test_language_frontier_watchlist_rejects_unknown_cadence():
    with pytest.raises(ValueError, match="cadence"):
        build_language_frontier_watchlist(ROOT, cadence="daily")


def test_language_playbook_report_exposes_operational_guidance_without_copying_text():
    python = build_language_playbook_report(ROOT, language="python")
    assert python["report_id"] == "dad:language-coding-playbook"
    assert python["language_id"] == "python"
    assert python["recommendable"] is True
    assert "playbook_text" not in python
    assert "profile evidence before performance or Rust claims" in python["must_check"]
    assert "dad:harness:language-frontier-research" in {
        route["harness_id"] for route in python["harness_routes"]
    }
    assert "proof:property-fuzz" in {
        proof["category_id"] for proof in python["proof_surfaces"]
    }
    assert "raw_private_rows" in python["research_intake_packet"]["forbidden_fields"]

    rust = build_language_playbook_report(ROOT, language="rust", include_text=True)
    assert rust["language_id"] == "rust"
    assert "same-scope parity for replacement claims" in rust["must_check"]
    assert "Python keeps orchestration and review authority" in rust["playbook_text"]
    assert "rust-buildout-guide" in rust["primary_assets"]
    assert "dad:harness:rust-shadow-parity" in {
        route["harness_id"] for route in rust["harness_routes"]
    }

    future = build_language_playbook_report(ROOT, language="future-language-template")
    assert future["recommendable"] is False
    assert "official or reviewed source IDs" in future["must_check"]
    assert "template" in future["status"]


def test_language_playbook_report_rejects_unknown_language():
    with pytest.raises(ValueError, match="Available language ids"):
        build_language_playbook_report(ROOT, language="brainwave")


def test_language_playbook_report_rejects_unsafe_manifest_paths(tmp_path: Path):
    hub = _language_hub(tmp_path)
    manifest_path = hub / "assets" / "language-coding-playbooks" / "playbooks.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["playbooks"][0]["path"] = "../secret.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsafe language playbook path"):
        build_language_playbook_report(hub, language="python", include_text=True)

    manifest["playbooks"][0]["path"] = "docs/secret.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="outside assets/language-coding-playbooks"):
        build_language_playbook_report(hub, language="python", include_text=True)


def test_language_playbook_report_rejects_duplicate_rows_and_missing_proofs(
    tmp_path: Path,
):
    hub = _language_hub(tmp_path)
    manifest_path = hub / "assets" / "language-coding-playbooks" / "playbooks.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["playbooks"].append(deepcopy(manifest["playbooks"][0]))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate language playbook row"):
        build_language_playbook_report(hub, language="python")

    shutil.rmtree(hub)
    hub = _language_hub(tmp_path)
    registry_path = hub / "registry" / "language-coding-advantage-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["languages"][0]["proof_surface_refs"].append("proof:missing")
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown proof surfaces"):
        build_language_playbook_report(hub, language=registry["languages"][0]["language_id"])


def test_unknown_source_requires_justification(tmp_path: Path):
    hub = _intake_hub(tmp_path)
    with pytest.raises(ValueError, match="justification"):
        intake_external_candidate(
            hub,
            name="Mystery Skill",
            kind="skill",
            source_url="https://random-blog.example.com/skill",
        )
    result = intake_external_candidate(
        hub,
        name="Mystery Skill",
        kind="skill",
        source_url="https://random-blog.example.com/skill",
        justification="Author is a known kernel maintainer; content reviewed manually.",
    )
    assert result["intake"]["trust_tier"] == "unknown"
    assert result["intake"]["status"] == "quarantined"


def test_screening_gates_promotion_and_failed_check_holds(tmp_path: Path):
    hub = _intake_hub(tmp_path)
    intake = intake_external_candidate(
        hub,
        name="Trail of Bits Mutation Campaign Skill",
        kind="skill",
        source_url="https://github.com/trailofbits/skills",
        notes="Configure mutation testing campaigns.",
    )["intake"]
    with pytest.raises(ValueError, match="screening"):
        promote_intake(
            hub,
            intake["intake_id"],
            approved_by="Lowell",
            approval_id="dad:approval:test-1",
            target="skill_pointer",
        )
    record_screening(
        hub, intake["intake_id"], check="prompt_injection", result="fail", notes="needs rescan"
    )
    assert list_intake(hub, status="quarantined")["intake_count"] == 1
    record_screening(hub, intake["intake_id"], check="prompt_injection", result="pass")
    _screen_all(hub, intake["intake_id"])
    assert list_intake(hub, status="screened")["intake_count"] == 1


def test_promotion_requires_named_human_and_blocks_duplicates(tmp_path: Path):
    hub = _intake_hub(tmp_path)
    intake = intake_external_candidate(
        hub,
        name="Python Underused Idioms AI Coding Card",
        kind="asset",
        source_url="https://github.com/anthropics/example",
        notes="Near-copy of an existing offering.",
    )["intake"]
    _screen_all(hub, intake["intake_id"])
    with pytest.raises(ValueError, match="named human"):
        promote_intake(
            hub,
            intake["intake_id"],
            approved_by="agent",
            approval_id="x",
            target="offering",
        )
    with pytest.raises(ValueError, match="duplicate"):
        promote_intake(
            hub,
            intake["intake_id"],
            approved_by="Lowell",
            approval_id="dad:approval:test-2",
            target="offering",
            capabilities=["idiom_card", "underused_stdlib_guidance"],
        )


def test_promotion_writes_schema_valid_pointer_rows(tmp_path: Path):
    hub = _intake_hub(tmp_path)
    offering_intake = intake_external_candidate(
        hub,
        name="Comprehensive Rust Course Pointer",
        kind="doc",
        source_url="https://google.github.io/comprehensive-rust/",
        license_name="Apache-2.0",
        notes="Canonical structured Rust learning path incl. Idiomatic and Unsafe modules.",
    )["intake"]
    _screen_all(hub, offering_intake["intake_id"])
    promoted = promote_intake(
        hub,
        offering_intake["intake_id"],
        approved_by="Lowell",
        approval_id="dad:approval:test-3",
        target="offering",
        capabilities=["rust_learning_path"],
        task_types=["rust", "learning"],
    )
    assert promoted["intake"]["status"] == "promoted"
    pointer = Path(promoted["pointer_path"])
    assert pointer.exists()
    assert "google.github.io" in pointer.read_text(encoding="utf-8")
    offerings = json.loads(
        (hub / "registry" / "dad-offerings-registry.json").read_text(encoding="utf-8")
    )
    _validate("dad_offering_registry", offerings)
    row = next(
        item
        for item in offerings["offerings"]
        if item["offering_id"] == "dad:offering:external-comprehensive-rust-course-pointer"
    )
    assert row["review_status"] == "reviewed"
    assert row["public_safe"] is False
    assert "https://google.github.io/comprehensive-rust/" in row["source_refs"]

    skill_intake = intake_external_candidate(
        hub,
        name="Trail of Bits Differential Review Skill",
        kind="skill",
        source_url="https://github.com/trailofbits/skills",
        notes="Differential review workflow for security audits.",
    )["intake"]
    _screen_all(hub, skill_intake["intake_id"])
    promoted_skill = promote_intake(
        hub,
        skill_intake["intake_id"],
        approved_by="Lowell",
        approval_id="dad:approval:test-4",
        target="skill_pointer",
        capabilities=["differential_review"],
    )
    library = json.loads(
        (hub / "registry" / "agent-skill-library.json").read_text(encoding="utf-8")
    )
    _validate("agent_skill_library", library)
    skill_row = next(
        item
        for item in library["skills"]
        if item["skill_id"] == "skill:external-trail-of-bits-differential-review-skill"
    )
    assert skill_row["skill_format"] == "pointer_only"
    assert skill_row["checkout_modes"] == ["pointer"]
    assert promoted_skill["registry_ref"].startswith("registry/agent-skill-library.json#")


def test_compose_asset_suggestion_sends_pointer_and_graph_context(tmp_path: Path):
    hub = _intake_hub(tmp_path)
    graph = {
        "generated_at": "2026-07-02T00:00:00+00:00",
        "nodes": [
            {"node_id": "repo:repo-one", "node_type": "repo", "label": "repo-one"},
            {
                "node_id": "offering:dad:offering:python-underused-idioms",
                "node_type": "offering",
                "label": "Python Underused Idioms AI Coding Card",
            },
            {"node_id": "lesson:dad:lesson:x", "node_type": "lesson", "label": "Idiom card prevented zip truncation bug"},
        ],
        "edges": [
            {
                "edge_id": "e1",
                "source": "repo:repo-one",
                "target": "offering:dad:offering:python-underused-idioms",
                "edge_type": "uses_asset",
                "edge_basis": "usage ledger",
                "review_status": "candidate",
            },
            {
                "edge_id": "e2",
                "source": "lesson:dad:lesson:x",
                "target": "offering:dad:offering:python-underused-idioms",
                "edge_type": "about_asset",
                "edge_basis": "lesson evidence",
                "review_status": "candidate",
            },
        ],
    }
    graph_path = hub / "processed" / "learning" / "lesson-graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(json.dumps(graph), encoding="utf-8")

    result = compose_asset_suggestion(
        hub,
        asset_id="dad:offering:python-underused-idioms",
        target_repo="central_only",
        note="Recommended after your postflight mentioned readability work.",
    )
    payload = result["record"]["payload"]
    assert payload["library_path"] == "assets/python-underused-idioms"
    assert payload["library_ref"].startswith("dad://hub/")
    assert payload["version"] == "0.1.0"
    assert payload["delivery_model"].startswith("pointer_not_copy")
    assert payload["graph_context"]["available"] is True
    assert payload["graph_context"]["used_by_repos"] == ["repo-one"]
    assert payload["graph_context"]["lesson_count"] == 1
    assert "use_when" in payload and payload["use_when"]
    with pytest.raises(ValueError, match="Unknown DAD offering"):
        compose_asset_suggestion(hub, asset_id="dad:offering:nope", target_repo="central_only")
