from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from digital_asset_directory import portfolio_continuity_inventory as inventory
from digital_asset_directory import portfolio_continuity_search as continuity_search
from digital_asset_directory.portfolio_continuity_search import (
    search_continuity,
    search_continuity_all_sources,
)


def _git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "DAD Test",
        "GIT_AUTHOR_EMAIL": "dad@example.invalid",
        "GIT_COMMITTER_NAME": "DAD Test",
        "GIT_COMMITTER_EMAIL": "dad@example.invalid",
    }
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise AssertionError(f"git {args[0]} failed: {completed.stderr}")
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "private-repository-name"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    return repo


def _remote_only_commit(repo: Path, branch: str, filename: str, body: str) -> str:
    _git(repo, "switch", "-c", branch)
    (repo / filename).write_text(body, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-m", f"candidate {branch}")
    object_id = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", object_id)
    _git(repo, "switch", "main")
    _git(repo, "branch", "-D", branch)
    return object_id


def test_search_recovers_candidate_present_only_on_remote_ref_tree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    private_filename = "full-stack-engineering-agent-family.md"
    object_id = _remote_only_commit(
        repo,
        "unrelated-ref-name",
        private_filename,
        "private candidate body\n",
    )
    assert not (repo / private_filename).exists()

    packet = search_continuity(repo, "full stack engineering family")

    candidate = next(
        row
        for row in packet["candidates"]
        if row["source_kind"] == "git_object" and row["object_id"] == object_id
    )
    assert "tree_path_name" in candidate["matched_fields"]
    assert packet["primary_candidate_id"] == ""
    assert packet["coverage"]["network_calls"] == 0
    assert packet["coverage"]["git_writes"] == 0
    assert "codex_metadata_not_supplied" in packet["coverage"]["gaps"]
    assert packet["coverage"]["codex_source"] == "not_supplied"
    serialized = json.dumps(packet, sort_keys=True)
    assert str(repo.resolve()) not in serialized
    assert private_filename not in serialized
    assert "private candidate body" not in serialized
    assert "full stack engineering family" not in serialized


def test_search_recovers_candidate_preserved_only_by_local_tag(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    object_id = _remote_only_commit(
        repo,
        "tag-source",
        "forgotten-family-roadmap.md",
        "private tagged candidate\n",
    )
    _git(repo, "tag", "preserved-candidate", object_id)
    _git(repo, "update-ref", "-d", "refs/remotes/origin/tag-source")

    packet = search_continuity(repo, "forgotten family roadmap")

    candidate = next(
        row
        for row in packet["candidates"]
        if row["source_kind"] == "git_object" and row["object_id"] == object_id
    )
    assert candidate["object_id"] == object_id
    assert packet["primary_candidate_id"] == ""


def test_search_recovers_matching_dirty_overlay_without_persisting_path(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    private_filename = "hybrid-local-ai-roadmap.md"
    (repo / private_filename).write_text("uncommitted private idea\n", encoding="utf-8")

    packet = search_continuity(repo, "hybrid local ai roadmap")

    candidate = next(row for row in packet["candidates"] if row["source_kind"] == "dirty_overlay")
    assert candidate["changes"]["untracked"] == 1
    assert "dirty_path_name" in candidate["matched_fields"]
    serialized = json.dumps(packet, sort_keys=True)
    assert private_filename not in serialized
    assert "uncommitted private idea" not in serialized
    assert str(repo.resolve()) not in serialized


def test_equal_ref_candidates_remain_ambiguous_with_no_winner(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    first = _remote_only_commit(
        repo,
        "alpha",
        "portable-hybrid-agent-plan.md",
        "first private version\n",
    )
    second = _remote_only_commit(
        repo,
        "beta",
        "portable-hybrid-agent-plan.md",
        "second private version\n",
    )

    packet = search_continuity(repo, "portable hybrid agent plan")

    objects = {
        row["object_id"]
        for row in packet["candidates"]
        if row["source_kind"] == "git_object"
    }
    assert {first, second} <= objects
    assert packet["classification"] == "ambiguous_no_winner"
    assert packet["primary_candidate_id"] == ""


def test_search_uses_explicit_codex_metadata_privately_and_no_network_commands(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    commands: list[tuple[str, ...]] = []

    def recording_runner(cwd: Path, args: list[str] | tuple[str, ...]) -> inventory.GitResult:
        commands.append(tuple(args))
        return inventory._default_git_runner(cwd, args)

    task_id = "private-task-456"
    title = r"Continuity graph C:\Users\lowel\private\notes"
    packet = search_continuity(
        repo,
        "continuity graph",
        codex_metadata=[
            {
                "task_id": task_id,
                "title": title,
                "state": "active",
                "updated_at": "2026-07-16T12:00:00Z",
            }
        ],
        runner=recording_runner,
    )

    assert any(row["source_kind"] == "codex_item" for row in packet["candidates"])
    assert {row[0] for row in commands} <= {
        "rev-parse",
        "for-each-ref",
        "worktree",
        "status",
        "ls-tree",
    }
    assert not ({"fetch", "pull", "push", "remote", "update-ref"} & {row[0] for row in commands})
    serialized = json.dumps(packet, sort_keys=True)
    assert task_id not in serialized
    assert title not in serialized
    assert r"C:\Users\lowel" not in serialized


def test_unified_search_includes_dad_plan_entity_and_registry_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        continuity_search,
        "search_related_work",
        lambda *_a, **_k: {
            "candidates": [
                {
                    "candidate_id": "dad:portfolio-plan:hybrid-ai",
                    "candidate_kind": "plan",
                    "title": "Hybrid AI architecture",
                    "deterministic_score": 1.0,
                    "evidence_refs": ["plan-revision:one"],
                    "relation_candidate": "possible_duplicate_of",
                },
                {
                    "candidate_id": "family:cloud-platform-sre",
                    "candidate_kind": "agent_family",
                    "title": "Cloud Platform SRE",
                    "deterministic_score": 0.8,
                    "evidence_refs": ["registry/agent-family-portfolio-registry.json"],
                    "relation_candidate": "possible_duplicate_of",
                },
            ],
            "coverage": {
                "returned_count": 2,
                "unavailable_sources": [],
                "model_calls": 0,
            },
            "authority_boundary": "candidate only",
        },
    )

    packet = search_continuity_all_sources(
        repo, tmp_path / "hub", "hybrid ai architecture"
    )

    source_kinds = {row["source_kind"] for row in packet["candidates"]}
    assert {"dad_plan", "dad_agent_family"} <= source_kinds
    assert packet["schema_version"] == "dad.portfolio_continuity_search.v2"
    assert packet["primary_candidate_id"] == ""
    assert packet["coverage"]["network_calls"] == 0
    assert packet["coverage"]["git_writes"] == 0
    assert packet["coverage"]["model_calls"] == 0


def test_unified_search_degrades_corrupt_dad_identity_state_to_coverage_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        continuity_search,
        "search_related_work",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("corrupt private row")),
    )

    packet = search_continuity_all_sources(repo, tmp_path / "hub", "hybrid architecture")

    assert "dad_source_unavailable:dad_durable_identity_surfaces" in packet["coverage"]["gaps"]
    assert "corrupt private row" not in json.dumps(packet)
    assert packet["candidate_only"] is True
    assert packet["execution_authorized"] is False
