import pytest

from digital_asset_directory.models import AssetRecord
from digital_asset_directory.scoring import DEFAULT_WEIGHTS, score_asset

pytestmark = pytest.mark.unit

SCORING = {"weights": DEFAULT_WEIGHTS}


def _asset(aid: str, **overrides) -> AssetRecord:
    base = dict(
        asset_id=aid,
        revision_id="r",
        source_id="s",
        source_kind="local",
        asset_type="document",
        title=aid,
        logical_path=f"{aid}.md",
        content_hash="h",
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        lifecycle_state="active",
        freshness_status="current",
        trust_zone="source_owned",
        value_score=0,
        value_components={},
    )
    base.update(overrides)
    return AssetRecord(**base)


def test_provenance_rewards_real_content_hash_over_metadata_only():
    read = _asset("read", content_sha256="abc123", source_provenance={"observed_by": "local_scan"})
    metadata_only = _asset(
        "meta", content_sha256=None, source_provenance={"observed_by": "local_scan"}
    )
    score_asset(read, SCORING)
    score_asset(metadata_only, SCORING)
    # Previously provenance was a constant 0.95 for every asset; now it discriminates.
    assert read.value_components["provenance"] == 95.0
    assert metadata_only.value_components["provenance"] == 55.0


def test_uniqueness_drops_with_duplicate_cluster_size():
    solo = _asset("solo")
    dup = _asset("dup")
    score_asset(solo, SCORING)
    score_asset(dup, SCORING, duplicate_counts={"dup": 4})
    # Previously uniqueness was a hardcoded 0.55 (55.0) for every asset.
    assert solo.value_components["uniqueness"] == 100.0
    assert dup.value_components["uniqueness"] < solo.value_components["uniqueness"]


def test_dead_constants_removed_scores_vary_across_a_mix():
    assets = [
        _asset("a", asset_type="test", content_sha256="x", capabilities=["validate_contracts"]),
        _asset("b", asset_type="document", content_sha256=None),
        _asset("c", asset_type="schema", content_sha256="y", outcomes=["repeatable_quality"]),
    ]
    for asset in assets:
        score_asset(asset, SCORING)
    scores = {asset.value_score for asset in assets}
    # The fixed-constant components no longer collapse distinct assets to one score.
    assert len(scores) == len(assets)


def test_risk_penalties_are_multiplicative_and_unknown_license_is_real():
    safe = _asset(
        "safe",
        source_kind="github",
        asset_type="repository",
        content_sha256="x",
        sensitivity="internal",
        source_provenance={"observed_by": "github_scan"},
        metadata={"license": "MIT"},
    )
    risky = _asset(
        "risky",
        source_kind="github",
        asset_type="repository",
        content_sha256="x",
        sensitivity="internal",
        source_provenance={"observed_by": "github_scan"},
        metadata={},
    )

    score_asset(safe, SCORING)
    score_asset(risky, {"weights": DEFAULT_WEIGHTS, "risk_penalties": {"unknown_license": 0.2}})

    assert risky.value_components["risk_factor"] == 80.0
    assert risky.value_score < safe.value_score


def test_stale_is_only_represented_by_freshness_component():
    current = _asset(
        "current",
        freshness_status="current",
        sensitivity="internal",
        content_sha256="x",
        source_provenance={"observed_by": "test"},
        size_bytes=128,
        metadata={"text_tokens": ["current", "asset"]},
    )
    stale = _asset(
        "stale",
        freshness_status="stale",
        sensitivity="internal",
        content_sha256="x",
        source_provenance={"observed_by": "test"},
        size_bytes=128,
        metadata={"text_tokens": ["stale", "asset"]},
    )

    score_asset(current, {"weights": {"freshness": 1.0}, "risk_penalties": {"stale": 0.9}})
    score_asset(stale, {"weights": {"freshness": 1.0}, "risk_penalties": {"stale": 0.9}})

    assert current.value_score == 100
    assert stale.value_score == 25


def test_temp_fixture_schema_is_discounted_below_source_schema():
    source_schema = _asset(
        "source-schema",
        asset_type="schema",
        logical_path="repo/schemas/claim.schema.json",
        content_sha256="same",
        size_bytes=2048,
        capabilities=["validate_contracts"],
        outcomes=["repeatable_quality"],
        metadata={"text_tokens": ["schema", "contract", "validation"]},
    )
    temp_schema = _asset(
        "temp-schema",
        asset_type="schema",
        logical_path="repo/.pytest-tmp-root/pytest-of-Lowell/pytest-1/test_x/contract-repo/schemas/claim.schema.json",
        content_sha256="same",
        size_bytes=2048,
        capabilities=["validate_contracts"],
        outcomes=["repeatable_quality"],
        metadata={"text_tokens": ["schema", "contract", "validation"]},
    )

    score_asset(source_schema, SCORING, duplicate_counts={"source-schema": 2})
    score_asset(temp_schema, SCORING, duplicate_counts={"temp-schema": 2})

    assert source_schema.value_score > temp_schema.value_score
    assert temp_schema.metadata["instance_class"] == "temp_fixture"
    assert (
        "temp_fixture_lineage_not_independent_value"
        in temp_schema.metadata["score_discount_reasons"]
    )


def test_empty_marker_and_os_junk_floor_out():
    marker = _asset(
        "marker",
        asset_type="code",
        logical_path="repo/eval/__init__.py",
        content_sha256="empty",
        size_bytes=0,
    )
    junk = _asset(
        "junk",
        asset_type="unknown",
        logical_path="repo/.DS_Store",
        content_sha256="junk",
        size_bytes=6148,
    )

    score_asset(marker, SCORING)
    score_asset(junk, SCORING)

    assert marker.value_components["score_discount_factor"] == 25.0
    assert junk.value_components["score_discount_factor"] == 2.0
    assert junk.value_score < marker.value_score


def test_duplicate_non_representative_gets_strong_discount():
    representative = _asset(
        "representative",
        logical_path="repo/a.md",
        content_sha256="same",
        size_bytes=2048,
        metadata={
            "text_tokens": ["validated", "source", "asset"],
            "duplicate_representative_id": "representative",
        },
    )
    copy = _asset(
        "copy",
        logical_path="repo/b.md",
        content_sha256="same",
        size_bytes=2048,
        metadata={
            "text_tokens": ["validated", "source", "asset"],
            "duplicate_representative_id": "representative",
        },
    )

    score_asset(representative, SCORING, duplicate_counts={"representative": 8})
    score_asset(copy, SCORING, duplicate_counts={"copy": 8})

    assert copy.value_score < representative.value_score
    assert "duplicate_non_representative_discount" in copy.metadata["score_discount_reasons"]
