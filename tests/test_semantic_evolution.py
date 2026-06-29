from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.config import LocalSource
from digital_asset_directory.models import AssetRecord
from digital_asset_directory.semantic_evolution import (
    build_semantic_evolution_records,
    write_semantic_evolution_outputs,
)

pytestmark = pytest.mark.integration


def make_asset(asset_id: str, logical_path: str, *, asset_type: str = "schema") -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        source_kind="local",
        asset_type=asset_type,
        title=Path(logical_path).stem,
        logical_path=logical_path,
        content_hash=asset_id,
        metadata_fingerprint=f"metadata:{asset_id}",
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        lifecycle_state="active",
        freshness_status="current",
        trust_zone="source_owned",
        value_score=50,
        value_components={},
        metadata={},
    )


def write_json_file(root: Path, logical_path: str, payload: dict, *, pretty: bool = True) -> None:
    relative = logical_path.removeprefix("local/")
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def test_format_churn_in_temp_copy_is_noise_not_semantic_evolution(tmp_path: Path):
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example/schema.json",
        "title": "Example",
        "type": "object",
        "required": ["id"],
        "properties": {"id": {"type": "string"}, "status": {"enum": ["active", "inactive"]}},
    }
    canonical = "local/repo/schemas/example.schema.json"
    temp = "local/repo/.pytest-tmp-root/pytest-1/test_case/contract-repo/schemas/example.schema.json"
    write_json_file(tmp_path, canonical, schema, pretty=True)
    write_json_file(tmp_path, temp, {"properties": schema["properties"], **{k: v for k, v in schema.items() if k != "properties"}}, pretty=False)
    assets = [
        make_asset("dad:asset:canonical", canonical),
        make_asset("dad:asset:temp", temp),
    ]

    records = build_semantic_evolution_records(
        assets,
        [LocalSource(id="local", path=tmp_path, path_alias="local")],
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    record = records[0]
    assert record.evolution_grade == "none"
    assert record.noise_class == "fixture_lineage_noise"
    assert record.semantic_change_score == 0
    assert record.noise_score > 0.5
    assert "lineage_evidence_for" in record.graph_edge_suggestions


def test_required_and_enum_changes_grade_as_breaking_semantic_evolution(tmp_path: Path):
    old = {
        "type": "object",
        "required": ["id"],
        "properties": {
            "id": {"type": "string"},
            "status": {"type": "string", "enum": ["active", "inactive"]},
        },
    }
    new = {
        "type": "object",
        "required": ["id", "status"],
        "properties": {
            "id": {"type": "string", "pattern": "^EXT_[A-Z0-9]+$"},
            "status": {"type": "string", "enum": ["active"]},
            "source": {"type": "string"},
        },
    }
    old_path = "local/repo/schemas/example.schema.json"
    new_path = "local/repo-v2/schemas/example.schema.json"
    write_json_file(tmp_path, old_path, old)
    write_json_file(tmp_path, new_path, new)
    assets = [
        make_asset("dad:asset:old", old_path),
        make_asset("dad:asset:new", new_path),
    ]

    record = build_semantic_evolution_records(
        assets,
        [LocalSource(id="local", path=tmp_path, path_alias="local")],
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )[0]

    assert record.evolution_grade == "breaking_semantic"
    assert record.semantic_change_score >= 0.85
    assert "status" in record.structural_changes["required_added"]
    assert record.structural_changes["enum_values_removed"]["status"] == ["inactive"]
    assert "semantic_variant_of" in record.graph_edge_suggestions
    assert "evolved_from" in record.graph_edge_suggestions


def test_semantic_evolution_writer_creates_candidate_outputs(tmp_path: Path):
    left = "local/repo/schemas/sample.schema.json"
    right = "local/repo-copy/.pytest-tmp-root/pytest-1/test/sample.schema.json"
    payload = {"type": "object", "properties": {"id": {"type": "string"}}}
    write_json_file(tmp_path, left, payload)
    write_json_file(tmp_path, right, payload, pretty=False)
    assets = [make_asset("dad:asset:left", left), make_asset("dad:asset:right", right)]

    result = write_semantic_evolution_outputs(
        tmp_path,
        assets,
        [LocalSource(id="local", path=tmp_path, path_alias="local")],
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert result["semantic_evolution_count"] == 1
    assert Path(result["outputs"]["semantic_evolution_candidates"]).exists()
    assert Path(result["outputs"]["semantic_evolution_report"]).exists()


def test_semantic_evolution_respects_max_read_bytes(tmp_path: Path):
    left = "local/repo/schemas/large.schema.json"
    right = "local/repo-v2/schemas/large.schema.json"
    payload = {"type": "object", "properties": {"id": {"type": "string"}}}
    write_json_file(tmp_path, left, payload, pretty=False)
    write_json_file(tmp_path, right, {**payload, "description": "x" * 1000})
    assets = [make_asset("dad:asset:left", left), make_asset("dad:asset:right", right)]

    record = build_semantic_evolution_records(
        assets,
        [LocalSource(id="local", path=tmp_path, path_alias="local")],
        scan_id="dad:scan:test",
        max_read_bytes=500,
        generated_at="2026-01-01T00:00:00+00:00",
    )[0]

    assert record.evolution_grade == "insufficient_evidence"
    assert record.evidence["read_status_counts"]["skipped_too_large"] == 1
