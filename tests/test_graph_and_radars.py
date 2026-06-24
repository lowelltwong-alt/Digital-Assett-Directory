from digital_asset_directory.graph_engine import build_edges
from digital_asset_directory.models import AssetRecord
from digital_asset_directory.radars import detect_synergies, generate_alerts, activation_triggers

import pytest

pytestmark = pytest.mark.unit


def asset(aid, title, capabilities=None, needs=None, outcomes=None, tags=None, value=70):
    return AssetRecord(
        asset_id=aid,
        revision_id=f"r-{aid}",
        source_id="s",
        source_kind="local",
        asset_type="code",
        title=title,
        logical_path=title,
        content_hash=aid,
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        tags=tags or [],
        capabilities=capabilities or [],
        needs=needs or [],
        outcomes=outcomes or [],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=value,
        value_components={},
    )


def test_need_edges_synergy_and_alerts():
    left = asset(
        "a",
        "Orphan Detector",
        ["detect_orphans"],
        ["evaluation_harness"],
        ["higher_discovery"],
        ["graph"],
    )
    right = asset(
        "b", "Evaluation Harness", ["evaluation_harness"], [], ["higher_discovery"], ["evaluation"]
    )
    edges = build_edges([left, right], "scan", threshold=0.9)
    assert any(e.edge_type == "satisfies_need" and e.source_asset_id == "b" for e in edges)
    synergies = detect_synergies([left, right])
    assert synergies and synergies[0].needs_covered == ["evaluation_harness"]
    triggers = activation_triggers([left, right])
    alerts = generate_alerts([left, right], edges, synergies, triggers, "scan", 1, 0.3, 60)
    assert any(a.alert_type == "synergy_candidate" for a in alerts)
