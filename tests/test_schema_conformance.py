import json
from pathlib import Path

from jsonschema.validators import validator_for

from digital_asset_directory.models import (
    AssetChunkRecord,
    AssetDeltaRecord,
    AssetRecord,
    DuplicateClusterRecord,
)

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[1]


def validate_registered_schema(schema_name: str, payload: dict) -> None:
    registry = json.loads((ROOT / "registry" / "schema-registry.json").read_text(encoding="utf-8"))
    schema_path = ROOT / registry["schemas"][schema_name]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(payload)


def test_asset_model_dump_matches_registered_schema():
    record = AssetRecord(
        asset_id="dad:asset:test",
        revision_id="dad:revision:test",
        source_id="local",
        source_kind="local",
        asset_type="document",
        title="Asset",
        logical_path="repo/asset.md",
        content_hash="hash",
        metadata_fingerprint="metadata-hash",
        content_sha256="sha",
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        tags=[],
        capabilities=[],
        needs=[],
        outcomes=[],
        lifecycle_state="active",
        freshness_status="current",
        trust_zone="source_owned",
        value_score=50,
        value_components={},
        source_provenance={"observed_by": "test"},
        metadata={},
    )

    validate_registered_schema("asset", record.model_dump(mode="json"))


def test_identity_layer_model_dumps_match_registered_schemas():
    chunk = AssetChunkRecord(
        chunk_id="dad:chunk:test",
        asset_id="dad:asset:test",
        revision_id="dad:revision:test",
        source_id="local",
        logical_path="repo/asset.md",
        chunk_index=0,
        chunk_kind="text",
        content_hash="hash",
        char_start=0,
        char_end=10,
        text_excerpt="alpha beta",
        evidence={"source": "test"},
        created_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )
    cluster = DuplicateClusterRecord(
        cluster_id="dad:duplicate-cluster:test",
        cluster_type="near_duplicate_candidate",
        asset_ids=["dad:asset:a", "dad:asset:b"],
        methods=["token_shingle_minhash"],
        evidence={"source": "test"},
        confidence=0.7,
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )
    delta = AssetDeltaRecord(
        delta_id="dad:delta:test",
        left_asset_id="dad:asset:a",
        right_asset_id="dad:asset:b",
        delta_type="containment_candidate",
        summary="A is contained in B.",
        shared_chunk_hashes=["shared"],
        left_only_chunk_hashes=[],
        right_only_chunk_hashes=["right-only"],
        evidence={"source": "test"},
        confidence=0.8,
        generated_at="2026-01-01T00:00:00+00:00",
        scan_id="dad:scan:test",
    )

    validate_registered_schema("asset_chunk", chunk.model_dump(mode="json"))
    validate_registered_schema("duplicate_cluster", cluster.model_dump(mode="json"))
    validate_registered_schema("asset_delta", delta.model_dump(mode="json"))
