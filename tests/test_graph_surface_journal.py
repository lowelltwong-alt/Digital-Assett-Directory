from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from digital_asset_directory.graph_surfaces import (
    graph_surface_checkpoint_plan,
    write_graph_surface_checkpoint_artifacts,
)
from digital_asset_directory.journal import checkpoint_journal
from digital_asset_directory.transport import apply_data_migration, data_path

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _write_ready_lesson_surface(hub: Path) -> tuple[dict, bytes]:
    (hub / "registry").mkdir(parents=True, exist_ok=True)
    (hub / "registry" / "graph-surface-registry.json").write_text(
        (ROOT / "registry" / "graph-surface-registry.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    body = {
        "schema_version": "0.1.0",
        "surface_id": "lesson-graph",
        "nodes": [{"node_id": "lesson:a", "node_type": "lesson", "label": "A"}],
        "edges": [],
        "authority_boundary": "candidate only",
    }
    body_bytes = json.dumps(body, sort_keys=True).encode("utf-8")
    learning_dir = data_path(hub, "learning")
    learning_dir.mkdir(parents=True, exist_ok=True)
    body_path = learning_dir / "lesson-graph.json"
    body_path.write_bytes(body_bytes)
    manifest = {
        "schema_version": "0.1.0",
        "surface_id": "lesson-graph",
        "ontology_id": "knowledge",
        "generated_at": "2026-07-07T00:00:00+00:00",
        "builder_version": "test-builder",
        "graph_path": "processed/learning/lesson-graph.json",
        "manifest_path": "processed/learning/lesson-graph-manifest.json",
        "input_hashes": {},
        "methodology_hashes": {},
        "edge_registry_hash": "missing",
        "graph_content_hash": "missing",
        "freshness": {
            "state": "fresh",
            "computed_at": "2026-07-07T00:00:00+00:00",
            "reasons": [],
        },
        "counts": {"node_count": 1, "edge_count": 0},
        "authority_boundary": "candidate only",
    }
    (learning_dir / "lesson-graph-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    return manifest, body_bytes


def _write_threshold_rows(hub: Path, count: int = 200) -> None:
    inbox = data_path(hub, "central_mail") / "inbox" / "rows.jsonl"
    inbox.parent.mkdir(parents=True, exist_ok=True)
    inbox.write_text(
        "\n".join(json.dumps({"i": i}) for i in range(count)) + "\n",
        encoding="utf-8",
    )


def test_journal_checkpoint_plan_includes_graph_surface_snapshot_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    manifest, _body_bytes = _write_ready_lesson_surface(hub)
    _write_threshold_rows(hub)
    journal_repo = tmp_path / "dad-journal"

    plan = checkpoint_journal(hub, journal_repo, min_records=200, min_hours=999)

    assert plan["checkpoint_skipped_reason"] == "plan_only"
    graph_plan = plan["graph_surfaces"]
    snapshot = next(
        row for row in graph_plan["snapshots"] if row["surface_id"] == "lesson-graph"
    )
    assert snapshot["status"] == "ready"
    assert snapshot["manifest_json"] == manifest
    assert snapshot["body_sha256"].startswith("sha256:")
    assert snapshot["body_gzip_sha256"].startswith("sha256:")
    assert snapshot["body_gzip_snapshot_path"].endswith(".json.gz")
    assert snapshot["body_upload_action"] == "write_gzip"
    assert snapshot["index_row"]["body_sha256"] == snapshot["body_sha256"]
    assert not (hub / "processed" / "reports" / "journal_checkpoint_status.json").exists()
    assert (
        data_root / "processed" / "reports" / "journal_checkpoint_status.json"
    ).exists()


def test_graph_surface_checkpoint_artifacts_write_gzip_and_skip_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    hub = tmp_path / "hub"
    hub.mkdir()
    data_root = tmp_path / "data-root"
    apply_data_migration(hub, data_root)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data_root))
    manifest, body_bytes = _write_ready_lesson_surface(hub)
    journal_repo = tmp_path / "dad-journal"

    first = write_graph_surface_checkpoint_artifacts(hub, journal_repo)
    snapshot = next(
        row for row in first["snapshots"] if row["surface_id"] == "lesson-graph"
    )
    body_path = journal_repo / snapshot["body_gzip_snapshot_path"]
    manifest_path = journal_repo / snapshot["manifest_json_snapshot_path"]
    assert first["written_manifest_count"] == 1
    assert first["written_body_count"] == 1
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert gzip.decompress(body_path.read_bytes()) == body_bytes

    second = graph_surface_checkpoint_plan(hub, journal_repo)
    second_snapshot = next(
        row for row in second["snapshots"] if row["surface_id"] == "lesson-graph"
    )
    assert second_snapshot["body_upload_action"] == "skip_unchanged"
    assert second["skipped_unchanged_body_count"] == 1
