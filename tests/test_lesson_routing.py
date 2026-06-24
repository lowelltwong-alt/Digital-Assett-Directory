import json
from pathlib import Path

import pytest

from digital_asset_directory.learning import add_lesson, rebuild_lesson_routes

pytestmark = pytest.mark.integration


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_add_lesson_routes_to_repo_and_capability_indexes(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    record = add_lesson(
        hub,
        hub / "state" / "catalog.sqlite3",
        repository=str(tmp_path / "my-cool-repo"),
        summary="Learned something about evaluation",
        missing_capabilities=["evaluation_harness"],
        reusable_patterns=["redact once at the boundary"],
    )
    repo_index = hub / "raw" / "lessons" / "by-repo" / "my-cool-repo.jsonl"
    cap_index = hub / "raw" / "lessons" / "by-capability" / "evaluation-harness.jsonl"
    assert repo_index.exists() and cap_index.exists()

    pointer = _read_jsonl(repo_index)[0]
    assert pointer["lesson_id"] == record.lesson_id
    assert pointer["missing_capabilities"] == ["evaluation_harness"]
    assert pointer["source_path"].startswith("raw/lessons/")
    assert _read_jsonl(cap_index)[0]["lesson_id"] == record.lesson_id


def test_reindex_rebuilds_indexes_without_duplicates(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    db = hub / "state" / "catalog.sqlite3"
    add_lesson(
        hub, db, repository=str(tmp_path / "repo-a"), summary="A", missing_capabilities=["provenance"]
    )
    # Rebuild twice; each rebuild clears and regenerates from the canonical lesson files.
    rebuild_lesson_routes(hub)
    result = rebuild_lesson_routes(hub)
    cap_index = hub / "raw" / "lessons" / "by-capability" / "provenance.jsonl"
    assert result["lessons_indexed"] == 1
    assert len(_read_jsonl(cap_index)) == 1
