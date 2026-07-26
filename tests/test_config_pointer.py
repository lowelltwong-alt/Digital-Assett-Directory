"""Synthetic tests for the user-level local-config pointer (source-of-authority).

Covers the isolated-worktree problem: config/sources.local.yaml is gitignored,
so a fresh worktree must resolve the canonical config through a governed pointer
instead of a manual --config copy.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_asset_directory import config as C


def _repo_with_example(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "config" / "sources.example.yaml").write_text("project: {}\n", encoding="utf-8")
    return repo


def test_missing_local_config_falls_back_to_example(tmp_path: Path):
    repo = _repo_with_example(tmp_path)
    resolved = C.resolve_config_path(repo, environ={}, locator=tmp_path / "hub.json")
    assert resolved.name == "sources.example.yaml"


def test_env_pointer_resolves_canonical_config(tmp_path: Path):
    repo = _repo_with_example(tmp_path)
    canonical = tmp_path / "canonical.yaml"
    canonical.write_text("project: {}\n", encoding="utf-8")
    resolved = C.resolve_config_path(
        repo, environ={C.CONFIG_ENV_NAME: str(canonical)}, locator=tmp_path / "hub.json"
    )
    assert resolved == canonical


def test_locator_pointer_resolves_and_preserves_hub_path(tmp_path: Path):
    repo = _repo_with_example(tmp_path)
    canonical = tmp_path / "canonical.yaml"
    canonical.write_text("project: {}\n", encoding="utf-8")
    locator = tmp_path / "hub.json"
    locator.write_text(
        json.dumps({"schema_version": "dad.hub-locator.v1", "hub_path": "C:/hub", "hub_ref": "x"}),
        encoding="utf-8",
    )
    C.write_config_pointer(canonical, locator=locator)
    merged = json.loads(locator.read_text())
    assert merged["hub_path"] == "C:/hub"  # pointer write preserves existing locator fields
    assert Path(merged["config_path"]) == canonical.resolve()
    resolved = C.resolve_config_path(repo, environ={}, locator=locator)
    assert resolved == canonical.resolve()


def test_local_config_wins_over_pointer(tmp_path: Path):
    repo = _repo_with_example(tmp_path)
    (repo / "config" / "sources.local.yaml").write_text("project: {}\n", encoding="utf-8")
    canonical = tmp_path / "canonical.yaml"
    canonical.write_text("project: {}\n", encoding="utf-8")
    resolved = C.resolve_config_path(
        repo, environ={C.CONFIG_ENV_NAME: str(canonical)}, locator=tmp_path / "hub.json"
    )
    assert resolved.name == "sources.local.yaml"


def test_unusable_pointer_is_ignored_with_warning(tmp_path: Path):
    repo = _repo_with_example(tmp_path)
    missing = tmp_path / "nope.yaml"
    desc = C.describe_config_resolution(
        repo, environ={C.CONFIG_ENV_NAME: str(missing)}, locator=tmp_path / "hub.json"
    )
    assert desc["source"] == "repo_sources_example"
    assert desc["warnings"] and "readable file" in desc["warnings"][0]


def test_set_local_pointer_refuses_missing_file(tmp_path: Path):
    with pytest.raises(ValueError, match="missing file"):
        C.write_config_pointer(tmp_path / "does-not-exist.yaml", locator=tmp_path / "hub.json")
