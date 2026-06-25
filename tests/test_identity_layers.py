from digital_asset_directory.identity_layers import build_asset_chunks, build_identity_layers
from digital_asset_directory.models import AssetRecord

import pytest

pytestmark = pytest.mark.unit


def asset(
    aid: str,
    *,
    excerpt: str = "",
    content_sha256: str | None = None,
    size_bytes: int = 10,
) -> AssetRecord:
    return AssetRecord(
        asset_id=aid,
        revision_id=f"r-{aid}",
        source_id="s",
        source_kind="local",
        asset_type="document",
        title=aid,
        logical_path=f"{aid}.md",
        content_hash=content_sha256 or f"metadata-{aid}",
        metadata_fingerprint=f"metadata-{aid}",
        content_sha256=content_sha256,
        size_bytes=size_bytes,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        tags=[],
        capabilities=[],
        needs=[],
        outcomes=[],
        lifecycle_state="active",
        freshness_status="current",
        trust_zone="source_owned",
        value_score=10,
        value_components={},
        source_provenance={"authority": "test"},
        metadata={"excerpt": excerpt},
    )


def test_asset_chunks_use_text_when_available_and_metadata_otherwise():
    text_asset = asset("text", excerpt="alpha beta gamma")
    metadata_asset = asset("metadata")

    chunks = build_asset_chunks([text_asset, metadata_asset], "scan")

    text_chunk = next(chunk for chunk in chunks if chunk.asset_id == "text")
    metadata_chunk = next(chunk for chunk in chunks if chunk.asset_id == "metadata")
    assert text_chunk.chunk_kind == "text"
    assert text_chunk.text_excerpt == "alpha beta gamma"
    assert metadata_chunk.chunk_kind == "metadata"
    assert metadata_chunk.evidence["authority"].startswith("Metadata")


def test_exact_content_duplicates_emit_cluster_edges_and_delta():
    left = asset("left", content_sha256="same-sha", size_bytes=25)
    right = asset("right", content_sha256="same-sha", size_bytes=25)

    _chunks, clusters, deltas, edges = build_identity_layers([left, right], "scan")

    assert any(cluster.cluster_type == "exact_content_duplicate" for cluster in clusters)
    assert any(delta.delta_type == "exact_duplicate" for delta in deltas)
    assert any(edge.edge_type == "exact_duplicate_of" for edge in edges)
    assert all(edge.review_status == "generated_candidate" for edge in edges)


def test_exact_duplicate_edges_are_bounded_for_large_groups():
    assets = [
        asset(f"asset-{index}", content_sha256="same-sha", size_bytes=25) for index in range(20)
    ]

    _chunks, _clusters, _deltas, edges = build_identity_layers(assets, "scan")

    exact_edges = [edge for edge in edges if edge.edge_type == "exact_duplicate_of"]
    per_asset = {item.asset_id: 0 for item in assets}
    for edge in exact_edges:
        per_asset[edge.source_asset_id] += 1
        per_asset[edge.target_asset_id] += 1
    assert exact_edges
    assert max(per_asset.values()) <= 8


def test_near_duplicates_use_text_chunks_not_metadata_chunks():
    left = asset("left", excerpt="shared workflow agent governance")
    right = asset("right", excerpt="shared workflow agent governance")
    metadata_only = asset("metadata-only")

    _chunks, clusters, deltas, edges = build_identity_layers([left, right, metadata_only], "scan")

    assert any(cluster.cluster_type == "near_duplicate_candidate" for cluster in clusters)
    assert any(delta.delta_type == "near_duplicate_candidate" for delta in deltas)
    assert any(edge.edge_type == "near_duplicate_of" for edge in edges)
    assert not any("metadata-only" in cluster.asset_ids for cluster in clusters)
    near_delta = next(delta for delta in deltas if delta.delta_type == "near_duplicate_candidate")
    assert near_delta.confidence <= 0.8
    assert "MinHash" in near_delta.summary


def test_empty_files_are_not_exact_duplicate_clusters():
    left = asset("left", content_sha256="empty-sha", size_bytes=0)
    right = asset("right", content_sha256="empty-sha", size_bytes=0)

    _chunks, clusters, deltas, edges = build_identity_layers([left, right], "scan")

    assert clusters == []
    assert deltas == []
    assert edges == []


def test_near_duplicates_are_shift_invariant_with_token_shingles():
    left = asset("left", excerpt="alpha beta gamma delta epsilon zeta eta theta")
    right = asset("right", excerpt="intro alpha beta gamma delta epsilon zeta eta theta outro")

    _chunks, clusters, deltas, edges = build_identity_layers([left, right], "scan")

    assert any(cluster.cluster_type == "near_duplicate_candidate" for cluster in clusters)
    assert any(delta.delta_type == "near_duplicate_candidate" for delta in deltas)
    assert any(edge.method == "token_shingle_minhash" for edge in edges)


def test_containment_candidate_when_small_asset_is_inside_larger_asset():
    small = asset("small", excerpt="alpha beta gamma delta")
    large = asset(
        "large",
        excerpt=(
            "intro preface alpha beta gamma delta plus many extra tokens "
            "that make the symmetric jaccard estimate smaller"
        ),
    )

    _chunks, _clusters, deltas, edges = build_identity_layers([small, large], "scan")

    assert any(delta.delta_type == "containment_candidate" for delta in deltas)
    contained = next(edge for edge in edges if edge.edge_type == "contained_in")
    assert contained.source_asset_id == "small"
    assert contained.target_asset_id == "large"
