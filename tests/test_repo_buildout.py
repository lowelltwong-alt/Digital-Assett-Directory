from __future__ import annotations

from pathlib import Path

import pytest

from digital_asset_directory.models import AlertRecord, AssetRecord, EdgeRecord
from digital_asset_directory.repo_buildout import (
    build_repo_buildout_plan,
    repo_buildout_priority_score,
    resolve_repo_scope,
    write_repo_buildout_outputs,
)

pytestmark = pytest.mark.integration

TIMESTAMP = "2026-01-01T00:00:00+00:00"
SCAN_ID = "dad:scan:test"


def make_asset(
    asset_id: str,
    path: str,
    *,
    asset_type: str = "document",
    title: str | None = None,
    value_score: float = 60.0,
    capabilities: list[str] | None = None,
    needs: list[str] | None = None,
    tags: list[str] | None = None,
    sensitivity: str = "internal",
) -> AssetRecord:
    parts = path.split("/")
    repository_root = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
    if len(parts) >= 3 and parts[0] == "git-projects" and parts[1].startswith("02_"):
        repository_root = "/".join(parts[:3])
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id="dad:asset:repo-a" if path.startswith("git-projects/repo-a/") else None,
        source_kind="local",
        asset_type=asset_type,
        title=title or Path(path).stem,
        description="synthetic repo buildout asset",
        logical_path=path,
        content_hash=f"hash-{asset_id}",
        metadata_fingerprint=f"metadata-{asset_id}",
        content_sha256=f"sha-{asset_id}",
        size_bytes=100,
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        tags=tags or [],
        capabilities=capabilities or [],
        needs=needs or [],
        outcomes=["repeatable_quality"],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity=sensitivity,  # type: ignore[arg-type]
        trust_zone="source_owned",
        value_score=value_score,
        value_components={},
        confidence="medium",
        metadata={"repository_root": repository_root, "instance_class": "source"},
    )


def make_repo(asset_id: str, path: str, title: str) -> AssetRecord:
    return make_asset(asset_id, path, asset_type="repository", title=title, value_score=65.0)


def make_edge(source: str, target: str, edge_type: str = "satisfies_need") -> EdgeRecord:
    return EdgeRecord(
        edge_id=f"dad:edge:{source}:{target}:{edge_type}",
        edge_type=edge_type,
        source_asset_id=source,
        target_asset_id=target,
        method="test",
        confidence=0.9,
        evidence={"source": "synthetic"},
        created_at=TIMESTAMP,
        scan_id=SCAN_ID,
    )


def make_alert(asset_id: str) -> AlertRecord:
    return AlertRecord(
        alert_id=f"dad:alert:{asset_id}",
        created_at=TIMESTAMP,
        alert_type="orphan_asset",
        severity="medium",
        title="Review orphan asset",
        description="Few graph connections.",
        asset_ids=[asset_id],
        evidence={"value_score": 65.0},
        recommended_action="Review repo-local relationships.",
        scan_id=SCAN_ID,
    )


def repo_assets() -> list[AssetRecord]:
    return [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", "repo-a"),
        make_asset(
            "dad:asset:front",
            "git-projects/repo-a/AI_FRONT_DOOR.md",
            title="AI Front Door",
            value_score=80,
            tags=["governance"],
        ),
        make_asset(
            "dad:asset:schema",
            "git-projects/repo-a/schemas/item.schema.json",
            asset_type="schema",
            value_score=72,
            needs=["validate_contracts"],
        ),
        make_asset(
            "dad:asset:validator",
            "git-projects/repo-a/tests/test_item_schema.py",
            asset_type="test",
            value_score=68,
            capabilities=["validate_contracts"],
        ),
        make_asset(
            "dad:asset:provider",
            "git-projects/repo-a/src/provider.py",
            asset_type="code",
            capabilities=["workflow_runner"],
            value_score=66,
        ),
        make_asset(
            "dad:asset:consumer",
            "git-projects/repo-a/docs/consumer.md",
            asset_type="workflow",
            needs=["workflow_runner"],
            value_score=64,
        ),
        make_asset(
            "dad:asset:external-validator",
            "git-projects/repo-b/tests/test_contract.py",
            asset_type="test",
            title="External Contract Validator",
            value_score=70,
            capabilities=["validate_contracts"],
        ),
    ]


def test_resolve_repo_scope_accepts_repo_key_and_rejects_ambiguous_label():
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a", "repo-a"),
        make_repo("dad:asset:repo-a-copy", "archive/repo-a", "repo-a"),
    ]

    scope = resolve_repo_scope("git-projects/repo-a", assets)

    assert scope["target_repo_key"] == "git-projects/repo-a"
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_repo_scope("repo-a", assets)


def test_priority_score_failed_gate_caps_high_score():
    components = {
        "repo_relevance": 1.0,
        "gap_severity": 1.0,
        "workflow_leverage": 1.0,
        "validation_readiness": 1.0,
        "evidence_strength": 1.0,
        "low_risk_bonus": 1.0,
    }

    score = repo_buildout_priority_score(
        components,
        {
            "evidence_gate": False,
            "source_boundary_gate": True,
            "privacy_gate": True,
            "no_target_mutation_gate": True,
            "no_external_call_gate": True,
            "scan_watermark_gate": True,
        },
    )

    assert score == 25.0


def test_repo_buildout_plan_uses_internal_composition_but_excludes_duplicates():
    assets = repo_assets()
    duplicate = make_asset(
        "dad:asset:provider-copy",
        "git-projects/repo-a/archive/provider.py",
        asset_type="code",
        capabilities=["workflow_runner"],
        value_score=66,
    )
    assets.append(duplicate)
    edges = [make_edge("dad:asset:provider", duplicate.asset_id, "near_duplicate_of")]

    result = build_repo_buildout_plan(
        "git-projects/repo-a",
        assets,
        edges,
        [make_alert("dad:asset:consumer")],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        artifacts={},
        limit=20,
    )

    composition = [
        item
        for item in result["recommendations"]
        if item["recommendation_type"] == "internal_composition"
    ][0]
    assert composition["review_status"] == "generated_candidate"
    assert "dad:asset:provider-copy" not in composition["evidence_asset_ids"]
    assert result["internal_combinations"]
    assert all(
        "provider-copy" not in item["source_path"] for item in result["internal_combinations"]
    )


def test_cross_repo_inspiration_is_human_gated_and_report_only(tmp_path: Path):
    assets = repo_assets()
    artifacts = {
        "workflow_guidance": {
            "review_use_candidates": [
                {
                    "sample_id": "workflow-part-review-001",
                    "part_type": "validator",
                    "asset_pattern_id": "evaluation_contract_system",
                    "representative_path": "git-projects/repo-b/tests/test_contract.py",
                    "dataflow_completeness": "adequate_for_now",
                    "action": "review only",
                }
            ]
        }
    }

    result = build_repo_buildout_plan(
        "git-projects/repo-a",
        assets,
        [],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        artifacts=artifacts,
        limit=20,
    )
    cross_repo = [
        item
        for item in result["recommendations"]
        if item["recommendation_type"] == "cross_repo_inspiration"
    ][0]

    assert cross_repo["cross_repo_inspiration"] is True
    assert cross_repo["risk"] == "high"
    assert cross_repo["human_gates"]
    assert "Generated candidate" in cross_repo["authority_boundary"]

    written = write_repo_buildout_outputs(
        tmp_path,
        "git-projects/repo-a",
        assets,
        [],
        [],
        artifacts=artifacts,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        limit=20,
    )
    for key in ("report", "payload", "fresh_eyes_prompt", "index"):
        path = Path(written[key])
        assert path.exists()
        assert path.is_relative_to(tmp_path / "processed")
    assert written["candidate_only"] is True


def test_missing_optional_inputs_become_warnings_not_failures():
    result = build_repo_buildout_plan(
        "git-projects/repo-a",
        repo_assets(),
        [],
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
        artifacts={},
        limit=10,
    )

    assert result["warnings"]
    assert result["recommendations"]
    assert all(item["review_status"] == "generated_candidate" for item in result["recommendations"])
