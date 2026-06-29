from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from digital_asset_directory.models import AssetRecord, EdgeRecord, WorkflowPartRecord
from digital_asset_directory.workflow_parts import (
    build_workflow_part_edges,
    build_workflow_part_records,
    detect_workflow_part_matches,
    write_workflow_part_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(
    asset_id: str,
    *,
    title: str,
    logical_path: str,
    asset_type: str = "document",
    parent_asset_id: str | None = None,
    text: str = "",
    tags: list[str] | None = None,
    capabilities: list[str] | None = None,
    sensitivity: str = "internal",
    content_hash: str | None = None,
    content_sha256: str | None = None,
    value_score: float = 60.0,
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
        content_hash=content_hash or f"hash-{asset_id}",
        metadata_fingerprint=f"metadata-{asset_id}",
        content_sha256=content_sha256,
        size_bytes=100 if content_sha256 else 0,
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        tags=tags or [],
        capabilities=capabilities or [],
        outcomes=["repeatable_quality"],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity=sensitivity,  # type: ignore[arg-type]
        trust_zone="source_owned",
        value_score=value_score,
        value_components={},
        metadata={
            "excerpt": text,
            "chunk_text": text,
            "text_tokens": sorted(text.lower().split()),
            "asset_patterns": [],
        },
    )


def make_duplicate_edge(left: str, right: str) -> EdgeRecord:
    return EdgeRecord(
        edge_id=f"dad:edge:{left}:{right}:near_duplicate_of",
        edge_type="near_duplicate_of",
        source_asset_id=left,
        target_asset_id=right,
        method="test",
        confidence=0.9,
        evidence={"source": "synthetic"},
        created_at=TIMESTAMP,
        scan_id=SCAN_ID,
    )


def test_workflow_part_model_requires_context_bound_safety_fields():
    with pytest.raises(ValidationError):
        WorkflowPartRecord(
            part_id="dad:workflow-part:bad",
            part_type="validator",
            source_asset_ids=["dad:asset:test"],
            asset_pattern_id="evaluation_contract_system",
            role_in_workflow="Checks behavior.",
            authority_boundary="Generated candidate only.",
            evidence={"source": "test"},
            generated_at=TIMESTAMP,
            scan_id=SCAN_ID,
        )


def test_detect_workflow_parts_allows_multiple_roles_without_private_content():
    asset = make_asset(
        "dad:asset:validator",
        title="Schema Validator And Review Gate",
        logical_path="tests/test_schema_contract.py",
        asset_type="test",
        text=(
            "pytest validates JSON schema conformance and requires human review before "
            "promotion through a gate."
        ),
        tags=["governance"],
        capabilities=["validate_contracts"],
    )

    matches = detect_workflow_part_matches(asset)
    part_types = {match["part_type"] for match in matches}

    assert {"validator", "contract", "gate", "human_gate"}.issubset(part_types)
    assert all(match["review_status"] == "generated_candidate" for match in matches)
    assert "pytest validates" not in json.dumps(matches)


def test_workflow_part_records_are_candidate_only_and_skip_noise_or_private_lanes():
    canonical = make_asset(
        "dad:asset:canonical-validator",
        title="Canonical Validator",
        logical_path="repo/tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
    )
    temp_copy = make_asset(
        "dad:asset:temp-validator",
        title="Temp Validator Copy",
        logical_path="repo/.pytest-tmp-root/pytest-of-lowell/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
        value_score=99,
    )
    raw_data = make_asset(
        "dad:asset:raw-data",
        title="Raw Output Validator",
        logical_path="repo/data/output/validator_notes.md",
        asset_type="document",
        text="validator review notes",
    )

    records = build_workflow_part_records(
        [canonical, temp_copy, raw_data],
        [make_duplicate_edge(canonical.asset_id, temp_copy.asset_id)],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert records
    assert all(record.review_status == "generated_candidate" for record in records)
    assert all(record.methodology_version == "workflow-part-recognition-v1" for record in records)
    assert all("dad:asset:temp-validator" not in record.source_asset_ids for record in records)
    assert all("dad:asset:raw-data" not in record.source_asset_ids for record in records)
    assert all(record.maturity == "recognized" for record in records)
    assert all(record.inputs == [] and record.outputs == [] for record in records)


def test_workflow_part_family_dedup_groups_duplicate_canonical_assets():
    left = make_asset(
        "dad:asset:left",
        title="Validator Left",
        logical_path="repo-a/tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
    )
    right = make_asset(
        "dad:asset:right",
        title="Validator Right",
        logical_path="repo-b/tests/test_contract.py",
        asset_type="test",
        text="pytest validator schema conformance fixture.",
        capabilities=["validate_contracts"],
        content_sha256="same-sha",
    )

    records = build_workflow_part_records(
        [left, right],
        [make_duplicate_edge(left.asset_id, right.asset_id)],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    validators = [record for record in records if record.part_type == "validator"]

    assert len(validators) == 1
    assert set(validators[0].source_asset_ids) == {left.asset_id, right.asset_id}
    assert validators[0].confidence in {"medium", "high"}


def test_workflow_part_edges_and_writer_create_generated_outputs(tmp_path: Path):
    asset = make_asset(
        "dad:asset:gate",
        title="Preflight Gate",
        logical_path="docs/preflight-gate.md",
        asset_type="workflow",
        text="preflight postflight human review gate approval stop condition.",
        tags=["governance"],
    )
    records = build_workflow_part_records([asset], [], scan_id=SCAN_ID, generated_at=TIMESTAMP)
    edges = build_workflow_part_edges(records, scan_id=SCAN_ID, created_at=TIMESTAMP)

    assert edges
    assert {edge.edge_type for edge in edges} == {"has_member_asset"}
    assert all(edge.source_asset_id.startswith("dad:workflow-part:") for edge in edges)
    assert all(edge.review_status == "generated_candidate" for edge in edges)

    result = write_workflow_part_outputs(
        tmp_path,
        [asset],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        review_sample=10,
    )

    assert result["candidate_part_count"] == len(records)
    for path_text in result["outputs"].values():
        path = Path(path_text)
        assert path.exists()
        assert path.is_relative_to(tmp_path / "processed")
    payload = Path(result["outputs"]["workflow_parts"]).read_text(encoding="utf-8")
    assert "Generated candidate only" in payload


def test_workflow_part_edge_types_are_registered():
    registry = json.loads(Path("registry/edge-type-registry.json").read_text(encoding="utf-8"))
    edge_types = {item["id"] for item in registry["edge_types"]}

    assert {
        "produces_input_for",
        "substitutes_for",
        "specializes",
        "generalizes",
        "quarantines",
    }.issubset(edge_types)
