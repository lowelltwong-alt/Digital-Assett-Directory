from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.background_connections import (
    build_attention_seeds,
    build_connection_candidates,
    build_expansion_maps,
    connectivity_score,
    run_background_connection_radar,
    select_escalation_packets,
    write_background_connection_outputs,
)
from digital_asset_directory.models import AssetRecord, EdgeRecord

pytestmark = pytest.mark.integration


TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(
    asset_id: str,
    *,
    source_id: str = "source-a",
    asset_type: str = "workflow",
    title: str | None = None,
    logical_path: str | None = None,
    tags: list[str] | None = None,
    capabilities: list[str] | None = None,
    needs: list[str] | None = None,
    freshness: str = "current",
    value_score: float = 70,
    trust_zone: str = "source_owned",
    sensitivity: str = "internal",
    content_hash: str | None = None,
) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id=source_id,
        source_kind="local",
        asset_type=asset_type,
        title=title or asset_id.rsplit(":", maxsplit=1)[-1],
        description="synthetic background connection asset",
        logical_path=logical_path or f"local/repo/{asset_id.rsplit(':', maxsplit=1)[-1]}.md",
        content_hash=content_hash or f"hash-{asset_id}",
        metadata_fingerprint=f"metadata-{asset_id}",
        content_sha256=content_hash or f"sha-{asset_id}",
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        tags=tags or ["governance"],
        capabilities=capabilities or [],
        needs=needs or [],
        outcomes=["validated_reuse"],
        lifecycle_state="active",
        freshness_status=freshness,  # type: ignore[arg-type]
        sensitivity=sensitivity,  # type: ignore[arg-type]
        trust_zone=trust_zone,
        value_score=value_score,
        value_components={},
        confidence="medium",
        metadata={"asset_patterns": ["workflow_composition"]},
    )


def make_edge(
    source: str,
    target: str,
    *,
    edge_type: str = "satisfies_need",
    scan_id: str = SCAN_ID,
) -> EdgeRecord:
    return EdgeRecord(
        edge_id=f"dad:edge:{source}:{target}:{edge_type}",
        edge_type=edge_type,
        source_asset_id=source,
        target_asset_id=target,
        method="test",
        confidence=0.9,
        evidence={"source": "synthetic"},
        created_at=TIMESTAMP,
        scan_id=scan_id,
    )


def test_connectivity_score_formula_is_weighted_and_bounded():
    assert connectivity_score(
        {
            "attention_relevance": 0.5,
            "cold_lift": 1.0,
            "complementarity": 0.4,
            "multi_hop_potential": 0.2,
            "novelty": 0.8,
        }
    ) == pytest.approx(0.56)
    assert connectivity_score(
        {
            "attention_relevance": 9.0,
            "cold_lift": 9.0,
            "complementarity": 9.0,
            "multi_hop_potential": 9.0,
            "novelty": 9.0,
        }
    ) == 1.0


def test_attention_seeds_are_privacy_first_and_deterministic():
    asset = make_asset(
        "dad:asset:hot",
        tags=["roadmap", "calibration"],
        needs=["review_packet"],
    )

    first = build_attention_seeds([asset], scan_id=SCAN_ID, generated_at=TIMESTAMP)
    second = build_attention_seeds([asset], scan_id=SCAN_ID, generated_at=TIMESTAMP)

    assert [record.attention_seed_id for record in first] == [
        record.attention_seed_id for record in second
    ]
    assert first[0].raw_text_persisted is False
    assert first[0].source_kind == "recent_asset"
    assert first[0].evidence["source"] == "catalog_artifact_recency"
    assert "message" not in json.dumps(first[0].model_dump(mode="json")).lower()


def test_gate_before_score_blocks_safety_and_authority_failures():
    hot = make_asset("dad:asset:hot", needs=["review_packet"])
    sensitive = make_asset(
        "dad:asset:sensitive",
        logical_path="local/repo/secrets/private.md",
        capabilities=["review_packet"],
        freshness="stale",
    )
    cross_authority = make_asset(
        "dad:asset:cross",
        source_id="source-b",
        capabilities=["review_packet"],
        freshness="stale",
    )
    seeds = build_attention_seeds([hot], scan_id=SCAN_ID, generated_at=TIMESTAMP)

    candidates = build_connection_candidates(
        [hot, sensitive, cross_authority],
        [],
        seeds,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        tau=0.1,
    )
    by_target = {candidate.target_asset_ids[0]: candidate for candidate in candidates}

    assert by_target["dad:asset:sensitive"].connectivity_score > 0.1
    assert by_target["dad:asset:sensitive"].gates["safety_gate"] is False
    assert by_target["dad:asset:sensitive"].escalation_eligible is False
    assert by_target["dad:asset:cross"].connection_type == "requires_human_gate"
    assert by_target["dad:asset:cross"].gates["authority_gate"] is False
    assert by_target["dad:asset:cross"].escalation_eligible is False


def test_duplicate_similarity_reduces_complementarity_and_novelty():
    hot = make_asset("dad:asset:hot", needs=["review_packet"])
    copy = make_asset(
        "dad:asset:copy",
        capabilities=["review_packet"],
        freshness="stale",
        tags=["governance", "roadmap"],
    )
    duplicate_edge = make_edge(hot.asset_id, copy.asset_id, edge_type="near_duplicate_of")
    seeds = build_attention_seeds([hot], scan_id=SCAN_ID, generated_at=TIMESTAMP)

    candidate = build_connection_candidates(
        [hot, copy],
        [duplicate_edge],
        seeds,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        tau=0.0,
    )[0]

    assert candidate.connection_type == "duplicate_variant_delta"
    assert candidate.component_scores["complementarity"] == 0
    assert candidate.component_scores["novelty"] == 0
    assert candidate.cheap_signal_evidence["duplicate_similarity_penalty"] == 1.0


def test_family_dedup_runs_before_budget_and_cold_reserve_is_honored():
    hot = make_asset("dad:asset:hot", needs=["review_packet"])
    cold_a = make_asset(
        "dad:asset:cold-a",
        capabilities=["review_packet"],
        freshness="stale",
        value_score=35,
    )
    cold_b = make_asset(
        "dad:asset:cold-b",
        capabilities=["review_packet"],
        freshness="stale",
        value_score=34,
    )
    duplicate_edge = make_edge(cold_a.asset_id, cold_b.asset_id, edge_type="near_duplicate_of")
    seeds = build_attention_seeds([hot], scan_id=SCAN_ID, generated_at=TIMESTAMP)
    candidates = build_connection_candidates(
        [hot, cold_a, cold_b],
        [duplicate_edge],
        seeds,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        tau=0.1,
    )

    packets = select_escalation_packets(
        candidates,
        [hot, cold_a, cold_b],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        escalation_budget=1,
        reserve_cold=1,
    )

    assert len(packets) == 1
    assert packets[0].cold_memory_cue == "cold_asset_present"
    assert packets[0].deduped_member_candidate_ids


def test_expansion_maps_are_capped_to_two_hops_and_25_nodes():
    hot = make_asset("dad:asset:hot", needs=["review_packet"])
    cold = make_asset("dad:asset:cold", capabilities=["review_packet"], freshness="stale")
    neighbors = [make_asset(f"dad:asset:n{i}") for i in range(35)]
    candidates = run_background_connection_radar(
        [hot, cold, *neighbors],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        escalation_budget=1,
        reserve_cold=1,
        tau=0.1,
    ).candidates
    packets = select_escalation_packets(
        candidates,
        [hot, cold, *neighbors],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        escalation_budget=1,
        reserve_cold=1,
    )
    edges = [
        make_edge(hot.asset_id, neighbor.asset_id, edge_type="related_to")
        for neighbor in neighbors
    ]

    maps = build_expansion_maps(
        packets,
        edges,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        max_hops=2,
        max_nodes=25,
    )

    assert maps[0].max_hops == 2
    assert len(maps[0].direct_asset_ids) + len(maps[0].second_hop_asset_ids) <= 25
    assert maps[0].review_status == "generated_candidate"


def test_writer_creates_deterministic_generated_outputs_under_processed(tmp_path: Path):
    hot = make_asset("dad:asset:hot", needs=["review_packet"])
    cold = make_asset("dad:asset:cold", capabilities=["review_packet"], freshness="stale")

    first = write_background_connection_outputs(
        tmp_path,
        [hot, cold],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        tau=0.1,
        escalation_budget=1,
        reserve_cold=1,
    )
    candidates_path = Path(first["outputs"]["connection_candidates"])
    first_payload = candidates_path.read_text(encoding="utf-8")
    second = write_background_connection_outputs(
        tmp_path,
        [hot, cold],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        tau=0.1,
        escalation_budget=1,
        reserve_cold=1,
    )

    assert candidates_path.read_text(encoding="utf-8") == first_payload
    assert first["candidate_count"] == second["candidate_count"]
    for path_text in first["outputs"].values():
        path = Path(path_text)
        assert path.exists()
        assert path.is_relative_to(tmp_path / "processed")
