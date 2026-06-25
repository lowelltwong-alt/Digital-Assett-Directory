from digital_asset_directory.context_pack import rank_assets
from digital_asset_directory.models import AssetRecord

import pytest

pytestmark = pytest.mark.unit


def asset(aid: str, title: str, tags: list[str], value: float) -> AssetRecord:
    return AssetRecord(
        asset_id=aid,
        revision_id=f"r-{aid}",
        source_id="s",
        source_kind="local",
        asset_type="document",
        title=title,
        logical_path=f"{aid}.md",
        content_hash=aid,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        tags=tags,
        capabilities=[],
        needs=[],
        outcomes=[],
        lifecycle_state="active",
        freshness_status="current",
        trust_zone="source_owned",
        value_score=value,
        value_components={},
    )


def test_rank_assets_weights_rare_query_terms_above_common_boilerplate():
    rare = asset("rare", "rareterm", ["common", "rareterm"], 10)
    common = asset("common", "common", ["common"], 100)
    other = asset("other", "other", ["common"], 100)

    ranked = rank_assets("common rareterm", [rare, common, other])

    assert ranked[0][1].asset_id == "rare"
    assert ranked[0][2][0] == "rareterm"
