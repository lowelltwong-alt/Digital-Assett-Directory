from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import shutil

import pytest

from digital_asset_directory.entity_graph import build_entity_graph
from digital_asset_directory.entity_identity import fold_state, propose_relation, register_entity, semantic_card
from digital_asset_directory.entity_matching import compare_cards, find_candidates
from digital_asset_directory.portfolio_build_recovery import build_recovery_bundle, classify_worktree, snapshot_is_current
from digital_asset_directory.portfolio_related_work import search_related_work
from digital_asset_directory.transport import init_data_root


def _hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    source = Path(__file__).resolve().parents[1]
    repo = tmp_path / "hub"
    (repo / "registry").mkdir(parents=True)
    for name in (
        "agent-family-portfolio-registry.json",
        "agent-skill-library.json",
        "technical-product-company-os-registry.json",
    ):
        shutil.copy2(source / "registry" / name, repo / "registry" / name)
    data = tmp_path / "data"
    init_data_root(data, hub_root=repo, force_onedrive=True)
    monkeypatch.setenv("DAD_DATA_ROOT", str(data))
    return repo, data


def test_semantic_matching_never_merges_and_domains_stay_distinct() -> None:
    fullstack = semantic_card(label="Full-stack engineer family", entity_kind="agent_family", capabilities=["frontend", "backend", "database"], outcomes=["ship software"], domain_facets=["software engineering"])
    software = semantic_card(label="Software engineering family", entity_kind="agent_family", capabilities=["frontend", "backend", "database", "architecture"], outcomes=["ship software"], domain_facets=["software engineering"])
    biblical = semantic_card(label="Software engineering family", entity_kind="knowledge_library", capabilities=["exegesis"], outcomes=["biblical research"], domain_facets=["biblical studies"])
    related = compare_cards(fullstack, software)
    unrelated = compare_cards(fullstack, biblical)
    assert related["same_identity"] is False
    assert related["proposed_relation"] in {"specializes", "possible_duplicate_of", "peer_of", "variant_of"}
    assert unrelated["score"] < related["score"]


def test_equal_best_candidates_select_no_winner() -> None:
    source = {"entity_id": "source", "semantic_card": semantic_card(label="Frontend family", entity_kind="agent_family", capabilities=["frontend"])}
    candidates = [
        {"entity_id": "a", "semantic_card": semantic_card(label="Frontend family A", entity_kind="agent_family", capabilities=["frontend"])},
        {"entity_id": "b", "semantic_card": semantic_card(label="Frontend family B", entity_kind="agent_family", capabilities=["frontend"])},
    ]
    result = find_candidates(source, candidates)
    assert result["ambiguous_no_primary_candidate"] is True
    assert result["primary_candidate_id"] == ""


def test_entity_graph_rejects_cycles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _data = _hub(tmp_path, monkeypatch)
    a = register_entity(repo, semantic_card(label="A", entity_kind="concept"), observation_id="obs:a", source_ref="local")
    b = register_entity(repo, semantic_card(label="B", entity_kind="concept"), observation_id="obs:b", source_ref="local")
    propose_relation(repo, source_entity_id=a["payload"]["entity_id"], target_entity_id=b["payload"]["entity_id"], relation_type="continues", source_revision_id=a["payload"]["entity_revision_id"], target_revision_id=b["payload"]["entity_revision_id"], evidence_refs=["test"])
    propose_relation(repo, source_entity_id=b["payload"]["entity_id"], target_entity_id=a["payload"]["entity_id"], relation_type="continues", source_revision_id=b["payload"]["entity_revision_id"], target_revision_id=a["payload"]["entity_revision_id"], evidence_refs=["test"])
    from digital_asset_directory.entity_identity import read_events
    with pytest.raises(ValueError, match="Cycle detected"):
        build_entity_graph(fold_state(read_events(repo)))


def test_entity_journal_detects_payload_or_chain_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, data = _hub(tmp_path, monkeypatch)
    register_entity(
        repo, semantic_card(label="A", entity_kind="concept"),
        observation_id="obs:a", source_ref="local",
    )
    path = data / "raw" / "identity" / "entity-events.jsonl"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["payload"]["source_ref"] = "tampered"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    from digital_asset_directory.entity_identity import EntityIntegrityError, read_events
    with pytest.raises(EntityIntegrityError, match="digest mismatch"):
        read_events(repo)


def test_related_work_returns_at_most_five_candidate_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _data = _hub(tmp_path, monkeypatch)
    result = search_related_work(repo, repo, "full stack software engineering family")
    assert len(result["candidates"]) <= 5
    assert result["primary_candidate_id"] == ""
    assert result["execution_authorized"] is False
    assert result["coverage"]["external_embedding_calls"] == 0


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        ({"status_available": False}, "unknown"),
        ({"status_available": True, "dirty": True}, "dirty_unique_value_possible"),
        ({"status_available": True, "ahead": 2}, "ahead_unintegrated"),
        ({"status_available": True, "ahead": 1, "behind": 1}, "diverged"),
        ({"status_available": True, "contained_in_main": True}, "contained_in_main"),
    ],
)
def test_worktree_classification_is_conservative(observation: dict, expected: str) -> None:
    assert classify_worktree(observation) == expected


def test_clean_git_cannot_establish_completion_without_acceptance() -> None:
    observed = datetime.now(timezone.utc)
    worktree = {
        "status_available": True,
        "contained_in_main": True,
        "repository_id": "repo:fixture",
        "worktree_id": "worktree:fixture",
        "head_id": "commit:abc",
        "observed_at": observed.isoformat(),
    }
    bundle = build_recovery_bundle(
        plan={"plan_id": "p", "revision_id": "r", "implementation_state": "verified_complete"},
        worktree_observation=worktree,
    )
    assert bundle["classification"] == "contained_in_main"
    assert bundle["completion_supported"] is False
    assert bundle["execution_authorized"] is False
    assert "merge" in bundle["forbidden_git_actions"]
    material = {
        "plan_id": "p",
        "revision_id": "r",
        "worktree": worktree,
        "acceptance_evidence": [],
        "validation_evidence": [],
    }
    assert snapshot_is_current(bundle, material, now=observed + timedelta(minutes=1))
    assert not snapshot_is_current(bundle, material, now=observed + timedelta(minutes=16))


def test_recovery_bundle_requires_stable_snapshot_identity() -> None:
    with pytest.raises(ValueError, match="stable snapshot fields"):
        build_recovery_bundle(
            plan={"plan_id": "p", "revision_id": "r", "implementation_state": "partial"},
            worktree_observation={"status_available": True, "dirty": True},
        )


def test_recovery_bundle_sanitizes_evidence_and_stale_observations_fail_closed() -> None:
    stale = datetime.now(timezone.utc) - timedelta(days=30)
    bundle = build_recovery_bundle(
        plan={"plan_id": "p", "revision_id": "r", "implementation_state": "partial"},
        worktree_observation={
            "status_available": True,
            "dirty": True,
            "repository_id": "repo:fixture",
            "worktree_id": "worktree:fixture",
            "head_id": "commit:abc",
            "observed_at": stale.isoformat(),
        },
        acceptance_evidence=["C:\\Users\\lowel\\secret\\proof.txt"],
        validation_evidence=["token sk-12345678901234567890"],
    )
    assert bundle["snapshot_current"] is False
    assert bundle["classification"] == "unknown"
    assert "C:\\Users" not in repr(bundle)
    assert "sk-12345678901234567890" not in repr(bundle)
