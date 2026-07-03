from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for
import pytest

from digital_asset_directory.mail_center import compose_asset_suggestion
from digital_asset_directory.research_intake import (
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
    _, unknown_tier = match_trusted_source(ROOT, "https://random-blog.example.com/skill")
    assert unknown_tier == "unknown"


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
