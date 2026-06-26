from pathlib import Path

from digital_asset_directory.config import LocalSource, Settings
import digital_asset_directory.local_scan as local_scan
from digital_asset_directory.local_scan import discover_files, quarantine_summary, scan_local_source
from digital_asset_directory.scoring import DEFAULT_WEIGHTS
from digital_asset_directory.utils import sha256_file

import pytest

pytestmark = pytest.mark.integration


def test_local_scan_is_read_only_and_redacts_excerpt(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    readme = repo / "README.md"
    readme.write_text(
        "# Project\nsecret=do-not-store\nknowledge graph evaluation harness", encoding="utf-8"
    )
    empty_note = repo / "empty.md"
    empty_note.write_text("", encoding="utf-8")
    before = sha256_file(readme)
    source = LocalSource(id="test", path=tmp_path, path_alias="test", exclude=["**/.git/**"])
    assets, hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})
    assert sha256_file(readme) == before
    assert hashes[str(readme)] == before
    file_asset = next(a for a in assets if a.logical_path.endswith("README.md"))
    assert "do-not-store" not in file_asset.metadata["excerpt"]
    assert file_asset.parent_asset_id is not None
    assert file_asset.metadata_fingerprint
    assert file_asset.content_sha256 == before
    assert file_asset.source_provenance["authority"] == "Source repository remains authoritative."
    empty_asset = next(a for a in assets if a.logical_path.endswith("empty.md"))
    assert empty_asset.metadata["content_skipped_for_size"] is False
    assert empty_asset.metadata["excerpt"] == ""
    assert "exceeded the configured size limit" not in empty_asset.description


def test_default_noise_excludes_are_quarantined_not_scored(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# Real asset\nknowledge graph", encoding="utf-8")
    noisy = repo / ".pytest-tmp-root" / "pytest-of-Lowell" / "copy.schema.json"
    noisy.parent.mkdir(parents=True)
    noisy.write_text('{"title":"copy"}', encoding="utf-8")
    (repo / ".DS_Store").write_bytes(b"junk")
    source = LocalSource(id="test", path=tmp_path, path_alias="test", exclude=["**/.git/**"])

    files = discover_files(source)
    assets, _hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})
    quarantine = quarantine_summary(source)

    assert noisy not in files
    assert not any(asset.logical_path.endswith("copy.schema.json") for asset in assets)
    assert quarantine["count"] >= 2
    assert "pytest temp root" in quarantine["by_reason"]
    assert "macOS metadata file" in quarantine["by_reason"]


def test_quarantine_summary_can_be_bounded_for_validation_scans(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    for index in range(5):
        noisy = repo / ".pytest-tmp-root" / f"case-{index}" / "copy.txt"
        noisy.parent.mkdir(parents=True, exist_ok=True)
        noisy.write_text("temporary copy", encoding="utf-8")
    source = LocalSource(id="test", path=tmp_path, path_alias="test")

    quarantine = quarantine_summary(source, max_paths=1)

    assert quarantine["bounded"] is True
    assert quarantine["inspected_path_count"] == 1


def test_local_scan_adds_candidate_composite_patterns_to_repository(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "schemas").mkdir()
    (repo / "tests").mkdir()
    (repo / "workflows").mkdir()
    (repo / "docs").mkdir()
    (repo / "schemas" / "asset.schema.json").write_text(
        '{"title":"Asset schema","description":"json schema contract validation"}',
        encoding="utf-8",
    )
    (repo / "tests" / "test_graph.py").write_text(
        "def test_graph():\n    assert 'knowledge graph evaluation'\n",
        encoding="utf-8",
    )
    (repo / "workflows" / "agent_pipeline.md").write_text(
        "# Agent Workflow\npreflight postflight handoff agent orchestration learning loop",
        encoding="utf-8",
    )
    (repo / "docs" / "LESSONS.md").write_text(
        "# Lessons\nfeedback learning loop postflight lesson learned",
        encoding="utf-8",
    )
    source = LocalSource(id="test", path=tmp_path, path_alias="test", exclude=["**/.git/**"])

    assets, _hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})

    repo_asset = next(asset for asset in assets if asset.asset_type == "repository")
    pattern_ids = {
        str(pattern["pattern_id"]) for pattern in repo_asset.metadata.get("composite_patterns", [])
    }
    assert "evaluation_contract_system" in pattern_ids
    assert "governed_learning_loop_system" in pattern_ids
    assert repo_asset.metadata["composite_asset_hint"]["child_asset_count"] >= 4
    assert repo_asset.metadata["composite_asset_hint"]["authority"].startswith("Generated")
    assert "composite-asset" in repo_asset.tags


def test_local_scan_uses_metadata_identity_for_oversize_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    big_file = repo / "archive.bin"
    big_file.write_bytes(b"0123456789")

    original_sha256_file = local_scan.sha256_file

    def guarded_sha256_file(path: Path) -> str:
        if path == big_file:
            raise AssertionError("oversize files should not require full-byte hashing")
        return original_sha256_file(path)

    monkeypatch.setattr(local_scan, "sha256_file", guarded_sha256_file)
    source = LocalSource(
        id="test",
        path=tmp_path,
        path_alias="test",
        exclude=["**/.git/**"],
        max_file_bytes=5,
    )

    assets, hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})

    file_asset = next(a for a in assets if a.logical_path.endswith("archive.bin"))
    assert file_asset.content_hash == hashes[str(big_file)]
    assert file_asset.content_sha256 is None
    assert file_asset.metadata_fingerprint == hashes[str(big_file)]
    assert len(file_asset.content_hash) == 64
    assert file_asset.metadata["content_skipped_for_size"] is True
    assert file_asset.metadata["revision_identity_mode"] == "metadata_sha256_for_oversize_file"


def test_local_scan_profiles_skipped_text_code_without_full_content_hash(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    module = repo / "src" / "admission_validator.py"
    module.parent.mkdir()
    module.write_text(
        "\n".join(
            [
                "import json",
                "",
                "class AdmissionValidator:",
                "    def validate(self, packet):",
                "        return bool(packet)",
                "",
                "def build_validator():",
                "    return AdmissionValidator()",
            ]
        ),
        encoding="utf-8",
    )
    source = LocalSource(
        id="test",
        path=tmp_path,
        path_alias="test",
        exclude=["**/.git/**"],
        max_file_bytes=1,
    )

    assets, _hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})

    code_asset = next(a for a in assets if a.logical_path.endswith("admission_validator.py"))
    profile = code_asset.metadata["content_profile"]
    assert code_asset.content_sha256 is None
    assert code_asset.metadata["content_skipped_for_size"] is True
    assert code_asset.metadata["information_content_class"] == "content_profiled"
    assert profile["non_empty_line_count"] >= 5
    assert profile["class_count"] == 1
    assert profile["function_count"] == 2
    assert profile["code_role"] == "runtime_core"
    assert code_asset.value_components["content_role"] > 0


def test_local_scan_extracts_bounded_pdf_text_for_media_scoring(tmp_path: Path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    pdf = repo / "research.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Length 44>>stream\nBT (rare digital asset budget corpus) Tj ET\nendstream"
    )
    source = LocalSource(id="test", path=tmp_path, path_alias="test", exclude=["**/.git/**"])

    assets, _hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})

    media = next(asset for asset in assets if asset.logical_path.endswith("research.pdf"))
    assert media.asset_type == "media"
    assert media.metadata["extraction_method"] == "pdf_literal_strings"
    assert "digital asset budget corpus" in media.metadata["chunk_text"]
    assert media.value_components["information_content"] > 0


def test_local_scan_detects_cloud_placeholder_attributes(monkeypatch: pytest.MonkeyPatch):
    class FakeStat:
        st_file_attributes = local_scan.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS

    monkeypatch.setattr(local_scan.os, "name", "nt")
    assert local_scan._is_cloud_placeholder(FakeStat()) is True


def test_local_scan_cloud_placeholder_non_windows_fallback(monkeypatch: pytest.MonkeyPatch):
    class FakeStat:
        st_file_attributes = local_scan.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS

    monkeypatch.setattr(local_scan.os, "name", "posix")
    assert local_scan._is_cloud_placeholder(FakeStat()) is False
    assert local_scan._cloud_placeholder_detection_mode() == "bounded_size_only_non_windows"


def test_local_scan_ignores_files_that_vanish_during_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    missing = tmp_path / "vanished.md"
    source = LocalSource(id="test", path=tmp_path, path_alias="test")
    monkeypatch.setattr(local_scan, "discover_files", lambda _source, max_files=None: [missing])

    assets, hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})

    assert assets == []
    assert hashes == {}


def test_local_scan_marks_files_that_change_during_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / ".git").mkdir()
    note = repo / "README.md"
    note.write_text("# Project", encoding="utf-8")
    calls = 0

    def changing_identity(path: Path, max_file_bytes: int) -> tuple[str, str]:
        nonlocal calls
        if path == note:
            calls += 1
            return ("before", "content_sha256") if calls == 1 else ("after", "content_sha256")
        return ("stable", "content_sha256")

    monkeypatch.setattr(local_scan, "_file_revision_identity", changing_identity)
    source = LocalSource(id="test", path=tmp_path, path_alias="test", exclude=["**/.git/**"])

    assets, _hashes = scan_local_source(source, Settings(), {"weights": DEFAULT_WEIGHTS})

    file_asset = next(a for a in assets if a.logical_path.endswith("README.md"))
    assert file_asset.confidence == "low"
    assert file_asset.metadata["changed_during_scan"] is True
    assert file_asset.metadata["scan_stability"] == "changed_during_scan"
    assert file_asset.metadata["post_scan_revision_identity"] == "after"
