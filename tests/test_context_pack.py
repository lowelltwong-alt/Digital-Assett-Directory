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


def test_snake_case_asset_matches_natural_language_query():
    target = asset("lpr", "learning_promotion_readiness", [], 10)
    noise = asset("noise", "unrelated_topic", [], 10)

    ranked = rank_assets("learning promotion readiness", [target, noise])

    assert ranked, "expected at least one match for a snake_case title"
    assert ranked[0][1].asset_id == "lpr"


def test_camel_case_asset_matches_natural_language_query():
    target = asset("pc", "PortfolioCockpit", [], 10)
    noise = asset("noise", "SomethingElse", [], 10)

    ranked = rank_assets("portfolio cockpit", [target, noise])

    assert ranked, "expected at least one match for a camelCase title"
    assert ranked[0][1].asset_id == "pc"


def test_exact_underscore_token_query_still_matches():
    target = asset("bll", "budget_learning_loop", [], 10)
    noise = asset("noise", "unrelated_topic", [], 10)

    ranked = rank_assets("budget_learning_loop", [target, noise])

    assert ranked, "exact underscore token query should still match"
    assert ranked[0][1].asset_id == "bll"
