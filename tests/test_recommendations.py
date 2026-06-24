from digital_asset_directory.models import AssetRecord
from digital_asset_directory.recommendations import recommend_skills_and_agents, recommend_swarm


def make_asset(
    aid: str, capability: str = "capture_lessons", need: str | None = None
) -> AssetRecord:
    return AssetRecord(
        asset_id=aid,
        revision_id=f"r-{aid}",
        source_id="s",
        source_kind="local",
        asset_type="workflow",
        title=f"Asset {aid}",
        description="learning loop governance evaluation",
        logical_path=aid,
        content_hash=aid,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        capabilities=[capability],
        needs=[need] if need else [],
        outcomes=["faster_builds"],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=70,
        value_components={},
    )


def test_repeated_capability_becomes_skill_candidate_and_goal_gets_swarm():
    assets = [make_asset(str(index), need="evaluation_harness") for index in range(3)]
    recommendations = recommend_skills_and_agents(assets, repeat_threshold=3)
    assert any(
        record.kind == "skill" and "capture_lessons" in record.capabilities
        for record in recommendations
    )
    swarm = recommend_swarm("learning loop evaluation", assets)
    assert swarm.kind == "swarm"
    assert "lesson and handoff recorder" in swarm.suggested_roles
