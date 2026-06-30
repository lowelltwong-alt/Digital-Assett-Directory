from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.models import AssetRecord, EdgeRecord
from digital_asset_directory.reference_architectures import (
    build_reference_architecture_records,
    classify_architecture_component_roles,
    reference_architecture_score,
    write_reference_architecture_outputs,
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
    tags: list[str] | None = None,
    capabilities: list[str] | None = None,
    needs: list[str] | None = None,
    sensitivity: str = "internal",
    value_score: float = 70.0,
) -> AssetRecord:
    parts = path.split("/")
    repository_root = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id="dad:asset:repo-a" if path.startswith("git-projects/repo-a/") else None,
        source_kind="local",
        asset_type=asset_type,
        title=title or Path(path).stem,
        description="synthetic reference architecture asset",
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


def make_edge(source: str, target: str, edge_type: str = "governed_by") -> EdgeRecord:
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


def reference_assets(*, restricted: bool = False) -> list[AssetRecord]:
    sensitivity = "restricted" if restricted else "internal"
    return [
        make_asset(
            "dad:asset:repo-a",
            "git-projects/repo-a",
            asset_type="repository",
            title="repo-a",
        ),
        make_asset(
            "dad:asset:front",
            "git-projects/repo-a/AI_FRONT_DOOR.md",
            tags=["governance"],
            value_score=82,
        ),
        make_asset(
            "dad:asset:arch",
            "git-projects/repo-a/docs/ARCHITECTURE.md",
            tags=["architecture"],
            value_score=80,
        ),
        make_asset(
            "dad:asset:schema",
            "git-projects/repo-a/schemas/item.schema.json",
            asset_type="schema",
            value_score=74,
        ),
        make_asset(
            "dad:asset:rule",
            "git-projects/repo-a/registry/design-authority.json",
            tags=["governance", "human_gate"],
            sensitivity=sensitivity,
            value_score=73,
        ),
        make_asset(
            "dad:asset:test",
            "git-projects/repo-a/tests/test_item_schema.py",
            asset_type="test",
            capabilities=["validate_contracts"],
            value_score=72,
        ),
        make_asset(
            "dad:asset:workflow",
            "git-projects/repo-a/docs/WORKFLOW.md",
            asset_type="workflow",
            value_score=69,
        ),
    ]


def test_component_role_detection_uses_catalog_metadata():
    roles = classify_architecture_component_roles(
        make_asset("dad:asset:arch", "repo/docs/ARCHITECTURE.md", tags=["design"])
    )

    assert "architecture_docs" in roles
    assert "agent_navigation" not in roles


def test_repo_name_terms_do_not_contaminate_all_child_assets():
    asset = make_asset(
        "dad:asset:script",
        "git-projects/governance-architecture/scripts/build.py",
        asset_type="code",
        title="Build Script",
    )
    asset.metadata["repository_root"] = "git-projects/governance-architecture"

    roles = classify_architecture_component_roles(asset)

    assert "architecture_docs" not in roles
    assert "rules_governance" not in roles


def test_catalog_relative_path_prevents_alias_root_contamination():
    asset = make_asset(
        "dad:asset:script",
        "git-projects/03_World_View/logos-governance-architecture/scripts/build.py",
        asset_type="code",
        title="Build Script",
    )
    asset.metadata["repository_root"] = "03_World_View/logos-governance-architecture"
    asset.metadata["relative_path"] = (
        "03_World_View/logos-governance-architecture/scripts/build.py"
    )

    roles = classify_architecture_component_roles(asset)

    assert "architecture_docs" not in roles
    assert "rules_governance" not in roles


def test_reference_architecture_score_failed_gate_caps_score():
    components = {
        "completeness_score": 1.0,
        "usefulness_score": 1.0,
        "reusability_score": 1.0,
        "composition_score": 1.0,
        "validation_readiness": 1.0,
        "novelty_score": 1.0,
    }

    score = reference_architecture_score(
        components,
        0.0,
        {
            "evidence_gate": True,
            "source_boundary_gate": True,
            "privacy_gate": False,
            "no_content_read_gate": True,
            "no_external_call_gate": True,
            "candidate_only_gate": True,
        },
    )

    assert score == 25.0


def test_reference_architecture_records_are_candidate_only_and_deterministic():
    assets = reference_assets()
    edges = [
        make_edge("dad:asset:front", "dad:asset:arch"),
        make_edge("dad:asset:schema", "dad:asset:test", "tests"),
    ]

    first = build_reference_architecture_records(
        assets,
        edges,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )
    second = build_reference_architecture_records(
        assets,
        edges,
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert [record.model_dump(mode="json") for record in first] == [
        record.model_dump(mode="json") for record in second
    ]
    assert first
    record = first[0]
    assert record.review_status == "generated_candidate"
    assert record.architecture_type == "governance_control_plane"
    assert {"schemas_contracts", "validators_tests", "rules_governance"}.issubset(
        record.component_roles
    )
    assert record.gates["no_content_read_gate"] is True
    assert record.reference_score > 25.0


def test_restricted_component_fails_privacy_gate_and_caps_score():
    records = build_reference_architecture_records(
        reference_assets(restricted=True),
        [],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    assert records
    assert records[0].gates["privacy_gate"] is False
    assert records[0].reference_score <= 25.0
    assert "privacy_gate" in records[0].gate_failures


def test_reference_architecture_outputs_are_generated_under_processed(tmp_path: Path):
    outputs = write_reference_architecture_outputs(
        tmp_path,
        reference_assets(),
        [make_edge("dad:asset:schema", "dad:asset:test", "tests")],
        scan_id=SCAN_ID,
        generated_at=TIMESTAMP,
    )

    for key in ("report", "payload", "candidates", "scan_cycle_events"):
        path = Path(outputs[key])
        assert path.exists()
        assert path.is_relative_to(tmp_path / "processed")
    payload = json.loads(Path(outputs["payload"]).read_text(encoding="utf-8"))
    assert payload["candidate_only"] is True
    assert payload["summary"]["candidate_count"] == 1
    event_lines = Path(outputs["scan_cycle_events"]).read_text(encoding="utf-8").splitlines()
    assert event_lines
    assert json.loads(event_lines[-1])["pass_type"] == "reference_architecture_no_rescan_metadata_pass"
