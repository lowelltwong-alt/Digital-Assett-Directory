from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory.architecture_consult import write_architecture_consult_outputs
from digital_asset_directory.asset_families import (
    write_asset_family_reports,
    write_learning_loop_outputs,
)
from digital_asset_directory.background_connections import write_background_connection_outputs
from digital_asset_directory.ci_release_scope import write_ci_release_artifact_scope_outputs
from digital_asset_directory.config import LocalSource
from digital_asset_directory.governance_map_scope import write_governance_map_adoption_scope_outputs
from digital_asset_directory.models import AssetRecord
from digital_asset_directory.priority_content_lessons import write_priority_content_lesson_outputs
from digital_asset_directory.priority_content_scope import (
    write_priority_content_extract_outputs,
    write_priority_content_extract_scope_outputs,
)
from digital_asset_directory.public_safe_sweep import write_public_safe_source_sweep
from digital_asset_directory.reference_architectures import write_reference_architecture_outputs
from digital_asset_directory.repo_learning_scope import write_repo_learning_loop_install_scope_outputs
from digital_asset_directory.transport import apply_data_migration
from digital_asset_directory.workflow_parts import write_workflow_part_outputs

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
    value_score: float = 70.0,
    parent_asset_id: str | None = "dad:asset:repo-a",
) -> AssetRecord:
    root = "/".join(path.split("/")[:2])
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=parent_asset_id,
        source_kind="local",
        asset_type=asset_type,
        title=title or Path(path).stem,
        description="synthetic data-root generated writer asset",
        logical_path=path,
        content_hash=f"hash-{asset_id}",
        metadata_fingerprint=f"metadata-{asset_id}",
        content_sha256=f"sha-{asset_id}",
        size_bytes=100,
        first_seen_at=TIMESTAMP,
        last_seen_at=TIMESTAMP,
        modified_at=TIMESTAMP,
        tags=tags or ["governance"],
        capabilities=capabilities or [],
        needs=needs or [],
        outcomes=["repeatable_quality"],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=value_score,
        value_components={},
        confidence="medium",
        metadata={
            "repository_root": root,
            "instance_class": "source",
            "excerpt": "preflight postflight governance schema workflow",
            "chunk_text": "preflight postflight governance schema workflow",
            "text_tokens": ["preflight", "postflight", "governance", "schema", "workflow"],
            "asset_patterns": [],
            "pattern_evidence": {},
        },
    )


def make_repo(asset_id: str, path: str) -> AssetRecord:
    return make_asset(
        asset_id,
        path,
        asset_type="repository",
        title=Path(path).name,
        parent_asset_id=None,
    )


def observation() -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "observation_id": "obs:1",
        "approval_id": "approval:test",
        "methodology_version": "priority-content-extract-v0.1",
        "repo_key": "git-projects/repo-a",
        "asset_id": "dad:asset:agents",
        "logical_path": "git-projects/repo-a/AGENTS.md",
        "relative_path": "AGENTS.md",
        "category_id": "ai_navigation",
        "asset_type": "document",
        "content_read_bytes": 100,
        "content_truncated": False,
        "redaction_count": 0,
        "content_excerpt": "Read first. Run preflight and postflight.",
        "content_token_sample": ["preflight", "postflight"],
        "signal_counts": {"ai_navigation": 2},
        "signal_tags": ["ai_navigation"],
        "evidence": {"candidate_only": True},
        "authority_boundary": "Generated bounded content observations only.",
        "generated_at": TIMESTAMP,
        "scan_id": SCAN_ID,
        "review_status": "generated_candidate",
    }


def assert_under(path_text: str, root: Path, relative: str) -> None:
    path = Path(path_text)
    assert path.exists()
    assert path.is_relative_to(root / relative)


def test_generated_writer_family_uses_initialized_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))

    source_root = tmp_path / "sources"
    repo = source_root / "repo-a"
    repo.mkdir(parents=True)
    (repo / "AGENTS.md").write_text(
        "Read first. Run preflight and postflight. API_KEY=SECRET_VALUE_12345\n",
        encoding="utf-8",
    )
    source = LocalSource(
        id="git-projects",
        path=source_root,
        path_alias="git-projects",
        enabled=True,
        max_file_bytes=200,
    )
    assets = [
        make_repo("dad:asset:repo-a", "git-projects/repo-a"),
        make_asset(
            "dad:asset:agents",
            "git-projects/repo-a/AGENTS.md",
            capabilities=["review_packet"],
            needs=["human_review"],
            value_score=82.0,
        ),
        make_asset("dad:asset:schema", "git-projects/repo-a/schemas/item.schema.json", asset_type="schema"),
        make_asset("dad:asset:test", "git-projects/repo-a/tests/test_item.py", asset_type="test"),
    ]

    priority_scope = write_priority_content_extract_scope_outputs(
        hub, assets, [source], scan_id=SCAN_ID, generated_at=TIMESTAMP
    )
    priority_extract = write_priority_content_extract_outputs(
        hub,
        [source],
        approval_id="approval:test",
        repo_keys=["git-projects/repo-a"],
        category_ids=["ai_navigation"],
        scan_id=SCAN_ID,
        max_bytes_per_file=120,
        generated_at=TIMESTAMP,
    )
    repo_learning = write_repo_learning_loop_install_scope_outputs(
        hub, assets, [source], scan_id=SCAN_ID, generated_at=TIMESTAMP
    )
    ci_release = write_ci_release_artifact_scope_outputs(
        hub, assets, [source], scan_id=SCAN_ID, generated_at=TIMESTAMP
    )
    governance = write_governance_map_adoption_scope_outputs(
        hub, assets, [source], scan_id=SCAN_ID, generated_at=TIMESTAMP
    )
    background = write_background_connection_outputs(
        hub, assets, [], scan_id=SCAN_ID, generated_at=TIMESTAMP, tau=0.0
    )
    family = write_asset_family_reports(hub, assets, generated_at=TIMESTAMP)
    loops = write_learning_loop_outputs(hub, assets, scan_id=SCAN_ID, generated_at=TIMESTAMP)
    reference = write_reference_architecture_outputs(
        hub, assets, [], scan_id=SCAN_ID, generated_at=TIMESTAMP
    )
    workflow = write_workflow_part_outputs(hub, assets, [], scan_id=SCAN_ID, generated_at=TIMESTAMP)
    public_sweep = write_public_safe_source_sweep(
        hub, source_root, source_id="source", generated_at=TIMESTAMP
    )

    observations_path = data_root / "processed" / "learning" / "priority_content_observations.jsonl"
    observations_path.parent.mkdir(parents=True, exist_ok=True)
    observations_path.write_text(json.dumps(observation()) + "\n", encoding="utf-8")
    lessons = write_priority_content_lesson_outputs(hub, scan_id=SCAN_ID, generated_at=TIMESTAMP)

    intent = hub / "intent.md"
    intent.write_text(
        "New repo purpose: governed AI workflow control plane\n"
        "Domain: internal developer tools\n"
        "Risk level: medium\n",
        encoding="utf-8",
    )
    consult = write_architecture_consult_outputs(hub, intent, generated_at=TIMESTAMP)

    report_paths = [
        *priority_scope["outputs"].values(),
        priority_extract["outputs"]["report_markdown"],
        priority_extract["outputs"]["report_json"],
        *repo_learning["outputs"].values(),
        *ci_release["outputs"].values(),
        *governance["outputs"].values(),
        background["outputs"]["connection_report"],
        background["outputs"]["packet_report"],
        family["asset_family_report"],
        family["logos_report"],
        loops["learning_loop_report"],
        reference["report"],
        reference["payload"],
        workflow["outputs"]["report"],
        workflow["outputs"]["review_sample"],
        public_sweep["report"],
        public_sweep["record"],
        lessons["outputs"]["report_markdown"],
        lessons["outputs"]["report_json"],
        consult["report"],
        consult["payload"],
        consult["seed_prompt"],
    ]
    learning_paths = [
        priority_extract["outputs"]["observations"],
        background["outputs"]["attention_seeds"],
        background["outputs"]["connection_candidates"],
        background["outputs"]["escalation_packets"],
        background["outputs"]["expansion_maps"],
        loops["learning_loop_candidates"],
        loops["candidate_edges"],
        reference["candidates"],
        reference["scan_cycle_events"],
        workflow["outputs"]["workflow_parts"],
        workflow["outputs"]["candidate_edges"],
        lessons["outputs"]["lesson_candidates"],
    ]

    for path in report_paths:
        assert_under(path, data_root, "processed/reports")
    for path in learning_paths:
        assert_under(path, data_root, "processed/learning")
    assert not (hub / "processed" / "reports" / "priority_content_extract_scope.json").exists()
    assert not (hub / "processed" / "learning" / "priority_content_observations.jsonl").exists()
