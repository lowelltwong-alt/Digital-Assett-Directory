from __future__ import annotations

import json
import shutil
from pathlib import Path

import jsonschema

from digital_asset_directory.source_knowledge_ingestion import (
    _copy_safety_errors,
    classify_candidate,
    validate_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "assets/source-knowledge-ingestion/snapshots/albert"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_albert_snapshot_validates_and_accounts_for_every_tracked_path() -> None:
    result = validate_snapshot(SNAPSHOT)
    assert result["valid"], result["errors"]
    assert result["tracked_path_count"] == 4426
    assert result["candidate_count"] == 1424
    assert result["privacy_excluded_count"] == 3002
    assert result["knowledge_record_count"] == 552


def test_snapshot_manifest_and_graph_validate_against_registered_schemas() -> None:
    jsonschema.validate(_json(SNAPSHOT / "manifest.json"), _json(ROOT / "schemas/source-knowledge-ingestion.schema.json"))
    jsonschema.validate(_json(SNAPSHOT / "knowledge-graph.json"), _json(ROOT / "schemas/source-knowledge-graph.schema.json"))
    jsonschema.validate(_json(ROOT / "registry/source-knowledge-ingestion-registry.json"), _json(ROOT / "schemas/source-knowledge-ingestion-registry.schema.json"))


def test_ingestion_report_is_bound_to_the_current_snapshot_outputs() -> None:
    manifest = _json(SNAPSHOT / "manifest.json")
    report = _json(ROOT / "roadmap/evidence/albert-source-knowledge-ingestion-report.json")
    assert report["output_hashes"] == manifest["output_hashes"]
    assert report["coverage"]["tracked_paths"] == manifest["tracked_path_count"]
    assert report["coverage"]["candidate_paths"] == manifest["candidate_count"]
    assert report["coverage"]["privacy_excluded_paths"] == manifest["privacy_excluded_count"]
    assert report["coverage"]["normalized_knowledge_records"] == manifest["knowledge_record_count"]
    assert report["coverage"]["graph_nodes"] == manifest["graph_node_count"]
    assert report["coverage"]["graph_edges"] == manifest["graph_edge_count"]


def test_privacy_exclusions_are_opaque_and_never_copied() -> None:
    inventory = _jsonl(SNAPSHOT / "inventory.jsonl")
    excluded = [row for row in inventory if row.get("privacy_family")]
    assert len(excluded) == 3002
    assert all(row["source_path"] is None for row in excluded)
    assert all(row["disposition"] == "privacy_excluded_metadata_only" for row in excluded)
    copied = {path.relative_to(SNAPSHOT / "copies").as_posix() for path in (SNAPSHOT / "copies").rglob("*") if path.is_file()}
    assert not any(path.startswith(("source/", "outputs/", "reports/", "simulation/output/")) for path in copied)


def test_source_specific_domain_registries_are_normalized_and_hash_only() -> None:
    manifest = _json(SNAPSHOT / "manifest.json")
    for path in (
        "config/digital_asset_catalog.json",
        "config/legal_case_edge_type_registry.json",
        "registries/litigation_witness_prep_technique_registry.v1.json",
    ):
        assert path in manifest["approved_read_hashes"]
        assert path not in manifest["approved_copy_hashes"]
        assert not (SNAPSHOT / "copies" / path).exists()


def test_front_doors_and_enrollment_are_hash_bound_not_verbatim_copies() -> None:
    manifest = _json(SNAPSHOT / "manifest.json")
    for path in ("AGENTS.md", "AI_FRONT_DOOR.md", "AI_TOC.md", ".digital-asset/dad-integration.json"):
        assert path in manifest["approved_read_hashes"]
        assert path not in manifest["approved_copy_hashes"]
        assert not (SNAPSHOT / "copies" / path).exists()
    assert manifest["sanitization_findings"][".digital-asset/dad-integration.json"] == ["absolute_private_path"]


def test_ci_lesson_is_deduplicated_to_existing_dad_rule() -> None:
    records = _jsonl(SNAPSHOT / "knowledge-records.jsonl")
    lesson = next(row for row in records if row["source_id"] == "ALBERT-LESSON-072")
    assert lesson["dedupe_status"] == "deduplicated_as_source_provenance_for_existing_dad_rule"
    assert "learning-rule:ci-tests-follow-declared-module-dependency-edges" in lesson["dedupe_refs"]
    assert lesson["review_status"] == "generated_candidate"


def test_candidate_graph_is_closed_and_uses_registered_ingestion_edges() -> None:
    graph = _json(SNAPSHOT / "knowledge-graph.json")
    nodes = {node["node_id"] for node in graph["nodes"]}
    assert all(edge["source"] in nodes and edge["target"] in nodes for edge in graph["edges"])
    assert {"source_snapshot_of", "extracted_from"}.issubset({edge["edge_type"] for edge in graph["edges"]})
    assert all(node.get("review_status") != "promoted" for node in graph["nodes"])


def test_negative_path_classification_fails_closed() -> None:
    assert classify_candidate("source/raw/client-record.txt") == "rejected-or-unsafe"
    assert classify_candidate("outputs/cases/matter/witness.json") == "rejected-or-unsafe"
    assert classify_candidate("ai_workland/generated/file_manifest.json") == "private-reference-only"
    assert classify_candidate("tests/test_ci_contract.py") == "test-or-evaluation-pack"


def test_every_declared_negative_fixture_executes(tmp_path: Path) -> None:
    fixtures = _json(ROOT / "tests/fixtures/source_knowledge_ingestion/negative-cases.json")["cases"]
    assert {case["id"] for case in fixtures} == {
        "raw-source-content",
        "case-output",
        "private-reference",
        "credential-copy",
        "absolute-path-copy",
        "silent-promotion",
        "dangling-edge",
        "hash-drift",
    }
    by_id = {case["id"]: case for case in fixtures}
    assert classify_candidate(by_id["raw-source-content"]["path"]) == "rejected-or-unsafe"
    assert classify_candidate(by_id["case-output"]["path"]) == "rejected-or-unsafe"
    assert classify_candidate(by_id["private-reference"]["path"]) == "private-reference-only"

    secret_file = tmp_path / "synthetic-credential.txt"
    secret_file.write_text(
        "api" + "_key=" + chr(34) + "x" * 32 + chr(34),
        encoding="utf-8",
    )
    assert any(error.startswith("secret_pattern:") for error in _copy_safety_errors(secret_file, tmp_path / "source"))

    path_file = tmp_path / "synthetic-path.txt"
    path_file.write_text(str(tmp_path / "source"), encoding="utf-8")
    assert "absolute_private_path" in _copy_safety_errors(path_file, tmp_path / "source")


def _mutable_snapshot(tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    shutil.copytree(SNAPSHOT, target)
    return target


def test_negative_fixture_silent_promotion_is_rejected(tmp_path: Path) -> None:
    target = _mutable_snapshot(tmp_path, "promotion")
    inventory_path = target / "inventory.jsonl"
    rows = _jsonl(inventory_path)
    rows[0]["review_status"] = "reviewed"
    inventory_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    result = validate_snapshot(target)
    assert not result["valid"]
    assert any(error.startswith("unexpected_promotion:") for error in result["errors"])


def test_negative_fixture_dangling_edge_is_rejected(tmp_path: Path) -> None:
    target = _mutable_snapshot(tmp_path, "dangling")
    graph_path = target / "knowledge-graph.json"
    graph = _json(graph_path)
    graph["edges"][0]["target"] = "missing-node"
    graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = validate_snapshot(target)
    assert not result["valid"]
    assert any(error.startswith("dangling_graph_edge:") for error in result["errors"])


def test_snapshot_hashes_are_stable_across_text_line_endings(tmp_path: Path) -> None:
    target = _mutable_snapshot(tmp_path, "line-endings")
    manifest = _json(target / "manifest.json")
    relative = next(iter(manifest["approved_copy_hashes"]))
    copy_path = target / "copies" / relative
    payload = copy_path.read_bytes().replace(b"\r\n", b"\n")
    copy_path.write_bytes(payload.replace(b"\n", b"\r\n"))
    assert validate_snapshot(target)["valid"]


def test_negative_fixture_hash_drift_is_rejected(tmp_path: Path) -> None:
    target = _mutable_snapshot(tmp_path, "hash-drift")
    manifest = _json(target / "manifest.json")
    relative = next(iter(manifest["approved_copy_hashes"]))
    with (target / "copies" / relative).open("ab") as handle:
        handle.write(b"\n")
    result = validate_snapshot(target)
    assert not result["valid"]
    assert f"copy_hash_mismatch:{relative}" in result["errors"]
